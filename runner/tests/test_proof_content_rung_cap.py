#!/usr/bin/env python3
"""Content redo at the production cap, 1048576 bytes.

The scripts are ASCII, so the character count and the byte
count are the same number. The code admits exactly 1048576
and refuses 1048577. One command per line. Both shells.
"""
import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.tests.proof_content_build import (  # noqa: E402
    bash_script, present, ps_script, pwsh)

CAP = 1048576


class CapRedoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = {n: bash_script(CAP, n) for n in (0, 5, 11)}
        cls.over = bash_script(CAP + 1, 0)
        cls.ps = {n: ps_script(CAP, n) for n in (0, 5, 11)}
        cls.ps_over = ps_script(CAP + 1, 0)

    def test_lengths_and_variety(self):
        self.assertEqual(len(set(self.bash.values())), 3)
        for script in self.bash.values():
            self.assertEqual(len(script.encode("utf-8")), CAP)
            self.assertGreater(len(set(script.split("\n"))), 10)
        self.assertEqual(len(self.over.encode("utf-8")), CAP + 1)
        for script in self.ps.values():
            self.assertEqual(len(script.encode("utf-8")), CAP)

    def test_bash_accepts_each(self):
        for name, script in list(self.bash.items()) + [("over", self.over)]:
            proc = subprocess.run(
                ["bash", "-n"], input=script + "\n",
                text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, str(name) + proc.stderr[-200:])

    def test_the_boundary_is_the_cap_and_not_the_text(self):
        for name, script in self.bash.items():
            executed, notes = present(script, "rcapb%d" % name)
            self.assertEqual(executed, [CAP], notes[-3:])
        executed, notes = present(self.over, "rcapover")
        self.assertEqual(executed, [])
        self.assertTrue(
            any("max_script_bytes" in m and "1048577" in m for m in notes),
            notes[-4:])

    def test_powershell(self):
        binary = pwsh()
        if not binary:
            self.skipTest(
                "pwsh is not installed; the PowerShell half of "
                "this rung was not run")
        for name, script in list(self.ps.items()) + [("over", self.ps_over)]:
            proc = subprocess.run(
                [binary, "-NoProfile", "-Command",
                 "$s = [Console]::In.ReadToEnd(); $tok=$null; $errs=$null; "
                 "[void][System.Management.Automation.Language.Parser]::ParseInput("
                 "$s, [ref]$tok, [ref]$errs); "
                 "if ($errs -and $errs.Count -gt 0) { exit 1 } else { exit 0 }"],
                input=script, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, str(name) + proc.stderr[-300:])
        for name, script in self.ps.items():
            executed, notes = present(script, "rcapp%d" % name)
            self.assertEqual(executed, [CAP], notes[-3:])
        executed, notes = present(self.ps_over, "rcappover")
        self.assertEqual(executed, [])
        self.assertTrue(
            any("max_script_bytes" in m and "1048577" in m for m in notes))


if __name__ == "__main__":
    unittest.main()
