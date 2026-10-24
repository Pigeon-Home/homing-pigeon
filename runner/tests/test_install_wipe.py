#!/usr/bin/env python3
"""--wipe and --migrate: backup, delete, and consolidation.

No live processes are touched: _kill_runner_processes and the
platform task removal are mocked. Filesystem work happens in temp dirs.
"""
import importlib.util
import io
import os
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "install", os.path.join(REPO, "runner", "install.py"))
install = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install)


def _seed(d, files):
    for rel, text in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)


class WipeMigrateTest(unittest.TestCase):
    def test_merge_tree_never_overwrites(self):
        with tempfile.TemporaryDirectory() as t:
            src = os.path.join(t, "src")
            dst = os.path.join(t, "dst")
            _seed(src, {"a.txt": "new", "sub/b.txt": "b"})
            _seed(dst, {"a.txt": "original"})
            copied, skipped = install._merge_tree(src, dst)
            self.assertEqual((copied, skipped), (1, 1))
            with open(os.path.join(dst, "a.txt"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "original")
            with open(os.path.join(dst, "sub", "b.txt"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "b")

    def test_backup_zip_labels_each_source(self):
        with tempfile.TemporaryDirectory() as t:
            a = os.path.join(t, "a")
            b = os.path.join(t, "b")
            _seed(a, {"x.txt": "x"})
            _seed(b, {"y.txt": "y"})
            zp = os.path.join(t, "out.zip")
            n = install._backup_dirs_to_zip([a, b], zp)
            self.assertEqual(n, 2)
            names = zipfile.ZipFile(zp).namelist()
            self.assertEqual(len(names), 2)
            # Two distinct top-level labels, one per source dir.
            tops = {n.split("/")[0] for n in names}
            self.assertEqual(len(tops), 2)

    def test_do_wipe_backs_up_then_deletes(self):
        with tempfile.TemporaryDirectory() as t:
            d1 = os.path.join(t, "d1", ".homing-pigeon")
            d2 = os.path.join(t, "d2", ".homing-pigeon")
            _seed(d1, {"config.json": "{}", "retained/j1.json": "{}"})
            _seed(d2, {"runner.log": "hi"})
            bdir = os.path.join(t, "backups")
            with mock.patch.object(install, "_candidate_state_dirs",
                                   return_value=[d1, d2]), \
                 mock.patch.object(install, "_kill_runner_processes"), \
                 mock.patch.object(install, "_run_quiet"), \
                 redirect_stdout(io.StringIO()) as out:
                rc = install.do_wipe(backup_dir=bdir)
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(d1))
            self.assertFalse(os.path.exists(d2))
            zips = [f for f in os.listdir(bdir) if f.endswith(".zip")]
            self.assertEqual(len(zips), 1)
            self.assertTrue(zips[0].startswith("homing-pigeon-backup-"))
            with zipfile.ZipFile(os.path.join(bdir, zips[0])) as zf:
                names = zf.namelist()
                self.assertTrue(zf.infolist())
                self.assertEqual(zf.infolist()[0].compress_type,
                                 zipfile.ZIP_DEFLATED)
            self.assertEqual(len(names), 3)
            text = out.getvalue()
            self.assertIn("backed up", text)
            self.assertIn("deleted", text)
            self.assertIn(zips[0], text)

    def test_do_wipe_no_backup(self):
        with tempfile.TemporaryDirectory() as t:
            d1 = os.path.join(t, "d1")
            _seed(d1, {"config.json": "{}"})
            with mock.patch.object(install, "_candidate_state_dirs",
                                   return_value=[d1]), \
                 mock.patch.object(install, "_kill_runner_processes"), \
                 mock.patch.object(install, "_run_quiet"), \
                 redirect_stdout(io.StringIO()) as out:
                rc = install.do_wipe(no_backup=True)
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(d1))
            self.assertIn("--no-backup", out.getvalue())

    def test_do_wipe_no_dirs_found(self):
        with mock.patch.object(install, "_candidate_state_dirs",
                               return_value=[]), \
             mock.patch.object(install, "_kill_runner_processes"), \
             mock.patch.object(install, "_run_quiet"), \
             redirect_stdout(io.StringIO()) as out:
            rc = install.do_wipe()
        self.assertEqual(rc, 0)
        self.assertIn("no .homing-pigeon state dirs found", out.getvalue())

    def test_do_migrate_consolidates(self):
        with tempfile.TemporaryDirectory() as t:
            target = os.path.join(t, "target")
            src = os.path.join(t, "src", ".homing-pigeon")
            _seed(src, {"retained/j1.json": "{}", "config.json": "{}"})
            _seed(target, {"config.json": "{\"a\":1}"})
            with mock.patch.object(install, "_candidate_state_dirs",
                                   return_value=[src, target]), \
                 redirect_stdout(io.StringIO()) as out:
                rc = install.do_migrate(target)
            self.assertEqual(rc, 0)
            # j1.json arrived; target's config.json untouched.
            with open(os.path.join(target, "retained", "j1.json"),
                      encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "{}")
            with open(os.path.join(target, "config.json"),
                      encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "{\"a\":1}")
            text = out.getvalue()
            self.assertIn("1 copied, 1 skipped", text)
            self.assertIn("sources left in place", text)

    def test_candidate_state_dirs_dedupes(self):
        with tempfile.TemporaryDirectory() as t:
            d = os.path.join(t, ".homing-pigeon")
            os.makedirs(d)
            with mock.patch("os.path.expanduser", return_value=t), \
                 mock.patch.object(install.sys, "platform", "linux"):
                dirs = install._candidate_state_dirs()
            self.assertIn(d, dirs)
            self.assertEqual(len(dirs), len(set(dirs)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
