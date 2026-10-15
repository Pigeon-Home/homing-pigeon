#!/usr/bin/env python3
"""Loopback Oracle chat. No browser, no live model."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from io import StringIO
from contextlib import redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import (  # noqa: E402
    make_oracle_server,
    oracle_context,
    oracle_page,
    oracle_window,
)


FLAG = "FLAG-CRED-9f3c2a7e1b"


def _cfg(base):
    return {
        "base_dir": base,
        "shared_secret": "not-in-the-page-" + "ab" * 20,
        "mailbox_password": "mailbox-secret-should-not-appear",
        "owner_instructions": "Desktop/flag.txt is a password. Do not quote it.",
        "inference": {
            "endpoint": "http://127.0.0.1:11434/v1",
            "model": "llama3.2:3b",
            "max_answer_chars": 200,
            "timeout_sec": 5,
        },
        "redact_patterns_extra": {
            "desktop_flag": r"FLAG-CRED-[0-9a-f]{10}",
        },
    }


class OracleChatTest(unittest.TestCase):
    def test_refuses_a_non_loopback_bind(self):
        with self.assertRaises(ValueError):
            make_oracle_server({}, "0.0.0.0", 0)

    def test_context_is_recent_job_output_only(self):
        with tempfile.TemporaryDirectory() as d:
            kept = os.path.join(d, "retained")
            os.makedirs(kept)
            with open(os.path.join(kept, "job-1.json"), "w", encoding="utf-8") as fh:
                json.dump({"job_id": "job-1", "kind": "exec",
                           "stdout": "clock is noon\n"}, fh)
            with open(os.path.join(kept, "../evil.json"), "w", encoding="utf-8") as fh:
                fh.write("{}")
            text = oracle_context(d)
        self.assertIn("job-1", text)
        self.assertIn("clock is noon", text)
        self.assertNotIn("evil", text)

    def test_page_has_no_secret_and_no_html_injection(self):
        page = oracle_page("tok", "llama3.2:3b", True)
        self.assertNotIn("mailbox-secret", page)
        self.assertNotIn("innerHTML", page)
        self.assertIn("textContent", page)
        self.assertIn("Ask what it thinks is going on", page)

    def test_ask_needs_the_token_and_stays_on_loopback(self):
        with tempfile.TemporaryDirectory() as d:
            kept = os.path.join(d, "retained")
            os.makedirs(kept)
            with open(os.path.join(kept, "job-1.json"), "w", encoding="utf-8") as fh:
                json.dump({"stdout": "clock is noon\n", "kind": "exec"}, fh)
            httpd = make_oracle_server(_cfg(d), "127.0.0.1", 0)
            port = httpd.socket.getsockname()[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(httpd.shutdown)
            self.addCleanup(httpd.server_close)
            token = httpd.oracle_token
            seen = {}

            def fake_ask(inf, question, output_text, max_chars, patterns=None,
                         opener=None, instructions=None):
                seen["question"] = question
                seen["output"] = output_text
                seen["instructions"] = instructions
                if FLAG in (question or "") or FLAG in (output_text or ""):
                    return {"op": "ask", "rejected": "sanitization"}
                return {"op": "ask", "answer": "a job finished at noon"}

            with mock.patch("runner.runner.ask_model", side_effect=fake_ask):
                page = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/", timeout=5).read().decode()
                self.assertNotIn("mailbox-secret-should-not-appear", page)
                self.assertNotIn(_cfg(d)["shared_secret"], page)
                self.assertIn(token, page)

                def post(body, headers):
                    req = urllib.request.Request(
                        f"http://127.0.0.1:{port}/ask",
                        data=json.dumps(body).encode(),
                        headers=headers,
                        method="POST",
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            return resp.status, resp.read().decode()
                    except urllib.error.HTTPError as e:
                        return e.code, e.read().decode()

                origin = {"Origin": f"http://127.0.0.1:{port}",
                          "Content-Type": "application/json"}
                code, _ = post({"question": "what happened?"}, origin)
                self.assertEqual(code, 403)

                bad = dict(origin)
                bad["Origin"] = "http://evil.example"
                bad["X-Oracle-Token"] = token
                code, _ = post({"question": "what happened?"}, bad)
                self.assertEqual(code, 403)

                good = dict(origin)
                good["X-Oracle-Token"] = token
                code, body = post({"question": "what happened?"}, good)
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(body)["answer"],
                                 "a job finished at noon")
                self.assertIn("clock is noon", seen["output"])
                self.assertIn("password", seen["instructions"])

                code, body = post({"question": FLAG}, good)
                self.assertEqual(code, 200)
                parsed = json.loads(body)
                self.assertEqual(parsed.get("rejected"), "sanitization")
                self.assertNotIn(FLAG, body)

    def test_oracle_flag_does_not_need_a_mailbox(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"inference": {
                    "endpoint": "http://127.0.0.1:11434/v1",
                    "model": "m",
                }, "base_dir": d}, fh)
            with mock.patch("runner.runner.oracle_window", return_value=0) as win, \
                 mock.patch("runner.runner.ensure_inference_ready"), \
                 mock.patch("runner.runner.update_llama_from_config"), \
                 mock.patch("sys.argv", ["runner", "--config", path, "--oracle"]):
                from runner.runner import main
                self.assertEqual(main(), 0)
            win.assert_called_once()

    def test_startup_without_a_workspace_does_not_raise(self):
        from runner.runner import log_startup

        class Args:
            dry_run = True
            no_send = False
            once = True
            verbose = False

        buf = StringIO()
        with redirect_stdout(buf):
            log_startup(
                {"mailbox_user": "a@b.c", "judge": "enforce",
                 "max_result_view": "redacted"},
                Args(), "/tmp/base")
        self.assertIn("workspace_root is not set", buf.getvalue())
        self.assertNotIn("Traceback", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
