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
docs/archive/ and docs/steady/reports/ (AGENTS.md rule 6) describe
what
was true when they were written, and a report may name this test
by its file name.

One line is exempt by name: the author address in the front matter of
the Internet-Draft sources (the draft-slutsky-*.md files under
docs/ietf, in each draft's own folder since the per-draft layout). An RFC
prints its author's address, and the conductor chose this one for the
drafts (29-OCT 10:00PM PDT: "I think Slutsky 5544@gmail.com will be
best." / "No space."). It names an author, not a recommended provider.

The same rationale covers one more line, exempted the same narrow way
(2026-11-15, the 3.16.26.24 gate): the Contact line of the hosted
sign-in service's privacy policy (docs/steady/project/privacy-policy.md)
carries the operator's own address, because a privacy policy must say
where questions about it go. That line names the operator, not a
recommended provider. The exemption is scoped to that file and to
lines carrying that address: any other mention of the term in that
file, and the address itself in any other live doc, still fails.
"""

import os
import re
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


_TERM = re.compile(r"gmail", re.IGNORECASE)
_AUTHOR_LINE = 'email: "slutsky5544@gmail.com"'
_OPERATOR_ADDRESS = "slutsky5544@gmail.com"
_PRIVACY_POLICY_PARTS = ("docs", "steady", "project", "privacy-policy.md")



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
            # The changelog and the dated records the reorganization
            # moved out of docs/archive/ (the connector round-trip
            # capture, the docker record) are records, not live
            # docs: exempt by name, as the changelog always was.
            if name.endswith(".md") and name not in (
                    "CHANGELOG.md", "changelog.md",
                    "connector-roundtrip.md", "docker.md"):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def _is_privacy_policy(path):
    parts = tuple(p for p in path.replace("\\", "/").split("/") if p)
    return parts[-4:] == _PRIVACY_POLICY_PARTS


def _exempt(path, line):
    if ("ietf" in path.split(os.sep)
            and os.path.basename(path).startswith("draft-slutsky-")
            and line == _AUTHOR_LINE):
        return True
    # The privacy policy's contact line names the operator, the same
    # rationale as the draft author line above; scoped to that file
    # and to lines carrying the operator's own address.
    if _is_privacy_policy(path) and _OPERATOR_ADDRESS in line.lower():
        return True
    return False


def _hits(path):
    with open(path, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh.read().splitlines()
                if _TERM.search(ln)
                and not _exempt(path, ln.strip())]


class NoProviderNameInLiveDocsTest(unittest.TestCase):
    def test_scan_is_not_vacuous(self):
        docs = _live_docs()
        self.assertGreater(len(docs), 15)
        names = {os.path.basename(p) for p in docs}
        for expected in ("README.md", "INSTALL.md", "AGENTS.md",
                         "PROTOCOL.md", "idea321-runbook.md"):
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


class PrivacyPolicyContactExemptionTest(unittest.TestCase):
    """The 3.16.26.24 gate fix: the privacy policy's Contact line is
    exempt, scoped to that file and that address -- everything else
    the discipline ever caught, it still catches."""

    def _write(self, relpath, text):
        import tempfile
        base = tempfile.mkdtemp()
        path = os.path.join(base, *relpath.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_contact_line_is_exempt(self):
        path = self._write(
            "docs/steady/project/privacy-policy.md",
            "**Contact.** Questions about this policy: "
            "slutsky5544@gmail.com\n")
        self.assertEqual([], _hits(path))

    def test_contact_line_is_exempt_in_any_case(self):
        path = self._write(
            "docs/steady/project/privacy-policy.md",
            "**Contact.** Questions: SLUTSKY5544@GMAIL.COM\n")
        self.assertEqual([], _hits(path))

    def test_other_mention_in_privacy_policy_still_fails(self):
        path = self._write(
            "docs/steady/project/privacy-policy.md",
            "Sign in with your gmail account to continue.\n")
        self.assertEqual(["Sign in with your gmail account to continue."],
                         _hits(path))

    def test_other_address_in_privacy_policy_still_fails(self):
        path = self._write(
            "docs/steady/project/privacy-policy.md",
            "Write to someoneelse@gmail.com for help.\n")
        self.assertEqual(["Write to someoneelse@gmail.com for help."],
                         _hits(path))

    def test_contact_line_plus_other_mention_reports_only_the_other(self):
        path = self._write(
            "docs/steady/project/privacy-policy.md",
            "**Contact.** Questions about this policy: "
            "slutsky5544@gmail.com\n"
            "We recommend gmail for your mailbox.\n")
        self.assertEqual(["We recommend gmail for your mailbox."],
                         _hits(path))

    def test_operator_address_in_another_live_doc_still_fails(self):
        path = self._write(
            "docs/steady/project/other-page.md",
            "Reach the author at slutsky5544@gmail.com any time.\n")
        self.assertEqual(
            ["Reach the author at slutsky5544@gmail.com any time."],
            _hits(path))

    def test_privacy_policy_name_elsewhere_still_fails(self):
        path = self._write(
            "docs/other/privacy-policy.md",
            "**Contact.** Questions: slutsky5544@gmail.com\n")
        self.assertEqual(
            ["**Contact.** Questions: slutsky5544@gmail.com"],
            _hits(path))

    def test_draft_author_line_still_exempt(self):
        path = self._write(
            "docs/ietf/draft-slutsky-example.md",
            'email: "slutsky5544@gmail.com"\n')
        self.assertEqual([], _hits(path))

    def test_draft_other_line_still_fails(self):
        path = self._write(
            "docs/ietf/draft-slutsky-example.md",
            "Use gmail to send the draft.\n")
        self.assertEqual(["Use gmail to send the draft."], _hits(path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
