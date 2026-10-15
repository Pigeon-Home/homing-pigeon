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


if __name__ == "__main__":
    unittest.main(verbosity=2)
