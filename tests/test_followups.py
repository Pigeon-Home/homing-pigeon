#!/usr/bin/env python3
"""v3.1 ask, retained query follow-ups, and judgment denylist.

Judgment cases call judge_job directly, or use kind=ping so the script
field is never executed.
"""
import io
import json
import os
import sys
import tempfile
import time
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import datetime, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "cloud"))
sys.path.insert(0, os.path.join(REPO, "tests"))

from runner.runner import (  # noqa: E402
    answer_queries,
    ask_model,
    inference_config,
    judge_job,
    load_retained,
    poll_once,
    save_retained,
)
from runner.install import store_additional_secret  # noqa: E402
from send_job import sign_payload, verify_body  # noqa: E402
from tests.test_runner import (  # noqa: E402
    SECRET, SENDER, FakeIMAP, FakeSMTP, job_email, job_payload,
)


def _signed(subject, payload, secret=SECRET):
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = SENDER
    msg["Subject"] = subject
    msg.set_content(sign_payload(payload, secret))
    return msg.as_bytes()


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _FakeResp:
    def __init__(self, text):
        self._raw = json.dumps(
            {"choices": [{"message": {"content": text}}]}).encode()

    def read(self, n=-1):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class InferenceTest(unittest.TestCase):
    def test_loopback_refused(self):
        self.assertIsNone(inference_config({}))
        self.assertIsNone(inference_config({
            "inference": {"endpoint": "http://127.0.0.1:11434/v1"},
        }))
        self.assertIsNone(inference_config({
            "inference": {
                "endpoint": "http://192.0.2.1/v1",
                "model": "llama3.1:8b",
            },
        }))
        self.assertIsNone(inference_config({
            "inference": {
                "endpoint": "http://not-loopback.invalid/v1",
                "model": "llama3.1:8b",
            },
        }))

    def test_loopback_accepted(self):
        for endpoint in (
            "http://127.0.0.1:11434/v1",
            "http://localhost:11434/v1",
            "http://[::1]:11434/v1",
        ):
            cfg = inference_config({
                "inference": {"endpoint": endpoint, "model": "llama3.1:8b"},
            })
            self.assertIsNotNone(cfg, endpoint)
            self.assertEqual(cfg["model"], "llama3.1:8b")

    def test_sanitization_rejects_private_key(self):
        inf = inference_config({
            "inference": {
                "endpoint": "http://127.0.0.1:11434/v1",
                "model": "llama3.1:8b",
            },
        })

        def opener(req, timeout=60):
            return _FakeResp("leak -----BEGIN PRIVATE KEY-----\nabc")

        got = ask_model(inf, "why?", "output", 2000, opener=opener)
        self.assertEqual(got, {"op": "ask", "rejected": "sanitization"})

    def test_ask_spends_budget_when_rejected(self):
        answers, spent = answer_queries(
            [{"op": "ask", "question": "why?"}],
            {"stdout": "fail", "stderr": "", "exit_code": 1},
            {},
            budget=1,
            cfg={},
        )
        self.assertEqual(spent, 1)
        self.assertEqual(answers[0]["rejected"], "inference_unconfigured")

    def test_ask_wired_when_configured(self):
        import runner.runner as rr
        inf_cfg = {
            "inference": {
                "endpoint": "http://127.0.0.1:11434/v1",
                "model": "llama3.1:8b",
            },
        }

        def fake(cfg, question, output_text, max_chars, patterns=None, opener=None, instructions=None):
            return {"op": "ask", "answer": "tests failed", "model": cfg["model"],
                    "sanitized": True}

        orig = rr.ask_model
        rr.ask_model = fake
        try:
            answers, spent = rr.answer_queries(
                [{"op": "ask", "question": "why?"}],
                {"stdout": "FAIL", "stderr": "", "exit_code": 1},
                {},
                2,
                cfg=inf_cfg,
            )
        finally:
            rr.ask_model = orig
        self.assertEqual(spent, 1)
        self.assertEqual(answers[0]["answer"], "tests failed")
        self.assertTrue(answers[0]["sanitized"])


class QueryFollowupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-q-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "shared_secret": SECRET,
            "imap_host": "fake",
            "imap_port": 993,
            "smtp_host": "fake",
            "smtp_port": 587,
            "poll_interval_sec": 20,
            "max_job_age_sec": 3600,
            "max_output_bytes": 100000,
            "base_dir": self.tmp,
            "default_timeout_sec": 300,
            "max_query_budget": 8,
            "output_retention_days": 7,
            "workers": 1,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails, seen=None):
        imap = FakeIMAP(mails)
        smtp = FakeSMTP()
        seen = {} if seen is None else seen
        poll_once(self.cfg, self.tmp, seen, self.seen_path, imap=imap, smtp=smtp)
        return imap, smtp, seen

    def test_unknown_job_rejected_and_seen(self):
        payload = {
            "v": 1, "type": "query", "query_id": "q-missing",
            "job_id": "no-such-job", "issued_at": _now(),
            "queries": [{"op": "grep", "pattern": "x"}],
        }
        imap, smtp, seen = self.cycle([
            _signed("[HOMING-PIGEON] query q-missing", payload),
        ])
        self.assertIn("1", imap.flagged)
        self.assertIn("query:q-missing", seen)
        body = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(body["rejected"], "unknown_job")
        self.assertEqual(body["type"], "qresult")

    def test_grep_tail_attest_against_retained(self):
        save_retained(self.tmp, "job1", {
            "job_id": "job1",
            "stdout": "ERROR: boom\nline2\nok\n",
            "stderr": "",
            "exit_code": 0,
            "view": "full",
            "budget": 4,
            "spent": 0,
            "patterns": {},
            "confined": True,
            "digest": "abc",
            "saved_at": time.time(),
        })
        payload = {
            "v": 1, "type": "query", "query_id": "q1", "job_id": "job1",
            "issued_at": _now(),
            "queries": [
                {"op": "grep", "pattern": "ERROR", "max_matches": 5},
                {"op": "tail", "lines": 1},
                {"op": "attest", "predicate": "exit_zero"},
            ],
        }
        _, smtp, _ = self.cycle([
            _signed("[HOMING-PIGEON] query q1", payload),
        ])
        body = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(body["answers"][0]["matches"], ["ERROR: boom"])
        self.assertEqual(body["answers"][1]["lines"], ["ok"])
        self.assertTrue(body["answers"][2]["value"])
        self.assertEqual(body["budget_remaining"], 1)
        retained = load_retained(self.tmp, "job1")
        self.assertEqual(retained["spent"], 3)

    def test_budget_exhaustion_spends(self):
        save_retained(self.tmp, "job2", {
            "job_id": "job2",
            "stdout": "hello\n",
            "stderr": "",
            "exit_code": 0,
            "view": "full",
            "budget": 1,
            "spent": 1,
            "patterns": {},
            "confined": False,
            "saved_at": time.time(),
        })
        payload = {
            "v": 1, "type": "query", "query_id": "q-budget", "job_id": "job2",
            "issued_at": _now(),
            "queries": [{"op": "grep", "pattern": "hello"}],
        }
        _, smtp, _ = self.cycle([
            _signed("[HOMING-PIGEON] query q-budget", payload),
        ])
        body = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(body["answers"][0], {"rejected": "budget"})
        self.assertEqual(load_retained(self.tmp, "job2")["spent"], 2)
        self.assertEqual(body["budget_remaining"], 0)


class JudgmentDenylistTest(unittest.TestCase):
    def test_denylist_patterns_do_not_execute(self):
        scripts = [
            "rm -rf /",
            "rm -rf ~",
            ":(){ :|:& };:",
            "mkfs.ext4 /dev/sda",
            "dd if=/dev/zero of=/dev/sda bs=1M",
        ]
        for script in scripts:
            verdict, reasons = judge_job(
                {"judge": "enforce"}, {"kind": "ping", "script": script})
            self.assertEqual(verdict, "fail", script)
            self.assertTrue(reasons, script)

    def test_non_https_and_dotdot(self):
        _, reasons = judge_job(
            {"judge": "enforce"},
            {"kind": "ping", "script_url": "http://example.invalid/s"},
        )
        self.assertTrue(any("non-https" in r for r in reasons))
        _, reasons = judge_job(
            {"judge": "enforce"},
            {"kind": "ping", "files": [{"name": "../evil", "url": "https://x"}]},
        )
        self.assertTrue(any("path traversal" in r for r in reasons))

    def test_enforce_rejects_ping_before_execute(self):
        tmp = tempfile.mkdtemp(prefix="hp-judge-")
        cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "shared_secret": SECRET,
            "base_dir": tmp,
            "judge": "enforce",
            "workers": 1,
        }
        jid = str(uuid.uuid4())
        # kind=ping: judge reads script, execute_job never runs it.
        mail = job_email(job_payload(jid, script="rm -rf /"))
        imap = FakeIMAP([mail])
        smtp = FakeSMTP()
        seen = {}
        poll_once(cfg, tmp, seen, os.path.join(tmp, "seen.json"),
                  imap=imap, smtp=smtp)
        result = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("judge blocked", result["stderr"])
        self.assertIn(jid, seen)

    def test_advisory_attaches_verdict_and_runs(self):
        tmp = tempfile.mkdtemp(prefix="hp-judge-")
        cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "shared_secret": SECRET,
            "base_dir": tmp,
            "judge": "advisory",
            "workers": 1,
        }
        jid = str(uuid.uuid4())
        mail = job_email(job_payload(jid, script="mkfs"))
        smtp = FakeSMTP()
        poll_once(cfg, tmp, {}, os.path.join(tmp, "seen.json"),
                  imap=FakeIMAP([mail]), smtp=smtp)
        result = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["judgment"]["verdict"], "fail")
        self.assertTrue(result["judgment"]["reasons"])


class AdditionalSecretTest(unittest.TestCase):
    def test_stored_and_not_printed(self):
        tmp = tempfile.mkdtemp(prefix="hp-secret-")
        cfg_path = os.path.join(tmp, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump({"shared_secret": SECRET, "additional_secrets": {}}, fh)
        buf = io.StringIO()
        with redirect_stdout(buf):
            store_additional_secret(cfg_path, "grok-4")
        out = buf.getvalue()
        self.assertIn("additional secret stored for grok-4", out)
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        secret = cfg["additional_secrets"]["grok-4"]
        self.assertGreaterEqual(len(secret), 32)
        self.assertNotIn(secret, out)
        self.assertNotIn(secret, buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
