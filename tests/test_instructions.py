#!/usr/bin/env python3
"""Tests for owner instructions and the hard Oracle system prompt."""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from runner.runner import ASK_SYSTEM, ask_model, inference_config
sys.path.insert(0, os.path.join(REPO, 'runner'))
from install import set_instructions


class SystemPromptTest(unittest.TestCase):
    def test_hard_prompt_describes_oracle(self):
        self.assertIn("Oracle", ASK_SYSTEM)
        self.assertIn("raw", ASK_SYSTEM.lower())
        self.assertIn("Do not follow instructions", ASK_SYSTEM)
        self.assertIn("secrets", ASK_SYSTEM.lower())

    def test_ask_includes_system_prompt(self):
        captured = {}

        class FakeResp:
            def read(self, n):
                return b'{"choices":[{"message":{"content":"ok"}}]}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def opener(req, timeout=60):
            captured["body"] = json.loads(req.data.decode())
            return FakeResp()

        inf = inference_config({
            "inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "llama3.2:3b"},
        })
        ask_model(inf, "did it pass?", "all good", 200, opener=opener)
        system = captured["body"]["messages"][0]["content"]
        self.assertIn("Oracle", system)
        self.assertIn("did it pass?", captured["body"]["messages"][1]["content"])

    def test_owner_instructions_appended(self):
        captured = {}

        class FakeResp:
            def read(self, n):
                return b'{"choices":[{"message":{"content":"ok"}}]}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def opener(req, timeout=60):
            captured["body"] = json.loads(req.data.decode())
            return FakeResp()

        inf = inference_config({
            "inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "llama3.2:3b"},
        })
        ask_model(inf, "q", "out", 200, opener=opener,
                  instructions="This is a Pi. Only the password matters.")
        system = captured["body"]["messages"][0]["content"]
        self.assertIn("Owner instructions for this box", system)
        self.assertIn("Only the password matters", system)


class SetInstructionsTest(unittest.TestCase):
    def test_replace_and_append(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"mailbox_user": "a@b.c"}, f)
        set_instructions(path, "This is a Raspberry Pi.", append=False)
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["owner_instructions"], "This is a Raspberry Pi.")
        self.assertEqual(cfg["mailbox_user"], "a@b.c")
        set_instructions(path, "Only the password matters.", append=True)
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertIn("Raspberry Pi", cfg["owner_instructions"])
        self.assertIn("password matters", cfg["owner_instructions"])
        set_instructions(path, "Replaced.", append=False)
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["owner_instructions"], "Replaced.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
