"""Linux platform code: the bwrap argv, the systemd unit, the posture check.

Unit cases, one-field mutations, and a deterministic fuzz of the
confinement block. shutil.which and systemctl are mocked. Nothing
here execs bwrap, systemctl, or a job.
"""
import os
import random
import shlex
import tempfile
import unittest
from unittest import mock

from runner import sandbox as SB
from runner.install import do_wipe, install_linux, uninstall_linux
from runner.posture import _check_confinement_backend, _check_service_unit
from runner.runner import (
    _firewall_posture,
    _host_log_tail,
    _parse_iptables_policy,
    _parse_ufw,
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


if __name__ == "__main__":
    unittest.main()
