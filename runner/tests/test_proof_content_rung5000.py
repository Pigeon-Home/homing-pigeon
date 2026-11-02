#!/usr/bin/env python3
"""Content-independence redo at 5,000 characters.

The review in docs/proofs/content-series-review.md asked for
this rung first. It was missing from the earlier series. The
scripts are built from a catalog of constructs, one command
per line, cycled so the length is real material and not one
command stretched. bash -n checks the shell scripts.
PowerShell's own parser checks the PowerShell scripts when
pwsh is installed; where it is not, those cases are skipped
and the skip says so.

5,000 is the rung of the claim. It is not a limit in the
code. A script of 5,001 characters is still admitted.
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

RUNG = 5000

BASH = (
    "echo ok",
    "true",
    "printf x",
    ":",
    "echo ok | wc -c",
    "echo a && echo b",
    "echo a || true",
    "if true; then echo a; fi",
    "for i in a; do echo $i; done",
    "f(){ echo a; }; f",
    "(echo a)",
    "{ echo a; }",
    "echo {a,b}",
    "echo $HOME",
    "echo $(true)",
    "echo $((1+2))",
    "echo a > /dev/null",
    "echo 'a b'",
    'echo "a b"',
    "echo allowed_interpreters",
    "pwd",
    "echo ${HOME}",
)

POWERSHELL = (
    "Write-Output ok",
    "Get-Location",
    "$true",
    "Write-Output 'a b'",
    'Write-Output "a b"',
    "Write-Output $HOME",
    "Write-Output (1 + 2)",
    "Write-Output $($true)",
    "if ($true) { Write-Output a }",
    "foreach ($i in 1) { Write-Output $i }",
    "function f { Write-Output a }; f",
    "& { Write-Output a }",
    "Write-Output a > $null",
    "Write-Output allowed_interpreters",
    "Get-Date",
    "Write-Output ${HOME}",
)


def _pwsh():
    found = shutil.which("pwsh")
    if found:
        return found
    candidate = "/workspace/pwsh/pwsh"
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return None


def compose(n, catalog, start, pad_open, pad_close):
    """One command per line, catalog cycled from start, then one
    pad line that makes the character count exact."""
    min_pad = 1 + len(pad_open) + 1 + len(pad_close)
    lines = []
    i = start
    while i - start < 100000:
        line = catalog[i % len(catalog)]
        trial = "\n".join(lines + [line])
        if len(trial) + min_pad > n:
            break
        lines.append(line)
        i += 1
    if not lines:
        raise AssertionError("catalog line longer than the rung")
    body = "\n".join(lines)
    remain = n - len(body)
    payload = "p" * (remain - len("\n") - len(pad_open) - len(pad_close))
    script = body + "\n" + pad_open + payload + pad_close
    if len(script) != n:
        raise AssertionError("%s != %s" % (len(script), n))
    return script


def _bash_scripts():
    return {
        "b0": compose(RUNG, BASH, 0, "echo '", "'"),
        "b3": compose(RUNG, BASH, 3, "echo '", "'"),
        "b9": compose(RUNG, BASH, 9, "echo '", "'"),
        "past": compose(RUNG + 1, BASH, 0, "echo '", "'"),
    }


def _ps_scripts():
    return {
        "p0": compose(RUNG, POWERSHELL, 0, "Write-Output '", "'"),
        "p3": compose(RUNG, POWERSHELL, 3, "Write-Output '", "'"),
        "p9": compose(RUNG, POWERSHELL, 9, "Write-Output '", "'"),
    }


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


class Rung5000Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = _bash_scripts()
        cls.ps = _ps_scripts()

    def test_lengths_and_distinct_texts(self):
        for name in ("b0", "b3", "b9"):
            self.assertEqual(len(self.bash[name]), RUNG, name)
            self.assertEqual(
                len(self.bash[name].encode("utf-8")), RUNG, name)
        self.assertEqual(len(self.bash["past"]), RUNG + 1)
        self.assertEqual(len({self.bash["b0"], self.bash["b3"],
                              self.bash["b9"]}), 3)
        # one command per line, and more than one construct
        for script in self.bash.values():
            lines = script.split("\n")
            self.assertGreater(len(lines), 20)
            self.assertGreater(len(set(lines)), 10)

    def test_bash_accepts_each_as_syntax(self):
        for name, script in self.bash.items():
            proc = subprocess.run(
                ["bash", "-n"], input=script + "\n",
                text=True, capture_output=True)
            self.assertEqual(
                proc.returncode, 0, name + " " + proc.stderr[-300:])

    def _present(self, script, job_id, cap=None):
        executed = []

        def execute(*_a, **_k):
            executed.append(len(script))
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

    def test_the_gate_admits_every_bash_text(self):
        for name, script in self.bash.items():
            executed, notes = self._present(script, "c5-" + name)
            self.assertEqual(executed, [len(script)], notes[-4:])

    def test_a_short_cap_refuses_every_bash_text_for_the_cap(self):
        for name in ("b0", "b3", "b9"):
            executed, notes = self._present(
                self.bash[name], "c5c-" + name, cap=100)
            self.assertEqual(executed, [])
            self.assertTrue(
                any("max_script_bytes" in msg for msg in notes),
                notes[-4:])

    def test_powershell_parses_and_the_gate_admits_it(self):
        pwsh = _pwsh()
        if not pwsh:
            self.skipTest(
                "pwsh is not installed; the PowerShell half of "
                "this rung was not run")
        for name, script in self.ps.items():
            self.assertEqual(len(script), RUNG, name)
            proc = subprocess.run(
                [pwsh, "-NoProfile", "-Command",
                 "$s = [Console]::In.ReadToEnd(); "
                 "$tok = $null; $errs = $null; "
                 "[void][System.Management.Automation.Language.Parser]::ParseInput("
                 "$s, [ref]$tok, [ref]$errs); "
                 "if ($errs -and $errs.Count -gt 0) { exit 1 } else { exit 0 }"],
                input=script, text=True, capture_output=True)
            self.assertEqual(
                proc.returncode, 0, name + " " + proc.stderr[-400:]
                + proc.stdout[-400:])
            executed, notes = self._present(script, "c5p-" + name)
            self.assertEqual(executed, [RUNG], notes[-4:])
            executed, notes = self._present(
                script, "c5pc-" + name, cap=100)
            self.assertEqual(executed, [])
            self.assertTrue(
                any("max_script_bytes" in msg for msg in notes))


if __name__ == "__main__":
    unittest.main()
