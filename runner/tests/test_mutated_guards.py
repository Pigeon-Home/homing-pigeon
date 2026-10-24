"""Mutations of the guards the recent suites already pin.

Each case starts from a known input and changes one thing: a field,
a quote, a mode, a bound. Nothing here calls execute_job, starts a
process, or touches the job-user syscalls.
"""
import json
import os
import tempfile
import unittest

from runner.guard import security as S
from runner.runner import _answer_format_problem

# The field-report dump, then one-field mutations of it.
_DUMP = {
    "job_status": "Summary",
    "newest_job_index": "c1093eea-237a-44c3-84f5-202f5433ef4b",
    "job_ids": ["c1093eea-237a-44c3-84f5-202f5433ef4b"],
    "total_job_count": 7,
    "current_job_count": 1,
}

# 32 chars, mixed case so it is not a repeated unit. Estimates above 128 bits.
_STRONG = "0123456789abcdef0123456789ABCDEF"


class FormatGuardMutations(unittest.TestCase):
    def test_the_field_report_dump_still_trips(self):
        self.assertIn("job-index dump",
                      _answer_format_problem(json.dumps(_DUMP)))

    def test_dropping_to_one_index_key_passes(self):
        thin = {"job_status": "Summary", "answer": "all clear"}
        self.assertEqual(_answer_format_problem(json.dumps(thin)), "")

    def test_two_index_keys_still_trip_as_a_whole_object(self):
        pair = {"job_status": "Summary", "total_job_count": 7}
        self.assertIn("job-index dump",
                      _answer_format_problem(json.dumps(pair)))

    def test_two_quoted_fields_outside_json_do_not_trip(self):
        text = 'saw "job_status": Summary and "job_ids"=none'
        self.assertEqual(_answer_format_problem(text), "")

    def test_three_quoted_fields_trip_without_being_json(self):
        text = ('"job_status": Summary, "job_ids"=none, '
                '"total_job_count": 7, trailing note')
        self.assertIn("job-index dump", _answer_format_problem(text))

    def test_a_json_list_of_index_keys_is_not_a_dump(self):
        text = json.dumps(["job_status", "job_ids", "total_job_count"])
        self.assertEqual(_answer_format_problem(text), "")

    def test_parameters_without_command_and_without_a_tool_name_passes(self):
        self.assertEqual(
            _answer_format_problem('{"parameters": {"timeout_sec": 1}}'),
            "")

    def test_a_known_tool_name_with_arguments_trips(self):
        text = '{"name": "read_file", "arguments": {"path": "a"}}'
        self.assertIn("tool-call fragment", _answer_format_problem(text))

    def test_an_unknown_tool_name_does_not(self):
        text = '{"name": "not_a_tool", "arguments": {"path": "a"}}'
        self.assertEqual(_answer_format_problem(text), "")

    def test_unquoted_parameters_and_command_do_not_trip(self):
        self.assertEqual(
            _answer_format_problem("parameters command psexec"), "")

    def test_blank_and_non_strings_pass(self):
        self.assertEqual(_answer_format_problem("   \n"), "")
        self.assertEqual(_answer_format_problem(7), "")
        self.assertEqual(_answer_format_problem(["job_status"]), "")


class SecurityInputMutations(unittest.TestCase):
    def test_env_names_flip_on_case_and_prefix_only(self):
        self.assertFalse(S.is_dangerous_env_name(None))
        self.assertFalse(S.is_dangerous_env_name(""))
        self.assertFalse(S.is_dangerous_env_name("HOME"))
        self.assertFalse(S.is_dangerous_env_name("PATH "))
        self.assertTrue(S.is_dangerous_env_name("path"))
        self.assertTrue(S.is_dangerous_env_name("Ld_Preload"))
        self.assertTrue(S.is_dangerous_env_name("DYLD_INSERT_LIBRARIES"))
        self.assertTrue(S.is_dangerous_env_name("git_config_count"))
        self.assertFalse(S.is_dangerous_env_name("GIT_CONFIG"))

    def test_secret_mutations(self):
        S.validate_shared_secret(_STRONG)
        for bad in (None, "", "changeme-but-very-long-xxxxxxxxxxxxxxxx",
                    "abc" * 40, "0123456789abcdefWXYZ"):
            with self.assertRaises(RuntimeError):
                S.validate_shared_secret(bad)

    def test_mode_and_audit_bound_mutations(self):
        self.assertEqual(S.sec_mode(None, "audience"), "off")
        self.assertEqual(S.sec_mode({"security": []}, "audience"), "off")
        self.assertEqual(S.sec_mode(
            {"security": {"modes": []}}, "audience"), "off")
        self.assertEqual(S.sec_mode(
            {"security": {"modes": {"audience": "sometimes"}}},
            "audience"), "off")
        self.assertEqual(S.sec_mode(
            {"security": {"modes": {}}}, "audience"), "off")
        self.assertEqual(S.sec_mode(
            {"security": {"modes": {"audience": "audit"}}},
            "audience"), "audit")

        self.assertEqual(S.audit_max_lines(None), S.DEFAULT_AUDIT_MAX_LINES)
        self.assertEqual(S.audit_max_lines({"security": []}),
                         S.DEFAULT_AUDIT_MAX_LINES)
        self.assertEqual(S.audit_max_lines(
            {"security": {"audit_max_lines": True}}),
            S.DEFAULT_AUDIT_MAX_LINES)
        self.assertEqual(S.audit_max_lines(
            {"security": {"audit_max_lines": 0}}),
            S.DEFAULT_AUDIT_MAX_LINES)
        self.assertEqual(S.audit_max_lines(
            {"security": {"audit_max_lines": "20"}}),
            S.DEFAULT_AUDIT_MAX_LINES)
        self.assertEqual(S.audit_max_lines(
            {"security": {"audit_max_lines": 3}}), 3)

    def test_config_shape_mutations_stop_before_any_user_lookup(self):
        S.validate_security_config("not a dict")
        S.validate_security_config({})
        S.validate_security_config({"security": None})
        with self.assertRaises(RuntimeError):
            S.validate_security_config({"security": "nope"})
        with self.assertRaises(RuntimeError):
            S.validate_security_config({"security": {"modes": "nope"}})
        with self.assertRaises(RuntimeError):
            S.validate_security_config(
                {"security": {"modes": {"not_a_feature": "off"}}})
        with self.assertRaises(RuntimeError):
            S.validate_security_config(
                {"security": {"modes": {"audience": "sometimes"}}})
        with self.assertRaises(RuntimeError):
            S.validate_security_config(
                {"security": {"audit_max_lines": True}})
        with self.assertRaises(RuntimeError):
            S.validate_security_config(
                {"security": {"audit_max_lines": 0}})
        with self.assertRaises(RuntimeError):
            S.validate_security_config({"security": {"job_user": "root"}})
        with self.assertRaises(RuntimeError):
            S.validate_security_config(
                {"security": {"job_user": {"user": ""}}})


class _Boom:
    def __str__(self):
        raise RuntimeError("hostile")


class SecDecideMutations(unittest.TestCase):
    def test_off_audit_and_enforce_and_a_hostile_context(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_off = {}
            self.assertTrue(S.sec_decide(cfg_off, d, "audience", "because"))
            self.assertFalse(os.path.exists(
                os.path.join(d, S.AUDIT_FILE)))

            cfg_audit = {"security": {"modes": {"audience": "audit"},
                                      "audit_max_lines": 2}}
            self.assertTrue(S.sec_decide(
                cfg_audit, d, "audience", "because",
                ctx={"key_id": _Boom(), "job_id": "j", "detail": "d"}))
            with open(os.path.join(d, S.AUDIT_FILE), encoding="utf-8") as fh:
                first = json.loads(fh.readline())
            self.assertEqual(first["decision"], "would_deny")
            self.assertEqual(first["key_id"], "")
            self.assertEqual(first["mode"], "audit")

            cfg_enforce = {"security": {"modes": {"audience": "enforce"}}}
            self.assertFalse(S.sec_decide(
                cfg_enforce, d, "audience", "because",
                ctx="not-a-dict"))
            with open(os.path.join(d, S.AUDIT_FILE), encoding="utf-8") as fh:
                rows = [json.loads(line) for line in fh if line.strip()]
            self.assertEqual(rows[-1]["decision"], "denied")

            # A third line rolls the log at the audit bound of 2,
            # then the new entry is the only line left.
            self.assertTrue(S.sec_decide(
                cfg_audit, d, "audience", "again"))
            self.assertTrue(os.path.exists(
                os.path.join(d, S.AUDIT_ROLLED_FILE)))

    def test_a_corrupt_counts_file_is_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, S.COUNTS_FILE)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[1, 2]")
            S.bump_evaluated(d, "audience")
            with open(path, encoding="utf-8") as fh:
                counts = json.load(fh)
            self.assertEqual(counts["audience"]["evaluated"], 1)

            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"audience": "nope"}')
            S.write_audit_entry(d, "audience", "denied", "because",
                                cfg={"security": {"audit_max_lines": 50}})
            with open(path, encoding="utf-8") as fh:
                counts = json.load(fh)
            self.assertEqual(counts["audience"]["denied"], 1)
            # A directory is not a writable base. The writer must not raise.
            S.write_audit_entry(os.path.join(d, "missing"), "audience",
                                "denied", "because")


if __name__ == "__main__":
    unittest.main()
