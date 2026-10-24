"""Linux OAuth token file: mode 0600, and a symlink is not followed.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here opens a browser or a socket. A planted symlink is
not read or written through. The token is not printed.
"""
import json
import os
import random
import string
import tempfile
import threading
import unittest
from unittest import mock

from runner.wire.oauth import main, store_refresh_token


def _mode(path):
    return os.stat(path).st_mode & 0o777


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class OauthFileTest(unittest.TestCase):
    def test_the_token_is_owner_only_and_not_printed(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"oauth_client_id": "cid", "mailbox_user": "a@b.c"}, fh)
            seen = []
            real_open = os.open

            def spy(file_path, flags, *args, **kwargs):
                if str(file_path).endswith(".tmp." + str(threading.get_ident())):
                    seen.append(flags)
                return real_open(file_path, flags, *args, **kwargs)

            buf = __import__("io").StringIO()
            with mock.patch("os.open", side_effect=spy), \
                 mock.patch("sys.stdout", buf):
                saved = store_refresh_token(path, {
                    "oauth_client_id": "cid",
                    "mailbox_user": "a@b.c",
                }, "refresh-token-1")
            self.assertEqual(saved["auth"], "oauth")
            self.assertEqual(saved["oauth_refresh_token"], "refresh-token-1")
            self.assertNotIn("refresh-token-1", buf.getvalue())
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            with open(path, encoding="utf-8") as fh:
                on_disk = json.load(fh)
            self.assertEqual(on_disk["mailbox_user"], "a@b.c")
            self.assertEqual(on_disk["oauth_refresh_token"], "refresh-token-1")
            self.assertTrue(seen)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in seen))
            self.assertTrue(all(flags & os.O_EXCL for flags in seen))

    def test_a_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"oauth_refresh_token": "old", "secret": true}\n')
            path = os.path.join(d, "config.json")
            os.symlink(target, path)
            with self.assertRaises(OSError):
                store_refresh_token(path, {"oauth_client_id": "cid"}, "new-token")
            err = __import__("io").StringIO()
            with mock.patch("sys.argv", ["oauth", "--config", path]), \
                 mock.patch("sys.stderr", err), \
                 mock.patch("runner.wire.oauth.browser_consent",
                            return_value="should-not-run") as consent:
                code = main()
            self.assertEqual(code, 2)
            consent.assert_not_called()
            self.assertIn("symlink", err.getvalue())
            self.assertNotIn("should-not-run", err.getvalue())
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())
            self.assertTrue(os.path.islink(path))


class OauthMutations(unittest.TestCase):
    def test_bad_tokens_do_not_replace_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"oauth_client_id": "cid"}\n')
            with open(path, "rb") as fh:
                before = fh.read()
            for bad in ("", "a\nb", "a\rb", "a\x00b", None, 1):
                with self.assertRaises((ValueError, TypeError)):
                    store_refresh_token(path, {"oauth_client_id": "cid"}, bad)
            for bad_cfg in (None, [], "nope"):
                with self.assertRaises(TypeError):
                    store_refresh_token(path, bad_cfg, "token")
            with self.assertRaises(ValueError):
                store_refresh_token("", {"oauth_client_id": "cid"}, "token")
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), before)


class OauthFuzzTest(unittest.TestCase):
    def test_random_tokens_stay_owner_only(self):
        rng = random.Random(20261017)
        alphabet = string.ascii_letters + string.digits + "-._"
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(120):
                token = "".join(rng.choice(alphabet)
                                for _ in range(rng.randrange(0, 24)))
                if rng.randrange(7) == 0:
                    token = rng.choice(["", "a\nb", "a\x00b", "ok-%d" % i])
                try:
                    store_refresh_token(path, {"oauth_client_id": "cid"}, token)
                except ValueError:
                    if token and "\n" not in token and "\x00" not in token:
                        crashes.append("refused")
                        break
                    continue
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if _mode(path) != 0o600 or os.path.islink(path):
                    crashes.append("mode")
                    break
                with open(path, encoding="utf-8") as fh:
                    saved = json.load(fh)
                if saved.get("oauth_refresh_token") != token:
                    crashes.append("mismatch")
                    break
            os.remove(path)
            os.symlink(target, path)
            try:
                store_refresh_token(path, {"oauth_client_id": "cid"}, "token")
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
