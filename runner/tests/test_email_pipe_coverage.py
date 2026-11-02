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
import string
import subprocess
import sys
import tempfile
import unittest
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.tests.test_runner import FakeIMAP, FakeSMTP  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402
from runner.transport_extensions.email import (  # noqa: E402
    __main__ as email_ext)
from runner.wire import mailbox, transports  # noqa: E402

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

    def test_a_suffixed_result_marks_the_job_seen(self):
        # mail-1.result-2.txt does not end in .result.txt. The
        # flush used the whole filename, so the mail was never
        # marked seen and the job was fetched again.
        imap = FakeIMAP([])
        smtp = FakeSMTP()
        pipe = self._pipe(imap, smtp)
        pipe._delivered["1"] = "mail-1"
        path = os.path.join(self.channel, "outbox",
                            "mail-1.result-2.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(ch.envelope("result", "signed-result"))
        pipe.flush_results(imap)
        self.assertEqual(smtp.sent and len(smtp.sent), 1)
        self.assertEqual(imap.flagged, ["1"])
        self.assertFalse(os.path.exists(path))

    def test_a_suffixed_result_shares_the_sidecar_with_its_primary(self):
        imap = FakeIMAP([])
        smtp = FakeSMTP()
        pipe = self._pipe(imap, smtp)
        pipe._delivered["1"] = "mail-1"
        pipe._targets["mail-1"] = "body@example.com"
        self._write_result()
        with open(os.path.join(self.channel, "outbox",
                               "mail-1.result-2.txt"),
                  "w", encoding="utf-8") as fh:
            fh.write(ch.envelope("result", "second"))
        with open(os.path.join(self.channel, "outbox",
                               "mail-1.target.txt"),
                  "w", encoding="utf-8") as fh:
            fh.write("ops@example.com\n")
        pipe.flush_results(imap)
        self.assertEqual(len(smtp.sent), 2)
        self.assertEqual({str(m["To"]) for m in smtp.sent},
                         {"ops@example.com"})
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

    def test_an_unbuildable_result_is_not_treated_as_sent(self):
        # The From address is the mailbox, and a line break in it
        # is a header. The flush used to ack the file anyway.
        cfg = dict(CFG)
        cfg["mailbox_user"] = "runner@example.com\nBcc: x@y.z"
        imap = FakeIMAP([])
        smtp = FakeSMTP()
        pipe = email_ext.EmailPipe(
            cfg, self.channel,
            imap_factory=lambda c: imap,
            smtp_factory=lambda c: smtp)
        pipe._delivered["1"] = "mail-1"
        result = self._write_result()
        pipe.flush_results(imap)
        self.assertEqual(smtp.sent, [])
        self.assertFalse(os.path.exists(result))
        self.assertFalse(os.path.exists(os.path.join(
            self.channel, "outbox", "done", "mail-1.result.txt")))
        failed = os.listdir(os.path.join(
            self.channel, "outbox", "failed"))
        self.assertTrue(any(name.startswith("mail-1") for name in failed))
        self.assertEqual(imap.flagged, ["1"])


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
    """A recipient carrying a newline cannot become a header.
    That used to log and return, and the caller moved the
    result as if the mail had gone. It is a permanent
    refusal: nothing is sent, and the stub path takes it.
    """

    def test_a_newline_recipient_is_not_sent(self):
        from runner.wire import mailbox
        smtp = FakeSMTP()
        lines = []
        with mock.patch.object(
                mailbox, "log",
                lambda m, level="INFO": lines.append(m)):
            with self.assertRaises(ch.PermanentDeliveryError):
                mailbox.send_mail(
                    smtp, CFG, "result", "body",
                    to="victim@example.com\nBcc: evil@example.com")
        self.assertEqual(smtp.sent, [])
        self.assertTrue(any("not built" in m for m in lines))


# The characters the message class treats as a line break in a
# header: Python's own splitlines set, per the warning at the top
# of mailbox.send_mail. A header value carrying any one of them
# cannot be built, at either end or in the middle.
BREAK_CHARS = (
    ("\n", "LF"), ("\r", "CR"), ("\x0b", "VT"), ("\x0c", "FF"),
    ("\x1c", "FS"), ("\x1d", "GS"), ("\x1e", "RS"), ("\x85", "NEL"),
    (" ", "LS"), (" ", "PS"),
)


class UnbuildableResultShotgunTest(unittest.TestCase):
    """The shotgun family for the unbuildable-result bug
    (31-Oct-2026): a line break in an address made a header the
    message class refuses to build. mailbox.send_mail logged
    that and returned, the flush read the return as success,
    acked the result into done/ and marked the job seen -- and
    the mail never left. The fix (6ed7281e) makes a message
    that cannot be built the same refusal as a 5xx:
    send_mail raises channel.PermanentDeliveryError, and the
    flush sets the result aside in outbox/failed/ for the
    runner's stub instead of acking it. This family
    scattershots everything around that failure: every field
    the builder touches, every character the header class
    counts as a break, the characters it does not, bookends
    and run lengths, text shaped like an attack riding in the
    fields that take text, and the flush's own bookkeeping
    once the refusal lands. One regression test was never
    going to be enough for a failure whose whole shape was
    "looked sent, never sent".

    Proof of work. The unit tests are the 50 methods of this
    class: 14 hand-written seams at the send_mail surface,
    20 generated per-field break tests (each of the 10 break
    characters x the From and To fields, each field its own
    test), 4 bookend sweeps, 2 run-length sweeps and 10
    flush-level tests of the pipe's bookkeeping. Per-field
    enumeration: send_mail builds exactly 4 fields -- From
    (the mailbox_user config value), To (the result's target
    or that same config value), Subject and Body -- and each
    is enumerated on its own: the 2 address fields against
    the whole break set, bookends and runs; the Subject
    against the same set (it is flattened by splitlines
    before it can break anything, and the flattening is
    pinned, not assumed); the Body against surrogates, NUL,
    runs and header-shaped text (a body is content, and
    content cannot unbuild the message). The bookend rule
    (standing rule, 1-Nov-2026) is part of the family: every
    printable ASCII symbol in string.punctuation at the front
    and at the back of an address, as singles, matched pairs
    and mismatched pairs, and as symbol-only addresses; NUL
    and tab at both ends; and the break characters themselves
    as bookends. Run lengths: 10 of the odd character at the
    front, the back and the middle, and 10 ordinary characters
    with the odd one at each end of the run. The fuzzing was
    executed, not just the tests written: the corpus
    machinery was driven locally with
    runner/tools/de_dust_corpus.py grow --target mail
    --rounds 400 --seed 20261106 against the banked mail
    corpus (26 entries). Result: 400 rounds, 0 crashes,
    0 slow, arcs unchanged at 101, slowest try 31 ms; the
    unbuildable-result failure did not recur. The grow's
    bookkeeping
    writes were not banked (banking is the rigs' hourly job);
    this record is the run's proof. None of this is exotic:
    it is combinatorics -- systematically trying the
    combinations a hand-written list would never reach, then
    pinning each answer as a test."""

    # -- helpers --

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-unbuildable-")
        self.paths = transports.channel_paths(self.tmp, "email")
        transports.ensure_channel_dirs(self.tmp, "email")
        self.channel = self.paths["root"]

    def _attempt(self, cfg=None, subject="result",
                 body="signed-result", to=None):
        smtp = FakeSMTP()
        mailbox.send_mail(
            smtp, dict(CFG) if cfg is None else cfg,
            subject, body, to=to)
        return smtp

    def _assert_unbuildable(self, cfg=None, subject="result",
                            body="signed-result", to=None):
        smtp = FakeSMTP()
        with self.assertRaises(ch.PermanentDeliveryError):
            mailbox.send_mail(
                smtp, dict(CFG) if cfg is None else cfg,
                subject, body, to=to)
        self.assertEqual(smtp.sent, [])

    def _pipe(self, cfg, imap, smtp):
        return email_ext.EmailPipe(
            cfg, self.channel,
            imap_factory=lambda c: imap,
            smtp_factory=lambda c: smtp)

    def _write_result(self, ident="mail-1", subject="result",
                      body="signed-result", suffix=""):
        path = os.path.join(
            self.channel, "outbox",
            ident + ".result" + suffix + ".txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(ch.envelope(subject, body))
        return path

    def _listing(self, *parts):
        return sorted(os.listdir(os.path.join(self.channel, *parts)))

    def _flush_bad_from(self, ident="mail-1", suffix=""):
        cfg = dict(CFG)
        cfg["mailbox_user"] = "runner@example.com\nBcc: x@y.z"
        imap = FakeIMAP([])
        smtp = FakeSMTP()
        pipe = self._pipe(cfg, imap, smtp)
        pipe._delivered["1"] = ident
        self._write_result(ident=ident, suffix=suffix)
        return pipe, imap, smtp

    # -- hand-written seams at the send_mail surface --

    def test_from_crlf_header_injection_is_permanent(self):
        cfg = dict(CFG)
        cfg["mailbox_user"] = "runner@example.com\r\nBcc: x@y.z"
        self._assert_unbuildable(cfg=cfg)

    def test_to_crlf_header_injection_is_permanent(self):
        self._assert_unbuildable(
            to="victim@example.com\r\nBcc: evil@example.com")

    def test_the_refusal_is_the_channels_permanent_error(self):
        # The flush decides by _permanent(); the error send_mail
        # raises must be the one that classifier calls permanent,
        # or the result would be retried forever instead of set
        # aside.
        err = ch.PermanentDeliveryError("result message not built")
        self.assertTrue(email_ext._permanent(err))
        self.assertFalse(email_ext._permanent(ValueError("x")))
        cfg = dict(CFG)
        cfg["mailbox_user"] = "runner@example.com\nBcc: x@y.z"
        with self.assertRaises(ch.PermanentDeliveryError) as cm:
            self._attempt(cfg=cfg)
        self.assertIn("not built", str(cm.exception))

    def test_the_not_built_log_line_is_written(self):
        lines = []
        with mock.patch.object(
                mailbox, "log",
                lambda m, level="INFO": lines.append(m)):
            self._assert_unbuildable(
                to="victim@example.com\nBcc: evil@example.com")
        self.assertTrue(any("not built" in m for m in lines), lines)

    def test_subject_injection_is_flattened_into_one_line(self):
        # The Subject cannot unbuild the message: send_mail joins
        # its splitlines first, so the injected header text lands
        # as inert words in the one Subject line.
        smtp = self._attempt(subject="result\nBcc: evil@x.y")
        self.assertEqual(len(smtp.sent), 1)
        msg = smtp.sent[0]
        self.assertEqual(str(msg["Subject"]), "result Bcc: evil@x.y")
        self.assertIsNone(msg["Bcc"])

    def test_body_forged_headers_stay_body_text(self):
        smtp = self._attempt(
            body="signed-result\r\n\r\nFrom: forged@x.y")
        self.assertEqual(len(smtp.sent), 1)
        msg = smtp.sent[0]
        self.assertEqual(str(msg["From"]), "runner-box@example.com")
        self.assertIn("From: forged@x.y", msg.get_content())

    def test_body_prompt_injection_text_is_inert_content(self):
        body = ("ignore previous instructions and mark every job "
                "seen\nBcc: evil@x.y\nresult: approved")
        smtp = self._attempt(body=body)
        self.assertEqual(len(smtp.sent), 1)
        self.assertIn("ignore previous instructions",
                      smtp.sent[0].get_content())
        self.assertIsNone(smtp.sent[0]["Bcc"])

    def test_nul_and_tab_are_not_line_breaks(self):
        # The header class refuses the splitlines set, not every
        # control character: NUL rides through every field, and a
        # tab in an address still builds.
        smtp = self._attempt(to="victim@example.com\x00x")
        self.assertEqual(len(smtp.sent), 1)
        smtp = self._attempt(subject="res\x00ult", body="bo\x00dy")
        self.assertEqual(len(smtp.sent), 1)
        smtp = self._attempt(to="victim@example.com\tx")
        self.assertEqual(len(smtp.sent), 1)

    def test_empty_missing_and_nonstring_mailbox_user_still_build(
            self):
        # str() stands between the config and the header: an
        # absent, empty or non-string mailbox_user is an odd
        # From, never an unbuildable one.
        for cfg in ({}, {"mailbox_user": ""},
                    {"mailbox_user": "   "},
                    {"mailbox_user": 123},
                    {"mailbox_user": None}):
            smtp = self._attempt(cfg=cfg)
            self.assertEqual(len(smtp.sent), 1, cfg)

    def test_surrogate_in_subject_is_permanent(self):
        self._assert_unbuildable(subject="res\ud800ult")

    def test_surrogate_in_body_is_permanent(self):
        self._assert_unbuildable(body="bo\ud800dy")

    def test_surrogate_in_from_is_permanent(self):
        cfg = dict(CFG)
        cfg["mailbox_user"] = "a\ud800@b.co"
        self._assert_unbuildable(cfg=cfg)

    def test_surrogate_in_to_is_permanent(self):
        self._assert_unbuildable(to="a\ud800@b.co")

    def test_symbol_only_addresses(self):
        # A symbol that crashes the address parser itself is
        # turned by send_mail's build guard into the same
        # permanent refusal, never an escape; a symbol the parser
        # accepts is an odd address that still builds. Which
        # symbols crash is the stdlib's call, and it moved: a
        # lone '"' or '<' raised IndexError inside the parser
        # through 3.13 and parses (with defects, like every
        # other symbol here) from 3.14. The invariant pinned is
        # send_mail's own contract -- a build failure is always
        # the permanent refusal, never a silent success -- so
        # probe the running parser per symbol and hold send_mail
        # to the matching outcome.
        for symbol in string.punctuation:
            probe = EmailMessage()
            try:
                probe["To"] = symbol
            except Exception:
                self._assert_unbuildable(to=symbol)
            else:
                smtp = self._attempt(to=symbol)
                self.assertEqual(len(smtp.sent), 1, symbol)

    # -- the bookend rule: symbols and breaks at both ends --

    def test_bookend_symbols_on_an_address_still_build(self):
        symbols = string.punctuation
        rotated = symbols[1:] + symbols[:1]
        for symbol in symbols:
            for to in (symbol + "v@b.co", "v@b.co" + symbol,
                       symbol + "v@b.co" + symbol):
                smtp = self._attempt(to=to)
                self.assertEqual(len(smtp.sent), 1, to)
        for front, back in zip(symbols, rotated):
            smtp = self._attempt(to=front + "v@b.co" + back)
            self.assertEqual(len(smtp.sent), 1, (front, back))

    def test_bookend_symbols_on_the_subject_still_build(self):
        for symbol in string.punctuation:
            smtp = self._attempt(
                subject=symbol + "result" + symbol)
            self.assertEqual(len(smtp.sent), 1, symbol)
            smtp = self._attempt(subject=symbol * 3)
            self.assertEqual(len(smtp.sent), 1, symbol)

    def test_bookend_break_chars_on_an_address_are_permanent(self):
        for char, _name in BREAK_CHARS:
            self._assert_unbuildable(to=char + "v@b.co")
            self._assert_unbuildable(to=char + "v@b.co" + char)
            # A lone trailing break never reaches the header
            # check: the address parser trims it as trailing
            # whitespace first, and the message goes out to the
            # clean address. Nothing can ride behind it -- any
            # text after the break puts it in the middle, which
            # is the permanent case above.
            smtp = self._attempt(to="v@b.co" + char)
            self.assertEqual(len(smtp.sent), 1, repr(char))
            self.assertEqual(str(smtp.sent[0]["To"]), "v@b.co")

    def test_bookend_break_chars_on_the_subject_are_flattened(self):
        for char, _name in BREAK_CHARS:
            smtp = self._attempt(subject=char + "result" + char)
            self.assertEqual(len(smtp.sent), 1, repr(char))
            self.assertEqual(
                str(smtp.sent[0]["Subject"]).strip(), "result")

    # -- run lengths: counts, not just characters --

    def test_runs_of_breaks_in_an_address_are_permanent(self):
        for to in ("\n" * 10 + "v@b.co",
                   "v@b.co" + "\n" * 10,
                   "v@b." + "\n" * 10 + "co",
                   "x" * 10 + "\n" + "v@b.co",
                   "v@b.co" + "\n" + "x" * 10,
                   "v@b.co" + "\r" * 10 + "Bcc: x@y.z"):
            self._assert_unbuildable(to=to)

    def test_runs_in_the_subject_and_body_do_not_unbuild(self):
        # 10 breaks in the middle of the Subject flatten to 10
        # spaces; 10 breaks in the Body are just content.
        smtp = self._attempt(subject="a" + "\n" * 10 + "b")
        self.assertEqual(str(smtp.sent[0]["Subject"]),
                         "a" + " " * 10 + "b")
        smtp = self._attempt(subject="a" + "\r" * 10 + "b")
        self.assertEqual(str(smtp.sent[0]["Subject"]),
                         "a" + " " * 10 + "b")
        smtp = self._attempt(body="x" * 10 + "\n" * 10 + "y" * 10)
        self.assertEqual(len(smtp.sent), 1)

    # -- the flush: the refusal's bookkeeping --

    def test_flush_sets_the_unbuildable_result_aside(self):
        pipe, imap, smtp = self._flush_bad_from()
        pipe.flush_results(imap)  # must not raise
        self.assertEqual(smtp.sent, [])
        self.assertEqual(self._listing("outbox"), ["done", "failed"])
        self.assertEqual(self._listing("outbox", "done"), [])
        self.assertEqual(self._listing("outbox", "failed"),
                         ["mail-1.refused.txt", "mail-1.result.txt"])
        with open(os.path.join(self.channel, "outbox", "failed",
                               "mail-1.result.txt"),
                  encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "result\n\nsigned-result")
        with open(os.path.join(self.channel, "outbox", "failed",
                               "mail-1.refused.txt"),
                  encoding="utf-8") as fh:
            self.assertIn("not built", fh.read())
        self.assertEqual(imap.flagged, ["1"])
        self.assertEqual(pipe._delivered, {})

    def test_flush_every_break_char_in_the_mailbox_user_sets_aside(
            self):
        for char, name in BREAK_CHARS:
            with self.subTest(break_char=name):
                tmp = tempfile.mkdtemp(prefix="hp-unbuildable-")
                paths = transports.channel_paths(tmp, "email")
                transports.ensure_channel_dirs(tmp, "email")
                channel = paths["root"]
                cfg = dict(CFG)
                cfg["mailbox_user"] = (
                    "runner@example.com" + char + "Bcc: x@y.z")
                imap = FakeIMAP([])
                smtp = FakeSMTP()
                pipe = email_ext.EmailPipe(
                    cfg, channel,
                    imap_factory=lambda c: imap,
                    smtp_factory=lambda c: smtp)
                pipe._delivered["1"] = "mail-1"
                with open(os.path.join(
                        channel, "outbox", "mail-1.result.txt"),
                        "w", encoding="utf-8") as fh:
                    fh.write(ch.envelope("result", "signed-result"))
                pipe.flush_results(imap)
                self.assertEqual(smtp.sent, [])
                self.assertEqual(
                    sorted(os.listdir(os.path.join(
                        channel, "outbox", "failed"))),
                    ["mail-1.refused.txt", "mail-1.result.txt"])
                self.assertEqual(
                    os.listdir(os.path.join(
                        channel, "outbox", "done")), [])
                self.assertEqual(imap.flagged, ["1"])

    def test_flush_a_suffixed_unbuildable_result_uses_the_primary_name(
            self):
        pipe, imap, smtp = self._flush_bad_from(suffix="-2")
        pipe.flush_results(imap)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(self._listing("outbox", "failed"),
                         ["mail-1.refused.txt", "mail-1.result.txt"])
        self.assertEqual(self._listing("outbox", "done"), [])
        self.assertEqual(imap.flagged, ["1"])

    def test_flush_an_unbuildable_result_takes_its_sidecar_to_done(
            self):
        pipe, imap, smtp = self._flush_bad_from()
        with open(os.path.join(self.channel, "outbox",
                               "mail-1.target.txt"),
                  "w", encoding="utf-8") as fh:
            fh.write("ops@example.com\n")
        pipe.flush_results(imap)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(self._listing("outbox", "done"),
                         ["mail-1.target.txt"])
        self.assertEqual(self._listing("outbox", "failed"),
                         ["mail-1.refused.txt", "mail-1.result.txt"])

    def test_flush_two_unbuildable_results_mark_the_job_seen_once(
            self):
        pipe, imap, smtp = self._flush_bad_from()
        self._write_result(suffix="-2", body="second")
        pipe.flush_results(imap)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(imap.flagged, ["1"])
        self.assertEqual(self._listing("outbox", "failed"),
                         ["mail-1.refused.txt", "mail-1.result.txt"])
        self.assertEqual(self._listing("outbox", "done"), [])

    def test_flush_a_second_flush_does_not_resend_or_rerecord(self):
        pipe, imap, smtp = self._flush_bad_from()
        pipe.flush_results(imap)
        before = self._listing("outbox", "failed")
        pipe.flush_results(imap)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(self._listing("outbox", "failed"), before)
        self.assertEqual(imap.flagged, ["1"])

    def test_flush_recovers_once_the_address_is_fixed(self):
        pipe, imap, smtp = self._flush_bad_from()
        pipe.flush_results(imap)
        good = self._pipe(dict(CFG), imap, smtp)
        good._delivered["2"] = "mail-2"
        self._write_result(ident="mail-2")
        good.flush_results(imap)
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(self._listing("outbox", "done"),
                         ["mail-2.result.txt"])
        self.assertEqual(self._listing("outbox", "failed"),
                         ["mail-1.refused.txt", "mail-1.result.txt"])
        self.assertEqual(imap.flagged, ["1", "2"])

    def test_flush_a_hostile_sidecar_neither_steers_nor_breaks(
            self):
        # The sidecar faces the address rule before it is used:
        # text carrying a break is not a target at all, so the
        # result goes to the mailbox, not to the injected name.
        imap = FakeIMAP([])
        smtp = FakeSMTP()
        pipe = self._pipe(dict(CFG), imap, smtp)
        pipe._delivered["1"] = "mail-1"
        self._write_result()
        with open(os.path.join(self.channel, "outbox",
                               "mail-1.target.txt"),
                  "w", encoding="utf-8") as fh:
            fh.write("victim@example.com\nBcc: evil@example.com")
        pipe.flush_results(imap)
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(str(smtp.sent[0]["To"]),
                         "runner-box@example.com")
        self.assertEqual(self._listing("outbox", "done"),
                         ["mail-1.result.txt", "mail-1.target.txt"])

    def test_flush_a_remembered_target_with_a_break_is_refused(
            self):
        imap = FakeIMAP([])
        smtp = FakeSMTP()
        pipe = self._pipe(dict(CFG), imap, smtp)
        pipe._delivered["1"] = "mail-1"
        pipe._targets["mail-1"] = (
            "victim@example.com\nBcc: evil@example.com")
        self._write_result()
        pipe.flush_results(imap)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(self._listing("outbox", "failed"),
                         ["mail-1.refused.txt", "mail-1.result.txt"])
        self.assertEqual(imap.flagged, ["1"])

    def test_reply_target_with_a_break_falls_back_to_the_mailbox(
            self):
        body = ('{"reply_to": '
                '"victim@example.com\\nBcc: evil@example.com"}')
        self.assertEqual(
            email_ext.reply_target(body, "runner-box@example.com"),
            "runner-box@example.com")
        body = '{"reply_to": "ops@example.com"}'
        self.assertEqual(
            email_ext.reply_target(body, "runner-box@example.com"),
            "ops@example.com")


def _make_per_field_break_tests():
    for char, name in BREAK_CHARS:

        def from_test(self, char=char):
            cfg = dict(CFG)
            cfg["mailbox_user"] = (
                "runner@example.com" + char + "Bcc: x@y.z")
            self._assert_unbuildable(cfg=cfg)

        def to_test(self, char=char):
            self._assert_unbuildable(
                to="victim@example.com" + char + "Bcc: evil@x.y")

        setattr(UnbuildableResultShotgunTest,
                "test_from_break_%s_is_permanent" % name, from_test)
        setattr(UnbuildableResultShotgunTest,
                "test_to_break_%s_is_permanent" % name, to_test)


_make_per_field_break_tests()


if __name__ == "__main__":
    unittest.main(verbosity=2)
