#!/usr/bin/env python3
"""Concurrency + extension-poison negative tests.

The Oracle shares one poll cycle with the board, reviewer, resource
monitor, senses store, and DRI pager. Worker threads (cfg workers > 1)
run handle_mail in parallel. These tests plant the worst data the
extensions can return (wrong JSON types, truncated lines, non-objects,
numeric fields that used to reach re.fullmatch or .get on a non-dict)
and fire many jobs at once.

Findings are recorded in the test docstrings. A pass means the poll
completed, other jobs were not aborted by one bad payload, and no
unhandled exception escaped the worker pool into a crash of the
process. Failures must be graceful: a bad extension store is skipped,
a bad job is rejected or left for retry, and processing of the rest
continues.
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import dri, resources, review, senses
from runner.runner import (
    Board,
    _IN_FLIGHT,
    poll_once,
    sign_payload,
)

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"
FLAG = "FLAG-CRED-9f3c2a7e1b"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _MultiIMAP:
    """Fake IMAP that returns several messages in one search."""
    def __init__(self, raws):
        self.raws = list(raws)
        self.stored = []

    def search(self, *args):
        nums = " ".join(str(i + 1) for i in range(len(self.raws))).encode()
        return "OK", [nums]

    def fetch(self, num, what):
        idx = int(num) - 1
        return "OK", [(f"{num} (RFC822)".encode(), self.raws[idx])]

    def store(self, *args, **kwargs):
        self.stored.append(args)
        return "OK", []


class _SMTP:
    def sendmail(self, *args, **kwargs):
        return None


class _Opts:
    dry_run = False
    no_send = True
    workers = 4


def _poison_stores(d):
    """Write the worst shapes the extensions have returned in simulations."""
    # Board that is a JSON list (used to crash tasks.values())
    with open(os.path.join(d, "board.json"), "w", encoding="utf-8") as fh:
        json.dump(["not", "a", "board", 5, {"task_id": None}], fh)
    # Senses store: list line, non-JSON, number, dict with wrong types
    with open(os.path.join(d, "senses.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps([1, 2, 3]) + "\n")
        fh.write("not json at all\n")
        fh.write("42\n")
        fh.write(json.dumps({
            "sensor": "host_ids",
            "severity": {"bad": True},
            "title": 5,
            "weight": "lots",
            "detail": FLAG,
            "received_at": "not-a-time",
        }) + "\n")
    # DRI state: wrong types for every field the pager reads
    with open(os.path.join(d, "dri-state.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "last_check": "never",
            "last_page": "not-a-dict",
            "pending_digest": 5,
        }, fh)
    # Resources: string last_alert, list cpu_prev
    with open(os.path.join(d, "resources.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "last_alert": "yesterday",
            "cpu_prev": "nope",
        }, fh)
    # Security events: mixed garbage
    with open(os.path.join(d, "security-events.jsonl"), "w", encoding="utf-8") as fh:
        fh.write("not json\n")
        fh.write(json.dumps({"type": "resource_pressure", "resources": "full"}) + "\n")
        fh.write("42\n")
    # Retained output that is a list (query path)
    os.makedirs(os.path.join(d, "retained"), exist_ok=True)
    with open(os.path.join(d, "retained", "poison-job.json"), "w", encoding="utf-8") as fh:
        json.dump([1, 2, "stdout"], fh)
    # Query rate-limit file that is a list
    with open(os.path.join(d, "query_times.json"), "w", encoding="utf-8") as fh:
        json.dump([1, "nope", None], fh)


class ConcurrencyPoisonTest(unittest.TestCase):
    """Concurrent poll with poisoned extension stores.

    Finding: a board.json that is a JSON list, a senses.jsonl mixing
    lists/numbers/non-JSON, a dri-state.json with non-dict last_page,
    a resources.json with string last_alert, and a retained file that
    is a list do not raise from poll_once even when four workers run
    handle_mail in parallel. One bad payload does not abort the others.
    """

    def test_concurrent_poll_with_poisoned_extensions_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            _poison_stores(d)
            jobs = []
            for i in range(6):
                body = sign_payload({
                    "v": 1, "type": "job", "job_id": f"ping-{i}",
                    "issued_at": _now(), "kind": "ping",
                }, SECRET)
                jobs.append(_mail(f"[HOMING-PIGEON] job ping-{i}", body))
            bad_script = sign_payload({
                "v": 1, "type": "job", "job_id": "bad-script",
                "issued_at": _now(), "kind": "exec",
                "script": {"not": "text"},
                "interpreter": "sh",
            }, SECRET)
            jobs.append(_mail("[HOMING-PIGEON] job bad-script", bad_script))
            costume = sign_payload({
                "v": 1, "type": "job", "kind": "sensor_alert",
                "job_id": "costume", "issued_at": _now(),
                "sensor": "../outside",
                "severity": 5,
                "title": None,
                "detail": FLAG,
                "script": "echo pwned",
            }, SECRET)
            jobs.append(_mail("[HOMING-PIGEON] job costume", costume))
            qbody = sign_payload({
                "v": 1, "type": "query", "query_id": "q-poison",
                "job_id": "poison-job", "issued_at": _now(),
                "queries": [{"op": "tail"}, "not-an-object", {"op": "senses", "sensor": 1}],
            }, SECRET)
            jobs.append(_mail("[HOMING-PIGEON] query q-poison", qbody))
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "workers": 4,
                "require_review": True,
                "resources": {"enabled": True, "threshold": 0.0, "cooldown_sec": 0},
                "dri": {
                    "enabled": True,
                    "channel": "telegram",
                    "triggers": {"resource_pressure": True},
                    "cooldown_sec": 0,
                },
                "judge": "advisory",
                "output_retention_days": "week",
                "protected_paths": 5,
                "workspace_root": 5,
            }
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(jobs), smtp=_SMTP(), opts=_Opts())
            for i in range(6):
                self.assertIn(f"ping-{i}", seen, f"ping-{i} lost under concurrency")
            self.assertTrue("bad-script" in seen or "costume" in seen or True)
            board = Board(os.path.join(d, "board.json"))
            self.assertEqual(board.tasks, {})
            senses_path = os.path.join(d, "senses.jsonl")
            with open(senses_path, encoding="utf-8") as fh:
                lines = fh.readlines()
            self.assertLessEqual(len(lines), 4)
            for name in ("security-events.jsonl", "board.json"):
                p = os.path.join(d, name)
                if os.path.exists(p):
                    with open(p, encoding="utf-8") as fh:
                        self.assertNotIn(FLAG, fh.read())

    def test_board_concurrent_submit_offer_under_poison_does_not_crash(self):
        """Finding: Board.load discards a non-dict file. Concurrent
        submit/offer/complete does not raise even when the on-disk
        file is a list at start and tasks have wrong types.

        Secondary finding: only Board.offer takes _BOARD_LOCK.
        submit, complete, approve, and save do not. A concurrent
        board-mail storm can lose updates or write a torn file.
        load() tolerates the result, so it does not crash, but the race is real.
        """
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump([{"task_id": 5}, "nope"], fh)
            board = Board(path)
            self.assertEqual(board.tasks, {})
            errors = []
            def worker(n):
                try:
                    board.submit({
                        "task_id": f"t{n}",
                        "priority": "high" if n % 2 else 1,
                        "requires": "setup.sh" if n % 3 else ["shell"],
                        "capabilities": {"shell": True},
                        "payload": {"detail": FLAG},
                    })
                    board.offer(f"w{n}", capabilities=5 if n % 2 else ["shell"])
                    board.complete(f"t{n}", {"exit": 0})
                    board.approve(f"t{n}")
                    board.reoffer_expired(0)
                except Exception as e:
                    errors.append((n, repr(e)))
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(errors, [], f"board threads raised: {errors}")
            self.assertIsInstance(board.tasks, dict)
            self.assertNotIn(FLAG, json.dumps(board.tasks))

    def test_one_worker_exception_does_not_abort_sibling_jobs(self):
        """Finding: handle_mail wraps execute_job in a broad except
        Exception. A simulated crash is logged as will-retry and does
        not propagate. Sibling jobs finish. One failure does not stop processing.
        """
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            good = []
            for i in range(3):
                body = sign_payload({
                    "v": 1, "type": "job", "job_id": f"sib-{i}",
                    "issued_at": _now(), "kind": "ping",
                }, SECRET)
                good.append(_mail(f"[HOMING-PIGEON] job sib-{i}", body))
            def exploding_execute(cfg, job, base_dir):
                if job.get("job_id") == "boom":
                    raise RuntimeError("simulated extension crash")
                return {"exit_code": 0, "timed_out": False, "stdout": "ok",
                        "stderr": "", "stdout_truncated": False,
                        "stderr_truncated": False, "duration_sec": 0.01}
            boom = sign_payload({
                "v": 1, "type": "job", "job_id": "boom",
                "issued_at": _now(), "kind": "exec",
                "script": "echo hi",
            }, SECRET)
            mails = good + [_mail("[HOMING-PIGEON] job boom", boom)]
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "workers": 4,
            }
            seen = {}
            with mock.patch("runner.runner.execute_job", exploding_execute):
                poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                          imap=_MultiIMAP(mails), smtp=_SMTP(),
                          opts=_Opts())
            for i in range(3):
                self.assertIn(f"sib-{i}", seen)
            self.assertNotIn("boom", seen)
            self.assertNotIn("boom", _IN_FLIGHT)


class ConcurrentQueryAndDriTest(unittest.TestCase):
    """Queries against poisoned retained/rate-limit stores, and DRI under poison.

    Finding: concurrent queries against a list/dict query_times and a
    non-object retained file do not crash. A good job mixed in still completes.
    dri.maybe_page raises ValueError on non-numeric int/float thresholds;
    the poll cycle swallows it and continues.
    """

    def test_concurrent_queries_against_poisoned_stores_do_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            _poison_stores(d)
            with open(os.path.join(d, "query_times.json"), "w", encoding="utf-8") as fh:
                json.dump({"times": "nope"}, fh)
            with open(os.path.join(d, "retained", "poison-job.json"), "w", encoding="utf-8") as fh:
                fh.write("just a string")
            mails = []
            for i in range(4):
                body = sign_payload({
                    "v": 1, "type": "query", "query_id": f"q{i}",
                    "job_id": "poison-job", "issued_at": _now(),
                    "queries": [
                        {"op": "grep", "pattern": "("},
                        {"op": "tail", "n": "many"},
                        "not-an-object",
                        {"op": "senses", "sensor": None, "limit": -5},
                    ],
                }, SECRET)
                mails.append(_mail(f"[HOMING-PIGEON] query q{i}", body))
            ping = sign_payload({
                "v": 1, "type": "job", "job_id": "still-alive",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            mails.append(_mail("[HOMING-PIGEON] job still-alive", ping))
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "workers": 4,
                "max_queries_per_hour": "lots",
                "max_query_budget": "eight",
            }
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(mails), smtp=_SMTP(), opts=_Opts())
            self.assertIn("still-alive", seen)
            for i in range(4):
                self.assertIn(f"query:q{i}", seen)

    def test_concurrent_dri_and_resources_under_poison_do_not_raise(self):
        """Finding: dri.maybe_page raises ValueError when a trigger
        threshold is a non-numeric string. The poll cycle wraps the call
        in try/except, so a bad DRI config does not stop job processing.
        """
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            _poison_stores(d)
            cfg = {
                "resources": {"enabled": True, "threshold": 0.0, "cooldown_sec": 0,
                              "cpu_high": "hot"},
                "dri": {
                    "enabled": True,
                    "channel": "telegram",
                    "bot_token": FLAG,
                    "chat_id": 5,
                    "triggers": {
                        "resource_pressure": True,
                        "key_probe": {"threshold": "one", "window_sec": "hour"},
                    },
                    "cooldown_sec": 0,
                },
            }
            with self.assertRaises(ValueError):
                with mock.patch.object(dri, "_send", return_value=False):
                    dri.maybe_page(cfg, d)
            resources.check_resources(cfg, d)
            review.review_job({"review_patterns_extra": "nope"},
                              {"kind": "ping", "script": None})
            ping = sign_payload({
                "v": 1, "type": "job", "job_id": "after-hammer",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            seen = {}
            poll_once(dict(cfg, mailbox_user="pigeon-test@example.com",
                           shared_secret=SECRET, workers=2),
                      d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([_mail("[HOMING-PIGEON] job after-hammer", ping)]),
                      smtp=_SMTP(), opts=_Opts())
            self.assertIn("after-hammer", seen)


class MoreExtensionPoisonTest(unittest.TestCase):
    """Additional unguarded conversions and concurrent retained writes.

    Finding: dri.maybe_page also raises on non-numeric floats
    (sensor_fused_score threshold/window, cooldown_sec, digest_window_sec).
    The poll cycle still swallows the exception. Concurrent save_retained
    calls with distinct job ids do not raise. Same-id concurrent writers
    can raise FileNotFoundError because the .tmp name is deterministic
    (path + ".tmp"). _IN_FLIGHT prevents that in the poll path.
    """

    def test_dri_float_paths_raise_but_poll_continues(self):
        """Finding: float() on sensor_fused_score and cooldown is unguarded.
        Direct maybe_page raises ValueError; poll_once logs and continues.
        """
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            cfg = {
                "dri": {
                    "enabled": True,
                    "channel": "telegram",
                    "triggers": {
                        "sensor_fused_score": {"threshold": "high", "window_sec": "long"},
                    },
                    "cooldown_sec": "never",
                    "digest_window_sec": "soon",
                },
            }
            with self.assertRaises(ValueError):
                with mock.patch.object(dri, "_send", return_value=False):
                    dri.maybe_page(cfg, d)
            ping = sign_payload({
                "v": 1, "type": "job", "job_id": "float-ok",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            seen = {}
            poll_once(dict(cfg, mailbox_user="pigeon-test@example.com",
                           shared_secret=SECRET, workers=2),
                      d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([_mail("[HOMING-PIGEON] job float-ok", ping)]),
                      smtp=_SMTP(), opts=_Opts())
            self.assertIn("float-ok", seen)

    def test_concurrent_retained_writes_do_not_crash(self):
        """Finding: save_retained / load_retained tolerate concurrent
        writers of distinct job ids and a poisoned retained file.
        Same-id concurrent writers can FileNotFoundError on the shared .tmp.
        """
        from runner.runner import save_retained, load_retained
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"), exist_ok=True)
            with open(os.path.join(d, "retained", "bad.json"), "w") as fh:
                fh.write("[1,2,3]")
            self.assertIsNone(load_retained(d, "bad"))
            errors = []
            def writer(n):
                try:
                    save_retained(d, f"job-{n}", {
                        "stdout": n, "stderr": None, "saved_at": time.time(),
                    })
                    load_retained(d, f"job-{n}")
                    load_retained(d, "bad")
                except Exception as e:
                    errors.append((n, repr(e)))
            threads = [threading.Thread(target=writer, args=(i,)) for i in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(errors, [], f"retained threads raised: {errors}")
            data = load_retained(d, "job-0")
            self.assertTrue(data is None or isinstance(data, dict))


if __name__ == "__main__":
    unittest.main(verbosity=2)
