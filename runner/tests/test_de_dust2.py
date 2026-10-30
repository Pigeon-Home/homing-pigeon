# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""Campaign de_dust2 (docs/project/de_dust2.md): the tool's side.

P1 and P2: under --minutes each target's rounds come from a time
slice and its measured rate, the slice tilted by the target's recent
yield with a floor and a ceiling, and a target with a fresh seed
owed a full look. P3: parents are drawn by the rarity of the arcs
they reach and, on a target the reader mostly refuses, by whether
the reader took them. P4: a try far slower than the corpus replay's
median is a `slow` finding, kept apart from the crash file so no
timing ever becomes an expectedFailure probe. P10: `stats --yield`
prints the per-target table the review was built from.
"""
import argparse
import json
import os
import random
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from runner.tools import de_dust_corpus as B


def _grow(target, when, tried=1000, seconds=10.0, kept=0, arcs=0,
          accepted=500, refused=500, kind="grow"):
    return {"kind": kind, "target": target, "when": when, "tried": tried,
            "seconds": seconds, "kept": ["k%d" % i for i in range(kept)],
            "arcs_before": 100, "arcs_after": 100 + arcs,
            "outcomes": {"accepted": accepted, "refused": refused, "crash": 0}}


class SlicePlanTest(unittest.TestCase):

    def test_rate_and_yield_read_the_last_grows_by_time(self):
        runs = [_grow("a", "2026-10-29T10:00:00Z", tried=100, seconds=1.0, kept=2, arcs=3),
                _grow("a", "2026-10-29T09:00:00Z", tried=300, seconds=1.0),
                _grow("b", "2026-10-29T11:00:00Z", tried=10, seconds=10.0)]
        self.assertAlmostEqual(200.0, B.target_rate("a", runs))
        self.assertEqual((5, True), B.target_yield("a", runs))
        self.assertIsNone(B.target_rate("zzz", runs))
        self.assertEqual((0, True), B.target_yield("zzz", runs))

    def test_a_seed_record_resets_the_yield_window(self):
        runs = [_grow("a", "2026-10-29T0%d:00:00Z" % i, kept=1) for i in range(1, 8)]
        self.assertEqual((5, False), B.target_yield("a", runs))
        runs.append(_grow("a", "2026-10-29T07:30:00Z", kind="seed"))
        self.assertEqual((0, True), B.target_yield("a", runs))
        runs.append(_grow("a", "2026-10-29T08:00:00Z", kept=0))
        self.assertEqual((0, True), B.target_yield("a", runs))

    def test_the_tilt_has_a_floor_a_ceiling_and_a_first_look(self):
        self.assertEqual(B.TILT_FLOOR, B.slice_tilt(0, False))
        self.assertEqual(1.0, B.slice_tilt(0, True))
        self.assertEqual(1.25, B.slice_tilt(1, False))
        self.assertEqual(B.TILT_MAX, B.slice_tilt(400, False))
        self.assertEqual(2.0, B.slice_tilt(4, True))

    def test_rounds_follow_the_slice_and_the_rate_clamped(self):
        runs = ([_grow("slow", "2026-10-29T1%d:00:00Z" % i, tried=100, seconds=10.0)
                 for i in range(5)]
                + [_grow("fast", "2026-10-29T1%d:00:00Z" % i, tried=100000, seconds=10.0)
                   for i in range(5)]
                + [_grow("rich", "2026-10-29T1%d:00:00Z" % i, tried=1000, seconds=10.0, kept=4)
                   for i in range(5)])
        plan = B.slice_plan(["slow", "fast", "rich", "new"], 120, runs)
        self.assertEqual(B.SLICE_MIN_ROUNDS, plan["slow"]["rounds"])      # 30 s x 10/s = 300 -> floor
        self.assertEqual(B.SLICE_MAX_ROUNDS, plan["fast"]["rounds"])      # 30 s x 10k/s -> ceiling
        self.assertEqual(B.TILT_MAX, plan["rich"]["tilt"])                # 20 kept -> 4x
        self.assertEqual(int(480 * 100), plan["rich"]["rounds"])          # 480 s x 100/s
        self.assertEqual(B.SLICE_FIRST_ROUNDS, plan["new"]["rounds"])     # no rate yet
        self.assertEqual(1.0, plan["new"]["tilt"])

    def test_set_rounds_and_next_seed_rewrite_the_command(self):
        cmd = ["python", "tool", "grow", "--target", "a", "--rounds", "5", "--seed", "7"]
        self.assertEqual("9", B._set_rounds(cmd, 9)[6])
        self.assertEqual("8", B._next_seed(cmd)[8])
        self.assertIn("--rounds", B._set_rounds(["python", "tool", "grow"], 3))

    def test_comma_lists_name_a_lane(self):
        self.assertEqual(["query", "local"], B._targets("query, local"))
        self.assertEqual(list(B.TARGETS), B._targets("all"))
        with self.assertRaises(SystemExit):
            B._targets("query,nope")


class CycleUsesSlicesTest(unittest.TestCase):
    """`grow --minutes` without --rounds plans slices and re-plans a
    target's rounds each time it is requeued."""

    def test_a_cycling_grow_plans_and_requeues(self):
        args = argparse.Namespace(target="all", rounds=None, seed=1, jobs=1,
                                  minutes=1.0, verbose=False, archive=None,
                                  no_steer=True, order="fixed", slice=60.0,
                                  uniform_parents=False)
        seen = {}

        def fake_parallel(commands, jobs, out=print, minutes=0.0, requeue=None, **kw):
            seen["rounds"] = {tg: int(cmd[cmd.index("--rounds") + 1]) for tg, cmd in commands}
            seen["requeue"] = requeue
            tg, cmd = commands[0]
            seen["requeued"] = requeue(tg, cmd) if requeue else None
            return 0

        plan = {tg: {"tilt": 1.0, "seconds": 60.0, "rounds": 777, "rate": 10.0, "yield": 0}
                for tg in B.TARGETS}
        with mock.patch.object(B, "run_parallel", fake_parallel), \
                mock.patch.object(B, "slice_plan", return_value=plan), \
                mock.patch.object(B, "prune_retired_crashes", return_value=0):
            B.cmd_grow(args, out=lambda *a: None)
        self.assertEqual({tg: 777 for tg in B.TARGETS}, seen["rounds"])
        self.assertIsNotNone(seen["requeue"])
        self.assertEqual("777", seen["requeued"][seen["requeued"].index("--rounds") + 1])

    def test_rounds_named_means_no_slices(self):
        args = argparse.Namespace(target="all", rounds=5, seed=1, jobs=1,
                                  minutes=1.0, verbose=False, archive=None,
                                  no_steer=True, order="fixed", slice=None,
                                  uniform_parents=True)
        seen = {}

        def fake_parallel(commands, jobs, out=print, minutes=0.0, requeue=None, **kw):
            seen["rounds"] = {int(cmd[cmd.index("--rounds") + 1]) for tg, cmd in commands}
            seen["requeue"] = requeue
            seen["uniform"] = all("--uniform-parents" in cmd for tg, cmd in commands)
            return 0

        with mock.patch.object(B, "run_parallel", fake_parallel), \
                mock.patch.object(B, "prune_retired_crashes", return_value=0):
            B.cmd_grow(args, out=lambda *a: None)
        self.assertEqual({5}, seen["rounds"])
        self.assertIsNone(seen["requeue"])
        self.assertTrue(seen["uniform"])


class ParentChoiceTest(unittest.TestCase):

    def _session(self, hits, accepted):
        s = B.Session("names", [])
        s.entries = [{"id": i, "kind": "text", "data": i, "from": "", "mutator": "", "arcs": 0}
                     for i in hits]
        s.hits = {i: frozenset(a) for i, a in hits.items()}
        s.accepted_ids = set(accepted)
        return s

    def test_the_rarest_arc_sets_the_weight(self):
        s = self._session({"a": {1, 2}, "b": {1, 2}, "c": {1, 3}}, accepted={"a", "b", "c"})
        self.assertEqual([0.5, 0.5, 1.0], s.parent_weights())

    def test_accepted_parents_weigh_more_only_where_the_reader_mostly_refuses(self):
        mostly_refused = self._session({"a": {1}, "b": {1}, "c": {1}, "d": {1}, "e": {1}, "f": {1}},
                                       accepted={"a"})
        w = mostly_refused.parent_weights()
        self.assertEqual(B.ACCEPT_BOOST * w[1], w[0])
        balanced = self._session({"a": {1}, "b": {1}}, accepted={"a"})
        self.assertEqual([0.5, 0.5], balanced.parent_weights())

    def test_an_entry_without_a_run_weighs_as_the_median(self):
        s = self._session({"a": {1}, "b": {9}, "c": {1}, "d": {2}},
                          accepted={"a", "b", "c", "d"})
        s.hits.pop("b")
        self.assertEqual([0.5, 0.5, 0.5, 1.0], s.parent_weights())
        self.assertIsNone(B.Session("names", []).parent_weights())

    def test_a_keeper_joins_the_weights_before_the_next_recount(self):
        # A grow on a real corpus that keeps entries draws on without
        # a weight/population mismatch (the smoke that found it).
        entries = B.load(B.corpus_path("names"))
        s = B.Session("names", entries)
        B._with_rig(s.baseline)
        added = B._with_rig(lambda: s.grow(random.Random(3), 300))
        self.assertEqual(len(entries) + len(added), len(s.entries))

    def test_the_grow_draws_by_weight_unless_told_not_to(self):
        s = self._session({"a": {1}, "b": {1}}, accepted={"a", "b"})
        s.median, s.slow_bound = 0.001, 10.0
        with mock.patch.object(s, "parent_weights", return_value=[1.0, 0.0]) as pw, \
                mock.patch.object(B, "mutate", return_value=None):
            s.grow(random.Random(1), 3)
            self.assertTrue(pw.called)
            pw.reset_mock()
            s.grow(random.Random(1), 3, uniform_parents=True)
            self.assertFalse(pw.called)


class SlowClassTest(unittest.TestCase):

    def test_the_baseline_sets_the_bound_from_the_median(self):
        entries = B.load(B.corpus_path("names"))[:7]
        s = B.Session("names", entries)
        B._with_rig(s.baseline)
        self.assertIsNotNone(s.median)
        self.assertEqual(max(B.SLOW_FLOOR_SEC, B.SLOW_FACTOR * s.median), s.slow_bound)
        self.assertEqual(len(entries), len(s.hits))

    def test_a_slow_try_is_a_slow_outcome_and_a_record(self):
        s = B.Session("names", [])
        s.median, s.slow_bound = 0.001, 0.0
        entry = {"id": "x1", "kind": "text", "data": "a", "from": "", "mutator": "", "arcs": 0}
        with mock.patch.object(B, "check", return_value="accepted"):
            outcome, _new, _dt = s.run(entry, trace=False)
        self.assertEqual("slow", outcome)
        self.assertEqual(1, s.outcomes["slow"])
        self.assertEqual("slow", s.slow[0][1].kind)
        self.assertIn("corpus median", s.slow[0][1].detail)
        self.assertEqual([], s.crashes)

    def test_slow_records_go_to_their_own_file(self):
        s = B.Session("names", [])
        s.median = 0.002
        entry = {"id": "x2", "kind": "text", "data": "b", "from": "", "mutator": "", "arcs": 0}
        s.slow.append((entry, B.Crash("slow", "900 ms, 450x the corpus median of 2.0 ms")))
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(B, "CORPUS_DIR", td):
                self.assertEqual(1, B._record_slow("names", s, lambda *a: None))
                self.assertEqual(0, B._record_slow("names", s, lambda *a: None))
                path = B.corpus_path("names", slow=True)
                self.assertTrue(path.endswith("names.slow.jsonl"))
                recs = B.load(path)
        self.assertEqual(1, len(recs))
        self.assertEqual("slow", recs[0]["crash"])
        self.assertEqual(2.0, recs[0]["median_ms"])
        self.assertFalse(os.path.exists(B.corpus_path("names", crashes=True) + ".x"))

    def test_slow_records_on_file_replay_without_a_timing_assertion(self):
        # The probe suite carries crash files only; a slow file is a
        # finding to file, and every record on one must still read.
        for target in B.TARGETS:
            for record in B.load(B.corpus_path(target, slow=True)):
                entry = {k: record[k] for k in ("id", "kind", "data", "from", "mutator", "arcs")}
                outcome = B._with_rig(lambda: B.check(target, entry))
                self.assertIn(outcome, ("accepted", "refused"), (target, record["id"]))


class YieldTableTest(unittest.TestCase):

    def test_the_table_sums_the_window_and_sorts_by_cpu(self):
        now = datetime(2026, 10, 30, 0, 0, tzinfo=timezone.utc)
        runs = [_grow("a", "2026-10-29T20:00:00Z", tried=360, seconds=3600.0, kept=2, arcs=4),
                _grow("b", "2026-10-29T23:00:00Z", tried=7200, seconds=1800.0, accepted=10, refused=90),
                _grow("a", "2026-10-20T00:00:00Z", tried=1, seconds=99999.0, kept=50)]
        rows = B.yield_table(48, runs, now=now)
        self.assertEqual(["a", "b", "fleet"], [r["target"] for r in rows])
        a, b, fleet = rows
        self.assertEqual((1.0, 0.1, 2, 4), (a["cpu_h"], a["tries_per_s"], a["kept"], a["arcs"]))
        self.assertAlmostEqual(2.0, a["kept_per_cpu_h"])
        self.assertAlmostEqual(0.1, b["accepted_share"])
        self.assertEqual(2, fleet["runs"])
        self.assertAlmostEqual(1.5, fleet["cpu_h"])
        lines = B.format_yield(rows, 48)
        self.assertEqual(4, len(lines))
        self.assertIn("kept/cpu_h", lines[0])

    def test_stats_yield_prints_the_table(self):
        out = []
        args = argparse.Namespace(target="all", yield_table=True, hours=48)
        self.assertEqual(0, B.cmd_stats(args, out=out.append))
        self.assertTrue(out and out[0].startswith("de_dust2 yield"))


if __name__ == "__main__":
    unittest.main()
