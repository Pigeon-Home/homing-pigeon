"""Linux platform code: the bwrap argv, the systemd unit, the posture check.

Unit cases, one-field mutations, and a deterministic fuzz of the
confinement block. shutil.which and systemctl are mocked. Nothing
here execs bwrap, systemctl, or a job.
"""
import json
import os
import random
import shlex
import stat
import tempfile
import unittest
from io import StringIO
from unittest import mock

from runner import resources as RS
from runner import sandbox as SB
from runner import security as SEC
from runner.install import (
    detect_default_profile,
    do_wipe,
    install_files,
    install_linux,
    store_additional_secret,
    uninstall_linux,
)
from runner.posture import (
    _check_confinement_backend,
    _check_file_perms,
    _check_recommended_features,
    _check_service_unit,
)
from runner.senses import load_alerts, store_alert
from runner.runner import (
    _artifact_findings,
    _artifact_scan_enabled,
    _clam_hits,
    _clam_sig_line,
    _canary_state,
    _confinement_argv,
    _env_name_in,
    _file_artifact_hits,
    _file_fresh_lines,
    _firewall_posture,
    _host_log_tail,
    _label_auth,
    _local_watch,
    _oracle_watch_enabled,
    _parse_iptables_policy,
    _parse_ufw,
    _run_text,
    _runner_log_tail,
    _tail_marked,
    _yara_hits,
    _yara_rules_text,
    check_policy_constraints,
    kill_tree,
    oracle_context,
    platform_interpreter,
    script_filename,
)


def _argv(conf=None, env=None, args=None, interpreter=None, script="job.sh",
          workdir="/var/lib/pigeon/work"):
    """Build an argv with a fake interpreter. which() never searches PATH."""
    with mock.patch.object(SB.shutil, "which", return_value="/usr/bin/python3"):
        return SB.build_bwrap_command(
            {"security": {"confinement": conf or {}}},
            interpreter or ["python3", "-c"],
            script, workdir, list(args or []), dict(env or {}))


class SandboxAvailabilityTest(unittest.TestCase):
    def test_only_linux_with_bwrap_on_path(self):
        cases = [
            ("nt", "win32", "/usr/bin/bwrap", False),
            ("posix", "linux", None, False),
            ("posix", "linux", "/usr/bin/bwrap", True),
            ("posix", "darwin", "/usr/bin/bwrap", False),
            ("posix", "freebsd13", "/usr/bin/bwrap", False),
        ]
        for name, plat, found, expect in cases:
            with mock.patch.object(SB.os, "name", name), \
                 mock.patch.object(SB.sys, "platform", plat), \
                 mock.patch.object(SB.shutil, "which", return_value=found):
                self.assertEqual(SB.sandbox_available(), expect, plat)


class BwrapArgvTest(unittest.TestCase):
    def test_proven_flag_order_and_no_pid_namespace(self):
        argv = _argv(env={"JOB": "1"}, args=["--limit", "2"])
        self.assertEqual(argv[0], "bwrap")
        flags = argv[1:1 + len(SB.DEFAULT_FLAGS)]
        self.assertEqual(flags, SB.DEFAULT_FLAGS)
        self.assertNotIn("--unshare-pid", argv)
        self.assertLess(argv.index("--ro-bind"), argv.index("--proc"))
        self.assertLess(argv.index("--clearenv"), argv.index("--setenv"))
        bind = argv.index("--bind")
        self.assertEqual(argv[bind:bind + 4], [
            "--bind", "/var/lib/pigeon/work", "/work", "--chdir"])
        self.assertEqual(argv[bind + 4], "/work")
        self.assertEqual(argv[-5:], [
            "/usr/bin/python3", "-c", "/work/job.sh", "--limit", "2"])

    def test_custom_work_mount_is_both_bind_and_script_prefix(self):
        argv = _argv(conf={"work_mount": "/job"}, script="run.sh")
        self.assertIn("/job", argv)
        self.assertEqual(argv[argv.index("--chdir") + 1], "/job")
        self.assertIn("/job/run.sh", argv)
        self.assertNotIn("/work/run.sh", argv)

    def test_extra_flags_then_binds_then_scrubbed_env(self):
        argv = _argv(
            conf={
                "extra_flags": ["--unshare-pid"],
                "extra_ro_binds": [["/opt/data", "/data"]],
            },
            env={
                "OK": "kept",
                "A=B": "no",
                "": "no",
                "NIL": "a\x00b",
                "NUM": 1,
                2: "no",
            },
        )
        pid = argv.index("--unshare-pid")
        bind_ro = argv.index("/opt/data")
        path = argv.index("PATH")
        self.assertLess(pid, bind_ro)
        self.assertLess(bind_ro, path)
        self.assertEqual(argv[path + 1], "/usr/bin:/bin")
        self.assertIn("OK", argv)
        self.assertEqual(argv[argv.index("OK") + 1], "kept")
        self.assertNotIn("A=B", argv)
        self.assertNotIn("NUM", argv)

    def test_interpreter_mutations_raise_before_any_exec(self):
        with mock.patch.object(SB.shutil, "which", return_value=None):
            with self.assertRaises(RuntimeError):
                SB.build_bwrap_command({}, ["missing"], "s.sh", "/w", [], {})
        for bad in ([], ["python3", 1], None, "python3"):
            with self.assertRaises(RuntimeError):
                SB.build_bwrap_command({}, bad, "s.sh", "/w", [], {})


class ConfinementBlockMutations(unittest.TestCase):
    def _reject(self, block):
        with self.assertRaises(RuntimeError):
            SB._validate_confinement_block(block)

    def test_one_bad_field_is_refused_and_the_neighbors_pass(self):
        good = {
            "extra_flags": ["--die-with-parent"],
            "extra_ro_binds": [["/opt/data", "/data"]],
            "work_mount": "/work",
        }
        self.assertTrue(SB._validate_confinement_block(good))
        self.assertTrue(SB._validate_confinement_block({}))
        self._reject("nope")
        self._reject({**good, "extra_flags": "--die-with-parent"})
        self._reject({**good, "extra_flags": ["--ok", 1]})
        self._reject({**good, "extra_ro_binds": ["/opt/data", "/data"]})
        self._reject({**good, "extra_ro_binds": [["/only"]]})
        self._reject({**good, "extra_ro_binds": [["/opt", 2]]})
        self._reject({**good, "work_mount": "relative"})
        self._reject({**good, "work_mount": ""})
        self.assertTrue(SB._validate_confinement_block(
            {**good, "work_mount": "/a"}))

    def test_absolute_work_mount_of_one_character_passes(self):
        self.assertTrue(SB._validate_confinement_block({"work_mount": "/"}))


class SystemdUnitTest(unittest.TestCase):
    def test_user_unit_is_quoted_and_systemctl_is_not_a_shell(self):
        with tempfile.TemporaryDirectory() as home:
            calls = []
            with mock.patch.object(os.path, "expanduser",
                                   side_effect=lambda p: p.replace("~", home)), \
                 mock.patch("runner.install.run",
                            side_effect=lambda cmd, **kw: calls.append(list(cmd))):
                install_linux("/opt/homing pigeon", "/cfg/a.json", False,
                              ("--workers", "2", "has space"))
            path = os.path.join(home, ".config/systemd/user/homing-pigeon.service")
            with open(path, encoding="utf-8") as fh:
                unit = fh.read()
        self.assertIn("WantedBy=default.target", unit)
        start = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
        self.assertIn(shlex.quote("/opt/homing pigeon/runner.py"), start)
        self.assertIn(shlex.quote("has space"), start)
        self.assertNotIn("|", start)
        self.assertEqual(calls, [
            ["systemctl", "--user", "daemon-reload"],
            ["systemctl", "--user", "enable", "--now", "homing-pigeon.service"],
        ])

    def test_system_unit_targets_multi_user_and_does_not_touch_the_disk(self):
        written = {}

        class _Buf:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def write(self, text):
                written["unit"] = text

        def _open(path, mode="r", *args, **kwargs):
            if path == "/etc/systemd/system/homing-pigeon.service":
                return _Buf()
            raise AssertionError(path)

        calls = []
        with mock.patch("builtins.open", side_effect=_open), \
             mock.patch("runner.install.run",
                        side_effect=lambda cmd, **kw: calls.append(list(cmd))):
            install_linux("/opt/hp", "/cfg/a.json", True, ())
        self.assertIn("WantedBy=multi-user.target", written["unit"])
        self.assertEqual(calls[0], ["systemctl", "daemon-reload"])
        self.assertEqual(calls[1][0], "systemctl")
        self.assertNotIn("--user", calls[0])

    def test_uninstall_calls_disable_before_remove(self):
        order = []
        with mock.patch.object(os.path, "expanduser",
                               return_value="/tmp/hp-unit-not-real.service"), \
             mock.patch("runner.install.run",
                        side_effect=lambda cmd, **kw: order.append("run")), \
             mock.patch("runner.install.os.remove",
                        side_effect=lambda path: order.append("remove")):
            uninstall_linux(False)
        self.assertEqual(order[0], "run")
        self.assertEqual(order[1], "remove")


class PostureLinuxTest(unittest.TestCase):
    def test_confinement_backend_mutations(self):
        def check(plat, found):
            results = []
            with mock.patch("runner.posture.sys.platform", plat), \
                 mock.patch("runner.posture.shutil.which", return_value=found):
                _check_confinement_backend(results)
            return results[0]

        ok, _topic, detail = check("linux", "/usr/bin/bwrap")
        self.assertEqual(ok, "OK")
        self.assertIn("bwrap", detail)
        warn, _, detail = check("linux", None)
        self.assertEqual(warn, "WARN")
        self.assertIn("not installed", detail)
        other, _, detail = check("darwin", "/usr/bin/bwrap")
        self.assertEqual(other, "OK")
        self.assertIn("not applicable", detail)

    def test_unit_hardening_directives(self):
        with tempfile.TemporaryDirectory() as d:
            unit = os.path.join(d, "homing-pigeon.service")
            with open(unit, "w", encoding="utf-8") as fh:
                fh.write("NoNewPrivileges=yes\nProtectSystem=strict\n")

            def exists(path):
                return path == unit

            results = []
            with mock.patch("runner.posture.os.path.exists", side_effect=exists), \
                 mock.patch("runner.posture.os.path.expanduser", return_value=unit):
                _check_service_unit(results)
            self.assertEqual(results[0][0], "OK")
            self.assertIn("NoNewPrivileges", results[0][2])

            with open(unit, "w", encoding="utf-8") as fh:
                fh.write("ExecStart=/usr/bin/homing-pigeon\n")
            results = []
            with mock.patch("runner.posture.os.path.exists", side_effect=exists), \
                 mock.patch("runner.posture.os.path.expanduser", return_value=unit):
                _check_service_unit(results)
            self.assertEqual(results[0][0], "WARN")
            self.assertIn("lacks hardening", results[0][2])

            results = []
            with mock.patch("runner.posture.os.path.exists", side_effect=exists), \
                 mock.patch("runner.posture.os.path.expanduser", return_value=unit), \
                 mock.patch("builtins.open", side_effect=OSError("busy")):
                _check_service_unit(results)
            self.assertEqual(results[0][0], "WARN")
            self.assertIn("cannot read", results[0][2])

        results = []
        with mock.patch("runner.posture.os.path.exists", return_value=False):
            _check_service_unit(results)
        self.assertIn("no homing-pigeon systemd unit", results[0][2])


class ConfinementFuzzTest(unittest.TestCase):
    def test_random_blocks_either_reject_or_build_a_string_argv(self):
        rng = random.Random(20261017)

        def atom(depth):
            roll = rng.randrange(7)
            if roll == 0 or depth > 2:
                return rng.choice([
                    None, True, False, 0, 1, -1, "", "/", "rel",
                    "--die-with-parent", "\x00", "a=b", "/opt",
                ])
            if roll == 1:
                return rng.randrange(-2, 4)
            if roll == 2:
                n = rng.randrange(0, 8)
                return "".join(chr(rng.randrange(32, 127)) for _ in range(n))
            if roll == 3:
                return [atom(depth + 1) for _ in range(rng.randrange(0, 3))]
            if roll == 4:
                return {rng.choice(["extra_flags", "extra_ro_binds", "work_mount", "x"]):
                        atom(depth + 1)}
            return "\x00" * rng.randrange(0, 3)

        crashes = []
        for _ in range(300):
            block = atom(0)
            try:
                ok = SB._validate_confinement_block(block)
            except RuntimeError:
                continue
            except Exception as exc:
                crashes.append(("validate", type(exc).__name__, repr(block)[:80]))
                break
            if ok is not True:
                crashes.append(("validate-return", ok, repr(block)[:80]))
                break
            env = atom(0)
            if not isinstance(env, dict):
                env = {}
            try:
                with mock.patch.object(SB.shutil, "which",
                                       return_value="/usr/bin/python3"):
                    argv = SB.build_bwrap_command(
                        {"security": {"confinement": block}},
                        ["python3"], "job.sh", "/work", [], env)
            except Exception as exc:
                crashes.append(("build", type(exc).__name__, repr(block)[:80]))
                break
            if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
                crashes.append(("argv", argv[:5], repr(block)[:80]))
                break
            if argv[0] != "bwrap":
                crashes.append(("argv0", argv[0], repr(block)[:80]))
                break
        self.assertEqual(crashes, [])


class LinuxFirewallMutations(unittest.TestCase):
    def test_ufw_case_and_a_missing_space(self):
        self.assertEqual(
            _parse_ufw("STATUS: ACTIVE\nlogging: on"),
            "firewall: linux ufw=active")
        both = _parse_ufw("Status: active\nStatus: inactive")
        self.assertEqual(both, "firewall: linux ufw=active")
        self.assertIsNone(_parse_ufw("status:active"))
        self.assertIsNone(_parse_ufw(None))
        self.assertIsNone(_parse_ufw(1))

    def test_iptables_policy_mutations(self):
        forward = _parse_iptables_policy("-P FORWARD REJECT\n")
        self.assertIn("FORWARD=REJECT", forward)
        self.assertNotIn("T1562", forward)
        output_only = _parse_iptables_policy("-P OUTPUT DROP\n")
        self.assertIn("OUTPUT=DROP", output_only)
        self.assertIn("[T1562.004]", output_only)
        self.assertIn(
            "[T1562.004]",
            _parse_iptables_policy("-P INPUT drop\n"))
        self.assertIsNone(_parse_iptables_policy("-A INPUT -j DROP\n"))
        self.assertIsNone(_parse_iptables_policy("-P INPUT\n"))
        self.assertIsNone(_parse_iptables_policy(""))
        self.assertIsNone(_parse_iptables_policy(None))

    def test_ufw_wins_and_a_dead_ufw_falls_through(self):
        def which(name):
            if name == "ufw":
                return "/usr/sbin/ufw"
            if name == "iptables":
                return "/usr/sbin/iptables"
            return None

        def run_text(argv, timeout=5):
            if argv[:2] == ["ufw", "status"]:
                return "Status: inactive"
            if argv[:2] == ["iptables", "-S"]:
                return "-P INPUT DROP\n"
            raise AssertionError(argv)

        with mock.patch("runner.runner.sys.platform", "linux"), \
             mock.patch("runner.runner.shutil.which", side_effect=which), \
             mock.patch("runner.runner._run_text", side_effect=run_text):
            self.assertIn("ufw=inactive", _firewall_posture())

        def run_dead(argv, timeout=5):
            if argv[0] == "ufw":
                return None
            return "-P INPUT DROP\n"

        with mock.patch("runner.runner.sys.platform", "linux"), \
             mock.patch("runner.runner.shutil.which", side_effect=which), \
             mock.patch("runner.runner._run_text", side_effect=run_dead):
            line = _firewall_posture()
        self.assertIn("iptables", line)
        self.assertIn("INPUT=DROP", line)

        with mock.patch("runner.runner.sys.platform", "linux"), \
             mock.patch("runner.runner.shutil.which", return_value=None):
            self.assertIsNone(_firewall_posture())


class JournalFallbackTest(unittest.TestCase):
    def _tail(self, platform, stdout=None, rc=0, boom=False, journal=True):
        calls = []

        def run(argv, **kwargs):
            calls.append(list(argv))
            if boom:
                raise OSError("no journal")
            proc = mock.Mock()
            proc.returncode = rc
            proc.stdout = stdout
            return proc

        with mock.patch("runner.runner._AUTH_LOG_PATHS", ()), \
             mock.patch("runner.runner._SYS_LOG_PATHS", ()), \
             mock.patch("runner.runner.sys.platform", platform), \
             mock.patch("runner.runner.subprocess.run", side_effect=run):
            out = _host_log_tail(journal=journal, base_dir="")
        return out, calls

    def test_linux_reads_journal_errors_and_labels_auth(self):
        text = "failed password for root\nkernel: disk full\n"
        out, calls = self._tail("linux", stdout=text)
        self.assertEqual(calls[0][:4], ["journalctl", "-n", "20", "-p"])
        self.assertIn("failed password", out)
        self.assertIn("[T1110]", out)
        self.assertIn("disk full", out)
        self.assertNotIn("disk full [T", out)

    def test_mutations_that_are_not_a_readable_journal(self):
        for kwargs in (
            {"platform": "linux", "stdout": "", "rc": 1},
            {"platform": "linux", "stdout": None, "rc": 0},
            {"platform": "linux", "boom": True},
            {"platform": "linux", "stdout": "failed password\n", "journal": False},
            {"platform": "darwin", "stdout": "failed password\n"},
        ):
            out, calls = self._tail(**kwargs)
            self.assertIsNone(out)
            if kwargs["platform"] != "linux" or kwargs.get("journal") is False:
                self.assertEqual(calls, [])

    def test_a_bad_cap_and_a_long_journal_are_cut_from_the_end(self):
        lines = "\n".join("error %d" % i for i in range(30))
        out, _calls = self._tail("linux", stdout=lines)
        self.assertLessEqual(len(out.splitlines()), 20)
        self.assertIn("error 29", out)
        self.assertNotIn("error 0\n", out)
        short, _calls = self._tail("linux", stdout="failed password for root\n")
        with mock.patch("runner.runner._AUTH_LOG_PATHS", ()), \
             mock.patch("runner.runner._SYS_LOG_PATHS", ()), \
             mock.patch("runner.runner.sys.platform", "linux"), \
             mock.patch("runner.runner.subprocess.run",
                        return_value=mock.Mock(returncode=0, stdout="abcdefghij")):
            cut = _host_log_tail(max_chars="nope", base_dir="")
            tiny = _host_log_tail(max_chars=4, base_dir="")
        self.assertIn("abcdefghij", cut)
        self.assertEqual(tiny, "ghij")
        self.assertTrue(short)


class LinuxWipeTest(unittest.TestCase):
    def test_system_uninstall_disables_then_removes_the_unit(self):
        order = []
        with mock.patch("runner.install.run",
                        side_effect=lambda cmd, **kw: order.append(("run", list(cmd)))), \
             mock.patch("runner.install.os.remove",
                        side_effect=lambda path: order.append(("remove", path))):
            uninstall_linux(True)
        self.assertEqual(order, [
            ("run", ["systemctl", "disable", "--now", "homing-pigeon.service"]),
            ("remove", "/etc/systemd/system/homing-pigeon.service"),
            ("run", ["systemctl", "daemon-reload"]),
        ])

    def test_wipe_disables_both_units_and_deletes_nothing(self):
        calls = []
        with mock.patch("runner.install.sys.platform", "linux"), \
             mock.patch("runner.install._kill_runner_processes"), \
             mock.patch("runner.install._candidate_state_dirs", return_value=[]), \
             mock.patch("runner.install._run_quiet",
                        side_effect=lambda cmd: calls.append(list(cmd))):
            code = do_wipe(no_backup=True)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [
            ["systemctl", "--user", "disable", "--now", "homing-pigeon.service"],
            ["sudo", "-n", "systemctl", "disable", "--now",
             "homing-pigeon.service"],
        ])


class LinuxParserFuzzTest(unittest.TestCase):
    def test_random_text_never_raises_and_stays_a_linux_line(self):
        rng = random.Random(20261017)
        crashes = []
        for _ in range(300):
            roll = rng.randrange(5)
            if roll == 0:
                text = None
            elif roll == 1:
                text = rng.choice(["", 0, 1, True, [], {}])
            else:
                n = rng.randrange(0, 80)
                text = "".join(chr(rng.randrange(0, 128)) for _ in range(n))
                if rng.randrange(4) == 0:
                    text = "-P " + text
            for name, fn in (("ufw", _parse_ufw),
                             ("iptables", _parse_iptables_policy)):
                try:
                    got = fn(text)
                except Exception as exc:
                    crashes.append((name, type(exc).__name__))
                    break
                if got is None:
                    continue
                if not isinstance(got, str) or not got.startswith("firewall: linux "):
                    crashes.append((name, got[:40] if isinstance(got, str) else got))
                    break
            if crashes:
                break
        self.assertEqual(crashes, [])


def _conf(mode):
    return {"security": {"modes": {"confinement": mode}}}


def _audit_rows(base):
    path = os.path.join(base, "security-audit.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class ConfinementDecisionTest(unittest.TestCase):
    def test_off_and_a_bad_mode_stay_on_the_host(self):
        with tempfile.TemporaryDirectory() as d:
            for cfg in ({}, _conf("off"), _conf("sometimes"),
                        {"security": []}, None):
                argv, host, boxed = _confinement_argv(
                    cfg, d, "j", ["python3"], "/w/s.sh", "/w", [], {})
                self.assertEqual(argv[:2], ["python3", "/w/s.sh"])
                self.assertTrue(host)
                self.assertFalse(boxed)
            self.assertEqual(_audit_rows(d), [])

    def test_audit_does_not_ask_whether_bwrap_exists(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.runner._sandbox.sandbox_available") as avail, \
                 mock.patch("runner.runner._sandbox.build_bwrap_command") as build, \
                 mock.patch("runner.runner.subprocess.Popen") as popen:
                argv, host, boxed = _confinement_argv(
                    _conf("audit"), d, "j", ["python3"], "/w/s.sh",
                    "/w", ["a"], {"OK": "1"})
            avail.assert_not_called()
            build.assert_not_called()
            popen.assert_not_called()
            self.assertEqual(argv[0], "python3")
            self.assertTrue(host)
            self.assertFalse(boxed)
            row = _audit_rows(d)[-1]
            self.assertEqual(row["decision"], "would_sandbox")
            self.assertEqual(row["mode"], "audit")

    def test_enforce_falls_back_when_bwrap_or_the_build_is_missing(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.runner._sandbox.sandbox_available",
                            return_value=False), \
                 mock.patch("runner.runner.subprocess.Popen") as popen:
                argv, host, boxed = _confinement_argv(
                    _conf("enforce"), d, "j", ["python3"], "/w/s.sh",
                    "/w", [], {})
            popen.assert_not_called()
            self.assertTrue(host)
            self.assertFalse(boxed)
            self.assertEqual(_audit_rows(d)[-1]["reason"],
                             "confinement_unavailable")

            with mock.patch("runner.runner._sandbox.sandbox_available",
                            return_value=True), \
                 mock.patch("runner.runner._sandbox.build_bwrap_command",
                            side_effect=RuntimeError("no interpreter")), \
                 mock.patch("runner.runner.subprocess.Popen") as popen:
                argv, host, boxed = _confinement_argv(
                    _conf("enforce"), d, "j", ["python3"], "/w/s.sh",
                    "/w", [], {})
            popen.assert_not_called()
            self.assertFalse(boxed)
            row = _audit_rows(d)[-1]
            self.assertEqual(row["reason"], "confinement_build_failed")
            self.assertIn("no interpreter", row["detail"])

    def test_enforce_success_hands_back_bwrap_and_drops_the_host_env(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.runner._sandbox.sandbox_available",
                            return_value=True), \
                 mock.patch("runner.runner._sandbox.build_bwrap_command",
                            return_value=["bwrap", "--bind", "/w", "/work"]), \
                 mock.patch("runner.runner.subprocess.Popen") as popen:
                argv, host, boxed = _confinement_argv(
                    _conf("enforce"), d, "j", ["python3", "-c"],
                    "/w/s.sh", "/w", ["--x"], {"OK": "1"})
            popen.assert_not_called()
            self.assertEqual(argv[0], "bwrap")
            self.assertFalse(host)
            self.assertTrue(boxed)
            self.assertEqual(_audit_rows(d)[-1]["decision"], "sandboxed")


class PollWatchTest(unittest.TestCase):
    def test_the_poll_skips_journalctl(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.runner.sys.platform", "linux"), \
                 mock.patch("runner.runner._canary_watch"), \
                 mock.patch("runner.runner._firewall_watch"), \
                 mock.patch("runner.runner._av_watch"), \
                 mock.patch("runner.runner._host_log_tail") as tail, \
                 mock.patch("runner.runner.subprocess.run") as run:
                _local_watch({}, d)
            tail.assert_called_once()
            self.assertIs(tail.call_args.kwargs.get("journal"), False)
            run.assert_not_called()

    def test_watch_flag_mutations(self):
        skip = (False, 0, "false", "NO", "off", "0")
        keep = (True, 1, "yes", "on", "", None)
        for value in skip:
            self.assertFalse(_oracle_watch_enabled(
                {"inference": {"watch_system": value}}), value)
        for value in keep:
            self.assertTrue(_oracle_watch_enabled(
                {"inference": {"watch_system": value}}), value)
        self.assertTrue(_oracle_watch_enabled({}))
        self.assertTrue(_oracle_watch_enabled(None))
        self.assertTrue(_oracle_watch_enabled({"inference": []}))
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.runner._host_log_tail") as tail:
                _local_watch({"inference": {"watch_system": "off"}}, d)
            tail.assert_not_called()


class ConfinementDecisionFuzzTest(unittest.TestCase):
    def test_random_config_returns_a_triple_and_never_starts_a_process(self):
        rng = random.Random(20261017)

        def atom(depth):
            if depth > 2 or rng.randrange(4) == 0:
                return rng.choice([
                    None, True, False, 0, 1, "", "off", "audit",
                    "enforce", "sometimes", "/", "python3",
                ])
            if rng.randrange(2) == 0:
                return [atom(depth + 1) for _ in range(rng.randrange(0, 3))]
            key = rng.choice([
                "security", "modes", "confinement", "extra_flags",
                "work_mount", "inference", "watch_system",
            ])
            return {key: atom(depth + 1)}

        crashes = []
        with tempfile.TemporaryDirectory() as d, \
             mock.patch("runner.runner.subprocess.Popen",
                        side_effect=AssertionError("popen")), \
             mock.patch("runner.runner._sandbox.sandbox_available",
                        side_effect=lambda: rng.randrange(2) == 0), \
             mock.patch("runner.runner._sandbox.build_bwrap_command",
                        side_effect=lambda *a, **k: (
                            (_ for _ in ()).throw(RuntimeError("fuzz"))
                            if rng.randrange(4) == 0 else ["bwrap", "--"])):
            for _ in range(200):
                cfg = atom(0)
                if not isinstance(cfg, dict):
                    cfg = {"security": cfg}
                try:
                    got = _confinement_argv(
                        cfg, d, "j", ["python3"], "/w/s.sh", "/w", [],
                        {"OK": "1"})
                except Exception as exc:
                    crashes.append((type(exc).__name__, repr(cfg)[:80]))
                    break
                if (not isinstance(got, tuple) or len(got) != 3
                        or not isinstance(got[0], list)
                        or not isinstance(got[1], bool)
                        or not isinstance(got[2], bool)):
                    crashes.append(("shape", repr(got)[:80]))
                    break
                if got[2] and (got[1] or not got[0] or got[0][0] != "bwrap"):
                    crashes.append(("boxed", got[0][:3]))
                    break
                if not got[2] and not got[1]:
                    crashes.append(("host", got[:2]))
                    break
        self.assertEqual(crashes, [])


def _open_as(mapping):
    real = open

    def _open(path, *args, **kwargs):
        if path in mapping:
            return StringIO(mapping[path])
        return real(path, *args, **kwargs)

    return _open


class ProcSampleTest(unittest.TestCase):
    def test_proc_stat_mutations(self):
        cases = {
            "cpu  1 2 3 4 5\n": (9, 15),
            "cpu 1 2 3 4\n": (4, 10),
            "cpu\n": None,
            "cpu a b c d\n": None,
            "intr 1 2 3\n": None,
            "": None,
        }
        for text, expect in cases.items():
            with mock.patch("builtins.open", side_effect=_open_as({"/proc/stat": text})):
                self.assertEqual(RS._read_proc_stat(), expect, text)

    def test_cpu_fraction_clamps(self):
        self.assertAlmostEqual(RS._cpu_percent((0, 100), (0, 200)), 1.0)
        self.assertAlmostEqual(RS._cpu_percent((0, 100), (200, 200)), 0.0)
        self.assertIsNone(RS._cpu_percent((0, 100), ("x", 200)))
        self.assertIsNone(RS._cpu_percent((1,), (2, 3)))
        self.assertIsNone(RS._cpu_percent("cpu", (2, 3)))

    def test_meminfo_mutations(self):
        full = "MemTotal: 1000 kB\nMemAvailable: 250 kB\n"
        free = "MemTotal: 1000 kB\nMemFree: 250 kB\n"
        over = "MemTotal: 100 kB\nMemAvailable: 400 kB\n"
        for text, expect in ((full, 0.75), (free, 0.75), (over, 0.0)):
            with mock.patch("builtins.open", side_effect=_open_as({"/proc/meminfo": text})):
                self.assertAlmostEqual(RS._mem_fraction(), expect)
        for text in ("MemTotal: 0 kB\n", "MemFree: 1 kB\n", "nope\n", ""):
            with mock.patch("builtins.open", side_effect=_open_as({"/proc/meminfo": text})):
                self.assertIsNone(RS._mem_fraction(), text)

    def test_resource_config_mutations(self):
        self.assertTrue(RS.parse_resources({})["enabled"])
        for bad in (
            {"resources": {"enabled": "yes"}},
            {"resources": {"threshold": "high"}},
            {"resources": {"threshold": 0}},
            {"resources": {"threshold": 1.1}},
            {"resources": {"cooldown_sec": float("nan")}},
            {"resources": {"cooldown_sec": float("inf")}},
            {"resources": []},
            [],
        ):
            with self.assertRaises(RuntimeError):
                RS.parse_resources(bad)


class ClamAndPiTest(unittest.TestCase):
    def test_signature_age_mutations(self):
        now = 1_000_000.0
        day = 86400

        def mtime(path):
            if path.endswith("daily.cvd"):
                raise OSError("missing")
            if path.endswith("daily.cld"):
                return now - 8 * day
            raise OSError(path)

        with mock.patch("runner.runner.os.path.getmtime", side_effect=mtime):
            line = _clam_sig_line(now)
        self.assertIn("stale (8d)", line)
        self.assertIn("[T1562.001]", line)

        with mock.patch("runner.runner.os.path.getmtime",
                        return_value=now - day):
            self.assertEqual(_clam_sig_line(now), "av: clamav signatures current")
        with mock.patch("runner.runner.os.path.getmtime",
                        side_effect=OSError("none")):
            self.assertIsNone(_clam_sig_line(now))
        with mock.patch("runner.runner.os.path.getmtime",
                        side_effect=lambda path: __import__("time").time()):
            self.assertEqual(_clam_sig_line("nope"),
                             "av: clamav signatures current")

    def test_clam_hit_lines_do_not_run_a_scan(self):
        def which(name):
            return "/usr/bin/clamdscan" if name == "clamdscan" else None

        def hits(stdout, rc=1):
            proc = mock.Mock(returncode=rc, stdout=stdout)
            with mock.patch("runner.runner.shutil.which", side_effect=which), \
                 mock.patch("runner.runner.subprocess.run", return_value=proc) as run:
                got = _clam_hits("/work", ["/work/a.txt"])
            run.assert_called_once()
            argv = run.call_args.args[0]
            self.assertEqual(argv[0], "/usr/bin/clamdscan")
            self.assertNotIn("clamscan", argv)
            return got

        self.assertEqual(
            hits("/work/a.txt: Eicar-Test-Signature FOUND\n"),
            ["clamav Eicar-Test-Signature a.txt [T1204.002]"])
        self.assertEqual(hits("OK\n", rc=0), [])
        self.assertEqual(hits("/work/a.txt: Eicar FOUND\n", rc=2), [])
        self.assertEqual(hits(None, rc=1), [])
        self.assertEqual(hits("just a name FOUND\n"),
                         ["clamav just a name file [T1204.002]"])
        with mock.patch("runner.runner.shutil.which", return_value=None), \
             mock.patch("runner.runner.subprocess.run") as run:
            self.assertEqual(_clam_hits("/work", ["/work/a.txt"]), [])
            run.assert_not_called()
        with mock.patch("runner.runner.shutil.which", return_value="clamdscan"), \
             mock.patch("runner.runner.subprocess.run",
                        side_effect=OSError("down")):
            self.assertEqual(_clam_hits("/work", ["/work/a.txt"]), [])

    def test_pi_detection_mutations(self):
        def detect(tree, cpu):
            def _open(path, *args, **kwargs):
                if path == "/proc/device-tree/model":
                    if tree is None:
                        raise OSError(path)
                    return StringIO(tree)
                if path == "/proc/cpuinfo":
                    if cpu is None:
                        raise OSError(path)
                    return StringIO(cpu)
                raise OSError(path)

            with mock.patch("builtins.open", side_effect=_open):
                return detect_default_profile()

        self.assertEqual(detect("Raspberry Pi 5\x00", None), "raspberry-pi-home")
        self.assertEqual(detect("not a pi", "Hardware\t: Raspberry Pi"),
                         "raspberry-pi-home")
        self.assertEqual(detect(None, "model name\t: intel"), "password-only")
        self.assertEqual(detect(None, None), "password-only")
        self.assertEqual(detect("RASPBERRY PI", None), "raspberry-pi-home")


class ProcAndClamFuzzTest(unittest.TestCase):
    def test_random_proc_text_and_configs_do_not_raise(self):
        rng = random.Random(20261017)
        crashes = []
        for _ in range(200):
            n = rng.randrange(0, 40)
            text = "".join(chr(rng.randrange(9, 127)) for _ in range(n))
            if rng.randrange(3) == 0:
                text = "cpu " + " ".join(str(rng.randrange(-1, 5))
                                         for _ in range(rng.randrange(0, 8)))
            cfg = rng.choice([
                {},
                {"resources": rng.choice([
                    None, [], "x", True,
                    {"enabled": rng.choice([True, False, 1, "yes"])},
                    {"threshold": rng.choice([0, 1, 0.5, "n", 2])},
                    {"cooldown_sec": rng.choice([0, -1, "n"])},
                ])},
                [],
            ])
            try:
                with mock.patch("builtins.open",
                                side_effect=_open_as({"/proc/stat": text,
                                                      "/proc/meminfo": text})):
                    stat = RS._read_proc_stat()
                    mem = RS._mem_fraction()
                if stat is not None and (
                        not isinstance(stat, tuple) or len(stat) != 2):
                    crashes.append(("stat", stat))
                    break
                if mem is not None and not (0.0 <= mem <= 1.0):
                    crashes.append(("mem", mem))
                    break
                try:
                    parsed = RS.parse_resources(cfg)
                except RuntimeError:
                    parsed = None
                if parsed is not None and not (
                        isinstance(parsed["enabled"], bool)
                        and 0 < parsed["threshold"] <= 1):
                    crashes.append(("cfg", parsed))
                    break
            except Exception as exc:
                crashes.append((type(exc).__name__, text[:40]))
                break
        self.assertEqual(crashes, [])


class ArtifactScanTest(unittest.TestCase):
    def test_scan_flag_mutations(self):
        skip = (False, 0, "false", "NO", "off", "0")
        keep = (True, 1, "yes", "on", "", None)
        for value in skip:
            self.assertFalse(_artifact_scan_enabled(
                {"inference": {"artifact_scan": value}}), value)
        for value in keep:
            self.assertTrue(_artifact_scan_enabled(
                {"inference": {"artifact_scan": value}}), value)
        self.assertTrue(_artifact_scan_enabled({}))
        self.assertTrue(_artifact_scan_enabled(None))
        self.assertTrue(_artifact_scan_enabled({"inference": []}))

    def test_only_a_new_small_file_is_offered_to_clam(self):
        after = {
            "/w/old": (3, 1),
            "/w/big": (1048577, 1),
            "/w/new": (4, 2),
            "/w/neg": (-1, 1),
            "/w/bad": ("4", 1),
        }
        offered = {}

        def yara(work, targets, cfg=None):
            offered["yara"] = list(targets)
            return ["yara hp_webshell new [T1505.003]"]

        def clam(work, targets):
            offered["clam"] = list(targets)
            return ["clamav Eicar new [T1204.002]"]

        with mock.patch("runner.runner._work_files", return_value=after), \
             mock.patch("runner.runner._yara_hits", side_effect=yara), \
             mock.patch("runner.runner._clam_hits", side_effect=clam), \
             mock.patch("runner.runner.subprocess.run",
                        side_effect=AssertionError("scan")):
            hits = _artifact_findings("/w", {"/w/old": (3, 1)}, {})
        self.assertEqual(offered["yara"], ["/w/new"])
        self.assertEqual(offered["clam"], ["/w/new"])
        self.assertEqual(hits, [
            "yara hp_webshell new [T1505.003]",
            "clamav Eicar new [T1204.002]",
        ])

        with mock.patch("runner.runner._work_files") as files, \
             mock.patch("runner.runner.subprocess.run",
                        side_effect=AssertionError("scan")):
            self.assertEqual(_artifact_findings(
                "/w", {}, {"inference": {"artifact_scan": "off"}}), [])
        files.assert_not_called()

    def test_a_yara_crash_does_not_reach_clam_and_the_forty_first_file_is_dropped(self):
        after = {"/w/f%02d" % i: (1, i) for i in range(50)}
        offered = {}

        def clam(work, targets):
            offered["n"] = len(targets)
            return []

        with mock.patch("runner.runner._work_files", return_value=after), \
             mock.patch("runner.runner._yara_hits", return_value=[]), \
             mock.patch("runner.runner._clam_hits", side_effect=clam):
            self.assertEqual(_artifact_findings("/w", {}, {}), [])
        self.assertEqual(offered["n"], 40)

        with mock.patch("runner.runner._work_files", return_value={"/w/a": (1, 1)}), \
             mock.patch("runner.runner._yara_hits", side_effect=RuntimeError("yr")), \
             mock.patch("runner.runner._clam_hits",
                        side_effect=AssertionError("clam")):
            self.assertEqual(_artifact_findings("/w", {}, {}), [])

        with mock.patch("runner.runner._work_files", return_value={"/w/a": (1, 1)}), \
             mock.patch("runner.runner._yara_hits",
                        return_value=["yara hp_webshell a [T1505.003]"]), \
             mock.patch("runner.runner._clam_hits", side_effect=OSError("down")):
            hits = _artifact_findings("/w", {}, {})
        self.assertEqual(hits, ["yara hp_webshell a [T1505.003]"])

    def test_yara_labels_a_hit_and_drops_tool_noise(self):
        proc = mock.Mock(
            returncode=0,
            stdout="hp_webshell /w/a.php\nerror boom\nwarning x\ncustom /w/a.php\n")

        def which(name):
            return "/usr/bin/yr" if name == "yr" else None

        with mock.patch("runner.runner.shutil.which", side_effect=which), \
             mock.patch("runner.runner.subprocess.run", return_value=proc) as run:
            hits = _yara_hits("/w", ["/w/a.php"], {})
        argv = run.call_args.args[0]
        self.assertEqual(argv[:2], ["/usr/bin/yr", "scan"])
        self.assertEqual(hits, [
            "yara hp_webshell a.php [T1505.003]",
            "yara custom a.php [T1204.002]",
        ])

        def which_yara(name):
            return "/usr/bin/yara" if name == "yara" else None

        with mock.patch("runner.runner.shutil.which", side_effect=which_yara), \
             mock.patch("runner.runner.subprocess.run", return_value=proc) as run:
            _yara_hits("/w", ["/w/a.php"], {})
        self.assertEqual(run.call_args.args[0][:2], ["/usr/bin/yara", run.call_args.args[0][1]])
        self.assertNotIn("scan", run.call_args.args[0])

        with mock.patch("runner.runner.shutil.which", return_value=None), \
             mock.patch("runner.runner.subprocess.run") as run:
            self.assertEqual(_yara_hits("/w", ["/w/a.php"], {}), [])
        run.assert_not_called()


class ArtifactScanFuzzTest(unittest.TestCase):
    def test_random_workdirs_return_a_short_list_and_never_scan(self):
        rng = random.Random(20261017)
        crashes = []

        def yara(work, targets, cfg=None):
            if rng.randrange(5) == 0:
                raise RuntimeError("yr")
            return ["yara hp_webshell x [T1505.003]"] * rng.randrange(0, 3)

        def clam(work, targets):
            if rng.randrange(5) == 0:
                raise OSError("down")
            return ["clamav Eicar x [T1204.002]"] * rng.randrange(0, 3)

        with mock.patch("runner.runner._yara_hits", side_effect=yara), \
             mock.patch("runner.runner._clam_hits", side_effect=clam), \
             mock.patch("runner.runner.subprocess.run",
                        side_effect=AssertionError("scan")):
            for _ in range(200):
                after = {}
                for i in range(rng.randrange(0, 6)):
                    size = rng.choice([0, 1, -1, 1048576, 1048577, "1", None])
                    after["/w/%d" % i] = (size, rng.randrange(0, 4))
                before = {}
                if after and rng.randrange(2) == 0:
                    key = next(iter(after))
                    before[key] = after[key]
                cfg = rng.choice([
                    {},
                    None,
                    {"inference": []},
                    {"inference": {"artifact_scan": rng.choice(
                        [True, False, 0, "off", "yes", "0"])}},
                ])
                try:
                    with mock.patch("runner.runner._work_files",
                                    return_value=after):
                        hits = _artifact_findings("/w", before, cfg)
                except Exception as exc:
                    crashes.append((type(exc).__name__, repr(cfg)[:40]))
                    break
                if not isinstance(hits, list) or len(hits) > 20:
                    crashes.append(("shape", hits[:3] if isinstance(hits, list) else hits))
                    break
                if any(not isinstance(item, str) for item in hits):
                    crashes.append(("item", hits[:2]))
                    break
        self.assertEqual(crashes, [])


class YaraRulesTest(unittest.TestCase):
    def test_empty_whitespace_and_a_bad_path_fall_back(self):
        with tempfile.TemporaryDirectory() as d:
            empty = os.path.join(d, "empty.yar")
            blank = os.path.join(d, "blank.yar")
            open(empty, "w", encoding="utf-8").close()
            with open(blank, "w", encoding="utf-8") as fh:
                fh.write("  \n\t")
            for path in (empty, blank, os.path.join(d, "missing.yar"), d):
                text = _yara_rules_text({"inference": {"yara_rules": path}})
                self.assertIn("hp_webshell", text)
                self.assertIn("hp_encoded_exec", text)
        for cfg in (None, {}, {"inference": []},
                    {"inference": {"yara_rules": 1}},
                    {"inference": {"yara_rules": "  "}}):
            self.assertIn("hp_webshell", _yara_rules_text(cfg))

    def test_a_long_file_is_cut_at_64k_and_a_real_file_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.yar")
            body = "rule hp_custom { condition: true }\n" + ("x" * 70000)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
            text = _yara_rules_text({"inference": {"yara_rules": path}})
        self.assertTrue(text.startswith("rule hp_custom"))
        self.assertEqual(len(text), 65536)
        self.assertNotIn("hp_webshell", text)


class PosixModeTest(unittest.TestCase):
    def _one(self, mode):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            os.chmod(path, mode)
            results = []
            _check_file_perms(path, results)
        return results[0]

    def test_only_0600_is_ok(self):
        level, _section, detail = self._one(0o600)
        self.assertEqual(level, "OK")
        self.assertIn("0600", detail)
        for mode in (0o640, 0o644, 0o700, 0o000):
            level, _section, detail = self._one(mode)
            self.assertEqual(level, "WARN", oct(mode))
            self.assertIn("%04o" % mode, detail)
            self.assertIn("expected 0600", detail)

    def test_a_missing_file_fails_and_the_type_bits_are_ignored(self):
        results = []
        _check_file_perms("/no/such/hp-config.json", results)
        self.assertEqual(results[0][0], "FAIL")
        self.assertIn("cannot stat", results[0][2])

        class _Stat:
            st_mode = 0o100600

        results = []
        with mock.patch("runner.posture.os.stat", return_value=_Stat()):
            _check_file_perms("/tmp/hp-config.json", results)
        self.assertEqual(results[0][0], "OK")

    def test_feature_mode_case(self):
        results = []
        _check_recommended_features(
            {"security": {"modes": {
                "audience": "OFF",
                "policy_env": "Audit",
                "policy_files": 1,
                "policy_args": "enforce",
            }}},
            results)
        text = " ".join(row[2] for row in results)
        self.assertIn("audience is off", text)
        self.assertIn("policy_files is off", text)
        self.assertNotIn("policy_env is off", text)
        self.assertNotIn("policy_args is off", text)


class RulesAndModeFuzzTest(unittest.TestCase):
    def test_random_rules_and_modes_do_not_raise(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            for i in range(200):
                path = os.path.join(d, "r.yar")
                blob = bytes(rng.randrange(0, 256) for _ in range(rng.randrange(0, 80)))
                with open(path, "wb") as fh:
                    fh.write(blob)
                cfg = rng.choice([
                    None,
                    {},
                    {"inference": {"yara_rules": path}},
                    {"inference": {"yara_rules": rng.choice([None, 1, "", path])}},
                    [],
                ])
                mode = rng.randrange(0, 0o1000)
                try:
                    text = _yara_rules_text(cfg)
                    results = []

                    class _Stat:
                        st_mode = 0o100000 | mode

                    with mock.patch("runner.posture.os.stat", return_value=_Stat()):
                        _check_file_perms(path, results)
                except Exception as exc:
                    crashes.append((type(exc).__name__, i))
                    break
                if not isinstance(text, str) or not text.strip():
                    crashes.append(("rules", repr(text)[:40]))
                    break
                level = results[0][0]
                if level == "OK" and mode != 0o600:
                    crashes.append(("mode-ok", oct(mode)))
                    break
                if level == "WARN" and mode == 0o600:
                    crashes.append(("mode-warn", oct(mode)))
                    break
                if level not in ("OK", "WARN"):
                    crashes.append(("level", level))
                    break
        self.assertEqual(crashes, [])


def _linux_context(base, host, fw, av, **kwargs):
    with mock.patch("runner.runner.sys.platform", "linux"), \
         mock.patch("runner.runner._canary_watch", return_value=""), \
         mock.patch("runner.runner._host_log_tail", return_value=host), \
         mock.patch("runner.runner._firewall_watch", return_value=fw), \
         mock.patch("runner.runner._av_watch", return_value=av), \
         mock.patch("runner.runner.subprocess.run",
                    side_effect=AssertionError("host")):
        return oracle_context(base, **kwargs)


class OracleLinuxContextTest(unittest.TestCase):
    def test_linux_shows_host_firewall_and_av_and_not_windows(self):
        with tempfile.TemporaryDirectory() as d:
            blob = _linux_context(
                d, None, None, None)
        self.assertIn("Host log tail: unreadable", blob)
        self.assertIn("do not claim the log is clean", blob)
        self.assertIn("Firewall posture: unreadable", blob)
        self.assertIn("do not claim the firewall is on", blob)
        self.assertIn("AV posture: unreadable", blob)
        self.assertNotIn("Windows Event Log", blob)
        self.assertNotIn("registry watch", blob)

        with tempfile.TemporaryDirectory() as d:
            blob = _linux_context(
                d, "", "firewall: linux ufw=active",
                "av: clamav signatures current")
        self.assertIn("no matching auth failures", blob)
        self.assertIn("ufw=active", blob)
        self.assertIn("signatures current", blob)
        self.assertNotIn("unreadable", blob)

        with tempfile.TemporaryDirectory() as d:
            blob = _linux_context(
                d, "failed password for root [T1110]",
                "firewall: linux ufw=inactive [T1562.004]",
                "av: clamav signatures stale (8d) [T1562.001]")
        self.assertIn("[T1110]", blob)
        self.assertIn("[T1562.004]", blob)
        self.assertIn("[T1562.001]", blob)

    def test_caps_and_the_watch_switch(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_linux_context(d, "x", "y", "z", max_chars=0), "")
            short = _linux_context(d, "x", "y", "z", max_chars=5)
            self.assertNotIn("Firewall", short)
            self.assertLessEqual(len(short), 5)
            quiet = _linux_context(d, "failed password", "ufw", "clam",
                                   watch=False)
        self.assertNotIn("Host log tail", quiet)
        self.assertNotIn("Firewall", quiet)
        self.assertNotIn("Windows", quiet)
        self.assertEqual(oracle_context(5), "")

    def test_limit_mutations_keep_only_safe_job_ids(self):
        with tempfile.TemporaryDirectory() as d:
            retained = os.path.join(d, "retained")
            os.makedirs(retained)
            for name, body in (
                ("job-new.json", {"kind": "ping", "exit_code": 0}),
                ("job-old.json", {"kind": "ping", "exit_code": 1}),
                ("../evil.json", {"kind": "exec"}),
                ("not a job.json", {"kind": "ping"}),
            ):
                path = os.path.join(retained, name)
                if name.startswith(".."):
                    continue
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(body, fh)
            os.utime(os.path.join(retained, "job-old.json"), (1, 1))
            os.utime(os.path.join(retained, "job-new.json"), (2, 2))
            one = _linux_context(d, "", "", "", limit=1, watch=False)
            none = _linux_context(d, "", "", "", limit=-1, watch=False)
            bad = _linux_context(d, "", "", "", limit="nope", watch=False)
            flag = _linux_context(d, "", "", "", limit=True, watch=False)
        self.assertIn("job-new", one)
        self.assertNotIn("job-old", one)
        self.assertNotIn("job-new", none)
        self.assertIn("job-new", bad)
        self.assertIn("job-old", bad)
        self.assertIn("job-new", flag)
        self.assertNotIn("evil", one)


class OracleContextFuzzTest(unittest.TestCase):
    def test_random_watch_lines_stay_text_and_stay_off_windows(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d, \
             mock.patch("runner.runner.subprocess.run",
                        side_effect=AssertionError("host")):
            for _ in range(200):
                def pick():
                    roll = rng.randrange(4)
                    if roll == 0:
                        return None
                    if roll == 1:
                        return ""
                    n = rng.randrange(0, 30)
                    return "".join(chr(rng.randrange(32, 127)) for _ in range(n))

                try:
                    blob = _linux_context(d, pick(), pick(), pick(),
                                          max_chars=rng.choice([0, 5, 80, 8000]))
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(blob, str):
                    crashes.append(type(blob).__name__)
                    break
                if "Windows Event Log" in blob or "registry watch" in blob:
                    crashes.append("windows")
                    break
                if len(blob) > 8000:
                    crashes.append(len(blob))
                    break
        self.assertEqual(crashes, [])


class LinuxEnvMatchTest(unittest.TestCase):
    def test_posix_is_exact_and_windows_folds_case(self):
        with mock.patch("runner.runner.os.name", "posix"):
            self.assertTrue(_env_name_in("PATH", ["PATH"]))
            self.assertFalse(_env_name_in("path", ["PATH"]))
            self.assertFalse(_env_name_in("PATH", []))
            self.assertFalse(_env_name_in("PATH", None))
            self.assertFalse(_env_name_in("PATH", 1))
        with mock.patch("runner.runner.os.name", "nt"):
            self.assertTrue(_env_name_in("path", ["PATH"]))
            self.assertFalse(_env_name_in("HOME", ["PATH"]))
            self.assertFalse(_env_name_in("PATH", 1))

    def test_linux_policy_mutations(self):
        with mock.patch("runner.runner.os.name", "posix"):
            denied = check_policy_constraints(
                {"denied_env": ["PATH"]}, "k", {},
                {"kind": "exec", "env": {"path": "x", "PATH": "y"}})
            self.assertEqual(
                [row[2] for row in denied if row[1] == "denied_env"],
                ["env 'PATH' is denied for this key"])

            gate = check_policy_constraints(
                {"allowed_env": ["LD_PRELOAD"], "allow_dangerous_env": "true"},
                "k", {},
                {"kind": "exec", "env": {"LD_PRELOAD": "x"}})
            self.assertTrue(any(row[1] == "dangerous_env" for row in gate))

            opened = check_policy_constraints(
                {"allowed_env": ["LD_PRELOAD"], "allow_dangerous_env": True},
                "k", {},
                {"kind": "exec", "env": {"LD_PRELOAD": "x", "OTHER": "z"}})
            reasons = [row[1] for row in opened]
            self.assertNotIn("dangerous_env", reasons)
            self.assertIn("env_not_allowed", reasons)

            many = check_policy_constraints(
                {"max_args": True, "args_pattern": 1,
                 "allowed_files": "ab"},
                "k", {},
                {"kind": "exec", "args": ["a" * 1025, "nope"],
                 "files": [{"name": "a", "url": "http://x"}]})
            self.assertEqual(many, [])

            pinned = check_policy_constraints(
                {"allowed_script_sha384": ["ab"], "allow_file_urls": False},
                "k", {},
                {"kind": "exec", "env": {"FOO": "1"},
                 "files": [{"name": "a", "url": "http://x"}]})
            self.assertIn("pinned_script_with_env", [row[1] for row in pinned])
            self.assertIn("file_url_not_allowed", [row[1] for row in pinned])

            self.assertEqual(check_policy_constraints([], "k", {}, {}), [])
            self.assertEqual(check_policy_constraints({}, "k", {}, None), [])


class PolicyFuzzTest(unittest.TestCase):
    def test_random_policies_return_findings_and_do_not_raise(self):
        rng = random.Random(20261017)

        def atom(depth):
            if depth > 2 or rng.randrange(3) == 0:
                return rng.choice([
                    None, True, False, 0, 1, "", "PATH", "path",
                    "LD_PRELOAD", "a", "^a+$", "(", "http://x",
                ])
            if rng.randrange(2) == 0:
                return [atom(depth + 1) for _ in range(rng.randrange(0, 3))]
            key = rng.choice([
                "denied_env", "allowed_env", "allow_dangerous_env",
                "allowed_files", "allow_file_urls", "max_args",
                "args_pattern", "allowed_script_sha384", "kind",
                "env", "files", "args", "name", "url",
            ])
            return {key: atom(depth + 1)}

        crashes = []
        with mock.patch("runner.runner.os.name", "posix"):
            for _ in range(200):
                pol = atom(0)
                job = atom(0)
                try:
                    got = check_policy_constraints(pol, "k", {}, job)
                except Exception as exc:
                    crashes.append((type(exc).__name__, repr(pol)[:60]))
                    break
                if not isinstance(got, list):
                    crashes.append(("shape", type(got).__name__))
                    break
                for row in got:
                    if (not isinstance(row, tuple) or len(row) != 3
                            or not all(isinstance(x, str) for x in row)):
                        crashes.append(("row", row))
                        break
                if crashes:
                    break
        self.assertEqual(crashes, [])


class SandboxNameTest(unittest.TestCase):
    def test_script_name_mutations_never_resolve_a_binary(self):
        bad = ("", ".", "..", "../etc/passwd", "/bin/sh",
               "a/b", "a\\b", "a\x00b", None, 1)
        for name in bad:
            with mock.patch("runner.sandbox.shutil.which",
                            side_effect=AssertionError("which")):
                with self.assertRaises(RuntimeError):
                    SB.build_bwrap_command(
                        {}, ["sh"], name, "/work", [], {})
        with mock.patch("runner.sandbox.shutil.which", return_value="/bin/sh"):
            argv = SB.build_bwrap_command(
                {}, ["sh", "-c"], "job.sh", "/work", ["--x"], {"OK": "1"})
        self.assertEqual(argv[-2:], ["/work/job.sh", "--x"])
        self.assertNotIn("..", argv[-1])

    def test_workdir_args_and_env_mutations(self):
        with mock.patch("runner.sandbox.shutil.which",
                        side_effect=AssertionError("which")):
            for workdir, args, env in (
                ("", [], {}),
                ("/work\x00", [], {}),
                (None, [], {}),
                ("/work", ["ok", 1], {}),
                ("/work", None, {}),
                ("/work", [], None),
                ("/work", [], []),
            ):
                with self.assertRaises(RuntimeError):
                    SB.build_bwrap_command(
                        {}, ["sh"], "job.sh", workdir, args, env)


class JobUserNameTest(unittest.TestCase):
    def test_only_a_real_username_passes(self):
        def lookup(name):
            if name == "pigeon":
                return mock.Mock()
            raise KeyError(name)

        with mock.patch("pwd.getpwnam", side_effect=lookup):
            SEC.validate_security_config(
                {"security": {"job_user": {"user": "pigeon"}}})
            for bad in ("no-such", "a/b", "a\\b", "a\x00b", "a:b",
                        "a b", " a", "a\n", "root/../pigeon"):
                with self.assertRaises(RuntimeError) as caught:
                    SEC.validate_security_config(
                        {"security": {"job_user": {"user": bad}}})
                self.assertIn("job_user", str(caught.exception))
            for bad in ("", 1, None):
                shape = {"user": ""} if bad == "" else bad
                with self.assertRaises(RuntimeError):
                    SEC.validate_security_config(
                        {"security": {"job_user": shape}})


class SandboxAndUserFuzzTest(unittest.TestCase):
    def test_random_names_raise_or_return_a_string_argv(self):
        rng = random.Random(20261017)
        crashes = []

        def lookup(name):
            if name == "pigeon":
                return mock.Mock()
            raise KeyError(name)

        with mock.patch("runner.sandbox.shutil.which", return_value="/bin/sh"), \
             mock.patch("pwd.getpwnam", side_effect=lookup):
            for _ in range(200):
                name = "".join(chr(rng.randrange(0, 128))
                               for _ in range(rng.randrange(0, 12)))
                if rng.randrange(8) == 0:
                    name = rng.choice(["job.sh", "pigeon", "..", "", "a/b"])
                try:
                    argv = SB.build_bwrap_command(
                        {}, ["sh"], name, "/work", [], {})
                except RuntimeError:
                    argv = None
                except Exception as exc:
                    crashes.append(("argv", type(exc).__name__))
                    break
                if argv is not None:
                    if not all(isinstance(x, str) for x in argv):
                        crashes.append(("type", argv[:3]))
                        break
                    if "/" in name or name in ("", ".", ".."):
                        crashes.append(("accepted", name))
                        break
                try:
                    SEC.validate_security_config(
                        {"security": {"job_user": {"user": name or "x"}}})
                except RuntimeError:
                    pass
                except Exception as exc:
                    crashes.append(("user", type(exc).__name__))
                    break
        self.assertEqual(crashes, [])


class AuditAndDiskTest(unittest.TestCase):
    def test_an_audit_line_is_owner_only_and_a_hostile_detail_stays_inside(self):
        class Boom:
            def __str__(self):
                raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(SEC.sec_decide(
                {"security": {"modes": {"audience": "audit"}}},
                d, "audience", "runner_id_mismatch",
                {"detail": Boom(), "key_id": "k"}))
            path = os.path.join(d, SEC.AUDIT_FILE)
            mode = stat.S_IMODE(os.stat(path).st_mode)
            self.assertEqual(mode, 0o600)
            with open(path, encoding="utf-8") as fh:
                row = json.loads(fh.readline())
            self.assertEqual(row.get("key_id", ""), "")
            self.assertNotIn("detail", row)
            self.assertNotIn("boom", json.dumps(row))

    def test_disk_fraction_mutations(self):
        def usage(total, used):
            return mock.Mock(total=total, used=used)

        with mock.patch("runner.resources.shutil.disk_usage",
                        return_value=usage(0, 0)):
            self.assertIsNone(RS._disk_fraction("/tmp"))
        with mock.patch("runner.resources.shutil.disk_usage",
                        return_value=usage(100, 150)):
            self.assertEqual(RS._disk_fraction("/tmp"), 1.0)
        with mock.patch("runner.resources.shutil.disk_usage",
                        return_value=usage(100, 0)):
            self.assertEqual(RS._disk_fraction("/tmp"), 0.0)
        with mock.patch("runner.resources.shutil.disk_usage",
                        return_value=usage("n", 1)):
            self.assertIsNone(RS._disk_fraction("/tmp"))
        with mock.patch("runner.resources.shutil.disk_usage",
                        side_effect=OSError("nope")):
            self.assertIsNone(RS._disk_fraction("/tmp"))
        self.assertIsNone(RS._disk_fraction(1))
        self.assertIsNone(RS._disk_fraction(None))

    def test_cpu_cooldown_does_not_hide_memory(self):
        cfg = {"resources": {"threshold": 0.5, "cooldown_sec": 100}}
        plan = [
            ((0, 100), 0.1, 0.1),
            ((0, 200), 0.1, 0.1),
            ((0, 300), 0.9, 0.1),
        ]
        cursor = {"i": 0}

        def proc():
            return plan[cursor["i"]][0]

        def mem():
            return plan[cursor["i"]][1]

        def disk(_path):
            return plan[cursor["i"]][2]

        seen = []
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(RS, "_read_proc_stat", side_effect=proc), \
                 mock.patch.object(RS, "_mem_fraction", side_effect=mem), \
                 mock.patch.object(RS, "_disk_fraction", side_effect=disk):
                for i in range(3):
                    cursor["i"] = i
                    seen.append(RS.check_resources(cfg, d, now=1000 + i))
        self.assertIsNone(seen[0])
        self.assertEqual(set(seen[1]["resources"]), {"cpu"})
        self.assertEqual(set(seen[2]["resources"]), {"mem"})


class AuditFuzzTest(unittest.TestCase):
    def test_random_entries_never_raise_and_stay_owner_only(self):
        rng = random.Random(20261017)
        crashes = []

        class Boom:
            def __str__(self):
                raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as d:
            for _ in range(200):
                detail = rng.choice(["", "ok", Boom(), None])
                cfg = rng.choice([
                    None,
                    {},
                    {"security": {"audit_max_lines": rng.choice([1, 2, True, "n"])}},
                ])
                try:
                    SEC.write_audit_entry(
                        d, rng.choice(["audience", "confinement", ""]),
                        rng.choice(["denied", "would_deny", ""]),
                        "reason", detail=detail, cfg=cfg)
                    got = RS._disk_fraction(rng.choice(["/tmp", 1, None, ""]))
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                path = os.path.join(d, SEC.AUDIT_FILE)
                if os.path.exists(path):
                    mode = stat.S_IMODE(os.stat(path).st_mode)
                    if mode != 0o600:
                        crashes.append(oct(mode))
                        break
                if got is not None and not (0.0 <= got <= 1.0):
                    crashes.append(got)
                    break
        self.assertEqual(crashes, [])


class AuthLineTest(unittest.TestCase):
    def test_each_mark_is_tagged_once_and_case_does_not_matter(self):
        cases = (
            ("Failed password for root", "T1110"),
            ("AUTHENTICATION FAILURE", "T1110"),
            ("Invalid user bob", "T1110"),
            ("sudo: bob : COMMAND=/bin/id", "T1548.003"),
            ("useradd bob", "T1136"),
            ("USERMOD bob", "T1136"),
            ("groupadd wheel", "T1136"),
        )
        for line, attack in cases:
            tagged = _label_auth(line)
            tag = "[" + attack + "]"
            self.assertTrue(tagged.endswith(tag), tagged)
            self.assertEqual(tagged.count(tag), 1)
            self.assertEqual(_label_auth(tagged), tagged)
        self.assertEqual(_label_auth("kernel: error: disk full"),
                         "kernel: error: disk full")
        self.assertEqual(_label_auth(None), None)
        self.assertEqual(_label_auth(1), 1)
        both = _label_auth("failed password sudo: bob")
        self.assertIn("[T1110]", both)
        self.assertNotIn("[T1548.003]", both)

    def test_a_zero_cap_keeps_nothing_and_a_long_line_is_cut(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "auth.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("ok\n" + ("failed password " + ("x" * 400)) + "\n")
            self.assertEqual(_tail_marked(path, ("failed password",), 0), [])
            self.assertEqual(_tail_marked(path, ("failed password",), True), [])
            self.assertEqual(_tail_marked(path, ("failed password",), -1), [])
            self.assertEqual(_tail_marked(path, "failed", 5), [])
            kept = _tail_marked(path, ("failed password",), 5)
        self.assertEqual(len(kept), 1)
        self.assertLessEqual(len(kept[0]), 240)
        self.assertTrue(kept[0].lower().startswith("failed password"))
        self.assertIsNone(_tail_marked("/no/such/auth.log", ("error",)))


class AuthLineFuzzTest(unittest.TestCase):
    def test_random_lines_and_log_bytes_do_not_raise(self):
        rng = random.Random(20261017)
        marks = (
            "failed password", "authentication failure", "invalid user",
            "sudo:", "useradd", "usermod", "groupadd",
        )
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "syslog")
            for _ in range(200):
                line = "".join(chr(rng.randrange(32, 127))
                               for _ in range(rng.randrange(0, 80)))
                if rng.randrange(3) == 0:
                    line = rng.choice(marks).upper() + " " + line
                blob = bytes(rng.randrange(0, 256) for _ in range(rng.randrange(0, 300)))
                cap = rng.choice([0, 1, 3, 20, -1, True, None])
                try:
                    tagged = _label_auth(line)
                    with open(path, "wb") as fh:
                        fh.write(blob)
                    kept = _tail_marked(path, marks, cap)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(tagged, str):
                    crashes.append(("tag", type(tagged).__name__))
                    break
                if not isinstance(kept, list):
                    crashes.append(("kept", type(kept).__name__))
                    break
                if isinstance(cap, int) and not isinstance(cap, bool) and cap > 0:
                    if len(kept) > cap:
                        crashes.append(("cap", len(kept)))
                        break
                elif kept:
                    crashes.append(("empty", cap))
                    break
                if any(not isinstance(item, str) or len(item) > 240 for item in kept):
                    crashes.append(("item", kept[:1]))
                    break
        self.assertEqual(crashes, [])


def _alerts(base, sensor):
    from runner.runner import _senses
    return _senses.load_alerts(base, sensor=sensor)


class FreshLineTest(unittest.TestCase):
    def test_only_a_new_technique_line_is_filed_and_only_eight(self):
        with tempfile.TemporaryDirectory() as d:
            _file_fresh_lines(d, "hostlog",
                              "Failed password [T1110]\nkernel: disk full\nnote [nope]")
            self.assertEqual(_alerts(d, "hostlog"), [])
            lines = "\n".join("event %d [T1110]" % i for i in range(9))
            _file_fresh_lines(d, "hostlog", lines)
            self.assertEqual(len(_alerts(d, "hostlog")), 8)
            _file_fresh_lines(d, "hostlog", lines)
            self.assertEqual(len(_alerts(d, "hostlog")), 9)
            _file_fresh_lines(d, "hostlog", lines)
            filed = _alerts(d, "hostlog")
        self.assertEqual(len(filed), 9)
        self.assertTrue(all(row["detail"]["attack"] == "T1110" for row in filed))
        self.assertTrue(all(len(row["title"]) <= 200 for row in filed))

    def test_bracket_and_snapshot_mutations(self):
        with tempfile.TemporaryDirectory() as d:
            _file_fresh_lines(None, "hostlog", "x [T1110]")
            _file_fresh_lines(d, "hostlog", None)
            _file_fresh_lines(d, "hostlog", "plain [t1110]\nlast [T1110] tail [nope]")
            self.assertEqual(_alerts(d, "hostlog"), [])
            path = os.path.join(d, "oracle-logseen.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[]")
            _file_fresh_lines(d, "hostlog", "again [T1548.003]")
            self.assertEqual(_alerts(d, "hostlog"), [])
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"hostlog": "nope"}, fh)
            _file_fresh_lines(d, "hostlog", "sudo: bob [T1548.003]")
            self.assertEqual(_alerts(d, "hostlog"), [])
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"hostlog": ["not-this"]}, fh)
            _file_fresh_lines(d, "hostlog", "useradd bob [T1136]")
            filed = _alerts(d, "hostlog")
        self.assertEqual(len(filed), 1)
        self.assertEqual(filed[0]["detail"]["attack"], "T1136")

    def test_artifact_hits_keep_eight_and_the_job_id(self):
        with tempfile.TemporaryDirectory() as d:
            _file_artifact_hits(d, "job-1", None)
            _file_artifact_hits(d, "job-1", ["", "  ", 1, "yara hp_webshell a.php [T1505.003]"])
            self.assertEqual(len(_alerts(d, "artifact")), 1)
            _file_artifact_hits(d, "job-1", ["clamav Eicar a.txt [T1204.002]"] * 10)
            filed = _alerts(d, "artifact")
        self.assertEqual(len(filed), 9)
        attacks = [row["detail"]["attack"] for row in filed]
        self.assertEqual(attacks.count("T1505.003"), 1)
        self.assertEqual(attacks.count("T1204.002"), 8)
        self.assertTrue(all(row["title"].startswith("job-1: ") for row in filed))
        self.assertTrue(all(len(row["title"]) <= 200 for row in filed))
        self.assertTrue(all(row["severity"] == "high" for row in filed))


class FreshLineFuzzTest(unittest.TestCase):
    def test_random_text_never_raises_and_files_at_most_eight(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            for _ in range(200):
                n = rng.randrange(0, 12)
                lines = []
                for i in range(n):
                    attack = rng.choice(["T1110", "T1548.003", "nope", "t1110", ""])
                    lines.append("line %d [%s]" % (i, attack))
                text = rng.choice(["\n".join(lines), None, 1, ""])
                sensor = rng.choice(["hostlog", "auth", ""])
                try:
                    before = len(_alerts(d, sensor)) if sensor else 0
                    _file_fresh_lines(d, sensor, text)
                    _file_artifact_hits(
                        d, rng.choice(["job-1", "", None]),
                        rng.choice([lines, None, "x", []]))
                    after = len(_alerts(d, sensor)) if sensor else 0
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if sensor and after - before > 8:
                    crashes.append(after - before)
                    break
        self.assertEqual(crashes, [])


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class InstallModeTest(unittest.TestCase):
    def _src(self, d):
        for name in ("runner.py", "oauth.py", "winlog.py",
                     "homing-pigeon", "install", "install.exe",
                     "config.example.json"):
            with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                fh.write("{}\n" if name.endswith(".json") else "# stub\n")

    def test_a_seeded_config_is_owner_only_and_an_existing_one_is_left_alone(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            self._src(src)
            with mock.patch("runner.install.FROZEN", False):
                self.assertTrue(install_files(src, dst))
            cfg = os.path.join(dst, "config.json")
            self.assertEqual(_mode(cfg), 0o600)
            os.chmod(cfg, 0o644)
            with mock.patch("runner.install.FROZEN", False):
                self.assertTrue(install_files(src, dst))
            self.assertEqual(_mode(cfg), 0o644)

    def test_a_frozen_binary_is_executable_only_on_posix(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            self._src(src)
            with mock.patch("runner.install.FROZEN", True), \
                 mock.patch("runner.install.os.name", "posix"):
                self.assertTrue(install_files(src, dst))
            self.assertEqual(_mode(os.path.join(dst, "homing-pigeon")), 0o755)
            self.assertEqual(_mode(os.path.join(dst, "install")), 0o755)
            self.assertEqual(_mode(os.path.join(dst, "config.json")), 0o600)

        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            self._src(src)
            with mock.patch("runner.install.FROZEN", True), \
                 mock.patch("runner.install.os.name", "nt"), \
                 mock.patch("runner.install.os.chmod") as chmod:
                self.assertTrue(install_files(src, dst))
            self.assertNotIn(0o755, [call.args[-1] for call in chmod.call_args_list])

    def test_a_bad_key_id_does_not_write_and_the_secret_is_not_printed(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"additional_secrets": {}}\n')
            os.chmod(path, 0o600)
            for bad in ("", "a/b", "has space", "x" * 65, "ü", "../k"):
                with self.assertRaises(SystemExit) as caught:
                    store_additional_secret(path, bad)
                self.assertEqual(caught.exception.code, 2)
            buf = __import__("io").StringIO()
            with mock.patch("sys.stdout", buf):
                store_additional_secret(path, "ops.reader")
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)["additional_secrets"]["ops.reader"]
            self.assertNotIn(saved, buf.getvalue())
            self.assertEqual(_mode(path), 0o600)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"additional_secrets": []}\n')
            with self.assertRaises(SystemExit):
                store_additional_secret(path, "ops.reader")


class InstallModeFuzzTest(unittest.TestCase):
    def test_random_key_ids_exit_or_store_an_unprinted_secret(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            for _ in range(200):
                n = rng.randrange(0, 70)
                key = "".join(chr(rng.randrange(32, 127)) for _ in range(n))
                if rng.randrange(5) == 0:
                    key = rng.choice(["a", "A._-z", "", "a/b", "x" * 65])
                buf = __import__("io").StringIO()
                try:
                    with mock.patch("sys.stdout", buf):
                        store_additional_secret(path, key)
                except SystemExit as exc:
                    if exc.code != 2:
                        crashes.append(exc.code)
                        break
                    continue
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                with open(path, encoding="utf-8") as fh:
                    saved = json.load(fh)["additional_secrets"][key]
                if saved in buf.getvalue() or _mode(path) != 0o600:
                    crashes.append(key[:20])
                    break
        self.assertEqual(crashes, [])


_HARDENING = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hardening")
_POLICY_TOKENS = ("@PYTHON@", "@RUNNER_DIR@", "@BASE_DIR@", "@CONFIG@", "@USER@")


def _policy(name):
    with open(os.path.join(_HARDENING, name), encoding="utf-8") as fh:
        return fh.read()


def _safe_value(token, value):
    if not isinstance(value, str) or not value:
        return False
    if any(c in value for c in "\n\r\t @#{}'\""):
        return False
    if token == "@USER@":
        bare = value.replace(".", "").replace("_", "").replace("-", "")
        return bool(bare) and bare.isalnum() and "/" not in value
    return value.startswith("/")


def _render_policy(text, values):
    for token, value in values.items():
        if token not in _POLICY_TOKENS or not _safe_value(token, value):
            raise ValueError(token)
        text = text.replace(token, value)
    return text


def _active(text):
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("#", "!")))


def _policy_ok(name, text):
    active = _active(text)
    if name.startswith("apparmor/"):
        if active.count("flags=(complain)") != 1 or "flags=(enforce)" in active:
            return False
        if "deny /home/** w," not in active:
            return False
        if re_search_capability(text):
            return False
    if name.endswith(".service"):
        lines = active.splitlines()
        if "CapabilityBoundingSet=" not in lines or "AmbientCapabilities=" not in lines:
            return False
        if "NoNewPrivileges=true" not in lines or "ProtectHome=true" not in lines:
            return False
    if name.endswith(".te"):
        if re_caps(text) != {"sys_admin", "sys_chroot", "setuid", "setgid"}:
            return False
    return True


def re_search_capability(text):
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        if "capability" in line:
            return True
    return False


def re_caps(text):
    import re
    match = re.search(r"capability \{ ([^}]+) \}", text)
    if not match:
        return set()
    return set(match.group(1).split())


class LinuxPolicyTest(unittest.TestCase):
    NAMES = (
        "apparmor/homing-pigeon",
        "systemd/homing-pigeon.service",
        "selinux/homing_pigeon.te",
    )

    def test_shipped_policies_stay_in_complain_and_drop_capabilities(self):
        for name in self.NAMES:
            text = _policy(name)
            self.assertTrue(_policy_ok(name, text), name)
        unit = _policy("systemd/homing-pigeon.service")
        self.assertIn("CapabilityBoundingSet=\n", unit)
        self.assertIn("AmbientCapabilities=\n", unit)
        self.assertNotIn("CapabilityBoundingSet=CAP_", unit)

    def test_placeholder_mutations(self):
        clean = {
            "@PYTHON@": "/usr/bin/python3",
            "@RUNNER_DIR@": "/opt/homing-pigeon",
            "@BASE_DIR@": "/var/lib/homing-pigeon",
            "@CONFIG@": "/etc/homing-pigeon.json",
            "@USER@": "pigeon",
        }
        for name in self.NAMES:
            rendered = _render_policy(_policy(name), clean)
            self.assertTrue(_policy_ok(name, rendered), name)
            for token in _POLICY_TOKENS:
                self.assertNotIn(token, "\n".join(
                    line for line in rendered.splitlines()
                    if not line.lstrip().startswith(("#", "!"))))
        raw = _policy("apparmor/homing-pigeon")
        for bad in ("", "python3", "/usr/bin/python3\n/tmp/x rw,",
                    "/opt/{x}", "/opt/@X@", "/opt/a b", "p igeon"):
            with self.assertRaises(ValueError):
                _render_policy(raw, {"@PYTHON@": bad})


class LinuxPolicyFuzzTest(unittest.TestCase):
    def test_random_placeholders_either_refuse_or_keep_the_invariants(self):
        rng = random.Random(20261017)
        crashes = []
        raw = {name: _policy(name) for name in LinuxPolicyTest.NAMES}
        for _ in range(200):
            values = {}
            for token in _POLICY_TOKENS:
                if token == "@USER@":
                    values[token] = rng.choice(
                        ["pigeon", "a", "svc_user", "p igeon", "", "root/x"])
                    continue
                if rng.randrange(2) == 0:
                    values[token] = "/" + "".join(
                        rng.choice("abc._-") for _ in range(rng.randrange(1, 8)))
                else:
                    values[token] = "".join(
                        chr(rng.randrange(32, 127)) for _ in range(rng.randrange(0, 12)))
            try:
                rendered = {name: _render_policy(text, values) for name, text in raw.items()}
            except ValueError:
                continue
            except Exception as exc:
                crashes.append(type(exc).__name__)
                break
            for name, text in rendered.items():
                if not _policy_ok(name, text):
                    crashes.append(name)
                    break
            if crashes:
                break
        self.assertEqual(crashes, [])


class PosixKillTest(unittest.TestCase):
    def test_linux_kills_the_group_and_does_not_call_taskkill(self):
        proc = mock.Mock()
        proc.pid = 42
        with mock.patch("runner.runner.os.name", "posix"), \
             mock.patch("runner.runner.os.killpg") as killpg, \
             mock.patch("runner.runner.subprocess.run",
                        side_effect=AssertionError("taskkill")):
            kill_tree(proc)
        killpg.assert_called_once()
        self.assertEqual(killpg.call_args.args[0], 42)
        proc.kill.assert_not_called()

        proc.kill.side_effect = OSError("gone")
        with mock.patch("runner.runner.os.name", "posix"), \
             mock.patch("runner.runner.os.killpg", side_effect=OSError("no group")), \
             mock.patch("runner.runner.subprocess.run",
                        side_effect=AssertionError("taskkill")):
            kill_tree(proc)
        proc.kill.assert_called_once()

    def test_interpreter_and_script_name_mutations(self):
        with mock.patch("runner.runner.os.name", "posix"):
            self.assertEqual(platform_interpreter(), ["sh"])
        with mock.patch("runner.runner.os.name", "nt"):
            self.assertEqual(platform_interpreter()[-1], "-File")
        self.assertEqual(script_filename(["sh"]), "script")
        self.assertEqual(script_filename(["/bin/bash"]), "script")
        self.assertEqual(script_filename(["Python3"]), "script.py")
        self.assertEqual(script_filename(["powershell"]), "script.ps1")
        self.assertEqual(script_filename(None), "script")
        self.assertEqual(script_filename(["sh", None]), "script")

    def test_run_text_does_not_execute_and_drops_a_failure(self):
        def fake_run(argv, **kwargs):
            self.assertNotIn("creationflags", kwargs)
            self.assertEqual(argv, ["ufw", "status"])
            return mock.Mock(returncode=0, stdout="Status: active\n")

        with mock.patch("runner.runner.sys.platform", "linux"), \
             mock.patch("runner.runner.subprocess.run", side_effect=fake_run):
            self.assertEqual(_run_text(["ufw", "status"]), "Status: active\n")
        with mock.patch("runner.runner.subprocess.run",
                        return_value=mock.Mock(returncode=1, stdout="no")):
            self.assertIsNone(_run_text(["ufw", "status"]))
        with mock.patch("runner.runner.subprocess.run",
                        return_value=mock.Mock(returncode=0, stdout=None)):
            self.assertIsNone(_run_text(["ufw", "status"]))
        with mock.patch("runner.runner.subprocess.run",
                        side_effect=OSError("missing")):
            self.assertIsNone(_run_text(["no-such-binary"]))


class AlertStoreTest(unittest.TestCase):
    def test_the_cap_keeps_the_newest_and_a_bad_record_is_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.senses.MAX_STORED", 3):
                store_alert("", {"sensor": "x"})
                store_alert(d, ["not", "a", "dict"])
                store_alert(d, {"sensor": "bad", "n": float("nan")})
                for i in range(5):
                    store_alert(d, {"sensor": "host", "n": i, "severity": "high"})
                rows = load_alerts(d, sensor="host")
            self.assertEqual([row["n"] for row in rows], [2, 3, 4])
            path = os.path.join(d, "senses.jsonl")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("not-json\n")
            self.assertEqual(len(load_alerts(d, sensor="host")), 3)
            self.assertEqual(
                load_alerts(d, sensor="host", severity_floor="critical"), [])


class KillAndStoreFuzzTest(unittest.TestCase):
    def test_random_kills_reads_and_records_do_not_raise(self):
        rng = random.Random(20261017)
        crashes = []

        def killpg(pid, sig):
            if rng.randrange(3) == 0:
                raise OSError("no group")

        def fake_run(argv, **kwargs):
            return mock.Mock(
                returncode=rng.choice([0, 1, 2]),
                stdout=rng.choice(["ok", "", None, b"ok"]))

        with tempfile.TemporaryDirectory() as d, \
             mock.patch("runner.runner.os.name", "posix"), \
             mock.patch("runner.runner.os.killpg", side_effect=killpg), \
             mock.patch("runner.runner.subprocess.run", side_effect=fake_run), \
             mock.patch("runner.senses.MAX_STORED", 5):
            for _ in range(200):
                proc = mock.Mock()
                proc.pid = rng.choice([1, 42, None, "x"])
                proc.kill.side_effect = OSError("gone") if rng.randrange(4) == 0 else None
                record = rng.choice([
                    {"sensor": "host", "n": rng.randrange(0, 8), "severity": "low"},
                    {"sensor": "host", "n": float("nan")},
                    ["x"],
                    None,
                ])
                try:
                    kill_tree(proc)
                    got = _run_text(["ufw", "status"])
                    store_alert(d, record)
                    rows = load_alerts(d, sensor="host", limit=10)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if got not in (None, "ok", ""):
                    crashes.append(got)
                    break
                if not isinstance(rows, list) or len(rows) > 5:
                    crashes.append(len(rows) if isinstance(rows, list) else rows)
                    break
        self.assertEqual(crashes, [])


class LogAndCanaryTest(unittest.TestCase):
    def test_log_tail_caps_and_drops_the_partial_first_line(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_runner_log_tail(None), "")
            self.assertEqual(_runner_log_tail(d), "")
            path = os.path.join(d, "runner.log")
            with open(path, "wb") as fh:
                fh.write(b"DROPME-" + (b"a" * 5000) + b"\nKEEPME\n")
            self.assertIn("KEEPME", _runner_log_tail(d))
            self.assertNotIn("DROPME", _runner_log_tail(d))
            self.assertEqual(_runner_log_tail(d, 0), "")
            self.assertEqual(_runner_log_tail(d, -3), "")
            self.assertEqual(len(_runner_log_tail(d, 5)), 5)
            full = _runner_log_tail(d, True)
            self.assertIn("KEEPME", full)
            self.assertEqual(_runner_log_tail(d, "nope"), full)
            with open(path, "wb") as fh:
                fh.write(b"\xff\xfe KEEP\n")
            self.assertIn("KEEP", _runner_log_tail(d))

    def test_canary_hash_folds_crlf_and_stops_at_64k(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "passwords.txt")
            self.assertIsNone(_canary_state(path))
            with open(path, "wb") as fh:
                fh.write(b"line\r\n")
            folded = _canary_state(path)
            with open(path, "wb") as fh:
                fh.write(b"line\n")
            self.assertEqual(_canary_state(path), folded)
            with open(path, "wb") as fh:
                fh.write(b"line\r")
            self.assertNotEqual(_canary_state(path), folded)
            with open(path, "wb") as fh:
                fh.write(b"a" * 65536 + b"b")
            capped = _canary_state(path)
            with open(path, "wb") as fh:
                fh.write(b"a" * 65536 + b"c")
            self.assertEqual(_canary_state(path), capped)
            self.assertEqual(len(capped), 12)
            with mock.patch("builtins.open", side_effect=OSError("busy")):
                self.assertEqual(_canary_state(path), "?")


class LogAndCanaryFuzzTest(unittest.TestCase):
    def test_random_bytes_stay_inside_the_cap(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            log_path = os.path.join(d, "runner.log")
            canary = os.path.join(d, "canary.txt")
            for _ in range(200):
                blob = bytes(rng.randrange(0, 256) for _ in range(rng.randrange(0, 8000)))
                cap = rng.choice([0, 1, 8, 2000, -1, True, False, None, "nope"])
                try:
                    with open(log_path, "wb") as fh:
                        fh.write(blob)
                    with open(canary, "wb") as fh:
                        fh.write(blob[:100])
                    tail = _runner_log_tail(d, cap)
                    state = _canary_state(canary)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(tail, str):
                    crashes.append(type(tail).__name__)
                    break
                if isinstance(cap, int) and not isinstance(cap, bool) and 0 <= cap < 2000:
                    if len(tail) > cap:
                        crashes.append(len(tail))
                        break
                if state is not None and (
                        not isinstance(state, str) or len(state) not in (1, 12)
                        or (len(state) == 12 and any(c not in "0123456789abcdef" for c in state))):
                    crashes.append(state)
                    break
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
