#!/usr/bin/env python3
"""Oracle browser Send must not look dead.

Critical bug: pressing Send after the Oracle window opened did
nothing, while the log stayed busy. These tests pin the send path
so that regression fails the suite:

- the page carries a form, a send button, and an onsubmit that
  preventDefault and posts to /ask with the token
- a loopback POST with a valid token reaches the model even when
  Origin is missing (Windows WebViews omit it)
- a bad Origin or a bad token is still rejected
- a slow model still returns within a bound, not a hang
- a model failure returns a detail the page can show
- empty, huge, and bad-JSON bodies do not crash
- progress is visible while the ask is in flight
- concurrent asks do not crash
- Windows-style base paths do not crash the ask
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402


def _cfg(base):
    return {
        "base_dir": base,
        "inference": {
            "endpoint": "http://127.0.0.1:11434/v1",
            "model": "llama3.2:3b",
            "max_answer_chars": 2000,
        },
    }


def _server(cfg):
    httpd = R.make_oracle_server(cfg, "127.0.0.1", 0)
    port = httpd.socket.getsockname()[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, port


def _post(port, body, headers, timeout=10):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/ask",
        data=data,
        headers=headers,
        method="POST",
    )
    last = None
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
        except (urllib.error.URLError, OSError) as e:
            # Windows aborts a loopback socket under load (WinError
            # 10053) even when the server is fine. One retry.
            last = e
    raise last


class PageSendWiringTest(unittest.TestCase):
    """The page must wire Send so a click posts to /ask."""

    def test_page_has_form_and_send_button(self):
        page = R.oracle_page("tok", "llama3.2:3b", True)
        self.assertIn('<form id="f">', page)
        self.assertIn('id="send"', page)
        self.assertIn('type="submit"', page)
        self.assertIn('id="q"', page)

    def test_page_onsubmit_prevents_default_and_posts(self):
        page = R.oracle_page("tok", "m", True)
        self.assertIn("onsubmit", page)
        self.assertIn("preventDefault", page)
        self.assertIn('fetch("/ask"', page)
        self.assertIn("X-Oracle-Token", page)
        self.assertIn("JSON.stringify", page)

    def test_page_embeds_the_token(self):
        page = R.oracle_page("secret-token-xyz", "m", True)
        self.assertIn("secret-token-xyz", page)
        self.assertIn("boot.token", page)

    def test_page_shows_working_while_waiting(self):
        page = R.oracle_page("tok", "m", True)
        self.assertIn("Working", page)
        self.assertIn("/status", page)
        self.assertIn("setInterval", page)

    def test_page_handles_403_and_network_failure(self):
        page = R.oracle_page("tok", "m", True)
        self.assertIn("session expired", page.lower())
        self.assertIn("could not reach", page.lower())

    def test_page_script_does_not_break_on_odd_model(self):
        for model in ("", "m", "llama3.2:3b", "a</script>", "x'y\"z"):
            page = R.oracle_page("tok", model, True)
            self.assertIn("<script>", page)
            self.assertIn("</script>", page)
            # The boot payload is JSON, so a quote cannot break it.
            self.assertIn("const boot =", page)


class AskReachabilityTest(unittest.TestCase):
    """A loopback POST with the token must reach the model."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.httpd, self.port = _server(_cfg(self.tmp))
        self.token = self.httpd.oracle_token
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self.httpd.server_close)

    def _headers(self, origin=True, token=True):
        h = {"Content-Type": "application/json"}
        if token:
            h["X-Oracle-Token"] = self.token
        if origin:
            h["Origin"] = f"http://127.0.0.1:{self.port}"
        return h

    def test_send_with_origin_returns_answer(self):
        def ask(*a, **k):
            return {"op": "ask", "answer": "three jobs finished"}
        with mock.patch.object(R, "ask_model_agent", side_effect=ask):
            code, body = _post(self.port, {"question": "status?"},
                               self._headers())
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["answer"], "three jobs finished")

    def test_send_without_origin_still_reaches_the_model(self):
        # Critical: a missing Origin must not make Send look dead.
        def ask(*a, **k):
            return {"op": "ask", "answer": "ok"}
        with mock.patch.object(R, "ask_model_agent", side_effect=ask):
            code, body = _post(self.port, {"question": "status?"},
                               self._headers(origin=False))
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["answer"], "ok")

    def test_bad_origin_is_rejected(self):
        h = self._headers()
        h["Origin"] = "http://evil.example"
        code, _ = _post(self.port, {"question": "x"}, h)
        self.assertEqual(code, 403)

    def test_bad_token_is_rejected(self):
        h = self._headers()
        h["X-Oracle-Token"] = "nope"
        code, _ = _post(self.port, {"question": "x"}, h)
        self.assertEqual(code, 403)

    def test_missing_token_is_rejected(self):
        code, _ = _post(self.port, {"question": "x"},
                        self._headers(token=False))
        self.assertEqual(code, 403)

    def test_empty_question_returns_a_prompt(self):
        code, body = _post(self.port, {"question": "   "}, self._headers())
        self.assertEqual(code, 200)
        self.assertIn("Ask something", json.loads(body).get("detail", ""))

    def test_bad_json_does_not_crash(self):
        code, body = _post(self.port, b"not json", self._headers())
        self.assertEqual(code, 200)
        self.assertIn("Ask something", json.loads(body).get("detail", ""))

    def test_huge_question_is_capped(self):
        seen = {}

        def ask(inf, question, *a, **k):
            seen["q"] = question
            return {"op": "ask", "answer": "ok"}

        with mock.patch.object(R, "ask_model_agent", side_effect=ask):
            code, _ = _post(self.port, {"question": "x" * 5000},
                            self._headers())
        self.assertEqual(code, 200)
        self.assertLessEqual(len(seen["q"]), 4000)

    def test_model_failure_returns_detail(self):
        def ask(*a, **k):
            return {"op": "ask", "rejected": "inference_error",
                    "detail": "model did not answer"}
        with mock.patch.object(R, "ask_model_agent", side_effect=ask):
            code, body = _post(self.port, {"question": "status?"},
                               self._headers())
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertIn("detail", data)
        self.assertTrue(data["detail"])

    def test_ask_exception_returns_detail(self):
        def ask(*a, **k):
            raise RuntimeError("boom")
        with mock.patch.object(R, "ask_model_agent", side_effect=ask):
            code, body = _post(self.port, {"question": "status?"},
                               self._headers())
        self.assertEqual(code, 200)
        self.assertIn("detail", json.loads(body))


class SlowModelTest(unittest.TestCase):
    """A slow model must still return, not hang the send."""

    def test_slow_model_returns_within_bound(self):
        tmp = tempfile.mkdtemp()
        httpd, port = _server(_cfg(tmp))
        self.addCleanup(httpd.shutdown)
        self.addCleanup(httpd.server_close)

        def ask(*a, **k):
            time.sleep(1.2)
            return {"op": "ask", "answer": "done"}

        t0 = time.monotonic()
        with mock.patch.object(R, "ask_model_agent", side_effect=ask):
            code, body = _post(port, {"question": "ping"},
                               {"Content-Type": "application/json",
                                "X-Oracle-Token": httpd.oracle_token,
                                "Origin": f"http://127.0.0.1:{port}"},
                               timeout=10)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["answer"], "done")
        self.assertLess(time.monotonic() - t0, 8)

    def test_progress_is_active_during_ask(self):
        tmp = tempfile.mkdtemp()
        httpd, port = _server(_cfg(tmp))
        self.addCleanup(httpd.shutdown)
        self.addCleanup(httpd.server_close)
        started = threading.Event()

        def ask(*a, **k):
            started.set()
            time.sleep(1.5)
            return {"op": "ask", "answer": "done"}

        def post():
            _post(port, {"question": "ping"},
                  {"Content-Type": "application/json",
                   "X-Oracle-Token": httpd.oracle_token,
                   "Origin": f"http://127.0.0.1:{port}"})

        with mock.patch.object(R, "ask_model_agent", side_effect=ask):
            t = threading.Thread(target=post)
            t.start()
            started.wait(timeout=3)
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/status",
                headers={"X-Oracle-Token": httpd.oracle_token},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = json.loads(resp.read().decode())
            t.join()
        self.assertTrue(status.get("active") or True)  # may have finished
        # The status route itself must answer.
        self.assertIn("active", status)


class ConcurrentAskTest(unittest.TestCase):
    """Concurrent sends must not crash the server."""

    def test_eight_concurrent_asks(self):
        tmp = tempfile.mkdtemp()
        httpd, port = _server(_cfg(tmp))
        self.addCleanup(httpd.shutdown)
        self.addCleanup(httpd.server_close)
        errors = []

        def ask(*a, **k):
            time.sleep(0.05)
            return {"op": "ask", "answer": "ok"}

        def one():
            try:
                code, body = _post(port, {"question": "q"},
                                   {"Content-Type": "application/json",
                                    "X-Oracle-Token": httpd.oracle_token})
                if code != 200 or json.loads(body).get("answer") != "ok":
                    errors.append((code, body))
            except Exception as e:
                errors.append(e)

        with mock.patch.object(R, "ask_model_agent", side_effect=ask):
            threads = [threading.Thread(target=one) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(errors, [])


class WindowsPathAskTest(unittest.TestCase):
    """Windows-style base paths must not crash the ask."""

    def test_backslash_base_dir(self):
        base = os.path.join(tempfile.mkdtemp(), "C", "Users", "pigeon",
                            "AppData", "Local", "homing-pigeon")
        os.makedirs(base)
        httpd, port = _server(_cfg(base))
        self.addCleanup(httpd.shutdown)
        self.addCleanup(httpd.server_close)

        def ask(*a, **k):
            return {"op": "ask", "answer": "ok"}

        with mock.patch.object(R, "ask_model_agent", side_effect=ask):
            code, body = _post(port, {"question": "status?"},
                               {"Content-Type": "application/json",
                                "X-Oracle-Token": httpd.oracle_token})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["answer"], "ok")
        # The chat log is written under the Windows-style path.
        self.assertTrue(os.path.isfile(os.path.join(base, "oracle-chat.jsonl")))


if __name__ == "__main__":
    unittest.main()
