#!/usr/bin/env python3
"""The credential-artifact tripwire's declaration harvest.

Found live on the Germany rig (Windows), 1-Nov-2026, scenario
item 0/2: a job whose script wrote a file naming an undeclared
credential-store path -- the probe shape
``Set-Content probe.txt 'reads ~/.ssh/id_rsa at noon'`` --
finished exit 0 with a clean pass result, no kill, no
quarantine, no credential record. The identical shape was
believed killed in the 31-Oct soak; the soak's tally counted
any delivered result as a kill, so it could not tell.

Root cause: the monitor's declared-credential set was
harvested from EVERY credential-shaped token in the script
text, including the string literal the script was about to
write as data. A job could therefore "declare" a credential
path merely by carrying it as data, and the produced artifact
repeating it could never trip. A declaration is a statement
about the job, made where statements to the runner live: the
script's comment lines (the header the sending guide tells
operators to declare paths in). Command text -- strings
included -- is the job's business, not its declaration.

These tests pin the narrowed harvest end to end (a literal
write trips; a comment declaration still covers), pin the
helper's line rules, and pin the scan's second chance: a file
whose scan failed transiently (a locked file on Windows is
the live shape) must be scanned again on the next pass, not
exempted forever by a marker recorded before the read.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as _runner  # noqa: E402
from runner.ops import paths as _paths  # noqa: E402
from runner.oracle import remediation as rem  # noqa: E402

POSIX = os.name != "nt"
CRED = "~/.ssh/id_rsa"
PROBE_WRITE = "printf 'reads ~/.ssh/id_rsa at noon' > probe.txt"


def _declared(script, base_dir=None, job_id="job-t"):
    return _paths._script_declared_credential_paths(
        script, base_dir, job_id)


class DeclaredCredentialPathsTest(unittest.TestCase):
    """The harvest: comment lines declare, command text does not."""

    def test_comment_line_declares(self):
        self.assertEqual(
            _declared("# touches ~/.ssh/id_rsa for the copy\n"
                      "echo hi\n"),
            [CRED])

    def test_indented_comment_line_declares(self):
        self.assertEqual(
            _declared("   # touches ~/.ssh/id_rsa\necho hi\n"),
            [CRED])

    def test_command_string_does_not_declare(self):
        # The live probe shape: the path rides in a string the
        # script writes. Data, not a declaration.
        self.assertEqual(_declared(PROBE_WRITE + "; echo done\n"),
                         [])

    def test_bare_command_reference_does_not_declare(self):
        self.assertEqual(_declared("cat ~/.ssh/id_rsa\n"), [])

    def test_hash_inside_a_string_does_not_declare(self):
        self.assertEqual(
            _declared("printf '# ~/.ssh/id_rsa\\n' > decl.txt\n"),
            [])

    def test_trailing_comment_does_not_declare(self):
        # A declaration is a line of its own (the header);
        # text after a command is not the header.
        self.assertEqual(
            _declared("echo hi # ~/.ssh/id_rsa\n"), [])

    def test_windows_shape_in_comment_declares(self):
        self.assertEqual(
            _declared("# C:\\Users\\u\\.ssh\\id_rsa\n"),
            ["C:\\Users\\u\\.ssh\\id_rsa"])

    def test_non_credential_comment_is_not_returned(self):
        self.assertEqual(
            _declared("# see /etc/hostname and ~/.aws/credentials\n"),
            ["~/.aws/credentials"])

    def test_no_comment_no_declaration(self):
        self.assertEqual(_declared("echo hi\n"), [])
        self.assertEqual(_declared(""), [])
        self.assertEqual(_declared(None), [])


@unittest.skipIf(not POSIX, "execute_job fixtures are POSIX shell")
class TripwireHarvestEndToEnd(unittest.TestCase):
    """The live shapes through execute_job, monitor and all."""

    def _run(self, script, job_id):
        base = tempfile.mkdtemp(prefix="hp-harvest-")
        self.addCleanup(lambda: __import__("shutil").rmtree(
            base, ignore_errors=True))
        cfg = {"base_dir": base, "remediation_sample_sec": 0.1}
        job = {"job_id": job_id, "kind": "exec", "script": script}
        with mock.patch.object(rem, "av_referral",
                               return_value=("clean", "fake scan")):
            return base, _runner.execute_job(cfg, job, base)

    def test_literal_write_of_credential_path_trips(self):
        # The Germany rig probe, POSIX spelling: the script
        # names the path only inside the string it writes.
        _base, r = self._run(PROBE_WRITE + "; echo done", "probe-1")
        member = r.get("remediation")
        self.assertIsNotNone(member, r)
        self.assertEqual(member["authority"], "tripwire")
        self.assertTrue(member["divergence"].startswith(
            "credential_artifact"))

    def test_comment_declared_write_does_not_trip(self):
        # The documented workflow survives: declare the path
        # in a header comment and the produced file may
        # repeat it.
        _base, r = self._run(
            "# declares: ~/.ssh/id_rsa\n" + PROBE_WRITE
            + "; echo done", "probe-2")
        self.assertEqual(r["exit_code"], 0)
        self.assertNotIn("remediation", r)

    def test_hash_in_string_does_not_declare(self):
        _base, r = self._run(
            "printf '# ~/.ssh/id_rsa\\n' > decl.txt; "
            + PROBE_WRITE + "; echo done", "probe-3")
        member = r.get("remediation")
        self.assertIsNotNone(member, r)
        self.assertTrue(member["divergence"].startswith(
            "credential_artifact"))


class ScanRetryTest(unittest.TestCase):
    """A transiently failed scan is retried on the next pass.

    _scan_workdir recorded a file's (size, mtime) marker
    BEFORE _scan_file read it, so any transient failure --
    a locked file (WinError 32 is the live Windows shape),
    a findings parser hiccup -- exempted that exact file
    version from scanning for the rest of the job.
    """

    def _monitor(self, work, findings_fn):
        st = rem.settings({})
        return rem.JobMonitor(
            st, "job-retry", 4242, work,
            findings_fn=findings_fn,
            kill_fn=lambda _extra: None,
            sampler=lambda _pid: {4242: (0.0, None)})

    def _work_with_leak(self):
        work = tempfile.mkdtemp(prefix="hp-retry-")
        self.addCleanup(lambda: __import__("shutil").rmtree(
            work, ignore_errors=True))
        with open(os.path.join(work, "leak.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("payload")
        return work

    def test_findings_failure_is_retried(self):
        calls = {"n": 0}

        def flaky(_text):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("parser hiccup")
            return [(CRED, rem.CREDENTIAL_REASON)]

        mon = self._monitor(self._work_with_leak(), flaky)
        mon.sample_once()
        self.assertIsNone(mon.outcome["acted"])
        mon.sample_once()
        self.assertEqual(calls["n"], 2)
        self.assertIsNotNone(mon.outcome["acted"])
        self.assertEqual(mon.outcome["acted"]["divergence"]
                         ["kind"], "credential_artifact")

    def test_read_failure_is_retried(self):
        real_getsize = os.path.getsize
        state = {"failed": False}

        def getsize(path):
            if not state["failed"]:
                state["failed"] = True
                raise OSError("locked (WinError 32 shape)")
            return real_getsize(path)

        mon = self._monitor(
            self._work_with_leak(),
            lambda _t: [(CRED, rem.CREDENTIAL_REASON)])
        with mock.patch.object(os.path, "getsize",
                               side_effect=getsize):
            mon.sample_once()
            self.assertIsNone(mon.outcome["acted"])
            mon.sample_once()
        self.assertIsNotNone(mon.outcome["acted"])
        self.assertEqual(mon.outcome["acted"]["divergence"]
                         ["kind"], "credential_artifact")

    def test_clean_scan_is_not_repeated(self):
        calls = {"n": 0}

        def clean(_text):
            calls["n"] += 1
            return []

        mon = self._monitor(self._work_with_leak(), clean)
        mon.sample_once()
        mon.sample_once()
        self.assertEqual(calls["n"], 1)


if __name__ == "__main__":
    unittest.main()
