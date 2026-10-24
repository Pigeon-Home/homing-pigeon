#!/usr/bin/env python3
"""Oracle chat stall fixes (2026-10-16 field reports).

A first question on a cold laptop model looked identical to a dead
chat: multi-minute model calls, an agent that reached for shell
searches, tool commands that could sit on stdin for their whole
timeout, and a page that showed nothing. These tests pin the fixes:
empty stdin + the existing timeout clamp on run, keep_alive on the
local endpoint, the per-question wall clock that forces a final
answer, progress steps, the token-gated /status route, and the
prompt's ranking of run as the last resort. No live model: scripted
openers only.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402


def _agent_cfg(**over):
    cfg = {"endpoint": "http://127.0.0.1:11434/v1",
           "model": "llama3.2:3b",
           "timeout_sec": 5,
           "max_answer_chars": 2000}
    cfg.update(over)
    return cfg


class _Resp:
    def __init__(self, body):
        self._body = body

    def read(self, n=-1):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _scripted_opener(script, seen):
    """Each call records the request payload and returns the next
    scripted message as the chat completion."""
    def opener(req, timeout=None):
        seen.append(json.loads(req.data.decode("utf-8")))
        msg = script.pop(0)
        body = json.dumps({"choices": [{"message": msg}]}).encode()
        return _Resp(body)
    return opener


def _tool_call_msg(path):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": "c1", "type": "function",
         "function": {"name": "read_file",
                      "arguments": json.dumps({"path": path})}}]}


class RunToolStdinTest(unittest.TestCase):
    def test_run_tool_gets_empty_stdin_and_clamped_timeout(self):
        captured = {}

        def fake_run(*args, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(
                args, 0, stdout=b"done", stderr=b"")

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(R.subprocess, "run", fake_run):
                out = R._run_oracle_tool(
                    "run",
                    {"command": "findstr /i x *.json",
                     "timeout_sec": "3600"},
                    base_dir=d)
        self.assertIn("exit=0", out)
        # The model asked for an hour; the clamp still owns the cap.
        self.assertEqual(captured.get("timeout"), 120)
        # A command that reads stdin must meet EOF at once, not sit
        # on the console's stdin for the whole timeout.
        self.assertIs(captured.get("stdin"), subprocess.DEVNULL)


class KeepAliveTest(unittest.TestCase):
    def test_keep_alive_default_on_ollama_endpoint(self):
        seen = []
        opener = _scripted_opener(
            [{"role": "assistant", "content": "ok"}], seen)
        R._inference_chat(_agent_cfg(),
                          [{"role": "user", "content": "hi"}],
                          None, opener, 5)
        self.assertEqual(seen[0].get("keep_alive"), "30m")

    def test_no_keep_alive_on_a_foreign_endpoint(self):
        seen = []
        opener = _scripted_opener(
            [{"role": "assistant", "content": "ok"}], seen)
        cfg = _agent_cfg(endpoint="https://api.example.com/v1")
        R._inference_chat(cfg, [{"role": "user", "content": "hi"}],
                          None, opener, 5)
        self.assertNotIn("keep_alive", seen[0])

    def test_explicit_keep_alive_wins(self):
        seen = []
        opener = _scripted_opener(
            [{"role": "assistant", "content": "ok"}], seen)
        cfg = _agent_cfg(endpoint="https://api.example.com/v1",
                         keep_alive="10m")
        R._inference_chat(cfg, [{"role": "user", "content": "hi"}],
                          None, opener, 5)
        self.assertEqual(seen[0].get("keep_alive"), "10m")


class WallClockTest(unittest.TestCase):
    def _drive(self, monotonic, script, progress):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "job-1.json")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"job_id": "job-1"}')
            full_script = [_tool_call_msg(target)] + script
            seen = []
            opener = _scripted_opener(full_script, seen)
            with mock.patch.object(R.time, "monotonic", monotonic):
                ans = R.ask_model_agent(
                    _agent_cfg(), "Summarize the jobs", "index text",
                    2000, opener=opener, base_dir=d, progress=progress)
        return ans, seen

    def test_wall_clock_forces_a_final_answer_without_tools(self):
        calls = {"n": 0}

        def fake_monotonic():
            calls["n"] += 1
            return 0.0 if calls["n"] == 1 else 9999.0

        progress = {}
        ans, seen = self._drive(
            fake_monotonic,
            [{"role": "assistant", "content": "One job ran."}],
            progress)
        self.assertEqual(ans.get("answer"), "One job ran.")
        self.assertEqual(ans.get("tool_rounds"), 1)
        self.assertEqual(len(seen), 2)
        # The forced final call must not offer tools again.
        self.assertNotIn("tools", seen[1])
        self.assertEqual(progress.get("step"),
                         "Writing the answer from what it has")

    def test_progress_reports_steps_while_working(self):
        progress = {}
        ans, seen = self._drive(
            lambda: 0.0,
            [{"role": "assistant", "content": "All done."}],
            progress)
        self.assertEqual(ans.get("answer"), "All done.")
        self.assertEqual(ans.get("tool_rounds"), 1)
        self.assertEqual(progress.get("step"), "Thinking (step 2)")


class PromptTest(unittest.TestCase):
    def test_prompt_ranks_run_last(self):
        self.assertIn("Never use run to", R.ASK_AGENT_SYSTEM)
        self.assertIn("Answer a summary", R.ASK_AGENT_SYSTEM)


class StatusEndpointTest(unittest.TestCase):
    def test_status_requires_the_token_and_reports_idle(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d, "shared_secret": "s" * 40,
                   "inference": {
                       "endpoint": "http://127.0.0.1:11434/v1",
                       "model": "llama3.2:3b"}}
            httpd = R.make_oracle_server(cfg, "127.0.0.1", 0, base_dir=d)
            port = httpd.socket.getsockname()[1]
            thread = threading.Thread(target=httpd.serve_forever,
                                      daemon=True)
            thread.start()
            self.addCleanup(httpd.shutdown)
            self.addCleanup(httpd.server_close)
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/status")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(cm.exception.code, 403)
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/status",
                headers={"X-Oracle-Token": httpd.oracle_token})
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read().decode())
            self.assertEqual(body.get("active"), False)
            self.assertIn("elapsed_sec", body)
            self.assertIn("step", body)

    def test_page_polls_status_while_working(self):
        page = R.oracle_page("tok", "llama3.2:3b", True)
        self.assertIn('"/status"', page)
        self.assertIn("clearInterval", page)
        self.assertIn("Working", page)


if __name__ == "__main__":
    unittest.main()
