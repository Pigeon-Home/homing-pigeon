# Agent-Stamp: 90000998-709f-46f5-b2bc-2c3c5cf8dc6c
"""The delivery paths' edges that only the property suites reached.

A box without hypothesis (and every Windows leg that skips those
suites) ran none of these lines. Pinned here with plain unit tests:
the channel refusal sweep on bad input, a stub that cannot be signed
or written, the kept original for an unsafe job id, a record moved
back from sent/ that cannot be written, and the output-file reader on
the cases it names instead of raising.
"""
import json
import os
import shutil
import smtplib
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner import runner as R  # noqa: E402
from runner.ops import exec as X  # noqa: E402

CFG = {"mailbox_user": "runner@example.com",
       "shared_secret": "4298e27808c3de551f9432d959d041b2"
                        "1a9b876526b8cd9bb312517c2c542585"}


class _Base(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-deliv-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.cfg = dict(CFG)
        self.paths = R._transports.ensure_channel_dirs(self.base, "file")
        self.failed = os.path.join(self.paths["outbox"],
                                   R.OUTBOX_FAILED_DIRNAME)
        os.makedirs(self.failed, exist_ok=True)

    def refusal(self, stem, envelope, reason="552 too large"):
        with open(os.path.join(self.failed, stem + ".refused.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write(reason)
        mode = "wb" if isinstance(envelope, bytes) else "w"
        with open(os.path.join(self.failed, stem + ".result.txt"), mode) as fh:
            fh.write(envelope)

    def record(self, job_id, **extra):
        skey = R._seen_key(self.cfg, job_id)
        rec = {"job_id": job_id, "subject": R.SUBJECT_RESULT + job_id,
               "body": "{}", "key_id": "", "stubbed": False, **extra}
        path = R._sent_path(self.base, skey)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        R._atomicio.write_json(path, rec)
        return skey, path

    def sweep(self):
        return R._sweep_channel_refusals(self.base, self.cfg, ["file"])

    def done(self):
        try:
            return sorted(os.listdir(self.paths["outbox_done"]))
        except FileNotFoundError:
            return []


class SweepTest(_Base):
    def test_no_transports_module_or_base_does_nothing(self):
        with mock.patch.object(R, "_transports", None):
            self.assertEqual(self.sweep(), 0)
        self.assertEqual(R._sweep_channel_refusals("", self.cfg, ["file"]), 0)

    def test_a_channel_that_cannot_be_named_is_skipped(self):
        self.refusal("a", R._transports.format_envelope(
            R.SUBJECT_RESULT + "j1", "{}"))
        with mock.patch.object(R._transports, "channel_paths",
                               side_effect=ValueError("bad name")):
            self.assertEqual(self.sweep(), 0)
        self.assertEqual(self.done(), [])

    def test_a_channel_with_no_failed_folder_is_skipped(self):
        shutil.rmtree(self.failed)
        self.assertEqual(self.sweep(), 0)

    def test_bytes_that_are_not_utf8_are_set_aside(self):
        self.refusal("bad", b"\xff\xfe not text")
        self.assertEqual(self.sweep(), 1)
        self.assertEqual(self.done(), ["bad.refused.txt", "bad.result.txt"])
        self.assertEqual(os.listdir(self.failed), [])

    def test_a_result_with_no_job_id_is_set_aside(self):
        self.refusal("nid", R._transports.format_envelope(
            "[HOMING-PIGEON] something else", "{}"))
        self.assertEqual(self.sweep(), 1)
        self.assertEqual(self.done(), ["nid.refused.txt", "nid.result.txt"])

    def test_a_stub_that_cannot_be_signed_gives_the_record_up(self):
        skey, _ = self.record("j-nostub")
        self.refusal("ns", R._transports.format_envelope(
            R.SUBJECT_RESULT + "j-nostub", "{}"))
        with mock.patch.object(R, "_stub_body", return_value=None), \
                mock.patch.object(R, "_stash_fail_sent") as gave_up:
            self.assertEqual(self.sweep(), 1)
        args = gave_up.call_args.args
        self.assertEqual(args[1], skey)
        self.assertIn("no stub could be signed", args[3])

    def test_a_stub_the_channel_will_not_take_waits_for_the_next_pass(self):
        _, path = self.record("j-nowrite")
        self.refusal("nw", R._transports.format_envelope(
            R.SUBJECT_RESULT + "j-nowrite", "{}"))
        with mock.patch.object(R, "_stub_body", return_value="stub"), \
                mock.patch.object(R, "_keep_original_result"), \
                mock.patch.object(R._transports, "write_channel_result",
                                  side_effect=OSError("disk full")):
            self.assertEqual(self.sweep(), 0)
        # Nothing moved and the record is not marked: the next pass
        # tries the same refusal again.
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["nw.refused.txt", "nw.result.txt"])
        self.assertFalse(R._read_record(path).get("stubbed"))

    def test_a_refusal_file_that_will_not_move_still_counts(self):
        self.refusal("stuck", b"\xff")
        with mock.patch.object(R.os, "replace",
                               side_effect=OSError("busy")):
            self.assertEqual(self.sweep(), 1)


class KeptOriginalTest(_Base):
    def test_an_unsafe_job_id_keeps_nothing(self):
        for job_id in (None, 7, "..", ".", "a/b", ""):
            self.assertFalse(R._keep_original_result(
                self.base, {"job_id": job_id}, {}), job_id)
        self.assertFalse(os.path.exists(os.path.join(self.base, "work")))

    def test_a_record_that_does_not_open_keeps_nothing(self):
        with mock.patch.object(R, "_record_payload", return_value=None):
            self.assertFalse(R._keep_original_result(
                self.base, {"job_id": "j1"}, {}))

    def test_a_write_that_fails_is_logged_not_raised(self):
        with mock.patch.object(R, "_record_payload",
                               return_value={"v": 1}), \
                mock.patch.object(R._atomicio, "write_json",
                                  side_effect=OSError("read-only")):
            self.assertFalse(R._keep_original_result(
                self.base, {"job_id": "j1"}, {}))


class StashMoveTest(_Base):
    def test_undeliver_needs_a_base_and_a_record(self):
        self.assertFalse(R.undeliver_stash("", "k", "why"))
        self.assertFalse(R.undeliver_stash(self.base, "nothing-sent", "why"))

    def test_undeliver_that_cannot_write_leaves_the_record_sent(self):
        skey, path = self.record("j-back")
        with mock.patch.object(R._atomicio, "write_json",
                               side_effect=OSError("read-only")):
            self.assertFalse(R.undeliver_stash(self.base, skey, "outbox"))
        self.assertTrue(os.path.exists(path))

    def test_undeliver_counts_the_attempt_and_keeps_the_reason(self):
        skey, path = self.record("j-again", attempts=2)
        self.assertTrue(R.undeliver_stash(self.base, skey, "x" * 900))
        self.assertFalse(os.path.exists(path))
        rec = R._read_record(R._stash_path(self.base, skey))
        self.assertEqual(rec["attempts"], 3)
        self.assertEqual(len(rec["last_error"]), 500)

    def test_a_stash_move_that_fails_says_so(self):
        self.assertFalse(R._stash_move(self.base, "no-such-record",
                                       os.path.join(self.base, "sent")))

    def test_the_job_digest_ignores_the_signature(self):
        with mock.patch.object(R, "_opinion", None):
            a = R._job_digest({"job_id": "j", "sig": "1"})
            b = R._job_digest({"job_id": "j", "sig": "2"})
            self.assertEqual(a, b)
            self.assertNotEqual(a, R._job_digest({"job_id": "k"}))
            self.assertEqual(len(R._job_digest(None)), 96)


class ReadOutputTest(unittest.TestCase):
    def setUp(self):
        self.work = os.path.realpath(tempfile.mkdtemp(prefix="hp-out-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)

    def read(self, name, limit=1000):
        return X._read_output(self.work, self.work, name, limit)

    def write(self, name, data):
        with open(os.path.join(self.work, name), "wb") as fh:
            fh.write(data)

    def test_a_regular_file_reads(self):
        self.write("ok.txt", b"hello")
        self.assertEqual(self.read("ok.txt"), (b"hello", 5, None))

    def test_the_named_refusals(self):
        self.assertEqual(self.read("absent"), (None, 0, "missing"))
        os.mkdir(os.path.join(self.work, "d"))
        self.assertEqual(self.read("d"), (None, 0, "not a regular file"))
        self.write("big", b"x" * 20)
        self.assertEqual(self.read("big", limit=10), (None, 20, "too_large"))
        self.assertEqual(self.read("../escape"),
                         (None, 0, "outside the workdir"))

    def test_a_path_that_will_not_resolve_is_unreadable(self):
        with mock.patch.object(X.os.path, "realpath",
                               side_effect=ValueError("embedded null")):
            self.assertEqual(self.read("x"), (None, 0, "unreadable"))

    def test_an_lstat_that_fails_is_unreadable(self):
        with mock.patch.object(X.os, "lstat",
                               side_effect=PermissionError("denied")):
            self.assertEqual(self.read("x"), (None, 0, "unreadable"))

    def test_an_open_that_fails_is_unreadable(self):
        self.write("locked", b"data")
        with mock.patch.object(X.os, "open",
                               side_effect=PermissionError("denied")):
            self.assertEqual(self.read("locked"), (None, 0, "unreadable"))

    def test_a_file_swapped_between_check_and_open_is_named(self):
        self.write("a", b"one")
        self.write("b", b"two")
        real_lstat = os.lstat
        other = real_lstat(os.path.join(self.work, "b"))
        with mock.patch.object(X.os, "lstat", side_effect=lambda p: other
                               if p.endswith(os.sep + "a") else real_lstat(p)):
            self.assertEqual(self.read("a"), (None, 0, "changed while read"))

    def test_a_file_that_grows_while_read_is_too_large(self):
        self.write("grow", b"x" * 5)
        real_read = os.read
        with mock.patch.object(X.os, "read", side_effect=lambda fd, n:
                               real_read(fd, n) * 4):
            got = self.read("grow", limit=10)
        self.assertEqual((got[0], got[2]), (None, "too_large"))


class StashRecordTest(_Base):
    def stash(self, job_id, **extra):
        skey = R._seen_key(self.cfg, job_id)
        rec = {"job_id": job_id, "subject": R.SUBJECT_RESULT + job_id,
               "body": "{}", "key_id": "", **extra}
        os.makedirs(R._outbox_dir(self.base), exist_ok=True)
        R._atomicio.write_json(R._stash_path(self.base, skey), rec)
        return skey

    def refuse(self, *a):
        raise smtplib.SMTPDataError(552, b"too large")

    def test_a_stub_refused_too_is_given_up(self):
        skey = self.stash("j-twice", stubbed=True)
        with mock.patch.object(R, "_stash_fail") as gave_up:
            self.assertFalse(R.deliver_stash(self.base, skey, self.refuse,
                                             self.cfg))
        self.assertIn("stub was refused too", gave_up.call_args.args[3])

    def test_a_refusal_with_no_stub_is_given_up(self):
        skey = self.stash("j-nokey")
        with mock.patch.object(R, "_stub_body", return_value=None), \
                mock.patch.object(R, "_stash_fail") as gave_up:
            self.assertFalse(R.deliver_stash(self.base, skey, self.refuse,
                                             self.cfg))
        self.assertIn("no stub could be signed", gave_up.call_args.args[3])

    def test_a_rewrite_that_fails_is_logged_not_raised(self):
        with mock.patch.object(R._atomicio, "write_json",
                               side_effect=OSError("read-only")):
            R._stash_rewrite(self.base, "k", {"job_id": "j"})

    def test_the_delivery_audit_never_raises(self):
        with mock.patch.object(R, "_security", None):
            R._delivery_audit(self.base, "failed", "why", "j")
        with mock.patch.object(R._security, "write_audit_entry",
                               side_effect=OSError("full")):
            R._delivery_audit(self.base, "failed", "why", "j")

    def test_an_ack_rollback_only_logs(self):
        out = R.process_transport_message(
            self.cfg, self.base, {}, {}, None, "[HOMING-PIGEON] other",
            "{}", None, transport="file")
        with mock.patch.object(R, "log") as log:
            out.rollback(["k1", "k2"])
        self.assertEqual(log.call_count, 2)


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.work = os.path.realpath(tempfile.mkdtemp(prefix="hp-ws-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)

    def sweep(self):
        R._sweep_workspace(self.work, self.work, "after staging")

    def test_an_entry_that_cannot_be_read_is_refused(self):
        open(os.path.join(self.work, "f"), "w").close()
        with mock.patch.object(R.os, "lstat",
                               side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(R.JobRejected, "cannot be read"):
                self.sweep()

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX only")
    def test_a_fifo_is_not_a_regular_file(self):
        os.mkfifo(os.path.join(self.work, "pipe"))
        with self.assertRaisesRegex(R.JobRejected,
                                    "not a regular file or directory"):
            self.sweep()

    def test_an_entry_resolving_outside_is_refused(self):
        open(os.path.join(self.work, "f"), "w").close()
        with mock.patch.object(R.os.path, "realpath",
                               return_value=os.path.sep + "elsewhere"):
            with self.assertRaisesRegex(R.JobRejected,
                                        "resolves outside"):
                self.sweep()

    def test_a_parent_that_cannot_be_made_is_refused(self):
        with mock.patch.object(R.os, "makedirs",
                               side_effect=OSError("read-only")):
            with self.assertRaisesRegex(R.JobRejected,
                                        "cannot create the directory"):
                R._staged_dest(self.work, "a/b.txt", self.work)


if __name__ == "__main__":
    unittest.main()
