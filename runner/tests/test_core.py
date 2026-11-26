# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Core (runner/ops/core.py): the production runner as a named set.

CORE_FILES is the canonical list of the stripped
production-runner set — the set "test core" means. The pins:
every listed file exists, no test file or harness is listed,
the list is sorted and duplicate-free, the zip build is
deterministic and carries exactly the listed files, the line
count is computed live and pinned against the recorded
as-assembled figures, the recorded as-assembled zip size is
pinned against a live build of the as-assembled set (the
canonical list plus the 3 suite runners), the per-part
breakdown sums to the total and differs from the recorded
one in runner/tools only, and the CLI prints its figure
lines in shape.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "runner"))

from ops import core  # noqa: E402

from runner.tests.mutant_copy import skip_in_mutant_copy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))

SUITE_RUNNERS = (
    "runner/tools/run_tests_parallel.py",
    "runner/tools/run_tests_shuffled.py",
    "runner/tools/run_tests_windows_sim.py",
)

# The as-assembled set the recorded figures describe: the
# canonical list plus the 3 suite runners, sorted as one
# list -- the construction the release train's own re-record
# (record_core_measure in runner/tools/release_train.py)
# measures the recorded figures over.
ASSEMBLED_FILES = tuple(sorted(set(core.CORE_FILES) | set(SUITE_RUNNERS)))


class CoreListTest(unittest.TestCase):
    def test_every_listed_file_exists(self):
        missing = [name for name in core.CORE_FILES
                   if not os.path.isfile(os.path.join(ROOT, name))]
        self.assertEqual([], missing)

    def test_count_is_the_corrected_canonical_count(self):
        # 133 as assembled for the 2026-11-04 pass, minus the 3
        # suite runners the definition of core leaves out, plus
        # the 2 briefing files the Oracle briefing work added
        # on 2026-11-08: 135 as assembled, 132 canonical; plus
        # the 2 platform confinement backends (windows_confine,
        # freebsd_confine) registered on 2026-11-10: 137 as
        # assembled, 134 canonical; plus the disclosure
        # posture module the posture stamp producer wired
        # into the runner on 2026-11-10: 138 as assembled,
        # 135 canonical; plus the macOS confinement backend
        # (macos_confine) registered on 2026-11-11: 139 as
        # assembled, 136 canonical; plus the build identity
        # module (ops/identity) registered on 2026-11-15: 140
        # as assembled, 137 canonical; plus the shared trust
        # store (wire/tls) registered on 2026-11-20: 141 as
        # assembled, 138 canonical; plus the signup module
        # (cloud/signup) registered on 2026-11-20: 142 as
        # assembled, 139 canonical.
        self.assertEqual(142, core.AS_ASSEMBLED_FILES)
        self.assertEqual(139, len(core.CORE_FILES))

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
        # re-recorded at the 2026-11-05 re-measures and again
        # at the 2026-11-10 re-measure that corrected the Q134
        # entry's figures and took up the trial staging fix,
        # and again at the 2026-11-10 re-measures that took up
        # the briefing's contradiction mark and the posture
        # stamp producer, and again on 2026-11-20 at the
        # re-measure that took up the install record's CPU
        # fact; the Gemini token count above still
        # describes the 2026-11-04 assembly.
        self.assertEqual(945248, core.AS_ASSEMBLED_ZIP_BYTES)

    def test_the_recorded_line_measure_stays_named(self):
        # Re-measured 2026-11-05, after the Q-new runner fixes
        # grew 4 of the set's files, and again after the
        # CHECKLIST-04 send_job fixes grew runner/cloud, and
        # again on 2026-11-06 after the signed-body strictness
        # fix grew runner/guard and the audit hash-chain fix
        # grew runner/guard and runner/ops, and once more the
        # same day after the Oracle tool-mode work and the
        # startup posture assertion switch grew runner/ops,
        # runner/guard and the runner proper, and once more
        # after the outbox stash took the per-key guard in
        # the runner proper, and again after the fy_iceworld
        # fragment-buffer caps grew runner/wire, and again
        # after the temp-reaping work grew runner/ops,
        # runner/tools, runner/guard and the runner proper,
        # and again after the repair-note cap fix grew
        # runner/oracle, and again after the world-readable
        # secret-file check grew runner/wire, and again after
        # the DTLS record-layer and framing work grew
        # runner/wire, runner/guard, runner/ops,
        # runner/transport_extensions and the runner proper,
        # and again on 2026-11-07 after the job_user startup
        # gate took its POSIX branches (Q132) and the
        # confinement startup trial took the configured
        # extra_flags (Q133), growing runner/ops and
        # runner/guard, and after the stamp audit took its
        # historical-signings acceptance, growing
        # runner/tools, and again on 2026-11-08 after the
        # personal-documents shelter marker grew
        # runner/oracle and the shelter's security-mode
        # feature grew runner/guard, and again on 2026-11-08
        # after the Oracle briefing (shape 4) added
        # runner/ops/briefing.py and runner/tools/
        # make_briefing.py to the canonical list and its
        # wiring grew runner/ops, runner/tools and the
        # runner proper, and again on 2026-11-09 after the
        # default-posture measurement corrected a comment in
        # runner/ops/main.py, growing runner/ops by 1 line,
        # and again on 2026-11-10 after the platform
        # confinement backends (windows_confine,
        # freebsd_confine) joined the canonical list and
        # their wiring grew runner/ops and the runner
        # proper, the whole set re-measured over the
        # current tree, and again the same day after the
        # FreeBSD backend's field-test mount fix grew
        # runner/guard, and again the same day after the
        # Windows backend's import-safety change grew
        # runner/guard/windows_confine.py by 15 lines, and
        # again the same day after the Q134 confinement
        # trial grew runner/guard -- that entry's figures
        # recorded the set below the tree it stood on
        # (runner/ops by 11 lines, runner/guard by 5, the
        # runner proper by 8) and are corrected at this
        # re-measure -- and again the same day after the
        # Q134 trial's staging fix grew
        # runner/guard/windows_confine.py, and again the
        # same day after the briefing's contradiction mark
        # (the Q138 build) grew runner/ops/briefing.py and
        # runner/ops/startup.py and the runner proper, and
        # again the same day after the posture stamp
        # producer (Q137) wired the runner to the
        # disclosure module and runner/tools/disclosure.py
        # joined the canonical list, growing runner/ops,
        # runner/tools and the runner proper, and again
        # the same day after the job_user postspawn fix
        # grew runner/ops/remediation_ops.py by 36 lines,
        # which that landing left unrecorded, and again
        # the same day after the macOS confinement fourth
        # fix grew runner/guard/macos_confine.py by 102
        # lines, and again on 2026-11-12 after the macOS
        # confinement spawn-limits fix grew
        # runner/guard/macos_confine.py by 48 lines, the
        # whole set re-measured over the current tree, and
        # again on 2026-11-14 after the FreeBSD confinement
        # backend's second shape grew
        # runner/guard/freebsd_confine.py by 814 lines,
        # runner/guard/sandbox.py by 14 and
        # runner/ops/remediation_ops.py by 13, and again the
        # same day after the posture report's FreeBSD line
        # grew runner/guard/freebsd_confine.py by 31 lines
        # and runner/ops/posture.py by 20, and again the
        # same day after the FreeBSD seed took to asking
        # the machine grew runner/ops/install.py by 221
        # lines and runner/ops/setup.py by 37, over a tree
        # that also carries the query worker's start
        # allowance (runner/ops/queries.py by 28 lines, the
        # runner proper by 1), and again the same day after
        # the seed took to naming a job user where it leaves
        # the jail on grew runner/ops/install.py by 212
        # lines, runner/guard/freebsd_confine.py by 27 and
        # runner/ops/setup.py by 13, and again the same day
        # after the installer took to making the account
        # that seed names grew runner/ops/install.py by 144
        # lines and runner/ops/setup.py by 4, over a tree
        # that also carries the briefing's spaced-token rule
        # (runner/ops/briefing.py by 10 lines), and again the
        # same day after the seed's questions to the machine
        # took a switch in the environment grew
        # runner/ops/install.py by 33 lines, and once more
        # after the job user's process ceiling grew
        # runner/guard/freebsd_confine.py by 131 lines and
        # runner/ops/install.py by 21, and the release's
        # collecting of the job's first process grew the
        # backend by 12 more, and again on
        # 2026-11-15 after the regression guard's leak run
        # took to starting a module through the test package
        # grew runner/tools/regression_guard.py by 7 lines,
        # and again that day after a job's jail took to being
        # pinned to a set of cores grew
        # runner/guard/freebsd_confine.py by 191 lines, and
        # by 41 more when a runner kept to some of its cores
        # took to pinning its jobs' jails to its own, over a
        # tree that also carries the setup wizard's third
        # sign-in choice (runner/ops/setup.py by 187 lines),
        # and again on 2026-11-15 after the build identity
        # banner grew runner/runner.py by 25 lines,
        # runner/ops by 70, runner/wire by 14 and
        # runner/cloud by 18, and the identity module itself
        # (runner/ops/identity.py, 148 lines) joined the set,
        # and again the same day after the setup wizard's
        # client-secret step grew runner/ops/setup.py by
        # 37 lines net (Q197).
        # Again that day, after the macOS backend's
        # launcher became the system shell and its memory
        # ceiling became one a job meets, the set grew by
        # runner/guard/macos_confine.py's 341 lines and
        # runner/guard/sandbox.py's 7, and by 148 in
        # runner/ops for the seed that asks that backend
        # (the macOS launcher landing).
        # Again that day, after the hosted Macs answered
        # the landing, by 30 lines more of
        # runner/guard/macos_confine.py (the hosted run's
        # two answers).
        # And when the profile came to name the services
        # of the session a job may look up, by 161 lines
        # of runner/guard/macos_confine.py, 1 of
        # runner/ops/install.py and 1 of
        # runner/ops/remediation_ops.py (the session's
        # services).
        # Again that day, after the hosted Macs answered
        # that landing, by 2 lines more of
        # runner/guard/macos_confine.py (the hosted run's
        # answer on the pasteboard).
        # On 2026-11-16, after a copy of the installer
        # started by path came to speak for its own tree
        # beside a stale install, by 26 lines of
        # runner/ops/install.py, 11 of
        # runner/guard/freebsd_confine.py and 11 of
        # runner/guard/sandbox.py (the seed's own tree).
        # Again that day, after the retained store came to
        # keep two records whose job ids differ only in
        # case on a filesystem that folds case, by 62
        # lines of runner/runner.py (the retained store's
        # case-folded sibling).
        # Again that day, after the pre-push guard came to
        # read these figures against the tree on every
        # run, by 29 lines of
        # runner/tools/regression_guard.py (the guard's
        # core check).
        # On 2026-11-20, after the install record came to
        # name the machine's CPU beside its memory and
        # its hard drive, by 33 lines of
        # runner/ops/setup.py (the setup wizard's system
        # facts).
        self.assertEqual(73435, core.AS_ASSEMBLED_LINES)
        self.assertEqual(66635, core.AS_ASSEMBLED_NONBLANK_LINES)
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
                # The stored bytes the reader returns, not the
                # raw checkout bytes: on a CRLF checkout the
                # raw bytes are the converted ones, and the
                # entries carry the stored ones (Q199).
                self.assertEqual(
                    core._read_core_file(ROOT, name), zf.read(name),
                    name)

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

    # -- the live pin on the recorded as-assembled zip size --
    # The line figures have a live guard in CorePartsTest: the
    # recorded parts are compared against a live count, so a
    # stale line figure stands red. The zip figure had no such
    # guard, and it drifted stale through four landings while
    # every other figure in the same refreshes checked live
    # (Q199). These tests give it the same guard.

    def _assert_recorded_zip_size_matches_a_live_build(self):
        data = core.core_zip_bytes(ROOT, files=ASSEMBLED_FILES)
        self.assertEqual(core.AS_ASSEMBLED_ZIP_BYTES, len(data))

    def test_the_as_assembled_set_is_the_canonical_list_plus_the_suite_runners(self):
        self.assertEqual(core.AS_ASSEMBLED_FILES, len(ASSEMBLED_FILES))
        self.assertEqual(sorted(ASSEMBLED_FILES), list(ASSEMBLED_FILES))
        self.assertEqual(len(set(ASSEMBLED_FILES)), len(ASSEMBLED_FILES))
        self.assertEqual(set(SUITE_RUNNERS),
                         set(ASSEMBLED_FILES) - set(core.CORE_FILES))
        self.assertTrue(set(core.CORE_FILES) < set(ASSEMBLED_FILES))

    def test_recorded_zip_size_matches_a_live_as_assembled_build(self):
        # Inside a mutant copy the mutated file carries one copy
        # per mutant, so a live build is the copy's, not the
        # tree's (Q170); see the lines test in CoreLinesTest.
        skip_in_mutant_copy(self)
        self._assert_recorded_zip_size_matches_a_live_build()

    def test_as_assembled_zip_build_is_deterministic(self):
        first = core.core_zip_bytes(ROOT, files=ASSEMBLED_FILES)
        second = core.core_zip_bytes(ROOT, files=ASSEMBLED_FILES)
        self.assertEqual(first, second)

    def test_as_assembled_zip_contains_exactly_the_as_assembled_files(self):
        data = core.core_zip_bytes(ROOT, files=ASSEMBLED_FILES)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            self.assertEqual(list(ASSEMBLED_FILES), zf.namelist())

    def test_a_stale_recorded_zip_size_fails_the_pin(self):
        # The pin's comparison, handed the figures a stale record
        # would carry: the drifted figure Q199 filed (894,316) and
        # the figures one byte to either side of the live one.
        # Each must fail; the true constant, checked by the pin
        # test above, passes.
        skip_in_mutant_copy(self)
        live = len(core.core_zip_bytes(ROOT, files=ASSEMBLED_FILES))
        for stale in (894316, live - 1, live + 1):
            with self.subTest(stale=stale):
                with mock.patch.object(
                        core, "AS_ASSEMBLED_ZIP_BYTES", stale):
                    with self.assertRaises(AssertionError):
                        self._assert_recorded_zip_size_matches_a_live_build()

    def test_a_grown_core_file_moves_the_as_assembled_zip_size(self):
        # The drift shape itself, on a copy of the tree: the copy
        # builds to the recorded figure, and the same copy with
        # one core file grown builds to another size -- so a
        # landing that grows the core without re-recording the
        # zip stands red under the pin above, not merely a
        # landing that edits the constant.
        skip_in_mutant_copy(self)
        with tempfile.TemporaryDirectory() as tmp:
            for name in ASSEMBLED_FILES:
                dest = os.path.join(tmp, name)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copyfile(os.path.join(ROOT, name), dest)
            before = core.core_zip_bytes(tmp, files=ASSEMBLED_FILES)
            self.assertEqual(core.AS_ASSEMBLED_ZIP_BYTES, len(before))
            with open(os.path.join(tmp, "runner", "runner.py"),
                      "a", encoding="utf-8") as fh:
                fh.write("# a landing that grows the core\n")
            after = core.core_zip_bytes(tmp, files=ASSEMBLED_FILES)
            self.assertNotEqual(len(before), len(after))
            self.assertNotEqual(core.AS_ASSEMBLED_ZIP_BYTES, len(after))

    # -- the checkout shape (Q199, the ship lane's re-test) --
    # The pin above was measured on a Linux tree and stood
    # red on the hosted Windows leg: a checkout that
    # converts line endings (Git for Windows' autocrlf)
    # handed the builder CRLF bytes, and the live build
    # read 902,401 against the recorded 896,433. The
    # reader now folds CRLF back to the stored bytes, so
    # the recorded figure is a property of the stored
    # tree, not of the checkout. These tests reproduce
    # the converted tree on any platform.

    def test_a_crlf_checked_out_tree_builds_the_same_zip(self):
        skip_in_mutant_copy(self)
        with tempfile.TemporaryDirectory() as tmp:
            for name in ASSEMBLED_FILES:
                dest = os.path.join(tmp, name)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(os.path.join(ROOT, name), "rb") as fh:
                    stored = fh.read().replace(b"\r\n", b"\n")
                with open(dest, "wb") as fh:
                    fh.write(stored.replace(b"\n", b"\r\n"))
            converted = core.core_zip_bytes(tmp, files=ASSEMBLED_FILES)
            self.assertEqual(core.AS_ASSEMBLED_ZIP_BYTES,
                             len(converted))
            self.assertEqual(
                core.core_zip_bytes(ROOT, files=ASSEMBLED_FILES),
                converted)

    def test_the_reader_folds_crlf_to_the_stored_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "one.py"), "wb") as fh:
                fh.write(b"one\r\ntwo\r\n")
            self.assertEqual(b"one\ntwo\n",
                             core._read_core_file(tmp, "one.py"))

    def test_the_reader_keeps_a_lone_carriage_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "one.py"), "wb") as fh:
                fh.write(b"one\rtwo\n")
            self.assertEqual(b"one\rtwo\n",
                             core._read_core_file(tmp, "one.py"))

    def test_the_reader_passes_stored_bytes_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "one.py"), "wb") as fh:
                fh.write(b"one\ntwo\n")
            self.assertEqual(b"one\ntwo\n",
                             core._read_core_file(tmp, "one.py"))


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
        # Inside a mutant copy the mutated file carries one copy
        # per mutant, so the live count is the copy's, not the
        # tree's (Q170).
        skip_in_mutant_copy(self)
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
        self.assertEqual(7444, core.AS_ASSEMBLED_PART_LINES["runner/runner.py"])
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
        # The guard part's live count is the mutant copy's own
        # inside mutmut's tree (Q170); see the lines test above.
        skip_in_mutant_copy(self)
        parts = core.measure_core_lines_by_part(ROOT)
        self.assertEqual(set(core.AS_ASSEMBLED_PART_LINES), set(parts))
        for part, recorded in core.AS_ASSEMBLED_PART_LINES.items():
            if part == "runner/tools":
                # The 3 excluded suite runners: 1119 lines.
                self.assertEqual(recorded - 1119, parts[part])
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
        self.assertEqual("core files: 139", lines[0])
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
            self.assertIn("core files: 139", out)

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
            proc.stdout.startswith("core files: 139\n"), proc.stdout)


if __name__ == "__main__":
    unittest.main()
