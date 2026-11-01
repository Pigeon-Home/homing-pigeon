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


def _wire(job, encrypt, subject=None):
    signed = sign_payload(job, SECRET)
    body = signed
    if encrypt:
        body = jobcrypto.encrypt_body(
            signed, SECRET, job_id=job["job_id"], key_id="",
            sign=sign_payload)
    msg = EmailMessage()
    msg["Subject"] = subject or ("[HOMING-PIGEON] job " + job["job_id"])
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
               patch=None, expect_execute=False, opts=None, seen=None,
               subject=None):
        executed = []

        def execute(*_args, **_kwargs):
            executed.append(job["job_id"])
            if not expect_execute:
                raise AssertionError("the gate executed " + job["job_id"])
            return {"exit_code": 0, "stdout": "", "stderr": "",
                    "timed_out": False, "duration_sec": 0.0}

        notes = []

        def grab(msg, level="INFO"):
            notes.append(msg)

        if seen is None:
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
            if opts is None:
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
                            _wire(job, encrypt, subject=subject),
                            directory, seen, secrets, opts, policies)
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

    def test_a_good_encrypted_ping_does_execute(self):
        seen, notes, executed = self._drive(
            _job("good-1"), expect_execute=True)
        self.assertEqual(executed, ["good-1"])
        self.assertTrue(seen)

    def test_an_over_cap_raw_message_does_not_execute(self):
        job = _job("raw-1")
        seen, notes, executed = self._drive(
            job, cfg_extra={"max_job_bytes": 20})
        self.assertEqual(executed, [])
        self.assertEqual(seen, {})
        self._said(notes, "max_job_bytes")

    def test_a_script_over_the_cap_does_not_execute(self):
        job = _job("scr-1", kind="exec", script="abcde")
        seen, notes, executed = self._drive(
            job, cfg_extra={"max_script_bytes": 4})
        self.assertEqual(executed, [])
        self.assertEqual(seen, {})
        self._said(notes, "max_script_bytes")

    def test_a_script_at_the_cap_does_execute(self):
        job = _job("scr-2", kind="exec", script="abcd")
        _seen, _notes, executed = self._drive(
            job, cfg_extra={"max_script_bytes": 4},
            expect_execute=True)
        self.assertEqual(executed, ["scr-2"])

    def test_the_wrong_audience_is_refused_when_enforced(self):
        job = _job("aud-1", aud="other-box")
        seen, notes, executed = self._drive(job, cfg_extra={
            "runner_id": "this-box",
            "security": {"modes": {"audience": "enforce"}},
        })
        self.assertEqual(executed, [])
        self.assertEqual(seen, {})
        self._said(notes, "audience")

    def test_the_wrong_audience_executes_when_the_check_is_off(self):
        job = _job("aud-2", aud="other-box")
        _seen, _notes, executed = self._drive(job, cfg_extra={
            "runner_id": "this-box",
            "security": {"modes": {"audience": "off"}},
        }, expect_execute=True)
        self.assertEqual(executed, ["aud-2"])

    def test_a_bad_version_a_bad_type_and_a_mismatched_id_do_not_execute(self):
        for job, fragment in (
            (_job("ver-1", v=2), "unsupported version"),
            (_job("ver-2", type="ping"), "unsupported version"),
        ):
            seen, notes, executed = self._drive(job)
            self.assertEqual(executed, [], job["job_id"])
            self.assertEqual(seen, {})
            self._said(notes, fragment)
        job = _job("ver-3")
        signed = sign_payload(job, SECRET)
        body = jobcrypto.encrypt_body(
            signed, SECRET, job_id="ver-other", key_id="",
            sign=sign_payload)
        msg = EmailMessage()
        msg["Subject"] = "[HOMING-PIGEON] job ver-other"
        msg["From"] = "si@example.com"
        msg.set_content(body)
        executed = []
        notes = []
        seen = {}
        with tempfile.TemporaryDirectory() as directory:
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
                "base_dir": directory,
                "oracle_opinion_mode": "off",
            }
            with mock.patch.object(
                    runner, "execute_job",
                    lambda *_a, **_k: executed.append("ver-3")):
                with mock.patch.object(
                        runner, "log",
                        lambda msg, level="INFO": notes.append(msg)):
                    handle_mail(
                        cfg, _IMAP(), _SMTP(), 3, msg.as_bytes(),
                        directory, seen, runner.build_secrets(cfg),
                        Namespace(dry_run=False, no_send=True), None)
        self.assertEqual(executed, [])
        self.assertEqual(seen, {})
        self._said(notes, "job_id mismatch")

    def test_a_stale_job_and_a_future_job_do_not_execute(self):
        from datetime import timedelta
        old = (datetime.now(timezone.utc) - timedelta(days=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        ahead = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        for stamp in (old, ahead, "2026-11-01T00:00:00"):
            job = _job("age-1", issued_at=stamp)
            seen, notes, executed = self._drive(job)
            self.assertEqual(executed, [])
            self.assertEqual(seen, {})
            self._said(notes, "issued_at")

    def test_a_key_policy_forbids_the_kind(self):
        job = _job("pol-1")
        seen, notes, executed = self._drive(
            job, policies={"": {"allowed_kinds": ["exec"]}})
        self.assertEqual(executed, [])
        self.assertEqual(seen, {})
        self._said(notes, "key policy")

    def test_a_dry_run_does_not_execute(self):
        seen, notes, executed = self._drive(
            _job("dry-1"),
            opts=Namespace(dry_run=True, no_send=True))
        self.assertEqual(executed, [])
        self.assertEqual(seen, {})
        self._said(notes, "dry-run")

    def test_an_id_already_seen_is_not_executed(self):
        job = _job("seen-1")
        seen, _notes, executed = self._drive(job, seen={"seen-1": True})
        self.assertEqual(executed, [])
        self.assertEqual(seen, {"seen-1": True})

    def test_a_sensor_alert_is_not_script_execution(self):
        job = _job("sens-1", kind="sensor_alert", sensor="box",
                   title="up", severity="info")
        seen, notes, executed = self._drive(job)
        self.assertEqual(executed, [])
        self._said(notes, "sensor alert")

    def test_the_panic_word_executes_nothing(self):
        from runner.guard import panic
        word = panic.generate_word()
        try:
            with tempfile.TemporaryDirectory() as directory:
                panic.arm(directory, word)
                job = _job("panic-1")
                subject = "[HOMING-PIGEON] panic " + word
                executed = []

                def execute(*_a, **_k):
                    executed.append("panic-1")

                notes = []
                cfg = {
                    "mailbox_user": "t@example.com",
                    "shared_secret": SECRET,
                    "base_dir": directory,
                    "oracle_opinion_mode": "off",
                }
                seen = {}
                with mock.patch.object(runner, "execute_job", execute):
                    with mock.patch.object(
                            runner, "log",
                            lambda msg, level="INFO": notes.append(msg)):
                        handle_mail(
                            cfg, _IMAP(), _SMTP(), 3,
                            _wire(job, True, subject=subject),
                            directory, seen, runner.build_secrets(cfg),
                            Namespace(dry_run=False, no_send=True), None)
            self.assertEqual(executed, [])
            self.assertEqual(seen, {})
            self.assertTrue(any("panic" in msg for msg in notes), notes)
        finally:
            panic._reset_for_tests()

    def test_nats_without_credentials_refuses_to_start(self):
        from runner.transport_extensions.nats.__main__ import (
            NatsPipe, TransportError)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TransportError) as raised:
                NatsPipe({"url": "nats://127.0.0.1:4222"}, directory)
        self.assertIn("refuses to start", str(raised.exception))
        self.assertIn("allow_unauthenticated", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
