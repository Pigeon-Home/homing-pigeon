#!/usr/bin/env python3
"""Tests for transport extensions (runner/wire/transports.py).

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
import imaplib
import json
import os
import smtplib
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

from runner.wire import jobcrypto, mailbox, transports  # noqa: E402
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
    payload = _payload(job_id, **kw)
    # Jobs travel encrypted since the HMAC-only form was
    # removed: sign, encrypt, sign the envelope. The wire body
    # is the envelope whatever container carries it (channel
    # file, NATS message, drop-in pipe).
    body = jobcrypto.encrypt_body(
        sign_payload(payload, secret), secret, job_id=job_id,
        key_id=payload.get("key_id") or "", sign=sign_payload)
    return transports.format_envelope(
        f"[HOMING-PIGEON] job {job_id}", body)


def _read_result(body, job_id, secret=SECRET):
    """Verify a result body, unwrapping the hp_enc envelope
    the result mirrors from its (encrypted) job."""
    result = verify_body(body, secret)
    if jobcrypto.is_envelope(result):
        inner = jobcrypto.decrypt_body(
            result, secret, job_id, result.get("key_id") or "")
        result = verify_body(inner, secret)
    return result


def _tamper_envelope(env):
    """Flip the last hex digit of the envelope's signature:
    a tampered signature, rejected exactly as before."""
    return env[:-3] + ("0" if env[-3] != "0" else "1") + env[-2:]


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


class ChannelResultTargetTest(unittest.TestCase):
    """write_channel_result's target sidecar: the core hands a
    pipe the job's validated reply_to as <ident>.target.txt
    beside the result file, and only that -- no target (or an
    empty one) writes no sidecar."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-test-")
        self.paths = transports.channel_paths(self.tmp, "email")
        transports.ensure_channel_dirs(self.tmp, "email")

    def _drop(self, **kw):
        return transports.write_channel_result(
            self.tmp, "email", "[HOMING-PIGEON] job abc",
            "[HOMING-PIGEON] result abc", "{}", ident_hint="job-1",
            **kw)

    def test_a_validated_target_writes_the_sidecar(self):
        path = self._drop(target="ops@example.com")
        self.assertEqual(os.path.basename(path),
                         "job-1.result.txt")
        sidecar = os.path.join(self.paths["outbox"],
                               "job-1.target.txt")
        with open(sidecar, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "ops@example.com")

    def test_no_target_no_sidecar(self):
        self._drop()
        self.assertEqual(sorted(os.listdir(self.paths["outbox"])),
                         ["done", "job-1.result.txt"])

    def test_an_empty_target_no_sidecar(self):
        self._drop(target="")
        self.assertEqual(sorted(os.listdir(self.paths["outbox"])),
                         ["done", "job-1.result.txt"])


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
                         ["dtls", "email", "file", "nats", "queues"])
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
            self.kw = kw
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

    def test_the_child_does_not_inherit_mutmuts_switch(self):
        os.environ["MUTANT_UNDER_TEST"] = "stats"
        try:
            cfg = _cfg(self.tmp, transports=["dtls"],
                       transport_dtls={"port": 20220,
                                       "bind": "127.0.0.1"})
            sup = self._supervisor(self.tmp, cfg)
            sup.start()
            self.assertEqual(len(self.procs), 1)
            self.assertNotIn(
                "MUTANT_UNDER_TEST", self.procs[0].kw["env"])
            sup.stop()
        finally:
            os.environ.pop("MUTANT_UNDER_TEST", None)

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
        result = _read_result(body, jid)
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
        result = _read_result(body, jid)
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
        env = _tamper_envelope(env)
        self._drop("job.txt", env)
        self._cycle()
        self.assertEqual(self._results(), [])
        # Still consumed (process-once), and nothing executed.
        self.assertIn(
            "job.txt",
            os.listdir(os.path.join(self.inbox, "done")))

    def test_a_retryable_failure_stays_in_the_inbox(self):
        # The channel used to ack when handle_mail returned,
        # including the path that logs "will retry" and does
        # not record the id. The mail rule is the opposite:
        # poison is consumed, a result that never landed is not.
        jid = str(uuid.uuid4())
        self._drop("job.txt", _envelope(jid))
        self.pipe.scan_jobs()
        from runner import runner as rr
        with mock.patch.object(
                rr, "execute_job",
                side_effect=RuntimeError("disk full")):
            poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        self.assertNotIn(jid, self.seen)
        chan_inbox = self.paths["inbox"]
        self.assertIn("job.job.txt", os.listdir(chan_inbox))
        self.assertEqual(
            os.listdir(os.path.join(chan_inbox, "done")), [])
        self.assertIn("job.txt", os.listdir(self.inbox))
        self._cycle()
        self.assertEqual(self._results(), [f"{jid}.result.txt"])
        self.assertIn(jid, self.seen)
        self.assertEqual(os.listdir(self.inbox), ["done"])

    def test_a_result_that_does_not_land_is_resent_not_run_again(self):
        # Review item 1: the job executed once and is seen; the result
        # that could not be written to the channel outbox goes back to
        # the core's outbox and the next cycle's resend pass writes it.
        from runner import runner as runner_mod
        jid = str(uuid.uuid4())
        self._drop("job.txt", _envelope(jid))
        self.pipe.scan_jobs()
        with mock.patch.object(
                transports, "write_channel_result",
                side_effect=OSError("disk full")):
            poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        self.assertIn(jid, self.seen)
        self.assertIn(
            "job.job.txt", os.listdir(self.paths["inbox"]))
        waiting = runner_mod.outbox_report(self.tmp)["waiting"]
        self.assertEqual([w["job_id"] for w in waiting], [jid])
        # The same cycle's resend pass hit the same failure, so the
        # backoff holds; a cycle past it writes the result.
        later = time.time() + 120
        with mock.patch.object(runner_mod.time, "time", lambda: later):
            self._cycle()
        self.assertEqual(self._results(), [f"{jid}.result.txt"])
        self.assertEqual(runner_mod.outbox_report(self.tmp)["waiting"], [])
        with open(os.path.join(self.outbox, f"{jid}.result.txt"),
                  encoding="utf-8") as f:
            _subject, body = transports.parse_envelope(f.read())
        result = _read_result(body, jid)
        self.assertEqual(result["stdout"], "pong")

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
        from runner.tests.test_runner import FakeIMAP, FakeSMTP
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
            result = _read_result(body, jid)
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
        conn = None
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
        except (ConnectionResetError, BrokenPipeError):
            # The test stops the client once the publish is in.
            # The client is still waiting for this publish's PONG,
            # so the close lands in the middle of that exchange.
            pass
        except Exception as e:  # noqa: BLE001 - recorded for asserts
            self.error = e
        finally:
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    pass
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
        result = _read_result(body, jid)
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
        result = _read_result(body, jid)
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
        env = _tamper_envelope(env)
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

    def test_a_publish_the_broker_refuses_leaves_the_result(self):
        # The file used to move as soon as sendall returned.
        # The broker then said no, and the result was gone.
        outbox = self.paths["outbox"]
        with open(os.path.join(outbox, "j1.result.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("[HOMING-PIGEON] result j1\n\nok\n")
        pipe = nats_ext.NatsPipe(
            {"allow_unauthenticated": True}, self.paths["root"])

        class Broker:
            timeout = 5

            def publish(self, subject, payload):
                self.subject = subject

            def flush(self, deadline):
                raise nats_ext.TransportError(
                    "nats: server error: 'Maximum Payload Violation'")

        with self.assertRaises(nats_ext.TransportError):
            pipe._flush_results(Broker())
        self.assertTrue(os.path.isfile(
            os.path.join(outbox, "j1.result.txt")))
        self.assertEqual(os.listdir(self.paths["outbox_done"]), [])

        class Accepted:
            timeout = 5

            def publish(self, subject, payload):
                pass

            def flush(self, deadline):
                pass

        pipe._flush_results(Accepted())
        self.assertFalse(os.path.exists(
            os.path.join(outbox, "j1.result.txt")))
        self.assertIn("j1.result.txt",
                      os.listdir(self.paths["outbox_done"]))


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
        from runner.tests.test_runner import FakeIMAP, FakeSMTP
        self.FakeIMAP = FakeIMAP
        self.FakeSMTP = FakeSMTP

    def _raw_mail(self, job_id, **kw):
        payload = _payload(job_id, **kw)
        body = jobcrypto.encrypt_body(
            sign_payload(payload, SECRET), SECRET, job_id=job_id,
            key_id=payload.get("key_id") or "", sign=sign_payload)
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
        result = _read_result(body, jid)
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(imap.flagged, ["1"])

    def test_a_retryable_failure_is_not_marked_seen(self):
        jid = str(uuid.uuid4())
        imap = self.FakeIMAP([self._raw_mail(jid)])
        smtp = self.FakeSMTP()
        pipe = self._pipe(imap, smtp)
        pipe.pass_once()
        from runner import runner as rr
        with mock.patch.object(
                rr, "execute_job",
                side_effect=RuntimeError("disk full")):
            poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        pipe.pass_once()
        self.assertEqual(smtp.sent, [])
        self.assertEqual(imap.flagged, [])
        self.assertNotIn(jid, self.seen)
        poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        pipe.pass_once()
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(imap.flagged, ["1"])
        body = smtp.sent[0].get_content()
        result = _read_result(body, jid)
        self.assertEqual(result["stdout"], "pong")

    def test_a_permanent_refusal_is_set_aside_and_answered_with_a_stub(self):
        # Review item 4: a 552 on one result does not wedge the queue.
        # The pipe sets it aside under outbox/failed/, sends the next
        # result, marks the refused one's mail seen; the core's next
        # pass answers the refusal with a signed stub the pipe then
        # sends; the original is kept under work/<job_id>/result.json.
        from runner import runner as rr
        jid_big = str(uuid.uuid4())
        jid_ok = str(uuid.uuid4())
        imap = self.FakeIMAP([self._raw_mail(jid_big), self._raw_mail(jid_ok)])

        class Picky(self.FakeSMTP):
            refused = []

            def send_message(self, msg):
                # The first body for jid_big is "too large"; the stub
                # that follows (encrypted like the original, so not
                # readable here) is accepted.
                if jid_big in str(msg["Subject"]) and not self.refused:
                    self.refused.append(msg)
                    raise smtplib.SMTPDataError(552, b"5.3.4 too large")
                super().send_message(msg)

        smtp = Picky()
        pipe = self._pipe(imap, smtp)
        pipe.pass_once()
        poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        pipe.pass_once()
        # The ok result went; the big one is set aside, its mail seen.
        self.assertEqual([jid_ok in str(m["Subject"]) for m in smtp.sent],
                         [True])
        self.assertEqual(sorted(str(x) for x in imap.flagged), ["1", "2"])
        failed = os.path.join(self.paths["outbox"], "failed")
        self.assertEqual(len([n for n in os.listdir(failed)
                              if n.endswith(".refused.txt")]), 1)
        # The core's pass: the stub goes back out the channel.
        poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        self.assertEqual(os.listdir(failed), [])
        pipe.pass_once()
        self.assertEqual(len(smtp.sent), 2)
        stub_msg = [m for m in smtp.sent if jid_big in str(m["Subject"])][0]
        stub = _read_result(stub_msg.get_content(), jid_big)
        self.assertEqual(stub["stdout"], "")
        self.assertIn("552", stub["delivery_note"])
        with open(os.path.join(self.tmp, "work", jid_big, "result.json"),
                  encoding="utf-8") as fh:
            self.assertIn('"pong"', fh.read())
        self.assertEqual(rr.outbox_report(self.tmp)["failed"], [])

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

    def _sidecars(self, where="outbox"):
        return sorted(f for f in os.listdir(self.paths[where])
                      if f.endswith(".target.txt"))

    def test_the_core_leaves_a_sidecar_for_a_valid_reply_to(
            self):
        # The encrypted envelope shows the pipe no reply_to;
        # the core, which parsed and validated the job, states
        # its routing decision beside the result instead.
        jid = str(uuid.uuid4())
        imap = self.FakeIMAP([self._raw_mail(
            jid, reply_to="ops@example.com")])
        smtp = self.FakeSMTP()
        pipe = self._pipe(imap, smtp)
        pipe.pass_once()
        poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        sidecars = self._sidecars()
        self.assertEqual(len(sidecars), 1)
        with open(os.path.join(self.paths["outbox"], sidecars[0]),
                  encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "ops@example.com")
        # And once the result has been sent, the sidecar has
        # followed it into done/: nothing is left behind.
        pipe.pass_once()
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(self._sidecars(), [])
        self.assertEqual(len(self._sidecars("outbox_done")), 1)

    def test_no_reply_to_leaves_no_sidecar(self):
        jid = str(uuid.uuid4())
        imap = self.FakeIMAP([self._raw_mail(jid)])
        smtp = self.FakeSMTP()
        pipe = self._pipe(imap, smtp)
        pipe.pass_once()
        poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        self.assertEqual(self._sidecars(), [])
        pipe.pass_once()
        self.assertEqual(str(smtp.sent[0]["To"]), SENDER)

    def test_an_invalid_reply_to_leaves_no_sidecar(self):
        # An unvalidated address is never written down as a
        # routing instruction: the core's rule rejects it, the
        # result falls back to the mailbox, no sidecar appears.
        jid = str(uuid.uuid4())
        imap = self.FakeIMAP([self._raw_mail(
            jid, reply_to="not-an-address")])
        smtp = self.FakeSMTP()
        pipe = self._pipe(imap, smtp)
        pipe.pass_once()
        poll_once(self.cfg, self.tmp, self.seen, self.seen_path)
        self.assertEqual(self._sidecars(), [])
        pipe.pass_once()
        self.assertEqual(str(smtp.sent[0]["To"]), SENDER)

    def test_the_sidecar_beats_the_body_parse_fallback(self):
        # A result the pipe is carrying, a core sidecar naming
        # one address, and the delivery-time body parse (the
        # cleartext-era fallback) naming another: the sidecar
        # wins, and it is acked into done/ with its result.
        imap = self.FakeIMAP([])
        smtp = self.FakeSMTP()
        pipe = self._pipe(imap, smtp)
        ident = "mail-9"
        with open(os.path.join(self.paths["outbox"],
                               ident + ".result.txt"),
                  "w", encoding="utf-8") as f:
            f.write(transports.format_envelope(
                "[HOMING-PIGEON] result abc", "{}"))
        with open(os.path.join(self.paths["outbox"],
                               ident + ".target.txt"),
                  "w", encoding="utf-8") as f:
            f.write("ops@example.com\n")
        pipe._targets[ident] = "body@example.com"
        pipe.flush_results(imap)
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(str(smtp.sent[0]["To"]),
                         "ops@example.com")
        self.assertEqual(self._sidecars(), [])
        self.assertEqual(self._sidecars("outbox_done"),
                         [ident + ".target.txt"])

    def test_a_sidecar_that_fails_the_address_rule_is_ignored(
            self):
        imap = self.FakeIMAP([])
        smtp = self.FakeSMTP()
        pipe = self._pipe(imap, smtp)
        ident = "mail-9"
        with open(os.path.join(self.paths["outbox"],
                               ident + ".result.txt"),
                  "w", encoding="utf-8") as f:
            f.write(transports.format_envelope(
                "[HOMING-PIGEON] result abc", "{}"))
        with open(os.path.join(self.paths["outbox"],
                               ident + ".target.txt"),
                  "w", encoding="utf-8") as f:
            f.write("not-an-address\n")
        pipe._targets[ident] = "body@example.com"
        pipe.flush_results(imap)
        self.assertEqual(str(smtp.sent[0]["To"]),
                         "body@example.com")

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


_NO_CONTEXT = object()


class _FakeIMAPSSL:
    """Stands in for imaplib.IMAP4_SSL: records the constructor
    arguments, then behaves just enough for connect_imap."""

    instances = []

    def __init__(self, host, port, **kw):
        self.host, self.port, self.kw = host, port, kw
        self.login_args = None
        _FakeIMAPSSL.instances.append(self)

    def login(self, user, password):
        self.login_args = (user, password)
        return "OK", []

    def select(self, _name):
        return "OK", [b"0"]


class _FakeSMTPConn:
    """Stands in for smtplib.SMTP: records whether starttls got
    a context (and which), or no context at all."""

    instances = []
    starttls_error = None

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port
        self.starttls_context = _NO_CONTEXT
        self.login_args = None
        _FakeSMTPConn.instances.append(self)

    def starttls(self, context=_NO_CONTEXT):
        if _FakeSMTPConn.starttls_error is not None:
            raise _FakeSMTPConn.starttls_error
        self.starttls_context = context

    def login(self, user, password):
        self.login_args = (user, password)


class MailTlsRequiredTest(unittest.TestCase):
    """`mail_tls_required`: the draft's TLS MUST expressed as a
    runner option. Default (anything but literal false) requires
    verified TLS 1.2+ on both mailbox connections; literal
    false opens a logged escape hatch that relaxes verification
    only -- no cleartext path exists in either mode."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-test-")
        _FakeIMAPSSL.instances = []
        _FakeSMTPConn.instances = []
        _FakeSMTPConn.starttls_error = None
        self.logs = []
        self._orig_log = mailbox.log
        mailbox.set_logger(
            lambda msg, level="INFO": self.logs.append(
                (level, msg)))
        mailbox._TLS_HATCH_WARNED = False

    def tearDown(self):
        mailbox.set_logger(self._orig_log)
        mailbox._TLS_HATCH_WARNED = False
        _FakeSMTPConn.starttls_error = None

    def _connect_both(self, cfg):
        with mock.patch.object(imaplib, "IMAP4_SSL",
                               _FakeIMAPSSL), \
                mock.patch.object(smtplib, "SMTP",
                                  _FakeSMTPConn):
            mailbox.connect_imap(cfg)
            mailbox.connect_smtp(cfg)
        return (_FakeIMAPSSL.instances[-1],
                _FakeSMTPConn.instances[-1])

    def _assert_verifying(self, ctx):
        self.assertIsInstance(ctx, ssl.SSLContext)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)
        self.assertEqual(ctx.minimum_version,
                         ssl.TLSVersion.TLSv1_2)

    def test_only_literal_false_opens_the_hatch(self):
        cases = [
            ({}, True),
            ({"mail_tls_required": True}, True),
            ({"mail_tls_required": False}, False),
            ({"mail_tls_required": "false"}, True),
            ({"mail_tls_required": "no"}, True),
            ({"mail_tls_required": 0}, True),
            ({"mail_tls_required": None}, True),
        ]
        for extra, expected in cases:
            with self.subTest(extra=extra):
                self.assertIs(mailbox.mail_tls_required(extra),
                              expected)
        self.assertIs(mailbox.mail_tls_required(None), True)

    def test_default_mode_verifies_both_connections(self):
        imap, smtp = self._connect_both(_cfg(self.tmp))
        self._assert_verifying(imap.kw["ssl_context"])
        self._assert_verifying(smtp.starttls_context)
        self.assertEqual(self.logs, [])

    def test_hatch_mode_keeps_the_previous_unverified_posture(
            self):
        cfg = _cfg(self.tmp, mail_tls_required=False)
        imap, smtp = self._connect_both(cfg)
        # Previous posture exactly: no context object handed to
        # either constructor/call -- the stdlib defaults apply.
        self.assertIsNone(imap.kw["ssl_context"])
        self.assertIs(smtp.starttls_context, _NO_CONTEXT)

    def test_hatch_warns_once_and_names_the_lost_claim(self):
        cfg = _cfg(self.tmp, mail_tls_required=False)
        self._connect_both(cfg)
        self._connect_both(cfg)
        warns = [m for level, m in self.logs if level == "WARN"]
        self.assertEqual(len(warns), 1)
        self.assertIn("mail_tls_required", warns[0])
        self.assertIn("does not meet the draft's TLS requirement",
                      warns[0])

    def test_starttls_refusal_fails_the_connect_when_required(
            self):
        _FakeSMTPConn.starttls_error = smtplib.SMTPException(
            "STARTTLS refused")
        with mock.patch.object(smtplib, "SMTP", _FakeSMTPConn):
            with self.assertRaises(smtplib.SMTPException):
                mailbox.connect_smtp(_cfg(self.tmp))
        # The failure is at the upgrade: login was never reached
        # over a plaintext or unverified session.
        self.assertIsNone(_FakeSMTPConn.instances[-1].login_args)

    def test_no_plaintext_imap_constructor_in_either_mode(self):
        def _boom(*a, **kw):
            raise AssertionError("plaintext IMAP4 constructed")

        for extra in ({}, {"mail_tls_required": False}):
            with self.subTest(extra=extra):
                cfg = _cfg(self.tmp, **extra)
                with mock.patch.object(imaplib, "IMAP4", _boom), \
                        mock.patch.object(imaplib, "IMAP4_SSL",
                                          _FakeIMAPSSL):
                    mailbox.connect_imap(cfg)

    def test_the_key_reaches_the_email_extension(self):
        cfg = _cfg(self.tmp, mail_tls_required=False)
        handed = transports._runtime_config(
            cfg, "email", self.tmp,
            transports.channel_paths(self.tmp, "email"))
        self.assertIs(handed["mail_tls_required"], False)
        # Absent stays absent: the extension applies the same
        # default (required) on its side of the channel.
        handed = transports._runtime_config(
            _cfg(self.tmp), "email", self.tmp,
            transports.channel_paths(self.tmp, "email"))
        self.assertNotIn("mail_tls_required", handed)


class MailForwardSecrecyTest(unittest.TestCase):
    """Forward secrecy on the mail hops, required posture:
    the verifying context pins TLS <= 1.2 suites to ECDHE key
    exchange, so a 1.2 session cannot fall back to a
    static-RSA suite without it. TLS 1.3 suites are
    forward-secret by construction and not governed by
    set_ciphers. The escape hatch keeps the old posture
    exactly -- no context, no pin -- and a platform that
    rejects the pin falls back to default suites with a
    WARN rather than losing its mail."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-test-")
        _FakeIMAPSSL.instances = []
        _FakeSMTPConn.instances = []
        _FakeSMTPConn.starttls_error = None
        self.logs = []
        self._orig_log = mailbox.log
        mailbox.set_logger(
            lambda msg, level="INFO": self.logs.append(
                (level, msg)))
        mailbox._TLS_HATCH_WARNED = False
        mailbox._PFS_PIN_WARNED = False

    def tearDown(self):
        mailbox.set_logger(self._orig_log)
        mailbox._TLS_HATCH_WARNED = False
        mailbox._PFS_PIN_WARNED = False
        _FakeSMTPConn.starttls_error = None

    def _connect_both(self, cfg):
        with mock.patch.object(imaplib, "IMAP4_SSL",
                               _FakeIMAPSSL), \
                mock.patch.object(smtplib, "SMTP",
                                  _FakeSMTPConn):
            mailbox.connect_imap(cfg)
            mailbox.connect_smtp(cfg)
        return (_FakeIMAPSSL.instances[-1],
                _FakeSMTPConn.instances[-1])

    def _assert_ecdhe_only_below_tls13(self, ctx):
        names = [c["name"] for c in ctx.get_ciphers()]
        below13 = [n for n in names if not n.startswith("TLS_")]
        self.assertTrue(below13)
        for name in below13:
            self.assertTrue(
                name.startswith("ECDHE"),
                f"non-ECDHE TLS<=1.2 suite enabled: {name}")

    def test_required_posture_pins_ecdhe_on_both_connections(
            self):
        imap, smtp = self._connect_both(_cfg(self.tmp))
        self._assert_ecdhe_only_below_tls13(
            imap.kw["ssl_context"])
        self._assert_ecdhe_only_below_tls13(
            smtp.starttls_context)
        self.assertEqual(self.logs, [])

    def test_hatch_mode_applies_no_cipher_pin(self):
        calls = []
        real_pin = ssl.SSLContext.set_ciphers

        def _recording_pin(self, ciphers):
            calls.append(ciphers)
            return real_pin(self, ciphers)

        with mock.patch.object(ssl.SSLContext, "set_ciphers",
                               _recording_pin):
            imap, smtp = self._connect_both(
                _cfg(self.tmp, mail_tls_required=False))
        self.assertEqual(calls, [])
        self.assertIsNone(imap.kw["ssl_context"])
        self.assertIs(smtp.starttls_context, _NO_CONTEXT)

    def test_rejected_pin_falls_back_to_default_suites_and_warns(
            self):
        def _no_pin(self, _ciphers):
            raise ssl.SSLError("no cipher match")

        with mock.patch.object(ssl.SSLContext, "set_ciphers",
                               _no_pin):
            imap, smtp = self._connect_both(_cfg(self.tmp))
            # A second pair: the warning fires once per process.
            self._connect_both(_cfg(self.tmp))
        ctx = imap.kw["ssl_context"]
        # The fallback context still verifies and keeps the
        # TLS 1.2 floor; only the pin is missing, so default
        # (non-ECDHE) suites are present again.
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(ctx.minimum_version,
                         ssl.TLSVersion.TLSv1_2)
        names = [c["name"] for c in ctx.get_ciphers()]
        self.assertTrue(any(not n.startswith(("ECDHE", "TLS_"))
                            for n in names))
        self.assertIs(smtp.starttls_context.verify_mode,
                      ssl.CERT_REQUIRED)
        warns = [m for level, m in self.logs if level == "WARN"]
        self.assertEqual(len(warns), 1)
        self.assertIn("forward secrecy", warns[0])
        self.assertIn("ECDHE", warns[0])


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
    """DRU's requirement: an owner can drop a transport
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
            result = _read_result(body, jid)
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


class ChannelEdgeTest(unittest.TestCase):
    def test_the_extensions_dir_and_a_frozen_bundle(self):
        self.assertEqual(
            transports._extensions_dir_for(
                {"extensions_dir": "/abs/ext"}, ""),
            "/abs/ext")
        self.assertEqual(transports._extensions_dir_for({}, ""), "")
        with mock.patch.object(transports.sys, "_MEIPASS", "/mei",
                               create=True):
            roots = transports.builtin_transport_roots()
        self.assertIn(
            os.path.join("/mei", "pigeon-transport-extensions"), roots)
        self.assertIn(os.path.join("/mei", "transport_extensions"), roots)

    def test_a_result_id_comes_from_the_job_when_there_is_no_hint(self):
        with tempfile.TemporaryDirectory() as d:
            path = transports.write_channel_result(
                d, "file",
                "[HOMING-PIGEON] job abc/def",
                "[HOMING-PIGEON] result",
                "body-no-newline")
            self.assertTrue(path.endswith("abc_def.result.txt"))
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertTrue(text.endswith("\n"))
            self.assertIn("body-no-newline", text)

    def test_a_directory_and_bad_bytes_are_not_a_job(self):
        with tempfile.TemporaryDirectory() as d:
            paths = transports.ensure_channel_dirs(d, "file")
            os.mkdir(os.path.join(paths["inbox"], "notes"))
            with open(os.path.join(paths["inbox"], "bad.job.txt"),
                      "wb") as fh:
                fh.write(b"\xff\xfe not utf-8\n\nbody")
            lines = []
            got = transports.fetch_channel_messages(
                d, "file", log=lambda m, level="INFO": lines.append(m))
            self.assertEqual(len(got), 1)
            self.assertEqual(got[0].subject, "")
            self.assertTrue(any("UTF-8" in m for m in lines))
            got[0].ack()
            self.assertTrue(os.path.isfile(os.path.join(
                paths["inbox_done"], "bad.job.txt")))

    def test_a_symlink_and_an_oversize_file_are_refused(self):
        with tempfile.TemporaryDirectory() as d, \
                tempfile.TemporaryDirectory() as outside:
            paths = transports.ensure_channel_dirs(d, "file")
            os.symlink(os.path.join(outside, "nope"),
                       os.path.join(paths["inbox"], "link.job.txt"))
            with open(os.path.join(paths["inbox"], "big.job.txt"),
                      "wb") as fh:
                fh.write(b"x" * (transports.FILE_MAX_BYTES + 1))
            lines = []
            got = transports.fetch_channel_messages(
                d, "file", log=lambda m, level="INFO": lines.append(m))
            self.assertEqual(len(got), 2)
            self.assertTrue(any("symlink" in m for m in lines))
            self.assertTrue(any("exceeds" in m for m in lines))

    def test_an_ack_logs_a_file_that_cannot_be_moved(self):
        with tempfile.TemporaryDirectory() as d:
            paths = transports.ensure_channel_dirs(d, "file")
            job = os.path.join(paths["inbox"], "j.job.txt")
            with open(job, "w", encoding="utf-8") as fh:
                fh.write("Subject: hi\n\nbody\n")
            lines = []
            got = transports.fetch_channel_messages(
                d, "file", log=lambda m, level="INFO": lines.append(m))
            os.remove(job)
            got[0].ack()
            self.assertTrue(any("cannot move" in m for m in lines))
            with open(job, "w", encoding="utf-8") as fh:
                fh.write("Subject: hi\n\nbody\n")
            lines.clear()
            got = transports.fetch_channel_messages(
                d, "file", log=lambda m, level="INFO": lines.append(m))
            import shutil
            shutil.rmtree(paths["inbox_done"])
            with open(paths["inbox_done"], "w", encoding="utf-8") as fh:
                fh.write("not a directory")
            got[0].ack()
            self.assertTrue(any("cannot move" in m for m in lines))

    def test_a_failed_ack_must_roll_back_probe(self):
        # FAILING BY DESIGN -- Q25 in docs/seats/questions.md.
        #
        # (1) The claim, from service_channel's code and
        # docstring in runner/wire/transports.py: "rollback
        # on the sequence, when callable, runs in that case
        # so a seen-set entry recorded before the write can
        # be dropped", and the ack site reads
        # `acked = msg.ack()` and rolls back
        # `if acked is False and callable(rollback)` -- a
        # failed ack is a rollback case.
        # (2) Where stated: the service_channel docstring
        # and its ack branch (transports.py ~516-535); the
        # channel ack itself returns False when it refuses
        # (the envelope changed after it was read, ~443).
        # (3) What the code does instead:
        # IncomingMessage.ack() calls self._ack() and
        # discards its return, so msg.ack() is always None,
        # `acked is False` is never true, and the rollback
        # branch is dead: the envelope stays for the next
        # cycle (correct) but its seen-set entry is never
        # dropped, so the retry can be refused as a
        # duplicate of itself.
        # (4) DO NOT GREEN by editing this test. It goes
        # green when IncomingMessage.ack() returns the
        # wrapped ack's result (Claude's lane, Q25).
        class _Replies(list):
            def __init__(self, items, rollback):
                super().__init__(items)
                self.rollback = rollback

        with tempfile.TemporaryDirectory() as d:
            paths = transports.ensure_channel_dirs(d, "file")
            job = os.path.join(paths["inbox"], "j.job.txt")
            with open(job, "w", encoding="utf-8") as fh:
                fh.write("Subject: hi\n\nbody\n")
            rolled = []

            def rollback():
                rolled.append(True)
                raise RuntimeError("rollback broke")

            def process(_subject, _body):
                with open(job, "a", encoding="utf-8") as fh:
                    fh.write("changed after the read\n")
                return _Replies([("result subject", "the body")],
                                rollback)

            lines = []
            visited = transports.service_channel(
                d, "file", process,
                log=lambda m, level="INFO": lines.append(m))
            self.assertEqual(visited, 1)
            self.assertEqual(rolled, [True])
            self.assertTrue(any("rollback failed" in m
                                for m in lines))
            self.assertTrue(os.path.isfile(job))
            self.assertEqual(os.listdir(paths["inbox_done"]), [])
            # The reply landed: one file beside the outbox's own
            # done/ folder (ensure_channel_dirs makes it).
            self.assertEqual(len([
                f for f in os.listdir(paths["outbox"])
                if os.path.isfile(os.path.join(paths["outbox"], f))]), 1)

    def test_a_file_that_cannot_be_read_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            paths = transports.ensure_channel_dirs(d, "file")
            job = os.path.join(paths["inbox"], "gone.job.txt")
            with open(job, "w", encoding="utf-8") as fh:
                fh.write("Subject: hi\n\nbody\n")
            real_open = open

            def boom(path, mode="r", *args, **kwargs):
                if path == job and "b" in str(mode):
                    raise OSError("denied")
                return real_open(path, mode, *args, **kwargs)

            lines = []
            with mock.patch("builtins.open", boom):
                got = transports.fetch_channel_messages(
                    d, "file",
                    log=lambda m, level="INFO": lines.append(m))
            self.assertEqual(len(got), 1)
            self.assertTrue(any("cannot read" in m for m in lines))
            import shutil
            shutil.rmtree(paths["inbox_done"])
            with open(paths["inbox_done"], "w", encoding="utf-8") as fh:
                fh.write("not a directory")
            got[0].ack()
            self.assertTrue(any("cannot move" in m for m in lines))

    def test_a_rewrite_during_the_read_is_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            paths = transports.ensure_channel_dirs(d, "file")
            target = os.path.join(paths["inbox"], "race.job.txt")
            first = b"Subject: one\n\nbody\n"
            second = b"Subject: two\n\nbody\n"
            with open(target, "wb") as fh:
                fh.write(first)
            real_open = open
            calls = {"n": 0}

            def flip(path, mode="r", *args, **kwargs):
                if path == target and "b" in str(mode):
                    calls["n"] += 1
                    import io
                    body = first if calls["n"] == 1 else second
                    return io.BytesIO(body)
                return real_open(path, mode, *args, **kwargs)

            with mock.patch("builtins.open", flip):
                got = transports.fetch_channel_messages(d, "file")
            self.assertEqual(got, [])
            self.assertTrue(os.path.isfile(target))

    def test_a_result_that_does_not_land_is_not_consumed(self):
        with tempfile.TemporaryDirectory() as d:
            paths = transports.ensure_channel_dirs(d, "file")
            job = os.path.join(paths["inbox"], "j.job.txt")
            with open(job, "w", encoding="utf-8") as fh:
                fh.write("Subject: hi\n\nbody\n")
            lines = []

            def log(msg, level="INFO"):
                lines.append(msg)

            def process(subject, body):
                return [("Subject: out", "body")]

            with mock.patch.object(
                    transports, "write_channel_result",
                    side_effect=OSError("full")):
                n = transports.service_channel(
                    d, "file", process, log=log)
            self.assertEqual(n, 1)
            self.assertTrue(os.path.isfile(job))
            self.assertTrue(any("did not land" in m for m in lines))

    def test_a_raising_rollback_and_a_raising_ack_are_logged(self):
        with tempfile.TemporaryDirectory() as d:
            paths = transports.ensure_channel_dirs(d, "file")
            with open(os.path.join(paths["inbox"], "j.job.txt"),
                      "w", encoding="utf-8") as fh:
                fh.write("Subject: hi\n\nbody\n")
            lines = []

            class Replies(list):
                def rollback(self):
                    raise RuntimeError("rb")

            def process(subject, body):
                out = Replies()
                out.consume = False
                return out

            transports.service_channel(
                d, "file", process, log=lambda m, level="INFO": lines.append(m))
            self.assertTrue(any("rollback failed" in m for m in lines))

            def boom(subject, body):
                raise RuntimeError("bad job")

            lines.clear()
            with mock.patch.object(
                    transports.IncomingMessage, "ack",
                    side_effect=OSError("stuck")):
                transports.service_channel(
                    d, "file", boom,
                    log=lambda m, level="INFO": lines.append(m))
            self.assertTrue(any("ack failed" in m for m in lines))
            self.assertTrue(any("failed" in m for m in lines))

    def test_a_processor_that_returns_nothing_still_acks(self):
        with tempfile.TemporaryDirectory() as d:
            paths = transports.ensure_channel_dirs(d, "file")
            with open(os.path.join(paths["inbox"], "j.job.txt"),
                      "w", encoding="utf-8") as fh:
                fh.write("Subject: hi\n\nbody\n")
            n = transports.service_channel(
                d, "file", lambda subject, body: None)
            self.assertEqual(n, 1)
            self.assertTrue(os.path.isfile(os.path.join(
                paths["inbox_done"], "j.job.txt")))
            msg = transports.IncomingMessage("s", "b", lambda *a: None)
            msg.ack()

    def test_dtls_secrets_come_from_files_and_inline_wins(self):
        with tempfile.TemporaryDirectory() as d:
            secret = os.path.join(d, "secret")
            extra = os.path.join(d, "extra")
            with open(secret, "w", encoding="utf-8") as fh:
                fh.write("sekrit\n")
            with open(extra, "w", encoding="utf-8") as fh:
                fh.write("from-file\n")
            out = transports._dtls_secret_material({
                "shared_secret_file": secret,
                "additional_secrets": {"a": "inline", "bad": 5},
                "additional_secrets_files": {
                    "a": extra, "b": extra, "c": 5,
                    "d": os.path.join(d, "missing")},
            })
            self.assertEqual(out["shared_secret"], "sekrit")
            self.assertEqual(out["additional_secrets"]["a"], "inline")
            self.assertEqual(out["additional_secrets"]["b"], "from-file")
            self.assertNotIn("d", out["additional_secrets"])
            self.assertEqual(transports._read_secret_file_quiet(
                os.path.join(d, "missing")), "")
            handed = transports._runtime_config(
                None, "file", d, {"root": d})
            self.assertEqual(handed["poll_interval_sec"], 20)
            paths = {"root": d}
            real_open = os.open

            def refuse(*args, **kwargs):
                raise OSError("no fd")

            with mock.patch("runner.wire.transports.os.open", refuse):
                written = transports._write_runtime_config(
                    paths, {"name": "file"})
            with open(written, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["name"], "file")


class SupervisorFailureTest(unittest.TestCase):
    def _sup(self, tmp, cfg, popen):
        return transports.TransportSupervisor(
            cfg, tmp, log=lambda m, level="INFO": self.lines.append(
                (level, m)),
            popen=popen, clock=lambda: self.clock[0])

    def setUp(self):
        self.lines = []
        self.clock = [1000.0]
        self.tmp = tempfile.mkdtemp(prefix="hp-sup-")

    def test_a_broken_folder_is_logged_and_a_frozen_argv_is_rewritten(self):
        ext = os.path.join(self.tmp, "ext", "broken")
        os.makedirs(ext)
        with open(os.path.join(ext, "extension.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{")
        cfg = {"transports": ["file"],
               "extensions_dir": os.path.dirname(ext)}
        seen = []

        def popen(argv, **kw):
            seen.append((argv, kw))
            proc = SupervisorTest.FakeProc(argv, **kw)
            proc.stdout = None
            return proc

        with mock.patch.object(transports.sys, "frozen", True, create=True):
            sup = self._sup(self.tmp, cfg, popen)
            sup.start()
        self.assertTrue(any("not valid JSON" in m for _l, m in self.lines))
        argv = seen[0][0]
        self.assertEqual(argv[1], "--transport-extension-module")
        parent = os.path.dirname(os.path.dirname(
            os.path.abspath(transports.__file__)))
        os.environ["PYTHONPATH"] = parent
        try:
            with mock.patch.object(transports.sys, "frozen", False, create=True):
                sup2 = self._sup(self.tmp, {"transports": ["file"]}, popen)
                sup2.start()
            env = seen[-1][1]["env"]["PYTHONPATH"].split(os.pathsep)
            self.assertEqual(env.count(parent), 1)
            sup2.stop()
        finally:
            os.environ.pop("PYTHONPATH", None)
        sup.processes["file"]["restarts"] = 4
        self.clock[0] += 61
        sup.check()
        self.assertEqual(sup.processes["file"]["restarts"], 0)
        sup.stopped = True
        sup.check()
        sup.stop()

    def test_settle_treats_an_unreadable_inbox_as_empty(self):
        cfg = {"transports": ["file"]}
        sup = self._sup(self.tmp, cfg, lambda argv, **kw:
                        SupervisorTest.FakeProc(argv, **kw))
        sup.start()
        rec = sup.processes["file"]
        rec["settled"] = False
        rec["manifest"]["startup_settle_ms"] = 40
        inbox = transports.channel_paths(self.tmp, "file")["inbox"]
        import shutil
        shutil.rmtree(inbox)
        with open(inbox, "w", encoding="utf-8") as fh:
            fh.write("not a directory")
        sup.settle()
        self.assertTrue(rec["settled"])
        sup.stop()

    def test_the_pump_reopens_a_sidecar_and_survives_a_bad_log(self):
        cfg = {"transports": ["file"]}
        sup = self._sup(self.tmp, cfg, lambda argv, **kw:
                        SupervisorTest.FakeProc(argv, **kw))
        log_path = os.path.join(self.tmp, "extension.log")
        writes = {"n": 0}
        real_open = open

        class Handle:
            def write(self, data):
                writes["n"] += 1
                if writes["n"] == 1:
                    raise OSError("closed")
                return len(data)
            def flush(self):
                return None
            def close(self):
                raise OSError("close")

        def fake_open(path, mode="r", *args, **kwargs):
            if path == log_path:
                return Handle()
            return real_open(path, mode, *args, **kwargs)

        def lines():
            yield b"\n"
            yield b"WARN: the pipe filled\n"
            raise OSError("pipe")

        def bad_log(msg, level="INFO"):
            raise RuntimeError("log")

        sup.log = bad_log
        with mock.patch("builtins.open", fake_open):
            sup._pump_extension_log("file", lines(), log_path)
        self.assertGreaterEqual(writes["n"], 2)

    def test_a_process_that_will_not_die_is_killed(self):
        class Stubborn(SupervisorTest.FakeProc):
            def poll(self):
                return None
            def terminate(self):
                raise OSError("term")
            def kill(self):
                raise OSError("kill")

        cfg = {"transports": ["file"]}
        sup = self._sup(self.tmp, cfg, lambda argv, **kw: Stubborn(argv, **kw))
        sup.start()
        with mock.patch("runner.wire.transports._wait_down", return_value=False):
            sup.stop()
        self.assertTrue(sup.stopped)

        class Alive(SupervisorTest.FakeProc):
            def poll(self):
                return None

        ticks = {"n": 0}

        def mono():
            ticks["n"] += 1
            return ticks["n"] * 10

        with mock.patch("runner.wire.transports.time.monotonic", mono), \
                mock.patch("runner.wire.transports._SLEEP", lambda _s: None):
            self.assertFalse(transports._wait_down(Alive([],), 1))

    def test_the_same_config_reuses_the_supervisor(self):
        cfg = {"transports": ["file"]}
        with mock.patch("runner.wire.transports.subprocess.Popen",
                        lambda argv, **kw: SupervisorTest.FakeProc(argv, **kw)):
            first = transports.start_supervisor(cfg, self.tmp)
            second = transports.start_supervisor(cfg, self.tmp)
            self.assertIs(first, second)
            self.assertIs(
                transports.active_supervisor(cfg, self.tmp), first)
            self.assertEqual(
                transports._config_signature(None, self.tmp),
                (self.tmp, ""))
            bad = {"transports": ["dtls"], "additional_secrets": {1: "x"}}
            sig = transports._config_signature(bad, self.tmp)
            self.assertEqual(sig[0], self.tmp)
            first.stop()
            self.assertIsNone(transports.active_supervisor(cfg, self.tmp))

        class Boom:
            stopped = False
            def stop(self):
                raise RuntimeError("no")

        transports._ACTIVE_SUPERVISORS[(self.tmp, "boom")] = Boom()
        transports.stop_supervisors(self.tmp)
        self.assertNotIn((self.tmp, "boom"), transports._ACTIVE_SUPERVISORS)

    def test_a_start_that_fails_and_a_waiting_inbox(self):
        lines = []

        def refuse(argv, **kw):
            raise OSError("nope")

        sup = transports.TransportSupervisor(
            {"transports": ["file"]}, self.tmp,
            log=lambda m, level="INFO": lines.append(m),
            popen=refuse, clock=lambda: 1.0)
        sup.start()
        self.assertIsNone(sup.processes["file"]["proc"])
        self.assertTrue(any("cannot start" in m for m in lines))
        sup.stop()

        def popen(argv, **kw):
            return SupervisorTest.FakeProc(argv, **kw)

        sup = transports.TransportSupervisor(
            {"transports": ["file"]}, self.tmp, popen=popen,
            clock=lambda: 1.0)
        sup.start()
        rec = sup.processes["file"]
        rec["settled"] = False
        rec["manifest"]["startup_settle_ms"] = 500
        inbox = transports.channel_paths(self.tmp, "file")["inbox"]
        with open(os.path.join(inbox, "waiting.job.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("x")
        sup.settle()
        self.assertTrue(rec["settled"])
        sup.stop()

        class Keep:
            def stop(self):
                self.called = True

        keep = Keep()
        transports._ACTIVE_SUPERVISORS[("/other-base", "k")] = keep
        transports.stop_supervisors(self.tmp)
        self.assertIn(("/other-base", "k"), transports._ACTIVE_SUPERVISORS)
        del transports._ACTIVE_SUPERVISORS[("/other-base", "k")]

        loop = {}
        loop["self"] = loop
        sig = transports._config_signature(
            {"transports": ["dtls"], "additional_secrets": loop},
            self.tmp)
        self.assertIn("additional_secrets", sig[1])

    def test_the_pump_drops_a_poisoned_line_and_a_dead_sidecar(self):
        sup = transports.TransportSupervisor(
            {"transports": ["file"]}, self.tmp, popen=lambda *a, **k: None,
            clock=lambda: 1.0)
        log_path = os.path.join(self.tmp, "extension.log")

        class Dead:
            def write(self, data):
                raise OSError("closed")
            def flush(self):
                return None
            def close(self):
                return None

        real_open = open

        def fake_open(path, mode="r", *args, **kwargs):
            if path == log_path:
                return Dead()
            return real_open(path, mode, *args, **kwargs)

        def lines():
            yield b"WARN: still here\n"

        with mock.patch("builtins.open", fake_open):
            sup._pump_extension_log("file", lines(), log_path)

        def poison(text):
            raise RuntimeError("poison")

        def more():
            yield b"plain line\n"

        with mock.patch("runner.wire.transports._extension_line_parts", poison):
            sup._pump_extension_log("file", more(), log_path)


class _ScriptedNats(threading.Thread):
    """One connection, one scripted behavior: the behavior
    callable gets the connected socket. It should hold the
    connection (a recv that ends when the client gives up
    and closes) when the script is silence."""

    def __init__(self, behavior):
        super().__init__(daemon=True)
        self.behavior = behavior
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
            conn.settimeout(10)
            try:
                self.behavior(conn)
            finally:
                conn.close()
        except Exception:
            pass
        finally:
            self.sock.close()


def _hold(conn):
    try:
        while conn.recv(4096):
            pass
    except OSError:
        pass


def _after_info(reply):
    def behave(conn):
        conn.sendall(b'INFO {"server_id":"fake"}\r\n')
        conn.recv(4096)          # the CONNECT + PING
        if reply is not None:
            conn.sendall(reply)
        _hold(conn)
    return behave


class _ScriptedSock:
    """A socket stand-in feeding scripted chunks; when
    they run out, recv times out, like a quiet server."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.sent = []

    def settimeout(self, _value):
        pass

    def recv(self, _size):
        if self._chunks:
            return self._chunks.pop(0)
        raise socket.timeout("quiet")

    def sendall(self, data):
        self.sent.append(data)


class NatsNextMessageLegsTest(unittest.TestCase):
    """Queue A refill: NatsClient.next_message's
    control-line legs and _read_exact's mid-message
    timeout (coverage run 40189711740: next_message
    lines 237-238, 240, 242; _read_exact lines
    164-167). The minimal client's contract: a
    server PING is answered with PONG and skipped,
    PONG/+OK lines are skipped, an -ERR ends the
    cycle as a TransportError naming the server's
    text, and a payload that stops arriving
    mid-message is a timeout, not a hang.
    """

    def _client(self, chunks):
        client = nats_ext.NatsClient("nats://127.0.0.1:4222")
        client.sock = _ScriptedSock(chunks)
        return client

    def test_control_lines_are_skipped_and_a_ping_answered(self):
        client = self._client(
            [b"PING\r\nPONG\r\n+OK\r\nMSG subj 1 5\r\nhello\r\n"])
        got = client.next_message(time.monotonic() + 30)
        self.assertEqual(got, ("subj", b"hello"))
        self.assertIn(b"PONG\r\n", client.sock.sent)

    def test_a_server_error_raises(self):
        client = self._client([b"-ERR 'Authorization Violation'\r\n"])
        with self.assertRaisesRegex(nats_ext.TransportError,
                                    "Authorization Violation"):
            client.next_message(time.monotonic() + 30)

    def test_a_refused_publish_is_not_a_pong(self):
        # The broker processed the PUB and refused it. Waiting
        # only for the write to return moved the result anyway.
        client = self._client(
            [b"-ERR 'Maximum Payload Violation'\r\n"])
        with self.assertRaisesRegex(nats_ext.TransportError,
                                    "Maximum Payload Violation"):
            client.flush(time.monotonic() + 30)
        self.assertIn(b"PING\r\n", client.sock.sent)

    def test_a_job_arriving_before_the_pong_is_not_dropped(self):
        client = self._client([
            b"MSG homing-pigeon.jobs 1 5\r\nhello\r\n",
            b"PONG\r\n",
        ])
        client.flush(time.monotonic() + 30)
        got = client.next_message(time.monotonic() + 30)
        self.assertEqual(got, ("homing-pigeon.jobs", b"hello"))

    def test_a_payload_that_stops_mid_message_times_out(self):
        client = self._client([b"MSG s 1 100\r\nshort"])
        with self.assertRaisesRegex(nats_ext.TransportError,
                                    "timed out mid-message"):
            client.next_message(time.monotonic() + 30)

    def test_a_past_deadline_and_a_broken_socket(self):
        # Queue A refill: _fill's expired-deadline leg,
        # _send's failure leg and close's swallow
        # (coverage run 40189711740: _fill line 143,
        # _send lines 175-176, close lines 256-257).
        # A deadline already gone reads as no message;
        # a send the socket refuses is a TransportError;
        # a close the socket refuses is swallowed and
        # the socket is still dropped.
        client = self._client([b"PING\r\n"])
        self.assertIsNone(
            client.next_message(time.monotonic() - 1))

        class BrokenSock(_ScriptedSock):
            def sendall(self, data):
                raise OSError("refused")

            def close(self):
                raise OSError("stuck")

        client = self._client([])
        client.sock = BrokenSock([])
        with self.assertRaisesRegex(nats_ext.TransportError,
                                    "send failed"):
            client._send(b"PONG\r\n")
        client.close()
        self.assertIsNone(client.sock)


class NatsSmallLegsTest(unittest.TestCase):
    """Queue A refill: the NATS client's small
    legs (coverage run 40189711740: __init__'s
    token-only URL 133, _fill's closed server
    152, ping 225, and the silent default log
    55). A URL naming only a user authenticates
    with it as the token; a server that closes
    mid-read is a transport error, not an idle;
    a ping is one PING line; and the default
    log says nothing, by design.
    """

    def test_a_token_only_url(self):
        client = nats_ext.NatsClient(
            "nats://onlytoken@127.0.0.1:4222")
        self.assertEqual(
            client._connect_opts.get("auth_token"),
            "onlytoken")
        self.assertNotIn("user", client._connect_opts)

    def test_a_closed_server_is_a_transport_error(self):
        import time as _time
        client = object.__new__(nats_ext.NatsClient)
        client.sock = mock.Mock()
        client.sock.recv.return_value = b""
        client._buf = b""
        with self.assertRaisesRegex(
                nats_ext.TransportError, "server closed"):
            client._fill(_time.monotonic() + 5)

    def test_ping_is_one_line(self):
        client = object.__new__(nats_ext.NatsClient)
        sent = []
        client._send = sent.append
        client.ping()
        self.assertEqual(sent, [b"PING\r\n"])

    def test_the_default_log_is_silent(self):
        self.assertIsNone(nats_ext._silent_log("anything"))


class NatsConnectFailuresTest(unittest.TestCase):
    """Queue A refill: NatsClient.connect's failure legs
    (coverage run 40187685363: 9 lines on both platforms).
    The client's contract, from its own error strings:
    every refusal and every silence from the broker is a
    TransportError that says which stage failed -- the
    transport fails the cycle and the next poll reconnects,
    so connect must never hang past its timeout and never
    mistake a wrong answer for a handshake.
    """

    def _connect(self, port, timeout=5.0):
        client = nats_ext.NatsClient(
            f"nats://127.0.0.1:{port}", timeout=timeout)
        try:
            with self.assertRaises(
                    nats_ext.TransportError) as cm:
                client.connect()
            return str(cm.exception)
        finally:
            if client.sock is not None:
                client.sock.close()

    def _serve(self, behavior):
        server = _ScriptedNats(behavior)
        server.start()
        return server.port

    def test_a_refused_connection_is_named(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        msg = self._connect(port, timeout=2.0)
        self.assertIn("cannot connect to", msg)

    def test_silence_before_info_times_out(self):
        msg = self._connect(self._serve(_hold), timeout=0.5)
        self.assertIn("timed out waiting for the server INFO",
                      msg)

    def test_a_non_info_greeting_is_refused(self):
        def behave(conn):
            conn.sendall(b"HELLO\r\n")
            _hold(conn)

        msg = self._connect(self._serve(behave))
        self.assertIn("expected INFO, got", msg)

    def test_silence_after_info_times_out(self):
        msg = self._connect(self._serve(_after_info(None)),
                            timeout=0.5)
        self.assertIn("timed out waiting for PONG", msg)

    def test_a_server_error_is_carried(self):
        msg = self._connect(self._serve(
            _after_info(b"-ERR 'Authorization Violation'\r\n")))
        self.assertIn("server error:", msg)
        self.assertIn("Authorization Violation", msg)

    def test_a_wrong_pong_is_refused(self):
        msg = self._connect(self._serve(
            _after_info(b"PANG\r\n")))
        self.assertIn("expected PONG, got", msg)


class NatsPipeRunDropsTest(unittest.TestCase):
    """Queue A refill: NatsPipe.run's drop and cleanup
    legs (coverage run 40187685363: 7 lines on Linux, 5
    on Windows). The pipe's contract for broker traffic:
    a message that is not UTF-8 and a message that is
    not an envelope are each logged and dropped, never
    delivered; a dead connection is closed, logged, and
    re-established with backoff -- the loop takes
    nothing down with it.
    """

    def test_bad_messages_drop_and_a_dead_link_closes(self):
        logs = []
        script = [("homing-pigeon.jobs", b"\xff\xfe binary"),
                  ("homing-pigeon.jobs", b"no blank line here")]

        class FakeClient:
            def __init__(self):
                self.closed = False

            def next_message(self, deadline):
                if script:
                    return script.pop(0)
                raise nats_ext.TransportError("link down")

            def close(self):
                self.closed = True

        client = FakeClient()
        with tempfile.TemporaryDirectory() as d:
            channel = os.path.join(d, "channel")
            pipe = nats_ext.NatsPipe(
                {"url": "nats://127.0.0.1:4222",
                 "allow_unauthenticated": True},
                channel,
                log=lambda m, level="INFO": logs.append(m))
            connects = []

            def fake_connect():
                connects.append(1)
                if len(connects) == 1:
                    pipe.client = client
                else:
                    pipe.stop()
                    raise nats_ext.TransportError("still down")

            pipe._connect = fake_connect
            with mock.patch.object(nats_ext.ch, "nap",
                                   lambda s: None):
                pipe.run()
            delivered = []
            for root, _dirs, files in os.walk(channel):
                delivered += [f for f in files
                              if f.endswith(".job.txt")]
        self.assertEqual(delivered, [])
        self.assertTrue(client.closed)
        text = "\n".join(logs)
        self.assertIn("non-UTF-8", text)
        self.assertIn("malformed envelope", text)
        self.assertIn("reconnecting", text)


class ReviewFailureTest(unittest.TestCase):
    """Queue A (coverage map, discover_transport_extensions):
    the extension review failing must never take discovery
    down -- the registry is returned unreviewed and the
    failure is a WARN line, per the catch's own comment."""

    def test_a_raising_review_leaves_the_registry_whole(self):
        lines = []

        def log(msg, level="INFO"):
            lines.append((level, msg))

        with mock.patch.object(
                transports._extreview, "apply",
                side_effect=RuntimeError("review blew up")):
            registry, problems = \
                transports.discover_transport_extensions(
                    {}, tempfile.mkdtemp(prefix="hp-test-"),
                    log=log)
        self.assertEqual(sorted(registry),
                         ["dtls", "email", "file", "nats", "queues"])
        self.assertEqual(problems, [])
        self.assertTrue(
            any(level == "WARN" and "extension review failed"
                in msg and "review blew up" in msg
                for level, msg in lines), lines)


if __name__ == "__main__":
    unittest.main()
