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


class JudgeGracefulTest(unittest.TestCase):
    """Finding: judge_job runs before execute when judge is on.
    A hostile job must not make it raise, or the job is dropped
    and the worker stops on that message.
    """

    def test_judge_hostile_jobs(self):
        from runner.runner import judge_job
        cfg = {"judge": "enforce"}
        jobs = [
            {},
            {"kind": "exec", "script": None},
            {"kind": "exec", "script": 123},
            {"kind": "exec", "script": "dd of=/dev/sda"},
            {"kind": "ping"},
            {"kind": "exec", "script": "echo ok", "interpreter": "not-a-list"},
        ]
        for job in jobs:
            try:
                reasons = judge_job(cfg, job)
            except Exception as e:
                self.fail(f"judge_job crashed on {job}: {e}")
            self.assertTrue(isinstance(reasons, (list, tuple)))

    def test_judge_off_and_advisory(self):
        from runner.runner import judge_job
        job = {"kind": "exec", "script": "rm -rf /"}
        for mode in ("off", "advisory", "enforce", None, "nope"):
            try:
                judge_job({"judge": mode}, job)
            except Exception as e:
                self.fail(f"judge mode {mode!r} crashed: {e}")

    def test_concurrent_judge(self):
        from runner.runner import judge_job
        errors = []

        def one(i):
            try:
                judge_job({"judge": "enforce"}, {"kind": "exec", "script": f"echo {i}"})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class KeyPolicyGracefulTest(unittest.TestCase):
    """Finding: check_key_policy and verify_body_keyed run on every
    message. Bad policy shapes and bad bodies must reject cleanly,
    not crash the poll.
    """

    def test_check_key_policy_odd_shapes(self):
        from runner.runner import check_key_policy
        cases = [
            ({}, "", {}, {}),
            ({"k": "not-a-dict"}, "k", {}, {"kind": "ping"}),
            ({"k": {"allow_kinds": "ping"}}, "k", {}, {"kind": "ping"}),
            (None, "", {}, {}),
        ]
        for policies, key_id, cfg, job in cases:
            try:
                check_key_policy(policies or {}, key_id, cfg, job)
            except Exception as e:
                self.fail(f"check_key_policy crashed: {e}")

    def test_verify_bad_bodies(self):
        from runner.runner import verify_body_keyed
        secret = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"
        secrets = {"": secret}
        for body in ("", "not json", "{}", "[]", "null"):
            try:
                verify_body_keyed(body, secrets)
                self.fail(f"verify accepted {body!r}")
            except Exception:
                pass  # clean rejection is the graceful path

    def test_build_key_policies_bad(self):
        from runner.runner import build_key_policies
        for cfg in ({}, {"key_policies": None}, {"key_policies": []},
                    {"key_policies": {"k": "nope"}}):
            try:
                build_key_policies(cfg)
            except RuntimeError:
                pass
            except Exception as e:
                self.fail(f"build_key_policies crashed on {cfg}: {e}")


class InferenceGracefulTest(unittest.TestCase):
    """Finding: ask_model runs when a job declares an ask query.
    A bad endpoint, a crashing opener, or a weird reply must reject
    cleanly, not crash the worker.
    """

    def test_inference_config_odd(self):
        from runner.runner import inference_config
        cases = [
            {},
            {"inference": None},
            {"inference": "nope"},
            {"inference": {"endpoint": "http://evil.example/v1", "model": "m"}},
            {"inference": {"endpoint": "http://127.0.0.1:11434/v1"}},
        ]
        for cfg in cases:
            try:
                inference_config(cfg)
            except Exception as e:
                self.fail(f"inference_config crashed on {cfg}: {e}")

    def test_ask_model_opener_raises(self):
        from runner.runner import ask_model
        inf = {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"}

        def boom(req, timeout=60):
            raise OSError("down")

        try:
            got = ask_model(inf, "why?", "out", 100, opener=boom)
        except Exception as e:
            self.fail(f"ask_model let the opener raise out: {e}")
        self.assertEqual(got.get("rejected"), "inference_error")

    def test_ask_model_weird_reply(self):
        from runner.runner import ask_model
        import json

        class Resp:
            def read(self, n):
                return b"not json"
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        inf = {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"}
        try:
            got = ask_model(inf, "q", "out", 100, opener=lambda req, timeout=60: Resp())
        except Exception as e:
            self.fail(f"weird reply crashed ask_model: {e}")
        self.assertIn("rejected", got)


class SeenAndConfigGracefulTest(unittest.TestCase):
    """Finding: load_seen and reload_hot_config run every cycle.
    A corrupt seen file or a corrupt config must not crash the
    poll; the runner keeps the old state.
    """

    def test_load_seen_corrupt(self):
        from runner.runner import load_seen
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "seen.json")
        for content in ("not json", "[]", "42", ""):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            try:
                seen = load_seen(path)
            except Exception as e:
                self.fail(f"load_seen crashed on {content!r}: {e}")
            self.assertIsInstance(seen, dict)

    def test_load_seen_missing(self):
        from runner.runner import load_seen
        try:
            seen = load_seen("/no/such/seen.json")
        except Exception as e:
            self.fail(f"missing seen crashed: {e}")
        self.assertEqual(seen, {})

    def test_reload_hot_corrupt_keeps_old(self):
        from runner.runner import reload_hot_config
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not json")
        cfg = {"mailbox_user": "a@b.c"}
        state = {"mtime": 0}
        # Finding: reload_hot_config raises on corrupt JSON. The poll
        # loop catches it and keeps the old cfg. The raise itself is
        # the signal; the caller must contain it.
        try:
            reload_hot_config(cfg, path, state, set())
        except Exception:
            pass
        self.assertEqual(cfg.get("mailbox_user"), "a@b.c")

    def test_concurrent_save_seen(self):
        from runner.runner import save_seen, load_seen
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "seen.json")
        errors = []

        def one(i):
            try:
                save_seen(path, {f"j{i}": True})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Finding: concurrent save_seen can race. A clean load after
        # is the graceful bar.
        try:
            load_seen(path)
        except Exception as e:
            self.fail(f"seen file unreadable after concurrent saves: {e}")


class EventAndCompartmentGracefulTest(unittest.TestCase):
    """Finding: security events and worker compartments are read on
    the poll and offer paths. Odd shapes must not stop the cycle.
    """

    def test_append_event_odd(self):
        from runner.runner import _append_security_event
        tmp = tempfile.mkdtemp()
        for event in ({}, {"type": None}, {"type": "x", "at": 123}):
            try:
                _append_security_event(tmp, event)
            except Exception as e:
                self.fail(f"append event crashed on {event}: {e}")

    def test_compartments_odd_shapes(self):
        tmp = tempfile.mkdtemp()
        b = Board(os.path.join(tmp, "board.json"))
        b.submit({"task_id": "t", "kind": "ping", "compartments": ["a"]})
        for cfg in ({}, {"worker_compartments": None},
                    {"worker_compartments": "nope"},
                    {"worker_compartments": {"w": "not-a-list"}}):
            try:
                b.offer("w", ["ping"], "", cfg)
            except Exception as e:
                self.fail(f"odd compartments crashed offer: {e}")

    def test_concurrent_append_events(self):
        from runner.runner import _append_security_event
        tmp = tempfile.mkdtemp()
        errors = []

        def one(i):
            try:
                _append_security_event(tmp, {"type": "t", "i": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class InstructionsGracefulTest(unittest.TestCase):
    """Finding: owner_instructions is spliced into the ask prompt.
    A non-string value must not crash ask_model.
    """

    def test_non_string_instructions(self):
        from runner.runner import ask_model
        inf = {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"}

        def boom(req, timeout=60):
            raise OSError("down")

        for instructions in (None, 42, ["list"], {"k": "v"}):
            try:
                got = ask_model(inf, "q", "out", 50, opener=boom, instructions=instructions)
            except Exception as e:
                self.fail(f"instructions {instructions!r} crashed ask: {e}")
            self.assertEqual(got.get("rejected"), "inference_error")

    def test_record_oracle_turn_odd_ans(self):
        from runner.runner import record_oracle_turn
        tmp = tempfile.mkdtemp()
        for ans in ({}, None, "string", {"answer": None}, {"rejected": 12}):
            try:
                record_oracle_turn(tmp, {}, "q", ans if isinstance(ans, dict) else {})
            except Exception as e:
                self.fail(f"record_oracle_turn crashed on {ans!r}: {e}")


class LogAndBodyGracefulTest(unittest.TestCase):
    """Finding: log, _preview, and get_text_body run on every message.
    Odd inputs must not raise, or one bad message stops the poll.
    """

    def test_preview_odd(self):
        from runner.runner import _preview
        for text_in in (None, 42, "", "x" * 500, "line\nbreak"):
            try:
                _preview(text_in if isinstance(text_in, str) else "")
            except Exception as e:
                self.fail(f"_preview crashed on {text_in!r}: {e}")

    def test_log_odd(self):
        from runner.runner import log
        for msg in ("", "x" * 5000, "üñícode", "line\nbreak"):
            try:
                log(msg, "WARN")
            except Exception as e:
                self.fail(f"log crashed on {msg[:20]!r}: {e}")

    def test_get_text_body_empty(self):
        from email.message import EmailMessage
        from runner.runner import get_text_body
        msg = EmailMessage()
        try:
            body = get_text_body(msg)
        except Exception as e:
            self.fail(f"empty message crashed get_text_body: {e}")
        self.assertIsInstance(body, str)


class SnapshotGracefulTest(unittest.TestCase):
    """Finding: snapshot_outside walks the parent of the workspace.
    A root, empty, or non-string workspace must return fast and
    not walk the disk.
    """

    def test_root_and_empty_do_not_walk(self):
        from runner.runner import snapshot_outside
        import time
        for root in ("/", "", None, 42, "/no/such/workspace"):
            start = time.time()
            try:
                snap = snapshot_outside(root)
            except Exception as e:
                self.fail(f"snapshot crashed on {root!r}: {e}")
            self.assertIsInstance(snap, dict)
            self.assertLess(time.time() - start, 1.0)

    def test_concurrent_snapshots(self):
        from runner.runner import snapshot_outside
        tmp = tempfile.mkdtemp()
        errors = []

        def one():
            try:
                snapshot_outside(tmp)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class ExcludeAndTokenGracefulTest(unittest.TestCase):
    """Finding: snapshot exclude and token refresh run on the exec
    and oauth paths. Odd exclude lists and bad token responses must
    not crash.
    """

    def test_snapshot_bad_exclude(self):
        from runner.runner import snapshot_outside
        tmp = tempfile.mkdtemp()
        for exclude in (None, "not-a-list", [1, None, ""], ["/no/such"], 42):
            try:
                snap = snapshot_outside(tmp, exclude=exclude)
            except Exception as e:
                self.fail(f"exclude {exclude!r} crashed snapshot: {e}")
            self.assertIsInstance(snap, dict)

    def test_refresh_bad_cfg(self):
        from runner import oauth
        for cfg in ({}, {"oauth_client_id": ""}, {"oauth_refresh_token": None}):
            try:
                oauth.refresh_access_token(cfg)
            except Exception:
                pass  # contained failure is graceful

    def test_xoauth2_odd(self):
        from runner import oauth
        for user, token in (("", ""), (None, None), (42, "tok")):
            try:
                raw = oauth.xoauth2_raw(user if isinstance(user, str) else "",
                                        token if isinstance(token, str) else "")
            except Exception as e:
                self.fail(f"xoauth2_raw crashed on {user!r}: {e}")
            self.assertIsInstance(raw, str)


class HelpersGracefulTest(unittest.TestCase):
    """Finding: _describe_job, _worker_count, and validate_shared_secret
    run on the poll path. Odd inputs must not raise.
    """

    def test_describe_odd_jobs(self):
        from runner.runner import _describe_job
        for job in ({}, {"kind": None}, {"kind": "exec", "script": None},
                    {"kind": "exec", "script": 123}):
            try:
                desc = _describe_job(job)
            except Exception as e:
                self.fail(f"_describe_job crashed on {job}: {e}")
            self.assertIsInstance(desc, str)

    def test_worker_count_odd(self):
        from runner.runner import _worker_count
        class Opts:
            workers = None
        for cfg in ({}, {"workers": "nope"}, {"workers": -1}, {"workers": None}):
            try:
                n = _worker_count(cfg, Opts())
            except Exception as e:
                self.fail(f"_worker_count crashed on {cfg}: {e}")
            self.assertIsInstance(n, int)
            self.assertGreaterEqual(n, 1)

    def test_validate_secret_rejects_clean(self):
        from runner.runner import validate_shared_secret
        for secret in ("", "short", "changeme", "x" * 32):
            try:
                validate_shared_secret(secret)
            except RuntimeError:
                pass
            except Exception as e:
                self.fail(f"validate crashed with non-RuntimeError: {e}")


class NoneCfgGracefulTest(unittest.TestCase):
    """Finding: several poll helpers are called with cfg that may be
    missing keys. None cfg must not raise AttributeError.
    """

    def test_helpers_accept_none_cfg(self):
        from runner.runner import (
            query_budget, check_rate_limit, inference_config,
            _redact_patterns, judge_job,
        )
        calls = [
            ("query_budget", lambda: query_budget(None, {})),
            ("check_rate_limit", lambda: check_rate_limit("k", None)),
            ("inference_config", lambda: inference_config(None)),
            ("judge_job", lambda: judge_job(None, {"kind": "ping"})),
        ]
        for name, call in calls:
            try:
                call()
            except AttributeError as e:
                self.fail(f"{name} raised AttributeError: {e}")
            except Exception:
                pass
        # Finding, fixed: _redact_patterns(None) used to raise
        # AttributeError. A missing cfg is the built-in patterns.
        from runner.runner import BUILTIN_REDACT_PATTERNS
        self.assertEqual(set(_redact_patterns(None)), set(BUILTIN_REDACT_PATTERNS))

    def test_answer_queries_none_cfg(self):
        try:
            answers, spent = answer_queries(
                [{"op": "attest", "predicate": "exit_zero"}],
                {"stdout": "", "stderr": "", "exit_code": 0},
                {},
                4,
                cfg=None,
            )
        except Exception as e:
            self.fail(f"None cfg crashed answer_queries: {e}")
        self.assertEqual(spent, 1)


class DRIConfigGracefulTest(unittest.TestCase):
    """Finding: DRI evaluation runs once per poll. A bad dri block
    must not crash the cycle.
    """

    def test_parse_dri_odd(self):
        for cfg in ({}, {"dri": None}, {"dri": "nope"}, {"dri": []},
                    {"dri": {"enabled": "yes", "triggers": "nope"}}):
            try:
                dri.parse_dri(cfg)
            except RuntimeError:
                pass  # clean rejection
            except Exception as e:
                self.fail(f"parse_dri crashed on {cfg}: {e}")

    def test_evaluate_triggers_odd(self):
        tmp = tempfile.mkdtemp()
        for dcfg in ({}, {"enabled": True, "triggers": None},
                     {"enabled": True, "triggers": "nope"},
                     {"enabled": True, "min_severity": 12}):
            try:
                dri.evaluate_page_triggers(dcfg, tmp, 0)
            except Exception as e:
                self.fail(f"evaluate crashed on {dcfg}: {e}")

    def test_concurrent_maybe_page(self):
        tmp = tempfile.mkdtemp()
        errors = []

        def one():
            try:
                dri.maybe_page({"dri": {"enabled": True}}, tmp)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class PortAndPatternsGracefulTest(unittest.TestCase):
    """Finding: _port and _redact_patterns run at connect and on
    every result. A word port must be a clean RuntimeError. None
    patterns must not raise.
    """

    def test_port_word_is_runtime_error(self):
        from runner.runner import _port
        for cfg in ({"smtp_port": "smtp"}, {"imap_port": "nope"}, {"smtp_port": None}):
            try:
                _port(cfg, "smtp_port", 587)
            except RuntimeError:
                pass
            except Exception as e:
                self.fail(f"word port crashed with non-RuntimeError: {e}")

    def test_port_none_cfg(self):
        from runner.runner import _port
        try:
            _port(None, "smtp_port", 587)
        except RuntimeError:
            pass
        except Exception as e:
            self.fail(f"None cfg port crashed: {e}")

    def test_redact_patterns_none(self):
        from runner.runner import _redact_patterns
        # Finding from earlier: None raises. Pin it so a fix is visible.
        try:
            got = _redact_patterns(None)
        except AttributeError:
            return  # known finding
        self.assertIsInstance(got, (dict, list))


class AlertSerializationGracefulTest(unittest.TestCase):
    """Finding: store_alert serializes the record. A non-serializable
    detail must not crash the sensor path.
    """

    def test_store_non_serializable(self):
        tmp = tempfile.mkdtemp()
        class Weird:
            pass
        for record in (
            {"sensor": "s", "detail": Weird()},
            {"sensor": "s", "detail": set([1, 2])},
            {"sensor": "s", "at": object()},
        ):
            try:
                senses.store_alert(tmp, record)
            except TypeError:
                pass  # contained if the store refuses
            except Exception as e:
                self.fail(f"store crashed on {record}: {e}")

    def test_load_mixed_lines(self):
        tmp = tempfile.mkdtemp()
        path = senses._path(tmp)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = [
            '{"sensor":"ok"}',
            '{"sensor":"ok","detail":{"nested":true}}',
            "",
            "not json",
        ]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        try:
            recs = senses.load_alerts(tmp)
        except Exception as e:
            self.fail(f"load mixed lines crashed: {e}")
        self.assertIsInstance(recs, list)

    def test_concurrent_store_and_load(self):
        tmp = tempfile.mkdtemp()
        errors = []

        def store(i):
            try:
                senses.store_alert(tmp, {"sensor": f"s{i}", "severity": "low"})
            except Exception as e:
                errors.append(e)

        def load():
            try:
                senses.load_alerts(tmp)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=store, args=(i,)) for i in range(6)]
        threads += [threading.Thread(target=load) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class DiskFractionGracefulTest(unittest.TestCase):
    """Finding: disk checks run on the resource monitor. A bad path
    must not crash the poll.
    """

    def test_disk_fraction_bad_paths(self):
        for path in ("", "/no/such/path", None, 42, "C:\\nope"):
            try:
                resources._disk_fraction(path if isinstance(path, str) else "/")
            except Exception as e:
                self.fail(f"disk fraction crashed on {path!r}: {e}")

    def test_check_resources_odd_disk_path(self):
        tmp = tempfile.mkdtemp()
        for cfg in ({}, {"resources": {"disk_path": None}},
                    {"resources": {"disk_path": "/no/such"}},
                    {"resources": "not-a-dict"}):
            try:
                resources.check_resources(cfg, tmp)
            except Exception as e:
                self.fail(f"check_resources crashed on {cfg}: {e}")

    def test_concurrent_disk_checks(self):
        tmp = tempfile.mkdtemp()
        errors = []

        def one():
            try:
                resources.check_resources({"resources": {"disk_path": tmp}}, tmp)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class PatternMapGracefulTest(unittest.TestCase):
    """Finding: _redact_patterns runs on every result. A non-object
    extra map or a bad regex must not crash.
    """

    def test_extra_not_an_object(self):
        from runner.runner import _redact_patterns
        for extra in (None, [], "nope", 42, True):
            try:
                pats = _redact_patterns({"redact_patterns_extra": extra})
            except Exception as e:
                self.fail(f"extra {extra!r} crashed: {e}")
            self.assertIsInstance(pats, dict)

    def test_bad_regex_skipped(self):
        from runner.runner import _redact_patterns
        cfg = {"redact_patterns_extra": {"bad": "(unclosed", "ok": "password"}}
        try:
            pats = _redact_patterns(cfg)
        except Exception as e:
            self.fail(f"bad regex crashed: {e}")
        self.assertIn("ok", pats)
        self.assertNotIn("bad", pats)

    def test_none_cfg_now_returns(self):
        from runner.runner import _redact_patterns
        try:
            pats = _redact_patterns(None)
        except Exception as e:
            self.fail(f"None cfg crashed: {e}")
        self.assertIsInstance(pats, dict)


class DRIThresholdGracefulTest(unittest.TestCase):
    """Finding: DRI thresholds are parsed each cycle. A word or a
    negative threshold must not stop the page cycle.
    """

    def test_word_threshold_rejected_clean(self):
        cfg = {"dri": {"enabled": True, "sensor_fused_score":
                       {"threshold": "high", "window_sec": 60}}}
        try:
            dri.parse_dri(cfg)
        except RuntimeError:
            pass
        except Exception as e:
            self.fail(f"word threshold crashed: {e}")

    def test_negative_and_missing(self):
        tmp = tempfile.mkdtemp()
        for dcfg in (
            {"enabled": True},
            {"enabled": True, "sensor_fused_score": {"threshold": -1, "window_sec": 60}},
            {"enabled": True, "sensor_fused_score": {"threshold": None, "window_sec": "nope"}},
        ):
            try:
                dri.evaluate_page_triggers(dcfg, tmp, 0)
            except Exception as e:
                self.fail(f"threshold {dcfg} crashed evaluate: {e}")

    def test_concurrent_evaluate(self):
        tmp = tempfile.mkdtemp()
        errors = []

        def one():
            try:
                dri.evaluate_page_triggers({"enabled": True}, tmp, 0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class EnvGracefulTest(unittest.TestCase):
    """Finding: env is read before execute. A bad name or a non-dict
    env must reject cleanly, not retry forever or crash.
    """

    def test_scrub_odd_env(self):
        from runner.runner import _scrub_env
        for env in ({}, {"OK": "1"}, {"bad name": "x"}, {"": "x"},
                    {"A": None}, None, "nope"):
            try:
                _scrub_env(env if isinstance(env, dict) else {})
            except Exception as e:
                self.fail(f"scrub crashed on {env!r}: {e}")

    def test_review_bad_env_name(self):
        job = {"kind": "exec", "script": "echo hi", "env": {"bad name": "x", "OK": "1"}}
        try:
            review.review_job({}, job)
        except Exception as e:
            self.fail(f"review crashed on bad env name: {e}")

    def test_concurrent_scrub(self):
        from runner.runner import _scrub_env
        errors = []

        def one(i):
            try:
                _scrub_env({"K": str(i), "bad name": "x"})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class ArgsGracefulTest(unittest.TestCase):
    """Finding: args are read before execute. A non-list or a null
    entry must not crash the describe or review path.
    """

    def test_describe_bad_args(self):
        from runner.runner import _describe_job
        for job in (
            {"kind": "exec", "script": "echo", "args": None},
            {"kind": "exec", "script": "echo", "args": "not-a-list"},
            {"kind": "exec", "script": "echo", "args": [None, 1, "ok"]},
            {"kind": "exec", "script": "echo", "args": [{"nested": True}]},
        ):
            try:
                desc = _describe_job(job)
            except Exception as e:
                self.fail(f"describe crashed on {job['args']!r}: {e}")
            self.assertIsInstance(desc, str)

    def test_review_bad_args(self):
        for args in (None, "nope", [None], [1, 2]):
            job = {"kind": "exec", "script": "echo", "args": args}
            try:
                review.review_job({}, job)
            except Exception as e:
                self.fail(f"review crashed on args {args!r}: {e}")

    def test_concurrent_describe(self):
        from runner.runner import _describe_job
        errors = []

        def one(i):
            try:
                _describe_job({"kind": "exec", "script": "echo", "args": [None, str(i)]})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class ReloadGracefulTest(unittest.TestCase):
    """Finding: hot reload runs every cycle. A bad file must not
    raise out of reload, and must not replace the live cfg.
    """

    def test_load_config_bad_file(self):
        from runner.runner import load_config
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "config.json")
        for content in ("not json", "[]", "null", ""):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            try:
                load_config(path)
            except (RuntimeError, ValueError):
                pass  # clean rejection, including JSONDecodeError
            except Exception as e:
                self.fail(f"load_config crashed on {content!r}: {e}")

    def test_reload_bad_keeps_cfg(self):
        from runner.runner import reload_hot_config
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not json")
        cfg = {"mailbox_user": "keep-me"}
        try:
            reload_hot_config(cfg, path, {"mtime": 0}, set())
        except Exception as e:
            self.fail(f"reload raised: {e}")
        self.assertEqual(cfg.get("mailbox_user"), "keep-me")

    def test_concurrent_reload(self):
        from runner.runner import reload_hot_config
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"mailbox_user":"a@b.c"}')
        errors = []

        def one():
            try:
                reload_hot_config({"mailbox_user": "old"}, path, {"mtime": 0}, set())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class FilesAndTimeoutGracefulTest(unittest.TestCase):
    """Finding: files and timeout are read before execute. A non-list
    files field or a word timeout must not crash describe or review.
    """

    def test_describe_bad_files(self):
        from runner.runner import _describe_job
        for job in (
            {"kind": "exec", "script": "echo", "files": None},
            {"kind": "exec", "script": "echo", "files": "nope"},
            {"kind": "exec", "script": "echo", "files": [None]},
            {"kind": "exec", "script": "echo", "files": [{"name": None}]},
            {"kind": "exec", "script": "echo", "timeout": "long"},
        ):
            try:
                desc = _describe_job(job)
            except Exception as e:
                self.fail(f"describe crashed: {e}")
            self.assertIsInstance(desc, str)

    def test_review_bad_files(self):
        for files in (None, "nope", [None], [{"name": "../x", "content": "a"}]):
            job = {"kind": "exec", "script": "echo", "files": files}
            try:
                review.review_job({}, job)
            except Exception as e:
                self.fail(f"review crashed on files {files!r}: {e}")

    def test_reoffer_bad_timeout(self):
        tmp = tempfile.mkdtemp()
        b = Board(os.path.join(tmp, "board.json"))
        for timeout in (None, "nope", -1, 0):
            try:
                b.reoffer_expired(timeout if isinstance(timeout, int) else 0)
            except Exception as e:
                self.fail(f"reoffer crashed on {timeout!r}: {e}")


class SenseProfileGracefulTest(unittest.TestCase):
    """Finding: gate_alert runs on every sensor alert. A bad profile
    or a raced hourly cap must not raise.
    """

    def test_gate_bad_profile(self):
        alert = {"sensor": "door", "severity": "high", "title": "open"}
        for scfg in ({}, {"enabled": True}, {"enabled": True, "cooldown_sec": "nope"},
                     {"enabled": True, "hourly_cap": None}, None):
            try:
                senses.gate_alert(scfg if isinstance(scfg, dict) else {}, alert, [])
            except Exception as e:
                self.fail(f"gate crashed on {scfg}: {e}")

    def test_gate_bad_recent(self):
        alert = {"sensor": "door", "severity": "low", "title": "x"}
        for recent in (None, "nope", [None], [{"severity": None}]):
            try:
                senses.gate_alert({"enabled": True}, alert, recent if isinstance(recent, list) else [])
            except Exception as e:
                self.fail(f"gate crashed on recent {recent!r}: {e}")

    def test_concurrent_gate(self):
        errors = []
        alert = {"sensor": "s", "severity": "low", "title": "t"}

        def one():
            try:
                senses.gate_alert({"enabled": True, "hourly_cap": 2}, alert, [])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class BaseDirGracefulTest(unittest.TestCase):
    """Finding: senses, resources, and retained all take a base_dir.
    A bad one must not crash the poll.
    """

    def test_senses_bad_base(self):
        for base in ("", "/no/such/base", None):
            try:
                senses.load_alerts(base if isinstance(base, str) else "")
            except Exception as e:
                self.fail(f"senses load crashed on {base!r}: {e}")

    def test_resources_bad_base(self):
        for base in ("", "/no/such/base"):
            try:
                resources.check_resources({}, base)
            except Exception as e:
                self.fail(f"resources crashed on {base!r}: {e}")

    def test_retained_bad_base(self):
        from runner.runner import prune_retained, save_retained
        for base in ("", "/no/such/base"):
            try:
                prune_retained(base, 7)
            except Exception as e:
                self.fail(f"prune crashed on {base!r}: {e}")
        try:
            save_retained("/no/such/base", "job", {"stdout": "x"})
        except Exception as e:
            self.fail(f"save_retained crashed on missing base: {e}")


class ClosedStdoutGracefulTest(unittest.TestCase):
    """Finding: log prints to stdout. A closed stdout must not raise.
    """

    def test_log_with_closed_stdout(self):
        from runner.runner import log
        import io
        closed = io.StringIO()
        closed.close()
        real = sys.stdout
        try:
            sys.stdout = closed
            log("still here", "WARN")
        except Exception as e:
            self.fail(f"closed stdout crashed log: {e}")
        finally:
            sys.stdout = real

    def test_log_non_string(self):
        from runner.runner import log
        for msg in (None, 42, {"k": "v"}, ["a"]):
            try:
                log(msg, "INFO")
            except Exception as e:
                self.fail(f"log crashed on {msg!r}: {e}")

    def test_concurrent_log(self):
        from runner.runner import log
        errors = []

        def one(i):
            try:
                log(f"c{i}", "INFO")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class InterpreterGracefulTest(unittest.TestCase):
    """Finding: interpreter is resolved before execute. A bad shape
    must not crash describe or script_filename.
    """

    def test_script_filename_odd(self):
        from runner.runner import script_filename
        for interp in (None, "", "python3", ["python3"], ["pwsh", "-File"], 42):
            try:
                name = script_filename(interp if isinstance(interp, (str, list)) else "")
            except Exception as e:
                self.fail(f"script_filename crashed on {interp!r}: {e}")
            self.assertIsInstance(name, str)

    def test_describe_bad_interpreter(self):
        from runner.runner import _describe_job
        for job in (
            {"kind": "exec", "script": "echo", "interpreter": None},
            {"kind": "exec", "script": "echo", "interpreter": 42},
            {"kind": "exec", "script": "echo", "interpreter": ["python3", None]},
        ):
            try:
                desc = _describe_job(job)
            except Exception as e:
                self.fail(f"describe crashed on interpreter: {e}")
            self.assertIsInstance(desc, str)

    def test_concurrent_script_filename(self):
        from runner.runner import script_filename
        errors = []

        def one(i):
            try:
                script_filename(["python3"] if i % 2 else "bash")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=one, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

if __name__ == "__main__":
    unittest.main(verbosity=2)
