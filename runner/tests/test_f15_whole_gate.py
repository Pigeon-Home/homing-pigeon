"""Finding F15, generalized: the whole gate answers deep nesting.

F15 closed 3 shapes whose nesting made the gate raise and
leave the message unmarked. The census and the measurement
stand in docs/infrastructure-documents/project/
f15-recursion-generalization-supposition-2026-11-27.md: every
reader in front of the signature already had an answer except
one, the chain door, whose body read caught only
JobCryptoError and ValueError around a second parse of the
raw mail. A chain mail nested at 979 and 980 (the band
between the gate's parse and the door's, on the measuring
driver's stack) raised RecursionError out of the gate,
unmarked. These tests pin the invariant the fix stands on:
at every count, at every door, the gate returns an answer
and the message is marked. The counts are derived from
ranges, never written out, and the band's exact address is
stack-relative, so no test names it: the range is swept.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner import runner as R  # noqa: E402
from runner.ops import chain as CHAIN_OPS  # noqa: E402


class _Imap:
    def __init__(self):
        self.stored = []

    def store(self, seq, op, flag):
        self.stored.append(seq)
        return "OK", []


class _Smtp:
    def send_message(self, msg):
        pass


def _nested_text(count, innermost="{}"):
    """A text body wrapped in `count` multipart layers."""
    text = ("Content-Type: text/plain; charset=utf-8\r\n"
            "Content-Transfer-Encoding: 8bit\r\n\r\n" + innermost)
    for level in range(count):
        text = ('Content-Type: multipart/mixed; boundary="b%d"\r\n'
                "\r\n--b%d\r\n%s\r\n--b%d--\r\n"
                % (level, level, text, level))
    return text


def _mail(subject, text):
    return ("Subject: %s\r\nFrom: si@example.com\r\n"
            "MIME-Version: 1.0\r\n" % subject + text).encode("utf-8")


def _nested_mail(subject, count, innermost="{}"):
    return _mail(subject, _nested_text(count, innermost))


def _rfc822_mail(subject, count):
    """A mail nested `count` deep in message/rfc822 parts."""
    body = "Content-Type: text/plain\r\n\r\n{}"
    for _level in range(count):
        body = "Content-Type: message/rfc822\r\n\r\n" + body
    return _mail(subject, body)


def _mixed_mail(subject, count):
    """Nesting that alternates multipart and message/rfc822."""
    text = "Content-Type: text/plain\r\n\r\n{}"
    for level in range(count):
        if level % 2:
            text = "Content-Type: message/rfc822\r\n\r\n" + text
        else:
            text = ('Content-Type: multipart/mixed; boundary="m%d"\r\n'
                    "\r\n--m%d\r\n%s\r\n--m%d--\r\n"
                    % (level, level, text, level))
    return _mail(subject, text)


def _middle_nested_mail(subject, count):
    """3 parts in a row; the middle one carries the nesting."""
    top = ('Content-Type: multipart/mixed; boundary="top"\r\n\r\n'
           "--top\r\nContent-Type: text/plain\r\n\r\nbefore\r\n"
           "--top\r\n%s\r\n"
           "--top\r\nContent-Type: text/plain\r\n\r\nafter\r\n"
           "--top--\r\n" % _nested_text(count))
    return _mail(subject, top)


SUBJECTS = {
    "job": "[HOMING-PIGEON] job m1",
    "chain": "[HOMING-PIGEON] chain m1",
    "cancel": "[HOMING-PIGEON] cancel m1",
    "query": "[HOMING-PIGEON] query m1",
    "board": "[HOMING-PIGEON] task_submit m1",
}

# The band and the first parse's own limit both live inside
# this range on any stack the gate is driven from; below it
# every parse succeeds and above it the first parse raises,
# so a decided-at-every-count sweep over it covers the hole
# wherever the running stack puts it.
BAND = range(950, 1021)


class _Gate(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-f15-")
        self.cfg = {"mailbox_user": "t@example.com",
                    "shared_secret": "x" * 64, "board": object()}
        self.lines = []

    def drive(self, raw):
        """One mail at the real gate: (raised, marked)."""
        imap = _Imap()
        raised = None
        with mock.patch.object(R, "log",
                               lambda msg, level="INFO":
                               self.lines.append(msg)), \
                mock.patch.object(R, "vlog", lambda *a, **k: None), \
                mock.patch.object(R, "send_mail",
                                  lambda *a, **k: None):
            try:
                R.handle_mail(self.cfg, imap, _Smtp(), 7, raw,
                              self.base, {}, {}, None, None)
            except Exception as e:  # the test names what escaped
                raised = e
        return raised, 7 in imap.stored


class ChainBandTest(_Gate):
    def test_chain_mail_decided_at_every_count(self):
        for count in BAND:
            with self.subTest(count=count):
                raised, marked = self.drive(
                    _nested_mail(SUBJECTS["chain"], count))
                self.assertIsNone(raised)
                self.assertTrue(marked)


class EveryDoorTest(_Gate):
    def test_doors_decided_across_the_range(self):
        for door in ("job", "cancel", "query", "board"):
            for count in range(BAND.start, BAND.stop, 4):
                with self.subTest(door=door, count=count):
                    raised, marked = self.drive(
                        _nested_mail(SUBJECTS[door], count))
                    self.assertIsNone(raised)
                    self.assertTrue(marked)


class ChainDoorDirectTest(_Gate):
    def _drive_door(self, raw, subject=SUBJECTS["chain"]):
        imap = _Imap()
        with mock.patch.object(R, "log",
                               lambda msg, level="INFO":
                               self.lines.append(msg)), \
                mock.patch.object(R, "vlog", lambda *a, **k: None):
            handled = CHAIN_OPS.handle_chain_mail(
                self.cfg, imap, _Smtp(), 7, raw, subject, {},
                None, self.base, {})
        return handled, 7 in imap.stored

    def test_the_door_answers_at_every_count(self):
        counts = list(range(BAND.start, BAND.stop, 2)) + [1200, 3000]
        for count in counts:
            with self.subTest(count=count):
                handled, marked = self._drive_door(
                    _nested_mail(SUBJECTS["chain"], count))
                self.assertTrue(handled)
                self.assertTrue(marked)

    def test_the_door_answers_a_reader_raise_in_its_own_words(self):
        with mock.patch.object(R, "get_text_body",
                               side_effect=RecursionError):
            handled, marked = self._drive_door(
                _nested_mail(SUBJECTS["chain"], 3))
        self.assertTrue(handled)
        self.assertTrue(marked)
        self.assertTrue(any("shape could not be read" in line
                            for line in self.lines))

    def test_a_bad_signature_is_still_refused_as_one(self):
        handled, marked = self._drive_door(
            _nested_mail(SUBJECTS["chain"], 3))
        self.assertTrue(handled)
        self.assertTrue(marked)
        self.assertTrue(any("bad signature" in line
                            for line in self.lines))
        self.assertFalse(any("shape could not be read" in line
                             for line in self.lines))


class DispatchGuardTest(_Gate):
    def test_a_dispatch_raise_gets_the_f15_answer(self):
        with mock.patch.object(R, "_early_dispatch",
                               side_effect=RecursionError):
            raised, marked = self.drive(
                _nested_mail(SUBJECTS["job"], 3))
        self.assertIsNone(raised)
        self.assertTrue(marked)
        self.assertTrue(any("the mail's shape could not be read"
                            in line for line in self.lines))

    def test_a_dispatch_raise_with_a_stopped_box_leaves_the_mail(self):
        with mock.patch.object(R, "_early_dispatch",
                               side_effect=RecursionError), \
                mock.patch.object(R._panic, "fired",
                                  side_effect=[False, True]):
            raised, marked = self.drive(
                _nested_mail(SUBJECTS["job"], 3))
        self.assertIsNone(raised)
        self.assertFalse(marked)

    def test_other_dispatch_errors_still_raise(self):
        with mock.patch.object(R, "_early_dispatch",
                               side_effect=ValueError("bad")):
            raised, _marked = self.drive(
                _nested_mail(SUBJECTS["job"], 3))
        self.assertIsInstance(raised, ValueError)


class ShapeFamiliesTest(_Gate):
    def test_nesting_in_a_middle_part(self):
        for door in ("chain", "job"):
            for count in (975, 979, 980, 981, 1200):
                with self.subTest(door=door, count=count):
                    raised, marked = self.drive(
                        _middle_nested_mail(SUBJECTS[door], count))
                    self.assertIsNone(raised)
                    self.assertTrue(marked)

    def test_rfc822_nesting(self):
        for door in ("chain", "job"):
            for count in (400, 500, 600, 800, 1000):
                with self.subTest(door=door, count=count):
                    raised, marked = self.drive(
                        _rfc822_mail(SUBJECTS[door], count))
                    self.assertIsNone(raised)
                    self.assertTrue(marked)

    def test_mixed_nesting(self):
        for count in (600, 900, 990):
            with self.subTest(count=count):
                raised, marked = self.drive(
                    _mixed_mail(SUBJECTS["chain"], count))
                self.assertIsNone(raised)
                self.assertTrue(marked)

    def test_bookended_nesting(self):
        symbols = "".join(chr(c) for c in range(33, 127)
                          if not chr(c).isalnum())
        inner = symbols + "{}" + symbols
        for count in (979, 980, 1200):
            with self.subTest(count=count):
                raised, marked = self.drive(_nested_mail(
                    SUBJECTS["chain"], count, innermost=inner))
                self.assertIsNone(raised)
                self.assertTrue(marked)


class FirstParseTest(_Gate):
    def test_deep_parts_are_decided_at_the_first_parse(self):
        for count in (1200, 3000):
            with self.subTest(count=count):
                self.lines = []
                raised, marked = self.drive(
                    _nested_mail(SUBJECTS["job"], count))
                self.assertIsNone(raised)
                self.assertTrue(marked)
                self.assertTrue(any(
                    "the mail's shape could not be read" in line
                    for line in self.lines))


if __name__ == "__main__":
    unittest.main()
