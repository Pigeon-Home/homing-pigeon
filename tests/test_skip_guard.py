# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
""".github/tools/skip_guard.py: a forbidden skip fails, everything else passes.

The guard exists because a skipped proof looks exactly like a
passed one from the outside. These tests pin the parsing of
unittest's skip line and the one rule: only the named reasons
fail the build.
"""
import importlib.util
import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _load():
    path = os.path.join(os.path.dirname(__file__), "..", ".github", "tools",
                        "skip_guard.py")
    spec = importlib.util.spec_from_file_location("skip_guard", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SG = _load()

LOG = """\
test_a (tests.t.T.test_a) ... ok
test_b (tests.t.T.test_b) ... skipped 'bwrap not available on this machine'
test_c (tests.t.T.test_c) ... skipped "z3 is not installed"
test_d (tests.t.T.test_d) ... skipped 'bwrap not available on this machine'
test_e (tests.t.T.test_e) ... FAIL
test_f (tests.t.T.test_f) ... skipped 'runs in the .github/docker/minimal-userland image'
"""


class ParseTests(unittest.TestCase):
    def test_counts_each_reason(self):
        reasons = SG.skips_in(io.StringIO(LOG))
        self.assertEqual(reasons["bwrap not available on this machine"], 2)
        self.assertEqual(reasons["z3 is not installed"], 1)
        self.assertEqual(
            reasons["runs in the .github/docker/minimal-userland image"], 1)
        self.assertEqual(sum(reasons.values()), 4)

    def test_ok_and_fail_lines_are_not_skips(self):
        reasons = SG.skips_in(io.StringIO("x ... ok\ny ... FAIL\n"))
        self.assertEqual(reasons, {})

    def test_crlf_logs_parse(self):
        reasons = SG.skips_in(io.StringIO(
            "t (m.T.t) ... skipped 'bwrap not available'\r\n"))
        self.assertEqual(reasons["bwrap not available"], 1)


class RuleTests(unittest.TestCase):
    def _run(self, text, *forbid):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(text)
            path = fh.name
        try:
            out = io.StringIO()
            argv = [path]
            for f in forbid:
                argv += ["--forbid", f]
            with redirect_stdout(out):
                rc = SG.main(argv)
            return rc, out.getvalue()
        finally:
            os.unlink(path)

    def _run_args(self, text, extra):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(text)
            path = fh.name
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = SG.main([path] + list(extra))
            return rc, out.getvalue()
        finally:
            os.unlink(path)

    def test_no_forbidden_reasons_passes_and_lists_skips(self):
        rc, out = self._run(LOG)
        self.assertEqual(rc, 0)
        self.assertIn("skip reasons seen:", out)
        self.assertIn("bwrap not available", out)
        self.assertNotIn("FORBIDDEN", out)

    def test_forbidden_substring_fails(self):
        rc, out = self._run(LOG, "bwrap not available")
        self.assertEqual(rc, 1)
        self.assertIn("FORBIDDEN", out)
        self.assertIn("   2  bwrap not available on this machine", out)

    def test_only_named_reasons_fail(self):
        # z3 is a deliberate skip (tests/test_runbook_constraints.py);
        # forbidding bwrap must not drag it in.
        rc, out = self._run(LOG, "bwrap not available")
        self.assertEqual(rc, 1)
        forbidden_section = out.split("FORBIDDEN")[1]
        self.assertIn("bwrap", forbidden_section)
        self.assertNotIn("z3", forbidden_section)
        # And once bwrap is present, the same forbid list passes.
        rc2, _ = self._run(LOG.replace(
            "skipped 'bwrap not available on this machine'", "ok"),
            "bwrap not available")
        self.assertEqual(rc2, 0)

    def test_forbid_is_repeatable(self):
        rc, out = self._run(LOG, "nothing-here", "z3 is not")
        self.assertEqual(rc, 1)
        self.assertIn("z3 is not installed", out.split("FORBIDDEN")[1])

    def test_no_skips_fails_on_any_skip(self):
        rc, out = self._run_args(LOG, ["--no-skips"])
        self.assertEqual(rc, 1)
        self.assertIn("SKIPS are not allowed", out)
        rc2, _ = self._run_args("t (m.T.t) ... ok\nRan 1 test in 0.0s\nOK\n",
                                ["--no-skips"])
        self.assertEqual(rc2, 0)

    def test_require_ok_needs_ran_and_verdict(self):
        good = "t (m.T.t) ... ok\n\nRan 7 tests in 0.3s\n\nOK\n"
        self.assertEqual(self._run_args(good, ["--require-ok"])[0], 0)
        # a FAILED verdict, an empty discovery, and a missing verdict
        bad1 = good.replace("OK", "FAILED (failures=1)")
        bad2 = good.replace("Ran 7 tests", "Ran 0 tests")
        bad3 = "t ... ok\n"
        for text in (bad1, bad2, bad3):
            rc, out = self._run_args(text, ["--require-ok"])
            self.assertEqual(rc, 1, text)
            self.assertIn("REQUIRE-OK", out)
        # "OK (skipped=2)" is not a bare OK: with --no-skips it fails
        # twice over, which is the point.
        rc, _ = self._run_args(
            "t ... skipped 'x'\nRan 1 test in 0.0s\nOK (skipped=1)\n",
            ["--require-ok", "--no-skips"])
        self.assertEqual(rc, 1)

    def test_annotate_emits_failures_and_verdicts(self):
        log = ("test_x (tests.m.T.test_x) ... FAIL\n"
               "FAIL: test_x (tests.m.T.test_x)\n"
               "Traceback (most recent call last):\n"
               "AssertionError: 1 != 0 : scen-2\n"
               "FAIL: test_bad (test_gamma.T.test_bad)\n"   # fixture noise
               "Ran 1 test in 0.0s\nFAILED (failures=1)\n")
        rc, out = self._run_args(log, ["--require-ok", "--annotate"])
        self.assertEqual(rc, 1)
        self.assertIn("::error::FAIL: test_x (tests.m.T.test_x)", out)
        self.assertIn("::error::AssertionError: 1 != 0 : scen-2", out)
        self.assertNotIn("::error::FAIL: test_bad", out)
        self.assertIn("::error::REQUIRE-OK", out)
        # a clean log annotates nothing
        rc, out = self._run_args("t ... ok\nRan 1 test in 0.0s\nOK\n",
                                 ["--require-ok", "--annotate"])
        self.assertEqual(rc, 0)
        self.assertNotIn("::error::", out)

    # Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
    def test_annotations_spend_their_ten_slots_on_test_ids_first(self):
        # Twelve exception-looking lines come first in log order (a
        # fixture dumping its deliberately red shard), then the one
        # real failure. The real FAIL: line must be annotated; the
        # noise fills whatever of the ten slots remain.
        noise = "".join("AssertionError: fixture noise %d\n" % i
                        for i in range(12))
        log = (noise +
               "FAIL: test_x (tests.m.T.test_x)\n"
               "AssertionError: 1 != 0 : the real one\n"
               "Ran 9 tests in 0.0s\nFAILED (failures=1)\n")
        got = SG.failures_in(log.splitlines())
        self.assertEqual(len(got), 10)
        self.assertEqual(got[0], "FAIL: test_x (tests.m.T.test_x)")
        self.assertIn("AssertionError: fixture noise 0", got)
        rc, out = self._run_args(log, ["--annotate"])
        self.assertIn("::error::FAIL: test_x (tests.m.T.test_x)", out)

    def test_a_green_verdict_annotates_no_exception_lines(self):
        # The same fixture noise in a log whose suite passed: a
        # passing run page must not show red annotations.
        log = ("AssertionError: False is not true\n"
               "BrokenPipeError: [Errno 32] Broken pipe\n"
               "Ran 9 tests in 0.0s\nOK\n")
        self.assertEqual(SG.failures_in(log.splitlines()), [])
        rc, out = self._run_args(log, ["--annotate"])
        self.assertEqual(rc, 0)
        self.assertNotIn("::error::", out)
        # The CI suite's own verdict carries skips: still green.
        log = ("AssertionError: False is not true\n"
               "Ran 4549 tests in 300.0s\nOK (skipped=22)\n")
        self.assertEqual(SG.failures_in(log.splitlines()), [])
        # A bare OK printed by a fixture (the passing fake shard's
        # tail, from the test that proves the shard runner) before
        # the real summary is not the verdict. The first CI run of
        # this guard read that OK and annotated nothing on a red
        # suite.
        log = ("shard 0: OK\nRan 1 test in 0.000s\n\nOK\n"
               "test_y ... FAIL\nFAIL: test_y (tests.m.T.test_y)\n"
               "AssertionError: the real one\n"
               "Ran 4549 tests in 300.0s\n\nFAILED (failures=1)\n")
        self.assertEqual(SG.verdict_of(log.splitlines()),
                         "FAILED (failures=1)")
        self.assertEqual(SG.failures_in(log.splitlines())[0],
                         "FAIL: test_y (tests.m.T.test_y)")
        # ...and --require-ok is not fooled by that OK either.
        rc, out = self._run_args(log, ["--require-ok"])
        self.assertEqual(rc, 1)
        self.assertIn("REQUIRE-OK", out)
        self.assertEqual(SG.verdict_of(["t ... ok"]), "")
        # A FAILED verdict annotates; so does a log with no verdict
        # at all (a suite that died before printing one).
        for tail in ("Ran 1 test in 0.0s\nFAILED (errors=1)\n", ""):
            log = "AssertionError: boom\n" + tail
            self.assertEqual(SG.failures_in(log.splitlines()),
                             ["AssertionError: boom"])

    def test_empty_log_passes(self):
        rc, out = self._run("", "bwrap")
        self.assertEqual(rc, 0)
        self.assertIn("none", out)


if __name__ == "__main__":
    unittest.main()
