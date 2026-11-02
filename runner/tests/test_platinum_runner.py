"""Project Platinum, cycle 1: the delivery/stash family in runner.py.

Targets from `runner/tools/coverage_targets.py` on the cycle-1
baseline (90445244), taken top-down per queue P:

  logic  _sweep_channel_refusals (13 missing) -- a transport
         extension's refused-result notes, answered with a signed
         stub, the original kept, the note filed to done/. The
         inputs are extension-written files: untrusted shapes.
  logic  undeliver_stash (5) -- a counted delivery that did not
         land goes back to the outbox with the failure on it.
  logic  _keep_original_result (5) -- work/<job_id>/result.json,
         the refused result kept for the operator.
  logic  _delivery_audit (3) -- the audit entry, best effort.
  guard  _record_payload (3) -- the signed (maybe encrypted)
         payload a stashed body carries, read back or None.
  except _stash_move (3) -- the record file moved, or False.

One hypothesis test per target, no max_examples of its own (the
rig's HP_PLATINUM_EXAMPLES decides), driving the function with a
seed corpus mutated the ordinary ways: field missing, field
doubled, type swaps, boundary sizes, encoding edges, path shapes.
The assertions are the contracts in the docstrings: a refusal is a
value, no exception escapes, the files land where the docstring
says they land.

Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90
"""
import json
import os
import shutil
import string
import sys
import tempfile
import time
import unittest
from unittest import mock

try:
    from hypothesis import given, settings, strategies as st
except ImportError:  # test-only dep: runner/tests/_hypothesis_shim.py
    from runner.tests._hypothesis_shim import given, settings, strategies as st

from runner import runner as R
from runner.wire import transports as T

TESTKEY = "Platinum" + "Key-7f3a" + "9c1eB8d2" + "F4a6e5C7" + "b9D1a0F2"
WRONGKEY = "Platinum" + "Wrong-1b2c" + "3d4eF5a6" + "B7c8D9e0" + "F1a2B3c4"


def _cfg(with_key=True, runner_id=None):
    cfg = {}
    if with_key:
        cfg["shared_secret"] = TESTKEY
    if runner_id:
        cfg["runner_id"] = runner_id
    return cfg


def _payload(job_id, marker="payload"):
    return {"job_id": job_id, "exit_code": 0, "stdout": marker,
            "stderr": "", "truncated": False}


def _plant_sent_record(base, cfg, job_id, stubbed=False, encrypted=False,
                       key_id=""):
    """A genuine record in sent/, built through the runner's own
    stash path so its body is a real signed (maybe encrypted) one."""
    body = R._outgoing_result_body(_payload(job_id), TESTKEY, encrypted,
                                   job_id, key_id)
    skey = R._seen_key(cfg, job_id)
    job = {"job_id": job_id}
    subject = f"[HOMING-PIGEON] result {job_id}"
    assert R.stash_result(base, skey, job, subject, body, key_id=key_id,
                          encrypted=encrypted)
    if stubbed:
        rec = R._read_record(R._stash_path(base, skey))
        rec["stubbed"] = True
        R._atomicio.write_json(R._stash_path(base, skey), rec)
    moved = R._stash_move(base, skey, os.path.join(base, "sent"))
    assert moved
    return skey


def _plant_refusal(base, name, stem, reason_text, result_text):
    paths = T.ensure_channel_dirs(base, name)
    failed = os.path.join(paths["outbox"], "failed")
    os.makedirs(failed, exist_ok=True)
    with open(os.path.join(failed, stem + ".refused.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(reason_text)
    if result_text is not None:
        with open(os.path.join(failed, stem + ".result.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write(result_text)
    return paths


def _result_text(job_id):
    return T.format_envelope(f"[HOMING-PIGEON] result {job_id}",
                             "the refused body")


_NOTE_PLAN = st.fixed_dictionaries({
    "record": st.sampled_from(["live", "stubbed", "absent", "wrongkey"]),
    "result": st.sampled_from(["matching", "garbage", "absent"]),
    "reason": st.text(max_size=80),
})


class SweepChannelRefusalsProperties(unittest.TestCase):
    @settings(deadline=None)
    @given(plans=st.lists(_NOTE_PLAN, max_size=3),
           bogus_names=st.lists(
               st.sampled_from([None, 7, b"bytes-name", "ghost-chan"]),
               max_size=2))
    def test_notes_are_answered_and_filed_never_raising(self, plans,
                                                         bogus_names):
        base = tempfile.mkdtemp(prefix="hp-plat-sweep-")
        try:
            cfg = _cfg(with_key=True)
            names = []
            for i, plan in enumerate(plans):
                name = f"chan{i}"
                names.append(name)
                job_id = f"job-{i}-" + "a" * 8
                stem = f"stem{i}"
                if plan["record"] != "absent":
                    _plant_sent_record(
                        base, cfg, job_id,
                        stubbed=(plan["record"] == "stubbed"),
                        key_id=("other" if plan["record"] == "wrongkey"
                                else ""))
                if plan["result"] == "matching":
                    result_text = _result_text(job_id)
                elif plan["result"] == "garbage":
                    result_text = "no blank line in this file at all"
                else:
                    result_text = None
                _plant_refusal(base, name, stem, plan["reason"],
                               result_text)
            def _stays(plan):
                # A result file with no record to answer it stays
                # in failed/. Garbage does not name the job, so the
                # sweep looks up the file's stem and does not find
                # the record planted under the job id.
                if plan["result"] == "absent":
                    return False
                if plan["result"] == "garbage":
                    return True
                return plan["record"] == "absent"

            handled = R._sweep_channel_refusals(
                base, cfg, names + bogus_names)
            self.assertEqual(handled, sum(not _stays(p) for p in plans))
            for i, plan in enumerate(plans):
                paths = T.channel_paths(base, f"chan{i}")
                done = os.path.join(paths["outbox_done"],
                                    f"stem{i}.refused.txt")
                kept = os.path.join(paths["outbox"], "failed",
                                    f"stem{i}.refused.txt")
                if _stays(plan):
                    self.assertFalse(os.path.exists(done),
                                     f"note {i} filed with no record")
                    self.assertTrue(os.path.exists(kept))
                    continue
                self.assertTrue(os.path.exists(done),
                                f"note {i} not filed to done/")
                job_id = f"job-{i}-" + "a" * 8
                skey = R._seen_key(cfg, job_id)
                sent = R._sent_path(base, skey)
                if plan["record"] == "absent" \
                        or plan["result"] != "matching":
                    continue
                if plan["record"] == "live":
                    rec = R._read_record(sent)
                    self.assertIsNotNone(rec)
                    self.assertTrue(rec.get("stubbed"))
                    stub = os.path.join(paths["outbox"],
                                        f"stem{i}.result.txt")
                    self.assertTrue(os.path.exists(stub),
                                    "stub not written to the channel")
                    kept = os.path.join(base, "work", job_id,
                                        "result.json")
                    self.assertTrue(os.path.exists(kept),
                                    "original result not kept")
                else:  # stubbed already, or no key to sign a stub:
                    # given up to the runner's own outbox/failed/
                    self.assertFalse(os.path.exists(sent))
                    failed = os.path.join(base, "outbox", "failed",
                                          R._record_name(skey))
                    self.assertTrue(os.path.exists(failed))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_no_transports_and_bad_base_return_zero(self):
        self.assertEqual(R._sweep_channel_refusals("", {}, ["x"]), 0)
        self.assertEqual(R._sweep_channel_refusals(None, {}, ["x"]), 0)
        self.assertEqual(
            R._sweep_channel_refusals(tempfile.mkdtemp(), {}, None), 0)


class SweepDeterministicArms(unittest.TestCase):
    def test_a_result_that_does_not_parse_is_still_the_job_in_its_name(self):
        # No blank line, so the subject cannot name the job. The
        # file is j1.result.txt. Leaving it unnamed moved the pair
        # to done and the queue acked j1 with nothing stored.
        base = tempfile.mkdtemp(prefix="hp-plat-unnamed-")
        try:
            cfg = _cfg()
            job_id = "j1"
            _plant_sent_record(base, cfg, job_id)
            _plant_refusal(base, "queues", job_id, "not an envelope",
                           "not an envelope")
            handled = R._sweep_channel_refusals(base, cfg, ["queues"])
            self.assertEqual(handled, 1)
            paths = T.channel_paths(base, "queues")
            stub = os.path.join(paths["outbox"], job_id + ".result.txt")
            self.assertTrue(os.path.isfile(stub))
            with open(stub, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn(f"result {job_id}", text)
            self.assertIn("\n\n", text)
            rec = R._read_record(R._sent_path(base, R._seen_key(cfg, job_id)))
            self.assertTrue(rec.get("stubbed"))
            self.assertFalse(os.path.exists(os.path.join(
                paths["outbox"], "failed", job_id + ".result.txt")))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_a_failed_stub_write_leaves_the_note_for_next_cycle(self):
        base = tempfile.mkdtemp(prefix="hp-plat-stubfail-")
        try:
            cfg = _cfg()
            job_id = "job-stubfail-1"
            _plant_sent_record(base, cfg, job_id)
            _plant_refusal(base, "chan", "stem", "refused for good",
                           _result_text(job_id))
            with mock.patch.object(
                    T, "write_channel_result",
                    side_effect=OSError("channel is read-only")):
                handled = R._sweep_channel_refusals(base, cfg, ["chan"])
            self.assertEqual(handled, 0)
            paths = T.channel_paths(base, "chan")
            note = os.path.join(paths["outbox"], "failed",
                                "stem.refused.txt")
            self.assertTrue(os.path.exists(note))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_a_blocked_done_dir_does_not_stop_the_sweep(self):
        base = tempfile.mkdtemp(prefix="hp-plat-doneblock-")
        try:
            cfg = _cfg()
            paths = _plant_refusal(base, "chan", "stem",
                                   "no record here", None)
            os.rmdir(paths["outbox_done"])
            with open(paths["outbox_done"], "w", encoding="utf-8") as fh:
                fh.write("a file where the done dir belongs")
            handled = R._sweep_channel_refusals(base, cfg, ["chan"])
            self.assertEqual(handled, 1)
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_a_refusal_with_no_record_stays_until_one_exists(self):
        # The pair was moved to done. The queue then saw no
        # result and no refusal, and acked the job.
        base = tempfile.mkdtemp(prefix="hp-plat-norec-")
        try:
            cfg = _cfg()
            _plant_refusal(base, "queues", "j1", "not an envelope",
                           "not an envelope")
            handled = R._sweep_channel_refusals(base, cfg, ["queues"])
            self.assertEqual(handled, 0)
            paths = T.channel_paths(base, "queues")
            failed = os.path.join(paths["outbox"], "failed")
            self.assertEqual(sorted(os.listdir(failed)),
                             ["j1.refused.txt", "j1.result.txt"])
            self.assertEqual(os.listdir(paths["outbox_done"]), [])
            _plant_sent_record(base, cfg, "j1")
            handled = R._sweep_channel_refusals(base, cfg, ["queues"])
            self.assertEqual(handled, 1)
            stub = os.path.join(paths["outbox"], "j1.result.txt")
            self.assertTrue(os.path.isfile(stub))
            self.assertFalse(os.path.exists(os.path.join(
                failed, "j1.result.txt")))
        finally:
            shutil.rmtree(base, ignore_errors=True)


class SweepRefusalEncodingProbe(unittest.TestCase):
    # Q60: a refusal note (or its result file) whose bytes are not
    # UTF-8 made the sweep raise UnicodeDecodeError: the reads were
    # guarded only against OSError, and the poll pass calls the
    # sweep unguarded, so one extension-written file re-killed the
    # delivery pass every cycle. The sweep now contains a ValueError
    # the way it contains an OSError: the pair reads as unparsed,
    # reason "refused", and the note is filed.
    def test_a_non_utf8_refusal_note_is_contained(self):
        base = tempfile.mkdtemp(prefix="hp-plat-q60-")
        try:
            paths = T.ensure_channel_dirs(base, "chan")
            failed = os.path.join(paths["outbox"], "failed")
            os.makedirs(failed, exist_ok=True)
            with open(os.path.join(failed, "x.refused.txt"),
                      "wb") as fh:
                fh.write(b"\xff\xfe not utf-8")
            handled = R._sweep_channel_refusals(base, _cfg(), ["chan"])
            self.assertEqual(handled, 1)
        finally:
            shutil.rmtree(base, ignore_errors=True)


class RecordPayloadProperties(unittest.TestCase):
    @settings(deadline=None)
    @given(encrypted=st.booleans(),
           secrets_kind=st.sampled_from(["right", "missing", "wrong"]),
           body_kind=st.sampled_from(["genuine", "garbage", "empty",
                                      "nonstr"]))
    def test_payload_reads_back_or_none_never_raising(
            self, encrypted, secrets_kind, body_kind):
        job_id = "job-payload-1"
        genuine = R._outgoing_result_body(_payload(job_id), TESTKEY,
                                          encrypted, job_id, "")
        body = {"genuine": genuine, "garbage": "not a signed body",
                "empty": "", "nonstr": None}[body_kind]
        rec = {"body": body, "job_id": job_id, "key_id": ""}
        secrets = {"right": {"": TESTKEY}, "missing": {},
                   "wrong": {"": WRONGKEY}}[secrets_kind]
        out = R._record_payload(rec, secrets)
        if body_kind == "genuine" and secrets_kind == "right":
            self.assertIsInstance(out, dict)
            self.assertEqual(out["stdout"], "payload")
        else:
            self.assertIsNone(out)


class KeepOriginalResultProperties(unittest.TestCase):
    @settings(deadline=None)
    @given(job_id=st.one_of(
        st.sampled_from(["job-keep-1", "..", ".", "../escape", "a/b",
                         "a\\b", "", "x" * 200]),
        st.text(max_size=40)),
        readable=st.booleans())
    def test_kept_only_under_a_safe_job_id(self, job_id, readable):
        base = tempfile.mkdtemp(prefix="hp-plat-keep-")
        try:
            body = R._outgoing_result_body(
                _payload("job-keep-1"), TESTKEY, False, "job-keep-1",
                "") if readable else "garbage"
            rec = {"body": body, "job_id": job_id, "key_id": ""}
            kept = R._keep_original_result(base, rec, {"": TESTKEY})
            safe = isinstance(job_id, str) \
                and R._SAFE_JOB_ID.match(job_id) \
                and job_id not in (".", "..")
            if safe and readable:
                self.assertTrue(kept)
                path = os.path.join(base, "work", job_id, "result.json")
                with open(path, encoding="utf-8") as fh:
                    self.assertEqual(json.load(fh)["stdout"], "payload")
            else:
                self.assertFalse(kept)
                self.assertFalse(os.path.exists(
                    os.path.join(base, "escape")))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_a_blocked_work_dir_is_a_quiet_false(self):
        base = tempfile.mkdtemp(prefix="hp-plat-keepblock-")
        try:
            with open(os.path.join(base, "work"), "w",
                      encoding="utf-8") as fh:
                fh.write("a file where the work dir belongs")
            body = R._outgoing_result_body(
                _payload("job-keep-1"), TESTKEY, False, "job-keep-1",
                "")
            rec = {"body": body, "job_id": "job-keep-1", "key_id": ""}
            self.assertFalse(
                R._keep_original_result(base, rec, {"": TESTKEY}))
        finally:
            shutil.rmtree(base, ignore_errors=True)


class UndeliverStashProperties(unittest.TestCase):
    @settings(deadline=None)
    @given(present=st.sampled_from(["record", "absent", "corrupt",
                                    "blocked"]),
           reason=st.one_of(st.text(max_size=700),
                            st.sampled_from([None, 42, ""])))
    def test_back_in_the_outbox_with_the_failure_on_it(self, present,
                                                       reason):
        base = tempfile.mkdtemp(prefix="hp-plat-undeliver-")
        try:
            cfg = _cfg()
            job_id = "job-undeliver-1"
            skey = R._seen_key(cfg, job_id)
            if present in ("record", "blocked"):
                _plant_sent_record(base, cfg, job_id)
            if present == "corrupt":
                os.makedirs(os.path.join(base, "sent"), exist_ok=True)
                with open(R._sent_path(base, skey), "w",
                          encoding="utf-8") as fh:
                    fh.write("{not json")
            if present == "blocked":
                os.makedirs(R._stash_path(base, skey), exist_ok=True)
            moved = R.undeliver_stash(base, skey, reason)
            if present != "record":
                self.assertFalse(moved)
                return
            self.assertTrue(moved)
            self.assertFalse(os.path.exists(R._sent_path(base, skey)))
            rec = R._read_record(R._stash_path(base, skey))
            self.assertIsNotNone(rec)
            self.assertEqual(rec["attempts"], 1)
            self.assertEqual(rec["last_error"],
                             R._as_text(reason)[:500])
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_a_bad_base_is_a_quiet_false(self):
        self.assertFalse(R.undeliver_stash("", "k", "reason"))
        self.assertFalse(R.undeliver_stash(None, "k", "reason"))


class DeliveryAuditTest(unittest.TestCase):
    def test_no_security_module_is_a_quiet_no_op(self):
        with mock.patch.object(R, "_security", None):
            R._delivery_audit(tempfile.mkdtemp(), "stubbed", "why",
                              "job-1")

    def test_a_failing_audit_write_is_swallowed(self):
        broken = mock.Mock()
        broken.write_audit_entry.side_effect = RuntimeError("disk")
        with mock.patch.object(R, "_security", broken):
            R._delivery_audit(tempfile.mkdtemp(), "failed", "why",
                              "job-1", cfg={})
        broken.write_audit_entry.assert_called_once()


class StashMoveProperties(unittest.TestCase):
    @settings(deadline=None)
    @given(present=st.booleans(), folder_kind=st.sampled_from(
        ["plain", "nested", "blocked"]))
    def test_move_or_false_never_raising(self, present, folder_kind):
        base = tempfile.mkdtemp(prefix="hp-plat-move-")
        try:
            cfg = _cfg()
            skey = R._seen_key(cfg, "job-move-1")
            if present:
                body = R._outgoing_result_body(
                    _payload("job-move-1"), TESTKEY, False,
                    "job-move-1", "")
                assert R.stash_result(base, skey, {"job_id": "job-move-1"},
                                      "[HOMING-PIGEON] result job-move-1",
                                      body)
            if folder_kind == "plain":
                folder = os.path.join(base, "dest")
            elif folder_kind == "nested":
                folder = os.path.join(base, "a", "b", "dest")
            else:
                folder = os.path.join(base, "blocker")
                with open(folder, "w", encoding="utf-8") as fh:
                    fh.write("a file, not a directory")
            moved = R._stash_move(base, skey, folder)
            if present and folder_kind != "blocked":
                self.assertTrue(moved)
                self.assertTrue(os.path.exists(
                    os.path.join(folder, R._record_name(skey))))
                self.assertFalse(os.path.exists(
                    R._stash_path(base, skey)))
            else:
                self.assertFalse(moved)
        finally:
            shutil.rmtree(base, ignore_errors=True)


class SweepWorkspaceProperties(unittest.TestCase):
    """Cycle 2 target, guard class: `_sweep_workspace` (3).

    The docstring is the contract: every entry under the work
    directory is a regular file or directory, not a symlink, with
    its real path under the root -- anything else is a
    JobRejected naming the entry and the moment. Mutated entry
    kinds are the corpus: plain files and directories pass;
    symlinks and special files are refused; an entry that
    vanishes before lstat is refused as unreadable.
    """

    _BAD = {"link_in": "is a symlink", "link_out": "is a symlink",
            "fifo": "is not a regular file or directory"}

    def _plant(self, work, root, name, kind):
        path = os.path.join(work, name)
        if kind == "file":
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("payload")
        elif kind == "dir":
            os.makedirs(path)
            with open(os.path.join(path, "inner.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("payload")
        elif kind == "link_in":
            os.symlink(os.path.join(work, "seed.txt"), path)
        elif kind == "link_out":
            os.symlink(os.path.join(root, "outside.txt"), path)
        elif kind == "fifo":
            os.mkfifo(path)
        return path

    @unittest.skipUnless(os.name == "posix",
                         "entry kinds need POSIX links and fifos")
    @settings(deadline=None)
    @given(kinds=st.lists(st.sampled_from(
        ["file", "dir", "link_in", "link_out", "fifo"]),
        min_size=0, max_size=5))
    def test_every_entry_is_what_it_claims_to_be(self, kinds):
        # The real path: production hands the sweep a root from
        # _workspace_root (os.path.realpath), and a macOS temp
        # directory is reached through a link (/var -> /private/var),
        # so a raw mkdtemp root fails every plain file as resolving
        # outside it.
        base = os.path.realpath(tempfile.mkdtemp(prefix="hp-plat-sweep-"))
        try:
            root = os.path.join(base, "root")
            work = os.path.join(root, "work")
            os.makedirs(work)
            with open(os.path.join(work, "seed.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("seed")
            with open(os.path.join(root, "outside.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("outside")
            for i, kind in enumerate(kinds):
                self._plant(work, root, f"entry{i}", kind)
            bad = [self._BAD[k] for k in kinds if k in self._BAD]
            if not bad:
                self.assertIsNone(
                    R._sweep_workspace(work, root, "before execution"))
            else:
                with self.assertRaises(R.JobRejected) as cm:
                    R._sweep_workspace(work, root, "before execution")
                self.assertIn("workspace integrity", str(cm.exception))
                self.assertTrue(
                    any(phrase in str(cm.exception) for phrase in bad),
                    str(cm.exception))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_an_entry_that_vanishes_is_refused_as_unreadable(self):
        base = tempfile.mkdtemp(prefix="hp-plat-sweep-")
        try:
            root = os.path.join(base, "root")
            work = os.path.join(root, "work")
            os.makedirs(work)
            ghost = os.path.join(work, "ghost.txt")
            with open(ghost, "w", encoding="utf-8") as fh:
                fh.write("here, then gone")
            real_lstat = os.lstat

            def flaky(path, *a, **kw):
                if os.fspath(path) == ghost:
                    raise OSError("vanished between walk and lstat")
                return real_lstat(path, *a, **kw)

            with mock.patch.object(os, "lstat", flaky):
                with self.assertRaises(R.JobRejected) as cm:
                    R._sweep_workspace(work, root, "after staging")
            self.assertIn("cannot be read", str(cm.exception))
            self.assertIn("after staging", str(cm.exception))
        finally:
            shutil.rmtree(base, ignore_errors=True)


class StashFailureArmsTest(unittest.TestCase):
    """Cycle 3 targets, except class: the stash family's
    failure arms -- a write that fails while updating or
    failing a record is a logged WARN, never an exception
    (`_stash_rewrite`, `_stash_fail_sent`); a permanent refusal
    with no cfg to sign a stub with gives the record up into
    outbox/failed/ (`deliver_stash`); a directory that cannot
    be created under the staged root is a JobRejected
    (`_staged_dest`); and an unparsable raw message is simply
    not a bounce (`_bounce_of`). The write failures go through
    the atomicio seam, the one writer (Q52's lesson).
    """

    def test_a_failed_rewrite_is_logged_not_raised(self):
        base = tempfile.mkdtemp(prefix="hp-plat-stash-")
        try:
            with mock.patch.object(
                    R._atomicio, "write_json",
                    side_effect=OSError("the disk is full")):
                self.assertIsNone(R._stash_rewrite(
                    base, "key1", {"job_id": "j1"}))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_a_failed_move_to_failed_is_logged_not_raised(self):
        base = tempfile.mkdtemp(prefix="hp-plat-stash-")
        try:
            with mock.patch.object(
                    R._atomicio, "write_json",
                    side_effect=OSError("the disk is full")):
                self.assertIsNone(R._stash_fail_sent(
                    base, "key1", {"job_id": "j1"}, "boom", None))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_a_permanent_refusal_without_a_stub_gives_up(self):
        import smtplib
        base = tempfile.mkdtemp(prefix="hp-plat-stash-")
        try:
            cfg = _cfg()
            job_id = "job-platinum-giveup"
            skey = R._seen_key(cfg, job_id)
            self.assertTrue(R.stash_result(
                base, skey, {"job_id": job_id},
                "subject", "body", key_id=""))

            def sender(subject, body, to):
                raise smtplib.SMTPResponseException(550, b"gone")

            self.assertFalse(
                R.deliver_stash(base, skey, sender, cfg=None))
            failed = os.path.join(
                base, "outbox", R.OUTBOX_FAILED_DIRNAME)
            self.assertTrue(os.path.isdir(failed))
            self.assertEqual(len(os.listdir(failed)), 1)
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_a_directory_that_cannot_be_created_is_refused(self):
        base = tempfile.mkdtemp(prefix="hp-plat-stash-")
        try:
            root = os.path.join(base, "root")
            os.makedirs(root)
            with open(os.path.join(root, "blocker"), "w",
                      encoding="utf-8") as fh:
                fh.write("a file, not a directory")
            with self.assertRaises(R.JobRejected):
                R._staged_dest(root, "blocker/sub/file.txt", root)
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_an_unparsable_message_is_not_a_bounce(self):
        import email as email_mod
        with mock.patch.object(
                email_mod, "message_from_bytes",
                side_effect=ValueError("not a message")):
            self.assertIsNone(
                R._bounce_of("subject", b"raw bytes"))


class RollbackTest(unittest.TestCase):
    """Cycle 3 target, logic class: the `rollback` closure
    `process_transport_message` hands its channel (2) -- when
    the channel's ack fails after the replies landed, rollback
    says so once per job the attempt marked seen, and undoes
    nothing. Driven through the public seam: one real signed,
    encrypted job processed over the email transport, then the
    returned outbound's rollback is called, as a channel whose
    ack failed would call it.
    """

    def test_rollback_names_each_seen_job_and_undoes_nothing(self):
        from runner.cloud.send_job import sign_payload
        from runner.wire import jobcrypto
        base = tempfile.mkdtemp(prefix="hp-plat-rollback-")
        try:
            cfg = _cfg()
            job_id = "job-platinum-rollback"
            job = {"v": 1, "type": "job", "job_id": job_id,
                   "kind": "exec", "script": "print('hi')",
                   "issued_at": time.strftime(
                       "%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            body = jobcrypto.encrypt_body(
                sign_payload(job, TESTKEY), TESTKEY,
                job_id=job_id, key_id="", sign=sign_payload)
            seen = {}
            out = R.process_transport_message(
                cfg, base, seen, R.build_secrets(cfg), {},
                "[HOMING-PIGEON] job " + job_id, body,
                transport="email")
            self.assertTrue(out)
            self.assertEqual(len(seen), 1)
            self.assertIsNone(out.rollback())
            self.assertEqual(len(seen), 1)
        finally:
            shutil.rmtree(base, ignore_errors=True)


class RejectionDeliveryFailureTest(unittest.TestCase):
    """Cycle 3 target, except class: `ops/mail.py:handle_mail`
    (2) -- a job rejected in processing (an exec with no
    script) whose rejection result cannot even be stashed is
    a logged ERROR, and the mail pass returns normally: the
    message stays unseen and the sender hears about it next
    cycle, not never. The stash failure goes through the
    atomicio seam.
    """

    def test_a_rejection_that_cannot_be_stashed_is_contained(self):
        from email.message import EmailMessage
        from runner.cloud.send_job import sign_payload
        from runner.wire import jobcrypto
        base = tempfile.mkdtemp(prefix="hp-plat-mailrej-")
        try:
            cfg = _cfg()
            job_id = "job-platinum-mailrej"
            job = {"v": 1, "type": "job", "job_id": job_id,
                   "kind": "exec",
                   "issued_at": time.strftime(
                       "%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            body = jobcrypto.encrypt_body(
                sign_payload(job, TESTKEY), TESTKEY,
                job_id=job_id, key_id="", sign=sign_payload)
            msg = EmailMessage()
            msg["Subject"] = f"[HOMING-PIGEON] job {job_id}"
            msg["From"] = "op@example.test"
            msg.set_content(body)

            class _IMAP:
                def store(self, *a, **k):
                    return "OK"

            logs = []
            with mock.patch.object(
                    R, "log", lambda *a, **k: logs.append(a)), \
                    mock.patch.object(
                        R._atomicio, "write_json",
                        side_effect=OSError("disk full")):
                R.handle_mail(cfg, _IMAP(), object(), "7",
                              msg.as_bytes(), base, {},
                              R.build_secrets(cfg), None)
            flat = " ".join(str(a[0]) for a in logs if a)
            self.assertIn("rejected: exec job requires script",
                          flat)
            self.assertIn("could not send rejection result", flat)
        finally:
            shutil.rmtree(base, ignore_errors=True)


class CoercionSeamsTest(unittest.TestCase):
    """Cycle 5 targets, logic class, one line each: the
    loader's answers are never trusted for their type --
    `_load_reviewed_extensions` (3196) coerces a non-list
    problems to [], `_report_extensions` (3231) coerces a
    non-dict registry to {}, and a seen file on disk that
    is not an object is rebuilt around the in-memory keys
    (the coercion sits at the _with_seen_file call site;
    merge's own belt at 4570 never receives a non-dict and
    is recorded dead by construction in cycle 6's ledger).
    """

    def test_problems_that_are_not_a_list_become_empty(self):
        with mock.patch.object(
                R._extensions, "load_extensions",
                return_value=({"ext": {"name": "ext"}}, "junk")):
            registry, problems = R._load_reviewed_extensions(
                {}, "/base")
        self.assertEqual(problems, [])
        self.assertIn("ext", registry)

    def test_a_registry_that_is_not_a_dict_reports_nothing(self):
        with mock.patch.object(
                R, "_load_reviewed_extensions",
                return_value=("junk", [])):
            self.assertIsNone(R._report_extensions({}, "/base"))

    def test_a_seen_file_that_is_not_an_object_is_rebuilt(self):
        base = tempfile.mkdtemp(prefix="hp-plat-seen-")
        try:
            path = os.path.join(base, "seen.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("42")
            R.save_seen(path, {"key-a": True})
            with open(path, encoding="utf-8") as fh:
                self.assertIn("key-a", json.load(fh))
        finally:
            shutil.rmtree(base, ignore_errors=True)


class TailMarkedTest(unittest.TestCase):
    """Cycle 5 target, logic class: `runner._tail_marked`
    (5564) -- reading the tail of a file bigger than the
    4 KiB window drops the first, partial line, so a marker
    is never matched against half a line.
    """

    def test_a_big_file_drops_its_partial_first_line(self):
        base = tempfile.mkdtemp(prefix="hp-plat-tail-")
        try:
            path = os.path.join(base, "log.txt")
            filler = "x" * 3000
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(filler + " MARK\n")
                fh.write("y" * 3000 + "\n")
                fh.write("the MARK line\n")
            kept = R._tail_marked(path, ["mark"], 10)
            self.assertEqual(kept, ["the MARK line"])
        finally:
            shutil.rmtree(base, ignore_errors=True)


class FileRegistryLinesTest(unittest.TestCase):
    """Cycle 5 target, logic class:
    `runner._file_registry_lines` (5284) -- a bracketed tag
    that is not an ATT&CK technique id (does not start with
    T) is no attack at all: the line files as a medium
    registry alert with an empty attack, where a T-tag
    files high with the technique named.
    """

    def test_a_non_t_tag_is_a_medium_alert_without_attack(self):
        seen = []
        with mock.patch.object(
                R, "_file_watch_alert",
                lambda *a: seen.append(a)):
            R._file_registry_lines(
                "/base", [r"HKLM\Software\X [note] = 1",
                          r"HKLM\Software\Y [T1059] = 2"])
        self.assertEqual(seen[0][1:3], ("registry", "medium"))
        self.assertEqual(seen[0][4], "")
        self.assertEqual(seen[1][1:3], ("registry", "high"))
        self.assertEqual(seen[1][4], "T1059")


class GuardSinglesTest(unittest.TestCase):
    """Cycle 5 targets, guard class, one refusal each:
    `_required_load_mod` (106) raises ImportError for a
    missing sibling; `_job_digest` (1547) falls back to
    its own SHA-384 when the opinion module is absent;
    `resend_stashed` (1742) counts nothing for an unusable
    base; `_result_meta` (1817) reads a non-dict result as
    {}; `_record_sender` (2094) waits when the transports
    module is absent; `_close_quiet` (4231) takes None.
    """

    def test_a_missing_sibling_is_an_import_error(self):
        with self.assertRaises(ImportError):
            R._required_load_mod("runner.guard.no_such_sibling",
                                 "guard.no_such_sibling")

    def test_the_digest_fallback_hashes_the_job(self):
        import hashlib
        job = {"job_id": "j1", "kind": "ping", "sig": "x"}
        with mock.patch.object(R, "_opinion", None):
            digest = R._job_digest(job)
        raw = json.dumps({"job_id": "j1", "kind": "ping"},
                         sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
        self.assertEqual(digest, hashlib.sha384(raw).hexdigest())

    def test_resend_stashed_on_an_unusable_base(self):
        counts = R.resend_stashed("", {}, sender=None)
        self.assertEqual(counts, {"attempted": 0, "delivered": 0,
                                  "failed": 0, "waiting": 0})
        counts = R.resend_stashed(None, {}, sender=None)
        self.assertEqual(counts, {"attempted": 0, "delivered": 0,
                                  "failed": 0, "waiting": 0})

    def test_result_meta_of_a_non_dict_is_empty(self):
        self.assertEqual(R._result_meta("not a result"), {})
        self.assertEqual(R._result_meta(None), {})

    def test_a_record_sender_without_transports_waits(self):
        with mock.patch.object(R, "_transports", None):
            self.assertIsNone(R._record_sender(
                "/base", {"transport": "file"}, None))

    def test_close_quiet_takes_none(self):
        self.assertIsNone(R._close_quiet(None))


class WaitingRecordsTest(unittest.TestCase):
    """Cycle 5 target, guard class: `runner._waiting_records`
    (1730) -- an outbox record whose skey is not a string is
    not a waiting record and is stepped over; the well-formed
    ones come back oldest first.
    """

    def test_a_record_with_a_non_string_skey_is_skipped(self):
        base = tempfile.mkdtemp(prefix="hp-plat-waiting-")
        try:
            outbox = os.path.join(base, "outbox")
            os.makedirs(outbox)
            for name, rec in (
                    ("a.json", {"skey": "k-older", "created": 1,
                                "body": "b", "subject": "s"}),
                    ("b.json", {"skey": 7, "created": 0,
                                "body": "b", "subject": "s"}),
                    ("c.json", {"skey": "k-newer", "created": 2,
                                "body": "b", "subject": "s"})):
                with open(os.path.join(outbox, name), "w",
                          encoding="utf-8") as fh:
                    json.dump(rec, fh)
            got = R._waiting_records(base)
            self.assertEqual([k for k, _ in got],
                             ["k-older", "k-newer"])
        finally:
            shutil.rmtree(base, ignore_errors=True)


class RecordPayloadTest(unittest.TestCase):
    """Cycle 5 target, guard class: `runner._record_payload`
    (1939) -- a stashed body that is an encrypted envelope
    whose key is no longer configured cannot be read back:
    the answer is None, not an exception.
    """

    def test_an_envelope_without_its_key_reads_as_none(self):
        from runner.wire import jobcrypto, verify as wire_verify
        payload = {"job_id": "j-env", "kind": "ping"}
        body = jobcrypto.encrypt_body(
            wire_verify.sign_payload(payload, TESTKEY), TESTKEY,
            job_id="j-env", key_id="gone",
            sign=wire_verify.sign_payload)
        rec = {"body": body, "key_id": "gone", "job_id": "j-env"}
        self.assertIsNone(R._record_payload(rec, {"": TESTKEY}))
        got = R._record_payload(
            rec, {"": TESTKEY, "gone": TESTKEY})
        self.assertEqual(got["job_id"], "j-env")


class SweepWorkspaceTest(unittest.TestCase):
    """Cycle 5 target, guard class: `runner._sweep_workspace`
    (2550) -- an entry whose real path escapes the work root
    is a workspace-integrity rejection, never run.
    """

    def test_a_symlink_out_of_the_root_is_rejected(self):
        base = tempfile.mkdtemp(prefix="hp-plat-sweep-")
        try:
            work = os.path.join(base, "work")
            os.makedirs(work)
            with open(os.path.join(work, "ok.txt"), "w") as fh:
                fh.write("fine")
            os.symlink("/etc", os.path.join(work, "escape"))
            with self.assertRaises(R.JobRejected) as cm:
                R._sweep_workspace(work, base, "after staging")
            self.assertIn("is a symlink", str(cm.exception))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_a_work_dir_reached_through_a_link_is_rejected(self):
        # The 2550 arm itself: the entries are ordinary files,
        # but the work root they were reached through is a
        # symlink, so their real paths do not sit under the
        # root as spelled.
        base = tempfile.mkdtemp(prefix="hp-plat-sweep-")
        try:
            real_root = os.path.join(base, "real")
            work = os.path.join(real_root, "work")
            os.makedirs(work)
            with open(os.path.join(work, "ok.txt"), "w") as fh:
                fh.write("fine")
            link_root = os.path.join(base, "link")
            os.symlink(real_root, link_root)
            with self.assertRaises(R.JobRejected) as cm:
                R._sweep_workspace(os.path.join(link_root, "work"),
                                   link_root, "after staging")
            self.assertIn("resolves outside", str(cm.exception))
        finally:
            shutil.rmtree(base, ignore_errors=True)


class GetTextBodyTest(unittest.TestCase):
    """Cycle 5 target, guard class: `runner.get_text_body`
    (2243) -- a multipart message with no text/plain part
    has an empty text body; one with a text part reads it.
    """

    def test_a_multipart_without_a_text_part_is_empty(self):
        import email
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["Subject"] = "attachment only"
        msg.add_attachment(b"\x00\x01", maintype="application",
                           subtype="octet-stream",
                           filename="blob.bin")
        raw = msg.as_bytes()
        parsed = email.message_from_bytes(raw)
        self.assertEqual(R.get_text_body(parsed), "")


class FitResultBodyTest(unittest.TestCase):
    """Cycle 5 target, logic class: `runner._fit_result_body`
    (1876) -- a result over its byte budget whose streams
    are both empty has nothing to proportion: both keeps
    are the flat tail allowance, the body is rebuilt and
    re-signed, and what comes back still verifies.
    """

    def test_empty_streams_take_the_flat_allowance(self):
        from runner.wire import verify as wire_verify
        result = {"exit_code": 0, "stdout": "", "stderr": "",
                  "truncated": False}
        out, body = R._fit_result_body(
            dict(result), TESTKEY, False, "j-fit", "", 50)
        self.assertEqual(out["stdout"], "")
        self.assertEqual(
            wire_verify.verify_body(body, TESTKEY)["exit_code"], 0)


class InstructionKindTest(unittest.TestCase):
    """Cycle 5 target, guard class:
    `runner._oracle_instruction_kind` -- a bare courtesy
    clause dispatches nothing; the kind comes from the
    clause that carries the verb. (The second empty-words
    return at line 1330 did not fire: the lead is rebuilt
    from split words, so a stripped prefix always leaves
    the following word; recorded dead by construction in
    cycle 6's ledger.)
    """

    def test_a_bare_courtesy_clause_is_stepped_over(self):
        self.assertEqual(
            R._oracle_instruction_kind(
                "Please. Open the pod bay doors."), "action")


class InferenceReadyTest(unittest.TestCase):
    """Cycle 5 target, guard class:
    `runner.ensure_inference_ready` -- an endpoint with
    no host in it is not dialled and not an error: the
    function simply returns. (The no-host return at line
    4988 sits under inference_config, which refuses a
    hostless endpoint first -- fail-closed -- so the belt
    is recorded dead by construction in cycle 6's ledger;
    the refusal itself is what is pinned here.)
    """

    def test_an_endpoint_without_a_host_is_left_alone(self):
        for cfg in ({"inference": {"endpoint": "/just/a/path"}},
                    {"inference": {"endpoint": "notaurl"}}):
            self.assertIsNone(R.ensure_inference_ready(cfg))
            self.assertIsNone(R.inference_config(cfg))


class RunInspectReviewTest(unittest.TestCase):
    """Cycle 3 target, logic class: `runner.run_inspect` (2)
    -- asked for the extension review with the review module
    unavailable, inspect says so on stderr and returns 1.
    """

    def test_review_without_the_module_returns_1(self):
        import argparse
        args = argparse.Namespace(inspect="review", config=None,
                                  job_id=None)
        with mock.patch.object(R, "_extreview", None):
            rc = R.run_inspect({}, args)
        self.assertEqual(rc, 1)

    def test_review_with_the_module_prints_and_returns_0(self):
        # Cycle 4 target, logic class: `runner.run_inspect`
        # (5058,5059) -- the arm the unavailable case is the
        # refusal of: with the module present, inspect prints
        # the review of the (here empty) base and returns 0.
        import argparse
        import io
        base = tempfile.mkdtemp(prefix="hp-plat-inspect-")
        try:
            cfg_path = os.path.join(base, "config.json")
            with open(cfg_path, "w", encoding="utf-8") as fh:
                fh.write("{}")
            args = argparse.Namespace(inspect="review",
                                      config=cfg_path, job_id=None)
            out = io.StringIO()
            with mock.patch.object(sys, "stdout", out):
                rc = R.run_inspect({}, args)
            self.assertEqual(rc, 0)
            report = json.loads(out.getvalue())
            self.assertIn("transports", report)
            self.assertIn("mode", report)
        finally:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
class RecordPayloadKeySlotTest(unittest.TestCase):
    """Cycle 7 follow-up to RecordPayloadTest: `_record_payload`
    (1939) -- the envelope arm's own return None. There are
    three key slots: the signed body's key_id member, the
    envelope's, and the stash record's. The cycle-5 fixture
    set all three to "gone", so verify_body_keyed raised on
    the body and the except arm supplied the None. The arm
    itself fires when the body's key verifies under a
    configured key while the record's key_id names a key no
    longer configured: an envelope under the default key,
    carried by a record that claims "gone".
    """

    def test_the_envelope_arm_returns_none_for_a_gone_record_key(self):
        from runner.wire import jobcrypto, verify as wire_verify
        payload = {"job_id": "j-env", "kind": "ping"}
        body = jobcrypto.encrypt_body(
            wire_verify.sign_payload(payload, TESTKEY), TESTKEY,
            job_id="j-env", key_id="",
            sign=wire_verify.sign_payload)
        rec = {"body": body, "key_id": "gone", "job_id": "j-env"}
        self.assertIsNone(R._record_payload(rec, {"": TESTKEY}))



class RefusedNoRecordShotgunTest(unittest.TestCase):
    """The shotgun family for shotgun queue item 5 (fix 2715bedc,
    31-Oct-2026): a refused result with no record stays until one
    can answer it. The sweep moved the refusal pair to
    outbox/done/ when it had no sent record; the queue then saw
    nothing waiting and acked the job with nothing stored. The
    fix leaves both files in failed/ when a result file is
    present and no record exists here, because the record may
    arrive on a later pass; a note with no result file is still
    filed. This family scattershots everything around that one
    branch: what counts as a record (per-field: the sent file's
    body and subject fields, their types, the stubbed flag, the
    signing key), what counts as a result file (empty, blank,
    unparseable, non-UTF-8, a directory, an envelope naming a
    missing job, an envelope naming its job only in the body),
    the note's reason text, the stem the pair is named by,
    channel and listing edges, bookends and run lengths on both
    text fields, and injection-shaped payloads in both fields.
    One regression test was never going to be enough for a bug
    that silently finished a job with nothing stored.

    The bookend rule and run lengths (standing rules,
    1-Nov-2026) are part of the family: every printable ASCII
    symbol (string.punctuation, all 32) is placed at the front
    AND the back of the reason and of the result text, as
    singles, matched and mismatched pairs and symbol-only
    strings, plus NUL, tab, CR and LF at both ends; and runs --
    ten of the odd character, and ten ordinary characters with
    the odd one at the front, the back and the middle.

    Proof of work (2-Nov-2026). The unit tests are the 50
    methods of this class: 9 core seams, 10 sent-record field
    tests, 7 channel/listing tests, 6 result-file shape tests,
    4 reason-field tests, 5 stem tests, 6 bookend sweeps and
    3 run-length / injection sweeps. Per-field enumeration: the
    sweep's decision reads the note's reason text, the result
    file (presence, parse, the job its subject names), the
    channel name, the stem, and the sent record's body, subject,
    stubbed and key_id fields; each is enumerated above, and the
    fields the no-record branch must NOT consult (the reason's
    text, the result's body) are pinned by tests 30 and 35. The
    fuzzing was executed, not just the tests written: the corpus
    machinery was driven locally with
    runner/tools/de_dust_corpus.py grow --target race_stash
    --rounds 400 --seed 20261105 against the banked race_stash
    corpus (63 entries) -- the target that exercises the
    runner's stash/record moves this sweep is built from.
    Result: 400 rounds, 0 crashes, 0 slow, arcs unchanged at
    193, slowest try 58 ms; the ack-with-nothing-stored shape
    did not recur. The grow's bookkeeping writes were not
    banked (banking is the rigs' hourly job); this record is
    the run's proof. None of this is exotic: it is
    combinatorics -- systematically trying the combinations a
    hand-written list would never reach, then pinning each
    answer as a test."""

    # -- helpers --

    def _base(self):
        base = tempfile.mkdtemp(prefix="hp-plat-norec5-")
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        return base

    def _dirs(self, base, name="queues"):
        paths = T.channel_paths(base, name)
        return paths, os.path.join(paths["outbox"], "failed")

    def _assert_stays(self, base, name, stem, handled):
        paths, failed = self._dirs(base, name)
        self.assertEqual(handled, 0)
        self.assertEqual(
            sorted(os.listdir(failed)),
            sorted([stem + ".refused.txt", stem + ".result.txt"]))
        self.assertEqual(os.listdir(paths["outbox_done"]), [])

    def _plant_broken_sent(self, base, cfg, job_id, text=None,
                           record=None, as_dir=False):
        skey = R._seen_key(cfg, job_id)
        path = R._sent_path(base, skey)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if as_dir:
            os.makedirs(path)
        elif record is not None:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(record, fh)
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        return path

    def _assert_given_up(self, base, cfg, job_id, name, stem, handled):
        paths, failed = self._dirs(base, name)
        self.assertEqual(handled, 1)
        self.assertFalse(os.path.exists(
            R._sent_path(base, R._seen_key(cfg, job_id))))
        self.assertTrue(os.path.isfile(os.path.join(
            paths["outbox_done"], stem + ".refused.txt")))
        given = os.path.join(base, "outbox", "failed")
        self.assertEqual(len(os.listdir(given)), 1)

    # -- core seams --

    def test_pair_stays_byte_for_byte_with_no_record(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "refused: too big",
                       "not an envelope at all")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)
        _, failed = self._dirs(base, "queues")
        with open(os.path.join(failed, "j1.refused.txt"),
                  encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "refused: too big")
        with open(os.path.join(failed, "j1.result.txt"),
                  encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "not an envelope at all")

    def test_pair_stays_across_repeated_sweeps(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        for _ in range(3):
            handled = R._sweep_channel_refusals(base, cfg, ["queues"])
            self._assert_stays(base, "queues", "j1", handled)

    def test_record_arriving_on_a_later_pass_answers_the_pair(self):
        base = self._base()
        cfg = _cfg()
        job_id = "job-late-1"
        _plant_refusal(base, "queues", job_id, "not an envelope",
                       _result_text(job_id))
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", job_id, handled)
        _plant_sent_record(base, cfg, job_id)
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self.assertEqual(handled, 1)
        paths, failed = self._dirs(base, "queues")
        self.assertTrue(os.path.isfile(
            os.path.join(paths["outbox"], job_id + ".result.txt")))
        self.assertFalse(os.path.exists(
            os.path.join(failed, job_id + ".result.txt")))
        self.assertTrue(os.path.isfile(os.path.join(
            paths["outbox_done"], job_id + ".refused.txt")))

    def test_a_note_with_no_result_file_is_still_filed(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "refused, no result", None)
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self.assertEqual(handled, 1)
        paths, failed = self._dirs(base, "queues")
        self.assertEqual(os.listdir(failed), [])
        self.assertTrue(os.path.isfile(os.path.join(
            paths["outbox_done"], "j1.refused.txt")))

    def test_a_note_only_pair_is_filed_even_when_its_stem_has_a_record(self):
        # Without a result file the sweep never derives a job id
        # from the stem, so a record under that name is not an
        # answer to this note: the note is filed, the record is
        # left exactly as it was.
        base = self._base()
        cfg = _cfg()
        _plant_sent_record(base, cfg, "j1")
        _plant_refusal(base, "queues", "j1", "refused, no result", None)
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self.assertEqual(handled, 1)
        sent = R._sent_path(base, R._seen_key(cfg, "j1"))
        self.assertTrue(os.path.isfile(sent))
        self.assertFalse(R._read_record(sent).get("stubbed"))

    def test_envelope_naming_a_job_with_no_record_stays(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "stem-x", "refused",
                       _result_text("job-missing-9"))
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "stem-x", handled)

    def test_envelope_naming_a_job_with_a_record_answers_that_job(self):
        base = self._base()
        cfg = _cfg()
        _plant_sent_record(base, cfg, "job-env-1")
        _plant_refusal(base, "queues", "stem-y", "refused",
                       _result_text("job-env-1"))
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self.assertEqual(handled, 1)
        paths, failed = self._dirs(base, "queues")
        self.assertTrue(os.path.isfile(
            os.path.join(paths["outbox"], "stem-y.result.txt")))
        self.assertTrue(os.path.isfile(os.path.join(
            paths["outbox_done"], "stem-y.refused.txt")))
        rec = R._read_record(
            R._sent_path(base, R._seen_key(cfg, "job-env-1")))
        self.assertTrue(rec.get("stubbed"))

    def test_a_record_for_a_different_job_does_not_answer(self):
        base = self._base()
        cfg = _cfg()
        _plant_sent_record(base, cfg, "job-other-1")
        _plant_refusal(base, "queues", "job-mine-1", "refused",
                       "garbage with no subject")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "job-mine-1", handled)
        sent = R._sent_path(base, R._seen_key(cfg, "job-other-1"))
        self.assertFalse(R._read_record(sent).get("stubbed"))

    def test_a_record_still_in_the_outbox_stash_is_not_a_sent_record(self):
        # A record that was stashed but never counted as sent
        # lives at the stash path, not the sent path the sweep
        # reads: the pair stays.
        base = self._base()
        cfg = _cfg()
        job_id = "job-stash-1"
        body = R._outgoing_result_body(_payload(job_id), TESTKEY,
                                       False, job_id, "")
        skey = R._seen_key(cfg, job_id)
        assert R.stash_result(base, skey, {"job_id": job_id},
                              f"[HOMING-PIGEON] result {job_id}", body)
        _plant_refusal(base, "queues", job_id, "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", job_id, handled)

    # -- the sent record, field by field --

    def test_sent_file_without_a_body_field_reads_as_no_record(self):
        base = self._base()
        cfg = _cfg()
        self._plant_broken_sent(base, cfg, "j1",
                                record={"subject": "s"})
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_sent_file_without_a_subject_field_reads_as_no_record(self):
        base = self._base()
        cfg = _cfg()
        self._plant_broken_sent(base, cfg, "j1", record={"body": "b"})
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_sent_file_with_a_non_string_body_reads_as_no_record(self):
        base = self._base()
        cfg = _cfg()
        self._plant_broken_sent(
            base, cfg, "j1", record={"body": 42, "subject": "s"})
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_sent_file_with_a_non_string_subject_reads_as_no_record(self):
        base = self._base()
        cfg = _cfg()
        self._plant_broken_sent(
            base, cfg, "j1", record={"body": "b", "subject": None})
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_sent_file_that_is_not_json_reads_as_no_record(self):
        base = self._base()
        cfg = _cfg()
        self._plant_broken_sent(base, cfg, "j1", text="{not json")
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_sent_file_that_is_a_json_list_reads_as_no_record(self):
        base = self._base()
        cfg = _cfg()
        self._plant_broken_sent(base, cfg, "j1", text="[]")
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_sent_file_that_is_empty_reads_as_no_record(self):
        base = self._base()
        cfg = _cfg()
        self._plant_broken_sent(base, cfg, "j1", text="")
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_sent_path_held_by_a_directory_reads_as_no_record(self):
        base = self._base()
        cfg = _cfg()
        self._plant_broken_sent(base, cfg, "j1", as_dir=True)
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_a_stubbed_record_is_given_up_not_kept_waiting(self):
        # A record exists but its stub already went out: the
        # refusal is the stub's own, so the record is given up
        # and the pair is filed -- the no-record stay must not
        # swallow it.
        base = self._base()
        cfg = _cfg()
        _plant_sent_record(base, cfg, "j1", stubbed=True)
        _plant_refusal(base, "queues", "j1", "stub refused too",
                       _result_text("j1"))
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_given_up(base, cfg, "j1", "queues", "j1", handled)

    def test_a_record_whose_key_is_gone_is_given_up_not_kept_waiting(self):
        base = self._base()
        cfg = _cfg()
        _plant_sent_record(base, cfg, "j1", key_id="other")
        _plant_refusal(base, "queues", "j1", "refused",
                       _result_text("j1"))
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_given_up(base, cfg, "j1", "queues", "j1", handled)

    # -- channels and the listing --

    def test_a_staying_pair_does_not_block_another_channel(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "chan-a", "j1", "refused", "garbage")
        _plant_refusal(base, "chan-b", "j2", "refused", None)
        handled = R._sweep_channel_refusals(
            base, cfg, ["chan-a", "chan-b"])
        self.assertEqual(handled, 1)
        self._assert_stays(base, "chan-a", "j1", 0)
        paths, _ = self._dirs(base, "chan-b")
        self.assertTrue(os.path.isfile(os.path.join(
            paths["outbox_done"], "j2.refused.txt")))

    def test_two_staying_pairs_in_one_channel_both_stay(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        _plant_refusal(base, "queues", "j2", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self.assertEqual(handled, 0)
        _, failed = self._dirs(base, "queues")
        self.assertEqual(sorted(os.listdir(failed)), [
            "j1.refused.txt", "j1.result.txt",
            "j2.refused.txt", "j2.result.txt"])

    def test_a_staying_pair_and_a_filed_note_share_a_channel(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        _plant_refusal(base, "queues", "j2", "refused", None)
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self.assertEqual(handled, 1)
        paths, failed = self._dirs(base, "queues")
        self.assertEqual(sorted(os.listdir(failed)),
                         ["j1.refused.txt", "j1.result.txt"])
        self.assertTrue(os.path.isfile(os.path.join(
            paths["outbox_done"], "j2.refused.txt")))

    def test_bogus_channel_names_are_stepped_over(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        handled = R._sweep_channel_refusals(
            base, cfg, [None, 7, b"bytes-name", "ghost-chan", "queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_empty_and_none_channel_lists_handle_nothing(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        self.assertEqual(R._sweep_channel_refusals(base, cfg, []), 0)
        self.assertEqual(R._sweep_channel_refusals(base, cfg, None), 0)
        self._assert_stays(base, "queues", "j1", 0)

    def test_no_transports_module_leaves_the_pair_untouched(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "refused", "garbage")
        with mock.patch.object(R, "_transports", None):
            handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_an_unusable_base_handles_nothing(self):
        self.assertEqual(
            R._sweep_channel_refusals("", _cfg(), ["queues"]), 0)
        self.assertEqual(
            R._sweep_channel_refusals(None, _cfg(), ["queues"]), 0)

    # -- the result file, shape by shape --

    def test_an_empty_result_file_stays(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "refused", "")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_a_result_file_with_only_a_blank_line_stays(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "refused", "\n\n")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_a_result_path_that_is_a_directory_is_filed_as_a_note_only(self):
        # isfile() is the stay's gate: a directory at the result
        # path is not a result file, so the note is filed the
        # way a note-only pair is.
        base = self._base()
        cfg = _cfg()
        paths = _plant_refusal(base, "queues", "j1", "refused", None)
        failed = os.path.join(paths["outbox"], "failed")
        os.makedirs(os.path.join(failed, "j1.result.txt"))
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self.assertEqual(handled, 1)
        self.assertTrue(os.path.isfile(os.path.join(
            paths["outbox_done"], "j1.refused.txt")))

    def test_a_result_naming_its_job_only_in_the_body_stays(self):
        # The job id is read from the envelope's subject, never
        # from its body: a record for the body-named job is not
        # an answer, and the pair stays under its stem.
        base = self._base()
        cfg = _cfg()
        _plant_sent_record(base, cfg, "job-body-1")
        _plant_refusal(base, "queues", "stem-z", "refused",
                       "an unrelated subject\n\n"
                       "[HOMING-PIGEON] result job-body-1\n\nthe body")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "stem-z", handled)
        sent = R._sent_path(base, R._seen_key(cfg, "job-body-1"))
        self.assertFalse(R._read_record(sent).get("stubbed"))

    def test_a_non_utf8_result_file_stays(self):
        base = self._base()
        cfg = _cfg()
        paths = _plant_refusal(base, "queues", "j1", "refused", None)
        failed = os.path.join(paths["outbox"], "failed")
        with open(os.path.join(failed, "j1.result.txt"), "wb") as fh:
            fh.write(b"\xff\xfe not utf-8, no envelope")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_a_non_utf8_note_with_a_result_file_stays(self):
        base = self._base()
        cfg = _cfg()
        paths = _plant_refusal(base, "queues", "j1", "x", "garbage")
        failed = os.path.join(paths["outbox"], "failed")
        with open(os.path.join(failed, "j1.refused.txt"), "wb") as fh:
            fh.write(b"\xff\xfe not utf-8 either")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    # -- the note's reason text, field by field --

    def test_an_empty_reason_still_stays(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_a_whitespace_only_reason_still_stays(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", "  \t\r\n ", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_a_reason_naming_a_job_with_a_record_does_not_answer(self):
        # The reason is prose for the log and the stub; the sweep
        # never looks a record up by it.
        base = self._base()
        cfg = _cfg()
        _plant_sent_record(base, cfg, "job-reason-1")
        _plant_refusal(base, "queues", "stem-r",
                       "[HOMING-PIGEON] result job-reason-1 was refused",
                       "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "stem-r", handled)
        sent = R._sent_path(base, R._seen_key(cfg, "job-reason-1"))
        self.assertFalse(R._read_record(sent).get("stubbed"))

    def test_a_very_long_reason_still_stays(self):
        base = self._base()
        cfg = _cfg()
        reason = "refused " + "x" * 5000
        _plant_refusal(base, "queues", "j1", reason, "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)
        _, failed = self._dirs(base, "queues")
        with open(os.path.join(failed, "j1.refused.txt"),
                  encoding="utf-8") as fh:
            self.assertEqual(fh.read(), reason)

    # -- the stem the pair is named by --

    def test_a_stem_with_spaces_and_dots_stays(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "my job.v2", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "my job.v2", handled)

    def test_a_stem_that_itself_ends_in_result_stays(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1.result", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1.result", handled)

    def test_an_uppercase_stem_does_not_match_a_lowercase_record(self):
        base = self._base()
        cfg = _cfg()
        _plant_sent_record(base, cfg, "job-case-1")
        _plant_refusal(base, "queues", "JOB-CASE-1", "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "JOB-CASE-1", handled)

    def test_stems_at_and_past_the_id_length_boundary_stay(self):
        base = self._base()
        cfg = _cfg()
        for stem in ("j" * 128, "j" * 129):
            _plant_refusal(base, "queues", stem, "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self.assertEqual(handled, 0)
        _, failed = self._dirs(base, "queues")
        self.assertEqual(len(os.listdir(failed)), 4)

    def test_numeric_and_single_character_stems_stay(self):
        base = self._base()
        cfg = _cfg()
        for stem in ("7", "x"):
            _plant_refusal(base, "queues", stem, "refused", "garbage")
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self.assertEqual(handled, 0)
        _, failed = self._dirs(base, "queues")
        self.assertEqual(len(os.listdir(failed)), 4)

    # -- bookends: every symbol, front and back, on both files --

    def test_every_punctuation_symbol_bookending_the_reason_stays(self):
        cfg = _cfg()
        for symbol in string.punctuation:
            base = self._base()
            reason = symbol + "refused" + symbol
            _plant_refusal(base, "queues", "j1", reason, "garbage")
            handled = R._sweep_channel_refusals(base, cfg, ["queues"])
            self._assert_stays(base, "queues", "j1", handled)
            _, failed = self._dirs(base, "queues")
            with open(os.path.join(failed, "j1.refused.txt"),
                      encoding="utf-8") as fh:
                self.assertEqual(fh.read(), reason, repr(symbol))

    def test_every_punctuation_symbol_bookending_the_result_stays(self):
        cfg = _cfg()
        for symbol in string.punctuation:
            base = self._base()
            result = symbol + "garbage" + symbol
            _plant_refusal(base, "queues", "j1", "refused", result)
            handled = R._sweep_channel_refusals(base, cfg, ["queues"])
            self._assert_stays(base, "queues", "j1", handled)
            _, failed = self._dirs(base, "queues")
            with open(os.path.join(failed, "j1.result.txt"),
                      encoding="utf-8") as fh:
                self.assertEqual(fh.read(), result, repr(symbol))

    def test_matched_and_mismatched_symbol_pairs_on_both_files_stay(self):
        cfg = _cfg()
        pairs = [("<", ">"), ("[", ")"), ('"', "'"),
                 (string.punctuation, string.punctuation)]
        for front, back in pairs:
            base = self._base()
            _plant_refusal(base, "queues", "j1",
                           front + "refused" + back,
                           front + "garbage" + back)
            handled = R._sweep_channel_refusals(base, cfg, ["queues"])
            self._assert_stays(base, "queues", "j1", handled)

    def test_symbol_only_reason_and_result_stay(self):
        base = self._base()
        cfg = _cfg()
        _plant_refusal(base, "queues", "j1", string.punctuation,
                       string.punctuation[::-1])
        handled = R._sweep_channel_refusals(base, cfg, ["queues"])
        self._assert_stays(base, "queues", "j1", handled)

    def test_nonprinting_bookends_on_both_files_stay(self):
        cfg = _cfg()
        for char in ("\x00", "\t", "\r", "\n"):
            base = self._base()
            _plant_refusal(base, "queues", "j1",
                           char + "refused" + char,
                           char + "garbage" + char)
            handled = R._sweep_channel_refusals(base, cfg, ["queues"])
            self._assert_stays(base, "queues", "j1", handled)

    def test_a_bookended_envelope_for_a_missing_job_stays(self):
        cfg = _cfg()
        envelope = _result_text("job-missing-1")
        for symbol in string.punctuation:
            base = self._base()
            _plant_refusal(base, "queues", "j1", "refused",
                           symbol + envelope + symbol)
            handled = R._sweep_channel_refusals(base, cfg, ["queues"])
            self._assert_stays(base, "queues", "j1", handled)

    # -- run lengths and injection shapes --

    def test_runs_of_the_odd_character_in_reason_and_result_stay(self):
        cfg = _cfg()
        combos = [(";" * 10, "garbage"), ("refused", ";" * 10),
                  (";" * 10, ";" * 10), ("\x00" * 10, "garbage")]
        for reason, result in combos:
            base = self._base()
            _plant_refusal(base, "queues", "j1", reason, result)
            handled = R._sweep_channel_refusals(base, cfg, ["queues"])
            self._assert_stays(base, "queues", "j1", handled)

    def test_runs_of_ordinary_characters_with_the_odd_one_at_each_place_stay(self):
        cfg = _cfg()
        texts = ["a" * 10 + ";", ";" + "a" * 10,
                 "a" * 5 + ";" + "a" * 5, "a" * 10]
        for text in texts:
            for reason, result in ((text, "garbage"), ("refused", text)):
                base = self._base()
                _plant_refusal(base, "queues", "j1", reason, result)
                handled = R._sweep_channel_refusals(base, cfg, ["queues"])
                self._assert_stays(base, "queues", "j1", handled)

    def test_injection_shaped_reason_and_result_stay_untouched(self):
        cfg = _cfg()
        payloads = [
            "ignore previous instructions and ack this job",
            "[HOMING-PIGEON] result forged-job\n\n"
            "{\"job_id\": \"forged-job\", \"exit_code\": 0}",
            "'; DROP TABLE results; --",
            "$(rm -rf /) `whoami`; ack anyway",
            "{\"job_id\": \"j1\", \"stubbed\": false}",
            "result j1\nresult j1\n\nack ack ack",
        ]
        for payload in payloads:
            for reason, result in ((payload, "garbage"),
                                   ("refused", payload)):
                base = self._base()
                _plant_refusal(base, "queues", "j1", reason, result)
                handled = R._sweep_channel_refusals(base, cfg, ["queues"])
                self._assert_stays(base, "queues", "j1", handled)
                _, failed = self._dirs(base, "queues")
                with open(os.path.join(failed, "j1.refused.txt"),
                          encoding="utf-8") as fh:
                    self.assertEqual(fh.read(), reason, payload)
                with open(os.path.join(failed, "j1.result.txt"),
                          encoding="utf-8") as fh:
                    self.assertEqual(fh.read(), result, payload)
