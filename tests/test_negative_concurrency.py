#!/usr/bin/env python3
"""Negative concurrency and extension-poison resilience.

Findings documented here (2026-10-15 simulation in virtual environment):

1. Concurrent mixed good/poison mails (ThreadPoolExecutor path):
   One worker raising on a poisoned retained/query or bad board task
   must not prevent other workers from completing, and poll_once must
   not raise for cases already classified as poison/reject.

2. Malformed extension state files (senses.jsonl, dri-state.json,
   resources.json, security-events.jsonl, board.json, retained/*.json,
   query_times.json):
   Empty files, truncated JSON, non-UTF8 bytes, lists where objects
   expected, numeric/string type confusion, and extreme values must
   be ignored or logged, never crash the poll or Oracle answer path.

3. Oracle / confinement / ask paths with poisoned retained output
   (numeric stdout, null fields, wrong-type view/budget) continue
   and redact rather than raise.

4. Sensor alerts with invalid shapes (wrong types, path traversal
   names, non-dict detail) are rejected without execution or crash.

All cases below are expected to pass (graceful). Failures indicate
a real crash path that must be hardened.
"""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import dri, resources  # noqa: E402
from runner.runner import (  # noqa: E402
    Board,
    _redact_patterns,
    answer_queries,
    poll_once,
    sign_payload,
)

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"
FLAG = "FLAG-CRED-9f3c2a7e1"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _MultiIMAP:
    """Feeds multiple raw messages on successive fetches."""
    def __init__(self, raws):
        self.raws = list(raws)
        self.n = 0

    def search(self, *args):
        ids = [str(i + 1).encode() for i in range(len(self.raws))]
        return "OK", [b" ".join(ids)] if ids else [b""]

    def fetch(self, num, what):
        idx = int(num) - 1
        if 0 <= idx < len(self.raws):
            return "OK", [(b"%d (RFC822)" % int(num), self.raws[idx])]
        return "OK", []

    def store(self, *args, **kwargs):
        return "OK", []


class _SMTP:
    def sendmail(self, *args, **kwargs):
        return None


class _Opts:
    dry_run = False
    no_send = True
    workers = 4


class ConcurrentPoisonTest(unittest.TestCase):
    """Finding: concurrent workers processing mixed poison and good jobs
    must all complete; poll_once returns without raising.
    """

    def test_mixed_poison_and_ping_do_not_crash_poll(self):
        with tempfile.TemporaryDirectory() as d:
            # Poison: numeric task_id on board
            bad_body = sign_payload({
                "v": 1, "type": "task_submit", "issued_at": _now(),
                "task_id": 999, "priority": "high",
            }, SECRET)
            # Good ping
            good_body = sign_payload({
                "v": 1, "type": "job", "job_id": "good-ping",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            # Poison: query against missing/poisoned retained
            q_body = sign_payload({
                "v": 1, "type": "query", "query_id": "q-bad",
                "job_id": "missing", "issued_at": _now(),
                "queries": [{"op": "grep", "pattern": "("}],
            }, SECRET)
            raws = [
                _mail("[HOMING-PIGEON] task_submit b1", bad_body),
                _mail("[HOMING-PIGEON] job good-ping", good_body),
                _mail("[HOMING-PIGEON] query q-bad", q_body),
            ]
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "workers": 4,
            }
            seen = {}
            # Must not raise
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Opts())
            self.assertIn("good-ping", seen)


class MalformedExtensionStateTest(unittest.TestCase):
    """Finding: poisoned on-disk extension state (wrong types, truncated,
    binary, empty) is ignored; poll and DRI/resources continue.
    """

    def test_empty_truncated_binary_state_files_do_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            # Empty
            open(os.path.join(d, "senses.jsonl"), "w").close()
            open(os.path.join(d, "security-events.jsonl"), "w").close()
            # Truncated JSON
            with open(os.path.join(d, "dri-state.json"), "w") as fh:
                fh.write('{"last_check":')
            # Binary / non-UTF8
            with open(os.path.join(d, "resources.json"), "wb") as fh:
                fh.write(b"\xff\xfe not json")
            # Wrong top-level type
            with open(os.path.join(d, "board.json"), "w") as fh:
                json.dump(["not", "a", "board"], fh)
            # Extreme / wrong types in retained
            os.makedirs(os.path.join(d, "retained"))
            with open(os.path.join(d, "retained", "job-x.json"), "w") as fh:
                json.dump({
                    "stdout": 42, "stderr": None, "view": True,
                    "budget": float("inf"), "spent": "many",
                    "patterns": "not-a-dict", "saved_at": "yesterday",
                }, fh)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "resources": {"enabled": True, "threshold": 0.0},
                "dri": {"enabled": True, "channel": "telegram"},
            }
            # Resource check and DRI must not raise
            event = resources.check_resources(cfg, d)
            self.assertTrue(event is None or isinstance(event, dict))
            with mock.patch.object(dri, "_send", return_value=False):
                dri.maybe_page(cfg, d)
            # A ping still works
            body = sign_payload({
                "v": 1, "type": "job", "job_id": "still-works",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            raw = _mail("[HOMING-PIGEON] job still-works", body)
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([raw]), smtp=_SMTP(), opts=_Opts())

    def test_oracle_answers_on_poisoned_retained(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            with open(os.path.join(d, "retained", "job-p.json"), "w") as fh:
                json.dump({
                    "stdout": 12345, "stderr": {"bad": True},
                    "exit_code": "zero", "view": 99, "budget": "lots",
                    "patterns": [1, 2], "saved_at": time.time(),
                }, fh)
            cfg = {"redact_patterns_extra": {"flag": r"FLAG-CRED"}}
            answers, spent = answer_queries(
                [{"op": "grep", "pattern": "x"}, {"op": "attest", "predicate": "exit_zero"}],
                {"stdout": "", "stderr": "", "exit_code": 0},
                _redact_patterns(cfg),
                budget=4,
                cfg=cfg,
                view="attested",
                base_dir=d,
            )
            self.assertIsInstance(answers, list)
            self.assertGreaterEqual(spent, 0)


class SensorShapePoisonTest(unittest.TestCase):
    """Finding: sensor_alert jobs with wrong-type fields or path-like
    names are rejected before store/execute; no crash, no side effects.
    """

    def test_bad_sensor_shapes_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            jobs = [
                {  # wrong types
                    "v": 1, "type": "job", "kind": "sensor_alert",
                    "job_id": "bad-types", "issued_at": _now(),
                    "sensor": 5, "severity": ["high"], "title": None,
                    "detail": "string-detail",
                },
                {  # path traversal
                    "v": 1, "type": "job", "kind": "sensor_alert",
                    "job_id": "trav", "issued_at": _now(),
                    "sensor": "../etc/passwd", "severity": "critical",
                    "title": "x", "detail": FLAG,
                },
            ]
            raws = []
            for j in jobs:
                raws.append(_mail(
                    f"[HOMING-PIGEON] job {j['job_id']}",
                    sign_payload(j, SECRET),
                ))
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "sensors": {
                    "host_ids": {
                        "enabled": True,
                        "key_id": "default",
                        "weight": 1.0,
                    },
                },
            }
            # Must not raise; nothing executed
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Opts())
            self.assertFalse(os.path.exists(os.path.join(d, "work")))
            # senses.jsonl either missing or contains no FLAG
            path = os.path.join(d, "senses.jsonl")
            if os.path.exists(path):
                with open(path, encoding="utf-8", errors="replace") as fh:
                    self.assertNotIn(FLAG, fh.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)


class OracleAndConfinementPoisonTest(unittest.TestCase):
    """Finding: Oracle answer path, confinement snapshots, and retained
    loads tolerate extreme bad data without raising.
    """

    def test_answer_queries_rejects_non_objects_and_bad_ops(self):
        answers, spent = answer_queries(
            ["not-dict", None, 5, {"op": "unknown_xyz"},
             {"op": "grep", "pattern": None}, {"op": "tail", "n": "lots"}],
            {"stdout": None, "stderr": 1, "exit_code": "x"},
            {}, budget=10, view="attested",
        )
        self.assertIsInstance(answers, list)
        self.assertGreaterEqual(spent, 0)
        # No crash; rejects or empty answers only
        for a in answers:
            self.assertIsInstance(a, dict)

    def test_confinement_snapshot_tolerates_bad_roots(self):
        from runner.runner import snapshot_outside, confinement_violated
        with tempfile.TemporaryDirectory() as d:
            # nonexistent
            before = snapshot_outside(os.path.join(d, "missing"))
            self.assertIsInstance(before, dict)
            # file used as root
            fpath = os.path.join(d, "afile")
            open(fpath, "w").close()
            before = snapshot_outside(fpath)
            self.assertIsInstance(before, dict)
            # empty string
            before = snapshot_outside("")
            self.assertIsInstance(before, dict)
            # confinement check on empties
            self.assertFalse(confinement_violated({}, {}))

    def test_load_retained_poison_returns_none(self):
        from runner.runner import load_retained
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            cases = [
                ("bad", "not json at all"),
                ("list", "[1, 2, 3]"),
                ("null", "null"),
                ("num", "42"),
                ("empty", ""),
                ("trunc", '{"stdout":'),
            ]
            for name, content in cases:
                with open(os.path.join(d, "retained", f"{name}.json"), "w") as fh:
                    fh.write(content)
                self.assertIsNone(load_retained(d, name))

    def test_board_rejects_non_dict_and_bad_offer(self):
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            ok, reason = board.submit("not a dict")
            self.assertFalse(ok)
            ok, reason = board.submit(None)
            self.assertFalse(ok)
            # offer with garbage capabilities
            self.assertIsNone(board.offer("w1", "not-a-list"))
            self.assertIsNone(board.offer("w1", None))
            self.assertIsNone(board.offer("w1", 5))
            # still usable
            ok, reason = board.submit({"task_id": "ok-1", "priority": 1})
            self.assertTrue(ok)


class ConcurrentQueryPoisonTest(unittest.TestCase):
    """Finding: concurrent query mails against missing or poisoned
    retained stores do not raise and do not stop other processing.
    """

    def test_many_bad_queries_do_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            raws = []
            for i in range(8):
                body = sign_payload({
                    "v": 1, "type": "query", "query_id": f"q{i}",
                    "job_id": f"missing-{i}", "issued_at": _now(),
                    "queries": [
                        {"op": "grep", "pattern": "("},
                        "not-an-object",
                        {"op": "senses", "sensor": 99},
                    ],
                }, SECRET)
                raws.append(_mail(f"[HOMING-PIGEON] query q{i}", body))
            # also a good ping so we confirm the poll still processes
            ping = sign_payload({
                "v": 1, "type": "job", "job_id": "still-alive",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            raws.append(_mail("[HOMING-PIGEON] job still-alive", ping))
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "workers": 4,
                "max_queries_per_hour": 0,
            }
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Opts())
            self.assertIn("still-alive", seen)


class ExtremeExtensionStateTest(unittest.TestCase):
    """Finding: extreme values (NaN-like, huge strings, deeply nested)
    in extension stores are ignored; processing continues.
    """

    def test_extreme_values_in_state_do_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            # huge line in jsonl
            with open(os.path.join(d, "senses.jsonl"), "w") as fh:
                fh.write(json.dumps({"sensor": "x", "detail": "A" * 100000}) + "\n")
                fh.write("not json\n")
                fh.write(json.dumps({"severity": float("nan")}) + "\n")
            # dri with extreme cooldown
            with open(os.path.join(d, "dri-state.json"), "w") as fh:
                json.dump({
                    "last_check": 1e30,
                    "last_page": {"k": -1e9},
                    "pending_digest": [None, "x", 5],
                }, fh)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "resources": {"enabled": True, "threshold": 0.5},
                "dri": {"enabled": True, "channel": "telegram",
                        "cooldown_sec": 0},
            }
            event = resources.check_resources(cfg, d)
            self.assertTrue(event is None or isinstance(event, dict))
            with mock.patch.object(dri, "_send", return_value=False):
                dri.maybe_page(cfg, d)
            # poll still works
            body = sign_payload({
                "v": 1, "type": "job", "job_id": "after-extreme",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([_mail("[HOMING-PIGEON] job after-extreme", body)]),
                      smtp=_SMTP(), opts=_Opts())


class ResultPolicyPoisonTest(unittest.TestCase):
    """Finding (2026-10-15): apply_result_policy crashed on non-string
    stdout/stderr (int + str). A poisoned or extension-supplied result
    dict with numeric stdout stopped the poll. Coercion to str makes
    it fail gracefully; the digest is still computed and the view is
    applied.
    """

    def test_non_string_stdout_stderr_do_not_raise(self):
        from runner.runner import apply_result_policy
        cases = [
            {"stdout": 42, "stderr": None, "exit_code": 0},
            {"stdout": None, "stderr": 99, "exit_code": 1},
            {"stdout": ["a"], "stderr": {"b": 1}, "exit_code": "x"},
            {"stdout": True, "stderr": False, "exit_code": 0},
        ]
        for er in cases:
            out, retain = apply_result_policy(
                {}, {"job_id": "p", "kind": "exec", "result_policy": {"view": "summary"}},
                er, {}, confined=None,
            )
            self.assertIsInstance(out, dict)
            self.assertIn("output_digest", out)
            self.assertIn("view", out)
            # full view path also must not raise
            out2, _ = apply_result_policy(
                {}, {"job_id": "p", "kind": "exec"},
                er, {}, confined=None,
            )
            self.assertIsInstance(out2, dict)
            self.assertIn("output_digest", out2)


class RedactPatternPoisonTest(unittest.TestCase):
    """Finding (2026-10-15): redact_text and secret_scan raised TypeError
    when a pattern value was None, an int, or a list. A broken extension
    that put the wrong type in the pattern map crashed the Oracle.

    After the fix, non-string patterns are skipped. Processing continues.
    """

    def test_non_string_patterns_are_skipped(self):
        from runner.runner import redact_text, secret_scan, secret_fragment_hit
        bad = {"ok": r"FLAG", "none": None, "num": 5, "lst": ["a"], "obj": {}}
        text = "hello FLAG world"
        out, families = redact_text(text, bad)
        self.assertIn("[REDACTED:ok]", out)
        self.assertIn("ok", families)
        self.assertNotIn("none", families)
        hits = secret_scan(text, bad)
        self.assertIn("ok", hits)
        self.assertFalse(secret_fragment_hit("FLAG", text, bad) is None)
        # answer_queries path also survives
        answers, spent = answer_queries(
            [{"op": "grep", "pattern": "x"}],
            {"stdout": text, "stderr": ""},
            bad, budget=2,
        )
        self.assertIsInstance(answers, list)


class ConcurrentBoardAndSensesTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. Board.submit mutated self.tasks without the lock while
       _offer_unlocked iterated values(). Concurrent hammer raised
       RuntimeError: dictionary changed size during iteration.
       Also Board.save used a fixed .tmp name, so concurrent saves
       raced with FileNotFoundError on replace.

    2. senses.load_alerts did int(limit) with no guard. limit="bad"
       raised ValueError and stopped the caller.

    Both are hardened. Concurrent submit/offer and bad limit now
    complete without raising.
    """

    def test_concurrent_board_submit_and_offer_do_not_raise(self):
        import threading
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            errors = []

            def hammer():
                for i in range(25):
                    try:
                        board.submit({
                            "task_id": f"t{threading.get_ident()}-{i}",
                            "priority": i,
                        })
                        board.offer(f"w{threading.get_ident()}", ["shell"])
                        board.submit("not-a-dict")
                        board.offer("w", None)
                    except Exception as e:
                        errors.append(e)

            threads = [threading.Thread(target=hammer) for _ in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            # board remains usable
            ok, _ = board.submit({"task_id": "after-hammer"})
            self.assertTrue(ok)

    def test_load_alerts_bad_limit_does_not_raise(self):
        from runner import senses
        with tempfile.TemporaryDirectory() as d:
            senses.store_alert(d, {
                "sensor": "host_ids", "severity": "info",
                "title": "x", "detail": {},
            })
            self.assertIsInstance(senses.load_alerts(d, limit="bad"), list)
            self.assertIsInstance(senses.load_alerts(d, limit=None), list)
            self.assertIsInstance(senses.load_alerts(d, limit=-1), list)
            self.assertIsInstance(senses.load_alerts(d, sensor=5), list)


class OraclePolicyPoisonTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. confinement_violated assumed before/after were dicts. Passing a
       string raised AttributeError and stopped the caller.
    2. judge_job assumed cfg and job were dicts. None raised
       AttributeError.
    3. build_attestations iterated queries and called .get on each
       item. A string queries value ("bad") made q a character and
       raised AttributeError inside apply_result_policy.
    4. apply_result_policy redacted branch called re.search on
       non-string patterns without a guard.
    5. query_budget returned a negative ceiling when max_query_budget
       was negative.

    All hardened. Poison inputs now return safe defaults and do not
    stop processing.
    """

    def test_confinement_judge_policy_budget_tolerate_poison(self):
        from runner.runner import (
            confinement_violated, judge_job, apply_result_policy,
            query_budget, build_attestations,
        )
        self.assertFalse(confinement_violated(None, "bad"))
        self.assertFalse(confinement_violated({}, None))
        self.assertEqual(judge_job(None, None), ("pass", []))
        self.assertEqual(judge_job({"judge": 5}, {"script": None}), ("pass", []))
        result, retain = apply_result_policy(
            {"max_result_view": None},
            {"result_policy": {"view": 5, "queries": "bad"}},
            {"stdout": None, "stderr": 1, "exit_code": "x"},
            {"bad": None}, None,
        )
        self.assertIsInstance(result, dict)
        self.assertIsInstance(retain, bool)
        self.assertEqual(build_attestations("bad", {}), [])
        self.assertEqual(build_attestations([5, "x", None], {}), [])
        self.assertGreaterEqual(query_budget({"max_query_budget": -1}, {}), 0)
        self.assertGreaterEqual(query_budget(None, None), 0)

    def test_concurrent_policy_and_judge_do_not_raise(self):
        import threading
        from runner.runner import (
            confinement_violated, judge_job, apply_result_policy,
        )
        errors = []

        def hammer():
            for _ in range(20):
                try:
                    confinement_violated(None, "bad")
                    judge_job(None, None)
                    apply_result_policy(
                        {"max_result_view": 5},
                        {"result_policy": {"queries": "bad", "view": None}},
                        {"stdout": None},
                        {"bad": None}, None,
                    )
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class ExtensionBudgetAndPrunePoisonTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. answer_queries compared spent >= budget without coercing budget.
       budget="lots" raised TypeError and stopped the Oracle.
    2. prune_retained did days <= 0 without coercing. days="bad" raised
       TypeError.
    3. senses.validate_sensor_alert assumed job was a dict. None raised
       AttributeError.
    4. senses.gate_alert assumed sensor_cfg was a dict. A string raised
       AttributeError.
    5. senses.store_alert json.dumps'd a non-dict record without a guard.
    6. dri.maybe_page called parse_dri which did cfg.get. None cfg raised
       AttributeError (only RuntimeError was caught).

    All hardened. Poison inputs return safe defaults and do not stop
    processing. Concurrent hammers also pass.
    """

    def test_budget_prune_senses_dri_tolerate_poison(self):
        from runner.runner import answer_queries, prune_retained
        from runner import senses, dri
        answers, spent = answer_queries(
            [{"op": "grep", "pattern": "x"}],
            {"stdout": "hello"}, {}, budget="lots",
        )
        self.assertIsInstance(answers, list)
        self.assertIsInstance(spent, int)
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(prune_retained(d, "bad"), 0)
            self.assertEqual(prune_retained(d, None), 0)
            self.assertEqual(prune_retained(d, -1), 0)
            self.assertEqual(senses.validate_sensor_alert(None), "job must be an object")
            self.assertEqual(senses.validate_sensor_alert("bad"), "job must be an object")
            self.assertIsInstance(senses.gate_alert("bad", {}, []), str)
            self.assertIsInstance(senses.gate_alert({}, "bad", []), str)
            senses.store_alert(d, None)
            senses.store_alert(d, "bad")
            self.assertEqual(dri.maybe_page(None, d), 0)
            self.assertEqual(dri.maybe_page({"dri": "bad"}, d), 0)
            self.assertEqual(dri.maybe_page({"dri": {"enabled": "yes"}}, d), 0)

    def test_concurrent_budget_and_senses_do_not_raise(self):
        import threading
        from runner.runner import answer_queries, prune_retained
        from runner import senses, dri
        errors = []

        def hammer():
            with tempfile.TemporaryDirectory() as d:
                for _ in range(10):
                    try:
                        answer_queries(
                            [None, {"op": "grep", "pattern": None}],
                            {"stdout": None}, {"bad": None}, budget="lots",
                        )
                        prune_retained(d, "bad")
                        senses.validate_sensor_alert(None)
                        senses.gate_alert("bad", {}, [])
                        senses.store_alert(d, None)
                        dri.maybe_page(None, d)
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class NameOracleResourcesPoisonTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. windows_reserved_name assumed name was a string. None, int, list,
       or dict raised AttributeError on .replace.
    2. record_oracle_turn did (ans or {}).get(...). A string ans is
       truthy, so .get raised AttributeError.
    3. resources.check_resources called parse_resources which did
       cfg.get. None cfg raised AttributeError (only RuntimeError was
       caught).

    All hardened. Poison inputs return safe defaults and do not stop
    processing.
    """

    def test_name_oracle_resources_tolerate_poison(self):
        from runner.runner import windows_reserved_name, record_oracle_turn
        from runner import resources
        self.assertFalse(windows_reserved_name(None))
        self.assertFalse(windows_reserved_name(5))
        self.assertFalse(windows_reserved_name(["a"]))
        self.assertFalse(windows_reserved_name({}))
        self.assertTrue(windows_reserved_name("CON"))
        with tempfile.TemporaryDirectory() as d:
            record_oracle_turn(d, {}, "q", "bad")
            record_oracle_turn(d, {}, 5, None)
            record_oracle_turn(d, None, None, {"answer": 5, "rejected": 1})
            self.assertIsNone(resources.check_resources(None, d))
            self.assertIsNone(resources.check_resources({"resources": None}, d))
            self.assertIsNone(resources.check_resources({"resources": "bad"}, d))

    def test_concurrent_name_and_resources_do_not_raise(self):
        import threading
        from runner.runner import windows_reserved_name, record_oracle_turn
        from runner import resources
        errors = []

        def hammer():
            with tempfile.TemporaryDirectory() as d:
                for _ in range(15):
                    try:
                        windows_reserved_name(None)
                        windows_reserved_name(5)
                        record_oracle_turn(d, {}, None, "bad")
                        resources.check_resources(None, d)
                        resources.check_resources({"resources": {"enabled": True, "threshold": "high"}}, d)
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class ConfigAndJobShapePoisonTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. execute_job assumed job was a dict. None/str/int raised
       AttributeError instead of a clean JobRejected.
    2. build_secrets and build_key_policies assumed cfg was a dict.
       None/str raised AttributeError (would stop a poll cycle).
    3. check_key_policy assumed policies and job were dicts. None
       raised AttributeError.
    4. senses.parse_sensors and dri.parse_dri assumed cfg was a dict.
       None raised AttributeError.

    All hardened. Non-dict inputs now raise RuntimeError (config) or
    JobRejected (job), or return a reason string. Processing does not
    stop with an unhandled AttributeError.
    """

    def test_non_dict_job_and_cfg_do_not_attribute_error(self):
        from runner.runner import (
            execute_job, JobRejected, build_secrets, build_key_policies,
            check_key_policy,
        )
        from runner import senses, dri
        with tempfile.TemporaryDirectory() as d:
            for job in (None, "bad", 5, []):
                with self.assertRaises(JobRejected):
                    execute_job({}, job, d)
        for cfg in (None, "bad", 5):
            with self.assertRaises(RuntimeError):
                build_secrets(cfg)
            with self.assertRaises(RuntimeError):
                build_key_policies(cfg)
            with self.assertRaises(RuntimeError):
                senses.parse_sensors(cfg)
            with self.assertRaises(RuntimeError):
                dri.parse_dri(cfg)
        self.assertIsInstance(check_key_policy(None, "k", {}, {}), str)
        self.assertIsInstance(check_key_policy({}, "k", {}, None), str)

    def test_concurrent_shape_checks_do_not_raise_unexpected(self):
        import threading
        from runner.runner import (
            execute_job, JobRejected, build_secrets, check_key_policy,
        )
        from runner import senses, dri
        errors = []

        def hammer():
            with tempfile.TemporaryDirectory() as d:
                for _ in range(8):
                    try:
                        try:
                            execute_job({}, None, d)
                        except JobRejected:
                            pass
                        try:
                            build_secrets(None)
                        except RuntimeError:
                            pass
                        check_key_policy(None, "k", {}, None)
                        try:
                            senses.parse_sensors("bad")
                        except RuntimeError:
                            pass
                        try:
                            dri.parse_dri(None)
                        except RuntimeError:
                            pass
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class VerifySeenLogPoisonTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. verify_body_keyed assumed body was a string. None/int/bytes
       raised AttributeError or TypeError instead of ValueError.
    2. save_seen assumed path was a path and seen was a dict. None path
       raised TypeError; None seen raised AttributeError on .keys.
    3. append_bounded_log assumed text was a string and max_bytes was
       an int. An int text raised AttributeError; max_bytes="bad"
       raised TypeError. Logging must not kill the runner.

    All hardened. Poison inputs return or raise ValueError cleanly
    and do not stop processing.
    """

    def test_verify_seen_log_tolerate_poison(self):
        from runner.runner import verify_body_keyed, save_seen, append_bounded_log, load_seen
        for body in (None, 5, b"bytes", []):
            with self.assertRaises(ValueError):
                verify_body_keyed(body, {"": SECRET})
        with self.assertRaises(ValueError):
            verify_body_keyed("{}", None)
        with tempfile.TemporaryDirectory() as d:
            save_seen(None, {"a": True})
            path = os.path.join(d, "seen.json")
            save_seen(path, None)
            self.assertEqual(load_seen(path), {})
            save_seen(path, "bad")
            self.assertEqual(load_seen(path), {})
            append_bounded_log(os.path.join(d, "l"), None)
            append_bounded_log(os.path.join(d, "l"), 5)
            append_bounded_log(os.path.join(d, "l"), "hello", "bad")
            append_bounded_log(None, "hello")

    def test_concurrent_seen_and_log_do_not_raise(self):
        import threading
        from runner.runner import save_seen, append_bounded_log, verify_body_keyed
        errors = []

        def hammer():
            with tempfile.TemporaryDirectory() as d:
                for _ in range(10):
                    try:
                        try:
                            verify_body_keyed(None, {"": SECRET})
                        except ValueError:
                            pass
                        save_seen(os.path.join(d, "s.json"), None)
                        append_bounded_log(os.path.join(d, "l"), 5, "bad")
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
