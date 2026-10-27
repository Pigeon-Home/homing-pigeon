# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""A signed body is JSON and no more (Q89): the literals NaN and
Infinity are a parser's extensions, a number too large for a double
is not a number the reader can carry, and the object nests at most
200 levels (the object itself the first). Before this, both
verifiers read NaN and Infinity into a job, the runner's verifier
walked a body only 200 levels down and accepted a lone surrogate
below that, and the front-end's verifier either refused the same
body or raised a RecursionError on a deeper one, so the two readers
of one body disagreed. All three doors -- the runner's two readers
and the front-end's -- refuse the same bodies with the same words
now, and the nesting is measured without recursion."""

import hashlib
import hmac
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.cloud import send_job as SJ  # noqa: E402
from runner.guard import textutil as TU  # noqa: E402
from runner.wire import verify as V  # noqa: E402

SECRET = "5e0f3c2a9b8d7e6f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7081"
HEAD = '{"v":1,"type":"job","job_id":"bm-b-0001","kind":"exec",'


def _signed(text):
    sig = hmac.new(SECRET.encode("utf-8"), text.encode("utf-8"),
                   hashlib.sha384).hexdigest()
    return text[:-1] + ',"sig":"' + sig + '"}'


def _nested(depth, leaf="1", opener="[", closer="]"):
    return HEAD + '"deep":' + opener * depth + leaf + closer * depth + "}"


DOORS = (
    ("verify_body", lambda b: V.verify_body(b, SECRET)),
    ("verify_body_keyed", lambda b: V.verify_body_keyed(b, {"": SECRET})[0]),
    ("send_job.verify_body", lambda b: SJ.verify_body(b, SECRET)),
)


class NumbersTest(unittest.TestCase):
    def test_the_literals_are_refused_by_name(self):
        for literal in ("NaN", "Infinity", "-Infinity"):
            body = _signed(HEAD + '"x":' + literal + "}")
            for name, door in DOORS:
                with self.assertRaisesRegex(
                        ValueError, f"carries {literal}, which is not JSON",
                        msg=f"{name}: {literal}"):
                    door(body)

    def test_a_number_that_overflows_is_refused(self):
        for text in ("1e400", "-1e400", "[1, 2e999]", '{"a": 1E309}'):
            body = _signed(HEAD + '"x":' + text + "}")
            for name, door in DOORS:
                with self.assertRaisesRegex(ValueError, "not finite",
                                            msg=f"{name}: {text}"):
                    door(body)

    def test_finite_numbers_still_read(self):
        body = _signed(HEAD + '"x":1.7976931348623157e308,"y":-1e308,'
                       '"z":5e-324,"n":-0,"i":12345678901234567890}')
        for name, door in DOORS:
            job = door(body)
            self.assertEqual(job["x"], 1.7976931348623157e308, name)
            self.assertEqual(job["z"], 5e-324, name)
            self.assertEqual(job["i"], 12345678901234567890, name)

    def test_the_text_nan_is_text(self):
        body = _signed(HEAD + '"note":"NaN and Infinity"}')
        for _name, door in DOORS:
            self.assertEqual(door(body)["note"], "NaN and Infinity")


class NestingTest(unittest.TestCase):
    def test_the_bound_is_two_hundred_levels_counting_the_object(self):
        at = _signed(_nested(199))
        past = _signed(_nested(200))
        for name, door in DOORS:
            self.assertEqual(door(at)["job_id"], "bm-b-0001", name)
            with self.assertRaisesRegex(ValueError, "nests deeper than 200",
                                        msg=name):
                door(past)

    def test_objects_count_as_lists_do(self):
        at = _signed(_nested(199, opener='{"a":', closer="}"))
        past = _signed(_nested(200, opener='{"a":', closer="}"))
        for name, door in DOORS:
            self.assertEqual(door(at)["job_id"], "bm-b-0001", name)
            with self.assertRaisesRegex(ValueError, "nests deeper than 200",
                                        msg=name):
                door(past)

    def test_a_body_of_any_depth_is_refused_not_crashed(self):
        for depth in (300, 1500, 5000):
            body = _signed(_nested(depth, leaf='"\\ud800"'))
            for name, door in DOORS:
                with self.assertRaisesRegex(ValueError, "nests deeper than",
                                            msg=f"{name}: {depth}"):
                    door(body)

    def test_a_body_the_parser_cannot_finish_is_refused_the_same_way(self):
        # Where the interpreter's C recursion limit is low (the
        # Windows build's), the parser gives up on a deep body before
        # the measure runs; the refusal is the same ValueError, not
        # the parser's RecursionError. The limit cannot be lowered
        # from here, so the parser's refusal is played.
        body = _signed(_nested(400))

        def give_up(*_a, **_k):
            raise RecursionError("maximum recursion depth exceeded")

        with mock.patch.object(TU.json, "loads", give_up), \
                mock.patch.object(SJ.json, "loads", give_up):
            for name, door in DOORS:
                with self.assertRaisesRegex(ValueError, "nests deeper than",
                                            msg=name):
                    door(body)

    def test_a_surrogate_at_the_bottom_of_the_bound_is_seen(self):
        body = _signed(_nested(199, leaf='"\\ud800"'))
        for name, door in DOORS:
            with self.assertRaisesRegex(ValueError, "unpaired UTF-16 surrogate",
                                        msg=name):
                door(body)

    def test_the_measure_itself(self):
        self.assertFalse(TU._nests_deeper_than({"a": [[1]]}, 3))
        self.assertTrue(TU._nests_deeper_than({"a": [[[1]]]}, 3))
        self.assertFalse(TU._nests_deeper_than("flat", 1))
        self.assertFalse(TU._nests_deeper_than({}, 1))
        self.assertTrue(TU._nests_deeper_than({"a": {}}, 1))
        deep = []
        cur = deep
        for _ in range(100000):
            nxt = []
            cur.append(nxt)
            cur = nxt
        self.assertTrue(TU._nests_deeper_than(deep, 200))
        self.assertTrue(SJ._nests_deeper_than(deep, 200))
        self.assertEqual(TU.NESTING_LIMIT, SJ.NESTING_LIMIT)


if __name__ == "__main__":
    unittest.main()
