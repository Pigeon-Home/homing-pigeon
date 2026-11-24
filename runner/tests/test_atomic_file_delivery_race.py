#!/usr/bin/env python3
"""The atomic file delivery race, pinned at the real boundary.

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

`send_job --to-file` publishes its envelope into the file
transport's watched inbox through guard/atomicio, whose staging
file lives in that same directory under a reserved name until
the rename. FilePipe.scan_jobs used to process every regular
file it found, staging files included: a scan after staging
creation consumed the empty temp as a malformed envelope and
the writer's rename died with FileNotFoundError (the job was
lost); a scan after the write but before the rename delivered
the complete temp, and the renamed final file delivered the
same job a second time.

These tests force both interleavings deterministically -- no
sleeps -- by wrapping the sender's own atomicio hooks so the
real FilePipe.scan_jobs runs at the exact staging moment, and
they pin the fix around them: the reserved-name definition,
the near-miss names that are NOT reserved, the abandoned temp
rule (a scanner never deletes a temp), failure cleanup, and
the existing-file case. The supposition and the outcome stand
in docs/infrastructure-documents/project/
atomic-file-delivery-race-2026-11-23.md.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.cloud import send_job  # noqa: E402
from runner.guard import atomicio  # noqa: E402
import importlib  # noqa: E402

file_main = importlib.import_module(
    "runner.transport_extensions.file.__main__")
FilePipe = file_main.FilePipe

SECRET = ("9f3ac41e7b02d58a" "c61e904bf27a3d85"
          "1e6b09d4a83fc257" "6d190be42f7ac938")
ENVELOPE = "[HOMING-PIGEON] job race-1\n\nsigned-body\n"


class _Boundary:
    """One watched inbox, one channel, one sender target."""

    def __init__(self, test):
        self.tmp = tempfile.mkdtemp(prefix="hp-race-")
        test.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.script = os.path.join(self.tmp, "job.py")
        with open(self.script, "w", encoding="utf-8") as fh:
            fh.write("print('hello from the raced job')\n")
        self.channel = os.path.join(self.tmp, "channel")
        self.pipe = FilePipe(
            {"base_dir": self.tmp, "inbox_dir": "watched-in",
             "outbox_dir": "watched-out"}, self.channel)
        self.target = os.path.join(self.pipe.inbox, "job.txt")

    def send(self):
        argv = ["send_job.py", "new", "--secret", SECRET,
                "--script-file", self.script,
                "--to-file", self.target]
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", argv):
            with redirect_stdout(out), redirect_stderr(err):
                rc = send_job.main()
        return rc, err.getvalue()

    def channel_jobs(self):
        inbox = os.path.join(self.channel, "inbox")
        if not os.path.isdir(inbox):
            return []
        return sorted(n for n in os.listdir(inbox)
                      if n.endswith(".job.txt"))

    def inbox_names(self):
        return sorted(os.listdir(self.pipe.inbox))

    def done_names(self):
        return sorted(os.listdir(self.pipe.done))


class ScanAfterTempCreationTest(unittest.TestCase):
    """Interleaving 1: the scan lands after the staging file is
    created, before its first byte is written."""

    def test_the_scan_leaves_the_staging_file_and_the_job_lands(self):
        b = _Boundary(self)
        seen = {}
        real_open_new = send_job._atomicio._open_new

        def hooked(path, mode):
            fd = real_open_new(path, mode)
            b.pipe.scan_jobs()
            seen["during_pending"] = dict(b.pipe._pending)
            seen["during_channel"] = b.channel_jobs()
            seen["during_inbox"] = b.inbox_names()
            seen["during_done"] = b.done_names()
            seen["temp_name"] = os.path.basename(path)
            return fd

        with mock.patch.object(send_job._atomicio, "_open_new",
                               hooked):
            rc, err = b.send()
        self.assertEqual(rc, 0, err)
        # The forced scan consumed and delivered nothing, and
        # the staging file stayed in the inbox under its name.
        self.assertEqual(seen["during_pending"], {})
        self.assertEqual(seen["during_channel"], [])
        self.assertIn(seen["temp_name"], seen["during_inbox"])
        self.assertEqual(seen["during_done"], [])
        # The sender completed and the final file stands whole.
        self.assertTrue(os.path.exists(b.target))
        self.assertNotIn(seen["temp_name"], b.inbox_names())
        # A later scan delivers the final envelope exactly once.
        b.pipe.scan_jobs()
        self.assertEqual(sorted(b.pipe._pending), ["job"])
        self.assertEqual(len(b.channel_jobs()), 1)
        b.pipe.scan_jobs()
        self.assertEqual(len(b.channel_jobs()), 1)


class ScanAfterWriteBeforeRenameTest(unittest.TestCase):
    """Interleaving 2: the scan lands after the staging file is
    fully written, before the rename publishes it."""

    def test_no_duplicate_enqueue_at_the_boundary(self):
        b = _Boundary(self)
        seen = {}
        real_replace = send_job._atomicio._replace
        fired = []

        def hooked(tmp, path):
            if not fired:
                fired.append(True)
                b.pipe.scan_jobs()
                seen["during_pending"] = dict(b.pipe._pending)
                seen["during_channel"] = b.channel_jobs()
                seen["during_inbox"] = b.inbox_names()
            return real_replace(tmp, path)

        with mock.patch.object(send_job._atomicio, "_replace",
                               hooked):
            rc, err = b.send()
        self.assertEqual(rc, 0, err)
        # The complete staging file was NOT delivered under its
        # staging name: no pending entry, no channel copy.
        self.assertEqual(seen["during_pending"], {})
        self.assertEqual(seen["during_channel"], [])
        self.assertTrue(any(atomicio.is_temp_name(n)
                            for n in seen["during_inbox"]))
        # After publication, exactly one delivery of the job.
        b.pipe.scan_jobs()
        self.assertEqual(sorted(b.pipe._pending), ["job"])
        self.assertEqual(b.channel_jobs(), ["job.job.txt"])
        b.pipe.scan_jobs()
        self.assertEqual(b.channel_jobs(), ["job.job.txt"])


class AbandonedTempTest(unittest.TestCase):
    """The abandoned temp rule: a scanner never consumes and
    never deletes a staging file, empty or complete, however
    many times it scans."""

    def _plant(self, b, name, text):
        with open(os.path.join(b.pipe.inbox, name), "w",
                  encoding="utf-8") as fh:
            fh.write(text)

    def test_an_empty_orphan_temp_is_left_alone(self):
        b = _Boundary(self)
        name = "job.txt.tmp.4242.777.0123abcd"
        self._plant(b, name, "")
        for _ in range(3):
            b.pipe.scan_jobs()
        self.assertIn(name, b.inbox_names())
        self.assertEqual(b.done_names(), [])
        self.assertEqual(b.pipe._pending, {})
        self.assertEqual(b.channel_jobs(), [])

    def test_a_complete_orphan_temp_is_left_alone(self):
        b = _Boundary(self)
        name = "job.txt.tmp.4242.777.89abcdef"
        self._plant(b, name, ENVELOPE)
        for _ in range(3):
            b.pipe.scan_jobs()
        self.assertIn(name, b.inbox_names())
        self.assertEqual(b.done_names(), [])
        self.assertEqual(b.pipe._pending, {})
        self.assertEqual(b.channel_jobs(), [])


class ReservedNameTest(unittest.TestCase):
    """The reserved convention itself: exactly the names
    atomicio builds, and nothing beside them."""

    def test_every_generated_temp_name_is_reserved(self):
        for dest in ("job.txt", "a", "x.y.z", "job-1.email.txt",
                     "UPPER.TXT", "with space.txt"):
            for _ in range(4):
                name = atomicio._temp_name(dest)
                self.assertTrue(atomicio.is_temp_name(name), name)
                self.assertTrue(
                    atomicio.is_temp_name(
                        os.path.join("some", "dir", name)), name)

    def test_near_miss_names_are_not_reserved(self):
        for name in (
                "job.txt",
                "job.txt.tmp",
                "job.txt.tmp.123.456.abcdef1",      # nonce short
                "job.txt.tmp.123.456.abcdef123",    # nonce long
                "job.txt.tmp.123.456.abcdefg1",     # nonce not hex
                "job.txt.tmp.123.456.ABCDEF12",     # nonce uppercase
                "job.txt.tmp.12a.456.abcdef12",     # pid not decimal
                "job.txt.tmp.123.45b.abcdef12",     # thread not decimal
                "job.txt.tmpx.123.456.abcdef12",    # marker misspelled
                "job.txt.tmp.123.456.abcdef12.bak",  # suffix not at end
                ".tmp.123.456.abcdef12",            # no stem
                "job.tmp.txt",
                "done",
                ""):
            self.assertFalse(atomicio.is_temp_name(name), name)

    def test_a_near_miss_file_is_processed_not_ignored(self):
        b = _Boundary(self)
        name = "job.txt.tmp.123.456.ABCDEF12"
        with open(os.path.join(b.pipe.inbox, name), "w",
                  encoding="utf-8") as fh:
            fh.write(ENVELOPE)
        b.pipe.scan_jobs()
        # Delivered, not ignored: it stands in _pending (the
        # watched file itself moves only when the result lands,
        # like every delivered job) with one channel copy.
        self.assertIn(name, b.pipe._pending)
        self.assertEqual(len(b.channel_jobs()), 1)

    def test_a_near_miss_malformed_file_is_refused_not_ignored(self):
        b = _Boundary(self)
        name = "job.txt.tmp.123.456.abcdef123"
        with open(os.path.join(b.pipe.inbox, name), "w",
                  encoding="utf-8") as fh:
            fh.write("no blank line here\n")
        b.pipe.scan_jobs()
        self.assertIn(name, b.done_names())
        self.assertIn(name + ".refused.txt", b.done_names())


class FailureAndExistingFileTest(unittest.TestCase):
    """Failure cleanup and the existing-file case, at the same
    boundary."""

    def test_a_failed_publish_leaves_no_temp_and_no_final(self):
        b = _Boundary(self)

        def boom(tmp, path):
            raise OSError("rename refused")

        with mock.patch.object(send_job._atomicio, "_replace",
                               boom):
            with self.assertRaises(OSError):
                b.send()
        self.assertFalse(os.path.exists(b.target))
        self.assertEqual(
            [n for n in b.inbox_names() if n != "done"], [])
        b.pipe.scan_jobs()
        self.assertEqual(b.pipe._pending, {})
        self.assertEqual(b.channel_jobs(), [])

    def test_a_write_failure_cleans_its_temp(self):
        b = _Boundary(self)
        dest = os.path.join(b.pipe.inbox, "direct.txt")
        with mock.patch.object(atomicio.os, "write",
                               side_effect=OSError("disk gone")):
            with self.assertRaises(OSError):
                atomicio.write_text(dest, "payload\n")
        self.assertFalse(os.path.exists(dest))
        self.assertEqual(
            [n for n in b.inbox_names() if n != "done"], [])

    def test_publish_over_an_existing_file_replaces_it_whole(self):
        b = _Boundary(self)
        with open(b.target, "w", encoding="utf-8") as fh:
            fh.write("[HOMING-PIGEON] job old-0\n\nold-body\n")
        rc, err = b.send()
        self.assertEqual(rc, 0, err)
        with open(b.target, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("old-0", text)
        self.assertTrue(
            text.startswith("[HOMING-PIGEON] job "))
        b.pipe.scan_jobs()
        self.assertEqual(sorted(b.pipe._pending), ["job"])
        self.assertEqual(len(b.channel_jobs()), 1)

    def test_a_failed_publish_keeps_the_existing_file(self):
        b = _Boundary(self)
        with open(b.target, "w", encoding="utf-8") as fh:
            fh.write(ENVELOPE)

        def boom(tmp, path):
            raise OSError("rename refused")

        with mock.patch.object(send_job._atomicio, "_replace",
                               boom):
            with self.assertRaises(OSError):
                b.send()
        with open(b.target, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), ENVELOPE)
        self.assertEqual(
            [n for n in b.inbox_names()
             if n not in ("done", "job.txt")], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
