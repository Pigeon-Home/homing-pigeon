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


if __name__ == "__main__":
    unittest.main()
