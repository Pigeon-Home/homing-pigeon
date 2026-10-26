"""Linux install receipt: mode 0600, and a symlink is not followed.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not read
or written through.
"""
import json
import os
import random
import tempfile
import threading
import unittest
from unittest import mock

from runner.guard import atomicio as _atomicio

# The atomic writer (runner/guard/atomicio.py) picks a random temp
# name; these tests plant symlinks at the exact name, so the name is
# pinned for the module (Agent-Chat-Stamp
# 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f).
_PIN = mock.patch.object(_atomicio, "_temp_name", lambda p: p + ".tmp.pinned")


def setUpModule():
    _PIN.start()


def tearDownModule():
    _PIN.stop()

from runner.ops.install import RECEIPT_NAME, _read_receipt, _write_receipt


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _path(home):
    return os.path.join(home, RECEIPT_NAME)


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class ReceiptFileTest(unittest.TestCase):
    def test_a_fresh_receipt_is_owner_only(self):
        with tempfile.TemporaryDirectory() as home:
            seen = []
            real_open = os.open

            def spy(path, flags, *args, **kwargs):
                if ".tmp." in str(path):
                    seen.append(flags)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.dict(os.environ, {"USERNAME": "tester", "USERDOMAIN": ""},
                                 clear=False), \
                 mock.patch("os.open", side_effect=spy):
                os.environ.pop("USERDOMAIN", None)
                _write_receipt(home, fresh=True)
            got = _read_receipt(home)
            self.assertEqual(got["installed_by"], "tester")
            self.assertEqual(got["layout_version"], 1)
            self.assertNotIn("upgraded_at", got)
            path = _path(home)
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            self.assertTrue(seen)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in seen))
            self.assertTrue(all(flags & os.O_EXCL for flags in seen))
            _write_receipt(home, fresh=False)
            second = _read_receipt(home)
            self.assertEqual(second["installed_at"], got["installed_at"])
            self.assertIn("upgraded_at", second)
            self.assertEqual(_mode(path), 0o600)

    def test_a_symlink_is_not_read(self):
        with tempfile.TemporaryDirectory() as home:
            target = os.path.join(home, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"installed_by": "root", "secret": true}\n')
            path = _path(home)
            os.symlink(target, path)
            self.assertEqual(_read_receipt(home), "corrupt")
            _write_receipt(home, fresh=True)
            self.assertFalse(os.path.islink(path))
            got = _read_receipt(home)
            self.assertNotIn("secret", got)
            self.assertEqual(_mode(path), 0o600)
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())


class ReceiptMutations(unittest.TestCase):
    def test_corrupt_and_odd_users_do_not_raise(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertIsNone(_read_receipt(home))
            path = _path(home)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("not json{")
            self.assertEqual(_read_receipt(home), "corrupt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[1, 2]\n")
            self.assertEqual(_read_receipt(home), "corrupt")
            for user in ("tester", "a\nb", "a/b", "", "ü"):
                with mock.patch.dict(os.environ, {"USERNAME": user}, clear=False):
                    os.environ.pop("USERDOMAIN", None)
                    _write_receipt(home, fresh=True)
                got = _read_receipt(home)
                self.assertIsInstance(got, dict)
                self.assertEqual(_mode(path), 0o600)
                with open(path, encoding="utf-8") as fh:
                    json.load(fh)


class ReceiptFuzzTest(unittest.TestCase):
    def test_random_users_stay_owner_only(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as home:
            target = os.path.join(home, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(80):
                user = "".join(chr(rng.randrange(32, 127))
                               for _ in range(rng.randrange(0, 12)))
                try:
                    with mock.patch.dict(os.environ, {"USERNAME": user}, clear=False):
                        os.environ.pop("USERDOMAIN", None)
                        _write_receipt(home, fresh=rng.choice([True, False]))
                    got = _read_receipt(home)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(got, dict) or _mode(_path(home)) != 0o600:
                    crashes.append("shape")
                    break
            path = _path(home)
            os.remove(path)
            os.symlink(target, path)
            try:
                self.assertEqual(_read_receipt(home), "corrupt")
                _write_receipt(home, fresh=True)
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
            if os.path.islink(path):
                crashes.append("still-link")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
