# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""runner/tools/duplication_audit.py: the dormant-code measure.

The method is the standing audit's (2026-11-03): a sliding
window of 8 normalized non-blank, non-comment lines over the
Python files for near-duplicates, exact copies by file hash,
and a scan for Python files nothing references. These tests
pin the method on synthetic trees where the answer is known
by construction:

- a block of 8 lines shared by 2 files counts on both sides,
  and a block repeated inside 1 file counts there;
- a repetition shorter than the window does not count;
- normalization is real: blocks differing only in
  indentation, blank lines, and comment lines are the same
  block;
- exact copies charge every copy past the first, and only
  those;
- a module named by another file is referenced, a module
  named nowhere is reported, and a test file is reached by
  discovery rather than by name;
- the whole-tree measure carries the keys the audit record
  and the statistics facts are written from, and the
  non-latent figure is 100 minus the near-duplicate share.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.tools import duplication_audit as DA  # noqa: E402

BLOCK = ["value_%d = compute(%d)" % (i, i) for i in range(8)]


def _write(root, rel, lines):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


class NearDuplicateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_shared_block_counts_on_both_sides(self):
        _write(self.root, "a.py", ["alpha = 1"] + BLOCK + ["omega = 2"])
        _write(self.root, "b.py", ["beta = 1"] + BLOCK + ["zeta = 2"])
        per_file = DA.near_duplicate_lines(self.root, ["a.py", "b.py"])
        self.assertEqual(8, per_file["a.py"][2])
        self.assertEqual(8, per_file["b.py"][2])

    def test_block_repeated_inside_one_file_counts(self):
        _write(self.root, "a.py", BLOCK + ["middle = 0"] + BLOCK)
        per_file = DA.near_duplicate_lines(self.root, ["a.py"])
        self.assertEqual(16, per_file["a.py"][2])

    def test_seven_line_repetition_does_not_count(self):
        _write(self.root, "a.py", BLOCK[:7] + ["unique_a = 1"])
        _write(self.root, "b.py", BLOCK[:7] + ["unique_b = 1"])
        per_file = DA.near_duplicate_lines(self.root, ["a.py", "b.py"])
        self.assertEqual(0, per_file["a.py"][2])
        self.assertEqual(0, per_file["b.py"][2])

    def test_normalization_ignores_indent_blanks_and_comments(self):
        dressed = []
        for line in BLOCK:
            dressed.append("    " + line)
            dressed.append("")
            dressed.append("# a comment between the lines")
        _write(self.root, "a.py", BLOCK)
        _write(self.root, "b.py", dressed)
        per_file = DA.near_duplicate_lines(self.root, ["a.py", "b.py"])
        self.assertEqual(8, per_file["a.py"][2])
        self.assertEqual(8, per_file["b.py"][2])

    def test_unique_code_counts_nothing(self):
        _write(self.root, "a.py",
               ["line_%d = %d" % (i, i) for i in range(40)])
        per_file = DA.near_duplicate_lines(self.root, ["a.py"])
        self.assertEqual(0, per_file["a.py"][2])


class ExactCopyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_copies_past_the_first_are_charged(self):
        body = ["line %d" % i for i in range(10)]
        _write(self.root, "x.txt", body)
        _write(self.root, "y.txt", body)
        _write(self.root, "z.txt", body)
        _write(self.root, "other.txt", ["different"])
        total, groups = DA.exact_copies(
            self.root, DA.tracked_files(self.root))
        self.assertEqual(20, total)
        self.assertEqual(1, len(groups))

    def test_distinct_files_charge_nothing(self):
        _write(self.root, "x.txt", ["one"])
        _write(self.root, "y.txt", ["two"])
        total, groups = DA.exact_copies(
            self.root, DA.tracked_files(self.root))
        self.assertEqual(0, total)
        self.assertEqual([], groups)


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_named_module_is_referenced_lonely_one_is_not(self):
        _write(self.root, os.path.join("pkg", "named_mod.py"),
               ["X = 1"])
        _write(self.root, os.path.join("pkg", "lonely_mod.py"),
               ["Y = 2"])
        _write(self.root, "user.py",
               ["from pkg import named_mod", "print(named_mod.X)"])
        _write(self.root, "notes.txt",
               ["the entry point is user.py, run by hand"])
        files = DA.tracked_files(self.root)
        python_files = [f for f in files if f.endswith(".py")]
        unreferenced = DA.unreferenced_python(
            self.root, files, set(python_files))
        self.assertEqual(
            [os.path.join("pkg", "lonely_mod.py")], unreferenced)

    def test_test_files_are_reached_by_discovery(self):
        _write(self.root,
               os.path.join("runner", "tests", "test_lonely.py"),
               ["import unittest"])
        _write(self.root, "main.py", ["print('hi')"])
        files = DA.tracked_files(self.root)
        python_files = [f for f in files if f.endswith(".py")]
        unreferenced = DA.unreferenced_python(
            self.root, files, set(python_files))
        self.assertNotIn(
            os.path.join("runner", "tests", "test_lonely.py"),
            unreferenced)


class GeneratedMarkerTests(unittest.TestCase):
    def test_generated_marker_is_named(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "made.py",
                   ["# generated by a tool", "X = 1"])
            _write(root, "hand.py", ["# written by hand", "Y = 2"])
            marked = DA.generated_marked(root, DA.tracked_files(root))
            self.assertEqual(["made.py"], marked)


class WholeMeasureTests(unittest.TestCase):
    def test_measure_shape_and_non_latent_derivation(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "first.py",
                   ["alpha = 1"] + BLOCK + ["omega = 2"])
            _write(root, "second.py",
                   ["beta = 1"] + BLOCK + ["zeta = 2"])
            _write(root, "notes.txt",
                   ["first and second share a block"])
            result = DA.audit(root)
            for key in ("tree_lines", "python_files", "python_lines",
                        "near_duplicate_lines",
                        "near_duplicate_percent_tree",
                        "near_duplicate_percent_python",
                        "near_duplicate_test_lines",
                        "near_duplicate_production_lines",
                        "non_latent_percent", "exact_copy_lines",
                        "exact_copy_percent_tree",
                        "unreferenced_python", "generated_marked",
                        "top_files"):
                self.assertIn(key, result)
            self.assertEqual(16, result["near_duplicate_lines"])
            self.assertEqual(
                round(100.0 - result["near_duplicate_percent_tree"], 2),
                result["non_latent_percent"])
            self.assertEqual([], result["unreferenced_python"])


if __name__ == "__main__":
    unittest.main()
