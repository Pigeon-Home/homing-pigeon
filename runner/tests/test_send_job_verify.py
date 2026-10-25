#!/usr/bin/env python3
"""Queue A: `send_job.py verify`, the sender's side of a result.

The coverage map (run 40180268696) showed cmd_verify never
ran on either platform: the command a cloud SI uses to check
a result that came back -- verify the signature, decrypt the
envelope when there is one, print the payload -- had no test
at all. Its contract, from the module docstring and the code:

  - a body whose signature verifies prints as JSON on
    stdout and exits 0, whether it arrives on stdin or in a
    file;
  - a body that does not verify is INVALID on stderr and
    exit 1 -- a wrong secret, a tampered body, plain
    garbage;
  - an encryption envelope without --job-id is INVALID
    with the reason named (the job id lives in the subject,
    not the envelope); with the right --job-id it decrypts
    and the inner signed body is what prints; with the
    wrong one it is INVALID;
  - a result whose oracle_opinion records a repair adds
    one plain line on stderr saying what was received and
    what ran (or that the repair was refused); stdout stays
    the JSON.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.cloud import send_job  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402

SECRET = "verify-test-secret-0123456789abcdef"
OTHER = "verify-test-other-secret-fedcba9876543210"
JOB_ID = "verify-job-0001"

RESULT = {"v": 1, "type": "result", "job_id": JOB_ID,
          "ok": True, "stdout": "hello back\n", "stderr": ""}


def _verify(argv, stdin_text=""):
    out, err = io.StringIO(), io.StringIO()
    full = ["send_job.py", "verify", "--secret", SECRET] + argv
    with mock.patch.object(sys, "argv", full), \
            mock.patch.object(sys, "stdin", io.StringIO(stdin_text)):
        with redirect_stdout(out), redirect_stderr(err):
            rc = send_job.main()
    return rc, out.getvalue(), err.getvalue()


def _envelope(payload, job_id=JOB_ID, secret=SECRET):
    return jobcrypto.encrypt_body(
        send_job.sign_payload(payload, secret), secret,
        job_id=job_id, key_id="", sign=send_job.sign_payload)


class VerifyTest(unittest.TestCase):
    def test_a_signed_result_from_stdin_prints(self):
        body = send_job.sign_payload(RESULT, SECRET)
        rc, out, err = _verify([], stdin_text=body)
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out), RESULT)
        self.assertNotIn("INVALID", err)
        self.assertNotIn("repair:", err)

    def test_a_signed_result_from_a_file_prints(self):
        body = send_job.sign_payload(RESULT, SECRET)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "result.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
            rc, out, err = _verify([path])
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out), RESULT)

    def test_a_wrong_secret_is_invalid(self):
        body = send_job.sign_payload(RESULT, OTHER)
        rc, out, err = _verify([], stdin_text=body)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("INVALID:", err)

    def test_a_tampered_body_is_invalid(self):
        body = send_job.sign_payload(RESULT, SECRET)
        body = body.replace("hello back", "hello jack")
        rc, _out, err = _verify([], stdin_text=body)
        self.assertEqual(rc, 1)
        self.assertIn("INVALID:", err)

    def test_garbage_is_invalid(self):
        rc, _out, err = _verify([], stdin_text="not a signed body")
        self.assertEqual(rc, 1)
        self.assertIn("INVALID:", err)

    def test_an_envelope_without_a_job_id_is_invalid(self):
        rc, _out, err = _verify([], stdin_text=_envelope(RESULT))
        self.assertEqual(rc, 1)
        self.assertIn("--job-id", err)

    def test_an_envelope_with_its_job_id_decrypts(self):
        rc, out, err = _verify(["--job-id", JOB_ID],
                               stdin_text=_envelope(RESULT))
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out), RESULT)

    def test_an_envelope_with_the_wrong_job_id_is_invalid(self):
        rc, _out, err = _verify(["--job-id", "some-other-job"],
                                stdin_text=_envelope(RESULT))
        self.assertEqual(rc, 1)
        self.assertIn("INVALID:", err)

    def test_a_repair_is_one_line_on_stderr(self):
        payload = dict(RESULT)
        payload["oracle_opinion"] = {
            "repaired": True, "received_digest": "sha384:abc123"}
        body = send_job.sign_payload(payload, SECRET)
        rc, out, err = _verify([], stdin_text=body)
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out), payload)
        self.assertIn("repair: received sha384:abc123", err)
        self.assertIn("ran: hello back", err)

    def test_a_refused_repair_says_so_on_stderr(self):
        payload = dict(RESULT)
        payload["oracle_opinion"] = {"repaired": False}
        body = send_job.sign_payload(payload, SECRET)
        rc, _out, err = _verify([], stdin_text=body)
        self.assertEqual(rc, 0, err)
        self.assertIn("repair: refused", err)


if __name__ == "__main__":
    unittest.main()
