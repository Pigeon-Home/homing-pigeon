# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""A cycling grow starts where the campaign is thinnest (Q107).

`grow --minutes` on a rig used to start every cycle at the head of
the target list, so a one-core box with a thirty-minute cycle grew
the first five targets every cycle and the rest never, and two rigs
on the same list spent the hour on the same targets. Now the targets
cycle least recently grown first, by the newest run record of each in
the merged runs.jsonl; `--order fixed` keeps the list's own order.
"""
import argparse
import unittest
from unittest import mock

from runner.tools import de_dust_corpus as B


def _run(target, when, kind="grow"):
    return {"kind": kind, "target": target, "when": when}


class StaleOrderTest(unittest.TestCase):

    def test_never_run_first_then_oldest_newest_record(self):
        runs = [_run("a", "2026-10-28T10:00:00Z"), _run("a", "2026-10-28T12:00:00Z"),
                _run("b", "2026-10-28T11:00:00Z"), _run("d", "2026-10-27T09:00:00Z")]
        self.assertEqual(["c", "d", "b", "a"], B.stale_order(["a", "b", "c", "d"], runs))

    def test_ties_keep_the_lists_order(self):
        runs = [_run("b", "2026-10-28T10:00:00Z"), _run("a", "2026-10-28T10:00:00Z")]
        self.assertEqual(["a", "b"], B.stale_order(["a", "b"], runs))
        self.assertEqual(["b", "a"], B.stale_order(["b", "a"], runs))

    def test_a_seed_record_counts_and_other_targets_do_not(self):
        runs = [_run("a", "2026-10-28T10:00:00Z", kind="seed"),
                _run("zzz", "2026-10-01T00:00:00Z")]
        self.assertEqual(["b", "a"], B.stale_order(["a", "b"], runs))

    def test_the_live_ledger_orders_every_target(self):
        order = B.stale_order(list(B.TARGETS))
        self.assertEqual(sorted(B.TARGETS), sorted(order))


class GrowUsesTheOrderTest(unittest.TestCase):

    def _grow(self, **over):
        args = argparse.Namespace(target="all", rounds=5, seed=1, jobs=1,
                                  minutes=1.0, verbose=False, archive=None,
                                  no_steer=True, order="stale")
        for k, v in over.items():
            setattr(args, k, v)
        seen = {}

        def fake_parallel(commands, jobs, out=print, minutes=0.0, **kw):
            seen["targets"] = [tg for tg, _cmd in commands]
            return 0

        with mock.patch.object(B, "run_parallel", fake_parallel), \
                mock.patch.object(B, "stale_order",
                                  side_effect=lambda ts, runs=None: list(reversed(ts))) as so, \
                mock.patch.object(B, "prune_retired_crashes", return_value=0):
            B.cmd_grow(args, out=lambda *a: None)
        return seen["targets"], so.called

    def test_a_cycling_grow_takes_the_stale_order(self):
        targets, called = self._grow()
        self.assertTrue(called)
        self.assertEqual(list(reversed(list(B.TARGETS))), targets)

    def test_order_fixed_keeps_the_list(self):
        targets, called = self._grow(order="fixed")
        self.assertFalse(called)
        self.assertEqual(list(B.TARGETS), targets)

    def test_one_pass_with_jobs_keeps_the_list(self):
        targets, called = self._grow(minutes=0.0, jobs=2)
        self.assertFalse(called)
        self.assertEqual(list(B.TARGETS), targets)


if __name__ == "__main__":
    unittest.main()
