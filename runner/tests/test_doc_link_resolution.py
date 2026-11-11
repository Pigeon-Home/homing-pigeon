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


if __name__ == "__main__":
    unittest.main()
