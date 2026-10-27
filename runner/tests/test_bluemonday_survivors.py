# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""Project blueMonday's survivors tool: the mutants the corpus
cannot tell from the reader (the plan's section 8, step 5)."""

import ast
import json
import os
import random
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tools import bluemonday_corpus as B  # noqa: E402
from runner.tools import bluemonday_survivors as S  # noqa: E402

FIXTURE = '''\
"""A reader."""
import logging

CAP = 4


def read(text, strict=True):
    """Accept a short word."""
    if not isinstance(text, str):
        raise ValueError("not text")
    if len(text) > CAP:
        raise ValueError("too long")
    logging.info("read %s", text)
    return text.upper() + "!"


def unused(a, b):
    return a - b
'''


class SitesTest(unittest.TestCase):
    def test_sites_skip_prose_defaults_and_log_calls(self):
        tree = ast.parse(FIXTURE)
        ops = [(op, node.lineno) for node, op in S.sites(tree)]
        self.assertIn(("compare", 11), ops)          # len(text) > CAP
        self.assertIn(("int+1", 4), ops)             # CAP = 4
        self.assertIn(("raise-pass", 10), ops)
        self.assertIn(("return-none", 14), ops)
        self.assertIn(("add-sub", 18), ops)
        texts = [op for op, _ in ops if op == "str-empty"]
        # The docstrings, the raise texts, the log call's format and
        # the "!" literal: only the literal is a site.
        self.assertEqual(texts, ["str-empty"])
        self.assertNotIn(("bool", 8), ops)           # strict=True default

    def test_reached_lines_narrow_the_sites(self):
        tree = ast.parse(FIXTURE)
        ops = [(op, node.lineno) for node, op in S.sites(tree, {11, 12})]
        self.assertTrue(all(line in (11, 12) for _, line in ops))
        self.assertIn(("compare", 11), ops)
        self.assertIn(("raise-pass", 12), ops)

    def test_mutants_reproduce_by_index_and_are_valid_source(self):
        first = S.mutants(FIXTURE)
        again = S.mutants(FIXTURE)
        self.assertEqual([(i, op, line) for i, op, line, _t in first],
                         [(i, op, line) for i, op, line, _t in again])
        self.assertGreater(len(first), 6)
        for _i, _op, _line, text in first:
            ast.parse(text)
            self.assertNotEqual(ast.dump(ast.parse(text)),
                                ast.dump(ast.parse(FIXTURE)))
        sampled = S.mutants(FIXTURE, limit=3, rng=random.Random(1))
        self.assertEqual(len(sampled), 3)
        self.assertEqual([m[0] for m in sampled], sorted(m[0] for m in sampled))


class KillTest(unittest.TestCase):
    """A mutant the corpus tells apart is killed; one it cannot
    survives; a note tells two accepting readers apart."""

    def setUp(self):
        self.stub = types.ModuleType("runner.tests.bm_stub")
        self.stub.__file__ = os.path.join(ROOT, "runner", "tests",
                                          "bm_stub.py")
        self.stub.__package__ = "runner.tests"
        exec(compile(FIXTURE, self.stub.__file__, "exec"), self.stub.__dict__)
        self.addCleanup(lambda: delattr(B, "STUB") if hasattr(B, "STUB")
                        else None)
        B.STUB = self.stub

        def check(entry):
            got, exc = B._call(B.STUB.read, entry["data"])
            if exc is not None:
                B._expect_refusal(exc, ValueError, "read")
                return "refused"
            B.note("out", got)
            return "accepted"
        self.targets = {"stub": {"files": [self.stub.__file__],
                                 "check": check, "seeds": lambda: []}}
        self.corpora = {"stub": [B.make_entry("payload", d, "seed:x", "seed")
                                 for d in ("ab", "abcd", "abcde", 7)]}

    def _kill(self, text):
        with mock.patch.dict(B.TARGETS, self.targets):
            baseline = B._with_rig(lambda: S.outcomes(["stub"], self.corpora))
            return S.kill("STUB", text, ["stub"], self.corpora, baseline)

    def test_a_boundary_mutant_is_killed_and_an_unused_one_survives(self):
        made = {(op, line): text for _i, op, line, text in S.mutants(FIXTURE)}
        self.assertEqual(self._kill(made[("compare", 11)]), "killed")
        self.assertEqual(self._kill(made[("int+1", 4)]), "killed")
        self.assertEqual(self._kill(made[("raise-pass", 12)]), "killed")
        self.assertEqual(self._kill(made[("add-sub", 18)]), "survived")
        # The literal "!" is only seen through the note.
        self.assertEqual(self._kill(made[("str-empty", 14)]), "killed")
        self.assertEqual(self._kill("this is not python"), "broken")
        self.assertIs(getattr(B, "STUB"), self.stub)   # put back after

    def test_timeout_is_a_verdict_where_the_alarm_exists(self):
        if not hasattr(S.signal, "SIGALRM"):
            self.skipTest("no SIGALRM on this platform")
        looping = FIXTURE.replace("    return text.upper() + \"!\"",
                                  "    while True:\n        pass")
        with mock.patch.dict(B.TARGETS, self.targets):
            baseline = B._with_rig(lambda: S.outcomes(["stub"], self.corpora))
            verdict = S.kill("STUB", looping, ["stub"], self.corpora,
                             baseline, timeout=1)
        self.assertEqual(verdict, "timeout")


class ReportTest(unittest.TestCase):
    def test_the_committed_report_is_stamped_and_names_the_scope(self):
        with open(S.REPORT, encoding="utf-8") as fh:
            raw = fh.read()
        self.assertTrue(raw.isascii())
        r = json.loads(raw)
        self.assertEqual(r["Agent-Stamp"], B.STAMP)
        self.assertEqual(r["kind"], "survivors")
        self.assertEqual(r["through_agent"], sorted(S.THROUGH_AGENT))
        self.assertTrue(set(r["modules"]) <= set(S.MODULES))
        for name, m in r["modules"].items():
            self.assertEqual(m["mutants"], m["killed"] + m["survived"]
                             + m["timeout"] + m["broken"])
            self.assertEqual(len(m["survivors"]), m["survived"] + m["timeout"])
            self.assertTrue(all(t in B.TARGETS for t in m["targets"]))
            for s in m["survivors"]:
                self.assertEqual(set(s), {"index", "op", "line", "verdict",
                                          "text"})

    def test_targets_for_follows_the_files_and_skips_the_agent_path(self):
        self.assertIn("wire", S.targets_for("verify"))
        self.assertIn("inbox", S.targets_for("transports"))
        self.assertNotIn("local", S.targets_for("transports"))
        self.assertEqual(S.targets_for("no_such_module"), [])

    def test_every_reader_replays_the_same_twice(self):
        corpora = {t: B.load(B.corpus_path(t)) for t in B.TARGETS}
        for name in ("verify", "board", "transports"):
            targets = S.targets_for(name)
            a = B._with_rig(lambda: S.outcomes(targets, corpora))
            b = B._with_rig(lambda: S.outcomes(targets, corpora))
            self.assertEqual(a, b, name)
            self.assertTrue(any(notes for res in a.values()
                                for _o, notes in res), name)


if __name__ == "__main__":
    unittest.main()
