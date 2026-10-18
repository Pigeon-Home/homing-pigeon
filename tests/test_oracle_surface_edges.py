"""Policy, ask-fallback, tool, and Oracle-surface edge branches.

The full-suite coverage run on 96c1748 left a scatter of single
branches unexercised around the Oracle path: the redaction loop's
two skips (a non-string pattern, an uncompilable regex), the ask
guard's answerless re-ask and junk-cap fallback, the tool runner's
validation and cap arithmetic, the oracle log's one-time announce,
and the window's Host/Origin gate. Each test here names the branch
it pins.
"""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

from runner import runner as R


class PolicyRedactionTest(unittest.TestCase):
    def _run(self, patterns, stdout="secret-42 and secret-7"):
        cfg = {"max_result_view": "full"}
        job = {"job_id": "j1", "kind": "exec",
               "result_policy": {"view": "redacted"}}
        exe = {"stdout": stdout, "stderr": "", "exit_code": 0}
        return R.apply_result_policy(cfg, job, exe, patterns, False)

    def test_bad_patterns_are_skipped_good_ones_still_redact(self):
        patterns = {"good": r"secret-\d+", "not_a_string": 123,
                    "broken": r"([a-z"}
        result, retain = self._run(patterns)
        self.assertTrue(retain)
        self.assertEqual(result["stdout"],
                         "[REDACTED:good] and [REDACTED:good]")
        self.assertEqual(result["redacted_families"], ["good"])
        self.assertEqual(result["stderr"], "")

    def test_redacted_view_with_no_match_keeps_output(self):
        result, _ = self._run({"absent": r"zzz-\d+"}, stdout="plain text")
        self.assertEqual(result["stdout"], "plain text")
        self.assertEqual(result["redacted_families"], [])

    def test_non_dict_patterns_are_treated_as_empty(self):
        result, _ = self._run(None, stdout="secret-42")
        self.assertEqual(result["stdout"], "secret-42")
        self.assertEqual(result["redacted_families"], [])

    def test_families_are_recorded_in_pattern_order(self):
        patterns = {"beta": r"B\d", "alpha": r"A\d"}
        result, _ = self._run(patterns, stdout="A1 B2")
        self.assertEqual(result["redacted_families"], ["beta", "alpha"])
        self.assertEqual(result["stdout"],
                         "[REDACTED:alpha] [REDACTED:beta]")


class AskModelFallbackTest(unittest.TestCase):
    # A whole-reply JSON object carrying two index field names is
    # what the format guard calls a dump (see _answer_format_problem).
    DUMP = '{"job_status": "ok", "job_ids": "x"}'

    def _ask(self, replies, max_chars=2000):
        with mock.patch.object(R, "_ask_model_once",
                               side_effect=replies) as once:
            out = R.ask_model({}, "q?", "ctx", max_chars)
        return out, once

    def test_clean_first_answer_never_reasks(self):
        out, once = self._ask([{"answer": "All quiet."}])
        self.assertEqual(out, {"answer": "All quiet."})
        self.assertEqual(once.call_count, 1)

    def test_clean_reask_is_returned(self):
        out, once = self._ask([{"answer": self.DUMP},
                               {"answer": "One job ran."}])
        self.assertEqual(out, {"answer": "One job ran."})
        self.assertEqual(once.call_count, 2)

    def test_answerless_reask_passes_through_unchanged(self):
        rejection = {"rejected": "inference_error"}
        out, _ = self._ask([{"answer": self.DUMP}, rejection])
        self.assertIs(out, rejection)

    def test_double_format_failure_uses_the_fallback_sentence(self):
        out, _ = self._ask([{"answer": self.DUMP},
                            {"answer": self.DUMP}])
        self.assertEqual(out["answer"], R._FORMAT_FALLBACK_ANSWER)

    def test_junk_cap_falls_back_to_2000_for_the_fallback(self):
        for junk in ("wide", None):
            out, _ = self._ask([{"answer": self.DUMP},
                                {"answer": self.DUMP}], max_chars=junk)
            self.assertEqual(out["answer"], R._FORMAT_FALLBACK_ANSWER)

    def test_first_rejection_is_not_a_format_problem(self):
        rejection = {"rejected": "sanitization"}
        out, once = self._ask([rejection])
        self.assertIs(out, rejection)
        self.assertEqual(once.call_count, 1)


class OracleToolTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, text):
        path = os.path.join(self.base, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_args_must_be_an_object(self):
        self.assertEqual(R._run_oracle_tool("read_file", None, self.base),
                         "error: args must be an object")
        self.assertEqual(R._run_oracle_tool("read_file", ["x"], self.base),
                         "error: args must be an object")

    def test_unknown_tool_is_an_error_string(self):
        out = R._run_oracle_tool("delete_everything", {}, self.base)
        self.assertTrue(out.startswith("error:"), out)

    def test_read_file_requires_a_path(self):
        for args in ({}, {"path": ""}, {"path": 7}):
            out = R._run_oracle_tool("read_file", args, self.base)
            self.assertEqual(out, "error: path must be a non-empty string")

    def test_read_file_refuses_to_leave_the_state_dir(self):
        out = R._run_oracle_tool(
            "read_file", {"path": "../outside.txt"}, self.base)
        self.assertEqual(out, "error: path leaves the state dir")

    def test_read_file_missing_file_reports_cannot_read(self):
        out = R._run_oracle_tool(
            "read_file", {"path": "nope.txt"}, self.base)
        self.assertTrue(out.startswith("error: cannot read"), out)

    def test_read_file_empty_file_is_named(self):
        self._write("empty.txt", "")
        self.assertEqual(R._run_oracle_tool(
            "read_file", {"path": "empty.txt"}, self.base), "(empty file)")

    def test_read_file_truncates_at_max_chars(self):
        self._write("long.txt", "a" * 500)
        out = R._run_oracle_tool(
            "read_file", {"path": "long.txt", "max_chars": 100}, self.base)
        self.assertTrue(out.endswith("...[truncated]"))
        self.assertLessEqual(len(out), 100 + len("\n...[truncated]"))

    def test_read_file_bool_and_junk_caps_use_the_default(self):
        self._write("mid.txt", "b" * 3000)
        for cap in (True, "junk", None):
            out = R._run_oracle_tool(
                "read_file", {"path": "mid.txt", "max_chars": cap},
                self.base)
            self.assertEqual(len(out), 3000)

    def test_read_file_cap_is_clamped_to_20000(self):
        self._write("big.txt", "c" * 21000)
        out = R._run_oracle_tool(
            "read_file", {"path": "big.txt", "max_chars": 10 ** 9},
            self.base)
        self.assertTrue(out.endswith("...[truncated]"))
        self.assertLessEqual(len(out), 20000 + len("\n...[truncated]"))

    def test_list_dir_marks_subdirs_and_names_empty(self):
        os.makedirs(os.path.join(self.base, "sub"))
        self._write("file.txt", "x")
        out = R._run_oracle_tool("list_dir", {"path": "."}, self.base)
        self.assertIn("sub/", out)
        self.assertIn("file.txt", out)
        empty = os.path.join(self.base, "empty")
        os.makedirs(empty)
        self.assertEqual(R._run_oracle_tool(
            "list_dir", {"path": "empty"}, self.base), "(empty directory)")

    def test_list_dir_caps_at_200_entries(self):
        for i in range(205):
            self._write(f"f{i:03d}.txt", "")
        out = R._run_oracle_tool("list_dir", {"path": "."}, self.base)
        self.assertIn("...[5 more]", out)

    def test_list_dir_isdir_failure_keeps_the_entry(self):
        self._write("file.txt", "x")
        with mock.patch.object(os.path, "isdir",
                               side_effect=OSError("raced away")):
            out = R._run_oracle_tool("list_dir", {"path": "."}, self.base)
        self.assertIn("file.txt", out)

    def test_list_dir_missing_path_reports_cannot_list(self):
        out = R._run_oracle_tool(
            "list_dir", {"path": "nope"}, self.base)
        self.assertTrue(out.startswith("error: cannot list"), out)

    def test_write_file_validation(self):
        cases = [
            ({"path": "", "content": "x"}, "path must be a non-empty"),
            ({"path": "a.txt", "content": 5}, "content must be a string"),
            ({"path": "../esc.txt", "content": "x"}, "leaves the state dir"),
            ({"path": "a.txt", "content": "x" * 200001}, "too large"),
        ]
        for args, fragment in cases:
            out = R._run_oracle_tool("write_file", args, self.base)
            self.assertTrue(out.startswith("error:"), out)
            self.assertIn(fragment, out)

    def test_write_file_at_the_cap_and_roundtrip(self):
        out = R._run_oracle_tool(
            "write_file", {"path": "deep/nested/a.txt",
                           "content": "z" * 200000}, self.base)
        self.assertFalse(out.startswith("error:"), out)
        back = R._run_oracle_tool(
            "read_file", {"path": "deep/nested/a.txt",
                          "max_chars": 20000}, self.base)
        self.assertTrue(back.startswith("z" * 100))


class OracleLogBitsTest(unittest.TestCase):
    def test_log_settings_default_for_non_dict_cfg(self):
        max_bytes, backups = R._oracle_log_settings(None)
        self.assertEqual(max_bytes, R._ORACLE_LOG_DEFAULT_MAX_BYTES)
        self.assertGreaterEqual(backups, 0)

    def test_log_settings_junk_values_use_defaults(self):
        max_bytes, _ = R._oracle_log_settings(
            {"oracle_log_max_bytes": "enormous"})
        self.assertEqual(max_bytes, R._ORACLE_LOG_DEFAULT_MAX_BYTES)

    def test_announce_logs_once(self):
        old = (R._ORACLE_LOG_ENABLED, R._ORACLE_LOG_PATH,
               R._ORACLE_LOG_ANNOUNCED)
        lines = []
        try:
            R._ORACLE_LOG_ENABLED = True
            R._ORACLE_LOG_PATH = "/somewhere/oracle.log"
            R._ORACLE_LOG_ANNOUNCED = False
            with mock.patch.object(R, "log",
                                   side_effect=lambda *a, **k:
                                   lines.append(a)):
                R._announce_oracle_log()
                R._announce_oracle_log()
        finally:
            (R._ORACLE_LOG_ENABLED, R._ORACLE_LOG_PATH,
             R._ORACLE_LOG_ANNOUNCED) = old
        self.assertEqual(len(lines), 1)
        self.assertIn("/somewhere/oracle.log", lines[0][0])

    def test_log_record_swallows_unserializable_records(self):
        record = {}
        record["self"] = record
        with mock.patch.object(R, "append_bounded_log") as append, \
                mock.patch.object(R, "_ORACLE_LOG_ENABLED", True), \
                mock.patch.object(R, "_ORACLE_LOG_PATH", "/x/oracle.log"):
            R._oracle_log_record(record)  # must not raise
        append.assert_not_called()

    def test_log_record_disabled_writes_nothing(self):
        with mock.patch.object(R, "append_bounded_log") as append, \
                mock.patch.object(R, "_ORACLE_LOG_ENABLED", False):
            R._oracle_log_record({"a": 1})
        append.assert_not_called()


class _Handler:
    def __init__(self, peer, headers):
        self.client_address = (peer, 12345)
        self.headers = headers


class OracleHostOkTest(unittest.TestCase):
    def test_non_loopback_peer_is_refused(self):
        h = _Handler("203.0.113.9", {"Host": "127.0.0.1"})
        self.assertFalse(R._oracle_host_ok(h))

    def test_foreign_host_header_is_refused(self):
        h = _Handler("127.0.0.1", {"Host": "evil.example"})
        self.assertFalse(R._oracle_host_ok(h))

    def test_loopback_host_with_port_is_ok(self):
        h = _Handler("127.0.0.1", {"Host": "127.0.0.1:11436"})
        self.assertTrue(R._oracle_host_ok(h))

    def test_bracketed_ipv6_host_is_ok(self):
        h = _Handler("::1", {"Host": "[::1]:11436"})
        self.assertTrue(R._oracle_host_ok(h))

    def test_localhost_origin_over_http_is_ok(self):
        h = _Handler("127.0.0.1", {"Host": "localhost",
                                   "Origin": "http://localhost:11436"})
        self.assertTrue(R._oracle_host_ok(h))

    def test_https_origin_is_refused(self):
        h = _Handler("127.0.0.1", {"Host": "localhost",
                                   "Origin": "https://127.0.0.1"})
        self.assertFalse(R._oracle_host_ok(h))

    def test_foreign_origin_is_refused(self):
        h = _Handler("127.0.0.1", {"Host": "localhost",
                                   "Origin": "http://evil.example"})
        self.assertFalse(R._oracle_host_ok(h))


class OraclePageTest(unittest.TestCase):
    def test_unstringifiable_token_becomes_empty(self):
        class Bad:
            def __str__(self):
                raise RuntimeError("no")
        page = R.oracle_page(Bad(), None, "yes")
        self.assertIn('"token": ""', page)
        self.assertIn('"model": ""', page)
        self.assertIn('"ready": true', page)

    def test_angle_brackets_are_escaped_in_the_payload(self):
        page = R.oracle_page("t<k", "m", False)
        self.assertIn("t\\u003ck", page)
        self.assertIn('"ready": false', page)


class OracleWindowPortTest(unittest.TestCase):
    def test_non_integer_port_is_an_error(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = R.oracle_window({}, port="abc")
        self.assertEqual(rc, 2)
        self.assertIn("must be an integer", err.getvalue())

    def test_out_of_range_ports_are_errors(self):
        for port in (-1, 65536):
            with redirect_stderr(io.StringIO()):
                self.assertEqual(R.oracle_window({}, port=port), 2)


if __name__ == "__main__":
    unittest.main()
