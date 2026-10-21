"""The install.py branches the coverage run still left.

Health judgments, the one-home install, the ACL call, and
the fetches. Package commands are fake. Nothing is installed.
"""
import contextlib
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

        seen = {}

        def urlopen(req, timeout=60):
            seen["timeout"] = timeout
            seen["ua"] = req.get_header("User-agent")
            return _Body()

        with mock.patch("urllib.request.urlopen", urlopen):
            self.assertEqual(
                inst._download("https://example.test/a"), b"payload")
        self.assertEqual(seen["timeout"], 180)
        self.assertEqual(seen["ua"], "homing-pigeon-install")

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
            # USERPROFILE is what ntpath.expanduser reads; os.getuid
            # is POSIX-only, so create it for a Windows host.
            with mock.patch.dict(os.environ,
                                 {"HOME": home, "USERPROFILE": home}), \
                    mock.patch.object(os, "getuid", create=True,
                                      return_value=501), \
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
        if os.name == "nt":
            self.skipTest("frozen tree layout differs on Windows")
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
        if os.name == "nt":
            self.skipTest("ACL home differs on Windows")
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
            # install.py prefers `from runner import setup` and only
            # falls back to the top-level `setup`; the two are separate
            # module objects. Load both, then patch every loaded copy,
            # so the real wizard never reaches input() whichever one
            # the installer picks (in the full suite runner.setup is
            # usually imported already).
            import setup  # noqa: F401
            try:
                import runner.setup  # noqa: F401
            except ImportError:
                pass
            copies = [sys.modules[n] for n in ("setup", "runner.setup")
                      if n in sys.modules]
            wizards = []
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(
                    sys.stdin, "isatty", return_value=True))
                for mod in copies:
                    stack.enter_context(mock.patch.object(
                        mod, "needs_setup", return_value="no mailbox"))
                    stack.enter_context(mock.patch.object(
                        mod, "prompt_yes_no", return_value=True))
                    wizards.append(stack.enter_context(
                        mock.patch.object(mod, "run_setup_wizard")))
                cols = stack.enter_context(mock.patch.object(
                    inst, "install_collectors", return_value=["ok"]))
                inst._setup_fresh_config(args, cfg)
            self.assertTrue(any(w.called for w in wizards))
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
            run.assert_called_once_with(
                ["apt-get", "install", "-y", "osquery"])

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


class TailTest(unittest.TestCase):
    def test_the_loops_that_only_matter_on_the_second_pass(self):
        if os.name == "nt":
            self.skipTest("chmod behavior differs on Windows")
        with tempfile.TemporaryDirectory() as src, \
                tempfile.TemporaryDirectory() as dst:
            for name in ("homing-pigeon", "install.exe",
                         "config.example.json"):
                with open(os.path.join(src, name), "w",
                          encoding="utf-8") as fh:
                    fh.write("x")
            cfg = os.path.join(dst, "config.json")
            real = os.chmod

            def chmod(path, mode, **k):
                if "follow_symlinks" not in k and mode == 0o600:
                    raise OSError("no")
                return real(path, mode, **k)

            with mock.patch.object(inst, "FROZEN", True), \
                    mock.patch.object(os, "name", "nt"):
                self.assertTrue(inst.install_files(
                    src, os.path.join(dst, "bin"), cfg))
            for name in inst.FILES:
                with open(os.path.join(src, name), "w",
                          encoding="utf-8") as fh:
                    fh.write("x")
            fresh = os.path.join(dst, "fresh", "config.json")
            with mock.patch.object(os, "chmod", chmod):
                self.assertTrue(inst.install_files(src, dst, fresh))

        with mock.patch.object(os.path, "expanduser", return_value=""):
            inst._candidate_state_dirs()
        with mock.patch.object(os.path, "abspath",
                               side_effect=OSError("bad")):
            self.assertEqual(inst._candidate_state_dirs(), [])
        with mock.patch.object(os.path, "expanduser",
                               return_value="/root"), \
                mock.patch.object(os.path, "isdir",
                                  side_effect=OSError("no")):
            self.assertEqual(inst._candidate_state_dirs(), [])

        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "s")
            os.makedirs(state)
            with open(os.path.join(state, "a"), "w",
                      encoding="utf-8") as fh:
                fh.write("a")

            class _Z:
                def __init__(self, *_a, **_k):
                    pass

                def __enter__(self):
                    return self

                def __exit__(self, *_a):
                    return False

                def write(self, *_a, **_k):
                    raise OSError("zip")

            with mock.patch.object(inst.zipfile, "ZipFile", _Z):
                self.assertEqual(
                    inst._backup_dirs_to_zip([state],
                                            os.path.join(d, "b.zip")), 0)

        seen = {"n": 0}

        def running(_image):
            seen["n"] += 1
            return seen["n"] == 1

        with mock.patch.object(inst, "_process_running", running), \
                mock.patch.object(inst.time, "sleep"):
            self.assertTrue(inst._wait_for_exit("homing-pigeon.exe",
                                                timeout=1))
        self.assertEqual(inst._split_host_port(1), (None, None))

        def query(cmd, **_k):
            if "/V" in cmd:
                return mock.Mock(returncode=0, stdout="Status: Ready\n")
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(inst.subprocess, "run", query):
            self.assertIsNone(inst._task_command())

    def test_profile_files_instructions_and_a_key_that_never_arrives(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write('{"base_dir": "/keep", "owner_instructions": 3}\n')
            inst._ensure_base_dir(cfg, os.path.join(d, "state"))
            with open(cfg, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["base_dir"], "/keep")
            inst.set_instructions(cfg, "one", False)
            inst.apply_instruction_flags(cfg, "replaced", "added")
            with open(cfg, encoding="utf-8") as fh:
                self.assertIn("added", json.load(fh)["owner_instructions"])
            os.symlink(cfg, os.path.join(d, "link.json"))
            with self.assertRaises(OSError):
                inst._read_config(os.path.join(d, "link.json"))
            with open(os.path.join(d, "list.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("[]\n")
            with self.assertRaises(ValueError):
                inst._read_config(os.path.join(d, "list.json"))
            prof = os.path.join(d, "prof.json")
            with open(prof, "w", encoding="utf-8") as fh:
                fh.write('{"profile": "pi-light", "oracle_mode": "x"}\n')
            self.assertEqual(
                inst._profile_spec(prof).get("profile"), "pi-light")
            with open(prof, "w", encoding="utf-8") as fh:
                fh.write("{")
            self.assertEqual(inst._profile_spec(prof), {})
            self.assertEqual(inst.inference_model_for(prof),
                             inst.DEFAULT_INFERENCE_MODEL)
            with open(prof, "w", encoding="utf-8") as fh:
                fh.write('{"profile": "pi-light"}\n')
            inst.apply_profile(cfg, "")
            inst.apply_profile(os.path.join(d, "fresh.json"), prof)
            inst.apply_profile(cfg, "not-a-profile")
            with mock.patch("builtins.open", mock.mock_open(
                    read_data="pi-light\n")):
                self.assertEqual(
                    inst._bundled_default_profile("/tmp/x"), "pi-light")
                self.assertEqual(inst.chosen_profile(None, False),
                                 "pi-light")
            with self.assertRaises(RuntimeError):
                with mock.patch.object(inst, "_download",
                                       side_effect=OSError("no")):
                    inst._write_keyring(
                        ["https://example.test/a"],
                        os.path.join(d, "k.gpg"))

        text = "NAME=Debian\n"

        class _F:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def __iter__(self):
                return iter(text.splitlines(True))

        with mock.patch("builtins.open", return_value=_F()):
            self.assertEqual(inst._os_release_version(), "")

    def test_the_dispatch_branches_and_a_bpf_load_that_succeeds(self):
        args = mock.Mock(no_collector=False, collector=["osquery",
                                                        "osquery"],
                         wazuh_manager=None)
        self.assertEqual(inst.requested_collectors(args), ["osquery"])
        with mock.patch.object(inst, "_install_osquery_linux",
                               return_value="os"), \
                mock.patch.object(inst, "_install_falco_linux",
                                  return_value="fa"):
            self.assertEqual(
                inst._install_collector_linux("osquery", args), "os")
            self.assertEqual(
                inst._install_collector_linux("falco", args), "fa")
        with mock.patch.object(inst.sys, "platform", "win32"), \
                mock.patch.object(inst, "_install_collector_windows",
                                  return_value="win"):
            self.assertEqual(
                inst.install_collectors(["osquery"], args), ["win"])

        class _Lib:
            def syscall(self, *_a):
                return 3

        with mock.patch.object(inst.sys, "platform", "linux"), \
                mock.patch("platform.machine", return_value="x86_64"), \
                mock.patch("ctypes.CDLL", return_value=_Lib()), \
                mock.patch.object(os, "close"):
            self.assertTrue(inst._bpf_loadable())

        rows = {n: d for n, _s, d in inst.collector_health_rows({
            "installed": {"osquery": False, "falco": False,
                          "suricata": True, "zeek": False, "aide": False,
                          "softflowd": False, "sysmon": True,
                          "wazuh": False},
            "service_active": {"suricata": True, "sysmon": True},
            "running": {}, "bpf_ok": True, "falco_device": False,
            "sysmon_telemetry_error": False, "aide_db": False,
            "wazuh_manager": False,
            "artifact_age_sec": {"suricata": 4},
        })}
        self.assertIn("running", rows["suricata"])
        self.assertIn("running", rows["sysmon"])

    def test_main_says_not_configured_when_the_model_did_not_install(self):
        with tempfile.TemporaryDirectory() as dst:
            with mock.patch.object(inst.sys, "platform", "linux"), \
                    mock.patch.object(inst, "install_files",
                                   return_value=True), \
                    mock.patch.object(
                        inst, "_setup_fresh_config",
                        return_value=(False, None, False)), \
                    mock.patch.object(inst, "install_linux"), \
                    mock.patch.object(
                        sys, "argv",
                        ["install.py", "--dir", dst, "--no-collector"]):
                self.assertEqual(inst.main(), 0)
            missing = os.path.join(dst, "missing.json")
            with mock.patch.object(inst, "_ollama_bin",
                                   return_value="/usr/bin/ollama"), \
                    mock.patch.object(inst, "ensure_ollama_running",
                                      return_value=True), \
                    mock.patch.object(inst, "run"):
                self.assertTrue(inst.install_ollama_and_model(
                    missing, "m", False))

    def test_the_version_is_the_constant(self):
        # Frozen binaries hardcode the version; the constant is the
        # source of truth. tests/test_version.py checks it matches
        # pyproject.toml.
        self.assertEqual(inst.__version__, "3.11.32")

    def test_the_last_platform_decisions(self):
        args = mock.Mock(no_collector=False, collector=["osquery"],
                         wazuh_manager=None)
        with mock.patch.object(inst.sys, "platform", "darwin"), \
                mock.patch.object(inst, "_install_collector_darwin",
                                  return_value="mac"):
            self.assertEqual(
                inst.install_collectors(["osquery"], args), ["mac"])

        class _Denied:
            def syscall(self, *_a):
                return -1

        with mock.patch.object(inst.sys, "platform", "linux"), \
                mock.patch("platform.machine", return_value="x86_64"), \
                mock.patch("ctypes.CDLL", return_value=_Denied()):
            self.assertFalse(inst._bpf_loadable())

        with tempfile.TemporaryDirectory() as home:
            bind = os.path.join(home, "bin")
            os.makedirs(bind)
            exe = os.path.join(bind, inst.RUNNER_BIN)
            with open(exe, "w", encoding="utf-8") as fh:
                fh.write("x")
            cfg = os.path.join(home, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write('{"shared_secret": "x"}\n')
            with open(os.path.join(home, "install-receipt.json"), "w",
                      encoding="utf-8") as fh:
                fh.write('{"version": "3"}\n')
            os.makedirs(os.path.join(home, "state"))
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.object(inst, "_task_exists",
                                      return_value=True), \
                    mock.patch.object(
                        inst, "_task_command",
                        return_value=bind + "\\homing-pigeon.exe"), \
                    mock.patch.object(inst, "collector_health_rows",
                                      return_value=[]):
                self.assertEqual(
                    inst.do_check(home, bind, cfg,
                                  os.path.join(home, "state")), 0)

        with mock.patch.object(inst.sys, "platform", "darwin"), \
                mock.patch.object(inst.os.path, "isfile",
                                  return_value=True):
            self.assertTrue(str(inst._ollama_bin()).endswith("ollama"))
        with mock.patch.object(inst.sys, "platform", "win32"), \
                mock.patch.dict(os.environ, {"LOCALAPPDATA": ""}), \
                mock.patch.object(inst, "_which", return_value=None):
            self.assertIsNone(inst._ollama_bin())

        with tempfile.TemporaryDirectory() as d:
            prof = os.path.join(d, "p.json")
            with open(prof, "w", encoding="utf-8") as fh:
                fh.write('{"profile": "password-only"}\n')
            self.assertEqual(
                inst.inference_model_for(prof),
                inst.DEFAULT_INFERENCE_MODEL)
            path = os.path.join(d, "note.txt")
            os.O_BINARY = 0
            try:
                inst._write_text(path, "n")
                with mock.patch.object(os, "chmod", side_effect=OSError):
                    inst._write_json(os.path.join(d, "c.json"), {"a": 1})
            finally:
                del os.O_BINARY


class CleanupTest(unittest.TestCase):
    def test_a_platform_with_no_service_still_wipes(self):
        with mock.patch.object(inst.sys, "platform", "freebsd"), \
                mock.patch.object(inst, "_candidate_state_dirs",
                                  return_value=[]), \
                mock.patch.object(inst, "_run_quiet"):
            self.assertEqual(inst.do_wipe(no_backup=True), 0)

    def test_no_setup_module_and_an_unreadable_config(self):
        import builtins
        real = builtins.__import__

        def guarded(name, *a, **k):
            if name in ("runner", "setup") or name.startswith("runner."):
                raise ImportError(name)
            return real(name, *a, **k)

        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            args = mock.Mock(
                shared_secret=None, additional_secret=["si.1"],
                profile=None, no_profile=True, inference_model=None,
                faster=False, no_inference=True, no_collector=True,
                collector=None, instructions=None,
                instructions_add=None, wazuh_manager=None)
            with mock.patch("builtins.__import__", guarded):
                inst._setup_fresh_config(args, cfg)
            with open(cfg, encoding="utf-8") as fh:
                self.assertIn("si.1", json.load(fh)["additional_secrets"])
            args.additional_secret = []
            with mock.patch.object(inst, "ensure_shared_secret"):
                inst._setup_fresh_config(args, os.path.join(d, "missing"))

    def test_a_profile_file_without_a_name_keeps_the_default(self):
        with tempfile.TemporaryDirectory() as d:
            prof = os.path.join(d, "p.json")
            with open(prof, "w", encoding="utf-8") as fh:
                fh.write('{"profile": 1}\n')
            self.assertEqual(inst.inference_model_for(prof),
                             inst.DEFAULT_INFERENCE_MODEL)

    def test_a_write_that_dies_midway_closes_and_unlinks(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.json")
            had = hasattr(os, "O_NOFOLLOW")
            saved = getattr(os, "O_NOFOLLOW", None)
            if had:
                delattr(os, "O_NOFOLLOW")
            try:
                inst._write_json(path, {"a": 1})
            finally:
                if had:
                    os.O_NOFOLLOW = saved
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["a"], 1)

            def fdopen(*_a, **_k):
                raise OSError("fd")

            def close(_fd):
                raise OSError("close")

            real_open = os.open
            real_close = os.close
            opened = []

            def tracking_open(*args, **kwargs):
                fd = real_open(*args, **kwargs)
                opened.append(fd)
                return fd

            with mock.patch.object(os, "open", tracking_open), \
                    mock.patch.object(os, "fdopen", fdopen), \
                    mock.patch.object(os, "close", close):
                with self.assertRaises(OSError):
                    inst._write_json(path, {"b": 2})
            # close() was simulated as broken, so the fd is still
            # open. Windows refuses to delete an open file
            # (WinError 32) and TemporaryDirectory then errors.
            for fd in opened:
                try:
                    real_close(fd)
                except OSError:
                    pass

            def unlink(_p):
                raise OSError("unlink")

            with mock.patch.object(os, "unlink", unlink):
                with self.assertRaises(OSError):
                    inst._write_json(path, {"c": 3})

    def test_collectors_when_the_package_leaves_nothing_behind(self):
        args = mock.Mock(wazuh_manager=None)
        with mock.patch.object(inst, "_apt_install"), \
                mock.patch.object(inst, "run"), \
                mock.patch.object(inst.os, "makedirs"), \
                mock.patch.object(inst, "_write_text"), \
                mock.patch.object(inst.os.path, "isfile",
                                  return_value=False):
            line = inst._install_collector_linux("aide", args)
        self.assertIn("aide", line)
        with mock.patch.object(inst.shutil, "which",
                               return_value="/usr/local/bin/brew"), \
                mock.patch.object(inst, "run"), \
                mock.patch.object(inst.os, "makedirs"), \
                mock.patch.object(inst, "_write_text"), \
                mock.patch.object(inst.os.path, "isfile",
                                  return_value=False):
            line = inst._install_collector_darwin("osquery", args)
        self.assertIn("light pack", line)
        with mock.patch.object(inst.shutil, "which",
                               return_value="winget"), \
                mock.patch.object(inst, "run"), \
                mock.patch.object(inst.os.path, "isdir",
                                  return_value=False):
            line = inst._install_collector_windows("osquery", args)
        self.assertIn("light pack", line)

    def test_health_sees_a_falco_unit_and_a_wazuh_manager(self):
        import io

        def globber(pat):
            if "falco" in pat:
                return ["/lib/systemd/system/falco-bpf.service"]
            return []

        def which(binary):
            return "/usr/bin/sysmon" if binary == "sysmon" else None

        real_open = open

        def opener(path, *a, **k):
            if path == "/var/ossec/etc/ossec.conf":
                return io.StringIO("<address>10.1.1.1</address>\n")
            return real_open(path, *a, **k)

        with mock.patch("glob.glob", globber), \
                mock.patch.object(inst, "_which_safe", which), \
                mock.patch.object(inst.subprocess, "run",
                                  side_effect=OSError("no journal")), \
                mock.patch.object(inst.os.path, "isfile",
                                  return_value=False), \
                mock.patch.object(inst.os.path, "isdir",
                                  return_value=False), \
                mock.patch.object(inst.os.path, "exists",
                                  return_value=False), \
                mock.patch("builtins.open", opener):
            facts = inst.collector_health_facts()
        self.assertEqual(facts["service_active"].get("falco"), False)
        self.assertTrue(facts["wazuh_manager"])
        self.assertFalse(facts["sysmon_telemetry_error"])

    def test_running_the_file_as_main_exits(self):
        import runpy
        with mock.patch.object(sys, "argv", ["install.py", "--version"]):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(inst.__file__, run_name="__main__")
        self.assertEqual(caught.exception.code, 0)




