"""Live docs carry no provider name at all.

DRU's directive (2026-10-18, superseding the same day's
sanctioned-mentions regime): the term for the recommended mail
provider appears in NO live document -- not in examples, not in
hostnames, not in walkthroughs. The transport is email over
IMAP/SMTP with any provider; the concrete defaults live in code
(the installer's constants and config.example.json), which is
where a reader who needs them finds them. His manual passes kept
being stepped on by later edits, so this guard is the sift: any
live doc that reintroduces the term fails the build.

Dated records are exempt by design and stay exempt: CHANGELOG.md,
docs/archive/ and docs/reports/ (AGENTS.md rule 6) describe what
was true when they were written, and a report may name this test
by its file name.

One line is exempt by name: the author address in the front matter of
the Internet-Draft sources (docs/ietf/draft-slutsky-*.md). An RFC
prints its author's address, and the conductor chose this one for the
drafts (29-OCT 10:00PM PDT: "I think Slutsky 5544@gmail.com will be
best." / "No space."). It names an author, not a recommended provider.
"""

import os
import re
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


_TERM = re.compile(r"gmail", re.IGNORECASE)
_AUTHOR_LINE = 'email: "slutsky5544@gmail.com"'



def _live_docs():
    root = _root()
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        parts = set(rel.split(os.sep))
        if ".git" in parts or "__pycache__" in parts:
            dirnames[:] = []
            continue
        if ("archive" in parts or "reports" in parts) and "docs" in parts:
            dirnames[:] = []
            continue
        for name in filenames:
            if name.endswith(".md") and name != "CHANGELOG.md":
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def _hits(path):
    draft = (os.path.basename(os.path.dirname(path)) == "ietf"
             and os.path.basename(path).startswith("draft-slutsky-"))
    with open(path, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh.read().splitlines()
                if _TERM.search(ln)
                and not (draft and ln.strip() == _AUTHOR_LINE)]


class NoProviderNameInLiveDocsTest(unittest.TestCase):
    def test_scan_is_not_vacuous(self):
        docs = _live_docs()
        self.assertGreater(len(docs), 15)
        names = {os.path.basename(p) for p in docs}
        for expected in ("README.md", "INSTALL.md", "AGENTS.md",
                         "PROTOCOL.md", "RUNBOOK.md"):
            self.assertIn(expected, names)

    def test_mutmut_copies_the_root_manuals(self):
        # mutmut runs the suite from mutants/, which contains the
        # runner package plus also_copy. The scan above is rooted
        # there, so a manual missing from also_copy is invisible
        # and the vacuous check fails the baseline (tag v3.7.29).
        with open(os.path.join(_root(), "pyproject.toml"),
                  encoding="utf-8") as fh:
            text = fh.read()
        m = re.search(r"also_copy\s*=\s*\[(.*?)\]", text, re.S)
        self.assertIsNotNone(m, "no also_copy list in pyproject.toml")
        body = m.group(1)
        for name in ("README.md", "INSTALL.md", "AGENTS.md",
                     "PROTOCOL.md"):
            self.assertIn('"%s"' % name, body,
                          "mutmut will not copy %s" % name)

    def test_no_live_doc_names_the_provider(self):
        offenders = {}
        for path in _live_docs():
            hits = _hits(path)
            if hits:
                offenders[os.path.relpath(path, _root())] = hits
        self.assertEqual({}, offenders,
                         "live docs must not name the mail provider; "
                         "say mailbox / mail account / provider instead: "
                         "%s" % (offenders,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
