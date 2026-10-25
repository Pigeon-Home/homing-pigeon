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


if __name__ == "__main__":
    unittest.main()
