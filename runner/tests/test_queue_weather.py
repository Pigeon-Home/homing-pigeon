# Agent-Stamp: 90000998-709f-46f5-b2bc-2c3c5cf8dc6c
"""The sender rides out the hosted queue's weather (questions.md Q105).

A read cut short or a dropped connection is retried a bounded number
of times; a read that still cannot finish is one plain line and exit
2, never a traceback. A post whose connection drops is retried with
the same envelope, and the Worker's duplicate answer for a job it
already holds reads as queued. An HTTP status is an answer, never
retried, and an error that is not weather is not swallowed.
"""
import argparse
import hashlib
import http.client
import io
import json
import os
import sys
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.cloud import send_job  # noqa: E402
from runner.tests.test_send_job_queue_edges import (  # noqa: E402
    SECRET, URL, _Opener, _args)


def _cut():
    return http.client.IncompleteRead(b"x" * 771, 2621 - 771)


def _drop():
    return http.client.RemoteDisconnected(
        "Remote end closed connection without response")


class _Base(unittest.TestCase):
    def setUp(self):
        self.slept = []
        patch = mock.patch.object(send_job, "_queue_sleep",
                                  self.slept.append)
        patch.start()
        self.addCleanup(patch.stop)
        env = mock.patch.dict(os.environ, {"HP_SI_TOKEN": "t0k"})
        env.start()
        self.addCleanup(env.stop)

    def run_cmd(self, cmd, opener, **kw):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = cmd(_args(**kw), opener=opener)
        return rc, out.getvalue(), err.getvalue()


class TransientTest(unittest.TestCase):
    def test_weather_and_answers(self):
        self.assertTrue(send_job._transient(_cut()))
        self.assertTrue(send_job._transient(_drop()))
        self.assertTrue(send_job._transient(ConnectionResetError()))
        self.assertTrue(send_job._transient(TimeoutError()))
        self.assertTrue(send_job._transient(
            urllib.error.URLError(ConnectionRefusedError())))
        self.assertFalse(send_job._transient(urllib.error.HTTPError(
            URL, 503, "busy", {}, None)))
        self.assertFalse(send_job._transient(
            urllib.error.URLError("name does not resolve")))
        self.assertFalse(send_job._transient(ValueError("bad")))


class ReadTest(_Base):
    def test_a_read_cut_short_is_read_again(self):
        opener = _Opener(_cut(), (204, ""))
        rc, out, err = self.run_cmd(send_job.cmd_results, opener)
        self.assertEqual(rc, 0)
        self.assertEqual(len(opener.requests), 2)
        self.assertEqual(self.slept, [send_job._QUEUE_BACKOFF[0]])
        self.assertIn("no results waiting", err)

    def test_a_read_that_never_finishes_is_one_plain_line(self):
        attempts = len(send_job._QUEUE_BACKOFF) + 1
        opener = _Opener(*[_cut() for _ in range(attempts)])
        rc, out, err = self.run_cmd(send_job.cmd_results, opener)
        self.assertEqual(rc, 2)
        self.assertEqual(len(opener.requests), attempts)
        self.assertEqual(out, "")
        self.assertNotIn("Traceback", err)
        self.assertIn("could not reach the queue (IncompleteRead", err)

    def test_a_200_without_a_list_is_unknown_not_empty(self):
        # The Worker's empty answer is a 204; a 200 always carries the
        # list. A body without one is exit 2, never "no results".
        for body in ("{}", '{"results": null}', '{"results": "x"}',
                     '{"results": {}}', "[]", "null"):
            rc, out, err = self.run_cmd(send_job.cmd_results,
                                        _Opener((200, body)))
            self.assertEqual(rc, 2, body)
            self.assertEqual(out, "", body)
            self.assertNotIn("no results waiting", err, body)
            self.assertIn("not a results list", err, body)
        for body in ("{}", '{"dead": null}', '{"dead": 3}'):
            rc, out, err = self.run_cmd(send_job.cmd_dlq,
                                        _Opener((200, body)), drop=None,
                                        requeue=None)
            self.assertEqual(rc, 2, body)
            self.assertIn("not a dead-letter list", err, body)

    def test_a_cut_results_list_is_read_through(self):
        opener = _Opener(
            (200, json.dumps({"results": [{"id": "a", "envelope": "nope"}],
                              "more": True})),
            (200, json.dumps({"results": [{"id": "b", "envelope": "nope"}]})))
        rc, out, err = self.run_cmd(send_job.cmd_results, opener)
        self.assertEqual(rc, 1, err)
        self.assertEqual([json.loads(line)["id"]
                          for line in out.splitlines()], ["a", "b"])
        self.assertTrue(all(json.loads(line)["ok"] is False
                            for line in out.splitlines()))
        self.assertIn("after=a", opener.requests[1].full_url)

    def test_a_results_page_that_repeats_is_refused(self):
        page = json.dumps({"results": [{"id": "a", "envelope": "nope"}],
                           "more": True})
        opener = _Opener((200, page), (200, page))
        rc, out, err = self.run_cmd(send_job.cmd_results, opener)
        self.assertEqual(rc, 2)
        self.assertIn("did not advance", err)
        self.assertEqual(json.loads(out)["id"], "a")

    def test_the_dead_letter_list_rides_it_out_too(self):
        opener = _Opener(_drop(), (200, json.dumps({"dead": [{"id": "j"}]})))
        rc, out, err = self.run_cmd(send_job.cmd_dlq, opener, drop=None,
                                    requeue=None)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), {"id": "j"})

    def test_a_cut_dead_letter_list_is_read_through(self):
        opener = _Opener(
            (200, json.dumps({"dead": [{"id": "a"}, {"id": "b"}],
                              "more": True})),
            (200, json.dumps({"dead": [{"id": "c"}]})))
        rc, out, err = self.run_cmd(send_job.cmd_dlq, opener, drop=None,
                                    requeue=None)
        self.assertEqual(rc, 0, err)
        self.assertEqual([json.loads(line)["id"]
                          for line in out.splitlines()], ["a", "b", "c"])
        self.assertIn("after=b", opener.requests[1].full_url)
        self.assertEqual(err, "")

    def test_a_dead_letter_page_that_repeats_is_refused(self):
        page = json.dumps({"dead": [{"id": "a"}], "more": True})
        opener = _Opener((200, page), (200, page))
        rc, out, err = self.run_cmd(send_job.cmd_dlq, opener, drop=None,
                                    requeue=None)
        self.assertEqual(rc, 2)
        self.assertIn("did not advance", err)
        self.assertEqual(json.loads(out)["id"], "a")

    def test_an_ack_that_cannot_land_leaves_the_result_waiting(self):
        from runner.wire import jobcrypto
        body = jobcrypto.encrypt_body(
            send_job.sign_payload({"v": 1, "type": "result", "job_id": "j1",
                                   "exit_code": 0}, SECRET),
            SECRET, job_id="j1", key_id="", sign=send_job.sign_payload)
        envelope = "[HOMING-PIGEON] result j1\n\n" + body
        attempts = len(send_job._QUEUE_BACKOFF) + 1
        opener = _Opener((200, json.dumps({"results": [
            {"id": "r1", "envelope": envelope}]})),
            *[_drop() for _ in range(attempts)])
        rc, out, err = self.run_cmd(send_job.cmd_results, opener, ack=True)
        self.assertEqual(rc, 0)
        line = json.loads(out)
        self.assertTrue(line["ok"])
        self.assertFalse(line["acked"])

    def test_an_http_status_is_never_retried(self):
        opener = _Opener(urllib.error.HTTPError(URL, 503, "busy", {},
                                                io.BytesIO(b"later")))
        rc, out, err = self.run_cmd(send_job.cmd_results, opener)
        self.assertEqual(rc, 2)
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(self.slept, [])

    def test_an_error_that_is_not_weather_is_not_swallowed(self):
        opener = _Opener(ValueError("a bug in the opener"))
        with self.assertRaises(ValueError):
            self.run_cmd(send_job.cmd_results, opener)


class PostTest(_Base):
    def test_a_dropped_post_goes_again_with_the_same_envelope(self):
        opener = _Opener(_drop(), (200, json.dumps(
            {"id": "j9", "duplicate": True})))
        status, text = send_job.post_to_queue(URL, "[HOMING-PIGEON] job j9"
                                              "\n\nbody\n", opener=opener)
        self.assertEqual(status, 200)
        self.assertEqual(len(opener.requests), 2)
        self.assertEqual(opener.requests[0].data, opener.requests[1].data)

    def test_a_post_that_never_lands_raises_for_the_caller(self):
        attempts = len(send_job._QUEUE_BACKOFF) + 1
        opener = _Opener(*[_drop() for _ in range(attempts)])
        with self.assertRaises(send_job.QueueUnreachable):
            send_job.post_to_queue(URL, "x", opener=opener)

    def test_new_names_the_job_and_how_to_resend_it(self):
        args = argparse.Namespace(to_queue=URL, queue_token_env=None)
        with mock.patch.object(send_job, "post_to_queue",
                               side_effect=send_job.QueueUnreachable(
                                   "RemoteDisconnected: gone")):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = self._send_new(args)
        self.assertEqual(rc, 2)
        self.assertIn("may or may not be queued", err.getvalue())
        self.assertIn("--job-id jq-1", err.getvalue())

    def test_new_says_a_duplicate_was_already_queued(self):
        args = argparse.Namespace(to_queue=URL, queue_token_env=None)
        with mock.patch.object(send_job, "post_to_queue", return_value=(
                200, json.dumps({"id": "jq-1", "duplicate": True}))):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = self._send_new(args)
        self.assertEqual(rc, 0)
        self.assertIn("already queued", err.getvalue())

    def test_a_different_envelope_for_a_live_id_is_not_queued(self):
        # 200 used to mean success. The first envelope stays, so a
        # second script under the same id never ran, and the command
        # still exited 0.
        args = argparse.Namespace(to_queue=URL, queue_token_env=None)
        with mock.patch.object(send_job, "post_to_queue", return_value=(
                200, json.dumps({"id": "jq-1", "duplicate": True,
                                 "sha256": "0" * 64}))):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = self._send_new(args)
        self.assertEqual(rc, 1)
        self.assertIn("different envelope", err.getvalue())

    def test_the_same_envelope_sent_again_is_already_queued(self):
        args = argparse.Namespace(to_queue=URL, queue_token_env=None)
        sent = {}

        def answer(url, envelope, token_env=None, opener=None):
            sent["envelope"] = envelope
            digest = hashlib.sha256(envelope.encode("utf-8")).hexdigest()
            return 200, json.dumps({"id": "jq-1", "duplicate": True,
                                    "sha256": digest})

        with mock.patch.object(send_job, "post_to_queue", side_effect=answer):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = self._send_new(args)
        self.assertEqual(rc, 0)
        self.assertIn("already queued", err.getvalue())
        self.assertTrue(sent["envelope"].startswith(
            "[HOMING-PIGEON] job jq-1\n"))

    def _send_new(self, args):
        argv = ["send_job.py", "new", "--kind", "ping", "--job-id", "jq-1",
                "--secret", SECRET, "--to-queue", URL]
        with mock.patch.object(sys, "argv", argv):
            return send_job.main()


import socket  # noqa: E402


class _Resp2:
    """A response whose read can be scripted to blow up."""

    def __init__(self, status=200, body=b"", read_exc=None):
        self.status = status
        self._body = body
        self._read_exc = read_exc

    def read(self):
        if self._read_exc is not None:
            raise self._read_exc
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _ScriptedOpener:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []
        self.timeouts = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        self.timeouts.append(timeout)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


class QueueWeatherShotgunTest(_Base):
    """The shotgun family for queue item 50, Q105: the queue
    client broke on a dropped connection and a cut-short read
    (fixed c4df30c7, 27-Oct-2026). The fix put every queue call
    through one sender that retries IncompleteRead,
    RemoteDisconnected, a reset and a timeout twice (1 s, 3 s)
    and never an HTTP status; a read that still cannot finish is
    one plain line and exit 2, a dropped post goes again with
    the same envelope and the Worker's duplicate answer reads as
    queued, and an ack that cannot land leaves the result
    waiting. This family scattershots everything around that
    failure: every transient exception shape and every
    non-transient lookalike, failures at the call and at the
    read, the backoff sequence itself, and each door the sender
    serves (post, results, dead-letter, ack, new). The fix's own
    tests live in this file, so the family lives here too. One
    regression test was never going to be enough for a bug that
    took days of CPU to find.

    Per-field enumeration: the sender's surface is the request
    (pinned as the same object, resent byte-for-byte, with the
    same 30-second timeout), the response status and body (a
    status is an answer, never retried; a body decodes with
    replacement), the exception (sorted by _transient, field by
    field: the class, and for URLError its reason), the backoff
    table, and each command's exit line. Bookends and run
    lengths, in the form this surface takes them: failure runs
    of 1, 2 and 3 (success on the first, second and third try,
    and no fourth), the odd failure at the front, the middle
    and the back of a call sequence, and text carried through
    the retry bookended with every shape the existing suites
    pin (the envelope is asserted byte-identical across tries).

    Proof of work. The unit tests are the 50 methods of this
    class: 34 hand-written seams plus 16 generated _transient
    classification tests. The fuzzing was executed, not just
    the tests written: runner/tools/de_dust_corpus.py grow
    --target channels --rounds 400 --seed 20261151 against the
    banked channels corpus (11 entries). Result: 400 rounds,
    0 crashes, 0 slow, arcs unchanged at 142, slowest try
    953 ms; the dropped-connection shape did not recur. The
    grow's bookkeeping writes were reverted and are not banked
    (banking is the rigs' hourly job). None of this is exotic:
    it is combinatorics -- systematically trying the
    combinations a hand-written list would never reach, then
    pinning each answer as a test."""

    ATTEMPTS = len(send_job._QUEUE_BACKOFF) + 1

    def _retry(self, *answers):
        opener = _ScriptedOpener(*answers)
        return opener, send_job._send_with_retry(opener, "REQ")

    # -- the one sender, seam by seam --

    def test_first_try_success_sleeps_never(self):
        opener, got = self._retry(_Resp2(200, b"ok"))
        self.assertEqual(got, (200, "ok"))
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(self.slept, [])

    def test_drop_then_success_sleeps_once(self):
        opener, got = self._retry(_drop(), _Resp2(200, b"ok"))
        self.assertEqual(got, (200, "ok"))
        self.assertEqual(self.slept, [1.0])

    def test_cut_then_drop_then_success_sleeps_twice(self):
        opener, got = self._retry(_cut(), _drop(), _Resp2(201, b"made"))
        self.assertEqual(got, (201, "made"))
        self.assertEqual(self.slept, [1.0, 3.0])
        self.assertEqual(len(opener.requests), 3)

    def test_every_attempt_dropping_raises_unreachable(self):
        opener = _ScriptedOpener(*[_drop() for _ in range(self.ATTEMPTS)])
        with self.assertRaises(send_job.QueueUnreachable) as ctx:
            send_job._send_with_retry(opener, "REQ")
        self.assertIn("RemoteDisconnected", str(ctx.exception))
        self.assertEqual(len(opener.requests), self.ATTEMPTS)
        self.assertEqual(self.slept, [1.0, 3.0])

    def test_unreachable_message_is_cut_at_200(self):
        opener = _ScriptedOpener(
            *[http.client.RemoteDisconnected("x" * 500)
              for _ in range(self.ATTEMPTS)])
        with self.assertRaises(send_job.QueueUnreachable) as ctx:
            send_job._send_with_retry(opener, "REQ")
        self.assertLessEqual(len(str(ctx.exception)), 200)

    def test_an_http_status_is_returned_never_retried(self):
        err = urllib.error.HTTPError(URL, 500, "err", {},
                                     io.BytesIO(b"later"))
        opener, got = self._retry(err)
        self.assertEqual(got, (500, "later"))
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(self.slept, [])

    def test_an_http_error_with_an_unreadable_body_reads_empty(self):
        class Blows(io.BytesIO):
            def read(self, *a):
                raise OSError("gone")
        err = urllib.error.HTTPError(URL, 503, "err", {}, Blows(b"x"))
        _opener, got = self._retry(err)
        self.assertEqual(got, (503, ""))

    def test_a_non_transient_error_raises_at_once(self):
        opener = _ScriptedOpener(RuntimeError("a bug"))
        with self.assertRaises(RuntimeError):
            send_job._send_with_retry(opener, "REQ")
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(self.slept, [])

    def test_a_read_cut_short_inside_the_response_is_retried(self):
        opener, got = self._retry(
            _Resp2(200, read_exc=_cut()), _Resp2(200, b"whole"))
        self.assertEqual(got, (200, "whole"))
        self.assertEqual(self.slept, [1.0])

    def test_a_read_dropped_inside_the_response_is_retried(self):
        opener, got = self._retry(
            _Resp2(200, read_exc=_drop()), _Resp2(200, b"whole"))
        self.assertEqual(got, (200, "whole"))

    def test_a_body_that_is_not_utf8_decodes_with_replacement(self):
        _opener, got = self._retry(_Resp2(200, b"\xff\xfe ok"))
        self.assertEqual(got[0], 200)
        self.assertIn("\ufffd", got[1])
        self.assertTrue(got[1].endswith(" ok"))

    def test_the_backoff_table_and_attempt_count(self):
        self.assertEqual(send_job._QUEUE_BACKOFF, (1.0, 3.0))
        self.assertEqual(self.ATTEMPTS, 3)

    def test_the_same_request_object_and_timeout_go_again(self):
        opener, _got = self._retry(_drop(), _drop(), _Resp2(200, b"ok"))
        self.assertTrue(all(r is opener.requests[0]
                            for r in opener.requests))
        self.assertEqual(opener.timeouts, [30, 30, 30])

    # -- post and the generic queue call --

    def test_post_cut_then_duplicate_answer_is_returned(self):
        opener = _Opener(_cut(), (200, json.dumps(
            {"id": "j9", "duplicate": True})))
        status, text = send_job.post_to_queue(URL, "env\n", opener=opener)
        self.assertEqual(status, 200)
        self.assertIn('"duplicate": true', text)
        self.assertEqual(opener.requests[0].data,
                         opener.requests[1].data)
        self.assertEqual(opener.requests[0].headers.get("Authorization"),
                         "Bearer t0k")

    def test_post_every_drop_raises_unreachable(self):
        opener = _Opener(*[_drop() for _ in range(self.ATTEMPTS)])
        with self.assertRaises(send_job.QueueUnreachable):
            send_job.post_to_queue(URL, "env\n", opener=opener)
        self.assertEqual(self.slept, [1.0, 3.0])

    def test_post_http_status_comes_back_once(self):
        opener = _Opener(urllib.error.HTTPError(
            URL, 503, "busy", {}, io.BytesIO(b"later")))
        status, text = send_job.post_to_queue(URL, "env\n", opener=opener)
        self.assertEqual((status, text), (503, "later"))
        self.assertEqual(len(opener.requests), 1)

    def test_queue_call_rides_a_reset(self):
        opener = _Opener(ConnectionResetError("rst"), (200, "{}"))
        got = send_job._queue_call(URL, "GET", "/results",
                                   None, opener)
        self.assertEqual(got, (200, "{}"))
        self.assertEqual(self.slept, [1.0])

    def test_queue_call_every_timeout_raises_unreachable(self):
        opener = _Opener(*[TimeoutError("slow")
                           for _ in range(self.ATTEMPTS)])
        with self.assertRaises(send_job.QueueUnreachable):
            send_job._queue_call(URL, "GET", "/results", None, opener)

    def test_queue_call_404_is_an_answer(self):
        opener = _Opener(urllib.error.HTTPError(
            URL, 404, "no", {}, io.BytesIO(b"none")))
        got = send_job._queue_call(URL, "POST", "/results/x/ack",
                                   None, opener)
        self.assertEqual(got, (404, "none"))
        self.assertEqual(len(opener.requests), 1)

    # -- the commands over the sender --

    def test_results_drop_then_empty_is_a_clean_read(self):
        rc, out, err = self.run_cmd(send_job.cmd_results,
                                    _Opener(_drop(), (204, "")))
        self.assertEqual(rc, 0)
        self.assertEqual(self.slept, [1.0])
        self.assertIn("no results waiting", err)

    def test_results_cut_forever_is_one_plain_line(self):
        opener = _Opener(*[_cut() for _ in range(self.ATTEMPTS)])
        rc, out, err = self.run_cmd(send_job.cmd_results, opener)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertNotIn("Traceback", err)

    def test_dlq_drop_then_a_row_reads(self):
        opener = _Opener(_drop(), (200, json.dumps({"dead": [{"id": "j"}]})))
        rc, out, err = self.run_cmd(send_job.cmd_dlq, opener,
                                    drop=None, requeue=None)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), {"id": "j"})

    def test_dlq_cut_forever_is_exit_2(self):
        opener = _Opener(*[_cut() for _ in range(self.ATTEMPTS)])
        rc, out, err = self.run_cmd(send_job.cmd_dlq, opener,
                                    drop=None, requeue=None)
        self.assertEqual(rc, 2)
        self.assertIn("could not reach the queue", err)

    def _result_opener(self, *ack_answers):
        from runner.wire import jobcrypto
        body = jobcrypto.encrypt_body(
            send_job.sign_payload({"v": 1, "type": "result",
                                   "job_id": "j1", "exit_code": 0},
                                  SECRET),
            SECRET, job_id="j1", key_id="", sign=send_job.sign_payload)
        envelope = "[HOMING-PIGEON] result j1\n\n" + body
        return _Opener((200, json.dumps(
            {"results": [{"id": "r1", "envelope": envelope}]})),
            *ack_answers)

    def test_an_ack_reset_forever_leaves_the_result_unacked(self):
        opener = self._result_opener(
            *[ConnectionResetError("rst") for _ in range(self.ATTEMPTS)])
        rc, out, err = self.run_cmd(send_job.cmd_results, opener, ack=True)
        self.assertEqual(rc, 0)
        line = json.loads(out)
        self.assertTrue(line["ok"])
        self.assertFalse(line["acked"])
        self.assertEqual(self.slept, [1.0, 3.0])

    def test_an_ack_refused_by_status_is_not_acked_and_not_retried(self):
        opener = self._result_opener(urllib.error.HTTPError(
            URL, 500, "err", {}, io.BytesIO(b"no")))
        rc, out, err = self.run_cmd(send_job.cmd_results, opener, ack=True)
        self.assertEqual(rc, 0)
        self.assertFalse(json.loads(out)["acked"])
        self.assertEqual(len(opener.requests), 2)
        self.assertEqual(self.slept, [])

    def test_an_ack_that_lands_on_the_second_try_acks(self):
        opener = self._result_opener(_drop(), (200, "{}"))
        rc, out, err = self.run_cmd(send_job.cmd_results, opener, ack=True)
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["acked"])
        self.assertEqual(self.slept, [1.0])

    def test_a_runtime_error_from_the_opener_propagates(self):
        opener = _Opener(RuntimeError("a bug in the opener"))
        with self.assertRaises(RuntimeError):
            self.run_cmd(send_job.cmd_results, opener)

    def test_the_plain_wrapper_keeps_the_command_name(self):
        self.assertEqual(send_job.cmd_results.__name__, "cmd_results")
        self.assertEqual(send_job.cmd_dlq.__name__, "cmd_dlq")

    # -- cmd_new over a mocked post --

    def _send_new(self, post):
        args = argparse.Namespace(to_queue=URL, queue_token_env=None)
        argv = ["send_job.py", "new", "--kind", "ping",
                "--job-id", "jq-50", "--secret", SECRET,
                "--to-queue", URL]
        with mock.patch.object(send_job, "post_to_queue", post), \
                mock.patch.object(sys, "argv", argv):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = send_job.main()
        return rc, err.getvalue()

    def test_new_unreachable_names_the_job_and_the_resend(self):
        rc, err = self._send_new(mock.Mock(side_effect=send_job.QueueUnreachable(
            "RemoteDisconnected: gone")))
        self.assertEqual(rc, 2)
        self.assertIn("may or may not be queued", err)
        self.assertIn("--job-id jq-50", err)
        self.assertNotIn("Traceback", err)

    def test_new_duplicate_without_a_hash_reads_as_queued(self):
        rc, err = self._send_new(mock.Mock(return_value=(
            202, json.dumps({"id": "jq-50", "duplicate": True}))))
        self.assertEqual(rc, 0)
        self.assertIn("already queued", err)
        self.assertIn("HTTP 202", err)

    def test_new_duplicate_with_our_hash_reads_as_queued(self):
        sent = {}

        def answer(url, envelope, token_env=None, opener=None):
            sent["envelope"] = envelope
            return 200, json.dumps({
                "id": "jq-50", "duplicate": True,
                "sha256": hashlib.sha256(
                    envelope.encode("utf-8")).hexdigest()})
        rc, err = self._send_new(mock.Mock(side_effect=answer))
        self.assertEqual(rc, 0)
        self.assertIn("already queued", err)

    def test_new_duplicate_with_another_hash_is_refused(self):
        rc, err = self._send_new(mock.Mock(return_value=(
            200, json.dumps({"id": "jq-50", "duplicate": True,
                             "sha256": "0" * 64}))))
        self.assertEqual(rc, 1)
        self.assertIn("different envelope", err)

    def test_new_a_refusal_status_is_not_queued(self):
        rc, err = self._send_new(mock.Mock(return_value=(403, "no")))
        self.assertEqual(rc, 1)
        self.assertIn("queue refused", err)

    def test_new_a_non_json_answer_still_reads_as_queued(self):
        rc, err = self._send_new(mock.Mock(return_value=(200, "queued-ish")))
        self.assertEqual(rc, 0)
        self.assertIn("queued job jq-50", err)
        self.assertNotIn("already queued", err)


def _make_transient_test(factory, want):
    def run(self):
        self.assertEqual(send_job._transient(factory()), want)
    return run


# 16 generated classification tests: every weather shape the
# sender rides out, and the lookalikes it must not swallow.
_TRANSIENT_CASES = (
    ("incomplete_read", lambda: _cut(), True),
    ("remote_disconnected", lambda: _drop(), True),
    ("connection_reset", lambda: ConnectionResetError("r"), True),
    ("connection_refused", lambda: ConnectionRefusedError("r"), True),
    ("broken_pipe", lambda: BrokenPipeError("r"), True),
    ("socket_timeout", lambda: socket.timeout("r"), True),
    ("timeout_error", lambda: TimeoutError("r"), True),
    ("urlerror_reset_reason",
     lambda: urllib.error.URLError(ConnectionResetError("r")), True),
    ("urlerror_timeout_reason",
     lambda: urllib.error.URLError(socket.timeout("r")), True),
    ("urlerror_disconnected_reason",
     lambda: urllib.error.URLError(_drop()), True),
    ("http_error", lambda: urllib.error.HTTPError(
        URL, 503, "busy", {}, None), False),
    ("urlerror_text_reason",
     lambda: urllib.error.URLError("name does not resolve"), False),
    ("urlerror_value_reason",
     lambda: urllib.error.URLError(ValueError("x")), False),
    ("value_error", lambda: ValueError("bad"), False),
    ("plain_os_error", lambda: OSError("disk"), False),
    ("runtime_error", lambda: RuntimeError("bug"), False),
)
for _i, (_label, _factory, _want) in enumerate(_TRANSIENT_CASES):
    setattr(QueueWeatherShotgunTest, f"test_transient_{_i:02d}_{_label}",
            _make_transient_test(_factory, _want))
del _i, _label, _factory, _want


if __name__ == "__main__":
    unittest.main()
