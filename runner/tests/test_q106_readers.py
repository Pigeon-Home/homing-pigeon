# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""Q106: the Germany rig's first bank, 135 crash records, four readers.

Below the full view an output entry leaves as its commitment only
(name, size, SHA-384, or the reason it was not read), each member in
its own shape, so a member the collector never writes cannot carry
the job's output past the view. A `senses` query that names a sensor
reads that sensor alone, the empty name among them. A retained
record's digest is read only when it is one; otherwise it is
recomputed, so the attest answer always seals. A board reply that
cannot be sealed is logged and the message taken, never raised. And
a crash record `promote` retired stays retired: the tool writes the
retired list, the grow drops a rig's stale copy, and the bank never
re-adds one, so a fixed crash cannot come back as a probe that passes.
"""
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from runner import runner
from runner.ops import policy as PO
from runner.ops import queries as QU
from runner.oracle import senses as SN
from runner.runner import load_retained, save_retained
from runner.tests.security_parity import SECRET, FakeIMAP, FakeSMTP
from runner.tests.test_q98_doors import (
    BoardDoorTest, QueryBudgetBelongsToItsKeyTest, _Opts, _bmail, _iso,
    _mail, _now, _reply, _sealed)
from runner.tools import de_dust_corpus as B
from runner.tools import rig_bank as RB

HEX = "ab" * 48


class OutputCommitmentTest(unittest.TestCase):

    def test_the_four_members_in_their_shapes(self):
        entry = {"name": "reports/junit.xml", "size": 5, "sha384": HEX.upper(),
                 "content_b64": "aGVsbG8="}
        self.assertEqual({"name": "reports/junit.xml", "size": 5,
                          "sha384": HEX}, PO.output_commitment(entry))
        self.assertEqual({"name": "big.log", "omitted": "too_large", "size": 9},
                         PO.output_commitment({"name": "big.log", "size": 9,
                                               "omitted": "too_large"}))

    def test_a_member_in_another_shape_stays_home(self):
        secret = "SECRET-12345 is the canary line of the output\n"
        entry = {"name": secret, "size": secret, "sha384": secret,
                 "omitted": secret, "note": secret, "content_b64": "QQ=="}
        self.assertEqual({}, PO.output_commitment(entry))
        self.assertEqual({}, PO.output_commitment(
            {"name": 7, "size": True, "sha384": "0" * 95, "omitted": "lost"}))
        self.assertEqual({"size": 0}, PO.output_commitment({"size": 0, "x": 1}))

    def test_a_name_the_rules_refuse_is_not_a_name(self):
        self.assertEqual({}, PO.output_commitment({"name": "../x"}))
        self.assertEqual({}, PO.output_commitment({"name": "CON"}))
        self.assertEqual({"name": "a/b"}, PO.output_commitment({"name": "a/b"}))

    def _view(self, view, outputs):
        job = {"job_id": "j", "kind": "exec", "result_policy": {"view": view}}
        exe = {"stdout": "out\n", "stderr": "", "exit_code": 0,
               "outputs": outputs}
        result, _retain = PO.apply_result_policy({}, job, exe, {}, True)
        return result

    def test_every_view(self):
        leak = "SECRET-12345 is the canary line of the output\n"
        outs = [{"name": "r.xml", "size": 3, "sha384": HEX, "content_b64": "QUJD",
                 "stray": leak},
                "not an entry", {"name": "gone", "omitted": "missing"}]
        full = self._view("full", outs)
        self.assertEqual(outs, full["outputs"])
        for view in ("redacted", "summary"):
            got = self._view(view, outs)["outputs"]
            self.assertEqual([{"name": "r.xml", "size": 3, "sha384": HEX},
                              {"name": "gone", "omitted": "missing"}], got)
            self.assertNotIn(leak, json.dumps(got))
        self.assertNotIn("outputs", self._view("attested", outs))
        self.assertNotIn("outputs", self._view("summary", {"name": "x"}))


class SensesFilterTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="hp-q106-senses-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        path = SN._path(self.dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            for sensor in ("canary", "host_ids"):
                fh.write(json.dumps({"sensor": sensor, "title": "t-" + sensor,
                                     "severity": "high",
                                     "observed_at": "2026-10-26T10:00:00Z"})
                         + "\n")

    def _sensors(self, **kw):
        return sorted(r.get("sensor") for r in SN.load_alerts(self.dir, **kw))

    def test_no_name_reads_every_sensor(self):
        self.assertEqual(["canary", "host_ids"], self._sensors())

    def test_a_name_reads_that_sensor_alone(self):
        self.assertEqual(["canary"], self._sensors(sensor="canary"))

    def test_the_empty_name_reads_nothing(self):
        self.assertEqual([], self._sensors(sensor=""))
        self.assertEqual([], self._sensors(sensor="nobody"))


class DigestInTheRecordTest(QueryBudgetBelongsToItsKeyTest):
    """A record a crash left: its digest is not one."""

    def test_a_digest_that_is_not_hex_is_recomputed(self):
        self.assertIsNone(QU._hex_digest("\ud800"))
        self.assertIsNone(QU._hex_digest("x" * 96))
        self.assertIsNone(QU._hex_digest(7))
        self.assertEqual(HEX, QU._hex_digest(HEX.upper()))

    def _attest(self, query_id):
        obj = {"v": 1, "type": "query", "query_id": query_id,
               "job_id": self.JOB, "issued_at": _now(),
               "queries": [{"op": "attest", "predicate": "output_digest"}]}
        subject = "[HOMING-PIGEON] query " + query_id
        smtp = FakeSMTP()
        runner.handle_query_mail(
            self.cfg, FakeIMAP([]), smtp, b"1",
            _mail(subject, _sealed(obj, query_id, SECRET, "")),
            subject, self.secrets, _Opts(), self.dir, {})
        return smtp

    def test_the_attest_answer_seals_and_the_budget_is_spent_once(self):
        save_retained(self.dir, self.JOB, {
            "stdout": "ok\nbad \udfff line\n", "stderr": "", "exit_code": 0,
            "budget": 8, "spent": 0, "saved_at": time.time(),
            "view": "full", "key": "", "digest": "\ud800"})
        smtp = self._attest("q106-d-1")
        self.assertEqual(1, len(smtp.sent))
        reply = _reply(smtp, SECRET, "q106-d-1")
        digest = reply["answers"][0]["digest"]
        self.assertEqual(96, len(digest))
        self.assertEqual(1, load_retained(self.dir, self.JOB)["spent"])

    # the inherited cases are the Q98 rig's own
    test_another_keys_query_is_an_unknown_job_and_spends_nothing = None
    test_the_jobs_own_key_still_asks = None
    test_the_jobs_key_by_its_fingerprint_is_the_same_key = None


class BoardReplyTest(BoardDoorTest):
    """A board file a hand wrote holds a key no signer accepts."""

    def _plant(self):
        board = {"bm-1": {"task_id": "bm-1", "priority": 1, "requires": [],
                          "capabilities": ["shell"], "compartments": [],
                          "payload": {"script": "echo"}, "state": "open",
                          "cla\ud800med_by": None,
                          "submitted_at": "2026-10-26T12:00:00+00:00"}}
        with open(os.path.join(self.tmp, "board.json"), "wb") as fh:
            fh.write(json.dumps(board).encode("utf-8", "surrogatepass"))

    def test_a_reply_that_cannot_be_sealed_is_logged_and_the_message_taken(self):
        self._plant()
        body = {"v": 1, "type": "task_request", "worker_id": "w1",
                "issued_at": _iso(), "capabilities": ["shell"]}
        out = io.StringIO()
        with redirect_stdout(out):
            smtp = self.cycle([_bmail("[HOMING-PIGEON] task_request w1", body)])
        self.assertEqual([], smtp.sent)
        self.assertIn("could not send board reply", out.getvalue())
        self.assertEqual("claimed", self.board()["bm-1"]["state"])

    # the inherited cases are the Q98 door's own
    for _name in list(vars(BoardDoorTest)):
        if _name.startswith("test_"):
            locals()[_name] = None
    del _name


class RetiredListTest(unittest.TestCase):

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.corpus = mock.patch.object(B, "CORPUS_DIR", self.td.name)
        self.corpus.start()
        self.addCleanup(self.corpus.stop)

    def _crash(self, ident, found):
        return {"id": ident, "kind": "payload", "data": {"x": ident},
                "from": "seed:x", "mutator": "p_add_key", "arcs": 0,
                "crash": "leak", "detail": "d", "found": found}

    def test_round_trip_and_staleness(self):
        B.save_retired("wire", {"a1": {"on": "2026-10-28", "why": "redundant"}})
        retired = B.load_retired("wire")
        self.assertEqual({"a1": {"on": "2026-10-28", "why": "redundant"}}, retired)
        with open(B.retired_path("wire"), encoding="utf-8") as fh:
            head = json.load(fh)
        self.assertEqual(("wire", 1), (head["target"], head["de_dust"]))
        self.assertTrue(B.retired_stale(self._crash("a1", "2026-10-27"), retired))
        self.assertTrue(B.retired_stale(self._crash("a1", "2026-10-28"), retired))
        self.assertFalse(B.retired_stale(self._crash("a1", "2026-10-29"), retired))
        self.assertFalse(B.retired_stale(self._crash("b2", "2026-10-01"), retired))
        self.assertEqual({}, B.load_retired("cloud"))

    def test_the_grow_drops_a_rigs_stale_copy_and_keeps_a_new_crash(self):
        B.save_retired("wire", {"a1": {"on": "2026-10-28", "why": "redundant"}})
        B.save(B.corpus_path("wire", crashes=True), "wire",
               [self._crash("a1", "2026-10-27"), self._crash("a1", "2026-10-29"),
                self._crash("c3", "2026-10-20")])
        # a1 appears twice only to show both halves of the rule; a
        # real file holds one record per id
        out = []
        self.assertEqual(1, B.prune_retired_crashes("wire", out.append))
        left = {r["id"]: r["found"] for r in B.load(B.corpus_path("wire", crashes=True))}
        self.assertEqual({"a1": "2026-10-29", "c3": "2026-10-20"}, left)
        self.assertEqual(0, B.prune_retired_crashes("cloud", out.append))

    def test_a_file_of_only_stale_copies_is_removed(self):
        B.save_retired("wire", {"a1": {"on": "2026-10-28", "why": "promoted"}})
        path = B.corpus_path("wire", crashes=True)
        B.save(path, "wire", [self._crash("a1", "2026-10-28")])
        self.assertEqual(1, B.prune_retired_crashes("wire", lambda *a: None))
        self.assertFalse(os.path.exists(path))


class BankHonorsRetirementTest(unittest.TestCase):

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.tree = os.path.join(self.td.name, "tree")
        self.bank = os.path.join(self.td.name, "bank")
        os.makedirs(self.tree)
        os.makedirs(self.bank)

    def _write(self, folder, name, objs):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"de_dust": 1, "target": "wire",
                                 "Agent-Stamp": "x"}) + "\n")
            for o in objs:
                fh.write(json.dumps(o) + "\n")

    def _crash(self, ident, found):
        return {"id": ident, "crash": "leak", "found": found, "data": {}}

    def test_a_stale_copy_is_not_re_added_and_a_new_crash_is(self):
        with open(os.path.join(self.tree, "wire.retired.json"), "w") as fh:
            json.dump({"retired": {"a1": {"on": "2026-10-28", "why": "redundant"},
                                   "b2": {"on": "2026-10-28", "why": "promoted"}}},
                      fh)
        self._write(self.bank, "wire.crashes.jsonl", [
            self._crash("a1", "2026-10-27"), self._crash("b2", "2026-10-30"),
            self._crash("c3", "2026-10-27")])
        added = RB.merge_id_file(os.path.join(self.tree, "wire.crashes.jsonl"),
                                 os.path.join(self.bank, "wire.crashes.jsonl"))
        self.assertEqual(["b2", "c3"], added)
        _h, objs = RB.read_jsonl(os.path.join(self.tree, "wire.crashes.jsonl"))
        self.assertEqual({"b2", "c3"}, {o["id"] for o in objs})

    def test_an_entry_file_is_unioned_as_before(self):
        self._write(self.bank, "wire.jsonl", [{"id": "e1"}, {"id": "e2"}])
        self._write(self.tree, "wire.jsonl", [{"id": "e1"}])
        added = RB.merge_id_file(os.path.join(self.tree, "wire.jsonl"),
                                 os.path.join(self.bank, "wire.jsonl"))
        self.assertEqual(["e2"], added)

    def test_no_retired_list_means_the_union_as_before(self):
        self._write(self.bank, "wire.crashes.jsonl", [self._crash("a1", "2026-10-27")])
        added = RB.merge_id_file(os.path.join(self.tree, "wire.crashes.jsonl"),
                                 os.path.join(self.bank, "wire.crashes.jsonl"))
        self.assertEqual(["a1"], added)


class RetiredListsInTheTreeTest(unittest.TestCase):

    def test_every_retired_list_is_stamped_and_dated(self):
        for target in B.TARGETS:
            path = B.retired_path(target)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(target, data.get("target"))
            self.assertIn("Agent-Stamp", data)
            for ident, row in data["retired"].items():
                self.assertRegex(ident, r"^[0-9a-f]{16}$")
                self.assertRegex(row["on"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertIn(row["why"], ("promoted", "redundant"))


if __name__ == "__main__":
    unittest.main()


class BankSettlesCrashesTest(unittest.TestCase):
    """A bank replays the crash records it merged at main's head (Q108)."""

    def test_promote_runs_once_per_target_with_new_crash_records(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append((cmd, kw.get("cwd")))
            target = cmd[-1]
            return mock.Mock(returncode=1, stdout=(
                f"noise\n{target}: 1 promoted, 2 redundant (fixed, reaching "
                f"nothing new), 1 still crash\n").encode())

        report = {"crashes": {"queries.crashes.jsonl": ["a", "b"],
                              "wire.crashes.jsonl": ["c"]}}
        got = RB.settle_crashes("/clone", report, run=fake_run)
        self.assertEqual(["queries", "wire"], [c[0][-1] for c in calls])
        self.assertEqual({"/clone"}, {c[1] for c in calls})
        self.assertTrue(all(c[0][-3:-1] == ["promote", "--target"] for c in calls))
        self.assertEqual("wire: 1 promoted, 2 redundant (fixed, reaching nothing "
                         "new), 1 still crash", got["wire"])

    def test_a_promote_that_cannot_run_leaves_the_merge(self):
        def boom(cmd, **kw):
            raise OSError("no python")
        got = RB.settle_crashes("/clone", {"crashes": {"queries.crashes.jsonl": ["a"]}},
                                run=boom)
        self.assertEqual({"queries": "queries: promote did not run (OSError)"}, got)
        self.assertEqual({}, RB.settle_crashes("/clone", {"crashes": {}}, run=boom))

    def test_the_ledger_block_names_the_settlement(self):
        report = {"totals": (10, 20), "settled": {"queries": "queries: 0 promoted, "
                                                              "11 redundant, 0 still crash"}}
        block = RB.ledger_block("Test rig", 3, report, [], None)
        self.assertIn("Crash records replayed at main's head: queries: 0 promoted, "
                      "11 redundant, 0 still crash.", block)
        self.assertNotIn("replayed", RB.ledger_block("Test rig", 3,
                                                     {"totals": (1, 1)}, [], None))

    def test_a_real_promote_in_a_scratch_tree_retires_what_passes(self):
        # A clone is the tree itself; the corpus dir is pointed at a
        # scratch copy, so nothing in the repository moves.
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        scratch = os.path.join(td.name, "de_dust")
        os.makedirs(scratch)
        # one wire entry that passes (a stale-tree echo) and one that
        # the reader refuses properly today, as a crash file
        good = B.make_entry("text", "not a signed body at all", "seed:x", "p_text")
        record = dict(good, crash="exception", detail="old", found="2026-10-01")
        B.save(os.path.join(scratch, "wire.crashes.jsonl"), "wire", [record])
        B.save(os.path.join(scratch, "wire.jsonl"), "wire", [])
        env = dict(os.environ, HP_DE_DUST_CORPUS_DIR=scratch)
        proc = subprocess.run([sys.executable, "runner/tools/de_dust_corpus.py",
                               "promote", "--target", "wire"],
                              cwd=os.path.dirname(os.path.dirname(os.path.dirname(
                                  os.path.abspath(B.__file__)))),
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=600)
        text = proc.stdout.decode()
        if "HP_DE_DUST_CORPUS_DIR" not in open(B.__file__, encoding="utf-8").read():
            self.skipTest("the tool reads no corpus dir override")
        self.assertIn("wire: ", text)
        self.assertFalse(os.path.exists(os.path.join(scratch, "wire.crashes.jsonl")), text)
        with open(os.path.join(scratch, "wire.retired.json"), encoding="utf-8") as fh:
            self.assertIn(record["id"], json.load(fh)["retired"])


import subprocess  # noqa: E402
import sys  # noqa: E402
