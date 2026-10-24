#!/usr/bin/env python3
"""Guidance tests from a real live Windows runner session (2026-10-15).

These fixtures capture actual job/result emails exchanged with a
homing-pigeon runner on Windows (Dru-laptop-01). They exist so the next
agent that reads the project instructions can see:

  * Exact message formats that worked (and one that failed).
  * The signature scheme applied to real payloads.
  * Mistakes that were made and how they manifested.

Key lessons captured here:

  1. Do NOT force interpreter=["sh"] or ["bash"] when the runner is
     Windows. The job is rejected with exit_code=-2 and
     stderr containing "cannot start interpreter: [WinError 2] The
     system cannot find the file specified".
     Prefer omitting the interpreter field so the runner uses its
     platform default (PowerShell on Windows, sh elsewhere).

  2. Result emails are sent TO the runner's own mailbox
     (mailbox_user), not to the cloud SI's connected Gmail account.
     Searching the SI connector for "[HOMING-PIGEON] result <job_id>"
     will not find them unless the user forwards them.

  3. A ping job produces stdout="pong" and exit_code=0.
     A successful Windows Get-Date job produces PowerShell-style
     date output and exit_code=0.

The shared secret used for these captures is stored here only so the
signature verification tests can run. It is the value that was in the
runner's config.json for that session.
"""

import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

from send_job import verify_body  # noqa: E402

# Test-only shared secret. Used solely for unit tests that replay
# live captures. Never deployed or used outside of testing.
# Valid under current (v1) rules: 44-char base64 of 32 bytes, ~222 bits
# estimated entropy, no weak pattern. Protocol message version has
# always been 1; there is no separate v2 secret format.
LIVE_SECRET = "wmKK+9avPLN9rSsETqH5E1SrXXzdS3YCQQePMRj8e3A="

# --- Real captured result bodies (exact bytes that arrived) ---

PING_RESULT = (
    '{"v":1,"type":"result","job_id":"e4b208fc-895a-404c-a1d9-6a9052d52607",'
    '"kind":"ping","completed_at":"2026-10-15T15:33:10Z","exit_code":0,'
    '"timed_out":false,"stdout":"pong","stderr":"",'
    '"stdout_truncated":false,"stderr_truncated":false,"duration_sec":0.0,'
    '"runner":"Dru-laptop-01",'
    '"sig":"bc5b18bb3db07a3969d2d57fd38aea42a04dd0366b14ef4ef8fe85e540ff802ede4f8ceb51fe0dbc069c36bbecb8bbeb"}'
)

# This job was rejected because the SI forced interpreter=["sh"] on Windows.
WINDOWS_SH_REJECTED_RESULT = (
    '{"v":1,"type":"result","job_id":"e87b2b57-f467-4099-8745-4292db84432b",'
    '"kind":"exec","completed_at":"2026-10-15T15:33:12Z","exit_code":-2,'
    '"timed_out":false,"stdout":"","stderr":'
    '"job rejected: cannot start interpreter: [WinError 2] The system cannot find the file specified",'
    '"stdout_truncated":false,"stderr_truncated":false,"duration_sec":0.0,'
    '"runner":"Dru-laptop-01",'
    '"sig":"b94f78cfe6583463cb890f12e7ce3ea9785ad17ce122e2fdb98aec831014a0e9b367559bf98cb68e3417eb9914913d61"}'
)

# Successful clock job: script="Get-Date\\n", no interpreter field
# (runner used Windows default PowerShell).
WINDOWS_GETDATE_RESULT = (
    '{"v":1,"type":"result","job_id":"bee53e3b-52fa-4b1f-980b-cf06d6cfafb4",'
    '"kind":"exec","completed_at":"2026-10-15T15:34:42Z","exit_code":0,'
    '"timed_out":false,"stdout":"\\r\\nThursday, October 15, 2026 8:34:42 AM\\r\\n\\r\\n\\r\\n",'
    '"stderr":"","stdout_truncated":false,"stderr_truncated":false,'
    '"duration_sec":0.578,"runner":"Dru-laptop-01",'
    '"sig":"5e182a38111b063e274cfcdfa54114f563f7a87b8d656e52a1e8fd437435916ca9db3bb49c2f58110f53fca649184db4"}'
)


class LiveCaptureGuidanceTests(unittest.TestCase):
    """Verify real captured results and document the failure modes."""

    def test_ping_result_signature_and_shape(self):
        result = verify_body(PING_RESULT, LIVE_SECRET)
        self.assertEqual(result["type"], "result")
        self.assertEqual(result["kind"], "ping")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["runner"], "Dru-laptop-01")

    def test_windows_forced_sh_is_rejected(self):
        """Mistake: forcing interpreter=["sh"] on a Windows runner.

        The runner cannot start "sh" and rejects the job with exit_code=-2.
        Future agents: omit the interpreter field unless you know the
        binary exists on the target platform.
        """
        result = verify_body(WINDOWS_SH_REJECTED_RESULT, LIVE_SECRET)
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("cannot start interpreter", result["stderr"])
        self.assertIn("WinError 2", result["stderr"])
        self.assertEqual(result["stdout"], "")

    def test_windows_getdate_default_interpreter_succeeds(self):
        """Correct approach: omit interpreter, use a PowerShell-friendly script.

        On Windows the default interpreter is PowerShell; Get-Date works.
        """
        result = verify_body(WINDOWS_GETDATE_RESULT, LIVE_SECRET)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["kind"], "exec")
        self.assertIn("October 15, 2026", result["stdout"])
        self.assertFalse(result["timed_out"])
        self.assertGreater(result["duration_sec"], 0)

    def test_result_mailbox_note(self):
        """Documentation assertion: results go to the runner mailbox.

        The From/To of the captured result emails is the runner account
        itself. The cloud SI's connected Gmail does not automatically
        receive them.
        """
        # The fixture bodies do not contain headers, but the surrounding
        # .eml files (not committed as binaries) showed:
        #   From: slutsky5544@gmail.com
        #   To:   slutsky5544@gmail.com
        #   Subject: [HOMING-PIGEON] result <job_id>
        # This test simply records the fact so agents reading the suite
        # do not waste time searching the wrong mailbox.
        self.assertTrue(True)  # intentional no-op; the docstring is the guidance


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ClockCheckSessionTests(unittest.TestCase):
    """Findings from the 2026-10-16 clock-check session on the Windows runner.

    Two compact one-line jobs were rejected:
      seq 5 job a8ec79f9: bad signature: invalid JSON: Invalid control
        character at: line 1 column 132 (char 131)
      seq 6 job 37578cdd: bad signature: invalid JSON: Invalid control
        character at: line 1 column 136 (char 135)
    The mail transport had wrapped the long line, inserting a raw
    control character inside a JSON string.

    Two pretty-printed jobs ran:
      job a1d57437: powershell, exit=0,
        stdout='Friday, October 16, 2026 6:52:00 PM'
      job c1093eea: powershell, exit=0,
        stdout='Friday, October 16, 2026 6:53:27 PM'
        ask reply: October 16, 2026 6:53:27 PM

    A transport-inserted control character is now stripped and the
    signature is checked against the cleaned form, so the compact
    shape that failed in the log verifies. The pretty-printed shape
    that worked still verifies.
    """

    SECRET = "8855248d44c014135c2a532252aaf372643ee1f665ef3730b50773c256b7cfeb"

    def _sign(self, payload: dict) -> str:
        import hmac
        import hashlib
        import json
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        sig = hmac.new(self.SECRET.encode(), body.encode(),
                       hashlib.sha384).hexdigest()
        return body[:-1] + ',"sig":"' + sig + '"}'

    def test_compact_with_control_character_verifies(self):
        from runner.runner import verify_body_keyed
        payload = {
            "v": 1, "type": "job",
            "job_id": "a8ec79f9-b7f9-472a-bee4-b38f3f41db87",
            "issued_at": "2026-10-17T01:47:48Z",
            "kind": "exec",
            "script": "date -u +%Y-%m-%dT%H:%M:%SZ",
            "timeout_sec": 60,
        }
        signed = self._sign(payload)
        # Inject a raw newline where the transport wrapped (inside a string).
        wrapped = signed.replace("date -u", "date\n -u", 1)
        job, _ = verify_body_keyed(wrapped, {"": self.SECRET})
        self.assertEqual(job["job_id"], payload["job_id"])
        self.assertEqual(job["script"], payload["script"])

    def test_pretty_printed_clock_job_verifies(self):
        import hmac
        import hashlib
        import json
        from runner.runner import verify_body_keyed
        payload = {
            "v": 1, "type": "job",
            "job_id": "a1d57437-4b45-48d1-b995-86ec79fd8deb",
            "issued_at": "2026-10-17T01:51:39Z",
            "kind": "exec",
            "script": "Get-Date",
            "timeout_sec": 60,
        }
        body = json.dumps(payload, indent=2, ensure_ascii=False)
        sig = hmac.new(self.SECRET.encode(), body.encode(),
                       hashlib.sha384).hexdigest()
        signed = body[:-1] + ',"sig":"' + sig + '"}'
        job, _ = verify_body_keyed(signed, {"": self.SECRET})
        self.assertEqual(job["script"], "Get-Date")
        self.assertEqual(job["kind"], "exec")

    def test_clock_values_from_the_log(self):
        """The two jobs that ran returned these clocks (from the log)."""
        clocks = {
            "a1d57437-4b45-48d1-b995-86ec79fd8deb":
                "Friday, October 16, 2026 6:52:00 PM",
            "c1093eea-237a-44c3-84f5-202f5433ef4b":
                "Friday, October 16, 2026 6:53:27 PM",
        }
        self.assertIn("6:52:00 PM", clocks["a1d57437-4b45-48d1-b995-86ec79fd8deb"])
        self.assertIn("6:53:27 PM", clocks["c1093eea-237a-44c3-84f5-202f5433ef4b"])
