# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Core (runner/ops/core.py): the production runner as a named set.

CORE_FILES is the canonical list of the stripped
production-runner set — the set "test core" means. The pins:
every listed file exists, no test file or harness is listed,
the list is sorted and duplicate-free, the zip build is
deterministic and carries exactly the listed files, the line
count is computed live and pinned against the recorded
as-assembled figures, and the CLI prints its 5 figure lines
in shape.
"""
import io
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "runner"))

from ops import core  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))

SUITE_RUNNERS = (
    "runner/tools/run_tests_parallel.py",
    "runner/tools/run_tests_shuffled.py",
    "runner/tools/run_tests_windows_sim.py",
)


class CoreListTest(unittest.TestCase):
    def test_every_listed_file_exists(self):
        missing = [name for name in core.CORE_FILES
                   if not os.path.isfile(os.path.join(ROOT, name))]
        self.assertEqual([], missing)

    def test_count_is_the_corrected_canonical_count(self):
        # 133 as assembled for the 2026-11-04 pass, minus the 3
        # suite runners the definition of core leaves out.
        self.assertEqual(133, core.AS_ASSEMBLED_FILES)
        self.assertEqual(130, len(core.CORE_FILES))

    def test_list_is_sorted_and_duplicate_free(self):
        files = list(core.CORE_FILES)
        self.assertEqual(sorted(files), files)
        self.assertEqual(len(set(files)), len(files))

    def test_every_path_is_under_runner(self):
        for name in core.CORE_FILES:
            self.assertTrue(name.startswith("runner/"), name)

    def test_no_test_file_or_harness_is_listed(self):
        for name in core.CORE_FILES:
            base = os.path.basename(name)
            self.assertFalse(name.startswith("runner/tests/"), name)
            self.assertNotIn("/tests/", name)
            self.assertFalse(base.startswith("test_"), name)
            self.assertNotIn("run_tests", name)

    def test_the_suite_runners_are_excluded_by_name(self):
        for name in SUITE_RUNNERS:
            self.assertNotIn(name, core.CORE_FILES)
            # They exist in the tree; the exclusion is a decision
            # about the set, not an absence.
            self.assertTrue(os.path.isfile(os.path.join(ROOT, name)), name)

    def test_the_recorded_gemini_measure_stays_named(self):
        self.assertEqual(619845, core.GEMINI_COUNT_TOKENS)
        self.assertEqual("2026-11-04", core.GEMINI_COUNT_DATE)
        self.assertEqual(701403, core.AS_ASSEMBLED_ZIP_BYTES)

    def test_the_recorded_line_measure_stays_named(self):
        self.assertEqual(54427, core.AS_ASSEMBLED_LINES)
        self.assertEqual(48981, core.AS_ASSEMBLED_NONBLANK_LINES)
        self.assertLess(core.AS_ASSEMBLED_NONBLANK_LINES,
                        core.AS_ASSEMBLED_LINES)


class CoreZipTest(unittest.TestCase):
    def test_zip_build_is_deterministic(self):
        first = core.core_zip_bytes(ROOT)
        second = core.core_zip_bytes(ROOT)
        self.assertEqual(first, second)

    def test_zip_contains_exactly_the_listed_files(self):
        data = core.core_zip_bytes(ROOT)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            self.assertEqual(list(core.CORE_FILES), zf.namelist())

    def test_zip_entries_carry_the_fixed_timestamp(self):
        data = core.core_zip_bytes(ROOT)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                self.assertEqual((1980, 1, 1, 0, 0, 0), info.date_time)

    def test_zip_entries_match_the_tree_bytes(self):
        data = core.core_zip_bytes(ROOT)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in ("runner/__init__.py", "runner/runner.py",
                         "runner/wire/verify.py"):
                with open(os.path.join(ROOT, name), "rb") as fh:
                    self.assertEqual(fh.read(), zf.read(name), name)

    def test_build_writes_the_same_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "core.zip")
            size = core.build_core_zip(ROOT, out)
            with open(out, "rb") as fh:
                self.assertEqual(core.core_zip_bytes(ROOT), fh.read())
            self.assertEqual(size, os.path.getsize(out))

    def test_a_missing_listed_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                core.core_zip_bytes(tmp, files=("runner/__init__.py",))


class CoreMeasureTest(unittest.TestCase):
    def test_measure_counts_with_the_project_estimator(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "one.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("hello world 123\n")
            # Estimator rule: "hello", "world", "123" — 3 tokens.
            self.assertEqual(
                3, core.measure_core_tokens(tmp, files=("one.py",)))

    def test_measure_of_the_tree_is_positive_and_below_the_tree(self):
        total = core.measure_core_tokens(ROOT)
        self.assertGreater(total, 0)
        self.assertLess(total, 17716094)


class CoreLinesTest(unittest.TestCase):
    def test_lines_counted_on_a_known_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "one.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("one\n\n   \ntwo\n")
            # 4 lines; "one" and "two" are non-blank.
            self.assertEqual(
                (4, 2), core.measure_core_lines(tmp, files=("one.py",)))

    def test_the_canonical_set_is_smaller_than_the_record(self):
        total, nonblank = core.measure_core_lines(ROOT)
        self.assertGreater(total, 0)
        self.assertGreater(nonblank, 0)
        self.assertLess(nonblank, total)
        # The canonical list is a strict subset of the recorded
        # as-assembled set, so its live count sits below it.
        self.assertLess(total, core.AS_ASSEMBLED_LINES)
        self.assertLess(nonblank, core.AS_ASSEMBLED_NONBLANK_LINES)

    def test_lines_match_an_independent_count(self):
        total = 0
        nonblank = 0
        for name in core.CORE_FILES:
            with open(os.path.join(ROOT, name), "rb") as fh:
                lines = fh.read().decode("utf-8", "replace").splitlines()
            total += len(lines)
            nonblank += sum(1 for line in lines if line.strip())
        self.assertEqual((total, nonblank), core.measure_core_lines(ROOT))


class CoreCliTest(unittest.TestCase):
    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = core.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_cli_output_shape(self):
        rc, out, _err = self._run(["--root", ROOT])
        self.assertEqual(0, rc)
        lines = out.strip().splitlines()
        self.assertEqual(5, len(lines))
        self.assertEqual("core files: 130", lines[0])
        total, nonblank = core.measure_core_lines(ROOT)
        self.assertEqual(
            "core lines: %d (%d non-blank)" % (total, nonblank), lines[1])
        self.assertTrue(lines[2].startswith("core zip bytes: "), lines[2])
        self.assertGreater(int(lines[2].split(": ")[1]), 0)
        self.assertTrue(
            lines[3].startswith("core tokens (project estimator): "),
            lines[3])
        self.assertEqual(core.measure_core_tokens(ROOT),
                         int(lines[3].split(": ")[1]))
        self.assertEqual(
            "core tokens (Gemini countTokens, 2026-11-04): 619845",
            lines[4])

    def test_cli_build_writes_the_zip_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_zip = os.path.join(tmp, "out.zip")
            rc, out, _err = self._run(["build", out_zip, "--root", ROOT])
            self.assertEqual(0, rc)
            with zipfile.ZipFile(out_zip) as zf:
                self.assertEqual(list(core.CORE_FILES), zf.namelist())
            self.assertIn("core files: 130", out)

    def test_cli_rejects_an_unknown_command(self):
        rc, _out, err = self._run(["frobnicate"])
        self.assertEqual(2, rc)
        self.assertIn("usage:", err)

    def test_cli_missing_core_file_is_a_failure_not_a_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, _out, err = self._run(["--root", tmp])
            self.assertEqual(1, rc)
            self.assertIn("core file missing", err)


if __name__ == "__main__":
    unittest.main()
