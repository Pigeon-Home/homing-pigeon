"""Bounces in the inbox, and one odd message never stopping the poll.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

A delivery status notification about one of the runner's own results
("Undeliverable: [HOMING-PIGEON] result <id>", a multipart/report,
the quoted original inside it) is said once at INFO with the id it
refers to, marked seen, and never parsed as a job -- not even when
the provider's subject keeps the word "job". The subject parser
recognizes `job <id>` and nothing else. And a message whose parts
raise inside the handler fails that message alone: the poll finishes
and the message behind it is still handled. (Review item 4.)
"""
import os
import shutil
import sys
import unittest
import uuid
from email.message import EmailMessage
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runner", "cloud"))

from runner import runner as R  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402


def _dsn(subject, original_subject, original_bytes, style="gmail"):
    """A multipart/report DSN (report-type delivery-status) carrying a
    human part, a delivery-status part and the quoted original."""
    import email
    from email.mime.base import MIMEBase
    from email.mime.message import MIMEMessage
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    msg = MIMEMultipart("report", **{"report-type": "delivery-status"})
    msg["From"] = "mailer-daemon@example.com"
    msg["To"] = TR.SENDER
    msg["Subject"] = subject
    if style == "gmail":
        msg["Auto-Submitted"] = "auto-replied"
    msg.attach(MIMEText("Delivery to the following recipient failed "
                        "permanently:\n\n  someone@example.com\n\n"
                        "Technical details of permanent failure:\n"
                        "552 5.3.4 Message too large\n"))
    status = MIMEBase("message", "delivery-status")
    # A delivery-status body is a sequence of header blocks.
    status.set_payload([
        email.message_from_string("Reporting-MTA: dns; mx.example.com\n"),
        email.message_from_string("Final-Recipient: rfc822; someone@example.com\n"
                                  "Action: failed\nStatus: 5.3.4\n")])
    msg.attach(status)
    msg.attach(MIMEMessage(email.message_from_bytes(original_bytes)))
    return msg.as_bytes()


class BounceTest(unittest.TestCase):
    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.cfg = self.h.cfg
        self.tmp = self.h.tmp
        self.seen_path = self.h.seen_path

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cycle(self, mails):
        imap, smtp = TR.FakeIMAP(mails), TR.FakeSMTP()
        seen = {}
        lines = []
        real_log = R.log

        def spy(msg, level="INFO"):
            lines.append((level, msg))
            return real_log(msg, level)

        with mock.patch.object(R, "log", spy):
            R.poll_once(self.cfg, self.tmp, seen, self.seen_path,
                        imap=imap, smtp=smtp)
        return imap, smtp, seen, lines

    def test_dsn_in_inbox_is_ignored_and_marked_seen(self):
        jid = str(uuid.uuid4())
        job_mail = TR.job_email(TR.job_payload(jid))
        cases = {
            "gmail": "Undeliverable: [HOMING-PIGEON] result " + jid,
            "exchange": "Delivery Status Notification (Failure)",
            "postfix": "Undelivered Mail Returned to Sender",
            "quoted job": "Undeliverable: [HOMING-PIGEON] job " + jid,
        }
        for style, subject in cases.items():
            with self.subTest(style=style):
                dsn = _dsn(subject, "[HOMING-PIGEON] job " + jid, job_mail,
                           style="exchange" if style != "gmail" else "gmail")
                imap, smtp, seen, lines = self._cycle([dsn])
                self.assertEqual(smtp.sent, [])          # never a job
                self.assertEqual(seen, {})
                self.assertEqual([str(x) for x in imap.flagged], ["1"])
                bounce_lines = [m for lvl, m in lines
                                if lvl == "INFO" and m.startswith("bounce:")]
                self.assertEqual(len(bounce_lines), 1, lines)
                if "[HOMING-PIGEON]" in subject:
                    self.assertIn(jid, bounce_lines[0])
                self.assertFalse(any("rejecting" in m for _l, m in lines))
                # No auth_rejection event for a bounce (the resource
                # monitor may write other events under load).
                events = os.path.join(self.tmp, "security-events.jsonl")
                if os.path.exists(events):
                    with open(events, encoding="utf-8") as fh:
                        self.assertNotIn("auth_rejection", fh.read())

    def test_the_subject_parser_recognizes_job_and_nothing_else(self):
        jid = str(uuid.uuid4())
        for subject in ("[HOMING-PIGEON] result " + jid,
                        "[HOMING-PIGEON] query " + jid,
                        "Re: [HOMING-PIGEON] result " + jid,
                        "[HOMING-PIGEON] " + jid):
            with self.subTest(subject=subject):
                msg = EmailMessage()
                msg["From"] = TR.SENDER
                msg["To"] = TR.SENDER
                msg["Subject"] = subject
                msg.set_content("{}")
                imap, smtp, seen, _lines = self._cycle([msg.as_bytes()])
                self.assertEqual(smtp.sent, [])
                self.assertEqual(seen, {})
                self.assertEqual([str(x) for x in imap.flagged], ["1"])
        # The real thing still runs.
        imap, smtp, seen, _lines = self._cycle([TR.job_email(TR.job_payload(jid))])
        self.assertEqual(len(smtp.sent), 1)
        self.assertTrue(any(jid in k for k in seen))

    def test_bounce_of_names_what_it_refers_to(self):
        self.assertEqual(R._bounce_of("Undeliverable: [HOMING-PIGEON] result x9",
                                      b""), "result x9")
        self.assertEqual(R._bounce_of("Mail delivery failed: returning message "
                                      "to sender", b""), "a message")
        self.assertIsNone(R._bounce_of("[HOMING-PIGEON] job x9", b"plain"))
        self.assertIsNone(R._bounce_of("", None))
        dsn = _dsn("Returned", "[HOMING-PIGEON] job x9", b"x")
        self.assertEqual(R._bounce_of("anything at all", dsn), "a message")

    def test_poison_message_does_not_stop_the_poll(self):
        # One message whose body access raises; the one behind it is
        # handled, the poll finishes, and the broken one is left for
        # the operator (unseen, named in the log).
        jid_bad = str(uuid.uuid4())
        jid_good = str(uuid.uuid4())
        bad = TR.job_email(TR.job_payload(jid_bad))
        good = TR.job_email(TR.job_payload(jid_good))
        real = R.get_text_body

        def explode(msg):
            if jid_bad in str(msg["Subject"]):
                raise RuntimeError("payload exploded")
            return real(msg)

        with mock.patch.object(R, "get_text_body", explode):
            imap, smtp, seen, lines = self._cycle([bad, good])
        self.assertEqual(len(smtp.sent), 1)
        self.assertIn(jid_good, smtp.sent[0]["Subject"])
        self.assertTrue(any(jid_good in k for k in seen))
        self.assertFalse(any(jid_bad in k for k in seen))
        self.assertTrue(any("payload exploded" in m for _l, m in lines), lines)


if __name__ == "__main__":
    unittest.main()
