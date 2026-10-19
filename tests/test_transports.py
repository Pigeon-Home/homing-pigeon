#!/usr/bin/env python3
"""Tests for transport extensions (runner/transports.py).

Every transport -- email, file, NATS, and any drop-in -- is a
standalone extension program the runner supervises as a child
process; the core talks to it through a per-extension file
channel (job envelopes in, result envelopes out) and never
imports its code. These tests drive transports THROUGH that
contract: the file and NATS extensions run as real supervised
processes (the NATS broker is an in-process fake server), the
email extension is driven in-process with fake IMAP/SMTP behind
it, and the same verification/execution core the mail path has
always used does the work. No network beyond loopback, no
broker, no mailbox.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "cloud"))

from runner import transports  # noqa: E402
from runner.runner import (  # noqa: E402
    _transports_arg, apply_cli_overrides, poll_once)
from runner.transport_extensions.email import (  # noqa: E402
    __main__ as email_ext)
from runner.transport_extensions.file import (  # noqa: E402
    __main__ as file_ext)
from runner.transport_extensions.nats import (  # noqa: E402
    __main__ as nats_ext)
from send_job import sign_payload, verify_body  # noqa: E402

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"
SENDER = "runner@example.com"


def _cfg(tmp, **over):
    cfg = {
        "mailbox_user": SENDER,
        "mailbox_password": "test-gmail-password",
        "shared_secret": SECRET,
        "imap_host": "fake", "imap_port": 993,
        "smtp_host": "fake", "smtp_port": 587,
        "poll_interval_sec": 20,
        "max_job_age_sec": 3600,
        "max_output_bytes": 100000,
        "base_dir": tmp,
        "default_timeout_sec": 300,
    }
    cfg.update(over)
    return cfg


def _payload(job_id, **kw):
    p = {
        "v": 1, "type": "job", "job_id": job_id,
        "issued_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "kind": "ping",
    }
    p.update(kw)
    return p


def _envelope(job_id, secret=SECRET, **kw):
    body = sign_payload(_payload(job_id, **kw), secret)
    return transports.format_envelope(
        f"[HOMING-PIGEON] job {job_id}", body)


def _wait_for(pred, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.1)
    return pred()


class EnabledTransportsTest(unittest.TestCase):
    def test_default_is_email(self):
        self.assertEqual(transports.enabled_transports({}),
                         ["email"])

    def test_list_and_string_forms(self):
        self.assertEqual(
            transports.enabled_transports(
                {"transports": ["file", "nats"]}),
            ["file", "nats"])
        self.assertEqual(
            transports.enabled_transports(
                {"transports": "file, nats"}),
            ["file", "nats"])

    def test_dedupes_and_drops_blanks(self):
        self.assertEqual(
            transports.enabled_transports(
                {"transports": ["file", "", "file"]}),
            ["file"])

    def test_an_unregistered_name_is_a_valid_selection(self):
        # Names are extension names, not a fixed registry: an
        # owner can enable a drop-in nobody catalogued. Whether
        # it loads is discovery's question, not validation's.
        self.assertEqual(
            transports.enabled_transports(
                {"transports": ["smoke"]}),
            ["smoke"])

    def test_a_malformed_name_is_an_error(self):
        with self.assertRaises(ValueError) as cm:
            transports.enabled_transports(
                {"transports": ["bad name"]})
        self.assertIn("bad name", str(cm.exception))

    def test_empty_and_wrong_type_are_errors(self):
        with self.assertRaises(ValueError):
            transports.enabled_transports({"transports": []})
        with self.assertRaises(ValueError):
            transports.enabled_transports({"transports": 42})

    def test_poll_once_tolerates_a_name_with_no_extension(self):
        # A name with no loadable extension is logged by the
        # supervisor at startup; a poll cycle must not raise.
        tmp = tempfile.mkdtemp(prefix="hp-test-")
        cfg = _cfg(tmp, transports=["bogus"])
        poll_once(cfg, tmp, {}, os.path.join(tmp, "seen.json"))


class EnvelopeTest(unittest.TestCase):
    def test_round_trip(self):
        text = transports.format_envelope(
            "[HOMING-PIGEON] job abc", "body\nlines")
        self.assertEqual(transports.parse_envelope(text),
                         ("[HOMING-PIGEON] job abc", "body\nlines"))

    def test_crlf_is_normalized(self):
        self.assertEqual(
            transports.parse_envelope("subj\r\n\r\nbody"),
            ("subj", "body"))

    def test_no_blank_line_is_malformed(self):
        self.assertIsNone(transports.parse_envelope(
            "subject only, no body"))
        self.assertIsNone(transports.parse_envelope(None))


class CliTransportsTest(unittest.TestCase):
    def test_arg_parses_a_list(self):
        self.assertEqual(_transports_arg("file,nats"),
                         ["file", "nats"])
        self.assertEqual(_transports_arg(" email "), ["email"])

    def test_arg_accepts_a_drop_in_name(self):
        self.assertEqual(_transports_arg("file,smoke-signals"),
                         ["file", "smoke-signals"])

    def test_arg_rejects_a_malformed_name(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            _transports_arg("file,bad name")

    def test_override_lands_in_cfg(self):
        args = SimpleNamespace(
            **{dest: None for dest, _k
               in __import__("runner.runner", fromlist=["x"])
               ._CLI_OVERRIDES})
        args.transports = ["file"]
        cfg = {}
        applied = apply_cli_overrides(cfg, args)
        self.assertEqual(cfg["transports"], ["file"])
        self.assertIn("transports", applied)


class ManifestContractTest(unittest.TestCase):
    """The contract is versioned at one, manifests carry
    identity, and anything else is refused -- logged, never
    fatal."""

    def _drop(self, root, folder, manifest):
        path = os.path.join(root, folder)
        os.makedirs(path)
        with open(os.path.join(path, "extension.json"), "w",
                  encoding="utf-8") as f:
            json.dump(manifest, f)
        return path

    def _manifest(self, **over):
        m = {"name": "smoke", "kind": "transport",
             "api_version": 1, "version": "0.1.0",
             "publisher": "Test Harness",
             "entry": ["{python}", "-c", "pass"]}
        m.update(over)
        return m

    def test_api_version_is_one(self):
        self.assertEqual(transports.TRANSPORT_API_VERSION, 1)

    def test_first_party_manifests_declare_the_contract(self):
        registry, problems = \
            transports.discover_transport_extensions(
                {}, tempfile.mkdtemp(prefix="hp-test-"))
        self.assertEqual(problems, [])
        self.assertEqual(sorted(registry),
                         ["email", "file", "nats"])
        for name, manifest in registry.items():
            self.assertEqual(manifest["api_version"], 1, name)
            self.assertEqual(manifest["kind"], "transport", name)
            self.assertTrue(manifest["publisher"], name)
            self.assertTrue(manifest["entry"], name)

    def test_a_newer_api_version_is_refused_not_fatal(self):
        tmp = tempfile.mkdtemp(prefix="hp-test-")
        ext = os.path.join(tmp, "extensions")
        self._drop(ext, "future", self._manifest(
            name="future", api_version=2))
        registry, problems = \
            transports.discover_transport_extensions(
                {"extensions_dir": ext}, tmp)
        self.assertNotIn("future", registry)
        self.assertTrue(
            any("future" in p and "v2" in p for p in problems),
            problems)

    def test_a_zero_api_version_is_refused(self):
        tmp = tempfile.mkdtemp(prefix="hp-test-")
        ext = os.path.join(tmp, "extensions")
        self._drop(ext, "zero", self._manifest(
            name="zero", api_version=0))
        registry, problems = \
            transports.discover_transport_extensions(
                {"extensions_dir": ext}, tmp)
        self.assertNotIn("zero", registry)
        self.assertTrue(problems)

    def test_a_transport_manifest_needs_entry_and_publisher(self):
        tmp = tempfile.mkdtemp(prefix="hp-test-")
        ext = os.path.join(tmp, "extensions")
        self._drop(ext, "noentry", self._manifest(
            name="noentry", entry=None))
        self._drop(ext, "nopub", self._manifest(
            name="nopub", publisher=""))
        registry, problems = \
            transports.discover_transport_extensions(
                {"extensions_dir": ext}, tmp)
        self.assertNotIn("noentry", registry)
        self.assertNotIn("nopub", registry)
        self.assertGreaterEqual(len(problems), 2, problems)

    def test_a_drop_in_shadows_the_shipped_transport(self):
        tmp = tempfile.mkdtemp(prefix="hp-test-")
        ext = os.path.join(tmp, "extensions")
        mine = self._drop(ext, "myfile", self._manifest(
            name="file", publisher="The Owner"))
        registry, _problems = \
            transports.discover_transport_extensions(
                {"extensions_dir": ext}, tmp)
        self.assertEqual(registry["file"]["dir"], mine)
        self.assertEqual(registry["file"]["publisher"],
                         "The Owner")


class SupervisorTest(unittest.TestCase):
    """Supervision with a fake Popen: start, runtime config,
    restart-on-death with backoff, death isolation, stop."""

    class FakeProc:
        def __init__(self, argv, **kw):
            self.argv = argv
            self.pid = id(self) % 10000 + 1000
            self.dead = False
            self.code = None
            self.terminated = False

        def poll(self):
            return self.code if self.dead else None

        def terminate(self):
            self.terminated = True
            self.dead = True
            self.code = 0

        def kill(self):
            self.dead = True
            self.code = -9

        def wait(self, timeout=None):
            return self.code

    def _supervisor(self, tmp, cfg):
        self.procs = []

        def fake_popen(argv, **kw):
            proc = self.FakeProc(argv, **kw)
            self.procs.append(proc)
            return proc

        self.clock = [1000.0]
        sup = transports.TransportSupervisor(
            cfg, tmp, log=lambda m, level="INFO":
            self.lines.append((level, m)),
            popen=fake_popen, clock=lambda: self.clock[0])
        self.lines = []
        return sup

    def setUp(self):
        self.lines = []
        self.procs = []
        self.tmp = tempfile.mkdtemp(prefix="hp-test-")

    def test_starts_the_enabled_extensions_only(self):
        cfg = _cfg(self.tmp, transports=["file"])
        sup = self._supervisor(self.tmp, cfg)
        sup.start()
        self.assertEqual(len(self.procs), 1)
        self.assertIn("runner.transport_extensions.file",
                      " ".join(self.procs[0].argv))
        sup.stop()
        self.assertTrue(self.procs[0].terminated)

    def test_default_config_starts_email(self):
        # A fresh install behaves exactly as today: email is
        # enabled by default, as the default-enabled transport
        # extension.
        sup = self._supervisor(self.tmp, _cfg(self.tmp))
        sup.start()
        self.assertEqual(len(self.procs), 1)
        self.assertIn("runner.transport_extensions.email",
                      " ".join(self.procs[0].argv))
        sup.stop()

    def test_runtime_config_hands_over_only_the_extensions_own(
            self):
        cfg = _cfg(self.tmp, transports=["file"],
                   transport_file={"inbox": "in-x"})
        sup = self._supervisor(self.tmp, cfg)
        sup.start()
        paths = transports.channel_paths(self.tmp, "file")
        with open(os.path.join(paths["root"],
                               "runtime-config.json"),
                  encoding="utf-8") as f:
            handed = json.load(f)
        self.assertEqual(handed["inbox"], "in-x")
        self.assertEqual(handed["name"], "file")
        # The core's secret is never handed to a pipe.
        self.assertNotIn("shared_secret", handed)
        sup.stop()

    def test_email_runtime_config_carries_the_mailbox_keys(self):
        cfg = _cfg(self.tmp, transports=["email"])
        sup = self._supervisor(self.tmp, cfg)
        sup.start()
        paths = transports.channel_paths(self.tmp, "email")
        with open(os.path.join(paths["root"],
                               "runtime-config.json"),
                  encoding="utf-8") as f:
            handed = json.load(f)
        self.assertEqual(handed["mailbox_user"], SENDER)
        self.assertEqual(handed["mailbox_password"],
                         "test-gmail-password")
        self.assertNotIn("shared_secret", handed)
        sup.stop()

    def test_a_dead_extension_restarts_with_backoff(self):
        cfg = _cfg(self.tmp, transports=["file"])
        sup = self._supervisor(self.tmp, cfg)
        sup.start()
        first = self.procs[0]
        first.dead = True
        first.code = 1
        sup.check()   # notices the death, schedules a restart
        self.assertEqual(len(self.procs), 1)
        self.clock[0] += 0.5
        sup.check()   # backoff has not elapsed
        self.assertEqual(len(self.procs), 1)
        self.clock[0] += 1.0
        sup.check()   # restart fires
        self.assertEqual(len(self.procs), 2)
        warns = [m for level, m in self.lines if level == "WARN"]
        self.assertTrue(any("exited" in m for m in warns),
                        self.lines)
        sup.stop()

    def test_one_extensions_death_leaves_the_other_running(self):
        cfg = _cfg(self.tmp, transports=["file", "nats"],
                   transport_nats={"token": "tok"})
        sup = self._supervisor(self.tmp, cfg)
        sup.start()
        self.assertEqual(len(self.procs), 2)
        file_proc, nats_proc = self.procs
        file_proc.dead = True
        file_proc.code = 1
        sup.check()
        self.assertFalse(nats_proc.terminated)
        self.assertIsNone(nats_proc.poll())
        self.clock[0] += 2.0
        sup.check()
        self.assertEqual(len(self.procs), 3)  # file restarted
        self.assertFalse(nats_proc.terminated)
        sup.stop()

    def test_a_missing_extension_is_logged_not_fatal(self):
        cfg = _cfg(self.tmp, transports=["bogus"])
        sup = self._supervisor(self.tmp, cfg)
        sup.start()
        self.assertEqual(self.procs, [])
        errors = [m for level, m in self.lines if level == "ERROR"]
        self.assertTrue(any("bogus" in m for m in errors),
                        self.lines)
        sup.check()  # must not raise
        sup.stop()


class FileTransportExtensionTest(unittest.TestCase):
    """The file transport, driven through the contract: the
    extension process's pipe logic in-process here (its
    supervised-process form is covered end-to-end by
    SupervisedFileRoundTripTest), the core via poll_once."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-test-")
        self.cfg = _cfg(self.tmp, transports=["file"])
        self.seen = {}
        self.seen_path = os.path.join(self.tmp, "seen.json")
        self.paths = transports.channel_paths(self.tmp, "file")
        transports.ensure_channel_dirs(self.tmp, "file")
        self.pipe = file_ext.FilePipe(
            {"base_dir": self.tmp,
             "inbox": "transport-file/inbox",
             "outbox": "transport-file/outbox"},
            self.paths["root"])
        self.inbox, self.outbox = self.pipe.inbox, self.pipe.outbox

    def _drop(self, name, text):
        with open(os.path.join(self.inbox, name), "w",
                  encoding="utf-8") as f:
            f.write(text)

    def _cycle(self):
        self.pipe.scan_jobs()
        poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        self.pipe.scan_results()

    def _results(self):
        return sorted(os.listdir(self.outbox))

    def test_ping_round_trip(self):
        jid = str(uuid.uuid4())
        self._drop("job.txt", _envelope(jid))
        self._cycle()
        results = self._results()
        self.assertEqual(results, [f"{jid}.result.txt"])
        with open(os.path.join(self.outbox, results[0]),
                  encoding="utf-8") as f:
            subject, body = transports.parse_envelope(f.read())
        self.assertIn("result", subject)
        result = verify_body(body, SECRET)
        self.assertEqual(result["stdout"], "pong")
        # Processed exactly once: the job file moved to done/.
        self.assertEqual(os.listdir(self.inbox), ["done"])
        self.assertIn(
            "job.txt",
            os.listdir(os.path.join(self.inbox, "done")))

    def test_exec_round_trip(self):
        jid = str(uuid.uuid4())
        self._drop("job.txt", _envelope(
            jid, kind="exec", script="echo hello-from-file",
            interpreter=["sh"]))
        self._cycle()
        with open(os.path.join(self.outbox, f"{jid}.result.txt"),
                  encoding="utf-8") as f:
            _subject, body = transports.parse_envelope(f.read())
        result = verify_body(body, SECRET)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello-from-file", result["stdout"])

    def test_process_once_across_cycles(self):
        jid = str(uuid.uuid4())
        self._drop("job.txt", _envelope(jid))
        self._cycle()
        self._cycle()
        self.assertEqual(self._results(), [f"{jid}.result.txt"])

    def test_a_redelivered_copy_is_not_reexecuted(self):
        jid = str(uuid.uuid4())
        env = _envelope(jid)
        self._drop("job.txt", env)
        self._cycle()
        self._drop("job.txt", env)  # the same file again
        self._cycle()
        self.assertEqual(self._results(), [f"{jid}.result.txt"])

    def test_tampered_signature_is_rejected(self):
        jid = str(uuid.uuid4())
        env = _envelope(jid, kind="exec",
                        script="echo should-not-run",
                        interpreter=["sh"])
        env = env.replace("should-not-run", "tampered-body---")
        self._drop("job.txt", env)
        self._cycle()
        self.assertEqual(self._results(), [])
        # Still consumed (process-once), and nothing executed.
        self.assertIn(
            "job.txt",
            os.listdir(os.path.join(self.inbox, "done")))

    def test_symlink_is_refused_unread(self):
        target = os.path.join(self.tmp, "elsewhere.txt")
        jid = str(uuid.uuid4())
        with open(target, "w", encoding="utf-8") as f:
            f.write(_envelope(jid))
        os.symlink(target, os.path.join(self.inbox, "link.txt"))
        self._cycle()
        self.assertEqual(self._results(), [])
        done = os.path.join(self.inbox, "done", "link.txt")
        self.assertTrue(os.path.islink(done))
        self.assertTrue(os.path.exists(
            done + ".refused.txt"))

    def test_oversize_is_refused_unread(self):
        path = os.path.join(self.inbox, "big.txt")
        with open(path, "wb") as f:
            f.write(b"x" * (transports.FILE_MAX_BYTES + 1))
        self._cycle()
        self.assertEqual(self._results(), [])
        self.assertTrue(os.path.exists(
            os.path.join(self.inbox, "done", "big.txt")))

    def test_malformed_envelope_is_consumed_quietly(self):
        self._drop("junk.txt", "no blank line in this file")
        self._cycle()
        self.assertEqual(self._results(), [])
        self.assertIn(
            "junk.txt",
            os.listdir(os.path.join(self.inbox, "done")))

    def test_email_only_default_ignores_the_watched_inbox(self):
        cfg = _cfg(self.tmp)  # no transports key: email only
        jid = str(uuid.uuid4())
        self._drop("job.txt", _envelope(jid))
        from tests.test_runner import FakeIMAP, FakeSMTP
        poll_once(cfg, self.tmp, {}, self.seen_path,
                  imap=FakeIMAP([]), smtp=FakeSMTP())
        # The core never touches the watched folder when the
        # file transport is not enabled: the job file sits
        # exactly where it was dropped, unconsumed.
        self.assertIn("job.txt", os.listdir(self.inbox))
        self.assertEqual(
            os.listdir(os.path.join(self.inbox, "done")), [])
        self.assertEqual(self._results(), [])


class SupervisedFileRoundTripTest(unittest.TestCase):
    """End to end with real processes: the supervisor starts
    the file transport extension, a job dropped in the watched
    folder is executed by the core, and the signed result lands
    in the watched outbox."""

    def test_supervised_round_trip(self):
        tmp = tempfile.mkdtemp(prefix="hp-test-")
        cfg = _cfg(tmp, transports=["file"])
        seen_path = os.path.join(tmp, "seen.json")
        inbox = os.path.join(tmp, "transport-file", "inbox")
        outbox = os.path.join(tmp, "transport-file", "outbox")
        os.makedirs(inbox)
        jid = str(uuid.uuid4())
        with open(os.path.join(inbox, "job.txt"), "w",
                  encoding="utf-8") as f:
            f.write(_envelope(
                jid, kind="exec", script="echo hello-supervised",
                interpreter=["sh"]))
        transports.start_supervisor(cfg, tmp)
        try:
            result_path = os.path.join(
                outbox, f"{jid}.result.txt")

            def cycle():
                poll_once(cfg, tmp, {}, seen_path)
                return os.path.exists(result_path)

            self.assertTrue(_wait_for(cycle, timeout=30),
                            "no result from the supervised "
                            "file extension")
            with open(result_path, encoding="utf-8") as f:
                _s, body = transports.parse_envelope(f.read())
            result = verify_body(body, SECRET)
            self.assertEqual(result["exit_code"], 0)
            self.assertIn("hello-supervised", result["stdout"])
        finally:
            transports.stop_supervisors(tmp)


class FakeNatsServer(threading.Thread):
    """Just enough core NATS: INFO, CONNECT capture, PING/PONG,
    SUB then deliver, PUB capture. One connection, then it
    waits for the client to close."""

    def __init__(self, deliveries):
        super().__init__(daemon=True)
        self.deliveries = deliveries  # envelope texts
        self.connect_opts = None
        self.published = []           # (subject, payload bytes)
        self.error = None
        self.sock = socket.socket(socket.AF_INET,
                                  socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET,
                             socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]

    def run(self):
        try:
            conn, _ = self.sock.accept()
            conn.settimeout(30)
            f = conn.makefile("rb")
            conn.sendall(
                b'INFO {"server_id":"fake","version":"2.0.0",'
                b'"max_payload":1048576}\r\n')
            while True:
                line = f.readline()
                if not line:
                    break
                line = line.decode("utf-8", "replace").strip()
                if line.startswith("CONNECT "):
                    self.connect_opts = json.loads(line[8:])
                elif line == "PING":
                    conn.sendall(b"PONG\r\n")
                elif line.startswith("SUB "):
                    parts = line.split(" ")
                    subject, sid = parts[1], parts[2]
                    for text in self.deliveries:
                        payload = text.encode("utf-8")
                        conn.sendall(
                            f"MSG {subject} {sid} "
                            f"{len(payload)}\r\n".encode()
                            + payload + b"\r\n")
                elif line.startswith("PUB "):
                    parts = line.split(" ")
                    size = int(parts[-1])
                    payload = f.read(size)
                    f.read(2)
                    self.published.append((parts[1], payload))
                elif line in ("PONG",) or line.startswith("UNSUB"):
                    pass
            conn.close()
        except Exception as e:  # noqa: BLE001 - recorded for asserts
            self.error = e
        finally:
            self.sock.close()


class NatsTransportExtensionTest(unittest.TestCase):
    """The NATS extension through the contract: the pipe runs
    its persistent loop in a thread against the fake broker,
    the core services the channel via poll_once."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-test-")
        self.seen = {}
        self.seen_path = os.path.join(self.tmp, "seen.json")
        self.paths = transports.channel_paths(self.tmp, "nats")
        transports.ensure_channel_dirs(self.tmp, "nats")

    def _run(self, deliveries, nats_block, expect_publish=True):
        server = FakeNatsServer(deliveries)
        server.start()
        block = dict(nats_block)
        block.setdefault(
            "url", f"nats://127.0.0.1:{server.port}")
        cfg = _cfg(self.tmp, transports=["nats"],
                   transport_nats=block)
        pipe = nats_ext.NatsPipe(block, self.paths["root"])
        thread = threading.Thread(target=pipe.run, daemon=True)
        thread.start()
        try:
            def cycle():
                poll_once(cfg, self.tmp, self.seen,
                          self.seen_path)
                if len(server.published) >= 1:
                    return True
                if not expect_publish:
                    done = os.listdir(self.paths["inbox_done"])
                    return bool(done)
                return False

            _wait_for(cycle, timeout=25)
            if not expect_publish:
                # The job was processed; give the pipe a window
                # in which a (wrong) publish would land.
                time.sleep(1.5)
        finally:
            pipe.stop()
            thread.join(timeout=10)
            server.join(timeout=10)
        self.assertIsNone(server.error)
        return server

    def test_ping_round_trip_with_user_pass(self):
        jid = str(uuid.uuid4())
        server = self._run(
            [_envelope(jid)],
            {"user": "runner", "password": "s3cret"})
        self.assertEqual(server.connect_opts["user"], "runner")
        self.assertEqual(server.connect_opts["pass"], "s3cret")
        self.assertEqual(len(server.published), 1)
        subject, payload = server.published[0]
        self.assertEqual(subject, f"homing-pigeon.results.{jid}")
        _s, body = transports.parse_envelope(
            payload.decode("utf-8"))
        result = verify_body(body, SECRET)
        self.assertEqual(result["stdout"], "pong")

    def test_exec_round_trip_with_token(self):
        jid = str(uuid.uuid4())
        server = self._run(
            [_envelope(jid, kind="exec",
                       script="echo hello-from-nats",
                       interpreter=["sh"])],
            {"token": "tok-123"})
        self.assertEqual(server.connect_opts["auth_token"],
                         "tok-123")
        self.assertEqual(len(server.published), 1)
        _subject, payload = server.published[0]
        _s, body = transports.parse_envelope(
            payload.decode("utf-8"))
        result = verify_body(body, SECRET)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello-from-nats", result["stdout"])

    def test_url_userinfo_credentials(self):
        jid = str(uuid.uuid4())
        server = FakeNatsServer([_envelope(jid)])
        server.start()
        block = {"url": f"nats://u2:p2@127.0.0.1:{server.port}"}
        cfg = _cfg(self.tmp, transports=["nats"],
                   transport_nats=block)
        pipe = nats_ext.NatsPipe(block, self.paths["root"])
        thread = threading.Thread(target=pipe.run, daemon=True)
        thread.start()
        try:
            def cycle():
                poll_once(cfg, self.tmp, self.seen,
                          self.seen_path)
                return len(server.published) >= 1

            _wait_for(cycle, timeout=25)
        finally:
            pipe.stop()
            thread.join(timeout=10)
            server.join(timeout=10)
        self.assertEqual(server.connect_opts["user"], "u2")
        self.assertEqual(server.connect_opts["pass"], "p2")
        self.assertEqual(len(server.published), 1)

    def test_tampered_signature_gets_no_result(self):
        jid = str(uuid.uuid4())
        env = _envelope(jid, kind="exec",
                        script="echo should-not-run",
                        interpreter=["sh"])
        env = env.replace("should-not-run", "tampered-body---")
        server = self._run([env], {"token": "tok-123"},
                           expect_publish=False)
        self.assertEqual(server.published, [])

    def test_refuses_to_start_without_credentials(self):
        with self.assertRaises(nats_ext.TransportError):
            nats_ext.NatsPipe({}, self.paths["root"])
        with self.assertRaises(nats_ext.TransportError):
            nats_ext.NatsPipe({"allow_unauthenticated": 1},
                              self.paths["root"])

    def test_the_extension_process_refuses_without_credentials(
            self):
        # The two-gate rule through the actual extension
        # process the supervisor would start: no credentials and
        # no override -> a clear refusal and a nonzero exit,
        # never a silent unauthenticated start.
        cfg_path = os.path.join(self.paths["root"],
                                "runtime-config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"url": "nats://127.0.0.1:4222"}, f)
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO + os.pathsep + env.get(
            "PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, "-m",
             "runner.transport_extensions.nats",
             self.paths["root"], cfg_path],
            capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("refuses to start", proc.stderr)

    def test_unauthenticated_override_is_logged_as_warn(self):
        lines = []
        nats_ext.NatsPipe(
            {"allow_unauthenticated": True}, self.paths["root"],
            log=lambda m, level="INFO": lines.append((level, m)))
        warns = [m for level, m in lines if level == "WARN"]
        self.assertTrue(any("ONLY" in m for m in warns), lines)

    def test_two_gates_notice_names_both_without_secrets(self):
        lines = []
        nats_ext.NatsPipe(
            {"user": "u", "password": "p"}, self.paths["root"],
            log=lambda m, level="INFO": lines.append((level, m)))
        infos = [m for level, m in lines if level == "INFO"]
        self.assertTrue(
            any("two authorization gates" in m for m in infos),
            lines)
        self.assertFalse(any("p" == m for _l, m in lines))

    def test_config_credentials_win_over_url_userinfo(self):
        client = nats_ext.NatsClient(
            "nats://urluser:urlpass@127.0.0.1:4222",
            token="cfg-token")
        self.assertEqual(client._connect_opts["auth_token"],
                         "cfg-token")
        self.assertNotIn("user", client._connect_opts)
        client = nats_ext.NatsClient(
            "nats://urltoken@127.0.0.1:4222",
            user="cfguser", password="cfgpass")
        self.assertEqual(client._connect_opts["user"], "cfguser")
        self.assertEqual(client._connect_opts["pass"], "cfgpass")
        self.assertNotIn("auth_token", client._connect_opts)


class EmailTransportExtensionTest(unittest.TestCase):
    """The email extension with fake IMAP/SMTP behind it: the
    pipe fetches, the core (via the channel) executes, the pipe
    sends the result and marks the message seen."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-test-")
        self.cfg = _cfg(self.tmp, transports=["email"])
        self.seen = {}
        self.seen_path = os.path.join(self.tmp, "seen.json")
        self.paths = transports.channel_paths(self.tmp, "email")
        transports.ensure_channel_dirs(self.tmp, "email")
        from tests.test_runner import FakeIMAP, FakeSMTP
        self.FakeIMAP = FakeIMAP
        self.FakeSMTP = FakeSMTP

    def _raw_mail(self, job_id, **kw):
        body = sign_payload(_payload(job_id, **kw), SECRET)
        raw = (f"Subject: [HOMING-PIGEON] job {job_id}\r\n"
               f"From: someone@example.com\r\n"
               f'Content-Type: text/plain; charset="utf-8"\r\n'
               f"\r\n{body}").encode("utf-8")
        return raw

    def _pipe(self, imap, smtp):
        return email_ext.EmailPipe(
            self.cfg, self.paths["root"],
            imap_factory=lambda cfg: imap,
            smtp_factory=lambda cfg: smtp)

    def test_round_trip_marks_seen_after_the_result_is_sent(
            self):
        jid = str(uuid.uuid4())
        imap = self.FakeIMAP([self._raw_mail(jid)])
        smtp = self.FakeSMTP()
        pipe = self._pipe(imap, smtp)
        pipe.pass_once()
        # Delivered to the channel, not yet seen: the result
        # has not been sent yet.
        self.assertEqual(imap.flagged, [])
        poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        pipe.pass_once()
        self.assertEqual(len(smtp.sent), 1)
        msg = smtp.sent[0]
        self.assertIn("result", str(msg["Subject"]))
        self.assertEqual(str(msg["To"]), SENDER)
        body = msg.get_content()
        result = verify_body(body, SECRET)
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(imap.flagged, ["1"])

    def test_reply_to_routes_the_result(self):
        jid = str(uuid.uuid4())
        imap = self.FakeIMAP([self._raw_mail(
            jid, reply_to="ops@example.com")])
        smtp = self.FakeSMTP()
        pipe = self._pipe(imap, smtp)
        pipe.pass_once()
        poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        pipe.pass_once()
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(str(smtp.sent[0]["To"]),
                         "ops@example.com")

    def test_a_restart_does_not_redeliver_a_finished_job(self):
        jid = str(uuid.uuid4())
        imap = self.FakeIMAP([self._raw_mail(jid)])
        smtp = self.FakeSMTP()
        pipe = self._pipe(imap, smtp)
        pipe.pass_once()
        poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        pipe.pass_once()
        self.assertEqual(len(smtp.sent), 1)
        # A fresh pipe (a restarted extension) seeing the same
        # still-unseen message: the channel's done/ says the job
        # was already carried, so it is only marked seen.
        imap2 = self.FakeIMAP([self._raw_mail(jid)])
        smtp2 = self.FakeSMTP()
        pipe2 = self._pipe(imap2, smtp2)
        pipe2.pass_once()
        self.assertEqual(smtp2.sent, [])
        self.assertEqual(imap2.flagged, ["1"])


class MultipleTransportsTest(unittest.TestCase):
    def test_file_and_nats_in_one_supervised_run(self):
        tmp = tempfile.mkdtemp(prefix="hp-test-")
        file_jid = str(uuid.uuid4())
        nats_jid = str(uuid.uuid4())
        server = FakeNatsServer([_envelope(nats_jid)])
        server.start()
        cfg = _cfg(
            tmp, transports=["file", "nats"],
            transport_nats={
                "url": f"nats://127.0.0.1:{server.port}",
                "token": "tok"})
        inbox = os.path.join(tmp, "transport-file", "inbox")
        outbox = os.path.join(tmp, "transport-file", "outbox")
        os.makedirs(inbox)
        with open(os.path.join(inbox, "job.txt"), "w",
                  encoding="utf-8") as f:
            f.write(_envelope(file_jid))
        seen_path = os.path.join(tmp, "seen.json")
        transports.start_supervisor(cfg, tmp)
        try:
            result_path = os.path.join(
                outbox, f"{file_jid}.result.txt")

            def cycle():
                poll_once(cfg, tmp, {}, seen_path)
                return os.path.exists(result_path) \
                    and len(server.published) >= 1

            self.assertTrue(_wait_for(cycle, timeout=30),
                            "both transports should deliver in "
                            "one supervised run")
            subject, _payload_bytes = server.published[0]
            self.assertEqual(
                subject, f"homing-pigeon.results.{nats_jid}")
        finally:
            transports.stop_supervisors(tmp)
            server.join(timeout=10)


class UnregisteredDropInTest(unittest.TestCase):
    """Andrew's requirement: an owner can drop a transport
    extension into the local extensions folder -- a test
    transport, a private experiment, a pipe nobody catalogued
    -- and the runner loads and uses it with NO registry or
    catalog check of any kind. Registration is for discovery
    and future lockdown pinning; it is never a permission to
    run."""

    SCRIPT = '''
import json
import os
import sys
import time

channel, cfg_path = sys.argv[1], sys.argv[2]
with open(cfg_path, encoding="utf-8") as f:
    cfg = json.load(f)
inbox = os.path.join(channel, "inbox")
outbox = os.path.join(channel, "outbox")
os.makedirs(os.path.join(inbox, "done"), exist_ok=True)
os.makedirs(os.path.join(outbox, "done"), exist_ok=True)
delivered = False
deadline = time.time() + 120
while time.time() < deadline:
    if not delivered and os.path.exists(cfg["job_file"]):
        with open(cfg["job_file"], encoding="utf-8") as f:
            text = f.read()
        tmp = os.path.join(inbox, "dropin.job.txt.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, os.path.join(inbox, "dropin.job.txt"))
        delivered = True
    for name in sorted(os.listdir(outbox)):
        if name == "done" or not name.endswith(".result.txt"):
            continue
        with open(os.path.join(outbox, name),
                  encoding="utf-8") as f:
            text = f.read()
        with open(cfg["got_file"], "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(os.path.join(outbox, name),
                   os.path.join(outbox, "done", name))
    time.sleep(0.1)
'''

    def test_an_unregistered_drop_in_carries_a_job_end_to_end(
            self):
        tmp = tempfile.mkdtemp(prefix="hp-test-")
        ext_root = os.path.join(tmp, "extensions")
        folder = os.path.join(ext_root, "smoke-pipe")
        os.makedirs(folder)
        with open(os.path.join(folder, "smoke.py"), "w",
                  encoding="utf-8") as f:
            f.write(self.SCRIPT)
        manifest = {
            "name": "smoke", "kind": "transport",
            "api_version": 1, "version": "0.0.1",
            "publisher": "A. Owner, testing locally",
            "entry": ["{python}",
                      os.path.join(folder, "smoke.py"),
                      "{channel_dir}", "{runtime_config}"],
        }
        with open(os.path.join(folder, "extension.json"), "w",
                  encoding="utf-8") as f:
            json.dump(manifest, f)
        job_file = os.path.join(tmp, "job-envelope.txt")
        got_file = os.path.join(tmp, "got-result.txt")
        jid = str(uuid.uuid4())
        with open(job_file, "w", encoding="utf-8") as f:
            f.write(_envelope(
                jid, kind="exec", script="echo hello-drop-in",
                interpreter=["sh"]))
        cfg = _cfg(tmp, transports=["smoke"],
                   extensions_dir=ext_root,
                   transport_smoke={"job_file": job_file,
                                    "got_file": got_file})
        # No registry anywhere names "smoke": discovery works
        # from the manifest alone.
        registry, problems = \
            transports.discover_transport_extensions(cfg, tmp)
        self.assertIn("smoke", registry, problems)
        seen_path = os.path.join(tmp, "seen.json")
        transports.start_supervisor(cfg, tmp)
        try:
            def cycle():
                poll_once(cfg, tmp, {}, seen_path)
                return os.path.exists(got_file)

            self.assertTrue(_wait_for(cycle, timeout=30),
                            "the drop-in extension never "
                            "carried the job")
            with open(got_file, encoding="utf-8") as f:
                _s, body = transports.parse_envelope(f.read())
            result = verify_body(body, SECRET)
            self.assertEqual(result["exit_code"], 0)
            self.assertIn("hello-drop-in", result["stdout"])
        finally:
            transports.stop_supervisors(tmp)


class OldConfigCompatTest(unittest.TestCase):
    """A config.json written for 3.9.0 keeps working unchanged:
    the mailbox keys and the transport_file / transport_nats
    blocks are handed to the owning extensions by the runner;
    nothing needs editing."""

    def test_a_390_shaped_config_file_drives_the_file_pipe(self):
        tmp = tempfile.mkdtemp(prefix="hp-test-")
        old_config = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "imap_host": "imap.example.com", "imap_port": 993,
            "smtp_host": "smtp.example.com", "smtp_port": 587,
            "shared_secret": SECRET,
            "poll_interval_sec": 20,
            "transports": ["file"],
            "transport_file": {"inbox": "transport-file/inbox",
                               "outbox": "transport-file/outbox"},
            "transport_nats": {"url": "nats://127.0.0.1:4222",
                               "token": "tok"},
        }
        cfg_path = os.path.join(tmp, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(old_config, f)
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["base_dir"] = tmp
        # The old keys select and configure the extensions.
        self.assertEqual(transports.enabled_transports(cfg),
                         ["file"])
        paths = transports.channel_paths(tmp, "file")
        pipe = file_ext.FilePipe(
            transports._runtime_config(cfg, "file", tmp, paths),
            paths["root"])
        inbox = os.path.join(tmp, "transport-file", "inbox")
        jid = str(uuid.uuid4())
        with open(os.path.join(inbox, "job.txt"), "w",
                  encoding="utf-8") as f:
            f.write(_envelope(jid))
        pipe.scan_jobs()
        poll_once(cfg, tmp, {}, os.path.join(tmp, "seen.json"))
        pipe.scan_results()
        result_path = os.path.join(
            tmp, "transport-file", "outbox",
            f"{jid}.result.txt")
        self.assertTrue(os.path.exists(result_path))
        # And the mailbox keys reach the email extension whole.
        handed = transports._runtime_config(
            cfg, "email", tmp,
            transports.channel_paths(tmp, "email"))
        self.assertEqual(handed["imap_host"], "imap.example.com")
        self.assertEqual(handed["mailbox_user"], SENDER)


if __name__ == "__main__":
    unittest.main()
