# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""The grep query worker (runner/ops/queries.py): one JSON request a
line, one JSON reply a line, in a process the parent kills when a
reply is late (Q84). These hold the worker's own loop in process and
every way the parent's side reads a worker that misbehaves: it does
not start, it dies between calls, it answers with something that is
not a reply. Each of those is a timeout or a bad pattern to the
query, never an exception, and a broken worker is dropped so the
next call starts a fresh one."""

import io
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.ops import queries as Q  # noqa: E402


def _run_worker(*requests):
    """worker_main over the given request lines; the reply lines."""
    stdin = io.TextIOWrapper(io.BytesIO(b"".join(requests)))
    out = io.BytesIO()
    stdout = io.TextIOWrapper(out)
    with mock.patch.object(sys, "stdin", stdin), \
            mock.patch.object(sys, "stdout", stdout):
        rc = Q.worker_main()
        stdout.flush()
    return rc, [json.loads(x) for x in out.getvalue().splitlines()]


def _req(**kw):
    return (json.dumps(kw) + "\n").encode("utf-8")


class WorkerLoopTest(unittest.TestCase):
    """worker_main, in this process."""

    def test_end_of_input_ends_the_loop(self):
        rc, replies = _run_worker()
        self.assertEqual(0, rc)
        self.assertEqual([], replies)

    def test_matches_in_order_within_the_limit(self):
        _, replies = _run_worker(_req(pattern="ERR", lines=[
            "ok", "ERR one", "ERR two", "fine"], limit=5))
        self.assertEqual([{"matches": ["ERR one", "ERR two"],
                           "truncated": False}], replies)

    def test_a_match_past_the_limit_truncates(self):
        _, replies = _run_worker(_req(pattern="x", lines=[
            "x1", "x2", "x3"], limit=2))
        self.assertEqual([{"matches": ["x1", "x2"], "truncated": True}],
                         replies)

    def test_a_line_that_is_not_text_is_skipped(self):
        _, replies = _run_worker(_req(pattern="a", lines=[
            "a", 7, None, ["a"], "ba"], limit=9))
        self.assertEqual(["a", "ba"], replies[0]["matches"])

    def test_bad_requests_are_refused_and_the_loop_goes_on(self):
        _, replies = _run_worker(
            b"not json\n",
            b"[1, 2]\n",
            _req(pattern=5, lines=[]),
            _req(pattern="a", lines="a"),
            _req(pattern="a", lines=[], limit="many"),
            _req(pattern="(", lines=["("]),
            b"\xff\xfe\n",
            _req(pattern="b", lines=["b"], limit=1))
        self.assertEqual([{"rejected": "bad_pattern"}] * 7, replies[:7])
        self.assertEqual({"matches": ["b"], "truncated": False}, replies[7])


class _FakeProc:
    """A worker as the parent sees it: a pipe in, a line out."""

    def __init__(self, reply=b"", alive=True, write_error=None):
        self.stdin = mock.Mock()
        if write_error is not None:
            self.stdin.write.side_effect = write_error
        self.stdout = io.BytesIO(reply)
        self.stderr = None
        self.pid = 4242
        self._alive = alive
        self.killed = False

    def poll(self):
        return None if self._alive else 1

    def kill(self):
        self.killed = True
        self._alive = False

    def wait(self, timeout=None):
        return 0


class GrepMatchesTest(unittest.TestCase):
    """grep_matches against a worker that misbehaves."""

    def setUp(self):
        self._saved = Q._worker
        Q._worker = None
        self.addCleanup(setattr, Q, "_worker", self._saved)
        # The stop path kills by process group on POSIX; a fake has none.
        killpg = mock.patch.object(Q.os, "killpg", create=True)
        killpg.start()
        self.addCleanup(killpg.stop)

    def _grep(self, *procs):
        starts = mock.patch.object(Q, "_start_worker", side_effect=list(procs))
        with starts as started:
            got = Q.grep_matches("x", ["x"], 5, deadline=2)
        return got, started.call_count

    def test_a_good_reply_is_the_matches(self):
        proc = _FakeProc(b'{"matches": ["x", 3, "xx"], "truncated": 1}\n')
        got, _ = self._grep(proc)
        self.assertEqual(("ok", ["x", "xx"], True), got)
        self.assertIs(proc, Q._worker, "a good worker is kept for the next call")

    def test_a_refusal_is_a_bad_pattern(self):
        got, _ = self._grep(_FakeProc(b'{"rejected": "bad_pattern"}\n'))
        self.assertEqual(("bad_pattern",), got)

    def test_a_reply_that_is_not_json_drops_the_worker(self):
        got, _ = self._grep(_FakeProc(b"garbage\n"))
        self.assertEqual(("timeout",), got)
        self.assertIsNone(Q._worker)

    def test_a_reply_that_is_not_utf8_drops_the_worker(self):
        got, _ = self._grep(_FakeProc(b"\xff\xfe\n"))
        self.assertEqual(("timeout",), got)
        self.assertIsNone(Q._worker)

    def test_a_reply_that_is_not_an_object_is_a_timeout(self):
        got, _ = self._grep(_FakeProc(b"[1, 2]\n"))
        self.assertEqual(("timeout",), got)

    def test_matches_that_are_not_a_list_are_a_timeout(self):
        got, _ = self._grep(_FakeProc(b'{"matches": "x"}\n'))
        self.assertEqual(("timeout",), got)

    def test_a_worker_that_died_with_nothing_said_is_a_timeout(self):
        proc = _FakeProc(b"", alive=False)
        got, _ = self._grep(proc, proc)
        self.assertEqual(("timeout",), got)
        self.assertIsNone(Q._worker)

    def test_a_worker_that_cannot_start_is_a_timeout(self):
        with mock.patch.object(Q, "_start_worker",
                               side_effect=OSError("no exec")), \
                mock.patch.object(Q._runner(), "log") as log:
            got = Q.grep_matches("x", ["x"], 5, deadline=2)
        self.assertEqual(("timeout",), got)
        self.assertIsNone(Q._worker)
        self.assertIn("did not start", log.call_args[0][0])

    def test_a_broken_pipe_starts_a_fresh_worker_once(self):
        dead = _FakeProc(write_error=BrokenPipeError())
        fresh = _FakeProc(b'{"matches": ["x"], "truncated": false}\n')
        got, starts = self._grep(dead, fresh)
        self.assertEqual(("ok", ["x"], False), got)
        self.assertEqual(2, starts)
        self.assertIs(fresh, Q._worker)

    def test_a_worker_that_exited_between_calls_is_replaced(self):
        Q._worker = _FakeProc(alive=False)
        fresh = _FakeProc(b'{"matches": [], "truncated": false}\n')
        got, starts = self._grep(fresh)
        self.assertEqual(("ok", [], False), got)
        self.assertEqual(1, starts)

    def test_no_deadline_given_is_the_module_deadline(self):
        proc = _FakeProc()
        with mock.patch.object(Q, "_read_line", return_value=None) as rl, \
                mock.patch.object(Q, "_start_worker", return_value=proc):
            Q.grep_matches("x", ["x"], 5)
        self.assertEqual(Q._GREP_DEADLINE, rl.call_args[0][1])

    def test_a_late_reply_is_a_timeout(self):
        proc = _FakeProc(b'{"matches": []}\n')
        with mock.patch.object(Q, "_read_line", return_value=None), \
                mock.patch.object(Q, "_start_worker", return_value=proc):
            got = Q.grep_matches("x", ["x"], 5, deadline=0)
        self.assertEqual(("timeout",), got)
        self.assertIsNone(Q._worker)


class StopWorkerTest(unittest.TestCase):

    def test_none_is_nothing_to_stop(self):
        Q._stop_worker(None)

    def test_a_worker_already_gone_only_has_its_pipes_closed(self):
        proc = mock.Mock()
        proc.poll.return_value = 0
        Q._stop_worker(proc)
        proc.kill.assert_not_called()
        proc.stdin.close.assert_called_once()

    def test_kill_races_and_close_errors_are_swallowed(self):
        proc = mock.Mock()
        proc.poll.return_value = None
        proc.pid = 1
        proc.kill.side_effect = ProcessLookupError()
        proc.wait.side_effect = subprocess.TimeoutExpired("w", 2)
        proc.stdin.close.side_effect = OSError()
        proc.stdout.close.side_effect = ValueError()
        proc.stderr = None
        with mock.patch.object(Q.os, "killpg", create=True,
                               side_effect=ProcessLookupError()):
            Q._stop_worker(proc)
        proc.stdout.close.assert_called_once()

    def test_off_posix_the_worker_itself_is_killed(self):
        proc = mock.Mock()
        proc.poll.return_value = None
        with mock.patch.object(Q.os, "name", "nt"):
            Q._stop_worker(proc)
        proc.kill.assert_called_once()

    def test_drop_worker_clears_and_stops(self):
        saved = Q._worker
        self.addCleanup(setattr, Q, "_worker", saved)
        Q._worker = proc = mock.Mock()
        with mock.patch.object(Q, "_stop_worker") as stop:
            Q._drop_worker()
        self.assertIsNone(Q._worker)
        stop.assert_called_once_with(proc)


class StartWorkerTest(unittest.TestCase):

    def test_a_source_tree_runs_the_module(self):
        with mock.patch.object(sys, "frozen", False, create=True):
            self.assertEqual([sys.executable, "-m", "runner.ops.queries"],
                             Q._query_worker_argv())

    def test_a_frozen_exe_reenters_itself(self):
        with mock.patch.object(sys, "frozen", True, create=True):
            self.assertEqual([sys.executable, "--query-worker"],
                             Q._query_worker_argv())

    def test_the_child_runs_the_real_code_from_this_tree(self):
        env = {"MUTANT_UNDER_TEST": "m1", "PYTHONPATH": "/elsewhere"}
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(Q.subprocess, "Popen") as popen:
            Q._start_worker()
        child_env = popen.call_args.kwargs["env"]
        self.assertNotIn("MUTANT_UNDER_TEST", child_env)
        parts = child_env["PYTHONPATH"].split(os.pathsep)
        self.assertEqual(ROOT, parts[0])
        self.assertIn("/elsewhere", parts)
        self.assertIs(subprocess.PIPE, popen.call_args.kwargs["stdin"])

    def test_the_tree_is_not_added_twice(self):
        with mock.patch.dict(os.environ, {"PYTHONPATH": ROOT}), \
                mock.patch.object(Q.subprocess, "Popen") as popen:
            Q._start_worker()
        self.assertEqual(ROOT, popen.call_args.kwargs["env"]["PYTHONPATH"])

    def test_a_real_worker_round_trip(self):
        saved = Q._worker
        Q._worker = None
        try:
            got = Q.grep_matches("^b", ["a", "bb", "cb"], 5, deadline=30)
        finally:
            Q._drop_worker()
            Q._worker = saved
        self.assertEqual(("ok", ["bb"], False), got)


if __name__ == "__main__":
    unittest.main()
