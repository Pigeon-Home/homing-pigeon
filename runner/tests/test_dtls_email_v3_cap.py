#!/usr/bin/env python3
"""Version 3 carriage: the version 1 mail size cap applies to
flight mail 1st (draft Section 5.3).

A flight mail's raw object is refused above the receiver's mail
size cap (max_job_bytes, the version 1 cap for mail on this
binding) before any base64 is decoded, any reassembly state is
allocated, or any octet is fed to a DTLS stack. Flight mail
never reaches the runner core -- the email transport extension
consumes it -- so the extension applies the cap in its own lane,
by the message's subject alone. An oversized flight mail is
consumed as malformed DTLS mail: marked seen, dropped, never
answered, and never reinterpreted as a job. The cap is not the
extension's to apply to ordinary job mail, which crosses to the
core under the core's own application of the same cap.
"""
import os
import sys
import tempfile
import unittest
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.transport_extensions.email import (  # noqa: E402
    __main__ as email_ext)
from runner.wire import dtls_mailbox, transports  # noqa: E402
from runner.wire.dtls_mailbox import (  # noqa: E402
    Deposit, DtlsMailClient, LocalMailbox, build_flight_message)
from runner.tests.test_dtls_email_v3 import (  # noqa: E402
    CFG, NOW, SECRET, SID, _job_envelope, _raw_mail)


class MailSizeCapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-v3-cap-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.paths = transports.channel_paths(self.tmp, "email")
        transports.ensure_channel_dirs(self.tmp, "email")
        self.channel = self.paths["root"]
        self.runner_box = LocalMailbox()
        self.client_box = LocalMailbox()

    def _pipe(self, **overrides):
        cfg = {
            "mailbox_user": "runner@example.com",
            "shared_secret": SECRET,
            "dtls_via_email": True,
            "dtls_greeting": "none",
            "oracle_opinion_mode": "off",
            "base_dir": self.tmp,
        }
        cfg.update(overrides)
        return email_ext.EmailPipe(
            cfg, self.channel,
            imap_factory=lambda cfg: self.runner_box,
            smtp_factory=lambda cfg: Deposit(self.client_box))

    def _flight_raw(self):
        client = DtlsMailClient(SECRET, session_id=SID)
        subject, body = client.start_mails(NOW)[0]
        return build_flight_message(CFG, subject, body).as_bytes()

    def _job_files(self):
        inbox = os.path.join(self.channel, "inbox")
        return [n for n in os.listdir(inbox)
                if n.endswith(".job.txt")]

    def test_an_oversized_flight_mail_is_refused_before_decoding(self):
        raw = self._flight_raw()
        pipe = self._pipe(max_job_bytes=len(raw) - 1)
        self.runner_box.add(raw)
        pipe.pass_once()
        # Consumed as DTLS mail, and nothing else happened: no
        # HelloRetryRequest was posted, no session exists, and
        # the mail was not reinterpreted as a job.
        self.assertTrue(self.runner_box.messages[0]["seen"])
        self.assertEqual(self.client_box.messages, [])
        self.assertEqual(self._job_files(), [])
        server = pipe._dtls_server
        self.assertIsNotNone(server)
        self.assertEqual(server.core.sessions, {})

    def test_a_flight_mail_at_the_cap_is_answered(self):
        raw = self._flight_raw()
        pipe = self._pipe(max_job_bytes=len(raw))
        self.runner_box.add(raw)
        pipe.pass_once()
        self.assertTrue(self.runner_box.messages[0]["seen"])
        self.assertEqual(len(self.client_box.messages), 1)
        parsed = dtls_mailbox.parse_message(
            self.client_box.messages[0]["raw"])
        self.assertIn(parsed.kind, ("dtls", "dtls-part"))

    def test_a_cap_of_zero_means_no_limit(self):
        raw = self._flight_raw()
        pipe = self._pipe(max_job_bytes=0)
        self.runner_box.add(raw)
        pipe.pass_once()
        self.assertEqual(len(self.client_box.messages), 1)

    def test_an_oversized_job_mail_is_not_the_extensions_to_refuse(self):
        pipe = self._pipe(max_job_bytes=1)
        body = _job_envelope("cap-job-1").decode("utf-8")
        _head, _sep, signed = body.partition("\n\n")
        self.runner_box.add(
            _raw_mail("[HOMING-PIGEON] job cap-job-1", signed))
        pipe.pass_once()
        names = self._job_files()
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].startswith("mail-"))

    def test_the_cap_decision_reads_the_subject_alone(self):
        raw = self._flight_raw()
        pipe = self._pipe(max_job_bytes=len(raw) - 1)
        self.assertTrue(pipe._flight_mail_over_cap(raw))
        at_cap = self._pipe(max_job_bytes=len(raw))
        self.assertFalse(at_cap._flight_mail_over_cap(raw))
        job_raw = _raw_mail("[HOMING-PIGEON] job cap-job-1",
                            "x" * (len(raw) + 10))
        self.assertFalse(pipe._flight_mail_over_cap(job_raw))
        other_raw = _raw_mail("a newsletter", "x" * (len(raw) + 10))
        self.assertFalse(pipe._flight_mail_over_cap(other_raw))


if __name__ == "__main__":
    unittest.main()
