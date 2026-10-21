#!/usr/bin/env python3
"""The cleartext (HMAC-only) job policy: secure by default,
command line only.

Andrew's confirmed shape (2026-10-19): the runner refuses a
signature-valid job whose body is not an hp_enc envelope BY
DEFAULT. Acceptance exists only as a command-line switch on
the runner process (--allow-cleartext): per-process,
never persisted, and deliberately with NO config-file key.
The senders keep their --cleartext flags (the same command-line
principle on the sending side), with encryption the default.
The HMAC signature is required in every mode: cleartext never
means unauthenticated -- a cleartext job with a bad signature
is rejected by the ordinary signature path, flag or no flag.

This file pins that contract:

- refusal by default, with the key-policy reject's semantics
  (logged, message marked seen, auth_rejection event recorded,
  NO result sent, job_id NOT recorded in the seen set);
- the flag enables acceptance for the process, and the result
  then mirrors in cleartext -- the field loop Andrew runs:
  send --cleartext, run the runner with the flag, read the
  cleartext job and result in the inbox (both are plain signed
  JSON as they sit on the wire, no encoding or wrapping);
- no config key can enable acceptance, plausible names
  included, and the CLI override table carries no cleartext
  entry (the flag never travels through cfg at all);
- both senders' --cleartext flags produce valid plain signed
  jobs; both senders encrypt by default;
- the installer can bake the flag into the installed service
  command, like the other runner flags it forwards;
- encrypted jobs are unaffected, flag off or on, on the mail
  path and on a transport channel (the form decides, not the
  channel -- DTLS included).
"""

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "cloud"))

from runner import install as install_mod  # noqa: E402
from runner import jobcrypto  # noqa: E402
from runner import runner as runner_mod  # noqa: E402
from runner.runner import (  # noqa: E402
    apply_cli_overrides, poll_once, process_transport_message,
    verify_body,
)
from runner.transport_extensions import channel as ch  # noqa: E402
import send_dtls  # noqa: E402
import send_job  # noqa: E402

SECRET = "hpct-" + "7f3a9c51e8b4d602a5f9c3e7b1d84062a5f9c3e7"
SENDER = "runner@example.com"


class FakeIMAP:
    def __init__(self, mails):
        self.mails = list(mails)
        self.flagged = []

    def login(self, u, p):
        return ("OK", [])

    def select(self, box):
        return ("OK", [])

    def search(self, *args):
        nums = b" ".join(str(i + 1).encode() for i in range(len(self.mails)))
        return ("OK", [nums])

    def fetch(self, num, _spec):
        raw = self.mails[int(num) - 1]
        head = f"{num.decode()} (RFC822 {{{len(raw)}}}".encode()
        return ("OK", [(head, raw), b")"])

    def store(self, seq, _op, _flags):
        self.flagged.append(seq)
        return ("OK", [])

    def logout(self):
        return ("OK", [])


class FakeSMTP:
    def __init__(self):
        self.sent = []

    def send_message(self, msg):
        self.sent.append(msg)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def job_payload(jid, **kw):
    p = {"v": 1, "type": "job", "job_id": jid,
         "issued_at": now_iso(), "kind": "ping"}
    p.update(kw)
    return p


def mail(jid, body):
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = SENDER
    msg["Subject"] = f"[HOMING-PIGEON] job {jid}"
    msg.set_content(body)
    return msg.as_bytes()


def cleartext_mail(jid, secret=SECRET):
    return mail(jid, send_job.sign_payload(job_payload(jid), secret))


def encrypted_mail(jid, secret=SECRET):
    signed = send_job.sign_payload(job_payload(jid), secret)
    wire = jobcrypto.encrypt_body(signed, secret, job_id=jid,
                                  key_id="",
                                  sign=send_job.sign_payload)
    return mail(jid, wire)


def run_send_job_new(*extra):
    argv = ["send_job.py", "new", "--kind", "ping",
            "--secret", SECRET, *extra]
    out = io.StringIO()
    with mock.patch.object(sys, "argv", argv):
        with contextlib.redirect_stdout(out):
            send_job.main()
    return out.getvalue()


class CleartextBase(unittest.TestCase):
    def setUp(self):
        # The flag is process state: pin it off at the start of
        # every test so test order cannot leak acceptance.
        runner_mod._set_allow_cleartext_jobs(False)
        self.addCleanup(runner_mod._set_allow_cleartext_jobs, False)
        self.tmp = tempfile.mkdtemp(prefix="hp-cleartext-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "shared_secret": SECRET,
            "imap_host": "fake", "imap_port": 993,
            "smtp_host": "fake", "smtp_port": 587,
            "max_job_age_sec": 3600,
            "max_output_bytes": 100000,
            "default_timeout_sec": 300,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails, cfg=None, logs=None):
        cfg = cfg or self.cfg
        seen = {}
        imap, smtp = FakeIMAP(mails), FakeSMTP()
        if logs is None:
            poll_once(cfg, self.tmp, seen, self.seen_path,
                      imap=imap, smtp=smtp)
        else:
            def fake_log(msg, level="INFO"):
                logs.append(str(msg))
            fake_log.identity_logged = True
            with mock.patch.object(runner_mod, "log", fake_log):
                poll_once(cfg, self.tmp, seen, self.seen_path,
                          imap=imap, smtp=smtp)
        return imap, smtp, seen

    def security_events(self):
        path = os.path.join(self.tmp, "security-events.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def result_body(self, smtp):
        return smtp.sent[0].get_content()


class RefusalByDefaultTest(CleartextBase):
    def test_cleartext_job_refused_with_key_policy_semantics(self):
        jid = str(uuid.uuid4())
        logs = []
        imap, smtp, seen = self.cycle([cleartext_mail(jid)], logs=logs)
        # No execution, no result -- exactly a key-policy reject.
        self.assertEqual(len(smtp.sent), 0)
        self.assertNotIn(jid, seen)
        # The message is still marked seen on the mailbox.
        self.assertIn("1", imap.flagged)
        # The refusal is logged, naming the default and the flag.
        self.assertTrue(any(
            "cleartext job refused" in line
            and "--allow-cleartext" in line for line in logs))
        # And recorded as an auth_rejection event with its reason.
        events = [e for e in self.security_events()
                  if e.get("type") == "auth_rejection"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].get("reason"),
                         "cleartext_not_supported")

    def test_cleartext_refused_over_a_transport_channel(self):
        # Every transport channel funnels through the same core
        # acceptance point (process_transport_message), DTLS
        # included: the object form decides, not the channel.
        jid = str(uuid.uuid4())
        body = send_job.sign_payload(job_payload(jid), SECRET)
        seen = {}
        sent = process_transport_message(
            self.cfg, self.tmp, seen, {"": SECRET}, {},
            f"[HOMING-PIGEON] job {jid}", body)
        self.assertEqual(sent, [])
        self.assertNotIn(jid, seen)


class NoConfigKeyTest(CleartextBase):
    def test_no_plausible_config_key_enables_acceptance(self):
        for key in ("allow_cleartext_jobs", "allow_cleartext",
                    "cleartext_jobs", "accept_cleartext_jobs"):
            jid = str(uuid.uuid4())
            cfg = dict(self.cfg, **{key: True})
            _, smtp, seen = self.cycle([cleartext_mail(jid)], cfg=cfg)
            self.assertEqual(len(smtp.sent), 0, key)
            self.assertNotIn(jid, seen, key)

    def test_example_config_has_no_cleartext_acceptance_key(self):
        path = os.path.join(REPO, "runner", "config.example.json")
        with open(path, encoding="utf-8") as fh:
            example = json.load(fh)
        self.assertNotIn("allow_cleartext_jobs", example)

    def test_flag_never_travels_through_cfg(self):
        # The CLI override table is how flags reach cfg; the
        # cleartext flag is not in it, and apply_cli_overrides
        # leaves both cfg and the acceptance state untouched.
        table = runner_mod._CLI_OVERRIDES
        self.assertFalse(any("cleartext" in dest or "cleartext" in key
                             for dest, key in table))
        cfg = dict(self.cfg)
        args = argparse.Namespace(allow_cleartext_jobs=True)
        applied = apply_cli_overrides(cfg, args)
        self.assertEqual(applied, [])
        self.assertNotIn("allow_cleartext_jobs", cfg)
        self.assertFalse(runner_mod._cleartext_jobs_allowed())

    def test_startup_block_is_silent_about_cleartext_by_default(self):
        logs = []
        args = argparse.Namespace(dry_run=False, no_send=False,
                                  once=False, verbose_level=1)
        def fake_log(msg, level="INFO"):
            logs.append(str(msg))
        fake_log.identity_logged = True
        with mock.patch.object(runner_mod, "log", fake_log):
            runner_mod.log_startup(self.cfg, args, self.tmp)
        self.assertFalse(any("ACCEPTED" in line for line in logs))

    def test_runner_help_lists_the_flag(self):
        proc = subprocess.run(
            [sys.executable,
             os.path.join(REPO, "runner", "runner.py"), "--help"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--allow-cleartext", proc.stdout)


class FlagAcceptanceTest(CleartextBase):
    def setUp(self):
        super().setUp()
        # The way main() turns the flag on for a process.
        runner_mod._set_allow_cleartext_jobs(True)

    def test_cleartext_job_executes_and_result_is_cleartext(self):
        jid = str(uuid.uuid4())
        logs = []
        _, smtp, seen = self.cycle([cleartext_mail(jid)], logs=logs)
        self.assertIn(jid, seen)
        self.assertEqual(len(smtp.sent), 1)
        # The result mirrors the job's form: plain signed JSON,
        # verifiable (and readable) exactly as it sits in the
        # inbox -- no envelope to unwrap first.
        result = verify_body(self.result_body(smtp), SECRET)
        self.assertFalse(jobcrypto.is_envelope(result))
        self.assertEqual(result["type"], "result")
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(any("received in clear text" in line
                            for line in logs))

    def test_cleartext_accepted_over_a_transport_channel(self):
        jid = str(uuid.uuid4())
        body = send_job.sign_payload(job_payload(jid), SECRET)
        seen = {}
        sent = process_transport_message(
            self.cfg, self.tmp, seen, {"": SECRET}, {},
            f"[HOMING-PIGEON] job {jid}", body)
        self.assertEqual(len(sent), 1)
        self.assertIn(jid, seen)

    def test_startup_block_announces_acceptance_prominently(self):
        logs = []
        args = argparse.Namespace(dry_run=False, no_send=False,
                                  once=False, verbose_level=1)
        def fake_log(msg, level="INFO"):
            logs.append((str(msg), level))
        fake_log.identity_logged = True
        with mock.patch.object(runner_mod, "log", fake_log):
            runner_mod.log_startup(self.cfg, args, self.tmp)
        warn = [m for m, lvl in logs if lvl == "WARN"]
        self.assertTrue(any(
            "--allow-cleartext" in line and "ACCEPTED" in line
            for line in warn))

    def test_bad_signature_cleartext_rejected_even_with_flag(self):
        # HMAC is required in every mode: a cleartext job whose
        # signature does not verify dies on the ordinary
        # signature path, never reaching the form check.
        jid = str(uuid.uuid4())
        forged = cleartext_mail(jid, secret="forged-" + "1b2c3d4e5f60718293a4b5c6d7e8f90123456789")
        _, smtp, seen = self.cycle([forged])
        self.assertEqual(len(smtp.sent), 0)
        self.assertNotIn(jid, seen)
        reasons = [e.get("reason") for e in self.security_events()
                   if e.get("type") == "auth_rejection"]
        self.assertNotIn("cleartext_not_supported", reasons)


class FieldScenarioTest(CleartextBase):
    """Andrew's acceptance scenario, composed end to end: the
    sender's --cleartext output is the job; a runner process
    with ONLY the command-line flag accepts and executes it and
    the result comes back readable; a runner without the flag
    refuses the very same bytes."""

    def test_sender_cleartext_round_trip(self):
        out = run_send_job_new("--cleartext")
        subject, _, body = out.partition("\n\n")
        jid = subject.rsplit(" ", 1)[-1].strip()
        # The wire form is human-readable as it sits in the
        # mailbox: plain JSON, signature visible, no wrapping.
        wire = json.loads(body)
        self.assertEqual(wire["job_id"], jid)
        self.assertIn("sig", wire)
        self.assertNotIn("hp_enc", wire)
        raw = mail(jid, body.strip())

        # Without the flag: refused, no result.
        _, smtp, seen = self.cycle([raw])
        self.assertEqual(len(smtp.sent), 0)
        self.assertNotIn(jid, seen)

        # With only the flag: executed, and the result in the
        # inbox is cleartext too.
        runner_mod._set_allow_cleartext_jobs(True)
        _, smtp, seen = self.cycle([raw])
        self.assertIn(jid, seen)
        self.assertEqual(len(smtp.sent), 1)
        result = verify_body(self.result_body(smtp), SECRET)
        self.assertFalse(jobcrypto.is_envelope(result))
        self.assertEqual(result["exit_code"], 0)


class SenderFlagsTest(CleartextBase):
    def test_send_job_cleartext_is_plain_signed_and_readable(self):
        out = run_send_job_new("--cleartext")
        _, _, body = out.partition("\n\n")
        job = verify_body(body.strip(), SECRET)
        self.assertEqual(job["kind"], "ping")
        self.assertNotIn("hp_enc", job)
        # Readable in an inbox: the job_id is right there in the
        # text an operator would open.
        self.assertIn(job["job_id"], body)

    def test_send_job_default_is_encrypted(self):
        out = run_send_job_new()
        _, _, body = out.partition("\n\n")
        outer = verify_body(body.strip(), SECRET)
        self.assertTrue(jobcrypto.is_envelope(outer))

    def _dtls_args(self, **over):
        ns = argparse.Namespace(
            kind="ping", job_id="compose-1", key_id=None,
            script_file=None, timeout=300, secret=SECRET,
            cleartext=False)
        for k, v in over.items():
            setattr(ns, k, v)
        return ns

    def test_send_dtls_cleartext_is_plain_signed(self):
        _job_id, envelope = send_dtls._build_body(
            self._dtls_args(cleartext=True))
        _subject, body = ch.parse_envelope(envelope.decode("utf-8"))
        payload = verify_body(body.strip(), SECRET)
        self.assertEqual(payload["job_id"], "compose-1")
        self.assertFalse(jobcrypto.is_envelope(payload))

    def test_send_dtls_default_is_encrypted(self):
        _job_id, envelope = send_dtls._build_body(self._dtls_args())
        _subject, body = ch.parse_envelope(envelope.decode("utf-8"))
        outer = verify_body(body.strip(), SECRET)
        self.assertTrue(jobcrypto.is_envelope(outer))

    def test_send_dtls_help_lists_cleartext(self):
        proc = subprocess.run(
            [sys.executable,
             os.path.join(REPO, "cloud", "send_dtls.py"), "--help"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--cleartext", proc.stdout)

    # The board subcommands must follow the same rule as `new`: the
    # default runner refuses a cleartext board message, so a tool
    # that emitted one by default produced messages nobody could
    # accept without --allow-cleartext (claims audit 2026-10-21,
    # finding C-01).
    def _run_board(self, *argv):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["send_job.py", *argv]):
            with contextlib.redirect_stdout(out):
                send_job.main()
        subject, _, body = out.getvalue().partition("\n\n")
        return subject.strip(), body.strip()

    def test_task_submit_default_is_an_envelope_the_runner_admits(self):
        subject, body = self._run_board(
            "task-submit", "--task-id", "t-1", "--secret", SECRET)
        self.assertEqual(subject, "[HOMING-PIGEON] task_submit t-1")
        outer = verify_body(body, SECRET)
        self.assertTrue(jobcrypto.is_envelope(outer))
        payload, _kid, _sec, encrypted = runner_mod._admit_object(
            body, {"": SECRET}, "t-1")
        self.assertTrue(encrypted)
        self.assertEqual(payload["task_id"], "t-1")

    def test_task_request_default_is_an_envelope_the_runner_admits(self):
        subject, body = self._run_board(
            "task-request", "--worker-id", "w-1", "--secret", SECRET,
            "--capability", "py", "--capability", "review")
        self.assertEqual(subject, "[HOMING-PIGEON] task_request w-1")
        payload, _kid, _sec, encrypted = runner_mod._admit_object(
            body, {"": SECRET}, "w-1")
        self.assertTrue(encrypted)
        self.assertEqual(payload["worker_id"], "w-1")
        self.assertEqual(payload["capabilities"], ["py", "review"])

    def test_board_cleartext_flag_is_plain_signed(self):
        _subject, body = self._run_board(
            "task-submit", "--task-id", "t-2", "--secret", SECRET,
            "--cleartext")
        payload = verify_body(body, SECRET)
        self.assertFalse(jobcrypto.is_envelope(payload))
        self.assertEqual(payload["task_id"], "t-2")


class InstallerBakeTest(unittest.TestCase):
    def _args(self, **over):
        ns = types.SimpleNamespace(
            dry_run=False, no_send=False, pdb=False,
            allow_cleartext=False, verbose=True,
            poll_interval=None, max_output_bytes=None,
            timeout=None, workers=None)
        for k, v in over.items():
            setattr(ns, k, v)
        return ns

    def test_flag_bakes_into_the_service_command(self):
        baked = install_mod._forwarded_args(
            self._args(allow_cleartext=True))
        self.assertIn("--allow-cleartext", baked)

    def test_flag_absent_by_default(self):
        baked = install_mod._forwarded_args(self._args())
        self.assertNotIn("--allow-cleartext", baked)


class EncryptedUnaffectedTest(CleartextBase):
    def test_encrypted_job_end_to_end_by_mail(self):
        jid = str(uuid.uuid4())
        _, smtp, seen = self.cycle([encrypted_mail(jid)])
        self.assertIn(jid, seen)
        self.assertEqual(len(smtp.sent), 1)
        outer = verify_body(self.result_body(smtp), SECRET)
        self.assertTrue(jobcrypto.is_envelope(outer))

    def test_encrypted_job_over_a_transport_channel(self):
        jid = str(uuid.uuid4())
        signed = send_job.sign_payload(job_payload(jid), SECRET)
        wire = jobcrypto.encrypt_body(signed, SECRET, job_id=jid,
                                      key_id="",
                                      sign=send_job.sign_payload)
        seen = {}
        sent = process_transport_message(
            self.cfg, self.tmp, seen, {"": SECRET}, {},
            f"[HOMING-PIGEON] job {jid}", wire)
        self.assertEqual(len(sent), 1)
        self.assertIn(jid, seen)

    def test_encrypted_job_also_fine_with_flag_on(self):
        runner_mod._set_allow_cleartext_jobs(True)
        jid = str(uuid.uuid4())
        _, smtp, seen = self.cycle([encrypted_mail(jid)])
        self.assertIn(jid, seen)
        self.assertEqual(len(smtp.sent), 1)


if __name__ == "__main__":
    unittest.main()
