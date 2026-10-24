#!/usr/bin/env python3
"""Answer-format guard (2026-10-17 field reports).

On a 2-core laptop the 1B Oracle answered a job-status summary by
re-serializing the job index as JSON, and a follow-up judgment
question with corrupted JSON ending in a fabricated tool-call
fragment (a "run" of psexec, as answer text). A reply that is a
structured-data dump or carries a tool-call fragment is withheld,
the question is re-asked once for plain prose, and a second failure
returns a mechanical fallback sentence instead of the dump. These
tests pin the detectors and both guarded paths (ask_model and
ask_model_agent). No live model: scripted openers only.
"""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402

CLEAN_DUMP = json.dumps({
    "job_status": "Summary",
    "newest_job_index": "c1093eea-237a-44c3-84f5-202f5433ef4b",
    "job_ids": ["c1093eea-237a-44c3-84f5-202f5433ef4b",
                "a1d57437-4b45-48d1-b995-86ec79fd8deb"],
    "times": ["2026-10-16 18:53", "2026-10-16 18:52"],
    "status": "summary and status questions",
    "previous_job_details": None,
    "total_job_count": 7,
    "current_job_count": 1,
})

CORRUPT_DUMP = (
    '{"job_status": ["Summary", "newest_job_index='
    '\\"c1093eea-237a-44c3-84f5-202f5433ef4b\\",kind=\\"Get-Date\\",'
    'exit_code\\\\s(0,0)\\",time=\\"2026-10-16 18:53\\""], '
    '{"name": "run", "parameters": {"command": '
    '"psexec -i -a -n -C home.exe -l 16 -w -r", "timeout_sec": 300}}'
)

PROSE = ("Seven jobs are on record. The newest, "
         "c1093eea-237a-44c3-84f5-202f5433ef4b, was a Get-Date check "
         "at 2026-10-16 18:53 and exited 0. None of them did anything "
         "malicious.")


class _Resp:
    def __init__(self, body):
        self._body = body

    def read(self, n=-1):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _scripted_opener(script, seen):
    def opener(req, timeout=None):
        seen.append(json.loads(req.data.decode("utf-8")))
        msg = script.pop(0)
        body = json.dumps({"choices": [{"message": msg}]}).encode()
        return _Resp(body)
    return opener


def _msg(content):
    return {"role": "assistant", "content": content}


def _cfg():
    return {"endpoint": "http://127.0.0.1:11434/v1",
            "model": "llama3.2:1b",
            "timeout_sec": 5,
            "max_answer_chars": 2000}


class DetectorTest(unittest.TestCase):
    def test_clean_index_dump_trips(self):
        self.assertIn("job-index dump",
                      R._answer_format_problem(CLEAN_DUMP))

    def test_corrupt_dump_with_fragment_trips(self):
        self.assertIn("tool-call fragment",
                      R._answer_format_problem(CORRUPT_DUMP))

    def test_bare_fragment_trips(self):
        text = ('It ran {"name": "run", "parameters": '
                '{"command": "date", "timeout_sec": 300}}')
        self.assertIn("tool-call fragment",
                      R._answer_format_problem(text))

    def test_small_json_with_two_index_keys_trips(self):
        self.assertIn("job-index dump", R._answer_format_problem(
            '{"job_status": "Summary", "total_job_count": 7}'))

    def test_prose_passes(self):
        self.assertEqual(R._answer_format_problem(PROSE), "")

    def test_prose_naming_a_tool_passes(self):
        self.assertEqual(R._answer_format_problem(
            'The "run" tool was not needed for that question.'), "")

    def test_unrelated_json_is_not_the_guards_business(self):
        self.assertEqual(R._answer_format_problem(
            '{"answer": "all clear", "count": 7}'), "")

    def test_empty_and_nonstr_pass(self):
        self.assertEqual(R._answer_format_problem(""), "")
        self.assertEqual(R._answer_format_problem(None), "")


class AskModelGuardTest(unittest.TestCase):
    def _ask(self, script):
        seen = []
        result = R.ask_model(_cfg(), "What ran?", "some job output",
                             2000, opener=_scripted_opener(script, seen))
        return result, seen

    def test_dump_then_prose_returns_prose(self):
        result, seen = self._ask([_msg(CLEAN_DUMP), _msg(PROSE)])
        self.assertEqual(result.get("answer"), PROSE)
        self.assertEqual(len(seen), 2)
        retry_user = seen[1]["messages"][1]["content"]
        self.assertIn("plain sentences", retry_user)

    def test_dump_twice_returns_fallback(self):
        result, seen = self._ask([_msg(CLEAN_DUMP), _msg(CORRUPT_DUMP)])
        self.assertEqual(result.get("answer"), R._FORMAT_FALLBACK_ANSWER)
        self.assertEqual(len(seen), 2)

    def test_prose_first_try_no_retry(self):
        result, seen = self._ask([_msg(PROSE)])
        self.assertEqual(result.get("answer"), PROSE)
        self.assertEqual(len(seen), 1)


class AgentGuardTest(unittest.TestCase):
    def _ask(self, script):
        seen = []
        with tempfile.TemporaryDirectory() as base:
            result = R.ask_model_agent(
                _cfg(), "Give me a summary of the job status.",
                "some job output", 2000,
                opener=_scripted_opener(script, seen), base_dir=base)
        return result, seen

    def test_dump_then_prose_returns_prose(self):
        result, seen = self._ask([_msg(CLEAN_DUMP), _msg(PROSE)])
        self.assertEqual(result.get("answer"), PROSE)
        self.assertEqual(len(seen), 2)
        self.assertFalse(seen[1].get("tools"))

    def test_fragment_then_prose_returns_prose(self):
        result, seen = self._ask([_msg(CORRUPT_DUMP), _msg(PROSE)])
        self.assertEqual(result.get("answer"), PROSE)
        self.assertEqual(len(seen), 2)

    def test_dump_twice_returns_fallback(self):
        result, seen = self._ask([_msg(CLEAN_DUMP), _msg(CLEAN_DUMP)])
        self.assertEqual(result.get("answer"), R._FORMAT_FALLBACK_ANSWER)
        self.assertEqual(len(seen), 2)


if __name__ == "__main__":
    unittest.main()
