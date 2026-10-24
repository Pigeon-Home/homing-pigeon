#!/usr/bin/env python3
"""Sixth-pass negative tests: Board.counts races, extreme query ops, dense concurrent poll.

Findings from virtual-environment simulation (2026-10-15, sixth pass):

1. Concurrent Board.counts / offer / complete while board.json is
   being overwritten with garbage or non-dict data does not raise.
   counts() returns a dict of integers; the Board remains loadable.

2. answer_queries with extreme query shapes (non-dict ops, huge
   patterns, negative budgets, non-string predicates, nested lists)
   returns structured answers or rejections and never raises.

3. A denser poll_once (8 workers, mixed good/bad jobs) running while
   senses.jsonl, resources.json, and retained files are being
   corrupted in parallel completes without the poll raising.
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
    Board, answer_queries, _redact_patterns, poll_once, sign_payload
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
    workers = 8
    once = True
    dry_run = False
    no_send = True

class BoardCountsRaceTest(unittest.TestCase):
    def test_concurrent_counts_under_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            b = Board(path)
            for i in range(10):
                b.submit({"task_id": f"t{i}", "kind": "ping", "requires": ["ping"]})
            errors = []
            def corruptor():
                for i in range(20):
                    try:
                        with open(path, "w") as f:
                            f.write("not json" if i % 2 == 0 else "[]")
                    except Exception:
                        pass
                    time.sleep(0.001)
            def worker(n):
                try:
                    c = b.counts()
                    assert isinstance(c, dict)
                    if n % 2 == 0:
                        task = b.offer(f"w{n}", ["ping"])
                        if task and isinstance(task, dict):
                            b.complete(task.get("task_id"), {"ok": True})
                except Exception as e:
                    errors.append(repr(e))
            t = threading.Thread(target=corruptor, daemon=True)
            t.start()
            with ThreadPoolExecutor(max_workers=6) as ex:
                list(ex.map(worker, range(6)))
            t.join(timeout=1)
            self.assertEqual(errors, [])
            self.assertIsInstance(Board(path).counts(), dict)

class ExtremeQueryTest(unittest.TestCase):
    def test_answer_queries_extreme_shapes(self):
        queries = [
            None,
            "not a dict",
            {"op": "attest"},
            {"op": "grep", "pattern": "(" * 100},  # bad regex
            {"op": "ask", "question": "x" * 10000},
            {"op": "senses", "limit": -5, "severity_floor": 123},
            {"op": "unknown"},
            {"op": "attest", "predicate": ["not", "string"]},
        ]
        errors = []
        def worker(q):
            try:
                answers, spent = answer_queries(
                    [q] if q is not None else None,
                    {"stdout": "line\n", "exit_code": 0},
                    _redact_patterns({}),
                    budget=-1,  # negative budget
                    view="full",
                )
                assert isinstance(answers, list)
                assert isinstance(spent, int)
            except Exception as e:
                errors.append(repr(e))
        with ThreadPoolExecutor(max_workers=4) as ex:
            list(ex.map(worker, queries))
        self.assertEqual(errors, [])

class DensePollTest(unittest.TestCase):
    def test_dense_poll_under_parallel_extension_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
                "resources": {"enabled": True},
                "dri": {"enabled": True},
                "senses": {"enabled": True},
            }
            raws = []
            for i in range(6):
                body = sign_payload({
                    "v": 1, "type": "job", "job_id": f"g{i}",
                    "issued_at": _now(), "kind": "ping"
                }, SECRET)
                raws.append(_mail(f"[HOMING-PIGEON] job g{i}", body))
            raws.append(_mail("[HOMING-PIGEON] job bad", "unsigned"))
            def corruptor():
                for _ in range(8):
                    try:
                        with open(os.path.join(d, "senses.jsonl"), "a") as f:
                            f.write("not json\n")
                        with open(os.path.join(d, "resources.json"), "w") as f:
                            f.write("null")
                        os.makedirs(os.path.join(d, "retained"), exist_ok=True)
                        with open(os.path.join(d, "retained", "x.json"), "w") as f:
                            f.write("{")
                    except Exception:
                        pass
                    time.sleep(0.002)
            t = threading.Thread(target=corruptor, daemon=True)
            t.start()
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Opts())
            t.join(timeout=1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
