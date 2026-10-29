# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""runner/tools/rig_bank.py: a muster's hold stops the bank's push (Q109).

test_rig_bank holds that the file is read. This drives the whole bank
with git scripted, so what is held is the push itself: a hold standing
at the clone merges, commits and pushes nothing and exits 75; a hold
that lands while the bank runs, as the very commit that refuses its
first push, stops the retry before it merges on the new head; and with
no hold the bank pushes and lands.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

_TOOL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "runner", "tools", "rig_bank.py")
_spec = importlib.util.spec_from_file_location("rig_bank_hold", _TOOL)
RB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RB)

RUNS_HEADER = {"Agent-Stamp": "x", "de_dust": 1, "file": "runs"}
ENTRY_HEADER = {"Agent-Stamp": "x", "de_dust": 1, "target": "wire"}
ORDERS = ("# orders\n\n## Ledger\n\n"
          "- de_dust 1 (test rig): 1 entries, 10 arcs, 0 crashes\n")


def _jsonl(path, header, objs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for obj in [header] + objs:
            fh.write(json.dumps(obj) + "\n")


def _run(when, entries_after):
    return {"target": "wire", "when": when, "seed": 1, "tried": 5,
            "entries_before": 0, "entries_after": entries_after,
            "arcs_after": 10, "crashes": 0}


class _Git:
    """git, scripted: a clone writes a main with one entry, a push is
    refused `refuse` times, and `hold_at` names the step after which
    main carries docs/use/muster.hold."""

    def __init__(self, refuse=0, hold_at=None):
        self.calls = []
        self.refuse = refuse
        self.hold_at = hold_at
        self.clone = None

    def _hold(self):
        path = os.path.join(self.clone, "docs", "use", "muster.hold")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()

    def __call__(self, args, cwd, pat=None):
        verb = args[0] if args[0] != "-c" else "commit"
        self.calls.append(verb)
        if verb == "clone":
            self.clone = args[-1]
            os.makedirs(os.path.join(self.clone, "docs", "project"))
            with open(os.path.join(self.clone, RB.ORDERS_REL), "w",
                      encoding="utf-8") as fh:
                fh.write(ORDERS)
            corpus = os.path.join(self.clone, RB.CORPUS_REL)
            _jsonl(os.path.join(corpus, "wire.jsonl"), ENTRY_HEADER,
                   [{"id": "a", "target": "wire", "kind": "payload",
                     "data": "a"}])
            _jsonl(os.path.join(corpus, "runs.jsonl"), RUNS_HEADER,
                   [_run("2026-10-28T01:00:00Z", 1)])
        elif verb == "push":
            if self.calls.count("push") <= self.refuse:
                raise RB.Refusal("git push failed (output withheld)")
        elif verb == "ls-remote":
            return "f" * 40 + "\trefs/heads/main\n"
        elif verb == "rev-parse":
            return "f" * 40 + "\n"
        if verb == self.hold_at:
            self._hold()
        return ""


class BankHoldTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="hp-bank-hold-")
        self.addCleanup(shutil.rmtree, self.td, True)
        self.corpus = os.path.join(self.td, "rig", "de_dust")
        _jsonl(os.path.join(self.corpus, "wire.jsonl"), ENTRY_HEADER,
               [{"id": "a", "target": "wire", "kind": "payload", "data": "a"},
                {"id": "b", "target": "wire", "kind": "payload", "data": "b"}])
        _jsonl(os.path.join(self.corpus, "runs.jsonl"), RUNS_HEADER,
               [_run("2026-10-28T01:00:00Z", 1),
                _run("2026-10-28T02:00:00Z", 2)])
        self.pat = os.path.join(self.td, "pat")
        with open(self.pat, "w") as fh:
            fh.write("token\n")

    def _bank(self, git):
        out = io.StringIO()
        with mock.patch.object(RB, "_git", git), \
                mock.patch.object(RB, "tree_head", lambda d: None), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            rc = RB.bank("test rig", self.corpus, self.pat)
        return rc, out.getvalue()

    def test_a_hold_at_the_clone_merges_and_pushes_nothing(self):
        git = _Git(hold_at="clone")
        rc, out = self._bank(git)
        self.assertEqual(rc, RB.HOLD_EXIT)
        self.assertEqual(git.calls, ["clone"])
        self.assertIn("muster holds, nothing merged, nothing pushed", out)

    def test_a_hold_that_refuses_the_first_push_stops_the_retry(self):
        # The muster's commit is what moves main under the bank: the
        # first push is refused, and the fetch brings the hold.
        git = _Git(refuse=1, hold_at="fetch")
        rc, out = self._bank(git)
        self.assertEqual(rc, RB.HOLD_EXIT)
        self.assertEqual(git.calls.count("push"), 1)
        self.assertEqual(git.calls[-2:], ["fetch", "reset"])
        self.assertIn("muster holds, nothing merged, nothing pushed", out)

    def test_no_hold_banks_after_a_refused_push(self):
        git = _Git(refuse=1)
        rc, out = self._bank(git)
        self.assertEqual(rc, 0)
        self.assertEqual(git.calls.count("push"), 2)
        self.assertIn("rig_bank: banked as fffffffff", out)


if __name__ == "__main__":
    unittest.main()
