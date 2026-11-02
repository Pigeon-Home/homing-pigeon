#!/usr/bin/env python3
"""Content redo at 50,000 characters. Both shells, one command
per line, the catalog cycled. 50,000 is not a code limit."""
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

RUNG = 50000


class Rung50000RedoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = {n: bash_script(RUNG, n) for n in (0, 5, 11)}
        cls.past = bash_script(RUNG + 1, 0)
        cls.ps = {n: ps_script(RUNG, n) for n in (0, 5, 11)}

    def test_lengths_and_variety(self):
        self.assertEqual(len(set(self.bash.values())), 3)
        for script in list(self.bash.values()) + [self.past]:
            self.assertEqual(
                len(script), RUNG if script is not self.past else RUNG + 1)
            lines = script.split("\n")
            self.assertGreater(len(set(lines)), 10)
        for script in self.ps.values():
            self.assertEqual(len(script), RUNG)

    def test_bash_accepts_each(self):
        for name, script in list(self.bash.items()) + [("past", self.past)]:
            proc = subprocess.run(
                ["bash", "-n"], input=script + "\n",
                text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, str(name) + proc.stderr[-200:])

    def test_the_gate_admits_them_and_a_short_cap_refuses(self):
        for name, script in self.bash.items():
            executed, notes = present(script, "r50b%d" % name)
            self.assertEqual(executed, [RUNG], notes[-3:])
            executed, notes = present(script, "r50c%d" % name, cap=100)
            self.assertEqual(executed, [])
            self.assertTrue(any("max_script_bytes" in m for m in notes))
        executed, notes = present(self.past, "r50past")
        self.assertEqual(executed, [RUNG + 1], notes[-3:])

    def test_powershell(self):
        binary = pwsh()
        if not binary:
            self.skipTest(
                "pwsh is not installed; the PowerShell half of "
                "this rung was not run")
        for name, script in self.ps.items():
            proc = subprocess.run(
                [binary, "-NoProfile", "-Command",
                 "$s = [Console]::In.ReadToEnd(); $tok=$null; $errs=$null; "
                 "[void][System.Management.Automation.Language.Parser]::ParseInput("
                 "$s, [ref]$tok, [ref]$errs); "
                 "if ($errs -and $errs.Count -gt 0) { exit 1 } else { exit 0 }"],
                input=script, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr[-300:])
            executed, notes = present(script, "r50p%d" % name)
            self.assertEqual(executed, [RUNG], notes[-3:])
            executed, notes = present(script, "r50pc%d" % name, cap=100)
            self.assertEqual(executed, [])
            self.assertTrue(any("max_script_bytes" in m for m in notes))


if __name__ == "__main__":
    unittest.main()
