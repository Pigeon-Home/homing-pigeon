#!/usr/bin/env python3
"""Q17 (the send_job half): every job `send_job.py new` builds,
fed straight back into the runner's verifier.

The builder is the command a cloud SI uses to make a job; the
coverage map showed most of cmd_new never ran -- the key_id,
aud and reply_to members, the whole exec block (script-url,
script-sha384, files, args, env, interpreter), the refusal
when an exec job has no script, and the --to-file envelope.
The promise under test is AGENTS.md's: use send_job.py, do
not hand-roll -- so everything it emits must verify through
the runner's own intake (`_admit_object`: outer signature,
decrypt, inner signature), and the shapes AGENTS.md's
"Do not emit" table lists must never be produced.
"""
import io
import os
import re
import secrets
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.cloud import send_job  # noqa: E402
from runner.runner import _admit_object  # noqa: E402

SECRET = secrets.token_hex(32)
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class CmdNew(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-q17-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.script = os.path.join(self.tmp, "job.py")
        with open(self.script, "w", encoding="utf-8") as fh:
            fh.write("print('hello from the built job')\n")

    def _new(self, argv, secret=SECRET):
        out, err = io.StringIO(), io.StringIO()
        full = ["send_job.py", "new", "--secret", secret] + argv
        with mock.patch.object(sys, "argv", full):
            with redirect_stdout(out), redirect_stderr(err):
                rc = send_job.main()
        return rc, out.getvalue(), err.getvalue()

    def _built_job(self, argv, secret=SECRET, secrets_map=None):
        rc, out, err = self._new(argv, secret=secret)
        self.assertEqual(rc, 0, err)
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("[HOMING-PIGEON] job "),
                        lines[0])
        job_id = lines[0].rsplit(" ", 1)[1]
        body = "\n".join(lines[2:])
        job, key_id, _secret, encrypted = _admit_object(
            body, secrets_map or {"": secret}, job_id)
        return job, key_id, encrypted, job_id, body

    def test_plain_exec_is_encrypted_and_verifies(self):
        job, key_id, encrypted, job_id, body = self._built_job(
            ["--script-file", self.script])
        self.assertTrue(encrypted)
        # The job carries the key's name by default (Q94): the
        # fingerprint of the secret, which the runner's default key
        # answers to even in a map built by hand as {"": secret}.
        self.assertEqual(key_id, send_job.key_fingerprint(SECRET))
        self.assertEqual(job["key_id"], key_id)
        self.assertEqual(job["job_id"], job_id)
        self.assertEqual(job["kind"], "exec")
        self.assertEqual(job["script"],
                         "print('hello from the built job')\n")
        self.assertEqual(job["timeout_sec"], 300)
        # The script never crosses in the clear.
        self.assertNotIn("hello from the built job", body)
        # AGENTS.md's "Do not emit" shapes, checked on output:
        self.assertTrue(SAFE_ID.match(job_id), job_id)
        self.assertTrue(job["issued_at"].endswith("Z"))

    def test_cleartext_verifies_unencrypted(self):
        job, _kid, encrypted, _jid, body = self._built_job(
            ["--script-file", self.script, "--cleartext"])
        self.assertFalse(encrypted)
        self.assertIn("hello from the built job", body)

    def test_full_exec_option_matrix(self):
        job, key_id, _enc, _jid, _body = self._built_job(
            ["--job-id", "q17-matrix",
             "--script-url", "https://example.com/s.py",
             "--script-sha384", "ab" * 48,
             "--interpreter", '["/usr/bin/python3", "-u"]',
             "--timeout", "30",
             "--file", "data.txt=https://example.com/d.txt",
             "--file", "more.bin=https://example.com/m.bin",
             "--arg", "one", "--arg", "two",
             "--env", "MODE=test", "--env", "EMPTY=",
             "--reply-to", "worker@example.com",
             "--aud", "runner-1",
             "--key-id", "kid-7"],
            secrets_map={"kid-7": SECRET})
        self.assertEqual(key_id, "kid-7")
        self.assertEqual(job["job_id"], "q17-matrix")
        self.assertEqual(job["script_url"],
                         "https://example.com/s.py")
        self.assertEqual(job["script_sha384"], "ab" * 48)
        # The interpreter is a list, never a string (AGENTS.md).
        self.assertEqual(job["interpreter"],
                         ["/usr/bin/python3", "-u"])
        self.assertEqual(job["timeout_sec"], 30)
        self.assertEqual(job["files"], [
            {"name": "data.txt",
             "url": "https://example.com/d.txt"},
            {"name": "more.bin",
             "url": "https://example.com/m.bin"}])
        self.assertEqual(job["args"], ["one", "two"])
        self.assertEqual(job["env"], {"MODE": "test", "EMPTY": ""})
        self.assertEqual(job["reply_to"], "worker@example.com")
        self.assertEqual(job["aud"], "runner-1")
        self.assertEqual(job["key_id"], "kid-7")

    def test_exec_without_a_script_is_refused(self):
        rc, out, err = self._new([])
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("--script-file or --script-url", err)

    def test_a_bad_file_spec_is_refused(self):
        rc, out, err = self._new(
            ["--script-file", self.script,
             "--file", "no-equals-here"])
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("bad --file spec", err)

    def test_ping_needs_no_script_and_carries_no_timeout(self):
        job, _kid, _enc, _jid, _body = self._built_job(
            ["--kind", "ping"])
        self.assertEqual(job["kind"], "ping")
        self.assertNotIn("script", job)
        self.assertNotIn("timeout_sec", job)

    def test_to_file_writes_the_printed_envelope(self):
        target = os.path.join(self.tmp, "job.email.txt")
        rc, out, err = self._new(
            ["--script-file", self.script, "--to-file", target])
        self.assertEqual(rc, 0, err)
        self.assertEqual(out, "")
        with open(target, encoding="utf-8") as fh:
            text = fh.read()
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("[HOMING-PIGEON] job "))
        job_id = lines[0].rsplit(" ", 1)[1]
        job, _kid, encrypted, = _admit_object(
            "\n".join(lines[2:]), {"": SECRET}, job_id)[:3]
        self.assertTrue(encrypted)
        self.assertEqual(job["job_id"], job_id)


class ToFilePublishesAtomically(unittest.TestCase):
    """--to-file must publish the envelope atomically.

    The file transport polls its watched inbox and refuses,
    permanently, any file whose content does not parse at the
    moment it is read: the refusal moves the file into done/
    with a .refused.txt note, no result is ever produced, and
    the job never runs. The --to-file write used to be a plain
    buffered open() at the destination path, so the file was
    visible in the folder from the moment it was created and
    empty until the writer's close flushed it. On a loaded
    machine the writer can sit descheduled inside that window
    for seconds, long enough for a poll to read the empty
    file and refuse a perfectly good envelope. It bit the
    rig battery twice: 2026-11-23, the Linux battery's clock
    step on 640e0452, and 2026-11-24, the same battery's
    memory-ceiling step on a21fd7c1 -- the envelope recovered
    from that inbox's done/ folder was complete and correctly
    signed; only the read timing was wrong. The project's
    rule for its state files is atomicio: a reader sees the
    old file or the new one, never a hole. These tests pin
    the --to-file publish to that rule.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-atomic-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.script = os.path.join(self.tmp, "job.py")
        with open(self.script, "w", encoding="utf-8") as fh:
            fh.write("print('hello from the built job')\n")
        self.target = os.path.join(self.tmp, "job.txt")

    def _new(self, argv, secret=SECRET):
        out, err = io.StringIO(), io.StringIO()
        full = ["send_job.py", "new", "--secret", secret] + argv
        with mock.patch.object(sys, "argv", full):
            with redirect_stdout(out), redirect_stderr(err):
                rc = send_job.main()
        return rc, out.getvalue(), err.getvalue()

    def _publish(self):
        return self._new(["--script-file", self.script,
                          "--to-file", self.target])

    def test_the_destination_is_never_opened_for_writing(self):
        writes = []
        real_open = open

        def guard(file, mode="r", *args, **kwargs):
            try:
                same = (os.path.abspath(os.fspath(file))
                        == os.path.abspath(self.target))
            except TypeError:
                same = False
            if same and any(c in mode for c in "wax+"):
                writes.append(mode)
            return real_open(file, mode, *args, **kwargs)

        with mock.patch("builtins.open", guard):
            rc, _out, err = self._publish()
        self.assertEqual(rc, 0, err)
        self.assertEqual(writes, [])
        self.assertTrue(os.path.exists(self.target))

    def test_the_envelope_goes_through_the_atomic_writer_whole(self):
        calls = []
        real_write_text = send_job._atomicio.write_text

        def spy(path, text, **kwargs):
            calls.append((path, text))
            return real_write_text(path, text, **kwargs)

        with mock.patch.object(send_job._atomicio, "write_text", spy):
            rc, _out, err = self._publish()
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(calls), 1)
        path, text = calls[0]
        self.assertEqual(path, self.target)
        self.assertTrue(text.startswith("[HOMING-PIGEON] job "))
        self.assertIn("\n\n", text)
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))
        with open(self.target, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), text)

    def test_a_preexisting_destination_is_replaced_whole(self):
        with open(self.target, "w", encoding="utf-8") as fh:
            fh.write("X" * 100000)
        rc, _out, err = self._publish()
        self.assertEqual(rc, 0, err)
        with open(self.target, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("X" * 100, text)
        self.assertLess(len(text), 100000)
        self.assertTrue(text.startswith("[HOMING-PIGEON] job "))

    def test_a_failed_publish_leaves_the_previous_file_untouched(self):
        sentinel = "the previous envelope, kept whole\n"
        with open(self.target, "w", encoding="utf-8") as fh:
            fh.write(sentinel)

        def boom(path, text, **kwargs):
            raise OSError("disk full")

        with mock.patch.object(send_job._atomicio, "write_text", boom):
            with self.assertRaises(OSError):
                self._publish()
        with open(self.target, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), sentinel)
        self.assertEqual(sorted(os.listdir(self.tmp)),
                         ["job.py", "job.txt"])

    def test_no_temp_files_are_left_behind(self):
        rc, _out, err = self._publish()
        self.assertEqual(rc, 0, err)
        self.assertEqual(sorted(os.listdir(self.tmp)),
                         ["job.py", "job.txt"])

    @unittest.skipIf(os.name != "posix", "mode bits are POSIX")
    def test_the_published_file_carries_the_atomic_mode(self):
        rc, _out, err = self._publish()
        self.assertEqual(rc, 0, err)
        self.assertEqual(
            oct(os.stat(self.target).st_mode & 0o777), "0o600")


if __name__ == "__main__":
    unittest.main(verbosity=2)
