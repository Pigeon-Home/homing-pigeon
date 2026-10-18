#!/usr/bin/env python3
"""Oracle page script must stay valid JavaScript.

Critical bug (2026-10-18): oracle_page emitted a raw newline inside a
JS string literal. The entire <script> became a SyntaxError, the
onsubmit handler never attached, and pressing Send did nothing.
The server log stayed quiet or only showed a plain form POST.

These tests lock the contract:
- The emitted script parses under node --check for many boot payloads.
- Common ways to break a page script are rejected statically
  (raw newlines inside string literals, unescaped </script>,
  unescaped quotes that split a string, token leaking into the URL).
- The send path is structurally present (form, type=submit, onsubmit,
  preventDefault, fetch /ask, X-Oracle-Token).
- Special characters in the token or model name cannot break the script.
- Ready and not-ready pages both produce valid scripts.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

NODE = shutil.which("node")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import oracle_page  # noqa: E402


def _script(page: str) -> str:
    start = page.find("<script>")
    end = page.find("</script>")
    if start < 0 or end < start:
        raise AssertionError("page has no <script> block")
    return page[start + 8:end]


def _check_js(js: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", "--check", "-"],
        input=js.encode("utf-8"),
        capture_output=True,
    )


class OraclePageScriptParsesTest(unittest.TestCase):
    """The emitted script must parse for every reasonable boot payload."""

    def _assert_parses(self, token, model, ready, label=""):
        page = oracle_page(token, model, ready)
        js = _script(page)
        r = _check_js(js)
        self.assertEqual(
            r.returncode, 0,
            f"{label or (token, model, ready)}: {r.stderr.decode()}"
        )

    def test_ready_page_parses(self):
        self._assert_parses("tok", "llama3.2:3b", True)

    def test_not_ready_page_parses(self):
        self._assert_parses("tok", "", False)

    def test_empty_token_and_model_parse(self):
        self._assert_parses("", "", True)
        self._assert_parses("", "", False)

    def test_unicode_model_name_parses(self):
        self._assert_parses("tok", "模型-αβγ", True)

    def test_model_with_quotes_parses(self):
        self._assert_parses("tok", 'model "with" quotes', True)
        self._assert_parses("tok", "model 'with' quotes", True)

    def test_model_with_backslash_parses(self):
        self._assert_parses("tok", "path\\to\\model", True)

    def test_model_with_newline_parses(self):
        # A newline in the model name must not break the boot JSON or the script.
        self._assert_parses("tok", "model\nwith\nnewlines", True)

    def test_long_token_parses(self):
        self._assert_parses("x" * 200, "m", True)

    def test_token_with_special_chars_parses(self):
        self._assert_parses("tok</script><script>alert(1)", "m", True)
        self._assert_parses("tok\"; alert(1);//", "m", True)
        self._assert_parses("tok` + alert(1) + `", "m", True)

    def test_none_values_parse(self):
        # oracle_page coerces non-strings.
        self._assert_parses(None, None, True)  # type: ignore
        self._assert_parses(None, 123, False)  # type: ignore

    def test_many_calls_all_parse(self):
        for i in range(20):
            self._assert_parses(f"tok-{i}", f"model-{i}", i % 2 == 0, label=f"call {i}")


class OraclePageScriptStructureTest(unittest.TestCase):
    """The send path must be present and correctly wired."""

    def setUp(self):
        self.page = oracle_page("session-token-abc", "llama3.2:3b", True)
        self.js = _script(self.page)

    def test_form_and_button_exist(self):
        self.assertIn('<form id="f">', self.page)
        self.assertIn('<button id="send" type="submit">', self.page)
        self.assertIn('<textarea id="q"', self.page)

    def test_onsubmit_prevents_default_and_fetches_ask(self):
        self.assertIn('document.getElementById("f").onsubmit', self.js)
        self.assertIn("e.preventDefault()", self.js)
        self.assertIn('fetch("/ask"', self.js)
        self.assertIn('"X-Oracle-Token": boot.token', self.js)
        self.assertIn("JSON.stringify({question: text})", self.js)

    def test_send_is_disabled_while_working(self):
        self.assertIn("send.disabled = true", self.js)
        self.assertIn("send.disabled = false", self.js)

    def test_working_bubble_and_status_poll_exist(self):
        self.assertIn('"Working…"', self.js)
        self.assertIn('fetch("/status"', self.js)
        self.assertIn("setInterval(paint, 1000)", self.js)

    def test_error_paths_are_present(self):
        self.assertIn("The chat session expired", self.js)
        self.assertIn("The page could not reach the local Oracle.", self.js)

    def test_default_question_is_present(self):
        self.assertIn("Give me a summary of the job status", self.page)

    def test_token_is_injected_into_boot_not_url(self):
        self.assertIn('"token": "session-token-abc"', self.js)
        # Token must not appear in any href or src.
        self.assertNotIn("session-token-abc", self.page.split("<script>")[0])

    def test_ready_note_names_the_model(self):
        self.assertIn("Local model", self.js)
        self.assertIn("llama3.2:3b", self.js)

    def test_not_ready_note_explains_how_to_fix(self):
        page = oracle_page("tok", "", False)
        js = _script(page)
        self.assertIn("No loopback model is configured", js)
        self.assertIn("--inference-only", js)
        self.assertIn("inference.endpoint", js)


class OraclePageScriptSafetyTest(unittest.TestCase):
    """Static checks for patterns that break a page script."""

    def test_no_raw_newline_inside_double_quoted_string(self):
        """The original bug: a raw newline inside a \"...\" string."""
        page = oracle_page("tok", "m", True)
        js = _script(page)
        # Walk the script looking for " that is followed by a newline
        # before the closing " (ignoring escapes).
        i = 0
        while i < len(js):
            if js[i] == '"' and (i == 0 or js[i - 1] != "\\"):
                # Find the closing quote, allowing escapes.
                j = i + 1
                while j < len(js):
                    if js[j] == "\\" and j + 1 < len(js):
                        j += 2
                        continue
                    if js[j] == '"':
                        break
                    if js[j] == "\n":
                        self.fail(
                            f"raw newline inside double-quoted string "
                            f"at offset {i}: {js[i:i+40]!r}"
                        )
                    j += 1
                i = j + 1
            else:
                i += 1

    def test_fit_function_uses_escaped_newline(self):
        page = oracle_page("tok", "m", True)
        js = _script(page)
        # The fit() return must contain a JS-escaped newline, not a raw one.
        self.assertIn(
            'return text.slice(0, BUBBLE) + "\\n… cut. The full answer is in oracle-chat.jsonl.";',
            js,
        )
        # And must not contain the broken form.
        self.assertNotIn(
            'return text.slice(0, BUBBLE) + "\n',
            js,
        )

    def test_no_unescaped_script_close_in_boot(self):
        """A token or model containing </script> must not break out of the script."""
        page = oracle_page("tok</script><script>alert(1)", "m</script>", True)
        # The boot JSON is escaped so < becomes \u003c.
        self.assertNotIn("</script><script>alert", page)
        self.assertIn("\\u003c", page)
        r = _check_js(_script(page))
        self.assertEqual(r.returncode, 0, r.stderr.decode())

    def test_boot_payload_is_valid_json(self):
        page = oracle_page("tok", "llama3.2:3b", True)
        js = _script(page)
        m = re.search(r"const boot = (\{.*?\});", js)
        self.assertIsNotNone(m, "boot assignment not found")
        boot = json.loads(m.group(1))
        self.assertEqual(boot["token"], "tok")
        self.assertEqual(boot["model"], "llama3.2:3b")
        self.assertTrue(boot["ready"])

    def test_boot_payload_survives_special_chars(self):
        cases = [
            ("tok</script>", 'model "q"', True),
            ("tok\nline", "model\\path", False),
            ("tok`backtick`", "model'quote'", True),
            ("", "", True),
        ]
        for token, model, ready in cases:
            page = oracle_page(token, model, ready)
            js = _script(page)
            m = re.search(r"const boot = (\{.*?\});", js, re.DOTALL)
            self.assertIsNotNone(m, f"boot not found for {token!r}")
            boot = json.loads(m.group(1))
            self.assertEqual(boot["ready"], bool(ready))
            r = _check_js(js)
            self.assertEqual(r.returncode, 0, r.stderr.decode())

    def test_page_has_no_remote_assets(self):
        page = oracle_page("tok", "m", True)
        # No external scripts, stylesheets, or images.
        self.assertNotIn("src=", page.lower())
        self.assertNotIn("href=", page.lower())
        self.assertNotIn("http://", page.split("<script>")[0])
        self.assertNotIn("https://", page.split("<script>")[0])


class OraclePageScriptRegressionTest(unittest.TestCase):
    """Named regressions for the Send-does-nothing class of bug."""

    def test_the_original_newline_bug_is_fixed(self):
        """2026-10-18: raw newline in fit() made the script a SyntaxError."""
        page = oracle_page("tok", "m", True)
        js = _script(page)
        r = _check_js(js)
        self.assertEqual(r.returncode, 0, r.stderr.decode())
        # The specific broken form must not appear.
        self.assertNotIn(' + "\n… cut.', js)
        self.assertIn(' + "\\n… cut.', js)

    def test_send_handler_is_assigned_after_elements_exist(self):
        """The onsubmit assignment must come after the element lookups."""
        page = oracle_page("tok", "m", True)
        js = _script(page)
        send_lookup = js.find('const send = document.getElementById("send")')
        onsubmit = js.find('document.getElementById("f").onsubmit')
        self.assertGreater(send_lookup, 0)
        self.assertGreater(onsubmit, send_lookup)

    def test_empty_question_is_rejected_client_side(self):
        page = oracle_page("tok", "m", True)
        js = _script(page)
        self.assertIn("if (!text || send.disabled) return;", js)

    def test_question_is_trimmed_before_send(self):
        page = oracle_page("tok", "m", True)
        js = _script(page)
        self.assertIn("const text = q.value.trim();", js)


if __name__ == "__main__":
    unittest.main()


# --- Carried from the main-line page gate (cfb7675): the same
# contract from the other side of the collapse. ---


class PageScriptParsesTest(unittest.TestCase):
    def test_one_script_block(self):
        page = oracle_page("tok", "llama3.2:3b", True)
        self.assertEqual(page.count("<script>"), 1)
        self.assertEqual(page.count("</script>"), 1)

    def test_send_is_wired(self):
        js = _script(oracle_page("tok", "llama3.2:3b", True))
        self.assertIn('document.getElementById("f").onsubmit', js)
        self.assertIn("e.preventDefault()", js)
        self.assertIn('fetch("/ask"', js)
        self.assertIn("X-Oracle-Token", js)
        self.assertIn("boot.token", js)
        self.assertIn("send.disabled", js)
        self.assertIn('id="send"', oracle_page("tok", "m", True))

    def test_the_cut_notice_is_one_string(self):
        js = _script(oracle_page("tok", "m", True))
        fit = js[js.find("function fit"):js.find("function add")]
        # A real newline inside the string is what killed Send.
        self.assertNotIn('"\n', fit)
        self.assertIn("\\n…", fit)

    def test_boot_json_cannot_break_out(self):
        nasty = [
            ('tok</script><script>alert(1)', "m", True),
            ('a"b', "m", True),
            ("tok", "model\nwith\nlines", True),
            ("tok", "model\\with\\slashes", False),
            ("", "", False),
        ]
        for token, model, ready in nasty:
            page = oracle_page(token, model, ready)
            js = _script(page)
            self.assertEqual(page.count("<script>"), 1, token)
            self.assertNotIn("</script>", js, token)
            # The boot object is JSON, so it round-trips.
            blob = js[js.find("const boot = ") + len("const boot = "):]
            blob = blob[:blob.find(";")]
            got = json.loads(blob)
            self.assertEqual(got["ready"], ready)

    @unittest.skipUnless(NODE, "node is not installed")
    def test_node_accepts_every_variant(self):
        variants = [
            ("tok", "llama3.2:3b", True),
            ("tok", "llama3.2:3b", False),
            ("a" * 80, "model-name", True),
            ("tok'\"\\", "m\n<x>", True),
            ("", "", False),
        ]
        for token, model, ready in variants:
            js = _script(oracle_page(token, model, ready))
            with tempfile.NamedTemporaryFile("w", suffix=".js") as fh:
                fh.write(js)
                fh.flush()
                proc = subprocess.run(
                    [NODE, "--check", fh.name],
                    capture_output=True, text=True,
                )
            self.assertEqual(
                proc.returncode, 0,
                f"{token!r} {model!r}: {proc.stderr}",
            )


class PageSendContractTest(unittest.TestCase):
    """The pieces Send needs, present and in order."""

    def test_the_form_exists_before_the_script(self):
        page = oracle_page("tok", "m", True)
        self.assertLess(page.find('id="f"'), page.find("<script>"))
        self.assertLess(page.find('id="q"'), page.find("<script>"))
        self.assertLess(page.find('id="send"'), page.find("<script>"))
        self.assertLess(page.find('id="log"'), page.find("<script>"))

    def test_submit_reads_the_box_and_clears_it(self):
        js = _script(oracle_page("tok", "m", True))
        self.assertIn("q.value.trim()", js)
        self.assertIn('q.value = ""', js)
        self.assertIn("send.disabled = true", js)
        self.assertIn("send.disabled = false", js)

    def test_a_failure_still_says_something(self):
        js = _script(oracle_page("tok", "m", True))
        self.assertIn("The page could not reach the local Oracle.", js)
        self.assertIn("The chat session expired.", js)
        self.assertIn("catch (err)", js)

    def test_the_window_constants_are_present(self):
        js = _script(oracle_page("tok", "m", True))
        self.assertIn("const KEEP = 40", js)
        self.assertIn("const BUBBLE = 4000", js)
        self.assertIn("function trimLog()", js)
        self.assertIn("trimLog();", js)
