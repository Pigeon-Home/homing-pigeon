"""The hosted-queue pipe's refusal and failure arms, without a server.

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854

test_transport_queues drives the pipe against a loopback Worker. These
are the arms that Worker never takes: an error body that cannot be
read, a pull answer that is not JSON, a jobs list with junk in it, a
lease renewal that raises, a job offered twice, a result with no
final newline, a launch with no channel, and a pass that raises
between two naps. Each is logged or skipped; none ends the pipe.
"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.transport_extensions import channel as ch  # noqa: E402
from runner.transport_extensions.queues import __main__ as q  # noqa: E402


class _Resp:
    def __init__(self, status, body):
        self.status, self._body = status, body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener(status, body):
    return lambda req, timeout=None: _Resp(status, body)


class ClientArmsTest(unittest.TestCase):
    def test_an_error_body_that_cannot_be_read_is_empty(self):
        err = urllib.error.HTTPError("https://q.example.test/jobs", 503,
                                     "down", {}, None)
        err.read = mock.MagicMock(side_effect=OSError("reset"))

        def opener(req, timeout=None):
            raise err
        c = q.QueueClient("https://q.example.test/t/a", "tok", opener=opener)
        self.assertEqual(c._request("GET", "/jobs"), (503, b""))

    def test_a_pull_that_is_not_json_raises_and_junk_items_are_skipped(self):
        c = q.QueueClient("https://q.example.test/t/a", "tok",
                          opener=_opener(200, b"<html>"))
        with self.assertRaises(RuntimeError):
            c.pull(8)
        body = json.dumps({"jobs": ["junk", 7, {"id": "", "envelope": "x"},
                                    {"id": "a", "envelope": 1},
                                    {"id": "b", "envelope": "env"}]})
        c = q.QueueClient("https://q.example.test/t/a", "tok",
                          opener=_opener(200, body.encode()))
        self.assertEqual(c.pull(8), [("b", "env")])


class PipeArmsTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.channel = os.path.join(self.td.name, "channel")
        ch.dirs(self.channel)
        self.client = mock.MagicMock()
        self.pipe = q.QueuePipe({}, self.channel, self.client)
        self.logs = []
        p = mock.patch.object(q.ch, "log",
                              side_effect=lambda m, lvl="INFO":
                              self.logs.append((lvl, m)))
        p.start()
        self.addCleanup(p.stop)

    def test_a_renewal_that_raises_is_logged_and_the_rest_renew(self):
        self.pipe._pending = {"a": "ja", "b": "jb"}
        self.client.renew.side_effect = [RuntimeError("HTTP 502"), True]
        self.pipe.renew_leases()
        self.assertEqual(self.client.renew.call_count, 2)
        self.assertTrue(any("lease renewal failed" in m for _, m in self.logs))

    def test_a_job_offered_again_is_not_delivered_twice(self):
        env = "[HOMING-PIGEON] job j1\n\n{}\n"
        self.client.pull.return_value = [("q1", env)]
        self.pipe.pull_jobs()
        self.pipe.pull_jobs()
        inbox = [n for n in os.listdir(ch.dirs(self.channel)["inbox"])
                 if n.endswith(".job.txt")]
        self.assertEqual(inbox, ["q1.job.txt"])

    def test_a_result_without_a_final_newline_gets_one(self):
        # The file is named for the id in the subject. A different
        # name is left where it is and never posted, which is not
        # this arm.
        ch._atomic_write(os.path.join(ch.dirs(self.channel)["outbox"],
                                      "j1.result.txt"),
                         "[HOMING-PIGEON] result j1\n\n{\"sig\":\"00\"}")
        sent = []
        self.client.post_result.side_effect = lambda t: sent.append(t) or True
        self.pipe.push_results()
        self.assertTrue(sent and sent[0].endswith("}\n"), sent)


class MainArmsTest(unittest.TestCase):
    def test_no_channel_directory_refuses_to_start(self):
        with mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(q.ch, "log") as log:
            os.environ.pop("HOMING_PIGEON_TRANSPORT_CHANNEL", None)
            os.environ.pop("HOMING_PIGEON_TRANSPORT_CONFIG", None)
            self.assertEqual(q.main(["queues"]), 2)
        self.assertIn("no channel directory", log.call_args[0][0])

    def test_a_pass_that_raises_is_logged_and_the_next_pass_runs(self):
        with tempfile.TemporaryDirectory() as td:
            chan = os.path.join(td, "channel")
            ch.dirs(chan)
            cfg = os.path.join(td, "rt.json")
            with open(cfg, "w") as fh:
                json.dump({"url": "https://q.example.test/t/a",
                           "token": "tok"}, fh)
            naps, logs = [], []
            with mock.patch.object(q.ch, "nap", side_effect=naps.append), \
                    mock.patch.object(q.ch, "log",
                                      side_effect=lambda m, lvl="INFO":
                                      logs.append(m)), \
                    mock.patch.object(q.QueuePipe, "pull_jobs",
                                      side_effect=OSError("refused")):
                rc = q.main(["queues", chan, cfg], passes=2)
        self.assertEqual(rc, 0)
        self.assertEqual(len(naps), 1)
        self.assertEqual(sum("pass failed" in m for m in logs), 2)


if __name__ == "__main__":
    unittest.main()
