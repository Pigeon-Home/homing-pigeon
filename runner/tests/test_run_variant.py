"""The core's --run-variant door: the job-fuzz sense's
execution path.

Pins runner.run_variant: one locally supplied variant job
runs through the same validation and confined execution as
a real exec job and reports its outcome as JSON, under an
allowlist that drops everything a variant must never carry
(files, script_url, signatures), with an audit entry per
run and work confined to <base_dir>/fuzz-work.

Local only: no mailbox, no network (the one URL-bearing
case points at an unroutable address and proves it is
never fetched), temp state dirs throughout.
"""
import argparse
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402


class RunVariantTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-rv-")
        self.cfg = {"base_dir": self.tmp,
                    "default_timeout_sec": 30}

    def _variant_file(self, variant, name="variant.json"):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            if isinstance(variant, str):
                fh.write(variant)
            else:
                json.dump(variant, fh)
        return path

    def _run(self, path):
        args = argparse.Namespace(
            config=os.path.join(self.tmp, "config.json"),
            run_variant=path)
        out = io.StringIO()
        with redirect_stdout(out):
            rc = R.run_variant(self.cfg, args)
        # The runner's log shares stdout in one-shot modes;
        # the report is the JSON line, as the sense reads it.
        report = None
        for line in reversed(out.getvalue().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    report = json.loads(line)
                    break
                except ValueError:
                    continue
        return rc, report

    def test_a_variant_runs_in_the_bucket(self):
        path = self._variant_file(
            {"job_id": "fuzz-t1", "kind": "exec",
             "script": "echo variant-hello"})
        rc, report = self._run(path)
        self.assertEqual(rc, 0)
        self.assertEqual(report["stage"], "ran")
        self.assertEqual(report["exit_code"], 0)
        self.assertFalse(report["timed_out"])
        # The digest is over the run's actual output bytes,
        # whose line endings belong to the platform's shell
        # (LF here, CRLF on Windows) -- so the pinned
        # contract is shape plus determinism, not one
        # platform's bytes.
        self.assertEqual(len(report["digest"]), 96)
        self.assertGreater(report["stdout_bytes"], 0)
        _rc2, report2 = self._run(path)
        self.assertEqual(report2["digest"], report["digest"])
        # Work landed in the fuzz scratch tree, not the
        # runner's live work tree.
        self.assertTrue(os.path.isdir(
            os.path.join(self.tmp, "fuzz-work", "work",
                         "fuzz-t1")))
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp, "work")))

    def test_the_malformed_interpreter_shape_is_refused(self):
        path = self._variant_file(
            {"job_id": "fuzz-t2", "kind": "exec",
             "script": "echo x", "interpreter": "sh"})
        rc, report = self._run(path)
        self.assertEqual(rc, 0)
        self.assertEqual(report["stage"], "refused")
        self.assertIn("interpreter", report["reason"])

    def test_a_non_exec_kind_is_refused(self):
        path = self._variant_file(
            {"job_id": "fuzz-t3", "kind": "query",
             "script": "echo x"})
        _rc, report = self._run(path)
        self.assertEqual(report["stage"], "refused")
        self.assertIn("not exec", report["reason"])

    def test_fetch_and_delivery_keys_are_dropped(self):
        # files and script_url point at an unroutable host:
        # if either survived the allowlist the run would
        # fail trying to fetch. It must run the inline
        # script alone.
        path = self._variant_file(
            {"job_id": "fuzz-t4", "kind": "exec",
             "script": "echo clean",
             "script_url": "https://10.255.255.1/s",
             "files": [{"name": "f",
                        "url": "https://10.255.255.1/f"}],
             "signature": "deadbeef", "reply_to": "x@y.z"})
        rc, report = self._run(path)
        self.assertEqual(rc, 0)
        self.assertEqual(report["stage"], "ran")
        self.assertEqual(report["exit_code"], 0)

    def test_a_non_object_variant_is_refused_not_fatal(self):
        path = self._variant_file("[1, 2, 3]")
        rc, report = self._run(path)
        self.assertEqual(rc, 0)
        self.assertEqual(report["stage"], "refused")

    def test_a_missing_variant_file_is_a_usage_error(self):
        rc, report = self._run(
            os.path.join(self.tmp, "nope.json"))
        self.assertEqual(rc, 2)
        self.assertIsNone(report)

    def test_the_mutator_rides_the_report(self):
        path = self._variant_file(
            {"job_id": "fuzz-t5", "kind": "exec",
             "script": "echo x", "mutator": "truncate"})
        _rc, report = self._run(path)
        self.assertEqual(report["mutator"], "truncate")

    def test_every_run_leaves_an_audit_entry(self):
        path = self._variant_file(
            {"job_id": "fuzz-t6", "kind": "exec",
             "script": "echo x", "mutator": "truncate"})
        self._run(path)
        audit = os.path.join(self.tmp, "security-audit.jsonl")
        with open(audit, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("variant_run", text)
        self.assertIn("fuzz-t6", text)

    def test_a_variant_exit_code_is_reported_verbatim(self):
        path = self._variant_file(
            {"job_id": "fuzz-t7", "kind": "exec",
             "script": "exit 7"})
        _rc, report = self._run(path)
        self.assertEqual(report["stage"], "ran")
        self.assertEqual(report["exit_code"], 7)


class RunVariantFallbacksTest(unittest.TestCase):
    """Queue A refill: run_variant's fallback legs
    (coverage run 40189608702: 8 lines on both
    platforms). The door's own docstring fixes the
    shapes: the variant's timeout is capped whatever
    the file asks for -- an unusable one reads as the
    cap itself; a variant with no usable job id runs
    under the default id; a work dir that cannot be
    created is a usage error (exit 2, named on
    stderr); and a failure in the execution path
    itself is an "error" report, never a raise and
    never a refusal.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-rv-")
        self.cfg = {"base_dir": self.tmp,
                    "default_timeout_sec": 30}

    def _variant_file(self, variant, name="variant.json"):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            if isinstance(variant, str):
                fh.write(variant)
            else:
                json.dump(variant, fh)
        return path

    def _run(self, path):
        args = argparse.Namespace(
            config=os.path.join(self.tmp, "config.json"),
            run_variant=path)
        out = io.StringIO()
        with redirect_stdout(out):
            rc = R.run_variant(self.cfg, args)
        report = None
        for line in reversed(out.getvalue().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    report = json.loads(line)
                    break
                except ValueError:
                    continue
        return rc, report

    def _capture_job(self, variant):
        seen = {}

        def fake_execute(cfg, job, work_base):
            seen.update(job)
            return {"exit_code": 0, "stdout": "x",
                    "stderr": "", "timed_out": False,
                    "duration_sec": 0.1}

        path = self._variant_file(variant)
        with mock.patch.object(R, "execute_job", fake_execute):
            rc, report = self._run(path)
        return rc, report, seen

    def test_an_unusable_timeout_reads_as_the_cap(self):
        rc, report, seen = self._capture_job(
            {"job_id": "fuzz-t", "script": "echo x",
             "timeout_sec": "not-a-number"})
        self.assertEqual(rc, 0)
        self.assertEqual(report["stage"], "ran")
        self.assertEqual(seen["timeout_sec"],
                         R._VARIANT_TIMEOUT_CAP_SEC)

    def test_a_missing_job_id_gets_the_default(self):
        _rc, report, seen = self._capture_job(
            {"script": "echo x"})
        self.assertEqual(report["stage"], "ran")
        self.assertEqual(seen["job_id"], "fuzz-variant")

    def test_an_uncreatable_work_dir_is_exit_2(self):
        import argparse
        blocker = os.path.join(self.tmp, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("not a directory")
        path = self._variant_file(
            {"job_id": "fuzz-t", "script": "echo x"})
        args = argparse.Namespace(
            config=os.path.join(self.tmp, "config.json"),
            run_variant=path)
        err = io.StringIO()
        with redirect_stderr(err):
            rc = R.run_variant({"base_dir": blocker}, args)
        self.assertEqual(rc, 2)
        self.assertIn("cannot create", err.getvalue())

    def test_an_execution_error_is_an_error_report(self):
        path = self._variant_file(
            {"job_id": "fuzz-t", "script": "echo x"})
        with mock.patch.object(
                R, "execute_job",
                side_effect=RuntimeError("bucket broke")):
            rc, report = self._run(path)
        self.assertEqual(rc, 0)
        self.assertEqual(report["stage"], "error")
        self.assertIn("RuntimeError: bucket broke",
                      report["reason"])


if __name__ == "__main__":
    unittest.main()
