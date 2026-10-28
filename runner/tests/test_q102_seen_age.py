# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""Q102: the replay cache keeps an entry by its age, not its place.

The cache used to keep the newest 2000 keys. Board polling writes one
key per request since Q98, so a busy board could push a job's key out
while a captured copy of that job was still inside the freshness
window, and the copy would run again. Now an entry keeps the time it
was first recorded and leaves only once no message carrying it could
pass the freshness check: the window plus the 300-second future
bound, a day at least. The count is a backstop far above any window.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

import runner.runner as rr
from runner.runner import load_seen, save_seen, seen_keep_sec

T0 = 1_800_000_000.0


class KeepHorizonTest(unittest.TestCase):

    def test_the_window_plus_the_future_bound_a_day_at_least(self):
        self.assertEqual(86400, seen_keep_sec({}))
        self.assertEqual(86400, seen_keep_sec({"max_job_age_sec": 60}))
        self.assertEqual(7 * 86400 + 300,
                         seen_keep_sec({"max_job_age_sec": 7 * 86400}))
        self.assertEqual(86400, seen_keep_sec(None))
        self.assertEqual(86400, seen_keep_sec({"max_job_age_sec": "x"}))


class AgeRuleTest(unittest.TestCase):

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.path = os.path.join(self.td.name, "seen.json")
        keep = mock.patch.object(rr, "_SEEN_KEEP", [86400])
        keep.start()
        self.addCleanup(keep.stop)

    def _save(self, seen, at, keep=86400):
        with mock.patch.object(rr.time, "time", return_value=at):
            save_seen(self.path, seen, keep_sec=keep)

    def _disk(self):
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_a_flood_of_board_keys_does_not_push_out_a_fresh_job_key(self):
        self._save({"job-1": True}, T0)
        flood = {f"board:task_request:w1:{i:06d}": True for i in range(5000)}
        self._save(flood, T0 + 60)
        self.assertIn("job-1", load_seen(self.path))
        self.assertEqual(5001, len(load_seen(self.path)))

    def test_an_entry_keeps_the_time_it_was_first_recorded(self):
        self._save({"job-1": True}, T0)
        self._save({"job-1": True, "job-2": True}, T0 + 500)
        disk = self._disk()
        self.assertEqual(T0, disk["job-1"])
        self.assertEqual(T0 + 500, disk["job-2"])

    def test_an_entry_past_the_horizon_leaves_the_file_and_the_memory(self):
        seen = {"job-1": True}
        self._save(seen, T0)
        seen["job-2"] = True
        self._save(seen, T0 + 86400 + 1)
        self.assertEqual({"job-2"}, set(load_seen(self.path)))
        self.assertEqual({"job-2": True}, seen)

    def test_an_entry_inside_the_horizon_stays(self):
        self._save({"job-1": True}, T0)
        self._save({}, T0 + 86400 - 1)
        self.assertIn("job-1", load_seen(self.path))

    def test_a_longer_window_keeps_entries_longer(self):
        self._save({"job-1": True}, T0, keep=3 * 86400)
        self._save({}, T0 + 2 * 86400, keep=3 * 86400)
        self.assertIn("job-1", load_seen(self.path))

    def test_a_file_from_an_older_release_is_stamped_not_dropped(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(["old-1", "old-2"], fh)
        self._save({"new": True}, T0)
        self.assertEqual({"old-1": T0, "old-2": T0, "new": T0}, self._disk())
        self._save({}, T0 + 86400 + 1)
        self.assertEqual({}, load_seen(self.path))

    def test_load_seen_still_answers_true_for_every_key(self):
        self._save({"job-1": True}, T0)
        self.assertEqual({"job-1": True}, load_seen(self.path))
        self.assertEqual({"job-1": T0}, load_seen(self.path, stamped=True))

    def test_a_small_number_is_a_flag_not_a_time(self):
        self._save({"job-1": 1}, T0 + 86400 * 30)
        self.assertIn("job-1", load_seen(self.path))

    def test_the_ceiling_drops_the_oldest_and_says_so(self):
        seen = {f"k{i}": T0 + i for i in range(10)}
        with mock.patch.object(rr, "SEEN_CAP", 4), \
                mock.patch.object(rr, "log") as log:
            self._save(seen, T0 + 20)
        self.assertEqual({"k6", "k7", "k8", "k9"}, set(load_seen(self.path)))
        self.assertIn("ceiling", log.call_args[0][0])

    def test_a_freshness_refused_replay_needs_no_entry(self):
        # The horizon is never shorter than what the door would accept:
        # a message older than the window is refused before the cache.
        cfg = {"max_job_age_sec": 3600}
        ok, _why = rr._issued_at_ok("2001-01-01T00:00:00Z", cfg)
        self.assertFalse(ok)
        self.assertGreater(seen_keep_sec(cfg), 3600 + 300)


if __name__ == "__main__":
    unittest.main()
