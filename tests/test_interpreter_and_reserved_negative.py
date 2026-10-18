#!/usr/bin/env python3
"""Negative cases for platform_interpreter and windows_reserved_name.

Findings: platform_interpreter always returns a list. windows_reserved_name
tolerates non-string input and returns bool without raising.
Concurrent calls do not raise.
"""
import os
import sys
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import platform_interpreter, windows_reserved_name  # noqa: E402


class InterpreterAndReservedNegative(unittest.TestCase):
    def test_platform_interpreter_always_list(self):
        """Finding: platform_interpreter returns a list of strings
        even under unexpected platform state."""
        interp = platform_interpreter()
        self.assertIsInstance(interp, list)
        self.assertTrue(all(isinstance(x, str) for x in interp))

    def test_windows_reserved_bad_input(self):
        """Finding: non-string, None, and edge names return bool
        without raising."""
        self.assertIsInstance(windows_reserved_name(None), bool)
        self.assertIsInstance(windows_reserved_name(123), bool)
        self.assertIsInstance(windows_reserved_name(""), bool)
        self.assertIsInstance(windows_reserved_name("CON"), bool)
        self.assertIsInstance(windows_reserved_name("file.txt"), bool)
        self.assertIsInstance(windows_reserved_name("NUL."), bool)

    def test_concurrent_reserved(self):
        """Finding: concurrent windows_reserved_name calls do not raise."""
        errors = []
        def worker():
            try:
                for name in [None, "CON", "aux.txt", 5, "", "normal"]:
                    windows_reserved_name(name)
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
