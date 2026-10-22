# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
"""Repair on a bare-bones box: a signed job, really executed.

The repair claim (README "Opinions, before anything runs";
PROTOCOL 3.2) is that an absent interpreter is replaced with the
platform default when the script's shape fits, never silently.
A bash-only script does not fit sh, and is not repaired.
tests/test_oracle_opinion.py proves the plan with execute_job
stubbed. This module proves it with nothing stubbed but the mail
transport: the job goes through poll_once and the repaired job
actually runs on a box that has no bash.

It runs only where HP_MINIMAL_USERLAND=1 is set -- the
docker/minimal-userland image (Alpine: BusyBox ash is /bin/sh,
bash is not installed) that .github/workflows/minimal-userland.yml
builds on x86_64 and arm64. Anywhere else the module skips: on a
box with bash these jobs would not need repairing, and the test
would prove nothing.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runner import opinion as op
from runner import runner
from tests import test_oracle_opinion as oo

ENABLED = os.environ.get("HP_MINIMAL_USERLAND") == "1"


def _run(payload, cfg_over=None):
    """One signed job through poll_once, executed for real."""
    tmp = tempfile.mkdtemp(prefix="hp-minimal-")
    cfg = {
        "mailbox_user": oo.SENDER,
        "mailbox_password": oo.SECRET,
        "shared_secret": oo.SECRET,
        "imap_host": "fake", "imap_port": 993,
        "smtp_host": "fake", "smtp_port": 587,
        "max_job_age_sec": 3600,
        "default_timeout_sec": 60,
    }
    cfg.update(cfg_over or {})
    smtp = oo._FakeSMTP()
    runner.poll_once(cfg, tmp, {}, os.path.join(tmp, "seen.json"),
                     imap=oo._FakeIMAP([oo._job_email(payload)]),
                     smtp=smtp)
    return oo._read_result(smtp.sent[-1])


@unittest.skipUnless(ENABLED, "runs in the docker/minimal-userland image")
class MinimalUserlandRepairTests(unittest.TestCase):

    def test_box_really_is_minimal(self):
        # The precondition is the point: if bash crept into the
        # image, every test below would pass for the wrong reason.
        self.assertIsNone(shutil.which("bash"))
        self.assertIsNone(shutil.which("zsh"))
        self.assertIsNotNone(shutil.which("sh"))

    def test_bash_job_is_repaired_and_runs(self):
        job = oo._exec_payload(interpreter=["bash"],
                               script="echo pigeon-$((6 * 7))")
        result = _run(job)
        member = result["oracle_opinion"]
        self.assertEqual(result["exit_code"], 0, result.get("stderr"))
        self.assertIn("pigeon-42", result["stdout"])
        self.assertEqual(member["mode"], "repair")
        self.assertIs(member["repaired"], True)
        self.assertEqual(member["received_digest"],
                         op.received_digest(job))

    def test_posix_shaped_job_is_repaired_and_runs(self):
        job = oo._exec_payload(
            interpreter=["zsh"],
            script="export GREETING=coo\necho \"$GREETING-$(uname -s)\"")
        result = _run(job)
        self.assertEqual(result["exit_code"], 0, result.get("stderr"))
        self.assertIn("coo-Linux", result["stdout"])
        self.assertIs(result["oracle_opinion"]["repaired"], True)

    def test_powershell_shaped_job_is_not_repaired(self):
        # The shape does not fit sh, so there is no repair: the
        # job is never rewritten into something it is not.
        job = oo._exec_payload(interpreter=["pwsh"],
                               script="Write-Host 'hello'")
        result = _run(job)
        member = result.get("oracle_opinion") or {}
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIsNot(member.get("repaired"), True)

    def test_owner_ceiling_diagnose_means_no_repair(self):
        job = oo._exec_payload(interpreter=["bash"], script="echo hi")
        result = _run(job, {"oracle_opinion_mode": "diagnose"})
        member = result.get("oracle_opinion") or {}
        self.assertNotEqual(result["exit_code"], 0)
        self.assertNotIn("repaired", member)

    def test_bash_only_script_is_not_repaired_onto_sh(self):
        # A bash-only script (arrays) naming absent bash is NOT
        # moved onto sh -- that shell cannot run it. shape="bash"
        # does not fit the sh default, so the repair declines and
        # the opinion names bash itself as the thing that is
        # missing.
        job = oo._exec_payload(
            interpreter=["bash"],
            script="#!/bin/bash\nnums=(4 2)\necho \"yes-${nums[1]}\"")
        result = _run(job)
        member = result.get("oracle_opinion") or {}
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIsNot(member.get("repaired"), True)
        self.assertNotIn("yes-2", result.get("stdout", ""))


if __name__ == "__main__":
    unittest.main()
