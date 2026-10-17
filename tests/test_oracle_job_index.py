#!/usr/bin/env python3
"""The job index at the head of oracle_context (2026-10-16 field
report). Asked for a job summary, the local model narrated the
runner log tail instead -- authentication warnings and startup
lines -- and never named a job. The context it was handed had no
index to read back: six detailed job blocks, then a noisy log. The
context now leads with a computed index (id, kind, result, time,
newest first), and the prompt says a summary names jobs from it.
"""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402


def _write_job(d, job_id, data, mtime):
    path = os.path.join(d, "retained", job_id + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.utime(path, (mtime, mtime))


class JobIndexTest(unittest.TestCase):
    def test_context_leads_with_a_job_index(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            _write_job(d, "job-aaa", {"kind": "exec", "exit_code": 0,
                                      "saved_at": 1760000000,
                                      "script": "echo a",
                                      "stdout": "a"}, 1000)
            _write_job(d, "job-bbb", {"kind": "exec", "exit_code": 1,
                                      "saved_at": 1760003600,
                                      "script": "echo b",
                                      "stdout": "b"}, 2000)
            text = R.oracle_context(d, watch=False)
        self.assertIn("Job index (newest first", text)
        lines = text.splitlines()
        head = lines.index(next(ln for ln in lines
                                if ln.startswith("Job index")))
        idx = []
        for ln in lines[head + 1:]:
            if not ln:
                break
            idx.append(ln)
        self.assertEqual(len(idx), 2)
        # Newest first, facts on one line each.
        self.assertIn("job-bbb", idx[0])
        self.assertIn("exit code 1", idx[0])
        self.assertIn("job-aaa", idx[1])
        self.assertIn("exit code 0", idx[1])
        # The index sits ahead of every detailed block.
        self.assertLess(text.index("Job index"),
                        text.index("script:"))

    def test_index_facts_for_missing_kind_and_timeouts(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            _write_job(d, "job-old", {"stdout": "x"}, 1000)
            _write_job(d, "job-slow", {"kind": "exec",
                                       "timed_out": True,
                                       "stdout": "y"}, 2000)
            text = R.oracle_context(d, watch=False)
        self.assertIn("job job-old (kind not recorded,", text)
        self.assertIn("job job-slow (exec, timed out,", text)

    def test_index_survives_a_small_cap(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            _write_job(d, "job-aaa", {"kind": "exec", "exit_code": 0,
                                      "saved_at": 1760000000,
                                      "script": "echo " + "x" * 500,
                                      "stdout": "z" * 500}, 1000)
            text = R.oracle_context(d, max_chars=200, watch=False)
        self.assertIn("Job index", text)
        self.assertIn("job-aaa", text)

    def test_no_jobs_no_index(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            text = R.oracle_context(d, watch=False)
        self.assertIn("(no job output retained yet)", text)
        self.assertNotIn("Job index", text)

    def test_prompt_names_the_index_rule(self):
        self.assertIn("name the jobs from the Job index",
                      R.ASK_AGENT_SYSTEM)
        self.assertIn("are not jobs", R.ASK_AGENT_SYSTEM)
        # Round 2 of the field loop: the model listed directories
        # twice before answering a summary question -- "do not open
        # files" left list_dir outside the rule. The rule now covers
        # every tool, and the index line's time is part of the ask.
        self.assertIn("Do not use tools for those",
                      R.ASK_AGENT_SYSTEM)
        self.assertIn("the result, and the time", R.ASK_AGENT_SYSTEM)


if __name__ == "__main__":
    unittest.main()
