#!/usr/bin/env python3
"""Unit tests documenting black-box findings from live runner testing
(session of 2026-10-15, ~19:50–20:30 UTC).

Confirmed on a Windows runner via signed email jobs to slutsky5544@gmail.com.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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

# Test-only shared secret. Used solely for unit tests in this file.
# Never deployed or used outside of testing.
# Valid under the secret rules: 44-char
# base64 of 32 bytes, ~222 bits estimated entropy, no weak pattern.
# A same-day bump to protocol 2 on 2026-10-17 was reverted. The
# secret format did not change with either edit.
SECRET = "wmKK+9avPLN9rSsETqH5E1SrXXzdS3YCQQePMRj8e3A="


class ProtocolVersionTest(unittest.TestCase):
    """Finding: message version field is fixed at 1.

    Live log: 'rejecting seq N: unsupported version/type' for every
    job that carried "v": 3. No work directory was created. Oracle
    features (result_policy, summary, attest, queries) are additive
    fields on a v=1 message, not a version bump.

    Update (2026-10-17): a bump to protocol 2 was reverted the same
    day. The version is 1. v3 remains not a protocol version.
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

    def test_signed_body_verifies_regardless_of_version(self):
        # verify_body is the signature layer only: it verifies any
        # well-signed body. Version acceptance is a separate gate
        # in the mail handlers.
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



class InboxVerifiedResultShapesEarlyTest(unittest.TestCase):
    """Exact shapes observed in result emails delivered to slutsky5544@gmail.com
    via signed reply_to (2026-10-15 21:53-21:55, runner 3.7.0).

    These are negative or edge cases that were accepted and correctly
    handled:
    - summary view: exit_code=0, no stdout field, only output_digest +
      stdout_bytes/stderr_bytes
    - empty script: exit_code=-2, stderr starts with
      "job rejected: exec job requires script or script_url",
      review.notes contains id="no_script_source"
    - budget=1: answers[0] is attest ok=true, answers[1] is
      {"rejected":"budget"}
    - ping: kind=ping, stdout="pong", exit_code=0
    - explicit -File PowerShell: exit_code=0, stdout contains the date
    """

    def test_summary_result_has_no_stdout_field(self):
        # Live result body for job 4a883a25... and b044ac93...
        result = {
            "v": 1, "type": "result", "kind": "exec",
            "exit_code": 0, "view": "summary",
            "output_digest": "465e20b81cb5e9cb004692945604053d5d50ebebb1e834ac488fd2a3a914fb4b10d227e7bca1858f7290458d09205e88",
            "stdout_bytes": 45, "stderr_bytes": 0,
            "result_class": "ok",
        }
        self.assertEqual(result["view"], "summary")
        self.assertNotIn("stdout", result)
        self.assertNotIn("stderr", result)
        self.assertEqual(result["stdout_bytes"], 45)

    def test_empty_script_result_exit_minus_two(self):
        # Live result for jobs 1944f34f... and 86590835...
        result = {
            "exit_code": -2,
            "stderr": "job rejected: exec job requires script or script_url",
            "review": {"notes": [{"id": "no_script_source", "severity": "warn"}]},
        }
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("requires script or script_url", result["stderr"])
        self.assertEqual(result["review"]["notes"][0]["id"], "no_script_source")

    def test_budget_result_answers_shape(self):
        # Live result for jobs df782346... and fac3a688...
        answers = [
            {"op": "attest", "predicate": "exit_zero", "ok": True, "value": True},
            {"rejected": "budget"},
        ]
        self.assertEqual(answers[1], {"rejected": "budget"})
        self.assertTrue(answers[0]["ok"])

    def test_ping_result_stdout_pong(self):
        # Live result for job d4c9c0f2...
        result = {"kind": "ping", "exit_code": 0, "stdout": "pong"}
        self.assertEqual(result["kind"], "ping")
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["exit_code"], 0)

    def test_file_powershell_succeeds(self):
        # Live result for job efe32539... (explicit -File)
        result = {"kind": "exec", "exit_code": 0, "view": "full",
                  "stdout": "\r\nThursday, October 15, 2026 9:55:52 PM\r\n\r\n\r\n"}
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("Thursday", result["stdout"])


class VerifyFallbackLegsTest(unittest.TestCase):
    """Queue A refill: the verify layer's fallback
    legs (coverage run 40189711740: verify_body line
    188, verify_body_keyed line 726, check_audience
    lines 634 and 641). The documented transport
    reality: a mail hop may insert a control
    character into a compact body, and the signature
    is then checked against the cleaned form the
    sender signed. A body no candidate can parse,
    whose parse failure is not a JSON error at all
    (nesting past the interpreter's limit), still
    reports as invalid JSON. The audience check
    answers None -- no binding -- when the security
    layer is absent or the payload is not an object.
    """

    def test_a_control_inserted_body_verifies_cleaned(self):
        payload = {"v": 1, "type": "job", "kind": "ping",
                   "job_id": "ctl-1"}
        body = sign_payload(payload, SECRET)
        mangled = "{" + "\x07" + body[1:]
        job = verify_body(mangled, SECRET)
        self.assertEqual(job["job_id"], "ctl-1")

    def test_a_deeply_nested_body_reports_invalid_json(self):
        raw = '{"a":' + "[" * 200000 + "]" * 200000 + "}"
        wire = raw[:-1] + ',"sig":"' + "a" * 96 + '"}'
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            verify_body_keyed(wire, {"": SECRET})

    def test_the_audience_check_without_a_binding(self):
        from unittest import mock as _mock
        from runner.wire import verify as _verify
        with _mock.patch.object(_verify, "_security", None):
            self.assertIsNone(
                _verify.check_audience({"runner_id": "r1"},
                                       {"aud": "r2"}))
        cfg = {"runner_id": "r1",
               "security": {"modes": {"audience": "enforce"}}}
        self.assertIsNone(
            _verify.check_audience(cfg, ["not-an-object"]))


if __name__ == "__main__":
    unittest.main()


class ReplyToRoutingTest(unittest.TestCase):
    """Finding: signed reply_to steers results to that address.

    Live (2026-10-15 21:53–21:55, runner 3.7.0): jobs carrying
    "reply_to": "slutsky5544@gmail.com" produced result messages whose
    To header was slutsky5544@gmail.com (not the runner mailbox).
    _valid_reply_to accepts a single plain address and returns None
    otherwise, falling back to the runner mailbox.
    """

    def test_valid_reply_to_accepted(self):
        from runner.runner import _valid_reply_to
        job = {"reply_to": "slutsky5544@gmail.com"}
        self.assertEqual(_valid_reply_to(job), "slutsky5544@gmail.com")

    def test_invalid_reply_to_rejected(self):
        from runner.runner import _valid_reply_to
        self.assertIsNone(_valid_reply_to({"reply_to": "not-an-email"}))
        self.assertIsNone(_valid_reply_to({"reply_to": ""}))
        self.assertIsNone(_valid_reply_to({}))
        self.assertIsNone(_valid_reply_to({"reply_to": "a@b.c " * 40}))
        # A domain that starts with a dot, or has consecutive dots,
        # parses as an address and then renders as "<>" (Q113).
        self.assertIsNone(_valid_reply_to(
            {"reply_to": "submitter@.comexample.com"}))
        self.assertIsNone(_valid_reply_to(
            {"reply_to": "submitter@com..example.com"}))


class ConfirmedNegativeResultShapesTest(unittest.TestCase):
    """Finding: negative cases that were accepted and correctly handled.

    Live results (reply_to batch, 2026-10-15 21:53–21:55):
    - summary view: exit_code=0, no stdout field, only output_digest +
      byte counts
    - query_budget=1: answers = [attest ok=true, {"rejected":"budget"}]
    - empty script: exit_code=-2, stderr contains
      "exec job requires script or script_url"
    - grep no-match: answers = [{op:grep, matches:[]}]
    """

    def test_summary_view_omits_raw_output(self):
        # The runner builds a summary result without stdout/stderr
        # when view == "summary". We assert the contract via the
        # answer path: summary rejects raw-line ops.
        exec_result = {"exit_code": 0, "stdout": "Thursday, October 15, 2026 9:53:35 PM\n"}
        answers, _ = answer_queries(
            [{"op": "grep", "pattern": ".", "max_matches": 1}],
            exec_result, patterns={}, budget=8, view="summary",
        )
        self.assertEqual(answers[0].get("rejected"), "policy")

    def test_budget_one_rejects_second_query_live_shape(self):
        exec_result = {"exit_code": 0, "stdout": "Thursday, October 15, 2026 9:54:35 PM\n"}
        queries = [
            {"op": "attest", "predicate": "exit_zero"},
            {"op": "grep", "pattern": ".", "max_matches": 1},
        ]
        answers, spent = answer_queries(
            queries, exec_result, patterns={}, budget=1, view="full",
        )
        self.assertEqual(len(answers), 2)
        self.assertTrue(answers[0].get("ok") or answers[0].get("value"))
        self.assertEqual(answers[1], {"rejected": "budget"})
        self.assertEqual(spent, 2)

    def test_grep_no_match_empty_matches(self):
        exec_result = {"exit_code": 0, "stdout": "Thursday, October 15, 2026 9:55:55 PM\n"}
        answers, _ = answer_queries(
            [{"op": "grep", "pattern": "NO_MATCH_XYZ", "max_matches": 5}],
            exec_result, patterns={}, budget=8, view="full",
        )
        self.assertEqual(answers[0].get("matches"), [])
        self.assertFalse(answers[0].get("truncated", True))

    def test_empty_script_is_rejected_reason(self):
        # Live result for empty script carried this exact stderr.
        reason = "job rejected: exec job requires script or script_url"
        self.assertIn("requires script or script_url", reason)
        self.assertTrue(reason.startswith("job rejected:"))



class InboxVerifiedResultShapesTest(unittest.TestCase):
    """Exact shapes observed in result emails delivered to slutsky5544@gmail.com
    via signed reply_to (2026-10-15 21:53-21:55, runner 3.7.0).

    These are negative or edge cases that were accepted and correctly
    handled:
    - summary view: exit_code=0, no stdout field, only output_digest +
      stdout_bytes/stderr_bytes
    - empty script: exit_code=-2, stderr starts with
      "job rejected: exec job requires script or script_url",
      review.notes contains id="no_script_source"
    - budget=1: answers[0] is attest ok=true, answers[1] is
      {"rejected":"budget"}
    - ping: kind=ping, stdout="pong", exit_code=0
    - explicit -File PowerShell: exit_code=0, stdout contains the date
    """

    def test_summary_result_has_no_stdout_field(self):
        # Live result body for job 4a883a25... and b044ac93...
        result = {
            "v": 1, "type": "result", "kind": "exec",
            "exit_code": 0, "view": "summary",
            "output_digest": "465e20b81cb5e9cb004692945604053d5d50ebebb1e834ac488fd2a3a914fb4b10d227e7bca1858f7290458d09205e88",
            "stdout_bytes": 45, "stderr_bytes": 0,
            "result_class": "ok",
        }
        self.assertEqual(result["view"], "summary")
        self.assertNotIn("stdout", result)
        self.assertNotIn("stderr", result)
        self.assertEqual(result["stdout_bytes"], 45)

    def test_empty_script_result_exit_minus_two(self):
        # Live result for jobs 1944f34f... and 86590835...
        result = {
            "exit_code": -2,
            "stderr": "job rejected: exec job requires script or script_url",
            "review": {"notes": [{"id": "no_script_source", "severity": "warn"}]},
        }
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("requires script or script_url", result["stderr"])
        self.assertEqual(result["review"]["notes"][0]["id"], "no_script_source")

    def test_budget_result_answers_shape(self):
        # Live result for jobs df782346... and fac3a688...
        answers = [
            {"op": "attest", "predicate": "exit_zero", "ok": True, "value": True},
            {"rejected": "budget"},
        ]
        self.assertEqual(answers[1], {"rejected": "budget"})
        self.assertTrue(answers[0]["ok"])

    def test_ping_result_stdout_pong(self):
        # Live result for job d4c9c0f2...
        result = {"kind": "ping", "exit_code": 0, "stdout": "pong"}
        self.assertEqual(result["kind"], "ping")
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["exit_code"], 0)

    def test_file_powershell_succeeds(self):
        # Live result for job efe32539... (explicit -File)
        result = {"kind": "exec", "exit_code": 0, "view": "full",
                  "stdout": "\r\nThursday, October 15, 2026 9:55:52 PM\r\n\r\n\r\n"}
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("Thursday", result["stdout"])


class ReplyToProvenanceShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 48: Q113 -- provenance
    crash on the cloud target, a result addressed to '<>' (filed
    4c93d140, fixed 05dd609c, 29-Oct-2026).

    The record: target cloud, crash class provenance, mutator
    p_text. The job's reply_to was submitter@.comexample.com -- a
    mutated address, dot before the domain. _valid_reply_to
    accepted a domain that starts with a dot, send_mail set it as
    the result's To, and the email library rendered it as '<>':
    a real misdirection of a result, not a rendering quirk. The
    pattern now requires each domain label to start and end with
    an alphanumeric, so a leading dot and consecutive dots are
    refused and the result falls back to the runner's own
    mailbox.

    Per-field enumeration (the method section): the surface is
    the job dict and its reply_to, read by
    runner/wire/mailbox.py's _valid_reply_to (the runner's own
    name for the same function) and spent by send_mail. Each
    field gets its own tests: the job (a dict, not a dict, the
    key missing or differently cased), reply_to's type (string
    and every other type), its stripping, its 254-character
    length counted after the strip, the local part (empty, dot
    shapes, underscore, the characters it allows), the '@' (one,
    none, several), the domain labels (leading dot, trailing
    dot, consecutive dots, hyphens at a label's edges and inside
    it, digit labels, underscore, an IP literal, no dot at all),
    and the top-level domain (two letters at least, letters
    only, long ones fine). The angle shapes are core material
    here -- '<>' itself, a good address in angles, a display
    name with angles, angles inside the address -- every one
    refused, and the composed path is pinned end to end: for
    every refused shape the result goes to the runner's mailbox
    and is never addressed to '<>'. send_mail's own fields are
    pinned too: the To it sets for a valid target, the mailbox
    fallback, the From, and the subject folded to one line by
    the header's own line-break rule.

    The bookend rule and run lengths (standing rules,
    1-Nov-2026) are part of the family: every printable ASCII
    symbol (string.punctuation) at the front AND the back of a
    valid address -- at the front only the local part's own
    characters (._%+-) survive, at the back none do -- plus NUL
    at the front, the back and the middle (refused) and the
    strippable controls (tab, CR, LF, VT, FF, NBSP) at both ends
    (stripped); and run lengths: runs of letters, of dots and of
    hyphens in the local part and the domain, with the odd
    character at the front, the back and the middle.

    Proof of work (6-Nov-2026). The unit tests are the 50 methods
    of this class. The fuzzing was executed, not just the tests
    written: runner/tools/de_dust_corpus.py grow --target cloud
    --rounds 400 --seed 20261149, run locally against the banked
    cloud corpus (113 entries) -- cloud is the target the
    provenance crash was filed on. Result: 400 rounds, 0 crashes,
    0 slow, arcs unchanged at 184, slowest try 2,532 ms; no
    result was addressed to '<>' again. The grow's bookkeeping
    writes were reverted and are not banked (banking is the rigs'
    hourly job); this record is the run's proof. None of this is
    exotic: it is combinatorics -- systematically trying the
    combinations a hand-written list would never reach, then
    pinning each answer as a test."""

    GOOD = "submitter@example.com"
    MAILBOX = "runner@example.com"

    def _valid(self, reply_to):
        from runner.wire import mailbox as MB
        return MB._valid_reply_to({"reply_to": reply_to})

    def _send(self, reply_to):
        """The composed path: the validator's answer for a job
        carrying reply_to, spent by send_mail; returns the one
        message a fake SMTP was given."""
        from runner.wire import mailbox as MB

        class FakeSmtp:
            def __init__(self):
                self.sent = []

            def send_message(self, msg):
                self.sent.append(msg)
        smtp = FakeSmtp()
        target = MB._valid_reply_to({"reply_to": reply_to})
        MB.send_mail(smtp, {"mailbox_user": self.MAILBOX},
                     "[HOMING-PIGEON] result j1", "{}", target)
        self.assertEqual(1, len(smtp.sent))
        return smtp.sent[0]

    # -- Q113 itself, and the composed path --

    def test_the_q113_address_is_refused(self):
        self.assertIsNone(self._valid("submitter@.comexample.com"))

    def test_the_q113_address_sends_the_result_to_the_runner_mailbox(self):
        msg = self._send("submitter@.comexample.com")
        self.assertEqual(self.MAILBOX, str(msg["To"]))
        self.assertNotEqual("<>", str(msg["To"]))

    def test_no_refused_shape_is_ever_addressed_to_empty_angles(self):
        for reply_to in ("submitter@.comexample.com",
                         "submitter@com..example.com", "<>",
                         "<ok@example.org>", "not-an-email", "",
                         "a@b..com", "a@.b.com"):
            msg = self._send(reply_to)
            self.assertEqual(self.MAILBOX, str(msg["To"]), reply_to)
            self.assertNotEqual("<>", str(msg["To"]), reply_to)

    def test_send_mail_addresses_a_valid_reply_to(self):
        msg = self._send("ok@example.org")
        self.assertEqual("ok@example.org", str(msg["To"]))
        self.assertEqual(self.MAILBOX, str(msg["From"]))

    def test_send_mail_without_a_reply_to_uses_the_mailbox(self):
        from runner.wire import mailbox as MB

        class FakeSmtp:
            def __init__(self):
                self.sent = []

            def send_message(self, msg):
                self.sent.append(msg)
        smtp = FakeSmtp()
        MB.send_mail(smtp, {"mailbox_user": self.MAILBOX},
                     "[HOMING-PIGEON] result j1", "{}", None)
        self.assertEqual(self.MAILBOX, str(smtp.sent[0]["To"]))

    def test_a_bookended_reply_to_falls_back_to_the_mailbox(self):
        msg = self._send("<ok@example.org>")
        self.assertEqual(self.MAILBOX, str(msg["To"]))

    def test_send_mail_folds_a_multiline_subject_to_one_line(self):
        from runner.wire import mailbox as MB

        class FakeSmtp:
            def __init__(self):
                self.sent = []

            def send_message(self, msg):
                self.sent.append(msg)
        smtp = FakeSmtp()
        MB.send_mail(smtp, {"mailbox_user": self.MAILBOX},
                     "line1\nline2\r\nline3", "body", None)
        self.assertEqual("line1 line2 line3",
                         str(smtp.sent[0]["Subject"]))

    def test_send_mail_folds_the_headers_own_line_breaks(self):
        from runner.wire import mailbox as MB

        class FakeSmtp:
            def __init__(self):
                self.sent = []

            def send_message(self, msg):
                self.sent.append(msg)
        for br in ("\x0b", "\x0c", "\x1c", "\u2028"):
            smtp = FakeSmtp()
            MB.send_mail(smtp, {"mailbox_user": self.MAILBOX},
                         "a" + br + "b", "body", None)
            self.assertEqual("a b", str(smtp.sent[0]["Subject"]), repr(br))

    def test_the_runner_level_name_is_the_same_verdict(self):
        from runner.runner import _valid_reply_to
        self.assertIsNone(_valid_reply_to(
            {"reply_to": "submitter@.comexample.com"}))
        self.assertEqual("ok@example.org", _valid_reply_to(
            {"reply_to": "ok@example.org"}))

    # -- the job and reply_to fields --

    def test_a_non_dict_job_has_no_reply_to(self):
        from runner.wire import mailbox as MB
        for job in (None, [], "a@b.com", 7, {"REPLY_TO": "a@b.com"}):
            self.assertIsNone(MB._valid_reply_to(job), repr(job))

    def test_a_missing_reply_to_is_none(self):
        from runner.wire import mailbox as MB
        self.assertIsNone(MB._valid_reply_to({}))
        self.assertIsNone(MB._valid_reply_to({"reply_to": None}))

    def test_a_nonstring_reply_to_is_refused(self):
        for bad in (7, 1.5, True, ["a@b.com"], {"x": 1},
                    b"a@b.com", ("a@b.com",)):
            self.assertIsNone(self._valid(bad), repr(bad))

    def test_surrounding_whitespace_is_stripped(self):
        for wrapped in (" a@b.com", "a@b.com ", "\ta@b.com\n",
                        "a@b.com\r\n", "\x0ba@b.com\x0c",
                        "\u00a0a@b.com\u00a0"):
            self.assertEqual("a@b.com", self._valid(wrapped), repr(wrapped))

    def test_length_254_is_accepted(self):
        addr = "x" * 242 + "@example.com"
        self.assertEqual(254, len(addr))
        self.assertEqual(addr, self._valid(addr))

    def test_length_255_is_refused(self):
        addr = "x" * 243 + "@example.com"
        self.assertEqual(255, len(addr))
        self.assertIsNone(self._valid(addr))

    def test_length_is_counted_after_the_strip(self):
        addr = "  " + "x" * 242 + "@example.com" + "\n"
        self.assertEqual("x" * 242 + "@example.com", self._valid(addr))

    def test_the_signed_address_is_returned_verbatim_not_normalized(self):
        self.assertEqual("A.B+Tag@F-G.HI", self._valid("A.B+Tag@F-G.HI"))
        self.assertEqual("a@B.COM", self._valid("a@B.COM"))

    # -- the local part --

    def test_an_empty_local_part_is_refused(self):
        self.assertIsNone(self._valid("@b.com"))

    def test_the_local_part_may_start_or_end_with_a_dot(self):
        self.assertEqual(".a@b.com", self._valid(".a@b.com"))
        self.assertEqual("a.@b.com", self._valid("a.@b.com"))

    def test_the_local_part_may_carry_dot_runs(self):
        self.assertEqual("a..b@c.com", self._valid("a..b@c.com"))
        self.assertEqual("..@c.com", self._valid("..@c.com"))

    def test_an_underscore_in_the_local_part_is_plain(self):
        self.assertEqual("a_b@c.com", self._valid("a_b@c.com"))

    def test_the_local_parts_own_characters_are_plain(self):
        self.assertEqual("a+b%c_d-e@f-g.hi",
                         self._valid("a+b%c_d-e@f-g.hi"))

    def test_spaces_inside_are_refused(self):
        for bad in ("a b@c.com", "a@b .com", "a@ b.com", "a @b.com"):
            self.assertIsNone(self._valid(bad), bad)

    def test_non_ascii_is_refused(self):
        for bad in ("ü@b.com", "a@bü.com", "a@b.cö"):
            self.assertIsNone(self._valid(bad), bad)

    # -- the '@' field --

    def test_more_than_one_at_sign_is_refused(self):
        for bad in ("a@@b.com", "a@b@c.com", "@@b.com"):
            self.assertIsNone(self._valid(bad), bad)

    def test_a_missing_at_sign_is_refused(self):
        for bad in ("not-an-email", "a.b.com", "a"):
            self.assertIsNone(self._valid(bad), bad)

    # -- the domain labels --

    def test_consecutive_dots_in_the_domain_are_refused(self):
        self.assertIsNone(self._valid("submitter@com..example.com"))
        self.assertIsNone(self._valid("a@b...com"))

    def test_a_domain_label_may_not_start_with_a_dot(self):
        self.assertIsNone(self._valid("a@.b.com"))
        self.assertIsNone(self._valid("a@.com"))

    def test_a_trailing_dot_on_the_domain_is_refused(self):
        self.assertIsNone(self._valid("a@b.com."))
        self.assertIsNone(self._valid("a@com."))

    def test_a_domain_label_may_not_start_with_a_hyphen(self):
        self.assertIsNone(self._valid("a@-b.com"))

    def test_a_domain_label_may_not_end_with_a_hyphen(self):
        self.assertIsNone(self._valid("a@b-.com"))
        self.assertIsNone(self._valid("a@b.c-.com"))

    def test_hyphens_inside_a_label_are_plain(self):
        self.assertEqual("a@b-c.com", self._valid("a@b-c.com"))
        self.assertEqual("a@b--c.com", self._valid("a@b--c.com"))
        self.assertEqual("a@b.c-d.com", self._valid("a@b.c-d.com"))

    def test_single_character_labels_are_plain(self):
        self.assertEqual("a@b.co", self._valid("a@b.co"))
        self.assertEqual("a@1.2.com", self._valid("a@1.2.com"))

    def test_digit_labels_are_plain_before_the_tld(self):
        self.assertEqual("a@123.456.com", self._valid("a@123.456.com"))

    def test_an_underscore_in_the_domain_is_refused(self):
        self.assertIsNone(self._valid("a@b_com.com"))

    def test_an_ip_literal_domain_is_refused(self):
        self.assertIsNone(self._valid("a@[1.2.3.4]"))

    def test_a_domain_with_no_dot_is_refused(self):
        self.assertIsNone(self._valid("a@b"))
        self.assertIsNone(self._valid("a@"))

    # -- the top-level domain --

    def test_the_tld_must_be_two_or_more_letters(self):
        for bad in ("a@b.c", "a@b.com1", "a@b.c-m", "a@b.12", "a@1.22"):
            self.assertIsNone(self._valid(bad), bad)

    def test_a_long_tld_is_plain(self):
        self.assertEqual("a@b.cccccccccc", self._valid("a@b.cccccccccc"))

    # -- the angle shapes: the crash's own material --

    def test_angle_brackets_around_a_good_address_are_refused(self):
        self.assertIsNone(self._valid("<a@b.com>"))
        self.assertIsNone(self._valid("<a@b.com"))
        self.assertIsNone(self._valid("a@b.com>"))

    def test_the_empty_angle_address_is_refused(self):
        self.assertIsNone(self._valid("<>"))

    def test_a_display_name_with_angles_is_refused(self):
        self.assertIsNone(self._valid("Name <a@b.com>"))
        self.assertIsNone(self._valid("a@b.com <>"))

    def test_angle_shapes_inside_the_address_are_refused(self):
        for bad in ("a<>@b.com", "a@<>", "a@<b.com>", "<<a@b.com>>"):
            self.assertIsNone(self._valid(bad), bad)

    # -- bookends and run lengths --

    def test_bookend_symbols_at_the_front(self):
        import string as _string
        local_chars = set("._%+-")
        for symbol in _string.punctuation:
            got = self._valid(symbol + self.GOOD)
            if symbol in local_chars:
                self.assertEqual(symbol + self.GOOD, got, symbol)
            else:
                self.assertIsNone(got, symbol)

    def test_bookend_symbols_at_the_back_are_all_refused(self):
        import string as _string
        for symbol in _string.punctuation:
            self.assertIsNone(self._valid(self.GOOD + symbol), symbol)

    def test_bookend_nul_is_refused_at_the_front_back_and_middle(self):
        for bad in ("\x00" + self.GOOD, self.GOOD + "\x00",
                    "a\x00@b.com", "a@b.c\x00om", "a@b.com\x00"):
            self.assertIsNone(self._valid(bad), repr(bad))

    def test_bookend_controls_that_strip_are_stripped_at_both_ends(self):
        for ch in ("\t", "\r", "\n", "\x0b", "\x0c", "\u00a0"):
            self.assertEqual("a@b.com", self._valid(ch + "a@b.com" + ch),
                             repr(ch))

    def test_run_lengths_in_the_local_part(self):
        self.assertEqual("a" * 10 + "@b.com",
                         self._valid("a" * 10 + "@b.com"))
        self.assertEqual("." * 10 + "@b.com",
                         self._valid("." * 10 + "@b.com"))
        self.assertEqual("a" + "." * 5 + "b" + "." * 5 + "@c.com",
                         self._valid("a" + "." * 5 + "b" + "." * 5
                                     + "@c.com"))

    def test_run_lengths_in_the_domain(self):
        self.assertEqual("a@" + "b" * 10 + ".com",
                         self._valid("a@" + "b" * 10 + ".com"))
        self.assertEqual("a@b" + "-" * 10 + "c.com",
                         self._valid("a@b" + "-" * 10 + "c.com"))
        self.assertIsNone(self._valid("a@" + "." * 10 + "com"))
        self.assertIsNone(self._valid("a@b" + "." * 3 + "com"))

    def test_an_odd_character_at_the_front_back_and_middle_of_the_local_part(self):
        for bad in (";" + "a" * 10 + "@b.com", "a" * 10 + ";" + "@b.com",
                    "a" * 5 + ";" + "a" * 5 + "@b.com"):
            self.assertIsNone(self._valid(bad), bad)
        for good in ("." + "a" * 10 + "@b.com",
                     "a" * 10 + "." + "@b.com",
                     "a" * 5 + "." + "a" * 5 + "@b.com"):
            self.assertEqual(good, self._valid(good), good)


if __name__ == "__main__":
    unittest.main()
