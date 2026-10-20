#!/usr/bin/env python3
"""Tests for the --diagnose harness. All network/mail/model access
is mocked: CI has no live services. The sections that are pure
(banner, config, context) run for real against a temp state dir.
"""
import glob
import json
import os
import sys
import tempfile
import unittest
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import harness as H  # noqa: E402
from runner import jobcrypto  # noqa: E402
from runner import runner as R  # noqa: E402


SECRET = ("9f2c41aa07b3e5d80192f4a6b8c3d5e7"
          "f0a1b2c3d4e5f60718293a4b5c6d7e8f")
PASSWORD = "app-password-that-must-not-print"


def _cfg(**over):
    cfg = {
        "shared_secret": SECRET,
        "mailbox_user": "runner@example.com",
        "mailbox_password": PASSWORD,
        "imap_host": "imap.example.com",
        "smtp_host": "smtp.example.com",
        "inference": {"endpoint": "http://127.0.0.1:11434/v1",
                      "model": "llama3.2:3b",
                      "watch_system": False},
    }
    cfg.update(over)
    return cfg


def _ctx(cfg, base_dir, timeout=5):
    return {"cfg": cfg, "base_dir": base_dir, "cfg_path": None,
            "roundtrip_timeout": timeout, "context": None,
            "retained_count": 0}


class EntropyTest(unittest.TestCase):
    def test_known_strings(self):
        self.assertEqual(H.estimate_entropy_bits(""), 0.0)
        self.assertEqual(H.estimate_entropy_bits("aaaaaaaa"), 0.0)
        self.assertEqual(H.estimate_entropy_bits(None), 0.0)
        # 64 chars over a 2-symbol alphabet: 64 x 1 bit.
        self.assertAlmostEqual(H.estimate_entropy_bits("ab" * 32), 64.0)
        # 64 hex chars using all 16 symbols: 64 x 4 bits.
        hexed = "0123456789abcdef" * 4
        self.assertAlmostEqual(H.estimate_entropy_bits(hexed), 256.0)


class ReportAndIsolationTest(unittest.TestCase):
    def test_fault_isolation_exit_code_and_report(self):
        ran = []

        def ok(ctx, sec):
            ran.append("ok")
            sec.verdict(H.PASS, "fine")

        def boom(ctx, sec):
            ran.append("boom")
            raise RuntimeError("kaboom")

        def info(ctx, sec):
            ran.append("info")
            sec.note("just so you know")

        lines = []
        with tempfile.TemporaryDirectory() as d:
            fails = H.run_diagnose(
                _cfg(), out=lines.append, base_dir=d,
                sections=[("first", ok), ("bad", boom),
                          ("third", info)])
            reports = glob.glob(os.path.join(d, "harness-report-*.txt"))
            self.assertEqual(len(reports), 1)
            with open(reports[0], encoding="utf-8") as fh:
                report = fh.read()
        self.assertEqual(ran, ["ok", "boom", "info"])
        self.assertEqual(fails, 1)
        self.assertTrue(any(ln.startswith("[PASS] first") for ln in lines))
        self.assertTrue(any(ln.startswith("[FAIL] bad") for ln in lines))
        self.assertTrue(any(ln.startswith("[INFO] third") for ln in lines))
        self.assertIn("kaboom", report)
        self.assertIn("== bad — FAIL", report)
        self.assertIn("1 failed, 1 passed, 1 info", report)

    def test_exit_code_counts_all_failures(self):
        def fail(ctx, sec):
            sec.verdict(H.FAIL, "no")

        lines = []
        with tempfile.TemporaryDirectory() as d:
            fails = H.run_diagnose(
                {}, out=lines.append, base_dir=d,
                sections=[("a", fail), ("b", fail)])
        self.assertEqual(fails, 2)


class SecretHygieneTest(unittest.TestCase):
    def test_secret_and_password_never_printed(self):
        lines = []
        with tempfile.TemporaryDirectory() as d:
            fails = H.run_diagnose(
                _cfg(), out=lines.append, base_dir=d,
                sections=[("banner", H._sec_banner),
                          ("config", H._sec_config)])
            reports = glob.glob(os.path.join(d, "harness-report-*.txt"))
            with open(reports[0], encoding="utf-8") as fh:
                report = fh.read()
        blob = "\n".join(lines) + report
        self.assertNotIn(SECRET, blob)
        self.assertNotIn(PASSWORD, blob)
        self.assertEqual(fails, 0)
        self.assertIn("length 64", blob)
        self.assertIn("bits estimated entropy", blob)


class ConfigSectionTest(unittest.TestCase):
    def test_missing_secret_fails(self):
        lines = []
        with tempfile.TemporaryDirectory() as d:
            sec = H._run_section("config", H._sec_config,
                                 _ctx({}, d), lines.append)
        self.assertEqual(sec.status, H.FAIL)
        self.assertIn("MISSING", "\n".join(sec.evidence))

    def test_good_config_passes(self):
        lines = []
        with tempfile.TemporaryDirectory() as d:
            sec = H._run_section("config", H._sec_config,
                                 _ctx(_cfg(), d), lines.append)
        self.assertEqual(sec.status, H.PASS)


class MailboxSectionTest(unittest.TestCase):
    def test_connect_failure_is_a_section_fail(self):
        lines = []
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    R, "connect_imap",
                    side_effect=RuntimeError("login denied")):
                sec = H._run_section("mailbox", H._sec_mailbox,
                                     _ctx(_cfg(), d), lines.append)
        self.assertEqual(sec.status, H.FAIL)
        self.assertIn("login denied", sec.summary)


class _FakeResp:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


class ModelSectionTest(unittest.TestCase):
    def _opener(self, url_map):
        def fake_open(req, timeout=60):
            for suffix, payload in url_map.items():
                if req.full_url.endswith(suffix):
                    return _FakeResp(payload)
            raise RuntimeError(f"unexpected url {req.full_url}")
        return fake_open

    def test_model_listed_and_answers(self):
        url_map = {
            "/models": {"data": [{"id": "llama3.2:3b"},
                                 {"id": "llama3.2:1b"}]},
            "/chat/completions": {
                "choices": [{"message": {"content": "pong"}}]},
        }
        lines = []
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(R, "_default_inference_open",
                                   self._opener(url_map)):
                sec = H._run_section("model", H._sec_model,
                                     _ctx(_cfg(), d), lines.append)
        self.assertEqual(sec.status, H.PASS)
        self.assertIn("llama3.2:3b answered", sec.summary)

    def test_model_not_served_fails(self):
        url_map = {"/models": {"data": [{"id": "something-else:7b"}]}}
        lines = []
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(R, "_default_inference_open",
                                   self._opener(url_map)):
                sec = H._run_section("model", H._sec_model,
                                     _ctx(_cfg(), d), lines.append)
        self.assertEqual(sec.status, H.FAIL)
        self.assertIn("NOT in the model list", "\n".join(sec.evidence))

    def test_model_names_shapes(self):
        self.assertEqual(
            H._model_names({"data": [{"id": "a"}, {"id": "b"}]}),
            ["a", "b"])
        self.assertEqual(
            H._model_names({"models": [{"name": "x"}]}), ["x"])
        self.assertEqual(H._model_names({"nope": 1}), [])


def _captured_job(captured):
    """Recover the job dict from the captured wire body.

    The harness sends its round-trip job as an hp_enc envelope
    (the HMAC-only form is refused by default), so the fake
    receiver unwraps it the way the runner does: verify the
    envelope, decrypt, verify the inner signed body. Returns
    (job_dict, was_envelope).
    """
    payload = R.verify_body(captured["body"], SECRET)
    if not jobcrypto.is_envelope(payload):
        return payload, False
    jid = str(captured["subject"]).rsplit(" ", 1)[-1]
    inner = jobcrypto.decrypt_body(
        payload, SECRET, jid, payload.get("key_id") or "")
    return R.verify_body(inner, SECRET), True


class _FakeIMAP:
    """Serves the job mail and, once the job was 'sent', its result."""

    def __init__(self, captured, serve_result=True):
        self.captured = captured
        self.serve_result = serve_result

    def search(self, charset, *criteria):
        if not self.serve_result:
            return "OK", [b""]
        return "OK", [b"1 2"]

    def fetch(self, num, query):
        job, was_envelope = _captured_job(self.captured)
        if num == b"1":
            raw = self.captured["raw_job"]
        else:
            nonce = job["script"].split()[-1]
            result = {"v": R.PROTOCOL_VERSION, "type": "result",
                      "job_id": job["job_id"], "kind": "exec",
                      "exit_code": 0, "timed_out": False,
                      "stdout": nonce + "\n", "stderr": "",
                      "runner": "testbox"}
            msg = EmailMessage()
            msg["From"] = "runner@example.com"
            msg["To"] = "runner@example.com"
            msg["Subject"] = f"[HOMING-PIGEON] result {job['job_id']}"
            wire = R.sign_payload(result, SECRET)
            if was_envelope:
                # The result mirrors the job's encrypted form.
                wire = jobcrypto.encrypt_body(
                    wire, SECRET, job_id=job["job_id"], key_id="",
                    sign=R.sign_payload)
            msg.set_content(wire)
            raw = msg.as_bytes()
        return "OK", [(b"1 (BODY[] {%d}" % len(raw), raw), b")"]

    def logout(self):
        return "BYE", []


class RoundTripSectionTest(unittest.TestCase):
    def _run(self, d, serve_result=True, timeout=5):
        captured = {}

        def fake_send(smtp, cfg, subject, body, to=None):
            captured["subject"] = subject
            captured["body"] = body
            msg = EmailMessage()
            msg["From"] = "runner@example.com"
            msg["To"] = "runner@example.com"
            msg["Subject"] = subject
            msg.set_content(body)
            captured["raw_job"] = msg.as_bytes()

        lines = []
        with mock.patch.object(R, "connect_smtp", lambda cfg: object()), \
                mock.patch.object(R, "send_mail", fake_send), \
                mock.patch.object(
                    R, "connect_imap",
                    lambda cfg: _FakeIMAP(captured, serve_result)), \
                mock.patch.object(H, "_ROUNDTRIP_POLL_SEC", 0.01):
            sec = H._run_section("round-trip", H._sec_roundtrip,
                                 _ctx(_cfg(), d, timeout=timeout),
                                 lines.append)
        return sec, captured

    def test_round_trip_passes_and_uses_protocol_version(self):
        with tempfile.TemporaryDirectory() as d:
            sec, captured = self._run(d)
        self.assertEqual(sec.status, H.PASS)
        job, was_envelope = _captured_job(captured)
        self.assertTrue(was_envelope)
        self.assertEqual(job["v"], R.PROTOCOL_VERSION)
        self.assertEqual(job["kind"], "exec")
        self.assertIn("[HOMING-PIGEON] job ", captured["subject"])

    def test_no_result_is_a_bounded_fail(self):
        with tempfile.TemporaryDirectory() as d:
            sec, _captured = self._run(d, serve_result=False, timeout=1)
        self.assertEqual(sec.status, H.FAIL)
        self.assertIn("may not be polling", "\n".join(sec.evidence))


class ContextSectionTest(unittest.TestCase):
    def test_index_lines_reported_verbatim(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            data = {"kind": "exec", "exit_code": 0,
                    "saved_at": 1760000000, "script": "echo a",
                    "stdout": "a"}
            with open(os.path.join(d, "retained", "job-aaa.json"),
                      "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            lines = []
            sec = H._run_section("oracle-context", H._sec_context,
                                 _ctx(_cfg(), d), lines.append)
        self.assertEqual(sec.status, H.PASS)
        self.assertIn("job job-aaa (exec, exit code 0",
                      "\n".join(sec.evidence))

    def test_no_retained_jobs_is_info(self):
        with tempfile.TemporaryDirectory() as d:
            lines = []
            sec = H._run_section("oracle-context", H._sec_context,
                                 _ctx(_cfg(), d), lines.append)
        self.assertEqual(sec.status, H.INFO)


class ProbesSectionTest(unittest.TestCase):
    def test_all_answered_passes(self):
        lines = []
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    H.LT, "answer_as_oracle",
                    lambda cfg, q: {"answer": "an answer"}):
                sec = H._run_section("oracle-probes", H._sec_probes,
                                     _ctx(_cfg(), d), lines.append)
        self.assertEqual(sec.status, H.PASS)
        self.assertIn("Q5:", "\n".join(sec.evidence))
        self.assertEqual(len(H.PROBES), 5)

    def test_rejected_probe_fails(self):
        lines = []
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    H.LT, "answer_as_oracle",
                    lambda cfg, q: {"rejected": "inference_unconfigured"}):
                sec = H._run_section("oracle-probes", H._sec_probes,
                                     _ctx(_cfg(), d), lines.append)
        self.assertEqual(sec.status, H.FAIL)


class SensesSectionTest(unittest.TestCase):
    def test_senses_reported_as_context_reports_them(self):
        lines = []
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    R, "_canary_watch",
                    return_value="canaries intact: 3 planted"), \
                    mock.patch.object(R, "_eventlog_tail",
                                      return_value=""), \
                    mock.patch.object(R, "_registry_watch",
                                      return_value=""), \
                    mock.patch.object(R, "_host_log_tail",
                                      return_value=""):
                sec = H._run_section("senses", H._sec_senses,
                                     _ctx(_cfg(), d), lines.append)
        self.assertEqual(sec.status, H.PASS)
        self.assertIn("canaries intact", "\n".join(sec.evidence))

    def test_unreadable_source_fails_and_says_unreadable(self):
        lines = []
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    R, "_canary_watch", return_value="ok"), \
                    mock.patch.object(R, "_eventlog_tail",
                                      return_value=None), \
                    mock.patch.object(R, "_registry_watch",
                                      return_value=None), \
                    mock.patch.object(R, "_host_log_tail",
                                      return_value=None):
                sec = H._run_section("senses", H._sec_senses,
                                     _ctx(_cfg(), d), lines.append)
        self.assertEqual(sec.status, H.FAIL)
        self.assertIn("UNREADABLE", "\n".join(sec.evidence))


class WiringTest(unittest.TestCase):
    def test_diagnose_flag_is_wired(self):
        with open(os.path.join(REPO, "runner", "runner.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('"--diagnose"', src)
        self.assertIn("args.diagnose", src)
        self.assertIn("_harness.main", src)


if __name__ == "__main__":
    unittest.main()
