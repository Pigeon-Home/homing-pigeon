# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The rig battery readiness probe: readiness is proven, not waited out.

The Windows preview battery trio (startup, build stamp, clock)
failed for 2 weeks on a healthy runner because the driver waited
a fixed 30 seconds for the runner log and slept a fixed 6
seconds: on the saturated rig the runner takes 140 to 154
seconds to reach its starting line. The harness fix proved
readiness with a real probe job instead. These tests pin that
behavior in runner/tools/rig_readiness.py, the repository home
of the fix: the starting line for the commit under test, the
transport watching line, and an attested probe result are all
required, in order; a missing probe envelope is resubmitted at
most 3 times inside the one budget; the clock job window stays
120 seconds. The supposition and conclusions stand in
docs/infrastructure-documents/project/rig-readiness-probe-2026-11-22.md.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tools import rig_readiness as rr  # noqa: E402

COMMIT = "abc1234deadbeef"
STARTING = "runner starting (build %s) on rig" % COMMIT
WATCHING = "file transport: watching C:\\hp-preview-test\\state"


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class ScriptedLog:
    """read_log() returns the text for the current fake time."""

    def __init__(self, clock, stages):
        # stages: list of (at_seconds, text), latest reached wins
        self.clock = clock
        self.stages = sorted(stages)

    def __call__(self):
        text = ""
        for at, stage_text in self.stages:
            if self.clock.t >= at:
                text = stage_text
        return text


def attested_probe(clock, latency=7.5):
    def probe():
        clock.t += latency
        return rr.ProbeOutcome(arrived=True, attested=True,
                               latency_sec=latency)
    return probe


class ConstantsTest(unittest.TestCase):
    def test_the_budgets_stand_as_named_constants(self):
        self.assertEqual(rr.READINESS_BUDGET_SEC, 420)
        self.assertEqual(rr.CLOCK_JOB_TIMEOUT_SEC, 120)
        self.assertEqual(rr.MAX_PROBE_ATTEMPTS, 3)
        self.assertEqual(rr.PROBE_RESULT_TIMEOUT_SEC, 240)

    def test_the_default_budget_is_the_named_constant(self):
        import inspect
        sig = inspect.signature(rr.wait_for_readiness)
        self.assertEqual(sig.parameters["budget_sec"].default,
                         rr.READINESS_BUDGET_SEC)


class ReadinessTest(unittest.TestCase):
    def _run(self, log, probe, alive=None, budget=420):
        clock = log.clock if hasattr(log, "clock") else FakeClock()
        return rr.wait_for_readiness(
            log, COMMIT, probe, budget_sec=budget,
            alive=alive, now=clock.now, sleep=clock.sleep,
            poll_interval_sec=1.0), clock

    def test_ready_when_all_three_stages_pass(self):
        clock = FakeClock()
        log = ScriptedLog(clock, [(10, STARTING + "\n" + WATCHING)])
        calls = []

        def probe():
            calls.append(1)
            clock.t += 7.5
            return rr.ProbeOutcome(True, True, 7.5)

        res, _ = self._run(log, probe)
        self.assertTrue(res.ready)
        self.assertEqual(res.starting_line, STARTING)
        self.assertEqual(res.seen_starting_line, STARTING)
        self.assertTrue(res.watching)
        self.assertEqual(res.probe_attempts, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(res.probe_sec, 7.5)
        self.assertGreaterEqual(res.ready_in_sec, 17.5)

    def test_the_starting_line_alone_is_never_readiness(self):
        clock = FakeClock()
        log = ScriptedLog(clock, [(0, STARTING)])
        calls = []

        def probe():
            calls.append(1)
            return rr.ProbeOutcome(True, True, 1.0)

        res, _ = self._run(log, probe, budget=30)
        self.assertFalse(res.ready)
        self.assertEqual(calls, [],
                         "the probe must not fire before the "
                         "transport is watching")
        self.assertFalse(res.watching)

    def test_the_watching_line_alone_is_never_readiness(self):
        clock = FakeClock()
        log = ScriptedLog(clock, [(0, WATCHING)])
        res, _ = self._run(log, attested_probe(clock), budget=30)
        self.assertFalse(res.ready)
        self.assertEqual(res.probe_attempts, 0)
        self.assertEqual(res.seen_starting_line, "")

    def test_a_starting_line_for_another_commit_does_not_count(self):
        clock = FakeClock()
        other = "runner starting (build 9999other) on rig"
        log = ScriptedLog(clock, [(0, other + "\n" + WATCHING)])
        res, _ = self._run(log, attested_probe(clock), budget=30)
        self.assertFalse(res.ready)
        self.assertEqual(res.seen_starting_line, other)
        self.assertEqual(res.starting_line, "")
        self.assertEqual(res.probe_attempts, 0)

    def test_an_unattested_probe_result_is_not_readiness(self):
        clock = FakeClock()
        log = ScriptedLog(clock, [(0, STARTING + "\n" + WATCHING)])

        def probe():
            clock.t += 3.0
            return rr.ProbeOutcome(arrived=True, attested=False,
                                   latency_sec=3.0)

        res, _ = self._run(log, probe)
        self.assertFalse(res.ready)
        self.assertGreaterEqual(res.probe_attempts, 1)

    def test_a_missing_envelope_is_resubmitted_then_ready(self):
        clock = FakeClock()
        log = ScriptedLog(clock, [(0, STARTING + "\n" + WATCHING)])
        outcomes = [None, None, rr.ProbeOutcome(True, True, 5.0)]

        def probe():
            clock.t += 2.0
            return outcomes.pop(0)

        res, _ = self._run(log, probe)
        self.assertTrue(res.ready)
        self.assertEqual(res.probe_attempts, 3)
        self.assertEqual(res.probe_sec, 5.0)

    def test_missing_envelopes_stop_at_three_attempts(self):
        clock = FakeClock()
        log = ScriptedLog(clock, [(0, STARTING + "\n" + WATCHING)])

        def probe():
            clock.t += 2.0
            return None

        res, _ = self._run(log, probe)
        self.assertFalse(res.ready)
        self.assertEqual(res.probe_attempts, 3)

    def test_resubmission_stays_inside_the_one_budget(self):
        clock = FakeClock()
        log = ScriptedLog(clock, [(0, STARTING + "\n" + WATCHING)])

        def probe():
            clock.t += 500.0
            return None

        res, _ = self._run(log, probe, budget=420)
        self.assertFalse(res.ready)
        self.assertEqual(res.probe_attempts, 1,
                         "an attempt that eats the budget leaves "
                         "no room for another")

    def test_budget_expiry_before_the_starting_line(self):
        clock = FakeClock()
        log = ScriptedLog(clock, [])
        res, _ = self._run(log, attested_probe(clock), budget=20)
        self.assertFalse(res.ready)
        self.assertEqual(res.probe_attempts, 0)
        self.assertGreaterEqual(res.ready_in_sec, 20)

    def test_a_missing_log_is_not_an_error(self):
        clock = FakeClock()
        log = ScriptedLog(clock, [(0, "")])
        res, _ = self._run(log, attested_probe(clock), budget=5)
        self.assertFalse(res.ready)

    def test_a_dead_process_fails_fast(self):
        clock = FakeClock()
        log = ScriptedLog(clock, [])
        state = {"alive": True}

        def alive():
            return clock.t < 10

        res, _ = self._run(log, attested_probe(clock), alive=alive,
                           budget=420)
        self.assertFalse(res.ready)
        self.assertLess(res.ready_in_sec, 60)

    def test_a_process_dying_before_the_probe_is_not_ready(self):
        clock = FakeClock()
        log = ScriptedLog(clock, [(0, STARTING + "\n" + WATCHING)])

        def alive():
            return clock.t < 5

        def probe():
            clock.t += 30.0
            return rr.ProbeOutcome(True, True, 30.0)

        res, _ = self._run(log, probe, alive=alive)
        self.assertFalse(res.ready)


if __name__ == "__main__":
    unittest.main()
