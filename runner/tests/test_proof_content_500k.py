#!/usr/bin/env python3
"""Stage 9: content-independence at 500,000 characters.

Stage 8 did this at 50,000 characters. The next figure the
ladder names is 500,000. It is a bound of the claim, not a
limit in the code. The code's script cap remains 1048576
UTF-8 bytes, so a script of 500,000 characters is inside
the cap, and a script of one character past the rung is
still inside the cap.
"""
import os
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

RUNG = 500000


def _echo(payload):
    if "'" in payload:
        raise AssertionError("payload must not contain a quote")
    return "echo '" + payload + "'"


def _pad(payload, n):
    return (payload * ((n // len(payload)) + 1))[:n]


def _scripts():
    # One command per line, not one long list: a single
    # line of this many commands overflows the stack of
    # bash's parser at the larger rungs (see the cap
    # module). "true\n" is the same length as "true;".
    chain = "true\n" * (RUNG // len("true\n"))
    letters = _echo(_pad("a", RUNG - len("echo ''")))
    words = _echo(_pad("allowed_interpreters ", RUNG - len("echo ''")))
    return {
        "chain": chain,
        "letters": letters,
        "words": words,
        "past": chain + ":",
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


class Rung500000Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scripts = _scripts()

    def test_the_rung_scripts_are_exactly_500000_characters(self):
        for name in ("chain", "letters", "words"):
            script = self.scripts[name]
            self.assertEqual(len(script), RUNG, name)
            self.assertEqual(len(script.encode("utf-8")), RUNG, name)
        self.assertEqual(len(self.scripts["past"]), RUNG + 1)
        texts = [self.scripts[n] for n in ("chain", "letters", "words")]
        self.assertEqual(len(set(texts)), 3)

    # The bash -n leg is POSIX-only: on Windows the bash name
    # is answered by the WSL launcher, which is not a bash.
    # The gate legs in this module run in every job.
    @unittest.skipIf(os.name == "nt", "POSIX only")
    def test_bash_accepts_each_as_syntax(self):
        for name, script in self.scripts.items():
            proc = subprocess.run(
                ["bash", "-n"], input=script + "\n",
                text=True, capture_output=True)
            self.assertEqual(
                proc.returncode, 0, name + " " + proc.stderr[-200:])

    def _present(self, script, job_id, cap=None):
        executed = []

        def execute(*_a, **_k):
            passed = _a[1] if len(_a) > 1 else {}
            executed.append(len(passed.get("script") or ""))
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

    def test_the_gate_admits_every_text_at_the_rung(self):
        for name in ("chain", "letters", "words", "past"):
            executed, notes = self._present(
                self.scripts[name], "r9-" + name)
            self.assertEqual(
                executed, [len(self.scripts[name])], notes[-5:])

    def test_a_short_cap_refuses_every_text_for_the_cap(self):
        for name in ("chain", "letters", "words"):
            executed, notes = self._present(
                self.scripts[name], "r9c-" + name, cap=100)
            self.assertEqual(executed, [], name)
            self.assertTrue(
                any("max_script_bytes" in msg for msg in notes),
                notes[-5:])


if __name__ == "__main__":
    unittest.main()
