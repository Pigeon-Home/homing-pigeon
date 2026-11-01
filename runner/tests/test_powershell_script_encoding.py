#!/usr/bin/env python3
"""PowerShell script staging must carry a UTF-8 byte order mark.

Finding (Germany rig, 1-Nov-2026, windows-hammering item 6): a job
whose PowerShell script held literal non-ASCII text failed on the
rig with a parser error ("The string is missing the terminator")
and exit 1, and a simpler accented line came back garbled. The
runner stages the script as UTF-8 with no BOM
(runner/ops/exec.py, encoding="utf-8"); Windows PowerShell 5.1 --
the "powershell" interpreter on the rig -- reads a BOM-less file
in the machine ANSI code page instead, so multi-byte UTF-8
sequences are misread and can swallow a closing quote. Non-ASCII
output built at run time from code points round-tripped exactly
in the same run, so the break is in script staging, not in the
output pipeline.

The staged .ps1 must therefore begin with the UTF-8 BOM, exactly
once, and decode back to the sender's script under utf-8-sig.
Other script kinds must NOT gain a BOM: a BOM at the head of an
sh script is a syntax error waiting on some shells, and Python
and generic scripts keep their exact bytes.
"""
import codecs
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402

BOM = codecs.BOM_UTF8

NONASCII_SAMPLES = [
    "héllo wörld",
    "café naïve résumé",
    "中文測試 日本語テスト 한국어",
    "duck 🦆 check ✓ euro €",
    "em — dash, en – dash, curly “quotes”",
    "Ωμέγα αλφάβητο",
    "é" * 10,                       # a run of the odd character
    "a" * 10 + "é",                 # the odd character after a run
    "é" + "a" * 10,                 # the odd character before a run
    "Ω" * 5 + "mid" + "🦆" * 3,
]


def _stage(tmp, job_id, interpreter, script):
    """Run one exec job through staging and return the staged bytes.

    On a machine without the named interpreter the run stops at
    "cannot start interpreter" after staging; that is fine here --
    staging is the unit under test -- so both a result and a
    JobRejected are accepted, and the staged file is read either way.
    """
    job = {"v": 1, "type": "job", "job_id": job_id,
           "issued_at": "2026-11-01T00:00:00Z", "kind": "exec",
           "interpreter": interpreter, "script": script}
    try:
        R.execute_job({"base_dir": tmp}, job, tmp)
    except R.JobRejected:
        pass
    work = os.path.join(tmp, "work", job_id)
    names = sorted(os.listdir(work)) if os.path.isdir(work) else []
    staged = [n for n in names if n.startswith("script")]
    if len(staged) != 1:
        raise AssertionError(f"expected one staged script, found {names}")
    with open(os.path.join(work, staged[0]), "rb") as fh:
        return staged[0], fh.read()


class PowerShellBomTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._n = 0

    def _ps(self, script, interpreter=("powershell",)):
        self._n += 1
        return _stage(self._tmp, f"ps-{self._n}", list(interpreter), script)

    def test_nonascii_scripts_get_one_bom_and_round_trip(self):
        for sample in NONASCII_SAMPLES:
            with self.subTest(sample=sample[:20]):
                script = f'Write-Output "{sample}"\n'
                name, data = self._ps(script)
                self.assertEqual(name, "script.ps1")
                self.assertTrue(data.startswith(BOM),
                                "staged .ps1 must start with a UTF-8 BOM")
                self.assertEqual(data.count(BOM), 1)
                self.assertEqual(data.decode("utf-8-sig"), script)

    def test_nonascii_at_front_middle_and_back(self):
        for script in (
            "# héllo\nWrite-Output \"x\"\n",
            "Write-Output \"héllo\"\n",
            "Write-Output \"x\"\n# héllo at the back 🦆\n",
            "# 🦆 bookend 🦆\nWrite-Output \"x\"\n# 🦆 bookend 🦆\n",
        ):
            with self.subTest(script=script[:24]):
                _name, data = self._ps(script)
                self.assertTrue(data.startswith(BOM))
                self.assertEqual(data.decode("utf-8-sig"), script)

    def test_plain_ascii_powershell_also_gets_the_bom(self):
        script = 'Write-Output "plain ascii"\n'
        _name, data = self._ps(script)
        self.assertTrue(data.startswith(BOM))
        self.assertEqual(data.decode("utf-8-sig"), script)

    def test_pwsh_and_powershell_exe_get_the_bom(self):
        script = 'Write-Output "héllo"\n'
        for interp in (("pwsh",), ("powershell.exe",), ("PowerShell",)):
            with self.subTest(interpreter=interp):
                name, data = self._ps(script, interp)
                self.assertEqual(name, "script.ps1")
                self.assertTrue(data.startswith(BOM))
                self.assertEqual(data.decode("utf-8-sig"), script)

    def test_script_already_carrying_a_bom_gets_exactly_one(self):
        script = "\ufeff" + 'Write-Output "héllo"\n'
        _name, data = self._ps(script)
        self.assertEqual(data.count(BOM), 1)
        self.assertEqual(data.decode("utf-8-sig"),
                         'Write-Output "héllo"\n')


class OtherInterpretersKeepExactBytesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._n = 0

    def _stage_one(self, interpreter, script):
        self._n += 1
        return _stage(self._tmp, f"other-{self._n}", interpreter, script)

    def test_sh_script_has_no_bom(self):
        script = "echo héllo 🦆\n"
        name, data = self._stage_one(["sh"], script)
        self.assertEqual(name, "script")
        self.assertFalse(data.startswith(BOM))
        self.assertEqual(data, script.encode("utf-8"))

    def test_python_script_has_no_bom(self):
        script = "# héllo\nprint('🦆')\n"
        name, data = self._stage_one([sys.executable], script)
        self.assertEqual(name, "script.py")
        self.assertFalse(data.startswith(BOM))
        self.assertEqual(data, script.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
