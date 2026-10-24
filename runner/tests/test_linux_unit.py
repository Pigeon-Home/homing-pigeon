"""Linux systemd unit: mode 0644, quoted argv, no symlink follow.

Unit cases, one-field mutations, and a deterministic fuzz.
systemctl is mocked. Nothing here starts a service.
"""
import os
import random
import shlex
import tempfile
import unittest
from unittest import mock

from runner.install import install_linux


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _install(home, dst, cfg, extra=()):
    calls = []
    with mock.patch.object(os.path, "expanduser",
                           side_effect=lambda p: p.replace("~", home)), \
         mock.patch("runner.install.run",
                    side_effect=lambda cmd, **kw: calls.append(list(cmd))):
        install_linux(dst, cfg, False, extra)
    return calls


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class UnitFileTest(unittest.TestCase):
    def test_the_user_unit_is_owner_readable_and_quoted(self):
        with tempfile.TemporaryDirectory() as home:
            calls = _install(home, "/opt/homing pigeon", "/cfg/a b.json",
                             ("--workers", "2"))
            path = os.path.join(home, ".config/systemd/user/homing-pigeon.service")
            self.assertEqual(_mode(path), 0o644)
            self.assertFalse(os.path.islink(path))
            with open(path, encoding="utf-8") as fh:
                unit = fh.read()
        start = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
        self.assertIn(shlex.quote("/opt/homing pigeon/runner.py"), start)
        self.assertIn(shlex.quote("/cfg/a b.json"), start)
        self.assertIn("--workers", start)
        self.assertIn("WantedBy=default.target", unit)
        self.assertEqual(calls, [
            ["systemctl", "--user", "daemon-reload"],
            ["systemctl", "--user", "enable", "--now", "homing-pigeon.service"],
        ])
        self.assertTrue(all(isinstance(part, str) for call in calls for part in call))

    def test_a_symlink_is_not_followed_and_systemctl_is_not_called(self):
        with tempfile.TemporaryDirectory() as home:
            target = os.path.join(home, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            udir = os.path.join(home, ".config/systemd/user")
            os.makedirs(udir)
            link = os.path.join(udir, "homing-pigeon.service")
            os.symlink(target, link)
            calls = []
            with mock.patch.object(os.path, "expanduser",
                                   side_effect=lambda p: p.replace("~", home)), \
                 mock.patch("runner.install.run",
                            side_effect=lambda cmd, **kw: calls.append(list(cmd))):
                with self.assertRaises(OSError):
                    install_linux("/opt/hp", "/cfg/a.json", False, ())
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")
            self.assertTrue(os.path.islink(link))
            self.assertEqual(calls, [])


class UnitMutations(unittest.TestCase):
    def test_shell_metacharacters_stay_quoted(self):
        nasty = ["$(id)", "`id`", "a;rm", "a|b", "a&b", "a'b", 'a"b', ""]
        with tempfile.TemporaryDirectory() as home:
            _install(home, "/opt/hp", "/cfg/a.json", tuple(nasty))
            path = os.path.join(home, ".config/systemd/user/homing-pigeon.service")
            with open(path, encoding="utf-8") as fh:
                unit = fh.read()
            calls = []
            with mock.patch.object(os.path, "expanduser",
                                   side_effect=lambda p: p.replace("~", home)), \
                 mock.patch("runner.install.run",
                            side_effect=lambda cmd, **kw: calls.append(list(cmd))):
                with self.assertRaises(ValueError):
                    install_linux("/opt/hp", "/cfg/a.json", False, ("a\nb",))
                with self.assertRaises(ValueError):
                    install_linux("/opt/hp", "/cfg/a.json", False, ("a\x00b",))
            self.assertEqual(calls, [])
            start = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
            argv = shlex.split(start[len("ExecStart="):])
            self.assertEqual(argv[-len(nasty):], nasty)
            self.assertNotIn("\n", start)
            self.assertEqual(_mode(path), 0o644)


class UnitFuzzTest(unittest.TestCase):
    def test_random_args_stay_one_exec_line(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as home:
            target = os.path.join(home, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(80):
                extra = []
                for _ in range(rng.randrange(0, 4)):
                    extra.append("".join(rng.choice("abc;|$`'\" ")
                                         for _ in range(rng.randrange(0, 8))))
                if rng.randrange(8) == 0:
                    extra.append(rng.choice(["a\nb", "a\x00b", "a\rb"]))
                try:
                    if any("\n" in a or "\r" in a or "\x00" in a for a in extra):
                        with self.assertRaises(ValueError):
                            _install(home, "/opt/hp", "/cfg/a.json", tuple(extra))
                        continue
                    calls = _install(home, "/opt/hp %d" % (i % 3),
                                     "/cfg/a.json", tuple(extra))
                    path = os.path.join(
                        home, ".config/systemd/user/homing-pigeon.service")
                    with open(path, encoding="utf-8") as fh:
                        unit = fh.read()
                    start = next(line for line in unit.splitlines()
                                 if line.startswith("ExecStart="))
                    argv = shlex.split(start[len("ExecStart="):])
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if extra and argv[-len(extra):] != extra:
                    crashes.append(extra)
                    break
                if _mode(path) != 0o644 or os.path.islink(path):
                    crashes.append("mode")
                    break
                if calls[0] != ["systemctl", "--user", "daemon-reload"]:
                    crashes.append(calls[0])
                    break
                if "\n" in start:
                    crashes.append("newline")
                    break
            link = os.path.join(home, ".config/systemd/user/homing-pigeon.service")
            os.remove(link)
            os.symlink(target, link)
            calls = []
            try:
                with mock.patch.object(os.path, "expanduser",
                                       side_effect=lambda p: p.replace("~", home)), \
                     mock.patch("runner.install.run",
                                side_effect=lambda cmd, **kw: calls.append(list(cmd))):
                    install_linux("/opt/hp", "/cfg/a.json", False, ())
                crashes.append("no-raise")
            except OSError:
                pass
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
            if calls:
                crashes.append(calls)
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
