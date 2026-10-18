#!/usr/bin/env python3
"""Installer gaps: auto profile, secret safety, inference setup.

No live Ollama, no network, no curl. Subprocess is mocked.
"""
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "runner"))

from install import (  # noqa: E402
    DEFAULT_INFERENCE_MODEL,
    apply_profile,
    chosen_profile,
    daemon_popen_kwargs,
    detect_default_profile,
    inference_model_for,
    install_ollama_and_model,
    windows_task_command,
    ensure_runner_id,
    _ollama_bin,
)

_spec = importlib.util.spec_from_file_location(
    "homing_pigeon_runner_mod",
    os.path.join(REPO, "runner", "runner.py"))
pigeon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pigeon)


def _cfg(path, body):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh)
    os.chmod(path, 0o640)


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def _assert_mode(tc, path, expected):
    # Windows has no Unix permission bits; os.chmod is a no-op for them
    # and stat reports 0o666. The assertion is POSIX-only.
    if os.name == "nt":
        return
    tc.assertEqual(_mode(path), expected)


class ProfileSelectionTest(unittest.TestCase):
    def test_flags(self):
        self.assertIsNone(chosen_profile("raspberry-pi-home", True))
        self.assertEqual(chosen_profile("password-only", False), "password-only")
        with mock.patch("install.detect_default_profile", return_value="password-only"):
            self.assertEqual(chosen_profile(None, False), "password-only")
        self.assertIsNone(chosen_profile(None, True))

    def test_detect_reads_device_tree_then_cpuinfo(self):
        def open_pi(path, *args, **kwargs):
            if path == "/proc/device-tree/model":
                return io.StringIO("Raspberry Pi 4 Model B\x00")
            raise OSError(path)

        with mock.patch("builtins.open", side_effect=open_pi):
            self.assertEqual(detect_default_profile(), "raspberry-pi-home")

        def open_other(path, *args, **kwargs):
            if path == "/proc/device-tree/model":
                raise OSError(path)
            if path == "/proc/cpuinfo":
                return io.StringIO("processor\t: 0\nmodel name\t: not a pi\n")
            raise OSError(path)

        with mock.patch("builtins.open", side_effect=open_other):
            self.assertEqual(detect_default_profile(), "password-only")

    def test_project_default_is_the_battery_winner(self):
        # The default is a measured choice, not a habit: the full
        # eval battery (2026-10-18, hp-vmtest EVAL.md) under the
        # owner's ranking -- clean catch with no invention first,
        # then history/detail, then latency -- put qwen3:1.7b in
        # this slot (two clean catches, no invented findings,
        # history and detail passed). If this pin ever needs to
        # change, the battery that justifies the new value should
        # exist first.
        self.assertEqual(DEFAULT_INFERENCE_MODEL, "qwen3:1.7b")

    def test_pi_profile_pulls_the_lighter_llama(self):
        self.assertEqual(inference_model_for("raspberry-pi-home", None),
                         "llama3.2:1b")
        self.assertEqual(inference_model_for("password-only", None),
                         "qwen3:1.7b")
        self.assertEqual(inference_model_for(None, None), "qwen3:1.7b")
        self.assertEqual(inference_model_for("password-only", None, faster=True),
                         "qwen2.5:3b")
        self.assertEqual(inference_model_for(None, "llama3.2:3b", faster=True),
                         "llama3.2:3b")
        self.assertEqual(
            inference_model_for("raspberry-pi-home", "llama3.2:3b"),
            "llama3.2:3b")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "box.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"profile": "raspberry-pi-home"}, fh)
            self.assertEqual(inference_model_for(path, None), "llama3.2:1b")
            self.assertEqual(inference_model_for(path, "other:1b"), "other:1b")


class ProfileMergeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-prof-")
        self.path = os.path.join(self.tmp, "config.json")
        _cfg(self.path, {
            "mailbox_user": "a@b.c",
            "mailbox_password": "keep-me",
            "shared_secret": "keep-secret",
            "additional_secrets": {"lane": "keep-lane"},
            "redact_patterns_extra": {"vscode_token": "ghp_[A-Za-z0-9]{36}"},
        })

    def test_builtin_merges_patterns_and_locks_mode(self):
        apply_profile(self.path, "raspberry-pi-home")
        with open(self.path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertEqual(cfg["mailbox_user"], "a@b.c")
        self.assertEqual(cfg["shared_secret"], "keep-secret")
        self.assertEqual(cfg["additional_secrets"]["lane"], "keep-lane")
        self.assertEqual(cfg["max_result_view"], "attested")
        self.assertEqual(cfg["judge"], "advisory")
        self.assertIn("/home/pi/docs/manuals", cfg["protected_paths"])
        self.assertIn("vscode_token", cfg["redact_patterns_extra"])
        self.assertIn("shadow_hash", cfg["redact_patterns_extra"])
        self.assertNotIn("inference_model", cfg)
        _assert_mode(self, self.path, 0o600)
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_file_cannot_overwrite_secrets(self):
        hostile = os.path.join(self.tmp, "hostile.json")
        with open(hostile, "w", encoding="utf-8") as fh:
            json.dump({
                "profile": "hostile",
                "shared_secret": "stolen",
                "mailbox_user": "evil@x",
                "mailbox_password": "stolen",
                "additional_secrets": {"x": "y"},
                "max_result_view": "summary",
                "redact_patterns_extra": {"from_file": "ZZZ"},
            }, fh)
        apply_profile(self.path, hostile)
        with open(self.path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertEqual(cfg["shared_secret"], "keep-secret")
        self.assertEqual(cfg["mailbox_user"], "a@b.c")
        self.assertEqual(cfg["mailbox_password"], "keep-me")
        self.assertEqual(cfg["additional_secrets"], {"lane": "keep-lane"})
        self.assertEqual(cfg["max_result_view"], "summary")
        self.assertEqual(cfg["profile"], "hostile")
        self.assertIn("vscode_token", cfg["redact_patterns_extra"])
        self.assertIn("from_file", cfg["redact_patterns_extra"])
        _assert_mode(self, self.path, 0o600)

    def test_unknown_name_does_not_write(self):
        with open(self.path, "rb") as fh:
            before = fh.read()
        buf = io.StringIO()
        with redirect_stdout(buf):
            apply_profile(self.path, "not-a-profile")
        with open(self.path, "rb") as fh:
            self.assertEqual(fh.read(), before)
        self.assertIn("unknown", buf.getvalue())
        _assert_mode(self, self.path, 0o640)


class InstallOllamaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-ollama-")
        self.path = os.path.join(self.tmp, "config.json")
        _cfg(self.path, {"shared_secret": "keep-secret", "mailbox_user": "a@b.c"})

    def test_skip_writes_nothing(self):
        with open(self.path, "rb") as fh:
            before = fh.read()
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch("install.run") as run:
            install_ollama_and_model(self.path, "llama3.2:3b", skip=True)
        run.assert_not_called()
        with open(self.path, "rb") as fh:
            self.assertEqual(fh.read(), before)
        self.assertIn("skipped", buf.getvalue())
        _assert_mode(self, self.path, 0o640)

    def test_present_ollama_pulls_without_curl_and_locks_mode(self):
        with mock.patch("install._ollama_bin", return_value="ollama"), \
             mock.patch("install.ensure_ollama_running", return_value=True), \
             mock.patch("install.run") as run:
            ok = install_ollama_and_model(self.path, "llama3.2:3b; touch /tmp/nope", skip=False)
        self.assertTrue(ok)
        run.assert_called_once_with(
            ["ollama", "pull", "llama3.2:3b; touch /tmp/nope"])
        with open(self.path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertEqual(cfg["shared_secret"], "keep-secret")
        self.assertEqual(cfg["inference"]["endpoint"], "http://127.0.0.1:11434/v1")
        self.assertEqual(cfg["inference"]["model"], "llama3.2:3b; touch /tmp/nope")
        _assert_mode(self, self.path, 0o600)
        joined = " ".join(run.call_args[0][0])
        self.assertNotIn("curl", joined)
        self.assertNotIn("|", joined)

    def test_linux_install_command_is_pinned_and_failures_do_not_write(self):
        curl = ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"]
        with mock.patch("install._ollama_bin", return_value=None), \
             mock.patch("install.sys.platform", "linux"), \
             mock.patch("install.ensure_ollama_running", return_value=True), \
             mock.patch("install.run", side_effect=subprocess.CalledProcessError(1, curl)) as run:
            ok = install_ollama_and_model(self.path, "llama3.2:3b", skip=False)
        self.assertFalse(ok)
        run.assert_called_once_with(curl)
        with open(self.path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertNotIn("inference", cfg)
        self.assertEqual(cfg["shared_secret"], "keep-secret")

        with mock.patch("install._ollama_bin", return_value="/usr/bin/ollama"), \
             mock.patch("install.ensure_ollama_running", return_value=True), \
             mock.patch("install.run", side_effect=subprocess.CalledProcessError(1, "pull")):
            ok = install_ollama_and_model(self.path, "llama3.2:3b", skip=False)
        self.assertFalse(ok)
        with open(self.path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertNotIn("inference", cfg)


class OllamaBinTest(unittest.TestCase):
    """The stale-PATH bug: winget installs Ollama into %LOCALAPPDATA% but
    the running installer never picks up the registry PATH change, so
    'ollama pull' died with FileNotFoundError and no inference block was
    ever written. _ollama_bin checks the well-known locations first."""

    def test_windows_known_location_beats_path(self):
        fake = os.path.join("C:\\", "Users", "u", "AppData", "Local",
                            "Programs", "Ollama", "ollama.exe")
        with mock.patch("install.sys.platform", "win32"), \
             mock.patch.dict(os.environ, {"LOCALAPPDATA": os.path.join("C:\\", "Users", "u", "AppData", "Local")}), \
             mock.patch("install.os.path.isfile", return_value=True), \
             mock.patch("install._which", return_value=None):
            self.assertEqual(_ollama_bin(), fake)

    def test_falls_back_to_which(self):
        with mock.patch("install.sys.platform", "linux"), \
             mock.patch("install.os.path.isfile", return_value=False), \
             mock.patch("install._which", return_value="/usr/bin/ollama"):
            self.assertEqual(_ollama_bin(), "/usr/bin/ollama")

    def test_none_when_nowhere(self):
        with mock.patch("install.sys.platform", "linux"), \
             mock.patch("install.os.path.isfile", return_value=False), \
             mock.patch("install._which", return_value=None):
            self.assertIsNone(_ollama_bin())


class InferenceOnlyFlagTest(unittest.TestCase):
    def _tmp(self):
        d = tempfile.mkdtemp(prefix="hp-infonly-")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return d

    def test_inference_only_runs_just_the_model_setup(self):
        import install
        with mock.patch.object(install, "install_ollama_and_model", return_value=True) as oll, \
             mock.patch.object(install, "install_files") as files, \
             mock.patch.object(install, "ensure_shared_secret"), \
             mock.patch.object(sys, "argv", ["install", "--inference-only",
                                             "--dir", self._tmp()]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = install.main()
        self.assertEqual(code, 0)
        oll.assert_called_once()
        files.assert_not_called()
        self.assertIn("READY", buf.getvalue())

    def test_inference_only_reports_failure_actionably(self):
        import install
        with mock.patch.object(install, "install_ollama_and_model", return_value=False), \
             mock.patch.object(install, "install_files"), \
             mock.patch.object(install, "ensure_shared_secret"), \
             mock.patch.object(sys, "argv", ["install", "--inference-only",
                                             "--dir", self._tmp()]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = install.main()
        self.assertEqual(code, 0)
        self.assertIn("--inference-only", buf.getvalue())


class OracleUnconfiguredMessageTest(unittest.TestCase):
    def test_reject_tells_the_owner_how_to_fix(self):
        msg = pigeon._ORACLE_REJECTS["inference_unconfigured"]
        self.assertIn("--inference-only", msg)
        self.assertIn("inference.endpoint", msg)


class WindowsSpawnTest(unittest.TestCase):
    def test_windows_daemon_does_not_pass_start_new_session(self):
        for fn in (daemon_popen_kwargs, pigeon.daemon_popen_kwargs):
            win = fn(True)
            posix = fn(False)
            self.assertNotIn("start_new_session", win)
            self.assertEqual(win["creationflags"] & 0x00000008, 0x00000008)
            self.assertTrue(posix.get("start_new_session"))
            self.assertNotIn("creationflags", posix)

    def test_scheduled_task_command_is_not_posix_quoted(self):
        tr = windows_task_command(
            "/tmp/pigeon home", "/tmp/pigeon home/config.json",
            ["--workers", "2"])
        self.assertNotIn("'", tr)
        self.assertIn('"/tmp/pigeon home/config.json"', tr)
        self.assertIn("--workers", tr)
        self.assertIn(" 2", tr)
        self.assertIn("--config", tr)


class RunnerIdTest(unittest.TestCase):
    def test_ensure_runner_id_generates_128_bit(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"shared_secret": "x" * 64}, f)
            ensure_runner_id(path)
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
            rid = cfg["runner_id"]
            # 128 bits, hex-encoded.
            self.assertEqual(len(rid), 32)
            int(rid, 16)

    def test_ensure_runner_id_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"runner_id": "keep-me"}, f)
            ensure_runner_id(path)
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
            self.assertEqual(cfg["runner_id"], "keep-me")


if __name__ == "__main__":
    unittest.main(verbosity=2)
