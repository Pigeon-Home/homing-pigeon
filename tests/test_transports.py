#!/usr/bin/env python3
"""Tests for the job-transport seam (runner/transports.py).

Drives file and NATS transports through the real poll_once and
the real verification/execution core -- the same core the mail
path uses -- against a watched temp folder and an in-process
fake NATS server. No network beyond loopback, no broker.
"""

import argparse
import json
import os
import socket
import sys
import tempfile
import threading
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

    def test_unknown_name_is_an_error(self):
        with self.assertRaises(ValueError) as cm:
            transports.enabled_transports({"transports": ["smoke"]})
        self.assertIn("smoke", str(cm.exception))

    def test_empty_and_wrong_type_are_errors(self):
        with self.assertRaises(ValueError):
            transports.enabled_transports({"transports": []})
        with self.assertRaises(ValueError):
            transports.enabled_transports({"transports": 42})

    def test_poll_once_rejects_an_unknown_transport(self):
        tmp = tempfile.mkdtemp(prefix="hp-test-")
        cfg = _cfg(tmp, transports=["bogus"])
        with self.assertRaises(ValueError):
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

    def test_arg_rejects_a_bad_name(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            _transports_arg("file,smoke-signals")

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


class FileTransportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-test-")
        self.cfg = _cfg(self.tmp, transports=["file"])
        self.seen = {}
        self.seen_path = os.path.join(self.tmp, "seen.json")
        t = transports.FileTransport(self.cfg, self.tmp)
        self.inbox, self.outbox = t.inbox_dir, t.outbox_dir
        os.makedirs(self.inbox)
        os.makedirs(self.outbox)

    def _drop(self, name, text):
        with open(os.path.join(self.inbox, name), "w",
                  encoding="utf-8") as f:
            f.write(text)

    def _cycle(self):
        poll_once(self.cfg, self.tmp, self.seen, self.seen_path)

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
        self.assertEqual(
            os.listdir(os.path.join(self.inbox, "done")),
            ["job.txt"])

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
        self.assertEqual(
            os.listdir(os.path.join(self.inbox, "done")),
            ["job.txt"])

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
        self.assertEqual(
            os.listdir(os.path.join(self.inbox, "done")),
            ["junk.txt"])

    def test_email_only_default_ignores_the_inbox(self):
        cfg = _cfg(self.tmp)  # no transports key: email only
        jid = str(uuid.uuid4())
        self._drop("job.txt", _envelope(jid))
        from tests.test_runner import FakeIMAP, FakeSMTP
        poll_once(cfg, self.tmp, {}, self.seen_path,
                  imap=FakeIMAP([]), smtp=FakeSMTP())
        self.assertEqual(os.listdir(self.inbox), ["job.txt"])
        self.assertEqual(self._results(), [])


class FakeNatsServer(threading.Thread):
    """Just enough core NATS: INFO, CONNECT capture, PING/PONG,
    SUB then deliver, PUB capture."""

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
        self.sock.listen(1)
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


class NatsTransportTest(unittest.TestCase):
    def setUp(self):
        transports._NOTICE_LOGGED.clear()
        self._drain = transports.NatsTransport.drain_idle_sec
        transports.NatsTransport.drain_idle_sec = 0.3
        self.tmp = tempfile.mkdtemp(prefix="hp-test-")
        self.seen = {}
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def tearDown(self):
        transports.NatsTransport.drain_idle_sec = self._drain

    def _run(self, deliveries, nats_block):
        server = FakeNatsServer(deliveries)
        server.start()
        block = dict(nats_block)
        block.setdefault(
            "url", f"nats://127.0.0.1:{server.port}")
        cfg = _cfg(self.tmp, transports=["nats"],
                   transport_nats=block)
        poll_once(cfg, self.tmp, self.seen, self.seen_path)
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
        cfg = _cfg(
            self.tmp, transports=["nats"],
            transport_nats={
                "url": f"nats://u2:p2@127.0.0.1:{server.port}"})
        poll_once(cfg, self.tmp, self.seen, self.seen_path)
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
        server = self._run([env], {"token": "tok-123"})
        self.assertEqual(server.published, [])

    def test_refuses_to_start_without_credentials(self):
        with self.assertRaises(transports.TransportError):
            transports.build_transport(
                "nats", {"transport_nats": {}}, self.tmp)
        with self.assertRaises(transports.TransportError):
            transports.build_transport(
                "nats",
                {"transport_nats": {"allow_unauthenticated": 1}},
                self.tmp)

    def test_unauthenticated_override_is_logged_as_warn(self):
        jid = str(uuid.uuid4())
        lines = []
        server = FakeNatsServer([_envelope(jid)])
        server.start()
        cfg = _cfg(
            self.tmp, transports=["nats"],
            transport_nats={
                "url": f"nats://127.0.0.1:{server.port}",
                "allow_unauthenticated": True})
        # Drive the transport directly to capture its log lines.
        t = transports.build_transport(
            "nats", cfg, self.tmp,
            log=lambda m, level="INFO": lines.append((level, m)))
        t.close()
        poll_once(cfg, self.tmp, self.seen, self.seen_path)
        server.join(timeout=10)
        warns = [m for level, m in lines if level == "WARN"]
        self.assertTrue(any("ONLY" in m for m in warns), lines)
        self.assertEqual(len(server.published), 1)

    def test_two_gates_notice_names_both_without_secrets(self):
        lines = []
        transports.build_transport(
            "nats",
            {"transport_nats": {"user": "u", "password": "p"}},
            self.tmp,
            log=lambda m, level="INFO": lines.append((level, m)))
        infos = [m for level, m in lines if level == "INFO"]
        self.assertTrue(
            any("two authorization gates" in m for m in infos),
            lines)

    def test_config_credentials_win_over_url_userinfo(self):
        client = transports.NatsClient(
            "nats://urluser:urlpass@127.0.0.1:4222",
            token="cfg-token")
        self.assertEqual(client._connect_opts["auth_token"],
                         "cfg-token")
        self.assertNotIn("user", client._connect_opts)
        client = transports.NatsClient(
            "nats://urltoken@127.0.0.1:4222",
            user="cfguser", password="cfgpass")
        self.assertEqual(client._connect_opts["user"], "cfguser")
        self.assertEqual(client._connect_opts["pass"], "cfgpass")
        self.assertNotIn("auth_token", client._connect_opts)


class MultipleTransportsTest(unittest.TestCase):
    def test_file_and_nats_in_one_cycle(self):
        transports._NOTICE_LOGGED.clear()
        drain = transports.NatsTransport.drain_idle_sec
        transports.NatsTransport.drain_idle_sec = 0.3
        try:
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
            t = transports.FileTransport(cfg, tmp)
            os.makedirs(t.inbox_dir)
            with open(os.path.join(t.inbox_dir, "job.txt"), "w",
                      encoding="utf-8") as f:
                f.write(_envelope(file_jid))
            poll_once(cfg, tmp, {}, os.path.join(tmp, "seen.json"))
            server.join(timeout=10)
            self.assertTrue(os.path.exists(os.path.join(
                t.outbox_dir, f"{file_jid}.result.txt")))
            self.assertEqual(len(server.published), 1)
            subject, _payload_bytes = server.published[0]
            self.assertEqual(
                subject, f"homing-pigeon.results.{nats_jid}")
        finally:
            transports.NatsTransport.drain_idle_sec = drain


if __name__ == "__main__":
    unittest.main()
