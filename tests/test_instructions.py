#!/usr/bin/env python3
"""Tests for owner instructions and the hard Oracle system prompt."""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from runner.runner import ASK_SYSTEM, answer_queries, ask_model, inference_config
sys.path.insert(0, os.path.join(REPO, 'runner'))
from install import apply_instruction_flags, set_instructions


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

    def test_blank_instructions_add_no_header(self):
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
            "inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"},
        })
        ask_model(inf, "q", "out", 200, opener=opener, instructions="   ")
        self.assertNotIn("Owner instructions", captured["body"]["messages"][0]["content"])

    def test_answer_queries_reads_owner_instructions(self):
        import runner.runner as rr
        captured = {}

        class FakeResp:
            def read(self, n):
                return b'{"choices":[{"message":{"content":"fine"}}]}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def opener(req, timeout=60):
            captured["body"] = json.loads(req.data.decode())
            return FakeResp()

        orig = rr._default_inference_open
        rr._default_inference_open = opener
        try:
            answers, spent = answer_queries(
                [{"op": "ask", "question": "status?"}],
                {"stdout": "pong\n", "stderr": ""},
                {},
                1,
                cfg={
                    "inference": {
                        "endpoint": "http://127.0.0.1:11434/v1",
                        "model": "m",
                    },
                    "owner_instructions": "Only the password matters.",
                },
            )
        finally:
            rr._default_inference_open = orig
        self.assertEqual(spent, 1)
        self.assertEqual(answers[0]["answer"], "fine")
        system = captured["body"]["messages"][0]["content"]
        self.assertIn("Only the password matters", system)
        self.assertIn("Oracle", system)


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

    def test_blank_text_does_not_rewrite(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"owner_instructions": "keep me", "mailbox_user": "a@b.c"}, f)
        os.chmod(path, 0o640)
        with open(path, "rb") as fh:
            before = fh.read()
        set_instructions(path, "   ", append=False)
        set_instructions(path, "", append=True)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), before)

    def test_add_wins_when_both_flags_are_set(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"owner_instructions": "base", "mailbox_user": "a@b.c"}, f)
        apply_instruction_flags(path, "should not replace", "and this")
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertIn("base", cfg["owner_instructions"])
        self.assertIn("and this", cfg["owner_instructions"])
        self.assertNotIn("should not replace", cfg["owner_instructions"])
        self.assertEqual(cfg["mailbox_user"], "a@b.c")


if __name__ == "__main__":
    unittest.main(verbosity=2)
