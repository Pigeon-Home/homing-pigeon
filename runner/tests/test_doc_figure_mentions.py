"""Headline figures in evergreen docs: dated, pointed, and in
agreement with the canonical record.

The normalization settled 2026-11-08: a headline figure may
stand in many places, but each mention carries the figure with
its date and a link back to the one canonical home for its
class -- the statistics record for whole-tree figures
(docs/infrastructure-documents/project/statistics.md), the
duplication audit for the latent percentages, runner/ops/
core.py for the core's size. The failure this guards is on
record: AGENTS.md and PROTOCOL.md carried "17 million tokens"
from 2026-11-03/04, undated in the fair-warning sentence and
linked nowhere, while the tree measured 20,163,806 -- the
figure rotted in place through dozens of releases because
nothing looked at it.

This is a shape guard, not a value pin: no figure value is
hardcoded here. Whole-tree mentions are checked for agreement
against the canonical record's CURRENT values, parsed out of
statistics.md itself -- an exact mention must state the
record's measured count, a millions mention its whole
millions, and the date a mention carries must be the record's
dated date. When the tree is re-measured and the record is
refreshed (the release procedure refreshes it in the same cut
as a fresh measure), the mentions must move with it, and this
test is the tripwire that says so.

The guard's limit, stated plainly: it proves the mentions
agree with the record, not that the record is fresh. The
record's freshness rests on its dated, commit-named header
(pinned below) and on the release procedure's refresh step.

Subset figures (an exact count under ten million tokens: the
core, a documentation subset, a sitting's packet) are a
different class: each must carry its date in its paragraph
and either a link to a canonical home or the name of the
counter that produced it -- the project's estimator, Gemini
countTokens, an API's own count -- because the tree holds
several counters and they are not interchangeable. An exact
round power of ten (1,000,000 tokens) is a capacity -- a
vendor's window size -- not a measured count of project
material, and is not a figure for this guard.

Dated records are exempt by design, as in the version-rot
guard: the changelog, docs/archive/, the dated reports, the
IETF drafts, and the two standing logs keep the figures of
their day. The canonical homes exempt themselves.
"""

import os
import re
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


STATISTICS_REL = os.path.join(
    "docs", "infrastructure-documents", "project", "statistics.md")
AUDIT_REL = os.path.join(
    "docs", "infrastructure-documents", "project",
    "duplication-audit.md")

STATISTICS_LINK = re.compile(r"\]\([^)]*project/statistics\.md\)")
AUDIT_LINK = re.compile(r"\]\([^)]*project/duplication-audit\.md\)")
CORE_LINK = re.compile(r"\]\([^)]*runner/ops/core\.py\)")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

MILLION = re.compile(r"(\d+(?:\.\d+)?)\s+million\s+tokens")
MIL = re.compile(r"(\d+)\s+mil\s+(?:security\s+)?tokens")
EXACT = re.compile(r"(\d[\d,]*)\s+tokens")
PCT_TREE = re.compile(r"\d+(?:\.\d+)?%\s+of\s+the\s+tree")
PCT_NONLATENT = re.compile(r"\d+(?:\.\d+)?%\s+non-latent")

# Subset counters the tree names where a subset figure stands.
ATTRIBUTIONS = (
    "Gemini count", "countTokens", "API's own count",
    "counted by the API", "same estimator", "own estimator",
)

WHOLE_TREE_EXACT_FLOOR = 10_000_000
SUBSET_EXACT_FLOOR = 10_000


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _evergreen_docs():
    root = _root()
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        parts = set(rel.split(os.sep))
        if ".git" in parts or "__pycache__" in parts:
            dirnames[:] = []
            continue
        # Dated records are exempt, the version-rot rule:
        # the archive, the IETF drafts, the dated reports.
        if parts & {"archive", "ietf", "reports"}:
            dirnames[:] = []
            continue
        for name in filenames:
            if name.endswith(".md") and name not in (
                    "CHANGELOG.md", "changelog.md"):
                found.append(os.path.join(dirpath, name))
    logs = {os.path.join(root, "docs", "steady", "seats",
                         "questions.md"),
            os.path.join(root, "docs", "infrastructure-documents",
                         "project", "campaign-standing-orders.md")}
    # The canonical homes state the figures themselves; a home
    # does not point at itself.
    homes = {os.path.join(root, STATISTICS_REL),
             os.path.join(root, AUDIT_REL)}
    return [p for p in found if p not in logs and p not in homes]


def _paragraphs(text):
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def _record_values():
    """The canonical record's dated date and measured count."""
    text = _read(os.path.join(_root(), STATISTICS_REL))
    date = re.search(r"^Dated (\d{4}-\d{2}-\d{2})", text, re.M)
    count = re.search(r"-\s*Tokens:\s*([\d,]+)", text)
    return (date.group(1) if date else None,
            int(count.group(1).replace(",", "")) if count else None)


def _classify(paragraph):
    """Yield (kind, value) for each headline figure in a paragraph.

    kind is "tree" (whole-tree scale), "subset" (a named part
    of the tree, or a sitting's count), or "percent" (a share
    of the tree). Values are token counts for the token kinds.
    """
    for match in MILLION.finditer(paragraph):
        if float(match.group(1)) >= 2:
            yield ("tree", float(match.group(1)) * 1_000_000)
    for match in MIL.finditer(paragraph):
        yield ("tree", float(match.group(1)) * 1_000_000)
    for match in EXACT.finditer(paragraph):
        value = int(match.group(1).replace(",", ""))
        if value == 10 ** (len(str(value)) - 1):
            continue  # a round power of ten: a capacity, not a count
        if value >= WHOLE_TREE_EXACT_FLOOR:
            yield ("tree", value)
        elif value >= SUBSET_EXACT_FLOOR:
            yield ("subset", value)
    if PCT_TREE.search(paragraph) or PCT_NONLATENT.search(paragraph):
        yield ("percent", None)


def _mentions():
    """(relpath, paragraph, kind, value) for every figure found."""
    root = _root()
    for path in _evergreen_docs():
        rel = os.path.relpath(path, root)
        for paragraph in _paragraphs(_read(path)):
            for kind, value in _classify(paragraph):
                yield (rel, paragraph, kind, value)


class FigureMentionShapeTest(unittest.TestCase):
    def test_scan_is_not_vacuous(self):
        self.assertGreater(len(_evergreen_docs()), 10)
        self.assertGreater(len(list(_mentions())), 0)

    def test_record_parses(self):
        date, count = _record_values()
        self.assertIsNotNone(date)
        self.assertIsNotNone(count)

    def test_whole_tree_mentions_agree_with_the_record(self):
        date, count = _record_values()
        offenders = []
        for rel, paragraph, kind, value in _mentions():
            if kind != "tree":
                continue
            if not STATISTICS_LINK.search(paragraph):
                offenders.append(
                    "%s: whole-tree figure without a link to the "
                    "statistics record" % rel)
            elif date not in paragraph:
                offenders.append(
                    "%s: whole-tree figure not dated with the "
                    "record's date (%s)" % (rel, date))
            elif abs(value - count) > 0.01 * count:
                offenders.append(
                    "%s: whole-tree figure disagrees with the "
                    "record's measured count (%d)" % (rel, count))
        self.assertEqual([], offenders)

    def test_subset_mentions_carry_date_and_pointer(self):
        offenders = []
        for rel, paragraph, kind, value in _mentions():
            if kind != "subset":
                continue
            if not ISO_DATE.search(paragraph):
                offenders.append(
                    "%s: subset figure (%d tokens) without a date"
                    % (rel, value))
            elif not (STATISTICS_LINK.search(paragraph)
                      or AUDIT_LINK.search(paragraph)
                      or CORE_LINK.search(paragraph)
                      or any(a in paragraph for a in ATTRIBUTIONS)):
                offenders.append(
                    "%s: subset figure (%d tokens) with neither a "
                    "canonical link nor a named counter"
                    % (rel, value))
        self.assertEqual([], offenders)

    def test_percent_mentions_carry_date_and_pointer(self):
        offenders = []
        for rel, paragraph, kind, value in _mentions():
            if kind != "percent":
                continue
            if not ISO_DATE.search(paragraph):
                offenders.append(
                    "%s: a share of the tree stated without a date"
                    % rel)
            elif not (AUDIT_LINK.search(paragraph)
                      or STATISTICS_LINK.search(paragraph)):
                offenders.append(
                    "%s: a share of the tree stated without a "
                    "link to the audit or the record" % rel)
        self.assertEqual([], offenders)


class StatisticsRecordPinTest(unittest.TestCase):
    def test_display_line_is_the_settled_line(self):
        text = _read(os.path.join(_root(), STATISTICS_REL))
        self.assertIn(
            "20 mil security tokens, 5,000 commits, 1,200,000 "
            "lines at 96.35% non-latent code", text)

    def test_header_is_dated_and_names_its_commit(self):
        text = _read(os.path.join(_root(), STATISTICS_REL))
        header = text[:800]
        self.assertRegex(header, r"Dated \d{4}-\d{2}-\d{2}")
        self.assertRegex(header, r"commit\s*\n?\s*`?[0-9a-f]{40}`?")

    def test_record_names_its_verify_routes(self):
        text = _read(os.path.join(_root(), STATISTICS_REL))
        self.assertIn("version4.py measure", text)
        self.assertIn("CI-SNAPSHOT.json", text)
        self.assertIn("gh attestation verify", text)
        self.assertIn("canonical source for the tree's figures",
                      text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
