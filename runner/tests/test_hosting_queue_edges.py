# Agent-Stamp: 70000a51-e296-4b2c-bf5b-ba020e23eb91
"""The hosted queue's edges: what the runner's queues transport, the
SI's `send_job.py results` and `dlq`, and `homing-pigeon-host` do when
the queue or the input is not what the happy path expects.

Every case here is a branch the queue suites did not reach: a queue
that answers something other than JSON, a renewal that raises, a
result with no envelope, a keyring that supplies the secret, a
dead-letter call the queue refuses. No network: a scripted opener
stands in for the Worker.
"""
import io
import json
import os
import secrets
import sys
import tempfile
import types
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.cloud import send_job  # noqa: E402
from runner.hosting import cli as host_cli  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402
from runner.transport_extensions.queues import __main__ as q  # noqa: E402


class _Resp:
    def __init__(self, status, body=b""):
        self.status = status
        self._body = body if isinstance(body, bytes) else body.encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener(*answers):
    """An opener that answers each request with the next (status, body);
    a status >= 400 is raised as HTTPError, as urllib does."""
    script = list(answers)
    seen = []

    def _open(req, timeout=None):
        seen.append((req.get_method(), req.full_url))
        status, body = script.pop(0)
        if status >= 400:
            fp = io.BytesIO(body if isinstance(body, bytes) else body.encode())
            raise urllib.error.HTTPError(req.full_url, status, "x", {}, fp)
        return _Resp(status, body)
    _open.seen = seen
    return _open


class QueueClientEdgesTest(unittest.TestCase):
    def test_pull_refuses_a_non_json_or_failed_answer(self):
        c = q.QueueClient("https://w.example/t/a", "tok",
                          opener=opener((200, b"<html>")))
        with self.assertRaisesRegex(RuntimeError, "not JSON"):
            c.pull(4)
        c = q.QueueClient("https://w.example/t/a", "tok",
                          opener=opener((503, b"later")))
        with self.assertRaisesRegex(RuntimeError, "HTTP 503"):
            c.pull(4)

    def test_pull_keeps_only_well_formed_items(self):
        body = json.dumps({"jobs": [
            "not a dict", {"id": "", "envelope": "x"}, {"id": "j1"},
            {"id": "j2", "envelope": "[HOMING-PIGEON] job j2\n\n{}\n"}]})
        c = q.QueueClient("https://w.example/t/a", "tok",
                          opener=opener((200, body)))
        self.assertEqual([i for i, _ in c.pull(8)], ["j2"])

    def test_an_error_body_that_cannot_be_read_is_empty(self):
        class Broken(io.BytesIO):
            def read(self, *a):
                raise OSError("gone")

        def _open(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 502, "x", {}, Broken())
        c = q.QueueClient("https://w.example/t/a", "tok", opener=_open)
        self.assertEqual(c._request("GET", "/jobs"), (502, b""))

    def test_renew_reports_whether_the_queue_still_holds_the_lease(self):
        c = q.QueueClient("https://w.example/t/a", "tok",
                          opener=opener((204, b""), (404, b"")))
        self.assertTrue(c.renew("j/1"))
        self.assertFalse(c.renew("j1"))


class QueuePipeEdgesTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.channel = os.path.join(self.td.name, "channel")
        ch.dirs(self.channel)

    def tearDown(self):
        self.td.cleanup()

    def test_a_renewal_that_raises_is_logged_and_the_pass_goes_on(self):
        client = mock.Mock()
        client.renew.side_effect = [OSError("down"), True]
        pipe = q.QueuePipe({}, self.channel, client)
        pipe._pending = {"a": "a", "b": "b"}
        logs = []
        with mock.patch.object(ch, "log", lambda m, *a: logs.append(m)):
            pipe.renew_leases()
        self.assertEqual(client.renew.call_count, 2)
        self.assertTrue(any("lease renewal failed" in m for m in logs))

    def test_a_result_body_without_a_final_newline_gets_one(self):
        d = ch.dirs(self.channel)
        ch._atomic_write(os.path.join(d["outbox"], "j1.result.txt"),
                         "[HOMING-PIGEON] result j1\n\n{\"sig\":\"00\"}")
        client = mock.Mock()
        pipe = q.QueuePipe({}, self.channel, client)
        with mock.patch.object(ch, "pending_results",
                               lambda c: [("j1.result.txt",
                                           "[HOMING-PIGEON] result j1",
                                           "{\"sig\":\"00\"}")]):
            pipe.push_results()
        posted = client.post_result.call_args[0][0]
        self.assertTrue(posted.endswith("}\n"))


class QueueMainEdgesTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.channel = os.path.join(self.td.name, "channel")
        self.cfg = os.path.join(self.td.name, "cfg.json")
        for k in ("HOMING_PIGEON_TRANSPORT_CHANNEL",
                  "HOMING_PIGEON_TRANSPORT_CONFIG"):
            os.environ.pop(k, None)

    def tearDown(self):
        self.td.cleanup()

    def _cfg(self, **cfg):
        with open(self.cfg, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)

    def test_no_channel_and_no_token_are_refused(self):
        logs = []
        with mock.patch.object(ch, "log", lambda m, *a: logs.append(m)):
            self.assertEqual(q.main(["queues"]), 2)
            self._cfg(url="https://w.example/t/a")
            self.assertEqual(q.main(["queues", self.channel, self.cfg]), 2)
        self.assertTrue(any("no channel" in m for m in logs))
        self.assertTrue(any("transport_queues.token, or token_env" in m
                            for m in logs))

    def test_a_failed_pass_is_logged_and_the_loop_naps_and_goes_on(self):
        self._cfg(url="https://w.example/t/a", token="tok")
        logs, naps = [], []
        with mock.patch.object(ch, "log", lambda m, *a: logs.append(m)), \
                mock.patch.object(ch, "nap", naps.append), \
                mock.patch.object(q.QueuePipe, "pull_jobs",
                                  side_effect=RuntimeError("boom")):
            rc = q.main(["queues", self.channel, self.cfg],
                        opener=opener(), passes=2)
        self.assertEqual(rc, 0)
        self.assertEqual(sum("pass failed" in m for m in logs), 2)
        self.assertEqual(len(naps), 1)


def _args(**kw):
    base = {"from_queue": "https://w.example/t/a", "queue_token_env": None,
            "max": 20, "ack": False, "secret": None, "key_id": None,
            "keyring": None, "drop": None, "requeue": None}
    base.update(kw)
    return types.SimpleNamespace(**base)


class SendJobQueueEdgesTest(unittest.TestCase):
    def setUp(self):
        os.environ["HP_SI_TOKEN"] = "si"
        self.td = tempfile.TemporaryDirectory()

    def tearDown(self):
        os.environ.pop("HP_SI_TOKEN", None)
        self.td.cleanup()

    def _quiet(self, fn, *a, **k):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = fn(*a, **k)
        return rc, out.getvalue(), err.getvalue()

    def test_a_refused_post_or_read_returns_the_status_and_body(self):
        status, text = send_job.post_to_queue(
            "https://w.example/t/a", "[HOMING-PIGEON] job j\n\n{}\n",
            opener=opener((403, b'{"error":"invalid signature"}')))
        self.assertEqual((status, text), (403, '{"error":"invalid signature"}'))

        class Broken(io.BytesIO):
            def read(self, *a):
                raise OSError("gone")

        def _open(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 502, "x", {}, Broken())
        self.assertEqual(send_job.post_to_queue(
            "https://w.example/t/a", "x\n\ny", opener=_open), (502, ""))
        self.assertEqual(send_job._queue_call(
            "https://w.example/t/a", "GET", "/dlq", opener=_open), (502, ""))

    def test_a_plain_http_queue_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "must be https"):
            send_job._queue_call("http://w.example/t/a", "GET", "/results")

    def test_results_that_are_not_a_list_are_a_refused_read(self):
        rc, _, err = self._quiet(send_job.cmd_results, _args(),
                                 opener=opener((200, b"[]")))
        self.assertEqual(rc, 2)
        self.assertIn("not a results list", err)
        rc, _, err = self._quiet(send_job.cmd_results, _args(),
                                 opener=opener((401, b"si token")))
        self.assertEqual(rc, 2)

    def test_a_result_without_an_envelope_is_reported_not_fatal(self):
        body = json.dumps({"results": [{"id": "r1"}]})
        rc, out, _ = self._quiet(send_job.cmd_results, _args(secret="x"),
                                 opener=opener((200, body)))
        self.assertEqual(rc, 1)
        line = json.loads(out)
        self.assertEqual(line, {"id": "r1", "ok": False,
                                "error": "the result carries no envelope"})

    def test_the_keyring_supplies_the_secret_a_result_names(self):
        secret = secrets.token_hex(32)
        kid = send_job.key_fingerprint(secret)
        ring = os.path.join(self.td.name, "ring.json")
        send_job.keyring_save(ring, {kid: {"secret": secret,
                                           "runner": "r@example.test"}})
        body = send_job.sign_payload(
            {"v": 1, "type": "result", "job_id": "j1", "key_id": kid,
             "exit_code": 0}, secret)
        env = f"[HOMING-PIGEON] result j1\n\n{body}\n"
        answer = json.dumps({"results": [{"id": "j1", "envelope": env}]})
        rc, out, _ = self._quiet(send_job.cmd_results, _args(keyring=ring),
                                 opener=opener((200, answer)))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["payload"]["exit_code"], 0)
        # A body that names no key, with no --secret, cannot be opened.
        bare = send_job.sign_payload({"v": 1, "exit_code": 0}, secret)
        answer = json.dumps({"results": [{
            "id": "j2", "envelope": f"[HOMING-PIGEON] result j2\n\n{bare}\n"}]})
        rc, out, _ = self._quiet(send_job.cmd_results, _args(keyring=ring),
                                 opener=opener((200, answer)))
        self.assertEqual(rc, 1)
        self.assertIn("names no key_id", json.loads(out)["error"])

    def test_a_result_subject_names_its_job(self):
        self.assertEqual(send_job._result_job_id(
            "[HOMING-PIGEON] result j9"), "j9")
        self.assertEqual(send_job._result_job_id(
            "Re: [HOMING-PIGEON] qresult j8"), "j8")
        self.assertIsNone(send_job._result_job_id("[HOMING-PIGEON] job j9"))
        self.assertIsNone(send_job._result_job_id(None))

    def test_dlq_refusals_are_two(self):
        rc, _, _ = self._quiet(send_job.cmd_dlq, _args(),
                               opener=opener((500, b"no")))
        self.assertEqual(rc, 2)
        rc, _, err = self._quiet(send_job.cmd_dlq, _args(),
                                 opener=opener((200, b"[1]")))
        self.assertEqual(rc, 2)
        self.assertIn("not a dead-letter list", err)
        rc, _, _ = self._quiet(send_job.cmd_dlq, _args(requeue="d1"),
                               opener=opener((429, b"quota")))
        self.assertEqual(rc, 2)
        o = opener((204, b""))
        rc, out, _ = self._quiet(send_job.cmd_dlq, _args(drop="a/b"),
                                 opener=o)
        self.assertEqual(rc, 0)
        self.assertTrue(o.seen[0][1].endswith("/dlq/a%2Fb/ack"))


class HostCliEdgesTest(unittest.TestCase):
    def test_an_empty_secret_env_is_refused_before_any_call(self):
        os.environ["HP_TEST_FLY"] = "tok"
        os.environ.pop("HP_TEST_EMPTY_SECRET", None)
        try:
            args = types.SimpleNamespace(
                token_env="HP_TEST_FLY", blob=None, queue=None,
                secret_env="HP_TEST_EMPTY_SECRET")
            with self.assertRaisesRegex(SystemExit, "is empty"):
                host_cli.cmd_up(args, http=object())
        finally:
            os.environ.pop("HP_TEST_FLY", None)

    def test_main_turns_a_value_error_into_exit_two(self):
        with mock.patch.object(host_cli, "cmd_status",
                               side_effect=ValueError("bad blob")):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = host_cli.main(["status"])
        self.assertEqual(rc, 2)
        self.assertIn("bad blob", err.getvalue())


if __name__ == "__main__":
    unittest.main()
