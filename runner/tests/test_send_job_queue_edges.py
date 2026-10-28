# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""The sender's queue reader at its edges (runner/cloud/send_job.py):
what `results` does with a queue answer that is not a results list
or with an item that carries no envelope, how it clamps --max, how
one queue call reads an HTTP error whose body cannot be read, and
what `_named_key_in` takes from a body before anything is verified.
The happy paths are in test_transport_queues.py; these are the
branches it does not reach."""

import argparse
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

URL = "https://q.example.test/t/a"
SECRET = "8d3f0a6c1e2b4d5f9a7c3e1b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4b6d8f"


class _Resp:
    def __init__(self, status, text):
        self.status = status
        self._text = text.encode("utf-8")

    def read(self):
        return self._text

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Opener:
    """Answers each call from a list, and keeps the requests."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return _Resp(*a)


def _args(**kw):
    base = dict(from_queue=URL, max=None, queue_token_env=None, ack=False,
                secret=SECRET, key_id=None)
    base.update(kw)
    return argparse.Namespace(**base)


def _results(opener, **kw):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {"HP_SI_TOKEN": "t0k"}), \
            redirect_stdout(out), redirect_stderr(err):
        rc = send_job.cmd_results(_args(**kw), opener=opener)
    lines = [json.loads(x) for x in out.getvalue().splitlines() if x]
    return rc, lines, err.getvalue()


class ResultsEdgesTest(unittest.TestCase):

    def test_an_answer_that_is_not_json_is_a_refused_read(self):
        rc, lines, err = _results(_Opener((200, "<html>")))
        self.assertEqual((2, []), (rc, lines))
        self.assertIn("not a results list", err)

    def test_an_answer_that_is_not_an_object_is_a_refused_read(self):
        rc, _lines, err = _results(_Opener((200, "[1, 2]")))
        self.assertEqual(2, rc)
        self.assertIn("not a results list", err)

    def test_an_item_without_an_envelope_fails_that_item_only(self):
        answer = json.dumps({"results": [
            {"id": "a"}, "not-an-item", {"id": "b", "envelope": 7}]})
        rc, lines, _err = _results(_Opener((200, answer)), ack=True)
        self.assertEqual(1, rc)
        self.assertEqual(3, len(lines))
        self.assertTrue(all(l["ok"] is False for l in lines))
        self.assertTrue(all("no envelope" in l["error"] for l in lines))
        self.assertTrue(all("acked" not in l for l in lines))
        self.assertIsNone(lines[1]["id"])

    def test_max_is_clamped_to_the_queue_range(self):
        for asked, sent in ((None, 20), (0, 20), (-5, 1), (500, 100),
                            ("7", 7)):
            op = _Opener((204, ""))
            _results(op, max=asked)
            self.assertTrue(op.requests[0].full_url.endswith(
                f"/results?max={sent}"), (asked, op.requests[0].full_url))

    def test_another_status_is_a_refused_read(self):
        rc, _lines, err = _results(_Opener((503, "busy")))
        self.assertEqual(2, rc)
        self.assertIn("503", err)


class QueueCallTest(unittest.TestCase):

    def _http_error(self, readable):
        e = urllib.error.HTTPError(URL, 418, "teapot", {}, None)
        if readable:
            e.read = lambda: b"short and stout"
        else:
            def boom():
                raise OSError("gone")
            e.read = boom
        return e

    def test_an_http_error_is_its_status_and_body(self):
        with mock.patch.dict(os.environ, {"HP_SI_TOKEN": "t0k"}):
            got = send_job._queue_call(URL, "GET", "/x",
                                       opener=_Opener(self._http_error(True)))
        self.assertEqual((418, "short and stout"), got)

    def test_an_http_error_whose_body_cannot_be_read_is_empty_text(self):
        with mock.patch.dict(os.environ, {"HP_SI_TOKEN": "t0k"}):
            got = send_job._queue_call(URL, "GET", "/x",
                                       opener=_Opener(self._http_error(False)))
        self.assertEqual((418, ""), got)

    def test_a_post_carries_an_empty_body_and_the_bearer_token(self):
        op = _Opener((204, ""))
        with mock.patch.dict(os.environ, {"HP_OTHER": "s3cr3t"}):
            send_job._queue_call(URL + "/", "POST", "/r/1/ack",
                                 token_env="HP_OTHER", opener=op)
        req = op.requests[0]
        self.assertEqual(URL + "/r/1/ack", req.full_url)
        self.assertEqual(b"", req.data)
        self.assertEqual("Bearer s3cr3t", req.get_header("Authorization"))

    def test_loopback_http_is_allowed_and_other_http_is_not(self):
        op = _Opener((204, ""), (204, ""))
        with mock.patch.dict(os.environ, {"HP_SI_TOKEN": "t0k"}):
            send_job._queue_call("http://127.0.0.1:8787", "GET", "/x", opener=op)
            send_job._queue_call("http://localhost:8787", "GET", "/x", opener=op)
            with self.assertRaises(SystemExit):
                send_job._queue_call("http://q.example.test", "GET", "/x",
                                     opener=op)
            with self.assertRaises(SystemExit):
                send_job._queue_call(None, "GET", "/x", opener=op)
        self.assertEqual(2, len(op.requests))


class NamedKeyInTest(unittest.TestCase):

    def test_the_name_a_signed_body_carries(self):
        body = send_job.sign_payload({"v": 1, "key_id": "k-0011aabb"}, SECRET)
        self.assertEqual("k-0011aabb", send_job._named_key_in(body))

    def test_no_name_or_a_name_that_is_not_text_is_none(self):
        for payload in ({"v": 1}, {"v": 1, "key_id": 5},
                        {"v": 1, "key_id": None}):
            body = send_job.sign_payload(payload, SECRET)
            self.assertIsNone(send_job._named_key_in(body), payload)

    def test_text_that_is_not_a_signed_body_is_none(self):
        for text in ("", "hello", '{"key_id": "x"}',
                     '{"key_id": "x","sig":"' + "z" * 96 + '"}'):
            self.assertIsNone(send_job._named_key_in(text), text)


if __name__ == "__main__":
    unittest.main()
