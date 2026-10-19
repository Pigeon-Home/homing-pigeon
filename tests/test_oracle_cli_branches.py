"""--oracle-cli: the branches the loop tests leave behind.

tests/test_oracle_cli.py pins the loop's main path. This file takes
the seams around it: the default input/print functions, a non-dict
config, the cfg_path banner, the not-configured banner and its
reject text, the warm-up thread's spawn and join, ask results that
are not dicts, unknown reject keys, a chat-log writer that fails on
one turn only, and the exact arguments the CLI hands the ask.
"""

import builtins
import tempfile
import unittest
from unittest import mock

from runner import runner as R

INF = {"endpoint": "http://127.0.0.1:11434/v1", "model": "m",
       "max_answer_chars": 2000}


class _FakeThread:
    instances = []

    def __init__(self, target=None, args=(), daemon=None):
        self.target, self.args, self.daemon = target, args, daemon
        self.started = self.joined = False
        _FakeThread.instances.append(self)

    def start(self):
        self.started = True

    def join(self, timeout=None):
        self.joined = True
        self.join_timeout = timeout


def _drive(lines, ask, cfg_extra=None, inf=INF, record=None,
           cfg_path=None, thread_cls=None):
    """Run oracle_cli scripted; return (rc, out, turns, ask_mock, seen)."""
    out, turns, seen = [], [], {}
    queue = list(lines)

    def fake_input(prompt=""):
        if not queue:
            raise EOFError
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def fake_record(base, cfg, question, ans, event="turn"):
        seen.setdefault("bases", []).append(base)
        turns.append((question, event))
        if record is not None:
            record(question, event)

    def fake_context(base, watch=True):
        seen["watch"] = watch
        return "CTX"

    with tempfile.TemporaryDirectory() as d:
        cfg = {"base_dir": d}
        if inf is not None:
            cfg["inference"] = dict(inf)
        cfg.update(cfg_extra or {})
        patches = [
            mock.patch.object(R, "ask_model_agent", side_effect=ask),
            mock.patch.object(R, "record_oracle_turn",
                              side_effect=fake_record),
            mock.patch.object(R, "oracle_context",
                              side_effect=fake_context),
            mock.patch.object(R, "_refresh_log_settings"),
            mock.patch.object(R, "_announce_oracle_log"),
        ]
        if thread_cls is not None:
            patches.append(mock.patch.object(
                R.threading, "Thread", thread_cls))
        for p in patches:
            p.start()
        try:
            rc = R.oracle_cli(cfg, cfg_path=cfg_path,
                              input_fn=fake_input, print_fn=out.append)
        finally:
            for p in patches:
                p.stop()
    return rc, out, turns, seen


def _ok_ask(inf, question, ctx, cap, patterns, **kw):
    return {"answer": "Fine."}


class OracleCliSeamsTest(unittest.TestCase):
    def test_default_input_and_print_seams(self):
        out = []
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d, "inference": dict(INF)}
            with mock.patch.object(R, "ask_model_agent",
                                   side_effect=_ok_ask), \
                    mock.patch.object(R, "record_oracle_turn"), \
                    mock.patch.object(R, "oracle_context",
                                      return_value="CTX"), \
                    mock.patch.object(R, "_refresh_log_settings"), \
                    mock.patch.object(R, "_announce_oracle_log"), \
                    mock.patch.object(R, "_warm_oracle_model"), \
                    mock.patch.object(builtins, "input",
                                      side_effect=EOFError), \
                    mock.patch.object(builtins, "print", out.append):
                rc = R.oracle_cli(cfg)
        self.assertEqual(rc, 0)
        self.assertTrue(any("oracle-cli" in line for line in out))

    def test_non_dict_cfg_is_treated_as_empty(self):
        out = []
        with mock.patch.object(R, "record_oracle_turn"), \
                mock.patch.object(R, "_refresh_log_settings"), \
                mock.patch.object(R, "_announce_oracle_log"), \
                mock.patch.object(R, "_base_dir_for",
                                  return_value=tempfile.mkdtemp()):
            rc = R.oracle_cli(None, input_fn=lambda prompt="": (_ for _ in ()).throw(EOFError),
                              print_fn=out.append)
        self.assertEqual(rc, 0)
        self.assertTrue(any("not configured" in line for line in out))

    def test_cfg_path_banner_names_the_config(self):
        rc, out, turns, seen = _drive([], _ok_ask,
                                      cfg_path="/some/where/config.json")
        self.assertEqual(rc, 0)
        self.assertTrue(any("Config:" in line and "config.json" in line
                            for line in out))

    def test_not_configured_banner_and_reject_text(self):
        def ask(inf, question, ctx, cap, patterns, **kw):
            return {"rejected": "inference_unconfigured"}
        rc, out, turns, seen = _drive(["status?"], ask, inf=None)
        self.assertTrue(any("not configured" in line for line in out))
        self.assertTrue(any("No loopback model is configured" in line
                            for line in out))

    def test_warm_thread_is_spawned_with_inference_and_joined(self):
        _FakeThread.instances = []
        rc, out, turns, seen = _drive(["/quit"], _ok_ask,
                                      thread_cls=_FakeThread)
        self.assertEqual(rc, 0)
        self.assertEqual(len(_FakeThread.instances), 1)
        warm = _FakeThread.instances[0]
        self.assertTrue(warm.started)
        self.assertTrue(warm.joined)
        self.assertEqual(warm.join_timeout, 5)
        self.assertEqual(warm.args[0]["model"], "m")
        self.assertTrue(warm.daemon)

    def test_no_warm_thread_without_a_model(self):
        _FakeThread.instances = []
        rc, out, turns, seen = _drive(["/quit"], _ok_ask, inf=None,
                                      thread_cls=_FakeThread)
        self.assertEqual(_FakeThread.instances, [])

    def test_non_dict_ask_result_reports_inference_error(self):
        def ask(inf, question, ctx, cap, patterns, **kw):
            return None
        rc, out, turns, seen = _drive(["status?"], ask)
        self.assertTrue(any("The local model did not answer" in line
                            for line in out))

    def test_unknown_reject_key_uses_the_stock_line(self):
        def ask(inf, question, ctx, cap, patterns, **kw):
            return {"rejected": "some_future_reason"}
        rc, out, turns, seen = _drive(["status?"], ask)
        self.assertIn("The Oracle did not answer.", out)

    def test_inference_error_detail_overrides_the_stock_line(self):
        def ask(inf, question, ctx, cap, patterns, **kw):
            return {"rejected": "inference_error",
                    "detail": "endpoint said 503: model loading"}
        rc, out, turns, seen = _drive(["status?"], ask)
        self.assertIn("endpoint said 503: model loading", out)

    def test_empty_answer_falls_back_to_inference_error(self):
        def ask(inf, question, ctx, cap, patterns, **kw):
            return {"answer": ""}
        rc, out, turns, seen = _drive(["status?"], ask)
        self.assertTrue(any("The local model did not answer" in line
                            for line in out))

    def test_record_failure_on_one_turn_still_prints_and_continues(self):
        def record(question, event):
            if event == "turn":
                raise OSError("disk full")
        rc, out, turns, seen = _drive(["one?", "two?"], _ok_ask,
                                      record=record)
        self.assertEqual(rc, 0)
        self.assertEqual(out.count("Fine."), 2)
        self.assertEqual([e for _, e in turns],
                         ["open", "turn", "turn", "close"])

    def test_open_record_failure_does_not_stop_the_chat(self):
        def record(question, event):
            if event == "open":
                raise RuntimeError("nope")
        rc, out, turns, seen = _drive(["one?"], _ok_ask, record=record)
        self.assertEqual(rc, 0)
        self.assertIn("Fine.", out)

    def test_close_record_failure_is_swallowed(self):
        def record(question, event):
            if event == "close":
                raise RuntimeError("nope")
        rc, out, turns, seen = _drive(["one?"], _ok_ask, record=record)
        self.assertEqual(rc, 0)
        self.assertIn("Fine.", out)

    def test_ctrl_c_after_an_answer_ends_cleanly(self):
        rc, out, turns, seen = _drive(
            ["one?", KeyboardInterrupt()], _ok_ask)
        self.assertEqual(rc, 0)
        self.assertIn("Fine.", out)
        self.assertEqual([e for _, e in turns], ["open", "turn", "close"])

    def test_ask_receives_instructions_cap_and_watch(self):
        captured = {}

        def ask(inf, question, ctx, cap, patterns, **kw):
            captured.update(kw)
            captured["cap"] = cap
            captured["ctx"] = ctx
            return {"answer": "Fine."}

        inf = {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"}
        rc, out, turns, seen = _drive(
            ["  padded question?  "], ask, inf=inf,
            cfg_extra={"owner_instructions": "Be terse.",
                       "inference": dict(inf, watch_system=False)})
        self.assertEqual(captured["instructions"], "Be terse.")
        self.assertEqual(captured["cap"], 2000)  # inf has no cap key
        self.assertEqual(captured["ctx"], "CTX")
        self.assertFalse(seen["watch"])
        asked = [q for q, e in turns if e == "turn"]
        self.assertEqual(asked, ["padded question?"])


if __name__ == "__main__":
    unittest.main()
