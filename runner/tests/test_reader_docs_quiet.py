# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""The reader's documentation carries no trace of how the project is
run. The manuals at the root and the guides under docs/use, extend,
security, oracle, design and ietf are for someone running or
extending the runner; how the seats work -- question numbers, seat
names, stamps' roles, campaign names, standing orders -- lives in
docs/project, docs/archive, docs/reports and docs/seats (the questions
file, status.txt and the forum). A reference that drifts into a
reader's page fails here, with the line.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

READER_FILES = ["README.md", "INSTALL.md", "SECURITY.md", "PROTOCOL.md", "FAQ.md",
                "ENTERPRISE.md", "docs/CONTRIBUTING.md"]
READER_DIRS = ["docs/use", "docs/extend", "docs/security", "docs/oracle",
               "docs/design", "docs/ietf"]
# The seats' own files under a reader directory.
NOT_READER = set()   # the seats' files live in docs/seats, outside the reader's folders

# What a seat says and a reader should not meet.
PROCESS = re.compile(
    r"\bQ\d{1,3}\b"                      # a question number
    r"|\bthe (desk|conductor|hosting seat|review seat|audit seat|questions desk)\b"
    r"|\bconductor\b"
    r"|\b(de_dust2?|de_aztec|blueMonday)\b"
    r"|\(M\d+\b"                         # a hardening-milestone label
    r"|\bstanding orders\b"
    r"|\btelephone-pole\b"
    r"|\bquestions\.md\b|\.com\.chat\b"
    r"|(?<!-)\bcampaign\b(?!-)"           # the word, not a file named campaign-x or x-campaign
)
# Lines a reader is meant to see as they are.
ALLOWED = (
    re.compile(r"<!--\s*Agent-(Chat-)?Stamp:"),        # the stamp header, invisible
    re.compile(r"^Works with .*any assistant"),        # the README's banner
)


def reader_paths():
    out = [os.path.join(ROOT, f) for f in READER_FILES]
    for d in READER_DIRS:
        for folder, _dirs, files in os.walk(os.path.join(ROOT, d)):
            for name in files:
                if name.endswith(".md"):
                    out.append(os.path.join(folder, name))
    return [p for p in out if os.path.exists(p)
            and os.path.relpath(p, ROOT).replace(os.sep, "/") not in NOT_READER]


class ReaderDocsQuietTest(unittest.TestCase):

    def test_no_process_reference_in_a_reader_s_page(self):
        bad = []
        for path in reader_paths():
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    if any(a.search(line) for a in ALLOWED):
                        continue
                    m = PROCESS.search(line)
                    if m:
                        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
                        bad.append(f"{rel}:{n}: {m.group(0)!r} in {line.strip()[:80]!r}")
        self.assertEqual([], bad, "process talk in a reader's page:\n  " + "\n  ".join(bad))

    def test_docs_use_holds_only_the_reader_s_pages(self):
        # The seats' files (the questions file, status.txt, the forum,
        # a muster hold) live in docs/seats. A job on a rig that still
        # writes to the old path puts a file here, and this names it.
        stray = sorted(n for n in os.listdir(os.path.join(ROOT, "docs", "use"))
                       if not n.endswith(".md"))
        self.assertEqual([], stray, "not a reader's page under docs/use")


if __name__ == "__main__":
    unittest.main()
