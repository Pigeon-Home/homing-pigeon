#!/usr/bin/env python3
"""Replay bodies captured from the live Gmail round-trip.

These are the real payloads from docs/archive/connector-roundtrip.md. They lock
in: a happy-path ping verifies and runs, a signature marker inside a
script field does not confuse the verifier, preambles/trailers around
the signed object are ignored, and tampering is rejected. The
test_mutation_* cases perturb the captures to probe the verifier's
edges (decoy markers, truncated/non-hex/mixed-case signatures, CRLF,
empty bodies).
"""

import os
import re
import sys
import tempfile
import unittest
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.wire import jobcrypto  # noqa: E402
from runner.runner import (  # noqa: E402
    execute_job,
    poll_once,
    sign_payload,
    verify_body,
)

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"

# Payload shape from message 1a1380ce30ccfbfb; sig re-computed with the test secret.
HAPPY_PING = (
    '{"v":1,"type":"job","job_id":"c142d598-261a-4000-8a41-b8cb7d28bf38",'
    '"issued_at":"2026-10-14T01:35:25Z","kind":"ping",'
    '"sig":"f30e8c12cefef51f936906f1a76ffbcdd104ebbb93b29cd20f3fa87c8357d075f2376187a37b0249afe0a075e2e115b0"}'
)

# Payload shape from message 1a1380e84018aa6a (sig marker inside script); sig re-computed.
SIG_IN_SCRIPT = (
    '{"v":1,"type":"job","job_id":"f62b9568-47fe-403e-8124-f9e06d5baed2",'
    '"issued_at":"2026-10-14T01:36:50Z","kind":"exec",'
    '"script":"echo \\",\\"sig\\":\\"deadbeef",'
    '"sig":"5027538989855f5d3866a30de3a4d7638779cff981b73d2dba1d42cb81674621b8389174b33b3d51f62fae0b34230be6"}'
)

# Payload shape from message 1a1380e8aa70b40a; sig re-computed and uppercased.
UPPER_SIG = (
    '{"v":1,"type":"job","job_id":"4653829a-a53a-44ba-85d5-90d52a73b980",'
    '"issued_at":"2026-10-14T01:36:50Z","kind":"ping",'
    '"sig":"77BF00AB0C36DF5E9EB481F245DFBCF79848E19F8E83F408455564C66F22A20C157BB7EFA0D0AE7B290FE2A266373542"}'
)

HAPPY_PREAMBLE = (
    "Homing Pigeon connector pipeline test. Safe to ignore or delete.\n\n"
    + HAPPY_PING
    + "\n"
)


class FakeIMAP:
    def __init__(self, mails):
        self.mails = list(mails)
        self.flagged = []

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

    def quit(self):
        pass


class ConnectorCaptureTests(unittest.TestCase):
    def test_happy_ping_verifies(self):
        job = verify_body(HAPPY_PING, SECRET)
        self.assertEqual(job["job_id"], "c142d598-261a-4000-8a41-b8cb7d28bf38")
        self.assertEqual(job["kind"], "ping")

    def test_happy_ping_executes(self):
        job = verify_body(HAPPY_PING, SECRET)
        base = tempfile.mkdtemp(prefix="hp-cap-")
        r = execute_job({"default_timeout_sec": 10}, job, base)
        self.assertEqual(r["exit_code"], 0)
        self.assertEqual(r["stdout"], "pong")

    def test_happy_ping_through_poll(self):
        # Rebuild a runner-legal mail from the captured payload and
        # a subject the runner accepts. The captured body itself is
        # genuine protocol 1 traffic; it rides inside an hp_enc
        # envelope, the only form the runner accepts by default.
        job = verify_body(HAPPY_PING, SECRET)
        wire = jobcrypto.encrypt_body(
            HAPPY_PING, SECRET, job_id=job["job_id"], key_id="",
            sign=sign_payload)
        msg = EmailMessage()
        msg["From"] = "runner@example.com"
        msg["To"] = "runner@example.com"
        msg["Subject"] = "[HOMING-PIGEON] job " + job["job_id"]
        msg.set_content(wire)
        base = tempfile.mkdtemp(prefix="hp-cap-")
        seen = {}
        imap, smtp = FakeIMAP([msg.as_bytes()]), FakeSMTP()
        cfg = {
            "mailbox_user": "runner@example.com",
            "mailbox_password": SECRET,
            "shared_secret": SECRET,
            "max_job_age_sec": 10**9,  # captured issued_at is in the past
        }
        poll_once(cfg, base, seen, os.path.join(base, "seen.json"),
                  imap=imap, smtp=smtp)
        self.assertEqual(len(smtp.sent), 1)
        # The result mirrors the job's encrypted form; unwrap it.
        result = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertTrue(jobcrypto.is_envelope(result))
        inner = jobcrypto.decrypt_body(
            result, SECRET, job["job_id"], result.get("key_id") or "")
        result = verify_body(inner, SECRET)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "pong")
        self.assertIn(job["job_id"], seen)

    def test_sig_marker_inside_script_still_verifies(self):
        job = verify_body(SIG_IN_SCRIPT, SECRET)
        self.assertEqual(job["job_id"], "f62b9568-47fe-403e-8124-f9e06d5baed2")
        self.assertIn("sig", job["script"])

    def test_uppercase_sig_accepted(self):
        # HMAC hex is case-insensitive. A sender that emits uppercase
        # must still verify.
        job = verify_body(UPPER_SIG, SECRET)
        self.assertEqual(job["job_id"], "4653829a-a53a-44ba-85d5-90d52a73b980")
        self.assertEqual(job["kind"], "ping")

    def test_preamble_is_ignored(self):
        # The note we put above the JSON in the real test mail is not
        # part of the signed content. Extraction must still verify.
        job = verify_body(HAPPY_PREAMBLE, SECRET)
        self.assertEqual(job["job_id"], "c142d598-261a-4000-8a41-b8cb7d28bf38")

    def test_preamble_and_trailer_ignored(self):
        wrapped = "note above\n\n" + HAPPY_PING + "\n-- \nsent from my phone\n"
        job = verify_body(wrapped, SECRET)
        self.assertEqual(job["kind"], "ping")

    def test_tampered_inside_wrapper_still_fails(self):
        bad = HAPPY_PING[:-3] + "00}"
        wrapped = "note\n" + bad + "\ntrailer\n"
        with self.assertRaises(ValueError):
            verify_body(wrapped, SECRET)

    # --- Mutations on the captured inputs: perturb the real payloads
    # to probe the verifier's edges. ---

    def test_preamble_with_braces_still_finds_object(self):
        # The object scanner must skip over brace-heavy preamble text
        # (and a whole closed JSON object) to find the signed root.
        preamble = 'if (x) { run(); } note: {"a": 1, "b": {"c": 2}}\n\n'
        job = verify_body(preamble + HAPPY_PING, SECRET)
        self.assertEqual(job["job_id"], "c142d598-261a-4000-8a41-b8cb7d28bf38")

    def test_fake_sig_marker_in_preamble_ignored(self):
        # rfind takes the LAST marker; an early decoy must not win.
        decoy = ',"sig":"' + "a" * 96 + '"}'
        body = "decoy: " + decoy + "\n\n" + HAPPY_PING
        job = verify_body(body, SECRET)
        self.assertEqual(job["kind"], "ping")

    def test_truncated_signature_rejected_cleanly(self):
        with self.assertRaises(ValueError):
            verify_body(HAPPY_PING[:-10], SECRET)

    def _sig_prefix(self, n=8):
        m = re.search(r'"sig":"([0-9a-fA-F]{%d})' % n, HAPPY_PING)
        return m.group(1)

    def test_non_hex_signature_rejected(self):
        bad = HAPPY_PING.replace('"sig":"' + self._sig_prefix(4),
                                 '"sig":"zzzz', 1)
        with self.assertRaises(ValueError):
            verify_body(bad, SECRET)

    def test_mixed_case_signature_accepted(self):
        prefix = self._sig_prefix()
        mixed = HAPPY_PING.replace('"sig":"' + prefix,
                                   '"sig":"' + prefix.upper(), 1)
        assert mixed != HAPPY_PING  # the replacement actually changed something
        job = verify_body(mixed, SECRET)
        self.assertEqual(job["kind"], "ping")

    def test_crlf_body_verifies(self):
        crlf = HAPPY_PING.replace("\n", "\r\n")
        job = verify_body(crlf, SECRET)
        self.assertEqual(job["job_id"], "c142d598-261a-4000-8a41-b8cb7d28bf38")

    def test_empty_body_rejected(self):
        with self.assertRaises(ValueError):
            verify_body("", SECRET)
        with self.assertRaises(ValueError):
            verify_body("no json here", SECRET)

    def test_marker_without_object_rejected(self):
        with self.assertRaises(ValueError):
            verify_body(',"sig":"' + "b" * 96 + '"}', SECRET)


if __name__ == "__main__":
    unittest.main(verbosity=2)
