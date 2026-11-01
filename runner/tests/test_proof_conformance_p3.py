#!/usr/bin/env python3
"""Stage 5 conformance for P3: a transport's own credentials
are a required second gate beside the signature, and the core
is transport-blind.

Driven per transport at its own edge, plus one chain end to
end: the file pipe, the channel, the real core through
process_transport_message, and back out to the watched outbox.
NATS is driven at its constructor and against a fake broker;
DTLS at its startup floor, its directory-wrapped PSK lookup,
and a real pipe on a real UDP socket; the queues at their
client, their startup, and the hosted Worker itself under
node. Email is the clause-4 transport: no sender gate, and
none is claimed. Clause numbers are properties.md's P3
clauses.
"""
import email as email_lib
import imaplib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from argparse import Namespace
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner import runner  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402
from runner.transport_extensions.dtls import __main__ as dtls_ext  # noqa: E402
from runner.transport_extensions.file import __main__ as file_ext  # noqa: E402
from runner.transport_extensions.nats import __main__ as nats_ext  # noqa: E402
from runner.transport_extensions.queues import __main__ as queues_ext  # noqa: E402
from runner.wire import dtlsproto, mailbox, transports  # noqa: E402

try:
    from runner.tests import test_proof_conformance as base
except ImportError:  # pragma: no cover - direct-file runs
    import test_proof_conformance as base

SECRET = base.SECRET
_OK = base._OK_RESULT


def _split(job):
    raw = base._wire2(job)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    msg = email_lib.message_from_string(raw)
    return msg["Subject"], msg.get_payload(decode=True).decode(
        "utf-8")


def _envelope_text(job):
    subject, body = _split(job)
    return subject + "\n\n" + body


# ------------------------------------------------------------------
# The file transport, end to end (clauses 1, 2, and 3)
# ------------------------------------------------------------------

class FileChainTest(base._GateCase):
    """A valid envelope travels the whole chain and executes;
    a bad-signature envelope is delivered the same way and
    never executes -- the pipe is a carrier, the core's gate
    is the gate, on every transport."""

    def _chain(self, td, envelope_text, fname="job1.txt"):
        watched = os.path.join(td, "watched")
        inbox = os.path.join(watched, "inbox")
        outbox = os.path.join(watched, "outbox")
        os.makedirs(inbox)
        with open(os.path.join(inbox, fname), "w",
                  encoding="utf-8") as fh:
            fh.write(envelope_text)
        home = os.path.join(td, "home")
        os.makedirs(home)
        channel_root = transports.channel_paths(home, "file")["root"]
        pipe = file_ext.FilePipe(
            {"base_dir": watched, "inbox": inbox, "outbox": outbox},
            channel_root)
        pipe.scan_jobs()
        cfg = {"mailbox_user": "t@example.com",
               "shared_secret": SECRET, "base_dir": home,
               "oracle_opinion_mode": "off"}
        secrets = runner.build_secrets(cfg)
        seen = {}
        executed = []

        def execute(_cfg, run_job, _base):
            executed.append(run_job)
            return dict(_OK)

        def process(subject, body):
            return runner.process_transport_message(
                cfg, home, seen, secrets, None, subject, body,
                opts=Namespace(dry_run=False, no_send=False),
                transport="file")

        with mock.patch.object(runner, "execute_job", execute):
            visited = transports.service_channel(home, "file",
                                                 process)
        pipe.scan_results()
        return {"visited": visited, "executed": executed,
                "inbox": inbox, "outbox": outbox}

    def test_a_valid_envelope_executes_and_answers(self):
        job = base._job2("file-1")
        with tempfile.TemporaryDirectory() as td:
            out = self._chain(td, _envelope_text(job))
            self.assertEqual(out["visited"], 1)
            self.assertEqual(len(out["executed"]), 1)
            results = os.listdir(out["outbox"])
            self.assertEqual(results, ["file-1.result.txt"])
            done = os.listdir(os.path.join(out["inbox"], "done"))
            self.assertIn("job1.txt", done)

    def test_a_bad_signature_envelope_never_executes(self):
        job = base._job2("file-2")
        wrong = base.WRONGSECRET
        raw_bad = base._wire2(job, wrong)
        if isinstance(raw_bad, bytes):
            raw_bad = raw_bad.decode("utf-8")
        msg_bad = email_lib.message_from_string(raw_bad)
        envelope = msg_bad["Subject"] + "\n\n" + msg_bad.get_payload(
            decode=True).decode("utf-8")
        with tempfile.TemporaryDirectory() as td:
            out = self._chain(td, envelope)
            self.assertEqual(out["visited"], 1)
            self.assertEqual(out["executed"], [])
            self.assertEqual(os.listdir(out["outbox"]), [])
            done = os.listdir(os.path.join(out["inbox"], "done"))
            self.assertIn("job1.txt", done)


class FileRefusalTest(unittest.TestCase):
    """Clause 1 at the pipe's own edge: what the pipe will not
    read, it refuses with the reason left behind."""

    def _pipe(self, td):
        inbox = os.path.join(td, "inbox")
        outbox = os.path.join(td, "outbox")
        channel_root = os.path.join(td, "channel")
        pipe = file_ext.FilePipe(
            {"base_dir": td, "inbox": inbox, "outbox": outbox},
            channel_root)
        return pipe, inbox, channel_root

    def _refusal(self, pipe, inbox, fname):
        done = os.path.join(inbox, "done")
        path = os.path.join(done, fname + ".refused.txt")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_a_symlink_is_refused_unread(self):
        with tempfile.TemporaryDirectory() as td:
            pipe, inbox, channel_root = self._pipe(td)
            target = os.path.join(td, "real.txt")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(_envelope_text(base._job2("file-3")))
            os.symlink(target, os.path.join(inbox, "link.txt"))
            pipe.scan_jobs()
            reason = self._refusal(pipe, inbox, "link.txt")
            self.assertIsNotNone(reason)
            self.assertIn("symlink", reason)
            delivered = []
            for root, _dirs, files in os.walk(channel_root):
                delivered.extend(f for f in files
                                 if f.endswith(".job.txt"))
            self.assertEqual(delivered, [])

    def test_an_oversize_file_is_refused_unread(self):
        with tempfile.TemporaryDirectory() as td:
            pipe, inbox, channel_root = self._pipe(td)
            big = os.path.join(inbox, "big.txt")
            with open(big, "wb") as fh:
                fh.write(b"x" * (ch.FILE_MAX_BYTES + 1))
            pipe.scan_jobs()
            reason = self._refusal(pipe, inbox, "big.txt")
            self.assertIsNotNone(reason)
            self.assertIn("cap", reason)

    def test_a_malformed_envelope_is_refused_with_its_reason(self):
        with tempfile.TemporaryDirectory() as td:
            pipe, inbox, channel_root = self._pipe(td)
            with open(os.path.join(inbox, "bad.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("no blank line in this file\n")
            pipe.scan_jobs()
            reason = self._refusal(pipe, inbox, "bad.txt")
            self.assertIsNotNone(reason)
            self.assertIn("malformed", reason)


# ------------------------------------------------------------------
# NATS (clause 1)
# ------------------------------------------------------------------

class NatsGateTest(unittest.TestCase):
    """The pipe refuses to start without broker credentials
    unless the waiver is literally true."""

    # The bare no-credentials refusal itself is pinned in
    # test_proof_conformance.py
    # (test_nats_without_credentials_refuses_to_start); this
    # class carries the shapes around it.

    def test_a_string_waiver_does_not_waive(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(nats_ext.TransportError):
                nats_ext.NatsPipe(
                    {"allow_unauthenticated": "true"}, td)

    def test_a_literal_true_waiver_starts(self):
        with tempfile.TemporaryDirectory() as td:
            pipe = nats_ext.NatsPipe(
                {"allow_unauthenticated": True}, td)
            self.assertIsNone(pipe.client)

    def test_a_token_is_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            pipe = nats_ext.NatsPipe({"token": "tok-abc"}, td)
            self.assertIsNotNone(pipe)

    def test_url_embedded_credentials_count(self):
        with tempfile.TemporaryDirectory() as td:
            pipe = nats_ext.NatsPipe(
                {"url": "nats://user:pass@127.0.0.1:4222"}, td)
            self.assertIsNotNone(pipe)


class _FakeBroker(threading.Thread):
    """One connection: INFO, read the CONNECT and PING, answer
    with the scripted verdict line."""

    def __init__(self, verdict):
        super().__init__(daemon=True)
        self.verdict = verdict
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET,
                             socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]

    def run(self):
        try:
            conn, _addr = self.sock.accept()
            conn.settimeout(5)
            conn.sendall(b'INFO {"server_id":"fake",'
                         b'"version":"2"}\r\n')
            data = b""
            while b"PING" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            conn.sendall(self.verdict)
            time.sleep(0.2)
            conn.close()
        except OSError:
            pass
        finally:
            self.sock.close()


class NatsBrokerTest(unittest.TestCase):
    """The broker enforces at connect: an -ERR after CONNECT
    ends the attempt, and nothing is delivered."""

    def _connect(self, verdict):
        broker = _FakeBroker(verdict)
        broker.start()
        client = nats_ext.NatsClient(
            "nats://127.0.0.1:%d" % broker.port, timeout=5)
        return client

    def test_an_authorization_error_ends_the_connect(self):
        client = self._connect(b"-ERR 'Authorization Violation'\r\n")
        with self.assertRaises(nats_ext.TransportError) as cm:
            client.connect()
        self.assertIn("Authorization Violation", str(cm.exception))

    def test_a_pong_completes_the_connect(self):
        client = self._connect(b"PONG\r\n")
        self.assertIs(client.connect(), client)
        client.sock.close()


# ------------------------------------------------------------------
# DTLS (clauses 1 and 3)
# ------------------------------------------------------------------

def _runtime_main(ext, td, cfg_dict):
    path = os.path.join(td, "runtime.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg_dict, fh)
    channel = os.path.join(td, "channel")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("HOMING_PIGEON_TRANSPORT_")}
    with mock.patch.dict(os.environ, env, clear=True):
        return ext.main(["prog", channel, path])


class DtlsStartupTest(unittest.TestCase):
    """The shared secret is the handshake PSK: no secret handed
    over, no start; a secret under the entropy floor, no start."""

    def test_no_secret_no_start(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(_runtime_main(dtls_ext, td, {}), 2)

    def test_a_weak_secret_no_start(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                _runtime_main(dtls_ext, td,
                              {"shared_secret": "abc"}), 2)

    def test_the_floor_names_a_weak_additional_secret(self):
        problem = dtls_ext._psk_floor_problem(
            {"shared_secret": SECRET,
             "additional_secrets": {"k": "abc"}})
        self.assertIsNotNone(problem)
        self.assertIn("additional_secrets", problem)
        self.assertIsNone(dtls_ext._psk_floor_problem(
            {"shared_secret": SECRET}))


class DtlsDirectoryLookupTest(unittest.TestCase):
    """Clause 1's directory half: the PSK lookup itself is
    wrapped by the key directory."""

    def _look(self, cfg):
        lookup = dtls_ext.directory_lookup(
            cfg, dtlsproto.make_secret_lookup(SECRET, None))
        return lookup(dtlsproto.DEFAULT_IDENTITY.encode("utf-8"))

    def test_no_directory_the_secret_answers(self):
        found = self._look({"shared_secret": SECRET})
        self.assertEqual(found, SECRET)

    def test_a_refusing_directory_answers_nothing(self):
        found = self._look(
            {"shared_secret": SECRET,
             "key_directory": {"": {"state": "compromised"}}})
        self.assertIsNone(found)

    def test_an_unreadable_directory_answers_nothing(self):
        found = self._look(
            {"shared_secret": SECRET,
             "key_directory_file": "/no/such/directory.json"})
        self.assertIsNone(found)


class DtlsPipeSocketTest(unittest.TestCase):
    """A real pipe on a real socket: the right PSK establishes
    a session and a job reaches the channel; the wrong PSK
    never establishes, and no job reaches the channel."""

    def _pipe(self, td, **cfg_over):
        channel = os.path.join(td, "channel")
        cfg = {"shared_secret": SECRET, "port": 0,
               "bind": "127.0.0.1", "dtls_greeting": "family"}
        cfg.update(cfg_over)
        pipe = dtls_ext.DtlsPipe(cfg, channel)
        return pipe, channel, pipe.sock.getsockname()[1]

    def _drive(self, pipe, client, sock, pred, timeout=6.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pipe.run_once()
            for dg in client.tick(time.monotonic()):
                sock.send(dg)
            try:
                data = sock.recv(65535)
            except OSError:
                data = None
            if data:
                for dg in client.feed(data, time.monotonic()):
                    sock.send(dg)
            if pred():
                return True
        return pred()

    def _client(self, port, secret_value):
        client = dtlsproto.DtlsClientCore(secret_value)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.05)
        sock.connect(("127.0.0.1", port))
        return client, sock

    def _handshake(self, pipe, client, sock, timeout=6.0):
        if sys.platform.startswith("linux"):
            pipe.sock.connect(sock.getsockname())
        for dg in client.start(time.monotonic()):
            sock.send(dg)
        return self._drive(pipe, client, sock,
                           lambda: client.greeting is not None,
                           timeout=timeout)

    def test_the_right_psk_establishes_and_carries_a_job(self):
        job = base._job2("dtls-1")
        with tempfile.TemporaryDirectory() as td:
            pipe, channel, port = self._pipe(td)
            client, sock = self._client(port, SECRET)
            try:
                self.assertTrue(
                    self._handshake(pipe, client, sock))
                for dg in client.send_app(
                        _envelope_text(job).encode("utf-8")):
                    sock.send(dg)
                job_file = os.path.join(channel, "inbox",
                                        "dtls-1.job.txt")
                self.assertTrue(self._drive(
                    pipe, client, sock,
                    lambda: os.path.exists(job_file)))
            finally:
                sock.close()
                pipe.sock.close()

    def test_the_wrong_psk_never_establishes(self):
        wrong = base.WRONGSECRET
        with tempfile.TemporaryDirectory() as td:
            pipe, channel, port = self._pipe(td)
            client, sock = self._client(port, wrong)
            try:
                self.assertFalse(self._handshake(
                    pipe, client, sock, timeout=3.0))
                self.assertEqual(
                    os.listdir(os.path.join(channel, "inbox")),
                    ["done"])
            finally:
                sock.close()
                pipe.sock.close()

    def test_a_refusing_directory_blocks_the_right_psk(self):
        with tempfile.TemporaryDirectory() as td:
            pipe, channel, port = self._pipe(
                td, key_directory={"": {"state": "compromised"}})
            client, sock = self._client(port, SECRET)
            try:
                self.assertFalse(self._handshake(
                    pipe, client, sock, timeout=3.0))
            finally:
                sock.close()
                pipe.sock.close()


# ------------------------------------------------------------------
# Queues (clauses 1 and 3)
# ------------------------------------------------------------------

class _Resp:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class QueuesClientTest(unittest.TestCase):
    """The client sends its bearer token on every call, and a
    refusal at the edge is a failed pull, not an empty one."""

    def test_the_bearer_header_rides_the_pull(self):
        seen = []

        def opener(req, timeout=None):
            seen.append(req.get_header("Authorization"))
            return _Resp(200, b'{"jobs": []}')

        client = queues_ext.QueueClient(
            "https://q.example", "tok-123", opener=opener)
        self.assertEqual(client.pull(5), [])
        self.assertEqual(seen, ["Bearer tok-123"])

    def test_a_401_pull_raises(self):
        def opener(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 401, "unauthorized", {},
                io.BytesIO(b"denied"))

        client = queues_ext.QueueClient(
            "https://q.example", "tok-123", opener=opener)
        with self.assertRaises(RuntimeError) as cm:
            client.pull(5)
        self.assertIn("401", str(cm.exception))


class QueuesStartupTest(unittest.TestCase):
    """No runner token handed over, no start."""

    def test_no_url_no_start(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(_runtime_main(queues_ext, td, {}), 2)

    def test_no_token_no_start(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                _runtime_main(queues_ext, td,
                              {"url": "https://q.example"}), 2)


_HARNESS = r"""
import fs from "node:fs";
const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const worker = (await import("file://" + spec.worker)).default;
function makeEnv(cfg) {
  const calls = [];
  const stub = { fetch: async (req) => {
    calls.push(new URL(req.url).pathname + "|" +
               (req.headers.get("x-hp-job-id") || ""));
    return new Response(JSON.stringify({ ok: true }),
      { status: 200, headers: { "content-type": "application/json" } });
  } };
  const env = { TENANT: cfg.tenant,
                TENANT_QUEUE: { idFromName: (n) => n,
                                get: () => stub } };
  if (cfg.siToken) env.SI_TOKEN = cfg.siToken;
  if (cfg.runnerToken) env.RUNNER_TOKEN = cfg.runnerToken;
  if (cfg.hmacSecret) env.HMAC_SECRET = cfg.hmacSecret;
  return { env, calls };
}
const out = [];
for (const c of spec.cases) {
  const { env, calls } = makeEnv(spec.envs[c.env]);
  const headers = {};
  if (c.auth) headers["Authorization"] = "Bearer " + c.auth;
  const init = { method: c.method, headers };
  if (c.body != null) init.body = c.body;
  const resp = await worker.fetch(
    new Request("https://q" + c.path, init), env);
  out.push({ name: c.name, status: resp.status, calls });
}
console.log(JSON.stringify(out));
"""


class QueuesWorkerTest(unittest.TestCase):
    """The hosted Worker's own edge, driven under node: the
    SI's bearer token is checked first, the signature verdict
    second, and only then does the tenant queue see the job;
    the runner's pull takes the runner token, not the SI's;
    a tenant with no stored SI hash refuses everyone."""

    def test_the_worker_edge(self):
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("node is not installed")
        job = base._job2("wq-1")
        signed = runner.sign_payload(job, SECRET)
        envelope = "[HOMING-PIGEON] job wq-1\n\n" + signed
        unsigned = "[HOMING-PIGEON] job wq-1\n\n" + json.dumps(job)
        wrong = base.WRONGSECRET
        bad = "[HOMING-PIGEON] job wq-1\n\n" + runner.sign_payload(
            job, wrong)
        spec = {
            "worker": os.path.join(
                REPO, "runner", "cloud", "queues-worker", "src",
                "index.js"),
            "envs": {
                "main": {"tenant": "acme", "siToken": "si-tok",
                         "runnerToken": "run-tok",
                         "hmacSecret": SECRET},
                "noSi": {"tenant": "acme", "runnerToken": "run-tok",
                         "hmacSecret": SECRET},
            },
            "cases": [
                {"name": "no_auth", "env": "main", "method": "POST",
                 "path": "/t/acme/jobs", "auth": None,
                 "body": envelope},
                {"name": "wrong_si", "env": "main", "method": "POST",
                 "path": "/t/acme/jobs", "auth": "nope",
                 "body": envelope},
                {"name": "unsigned", "env": "main", "method": "POST",
                 "path": "/t/acme/jobs", "auth": "si-tok",
                 "body": unsigned},
                {"name": "bad_sig", "env": "main", "method": "POST",
                 "path": "/t/acme/jobs", "auth": "si-tok",
                 "body": bad},
                {"name": "valid", "env": "main", "method": "POST",
                 "path": "/t/acme/jobs", "auth": "si-tok",
                 "body": envelope},
                {"name": "pull_with_si", "env": "main",
                 "method": "GET", "path": "/t/acme/jobs",
                 "auth": "si-tok", "body": None},
                {"name": "pull_with_runner", "env": "main",
                 "method": "GET", "path": "/t/acme/jobs",
                 "auth": "run-tok", "body": None},
                {"name": "no_hash_fail_closed", "env": "noSi",
                 "method": "POST", "path": "/t/acme/jobs",
                 "auth": "anything", "body": envelope},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            harness = os.path.join(td, "harness.mjs")
            with open(harness, "w", encoding="utf-8") as fh:
                fh.write(_HARNESS)
            spec_path = os.path.join(td, "spec.json")
            with open(spec_path, "w", encoding="utf-8") as fh:
                json.dump(spec, fh)
            proc = subprocess.run(
                [node, harness, spec_path], capture_output=True,
                text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        results = {r["name"]: r
                   for r in json.loads(proc.stdout.strip())}
        self.assertEqual(results["no_auth"]["status"], 401)
        self.assertEqual(results["no_auth"]["calls"], [])
        self.assertEqual(results["wrong_si"]["status"], 401)
        self.assertEqual(results["wrong_si"]["calls"], [])
        self.assertEqual(results["unsigned"]["status"], 400)
        self.assertEqual(results["unsigned"]["calls"], [])
        self.assertEqual(results["bad_sig"]["status"], 403)
        self.assertEqual(results["bad_sig"]["calls"], [])
        self.assertEqual(results["valid"]["status"], 200)
        self.assertEqual(results["valid"]["calls"],
                         ["/enqueue|wq-1"])
        self.assertEqual(results["pull_with_si"]["status"], 401)
        self.assertEqual(results["pull_with_runner"]["status"], 200)
        self.assertEqual(results["pull_with_runner"]["calls"],
                         ["/pull|"])
        self.assertEqual(results["no_hash_fail_closed"]["status"],
                         401)
        self.assertEqual(results["no_hash_fail_closed"]["calls"],
                         [])


# ------------------------------------------------------------------
# Email (clause 4)
# ------------------------------------------------------------------

class EmailGateTest(base._GateCase):
    """Clause 4, both halves: the sender's address is not a
    gate -- a job from an unrelated address with a valid
    signature executes -- and the mailbox's own login is the
    transport's credential, enforced by the server at connect,
    not by anything in the core."""

    def test_an_arbitrary_sender_executes(self):
        job = base._job2("mail-1")
        raw = base._wire2(job).decode("utf-8").replace(
            "si@example.com", "mallory@unrelated.example").encode(
            "utf-8")
        out = base._run(raw=raw)
        self.assertEqual(len(out.executed), 1)

    def test_a_failed_mailbox_login_raises_at_connect(self):
        class BadIMAP:
            def __init__(self, host, port, ssl_context=None,
                         timeout=None):
                self.host = host

            def login(self, user, password):
                raise imaplib.IMAP4.error("login rejected")

        pw = "pw"
        cfg = {"mailbox_user": "u@example.com",
               "mailbox_password": pw,
               "imap_host": "imap.example.com"}
        with mock.patch.object(mailbox.imaplib, "IMAP4_SSL",
                               BadIMAP):
            with self.assertRaises(imaplib.IMAP4.error):
                mailbox.connect_imap(cfg)


if __name__ == "__main__":
    unittest.main()
