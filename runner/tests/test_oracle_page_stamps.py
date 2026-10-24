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

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


class PageWindowTest(unittest.TestCase):
    """A long Oracle investigation must not blow the page.

    The field loop is many turns. The page used to keep every
    bubble forever. It now keeps the last 40 and cuts a single
    bubble at 4000 characters. The full exchange stays in
    oracle-chat.jsonl.
    """

    def test_the_page_script_is_one_string(self):
        """A real newline in the cut-message killed Send.

        The script did not parse, so the form never attached and
        the button did nothing. The cut notice stays one JS string.
        """
        page = R.oracle_page("tok", "llama3.2:3b", True)
        js = page[page.find("<script>") + 8:page.find("</script>")]
        fit = js[js.find("function fit"):js.find("function add")]
        self.assertNotIn("\n…", fit)
        self.assertIn("\\n…", fit)

    def test_the_page_windows_itself(self):
        page = R.oracle_page("tok", "llama3.2:3b", True)
        self.assertIn("const KEEP = 40", page)
        self.assertIn("const BUBBLE = 4000", page)
        self.assertIn("function trimLog()", page)
        self.assertIn("function fit(text)", page)
        self.assertIn("oracle-chat.jsonl", page)
        self.assertIn("trimLog();", page)


class OraclePageScriptTest(unittest.TestCase):
    """The page script must parse. A raw newline inside a JS string
    used to make the whole script a SyntaxError, so the send handler
    never attached and pressing Send did nothing.
    """

    def test_oracle_page_script_parses(self):
        import subprocess
        from runner.runner import oracle_page
        page = oracle_page("tok", "m", True)
        start = page.find("<script>")
        end = page.find("</script>")
        self.assertGreater(start, 0)
        self.assertGreater(end, start)
        js = page[start + 8:end]
        # Must not contain a raw newline inside a double-quoted string
        # that would break the parser. node --check is the authority.
        r = subprocess.run(
            ["node", "--check", "-"],
            input=js.encode(),
            capture_output=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr.decode())
