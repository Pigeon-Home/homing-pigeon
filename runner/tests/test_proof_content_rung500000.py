#!/usr/bin/env python3
"""Content redo at 500,000 characters. Both shells, one command
per line, the catalog cycled. 500,000 is not a code limit."""
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

RUNG = 500000


class Rung500000RedoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = {n: bash_script(RUNG, n) for n in (0, 5, 11)}
        cls.past = bash_script(RUNG + 1, 0)
        cls.ps = {n: ps_script(RUNG, n) for n in (0, 5, 11)}

    def test_lengths_and_variety(self):
        self.assertEqual(len(set(self.bash.values())), 3)
        for script in self.bash.values():
            self.assertEqual(len(script), RUNG)
            self.assertGreater(len(set(script.split("\n"))), 10)
        self.assertEqual(len(self.past), RUNG + 1)
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
            executed, notes = present(script, "r500b%d" % name)
            self.assertEqual(executed, [RUNG], notes[-3:])
            executed, notes = present(script, "r500c%d" % name, cap=100)
            self.assertEqual(executed, [])
            self.assertTrue(any("max_script_bytes" in m for m in notes))
        executed, notes = present(self.past, "r500past")
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
            executed, notes = present(script, "r500p%d" % name)
            self.assertEqual(executed, [RUNG], notes[-3:])


if __name__ == "__main__":
    unittest.main()
