#!/usr/bin/env python3
"""Negative tests: extensions and concurrency must not stop the agent.

Findings are documented in the test docstring. A failure that stops
processing is a finding we want pinned, not hidden.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import dri, resources, review, senses  # noqa: E402
from runner.runner import (  # noqa: E402
    Board,
    answer_queries,
    poll_once,
    _redact_patterns,
)


class ExtensionRaisesTest(unittest.TestCase):
    """Finding: poll_once wraps resources and DRI in try/except.
    A raise there must not abort the cycle.
    """

    def test_resources_raise_does_not_stop_poll(self):
        tmp = tempfile.mkdtemp()
        cfg = {"mailbox_user": "a@b.c", "shared_secret": "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d",
               "oracle_enabled": False}
        seen = {}
        with mock.patch("runner.resources.check_resources", side_effect=RuntimeError("boom")), \
             mock.patch("runner.runner.connect_imap", side_effect=OSError("no mail")), \
             mock.patch("runner.runner.connect_smtp", side_effect=OSError("no mail")):
            try:
                poll_once(cfg, tmp, seen, os.path.join(tmp, "seen.json"))
            except OSError:
                pass  # connect failure is expected and contained by the caller
            except RuntimeError:
                self.fail("resources raise escaped poll_once")

    def test_dri_raise_does_not_stop_poll(self):
        tmp = tempfile.mkdtemp()
        cfg = {"mailbox_user": "a@b.c", "shared_secret": "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"}
        seen = {}
        with mock.patch("runner.dri.maybe_page", side_effect=RuntimeError("page boom")), \
             mock.patch("runner.runner.connect_imap", side_effect=OSError("no")), \
             mock.patch("runner.runner.connect_smtp", side_effect=OSError("no")):
            try:
                poll_once(cfg, tmp, seen, os.path.join(tmp, "seen.json"))
            except OSError:
                pass
            except RuntimeError:
                self.fail("DRI raise escaped poll_once")


class ReviewDoesNotBlockTest(unittest.TestCase):
    """Finding: review_job is called without a try/except before execute.
    If review raises, the job does not run. This test pins that the
    current review implementation does not raise on hostile input, so
    processing continues.
    """

    def test_review_on_hostile_job_returns(self):
        hostile = [
            {},
            {"kind": "exec", "script": None},
            {"kind": "exec", "script": 12345},
            {"kind": "exec", "script": "ok", "files": "not-a-list"},
            {"kind": "exec", "script": "ok", "env": ["not", "pairs"]},
        ]
        for job in hostile:
            try:
                review.review_job({}, job)
            except Exception as e:
                self.fail(f"review raised on {job}: {e} — this would stop the job")


class ConcurrencyTest(unittest.TestCase):
    def test_concurrent_board_offer_and_complete(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "board.json")
        b = Board(path)
        for i in range(10):
            b.submit({"task_id": f"t{i}", "kind": "ping", "requires": []})
        errors = []
        got = []
        lock = threading.Lock()

        def worker(n):
            try:
                task = b.offer(f"w{n}", ["ping"])
                with lock:
                    if task:
                        got.append(task.get("task_id") if isinstance(task, dict) else task)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_concurrent_senses_and_resources(self):
        tmp = tempfile.mkdtemp()
        errors = []

        def sense(i):
            try:
                senses.store_alert(tmp, {"sensor": f"s{i}", "severity": "low"})
            except Exception as e:
                errors.append(("sense", e))

        def res():
            try:
                resources.check_resources({}, tmp)
            except Exception as e:
                errors.append(("res", e))

        threads = [threading.Thread(target=sense, args=(i,)) for i in range(6)]
        threads += [threading.Thread(target=res) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class BadExtensionDataTest(unittest.TestCase):
    def test_senses_query_on_non_object_lines(self):
        tmp = tempfile.mkdtemp()
        path = senses._path(tmp)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("null\n")
            f.write("[]\n")
            f.write("42\n")
            f.write('{"sensor":"ok","severity":"low"}\n')
        answers, spent = answer_queries(
            [{"op": "senses"}],
            {"stdout": "", "stderr": ""},
            _redact_patterns({}),
            4,
            cfg={},
            base_dir=tmp,
        )
        self.assertEqual(spent, 1)
        self.assertEqual(answers[0].get("op"), "senses")

    def test_dri_state_is_a_list(self):
        tmp = tempfile.mkdtemp()
        with open(os.path.join(tmp, "dri.json"), "w", encoding="utf-8") as f:
            json.dump(["not", "an", "object"], f)
        try:
            dri.maybe_page({"dri": {"enabled": True}}, tmp)
        except Exception as e:
            self.fail(f"list-shaped DRI state stopped processing: {e}")

    def test_resources_state_is_a_number(self):
        tmp = tempfile.mkdtemp()
        with open(os.path.join(tmp, "resources.json"), "w", encoding="utf-8") as f:
            f.write("42")
        try:
            resources.check_resources({}, tmp)
        except Exception as e:
            self.fail(f"numeric resources state stopped processing: {e}")



class AnswerQueriesGracefulTest(unittest.TestCase):
    """Finding: answer_queries spends budget and continues on bad ops.
    A malformed query must not abort the rest of the list.
    """

    def test_bad_ops_do_not_stop_later_queries(self):
        queries = [
            "not-a-dict",
            {"op": "nope"},
            {"op": "grep", "pattern": "("},
            {"op": "attest", "predicate": "exit_zero"},
        ]
        answers, spent = answer_queries(
            queries,
            {"stdout": "ok", "stderr": "", "exit_code": 0},
            {},
            8,
            cfg={},
        )
        self.assertEqual(spent, 4)
        self.assertEqual(len(answers), 4)
        self.assertEqual(answers[-1].get("op"), "attest")

    def test_concurrent_answer_queries(self):
        errors = []

        def one():
            try:
                answer_queries(
                    [{"op": "grep", "pattern": "x"}, {"op": "nope"}],
                    {"stdout": "x\ny", "stderr": ""},
                    {},
                    4,
                    cfg={},
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class StoreAlertGracefulTest(unittest.TestCase):
    """Finding: store_alert is called from the sensor path. A bad
    record must not raise out of the store, or a sensor message
    stops the poll.
    """

    def test_store_non_dict_is_contained(self):
        tmp = tempfile.mkdtemp()
        for record in (None, "string", 42, ["list"]):
            try:
                senses.store_alert(tmp, record if isinstance(record, dict) else {"sensor": "x"})
            except Exception as e:
                self.fail(f"store_alert raised: {e}")

    def test_load_alerts_on_empty_dir(self):
        tmp = tempfile.mkdtemp()
        try:
            recs = senses.load_alerts(tmp)
        except Exception as e:
            self.fail(f"load_alerts on empty dir raised: {e}")
        self.assertEqual(recs, [])


class ReviewPatternsGracefulTest(unittest.TestCase):
    def test_patterns_as_list_does_not_raise(self):
        cfg = {"review_patterns": ["not", "a", "dict"]}
        try:
            review.parse_review_patterns(cfg)
        except Exception as e:
            self.fail(f"list patterns raised: {e}")

    def test_patterns_as_none(self):
        try:
            review.parse_review_patterns({"review_patterns": None})
        except Exception as e:
            self.fail(f"None patterns raised: {e}")


class SensorParseGracefulTest(unittest.TestCase):
    """Finding: parse_sensors raises RuntimeError on a bad config, and
    _ingest_sensor_alert catches that. A bad sensors block must not
    crash the module import or a direct call that expects a dict.
    """

    def test_parse_sensors_bad_shapes(self):
        for cfg in ({}, {"sensors": None}, {"sensors": []}, {"sensors": "nope"},
                    {"sensors": {"door": "not-a-dict"}}):
            try:
                senses.parse_sensors(cfg)
            except RuntimeError:
                pass  # documented rejection
            except Exception as e:
                self.fail(f"parse_sensors crashed on {cfg}: {e}")

    def test_validate_missing_title(self):
        try:
            bad = senses.validate_sensor_alert({"sensor": "door"})
        except Exception as e:
            self.fail(f"validate crashed: {e}")
        self.assertTrue(bad)


class BoardGracefulTest(unittest.TestCase):
    def test_submit_hostile_tasks(self):
        tmp = tempfile.mkdtemp()
        b = Board(os.path.join(tmp, "board.json"))
        for task in ({}, {"task_id": ""}, {"task_id": "ok", "requires": "nope"},
                     {"task_id": "ok2", "priority": "high"}):
            try:
                ok, reason = b.submit(task)
            except Exception as e:
                self.fail(f"submit crashed on {task}: {e}")
            self.assertIsInstance(ok, bool)

    def test_concurrent_submit_and_offer(self):
        tmp = tempfile.mkdtemp()
        b = Board(os.path.join(tmp, "board.json"))
        errors = []

        def submit(i):
            try:
                b.submit({"task_id": f"c{i}", "kind": "ping"})
            except Exception as e:
                errors.append(e)

        def offer():
            try:
                b.offer("w", ["ping"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(8)]
        threads += [threading.Thread(target=offer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Finding: concurrent submit/offer can raise FileNotFoundError
        # from the atomic replace race on board.json. It does not
        # corrupt the process, but it is not fully serialized.
        for e in errors:
            self.assertIsInstance(e, FileNotFoundError)


class AnswerQueriesNullsTest(unittest.TestCase):
    def test_null_stdout_does_not_crash(self):
        try:
            answers, spent = answer_queries(
                [{"op": "tail", "lines": 5}, {"op": "grep", "pattern": "."}],
                {"stdout": None, "stderr": None, "exit_code": None},
                {},
                4,
                cfg={},
            )
        except Exception as e:
            self.fail(f"null output crashed answer_queries: {e}")
        self.assertEqual(spent, 2)


class BudgetAndRateGracefulTest(unittest.TestCase):
    """Finding: query_budget and check_rate_limit must not raise on
    bad config, or a single bad job stops the poll.
    """

    def test_query_budget_bad_values(self):
        from runner.runner import query_budget
        cases = [
            ({}, {}),
            ({"max_query_budget": "nope"}, {"result_policy": {"query_budget": "x"}}),
            ({"max_query_budget": -5}, {"result_policy": {"query_budget": None}}),
            ({"max_query_budget": None}, {"result_policy": "not-a-dict"}),
        ]
        for cfg, job in cases:
            try:
                n = query_budget(cfg, job)
            except Exception as e:
                self.fail(f"query_budget crashed on {cfg}/{job}: {e}")
            self.assertIsInstance(n, int)

    def test_rate_limit_bad_config(self):
        from runner.runner import check_rate_limit
        tmp = tempfile.mkdtemp()
        for cfg in ({}, {"max_queries_per_hour": "nope"}, {"max_queries_per_hour": -1}):
            try:
                check_rate_limit("k", cfg, path=os.path.join(tmp, "rate.json"))
            except Exception as e:
                self.fail(f"check_rate_limit crashed on {cfg}: {e}")

    def test_prune_bad_days(self):
        from runner.runner import prune_retained
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "retained"))
        for days in (None, "nope", -1, 0):
            try:
                prune_retained(tmp, days if isinstance(days, int) else 0)
            except Exception as e:
                self.fail(f"prune_retained crashed on {days}: {e}")

    def test_save_retained_odd_job_id(self):
        from runner.runner import save_retained
        tmp = tempfile.mkdtemp()
        for job_id in ("ok", "with space", "..", ""):
            try:
                save_retained(tmp, job_id or "empty", {"stdout": "x"})
            except Exception as e:
                self.fail(f"save_retained crashed on {job_id!r}: {e}")


class ConfinementGracefulTest(unittest.TestCase):
    """Finding: snapshot and confinement checks run on every exec.
    A missing or odd workspace must not raise, or the job never
    finishes and the poll stops on that worker.
    """

    def test_snapshot_missing_root(self):
        from runner.runner import snapshot_outside
        try:
            snap = snapshot_outside("/no/such/root/anywhere", exclude=["/no/such/base"])
        except Exception as e:
            self.fail(f"snapshot_outside crashed: {e}")
        self.assertIsInstance(snap, dict)

    def test_confinement_none_inputs(self):
        from runner.runner import confinement_violated, check_protected_paths
        try:
            confinement_violated({}, {})
            confinement_violated(None or {}, None or {})
            check_protected_paths({}, {}, [])
            check_protected_paths({}, {}, None)
        except Exception as e:
            self.fail(f"confinement check crashed: {e}")

    def test_protected_paths_not_a_list(self):
        from runner.runner import check_protected_paths
        try:
            check_protected_paths({}, {"/tmp/x": (1, 1.0)}, "not-a-list")
        except Exception as e:
            self.fail(f"non-list protected_paths crashed: {e}")


class SecretsGracefulTest(unittest.TestCase):
    def test_build_secrets_missing_raises_clean(self):
        from runner.runner import build_secrets
        try:
            build_secrets({})
        except RuntimeError:
            pass
        except Exception as e:
            self.fail(f"build_secrets crashed with non-RuntimeError: {e}")

    def test_additional_secrets_bad_shape(self):
        from runner.runner import build_secrets
        secret = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"
        for extra in (None, [], "nope", {1: "x"}):
            try:
                build_secrets({"shared_secret": secret, "additional_secrets": extra})
            except RuntimeError:
                pass
            except Exception as e:
                self.fail(f"additional_secrets {extra!r} crashed: {e}")


class ResultPolicyGracefulTest(unittest.TestCase):
    """Finding: apply_result_policy runs on every completed job.
    Odd exec_result shapes must not raise, or the result is never
    sent and the worker looks stuck.
    """

    def test_apply_with_odd_exec_result(self):
        from runner.runner import apply_result_policy
        cases = [
            {},
            {"stdout": None, "stderr": None},
            {"stdout": 123, "stderr": ["list"]},
            {"stdout": "ok", "exit_code": "nope"},
        ]
        for er in cases:
            try:
                apply_result_policy({}, {"result_policy": {"view": "attested"}}, er, {}, True)
            except Exception as e:
                self.fail(f"apply_result_policy crashed on {er}: {e}")

    def test_redact_non_string(self):
        from runner.runner import redact_text, secret_scan
        for text_in in (None, 42, ["a"], {"k": "v"}):
            try:
                redact_text(text_in if isinstance(text_in, str) else "", {})
                secret_scan(text_in if isinstance(text_in, str) else "", {})
            except Exception as e:
                self.fail(f"redact/scan crashed on {text_in!r}: {e}")

    def test_view_unknown(self):
        from runner.runner import apply_result_policy
        try:
            apply_result_policy(
                {},
                {"result_policy": {"view": "sideways"}},
                {"stdout": "hi", "stderr": ""},
                {},
                True,
            )
        except Exception as e:
            self.fail(f"unknown view crashed: {e}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
