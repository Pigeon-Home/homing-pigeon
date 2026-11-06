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


import string  # noqa: E402


class ReplayCacheAgeShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 51, Q102: the replay
    cache kept an entry by its place, not its age; callers saw
    times instead of keys (fixed eff6a7ae, 369eafd9 and
    862669f2, 27-Oct-2026). The fixes made an entry keep the
    time it was first recorded and leave, from the file and
    from memory, only past seen_keep_sec (the freshness window
    plus the 300-second future bound, a day at least), made the
    count a backstop at SEEN_CAP, oldest first and logged, made
    a file from an older release be stamped on its next save
    rather than dropped, and made _with_seen_file answer True
    per key while _write_seen_unlocked returns nothing -- the
    stamps live on disk only. This family scattershots
    everything around those failures: floods at and past the
    old 2000 count, ages at, inside and past the horizon, the
    stamp-plausibility bound, flag-shaped values, bookended
    keys, and every caller-visible shape. The fixes' own tests
    live in this file, so the family lives here too. One
    regression test was never going to be enough for a bug that
    took days of CPU to find.

    Per-field enumeration: the one governing config field,
    max_job_age_sec, is enumerated value by value against
    seen_keep_sec (the generated tests); the entry fields --
    the key and its recorded-at value -- are each enumerated
    (string, non-string and NUL keys; stamp, flag, bool, small
    number and wrong-typed values); and keep_sec, the save
    call's own field, is enumerated for the values that set it
    and the values that must not. Bookends: every printable
    ASCII symbol at the front and at the back of a key, plus
    tab, CR and LF keys as distinct entries and a NUL key
    dropped. Run lengths: floods of 2000, 2001 and 10000 board
    keys, ages run at 1 second inside, exactly at, and 1 second
    past the horizon, and repeated saves at the same instant.

    Proof of work. The unit tests are the 50 methods of this
    class: 34 hand-written seams plus 16 generated
    seen_keep_sec readings. The fuzzing was executed, not just
    the tests written: runner/tools/de_dust_corpus.py grow
    --target mail --rounds 400 --seed 20261152 against the
    banked mail corpus (26 entries) -- mail is the nearest
    de_dust target to the replay surface, which the poll and
    mail doors write on every pass. Result: 400 rounds,
    0 crashes, 0 slow, arcs unchanged at 131, slowest try
    1364 ms; the place-not-age shape did not recur. The grow's
    bookkeeping writes were reverted and are not banked
    (banking is the rigs' hourly job). None of this is exotic:
    it is combinatorics -- systematically trying the
    combinations a hand-written list would never reach, then
    pinning each answer as a test."""

    KEEP = 86400

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.path = os.path.join(self.td.name, "seen.json")
        keep = mock.patch.object(rr, "_SEEN_KEEP", [self.KEEP])
        keep.start()
        self.addCleanup(keep.stop)

    def _save(self, seen, at, keep=None):
        with mock.patch.object(rr.time, "time", return_value=at):
            if keep is None:
                save_seen(self.path, seen)
            else:
                save_seen(self.path, seen, keep_sec=keep)

    def _disk(self):
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)

    def _raw(self, data):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    # -- the count is a backstop, not the rule --

    def test_a_flood_of_exactly_2000_board_keys_keeps_the_job(self):
        self._save({"job-1": True}, T0)
        flood = {f"board:k:{i}": True for i in range(2000)}
        self._save(flood, T0 + 60)
        self.assertIn("job-1", load_seen(self.path))
        self.assertEqual(2001, len(load_seen(self.path)))

    def test_a_flood_of_2001_board_keys_keeps_the_job(self):
        self._save({"job-1": True}, T0)
        flood = {f"board:k:{i}": True for i in range(2001)}
        self._save(flood, T0 + 60)
        self.assertIn("job-1", load_seen(self.path))

    def test_a_flood_of_10000_board_keys_keeps_the_job(self):
        self._save({"job-1": True}, T0)
        flood = {f"board:k:{i}": True for i in range(10000)}
        self._save(flood, T0 + 60)
        self.assertIn("job-1", load_seen(self.path))
        self.assertEqual(10001, len(load_seen(self.path)))

    def test_a_job_key_between_board_floods_survives_both(self):
        self._save({f"board:a:{i}": True for i in range(3000)}, T0)
        self._save({"job-mid": True}, T0 + 30)
        self._save({f"board:b:{i}": True for i in range(3000)}, T0 + 60)
        self.assertIn("job-mid", load_seen(self.path))

    def test_the_ceiling_drops_the_oldest_first_and_logs(self):
        seen = {f"k{i}": T0 + i * 10 for i in range(6)}
        with mock.patch.object(rr, "SEEN_CAP", 3), \
                mock.patch.object(rr, "log") as log:
            self._save(seen, T0 + 100)
        self.assertEqual({"k3", "k4", "k5"}, set(load_seen(self.path)))
        self.assertIn("ceiling", log.call_args[0][0])

    def test_at_the_ceiling_exactly_nothing_is_dropped(self):
        seen = {f"k{i}": T0 + i for i in range(4)}
        with mock.patch.object(rr, "SEEN_CAP", 4), \
                mock.patch.object(rr, "log") as log:
            self._save(seen, T0 + 20)
        self.assertEqual(4, len(load_seen(self.path)))
        self.assertFalse(log.called)

    # -- age, at the horizon's three points --

    def test_an_entry_exactly_at_the_horizon_stays(self):
        self._save({"job-1": True}, T0)
        self._save({}, T0 + self.KEEP)
        self.assertIn("job-1", load_seen(self.path))

    def test_an_entry_one_second_past_the_horizon_leaves(self):
        seen = {"job-1": True}
        self._save(seen, T0)
        seen["job-2"] = True
        self._save(seen, T0 + self.KEEP + 1)
        self.assertEqual({"job-2"}, set(load_seen(self.path)))
        self.assertNotIn("job-1", seen)

    def test_an_entry_one_second_inside_the_horizon_stays(self):
        self._save({"job-1": True}, T0)
        self._save({}, T0 + self.KEEP - 1)
        self.assertIn("job-1", load_seen(self.path))

    def test_a_future_stamped_entry_stays(self):
        self._raw({"job-1": T0 + 10000})
        self._save({"job-2": True}, T0)
        self.assertIn("job-1", load_seen(self.path))
        self.assertEqual(T0 + 10000, self._disk()["job-1"])

    def test_first_recorded_time_survives_repeated_resaves(self):
        self._save({"job-1": True}, T0)
        for at in (T0 + 100, T0 + 200, T0 + 300):
            self._save({"job-1": True}, at)
        self.assertEqual(T0, self._disk()["job-1"])

    def test_a_resave_carrying_a_newer_stamp_does_not_move_it(self):
        self._save({"job-1": True}, T0)
        self._save({"job-1": T0 + 5000}, T0 + 10)
        self.assertEqual(T0, self._disk()["job-1"])

    def test_repeated_saves_at_the_same_instant_are_idempotent(self):
        self._save({"a": True, "b": True}, T0)
        first = self._disk()
        self._save({"a": True, "b": True}, T0)
        self.assertEqual(first, self._disk())

    def test_an_empty_save_wipes_nothing_inside_the_horizon(self):
        self._save({"job-1": True}, T0)
        self._save({}, T0 + 60)
        self.assertEqual({"job-1": T0}, self._disk())

    def test_the_callers_dict_is_normalized_to_keys(self):
        seen = {"job-1": True}
        self._save(seen, T0)
        seen["old"] = True
        with mock.patch.object(rr.time, "time",
                               return_value=T0 + self.KEEP + 5):
            save_seen(self.path, {"fresh": True})
        self._save({"job-1": True, "fresh": True}, T0 + self.KEEP + 5)
        loaded = load_seen(self.path)
        self.assertTrue(all(v is True for v in loaded.values()))

    # -- stamps, flags and old files --

    def test_seen_stamp_plausibility_table(self):
        for value, want in ((True, None), (False, None), (1, None),
                            (0, None), (999_999_999, None),
                            (1_000_000_000, None),
                            (1_000_000_001, 1_000_000_001.0),
                            (T0, T0), ("x", None), (None, None),
                            ([], None), ({"t": 1}, None)):
            self.assertEqual(rr._seen_stamp(value), want, repr(value))

    def test_a_value_just_under_the_plausibility_bound_is_a_flag(self):
        self._save({"job-1": 999_999_999}, T0 + 500)
        self.assertEqual(T0 + 500, self._disk()["job-1"])

    def test_bool_values_are_flags_stamped_at_the_save(self):
        self._save({"yes": True, "no": False}, T0)
        self.assertEqual({"yes": T0, "no": T0}, self._disk())
        self.assertEqual({"yes": True, "no": True},
                         load_seen(self.path))

    def test_an_old_release_list_is_stamped_then_expires(self):
        self._raw(["old-1", "old-2"])
        self._save({"new": True}, T0)
        self.assertEqual({"old-1": T0, "old-2": T0, "new": T0},
                         self._disk())
        self._save({}, T0 + self.KEEP + 1)
        self.assertEqual({}, load_seen(self.path))

    def test_load_stamped_reads_times_and_flags_apart(self):
        self._raw({"a": T0, "b": True, "c": 1})
        self.assertEqual(load_seen(self.path, stamped=True),
                         {"a": T0, "b": True, "c": True})
        self.assertEqual(load_seen(self.path),
                         {"a": True, "b": True, "c": True})

    def test_nonstring_keys_are_stringified_and_nul_keys_dropped(self):
        with mock.patch.object(rr.time, "time", return_value=T0):
            rr._write_seen_unlocked(
                self.path, {7: True, 2.5: True, "a\x00b": True,
                            "plain": True})
        self.assertEqual(set(load_seen(self.path)),
                         {"7", "2.5", "plain"})

    def test_bookended_keys_are_distinct_entries(self):
        keys = {}
        for sym in string.punctuation:
            keys[sym + "job"] = True
            keys["job" + sym] = True
        for sym in ("\t", "\r", "\n"):
            keys[sym + "job"] = True
            keys["job" + sym] = True
        self._save(keys, T0)
        loaded = load_seen(self.path)
        for key in keys:
            self.assertIn(key, loaded, repr(key))

    # -- keep_sec, the save call's own field --

    def test_keep_sec_argument_shortens_the_horizon(self):
        self._save({"job-1": True}, T0)
        self._save({"job-2": True}, T0 + 11, keep=10)
        self.assertEqual({"job-2"}, set(load_seen(self.path)))

    def test_keep_sec_argument_invalid_values_change_nothing(self):
        for bad in (0, -1, "x", True, None):
            with mock.patch.object(rr.time, "time", return_value=T0):
                save_seen(self.path, {"j": True}, keep_sec=bad)
            self.assertEqual(rr._SEEN_KEEP[0], self.KEEP, repr(bad))

    # -- the caller-visible shapes (the second fix) --

    def test_with_seen_file_answers_keys_not_times(self):
        self._save({"job-1": True}, T0)
        got = rr._with_seen_file(self.path, lambda disk: disk)
        self.assertEqual(got, {"job-1": True})
        self.assertEqual(self._disk(), {"job-1": T0})

    def test_with_seen_file_a_non_dict_mutator_result_keeps_disk(self):
        self._save({"job-1": True}, T0)
        got = rr._with_seen_file(self.path, lambda disk: None)
        self.assertEqual(got, {"job-1": True})
        self.assertEqual(self._disk(), {"job-1": T0})

    def test_write_seen_unlocked_returns_nothing(self):
        with mock.patch.object(rr.time, "time", return_value=T0):
            got = rr._write_seen_unlocked(self.path, {"job-1": True})
        self.assertIsNone(got)
        self.assertEqual(self._disk(), {"job-1": T0})

    def test_write_seen_kept_returns_the_stamps_it_wrote(self):
        with mock.patch.object(rr.time, "time", return_value=T0):
            kept = rr._write_seen_kept(self.path,
                                       {"a": True, "b": T0 - 10})
        self.assertEqual(kept, {"a": T0, "b": T0 - 10})

    # -- the file's own weather --

    def test_load_of_missing_and_corrupt_files_is_empty(self):
        self.assertEqual(load_seen(self.path), {})
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual(load_seen(self.path), {})
        self._raw(42)
        self.assertEqual(load_seen(self.path), {})
        self._raw("text")
        self.assertEqual(load_seen(self.path), {})

    def test_load_and_save_with_bad_paths_never_raise(self):
        for bad in (None, "", 7):
            self.assertEqual(load_seen(bad), {})
            save_seen(bad, {"j": True})

    @unittest.skipUnless(os.name == "posix", "POSIX symlink fixture")
    def test_load_does_not_follow_a_symlink(self):
        target = os.path.join(self.td.name, "real.json")
        with open(target, "w", encoding="utf-8") as fh:
            json.dump({"job-1": T0}, fh)
        os.symlink(target, self.path)
        self.assertEqual(load_seen(self.path), {})

    def test_the_disk_file_holds_times_not_flags(self):
        self._save({"a": True, "b": True}, T0)
        disk = self._disk()
        self.assertTrue(all(isinstance(v, float) or isinstance(v, int)
                            for v in disk.values()))
        self.assertEqual(set(disk), {"a", "b"})

    def test_tiny_windows_all_read_as_the_day_floor(self):
        for window in (1, 60, 3599, 3600, 43200, 86099):
            self.assertEqual(seen_keep_sec({"max_job_age_sec": window}),
                             86400, window)

    def test_save_seen_with_a_non_dict_seen_writes_disk_only(self):
        self._save({"job-1": True}, T0)
        with mock.patch.object(rr.time, "time", return_value=T0 + 5):
            save_seen(self.path, ["not", "a", "dict"])
        self.assertIn("job-1", load_seen(self.path))


def _make_keep_test(cfg, want):
    def run(self):
        self.assertEqual(seen_keep_sec(cfg), want, repr(cfg))
    return run


# 16 generated readings of the one governing config field,
# max_job_age_sec: the window plus 300, a day at least.
_KEEP_CASES = (
    ({}, 86400),
    (None, 86400),
    ({"max_job_age_sec": 60}, 86400),
    ({"max_job_age_sec": 0}, 86400),
    ({"max_job_age_sec": -5}, 86400),
    ({"max_job_age_sec": "x"}, 86400),
    ({"max_job_age_sec": "3600"}, 86400),
    ({"max_job_age_sec": 2.5}, 86400),
    ({"max_job_age_sec": True}, 86400),
    ({"max_job_age_sec": 86100}, 86400),
    ({"max_job_age_sec": 86101}, 86401),
    ({"max_job_age_sec": 86400}, 86700),
    ({"max_job_age_sec": 7 * 86400}, 7 * 86400 + 300),
    ({"max_job_age_sec": 30 * 86400}, 30 * 86400 + 300),
    ({"other_field": 10 ** 9}, 86400),
    ({"max_job_age_sec": 10 ** 6}, 10 ** 6 + 300),
)
for _i, (_cfg, _want) in enumerate(_KEEP_CASES):
    setattr(ReplayCacheAgeShotgunTest, f"test_keep_reading_{_i:02d}",
            _make_keep_test(_cfg, _want))
del _i, _cfg, _want


if __name__ == "__main__":
    unittest.main()
