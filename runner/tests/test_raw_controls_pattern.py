#!/usr/bin/env python3
"""The raw-controls class in runner/wire/verify.py, spelled out.

_RAW_CONTROLS strips the raw control characters a mail transport
may insert before the verifier checks a cleaned form. It used to
spell its set with 2 ranges; code scanning alert 48 read that
spelling as an overly permissive range, and the class is now
written out character by character. The set is the point, and it
did not move: every C0 control except the tab, 31 characters,
which is exactly the set _strip_controls drops.

These tests hold the new spelling to the set, differentially:
the pattern's verdict against an arithmetic statement of the
set, on every character a byte can name, on every string of 1
or 2 such characters, on bookended bodies (each control at the
front and at the back, and in runs), and on seeded random
strings; and the pattern against _strip_controls, whose
agreement with it is the contract test_opener_cost already pins
at the search.
"""
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.wire import verify as VERIFY  # noqa: E402

PATTERN = VERIFY._RAW_CONTROLS
CONTROLS = frozenset(chr(c) for c in range(0x20) if c != 0x09)
TAB = chr(0x09)


def reference_strip(text):
    """The set, stated arithmetically: drop exactly CONTROLS."""
    return "".join(c for c in text if c not in CONTROLS)


class RawControlsPatternTest(unittest.TestCase):

    def test_the_set_is_31_and_keeps_the_tab(self):
        self.assertEqual(len(CONTROLS), 31)
        self.assertNotIn(TAB, CONTROLS)
        self.assertIsNone(PATTERN.match(TAB))
        self.assertIsNone(PATTERN.match(chr(0x7F)))
        self.assertIsNone(PATTERN.match(" "))

    def test_every_character_a_byte_can_name(self):
        for value in range(256):
            char = chr(value)
            if char in CONTROLS:
                self.assertIsNotNone(PATTERN.match(char), value)
            else:
                self.assertIsNone(PATTERN.match(char), value)

    def test_no_character_above_the_bytes_matches(self):
        for value in list(range(256, 0x10000)) + [0x10000, 0x10FFFF]:
            self.assertIsNone(PATTERN.match(chr(value)), value)

    def test_sub_agrees_on_every_1_and_2_byte_string(self):
        chars = [chr(v) for v in range(256)]
        for first in chars:
            self.assertEqual(PATTERN.sub("", first),
                             reference_strip(first))
            for second in chars:
                text = first + second
                self.assertEqual(PATTERN.sub("", text),
                                 reference_strip(text))

    def test_sub_agrees_on_bookended_bodies(self):
        body = '{"k":"a' + "c" * 40 + '"}'
        for char in CONTROLS:
            for text in (char + body, body + char,
                         char * 10 + body + char * 10,
                         char + body + char):
                self.assertEqual(PATTERN.sub("", text),
                                 reference_strip(text))
                self.assertEqual(PATTERN.sub("", text),
                                 VERIFY._strip_controls(text))

    def test_sub_agrees_on_seeded_random_strings(self):
        rng = random.Random(48)
        for span in (40, 256):
            for _ in range(400):
                text = "".join(chr(rng.randrange(0, span))
                               for _ in range(60))
                self.assertEqual(PATTERN.sub("", text),
                                 reference_strip(text))
                self.assertEqual(PATTERN.sub("", text),
                                 VERIFY._strip_controls(text))


if __name__ == "__main__":
    unittest.main()
