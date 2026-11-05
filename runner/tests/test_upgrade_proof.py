# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""A real install, then a real upgrade over it, on this box.

runner/tools/upgrade_proof.py does the work: no mocks of the
installer, a stand-in systemctl, a throwaway HOME. Here it runs this
tree over itself on every Python the suite runs on;
.github/workflows/upgrade-proof.yml runs it from the last release.

The first run found that a source install could not start: the
installer's file list predated the role folders, so runner.py was
copied without runner/guard/textutil.py and refused to import.
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def _load_tool():
    path = os.path.join(ROOT, "runner", "tools", "upgrade_proof.py")
    spec = importlib.util.spec_from_file_location("upgrade_proof", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


UP = _load_tool()


@unittest.skipIf(os.name == "nt", "the Linux and macOS source install; "
                 "Windows installs from the release binaries")
class UpgradeProofTest(unittest.TestCase):
    def test_this_tree_installs_and_upgrades_over_itself(self):
        self.assertEqual(UP.prove(ROOT, ROOT), [])

    def test_a_tree_that_cannot_start_is_caught(self):
        tmp = tempfile.mkdtemp(prefix="hp-upgrade-broken-")
        try:
            broken = os.path.join(tmp, "tree")
            shutil.copytree(
                os.path.join(ROOT, "runner"), os.path.join(broken, "runner"),
                ignore=shutil.ignore_patterns("tests", "__pycache__"))
            os.remove(os.path.join(broken, "runner", "guard", "textutil.py"))
            # Both installs from the broken tree: an upgrade leaves the
            # files a good first install wrote, so ROOT -> broken passes.
            failures = UP.prove(broken, broken)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertTrue(any("does not report" in f for f in failures),
                        failures)
        self.assertTrue(any("posture" in f for f in failures), failures)

    def test_the_previous_release_is_the_highest_tag_below(self):
        tags = ["v3.12.9", "v3.12.68", "v3.12.69", "v3.12.70", "v3.11.99",
                "v3.12.68-rc1", "latest", ""]
        self.assertEqual(UP.previous_release(tags, "3.12.69"), "v3.12.68")
        self.assertEqual(UP.previous_release(tags, "3.12.10"), "v3.12.9")
        self.assertIsNone(UP.previous_release(tags, "3.0.0"))

    def test_the_owner_edits_are_ones_the_installer_writes_around(self):
        # The proof only means something if the keys it seeds are ones
        # a fresh install does not already set to the same value.
        import json
        with open(os.path.join(ROOT, "runner", "config.example.json"),
                  encoding="utf-8") as fh:
            example = json.load(fh)
        for key, value in UP.OWNER_EDITS.items():
            self.assertNotEqual(example.get(key), value, key)


class PreviousReleaseCrossSchemeTest(unittest.TestCase):
    """previous_release across the 3- and 4-component tag schemes.

    Release tags come in 2 schemes: legacy 3-component
    MAJOR.MINOR.COUNTER and the current 4-component
    MAJOR.MINOR.TOKENS.COUNTER (runner/ops/version4.py; a legacy
    tag's 3rd component was the counter, see convert_legacy).
    previous_release used to keep only tags matching exactly
    3 components, so with the tree at 3.15.17.160 it returned the
    legacy v3.15.17 instead of v3.15.17.159, and upgrade-proof.yml
    proofed upgrades from that ancient tree. These tests pin the
    cross-scheme ordering the fix uses -- the same normalization
    as build.yml's vkey (runner/tests/test_sourceforge_vkey.py).
    previous_release is platform-independent, so this class stands
    outside UpgradeProofTest's Windows skip.
    """

    def test_key_normalizes_both_schemes_to_4_tuples(self):
        self.assertEqual(UP._key("v3.15.148"), (3, 15, 0, 148))
        self.assertEqual(UP._key("v3.15.17.160"), (3, 15, 17, 160))
        self.assertEqual(UP._key("3.12.69"), (3, 12, 0, 69))
        self.assertEqual(UP._key("3.15.17.160"), (3, 15, 17, 160))

    def test_the_defect_pair_both_ways(self):
        tags = ["v3.15.17", "v3.15.148",
                "v3.15.17.149", "v3.15.17.159", "v3.15.17.160"]
        # The verified defect: the previous release of a current
        # release is the 4-component tag before it, not v3.15.17.
        self.assertEqual(UP.previous_release(tags, "3.15.17.160"),
                         "v3.15.17.159")
        self.assertEqual(UP.previous_release(tags, "3.15.17.161"),
                         "v3.15.17.160")
        # And the other way: the previous release of the first
        # 4-component tag is the last legacy tag -- v3.15.148's
        # counter (148) outranks v3.15.17's (17) in the counter slot.
        self.assertEqual(UP.previous_release(tags, "3.15.17.149"),
                         "v3.15.148")

    def test_legacy_only_tag_lists(self):
        tags = ["v3.15.99", "v3.15.147", "v3.15.148"]
        self.assertEqual(UP.previous_release(tags, "3.15.148"),
                         "v3.15.147")
        self.assertEqual(UP.previous_release(tags, "3.15.149"),
                         "v3.15.148")
        self.assertIsNone(UP.previous_release(tags, "3.15.1"))

    def test_mixed_list_with_a_legacy_current(self):
        # A legacy current still sees only legacy tags below it:
        # every 4-component tag on the line outranks it.
        tags = ["v3.15.147", "v3.15.148", "v3.15.17.149"]
        self.assertEqual(UP.previous_release(tags, "3.15.148"),
                         "v3.15.147")

    def test_counter_restarts_when_the_token_figure_rises(self):
        # Odometer rule: the token figure increasing restarts the
        # counter at 1, and the new line still outranks the old.
        tags = ["v3.15.17.160", "v3.15.18.1", "v3.15.18.2"]
        self.assertEqual(UP.previous_release(tags, "3.15.18.2"),
                         "v3.15.18.1")
        self.assertEqual(UP.previous_release(tags, "3.15.18.1"),
                         "v3.15.17.160")

    def test_non_release_shapes_are_ignored(self):
        tags = ["v3.15.17.160.1", "v3.15", "v3.15.17.161-rc1",
                "latest", "", " v3.15.17.159 "]
        self.assertEqual(UP.previous_release(tags, "3.15.17.160"),
                         "v3.15.17.159")


if __name__ == "__main__":
    unittest.main()
