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


class SignScrubDescribePoisonTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. sign_payload assumed secret was a string and payload a dict.
       None secret raised AttributeError on .encode.
    2. _scrub_env assumed env was a dict. None/str raised AttributeError
       on .items. Called when building a job environment.
    3. _estimate_secret_entropy and _secret_pattern_reason assumed
       secret was a string. None/int raised AttributeError/TypeError.
    4. _describe_job assumed job was a dict and files a list. None job
       raised AttributeError; files=5 raised TypeError on len.
    5. _worker_count assumed cfg was a dict. None raised AttributeError.
    6. reload_hot_config assumed path was a string. None raised TypeError.
    7. oracle_context assumed base_dir was a string. An int raised TypeError.

    All hardened. Poison inputs return safe defaults or raise ValueError
    and do not stop processing.
    """

    def test_sign_scrub_describe_tolerate_poison(self):
        from runner.runner import (
            sign_payload, _scrub_env, _estimate_secret_entropy,
            _secret_pattern_reason, _describe_job, _worker_count,
            reload_hot_config, oracle_context,
        )
        with self.assertRaises(ValueError):
            sign_payload({}, None)
        with self.assertRaises(ValueError):
            sign_payload(None, SECRET)
        self.assertEqual(_scrub_env(None), {})
        self.assertEqual(_scrub_env("bad"), {})
        self.assertEqual(_estimate_secret_entropy(None), 0.0)
        self.assertEqual(_estimate_secret_entropy(5), 0.0)
        self.assertIsInstance(_secret_pattern_reason(None), str)
        self.assertEqual(_describe_job(None), "invalid job")
        self.assertIsInstance(_describe_job({"files": 5, "kind": "exec"}), str)
        self.assertEqual(_worker_count(None, None), 1)
        self.assertEqual(reload_hot_config(None, None, None), [])
        self.assertEqual(oracle_context(5), "")
        self.assertEqual(oracle_context(None), "")

    def test_concurrent_scrub_and_describe_do_not_raise(self):
        import threading
        from runner.runner import (
            _scrub_env, _describe_job, _worker_count, oracle_context,
            _estimate_secret_entropy,
        )
        errors = []

        def hammer():
            for _ in range(15):
                try:
                    _scrub_env(None)
                    _describe_job({"files": "bad"})
                    _worker_count(None, None)
                    oracle_context(5)
                    _estimate_secret_entropy(None)
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class SnapshotExcludePoisonTest(unittest.TestCase):
    """Finding (2026-10-15 simulation):

    snapshot_outside did os.path.abspath on every truthy exclude entry.
    An int (or other non-string) in the exclude list raised TypeError
    and stopped the confinement check.

    Non-string entries are now filtered. A bad exclude list no longer
    crashes the snapshot.
    """

    def test_bad_exclude_does_not_raise(self):
        from runner.runner import snapshot_outside
        with tempfile.TemporaryDirectory() as d:
            self.assertIsInstance(snapshot_outside(d, exclude=[None, 5, "", d]), dict)
            self.assertIsInstance(snapshot_outside(d, exclude="bad"), dict)
            self.assertEqual(snapshot_outside(None), {})
            self.assertEqual(snapshot_outside(5), {})
            self.assertEqual(snapshot_outside(""), {})

    def test_concurrent_snapshot_with_bad_exclude_does_not_raise(self):
        import threading
        from runner.runner import snapshot_outside
        errors = []

        def hammer():
            with tempfile.TemporaryDirectory() as d:
                for _ in range(8):
                    try:
                        snapshot_outside(d, exclude=[None, 5, ""])
                        snapshot_outside(5)
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class ApplyAndFragmentPoisonTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. apply_result_policy guarded cfg after the first cfg.get.
       None cfg raised AttributeError on max_result_view and stopped
       result packaging.
    2. secret_fragment_hit did (reply or "").casefold(). An int reply
       is truthy, so .casefold raised AttributeError. A non-string
       source also crashed re.finditer.

    Both hardened. Poison inputs return safe defaults and do not stop
    processing.
    """

    def test_apply_and_fragment_tolerate_poison(self):
        from runner.runner import apply_result_policy, secret_fragment_hit
        result, retain = apply_result_policy(None, None, None, None, None)
        self.assertIsInstance(result, dict)
        self.assertIsInstance(retain, bool)
        result, retain = apply_result_policy(
            {"max_result_view": 5},
            {"result_policy": {"view": "redacted", "queries": "bad"}},
            None, "bad", "bad",
        )
        self.assertIsInstance(result, dict)
        self.assertFalse(secret_fragment_hit(5, "src", {}))
        self.assertFalse(secret_fragment_hit("hello", 5, {}))
        self.assertFalse(secret_fragment_hit(None, None, None))
        self.assertFalse(secret_fragment_hit("hello", "hello", {"bad": None}))

    def test_concurrent_apply_and_fragment_do_not_raise(self):
        import threading
        from runner.runner import apply_result_policy, secret_fragment_hit
        errors = []

        def hammer():
            for _ in range(15):
                try:
                    apply_result_policy(None, None, None, None, None)
                    secret_fragment_hit(5, None, {"bad": None})
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class DriEvaluatePoisonTest(unittest.TestCase):
    """Finding (2026-10-15 simulation):

    dri.evaluate_page_triggers assumed dcfg was a dict with a
    triggers key. None dcfg raised TypeError on subscript. A
    non-dict triggers value raised AttributeError on .get.

    Non-dict dcfg or triggers now return an empty list. Evaluation
    does not stop processing.
    """

    def test_bad_dcfg_returns_empty(self):
        from runner import dri
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(dri.evaluate_page_triggers(None, d, 0), [])
            self.assertEqual(dri.evaluate_page_triggers({}, d, 0), [])
            self.assertEqual(dri.evaluate_page_triggers({"triggers": "bad"}, d, 0), [])
            self.assertEqual(dri.evaluate_page_triggers({"triggers": None}, d, 0), [])
            self.assertIsInstance(
                dri.evaluate_page_triggers({"triggers": {}}, d, 0), list)

    def test_concurrent_evaluate_does_not_raise(self):
        import threading
        from runner import dri
        errors = []

        def hammer():
            with tempfile.TemporaryDirectory() as d:
                for _ in range(10):
                    try:
                        dri.evaluate_page_triggers(None, d, 0)
                        dri.evaluate_page_triggers({"triggers": "bad"}, d, "bad")
                        dri.maybe_page(None, d)
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class RetainedResourcesPagePoisonTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. retained_expired assumed data and cfg were dicts. None or a
       string raised AttributeError on .get and stopped retention
       checks.
    2. resources.parse_resources assumed cfg was a dict. None raised
       AttributeError (only RuntimeError was the expected config error).
    3. dri.format_page assumed events was a list. None raised TypeError
       on iteration and stopped a page.

    All hardened. Poison inputs return safe defaults or raise
    RuntimeError and do not stop processing.
    """

    def test_retained_resources_page_tolerate_poison(self):
        from runner.runner import retained_expired
        from runner import resources, dri
        self.assertTrue(retained_expired(None, {}))
        self.assertTrue(retained_expired("bad", "bad"))
        self.assertTrue(retained_expired({}, None))
        with self.assertRaises(RuntimeError):
            resources.parse_resources(None)
        with self.assertRaises(RuntimeError):
            resources.parse_resources("bad")
        self.assertIsInstance(dri.format_page(None), str)
        self.assertIsInstance(dri.format_page("bad"), str)
        self.assertIsInstance(dri.format_page([None, 5, {"title": None}]), str)

    def test_concurrent_retained_and_page_do_not_raise(self):
        import threading
        from runner.runner import retained_expired
        from runner import resources, dri
        errors = []

        def hammer():
            for _ in range(15):
                try:
                    retained_expired(None, "bad")
                    try:
                        resources.parse_resources(None)
                    except RuntimeError:
                        pass
                    dri.format_page(None)
                    dri.format_page([5, "x"])
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class AttestStoreResourcesBoardPoisonTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. build_attestations did sorted(pats.items()). Mixed-type pattern
       keys (int and str) raised TypeError on comparison and stopped
       the Oracle attestation.
    2. senses.store_alert json.dumps'd the record with no guard. A
       non-serializable value (object()) raised TypeError.
    3. resources.check_resources assumed base_dir was a path. None or
       an int raised TypeError on join.
    4. Board assumed path was a string. None raised TypeError on stat.

    All hardened. Poison inputs return safe defaults or raise ValueError
    and do not stop processing.
    """

    def test_attest_store_resources_board_tolerate_poison(self):
        from runner.runner import answer_queries, Board, build_attestations
        from runner import senses, resources
        answers, spent = answer_queries(
            [{"op": "attest", "predicate": "no_secrets"}],
            {"stdout": "hello"},
            {"bad": None, "ok": r"x", 5: "y"},
            budget=2,
        )
        self.assertIsInstance(answers, list)
        self.assertTrue(answers[0].get("ok"))
        with tempfile.TemporaryDirectory() as d:
            senses.store_alert(d, {"sensor": "x", "detail": object()})
            senses.store_alert(d, {"sensor": "x", "title": "t", "observed_at": float("nan")})
            self.assertIsNone(resources.check_resources({"resources": {"enabled": True}}, None))
            self.assertIsNone(resources.check_resources({"resources": {"enabled": True}}, 5))
        with self.assertRaises(ValueError):
            Board(None)
        with self.assertRaises(ValueError):
            Board("")

    def test_concurrent_attest_and_store_do_not_raise(self):
        import threading
        from runner.runner import answer_queries
        from runner import senses, resources
        errors = []

        def hammer():
            with tempfile.TemporaryDirectory() as d:
                for _ in range(10):
                    try:
                        answer_queries(
                            [{"op": "attest", "predicate": "no_secrets"}],
                            {"stdout": None}, {"bad": None, 5: "y"}, 2,
                        )
                        senses.store_alert(d, {"detail": object()})
                        resources.check_resources({"resources": {"enabled": True}}, None)
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class DiskFractionPoisonTest(unittest.TestCase):
    """Finding (2026-10-15 simulation):

    resources._disk_fraction assumed path was a path. None raised
    TypeError on statvfs and stopped the resource check when called
    with a bad base_dir.

    Non-path values now return None. The resource monitor does not
    crash.
    """

    def test_bad_path_returns_none(self):
        from runner import resources
        self.assertIsNone(resources._disk_fraction(None))
        self.assertIsNone(resources._disk_fraction(5))
        self.assertIsNone(resources._disk_fraction([]))
        self.assertIsInstance(resources._disk_fraction("/tmp"), (float, type(None)))

    def test_concurrent_disk_fraction_does_not_raise(self):
        import threading
        from runner import resources
        errors = []

        def hammer():
            for _ in range(15):
                try:
                    resources._disk_fraction(None)
                    resources._disk_fraction(5)
                    resources.check_resources({"resources": {"enabled": True}}, None)
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class PatternMapAndChatLogTest(unittest.TestCase):
    """Finding (2026-10-15 simulation, Oracle first, no mailbox poll):

    redact_text and secret_fragment_hit called .items() on the pattern
    map. A list or a string from an extension raised AttributeError
    in every concurrent caller. record_oracle_turn passed a list
    config into _redact_patterns, which called .get and raised, so
    the chat line was never written.

    A pattern map that is not an object falls back to the built-in
    patterns. A config that is not an object is ignored. The chat
    log is still written.
    """

    def test_bad_pattern_map_does_not_raise(self):
        from runner.runner import redact_text, record_oracle_turn, secret_fragment_hit
        secret = "AKIAIOSFODNN7EXAMPLE"
        out, families = redact_text("leak " + secret, ["not-a-map"])
        self.assertIsInstance(out, str)
        self.assertIn("REDACTED", out)
        self.assertIn("aws_key", families)
        self.assertFalse(secret_fragment_hit("hello", "short", ["not-a-map"]))
        self.assertTrue(secret_fragment_hit(secret[:8], "prefix " + secret, "nope"))
        with tempfile.TemporaryDirectory() as d:
            record_oracle_turn(d, ["not-a-config"], 5, "nope")
            path = os.path.join(d, "oracle-chat.jsonl")
            with open(path, encoding="utf-8") as fh:
                line = json.loads(fh.read())
            self.assertNotIn(secret, json.dumps(line))

    def test_concurrent_bad_pattern_maps_do_not_raise(self):
        import threading
        from runner.runner import redact_text, record_oracle_turn, secret_fragment_hit
        errors = []

        def hammer(i):
            try:
                redact_text("AKIAIOSFODNN7EXAMPLE", ["nope"] if i % 2 else "nope")
                secret_fragment_hit("AKIAIOSF", "x AKIAIOSFODNN7EXAMPLE y", ["nope"])
                with tempfile.TemporaryDirectory() as d:
                    record_oracle_turn(d, {"redact_patterns_extra": ["bad"]}, None, None)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=hammer, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_ping_still_completes_after_the_oracle_path(self):
        body = sign_payload({
            "v": 1, "type": "job", "job_id": "still-ping",
            "issued_at": _now(), "kind": "ping",
        }, SECRET)
        raw = _mail("[HOMING-PIGEON] job still-ping", body)
        cfg = {
            "mailbox_user": "pigeon-test@example.com",
            "shared_secret": SECRET,
            "redact_patterns_extra": ["not-a-map"],
        }
        with tempfile.TemporaryDirectory() as d:
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([raw]), smtp=_SMTP(), opts=_Opts())
            self.assertIn("still-ping", seen)


class DriParseNumericPoisonTest(unittest.TestCase):
    """Finding (2026-10-15 simulation):

    dri.parse_dri did float()/int() on trigger thresholds without a
    guard. threshold="high" raised ValueError, which maybe_page did
    not catch (only RuntimeError/AttributeError/TypeError). A bad
    DRI config stopped the page cycle.

    Numeric conversions now raise RuntimeError, and maybe_page also
    catches ValueError. A bad threshold returns 0 and does not stop
    processing.
    """

    def test_bad_threshold_does_not_stop_page(self):
        from runner import dri
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(dri.maybe_page(
                {"dri": {"enabled": True, "triggers": {
                    "sensor_fused_score": {"threshold": "high"}}}}, d), 0)
            self.assertEqual(dri.maybe_page(
                {"dri": {"enabled": True, "triggers": {
                    "key_probe": {"threshold": None}}}}, d), 0)
            with self.assertRaises(RuntimeError):
                dri.parse_dri({"dri": {"enabled": True, "triggers": {
                    "sensor_fused_score": {"threshold": "high"}}}})
            with self.assertRaises(RuntimeError):
                dri.parse_dri({"dri": {"enabled": True, "triggers": {
                    "key_probe": {"window_sec": "bad"}}}})

    def test_concurrent_bad_dri_cfg_does_not_raise(self):
        import threading
        from runner import dri
        errors = []

        def hammer():
            with tempfile.TemporaryDirectory() as d:
                for _ in range(10):
                    try:
                        dri.maybe_page({"dri": {"enabled": True, "triggers": {
                            "sensor_fused_score": {"threshold": "high"}}}}, d)
                        dri.maybe_page({"dri": {"enabled": True, "triggers": {
                            "key_probe": {"threshold": None}}}}, d)
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])



class ProtectedPathsPoisonTest(unittest.TestCase):
    """Finding (2026-10-15 simulation):

    check_protected_paths did os.path.abspath on every key of the
    before/after snapshots. An int key (poison from a bad snapshot)
    raised TypeError and stopped the confinement report.

    Non-dict snapshots and non-string keys are now skipped. A bad
    snapshot does not crash the check.
    """

    def test_bad_snapshot_keys_do_not_raise(self):
        from runner.runner import check_protected_paths
        self.assertEqual(check_protected_paths({5: (1, 2)}, {5: (1, 2)}, ["/tmp"]), [])
        self.assertEqual(check_protected_paths("bad", {}, [None, 5, ""]), [])
        self.assertEqual(check_protected_paths(None, None, None), [])
        changed = check_protected_paths(
            {"/tmp/x": None}, {"/tmp/x": (1, 2)}, [5, None, "/tmp"])
        self.assertIn("/tmp/x", changed)

    def test_concurrent_protected_paths_do_not_raise(self):
        import threading
        from runner.runner import check_protected_paths
        errors = []

        def hammer():
            for _ in range(15):
                try:
                    check_protected_paths({5: (1, 2)}, {5: (1, 2)}, [None, 5])
                    check_protected_paths(None, "bad", "not-list")
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class AskAndPageShapeTest(unittest.TestCase):
    """Finding (2026-10-15 simulation, Oracle and DRI, no mailbox poll):

    ask_model called .get on its config. A list or an int raised
    AttributeError in every concurrent caller. timeout_sec or
    max_answer_chars set to a word raised ValueError before the
    request, so the ask never returned a rejection.

    format_page iterated signals. An int is truthy, so "or []" did
    not save it, and the page raised TypeError. The digest was not
    saved.

    A bad ask config now returns inference_unconfigured or uses a
    numeric default. A signals value that is not a list is skipped.
    """

    def test_bad_ask_config_returns_a_rejection(self):
        from runner.runner import ask_model
        from runner import dri
        inf = {"endpoint": "http://127.0.0.1:9/v1", "model": "m"}
        for cfg in (["x"], 5, None):
            got = ask_model(cfg, "what happened?", "out", 10)
            self.assertEqual(got.get("rejected"), "inference_unconfigured")
        got = ask_model({**inf, "timeout_sec": "soon", "max_answer_chars": "x"},
                        "q", "out", "lots")
        self.assertIn(got.get("rejected"), ("inference_error", "inference_unconfigured"))
        text = dri.format_page([
            {"title": "pressure", "signals": 5},
            {"title": "ok", "signals": ["one"]},
            {"signals": "word"},
        ])
        self.assertIn("pressure", text)
        self.assertIn("one", text)
        self.assertNotIn("w", text.split("ok")[-1][:20])

    def test_concurrent_bad_asks_and_pages_do_not_raise(self):
        import threading
        from runner.runner import ask_model
        from runner import dri
        errors = []
        inf = {"endpoint": "http://127.0.0.1:9/v1", "model": "m",
               "timeout_sec": "soon", "max_answer_chars": "x"}

        def hammer(i):
            try:
                ask_model(["x"] if i % 2 else inf, "q", "out", "lots")
                dri.format_page([{"signals": 5}, {"signals": None}, 5])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=hammer, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_ping_still_completes(self):
        body = sign_payload({
            "v": 1, "type": "job", "job_id": "after-ask",
            "issued_at": _now(), "kind": "ping",
        }, SECRET)
        raw = _mail("[HOMING-PIGEON] job after-ask", body)
        cfg = {"mailbox_user": "pigeon-test@example.com", "shared_secret": SECRET}
        with tempfile.TemporaryDirectory() as d:
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([raw]), smtp=_SMTP(), opts=_Opts())
            self.assertIn("after-ask", seen)


class ReloadHotConfigPoisonTest(unittest.TestCase):
    """Finding (2026-10-15 simulation):

    reload_hot_config called load_config and let JSONDecodeError
    escape. A half-written or poisoned config.json raised and, if
    the caller did not catch it, stopped the cycle. The main loop
    caught it, but the function itself was not graceful.

    A bad file now returns [] and leaves mtime alone, so the next
    poll retries. Processing does not stop.
    """

    def test_bad_config_file_returns_empty(self):
        from runner.runner import reload_hot_config
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            open(path, "w").write("not json")
            state = {}
            self.assertEqual(reload_hot_config({"poll_interval_sec": 1}, path, state), [])
            self.assertNotIn("mtime", state)
            open(path, "w").write('{"poll_interval_sec": 5}')
            changed = reload_hot_config({"poll_interval_sec": 1}, path, state)
            self.assertIn("poll_interval_sec", changed)

    def test_concurrent_bad_reload_does_not_raise(self):
        import threading
        from runner.runner import reload_hot_config
        errors = []

        def hammer():
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "config.json")
                open(path, "w").write("not json")
                for _ in range(10):
                    try:
                        reload_hot_config({"poll_interval_sec": 1}, path, {})
                        reload_hot_config(None, path, None)
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])



class DriSaveStatePoisonTest(unittest.TestCase):
    """Finding (2026-10-15 simulation):

    dri._save_state assumed base_dir was a path. None or an int
    raised TypeError on join and stopped a concurrent page cycle
    that tried to persist state.

    Non-path base_dir now returns immediately. A non-dict state is
    treated as empty. Processing does not stop.
    """

    def test_bad_base_does_not_raise(self):
        from runner import dri
        dri._save_state(None, {})
        dri._save_state(5, {"x": 1})
        dri._save_state("", {"x": 1})
        with tempfile.TemporaryDirectory() as d:
            dri._save_state(d, None)
            self.assertEqual(dri._load_state(d), {})
            dri._save_state(d, {"last_check": 1})
            self.assertEqual(dri._load_state(d).get("last_check"), 1)

    def test_concurrent_save_state_does_not_raise(self):
        import threading
        from runner import dri
        errors = []

        def hammer():
            with tempfile.TemporaryDirectory() as d:
                for _ in range(10):
                    try:
                        dri._save_state(None, {})
                        dri._save_state(5, {"x": 1})
                        dri._save_state(d, None)
                        dri._load_state(d)
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class SenseGateAndPageTextTest(unittest.TestCase):
    """Finding (2026-10-15 simulation, senses and the Oracle page, no poll):

    gate_alert called .get on a profile that was a string or a list,
    float() on max_per_hour "lots", and .get on a recent row that was
    a string. Each raised, and six threads all died. A clock value of
    the word "now" raised TypeError. query_budget did the same .get
    on a list config. oracle_page json.dumps'd a set and the page
    was not built. download compared an int to the word "1MB".

    Two alerts with max_per_hour 1 both would have been stored if the
    load and the write were separate steps.

    Bad shapes are now dropped or ignored. The page is still built.
    Only one of the two alerts is stored.
    """

    def test_bad_gate_inputs_do_not_raise(self):
        from runner import senses
        from runner.runner import JobRejected, download, oracle_page, query_budget
        from unittest import mock
        alert = {"severity": "info", "title": "t"}
        self.assertIsNone(senses.gate_alert({"profile": "tight"}, alert, []))
        self.assertIsNone(senses.gate_alert({"profile": ["x"]}, alert, []))
        self.assertIsNone(senses.gate_alert(
            {"profile": {"max_per_hour": "lots"}}, alert, []))
        self.assertIsNone(senses.gate_alert(
            {"profile": {"cooldown_sec": 30}}, alert, ["not-a-dict"]))
        self.assertIsNone(senses.gate_alert(
            {"profile": {"cooldown_sec": 30}}, alert,
            [{"received_at": "2026-10-15T00:00:00Z", "title": "other"}],
            now="now"))
        self.assertEqual(query_budget(["x"], {"result_policy": {"query_budget": 1}}), 1)
        page = oracle_page({1}, {2}, "yes")
        self.assertIn("Oracle", page)
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "blob")

            class _Resp:
                def read(self, n):
                    return b""

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            with mock.patch("runner.runner.urlopen", return_value=_Resp()):
                download("https://example.com/a", dest, max_bytes="1MB")
            self.assertTrue(os.path.isfile(dest))
            with self.assertRaises(JobRejected):
                download("file:///etc/passwd", dest, max_bytes="1MB")

    def test_two_alerts_cannot_both_pass_the_hourly_cap(self):
        import threading
        from runner import senses
        scfg = {"profile": {"max_per_hour": 1}}
        kept = []
        dropped = []
        lock = threading.Lock()

        def once(i):
            rec = {
                "sensor": "host-ids", "severity": "info",
                "title": f"t{i}", "received_at": _now(),
            }
            reason = senses.file_sensor_alert(shared["d"], scfg, rec)
            with lock:
                (dropped if reason else kept).append(i)

        with tempfile.TemporaryDirectory() as d:
            shared = {"d": d}
            threads = [threading.Thread(target=once, args=(i,)) for i in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            rows = senses.load_alerts(d, limit=10)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(len(rows), 1)

    def test_ping_still_completes_after_the_sense_gate(self):
        body = sign_payload({
            "v": 1, "type": "job", "job_id": "after-sense",
            "issued_at": _now(), "kind": "ping",
        }, SECRET)
        raw = _mail("[HOMING-PIGEON] job after-sense", body)
        cfg = {"mailbox_user": "pigeon-test@example.com", "shared_secret": SECRET}
        with tempfile.TemporaryDirectory() as d:
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([raw]), smtp=_SMTP(), opts=_Opts())
            self.assertIn("after-sense", seen)


class BadBaseDirPoisonTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. resources._save_state assumed base_dir was a path. None or an
       int raised TypeError on join.
    2. senses.store_alert and load_alerts assumed base_dir was a path.
       None or an int raised TypeError.
    3. save_retained and load_retained assumed base_dir was a path.
       None or an int raised TypeError.

    All hardened. A bad base_dir returns immediately (None or []).
    Processing does not stop.
    """

    def test_bad_base_dir_does_not_raise(self):
        from runner.runner import save_retained, load_retained
        from runner import senses, resources
        resources._save_state(None, {"x": 1})
        resources._save_state(5, {"x": 1})
        resources._save_state("", {"x": 1})
        senses.store_alert(None, {"sensor": "x", "title": "t"})
        senses.store_alert(5, {"sensor": "x"})
        self.assertEqual(senses.load_alerts(None), [])
        self.assertEqual(senses.load_alerts(5), [])
        save_retained(None, "j", {"stdout": "x"})
        save_retained(5, "j", {"stdout": "x"})
        self.assertIsNone(load_retained(None, "j"))
        self.assertIsNone(load_retained(5, "j"))

    def test_concurrent_bad_base_does_not_raise(self):
        import threading
        from runner.runner import save_retained, load_retained
        from runner import senses, resources
        errors = []

        def hammer():
            for _ in range(10):
                try:
                    resources._save_state(None, {"x": 1})
                    senses.store_alert(5, {"sensor": "x"})
                    senses.load_alerts(None)
                    save_retained(None, "j", {"stdout": "x"})
                    load_retained(5, "j")
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class SignAndContextShapeTest(unittest.TestCase):
    """Finding (2026-10-15 simulation, signing and Oracle context, no poll):

    sign_payload json.dumps'd a set or bytes and raised TypeError, so
    a result carrying that value could not be signed. verify_body_keyed
    called .encode on a secret that was an int or bytes, which is not
    ValueError, so the worker raised and the message was retried.
    oracle_context sliced with limit "six" and max_chars "lots" and
    raised TypeError. Six threads all died.

    A set becomes a list, bytes become text, a bad secret is a
    ValueError, and a word limit falls back to the default.
    """

    def test_bad_sign_and_context_do_not_raise(self):
        from runner.runner import oracle_context, sign_payload, verify_body_keyed
        body = sign_payload({"notes": {1, 2}, "blob": b"hi"}, SECRET)
        self.assertIn("1", body)
        self.assertIn("2", body)
        self.assertIn("hi", body)
        with self.assertRaises(ValueError):
            verify_body_keyed(body, {"": 5})
        with self.assertRaises(ValueError):
            verify_body_keyed(body, {"": SECRET.encode()})
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            with open(os.path.join(d, "retained", "job-a.json"), "w", encoding="utf-8") as fh:
                json.dump({"stdout": "hello", "kind": "ping"}, fh)
            text = oracle_context(d, limit="six", max_chars="lots")
            self.assertIn("hello", text)
            self.assertEqual(oracle_context(d, max_chars=-5), "")

    def test_concurrent_sign_and_context_do_not_raise(self):
        import threading
        from runner.runner import oracle_context, sign_payload, verify_body_keyed
        errors = []

        def hammer():
            try:
                body = sign_payload({"notes": {1}, "blob": b"x"}, SECRET)
                try:
                    verify_body_keyed(body, {"": 5})
                except ValueError:
                    pass
                with tempfile.TemporaryDirectory() as d:
                    os.makedirs(os.path.join(d, "retained"))
                    oracle_context(d, limit="six", max_chars="lots")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_ping_still_completes_after_signing(self):
        body = sign_payload({
            "v": 1, "type": "job", "job_id": "after-sign",
            "issued_at": _now(), "kind": "ping",
        }, SECRET)
        raw = _mail("[HOMING-PIGEON] job after-sign", body)
        cfg = {"mailbox_user": "pigeon-test@example.com", "shared_secret": SECRET}
        with tempfile.TemporaryDirectory() as d:
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([raw]), smtp=_SMTP(), opts=_Opts())
            self.assertIn("after-sign", seen)


class MoreBadBasePoisonTest(unittest.TestCase):
    """Findings (2026-10-15 simulation):

    1. prune_retained assumed base_dir was a path. None or an int
       raised TypeError on isdir.
    2. _append_security_event assumed base_dir was a path. None or an
       int raised TypeError on join.
    3. dri._load_state assumed base_dir was a path. None or an int
       raised TypeError.
    4. resources._load_state assumed base_dir was a path. None or an
       int raised TypeError.

    All hardened. A bad base_dir returns 0 or {}. Processing does not
    stop.
    """

    def test_more_bad_base_does_not_raise(self):
        from runner.runner import prune_retained, _append_security_event
        from runner import dri, resources
        self.assertEqual(prune_retained(None, 7), 0)
        self.assertEqual(prune_retained(5, "bad"), 0)
        self.assertEqual(prune_retained("", -1), 0)
        _append_security_event(None, {"type": "x"})
        _append_security_event(5, {"type": "x"})
        _append_security_event("", None)
        self.assertEqual(dri._load_state(None), {})
        self.assertEqual(dri._load_state(5), {})
        self.assertEqual(resources._load_state(None), {})
        self.assertEqual(resources._load_state(5), {})

    def test_concurrent_more_bad_base_does_not_raise(self):
        import threading
        from runner.runner import prune_retained, _append_security_event
        from runner import dri, resources
        errors = []

        def hammer():
            for _ in range(10):
                try:
                    prune_retained(None, 7)
                    _append_security_event(5, {"type": "x"})
                    dri._load_state(None)
                    resources._load_state(5)
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class DriRecentPoisonTest(unittest.TestCase):
    """Finding (2026-10-15 simulation):

    dri._recent_events and _recent_retained assumed base_dir was a
    path. None or an int raised TypeError on join and stopped trigger
    evaluation when called with a bad base.

    Non-path base_dir now returns []. Evaluation does not stop.
    """

    def test_bad_base_returns_empty(self):
        from runner import dri
        self.assertEqual(dri._recent_events(None, 0), [])
        self.assertEqual(dri._recent_events(5, "bad"), [])
        self.assertEqual(dri._recent_events("", None), [])
        self.assertEqual(dri._recent_retained(None, 0), [])
        self.assertEqual(dri._recent_retained(5, None), [])
        self.assertEqual(dri._recent_retained("", -1), [])

    def test_concurrent_recent_does_not_raise(self):
        import threading
        from runner import dri
        errors = []

        def hammer():
            with tempfile.TemporaryDirectory() as d:
                for since in (None, "bad", float("nan"), -1, 0):
                    try:
                        dri._recent_events(None, since)
                        dri._recent_retained(5, since)
                        dri._recent_events(d, since)
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class BoardRateAndResourceClockTest(unittest.TestCase):
    """Finding (2026-10-15 simulation, board and resources, no poll):

    _query_limit, check_rate_limit, and budget_status called .get on
    a list config. Board.offer did the same. Six threads all raised
    AttributeError. Board.complete stored a set and json.dump raised,
    so the claim was not finished. check_resources subtracted a word
    clock from a float and raised, so the sample was not saved.

    A config that is not an object is treated as empty. A set in a
    result is saved as a list. A clock that is not a number is the
    current time. The sample still returns.
    """

    def test_bad_board_and_clock_do_not_raise(self):
        from runner.runner import Board, budget_status, check_rate_limit, _query_limit
        from runner import resources
        self.assertEqual(_query_limit(["x"]), 0)
        self.assertTrue(check_rate_limit("k", ["x"]))
        self.assertEqual(budget_status(None, ["x"]), [])
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            self.assertIsNone(board.offer("w", ["run"], cfg=["nope"]))
            self.assertTrue(board.submit({"task_id": "t1", "priority": 1})[0])
            claimed = board.offer("w1", ["run"])
            self.assertEqual(claimed.get("task_id"), "t1")
            status, _why = board.complete("t1", {"notes": {1, 2}})
            self.assertEqual(status, "done")
            again = Board(os.path.join(d, "board.json"))
            self.assertEqual(again.tasks["t1"]["state"], "done")
            self.assertIsInstance(again.tasks["t1"]["result"]["notes"], list)
            event = resources.check_resources(
                {"resources": {"enabled": True, "threshold": 0.01, "cooldown_sec": 0}},
                d, now="soon",
            )
            self.assertTrue(event is None or isinstance(event, dict))

    def test_concurrent_board_and_clock_do_not_raise(self):
        import threading
        from runner.runner import Board, check_rate_limit
        from runner import resources
        errors = []

        def hammer(i):
            try:
                check_rate_limit("k", ["x"])
                with tempfile.TemporaryDirectory() as d:
                    board = Board(os.path.join(d, "b.json"))
                    board.submit({"task_id": "t", "priority": 1})
                    board.offer("w", [], cfg=["bad"])
                    board.offer("w", ["run"])
                    board.complete("t", {"notes": {1}})
                    resources.check_resources(
                        {"resources": {"enabled": True, "threshold": 0.01}},
                        d, now="soon",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=hammer, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_ping_still_completes_after_the_board(self):
        body = sign_payload({
            "v": 1, "type": "job", "job_id": "after-board",
            "issued_at": _now(), "kind": "ping",
        }, SECRET)
        raw = _mail("[HOMING-PIGEON] job after-board", body)
        cfg = {"mailbox_user": "pigeon-test@example.com", "shared_secret": SECRET}
        with tempfile.TemporaryDirectory() as d:
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([raw]), smtp=_SMTP(), opts=_Opts())
            self.assertIn("after-board", seen)
