# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Markdown links resolve the way GitHub resolves them: relative to
the directory of the file that carries the link.

The gap this closes. The documentation overview's Packet 3 pass
reported "zero broken relative links" while docs/FAQ.md carried
[live-examples.md](docs/steady/use/live-examples.md) -- a target
written as if from the repository root. Checked as a root-relative
path it exists; resolved the way GitHub resolves it, from docs/,
it names docs/docs/steady/use/live-examples.md, which does not,
and the reader who clicks it gets a 404. The owner hit exactly
that link live. A link check that starts from the root cannot see
this family; this test starts from the linking file, which is the
only place GitHub ever starts from.

Scope: the current-facing documentation -- the root manuals,
docs/ and the steady and infrastructure-documents shelves.
Historical records are out of scope under the repository's audit
ignore list (AGENTS.md rule 6): docs/archive, docs/steady/reports
and the infrastructure changelog keep the links of their time.
Fenced code blocks and inline code are not links and are stripped
before the scan, so an example command that merely looks like a
link definition cannot fail the test.

The second gap, found when the conductor re-tested the repair
live. A reader who follows a page's prose meets paths that are
not links at all: a backtick path in the text, naming where a
page lives. The design page sent its readers to
`docs/use/live-examples.md` -- the live-examples page's home
before the layout move -- long after the clickable links were
repaired, and no link check can see a path that is not a link.
The reader's pages (the scope test_reader_docs_quiet draws:
the root manuals and the steady and infrastructure shelves'
reader families) must not name a retired-layout path in
backticks: `docs/use/`, `docs/security/`, `docs/oracle/`,
`docs/design/`, `docs/extend/`, `docs/proofs/`,
`docs/project/`, `docs/reports/` and `docs/seats/` are the
drawers the two-shelf layout retired. Dated records and the
seats' and project drawers quote those paths as history and
stand outside this scope, exactly as they stand outside the
reader's.
"""

import os
import re
import tempfile
import unicodedata
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EXCLUDED_PREFIXES = (
    os.path.join("docs", "archive") + os.sep,
    os.path.join("docs", "steady", "reports") + os.sep,
)
EXCLUDED_FILES = {
    os.path.join("docs", "infrastructure-documents", "changelog.md"),
}

INLINE_LINK = re.compile(
    r"!?\[[^\]]*\]\(\s*(<[^>]+>|[^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
REFERENCE_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(<[^>]+>|\S+)", re.MULTILINE)
FENCED_BLOCK = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
HTML_ANCHOR = re.compile(r"<a\s+(?:name|id)=\"([^\"]+)\"")


def scope_files(root):
    """Every current-facing markdown file under root, in path order."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            if os.sep in rel and not rel.startswith("docs" + os.sep):
                continue
            if rel in EXCLUDED_FILES:
                continue
            if any(rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
                continue
            found.append(path)
    return found


def strip_code(text):
    # Blanked, not deleted: the newlines survive so a line number
    # counted on the stripped text is the file's own line number.
    text = FENCED_BLOCK.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return INLINE_CODE.sub("", text)


def iter_targets(text):
    """(target, line number) for every link target in the text."""
    for match in INLINE_LINK.finditer(text):
        yield match.group(1).strip("<>"), text.count("\n", 0, match.start()) + 1
    for match in REFERENCE_DEF.finditer(text):
        yield match.group(1).strip("<>"), text.count("\n", 0, match.start()) + 1


def is_relative(target):
    if target.startswith(("#", "mailto:", "tel:", "//")):
        return False
    return "://" not in target


def resolve(linking_path, target):
    """The path GitHub resolves target to, from linking_path's file."""
    file_part = urllib.parse.unquote(target.partition("#")[0])
    if not file_part:
        return linking_path
    return os.path.normpath(os.path.join(os.path.dirname(linking_path), file_part))


def github_slug(heading, seen):
    slug = heading.strip().lower()
    slug = "".join(
        char for char in slug
        if char.isalnum() or char in " _-"
        or unicodedata.category(char).startswith("L"))
    slug = slug.replace(" ", "-")
    if slug in seen:
        seen[slug] += 1
        return "%s-%d" % (slug, seen[slug])
    seen[slug] = 0
    return slug


def anchors_of(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = strip_code(handle.read())
    anchors = set(HTML_ANCHOR.findall(text))
    seen = {}
    for match in HEADING.finditer(text):
        heading = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", match.group(1))
        heading = heading.replace("`", "").replace("*", "").replace("_", "")
        anchors.add(github_slug(heading, seen))
    return anchors


def broken_links(root):
    failures = []
    for path in scope_files(root):
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = strip_code(handle.read())
        rel = os.path.relpath(path, root)
        for target, line in iter_targets(text):
            if not is_relative(target):
                continue
            if not os.path.exists(resolve(path, target)):
                failures.append("%s:%d -> %s" % (rel, line, target))
    return failures


class CurrentFacingLinkTests(unittest.TestCase):

    def test_every_relative_link_resolves_from_its_own_file(self):
        self.assertEqual([], broken_links(ROOT))

    def test_anchors_on_markdown_targets_exist(self):
        failures = []
        cache = {}
        for path in scope_files(ROOT):
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = strip_code(handle.read())
            rel = os.path.relpath(path, ROOT)
            for target, line in iter_targets(text):
                if not is_relative(target) or "#" not in target:
                    continue
                anchor = urllib.parse.unquote(target.partition("#")[2])
                if not anchor:
                    continue
                resolved = resolve(path, target)
                if not resolved.endswith(".md") or not os.path.exists(resolved):
                    continue
                if resolved not in cache:
                    cache[resolved] = anchors_of(resolved)
                if anchor not in cache[resolved]:
                    failures.append("%s:%d -> %s" % (rel, line, target))
        self.assertEqual([], failures)


class ResolverShapeTests(unittest.TestCase):
    """The family shapes, pinned on a synthetic tree so the guard
    itself is proven able to catch the failure it exists for."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, "docs", "steady", "use"))
        self._write("docs/steady/use/live-examples.md", "# Live examples\n")
        self._write("README.md", "# Root\n")

    def _write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def _broken(self):
        return broken_links(self.root)

    def test_root_written_link_from_a_subdirectory_is_broken(self):
        # The FAQ shape that shipped: the target is true from the
        # root and false from the file that carries it.
        self._write("docs/FAQ.md",
                    "[live-examples.md](docs/steady/use/live-examples.md)\n")
        self.assertEqual(1, len(self._broken()))

    def test_directory_relative_link_resolves(self):
        self._write("docs/FAQ.md",
                    "[live-examples.md](steady/use/live-examples.md)\n")
        self.assertEqual([], self._broken())

    def test_the_same_words_from_the_root_file_resolve(self):
        # README.md's root-written links are correct and must not
        # be "fixed": from the root, the root path is the truth.
        self._write("README.md",
                    "[live examples](docs/steady/use/live-examples.md)\n")
        self.assertEqual([], self._broken())

    def test_parent_relative_link_resolves(self):
        self._write("docs/steady/use/page.md",
                    "[root](../../../README.md) and [faq](../../FAQ.md)\n")
        self._write("docs/FAQ.md", "# Faq\n")
        self.assertEqual([], self._broken())

    def test_missing_parent_relative_link_is_broken(self):
        self._write("docs/steady/use/page.md", "[nope](../../nope.md)\n")
        self.assertEqual(1, len(self._broken()))

    def test_fenced_code_is_not_a_link(self):
        self._write("docs/FAQ.md",
                    "```powershell\n[IO.File]::AppendAllText((Resolve-Path x)\n"
                    "[a](docs/steady/use/live-examples.md)\n```\n")
        self.assertEqual([], self._broken())

    def test_reference_definition_resolves_from_its_own_file(self):
        self._write("docs/FAQ.md",
                    "[live][1]\n\n[1]: steady/use/live-examples.md\n")
        self.assertEqual([], self._broken())

    def test_external_and_anchor_only_targets_are_skipped(self):
        self._write("docs/FAQ.md",
                    "[web](https://example.invalid/x.md) [here](#faq)\n")
        self.assertEqual([], self._broken())


READER_FILES = ["README.md", "INSTALL.md", "SECURITY.md", "PROTOCOL.md",
                "docs/FAQ.md", "docs/ENTERPRISE.md", "docs/support-matrix.md",
                "docs/steady/project/contributing.md",
                "docs/steady/extensions.md", "docs/steady/networking.md",
                "docs/steady/present-but-invalid-config.md",
                "docs/steady/secret-rotation.md", "docs/steady/sending.md",
                "docs/steady/verification.md"]
READER_DIRS = ["docs/steady/use", "docs/steady/oracle", "docs/steady/design",
               "docs/steady/security", "docs/infrastructure-documents/extend",
               "docs/infrastructure-documents/oracle",
               "docs/infrastructure-documents/security",
               "docs/infrastructure-documents/design", "docs/ietf"]
NOT_READER = {"docs/steady/security/hardening_report.md"}
RETIRED_PATH = re.compile(
    r"`(docs/(?:use|security|oracle|design|extend|proofs|project|"
    r"reports|seats)/[^`\s]*)`")


def reader_files(root):
    """The reader's pages under root, in the scope
    test_reader_docs_quiet draws."""
    found = [os.path.join(root, rel) for rel in READER_FILES]
    for rel_dir in READER_DIRS:
        for dirpath, _dirnames, filenames in os.walk(os.path.join(root, rel_dir)):
            for name in sorted(filenames):
                if name.endswith(".md"):
                    found.append(os.path.join(dirpath, name))
    return [path for path in found
            if os.path.exists(path)
            and os.path.relpath(path, root).replace(os.sep, "/")
            not in NOT_READER]


def retired_paths(root):
    failures = []
    for path in reader_files(root):
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        rel = os.path.relpath(path, root)
        for match in RETIRED_PATH.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            failures.append("%s:%d -> %s" % (rel, line, match.group(1)))
    return failures


class PlainTextPathTests(unittest.TestCase):

    def test_no_retired_layout_path_in_a_reader_page(self):
        self.assertEqual([], retired_paths(ROOT))


class PlainTextShapeTests(unittest.TestCase):
    """The plain-text family shapes, pinned on a synthetic tree."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def _write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_a_retired_live_examples_path_in_a_reader_page_fails(self):
        # The design page's shape: a present-tense pointer in
        # backticks, naming the page's pre-move home.
        self._write("docs/steady/design/oracle-opinion-design.md",
                    "The numbers are in `docs/use/live-examples.md`.\n")
        failures = retired_paths(self.root)
        self.assertEqual(1, len(failures))
        self.assertIn("docs/use/live-examples.md", failures[0])

    def test_the_current_home_in_a_reader_page_passes(self):
        self._write("docs/steady/design/oracle-opinion-design.md",
                    "The numbers are in "
                    "`docs/steady/use/live-examples.md`.\n")
        self.assertEqual([], retired_paths(self.root))

    def test_a_retired_path_in_a_dated_record_is_out_of_scope(self):
        # Reports are records of their day; the reader scope does
        # not reach them and their paths stand as written.
        self._write("docs/steady/reports/live-2026-10-25-readme.md",
                    "`docs/use/live-examples.md` quotes them.\n")
        self.assertEqual([], retired_paths(self.root))

    def test_every_retired_drawer_is_named(self):
        for drawer in ("use", "security", "oracle", "design", "extend",
                       "proofs", "project", "reports", "seats"):
            self._write("docs/steady/use/page.md",
                        "See `docs/%s/page.md`.\n" % drawer)
            self.assertEqual(1, len(retired_paths(self.root)),
                             "drawer %s not caught" % drawer)


if __name__ == "__main__":
    unittest.main()
