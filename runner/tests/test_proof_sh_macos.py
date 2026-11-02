#!/usr/bin/env python3
"""Content checks with the macOS shell.

macOS /bin/sh is bash 3.2 invoked as sh, which puts it in
POSIX mode. The binary this test accepts is upstream bash
3.2.57, started with --posix. Apple's patches are not in
that binary. Where the binary is absent the tests skip and
say so, rather than treating GNU bash 5 as if it were the
Mac shell.
"""
import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.tests.proof_content_build import present  # noqa: E402
from runner.tests.proof_sh_build import (  # noqa: E402
    at_length, enumerate49, macos_sh)

CAP = 1048576


def _syntax(binary, script):
    return subprocess.run(
        [binary, "--posix", "-n"], input=script + "\n",
        text=True, capture_output=True)


class MacOSShTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = macos_sh()
        cls.small = enumerate49()
        cls.long = {}
        for n in (5000, 50000, 500000, CAP):
            cls.long[n] = {
                "a": at_length(n, 0),
                "b": at_length(n, 5),
                "c": at_length(n, 11),
                "past": at_length(n + 1, 0),
            }

    def setUp(self):
        if not self.binary:
            self.skipTest(
                "the macOS sh parser is not on this machine; "
                "bash 3.2.57 was not found at HP_MACOS_SH or "
                "/tmp/macos-sh, and bash 5 is not that parser")

    def test_the_binary_is_bash_3_2_57(self):
        proc = subprocess.run(
            [self.binary, "--version"], text=True, capture_output=True)
        self.assertIn("3.2.57", proc.stdout + proc.stderr)

    def test_first_rung_parses_and_is_admitted(self):
        self.assertEqual(len(self.small), 3269)
        self.assertTrue(all(len(s) <= 49 for s in self.small))
        joined = _syntax(self.binary, "\n".join(self.small))
        self.assertEqual(joined.returncode, 0, joined.stderr[-300:])
        for n, script in enumerate(self.small):
            executed, notes = present(script, "m49b%d" % n)
            self.assertEqual(executed, [len(script)], script)
        sample = [s for s in self.small if len(s) > 1][:20]
        for n, script in enumerate(sample):
            executed, notes = present(script, "m49c%d" % n, cap=1)
            self.assertEqual(executed, [])
            self.assertTrue(any("max_script_bytes" in m for m in notes))
        executed, notes = present(":", "m49colon", cap=1)
        self.assertEqual(executed, [1], notes[-4:])

    def _long(self, n, prefix):
        group = self.long[n]
        self.assertEqual(len({group["a"], group["b"], group["c"]}), 3)
        for name in ("a", "b", "c", "past"):
            script = group[name]
            want = n if name != "past" else n + 1
            self.assertEqual(len(script), want, name)
            self.assertGreater(len(set(script.split("\n"))), 10)
            proc = _syntax(self.binary, script)
            self.assertEqual(proc.returncode, 0, name + proc.stderr[-200:])
        for name in ("a", "b", "c"):
            executed, notes = present(group[name], "%sb%s" % (prefix, name))
            self.assertEqual(executed, [n], notes[-3:])
        return group

    def test_5000(self):
        group = self._long(5000, "m5")
        executed, notes = present(group["past"], "m5past")
        self.assertEqual(executed, [5001], notes[-3:])
        executed, notes = present(group["a"], "m5cap", cap=100)
        self.assertEqual(executed, [])
        self.assertTrue(any("max_script_bytes" in m for m in notes))

    def test_50000(self):
        group = self._long(50000, "m50")
        executed, notes = present(group["past"], "m50past")
        self.assertEqual(executed, [50001], notes[-3:])

    def test_500000(self):
        group = self._long(500000, "m500")
        executed, notes = present(group["past"], "m500past")
        self.assertEqual(executed, [500001], notes[-3:])

    def test_the_production_cap(self):
        group = self._long(CAP, "mcap")
        executed, notes = present(group["past"], "mcapover")
        self.assertEqual(executed, [])
        self.assertTrue(
            any("max_script_bytes" in m and "1048577" in m for m in notes),
            notes[-4:])


if __name__ == "__main__":
    unittest.main()
