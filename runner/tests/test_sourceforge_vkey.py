# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The SourceForge step's tag ordering (build.yml's embedded vkey).

The sourceforge job in .github/workflows/build.yml embeds a python
heredoc that picks the newest v* tag on the repo with a vkey()
helper, and marks the release's default downloads only when the
release being published is that newest tag. Tags come in 2 schemes:
legacy 3-component MAJOR.MINOR.COUNTER, and the current 4-component
MAJOR.MINOR.TOKENS.COUNTER (runner/ops/version4.py; a legacy tag's
3rd component was the counter, see version4.convert_legacy).

A raw tuple compare of the split tag reads a legacy tag's counter
as the token figure, so v3.15.148 keyed (3, 15, 148) above every
v3.15.17.x and the default-download marking never ran for a current
release. These tests extract the embedded vkey from the workflow
itself and pin the cross-scheme ordering, so the helper the job
actually runs is the helper under test.
"""

import os
import re
import textwrap
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


def _workflow():
    with open(os.path.join(_root(), ".github", "workflows", "build.yml"),
              encoding="utf-8") as fh:
        return fh.read()


def _extract_vkey(workflow_text):
    """The workflow's embedded vkey function, compiled on its own."""
    lines = workflow_text.splitlines()
    starts = [i for i, ln in enumerate(lines)
              if re.match(r"^\s*def vkey\(t\):\s*$", ln)]
    assert len(starts) == 1, "expected exactly 1 vkey def, got %d" % len(starts)
    start = starts[0]
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.strip() and len(ln) - len(ln.lstrip()) <= indent:
            break
        body.append(ln)
    src = textwrap.dedent("\n".join(body)) + "\n"
    namespace = {}
    exec(compile(src, "build.yml:vkey", "exec"), namespace)
    return namespace["vkey"]


class VkeyExtractionTest(unittest.TestCase):
    def test_vkey_found_exactly_once_and_callable(self):
        # Self-check: if the extraction ever matches nothing, the
        # ordering tests below would fail on a missing helper rather
        # than pass vacuously -- and this one says so directly.
        vkey = _extract_vkey(_workflow())
        self.assertTrue(callable(vkey))
        self.assertEqual(vkey("v3.15.17.160"), (3, 15, 17, 160))


class VkeyOrderingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vkey = staticmethod(_extract_vkey(_workflow()))

    def test_current_release_outranks_last_legacy_tag(self):
        # The verified defect: this pair compared the wrong way, so
        # the marking was skipped for every 4-component release.
        self.assertGreater(self.vkey("v3.15.17.160"),
                           self.vkey("v3.15.148"))

    def test_first_four_component_outranks_last_legacy_tag(self):
        self.assertGreater(self.vkey("v3.15.17.149"),
                           self.vkey("v3.15.148"))

    def test_legacy_tags_order_by_counter(self):
        self.assertLess(self.vkey("v3.15.99"), self.vkey("v3.15.148"))
        self.assertGreater(self.vkey("v3.15.148"), self.vkey("v3.15.147"))

    def test_four_component_orders_by_tokens_then_counter(self):
        self.assertLess(self.vkey("v3.15.17.99"),
                        self.vkey("v3.15.17.160"))
        # Odometer rule: the token figure increasing restarts the
        # counter, and the newer figure still outranks the old line.
        self.assertGreater(self.vkey("v3.15.18.1"),
                           self.vkey("v3.15.17.160"))

    def test_minor_line_orders_before_either_scheme(self):
        self.assertLess(self.vkey("v3.14.148"), self.vkey("v3.15.1"))
        self.assertLess(self.vkey("v3.15.17.160"),
                        self.vkey("v3.16.17.1"))

    def test_newest_selection_over_a_mixed_tag_list(self):
        # The workflow's own selection: max over (vkey(name), name).
        tags = ["v3.15.144", "v3.15.148",
                "v3.15.17.149", "v3.15.17.150", "v3.15.17.160"]
        newest = max((self.vkey(n), n) for n in tags)[1]
        self.assertEqual(newest, "v3.15.17.160")

    def test_newest_selection_over_legacy_tags_only(self):
        tags = ["v3.15.99", "v3.15.148", "v3.15.147"]
        newest = max((self.vkey(n), n) for n in tags)[1]
        self.assertEqual(newest, "v3.15.148")

    def test_v_prefix_optional(self):
        self.assertEqual(self.vkey("3.15.148"), self.vkey("v3.15.148"))
        self.assertEqual(self.vkey("3.15.17.160"),
                         self.vkey("v3.15.17.160"))


class VkeyShapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vkey = staticmethod(_extract_vkey(_workflow()))

    def test_keys_are_uniform_4_tuples_of_ints(self):
        for tag in ("v3.15.148", "v3.15.17.160", "v3.14.42",
                    "v3.15.17.149"):
            key = self.vkey(tag)
            self.assertEqual(len(key), 4, tag)
            self.assertTrue(all(isinstance(x, int) for x in key), tag)

    def test_legacy_key_carries_its_counter_in_the_counter_slot(self):
        # convert_legacy's reading: the legacy 3rd component is the
        # counter; the token slot is 0 because the tag predates the
        # measure. This is what makes every 4-component release on
        # the line outrank every legacy tag on it.
        self.assertEqual(self.vkey("v3.15.148"), (3, 15, 0, 148))

    def test_non_release_shapes_raise_value_error(self):
        # The workflow skips a tag whose vkey raises ValueError, so
        # anything that is not a 3- or 4-component numeric release
        # tag must raise, never key somewhere arbitrary.
        for tag in ("v3.15", "v3.15.17.160.1", "v3.x.1", "v3.15.x"):
            with self.assertRaises(ValueError, msg=tag):
                self.vkey(tag)


if __name__ == "__main__":
    unittest.main()
