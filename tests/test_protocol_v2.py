#!/usr/bin/env python3
"""Protocol version is 1. The sender still refuses a weak secret.

The 2026-10-17 bump to version 2 changed the integer only and was
reverted the same day. A job, query, or board message with any other
`v` is rejected. Replies carry 1. cloud/send_job.py emits 1 and
refuses to sign with a sub-128-bit or patterned secret. Verification
stays signature-only: the floor is a signing rule, not a verify rule.
"""

import contextlib
import io
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))
sys.path.insert(0, os.path.join(REPO, "cloud"))

from runner import runner as R  # noqa: E402
from runner import security as SEC  # noqa: E402
from runner.runner import poll_once, sign_payload, verify_body  # noqa: E402
from tests.security_parity import SECRET, FakeIMAP, FakeSMTP  # noqa: E402

import send_job  # noqa: E402


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, payload):
    msg = EmailMessage()
    msg["From"] = "si@example.com"
    msg["To"] = "si@example.com"
    msg["Subject"] = subject
    msg.set_content(sign_payload(payload, SECRET))
    return msg.as_bytes()


def _job(v, job_id="ver-job"):
    return {"v": v, "type": "job", "job_id": job_id,
            "issued_at": _now(), "kind": "ping"}


class VersionGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-v1-")
        self.cfg = {
            "mailbox_user": "si@example.com",
            "mailbox_password": "test-password",
            "shared_secret": SECRET,
            "base_dir": self.tmp,
            "workers": 1,
            "max_job_age_sec": 3600,
            "default_timeout_sec": 30,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def _poll(self, mails):
        smtp = FakeSMTP()
        poll_once(self.cfg, self.tmp, {}, self.seen_path,
                  imap=FakeIMAP(mails), smtp=smtp)
        return smtp

    def test_version_ok_matrix(self):
        self.assertTrue(R._version_ok(1))
        self.assertFalse(R._version_ok(2))
        self.assertFalse(R._version_ok(3))
        self.assertFalse(R._version_ok(None))
        self.assertFalse(R._version_ok("1"))

    def test_v1_job_accepted_reply_is_v1(self):
        smtp = self._poll([_mail("[HOMING-PIGEON] job ver-job", _job(1))])
        self.assertEqual(len(smtp.sent), 1)
        body = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(body["type"], "result")
        self.assertEqual(body["v"], 1)

    def test_v2_job_rejected(self):
        smtp = self._poll([_mail("[HOMING-PIGEON] job ver-job", _job(2))])
        self.assertEqual(len(smtp.sent), 0)

    def test_v1_query_passes_the_version_gate(self):
        q = {"v": 1, "type": "query", "query_id": "q-v1",
             "job_id": "no-such-job", "issued_at": _now(),
             "queries": [{"op": "grep", "pattern": "x"}]}
        smtp = self._poll([_mail("[HOMING-PIGEON] query q-v1", q)])
        self.assertEqual(len(smtp.sent), 1)
        body = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(body["type"], "qresult")
        self.assertEqual(body["rejected"], "unknown_job")
        self.assertEqual(body["v"], 1)

    def test_v2_query_rejected(self):
        q = {"v": 2, "type": "query", "query_id": "q-v2",
             "job_id": "no-such-job", "issued_at": _now(),
             "queries": [{"op": "grep", "pattern": "x"}]}
        smtp = self._poll([_mail("[HOMING-PIGEON] query q-v2", q)])
        self.assertEqual(len(smtp.sent), 1)
        body = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(body["type"], "qresult")
        self.assertEqual(body["rejected"], "unsupported")
        self.assertEqual(body["v"], 1)

    def test_v2_board_submit_rejected(self):
        issued = _now()
        mail = _mail("[HOMING-PIGEON] task_submit t-v2", {
            "v": 2, "type": "task_submit", "task_id": "t-v2",
            "issued_at": issued, "priority": 3, "capabilities": ["py"],
            "payload": {"kind": "ping"},
        })
        smtp = self._poll([mail])
        subjects = [m["Subject"] for m in smtp.sent]
        self.assertFalse(any("task_ack" in s for s in subjects))
        board_path = os.path.join(self.tmp, "board.json")
        if os.path.exists(board_path):
            with open(board_path, encoding="utf-8") as fh:
                self.assertNotIn("t-v2", fh.read())

    def test_v1_board_submit_ack_is_v1(self):
        issued = _now()
        mail = _mail("[HOMING-PIGEON] task_submit t-v1", {
            "v": 1, "type": "task_submit", "task_id": "t-v1",
            "issued_at": issued, "priority": 3, "capabilities": ["py"],
            "payload": {"kind": "ping"},
        })
        smtp = self._poll([mail])
        acks = [m for m in smtp.sent if "task_ack t-v1" in m["Subject"]]
        self.assertEqual(len(acks), 1)
        body = verify_body(acks[0].get_content(), SECRET)
        self.assertEqual(body["type"], "task_ack")
        self.assertEqual(body["v"], 1)


class SenderFloorTest(unittest.TestCase):
    def _cmd_new(self, secret):
        args = types.SimpleNamespace(
            kind="ping", job_id="sj-1", key_id=None, aud=None,
            reply_to=None, timeout=300, script_url=None,
            script_sha384=None, script_file=None, file=[], arg=[],
            env=[], interpreter=None, secret=secret, cleartext=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = send_job.cmd_new(args)
        return rc, buf.getvalue()

    def test_send_job_emits_v1(self):
        rc, out = self._cmd_new(SECRET)
        self.assertEqual(rc, 0)
        body = out.split("\n\n", 1)[1]
        payload = send_job.verify_body(body, SECRET)
        self.assertEqual(payload["v"], 1)
        self.assertEqual(payload["v"], send_job.PROTOCOL_VERSION)

    def test_sign_refuses_short_secret(self):
        with self.assertRaises(ValueError):
            send_job.sign_payload({"v": 2, "type": "job"}, "short")

    def test_sign_refuses_periodic_secret(self):
        # 80 chars over a 4-char alphabet estimates at ~160 bits but
        # is one short unit repeated: the pattern check refuses it.
        with self.assertRaises(ValueError):
            send_job.sign_payload({"v": 2, "type": "job"}, "abcd" * 20)

    def test_sign_refuses_placeholder_secret(self):
        with self.assertRaises(ValueError):
            send_job.sign_payload(
                {"v": 2, "type": "job"},
                "example-secret-that-is-long-and-varied-0123456789")

    def test_cmd_new_refuses_weak_secret(self):
        with self.assertRaises(ValueError):
            self._cmd_new("short")

    def test_verify_does_not_refuse_weak_secret(self):
        # The floor binds signing, not verification: a body signed
        # (by the runner's signer, which has no sender floor) with a
        # weak secret still verifies, so old traffic stays readable.
        body = sign_payload({"v": 2, "type": "result"}, "weak-weak")
        payload = send_job.verify_body(body, "weak-weak")
        self.assertEqual(payload["type"], "result")

    def test_entropy_estimator_parity_with_runner(self):
        samples = [
            "", "a", "aa", "ab", "abcd" * 20, SECRET,
            "correct horse battery staple",
            "x" * 64, "0123456789abcdef" * 4,
        ]
        for s in samples:
            self.assertEqual(send_job._estimate_secret_entropy(s),
                             SEC._estimate_secret_entropy(s), s[:16])
            self.assertEqual(send_job._secret_pattern_reason(s),
                             SEC._secret_pattern_reason(s), s[:16])


if __name__ == "__main__":
    unittest.main()
