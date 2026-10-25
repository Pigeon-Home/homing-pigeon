#!/usr/bin/env python3
"""Q13: remediation acting on a real job, end to end.

test_remediation covers the decider and test_runner_seams the
close-out with fake monitors. What never ran until now is the
whole path at once: a real job through execute_job whose
produced artifact trips a tripwire, the monitor's kill, the
quarantine, and the records -- the design doc's "as built"
promises (docs/design/remediation-design.md):

  - a tripwire kill takes the whole tree, children included;
  - a job that exits before the kill lands is recorded as
    quarantined, never as killed;
  - the result member and the audit entry say what acted and
    why;
  - with the mode off, the same job is recorded and paged
    only, and runs to completion.

The tripwire used here is the credential artifact: the job
writes a file referencing a credential store its script never
named. The script builds the path by concatenation so the
literal never appears in the script text -- a path the script
itself names is declared, by design, and cannot trip.
"""
import json
import os
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as _runner  # noqa: E402
from runner.runner import JobRejected, execute_job  # noqa: E402

POSIX = os.name != "nt"

TRIP = "p = '~/.a' + 'ws/cred' + 'entials'"


def _job(jid, script, timeout=60):
    return {"v": 1, "type": "job", "job_id": jid,
            "issued_at": "2026-10-15T12:00:00Z",
            "kind": "exec", "interpreter": [sys.executable],
            "script": script, "timeout_sec": timeout}


def _write_loot(extra=(), after=""):
    lines = [TRIP,
             "with open('loot.txt', 'w') as f:",
             "    f.write('loot: ' + p)"]
    lines.extend(extra)
    if after:
        lines.append(after)
    return chr(10).join(lines) + chr(10)


class RemediationEndToEnd(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-q13-")
        self.cfg = {"base_dir": self.base,
                    "remediation_sample_sec": 0.2}

    def _audit(self):
        path = os.path.join(self.base, "security-audit.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def _events(self):
        path = os.path.join(self.base, "security-events.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def _quarantine(self, jid):
        return os.path.join(self.base, "quarantine", jid)

    @unittest.skipUnless(POSIX, "POSIX only")
    def test_tripwire_kills_and_quarantines(self):
        script = _write_loot(after=chr(10).join(
            ["import time", "time.sleep(30)",
             "print('should not reach')"]))
        t0 = time.monotonic()
        result = execute_job(self.cfg, _job("q13-kill", script),
                             self.base)
        duration = time.monotonic() - t0
        self.assertLess(duration, 15)
        self.assertEqual(result["exit_code"], -9)
        self.assertNotIn("should not reach", result["stdout"])
        member = result.get("remediation")
        self.assertIsNotNone(member, result)
        self.assertEqual(member["mode"], "deterministic")
        self.assertEqual(member["authority"], "tripwire")
        self.assertEqual(member["act"], "killed")
        self.assertIn("credential_artifact", member["divergence"])
        qdir = self._quarantine("q13-kill")
        self.assertTrue(os.path.exists(
            os.path.join(qdir, "remediation.json")))
        self.assertTrue(os.path.exists(
            os.path.join(qdir, "work", "loot.txt")))
        acted = [e for e in self._audit()
                 if e.get("feature") == "remediation"
                 and e.get("decision") == "acted"]
        self.assertEqual(len(acted), 1, self._audit())
        self.assertIn("act=killed", acted[0]["detail"])
        events = [e for e in self._events()
                  if e.get("type") == "remediation"
                  and e.get("job_id") == "q13-kill"]
        self.assertEqual(len(events), 1, self._events())
        self.assertEqual(events[0]["act"], "killed")

    @unittest.skipUnless(POSIX, "POSIX only")
    def test_tree_kill_takes_the_child_too(self):
        child = (
            "import subprocess, sys\n"
            "c = subprocess.Popen([sys.executable, '-c',\n"
            "    'import os, time;'\n"
            "    ' open(\"child.pid\", \"w\").write(str(os.getpid()));'\n"
            "    ' time.sleep(60)'])\n")
        script = _write_loot(extra=[child.rstrip("\n")],
                             after=chr(10).join(
                                 ["import time", "time.sleep(30)"]))
        result = execute_job(self.cfg, _job("q13-tree", script),
                             self.base)
        self.assertEqual(result["remediation"]["act"], "killed")
        pid_path = os.path.join(self._quarantine("q13-tree"),
                                "work", "child.pid")
        with open(pid_path, encoding="utf-8") as fh:
            child_pid = int(fh.read().strip())
        deadline = time.monotonic() + 5
        while True:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            if time.monotonic() > deadline:
                self.fail("child %d survived the tree kill"
                          % child_pid)
            time.sleep(0.1)

    @unittest.skipUnless(POSIX, "POSIX only")
    def test_sigterm_ignorer_is_killed_anyway(self):
        script = _write_loot(extra=[
            "import signal",
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)",
        ], after=chr(10).join(["import time", "time.sleep(30)"]))
        t0 = time.monotonic()
        result = execute_job(self.cfg, _job("q13-ign", script),
                             self.base)
        self.assertLess(time.monotonic() - t0, 15)
        self.assertEqual(result["exit_code"], -9)
        self.assertEqual(result["remediation"]["act"], "killed")

    @unittest.skipUnless(POSIX, "POSIX only")
    def test_job_that_exits_first_is_quarantined_not_killed(self):
        # The docstring's honesty case: the final scan finds
        # the tripwire after the job has already exited on its
        # own; the recorded act is the quarantine, never a kill
        # that did not land.
        script = _write_loot(after="print('done and gone')")
        result = execute_job(self.cfg, _job("q13-race", script),
                             self.base)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("done and gone", result["stdout"])
        member = result.get("remediation")
        self.assertIsNotNone(member, result)
        self.assertEqual(member["act"], "quarantined")
        self.assertEqual(member["authority"], "tripwire")
        self.assertTrue(os.path.exists(os.path.join(
            self._quarantine("q13-race"), "remediation.json")))

    def test_clean_job_has_no_remediation_member(self):
        result = execute_job(self.cfg, _job(
            "q13-clean", "print('all good')"), self.base)
        self.assertEqual(result["exit_code"], 0)
        self.assertNotIn("remediation", result)
        self.assertFalse(os.path.exists(
            os.path.join(self.base, "quarantine")))

    def test_mode_off_records_and_pages_only(self):
        cfg = dict(self.cfg, remediation_mode="off")
        script = _write_loot(after=chr(10).join([
            "import time", "time.sleep(1)",
            "print('ran to completion')"]))
        result = execute_job(cfg, _job("q13-off", script),
                             self.base)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("ran to completion", result["stdout"])
        self.assertNotIn("remediation", result)
        self.assertFalse(os.path.exists(
            os.path.join(self.base, "quarantine")))
        observed = [e for e in self._audit()
                    if e.get("feature") == "remediation"
                    and e.get("decision") == "observed"]
        self.assertEqual(len(observed), 1, self._audit())


class ExecuteJobFallbacksTest(unittest.TestCase):
    """Queue A refill, runner.execute_job's fallback lines
    (coverage run 40187685363): the remediation watch is an
    observer, never a dependency -- a monitor that fails to
    start, a monitor whose stop fails, and a close-out that
    raises must each leave the job's own result untouched,
    and a close-out that returns a member gets it attached
    (the attach line had never run on Windows). One line in
    the set is not a fallback: the script-write branch's
    own "script must be a string" raise is unreachable by
    construction, because the input validation above it
    rejects a non-string script first; the contract is
    pinned at that live guard instead.
    """

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-exec-fallback-")
        self.cfg = {"base_dir": self.base}
        self.job = _job("exec-fallback", "print('job ran')")

    def test_a_non_string_script_is_rejected(self):
        job = dict(self.job, script=12345)
        with self.assertRaises(JobRejected) as cm:
            execute_job(self.cfg, job, self.base)
        self.assertEqual(str(cm.exception),
                         "script must be a string")

    def test_a_monitor_that_fails_to_start_changes_nothing(self):
        with mock.patch.object(
                _runner, "_start_job_monitor",
                side_effect=RuntimeError("monitor down")):
            result = execute_job(self.cfg, self.job, self.base)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("job ran", result["stdout"])
        self.assertNotIn("remediation", result)

    def test_a_monitor_whose_stop_fails_changes_nothing(self):
        def bad_stop():
            raise RuntimeError("stop failed")

        monitor = types.SimpleNamespace(stop=bad_stop)
        with mock.patch.object(
                _runner, "_start_job_monitor",
                return_value=monitor), \
                mock.patch.object(
                _runner, "_finish_remediation",
                return_value=None):
            result = execute_job(self.cfg, self.job, self.base)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("job ran", result["stdout"])
        self.assertNotIn("remediation", result)

    def test_a_close_out_that_raises_attaches_nothing(self):
        monitor = types.SimpleNamespace(stop=lambda: None)
        with mock.patch.object(
                _runner, "_start_job_monitor",
                return_value=monitor), \
                mock.patch.object(
                _runner, "_finish_remediation",
                side_effect=RuntimeError("close-out down")):
            result = execute_job(self.cfg, self.job, self.base)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("job ran", result["stdout"])
        self.assertNotIn("remediation", result)

    def test_a_close_out_member_is_attached(self):
        monitor = types.SimpleNamespace(stop=lambda: None)
        member = {"outcome": "held_for_review"}
        with mock.patch.object(
                _runner, "_start_job_monitor",
                return_value=monitor), \
                mock.patch.object(
                _runner, "_finish_remediation",
                return_value=member):
            result = execute_job(self.cfg, self.job, self.base)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["remediation"], member)


if __name__ == "__main__":
    unittest.main(verbosity=2)
