"""check_door_policy's refusals before any policy is read.

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854

A door that is not one of the three, a key id that is not text, a
config that is not an object, and key policies that will not build
each come back as a reason, never as an exception and never as None.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.wire import verify as V  # noqa: E402

SECRETS = {"": "owner-" + "a1" * 20, "ci": "ci-" + "b2" * 20}


class DoorPolicyEdgesTest(unittest.TestCase):
    def test_an_unknown_door(self):
        self.assertEqual(V.check_door_policy({}, SECRETS, "ci", "mail"),
                         "unknown door")

    def test_a_key_id_that_is_not_text(self):
        self.assertEqual(V.check_door_policy({}, SECRETS, None, "query"),
                         "invalid key id")

    def test_a_config_that_is_not_an_object_reads_as_empty(self):
        self.assertIsNone(V.check_door_policy(["x"], SECRETS, "ci", "board"))

    def test_policies_that_will_not_build_are_a_refusal(self):
        with mock.patch.object(V, "build_key_policies",
                               side_effect=ValueError("bad regex")):
            why = V.check_door_policy({}, SECRETS, "ci", "v2")
        self.assertEqual(why, "key policies unreadable: bad regex")

    def test_the_owner_key_passes_when_no_entry_names_it(self):
        self.assertIsNone(V.check_door_policy({}, SECRETS, "", "query"))
        cfg = {"key_policies_default_deny": True,
               "key_policies": {"ci": {"allowed_kinds": ["exec"]}}}
        self.assertIsNone(V.check_door_policy(cfg, SECRETS, "", "board"))

    def test_an_entry_on_the_owner_key_binds_it_at_the_doors(self):
        # Q103 item 2: the owner's own entry is read, as at the job door.
        cfg = {"key_policies": {"": {"allowed_kinds": ["exec"]}}}
        self.assertEqual("query is not in this key's allowed_kinds",
                         V.check_door_policy(cfg, SECRETS, "", "query"))


if __name__ == "__main__":
    unittest.main()
