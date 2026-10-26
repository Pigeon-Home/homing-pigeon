"""Linux retained job files: mode 0600, and no symlink is followed.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not written
through, and a symlink inside retained/ is not read.
"""
import os
import random
import tempfile
import threading
import unittest
from unittest import mock

from runner.guard import atomicio as _atomicio

from runner.runner import load_retained, save_retained


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _tmp_for(path):
    return path + ".tmp.pinned"

# The atomic writer (runner/guard/atomicio.py) picks a random temp
# name; these tests plant symlinks at the exact name, so the name is
# pinned for the module (Agent-Chat-Stamp
# 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f).
_PIN = mock.patch.object(_atomicio, "_temp_name", lambda p: p + ".tmp.pinned")


def setUpModule():
    _PIN.start()


def tearDownModule():
    _PIN.stop()


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class RetainedFileTest(unittest.TestCase):
    def test_a_save_is_owner_only_and_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            seen = []
            real_open = os.open

            def spy(path, flags, *args, **kwargs):
                if ".tmp." in str(path):
                    seen.append(flags)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch("os.open", side_effect=spy):
                save_retained(d, "job.1", {"stdout": "ok", "n": float("nan")})
            got = load_retained(d, "job.1")
            self.assertEqual(got["stdout"], "ok")
            self.assertIsNone(got["n"])
            path = os.path.join(d, "retained", "job.1.json")
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            self.assertFalse(os.path.exists(_tmp_for(path)))
            self.assertTrue(seen)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in seen))
            self.assertTrue(all(flags & os.O_EXCL for flags in seen))

    def test_a_symlink_at_the_temp_name_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            path = os.path.join(d, "retained", "job.1.json")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            link = _tmp_for(path)
            os.symlink(target, link)
            real_unlink = os.unlink

            def leave_the_link(name):
                if name == link and os.path.islink(name):
                    return
                real_unlink(name)

            with mock.patch("os.unlink", side_effect=leave_the_link):
                save_retained(d, "job.1", {"stdout": "pwned"})
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")
            self.assertTrue(os.path.islink(link))
            self.assertFalse(os.path.exists(path))

    def test_a_symlink_inside_retained_is_not_read(self):
        with tempfile.TemporaryDirectory() as d:
            save_retained(d, "job.2", {"stdout": "real"})
            retained = os.path.join(d, "retained")
            target = os.path.join(d, "outside.json")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"stdout": "secret"}\n')
            os.symlink(target, os.path.join(retained, "job.1.json"))
            os.symlink(os.path.join(retained, "job.2.json"),
                       os.path.join(retained, "alias.json"))
            self.assertIsNone(load_retained(d, "job.1"))
            self.assertIsNone(load_retained(d, "alias"))
            self.assertEqual(load_retained(d, "job.2")["stdout"], "real")
            save_retained(d, "job.1", {"stdout": "replaced"})
            self.assertFalse(os.path.islink(os.path.join(retained, "job.1.json")))
            self.assertEqual(load_retained(d, "job.1")["stdout"], "replaced")
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), '{"stdout": "secret"}\n')


class RetainedMutations(unittest.TestCase):
    def test_bad_ids_and_bad_payloads_do_not_escape(self):
        with tempfile.TemporaryDirectory() as d:
            marker = os.path.join(d, "marker")
            with open(marker, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for bad in ("", ".", "..", "a/b", "/tmp/x", "a\\b", "a b",
                        "a\x00b", "x" * 129, None, 1):
                save_retained(d, bad, {"escaped": True})
                self.assertIsNone(
                    load_retained(d, bad if isinstance(bad, str) else "a/b"))
            self.assertFalse(os.path.exists(os.path.join(d, "retained", ".json")))
            save_retained(d, "job.1", ["not", "a", "dict"])
            self.assertEqual(load_retained(d, "job.1"), {})
            save_retained(d, "job.1", {"bag": {1}, "n": float("inf")})
            got = load_retained(d, "job.1")
            self.assertEqual(got["bag"], [1])
            self.assertIsNone(got["n"])
            save_retained(None, "job.1", {"x": 1})
            save_retained("", "job.1", {"x": 1})
            with open(marker, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")


class RetainedFuzzTest(unittest.TestCase):
    def test_random_ids_stay_inside_and_owner_only(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(200):
                job_id = rng.choice([
                    "job-%d" % (i % 7),
                    "ok",
                    ".",
                    "..",
                    "a/b",
                    "",
                    "x" * 129,
                    "a b",
                    None,
                ])
                payload = rng.choice([
                    {"n": i, "stdout": "ok"},
                    {"n": float("nan"), "bag": {i}},
                    ["x"],
                    None,
                ])
                try:
                    save_retained(d, job_id, payload)
                    loaded = load_retained(d, job_id if isinstance(job_id, str) else "nope")
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if loaded is not None and not isinstance(loaded, dict):
                    crashes.append(type(loaded).__name__)
                    break
            retained = os.path.join(d, "retained")
            if os.path.isdir(retained):
                for name in os.listdir(retained):
                    path = os.path.join(retained, name)
                    if os.path.islink(path):
                        crashes.append(name)
                        break
                    if os.path.isfile(path) and _mode(path) != 0o600:
                        crashes.append(oct(_mode(path)))
                        break
            path = os.path.join(d, "retained", "job-0.json")
            link = _tmp_for(path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if os.path.lexists(link):
                os.unlink(link)
            os.symlink(target, link)
            try:
                save_retained(d, "job-0", {"stdout": "x"})
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
