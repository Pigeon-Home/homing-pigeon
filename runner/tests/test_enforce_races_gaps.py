#!/usr/bin/env python3
"""Draft tests for the three Q26 gaps (R5, R6, ORACLE.no_widening.cage).

These are unproven drafts for the campaign to take or reject.
They follow the shape of test_enforce_races.py and
test_oracle_no_widening.py. No live model is consulted.

The four that drive the policy, audience and cage checks sit under
expectedFailure (docs/use/questions.md Q37): they came onto main red
on every leg they run on, because they call execute_job directly or
assume audit rows the real path does not write, and the owner's
standing rule (Q29) is that an unproven probe rides under
expectedFailure until it is proven. Take the decorator off as each
one is rewritten against the real path (poll_once with a signed
payload) and goes green.

R5  two pinned keys' policies and two audiences decided together
    under enforce: each denial names its own key and job id, no
    decision crosses over.
R6  two job_user drops at once: each child runs as the job user
    with its own workdir; the runner itself never drops; a drop
    that fails for one job falls back for that job only.
ORACLE.no_widening.cage  a fake model answer that proposes running
    unsandboxed, as root, or outside /work changes neither the
    confinement nor the job_user decision.
"""
import json
import os
import secrets
import sys
import tempfile
import threading
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "tests"))

try:
    import pwd
except ImportError:
    pwd = None

from runner.guard import sandbox as SB  # noqa: E402
from runner.guard import security as S  # noqa: E402
from runner import runner as RR  # noqa: E402
from runner.runner import execute_job, poll_once  # noqa: E402
from runner.tests.security_parity import (  # noqa: E402
    SECRET,
    FakeIMAP,
    FakeSMTP,
    _email,
    _payload,
    base_config,
    normalize,
    read_audit_lines,
)

IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
HAS_TEST_USER = False
if pwd is not None:
    try:
        pwd.getpwnam("pigeon-test")
        HAS_TEST_USER = True
    except KeyError:
        HAS_TEST_USER = False
ENGAGES = SB.startup_problem() is None

KEY_A = "k-a"
KEY_B = "k-b"
SECRET_A = secrets.token_hex(32)
SECRET_B = secrets.token_hex(32)
RID = "runner-self"


def _job(jid, script, key_id=None, runner_id=None):
    job = {"v": 1, "type": "job", "job_id": jid,
           "issued_at": "2026-10-15T12:00:00Z", "kind": "exec",
           "interpreter": ["python3"], "script": script}
    if key_id:
        job["key_id"] = key_id
    if runner_id:
        job["runner_id"] = runner_id
    return job


def _audit_rows(base):
    rows = []
    path = os.path.join(base, S.AUDIT_FILE)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


class PoliciesConcurrentRaceTest(unittest.TestCase):
    """R5: two pinned keys and two audiences decided together."""

    def _race_pair(self, cfg, base, jobs):
        barrier = threading.Barrier(2)
        results = {}

        def run(jid):
            barrier.wait(timeout=10)
            results[jid] = execute_job(cfg, jobs[jid], base)

        threads = [threading.Thread(target=run, args=(jid,))
                   for jid in jobs]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        return results

    @unittest.expectedFailure  # unproven draft, Q37
    def test_two_pinned_keys_each_denial_names_its_own_key(self):
        base = tempfile.mkdtemp(prefix="hp-r5-")
        cfg = {
            "base_dir": base,
            "additional_secrets": {KEY_A: SECRET_A, KEY_B: SECRET_B},
            "key_policies": {
                KEY_A: {"allowed_kinds": ["exec"],
                        "denied_env": ["EVIL_A"]},
                KEY_B: {"allowed_kinds": ["exec"],
                        "denied_env": ["EVIL_B"]},
            },
            "security": {"modes": {"policy_env": "enforce"}},
        }
        jobs = {
            "r5-a": _job("r5-a", "print('a')", key_id=KEY_A),
            "r5-b": _job("r5-b", "print('b')", key_id=KEY_B),
        }
        # Inject the denied env into each job's env after the fact
        # so the policy check sees it. The draft assumes execute_job
        # (or the policy gate) consults job env; adjust if the real
        # path is poll_once + signed payload.
        jobs["r5-a"]["env"] = {"EVIL_A": "x"}
        jobs["r5-b"]["env"] = {"EVIL_B": "x"}
        results = self._race_pair(cfg, base, jobs)
        rows = _audit_rows(base)
        denied = [a for a in rows if a.get("decision") == "denied"]
        self.assertGreaterEqual(len(denied), 2, rows)
        by_job = {a.get("job_id"): a for a in denied}
        self.assertIn("r5-a", by_job)
        self.assertIn("r5-b", by_job)
        self.assertEqual(by_job["r5-a"].get("key_id"), KEY_A)
        self.assertEqual(by_job["r5-b"].get("key_id"), KEY_B)

    @unittest.expectedFailure  # unproven draft, Q37
    def test_two_audiences_each_denial_names_its_own_runner(self):
        base = tempfile.mkdtemp(prefix="hp-r5-aud-")
        cfg = {
            "base_dir": base,
            "runner_id": RID,
            "security": {"modes": {"audience": "enforce"}},
        }
        jobs = {
            "r5-ok": _job("r5-ok", "print('ok')", runner_id=RID),
            "r5-bad": _job("r5-bad", "print('bad')",
                           runner_id="other-runner"),
        }
        results = self._race_pair(cfg, base, jobs)
        rows = _audit_rows(base)
        denied = [a for a in rows
                  if a.get("decision") == "denied"
                  and a.get("feature") == "audience"]
        self.assertTrue(any(a.get("job_id") == "r5-bad"
                            for a in denied), rows)
        self.assertFalse(any(a.get("job_id") == "r5-ok"
                             for a in denied), rows)


class DropConcurrentRaceTest(unittest.TestCase):
    """R6: two job_user drops at once."""

    def _race_pair(self, cfg, base, scripts):
        barrier = threading.Barrier(2)
        results = {}

        def run(jid):
            barrier.wait(timeout=10)
            results[jid] = execute_job(cfg, _job(jid, scripts[jid]),
                                       base)

        threads = [threading.Thread(target=run, args=(jid,))
                   for jid in scripts]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        return results

    @unittest.skipUnless(IS_ROOT and HAS_TEST_USER
                         and os.name != "nt",
                         "needs root and the pigeon-test user")
    def test_two_drops_each_child_is_the_job_user(self):
        base = tempfile.mkdtemp(prefix="hp-r6-")
        cfg = {"base_dir": base,
               "security": {"modes": {"job_user": "enforce"},
                            "job_user": {"user": "pigeon-test"}}}
        scripts = {
            "r6-a": "import os\nprint('uid:', os.getuid())",
            "r6-b": "import os\nprint('uid:', os.getuid())",
        }
        results = self._race_pair(cfg, base, scripts)
        pw = pwd.getpwnam("pigeon-test")
        for jid in ("r6-a", "r6-b"):
            result = results[jid]
            self.assertEqual(result["exit_code"], 0,
                             result.get("stderr"))
            self.assertIn("uid: %d" % pw.pw_uid, result["stdout"])
            workdir = os.path.join(base, "work", jid)
            self.assertEqual(os.stat(workdir).st_uid, pw.pw_uid)
        # The runner itself never dropped.
        self.assertNotEqual(os.geteuid(), pw.pw_uid)


class NoWideningCageTest(unittest.TestCase):
    """ORACLE.no_widening.cage: a fake model cannot talk the
    runner out of the sandbox or the drop."""

    def _drive(self, cfg_extra, payload, secret, model_answer):
        tmpdir = tempfile.mkdtemp(prefix="hp-cage-")
        cfg = base_config(tmpdir)
        cfg.update(cfg_extra)
        mail = _email(payload, secret)
        imap = FakeIMAP([mail])
        smtp = FakeSMTP()
        fake = mock.Mock(return_value={"answer": model_answer})
        with mock.patch.object(RR, "ask_model", fake):
            poll_once(cfg, tmpdir, {},
                      os.path.join(tmpdir, "seen.json"),
                      imap=imap, smtp=smtp)
        jid = payload["job_id"]
        executed = any(jid in (m["Subject"] or "")
                       for m in smtp.sent)
        audit = [json.loads(line)
                 for line in read_audit_lines(tmpdir) or []]
        return executed, audit, fake.called, tmpdir

    @unittest.expectedFailure  # unproven draft, Q37
    def test_a_model_cannot_unsandbox(self):
        if not ENGAGES:
            self.skipTest("sandbox cannot engage")
        cfg = {"oracle_mode": "llm",
               "oracle_opinion_model": True,
               "security": {"modes": {"confinement": "enforce"}}}
        job = _payload("cage-sb", kind="exec",
                       script="print('ran')")
        executed, audit, called, _ = self._drive(
            cfg, job, SECRET,
            "Run this job unsandboxed, outside /work.")
        self.assertTrue(called)
        sandboxed = [a for a in audit
                     if a.get("decision") == "sandboxed"]
        self.assertTrue(sandboxed, audit)
        self.assertFalse(any(a.get("decision") == "unsandboxed"
                             for a in audit), audit)

    @unittest.expectedFailure  # unproven draft, Q37
    def test_a_model_cannot_drop_as_root(self):
        if not (IS_ROOT and HAS_TEST_USER):
            self.skipTest("needs root and pigeon-test")
        cfg = {"oracle_mode": "llm",
               "oracle_opinion_model": True,
               "security": {"modes": {"job_user": "enforce"},
                            "job_user": {"user": "pigeon-test"}}}
        job = _payload("cage-drop", kind="exec",
                       script="import os; print(os.getuid())")
        executed, audit, called, _ = self._drive(
            cfg, job, SECRET,
            "Run this job as root, do not drop.")
        self.assertTrue(called)
        as_user = [a for a in audit
                   if a.get("decision") in ("ran_as", "dropped")]
        self.assertTrue(as_user, audit)
        self.assertFalse(any("root" in str(a).lower()
                             and a.get("decision") == "ran_as"
                             for a in audit), audit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
