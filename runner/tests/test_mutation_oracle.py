# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The mutation walk's oracle (Q170): derivation, pin, helper.

runner/tools/mutation_oracle.py derives pyproject.toml's
`[tool.mutmut]` test selection -- the test modules whose import
chains reach the mutated file, runner/guard/security.py -- from
the tree. The pins:

- the derivation's rules, on fixture trees: a direct import in
  either style (runner-prefixed, bare-package), a lazy
  function-level import through an intermediate module, a
  helper-module chain inside the tests package, and a name
  carried only as data (a file list, a string) making no edge;
- the recorded selection IS the derivation, recomputed from
  this tree, so the list cannot rot silently: a module that
  starts or stops loading the mutated file turns this test red
  until the list is regenerated with the tool;
- the filed Q170 examples by name: test_core is not in the
  selection (it loads runner/ops/core.py only, which names the
  mutated file as data), and test_agent_state_tree_wide is (its
  approvalguard import loads the mutated file lazily);
- the shared mutant-copy helper (runner/tests/mutant_copy.py):
  outside a mutant copy it is a no-op, inside one (any
  MUTANT_UNDER_TEST value) it skips with the reason registered
  in test_skip_registry.py;
- the seeded workflow runs the tool's --check before the walk.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from runner.tests import mutant_copy  # noqa: E402
from runner.tests.mutant_copy import skip_in_mutant_copy  # noqa: E402
from runner.tools import mutation_oracle as MO  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))

REASON = ("inside a mutant copy: this test measures the "
          "tracked tree, and mutmut's copy is not it")

BOOKENDS = "#$%^&*()_+-=[]{}|;':\",.<>/?`~ \t\r\n"


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _fixture_tree(root):
    """A miniature runner/ tree exercising every derivation rule."""
    _write(root, "runner/__init__.py", "")
    _write(root, "runner/guard/__init__.py", "")
    _write(root, "runner/guard/security.py", "VALUE = 1\n")
    _write(root, "runner/guard/textutil.py", "VALUE = 2\n")
    _write(root, "runner/ops/__init__.py", "")
    # core.py names the mutated file as data in its file list,
    # exactly the test_core shape: no import, no edge.
    _write(root, "runner/ops/core.py",
           "FILES = ['runner/guard/security.py']\n")
    _write(root, "runner/tools/__init__.py", "")
    # A tool that loads the mutated file lazily, from a
    # function: the approvalguard shape.
    _write(root, "runner/tools/lazytool.py",
           "def load():\n"
           "    from runner.guard import security\n"
           "    return security\n")
    _write(root, "runner/tests/__init__.py", "")
    _write(root, "runner/tests/helper.py",
           "from runner.guard import security  # noqa\n")
    _write(root, "runner/tests/test_direct.py",
           "from runner.guard import security  # noqa\n")
    _write(root, "runner/tests/test_bare.py",
           "from guard import security  # noqa\n")
    _write(root, "runner/tests/test_deep.py",
           "from runner.guard.security import VALUE  # noqa\n")
    _write(root, "runner/tests/test_multi.py",
           "from runner.guard import security, textutil  # noqa\n")
    _write(root, "runner/tests/test_lazy.py",
           "from runner.tools import lazytool  # noqa\n")
    _write(root, "runner/tests/test_helper_chain.py",
           "from runner.tests.helper import security  # noqa\n")
    _write(root, "runner/tests/test_data_only.py",
           "from runner.ops import core  # noqa\n")
    _write(root, "runner/tests/test_unrelated.py",
           "import os  # noqa\n")
    # Import-shaped text inside a string is data, not a load.
    _write(root, "runner/tests/test_string_only.py",
           "SRC = 'from runner.guard import security\\n'\n")


class DerivationFixtureTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        _fixture_tree(self._tmp.name)
        self.derived = MO.derive(self._tmp.name)

    def test_direct_and_bare_styles_are_selected(self):
        for name in ("test_direct", "test_bare", "test_deep",
                     "test_multi"):
            self.assertIn("runner/tests/%s.py" % name, self.derived)

    def test_lazy_and_helper_chains_are_selected(self):
        self.assertIn("runner/tests/test_lazy.py", self.derived)
        self.assertIn("runner/tests/test_helper_chain.py",
                      self.derived)

    def test_data_and_strings_make_no_edge(self):
        self.assertNotIn("runner/tests/test_data_only.py",
                         self.derived)
        self.assertNotIn("runner/tests/test_string_only.py",
                         self.derived)
        self.assertNotIn("runner/tests/test_unrelated.py",
                         self.derived)

    def test_the_selection_is_exactly_the_loaders(self):
        self.assertEqual(
            ["runner/tests/test_bare.py",
             "runner/tests/test_deep.py",
             "runner/tests/test_direct.py",
             "runner/tests/test_helper_chain.py",
             "runner/tests/test_lazy.py",
             "runner/tests/test_multi.py"], self.derived)

    def test_bookended_imports_still_load(self):
        # The bookend standard: an import statement wrapped in
        # symbol noise in the file's comments and strings is
        # still a statement; the derivation reads statements,
        # so the noise changes nothing.
        _write(self._tmp.name, "runner/tests/test_noisy.py",
               BOOKENDS + "\nfrom runner.guard import security\n"
               + BOOKENDS + "\n")
        self.assertIn("runner/tests/test_noisy.py",
                      MO.derive(self._tmp.name))

    def test_an_unparseable_file_loads_nothing(self):
        _write(self._tmp.name, "runner/tests/test_broken.py",
               "def broken(:\n    from runner.guard import security\n")
        self.assertNotIn("runner/tests/test_broken.py",
                         MO.derive(self._tmp.name))


class RecordedSelectionFixtureTest(unittest.TestCase):
    def test_comments_do_not_leak_into_the_recorded_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "pyproject.toml",
                   "[tool.mutmut]\n"
                   "# the \"runner/tests/test_fake.py\" shape\n"
                   "pytest_add_cli_args_test_selection = [\n"
                   "    \"runner/tests/test_a.py\",\n"
                   "    \"runner/tests/test_b.py\",  # a note\n"
                   "]\n")
            self.assertEqual(
                ["runner/tests/test_a.py",
                 "runner/tests/test_b.py"],
                MO.recorded_selection(tmp))

    def test_check_names_both_directions(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture_tree(tmp)
            _write(tmp, "pyproject.toml",
                   "[tool.mutmut]\n"
                   "pytest_add_cli_args_test_selection = [\n"
                   "    \"runner/tests/test_direct.py\",\n"
                   "    \"runner/tests/test_unrelated.py\",\n"
                   "]\n")
            _derived, _recorded, only_derived, only_recorded = \
                MO.check(tmp)
            self.assertIn("runner/tests/test_bare.py", only_derived)
            self.assertEqual(["runner/tests/test_unrelated.py"],
                             only_recorded)


_DERIVED = None
_RECORDED = None


def _real_lists():
    global _DERIVED, _RECORDED
    if _DERIVED is None:
        _DERIVED = MO.derive(ROOT)
        _RECORDED = MO.recorded_selection(ROOT)
    return _DERIVED, _RECORDED


class RecordedSelectionPinTest(unittest.TestCase):
    """The suite-side pin: pyproject's list is the derivation."""

    def test_the_recorded_selection_is_the_derivation(self):
        derived, recorded = _real_lists()
        self.assertEqual(
            derived, recorded,
            "pyproject.toml's mutmut selection has rotted; "
            "regenerate it with runner/tools/mutation_oracle.py "
            "(derived %d modules, recorded %d)"
            % (len(derived), len(recorded)))

    def test_the_selection_is_a_proper_subset_of_the_suite(self):
        derived, _recorded = _real_lists()
        total = sorted(
            "runner/tests/" + name
            for name in os.listdir(os.path.join(ROOT, "runner",
                                                "tests"))
            if name.startswith("test_") and name.endswith(".py"))
        self.assertLess(len(derived), len(total))
        self.assertGreater(len(derived), 100)

    def test_the_filed_examples_hold(self):
        derived, _recorded = _real_lists()
        # Loads runner/ops/core.py only, which names the mutated
        # file as data: not a loader (Q170, S1).
        self.assertNotIn("runner/tests/test_core.py", derived)
        # Loads approvalguard, whose _load_security imports the
        # mutated file lazily: a loader (Q170, S1).
        self.assertIn("runner/tests/test_agent_state_tree_wide.py",
                      derived)

    def test_every_selected_path_exists(self):
        derived, _recorded = _real_lists()
        for rel in derived:
            self.assertTrue(
                os.path.isfile(os.path.join(ROOT, rel)), rel)


class RecordedSelectionRotFamilyTest(unittest.TestCase):
    """The rot family around the 2026-11-23 gate failure.

    Build run 45303820640 (the 3.18.34.6 release head) went red
    on every platform because four loader modules had landed
    without the recorded selection being regenerated:
    test_de_dust_controls, test_ledger_honesty,
    test_raw_controls_pattern and test_v4_the_examples. Each
    one is pinned by name below, the recorded list's shape is
    pinned (sorted, unique, real paths), and the fixture tests
    simulate the rot shapes -- a dropped entry, several dropped
    entries, a phantom entry, a renamed loader -- so the check
    is seen naming each of them in the right direction.
    """

    ROT_2026_11_23 = (
        "runner/tests/test_de_dust_controls.py",
        "runner/tests/test_ledger_honesty.py",
        "runner/tests/test_raw_controls_pattern.py",
        "runner/tests/test_v4_the_examples.py",
    )

    def test_each_rotted_module_is_recorded(self):
        _derived, recorded = _real_lists()
        for rel in self.ROT_2026_11_23:
            self.assertIn(rel, recorded)

    def test_each_rotted_module_is_derived(self):
        derived, _recorded = _real_lists()
        for rel in self.ROT_2026_11_23:
            self.assertIn(rel, derived)

    def test_each_rotted_module_exists_on_disk(self):
        for rel in self.ROT_2026_11_23:
            self.assertTrue(
                os.path.isfile(os.path.join(ROOT, rel)), rel)

    def test_the_recorded_list_is_sorted(self):
        _derived, recorded = _real_lists()
        self.assertEqual(sorted(recorded), recorded)

    def test_the_recorded_list_has_no_duplicates(self):
        _derived, recorded = _real_lists()
        self.assertEqual(len(set(recorded)), len(recorded))

    def test_every_recorded_path_exists(self):
        _derived, recorded = _real_lists()
        for rel in recorded:
            self.assertTrue(
                os.path.isfile(os.path.join(ROOT, rel)), rel)

    def test_every_recorded_path_is_a_suite_test_module(self):
        _derived, recorded = _real_lists()
        for rel in recorded:
            self.assertTrue(rel.startswith("runner/tests/test_"),
                            rel)
            self.assertTrue(rel.endswith(".py"), rel)

    def _recorded_fixture(self, root, entries):
        _fixture_tree(root)
        _write(root, "pyproject.toml",
               "[tool.mutmut]\n"
               "pytest_add_cli_args_test_selection = [\n"
               + "".join('    "%s",\n' % e for e in entries)
               + "]\n")

    def test_one_dropped_entry_is_named_as_only_derived(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(tmp, [
                "runner/tests/test_direct.py",
                "runner/tests/test_bare.py",
                "runner/tests/test_deep.py",
                "runner/tests/test_multi.py",
                "runner/tests/test_lazy.py",
                # test_helper_chain.py dropped: the rot shape.
            ])
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            self.assertEqual(
                ["runner/tests/test_helper_chain.py"], only_derived)
            self.assertEqual([], only_recorded)

    def test_several_dropped_entries_are_all_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(tmp, [
                "runner/tests/test_direct.py",
            ])
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            for rel in ("runner/tests/test_bare.py",
                        "runner/tests/test_deep.py",
                        "runner/tests/test_multi.py",
                        "runner/tests/test_lazy.py",
                        "runner/tests/test_helper_chain.py"):
                self.assertIn(rel, only_derived)
            self.assertEqual([], only_recorded)

    def test_a_phantom_entry_is_named_as_only_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(tmp, [
                "runner/tests/test_direct.py",
                "runner/tests/test_bare.py",
                "runner/tests/test_deep.py",
                "runner/tests/test_multi.py",
                "runner/tests/test_lazy.py",
                "runner/tests/test_helper_chain.py",
                "runner/tests/test_phantom.py",
            ])
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            self.assertEqual([], only_derived)
            self.assertEqual(["runner/tests/test_phantom.py"],
                             only_recorded)

    def test_a_renamed_loader_rots_the_old_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(tmp, [
                "runner/tests/test_direct.py",
                "runner/tests/test_bare.py",
                "runner/tests/test_deep.py",
                "runner/tests/test_multi.py",
                "runner/tests/test_lazy.py",
                "runner/tests/test_helper_chain.py",
            ])
            _write(tmp, "runner/tests/test_direct_renamed.py",
                   "from runner.guard import security  # noqa\n")
            os.remove(os.path.join(
                tmp, "runner/tests/test_direct.py"))
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            self.assertEqual(
                ["runner/tests/test_direct_renamed.py"], only_derived)
            self.assertEqual(["runner/tests/test_direct.py"],
                             only_recorded)

    def test_an_exact_fixture_record_checks_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(tmp, [
                "runner/tests/test_bare.py",
                "runner/tests/test_deep.py",
                "runner/tests/test_direct.py",
                "runner/tests/test_helper_chain.py",
                "runner/tests/test_lazy.py",
                "runner/tests/test_multi.py",
            ])
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            self.assertEqual([], only_derived)
            self.assertEqual([], only_recorded)


class RecordedSelectionF15RotFamilyTest(unittest.TestCase):
    """The rot family around the 2026-11-27 gate failure.

    Ship 4.0.37.6 went red at the gate (hosted run 46023234083)
    in the test, test-macos and test-windows (1) jobs, each on
    the single pin test above: the F15 landing had added one
    loader module, runner/tests/test_f15_whole_gate.py, and
    the recorded selection was not regenerated, so the
    derivation held 403 modules against a recorded 402. The
    module is pinned by name below, at its sorted place, and
    the fixture tests simulate the shape that caused it: a
    newly landed loader, by each load style this tree uses,
    that nobody recorded.
    """

    F15_MODULE = "runner/tests/test_f15_whole_gate.py"

    def test_the_f15_module_is_derived(self):
        derived, _recorded = _real_lists()
        self.assertIn(self.F15_MODULE, derived)

    def test_the_f15_module_is_recorded(self):
        _derived, recorded = _real_lists()
        self.assertIn(self.F15_MODULE, recorded)

    def test_the_f15_module_exists_on_disk(self):
        self.assertTrue(os.path.isfile(
            os.path.join(ROOT, self.F15_MODULE)))

    def test_the_f15_module_sits_at_its_sorted_place(self):
        _derived, recorded = _real_lists()
        idx = recorded.index(self.F15_MODULE)
        self.assertEqual("runner/tests/test_extreview.py",
                         recorded[idx - 1])
        self.assertEqual("runner/tests/test_file_names.py",
                         recorded[idx + 1])

    def test_no_module_is_derived_but_unrecorded(self):
        derived, recorded = _real_lists()
        self.assertEqual(
            [], [p for p in derived if p not in recorded])

    def test_no_module_is_recorded_but_underived(self):
        derived, recorded = _real_lists()
        self.assertEqual(
            [], [p for p in recorded if p not in derived])

    def _recorded_fixture(self, root, entries):
        _fixture_tree(root)
        _write(root, "pyproject.toml",
               "[tool.mutmut]\n"
               "pytest_add_cli_args_test_selection = [\n"
               + "".join('    "%s",\n' % e for e in entries)
               + "]\n")

    _FIXTURE_RECORDED = [
        "runner/tests/test_bare.py",
        "runner/tests/test_deep.py",
        "runner/tests/test_direct.py",
        "runner/tests/test_helper_chain.py",
        "runner/tests/test_lazy.py",
        "runner/tests/test_multi.py",
    ]

    def test_a_new_direct_loader_unrecorded_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(tmp, self._FIXTURE_RECORDED)
            _write(tmp, "runner/tests/test_new_gate.py",
                   "from runner.guard import security  # noqa\n")
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            self.assertEqual(["runner/tests/test_new_gate.py"],
                             only_derived)
            self.assertEqual([], only_recorded)

    def test_a_new_lazy_loader_unrecorded_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(tmp, self._FIXTURE_RECORDED)
            _write(tmp, "runner/tests/test_new_lazy_gate.py",
                   "from runner.tools import lazytool  # noqa\n")
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            self.assertEqual(
                ["runner/tests/test_new_lazy_gate.py"], only_derived)
            self.assertEqual([], only_recorded)

    def test_a_new_helper_chain_loader_unrecorded_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(tmp, self._FIXTURE_RECORDED)
            _write(tmp, "runner/tests/test_new_chain_gate.py",
                   "from runner.tests.helper import security\n")
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            self.assertEqual(
                ["runner/tests/test_new_chain_gate.py"], only_derived)
            self.assertEqual([], only_recorded)

    def test_a_new_bookended_loader_unrecorded_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(tmp, self._FIXTURE_RECORDED)
            _write(tmp, "runner/tests/test_new_noisy_gate.py",
                   BOOKENDS
                   + "\nfrom runner.guard import security\n"
                   + BOOKENDS + "\n")
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            self.assertEqual(
                ["runner/tests/test_new_noisy_gate.py"], only_derived)
            self.assertEqual([], only_recorded)

    def test_two_new_loaders_unrecorded_are_both_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(tmp, self._FIXTURE_RECORDED)
            _write(tmp, "runner/tests/test_new_gate.py",
                   "from runner.guard import security  # noqa\n")
            _write(tmp, "runner/tests/test_new_lazy_gate.py",
                   "from runner.tools import lazytool  # noqa\n")
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            self.assertEqual(
                ["runner/tests/test_new_gate.py",
                 "runner/tests/test_new_lazy_gate.py"], only_derived)
            self.assertEqual([], only_recorded)

    def test_a_new_data_only_file_does_not_rot_the_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(tmp, self._FIXTURE_RECORDED)
            _write(tmp, "runner/tests/test_new_data_gate.py",
                   "from runner.ops import core  # noqa\n")
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            self.assertEqual([], only_derived)
            self.assertEqual([], only_recorded)

    def test_a_new_loader_recorded_checks_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._recorded_fixture(
                tmp, self._FIXTURE_RECORDED
                + ["runner/tests/test_new_gate.py"])
            _write(tmp, "runner/tests/test_new_gate.py",
                   "from runner.guard import security  # noqa\n")
            _d, _r, only_derived, only_recorded = MO.check(tmp)
            self.assertEqual([], only_derived)
            self.assertEqual([], only_recorded)


class MutantCopyHelperTest(unittest.TestCase):
    def test_outside_a_copy_the_helper_is_a_noop(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(mutant_copy.in_mutant_copy())
            self.assertIsNone(skip_in_mutant_copy(self))

            @skip_in_mutant_copy
            class Plain(unittest.TestCase):
                pass
            self.assertFalse(getattr(Plain, "__unittest_skip__",
                                     False))

    def test_inside_a_copy_the_method_call_skips(self):
        for value in ("stats", "runner.guard.security.x_f__mutmut_7"):
            with mock.patch.dict(
                    os.environ, {"MUTANT_UNDER_TEST": value}):
                self.assertTrue(mutant_copy.in_mutant_copy())
                with self.assertRaises(unittest.SkipTest) as cm:
                    skip_in_mutant_copy(self)
                self.assertEqual(REASON, str(cm.exception))

    def test_inside_a_copy_the_decorator_skips_the_class(self):
        with mock.patch.dict(os.environ,
                             {"MUTANT_UNDER_TEST": "stats"}):
            @skip_in_mutant_copy
            class TreeWide(unittest.TestCase):
                pass
            self.assertTrue(TreeWide.__unittest_skip__)
            self.assertEqual(REASON, TreeWide.__unittest_skip_why__)

    def test_the_reason_is_registered(self):
        from runner.tests.test_skip_registry import REGISTERED
        self.assertIn(REASON, REGISTERED)


class SeededWorkflowCheckTest(unittest.TestCase):
    def test_the_seeded_walk_checks_the_selection_first(self):
        path = os.path.join(ROOT, ".github", "workflows",
                            "mutation-seeded.yml")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("mutation_oracle.py --check", text)
        self.assertLess(text.index("mutation_oracle.py --check"),
                        text.index("mutmut run --max-children"))


if __name__ == "__main__":
    unittest.main()
