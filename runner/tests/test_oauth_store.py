#!/usr/bin/env python3
"""Queue A: `store_refresh_token`'s guards and failure
cleanup, on every platform.

The token file's thorough suite (test_linux_oauth) is
Linux-only by design -- it pins POSIX modes, nofollow
opens and systemd units -- so on the Windows coverage
map the store's guards never ran at all (coverage run
40183585961: 12 lines), and its write-failure cleanup
ran nowhere (9 more on Linux). The guards are platform
agnostic, and they are the ones that protect the
credential: a config path is required, a symlink is
never followed, the config must be an object, and the
token must be one line so it cannot break the JSON
writer or smuggle a second record. The cleanup promise:
a write that fails midway leaves no staging file, and
a cleanup step that itself fails never masks the
original error.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

from runner.wire import oauth
from runner.wire.oauth import store_refresh_token

CFG = {"oauth_client_id": "cid", "mailbox_user": "a@b.c"}


class StoreGuardsTest(unittest.TestCase):
    def test_the_path_is_required(self):
        for bad in ("", None, 5):
            with self.subTest(path=bad):
                with self.assertRaises(ValueError):
                    store_refresh_token(bad, dict(CFG), "tok")

    def test_the_config_must_be_an_object(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            for bad in (None, [], "nope"):
                with self.subTest(cfg=bad):
                    with self.assertRaises(TypeError):
                        store_refresh_token(path, bad, "tok")

    def test_the_token_must_be_one_line(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            for bad in ("", "a\nb", "a\rb", "a\x00b", None, 1):
                with self.subTest(token=bad):
                    with self.assertRaises((ValueError, TypeError)):
                        store_refresh_token(path, dict(CFG), bad)
            self.assertFalse(os.path.exists(path))

    def test_a_symlink_config_is_never_followed(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target.json")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            path = os.path.join(d, "config.json")
            try:
                os.symlink(target, path)
            except (OSError, NotImplementedError):
                self.skipTest("cannot create a symlink here")
            with self.assertRaises(OSError):
                store_refresh_token(path, dict(CFG), "tok")
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")


class StoreWriteTest(unittest.TestCase):
    def test_the_store_round_trips_and_copies_the_config(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "deep", "config.json")
            cfg = dict(CFG)
            saved = store_refresh_token(path, cfg, "tok-1")
            self.assertEqual(cfg, CFG)  # the caller's dict is untouched
            self.assertEqual(saved["auth"], "oauth")
            self.assertEqual(saved["oauth_refresh_token"], "tok-1")
            with open(path, encoding="utf-8") as fh:
                on_disk = json.load(fh)
            self.assertEqual(on_disk["oauth_refresh_token"], "tok-1")
            self.assertEqual(on_disk["mailbox_user"], "a@b.c")
            if os.name != "nt":
                self.assertEqual(
                    os.stat(path).st_mode & 0o777, 0o600)

    def test_a_failed_chmod_does_not_fail_the_store(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch.object(
                    os, "chmod",
                    side_effect=OSError("mode refused")):
                saved = store_refresh_token(path, dict(CFG), "tok")
            self.assertEqual(saved["oauth_refresh_token"], "tok")
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(
                    json.load(fh)["oauth_refresh_token"], "tok")

    def test_a_failed_write_leaves_no_staging_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch.object(
                    os, "fdopen",
                    side_effect=OSError("disk")):
                with self.assertRaises(OSError) as cm:
                    store_refresh_token(path, dict(CFG), "tok")
            self.assertEqual(str(cm.exception), "disk")
            self.assertEqual(os.listdir(d), [])

    def test_a_failed_close_does_not_mask_the_write_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch.object(
                    os, "fdopen",
                    side_effect=OSError("disk")), \
                    mock.patch.object(
                        os, "close",
                        side_effect=OSError("close refused")):
                with self.assertRaises(OSError) as cm:
                    store_refresh_token(path, dict(CFG), "tok")
            self.assertEqual(str(cm.exception), "disk")
            self.assertEqual(os.listdir(d), [])

    def test_a_failed_cleanup_unlink_does_not_mask_the_write_error(self):
        real_unlink = os.unlink

        def unlink(path, *a, **kw):
            if ".tmp." in str(path) and os.path.exists(path):
                raise OSError("unlink refused")
            return real_unlink(path, *a, **kw)

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch.object(
                    os, "fdopen",
                    side_effect=OSError("disk")), \
                    mock.patch.object(os, "unlink", unlink):
                with self.assertRaises(OSError) as cm:
                    store_refresh_token(path, dict(CFG), "tok")
            self.assertEqual(str(cm.exception), "disk")


if __name__ == "__main__":
    unittest.main(verbosity=2)
