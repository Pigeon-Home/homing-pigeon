"""The retained store: save / load / prune / expire branch coverage.

The full-suite coverage run on 96c1748 left the retained lifecycle's
failure branches unexercised: save_retained's cleanup paths (a failed
makedirs, a chmod that raises, an error while the fd is still owned,
the temp file's removal), load_retained's containment refusal, and
prune_retained's actual removal. These tests inject the failures
directly and pin what the store guarantees anyway: nothing escapes as
an exception, no partial record is left behind, a planted symlink is
never written through, and expiry is strict about its boundary.
"""

import json
import os
import tempfile
import threading
import time
import unittest
import unittest.mock

from runner import runner as R


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        self.rdir = os.path.join(self.base, "retained")

    def tearDown(self):
        self._tmp.cleanup()

    def record_path(self, job_id):
        return os.path.join(self.rdir, job_id + ".json")


class SaveRetainedTest(_Base):
    def test_roundtrip_preserves_the_payload(self):
        payload = {"stdout": "héllo", "nested": {"a": [1, 2, {"b": None}]},
                   "exit_code": 3, "saved_at": 123.5}
        R.save_retained(self.base, "job-1", payload)
        self.assertEqual(R.load_retained(self.base, "job-1"), payload)

    def test_non_dict_payload_is_stored_as_an_empty_record(self):
        R.save_retained(self.base, "job-2", ["not", "a", "dict"])
        self.assertEqual(R.load_retained(self.base, "job-2"), {})

    def test_unsafe_job_ids_are_dropped_not_written(self):
        for bad in ("..", ".", "../evil", "a/b", "a b", "", "a;b", "a\\b"):
            R.save_retained(self.base, bad, {"x": 1})
        for bad in (None, 123, b"bytes"):
            R.save_retained(self.base, bad, {"x": 1})
        self.assertFalse(os.path.exists(self.rdir))

    def test_unusable_base_dir_is_a_no_op(self):
        for bad in (None, "", 42):
            R.save_retained(bad, "job-3", {"x": 1})  # must not raise

    def test_makedirs_failure_drops_the_record_silently(self):
        with unittest.mock.patch.object(
                os, "makedirs", side_effect=OSError("read-only fs")):
            R.save_retained(self.base, "job-4", {"x": 1})  # must not raise
        self.assertFalse(os.path.exists(self.record_path("job-4")))

    def test_chmod_failure_still_saves_the_record(self):
        with unittest.mock.patch.object(
                os, "chmod", side_effect=OSError("no perms")):
            R.save_retained(self.base, "job-5", {"x": 9})
        self.assertEqual(R.load_retained(self.base, "job-5"), {"x": 9})

    def test_error_while_fd_is_owned_closes_and_cleans_up(self):
        # _json_safe runs after os.open: the fd is still owned by
        # save_retained, which must close it and remove the temp file.
        with unittest.mock.patch.object(
                R, "_json_safe", side_effect=TypeError("boom")):
            R.save_retained(self.base, "job-6", {"x": 1})  # must not raise
        self.assertEqual(os.listdir(self.rdir), [])

    def test_replace_failure_keeps_the_previous_record(self):
        R.save_retained(self.base, "job-7", {"v": "old"})
        with unittest.mock.patch.object(
                os, "replace", side_effect=OSError("cross-device")):
            R.save_retained(self.base, "job-7", {"v": "new"})
        self.assertEqual(R.load_retained(self.base, "job-7"), {"v": "old"})
        self.assertEqual(os.listdir(self.rdir), ["job-7.json"])

    def test_nan_infinity_and_circular_values_become_null(self):
        payload = {"nan": float("nan"), "inf": float("inf")}
        payload["self"] = payload
        R.save_retained(self.base, "job-8", payload)
        loaded = R.load_retained(self.base, "job-8")
        self.assertEqual(loaded, {"nan": None, "inf": None, "self": None})

    @unittest.skipUnless(os.name == "posix", "mode bits are POSIX")
    def test_record_file_is_mode_0600(self):
        R.save_retained(self.base, "job-9", {"x": 1})
        mode = os.stat(self.record_path("job-9")).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symlink")
    def test_planted_temp_symlink_is_unlinked_never_followed(self):
        # The stale-temp unlink clears a planted link before the
        # O_EXCL | O_NOFOLLOW create, so the guarantee is narrow and
        # specific: the link's target is never written through, and
        # the save itself proceeds as a fresh file.
        os.makedirs(self.rdir)
        victim = os.path.join(self.base, "victim.txt")
        with open(victim, "w", encoding="utf-8") as f:
            f.write("precious")
        tmp = self.record_path("job-10") + ".tmp." + str(threading.get_ident())
        os.symlink(victim, tmp)
        R.save_retained(self.base, "job-10", {"x": 1})
        with open(victim, encoding="utf-8") as f:
            self.assertEqual(f.read(), "precious")
        self.assertEqual(R.load_retained(self.base, "job-10"), {"x": 1})

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symlink")
    def test_record_symlink_is_replaced_not_followed(self):
        os.makedirs(self.rdir)
        victim = os.path.join(self.base, "victim2.txt")
        with open(victim, "w", encoding="utf-8") as f:
            f.write("precious")
        os.symlink(victim, self.record_path("job-11"))
        R.save_retained(self.base, "job-11", {"x": 2})
        with open(victim, encoding="utf-8") as f:
            self.assertEqual(f.read(), "precious")
        self.assertFalse(os.path.islink(self.record_path("job-11")))
        self.assertEqual(R.load_retained(self.base, "job-11"), {"x": 2})

    def test_concurrent_saves_of_one_id_leave_a_whole_record(self):
        payloads = [{"writer": i, "blob": "x" * 500} for i in range(2)]
        threads = [threading.Thread(
            target=R.save_retained, args=(self.base, "job-12", p))
            for p in payloads]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertIn(R.load_retained(self.base, "job-12"), payloads)


class LoadRetainedTest(_Base):
    def test_missing_record_is_none(self):
        self.assertIsNone(R.load_retained(self.base, "nope"))

    def test_corrupt_json_is_none(self):
        os.makedirs(self.rdir)
        with open(self.record_path("bad"), "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertIsNone(R.load_retained(self.base, "bad"))

    def test_non_dict_json_is_none(self):
        os.makedirs(self.rdir)
        with open(self.record_path("arr"), "w", encoding="utf-8") as f:
            json.dump([1, 2, 3], f)
        self.assertIsNone(R.load_retained(self.base, "arr"))

    def test_unsafe_id_is_none(self):
        self.assertIsNone(R.load_retained(self.base, "../secret"))

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symlink")
    def test_symlinked_record_is_refused(self):
        real = os.path.join(self.base, "real.json")
        with open(real, "w", encoding="utf-8") as f:
            json.dump({"x": 1}, f)
        os.makedirs(self.rdir)
        os.symlink(real, self.record_path("link"))
        self.assertIsNone(R.load_retained(self.base, "link"))

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symlink")
    def test_symlinked_retained_dir_loads_through_resolution(self):
        # Containment is evaluated after realpath on both sides, so a
        # retained dir that is itself a symlink resolves consistently
        # and loads; what is refused is a record that escapes the
        # resolved dir (the islink check above, the commonpath check).
        elsewhere = os.path.join(self.base, "elsewhere")
        os.makedirs(elsewhere)
        with open(os.path.join(elsewhere, "job.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"x": 1}, f)
        os.symlink(elsewhere, self.rdir)
        self.assertEqual(R.load_retained(self.base, "job"), {"x": 1})

    def test_commonpath_value_error_is_refused(self):
        R.save_retained(self.base, "job-13", {"x": 1})
        with unittest.mock.patch.object(
                os.path, "commonpath", side_effect=ValueError("mixed")):
            self.assertIsNone(R.load_retained(self.base, "job-13"))

    # Case is part of a job id. A case-insensitive filesystem
    # (Windows NTFS, a default macOS volume) answers a load for
    # "bm-RET-Y" with the record stored for "bm-ret-y" unless the
    # store checks the directory entry's exact name: the Germany
    # rig's grow filed exactly that as race_state crash
    # 9b26d146d86a0e08 (2026-11-01), a retained record returned
    # for a different job id than the one it was saved under.
    def test_case_variant_ids_do_not_alias_the_stored_record(self):
        R.save_retained(self.base, "bm-ret-y", {"v": "bm-ret-y"})
        self.assertEqual(R.load_retained(self.base, "bm-ret-y"),
                         {"v": "bm-ret-y"})
        for variant in ("bm-RET-Y", "BM-RET-Y", "bm-ret-Y", "Bm-Ret-Y"):
            self.assertIsNone(R.load_retained(self.base, variant),
                              variant)

    def test_case_variant_saves_do_not_alias_either_way(self):
        R.save_retained(self.base, "CaseJob-1", {"v": "upper-first"})
        self.assertIsNone(R.load_retained(self.base, "casejob-1"))
        self.assertIsNone(R.load_retained(self.base, "CASEJOB-1"))
        self.assertEqual(R.load_retained(self.base, "CaseJob-1"),
                         {"v": "upper-first"})

    def _load_under_case_insensitive_surface(self, job_id, payload):
        # Simulate the one seam a case-insensitive filesystem
        # changes: isfile and the read itself succeed for a name
        # that differs only in case. The directory listing still
        # carries the stored name's real case, as NTFS/APFS do.
        with unittest.mock.patch.object(
                os.path, "isfile", return_value=True), \
                unittest.mock.patch.object(
                    R, "_read_json_dict", return_value=dict(payload)):
            return R.load_retained(self.base, job_id)

    def test_case_variant_load_is_none_on_a_case_insensitive_fs(self):
        R.save_retained(self.base, "bm-ret-y", {"v": "bm-ret-y"})
        self.assertIsNone(self._load_under_case_insensitive_surface(
            "bm-RET-Y", {"v": "bm-ret-y"}))

    def test_exact_case_load_reads_on_a_case_insensitive_fs(self):
        R.save_retained(self.base, "bm-ret-y", {"v": "bm-ret-y"})
        self.assertEqual(self._load_under_case_insensitive_surface(
            "bm-ret-y", {"v": "bm-ret-y"}), {"v": "bm-ret-y"})


class PruneRetainedTest(_Base):
    def _plant(self, name, age_days):
        os.makedirs(self.rdir, exist_ok=True)
        path = os.path.join(self.rdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{}")
        when = time.time() - age_days * 86400
        os.utime(path, (when, when))
        return path

    def test_old_records_are_removed_and_counted(self):
        old = self._plant("old.json", 10)
        fresh = self._plant("fresh.json", 1)
        self.assertEqual(R.prune_retained(self.base, 7), 1)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(fresh))

    def test_missing_dir_removes_nothing(self):
        self.assertEqual(R.prune_retained(self.base, 7), 0)

    def test_unusable_days_remove_nothing(self):
        old = self._plant("old.json", 30)
        for days in ("x", None, 0, -3):
            self.assertEqual(R.prune_retained(self.base, days), 0)
        self.assertTrue(os.path.exists(old))

    def test_unusable_base_removes_nothing(self):
        self.assertEqual(R.prune_retained(None, 7), 0)
        self.assertEqual(R.prune_retained("", 7), 0)

    def test_a_directory_entry_is_skipped_not_fatal(self):
        subdir = os.path.join(self.rdir, "sub")
        self._plant("old.json", 10)
        os.makedirs(subdir)
        when = time.time() - 10 * 86400
        os.utime(subdir, (when, when))
        self.assertEqual(R.prune_retained(self.base, 7), 1)
        self.assertTrue(os.path.isdir(subdir))


class RetainedExpiredTest(unittest.TestCase):
    NOW = time.time()

    def test_non_dict_inputs_are_expired(self):
        self.assertTrue(R.retained_expired(None, {}))
        self.assertTrue(R.retained_expired({}, None))
        self.assertTrue(R.retained_expired([], []))

    def test_default_window_is_seven_days(self):
        old = {"saved_at": self.NOW - 8 * 86400}
        fresh = {"saved_at": self.NOW - 6 * 86400}
        self.assertTrue(R.retained_expired(old, {}))
        self.assertFalse(R.retained_expired(fresh, {}))

    def test_zero_days_means_no_expiry(self):
        # 0 is the operator turning retention off: no record is too
        # old. (The two readers of this key once disagreed about 0 --
        # retained_expired read it as the 7-day default through the
        # `or 7` idiom while prune_retained read it as "prune
        # nothing". Both now take the window from _retention_days.)
        for age_days in (0, 7, 8, 365):
            record = {"saved_at": self.NOW - age_days * 86400}
            self.assertFalse(R.retained_expired(
                record, {"output_retention_days": 0}),
                f"age {age_days}d must not expire at 0 days")
        self.assertFalse(R.retained_expired(
            {"saved_at": 1}, {"output_retention_days": 0}))

    def test_negative_days_never_expire(self):
        ancient = {"saved_at": 1}
        self.assertFalse(R.retained_expired(
            ancient, {"output_retention_days": -5}))
        self.assertFalse(R.retained_expired(
            ancient, {"output_retention_days": -1}))

    def test_zero_as_a_string_means_no_expiry(self):
        ancient = {"saved_at": 1}
        self.assertFalse(R.retained_expired(
            ancient, {"output_retention_days": "0"}))

    def test_absent_and_none_days_use_the_seven_day_default(self):
        old = {"saved_at": self.NOW - 8 * 86400}
        fresh = {"saved_at": self.NOW - 6 * 86400}
        for cfg in ({}, {"output_retention_days": None}):
            self.assertTrue(R.retained_expired(old, cfg))
            self.assertFalse(R.retained_expired(fresh, cfg))

    def test_retention_days_reading(self):
        # The shared reader's table: absent/None/garbage fall back
        # to 7; explicit values pass through, 0 and negatives
        # included.
        cases = [
            ({}, 7),
            ({"output_retention_days": None}, 7),
            ({"output_retention_days": "soon"}, 7),
            ({"output_retention_days": float("inf")}, 7),
            ({"output_retention_days": float("nan")}, 7),
            ({"output_retention_days": 7}, 7),
            ({"output_retention_days": 3}, 3),
            ({"output_retention_days": "3"}, 3),
            ({"output_retention_days": 0}, 0),
            ({"output_retention_days": "0"}, 0),
            ({"output_retention_days": -5}, -5),
            (None, 7),
            ("nope", 7),
        ]
        for cfg, expected in cases:
            self.assertEqual(R._retention_days(cfg), expected, repr(cfg))

    def test_expired_and_prune_agree_about_zero(self):
        # The agreement itself, through the production path: the
        # window poll_once derives from the config feeds
        # prune_retained, and retained_expired reads the same
        # config. At 0, neither reader may drop a record, at any age.
        cfg = {"output_retention_days": 0}
        with tempfile.TemporaryDirectory() as base:
            rdir = os.path.join(base, "retained")
            os.makedirs(rdir)
            for age_days in (0, 7, 8, 365):
                name = f"job{age_days}.json"
                path = os.path.join(rdir, name)
                with open(path, "w", encoding="utf-8") as f:
                    f.write("{}")
                when = time.time() - age_days * 86400
                os.utime(path, (when, when))
                record = {"saved_at": when}
                self.assertFalse(R.retained_expired(record, cfg))
            self.assertEqual(
                R.prune_retained(base, R._retention_days(cfg)), 0)
            self.assertEqual(len(os.listdir(rdir)), 4)

    def test_expired_and_prune_agree_about_a_positive_window(self):
        cfg = {"output_retention_days": 7}
        with tempfile.TemporaryDirectory() as base:
            rdir = os.path.join(base, "retained")
            os.makedirs(rdir)
            path = os.path.join(rdir, "old.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{}")
            when = time.time() - 8 * 86400
            os.utime(path, (when, when))
            self.assertTrue(R.retained_expired({"saved_at": when}, cfg))
            self.assertEqual(
                R.prune_retained(base, R._retention_days(cfg)), 1)
            self.assertFalse(os.path.exists(path))

    def test_garbage_days_fall_back_to_seven(self):
        old = {"saved_at": self.NOW - 8 * 86400}
        self.assertTrue(R.retained_expired(
            old, {"output_retention_days": "soon"}))

    def test_missing_or_garbage_saved_at_is_expired(self):
        self.assertTrue(R.retained_expired({}, {}))
        self.assertTrue(R.retained_expired({"saved_at": "abc"}, {}))
        self.assertTrue(R.retained_expired({"saved_at": None}, {}))

    def test_nan_and_infinite_saved_at_are_expired(self):
        self.assertTrue(R.retained_expired({"saved_at": float("nan")}, {}))
        self.assertTrue(R.retained_expired({"saved_at": float("inf")}, {}))

    def test_numeric_string_saved_at_is_evaluated(self):
        fresh = {"saved_at": str(self.NOW - 60)}
        self.assertFalse(R.retained_expired(fresh, {}))

    def test_boundary_is_strictly_greater(self):
        now = time.time()
        inside = {"saved_at": now - 7 * 86400 + 120}
        outside = {"saved_at": now - 7 * 86400 - 120}
        self.assertFalse(R.retained_expired(inside, {}))
        self.assertTrue(R.retained_expired(outside, {}))


if __name__ == "__main__":
    unittest.main()
