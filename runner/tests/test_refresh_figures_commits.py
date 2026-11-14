"""The commit count the refresh publishes: complete
histories only (Q193).

The 3.16.25.27 figure refresh ran in a shallow scratch
clone and published its reachable count -- 170 commits,
display 0 -- as the project's count, over standing facts
of 5,836. rev-list had answered exactly what it was
asked: the commits it could reach. The counting layer
now refuses a shallow history loudly and refuses a fresh
count below the standing facts, and this family pins the
shapes around that refusal: display rounding at its
boundaries, validation against the standing facts, real
git histories whole and truncated at every depth, a
history made whole again, and checkouts whose directory
names carry the bookend symbols at their edges.

The git shapes run real git in temporary directories;
nothing here touches the checkout the suite runs in.
"""
import math
import os
import shutil
import subprocess
import tempfile
import unittest

from runner.tools import refresh_figures as RF

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def _git(cwd, *args):
    out = subprocess.run(
        ["git", "-C", cwd] + list(args),
        capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _make_repo(path, commits):
    os.makedirs(path)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.invalid")
    _git(path, "config", "user.name", "Count Test")
    _git(path, "config", "commit.gpgsign", "false")
    for i in range(commits):
        with open(os.path.join(path, "f%03d.txt" % i), "w",
                  encoding="utf-8") as fh:
            fh.write("line %d\n" % i)
        _git(path, "add", ".")
        _git(path, "commit", "-q", "-m", "commit %d" % i)
    return path


def _clone(src, dst, depth=None):
    args = ["git", "clone", "-q"]
    if depth is not None:
        args += ["--depth", str(depth)]
    args += ["file://" + src, dst]
    subprocess.run(args, capture_output=True, text=True,
                   check=True)
    return dst


class _TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-count-")
        self.addCleanup(shutil.rmtree, self.tmp, True)


class DisplayRoundingTest(unittest.TestCase):
    """The settled rounding, pinned at and around every
    boundary shape: the bug's own 170 (which rounds to the
    0 that showed in the display line), the half-way step,
    and the standing published figures."""

    def test_the_bug_shape_rounds_to_zero(self):
        self.assertEqual(RF.display_commits_for(170), 0)

    def test_the_standing_figures_round_to_six_thousand(self):
        self.assertEqual(RF.display_commits_for(5832), 6000)
        self.assertEqual(RF.display_commits_for(5836), 6000)
        self.assertEqual(RF.display_commits_for(5866), 6000)

    def test_the_steps_are_where_they_are_named(self):
        self.assertEqual(RF.display_commits_for(0), 0)
        self.assertEqual(RF.display_commits_for(499), 0)
        self.assertEqual(RF.display_commits_for(500), 1000)
        self.assertEqual(RF.display_commits_for(1499), 1000)
        self.assertEqual(RF.display_commits_for(1500), 2000)


def _rounding_case(value):
    def test(self):
        expected = int(math.floor(value / 1000 + 0.5)) * 1000
        self.assertEqual(RF.display_commits_for(value), expected,
                         "count %d" % value)
    return test


_ROUNDING_VALUES = sorted(set(
    [0, 1, 2, 169, 170, 171, 499, 500, 501, 999, 1000,
     1499, 1500, 1501, 5832, 5836, 5866, 5867]
    + list(range(0, 10001, 500))
    + list(range(0, 10001, 999))))
for _value in _ROUNDING_VALUES:
    setattr(DisplayRoundingTest, "test_display_%d" % _value,
            _rounding_case(_value))
del _value


class DisplayLineTest(unittest.TestCase):
    """The record's line rendered from each shape of facts:
    the bug's line is reproducible from the bug's facts, so
    the pin holds the rendering as well as the count."""

    def _facts(self, commits, display):
        return {"tokens": 25_883_898, "display_commits": display,
                "display_lines": 1_500_000,
                "non_latent_percent": 96.16}

    def test_the_bug_facts_render_the_bug_line(self):
        self.assertEqual(
            RF.display_line(self._facts(170, 0)),
            "25 mil security tokens, 0 commits, 1,500,000 "
            "lines at 96.16% non-latent code")

    def test_the_true_facts_render_the_standing_line(self):
        self.assertEqual(
            RF.display_line(self._facts(5866, 6000)),
            "25 mil security tokens, 6,000 commits, "
            "1,500,000 lines at 96.16% non-latent code")


class ValidateCommitCountTest(unittest.TestCase):
    """A fresh count answers to the standing facts: equal
    or greater stands, smaller refuses, a negative refuses,
    and a standing count that is not an integer (an older
    or hand-kept record) does not block the measure."""

    def test_a_missing_standing_count_allows_any_count(self):
        self.assertEqual(RF.validate_commit_count(0, {}), 0)
        self.assertEqual(RF.validate_commit_count(170, {}), 170)

    def test_a_non_integer_standing_count_does_not_block(self):
        self.assertEqual(
            RF.validate_commit_count(5, {"commits": "5836"}), 5)
        self.assertEqual(
            RF.validate_commit_count(5, {"commits": None}), 5)


def _validate_case(new, standing, stands):
    def test(self):
        previous = {} if standing is None else {"commits": standing}
        if stands:
            self.assertEqual(
                RF.validate_commit_count(new, previous), new)
        else:
            with self.assertRaises(ValueError):
                RF.validate_commit_count(new, previous)
    return test


_VALIDATE_CASES = [
    (0, 0, True), (1, 0, True), (170, 170, True),
    (5836, 5836, True), (5866, 5836, True),
    (5867, 5866, True), (100000, 5836, True),
    (170, 5836, False), (0, 5836, False),
    (5835, 5836, False), (100, 101, False),
    (0, 1, False), (-1, None, False), (-100, 0, False),
    (-1, -5, False),
]
for _idx, (_new, _standing, _stands) in enumerate(_VALIDATE_CASES):
    setattr(ValidateCommitCountTest,
            "test_validate_%02d" % _idx,
            _validate_case(_new, _standing, _stands))
del _idx, _new, _standing, _stands


class FullHistoryCountTest(_TempDirCase):
    """A complete history counts whole, at the sizes a
    checkout takes on its way to the project's size."""

    def _count(self, commits):
        repo = _make_repo(os.path.join(self.tmp, "repo"), commits)
        self.assertFalse(RF.is_shallow_history(repo))
        self.assertEqual(
            _git(repo, "rev-parse", "--is-shallow-repository"),
            "false")
        self.assertEqual(RF.count_commits(repo), commits)


def _full_case(commits):
    def test(self):
        self._count(commits)
    return test


for _n in (1, 2, 3, 5, 10, 25):
    setattr(FullHistoryCountTest, "test_full_%02d" % _n,
            _full_case(_n))
del _n


class ShallowRefusalTest(_TempDirCase):
    """A truncated history refuses at every depth, and the
    refusal names the shallowness and what the clone can
    actually reach."""

    def _refuse(self, depth):
        src = _make_repo(os.path.join(self.tmp, "src"), 12)
        dst = _clone(src, os.path.join(self.tmp, "dst"),
                     depth=depth)
        self.assertTrue(RF.is_shallow_history(dst))
        self.assertEqual(
            _git(dst, "rev-parse", "--is-shallow-repository"),
            "true")
        with self.assertRaises(RF.ShallowHistoryError) as ctx:
            RF.count_commits(dst)
        self.assertIn("shallow", str(ctx.exception))
        self.assertIn("only %d commit(s)" % depth,
                      str(ctx.exception))


def _shallow_case(depth):
    def test(self):
        self._refuse(depth)
    return test


for _d in (1, 2, 3, 5, 11):
    setattr(ShallowRefusalTest, "test_shallow_depth_%02d" % _d,
            _shallow_case(_d))
del _d


class ShallowMadeWholeTest(_TempDirCase):
    def test_an_unshallowed_clone_counts_whole(self):
        src = _make_repo(os.path.join(self.tmp, "src"), 9)
        dst = _clone(src, os.path.join(self.tmp, "dst"), depth=2)
        with self.assertRaises(RF.ShallowHistoryError):
            RF.count_commits(dst)
        _git(dst, "fetch", "--unshallow", "origin")
        self.assertFalse(RF.is_shallow_history(dst))
        self.assertEqual(RF.count_commits(dst), 9)

    def test_a_depth_covering_the_history_agrees_with_git(self):
        src = _make_repo(os.path.join(self.tmp, "src"), 6)
        dst = _clone(src, os.path.join(self.tmp, "dst"), depth=50)
        git_says = _git(dst, "rev-parse",
                        "--is-shallow-repository") == "true"
        self.assertEqual(RF.is_shallow_history(dst), git_says)
        if not git_says:
            self.assertEqual(RF.count_commits(dst), 6)


class BookendedPathTest(_TempDirCase):
    """The counting reads a checkout by its path; the path
    shapes at the edges -- symbols front and back, runs of
    them, spaces -- change neither the count of a whole
    history nor the refusal of a truncated one."""

    def _whole(self, name):
        repo = _make_repo(os.path.join(self.tmp, name), 3)
        self.assertFalse(RF.is_shallow_history(repo))
        self.assertEqual(RF.count_commits(repo), 3)

    def _truncated(self, name):
        src = _make_repo(os.path.join(self.tmp, "src-" + name), 8)
        dst = _clone(src, os.path.join(self.tmp, name), depth=2)
        self.assertTrue(RF.is_shallow_history(dst))
        with self.assertRaises(RF.ShallowHistoryError):
            RF.count_commits(dst)


_BOOKEND_NAMES = [
    "plain", "-lead", "trail-", ";both;", "'quoted'",
    "sp ace", "under_score", "dot.name", "plus+name",
    "eq=name", "at@name", "pct%name", "multi---dash",
    "UPPER", "num123", "--both--", "..dots..",
]
for _idx, _name in enumerate(_BOOKEND_NAMES):
    setattr(BookendedPathTest, "test_whole_%02d" % _idx,
            (lambda n: lambda self: self._whole(n))(_name))
for _idx, _name in enumerate(["-lead", ";both;", "--both--"]):
    setattr(BookendedPathTest, "test_truncated_%02d" % _idx,
            (lambda n: lambda self: self._truncated(n))(_name))
del _idx, _name


class MeasureRefusalTest(_TempDirCase):
    """The end-to-end shape of Q193: a history of a dozen
    commits carrying the real statistics record, cloned at
    depth 2 -- the measure and the write refuse it, and
    write nothing. (The history is built here rather than
    cloned from the suite's own checkout, whose depth is
    the hosting leg's choice, not this test's.)"""

    def setUp(self):
        super().setUp()
        src = os.path.join(self.tmp, "src")
        os.makedirs(os.path.join(src, os.path.dirname(
            RF.STATISTICS_REL)))
        with open(os.path.join(REPO, RF.STATISTICS_REL),
                  encoding="utf-8") as fh:
            record = fh.read()
        with open(os.path.join(src, RF.STATISTICS_REL), "w",
                  encoding="utf-8") as fh:
            fh.write(record)
        _git(src, "init", "-q")
        _git(src, "config", "user.email", "test@example.invalid")
        _git(src, "config", "user.name", "Count Test")
        _git(src, "config", "commit.gpgsign", "false")
        for i in range(12):
            with open(os.path.join(src, "filler.txt"), "a",
                      encoding="utf-8") as fh:
                fh.write("line %d\n" % i)
            _git(src, "add", ".")
            _git(src, "commit", "-q", "-m", "commit %d" % i)
        self.clone = _clone(src, os.path.join(self.tmp, "clone"),
                            depth=2)
        self.stats = os.path.join(self.clone, RF.STATISTICS_REL)
        with open(self.stats, encoding="utf-8") as fh:
            self.before = fh.read()
        self.previous = RF.parse_facts(self.before)

    def test_the_shallow_measure_refuses(self):
        with self.assertRaises(RF.ShallowHistoryError):
            RF.measure_facts(self.clone, self.previous)

    def test_the_shallow_write_refuses_and_writes_nothing(self):
        with self.assertRaises(RF.ShallowHistoryError):
            RF.write(self.clone)
        with open(self.stats, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), self.before)

    def test_the_tool_itself_refuses_with_a_nonzero_exit(self):
        proc = subprocess.run(
            ["git", "-C", self.clone, "rev-parse",
             "--is-shallow-repository"],
            capture_output=True, text=True, check=True)
        self.assertEqual(proc.stdout.strip(), "true")
        tool = os.path.join(REPO, "runner", "tools",
                            "refresh_figures.py")
        proc = subprocess.run(
            ["python3", tool, "--write", "--root", self.clone],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("shallow", proc.stderr)
        with open(self.stats, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), self.before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
