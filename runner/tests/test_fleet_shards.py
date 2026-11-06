# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Cross-rig suite sharding (runner/tools/fleet_shards.py).

The manifest split, the shard worker, the shard-result shape, and
the census-checked merger, pinned on small made-up censuses and
fake modules: the split must cover the census exactly once under
any weights, a module that will not import must become an error
entry rather than vanish, and the merger must fail loudly — naming
the module — on a missing, duplicated, or wrong-head shard.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "fleet_shards",
    os.path.join(REPO, "runner", "tools", "fleet_shards.py"))
fs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fs)

COUNTS = {"runner.tests.test_a": 100, "runner.tests.test_b": 50,
          "runner.tests.test_c": 50, "runner.tests.test_d": 1,
          "runner.tests.test_e": 30, "runner.tests.test_f": 12}


def _obj(module, ran=1, failures=(), errors=(), skipped=0):
    return {"module": module, "ran": ran, "failures": list(failures),
            "errors": list(errors), "skipped": skipped, "seconds": 0.1}


def _result(head, rig, objects):
    return fs.build_shard_result(head, rig, 2, objects,
                                 "2026-11-06T00:00:00+00:00", 1.5)


def _green_results(manifest, head="abc123"):
    results = []
    for share in manifest["rigs"]:
        objects = [_obj(m, ran=manifest["census_counts"][m])
                   for m in share["modules"]]
        if objects:
            results.append(_result(head, share["rig"], objects))
    return results


class ManifestSplitTest(unittest.TestCase):
    def test_split_covers_the_census_exactly_once(self):
        manifest = fs.build_manifest("abc123", dict(COUNTS),
                                     [("menlo", 1), ("germany", 4)])
        self.assertEqual(manifest["schema"], 1)
        self.assertEqual(manifest["head"], "abc123")
        self.assertEqual(manifest["census"], sorted(COUNTS))
        self.assertEqual(manifest["census_counts"], COUNTS)
        self.assertEqual(manifest["total_tests"], sum(COUNTS.values()))
        flat = [m for share in manifest["rigs"]
                for m in share["modules"]]
        self.assertEqual(sorted(flat), sorted(COUNTS))
        self.assertEqual(len(flat), len(set(flat)))

    def test_uneven_weights_give_the_faster_rig_more_load(self):
        manifest = fs.build_manifest("abc123", dict(COUNTS),
                                     [("slow", 1), ("fast", 4)])
        loads = {share["rig"]: sum(COUNTS[m] for m in share["modules"])
                 for share in manifest["rigs"]}
        self.assertGreater(loads["fast"], loads["slow"])
        total = sum(COUNTS.values())
        # The weighted greedy keeps each rig within one largest
        # module of its proportional target.
        self.assertLessEqual(abs(loads["fast"] - total * 4 / 5),
                             max(COUNTS.values()))

    def test_equal_weights_match_the_unweighted_shape(self):
        split = fs.split_weighted(dict(COUNTS), [("a", 1), ("b", 1)])
        loads = sorted(sum(COUNTS[m] for m in mods)
                       for _n, _w, mods in split)
        self.assertEqual(loads[1] - loads[0],
                         min(loads[1] - loads[0], max(COUNTS.values())))

    def test_an_empty_rig_still_appears_in_the_manifest(self):
        # More rigs than modules, and a rig with zero weight: both
        # are handed nothing, and both are still named.
        manifest = fs.build_manifest(
            "abc123", {"runner.tests.test_a": 3},
            [("busy", 1), ("idle", 0), ("spare", 1)])
        by_rig = {share["rig"]: share["modules"]
                  for share in manifest["rigs"]}
        self.assertEqual(by_rig["idle"], [])
        self.assertEqual(sorted(by_rig), ["busy", "idle", "spare"])
        flat = [m for mods in by_rig.values() for m in mods]
        self.assertEqual(flat, ["runner.tests.test_a"])

    def test_all_zero_weights_are_refused(self):
        with self.assertRaises(ValueError):
            fs.split_weighted(dict(COUNTS), [("a", 0), ("b", 0)])

    def test_duplicate_rig_names_are_refused(self):
        with self.assertRaises(ValueError):
            fs.split_weighted(dict(COUNTS), [("a", 1), ("a", 2)])

    def test_an_empty_census_splits_to_empty_shares(self):
        manifest = fs.build_manifest("abc123", {}, [("a", 1)])
        self.assertEqual(manifest["census"], [])
        self.assertEqual(manifest["rigs"][0]["modules"], [])


_PASS = (
    "import unittest\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_one(self):\n"
    "        self.assertTrue(True)\n"
    "    def test_two(self):\n"
    "        self.assertTrue(True)\n"
    "    @unittest.skip('not today')\n"
    "    def test_three(self):\n"
    "        pass\n"
)
_FAIL = (
    "import unittest\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_bad(self):\n"
    "        self.assertTrue(False)\n"
)
_BROKEN = "raise RuntimeError('import boom')\n"


def _write_module(directory, name, body):
    with open(os.path.join(directory, name + ".py"), "w",
              encoding="utf-8") as fh:
        fh.write(body)


class _FakeTree(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        sys.path.insert(0, self._tmp.name)
        self.addCleanup(sys.path.remove, self._tmp.name)
        for name in ("fleet_fake_pass", "fleet_fake_fail",
                     "fleet_fake_broken"):
            sys.modules.pop(name, None)
            self.addCleanup(sys.modules.pop, name, None)


class WorkerTest(_FakeTree):
    def test_a_passing_module_object_shape(self):
        _write_module(self._tmp.name, "fleet_fake_pass", _PASS)
        obj = fs.run_module("fleet_fake_pass")
        self.assertEqual(set(obj), {"module", "ran", "failures",
                                    "errors", "skipped", "seconds"})
        self.assertEqual(obj["module"], "fleet_fake_pass")
        self.assertEqual(obj["ran"], 3)
        self.assertEqual(obj["failures"], [])
        self.assertEqual(obj["errors"], [])
        self.assertEqual(obj["skipped"], 1)
        self.assertGreaterEqual(obj["seconds"], 0)

    def test_a_failing_module_names_the_test(self):
        _write_module(self._tmp.name, "fleet_fake_fail", _FAIL)
        obj = fs.run_module("fleet_fake_fail")
        self.assertEqual(obj["ran"], 1)
        self.assertEqual(obj["failures"], ["fleet_fake_fail.T.test_bad"])
        self.assertEqual(obj["errors"], [])

    def test_an_import_broken_module_is_an_error_not_a_crash(self):
        _write_module(self._tmp.name, "fleet_fake_broken", _BROKEN)
        obj = fs.run_module("fleet_fake_broken")
        self.assertEqual(obj["module"], "fleet_fake_broken")
        self.assertEqual(obj["ran"], 1)
        self.assertEqual(obj["failures"], [])
        self.assertEqual(obj["errors"], ["fleet_fake_broken"])

    def test_a_missing_module_is_an_error_not_a_crash(self):
        obj = fs.run_module("fleet_fake_absent")
        self.assertEqual(obj["errors"], ["fleet_fake_absent"])
        self.assertEqual(obj["ran"], 1)

    def test_the_worker_cli_emits_the_object_as_json(self):
        _write_module(self._tmp.name, "fleet_fake_pass", _PASS)
        with tempfile.TemporaryDirectory() as out_dir:
            out = os.path.join(out_dir, "obj.json")
            rc = fs.main(["worker", "fleet_fake_pass", "--out", out])
            self.assertEqual(rc, 0)
            with open(out, encoding="utf-8") as fh:
                obj = json.load(fh)
        self.assertEqual(obj["module"], "fleet_fake_pass")
        self.assertEqual(obj["ran"], 3)


class ShardResultTest(unittest.TestCase):
    def test_the_result_shape_and_totals(self):
        objects = [_obj("runner.tests.test_b", ran=2,
                        failures=["runner.tests.test_b.T.test_x"]),
                   _obj("runner.tests.test_a", ran=3, skipped=1)]
        result = _result("abc123", "menlo", objects)
        self.assertEqual(set(result),
                         {"schema", "head", "rig", "platform", "python",
                          "jobs", "started_utc", "wall_seconds",
                          "modules", "totals"})
        self.assertEqual(result["schema"], 1)
        self.assertEqual(result["head"], "abc123")
        self.assertEqual(result["rig"], "menlo")
        self.assertEqual(result["jobs"], 2)
        # Modules are stored sorted by name, whatever order they
        # finished in.
        self.assertEqual([m["module"] for m in result["modules"]],
                         ["runner.tests.test_a", "runner.tests.test_b"])
        self.assertEqual(result["totals"],
                         {"modules": 2, "ran": 5, "failures": 1,
                          "errors": 0, "skipped": 1})


class RunShardTest(_FakeTree):
    def test_run_shard_over_worker_subprocesses(self):
        _write_module(self._tmp.name, "fleet_fake_pass", _PASS)
        _write_module(self._tmp.name, "fleet_fake_broken", _BROKEN)
        manifest = fs.build_manifest(
            "abc123",
            {"fleet_fake_pass": 3, "fleet_fake_broken": 1},
            [("menlo", 1)])
        with mock.patch.dict(os.environ,
                             {"PYTHONPATH": self._tmp.name}):
            result = fs.run_shard(manifest, "menlo", 2)
        self.assertEqual(result["head"], "abc123")
        self.assertEqual(result["rig"], "menlo")
        self.assertEqual(result["totals"]["modules"], 2)
        self.assertEqual(result["totals"]["ran"], 4)
        self.assertEqual(result["totals"]["errors"], 1)

    def test_run_shard_names_an_unknown_rig(self):
        manifest = fs.build_manifest("abc123", dict(COUNTS),
                                     [("menlo", 1)])
        with self.assertRaises(ValueError):
            fs.run_shard(manifest, "nowhere", 1)


class MergerTest(unittest.TestCase):
    def setUp(self):
        self.manifest = fs.build_manifest(
            "abc123", dict(COUNTS), [("menlo", 1), ("germany", 4)])

    def test_the_green_path(self):
        ok, lines = fs.merge_results(
            self.manifest, _green_results(self.manifest))
        self.assertTrue(ok, lines)
        self.assertEqual(lines[-1], "verdict: OK")

    def test_totals_arithmetic_across_rigs(self):
        results = _green_results(self.manifest)
        ok, lines = fs.merge_results(self.manifest, results)
        self.assertTrue(ok, lines)
        totals_line = [ln for ln in lines if ln.startswith("totals:")]
        self.assertEqual(
            totals_line,
            ["totals: ran=%d failures=0 errors=0 skipped=0"
             % sum(COUNTS.values())])
        census_line = [ln for ln in lines if ln.startswith("census:")]
        self.assertEqual(
            census_line,
            ["census: %d module(s); results: %d module(s) from %d rig(s)"
             % (len(COUNTS), len(COUNTS), len(results))])

    def test_a_missing_module_fails_and_is_named(self):
        results = _green_results(self.manifest)
        dropped = results[0]["modules"].pop()["module"]
        results[0]["totals"] = fs.totals_of(results[0]["modules"])
        ok, lines = fs.merge_results(self.manifest, results)
        self.assertFalse(ok)
        self.assertTrue(any("missing modules:" in ln and dropped in ln
                            for ln in lines), lines)
        self.assertEqual(lines[-1], "verdict: FAILED")

    def test_a_duplicate_module_fails_and_is_named(self):
        results = _green_results(self.manifest)
        dup = results[0]["modules"][0]
        results[1]["modules"].append(dict(dup))
        results[1]["totals"] = fs.totals_of(results[1]["modules"])
        ok, lines = fs.merge_results(self.manifest, results)
        self.assertFalse(ok)
        self.assertTrue(any("duplicated modules:" in ln
                            and dup["module"] in ln
                            for ln in lines), lines)

    def test_an_extra_module_fails_and_is_named(self):
        results = _green_results(self.manifest)
        results[0]["modules"].append(_obj("runner.tests.test_nope"))
        results[0]["totals"] = fs.totals_of(results[0]["modules"])
        ok, lines = fs.merge_results(self.manifest, results)
        self.assertFalse(ok)
        self.assertTrue(any("extra modules:" in ln
                            and "runner.tests.test_nope" in ln
                            for ln in lines), lines)

    def test_a_head_mismatch_fails_and_names_the_rig(self):
        results = _green_results(self.manifest, head="def456")
        ok, lines = fs.merge_results(self.manifest, results)
        self.assertFalse(ok)
        self.assertTrue(any("head" in ln and "def456" in ln
                            for ln in lines), lines)

    def test_a_failing_test_fails_the_merge_and_is_listed(self):
        results = _green_results(self.manifest)
        bad = results[0]["modules"][0]
        bad["failures"] = ["%s.T.test_bad" % bad["module"]]
        results[0]["totals"] = fs.totals_of(results[0]["modules"])
        ok, lines = fs.merge_results(self.manifest, results)
        self.assertFalse(ok)
        self.assertTrue(any("failing/erroring tests:" in ln
                            and "test_bad" in ln for ln in lines), lines)

    def test_totals_that_disagree_with_the_modules_fail(self):
        results = _green_results(self.manifest)
        results[0]["totals"] = dict(results[0]["totals"], ran=999)
        ok, lines = fs.merge_results(self.manifest, results)
        self.assertFalse(ok)
        self.assertTrue(any("totals" in ln and "do not match" in ln
                            for ln in lines), lines)

    def test_the_merge_cli_reads_a_results_directory(self):
        with tempfile.TemporaryDirectory() as d:
            manifest_path = os.path.join(d, "manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(self.manifest, fh)
            results_dir = os.path.join(d, "results")
            os.makedirs(results_dir)
            for i, result in enumerate(
                    _green_results(self.manifest)):
                with open(os.path.join(results_dir, "r%d.json" % i),
                          "w", encoding="utf-8") as fh:
                    json.dump(result, fh)
            rc = fs.main(["merge", "--manifest", manifest_path,
                          "--results-dir", results_dir])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
