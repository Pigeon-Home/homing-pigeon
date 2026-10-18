"""--oracle-cli: the Oracle chat in the terminal.

The loop runs against a scripted input and a fake ask_model_agent,
so the seams it shares with the --oracle window are what get pinned:
the same context, the same reject rendering, the same chat-log
turns (open, one per question, close), and /quit, /exit, /help, EOF,
and Ctrl+C all ending the chat without a mailbox in sight.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from runner import runner as R

INF = {"endpoint": "http://127.0.0.1:11434/v1", "model": "m",
       "max_answer_chars": 2000}


def _run_cli(lines, ask):
    """Drive oracle_cli over scripted input; return (rc, out, turns, ask)."""
    out = []
    turns = []
    seen = {}
    queue = list(lines)

    def fake_input(prompt=""):
        if not queue:
            raise EOFError
        return queue.pop(0)

    def fake_record(base, cfg, question, ans, event="turn"):
        seen["base"] = base
        turns.append((question, event))

    with tempfile.TemporaryDirectory() as d:
        cfg = {"base_dir": d, "inference": dict(INF)}
        with mock.patch.object(R, "ask_model_agent", side_effect=ask) \
                as ask_mock, \
                mock.patch.object(R, "record_oracle_turn",
                                  side_effect=fake_record), \
                mock.patch.object(R, "oracle_context",
                                  return_value="CTX"), \
                mock.patch.object(R, "inference_config",
                                  return_value=dict(INF)), \
                mock.patch.object(R, "_warm_oracle_model"), \
                mock.patch.object(R, "_refresh_log_settings"), \
                mock.patch.object(R, "_announce_oracle_log"):
            rc = R.oracle_cli(cfg, cfg_path=None,
                              input_fn=fake_input, print_fn=out.append)
    return rc, out, turns, ask_mock, seen


class OracleCliLoopTest(unittest.TestCase):
    def test_answer_is_printed_and_turns_are_recorded(self):
        def ask(inf, question, ctx, cap, patterns, **kw):
            return {"answer": "All quiet on the board."}

        rc, out, turns, ask_mock, seen = _run_cli(
            ["", "   ", "how is the board?", "/quit"], ask)
        self.assertEqual(rc, 0)
        ask_mock.assert_called_once()
        args, kw = ask_mock.call_args
        self.assertEqual(args[1], "how is the board?")
        self.assertEqual(args[2], "CTX")
        self.assertEqual(kw.get("base_dir"), seen["base"])
        self.assertIn("All quiet on the board.", out)
        self.assertEqual(turns[0], ("", "open"))
        self.assertEqual(turns[-1], ("", "close"))
        self.assertIn(("how is the board?", "turn"), turns)

    def test_banner_names_the_model(self):
        def ask(*a, **kw):
            return {"answer": "x"}

        rc, out, turns, ask_mock, _seen = _run_cli(["/quit"], ask)
        self.assertTrue(any("--oracle-cli" in line for line in out))
        self.assertTrue(any("local model m" in line for line in out))
        ask_mock.assert_not_called()

    def test_eof_ends_the_chat(self):
        def ask(*a, **kw):
            raise AssertionError("must not be called")

        rc, out, turns, ask_mock, _seen = _run_cli([], ask)
        self.assertEqual(rc, 0)
        ask_mock.assert_not_called()
        self.assertEqual(turns[-1], ("", "close"))

    def test_help_and_exit_never_ask(self):
        def ask(*a, **kw):
            raise AssertionError("must not be called")

        rc, out, turns, ask_mock, _seen = _run_cli(["/help", "/exit"], ask)
        self.assertEqual(rc, 0)
        ask_mock.assert_not_called()
        self.assertTrue(any("/quit" in line for line in out))

    def test_reject_prints_the_shared_detail(self):
        def ask(inf, question, ctx, cap, patterns, **kw):
            return {"rejected": "inference_unconfigured"}

        rc, out, turns, ask_mock, _seen = _run_cli(["anyone there?"], ask)
        self.assertIn(R._ORACLE_REJECTS["inference_unconfigured"], out)

    def test_ask_failure_reports_inference_error_and_goes_on(self):
        calls = []

        def ask(inf, question, ctx, cap, patterns, **kw):
            calls.append(question)
            if len(calls) == 1:
                raise RuntimeError("endpoint exploded")
            return {"answer": "Recovered."}

        rc, out, turns, ask_mock, _seen = _run_cli(
            ["first", "second", "/quit"], ask)
        self.assertEqual(rc, 0)
        self.assertIn(R._ORACLE_REJECTS["inference_error"], out)
        self.assertIn("Recovered.", out)

    def test_question_is_capped_like_the_window(self):
        seen = {}

        def ask(inf, question, ctx, cap, patterns, **kw):
            seen["n"] = len(question)
            return {"answer": "ok"}

        _run_cli(["x" * 5000], ask)
        self.assertEqual(seen["n"], 4000)


class OracleCliWiringTest(unittest.TestCase):
    def test_oracle_cli_flag_does_not_need_a_mailbox(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"inference": {
                    "endpoint": "http://127.0.0.1:11434/v1",
                    "model": "m",
                }, "base_dir": d}, fh)
            with mock.patch("runner.runner.oracle_cli",
                            return_value=0) as cli, \
                    mock.patch("runner.runner.ensure_inference_ready"), \
                    mock.patch("runner.runner.update_llama_from_config"), \
                    mock.patch("sys.argv",
                               ["runner", "--config", path, "--oracle-cli"]):
                from runner.runner import main
                self.assertEqual(main(), 0)
            cli.assert_called_once()
            self.assertEqual(cli.call_args.kwargs.get("cfg_path"), path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
