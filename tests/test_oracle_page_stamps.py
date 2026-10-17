#!/usr/bin/env python3
"""Oracle chat page: timestamps and chat alignment (2026-10-16).

Field request from the testing loop: a simple answer took over two
minutes and there was no way to document the timing from a photo or
screenshot -- nothing in the page said when a question was sent,
when the thinking started, or when the answer landed. Every bubble
now carries a clock stamp, the Working bubble is stamped with its
start time, and the answer is stamped with its arrival time and the
total wait ("took 2m 12s"). His messages are right-aligned, the
Oracle's stay on the left, like a normal chat.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402


class PageStampsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = R.oracle_page("tok", "llama3.2:3b", True)

    def test_user_messages_right_aligned_oracle_left(self):
        # His bubbles sit on the right, the Oracle's on the left,
        # each a real bubble with its own surface.
        self.assertIn("align-self: flex-end", self.page)
        self.assertIn("align-self: flex-start", self.page)
        self.assertIn("background: #1e3a5f", self.page)
        self.assertIn("background: #17191f", self.page)
        self.assertNotIn("Georgia", self.page)

    def test_every_bubble_carries_a_clock_stamp(self):
        self.assertIn("function stamp(", self.page)
        self.assertIn('add("You", text, "you", stamp(', self.page)
        self.assertIn('"oracle working", stamp(new Date(t0)))',
                      self.page)

    def test_the_answer_is_stamped_with_its_wait(self):
        self.assertIn("function took(", self.page)
        self.assertIn("took ", self.page)
        self.assertIn('add("Oracle", data.answer, "oracle", done)',
                      self.page)

    def test_the_working_pulse_still_ticks(self):
        # The stamp work must not break the elapsed/step pulse.
        self.assertIn("Current step:", self.page)
        self.assertIn("The answer replaces this line.", self.page)
        self.assertIn("pending.childNodes[1]", self.page)


if __name__ == "__main__":
    unittest.main()
