# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""AGENTS.md quotes the README try-it prompt; the quote must match.

The "Where the answer goes: reply to self, by default" note in
AGENTS.md explains the reply_to default by quoting the mailbox
line of the careful prompt at the top of README.md. The owner
rewrote that prompt on 19-Nov-2026: the mailbox line became a
pigeon-home.ai address, the shared secret is found in the
mailbox rather than stated in the prompt, and the prompt
itself carries the reply to self. The quote in AGENTS.md still
carried the old line ("My mailbox is your@email.com").

README.md is the owner's own current text and wins. This test
pins the quote in AGENTS.md to the mailbox line README.md
carries, so the next rewrite of the prompt fails here until
the quote is synced, and pins that the old prompt lines do
not stand quoted in AGENTS.md.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def readme_prompt_lines():
    """The lines of the fenced try-it prompt at the top of README.md."""
    text = read("README.md")
    marker = "careful prompt"
    start = text.index(marker)
    fence_open = text.index("```", start) + 3
    fence_close = text.index("```", fence_open)
    block = text[fence_open:fence_close]
    return [line for line in block.splitlines() if line.strip()]


def readme_mailbox_line():
    for line in readme_prompt_lines():
        if "mailbox" in line:
            return line
    raise AssertionError("README.md prompt carries no mailbox line")


class ReadmePromptQuoteTest(unittest.TestCase):

    def test_readme_prompt_block_stands(self):
        lines = readme_prompt_lines()
        self.assertEqual("Run a pigeon-home.ai job", lines[0])
        self.assertIn("Find the Shared Secret in my mailbox and reply_to self", lines)
        self.assertEqual("Retrieve the system clock and display it", lines[-1])

    def test_agents_quotes_the_current_mailbox_line(self):
        agents = read("AGENTS.md")
        match = re.search(r'whose mailbox line reads: "([^"]+)"', agents)
        self.assertIsNotNone(match, "AGENTS.md no longer quotes the mailbox line")
        self.assertEqual(readme_mailbox_line(), match.group(1))

    def test_agents_carries_no_old_prompt_lines(self):
        agents = read("AGENTS.md")
        self.assertNotIn("your@email.com", agents)
        self.assertNotIn("make one up for me", agents)
        self.assertNotIn("My mailbox is", agents)


if __name__ == "__main__":
    unittest.main()
