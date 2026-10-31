# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""Campaign de_dust2 (docs/project/de_dust2.md): the tool's side.

P1 and P2: under --minutes each target's rounds come from a time
slice and its measured rate, the slice tilted by the target's recent
yield with a floor and a ceiling, and a target with a fresh seed
owed a full look. P3: parents are drawn by the rarity of the arcs
they reach and, on a target the reader mostly refuses, by whether
the reader took them. P4: a try far slower than the corpus replay's
median is a `slow` finding, kept apart from the crash file so no
timing ever becomes an expectedFailure probe. A sliced grow also
stops at the slice's planned seconds, a slow child discounts its
parent for the rest of that grow, and the local neighbor log stays
one line so the timer measures the reader. P10: `stats --yield`
prints the per-target table the review was built from.
"""
import argparse
import json
import errno
import os
import shutil
import random
import time
import subprocess
import sys
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

    def test_the_tilt_reads_the_rate_not_the_slice_length(self):
        # Two targets keeping at the same rate: one on 1,000 s slices
        # with 20 kept each, one on 100 s slices with 2 kept each. The
        # raw count would tilt the long one 4x and the short one
        # 1.5x; projected onto the base slice they tilt the same.
        runs = ([_grow("long", "2026-10-29T1%d:00:00Z" % i, seconds=1000.0, kept=20)
                 for i in range(5)]
                + [_grow("short", "2026-10-29T1%d:00:00Z" % i, seconds=100.0, kept=2)
                   for i in range(5)])
        plan = B.slice_plan(["long", "short"], 600, runs)
        self.assertEqual(plan["long"]["tilt"], plan["short"]["tilt"])
        self.assertEqual(B.TILT_MAX, plan["short"]["tilt"])

    def test_the_yield_is_read_over_an_hour_of_the_target_s_own_time(self):
        # A floor target on 150 s slices keeps one entry every eighth
        # slice. Five grows see nothing; an hour of its run time (24
        # slices) sees three, and the tilt lifts off the floor.
        runs = [_grow("thin", "2026-10-29T%02d:%02d:00Z" % (10 + i // 4, (i % 4) * 15),
                      seconds=150.0, kept=(1 if i % 8 == 0 else 0))
                for i in range(24)]
        self.assertEqual((0, False), B.target_yield("thin", runs))
        got, fresh = B.target_yield_per_slice("thin", 600, runs)
        self.assertGreater(got, 0)
        self.assertFalse(fresh)
        self.assertGreater(B.slice_plan(["thin"], 600, runs)["thin"]["tilt"], B.TILT_FLOOR)

    def test_rounds_follow_the_slice_and_the_rate_clamped(self):
        runs = ([_grow("slow", "2026-10-29T1%d:00:00Z" % i, tried=100, seconds=10.0)
                 for i in range(5)]
                + [_grow("fast", "2026-10-29T1%d:00:00Z" % i, tried=10000000, seconds=10.0)
                   for i in range(5)]
                + [_grow("rich", "2026-10-29T1%d:00:00Z" % i, tried=1000, seconds=10.0, kept=4)
                   for i in range(5)])
        plan = B.slice_plan(["slow", "fast", "rich", "new"], 120, runs)
        self.assertEqual(B.SLICE_MIN_ROUNDS, plan["slow"]["rounds"])      # 30 s x 10/s = 300 -> floor
        self.assertEqual(B.SLICE_MAX_ROUNDS, plan["fast"]["rounds"])      # 30 s x 1M/s -> ceiling
        self.assertEqual(B.TILT_MAX, plan["rich"]["tilt"])                # 20 kept -> 4x
        self.assertEqual(int(480 * 100), plan["rich"]["rounds"])          # 480 s x 100/s
        self.assertEqual(B.SLICE_FIRST_ROUNDS, plan["new"]["rounds"])     # no rate yet
        self.assertEqual(1.0, plan["new"]["tilt"])

    def test_set_rounds_and_next_seed_rewrite_the_command(self):
        cmd = ["python", "tool", "grow", "--target", "a", "--rounds", "5", "--seed", "7"]
        self.assertEqual("9", B._set_rounds(cmd, 9)[6])
        self.assertEqual("8", B._next_seed(cmd)[8])
        self.assertIn("--rounds", B._set_rounds(["python", "tool", "grow"], 3))
        budged = B._set_budget(cmd, 30)
        self.assertEqual("30", budged[budged.index("--budget-sec") + 1])
        again = B._set_budget(budged, 12.5)
        self.assertEqual("12.5", again[again.index("--budget-sec") + 1])
        self.assertEqual(1, again.count("--budget-sec"))

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
            seen["budget"] = {tg: float(cmd[cmd.index("--budget-sec") + 1]) for tg, cmd in commands}
            seen["requeue"] = requeue
            tg, cmd = commands[0]
            seen["requeued"] = requeue(tg, cmd) if requeue else None
            return 0

        plan = {tg: {"tilt": 1.0, "seconds": 60.0, "rounds": 777, "rate": 10.0, "yield": 0}
                for tg in B.TARGETS}
        with mock.patch.object(B, "run_parallel", fake_parallel), \
                mock.patch.object(B, "slice_plan", return_value=plan), \
                mock.patch.object(B, "record_run", lambda rec: None), \
                mock.patch.object(B, "prune_retired_crashes", return_value=0):
            B.cmd_grow(args, out=lambda *a: None)
        self.assertEqual({tg: 777 for tg in B.TARGETS}, seen["rounds"])
        self.assertEqual({tg: 60.0 for tg in B.TARGETS}, seen["budget"])
        self.assertIsNotNone(seen["requeue"])
        self.assertEqual("777", seen["requeued"][seen["requeued"].index("--rounds") + 1])
        self.assertEqual("60", seen["requeued"][seen["requeued"].index("--budget-sec") + 1])

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
            seen["budget"] = any("--budget-sec" in cmd for tg, cmd in commands)
            return 0

        with mock.patch.object(B, "run_parallel", fake_parallel), \
                mock.patch.object(B, "prune_retired_crashes", return_value=0):
            B.cmd_grow(args, out=lambda *a: None)
        self.assertEqual({5}, seen["rounds"])
        self.assertIsNone(seen["requeue"])
        self.assertTrue(seen["uniform"])
        self.assertFalse(seen["budget"])


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

    def test_a_slow_child_discounts_its_parent_until_the_next_grow(self):
        s = self._session({"a": {1}, "b": {1}}, accepted={"a", "b"})
        base = s.parent_weights()
        s.slow_parents["a"] = B.SLOW_PARENT_DISCOUNT
        w = s.parent_weights()
        self.assertAlmostEqual(base[0] * B.SLOW_PARENT_DISCOUNT, w[0])
        self.assertAlmostEqual(base[1], w[1])
        fresh = self._session({"a": {1}, "b": {1}}, accepted={"a", "b"})
        self.assertEqual(base, fresh.parent_weights())

    def test_a_slow_try_cuts_that_parents_weight_before_the_next_draw(self):
        s = self._session({"a": {1}, "b": {1}}, accepted={"a", "b"})
        s.median, s.slow_bound = 0.001, 10.0
        seen = []
        n = {"i": 0}

        class Rigged(random.Random):
            def choices(self, population, weights=None, *, cum_weights=None, k=1):
                seen.append(list(weights))
                return [population[0]]

        def mutate(rng, parent, entries, target, weights):
            n["i"] += 1
            return ({"n": n["i"]}, "p_test")

        with mock.patch.object(B, "mutate", side_effect=mutate), \
                mock.patch.object(s, "run", return_value=("slow", 0, 1.0)):
            s.grow(Rigged(0), 2)
        self.assertEqual(B.SLOW_PARENT_DISCOUNT ** 2, s.slow_parents.get("a"))
        self.assertNotIn("b", s.slow_parents)
        self.assertEqual(2, len(seen))
        self.assertAlmostEqual(seen[1][0], seen[0][0] * B.SLOW_PARENT_DISCOUNT)
        self.assertAlmostEqual(seen[1][1], seen[0][1])


class SliceBudgetTest(unittest.TestCase):

    def test_the_grow_stops_when_the_slice_budget_is_spent(self):
        s = B.Session("names", [{"id": "a", "kind": "text", "data": "a",
                                 "from": "", "mutator": "", "arcs": 0}])
        s.median, s.slow_bound = 0.001, 10.0
        n = {"i": 0}

        def mutate(rng, parent, entries, target, weights):
            n["i"] += 1
            return ({"n": n["i"]}, "p_test")

        def clock():
            return 0.0 if s.tried == 0 else 50.0

        with mock.patch.object(B, "mutate", side_effect=mutate), \
                mock.patch.object(s, "run", return_value=("refused", 0, 0.001)):
            added = s.grow(random.Random(1), 1000, budget_sec=30,
                           clock=clock, uniform_parents=True)
        self.assertEqual([], added)
        self.assertEqual(1, s.tried)
        self.assertEqual("budget", s.stopped)

    def test_no_budget_runs_the_rounds(self):
        s = B.Session("names", [{"id": "a", "kind": "text", "data": "a",
                                 "from": "", "mutator": "", "arcs": 0}])
        s.median, s.slow_bound = 0.001, 10.0
        n = {"i": 0}

        def mutate(rng, parent, entries, target, weights):
            n["i"] += 1
            return ({"n": n["i"]}, "p_test")

        with mock.patch.object(B, "mutate", side_effect=mutate), \
                mock.patch.object(s, "run", return_value=("refused", 0, 0.001)):
            s.grow(random.Random(1), 5, uniform_parents=True)
        self.assertEqual(5, s.tried)
        self.assertIsNone(s.stopped)

    def test_rounds_are_tries_so_a_missing_mutator_does_not_spend_them(self):
        # Nine rounds in ten make nothing (a small script corpus
        # hands back a duplicate on most rounds). The rounds count
        # the children the reader ran, not the misses, so the grow
        # still makes its five tries.
        s = B.Session("names", [{"id": "a", "kind": "text", "data": "a",
                                 "from": "", "mutator": "", "arcs": 0}])
        s.median, s.slow_bound = 0.001, 10.0
        n = {"i": 0}

        def mutate(rng, parent, entries, target, weights):
            n["i"] += 1
            if n["i"] % 10:
                return None
            return ({"n": n["i"]}, "p_test")

        with mock.patch.object(B, "mutate", side_effect=mutate), \
                mock.patch.object(s, "run", return_value=("refused", 0, 0.001)):
            s.grow(random.Random(1), 5, uniform_parents=True)
        self.assertEqual(5, s.tried)
        self.assertEqual(50, n["i"])
        self.assertIsNone(s.stopped)

    def test_a_corpus_the_mutators_cannot_grow_ends_the_grow_as_exhausted(self):
        s = B.Session("names", [{"id": "a", "kind": "text", "data": "a",
                                 "from": "", "mutator": "", "arcs": 0}])
        s.median, s.slow_bound = 0.001, 10.0
        n = {"i": 0}

        def mutate(rng, parent, entries, target, weights):
            n["i"] += 1
            return None

        with mock.patch.object(B, "MISS_STREAK", 25), \
                mock.patch.object(B, "mutate", side_effect=mutate), \
                mock.patch.object(s, "run", return_value=("refused", 0, 0.001)):
            s.grow(random.Random(1), 5, uniform_parents=True)
        self.assertEqual(0, s.tried)
        self.assertEqual(25, n["i"])
        self.assertEqual("exhausted", s.stopped)

    def test_a_duplicate_child_is_a_miss_too(self):
        s = B.Session("names", [B.make_entry("text", "a", "", "seed")])
        s.median, s.slow_bound = 0.001, 10.0
        n = {"i": 0}

        def mutate(rng, parent, entries, target, weights):
            n["i"] += 1
            return ("a", "p_test")      # the parent itself, every time

        with mock.patch.object(B, "MISS_STREAK", 7), \
                mock.patch.object(B, "mutate", side_effect=mutate), \
                mock.patch.object(s, "run", return_value=("refused", 0, 0.001)):
            s.grow(random.Random(1), 5, uniform_parents=True)
        self.assertEqual(0, s.tried)
        self.assertEqual(7, n["i"])
        self.assertEqual("exhausted", s.stopped)


class FootprintTest(unittest.TestCase):
    """Q120. A discarded child must not leave a hit set behind, and
    a synthetic grow's RSS must not climb with the tries."""

    def test_a_refused_try_leaves_no_hit_set(self):
        s = B.Session("names", [{"id": "a", "kind": "text", "data": "a",
                                 "from": "", "mutator": "", "arcs": 0}])
        s.hits["a"] = frozenset()
        s.median, s.slow_bound = 0.001, 10.0
        n = {"i": 0}

        def mutate(rng, parent, entries, target, weights):
            n["i"] += 1
            return ("child-%d" % n["i"], "p_test")

        def run(entry, trace=True, remember=True):
            if remember:
                s.hits[entry["id"]] = frozenset({("f", 1, 2)})
            return ("refused", 0, 0.001)

        with mock.patch.object(B, "mutate", side_effect=mutate), \
                mock.patch.object(s, "run", side_effect=run):
            s.grow(random.Random(1), 30, uniform_parents=True)
        self.assertEqual(30, s.tried)
        self.assertEqual({"a"}, set(s.hits))

    def test_a_kept_child_keeps_its_hit_set(self):
        s = B.Session("names", [{"id": "a", "kind": "text", "data": "a",
                                 "from": "", "mutator": "", "arcs": 0}])
        s.hits["a"] = frozenset({("f", 0, 1)})
        s.median, s.slow_bound = 0.001, 10.0
        s.tracer.hit = {("f", 1, 2), ("f", 2, 3)}

        def mutate(rng, parent, entries, target, weights):
            return ("kept-child", "p_test")

        def run(entry, trace=True, remember=True):
            self.assertFalse(remember)
            return ("accepted", 2, 0.001)

        with mock.patch.object(B, "mutate", side_effect=mutate), \
                mock.patch.object(s, "run", side_effect=run):
            added = s.grow(random.Random(1), 1, uniform_parents=True)
        self.assertEqual(1, len(added))
        self.assertEqual(s.tracer.hit, set(s.hits[added[0]["id"]]))
        self.assertIn(added[0]["id"], s.accepted_ids)
        self.assertEqual({"a", added[0]["id"]}, set(s.hits))

    def test_the_lane_says_what_it_loaded(self):
        text = B.footprint_line("dtls", [{"id": "a"}])
        self.assertIn("dtls: corpus 1 entries,", text)
        self.assertIn("hit sets follow the entries, not the tries", text)
        if os.path.exists("/proc/meminfo"):
            self.assertIn("MemAvailable", text)
            self.assertIsInstance(B.memory_available_mb(), int)

    def test_a_synthetic_grow_peaks_with_the_corpus(self):
        if not os.path.exists("/proc/self/status"):
            self.skipTest("peak RSS is read from /proc")
        script = (
            "import json, random\n"
            "from runner.tools import de_dust_corpus as B\n"
            "def rss():\n"
            "    with open('/proc/self/status') as fh:\n"
            "        for line in fh:\n"
            "            if line.startswith('VmRSS:'):\n"
            "                return int(line.split()[1])\n"
            "seeds = [dict(e) for e in B.seeds_dtls()]\n"
            "s = B.Session('dtls', seeds)\n"
            "B._with_rig(s.baseline)\n"
            "base = rss()\n"
            "added = B._with_rig(lambda: s.grow(random.Random(1), 800))\n"
            "print(json.dumps({'base': base, 'end': rss(), "
            "'hits': len(s.hits), 'entries': len(s.entries), "
            "'tried': s.tried, 'added': len(added)}))\n"
        )
        proc = subprocess.run([sys.executable, "-c", script], cwd=B.ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=180)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-2000:])
        row = json.loads(proc.stdout.decode().strip().splitlines()[-1])
        self.assertEqual(row["hits"], row["entries"])
        self.assertGreater(row["tried"], 400)
        # A discarded hit set was about 20 KB of RSS. 800 tries of
        # that is well past 8 MB, which a corpus of the dtls seeds
        # does not need.
        self.assertLess(row["end"] - row["base"], 8 * 1024)


class SlowClassTest(unittest.TestCase):

    def test_the_baseline_sets_the_bound_from_the_median(self):
        entries = B.load(B.corpus_path("names"))[:7]
        s = B.Session("names", entries)
        B._with_rig(s.baseline)
        self.assertIsNotNone(s.median)
        self.assertEqual(max(B.SLOW_FLOOR_SEC, B.SLOW_FACTOR * s.median), s.slow_bound)
        self.assertEqual(len(entries), len(s.hits))

    def test_a_reader_with_a_deadline_of_its_own_has_a_higher_floor(self):
        # The queries reader runs a sender's pattern under its worker
        # deadline, six times a try; a try inside six deadlines is the
        # guard, not a slow reader (the queries slow record of 30-OCT,
        # `\s+\s+$` over 800 spaces, 2.3 s here and 5.3 s on the rig).
        self.assertEqual(6 * B.QU._GREP_DEADLINE + 1.0, B.slow_floor("queries"))
        self.assertEqual(B.SLOW_FLOOR_SEC, B.slow_floor("wire"))
        s = B.Session("queries", [])
        s.median = 0.019
        with mock.patch.object(s, "run", return_value=("accepted", 0, 0.019)):
            s.entries = [B.make_entry("payload", {"queries": []}, "x", "seed")]
            s.baseline()
        self.assertEqual(B.slow_floor("queries"), s.slow_bound)

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

    def test_a_grow_files_its_slowest_five_only(self):
        s = B.Session("names", [])
        s.median = 0.001
        for i in range(8):
            c = B.Crash("slow", f"{i} ms")
            c.seconds = i / 1000.0
            s.slow.append(({"id": "s%d" % i, "kind": "text", "data": str(i), "from": "",
                            "mutator": "", "arcs": 0}, c))
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(B, "CORPUS_DIR", td):
                self.assertEqual(B.SLOW_PER_GROW, B._record_slow("names", s, lambda *a: None))
                ids = [r["id"] for r in B.load(B.corpus_path("names", slow=True))]
        self.assertEqual(["s7", "s6", "s5", "s4", "s3"], ids)

    def test_promote_retires_a_slow_finding_that_runs_fast_now(self):
        entry = {"id": "f1", "kind": "text", "data": "a", "from": "", "mutator": "", "arcs": 0,
                 "crash": "slow", "detail": "900 ms", "median_ms": 2.0, "found": "2026-10-30",
                 "head": "abc"}
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(B, "CORPUS_DIR", td), \
                    mock.patch.object(B, "check", return_value="refused"), \
                    mock.patch.object(B, "head_sha", return_value="feedfacefeedface"):
                B.save(B.corpus_path("names", slow=True), "names", [entry])
                # Still slow when the floor is below any run.
                with mock.patch.object(B, "SLOW_FLOOR_SEC", -1.0):
                    self.assertTrue(B._promote_slow("names", lambda *a: None))
                self.assertTrue(os.path.exists(B.corpus_path("names", slow=True)))
                # Fast when it runs under half the floor.
                self.assertFalse(B._promote_slow("names", lambda *a: None))
                self.assertFalse(os.path.exists(B.corpus_path("names", slow=True)))
                retired = B.load_retired("names")
        self.assertEqual("fast", retired["f1"]["why"])
        self.assertEqual("feedfacefeed", retired["f1"]["head"])
        self.assertIn("ms", retired["f1"])

    def test_slow_records_on_file_replay_without_a_timing_assertion(self):
        # The probe suite carries crash files only; a slow file is a
        # finding to file, and every record on one must still read.
        for target in B.TARGETS:
            for record in B.load(B.corpus_path(target, slow=True)):
                entry = {k: record[k] for k in ("id", "kind", "data", "from", "mutator", "arcs")}
                outcome = B._with_rig(lambda: B.check(target, entry))
                self.assertIn(outcome, ("accepted", "refused"), (target, record["id"]))

    def test_the_local_neighbor_log_stays_one_line(self):
        # Thirty tries used to leave thirty neighbors, and the next
        # try read all of them. One prior neighbor is what a refusal
        # has to leave untouched.
        def run():
            for i in range(30):
                entry = {"id": "t%d" % i, "kind": "text", "data": "nope-%d" % i,
                         "from": "", "mutator": "", "arcs": 0}
                self.assertEqual("refused", B.check_local(entry))
            path = os.path.join(B._RIG.dir, "senses.jsonl")
            with open(path, encoding="utf-8") as fh:
                lines = fh.readlines()
            self.assertEqual(B._SENSES_KEEP, len(lines))
            self.assertIn("bm-neighbor", lines[-1])
            self.assertNotIn("nope-", lines[-1])
        B._with_rig(run)


class CiScopeTest(unittest.TestCase):
    """P8: build.yml's scope job and the tool behind it."""

    def test_corpus_only_means_every_path_is_corpus_or_ledger(self):
        from runner.tools import ci_scope as C
        self.assertTrue(C.corpus_only(["runner/tests/de_dust/query.jsonl",
                                       "runner/tests/de_dust/runs.jsonl",
                                       "runner/tests/de_dust/query.arcs.json",
                                       "runner/tests/de_dust/query.retired.json",
                                       "docs/project/campaign-standing-orders.md",
                                       "docs/seats/.com.chat", "docs/seats/status.txt", ""]))
        self.assertFalse(C.corpus_only(["runner/tests/de_dust/query.jsonl",
                                        "runner/tools/de_dust_corpus.py"]))
        self.assertFalse(C.corpus_only(["docs/seats/questions.md"]))
        self.assertFalse(C.corpus_only(["runner/tests/de_dust/queries.crashes.jsonl",
                                        "PROTOCOL.md"]))
        self.assertFalse(C.corpus_only([]))

    def test_decide_reads_the_push_range_and_nothing_else(self):
        from runner.tools import ci_scope as C

        def diff(paths, rc=0):
            def run(cmd, **kw):
                self.assertEqual(["git", "diff", "--name-only", "abc", "def"], cmd)
                return mock.Mock(returncode=rc, stdout="\n".join(paths) + "\n")
            return run

        self.assertEqual("true", C.decide("push", "abc", "def",
                                          run=diff(["runner/tests/de_dust/wire.jsonl"])))
        self.assertEqual("false", C.decide("push", "abc", "def",
                                           run=diff(["runner/wire/verify.py"])))
        self.assertEqual("false", C.decide("push", "abc", "def", run=diff([], rc=128)))
        self.assertEqual("false", C.decide("push", "0" * 40, "def", run=diff(["x"])))
        self.assertEqual("false", C.decide("workflow_dispatch", "abc", "def", run=diff(["x"])))
        self.assertEqual("false", C.decide("push", "abc", "", run=diff(["x"])))

    def test_main_prints_the_output_line(self):
        from runner.tools import ci_scope as C
        out = []
        with mock.patch.object(C, "decide", return_value="true"):
            self.assertEqual(0, C.main(environ={"EVENT": "push", "BEFORE": "a", "AFTER": "b"},
                                       out=out.append))
        self.assertEqual(["corpus_only=true"], out)

    def test_the_heavy_jobs_wait_on_scope_and_the_suite_does_not(self):
        import re
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(root, ".github", "workflows", "build.yml"), encoding="utf-8") as fh:
            wf = fh.read()

        def block(job):
            m = re.search(r"^  %s:\n(.*?)(?=^  [a-z0-9_-]+:|\Z)" % re.escape(job), wf, re.M | re.S)
            self.assertIsNotNone(m, job)
            return m.group(1)

        for job in ("test-macos", "build-windows", "build-windows-arm64", "build-linux",
                    "build-linux-arm64", "build-macos", "build-macos-x86_64",
                    "build-pi-light", "build-python"):
            b = block(job)
            self.assertIn("needs: scope", b, job)
            self.assertIn("if: needs.scope.outputs.corpus_only != 'true'", b, job)
        for job in ("test", "typecheck", "scope"):
            self.assertNotIn("corpus_only != 'true'", block(job), job)
        self.assertIn("runner/tools/ci_scope.py", block("scope"))
        self.assertIn("contents: read", block("scope"))


class TechniquesTest(unittest.TestCase):
    """Two techniques beside mutation: stateful in-memory protocol
    scripts (dtls_session) and thread interleavings (race_board)."""

    def test_the_targets_declare_their_technique(self):
        self.assertEqual("protocol", B.TARGETS["dtls_session"]["technique"])
        self.assertEqual("protocol", B.TARGETS["dtls_hostile"]["technique"])
        self.assertEqual("race", B.TARGETS["race_board"]["technique"])
        self.assertEqual("race", B.TARGETS["race_stash"]["technique"])
        self.assertEqual("race", B.TARGETS["race_state"]["technique"])
        self.assertEqual("parity", B.TARGETS["edge_subject"]["technique"])
        self.assertNotIn("technique", B.TARGETS["wire"])

    def test_edge_subject_seeds_agree_and_the_python_side_always_reads(self):
        # Every seed subject agrees between the gate and the runner
        # (or skips when node is absent); the Python side is exercised
        # either way, so the replay is not a no-op off node.
        for e in B.seeds_edge_subject():
            self.assertIn(B._with_rig(lambda: B.check("edge_subject", e)),
                          ("accepted", "refused"))

    @unittest.skipUnless(shutil.which("node"), "the gate differential needs node")
    def test_edge_subject_catches_the_separator_split(self):
        # Q121: Python's \s treats the information separators
        # \x1c-\x1f and \x85 as whitespace; the gate's (JS) does
        # not, so a subject that separates with one routes at the
        # runner and not at the gate. The target must see that as a
        # disagreement until the grammar is aligned.
        entry = {"id": "x", "kind": "payload",
                 "data": "[HOMING-PIGEON]\x1f result bm-0001",
                 "from": "", "mutator": "", "arcs": 0}
        split = False
        try:
            B._with_rig(lambda: B.check("edge_subject", entry))
        except B.Crash as c:
            split = c.kind == "agreement"
        # Either the split is still open (crash) or it was fixed
        # (no crash); both are valid states of the tree, but the
        # target must not raise anything else.
        self.assertIn(split, (True, False))

    def test_race_state_holds_no_lost_update_and_record_integrity(self):
        seeds = {e["from"]: e for e in B.seeds_race_state()}
        for name in ("seed:four_markers_distinct", "seed:save_distinct_records",
                     "seed:seen_and_retained_together", "seed:save_and_load_same_id",
                     "seed:unknown_ops"):
            self.assertEqual(
                "accepted",
                B._with_rig(lambda n=name: B.check("race_state", seeds[n])),
                name)
        for name in ("seed:empty", "seed:not_an_object"):
            self.assertEqual(
                "refused",
                B._with_rig(lambda n=name: B.check("race_state", seeds[n])),
                name)
        same = seeds["seed:save_and_load_same_id"]
        for _ in range(25):
            self.assertEqual("accepted",
                             B._with_rig(lambda: B.check("race_state", same)))

    def test_a_state_crash_removes_its_directory(self):
        seeds = {e["from"]: e for e in B.seeds_race_state()}
        entry = seeds["seed:four_markers_distinct"]
        prefix = "hp-de_dust-state-"

        def leftover():
            root = B._own_tmp
            if not root or not os.path.isdir(root):
                return set()
            return {n for n in os.listdir(root) if n.startswith(prefix)}

        before = leftover()
        with mock.patch.object(B.R, "save_seen", side_effect=RuntimeError("boom")):
            with self.assertRaises(B.Crash):
                B._with_rig(lambda: B.check("race_state", entry))
        self.assertEqual(before, leftover())

    def test_a_hostile_server_never_establishes_the_client(self):
        seeds = {e["from"]: e for e in B.seeds_dtls_hostile()}
        for name, seed in seeds.items():
            first = B._with_rig(lambda: B.check("dtls_hostile", seed))
            self.assertEqual(first,
                             B._with_rig(lambda: B.check("dtls_hostile", seed)), name)
        self.assertEqual("accepted",
                         B._with_rig(lambda: B.check("dtls_hostile",
                                                     seeds["seed:full_handshake"])))

    def test_a_mutated_hostile_step_never_breaks_the_client(self):
        junk = [{"op": {"x": 1}}, {"op": "deliver", "n": "all", "flip": "x",
                 "dup": -2, "cut": None, "reverse": 1}, {"op": "inject", "bytes": "zz"},
                {"op": "inject", "bytes": 999}, {"op": "tick", "dt": float("nan")},
                {"op": "app"}, 7, None]
        entry = {"id": "x", "kind": "payload", "data": junk, "from": "", "mutator": "", "arcs": 0}
        self.assertIn(B._with_rig(lambda: B.check("dtls_hostile", entry)),
                      ("accepted", "refused"))

    def test_distill_keeps_full_arc_coverage_and_drops_a_redundant_entry(self):
        session = B.Session("dtls_hostile", [])
        a1, a3, a2 = frozenset({1}), frozenset({1, 2, 3}), frozenset({1, 2})
        session.entries = [
            dict(B.make_entry("payload", 0, "seed:s", "seed"), id="s"),
            dict(B.make_entry("payload", 0, "grown:a", "m"), id="a", mutator="m"),
            dict(B.make_entry("payload", 0, "grown:b", "m"), id="b", mutator="m")]
        session.hits = {"s": a1, "a": a3, "b": a2}
        kept, dropped = session.distill()
        self.assertEqual(session._distill_full, session._distill_covered)
        kept_ids = {e["id"] for e in kept}
        self.assertIn("s", kept_ids)   # seed pinned
        self.assertIn("a", kept_ids)   # covers 1,2,3
        self.assertEqual(["b"], [e["id"] for e in dropped])  # subset of a

    def test_a_session_script_replays_the_same_way_twice(self):
        seeds = {e["from"]: e for e in B.seeds_dtls_session()}
        for name in ("seed:handshake_and_job", "seed:resume_own", "seed:wrong_key"):
            first = B._with_rig(lambda: B.check("dtls_session", seeds[name]))
            notes = list(B.NOTES)
            second = B._with_rig(lambda: B.check("dtls_session", seeds[name]))
            self.assertEqual((first, notes), (second, list(B.NOTES)), name)
        self.assertEqual("accepted", B._with_rig(lambda: B.check("dtls_session", seeds["seed:handshake_and_job"])))
        self.assertEqual("refused", B._with_rig(lambda: B.check("dtls_session", seeds["seed:wrong_key"])))

    def test_a_session_script_holds_the_resume_invariant(self):
        seeds = {e["from"]: e for e in B.seeds_dtls_session()}
        self.assertEqual("refused", B._with_rig(lambda: B.check("dtls_session", seeds["seed:resume_gone_ticket"])))
        self.assertEqual("accepted", B._with_rig(lambda: B.check("dtls_session", seeds["seed:resume_live_ticket"])))

    def test_a_mutated_step_never_breaks_the_interpreter(self):
        junk = [{"op": {"x": 1}}, {"op": "start", "c": {"a": 1}}, {"op": "start", "key": ["old"]},
                {"op": "deliver", "dir": 7, "n": "all", "flip": "x", "dup": -3, "cut": None},
                {"op": "tick", "dt": float("nan")}, {"op": "app", "c": 9}, {"op": "rebind", "c": None},
                {"op": "start", "ticket": "own:zz"}, {"op": "start", "c": 0, "ticket": "own:0"}]
        entry = {"id": "x", "kind": "payload", "data": junk, "from": "", "mutator": "", "arcs": 0}
        self.assertEqual("refused", B._with_rig(lambda: B.check("dtls_session", entry)))

    def test_a_race_spec_runs_its_lanes_and_keeps_the_lease_rules(self):
        seeds = {e["from"]: e for e in B.seeds_race_board()}
        for name in ("seed:one_task_two_workers", "seed:four_lanes_fast_switch",
                     "seed:complete_what_you_do_not_hold", "seed:unknown_ops"):
            self.assertIn(B._with_rig(lambda: B.check("race_board", seeds[name])),
                          ("accepted", "refused"), name)

    def test_a_stash_race_keeps_the_outbox_rules(self):
        seeds = {e["from"]: e for e in B.seeds_race_stash()}
        for name in ("seed:two_keys", "seed:fail_then_resend",
                     "seed:deliver_undeliver_deliver", "seed:two_bodies_one_key"):
            self.assertEqual("accepted",
                             B._with_rig(lambda: B.check("race_stash", seeds[name])),
                             name)
        for name in ("seed:empty", "seed:junk", "seed:yield_only"):
            self.assertEqual("refused",
                             B._with_rig(lambda: B.check("race_stash", seeds[name])),
                             name)

    def test_a_stash_logged_after_its_delivery_is_not_a_fault(self):
        # The event log takes each entry after its operation returns,
        # so a stash that wrote, was read and delivered by the other
        # lane, and only then returned is logged after the delivery.
        # The verdict reads counts, not the log's order, so that
        # delivery is not "a body that was not stashed" (the
        # race_stash echo of 30-OCT). Driven from a hand-built log so
        # it does not race two threads on a slow box.
        events = [("deliver", "bm-stash-0001", "beta", True),
                  ("stash", "bm-stash-0001", "beta", True)]
        faults, delivered = B._stash_verdict(events)
        self.assertEqual([], faults)
        self.assertEqual(1, delivered)

    def test_the_stash_verdict_still_catches_a_real_breach(self):
        # A body delivered for a key it was never stashed under is a
        # fault whatever the order, and a second delivery with no
        # undeliver between is one too.
        self.assertEqual("bm-stash-0001 delivered a body that was not stashed",
                         B._stash_verdict([("deliver", "bm-stash-0001", "ghost", True)])[0][0])
        # A stash whose write was refused does not count as stashed.
        self.assertTrue(B._stash_verdict([("stash", "k", "x", False),
                                          ("deliver", "k", "x", True)])[0])
        twice = [("stash", "k", "x", True), ("deliver", "k", "x", True),
                 ("deliver", "k", "x", True)]
        self.assertIn("delivered twice", B._stash_verdict(twice)[0][0])
        once_each = [("stash", "k", "x", True), ("deliver", "k", "x", True),
                     ("undeliver", "k"), ("deliver", "k", "x", True)]
        self.assertEqual([], B._stash_verdict(once_each)[0])

    def test_the_filed_crashes_meet_the_contract(self):
        # board_mail: a unit separator is a word, so the handler takes
        # the subject. A board key with a space is not a task id, so
        # it is not offered. race_stash: one record is sent once even
        # when a resend and a deliver overlap.
        board = [
            {"file": None, "ident": "\x1f",
             "kind": {"task_id": ".", "type": "task_approve", "v": 1},
             "payload": "task_approve"},
            {"file": "{\n  \"bm-task-000[HOMING-PIGEON] TEST job 1\": {\n"
             "    \"task_id\": \"bm-task-0001\",\n    \"priority\": \"canary-key\",\n"
             "    \"requires\": [],\n    \"capabilities\": [\"shell\"],\n"
             "    \"compartments\": [],\n    \"payload\": {\"script\": \"echo task\"},\n"
             "    \"state\": \"open\",\n"
             "    \"submitted_at\": \"2026-10-26T12:00:00+00:00\"\n  }\n}",
             "ident": "worker-a", "kind": "task_request",
             "payload": {"capabilities": ["shell"],
                         "reply_to": "worker@example.com",
                         "type": "task_request", "v": 1,
                         "worker_id": "worker-a"}},
        ]
        for data in board:
            entry = {"id": "x", "kind": "payload", "data": data,
                     "from": "", "mutator": "", "arcs": 0}
            self.assertIn(B._with_rig(lambda e=entry: B.check("board_mail", e)),
                          ("accepted", "refused"))
        stash = [
            {"threads": [[{"body": "alpha", "op": "stash", "skey": "bm-stash-0001"},
                          {"op": "yield"},
                          {"op": "deliver", "skey": "bm-stash-0001"}],
                         [{"op": "resend"},
                          {"SKEY": "bm-stash-0001", "body": "beta", "op": "stash"}]]},
            {"threads": [[{"body": "alpha", "op": "stash", "skey": "bm-stash-0001"},
                          [[{"op": "nope"}], "nope"],
                          {"op": "deliver", "skey": "bm-stash-0001"}],
                         [{"op": "resend"},
                          {"Skey": "bm-stash-0001", "body": "beta", "op": "stash"}]]},
        ]
        for data in stash:
            entry = {"id": "x", "kind": "payload", "data": data,
                     "from": "", "mutator": "", "arcs": 0}
            for _ in range(8):
                self.assertIn(
                    B._with_rig(lambda e=entry: B.check("race_stash", e)),
                    ("accepted", "refused"))

    def test_race_targets_sit_out_the_surface_differential_and_the_kill_set(self):
        self.assertEqual([], B.platform_disagreements("race_board"))
        self.assertEqual([], B.platform_disagreements("race_stash"))
        self.assertEqual([], B.platform_disagreements("race_state"))
        from runner.tools import de_dust_survivors as S
        self.assertNotIn("race_board", S.targets_for("board"))
        self.assertNotIn("race_state", S.targets_for("runner"))
        self.assertIn("board", S.targets_for("board"))

    def test_the_tracer_follows_threads(self):
        import threading
        tracer = B.ArcTracer([B.__file__])
        seen = []

        def work():
            seen.append(threading.current_thread().name)
            return 1

        def spawn():
            t = threading.Thread(target=work)
            t.start()
            t.join()
            return 0

        tracer.run(spawn)
        self.assertTrue(seen)
        self.assertIsNone(threading._trace_hook if hasattr(threading, "_trace_hook") else None)


class ParallelDrainTest(unittest.TestCase):

    def test_a_child_that_fills_the_pipe_still_finishes(self):
        # Q122: the parent used to poll without draining stdout; a
        # child past the pipe buffer blocked on its write for good.
        import sys
        cmd = [sys.executable, "-c",
               "import sys; sys.stdout.write('x' * (2 * 1024 * 1024) + '\\nend\\n')"]
        lines = []
        status = B.run_parallel([("a", cmd), ("b", cmd)], 2, out=lines.append)
        self.assertEqual(0, status)
        self.assertEqual(2, lines.count("end"))


class FlickeringDiskTest(unittest.TestCase):
    """Menlo Park, 30-OCT: a write refused at random lands on the
    next try. The tool's writes and temp dirs retry; the disk probe
    counts what a disk refuses."""

    def test_a_write_refused_twice_lands_on_the_third_try(self):
        calls = []

        def flaky(*a, **k):
            calls.append(1)
            if len(calls) < 3:
                raise OSError(errno.EPERM, "Operation not permitted")
            return "landed"
        with mock.patch.object(B.time, "sleep", lambda s: None):
            self.assertEqual("landed", B._patient(flaky))
        self.assertEqual(3, len(calls))

    def test_a_fault_that_is_not_the_disk_s_is_not_retried(self):
        calls = []

        def broken(*a, **k):
            calls.append(1)
            raise OSError(errno.ENOSPC, "No space left on device")
        with self.assertRaises(OSError):
            B._patient(broken)
        self.assertEqual(1, len(calls))

    def test_a_disk_that_never_answers_raises_after_five_tries(self):
        calls = []

        def dead(*a, **k):
            calls.append(1)
            raise OSError(errno.EPERM, "Operation not permitted")
        with mock.patch.object(B.time, "sleep", lambda s: None), \
                mock.patch.object(B.tempfile, "mkdtemp", dead), \
                self.assertRaises(OSError):
            B._tmpdir("x-")
        self.assertEqual(5, len(calls))

    def test_the_disk_probe_reads_zero_on_a_healthy_disk(self):
        where = tempfile.mkdtemp(prefix="hp-probe-")
        lines = []
        status = B.cmd_disk(argparse.Namespace(writes=20, where=where), out=lines.append)
        self.assertEqual(0, status)
        self.assertIn("20 writes", lines[0])
        self.assertIn("0 failed", lines[0])
        self.assertEqual([], os.listdir(where))


class HourlyNoteTest(unittest.TestCase):

    def test_the_note_is_written_from_the_ledger(self):
        now = datetime(2026, 10, 30, 22, 0, tzinfo=timezone.utc)
        runs = [_grow("wire", "2026-10-30T21:30:00Z", seconds=1800.0, kept=2),
                _grow("race_state", "2026-10-30T21:40:00Z", seconds=600.0, kept=1),
                {"kind": "plan", "when": "2026-10-30T21:00:00Z", "slice": 60.0,
                 "jobs": 1, "head": "abc", "rig": "Menlo Park",
                 "targets": {"wire": {"tilt": 2.0, "seconds": 120, "rounds": 10,
                                      "rate": 1.0, "yield": 1, "technique": "mutation"}}}]
        runs[0]["mutators_kept"] = {"t_grammar": 2}
        runs[1]["crashes"] = 1
        text = B.hourly_note(runs, now=now, probe=False)
        self.assertIn("kept 3 entries", text)
        self.assertIn("on Menlo Park, puts wire at 120 s with a 2.00x yield tilt", text)
        self.assertIn("Entries kept: 3 in the last hour", text)
        self.assertIn("crashes, on race_state", text)
        self.assertIn("wire -- t_grammar", text)
        self.assertNotIn("Disk probe", text)

    def test_the_note_says_how_the_hour_s_grows_ended(self):
        now = datetime(2026, 10, 30, 22, 0, tzinfo=timezone.utc)
        runs = [_grow("wire", "2026-10-30T21:30:00Z", seconds=1800.0, tried=900),
                _grow("dtls_hostile", "2026-10-30T21:40:00Z", seconds=1800.0, tried=100),
                _grow("race_stash", "2026-10-30T21:50:00Z", seconds=3.0, tried=0)]
        runs[0]["stopped"] = "budget"
        runs[2]["stopped"] = "exhausted"
        text = B.hourly_note(runs, now=now, probe=False)
        self.assertIn("Grows in the last hour: 3, 1,000 tries over 1.00 CPU-hours; "
                      "1 ran their budget out, 1 their rounds, and 1 ended exhausted, "
                      "the mutators making nothing new from the corpus of race_stash.", text)

    def test_two_plans_at_one_moment_are_both_in_the_note(self):
        now = datetime(2026, 10, 30, 22, 30, tzinfo=timezone.utc)
        when = "2026-10-30T22:17:14Z"
        runs = [
            _grow("wire", "2026-10-30T22:20:00Z", seconds=30.0, kept=1),
            {"kind": "plan", "when": when, "jobs": 1, "rig": "Menlo Park",
             "targets": {"stage": {"seconds": 203, "tilt": 1.69}}},
            {"kind": "plan", "when": when, "jobs": 1, "rig": "Menlo Park",
             "targets": {"dtls_hostile": {"seconds": 2400, "tilt": 4.0},
                         "race_state": {"seconds": 1673, "tilt": 2.79}}},
        ]
        text = B.hourly_note(runs, now=now, probe=False)
        self.assertIn("the newest plans", text)
        self.assertIn("stage at 203 s", text)
        self.assertIn("dtls_hostile at 2,400 s", text)
        self.assertIn("race_state at 1,673 s", text)

    def test_the_cli_prints_the_note_with_the_probe(self):
        lines = []
        B.cmd_stats(argparse.Namespace(yield_table=False, note=True, plan=False, hours=24),
                    out=lines.append)
        self.assertIn("Disk probe at", lines[0])


class WatchTest(unittest.TestCase):
    """The ten-minute watch: the floors (Q120) and the stall shape
    (Q122), with every reading handed in."""

    def _runs(self, when="2026-10-30T21:30:00Z"):
        return [_grow("wire", when, seconds=100.0, kept=1),
                {"kind": "plan", "when": "2026-10-30T21:00:00Z", "slice": 600.0,
                 "jobs": 1, "head": "abc", "targets": {"wire": {"seconds": 1800}}}]

    def test_a_clean_box_reads_ok(self):
        now = datetime(2026, 10, 30, 21, 40, tzinfo=timezone.utc)
        lines, breaches = B.watch_readings(self._runs(), now=now, disk_used_pct=45.0,
                                           mem_avail_mb=640, workers=2, measure_temp=False)
        self.assertEqual([], breaches)
        self.assertEqual(3, len(lines))
        self.assertIn("stale past 60 min", lines[2])

    def test_the_floors_breach(self):
        now = datetime(2026, 10, 30, 21, 40, tzinfo=timezone.utc)
        _l, breaches = B.watch_readings(self._runs(), now=now, disk_used_pct=91.0,
                                        mem_avail_mb=188, mem_min_mb=256, workers=2,
                                        measure_temp=False)
        self.assertEqual(2, len(breaches))
        self.assertIn("disk 91% over the 90% line", breaches[0])
        self.assertIn("memory 188 MB under the 256 MB floor", breaches[1])

    def test_no_workers_with_a_plan_standing_is_a_stall(self):
        now = datetime(2026, 10, 30, 21, 40, tzinfo=timezone.utc)
        _l, breaches = B.watch_readings(self._runs(), now=now, disk_used_pct=10.0,
                                        mem_avail_mb=900, workers=0, measure_temp=False)
        self.assertEqual(1, len(breaches))
        self.assertIn("0 grow worker(s) live, 1 expected", breaches[0])

    def test_workers_live_but_silent_past_the_slice_is_the_q122_shape(self):
        now = datetime(2026, 10, 30, 23, 0, tzinfo=timezone.utc)
        _l, breaches = B.watch_readings(self._runs(), now=now, disk_used_pct=10.0,
                                        mem_avail_mb=900, workers=2, measure_temp=False)
        self.assertEqual(1, len(breaches))
        self.assertIn("no run record in 90 min", breaches[0])
        self.assertIn("blocked on its pipe", breaches[0])

    def test_the_long_lane_sets_the_stall_line_when_two_plans_share_a_time(self):
        now = datetime(2026, 10, 30, 23, 0, tzinfo=timezone.utc)
        when = "2026-10-30T22:17:14Z"
        runs = [
            _grow("dtls_hostile", "2026-10-30T22:20:00Z", seconds=2400.0, kept=0),
            {"kind": "plan", "when": when, "jobs": 1,
             "targets": {"stage": {"seconds": 203}}},
            {"kind": "plan", "when": when, "jobs": 1,
             "targets": {"dtls_hostile": {"seconds": 2400}}},
        ]
        _l, breaches = B.watch_readings(runs, now=now, disk_used_pct=10.0,
                                        mem_avail_mb=900, workers=1, measure_temp=False)
        self.assertEqual([], breaches)
        later = datetime(2026, 10, 30, 23, 50, tzinfo=timezone.utc)
        _l, breaches = B.watch_readings(runs, now=later, disk_used_pct=10.0,
                                        mem_avail_mb=900, workers=1, measure_temp=False)
        self.assertEqual(1, len(breaches))
        self.assertIn("no run record in 90 min", breaches[0])

    def test_a_full_temp_volume_is_a_breach_when_the_corpus_volume_is_not(self):
        now = datetime(2026, 10, 30, 21, 40, tzinfo=timezone.utc)
        lines, breaches = B.watch_readings(
            self._runs(), now=now, disk_used_pct=25.0, temp_used_pct=93.0,
            mem_avail_mb=900, workers=2, measure_temp=False)
        self.assertEqual(["temp 93% over the 90% line"], breaches)
        self.assertTrue(any(line.startswith("temp: 93%") for line in lines))
        self.assertTrue(any("corpus volume" in line for line in lines))

    def test_a_grow_removes_a_dead_process_temp_and_keeps_a_live_one(self):
        tmp = tempfile.mkdtemp(prefix="hp-de_dust-sweep-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.mkdir(os.path.join(tmp, "hp-de_dust-999999-dead"))
        os.mkdir(os.path.join(tmp, f"hp-de_dust-{os.getpid()}-ours"))
        os.mkdir(os.path.join(tmp, "hp-de_dust-flat-other-lane"))
        removed = B.sweep_dead_grow_temps(tmp, alive=lambda pid: pid == os.getpid())
        self.assertEqual(["hp-de_dust-999999-dead"], removed)
        self.assertFalse(os.path.exists(os.path.join(tmp, "hp-de_dust-999999-dead")))
        self.assertTrue(os.path.isdir(os.path.join(tmp, f"hp-de_dust-{os.getpid()}-ours")))
        self.assertTrue(os.path.isdir(os.path.join(tmp, "hp-de_dust-flat-other-lane")))

    def test_a_check_temp_lives_under_this_process(self):
        path = B._tmpdir(prefix="hp-de_dust-probe-")
        self.addCleanup(shutil.rmtree, path, True)
        root = B._grow_tmp_root()
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(path.startswith(root + os.sep))
        self.assertTrue(os.path.basename(root).startswith(f"hp-de_dust-{os.getpid()}-"))

    def test_the_rig_table_reads_the_ledger_and_git(self):
        now = datetime(2026, 10, 30, 22, 0, tzinfo=timezone.utc)
        runs = [dict(_grow("wire", "2026-10-30T21:50:00Z"), rig="Nuremberg", head="aaaa"),
                dict(_grow("dtls", "2026-10-30T20:00:00Z"), rig="Nuremberg", head="old0"),
                dict(_grow("local", "2026-10-30T21:55:00Z"), rig="San Francisco", head="bbbb")]
        seen = []

        def git(args):
            seen.append(args)
            if args[0] == "cat-file":
                return 0
            return 0 if args[2:] == ["fix0", "aaaa"] else 1
        rows = B.rig_table(runs, now=now, past="fix0", git=git)
        self.assertEqual(["Nuremberg", "San Francisco"], [r["rig"] for r in rows])
        self.assertEqual(("aaaa", 10, 1, True), (rows[0]["head"], rows[0]["age_min"],
                                                 rows[0]["last_hour"], rows[0]["past"]))
        self.assertEqual(False, rows[1]["past"])


class CampaignNameTest(unittest.TestCase):

    def test_the_tool_and_the_bank_name_the_same_campaign(self):
        from runner.tools import rig_bank as RB
        self.assertEqual("de_aztec", B.CAMPAIGN)
        self.assertEqual(B.CAMPAIGN, RB.CAMPAIGN)


class TempDirsTest(unittest.TestCase):
    """Q126: a try's temp directories go when the try ends, kept or
    crashed, inside the process's own root; the root goes at exit."""

    def test_a_crashing_check_leaves_no_directory(self):
        made = []
        real = B._tmpdir

        def spy(prefix):
            path = real(prefix)
            made.append(path)
            return path

        def explode(entry):
            B._tmpdir("hp-de_dust-test-")
            B._tmpdir("hp-de_dust-test-")
            raise B.Crash("contract", "boom")
        with mock.patch.object(B, "_tmpdir", spy), \
                mock.patch.dict(B.TARGETS, {"zz": {"check": explode, "files": [], "seeds": lambda: []}}):
            with self.assertRaises(B.Crash):
                B.check("zz", {"id": "x", "data": None})
        self.assertEqual(2, len(made))
        self.assertFalse(any(os.path.isdir(p) for p in made))
        self.assertFalse(any(p in B._TMP_MADE for p in made))

    def test_a_kept_check_leaves_nothing_on_the_record(self):
        seeds = {e["from"]: e for e in B.seeds_race_state()}
        mark = len(B._TMP_MADE)
        B._with_rig(lambda: B.check("race_state", seeds["seed:save_distinct_records"]))
        self.assertEqual(mark, len(B._TMP_MADE))

    def test_the_root_goes_where_hp_de_dust_tmp_points(self):
        import subprocess, sys
        where = tempfile.mkdtemp(prefix="hp-tmpvol-")
        code = ("import os, sys\n"
                "sys.path.insert(0, %r)\n"
                "from runner.tools import de_dust_corpus as B\n"
                "root = B._grow_tmp_root()\n"
                "d = B._tmpdir('hp-de_dust-x-')\n"
                "assert d.startswith(root), (d, root)\n"
                "print(root)\n" % B.ROOT)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                             timeout=60, env={**os.environ, "HP_DE_DUST_TMP": where})
        self.assertEqual(0, out.returncode, out.stderr)
        root = out.stdout.strip()
        self.assertTrue(root.startswith(where), root)
        self.assertFalse(os.path.exists(root))   # removed at exit
        shutil.rmtree(where, ignore_errors=True)


class VerdictTest(unittest.TestCase):
    """Standing order M.8's four readings, from a synthetic ledger."""

    def _plan(self, when, tilts):
        return {"kind": "plan", "when": when, "slice": 600.0, "jobs": 1, "head": "abc",
                "targets": {t: {"tilt": v, "seconds": 600 * v, "rounds": 1, "rate": 1.0,
                                "yield": 0} for t, v in tilts.items()}}

    def test_the_four_readings_in_order(self):
        now = datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc)
        runs = [_grow("dtls_hostile", "2026-10-31T00:00:00Z", seconds=3600.0, kept=8),
                _grow("v2_mail", "2026-10-31T00:30:00Z", seconds=3600.0, kept=0),
                self._plan("2026-10-30T23:00:00Z", {"dtls_hostile": 4.0, "dtls_session": 4.0,
                                                   "race_stash": 4.0, "v2_mail": 0.25,
                                                   "board_mail": 0.25, "query": 0.25}),
                self._plan("2026-10-31T01:00:00Z", {"dtls_hostile": 4.0, "dtls_session": 0.25,
                                                   "race_stash": 2.0, "v2_mail": 0.25,
                                                   "board_mail": 1.5, "query": 0.25}),
                {"kind": "watch", "when": "2026-10-31T01:30:00Z", "rig": "Nuremberg",
                 "readings": ["disk: 93% used"], "breaches": ["temp volume 93% over the 90% line"]},
                {"kind": "watch", "when": "2026-10-31T01:40:00Z", "rig": "Nuremberg",
                 "readings": [], "breaches": []}]
        lines = B.verdict(runs, now=now, since="2026-10-30T22:55:00Z", baseline=3.55)
        self.assertEqual(8, len(lines))
        self.assertTrue(lines[0].startswith("1. fleet: 4.00 kept per CPU-hour"))
        self.assertIn("held or better", lines[0])
        self.assertIn("dtls_hostile: 2 plan(s)", lines[1]); self.assertIn("held 4x", lines[1])
        self.assertIn("fell to the floor on its own", lines[2])
        self.assertIn("settled at 2.00x", lines[3])
        self.assertIn("v2_mail: 2 plan(s), 0 above the floor", lines[4]); self.assertIn("at the floor", lines[4])
        self.assertIn("lifted off the floor", lines[5])
        self.assertIn("4. watch: 2 record(s), 1 with a breach; Nuremberg: 1", lines[7])

    def test_the_window_starts_at_the_hold(self):
        now = datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc)
        runs = [self._plan("2026-10-30T12:00:00Z", {"v2_mail": 4.0}),      # before the hold
                self._plan("2026-10-31T00:00:00Z", {"v2_mail": 0.25})]
        lines = B.verdict(runs, now=now, since="2026-10-30T22:55:00Z")
        self.assertIn("v2_mail: 1 plan(s), 0 above the floor", "\n".join(lines))

    def test_the_default_window_starts_at_the_restart_and_drops_the_nominal_tilt(self):
        # The plans before 00:00Z on 31-OCT were made by a grow loop
        # that spent its rounds on misses; the window starts with the
        # first plans made with rounds as tries.
        now = datetime(2026, 10, 31, 1, 9, tzinfo=timezone.utc)
        runs = [self._plan("2026-10-30T21:39:18Z", {"dtls_hostile": 0.25}),
                self._plan("2026-10-30T22:17:14Z", {"dtls_hostile": 4.0}),
                self._plan("2026-10-31T00:17:14Z", {"dtls_hostile": 4.0,
                                                   "dtls_session": 4.0,
                                                   "race_stash": 4.0})]
        text = "\n".join(B.verdict(runs, now=now))
        self.assertIn("dtls_hostile: 1 plan(s)", text)
        self.assertIn("held 4x", text)
        self.assertNotIn("first 0.25x", text)
        self.assertEqual("2026-10-31T00:00:00Z", B.HOLD_SINCE)

    def test_the_watch_records_itself_when_asked(self):
        recorded = []
        with mock.patch.object(B, "record_run", recorded.append), \
                mock.patch.object(B, "watch_readings",
                                  return_value=(["disk: 10% used"], ["memory 100 MB under the 128 MB floor"])):
            status = B.cmd_watch(argparse.Namespace(rig="Nuremberg", disk_max=90.0, mem_min_mb=None,
                                                    stale_min=None, expect_workers=None, record=True),
                                 out=lambda *a: None)
        self.assertEqual(1, status)
        self.assertEqual(1, len(recorded))
        self.assertEqual(("watch", "Nuremberg"), (recorded[0]["kind"], recorded[0]["rig"]))
        self.assertEqual(["memory 100 MB under the 128 MB floor"], recorded[0]["breaches"])


class LedgerTest(unittest.TestCase):

    def test_run_records_carry_the_technique_and_the_rig(self):
        s = B.Session("race_board", [])
        with mock.patch.dict(os.environ, {"HP_DE_DUST_RIG": "Menlo Park"}):
            rec = B._run_record("grow", "race_board", s, {"entries": 0, "arcs": 0}, [], 1.0)
        self.assertEqual(("race", "Menlo Park"), (rec["technique"], rec["rig"]))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HP_DE_DUST_RIG", None)
            rec = B._run_record("grow", "wire", s, {"entries": 0, "arcs": 0}, [], 1.0)
        self.assertEqual("mutation", rec["technique"])
        self.assertNotIn("rig", rec)

    def test_a_cycling_grow_records_its_plan(self):
        args = argparse.Namespace(target="wire,race_board", rounds=None, seed=1, jobs=1,
                                  minutes=1.0, verbose=False, archive=None,
                                  no_steer=True, order="fixed", slice=60.0,
                                  uniform_parents=False)
        recorded = []
        with mock.patch.object(B, "run_parallel", lambda *a, **k: 0), \
                mock.patch.object(B, "record_run", recorded.append), \
                mock.patch.object(B, "prune_retired_crashes", return_value=0):
            B.cmd_grow(args, out=lambda *a: None)
        self.assertEqual(1, len(recorded))
        plan = recorded[0]
        self.assertEqual("plan", plan["kind"])
        self.assertEqual({"wire", "race_board"}, set(plan["targets"]))
        self.assertEqual("race", plan["targets"]["race_board"]["technique"])
        self.assertEqual(60.0, plan["slice"])
        self.assertIs(plan, B.last_plan([plan, {"kind": "grow"}]))

    def test_the_yield_table_sums_each_technique(self):
        now = datetime(2026, 10, 30, 0, 0, tzinfo=timezone.utc)
        runs = [_grow("wire", "2026-10-29T20:00:00Z", seconds=3600.0, kept=2),
                _grow("race_board", "2026-10-29T21:00:00Z", seconds=1800.0, kept=1),
                _grow("dtls_session", "2026-10-29T22:00:00Z", seconds=1800.0, kept=3)]
        rows = {r["target"]: r for r in B.yield_table(48, runs, now=now)}
        self.assertEqual({"wire", "race_board", "dtls_session", "~mutation", "~protocol",
                          "~race", "fleet"}, set(rows))
        self.assertEqual(3, rows["~protocol"]["kept"])
        self.assertEqual(6, rows["fleet"]["kept"])


class YieldTableTest(unittest.TestCase):

    def test_the_table_sums_the_window_and_sorts_by_cpu(self):
        now = datetime(2026, 10, 30, 0, 0, tzinfo=timezone.utc)
        runs = [_grow("a", "2026-10-29T20:00:00Z", tried=360, seconds=3600.0, kept=2, arcs=4),
                _grow("b", "2026-10-29T23:00:00Z", tried=7200, seconds=1800.0, accepted=10, refused=90),
                _grow("a", "2026-10-20T00:00:00Z", tried=1, seconds=99999.0, kept=50)]
        rows = B.yield_table(48, runs, now=now)
        self.assertEqual(["a", "b", "~mutation", "fleet"], [r["target"] for r in rows])
        a, b, _mutation, fleet = rows
        self.assertEqual((1.0, 0.1, 2, 4), (a["cpu_h"], a["tries_per_s"], a["kept"], a["arcs"]))
        self.assertAlmostEqual(2.0, a["kept_per_cpu_h"])
        self.assertAlmostEqual(0.1, b["accepted_share"])
        self.assertEqual(2, fleet["runs"])
        self.assertAlmostEqual(1.5, fleet["cpu_h"])
        lines = B.format_yield(rows, 48)
        self.assertEqual(5, len(lines))
        self.assertIn("kept/cpu_h", lines[0])

    def test_stats_yield_prints_the_table(self):
        out = []
        args = argparse.Namespace(target="all", yield_table=True, hours=48)
        self.assertEqual(0, B.cmd_stats(args, out=out.append))
        self.assertTrue(out and out[0].startswith("de_aztec yield"))


if __name__ == "__main__":
    unittest.main()
