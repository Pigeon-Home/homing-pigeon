#!/usr/bin/env python3
"""Content redo at the first rung: scripts of at most 49 characters.

Generated, not listed by hand. Bash: every atom, every pair
joined by &&, ||, ;, or a pipe, and every triple of the short
atoms joined by semicolons, kept only when the result is at
most 49 characters. PowerShell: the same shape over its own
constructs, then its own parser drops whatever it rejects.
The survivors are syntax-checked and presented to handle_mail.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner import runner  # noqa: E402
from runner.runner import handle_mail, sign_payload  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402

SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)
BOUND = 49

BASH_ATOMS = (
    "true", ":", "pwd", "false", "echo a", "echo b", "echo c",
    "printf x", "echo ok", "echo 'a'", 'echo "a"', "echo 'a b'",
    'echo "x y"', "echo $HOME", "echo ${HOME}", "echo $((1))",
    "echo $(:)", "echo $((1+2))", "echo {a,b}", "(echo a)",
    "echo a > /dev/null", "if true; then echo a; fi",
)
BASH_JOINERS = (" && ", " || ", "; ", " | ")

PS_ATOMS = (
    "Write-Output a", "Write-Output b", "$true", "Get-Location",
    "Write-Output 'a'", 'Write-Output "a"', "Write-Output $HOME",
    "Write-Output (1+2)", "Get-Date", "Write-Output $($true)",
)
PS_JOINERS = ("; ", " | ")


def _pairs(atoms, joiners):
    out = set(atoms)
    short = [a for a in atoms if len(a) <= 8] if atoms[0] == "true" else [
        a for a in atoms if len(a) <= 16]
    for a in atoms:
        for b in atoms:
            for joiner in joiners:
                script = a + joiner + b
                if len(script) <= BOUND:
                    out.add(script)
    for a in short:
        for b in short:
            for c in short:
                script = a + "; " + b + "; " + c
                if len(script) <= BOUND:
                    out.add(script)
    return sorted(out)


def _pwsh():
    found = shutil.which("pwsh")
    if found:
        return found
    candidate = "/workspace/pwsh/pwsh"
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return None


def _ps_survivors(pwsh, scripts):
    blob = "\n###HP###\n".join(scripts)
    proc = subprocess.run(
        [pwsh, "-NoProfile", "-Command",
         "$raw = [Console]::In.ReadToEnd(); "
         "$parts = $raw -split '###HP###'; "
         "foreach ($s in $parts) { "
         "$s = $s.Trim(\"`n\"); if (-not $s) { continue }; "
         "$tok = $null; $errs = $null; "
         "[void][System.Management.Automation.Language.Parser]::ParseInput("
         "$s, [ref]$tok, [ref]$errs); "
         "if ($errs -and $errs.Count -gt 0) { Write-Output 'BAD' } "
         "else { Write-Output 'OK' } }"],
        input=blob, text=True, capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr[-400:])
    flags = [line for line in proc.stdout.splitlines() if line in ("OK", "BAD")]
    if len(flags) != len(scripts):
        raise AssertionError("%s flags for %s scripts" % (len(flags), len(scripts)))
    kept = [s for s, flag in zip(scripts, flags) if flag == "OK"]
    dropped = len(scripts) - len(kept)
    return kept, dropped


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wire(job):
    signed = sign_payload(job, SECRET)
    body = jobcrypto.encrypt_body(
        signed, SECRET, job_id=job["job_id"], key_id="",
        sign=sign_payload)
    msg = EmailMessage()
    msg["Subject"] = "[HOMING-PIGEON] job " + job["job_id"]
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class Rung49Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = _pairs(BASH_ATOMS, BASH_JOINERS)
        cls.pwsh = _pwsh()
        cls.ps = []
        cls.ps_dropped = None
        if cls.pwsh:
            candidates = _pairs(PS_ATOMS, PS_JOINERS)
            cls.ps, cls.ps_dropped = _ps_survivors(cls.pwsh, candidates)

    def test_the_bash_set_is_thousands_inside_the_bound(self):
        self.assertEqual(len(self.bash), 3682)
        self.assertTrue(all(len(s) <= BOUND for s in self.bash))
        self.assertGreater(len(set(self.bash)), 2000)

    def test_bash_accepts_the_set_as_syntax(self):
        proc = subprocess.run(
            ["bash", "-n"], input="\n".join(self.bash) + "\n",
            text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr[-300:])

    def _present(self, script, job_id, cap=None):
        executed = []

        def execute(*_a, **_k):
            executed.append(1)
            return {"exit_code": 0, "stdout": "", "stderr": "",
                    "timed_out": False, "duration_sec": 0.0}

        notes = []
        job = {
            "v": 1, "type": "job", "job_id": job_id,
            "issued_at": _now(), "kind": "exec", "script": script,
        }
        with tempfile.TemporaryDirectory() as directory:
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
                "base_dir": directory,
                "oracle_opinion_mode": "off",
            }
            if cap is not None:
                cfg["max_script_bytes"] = cap
            with mock.patch.object(runner, "execute_job", execute):
                with mock.patch.object(
                        runner, "log",
                        lambda msg, level="INFO": notes.append(msg)):
                    handle_mail(
                        cfg, mock.Mock(), mock.Mock(), 3,
                        _wire(job), directory, {},
                        runner.build_secrets(cfg),
                        Namespace(dry_run=False, no_send=True), None)
        return executed, notes

    def test_the_gate_admits_every_bash_script(self):
        for n, script in enumerate(self.bash):
            executed, notes = self._present(script, "r49b%d" % n)
            self.assertEqual(executed, [1], script)

    def test_a_one_byte_cap_is_about_length(self):
        # A sample, named as one. The admission above is the
        # whole set. This checks the cap on twenty scripts and
        # on the one-byte builtin, which the cap must still admit.
        sample = [s for s in self.bash if len(s.encode("utf-8")) > 1][:20]
        self.assertEqual(len(sample), 20)
        for n, script in enumerate(sample):
            executed, notes = self._present(script, "r49c%d" % n, cap=1)
            self.assertEqual(executed, [], script)
            self.assertTrue(any("max_script_bytes" in m for m in notes))
        executed, notes = self._present(":", "r49colon", cap=1)
        self.assertEqual(executed, [1], notes[-4:])

    def test_powershell_set_parses_and_is_admitted(self):
        if not self.pwsh:
            self.skipTest(
                "pwsh is not installed; the PowerShell half of "
                "this rung was not run")
        self.assertEqual(len(self.ps), 511)
        self.assertEqual(self.ps_dropped, 10)
        self.assertTrue(all(len(s) <= BOUND for s in self.ps))
        for n, script in enumerate(self.ps):
            executed, notes = self._present(script, "r49p%d" % n)
            self.assertEqual(executed, [1], script)


if __name__ == "__main__":
    unittest.main()
