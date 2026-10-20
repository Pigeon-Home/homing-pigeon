"""Tests for the Oracle's canary tripwire watch. Canaries are plain
files, so the real helpers run against temp dirs on every platform;
no platform patching or subprocess mocking needed."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runner import runner as R


def _canary_path(base, name):
    return os.path.join(base, "canaries", name)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class CanaryPlantTest(unittest.TestCase):
    def test_first_run_plants_and_reports(self):
        tmp = tempfile.mkdtemp()
        out = R._canary_watch(tmp)
        self.assertIn("canaries planted", out)
        for name in R._CANARY_NAMES:
            self.assertTrue(os.path.exists(_canary_path(tmp, name)))
        self.assertTrue(os.path.exists(
            os.path.join(tmp, "canary-watch.json")))

    def test_planted_files_carry_marker_and_unique_tokens(self):
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        tokens = []
        for name in R._CANARY_NAMES:
            body = _read(_canary_path(tmp, name))
            self.assertIn("tripwire", body)
            token_lines = [ln for ln in body.splitlines()
                           if ln.startswith("canary-token:")]
            self.assertEqual(len(token_lines), 1)
            tokens.append(token_lines[0])
        self.assertEqual(len(set(tokens)), len(R._CANARY_NAMES))

    def test_snapshot_records_hash_and_existence(self):
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        with open(os.path.join(tmp, "canary-watch.json"),
                  encoding="utf-8") as fh:
            snap = json.load(fh)
        self.assertEqual(set(snap["files"]), set(R._CANARY_NAMES))
        for entry in snap["files"].values():
            self.assertTrue(entry["exists"])
            self.assertTrue(entry["hash"])


class CanaryQuietTest(unittest.TestCase):
    def test_untouched_is_one_quiet_line(self):
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        out = R._canary_watch(tmp)
        self.assertNotIn("TRIPPED", out)
        self.assertIn("untouched", out)

    def test_steady_state_stays_quiet(self):
        tmp = tempfile.mkdtemp()
        for _ in range(3):
            out = R._canary_watch(tmp)
        self.assertNotIn("TRIPPED", out)
        self.assertIn("(%d canaries untouched)" % len(R._CANARY_NAMES), out)


class CanaryTripTest(unittest.TestCase):
    def test_crlf_rewrite_is_not_a_trip(self):
        # Regression: on Windows the original plant wrote text mode, so
        # the file landed on disk with CRLF endings while the snapshot
        # hashed the LF string — every canary read as modified forever
        # (build-windows CI failure, 2026-10-16). Line-ending
        # translation alone must stay quiet, on every platform.
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        for name in R._CANARY_NAMES:
            path = _canary_path(tmp, name)
            with open(path, "rb") as fh:
                data = fh.read()
            # Fold first. Replacing bare \n in a file that is already
            # CRLF turns \r\n into \r\r\n, which is a real content
            # change and trips. That is what failed build-windows on
            # the v3.11.14 tag run. Write the other ending of the
            # same text so the rewrite is translation only.
            lf = data.replace(b"\r\n", b"\n")
            other = lf if b"\r\n" in data else lf.replace(b"\n", b"\r\n")
            self.assertNotEqual(other, data)
            with open(path, "wb") as fh:
                fh.write(other)
        out = R._canary_watch(tmp)
        self.assertNotIn("TRIPPED", out)
        self.assertIn("untouched", out)

    def test_content_change_with_crlf_still_trips(self):
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        path = _canary_path(tmp, "passwords.txt")
        with open(path, "rb") as fh:
            data = fh.read().replace(b"\n", b"\r\n")
        with open(path, "wb") as fh:
            fh.write(data + b"hunter2\r\n")
        out = R._canary_watch(tmp)
        self.assertIn("TRIPPED", out)
        self.assertIn("passwords.txt", out)

    def test_modify_trips_by_name(self):
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        path = _canary_path(tmp, "passwords.txt")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("hunter2\n")
        out = R._canary_watch(tmp)
        self.assertIn("TRIPPED", out)
        self.assertIn("passwords.txt", out)
        self.assertIn("modified", out)
        self.assertIn("(%d canaries untouched)"
                      % (len(R._CANARY_NAMES) - 1), out)

    def test_delete_trips_by_name(self):
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        os.remove(_canary_path(tmp, "api-keys.txt"))
        out = R._canary_watch(tmp)
        self.assertIn("TRIPPED", out)
        self.assertIn("api-keys.txt", out)
        self.assertIn("missing", out)

    def test_deleting_whole_canary_dir_trips_everything(self):
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        import shutil
        shutil.rmtree(os.path.join(tmp, "canaries"))
        out = R._canary_watch(tmp)
        for name in R._CANARY_NAMES:
            self.assertIn(name, out)
        self.assertEqual(out.count("TRIPPED"), len(R._CANARY_NAMES))

    def test_trip_persists_until_restored(self):
        # The snapshot must not be re-baselined over a trip: a modified
        # canary keeps reporting TRIPPED on the next look, and only
        # restoring the original content clears it.
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        path = _canary_path(tmp, "backup-codes.txt")
        original = _read(path)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("tampered\n")
        self.assertIn("TRIPPED", R._canary_watch(tmp))
        self.assertIn("TRIPPED", R._canary_watch(tmp))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(original)
        out = R._canary_watch(tmp)
        self.assertNotIn("TRIPPED", out)
        self.assertIn("untouched", out)


class CanarySnapshotTest(unittest.TestCase):
    def test_corrupt_snapshot_rebaselines_without_tripping(self):
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        with open(os.path.join(tmp, "canary-watch.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{not json")
        out = R._canary_watch(tmp)
        self.assertIn("canaries planted", out)
        self.assertNotIn("TRIPPED", out)

    def test_missing_snapshot_adopts_existing_files(self):
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        os.remove(os.path.join(tmp, "canary-watch.json"))
        out = R._canary_watch(tmp)
        self.assertNotIn("TRIPPED", out)
        # And the adopted baseline tracks later edits.
        path = _canary_path(tmp, "passwords.txt")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("x")
        self.assertIn("TRIPPED", R._canary_watch(tmp))

    def test_unusable_base_dir_degrades_to_nothing(self):
        self.assertEqual(R._canary_watch(""), "")
        self.assertEqual(R._canary_watch(None), "")
        self.assertEqual(R._canary_watch(123), "")
        tmp = tempfile.mkdtemp()
        a_file = os.path.join(tmp, "afile")
        with open(a_file, "w", encoding="utf-8") as fh:
            fh.write("x")
        self.assertEqual(R._canary_watch(os.path.join(a_file, "sub")), "")

    def test_output_is_bounded(self):
        tmp = tempfile.mkdtemp()
        out = R._canary_watch(tmp, max_chars=10)
        self.assertLessEqual(len(out), 10)


class OracleContextCanaryTest(unittest.TestCase):
    def test_context_includes_canary_section(self):
        tmp = tempfile.mkdtemp()
        blob = R.oracle_context(tmp)
        self.assertIn("Canary watch", blob)
        self.assertIn("canaries planted", blob)

    def test_context_reports_trip(self):
        tmp = tempfile.mkdtemp()
        R.oracle_context(tmp)
        path = _canary_path(tmp, "passwords.txt")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("peeked\n")
        blob = R.oracle_context(tmp)
        self.assertIn("TRIPPED", blob)
        self.assertIn("passwords.txt", blob)

    def test_watch_false_excludes_and_does_not_plant(self):
        tmp = tempfile.mkdtemp()
        blob = R.oracle_context(tmp, watch=False)
        self.assertNotIn("Canary watch", blob)
        self.assertFalse(os.path.exists(os.path.join(tmp, "canaries")))

    def test_canary_yields_when_job_output_fills_the_budget(self):
        # max_chars is a real cap: when the retained job output alone
        # saturates it, the canary section must not push past it.
        tmp = tempfile.mkdtemp()
        retained = os.path.join(tmp, "retained")
        os.makedirs(retained)
        with open(os.path.join(retained, "big.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"job_id": "big", "kind": "exec",
                       "script": "s" * 2000, "stdout": "o" * 5000,
                       "exit_code": 0, "saved_at": 1}, fh)
        blob = R.oracle_context(tmp, max_chars=500)
        self.assertLessEqual(len(blob), 500)
        self.assertNotIn("Canary watch", blob)
        self.assertEqual(R.oracle_context(tmp, max_chars=-5), "")


class AskSystemCanaryTest(unittest.TestCase):
    def test_instructions_document_the_canary_watch(self):
        self.assertIn("Canary watch", R.ASK_SYSTEM)
        self.assertIn("Canary watch", R.ASK_AGENT_SYSTEM)
        self.assertIn("TRIPPED", R.ASK_SYSTEM)
        self.assertIn("TRIPPED", R.ASK_AGENT_SYSTEM)
        self.assertIn("Never invent a trip", R.ASK_SYSTEM)
        self.assertIn("Never invent a trip", R.ASK_AGENT_SYSTEM)


if __name__ == "__main__":
    unittest.main()
