# Tests for the switch-proof roster and the tool that runs it
# (runner/tests/switch_roster.py, runner/tools/switch_proofs.py).
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
"""Two guards. The roster itself: every control's proof must load, so
a renamed or deleted test fails here on main before the workflow
notices. The tool: each verdict on a synthetic roster whose fakes
pass, fail, skip or do not exist.
"""

import importlib.util
import io
import os
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "switch_proofs", os.path.join(ROOT, "runner", "tools", "switch_proofs.py"))
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)

from runner.tests import switch_roster  # noqa: E402


def _fakes():
    # Built inside a function so discovery never collects them as
    # tests of this module; the tool reaches them by dotted name.
    class Pass(unittest.TestCase):
        def test_one(self):
            self.assertTrue(True)

        def test_two(self):
            self.assertTrue(True)

    class Fail(unittest.TestCase):
        def test_breaks(self):
            self.fail("the promise broke")

    class Skip(unittest.TestCase):
        @unittest.skip("not on this leg")
        def test_elsewhere(self):
            pass

    class Mixed(unittest.TestCase):
        def test_runs(self):
            pass

        @unittest.skip("unix only")
        def test_skips(self):
            pass

    return types.SimpleNamespace(Pass=Pass, Fail=Fail, Skip=Skip, Mixed=Mixed)


fakes = _fakes()
_HERE = "runner.tests.test_switch_proofs.fakes."


class RosterTest(unittest.TestCase):

    def test_ids_unique_and_needs_known(self):
        ids = [e["id"] for e in switch_roster.ROSTER]
        self.assertEqual(len(ids), len(set(ids)), "duplicate roster ids")
        for entry in switch_roster.ROSTER:
            self.assertTrue(entry.get("promise"), entry["id"] + ": no promise")
            self.assertLessEqual(set(entry.get("needs", ())),
                                 set(switch_roster.KNOWN_NEEDS),
                                 entry["id"] + ": unknown need")

    def test_every_listed_proof_loads(self):
        loader = unittest.defaultTestLoader
        for entry in switch_roster.ROSTER:
            for test_id in entry.get("tests", ()):
                with self.subTest(control=entry["id"], test=test_id):
                    suite = loader.loadTestsFromName(test_id)
                    cases = list(sp._flatten(suite))
                    self.assertTrue(cases, "%s lists %s, which loads nothing"
                                    % (entry["id"], test_id))
                    self.assertFalse(
                        [c for c in cases if type(c).__name__ == "_FailedTest"],
                        "%s lists %s, which does not import"
                        % (entry["id"], test_id))

    def test_the_races_and_walls_are_on_the_roster(self):
        ids = {e["id"] for e in switch_roster.ROSTER}
        for wanted in ("M6.wall.network", "M6.wall.home", "M8.drop",
                       "R1.two_jobs", "R2.audit_rollover", "R3.seen_set",
                       "R4.config_write", "ORACLE.no_widening"):
            self.assertIn(wanted, ids)


class VerdictTest(unittest.TestCase):
    ROSTER = [
        {"id": "ok", "promise": "p", "tests": [_HERE + "Pass"], "needs": []},
        {"id": "bad", "promise": "p", "tests": [_HERE + "Fail"], "needs": []},
        {"id": "gone", "promise": "p", "tests": [_HERE + "Nope"], "needs": []},
        {"id": "skipped", "promise": "p", "tests": [_HERE + "Skip"], "needs": []},
        {"id": "partly", "promise": "p", "tests": [_HERE + "Mixed"], "needs": []},
        {"id": "empty", "promise": "p", "tests": [], "needs": []},
        {"id": "elsewhere", "promise": "p", "tests": [_HERE + "Pass"],
         "needs": ["root"]},
    ]

    def _run(self, have):
        verdicts, _ = sp.run_roster(self.ROSTER, set(have), stream=io.StringIO())
        return {e["id"]: (v, d) for e, v, d in verdicts}

    def test_each_verdict(self):
        got = self._run(["linux"])
        self.assertEqual(got["ok"][0], "proven")
        self.assertEqual(got["bad"][0], "FAILED")
        self.assertIn("the promise broke", got["bad"][1])
        self.assertEqual(got["gone"][0], "MISSING")
        self.assertEqual(got["skipped"][0], "SKIPPED")
        # One test skipping where another ran is still a proof.
        self.assertEqual(got["partly"][0], "proven")
        self.assertIn("1 skipped", got["partly"][1])
        self.assertEqual(got["empty"][0], "unproven")
        self.assertEqual(got["elsewhere"], ("not here", "needs root"))

    def test_the_leg_that_has_root_judges_it(self):
        got = self._run(["linux", "root"])
        self.assertEqual(got["elsewhere"][0], "proven")

    def test_render_and_exit_code(self):
        verdicts, _ = sp.run_roster(self.ROSTER, {"linux"}, stream=io.StringIO())
        text = sp.render(verdicts, {"linux"}, "unit")
        self.assertIn("# Switch proofs: unit", text)
        self.assertIn("| `bad` | FAILED |", text)
        self.assertIn("6 controls judged here: 2 proven, 1 unproven, 1 failed, "
                      "1 missing, 1 skipped; 1 not applicable", text)
        bad = [v for _e, v, _d in verdicts if v in ("FAILED", "MISSING", "SKIPPED")]
        self.assertEqual(len(bad), 3)

    def test_root_flag_is_refused_without_root(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("running as root")
        self.assertEqual(sp.main(["--root", "--root-dir", ROOT, "--list"]), 2)

    def test_unknown_have_is_refused(self):
        self.assertEqual(sp.main(["--have", "windows", "--root-dir", ROOT,
                                  "--list"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
