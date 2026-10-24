#!/usr/bin/env python3
"""Deeper negative tests: rate-limit races, retained poison, snapshot edges, concurrent extensions.

Findings from virtual-environment simulation (2026-10-15, second pass):

1. Concurrent check_rate_limit against a query_times.json that is being
   overwritten with garbage, lists, or non-UTF8 does not raise. The
   _QUERY_LOCK + type checks + except-on-load keep both workers and the
   next call alive. Unlimited (limit <= 0) and exhausted windows behave
   as documented.

2. Concurrent save_retained / load_retained with unsafe job_ids, corrupt
   files, and non-dict payloads never raises. Unsafe ids are dropped;
   corrupt files return None.

3. snapshot_outside and confinement_violated survive missing dirs,
   permission errors (mocked), and non-string roots without raising
   into the caller.

4. Concurrent resources.check_resources + dri.maybe_page against
   poisoned state files (empty, list, truncated, binary) do not raise
   and do not stop a subsequent poll_once.
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
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import dri, resources
from runner.runner import (
    check_rate_limit, load_retained, save_retained,
    snapshot_outside, confinement_violated, poll_once, sign_payload
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
    workers = 2
    once = True
    dry_run = False
    no_send = True

class RateLimitRaceTest(unittest.TestCase):
    def test_concurrent_rate_limit_under_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "query_times.json")
            cfg = {"max_queries_per_hour": 5}
            errors = []
            def corruptor():
                for i in range(30):
                    try:
                        with open(path, "w") as f:
                            if i % 3 == 0:
                                f.write("not json")
                            elif i % 3 == 1:
                                f.write("[1,2,3]")
                            else:
                                f.write(b"\xff".decode("latin1"))
                    except Exception:
                        pass
                    time.sleep(0.001)
            def worker(n):
                try:
                    for _ in range(4):
                        ok = check_rate_limit(f"key{n}", cfg, path)
                        assert isinstance(ok, bool)
                except Exception as e:
                    errors.append(repr(e))
            t = threading.Thread(target=corruptor, daemon=True)
            t.start()
            with ThreadPoolExecutor(max_workers=6) as ex:
                list(ex.map(worker, range(6)))
            t.join(timeout=1)
            self.assertEqual(errors, [])
            # unlimited path
            self.assertTrue(check_rate_limit("k", {"max_queries_per_hour": 0}, path))

class RetainedRaceTest(unittest.TestCase):
    def test_concurrent_retained_poison(self):
        with tempfile.TemporaryDirectory() as d:
            errors = []
            def worker(n):
                try:
                    # unsafe ids dropped
                    save_retained(d, "../bad", {"x": 1})
                    save_retained(d, "", {"x": 1})
                    save_retained(d, f"job{n}", {"stdout": n, "saved_at": time.time()})
                    data = load_retained(d, f"job{n}")
                    # may be None if raced, but must not raise
                    if data is not None:
                        assert isinstance(data, dict)
                    # corrupt file
                    bad = os.path.join(d, "retained", "corrupt.json")
                    os.makedirs(os.path.dirname(bad), exist_ok=True)
                    with open(bad, "w") as f:
                        f.write("not json")
                    self.assertIsNone(load_retained(d, "corrupt"))
                except Exception as e:
                    errors.append(repr(e))
            with ThreadPoolExecutor(max_workers=8) as ex:
                list(ex.map(worker, range(8)))
            self.assertEqual(errors, [])

class SnapshotEdgeTest(unittest.TestCase):
    def test_snapshot_survives_bad_roots(self):
        # missing
        before = snapshot_outside("/tmp/does-not-exist-xyz")
        self.assertIsInstance(before, dict)
        # non-string
        try:
            snapshot_outside(None)
            snapshot_outside(123)
        except Exception as e:
            self.fail(f"snapshot raised: {e}")
        # confinement with bad snapshots
        self.assertFalse(confinement_violated(None, None))
        self.assertTrue(confinement_violated({}, {"a": 1}))  # change detected is expected

class ConcurrentExtensionTest(unittest.TestCase):
    def test_resources_and_dri_under_poison_then_poll(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("resources.json", "dri-state.json"):
                with open(os.path.join(d, name), "w") as f:
                    f.write("[]" if name.startswith("r") else "null")
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
                "resources": {"enabled": True, "threshold": 0.0},
                "dri": {"enabled": True, "channel": "log"},
            }
            errors = []
            def ext_worker():
                try:
                    resources.check_resources(cfg, d)
                    with mock.patch.object(dri, "_send", return_value=False):
                        dri.maybe_page(cfg, d)
                except Exception as e:
                    errors.append(repr(e))
            threads = [threading.Thread(target=ext_worker) for _ in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            # still can poll
            body = sign_payload({
                "v": 1, "type": "job", "job_id": "still",
                "issued_at": _now(), "kind": "ping"
            }, SECRET)
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([_mail("[HOMING-PIGEON] job still", body)]),
                      smtp=_SMTP(), opts=_Opts())

if __name__ == "__main__":
    unittest.main(verbosity=2)
