#!/usr/bin/env python3
"""Per-job encryption end-to-end: envelopes through the real
mail path (poll_once with fake IMAP/SMTP -- the same fakes the
protocol edge tests use), result mirroring, the job_encryption
config override, and the send_job CLI default.

Unit-level primitive and envelope-shape proof lives in
tests/test_jobcrypto.py; this file proves the integrated
behavior: verify-before-decrypt in handle_mail, the second
signature check on the recovered body, and results that mirror
the job's form.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "cloud"))

from runner import jobcrypto  # noqa: E402
from runner import runner as runner_mod  # noqa: E402
from runner.runner import poll_once, verify_body, verify_body_keyed  # noqa: E402
import send_job  # noqa: E402

SECRET = ("kX9f" "2vQz" "7Lp4" "Wd8s" "Rb3N" "j6Hc" "5Ty1" "Mx0G" "aVqP")
ALT_SECRET = ("Zp8w" "Qx3K" "v7Nm" "2Bs9" "Df4G" "h6Jk" "1Lc5" "Rt0V" "yUnB")
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


def encrypted_mail(jid, secret=SECRET, key_id="", **kw):
    if key_id:
        kw["key_id"] = key_id
    signed = send_job.sign_payload(job_payload(jid, **kw), secret)
    wire = jobcrypto.encrypt_body(signed, secret, job_id=jid,
                                  key_id=key_id,
                                  sign=send_job.sign_payload)
    return mail(jid, wire)


class EncryptedMailPathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-enc-")
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

    def result_body(self, smtp):
        self.assertEqual(len(smtp.sent), 1)
        return smtp.sent[0].get_content()

    def test_encrypted_job_runs_and_result_is_encrypted(self):
        jid = str(uuid.uuid4())
        logs = []
        _, smtp, seen = self.cycle([encrypted_mail(jid)], logs=logs)
        self.assertIn(jid, seen)
        body = self.result_body(smtp)
        payload, key_id = verify_body_keyed(body, {"": SECRET})
        self.assertTrue(jobcrypto.is_envelope(payload))
        inner = jobcrypto.decrypt_body(payload, SECRET, jid, "")
        result = verify_body(inner, SECRET)
        self.assertEqual(result["type"], "result")
        self.assertEqual(result["job_id"], jid)
        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(any("clear text" in line for line in logs))

    def test_cleartext_job_runs_result_cleartext_and_is_logged(self):
        jid = str(uuid.uuid4())
        logs = []
        signed = send_job.sign_payload(job_payload(jid), SECRET)
        _, smtp, seen = self.cycle([mail(jid, signed)], logs=logs)
        self.assertIn(jid, seen)
        result = verify_body(self.result_body(smtp), SECRET)
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(any("received in clear text" in line
                            for line in logs))

    def test_runner_refuses_cleartext_unless_the_flag_is_set(self):
        jid = str(uuid.uuid4())
        signed = send_job.sign_payload(job_payload(jid), SECRET)
        raw = mail(jid, signed)
        seen = {}
        imap, smtp = FakeIMAP([raw]), FakeSMTP()
        refused = type("O", (), {"allow_cleartext": False,
                                 "dry_run": False, "no_send": False})()
        logs = []

        def fake_log(msg, level="INFO"):
            logs.append(str(msg))
        fake_log.identity_logged = True
        with mock.patch.object(runner_mod, "log", fake_log):
            poll_once(self.cfg, self.tmp, seen, self.seen_path,
                      imap=imap, smtp=smtp, opts=refused)
        self.assertEqual(len(smtp.sent), 0)
        self.assertNotIn(jid, seen)
        self.assertTrue(any("cleartext job refused" in line
                            for line in logs))

        jid2 = str(uuid.uuid4())
        signed2 = send_job.sign_payload(job_payload(jid2), SECRET)
        allowed = type("O", (), {"allow_cleartext": True,
                                 "dry_run": False, "no_send": True})()
        seen2 = {}
        imap2, smtp2 = FakeIMAP([mail(jid2, signed2)]), FakeSMTP()
        poll_once(self.cfg, self.tmp, seen2, self.seen_path,
                  imap=imap2, smtp=smtp2, opts=allowed)
        self.assertIn(jid2, seen2)

    def test_tampered_envelope_rejected_no_result(self):
        jid = str(uuid.uuid4())
        signed = send_job.sign_payload(job_payload(jid), SECRET)
        wire = jobcrypto.encrypt_body(signed, SECRET, job_id=jid,
                                      key_id="",
                                      sign=send_job.sign_payload)
        env = json.loads(wire[:wire.rfind(',"sig":"')] + "}")
        ct = env["hp_enc"]["ct"]
        env["hp_enc"]["ct"] = ("A" if ct[0] != "A" else "B") + ct[1:]
        tampered = json.dumps(env, separators=(",", ":")) \
            + wire[wire.rfind(',"sig":"'):]
        imap, smtp, seen = self.cycle([mail(jid, tampered)])
        self.assertEqual(len(smtp.sent), 0)
        self.assertNotIn(jid, seen)
        self.assertIn("1", imap.flagged)

    def test_encrypted_under_other_secret_rejected(self):
        # Outer signature verifies under SECRET; the ciphertext
        # was produced under ALT_SECRET, so AEAD must fail and
        # the job must not run.
        jid = str(uuid.uuid4())
        signed = send_job.sign_payload(job_payload(jid), SECRET)
        wire = jobcrypto.encrypt_body(
            signed, ALT_SECRET, job_id=jid, key_id="",
            sign=lambda p, s: send_job.sign_payload(p, SECRET))
        _, smtp, seen = self.cycle([mail(jid, wire)])
        self.assertEqual(len(smtp.sent), 0)
        self.assertNotIn(jid, seen)

    def test_unknown_alg_envelope_rejected_cleanly(self):
        jid = str(uuid.uuid4())
        env = {"hp_enc": {"alg": "aes-256-gcm",
                          "nonce": "AAAAAAAAAAAAAAA=",
                          "ct": "AAAAAAAAAAAAAAAAAAAAAA=="}}
        wire = send_job.sign_payload(env, SECRET)
        _, smtp, seen = self.cycle([mail(jid, wire)])
        self.assertEqual(len(smtp.sent), 0)
        self.assertNotIn(jid, seen)

    def test_key_id_job_and_result(self):
        jid = str(uuid.uuid4())
        cfg = dict(self.cfg)
        cfg["additional_secrets"] = {"alt": ALT_SECRET}
        _, smtp, seen = self.cycle(
            [encrypted_mail(jid, secret=ALT_SECRET, key_id="alt")],
            cfg=cfg)
        self.assertIn(jid, seen)
        body = self.result_body(smtp)
        secrets = {"": SECRET, "alt": ALT_SECRET}
        payload, key_id = verify_body_keyed(body, secrets)
        self.assertEqual(key_id, "alt")
        self.assertTrue(jobcrypto.is_envelope(payload))
        inner = jobcrypto.decrypt_body(payload, ALT_SECRET, jid,
                                       "alt")
        result = verify_body(inner, ALT_SECRET)
        self.assertEqual(result["exit_code"], 0)

    def test_job_encryption_true_encrypts_cleartext_jobs_result(self):
        jid = str(uuid.uuid4())
        cfg = dict(self.cfg, job_encryption=True)
        signed = send_job.sign_payload(job_payload(jid), SECRET)
        _, smtp, _ = self.cycle([mail(jid, signed)], cfg=cfg)
        payload, _ = verify_body_keyed(self.result_body(smtp),
                                       {"": SECRET})
        self.assertTrue(jobcrypto.is_envelope(payload))

    def test_job_encryption_false_sends_cleartext_result(self):
        jid = str(uuid.uuid4())
        cfg = dict(self.cfg, job_encryption=False)
        _, smtp, seen = self.cycle([encrypted_mail(jid)], cfg=cfg)
        self.assertIn(jid, seen)
        result = verify_body(self.result_body(smtp), SECRET)
        self.assertEqual(result["exit_code"], 0)

    def test_job_encryption_string_is_not_the_hatch(self):
        # Only literal False opens the hatch (mail_tls_required
        # discipline): a stray string keeps results encrypted.
        jid = str(uuid.uuid4())
        cfg = dict(self.cfg, job_encryption="false")
        _, smtp, _ = self.cycle([encrypted_mail(jid)], cfg=cfg)
        payload, _ = verify_body_keyed(self.result_body(smtp),
                                       {"": SECRET})
        self.assertTrue(jobcrypto.is_envelope(payload))


class SendJobCliTest(unittest.TestCase):
    def run_new(self, *extra):
        argv = ["send_job.py", "new", "--kind", "ping",
                "--secret", SECRET] + list(extra)
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", argv):
            with contextlib.redirect_stdout(buf):
                rc = send_job.main()
        self.assertEqual(rc, 0)
        return buf.getvalue()

    def test_new_encrypts_by_default(self):
        out = self.run_new()
        subject, _, body = out.partition("\n\n")
        jid = subject.rsplit(" ", 1)[1]
        payload, _ = verify_body_keyed(body, {"": SECRET})
        self.assertTrue(jobcrypto.is_envelope(payload))
        inner = jobcrypto.decrypt_body(payload, SECRET, jid, "")
        job = verify_body(inner, SECRET)
        self.assertEqual(job["kind"], "ping")

    def test_new_cleartext_flag(self):
        out = self.run_new("--cleartext")
        _, _, body = out.partition("\n\n")
        job = verify_body(body, SECRET)
        self.assertEqual(job["kind"], "ping")
        self.assertNotIn("hp_enc", job)

    def test_cloud_and_runner_share_the_module(self):
        self.assertIs(send_job.jobcrypto, jobcrypto)


if __name__ == "__main__":
    unittest.main()
