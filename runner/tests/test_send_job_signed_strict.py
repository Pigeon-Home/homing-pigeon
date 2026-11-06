# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""send_job's verifier reads a signed body with the runner's own
strict reader (the do-now follow-up).

runner/wire/verify.py parses every signed body it checks with
runner.guard.textutil.loads_signed: duplicate member names are
refused by its object_pairs_hook and the raw bracket depth is
scanned before the parse. send_job.verify_body carried its own
parse instead -- same constant and float refusals, but no
object_pairs_hook, so a correctly signed body carrying one name
twice verified here (last value wins) while the runner refused
the same body: two readers of one signed body disagreed, the
parser differential the shared hook exists to close. send_job
now parses through the shared loads_signed, and this file pins
the sender-side reader to the shared behaviour.
"""

import hashlib
import hmac
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.cloud import send_job  # noqa: E402
from runner.guard import textutil as TU  # noqa: E402

SECRET = "sendjob-strict-secret-0123456789abcdef"
LIMIT = TU.NESTING_LIMIT


def sign_raw(raw, secret=SECRET):
    """Sign an exact raw object text the way sign_payload signs a
    dict: HMAC over the normalized text, trailing brace replaced
    by the sig member. A dict cannot carry a duplicate name, so
    the duplicate bodies below are built as raw text and signed
    over exactly that text."""
    sig = hmac.new(secret.encode("utf-8"),
                   send_job.normalize(raw).encode("utf-8"),
                   hashlib.sha384).hexdigest()
    return raw[:-1] + ',"sig":"' + sig + '"}'


class DuplicateNamesTest(unittest.TestCase):
    def assert_duplicate(self, raw, key):
        with self.assertRaises(ValueError) as caught:
            send_job.verify_body(sign_raw(raw), SECRET)
        message = str(caught.exception)
        self.assertIn("duplicate", message)
        self.assertIn(key, message)

    def test_duplicate_at_the_top_level_is_refused_and_named(self):
        self.assert_duplicate(
            '{"v": 1, "type": "result", "ok": true, "ok": false}',
            "ok")

    def test_duplicate_nested_in_an_object_is_refused(self):
        self.assert_duplicate(
            '{"v": 1, "outer": {"x": 1, "x": 2}}', "x")

    def test_duplicate_in_an_object_inside_an_array_is_refused(self):
        self.assert_duplicate(
            '{"v": 1, "list": [1, {"k": 1, "k": 2}, 3]}', "k")

    def test_a_unicode_escaped_spelling_of_a_name_is_a_duplicate(self):
        self.assert_duplicate(
            '{"v": 1, "ok": true, "\\u006fk": false}', "ok")

    def test_duplicate_names_bookended_with_symbols(self):
        for key in ("-ok-", ";ok;", "--ok--"):
            raw = '{"%s": 1, "%s": 2}' % (key, key)
            self.assert_duplicate(raw, key)

    def test_the_refusal_is_the_shared_readers_wording(self):
        raw = '{"v": 1, "ok": true, "ok": false}'
        with self.assertRaises(ValueError) as shared:
            TU.loads_signed(raw)
        with self.assertRaises(ValueError) as sender:
            send_job.verify_body(sign_raw(raw), SECRET)
        self.assertEqual(str(sender.exception), str(shared.exception))

    def test_the_same_name_in_different_objects_still_verifies(self):
        raw = ('{"v": 1, "a": {"k": 1}, "b": [{"k": 2}, {"k": 3}],'
               ' "k": 4}')
        self.assertEqual(send_job.verify_body(sign_raw(raw), SECRET),
                         {"v": 1, "a": {"k": 1},
                          "b": [{"k": 2}, {"k": 3}], "k": 4})

    def test_names_differing_only_by_case_still_verify(self):
        raw = '{"v": 1, "ok": true, "OK": false}'
        self.assertEqual(send_job.verify_body(sign_raw(raw), SECRET),
                         {"v": 1, "ok": True, "OK": False})


class SharedReaderParityTest(unittest.TestCase):
    """For every raw body, the sender's verifier and the runner's
    reader agree: both accept with the same value, or both refuse
    with the same message."""

    CASES = (
        '{"v": 1, "type": "result", "ok": true}',
        '{"v": 1, "ok": true, "ok": false}',
        '{"v": 1, "outer": {"x": 1, "x": 2}}',
        '{"v": 1, "x": NaN}',
        '{"v": 1, "x": Infinity}',
        '{"v": 1, "x": 1e400}',
        '{"v": 1, "s": "text", "n": -0, "f": 1.5e3, "u": null}',
    )

    def test_outcomes_match_the_shared_reader(self):
        for raw in self.CASES:
            try:
                expected = TU.loads_signed(raw)
                expected_error = None
            except ValueError as exc:
                expected, expected_error = None, str(exc)
            try:
                got = send_job.verify_body(sign_raw(raw), SECRET)
                got_error = None
            except ValueError as exc:
                got, got_error = None, str(exc)
            self.assertEqual(got_error, expected_error, raw)
            if expected_error is None:
                self.assertEqual(got, expected, raw)


class NestingPreScanTest(unittest.TestCase):
    def test_nesting_past_the_limit_is_refused(self):
        raw = '{"a":' * (LIMIT + 1) + "1" + "}" * (LIMIT + 1)
        with self.assertRaisesRegex(ValueError, "nests deeper than"):
            send_job.verify_body(sign_raw(raw), SECRET)

    def test_a_raw_wall_of_brackets_is_refused_as_nesting(self):
        raw = '{"a": ' + "[" * 5000 + "]" * 5000 + "}"
        with self.assertRaises(ValueError) as caught:
            send_job.verify_body(sign_raw(raw), SECRET)
        self.assertIn("nests deeper than", str(caught.exception))
        self.assertIn(str(LIMIT), str(caught.exception))

    def test_nesting_at_the_limit_still_verifies(self):
        raw = '{"a":' * LIMIT + "1" + "}" * LIMIT
        value = send_job.verify_body(sign_raw(raw), SECRET)
        for _ in range(LIMIT):
            value = value["a"]
        self.assertEqual(value, 1)

    def test_brackets_inside_strings_do_not_count(self):
        wall = "[" * 5000 + "]" * 5000
        raw = '{"v": 1, "note": "%s"}' % wall
        self.assertEqual(send_job.verify_body(sign_raw(raw), SECRET),
                         {"v": 1, "note": wall})


class ExistingRefusalsTest(unittest.TestCase):
    def test_a_lone_surrogate_is_still_refused(self):
        raw = '{"v": 1, "s": "\\ud800"}'
        with self.assertRaisesRegex(ValueError, "surrogate"):
            send_job.verify_body(sign_raw(raw), SECRET)

    def test_a_signature_mismatch_is_still_refused_first(self):
        raw = '{"v": 1, "ok": true, "ok": false}'
        body = sign_raw(raw, secret="some-other-secret-0123456789")
        with self.assertRaisesRegex(ValueError, "signature mismatch"):
            send_job.verify_body(body, SECRET)


class VerifyCommandTest(unittest.TestCase):
    def test_verify_command_reports_a_duplicate_body_invalid(self):
        raw = '{"v": 1, "type": "result", "ok": true, "ok": false}'
        out, err = io.StringIO(), io.StringIO()
        argv = ["send_job.py", "verify", "--secret", SECRET]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(sys, "stdin",
                                  io.StringIO(sign_raw(raw))):
            with redirect_stdout(out), redirect_stderr(err):
                rc = send_job.main()
        self.assertEqual(rc, 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("INVALID:", err.getvalue())
        self.assertIn("duplicate", err.getvalue())

    def test_verify_command_still_prints_a_clean_body(self):
        payload = {"v": 1, "type": "result", "ok": True}
        body = send_job.sign_payload(payload, SECRET)
        out, err = io.StringIO(), io.StringIO()
        argv = ["send_job.py", "verify", "--secret", SECRET]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(sys, "stdin", io.StringIO(body)):
            with redirect_stdout(out), redirect_stderr(err):
                rc = send_job.main()
        self.assertEqual(rc, 0, err.getvalue())
        self.assertEqual(json.loads(out.getvalue()), payload)


if __name__ == "__main__":
    unittest.main()
