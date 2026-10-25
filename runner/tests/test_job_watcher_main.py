#!/usr/bin/env python3
"""Queue A: `job_watcher.main`'s live and delivery legs
(coverage run 40183585961: 10 lines on both platforms).

The shape hunts drive decide(); main's own legs never
ran: the live read through --runner-dir (the manifest
copy, the tunables injection, read_live itself), the
truncation notice when the retained store outgrows one
pass, and the delivery discipline -- local delivery not
set up is exit 2, and a partial delivery is exit 2 with
the state deliberately NOT saved, so the next pass
reports the same jobs again instead of losing them.
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

EXT_DIR = os.path.join(REPO, "runner", "extensions",
                       "job-watcher")


def _load():
    spec = importlib.util.spec_from_file_location(
        "job_watcher_main", os.path.join(EXT_DIR,
                                         "job_watcher.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


JW = _load()
NOW = time.time()


def _manifest(**tunables):
    with open(os.path.join(EXT_DIR, "extension.json"),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    manifest.setdefault("tunables", {}).update(tunables)
    return manifest


def _retained_record(job_id, saved_at, exit_code=1):
    return {"job_id": job_id, "kind": "exec",
            "script": "backup.sh", "exit_code": exit_code,
            "saved_at": saved_at, "duration_sec": 3.0,
            "stderr": "boom\n"}


def _observation(job_id, saved_at, exit_code=1):
    """The shape decide() reads -- what _record_observation
    makes of a retained record, key included."""
    return {"job_id": job_id,
            "key": JW.job_key("exec", "backup.sh"),
            "kind": "exec", "label": "backup.sh",
            "exit_code": exit_code, "saved_at": saved_at,
            "duration_sec": 3.0, "error": "boom"}


class MainLiveAndDeliveryTest(unittest.TestCase):
    def _main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = JW.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def _write(self, path, payload):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return path

    def _runner_dir(self, d, count=3):
        base = os.path.join(d, "runner")
        retained = os.path.join(base, "retained")
        os.makedirs(retained)
        for i in range(count):
            self._write(
                os.path.join(retained, "job-%d.json" % i),
                _retained_record("job-%d" % i, NOW - 100 + i))
        return base

    def test_the_live_read_through_runner_dir(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._runner_dir(d)
            manifest = self._write(
                os.path.join(d, "extension.json"), _manifest())
            state = os.path.join(d, "state.json")
            rc, out, _err = self._main(
                ["--manifest", manifest, "--state", state,
                 "--runner-dir", base])
            self.assertEqual(rc, 0)
            alerts = [json.loads(line)
                      for line in out.splitlines() if line.strip()]
            self.assertEqual(len(alerts), 1)
            self.assertEqual(alerts[0]["signal"],
                             "job_failing_repeatedly")
            with open(state, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(len(saved["seen"]), 3)

    def test_a_truncated_store_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._runner_dir(d)
            manifest = self._write(
                os.path.join(d, "extension.json"),
                _manifest(max_records_per_pass=1))
            rc, _out, err = self._main(
                ["--manifest", manifest,
                 "--state", os.path.join(d, "state.json"),
                 "--runner-dir", base])
            self.assertEqual(rc, 0)
            self.assertIn("2 retained record(s) beyond "
                          "max_records_per_pass were not read",
                          err)

    def test_local_delivery_not_set_up_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = self._write(
                os.path.join(d, "extension.json"), _manifest())
            readings = self._write(
                os.path.join(d, "readings.json"),
                {"now": NOW, "records": [
                    _observation("job-%d" % i, NOW - 10 + i)
                    for i in range(3)]})
            rc, _out, err = self._main(
                ["--manifest", manifest,
                 "--state", os.path.join(d, "state.json"),
                 "--readings", readings,
                 "--local-dir", d,
                 "--secret-env", "HP_JW_UNSET_SECRET"])
            self.assertEqual(rc, 2)
            self.assertIn("no signing secret", err)

    def test_a_partial_delivery_saves_no_state(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = self._write(
                os.path.join(d, "extension.json"), _manifest())
            readings = self._write(
                os.path.join(d, "readings.json"),
                {"now": NOW, "records": [
                    _observation("job-%d" % i, NOW - 10 + i)
                    for i in range(3)]})
            blocker = self._write(
                os.path.join(d, "blocker"), {"x": 1})
            state = os.path.join(d, "state.json")
            saved_env = os.environ.get(
                "HOMING_PIGEON_SENSOR_SECRET")
            os.environ["HOMING_PIGEON_SENSOR_SECRET"] = \
                "jw-test-secret-0123456789abcdef"
            try:
                rc, _out, err = self._main(
                    ["--manifest", manifest, "--state", state,
                     "--readings", readings,
                     "--local-dir", blocker])
            finally:
                if saved_env is None:
                    os.environ.pop(
                        "HOMING_PIGEON_SENSOR_SECRET", None)
                else:
                    os.environ["HOMING_PIGEON_SENSOR_SECRET"] = \
                        saved_env
            self.assertEqual(rc, 2)
            self.assertIn("not delivered; state not saved", err)
            self.assertFalse(os.path.exists(state))


class EmptyRunsJobLegTest(unittest.TestCase):
    """Queue A refill: decide's empty-history
    skip (coverage run 40189711740: line 513).
    A job the state knows but that has no runs
    yet is passed over in silence -- there is
    nothing to judge, and no signal may file
    on an empty history.
    """

    def test_a_job_with_no_runs_files_nothing(self):
        state = {"seen": {},
                 "jobs": {"backup": {"kind": "exec",
                                     "label": "backup",
                                     "runs": [],
                                     "fired": {}}},
                 "cluster_fired": None}
        alerts, new_state = JW.decide(
            {"now": NOW, "records": []}, _manifest(), state)
        self.assertEqual(alerts, [])
        self.assertEqual(
            new_state["jobs"]["backup"]["runs"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
