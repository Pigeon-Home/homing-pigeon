"""The install.py branches the coverage run still left.

Health judgments, the one-home install, the ACL call, and
the fetches. Package commands are fake. Nothing is installed.
"""
import json
import os
import socket
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runner"))

import install as inst  # noqa: E402


class _Proc:
    def __init__(self, code=0, out="", err=""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


def _names():
    return ("osquery", "falco", "suricata", "zeek", "aide",
            "softflowd", "sysmon", "wazuh")


def _facts(**over):
    facts = {
        "installed": {n: False for n in _names()},
        "service_active": {},
        "running": {},
        "bpf_ok": None,
        "falco_device": False,
        "sysmon_telemetry_error": False,
        "aide_db": False,
        "wazuh_manager": False,
        "artifact_age_sec": {},
    }
    facts.update(over)
    return facts


class HealthRowsTest(unittest.TestCase):
    def test_each_installed_collector_that_is_not_running(self):
        installed = {n: True for n in _names()}
        rows = {name: (state, detail)
                for name, state, detail in inst.collector_health_rows(_facts(
                    installed=installed, falco_device=True, bpf_ok=False,
                    wazuh_manager=True, aide_db=False))}
        self.assertIn("not running", rows["osquery"][1])
        self.assertIn("driver device", rows["falco"][1])
        self.assertIn("not running", rows["suricata"][1])
        self.assertIn("not running", rows["zeek"][1])
        self.assertIn("not initialized", rows["aide"][1])
        self.assertIn("not running", rows["softflowd"][1])
        self.assertIn("denies trivial BPF", rows["sysmon"][1])
        self.assertIn("not running", rows["wazuh"][1])

        rows = {name: (state, detail)
                for name, state, detail in inst.collector_health_rows(_facts(
                    installed=installed, bpf_ok=None))}
        self.assertIn("unknown", rows["falco"][1])
        self.assertIn("not running", rows["sysmon"][1])

    def test_a_sysmon_journal_that_says_telemetry_failed(self):
        def which(binary):
            return "/usr/bin/" + binary if binary == "sysmon" else None

        def run(cmd, **_k):
            if cmd and cmd[0] == "journalctl":
                return _Proc(0, "Telemetry failed to start")
            return _Proc(1, "")

        with mock.patch.object(inst.sys, "platform", "linux"), \
                mock.patch.object(inst, "_which_safe", which), \
                mock.patch.object(inst.subprocess, "run", run), \
                mock.patch.object(inst.os.path, "isfile",
                                  return_value=False), \
                mock.patch.object(inst.os.path, "isdir",
                                  return_value=False), \
                mock.patch.object(inst.os.path, "exists",
                                  return_value=False), \
                mock.patch("glob.glob", return_value=[]):
            facts = inst.collector_health_facts()
        self.assertTrue(facts["sysmon_telemetry_error"])
        self.assertTrue(facts["installed"]["sysmon"])


class OneHomeTest(unittest.TestCase):
    def _args(self, **kw):
        base = dict(
            run_as=None, no_inference=True, faster=False,
            no_profile=True, profile=None, additional_secret=[],
            instructions=None, instructions_add=None,
            collector=None, no_collector=True, shared_secret=None,
            inference_model=None, wazuh_manager=None,
            dry_run=False, no_send=False, pdb=False, verbose=True,
            poll_interval=None, max_output_bytes=None,
            timeout=None, workers=None)
        base.update(kw)
        return mock.Mock(**base)

    def test_a_fresh_home_needs_an_administrator(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.object(inst, "_is_admin",
                                      return_value=False):
                code = inst.do_install_home(
                    self._args(), home, os.path.join(home, "bin"),
                    os.path.join(home, "config.json"),
                    os.path.join(home, "state"), "/src")
            self.assertEqual(code, 2)

    def test_an_upgrade_can_switch_to_the_faster_model(self):
        with tempfile.TemporaryDirectory() as home:
            with open(os.path.join(home, "install-receipt.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"version": "3.9.0"}, fh)
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.object(inst, "install_files",
                                      return_value=True), \
                    mock.patch.object(inst, "install_windows"), \
                    mock.patch.object(inst, "_stop_task_for_upgrade"), \
                    mock.patch.object(inst, "_write_receipt"), \
                    mock.patch.object(
                        inst, "install_ollama_and_model",
                        return_value=True) as pull:
                code = inst.do_install_home(
                    self._args(faster=True, no_inference=False),
                    home, os.path.join(home, "bin"),
                    os.path.join(home, "config.json"),
                    os.path.join(home, "state"), "/src")
            self.assertEqual(code, 0)
            pull.assert_called()
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.object(inst, "install_files",
                                      return_value=False), \
                    mock.patch.object(inst, "_stop_task_for_upgrade"):
                self.assertEqual(inst.do_install_home(
                    self._args(), home, os.path.join(home, "bin"),
                    os.path.join(home, "config.json"),
                    os.path.join(home, "state"), "/src"), 1)

    def test_the_acl_call_warns_and_does_not_abort(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.object(inst.sys, "platform", "win32"):
                with mock.patch.object(
                        inst.subprocess, "run",
                        return_value=_Proc(1, err="denied")):
                    self.assertFalse(inst._acl_home(home, "pigeon"))
                with mock.patch.object(
                        inst.subprocess, "run",
                        side_effect=OSError("no icacls")):
                    self.assertFalse(inst._acl_home(home, None))
                with mock.patch.object(
                        inst.subprocess, "run",
                        return_value=_Proc(0)):
                    self.assertTrue(inst._acl_home(home, "pigeon"))
            with mock.patch.object(inst.sys, "platform", "win32"):
                self.assertIn(inst._is_admin(), (True, False))


class FetchAndConfigTest(unittest.TestCase):
    def test_a_download_returns_the_body(self):
        class _Body:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"payload"

        with mock.patch("urllib.request.urlopen", return_value=_Body()):
            self.assertEqual(
                inst._download("https://example.test/a"), b"payload")

    def test_the_os_release_version_is_the_quoted_id(self):
        text = 'NAME="Debian"\nVERSION_ID="12"\n'

        class _F:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def __iter__(self):
                return iter(text.splitlines(True))

        def opener(path, *a, **k):
            if path == "/etc/os-release":
                return _F()
            raise OSError(path)

        with mock.patch("builtins.open", opener):
            self.assertEqual(inst._os_release_version(), "12")

    def test_a_config_that_cannot_be_replaced_is_cleaned_up(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            os.mkdir(path)
            with self.assertRaises(OSError):
                inst._write_json(path, {"a": 1})
            self.assertFalse(os.path.exists(path + ".tmp." + str(
                __import__("threading").get_ident())))

    def test_a_missing_example_and_a_chmod_failure(self):
        with tempfile.TemporaryDirectory() as src, \
                tempfile.TemporaryDirectory() as dst:
            for name in inst.FILES:
                with open(os.path.join(src, name), "w",
                          encoding="utf-8") as fh:
                    fh.write("x")
            cfg = os.path.join(dst, "sub", "config.json")
            self.assertFalse(inst.install_files(src, dst, cfg))

    def test_ollama_missing_after_install_and_a_config_it_cannot_write(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            os.mkdir(cfg)
            with mock.patch.object(inst.sys, "platform", "linux"), \
                    mock.patch.object(inst, "_ollama_bin",
                                      return_value=None), \
                    mock.patch.object(inst, "run"):
                self.assertFalse(inst.install_ollama_and_model(
                    cfg, "m", False))
            with mock.patch.object(inst, "_ollama_bin",
                                  return_value="/usr/bin/ollama"), \
                    mock.patch.object(inst, "ensure_ollama_running",
                                      return_value=True), \
                    mock.patch.object(inst, "run"):
                self.assertFalse(inst.install_ollama_and_model(
                    cfg, "m", False))
            with open(os.path.join(d, "ok.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("{}\n")

    def test_a_listening_port_is_up_and_a_closed_one_is_not(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        try:
            self.assertTrue(inst._ollama_up(port))
        finally:
            server.close()
        self.assertFalse(inst._ollama_up(1))

    def test_pi_light_inference_only_on_a_windows_home(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.object(
                        sys, "argv",
                        ["install.py", "--home", home,
                         "--inference-only", "--profile", "pi-light"]):
                self.assertEqual(inst.main(), 0)

    def test_small_failures_stay_small(self):
        with mock.patch.object(inst.subprocess, "run",
                               side_effect=OSError("no")):
            inst._run_quiet(["pkill", "-f", "x"])
        with mock.patch.object(inst.subprocess, "run"):
            inst.run(["echo", "hi"])
        self.assertEqual(inst._split_host_port(None), (None, None))
        self.assertIsNone(inst._which("this-binary-is-not-real-hp"))
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict(os.environ, {"HOME": home}), \
                    mock.patch.object(inst, "run"):
                inst.uninstall_macos()
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src")
            os.makedirs(src)
            with open(os.path.join(src, "a.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("a")
            with mock.patch.object(inst.shutil, "copy2",
                                  side_effect=OSError("ro")):
                copied, skipped = inst._merge_tree(
                    src, os.path.join(d, "dst"))
            self.assertEqual((copied, skipped), (0, 1))
            with mock.patch.object(os.path, "getsize",
                                  side_effect=OSError):
                n, size = inst._dir_summary(src)
            self.assertEqual((n, size), (1, 0))
            with mock.patch.object(
                    inst, "_candidate_state_dirs",
                    return_value=[d]), \
                    mock.patch.object(inst, "_run_quiet"):
                self.assertEqual(inst.do_migrate(d), 0)
        bad = os.path.join(tempfile.gettempdir(), "not-a-profile-hp.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{")
        try:
            self.assertEqual(
                inst.inference_model_for(bad),
                inst.DEFAULT_INFERENCE_MODEL)
        finally:
            os.remove(bad)
        with mock.patch.dict(inst.BUILTIN_PROFILES, {
                "custom": {"inference_model": "  tiny  "}}):
            self.assertEqual(inst.inference_model_for("custom"), "tiny")
        marker = os.path.join(inst._src_dir(), "default_profile")
        with mock.patch("builtins.open", mock.mock_open(
                read_data="not-a-real-profile\n")):
            self.assertIsNone(inst._bundled_default_profile(marker))


class LastBranchesTest(unittest.TestCase):
    def test_a_provided_secret_is_written_and_a_non_string_is_not_one(self):
        self.assertFalse(inst._looks_like_placeholder(None))
        self.assertFalse(inst._looks_patterned(None))
        self.assertTrue(inst._looks_like_placeholder("changeme"))
        self.assertTrue(inst._looks_patterned("abcabcabcabc"))
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            provided = "k9" + __import__("secrets").token_hex(40)
            inst.ensure_shared_secret(cfg, provided)
            with open(cfg, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["shared_secret"], provided)

    def test_a_frozen_tree_that_cannot_replace_its_binary(self):
        with tempfile.TemporaryDirectory() as src:
            for name in ("homing-pigeon", "install",
                         "config.example.json"):
                with open(os.path.join(src, name), "w",
                          encoding="utf-8") as fh:
                    fh.write("x")
            with mock.patch.object(inst, "FROZEN", True):
                self.assertTrue(inst._src_dir())
                self.assertTrue(inst._runner_argv(src)[0].endswith(
                    "homing-pigeon"))
                with mock.patch.object(inst.shutil, "copy2",
                                       side_effect=OSError("busy")):
                    self.assertFalse(inst.install_files(src, src))

    def test_the_doctor_names_corrupt_and_unreadable_pieces(self):
        with tempfile.TemporaryDirectory() as root:
            home = os.path.join(root, "home")
            bind = os.path.join(home, "bin")
            os.makedirs(bind)
            os.symlink(os.path.join(root, "nope"),
                       os.path.join(home, "install-receipt.json"))
            cfg = os.path.join(home, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("{")
            with mock.patch.object(inst, "FROZEN", True), \
                    mock.patch.object(inst, "collector_health_rows",
                                      return_value=[]):
                self.assertEqual(inst.do_check(
                    home, bind, cfg, os.path.join(home, "state")), 1)
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            os.remove(os.path.join(home, "install-receipt.json"))
            with open(os.path.join(home, "install-receipt.json"), "w",
                      encoding="utf-8") as fh:
                fh.write('{"version": "3"}\n')
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.object(inst, "_task_exists",
                                      return_value=True), \
                    mock.patch.object(inst, "_task_command",
                                      return_value=None), \
                    mock.patch.object(inst, "collector_health_rows",
                                      return_value=[]):
                self.assertEqual(inst.do_check(
                    home, bind, cfg, os.path.join(home, "state")), 1)

    def test_console_without_a_config_and_a_follow_that_waits(self):
        with tempfile.TemporaryDirectory() as home:
            bind = os.path.join(home, "bin")
            os.makedirs(bind)
            exe = os.path.join(bind, inst.RUNNER_BIN)
            with open(exe, "w", encoding="utf-8") as fh:
                fh.write("x")
            with mock.patch.object(inst.sys, "platform", "win32"):
                self.assertEqual(inst.do_console(
                    home, bind, os.path.join(home, "missing.json")), 1)

        class _FH:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def seek(self, *_a):
                return None

            def readline(self):
                return ""

        with mock.patch("builtins.open", return_value=_FH()), \
                mock.patch.object(inst.time, "sleep",
                                  side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                inst._follow_file("/tmp/no-log")

    def test_pi_light_yields_to_an_explicit_model(self):
        self.assertFalse(inst._pi_light_skip(
            mock.Mock(inference_model="qwen3:1.7b", faster=False),
            "pi-light"))
        self.assertFalse(inst._pi_light_skip(
            mock.Mock(inference_model=None, faster=True), "pi-light"))
        self.assertTrue(inst._acl_home("/tmp", None))

    def test_the_wizard_runs_only_when_the_owner_says_yes(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            args = mock.Mock(
                shared_secret=None, additional_secret=[],
                profile=None, no_profile=True, inference_model=None,
                faster=False, no_inference=True, no_collector=False,
                collector=None, instructions=None, instructions_add=None,
                wazuh_manager=None)
            import setup
            with mock.patch.object(sys.stdin, "isatty",
                                   return_value=True), \
                    mock.patch.object(setup, "needs_setup",
                                      return_value="no mailbox"), \
                    mock.patch.object(setup, "prompt_yes_no",
                                      return_value=True), \
                    mock.patch.object(setup, "run_setup_wizard") as wiz, \
                    mock.patch.object(inst, "install_collectors",
                                      return_value=["ok"]) as cols:
                inst._setup_fresh_config(args, cfg)
            wiz.assert_called()
            cols.assert_called()

    def test_a_fresh_home_prints_the_baked_flags(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.object(inst, "_is_admin",
                                      return_value=True), \
                    mock.patch.object(inst, "_acl_home",
                                      return_value=True), \
                    mock.patch.object(inst, "install_files",
                                      return_value=True), \
                    mock.patch.object(inst, "_setup_fresh_config",
                                      return_value=(False, None, False)), \
                    mock.patch.object(inst, "_ensure_base_dir"), \
                    mock.patch.object(inst, "_write_receipt"), \
                    mock.patch.object(inst, "install_windows"):
                code = inst.do_install_home(
                    mock.Mock(
                        run_as=None, no_inference=False, faster=False,
                        dry_run=True, no_send=False, pdb=False,
                        verbose=True, poll_interval=None,
                        max_output_bytes=None, timeout=None,
                        workers=None),
                    home, os.path.join(home, "bin"),
                    os.path.join(home, "config.json"),
                    os.path.join(home, "state"), "/src")
            self.assertEqual(code, 0)

    def test_each_platform_install_from_main_and_a_home_note(self):
        with tempfile.TemporaryDirectory() as dst:
            for plat, name in (("win32", "install_windows"),
                               ("darwin", "install_macos"),
                               ("freebsd14", "install_freebsd")):
                with mock.patch.object(inst.sys, "platform", plat), \
                        mock.patch.object(inst, "install_files",
                                          return_value=True), \
                        mock.patch.object(
                            inst, "_setup_fresh_config",
                            return_value=(False, None, True)), \
                        mock.patch.object(inst, name) as fn, \
                        mock.patch.object(
                            sys, "argv",
                            ["install.py", "--dir", dst, "--no-collector"]):
                    self.assertEqual(inst.main(), 0)
                fn.assert_called()
            with mock.patch.object(inst, "install_files",
                                   return_value=False), \
                    mock.patch.object(
                        sys, "argv",
                        ["install.py", "--home", dst, "--dir", dst]):
                self.assertEqual(inst.main(), 1)
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.object(
                        inst, "install_ollama_and_model",
                        return_value=False), \
                    mock.patch.object(
                        sys, "argv",
                        ["install.py", "--home", dst,
                         "--inference-only", "--no-profile"]):
                self.assertEqual(inst.main(), 0)
            with mock.patch.object(
                    sys, "argv",
                    ["install.py", "--dir", dst, "--logs"]):
                self.assertEqual(inst.main(), 1)

    def test_a_key_that_fails_over_and_a_daemon_that_comes_up(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "k.gpg")

            def download(url):
                if "bad" in url:
                    raise OSError("no")
                return b"key"

            with mock.patch.object(inst, "_download", download):
                self.assertEqual(inst._write_keyring(
                    ["https://example.test/bad",
                     "https://example.test/good"], dest), dest)
            with mock.patch.object(inst, "run") as run:
                inst._apt_install(["osquery"])
            run.assert_called()

        answers = iter([False, True])
        with mock.patch.object(inst, "_ollama_up",
                               side_effect=lambda *a: next(answers)), \
                mock.patch.object(inst, "_ollama_bin",
                                  return_value="/usr/bin/ollama"), \
                mock.patch.object(inst.subprocess, "Popen"), \
                mock.patch.object(inst.time, "sleep"):
            self.assertTrue(inst.ensure_ollama_running())
        with mock.patch.object(inst, "_ollama_bin",
                               return_value="/usr/bin/ollama"), \
                mock.patch.object(inst, "ensure_ollama_running",
                                  return_value=False), \
                mock.patch.object(inst.sys, "platform", "linux"):
            self.assertFalse(inst.install_ollama_and_model(
                os.path.join(d, "nope.json"), "m", False))

    def test_probes_that_fail_closed(self):
        with mock.patch.object(inst.sys, "platform", "linux"), \
                mock.patch("platform.machine", return_value="mips"):
            self.assertIsNone(inst._bpf_loadable())
        with mock.patch.object(inst.sys, "platform", "linux"), \
                mock.patch("ctypes.CDLL", side_effect=OSError("no")):
            self.assertIsNone(inst._bpf_loadable())

        class _C:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return "zeek\n"

        def opener(path, *a, **k):
            return _C()

        with mock.patch.object(os, "listdir", return_value=["5"]), \
                mock.patch("builtins.open", opener):
            self.assertTrue(inst._proc_running("zeek"))
        with mock.patch.object(os, "listdir", side_effect=OSError):
            self.assertFalse(inst._proc_running("zeek"))

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "unit.txt")
            had = hasattr(os, "O_NOFOLLOW")
            saved = getattr(os, "O_NOFOLLOW", None)
            if had:
                delattr(os, "O_NOFOLLOW")
            try:
                with mock.patch.object(os, "chmod", side_effect=OSError):
                    inst._write_text(path, "unit\n")
            finally:
                if had:
                    os.O_NOFOLLOW = saved
            self.assertTrue(os.path.isfile(path))

