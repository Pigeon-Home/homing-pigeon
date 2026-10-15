#!/usr/bin/env python3
"""Concurrency + extension-poison negative tests.

The Oracle shares one poll cycle with the board, reviewer, resource
monitor, senses store, and DRI pager. Worker threads (cfg workers > 1)
run handle_mail in parallel. These tests plant the worst data the
extensions can return and fire many jobs at once.

Findings are recorded in the test docstrings. A pass means the poll
completed, other jobs were not aborted by one bad payload, and no
unhandled exception escaped into a process crash. Failures must be
graceful: a bad extension store is skipped, a bad job is rejected or
left for retry, and processing of the rest continues.
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
    with open(os.path.join(d, "board.json"), "w", encoding="utf-8") as fh:
        json.dump(["not", "a", "board", 5, {"task_id": None}], fh)
    with open(os.path.join(d, "senses.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps([1, 2, 3]) + "\n")
        fh.write("not json at all\n")
        fh.write("42\n")
        fh.write(json.dumps({
            "sensor": "host_ids", "severity": {"bad": True}, "title": 5,
            "weight": "lots", "detail": FLAG, "received_at": "not-a-time",
        }) + "\n")
    with open(os.path.join(d, "dri-state.json"), "w", encoding="utf-8") as fh:
        json.dump({"last_check": "never", "last_page": "not-a-dict", "pending_digest": 5}, fh)
    with open(os.path.join(d, "resources.json"), "w", encoding="utf-8") as fh:
        json.dump({"last_alert": "yesterday", "cpu_prev": "nope"}, fh)
    with open(os.path.join(d, "security-events.jsonl"), "w", encoding="utf-8") as fh:
        fh.write("not json\n")
        fh.write(json.dumps({"type": "resource_pressure", "resources": "full"}) + "\n")
        fh.write("42\n")
    os.makedirs(os.path.join(d, "retained"), exist_ok=True)
    with open(os.path.join(d, "retained", "poison-job.json"), "w", encoding="utf-8") as fh:
        json.dump([1, 2, "stdout"], fh)
    with open(os.path.join(d, "query_times.json"), "w", encoding="utf-8") as fh:
        json.dump([1, "nope", None], fh)


class ConcurrencyPoisonTest(unittest.TestCase):
    """Finding: poisoned board/senses/dri/resources/retained do not crash
    poll_once under 4 workers. One bad payload does not abort the others.
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
                "script": {"not": "text"}, "interpreter": "sh",
            }, SECRET)
            jobs.append(_mail("[HOMING-PIGEON] job bad-script", bad_script))
            costume = sign_payload({
                "v": 1, "type": "job", "kind": "sensor_alert",
                "job_id": "costume", "issued_at": _now(),
                "sensor": "../outside", "severity": 5, "title": None,
                "detail": FLAG, "script": "echo pwned",
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
                "shared_secret": SECRET, "workers": 4,
                "require_review": True,
                "resources": {"enabled": True, "threshold": 0.0, "cooldown_sec": 0},
                "dri": {"enabled": True, "channel": "telegram",
                        "triggers": {"resource_pressure": True}, "cooldown_sec": 0},
                "judge": "advisory", "output_retention_days": "week",
                "protected_paths": 5, "workspace_root": 5,
            }
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(jobs), smtp=_SMTP(), opts=_Opts())
            for i in range(6):
                self.assertIn(f"ping-{i}", seen)
            board = Board(os.path.join(d, "board.json"))
            self.assertEqual(board.tasks, {})
            with open(os.path.join(d, "senses.jsonl"), encoding="utf-8") as fh:
                self.assertLessEqual(len(fh.readlines()), 4)

    def test_board_concurrent_submit_offer_under_poison_does_not_crash(self):
        """Finding: only Board.offer takes _BOARD_LOCK. submit/complete/
        approve/save do not. Concurrent board mail can lose updates.
        load() is tolerant so no crash, but the race is real.
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
            self.assertEqual(errors, [])
            self.assertIsInstance(board.tasks, dict)
            self.assertNotIn(FLAG, json.dumps(board.tasks))

    def test_one_worker_exception_does_not_abort_sibling_jobs(self):
        """Finding: handle_mail catches Exception from execute_job,
        logs will-retry, does not propagate. Siblings finish.
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
                "issued_at": _now(), "kind": "exec", "script": "echo hi",
            }, SECRET)
            mails = good + [_mail("[HOMING-PIGEON] job boom", boom)]
            cfg = {"mailbox_user": "pigeon-test@example.com",
                   "shared_secret": SECRET, "workers": 4}
            seen = {}
            with mock.patch("runner.runner.execute_job", exploding_execute):
                poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                          imap=_MultiIMAP(mails), smtp=_SMTP(), opts=_Opts())
            for i in range(3):
                self.assertIn(f"sib-{i}", seen)
            self.assertNotIn("boom", seen)
            self.assertNotIn("boom", _IN_FLIGHT)


class ConcurrentQueryAndDriTest(unittest.TestCase):
    """Finding: concurrent queries against poisoned query_times/retained
    do not crash. dri.maybe_page raises on non-numeric thresholds;
    the poll cycle swallows it.
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
                    "queries": [{"op": "grep", "pattern": "("}, {"op": "tail", "n": "many"},
                                "not-an-object", {"op": "senses", "sensor": None, "limit": -5}],
                }, SECRET)
                mails.append(_mail(f"[HOMING-PIGEON] query q{i}", body))
            ping = sign_payload({
                "v": 1, "type": "job", "job_id": "still-alive",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            mails.append(_mail("[HOMING-PIGEON] job still-alive", ping))
            cfg = {"mailbox_user": "pigeon-test@example.com", "shared_secret": SECRET,
                   "workers": 4, "max_queries_per_hour": "lots", "max_query_budget": "eight"}
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(mails), smtp=_SMTP(), opts=_Opts())
            self.assertIn("still-alive", seen)
            for i in range(4):
                self.assertIn(f"query:q{i}", seen)

    def test_concurrent_dri_and_resources_under_poison_do_not_raise(self):
        """Finding: dri.maybe_page raises ValueError on non-numeric
        key_probe threshold. Poll cycle catches it.
        """
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            _poison_stores(d)
            cfg = {
                "resources": {"enabled": True, "threshold": 0.0, "cooldown_sec": 0, "cpu_high": "hot"},
                "dri": {"enabled": True, "channel": "telegram", "bot_token": FLAG, "chat_id": 5,
                        "triggers": {"resource_pressure": True,
                                     "key_probe": {"threshold": "one", "window_sec": "hour"}},
                        "cooldown_sec": 0},
            }
            with self.assertRaises(ValueError):
                with mock.patch.object(dri, "_send", return_value=False):
                    dri.maybe_page(cfg, d)
            resources.check_resources(cfg, d)
            review.review_job({"review_patterns_extra": "nope"}, {"kind": "ping", "script": None})
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
    """Finding: DRI float() paths raise; poll continues. Concurrent
    save_retained with distinct ids is safe; same-id can FileNotFoundError
    on the shared .tmp name.
    """

    def test_dri_float_paths_raise_but_poll_continues(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            cfg = {"dri": {"enabled": True, "channel": "telegram",
                           "triggers": {"sensor_fused_score": {"threshold": "high", "window_sec": "long"}},
                           "cooldown_sec": "never", "digest_window_sec": "soon"}}
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
        from runner.runner import save_retained, load_retained
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"), exist_ok=True)
            with open(os.path.join(d, "retained", "bad.json"), "w") as fh:
                fh.write("[1,2,3]")
            self.assertIsNone(load_retained(d, "bad"))
            errors = []
            def writer(n):
                try:
                    save_retained(d, f"job-{n}", {"stdout": n, "stderr": None, "saved_at": time.time()})
                    load_retained(d, f"job-{n}")
                    load_retained(d, "bad")
                except Exception as e:
                    errors.append((n, repr(e)))
            threads = [threading.Thread(target=writer, args=(i,)) for i in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(errors, [])
            data = load_retained(d, "job-0")
            self.assertTrue(data is None or isinstance(data, dict))


class StateFileRaceAndResourcesTest(unittest.TestCase):
    """Finding: resources.check_resources catches bad threshold and
    returns None (fail closed). parse_resources still raises.
    Concurrent dri.maybe_page can race on dri-state.json.tmp.
    senses.store_alert concurrent appends do not raise.
    Final poll with every knob poisoned still processes good jobs.
    """

    def test_resources_bad_threshold_fails_closed_without_raising(self):
        cfg = {"resources": {"enabled": True, "threshold": "hot", "cooldown_sec": "never"}}
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(resources.check_resources(cfg, d))
            with self.assertRaises(RuntimeError):
                resources.parse_resources(cfg)
            for i in range(5):
                senses.store_alert(d, {"sensor": f"s{i}", "title": None, "detail": FLAG})
            self.assertTrue(os.path.isdir(d))

    def test_concurrent_dri_state_writers_and_senses_appends(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            cfg = {"dri": {"enabled": True, "channel": "telegram",
                           "triggers": {"resource_pressure": True}, "cooldown_sec": 0}}
            dri_errors = []
            sense_errors = []
            def dri_worker(n):
                try:
                    dri.maybe_page(cfg, d)
                except FileNotFoundError as e:
                    dri_errors.append(("fnf", repr(e)))
                except Exception as e:
                    dri_errors.append(("other", repr(e)))
            def sense_worker(n):
                try:
                    senses.store_alert(d, {"sensor": f"s{n}", "severity": "info",
                                           "title": f"t{n}", "detail": {"n": n}})
                except Exception as e:
                    sense_errors.append((n, repr(e)))
            threads = []
            for i in range(8):
                threads.append(threading.Thread(target=dri_worker, args=(i,)))
                threads.append(threading.Thread(target=sense_worker, args=(i,)))
            with mock.patch.object(dri, "_send", return_value=False):
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(timeout=5)
            self.assertEqual(sense_errors, [])
            other = [e for e in dri_errors if e[0] != "fnf"]
            self.assertEqual(other, [])

    def test_final_poll_with_all_poison_continues(self):
        """End-of-suite poll: every extension store and config knob is
        poisoned. The poll must return and the good jobs must be seen.
        """
        with tempfile.TemporaryDirectory() as d:
            _poison_stores(d)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET, "workers": 4,
                "resources": {"enabled": True, "threshold": "hot"},
                "dri": {"enabled": True, "channel": "telegram",
                        "triggers": {"resource_pressure": True,
                                     "key_probe": {"threshold": "one"},
                                     "sensor_fused_score": {"threshold": "high"}},
                        "cooldown_sec": "never"},
                "sensors": {"host": {"enabled": True, "key_id": "sense", "weight": "lots"}},
                "output_retention_days": "week", "protected_paths": 5,
                "workspace_root": 5, "judge": "advisory",
            }
            mails = []
            for i in range(4):
                body = sign_payload({
                    "v": 1, "type": "job", "job_id": f"final-{i}",
                    "issued_at": _now(), "kind": "ping",
                }, SECRET)
                mails.append(_mail(f"[HOMING-PIGEON] job final-{i}", body))
            costume = sign_payload({
                "v": 1, "type": "job", "kind": "sensor_alert",
                "job_id": "final-costume", "issued_at": _now(),
                "sensor": "../x", "severity": 5, "title": None, "detail": FLAG,
            }, SECRET)
            mails.append(_mail("[HOMING-PIGEON] job final-costume", costume))
            q = sign_payload({
                "v": 1, "type": "query", "query_id": "final-q",
                "job_id": "nope", "issued_at": _now(),
                "queries": ["bad", {"op": "senses", "sensor": 1}],
            }, SECRET)
            mails.append(_mail("[HOMING-PIGEON] query final-q", q))
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(mails), smtp=_SMTP(), opts=_Opts())
            for i in range(4):
                self.assertIn(f"final-{i}", seen)


class OracleAndKeyPolicyPoisonTest(unittest.TestCase):
    """Oracle chat path and key-policy config under bad data.

    Finding: oracle_context skips non-object and non-JSON retained files.
    record_oracle_turn raises AttributeError on a non-dict ans (unguarded
    .get). The chat path always passes a dict from ask_model, so the
    window is safe. Concurrent append_bounded_log is locked and does not
    raise. build_key_policies raises RuntimeError on a non-numeric
    max_timeout_sec; that is a config-load failure, not a poll failure.
    """

    def test_oracle_context_and_record_tolerate_poison(self):
        from runner.runner import oracle_context, record_oracle_turn, append_bounded_log
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"), exist_ok=True)
            with open(os.path.join(d, "retained", "good.json"), "w") as fh:
                json.dump({"stdout": "hello", "kind": "ping"}, fh)
            with open(os.path.join(d, "retained", "bad.json"), "w") as fh:
                fh.write("[1,2,3]")
            with open(os.path.join(d, "retained", "nope.txt"), "w") as fh:
                fh.write("not json")
            ctx = oracle_context(d)
            self.assertIn("hello", ctx)
            self.assertNotIn("1,2,3", ctx)
            record_oracle_turn(d, {}, "q", None)
            record_oracle_turn(d, {"owner_instructions": 5}, "q", {"answer": FLAG})
            with self.assertRaises(AttributeError):
                record_oracle_turn(d, {}, "q", "not-a-dict")
            errors = []
            def writer(n):
                try:
                    append_bounded_log(os.path.join(d, "oracle-chat.jsonl"),
                                       json.dumps({"n": n, "q": FLAG}))
                except Exception as e:
                    errors.append((n, repr(e)))
            threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(errors, [])
            with open(os.path.join(d, "oracle-chat.jsonl"), encoding="utf-8") as fh:
                self.assertTrue(fh.read())

    def test_key_policies_bad_timeout_raises_at_parse(self):
        """Finding: build_key_policies raises RuntimeError on a non-numeric
        max_timeout_sec. This fails at config load, not during a poll.
        """
        from runner.runner import build_key_policies
        bad = {"key_policies": {"sense": {"max_timeout_sec": "hour"}}}
        with self.assertRaises(RuntimeError):
            build_key_policies(bad)
        self.assertEqual(build_key_policies({}), {})
        self.assertEqual(build_key_policies({"key_policies": None}), {})


class SecurityEventAndConfinementTest(unittest.TestCase):
    """Security-event append and confinement under bad data.

    Finding: _append_security_event only catches OSError. A non-JSON-
    serializable event (a set, a custom object) raises TypeError from
    json.dumps and propagates. The normal poll path passes serializable
    dicts, so it is safe in practice; a caller that passes a bad event
    can abort the cycle. Concurrent normal appends do not raise.
    check_protected_paths returns [] for a non-list protected_paths.
    """

    def test_security_event_non_serializable_raises(self):
        """Finding: json.dumps of a set raises TypeError; the function
        does not catch it. Normal dicts append fine.
        """
        from runner.runner import _append_security_event
        with tempfile.TemporaryDirectory() as d:
            _append_security_event(d, {"type": "ok", "n": 1})
            with self.assertRaises(TypeError):
                _append_security_event(d, {"type": "bad", "data": {1, 2, 3}})
            errors = []
            def worker(n):
                try:
                    _append_security_event(d, {"type": "race", "n": n})
                except Exception as e:
                    errors.append((n, repr(e)))
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(errors, [])

    def test_confinement_and_judge_tolerate_bad_types(self):
        """Finding: check_protected_paths returns [] for a non-list.
        judge_job tolerates a non-string script and a non-list files.
        Neither raises.
        """
        from runner.runner import check_protected_paths, judge_job, snapshot_outside
        self.assertEqual(check_protected_paths({}, {}, 5), [])
        self.assertEqual(check_protected_paths({}, {}, "not-a-list"), [])
        self.assertEqual(check_protected_paths({}, {}, [5, None, ""]), [])
        verdict, reasons = judge_job({"judge": "enforce"}, {"script": {"bad": True}, "files": "nope"})
        self.assertEqual(verdict, "pass")
        self.assertEqual(snapshot_outside(5), {})
        self.assertEqual(snapshot_outside(None), {})


class AttestAndQueryBudgetTest(unittest.TestCase):
    """Attestation and query-budget paths under bad data.

    Finding: answer_queries does spent = int(already_spent or 0) with no
    try/except. A non-numeric already_spent raises ValueError. The poll
    path always passes an int, so it is safe in practice.
    build_attestations assumes every query is a dict and that ctx has
    exit_code/digest/patterns. A non-dict query raises AttributeError;
    a missing key raises KeyError. answer_queries filters non-dicts
    before calling, so the query path is safe; a direct caller is not.
    """

    def test_answer_queries_bad_already_spent_raises(self):
        """Finding: int(already_spent) is unguarded. "lots" raises ValueError.
        A normal int or None does not.
        """
        from runner.runner import answer_queries
        with self.assertRaises(ValueError):
            answer_queries([], {}, {}, 8, already_spent="lots")
        answers, spent = answer_queries([], {}, {}, 8, already_spent=0)
        self.assertEqual(spent, 0)
        answers, spent = answer_queries([], {}, {}, 8, already_spent=None)
        self.assertEqual(spent, 0)

    def test_build_attestations_bad_query_and_ctx_raise(self):
        """Finding: build_attestations does q.get without an isinstance
        check, and indexes ctx["exit_code"] / ctx["patterns"] directly.
        Non-dict query -> AttributeError. Missing key -> KeyError.
        """
        from runner.runner import build_attestations
        with self.assertRaises(AttributeError):
            build_attestations(["not-a-dict"], {"exit_code": 0, "digest": "x", "patterns": {}})
        with self.assertRaises(KeyError):
            build_attestations([{"op": "attest", "predicate": "exit_zero"}], {})
        atts = build_attestations(
            [{"op": "attest", "predicate": "exit_zero"}],
            {"exit_code": 0, "digest": "abc", "patterns": {}},
        )
        self.assertEqual(atts[0]["ok"], True)


class ResultPolicyAndSensesLoadTest(unittest.TestCase):
    """Result policy and senses load under bad types.

    Finding: apply_result_policy does job.get and exec_result.get without
    an isinstance check after the first policy lookup. A non-dict job or
    exec_result raises AttributeError. patterns.items() in the redacted
    path also assumes a dict. The poll path always passes dicts, so it
    is safe in practice.
    senses.load_alerts does out[-int(limit):] with no try/except. A
    non-numeric limit raises ValueError. The query path guards the type;
    a direct call does not.
    """

    def test_apply_result_policy_bad_types_raise(self):
        """Finding: non-dict job or exec_result raises AttributeError.
        Non-dict patterns raises AttributeError on the redacted path.
        """
        from runner.runner import apply_result_policy
        with self.assertRaises(AttributeError):
            apply_result_policy({}, "not-a-job", {}, {}, False)
        with self.assertRaises(AttributeError):
            apply_result_policy({}, {"job_id": "x"}, "not-a-result", {}, False)
        with self.assertRaises(AttributeError):
            apply_result_policy(
                {"max_result_view": "redacted"},
                {"job_id": "x", "result_policy": {"view": "redacted"}},
                {"stdout": "hi", "stderr": ""},
                "not-a-dict",
                False,
            )
        result, retain = apply_result_policy(
            {}, {"job_id": "ok"}, {"stdout": "hi", "stderr": "", "exit_code": 0}, {}, False,
        )
        self.assertIn("stdout", result)

    def test_senses_load_alerts_bad_limit_raises(self):
        """Finding: int(limit) is unguarded. "many" raises ValueError.
        An int or None does not.
        """
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "senses.jsonl"), "w") as fh:
                fh.write(json.dumps({"sensor": "s", "severity": "info"}) + "\n")
            with self.assertRaises(ValueError):
                senses.load_alerts(d, limit="many")
            self.assertIsInstance(senses.load_alerts(d, limit=5), list)
            self.assertIsInstance(senses.load_alerts(d, limit=None), list)


class RedactPatternsAndQueryRateTest(unittest.TestCase):
    """Redaction config and query-rate paths under bad types.

    Finding: _redact_patterns does extra.items() without checking that
    redact_patterns_extra is a dict. A list or string raises AttributeError.
    handle_mail catches Exception and logs "will retry"; the job is not
    marked seen, so it will be retried forever. Other jobs continue.
    _query_limit returns -1 for a non-numeric cap (refuse rather than
    treat as unlimited). _live_times skips non-numeric timestamps.
    """

    def test_redact_patterns_bad_extra_raises_but_poll_continues(self):
        """Finding: non-dict redact_patterns_extra raises AttributeError
        inside handle_mail. The except logs will-retry and does not mark
        the job seen. The poll returns (no crash).
        """
        from runner.runner import _redact_patterns
        with self.assertRaises(AttributeError):
            _redact_patterns({"redact_patterns_extra": ["bad"]})
        with self.assertRaises(AttributeError):
            _redact_patterns({"redact_patterns_extra": "not-a-dict"})
        self.assertIsInstance(_redact_patterns({}), dict)
        self.assertIsInstance(_redact_patterns({"redact_patterns_extra": None}), dict)
        with tempfile.TemporaryDirectory() as d:
            bad = sign_payload({
                "v": 1, "type": "job", "job_id": "redact-bad",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            good = sign_payload({
                "v": 1, "type": "job", "job_id": "redact-ok",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET, "workers": 2,
                "redact_patterns_extra": [1, 2, 3],
            }
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([
                          _mail("[HOMING-PIGEON] job redact-bad", bad),
                          _mail("[HOMING-PIGEON] job redact-ok", good),
                      ]),
                      smtp=_SMTP(), opts=_Opts())
            self.assertIsInstance(seen, dict)

    def test_query_limit_and_live_times_tolerate_bad_types(self):
        """Finding: _query_limit returns -1 for a non-numeric cap.
        _live_times skips non-numeric timestamps. Neither raises.
        """
        from runner.runner import _query_limit, _live_times
        self.assertEqual(_query_limit({"max_queries_per_hour": "lots"}), -1)
        self.assertEqual(_query_limit({"max_queries_per_hour": None}), 0)
        self.assertEqual(_query_limit({}), 0)
        now = time.time()
        live = _live_times([now - 10, "bad", None, now - 4000], now)
        self.assertEqual(len(live), 1)
        self.assertEqual(_live_times("not-a-list", now), [])


class RateLimitAndWriteJsonRaceTest(unittest.TestCase):
    """Query rate-limit and _write_json under concurrency.

    Finding: check_rate_limit loads, mutates, and writes without a lock.
    _write_json uses a deterministic path.tmp name. Concurrent calls on
    the same path can raise FileNotFoundError on the replace, or lose
    updates. handle_mail catches the exception and logs will-retry.
    The rate limit can be exceeded under concurrency because updates
    can be overwritten.
    """

    def test_concurrent_rate_limit_can_race_or_lose_updates(self):
        """Finding: concurrent check_rate_limit on the same path may
        raise FileNotFoundError or lose window updates. Neither stops
        the process; the caller catches or the poll retries.
        """
        from runner.runner import check_rate_limit
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "query_times.json")
            cfg = {"max_queries_per_hour": 100}
            errors = []
            def worker(n):
                try:
                    check_rate_limit(f"key-{n % 3}", cfg, path)
                except FileNotFoundError as e:
                    errors.append(("fnf", repr(e)))
                except Exception as e:
                    errors.append(("other", repr(e)))
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            other = [e for e in errors if e[0] != "fnf"]
            self.assertEqual(other, [])
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                self.assertIsInstance(data, dict)

    def test_write_json_bad_object_raises(self):
        """Finding: _write_json does json.dump with no try/except.
        A non-serializable object raises TypeError. Normal dicts write.
        """
        from runner.runner import _write_json
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ok.json")
            _write_json(path, {"a": 1})
            self.assertTrue(os.path.isfile(path))
            with self.assertRaises(TypeError):
                _write_json(path, {"bad": {1, 2}})


class SensesGateAndStorePoisonTest(unittest.TestCase):
    """Senses gate and store under bad profile and record types.

    Finding: senses.gate_alert does unguarded float() on cooldown_sec
    and max_per_hour. A non-numeric profile value raises ValueError.
    The sensor alert path does not catch it, so the job is left for
    retry. store_alert does unguarded json.dumps. A non-serializable
    record raises TypeError, which is not caught by the OSError
    handler around the call. Concurrent store_alert appends do not
    raise on normal dicts.
    """

    def test_gate_alert_bad_profile_raises(self):
        """Finding: float(cooldown_sec) and float(max_per_hour) are
        unguarded. "hot" and "lots" raise ValueError.
        """
        with self.assertRaises(ValueError):
            senses.gate_alert({"profile": {"cooldown_sec": "hot"}}, {"title": "t"}, [])
        with self.assertRaises(ValueError):
            senses.gate_alert({"profile": {"max_per_hour": "lots"}}, {"title": "t"}, [])
        self.assertIsNone(senses.gate_alert({"profile": {"cooldown_sec": 0, "max_per_hour": 0}}, {"title": "t"}, []))

    def test_store_alert_non_serializable_raises(self):
        """Finding: json.dumps of a set raises TypeError. The OSError
        handler in the sensor path does not catch it. Concurrent
        normal appends do not raise.
        """
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(TypeError):
                senses.store_alert(d, {"sensor": "s", "detail": {1, 2}})
            errors = []
            def worker(n):
                try:
                    senses.store_alert(d, {"sensor": f"s{n}", "title": f"t{n}"})
                except Exception as e:
                    errors.append((n, repr(e)))
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(errors, [])


class BoardSaveAndSeenRaceTest(unittest.TestCase):
    """Board.save and seen-dict mutation under concurrency.

    Finding: Board.save uses a deterministic path.tmp name and is not
    locked (only offer takes _BOARD_LOCK). Concurrent save calls can
    raise FileNotFoundError on the replace or lose updates. The seen
    dict is mutated under _MAIL_LOCK in the poll path, so concurrent
    mark-seen is safe. A direct concurrent mutation of seen without
    the lock can lose entries.
    """

    def test_concurrent_board_save_can_race(self):
        """Finding: concurrent Board.save on the same path may raise
        FileNotFoundError or lose task updates. The process does not
        crash; the race is the finding.
        """
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            board = Board(path)
            errors = []
            def worker(n):
                try:
                    board.tasks[f"t{n}"] = {"task_id": f"t{n}", "state": "open"}
                    board.save()
                except FileNotFoundError as e:
                    errors.append(("fnf", repr(e)))
                except Exception as e:
                    errors.append(("other", repr(e)))
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            other = [e for e in errors if e[0] != "fnf"]
            self.assertEqual(other, [])
            if os.path.isfile(path):
                loaded = Board(path)
                self.assertIsInstance(loaded.tasks, dict)

    def test_concurrent_seen_mutation_under_lock_does_not_raise(self):
        """Finding: the poll path mutates seen under _MAIL_LOCK.
        Concurrent locked updates do not raise. An unlocked concurrent
        mutation can lose entries (dict is not atomic for compound ops).
        """
        from runner.runner import _MAIL_LOCK
        seen = {}
        errors = []
        def worker(n):
            try:
                with _MAIL_LOCK:
                    seen[f"k{n}"] = True
            except Exception as e:
                errors.append((n, repr(e)))
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(len(seen), 20)


class PruneAndSensesRewriteRaceTest(unittest.TestCase):
    """prune_retained and senses rewrite under concurrency.

    Finding: prune_retained walks the retained dir and removes old
    files without a lock. Concurrent save_retained can race with the
    remove (the file can be deleted after the writer opens the .tmp,
    or the writer can recreate a file prune just removed). Neither
    raises; the race can lose a retained output. senses.store_alert
    appends then rewrites the whole file when over the cap. Concurrent
    append + rewrite can interleave lines or drop entries. Neither
    raises; the race is the finding.
    """

    def test_concurrent_prune_and_save_retained_do_not_raise(self):
        """Finding: prune and save_retained concurrent on the same
        dir do not raise. A retained file can be lost to the race.
        """
        from runner.runner import save_retained, prune_retained
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"), exist_ok=True)
            old = time.time() - 86400 * 30
            for i in range(5):
                pth = os.path.join(d, "retained", f"old-{i}.json")
                with open(pth, "w") as fh:
                    fh.write("{}")
                os.utime(pth, (old, old))
            errors = []
            def saver(n):
                try:
                    save_retained(d, f"new-{n}", {"stdout": n, "saved_at": time.time()})
                except Exception as e:
                    errors.append(("save", n, repr(e)))
            def pruner():
                try:
                    prune_retained(d, 7)
                except Exception as e:
                    errors.append(("prune", repr(e)))
            threads = [threading.Thread(target=saver, args=(i,)) for i in range(8)]
            threads.append(threading.Thread(target=pruner))
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(errors, [])

    def test_concurrent_senses_append_and_rewrite_do_not_raise(self):
        """Finding: concurrent store_alert with a small cap can
        interleave the append and the rewrite. Neither raises.
        """
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "senses.jsonl")
            with open(path, "w") as fh:
                for i in range(100):
                    fh.write(json.dumps({"sensor": f"seed{i}"}) + "\n")
            errors = []
            def worker(n):
                try:
                    senses.store_alert(d, {"sensor": f"s{n}", "title": f"t{n}"})
                except Exception as e:
                    errors.append((n, repr(e)))
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(errors, [])
            with open(path, encoding="utf-8") as fh:
                self.assertTrue(fh.read())


class SameJobIdWorkDirRaceTest(unittest.TestCase):
    """Same job_id concurrent execute_job under no _IN_FLIGHT.

    Finding: the poll path uses _IN_FLIGHT to stop two threads from
    running the same job_id. A direct concurrent call to execute_job
    with the same job_id races on the work dir (rmtree vs makedirs).
    The race can raise OSError (caught as JobRejected) or produce a
    work dir that one thread sees as missing. Neither crashes the
    process; the race is the finding.
    """

    def test_concurrent_execute_job_same_id_does_not_crash_process(self):
        """Finding: concurrent execute_job on the same job_id may
        raise OSError/JobRejected from the rmtree/makedirs race.
        The process continues.
        """
        from runner.runner import execute_job, JobRejected
        with tempfile.TemporaryDirectory() as d:
            errors = []
            def worker(n):
                try:
                    execute_job({"workers": 1}, {
                        "job_id": "same-id",
                        "kind": "ping",
                    }, d)
                except JobRejected as e:
                    errors.append(("rejected", repr(e)))
                except OSError as e:
                    errors.append(("os", repr(e)))
                except Exception as e:
                    errors.append(("other", repr(e)))
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            other = [e for e in errors if e[0] not in ("rejected", "os")]
            self.assertEqual(other, [])
            work = os.path.join(d, "work", "same-id")
            if os.path.exists(work):
                self.assertTrue(os.path.isdir(work))


class AskModelAndDownloadRaceTest(unittest.TestCase):
    """ask_model timeout and concurrent download dest under bad data.

    Finding: ask_model does timeout = int(cfg.get("timeout_sec") or 60)
    with no try/except. A non-numeric timeout_sec raises ValueError
    before the inference call. inference_config guards the type, so
    the poll path is safe; a direct call is not. Concurrent download
    to the same dest can interleave writes. The poll path uses unique
    work dirs, so the race is only on a direct call.
    """

    def test_ask_model_bad_timeout_raises(self):
        """Finding: int(timeout_sec) is unguarded. "hour" raises ValueError.
        A normal int or None does not raise before the call.
        """
        from runner.runner import ask_model
        with self.assertRaises(ValueError):
            ask_model({"endpoint": "http://127.0.0.1:1", "model": "m",
                       "timeout_sec": "hour"}, "q", "out", 100)
        ans = ask_model({"endpoint": "http://127.0.0.1:1", "model": "m",
                         "timeout_sec": 1}, "q", "out", 100)
        self.assertEqual(ans.get("rejected"), "inference_error")

    def test_concurrent_download_same_dest_does_not_crash_process(self):
        """Finding: concurrent download to the same dest may interleave
        writes. The process does not crash. The poll path uses unique
        work dirs, so this is a direct-call race.
        """
        from runner.runner import download, JobRejected
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "out.bin")
            errors = []
            def worker(n):
                try:
                    download("file:///etc/passwd", dest)
                except JobRejected:
                    pass
                except Exception as e:
                    errors.append((n, repr(e)))
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(errors, [])


class WindowsNameAndKillTreeTest(unittest.TestCase):
    """Windows reserved names and kill_tree under bad input.

    Finding: windows_reserved_name does name.replace without a type
    check. A non-string name raises AttributeError. The file staging
    path checks isinstance(name, str) before calling, so the poll
    path is safe. kill_tree catches Exception around the kill. A
    None or non-Popen does not crash the process.
    """

    def test_windows_reserved_name_bad_type_raises(self):
        """Finding: non-string name raises AttributeError. Normal
        strings return a bool.
        """
        from runner.runner import windows_reserved_name
        with self.assertRaises(AttributeError):
            windows_reserved_name(5)
        with self.assertRaises(AttributeError):
            windows_reserved_name(None)
        self.assertIsInstance(windows_reserved_name("CON"), bool)
        self.assertIsInstance(windows_reserved_name("safe.txt"), bool)

    def test_kill_tree_bad_proc_does_not_raise(self):
        """Finding: kill_tree catches Exception. None and a non-Popen
        do not propagate.
        """
        from runner.runner import kill_tree
        kill_tree(None)
        kill_tree("not-a-proc")
        self.assertTrue(True)


class ConcurrentKillTreeAndSetupTest(unittest.TestCase):
    """Concurrent kill_tree and setup config under bad input.

    Finding: kill_tree catches Exception around the kill. Concurrent
    calls on None and non-Popen do not raise. setup._blank_config
    starts from the example or a fallback dict. A missing example
    does not raise; the fallback has the Gmail endpoints.
    """

    def test_concurrent_kill_tree_does_not_raise(self):
        """Finding: concurrent kill_tree on None and non-Popen do
        not raise. The process continues.
        """
        from runner.runner import kill_tree
        errors = []
        def worker(n):
            try:
                kill_tree(None)
                kill_tree("not-a-proc")
                kill_tree(5)
            except Exception as e:
                errors.append((n, repr(e)))
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertEqual(errors, [])

    def test_blank_config_missing_example_does_not_raise(self):
        """Finding: _blank_config returns a dict even when the
        example is missing. The fallback has the Gmail endpoints.
        """
        from runner.setup import _blank_config
        cfg = _blank_config()
        self.assertIsInstance(cfg, dict)
        self.assertIn("imap_host", cfg)
        self.assertIn("smtp_host", cfg)


class ConcurrentOracleContextAndBoardLoadTest(unittest.TestCase):
    """Concurrent oracle_context and Board.load under poison.

    Finding: concurrent oracle_context against a poisoned retained
    dir does not raise. Non-JSON and non-object files are skipped.
    Concurrent Board.load against a file that is being rewritten
    does not raise. A torn write returns an empty tasks dict.
    """

    def test_concurrent_oracle_context_does_not_raise(self):
        """Finding: concurrent oracle_context on a poisoned retained
        dir does not raise. The process continues.
        """
        from runner.runner import oracle_context
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"), exist_ok=True)
            with open(os.path.join(d, "retained", "good.json"), "w") as fh:
                json.dump({"stdout": "hello", "kind": "ping"}, fh)
            with open(os.path.join(d, "retained", "bad.json"), "w") as fh:
                fh.write("not json")
            with open(os.path.join(d, "retained", "list.json"), "w") as fh:
                fh.write("[1,2,3]")
            errors = []
            def worker(n):
                try:
                    oracle_context(d)
                except Exception as e:
                    errors.append((n, repr(e)))
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(errors, [])

    def test_concurrent_board_load_does_not_raise(self):
        """Finding: concurrent Board.load against a file that is
        being rewritten does not raise. A torn write returns an
        empty tasks dict.
        """
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            board = Board(path)
            errors = []
            def loader(n):
                try:
                    board.load()
                except Exception as e:
                    errors.append((n, repr(e)))
            def writer(n):
                try:
                    board.tasks[f"t{n}"] = {"task_id": f"t{n}", "state": "open"}
                    board.save()
                except FileNotFoundError:
                    pass
                except Exception as e:
                    errors.append(("w", n, repr(e)))
            threads = [threading.Thread(target=loader, args=(i,)) for i in range(6)]
            threads += [threading.Thread(target=writer, args=(i,)) for i in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(errors, [])
            self.assertIsInstance(board.tasks, dict)


class RetainedExpiredAndSecretScanTest(unittest.TestCase):
    """retained_expired and secret_scan under bad types.

    Finding: retained_expired does data.get without a type check.
    A non-dict data raises AttributeError. The prune path checks
    the type before calling, so the poll path is safe. secret_scan
    does (patterns or BUILTIN).items() without a type check. A
    list raises AttributeError. The poll path always passes a dict.
    """

    def test_retained_expired_bad_data_raises(self):
        """Finding: non-dict data raises AttributeError. A normal
        dict returns a bool.
        """
        from runner.runner import retained_expired
        with self.assertRaises(AttributeError):
            retained_expired("not-a-dict", {})
        with self.assertRaises(AttributeError):
            retained_expired(5, {})
        self.assertIsInstance(retained_expired({"saved_at": 0}, {}), bool)
        self.assertIsInstance(retained_expired({"saved_at": "bad"}, {}), bool)

    def test_secret_scan_bad_patterns_raises(self):
        """Finding: non-dict patterns raises AttributeError. A
        normal dict returns a list.
        """
        from runner.runner import secret_scan
        with self.assertRaises(AttributeError):
            secret_scan("text", ["bad"])
        with self.assertRaises(AttributeError):
            secret_scan("text", "not-a-dict")
        self.assertIsInstance(secret_scan("text", {}), list)
        self.assertIsInstance(secret_scan("text", None), list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
