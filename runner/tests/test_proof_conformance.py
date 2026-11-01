#!/usr/bin/env python3
"""Stage 5, first slice: the real gate along three findings.

The models in docs/proofs/ say what must not happen. These tests
drive handle_mail and check the outcome, not a stand-in:

- a cleartext job, with cleartext refused, does not execute and
  does not consume the job id
- a repaired interpreter the key's policy forbids does not execute
- a job whose result is already on record is answered from the
  record and does not execute

The rest of the clause-by-clause family is still stage 5's, and
stage5.md says so.
"""
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner import runner  # noqa: E402
from runner.runner import handle_mail, sign_payload  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402

SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _job(job_id, **extra):
    job = {
        "v": 1, "type": "job", "job_id": job_id,
        "issued_at": _now(), "kind": "ping",
    }
    job.update(extra)
    return job


def _wire(job, encrypt):
    signed = sign_payload(job, SECRET)
    body = signed
    if encrypt:
        body = jobcrypto.encrypt_body(
            signed, SECRET, job_id=job["job_id"], key_id="",
            sign=sign_payload)
    msg = EmailMessage()
    msg["Subject"] = "[HOMING-PIGEON] job " + job["job_id"]
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _IMAP:
    def store(self, *args):
        return "OK", None


class _SMTP:
    transport = None


class GateConformanceTest(unittest.TestCase):
    def _drive(self, job, encrypt=True, cfg_extra=None, policies=None,
               patch=None):
        executed = []

        def execute(*_args, **_kwargs):
            executed.append(job["job_id"])
            raise AssertionError("the gate executed " + job["job_id"])

        notes = []

        def grab(msg, level="INFO"):
            notes.append(msg)

        seen = {}
        with tempfile.TemporaryDirectory() as directory:
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
                "base_dir": directory,
                "oracle_opinion_mode": "off",
            }
            if cfg_extra:
                cfg.update(cfg_extra)
            secrets = runner.build_secrets(cfg)
            opts = Namespace(dry_run=False, no_send=True)
            started = []
            for item in patch or []:
                item.start()
                started.append(item)
            try:
                with mock.patch.object(runner, "execute_job", execute):
                    with mock.patch.object(runner, "log", grab):
                        handle_mail(
                            cfg, _IMAP(), _SMTP(), 3,
                            _wire(job, encrypt), directory, seen,
                            secrets, opts, policies)
            finally:
                for item in reversed(started):
                    item.stop()
        return seen, notes, executed

    def _said(self, notes, fragment):
        self.assertTrue(
            any(fragment in msg for msg in notes), notes)

    def test_cleartext_does_not_execute_or_consume_the_id(self):
        job = _job("clear-1")
        seen, notes, executed = self._drive(job, encrypt=False)
        self.assertEqual(executed, [])
        self.assertEqual(seen, {})
        self._said(notes, "cleartext job refused")

    def test_an_unsigned_body_does_not_execute(self):
        job = _job("unsigned-1")
        raw_job = dict(job)
        # A body with no signature is not a signed payload.
        from email.message import EmailMessage as M
        import json
        msg = M()
        msg["Subject"] = "[HOMING-PIGEON] job unsigned-1"
        msg["From"] = "si@example.com"
        msg.set_content(json.dumps(raw_job))
        executed = []

        def execute(*_a, **_k):
            executed.append("unsigned-1")

        seen = {}
        with tempfile.TemporaryDirectory() as directory:
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
                "base_dir": directory,
                "oracle_opinion_mode": "off",
            }
            with mock.patch.object(runner, "execute_job", execute):
                handle_mail(
                    cfg, _IMAP(), _SMTP(), 3, msg.as_bytes(),
                    directory, seen, runner.build_secrets(cfg),
                    Namespace(dry_run=False, no_send=True), None)
        self.assertEqual(executed, [])
        self.assertEqual(seen, {})

    def test_a_record_is_resent_and_not_executed(self):
        cached = {
            "subject": "[HOMING-PIGEON] result record-1",
            "body": "the stored result",
            "to": None,
            "completed_at": "2026-10-31T00:00:00Z",
        }
        job = _job("record-1")
        seen, notes, executed = self._drive(
            job,
            patch=[mock.patch.object(
                runner, "load_sent_result", return_value=cached)])
        self.assertEqual(executed, [])
        self._said(notes, "result resent from the record")
        self.assertTrue(seen, "the resent id was not recorded")

    def test_a_repaired_interpreter_the_key_forbids_does_not_execute(self):
        missing = ["/no/such/hp-proof-interp"]
        job = _job(
            "repair-1", kind="exec", script="echo ok",
            interpreter=missing)
        seen, notes, executed = self._drive(
            job,
            cfg_extra={"oracle_opinion_mode": "repair"},
            policies={"": {"allowed_interpreters": [missing]}})
        self.assertEqual(executed, [])
        self._said(notes, "repaired job refused")


if __name__ == "__main__":
    unittest.main()
