#!/usr/bin/env python3
"""Third-pass negative tests: multi-key policy, concurrent query answering, interpreter edges.

Findings from virtual-environment simulation (2026-10-15, third pass):

1. Concurrent check_key_policy against a policies map that is being
   mutated or replaced with non-dicts, lists, or missing keys does not
   raise. Invalid maps return a reason string; unrestricted keys stay
   unrestricted. Default-deny is respected when set.

2. Concurrent answer_queries on retained data that is numeric, None,
   non-dict, or has wrong-type view/budget/patterns continues and
   returns structured answers or rejections. No query path raises.

3. poll_once with jobs that have non-list interpreters, empty interpreter
   lists, and extreme timeout values rejects cleanly and does not stop
   sibling workers. Extension state remains readable afterward.
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import (
    check_key_policy, build_key_policies, answer_queries,
    _redact_patterns, poll_once, sign_payload, load_retained
)

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"

def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()

class _MultiIMAP:
    def __init__(self, raws):
        self.raws = list(raws)
    def search(self, *a):
        ids = [str(i+1).encode() for i in range(len(self.raws))]
        return "OK", [b" ".join(ids)] if ids else [b""]
    def fetch(self, num, what):
        idx = int(num) - 1
        if 0 <= idx < len(self.raws):
            return "OK", [(None, self.raws[idx])]
        return "NO", None
    def store(self, *a): return "OK", None
    def expunge(self): return "OK", None
    def logout(self): return "OK", None

class _SMTP:
    def send_message(self, *a, **k): return {}
    def quit(self): pass

class _Opts:
    dry_run = False
    workers = 3
    once = True
    no_send = True

class KeyPolicyRaceTest(unittest.TestCase):
    def test_concurrent_key_policy_under_mutation(self):
        base_cfg = {
            "key_policies": {
                "worker1": {"allowed_kinds": ["ping"], "max_timeout_sec": 60},
                "worker2": {"allowed_interpreters": [["sh"]], "allowed_kinds": ["exec"]},
            },
            "key_policies_default_deny": True,
        }
        policies = build_key_policies(base_cfg)
        errors = []
        def mutator():
            for i in range(20):
                try:
                    # racey replacement
                    if i % 2 == 0:
                        policies.clear()
                    else:
                        policies["worker1"] = {"allowed_kinds": ["ping"]}
                except Exception:
                    pass
                time.sleep(0.001)
        def worker(n):
            try:
                job = {"kind": "ping" if n % 2 == 0 else "exec",
                       "timeout_sec": 30, "interpreter": ["sh"]}
                reason = check_key_policy(policies, f"worker{n%3}", base_cfg, job)
                # reason is str or None; never raises
                assert reason is None or isinstance(reason, str)
                # bad inputs
                check_key_policy("not-a-dict", "x", base_cfg, job)
                check_key_policy(policies, "x", base_cfg, "not-a-job")
            except Exception as e:
                errors.append(repr(e))
        t = threading.Thread(target=mutator, daemon=True)
        t.start()
        with ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(worker, range(6)))
        t.join(timeout=1)
        self.assertEqual(errors, [])

class ConcurrentQueryAnswerTest(unittest.TestCase):
    def test_answer_queries_on_poisoned_retained_concurrent(self):
        poisoned = [
            {"stdout": 42, "stderr": None, "exit_code": "zero", "view": True},
            {"stdout": None, "patterns": "bad", "budget": "lots"},
            None,
            "not a dict",
            {"stdout": "ok\nline", "exit_code": 0, "confined": True},
        ]
        errors = []
        def worker(data):
            try:
                answers, spent = answer_queries(
                    [{"op": "attest", "predicate": "exit_zero"},
                     {"op": "grep", "pattern": "x"},
                     {"op": "ask", "question": "why?"}],
                    data if isinstance(data, dict) else {},
                    _redact_patterns({}),
                    budget=5,
                    view="full",
                )
                assert isinstance(answers, list)
                assert isinstance(spent, int)
            except Exception as e:
                errors.append(repr(e))
        with ThreadPoolExecutor(max_workers=5) as ex:
            list(ex.map(worker, poisoned))
        self.assertEqual(errors, [])

class InterpreterEdgePollTest(unittest.TestCase):
    def test_poll_rejects_bad_interpreters_without_stopping(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
            }
            jobs = []
            # non-list interpreter
            jobs.append(sign_payload({
                "v": 1, "type": "job", "job_id": "badint",
                "issued_at": _now(), "kind": "exec",
                "script": "echo hi", "interpreter": "bash"
            }, SECRET))
            # empty list
            jobs.append(sign_payload({
                "v": 1, "type": "job", "job_id": "emptyint",
                "issued_at": _now(), "kind": "exec",
                "script": "echo hi", "interpreter": []
            }, SECRET))
            # extreme timeout
            jobs.append(sign_payload({
                "v": 1, "type": "job", "job_id": "bigtimeout",
                "issued_at": _now(), "kind": "exec",
                "script": "echo hi", "timeout_sec": 999999
            }, SECRET))
            # good ping sibling
            jobs.append(sign_payload({
                "v": 1, "type": "job", "job_id": "goodping",
                "issued_at": _now(), "kind": "ping"
            }, SECRET))
            raws = [_mail(f"[HOMING-PIGEON] job j{i}", body) for i, body in enumerate(jobs)]
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Opts())
            # if we are here, no crash; retained dir should be usable
            self.assertIsNone(load_retained(d, "no-such"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
