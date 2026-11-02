#!/usr/bin/env python3
"""Stage 7: content-independence at the first rung.

The gate model treats a script as a length and a digest. The
challenge in docs/proofs/thinking.md is to show that on the
real gate, not only by reading the check order. These tests
build the scripts a default bash can construct in 49
characters or fewer, check that bash accepts each as syntax,
and present each to handle_mail. The gate's decision is the
same for every one of them. A one-byte cap refuses every one
of them, and the refusal names the cap, not the text.

The scripts are not run. execute_job is the gate's decision
to run, and it is stubbed. bash -n is a syntax check only.
PowerShell is not installed here, so that half of the
challenge is not claimed.
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

# The inventory. Each line is one construct a default bash
# has, written so the whole script is at most 49 characters.
# The groups are the ones thinking.md names: a simple command,
# a pipeline, the operators that join commands, a conditional,
# a loop, a function, grouping, the expansions, redirection,
# and the quoting forms.
SCRIPTS = (
    "echo ok",
    "true",
    "printf x",
    ":",
    "echo ok | wc -c",
    "echo a && echo b",
    "echo a || true",
    "echo a; echo b",
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
    "echo a\\ b",
    # The text names a policy field. The gate does not read
    # the script for that, so this one is admitted too.
    "echo allowed_interpreters",
)

BOUND = 49


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


class ContentIndependenceTest(unittest.TestCase):
    def test_the_inventory_is_inside_the_first_rung(self):
        self.assertGreaterEqual(len(SCRIPTS), 20)
        for script in SCRIPTS:
            self.assertLessEqual(len(script), BOUND, script)
            self.assertEqual(script, script.strip())

    # The bash -n leg is POSIX-only: on Windows the bash name
    # is answered by the WSL launcher, which is not a bash.
    # The gate legs in this module run in every job.
    @unittest.skipIf(os.name == "nt", "POSIX only")
    def test_bash_accepts_each_script_as_syntax(self):
        for script in SCRIPTS:
            proc = subprocess.run(
                ["bash", "-n"], input=script + "\n",
                text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, script + proc.stderr)

    def _present(self, script, job_id, cap=None):
        executed = []

        def execute(*_a, **_k):
            passed = _a[1] if len(_a) > 1 else {}
            executed.append(passed.get("script"))
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

    def test_every_construct_is_admitted(self):
        for n, script in enumerate(SCRIPTS):
            executed, notes = self._present(script, "c7-%d" % n)
            self.assertEqual(executed, [script], notes)

    def test_a_one_byte_cap_refuses_by_length_not_by_text(self):
        # 0 means unlimited, so the tightest cap that still
        # refuses is 1. A one-byte script is at the cap and
        # is admitted, whichever character it is. Every longer
        # construct is refused, and the refusal names the cap.
        for name, script in (("colon", ":"), ("other", "Z")):
            executed, notes = self._present(script, "c7b-" + name)
            self.assertEqual(executed, [script], notes)
            executed, notes = self._present(
                script, "c7c-" + name, cap=1)
            self.assertEqual(executed, [script], notes)
        for n, script in enumerate(SCRIPTS):
            if len(script.encode("utf-8")) <= 1:
                continue
            executed, notes = self._present(
                script, "c7d-%d" % n, cap=1)
            self.assertEqual(executed, [], script)
            self.assertTrue(
                any("max_script_bytes" in msg for msg in notes),
                notes)


if __name__ == "__main__":
    unittest.main()
