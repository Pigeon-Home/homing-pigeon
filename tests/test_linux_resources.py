"""Linux resource sampler: /proc parsing and the state file.

Unit cases, one-field mutations, and a deterministic fuzz.
/proc is fed from strings. Nothing here starts a process.
A planted symlink is not written through.
"""
import io
import json
import os
import random
import tempfile
import threading
import unittest
from unittest import mock

from runner import resources as RS


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _tmp_for(base):
    path = os.path.join(base, RS.STATE_FILE)
    return path + ".tmp." + str(threading.get_ident())


def _open_proc(text, name):
    def fake(path, *args, **kwargs):
        if path == name:
            return io.StringIO(text)
        raise OSError(path)

    return fake


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class ProcParseTest(unittest.TestCase):
    def test_cpu_and_memory_lines(self):
        with mock.patch("builtins.open", _open_proc(
                "cpu  10 20 30 40 5 0 0 0 0 0\ncpu0 1 1 1 1\n", "/proc/stat")):
            self.assertEqual(RS._read_proc_stat(), (45, 105))
        with mock.patch("builtins.open", _open_proc(
                "MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 250 kB\n",
                "/proc/meminfo")):
            self.assertEqual(RS._mem_fraction(), 0.75)
        with mock.patch("builtins.open", _open_proc(
                "MemTotal: 1000 kB\nMemFree: 400 kB\n", "/proc/meminfo")):
            self.assertEqual(RS._mem_fraction(), 0.6)

    def test_the_state_file_is_owner_only(self):
        cfg = {"resources": {"threshold": 0.5, "cooldown_sec": 0}}
        with tempfile.TemporaryDirectory() as d:
            seen = []
            real_open = os.open

            def spy(path, flags, *args, **kwargs):
                if str(path).endswith(".tmp." + str(threading.get_ident())):
                    seen.append(flags)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.object(RS, "_read_proc_stat", return_value=(0, 100)), \
                 mock.patch.object(RS, "_mem_fraction", return_value=0.1), \
                 mock.patch.object(RS, "_disk_fraction", return_value=0.1), \
                 mock.patch("os.open", side_effect=spy):
                event = RS.check_resources(cfg, d, now=10)
            self.assertIsNone(event)
            path = os.path.join(d, RS.STATE_FILE)
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            self.assertFalse(os.path.exists(_tmp_for(d)))
            with open(path, encoding="utf-8") as fh:
                saved = json.loads(fh.read())
            self.assertEqual(saved["cpu_prev"], [0, 100])
            self.assertTrue(seen)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in seen))
            self.assertTrue(all(flags & os.O_EXCL for flags in seen))


class ProcMutations(unittest.TestCase):
    def test_bad_proc_text_is_none(self):
        for text in ("", "bogus\n", "cpu\n", "cpu a b c\n", "cpu 1 2\n"):
            with mock.patch("builtins.open", _open_proc(text, "/proc/stat")):
                self.assertIsNone(RS._read_proc_stat(), text)
        for text in ("", "MemTotal: no\n", "MemFree: 1 kB\n",
                     "MemTotal: 0 kB\nMemAvailable: 1 kB\n",
                     "MemTotal: 10 kB\nMemAvailable: -1 kB\n"):
            with mock.patch("builtins.open", _open_proc(text, "/proc/meminfo")):
                got = RS._mem_fraction()
            self.assertTrue(got is None or 0.0 <= got <= 1.0, (text, got))
        with mock.patch("builtins.open", side_effect=OSError("gone")):
            self.assertIsNone(RS._read_proc_stat())
            self.assertIsNone(RS._mem_fraction())

    def test_a_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"cpu_prev": [1, 1], "secret": true}\n')
            path = os.path.join(d, RS.STATE_FILE)
            os.symlink(target, path)
            self.assertEqual(RS._load_state(d), {})
            link = _tmp_for(d)
            os.symlink(target, link)
            real_unlink = os.unlink

            def leave_the_link(name):
                if name == link and os.path.islink(name):
                    return
                real_unlink(name)

            with mock.patch("os.unlink", side_effect=leave_the_link):
                RS._save_state(d, {"cpu_prev": [9, 9]})
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())
            self.assertTrue(os.path.islink(path))
            self.assertTrue(os.path.islink(link))

            os.unlink(link)
            RS._save_state(d, {"cpu_prev": [2, 8]})
            self.assertFalse(os.path.islink(path))
            self.assertEqual(_mode(path), 0o600)
            self.assertEqual(RS._load_state(d)["cpu_prev"], [2, 8])
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())


class ProcFuzzTest(unittest.TestCase):
    def test_random_proc_text_and_state_do_not_escape(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for _ in range(200):
                nums = " ".join(str(rng.choice([0, 1, -1, 10 ** 9, "x"]))
                                for _ in range(rng.randrange(0, 8)))
                stat = rng.choice([
                    "cpu %s\n" % nums,
                    "intr 1\n",
                    "",
                    "cpu\n",
                ])
                mem = rng.choice([
                    "MemTotal: %s kB\nMemAvailable: %s kB\n" % (
                        rng.choice([0, 100, "n"]), rng.choice([0, 40, -5])),
                    "MemTotal: 100 kB\nMemFree: 10 kB\n",
                    "",
                    "nope\n",
                ])
                try:
                    with mock.patch("builtins.open", _open_proc(stat, "/proc/stat")):
                        cpu = RS._read_proc_stat()
                    with mock.patch("builtins.open", _open_proc(mem, "/proc/meminfo")):
                        used = RS._mem_fraction()
                    RS._save_state(d, rng.choice([
                        {"cpu_prev": [1, 2], "n": rng.randrange(0, 4)},
                        {"bag": {1}},
                        None,
                    ]))
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if cpu is not None and (len(cpu) != 2 or not all(isinstance(n, int) for n in cpu)):
                    crashes.append(cpu)
                    break
                if used is not None and not (0.0 <= used <= 1.0):
                    crashes.append(used)
                    break
            path = os.path.join(d, RS.STATE_FILE)
            if os.path.isfile(path) and not os.path.islink(path):
                if _mode(path) != 0o600:
                    crashes.append(oct(_mode(path)))
            link = _tmp_for(d)
            if os.path.lexists(link):
                os.unlink(link)
            os.symlink(target, link)
            try:
                RS._save_state(d, {"cpu_prev": [1, 1]})
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
