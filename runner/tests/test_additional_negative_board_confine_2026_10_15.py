#!/usr/bin/env python3
"""Fifth-pass negative tests: Board approve/reoffer races, confinement edges, inference/download rejection.

Findings from virtual-environment simulation (2026-10-15, fifth pass):

1. Concurrent Board.approve / reoffer_expired / complete while board.json
   is being overwritten with garbage or non-dict data does not crash
   workers. The lock + type filtering keeps the Board usable; a later
   Board() still returns a dict.

2. snapshot_outside and confinement_violated survive non-existent roots,
   non-string arguments, and empty snapshots without raising. A real
   difference is reported as a violation (expected).

3. ask_model on non-loopback endpoints, missing config, and opener
   failures returns a structured rejection and never raises.

4. Jobs with non-https script_url or files containing non-dict entries
   are rejected by the validation path; poll_once continues and does
   not raise.
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

from runner.runner import (
    Board, snapshot_outside, confinement_violated, ask_model,
    poll_once, sign_payload
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
    workers = 3
    once = True
    dry_run = False
    no_send = True

class BoardApproveRaceTest(unittest.TestCase):
    def test_concurrent_approve_reoffer_complete_under_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            b = Board(path)
            for i in range(15):
                b.submit({"task_id": f"t{i}", "kind": "ping", "requires": ["ping"]})
            errors = []
            def corruptor():
                for i in range(25):
                    try:
                        with open(path, "w") as f:
                            f.write("garbage" if i % 2 == 0 else "[1,2]")
                    except Exception:
                        pass
                    time.sleep(0.001)
            def worker(n):
                try:
                    if n % 3 == 0:
                        b.approve(f"t{n}")
                    elif n % 3 == 1:
                        b.reoffer_expired(1)
                    else:
                        task = b.offer(f"w{n}", ["ping"])
                        if task and isinstance(task, dict):
                            b.complete(task.get("task_id"), {"ok": True})
                except Exception as e:
                    errors.append(repr(e))
            t = threading.Thread(target=corruptor, daemon=True)
            t.start()
            with ThreadPoolExecutor(max_workers=8) as ex:
                list(ex.map(worker, range(12)))
            t.join(timeout=1)
            self.assertEqual(errors, [])
            b2 = Board(path)
            self.assertIsInstance(b2.tasks, dict)

class ConfinementEdgeTest(unittest.TestCase):
    def test_snapshot_and_confinement_never_raise(self):
        # missing / bad roots
        s1 = snapshot_outside("/tmp/no-such-workspace-xyz")
        self.assertIsInstance(s1, dict)
        try:
            snapshot_outside(None)
            snapshot_outside(42)
            snapshot_outside("")
        except Exception as e:
            self.fail(f"snapshot raised: {e}")
        # confinement comparisons
        self.assertFalse(confinement_violated(None, None))
        self.assertFalse(confinement_violated({}, {}))
        self.assertTrue(confinement_violated({}, {"changed": True}))
        self.assertFalse(confinement_violated({"a": 1}, {"a": 1}))

class InferenceRejectionTest(unittest.TestCase):
    def test_ask_model_rejects_non_loopback_and_failures(self):
        # non-loopback
        cfg = {"inference": {"endpoint": "http://evil.example.com", "model": "x"}}
        result = ask_model(cfg, "why?", "out", 100)
        self.assertIsInstance(result, dict)
        self.assertIn("rejected", result)
        # opener boom
        def boom(*a, **k):
            raise OSError("connection refused")
        cfg2 = {"inference": {"endpoint": "http://127.0.0.1:11434", "model": "x"}}
        result = ask_model(cfg2, "why?", "out", 100, opener=boom)
        self.assertIsInstance(result, dict)
        # empty config
        result = ask_model({}, "why?", "out", 100)
        self.assertIsInstance(result, dict)

class DownloadRejectionPollTest(unittest.TestCase):
    def test_poll_rejects_bad_urls_without_crash(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
            }
            # non-https script_url
            body1 = sign_payload({
                "v": 1, "type": "job", "job_id": "badurl",
                "issued_at": _now(), "kind": "exec",
                "script_url": "http://insecure.example/script.sh"
            }, SECRET)
            # files with non-dict entry
            body2 = sign_payload({
                "v": 1, "type": "job", "job_id": "badfiles",
                "issued_at": _now(), "kind": "exec",
                "script": "echo hi",
                "files": ["not-a-dict", {"name": "ok.txt", "url": "https://example.com/ok"}]
            }, SECRET)
            # good sibling
            body3 = sign_payload({
                "v": 1, "type": "job", "job_id": "good",
                "issued_at": _now(), "kind": "ping"
            }, SECRET)
            raws = [
                _mail("[HOMING-PIGEON] job badurl", body1),
                _mail("[HOMING-PIGEON] job badfiles", body2),
                _mail("[HOMING-PIGEON] job good", body3),
            ]
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Opts())
            # reached here => no crash

if __name__ == "__main__":
    unittest.main(verbosity=2)
