"""Linux runner log tail. A symlink is not the log.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not opened.
"""
import os
import random
import tempfile
import unittest

from runner.runner import _runner_log_tail


class LogTailTest(unittest.TestCase):
    def test_a_regular_log_is_tailed_and_a_symlink_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "runner.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("line one\nline two\n")
            self.assertIn("line two", _runner_log_tail(d))
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("secret-log-line\n")
            os.remove(path)
            os.symlink(target, path)
            self.assertEqual(_runner_log_tail(d), "")
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "secret-log-line\n")
            self.assertTrue(os.path.islink(path))


class LogTailMutations(unittest.TestCase):
    def test_bad_inputs_do_not_raise(self):
        self.assertEqual(_runner_log_tail(None), "")
        self.assertEqual(_runner_log_tail(""), "")
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_runner_log_tail(d), "")
            path = os.path.join(d, "runner.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("")
            self.assertEqual(_runner_log_tail(d), "")
            lines = ["row %d" % i for i in range(40)]
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            tail = _runner_log_tail(d, max_chars=True)
            self.assertIn("row 39", tail)
            self.assertNotIn("row 0", tail)
            self.assertEqual(_runner_log_tail(d, max_chars=0), "")
            self.assertEqual(_runner_log_tail(d, max_chars=-5), "")
            short = _runner_log_tail(d, max_chars=8)
            self.assertTrue(len(short) <= 8)
            self.assertEqual(_runner_log_tail(d, max_chars="n"),
                             _runner_log_tail(d, max_chars=2000))


class LogTailFuzzTest(unittest.TestCase):
    def test_random_logs_do_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "runner.log")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("secret-log-line\n")
            for i in range(80):
                body = rng.choice([
                    "ok %d\n" % i,
                    "\n".join("r%d" % n for n in range(rng.randrange(0, 35))),
                    "",
                    "no-newline",
                ])
                cap = rng.choice([0, 1, 8, 2000, -1, True, "n"])
                try:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(body)
                    tail = _runner_log_tail(d, max_chars=cap)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(tail, str):
                    crashes.append(type(tail).__name__)
                    break
                if "secret-log-line" in tail:
                    crashes.append("leaked")
                    break
                if isinstance(cap, int) and not isinstance(cap, bool) and cap > 0:
                    if len(tail) > cap:
                        crashes.append(len(tail))
                        break
            os.remove(path)
            os.symlink(target, path)
            try:
                if _runner_log_tail(d) != "":
                    crashes.append("read")
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "secret-log-line\n":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
