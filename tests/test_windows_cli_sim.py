#!/usr/bin/env python3
"""Windows simulation of the Oracle CLI.

The browser send looked dead: the log was busy, the page showed
nothing useful. The CLI is the same ask path without the HTTP
layer. This drives it with Windows-style paths and a scripted
model, and pins that it returns an answer or a clear rejection
instead of hanging.
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402


class WindowsCLISim(unittest.TestCase):
    """Finding: the browser send can look dead while the model works.
    The CLI must return a line, not hang, even on Windows paths.
    """

    def _run(self, lines, ask, base):
        out = []
        queue = list(lines)

        def fake_input(prompt=""):
            if not queue:
                raise EOFError
            return queue.pop(0)

        with mock.patch.object(R, "ask_model_agent", side_effect=ask), \
             mock.patch.object(R, "_warm_oracle_model"):
            rc = R.oracle_cli(
                {"base_dir": base, "inference": {
                    "endpoint": "http://127.0.0.1:11434/v1",
                    "model": "llama3.2:3b",
                }},
                cfg_path=os.path.join(base, "config.json"),
                input_fn=fake_input,
                print_fn=out.append,
            )
        return rc, out

    def test_windows_path_returns_answer(self):
        # Simulate a Windows state dir. The CLI must print the answer.
        base = os.path.join(tempfile.mkdtemp(), "C", "Users", "pigeon",
                            "AppData", "Local", "homing-pigeon")
        os.makedirs(base)

        def ask(*a, **k):
            return {"op": "ask", "answer": "three jobs finished today"}

        rc, out = self._run(["what ran today?", "/quit"], ask, base)
        self.assertEqual(rc, 0)
        self.assertTrue(any("three jobs finished" in line for line in out),
                        out)
        # The chat log is written under the Windows-style path.
        log = os.path.join(base, "oracle-chat.jsonl")
        self.assertTrue(os.path.isfile(log))

    def test_windows_path_rejection_is_printed(self):
        base = os.path.join(tempfile.mkdtemp(), "C", "Users", "pigeon")
        os.makedirs(base)

        def ask(*a, **k):
            return {"op": "ask", "rejected": "inference_error",
                    "detail": "model did not answer"}

        rc, out = self._run(["status?", "/quit"], ask, base)
        self.assertEqual(rc, 0)
        self.assertTrue(any("did not answer" in line or "did not" in line
                            for line in out), out)

    def test_slow_model_does_not_hang_the_cli(self):
        # A model that takes a few seconds must still return. The
        # browser send looked dead for the same reason: the call
        # blocks until the model finishes.
        base = tempfile.mkdtemp()

        def ask(*a, **k):
            time.sleep(1.5)
            return {"op": "ask", "answer": "done"}

        t0 = time.monotonic()
        rc, out = self._run(["ping", "/quit"], ask, base)
        elapsed = time.monotonic() - t0
        self.assertEqual(rc, 0)
        self.assertLess(elapsed, 10)
        self.assertTrue(any("done" in line for line in out), out)

    def test_backslash_paths_in_context_do_not_crash(self):
        base = tempfile.mkdtemp()
        retained = os.path.join(base, "retained")
        os.makedirs(retained)
        with open(os.path.join(retained, "job-1.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"stdout": "ok", "kind": "exec"}, fh)

        def ask(inf, question, output_text, *a, **k):
            # The context must be a string even with odd paths.
            self.assertIsInstance(output_text, str)
            return {"op": "ask", "answer": "saw context"}

        rc, out = self._run(["what is in retained?", "/quit"], ask, base)
        self.assertEqual(rc, 0)
        self.assertTrue(any("saw context" in line for line in out), out)


if __name__ == "__main__":
    unittest.main()
