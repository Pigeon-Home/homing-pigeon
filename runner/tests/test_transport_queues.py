#!/usr/bin/env python3
# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""The queues transport extension against a fake Worker (Phase 2 of
docs/project/hosting.md). The fake speaks the same contract the
Cloudflare Worker does (runner/cloud/queues-worker/src/index.js, whose
own tests run under node): lease, ack, results. It listens on
loopback in this process; nothing leaves the machine.
"""
import hashlib
import http.server
import json
import os
import sys
import secrets
import tempfile
import threading
import unittest
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.transport_extensions import channel as ch  # noqa: E402
from runner.transport_extensions.queues import __main__ as q  # noqa: E402
from runner.cloud import send_job  # noqa: E402

RUNNER_TOKEN = "runner-token"
SI_TOKEN = "si-token"


class FakeWorkerState:
    def __init__(self):
        self.jobs = {}       # id -> envelope
        self.leased = set()
        self.acked = []
        self.results = {}
        self.results_acked = []
        self.renewed = []
        self.dead = []
        self.calls = []
        self.fail_results = 0  # next N result posts answer 503
        self.fail_acks = 0     # next N job acks answer 500
        self.conflict_acks = False  # 409: the job is still queued
        self.result_status = None  # a permanent refusal, when set
        self.attempt_out = {}  # id -> attempt number the next pull reports


def make_handler(state):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _auth(self, token):
            return self.headers.get("Authorization") == f"Bearer {token}"

        def _send(self, status, body=b"", ctype="application/json"):
            self.send_response(status)
            if body:
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
            else:
                self.send_header("Content-Length", "0")
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            state.calls.append(("GET", path))
            if path.startswith("/t/alice/results"):
                return self._si_results()
            if path.startswith("/t/alice/dlq"):
                return self._si_dlq()
            if not path.startswith("/t/alice/jobs"):
                return self._send(404)
            if not self._auth(RUNNER_TOKEN):
                return self._send(401)
            free = [(i, e) for i, e in state.jobs.items()
                    if i not in state.leased]
            if not free:
                return self._send(204)
            out = []
            for i, e in free[:8]:
                state.leased.add(i)
                out.append({"id": i, "envelope": e,
                            "attempt": state.attempt_out.get(i, 1)})
            return self._send(200, json.dumps({"jobs": out}).encode())

        def _si_results(self):
            if not self._auth(SI_TOKEN):
                return self._send(401)
            if not state.results:
                return self._send(204)
            out = [{"id": i, "envelope": e}
                   for i, e in list(state.results.items())[:20]]
            return self._send(200, json.dumps({"results": out}).encode())

        def _si_dlq(self):
            if not self._auth(SI_TOKEN):
                return self._send(401)
            if not state.dead:
                return self._send(204)
            out = [{"id": i, "attempts": 5, "subject": f"[HOMING-PIGEON] job {i}"}
                   for i in state.dead]
            return self._send(200, json.dumps({"dead": out}).encode())

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n).decode("utf-8") if n else ""
            state.calls.append(("POST", path))
            if path == "/t/alice/jobs":
                if not self._auth(SI_TOKEN):
                    return self._send(401)
                parsed = ch.parse_envelope(body)
                if parsed is None:
                    return self._send(400, b'{"error":"malformed"}')
                jid = q._job_id(parsed[0])
                state.jobs[jid] = body
                return self._send(202, json.dumps({"id": jid}).encode())
            if path.startswith("/t/alice/dlq/"):
                if not self._auth(SI_TOKEN):
                    return self._send(401)
                _, _, _, _, did, verb = path.split("/")
                if did not in state.dead:
                    return self._send(404)
                state.dead.remove(did)
                if verb == "requeue":
                    state.jobs[did] = envelope(did)
                    return self._send(202, json.dumps({"id": did}).encode())
                return self._send(204)
            if path.startswith("/t/alice/jobs/") and path.endswith("/lease"):
                if not self._auth(RUNNER_TOKEN):
                    return self._send(401)
                jid = path.split("/")[4]
                state.renewed.append(jid)
                return self._send(204 if jid in state.leased else 404)
            if path.startswith("/t/alice/jobs/") and path.endswith("/ack"):
                if not self._auth(RUNNER_TOKEN):
                    return self._send(401)
                if state.fail_acks:
                    state.fail_acks -= 1
                    return self._send(500, b'{"error":"later"}')
                if state.conflict_acks:
                    return self._send(409, b'{"error":"not this pull"}')
                jid = path.split("/")[4]
                had = state.jobs.pop(jid, None)
                state.leased.discard(jid)
                state.acked.append(jid)
                return self._send(204 if had else 404)
            if path.startswith("/t/alice/results/") and path.endswith("/ack"):
                if not self._auth(SI_TOKEN):
                    return self._send(401)
                rid = path.split("/")[4]
                had = state.results.pop(rid, None)
                state.results_acked.append(rid)
                return self._send(204 if had else 404)
            if path == "/t/alice/results":
                if not self._auth(RUNNER_TOKEN):
                    return self._send(401)
                if state.fail_results:
                    state.fail_results -= 1
                    return self._send(503, b'{"error":"later"}')
                if state.result_status:
                    return self._send(state.result_status,
                                      b'{"error":"no"}')
                parsed = ch.parse_envelope(body)
                rid = q._result_id(parsed[0]) if parsed else None
                if rid and rid in state.results:
                    digest = hashlib.sha256(
                        state.results[rid].encode("utf-8")).hexdigest()
                    return self._send(200, json.dumps(
                        {"id": rid, "duplicate": True,
                         "sha256": digest}).encode())
                state.results[rid] = body
                return self._send(202, json.dumps({"id": rid}).encode())
            return self._send(404)
    return Handler


class FakeWorker:
    def __enter__(self):
        self.state = FakeWorkerState()
        self.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.state))
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/t/alice"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def envelope(job_id, body='{"v":1,"sig":"00"}'):
    return f"[HOMING-PIGEON] job {job_id}\n\n{body}\n"


class QueueClientTest(unittest.TestCase):
    def test_pull_ack_and_post(self):
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            c = q.QueueClient(w.url, RUNNER_TOKEN)
            jobs = c.pull(8)
            self.assertEqual(jobs, [("j1", envelope("j1"))])
            self.assertEqual(c.pull(8), [])
            self.assertTrue(c.post_result(
                "[HOMING-PIGEON] result j1\n\n{\"exit_code\":0}\n"))
            self.assertIn("j1", w.state.results)
            self.assertTrue(c.ack("j1"))
            self.assertTrue(c.ack("j1"))  # 404 is still finished
            self.assertEqual(w.state.acked, ["j1", "j1"])

    def test_wrong_token_is_an_error_not_a_crash(self):
        with FakeWorker() as w:
            c = q.QueueClient(w.url, "nope")
            with self.assertRaises(RuntimeError) as cm:
                c.pull(8)
            self.assertIn("401", str(cm.exception))

    def test_resolve_token_prefers_the_environment(self):
        self.assertEqual(q.resolve_token({"token_env": "X"}, {"X": "abc"}), "abc")
        self.assertEqual(q.resolve_token({"token_env": "X", "token": "t"}, {}), "t")
        self.assertIsNone(q.resolve_token({"token_env": "X"}, {}))
        self.assertIsNone(q.resolve_token({}, {}))

    def test_int_reads_unusable_as_default(self):
        for bad in (None, True, "x", -1, 0, 10 ** 400, 1000):
            self.assertEqual(q._int(bad, 8, lo=1, hi=100), 8, repr(bad))
        self.assertEqual(q._int("5", 8, lo=1, hi=100), 5)

    def test_a_url_that_only_starts_with_loopback_is_not(self):
        # The inference door parses the host. The queue door used to
        # accept any string that began with the loopback text, and
        # the bearer token would have gone there in clear.
        self.assertTrue(q.queue_base_allowed("http://127.0.0.1:9/t/a"))
        self.assertTrue(q.queue_base_allowed("http://localhost/t/a"))
        self.assertTrue(q.queue_base_allowed("http://[::1]/t/a"))
        self.assertTrue(q.queue_base_allowed("https://q.example.test/t/a"))
        for bad in ("http://127.0.0.1.evil.test/t/a",
                    "http://localhost.evil.test/t/a",
                    "http://127.0.0.1@evil.test/t/a",
                    "http://q.example.test/t/a",
                    "http://2130706433/t/a",
                    "https://", "", None):
            self.assertFalse(q.queue_base_allowed(bad), bad)

    def test_a_redirect_does_not_take_the_token_with_it(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:1/stolen")
                self.end_headers()

            def log_message(self, *a):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/t/alice"
            client = q.QueueClient(url, RUNNER_TOKEN)
            with self.assertRaises(RuntimeError) as cm:
                client.pull(1)
        finally:
            server.shutdown()
            server.server_close()
        self.assertIn("302", str(cm.exception))


class QueuePipeTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.channel = os.path.join(self.td.name, "channel")
        ch.dirs(self.channel)

    def tearDown(self):
        self.td.cleanup()

    def _core_answers(self, ident, job_id):
        """Pretend the core ran the job: consume the inbox file and
        drop a result in the outbox, the way runner.py does."""
        d = ch.dirs(self.channel)
        os.replace(os.path.join(d["inbox"], ident + ".job.txt"),
                   os.path.join(d["inbox_done"], ident + ".job.txt"))
        ch._atomic_write(os.path.join(d["outbox"], ident + ".result.txt"),
                         f"[HOMING-PIGEON] result {job_id}\n\n"
                         f"{{\"exit_code\":0,\"sig\":\"00\"}}\n")

    def test_jobs_flow_in_results_flow_out_and_acks_follow(self):
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            w.state.jobs["j2"] = envelope("j2")
            pipe = q.QueuePipe({"max_jobs": 8}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            inbox = sorted(os.listdir(ch.dirs(self.channel)["inbox"]))
            self.assertEqual(inbox, ["done", "j1.job.txt", "j2.job.txt"])
            self.assertEqual(w.state.acked, [])  # nothing finished yet
            pipe.push_results()
            self.assertEqual(w.state.acked, [])
            self._core_answers("j1", "j1")
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1"])
            self.assertIn("j1", w.state.results)
            self.assertEqual(
                os.listdir(ch.dirs(self.channel)["outbox_done"]),
                ["j1.result.txt"])
            # A pull while j2 is still leased delivers nothing new.
            pipe.pull_jobs()
            self.assertEqual(sorted(os.listdir(
                ch.dirs(self.channel)["inbox"])),
                ["done", "j2.job.txt"])

    def test_a_running_job_keeps_its_lease_until_its_result_is_in(self):
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.renew_leases()               # nothing held yet
            self.assertEqual(w.state.renewed, [])
            pipe.pull_jobs()
            pipe.renew_leases()               # running: renewed
            pipe.renew_leases()
            self.assertEqual(w.state.renewed, ["j1", "j1"])
            self._core_answers("j1", "j1")
            pipe.push_results()
            pipe.renew_leases()               # finished: no renewal
            self.assertEqual(w.state.renewed, ["j1", "j1"])
            self.assertEqual(w.state.acked, ["j1"])

    def test_an_id_offered_again_after_it_finished_is_delivered_again(self):
        # The SI requeues, or posts the same id again, while this
        # process is still up. The pull has already leased it. Ignoring
        # the offer burns that lease, and the next ones, until the job
        # is dead. The previous life's done-file must not ack this one.
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            self._core_answers("j1", "j1")
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1"])
            again = envelope("j1", '{"v":1,"script":"echo again"}')
            w.state.jobs["j1"] = again
            pipe.pull_jobs()
            inbox = os.path.join(ch.dirs(self.channel)["inbox"], "j1.job.txt")
            done = os.path.join(ch.dirs(self.channel)["inbox_done"],
                                "j1.job.txt")
            self.assertTrue(os.path.isfile(inbox))
            with open(inbox, encoding="utf-8") as fh:
                self.assertIn("echo again", fh.read())
            self.assertFalse(os.path.exists(done))
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1"])
            self._core_answers("j1", "j1")
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1", "j1"])

    def test_a_lapsed_lease_keeps_one_copy_and_the_new_attempt(self):
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            client = q.QueueClient(w.url, RUNNER_TOKEN)
            pipe = q.QueuePipe({}, self.channel, client)
            pipe.pull_jobs()
            self.assertEqual(client._attempt["j1"], 1)
            w.state.leased.discard("j1")
            w.state.attempt_out["j1"] = 2
            pipe.pull_jobs()
            self.assertEqual(sorted(os.listdir(
                ch.dirs(self.channel)["inbox"])), ["done", "j1.job.txt"])
            self.assertEqual(client._attempt["j1"], 2)
            self.assertIn("j1", pipe._pending)

    def test_a_lease_the_queue_no_longer_holds_is_logged_not_fatal(self):
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            w.state.leased.discard("j1")     # the lease lapsed
            pipe.renew_leases()
            self.assertEqual(w.state.renewed, ["j1"])

    def test_a_rejected_job_is_acked_without_a_result(self):
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            d = ch.dirs(self.channel)
            os.replace(os.path.join(d["inbox"], "j1.job.txt"),
                       os.path.join(d["inbox_done"], "j1.job.txt"))
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1"])

    def test_a_collision_name_keeps_the_first_result_and_acks_the_job(self):
        # While j1.result.txt is still in the outbox, the writer names
        # the next file j1.result-2.txt. That name sorts first, and it
        # does not end in .result.txt, so the stem is not the job id.
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            d = ch.dirs(self.channel)
            ch._atomic_write(os.path.join(d["outbox"], "j1.result.txt"),
                             '[HOMING-PIGEON] result j1\n\n{"exit_code":0}\n')
            ch._atomic_write(os.path.join(d["outbox"], "j1.result-2.txt"),
                             '[HOMING-PIGEON] result j1\n\n{"exit_code":1}\n')
            pipe.push_results()
            self.assertIn("j1", w.state.acked)
            self.assertNotIn("j1", w.state.jobs)
            stored = w.state.results["j1"].replace(" ", "")
            self.assertIn('"exit_code":0', stored)
            self.assertNotIn('"exit_code":1', stored)
            # The second file is a different envelope. It was not
            # stored, so it stays for a person instead of being
            # thrown away.
            self.assertEqual(sorted(os.listdir(d["outbox"])),
                             ["done", "j1.result-2.txt"])
            self.assertEqual(os.listdir(d["outbox_done"]),
                             ["j1.result.txt"])

    def test_a_collision_name_alone_still_acks_the_job(self):
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            d = ch.dirs(self.channel)
            ch._atomic_write(os.path.join(d["outbox"], "j1.result-2.txt"),
                             '[HOMING-PIGEON] result j1\n\n{"exit_code":0}\n')
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1"])
            self.assertIn("j1", w.state.results)

    def test_a_result_headed_for_a_different_job_is_left(self):
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            w.state.jobs["j2"] = envelope("j2")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            d = ch.dirs(self.channel)
            ch._atomic_write(os.path.join(d["outbox"], "j1.result.txt"),
                             '[HOMING-PIGEON] result j2\n\n{"exit_code":0}\n')
            pipe.push_results()
            self.assertEqual(w.state.acked, [])
            self.assertEqual(w.state.results, {})
            self.assertTrue(os.path.isfile(
                os.path.join(d["outbox"], "j1.result.txt")))
            self.assertIn("j1", w.state.jobs)
            self.assertIn("j2", w.state.jobs)

    def test_a_different_result_already_stored_does_not_finish_the_job(self):
        # The previous life left its result. This life produced a
        # different one. A 200 is not that result being stored, so
        # the job stays leased and the new file stays in the outbox.
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            w.state.results["j1"] = (
                '[HOMING-PIGEON] result j1\n\n{"exit_code":0}\n')
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            d = ch.dirs(self.channel)
            ch._atomic_write(os.path.join(d["outbox"], "j1.result.txt"),
                             '[HOMING-PIGEON] result j1\n\n{"exit_code":1}\n')
            pipe.push_results()
            self.assertEqual(w.state.acked, [])
            self.assertIn("j1", w.state.jobs)
            self.assertIn("j1", pipe._pending)
            self.assertIn('"exit_code":0', w.state.results["j1"])
            self.assertTrue(os.path.isfile(
                os.path.join(d["outbox"], "j1.result.txt")))

    def test_a_retried_result_of_the_same_bytes_finishes_the_job(self):
        text = '[HOMING-PIGEON] result j1\n\n{"exit_code":0}\n'
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            w.state.results["j1"] = text
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            d = ch.dirs(self.channel)
            ch._atomic_write(os.path.join(d["outbox"], "j1.result.txt"), text)
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1"])
            self.assertFalse(os.path.exists(
                os.path.join(d["outbox"], "j1.result.txt")))
            self.assertNotIn("j1", pipe._pending)

    def test_a_result_the_worker_refuses_is_retried_not_dropped(self):
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            w.state.fail_results = 1
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            self._core_answers("j1", "j1")
            pipe.push_results()
            self.assertEqual(w.state.acked, [])
            self.assertEqual(sorted(os.listdir(ch.dirs(self.channel)["outbox"])),
                             ["done", "j1.result.txt"])
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1"])
            self.assertIn("j1", w.state.results)

    def test_a_result_the_worker_will_never_take_is_set_aside(self):
        # 413 will not succeed next pass. The file is set aside for
        # the stub, and the job stays leased so this pass does not
        # finish it with nothing stored.
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            w.state.result_status = 413
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            self._core_answers("j1", "j1")
            pipe.push_results()
            self.assertEqual(w.state.acked, [])
            self.assertIn("j1", pipe._pending)
            d = ch.dirs(self.channel)
            self.assertFalse(os.path.exists(
                os.path.join(d["outbox"], "j1.result.txt")))
            failed = os.path.join(d["outbox"], "failed")
            self.assertIn("j1.result.txt", os.listdir(failed))
            self.assertTrue(any(n.endswith(".refused.txt")
                                for n in os.listdir(failed)))

    def test_an_oversized_result_does_not_finish_the_job(self):
        # The listing sets a file over the channel cap aside before
        # this pass can post it. The core has already consumed the
        # job. That must not ack it: nothing is stored yet.
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            d = ch.dirs(self.channel)
            os.replace(os.path.join(d["inbox"], "j1.job.txt"),
                       os.path.join(d["inbox_done"], "j1.job.txt"))
            with open(os.path.join(d["outbox"], "j1.result.txt"), "wb") as fh:
                fh.write(b"x" * (ch.FILE_MAX_BYTES + 1))
            pipe.push_results()
            self.assertEqual(w.state.acked, [])
            self.assertIn("j1", pipe._pending)
            self.assertIn("j1", w.state.jobs)
            failed = os.path.join(d["outbox"], "failed")
            self.assertIn("j1.result.txt", os.listdir(failed))

    def test_a_refused_collision_name_is_the_job_the_sweep_reads(self):
        # j1.result-2.txt does not end in .result.txt. Set aside
        # under that name, the sweep opens <stem>.result.txt, never
        # sees the body, and writes no stub. The file stays in
        # failed/, so the job stays leased.
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            d = ch.dirs(self.channel)
            os.replace(os.path.join(d["inbox"], "j1.job.txt"),
                       os.path.join(d["inbox_done"], "j1.job.txt"))
            with open(os.path.join(d["outbox"], "j1.result-2.txt"), "wb") as fh:
                fh.write(b"x" * (ch.FILE_MAX_BYTES + 1))
            pipe.push_results()
            self.assertEqual(w.state.acked, [])
            self.assertIn("j1", pipe._pending)
            failed = os.path.join(d["outbox"], "failed")
            self.assertEqual(sorted(os.listdir(failed)),
                             ["j1.refused.txt", "j1.result.txt"])

    def test_a_result_that_cannot_be_read_does_not_finish_the_job(self):
        # No blank line, so no transport posts it. The core has
        # consumed the job. Skipping the file and acking here
        # finished the job with nothing stored.
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            d = ch.dirs(self.channel)
            os.replace(os.path.join(d["inbox"], "j1.job.txt"),
                       os.path.join(d["inbox_done"], "j1.job.txt"))
            with open(os.path.join(d["outbox"], "j1.result.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("not an envelope")
            with open(os.path.join(d["outbox"], "j1.target.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("ops@example.com\n")
            pipe.push_results()
            self.assertEqual(w.state.acked, [])
            self.assertIn("j1", pipe._pending)
            self.assertIn("j1", w.state.jobs)
            failed = os.path.join(d["outbox"], "failed")
            self.assertEqual(sorted(os.listdir(failed)),
                             ["j1.refused.txt", "j1.result.txt"])
            self.assertTrue(os.path.isfile(
                os.path.join(d["outbox"], "j1.target.txt")))

    def test_a_symlink_result_is_not_followed_and_does_not_finish_the_job(self):
        # A link was not a file the listing would post, so it was
        # skipped. The job was acked, and nothing was stored.
        # Following the link would have read some other file.
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            d = ch.dirs(self.channel)
            os.replace(os.path.join(d["inbox"], "j1.job.txt"),
                       os.path.join(d["inbox_done"], "j1.job.txt"))
            secret = os.path.join(self.channel, "secret.txt")
            with open(secret, "w", encoding="utf-8") as fh:
                fh.write("not-for-the-queue\n")
            os.symlink(secret, os.path.join(d["outbox"], "j1.result.txt"))
            pipe.push_results()
            self.assertEqual(w.state.acked, [])
            self.assertIn("j1", w.state.jobs)
            self.assertFalse(os.path.lexists(
                os.path.join(d["outbox"], "j1.result.txt")))
            failed = os.path.join(d["outbox"], "failed")
            stored = os.path.join(failed, "j1.result.txt")
            self.assertTrue(os.path.isfile(stored))
            self.assertFalse(os.path.islink(stored))
            with open(stored, encoding="utf-8") as fh:
                self.assertNotIn("not-for-the-queue", fh.read())

    def test_two_ids_that_differ_past_120_characters_both_finish(self):
        # The channel kept 120 characters of the id. A queue id is
        # 128. These two shared one inbox file, the result's name
        # was not the id in the subject, and the done-file was not
        # the name the ack looks for. Neither result was posted and
        # neither job was acked.
        a = "c" * 120 + "a" * 8
        b = "c" * 120 + "b" * 8
        with FakeWorker() as w:
            w.state.jobs[a] = envelope(a)
            w.state.jobs[b] = envelope(b)
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            inbox = ch.dirs(self.channel)["inbox"]
            names = sorted(n for n in os.listdir(inbox) if n != "done")
            self.assertEqual(names, [a + ".job.txt", b + ".job.txt"])
            self._core_answers(a, a)
            self._core_answers(b, b)
            pipe.push_results()
            self.assertEqual(sorted(w.state.acked), sorted([a, b]))
            self.assertIn(f"result {a}", w.state.results[a])
            self.assertIn(f"result {b}", w.state.results[b])
            self.assertNotIn(a, pipe._pending)
            self.assertNotIn(b, pipe._pending)

    def test_an_ack_the_queue_refuses_is_retried(self):
        # The result was stored. The ack came back 500. Moving the
        # file and forgetting the id there meant the next pass did
        # not try again, and the job stayed leased with no one to
        # finish it.
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            w.state.fail_acks = 1
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            self._core_answers("j1", "j1")
            pipe.push_results()
            self.assertEqual(w.state.acked, [])
            self.assertIn("j1", pipe._pending)
            self.assertIn("j1", w.state.jobs)
            self.assertIn("j1", w.state.results)
            d = ch.dirs(self.channel)
            self.assertTrue(os.path.isfile(
                os.path.join(d["outbox"], "j1.result.txt")))
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1"])
            self.assertNotIn("j1", pipe._pending)
            self.assertNotIn("j1", w.state.jobs)
            self.assertFalse(os.path.exists(
                os.path.join(d["outbox"], "j1.result.txt")))

    def test_an_ack_for_another_pull_keeps_the_result(self):
        # 404 means the job is not queued. A receipt that is not
        # this pull's used to be 404 too. The client forgot the
        # result, and the next time the lease ended the job ran
        # again. 409 leaves the file, and the next pass tries
        # the ack again.
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            w.state.conflict_acks = True
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            self._core_answers("j1", "j1")
            pipe.push_results()
            self.assertEqual(w.state.acked, [])
            self.assertIn("j1", pipe._pending)
            self.assertIn("j1", w.state.jobs)
            self.assertIn("j1", w.state.results)
            self.assertTrue(os.path.isfile(os.path.join(
                ch.dirs(self.channel)["outbox"], "j1.result.txt")))

    def test_a_result_from_the_life_already_finished_does_not_ack_the_next(self):
        # The first life posted and was acked. The file was still
        # in the outbox when the id was queued again. Posting it
        # acked the new life, so that life never ran.
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            self._core_answers("j1", "j1")
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1"])
            d = ch.dirs(self.channel)
            os.replace(os.path.join(d["outbox_done"], "j1.result.txt"),
                       os.path.join(d["outbox"], "j1.result.txt"))
            w.state.jobs["j1"] = envelope("j1")
            w.state.leased.discard("j1")
            pipe.pull_jobs()
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1"])
            self.assertIn("j1", w.state.jobs)
            self.assertIn("j1", pipe._pending)
            self.assertFalse(os.path.exists(
                os.path.join(d["outbox"], "j1.result.txt")))
            self._core_answers("j1", "j1")
            pipe.push_results()
            self.assertEqual(w.state.acked, ["j1", "j1"])
            self.assertNotIn("j1", w.state.jobs)
            self.assertNotIn("j1", pipe._pending)

    def test_malformed_and_oversize_envelopes_are_refused_and_acked(self):
        with FakeWorker() as w:
            w.state.jobs["bad"] = "no blank line here"
            w.state.jobs["big"] = envelope("big", "x" * (q.MAX_BYTES + 1))
            pipe = q.QueuePipe({}, self.channel,
                               q.QueueClient(w.url, RUNNER_TOKEN))
            pipe.pull_jobs()
            self.assertEqual(sorted(w.state.acked), ["bad", "big"])
            self.assertEqual(os.listdir(ch.dirs(self.channel)["inbox"]),
                             ["done"])

    def test_main_runs_bounded_passes_and_refuses_bad_config(self):
        with FakeWorker() as w:
            w.state.jobs["j1"] = envelope("j1")
            cfg_path = os.path.join(self.td.name, "rt.json")
            with open(cfg_path, "w", encoding="utf-8") as fh:
                json.dump({"url": w.url, "token_env": "HP_TEST_RUNNER_TOKEN",
                           "extension_poll_interval_sec": 0.2}, fh)
            os.environ["HP_TEST_RUNNER_TOKEN"] = RUNNER_TOKEN
            try:
                rc = q.main(["queues", self.channel, cfg_path], passes=1)
            finally:
                del os.environ["HP_TEST_RUNNER_TOKEN"]
            self.assertEqual(rc, 0)
            self.assertIn("j1.job.txt",
                          os.listdir(ch.dirs(self.channel)["inbox"]))
            # No token: refuse to start.
            self.assertEqual(q.main(["queues", self.channel, cfg_path],
                                    passes=1), 2)
            with open(cfg_path, "w", encoding="utf-8") as fh:
                json.dump({"url": "http://plain.example.test/t/a",
                           "token": "t"}, fh)
            self.assertEqual(q.main(["queues", self.channel, cfg_path],
                                    passes=1), 2)
            for disguised in ("http://127.0.0.1.evil.test/t/a",
                              "http://localhost.evil.test/t/a",
                              "http://127.0.0.1@evil.test/t/a"):
                with open(cfg_path, "w", encoding="utf-8") as fh:
                    json.dump({"url": disguised, "token": "t"}, fh)
                self.assertEqual(
                    q.main(["queues", self.channel, cfg_path], passes=1),
                    2, disguised)


class SendJobToQueueTest(unittest.TestCase):
    def test_post_to_queue_uses_the_env_token_and_the_jobs_route(self):
        with FakeWorker() as w:
            os.environ["HP_SI_TOKEN"] = SI_TOKEN
            try:
                status, text = send_job.post_to_queue(w.url, envelope("j9"))
            finally:
                del os.environ["HP_SI_TOKEN"]
            self.assertEqual(status, 202)
            self.assertEqual(json.loads(text)["id"], "j9")
            self.assertIn("j9", w.state.jobs)
            self.assertEqual(w.state.calls[-1], ("POST", "/t/alice/jobs"))

    def test_missing_token_and_plain_http_are_refused(self):
        os.environ.pop("HP_SI_TOKEN", None)
        with self.assertRaises(SystemExit):
            send_job.post_to_queue("https://q.example.test/t/a", envelope("j"))
        os.environ["HP_SI_TOKEN"] = SI_TOKEN
        try:
            with self.assertRaises(SystemExit):
                send_job.post_to_queue("http://q.example.test/t/a",
                                       envelope("j"))
            for disguised in ("http://127.0.0.1.evil.test/t/a",
                              "http://localhost.evil.test/t/a",
                              "http://127.0.0.1@evil.test/t/a"):
                with self.assertRaises(SystemExit):
                    send_job.post_to_queue(disguised, envelope("j"))
        finally:
            del os.environ["HP_SI_TOKEN"]

    def test_the_cli_queues_a_signed_job_end_to_end(self):
        with FakeWorker() as w:
            os.environ["HP_SI_TOKEN"] = SI_TOKEN
            try:
                import io
                from contextlib import redirect_stderr, redirect_stdout
                from unittest import mock
                err = io.StringIO()
                import secrets as _s
                argv = ["send_job", "new", "--secret", _s.token_hex(32),
                        "--kind", "ping", "--to-queue", w.url]
                with mock.patch.object(sys, "argv", argv), \
                        redirect_stdout(io.StringIO()), redirect_stderr(err):
                    rc = send_job.main()
            finally:
                del os.environ["HP_SI_TOKEN"]
            self.assertEqual(rc, 0, err.getvalue())
            self.assertEqual(len(w.state.jobs), 1)
            jid, env = next(iter(w.state.jobs.items()))
            self.assertIn(f"[HOMING-PIGEON] job {jid}", env)
            self.assertIn('"hp_enc"', env)



class SendJobResultsTest(unittest.TestCase):
    """`send_job.py results`: the SI's half of the loop, read back."""

    SECRET = secrets.token_hex(32)

    def _signed_result(self, job_id, secret=None, encrypt=True):
        secret = secret or self.SECRET
        payload = {"v": 1, "type": "result", "job_id": job_id,
                   "exit_code": 0, "stdout": "pong\n"}
        body = send_job.sign_payload(payload, secret)
        if encrypt:
            body = send_job.jobcrypto.encrypt_body(
                body, secret, job_id=job_id, key_id="",
                sign=send_job.sign_payload)
        return f"[HOMING-PIGEON] result {job_id}\n\n{body}\n"

    def _run(self, w, *extra):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from unittest import mock
        out, err = io.StringIO(), io.StringIO()
        argv = ["send_job", "results", "--from-queue", w.url,
                "--secret", self.SECRET] + list(extra)
        os.environ["HP_SI_TOKEN"] = SI_TOKEN
        try:
            with mock.patch.object(sys, "argv", argv), \
                    redirect_stdout(out), redirect_stderr(err):
                rc = send_job.main()
        finally:
            del os.environ["HP_SI_TOKEN"]
        lines = [json.loads(l) for l in out.getvalue().splitlines() if l]
        return rc, lines, err.getvalue()

    def test_an_encrypted_result_is_opened_under_its_subject_job_id(self):
        with FakeWorker() as w:
            w.state.results["j1"] = self._signed_result("j1")
            rc, lines, err = self._run(w)
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0]["ok"])
        self.assertEqual(lines[0]["job_id"], "j1")
        self.assertEqual(lines[0]["payload"]["stdout"], "pong\n")
        self.assertNotIn("acked", lines[0])
        self.assertIn("j1", w.state.results)   # no --ack, still queued

    def test_ack_removes_only_what_verified(self):
        with FakeWorker() as w:
            w.state.results["good"] = self._signed_result("good")
            w.state.results["bad"] = self._signed_result("bad",
                                                         secret=secrets.token_hex(32))
            rc, lines, _err = self._run(w, "--ack")
        self.assertEqual(rc, 1)
        by = {l["id"]: l for l in lines}
        self.assertTrue(by["good"]["ok"])
        self.assertTrue(by["good"]["acked"])
        self.assertFalse(by["bad"]["ok"])
        self.assertNotIn("acked", by["bad"])
        self.assertEqual(w.state.results_acked, ["good"])
        self.assertIn("bad", w.state.results)

    def test_a_cleartext_result_verifies_and_an_empty_queue_is_zero(self):
        with FakeWorker() as w:
            rc, lines, err = self._run(w)
            self.assertEqual((rc, lines), (0, []))
            self.assertIn("no results waiting", err)
            w.state.results["c1"] = self._signed_result("c1", encrypt=False)
            rc, lines, _err = self._run(w)
        self.assertEqual(rc, 0)
        self.assertEqual(lines[0]["payload"]["exit_code"], 0)

    def test_a_refused_read_is_two_and_the_token_never_leaves_the_env(self):
        with FakeWorker() as w:
            import io
            from contextlib import redirect_stderr, redirect_stdout
            from unittest import mock
            argv = ["send_job", "results", "--from-queue", w.url,
                    "--secret", self.SECRET, "--queue-token-env", "HP_WRONG"]
            os.environ["HP_WRONG"] = "not-the-token"
            try:
                with mock.patch.object(sys, "argv", argv), \
                        redirect_stdout(io.StringIO()), \
                        redirect_stderr(io.StringIO()):
                    rc = send_job.main()
            finally:
                del os.environ["HP_WRONG"]
        self.assertEqual(rc, 2)
        os.environ.pop("HP_SI_TOKEN", None)
        with self.assertRaises(SystemExit):
            send_job._queue_call("https://q.example.test/t/a", "GET",
                                 "/results")



class SendJobDlqTest(unittest.TestCase):
    """`send_job.py dlq`: the dead-letter list, read and handled."""

    def _run(self, w, *extra):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from unittest import mock
        out, err = io.StringIO(), io.StringIO()
        argv = ["send_job", "dlq", "--from-queue", w.url] + list(extra)
        os.environ["HP_SI_TOKEN"] = SI_TOKEN
        try:
            with mock.patch.object(sys, "argv", argv), \
                    redirect_stdout(out), redirect_stderr(err):
                rc = send_job.main()
        finally:
            del os.environ["HP_SI_TOKEN"]
        return rc, [json.loads(l) for l in out.getvalue().splitlines() if l], \
            err.getvalue()

    def test_list_drop_and_requeue(self):
        with FakeWorker() as w:
            rc, lines, err = self._run(w)
            self.assertEqual((rc, lines), (0, []))
            self.assertIn("empty", err)
            w.state.dead = ["d1", "d2"]
            rc, lines, _ = self._run(w)
            self.assertEqual(rc, 0)
            self.assertEqual([l["id"] for l in lines], ["d1", "d2"])
            rc, lines, _ = self._run(w, "--drop", "d1")
            self.assertEqual((rc, lines), (0, [{"id": "d1", "dropped": True}]))
            rc, lines, _ = self._run(w, "--requeue", "d2")
            self.assertEqual((rc, lines), (0, [{"id": "d2", "requeue": True}]))
            self.assertIn("d2", w.state.jobs)
            self.assertEqual(w.state.dead, [])
            rc, _, err = self._run(w, "--drop", "d9")
            self.assertEqual(rc, 1)
            self.assertIn("not on the dead-letter list", err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
