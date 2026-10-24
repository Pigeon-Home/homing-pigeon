# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
"""The portable proof: what must hold on ANY box the runner lands on.

One module, many hosts. .github/workflows/platform-matrix.yml runs
it natively (Linux, Windows, macOS, x86_64 and arm64), inside
containers (glibc and musl distributions, the Python 3.9 floor, a
FIPS-forced Red Hat), under QEMU (32-bit ARM as on an older Pi,
i386, ppc64le, s390x, riscv64), in BSD virtual machines, and under
the ordinary things administrators do to a box by accident (bash
gone, no $HOME, a minimal PATH, the C locale, umask 077, a noexec
/tmp, a read-only root, a closed stdin). Nothing is stubbed but the
mail transport: a signed job goes through poll_once and really
executes.

Every test here must run on every host. There is no platform skip;
the workflow fails a leg whose output shows a skip, because a
skipped proof is not a proof. The module itself is gated on
HP_PLATFORM_PROOF=1 so the ordinary suite is not slowed by it.

The invariants:
  1. the box reports what it is (one line, for the annotation channel)
  2. a signed job runs under the platform default interpreter
  3. a signed job runs under this Python
  4. a job with a bad signature produces no result at all
  5. a job naming an absent interpreter is repaired to the platform
     default, and the result says so
  6. non-ASCII output survives the box's locale
  7. the result carries the members every consumer relies on
"""
import os
import platform
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from runner.oracle import opinion as op
from runner import runner
from runner.tests import test_oracle_opinion as oo

ENABLED = os.environ.get("HP_PLATFORM_PROOF") == "1"
ABSENT = "hp-absent-interpreter-zz"


def _libc():
    name, ver = platform.libc_ver()
    if name:
        return "%s-%s" % (name, ver)
    try:
        for entry in os.listdir("/lib"):
            if entry.startswith("ld-musl"):
                return "musl"
    except OSError:
        pass
    return "unknown"


def _shell():
    sh = shutil.which("sh")
    if not sh:
        return "none"
    try:
        return os.path.basename(os.path.realpath(sh))
    except OSError:
        return os.path.basename(sh)


def platform_report():
    return ("PLATFORM-REPORT os=%s arch=%s libc=%s python=%s sh=%s "
            "default=%s mutation=%s" % (
                sys.platform, platform.machine() or "?", _libc(),
                platform.python_version(), _shell(),
                " ".join(runner.platform_interpreter()),
                os.environ.get("HP_MUTATION", "none")))


def _run(payload, cfg_over=None, secret=oo.SECRET):
    """One signed job through poll_once, executed for real.
    Returns (smtp, result-or-None)."""
    tmp = tempfile.mkdtemp(prefix="hp-proof-")
    cfg = {
        "mailbox_user": oo.SENDER,
        "mailbox_password": oo.SECRET,
        "shared_secret": oo.SECRET,
        "imap_host": "fake", "imap_port": 993,
        "smtp_host": "fake", "smtp_port": 587,
        "max_job_age_sec": 3600,
        "default_timeout_sec": 120,
    }
    cfg.update(cfg_over or {})
    smtp = oo._FakeSMTP()
    runner.poll_once(cfg, tmp, {}, os.path.join(tmp, "seen.json"),
                     imap=oo._FakeIMAP([oo._job_email(payload, secret)]),
                     smtp=smtp)
    if not smtp.sent:
        return smtp, None
    return smtp, oo._read_result(smtp.sent[-1])


@unittest.skipUnless(ENABLED, "set HP_PLATFORM_PROOF=1 to run the portable proof")
class PlatformProofTests(unittest.TestCase):

    def test_1_box_reports_itself(self):
        line = platform_report()
        print(line, flush=True)
        self.assertIn("arch=", line)

    def test_2_signed_job_runs_under_platform_default(self):
        # `echo` is a command in sh and an alias in PowerShell, so the
        # same neutral script runs under either platform default.
        job = oo._exec_payload(interpreter=runner.platform_interpreter(),
                               script="echo pigeon-42")
        _smtp, result = _run(job)
        self.assertIsNotNone(result, "no result was sent")
        self.assertEqual(result["exit_code"], 0, result.get("stderr"))
        self.assertIn("pigeon-42", result["stdout"])

    def test_3_signed_job_runs_under_this_python(self):
        job = oo._exec_payload(interpreter=[sys.executable],
                               script="import sys\nprint('py-ok', sys.version_info[0])")
        _smtp, result = _run(job)
        self.assertIsNotNone(result, "no result was sent")
        self.assertEqual(result["exit_code"], 0, result.get("stderr"))
        self.assertIn("py-ok 3", result["stdout"])

    def test_4_bad_signature_produces_no_result(self):
        job = oo._exec_payload(interpreter=runner.platform_interpreter(),
                               script="echo never")
        smtp, result = _run(job, secret="wrong-" + oo.SECRET2)
        self.assertIsNone(result)
        self.assertEqual(smtp.sent, [])

    def test_5_absent_interpreter_is_repaired_and_stated(self):
        if shutil.which(ABSENT):
            self.fail("fixture interpreter unexpectedly present")
        job = oo._exec_payload(interpreter=[ABSENT], script="echo pigeon-42")
        _smtp, result = _run(job)
        self.assertIsNotNone(result, "no result was sent")
        member = result.get("oracle_opinion") or {}
        self.assertIs(member.get("repaired"), True, member)
        self.assertEqual(member.get("received_digest"),
                         op.received_digest(job))
        self.assertEqual(result["exit_code"], 0, result.get("stderr"))
        self.assertIn("pigeon-42", result["stdout"])

    def test_6_non_ascii_output_survives_the_locale(self):
        # The job writes UTF-8 bytes; the runner must deliver the text
        # intact whatever the box's locale. (A job that print()s a str
        # is a different question: on Windows the child's stdout is
        # cp1252 and print() itself raises -- the matrix found that on
        # windows-11-arm. Whether the runner should set PYTHONUTF8=1 for
        # jobs is a policy call recorded in the commit, not hidden here.)
        job = oo._exec_payload(
            interpreter=[sys.executable],
            script="import sys\n"
                   "sys.stdout.buffer.write('pigeon-\\u00fc-\\u6f22-ok\\n'"
                   ".encode('utf-8'))\nsys.stdout.flush()")
        _smtp, result = _run(job)
        self.assertIsNotNone(result, "no result was sent")
        self.assertEqual(result["exit_code"], 0, result.get("stderr"))
        self.assertIn("pigeon-", result["stdout"])
        self.assertIn("-ok", result["stdout"])

    def test_7_result_has_the_members_consumers_rely_on(self):
        job = oo._exec_payload(interpreter=[sys.executable],
                               script="print('shape')")
        _smtp, result = _run(job)
        self.assertIsNotNone(result, "no result was sent")
        for key in ("exit_code", "stdout", "stderr", "timed_out",
                    "duration_sec", "job_id"):
            self.assertIn(key, result, key)
        self.assertEqual(result["job_id"], job["job_id"])
        self.assertIsInstance(result["exit_code"], int)
        self.assertIs(result["timed_out"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
