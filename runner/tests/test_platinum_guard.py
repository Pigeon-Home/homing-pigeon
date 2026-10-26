"""Project Platinum, cycle 2: the guard family.

Target from the cycle-1 refreshed table
(`docs/reports/v3.13.21/coverage-gaps.md`):

  except  guard/extreview.py:_scan_python (3) -- a source
          that does not parse is a "syntax" finding, never an
          exception out of the review: a plain SyntaxError on
          every supported Python, and the NUL-byte / nesting
          arm (ValueError, RecursionError, MemoryError) the
          comment keeps for the older interpreters. Whichever
          arm fires, the finding is the contract.

Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90
"""
import unittest

from hypothesis import given, settings, strategies as st

from runner.guard import extreview


def _scan(text, rel="ext.py"):
    observed, findings, signals = {}, [], {}
    extreview._scan_python(rel, text, observed, findings, signals)
    return observed, findings, signals


class ScanPythonProperties(unittest.TestCase):
    @settings(deadline=None)
    @given(text=st.sampled_from([
        "def broken(:\n",
        "x = (1 +\n",
        "return outside a function\n",
        "class\n",
        "if True print('no colon')\n",
        "x = " + "9" * 5000 + "\n",
        "x = " + "[" * 2000 + "]" * 2000 + "\n",
    ]))
    def test_a_syntax_error_is_a_finding_not_an_exception(self, text):
        _, findings, _ = _scan(text)
        syntax = [f for f in findings if f["code"] == "syntax"]
        self.assertEqual(len(syntax), 1)
        self.assertEqual(syntax[0]["severity"], "high")
        self.assertIn("does not compile", syntax[0]["detail"])

    def test_a_nul_byte_is_a_finding_not_an_exception(self):
        _, findings, _ = _scan("x = 1\x00y = 2\n")
        syntax = [f for f in findings if f["code"] == "syntax"]
        self.assertEqual(len(syntax), 1)
        self.assertEqual(syntax[0]["severity"], "high")

    def test_absurd_nesting_never_escapes(self):
        text = "x = " + "(" * 5000 + "1" + ")" * 5000 + "\n"
        _, findings, _ = _scan(text)
        syntax = [f for f in findings if f["code"] == "syntax"]
        self.assertLessEqual(len(syntax), 1)

    @settings(deadline=None)
    @given(text=st.sampled_from([
        "import socket\n",
        "x = 1\n",
        "def f():\n    return 42\n",
    ]))
    def test_a_parseable_source_has_no_syntax_finding(self, text):
        _, findings, _ = _scan(text)
        self.assertEqual(
            [f for f in findings if f["code"] == "syntax"], [])


class ApplyFallbackTest(unittest.TestCase):
    """Cycle 3 target, logic class: `extreview.apply` (2) --
    a review that itself fails must not abort the agent: the
    extension is reported with one high "unreviewed" finding
    naming the failure, and apply returns its triple. The
    review seam is the module's own `_cached_review`.
    """

    def test_a_review_that_raises_reports_unreviewed(self):
        import tempfile
        from unittest import mock
        folder = tempfile.mkdtemp(prefix="hp-plat-apply-")
        registry = {"broken-ext": {"dir": folder, "version": "1",
                                   "kind": "sense"}}
        with mock.patch.object(
                extreview, "_cached_review",
                side_effect=RuntimeError("the review blew up")):
            out, problems, report = extreview.apply(
                {}, "/base", registry, kind="sense")
        entry = report["extensions"]["broken-ext"]
        self.assertEqual(len(entry["findings"]), 1)
        self.assertEqual(entry["findings"][0]["code"], "unreviewed")
        self.assertEqual(entry["findings"][0]["severity"], "high")
        self.assertIn("the review blew up",
                      entry["findings"][0]["detail"])


class UnderAndReviewEntryTest(unittest.TestCase):
    """Cycle 3 targets: `extreview._under` (except) and
    `extreview._review_entry` (guard). A path realpath cannot
    read (an embedded NUL) is simply not under anything; an
    entry that points outside its folder, or runs shipped code
    it does not ship, is a finding -- and no mutated entry
    shape raises.
    """

    def test_a_path_realpath_refuses_is_not_under(self):
        self.assertFalse(extreview._under("a\x00b", "/tmp"))
        self.assertTrue(extreview._under("/tmp/x", "/tmp"))
        self.assertFalse(extreview._under("/etc/x", "/tmp"))

    @settings(deadline=None)
    @given(entry=st.lists(st.one_of(
        st.text(max_size=16),
        st.sampled_from(["{python}", "{extension_dir}/run.py",
                         "{extension_dir}/../escape.py",
                         "-m", "runner.guard.extreview",
                         "..", "../up.py", ""]),
        st.integers(), st.none()), max_size=4))
    def test_mutated_entries_find_or_pass_without_raising(
            self, entry):
        findings = []
        extreview._review_entry({"entry": entry}, "/ext/folder",
                                findings, shipped=True)
        for finding in findings:
            self.assertIn(finding["code"],
                          {"entry.outside", "entry.program",
                           "entry.path"})

    def test_an_entry_pointing_outside_is_a_high_finding(self):
        findings = []
        extreview._review_entry(
            {"entry": ["{extension_dir}/../escape.py"]},
            "/ext/folder", findings, shipped=True)
        self.assertEqual([f["code"] for f in findings],
                         ["entry.outside"])
        self.assertEqual(findings[0]["severity"], "high")


class FileNameSurrogateTest(unittest.TestCase):
    """Cycle 3 target, except class:
    `guard/filenames.py:validate_file_name` (2) -- a name with
    a lone surrogate cannot be encoded as UTF-8, and the
    refusal is the module's BadFileName saying so.
    """

    def test_a_lone_surrogate_is_not_valid_text(self):
        from runner.guard import filenames
        with self.assertRaises(filenames.BadFileName) as cm:
            filenames.validate_file_name("report-\ud800.txt")
        self.assertIn("not valid text", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
