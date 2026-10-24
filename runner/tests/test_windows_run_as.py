#!/usr/bin/env python3
"""M11 tests: Windows --run-as installer option.

Windows-only behavior is verified by inspecting the schtasks argv
the installer builds (no live schtasks here)."""
import os
import sys
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import install as IN  # noqa: E402


def _capture(dst="/tmp/pfx", cfg="/tmp/pfx/config.json", **kw):
    calls = []
    with mock.patch.object(IN, "run",
                           side_effect=lambda cmd, **k: calls.append(cmd)):
        IN.install_windows(dst, cfg, **kw)
    return calls


class RunAsTest(unittest.TestCase):
    def test_default_is_system_highest(self):
        calls = _capture()
        create = calls[0]
        self.assertEqual(create[0], "schtasks")
        self.assertIn("/RU", create)
        self.assertEqual(create[create.index("/RU") + 1], "SYSTEM")
        self.assertEqual(create[create.index("/RL") + 1], "HIGHEST")

    def test_named_user_gets_limited(self):
        calls = _capture(run_as="pigeon")
        create = calls[0]
        self.assertEqual(create[create.index("/RU") + 1], "pigeon")
        self.assertEqual(create[create.index("/RL") + 1], "LIMITED")

    def test_service_account(self):
        calls = _capture(run_as="NT AUTHORITY\\Network Service")
        create = calls[0]
        self.assertEqual(
            create[create.index("/RU") + 1],
            "NT AUTHORITY\\Network Service")
        self.assertEqual(create[create.index("/RL") + 1], "LIMITED")

    def test_none_means_system(self):
        calls = _capture(run_as=None)
        create = calls[0]
        self.assertEqual(create[create.index("/RU") + 1], "SYSTEM")

    def test_task_name_and_trigger_unchanged(self):
        calls = _capture(run_as="pigeon")
        create = calls[0]
        self.assertEqual(create[create.index("/TN") + 1], "HomingPigeon")
        self.assertEqual(create[create.index("/SC") + 1], "ONSTART")
        # second call starts the task
        self.assertEqual(calls[1][:3], ["schtasks", "/Run", "/TN"])

    def test_cli_flag_exists(self):
        # --run-as is wired into the installer's parser; check help text.
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                with mock.patch.object(sys, "argv", ["install.py", "--help"]):
                    IN.main()
            except SystemExit:
                pass
        self.assertIn("--run-as", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
