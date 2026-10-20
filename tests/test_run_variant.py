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
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        self.assertEqual(
            report["digest"],
            hashlib.sha384(b"variant-hello\n").hexdigest())
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


if __name__ == "__main__":
    unittest.main()
