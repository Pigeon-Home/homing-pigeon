#!/usr/bin/env python3
"""Tests for the connected install/runner systems.

Async is treated as first-class: concurrent config writers, concurrent
ask calls, and concurrent daemon-start attempts must not corrupt state.
No live model or network.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from runner.runner import (
    ASK_SYSTEM,
    ask_model,
    ensure_inference_ready,
    inference_config,
    update_llama_from_config,
)
sys.path.insert(0, os.path.join(REPO, 'runner'))
from install import set_instructions, apply_profile


def _fake_opener(captured, reply="ok"):
    class FakeResp:
        def read(self, n):
            return json.dumps(
                {"choices": [{"message": {"content": reply}}]}
            ).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def opener(req, timeout=60):
        body = json.loads(req.data.decode())
        captured.append(body)
        return FakeResp()
    return opener


class ConnectedInferenceTest(unittest.TestCase):
    def test_update_llama_noop_without_inference(self):
        # No endpoint configured: must not try to start or pull.
        with mock.patch("runner.runner.ensure_inference_ready") as ready:
            update_llama_from_config({})
            ready.assert_not_called()

    def test_update_llama_pulls_when_model_changes(self):
        cfg = {"inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "llama3.2:3b"}}
        prev = {"inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "old"}}
        with mock.patch("runner.runner.ensure_inference_ready"), \
             mock.patch("shutil.which", return_value="/usr/bin/ollama"), \
             mock.patch("subprocess.run") as run:
            update_llama_from_config(cfg, previous=prev)
            run.assert_called()
            args = run.call_args[0][0]
            self.assertEqual(args[:2], ["ollama", "pull"])
            self.assertIn("llama3.2:3b", args)

    def test_ensure_inference_ready_skips_when_unconfigured(self):
        with mock.patch("shutil.which") as which:
            ensure_inference_ready({})
            which.assert_not_called()

    def test_ensure_inference_ready_starts_when_port_down(self):
        cfg = {"inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"}}
        with mock.patch("socket.socket") as sock, \
             mock.patch("shutil.which", return_value="/usr/bin/ollama"), \
             mock.patch("subprocess.Popen") as popen:
            sock.return_value.connect.side_effect = OSError("down")
            ensure_inference_ready(cfg)
            popen.assert_called()
            self.assertEqual(popen.call_args[0][0][:2], ["ollama", "serve"])


class AsyncInstructionsTest(unittest.TestCase):
    def test_concurrent_instruction_writers_do_not_corrupt(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"mailbox_user": "a@b.c"}, f)
        errors = []

        def writer(i):
            try:
                set_instructions(path, f"note {i}", append=True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        # File remains valid JSON and mailbox credential survives.
        self.assertEqual(cfg["mailbox_user"], "a@b.c")
        self.assertIn("owner_instructions", cfg)
        self.assertIsInstance(cfg["owner_instructions"], str)

    def test_concurrent_asks_keep_their_own_instructions(self):
        captured = []
        lock = threading.Lock()

        class FakeResp:
            def read(self, n):
                return b'{"choices":[{"message":{"content":"ok"}}]}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def opener(req, timeout=60):
            body = json.loads(req.data.decode())
            with lock:
                captured.append(body["messages"][0]["content"])
            return FakeResp()

        inf = inference_config({
            "inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"},
        })

        def one(i):
            ask_model(inf, "q", "out", 100, opener=opener,
                      instructions=f"box note {i}")

        threads = [threading.Thread(target=one, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(captured), 6)
        # Each call carried the hard prompt and its own note.
        for i in range(6):
            self.assertTrue(any(f"box note {i}" in c for c in captured))
        for c in captured:
            self.assertIn("Oracle", c)


class ProfileApplyTest(unittest.TestCase):
    def test_profile_does_not_clobber_secrets(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"mailbox_user": "a@b.c", "shared_secret": "keep"}, f)
        apply_profile(path, "password-only")
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["mailbox_user"], "a@b.c")
        self.assertEqual(cfg["shared_secret"], "keep")
        self.assertEqual(cfg["max_result_view"], "attested")


if __name__ == "__main__":
    unittest.main(verbosity=2)
