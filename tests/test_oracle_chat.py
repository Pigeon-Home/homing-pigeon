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

    def test_numeric_retained_output_does_not_crash_the_chat(self):
        # From a simulation: one retained job stored stdout as a number
        # and another stored it as a list. Building the Oracle's context
        # used to raise TypeError before the model was asked.
        with tempfile.TemporaryDirectory() as d:
            kept = os.path.join(d, "retained")
            os.makedirs(kept)
            with open(os.path.join(kept, "job-num.json"), "w", encoding="utf-8") as fh:
                json.dump({"stdout": 5, "stderr": None, "kind": {"nope": True}}, fh)
            with open(os.path.join(kept, "job-list.json"), "w", encoding="utf-8") as fh:
                json.dump({"stdout": ["a", FLAG], "stderr": {"x": 1}}, fh)
            text = oracle_context(d)
            self.assertIn("job-num", text)
            self.assertIn("5", text)
            self.assertIn(FLAG, text)

            httpd = make_oracle_server(_cfg(d), "127.0.0.1", 0)
            port = httpd.socket.getsockname()[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(httpd.shutdown)
            self.addCleanup(httpd.server_close)

            def fake_ask(inf, question, output_text, max_chars, patterns=None,
                         opener=None, instructions=None):
                self.assertIn("5", output_text)
                return {"op": "ask", "rejected": "sanitization"}

            with mock.patch("runner.runner.ask_model", side_effect=fake_ask):
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/ask",
                    data=json.dumps({"question": "what happened?"}).encode(),
                    headers={
                        "Origin": f"http://127.0.0.1:{port}",
                        "Content-Type": "application/json",
                        "X-Oracle-Token": httpd.oracle_token,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    body = json.loads(resp.read().decode())
            self.assertEqual(body.get("rejected"), "sanitization")
            self.assertNotIn(FLAG, json.dumps(body))

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
                chat_path = os.path.join(d, "oracle-chat.jsonl")
                with open(chat_path, encoding="utf-8") as fh:
                    saved = fh.read()
                self.assertIn("what happened?", saved)
                self.assertIn("a job finished at noon", saved)

                code, body = post({"question": FLAG}, good)
                self.assertEqual(code, 200)
                parsed = json.loads(body)
                self.assertEqual(parsed.get("rejected"), "sanitization")
                self.assertNotIn(FLAG, body)
                with open(chat_path, encoding="utf-8") as fh:
                    saved = fh.read()
                self.assertNotIn(FLAG, saved)
                self.assertIn("[REDACTED:desktop_flag]", saved)

    def test_chat_log_rolls_before_it_can_fill_the_disk(self):
        from runner.runner import append_bounded_log, record_oracle_turn
        with tempfile.TemporaryDirectory() as d:
            record_oracle_turn(
                d, _cfg(d), "see " + FLAG,
                {"answer": "a credential was present", "model": "m"})
            with open(os.path.join(d, "oracle-chat.jsonl"),
                      encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn(FLAG, text)
            self.assertIn("[REDACTED:desktop_flag]", text)
            self.assertIn("a credential was present", text)
            path = os.path.join(d, "roll.txt")
            append_bounded_log(path, "a" * 80, max_bytes=100)
            append_bounded_log(path, "b" * 80, max_bytes=100)
            self.assertTrue(os.path.isfile(path + ".1"))
            self.assertLess(
                os.path.getsize(path) + os.path.getsize(path + ".1"), 400)

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


class OracleWindowDiagnosticsTest(unittest.TestCase):
    """--oracle says which config it loaded and whether a model is set."""

    def _run_window(self, cfg, cfg_path):
        from unittest import mock
        from runner.runner import oracle_window

        class FakeServer:
            socket = type("S", (), {"getsockname": lambda self: ("127.0.0.1", 11436)})()
            closed = False

            def serve_forever(self):
                raise KeyboardInterrupt

            def server_close(self):
                self.closed = True

        buf = StringIO()
        with tempfile.TemporaryDirectory() as d:
            cfg = dict(cfg, base_dir=d)
            with mock.patch("runner.runner.make_oracle_server", return_value=FakeServer()), \
                 redirect_stdout(buf):
                code = oracle_window(cfg, cfg_path=cfg_path, open_browser=False)
        return code, buf.getvalue()

    def test_prints_config_path_and_model(self):
        cfg_path = os.path.join("some", "dir", "my-config.json")
        code, out = self._run_window(_cfg("/tmp/x"), cfg_path)
        self.assertEqual(code, 0)
        self.assertIn("Config: %s" % os.path.abspath(cfg_path), out)
        self.assertIn("Inference: local model llama3.2:3b", out)
        self.assertIn("does not poll the mailbox", out)

    def test_prints_when_inference_missing(self):
        cfg = {"base_dir": "/tmp/x"}
        code, out = self._run_window(cfg, None)
        self.assertEqual(code, 0)
        self.assertNotIn("Config:", out)
        self.assertIn("Inference: not configured", out)

    def test_page_tells_stale_sessions_to_reload(self):
        from runner.runner import oracle_page
        page = oracle_page("tok", "llama3.2:3b", True)
        self.assertIn("The chat session expired. Reload the page", page)


class CleanShutdownTest(unittest.TestCase):
    """Ctrl+C on the frozen exe exits quietly, not as 'Failed to execute script'."""

    def test_keyboard_interrupt_exits_quietly(self):
        from unittest import mock
        from runner.runner import _run

        with mock.patch("runner.runner.main", side_effect=KeyboardInterrupt):
            with self.assertRaises(SystemExit) as cm:
                _run()
        self.assertEqual(cm.exception.code, 0)

    def test_normal_exit_code_passes_through(self):
        from unittest import mock
        from runner.runner import _run

        with mock.patch("runner.runner.main", return_value=3):
            with self.assertRaises(SystemExit) as cm:
                _run()
        self.assertEqual(cm.exception.code, 3)


class BaseDirForTest(unittest.TestCase):
    """State follows the config file, not the user running it."""

    def test_explicit_base_dir_wins(self):
        from runner.runner import _base_dir_for
        self.assertEqual(
            _base_dir_for({"base_dir": "/srv/pigeon"}, "/etc/pigeon/config.json"),
            "/srv/pigeon")

    def test_config_dir_is_default(self):
        from runner.runner import _base_dir_for
        with tempfile.TemporaryDirectory() as d:
            cfg_path = os.path.join(d, "config.json")
            self.assertEqual(_base_dir_for({}, cfg_path), d)

    def test_relative_config_path_resolves_against_cwd(self):
        import os
        from runner.runner import _base_dir_for
        self.assertEqual(
            _base_dir_for({}, "config.json"),
            os.path.dirname(os.path.abspath("config.json")))

    def test_home_fallback_when_no_config_path(self):
        import os
        from runner.runner import _base_dir_for
        self.assertEqual(
            _base_dir_for({}),
            os.path.join(os.path.expanduser("~"), ".homing-pigeon"))

    def test_blank_base_dir_falls_through(self):
        from runner.runner import _base_dir_for
        with tempfile.TemporaryDirectory() as d:
            cfg_path = os.path.join(d, "config.json")
            self.assertEqual(_base_dir_for({"base_dir": "   "}, cfg_path), d)

    def test_same_config_same_state_for_any_user(self):
        # The Windows failure: the service runs as SYSTEM, the chat as the
        # user. expanduser("~") differs per user, so the old default split
        # one config into two state dirs. The config path does not move.
        import os
        from unittest import mock
        from runner.runner import _base_dir_for
        cfg_path = "C:\\Users\\DRU\\.homing-pigeon\\config.json"
        with mock.patch("os.path.expanduser", return_value="C:\\Windows\\System32\\config\\systemprofile"):
            as_system = _base_dir_for({}, cfg_path)
        with mock.patch("os.path.expanduser", return_value="C:\\Users\\DRU"):
            as_user = _base_dir_for({}, cfg_path)
        self.assertEqual(as_system, as_user)
        self.assertEqual(as_user, os.path.dirname(os.path.abspath(cfg_path)))

    def test_oracle_window_passes_resolved_base_to_server(self):
        from unittest import mock
        from runner.runner import oracle_window

        class FakeServer:
            socket = type("S", (), {"getsockname": lambda self: ("127.0.0.1", 11436)})()
            closed = False

            def serve_forever(self):
                raise KeyboardInterrupt

            def server_close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as d:
            cfg_path = os.path.join(d, "svc", "config.json")
            os.makedirs(os.path.dirname(cfg_path))
            with open(cfg_path, "w") as fh:
                json.dump({"base_dir": d}, fh)
            with mock.patch("runner.runner.make_oracle_server",
                            return_value=FakeServer()) as made:
                oracle_window({"base_dir": d}, cfg_path=cfg_path,
                              open_browser=False)
        made.assert_called_once()
        self.assertEqual(made.call_args.kwargs.get("base_dir"), d)


class OracleContextSummaryTest(unittest.TestCase):
    """The Oracle gets kind, script, status, and time — not just output."""

    def _write(self, d, job_id, payload):
        import time
        os.makedirs(os.path.join(d, "retained"), exist_ok=True)
        p = os.path.join(d, "retained", job_id + ".json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        # newest first ordering is by mtime; stagger them
        ts = time.time() - len(os.listdir(os.path.join(d, "retained")))
        os.utime(p, (ts, ts))

    def test_summary_carries_kind_script_status_time(self):
        from runner.runner import oracle_context
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "job-1", {
                "job_id": "job-1", "kind": "exec",
                "script": "Get-Date; Write-Output hello",
                "stdout": "hello\n", "stderr": "",
                "exit_code": 0, "timed_out": False,
                "saved_at": 1760572271,
            })
            ctx = oracle_context(d)
        self.assertIn("job job-1 (exec, exit code 0,", ctx)
        self.assertIn("script: Get-Date; Write-Output hello", ctx)
        self.assertIn("output:\nhello", ctx)

    def test_old_records_without_new_fields_degrade_gracefully(self):
        from runner.runner import oracle_context
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "job-9", {"job_id": "job-9", "stdout": "x"})
            ctx = oracle_context(d)
        self.assertIn("job job-9 (unknown, status unknown, time unknown)", ctx)
        self.assertNotIn("script:", ctx)

    def test_timed_out_status(self):
        from runner.runner import _retained_job_summary
        s = _retained_job_summary({"timed_out": True, "exit_code": -1}, "j")
        self.assertIn("timed out", s)

    def test_output_still_capped(self):
        from runner.runner import oracle_context
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "big", {
                "job_id": "big", "kind": "exec",
                "script": "s" * 2000, "stdout": "o" * 5000,
                "exit_code": 0, "saved_at": 1,
            })
            ctx = oracle_context(d, max_chars=500)
        self.assertLessEqual(len(ctx), 500)

    def test_system_prompt_forbids_invented_ids(self):
        from runner.runner import ASK_SYSTEM
        self.assertIn("Never invent", ASK_SYSTEM)


class OracleLogTailTest(unittest.TestCase):
    """The Oracle can see the runner log, so it stops inventing log events."""

    def _write_log(self, d, lines):
        p = os.path.join(d, "runner.log")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return p

    def test_tail_returns_last_lines(self):
        from runner.runner import _runner_log_tail
        with tempfile.TemporaryDirectory() as d:
            self._write_log(d, [f"line {i}" for i in range(50)])
            tail = _runner_log_tail(d)
        self.assertIn("line 49", tail)
        self.assertNotIn("line 0\n", tail.split("\n")[0] if "\n" in tail else tail)
        self.assertLessEqual(len(tail), 2000)

    def test_tail_missing_log_is_empty(self):
        from runner.runner import _runner_log_tail
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_runner_log_tail(d), "")

    def test_tail_bad_base_dir_is_empty(self):
        from runner.runner import _runner_log_tail
        self.assertEqual(_runner_log_tail(None), "")
        self.assertEqual(_runner_log_tail(5), "")

    def test_context_includes_log_section(self):
        from runner.runner import oracle_context
        with tempfile.TemporaryDirectory() as d:
            self._write_log(d, [
                "2026-10-16 11:40:05 [ERROR] poll cycle failed: auth bad",
                "2026-10-16 11:40:06 [INFO] retrying",
            ])
            ctx = oracle_context(d)
        self.assertIn("Recent runner log", ctx)
        self.assertIn("poll cycle failed: auth bad", ctx)

    def test_context_includes_log_even_without_retained_dir(self):
        from runner.runner import oracle_context
        with tempfile.TemporaryDirectory() as d:
            self._write_log(d, ["2026-10-16 11:40:05 [ERROR] boom"])
            ctx = oracle_context(d)
        self.assertIn("(no job output retained yet)", ctx)
        self.assertIn("boom", ctx)

    def test_system_prompt_describes_log_section(self):
        from runner.runner import ASK_SYSTEM
        self.assertIn("Recent runner log", ASK_SYSTEM)
        self.assertIn("cannot", ASK_SYSTEM)


if __name__ == "__main__":
    unittest.main(verbosity=2)
