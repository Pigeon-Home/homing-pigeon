# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""A dry run verifies and says what it would do, and changes nothing
(--dry-run: execute nothing, send nothing, change nothing). Two
readers changed things under it (Q87, found by de_dust's query
and board_mail targets): a query answered under a dry run took a
slot of the sender's hourly window and spent the retained record's
budget, and a board message moved the board. Now the window is only
peeked, the record stays as it was, the board is not touched, and
both readers still say in the log what would have happened."""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner  # noqa: E402
from runner.cloud.send_job import sign_payload  # noqa: E402
from runner.runner import (  # noqa: E402
    Board, check_rate_limit, handle_board_mail, handle_query_mail,
    load_retained, save_retained)
from runner.tests.security_parity import (  # noqa: E402
    SECRET, WRONG_SECRET, FakeIMAP, FakeSMTP, base_config)
from runner.tests.test_cli_options import _captured_log  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402


class _Opts:
    dry_run = False
    no_send = False


class _DryOpts(_Opts):
    dry_run = True


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sealed(obj, ident, secret=SECRET):
    return jobcrypto.encrypt_body(sign_payload(obj, secret), secret,
                                  job_id=ident, key_id="", sign=sign_payload)


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class RateLimitPeekTest(unittest.TestCase):
    def test_a_peek_takes_no_slot_and_writes_nothing(self):
        cfg = {"max_queries_per_hour": 2}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "query_times.json")
            self.assertTrue(check_rate_limit("k", cfg, path, peek=True))
            self.assertFalse(os.path.exists(path))
            self.assertTrue(check_rate_limit("k", cfg, path))
            self.assertTrue(check_rate_limit("k", cfg, path))
            before = _read(path)
            self.assertFalse(check_rate_limit("k", cfg, path, peek=True))
            self.assertEqual(_read(path), before)
            self.assertTrue(check_rate_limit("other", cfg, path, peek=True))
            self.assertEqual(_read(path), before)
            self.assertEqual(len(json.loads(before)["k"]), 2)
        # The in-memory window, the same way.
        saved = dict(runner._QUERY_TIMES)
        try:
            runner._QUERY_TIMES.clear()
            self.assertTrue(check_rate_limit("m", {"max_queries_per_hour": 1},
                                             peek=True))
            self.assertEqual(runner._QUERY_TIMES, {})
            self.assertTrue(check_rate_limit("m", {"max_queries_per_hour": 1}))
            self.assertFalse(check_rate_limit("m", {"max_queries_per_hour": 1},
                                              peek=True))
            self.assertEqual(len(runner._QUERY_TIMES["m"]), 1)
        finally:
            runner._QUERY_TIMES.clear()
            runner._QUERY_TIMES.update(saved)


class _ReaderTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="hp-dry-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.saved = (runner._VERBOSE, runner._VERBOSE_LEVEL)
        self.addCleanup(self._restore)
        runner._set_verbosity(2)
        self.cfg = base_config(self.dir)
        self.cfg["max_queries_per_hour"] = 1

    def _restore(self):
        runner._VERBOSE, runner._VERBOSE_LEVEL = self.saved


class QueryDryRunTest(_ReaderTest):
    JOB = "bm-dry-job-1"

    def setUp(self):
        super().setUp()
        save_retained(self.dir, self.JOB, {
            "stdout": "one\ntwo\n", "stderr": "", "exit_code": 0,
            "budget": 8, "spent": 0, "saved_at": time.time(),
            "view": "full"})
        self.window = os.path.join(self.dir, "query_times.json")

    def _take(self, opts, query_id="bm-dry-q-1", queries=None, seen=None):
        obj = {"v": 1, "type": "query", "query_id": query_id,
               "job_id": self.JOB, "issued_at": _now(),
               "queries": queries or [{"op": "tail", "lines": 1}]}
        subject = "[HOMING-PIGEON] query " + query_id
        imap, smtp = FakeIMAP([]), FakeSMTP()
        with _captured_log() as buf:
            handled = handle_query_mail(
                self.cfg, imap, smtp, b"1", _mail(subject, _sealed(obj, query_id)),
                subject, runner.build_secrets(self.cfg), opts, self.dir, seen)
        self.assertTrue(handled)
        return buf.getvalue(), imap, smtp

    def test_a_dry_run_answers_in_the_log_and_spends_nothing(self):
        seen = {}
        out, imap, smtp = self._take(_DryOpts(), seen=seen)
        self.assertIn("query op=tail", out)
        self.assertNotIn("rejected", out)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(imap.flagged, [])
        self.assertEqual(seen, {})
        self.assertEqual(load_retained(self.dir, self.JOB)["spent"], 0)
        self.assertFalse(os.path.exists(self.window))

    def test_the_live_run_spends_what_the_dry_run_showed(self):
        self._take(_DryOpts())
        seen = {}
        out, imap, smtp = self._take(_Opts(), seen=seen)
        self.assertIn("query op=tail", out)
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(imap.flagged, [b"1"])
        self.assertEqual(list(seen), ["query:bm-dry-q-1"])
        self.assertEqual(load_retained(self.dir, self.JOB)["spent"], 1)
        self.assertEqual(len(json.loads(_read(self.window))[""]), 1)

    def test_a_dry_run_still_names_a_sender_over_the_cap(self):
        self._take(_Opts())                        # the one slot of the hour
        before = _read(self.window)
        out, imap, smtp = self._take(_DryOpts(), query_id="bm-dry-q-2")
        self.assertIn("rate limit exceeded", out)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(imap.flagged, [])
        self.assertEqual(_read(self.window), before)
        self.assertEqual(load_retained(self.dir, self.JOB)["spent"], 1)

    def test_a_dry_run_leaves_a_record_at_its_last_budget(self):
        self._take(_Opts(), queries=[{"op": "tail", "lines": 1},
                                     {"op": "grep", "pattern": "one"}])
        self.assertEqual(load_retained(self.dir, self.JOB)["spent"], 2)
        self.cfg["max_queries_per_hour"] = 0
        for n in range(3):
            self._take(_DryOpts(), query_id=f"bm-dry-q-{n + 3}",
                       queries=[{"op": "attest", "check": "exit_code",
                                 "value": 0}] * 3)
        self.assertEqual(load_retained(self.dir, self.JOB)["spent"], 2)


class BoardDryRunTest(_ReaderTest):
    def setUp(self):
        super().setUp()
        self.path = os.path.join(self.dir, "board.json")
        self.board = Board(self.path)
        self.board.tasks["t1"] = {"task_id": "t1", "state": "pending_review"}
        self.board.save()
        self.before = _read(self.path)

    def _take(self, opts, kind="task_approve", ident="t1", obj=None,
              secret=SECRET):
        obj = obj or {"v": 1, "type": kind}
        subject = f"[HOMING-PIGEON] {kind} {ident}"
        imap, smtp = FakeIMAP([]), FakeSMTP()
        with _captured_log() as buf:
            handled = handle_board_mail(
                self.cfg, imap, smtp, b"1",
                _mail(subject, _sealed(obj, ident, secret)), subject,
                self.board, runner.build_secrets(self.cfg), opts, self.dir)
        self.assertTrue(handled)
        return buf.getvalue(), imap, smtp

    def test_a_dry_run_leaves_the_board_and_sends_nothing(self):
        out, imap, smtp = self._take(_DryOpts())
        self.assertIn("dry run: board task_approve t1 verified, not applied", out)
        self.assertEqual(self.board.tasks["t1"]["state"], "pending_review")
        self.assertEqual(_read(self.path), self.before)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(imap.flagged, [])

    def test_a_dry_run_submission_adds_no_task(self):
        task = {"v": 1, "type": "task_submit", "task_id": "t2",
                "title": "count", "priority": 1,
                "required_capabilities": ["shell"]}
        out, _imap, smtp = self._take(_DryOpts(), "task_submit", "t2", task)
        self.assertIn("dry run: board task_submit t2 verified, not applied", out)
        self.assertNotIn("t2", self.board.tasks)
        self.assertEqual(_read(self.path), self.before)
        self.assertEqual(smtp.sent, [])

    def test_a_bad_signature_is_refused_under_a_dry_run_too(self):
        out, _imap, smtp = self._take(_DryOpts(), secret=WRONG_SECRET)
        self.assertIn("board reject", out)
        self.assertNotIn("verified", out)
        self.assertEqual(_read(self.path), self.before)
        self.assertEqual(smtp.sent, [])

    def test_the_live_run_applies_what_the_dry_run_showed(self):
        self._take(_DryOpts())
        out, imap, smtp = self._take(_Opts())
        self.assertNotIn("dry run", out)
        self.assertEqual(self.board.tasks["t1"]["state"], "done")
        self.assertNotEqual(_read(self.path), self.before)
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(imap.flagged, [b"1"])


if __name__ == "__main__":
    unittest.main()
