# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Q104: `send_job.py new` declares a job's result_policy.

PROTOCOL.md sections 9 and 10 give a job a `result_policy`: the view
it asks for, a query budget, and every query it will ever be asked,
answered inside the result under the effective view. The runner had
the reader and the sender had no way to write one, so an SI against a
rig whose `max_result_view` is `attested` could learn nothing about a
failed job but its exit code. `--view`, `--query JSON`, `--attest`,
`--grep`, `--tail`, `--query-budget` and `--result-policy-file` write
it, inside the signed body; a job the runner would refuse to read
the way it was meant is refused before it is signed.
"""
import io
import json
import os
import secrets
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from runner import runner as R  # noqa: E402
from runner.cloud import send_job  # noqa: E402
from runner.ops import policy as POL  # noqa: E402

SECRET = secrets.token_hex(32)


class ResultPolicyFlagsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-q104-")
        self.script = os.path.join(self.tmp, "job.sh")
        with open(self.script, "w", encoding="utf-8") as fh:
            fh.write("echo hello\n")

    def new(self, *flags):
        out, err = io.StringIO(), io.StringIO()
        argv = ["send_job.py", "new", "--secret", SECRET,
                "--script-file", self.script] + list(flags)
        with mock.patch.object(sys, "argv", argv), \
                redirect_stdout(out), redirect_stderr(err):
            rc = send_job.main()
        return rc, out.getvalue(), err.getvalue()

    def job(self, *flags):
        rc, out, err = self.new(*flags)
        self.assertEqual(rc, 0, err)
        lines = out.splitlines()
        job_id = lines[0].rsplit(" ", 1)[1]
        secrets_map = R.build_secrets({"shared_secret": SECRET})
        job, _kid, _sec, encrypted = R._admit_object(
            "\n".join(lines[2:]), secrets_map, job_id)
        self.assertTrue(encrypted)
        return job

    def test_no_flag_no_policy(self):
        self.assertNotIn("result_policy", self.job())

    def test_the_flags_write_the_policy_in_the_signed_body(self):
        job = self.job("--view", "attested", "--attest", "exit_zero",
                       "--attest", "no_secrets", "--grep", "ERROR",
                       "--tail", "5", "--query-budget", "6",
                       "--query", '{"op": "grep", "pattern": "warn", "max_matches": 2}')
        self.assertEqual(job["result_policy"], {
            "view": "attested", "query_budget": 6,
            "queries": [
                {"op": "grep", "pattern": "warn", "max_matches": 2},
                {"op": "attest", "predicate": "exit_zero"},
                {"op": "attest", "predicate": "no_secrets"},
                {"op": "grep", "pattern": "ERROR"},
                {"op": "tail", "lines": 5}]})

    def test_a_policy_file_is_the_base_the_flags_add_to(self):
        path = os.path.join(self.tmp, "policy.json")
        with open(path, "w") as fh:
            json.dump({"view": "full", "queries": [{"op": "tail"}]}, fh)
        job = self.job("--result-policy-file", path, "--view", "summary",
                       "--attest", "exit_zero")
        self.assertEqual(job["result_policy"]["view"], "summary")
        self.assertEqual(job["result_policy"]["queries"],
                         [{"op": "tail"}, {"op": "attest", "predicate": "exit_zero"}])

    def test_what_the_runner_could_not_read_as_meant_is_refused_unsigned(self):
        bad_file = os.path.join(self.tmp, "list.json")
        with open(bad_file, "w") as fh:
            fh.write("[1]")
        for flags in (["--query", "not json"],
                      ["--query", '{"op": "rm"}'],
                      ["--query", '["grep"]'],
                      ["--query-budget", "-1"],
                      ["--result-policy-file", bad_file],
                      ["--result-policy-file", os.path.join(self.tmp, "none.json")]):
            with self.subTest(flags=flags):
                rc, out, err = self.new(*flags)
                self.assertEqual(rc, 2)
                self.assertEqual(out, "")
                self.assertIn("error:", err)

    def test_an_unknown_view_is_refused_by_the_parser(self):
        with self.assertRaises(SystemExit):
            self.new("--view", "wide")

    def test_the_declared_queries_are_answered_under_an_attested_ceiling(self):
        """The case that asked for this: a rig capped at attested. No
        output leaves, and the declared attestations come home."""
        job = self.job("--view", "full", "--attest", "exit_zero",
                       "--grep", "ERROR", "--tail", "2")
        exec_result = {"stdout": "ok\nERROR disk full\n", "stderr": "",
                       "exit_code": 1, "timed_out": False, "duration_sec": 0.1}
        cfg = {"max_result_view": "attested"}
        result, retain = POL.apply_result_policy(cfg, job, exec_result, {}, True)
        self.assertEqual(result["view"], "attested")
        self.assertTrue(retain)
        self.assertEqual(result["stdout"], "")
        self.assertEqual(result["attestations"],
                         [{"predicate": "exit_zero", "ok": False}])
        answers, spent = R.answer_queries(
            job["result_policy"]["queries"],
            {"stdout": exec_result["stdout"], "stderr": "", "exit_code": 1,
             "confined": True, "digest": result["output_digest"]},
            {}, R.query_budget(cfg, job), cfg=cfg, view=result["view"])
        self.assertEqual(spent, 3)
        self.assertEqual(answers[0].get("value"), False)
        # grep and tail would carry output lines: refused under attested
        self.assertTrue(all("rejected" in a for a in answers[1:]), answers)
        self.assertNotIn("disk full", json.dumps(answers))


if __name__ == "__main__":
    unittest.main()
