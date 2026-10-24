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

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from runner.runner import (
    ask_model,
    ensure_inference_ready,
    inference_config,
    reload_hot_config,
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

    def test_update_llama_same_model_does_not_pull(self):
        cfg = {"inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "llama3.2:3b"}}
        prev = {"inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "llama3.2:3b"}}
        with mock.patch("runner.runner.ensure_inference_ready") as ready, \
             mock.patch("subprocess.run") as run:
            update_llama_from_config(cfg, previous=prev)
            ready.assert_called_once()
            run.assert_not_called()

    def test_ensure_inference_ready_skips_when_unconfigured(self):
        with mock.patch("socket.create_connection") as conn:
            ensure_inference_ready({})
            ensure_inference_ready({
                "inference": {"endpoint": "http://192.0.2.1/v1", "model": "m"},
            })
            conn.assert_not_called()

    def test_ensure_inference_ready_starts_when_port_down(self):
        cfg = {"inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"}}
        with mock.patch("socket.create_connection", side_effect=OSError("down")) as conn, \
             mock.patch("shutil.which", return_value="/usr/bin/ollama"), \
             mock.patch("subprocess.Popen") as popen:
            ensure_inference_ready(cfg)
            conn.assert_called_with(("127.0.0.1", 11434), timeout=1)
            popen.assert_called()
            self.assertEqual(popen.call_args[0][0][:2], ["ollama", "serve"])

    def test_ensure_inference_ready_leaves_a_listening_daemon(self):
        cfg = {"inference": {"endpoint": "http://127.0.0.1:11435/v1", "model": "m"}}
        live = mock.Mock()
        with mock.patch("socket.create_connection", return_value=live) as conn, \
             mock.patch("subprocess.Popen") as popen:
            ensure_inference_ready(cfg)
            conn.assert_called_with(("127.0.0.1", 11435), timeout=1)
            live.close.assert_called()
            popen.assert_not_called()

    def test_ensure_inference_ready_dials_ipv6_loopback(self):
        cfg = {"inference": {"endpoint": "http://[::1]:11434/v1", "model": "m"}}
        with mock.patch("socket.create_connection", side_effect=OSError("down")) as conn, \
             mock.patch("shutil.which", return_value="/usr/bin/ollama"), \
             mock.patch("subprocess.Popen") as popen:
            ensure_inference_ready(cfg)
            conn.assert_called_with(("::1", 11434), timeout=1)
            popen.assert_called()


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
        text = cfg["owner_instructions"]
        for i in range(8):
            self.assertIn(f"note {i}", text)

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


def _hot_cfg(**over):
    cfg = {
        "poll_interval_sec": 20,
        "workers": 1,
        "default_timeout_sec": 300,
        "max_output_bytes": 100000,
        "max_job_age_sec": 3600,
        "inference": {
            "endpoint": "http://127.0.0.1:11434/v1",
            "model": "llama3.2:3b",
        },
        "owner_instructions": "before",
    }
    cfg.update(over)
    return cfg


class LiveReloadTest(unittest.TestCase):
    def _reload(self, cfg, fresh):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(fresh, fh)
        os.utime(path, (2000, 2000))
        previous = {"inference": cfg.get("inference")}
        changed = reload_hot_config(cfg, path, {"mtime": 1000})
        return changed, previous

    def test_poll_interval_edit_does_not_change_the_model(self):
        cfg = _hot_cfg()
        fresh = _hot_cfg(poll_interval_sec=5)
        changed, previous = self._reload(cfg, fresh)
        self.assertEqual(changed, ["poll_interval_sec"])
        self.assertNotIn("inference", changed)
        self.assertEqual(cfg["inference"]["model"], "llama3.2:3b")
        self.assertEqual(
            inference_config(cfg)["model"],
            inference_config(previous)["model"],
        )

    def test_model_and_instructions_reload_and_only_then_pull(self):
        cfg = _hot_cfg()
        fresh = _hot_cfg(
            owner_instructions="after",
            inference={
                "endpoint": "http://127.0.0.1:11434/v1",
                "model": "llama3.2:3b",
            },
        )
        fresh["inference"] = {
            "endpoint": "http://127.0.0.1:11434/v1",
            "model": "other:7b",
        }
        changed, previous = self._reload(cfg, fresh)
        self.assertIn("inference", changed)
        self.assertIn("owner_instructions", changed)
        self.assertEqual(cfg["owner_instructions"], "after")
        with mock.patch("runner.runner.ensure_inference_ready"), \
             mock.patch("shutil.which", return_value="/usr/bin/ollama"), \
             mock.patch("subprocess.run") as run:
            if "inference" in changed:
                update_llama_from_config(cfg, previous=previous)
            args = run.call_args[0][0]
            self.assertEqual(args, ["ollama", "pull", "other:7b"])

    def test_invalid_inference_is_left_alone(self):
        cfg = _hot_cfg()
        fresh = _hot_cfg()
        fresh["inference"] = "not-an-object"
        changed, _ = self._reload(cfg, fresh)
        self.assertNotIn("inference", changed)
        self.assertEqual(cfg["inference"]["model"], "llama3.2:3b")


if __name__ == "__main__":
    unittest.main(verbosity=2)
