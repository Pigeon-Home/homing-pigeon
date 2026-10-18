#!/usr/bin/env python3
"""The Oracle page script must stay a program, or Send does nothing.

Field bug, 2026-10-18: the cut notice was a real newline inside a
JavaScript string. The script failed to parse, the form never
attached, and the button reloaded the page. The warm-up kept
writing the log, so it looked busy. These tests pin that class of
break: a quote that does not close, a boot value that breaks out of
the script, a handler that forgets preventDefault, and an empty box
that looks like a question already sent.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import make_oracle_server, oracle_page  # noqa: E402


class ScriptBreak(Exception):
    """The page script would not parse, so Send would not attach."""


def extract_script(page):
    start = page.find("<script>")
    end = page.find("</script>")
    if start < 0 or end < start:
        raise ScriptBreak("no script block")
    if page.find("<script>", start + 1) != -1:
        raise ScriptBreak("more than one script")
    if page.find("</script>", end + 1) != -1:
        raise ScriptBreak("more than one script closer")
    return page[start + 8:end]


def scan_js_strings(src):
    """Walk quotes. A raw newline in ' or " is the field bug.

    Comments are skipped so a // inside a string is not a comment,
    and a comment is not a string. Template literals may span lines;
    the page does not use them for the cut notice.
    """
    i = 0
    n = len(src)
    found = []
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            i = src.find("\n", i)
            if i < 0:
                break
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            end = src.find("*/", i + 2)
            if end < 0:
                raise ScriptBreak("unterminated comment")
            i = end + 2
            continue
        if c in ("'", '"', "`"):
            quote = c
            i += 1
            body = []
            while i < n:
                ch = src[i]
                if ch == "\\":
                    if i + 1 >= n:
                        raise ScriptBreak("dangling escape")
                    body.append(src[i:i + 2])
                    i += 2
                    continue
                if ch == quote:
                    found.append((quote, "".join(body)))
                    i += 1
                    break
                if quote != "`" and ch in "\n\r\u2028\u2029":
                    raise ScriptBreak(
                        "raw line break inside a %s string" % quote)
                body.append(ch)
                i += 1
            else:
                raise ScriptBreak("unterminated %s string" % quote)
            continue
        i += 1
    return found


def boot_object(js):
    mark = "const boot = "
    at = js.find(mark)
    if at < 0:
        raise ScriptBreak("boot payload missing")
    blob, _end = json.JSONDecoder().raw_decode(js[at + len(mark):])
    return blob


def node_check(js):
    if shutil.which("node") is None:
        raise unittest.SkipTest("node is not installed")
    proc = subprocess.run(
        ["node", "--check", "-"],
        input=js.encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise ScriptBreak(proc.stderr.decode() or "node --check failed")


# Values that have broken, or would break, a script spliced into HTML.
HOSTILE = [
    ("plain", "tok", "llama3.2:3b", True),
    ("empty token", "", "m", True),
    ("empty model", "tok", "", True),
    ("not ready", "tok", "m", False),
    ("double quote", 'to"k', 'qw"en', True),
    ("backslash", "to\\k", "m\\x", True),
    ("newline", "to\nk", "m\n", True),
    ("carriage return", "to\rk", "m\r", True),
    ("line separator", "a\u2028b", "c\u2029d", True),
    ("script closer", "tok</script><script>alert(1)", "m", True),
    ("script opener", "<script>", "<img src=x>", True),
    ("backtick", "to`k", "m${boot.token}", True),
    ("dollar", "$(reboot)", "${7}", True),
    ("line comment", "tok//nope", "m", True),
    ("block comment", "tok/*x*/", "m", True),
    ("unicode", "токен", "模型", True),
    ("apostrophe", "it's", "o'reilly", True),
    ("ampersand", "a&b", "c<d>e", True),
    ("null", "a\x00b", "m\x00", True),
    ("slash", "a/b", "c\\d", True),
    ("json breakout", '{"a":1}', "};alert(1);//", True),
    ("tag breakout", '"></textarea><script>alert(1)</script>', "m", True),
    ("long token", "T" * 4000, "M" * 400, True),
    ("spaces", "  tok  ", "  m  ", True),
    ("ready string", "tok", "m", "yes"),
    ("backslash end", "tok\\", "m\\", True),
    ("quote slash", 'a"\\', "b'\\", True),
]


_DRIVE = r"""
const fs = require("fs");
const script = fs.readFileSync(process.argv[2], "utf8");
const value = process.argv[3];
const disabled = process.argv[4] === "1";
const els = {};
function make(id) {
  const node = {
    id: id || "",
    textContent: "",
    value: "",
    disabled: false,
    className: "",
    children: [],
    childNodes: [],
    appendChild(child) { this.childNodes.push(child); this.children.push(child); return child; },
    removeChild() {},
    insertBefore() {},
    scrollIntoView() {},
    focus() {},
    remove() {},
  };
  return node;
}
global.document = {
  getElementById(id) {
    if (!els[id]) els[id] = make(id);
    return els[id];
  },
  createElement() { return make(""); },
  createTextNode(text) { return {textContent: text}; },
};
const fetches = [];
global.fetch = async (url, opts) => {
  fetches.push({url: url, body: opts && opts.body, headers: opts && opts.headers});
  return {status: 200, json: async () => ({answer: "ok"})};
};
let prevented = 0;
eval(script);
const form = els.f;
if (!form || typeof form.onsubmit !== "function") {
  console.log(JSON.stringify({error: "onsubmit missing"}));
  process.exit(2);
}
els.q.value = value;
els.send.disabled = disabled;
(async () => {
  await form.onsubmit({preventDefault() { prevented += 1; }});
  console.log(JSON.stringify({prevented: prevented, fetches: fetches}));
  process.exit(0);
})();
"""


def drive(js, value, disabled=False):
    if shutil.which("node") is None:
        raise unittest.SkipTest("node is not installed")
    with tempfile.TemporaryDirectory() as d:
        script_path = os.path.join(d, "page.js")
        harness = os.path.join(d, "drive.js")
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(js)
        with open(harness, "w", encoding="utf-8") as fh:
            fh.write(_DRIVE)
        proc = subprocess.run(
            ["node", harness, script_path, value, "1" if disabled else "0"],
            capture_output=True, timeout=10,
        )
    if proc.returncode != 0:
        raise ScriptBreak(proc.stderr.decode() or proc.stdout.decode())
    return json.loads(proc.stdout.decode())


class ScannerRejectsTheFieldBug(unittest.TestCase):
    def test_the_historical_newline_is_rejected(self):
        broken = ('return text.slice(0, BUBBLE) + "'
                  '\n… cut. The full answer is in oracle-chat.jsonl.";')
        with self.assertRaises(ScriptBreak):
            scan_js_strings(broken)

    def test_a_single_quoted_newline_is_rejected(self):
        with self.assertRaises(ScriptBreak):
            scan_js_strings("const s = 'hello\n';")

    def test_a_line_separator_is_rejected(self):
        with self.assertRaises(ScriptBreak):
            scan_js_strings('const s = "a\u2028b";')

    def test_an_unterminated_string_is_rejected(self):
        with self.assertRaises(ScriptBreak):
            scan_js_strings('const s = "hello;')

    def test_a_dangling_escape_is_rejected(self):
        with self.assertRaises(ScriptBreak):
            scan_js_strings('const s = "hello\\')

    def test_an_escaped_newline_is_allowed(self):
        # This is what the fixed cut notice looks like in the page.
        found = scan_js_strings(
            'return "\\n… cut. The full answer is in oracle-chat.jsonl.";')
        self.assertEqual(
            found,
            [('"', '\\n… cut. The full answer is in oracle-chat.jsonl.')])

    def test_a_comment_is_not_a_string(self):
        found = scan_js_strings('// "\nconst s = "ok";')
        self.assertEqual(found, [('"', "ok")])

    def test_slashes_inside_a_string_stay_a_string(self):
        found = scan_js_strings('const s = "http://127.0.0.1/ask";')
        self.assertEqual(len(found), 1)
        self.assertIn("/ask", found[0][1])


class LivePageScript(unittest.TestCase):
    def setUp(self):
        self.page = oracle_page("tok", "llama3.2:3b", True)
        self.js = extract_script(self.page)

    def test_the_cut_notice_is_one_line(self):
        scan_js_strings(self.js)
        self.assertIn(
            '"\\n… cut. The full answer is in oracle-chat.jsonl."',
            self.js)
        self.assertNotIn("\n… cut.", self.js)

    def test_there_is_one_script_and_it_is_inline(self):
        self.assertEqual(self.page.count("<script>"), 1)
        self.assertEqual(self.page.count("</script>"), 1)
        self.assertNotIn("<script src", self.page)
        self.assertNotIn("http://", self.js)
        self.assertNotIn("https://", self.js)

    def test_send_prevents_the_reload_before_it_asks(self):
        handler = self.js[self.js.find("onsubmit"):]
        guard = handler.find("if (!text || send.disabled) return;")
        ask = handler.find('fetch("/ask"')
        status = handler.find('fetch("/status"')
        self.assertIn('getElementById("f").onsubmit', self.js)
        self.assertLess(handler.find("e.preventDefault()"), guard)
        self.assertLess(guard, ask)
        self.assertLess(guard, status)
        self.assertIn("e.preventDefault();", handler[:80])

    def test_a_real_send_is_visible_and_a_failure_is_not_silence(self):
        self.assertIn("Working…", self.js)
        self.assertIn("The answer replaces this line.", self.js)
        self.assertIn("The page could not reach the local Oracle.", self.js)
        self.assertIn("The chat session expired.", self.js)
        self.assertEqual(self.js.count("clearInterval(tick)"), 2)
        self.assertEqual(self.js.count("clearInterval(poll)"), 2)
        self.assertIn("send.disabled = false;", self.js)

    def test_the_box_starts_empty(self):
        import re
        match = re.search(
            r'<textarea id="q"[^>]*>(.*?)</textarea>', self.page, re.S)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "")
        self.assertIn('type="submit"', self.page)
        self.assertIn("placeholder=", self.page)
        self.assertIn("Give me a summary of the job status", self.page)

    def test_boot_roundtrips(self):
        boot = boot_object(self.js)
        self.assertEqual(boot["token"], "tok")
        self.assertEqual(boot["model"], "llama3.2:3b")
        self.assertIs(boot["ready"], True)

    def test_node_parses_the_live_script(self):
        node_check(self.js)

    def test_the_historical_bug_still_fails_node(self):
        if shutil.which("node") is None:
            self.skipTest("node is not installed")
        broken = self.js.replace(
            '"\\n… cut. The full answer is in oracle-chat.jsonl."',
            '"\n… cut. The full answer is in oracle-chat.jsonl."',
            1)
        with self.assertRaises(ScriptBreak):
            scan_js_strings(broken)
        with self.assertRaises(ScriptBreak):
            node_check(broken)


class HostileBootValues(unittest.TestCase):
    def test_each_hostile_value_stays_inside_the_script(self):
        for name, token, model, ready in HOSTILE:
            with self.subTest(name=name):
                page = oracle_page(token, model, ready)
                self.assertEqual(page.count("<script>"), 1)
                self.assertEqual(page.count("</script>"), 1)
                self.assertNotIn("<script src", page)
                js = extract_script(page)
                scan_js_strings(js)
                boot = boot_object(js)
                self.assertEqual(boot["token"], token)
                self.assertEqual(boot["model"], model)
                self.assertEqual(boot["ready"], bool(ready))
                self.assertIn('getElementById("f").onsubmit', js)
                self.assertIn("e.preventDefault()", js)

    def test_node_parses_each_hostile_page(self):
        if shutil.which("node") is None:
            self.skipTest("node is not installed")
        for name, token, model, ready in HOSTILE:
            with self.subTest(name=name):
                node_check(extract_script(oracle_page(token, model, ready)))


class SendActuallyPosts(unittest.TestCase):
    def setUp(self):
        self.js = extract_script(oracle_page("session-token", "m", True))

    def test_an_empty_box_does_not_ask(self):
        out = drive(self.js, "")
        self.assertEqual(out["prevented"], 1)
        self.assertEqual(out["fetches"], [])

    def test_whitespace_does_not_ask(self):
        out = drive(self.js, "   \n  ")
        self.assertEqual(out["prevented"], 1)
        self.assertEqual(out["fetches"], [])

    def test_a_disabled_button_does_not_ask(self):
        out = drive(self.js, "what ran?", disabled=True)
        self.assertEqual(out["prevented"], 1)
        self.assertEqual(out["fetches"], [])

    def test_a_question_posts_ask_with_the_token(self):
        out = drive(self.js, "what ran?")
        self.assertEqual(out["prevented"], 1)
        urls = [item["url"] for item in out["fetches"]]
        self.assertIn("/ask", urls)
        ask = next(item for item in out["fetches"] if item["url"] == "/ask")
        self.assertEqual(json.loads(ask["body"])["question"], "what ran?")
        self.assertEqual(ask["headers"]["X-Oracle-Token"], "session-token")
        self.assertEqual(ask["headers"]["Content-Type"], "application/json")


class ServedPageIsTheSameProgram(unittest.TestCase):
    def test_get_returns_a_script_whose_token_is_the_ask_token(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d, "inference": {
                "endpoint": "http://127.0.0.1:11434/v1", "model": "m"}}
            httpd = make_oracle_server(cfg, "127.0.0.1", 0, base_dir=d)
            port = httpd.socket.getsockname()[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(httpd.shutdown)
            self.addCleanup(httpd.server_close)
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d/" % port, timeout=5) as resp:
                page = resp.read().decode()
            js = extract_script(page)
            scan_js_strings(js)
            node_check(js)
            boot = boot_object(js)
            self.assertEqual(boot["token"], httpd.oracle_token)
            self.assertEqual(boot["model"], "m")
            self.assertIs(boot["ready"], True)
            self.assertNotIn("</script>", js)


if __name__ == "__main__":
    unittest.main()
