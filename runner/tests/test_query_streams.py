# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""Two findings of de_dust's grows on the queries (Q90, Q92).

A retained record's stream is text or it is nothing. The executor
writes text; a record a crash left or a hand wrote may hold a list,
an object or a number there, and the query path read those two
ways: an empty container as nothing, a list or a number as the text
form of the value, handed back as the output's last line by tail
(`["x"]` became the line "['x']"). Now a stream that is not text is
no text, for every op.

A grep pattern whose repetition count is past what the engine holds
(`a{99999999999}`) raises OverflowError from re.compile, not the
engine's own error class, and it escaped the reader as a raise
instead of the bad_pattern refusal every other unusable pattern
gets. Whatever the engine refuses is a bad pattern now."""

import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner  # noqa: E402
from runner.ops.queries import (  # noqa: E402
    _carriable, _stream_text, answer_queries, handle_query_mail)
from runner.runner import _output_blob, load_retained, save_retained  # noqa: E402
from runner.tests.security_parity import (  # noqa: E402
    SECRET, FakeIMAP, FakeSMTP, base_config)
from runner.tests.test_cli_options import _captured_log  # noqa: E402
from runner.tests.test_dry_run_changes_nothing import (  # noqa: E402
    _Opts, _mail, _now, _sealed)

OUT = "one\ntwo\nthree\n"


def _answers(queries, stdout=OUT, stderr="", view="full", patterns=None):
    answers, _spent = answer_queries(
        queries, {"stdout": stdout, "stderr": stderr, "exit_code": 0},
        patterns or {}, 8, cfg={}, view=view)
    return answers


class StreamIsTextOrNothingTest(unittest.TestCase):
    def test_the_queries_text_is_text_and_nothing_else(self):
        self.assertEqual(_stream_text({"stdout": "a\n", "stderr": "b\n"}),
                         "a\nb\n")
        for other in ([], {}, ["x"], {"a": 1}, 7, 2.5, True, None, b"x"):
            self.assertEqual(_stream_text({"stdout": "a\n", "stderr": other}),
                             "a\n", repr(other))
            self.assertEqual(_stream_text({"stdout": other, "stderr": "b\n"}),
                             "b\n", repr(other))
        self.assertEqual(_stream_text({"stdout": ["x"], "stderr": 7}), "")
        self.assertEqual(_stream_text("not a result"), "")

    def test_the_oracle_still_sees_what_a_record_holds(self):
        # The owner's view keeps a value's text form: a credential
        # inside a list is scanned and shown, not hidden by its type.
        self.assertIn("FLAG-x", _output_blob({"stdout": ["a", "FLAG-x"],
                                              "stderr": {"n": 5}}))
        self.assertEqual(_output_blob({"stdout": 5, "stderr": None}), "5")

    def test_tail_hands_back_the_text_streams_last_lines_only(self):
        for stderr in ([], {}, ["warn: x", "warn: y"], 7, {"b": 1}):
            answers = _answers([{"op": "tail", "lines": 2}], stderr=stderr)
            self.assertEqual(answers[0]["lines"], ["two", "three"],
                             repr(stderr))
        answers = _answers([{"op": "tail", "lines": 2}],
                           stderr="warn: x\nwarn: y\n")
        self.assertEqual(answers[0]["lines"], ["warn: x", "warn: y"])
        answers = _answers([{"op": "tail", "lines": 2}], stdout=["one"],
                           stderr={"b": 1})
        self.assertEqual(answers[0]["lines"], [])

    def test_grep_and_the_digest_read_the_same_text(self):
        answers = _answers([{"op": "grep", "pattern": "t"},
                            {"op": "attest", "predicate": "output_digest"}],
                           stderr=["two"])
        self.assertEqual(answers[0]["matches"], ["two", "three"])
        self.assertEqual(answers[1]["digest"], _answers(
            [{"op": "attest", "predicate": "output_digest"}])[0]["digest"])


class SurrogateInARecordTest(unittest.TestCase):
    """Q93: a retained record a crash left can hold the escape of a
    lone surrogate in a stream; no UTF-8 encoder and so no signer
    accepts it, and the query's reply could not be sealed, so the
    handler raised into the poll and the message came back on every
    pass. On the wire the character is the replacement character,
    and a reply that cannot be sealed is logged, never raised."""

    def test_the_wire_text_replaces_a_lone_surrogate(self):
        self.assertEqual(_carriable("a\ud800b"), "a\ufffdb")
        self.assertEqual(_carriable("\udfff"), "\ufffd")
        # A pair of surrogate code points is the character they make.
        self.assertEqual(_carriable("\ud83d\udc26 caf\u00e9"),
                         "\U0001f426 caf\u00e9")
        self.assertEqual(_carriable("\U0001f426 caf\u00e9"),
                         "\U0001f426 caf\u00e9")
        self.assertEqual(_carriable("plain"), "plain")
        self.assertEqual(_stream_text({"stdout": "ok\n", "stderr": "\ud800"}),
                         "ok\n\ufffd")
        answers = _answers([{"op": "tail", "lines": 1},
                            {"op": "attest", "predicate": "output_digest"}],
                           stderr="bad \ud800 line\n")
        self.assertEqual(answers[0]["lines"], ["bad \ufffd line"])
        self.assertEqual(len(answers[1]["digest"]), 96)

    def _take(self, cfg, d, record, opts=None):
        save_retained(d, "bm-s-job", record)
        obj = {"v": 1, "type": "query", "query_id": "bm-s-q", "job_id": "bm-s-job",
               "issued_at": _now(), "queries": [{"op": "tail", "lines": 2}]}
        subject = "[HOMING-PIGEON] query bm-s-q"
        imap, smtp = FakeIMAP([]), FakeSMTP()
        with _captured_log() as buf:
            handled = handle_query_mail(
                cfg, imap, smtp, b"1", _mail(subject, _sealed(obj, "bm-s-q")),
                subject, runner.build_secrets(cfg), opts or _Opts(), d, {})
        return handled, imap, smtp, buf.getvalue()

    def test_the_handler_answers_a_record_with_a_surrogate(self):
        d = tempfile.mkdtemp(prefix="hp-q93-")
        self.addCleanup(shutil.rmtree, d, True)
        cfg = base_config(d)
        handled, imap, smtp, out = self._take(cfg, d, {
            "stdout": "one\ntwo\n", "stderr": "\ud800", "exit_code": 0,
            "budget": 8, "spent": 0, "view": "full", "saved_at": time.time()})
        self.assertTrue(handled)
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(imap.flagged, [b"1"])
        self.assertNotIn("could not send", out)
        self.assertNotIn("rejected", out)
        self.assertEqual(load_retained(d, "bm-s-job")["spent"], 1)

    def test_a_reply_that_cannot_be_sealed_is_logged_not_raised(self):
        d = tempfile.mkdtemp(prefix="hp-q93-")
        self.addCleanup(shutil.rmtree, d, True)
        cfg = base_config(d)
        with mock.patch.object(runner, "_seal_reply",
                               side_effect=ValueError("payload refused")):
            handled, imap, smtp, out = self._take(cfg, d, {
                "stdout": "one\n", "stderr": "", "exit_code": 0,
                "budget": 8, "spent": 0, "view": "full",
                "saved_at": time.time()})
        self.assertTrue(handled)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(imap.flagged, [b"1"])
        self.assertIn("could not send query result bm-s-q: payload refused", out)


class PatternTheEngineRefusesTest(unittest.TestCase):
    def test_a_repetition_past_the_engine_is_a_bad_pattern(self):
        for pattern in ("a{99999999999}", "a{1,99999999999}",
                        "(?:a+){9223372036854775808}",
                        "(?:a+){99999999999999999999}"):
            answers = _answers([{"op": "grep", "pattern": pattern},
                                {"op": "grep", "pattern": "one"}])
            self.assertEqual(answers[0], {"op": "grep",
                                          "rejected": "bad_pattern"}, pattern)
            self.assertEqual(answers[1]["matches"], ["one"], pattern)

    def test_under_every_view_that_runs_grep(self):
        for view in ("full", "redacted"):
            answers = _answers([{"op": "grep", "pattern": "a{99999999999}"}],
                               view=view, patterns={"x": "a{99999999999}"})
            self.assertEqual(answers[0]["rejected"], "bad_pattern", view)

    def test_a_large_repetition_the_engine_holds_still_runs(self):
        answers = _answers([{"op": "grep", "pattern": "a{65536}"},
                            {"op": "grep", "pattern": "e{1,2147483647}"}])
        self.assertEqual(answers[0]["matches"], [])
        self.assertEqual(answers[1]["matches"], ["one", "three"])


if __name__ == "__main__":
    unittest.main()
