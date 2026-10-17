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
from runner.install import install_linux, uninstall_linux
from runner.posture import _check_confinement_backend, _check_service_unit


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


if __name__ == "__main__":
    unittest.main()
