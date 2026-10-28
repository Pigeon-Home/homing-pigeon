"""Project Platinum, cycle 2: the queues transport extension.

Targets from the cycle-1 refreshed table
(`docs/reports/v3.13.21/coverage-gaps.md`):

  logic  transport_extensions/queues/__main__.py:main (5) --
         the refusal with no channel directory, a clean pass,
         and a pass whose pull blows up: the pipe must not die
         on one pass, and a finished run returns 0.
  guard  transport_extensions/queues/__main__.py:
         QueueClient.pull (3) -- a non-200 answer and a
         non-JSON answer are RuntimeErrors naming the failure;
         a 204 is an empty list; from a 200 only well-formed
         (id, envelope) pairs come back.

The client takes its opener as an argument and `main` takes
argv, opener and passes the same way, so every case here drives
the public seams with scripted answers -- no socket is opened.

Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90
"""
import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.error
from unittest import mock

try:
    from hypothesis import given, settings, strategies as st
except ImportError:  # test-only dep: runner/tests/_hypothesis_shim.py
    from runner.tests._hypothesis_shim import given, settings, strategies as st

from runner.transport_extensions.queues import __main__ as q

TOKEN = "tok" + "en-for-platinum"


class _Response:
    def __init__(self, status, body=b""):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def _opener_returning(status, body=b""):
    def open_(req, timeout=None):
        return _Response(status, body)
    return open_


def _opener_raising(exc):
    def open_(req, timeout=None):
        raise exc
    return open_


def _http_error(code, body=b"queue says no", read_fails=False):
    err = urllib.error.HTTPError(
        "http://127.0.0.1:9", code, "scripted", {},
        io.BytesIO(body))
    if read_fails:
        def boom():
            raise OSError("the error body is unreadable")
        err.read = boom
    return err


class PullProperties(unittest.TestCase):
    def _client(self, opener):
        return q.QueueClient("http://127.0.0.1:9/t/test", TOKEN,
                             opener=opener)

    def test_no_jobs_is_an_empty_list(self):
        self.assertEqual(self._client(_opener_returning(204)).pull(8),
                         [])

    @settings(deadline=None)
    @given(items=st.lists(st.dictionaries(
        st.sampled_from(["id", "envelope", "other"]),
        st.one_of(st.none(), st.booleans(), st.integers(),
                  st.text(max_size=10)),
        max_size=3), max_size=5))
    def test_only_well_formed_pairs_come_back(self, items):
        body = json.dumps({"jobs": items}).encode()
        got = self._client(_opener_returning(200, body)).pull(8)
        want = [(it["id"], it["envelope"]) for it in items
                if isinstance(it.get("id"), str) and it.get("id")
                and isinstance(it.get("envelope"), str)]
        self.assertEqual(got, want)

    @settings(deadline=None)
    @given(payload=st.one_of(
        st.binary(max_size=40),
        st.sampled_from([b"[1, 2]", b'"just a string"', b"42",
                         b"null", b'{"jobs": null}',
                         b'{"jobs": "not a list"}'])))
    def test_a_non_job_payload_is_empty_or_a_named_refusal(self,
                                                           payload):
        try:
            got = self._client(_opener_returning(200, payload)).pull(8)
        except RuntimeError as e:
            self.assertIn("not JSON", str(e))
        else:
            self.assertEqual(got, [])

    @settings(deadline=None)
    @given(status=st.integers(min_value=100, max_value=599).filter(
        lambda s: s not in (200, 204)))
    def test_an_error_status_returned_is_a_named_refusal(self, status):
        with self.assertRaises(RuntimeError) as cm:
            self._client(_opener_returning(status, b"nope")).pull(8)
        self.assertIn(f"HTTP {status}", str(cm.exception))

    @settings(deadline=None)
    @given(code=st.sampled_from([400, 401, 404, 500, 503]),
           read_fails=st.booleans())
    def test_an_http_error_is_a_named_refusal(self, code, read_fails):
        err = _http_error(code, read_fails=read_fails)
        with self.assertRaises(RuntimeError) as cm:
            self._client(_opener_raising(err)).pull(8)
        self.assertIn(f"HTTP {code}", str(cm.exception))

    def test_max_jobs_is_coerced_into_the_query(self):
        seen = {}

        def open_(req, timeout=None):
            seen["url"] = req.full_url
            return _Response(204)

        self._client(open_).pull(3.9)
        self.assertTrue(seen["url"].endswith("/jobs?max=3"))


class MainPassTest(unittest.TestCase):
    def _launch(self, opener, passes=1, cfg_extra=None):
        td = tempfile.mkdtemp(prefix="hp-plat-queues-")
        channel = os.path.join(td, "channel")
        os.makedirs(channel)
        cfg = {"url": "http://127.0.0.1:9/t/test",
               "token_env": "HP_PLATINUM_Q_TOKEN"}
        if cfg_extra:
            cfg.update(cfg_extra)
        cfg_path = os.path.join(td, "runtime.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        env = {"HP_PLATINUM_Q_TOKEN": TOKEN}
        with mock.patch.dict(os.environ, env):
            os.environ.pop("HOMING_PIGEON_TRANSPORT_CHANNEL", None)
            os.environ.pop("HOMING_PIGEON_TRANSPORT_CONFIG", None)
            rc = q.main(["queues", channel, cfg_path],
                        opener=opener, passes=passes)
        shutil.rmtree(td, ignore_errors=True)
        return rc

    def test_no_channel_directory_is_a_refusal(self):
        with mock.patch.dict(os.environ, {}):
            os.environ.pop("HOMING_PIGEON_TRANSPORT_CHANNEL", None)
            os.environ.pop("HOMING_PIGEON_TRANSPORT_CONFIG", None)
            self.assertEqual(q.main(["queues"], passes=1), 2)

    def test_a_clean_pass_returns_zero(self):
        self.assertEqual(
            self._launch(_opener_returning(204), passes=2), 0)

    def test_a_blown_pass_does_not_kill_the_pipe(self):
        self.assertEqual(
            self._launch(_opener_raising(
                ConnectionError("the queue is down"))), 0)


class _PipeClient:
    """The queue client as QueuePipe sees it: scripted
    pulls, recorded posts and acks."""

    def __init__(self, pulls=()):
        self.pulls = list(pulls)
        self.posted = []
        self.acked = []

    def pull(self, max_jobs):
        return list(self.pulls)

    def post_result(self, text):
        self.posted.append(text)

    def ack(self, ident):
        self.acked.append(ident)


def _load_pipe():
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(
        here, "..", "transport_extensions", "queues",
        "__main__.py")
    spec = importlib.util.spec_from_file_location(
        "queues_pipe_platinum", os.path.normpath(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class QueuePipeTest(unittest.TestCase):
    """Cycle 6 targets, guard class:
    `transport_extensions/queues/__main__.py` -- pull_jobs
    (168) steps over a queue id this process has already
    seen, delivering nothing twice; push_results (189)
    gives a posted envelope its final newline when the
    stashed body does not end with one.
    """

    def test_a_seen_id_is_not_delivered_twice(self):
        import tempfile
        mod = _load_pipe()
        td = tempfile.mkdtemp(prefix="hp-plat-pipe-")
        try:
            client = _PipeClient(pulls=[("q1", "job text")])
            pipe = mod.QueuePipe({}, td, client)
            pipe._seen.add("q1")
            pipe.pull_jobs()
            inbox = os.path.join(td, "inbox")
            landed = [n for n in os.listdir(inbox)
                      if n.endswith(".job.txt")] \
                if os.path.isdir(inbox) else []
            self.assertEqual(landed, [])
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)

    def test_a_result_without_a_final_newline_gets_one(self):
        import tempfile
        mod = _load_pipe()
        from runner.transport_extensions import channel as ch
        td = tempfile.mkdtemp(prefix="hp-plat-pipe-")
        try:
            dirs = ch.dirs(td)
            body = "the result body"
            with open(os.path.join(dirs["outbox"], "q1.result.txt"),
                      "w", encoding="utf-8") as fh:
                fh.write(ch.envelope("result q1", body))
            client = _PipeClient()
            pipe = mod.QueuePipe({}, td, client)
            pipe._pending["q1"] = "job-1"
            pipe.push_results()
            self.assertEqual(
                client.posted,
                [ch.envelope("result q1", body) + "\n"])
            self.assertEqual(client.acked, ["q1"])
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
