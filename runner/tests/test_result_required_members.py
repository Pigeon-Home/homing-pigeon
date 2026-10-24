"""The spec-required result members survive the result policy.

PROTOCOL's result table marks `completed_at` and `runner`
REQUIRED. The exec path builds both into the result, but
apply_result_policy rebuilds the dict around the view -- and the
rebuild dropped them, so every policy-shaped result the runner
emitted lacked two required members (claims audit, 2026-10-20).
The members now ride the policy's base dict: carried through
from the exec result when present, minted when a caller hands
in a bare exec result.
"""

import re
import socket
import unittest

from runner.runner import apply_result_policy

STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
VIEWS = ("full", "redacted", "summary", "attested")


def _job(view):
    return {"job_id": "job-1", "kind": "exec",
            "result_policy": {"view": view}}


def _exec(**over):
    er = {"stdout": "hello", "stderr": "", "exit_code": 0,
          "timed_out": False, "duration_sec": 0.25,
          "completed_at": "2026-10-13T12:01:23Z",
          "runner": "DESKTOP-ABC123"}
    er.update(over)
    return er


class CarriedThroughTest(unittest.TestCase):
    def test_members_survive_every_view(self):
        for view in VIEWS:
            with self.subTest(view=view):
                result, _retain = apply_result_policy(
                    {}, _job(view), _exec(), {}, True)
                self.assertEqual(result["completed_at"],
                                 "2026-10-13T12:01:23Z")
                self.assertEqual(result["runner"], "DESKTOP-ABC123")


class MintedWhenAbsentTest(unittest.TestCase):
    def test_missing_members_are_minted(self):
        er = _exec()
        del er["completed_at"]
        del er["runner"]
        for view in VIEWS:
            with self.subTest(view=view):
                result, _retain = apply_result_policy(
                    {}, _job(view), er, {}, True)
                self.assertRegex(result["completed_at"], STAMP)
                self.assertEqual(result["runner"],
                                 socket.gethostname())

    def test_wrong_typed_members_are_minted_not_carried(self):
        for bad in (42, None, "", ["x"], {"t": 1}):
            with self.subTest(bad=repr(bad)):
                result, _retain = apply_result_policy(
                    {}, _job("full"),
                    _exec(completed_at=bad, runner=bad), {}, True)
                self.assertRegex(result["completed_at"], STAMP)
                self.assertEqual(result["runner"],
                                 socket.gethostname())

    def test_bare_exec_result_still_gets_both_members(self):
        result, _retain = apply_result_policy(
            {}, _job("full"), {"stdout": "ok"}, {}, False)
        self.assertRegex(result["completed_at"], STAMP)
        self.assertEqual(result["runner"], socket.gethostname())


if __name__ == "__main__":
    unittest.main()
