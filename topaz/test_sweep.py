"""The sweep itself, against fake cases. No prompt text."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sweep  # noqa: E402
from cases.echo_one import QUESTION, minimal_payload  # noqa: E402


ECHO = '''"""Echo one."""
import subprocess, sys, unittest

def _echo_one():
    out = subprocess.check_output([sys.executable, "-c", "print('one')"], text=True)
    return out.strip()

class EchoOneTest(unittest.TestCase):
    def test_echo_one(self):
        self.assertEqual(_echo_one(), "one")
'''

CRASH = '''"""A case that does not finish clean."""
import unittest

class CrashTest(unittest.TestCase):
    def test_crash(self):
        raise SystemExit(1)
'''


class SweepTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="topaz-sweep-")
        self.cases = os.path.join(self.tmp, "cases")
        self.state = os.path.join(self.tmp, "state")
        os.makedirs(self.cases)
        with open(os.path.join(self.cases, "__init__.py"), "w", encoding="utf-8"):
            pass

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _write(self, name, text):
        with open(os.path.join(self.cases, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_echo_cases_leave_the_list(self):
        self._write("echo_one.py", ECHO)
        code = sweep.sweep("slow", self.cases, self.state)
        self.assertEqual(code, 0)
        self.assertEqual(sweep._read_ids(os.path.join(self.state, "pending.txt")), [])
        self.assertEqual(
            sweep._read_ids(os.path.join(self.state, "done.txt")),
            ["echo_one.EchoOneTest.test_echo_one"])
        self.assertFalse(os.path.exists(os.path.join(self.state, "suspicious.txt")))

    def test_a_crash_is_not_done_and_is_not_retried(self):
        self._write("echo_one.py", ECHO)
        self._write("crash_one.py", CRASH)
        sweep.sweep("default", self.cases, self.state)
        self.assertEqual(
            sweep._read_ids(os.path.join(self.state, "done.txt")),
            ["echo_one.EchoOneTest.test_echo_one"])
        self.assertEqual(
            sweep._read_ids(os.path.join(self.state, "suspicious.txt")),
            ["crash_one.CrashTest.test_crash"])
        done_path = os.path.join(self.state, "done.txt")
        with open(done_path, encoding="utf-8") as fh:
            before = fh.read()
        sweep.sweep("default", self.cases, self.state)
        with open(done_path, encoding="utf-8") as fh:
            after = fh.read()
        self.assertEqual(before, after)
        self.assertEqual(sweep._read_ids(os.path.join(self.state, "pending.txt")), [])

    def test_discover_does_not_import_the_case(self):
        path = os.path.join(self.cases, "echo_one.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("raise SystemExit('imported')\n")
            fh.write(ECHO)
        found = sweep.discover(self.cases)
        self.assertEqual(found, ["echo_one.EchoOneTest.test_echo_one"])

    def test_echo_payload_has_no_project_context(self):
        payload = minimal_payload("qwen2.5:3b")
        self.assertEqual(payload["model"], "qwen2.5:3b")
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(payload["messages"][0]["content"], QUESTION)
        self.assertNotIn("system", [m["role"] for m in payload["messages"]])
        self.assertLess(len(QUESTION), 80)


if __name__ == "__main__":
    unittest.main()
