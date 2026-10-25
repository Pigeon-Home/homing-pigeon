#!/usr/bin/env python3
"""Verification tests for the v3.1 work landed after e3cebb9.

No live model. No network call. Judgment cases use kind=ping or call
judge_job directly, so a denylisted script field is never executed.
"""
import io
import json
import os
import stat
import sys
import tempfile
import time
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))
sys.path.insert(0, os.path.join(REPO, "runner", "tests"))

import runner.runner as rr  # noqa: E402
from runner.runner import (  # noqa: E402
    _InferenceRedirectRefused,
    answer_queries,
    ask_model,
    inference_config,
    judge_job,
    load_retained,
    poll_once,
    retained_expired,
    save_retained,
)
from runner.wire import jobcrypto  # noqa: E402
from runner.ops.install import store_additional_secret  # noqa: E402
from send_job import sign_payload, verify_body  # noqa: E402
from runner.tests.test_runner import (  # noqa: E402
    SECRET, SENDER, FakeIMAP, FakeSMTP, job_email, job_payload,
)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _signed(subject, payload, secret=SECRET):
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = SENDER
    msg["Subject"] = subject
    signed = sign_payload(payload, secret)
    ident = subject.rsplit(" ", 1)[-1]
    key_id = payload.get("key_id") if isinstance(payload, dict) else ""
    wire = jobcrypto.encrypt_body(
        signed, secret, job_id=ident, key_id=key_id or "",
        sign=sign_payload)
    msg.set_content(wire)
    return msg.as_bytes()


def _read_result(msg, secret=SECRET):
    """Verify a job-result mail, unwrapping the hp_enc envelope
    the result mirrors from its (encrypted) job."""
    body = verify_body(msg.get_content(), secret)
    if jobcrypto.is_envelope(body):
        jid = str(msg["Subject"]).rsplit(" ", 1)[-1]
        inner = jobcrypto.decrypt_body(
            body, secret, jid, body.get("key_id") or "")
        body = verify_body(inner, secret)
    return body


class _FakeResp:
    def __init__(self, content):
        self._raw = json.dumps(
            {"choices": [{"message": {"content": content}}]}).encode()

    def read(self, n=-1):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _CaptureOpener:
    """Stand-in for urlopen. Records the request and returns a canned reply."""

    def __init__(self, content):
        self.content = content
        self.calls = []

    def __call__(self, req, timeout=60):
        self.calls.append({
            "url": req.full_url,
            "body": json.loads(req.data.decode("utf-8")),
            "timeout": timeout,
        })
        return _FakeResp(self.content)


def _loopback_cfg(**extra):
    inf = {
        "endpoint": "http://127.0.0.1:11434/v1",
        "model": "llama3.1:8b",
    }
    inf.update(extra)
    return {"inference": inf}


class InferenceGateTest(unittest.TestCase):
    def test_fail_closed_matrix(self):
        refused = [
            {},
            {"inference": "http://127.0.0.1:11434/v1"},
            {"inference": {"endpoint": "  ", "model": "llama3.1:8b"}},
            {"inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "  "}},
            {"inference": {
                "endpoint": "file:///tmp/model",
                "model": "llama3.1:8b",
            }},
            {"inference": {
                "endpoint": "http://0.0.0.0:11434/v1",
                "model": "llama3.1:8b",
            }},
            {"inference": {
                "endpoint": "http://192.0.2.9/v1",
                "model": "llama3.1:8b",
            }},
            {"inference": {
                "endpoint": "http://127.0.0.1:11434/v1",
                "model": "llama3.1:8b",
                "max_answer_chars": -1,
            }},
            {"inference": {
                "endpoint": "http://127.0.0.1:11434/v1",
                "model": "llama3.1:8b",
                "timeout_sec": -1,
            }},
            {"inference": {
                "endpoint": "http://127.0.0.1:11434/v1",
                "model": "llama3.1:8b",
                "max_answer_chars": "many",
            }},
        ]
        for cfg in refused:
            self.assertIsNone(inference_config(cfg), cfg)

    def test_normalizes_safe_endpoint(self):
        cfg = inference_config({
            "inference": {
                "endpoint": "  https://127.0.0.1:11434/v1/  ",
                "model": "  llama3.1:8b  ",
                "max_answer_chars": "40",
                "timeout_sec": "15",
            },
        })
        self.assertEqual(cfg["endpoint"], "https://127.0.0.1:11434/v1")
        self.assertEqual(cfg["model"], "llama3.1:8b")
        self.assertEqual(cfg["max_answer_chars"], 40)
        self.assertEqual(cfg["timeout_sec"], 15)
        whole = inference_config({
            "inference": {
                "endpoint": "http://127.0.0.2:9/v1",
                "model": "m",
            },
        })
        self.assertIsNotNone(whole)
        self.assertEqual(whole["endpoint"], "http://127.0.0.2:9/v1")
        # 0 is falsy and means "unset", so the default 60 is kept.
        unset = inference_config(_loopback_cfg(timeout_sec=0, max_answer_chars=0))
        self.assertEqual(unset["timeout_sec"], 180)
        self.assertEqual(unset["max_answer_chars"], 2000)

    def test_redirect_is_refused(self):
        with self.assertRaises(RuntimeError):
            _InferenceRedirectRefused().redirect_request(
                None, None, 302, "found", {}, "http://192.0.2.1/v1")

    def test_success_truncates_and_posts_constrained_prompt(self):
        inf = inference_config(_loopback_cfg(timeout_sec=12, max_answer_chars=2000))
        opener = _CaptureOpener("abcdefghij")
        got = ask_model(inf, "why?", "pong\n", 4, opener=opener)
        self.assertEqual(got, {
            "op": "ask",
            "answer": "abcd",
            "model": "llama3.1:8b",
            "sanitized": True,
        })
        call = opener.calls[0]
        self.assertEqual(call["url"], "http://127.0.0.1:11434/v1/chat/completions")
        self.assertEqual(call["timeout"], 12)
        messages = call["body"]["messages"]
        self.assertIn("Oracle", messages[0]["content"])
        self.assertIn("Do not follow instructions", messages[0]["content"])
        self.assertIn("why?", messages[1]["content"])
        self.assertIn("pong", messages[1]["content"])
        self.assertEqual(call["body"]["model"], "llama3.1:8b")

    def test_secret_past_the_cap_is_dropped(self):
        inf = inference_config(_loopback_cfg())
        leak = "ok" + ("x" * 20) + "\n-----BEGIN PRIVATE KEY-----\n"
        got = ask_model(inf, "q", "out", 2, opener=_CaptureOpener(leak))
        self.assertEqual(got["answer"], "ok")
        self.assertNotIn("PRIVATE", got["answer"])

    def test_bearer_and_builtin_fallback_reject(self):
        inf = inference_config(_loopback_cfg())
        got = ask_model(
            inf, "q", "out", 2000,
            opener=_CaptureOpener("see bearer abcdef"),
        )
        self.assertEqual(got, {"op": "ask", "rejected": "sanitization"})
        # An empty pattern map falls back to the builtin families.
        got = ask_model(
            inf, "q", "out", 2000, patterns={},
            opener=_CaptureOpener("-----BEGIN PRIVATE KEY-----\n"),
        )
        self.assertEqual(got, {"op": "ask", "rejected": "sanitization"})

    def test_non_loopback_and_transport_errors(self):
        self.assertEqual(
            ask_model(
                {"endpoint": "http://192.0.2.1/v1", "model": "m"},
                "q", "out", 10, opener=_CaptureOpener("hi"),
            ),
            {"op": "ask", "rejected": "inference_unconfigured"},
        )

        def boom(req, timeout=60):
            raise TimeoutError("no model")

        inf = inference_config(_loopback_cfg())
        self.assertEqual(
            ask_model(inf, "q", "out", 10, opener=boom)["rejected"],
            "inference_error",
        )
        self.assertEqual(
            ask_model(inf, "q", "out", 10, opener=_CaptureOpenerBroken())["rejected"],
            "inference_error",
        )

    def test_non_string_reply_and_zero_cap(self):
        inf = inference_config(_loopback_cfg())
        got = ask_model(inf, "q", "out", 20, opener=_FakeContent(7))
        self.assertEqual(got["answer"], "7")
        got = ask_model(inf, "q", "out", -5, opener=_CaptureOpener("hello"))
        self.assertEqual(got["answer"], "")
        self.assertTrue(got["sanitized"])


class _FakeContent:
    def __init__(self, content):
        self.content = content

    def __call__(self, req, timeout=60):
        return _FakeResp(self.content)


class _CaptureOpenerBroken:
    def __call__(self, req, timeout=60):
        return _BrokenResp()


class _BrokenResp:
    def read(self, n=-1):
        return b"not-json"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class AnswerQueryBranchTest(unittest.TestCase):
    def test_grep_tail_policy_redaction_and_budget(self):
        text = {
            "stdout": "ERROR one\nERROR two\nkeep\n",
            "stderr": "ERROR three\n",
            "exit_code": 0,
        }
        answers, spent = answer_queries(
            [
                {"op": "grep", "pattern": "ERROR", "max_matches": 1},
                {"op": "grep", "pattern": "(["},
                {"op": "tail", "lines": 0},
                "nope",
                {"op": "nope"},
            ],
            text, {}, budget=5,
        )
        self.assertEqual(spent, 5)
        self.assertEqual(answers[0]["matches"], ["ERROR one"])
        self.assertTrue(answers[0]["truncated"])
        self.assertEqual(answers[1]["rejected"], "bad_pattern")
        self.assertEqual(answers[2]["lines"], [])
        self.assertEqual(answers[3]["rejected"], "unknown_op")
        self.assertEqual(answers[4]["rejected"], "unknown_op")

        # stderr is part of the searchable blob
        answers, _ = answer_queries(
            [{"op": "grep", "pattern": "three"}],
            text, {}, budget=1,
        )
        self.assertEqual(answers[0]["matches"], ["ERROR three"])

        for view in ("attested", "summary"):
            answers, spent = answer_queries(
                [{"op": "grep", "pattern": "ERROR"}, {"op": "tail", "lines": 1}],
                text, {}, budget=2, view=view,
            )
            self.assertEqual(spent, 2, view)
            self.assertEqual(answers[0]["rejected"], "policy", view)
            self.assertEqual(answers[1]["rejected"], "policy", view)

        patterns = {"aws_key": r"AKIA[0-9A-Z]{16}"}
        answers, _ = answer_queries(
            [{"op": "tail", "lines": 1}, {"op": "grep", "pattern": "AKIA"}],
            {"stdout": "id AKIA1234567890ABCDEF\n", "stderr": ""},
            patterns, budget=2, view="redacted",
        )
        self.assertEqual(answers[0]["lines"], ["id [REDACTED:aws_key]"])
        self.assertIn("[REDACTED:aws_key]", answers[1]["matches"][0])
        self.assertNotIn("AKIA1234567890ABCD", json.dumps(answers))

    def test_budget_stops_mid_list_and_attest_unknown(self):
        answers, spent = answer_queries(
            [
                {"op": "grep", "pattern": "a"},
                {"op": "grep", "pattern": "a"},
            ],
            {"stdout": "a\n", "stderr": ""},
            {}, budget=1,
        )
        self.assertEqual(answers[0]["matches"], ["a"])
        self.assertEqual(answers[1], {"rejected": "budget"})
        self.assertEqual(spent, 2)

        answers, spent = answer_queries(
            [{"op": "attest", "predicate": "not_a_real_predicate"}],
            {"stdout": "", "stderr": "", "exit_code": 0},
            {}, budget=1,
        )
        self.assertEqual(spent, 1)
        self.assertFalse(answers[0]["value"])
        self.assertEqual(answers[0]["reason"], "unknown")

    def test_ask_uses_real_ask_model_and_spends_on_reject(self):
        opener = _CaptureOpener("-----BEGIN PRIVATE KEY-----\nsecret")
        orig = rr._default_inference_open
        rr._default_inference_open = opener
        try:
            answers, spent = answer_queries(
                [{"op": "ask", "question": "summarize", "max_chars": 50}],
                {"stdout": "line\n", "stderr": ""},
                {},
                budget=1,
                cfg=_loopback_cfg(),
            )
        finally:
            rr._default_inference_open = orig
        self.assertEqual(spent, 1)
        self.assertEqual(answers[0], {"op": "ask", "rejected": "sanitization"})
        self.assertIn("summarize", opener.calls[0]["body"]["messages"][1]["content"])
        self.assertIn("line", opener.calls[0]["body"]["messages"][1]["content"])


class RetainedEdgeTest(unittest.TestCase):
    def test_unsafe_corrupt_and_expiry(self):
        tmp = tempfile.mkdtemp(prefix="hp-ret-")
        save_retained(tmp, "job-ok", {"job_id": "job-ok", "stdout": "pong"})
        self.assertEqual(load_retained(tmp, "job-ok")["stdout"], "pong")
        for bad in ("../job-ok", "/tmp/job-ok", "a/b", "", ".", "..", "x" * 129, None, 3):
            self.assertIsNone(load_retained(tmp, bad), bad)
        outside = os.path.join(tmp, "job-ok.json")
        self.assertFalse(os.path.exists(outside))

        path = os.path.join(tmp, "retained", "broken.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertIsNone(load_retained(tmp, "broken"))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("[1, 2]")
        self.assertIsNone(load_retained(tmp, "broken"))

        fresh = {"saved_at": time.time()}
        old = {"saved_at": time.time() - 10 * 86400}
        self.assertFalse(retained_expired(fresh, {"output_retention_days": 7}))
        self.assertTrue(retained_expired(old, {"output_retention_days": 7}))
        # 0 is explicit: it disables expiry, and prune_retained
        # agrees (it prunes nothing at 0). The two readers of the
        # key once disagreed about 0; they now share one reading.
        self.assertFalse(retained_expired(old, {"output_retention_days": 0}))
        # A negative value also disables expiry.
        self.assertFalse(retained_expired(old, {"output_retention_days": -1}))
        self.assertTrue(retained_expired({"saved_at": "yesterday"}, {}))
        self.assertTrue(retained_expired({}, {}))


class QueryMailVerifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-qv-")
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
        rr._QUERY_TIMES.clear()

    def tearDown(self):
        rr._QUERY_TIMES.clear()

    def cycle(self, mails, seen=None):
        imap = FakeIMAP(mails)
        smtp = FakeSMTP()
        seen = {} if seen is None else seen
        poll_once(self.cfg, self.tmp, seen, self.seen_path, imap=imap, smtp=smtp)
        return imap, smtp, seen

    def test_job_then_followup_and_script_is_not_run(self):
        jid = "job-" + uuid.uuid4().hex
        # kind=ping. The script field is there for the judge to read.
        # ping returns pong and does not execute script.
        job = job_payload(jid, script="rm -rf /", result_policy={
            "view": "full",
            "queries": [{"op": "attest", "predicate": "exit_zero"}],
        })
        follow = {
            "v": 1, "type": "query", "query_id": "q-follow",
            "job_id": jid, "issued_at": _now(),
            "queries": [{"op": "grep", "pattern": "^pong$"}],
        }
        _, smtp, _ = self.cycle([
            job_email(job),
            _signed("[HOMING-PIGEON] query q-follow", follow),
        ])
        result = _read_result(smtp.sent[0])
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["stderr"], "")
        self.assertEqual(result["exit_code"], 0)
        self.assertNotIn("rm -rf", result["stderr"])
        qresult = _read_result(smtp.sent[1])
        self.assertEqual(qresult["answers"][0]["matches"], ["pong"])
        retained = load_retained(self.tmp, jid)
        self.assertEqual(retained["spent"], 2)
        self.assertEqual(qresult["budget_remaining"], retained["budget"] - 2)

    def test_expired_rate_limit_and_attested_view(self):
        save_retained(self.tmp, "old-job", {
            "job_id": "old-job", "stdout": "secret-line\n", "stderr": "",
            "exit_code": 0, "view": "full", "budget": 4, "spent": 0,
            "patterns": {}, "saved_at": time.time() - 30 * 86400,
        })
        payload = {
            "v": 1, "type": "query", "query_id": "q-old",
            "job_id": "old-job", "issued_at": _now(),
            "queries": [{"op": "tail", "lines": 1}],
        }
        _, smtp, seen = self.cycle([
            _signed("[HOMING-PIGEON] query q-old", payload),
        ])
        body = _read_result(smtp.sent[0])
        self.assertEqual(body["rejected"], "expired")
        self.assertEqual(load_retained(self.tmp, "old-job")["spent"], 0)
        self.assertIn("query:q-old", seen)

        save_retained(self.tmp, "rate-job", {
            "job_id": "rate-job", "stdout": "pong\n", "stderr": "",
            "exit_code": 0, "view": "full", "budget": 4, "spent": 0,
            "patterns": {}, "saved_at": time.time(),
        })
        self.cfg["max_queries_per_hour"] = 1
        first = {
            "v": 1, "type": "query", "query_id": "q-r1",
            "job_id": "rate-job", "issued_at": _now(),
            "queries": [{"op": "grep", "pattern": "pong"}],
        }
        second = dict(first, query_id="q-r2")
        _, smtp, _ = self.cycle([
            _signed("[HOMING-PIGEON] query q-r1", first),
            _signed("[HOMING-PIGEON] query q-r2", second),
        ])
        ok = _read_result(smtp.sent[0])
        limited = _read_result(smtp.sent[1])
        self.assertEqual(ok["answers"][0]["matches"], ["pong"])
        self.assertEqual(limited["rejected"], "rate_limit")
        self.assertEqual(load_retained(self.tmp, "rate-job")["spent"], 1)

        save_retained(self.tmp, "att-job", {
            "job_id": "att-job", "stdout": "hidden\n", "stderr": "",
            "exit_code": 0, "view": "attested", "budget": 2, "spent": 0,
            "patterns": {}, "saved_at": time.time(),
        })
        self.cfg["max_queries_per_hour"] = 0
        rr._QUERY_TIMES.clear()
        att = {
            "v": 1, "type": "query", "query_id": "q-att",
            "job_id": "att-job", "issued_at": _now(),
            "queries": [{"op": "grep", "pattern": "hidden"}],
        }
        _, smtp, _ = self.cycle([
            _signed("[HOMING-PIGEON] query q-att", att),
        ])
        body = _read_result(smtp.sent[0])
        self.assertEqual(body["answers"][0]["rejected"], "policy")
        self.assertNotIn("hidden", smtp.sent[0].get_content())
        self.assertEqual(load_retained(self.tmp, "att-job")["spent"], 1)

    def test_rejects_without_leaking_and_duplicate_is_silent(self):
        raw_bad = EmailMessage()
        raw_bad["From"] = SENDER
        raw_bad["To"] = SENDER
        raw_bad["Subject"] = "[HOMING-PIGEON] query q-bad"
        raw_bad.set_content("not a signed body")
        imap, smtp, seen = self.cycle([raw_bad.as_bytes()])
        self.assertIn("1", imap.flagged)
        self.assertEqual(smtp.sent, [])
        self.assertNotIn("query:q-bad", seen)

        stale = {
            "v": 1, "type": "query", "query_id": "q-stale",
            "job_id": "missing", "issued_at": "2001-01-01T00:00:00Z",
            "queries": [{"op": "tail", "lines": 1}],
        }
        imap, smtp, seen = self.cycle([
            _signed("[HOMING-PIGEON] query q-stale", stale),
        ])
        self.assertEqual(smtp.sent, [])
        self.assertIn("query:q-stale", seen)
        self.assertIn("1", imap.flagged)

        bad_type = {
            "v": 1, "type": "job", "query_id": "q-type",
            "job_id": "missing", "issued_at": _now(),
        }
        _, smtp, _ = self.cycle([
            _signed("[HOMING-PIGEON] query q-type", bad_type),
        ])
        body = _read_result(smtp.sent[0])
        self.assertEqual(body["rejected"], "unsupported")

        trav = {
            "v": 1, "type": "query", "query_id": "q-trav",
            "job_id": "../config", "issued_at": _now(),
            "queries": [{"op": "tail", "lines": 1}],
        }
        _, smtp, _ = self.cycle([
            _signed("[HOMING-PIGEON] query q-trav", trav),
        ])
        body = _read_result(smtp.sent[0])
        self.assertEqual(body["rejected"], "unknown_job")

        save_retained(self.tmp, "dup-job", {
            "job_id": "dup-job", "stdout": "pong\n", "stderr": "",
            "exit_code": 0, "view": "full", "budget": 3, "spent": 0,
            "patterns": {}, "saved_at": time.time(),
        })
        dup = {
            "v": 1, "type": "query", "query_id": "q-dup",
            "job_id": "dup-job", "issued_at": _now(),
            "queries": [{"op": "grep", "pattern": "pong"}],
        }
        mail = _signed("[HOMING-PIGEON] query q-dup", dup)
        _, smtp, seen = self.cycle([mail, mail])
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(load_retained(self.tmp, "dup-job")["spent"], 1)
        self.assertIn("query:q-dup", seen)

    def test_ask_sanitization_runs_before_the_email(self):
        save_retained(self.tmp, "ask-job", {
            "job_id": "ask-job", "stdout": "unit output\n", "stderr": "",
            "exit_code": 0, "view": "full", "budget": 2, "spent": 0,
            "patterns": {
                "private_key": r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
            },
            "saved_at": time.time(),
        })
        self.cfg.update(_loopback_cfg())
        opener = _CaptureOpener("leak -----BEGIN PRIVATE KEY-----\nabc")
        orig = rr._default_inference_open
        rr._default_inference_open = opener
        try:
            payload = {
                "v": 1, "type": "query", "query_id": "q-ask",
                "job_id": "ask-job", "issued_at": _now(),
                "queries": [{"op": "ask", "question": "what failed?"}],
            }
            _, smtp, _ = self.cycle([
                _signed("[HOMING-PIGEON] query q-ask", payload),
            ])
        finally:
            rr._default_inference_open = orig
        raw = smtp.sent[0].get_content()
        body = _read_result(smtp.sent[0])
        self.assertEqual(body["answers"][0], {"op": "ask", "rejected": "sanitization"})
        self.assertNotIn("PRIVATE KEY", raw)
        self.assertEqual(load_retained(self.tmp, "ask-job")["spent"], 1)
        self.assertEqual(len(opener.calls), 1)


class InstallVerifyTest(unittest.TestCase):
    def test_rejects_bad_id_and_merges(self):
        tmp = tempfile.mkdtemp(prefix="hp-inst-")
        cfg_path = os.path.join(tmp, "config.json")
        original = {
            "shared_secret": SECRET,
            "additional_secrets": {"kept": "already-there-value-not-printed"},
        }
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(original, fh)

        buf, err = io.StringIO(), io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            with self.assertRaises(SystemExit) as raised:
                store_additional_secret(cfg_path, "../nope")
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("KEY_ID", err.getvalue())
        with open(cfg_path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["additional_secrets"], original["additional_secrets"])
        self.assertNotIn("already-there", buf.getvalue())

        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump({"shared_secret": SECRET, "additional_secrets": [1]}, fh)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                store_additional_secret(cfg_path, "ok-id")
        self.assertEqual(raised.exception.code, 2)

        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump({"shared_secret": SECRET}, fh)
        out = io.StringIO()
        with redirect_stdout(out):
            store_additional_secret(cfg_path, "lane-a")
            store_additional_secret(cfg_path, "lane-b")
        text = out.getvalue()
        self.assertIn("additional secret stored for lane-a", text)
        self.assertIn("additional secret stored for lane-b", text)
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertEqual(cfg["shared_secret"], SECRET)
        self.assertEqual(set(cfg["additional_secrets"]), {"lane-a", "lane-b"})
        for value in cfg["additional_secrets"].values():
            self.assertGreaterEqual(len(value), 32)
            self.assertNotIn(value, text)
        self.assertFalse(os.path.exists(cfg_path + ".tmp"))
        # Windows does not honor Unix mode bits: chmod(0o600) is a
        # no-op there and stat comes back 0o666. Require 0o600 on POSIX;
        # on Windows the file inherits the parent directory's ACLs.
        if os.name != "nt":
            mode = stat.S_IMODE(os.stat(cfg_path).st_mode)
            self.assertEqual(mode, 0o600)


class JudgeOffPathTest(unittest.TestCase):
    def test_off_ignores_denylist_and_ping_still_pongs(self):
        verdict, reasons = judge_job(
            {"judge": "off"}, {"kind": "ping", "script": "rm -rf /"})
        self.assertEqual((verdict, reasons), ("pass", []))
        verdict, reasons = judge_job(
            {}, {"kind": "ping", "script": "mkfs.ext4 /dev/sda",
                 "script_url": "https://example.invalid/s"})
        self.assertEqual(verdict, "pass")
        self.assertEqual(reasons, [])

        verdict, reasons = judge_job(
            {"judge": "enforce"},
            {"kind": "ping", "script": "echo ok",
             "script_url": "https://example.invalid/s",
             "files": ["not-a-dict", {"name": "safe.py"}]},
        )
        self.assertEqual((verdict, reasons), ("pass", []))

        tmp = tempfile.mkdtemp(prefix="hp-joff-")
        cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "shared_secret": SECRET,
            "base_dir": tmp,
            "judge": "off",
            "workers": 1,
        }
        jid = str(uuid.uuid4())
        smtp = FakeSMTP()
        poll_once(
            cfg, tmp, {}, os.path.join(tmp, "seen.json"),
            imap=FakeIMAP([job_email(job_payload(jid, script="rm -rf /"))]),
            smtp=smtp,
        )
        result = _read_result(smtp.sent[0])
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["exit_code"], 0)
        self.assertNotIn("judgment", result)
        self.assertNotIn("rm -rf", result.get("stderr") or "")


class BoardVerifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-bv-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "shared_secret": SECRET,
            "base_dir": self.tmp,
            "workers": 1,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def test_second_offer_is_empty_and_duplicate_submit_fails(self):
        issued = _now()
        mails = [
            _signed("[HOMING-PIGEON] task_submit t-one", {
                "v": 1, "type": "task_submit", "task_id": "t-one",
                "issued_at": issued, "capabilities": ["py"],
            }),
            _signed("[HOMING-PIGEON] task_request w1", {
                "v": 1, "type": "task_request", "issued_at": issued,
                "capabilities": ["py"],
            }),
            _signed("[HOMING-PIGEON] task_request w2", {
                "v": 1, "type": "task_request", "issued_at": issued,
                "capabilities": ["py"],
            }),
            _signed("[HOMING-PIGEON] task_submit t-one", {
                "v": 1, "type": "task_submit", "task_id": "t-one",
                "issued_at": issued,
            }),
        ]
        smtp = FakeSMTP()
        poll_once(self.cfg, self.tmp, {}, self.seen_path,
                  imap=FakeIMAP(mails), smtp=smtp)
        bodies = [_read_result(m) for m in smtp.sent]
        self.assertEqual(bodies[0]["ok"], True)
        self.assertEqual(bodies[1]["type"], "task_offer")
        self.assertEqual(bodies[1]["task"]["task_id"], "t-one")
        self.assertTrue(bodies[2].get("empty"))
        self.assertEqual(bodies[3]["ok"], False)
        self.assertIn("duplicate", bodies[3]["reason"])
        with open(os.path.join(self.tmp, "board.json"), encoding="utf-8") as fh:
            tasks = json.load(fh)
        self.assertEqual(tasks["t-one"]["state"], "claimed")
        self.assertEqual(tasks["t-one"]["claimed_by"], "w1")

    def test_bad_signature_and_result_before_claim(self):
        raw = EmailMessage()
        raw["From"] = SENDER
        raw["To"] = SENDER
        raw["Subject"] = "[HOMING-PIGEON] task_submit t-x"
        raw.set_content("nope")
        issued = _now()
        result = _signed("[HOMING-PIGEON] task_result t-missing", {
            "v": 1, "type": "task_result", "issued_at": issued,
            "result": {"ok": True},
        })
        imap = FakeIMAP([raw.as_bytes(), result])
        smtp = FakeSMTP()
        poll_once(self.cfg, self.tmp, {}, self.seen_path, imap=imap, smtp=smtp)
        self.assertIn("1", imap.flagged)
        self.assertEqual(len(smtp.sent), 1)
        body = _read_result(smtp.sent[0])
        self.assertEqual(body["status"], "not_found")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "board.json")))


class PolicyArgsSkipLegTest(unittest.TestCase):
    """Queue A refill: check_policy_constraints'
    non-string arg skip (coverage run
    40189711740: verify.py line 612). An arg
    that is not a string is not the pattern's
    business -- it is skipped, not matched and
    not a finding; the string args around it
    are still judged.
    """

    def test_a_non_string_arg_is_skipped(self):
        from runner.wire import verify as V
        pol = {"args_pattern": "^ok$"}
        job = {"kind": "ping", "args": [123, "ok"]}
        self.assertEqual(
            V.check_policy_constraints(pol, "", {}, job), [])
        job2 = {"kind": "ping", "args": [123, "nope"]}
        findings = V.check_policy_constraints(
            pol, "", {}, job2)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][1],
                         "arg_pattern_mismatch")


if __name__ == "__main__":
    unittest.main(verbosity=2)
