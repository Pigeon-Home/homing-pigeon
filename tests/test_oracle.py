#!/usr/bin/env python3
"""Oracle privacy result tests (v3 Piece 3)."""
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import apply_result_policy, _redact_patterns, VIEW_ORDER

class OracleTest(unittest.TestCase):
    def test_full_view_default(self):
        cfg = {"oracle_enabled": True, "max_result_view": "full"}
        job = {"job_id": "j1", "kind": "ping"}
        er = {"exit_code": 0, "stdout": "pong", "stderr": "", "timed_out": False, "duration_sec": 0.0}
        result, retain = apply_result_policy(cfg, job, er, _redact_patterns(cfg), False)
        self.assertEqual(result["view"], "full")
        self.assertEqual(result["stdout"], "pong")
        self.assertFalse(retain)

    def test_ceiling_narrows(self):
        cfg = {"oracle_enabled": True, "max_result_view": "summary"}
        job = {"job_id": "j1", "kind": "exec", "result_policy": {"view": "full"}}
        er = {"exit_code": 0, "stdout": "secret", "stderr": "", "timed_out": False, "duration_sec": 0.1}
        result, retain = apply_result_policy(cfg, job, er, _redact_patterns(cfg), False)
        self.assertEqual(result["view"], "summary")
        self.assertNotIn("secret", result.get("stdout", ""))
        self.assertTrue(retain)

    def test_redacted_scrubs(self):
        cfg = {"oracle_enabled": True, "max_result_view": "full"}
        job = {"job_id": "j1", "kind": "exec", "result_policy": {"view": "redacted"}}
        er = {"exit_code": 0, "stdout": "key AKIAIOSFODNN7EXAMPLE found", "stderr": "", "timed_out": False, "duration_sec": 0.1}
        result, _ = apply_result_policy(cfg, job, er, _redact_patterns(cfg), False)
        self.assertEqual(result["view"], "redacted")
        self.assertIn("[REDACTED:aws_key]", result["stdout"])
        self.assertIn("aws_key", result["redacted_families"])

    def test_oracle_disabled_bypasses(self):
        cfg = {"oracle_enabled": False}
        job = {"job_id": "j1", "result_policy": {"view": "attested"}}
        er = {"exit_code": 0, "stdout": "raw", "stderr": "", "timed_out": False, "duration_sec": 0.0}
        result, retain = apply_result_policy(cfg, job, er, {}, False)
        self.assertEqual(result["stdout"], "raw")
        self.assertFalse(retain)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class JudgmentTest(unittest.TestCase):
    def test_judge_off_by_default(self):
        from runner.runner import judge_job
        v, r = judge_job({}, {"script": "rm -rf /"})
        self.assertEqual(v, "pass")
        self.assertEqual(r, [])

    def test_judge_detects_denylist(self):
        from runner.runner import judge_job
        v, r = judge_job({"judge": "enforce"}, {"script": "rm -rf /"})
        self.assertEqual(v, "fail")
        self.assertTrue(any("denylist" in x for x in r))

    def test_judge_non_string_fields_do_not_raise(self):
        from runner.runner import judge_job
        v, r = judge_job(
            {"judge": "enforce"},
            {"script": 5, "script_url": 9, "files": "not-a-list"},
        )
        self.assertEqual(v, "pass")
        self.assertEqual(r, [])

    def test_query_budget_min(self):
        from runner.runner import query_budget
        b = query_budget({"max_query_budget": 4}, {"result_policy": {"query_budget": 8}})
        self.assertEqual(b, 4)


class ProtectedPathsTest(unittest.TestCase):
    def test_reports_changes_under_protected(self):
        from runner.runner import check_protected_paths
        before = {"/home/user/docs/manuals/a.txt": (10, 1.0)}
        after = {"/home/user/docs/manuals/a.txt": (20, 2.0), "/tmp/other": (5, 1.0)}
        changed = check_protected_paths(before, after, ["/home/user/docs/manuals"])
        self.assertIn("/home/user/docs/manuals/a.txt", changed)
        self.assertNotIn("/tmp/other", changed)


class LogRedactionTest(unittest.TestCase):
    def setUp(self):
        from runner import runner as rr
        # Earlier tests can fill the per-minute log budget. This test
        # needs the line to actually print.
        rr._LOG_COUNT = 0
        rr._LOG_DROPPED = 0
        rr._LOG_MINUTE = 0.0
        rr._VERBOSE = True

    def test_process_log_redacts_before_printing(self):
        from runner.runner import execute_job
        buf = StringIO()
        with tempfile.TemporaryDirectory() as d:
            with redirect_stdout(buf):
                execute_job(
                    {"max_output_bytes": 1000},
                    {"job_id": "log-1", "kind": "exec",
                     "script": "echo AKIAIOSFODNN7EXAMPLE\n"},
                    d,
                )
        text = buf.getvalue()
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", text)
        self.assertIn("[REDACTED:aws_key]", text)

    def test_ask_log_redacts_before_printing(self):
        from runner.runner import ask_model

        class FakeResp:
            def read(self, n):
                return b'{"choices":[{"message":{"content":"key AKIAIOSFODNN7EXAMPLE"}}]}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        buf = StringIO()
        with redirect_stdout(buf):
            answer = ask_model(
                {"endpoint": "http://127.0.0.1:9/v1", "model": "m",
                 "timeout_sec": 1, "max_answer_chars": 100},
                "what key?", "out", 100, opener=lambda req, timeout=60: FakeResp(),
            )
        self.assertEqual(answer.get("rejected"), "sanitization")
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", buf.getvalue())
        self.assertIn("[REDACTED:aws_key]", buf.getvalue())

    def test_empty_default(self):
        from runner.runner import check_protected_paths
        self.assertEqual(check_protected_paths({}, {}, []), [])


class AttestationFixTest(unittest.TestCase):
    """Locks in the peer-review fixes: no_secrets actually scans, and
    confined_to_workspace distinguishes unconfigured from violated."""

    def test_no_secrets_scans_output(self):
        from runner.runner import build_attestations, BUILTIN_REDACT_PATTERNS
        # Clean output -> ok True.
        atts = build_attestations(
            [{"op": "attest", "predicate": "no_secrets"}],
            {"exit_code": 0, "patterns": BUILTIN_REDACT_PATTERNS,
             "text": "hello world", "confined": None})
        self.assertTrue(atts[0]["ok"])
        # Output containing a secret -> ok False (was hardcoded True).
        atts = build_attestations(
            [{"op": "attest", "predicate": "no_secrets"}],
            {"exit_code": 0, "patterns": BUILTIN_REDACT_PATTERNS,
             "text": "leaked AKIAIOSFODNN7EXAMPLE here", "confined": None})
        self.assertFalse(atts[0]["ok"])

    def test_confined_three_states(self):
        from runner.runner import build_attestations
        q = [{"op": "attest", "predicate": "confined_to_workspace"}]
        base = {"exit_code": 0, "patterns": {}, "text": ""}
        # Unconfigured -> ok False, reason "unconfigured".
        atts = build_attestations(q, {**base, "confined": None})
        self.assertFalse(atts[0]["ok"])
        self.assertEqual(atts[0]["reason"], "unconfigured")
        # Confined -> ok True.
        atts = build_attestations(q, {**base, "confined": True})
        self.assertTrue(atts[0]["ok"])
        # Violation -> ok False, reason is NOT "unconfigured".
        atts = build_attestations(q, {**base, "confined": False})
        self.assertFalse(atts[0]["ok"])
        self.assertNotEqual(atts[0]["reason"], "unconfigured")
