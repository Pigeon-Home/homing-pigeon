"""Linux config files: mode 0600, and a symlink is not followed.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not read
or written through. Secrets are not printed.
"""
import json
import os
import random
import string
import tempfile
import threading
import unittest
from unittest import mock

from runner.install import (
    _write_json,
    ensure_runner_id,
    ensure_shared_secret,
    set_instructions,
    store_additional_secret,
)


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _seed(path, cfg):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
        fh.write("\n")


class ConfigFileTest(unittest.TestCase):
    def test_a_generated_secret_is_owner_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            _seed(path, {"shared_secret": "changeme", "mailbox_user": "a@b.c"})
            seen = []
            real_open = os.open

            def spy(file_path, flags, *args, **kwargs):
                if str(file_path).endswith(".tmp." + str(threading.get_ident())):
                    seen.append(flags)
                return real_open(file_path, flags, *args, **kwargs)

            buf = __import__("io").StringIO()
            with mock.patch("os.open", side_effect=spy), \
                 mock.patch("sys.stdout", buf):
                ensure_shared_secret(path, None)
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
            secret = saved["shared_secret"]
            self.assertEqual(len(secret), 64)
            self.assertNotIn(secret, buf.getvalue())
            self.assertEqual(saved["mailbox_user"], "a@b.c")
            self.assertEqual(len(saved["runner_id"]), 32)
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            self.assertTrue(seen)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in seen))
            self.assertTrue(all(flags & os.O_EXCL for flags in seen))

    def test_a_symlink_config_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"shared_secret": "changeme", "secret": true}\n')
            path = os.path.join(d, "config.json")
            os.symlink(target, path)
            for call in (
                lambda: ensure_shared_secret(path, None),
                lambda: ensure_runner_id(path),
                lambda: store_additional_secret(path, "ops.reader"),
                lambda: set_instructions(path, "do not follow", append=False),
            ):
                with self.assertRaises(OSError):
                    call()
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())
            self.assertTrue(os.path.islink(path))

            real = os.path.join(d, "real.json")
            _seed(real, {"shared_secret": "ab" * 32})
            link = real + ".tmp." + str(threading.get_ident())
            os.symlink(target, link)
            real_unlink = os.unlink

            def leave_the_link(name):
                if name == link and os.path.islink(name):
                    return
                real_unlink(name)

            with open(real, "rb") as fh:
                before = fh.read()
            with mock.patch("os.unlink", side_effect=leave_the_link):
                with self.assertRaises(OSError):
                    _write_json(real, {"shared_secret": "zz" * 32})
            with open(real, "rb") as fh:
                self.assertEqual(fh.read(), before)
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())
            self.assertTrue(os.path.islink(link))


class ConfigMutations(unittest.TestCase):
    def test_weak_secrets_and_bad_key_ids_do_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            _seed(path, {"shared_secret": "", "additional_secrets": {}})
            with open(path, "rb") as fh:
                before = fh.read()
            for bad in ("aaaa", "changeme", "ab" * 4, "1" * 64):
                with self.assertRaises(SystemExit) as caught:
                    ensure_shared_secret(path, bad)
                self.assertEqual(caught.exception.code, 2)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), before)
            for bad in ("", "a/b", "has space", "x" * 65, "../k", "a\x00b"):
                with self.assertRaises(SystemExit) as caught:
                    store_additional_secret(path, bad)
                self.assertEqual(caught.exception.code, 2)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), before)
            ensure_runner_id(path)
            with open(path, encoding="utf-8") as fh:
                first = json.load(fh)["runner_id"]
            ensure_runner_id(path)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["runner_id"], first)
            self.assertEqual(_mode(path), 0o600)
            set_instructions(path, "   ", append=True)
            with open(path, encoding="utf-8") as fh:
                self.assertNotIn("owner_instructions", json.load(fh))


class ConfigFuzzTest(unittest.TestCase):
    def test_random_key_ids_store_or_refuse(self):
        rng = random.Random(20261017)
        alphabet = string.ascii_letters + string.digits + "._- /\\..\x00"
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            _seed(path, {"additional_secrets": {}})
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(120):
                key = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 70)))
                if rng.randrange(6) == 0:
                    key = rng.choice(["ops.reader", "a/b", "", "x" * 65, "ok-%d" % i])
                buf = __import__("io").StringIO()
                try:
                    with mock.patch("sys.stdout", buf):
                        try:
                            store_additional_secret(path, key)
                        except SystemExit as exc:
                            if exc.code != 2:
                                crashes.append(exc.code)
                                break
                            continue
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                text = buf.getvalue()
                with open(path, encoding="utf-8") as fh:
                    saved = json.load(fh)
                secret = saved["additional_secrets"][key]
                if secret in text or _mode(path) != 0o600:
                    crashes.append("leaked")
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
                    _write_json(path, {"additional_secrets": {}})
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
