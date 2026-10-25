#!/usr/bin/env python3
"""Q11: the email transport extension's failure shapes.

The happy path runs in test_transports (the round trip, the
seen-after-send discipline). What never ran anywhere, per the
coverage map, is what happens when things break mid-pass: a
connection that drops, an SMTP refusal on the result, a
logout or quit that raises, a sidecar that cannot be moved,
message shapes with no usable body, and the extension's own
main(). The promises under test are the module's header and
PROTOCOL.md section 5: a result that fails to send leaves the
job unseen for a retry, and a dropped connection fails the
pass, never the extension.
"""
import os
import smtplib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.tests.test_runner import FakeIMAP, FakeSMTP  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402
from runner.transport_extensions.email import (  # noqa: E402
    __main__ as email_ext)
from runner.wire import transports  # noqa: E402

CFG = {"mailbox_user": "runner-box@example.com",
       "poll_interval_sec": 1}

JOB_RAW = (b"Subject: [HOMING-PIGEON] job q11-1\r\n"
           b"From: someone@example.com\r\n"
           b'Content-Type: text/plain; charset="utf-8"\r\n'
           b"\r\nsigned-body")


class _Stop(Exception):
    pass


class EmailPipeFailureShapes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-q11-")
        self.paths = transports.channel_paths(self.tmp, "email")
        transports.ensure_channel_dirs(self.tmp, "email")
        self.channel = self.paths["root"]

    def _pipe(self, imap, smtp):
        return email_ext.EmailPipe(
            CFG, self.channel,
            imap_factory=lambda cfg: imap,
            smtp_factory=lambda cfg: smtp)

    def _write_result(self, ident="mail-1", subject="result",
                      body="signed-result"):
        path = os.path.join(self.channel, "outbox",
                            ident + ".result.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(ch.envelope(subject, body))
        return path

    def test_run_survives_a_dropped_connection_and_recovers(self):
        imap = FakeIMAP([JOB_RAW])
        calls = {"n": 0}

        def flaky_factory(cfg):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionResetError("server dropped us")
            return imap

        pipe = email_ext.EmailPipe(
            CFG, self.channel, imap_factory=flaky_factory,
            smtp_factory=lambda cfg: FakeSMTP())
        logs = []
        naps = {"n": 0}

        def nap(_interval):
            naps["n"] += 1
            if naps["n"] >= 2:
                raise _Stop()

        with mock.patch.object(ch, "log",
                               lambda m, level="INFO":
                               logs.append((level, m))), \
                mock.patch.object(ch, "nap", nap):
            with self.assertRaises(_Stop):
                pipe.run()
        self.assertTrue(
            any("pass failed" in m for _lvl, m in logs), logs)
        delivered = os.listdir(os.path.join(self.channel, "inbox"))
        self.assertIn("mail-1.job.txt", delivered)

    def test_pass_once_tolerates_logout_failure(self):
        class BadLogout(FakeIMAP):
            def logout(self):
                raise RuntimeError("connection already gone")

        pipe = self._pipe(BadLogout([JOB_RAW]), FakeSMTP())
        pipe.pass_once()  # must not raise
        delivered = os.listdir(os.path.join(self.channel, "inbox"))
        self.assertIn("mail-1.job.txt", delivered)

    def test_flush_tolerates_quit_failure(self):
        class BadQuit(FakeSMTP):
            def quit(self):
                raise RuntimeError("already closed")

        smtp = BadQuit()
        result = self._write_result()
        pipe = self._pipe(FakeIMAP([]), smtp)
        pipe.flush_results(FakeIMAP([]))  # must not raise
        self.assertEqual(len(smtp.sent), 1)
        self.assertFalse(os.path.exists(result))
        self.assertTrue(os.path.exists(os.path.join(
            self.channel, "outbox", "done", "mail-1.result.txt")))

    def test_smtp_refusal_leaves_result_pending_and_job_unseen(
            self):
        imap = FakeIMAP([JOB_RAW])
        pipe = self._pipe(imap, FakeSMTP())
        pipe.pass_once()  # delivers the job; no result yet
        result = self._write_result()

        class Refusing(FakeSMTP):
            def send_message(self, msg):
                raise smtplib.SMTPException("550 refused")

        pipe._smtp_factory = lambda cfg: Refusing()
        with self.assertRaises(smtplib.SMTPException):
            pipe.flush_results(imap)
        # The discipline: no ack, no seen -- the next pass
        # retries the send.
        self.assertTrue(os.path.exists(result))
        self.assertEqual(imap.flagged, [])

        good = FakeSMTP()
        pipe._smtp_factory = lambda cfg: good
        pipe.flush_results(imap)
        self.assertEqual(len(good.sent), 1)
        self.assertFalse(os.path.exists(result))
        self.assertEqual(imap.flagged, ["1"])

    def test_sidecar_move_failure_is_logged_not_fatal(self):
        self._write_result()
        sidecar = os.path.join(self.channel, "outbox",
                               "mail-1.target.txt")
        with open(sidecar, "w", encoding="utf-8") as fh:
            fh.write("worker@example.com")
        smtp = FakeSMTP()
        pipe = self._pipe(FakeIMAP([]), smtp)
        logs = []
        real_replace = os.replace

        def flaky_replace(src, dst):
            if str(dst).endswith(".target.txt"):
                raise OSError("simulated move failure")
            return real_replace(src, dst)

        with mock.patch.object(ch, "log",
                               lambda m, level="INFO":
                               logs.append((level, m))), \
                mock.patch("os.replace", flaky_replace):
            pipe.flush_results(FakeIMAP([]))
        self.assertEqual(len(smtp.sent), 1)
        self.assertTrue(
            any("cannot move sidecar" in m for _lvl, m in logs),
            logs)

    def test_subject_body_multipart_without_a_text_part(self):
        raw = (b"Subject: S\r\n"
               b"Content-Type: multipart/mixed; boundary=B\r\n"
               b"\r\n--B\r\n"
               b"Content-Type: application/octet-stream\r\n"
               b"Content-Transfer-Encoding: base64\r\n"
               b"\r\nAAAA\r\n--B--\r\n")
        self.assertEqual(email_ext._subject_body(raw), ("S", ""))

    def test_subject_body_text_part_with_a_filename_is_skipped(
            self):
        raw = (b"Subject: S\r\n"
               b"Content-Type: multipart/mixed; boundary=B\r\n"
               b"\r\n--B\r\n"
               b"Content-Type: text/plain\r\n"
               b"Content-Disposition: attachment;"
               b" filename=\"a.txt\"\r\n"
               b"\r\nattached\r\n--B--\r\n")
        self.assertEqual(email_ext._subject_body(raw), ("S", ""))


class EmailPipeMain(unittest.TestCase):
    def test_main_without_a_channel_returns_2(self):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("HOMING_PIGEON_TRANSPORT")}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(email_ext.main(["email-transport"]),
                             2)

    def test_main_with_a_config_runs_the_pipe(self):
        tmp = tempfile.mkdtemp(prefix="hp-q11-main-")
        cfg_path = os.path.join(tmp, "runtime.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            fh.write('{"mailbox_user": "runner-box@example.com"}')
        ran = []
        with mock.patch.object(email_ext.EmailPipe, "run",
                               lambda self: ran.append(self.channel)):
            rc = email_ext.main(
                ["email-transport", tmp, cfg_path])
        self.assertEqual(rc, 0)
        self.assertEqual(ran, [tmp])

    def test_module_entrypoint_exits_2_without_a_channel(self):
        # The runner launches transport extensions as modules
        # (transports.py builds [sys.executable, "-m", ...]).
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("HOMING_PIGEON_TRANSPORT")}
        proc = subprocess.run(
            [sys.executable, "-m",
             "runner.transport_extensions.email"],
            capture_output=True, text=True, env=env, cwd=REPO,
            timeout=60)
        self.assertEqual(proc.returncode, 2, proc.stderr)


class PendingResultsUnreadableTest(unittest.TestCase):
    """Queue A refill: channel.pending_results'
    unreadable leg (coverage run 40189711740: lines
    133-134). A result file that cannot be read as
    UTF-8 text is passed over; the pump still sees
    the results that can be read.
    """

    def test_an_undecodable_result_is_passed_over(self):
        import tempfile as _tempfile
        with _tempfile.TemporaryDirectory() as td:
            channel = os.path.join(td, "channel")
            outbox = ch.dirs(channel)["outbox"]
            with open(os.path.join(outbox, "good.result.txt"),
                      "w") as fh:
                fh.write(ch.envelope("subj", "body"))
            with open(os.path.join(outbox, "bad.result.txt"),
                      "wb") as fh:
                fh.write(b"\xff\xfe not utf-8")
            got = ch.pending_results(channel)
        self.assertEqual(got, [("good.result.txt", "subj",
                                "body")])


class XOAuth2RawTest(unittest.TestCase):
    """Queue A refill: mailbox._xoauth2_raw
    (coverage run 40189711740: lines 62-63). The
    IMAP XOAUTH2 string is composed from the
    mailbox user and a freshly refreshed access
    token, by the oauth module's own composer.
    """

    def test_the_raw_string_is_composed(self):
        import types as _types
        from runner.wire import mailbox
        fake = _types.SimpleNamespace(
            refresh_access_token=lambda cfg: "tok-1",
            xoauth2_raw=lambda user, tok: "user=%s tok=%s"
                                         % (user, tok))
        with mock.patch.object(mailbox, "_load_oauth",
                               return_value=fake):
            raw = mailbox._xoauth2_raw(
                {"mailbox_user": "runner-box@example.com"})
        self.assertEqual(
            raw, "user=runner-box@example.com tok=tok-1")


class SendMailUnbuildableTest(unittest.TestCase):
    """Queue A refill: send_mail's unbuildable-message
    leg (coverage run 40189711740: lines 353-355 of
    runner/wire/mailbox.py). A recipient carrying a
    newline cannot become a header; the function
    logs that the result message was not built and
    sends nothing, rather than raising into the
    job's retry path.
    """

    def test_a_newline_recipient_is_not_sent(self):
        from runner.wire import mailbox
        smtp = FakeSMTP()
        lines = []
        with mock.patch.object(
                mailbox, "log",
                lambda m, level="INFO": lines.append(m)):
            out = mailbox.send_mail(
                smtp, CFG, "result", "body",
                to="victim@example.com\nBcc: evil@example.com")
        self.assertIsNone(out)
        self.assertEqual(smtp.sent, [])
        self.assertTrue(any("not built" in m for m in lines))


if __name__ == "__main__":
    unittest.main(verbosity=2)
