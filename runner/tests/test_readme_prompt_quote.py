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

The owner rewrote the prompt again at 11:18 PM on
19-Nov-2026: the mailbox line now reads "Runner mailbox is
your@email.com", the generic form. The pin's job is
agreement between README.md and the AGENTS.md quote, not a
fixed address, so this suite no longer forbids the string
"your@email.com" in AGENTS.md: it is the current line the
owner chose, and the agreement test above is what holds it
in sync. The older prompt lines that no version of the
current prompt carries ("make one up for me", "My mailbox
is") stay forbidden.

The owner rewrote the prompt again on 20-Nov-2026: the
Shared Secret line came out of the prompt entirely, because
the secret agents notes in AGENTS.md now carry the shared
secret and the reply_to self default themselves, so the
prompt no longer has to say it. The block stands at 3
lines, and the block pin below holds exactly those.

The owner rewrote the prompt again on 27-Nov-2026: the
first line now reads "I installed the pigeon-home.ai
runner!" (the owner changed the casing of that first
line from the capital H form, pigeon-Home.ai, to the
lowercase pigeon-home.ai form, and the pin below
follows the lowercase line), the mailbox line is back
to "My mailbox is
your@email.com", and the clock line ends ", do you like
my desktop background?". The words "careful prompt" no
longer stand in README.md, so the block is now located
as the first fenced block at the top of the file. The
AGENTS.md quote is synced to the current mailbox line,
"Runner mailbox is" joins the forbidden list as a line
the current prompt no longer carries, and "My mailbox
is" leaves that list, because it is the current line
again.
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
    fence_open = text.index("```") + 3
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
        self.assertEqual(
            [
                "I installed the pigeon-home.ai runner!",
                "My mailbox is your@email.com",
                "Retrieve the system clock and display it, do you like my desktop background?",
            ],
            lines,
        )

    def test_agents_quotes_the_current_mailbox_line(self):
        agents = read("AGENTS.md")
        match = re.search(r'whose mailbox line reads: "([^"]+)"', agents)
        self.assertIsNotNone(match, "AGENTS.md no longer quotes the mailbox line")
        self.assertEqual(readme_mailbox_line(), match.group(1))

    def test_agents_carries_no_old_prompt_lines(self):
        agents = read("AGENTS.md")
        self.assertNotIn("make one up for me", agents)
        self.assertNotIn("Runner mailbox is", agents)


if __name__ == "__main__":
    unittest.main()
