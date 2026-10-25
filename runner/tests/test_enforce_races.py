#!/usr/bin/env python3
"""Queue R: races on the enforce path (roster R1 to R4).

Each race is driven with real threads and a barrier (never a
mock of time), run repeatedly where the window is narrow, and
asserts the SECURITY outcome -- not merely that nothing
crashed (test_concurrency_poison.py already covers the
crash-free half and is the rig pattern):

R1  two jobs at once under enforce (workers: 2): each workdir
    is chowned to the job user and holds only its own job's
    files; two sandboxes do not share /work, and the audit
    log holds both jobs' sandboxed decisions, each whole.
R2  a rollover of security-audit.jsonl (_enforce_bound) while
    a decision is being written: no entry lost, none split.
R3  a replayed job id and a fresh job hitting the seen set
    together: the replay is rejected on both orderings, and
    two copies of a fresh job still run it exactly once.
R4  a config.json write during a job, from a second thread
    while the job is provably in flight: the running job's
    security block does not change, the hot keys do move
    (the reload really ran), and the next job is still
    decided by the settings in force at ITS start -- a mode
    flipped in the file mid-flight denies nothing less.
"""
import json
import os
import secrets
import sys
import tempfile
import threading
import time
import unittest
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

try:
    import pwd
except ImportError:  # Windows has no pwd
    pwd = None

from runner.guard import sandbox as SB  # noqa: E402
from runner.guard import security as S  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402
from runner import runner as RR  # noqa: E402
from runner.runner import execute_job, poll_once, sign_payload  # noqa: E402

SECRET = secrets.token_hex(32)
ENGAGES = SB.startup_problem() is None
IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
HAS_TEST_USER = False
if pwd is not None:
    try:
        pwd.getpwnam("pigeon-test")
        HAS_TEST_USER = True
    except KeyError:
        HAS_TEST_USER = False


def _job(jid, script):
    return {"v": 1, "type": "job", "job_id": jid,
            "issued_at": "2026-10-15T12:00:00Z", "kind": "exec",
            "interpreter": ["python3"], "script": script}


def _audit_rows(base):
    rows = []
    path = os.path.join(base, S.AUDIT_FILE)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


class AuditRolloverRaceTest(unittest.TestCase):
    """R2: two writers race a nearly-full audit log. The bound
    rolls the file by rename; appends are single writes under
    O_APPEND. The outcome pinned: across the live file and
    the rolled one, every entry survives exactly once and
    every line parses -- a split line fails json.loads here.
    """

    ROUNDS = 25

    def test_rollover_never_loses_or_splits_an_entry(self):
        cfg = {"security": {"audit_max_lines": 10}}
        for _round in range(self.ROUNDS):
            base = tempfile.mkdtemp(prefix="hp-r2-")
            for i in range(9):
                S.write_audit_entry(base, "policy_env", "denied",
                                    "seed", job_id="seed-%d" % i,
                                    cfg=cfg)
            barrier = threading.Barrier(2)

            def write(jid):
                barrier.wait(timeout=10)
                S.write_audit_entry(base, "policy_env", "denied",
                                    "race", job_id=jid, cfg=cfg)

            threads = [threading.Thread(target=write, args=(jid,))
                       for jid in ("race-a", "race-b")]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
            ids = []
            for name in (S.AUDIT_FILE, S.AUDIT_ROLLED_FILE):
                path = os.path.join(base, name)
                if not os.path.exists(path):
                    continue
                with open(path, encoding="utf-8") as fh:
                    for line in fh:
                        if not line.strip():
                            continue
                        try:
                            ids.append(json.loads(line)["job_id"])
                        except ValueError:
                            self.fail("split audit line: %r" % line)
            want = ["seed-%d" % i for i in range(9)] + \
                ["race-a", "race-b"]
            self.assertEqual(sorted(ids), sorted(want),
                             "round %d" % _round)


class _IMAP:
    def __init__(self, raws):
        self.raws = list(raws)

    def search(self, *args):
        nums = " ".join(str(i + 1) for i in range(len(self.raws)))
        return "OK", [nums.encode()]

    def fetch(self, num, _what):
        idx = int(num) - 1
        return "OK", [(("%s (RFC822)" % num).encode(), self.raws[idx])]

    def store(self, *args, **kwargs):
        return "OK", []


class _SMTP:
    def sendmail(self, *args, **kwargs):
        return {}


class _Opts:
    dry_run = False
    no_send = True
    workers = 2


def _mail(jid):
    body = sign_payload(
        {"v": 1, "type": "job", "job_id": jid,
         "issued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                    time.gmtime()),
         "kind": "exec", "script": "echo zzzz >> count.txt"},
        SECRET)
    wire = jobcrypto.encrypt_body(body, SECRET, job_id=jid,
                                  key_id="", sign=sign_payload)
    msg = EmailMessage()
    msg["Subject"] = "[HOMING-PIGEON] job %s" % jid
    msg["From"] = "si@example.com"
    msg.set_content(wire)
    return msg.as_bytes()


class SeenSetRaceTest(unittest.TestCase):
    """R3: the seen-set claim is atomic (the mail lock, the
    in-flight set, the on-disk claim). A replayed id is
    rejected however the fresh job is ordered around it,
    and two copies of one fresh job execute it once.
    Executions are counted by the job's own appends in its
    workdir (four z's per run, in any shell's encoding).
    """

    def _executions(self, base, jid):
        path = os.path.join(base, "work", jid, "count.txt")
        if not os.path.exists(path):
            return 0
        with open(path, "rb") as fh:
            return fh.read().count(b"z") // 4

    def _poll(self, base, seen, jids):
        cfg = {"mailbox_user": "pigeon-test@example.com",
               "shared_secret": SECRET, "workers": 2}
        seen_path = os.path.join(base, "seen.json")
        poll_once(cfg, base, seen, seen_path,
                  imap=_IMAP([_mail(j) for j in jids]),
                  smtp=_SMTP(), opts=_Opts())

    def test_a_replay_is_rejected_on_both_orderings(self):
        for jids in (("job-x", "job-x", "job-y"),
                     ("job-y", "job-x", "job-x")):
            base = tempfile.mkdtemp(prefix="hp-r3-")
            seen = {"job-x": time.time()}
            with open(os.path.join(base, "seen.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(seen, fh)
            self._poll(base, seen, jids)
            self.assertEqual(self._executions(base, "job-x"), 0,
                             jids)
            self.assertEqual(self._executions(base, "job-y"), 1,
                             jids)
            self.assertIn("job-y", seen)

    def test_two_copies_of_a_fresh_job_run_it_once(self):
        base = tempfile.mkdtemp(prefix="hp-r3-")
        seen = {}
        self._poll(base, seen, ("job-z", "job-z", "job-y"))
        self.assertEqual(self._executions(base, "job-z"), 1)
        self.assertEqual(self._executions(base, "job-y"), 1)


class ConfigWriteRaceTest(unittest.TestCase):
    """R4: the writer thread flips the security mode in
    config.json and runs the real hot reload while job A is
    provably in flight (its started file exists, its end
    file does not). The reload moves the hot key and leaves
    the security block the identical object; the next job's
    gate still denies by the mode in force.
    """

    def test_a_config_write_during_a_job_changes_no_security(self):
        base = tempfile.mkdtemp(prefix="hp-r4-")
        cfg_path = os.path.join(base, "config.json")
        security = {"modes": {"policy_env": "enforce"}}
        cfg = {"base_dir": base, "poll_interval_sec": 20,
               "security": security}
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump({"poll_interval_sec": 20,
                       "security": {"modes": {"policy_env":
                                              "enforce"}}}, fh)
        state = {}
        RR.reload_hot_config(cfg, cfg_path, state)
        started = os.path.join(base, "started.txt")
        script = (
            "import time\n"
            "open(%r, 'w').write('go')\n"
            "time.sleep(2.0)\n"
            "print('a-done')\n" % started)
        outcome = {}

        def run_a():
            outcome["result"] = execute_job(
                cfg, _job("r4-a", script), base)

        thread = threading.Thread(target=run_a)
        thread.start()
        deadline = time.time() + 15
        while not os.path.exists(started):
            self.assertLess(time.time(), deadline,
                            "job A never started")
            time.sleep(0.05)
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump({"poll_interval_sec": 5,
                       "security": {"modes": {"policy_env":
                                              "off"}}}, fh)
        bumped = time.time() + 5
        os.utime(cfg_path, (bumped, bumped))
        changed = RR.reload_hot_config(cfg, cfg_path, state)
        self.assertTrue(thread.is_alive(),
                        "the reload did not land mid-flight")
        thread.join(timeout=30)
        self.assertEqual(outcome["result"]["exit_code"], 0,
                         outcome["result"])
        # The reload really ran: the hot key moved.
        self.assertEqual(changed, ["poll_interval_sec"])
        self.assertEqual(cfg["poll_interval_sec"], 5)
        # The security block did not move with it.
        self.assertIs(cfg["security"], security)
        self.assertEqual(S.sec_mode(cfg, "policy_env"), "enforce")
        # And the next job is decided by the mode in force:
        # the same gate composition the intake path runs.
        job_b = {"v": 1, "type": "job", "job_id": "r4-b",
                 "kind": "exec", "script": "echo hi",
                 "env": {"EVIL_VAR": "x"}}
        policy = {"allowed_kinds": ["exec"],
                  "denied_env": ["EVIL_VAR"]}
        findings = RR.check_policy_constraints(policy, "k2", cfg,
                                               job_b)
        self.assertTrue(findings)
        for feature, reason, detail in findings:
            allowed = S.sec_decide(
                cfg, base, feature, reason,
                {"key_id": "k2", "job_id": "r4-b",
                 "detail": detail})
            self.assertFalse(allowed)
        denied = [a for a in _audit_rows(base)
                  if a.get("job_id") == "r4-b"
                  and a.get("decision") == "denied"]
        self.assertTrue(denied)


class TwoJobsRaceTest(unittest.TestCase):
    """R1: two jobs at once under enforce, started on one
    barrier, sharing one base dir (the runner's workers: 2
    shape)."""

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
    def test_two_jobs_each_workdir_chowned_to_its_own_job(self):
        base = tempfile.mkdtemp(prefix="hp-r1-")
        cfg = {"base_dir": base,
               "security": {"modes": {"job_user": "enforce"},
                            "job_user": {"user": "pigeon-test"}}}
        scripts = {
            "r1-a": "open('token-a.txt', 'w').write('a')\n"
                    "import os\nprint('uid:', os.getuid())",
            "r1-b": "open('token-b.txt', 'w').write('b')\n"
                    "import os\nprint('uid:', os.getuid())",
        }
        results = self._race_pair(cfg, base, scripts)
        pw = pwd.getpwnam("pigeon-test")
        for jid, token, other in (("r1-a", "token-a.txt",
                                   "token-b.txt"),
                                  ("r1-b", "token-b.txt",
                                   "token-a.txt")):
            result = results[jid]
            self.assertEqual(result["exit_code"], 0,
                             result.get("stderr"))
            self.assertIn("uid: %d" % pw.pw_uid, result["stdout"])
            workdir = os.path.join(base, "work", jid)
            self.assertEqual(os.stat(workdir).st_uid, pw.pw_uid,
                             jid)
            names = os.listdir(workdir)
            self.assertIn(token, names, jid)
            self.assertNotIn(other, names, jid)

    @unittest.skipUnless(ENGAGES,
                         "sandbox cannot engage on this machine "
                         "(startup probe)")
    def test_two_sandboxes_do_not_share_work(self):
        base = tempfile.mkdtemp(prefix="hp-r1-")
        cfg = {"base_dir": base,
               "security": {"modes": {"confinement": "enforce"}}}
        scripts = {}
        for jid, token in (("r1-sa", "token-a"), ("r1-sb", "token-b")):
            other = "r1-sb" if jid == "r1-sa" else "r1-sa"
            scripts[jid] = (
                "import os, time\n"
                "open('/work/token.txt', 'w').write(%r)\n"
                "time.sleep(0.5)\n"
                "print('mine:', open('/work/token.txt').read())\n"
                "try:\n"
                "    open(%r).read()\n"
                "    print('other: reached')\n"
                "except Exception:\n"
                "    print('other: blocked')\n"
                % (token, os.path.join(base, "work", other,
                                       "token.txt")))
        results = self._race_pair(cfg, base, scripts)
        for jid, token in (("r1-sa", "token-a"), ("r1-sb", "token-b")):
            result = results[jid]
            self.assertEqual(result["exit_code"], 0,
                             result.get("stderr"))
            self.assertIn("mine: %s" % token, result["stdout"])
            self.assertIn("other: blocked", result["stdout"])
        rows = _audit_rows(base)
        sandboxed = [a for a in rows
                     if a.get("decision") == "sandboxed"]
        self.assertEqual(len(sandboxed), 2, rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)
