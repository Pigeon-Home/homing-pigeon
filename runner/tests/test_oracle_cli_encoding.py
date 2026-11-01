"""--oracle-cli must survive answers its console cannot encode.

Live find, Germany rig, 1-Nov-2026 (job 75563043): the rig runs the
deterministic (Pi Light) Oracle, whose answer is the box's own
records, un-narrated. Earlier jobs on that box printed non-ASCII
output (accented Latin, Chinese and Japanese text, a duck emoji),
so the records the answer is assembled from carry those characters.
On Windows the console's text layer is cp1252, print() raised
UnicodeEncodeError partway through the answer, and the whole
--oracle-cli door died with a traceback (exit 1) before the user
saw an answer. The loopback window does not have this problem: it
encodes its body as UTF-8 explicitly.

These tests drive oracle_cli with the real print (print_fn=None)
against fake stdouts shaped like the Windows console -- one whose
raw buffer takes UTF-8 bytes, one with no usable buffer at all --
and pin that the chat completes, the answer is delivered (whole
through the buffer, safely replaced without one), and the turns
are still recorded. Exotic characters ride the front, the middle
and the back of the answer text, in runs, per the bookend rule.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from runner import runner as R  # noqa: E402

EXOTIC = "café duck \U0001F986 check ✓ euro € Chinese 中文 Japanese 日本語"
INF = {"endpoint": "http://127.0.0.1:11434/v1", "model": "m",
       "max_answer_chars": 2000}


class _BufferStdout:
    """Stdout whose text layer is cp1252 but whose buffer works.

    Writing exotic text through the text layer raises
    UnicodeEncodeError, exactly like the real Windows console;
    the raw buffer takes UTF-8 bytes fine.
    """

    def __init__(self):
        self.buffer = io.BytesIO()
        self.encoding = "cp1252"

    def write(self, text):
        text.encode("cp1252")
        return len(text)

    def flush(self):
        pass


class _RaisingStdout:
    """Stdout with no buffer whose write raises on non-cp1252 text."""

    def __init__(self):
        self.written = []
        self.encoding = "cp1252"

    def write(self, text):
        text.encode("cp1252")
        self.written.append(text)
        return len(text)

    def flush(self):
        pass


def _det_cfg(base):
    return {"oracle_mode": "deterministic", "base_dir": base}


def _seed_retained(base, stdout_text):
    retained = os.path.join(base, "retained")
    os.makedirs(retained, exist_ok=True)
    rec = {
        "kind": "exec",
        "exit_code": 0,
        "saved_at": 1760000000,
        "script": "Write-Output hello",
        "stdout": stdout_text,
        "stderr": "",
    }
    with open(os.path.join(retained, "jobexotic.json"), "w",
              encoding="utf-8") as fh:
        json.dump(rec, fh)


def _run_det_cli(base, fake_stdout, lines=("what ran?", "/quit")):
    asked = iter(lines)

    def fake_input(prompt=""):
        return next(asked)

    with contextlib.redirect_stdout(fake_stdout):
        rc = R.oracle_cli(_det_cfg(base), cfg_path=os.path.join(
            base, "config.json"), input_fn=fake_input)
    return rc


class DeterministicAnswerEncodingTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = self._tmp.name
        _seed_retained(self.base, EXOTIC)

    def test_buffer_stdout_gets_the_answer_whole(self):
        fake = _BufferStdout()
        rc = _run_det_cli(self.base, fake)
        self.assertEqual(rc, 0)
        blob = fake.buffer.getvalue().decode("utf-8", "replace")
        self.assertIn("Deterministic Oracle (Pi Light)", blob)
        self.assertIn(EXOTIC, blob)

    def test_raising_stdout_still_completes_the_chat(self):
        fake = _RaisingStdout()
        rc = _run_det_cli(self.base, fake)
        self.assertEqual(rc, 0)
        blob = "\n".join(fake.written)
        self.assertIn("Oracle mode: deterministic (Pi Light)", blob)
        self.assertIn("Deterministic Oracle (Pi Light)", blob)
        # The turn was recorded even though the console could not
        # carry every character of the answer.
        chat = os.path.join(self.base, "oracle-chat.jsonl")
        with open(chat, encoding="utf-8") as fh:
            turns = fh.read()
        self.assertIn("what ran?", turns)

    def test_exotic_runs_at_the_answer_edges(self):
        edge = EXOTIC + " x " + (EXOTIC * 3)
        _seed_retained(self.base, edge)
        fake = _BufferStdout()
        rc = _run_det_cli(self.base, fake)
        self.assertEqual(rc, 0)
        blob = fake.buffer.getvalue().decode("utf-8", "replace")
        self.assertIn(EXOTIC, blob)


class ModelAnswerEncodingTest(unittest.TestCase):
    def _run_llm_cli(self, fake_stdout):
        out_lines = iter(["why?", "/quit"])
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d, "inference": dict(INF)}

            def fake_ask(inf, question, ctx, cap, patterns, **kw):
                return {"answer": "Model note: " + EXOTIC}

            with mock.patch.object(R, "ask_model_agent",
                                   side_effect=fake_ask), \
                    mock.patch.object(R, "_warm_oracle_model"), \
                    contextlib.redirect_stdout(fake_stdout):
                rc = R.oracle_cli(
                    cfg, cfg_path=None,
                    input_fn=lambda prompt="": next(out_lines))
        return rc

    def test_model_answer_survives_a_cp1252_buffer_stdout(self):
        fake = _BufferStdout()
        rc = self._run_llm_cli(fake)
        self.assertEqual(rc, 0)
        blob = fake.buffer.getvalue().decode("utf-8", "replace")
        self.assertIn(EXOTIC, blob)

    def test_model_answer_survives_a_cp1252_raising_stdout(self):
        fake = _RaisingStdout()
        rc = self._run_llm_cli(fake)
        self.assertEqual(rc, 0)
        blob = "\n".join(fake.written)
        self.assertIn("Model note:", blob)


class PlainStdoutUnchangedTest(unittest.TestCase):
    def test_ascii_answer_on_a_plain_stdout_is_byte_exact(self):
        fake = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            _seed_retained(d, "plain output only")
            asked = iter(["what ran?", "/quit"])
            with contextlib.redirect_stdout(fake):
                rc = R.oracle_cli(_det_cfg(d), cfg_path=os.path.join(
                    d, "config.json"),
                    input_fn=lambda prompt="": next(asked))
        self.assertEqual(rc, 0)
        self.assertIn("Deterministic Oracle (Pi Light)",
                      fake.getvalue())
        self.assertIn("plain output only", fake.getvalue())


if __name__ == "__main__":
    unittest.main()
