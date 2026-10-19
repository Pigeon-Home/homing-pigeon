"""The Oracle's tools stay inside the state dir and never raise.

A bad path, a huge write, a timed-out command, and an unknown tool
name all come back as an error string the model can read. The
terminal chat uses the same answer path with no mailbox and no
browser; input_fn and print_fn are the seams.
"""

import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import runner.runner as rr


class OracleToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_args_that_are_not_an_object_are_refused(self):
        self.assertEqual(rr._run_oracle_tool("read_file", ["x"]),
                         "error: args must be an object")

    def test_a_missing_path_is_refused_for_read_list_and_write(self):
        for name in ("read_file", "list_dir", "write_file"):
            self.assertIn("path must be a non-empty string",
                          rr._run_oracle_tool(name, {"path": ""}))
        self.assertIn("content must be a string",
                      rr._run_oracle_tool(
                          "write_file",
                          {"path": "a.txt", "content": 3}))

    def test_a_path_that_leaves_the_state_dir_is_refused(self):
        outside = os.path.abspath("/etc/hostname")
        for name in ("read_file", "list_dir"):
            got = rr._run_oracle_tool(name, {"path": outside}, self.base)
            self.assertIn("leaves the state dir", got)
        got = rr._run_oracle_tool(
            "write_file", {"path": outside, "content": "x"}, self.base)
        self.assertIn("leaves the state dir", got)

    def test_read_file_returns_text_and_marks_truncation(self):
        path = os.path.join(self.base, "note.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("abcdef")
        got = rr._run_oracle_tool(
            "read_file", {"path": "note.txt", "max_chars": 3}, self.base)
        self.assertTrue(got.startswith("abc"))
        self.assertIn("truncated", got)

    def test_a_bool_cap_and_a_junk_cap_both_fall_back_to_4000(self):
        path = os.path.join(self.base, "note.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("hi")
        for cap in (True, "nope"):
            got = rr._run_oracle_tool(
                "read_file", {"path": "note.txt", "max_chars": cap},
                self.base)
            self.assertEqual(got, "hi")

    def test_an_empty_file_reads_as_empty(self):
        open(os.path.join(self.base, "empty.txt"), "w").close()
        got = rr._run_oracle_tool(
            "read_file", {"path": "empty.txt"}, self.base)
        self.assertEqual(got, "(empty file)")

    def test_a_missing_file_is_an_error_string_not_an_exception(self):
        got = rr._run_oracle_tool(
            "read_file", {"path": "nope.txt"}, self.base)
        self.assertTrue(got.startswith("error: cannot read"))

    def test_list_dir_marks_directories_and_caps_at_200(self):
        os.mkdir(os.path.join(self.base, "aaa"))
        for i in range(201):
            open(os.path.join(self.base, f"f{i:03d}.txt"), "w").close()
        got = rr._run_oracle_tool(
            "list_dir", {"path": "."}, self.base)
        self.assertIn("aaa/", got)
        self.assertIn("more]", got)

    def test_an_empty_directory_lists_as_empty(self):
        empty = os.path.join(self.base, "bare")
        os.mkdir(empty)
        got = rr._run_oracle_tool(
            "list_dir", {"path": "bare"}, self.base)
        self.assertEqual(got, "(empty directory)")

    def test_listing_a_file_is_an_error_string(self):
        open(os.path.join(self.base, "a.txt"), "w").close()
        got = rr._run_oracle_tool(
            "list_dir", {"path": "a.txt"}, self.base)
        self.assertTrue(got.startswith("error: cannot list"))

    def test_write_file_creates_the_parent_and_reports_the_count(self):
        got = rr._run_oracle_tool(
            "write_file",
            {"path": "nest/a.txt", "content": "hello"},
            self.base)
        self.assertIn("wrote 5 chars", got)
        with open(os.path.join(self.base, "nest", "a.txt"),
                  encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "hello")
        mode = stat.S_IMODE(os.stat(
            os.path.join(self.base, "nest", "a.txt")).st_mode)
        self.assertEqual(mode & 0o777, 0o600)

    def test_a_write_over_200000_chars_is_refused(self):
        got = rr._run_oracle_tool(
            "write_file",
            {"path": "big.txt", "content": "x" * 200001},
            self.base)
        self.assertIn("too large", got)
        self.assertFalse(os.path.exists(os.path.join(self.base, "big.txt")))

    def test_run_refuses_a_blank_or_huge_command(self):
        self.assertIn("non-empty", rr._run_oracle_tool("run", {"command": "  "}))
        self.assertIn("too long", rr._run_oracle_tool(
            "run", {"command": "echo " + "x" * 8000}))

    def test_a_junk_timeout_falls_back_and_a_real_command_runs(self):
        got = rr._run_oracle_tool(
            "run",
            {"command": "echo hi", "timeout_sec": "nope"},
            self.base)
        self.assertTrue(got.startswith("exit=0"))
        self.assertIn("hi", got)

    def test_a_command_with_no_output_says_so(self):
        got = rr._run_oracle_tool(
            "run", {"command": "true"}, self.base)
        self.assertIn("(no output)", got)

    def test_an_unknown_tool_is_named_in_the_error(self):
        self.assertIn("unknown tool 'explode'",
                      rr._run_oracle_tool("explode", {}))

    def test_wire_arguments_keep_a_string_and_dump_a_dict(self):
        self.assertEqual(rr._wire_tool_arguments('{"a": 1}'), '{"a": 1}')
        self.assertEqual(rr._wire_tool_arguments({"a": 1}), '{"a": 1}')
        self.assertEqual(rr._wire_tool_arguments(None), "{}")

    def test_a_non_serializable_argument_becomes_empty_object(self):
        self.assertEqual(rr._wire_tool_arguments({1, 2}), "{}")


class OracleCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _cfg(self, **extra):
        cfg = {"base_dir": self.base}
        cfg.update(extra)
        return cfg

    def test_a_non_dict_config_still_opens_and_quits(self):
        lines = iter(["/quit"])
        printed = []
        rc = rr.oracle_cli(
            None, input_fn=lambda _p: next(lines),
            print_fn=printed.append)
        self.assertEqual(rc, 0)
        self.assertTrue(any("oracle-cli" in p for p in printed))
        self.assertTrue(any("not configured" in p for p in printed))

    def test_help_blank_and_exit_do_not_ask_the_model(self):
        lines = iter(["", "   ", "/help", "/exit"])
        printed = []
        with mock.patch.object(rr, "ask_model_agent") as ask:
            rc = rr.oracle_cli(
                self._cfg(), input_fn=lambda _p: next(lines),
                print_fn=printed.append)
        ask.assert_not_called()
        self.assertEqual(rc, 0)
        self.assertTrue(any("/quit ends" in p for p in printed))

    def test_eof_ends_the_chat(self):
        def boom(_p):
            raise EOFError
        rc = rr.oracle_cli(
            self._cfg(), input_fn=boom, print_fn=lambda *_a: None)
        self.assertEqual(rc, 0)

    def test_deterministic_mode_prints_the_box_record(self):
        printed = []
        lines = iter(["what is up", "/quit"])
        cfg = self._cfg(oracle_mode="deterministic")
        with mock.patch.object(
                rr, "_deterministic_oracle_answer",
                return_value="the box says hi"):
            rr.oracle_cli(
                cfg, cfg_path=os.path.join(self.base, "cfg.json"),
                input_fn=lambda _p: next(lines),
                print_fn=printed.append)
        self.assertTrue(any("deterministic" in p for p in printed))
        self.assertIn("the box says hi", printed)
        self.assertTrue(any("Config:" in p for p in printed))

    def test_a_configured_model_is_named_and_its_answer_prints(self):
        printed = []
        lines = iter(["status", "/quit"])
        cfg = self._cfg(inference={
            "endpoint": "http://127.0.0.1:11434",
            "model": "tiny",
        })
        with mock.patch.object(rr, "_warm_oracle_model"), \
                mock.patch.object(
                    rr, "ask_model_agent",
                    return_value={"answer": "all quiet"}):
            rr.oracle_cli(
                cfg, input_fn=lambda _p: next(lines),
                print_fn=printed.append)
        self.assertTrue(any("tiny" in p for p in printed))
        self.assertIn("all quiet", printed)

    def test_a_raised_ask_becomes_an_inference_error(self):
        printed = []
        lines = iter(["status", "/quit"])
        cfg = self._cfg(inference={
            "endpoint": "http://127.0.0.1:11434",
            "model": "tiny",
        })
        with mock.patch.object(rr, "_warm_oracle_model"), \
                mock.patch.object(
                    rr, "ask_model_agent",
                    side_effect=RuntimeError("down")):
            rr.oracle_cli(
                cfg, input_fn=lambda _p: next(lines),
                print_fn=printed.append)
        self.assertTrue(any("did not answer" in p.lower()
                            or "inference" in p.lower()
                            for p in printed))

    def test_a_reject_with_detail_is_printed(self):
        printed = []
        lines = iter(["status", "/quit"])
        cfg = self._cfg(inference={
            "endpoint": "http://127.0.0.1:11434",
            "model": "tiny",
        })
        with mock.patch.object(rr, "_warm_oracle_model"), \
                mock.patch.object(
                    rr, "ask_model_agent",
                    return_value={"rejected": "inference_error",
                                  "detail": "model cold"}):
            rr.oracle_cli(
                cfg, input_fn=lambda _p: next(lines),
                print_fn=printed.append)
        self.assertIn("model cold", printed)

    def test_a_failed_open_record_does_not_stop_the_chat(self):
        lines = iter(["/quit"])
        with mock.patch.object(
                rr, "record_oracle_turn",
                side_effect=OSError("disk")):
            rc = rr.oracle_cli(
                self._cfg(), input_fn=lambda _p: next(lines),
                print_fn=lambda *_a: None)
        self.assertEqual(rc, 0)

    def test_keyboard_interrupt_on_input_ends_cleanly(self):
        def boom(_p):
            raise KeyboardInterrupt
        rc = rr.oracle_cli(
            self._cfg(), input_fn=boom, print_fn=lambda *_a: None)
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
