#!/usr/bin/env python3
"""Tests for the disk guard: the 90% truncation guard in
runner/oracle/resources.py and its annotation in the runner.

The guard is on by default, acts only on the runner's own
material under base_dir, gives up its logs first and the oldest
material first, records what it did, and never stops the runner.
Disk pressure is simulated by patching _disk_fraction with a fake
that reads the real bytes under base_dir against a fixed total,
so a pass that frees real bytes sees the fraction fall, exactly
as it would on a real disk.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.oracle import resources as RS  # noqa: E402


def _tree_bytes(d):
    total = 0
    for root, _dirs, files in os.walk(d):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


class FakeDisk:
    """_disk_fraction stand-in: real bytes under base over a
    fixed total, clamped to 1."""

    def __init__(self, base, total):
        self.base = base
        self.total = total

    def __call__(self, path):
        return min(1.0, _tree_bytes(self.base) / self.total)


def _write(path, nbytes, mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * nbytes)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


# A recorded result older than the replay window at its default:
# 3600 seconds of freshness and the 300 second future bound.
OLD = 5000


def _write_log(path, lines):
    """A log of numbered 32-byte lines."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        for i in range(lines):
            f.write(("%06d " % i).encode("ascii") + b"x" * 24 + b"\n")
    return path


class EnabledTest(unittest.TestCase):
    def test_absent_key_is_on(self):
        self.assertTrue(RS.disk_guard_enabled({}))

    def test_false_is_on(self):
        self.assertTrue(RS.disk_guard_enabled({"no_90_disk_truncation": False}))

    def test_only_literal_true_turns_it_off(self):
        self.assertFalse(RS.disk_guard_enabled({"no_90_disk_truncation": True}))
        for value in ("true", "yes", 1, 0, None, [], {}):
            self.assertTrue(
                RS.disk_guard_enabled({"no_90_disk_truncation": value}),
                f"value {value!r} must leave the guard on")

    def test_bad_cfg_shape_is_on(self):
        self.assertTrue(RS.disk_guard_enabled(None))
        self.assertTrue(RS.disk_guard_enabled("junk"))
        self.assertTrue(RS.disk_guard_enabled([1, 2]))


class ThresholdTest(unittest.TestCase):
    def test_below_threshold_does_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            log = _write_log(os.path.join(d, "runner.log"), 6250)
            with mock.patch.object(RS, "_disk_fraction", lambda p: 0.8999):
                self.assertIsNone(RS.guard_disk({}, d))
            self.assertEqual(os.path.getsize(log), 200000)

    def test_at_threshold_acts(self):
        with tempfile.TemporaryDirectory() as d:
            log = _write_log(os.path.join(d, "runner.log"), 6250)
            with mock.patch.object(RS, "_disk_fraction", lambda p: 0.90):
                event = RS.guard_disk({}, d)
            self.assertIsNotNone(event)
            self.assertLess(os.path.getsize(log), 200000)

    def test_unreadable_disk_does_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            _write_log(os.path.join(d, "runner.log"), 6250)
            with mock.patch.object(RS, "_disk_fraction", lambda p: None):
                self.assertIsNone(RS.guard_disk({}, d))

    def test_bad_base_does_nothing(self):
        self.assertIsNone(RS.guard_disk({}, ""))
        self.assertIsNone(RS.guard_disk({}, None))
        self.assertIsNone(RS.guard_disk({}, 42))


class OptOutTest(unittest.TestCase):
    def test_opt_out_leaves_everything_alone(self):
        with tempfile.TemporaryDirectory() as d:
            log = _write_log(os.path.join(d, "runner.log"), 6250)
            sent = _write(os.path.join(d, "sent", "a.json"), 100000)
            cfg = {"no_90_disk_truncation": True}
            with mock.patch.object(RS, "_disk_fraction", lambda p: 0.99):
                self.assertIsNone(RS.guard_disk(cfg, d))
            self.assertEqual(os.path.getsize(log), 200000)
            self.assertTrue(os.path.exists(sent))


class OrderTest(unittest.TestCase):
    def test_logs_go_before_recorded_results(self):
        with tempfile.TemporaryDirectory() as d:
            _write_log(os.path.join(d, "runner.log"), 6250)  # 200000 bytes
            sent = _write(os.path.join(d, "sent", "a.json"), 200000)
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 420000)):
                event = RS.guard_disk({}, d)
            self.assertIsNotNone(event)
            self.assertTrue(os.path.exists(sent))
            self.assertEqual([a["path"] for a in event["actions"]],
                             ["runner.log"])
            self.assertFalse(event["still_over"])

    def test_rolled_backups_go_before_live_logs(self):
        with tempfile.TemporaryDirectory() as d:
            now = time.time()
            backup = _write(os.path.join(d, "runner.log.1"), 100000,
                            mtime=now - 5000)
            log = _write_log(os.path.join(d, "runner.log"), 3125)  # 100000
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 210000)):
                event = RS.guard_disk({}, d)
            self.assertIsNotNone(event)
            self.assertFalse(os.path.exists(backup))
            self.assertEqual(os.path.getsize(log), 100000)
            self.assertEqual(event["actions"][0]["path"], "runner.log.1")
            self.assertEqual(event["actions"][0]["action"], "remove")

    def test_oldest_first_within_a_stage(self):
        with tempfile.TemporaryDirectory() as d:
            now = time.time()
            old = _write(os.path.join(d, "sent", "old.json"), 100000,
                         mtime=now - 9000)
            new = _write(os.path.join(d, "sent", "new.json"), 100000,
                         mtime=now - OLD)
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 210000)):
                event = RS.guard_disk({}, d)
            self.assertIsNotNone(event)
            self.assertFalse(os.path.exists(old))
            self.assertTrue(os.path.exists(new))

    def test_oldest_first_across_result_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            now = time.time()
            retained = _write(os.path.join(d, "retained", "r.json"), 100000,
                              mtime=now - 9000)
            sent = _write(os.path.join(d, "sent", "s.json"), 100000,
                          mtime=now - OLD)
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 210000)):
                RS.guard_disk({}, d)
            self.assertFalse(os.path.exists(retained))
            self.assertTrue(os.path.exists(sent))

    def test_a_recorded_result_inside_the_replay_window_stays(self):
        # It is the layer that answers a redelivery the door would
        # still take once the replay cache has let the id go, so it
        # is not the guard's to give up.
        with tempfile.TemporaryDirectory() as d:
            now = time.time()
            fresh = _write(os.path.join(d, "sent", "fresh.json"), 100000,
                           mtime=now - 100)
            with mock.patch.object(RS, "_disk_fraction", lambda p: 0.99):
                event = RS.guard_disk({}, d, now=now)
            self.assertIsNone(event)
            self.assertTrue(os.path.exists(fresh))

    def test_the_replay_window_is_the_freshness_window_and_its_bound(self):
        self.assertEqual(RS._guard_replay_window({}), 3600 + 300)
        self.assertEqual(RS._guard_replay_window(None), 3900)
        self.assertEqual(
            RS._guard_replay_window({"max_job_age_sec": 60}), 360)
        # An unusable value reads as the documented default, as at
        # the door.
        for bad in (0, -5, True, "soon", None, []):
            self.assertEqual(
                RS._guard_replay_window({"max_job_age_sec": bad}), 3900,
                bad)

    def test_a_recorded_result_goes_only_once_past_the_window(self):
        with tempfile.TemporaryDirectory() as d:
            now = 2000000.0
            window = RS._guard_replay_window({})
            at_edge = _write(os.path.join(d, "sent", "edge.json"), 1000,
                             mtime=now - window)
            past = _write(os.path.join(d, "sent", "past.json"), 1000,
                          mtime=now - window - 1)
            with mock.patch.object(RS, "_disk_fraction", lambda p: 0.99):
                event = RS.guard_disk({}, d, now=now)
            self.assertEqual([a["path"] for a in event["actions"]],
                             [os.path.join("sent", "past.json")])
            self.assertTrue(os.path.exists(at_edge))
            self.assertFalse(os.path.exists(past))

    def test_the_window_follows_max_job_age_sec(self):
        with tempfile.TemporaryDirectory() as d:
            now = 2000000.0
            record = _write(os.path.join(d, "sent", "r.json"), 1000,
                            mtime=now - 5000)
            with mock.patch.object(RS, "_disk_fraction", lambda p: 0.99):
                wide = RS.guard_disk({"max_job_age_sec": 86400}, d, now=now)
                self.assertIsNone(wide)
                self.assertTrue(os.path.exists(record))
                narrow = RS.guard_disk({"max_job_age_sec": 3600}, d,
                                       now=now + 1000)
            self.assertIsNotNone(narrow)
            self.assertFalse(os.path.exists(record))

    def test_only_recorded_results_have_a_replay_window(self):
        # A retained output and a given up stash answer no
        # redelivery: fresh ones go like any other.
        with tempfile.TemporaryDirectory() as d:
            now = time.time()
            retained = _write(os.path.join(d, "retained", "r.json"), 1000,
                              mtime=now - 10)
            failed = _write(os.path.join(d, "outbox", "failed", "f.json"),
                            1000, mtime=now - 10)
            with mock.patch.object(RS, "_disk_fraction", lambda p: 0.99):
                RS.guard_disk({}, d, now=now)
            self.assertFalse(os.path.exists(retained))
            self.assertFalse(os.path.exists(failed))

    def test_pending_outbox_kept_failed_stash_given_up(self):
        with tempfile.TemporaryDirectory() as d:
            now = time.time()
            failed = _write(os.path.join(d, "outbox", "failed", "f.json"),
                            100000, mtime=now - 5000)
            pending = _write(os.path.join(d, "outbox", "p.json"), 100000,
                             mtime=now - 9000)
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 210000)):
                RS.guard_disk({}, d)
            self.assertFalse(os.path.exists(failed))
            self.assertTrue(os.path.exists(pending))


class ScopeTest(unittest.TestCase):
    def test_only_own_material_is_touched(self):
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "state")
            os.makedirs(base)
            config = _write(os.path.join(base, "config.json"), 50000)
            board = _write(os.path.join(base, "board.json"), 50000)
            seen = _write(os.path.join(base, "seen.json"), 50000)
            events = _write(os.path.join(base, "security-events.jsonl"),
                            50000)
            sent = _write(os.path.join(base, "sent", "a.json"), 10000,
                          mtime=time.time() - OLD)
            outside = _write(os.path.join(d, "other-app.bin"), 50000)
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(base, 55000)):
                event = RS.guard_disk({}, base)
            self.assertIsNotNone(event)
            self.assertTrue(event["still_over"])
            self.assertFalse(os.path.exists(sent))
            for kept in (config, board, seen, events, outside):
                self.assertTrue(os.path.exists(kept), kept)

    def test_symlink_is_never_followed(self):
        with tempfile.TemporaryDirectory() as d:
            target = _write(os.path.join(d, "target.bin"), 100000)
            sent_dir = os.path.join(d, "sent")
            os.makedirs(sent_dir)
            link = os.path.join(sent_dir, "link.json")
            try:
                os.symlink(target, link)
            except (OSError, NotImplementedError):
                return  # the platform cannot make the link; nothing to pin
            real = _write(os.path.join(sent_dir, "real.json"), 100000,
                          mtime=time.time() - OLD)
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 210000)):
                RS.guard_disk({}, d)
            self.assertTrue(os.path.exists(target))
            self.assertTrue(os.path.islink(link))
            self.assertFalse(os.path.exists(real))


class LogTruncationTest(unittest.TestCase):
    def test_newest_tail_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            log = _write_log(os.path.join(d, "runner.log"), 6250)
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 210000)):
                RS.guard_disk({}, d)
            with open(log, "rb") as f:
                data = f.read()
            self.assertLessEqual(len(data), RS.DISK_GUARD_LOG_KEEP_BYTES + 32)
            self.assertIn(b"006249", data)
            self.assertNotIn(b"000000", data)
            # The kept tail starts on a line boundary.
            self.assertTrue(data[:6].isdigit())

    def test_small_log_is_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            log = _write_log(os.path.join(d, "runner.log"), 100)
            sent = _write(os.path.join(d, "sent", "a.json"), 100000,
                          mtime=time.time() - OLD)
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 110000)):
                RS.guard_disk({}, d)
            self.assertEqual(os.path.getsize(log), 3200)
            self.assertFalse(os.path.exists(sent))


class WorkspaceTest(unittest.TestCase):
    def test_old_workspace_removed_fresh_one_kept(self):
        with tempfile.TemporaryDirectory() as d:
            now = time.time()
            old_dir = os.path.join(d, "work", "oldjob")
            _write(os.path.join(old_dir, "out.bin"), 100000)
            os.utime(old_dir, (now - 7200, now - 7200))
            new_dir = os.path.join(d, "work", "newjob")
            _write(os.path.join(new_dir, "out.bin"), 100000)
            os.utime(new_dir, (now, now))
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 210000)):
                event = RS.guard_disk({}, d, now=now)
            self.assertIsNotNone(event)
            self.assertFalse(os.path.exists(old_dir))
            self.assertTrue(os.path.exists(new_dir))


class AnnotationTest(unittest.TestCase):
    def test_event_shape_and_accounting(self):
        with tempfile.TemporaryDirectory() as d:
            _write_log(os.path.join(d, "runner.log"), 6250)
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 210000)):
                event = RS.guard_disk({}, d)
            self.assertEqual(event["type"], "disk_truncation")
            self.assertEqual(event["threshold"], RS.DISK_GUARD_THRESHOLD)
            self.assertGreaterEqual(event["disk_before"],
                                    RS.DISK_GUARD_THRESHOLD)
            self.assertLess(event["disk_after"], RS.DISK_GUARD_THRESHOLD)
            self.assertFalse(event["still_over"])
            self.assertEqual(event["freed_bytes"],
                             sum(a["bytes"] for a in event["actions"]))
            self.assertGreater(event["freed_bytes"], 0)
            for action in event["actions"]:
                self.assertFalse(os.path.isabs(action["path"]))
                self.assertIn(action["action"], ("truncate", "remove"))

    def test_note_writes_the_event_to_security_events(self):
        from runner import runner as RR
        with tempfile.TemporaryDirectory() as d:
            _write_log(os.path.join(d, "runner.log"), 6250)
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 210000)):
                event = RS.guard_disk({}, d)
            RR._note_disk_guard_event(d, event)
            path = os.path.join(d, "security-events.jsonl")
            with open(path, "r", encoding="utf-8") as f:
                lines = [json.loads(x) for x in f if x.strip()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["type"], "disk_truncation")
            self.assertEqual(lines[0]["freed_bytes"], event["freed_bytes"])

    def test_note_ignores_bad_shapes(self):
        from runner import runner as RR
        with tempfile.TemporaryDirectory() as d:
            RR._note_disk_guard_event(d, None)
            RR._note_disk_guard_event(d, {"type": "resource_pressure"})
            RR._note_disk_guard_event(d, "junk")
            self.assertFalse(
                os.path.exists(os.path.join(d, "security-events.jsonl")))


class CooldownTest(unittest.TestCase):
    def test_still_over_pass_holds_off_the_next_one(self):
        with tempfile.TemporaryDirectory() as d:
            now = 1000000.0
            _write(os.path.join(d, "sent", "a.json"), 10000,
                   mtime=now - OLD)
            with mock.patch.object(RS, "_disk_fraction", lambda p: 0.99):
                first = RS.guard_disk({}, d, now=now)
                self.assertIsNotNone(first)
                self.assertTrue(first["still_over"])
                _write(os.path.join(d, "sent", "b.json"), 10000,
                       mtime=now - OLD)
                self.assertIsNone(RS.guard_disk({}, d, now=now + 60))
                self.assertTrue(
                    os.path.exists(os.path.join(d, "sent", "b.json")))
                third = RS.guard_disk({}, d, now=now + 1000)
                self.assertIsNotNone(third)
                self.assertFalse(
                    os.path.exists(os.path.join(d, "sent", "b.json")))


class KeepsRunningTest(unittest.TestCase):
    def test_monitor_and_guard_both_run_after_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            _write_log(os.path.join(d, "runner.log"), 6250)
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 210000)):
                event = RS.guard_disk({}, d)
                self.assertIsNotNone(event)
                # Back under the threshold: the next pass is a no-op
                # and the monitor still answers.
                self.assertIsNone(RS.guard_disk({}, d))
                self.assertIsNone(RS.check_resources({}, d))

    def test_malformed_resources_block_still_protects(self):
        with tempfile.TemporaryDirectory() as d:
            log = _write_log(os.path.join(d, "runner.log"), 6250)
            cfg = {"resources": {"threshold": "junk"}}
            with mock.patch.object(RS, "_disk_fraction", FakeDisk(d, 210000)):
                event = RS.guard_disk(cfg, d)
            self.assertIsNotNone(event)
            self.assertLess(os.path.getsize(log), 200000)


if __name__ == "__main__":
    unittest.main()
