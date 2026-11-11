#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Decision 1 startup: the default class.

Split from runner/tests/test_decision1_startup.py in
the Q136 follow-on file split (2026-11-11); the tests
are moved verbatim, not rewritten. This piece carries
DefaultClassTest -- one generated test per field of
runner/guard/defaulted.py's table -- and
DefaultClassTableTest, the pin that the generated
family and the module's table are the same size.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.guard import defaulted  # noqa: E402
from runner.tests.decision1_startup_support import run_main  # noqa: E402


class DefaultClassTest(unittest.TestCase):
    """Generated below: one test per default-class field. The
    invalid value starts the runner on the documented default,
    and the startup warning names the key."""



# (key, present-but-invalid value, documented default) -- the
# table runner/guard/defaulted.py carries, with the defaults the
# docs promise, pinned here independently of that module.
DEFAULT_FIELDS = [
    ("task_timeout", True, 86400),
    ("default_timeout_sec", True, 300),
    ("max_job_age_sec", True, 3600),
    ("max_plan_steps", True, 8),
    ("max_plan_timeout_sec", True, 600),
    ("oracle_learning_promote_after", True, 2),
    ("review_scan_bytes", True, 65536),
    ("output_retention_days", True, 7),
    ("v2_answer_deadline_sec", True, 0),
    ("query_budget", True, 8),
    ("max_query_budget", True, 8),
    ("local_wake_cooldown_sec", True, 900),
    ("max_output_bytes", True, 100000),
    ("agent_wall_clock_sec", True, 300),
    ("poll_interval_sec", True, 20),
    ("result_stash_retention_sec", True, 86400),
    ("result_resend_backoff_sec", True, 60),
    ("work_retention_sec", True, 604800),
    ("dtls_greeting", "bogus", "family"),
]


def _make_default_tests():
    for key, bad, expected in DEFAULT_FIELDS:

        def default_test(self, key=key, bad=bad, expected=expected):
            # The reader's side: the key is defaulted, the default
            # on record is the documented one, and the summary line
            # (the startup warning's exact text) names the key.
            self.assertTrue(defaulted.is_defaulted(key, bad))
            self.assertEqual(defaulted.default_for(key), expected)
            self.assertEqual(defaulted.defaulted_keys({key: bad}),
                             [key])
            line = defaulted.summary_line([key])
            self.assertIn(key, line)
            # A usable value (the default itself) is not defaulted.
            self.assertFalse(defaulted.is_defaulted(key, expected))
            # The startup side: a real main() proceeds (the
            # read-only --audit-report one-shot returns 0) and its
            # warning line names the key as read-as-default.
            rc, out, err = run_main({key: bad}, ("--audit-report",))
            self.assertEqual(rc, 0, err)
            self.assertIn("read as their default: %s" % key, out)

        setattr(DefaultClassTest, "test_defaults_%s" % key,
                default_test)


_make_default_tests()


class DefaultClassTableTest(unittest.TestCase):
    """The generated family and the module's table are the same
    size: a default-class key added to defaulted.py without a
    test here fails this count instead of slipping through."""

    def test_the_family_covers_the_whole_table(self):
        table = set(defaulted.NUMERIC) | set(defaulted.ENUM)
        self.assertEqual({k for k, _b, _d in DEFAULT_FIELDS}, table)


if __name__ == "__main__":
    unittest.main(verbosity=2)
