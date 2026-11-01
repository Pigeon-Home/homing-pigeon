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


# Line endings are bytes too. The two tests above failed on the
# Windows CI leg for 3.15.26 (build runs 41335002283 and
# 41335002330, build-windows job, shard 2): the staged bytes came
# back with CRLF where the sender sent LF --
#   b"# héllo\r\nprint('🦆')\r\n" != b"# héllo\nprint('🦆')\n"
#   b"echo héllo 🦆\r\n" != b"echo héllo 🦆\n"
# while every Linux leg was green. Cause: the non-PowerShell
# branch staged through a text-mode open, and text mode on
# Windows translates "\n" to "\r\n" on write (on Linux the same
# code is an identity, which is why the bug hid until the Windows
# leg ran the family). A sender's CRLF is likewise mangled the
# other way: its "\n" half becomes CRLF, giving CR-CRLF.
#
# The samples below bookend the odd characters: LF, CRLF and CR
# endings, mixed endings, no trailing ending, runs of endings at
# the front, middle and back (the bookend rule), and non-ASCII
# text at the front, middle and back. Every sample must stage
# byte for byte, for sh and for Python, with no BOM.
LINE_ENDING_SAMPLES = [
    "echo héllo 🦆\n",
    "# héllo\nprint('🦆')\n",
    "echo one\necho two\necho café\n",
    "echo one\r\necho two\r\necho café\r\n",
    "echo one\recho two\recho café\r",
    "echo one\necho two\r\necho three\recho four\n",
    "echo héllo 🦆",
    "# héllo\nprint('🦆')",
    "echo x\n\n\necho y\n",
    "echo x\r\n\r\n\r\necho y\r\n",
    "\necho leading blank line\n",
    "\r\necho leading blank line\r\n",
    "echo front 🦆\n" + "\n" * 10 + "echo back é\n",
    "echo front é\r\n" + "\r\n" * 10 + "echo back 🦆\r\n",
    "é" * 10 + "\n" + "a" * 10 + "\n",
    "🦆" * 5 + "\r\n" + "mid é" + "\r\n" + "🦆" * 5 + "\r\n",
    ";-- echo bookends --;\n",
    "# --;'\" bookends\nprint('x')\n# --;'\" bookends\n",
]


class OtherInterpretersLineEndingsExactBytesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._n = 0

    def _stage_one(self, interpreter, script):
        self._n += 1
        return _stage(self._tmp, f"lines-{self._n}", interpreter, script)

    def test_sh_line_endings_keep_exact_bytes(self):
        for script in LINE_ENDING_SAMPLES:
            with self.subTest(script=repr(script[:24])):
                name, data = self._stage_one(["sh"], script)
                self.assertEqual(name, "script")
                self.assertFalse(data.startswith(BOM))
                self.assertEqual(data, script.encode("utf-8"))

    def test_python_line_endings_keep_exact_bytes(self):
        for script in LINE_ENDING_SAMPLES:
            with self.subTest(script=repr(script[:24])):
                name, data = self._stage_one([sys.executable], script)
                self.assertEqual(name, "script.py")
                self.assertFalse(data.startswith(BOM))
                self.assertEqual(data, script.encode("utf-8"))

    def test_powershell_line_endings_round_trip_under_bom(self):
        # The .ps1 branch already wrote bytes; pinning it here so
        # a unification of the two branches cannot regress it.
        for script in ("Write-Output \"héllo\"\n",
                       "Write-Output \"héllo\"\r\n",
                       "Write-Output \"one\"\nWrite-Output \"🦆\"\r\n"):
            with self.subTest(script=repr(script[:24])):
                name, data = self._stage_one(["powershell"], script)
                self.assertEqual(name, "script.ps1")
                self.assertTrue(data.startswith(BOM))
                self.assertEqual(data.count(BOM), 1)
                self.assertEqual(data.decode("utf-8-sig"), script)


class StagingWritesBytesNotTextTest(unittest.TestCase):
    """The deterministic substrate of the Windows failure.

    Text-mode newline translation cannot be reproduced on a
    Linux host (there os.linesep is the identity), so the
    behavioural tests above only fail where the bug lives, on
    Windows. This pin records the substrate they depend on, on
    every host: script staging in runner/ops/exec.py must write
    encoded bytes in binary mode, never a text-mode open whose
    newline translation is platform-dependent.
    """

    def test_exec_staging_opens_the_script_in_binary_mode(self):
        path = os.path.join(REPO, "runner", "ops", "exec.py")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn('open(script_path, "w"', source,
                         "text-mode staging translates newlines "
                         "on Windows; stage the encoded bytes")
        self.assertIn('open(script_path, "wb"', source)


if __name__ == "__main__":
    unittest.main()
