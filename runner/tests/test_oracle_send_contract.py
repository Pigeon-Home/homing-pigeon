#!/usr/bin/env python3
"""Critical-path contract for the Oracle send button.

The chat box is a textarea. A bare Enter does not submit a form, so
pressing send used to do nothing and the runner log stayed quiet.
Clicking Send disabled the button with no pending state, so a slow
model looked like a hang while the log printed "ask: calling model".

These tests pin the contract so that class of silent failure fails
the suite. No browser, no live model.
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

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import make_oracle_server, oracle_page  # noqa: E402


SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"


def _cfg(base):
    return {
        "base_dir": base,
        "shared_secret": SECRET,
        "inference": {
            "endpoint": "http://127.0.0.1:11434/v1",
            "model": "llama3.2:3b",
            "max_answer_chars": 200,
            "timeout_sec": 5,
        },
    }


def _script(page: str) -> str:
    start = page.find("<script>")
    end = page.rfind("</script>")
    if start < 0 or end < 0:
        return ""
    return page[start:end]


class OracleSendContractTest(unittest.TestCase):
    """The page must send on Enter and must not look dead while waiting."""

    def setUp(self):
        self.page = oracle_page("tok-abc", "llama3.2:3b", True)
        self.script = _script(self.page)

    def test_chat_box_is_a_textarea(self):
        # The bug exists because the box is a textarea. If someone
        # changes it to an input, Enter submits natively and this
        # contract can be revisited. Until then the handler is required.
        self.assertIn('<textarea id="q"', self.page)
        self.assertIn('<button id="send" type="submit">', self.page)
        self.assertIn('<form id="f">', self.page)

    def test_enter_submits_and_shift_enter_does_not(self):
        self.assertIn('e.key === "Enter"', self.script)
        self.assertIn("!e.shiftKey", self.script)
        self.assertIn("e.preventDefault()", self.script)
        self.assertIn("requestSubmit()", self.script)
        # The handler must be on the textarea, not only the form.
        self.assertIn('q.addEventListener("keydown"', self.script)

    def test_thinking_line_is_shown_before_the_fetch(self):
        # Order matters. The pending line must be added before fetch,
        # or a slow model looks like a hang again.
        thinking = self.script.find('add("Oracle", "Working')
        fetch = self.script.find('fetch("/ask"')
        self.assertGreater(thinking, 0)
        self.assertGreater(fetch, thinking)

    def test_button_is_disabled_while_waiting_and_reenabled_after(self):
        self.assertIn("send.disabled = true", self.script)
        self.assertIn("send.disabled = false", self.script)
        # Re-enable must be outside the try, so a thrown fetch or a
        # bad JSON body cannot leave the button dead forever.
        try_at = self.script.find("try {")
        disable = self.script.find("send.disabled = true")
        enable = self.script.rfind("send.disabled = false")
        catch = self.script.find("catch")
        self.assertLess(disable, try_at)
        self.assertGreater(enable, catch)

    def test_pending_line_is_replaced_not_left_forever(self):
        self.assertIn("pending.remove()", self.script)
        self.assertIn("data.answer", self.script)
        self.assertIn("data.detail", self.script)
        self.assertIn("The page could not reach the local Oracle.", self.script)

    def test_empty_send_is_a_no_op(self):
        # Whitespace-only must not disable the button or hit the model.
        self.assertIn("q.value.trim()", self.script)
        self.assertIn("if (!text || send.disabled) return", self.script)

    def test_fetch_posts_to_ask_with_the_token(self):
        self.assertIn('fetch("/ask"', self.script)
        self.assertIn('"X-Oracle-Token": boot.token', self.script)
        self.assertIn("JSON.stringify({question: text})", self.script)
        self.assertIn("method: \"POST\"", self.script)

    def test_boot_payload_is_json_and_escapes_lt(self):
        page = oracle_page("tok<script>", "model</script>", True)
        self.assertNotIn("<script>", page.split("const boot =", 1)[1].split(";", 1)[0])
        self.assertIn("\\u003c", page)
        self.assertIn("tok", page)

    def test_unready_page_still_has_the_send_contract(self):
        page = oracle_page("tok", "", False)
        script = _script(page)
        self.assertIn("No loopback model is configured", page)
        self.assertIn('e.key === "Enter"', script)
        self.assertIn("Working", script)
        self.assertIn("requestSubmit()", script)

    def test_page_does_not_use_innerhtml(self):
        # A future "fix" that injects the answer with innerHTML would
        # re-open the injection hole the chat page closed.
        self.assertNotIn("innerHTML", self.page)
        self.assertIn("textContent", self.page)


class OracleSendServerTest(unittest.TestCase):
    """The /ask handler must always answer. A bad or slow model must
    not leave the browser waiting with no body."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.httpd = make_oracle_server(_cfg(self.tmp), "127.0.0.1", 0)
        self.port = self.httpd.socket.getsockname()[1]
        self.token = self.httpd.oracle_token
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self.httpd.server_close)

    def _post(self, question="status?", headers=None, raw=None):
        hdrs = {
            "Origin": f"http://127.0.0.1:{self.port}",
            "Content-Type": "application/json",
            "X-Oracle-Token": self.token,
        }
        if headers:
            hdrs.update(headers)
        data = raw if raw is not None else json.dumps({"question": question}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/ask",
            data=data, headers=hdrs, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
        except (ConnectionAbortedError, ConnectionResetError,
                BrokenPipeError, TimeoutError, urllib.error.URLError,
                OSError):
            # Windows delivers WinError 10053, and sometimes 10038,
            # instead of the status when the host aborts a localhost
            # socket that arrived before accept. urllib wraps that
            # in URLError. A few fresh requests; a last abort is a
            # real failure and must still raise.
            last = None
            for _ in range(4):
                time.sleep(0.05)
                req = urllib.request.Request(
                    f"http://127.0.0.1:{self.port}/ask",
                    data=data, headers=hdrs, method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        return resp.status, resp.read().decode()
                except urllib.error.HTTPError as e:
                    return e.code, e.read().decode()
                except (ConnectionAbortedError, ConnectionResetError,
                        BrokenPipeError, TimeoutError,
                        urllib.error.URLError, OSError) as exc:
                    last = exc
            raise last

    def test_good_ask_returns_json_answer(self):
        with mock.patch("runner.runner.ask_model_agent",
                        return_value={"op": "ask", "answer": "quiet"}):
            code, body = self._post("what is going on")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["answer"], "quiet")

    def test_model_raise_returns_json_not_a_hang(self):
        def boom(*a, **k):
            raise RuntimeError("model exploded")
        with mock.patch("runner.runner.ask_model_agent", side_effect=boom):
            code, body = self._post()
        self.assertEqual(code, 200)
        parsed = json.loads(body)
        self.assertEqual(parsed.get("rejected"), "inference_error")
        self.assertIn("detail", parsed)

    def test_non_dict_model_return_is_rejected_not_leaked(self):
        for bad in (None, "string", 1, ["x"]):
            with mock.patch("runner.runner.ask_model_agent", return_value=bad):
                code, body = self._post()
            self.assertEqual(code, 200, bad)
            parsed = json.loads(body)
            self.assertIsInstance(parsed, dict)
            self.assertNotIn("answer", parsed)

    def test_slow_model_still_returns_a_body(self):
        def slow(*a, **k):
            time.sleep(0.4)
            return {"op": "ask", "answer": "late"}
        t0 = time.time()
        with mock.patch("runner.runner.ask_model_agent", side_effect=slow):
            code, body = self._post()
        self.assertLess(time.time() - t0, 5)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["answer"], "late")

    def test_empty_and_whitespace_questions_are_rejected_quickly(self):
        for q in ("", "   ", "\n\n"):
            t0 = time.time()
            code, body = self._post(q)
            self.assertLess(time.time() - t0, 2)
            self.assertEqual(code, 200)
            self.assertIn("Ask something first", body)

    def test_missing_origin_is_answered(self):
        # Superseded contract (feed560): a missing Origin used to be
        # a 403, and on some Windows WebViews and same-origin POSTs
        # that made Send look dead. Loopback Host + valid token is
        # the gate; a missing Origin is answered.
        with mock.patch("runner.runner.ask_model_agent",
                        return_value={"op": "ask", "answer": "quiet"}):
            code, body = self._post(headers={"Origin": ""})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["answer"], "quiet")

    def test_foreign_origin_is_forbidden(self):
        # A PRESENT Origin that is not loopback is still rejected.
        code, body = self._post(headers={"Origin": "http://evil.example"})
        self.assertEqual(code, 403)
        self.assertIn("forbidden", body)

    def test_missing_or_wrong_token_is_forbidden(self):
        code, _ = self._post(headers={"X-Oracle-Token": ""})
        self.assertEqual(code, 403)
        code, _ = self._post(headers={"X-Oracle-Token": "nope"})
        self.assertEqual(code, 403)

    def test_windows_host_and_origin_variants_are_accepted(self):
        # Windows browsers send these shapes. A parse bug here makes
        # Send return 403, which the page used to swallow as silence.
        variants = [
            {"Host": f"127.0.0.1:{self.port}",
             "Origin": f"http://127.0.0.1:{self.port}"},
            {"Host": f"localhost:{self.port}",
             "Origin": f"http://localhost:{self.port}"},
            {"Host": f"[::1]:{self.port}",
             "Origin": f"http://[::1]:{self.port}"},
            {"Host": "127.0.0.1",
             "Origin": f"http://127.0.0.1:{self.port}"},
        ]
        with mock.patch("runner.runner.ask_model_agent",
                        return_value={"op": "ask", "answer": "ok"}):
            for hdrs in variants:
                code, body = self._post(headers=hdrs)
                self.assertEqual(code, 200, hdrs)
                self.assertEqual(json.loads(body)["answer"], "ok")

    def test_bad_json_body_is_a_json_rejection_not_a_crash(self):
        code, body = self._post(raw=b"not-json")
        self.assertEqual(code, 200)
        self.assertIn("Ask something first", body)

    def test_non_string_question_is_rejected(self):
        code, body = self._post(raw=json.dumps({"question": 1}).encode())
        self.assertEqual(code, 200)
        self.assertIn("Ask something first", body)

    def test_oversized_body_is_rejected(self):
        code, _ = self._post(raw=b"x" * 9000)
        self.assertEqual(code, 400)

    def test_wrong_path_is_not_found(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/send",
            data=b"{}", method="POST",
            headers={"Origin": f"http://127.0.0.1:{self.port}",
                     "X-Oracle-Token": self.token},
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("expected 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_concurrent_asks_all_return(self):
        results = []
        errors = []

        def one(i):
            try:
                code, body = self._post(f"q{i}")
                results.append((code, json.loads(body).get("answer")))
            except Exception as exc:
                errors.append(repr(exc))

        with mock.patch("runner.runner.ask_model_agent",
                        return_value={"op": "ask", "answer": "ok"}):
            threads = [threading.Thread(target=one, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(15)
        self.assertFalse(any(t.is_alive() for t in threads), errors)
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 8, errors)
        self.assertTrue(all(code == 200 for code, _ in results), results)
        self.assertTrue(all(ans == "ok" for _, ans in results), results)


if __name__ == "__main__":
    unittest.main(verbosity=2)
