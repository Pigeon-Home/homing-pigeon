# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The on-box local submission path, pinned end to end.

An operator standing on a runner host submits jobs locally
through the file transport instead of the mailbox: the sender
tool builds the job, the watched folder carries it, the core
runs it, the result file comes back through the same folder,
and the sender tool opens it. This is the standing submission
path on the fleet's FreeBSD node (field proof 2026-11-12:
signed ping -> pong, signed clock exec -> exit 0, an
unknown-key job refused), and it is a composition the rest of
the suite covers only in pieces -- send_job's --to-file output
here, the file pipe's round trip with hand-built envelopes
there. This file pins the composition itself, exactly as the
operator runs it:

    send_job.py new --keyring <ring> --key-id <fingerprint>
        --aud <runner_id> --to-file <staging file>
    -> atomic rename into <base>/transport-file/inbox/<job_id>.txt
    -> FilePipe delivers it; the core verifies and runs it
    -> <base>/transport-file/outbox/<job_id>.result.txt
    -> send_job's verify path opens the result (signature
       checked, body decrypted) under the keyring

The fixture runs the audience gate at enforce, the posture
this path operates under on the node: a job addressed to a
different runner, and a job signed under a key the runner does
not hold, are refused and leave no result file. Confinement
and job_user are stated off -- not this fixture's subject,
the same scoping the transport suite's fixture states.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

from runner.cloud import send_job  # noqa: E402
from runner.runner import poll_once  # noqa: E402
from runner.wire import transports  # noqa: E402
from runner.transport_extensions.file import (  # noqa: E402
    __main__ as file_ext)

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"
OTHER_SECRET = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
RUNNER_ID = "97132610afb6466fae0523d49ffc1932"
SENDER = "runner@example.com"


class OperatorPathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-operator-path-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.base = os.path.join(self.tmp, "state")
        os.makedirs(self.base)
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "shared_secret": SECRET,
            "imap_host": "fake", "imap_port": 993,
            "smtp_host": "fake", "smtp_port": 587,
            "poll_interval_sec": 20,
            "max_job_age_sec": 3600,
            "max_output_bytes": 100000,
            "base_dir": self.base,
            "default_timeout_sec": 300,
            "runner_id": RUNNER_ID,
            "transports": ["file"],
            "security": {"modes": {"confinement": "off",
                                   "job_user": "off",
                                   "audience": "enforce"}},
        }
        self.seen = {}
        self.seen_path = os.path.join(self.tmp, "seen.json")
        paths = transports.channel_paths(self.base, "file")
        transports.ensure_channel_dirs(self.base, "file")
        self.pipe = file_ext.FilePipe(
            {"base_dir": self.base,
             "inbox": "transport-file/inbox",
             "outbox": "transport-file/outbox"},
            paths["root"])
        self.staging = os.path.join(self.tmp, "staging")
        os.makedirs(self.staging)
        self.ring = self._keyring("keyring.json", SECRET)

    def _keyring(self, name, secret):
        """A sender keyring keyed by the secret's fingerprint --
        the standing form: the name the runner answers to is
        also the name that selects the secret (Q94)."""
        path = os.path.join(self.tmp, name)
        send_job.keyring_save(path, {
            send_job.key_fingerprint(secret): {
                "secret": secret, "runner": SENDER}})
        return path

    def _submit(self, ring, *job_args):
        """send_job new --to-file into staging, then the atomic
        rename into the watched inbox -- the operator's drop."""
        jid = str(uuid.uuid4())
        staged = os.path.join(self.staging, jid + ".txt")
        argv = ["send_job.py", "new", "--kind", "ping",
                "--keyring", ring,
                "--key-id", self._ring_key_id(ring),
                "--job-id", jid, "--to-file", staged] + list(job_args)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", argv):
            with redirect_stdout(out), redirect_stderr(err):
                rc = send_job.main()
        self.assertEqual(rc, 0, err.getvalue())
        os.replace(staged, os.path.join(self.pipe.inbox, jid + ".txt"))
        return jid

    def _ring_key_id(self, ring):
        return next(iter(send_job.keyring_load(ring)))

    def _cycle(self):
        self.pipe.scan_jobs()
        poll_once(self.cfg, self.base, self.seen, self.seen_path)
        self.pipe.scan_results()

    def _open_result(self, jid):
        path = os.path.join(self.pipe.outbox, jid + ".result.txt")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        args = SimpleNamespace(secret=None, key_id=None,
                               keyring=self.ring)
        return send_job._open_body(text, args, jid)

    def test_ping_via_the_operator_path(self):
        jid = self._submit(self.ring, "--aud", RUNNER_ID)
        self._cycle()
        self.assertEqual(sorted(os.listdir(self.pipe.outbox)),
                         [jid + ".result.txt"])
        result = self._open_result(jid)
        self.assertEqual(result["job_id"], jid)
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["exit_code"], 0)
        # Processed exactly once: the job file rests in done/.
        self.assertIn(jid + ".txt", os.listdir(
            os.path.join(self.pipe.inbox, "done")))

    def test_wrong_audience_is_refused_without_a_result(self):
        jid = self._submit(self.ring, "--aud", "a-different-runner")
        self._cycle()
        self._cycle()
        self.assertEqual(os.listdir(self.pipe.outbox), [])
        self.assertIn(jid + ".txt", os.listdir(
            os.path.join(self.pipe.inbox, "done")))

    def test_a_key_the_runner_does_not_hold_is_refused(self):
        other = self._keyring("other-keyring.json", OTHER_SECRET)
        jid = self._submit(other, "--aud", RUNNER_ID)
        self._cycle()
        self._cycle()
        self.assertEqual(os.listdir(self.pipe.outbox), [])
        self.assertIn(jid + ".txt", os.listdir(
            os.path.join(self.pipe.inbox, "done")))


if __name__ == "__main__":
    unittest.main()
