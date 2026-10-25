#!/usr/bin/env python3
"""Q15: the Oracle agent's refusals, direct and through a
stub model.

test_runner_oracle_tools pins the common refusals one call at
a time. What the coverage map showed unrun, and what this
module adds:

  - the withheld-path refusal (the extension sources
    disclosure rule) for read, list and write;
  - error strings, never exceptions, for a directory read as
    a file, a write whose parent is a file, and a NUL-bearing
    path (refused at the stays-inside guard, which is why
    list_dir's generic except is unreachable -- recorded in
    Q15's answer);
  - a huge max_chars stays bounded by the file itself;
  - the whole loop under a hostile stub model: escaping
    reads and writes, an unknown tool, malformed arguments,
    a response that is not JSON, and a model that never stops
    calling tools. Every refusal comes back as an error string
    the model can read, nothing outside the state dir
    changes, and the loop ends -- by the model's answer, by
    an inference_error rejection, or by the tool budget.
"""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner.tests.test_oracle_agent_stall import (  # noqa: E402
    _Resp, _agent_cfg, _scripted_opener, _tool_call_msg)

ESCAPED = os.path.join(tempfile.gettempdir(),
                       "hp-q15-escaped.txt")


def _tool_msg(name, arguments, cid):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": cid, "type": "function",
         "function": {"name": name, "arguments": arguments}}]}


class DirectRefusals(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-q15-")
        self.secret_file = os.path.join(self.base, "source.txt")
        with open(self.secret_file, "w", encoding="utf-8") as fh:
            fh.write("withheld content")

    def test_withheld_path_refused_for_read_list_and_write(self):
        withheld = [self.secret_file]
        for name, args in (
                ("read_file", {"path": self.secret_file}),
                ("write_file", {"path": self.secret_file,
                                "content": "overwrite"})):
            out = R._run_oracle_tool(name, args,
                                     base_dir=self.base,
                                     withheld=withheld)
            self.assertTrue(out.startswith("error: withheld"),
                            (name, out))
        sub = os.path.join(self.base, "sub")
        os.mkdir(sub)
        out = R._run_oracle_tool("list_dir", {"path": sub},
                                 base_dir=self.base,
                                 withheld=[sub])
        self.assertTrue(out.startswith("error: withheld"), out)
        with open(self.secret_file, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "withheld content")

    def test_reading_a_directory_is_an_error_string(self):
        out = R._run_oracle_tool(
            "read_file", {"path": self.base}, base_dir=self.base)
        self.assertTrue(out.startswith("error:"), out)

    def test_write_below_a_file_is_an_error_string(self):
        blocker = os.path.join(self.base, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("file, not a directory")
        out = R._run_oracle_tool(
            "write_file",
            {"path": os.path.join(blocker, "child.txt"),
             "content": "x"},
            base_dir=self.base)
        self.assertTrue(out.startswith("error:"), out)
        with open(blocker, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "file, not a directory")

    def test_huge_max_chars_is_bounded_by_the_file(self):
        path = os.path.join(self.base, "small.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("abc" * 100)
        out = R._run_oracle_tool(
            "read_file", {"path": path, "max_chars": 10 ** 9},
            base_dir=self.base)
        self.assertEqual(out, "abc" * 100)

    def test_nul_path_is_refused_at_the_guard(self):
        out = R._run_oracle_tool(
            "list_dir", {"path": "sub\x00dir"},
            base_dir=self.base)
        self.assertEqual(out, "error: path leaves the state dir")


class HostileStubModel(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-q15-loop-")
        if os.path.exists(ESCAPED):
            os.unlink(ESCAPED)

    def tearDown(self):
        if os.path.exists(ESCAPED):
            os.unlink(ESCAPED)

    def test_hostile_sequence_gets_error_strings_only(self):
        script = [
            _tool_msg("read_file",
                      json.dumps({"path": "../outside.txt"}), "c1"),
            _tool_msg("write_file",
                      json.dumps({"path": ESCAPED, "content": "x"}),
                      "c2"),
            _tool_msg("exfiltrate", "{}", "c3"),
            _tool_msg("read_file", "not json", "c4"),
            {"role": "assistant", "content": "Final answer."},
        ]
        seen = []
        ans = R.ask_model_agent(
            _agent_cfg(), "q", "ctx", 2000,
            opener=_scripted_opener(list(script), seen),
            base_dir=self.base)
        self.assertEqual(ans.get("answer"), "Final answer.")
        self.assertEqual(ans.get("tool_rounds"), 4)
        results = [m.get("content") for payload in seen
                   for m in payload.get("messages", [])
                   if m.get("role") == "tool"]
        joined = "\n".join(str(r) for r in results)
        self.assertIn("error: path leaves the state dir", joined)
        self.assertIn("error: unknown tool 'exfiltrate'", joined)
        self.assertIn("error: path must be a non-empty string",
                      joined)
        self.assertFalse(os.path.exists(ESCAPED))

    def test_a_non_json_response_is_a_rejection_not_a_raise(self):
        def bad_opener(req, timeout=None):
            return _Resp(b"this is not json at all")

        ans = R.ask_model_agent(
            _agent_cfg(), "q", "ctx", 2000, opener=bad_opener,
            base_dir=self.base)
        self.assertEqual(ans.get("rejected"), "inference_error")

    def test_a_model_that_never_stops_hits_the_tool_budget(self):
        target = os.path.join(self.base, "note.txt")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("note")
        script = [_tool_call_msg(target) for _ in range(40)]
        seen = []
        ans = R.ask_model_agent(
            _agent_cfg(), "q", "ctx", 2000,
            opener=_scripted_opener(script, seen),
            base_dir=self.base)
        self.assertEqual(ans.get("rejected"), "tool_budget")
        self.assertLessEqual(len(seen), 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
