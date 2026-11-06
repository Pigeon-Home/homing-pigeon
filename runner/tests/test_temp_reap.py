"""Temp reaping: the runner reaps its per-job workspaces.

The Germany rig repair of 2026-11-06 weighed 134.8 GB of
accumulated temp on a box whose Python processes run as
SYSTEM: per-job workspaces and temp bases that nothing ever
removed. The record is
docs/infrastructure-documents/proofs/temp-reap.md.

These tests pin the product behavior:

- execute_job removes base_dir/work/<job_id> when the job
  finishes, on the success, failure and refusal paths alike.
- A workspace remediation seized (quarantine MOVES it out)
  is not the reap's business: the reap of the old path is a
  no-op and the seized copy survives.
- The startup orphan sweep (reap_work_orphans) removes only
  direct children of base_dir/work/ that are real
  directories, named like a job_id, older than the retention
  age in the config key work_retention_sec (default 7 days;
  0 disables; an unusable value reads as the default and is
  named by the startup line through the defaulted-keys
  registry). The sweep is bounded.
"""
import base64
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402

DAY = 86400


class _Base(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-reap-test-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.work_root = os.path.join(self.base, "work")

    def work_dir(self, job_id):
        return os.path.join(self.work_root, job_id)

    def plant(self, name, age_sec, is_dir=True):
        path = os.path.join(self.work_root, name)
        if is_dir:
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, "staged.txt"), "w") as fh:
                fh.write("x")
        else:
            os.makedirs(self.work_root, exist_ok=True)
            with open(path, "w") as fh:
                fh.write("x")
        when = time.time() - age_sec
        os.utime(path, (when, when))
        return path


class ExecuteJobReapTest(_Base):
    def exec_job(self, job_id, script="print('hi')"):
        return R.execute_job(
            {}, {"job_id": job_id, "kind": "exec", "script": script,
                 "interpreter": [sys.executable]}, self.base)

    def test_successful_exec_reaps_its_work_dir(self):
        r = self.exec_job("reap-ok")
        self.assertEqual(r["exit_code"], 0)
        self.assertFalse(os.path.exists(self.work_dir("reap-ok")))

    def test_outputs_are_collected_before_the_reap(self):
        r = R.execute_job(
            {}, {"job_id": "reap-outputs", "kind": "exec",
                 "script": "open('out.txt', 'w').write('payload')",
                 "interpreter": [sys.executable],
                 "outputs": ["out.txt"]}, self.base)
        self.assertEqual(r["exit_code"], 0)
        self.assertEqual(
            base64.b64decode(r["outputs"][0]["content_b64"]), b"payload")
        self.assertFalse(os.path.exists(self.work_dir("reap-outputs")))

    def test_ping_reaps_its_work_dir(self):
        r = R.execute_job({}, {"job_id": "reap-ping", "kind": "ping"},
                          self.base)
        self.assertEqual(r["stdout"], "pong")
        self.assertFalse(os.path.exists(self.work_dir("reap-ping")))

    def test_refused_job_reaps_its_work_dir(self):
        job = {"job_id": "reap-refused", "kind": "exec",
               "script": "print('x')", "interpreter": [sys.executable],
               "files": [{"name": "a.txt",
                          "content_b64": base64.b64encode(b"x").decode(),
                          "sha384": "0" * 96}]}
        with self.assertRaises(R.JobRejected):
            R.execute_job({}, job, self.base)
        self.assertFalse(os.path.exists(self.work_dir("reap-refused")))

    def test_unknown_kind_reaps_its_work_dir(self):
        with self.assertRaises(R.JobRejected):
            R.execute_job({}, {"job_id": "reap-nope", "kind": "nope"},
                          self.base)
        self.assertFalse(os.path.exists(self.work_dir("reap-nope")))

    def test_failed_download_reaps_its_work_dir(self):
        job = {"job_id": "reap-dl", "kind": "exec",
               "script": "print('x')", "interpreter": [sys.executable],
               "files": [{"name": "f.bin",
                          "url": "https://example.invalid/f"}]}
        with mock.patch.object(R, "download",
                               side_effect=OSError("boom")):
            with self.assertRaises(RuntimeError):
                R.execute_job({}, job, self.base)
        self.assertFalse(os.path.exists(self.work_dir("reap-dl")))

    def test_timed_out_job_reaps_its_work_dir(self):
        r = R.execute_job(
            {}, {"job_id": "reap-timeout", "kind": "exec",
                 "script": "import time; time.sleep(30)",
                 "interpreter": [sys.executable], "timeout_sec": 1},
            self.base)
        self.assertTrue(r["timed_out"])
        self.assertFalse(os.path.exists(self.work_dir("reap-timeout")))

    def test_quarantined_workspace_survives_the_reap(self):
        work = self.plant("reap-seized", 0)
        dest = R._remediation.quarantine_job(
            self.base, "reap-seized", work,
            {"job_id": "reap-seized", "mode": "enforce",
             "authority": "tripwire", "divergence": "test",
             "act": "quarantined", "received_digest": ""})
        self.assertIsNotNone(dest)
        seized = os.path.join(dest, "work", "staged.txt")
        self.assertTrue(os.path.isfile(seized))
        # The reap of the job's old path finds nothing there and
        # must not reach into the quarantine root.
        self.assertFalse(R.reap_work_dir(work))
        self.assertTrue(os.path.isfile(seized))

    def test_reap_work_dir_removes_and_reports(self):
        work = self.plant("reap-direct", 0)
        self.assertTrue(R.reap_work_dir(work))
        self.assertFalse(os.path.exists(work))
        self.assertFalse(R.reap_work_dir(work))


class WorkOrphanSweepTest(_Base):
    def sweep(self, cfg=None, now=None):
        return R.reap_work_orphans(self.base, cfg or {}, now=now)

    def test_old_orphan_is_reaped(self):
        path = self.plant("old-job-1", 8 * DAY)
        self.assertEqual(self.sweep(), 1)
        self.assertFalse(os.path.exists(path))

    def test_fresh_directory_is_kept(self):
        path = self.plant("fresh-job", 3600)
        self.assertEqual(self.sweep(), 0)
        self.assertTrue(os.path.isdir(path))

    def test_foreign_name_is_kept_at_any_age(self):
        for name in ("hello world", "semi;colon", "a" * 200):
            path = self.plant(name, 90 * DAY)
            self.assertEqual(self.sweep(), 0, name)
            self.assertTrue(os.path.isdir(path), name)

    def test_plain_file_is_kept(self):
        path = self.plant("file-job-1", 30 * DAY, is_dir=False)
        self.assertEqual(self.sweep(), 0)
        self.assertTrue(os.path.isfile(path))

    def test_symlink_is_kept(self):
        # The target's name is foreign to the sweep, so only the
        # symlink decision is exercised here.
        target = self.plant("real target", 30 * DAY)
        link = os.path.join(self.work_root, "link-job-1")
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("cannot create a symlink here")
        when = time.time() - 30 * DAY
        os.utime(link, (when, when), follow_symlinks=False)
        self.assertEqual(self.sweep(), 0)
        self.assertTrue(os.path.islink(link))
        self.assertTrue(os.path.isdir(target))

    def test_zero_retention_disables_the_sweep(self):
        path = self.plant("ancient-job", 365 * DAY)
        self.assertEqual(self.sweep({"work_retention_sec": 0}), 0)
        self.assertTrue(os.path.isdir(path))
        # 0 is a usable value (the sweep is off by the owner's
        # setting), not a defaulted one.
        self.assertFalse(
            R._defaulted.is_defaulted("work_retention_sec", 0))

    def test_unusable_retention_reads_as_the_default(self):
        old = self.plant("old-enough", 8 * DAY)
        fresh = self.plant("still-fresh", 3600)
        self.assertEqual(self.sweep({"work_retention_sec": "banana"}), 1)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.isdir(fresh))
        # ...and the value is named by the startup line's
        # registry (runner/guard/defaulted.py), not silently.
        self.assertTrue(
            R._defaulted.is_defaulted("work_retention_sec", "banana"))
        self.assertEqual(
            R._defaulted.default_for("work_retention_sec"), 604800)
        self.assertIn("work_retention_sec",
                      R._defaulted.defaulted_keys(
                          {"work_retention_sec": "banana"}))

    def test_boolean_retention_reads_as_the_default(self):
        old = self.plant("bool-job", 8 * DAY)
        self.assertEqual(self.sweep({"work_retention_sec": True}), 1)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(
            R._defaulted.is_defaulted("work_retention_sec", True))

    def test_custom_retention_age(self):
        old = self.plant("two-hours", 2 * 3600)
        fresh = self.plant("half-hour", 1800)
        self.assertEqual(self.sweep({"work_retention_sec": 3600}), 1)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.isdir(fresh))

    def test_sweep_is_bounded(self):
        for i in range(520):
            self.plant("bulk-%04d" % i, 30 * DAY)
        self.assertEqual(self.sweep(), 512)
        remaining = [n for n in os.listdir(self.work_root)]
        self.assertEqual(len(remaining), 8)

    def test_missing_work_root_is_quiet(self):
        empty = os.path.join(self.base, "no-such-base")
        self.assertEqual(R.reap_work_orphans(empty, {}), 0)

    def test_sweep_counts_only_what_it_reaped(self):
        self.plant("gone-1", 9 * DAY)
        self.plant("gone-2", 9 * DAY)
        self.plant("stays-fresh", 60)
        self.plant("stays foreign", 9 * DAY)
        self.assertEqual(self.sweep(), 2)
        self.assertEqual(sorted(os.listdir(self.work_root)),
                         ["stays foreign", "stays-fresh"])


if __name__ == "__main__":
    unittest.main()
