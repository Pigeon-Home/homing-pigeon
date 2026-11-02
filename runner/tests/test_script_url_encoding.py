#!/usr/bin/env python3
"""A script fetched by script_url is staged like an inline one.

Windows PowerShell 5.1 reads a BOM-less .ps1 in the machine
ANSI code page. The inline path adds a UTF-8 BOM and writes
bytes, so a newline is not translated. The download path
used to keep the fetched bytes with no mark.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.runner import declare_ps1_utf8  # noqa: E402


class ScriptUrlEncodingTest(unittest.TestCase):
    def test_a_bomless_utf8_ps1_gains_one_mark_and_keeps_its_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "script.ps1")
            body = "Write-Host 'café'\n".encode("utf-8")
            with open(path, "wb") as fh:
                fh.write(body)
            declare_ps1_utf8(path)
            with open(path, "rb") as fh:
                staged = fh.read()
            self.assertTrue(staged.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(staged[3:], body)
            self.assertNotIn(b"\r\n", staged)

    def test_a_mark_already_there_is_not_doubled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "script.ps1")
            body = b"\xef\xbb\xbfWrite-Host 1\n"
            with open(path, "wb") as fh:
                fh.write(body)
            declare_ps1_utf8(path)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), body)

    def test_bytes_that_are_not_utf8_are_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "script.ps1")
            body = b"\xff\xfeW\x00"
            with open(path, "wb") as fh:
                fh.write(body)
            declare_ps1_utf8(path)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), body)

    def test_a_shell_script_is_not_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "script")
            body = b"echo hi\n"
            with open(path, "wb") as fh:
                fh.write(body)
            declare_ps1_utf8(path)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), body)


if __name__ == "__main__":
    unittest.main()
