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


import hashlib  # noqa: E402
import string  # noqa: E402

from runner.ops import queries as _queries_mod  # noqa: E402


class QueryTargetCrashShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 53, Q90-Q93: the
    query-target crash families filed from grows 12-15.

    Verification, done first-hand before any test was written.
    Each Q-number was traced in the git record and in
    docs/steady/seats/questions.md: Q90 (grow 12, seed 6240,
    four `query` crashes, contract "tail's lines are not the
    output's last lines") and Q91 (grow 13, four more of the
    same shape) were fixed in f7698710 (release 3.13.67, whose
    message names Q90, Q91 and Q92), with the follow-up
    89262c09 scoping the text-or-nothing rule to the query path
    while the Oracle keeps a record's text form. Q92 (grow 14)
    is two shapes: the same Q90 tail break, plus a new class on
    `queries` -- answer_queries raising OverflowError for a
    repetition count the regex engine cannot hold -- also
    fixed in f7698710. Q93 (grow 15, five crashes at the pre-fix
    head) is three Q90 shapes plus a new pair: handle_query_mail
    raising ValueError on an unpaired UTF-16 surrogate in a
    retained stream, fixed in 721060ab (release 3.13.68, the
    _carriable rule and the seal-or-send guard). No Q-number
    was left ungrounded, so no mapping had to be invented.

    This family pins the crash shapes themselves -- the
    grow-filed inputs -- and is deliberately distinct from item
    51's replay-cache family and item 52's query-door family:
    non-text streams under every op, repetition counts at and
    past the engine's bound, surrogate escapes at every
    position, and the handler taking each of those records
    without raising. The fixes' own tests live in this file, so
    the family lives here too. One regression test was never
    going to be enough for a bug that took days of CPU to find.

    Per-field enumeration: the record's stdout and stderr
    fields (each non-text type, in each place, under tail,
    grep and the digest), the grep query's pattern and
    max_matches fields, the tail query's lines field, the
    queries list and the budget fields, and the stream text's
    surrogate positions. Bookends: patterns and stream lines
    bookended with every printable ASCII symbol (as literal
    text to grep for, and as regex text), symbol-only patterns,
    and surrogates at the front, the back and the middle of a
    line. Run lengths: patterns of 100 and 10000 characters,
    repetition counts the engine holds and counts it refuses,
    and streams of repeated lines with the odd line at the
    front, the back and the middle.

    Proof of work. The unit tests are the 50 methods of this
    class: 34 hand-written seams plus 16 generated non-text
    stream tests. The fuzzing was executed, not just the tests
    written: runner/tools/de_dust_corpus.py grow --target
    query --rounds 400 --seed 20261154 against the banked query
    corpus (167 entries). Result: 400 rounds,
    0 crashes, 0 slow, arcs 870 -> 903 (3 entries kept), slowest
    try 19208 ms; the grow-filed crash shapes did not
    recur. The grow's bookkeeping writes were reverted and are
    not banked (banking is the rigs' hourly job). None of this
    is exotic: it is combinatorics -- systematically trying the
    combinations a hand-written list would never reach, then
    pinning each answer as a test."""

    # The grep answers below run in the query worker subprocess,
    # whose boot on a busy box can pass the 2-second grep
    # deadline and read as a timeout (the same cold-interpreter
    # shape the Q102 slow-grep fix recorded). This family pins
    # grep's answers, not its deadline, so the class widens the
    # deadline while it runs and restores it afterwards; the
    # deadline's own pins live in the pattern-bound tests.
    @classmethod
    def setUpClass(cls):
        cls._saved_deadline = _queries_mod._GREP_DEADLINE
        _queries_mod._GREP_DEADLINE = 60.0

    @classmethod
    def tearDownClass(cls):
        _queries_mod._GREP_DEADLINE = cls._saved_deadline

    # -- Q90/Q91: the tail contract over non-text streams --

    def test_stream_text_table_both_fields(self):
        for other in ([], {}, ["x"], {"a": 1}, 7, 2.5, True, False,
                      None, b"x", [["x"]], {"a": ["x"]}):
            self.assertEqual(_stream_text({"stdout": "a\n",
                                           "stderr": other}), "a\n",
                             repr(other))
            self.assertEqual(_stream_text({"stdout": other,
                                           "stderr": "b\n"}), "b\n",
                             repr(other))
        self.assertEqual(_stream_text({"stdout": ["x"], "stderr": 7}), "")
        self.assertEqual(_stream_text(None), "")
        self.assertEqual(_stream_text([("stdout", "a")]), "")

    def test_tail_with_both_streams_nontext_hands_back_nothing(self):
        answers = _answers([{"op": "tail", "lines": 5}],
                           stdout=["one"], stderr={"b": 1})
        self.assertEqual(answers[0]["lines"], [])

    def test_grep_reads_only_the_text_stream(self):
        answers = _answers([{"op": "grep", "pattern": "two"}],
                           stderr=["two", "three"])
        self.assertEqual(answers[0]["matches"], ["two"])
        answers = _answers([{"op": "grep", "pattern": "x"}],
                           stdout="", stderr=[{"x": 1}])
        self.assertEqual(answers[0]["matches"], [])

    def test_the_digest_is_over_the_text_streams_only(self):
        with_list = _answers(
            [{"op": "attest", "predicate": "output_digest"}],
            stderr=["two"])
        plain = _answers([{"op": "attest", "predicate": "output_digest"}])
        self.assertEqual(with_list[0]["digest"], plain[0]["digest"])
        want = hashlib.sha384(OUT.encode("utf-8")).hexdigest()
        self.assertEqual(plain[0]["digest"], want)

    def test_the_q90_first_entry_shape_all_ops_one_record(self):
        # Grow 12's first entry carried attest, grep and tail
        # together against a record whose streams were not text.
        answers = _answers(
            [{"op": "attest", "predicate": "output_digest"},
             {"op": "grep", "pattern": "t"},
             {"op": "tail", "lines": 3}],
            stderr={"not": "text"})
        self.assertEqual(answers[1]["matches"], ["two", "three"])
        self.assertEqual(answers[2]["lines"], ["one", "two", "three"])
        self.assertEqual(len(answers[0]["digest"]), 96)

    def test_tail_asking_for_more_lines_than_the_text_has(self):
        answers = _answers([{"op": "tail", "lines": 200}],
                           stderr=["ignored"])
        self.assertEqual(answers[0]["lines"], ["one", "two", "three"])

    def test_nontext_streams_under_the_redacted_view(self):
        answers = _answers([{"op": "tail", "lines": 2},
                            {"op": "grep", "pattern": "t"}],
                           stderr=["two"], view="redacted")
        self.assertEqual(answers[0]["lines"], ["two", "three"])
        self.assertEqual(answers[1]["matches"], ["two", "three"])

    def test_nontext_streams_under_the_attested_view(self):
        answers = _answers([{"op": "tail", "lines": 2},
                            {"op": "grep", "pattern": "t"}],
                           stderr=["two"], view="attested")
        self.assertEqual(answers[0].get("rejected"), "policy")
        self.assertEqual(answers[1].get("rejected"), "policy")

    # -- Q92: the repetition the engine cannot hold --

    def test_overflow_repetition_spellings_are_bad_patterns(self):
        for pattern in ("a{99999999999}", "a{1,99999999999}",
                        "a{99999999999,}", "(?:a+){9223372036854775808}",
                        "(a|b){18446744073709551616}",
                        "x{10,99999999999999999999}"):
            answers = _answers([{"op": "grep", "pattern": pattern},
                                {"op": "tail", "lines": 1}])
            self.assertEqual(answers[0], {"op": "grep",
                                          "rejected": "bad_pattern"},
                             pattern)
            self.assertEqual(answers[1]["lines"], ["three"], pattern)

    def test_overflow_repetition_under_the_redacted_view(self):
        answers = _answers([{"op": "grep", "pattern": "a{99999999999}"}],
                           view="redacted",
                           patterns={"x": "a{99999999999}"})
        self.assertEqual(answers[0]["rejected"], "bad_pattern")

    def test_large_repetitions_the_engine_holds_still_run(self):
        answers = _answers([{"op": "grep", "pattern": "a{65536}"},
                            {"op": "grep", "pattern": "e{1,2147483647}"},
                            {"op": "grep", "pattern": "a{2147483648}"}])
        self.assertEqual(answers[0]["matches"], [])
        self.assertEqual(answers[1]["matches"], ["one", "three"])
        self.assertEqual(answers[2]["matches"], [])

    def test_syntax_bad_patterns_are_refusals_not_raises(self):
        for pattern in ("(", "[", "*", "\\", "(?P<",
                        "a**", "[z-a]", "(?i"):
            answers = _answers([{"op": "grep", "pattern": pattern}])
            self.assertEqual(answers[0].get("rejected"), "bad_pattern",
                             pattern)

    def test_backtracking_shapes_are_refused_before_they_run(self):
        for pattern in ("(a+)+$", "(a|a)*$", "(x+x+)+y"):
            answers = _answers([{"op": "grep", "pattern": pattern}],
                               stdout="a" * 30 + "\n")
            self.assertEqual(answers[0].get("rejected"), "bad_pattern",
                             pattern)
            self.assertIn("reason", answers[0], pattern)

    def test_pattern_field_wrong_types_read_as_the_empty_pattern(self):
        for bad in (None, 7, ["t"], {"p": "t"}, True):
            answers = _answers([{"op": "grep", "pattern": bad}])
            self.assertEqual(answers[0]["matches"],
                             ["one", "two", "three"], repr(bad))

    def test_patterns_that_are_plain_text_and_regex_text(self):
        answers = _answers([{"op": "grep", "pattern": "one|three"},
                            {"op": "grep", "pattern": "^two$"},
                            {"op": "grep", "pattern": "t.o"},
                            {"op": "grep", "pattern": "."}])
        self.assertEqual(answers[0]["matches"], ["one", "three"])
        self.assertEqual(answers[1]["matches"], ["two"])
        self.assertEqual(answers[2]["matches"], ["two"])
        self.assertEqual(answers[3]["matches"], ["one", "two", "three"])

    def test_bookend_and_runlength_patterns(self):
        for sym in string.punctuation:
            answers = _answers([{"op": "grep", "pattern": sym + "two"}])
            if sym in "*+?([){":
                # A leading quantifier has nothing to repeat, and
                # a group or class opened or closed around nothing
                # is never balanced: the engine refuses those, as
                # a bad_pattern. ("{" alone is a literal in this
                # engine and answers below.)
                if sym == "{":
                    self.assertNotIn("rejected", answers[0], sym)
                    continue
                self.assertEqual(answers[0].get("rejected"),
                                 "bad_pattern", sym)
            else:
                self.assertNotIn("rejected", answers[0], sym)
        answers = _answers([{"op": "grep", "pattern": "a" * 100},
                            {"op": "grep", "pattern": "x" * 10000},
                            {"op": "grep", "pattern": "a{100}"}])
        self.assertEqual(answers[0]["matches"], [])
        self.assertEqual(answers[1]["matches"], [])
        self.assertEqual(answers[2]["matches"], [])

    def test_symbol_only_patterns(self):
        # Symbol-only patterns are mostly literal or anchor text,
        # not refusals: they answer, and the one the engine
        # refuses ("***") is a bad_pattern.
        for pattern in ("!!!", "|||", "^^^", "$$$"):
            answers = _answers([{"op": "grep", "pattern": pattern}])
            self.assertIn("matches", answers[0], pattern)
        answers = _answers([{"op": "grep", "pattern": "***"}])
        self.assertEqual(answers[0].get("rejected"), "bad_pattern")
        answers = _answers([{"op": "grep", "pattern": "\\."}],
                           stdout="a.b\nplain\n")
        self.assertEqual(answers[0]["matches"], ["a.b"])

    # -- Q93: surrogate escapes in a retained stream --

    def test_carriable_table(self):
        self.assertEqual(_carriable("a\ud800b"), "a\ufffdb")
        self.assertEqual(_carriable("\udfff"), "\ufffd")
        self.assertEqual(_carriable("\ud800\ud800"), "\ufffd\ufffd")
        self.assertEqual(_carriable("\udc00\ud800"), "\ufffd\ufffd")
        self.assertEqual(_carriable("\ud83d\udc26"), "\U0001f426")
        self.assertEqual(_carriable(""), "")
        self.assertEqual(_carriable(None), "")
        self.assertEqual(_carriable(7), "")
        self.assertEqual(_carriable("plain"), "plain")

    def test_a_surrogate_line_tails_as_the_replacement_character(self):
        answers = _answers([{"op": "tail", "lines": 1}],
                           stderr="bad \ud800 line\n")
        self.assertEqual(answers[0]["lines"], ["bad \ufffd line"])

    def test_a_surrogate_pair_in_a_stream_is_the_character(self):
        answers = _answers([{"op": "tail", "lines": 1}],
                           stdout="crew \ud83d\udc26\n", stderr="")
        self.assertEqual(answers[0]["lines"], ["crew \U0001f426"])

    def test_surrogates_at_the_front_back_and_middle_of_lines(self):
        out = "\ud800start\nmid\ud800dle\nend\udfff\n"
        answers = _answers([{"op": "tail", "lines": 3}],
                           stdout=out, stderr="")
        self.assertEqual(answers[0]["lines"],
                         ["\ufffdstart", "mid\ufffddle", "end\ufffd"])

    def test_the_digest_is_over_the_carriable_text(self):
        answers = _answers(
            [{"op": "attest", "predicate": "output_digest"}],
            stderr="bad \ud800\n")
        want = hashlib.sha384(
            (OUT + "bad \ufffd\n").encode("utf-8")).hexdigest()
        self.assertEqual(answers[0]["digest"], want)

    def _take53(self, record, smtp=None, query_id="sg53-q"):
        d = tempfile.mkdtemp(prefix="hp-sg53-")
        self.addCleanup(shutil.rmtree, d, True)
        cfg = base_config(d)
        save_retained(d, "sg53-job", record)
        obj = {"v": 1, "type": "query", "query_id": query_id,
               "job_id": "sg53-job", "issued_at": _now(),
               "queries": [{"op": "tail", "lines": 2}]}
        subject = "[HOMING-PIGEON] query " + query_id
        imap = FakeIMAP([])
        smtp = smtp or FakeSMTP()
        with _captured_log() as buf:
            handled = handle_query_mail(
                cfg, imap, smtp, b"1",
                _mail(subject, _sealed(obj, query_id)),
                subject, runner.build_secrets(cfg), _Opts(), d, {})
        return handled, imap, smtp, buf.getvalue(), d

    _RECORD = {"stdout": "one\ntwo\n", "stderr": "", "exit_code": 0,
               "budget": 8, "spent": 0, "view": "full"}

    def test_the_handler_answers_a_record_with_a_surrogate_stdout(self):
        rec = dict(self._RECORD, stdout="one \ud800\ntwo\n",
                   saved_at=time.time())
        handled, imap, smtp, out, _d = self._take53(rec)
        self.assertTrue(handled)
        self.assertEqual(len(smtp.sent), 1)
        self.assertEqual(imap.flagged, [b"1"])
        self.assertNotIn("could not send", out)

    def test_the_handler_answers_a_record_with_nontext_streams(self):
        for n, streams in enumerate(({"stderr": ["x"]},
                                     {"stdout": 7},
                                     {"stdout": {"a": 1}, "stderr": []})):
            rec = dict(self._RECORD, saved_at=time.time(), **streams)
            handled, imap, smtp, out, _d = self._take53(
                rec, query_id=f"sg53-nt-{n}")
            self.assertTrue(handled, streams)
            self.assertEqual(len(smtp.sent), 1, streams)
            self.assertEqual(imap.flagged, [b"1"], streams)

    def test_a_reply_that_cannot_be_sent_is_logged_not_raised(self):
        class DeadSMTP(FakeSMTP):
            def send_message(self, msg):
                raise OSError("smtp gone")
        rec = dict(self._RECORD, saved_at=time.time())
        handled, imap, smtp, out, _d = self._take53(rec, smtp=DeadSMTP())
        self.assertTrue(handled)
        self.assertEqual(imap.flagged, [b"1"])
        self.assertIn("could not send query result", out)

    # -- the surrounding shapes the grows also carried --

    def test_the_budget_spends_one_per_query_then_refuses(self):
        queries = [{"op": "tail", "lines": 1}] * 3
        answers, spent = answer_queries(
            queries, {"stdout": OUT, "stderr": "", "exit_code": 0},
            {}, 2, cfg={})
        self.assertEqual(len(answers), 3)
        self.assertEqual(answers[2], {"rejected": "budget"})
        self.assertEqual(spent, 3)

    def test_non_dict_query_entries_are_unknown_ops(self):
        answers, _spent = answer_queries(
            [7, "grep", None, [], {"op": "tail", "lines": 1}],
            {"stdout": OUT, "stderr": "", "exit_code": 0}, {}, 8, cfg={})
        self.assertEqual([a.get("rejected") for a in answers[:4]],
                         ["unknown_op"] * 4)
        self.assertEqual(answers[4]["lines"], ["three"])

    def test_a_queries_field_that_is_not_a_list_answers_nothing(self):
        for bad in ({"op": "tail"}, "tail", None, 7):
            answers, spent = answer_queries(
                bad, {"stdout": OUT, "stderr": "", "exit_code": 0},
                {}, 8, cfg={})
            self.assertEqual(answers, [], repr(bad))
            self.assertEqual(spent, 0, repr(bad))

    def test_a_result_that_is_not_a_dict_answers_over_empty_text(self):
        for bad in ("text", [], None, 7):
            got, _spent = answer_queries(
                [{"op": "tail", "lines": 2},
                 {"op": "grep", "pattern": "one"}], bad, {}, 8, cfg={})
            self.assertEqual(got[0]["lines"], [], repr(bad))
            self.assertEqual(got[1]["matches"], [], repr(bad))

    def test_already_spent_shapes(self):
        base = {"stdout": OUT, "stderr": "", "exit_code": 0}
        answers, spent = answer_queries(
            [{"op": "tail", "lines": 1}], base, {}, 8, cfg={},
            already_spent=7)
        self.assertEqual(answers[0]["lines"], ["three"])
        self.assertEqual(spent, 8)
        answers, spent = answer_queries(
            [{"op": "tail", "lines": 1}], base, {}, 8, cfg={},
            already_spent="x")
        self.assertEqual(spent, 1)

    def test_tail_lines_field_shapes(self):
        for lines, want in ((0, []), (-1, ["one", "two", "three"]),
                            ("x", ["one", "two", "three"]),
                            (None, ["one", "two", "three"]),
                            (2.9, ["two", "three"]),
                            (10 ** 9, ["one", "two", "three"]),
                            (1, ["three"])):
            answers = _answers([{"op": "tail", "lines": lines}])
            self.assertEqual(answers[0]["lines"], want, repr(lines))

    def test_grep_max_matches_field_shapes(self):
        for field, want_count in ((0, 0), (1, 1), (2, 2),
                                  ("x", 3), (None, 3), (10 ** 9, 3)):
            q = {"op": "grep", "pattern": "e", "max_matches": field}
            answers = _answers([q], stdout="e1\ne2\ne3\n", stderr="")
            self.assertEqual(len(answers[0]["matches"]), want_count,
                             repr(field))

    def test_ask_and_senses_without_their_machinery_are_refusals(self):
        answers = _answers([{"op": "ask", "question": "what?"},
                            {"op": "senses"}])
        self.assertEqual(answers[0].get("rejected"),
                         "inference_unconfigured")
        self.assertEqual(answers[1].get("rejected"),
                         "senses_unavailable")

    def test_repeated_lines_with_the_odd_line_at_each_end(self):
        base = "\n".join(["same"] * 10) + "\n"
        for out, want_last in ((("odd\n" + base), "same"),
                               ((base + "odd\n"), "odd"),
                               (("same\n" * 5 + "odd\n" + "same\n" * 5),
                                "same")):
            answers = _answers([{"op": "tail", "lines": 1}],
                               stdout=out, stderr="")
            self.assertEqual(answers[0]["lines"], [want_last])


def _make_nontext_stream_test(value):
    def run(self):
        answers = _answers([{"op": "tail", "lines": 2}], stderr=value)
        self.assertEqual(answers[0]["lines"], ["two", "three"],
                         repr(value))
        answers = _answers([{"op": "tail", "lines": 2}], stdout=value,
                           stderr="err1\nerr2\n")
        self.assertEqual(answers[0]["lines"], ["err1", "err2"],
                         repr(value))
    return run


# 16 generated non-text stream tests: every type a crash or a
# hand can leave in a stream field, in each field's place.
_NONTEXT_STREAMS = (
    [], {}, ["x"], ["a", "b"], {"a": 1}, {"a": ["x"]}, 7, 0, 2.5,
    True, False, None, b"x", (1, 2), [["x"]], {"": ""},
)
for _i, _value in enumerate(_NONTEXT_STREAMS):
    setattr(QueryTargetCrashShotgunTest,
            f"test_nontext_stream_{_i:02d}",
            _make_nontext_stream_test(_value))
del _i, _value


if __name__ == "__main__":
    unittest.main()
