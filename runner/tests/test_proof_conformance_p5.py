#!/usr/bin/env python3
"""Stage 5 conformance for P5: a job runs at most once, and a
repeat is answered from the record, never by running again.

The pinning test in test_proof_constraints.py holds the three
layers' mechanics. These tests drive the layers in the order
handle_mail meets them, against one shared runner home so the
disk state is real: the in-memory claim, the seen.json cache,
the claim file another process holds, and the recorded result
in the outbox and sent store -- including the two priced
windows the property names (a crash between the run and the
stash; the record ageing out). Clause numbers are
properties.md's P5 clauses.
"""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner import runner  # noqa: E402

try:
    from runner.tests import test_proof_conformance as base
except ImportError:  # pragma: no cover - direct-file runs
    import test_proof_conformance as base


def _raw(job):
    return base._wire2(job)


def _skey_of(out):
    keys = list(out.seen)
    assert len(keys) == 1, keys
    return keys[0]


class ReplayDoorTest(base._GateCase):
    """Clauses 1 to 4 at the door: the layers in order."""

    def test_the_same_delivery_twice_executes_once(self):
        job = base._job2("rp-1")
        raw = _raw(job)
        with tempfile.TemporaryDirectory() as td:
            first = base._run(raw=raw, base_dir=td)
            self.assertEqual(len(first.executed), 1)
            second = base._run(raw=raw, base_dir=td,
                               seen=first.seen)
            self.assertEqual(second.executed, [])
            # The in-memory claim answers first: nothing is
            # sent again, and the copy is marked seen.
            self.assertEqual(second.sent, [])
            self.assertTrue(second.store_calls)

    def test_a_fresh_cache_reads_the_disk_cache_not_the_record(self):
        job = base._job2("rp-2")
        raw = _raw(job)
        with tempfile.TemporaryDirectory() as td:
            first = base._run(raw=raw, base_dir=td)
            self.assertEqual(len(first.executed), 1)
            no_record = mock.patch.object(
                runner, "load_sent_result",
                side_effect=AssertionError("record consulted"))
            second = base._run(raw=raw, base_dir=td, seen={},
                               patches=(no_record,))
            self.assertEqual(second.executed, [])
            self.assertEqual(second.sent, [])
            self.assertTrue(second.store_calls)

    def test_the_record_is_resent_when_the_cache_is_gone(self):
        job = base._job2("rp-3")
        raw = _raw(job)
        with tempfile.TemporaryDirectory() as td:
            first = base._run(raw=raw, base_dir=td)
            self.assertEqual(len(first.executed), 1)
            skey = _skey_of(first)
            os.remove(os.path.join(td, "seen.json"))
            second = base._run(raw=raw, base_dir=td, seen={})
            self.assertEqual(second.executed, [])
            # The recorded bytes are what goes out again.
            self.assertEqual(len(second.sent), 1)
            self.assertEqual(second.sent[0][1], first.sent[0][1])
            self.assertIn(skey, second.seen)

    def test_a_different_job_under_the_same_id_runs_on_its_own(self):
        job_a = base._job2("rp-4", script="echo A")
        job_b = base._job2("rp-4", script="echo B")
        with tempfile.TemporaryDirectory() as td:
            first = base._run(raw=_raw(job_a), base_dir=td)
            self.assertEqual(len(first.executed), 1)
            os.remove(os.path.join(td, "seen.json"))
            second = base._run(raw=_raw(job_b), base_dir=td,
                               seen={})
            self.assertEqual(len(second.executed), 1)
            self.assertEqual(second.executed[0]["script"],
                             "echo B")

    def test_a_live_claim_defers_the_job_unseen(self):
        job = base._job2("rp-5")
        raw = _raw(job)
        with tempfile.TemporaryDirectory() as td:
            probe = base._run(raw=raw, base_dir=td)
            skey = _skey_of(probe)
        with tempfile.TemporaryDirectory() as td:
            folder, claim = runner._claim_path(td, skey)
            os.makedirs(folder, exist_ok=True)
            sleeper = subprocess.Popen(
                [sys.executable, "-c",
                 "import time; time.sleep(60)"])
            try:
                with open(claim, "w", encoding="utf-8") as fh:
                    fh.write("%d\n%r\n%s\n"
                             % (sleeper.pid, time.time(), skey))
                out = base._run(raw=raw, base_dir=td, seen={})
            finally:
                sleeper.terminate()
                sleeper.wait()
            self.assertEqual(out.executed, [])
            self.assertEqual(out.sent, [])
            # Left unseen: a crash in the claiming process can
            # be stolen on a later poll instead of dropped.
            self.assertFalse(out.store_calls)
            self.assertNotIn(skey, out.seen)

    def test_an_inflight_claim_skips_and_marks(self):
        job = base._job2("rp-6")
        raw = _raw(job)
        with tempfile.TemporaryDirectory() as td:
            probe = base._run(raw=raw, base_dir=td)
            skey = _skey_of(probe)
        runner._IN_FLIGHT.add(skey)
        try:
            with tempfile.TemporaryDirectory() as td:
                out = base._run(raw=raw, base_dir=td, seen={})
        finally:
            runner._IN_FLIGHT.discard(skey)
        self.assertEqual(out.executed, [])
        self.assertTrue(out.store_calls)

    def test_a_restart_reads_the_cache_from_disk(self):
        job = base._job2("rp-7")
        raw = _raw(job)
        with tempfile.TemporaryDirectory() as td:
            first = base._run(raw=raw, base_dir=td)
            self.assertEqual(len(first.executed), 1)
            loaded = runner.load_seen(os.path.join(td, "seen.json"))
            second = base._run(raw=raw, base_dir=td, seen=loaded)
            self.assertEqual(second.executed, [])

    def test_the_crash_window_buys_exactly_one_more_run(self):
        # Clause 5, priced: a crash between the run and its
        # result being stashed (here, a stash that reports
        # failure) leaves the job uncommitted, so the next
        # delivery runs it once more -- and commits then.
        job = base._job2("rp-8")
        raw = _raw(job)
        with tempfile.TemporaryDirectory() as td:
            broken = mock.patch.object(runner, "stash_result",
                                       return_value=False)
            try:
                first = base._run(raw=raw, base_dir=td,
                                  patches=(broken,))
            except Exception:
                first = None
            if first is not None:
                self.assertEqual(len(first.executed), 1)
                self.assertEqual(first.seen, {})
            second = base._run(raw=raw, base_dir=td, seen={})
            self.assertEqual(len(second.executed), 1)
            self.assertEqual(len(second.seen), 1)
            third = base._run(raw=raw, base_dir=td,
                              seen=second.seen)
            self.assertEqual(third.executed, [])


class RecordStoreTest(unittest.TestCase):
    """Clauses 3, 5, and 6 at the record store itself."""

    def _deliver(self, td, skey):
        sent = []
        ok = runner.deliver_stash(
            td, skey,
            lambda subject, body, to=None: sent.append(
                (subject, body)))
        return ok, sent

    def test_a_failed_delivery_leaves_the_record_waiting(self):
        job = {"job_id": "rec-1", "kind": "exec",
               "script": "echo ok"}
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(runner.stash_result(
                td, "rec-1-key", job, "subj", "the body"))

            def failing(subject, body, to=None):
                raise OSError("mailbox unreachable")

            self.assertFalse(runner.deliver_stash(
                td, "rec-1-key", failing))
            waiting = runner.load_stash(td, "rec-1-key")
            self.assertIsNotNone(waiting)
            self.assertEqual(waiting["attempts"], 1)
            self.assertTrue(waiting["last_error"])
            ok, sent = self._deliver(td, "rec-1-key")
            self.assertTrue(ok)
            self.assertEqual(sent, [("subj", "the body")])
            self.assertIsNone(runner.load_stash(td, "rec-1-key"))
            record = runner.load_sent_result(td, "rec-1-key", job)
            self.assertIsNotNone(record)
            self.assertEqual(record["body"], "the body")

    def test_the_record_answers_only_the_same_job(self):
        job_a = {"job_id": "rec-2", "kind": "exec",
                 "script": "echo A"}
        job_b = {"job_id": "rec-2", "kind": "exec",
                 "script": "echo B"}
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(runner.stash_result(
                td, "rec-2-key", job_a, "subj", "body A"))
            ok, _sent = self._deliver(td, "rec-2-key")
            self.assertTrue(ok)
            self.assertIsNotNone(runner.load_sent_result(
                td, "rec-2-key", job_a))
            self.assertIsNone(runner.load_sent_result(
                td, "rec-2-key", job_b))

    def test_the_record_check_without_the_opinion_module(self):
        # EXHIBIT -- stage 4's P5 observation, pinned as the
        # current behavior: with the opinion module unloaded,
        # load_sent_result skips its digest comparison and
        # answers a different job under the same key. The
        # module loads unconditionally in the shipped runner;
        # at-most-once is untouched either way (the claim, not
        # this lookup, is what stops a second run).
        job_a = {"job_id": "rec-3", "kind": "exec",
                 "script": "echo A"}
        job_b = {"job_id": "rec-3", "kind": "exec",
                 "script": "echo B"}
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(runner.stash_result(
                td, "rec-3-key", job_a, "subj", "body A"))
            ok, _sent = self._deliver(td, "rec-3-key")
            self.assertTrue(ok)
            with mock.patch.object(runner, "_opinion", None):
                record = runner.load_sent_result(
                    td, "rec-3-key", job_b)
            self.assertIsNotNone(record)
            self.assertEqual(record["body"], "body A")

    def test_records_age_out_on_their_own_retention(self):
        # Clause 6, priced: past the retention the record is
        # deleted, and a later duplicate is a fresh job again
        # (the door-level half of that is the cache-loss test
        # above with no record left to answer from).
        job = {"job_id": "rec-4", "kind": "exec",
               "script": "echo ok"}
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(runner.stash_result(
                td, "rec-4-key", job, "subj", "body"))
            ok, _sent = self._deliver(td, "rec-4-key")
            self.assertTrue(ok)
            path = runner._sent_path(td, "rec-4-key")
            self.assertTrue(os.path.exists(path))
            # Keeping is the default shape of the rule: a zero
            # retention prunes nothing.
            self.assertEqual(runner.prune_sent(td, 0), 0)
            self.assertTrue(os.path.exists(path))
            old = time.time() - 10 * 86400
            os.utime(path, (old, old))
            self.assertEqual(runner.prune_sent(td, 7), 1)
            self.assertFalse(os.path.exists(path))
            self.assertIsNone(runner.load_sent_result(
                td, "rec-4-key", job))


if __name__ == "__main__":
    unittest.main()
