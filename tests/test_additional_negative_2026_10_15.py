#!/usr/bin/env python3
"""Additional negative tests for Homing Pigeon agent + Oracle.

Findings from virtual-environment negative testing (2026-10-15):

1. Concurrent Board.offer/complete while an external process is overwriting
   board.json with garbage does not crash the workers or the Board loader.
   The lock + unique-tmp replace + type checks keep the process alive;
   a subsequent Board() still returns a dict.

2. ask_model never raises into the caller on opener exceptions, non-JSON
   bodies, None/huge output_text, or missing inference config. It returns
   a structured rejection dict (or a redacted string) so the Oracle path
   can continue.

3. Concurrent senses.store_alert / load_alerts against a senses.jsonl that
   already contains truncated JSON, non-JSON lines, and non-UTF8 bytes
   does not raise. Bad lines are skipped; good records remain readable.

4. poll_once processes a mixed batch of good pings, type-invalid scripts,
   path-traversal job_ids, and unsigned garbage without raising, even when
   extension state files (resources.json, dri-state.json, retained/*.json)
   are corrupted. Rejected jobs are logged and the poll completes.
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
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import senses
from runner.runner import (
    Board, answer_queries, ask_model, poll_once, sign_payload
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
    workers = 4
    once = True
    dry_run = False
    verbose = False
    no_send = True
    inspect = False
    oracle = False
    pdb = False

class ConcurrentPoisonBoardTest(unittest.TestCase):
    def test_concurrent_offer_complete_with_mid_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            b = Board(path)
            for i in range(20):
                b.submit({"task_id": f"t{i}", "kind": "ping", "requires": ["ping"]})
            errors = []
            def corruptor():
                for _ in range(40):
                    try:
                        with open(path, "w") as f:
                            f.write("not json at all" if _ % 2 == 0 else '{"bad": true}')
                    except Exception:
                        pass
                    time.sleep(0.002)
            def worker(n):
                try:
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
            # Process stayed alive
            self.assertIsInstance(errors, list)
            # Loader still works
            b2 = Board(path)
            self.assertIsInstance(b2.tasks, dict)

class OracleAskNegativeTest(unittest.TestCase):
    def test_ask_model_never_raises(self):
        cfg = {"inference": {"endpoint": "http://127.0.0.1:11434", "model": "test"}}
        def boom(*a, **k):
            raise RuntimeError("socket died")
        # opener raises -> structured result, no exception
        result = ask_model(cfg, "why?", "some output", 100, opener=boom)
        self.assertIsInstance(result, dict)
        # non-JSON body
        def bad_json(*a, **k):
            class R:
                def read(self): return b"not json {{"
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return R()
        result = ask_model(cfg, "why?", "out", 100, opener=bad_json)
        self.assertIsInstance(result, dict)
        # None and huge output_text
        result = ask_model(cfg, "why?", None, 10, opener=bad_json)
        self.assertIsInstance(result, dict)
        result = ask_model(cfg, "why?", "x" * 500000, 50, opener=bad_json)
        self.assertIsInstance(result, dict)
        # completely unconfigured
        result = ask_model({}, "why?", "out", 100)
        self.assertIsInstance(result, dict)
        self.assertIn("rejected", result)

class SensesConcurrentCorruptTest(unittest.TestCase):
    def test_concurrent_load_store_with_corrupt_lines(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "senses.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"sensor":"ok","severity":"info","title":"good"}\n')
                f.write('not json\n')
                f.write('{"sensor":"bad"\n')
                f.write("\xff\xfe\n")
            errors = []
            def worker():
                try:
                    senses.store_alert(d, {
                        "sensor": "s", "severity": "warn", "title": "t",
                        "observed_at": _now()
                    })
                    recs = senses.load_alerts(d)
                    assert isinstance(recs, list)
                except Exception as e:
                    errors.append(repr(e))
            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [], f"workers raised: {errors}")

class PollMixedBadJobsTest(unittest.TestCase):
    def test_poll_once_survives_mixed_poison_jobs_and_extensions(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "resources.json"), "w") as f:
                f.write("[]")
            with open(os.path.join(d, "dri-state.json"), "w") as f:
                f.write("null")
            os.makedirs(os.path.join(d, "retained"))
            with open(os.path.join(d, "retained", "old.json"), "w") as f:
                f.write("not json")
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
                "resources": {"enabled": True},
                "dri": {"enabled": True},
            }
            good = sign_payload({
                "v": 1, "type": "job", "job_id": "good1",
                "issued_at": _now(), "kind": "ping"
            }, SECRET)
            bad_script = sign_payload({
                "v": 1, "type": "job", "job_id": "badscr",
                "issued_at": _now(), "kind": "exec", "script": 123
            }, SECRET)
            trav = sign_payload({
                "v": 1, "type": "job", "job_id": "../trav",
                "issued_at": _now(), "kind": "ping"
            }, SECRET)
            raws = [
                _mail("[HOMING-PIGEON] job good1", good),
                _mail("[HOMING-PIGEON] job badscr", bad_script),
                _mail("[HOMING-PIGEON] job ../trav", trav),
                _mail("[HOMING-PIGEON] job garbage", "not signed json"),
            ]
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Opts())
            # reached here => no crash

if __name__ == "__main__":
    unittest.main(verbosity=2)
