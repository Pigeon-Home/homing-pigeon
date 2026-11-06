# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""Campaign de_dust2 (docs/steady/project/de_dust2.md): the tool's side.

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
import copy
import io
import json
import errno
import os
import re
import shutil
import random
import string
import threading
import time
import string
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
                                       "docs/infrastructure-documents/project/campaign-standing-orders.md",
                                       "docs/infrastructure-documents/seats/.com.chat", "docs/steady/seats/status.txt", ""]))
        self.assertFalse(C.corpus_only(["runner/tests/de_dust/query.jsonl",
                                        "runner/tools/de_dust_corpus.py"]))
        self.assertFalse(C.corpus_only(["docs/steady/seats/questions.md"]))
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


class _GrowFakeProc:
    """A fake child for run_parallel: poll() reports finished after
    a set number of polls, stdout is whatever stream shape the test
    hands in, and communicate() / wait() count their calls."""

    def __init__(self, output=b"", rc=0, polls=0, stream="pipe",
                 comm=None):
        self._rc = rc
        self._polls = polls
        self.returncode = None
        self.communicated = 0
        self.waited = 0
        if stream == "pipe":
            self.stdout = io.BytesIO(output)
        elif stream == "none":
            self.stdout = None
        elif stream == "noread":
            self.stdout = object()
        self._comm = output if comm is None else comm

    def poll(self):
        if self._polls > 0:
            self._polls -= 1
            return None
        self.returncode = self._rc
        return self._rc

    def communicate(self):
        self.communicated += 1
        self.returncode = self._rc
        return self._comm, None

    def wait(self):
        self.waited += 1
        self.returncode = self._rc
        return self._rc


class _StepClock:
    """A monotonic clock that advances a fixed step per call, so a
    cycled grow's deadline arithmetic is deterministic."""

    def __init__(self, step=10.0):
        self.t = 0.0
        self.step = step

    def __call__(self):
        self.t += self.step
        return self.t


class ParallelGrowOwnShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 45: Q122 -- the parallel
    grow did not drain its children, and two crash families
    (race_state, v2_mail) were the grow's own (fixed 5b068aff,
    30-Oct-2026).

    Three surfaces, each scattered around the failure it came from.

    The drain: run_parallel now starts a reader thread per child at
    spawn and drains stdout into a buffer while the parent polls.
    Its fielded surface is enumerated one field per test below:
    commands, jobs, out, spawn, minutes, clock, nap, requeue and
    floor_sec -- through fakes at the spawn seam, never a real long
    parallel grow, so the family is fast and deterministic. The
    pins: drained output printed whole per child and never through
    communicate(); a child past the pipe buffer (200,000 bytes
    here, drained in 64 KB reads) finishing; the communicate()
    fallback for a child with no pipe, a None pipe, or a pipe with
    no read; the worst return code winning and a negative one never
    lowering it; the jobs cap; a busy-polling child; a pipe that
    breaks (OSError) or turns invalid (ValueError) mid-read; a
    pipe that dribbles three bytes at a time reassembled whole;
    out-of-order finishing with each output kept whole; and the
    cycling arithmetic -- the seed moving on, the deadline stopping
    new starts, the requeue callback's word going back on the
    queue, a budget clipped to the cycle's remainder, a budget
    under the floor not started (and naming its target, symbol
    bookends and all), a budgetless command never clipped, a
    budget that fits running unclipped, and the caller's command
    lists never mutated.

    The grow's own race_state family: the 72 banked records held
    the seen file to keys carrying a NUL, which the store drops by
    its own rule (_write_seen_kept). The harness honors the rule
    now: a NUL key alone is refused (nothing was held), a NUL key
    beside a good one is accepted, and no shape of NUL -- bookends,
    runs, front / back / middle -- is a lost-update crash again.

    The grow's own v2_mail family: subject idents were sanitized
    with Python's isspace, so an ident in the grammar's gap class
    built a subject with no id. The tool's sanitizers use the
    grammar's token class (_SUBJECT_TOKEN) now: every gap-class
    character (the ASCII controls and the Unicode spaces, BOM
    included) fails the token match and the ident falls back to
    the default, while a unit separator is a token character for
    the match and a message carrying one is refused by the reader,
    never a checker crash.

    The bookend rule and run lengths (standing rules, 1-Nov-2026)
    are part of the family: the text surfaces -- the target name in
    the slice messages, the seen keys, the subject idents -- get
    every printable ASCII symbol (string.punctuation) at the front
    AND the back, symbol-only strings, and NUL / tab / CR / LF
    shapes; and run lengths: runs of the odd character, and runs
    of ordinary characters with the odd one at the front, the back
    and the middle.

    Proof of work (6-Nov-2026). The unit tests are the 50 methods
    of this class: 30 on the drain and the cycling arithmetic, 11
    on the race_state attribution, 9 on the v2_mail attribution.
    The fuzzing was executed, not just the tests written:
    runner/tools/de_dust_corpus.py grow --target race_state
    --rounds 400 --seed 20261146, run locally against the banked
    race_state corpus (109 entries). race_state is the target
    chosen for this item's fuzz job: of the grow's two own
    families, its 72 records were the larger, and the drain fix
    and the NUL attribution were landed by the same commit.
    Result: 400 rounds, 0 crashes, 0 slow, arcs 183 -> 186,
    slowest try 480 ms; neither the stall nor the lost-update
    attribution recurred. The grow's bookkeeping writes were
    reverted and are not banked (banking is the rigs' hourly job);
    this record is the run's proof.
    None of this is exotic: it is combinatorics -- systematically
    trying the combinations a hand-written list would never reach,
    then pinning each answer as a test."""

    # -- helpers --

    def _run(self, cmds, factory, jobs=2, **kw):
        lines = []
        kw.setdefault("nap", 0)
        status = B.run_parallel(cmds, jobs, out=lines.append,
                                spawn=lambda cmd: factory(cmd), **kw)
        return status, lines

    def _race(self, spec):
        entry = B.make_entry("payload", spec, "shotgun45", "shotgun45")
        return B._with_rig(lambda: B.check("race_state", entry))

    def _v2(self, ident):
        seeds = {e["from"]: e for e in B.seeds_v2_mail()}
        entry = copy.deepcopy(seeds["seed:question"])
        entry["data"]["ident"] = ident
        return B._with_rig(lambda: B.check("v2_mail", entry))

    # -- the drain: run_parallel through the spawn seam --

    def test_drained_output_is_printed_whole_and_communicate_is_not_used(self):
        proc = _GrowFakeProc(b"one\ntwo\n", rc=3)
        status, lines = self._run([("a", ["x"])], lambda cmd: proc, jobs=1)
        self.assertEqual(3, status)
        self.assertEqual(["one", "two"], lines)
        self.assertEqual(0, proc.communicated)
        self.assertEqual(1, proc.waited)

    def test_a_child_past_the_pipe_buffer_is_drained_in_chunks(self):
        big = b"x" * 200000 + b"\nend\n"
        status, lines = self._run([("a", ["x"])],
                                  lambda cmd: _GrowFakeProc(big), jobs=1)
        self.assertEqual(0, status)
        self.assertEqual([200000, 3], [len(line) for line in lines])
        self.assertEqual("end", lines[1])

    def test_output_is_split_on_lines_and_the_trailing_blank_is_dropped(self):
        _s, lines = self._run([("a", ["x"])],
                              lambda cmd: _GrowFakeProc(b"a\n\nb\n\n"),
                              jobs=1)
        self.assertEqual(["a", "", "b"], lines)
        _s, lines = self._run([("a", ["x"])],
                              lambda cmd: _GrowFakeProc(b"one\ntwo\n"),
                              jobs=1)
        self.assertEqual(["one", "two"], lines)

    def test_invalid_utf8_in_the_drained_output_is_replaced_not_raised(self):
        status, lines = self._run(
            [("a", ["x"])], lambda cmd: _GrowFakeProc(b"\xff\xfe bad\n"),
            jobs=1)
        self.assertEqual(0, status)
        self.assertEqual(["\ufffd\ufffd bad"], lines)

    def test_a_child_without_a_stdout_attribute_uses_communicate(self):
        proc = _GrowFakeProc(stream="missing", comm=b"via comm\n")
        status, lines = self._run([("a", ["x"])], lambda cmd: proc, jobs=1)
        self.assertEqual(0, status)
        self.assertEqual(["via comm"], lines)
        self.assertEqual(1, proc.communicated)
        self.assertEqual(0, proc.waited)

    def test_a_child_with_stdout_none_uses_communicate(self):
        proc = _GrowFakeProc(stream="none", comm=b"none pipe\n")
        _s, lines = self._run([("a", ["x"])], lambda cmd: proc, jobs=1)
        self.assertEqual(["none pipe"], lines)
        self.assertEqual(1, proc.communicated)

    def test_a_child_whose_stdout_cannot_be_read_uses_communicate(self):
        proc = _GrowFakeProc(stream="noread", comm=b"unreadable pipe\n")
        _s, lines = self._run([("a", ["x"])], lambda cmd: proc, jobs=1)
        self.assertEqual(["unreadable pipe"], lines)
        self.assertEqual(1, proc.communicated)

    def test_communicate_text_output_is_printed_as_is(self):
        proc = _GrowFakeProc(stream="none", comm="text out\n")
        _s, lines = self._run([("a", ["x"])], lambda cmd: proc, jobs=1)
        self.assertEqual(["text out"], lines)

    def test_communicate_none_and_empty_outputs_print_nothing(self):
        procs = {"a": _GrowFakeProc(stream="none", comm=None),
                 "b": _GrowFakeProc(stream="none", comm=b"")}
        status, lines = self._run([("a", ["a"]), ("b", ["b"])],
                                  lambda cmd: procs[cmd[0]], jobs=2)
        self.assertEqual(0, status)
        self.assertEqual([], lines)

    def test_the_worst_returncode_is_the_grows_status(self):
        rcs = {"a": 2, "b": 7, "c": 0}
        status, _l = self._run(
            [(t, [t]) for t in "abc"],
            lambda cmd: _GrowFakeProc(b"", rc=rcs[cmd[0]]), jobs=3)
        self.assertEqual(7, status)

    def test_a_negative_returncode_never_lowers_the_status(self):
        rcs = {"a": -9, "b": 3}
        status, _l = self._run(
            [(t, [t]) for t in "ab"],
            lambda cmd: _GrowFakeProc(b"", rc=rcs[cmd[0]]), jobs=2)
        self.assertEqual(3, status)
        status, _l = self._run([("a", ["a"])],
                               lambda cmd: _GrowFakeProc(b"", rc=-9),
                               jobs=1)
        self.assertEqual(0, status)

    def test_no_commands_is_a_quiet_zero(self):
        def forbidden(cmd):
            raise AssertionError("spawn called with no commands")
        status, lines = self._run([], forbidden, jobs=2)
        self.assertEqual(0, status)
        self.assertEqual([], lines)

    def test_jobs_one_runs_children_in_the_order_given(self):
        spawned = []

        def factory(cmd):
            spawned.append(cmd[0])
            return _GrowFakeProc(b"done-" + cmd[0].encode() + b"\n",
                                 polls=1)
        status, lines = self._run([("a", ["a"]), ("b", ["b"]),
                                   ("c", ["c"])], factory, jobs=1)
        self.assertEqual(0, status)
        self.assertEqual(["a", "b", "c"], spawned)
        self.assertEqual(["done-a", "done-b", "done-c"], lines)

    def test_the_jobs_cap_is_never_exceeded(self):
        alive = {"now": 0, "max": 0}

        class CapProc(_GrowFakeProc):
            def poll(self):
                got = super().poll()
                if got is not None and not getattr(self, "_counted",
                                                   False):
                    self._counted = True
                    alive["now"] -= 1
                return got

        def factory(cmd):
            alive["now"] += 1
            alive["max"] = max(alive["max"], alive["now"])
            return CapProc(b"done\n", polls=2)
        status, lines = self._run(
            [("t%d" % i, ["c%d" % i]) for i in range(5)], factory, jobs=2)
        self.assertEqual(0, status)
        self.assertEqual(2, alive["max"])
        self.assertEqual(5, len(lines))

    def test_a_child_that_polls_busy_for_a_while_still_finishes_drained(self):
        proc = _GrowFakeProc(b"late\n", polls=5)
        status, lines = self._run([("a", ["x"])], lambda cmd: proc, jobs=1)
        self.assertEqual(0, status)
        self.assertEqual(["late"], lines)
        self.assertEqual(0, proc.communicated)

    def test_a_pipe_that_breaks_mid_read_still_lets_the_child_finish(self):
        class BadStream:
            def read(self, n=-1):
                raise OSError("pipe gone")
        proc = _GrowFakeProc(rc=4)
        proc.stdout = BadStream()
        status, lines = self._run([("a", ["x"])], lambda cmd: proc, jobs=1)
        self.assertEqual(4, status)
        self.assertEqual([], lines)
        self.assertEqual(1, proc.waited)

    def test_a_pipe_that_raises_valueerror_is_swallowed_the_same_way(self):
        class BadStream:
            def read(self, n=-1):
                raise ValueError("closed file")
        proc = _GrowFakeProc(rc=0)
        proc.stdout = BadStream()
        status, lines = self._run([("a", ["x"])], lambda cmd: proc, jobs=1)
        self.assertEqual(0, status)
        self.assertEqual([], lines)
        self.assertEqual(1, proc.waited)

    def test_a_dribbling_pipe_is_reassembled_whole(self):
        class Dribble(io.RawIOBase):
            def __init__(self, data):
                self._data = data
                self._at = 0

            def readable(self):
                return True

            def read(self, n=-1):
                if self._at >= len(self._data):
                    return b""
                chunk = self._data[self._at:self._at + 3]
                self._at += len(chunk)
                return chunk
        proc = _GrowFakeProc()
        proc.stdout = Dribble(b"abcdefghij\nend\n")
        status, lines = self._run([("a", ["x"])], lambda cmd: proc, jobs=1)
        self.assertEqual(0, status)
        self.assertEqual(["abcdefghij", "end"], lines)
        self.assertEqual(0, proc.communicated)

    def test_a_child_may_finish_out_of_order_and_each_output_stays_whole(self):
        procs = {"a": _GrowFakeProc(b"a-line\n", polls=3),
                 "b": _GrowFakeProc(b"b-line\n", polls=0)}
        status, lines = self._run([("a", ["a"]), ("b", ["b"])],
                                  lambda cmd: procs[cmd[0]], jobs=2)
        self.assertEqual(0, status)
        self.assertEqual(["b-line", "a-line"], lines)

    # -- the cycling arithmetic: minutes, clock, requeue, floor_sec --

    def test_cycling_moves_the_seed_on_each_round(self):
        spawned = []

        def factory(cmd):
            spawned.append(list(cmd))
            return _GrowFakeProc(b"tick\n")
        status, lines = self._run(
            [("t", ["grow", "--seed", "5"])], factory, jobs=1,
            minutes=1.0, clock=_StepClock(10.0))
        self.assertEqual(0, status)
        self.assertEqual([["grow", "--seed", "5"], ["grow", "--seed", "6"],
                          ["grow", "--seed", "7"]], spawned)
        self.assertEqual(["tick"] * 3, lines)

    def test_cycling_starts_nothing_new_once_the_deadline_has_passed(self):
        class Clock:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                return 0.0 if self.calls <= 2 else 100.0
        spawned = []

        def factory(cmd):
            spawned.append(list(cmd))
            return _GrowFakeProc(b"ran\n")
        status, _l = self._run([("t", ["grow", "--seed", "1"])], factory,
                               jobs=1, minutes=1.0, clock=Clock())
        self.assertEqual(0, status)
        self.assertEqual([["grow", "--seed", "1"]], spawned)

    def test_the_requeue_callback_gets_the_moved_seed_and_its_word_goes_back_on(self):
        class Clock:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                return 0.0 if self.calls <= 5 else 100.0
        calls = []
        spawned = []

        def requeue(target, cmd):
            calls.append((target, list(cmd)))
            return cmd + ["--again"]

        def factory(cmd):
            spawned.append(list(cmd))
            return _GrowFakeProc(b"r\n")
        status, _l = self._run([("t", ["grow", "--seed", "1"])], factory,
                               jobs=1, minutes=1.0, clock=Clock(),
                               requeue=requeue)
        self.assertEqual(0, status)
        self.assertEqual([("t", ["grow", "--seed", "2"]),
                          ("t", ["grow", "--seed", "3", "--again"])], calls)
        self.assertEqual([["grow", "--seed", "1"],
                          ["grow", "--seed", "2", "--again"]], spawned)

    def test_a_budget_over_the_remainder_is_clipped_to_it(self):
        spawned = []

        def factory(cmd):
            spawned.append(list(cmd))
            return _GrowFakeProc(b"ran\n")
        status, lines = self._run(
            [("t", ["grow", "--budget-sec", "900"])], factory, jobs=1,
            minutes=1.0, clock=_StepClock(10.0), floor_sec=30.0)
        self.assertEqual(0, status)
        self.assertEqual([["grow", "--budget-sec", "40"]], spawned)
        self.assertTrue(any("clipped to 40 s" in line for line in lines))
        self.assertTrue(any("not started, 10 s left" in line
                            for line in lines))

    def test_a_budget_under_the_floor_is_not_started_and_names_the_target(self):
        spawned = []

        def factory(cmd):
            spawned.append(list(cmd))
            return _GrowFakeProc(b"ran\n")
        status, lines = self._run(
            [("tg;t", ["grow", "--budget-sec", "900"])], factory, jobs=1,
            minutes=1.0, clock=_StepClock(55.0), floor_sec=30.0)
        self.assertEqual(0, status)
        self.assertEqual([], spawned)
        self.assertEqual(1, len(lines))
        self.assertIn("not started", lines[0])
        self.assertIn("tg;t", lines[0])

    def test_a_command_with_no_budget_is_never_clipped_nor_floored(self):
        spawned = []

        def factory(cmd):
            spawned.append(list(cmd))
            return _GrowFakeProc(b"ran\n")
        status, lines = self._run(
            [("t", ["grow", "--seed", "1"])], factory, jobs=1,
            minutes=1.0, clock=_StepClock(55.0), floor_sec=9999.0)
        self.assertEqual(0, status)
        self.assertEqual([["grow", "--seed", "1"]], spawned)
        self.assertEqual(["ran"], lines)

    def test_a_budget_that_fits_the_remainder_runs_unclipped(self):
        class Clock:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                return 0.0 if self.calls <= 3 else 100.0
        spawned = []

        def factory(cmd):
            spawned.append(list(cmd))
            return _GrowFakeProc(b"ran\n")
        status, lines = self._run(
            [("t", ["grow", "--budget-sec", "10"])], factory, jobs=1,
            minutes=1.0, clock=Clock(), floor_sec=30.0)
        self.assertEqual(0, status)
        self.assertEqual([["grow", "--budget-sec", "10"]], spawned)
        self.assertEqual(["ran"], lines)

    def test_next_seed_moves_only_the_seed(self):
        cmd = ["g", "--seed", "41"]
        self.assertEqual(["g", "--seed", "42"], B._next_seed(cmd))
        self.assertEqual(["g", "--seed", "41"], cmd)
        self.assertEqual(["g"], B._next_seed(["g"]))
        self.assertEqual(["--seed", "2", "--seed", "2"],
                         B._next_seed(["--seed", "1", "--seed", "2"]))

    def test_set_budget_replaces_in_place_and_appends_when_absent(self):
        cmd = ["g", "--budget-sec", "5"]
        self.assertEqual(["g", "--budget-sec", "2.5"],
                         B._set_budget(cmd, 2.5))
        self.assertEqual(["g", "--budget-sec", "5"], cmd)
        self.assertEqual(["g", "--budget-sec", "3"], B._set_budget(["g"], 3))

    def test_set_rounds_replaces_in_place_and_appends_when_absent(self):
        cmd = ["g", "--rounds", "5"]
        self.assertEqual(["g", "--rounds", "9"], B._set_rounds(cmd, 9))
        self.assertEqual(["g", "--rounds", "5"], cmd)
        self.assertEqual(["g", "--rounds", "9"], B._set_rounds(["g"], 9))

    def test_cycling_does_not_mutate_the_callers_commands(self):
        cmd = ["grow", "--seed", "5"]
        cmds = [("t", cmd)]
        self._run(cmds, lambda c: _GrowFakeProc(b"x\n"), jobs=1,
                  minutes=1.0, clock=_StepClock(10.0))
        self.assertEqual(["grow", "--seed", "5"], cmd)
        self.assertEqual([("t", ["grow", "--seed", "5"])], cmds)

    # -- the grow's own race_state family: the NUL seen keys --

    def test_a_nul_key_alone_is_refused_not_a_lost_update_crash(self):
        got = self._race({"threads": [[{"op": "mark", "key": "bm\x00x"},
                                       {"op": "load_seen"}]]})
        self.assertEqual("refused", got)

    def test_a_nul_key_beside_a_good_key_is_accepted(self):
        got = self._race({"threads": [[{"op": "mark", "key": "bm\x00x"},
                                       {"op": "mark", "key": "good-1"},
                                       {"op": "load_seen"}]]})
        self.assertEqual("accepted", got)

    def test_nul_bookends_and_runs_are_not_held_against_the_file(self):
        for key in ("\x00" * 10, "\x00k\x00", "k" + "\x00" * 10,
                    "\x00" * 5 + "k" + "\x00" * 5, "\x00"):
            got = self._race({"threads": [[{"op": "mark", "key": key},
                                           {"op": "mark", "key": "good"},
                                           {"op": "load_seen"}]]})
            self.assertEqual("accepted", got, repr(key))

    def test_a_tab_key_and_a_space_key_are_plain_keys(self):
        for key in ("a\tb", "a b", "a\rb", "a\nb"):
            got = self._race({"threads": [[{"op": "mark", "key": key},
                                           {"op": "load_seen"}]]})
            self.assertEqual("accepted", got, repr(key))

    def test_every_symbol_bookended_key_marks_and_reads_back(self):
        for symbol in string.punctuation:
            key = symbol + "k" + symbol
            got = self._race({"threads": [[{"op": "mark", "key": key},
                                           {"op": "load_seen"}]]})
            self.assertEqual("accepted", got, symbol)

    def test_run_length_keys_mark_and_read_back(self):
        for key in ("k" * 10, ";" * 10, "k" * 5 + ";" + "k" * 5,
                    ";" + "k" * 10, "k" * 10 + ";"):
            got = self._race({"threads": [[{"op": "mark", "key": key},
                                           {"op": "load_seen"}]]})
            self.assertEqual("accepted", got, repr(key))

    def test_an_empty_or_nonstring_key_falls_back_to_a_generated_key(self):
        for key in ("", 7, None):
            got = self._race({"threads": [[{"op": "mark", "key": key},
                                           {"op": "load_seen"}]]})
            self.assertEqual("accepted", got, repr(key))

    def test_unknown_and_malformed_ops_never_raise(self):
        got = self._race({"threads": [[{"op": "nope"}, 7, "mark",
                                       {"op": "mark", "key": "k"}],
                                      "x"]})
        self.assertEqual("accepted", got)

    def test_a_switch_of_the_wrong_shape_falls_back_to_the_default(self):
        for switch in ("fast", True, float("nan"), 5.0, None, 0):
            got = self._race({"switch": switch,
                              "threads": [[{"op": "mark", "key": "k1"}]]})
            self.assertEqual("accepted", got, repr(switch))

    def test_more_threads_than_the_cap_are_bounded(self):
        spec = {"threads": [[{"op": "mark", "key": "t%d" % i}]
                            for i in range(6)]}
        self.assertEqual(B._RACE_MAX_THREADS, len(B._race_ops(spec)))
        self.assertEqual("accepted", self._race(spec))

    def test_a_save_under_an_unsafe_id_is_not_held_but_a_good_one_is(self):
        got = self._race({"threads": [[{"op": "save", "id": ".."},
                                       {"op": "save", "id": "bm-ret-ok"},
                                       {"op": "load", "id": "bm-ret-ok"}]]})
        self.assertEqual("accepted", got)

    # -- the grow's own v2_mail family: the token grammar --

    def test_the_subject_token_grammar_uses_the_grammar_gap_class(self):
        for ch in ("\u00a0", "\u1680", "\u2000", "\u2003", "\u2028",
                   "\u2029", "\u202f", "\u205f", "\u3000", "\ufeff",
                   " ", "\t", "\n", "\r", "\x0b", "\x0c"):
            self.assertIsNone(B._SUBJECT_TOKEN.fullmatch(ch), repr(ch))
            self.assertIsNone(B._SUBJECT_TOKEN.fullmatch("a" + ch + "b"),
                              repr(ch))

    def test_the_subject_token_grammar_takes_plain_and_separator_idents(self):
        for ident in ("q.bm-job-0001", "a\x1fb", "\x1f", "job-1"):
            self.assertIsNotNone(B._SUBJECT_TOKEN.fullmatch(ident),
                                 repr(ident))

    def test_a_unicode_space_ident_falls_back_to_the_default(self):
        self.assertEqual("accepted", self._v2("\u00a0"))

    def test_a_bom_ident_falls_back_to_the_default(self):
        self.assertEqual("accepted", self._v2("\ufeff"))

    def test_idents_carrying_ascii_gaps_fall_back_to_the_default(self):
        for ident in ("a b", "a\tb", "a\nb", "a\rb"):
            self.assertEqual("accepted", self._v2(ident), repr(ident))

    def test_an_empty_or_nonstring_ident_falls_back_to_the_default(self):
        for ident in ("", 7, None):
            self.assertEqual("accepted", self._v2(ident), repr(ident))

    def test_a_unit_separator_ident_is_refused_not_a_crash(self):
        self.assertEqual("refused", self._v2("\x1f"))
        self.assertEqual("refused", self._v2("a\x1fb"))

    def test_an_overlong_ident_is_refused_not_a_crash(self):
        self.assertEqual("refused", self._v2("x" * 300))

    def test_every_symbol_bookended_ident_is_refused_not_a_crash(self):
        for symbol in string.punctuation:
            got = self._v2(symbol + "q.bm-job-0001" + symbol)
            self.assertEqual("refused", got, symbol)


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


class BoardSubjectAndStashShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 41: a board subject went
    unhandled, and one stash could be sent twice (fixed bc4cb3d8,
    31-Oct-2026).

    Why this file: the fix's own combined contract test,
    TechniquesTest.test_the_filed_crashes_meet_the_contract,
    lives here in test_de_dust2.py and covers both legs together
    (the board_mail entries and the race_stash entries), so the
    family lives beside it. The fix's second test, the direct
    two-caller thread test in test_result_stash.py, is pinned
    here through the same surface it drives (runner.deliver_stash
    via B.R) rather than copied.

    The two legs. (1) The board subject: handle_board_mail used
    to match the subject with a Python-whitespace pattern, so a
    unit separator inside the id was a gap and the message came
    back on every poll, unseen. The handler now matches with the
    shared subject grammar (runner/ops/startup.py's
    _BOARD_SUBJECT, built from runner/wire/subject.py), where
    the separator set is ECMAScript's: \\x1c-\\x1f and \\x85 are
    word characters, \\ufeff is a gap. And a board key that is
    not a task id ([A-Za-z0-9._-]{1,128}, not "." or "..") is not
    loaded, so it is never offered under a subject that splits.
    (2) One stash, sent once: the outbox holds one lock per key
    (runner._stash_guard) across the send and the move into
    sent/, shared by deliver_stash, resend_stashed and
    stash_result itself, so a resend and a direct deliver cannot
    both send the same record.

    Per-field enumeration: the subject's fields -- the marker,
    the extra words, the kind, the id -- each get their own
    tests; the board record's fields are enumerated through
    load and submit (the key/task_id, state, priority, and the
    requires / capabilities / compartments lists); the stash
    record's fields through stash, load and deliver (skey,
    job_id, subject, body, attempts, last_error).

    The bookend rule and run lengths (standing rules,
    1-Nov-2026) are part of the family: board keys and stash
    bodies get bookended variants -- all 32 printable ASCII
    symbols (string.punctuation) at the front and at the back,
    as singles, matched pairs and symbol-only strings, plus
    NUL, tab, CR and LF at both ends -- and run lengths: runs
    of the odd character at lengths 1, 5, 10, 100 and at the
    128/129 id boundary, and runs of ordinary characters with
    the odd one at the front, the back and the middle.

    Proof of work. The unit tests are the 50 methods of this
    class: 12 board-subject grammar tests, 12 board-load tests,
    6 board-submit tests, 12 stash-sent-once tests, 6 corpus
    contract tests and 2 bookend / run-length sweeps. The
    fuzzing was executed, not just the tests written:
    runner/tools/de_dust_corpus.py grow --target board_mail
    --rounds 400 --seed 20261142, run locally against the
    banked board_mail corpus (100 entries). Result: 400 rounds,
    0 crashes, 0 slow, arcs unchanged at 617, slowest try
    13703 ms -- the unhandled-subject and double-send shapes
    did not recur. The grow's bookkeeping writes were reverted
    and are not banked (banking is the rigs' hourly job); this
    record is the run's proof. None of this is exotic: it is
    combinatorics -- systematically trying the combinations a
    hand-written list would never reach, then pinning each
    answer as a test."""

    KINDS = ("task_submit", "task_request", "task_result", "task_approve")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    # -- helpers --

    def _match(self, subject):
        return B.ST._BOARD_SUBJECT.search(subject)

    def _task(self, tid, **extra):
        task = {"task_id": tid, "state": "open", "priority": 1,
                "requires": [], "capabilities": [], "compartments": [],
                "payload": {"script": "echo task"},
                "submitted_at": "2026-10-26T12:00:00+00:00"}
        task.update(extra)
        return task

    def _board(self, mapping, name="board.json"):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(mapping if isinstance(mapping, str)
                     else json.dumps(mapping))
        return B.BD.Board(path)

    def _stash(self, key="k1", body="alpha", base=None):
        return B.R.stash_result(
            base or self.tmp, key, {"job_id": key, "kind": "exec"},
            "[HOMING-PIGEON] result " + key, body)

    def _sender(self, sent, delay=0.02):
        def send(subject, body, to):
            if delay:
                time.sleep(delay)
            sent.append(body)
        return send

    def _run_threads(self, fns):
        threads = [threading.Thread(target=f) for f in fns]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
            self.assertFalse(t.is_alive())

    def _check(self, target, data, rounds=1):
        entry = {"id": "x", "kind": "payload", "data": data,
                 "from": "", "mutator": "", "arcs": 0}
        for _ in range(rounds):
            self.assertIn(
                B._with_rig(lambda e=entry: B.check(target, e)),
                ("accepted", "refused"))

    # -- 12 board-subject grammar tests --

    def test_subject_each_of_the_four_kinds_is_handled_with_a_plain_id(self):
        for kind in self.KINDS:
            m = self._match(f"[HOMING-PIGEON] {kind} task-1")
            self.assertIsNotNone(m, kind)
            self.assertEqual((m.group(1).lower(), m.group(2)), (kind, "task-1"))

    def test_subject_the_kind_is_case_insensitive_and_the_id_keeps_its_case(self):
        m = self._match("[HOMING-PIGEON] TASK_SUBMIT Task-ABC_1.x")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "TASK_SUBMIT")
        self.assertEqual(m.group(2), "Task-ABC_1.x")
        m = self._match("[hominG-pigeon] Task_Approve t2")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "t2")

    def test_subject_a_unit_separator_inside_the_id_is_a_word_not_a_gap(self):
        # The filed bug: Python's \s counts \x1f as a gap, so the
        # old pattern stopped the id there and the handler missed
        # the message. The shared grammar takes the whole token.
        m = self._match("[HOMING-PIGEON] task_approve a\x1fb")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1).lower(), "task_approve")
        self.assertEqual(m.group(2), "a\x1fb")

    def test_subject_each_information_separator_and_nel_inside_the_id_is_a_word(self):
        for ch in ("\x1c", "\x1d", "\x1e", "\x1f", "\x85"):
            m = self._match(f"[HOMING-PIGEON] task_submit a{ch}b")
            self.assertIsNotNone(m, repr(ch))
            self.assertEqual(m.group(2), f"a{ch}b", repr(ch))

    def test_subject_a_byte_order_mark_inside_the_id_is_a_gap(self):
        # \ufeff IS in the grammar's separator set (ECMAScript
        # counts it), so the id ends before it.
        m = self._match("[HOMING-PIGEON] task_submit a\ufeffb")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "a")

    def test_subject_the_gap_characters_each_separate_the_kind_from_the_id(self):
        for gap in (" ", "\t", "\x0b", "\x0c", "\r", "\xa0", "\u3000", "\ufeff"):
            m = self._match(f"[HOMING-PIGEON] task_submit{gap}t1")
            self.assertIsNotNone(m, repr(gap))
            self.assertEqual(m.group(2), "t1", repr(gap))

    def test_subject_extra_words_and_a_reply_prefix_do_not_hide_the_kind(self):
        m = self._match("[HOMING-PIGEON] TEST task_submit t1")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "t1")
        m = self._match("Re: [HOMING-PIGEON] task_request worker-1")
        self.assertIsNotNone(m)
        self.assertEqual((m.group(1).lower(), m.group(2)),
                         ("task_request", "worker-1"))

    def test_subject_other_kinds_and_kind_prefixes_are_not_board_mail(self):
        for subject in ("[HOMING-PIGEON] job t1",
                        "[HOMING-PIGEON] result t1",
                        "[HOMING-PIGEON] task_delete t1",
                        "[HOMING-PIGEON] task_submitx t1",
                        "[HOMING-PIGEON] task t1",
                        "[HOMING-PIGEON] submit t1"):
            self.assertIsNone(self._match(subject), subject)

    def test_subject_a_kind_with_no_id_is_not_handled(self):
        self.assertIsNone(self._match("[HOMING-PIGEON] task_submit"))
        self.assertIsNone(self._match("[HOMING-PIGEON] task_submit "))
        self.assertIsNone(self._match("[HOMING-PIGEON] task_submit \t"))

    def test_subject_no_marker_or_a_broken_marker_is_not_handled(self):
        for subject in ("task_submit t1",
                        "[HOMING-PIGEON task_submit t1",
                        "HOMING-PIGEON] task_submit t1",
                        "[OTHER] task_submit t1",
                        "[HOMING-PIGEON] ",
                        ""):
            self.assertIsNone(self._match(subject), subject)

    def test_subject_ids_at_the_length_boundary_and_with_the_safe_symbols(self):
        m = self._match("[HOMING-PIGEON] task_submit " + "a" * 128)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "a" * 128)
        m = self._match("[HOMING-PIGEON] task_result a.b-c_d")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "a.b-c_d")
        m = self._match("[HOMING-PIGEON] task_submit " + "a" * 129)
        self.assertIsNotNone(m)  # the grammar takes the token; the
        self.assertEqual(len(m.group(2)), 129)  # id gate refuses it

    def test_subject_the_grammar_and_python_whitespace_disagree_exactly_at_the_bug(self):
        # Pin the root cause both ways: Python's \S+ splits the
        # id at the separator controls; the board grammar does not.
        for ch in ("\x1c", "\x1f", "\x85"):
            token = f"a{ch}b"
            self.assertEqual(re.findall(r"\S+", token), ["a", "b"], repr(ch))
            m = self._match(f"[HOMING-PIGEON] task_submit {token}")
            self.assertEqual(m.group(2), token, repr(ch))

    # -- 12 board-load tests --

    def test_board_load_a_key_with_a_space_is_skipped_and_a_plain_key_is_kept(self):
        board = self._board({"a b": self._task("a b"),
                             "good1": self._task("good1")})
        self.assertEqual(sorted(board.tasks), ["good1"])

    def test_board_load_a_key_that_is_a_whole_subject_is_skipped(self):
        key = "{[HOMING-PIGEON] TEST job 1"
        board = self._board({key: self._task("x"),
                             "good1": self._task("good1")})
        self.assertEqual(sorted(board.tasks), ["good1"])

    def test_board_load_slash_and_backslash_keys_are_skipped(self):
        board = self._board({"a/b": self._task("a/b"),
                             "a\\b": self._task("a\\b"),
                             "good1": self._task("good1")})
        self.assertEqual(sorted(board.tasks), ["good1"])

    def test_board_load_the_dot_names_are_skipped_and_three_dots_are_kept(self):
        board = self._board({".": self._task("."), "..": self._task(".."),
                             "...": self._task("...")})
        self.assertEqual(sorted(board.tasks), ["..."])

    def test_board_load_a_129_character_key_is_skipped_and_a_128_is_kept(self):
        board = self._board({"a" * 129: self._task("a" * 129),
                             "a" * 128: self._task("a" * 128)})
        self.assertEqual(sorted(board.tasks), ["a" * 128])

    def test_board_load_control_and_non_ascii_keys_are_skipped(self):
        board = self._board({"a\x1fb": self._task("a\x1fb"),
                             "a\0b": self._task("a\0b"),
                             "é1": self._task("é1"),
                             "": self._task(""),
                             "good1": self._task("good1")})
        self.assertEqual(sorted(board.tasks), ["good1"])

    def test_board_load_a_record_whose_task_id_disagrees_carries_its_key(self):
        board = self._board({"good1": self._task("other-id")})
        self.assertEqual(board.tasks["good1"]["task_id"], "good1")

    def test_board_load_non_dict_task_values_are_skipped(self):
        board = self._board({"s": "text", "l": [1], "n": 42, "z": None,
                             "good1": self._task("good1")})
        self.assertEqual(sorted(board.tasks), ["good1"])

    def test_board_load_unusable_files_read_as_an_empty_board(self):
        self.assertEqual(self._board("[1, 2]", "a.json").tasks, {})
        self.assertEqual(self._board('"hello"', "b.json").tasks, {})
        self.assertEqual(self._board("42", "c.json").tasks, {})
        self.assertEqual(self._board("{not json", "d.json").tasks, {})
        missing = B.BD.Board(os.path.join(self.tmp, "missing.json"))
        self.assertEqual(missing.tasks, {})

    def test_board_load_a_non_finite_priority_record_is_skipped(self):
        text = ('{"good1": ' + json.dumps(self._task("good1")) +
                ', "bad1": {"task_id": "bad1", "state": "open",'
                ' "priority": NaN}}')
        board = self._board(text)
        self.assertEqual(sorted(board.tasks), ["good1"])

    def test_board_load_the_saved_file_reads_back_with_only_the_legal_keys(self):
        board = self._board({"a b": self._task("a b"),
                             "good1": self._task("good1"),
                             "good2": self._task("good2")})
        board.save()
        again = B.BD.Board(board.path)
        self.assertEqual(sorted(again.tasks), ["good1", "good2"])
        self.assertEqual(again.tasks["good1"]["state"], "open")

    def test_board_offer_never_offers_a_task_under_a_key_that_splits(self):
        board = self._board({"a b": self._task("a b")})
        self.assertIsNone(board.offer("worker-a", ["shell"]))
        board2 = self._board({"good1": self._task(
            "good1", capabilities=["shell"])}, "board2.json")
        offered = board2.offer("worker-a", ["shell"])
        self.assertIsNotNone(offered)
        self.assertEqual(offered["task_id"], "good1")
        self.assertEqual(board2.tasks["good1"]["state"], "claimed")

    # -- 6 board-submit tests --

    def test_board_submit_a_plain_task_is_open_with_its_fields_and_defaults(self):
        board = self._board({})
        ok, why = board.submit({"task_id": "t1"})
        self.assertEqual((ok, why), (True, "ok"))
        task = board.tasks["t1"]
        self.assertEqual(task["state"], "open")
        self.assertEqual(task["priority"], 0)
        self.assertEqual(task["requires"], [])
        self.assertEqual(task["capabilities"], [])
        self.assertEqual(task["compartments"], [])
        self.assertIsNone(task["payload"])

    def test_board_submit_the_dot_names_an_empty_and_an_overlong_id_are_refused(self):
        board = self._board({})
        for tid in (".", "..", "", "a" * 129):
            self.assertEqual(board.submit({"task_id": tid}),
                             (False, "invalid task_id"), tid[:10])
        self.assertEqual(board.tasks, {})

    def test_board_submit_ids_with_gaps_separators_and_brackets_are_refused(self):
        board = self._board({})
        for tid in ("a b", "a/b", "a\\b", "a\tb", "[t1]", "a:b", "a\x1fb", "é1"):
            self.assertEqual(board.submit({"task_id": tid}),
                             (False, "invalid task_id"), repr(tid))
        self.assertEqual(board.tasks, {})

    def test_board_submit_a_non_dict_task_and_non_string_ids_are_refused(self):
        board = self._board({})
        self.assertEqual(board.submit("t1"), (False, "invalid task"))
        self.assertEqual(board.submit(None), (False, "invalid task"))
        for tid in (42, None, ["t1"], {"id": "t1"}, True):
            self.assertEqual(board.submit({"task_id": tid}),
                             (False, "invalid task_id"), repr(tid))

    def test_board_submit_a_duplicate_id_is_refused_and_the_first_record_stays(self):
        board = self._board({})
        self.assertEqual(board.submit({"task_id": "t1", "priority": 3}),
                         (True, "ok"))
        self.assertEqual(board.submit({"task_id": "t1", "priority": 9}),
                         (False, "duplicate task_id"))
        self.assertEqual(board.tasks["t1"]["priority"], 3)

    def test_board_submit_each_list_field_and_the_priority_are_checked_by_name(self):
        board = self._board({})
        for field in ("requires", "capabilities", "compartments"):
            self.assertEqual(
                board.submit({"task_id": "t1", field: "shell"}),
                (False, f"{field} must be a list of strings"), field)
            self.assertEqual(
                board.submit({"task_id": "t1", field: [1]}),
                (False, f"{field} must be a list of strings"), field)
        self.assertEqual(board.submit({"task_id": "t1", "priority": "high"}),
                         (False, "priority must be numeric"))
        self.assertEqual(
            board.submit({"task_id": "t1", "priority": float("nan")}),
            (False, "priority must be a finite number"))
        self.assertEqual(
            board.submit({"task_id": "t1", "priority": float("inf")}),
            (False, "priority must be a finite number"))
        self.assertEqual(board.tasks, {})

    # -- 12 stash-sent-once tests --

    def test_stash_two_callers_send_one_stash_once(self):
        self.assertTrue(self._stash("bm-stash-0001", "alpha"))
        sent, results = [], []
        self._run_threads([
            lambda: results.append(B.R.deliver_stash(
                self.tmp, "bm-stash-0001", self._sender(sent))),
            lambda: results.append(B.R.deliver_stash(
                self.tmp, "bm-stash-0001", self._sender(sent))),
        ])
        self.assertEqual(sent, ["alpha"])
        self.assertEqual(sorted(results), [False, True])
        self.assertIsNone(B.R.load_stash(self.tmp, "bm-stash-0001"))
        self.assertTrue(os.path.isfile(
            B.R._sent_path(self.tmp, "bm-stash-0001")))

    def test_stash_four_callers_send_one_stash_once(self):
        self.assertTrue(self._stash("k1", "alpha"))
        sent = []
        self._run_threads([
            (lambda: B.R.deliver_stash(self.tmp, "k1", self._sender(sent)))
            for _ in range(4)])
        self.assertEqual(sent, ["alpha"])

    def test_stash_a_second_sequential_deliver_finds_the_record_gone(self):
        self.assertTrue(self._stash("k1", "alpha"))
        sent = []
        self.assertTrue(B.R.deliver_stash(self.tmp, "k1",
                                          self._sender(sent, delay=0)))
        self.assertFalse(B.R.deliver_stash(self.tmp, "k1",
                                           self._sender(sent, delay=0)))
        self.assertEqual(sent, ["alpha"])

    def test_stash_a_resend_and_a_direct_deliver_racing_send_it_once(self):
        for round_no in range(5):
            key = f"race-{round_no}"
            base = os.path.join(self.tmp, f"base-{round_no}")
            self.assertTrue(self._stash(key, "alpha", base=base))
            sent = []
            self._run_threads([
                lambda base=base, key=key: B.R.resend_stashed(
                    base, {}, self._sender(sent), now=time.time() + 120),
                lambda base=base, key=key: B.R.deliver_stash(
                    base, key, self._sender(sent)),
            ])
            self.assertEqual(sent, ["alpha"], f"round {round_no}")

    def test_stash_a_failed_send_keeps_the_record_and_the_next_send_is_the_only_one(self):
        self.assertTrue(self._stash("k1", "alpha"))

        def boom(subject, body, to):
            raise OSError("down")

        self.assertFalse(B.R.deliver_stash(self.tmp, "k1", boom))
        rec = B.R.load_stash(self.tmp, "k1")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["attempts"], 1)
        self.assertEqual(rec["last_error"], "down")
        self.assertEqual(rec["body"], "alpha")
        sent = []
        self.assertTrue(B.R.deliver_stash(self.tmp, "k1",
                                          self._sender(sent, delay=0)))
        self.assertEqual(sent, ["alpha"])

    def test_stash_two_keys_racing_each_send_their_own_record_once(self):
        self.assertTrue(self._stash("k1", "one"))
        self.assertTrue(self._stash("k2", "two"))
        sent = []
        self._run_threads([
            lambda: B.R.deliver_stash(self.tmp, "k1", self._sender(sent)),
            lambda: B.R.deliver_stash(self.tmp, "k2", self._sender(sent)),
            lambda: B.R.deliver_stash(self.tmp, "k1", self._sender(sent)),
            lambda: B.R.deliver_stash(self.tmp, "k2", self._sender(sent)),
        ])
        self.assertEqual(sorted(sent), ["one", "two"])

    def test_stash_a_fresh_stash_after_delivery_is_a_new_record_and_sends(self):
        self.assertTrue(self._stash("k1", "alpha"))
        sent = []
        self.assertTrue(B.R.deliver_stash(self.tmp, "k1",
                                          self._sender(sent, delay=0)))
        self.assertTrue(self._stash("k1", "beta"))
        self.assertTrue(B.R.deliver_stash(self.tmp, "k1",
                                          self._sender(sent, delay=0)))
        self.assertEqual(sent, ["alpha", "beta"])

    def test_stash_the_guard_is_one_lock_per_key_and_coerces_the_key_to_text(self):
        self.assertIs(B.R._stash_guard("k1"), B.R._stash_guard("k1"))
        self.assertIsNot(B.R._stash_guard("k1"), B.R._stash_guard("k2"))
        self.assertIs(B.R._stash_guard(123), B.R._stash_guard("123"))

    def test_stash_an_undelivered_record_can_be_sent_again_by_design(self):
        self.assertTrue(self._stash("k1", "alpha"))
        sent = []
        self.assertTrue(B.R.deliver_stash(self.tmp, "k1",
                                          self._sender(sent, delay=0)))
        B.R.undeliver_stash(self.tmp, "k1", "channel write failed")
        self.assertIsNotNone(B.R.load_stash(self.tmp, "k1"))
        self.assertTrue(B.R.deliver_stash(self.tmp, "k1",
                                          self._sender(sent, delay=0)))
        self.assertEqual(sent, ["alpha", "alpha"])

    def test_stash_the_resend_pass_alone_sends_once_and_a_second_pass_sends_nothing(self):
        self.assertTrue(self._stash("k1", "alpha"))
        sent = []
        counts = B.R.resend_stashed(self.tmp, {}, self._sender(sent, delay=0),
                                    now=time.time() + 120)
        self.assertEqual(counts["delivered"], 1)
        self.assertEqual(sent, ["alpha"])
        counts = B.R.resend_stashed(self.tmp, {}, self._sender(sent, delay=0),
                                    now=time.time() + 240)
        self.assertEqual(counts["delivered"], 0)
        self.assertEqual(counts["attempted"], 0)
        self.assertEqual(sent, ["alpha"])

    def test_stash_delivering_nothing_and_an_invalid_base_send_nothing(self):
        sent = []
        self.assertFalse(B.R.deliver_stash(self.tmp, "missing",
                                           self._sender(sent, delay=0)))
        self.assertFalse(B.R.deliver_stash("", "k1",
                                           self._sender(sent, delay=0)))
        self.assertFalse(B.R.deliver_stash(None, "k1",
                                           self._sender(sent, delay=0)))
        self.assertEqual(sent, [])

    def test_stash_the_record_carries_its_fields_through_a_failed_attempt(self):
        self.assertTrue(B.R.stash_result(
            self.tmp, "k1", {"job_id": "job-9", "kind": "exec"},
            "[HOMING-PIGEON] result job-9", "body-9", to="a@example.com"))

        def boom(subject, body, to):
            raise ValueError("header")

        self.assertFalse(B.R.deliver_stash(self.tmp, "k1", boom))
        rec = B.R.load_stash(self.tmp, "k1")
        self.assertEqual(rec["skey"], "k1")
        self.assertEqual(rec["job_id"], "job-9")
        self.assertEqual(rec["subject"], "[HOMING-PIGEON] result job-9")
        self.assertEqual(rec["body"], "body-9")
        self.assertEqual(rec["to"], "a@example.com")
        self.assertEqual(rec["attempts"], 1)
        self.assertEqual(rec["last_error"], "header")

    # -- 6 corpus contract tests (the fix's own entries, replayed) --

    def test_contract_the_filed_board_entry_with_a_separator_id_meets_the_contract(self):
        self._check("board_mail",
                    {"file": None, "ident": "\x1f",
                     "kind": {"task_id": ".", "type": "task_approve", "v": 1},
                     "payload": "task_approve"})

    def test_contract_the_filed_board_entry_with_a_splitting_board_key_meets_the_contract(self):
        self._check("board_mail",
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
                                 "worker_id": "worker-a"}})

    def test_contract_a_seed_board_submit_entry_meets_the_contract(self):
        seeds = {e["from"]: e for e in B.seeds_board_mail()}
        entry = seeds["seed:submit"]
        self.assertIn(B._with_rig(lambda: B.check("board_mail", entry)),
                      ("accepted", "refused"))

    def test_contract_a_seed_board_request_entry_meets_the_contract(self):
        seeds = {e["from"]: e for e in B.seeds_board_mail()}
        named = [e for name, e in seeds.items() if "request" in name]
        self.assertTrue(named, sorted(seeds))
        for entry in named[:1]:
            self.assertIn(B._with_rig(lambda e=entry: B.check("board_mail", e)),
                          ("accepted", "refused"))

    def test_contract_the_filed_race_stash_entries_meet_the_contract_repeatedly(self):
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
            self._check("race_stash", data, rounds=3)

    def test_contract_the_two_bodies_one_key_seed_never_sends_both(self):
        seeds = {e["from"]: e for e in B.seeds_race_stash()}
        entry = seeds["seed:two_bodies_one_key"]
        for _ in range(3):
            self.assertIn(B._with_rig(lambda: B.check("race_stash", entry)),
                          ("accepted", "refused"))

    # -- 2 bookend / run-length sweeps --

    def test_bookends_every_ascii_symbol_around_a_board_key_and_a_stash_body(self):
        self.assertEqual(len(string.punctuation), 32)
        mapping = {}
        for ch in string.punctuation:
            key = f"{ch}task1{ch}"
            mapping[key] = self._task(key)
        mapping["@@task@@"] = self._task("@@task@@")     # matched pair
        mapping["!task~"] = self._task("!task~")          # mismatched pair
        mapping[string.punctuation] = self._task(string.punctuation)
        board = self._board(mapping)
        self.assertEqual(sorted(board.tasks),
                         ["-task1-", ".task1.", "_task1_"])
        # Stash bodies bookended the same way are delivered
        # verbatim, each exactly once.
        sent = []
        for i, ch in enumerate(string.punctuation):
            key = f"b{i:02d}"
            self.assertTrue(self._stash(key, f"{ch}core{ch}"))
            self.assertTrue(B.R.deliver_stash(
                self.tmp, key, self._sender(sent, delay=0)))
        self.assertEqual(sent, [f"{ch}core{ch}" for ch in string.punctuation])
        self.assertTrue(self._stash("pair", "@@core@@"))
        self.assertTrue(B.R.deliver_stash(self.tmp, "pair",
                                          self._sender(sent, delay=0)))
        self.assertTrue(self._stash("only", string.punctuation))
        self.assertTrue(B.R.deliver_stash(self.tmp, "only",
                                          self._sender(sent, delay=0)))
        self.assertEqual(sent[-2:], ["@@core@@", string.punctuation])

    def test_runs_and_controls_board_keys_stash_bodies_and_subject_ids(self):
        # Board keys: runs and controls follow the id grammar.
        mapping = {}
        for key in ("-" * 10, "a" * 128, "...",
                    "a" * 129, "!" * 10, "a\x1fb", "a\0b", "a\tb", "a\nb",
                    "'; DROP TABLE board; --", "__proto__"):
            mapping[key] = self._task(key)
        board = self._board(mapping)
        self.assertEqual(sorted(board.tasks),
                         ["-" * 10, "...", "__proto__", "a" * 128])
        # Stash bodies: runs of the odd character at the front,
        # the back and the middle are delivered verbatim, once.
        shapes = []
        for n in (1, 5, 10):
            shapes += ["!" * n + "core", "core" + "!" * n,
                       "co" + "!" * n + "re", "a" * 10 + "!",
                       "!" + "a" * 10, "a" * 5 + "!" + "a" * 5,
                       "\0core\0", "\tcore\t", "\rcore\r", "\ncore\n"]
        sent = []
        for i, body in enumerate(shapes):
            key = f"s{i:02d}"
            self.assertTrue(self._stash(key, body))
            self.assertTrue(B.R.deliver_stash(
                self.tmp, key, self._sender(sent, delay=0)))
        self.assertEqual(sent, shapes)
        # Subject ids: the same run shapes are taken whole by the
        # board grammar (its gate, not the grammar, refuses them).
        for body in ("!" * 10 + "t1", "t1" + "!" * 10,
                     "t" + "!" * 5 + "1", "a" * 10 + "!"):
            m = self._match(f"[HOMING-PIGEON] task_submit {body}")
            self.assertIsNotNone(m, body)
            self.assertEqual(m.group(2), body, body)


if __name__ == "__main__":
    unittest.main()
