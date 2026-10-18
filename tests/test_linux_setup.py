"""Linux setup config write: mode 0600, and a symlink is not followed.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process or contacts a mailbox. A planted
symlink is not written through. Secrets stay in the file.
"""
import json
import os
import random
import tempfile
import threading
import unittest
from unittest import mock

from runner.setup import _write_config


def _mode(path):
    return os.stat(path).st_mode & 0o777


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class SetupFileTest(unittest.TestCase):
    def test_a_secret_is_owner_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "nested", "config.json")
            seen = []
            real_open = os.open

            def spy(file_path, flags, *args, **kwargs):
                if str(file_path).endswith(".tmp." + str(threading.get_ident())):
                    seen.append(flags)
                return real_open(file_path, flags, *args, **kwargs)

            secret = "ab" * 32
            with mock.patch("os.open", side_effect=spy):
                _write_config(path, {
                    "shared_secret": secret,
                    "mailbox_user": "a@b.c",
                })
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            self.assertFalse(os.path.exists(path + ".tmp." + str(threading.get_ident())))
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
                saved = json.loads(text)
            self.assertEqual(saved["shared_secret"], secret)
            self.assertTrue(text.endswith("\n"))
            self.assertTrue(seen)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in seen))
            self.assertTrue(all(flags & os.O_EXCL for flags in seen))

    def test_a_symlink_is_replaced_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"secret": true}\n')
            path = os.path.join(d, "config.json")
            os.symlink(target, path)
            _write_config(path, {"shared_secret": "cd" * 32})
            self.assertFalse(os.path.islink(path))
            self.assertEqual(_mode(path), 0o600)
            with open(path, encoding="utf-8") as fh:
                self.assertNotIn("secret", json.load(fh))
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())

            os.remove(path)
            _write_config(path, {"mailbox_user": "a@b.c"})
            link = path + ".tmp." + str(threading.get_ident())
            os.symlink(target, link)
            real_unlink = os.unlink

            def leave_the_link(name):
                if name == link and os.path.islink(name):
                    return
                real_unlink(name)

            with open(path, encoding="utf-8") as fh:
                before = fh.read()
            with mock.patch("os.unlink", side_effect=leave_the_link):
                with self.assertRaises(OSError):
                    _write_config(path, {"shared_secret": "ee" * 32})
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), before)
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())
            self.assertTrue(os.path.islink(link))


class SetupMutations(unittest.TestCase):
    def test_a_non_object_does_not_replace_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            _write_config(path, {"mailbox_user": "a@b.c"})
            with open(path, "rb") as fh:
                before = fh.read()
            for bad in (None, [], "secret", 1, {1}):
                with self.assertRaises(TypeError):
                    _write_config(path, bad)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), before)
            self.assertEqual(_mode(path), 0o600)
            _write_config(path, {})
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), {})


class SetupFuzzTest(unittest.TestCase):
    def test_random_fields_stay_owner_only(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(120):
                cfg = rng.choice([
                    {"shared_secret": "ab" * rng.randrange(0, 8), "n": i},
                    {"mailbox_user": rng.choice(["a@b.c", "", "a\nb", "ü"])},
                    {},
                    None,
                    [],
                ])
                try:
                    _write_config(path, cfg)
                except TypeError:
                    if isinstance(cfg, dict):
                        crashes.append("dict")
                        break
                    continue
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(cfg, dict):
                    crashes.append("wrote-non-dict")
                    break
                if _mode(path) != 0o600 or os.path.islink(path):
                    crashes.append("mode")
                    break
                with open(path, encoding="utf-8") as fh:
                    if not isinstance(json.load(fh), dict):
                        crashes.append("shape")
                        break
            link = path + ".tmp." + str(threading.get_ident())
            if os.path.lexists(link):
                os.unlink(link)
            os.symlink(target, link)
            real_unlink = os.unlink

            def leave_the_link(name):
                if name == link and os.path.islink(name):
                    return
                real_unlink(name)

            try:
                with mock.patch("os.unlink", side_effect=leave_the_link):
                    _write_config(path, {"n": 1})
                crashes.append("no-raise")
            except OSError:
                pass
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
