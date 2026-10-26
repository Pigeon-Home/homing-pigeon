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
import tempfile
import unittest
from unittest import mock

from hypothesis import given, settings, strategies as st

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
            planted = 0
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
                planted += 1
            handled = R._sweep_channel_refusals(
                base, cfg, names + bogus_names)
            self.assertEqual(handled, planted)
            for i, plan in enumerate(plans):
                paths = T.channel_paths(base, f"chan{i}")
                done = os.path.join(paths["outbox_done"],
                                    f"stem{i}.refused.txt")
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


if __name__ == "__main__":
    unittest.main()
