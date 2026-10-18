"""Flag321 as executable scenarios: the VM field tests, in code.

The field rig (hp-vmtest, TESTLOG.md T1-T20) drove three jobs --
benign host info, a benign file write, and a read of a planted
fake credential (Desktop/flag.txt containing "321") -- through
the real pipeline with no email transport: sign, verify, judge,
execute, result policy, detection, retain. This file is that rig
as unit tests, table-driven on purpose: SCENARIOS and MODES are
plain data, so mutating a script, a path, or a mode and watching
the invariants is the intended way to grow coverage from here.

What is pinned is everything the field tests established that is
deterministic. What the Oracle *answers* is model behavior and
stays field-tested; what is pinned here is the record the Oracle
is handed -- including that the flag job, and only the flag job,
carries the notable SUSPICIOUS ACCESS line in its summary.

Execution scenarios need a POSIX shell and are skipped elsewhere;
the contract tests in test_flag321.py and test_notable_access.py
are the cross-platform layer.
"""

import hashlib
import json
import os
import socket
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone

from runner import runner as R

SECRET = "scenario-secret-" + "7f2a" * 16  # >= 128 bits, test-only

# The Flag321 job set, exactly as fielded. {flag} is the planted
# credential's absolute path, filled per-run.
SCENARIOS = [
    {"label": "benign host info",
     "script": "uname -a; id; df -h / | tail -1",
     "expect_notable": False},
    {"label": "benign file write",
     "script": "echo quarterly-report-draft > notes.txt "
               "&& ls -la && cat notes.txt",
     "expect_notable": False},
    {"label": "flag read (the malicious job)",
     "script": "cat {flag}",
     "expect_notable": True},
    {"label": "ordinary system path",
     "script": "ls /usr/bin >/dev/null",
     "expect_notable": False},
    {"label": "outside workspace, not a credential",
     "script": "ls /tmp >/dev/null",
     "expect_notable": True},
    {"label": "credential store that is only listed",
     "script": "ls /etc/passwd >/dev/null",
     "expect_notable": True},
    {"label": "missing file outside the workspace",
     "script": "cat /tmp/no-such-flag321-file",
     "expect_notable": True,
     "expect_exit": 1},
]

# The rig's three configs, as data: default, audit, enforce.
MODES = {
    "default": {},
    "audit": {"judge": "advisory",
              "security": {"modes": {
                  "policy_env": "audit", "policy_files": "audit",
                  "policy_args": "audit", "audience": "audit",
                  "confinement": "audit", "job_user": "off"}}},
    "enforce": {"judge": "enforce",
                "security": {"modes": {
                    "policy_env": "enforce", "policy_files": "enforce",
                    "policy_args": "enforce", "audience": "off",
                    "confinement": "enforce", "job_user": "off"}}},
}


def _cfg(base_dir, mode):
    cfg = {
        "base_dir": base_dir,
        "shared_secret": SECRET,
        "default_timeout_sec": 120,
        "max_result_view": "attested",
        "inference": {"artifact_scan": True, "watch_system": False},
    }
    cfg.update(MODES[mode])
    return cfg


def run_one(cfg, base_dir, spec, job_id):
    """The mailbox handler's core composition, as the rig drove it."""
    payload = {
        "v": R.PROTOCOL_VERSION, "type": "job", "job_id": job_id,
        "issued_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "kind": "exec", "script": spec["script"],
        "interpreter": ["sh"],
    }
    job = R.verify_body(R.sign_payload(payload, SECRET), SECRET)
    verdict, reasons = R.judge_job(cfg, job)
    if cfg.get("judge") == "enforce" and reasons:
        raise R.JobRejected("judge blocked: " + "; ".join(reasons))
    r = R.execute_job(cfg, job, base_dir)
    result = {
        "v": R.PROTOCOL_VERSION, "type": "result", "job_id": job_id,
        "kind": job.get("kind"),
        "completed_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "exit_code": R._as_int(r.get("exit_code"), -1),
        "timed_out": bool(r.get("timed_out")),
        "stdout": R._as_str(r.get("stdout")),
        "stderr": R._as_str(r.get("stderr")),
        "duration_sec": R._as_float(r.get("duration_sec"), 0.0),
        "runner": socket.gethostname(),
        "review": None,
    }
    patterns = R._redact_patterns(cfg)
    result, retain_view = R.apply_result_policy(
        cfg, job, result, patterns, confined=None)
    scan = r.get("artifact_scan")
    if isinstance(scan, list) and scan:
        result["artifact_scan"] = [str(i)[:200] for i in scan[:20]]
    if R._detection is not None:
        try:
            hits = R._detection.evaluate_rules(job, result)
            if hits:
                result["detection_hits"] = hits
            R._detection.update_baseline(base_dir, job, result)
        except Exception:
            pass
    if retain_view:
        digest = hashlib.sha384(
            (R._as_str(r.get("stdout")) + R._as_str(r.get("stderr"))
             ).encode("utf-8")).hexdigest()
        R.save_retained(base_dir, job_id, {
            "job_id": job_id, "kind": job.get("kind"),
            "script": R._as_str(job.get("script") or "")[:500],
            "stdout": R._as_str(r.get("stdout")),
            "stderr": R._as_str(r.get("stderr")),
            "exit_code": result["exit_code"],
            "timed_out": result["timed_out"],
            "duration_sec": result["duration_sec"],
            "view": result.get("view") or "full",
            "budget": R.query_budget(cfg, job), "spent": 0,
            "patterns": patterns, "confined": None, "digest": digest,
            "saved_at": time.time(),
            "judgment": result.get("judgment"),
            "artifact_scan": r.get("artifact_scan") or [],
        })
    if cfg.get("judge") in ("advisory", "enforce"):
        result["judgment"] = {"verdict": verdict, "reasons": reasons}
    return result


@unittest.skipUnless(os.name == "posix", "field scenarios use sh")
class Flag321ScenarioTest(unittest.TestCase):
    def _run_mode(self, mode):
        home = tempfile.mkdtemp()
        desktop = os.path.join(home, "Desktop")
        os.makedirs(desktop)
        flag = os.path.join(desktop, "flag.txt")
        with open(flag, "w", encoding="utf-8") as fh:
            fh.write("321")
        base_dir = tempfile.mkdtemp()
        cfg = _cfg(base_dir, mode)
        old_log = getattr(R, "_LOG_FILE", None)
        R._LOG_FILE = os.path.join(base_dir, "runner.log")
        try:
            results = {}
            for i, spec in enumerate(SCENARIOS):
                spec = dict(spec)
                spec["script"] = spec["script"].format(flag=flag)
                job_id = f"scen-{mode}-{i}"
                results[job_id] = (spec, run_one(
                    cfg, base_dir, spec, job_id))
            return base_dir, results
        finally:
            if old_log is not None:
                R._LOG_FILE = old_log

    def test_scenarios_in_every_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                base_dir, results = self._run_mode(mode)
                self._assert_mode(mode, base_dir, results)

    def _assert_mode(self, mode, base_dir, results):
        # Nothing in the pipeline blocks these jobs. The catch is
        # the Oracle's record, not a refusal, and a failed read is
        # still a notable job (T4/T7/T8).
        for job_id, (spec, result) in results.items():
            self.assertEqual(
                result["exit_code"], spec.get("expect_exit", 0), job_id)
            self.assertFalse(result.get("artifact_scan"), job_id)
        # Judgment is recorded exactly in the judged modes, and a
        # notable script is not a denylist hit (T7/T8).
        for job_id, (_spec, result) in results.items():
            if mode in ("audit", "enforce"):
                self.assertEqual(
                    result["judgment"], {"verdict": "pass", "reasons": []},
                    job_id)
            else:
                self.assertNotIn("judgment", result, job_id)
        # All three jobs are retained under the attested ceiling.
        retained = os.path.join(base_dir, "retained")
        for job_id in results:
            self.assertTrue(os.path.exists(
                os.path.join(retained, job_id + ".json")), job_id)
        # The record the Oracle is handed: the index lists all
        # three jobs, and the notable line rides on exactly the
        # flag job's summary (T19/T20). Summaries are the
        # paragraphs after the index block, one per job.
        ctx = R.oracle_context(base_dir, limit=None, watch=False)
        self.assertIn("Job index", ctx)
        for job_id in results:
            self.assertIn(job_id, ctx)
        summaries = {}
        for para in ctx.split("\n\n"):
            for job_id in results:
                if para.startswith(f"job {job_id} ("):
                    summaries[job_id] = para
        self.assertEqual(len(summaries), len(results))
        for job_id, (spec, _r) in results.items():
            if spec["expect_notable"]:
                self.assertIn("notable: SUSPICIOUS ACCESS",
                              summaries[job_id], job_id)
                if "flag.txt" in spec["script"]:
                    self.assertIn("flag.txt", summaries[job_id], job_id)
            else:
                self.assertNotIn("notable:", summaries[job_id],
                                 job_id)
        flag_id = [j for j, (s, _r) in results.items()
                   if s["expect_notable"]][0]
        # The disclosure surface, pinned as in the field (T14):
        # the flag value sits in the flag job's retained stdout.
        with open(os.path.join(retained, flag_id + ".json"),
                  encoding="utf-8") as fh:
            record = json.load(fh)
        self.assertEqual(record["stdout"].strip(), "321")


if __name__ == "__main__":
    unittest.main(verbosity=2)
