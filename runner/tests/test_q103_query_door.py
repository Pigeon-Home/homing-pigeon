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

if __name__ == "__main__":
    unittest.main()
