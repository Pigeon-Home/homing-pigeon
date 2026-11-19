#!/usr/bin/env python3
"""The opener search reads a body a bounded number of times
(finding F10 of the v4 binding work, 2026-11-18).

A signed body is a JSON object whose last brace was replaced by
the signature. To find the object's first brace the verifier
tries every brace the walk passes, newest first, and takes the
first whose text parses. It used to copy, clean and parse the
text from each candidate to the marker. A body made of `{\\"`
repeated makes every brace a candidate that fails at its second
character, so the cost was candidates times length, before any
MAC: an unsigned 48 KB body held the verifier 15 seconds, and a
body at the 4 MiB cap would have held the mail loop for about a
day. The cost came to light when fuzz corpus text was used as a
result's streams and the verifier's time grew faster than the
text.

The search now looks at a candidate's first characters, and
passes it over there when the parse has already failed for
good. These tests hold 3 things: the answers are the old
search's on every text tried, the reading is bounded by a
count and not by a clock, and a parser that words its errors
another way costs time and never an answer. Both homes of the
search are held: runner/wire/verify.py and its copy in
runner/cloud/send_job.py.
"""
import json
import os
import random
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.cloud import send_job as SENDER  # noqa: E402
from runner.tests import test_proof_conformance as DOOR  # noqa: E402
from runner.tools import de_dust_corpus as DD  # noqa: E402
from runner.wire import verify as RUNNER_SIDE  # noqa: E402

MARK = ',"sig":"' + "a" * 96 + '"}'
# Pieces a hostile body is made of: braces, quotes and
# backslashes in every arrangement, tokens cut short, raw
# control characters, and the 2 units that make every brace a
# candidate.
PIECES = [
    '{', '}', '"', '\\"', '\\\\', '\\', '{"k":', '1,', '"a":"b",', '[', ']',
    'true', 'nul', ' ', '\n', '\t', '\\u0041', '\\ud83d', '\\u12', ':', ',',
    '{\\"', '"x', '-', '1e', '1.5', 'NaN', '-Infinity', '\x01', 'é',
    '"k":{', '}}', '{"a":1}', '"":"",', '":"', '",":']
UNITS = ['{\\"', '{"k":1,\\"', '{ \\"', '{"a":"b",\\"', '{"":\\"']


def old_search(module, norm, sig_at, both_forms):
    """The search as it stood before the look: every candidate
    read whole."""
    first = None
    for start in module._root_candidates(norm, sig_at):
        if first is None:
            first = start
        text = norm[start:sig_at] + "}"
        forms = (text, RUNNER_SIDE._strip_controls(text)) if both_forms \
            else (text,)
        for form in forms:
            try:
                candidate = json.loads(form)
            except (ValueError, RecursionError):
                continue
            if isinstance(candidate, dict):
                return start
            break
    if first is not None:
        return first
    raise ValueError("no JSON object before signature")


HOMES = ((RUNNER_SIDE, True), (SENDER, False))


def answer(search, *args):
    try:
        return search(*args)
    except ValueError:
        return "refused"


def hostile(rng):
    """1 body before its marker: loose pieces, or a real object
    with hostile strings behind a preamble, or a run of units."""
    kind = rng.random()
    if kind < 0.5:
        return "".join(rng.choice(PIECES)
                       for _ in range(rng.randrange(1, 60)))
    if kind < 0.8:
        strings = ["".join(rng.choice(PIECES)
                           for _ in range(rng.randrange(0, 30)))
                   for _ in range(3)]
        inner = json.dumps(
            {"v": 1, "k": strings[0],
             strings[1][:20] or "x": {"n": [strings[2], 1, None]}},
            separators=(",", ":"), ensure_ascii=bool(rng.getrandbits(1)))
        body = inner[:-1]
        if rng.random() < 0.6:
            body = "".join(rng.choice(PIECES)
                           for _ in range(rng.randrange(0, 12))) + body
        if rng.random() < 0.3:
            cut = rng.randrange(len(body) + 1)
            body = body[:cut] + rng.choice(
                ["\n", "\x02", "\t", '"', "{", "\\"]) + body[cut:]
        return body
    unit = rng.choice(UNITS)
    return "".join(rng.choice([unit, unit, unit, rng.choice(PIECES)])
                   for _ in range(rng.randrange(1, 80))) + '"'


class _Counted:
    """The json module as the search sees it, counting the
    characters handed to the parser."""

    def __init__(self):
        self.read = 0
        self.JSONDecodeError = json.JSONDecodeError
        self.dumps = json.dumps
        # Taken now: this module's own json is the name patched
        # when the old search is the one counted.
        self._parse = json.loads

    def loads(self, text, *args, **kwargs):
        self.read += len(text)
        return self._parse(text, *args, **kwargs)


def characters_read(search, module, norm, sig_at):
    counted = _Counted()
    with mock.patch.object(module, "json", counted):
        answer(search, norm, sig_at)
    return counted.read


def body_of(unit, size):
    norm = unit * (size // len(unit)) + '"' + MARK
    return norm, norm.rfind(',"sig":"')


class SameAnswers(unittest.TestCase):
    """The look changes the cost and no answer."""

    def test_the_old_search_s_answer_on_every_random_text(self):
        rng = random.Random(20261118)
        found = refused = 0
        for _ in range(20000):
            norm = RUNNER_SIDE._normalize(hostile(rng) + MARK)
            sig_at = norm.rfind(',"sig":"')
            # The first look's size moves, so a token is cut at
            # every distance from a look's edge.
            look = rng.choice((17, 20, 24, 32, 48, 64))
            for module, both_forms in HOMES:
                want = answer(old_search, module, norm, sig_at, both_forms)
                with mock.patch.object(module, "_OPENER_FIRST_LOOK", look):
                    got = answer(module._object_start, norm, sig_at)
                self.assertEqual(want, got, (module.__name__, look, norm))
            found += want != "refused"
            refused += want == "refused"
        self.assertGreater(found, 5000)
        self.assertGreater(refused, 2000)

    def test_the_old_search_s_answer_on_every_corpus_text_with_a_marker(self):
        seen = 0
        for target in sorted(DD.TARGETS):
            for entry in DD.load(DD.corpus_path(target)):
                data = entry.get("data")
                texts = [data] if isinstance(data, str) else [
                    json.dumps(data, ensure_ascii=False), json.dumps(data)]
                if isinstance(data, dict):
                    texts += [v for v in data.values() if isinstance(v, str)]
                for text in texts:
                    norm = RUNNER_SIDE._normalize(text).rstrip()
                    sig_at = norm.rfind(',"sig":"')
                    if sig_at < 0:
                        continue
                    seen += 1
                    for module, both_forms in HOMES:
                        self.assertEqual(
                            answer(old_search, module, norm, sig_at,
                                   both_forms),
                            answer(module._object_start, norm, sig_at),
                            (target, entry["id"]))
        self.assertGreater(seen, 400)

    def test_a_signed_job_full_of_the_hostile_units_is_taken_whole(self):
        # The units as a script's text, behind a preamble that
        # carries them too: the search still finds the 1 brace
        # that opens the signed object, and the MAC decides.
        script = "".join(UNITS) * 400
        job = DOOR._job2("g-open-1", kind="exec", script=script)
        signed = RUNNER_SIDE.sign_payload(job, DOOR.SECRET)
        for preamble in ("", "note {\\\" {\\\" \"\n", "{ \\\"" * 50 + "\"\n"):
            got, key_id = RUNNER_SIDE.verify_body_keyed(
                preamble + signed, {"": DOOR.SECRET})
            self.assertEqual(script, got["script"])
            self.assertEqual("", key_id)
            self.assertEqual(
                script, SENDER.verify_body(preamble + signed,
                                           DOOR.SECRET)["script"])

    def test_a_parser_that_words_its_errors_another_way_costs_no_answer(self):
        # With no error taken as settled the looks decide nothing
        # and every candidate goes to the full parse, as before.
        rng = random.Random(7)
        for _ in range(2000):
            norm = RUNNER_SIDE._normalize(hostile(rng) + MARK)
            sig_at = norm.rfind(',"sig":"')
            for module, both_forms in HOMES:
                with mock.patch.object(module, "_OPENER_SETTLED", ()):
                    self.assertEqual(
                        answer(old_search, module, norm, sig_at, both_forms),
                        answer(module._object_start, norm, sig_at))
        # And the cost is the old cost again, with the looks on top.
        norm, sig_at = body_of(UNITS[0], 3000)
        for module, _ in HOMES:
            with mock.patch.object(module, "_OPENER_SETTLED", ()):
                unsettled = characters_read(module._object_start, module,
                                            norm, sig_at)
            self.assertGreater(unsettled, 400 * len(norm), module.__name__)


class BoundedReading(unittest.TestCase):
    """The cost, as a count of characters handed to the parser."""

    def test_a_body_of_candidates_is_read_a_bounded_number_of_times(self):
        for unit in UNITS[:2]:
            for size in (3000, 12000, 48000):
                norm, sig_at = body_of(unit, size)
                candidates = sum(1 for _ in RUNNER_SIDE._root_candidates(
                    norm, sig_at))
                # Every brace is a candidate: the worst a body
                # of this size can be.
                self.assertEqual(norm.count("{"), candidates)
                self.assertGreater(candidates, size // 12)
                for module, _ in HOMES:
                    read = characters_read(module._object_start, module,
                                           norm, sig_at)
                    self.assertLessEqual(read, 16 * len(norm),
                                         (module.__name__, unit, size))

    def test_the_old_search_read_the_same_body_hundreds_of_times(self):
        norm, sig_at = body_of(UNITS[0], 3000)
        for module, both_forms in HOMES:
            old = characters_read(
                lambda n, s: old_search(module, n, s, both_forms),
                sys.modules[__name__], norm, sig_at)
            new = characters_read(module._object_start, module, norm, sig_at)
            self.assertGreater(old, 400 * len(norm), module.__name__)
            self.assertLess(new, 16 * len(norm), module.__name__)

    def test_the_reading_grows_with_the_body_and_not_with_its_square(self):
        for module, _ in HOMES:
            small = characters_read(module._object_start, module,
                                    *body_of(UNITS[0], 6000))
            large = characters_read(module._object_start, module,
                                    *body_of(UNITS[0], 48000))
            # 8 times the body is 8 times the reading. The old
            # search's reading grew 64 times.
            self.assertLess(large, 9 * small, module.__name__)

    def test_the_gate_and_the_sender_s_reader_refuse_the_body(self):
        norm, _ = body_of(UNITS[0], 48000)
        with self.assertRaises(ValueError):
            RUNNER_SIDE.verify_body_keyed(norm, {"": DOOR.SECRET})
        with self.assertRaises(ValueError):
            SENDER.verify_body(norm, DOOR.SECRET)
        raw = (b"Subject: [HOMING-PIGEON] job g-open-2\r\n"
               b"From: si@example.com\r\n\r\n" + norm.encode("ascii"))
        out = DOOR._run(raw=raw)
        self.assertEqual([], out.executed)
        self.assertTrue(any("bad signature" in note for note in out.notes),
                        out.notes)


class TheLook(unittest.TestCase):
    """What the look may settle, and what it must leave."""

    def test_the_2_homes_carry_the_same_look(self):
        for name in ("_OPENER_FIRST_LOOK", "_OPENER_LOOK_GROWTH",
                     "_OPENER_EDGE", "_OPENER_SETTLED"):
            self.assertEqual(getattr(RUNNER_SIDE, name),
                             getattr(SENDER, name), name)
        self.assertGreater(RUNNER_SIDE._OPENER_FIRST_LOOK,
                           RUNNER_SIDE._OPENER_EDGE)
        self.assertGreater(RUNNER_SIDE._OPENER_LOOK_GROWTH, 1)

    def test_this_parser_words_the_settled_errors_as_the_search_expects(self):
        settled = RUNNER_SIDE._OPENER_SETTLED
        for text in ('{\\"', '{ x', '{"a" 1}', '{"a":1 "b"}', '{"a":-}',
                     '{"a":"\\x"}', '{"a":1}x', '{"a":"\t"}'):
            with self.assertRaises(json.JSONDecodeError) as caught:
                json.loads(text)
            self.assertTrue(caught.exception.msg.startswith(settled), text)

    def test_a_string_that_runs_off_the_look_is_never_settled(self):
        with self.assertRaises(json.JSONDecodeError) as caught:
            json.loads('{"a')
        self.assertFalse(
            caught.exception.msg.startswith(RUNNER_SIDE._OPENER_SETTLED))
        # A first string longer than any early look, with braces
        # in it: the look grows and the object is found.
        norm = '{"' + "{x" * 5000 + '":1' + MARK
        sig_at = norm.rfind(',"sig":"')
        for module, _ in HOMES:
            self.assertTrue(module._opens_object(norm, 0, sig_at))
            self.assertEqual(0, module._object_start(norm, sig_at))

    def test_an_error_at_a_look_s_edge_is_left_to_a_longer_look(self):
        # Every prefix of a sound object, as the look would cut
        # it: none is settled as an error.
        sound = ('{"a":true,"b":[null,-1.5e+10,"\\u00e9\\ud83d\\ude00"],'
                 '"c":{"d":false,"e":"x y"},"f":-Infinity,"g":NaN,"h":1}')
        self.assertIsInstance(json.loads(sound), dict)
        norm = sound[:-1] + MARK
        sig_at = norm.rfind(',"sig":"')
        for module, _ in HOMES:
            for look in range(17, len(sound) + 20):
                with mock.patch.object(module, "_OPENER_FIRST_LOOK", look):
                    self.assertTrue(module._opens_object(norm, 0, sig_at),
                                    (module.__name__, look))
                    self.assertEqual(0, module._object_start(norm, sig_at))

    def test_the_runner_s_look_is_cleaned_as_the_search_cleans(self):
        rng = random.Random(3)
        for _ in range(400):
            text = "".join(chr(rng.randrange(0, 40)) for _ in range(60))
            self.assertEqual(RUNNER_SIDE._strip_controls(text),
                             RUNNER_SIDE._RAW_CONTROLS.sub("", text))
        # A raw control character inside a string fails the text
        # as received and passes it cleaned: the runner's look,
        # cleaned, does not settle against it. The sender's
        # reader takes the text as received only, as it did.
        norm = '{"k":"a\x02b' + "c" * 80 + '"' + MARK
        sig_at = norm.rfind(',"sig":"')
        self.assertTrue(RUNNER_SIDE._opens_object(norm, 0, sig_at))
        self.assertEqual(0, RUNNER_SIDE._object_start(norm, sig_at))
        self.assertFalse(SENDER._opens_object(norm, 0, sig_at))

    def test_a_candidate_nested_past_the_parser_is_settled_by_its_look(self):
        # Each unit opens an object and nests arrays deeper than
        # the parser follows, then hides the next unit in a
        # string. Every brace is a candidate, and none is read
        # whole.
        deep = 30000
        unit = '{"a":' + "[" * deep + '\\"'
        norm = unit * 6 + '"' + MARK
        sig_at = norm.rfind(',"sig":"')
        self.assertEqual(6, sum(1 for _ in RUNNER_SIDE._root_candidates(
            norm, sig_at)))
        with self.assertRaises(RecursionError):
            json.loads(unit[:-2] + "]" * deep + "}")
        for module, both_forms in HOMES:
            self.assertEqual(
                answer(old_search, module, norm, sig_at, both_forms),
                answer(module._object_start, norm, sig_at))
            read = characters_read(module._object_start, module, norm,
                                   sig_at)
            self.assertLess(read, 2 * len(norm), module.__name__)


if __name__ == "__main__":
    unittest.main()
