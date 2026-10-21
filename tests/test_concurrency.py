#!/usr/bin/env python3
"""Concurrency and bad extension data. The poll and the Oracle keep going.

Findings from the simulation this file locks in:

- A resource event that is a string, an int, or a map of words used to
  raise while formatting the log line. No mail in that cycle was read.
- One worker exception used to fail the whole poll after the other
  workers had already finished, so the cycle was reported as failed.
- ask_model returning None, a string, a list, or raising used to drop
  the chat request. A bad answer must be a JSON error, not a dead socket.
- Concurrent sense alerts share one file. The lines must stay valid JSON.
"""
import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import jobcrypto, senses  # noqa: E402
from runner.runner import (  # noqa: E402
    answer_queries,
    fetch_job_mails,
    handle_mail,
    make_oracle_server,
    poll_once,
    sign_payload,
)

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wire_body(subject, body):
    """Put a signed job body on the wire in its encrypted form.

    Jobs are refused in the HMAC-only (cleartext) form by default,
    so a signed job that is meant to reach execution must travel
    as an hp_enc envelope: sign, encrypt, sign the envelope (the
    pattern from tests/test_protocol_and_edges.py). The AAD job_id
    is the one in the subject -- the id the runner decrypts
    against -- so a body whose job_id deliberately differs from
    the subject still decrypts and meets the check written for
    it, with its inner bytes unchanged. Anything that is not a
    signed job object is returned byte-identical, and so is a
    body that does not parse. Queries and board messages are
    enveloped the same way: those paths refuse cleartext too.
    """
    if not isinstance(body, str):
        return body
    try:
        payload = json.loads(body)
    except ValueError:
        return body
    if not isinstance(payload, dict):
        return body
    kind = payload.get("type")
    if kind == "job":
        m = re.search(r"\bjob\s+(\S+)", subject or "")
        if not m:
            return body
        object_id = m.group(1)
    elif kind in ("query", "task_submit", "task_request",
                  "task_result", "task_approve"):
        object_id = (subject or "").rsplit(" ", 1)[-1]
    else:
        return body
    key_id = payload.get("key_id")
    if not isinstance(key_id, str):
        key_id = ""
    return jobcrypto.encrypt_body(
        body, SECRET, job_id=object_id, key_id=key_id,
        sign=sign_payload)


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(_wire_body(subject, body))
    return msg.as_bytes()


class _IMAP:
    def __init__(self, raws):
        self.raws = list(raws)

    def search(self, *a):
        ids = b" ".join(str(i + 1).encode() for i in range(len(self.raws)))
        return "OK", [ids]

    def fetch(self, n, w):
        return "OK", [(b"x", self.raws[int(n) - 1])]

    def store(self, *a, **k):
        return "OK", []


class _SMTP:
    def send_message(self, *a, **k):
        return None


class _Opts:
    dry_run = False
    no_send = True
    workers = 4


def _pings(n=6):
    out = []
    for i in range(n):
        body = sign_payload({
            "v": 1, "type": "job", "job_id": f"ping-{i}",
            "issued_at": _now(), "kind": "ping",
        }, SECRET)
        out.append(_mail(f"[HOMING-PIGEON] job ping-{i}", body))
    return out


def _cfg():
    return {
        "mailbox_user": "pigeon-test@example.com",
        "shared_secret": SECRET,
        "workers": 4,
    }


class BadExtensionTest(unittest.TestCase):
    def test_bad_resource_events_do_not_skip_mail(self):
        shapes = [
            "hot",
            5,
            {"threshold": "high", "resources": {"cpu": "hot"}},
            {"resources": None, "threshold": 0.9},
        ]
        for shape in shapes:
            with tempfile.TemporaryDirectory() as d:
                seen = {}
                with mock.patch("runner.resources.check_resources",
                                return_value=shape), \
                     mock.patch("runner.dri.maybe_page",
                                side_effect=RuntimeError("pager down")):
                    poll_once(_cfg(), d, seen, os.path.join(d, "seen.json"),
                              imap=_IMAP(_pings()), smtp=_SMTP(), opts=_Opts())
                self.assertEqual(len(seen), 6, shape)

    def test_one_worker_crash_does_not_drop_the_others(self):
        with tempfile.TemporaryDirectory() as d:
            seen = {}

            def boom(cfg, imap, smtp, seq, raw, base_dir, seen_map,
                     secrets, opts=None, key_policies=None):
                if str(seq) == "1":
                    raise RuntimeError("extension blew up")
                return handle_mail(cfg, imap, smtp, seq, raw, base_dir,
                                   seen_map, secrets, opts, key_policies)

            with mock.patch("runner.runner.handle_mail", side_effect=boom):
                poll_once(_cfg(), d, seen, os.path.join(d, "seen.json"),
                          imap=_IMAP(_pings()), smtp=_SMTP(), opts=_Opts())
            self.assertNotIn("ping-0", seen)
            self.assertEqual(len(seen), 5)


class OracleBadAnswerTest(unittest.TestCase):
    def test_concurrent_bad_answers_stay_json(self):
        answers = [
            None,
            "nope",
            ["not", "a", "dict"],
            {"answer": {"nested": True}},
            RuntimeError("model socket died"),
            {"answer": "a job finished"},
        ]

        n = len(answers)
        lock = threading.Lock()

        def fake_ask(*a, **k):
            with lock:
                if not answers:
                    # A retried request can reach the model again
                    # after the first six answers were consumed.
                    # The contract under test is that the client
                    # still gets JSON, not which answer it was.
                    return {"rejected": "inference_error"}
                item = answers.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with tempfile.TemporaryDirectory() as d:
            cfg = _cfg()
            cfg["base_dir"] = d
            cfg["inference"] = {
                "endpoint": "http://127.0.0.1:11434/v1",
                "model": "llama3.2:3b",
            }
            httpd = make_oracle_server(cfg, "127.0.0.1", 0)
            port = httpd.socket.getsockname()[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(httpd.shutdown)
            self.addCleanup(httpd.server_close)
            token = httpd.oracle_token
            barrier = threading.Barrier(len(answers))
            codes = []

            def post():
                barrier.wait()
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/ask",
                    data=json.dumps({"question": "what happened?"}).encode(),
                    headers={
                        "Origin": f"http://127.0.0.1:{port}",
                        "Content-Type": "application/json",
                        "X-Oracle-Token": token,
                    },
                    method="POST",
                )
                # Windows CI aborts a localhost connection when six
                # clients hit the oracle together (10053, 10038,
                # timeout). One attempt then fails the shard. Retry
                # the POST; the JSON contract is what this pins.
                last = None
                for attempt in range(3):
                    try:
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            body = json.loads(resp.read().decode())
                            codes.append((resp.status, body))
                            return
                    except (urllib.error.URLError, TimeoutError, OSError) as exc:
                        last = exc
                        time.sleep(0.05 * (attempt + 1))
                raise last

            with mock.patch("runner.runner.ask_model", side_effect=fake_ask):
                threads = [threading.Thread(target=post) for _ in answers]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(timeout=20)
                    self.assertFalse(t.is_alive())
            self.assertEqual(len(codes), n)
            for status, body in codes:
                self.assertEqual(status, 200)
                self.assertTrue("answer" in body or "rejected" in body)


class SenseStoreTest(unittest.TestCase):
    def test_concurrent_alerts_stay_json(self):
        with tempfile.TemporaryDirectory() as d:
            def write(i):
                senses.store_alert(d, {
                    "sensor": "host-ids", "severity": "info",
                    "title": f"t{i}", "detail": {"n": i},
                })

            threads = [threading.Thread(target=write, args=(i,)) for i in range(40)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            rows = senses.load_alerts(d, limit=100)
            self.assertEqual(len(rows), 40)
            self.assertEqual(len({r["title"] for r in rows}), 40)


class ReviewAndAgeTest(unittest.TestCase):
    """A bad age window and a bad review used to stop every job.

    Finding: max_job_age_sec set to the word "hour" raised inside
    each worker before the job ran, so a poll of two pings stored
    nothing. A review that raises, or that returns a set, did not
    get that far in that run. Both must be skipped, not fatal.
    """

    def _two(self):
        raws = []
        for jid in ("good", "reviewed"):
            body = sign_payload({
                "v": 1, "type": "job", "job_id": jid,
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            raws.append(_mail(f"[HOMING-PIGEON] job {jid}", body))
        return raws

    def test_word_age_and_a_raising_review_still_run_both_jobs(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = _cfg()
            cfg["max_job_age_sec"] = "hour"
            seen = {}

            def boom(*a, **k):
                raise RuntimeError("review exploded")

            with mock.patch("runner.review.review_job", side_effect=boom):
                poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                          imap=_IMAP(self._two()), smtp=_SMTP(), opts=_Opts())
            self.assertEqual(sorted(seen), ["good", "reviewed"])

    def test_non_json_review_is_dropped_and_the_job_finishes(self):
        with tempfile.TemporaryDirectory() as d:
            seen = {}
            with mock.patch("runner.review.review_job",
                            return_value={"notes": {1, 2}, "blob": b"\xff"}):
                poll_once(_cfg(), d, seen, os.path.join(d, "seen.json"),
                          imap=_IMAP(self._two()), smtp=_SMTP(), opts=_Opts())
            self.assertEqual(sorted(seen), ["good", "reviewed"])


class ImapAndBudgetTest(unittest.TestCase):
    """Bad SEARCH data and two queries spending one budget.

    Finding: SEARCH that returned None, an empty list, or a number
    raised before any mail was read, so the cycle failed. Two workers
    reading the same retained job both saw spent 0 and both answered
    a budget of 1. The last write left spent at 1.
    """

    def test_bad_search_does_not_fail_the_poll(self):
        class Bad:
            def __init__(self, data):
                self.data = data

            def search(self, *a):
                return "OK", self.data

            def fetch(self, *a):
                raise AssertionError("fetch")

            def store(self, *a, **k):
                return "OK", []

        for data in (None, [], [5], [None]):
            self.assertEqual(fetch_job_mails(Bad(data)), [])
            with tempfile.TemporaryDirectory() as d:
                poll_once(_cfg(), d, {}, os.path.join(d, "seen.json"),
                          imap=Bad(data), smtp=_SMTP(), opts=_Opts())

    def test_one_bad_fetch_does_not_drop_the_sibling(self):
        body = sign_payload({
            "v": 1, "type": "job", "job_id": "kept",
            "issued_at": _now(), "kind": "ping",
        }, SECRET)
        good = _mail("[HOMING-PIGEON] job kept", body)

        class Mixed:
            def search(self, *a):
                return "OK", [b"1 2"]

            def fetch(self, num, what):
                seq = num.decode() if isinstance(num, bytes) else str(num)
                if seq == "1":
                    raise RuntimeError("folder glitch")
                return "OK", [(b"x", good)]

            def store(self, *a, **k):
                return "OK", []

        with tempfile.TemporaryDirectory() as d:
            seen = {}
            poll_once(_cfg(), d, seen, os.path.join(d, "seen.json"),
                      imap=Mixed(), smtp=_SMTP(), opts=_Opts())
            self.assertIn("kept", seen)

    def test_two_queries_cannot_both_spend_the_last_slot(self):
        import time
        spent_seen = []
        real = answer_queries

        def slow(queries, exec_result, patterns, budget, cfg=None, view="full",
                 already_spent=0, base_dir=None):
            spent_seen.append(already_spent)
            time.sleep(0.05)
            return real(queries, exec_result, patterns, budget, cfg=cfg,
                        view=view, already_spent=already_spent, base_dir=base_dir)

        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            with open(os.path.join(d, "retained", "job-b.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "stdout": "hello flag\n", "stderr": "",
                    "budget": 1, "spent": 0, "view": "full",
                    "saved_at": time.time(),
                }, fh)
            raws = []
            for qid in ("q1", "q2"):
                body = sign_payload({
                    "v": 1, "type": "query", "query_id": qid,
                    "job_id": "job-b", "issued_at": _now(),
                    "queries": [{"op": "grep", "pattern": "flag"}],
                }, SECRET)
                raws.append(_mail(f"[HOMING-PIGEON] query {qid}", body))
            with mock.patch("runner.runner.answer_queries", side_effect=slow):
                poll_once(_cfg(), d, {}, os.path.join(d, "seen.json"),
                          imap=_IMAP(raws), smtp=_SMTP(), opts=_Opts())
            self.assertEqual(sorted(spent_seen), [0, 1])
            with open(os.path.join(d, "retained", "job-b.json"), encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["spent"], 2)


class MailboxConnectionLockTest(unittest.TestCase):
    """SEARCH/FETCH and STORE share one IMAP connection.

    The mailbox lock serializes them. A STORE failure is logged
    after that lock is released, because the logger takes the
    runner lock and the claim path holds the runner lock while
    it marks seen. The other order deadlocks.
    """

    def test_fetch_and_store_do_not_overlap(self):
        from runner import mailbox

        state = {"inside": 0, "overlap": 0}
        gate = threading.Lock()

        class IMAP:
            def _enter(self):
                with gate:
                    state["inside"] += 1
                    if state["inside"] > 1:
                        state["overlap"] += 1

            def _leave(self):
                with gate:
                    state["inside"] -= 1

            def search(self, *args):
                self._enter()
                try:
                    time.sleep(0.02)
                    return "OK", [b"1"]
                finally:
                    self._leave()

            def fetch(self, *args):
                self._enter()
                try:
                    time.sleep(0.02)
                    return "OK", [(b"1 (RFC822)", b"raw")]
                finally:
                    self._leave()

            def store(self, *args):
                self._enter()
                try:
                    time.sleep(0.02)
                    return "OK", []
                finally:
                    self._leave()

        imap = IMAP()
        errors = []

        def run(fn):
            try:
                fn()
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(4):
            threads.append(threading.Thread(
                target=run,
                args=(lambda: mailbox.fetch_job_mails(imap),),
                daemon=True))
            threads.append(threading.Thread(
                target=run,
                args=(lambda: mailbox.mark_seen(imap, "1"),),
                daemon=True))
        for th in threads:
            th.start()
        for th in threads:
            th.join(5)
        self.assertFalse(any(th.is_alive() for th in threads))
        self.assertEqual(errors, [])
        self.assertEqual(state["overlap"], 0)

    def test_a_failed_store_does_not_deadlock_the_runner_lock(self):
        from runner import mailbox
        from runner.runner import _MAIL_LOCK

        in_store = threading.Event()
        finish_store = threading.Event()

        class IMAP:
            def store(self, *args):
                in_store.set()
                if not finish_store.wait(2):
                    raise RuntimeError("store timed out")
                raise RuntimeError("store failed")

        errors = []

        def storer():
            try:
                mailbox.mark_seen(IMAP(), "1")
            except Exception as e:
                errors.append(e)

        def holder():
            try:
                with _MAIL_LOCK:
                    if not in_store.wait(2):
                        raise RuntimeError("store never started")
                    finish_store.set()
                    mailbox.mark_seen(IMAP(), "2")
            except Exception as e:
                errors.append(e)

        t_store = threading.Thread(target=storer, daemon=True)
        t_hold = threading.Thread(target=holder, daemon=True)
        t_store.start()
        self.assertTrue(in_store.wait(2))
        t_hold.start()
        t_store.join(3)
        t_hold.join(3)
        self.assertFalse(t_store.is_alive())
        self.assertFalse(t_hold.is_alive())
        self.assertEqual(errors, [])


class SecurityEventTrimTest(unittest.TestCase):
    """security-events.jsonl is appended from more than one thread.

    The trim must not tear a line or drop the cap by truncating
    the live file under another writer.
    """

    def test_concurrent_appends_stay_valid_and_capped(self):
        from runner.runner import (
            _append_security_event, _SECURITY_EVENTS_MAX)
        with tempfile.TemporaryDirectory() as d:
            with mock.patch(
                    "runner.runner._SECURITY_EVENTS_MAX", 5):
                errors = []

                def worker(n):
                    try:
                        for i in range(8):
                            _append_security_event(d, {
                                "type": "test",
                                "n": n,
                                "i": i,
                            })
                    except Exception as e:
                        errors.append(e)

                threads = [
                    threading.Thread(target=worker, args=(n,),
                                     daemon=True)
                    for n in range(4)]
                for th in threads:
                    th.start()
                for th in threads:
                    th.join(5)
                self.assertFalse(any(th.is_alive() for th in threads))
                self.assertEqual(errors, [])
                path = os.path.join(d, "security-events.jsonl")
                with open(path, encoding="utf-8") as fh:
                    lines = fh.readlines()
                self.assertLessEqual(len(lines), 5)
                self.assertGreaterEqual(len(lines), 1)
                for line in lines:
                    rec = json.loads(line)
                    self.assertEqual(rec["type"], "test")
                self.assertEqual(_SECURITY_EVENTS_MAX, 5000)
