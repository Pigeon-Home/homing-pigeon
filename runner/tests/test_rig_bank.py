"""Unit tests for runner/tools/rig_bank.py, the mechanical bank.

The bank contract is section M item 7 of the standing orders:
entry files union by id, runs union stable-sorted on when under
exactly one header, totals from the merged tree, grow numbers
per rig, and a bank that cannot meet the shape refuses. These
tests pin the merge core on fixture trees; the git shell-outs
are not exercised here.
"""

import importlib.util
import json
import os
import tempfile
import unittest

_TOOL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "runner", "tools", "rig_bank.py",
)
_spec = importlib.util.spec_from_file_location("rig_bank", _TOOL)
rig_bank = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rig_bank)

HEADER = {"Agent-Stamp": "x", "de_dust": 1, "file": "runs"}
ENTRY_HEADER = {"Agent-Stamp": "x", "de_dust": 1, "target": "wire"}


def _write(path, objs, header=None):
    with open(path, "w", encoding="utf-8") as fh:
        if header is not None:
            fh.write(json.dumps(header) + "\n")
        for obj in objs:
            fh.write(json.dumps(obj) + "\n")


def _entry(eid, target="wire"):
    return {"id": eid, "target": target, "kind": "payload", "data": eid}


def _run(target, when, seed, entries_after, arcs_after, tried=10, crashes=0):
    return {
        "target": target, "when": when, "seed": seed, "tried": tried,
        "entries_before": 0, "entries_after": entries_after,
        "arcs_after": arcs_after, "crashes": crashes,
    }


class ReadJsonlTest(unittest.TestCase):
    def test_header_split(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.jsonl")
            _write(p, [_entry("a")], header=ENTRY_HEADER)
            header, objs = rig_bank.read_jsonl(p)
            self.assertEqual(header, ENTRY_HEADER)
            self.assertEqual([o["id"] for o in objs], ["a"])

    def test_torn_tail_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.jsonl")
            _write(p, [_entry("a")], header=ENTRY_HEADER)
            with open(p, "a", encoding="utf-8") as fh:
                fh.write('{"id": "b", "tar')
            _, objs = rig_bank.read_jsonl(p)
            self.assertEqual([o["id"] for o in objs], ["a"])

    def test_torn_middle_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.jsonl")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(ENTRY_HEADER) + "\n")
                fh.write('{"id": "a", "tar\n')
                fh.write(json.dumps(_entry("b")) + "\n")
            with self.assertRaises(rig_bank.TornRead):
                rig_bank.read_jsonl(p)


class MergeIdFileTest(unittest.TestCase):
    def test_union_by_id(self):
        with tempfile.TemporaryDirectory() as d:
            t = os.path.join(d, "t.jsonl")
            b = os.path.join(d, "b.jsonl")
            _write(t, [_entry("a"), _entry("b")], header=ENTRY_HEADER)
            _write(b, [_entry("b"), _entry("c")], header=ENTRY_HEADER)
            added = rig_bank.merge_id_file(t, b)
            self.assertEqual(added, ["c"])
            _, objs = rig_bank.read_jsonl(t)
            self.assertEqual({o["id"] for o in objs}, {"a", "b", "c"})

    def test_creates_missing_tree_file(self):
        with tempfile.TemporaryDirectory() as d:
            t = os.path.join(d, "t.jsonl")
            b = os.path.join(d, "b.jsonl")
            _write(b, [_entry("a")], header=ENTRY_HEADER)
            added = rig_bank.merge_id_file(t, b)
            self.assertEqual(added, ["a"])
            header, objs = rig_bank.read_jsonl(t)
            self.assertEqual(header, ENTRY_HEADER)
            self.assertEqual(len(objs), 1)


class MergeRunsTest(unittest.TestCase):
    def test_union_sorted_one_header(self):
        with tempfile.TemporaryDirectory() as d:
            t = os.path.join(d, "t.jsonl")
            b = os.path.join(d, "b.jsonl")
            r1 = _run("wire", "2026-10-28T01:00:00Z", 100, 5, 50)
            r2 = _run("wire", "2026-10-28T03:00:00Z", 100, 7, 60)
            r3 = _run("cloud", "2026-10-28T02:00:00Z", 100, 3, 30)
            _write(t, [r1, r2], header=HEADER)
            _write(b, [r1, r3], header=HEADER)
            added, merged = rig_bank.merge_runs(t, b)
            self.assertEqual(added, 1)
            self.assertEqual([o["when"] for o in merged],
                             ["2026-10-28T01:00:00Z", "2026-10-28T02:00:00Z",
                              "2026-10-28T03:00:00Z"])
            header, objs = rig_bank.read_jsonl(t)
            self.assertEqual(header, HEADER)
            self.assertEqual(len(objs), 3)

    def test_differing_headers_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            t = os.path.join(d, "t.jsonl")
            b = os.path.join(d, "b.jsonl")
            other = dict(HEADER, file="other")
            _write(t, [], header=HEADER)
            _write(b, [], header=other)
            with self.assertRaises(rig_bank.Refusal):
                rig_bank.merge_runs(t, b)

    def test_missing_header_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            t = os.path.join(d, "t.jsonl")
            b = os.path.join(d, "b.jsonl")
            _write(t, [], header=HEADER)
            _write(b, [_run("wire", "2026-10-28T01:00:00Z", 1, 1, 1)])
            with self.assertRaises(rig_bank.Refusal):
                rig_bank.merge_runs(t, b)


class MergeCorpusTest(unittest.TestCase):
    def _tree(self, root, entries, runs, crashes=None, arcs=None):
        os.makedirs(root, exist_ok=True)
        _write(os.path.join(root, "wire.jsonl"), entries, header=ENTRY_HEADER)
        _write(os.path.join(root, "runs.jsonl"), runs, header=HEADER)
        if crashes is not None:
            _write(os.path.join(root, "wire.crashes.jsonl"), crashes,
                   header=ENTRY_HEADER)
        if arcs is not None:
            with open(os.path.join(root, "wire.arcs.json"), "w") as fh:
                json.dump({"de_dust": 1, "target": "wire", "arcs": arcs}, fh)

    def test_full_merge_and_totals(self):
        with tempfile.TemporaryDirectory() as d:
            tree = os.path.join(d, "tree")
            bank = os.path.join(d, "bank")
            self._tree(tree, [_entry("a")],
                       [_run("wire", "2026-10-28T01:00:00Z", 1, 1, 10)],
                       arcs=[[1, 2]])
            self._tree(bank, [_entry("a"), _entry("b")],
                       [_run("wire", "2026-10-28T01:00:00Z", 1, 1, 10),
                        _run("wire", "2026-10-28T02:00:00Z", 2, 2, 25,
                             crashes=1)],
                       crashes=[{"id": "c1", "target": "wire", "crash": "x"}],
                       arcs=[[1, 2], [3, 4]])
            report = rig_bank.merge_corpus(tree, bank)
            self.assertEqual(report["entries"], {"wire.jsonl": ["b"]})
            self.assertEqual(report["crashes"], {"wire.crashes.jsonl": ["c1"]})
            self.assertEqual(report["arcs"], 1)
            self.assertEqual(report["runs_added"], 1)
            self.assertEqual(report["totals"], (2, 25))


class LedgerTest(unittest.TestCase):
    def test_next_grow_no_counts_only_that_rig(self):
        text = (
            "  de_dust 24 (VM rig): 1295 entries, 4978 arcs, 0 crashes filed.\n"
            "  de_dust 1 (Germany rig): 1300 entries, 5000 arcs, 0 crashes filed.\n"
            "  de_dust 25 (VM rig): 1296 entries, 4978 arcs, 0 crashes filed.\n"
        )
        self.assertEqual(rig_bank.next_grow_no(text, "Germany rig"), 2)
        # The number counts the rig's ledger summary lines, so a rig
        # whose grows were numbered before the lines carried its
        # name is the seat's to number by hand; a rig that starts
        # with rig_bank (the Germany rig) numbers from 1 correctly.
        self.assertEqual(rig_bank.next_grow_no(text, "VM rig"), 3)

    def test_ledger_block_shape(self):
        report = {"totals": (1300, 5001)}
        records = [_run("wire", "2026-10-28T02:00:00Z", 77, 2, 25,
                        tried=1234, crashes=2)]
        block = rig_bank.ledger_block("Germany rig", 3, report, records,
                                      resources="box cpu 99%")
        self.assertIn("de_dust 3 (Germany rig): 1300 entries, 5001 arcs, "
                      "2 crashes filed.", block)
        self.assertIn("1 run records, 1,234 children (seeds 77)", block)
        self.assertIn("Resources: box cpu 99%.", block)

    def test_insert_ledger_after_last_summary_block(self):
        text = (
            "## Ledger\n"
            "- rules refreshed\n"
            "  de_dust 1 (Germany rig): 5 entries, 9 arcs, 0 crashes filed.\n"
            "  Banked line one.\n"
            "  Banked line two.\n"
            "- the next block\n"
        )
        out = rig_bank.insert_ledger(text, "  de_dust 2 (Germany rig): 6 entries, 9 arcs, 0 crashes filed.\n")
        lines = out.splitlines()
        idx = lines.index("  de_dust 2 (Germany rig): 6 entries, 9 arcs, 0 crashes filed.")
        self.assertEqual(lines[idx - 1], "  Banked line two.")
        self.assertEqual(lines[idx + 1], "- the next block")

    def test_insert_ledger_appends_without_anchor(self):
        out = rig_bank.insert_ledger("## Ledger\n", "  de_dust 1 (Germany rig): 5 entries, 9 arcs, 0 crashes filed.\n")
        self.assertTrue(out.endswith("crashes filed.\n"))


if __name__ == "__main__":
    unittest.main()
