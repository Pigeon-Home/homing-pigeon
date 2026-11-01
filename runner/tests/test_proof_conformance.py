#!/usr/bin/env python3
"""Stage 5: the real gate, clause by clause (P1).

The models in docs/proofs/ say what must not happen. These tests
drive handle_mail and check the outcome, not a stand-in:

- a cleartext job, with cleartext refused, does not execute and
  does not consume the job id
- a repaired interpreter the key's policy forbids does not execute
- a job whose result is already on record is answered from the
  record and does not execute

The classes after GateConformanceTest are the clause-by-clause
family for P1: one or more tests per clause of properties.md,
at and either side of each cap, in each audience mode, with
cleartext and encrypted arrivals, with replayed deliveries,
and with the check order pinned by which refusal a handling
records when two clauses both fail. The companion files carry
P2 to P6: test_proof_conformance_p2.py and onward.
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


# ------------------------------------------------------------------
# The clause-by-clause family for P1.
#
# One drive helper: it hands handle_mail a real wire message and
# records what executed (the job dicts execute_job was handed),
# what was logged, what the replay cache holds afterwards, and
# what result mail would have been sent.
# ------------------------------------------------------------------

import contextlib as _contextlib
import hashlib as _hashlib
import hmac as _hmac
import json as _json
from datetime import timedelta as _timedelta
from types import SimpleNamespace as _NS

UPSECRET = (
    "fedcba9876543210"
    "0123456789abcdef"
    "ffeeddccbbaa9988"
    "7766554433221100"
)
WRONGSECRET = (
    "0011223344556677"
    "8899aabbccddeeff"
    "0123456789abcdef"
    "fedcba9876543210"
)


def _issued(**delta):
    when = datetime.now(timezone.utc) + _timedelta(**delta)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _job2(job_id, **extra):
    job = {
        "v": 1, "type": "job", "job_id": job_id,
        "issued_at": _issued(), "kind": "ping",
    }
    job.update(extra)
    return job


def _wire2(job, secret=SECRET, key_id="", encrypt=True):
    payload = dict(job)
    if key_id:
        payload["key_id"] = key_id
    signed = sign_payload(payload, secret)
    body = signed
    if encrypt:
        body = jobcrypto.encrypt_body(
            signed, secret, job_id=job["job_id"], key_id=key_id,
            sign=sign_payload)
    msg = EmailMessage()
    msg["Subject"] = "[HOMING-PIGEON] job " + job["job_id"]
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _IMAP2:
    def __init__(self):
        self.store_calls = 0

    def store(self, *args):
        self.store_calls += 1
        return "OK", None


class _SMTP2:
    transport = None


_OK_RESULT = {
    "exit_code": 0, "stdout": "ok", "stderr": "",
    "timed_out": False, "duration_sec": 0.01,
    "stdout_truncated": False, "stderr_truncated": False,
}


def _run(job=None, raw=None, encrypt=True, secret=SECRET, key_id="",
         cfg_extra=None, policies=None, seen=None, opts=None,
         patches=(), exec_result=None, base_dir=None):
    executed = []
    sent = []

    def execute(_cfg, run_job, _base):
        executed.append(run_job)
        return dict(_OK_RESULT if exec_result is None else exec_result)

    def send(_smtp, _cfg, subject, body, to=None):
        sent.append((subject, body))

    notes = []

    def grab(msg, level="INFO"):
        notes.append(msg)

    if seen is None:
        seen = {}
    if raw is None:
        raw = _wire2(job, secret=secret, key_id=key_id, encrypt=encrypt)
    imap = _IMAP2()
    started = []
    for item in patches:
        item.start()
        started.append(item)
    owns_dir = None
    if base_dir is None:
        owns_dir = tempfile.TemporaryDirectory()
        base_dir = owns_dir.name
    try:
        with _contextlib.ExitStack() as stack:
            if owns_dir is not None:
                stack.enter_context(owns_dir)
            directory = base_dir
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
                "base_dir": directory,
                "oracle_opinion_mode": "off",
            }
            if cfg_extra:
                cfg.update(cfg_extra)
            secrets = runner.build_secrets(cfg)
            with mock.patch.object(runner, "execute_job", execute), \
                    mock.patch.object(runner, "send_mail", send), \
                    mock.patch.object(runner, "log", grab):
                handle_mail(
                    cfg, imap, _SMTP2(), 3, raw, directory, seen,
                    secrets,
                    opts if opts is not None else Namespace(
                        dry_run=False, no_send=False),
                    policies)
    finally:
        for item in reversed(started):
            item.stop()
    return _NS(executed=executed, notes=notes, seen=seen, sent=sent,
               store_calls=imap.store_calls)


class _GateCase(unittest.TestCase):
    def said(self, out, fragment):
        self.assertTrue(
            any(fragment in msg for msg in out.notes),
            f"{fragment!r} not in {out.notes!r}")

    def not_said(self, out, fragment):
        self.assertFalse(
            any(fragment in msg for msg in out.notes),
            f"{fragment!r} unexpectedly in {out.notes!r}")

    def refused(self, out, fragment):
        self.assertEqual(out.executed, [])
        self.said(out, fragment)


class P1RawSizeTest(_GateCase):
    """Clause 1: the raw message bound, before any signature work."""

    def test_over_cap_refused_at_exactly_one_over(self):
        job = _job2("raw-1")
        raw = _wire2(job)
        out = _run(raw=raw, cfg_extra={"max_job_bytes": len(raw) - 1})
        self.refused(out, "mail exceeds max_job_bytes")

    def test_at_cap_passes_the_size_step_and_executes(self):
        job = _job2("raw-2")
        raw = _wire2(job)
        out = _run(raw=raw, cfg_extra={"max_job_bytes": len(raw)})
        self.assertEqual(len(out.executed), 1)

    def test_cap_zero_is_unlimited(self):
        job = _job2("raw-3")
        out = _run(job=job, cfg_extra={"max_job_bytes": 0})
        self.assertEqual(len(out.executed), 1)

    def test_unmarked_oversize_mail_is_not_a_size_refusal(self):
        # The bound binds protocol messages; unmarked mail is
        # refused later for having no job id, not at this step.
        msg = EmailMessage()
        msg["Subject"] = "a newsletter"
        msg["From"] = "si@example.com"
        msg.set_content("x" * 5000)
        out = _run(raw=msg.as_bytes(), cfg_extra={"max_job_bytes": 10})
        self.assertEqual(out.executed, [])
        self.not_said(out, "max_job_bytes")


class P1SignatureTest(_GateCase):
    """Clause 2: a signature verifies, under the key the id selects."""

    def test_bad_signature_refused_and_id_not_consumed(self):
        job = _job2("sig-1")
        wrong = WRONGSECRET
        out = _run(job, None, True, wrong)
        self.refused(out, "bad signature")
        self.assertEqual(out.seen, {})

    def test_unknown_key_id_refused_before_any_mac(self):
        job = _job2("sig-2")
        out = _run(job=job, key_id="no-such-key")
        self.refused(out, "unknown key_id")

    def test_null_key_id_refused(self):
        # A present key_id that is null selects nothing: key
        # selection refuses it as unknown, before any MAC work.
        job = _job2("sig-3", key_id=None)
        out = _run(job=job)
        self.refused(out, "unknown key_id")

    def test_signed_under_one_key_named_as_another_refused(self):
        # The payload names the additional key but is signed with
        # the default secret: selection picks the named key's
        # secret and the MAC fails.
        job = _job2("sig-4")
        cfg = {"additional_secrets": {"upgrade": UPSECRET}}
        out = _run(job=job, key_id="upgrade", cfg_extra=cfg)
        self.refused(out, "bad signature")

    def test_fingerprint_key_id_selects_the_default_key(self):
        fp = runner._security.key_fingerprint(SECRET)
        job = _job2("sig-5")
        out = _run(job=job, key_id=fp)
        self.assertEqual(len(out.executed), 1)

    def test_named_additional_key_executes(self):
        job = _job2("sig-6")
        cfg = {"additional_secrets": {"upgrade": UPSECRET}}
        up = UPSECRET
        out = _run(job, None, True, up, "upgrade", cfg_extra=cfg)
        self.assertEqual(len(out.executed), 1)


class P1EnvelopeTest(_GateCase):
    """Clause 3: the one AEAD, the same key inside and out, and
    cleartext only under the process flag."""

    def test_tampered_envelope_refused_at_the_aead(self):
        job = _job2("env-1")
        body = jobcrypto.encrypt_body(
            sign_payload(job, SECRET), SECRET, job_id="env-1",
            key_id="", sign=sign_payload)
        envelope = _json.loads(body)
        ct = envelope["hp_enc"]["ct"]
        envelope["hp_enc"]["ct"] = ("A" if ct[0] != "A" else "B") + ct[1:]
        tampered = sign_payload(envelope, SECRET)
        msg = EmailMessage()
        msg["Subject"] = "[HOMING-PIGEON] job env-1"
        msg["From"] = "si@example.com"
        msg.set_content(tampered)
        out = _run(raw=msg.as_bytes())
        self.refused(out, "bad encrypted envelope")

    def test_inner_key_id_mismatch_refused(self):
        job = _job2("env-2")
        inner = dict(job)
        inner["key_id"] = "upgrade"
        body = jobcrypto.encrypt_body(
            sign_payload(inner, UPSECRET), SECRET, job_id="env-2",
            key_id="", sign=sign_payload)
        msg = EmailMessage()
        msg["Subject"] = "[HOMING-PIGEON] job env-2"
        msg["From"] = "si@example.com"
        msg.set_content(body)
        cfg = {"additional_secrets": {"upgrade": UPSECRET}}
        out = _run(raw=msg.as_bytes(), cfg_extra=cfg)
        self.refused(out, "key_id does not match")

    def test_cleartext_executes_only_with_the_process_flag(self):
        job = _job2("env-3")
        runner._set_allow_cleartext_jobs(True)
        try:
            out = _run(job=job, encrypt=False)
        finally:
            runner._set_allow_cleartext_jobs(False)
        self.assertEqual(len(out.executed), 1)
        self.said(out, "accepted under --allow-cleartext")

    def test_no_config_key_turns_cleartext_on(self):
        # C8: acceptance is a command-line decision only; a config
        # key that sounds like it does not exist in the gate.
        job = _job2("env-4")
        out = _run(job=job, encrypt=False,
                   cfg_extra={"allow_cleartext": True})
        self.refused(out, "cleartext job refused")


class P1AudienceTest(_GateCase):
    """Clause 4: the audience decision, in each of its modes."""

    def _cfg(self, mode):
        return {"security": {"modes": {"audience": mode}},
                "runner_id": "runner-1"}

    def test_enforce_mismatch_refused(self):
        job = _job2("aud-1", aud="runner-2")
        out = _run(job=job, cfg_extra=self._cfg("enforce"))
        self.refused(out, "security policy (audience)")

    def test_enforce_match_executes(self):
        job = _job2("aud-2", aud="runner-1")
        out = _run(job=job, cfg_extra=self._cfg("enforce"))
        self.assertEqual(len(out.executed), 1)

    def test_audit_mismatch_executes_and_is_recorded(self):
        job = _job2("aud-3", aud="runner-2")
        entries = []

        def capture(base_dir, feature, decision, reason, **kw):
            entries.append((feature, decision, reason))

        out = _run(job=job, cfg_extra=self._cfg("audit"),
                   patches=[mock.patch.object(
                       runner._security, "write_audit_entry", capture)])
        self.assertEqual(len(out.executed), 1)
        self.assertIn(("audience", "would_deny", "runner_id_mismatch"),
                      entries)

    def test_off_mismatch_executes(self):
        job = _job2("aud-4", aud="runner-2")
        out = _run(job=job, cfg_extra=self._cfg("off"))
        self.assertEqual(len(out.executed), 1)

    def test_enforce_without_a_runner_id_binds_nothing(self):
        # Stage 3 finding F4's precondition, pinned as the code
        # performs it: with no runner_id configured there is
        # nothing to bind to, and the check is skipped.
        job = _job2("aud-5", aud="runner-2")
        cfg = {"security": {"modes": {"audience": "enforce"}}}
        out = _run(job=job, cfg_extra=cfg)
        self.assertEqual(len(out.executed), 1)


class P1ScriptBoundTest(_GateCase):
    """Clause 5: the script bound, in UTF-8 bytes, after the
    signature."""

    def _exec_job(self, job_id, script):
        return _job2(job_id, kind="exec", script=script)

    def test_script_at_the_cap_executes(self):
        job = self._exec_job("scr-1", "x" * 10)
        out = _run(job=job, cfg_extra={"max_script_bytes": 10})
        self.assertEqual(len(out.executed), 1)

    def test_script_one_byte_over_refused(self):
        job = self._exec_job("scr-2", "x" * 11)
        out = _run(job=job, cfg_extra={"max_script_bytes": 10})
        self.refused(out, "script exceeds max_script_bytes")

    def test_the_measure_is_utf8_bytes_not_characters(self):
        # Six characters, twelve UTF-8 bytes: over a 10-byte cap.
        job = self._exec_job("scr-3", "é" * 6)
        out = _run(job=job, cfg_extra={"max_script_bytes": 10})
        self.refused(out, "script exceeds max_script_bytes")

    def test_cap_zero_is_unlimited(self):
        job = self._exec_job("scr-4", "x" * 5000)
        out = _run(job=job, cfg_extra={"max_script_bytes": 0})
        self.assertEqual(len(out.executed), 1)


class P1IdentityTest(_GateCase):
    """Clause 6: v is the integer 1, type is job, the body's id
    is the subject's."""

    def test_version_two_refused(self):
        out = _run(job=_job2("idn-1", v=2))
        self.refused(out, "unsupported version/type")

    def test_version_true_refused(self):
        out = _run(job=_job2("idn-2", v=True))
        self.refused(out, "unsupported version/type")

    def test_version_float_refused(self):
        out = _run(job=_job2("idn-3", v=1.0))
        self.refused(out, "unsupported version/type")

    def test_version_string_refused(self):
        out = _run(job=_job2("idn-4", v="1"))
        self.refused(out, "unsupported version/type")

    def test_type_other_than_job_refused(self):
        out = _run(job=_job2("idn-5", type="query"))
        self.refused(out, "unsupported version/type")

    def test_body_id_must_equal_subject_id(self):
        # Cleartext under the flag, so the handling reaches the
        # identity step (an encrypted body's envelope binds the
        # subject's id earlier, at decryption).
        job = _job2("idn-body")
        raw = _wire2(job, encrypt=False)
        raw = raw.replace(b"job idn-body", b"job idn-subject")
        runner._set_allow_cleartext_jobs(True)
        try:
            out = _run(raw=raw)
        finally:
            runner._set_allow_cleartext_jobs(False)
        self.refused(out, "job_id mismatch between subject and body")


class P1FreshnessTest(_GateCase):
    """Clause 7: issued_at parses, carries a timezone, and sits
    inside the window."""

    def test_stale_job_refused(self):
        job = _job2("fresh-1", issued_at=_issued(seconds=-7200))
        out = _run(job=job)
        self.refused(out, "issued_at outside allowed window")

    def test_future_beyond_the_bound_refused(self):
        job = _job2("fresh-2", issued_at=_issued(seconds=301))
        out = _run(job=job)
        self.refused(out, "issued_at outside allowed window")

    def test_future_inside_the_bound_executes(self):
        job = _job2("fresh-3", issued_at=_issued(seconds=299))
        out = _run(job=job)
        self.assertEqual(len(out.executed), 1)

    def test_naive_timestamp_refused(self):
        naive = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        job = _job2("fresh-4", issued_at=naive)
        out = _run(job=job)
        self.refused(out, "issued_at missing timezone")

    def test_unparseable_timestamp_refused(self):
        job = _job2("fresh-5", issued_at="not-a-date")
        out = _run(job=job)
        self.refused(out, "unparseable issued_at")

    def test_missing_timestamp_refused(self):
        job = _job2("fresh-6")
        del job["issued_at"]
        out = _run(job=job)
        self.refused(out, "unparseable issued_at")


class P1CheckOrderTest(_GateCase):
    """The order itself: when two clauses fail, the refusal the
    handling records is the earlier step's."""

    def test_size_before_signature(self):
        job = _job2("ord-1")
        wrong = WRONGSECRET
        raw = _wire2(job, wrong)
        out = _run(raw=raw, cfg_extra={"max_job_bytes": 10})
        self.refused(out, "mail exceeds max_job_bytes")
        self.not_said(out, "bad signature")

    def test_signature_before_cleartext(self):
        job = _job2("ord-2")
        wrong = WRONGSECRET
        out = _run(job, None, False, wrong)
        self.refused(out, "bad signature")
        self.not_said(out, "cleartext job refused")

    def test_cleartext_before_audience(self):
        job = _job2("ord-3", aud="runner-2")
        cfg = {"security": {"modes": {"audience": "enforce"}},
               "runner_id": "runner-1"}
        out = _run(job=job, encrypt=False, cfg_extra=cfg)
        self.refused(out, "cleartext job refused")
        self.not_said(out, "security policy (audience)")

    def test_audience_before_script_size(self):
        job = _job2("ord-4", kind="exec", script="x" * 100,
                    aud="runner-2")
        cfg = {"security": {"modes": {"audience": "enforce"}},
               "runner_id": "runner-1", "max_script_bytes": 10}
        out = _run(job=job, cfg_extra=cfg)
        self.refused(out, "security policy (audience)")
        self.not_said(out, "script exceeds max_script_bytes")

    def test_script_size_before_freshness(self):
        job = _job2("ord-5", kind="exec", script="x" * 100,
                    issued_at=_issued(seconds=-7200))
        out = _run(job=job, cfg_extra={"max_script_bytes": 10})
        self.refused(out, "script exceeds max_script_bytes")
        self.not_said(out, "issued_at outside allowed window")

    def test_freshness_before_key_policy(self):
        job = _job2("ord-6", issued_at=_issued(seconds=-7200))
        policies = {"": {"allowed_kinds": ["exec"]}}
        out = _run(job=job, policies=policies)
        self.refused(out, "issued_at outside allowed window")
        self.not_said(out, "key policy")

    def test_surrogate_carrying_job_never_executes(self):
        # Stage 3 finding F1: the encodability check stands in
        # the verification step as well as at its own step; both
        # refuse, and the outcome the property claims is the
        # refusal. The project's own signer refuses to sign such
        # a payload, so the body is signed here by hand, the way
        # a key holder's foreign tooling could produce it: the
        # surrogate rides as a \ud800 escape in the JSON text.
        job = _job2("ord-7", kind="exec", script="bad\ud800script")
        text = _json.dumps(job, separators=(",", ":"),
                           ensure_ascii=True)
        sig = _hmac.new(SECRET.encode("utf-8"),
                        text.encode("utf-8"),
                        _hashlib.sha384).hexdigest()
        body = text[:-1] + ',"sig":"' + sig + '"}'
        msg = EmailMessage()
        msg["Subject"] = "[HOMING-PIGEON] job ord-7"
        msg["From"] = "si@example.com"
        msg.set_content(body)
        out = _run(raw=msg.as_bytes())
        self.assertEqual(out.executed, [])
        self.said(out, "surrogate")


class P1HandlingShapeTest(_GateCase):
    """The steps around the clauses: panic first, the sensor
    branch through the gate, dry run last before the claim."""

    def test_panic_word_stops_everything_before_the_signature(self):
        word = runner._panic.generate_word()
        executed = []

        def execute(*_a, **_k):
            executed.append(1)
            return dict(_OK_RESULT)

        with tempfile.TemporaryDirectory() as directory:
            runner._panic.arm(directory, word)
            cfg = {"mailbox_user": "t@example.com",
                   "shared_secret": SECRET, "base_dir": directory,
                   "oracle_opinion_mode": "off"}
            msg = EmailMessage()
            msg["Subject"] = "[HOMING-PIGEON] panic " + word
            msg["From"] = "anyone@example.com"
            msg.set_content("not even signed")
            try:
                with mock.patch.object(runner, "execute_job", execute):
                    handle_mail(cfg, _IMAP2(), _SMTP2(), 3,
                                msg.as_bytes(), directory, {},
                                runner.build_secrets(cfg),
                                Namespace(dry_run=False, no_send=True),
                                None)
                self.assertEqual(executed, [])
                self.assertTrue(runner._panic.fired(directory))
            finally:
                runner._panic._FIRED = False

    def test_sensor_alert_leaves_through_the_gate_not_execution(self):
        job = _job2("sen-1", kind="sensor_alert")
        ingested = []

        def ingest(*args, **_k):
            ingested.append(args[3])

        out = _run(job=job, patches=[mock.patch.object(
            runner, "_ingest_sensor_alert", ingest)])
        self.assertEqual(out.executed, [])
        self.assertEqual(ingested, ["sen-1"])

    def test_dry_run_verifies_and_executes_nothing(self):
        job = _job2("dry-1")
        out = _run(job=job, opts=Namespace(dry_run=True, no_send=True))
        self.assertEqual(out.executed, [])
        self.assertEqual(out.seen, {})
        self.said(out, "dry-run: would execute job dry-1")

    def test_the_same_delivery_twice_executes_once(self):
        job = _job2("dup-1")
        raw = _wire2(job)
        seen = {}
        first = _run(raw=raw, seen=seen)
        second = _run(raw=raw, seen=seen)
        self.assertEqual(len(first.executed), 1)
        self.assertEqual(second.executed, [])


if __name__ == "__main__":
    unittest.main()
