#!/usr/bin/env python3
"""Content checks with FreeBSD sh.

FreeBSD /bin/sh is not bash and not the macOS sh. This test
runs only when that program is present at HP_FREEBSD_SH or
/tmp/freebsd-sh. It does not substitute dash, or bash in
POSIX mode, for it. The skip message is the reason.
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
    at_length, enumerate49, freebsd_sh)

CAP = 1048576


class FreeBSDShTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = freebsd_sh()

    def setUp(self):
        if not self.binary:
            self.skipTest(
                "FreeBSD sh is not on this machine. Its sources "
                "are the FreeBSD base system and do not build "
                "with the Linux toolchain here, and qemu-user "
                "runs Linux binaries, not FreeBSD ones. dash "
                "was not used in its place")

    def _syntax(self, script):
        return subprocess.run(
            [self.binary, "-n"], input=script + "\n",
            text=True, capture_output=True)

    def test_first_rung(self):
        scripts = enumerate49()
        self.assertGreaterEqual(len(scripts), 2000)
        joined = self._syntax("\n".join(scripts))
        self.assertEqual(joined.returncode, 0, joined.stderr[-300:])
        for n, script in enumerate(scripts):
            executed, _notes = present(script, "f49b%d" % n)
            self.assertEqual(executed, [len(script)], script)

    def test_the_long_rungs(self):
        for n, prefix in ((5000, "f5"), (50000, "f50"),
                          (500000, "f500"), (CAP, "fcap")):
            for name, start in (("a", 0), ("b", 5), ("c", 11)):
                script = at_length(n, start)
                proc = self._syntax(script)
                self.assertEqual(proc.returncode, 0, proc.stderr[-200:])
                executed, notes = present(script, "%s%s" % (prefix, name))
                self.assertEqual(executed, [n], notes[-3:])
            over = at_length(n + 1, 0)
            proc = self._syntax(over)
            self.assertEqual(proc.returncode, 0, proc.stderr[-200:])
            executed, notes = present(over, prefix + "over")
            if n == CAP:
                self.assertEqual(executed, [])
                self.assertTrue(any("1048577" in m for m in notes))
            else:
                self.assertEqual(executed, [n + 1], notes[-3:])


if __name__ == "__main__":
    unittest.main()
