# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The 4-component version scheme (runner/ops/version4.py).

MAJOR.MINOR.TOKENS.COUNTER: the major never moves, the third
component is the repository's size in tokens in whole millions
(measured at most once every 24 hours for general callers — a
release cut passes --fresh and takes a fresh recount instead),
and the counter restarts at 1 whenever a number to its left
increases.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
import shutil

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "runner"))

from ops import version4  # noqa: E402

NOW = 1700000000.0
WINDOW = version4.MEASURE_WINDOW_SEC


class ParseTest(unittest.TestCase):
    def test_parse_round_trip(self):
        for text, parts in [
                ("3.15.6.148", (3, 15, 6, 148)),
                ("3.15.0.1", (3, 15, 0, 1)),
                ("0.0.0.0", (0, 0, 0, 0)),
                ("10.200.34.9999", (10, 200, 34, 9999))]:
            self.assertEqual(version4.parse(text), parts)
            self.assertEqual(version4.format_version(parts), text)

    def test_parse_rejects_malformed(self):
        for bad in ["", "3.15.148", "3.15.6.148.1", "3.15.6", "3.15..1",
                    "3.15.6.", ".15.6.148", "3.15.6.-1", "3.15.6.+1",
                    "3.15.6. 1", " 3.15.6.148", "3.15.6.148 ",
                    "3.15.6.x", "3.15.06.148", "3.15.6.0148",
                    "v3.15.6.148", "3,15,6,148", "3.15.6.148\n",
                    None, 3156148, (3, 15, 6, 148)]:
            with self.assertRaises(ValueError, msg=repr(bad)):
                version4.parse(bad)

    def test_format_rejects_bad_parts(self):
        for bad in [(3, 15, 6, -1), (3, 15, 6, "148"), (3, 15, 6),
                    (3, 15, 6, 148, 9), (3, 15, 6, None)]:
            with self.assertRaises((ValueError, TypeError), msg=repr(bad)):
                version4.format_version(bad)


class ConvertLegacyTest(unittest.TestCase):
    def test_counter_carries_over(self):
        self.assertEqual(version4.convert_legacy("3.15.148", 6),
                         "3.15.6.148")
        self.assertEqual(version4.convert_legacy("3.15.1", 0), "3.15.0.1")

    def test_rejects_non_legacy_shapes(self):
        for bad in ["3.15.6.148", "3.15", "3.15.x", "3.15.0148", "", None]:
            with self.assertRaises(ValueError, msg=repr(bad)):
                version4.convert_legacy(bad, 6)
        with self.assertRaises(ValueError):
            version4.convert_legacy("3.15.148", -1)


class EstimatorTest(unittest.TestCase):
    def test_count_text_tokens_rule(self):
        self.assertEqual(version4.count_text_tokens(""), 0)
        self.assertEqual(version4.count_text_tokens("hello world"), 2)
        self.assertEqual(version4.count_text_tokens("abc123"), 2)
        self.assertEqual(version4.count_text_tokens("a+b"), 3)
        self.assertEqual(version4.count_text_tokens("  spaced   out  "), 2)
        self.assertEqual(version4.count_text_tokens("x = 42;"), 4)

    def test_tokens_millions_floors(self):
        self.assertEqual(version4.tokens_millions(0), 0)
        self.assertEqual(version4.tokens_millions(999999), 0)
        self.assertEqual(version4.tokens_millions(1000000), 1)
        self.assertEqual(version4.tokens_millions(6412908), 6)
        with self.assertRaises(ValueError):
            version4.tokens_millions(-1)


class NextVersionTest(unittest.TestCase):
    def test_counter_increments_when_nothing_increases(self):
        # Measured 1 hour ago: inside the window, figure reused.
        got = version4.next_version("3.15.6.148", NOW, NOW - 3600, 6,
                                    fresh_tokens_millions=99)
        self.assertEqual(got, "3.15.6.149")

    def test_token_increase_restarts_counter(self):
        got = version4.next_version("3.15.6.148", NOW, NOW - 90000, 6,
                                    fresh_tokens_millions=7)
        self.assertEqual(got, "3.15.7.1")

    def test_same_figure_after_window_increments(self):
        got = version4.next_version("3.15.6.148", NOW, NOW - 90000, 6,
                                    fresh_tokens_millions=6)
        self.assertEqual(got, "3.15.6.149")

    def test_lower_figure_is_held(self):
        got = version4.next_version("3.15.6.148", NOW, NOW - 90000, 6,
                                    fresh_tokens_millions=5)
        self.assertEqual(got, "3.15.6.149")

    def test_minor_increase_restarts_counter(self):
        got = version4.next_version("3.15.6.148", NOW, NOW - 3600, 6,
                                    new_minor=16)
        self.assertEqual(got, "3.16.6.1")

    def test_minor_increase_uses_fresh_figure_outside_window(self):
        got = version4.next_version("3.15.6.148", NOW, NOW - 90000, 6,
                                    fresh_tokens_millions=8, new_minor=16)
        self.assertEqual(got, "3.16.8.1")

    def test_same_minor_is_not_a_restart(self):
        got = version4.next_version("3.15.6.148", NOW, NOW - 3600, 6,
                                    new_minor=15)
        self.assertEqual(got, "3.15.6.149")

    def test_minor_decrease_rejected(self):
        with self.assertRaises(ValueError):
            version4.next_version("3.15.6.148", NOW, NOW - 3600, 6,
                                  new_minor=14)

    def test_major_never_moves(self):
        for got in [
                version4.next_version("3.15.6.148", NOW, NOW - 3600, 6),
                version4.next_version("3.15.6.148", NOW, NOW - 90000, 6,
                                      fresh_tokens_millions=9),
                version4.next_version("3.15.6.148", NOW, NOW - 3600, 6,
                                      new_minor=16)]:
            self.assertEqual(version4.parse(got)[0], 3)

    def test_window_boundary(self):
        # 1 second inside the window: reuse, fresh ignored.
        got = version4.next_version("3.15.6.148", NOW, NOW - WINDOW + 1, 6,
                                    fresh_tokens_millions=99)
        self.assertEqual(got, "3.15.6.149")
        # Exactly at the boundary the window has elapsed: remeasure.
        got = version4.next_version("3.15.6.148", NOW, NOW - WINDOW, 6,
                                    fresh_tokens_millions=7)
        self.assertEqual(got, "3.15.7.1")

    def test_clock_before_last_measurement_reuses(self):
        got = version4.next_version("3.15.6.148", NOW, NOW + 3600, 6)
        self.assertEqual(got, "3.15.6.149")

    def test_never_measured_requires_fresh(self):
        with self.assertRaises(ValueError):
            version4.next_version("3.15.6.148", NOW, None, None)
        got = version4.next_version("3.15.6.148", NOW, None, None,
                                    fresh_tokens_millions=6)
        self.assertEqual(got, "3.15.6.149")

    def test_outside_window_requires_fresh(self):
        with self.assertRaises(ValueError):
            version4.next_version("3.15.6.148", NOW, NOW - 90000, 6)

    def test_inside_window_without_last_figure_rejected(self):
        with self.assertRaises(ValueError):
            version4.next_version("3.15.6.148", NOW, NOW - 3600, None,
                                  fresh_tokens_millions=6)

    def test_reused_figure_can_restart_counter(self):
        # The last release measured 7 while the current version still
        # carries 6: the increase lands now, inside the window.
        got = version4.next_version("3.15.6.148", NOW, NOW - 3600, 7)
        self.assertEqual(got, "3.15.7.1")

    def test_malformed_current_rejected(self):
        with self.assertRaises(ValueError):
            version4.next_version("3.15.148", NOW, NOW - 3600, 6)


def _git(root, *args):
    subprocess.run(["git", "-C", root] + list(args),
                   check=True, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE)


class MeasureTest(unittest.TestCase):
    def _repo(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        _git(root, "init", "-q")
        _git(root, "config", "user.email", "test@example.invalid")
        _git(root, "config", "user.name", "test")
        with open(os.path.join(root, "a.txt"), "w", encoding="utf-8") as fh:
            fh.write("hello world\n")  # 2 tokens
        with open(os.path.join(root, "b.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 42;\n")  # 4 tokens
        with open(os.path.join(root, "bin.dat"), "wb") as fh:
            fh.write(b"\x00\x01\x02binary")  # binary by NUL sniff
        with open(os.path.join(root, "img.png"), "wb") as fh:
            fh.write(b"not really a png")  # binary by extension
        with open(os.path.join(root, "untracked.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("must not be counted at all\n")
        _git(root, "add", "a.txt", "b.py", "bin.dat", "img.png")
        return root

    def test_measure_counts_tracked_text_only(self):
        self.assertEqual(version4.measure_repo_tokens(self._repo()), 6)

    def test_measure_rejects_non_repo(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        with self.assertRaises(RuntimeError):
            version4.measure_repo_tokens(base)


class MeasureCacheTest(unittest.TestCase):
    def test_round_trip(self):
        _tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, _tmp, ignore_errors=True)
        path = os.path.join(_tmp, "token-measure.txt")
        self.assertIsNone(version4.read_measure_cache(path))
        version4.write_measure_cache(path, NOW, 6)
        self.assertEqual(version4.read_measure_cache(path), (NOW, 6))

    def test_malformed_cache_reads_as_none(self):
        _tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, _tmp, ignore_errors=True)
        path = os.path.join(_tmp, "token-measure.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not a cache\n")
        self.assertIsNone(version4.read_measure_cache(path))


class CliTest(unittest.TestCase):
    def _run_main(self, argv):
        buf = StringIO()
        with redirect_stdout(buf):
            code = version4.main(argv)
        return code, buf.getvalue().strip()

    def test_measure_command(self):
        repo = MeasureTest()._repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        code, out = self._run_main(["measure", "--root", repo])
        self.assertEqual(code, 0)
        self.assertEqual(out, "6 0")

    def test_next_command_measures_then_reuses(self):
        repo = MeasureTest()._repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        _tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, _tmp, ignore_errors=True)
        cache = os.path.join(_tmp, "token-measure.txt")
        code, out = self._run_main(
            ["next", "3.15.0.5", "--root", repo, "--cache", cache,
             "--now", str(NOW)])
        self.assertEqual((code, out), (0, "3.15.0.6"))
        self.assertEqual(version4.read_measure_cache(cache), (NOW, 0))
        # 1 hour later: inside the window, the cache is reused and
        # not rewritten even though nothing about the tree changed.
        code, out = self._run_main(
            ["next", "3.15.0.6", "--root", repo, "--cache", cache,
             "--now", str(NOW + 3600)])
        self.assertEqual((code, out), (0, "3.15.0.7"))
        self.assertEqual(version4.read_measure_cache(cache), (NOW, 0))

    def _grow_repo_past_a_million(self, repo):
        with open(os.path.join(repo, "big.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("x " * 1000001)  # 1,000,001 tokens on its own
        _git(repo, "add", "big.txt")

    def test_next_command_reuse_ignores_tree_change_inside_window(self):
        # The unchanged reuse path, proven against a tree that grew
        # past the next million inside the window: without --fresh
        # the cached figure still rules and the cache is untouched.
        repo = MeasureTest()._repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        _tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, _tmp, ignore_errors=True)
        cache = os.path.join(_tmp, "token-measure.txt")
        code, out = self._run_main(
            ["next", "3.15.0.5", "--root", repo, "--cache", cache,
             "--now", str(NOW)])
        self.assertEqual((code, out), (0, "3.15.0.6"))
        self._grow_repo_past_a_million(repo)
        code, out = self._run_main(
            ["next", "3.15.0.6", "--root", repo, "--cache", cache,
             "--now", str(NOW + 3600)])
        self.assertEqual((code, out), (0, "3.15.0.7"))
        self.assertEqual(version4.read_measure_cache(cache), (NOW, 0))

    def test_next_command_fresh_recounts_inside_window(self):
        # The ship flow's path (the owner's rule, 8-Nov-2026):
        # --fresh ignores a cache still inside its 24-hour window,
        # recounts the tree as it stands, and rewrites the cache
        # with the fresh measure.
        repo = MeasureTest()._repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        _tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, _tmp, ignore_errors=True)
        cache = os.path.join(_tmp, "token-measure.txt")
        code, out = self._run_main(
            ["next", "3.15.0.5", "--root", repo, "--cache", cache,
             "--now", str(NOW)])
        self.assertEqual((code, out), (0, "3.15.0.6"))
        self._grow_repo_past_a_million(repo)
        # 1 hour after the cached measure — deep inside the window —
        # --fresh still recounts: the figure moves to 1, the counter
        # restarts, and the cache carries the fresh measure.
        code, out = self._run_main(
            ["next", "3.15.0.6", "--root", repo, "--cache", cache,
             "--now", str(NOW + 3600), "--fresh"])
        self.assertEqual((code, out), (0, "3.15.1.1"))
        self.assertEqual(version4.read_measure_cache(cache),
                         (NOW + 3600, 1))

    def test_next_command_fresh_cache_records_the_measure(self):
        # A cut whose fresh recount lands under the standing
        # figure: the version holds its figure (the counter
        # increments), but the cache records the measure that was
        # actually taken — it is the record of the last measure,
        # not of the figure the version carries.
        repo = MeasureTest()._repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        _tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, _tmp, ignore_errors=True)
        cache = os.path.join(_tmp, "token-measure.txt")
        self._grow_repo_past_a_million(repo)
        code, out = self._run_main(
            ["next", "3.15.0.5", "--root", repo, "--cache", cache,
             "--now", str(NOW), "--fresh"])
        self.assertEqual((code, out), (0, "3.15.1.1"))
        self.assertEqual(version4.read_measure_cache(cache), (NOW, 1))
        _git(repo, "rm", "-q", "--cached", "big.txt")
        os.remove(os.path.join(repo, "big.txt"))
        code, out = self._run_main(
            ["next", "3.15.1.1", "--root", repo, "--cache", cache,
             "--now", str(NOW + 3600), "--fresh"])
        self.assertEqual((code, out), (0, "3.15.1.2"))
        self.assertEqual(version4.read_measure_cache(cache),
                         (NOW + 3600, 0))

    def test_next_command_stale_cache_measures_and_rewrites(self):
        # The non-fresh form of the measured path the typecheck
        # guard flagged: a cache older than the 24-hour window is
        # stale, so the command measures, and the cache is
        # rewritten with that measure — the write happens exactly
        # when a fresh figure exists to record.
        repo = MeasureTest()._repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        _tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, _tmp, ignore_errors=True)
        cache = os.path.join(_tmp, "token-measure.txt")
        code, out = self._run_main(
            ["next", "3.15.0.5", "--root", repo, "--cache", cache,
             "--now", str(NOW)])
        self.assertEqual((code, out), (0, "3.15.0.6"))
        self.assertEqual(version4.read_measure_cache(cache), (NOW, 0))
        self._grow_repo_past_a_million(repo)
        later = NOW + version4.MEASURE_WINDOW_SEC + 3600
        code, out = self._run_main(
            ["next", "3.15.0.6", "--root", repo, "--cache", cache,
             "--now", str(later)])
        self.assertEqual((code, out), (0, "3.15.1.1"))
        self.assertEqual(version4.read_measure_cache(cache), (later, 1))

    def test_next_command_fresh_without_cache_measures(self):
        repo = MeasureTest()._repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        code, out = self._run_main(
            ["next", "3.15.0.5", "--root", repo, "--fresh",
             "--now", str(NOW)])
        self.assertEqual((code, out), (0, "3.15.0.6"))

    def test_next_command_minor_bump_restarts_counter(self):
        # The rev the scheme holds in reserve, driven through the
        # CLI the ship flow actually calls: --minor above the
        # standing line moves the release to the new line and
        # restarts the counter at 1, carrying the measured figure.
        repo = MeasureTest()._repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        code, out = self._run_main(
            ["next", "3.15.0.5", "--root", repo, "--fresh",
             "--now", str(NOW), "--minor", "16"])
        self.assertEqual((code, out), (0, "3.16.0.1"))

    def test_next_command_minor_bump_takes_the_fresh_figure(self):
        # The ship flow's shape for a rev cut: --fresh recounts
        # the tree as it stands, and the new line's first release
        # carries that fresh figure, not the old line's.
        repo = MeasureTest()._repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        self._grow_repo_past_a_million(repo)
        code, out = self._run_main(
            ["next", "3.15.0.5", "--root", repo, "--fresh",
             "--now", str(NOW), "--minor", "16"])
        self.assertEqual((code, out), (0, "3.16.1.1"))

    def test_next_command_same_minor_flag_is_not_a_restart(self):
        # --minor naming the standing line is a no-op: the counter
        # increments exactly as if the flag were absent, so passing
        # the flag one cut too late cannot restart a line by
        # accident.
        repo = MeasureTest()._repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        code, out = self._run_main(
            ["next", "3.15.0.5", "--root", repo, "--fresh",
             "--now", str(NOW), "--minor", "15"])
        self.assertEqual((code, out), (0, "3.15.0.6"))

    def test_next_command_minor_decrease_rejected(self):
        # A --minor below the standing line is refused at the CLI
        # seam too: the odometer never runs backwards.
        repo = MeasureTest()._repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        with self.assertRaises(ValueError):
            self._run_main(
                ["next", "3.15.0.5", "--root", repo, "--fresh",
                 "--now", str(NOW), "--minor", "14"])

    def test_cache_write_is_narrowed_for_the_type_checker(self):
        # The measured path's cache write passes `fresh`, which is
        # None until a measure happens. The typecheck guard
        # (pyrefly, in the build workflow) flagged the call when
        # the write was guarded only by the `measured` flag: a
        # boolean cannot narrow Optional[int] to int. The call
        # must stay under an explicit `fresh is not None` guard so
        # the checked shape and the runtime shape stay the same.
        with open(version4.__file__, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        writes = [i for i, line in enumerate(lines)
                  if "write_measure_cache(cache, now, fresh)" in line]
        self.assertEqual(1, len(writes))
        guards = [line.strip() for line in lines[:writes[0]]
                  if line.strip().startswith("if ")]
        self.assertIn("fresh is not None", guards[-1])

    def test_usage_errors(self):
        code, _ = self._run_main([])
        self.assertEqual(code, 2)
        code, _ = self._run_main(["next"])
        self.assertEqual(code, 2)
        code, _ = self._run_main(["bogus"])
        self.assertEqual(code, 2)


class CurrentTreeTest(unittest.TestCase):
    def test_standing_version_is_four_component(self):
        import re

        import runner
        root = os.path.dirname(os.path.dirname(
            os.path.abspath(runner.__file__)))
        with open(os.path.join(root, "pyproject.toml"),
                  encoding="utf-8") as fh:
            text = fh.read()
        current = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1)
        parts = version4.parse(current)
        # The standing shape every release keeps: the major stays 3,
        # the minor is the 15 line, the token figure is measured, and
        # the counter is a live release counter. The 3.15.148
        # conversion itself (counter 148 carried over) is pinned by
        # the convert_legacy tests above with fixed inputs; pinning
        # the counter here would fail every later release.
        self.assertEqual(parts[0], 3)
        self.assertEqual(parts[1], 15)
        self.assertGreaterEqual(parts[2], 1)
        self.assertGreaterEqual(parts[3], 1)


if __name__ == "__main__":
    unittest.main()
