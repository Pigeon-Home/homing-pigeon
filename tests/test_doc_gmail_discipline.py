"""Docs name Gmail only where Gmail is the concrete fact.

The transport is email (IMAP/SMTP, any provider). Gmail is the
recommended easy path for the runner's dedicated mailbox, the cloud
connector's current identity, and the hostnames the installer
writes by default -- and the live docs may name it only for those
specific things (owner's call, 2026-10-18; audit in the goal
workspace, gmail-doc-audit.md). Everywhere else the docs say
"mailbox" / "mail account" / "mailbox provider".

This guard keeps the discipline from rotting: PROTOCOL.md (the
specification of record), TRANSPORTS.md, SECURITY.md and FUTURE.md
must stay provider-free, and in the remaining live docs every
Gmail-mentioning line must match one of the sanctioned shapes
below. Adding an offhand mention fails here; adding a genuinely
specific one means extending SANCTIONED with its shape, in the
open, in the same commit.
"""

import os
import re
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


# Live docs that must not mention Gmail at all.
PROVIDER_FREE = ("PROTOCOL.md", "TRANSPORTS.md", "SECURITY.md",
                 "FUTURE.md")

# Live docs that may mention Gmail in sanctioned shapes only.
SANCTIONED_FILES = ("README.md", "RUNBOOK.md", "INSTALL.md",
                    "AGENTS.md")

# Each pattern describes one specific, factual use:
SANCTIONED = (
    # Example addresses (your-runner@gmail.com) and the installer's
    # default hostnames (imap.gmail.com:993, smtp.gmail.com:587).
    re.compile(r"gmail\.com"),
    # The cloud connector's current identity, stated as a current
    # fact in AGENTS.md.
    re.compile(r"currently Gmail"),
    # The app-password walkthrough addresses the runner's account at
    # the provider the walkthrough documents.
    re.compile(r"runner's Gmail account"),
    # INSTALL.md describes the setup wizard's actual prompt.
    re.compile(r"Gmail app password"),
    # README's recommended-account walkthrough.
    re.compile(r"dedicated\*\* Gmail account"),
)


def _gmail_lines(name):
    with open(os.path.join(_root(), name), encoding="utf-8") as fh:
        return [ln for ln in fh.read().splitlines()
                if "gmail" in ln.lower()]


class ProviderFreeDocsTest(unittest.TestCase):
    def test_provider_free_docs_stay_provider_free(self):
        for name in PROVIDER_FREE:
            self.assertEqual([], _gmail_lines(name),
                             "%s must not mention Gmail" % name)


class SanctionedMentionsTest(unittest.TestCase):
    def test_scan_is_not_vacuous(self):
        # If the docs move or empty out, this guard must fail loudly
        # rather than pass over nothing.
        for name in SANCTIONED_FILES:
            self.assertTrue(_gmail_lines(name),
                            "no Gmail lines found in %s -- has the "
                            "file moved?" % name)

    def test_every_mention_matches_a_sanctioned_shape(self):
        for name in SANCTIONED_FILES:
            for line in _gmail_lines(name):
                self.assertTrue(
                    any(p.search(line) for p in SANCTIONED),
                    "%s has an unsanctioned Gmail mention: %s"
                    % (name, line.strip()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
