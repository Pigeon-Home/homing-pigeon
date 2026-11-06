# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Core (runner/ops/core.py): the production runner as a named set.

CORE_FILES is the canonical list of the stripped
production-runner set — the set "test core" means. The pins:
every listed file exists, no test file or harness is listed,
the list is sorted and duplicate-free, the zip build is
deterministic and carries exactly the listed files, the line
count is computed live and pinned against the recorded
as-assembled figures, the per-part breakdown sums to the
total and differs from the recorded one in runner/tools
only, and the CLI prints its figure lines in shape.
"""
import io
import os
import subprocess
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
        # The zip size is this module's own deterministic build,
        # re-recorded at the 2026-11-05 re-measures; the Gemini
        # token count above still describes the 2026-11-04
        # assembly.
        self.assertEqual(700490, core.AS_ASSEMBLED_ZIP_BYTES)

    def test_the_recorded_line_measure_stays_named(self):
        # Re-measured 2026-11-05, after the Q-new runner fixes
        # grew 4 of the set's files, and again after the
        # CHECKLIST-04 send_job fixes grew runner/cloud, and
        # again on 2026-11-06 after the signed-body strictness
        # fix grew runner/guard and the audit hash-chain fix
        # grew runner/guard and runner/ops, and once more the
        # same day after the Oracle tool-mode work and the
        # startup posture assertion switch grew runner/ops,
        # runner/guard and the runner proper.
        self.assertEqual(55299, core.AS_ASSEMBLED_LINES)
        self.assertEqual(49787, core.AS_ASSEMBLED_NONBLANK_LINES)
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


class CorePartsTest(unittest.TestCase):
    def test_the_recorded_breakdown_stays_named(self):
        self.assertEqual(6598, core.AS_ASSEMBLED_PART_LINES["runner/runner.py"])
        self.assertEqual(core.AS_ASSEMBLED_LINES,
                         sum(core.AS_ASSEMBLED_PART_LINES.values()))

    def test_parts_sum_to_the_total(self):
        parts = core.measure_core_lines_by_part(ROOT)
        total, _nonblank = core.measure_core_lines(ROOT)
        self.assertEqual(total, sum(parts.values()))

    def test_the_runner_proper_is_counted_live(self):
        parts = core.measure_core_lines_by_part(ROOT)
        with open(os.path.join(ROOT, "runner/runner.py"), "rb") as fh:
            own = len(fh.read().decode("utf-8", "replace").splitlines())
        self.assertEqual(own, parts["runner/runner.py"])

    def test_the_canonical_breakdown_differs_in_tools_only(self):
        parts = core.measure_core_lines_by_part(ROOT)
        self.assertEqual(set(core.AS_ASSEMBLED_PART_LINES), set(parts))
        for part, recorded in core.AS_ASSEMBLED_PART_LINES.items():
            if part == "runner/tools":
                # The 3 excluded suite runners: 784 lines.
                self.assertEqual(recorded - 784, parts[part])
            else:
                self.assertEqual(recorded, parts[part], part)

    def test_parts_on_a_known_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "runner", "ops"))
            with open(os.path.join(tmp, "runner", "ops", "a.py"),
                      "w", encoding="utf-8") as fh:
                fh.write("a\nb\n")
            with open(os.path.join(tmp, "runner", "runner.py"),
                      "w", encoding="utf-8") as fh:
                fh.write("x\n")
            parts = core.measure_core_lines_by_part(
                tmp, files=("runner/ops/a.py", "runner/runner.py"))
            self.assertEqual(
                {"runner/ops": 2, "runner/runner.py": 1}, parts)


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
        parts = core.measure_core_lines_by_part(ROOT)
        # 4 head lines, 1 line per part, then zip + 2 token lines.
        self.assertEqual(4 + len(parts) + 3, len(lines))
        self.assertEqual("core files: 130", lines[0])
        total, nonblank = core.measure_core_lines(ROOT)
        self.assertEqual(
            "core lines: %d (%d non-blank)" % (total, nonblank), lines[1])
        self.assertEqual(
            "core lines in runner/runner.py: %d" % (parts["runner/runner.py"],),
            lines[2])
        self.assertEqual("core lines by part:", lines[3])
        printed = {}
        for line in lines[4:4 + len(parts)]:
            name, _colon, count = line.strip().rpartition(": ")
            printed[name] = int(count)
        self.assertEqual(parts, printed)
        rest = lines[4 + len(parts):]
        self.assertTrue(rest[0].startswith("core zip bytes: "), rest[0])
        self.assertGreater(int(rest[0].split(": ")[1]), 0)
        self.assertTrue(
            rest[1].startswith("core tokens (project estimator): "),
            rest[1])
        self.assertEqual(core.measure_core_tokens(ROOT),
                         int(rest[1].split(": ")[1]))
        self.assertEqual(
            "core tokens (Gemini countTokens, 2026-11-04): 619845",
            rest[2])

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


class CoreScriptFallbackTest(unittest.TestCase):
    """The plain-script fallback import of version4 (used when
    core.py runs as `python3 runner/ops/core.py`, not as a package
    module) is invisible to pyrefly: version4 is a sibling on
    sys.path only in that mode. The line carries the house-style
    pyrefly suppression for missing-import, so the non-guard
    typecheck job stays clean, and the fallback itself runs."""

    def test_fallback_import_carries_the_pyrefly_suppression(self):
        with open(os.path.join(ROOT, "runner", "ops", "core.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        fallback = [line for line in src.splitlines()
                    if line.strip().startswith("import version4")]
        self.assertEqual(1, len(fallback))
        self.assertIn("pyrefly: ignore[missing-import]", fallback[0])

    def test_core_runs_as_a_plain_script(self):
        proc = subprocess.run(
            [sys.executable,
             os.path.join(ROOT, "runner", "ops", "core.py"),
             "--root", ROOT],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue(
            proc.stdout.startswith("core files: 130\n"), proc.stdout)


if __name__ == "__main__":
    unittest.main()
