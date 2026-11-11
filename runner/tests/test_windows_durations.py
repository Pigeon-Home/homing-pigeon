# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
# Tests for runner/tools/windows_durations.py and the parallel
# runner's --duration-table mode: the duration-balanced
# Windows split.
#
# The split this pins replaced a test-count split whose
# heaviest shard was still running when the 20-minute hang
# guard killed it (2026-11-10, the attempt and the rerun),
# while its siblings finished in 6 to 12 minutes. The
# packer is pinned directly (largest-first, budget, totality,
# determinism, the median default for an unmeasured file);
# the log estimator is pinned on crafted logs; the checked-in
# table is guarded in the shape the workflow runs it.

import contextlib
import importlib.util
import io
import json
import os
import random
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(REPO, relpath))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wd = _load("windows_durations",
           "runner/tools/windows_durations.py")
rtp = _load("run_tests_parallel_for_durations",
            "runner/tools/run_tests_parallel.py")

_PASS = (
    "import unittest\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_one(self):\n"
    "        self.assertTrue(True)\n"
)


def _write(root, name, body):
    with open(os.path.join(root, name), "w", encoding="utf-8") as fh:
        fh.write(body)


def _table_file(directory, durations, budget=720):
    path = os.path.join(directory, "durations.json")
    table = {"budget_seconds": budget, "durations": durations}
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(table))
    return path


def _loads(shards, durations, default=None):
    return wd.shard_loads(shards, durations, default)


class PackModulesTest(unittest.TestCase):
    def test_largest_first_order_is_pinned(self):
        durations = {"a": 100.0, "b": 90.0, "c": 80.0, "d": 10.0}
        shards = wd.pack_modules(["d", "c", "b", "a"], durations, 190.0)
        self.assertEqual(shards, [["a", "d"], ["b", "c"]])
        self.assertEqual(_loads(shards, durations), [110.0, 170.0])

    def test_one_shard_when_the_total_fits(self):
        durations = {"a": 100.0, "b": 90.0, "c": 80.0, "d": 10.0}
        self.assertEqual(
            wd.pack_modules(["a", "b", "c", "d"], durations, 720.0),
            [["a", "b", "c", "d"]])

    def test_the_split_balances_instead_of_filling_in_order(self):
        # The failure shape of a fill-in-order packer: shards
        # at the cap while the last stands nearly empty. Ten
        # heavy files and a tail of small ones must spread.
        durations = {"heavy%02d" % i: 150.0 for i in range(10)}
        durations.update({"small%03d" % i: 1.0 for i in range(100)})
        shards = wd.pack_modules(sorted(durations), durations, 720.0)
        loads = _loads(shards, durations)
        self.assertTrue(all(load <= 720.0 for load in loads))
        self.assertLessEqual(max(loads) - min(loads), 150.0)

    def test_budget_holds_and_packing_is_total_over_random_shapes(
            self):
        rng = random.Random(20261110)
        for _ in range(200):
            names = ["m%03d" % i for i in range(rng.randrange(0, 40))]
            durations = {name: float(rng.randrange(0, 900))
                         for name in names}
            budget = float(rng.choice([60, 300, 720]))
            shards = wd.pack_modules(names, durations, budget)
            flat = [name for shard in shards for name in shard]
            self.assertEqual(sorted(flat), sorted(names))
            self.assertEqual(len(flat), len(set(flat)))
            for shard in shards:
                load = sum(durations[n] for n in shard)
                if load > budget:
                    self.assertEqual(len(shard), 1)
                    self.assertGreater(durations[shard[0]], budget)
            self.assertEqual(shards,
                             wd.pack_modules(names, durations, budget))

    def test_deterministic_under_input_permutation(self):
        durations = {"m%02d" % i: float(37 * i % 500)
                     for i in range(30)}
        names = sorted(durations)
        expected = wd.pack_modules(names, durations, 720.0)
        rng = random.Random(7)
        for _ in range(10):
            shuffled = names[:]
            rng.shuffle(shuffled)
            self.assertEqual(
                wd.pack_modules(shuffled, durations, 720.0), expected)

    def test_an_unmeasured_file_takes_the_median(self):
        durations = {"a": 10.0, "b": 30.0}
        shards = wd.pack_modules(["a", "b", "new"], durations, 100.0)
        self.assertEqual(shards, [["b", "new", "a"]])
        self.assertEqual(wd.default_duration(durations), 20.0)

    def test_an_empty_table_defaults_to_one_second(self):
        self.assertEqual(wd.default_duration({}), 1.0)
        self.assertEqual(wd.pack_modules(["x", "y"], {}, 10.0),
                         [["x", "y"]])

    def test_a_file_over_budget_rides_alone(self):
        durations = {"big": 5000.0, "a": 10.0, "b": 20.0}
        shards = wd.pack_modules(["a", "big", "b"], durations, 720.0)
        self.assertIn(["big"], shards)
        self.assertTrue(all(shards), "no empty shards")
        flat = [n for shard in shards for n in shard]
        self.assertEqual(sorted(flat), ["a", "b", "big"])

    def test_a_file_exactly_at_budget_fits(self):
        durations = {"a": 720.0, "b": 720.0}
        shards = wd.pack_modules(["a", "b"], durations, 720.0)
        self.assertEqual(shards, [["a"], ["b"]])

    def test_zero_duration_files_pack(self):
        durations = {"a": 0.0, "b": 0.0, "c": 5.0}
        self.assertEqual(
            wd.pack_modules(["a", "b", "c"], durations, 10.0),
            [["c", "a", "b"]])

    def test_no_modules_no_shards(self):
        self.assertEqual(wd.pack_modules([], {"a": 1.0}, 720.0), [])

    def test_a_negative_duration_is_rejected(self):
        with self.assertRaises(ValueError):
            wd.pack_modules(["a"], {"a": -1.0}, 720.0)

    def test_a_nonpositive_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            wd.pack_modules(["a"], {"a": 1.0}, 0.0)


class TableValidationTest(unittest.TestCase):
    def _load_text(self, text):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.json")
            _write(d, "t.json", text)
            return wd.load_table_file(path)

    def test_a_valid_table_loads(self):
        table = self._load_text(
            '{"budget_seconds": 720, "durations": {"a": 3}}')
        self.assertEqual(table["budget_seconds"], 720.0)
        self.assertEqual(table["durations"], {"a": 3.0})

    def test_a_missing_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            self._load_text('{"durations": {}}')

    def test_a_negative_duration_is_rejected(self):
        with self.assertRaises(ValueError):
            self._load_text(
                '{"budget_seconds": 720, "durations": {"a": -1}}')

    def test_a_string_duration_is_rejected(self):
        with self.assertRaises(ValueError):
            self._load_text(
                '{"budget_seconds": 720, "durations": {"a": "3"}}')

    def test_a_nan_duration_is_rejected(self):
        with self.assertRaises(ValueError):
            self._load_text(
                '{"budget_seconds": 720, "durations": {"a": NaN}}')

    def test_a_boolean_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            self._load_text(
                '{"budget_seconds": true, "durations": {}}')

    def test_canonical_text_round_trips(self):
        table = {"budget_seconds": 720.0, "wall_minutes": 20,
                 "durations": {"b": 2.0, "a": 1.0}}
        text = wd.table_to_text(table)
        self.assertEqual(wd.table_to_text(json.loads(text)), text)
        self.assertTrue(text.endswith("\n"))
        self.assertLess(text.index('"a"'), text.index('"b"'))


_STEP = "build-windows\tRun python runner/tools/run_tests_parallel.py"


def _gh(body):
    return "%s\t2026-11-10T19:49:15.0000000Z %s" % (_STEP, body)


def _crafted_log():
    lines = [
        _gh("running 10 test(s) from 2 module(s) in 2 shard(s)"),
        _gh("shard 0: 1 module(s): pkg.test_a"),
        _gh("shard 1: 1 module(s): pkg.test_b"),
        _gh("shard 0: OK in 100.1s"),
        _gh("Slowest test durations"),
        _gh("40.000s    test_x (pkg.test_a.T.test_x)"),
        _gh("Ran 2 tests in 100.0s"),
        _gh("shard 1: OK in 55.1s"),
        _gh("Ran 8 tests in 55.0s"),
        _gh("sharded run finished in 100.1s (exit 0)"),
    ]
    return "\n".join(lines) + "\n"


class ParseLogTest(unittest.TestCase):
    def test_listed_tests_are_exact_and_the_rest_is_spread(self):
        runs = wd.parse_log_text(_crafted_log())
        self.assertEqual(len(runs), 1)
        estimates = wd.estimate_run(
            runs[0], {"pkg.test_a": 2, "pkg.test_b": 8})
        # test_a's listed 40s is exact; its shard's remaining
        # 60s of wall has nowhere else to go (it is the only
        # file in the shard), and test_b takes its shard's
        # whole 55s the same way.
        self.assertEqual(estimates,
                         {"pkg.test_a": 100.0, "pkg.test_b": 55.0})

    def test_the_residual_spreads_by_unlisted_count(self):
        lines = [
            _gh("running 10 test(s) from 2 module(s) in 1 shard(s)"),
            _gh("shard 0: 2 module(s): pkg.test_a, pkg.test_b"),
            _gh("shard 0: OK in 100.1s"),
            _gh("30.000s    test_x (pkg.test_a.T.test_x)"),
            _gh("Ran 10 tests in 100.0s"),
            _gh("sharded run finished in 100.1s (exit 0)"),
        ]
        runs = wd.parse_log_text("\n".join(lines))
        estimates = wd.estimate_run(
            runs[0], {"pkg.test_a": 4, "pkg.test_b": 6})
        # Wall 100, listed 30: the 70s residual spreads over
        # the unlisted counts (a: 3, b: 6) -- a gets 30 + 70/3,
        # b gets 140/3.
        self.assertAlmostEqual(estimates["pkg.test_a"], 30 + 70 / 3)
        self.assertAlmostEqual(estimates["pkg.test_b"], 140 / 3)

    def test_a_killed_shard_floors_at_the_run_total(self):
        lines = [
            _gh("running 4 test(s) from 1 module(s) in 1 shard(s)"),
            _gh("shard 0: 1 module(s): pkg.test_a"),
            _gh("=== shard 0 FAILED (exit 124) ==="),
            _gh("sharded run finished in 1200.1s (exit 1)"),
        ]
        runs = wd.parse_log_text("\n".join(lines))
        estimates = wd.estimate_run(runs[0], {"pkg.test_a": 4})
        self.assertEqual(estimates, {"pkg.test_a": 1200.1})

    def test_other_steps_lines_are_not_evidence(self):
        decoy = ("build-windows\tSome other step\t"
                 "2026-11-10T19:49:15.0000000Z "
                 "shard 0: OK in 1.0s")
        self.assertEqual(wd.parse_log_text(decoy + "\n"), [])

    def test_bare_shard_lines_are_accepted(self):
        runs = wd.parse_log_text(
            "running 1 test(s) from 1 module(s) in 1 shard(s)\n"
            "shard 0: 1 module(s): pkg.test_a\n"
            "shard 0: OK in 3.0s\n")
        estimates = wd.estimate_run(runs[0], {"pkg.test_a": 1})
        self.assertEqual(estimates, {"pkg.test_a": 3.0})

    def test_noise_and_bookends_do_not_crash_or_leak_in(self):
        junk = [
            "", " ", "\t", "===", "shards shards shards",
            _gh(""), _gh("=== shard x FAILED ==="),
            _gh("99.000s    test_x (pkg.test_a.T.test_x)"),
            _gh("Ran tests in s"),
            "40.000s    test_x (pkg.test_a.T.test_x)",
        ]
        text = "\n".join(junk) + "\r\n" + _crafted_log()
        runs = wd.parse_log_text(text)
        self.assertEqual(len(runs), 1)
        estimates = wd.estimate_run(
            runs[0], {"pkg.test_a": 2, "pkg.test_b": 8})
        self.assertEqual(estimates,
                         {"pkg.test_a": 100.0, "pkg.test_b": 55.0})

    def test_a_deeply_dotted_module_keeps_its_listed_tests(self):
        lines = [
            _gh("running 1 test(s) from 1 module(s) in 1 shard(s)"),
            _gh("shard 0: 1 module(s): a.b.c.test_x"),
            _gh("shard 0: OK in 9.0s"),
            _gh("5.000s    test_y (a.b.c.test_x.T.test_y)"),
            _gh("Ran 1 test in 9.0s"),
        ]
        runs = wd.parse_log_text("\n".join(lines))
        estimates = wd.estimate_run(runs[0], {"a.b.c.test_x": 1})
        # The listed 5s is exact and the residual 4s lands on
        # the same single file: the whole shard wall.
        self.assertEqual(estimates, {"a.b.c.test_x": 9.0})

    def test_estimates_take_the_max_and_drop_the_loader_bucket(self):
        def one_log(seconds, mods):
            return "\n".join([
                _gh("running 2 test(s) from %d module(s) in 1 "
                    "shard(s)" % len(mods)),
                _gh("shard 0: %d module(s): %s"
                    % (len(mods), ", ".join(mods))),
                _gh("shard 0: OK in %0.1fs" % seconds),
                _gh("Ran 2 tests in %0.1fs" % seconds),
            ])
        counts = {"pkg.test_a": 1, "unittest.loader": 1}
        combined = wd.estimate_from_logs(
            [one_log(50.0, ["pkg.test_a"]),
             one_log(80.0, ["pkg.test_a"]),
             one_log(999.0, ["unittest.loader"])], counts)
        self.assertEqual(combined, {"pkg.test_a": 80.0})


class DurationShardsBridgeTest(unittest.TestCase):
    def test_the_runner_packs_from_a_table(self):
        with tempfile.TemporaryDirectory() as d:
            path = _table_file(d, {"test_a": 100.0, "test_b": 30.0})
            shards, loads, budget = rtp.duration_shards(
                {"test_a": 1, "test_b": 1}, path)
        self.assertEqual(shards, [["test_a", "test_b"]])
        self.assertEqual(loads, [130.0])
        self.assertEqual(budget, 720.0)

    def test_a_budget_override_wins_over_the_table(self):
        with tempfile.TemporaryDirectory() as d:
            path = _table_file(d, {"test_a": 100.0, "test_b": 30.0})
            shards, loads, budget = rtp.duration_shards(
                {"test_a": 1, "test_b": 1}, path, 120.0)
        self.assertEqual(shards, [["test_a"], ["test_b"]])
        self.assertEqual(budget, 120.0)

    def test_an_unmeasured_module_is_packed_not_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            path = _table_file(d, {"test_a": 100.0})
            shards, loads, budget = rtp.duration_shards(
                {"test_a": 1, "test_new": 1}, path)
        flat = [n for shard in shards for n in shard]
        self.assertEqual(sorted(flat), ["test_a", "test_new"])
        self.assertEqual(loads, [200.0])

    def test_a_missing_table_raises(self):
        with self.assertRaises(OSError):
            rtp.duration_shards({"test_a": 1},
                                "/nonexistent/durations.json")

    def test_a_corrupt_table_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = _table_file(d, {"test_a": -5.0})
            with self.assertRaises(ValueError):
                rtp.duration_shards({"test_a": 1}, path)


class _OutsideActions(unittest.TestCase):
    def setUp(self):
        self._actions = os.environ.pop("GITHUB_ACTIONS", None)

    def tearDown(self):
        if self._actions is not None:
            os.environ["GITHUB_ACTIONS"] = self._actions


class MainTableModeTest(_OutsideActions):
    def test_table_mode_runs_every_module_once(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS)
            _write(d, "test_beta.py", _PASS)
            table = _table_file(
                d, {"test_alpha": 100.0, "test_beta": 30.0})
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = rtp.main(["--duration-table", table,
                               "--top-level-dir", d,
                               "test_alpha", "test_beta"])
        self.assertEqual(rc, 0)
        self.assertIn("duration-balanced from", out.getvalue())

    def test_a_missing_table_is_an_error_not_a_count_split(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS)
            with contextlib.redirect_stderr(io.StringIO()):
                rc = rtp.main(
                    ["--duration-table",
                     os.path.join(d, "nope.json"),
                     "--top-level-dir", d, "test_alpha"])
        self.assertEqual(rc, 2)


class CheckedInTableGuardTest(unittest.TestCase):
    def test_the_checked_in_table_passes_its_own_check(self):
        self.assertEqual(
            wd.check_table(REPO, wd.default_table_path()), [])

    def test_the_workflow_packs_from_the_checked_in_table(self):
        with open(os.path.join(REPO, ".github", "workflows",
                               "build.yml"),
                  encoding="utf-8") as fh:
            workflow = fh.read()
        block = workflow.split("build-windows:", 1)[1]
        block = block.split("build-windows-arm64:", 1)[0]
        self.assertIn("--duration-table "
                      "runner/tools/windows_durations.json", block)
        self.assertIn("--wall-clock 20", block)
        self.assertTrue(os.path.isfile(
            os.path.join(REPO, "runner", "tools",
                         "windows_durations.json")))

    def test_the_killed_shards_heavy_files_keep_their_floors(self):
        # Build run 42941458640 (2026-11-11): shard 5 hit the
        # 20-minute wall (exit 124) while its siblings finished
        # in 702-868s against the same 646s packed load. Its
        # first two files carry the overrun, and their prices
        # said otherwise. test_proof_content_rung500000 was
        # priced 144.1s; the module boundary in that build's
        # log -- shard start 01:48:11Z to the next file's first
        # log line 01:56:00Z, less that file's pre-log tests
        # (its hostile-pattern test alone measured 51.7s in
        # run 42933646758) -- puts the file at about 390s.
        # test_policy_constraints was priced 76.5s; its logged
        # job-running tests alone span 162s of that build
        # (01:56:00Z-01:58:42Z), before the timing tests and
        # the classes after the logged ones are counted, a
        # 230s floor. The estimator cannot learn either number
        # from that log: a killed shard prints no durations
        # block, so its wall spreads by test count, and a
        # 4-test file takes a 4-test share. These floors keep
        # the packer from re-creating that shard.
        table = wd.load_table_file(wd.default_table_path())
        durations = table["durations"]
        self.assertGreaterEqual(
            durations["runner.tests.test_proof_content_rung500000"],
            390.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_policy_constraints"],
            230.0)

    def test_the_two_heavy_files_do_not_share_a_shard(self):
        # Packed from the table's own names, the packing
        # check_table guards: a discovery here would only
        # repeat test_the_real_suite_packs_within_budget's
        # pass (and its known sys.path growth, which the
        # regression guard already counts once).
        table = wd.load_table_file(wd.default_table_path())
        shards = wd.pack_modules(sorted(table["durations"]),
                                 table["durations"],
                                 table["budget_seconds"])
        for shard in shards:
            self.assertFalse(
                "runner.tests.test_proof_content_rung500000" in shard
                and "runner.tests.test_policy_constraints" in shard,
                "the two files whose under-pricing killed shard 5 "
                "of run 42941458640 packed into one shard again")

    def test_the_shard2_heavy_files_keep_their_floors(self):
        # Build run 42950872171 (2026-11-11): shard 2 (55
        # modules, 705s packed) hit the 20-minute wall, exit
        # 124 at 1,200.2s, and the next head's build killed
        # the same shard the same way an hour later. The
        # killed shard's own last-lines dump shows about 105
        # test results printed when the kill landed; its
        # first three files hold 115 tests between them (4 +
        # 15 + 96), so the kill landed inside the third file
        # and the three together burn more than the wall
        # against 379.6s priced. test_proof_content_cap was
        # priced 261.7s; the estimator's own max for it over
        # the 21 Windows logs at hand is 379.9s, a 390s floor
        # (the same rounding the shard-5 floor took).
        # test_regression_guard was priced 66.1s; its one
        # directly measured end-to-end test -- the cheap
        # module, native run plus gates -- took 43.0s on
        # macOS and 34.6s on Linux, and the file carries a
        # second end-to-end run beside its 13 lighter tests,
        # a 250s floor. test_decision1_startup was priced
        # 51.8s for 96 tests, each a real in-process runner
        # startup through main(); with the first file
        # bounded at about 390s by the estimator and the
        # second at about 250s by its anchors, the rest of
        # the killed wall -- over 560s -- falls on it, a
        # 650s floor. The estimator cannot learn any of
        # these from the killed logs: a killed shard prints
        # no durations block, so its wall spreads by test
        # count (a refresh over the same logs prices the
        # three at 379.9 / 83.5 / 93.3). These floors keep
        # the packer from re-creating that shard.
        table = wd.load_table_file(wd.default_table_path())
        durations = table["durations"]
        self.assertGreaterEqual(
            durations["runner.tests.test_proof_content_cap"],
            390.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_regression_guard"],
            250.0)
        # test_decision1_startup's 650s floor, recorded in
        # the comment above, is retired by the Q136 file
        # split (2026-11-11): the module no longer exists,
        # and its five pieces carry their own floors,
        # pinned in
        # test_the_decision1_split_pieces_keep_their_prices.
        self.assertNotIn("runner.tests.test_decision1_startup",
                         durations)

    def test_the_shard2_heavy_files_do_not_share_a_shard(self):
        table = wd.load_table_file(wd.default_table_path())
        shards = wd.pack_modules(sorted(table["durations"]),
                                 table["durations"],
                                 table["budget_seconds"])
        heavy = ("runner.tests.test_proof_content_cap",
                 "runner.tests.test_regression_guard")
        for shard in shards:
            self.assertLessEqual(
                sum(1 for name in heavy if name in shard), 1,
                "two of the files whose under-pricing killed "
                "shard 2 of run 42950872171 packed into one "
                "shard again")

    def test_the_v2_consult_file_keeps_its_floor(self):
        # The 3.16.20.4 tag build (run 43003938484) killed
        # shard 0 at the 1,200.2s wall on both attempts.
        # That shard carried test_decision1_startup at its
        # 650s floor plus 19 files priced at about 37s in
        # all, so the companions burned over 500s beyond
        # their prices. The one companion that can carry
        # that residual is test_v2_consult: 104 tests, each
        # driving runner.main() the way
        # test_decision1_startup's do, landed by Q139/Q141
        # after the table's last refresh and so never
        # measured on Windows at all -- it packed at the
        # 3.7s median. (Its shard-mates are exonerated
        # file by file in the Q136 re-pack conclusions:
        # several completed inside other shards of the
        # .2-head builds, and test_doc_link_resolution,
        # the shard's other untabled name at the .4 tree,
        # completed inside shard 5 of both attempts.)
        # At test_decision1_startup's own per-startup
        # boundary cost (its 650s floor over 97 tests),
        # 104 such tests price at about 600s. The
        # estimator cannot learn this from the logs: the
        # killed shard prints no durations block, so its
        # wall spreads by test count and a refresh over
        # both .4 attempts prices the file at 326.8s.
        # This floor keeps the packer from re-creating
        # that shard; it is a floor from boundary
        # evidence, not a measurement.
        table = wd.load_table_file(wd.default_table_path())
        self.assertGreaterEqual(
            table["durations"]["runner.tests.test_v2_consult"],
            600.0)

    def test_decision1_and_v2_consult_do_not_share_a_shard(self):
        # After the Q136 file split (2026-11-11) the
        # decision1 side of this pin is the split family's
        # startup pieces: none of them packs beside
        # test_v2_consult, the other in-process-startup
        # file. Each startup piece is priced at 270s or
        # more, so the budget arithmetic (600 + 270 > 720)
        # holds the shape the way the original 650s floor
        # held it. The readers piece carries no startup
        # (its S3 price is import and reader cost), so it
        # is not part of this pin and may pack beside
        # test_v2_consult under the budget.
        pieces = ("runner.tests.test_decision1_startup_refuse_main",
                  "runner.tests.test_decision1_startup_refuse_policies",
                  "runner.tests.test_decision1_startup_gates",
                  "runner.tests.test_decision1_startup_defaults")
        table = wd.load_table_file(wd.default_table_path())
        shards = wd.pack_modules(sorted(table["durations"]),
                                 table["durations"],
                                 table["budget_seconds"])
        for shard in shards:
            if "runner.tests.test_v2_consult" in shard:
                for piece in pieces:
                    self.assertNotIn(
                        piece, shard,
                        "a decision1 split piece packed beside "
                        "test_v2_consult, re-creating the "
                        "combined in-process-startup shard that "
                        "killed shard 0 of the 3.16.20.4 tag "
                        "build")

    def test_the_completed_shards_listed_files_keep_their_floors(self):
        # Build run 43026648905 (2026-11-11), the first
        # completed build-windows verdict on a head
        # carrying the third re-pack: shards 0, 1 and 2
        # finished at their packed prices, every other
        # completed shard's internal time stayed within
        # 1.10x of its price, and the leg's only wall
        # kill was shard 3. Four files in completed
        # shards are convicted by exact evidence, not
        # by the estimator's spread: a file's listed
        # slowest-tests sum is a floor on its whole
        # cost, and in that run test_result_stash's
        # listed tests sum to 562.7s against 151.6
        # priced, test_notable_access's to 466.9
        # against 174.4, test_key_names' to 321.8
        # against 94.5, and test_concurrency's to
        # 253.4 against 16.1 (test_concurrency is also
        # the module whose bad-answers test failed in
        # shard 4 of the same run -- its cost is
        # load-sensitive, and the listed sum was taken
        # under that load). These floors, each just
        # under its listed sum, keep the packer from
        # pricing any of the four back under the cost
        # its own tests already measured.
        table = wd.load_table_file(wd.default_table_path())
        durations = table["durations"]
        self.assertGreaterEqual(
            durations["runner.tests.test_result_stash"], 560.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_notable_access"], 460.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_key_names"], 320.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_concurrency"], 250.0)

    def test_the_decision1_split_pieces_keep_their_prices(self):
        # The Q136 file split (2026-11-11). Three completed
        # build-windows verdicts on fifth-re-pack heads
        # (runs 43047662646, 43053974828 and 43057662476)
        # carried shard 0 as test_decision1_startup ALONE
        # at its 720s budget price and still failed exit
        # 124 at the 1,200s wall -- the condition the
        # fifth re-pack's conclusions named in advance:
        # the defect is in the file (97 in-process runner
        # startups), not the packing, and the answer is a
        # file split, not a sixth re-pack. The file is
        # split along its class seams into five pieces,
        # priced from the kill record at about 15s a
        # startup on the loaded Windows leg: refuse_main
        # 340 (22 startups), refuse_policies 330 (21),
        # gates 270 (15 startups plus the decision-point
        # subtests), defaults 300 (19) and readers 100
        # (no startup; its price is import and reader
        # cost, the largest local share). The pieces
        # total 1,340s -- above
        # the wall the whole file burned past -- and the
        # 400s ceiling on every piece is the regrowth
        # pin: a piece that grows past it fails here and
        # divides further instead of repricing upward
        # toward the budget the way the whole file did.
        # The retired pins this replaces (the 720s budget
        # floor packing alone, and the named-companion
        # pin from run 43026648905) cannot hold a split
        # family: pieces are priced to pack WITH
        # companions under the budget, by design.
        table = wd.load_table_file(wd.default_table_path())
        durations = table["durations"]
        floors = {
            "runner.tests.test_decision1_startup_refuse_main": 340.0,
            "runner.tests.test_decision1_startup_refuse_policies": 330.0,
            "runner.tests.test_decision1_startup_gates": 270.0,
            "runner.tests.test_decision1_startup_readers": 100.0,
            "runner.tests.test_decision1_startup_defaults": 300.0,
        }
        self.assertNotIn("runner.tests.test_decision1_startup",
                         durations)
        self.assertFalse(os.path.isfile(os.path.join(
            REPO, "runner", "tests", "test_decision1_startup.py")))
        total = 0.0
        for name, floor in floors.items():
            self.assertTrue(os.path.isfile(os.path.join(
                REPO, "runner", "tests",
                name.rsplit(".", 1)[1] + ".py")), name)
            self.assertGreaterEqual(durations[name], floor, name)
            self.assertLessEqual(durations[name], 400.0, name)
            total += durations[name]
        self.assertGreaterEqual(total, 1200.0)


    def test_the_fifth_repack_listed_files_keep_their_floors(self):
        # Build run 43035985891 (2026-11-11), the first
        # completed build-windows verdict on a head
        # carrying the fourth re-pack: shard 3 hit the
        # wall again (below), every completed shard ran
        # 99.5 to 484.0 seconds internally against
        # 717.3 packed, and in those completed shards
        # eight files are convicted by exact evidence --
        # a file's listed slowest-tests sum is a floor
        # on its whole cost. test_transports' listed
        # tests sum to 302.9s against 158.2 priced,
        # test_enforce_posture_reconciliation's to
        # 284.0 against 207.3, test_oracle_opinion's to
        # 247.0 against 172.8, test_negative_concurrency's
        # to 162.3 against 103.0, test_audience's to
        # 123.3 against 32.8, test_protocol_examples'
        # to 90.7 against 11.3, test_concurrency_poison's
        # to 71.7 against 21.0 and test_oracle_chat's to
        # 56.4 against 33.7. The last three are the
        # load-sensitive family: test_oracle_chat's two
        # timeouts failed shard 10 of the same run and
        # test_concurrency_poison listed in shard 17
        # beside test_concurrency's bad-answers failure,
        # so their sums were taken under the load that
        # failed them. These floors, each just under
        # its listed sum, keep the packer from pricing
        # any of the eight back under the cost its own
        # tests already measured.
        table = wd.load_table_file(wd.default_table_path())
        durations = table["durations"]
        self.assertGreaterEqual(
            durations["runner.tests.test_transports"], 300.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_enforce_posture_reconciliation"],
            280.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_oracle_opinion"], 245.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_negative_concurrency"], 160.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_audience"], 120.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_protocol_examples"], 90.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_concurrency_poison"], 70.0)
        self.assertGreaterEqual(
            durations["runner.tests.test_oracle_chat"], 55.0)

    def test_the_decision1_split_family_still_carries_97_tests(self):
        # The split is a move, not a rewrite: the five
        # pieces between them carry exactly the original
        # file's 97 tests, at the original per-class
        # counts (RefuseMain 43 across its two pieces,
        # the gates classes 18, RefuseReader 16, the
        # default class and its table pin 20). A test
        # lost, duplicated or silently dropped in a
        # future edit of a piece fails here.
        import importlib
        import unittest as _unittest
        expected = {
            "runner.tests.test_decision1_startup_refuse_main": 22,
            "runner.tests.test_decision1_startup_refuse_policies": 21,
            "runner.tests.test_decision1_startup_gates": 18,
            "runner.tests.test_decision1_startup_readers": 16,
            "runner.tests.test_decision1_startup_defaults": 20,
        }
        total = 0
        for name, count in expected.items():
            module = importlib.import_module(name)
            found = _unittest.TestLoader().loadTestsFromModule(
                module).countTestCases()
            self.assertEqual(found, count, name)
            total += found
        self.assertEqual(total, 97)


    def test_the_real_suite_packs_within_budget(self):
        table = wd.load_table_file(wd.default_table_path())
        counts = rtp.module_test_counts(
            os.path.join(REPO, "runner", "tests"), REPO)
        shards = wd.pack_modules(sorted(counts), table["durations"],
                                 table["budget_seconds"])
        flat = [n for shard in shards for n in shard]
        self.assertEqual(sorted(flat), sorted(counts))
        loads = wd.shard_loads(shards, table["durations"])
        self.assertTrue(
            all(load <= table["budget_seconds"] for load in loads),
            "packed loads over budget: %r" % (loads,))


if __name__ == "__main__":
    unittest.main()
