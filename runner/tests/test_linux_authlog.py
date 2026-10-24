"""Linux auth and system log tail. A symlink is not the log.

Unit cases, one-field mutations, and a deterministic fuzz.
journalctl is not called. Nothing here starts a process.
A planted symlink is not opened.
"""
import os
import random
import tempfile
import unittest
from unittest import mock

from runner.runner import _host_log_tail, _tail_marked


class AuthLogTest(unittest.TestCase):
    def test_a_failed_password_is_kept_and_a_symlink_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "auth.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("noise\nFailed password for bob\n")
            rows = _tail_marked(path, ("failed password",))
            self.assertEqual(rows, ["Failed password for bob"])
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("Failed password for root secret-auth\n")
            os.remove(path)
            os.symlink(target, path)
            self.assertIsNone(_tail_marked(path, ("failed password",)))
            with mock.patch("runner.runner._AUTH_LOG_PATHS", (path,)), \
                 mock.patch("runner.runner._SYS_LOG_PATHS", ()), \
                 mock.patch("runner.runner.sys.platform", "linux"):
                text = _host_log_tail(journal=False)
            self.assertIsNone(text)
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret-auth", fh.read())
            self.assertTrue(os.path.islink(path))


class AuthLogMutations(unittest.TestCase):
    def test_bad_inputs_do_not_raise(self):
        self.assertIsNone(_tail_marked(None, ("error",)))
        self.assertIsNone(_tail_marked(1, ("error",)))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "syslog")
            self.assertIsNone(_tail_marked(path, ("error",)))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("all quiet\nerror: disk\nFATAL: disk\n")
            self.assertEqual(_tail_marked(path, None), [])
            self.assertEqual(_tail_marked(path, ("error",), max_lines=True), [])
            self.assertEqual(_tail_marked(path, ("error",), max_lines=0), [])
            self.assertEqual(_tail_marked(path, ("error",), max_lines=-1), [])
            self.assertEqual(
                _tail_marked(path, ("error", "nope"), max_lines=1),
                ["error: disk"])
            with mock.patch("runner.runner._AUTH_LOG_PATHS", ()), \
                 mock.patch("runner.runner._SYS_LOG_PATHS", (path,)), \
                 mock.patch("runner.runner.sys.platform", "linux"):
                text = _host_log_tail(max_chars=8, journal=False)
            self.assertIsInstance(text, str)
            self.assertLessEqual(len(text), 8)
            self.assertNotIn("secret-auth", text or "")


class AuthLogFuzzTest(unittest.TestCase):
    def test_random_lines_do_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        crashes = []
        markers = ("failed password", "error", "sudo:")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "auth.log")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("Failed password for root secret-auth\n")
            for i in range(80):
                body = rng.choice([
                    "Failed password for bob %d\n" % i,
                    "all quiet\n",
                    "error: disk\n" * rng.randrange(1, 6),
                    "",
                ])
                cap = rng.choice([1, 3, 20, 0, -1, True, "n"])
                try:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(body)
                    rows = _tail_marked(path, markers, max_lines=cap)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if rows is not None and (
                        not isinstance(rows, list)
                        or any(not isinstance(row, str) for row in rows)):
                    crashes.append("shape")
                    break
                if isinstance(rows, list) and isinstance(cap, int) \
                        and not isinstance(cap, bool) and cap > 0 \
                        and len(rows) > cap:
                    crashes.append(len(rows))
                    break
                if rows and any("secret-auth" in row for row in rows):
                    crashes.append("leaked")
                    break
            os.remove(path)
            os.symlink(target, path)
            try:
                if _tail_marked(path, markers) is not None:
                    crashes.append("read")
                with mock.patch("runner.runner._AUTH_LOG_PATHS", (path,)), \
                     mock.patch("runner.runner._SYS_LOG_PATHS", ()), \
                     mock.patch("runner.runner.sys.platform", "linux"):
                    if _host_log_tail(journal=False) is not None:
                        crashes.append("host")
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if "secret-auth" not in fh.read():
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
