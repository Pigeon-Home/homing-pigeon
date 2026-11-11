#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Decision 1 startup, refuse class through main(): the
base field list.

Split from runner/tests/test_decision1_startup.py in the
Q136 follow-on file split (2026-11-11); the tests are
moved verbatim, not rewritten. This piece carries the
REFUSE_MAIN base list: the mailbox ports, the size caps
and their fellow startup checks in
runner._validate_size_caps (pong_platform,
extension_review, recipes, change_repos), and the whole
security block as validate_security_config reads it.
The generated security-mode values and the
build_key_policies fields live in
test_decision1_startup_refuse_policies.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.tests.decision1_startup_support import run_main  # noqa: E402


class RefuseMainTest(unittest.TestCase):
    """Generated below: one test per refuse-class field, each a
    real startup that must exit 2 with the key named on stderr."""


# (name, cfg_extra, substrings the refusal must contain)
REFUSE_MAIN = [
    ("imap_port", {"imap_port": "not-a-port"}, ["imap_port"]),
    ("smtp_port", {"smtp_port": True}, ["smtp_port"]),
    ("max_job_bytes", {"max_job_bytes": -1}, ["max_job_bytes"]),
    ("max_script_bytes", {"max_script_bytes": "huge"},
     ["max_script_bytes"]),
    ("max_result_bytes", {"max_result_bytes": 1.5},
     ["max_result_bytes"]),
    ("pong_platform", {"pong_platform": "bogus"}, ["pong_platform"]),
    ("extension_review", {"extension_review": "bogus"},
     ["extension_review"]),
    ("recipes", {"recipes": "nope"}, ["recipes"]),
    ("change_repos", {"change_repos": "nope"}, ["change_repos"]),
    ("security", {"security": "off"}, ["security"]),
    ("security_modes", {"security": {"modes": "off"}},
     ["security.modes"]),
    ("security_modes_unknown_feature",
     {"security": {"modes": {"nope": "off"}}}, ["nope"]),
    ("security_audit_max_lines",
     {"security": {"audit_max_lines": 0}}, ["audit_max_lines"]),
    ("security_audit_max_lines_text",
     {"security": {"audit_max_lines": "many"}}, ["audit_max_lines"]),
    ("security_confinement", {"security": {"confinement": "x"}},
     ["security.confinement"]),
    ("security_confinement_work_mount",
     {"security": {"confinement": {"work_mount": "relative/path"}}},
     ["confinement", "work_mount"]),
    ("security_confinement_extra_flags",
     {"security": {"confinement": {"extra_flags": "nope"}}},
     ["extra_flags"]),
    ("security_confinement_extra_ro_binds",
     {"security": {"confinement": {"extra_ro_binds": "nope"}}},
     ["extra_ro_binds"]),
    ("security_job_user", {"security": {"job_user": {}}},
     ["job_user"]),
    ("security_job_user_user_bad_char",
     {"security": {"job_user": {"user": "a/b"}}}, ["job_user"]),
    ("key_policies", {"key_policies": "nope"}, ["key_policies"]),
    ("key_policies_entry", {"key_policies": {"k": "nope"}},
     ["key_policies"]),
]


def _make_refuse_main_tests():
    for name, extra, needles in REFUSE_MAIN:

        def refuse_test(self, extra=extra, needles=needles):
            rc, _out, err = run_main(extra)
            self.assertEqual(rc, 2, err)
            for needle in needles:
                self.assertIn(needle, err)

        setattr(RefuseMainTest, "test_refuses_%s" % name, refuse_test)


_make_refuse_main_tests()


if __name__ == "__main__":
    unittest.main(verbosity=2)
