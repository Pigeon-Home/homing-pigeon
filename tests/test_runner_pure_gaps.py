"""Runner helpers the other tests never call by name.

No mailbox, no model, no process. Each decision is a return
value or a log line, not just a line that happened to run.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402


class SizeAndFlagTest(unittest.TestCase):
    def test_a_size_rejects_a_bool_and_clamps(self):
        self.assertEqual(R._cfg_size(True, 8, 10), 8)
        self.assertEqual(R._cfg_size("nope", 8, 10), 8)
        self.assertEqual(R._cfg_size(0, 8, 10), 8)
        self.assertEqual(R._cfg_size(99, 8, 10), 10)
        self.assertEqual(R._cfg_size(4, 8, 10), 4)

    def test_a_flag_is_on_only_for_the_yes_words(self):
        for value in (True, 1, " yes ", "ON", "True"):
            self.assertTrue(R._cfg_flag(value))
        for value in (False, 0, "no", None, 2):
            self.assertFalse(R._cfg_flag(value))

    def test_log_settings_ignore_a_non_dict(self):
        self.assertEqual(R._log_settings("nope")[1],
                         R._LOG_DEFAULT_BACKUPS)

    def test_size_caps_reject_a_bool_and_a_negative(self):
        self.assertIsNone(R._validate_size_caps("nope"))
        self.assertIsNone(R._validate_size_caps({}))
        self.assertIn("max_job_bytes",
                      R._validate_size_caps({"max_job_bytes": True}))
        self.assertIn("max_script_bytes",
                      R._validate_size_caps({"max_script_bytes": -1}))
        self.assertIsNone(R._validate_size_caps(
            {"max_job_bytes": 0, "max_script_bytes": 10}))


class ConfigAndSeenTest(unittest.TestCase):
    def test_a_symlink_config_is_refused_and_a_list_is_not_an_object(self):
        with tempfile.TemporaryDirectory() as d:
            real = os.path.join(d, "real.json")
            with open(real, "w", encoding="utf-8") as fh:
                fh.write('{"a": 1}\n')
            link = os.path.join(d, "link.json")
            os.symlink(real, link)
            with self.assertRaises(RuntimeError):
                R.load_config(link)
            with open(real, "w", encoding="utf-8") as fh:
                fh.write("[1]\n")
            with self.assertRaises(RuntimeError):
                R.load_config(real)
            with open(real, "w", encoding="utf-8") as fh:
                fh.write('{"a": 1}\n')
            self.assertEqual(R.load_config(real)["a"], 1)

    def test_the_seen_cache_accepts_a_list_or_a_dict_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            self.assertEqual(R.load_seen(path), {})
            self.assertEqual(R.load_seen(""), {})
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(["job-a"], fh)
            self.assertEqual(R.load_seen(path), {"job-a": True})
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"job-b": 1}, fh)
            self.assertEqual(R.load_seen(path), {"job-b": True})
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[]")
            os.symlink(path, os.path.join(d, "link.json"))
            self.assertEqual(R.load_seen(os.path.join(d, "link.json")), {})
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("123")
            self.assertEqual(R.load_seen(path), {})


class InvocationAndLoopbackTest(unittest.TestCase):
    def test_an_empty_argv_is_unknown_and_windows_uses_list2cmdline(self):
        self.assertEqual(R._invocation_line([]), "(unknown invocation)")
        with mock.patch.object(R.os, "name", "nt"):
            line = R._invocation_line(["prog", "a b"])
        self.assertIn("prog", line)
        self.assertIn('"', line)
        self.assertIn(" ", R._invocation_line(["prog", "ok"]))

    def test_loopback_accepts_the_mapped_and_bracketed_forms(self):
        self.assertTrue(R._is_loopback_ip("127.0.0.1"))
        self.assertTrue(R._is_loopback_ip("[::1]"))
        self.assertTrue(R._is_loopback_ip("::ffff:127.0.0.1"))
        self.assertTrue(R._is_loopback_ip("::1%eth0"))
        self.assertFalse(R._is_loopback_ip("10.0.0.1"))
        self.assertFalse(R._is_loopback_ip("not-an-ip"))
        self.assertFalse(R._is_loopback_ip(""))


class OpinionAndLearningTest(unittest.TestCase):
    def test_a_bad_interpreter_falls_back_to_the_platform(self):
        with mock.patch.object(R._opinion, "gather_facts",
                               return_value={"ok": 1}) as facts:
            got = R._opinion_env_facts(
                {}, {"interpreter": "sh"})
        self.assertEqual(got, {"ok": 1})
        used = facts.call_args[0][1]
        self.assertIsInstance(used, list)
        self.assertTrue(all(isinstance(x, str) for x in used))

    def test_the_model_note_stays_off_until_every_gate_is_open(self):
        with mock.patch.object(R._opinion, "model_enabled",
                               return_value=False):
            self.assertIsNone(R._opinion_model_note({}, {}))
        with mock.patch.object(R._opinion, "model_enabled",
                               return_value=True), \
                mock.patch.object(R, "inference_config",
                                  return_value=None):
            self.assertIsNone(R._opinion_model_note({}, {}))
        inf = {"endpoint": "http://127.0.0.1:9/v1", "model": "m"}
        with mock.patch.object(R._opinion, "model_enabled",
                               return_value=True), \
                mock.patch.object(R, "inference_config",
                                  return_value=inf), \
                mock.patch.object(R, "ask_model",
                                  side_effect=RuntimeError("down")):
            self.assertIsNone(R._opinion_model_note({}, {"kind": "ping"}))
        with mock.patch.object(R._opinion, "model_enabled",
                               return_value=True), \
                mock.patch.object(R, "inference_config",
                                  return_value=inf), \
                mock.patch.object(R, "ask_model",
                                  return_value={"answer": "  " + "x" * 300}):
            note = R._opinion_model_note({}, {"kind": "ping"})
        self.assertEqual(len(note), 240)
        with mock.patch.object(R._opinion, "model_enabled",
                               return_value=True), \
                mock.patch.object(R, "inference_config",
                                  return_value=inf), \
                mock.patch.object(R, "ask_model", return_value="nope"):
            self.assertIsNone(R._opinion_model_note({}, {}))

    def test_learning_stays_quiet_when_a_gate_is_shut(self):
        self.assertFalse(R._learning_active({}, None))
        self.assertFalse(R._learning_active(
            {}, {"active": True, "mode": "off"}))
        with mock.patch.object(R._learning, "learning_enabled",
                               return_value=False):
            self.assertEqual(R._learning_context({}, "/tmp", {}),
                             (None, []))
        with mock.patch.object(R._learning, "learning_enabled",
                               return_value=True), \
                mock.patch.object(R._learning, "load_state",
                                  side_effect=OSError("no")):
            self.assertEqual(R._learning_context({}, "/tmp", {}),
                             (None, []))

    def test_a_freeze_that_fails_does_not_raise(self):
        plan = {"active": True, "mode": "advisory", "findings": [],
                "checks_run": True}
        with mock.patch.object(R._learning, "learning_enabled",
                               return_value=False):
            self.assertIsNone(R._learning_freeze(
                {}, "/tmp", "j", {}, plan, {}, None))
        with mock.patch.object(R._learning, "learning_enabled",
                               return_value=True), \
                mock.patch.object(R._opinion, "verdict_of",
                                  return_value="pass"), \
                mock.patch.object(R._learning, "feature_keys",
                                  return_value=["tool:sh"]), \
                mock.patch.object(R._opinion, "received_digest",
                                  return_value="d"), \
                mock.patch.object(R._learning, "prediction_record",
                                  return_value={"id": "j"}), \
                mock.patch.object(R._learning, "freeze",
                                  return_value=False):
            self.assertIsNone(R._learning_freeze(
                {}, "/tmp", "j", {}, plan, {}, None))

    def test_reconcile_logs_a_write_that_does_not_land(self):
        with mock.patch.object(R._learning, "learning_enabled",
                               return_value=True), \
                mock.patch.object(R._learning, "feature_keys",
                                  return_value=[]), \
                mock.patch.object(R._learning, "touched_keys",
                                  return_value=[]), \
                mock.patch.object(R._learning, "reconcile",
                                  return_value=None):
            self.assertIsNone(R._learning_reconcile(
                {}, "/tmp", {"features": ["a"]}, "j", {}, {}, None))
        with mock.patch.object(R._learning, "learning_enabled",
                               return_value=True), \
                mock.patch.object(R._learning, "touched_keys",
                                  side_effect=OSError("no")):
            self.assertIsNone(R._learning_reconcile(
                {}, "/tmp", None, "j", {}, {}, {"x": 1}))

    def test_a_model_candidate_must_be_one_json_object(self):
        with mock.patch.object(R._learning, "learning_model_enabled",
                               return_value=False):
            self.assertIsNone(R._learning_model_candidate(
                {}, "/tmp", "j", {}, {}, "", ""))
        inf = {"endpoint": "http://127.0.0.1:9/v1", "model": "m"}
        with mock.patch.object(R._learning, "learning_model_enabled",
                               return_value=True), \
                mock.patch.object(R._opinion, "model_enabled",
                                  return_value=True), \
                mock.patch.object(R, "inference_config",
                                  return_value=inf), \
                mock.patch.object(R, "ask_model",
                                  return_value={"answer": "no brace"}), \
                mock.patch.object(R._learning, "validate_candidate") as val:
            R._learning_model_candidate(
                {}, "/tmp", "j", {"kind": "ping"},
                {"exit_code": 0}, "out", "")
        val.assert_not_called()
        with mock.patch.object(R._learning, "learning_model_enabled",
                               return_value=True), \
                mock.patch.object(R._opinion, "model_enabled",
                                  return_value=True), \
                mock.patch.object(R, "inference_config",
                                  return_value=inf), \
                mock.patch.object(
                    R, "ask_model",
                    return_value={"answer": 'note {"claim": "x"} tail'}), \
                mock.patch.object(R._learning, "validate_candidate",
                                  return_value=None):
            self.assertIsNone(R._learning_model_candidate(
                {}, "/tmp", "j", {"kind": "ping"},
                {"exit_code": 1, "timed_out": False}, "", "err"))
        for bad in (RuntimeError("down"), "nope", {"answer": 5}):
            with mock.patch.object(R._learning, "learning_model_enabled",
                                   return_value=True), \
                    mock.patch.object(R._opinion, "model_enabled",
                                      return_value=True), \
                    mock.patch.object(R, "inference_config",
                                      return_value=inf), \
                    mock.patch.object(
                        R, "ask_model",
                        side_effect=bad if isinstance(bad, Exception)
                        else None,
                        return_value=None if isinstance(bad, Exception)
                        else bad), \
                    mock.patch.object(R._learning, "validate_candidate") as val:
                self.assertIsNone(R._learning_model_candidate(
                    {}, "/tmp", "j", {"kind": "ping"},
                    {"exit_code": 0}, "", ""))
            val.assert_not_called()


class RemediationWireTest(unittest.TestCase):
    def test_the_oracle_ask_is_bounded_and_blank_answers_are_none(self):
        st = {"oracle_timeout_sec": 5, "mode": "oracle"}
        with mock.patch.object(R, "inference_config", return_value=None):
            self.assertIsNone(R._remediation_ask_fn({}, st))
        inf = {"endpoint": "http://127.0.0.1:9/v1", "model": "m",
               "timeout_sec": "nope"}
        with mock.patch.object(R, "inference_config", return_value=inf), \
                mock.patch.object(R, "ask_model",
                                  return_value={"answer": "  kill  "}) as ask:
            fn = R._remediation_ask_fn({}, st)
            self.assertEqual(fn("q", "ctx"), "  kill  ")
        self.assertEqual(ask.call_args[0][0]["timeout_sec"], 5)
        with mock.patch.object(R, "inference_config", return_value=inf), \
                mock.patch.object(R, "ask_model", return_value={"answer": 1}):
            fn = R._remediation_ask_fn({}, st)
            self.assertIsNone(fn("q", "ctx"))

    def test_an_audit_failure_is_swallowed(self):
        st = {"mode": "advisory"}
        with mock.patch.object(R._security, "write_audit_entry",
                               side_effect=OSError("full")):
            R._remediation_audit("/tmp", {}, st, "j", "spare", "quiet")
        with mock.patch.object(R, "_append_security_event",
                               side_effect=OSError("full")):
            R._remediation_event(
                "/tmp", st, "j", "quiet", "none", "reflex",
                None, None, "d")

    def test_a_captured_smtp_keeps_the_subject_when_the_body_is_bytes(self):
        cap = R._CaptureSMTP()

        class _Msg:
            def __getitem__(self, key):
                return "result 1" if key == "Subject" else None

            def get_content(self):
                raise RuntimeError("not a modern message")

            def get_payload(self, decode=False):
                return b"hello"

        cap.send_message(_Msg())
        self.assertEqual(cap.sent, [("result 1", "hello")])
        self.assertEqual(R._NullIMAP().store(1, "+FLAGS", "\\Seen")[0], "OK")

