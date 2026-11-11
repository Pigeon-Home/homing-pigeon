#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Decision 1 startup, refuse class through main(): the
generated mode and key-policy fields.

Split from runner/tests/test_decision1_startup.py in the
Q136 follow-on file split (2026-11-11); the tests are
moved verbatim, not rewritten. This piece carries the
REFUSE_MAIN entries the original file's loops appended:
one invalid mode value per security feature, and one
bad value per build_key_policies field that refuses,
plus the unrecognised key_policies field (Q129). The
twelfth policy field, allow_dangerous_env, has no
refuse test: the reader normalizes it fail-safe -- see
the original enumeration's record in the desk.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.guard.security import FEATURES  # noqa: E402
from runner.tests.decision1_startup_support import run_main  # noqa: E402


class RefusePoliciesTest(unittest.TestCase):
    """Generated below: one test per generated refuse-class
    field, each a real startup that must exit 2 with the key
    named on stderr."""


REFUSE_POLICIES = []
# One invalid mode value per security feature.
for _feature in FEATURES:
    REFUSE_POLICIES.append((
        "security_modes_%s" % _feature,
        {"security": {"modes": {_feature: "maybe"}}},
        ["security.modes.%s" % _feature]))

# One bad value per build_key_policies field that refuses. (The
# twelfth field, allow_dangerous_env, is normalized fail-safe and
# cannot refuse -- see the module docstring.)
POLICY_BAD = [
    ("allowed_kinds", "exec"),
    ("allowed_interpreters", "sh"),
    ("max_timeout_sec", "soon"),
    ("allowed_recipes", []),
    ("allowed_script_sha384", []),
    ("allowed_env", []),
    ("denied_env", "FOO"),
    ("allow_file_urls", "yes"),
    ("allowed_files", []),
    ("max_args", -1),
    ("args_pattern", "("),
]
# An unrecognised key_policies field refuses too (Q129,
# 2026-11-06): the field is not a malformed value of a known
# field but a name the builder does not know at all, and
# warn-and-drop left the key with a smaller policy than the
# file appeared to set -- possibly none of the fence the
# operator wrote.
REFUSE_POLICIES.append((
    "key_policies_unknown_field",
    {"key_policies": {"k": {"allowed_kind": ["exec"]}}},
    ["key_policies", "allowed_kind"]))

for _field, _bad in POLICY_BAD:
    REFUSE_POLICIES.append((
        "key_policies_%s" % _field,
        {"key_policies": {"k": {_field: _bad}}},
        ["key_policies", _field]))


def _make_refuse_main_tests():
    for name, extra, needles in REFUSE_POLICIES:

        def refuse_test(self, extra=extra, needles=needles):
            rc, _out, err = run_main(extra)
            self.assertEqual(rc, 2, err)
            for needle in needles:
                self.assertIn(needle, err)

        setattr(RefusePoliciesTest, "test_refuses_%s" % name, refuse_test)


_make_refuse_main_tests()


if __name__ == "__main__":
    unittest.main(verbosity=2)
