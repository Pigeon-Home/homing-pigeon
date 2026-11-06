#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""F2: Oracle run-tool modes and environment scrubbing.

The interactive Oracle's run tool is the owner's local debugging
door (its charter is pinned by test_oracle_charter.py and does not
change here). What this file pins is the operator knob around it:

- config key oracle_tool_mode (flat, the CLI-shaped spelling) or
  oracle.tool_mode (the nested spelling), values full | confirm |
  confined | readonly, default full -- the charter behavior;
- the CLI flag --oracle-tool-mode, which writes the flat key for
  one process, like every other mode flag;
- environment scrubbing in EVERY mode that executes: the child
  gets an explicit minimal environment (PATH, HOME, LANG/LC_*,
  and the Windows shell essentials on win32), never a variable
  whose name carries a secret marker (KEY, TOKEN, SECRET,
  PASSWORD, AUTH, CREDENTIAL), never the runner's own PIGEON_*
  variables, and never any other inherited variable;
- readonly refuses the run tool with an error string, the same
  shape as its other refusals, and runs nothing;
- confirm runs only after an affirmative confirmation; with no
  TTY the default confirmation refuses;
- confined refuses with a clear not-available error: the job
  sandbox is built for staged job scripts and is not applied to
  the interactive run tool, and a mode that pretends to confine
  while running unconfined would be worse than refusing;
- a bad mode value is named, never silently read as full: the
  tool refuses it and startup validation refuses it;
- the mode is visible in the --posture output.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner.ops import oracle_ops as OO  # noqa: E402
from runner.ops import posture as P  # noqa: E402

SENTINEL = "hp-test-sentinel-value-4f2a"


def _fake_proc(stdout=b"ran\n", returncode=0):
    proc = mock.Mock()
    proc.stdout = stdout
    proc.stderr = b""
    proc.returncode = returncode
    return proc


class ModeResolutionTest(unittest.TestCase):
    def test_default_is_full(self):
        self.assertEqual(OO._oracle_tool_mode({}), "full")
        self.assertEqual(OO._oracle_tool_mode(None), "full")
        self.assertEqual(OO._oracle_tool_mode("nope"), "full")

    def test_flat_key(self):
        self.assertEqual(
            OO._oracle_tool_mode({"oracle_tool_mode": "readonly"}),
            "readonly")

    def test_nested_key(self):
        self.assertEqual(
            OO._oracle_tool_mode({"oracle": {"tool_mode": "confirm"}}),
            "confirm")

    def test_flat_key_wins_over_nested(self):
        # The CLI override writes the flat key, and a flag beats the
        # config file, so the flat key wins when both are present.
        cfg = {"oracle_tool_mode": "full",
               "oracle": {"tool_mode": "readonly"}}
        self.assertEqual(OO._oracle_tool_mode(cfg), "full")

    def test_non_string_values_read_as_unset(self):
        self.assertEqual(OO._oracle_tool_mode(
            {"oracle_tool_mode": True}), "full")
        self.assertEqual(OO._oracle_tool_mode(
            {"oracle": "readonly"}), "full")


class ValidateModeTest(unittest.TestCase):
    def test_absent_and_valid_values_pass(self):
        OO._validate_oracle_tool_mode({})
        for mode in OO.ORACLE_TOOL_MODES:
            OO._validate_oracle_tool_mode({"oracle_tool_mode": mode})
            OO._validate_oracle_tool_mode(
                {"oracle": {"tool_mode": mode}})

    def test_bad_flat_value_is_named(self):
        with self.assertRaisesRegex(RuntimeError, "oracle_tool_mode"):
            OO._validate_oracle_tool_mode(
                {"oracle_tool_mode": "yolo"})
        with self.assertRaisesRegex(RuntimeError, "yolo"):
            OO._validate_oracle_tool_mode(
                {"oracle_tool_mode": "yolo"})

    def test_bad_nested_value_is_named(self):
        with self.assertRaisesRegex(RuntimeError, "yolo"):
            OO._validate_oracle_tool_mode(
                {"oracle": {"tool_mode": "yolo"}})

    def test_non_object_oracle_block_is_named(self):
        with self.assertRaisesRegex(RuntimeError, "oracle"):
            OO._validate_oracle_tool_mode({"oracle": "readonly"})


class EnvScrubTest(unittest.TestCase):
    def test_minimal_env_from_a_dirty_source(self):
        source = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/owner",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "C",
            "HP_TEST_SECRET_TOKEN": SENTINEL,
            "MY_API_KEY": SENTINEL,
            "MAILBOX_PASSWORD": SENTINEL,
            "OAUTH_REFRESH": SENTINEL,
            "AWS_CREDENTIALS": SENTINEL,
            "PIGEON_SECRET": SENTINEL,
            "PIGEON_ANYTHING": SENTINEL,
            "SOME_CUSTOM_MARKER": "benign-but-not-allowlisted",
        }
        env = OO._oracle_tool_env(source)
        self.assertEqual(env.get("PATH"), "/usr/bin:/bin")
        self.assertEqual(env.get("HOME"), "/home/owner")
        self.assertEqual(env.get("LANG"), "en_US.UTF-8")
        self.assertEqual(env.get("LC_ALL"), "C")
        for name in source:
            if name in ("PATH", "HOME", "LANG", "LC_ALL"):
                continue
            self.assertNotIn(name, env, name)
        self.assertNotIn(SENTINEL, env.values())

    def test_env_kwarg_reaches_subprocess_scrubbed(self):
        extra = {
            "HP_TEST_SECRET_TOKEN": SENTINEL,
            "RUNNER_API_KEY": SENTINEL,
            "PIGEON_MAILBOX_PASSWORD": SENTINEL,
            "HP_TEST_BENIGN_MARKER": "should-not-cross",
        }
        with mock.patch.dict(os.environ, extra):
            with mock.patch.object(
                    OO.subprocess, "run",
                    return_value=_fake_proc()) as run_mock:
                out = R._run_oracle_tool(
                    "run", {"command": "echo hi"},
                    base_dir=self._base())
        self.assertIn("ran", out)
        env = run_mock.call_args.kwargs.get("env")
        self.assertIsNotNone(env, "run tool must pass an explicit env")
        for name in extra:
            self.assertNotIn(name, env, name)
        self.assertNotIn(SENTINEL, env.values())
        self.assertEqual(env.get("PATH"), os.environ.get("PATH"))

    def _base(self):
        return tempfile.mkdtemp(prefix="hp-f2-env-")

    def test_real_child_does_not_see_the_sentinel(self):
        cmd = (f"{sys.executable} -c \"import os; "
               f"print(os.environ.get('HP_TEST_SECRET_TOKEN'))\"")
        with mock.patch.dict(os.environ,
                             {"HP_TEST_SECRET_TOKEN": SENTINEL}):
            out = R._run_oracle_tool("run", {"command": cmd},
                                     base_dir=self._base())
        self.assertIn("None", out)
        self.assertNotIn(SENTINEL, out)


class ModeGateTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-f2-mode-")

    def _run_mocked(self, **kwargs):
        with mock.patch.object(
                OO.subprocess, "run",
                return_value=_fake_proc()) as run_mock:
            out = R._run_oracle_tool(
                "run", {"command": "echo hi"}, base_dir=self.base,
                **kwargs)
        return out, run_mock

    def test_default_full_still_runs(self):
        out, run_mock = self._run_mocked()
        self.assertTrue(run_mock.called)
        self.assertIn("exit=0", out)
        self.assertIn("ran", out)

    def test_explicit_full_runs(self):
        out, run_mock = self._run_mocked(tool_mode="full")
        self.assertTrue(run_mock.called)
        self.assertIn("ran", out)

    def test_readonly_refuses_and_runs_nothing(self):
        out, run_mock = self._run_mocked(tool_mode="readonly")
        self.assertFalse(run_mock.called)
        self.assertTrue(out.startswith("error:"), out)
        self.assertIn("readonly", out)

    def test_readonly_from_flat_config(self):
        out, run_mock = self._run_mocked(
            cfg={"oracle_tool_mode": "readonly"})
        self.assertFalse(run_mock.called)
        self.assertIn("readonly", out)

    def test_readonly_from_nested_config(self):
        out, run_mock = self._run_mocked(
            cfg={"oracle": {"tool_mode": "readonly"}})
        self.assertFalse(run_mock.called)
        self.assertIn("readonly", out)

    def test_readonly_does_not_gate_the_file_tools(self):
        path = os.path.join(self.base, "note.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("still readable")
        out = R._run_oracle_tool(
            "read_file", {"path": path}, base_dir=self.base,
            tool_mode="readonly")
        self.assertEqual(out, "still readable")

    def test_confined_refuses_as_not_available(self):
        out, run_mock = self._run_mocked(tool_mode="confined")
        self.assertFalse(run_mock.called)
        self.assertTrue(out.startswith("error:"), out)
        self.assertIn("confined", out)
        self.assertIn("not available", out)

    def test_bad_mode_refuses_and_is_named(self):
        out, run_mock = self._run_mocked(tool_mode="yolo")
        self.assertFalse(run_mock.called)
        self.assertTrue(out.startswith("error:"), out)
        self.assertIn("yolo", out)

    def test_bad_mode_from_config_refuses(self):
        out, run_mock = self._run_mocked(
            cfg={"oracle_tool_mode": "yolo"})
        self.assertFalse(run_mock.called)
        self.assertIn("yolo", out)


class ConfirmModeTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-f2-confirm-")

    def test_declined_confirmation_runs_nothing(self):
        with mock.patch.object(OO.subprocess, "run") as run_mock:
            out = R._run_oracle_tool(
                "run", {"command": "echo hi"}, base_dir=self.base,
                tool_mode="confirm",
                confirm_fn=lambda command: False)
        self.assertFalse(run_mock.called)
        self.assertTrue(out.startswith("error:"), out)
        self.assertIn("confirm", out)

    def test_affirmative_confirmation_runs(self):
        seen = []
        with mock.patch.object(
                OO.subprocess, "run",
                return_value=_fake_proc()) as run_mock:
            out = R._run_oracle_tool(
                "run", {"command": "echo hi"}, base_dir=self.base,
                tool_mode="confirm",
                confirm_fn=lambda command: seen.append(command) or True)
        self.assertTrue(run_mock.called)
        self.assertEqual(seen, ["echo hi"])
        self.assertIn("ran", out)

    def test_no_tty_default_confirmation_refuses(self):
        with mock.patch.object(sys, "stdin", io.StringIO("")):
            with mock.patch.object(OO.subprocess, "run") as run_mock:
                out = R._run_oracle_tool(
                    "run", {"command": "echo hi"}, base_dir=self.base,
                    tool_mode="confirm")
        self.assertFalse(run_mock.called)
        self.assertTrue(out.startswith("error:"), out)


class _FakeResp:
    def __init__(self, message):
        self._body = json.dumps(
            {"choices": [{"message": message}]}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, n=-1):
        return self._body


class AgentLoopPlumbingTest(unittest.TestCase):
    """The mode rides the inference dict to the dispatcher:
    inference_config resolves it from the top-level config and
    passes it through, and ask_model_agent hands it to the tool."""

    _CFG = {"endpoint": "http://127.0.0.1:11434/v1",
            "model": "qwen2.5:3b"}

    def test_inference_config_passes_a_configured_mode_through(self):
        full = {"inference": dict(self._CFG),
                "oracle_tool_mode": "readonly"}
        inf = R.inference_config(full)
        self.assertEqual(inf["oracle_tool_mode"], "readonly")
        full = {"inference": dict(self._CFG),
                "oracle": {"tool_mode": "confirm"}}
        inf = R.inference_config(full)
        self.assertEqual(inf["oracle_tool_mode"], "confirm")

    def test_inference_config_omits_an_unconfigured_mode(self):
        inf = R.inference_config({"inference": dict(self._CFG)})
        self.assertNotIn("oracle_tool_mode", inf)

    def test_readonly_reaches_the_run_tool(self):
        seen = []
        state = {"i": 0}
        script = [
            {"role": "assistant", "content": "", "tool_calls": [{
                "id": "call-1", "type": "function",
                "function": {"name": "run",
                             "arguments": json.dumps(
                                 {"command": "echo hi"})}}]},
            {"role": "assistant", "content": "It was refused."},
        ]

        def opener(req, timeout=60):
            try:
                seen.append(json.loads(req.data.decode("utf-8")))
            except Exception:
                pass
            msg = script[min(state["i"], len(script) - 1)]
            state["i"] += 1
            return _FakeResp(msg)

        with tempfile.TemporaryDirectory() as d:
            inf = dict(self._CFG, oracle_tool_mode="readonly")
            R.ask_model_agent(inf, "Run echo for me.", "", 2000,
                              opener=opener, base_dir=d)
        self.assertGreaterEqual(len(seen), 2)
        self.assertIn("readonly", json.dumps(seen[1]))


class CliFlagTest(unittest.TestCase):
    def test_flag_parses_and_overrides(self):
        ap = R._cli.build_parser()
        with contextlib.redirect_stderr(io.StringIO()):
            args = ap.parse_args(["--oracle-tool-mode", "confirm"])
        self.assertEqual(args.oracle_tool_mode, "confirm")
        cfg = {}
        applied = R.apply_cli_overrides(cfg, args)
        self.assertEqual(cfg.get("oracle_tool_mode"), "confirm")
        self.assertIn("oracle_tool_mode", applied)

    def test_flag_rejects_a_bad_value(self):
        ap = R._cli.build_parser()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                ap.parse_args(["--oracle-tool-mode", "yolo"])

    def test_no_flag_leaves_config_alone(self):
        ap = R._cli.build_parser()
        args = ap.parse_args([])
        cfg = {"oracle_tool_mode": "readonly"}
        R.apply_cli_overrides(cfg, args)
        self.assertEqual(cfg["oracle_tool_mode"], "readonly")


class PostureVisibilityTest(unittest.TestCase):
    def _results(self, cfg):
        d = tempfile.mkdtemp(prefix="hp-f2-posture-")
        cfg_path = os.path.join(d, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        return P.build_posture(cfg, cfg_path, d)

    def test_mode_is_printed(self):
        results = self._results({"oracle_tool_mode": "readonly"})
        self.assertTrue(
            any("tool_mode=readonly" in msg for _, _, msg in results),
            results)

    def test_default_mode_is_printed(self):
        results = self._results({})
        self.assertTrue(
            any("tool_mode=full" in msg for _, _, msg in results),
            results)

    def test_bad_mode_is_a_posture_fail(self):
        results = self._results({"oracle_tool_mode": "yolo"})
        self.assertTrue(
            any(level == "FAIL" and "yolo" in msg
                for level, _, msg in results), results)


STRONG_SECRET = ("9f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c5b4a3928"
                 "a3bf4f1b2b0b822cd15d6c15b0f00a08")


class StartupValidationTest(unittest.TestCase):
    """A bad oracle_tool_mode refuses startup through main()."""

    def _run_main(self, extra):
        tmpdir = tempfile.mkdtemp(prefix="hp-f2-main-")
        cfg = {"mailbox_user": "a@b.c", "mailbox_password": "p",
               "shared_secret": STRONG_SECRET,
               "security": {"modes": {"confinement": "off",
                                      "job_user": "off"}},
               "base_dir": tmpdir}
        cfg.update(extra)
        cfg_path = os.path.join(tmpdir, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        out, err = io.StringIO(), io.StringIO()
        argv = ["runner", "--config", cfg_path, "--posture"]
        with mock.patch.object(sys, "argv", argv):
            with contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                rc = R.main()
        return rc, out.getvalue(), err.getvalue()

    def test_bad_mode_refuses_startup_naming_the_key(self):
        rc, _out, err = self._run_main({"oracle_tool_mode": "yolo"})
        self.assertEqual(rc, 2)
        self.assertIn("oracle_tool_mode", err)
        self.assertIn("yolo", err)

    def test_valid_mode_starts(self):
        rc, out, err = self._run_main({"oracle_tool_mode": "readonly"})
        self.assertNotEqual(rc, 2, err)
        self.assertIn("tool_mode=readonly", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
