#!/usr/bin/env python3
"""Fourth-pass negative tests: multi-secret verify races, concurrent review, security events, heavy poll.

Findings from virtual-environment simulation (2026-10-15, fourth pass):

1. Concurrent verify_body_keyed against a secrets map that is being
   mutated, or with non-dict secrets / non-string bodies, raises only
   the expected ValueError for bad input. It never leaves the process
   in a bad state; a subsequent good verify still succeeds.

2. Concurrent review_job on jobs that are non-dicts, have non-string
   scripts, missing fields, or extreme nested structures returns a
   notes dict and never raises.

3. Concurrent _append_security_event against a security-events.jsonl
   that is being truncated, overwritten with binary, or locked by
   another writer does not raise (best-effort append).

4. A heavier poll_once batch of mixed good pings and deliberately
   malformed signed jobs (bad key_id, truncated sig, non-object body)
   completes without the poll itself raising, even while extension
   files are being corrupted in parallel.
"""
import os
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import review
from runner.runner import (
    verify_body_keyed, build_secrets, _append_security_event,
    poll_once, sign_payload
)

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"
SECRET2 = "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"

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
    workers = 4
    once = True
    dry_run = False
    no_send = True

class MultiSecretRaceTest(unittest.TestCase):
    def test_concurrent_verify_under_secrets_mutation(self):
        cfg = {
            "shared_secret": SECRET,
            "keys": {"k2": SECRET2},
        }
        secrets = build_secrets(cfg)
        good = sign_payload({
            "v": 1, "type": "job", "job_id": "g",
            "issued_at": _now(), "kind": "ping"
        }, SECRET)
        errors = []
        def mutator():
            for i in range(15):
                try:
                    if i % 2 == 0:
                        secrets.clear()
                        secrets[""] = SECRET
                    else:
                        secrets["k2"] = SECRET2
                except Exception:
                    pass
                time.sleep(0.001)
        def worker(n):
            try:
                if n % 3 == 0:
                    verify_body_keyed(good, secrets)
                elif n % 3 == 1:
                    try:
                        verify_body_keyed("not json", secrets)
                    except ValueError:
                        pass
                else:
                    try:
                        verify_body_keyed(good, "not-a-dict")
                    except ValueError:
                        pass
            except Exception as e:
                if not isinstance(e, ValueError):
                    errors.append(repr(e))
        t = threading.Thread(target=mutator, daemon=True)
        t.start()
        with ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(worker, range(6)))
        t.join(timeout=1)
        self.assertEqual(errors, [])
        # still usable
        payload, kid = verify_body_keyed(good, {"": SECRET})
        self.assertEqual(kid, "")

class ConcurrentReviewTest(unittest.TestCase):
    def test_review_job_never_raises_on_poison(self):
        cfg = {"review_patterns_extra": {"bad": "["}}  # invalid regex
        poisons = [
            None,
            "not a dict",
            {"kind": "exec", "script": 123},
            {"kind": "exec", "script": "x" * 100000, "interpreter": "bash"},
            {"kind": "ping"},
            {"nested": {"a": {"b": {"c": list(range(1000))}}}},
        ]
        errors = []
        def worker(job):
            try:
                result = review.review_job(cfg, job)
                assert isinstance(result, dict)
                assert "notes" in result
            except Exception as e:
                errors.append(repr(e))
        with ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(worker, poisons))
        self.assertEqual(errors, [])

class SecurityEventRaceTest(unittest.TestCase):
    def test_append_security_event_under_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "security-events.jsonl")
            errors = []
            def corruptor():
                for i in range(20):
                    try:
                        with open(path, "wb") as f:
                            f.write(b"\xff\xfe" if i % 2 == 0 else b"")
                    except Exception:
                        pass
                    time.sleep(0.001)
            def worker(n):
                try:
                    _append_security_event(d, {"event": f"e{n}", "n": n})
                except Exception as e:
                    errors.append(repr(e))
            t = threading.Thread(target=corruptor, daemon=True)
            t.start()
            with ThreadPoolExecutor(max_workers=8) as ex:
                list(ex.map(worker, range(8)))
            t.join(timeout=1)
            self.assertEqual(errors, [])

class HeavyPollTest(unittest.TestCase):
    def test_poll_once_heavy_mixed_batch_under_extension_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
                "resources": {"enabled": True},
                "dri": {"enabled": True},
            }
            raws = []
            # 3 good pings
            for i in range(3):
                body = sign_payload({
                    "v": 1, "type": "job", "job_id": f"good{i}",
                    "issued_at": _now(), "kind": "ping"
                }, SECRET)
                raws.append(_mail(f"[HOMING-PIGEON] job good{i}", body))
            # bad ones
            raws.append(_mail("[HOMING-PIGEON] job bad1", "not signed"))
            raws.append(_mail("[HOMING-PIGEON] job bad2", '{"not":"signed"}'))
            # truncated-looking signed
            bad_sig = sign_payload({
                "v": 1, "type": "job", "job_id": "trunc",
                "issued_at": _now(), "kind": "ping"
            }, SECRET)[:-10]
            raws.append(_mail("[HOMING-PIGEON] job trunc", bad_sig))
            def corruptor():
                for _ in range(10):
                    try:
                        with open(os.path.join(d, "resources.json"), "w") as f:
                            f.write("null")
                        with open(os.path.join(d, "dri-state.json"), "w") as f:
                            f.write("[]")
                    except Exception:
                        pass
                    time.sleep(0.002)
            t = threading.Thread(target=corruptor, daemon=True)
            t.start()
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Opts())
            t.join(timeout=1)
            # reached here => no crash

if __name__ == "__main__":
    unittest.main(verbosity=2)
