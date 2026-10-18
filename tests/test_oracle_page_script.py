"""The Oracle page script must parse, or Send does nothing.

A real newline inside a JS string shipped once. The script failed
to parse, the form handler never attached, and the button did
nothing while the runner log kept moving. These tests are the
gate for that class of bug.
"""

import json
import shutil
import subprocess
import tempfile
import unittest

from runner.runner import oracle_page

NODE = shutil.which("node")


def _script(page):
    start = page.find("<script>")
    end = page.find("</script>")
    assert start != -1 and end != -1 and end > start
    return page[start + len("<script>"):end]


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
