"""The result's size on the wire, and what a permanent refusal gets.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

A result body is fitted to max_result_bytes before it is signed:
stdout and stderr are cut to head and tail with a marker in the
middle, the truncated flags set and a result_truncated member added,
in at most three passes, so the signature always covers what is
sent. A 5xx refusal of the body is permanent: a signed stub without
the streams is sent once and the original kept under
work/<job_id>/result.json; a 4xx, a socket or a TLS error is
transient and the original is resent. (Review item 4.)
"""
import json
import os
import shutil
import smtplib
import sys
import tempfile
import unittest
import uuid
from unittest import mock

try:
    from hypothesis import given, settings, strategies as st
except ImportError:  # pragma: no cover - hypothesis is a test-only dep
    given = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runner", "cloud"))

from runner import runner as R  # noqa: E402
from runner.guard import security as S  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402
from runner.tests.test_result_stash import Clock, StashHarness  # noqa: E402

SECRET = TR.SECRET


def _result(out, err, **extra):
    r = {"v": 1, "type": "result", "job_id": "j1", "kind": "exec",
         "completed_at": "2026-10-25T00:00:00Z", "exit_code": 0,
         "timed_out": False, "stdout": out, "stderr": err,
         "stdout_truncated": False, "stderr_truncated": False,
         "duration_sec": 0.5, "runner": "box", "review": None}
    r.update(extra)
    return r


class FitTest(unittest.TestCase):
    def _fit(self, out, err, cap, encrypt=False):
        res, body = R._fit_result_body(_result(out, err), SECRET, encrypt,
                                       "j1", "", cap)
        self.assertLessEqual(len(body.encode("utf-8")), cap)
        parsed = TR.verify_body(body, SECRET)
        if encrypt:
            from runner.wire import jobcrypto
            parsed = TR.verify_body(jobcrypto.decrypt_body(
                parsed, SECRET, "j1", ""), SECRET)
        self.assertEqual(parsed["stdout"], res["stdout"])
        return res, parsed

    def test_a_small_result_is_untouched(self):
        res, parsed = self._fit("hello", "", 100000)
        self.assertNotIn("result_truncated", res)
        self.assertEqual(parsed["stdout"], "hello")
        self.assertFalse(parsed["stdout_truncated"])

    def test_truncation_keeps_head_and_tail_and_marks_it(self):
        out = "H" * 50000 + "M" * 200000 + "T" * 50000
        res, parsed = self._fit(out, "e" * 1000, 60000)
        self.assertTrue(parsed["stdout_truncated"])
        self.assertTrue(parsed["stdout"].startswith("HHHH"))
        self.assertTrue(parsed["stdout"].endswith("TTTT"))
        self.assertIn("bytes dropped to fit max_result_bytes", parsed["stdout"])
        self.assertEqual(parsed["result_truncated"]["reason"],
                         "max_result_bytes")
        self.assertGreater(parsed["result_truncated"]["dropped"], 200000)
        self.assertEqual(parsed["exit_code"], 0)

    def test_the_third_pass_keeps_two_kib_each_side(self):
        # The streams alone leave no room under the cap: the last pass
        # drops both to their first and last 2 KiB.
        out = "A" * 20000 + "Z" * 20000
        res, parsed = self._fit(out, "x" * 40000, 9000)
        self.assertTrue(parsed["stdout"].startswith("A" * 100))
        self.assertTrue(parsed["stdout"].endswith("Z" * 100))
        self.assertLessEqual(len(parsed["stdout"]), 2 * R._TAIL_KEEP + 80)
        self.assertTrue(parsed["stderr_truncated"])

    def test_the_encrypted_form_is_fitted_too(self):
        res, parsed = self._fit("B" * 300000, "", 120000, encrypt=True)
        self.assertTrue(parsed["stdout_truncated"])

    def test_zero_is_unlimited(self):
        res, body = R._fit_result_body(_result("Q" * 100000, ""), SECRET,
                                       False, "j1", "", 0)
        self.assertNotIn("result_truncated", res)
        self.assertGreater(len(body), 100000)

    def test_the_cap_reads_as_documented(self):
        self.assertEqual(R._max_result_bytes({}), 5242880)
        self.assertEqual(R._max_result_bytes({"max_result_bytes": 10}), 10)
        self.assertEqual(R._max_result_bytes({"max_result_bytes": 0}), 0)
        self.assertEqual(R._max_result_bytes({"max_result_bytes": "big"}),
                         5242880)
        self.assertEqual(R._max_result_bytes({"max_result_bytes": True}),
                         5242880)
        self.assertIsNone(R._validate_size_caps({"max_result_bytes": 7}))
        self.assertIn("max_result_bytes",
                      R._validate_size_caps({"max_result_bytes": -1}))
        self.assertIn("max_result_bytes",
                      R._validate_size_caps({"max_result_bytes": "x"}))

    def test_shrink_stream_edges(self):
        self.assertEqual(R._shrink_stream("abc", 10), ("abc", 0))
        text, dropped = R._shrink_stream("abcdefghij", 4)
        self.assertEqual(dropped, 6)
        self.assertTrue(text.startswith("ab") and text.endswith("ij"))
        self.assertEqual(R._shrink_stream("abc", -5)[1], 3)


class ClassifyTest(unittest.TestCase):
    def test_permanent_and_transient(self):
        self.assertTrue(R._is_permanent_smtp(
            smtplib.SMTPDataError(552, b"message too large")))
        self.assertTrue(R._is_permanent_smtp(
            smtplib.SMTPDataError(554, b"rejected")))
        self.assertTrue(R._is_permanent_smtp(
            smtplib.SMTPSenderRefused(550, b"no", "a@example.com")))
        self.assertTrue(R._is_permanent_smtp(smtplib.SMTPRecipientsRefused(
            {"a@example.com": (550, b"unknown user")})))
        self.assertTrue(R._is_permanent_smtp(
            ch.PermanentDeliveryError("broker says no")))
        self.assertFalse(R._is_permanent_smtp(
            smtplib.SMTPDataError(421, b"try later")))
        self.assertFalse(R._is_permanent_smtp(smtplib.SMTPRecipientsRefused(
            {"a@example.com": (550, b"no"), "b@example.com": (450, b"later")})))
        self.assertFalse(R._is_permanent_smtp(smtplib.SMTPRecipientsRefused({})))
        self.assertFalse(R._is_permanent_smtp(OSError("reset")))
        self.assertFalse(R._is_permanent_smtp(TimeoutError()))
        self.assertFalse(R._is_permanent_smtp(smtplib.SMTPServerDisconnected()))


class RefusedSMTP(TR.FakeSMTP):
    """Refuses bodies over `limit` bytes with the given code."""

    def __init__(self, limit, code=552, text=b"5.3.4 message too large"):
        super().__init__()
        self.limit = limit
        self.code = code
        self.text = text
        self.calls = 0

    def send_message(self, msg):
        self.calls += 1
        if len(msg.get_content()) > self.limit:
            raise smtplib.SMTPDataError(self.code, self.text)
        super().send_message(msg)


class StubTest(StashHarness):
    def _big_job(self, jid):
        return TR.job_payload(jid, kind="exec", interpreter=["sh"],
                              script="i=0; while [ $i -lt 400 ]; do "
                                     "echo line-$i-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx;"
                                     " i=$((i+1)); done")

    def test_552_is_permanent_and_sends_stub_once(self):
        jid = str(uuid.uuid4())
        smtp = RefusedSMTP(limit=3000)
        seen = {}
        self._cycle([TR.job_email(self._big_job(jid))], smtp, seen)
        self.assertEqual(smtp.calls, 2)          # the body, then the stub
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(self._outbox(), [])     # delivered as the stub
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual(result["job_id"], jid)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "")
        self.assertTrue(result["stdout_truncated"])
        self.assertIn("552", result["delivery_note"])
        self.assertIn("work/%s/" % jid, result["delivery_note"])
        kept = os.path.join(self.tmp, "work", jid, "result.json")
        with open(kept, encoding="utf-8") as fh:
            original = json.load(fh)
        self.assertIn("line-399", original["stdout"])
        self.assertEqual(original["job_id"], jid)
        rows = [a for a in self._audit() if a.get("feature") == "delivery"]
        self.assertEqual(rows, [])               # a stub is not a failure
        self.assertTrue(any(jid in k for k in seen))

    def test_a_refused_stub_is_given_up_with_audit(self):
        jid = str(uuid.uuid4())
        smtp = RefusedSMTP(limit=0)              # refuses everything
        seen = {}
        self._cycle([TR.job_email(self._big_job(jid))], smtp, seen)
        self.assertEqual(smtp.calls, 2)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(self._outbox(), [])
        self.assertEqual(len(self._failed()), 1)
        rows = [a for a in self._audit() if a.get("feature") == "delivery"]
        self.assertEqual(rows[-1]["decision"], "failed")
        self.assertIn("stub", rows[-1]["reason"])
        self.clock.advance(1000)
        self._cycle([], smtp, seen)
        self.assertEqual(smtp.calls, 2)          # nothing retries a failed/ record

    def test_421_is_transient_and_resends_original(self):
        jid = str(uuid.uuid4())
        smtp = RefusedSMTP(limit=3000, code=421, text=b"try again later")
        seen = {}
        self._cycle([TR.job_email(self._big_job(jid))], smtp, seen)
        self.assertEqual(smtp.calls, 1)
        rec = self._record()
        self.assertFalse(rec.get("stubbed"))
        self.assertIn("421", rec["last_error"])
        smtp.limit = 10 ** 9                      # the server recovered
        self.clock.advance(120)
        self._cycle([], smtp, seen)
        self.assertEqual(len(smtp.sent), 1)
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertIn("line-399", result["stdout"])
        self.assertNotIn("delivery_note", result)
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp, "work", jid, "result.json")))

    def test_the_cap_keeps_a_big_result_under_the_wire_limit(self):
        # 400 lines are about 15 KB of stdout; the cap halves it.
        self.cfg["max_result_bytes"] = 12000
        jid = str(uuid.uuid4())
        smtp = RefusedSMTP(limit=12100)   # the message adds a newline
        seen = {}
        self._cycle([TR.job_email(self._big_job(jid))], smtp, seen)
        self.assertEqual(smtp.calls, 1)           # fitted first: no refusal
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertTrue(result["stdout_truncated"])
        self.assertEqual(result["result_truncated"]["reason"],
                         "max_result_bytes")
        self.assertTrue(result["stdout"].startswith("line-0-"))
        self.assertIn("line-399", result["stdout"])

    def test_the_stub_keeps_the_verdict_members_only(self):
        stub = R._stub_result("j9", {"v": 1, "type": "result", "exit_code": 7,
                                     "stdout": "big", "judgment": {"v": "x"},
                                     "answers": [1]}, "552 too large")
        self.assertEqual(stub["exit_code"], 7)
        self.assertEqual(stub["judgment"], {"v": "x"})
        self.assertNotIn("answers", stub)
        self.assertEqual(stub["stdout"], "")
        self.assertTrue(stub["stderr_truncated"])
        self.assertIn("552 too large", stub["delivery_note"])
        self.assertEqual(stub["job_id"], "j9")

    def test_a_channel_refusal_gets_its_stub_back_out_the_channel(self):
        # The email extension set a refused result aside under its
        # channel's outbox/failed/; the next pass answers it with the
        # stub, keeps the original, and moves the refusal to done/.
        jid = str(uuid.uuid4())
        job = TR.job_payload(jid)
        from runner.wire import jobcrypto
        from send_job import sign_payload
        body = jobcrypto.encrypt_body(sign_payload(job, TR.SECRET), TR.SECRET,
                                      job_id=jid, key_id="",
                                      sign=sign_payload)
        seen = {}
        out = R.process_transport_message(
            self.cfg, self.tmp, seen, R.build_secrets(self.cfg), {},
            "[HOMING-PIGEON] job " + jid, body, transport="email")
        subject, rbody, target = out[0]
        paths = R._transports.ensure_channel_dirs(self.tmp, "email")
        fname = "mail-7.result.txt"
        with open(os.path.join(paths["outbox"], fname), "w",
                  encoding="utf-8") as fh:
            fh.write(R._transports.format_envelope(subject, rbody))
        channel = R._transports.channel_root(self.tmp, "email")
        ch.refuse_result(channel, fname,
                         smtplib.SMTPDataError(552, b"too large"))
        self.assertEqual(sorted(os.listdir(os.path.join(paths["outbox"],
                                                        "failed"))),
                         ["mail-7.refused.txt", "mail-7.result.txt"])
        self.assertEqual(ch.pending_results(channel), [])
        handled = R._sweep_channel_refusals(self.tmp, self.cfg, ["email"])
        self.assertEqual(handled, 1)
        pending = ch.pending_results(channel)
        self.assertEqual([p[0] for p in pending], ["mail-7.result.txt"])
        stub = TR.verify_body(pending[0][2], TR.SECRET)
        stub = TR.verify_body(jobcrypto.decrypt_body(stub, TR.SECRET, jid, ""),
                              TR.SECRET)
        self.assertEqual(stub["stdout"], "")
        self.assertIn("552", stub["delivery_note"])
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "work", jid,
                                                    "result.json")))
        self.assertEqual(os.listdir(os.path.join(paths["outbox"], "failed")),
                         [])
        self.assertIn("mail-7.refused.txt", os.listdir(paths["outbox_done"]))
        rows = [a for a in self._audit() if a.get("feature") == "delivery"]
        self.assertEqual(rows[-1]["decision"], "stubbed")
        # Refused again: given up, the sent record moves to failed/.
        with open(os.path.join(paths["outbox"], fname), "w",
                  encoding="utf-8") as fh:
            fh.write(R._transports.format_envelope(subject, pending[0][2]))
        ch.refuse_result(channel, fname, "552 again")
        self.assertEqual(R._sweep_channel_refusals(self.tmp, self.cfg,
                                                   ["email"]), 1)
        self.assertEqual(ch.pending_results(channel), [])
        self.assertEqual(len(self._failed()), 1)
        rows = [a for a in self._audit() if a.get("feature") == "delivery"]
        self.assertEqual(rows[-1]["decision"], "failed")


if given is not None:
    class BodyNeverExceedsCapProperty(unittest.TestCase):
        @settings(max_examples=30, deadline=None)
        @given(out=st.integers(min_value=0, max_value=3 * 1024 * 1024),
               err=st.integers(min_value=0, max_value=3 * 1024 * 1024),
               cap=st.integers(min_value=20000, max_value=2 * 1024 * 1024),
               encrypt=st.booleans())
        def test_body_never_exceeds_cap(self, out, err, cap, encrypt):
            res, body = R._fit_result_body(
                _result("o" * out, "e" * err), SECRET, encrypt, "j1", "", cap)
            self.assertLessEqual(len(body.encode("utf-8")), cap)
            parsed = TR.verify_body(body, SECRET)    # the signature verifies
            if encrypt:
                from runner.wire import jobcrypto
                parsed = TR.verify_body(jobcrypto.decrypt_body(
                    parsed, SECRET, "j1", ""), SECRET)
            self.assertEqual(parsed["stdout"], res["stdout"])


if __name__ == "__main__":
    unittest.main()
