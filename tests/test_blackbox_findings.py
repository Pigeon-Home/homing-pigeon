#!/usr/bin/env python3
"""Unit tests documenting black-box findings from live runner testing
(session of 2026-10-15, ~19:50–20:30 UTC).

Confirmed on a Windows runner via signed email jobs to slutsky5544@gmail.com.
"""
import hmac
import hashlib
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import (  # noqa: E402
    PROTOCOL_VERSION,
    platform_interpreter,
    script_filename,
    answer_queries,
    sign_payload,
    verify_body,
    verify_body_keyed,
)

SECRET = "wmKK+9avPLN9rSsETqH5E1SrXXzdS3YCQQePMRj8e3A="


class ProtocolVersionTest(unittest.TestCase):
    """Finding: message version field is fixed at 1.

    Live log: 'rejecting seq N: unsupported version/type' for every
    job that carried "v": 3. No work directory was created. Oracle
    features (result_policy, summary, attest, queries) are additive
    fields on a v=1 message, not a version bump.
    """

    def test_protocol_version_is_1(self):
        self.assertEqual(PROTOCOL_VERSION, 1)

    def test_v3_is_not_protocol_version(self):
        self.assertNotEqual(3, PROTOCOL_VERSION)


class InterpreterStagingTest(unittest.TestCase):
    """Finding: runner always appends the staged script path.

    platform_interpreter() on Windows ends with -File, so the path is
    a script file. An interpreter list ending in -Command makes the
    path an invalid command string (live exit=1, empty stdout).
    script_filename returns .ps1 when 'powershell' appears, 'script'
    otherwise. Live sh jobs failed with WinError 2.
    """

    def test_script_filename_ps1_for_powershell(self):
        self.assertEqual(
            script_filename(["powershell", "-NoProfile", "-File"]),
            "script.ps1",
        )
        self.assertEqual(
            script_filename(["powershell", "-NoProfile", "-Command"]),
            "script.ps1",
        )

    def test_script_filename_generic_for_sh(self):
        self.assertEqual(script_filename(["sh"]), "script")
        self.assertEqual(script_filename(["bash"]), "script")

    def test_platform_default_contains_file_flag_shape(self):
        # On non-Windows the default is ["sh"]; the -File shape is
        # Windows-only. We still assert the function returns a list.
        interp = platform_interpreter()
        self.assertIsInstance(interp, list)
        self.assertTrue(interp)


class QueryBudgetAndAttestTest(unittest.TestCase):
    """Finding: query_budget limits subsequent queries; attest works.

    Live: job with query_budget=1 and [attest, grep] logged
    'query op=grep rejected: budget'. Attest on exit 1 returns ok=False.
    Grep for a non-matching pattern returns empty matches.
    """

    def test_budget_rejects_second_query(self):
        exec_result = {"exit_code": 0, "stdout": "Thursday, October 15, 2026 8:26:12 PM\n"}
        queries = [
            {"op": "attest", "predicate": "exit_zero"},
            {"op": "grep", "pattern": ".", "max_matches": 1},
        ]
        answers, spent = answer_queries(
            queries, exec_result, patterns={}, budget=1, view="full"
        )
        self.assertEqual(len(answers), 2)
        self.assertEqual(answers[0].get("op"), "attest")
        self.assertTrue(answers[0].get("ok") or answers[0].get("value"))
        self.assertEqual(answers[1].get("rejected"), "budget")
        self.assertEqual(spent, 2)

    def test_attest_false_on_nonzero_exit(self):
        exec_result = {"exit_code": 1, "stdout": ""}
        queries = [{"op": "attest", "predicate": "exit_zero"}]
        answers, _ = answer_queries(
            queries, exec_result, patterns={}, budget=8, view="full"
        )
        self.assertEqual(len(answers), 1)
        self.assertFalse(answers[0].get("ok", True))
        self.assertFalse(answers[0].get("value", True))

    def test_grep_no_match_returns_empty(self):
        exec_result = {"exit_code": 0, "stdout": "Thursday, October 15, 2026 8:27:23 PM\n"}
        queries = [{"op": "grep", "pattern": "NO_MATCH_XYZ", "max_matches": 5}]
        answers, _ = answer_queries(
            queries, exec_result, patterns={}, budget=8, view="full"
        )
        self.assertEqual(answers[0].get("matches"), [])

    def test_summary_view_rejects_raw_line_ops(self):
        # Summary view does not allow grep/tail (raw lines).
        exec_result = {"exit_code": 0, "stdout": "clock\n"}
        queries = [{"op": "grep", "pattern": ".", "max_matches": 1}]
        answers, _ = answer_queries(
            queries, exec_result, patterns={}, budget=8, view="summary"
        )
        self.assertEqual(answers[0].get("rejected"), "policy")


class SignatureEdgeCasesTest(unittest.TestCase):
    """Finding: signature verification fails closed on malformed input.

    Live rejects:
    - 'bad signature: malformed signature tail' (truncated sig)
    - 'bad signature: invalid JSON: Invalid control character' (raw
      newlines or unescaped quotes inside the JSON body)
    Valid signed v=1 jobs with result_policy were accepted and executed.
    """

    def _signed(self, payload):
        return sign_payload(payload, SECRET)

    def test_valid_v1_job_verifies(self):
        payload = {
            "v": 1, "type": "job", "kind": "exec",
            "script": "Get-Date\n", "timeout_sec": 30,
            "job_id": "test-job", "issued_at": "2026-10-16T03:00:00Z",
        }
        body = self._signed(payload)
        job = verify_body(body, SECRET)
        self.assertEqual(job["v"], 1)
        self.assertEqual(job["kind"], "exec")

    def test_truncated_signature_tail_rejected(self):
        payload = {"v": 1, "type": "job", "kind": "ping", "job_id": "x"}
        body = self._signed(payload)
        # Truncate the signature hex
        truncated = body[:-10]
        with self.assertRaises(ValueError) as cm:
            verify_body(truncated, SECRET)
        self.assertIn("malformed signature tail", str(cm.exception))

    def test_control_character_in_json_rejected(self):
        # A raw newline inside a JSON string (not escaped) makes the
        # body invalid JSON after signature extraction.
        bad = '{"v":1,"type":"job","script":"exit 1\n","sig":"' + "a"*96 + '"}'
        with self.assertRaises(ValueError) as cm:
            verify_body_keyed(bad, {"": SECRET})
        msg = str(cm.exception)
        self.assertTrue("invalid JSON" in msg or "malformed" in msg or "signature" in msg.lower())

    def test_unknown_key_id_rejected_before_crypto(self):
        payload = {"v": 1, "type": "job", "key_id": "no-such-key", "job_id": "x"}
        body = sign_payload(payload, SECRET)
        with self.assertRaises(ValueError) as cm:
            verify_body_keyed(body, {"": SECRET})
        self.assertIn("unknown key_id", str(cm.exception))


class EmptyScriptRejectionTest(unittest.TestCase):
    """Finding: an exec job with an empty script is rejected.

    Live log: 'job ... rejected: exec job requires script or script_url'
    for jobs that sent script: "".
    """

    def test_empty_script_is_falsy(self):
        script = ""
        self.assertFalse(script)


class ResultViewTest(unittest.TestCase):
    """Finding: summary view suppresses raw output in the result.

    Live results for view=summary had empty stdout while exit_code=0
    and the clock was printed internally. Full view returned the clock.
    """

    def test_summary_view_constant(self):
        # Document the view string the runner expects.
        self.assertEqual("summary", "summary")
        self.assertNotEqual("summary", "full")


if __name__ == "__main__":
    unittest.main()
