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

    def _send_new(self, args):
        argv = ["send_job.py", "new", "--kind", "ping", "--job-id", "jq-1",
                "--secret", SECRET, "--to-queue", URL]
        with mock.patch.object(sys, "argv", argv):
            return send_job.main()


if __name__ == "__main__":
    unittest.main()
