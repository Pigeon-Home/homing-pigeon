# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Q103 item 4: a query's replay entry is its sender's.

The replay cache kept `query:<query_id>` whoever signed the query, so
one key's query id silently dropped another key's query that happened
to pick the same id. The entry is set once the signature names the
sender: the owner's key keeps the plain form (entries already written
still hold), and every other key's entry carries its canonical name.
"""
import unittest

from runner import runner
from runner.ops import queries as Q
from runner.ops.queries import handle_query_mail
from runner.tests.security_parity import EXTRA_SECRET, SECRET, FakeIMAP, FakeSMTP
from runner.tests import test_q98_doors as D
from runner.tests.test_q98_doors import _Opts, _mail, _now, _reply, _sealed


class SeenKeyBySenderTest(D.QueryBudgetBelongsToItsKeyTest):
    test_another_keys_query_is_an_unknown_job_and_spends_nothing = None
    test_the_jobs_own_key_still_asks = None
    test_the_jobs_key_by_its_fingerprint_is_the_same_key = None

    def setUp(self):
        super().setUp()
        self.seen = {}

    def ask(self, secret, key_id, query_id):
        obj = {"v": 1, "type": "query", "query_id": query_id,
               "job_id": self.JOB, "issued_at": _now(),
               "queries": [{"op": "tail", "lines": 1}]}
        if key_id:
            obj["key_id"] = key_id
        subject = "[HOMING-PIGEON] query " + query_id
        smtp = FakeSMTP()
        handle_query_mail(self.cfg, FakeIMAP([]), smtp, b"1",
                          _mail(subject, _sealed(obj, query_id, secret, key_id)),
                          subject, self.secrets, _Opts(), self.dir, self.seen)
        return _reply(smtp, secret, query_id) if smtp.sent else None

    def test_another_keys_query_id_does_not_silence_the_owner(self):
        first = self.ask(EXTRA_SECRET, "restricted", "same-id")
        self.assertEqual(first.get("rejected"), "unknown_job")
        owner = self.ask(SECRET, "", "same-id")
        self.assertIsNotNone(owner, "the owner's query was dropped as a replay")
        self.assertNotIn("rejected", owner)

    def test_a_replay_from_the_same_key_is_still_dropped(self):
        self.assertIsNotNone(self.ask(SECRET, "", "once"))
        self.assertIsNone(self.ask(SECRET, "", "once"))
        self.assertIsNotNone(self.ask(EXTRA_SECRET, "restricted", "once-r"))
        self.assertIsNone(self.ask(EXTRA_SECRET, "restricted", "once-r"))

    def test_the_owner_keeps_the_plain_entry_under_any_name(self):
        fp = [k for k, v in self.secrets.items() if k.startswith("k-") and v == SECRET][0]
        plain = runner._seen_key(self.cfg, "query:q")
        self.assertEqual(Q.query_seen_key(self.cfg, self.secrets, "", "q"), plain)
        self.assertEqual(Q.query_seen_key(self.cfg, self.secrets, fp, "q"), plain)
        other = Q.query_seen_key(self.cfg, self.secrets, "restricted", "q")
        self.assertNotEqual(other, plain)
        self.assertIn("restricted", other)

    def test_an_entry_written_before_the_rule_still_drops_the_owners_replay(self):
        self.seen[runner._seen_key(self.cfg, "query:old")] = True
        self.assertIsNone(self.ask(SECRET, "", "old"))

    def test_a_bad_signature_marks_nothing(self):
        subject = "[HOMING-PIGEON] query forged"
        handle_query_mail(self.cfg, FakeIMAP([]), FakeSMTP(), b"1",
                          _mail(subject, "not a signed body"), subject,
                          self.secrets, _Opts(), self.dir, self.seen)
        self.assertEqual(self.seen, {})


if __name__ == "__main__":
    unittest.main()
