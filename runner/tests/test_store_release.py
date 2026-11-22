"""Pins on the Snap Store release planner.

The planner in runner/tools/store_release.py carries the rules
the manual Releases page fight taught: never release a half
built version, never fight the store while its review holds a
revision, release both architectures together, and say plainly
when a version already stands released. These tests pin those
rules so a later edit cannot quietly thin them. The planner
opens no socket and runs no command; the store call itself is
the pipeline's, with the credentials it already holds.
"""

import importlib.util
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "store_release",
    os.path.join(REPO, "runner", "tools", "store_release.py"))
store_release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(store_release)


def _rev(revision, arch, version="3.17.32.13", status="Approved",
         channels=()):
    return {"revision": revision, "architecture": arch,
            "version": version, "status": status,
            "channels": list(channels)}


class PlanReleaseTest(unittest.TestCase):

    def test_both_arches_release_together(self):
        plan = store_release.plan_release(
            [_rev(20, "amd64"), _rev(21, "arm64")], "3.17.32.13")
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["commands"], [
            "snapcraft release homing-pigeon 20 latest/stable,latest/edge",
            "snapcraft release homing-pigeon 21 latest/stable,latest/edge",
        ])

    def test_review_queued_refuses_and_names_the_hold(self):
        plan = store_release.plan_release(
            [_rev(20, "amd64", status="ReviewQueued"),
             _rev(21, "arm64", status="ReviewQueued")], "3.17.32.13")
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["commands"], [])
        self.assertIn("ReviewQueued", plan["reason"])

    def test_one_held_arch_refuses_the_whole_release(self):
        plan = store_release.plan_release(
            [_rev(20, "amd64"),
             _rev(21, "arm64", status="ReviewInProgress")], "3.17.32.13")
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["commands"], [])

    def test_missing_arch_refuses(self):
        plan = store_release.plan_release(
            [_rev(20, "amd64")], "3.17.32.13")
        self.assertFalse(plan["ok"])
        self.assertIn("arm64", plan["reason"])

    def test_no_revision_at_version_refuses(self):
        plan = store_release.plan_release(
            [_rev(12, "amd64", version="3.17.32.11"),
             _rev(13, "arm64", version="3.17.32.11")], "3.17.32.13")
        self.assertFalse(plan["ok"])
        self.assertIn("3.17.32.13", plan["reason"])

    def test_newest_revision_per_arch_wins(self):
        plan = store_release.plan_release(
            [_rev(18, "amd64"), _rev(20, "amd64"), _rev(21, "arm64")],
            "3.17.32.13")
        self.assertTrue(plan["ok"])
        self.assertIn(" 20 ", plan["commands"][0])

    def test_other_versions_do_not_leak_in(self):
        plan = store_release.plan_release(
            [_rev(99, "amd64", version="9.9.9.9"),
             _rev(20, "amd64"), _rev(21, "arm64")], "3.17.32.13")
        self.assertTrue(plan["ok"])
        self.assertNotIn("99", " ".join(plan["commands"]))

    def test_already_released_is_ok_with_no_commands(self):
        done = ["latest/stable", "latest/edge"]
        plan = store_release.plan_release(
            [_rev(20, "amd64", channels=done),
             _rev(21, "arm64", channels=done)], "3.17.32.13")
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["commands"], [])

    def test_partly_released_releases_only_the_missing_channels(self):
        plan = store_release.plan_release(
            [_rev(20, "amd64", channels=["latest/edge"]),
             _rev(21, "arm64", channels=["latest/edge"])], "3.17.32.13")
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["commands"], [
            "snapcraft release homing-pigeon 20 latest/stable",
            "snapcraft release homing-pigeon 21 latest/stable",
        ])

    def test_single_channel_target(self):
        plan = store_release.plan_release(
            [_rev(20, "amd64"), _rev(21, "arm64")], "3.17.32.13",
            channels=("latest/edge",))
        self.assertTrue(plan["ok"])
        self.assertTrue(all(c.endswith("latest/edge")
                            for c in plan["commands"]))


if __name__ == "__main__":
    unittest.main()
