# Agent-Stamp: 90000998-709f-46f5-b2bc-2c3c5cf8dc6c
"""send_job.py new carries a job's result_policy (questions.md Q104).

The protocol's capped-view channel (PROTOCOL.md sections 9 and 10)
had no sender: a job could not ask for a view or declare the queries
answered inside its result. Pinned here: the flags build the object,
a malformed spec is refused before anything is signed, and a job the
sender builds is answered by the runner under the attested view with
its attestations and query answers.
"""
import argparse
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner as R  # noqa: E402
from runner.cloud import send_job  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402


def _policy(**kw):
    base = dict(result_policy=None, view=None, query=[], query_budget=None)
    base.update(kw)
    err = io.StringIO()
    with redirect_stderr(err):
        out = send_job.result_policy(argparse.Namespace(**base))
    return out, err.getvalue()


class PolicyTest(unittest.TestCase):
    def test_no_flags_no_policy(self):
        self.assertEqual(_policy()[0], None)

    def test_the_flags_build_the_object(self):
        policy, _ = _policy(view="attested", query_budget=3, query=[
            "attest:exit_zero", "tail", "tail:5", "grep:ERR:OR",
            '{"op": "attest", "predicate": "no_secrets"}'])
        self.assertEqual(policy, {
            "view": "attested", "query_budget": 3, "queries": [
                {"op": "attest", "predicate": "exit_zero"},
                {"op": "tail"}, {"op": "tail", "lines": 5},
                {"op": "grep", "pattern": "ERR:OR"},
                {"op": "attest", "predicate": "no_secrets"}]})

    def test_the_flags_add_to_a_whole_object(self):
        d = tempfile.mkdtemp(prefix="hp-rp-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        path = os.path.join(d, "policy.json")
        with open(path, "w") as fh:
            json.dump({"view": "full", "queries": [{"op": "tail"}]}, fh)
        policy, _ = _policy(result_policy="@" + path, view="redacted",
                            query=["attest:exit_zero"])
        self.assertEqual(policy["view"], "redacted")
        self.assertEqual(len(policy["queries"]), 2)

    def test_a_capped_view_with_grep_says_what_the_runner_will_do(self):
        _, err = _policy(view="summary", query=["grep:x"])
        self.assertIn("refuses grep and tail", err)

    def test_bad_specs_are_refused(self):
        for kw in ({"query": ["attest:"]}, {"query": ["tail:many"]},
                   {"query": ["head:3"]}, {"query": ['{"pattern": "x"}']},
                   {"query": [" "]}, {"query_budget": -1},
                   {"result_policy": "[1]"},
                   {"result_policy": '{"view": "everything"}'},
                   {"result_policy": '{"queries": {}}', "query": ["tail"]}):
            with self.assertRaises(ValueError, msg=kw):
                _policy(**kw)


class NewTest(unittest.TestCase):
    def new(self, *extra):
        argv = ["send_job.py", "new", "--kind", "exec", "--secret",
                TR.SECRET, "--job-id", "rp-1", "--cleartext"] + list(extra)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", argv), redirect_stdout(out), \
                redirect_stderr(err):
            rc = send_job.main()
        return rc, out.getvalue(), err.getvalue()

    def test_a_bad_spec_signs_nothing(self):
        d = tempfile.mkdtemp(prefix="hp-rp-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        script = os.path.join(d, "s.sh")
        with open(script, "w") as fh:
            fh.write("echo hi\n")
        rc, out, err = self.new("--script-file", script, "--query", "head")
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("bad result policy", err)


class RunnerAnswersTest(unittest.TestCase):
    """The sender's job, through the runner, under the attested view."""

    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.addCleanup(shutil.rmtree, self.h.tmp, ignore_errors=True)

    @unittest.skipIf(os.name == "nt", "POSIX only")
    def test_attested_result_answers_the_declared_queries(self):
        d = tempfile.mkdtemp(prefix="hp-rp-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        script = os.path.join(d, "s.sh")
        with open(script, "w") as fh:
            fh.write("echo all good\n")
        argv = ["send_job.py", "new", "--kind", "exec", "--secret",
                TR.SECRET, "--job-id", "rp-2", "--script-file", script,
                "--interpreter", '["sh"]', "--view", "attested",
                "--query", "attest:exit_zero", "--query",
                "attest:output_digest"]
        out = io.StringIO()
        with mock.patch.object(sys, "argv", argv), redirect_stdout(out), \
                redirect_stderr(io.StringIO()):
            self.assertEqual(send_job.main(), 0)
        subject, _, body = out.getvalue().partition("\n\n")
        sent = R.process_transport_message(
            self.h.cfg, self.h.tmp, {}, R.build_secrets(self.h.cfg), {},
            subject.strip(), body, transport="file")
        self.assertEqual(len(sent), 1)
        from runner.wire import jobcrypto
        rbody = sent[0][1]
        outer = R.verify_body(rbody, TR.SECRET)
        result = R.verify_body(jobcrypto.decrypt_body(
            outer, TR.SECRET, "rp-2", outer.get("key_id", "")), TR.SECRET) \
            if "hp_enc" in outer else outer
        self.assertEqual(result["view"], "attested")
        self.assertEqual(result["stdout"], "")
        answers = {a.get("predicate"): a for a in result.get("answers", [])}
        self.assertTrue(answers["exit_zero"]["value"])
        self.assertIn("output_digest", answers)


if __name__ == "__main__":
    unittest.main()
