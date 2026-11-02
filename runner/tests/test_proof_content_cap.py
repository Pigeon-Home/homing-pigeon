#!/usr/bin/env python3
"""Stage 10: content-independence at the production cap.

The code refuses a script when its UTF-8 length is greater
than max_script_bytes. The default, and the ceiling, is
1048576 bytes. A script of exactly that many bytes is
admitted. A script of one byte more is refused, and the
refusal names the cap. The text does not change either
decision.

The scripts are ASCII, so the character count and the byte
count are the same number. The check itself counts bytes.
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

CAP = 1048576


def _echo(payload):
    if "'" in payload:
        raise AssertionError("payload must not contain a quote")
    return "echo '" + payload + "'"


def _pad(payload, n):
    return (payload * ((n // len(payload)) + 1))[:n]


def _scripts():
    # 1048576 is not divisible by len("true\n"). The chain is
    # filled out with a one-byte null command so the script
    # is exactly the cap and still valid bash. The commands
    # sit one per line: as one line of "true;" repeated, the
    # chain is a single list of about 200,000 commands, and
    # bash -n crashes on it (exit -11) at the usual 8 MB
    # stack limit -- the parser, not the script, is what
    # fails there, and whether it happened depended on the
    # stack a neighbouring test left behind.
    chain = ("true\n" * (CAP // len("true\n"))) + ":"
    letters = _echo(_pad("a", CAP - len("echo ''")))
    words = _echo(_pad("allowed_interpreters ", CAP - len("echo ''")))
    return {
        "chain": chain,
        "letters": letters,
        "words": words,
        "over-chain": chain + ":",
        "over-letters": letters + "a",
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


class ProductionCapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scripts = _scripts()

    def test_the_lengths_sit_on_the_boundary(self):
        for name in ("chain", "letters", "words"):
            script = self.scripts[name]
            self.assertEqual(len(script.encode("utf-8")), CAP, name)
        for name in ("over-chain", "over-letters"):
            script = self.scripts[name]
            self.assertEqual(len(script.encode("utf-8")), CAP + 1, name)
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

    def _present(self, script, job_id):
        executed = []

        def execute(*_a, **_k):
            executed.append(len(script.encode("utf-8")))
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

    def test_a_script_of_exactly_the_cap_is_admitted(self):
        for name in ("chain", "letters", "words"):
            executed, notes = self._present(
                self.scripts[name], "r10-" + name)
            self.assertEqual(executed, [CAP], notes[-5:])

    def test_one_byte_over_the_cap_is_refused_for_the_cap(self):
        for name in ("over-chain", "over-letters"):
            executed, notes = self._present(
                self.scripts[name], "r10-" + name)
            self.assertEqual(executed, [], name)
            self.assertTrue(
                any("max_script_bytes" in msg and "1048577" in msg
                    for msg in notes),
                notes[-5:])


if __name__ == "__main__":
    unittest.main()
