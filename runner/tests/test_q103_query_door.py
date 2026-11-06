# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""Q103: the query door read against PROTOCOL.md sections 10, 11 and 14.

Item 1: a retained record with no owner (written before the owner was
kept, an artifact note, a record a crash cut short) is the default
key's. Another key's query is an unknown job and spends nothing.
Item 2: a key_policies entry on the default key binds it at the
query, board and v2 doors as at the job's; only the deny flag leaves
the owner alone. Item 3: freshness runs before the door's policy, so
a stale query is silence whatever key signed it.
"""
import time
import unittest

from runner import runner
from runner.runner import load_retained, save_retained
from runner.tests.security_parity import EXTRA_SECRET, SECRET, FakeIMAP, FakeSMTP
from runner.tests.test_q98_doors import (
    QueryBudgetBelongsToItsKeyTest, _Opts, _mail, _now, _sealed)
from runner.wire import verify as V


class _Door(QueryBudgetBelongsToItsKeyTest):
    """The Q98 rig, with a record this class lays out itself."""

    RECORD = {"stdout": "one\ntwo\n", "stderr": "", "exit_code": 0,
              "budget": 8, "spent": 0, "view": "full"}

    def setUp(self):
        super().setUp()
        save_retained(self.dir, self.JOB, dict(self.RECORD, saved_at=time.time()))

    def _fingerprint(self, secret):
        return [k for k, v in self.secrets.items()
                if k.startswith("k-") and v == secret][0]

    def _spent(self):
        return load_retained(self.dir, self.JOB).get("spent")

    # The Q98 cases ask about a record whose owner is set; these
    # classes set their own.
    test_another_keys_query_is_an_unknown_job_and_spends_nothing = None
    test_the_jobs_own_key_still_asks = None
    test_the_jobs_key_by_its_fingerprint_is_the_same_key = None


class OwnerlessRecordTest(_Door):
    """Item 1."""

    def test_another_key_gets_unknown_job_and_spends_nothing(self):
        self.cfg["key_policies"] = {}
        before = load_retained(self.dir, self.JOB)
        reply = self._ask(EXTRA_SECRET, "restricted", "q103-1a")
        self.assertEqual("unknown_job", reply.get("rejected"))
        self.assertEqual(0, reply.get("budget_remaining"))
        self.assertEqual(before, load_retained(self.dir, self.JOB))

    def test_the_owner_opens_it_by_either_name(self):
        reply = self._ask(SECRET, "", "q103-1b")
        self.assertNotIn("rejected", reply)
        reply = self._ask(SECRET, self._fingerprint(SECRET), "q103-1c")
        self.assertNotIn("rejected", reply)
        self.assertEqual(2, self._spent())

    def test_an_owner_that_is_not_text_is_the_default_key(self):
        self.cfg["key_policies"] = {}
        owners = (None, 7, ["restricted"], {"k": "restricted"})
        for n, owner in enumerate(owners):
            save_retained(self.dir, self.JOB, dict(
                self.RECORD, saved_at=time.time(), key=owner))
            reply = self._ask(EXTRA_SECRET, "restricted", f"q103-1d-{n}")
            self.assertEqual("unknown_job", reply.get("rejected"), owner)

    def test_an_expired_record_of_another_key_is_unknown_not_expired(self):
        self.cfg["key_policies"] = {}
        save_retained(self.dir, self.JOB, dict(self.RECORD, saved_at=1.0))
        reply = self._ask(EXTRA_SECRET, "restricted", "q103-1e")
        self.assertEqual("unknown_job", reply.get("rejected"))
        reply = self._ask(SECRET, "", "q103-1f")
        self.assertEqual("expired", reply.get("rejected"))

    def test_an_artifact_note_keeps_its_owner(self):
        note = runner._artifact_note(
            self.JOB, {"kind": "exec", "script": "true"},
            {"artifact_scan": ["eicar"], "exit_code": 0}, key="restricted")
        self.assertEqual("restricted", note["key"])
        self.assertEqual("", runner._artifact_note(
            self.JOB, {}, {"artifact_scan": ["x"]})["key"])
        self.assertEqual("", runner._artifact_note(
            self.JOB, {}, {"artifact_scan": ["x"]}, key=None)["key"])
        save_retained(self.dir, self.JOB, note)
        self.cfg["key_policies"] = {}
        reply = self._ask(SECRET, "", "q103-1g")
        self.assertEqual("unknown_job", reply.get("rejected"))


class DefaultKeyPolicyTest(_Door):
    """Item 2."""

    def test_a_policy_on_the_owner_binds_the_query_door(self):
        self.cfg["key_policies"] = {"": {"allowed_kinds": ["exec"]}}
        reply = self._ask(SECRET, "", "q103-2a")
        self.assertEqual("policy", reply.get("rejected"))
        reply = self._ask(SECRET, self._fingerprint(SECRET), "q103-2b")
        self.assertEqual("policy", reply.get("rejected"))
        self.assertEqual(0, self._spent())

    def test_a_policy_that_lists_the_door_admits_the_owner(self):
        self.cfg["key_policies"] = {"": {"allowed_kinds": ["exec", "query"]}}
        reply = self._ask(SECRET, "", "q103-2c")
        self.assertNotIn("rejected", reply)

    def test_the_deny_flag_still_leaves_the_owner_alone(self):
        self.cfg["key_policies"] = {}
        self.cfg["key_policies_default_deny"] = True
        reply = self._ask(SECRET, "", "q103-2d")
        self.assertNotIn("rejected", reply)

    def test_every_door_reads_the_owner_entry(self):
        cfg = {"key_policies": {"": {"allowed_kinds": ["exec", "board"]}}}
        for door, refused in (("query", True), ("board", False), ("v2", True)):
            why = V.check_door_policy(cfg, self.secrets, "", door)
            self.assertEqual(refused, why is not None, door)

    def test_a_policy_entry_that_is_not_an_object_is_refused(self):
        cfg = {"key_policies": {"restricted": "everything"}}
        with unittest.mock.patch.object(V, "build_key_policies",
                                        return_value=cfg["key_policies"]):
            why = V.check_door_policy(cfg, self.secrets, "restricted", "query")
        self.assertEqual("invalid key policy entry", why)


class FreshnessBeforePolicyTest(_Door):
    """Item 3."""

    def _ask_raw(self, secret, key_id, query_id, **over):
        obj = {"v": 1, "type": "query", "query_id": query_id,
               "job_id": self.JOB, "issued_at": _now(),
               "queries": [{"op": "tail", "lines": 1}]}
        obj.update(over)
        if key_id:
            obj["key_id"] = key_id
        subject = "[HOMING-PIGEON] query " + query_id
        smtp = FakeSMTP()
        runner.handle_query_mail(
            self.cfg, FakeIMAP([]), smtp, b"1",
            _mail(subject, _sealed(obj, query_id, secret, key_id)),
            subject, self.secrets, _Opts(), self.dir, {})
        return smtp

    def test_a_stale_query_from_a_denied_key_is_silence(self):
        self.cfg["key_policies"] = {"restricted": {"allowed_kinds": ["exec"]}}
        smtp = self._ask_raw(EXTRA_SECRET, "restricted", "q103-3a",
                             issued_at="2001-01-01T00:00:00Z")
        self.assertEqual([], smtp.sent)

    def test_a_stale_query_from_the_owner_is_silence_too(self):
        smtp = self._ask_raw(SECRET, "", "q103-3b",
                             issued_at="2001-01-01T00:00:00Z")
        self.assertEqual([], smtp.sent)

    def test_a_version_2_query_from_a_denied_key_is_unsupported(self):
        self.cfg["key_policies"] = {"restricted": {"allowed_kinds": ["exec"]}}
        smtp = self._ask_raw(EXTRA_SECRET, "restricted", "q103-3c", v=2)
        self.assertEqual(1, len(smtp.sent))
        from runner.tests.test_q98_doors import _reply
        reply = _reply(smtp, EXTRA_SECRET, "q103-3c")
        self.assertEqual("unsupported", reply.get("rejected"))


import unittest.mock  # noqa: E402

from datetime import datetime, timedelta, timezone  # noqa: E402

from runner.ops import queries as Q  # noqa: E402
from runner.wire import verify as V2  # noqa: E402


class QueryDoorShotgunTest(_Door):
    """The shotgun family for queue item 52, Q103: the query
    door -- an ownerless record was not the owner's; the
    owner's policy did not reach every door; policy ran before
    freshness (fixed f02356a2 and 8d9e9102, 27-Oct-2026). The
    fixes made a retained record with no key, or a key that is
    not text, the default key's; made a key_policies entry on
    the default key bind it at the query, board and v2 doors
    (only the deny flag exempts the owner); made the three
    doors read policy after v, type and freshness; and made a
    query's replay entry its sender's (the owner keeps
    query:<id>, every other key's entry carries its canonical
    name). This family scattershots everything around those
    failures: owner shapes in the record, policy entries under
    every name of a key, freshness shapes of every kind, and
    the seen-key leg end to end. The fixes' own tests live in
    this file (and in test_q103_seen_key.py for the seen-key
    leg, pinned here at the same door), so the family lives
    here. One regression test was never going to be enough for
    a bug that took days of CPU to find.

    Per-field enumeration: the record's key field (missing,
    empty, text, and every non-text type), the key_policies
    map (the entry's name -- empty, canonical, fingerprint --
    its allowed_kinds list, and the deny flag), the query's
    own fields (v, issued_at, key_id, query_id), and the door
    (query, board, v2, cancel, and an unknown door, enumerated
    in the generated check_door_policy tests). Bookends and run
    lengths, in the form this surface takes them: repeated
    asks (a policy or unknown-job refusal spends nothing, run
    after run; the owner's asks spend exactly one each), stale
    shapes at both ends of the window and past both bounds,
    and query ids carried at the bookends of two keys' traffic.

    Proof of work. The unit tests are the 51 methods of this
    class: 35 hand-written seams plus 16 generated
    check_door_policy tests. The fuzzing was executed, not
    just the tests written: runner/tools/de_dust_corpus.py grow
    --target query --rounds 400 --seed 20261153 against the
    banked query corpus (167 entries). Result:
    400 rounds, 0 crashes, 0 slow, arcs
    unchanged at 903, slowest try 9214 ms; the ownerless and
    policy shapes did not recur. The grow's bookkeeping writes
    were reverted and are not banked (banking is the rigs'
    hourly job). None of this is exotic: it is combinatorics --
    systematically trying the combinations a hand-written list
    would never reach, then pinning each answer as a test."""

    # -- helpers --

    def _record(self, **over):
        rec = dict(self.RECORD, saved_at=time.time())
        rec.update(over)
        save_retained(self.dir, self.JOB, rec)
        return rec

    def _ask_raw2(self, secret, key_id, query_id, seen=None, **over):
        obj = {"v": 1, "type": "query", "query_id": query_id,
               "job_id": self.JOB, "issued_at": _now(),
               "queries": [{"op": "tail", "lines": 1}]}
        obj.update(over)
        if "issued_at" in over and over["issued_at"] is None:
            del obj["issued_at"]
        if key_id:
            obj["key_id"] = key_id
        subject = "[HOMING-PIGEON] query " + query_id
        smtp = FakeSMTP()
        runner.handle_query_mail(
            self.cfg, FakeIMAP([]), smtp, b"1",
            _mail(subject, _sealed(obj, query_id, secret, key_id)),
            subject, self.secrets, _Opts(), self.dir,
            {} if seen is None else seen)
        return smtp

    def _reply2(self, smtp, secret, query_id):
        from runner.tests.test_q98_doors import _reply
        return _reply(smtp, secret, query_id)

    def _at(self, seconds):
        return (datetime.now(timezone.utc)
                + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # -- the ownerless record leg --

    def test_a_record_with_no_key_field_at_all_is_the_owners(self):
        self.cfg["key_policies"] = {}
        rec = self._record()
        rec.pop("key", None)
        save_retained(self.dir, self.JOB, rec)
        reply = self._ask(EXTRA_SECRET, "restricted", "sg52-01")
        self.assertEqual("unknown_job", reply.get("rejected"))
        reply = self._ask(SECRET, "", "sg52-02")
        self.assertNotIn("rejected", reply)

    def test_nontext_key_shapes_are_all_the_default_key(self):
        self.cfg["key_policies"] = {}
        for n, owner in enumerate((None, 7, 2.5, True, ["restricted"],
                                   {"k": "restricted"})):
            self._record(key=owner)
            reply = self._ask(EXTRA_SECRET, "restricted", f"sg52-03-{n}")
            self.assertEqual("unknown_job", reply.get("rejected"),
                             repr(owner))
            self.assertEqual(0, self._spent(), repr(owner))

    def test_an_unknown_job_refusal_spends_nothing_run_after_run(self):
        self.cfg["key_policies"] = {}
        for n in range(3):
            reply = self._ask(EXTRA_SECRET, "restricted", f"sg52-04-{n}")
            self.assertEqual("unknown_job", reply.get("rejected"))
            self.assertEqual(0, reply.get("budget_remaining"))
        self.assertEqual(0, self._spent())

    def test_the_owner_opens_an_ownerless_record_and_spends_one_each(self):
        for n in range(2):
            reply = self._ask(SECRET, "", f"sg52-05-{n}")
            self.assertNotIn("rejected", reply)
        self.assertEqual(2, self._spent())

    def test_an_expired_ownerless_record_reads_by_owner_first(self):
        self.cfg["key_policies"] = {}
        self._record(saved_at=1.0)
        reply = self._ask(EXTRA_SECRET, "restricted", "sg52-06")
        self.assertEqual("unknown_job", reply.get("rejected"))
        reply = self._ask(SECRET, "", "sg52-07")
        self.assertEqual("expired", reply.get("rejected"))

    def test_an_artifact_note_for_the_owner_answers_the_owner(self):
        note = runner._artifact_note(
            self.JOB, {"kind": "exec", "script": "true"},
            {"artifact_scan": ["eicar"], "exit_code": 0}, key="restricted")
        save_retained(self.dir, self.JOB, note)
        self.cfg["key_policies"] = {}
        reply = self._ask(EXTRA_SECRET, "restricted", "sg52-08")
        self.assertNotIn("rejected", reply)
        reply = self._ask(SECRET, "", "sg52-09")
        self.assertEqual("unknown_job", reply.get("rejected"))

    def test_a_record_owned_in_text_by_a_third_name_is_no_ones_here(self):
        self.cfg["key_policies"] = {}
        self._record(key="someone-else")
        reply = self._ask(SECRET, "", "sg52-10")
        self.assertEqual("unknown_job", reply.get("rejected"))
        reply = self._ask(EXTRA_SECRET, "restricted", "sg52-11")
        self.assertEqual("unknown_job", reply.get("rejected"))

    # -- the owner's policy reaches every door --

    def test_an_owner_policy_refusal_spends_nothing_run_after_run(self):
        self.cfg["key_policies"] = {"": {"allowed_kinds": ["exec"]}}
        for n in range(3):
            reply = self._ask(SECRET, "", f"sg52-12-{n}")
            self.assertEqual("policy", reply.get("rejected"))
        self.assertEqual(0, self._spent())

    def test_a_policy_reply_names_no_job_and_no_answers(self):
        self.cfg["key_policies"] = {"": {"allowed_kinds": ["exec"]}}
        reply = self._ask(SECRET, "", "sg52-13")
        self.assertEqual("policy", reply.get("rejected"))
        self.assertNotIn("job_id", reply)
        self.assertEqual([], reply.get("answers"))

    def test_an_owner_policy_under_the_fingerprint_name_binds(self):
        fp = self._fingerprint(SECRET)
        self.cfg["key_policies"] = {fp: {"allowed_kinds": ["exec"]}}
        reply = self._ask(SECRET, "", "sg52-14")
        self.assertEqual("policy", reply.get("rejected"))
        reply = self._ask(SECRET, fp, "sg52-15")
        self.assertEqual("policy", reply.get("rejected"))

    def test_a_policy_listing_board_only_refuses_query_admits_board(self):
        self.cfg["key_policies"] = {"": {"allowed_kinds": ["board"]}}
        reply = self._ask(SECRET, "", "sg52-16")
        self.assertEqual("policy", reply.get("rejected"))
        self.assertIsNone(V2.check_door_policy(
            self.cfg, self.secrets, "", "board"))
        self.assertIsNotNone(V2.check_door_policy(
            self.cfg, self.secrets, "", "v2"))

    def test_default_deny_binds_a_record_owning_extra_key(self):
        self._record(key="restricted")
        self.cfg["key_policies"] = {}
        self.cfg["key_policies_default_deny"] = True
        reply = self._ask(EXTRA_SECRET, "restricted", "sg52-17")
        self.assertEqual("policy", reply.get("rejected"))
        self.assertEqual(0, self._spent())

    def test_a_policy_without_allowed_kinds_admits_the_door(self):
        # The policy carries a recognised field but no
        # allowed_kinds, so no door is fenced off. It used to
        # carry only {"note": "watched"}: an unrecognised field
        # built to an empty policy under warn-and-drop, but
        # Q129 (2026-11-06) put key policies in the refuse
        # class -- an unrecognised field now refuses the build
        # (see the companion test below) -- so the
        # no-allowed_kinds shape is built from a field the
        # builder recognises.
        self._record(key="restricted")
        self.cfg["key_policies"] = {
            "restricted": {"max_timeout_sec": 300}}
        reply = self._ask(EXTRA_SECRET, "restricted", "sg52-18")
        self.assertNotIn("rejected", reply)

    def test_a_policy_with_an_unrecognised_field_is_unreadable(self):
        # Q129 at this door: a policy carrying a field the
        # builder does not recognise does not silently build to
        # a smaller policy; check_door_policy reports the
        # policies unreadable and the query is refused as a
        # policy rejection, spending nothing.
        self._record(key="restricted")
        self.cfg["key_policies"] = {"restricted": {"note": "watched"}}
        why = V2.check_door_policy(
            self.cfg, self.secrets, "restricted", "query")
        self.assertIsNotNone(why)
        self.assertIn("unreadable", why)
        self.assertIn("note", why)
        reply = self._ask(EXTRA_SECRET, "restricted", "sg52-18b")
        self.assertEqual("policy", reply.get("rejected"))
        self.assertEqual(0, self._spent())

    def test_an_allowed_kinds_that_is_not_a_list_is_unreadable(self):
        self._record(key="restricted")
        self.cfg["key_policies"] = {
            "restricted": {"allowed_kinds": "query"}}
        why = V2.check_door_policy(
            self.cfg, self.secrets, "restricted", "query")
        self.assertIsNotNone(why)
        self.assertIn("unreadable", why)

    def test_an_empty_allowed_kinds_is_unreadable_too(self):
        self.cfg["key_policies"] = {
            "restricted": {"allowed_kinds": []}}
        why = V2.check_door_policy(
            self.cfg, self.secrets, "restricted", "query")
        self.assertIsNotNone(why)
        self.assertIn("unreadable", why)

    def test_a_door_refusal_message_names_the_door(self):
        self.cfg["key_policies"] = {"": {"allowed_kinds": ["exec"]}}
        why = V2.check_door_policy(self.cfg, self.secrets, "", "query")
        self.assertEqual("query is not in this key's allowed_kinds", why)
        why = V2.check_door_policy(self.cfg, self.secrets, "", "board")
        self.assertEqual("board is not in this key's allowed_kinds", why)

    def test_a_policy_on_an_unrelated_key_does_not_bind_the_owner(self):
        self.cfg["key_policies"] = {
            "restricted": {"allowed_kinds": ["exec"]}}
        reply = self._ask(SECRET, "", "sg52-27")
        self.assertNotIn("rejected", reply)
        self.assertEqual(1, self._spent())

    def test_a_query_inside_the_freshness_window_still_answers(self):
        smtp = self._ask_raw2(SECRET, "", "sg52-28",
                              issued_at=self._at(-3500))
        self.assertEqual(1, len(smtp.sent))

    def test_a_record_with_an_empty_string_key_is_the_owners(self):
        self.cfg["key_policies"] = {}
        self._record(key="")
        reply = self._ask(EXTRA_SECRET, "restricted", "sg52-29")
        self.assertEqual("unknown_job", reply.get("rejected"))
        reply = self._ask(SECRET, "", "sg52-30")
        self.assertNotIn("rejected", reply)

    def test_a_stale_version_2_query_is_unsupported_not_silent(self):
        # The v check runs before freshness at this door (the
        # doors read policy after v, type and freshness): a stale
        # v2 query is answered unsupported, where a stale v1
        # query is silence.
        smtp = self._ask_raw2(SECRET, "", "sg52-31", v=2,
                              issued_at="2001-01-01T00:00:00Z")
        self.assertEqual(1, len(smtp.sent))
        reply = self._reply2(smtp, SECRET, "sg52-31")
        self.assertEqual("unsupported", reply.get("rejected"))

    def test_a_query_only_policy_refuses_board_and_opens_query(self):
        self.cfg["key_policies"] = {"": {"allowed_kinds": ["query"]}}
        self.assertIsNotNone(V2.check_door_policy(
            self.cfg, self.secrets, "", "board"))
        reply = self._ask(SECRET, "", "sg52-32")
        self.assertNotIn("rejected", reply)

    # -- freshness before policy, every stale shape --

    def test_a_stale_query_from_an_allowed_key_is_silence(self):
        self._record(key="restricted")
        self.cfg["key_policies"] = {
            "restricted": {"allowed_kinds": ["query"]}}
        smtp = self._ask_raw2(EXTRA_SECRET, "restricted", "sg52-19",
                              issued_at="2001-01-01T00:00:00Z")
        self.assertEqual([], smtp.sent)
        self.assertEqual(0, self._spent())

    def test_a_future_query_past_the_bound_is_silence(self):
        smtp = self._ask_raw2(SECRET, "", "sg52-20",
                              issued_at=self._at(3600))
        self.assertEqual([], smtp.sent)

    def test_a_query_an_hour_old_is_silence_for_every_key(self):
        old = self._at(-3600)
        self.assertEqual([], self._ask_raw2(
            SECRET, "", "sg52-21", issued_at=old).sent)
        self.assertEqual([], self._ask_raw2(
            EXTRA_SECRET, "restricted", "sg52-22", issued_at=old).sent)

    def test_malformed_issued_at_shapes_are_silence(self):
        for n, bad in enumerate(("not-a-time", "", "2030-01-01T00:00:00",
                                 "2001-13-45T99:99:99Z")):
            smtp = self._ask_raw2(SECRET, "", f"sg52-23-{n}",
                                  issued_at=bad)
            self.assertEqual([], smtp.sent, bad)

    def test_a_query_with_no_issued_at_is_silence(self):
        smtp = self._ask_raw2(SECRET, "", "sg52-24", issued_at=None)
        self.assertEqual([], smtp.sent)

    def test_a_fresh_denied_query_gets_the_policy_reply_not_silence(self):
        self._record(key="restricted")
        self.cfg["key_policies"] = {
            "restricted": {"allowed_kinds": ["exec"]}}
        smtp = self._ask_raw2(EXTRA_SECRET, "restricted", "sg52-25")
        self.assertEqual(1, len(smtp.sent))
        reply = self._reply2(smtp, EXTRA_SECRET, "sg52-25")
        self.assertEqual("policy", reply.get("rejected"))

    def test_a_version_3_query_is_unsupported_not_policy(self):
        self.cfg["key_policies"] = {"": {"allowed_kinds": ["exec"]}}
        smtp = self._ask_raw2(SECRET, "", "sg52-26", v=3)
        self.assertEqual(1, len(smtp.sent))
        reply = self._reply2(smtp, SECRET, "sg52-26")
        self.assertEqual("unsupported", reply.get("rejected"))

    # -- the seen-key leg (8d9e9102), at this door --

    def test_seen_key_owner_plain_under_both_names(self):
        fp = self._fingerprint(SECRET)
        plain = runner._seen_key(self.cfg, "query:q1")
        self.assertEqual(
            Q.query_seen_key(self.cfg, self.secrets, "", "q1"), plain)
        self.assertEqual(
            Q.query_seen_key(self.cfg, self.secrets, fp, "q1"), plain)

    def test_seen_key_extra_key_carries_its_canonical_name(self):
        fp = [k for k, v in self.secrets.items()
              if k.startswith("k-") and v == EXTRA_SECRET][0]
        by_name = Q.query_seen_key(self.cfg, self.secrets,
                                   "restricted", "q1")
        by_fp = Q.query_seen_key(self.cfg, self.secrets, fp, "q1")
        self.assertEqual(by_name, by_fp)
        self.assertIn("restricted", by_name)
        self.assertNotEqual(
            by_name, Q.query_seen_key(self.cfg, self.secrets,
                                      "restricted", "q2"))

    def test_two_keys_sharing_a_query_id_do_not_silence_each_other(self):
        seen = {}
        self._record(key="restricted")
        smtp = self._ask_raw2(EXTRA_SECRET, "restricted", "shared-52",
                              seen=seen)
        self.assertEqual(1, len(smtp.sent))
        smtp = self._ask_raw2(SECRET, "", "shared-52", seen=seen)
        self.assertEqual(1, len(smtp.sent))

    def test_a_replay_from_the_same_key_is_dropped(self):
        seen = {}
        self.assertEqual(1, len(self._ask_raw2(
            SECRET, "", "once-52", seen=seen).sent))
        self.assertEqual(0, len(self._ask_raw2(
            SECRET, "", "once-52", seen=seen).sent))
        self.assertEqual(1, len(self._ask_raw2(
            EXTRA_SECRET, "restricted", "once-52", seen=seen).sent))

    def test_a_pre_rule_plain_entry_still_drops_the_owners_replay(self):
        seen = {runner._seen_key(self.cfg, "query:old-52"): True}
        smtp = self._ask_raw2(SECRET, "", "old-52", seen=seen)
        self.assertEqual(0, len(smtp.sent))

    def test_a_bad_signature_marks_nothing_in_seen(self):
        seen = {}
        subject = "[HOMING-PIGEON] query forged-52"
        runner.handle_query_mail(
            self.cfg, FakeIMAP([]), FakeSMTP(), b"1",
            _mail(subject, "not a signed body"), subject,
            self.secrets, _Opts(), self.dir, seen)
        self.assertEqual(seen, {})


def _make_door_policy_test(cfg, key_id, door, want_refused, use_fp=False):
    def run(self):
        self.cfg["key_policies"] = cfg.get("key_policies", {})
        if cfg.get("deny"):
            self.cfg["key_policies_default_deny"] = True
        kid = self._fingerprint(SECRET) if use_fp else key_id
        why = V2.check_door_policy(self.cfg, self.secrets, kid, door)
        self.assertEqual(want_refused, why is not None,
                         f"{kid} at {door}: {why}")
    return run


# 16 generated door-policy tests: every door against the
# owner's and the extra key's policy entries, the deny flag,
# the cancel door's own rule, and the door/key-id edges.
_DOOR_CASES = (
    ({"key_policies": {"": {"allowed_kinds": ["exec"]}}}, "", "query", True, False),
    ({"key_policies": {"": {"allowed_kinds": ["exec"]}}}, "", "board", True, False),
    ({"key_policies": {"": {"allowed_kinds": ["exec"]}}}, "", "v2", True, False),
    ({"key_policies": {"": {"allowed_kinds": ["exec"]}}}, "", "cancel", False, False),
    ({"key_policies": {"": {"allowed_kinds": ["query"]}}}, "", "query", False, False),
    ({"key_policies": {"": {"allowed_kinds": ["board"]}}}, "", "board", False, False),
    ({"key_policies": {}}, "", "query", False, False),
    ({"key_policies": {"restricted": {"allowed_kinds": ["exec"]}}}, "restricted", "query", True, False),
    ({"key_policies": {"restricted": {"allowed_kinds": ["query"]}}}, "restricted", "query", False, False),
    ({"key_policies": {}, "deny": True}, "restricted", "board", True, False),
    ({"key_policies": {}, "deny": True}, "", "board", False, False),
    ({"key_policies": {}}, "", "teleport", True, False),
    ({"key_policies": {}}, None, "query", True, False),
    ({"key_policies": {"restricted": {"allowed_kinds": []}}}, "restricted", "query", True, False),
    ({"key_policies": {"": {"allowed_kinds": ["exec"]}}}, "", "query", True, True),
    ({"key_policies": {"restricted": {"allowed_kinds": ["exec", "board", "v2", "query"]}}}, "restricted", "v2", False, False),
)
for _i, (_cfg, _kid, _door, _want, _fp) in enumerate(_DOOR_CASES):
    setattr(QueryDoorShotgunTest, f"test_door_policy_{_i:02d}",
            _make_door_policy_test(_cfg, _kid, _door, _want, _fp))
del _i, _cfg, _kid, _door, _want, _fp


if __name__ == "__main__":
    unittest.main()
