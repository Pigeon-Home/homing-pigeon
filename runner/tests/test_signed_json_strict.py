# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""A signed body refuses duplicate member names and is nesting-
scanned before it is parsed (S1).

Duplicate names in one object were last-value-wins: no
object_pairs_hook was passed, so two readers of one signed body
could disagree about which value a name carries -- a parser
differential at a security boundary (RFC 8259 section 4 says names
SHOULD be unique and that non-unique names make receiver behaviour
unpredictable). The nesting bound was likewise only measured on
the parsed value, after json.loads had already recursed as deep
as the body asked; loads_signed now counts bracket depth on the
raw text first, so the parser never recurses past the bound.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.guard import textutil as TU  # noqa: E402

loads_signed = TU.loads_signed
LIMIT = TU.NESTING_LIMIT


class DuplicateNamesTest(unittest.TestCase):
    def assert_duplicate(self, text, key):
        with self.assertRaises(ValueError) as caught:
            loads_signed(text)
        message = str(caught.exception)
        self.assertIn("duplicate", message)
        self.assertIn(key, message)

    def test_duplicate_at_the_top_level_is_refused_and_named(self):
        self.assert_duplicate('{"a": 1, "b": 2, "a": 3}', "a")

    def test_duplicate_nested_in_an_object_is_refused(self):
        self.assert_duplicate('{"outer": {"x": 1, "x": 2}}', "x")

    def test_duplicate_in_an_object_inside_an_array_is_refused(self):
        self.assert_duplicate('{"list": [1, {"k": 1, "k": 2}, 3]}', "k")
        self.assert_duplicate('[{"k": 1, "k": 2}]', "k")

    def test_the_same_name_in_different_objects_is_not_a_duplicate(self):
        body = '{"a": {"k": 1}, "b": [{"k": 2}, {"k": 3}], "k": 4}'
        self.assertEqual(loads_signed(body),
                         {"a": {"k": 1}, "b": [{"k": 2}, {"k": 3}],
                          "k": 4})

    def test_names_differing_only_by_case_are_not_duplicates(self):
        # JSON member names are compared as the strings they are;
        # "a" and "A" are two names, not one name twice.
        self.assertEqual(loads_signed('{"a": 1, "A": 2}'),
                         {"a": 1, "A": 2})

    def test_a_unicode_escaped_spelling_of_a_name_is_a_duplicate(self):
        # json decodes the escapes in a member name before the
        # pairs hook sees it, so "a" and its escaped spelling
        # (backslash-u 0061) arrive as the same name and are
        # refused as duplicates. Pinned because the raw spellings
        # differ: the comparison is on the decoded name, which is
        # what every other reader compares.
        self.assert_duplicate('{"a": 1, "\\u0061": 2}', "a")

    def test_duplicate_names_bookended_with_symbols(self):
        # The bookend family for this surface: the duplicated name
        # itself carries the symbols, at the front and the back.
        for key in ("-a-", ";a;", "--a--", " a ", "[]a{}", "a-", "-a"):
            text = '{"%s": 1, "%s": 2}' % (key, key)
            self.assert_duplicate(text, key)
        # A quote and a tab inside a name travel escaped in the
        # raw text; decoded, they are still the one name twice.
        self.assert_duplicate('{"\\"a\\"": 1, "\\"a\\"": 2}', '"a"')
        # The refusal names the key in repr form, so the tab
        # travels in the message as its escape, not a raw tab.
        with self.assertRaises(ValueError) as caught:
            loads_signed('{"\\ta": 1, "\\ta": 2}')
        self.assertIn("duplicate", str(caught.exception))
        self.assertIn("'\\ta'", str(caught.exception))

    def test_duplicate_empty_string_name_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            loads_signed('{"": 1, "": 2}')
        self.assertIn("duplicate", str(caught.exception))
        self.assertIn("''", str(caught.exception))

    def test_duplicate_very_long_name_is_refused_and_named(self):
        key = "k" * 5000
        self.assert_duplicate('{"%s": 1, "%s": 2}' % (key, key), key)

    def test_an_empty_object_and_an_empty_name_still_parse(self):
        self.assertEqual(loads_signed("{}"), {})
        self.assertEqual(loads_signed('{"": 1}'), {"": 1})
        self.assertEqual(loads_signed("[]"), [])


class UnchangedBodiesTest(unittest.TestCase):
    def test_non_duplicate_bodies_parse_identically(self):
        cases = (
            ('{"v": 1, "type": "job", "n": -0, "f": 1.5e3,'
             ' "t": true, "u": null}', {"v": 1, "type": "job", "n": 0,
                                        "f": 1500.0, "t": True,
                                        "u": None}),
            ('[1, "two", [3], {"four": 4}]',
             [1, "two", [3], {"four": 4}]),
            ('"plain"', "plain"),
            ('{"nested": {"deep": {"deeper": [true, false]}}}',
             {"nested": {"deep": {"deeper": [True, False]}}}),
        )
        for text, expected in cases:
            self.assertEqual(loads_signed(text), expected, text)

    def test_the_existing_refusals_still_fire(self):
        for text in ('{"x": NaN}', '{"x": Infinity}', '{"x": 1e400}'):
            with self.assertRaises(ValueError, msg=text):
                loads_signed(text)


class NestingPreScanTest(unittest.TestCase):
    def test_a_raw_wall_of_brackets_is_refused_as_nesting(self):
        # 5000 open brackets with no parseable body at all: the
        # refusal must be the nesting ValueError from the pre-scan,
        # not a RecursionError and not a syntax error the parser
        # reaches first by recursing.
        text = "[" * 5000 + "]" * 5000
        with self.assertRaises(ValueError) as caught:
            loads_signed(text)
        self.assertIn("nests deeper than", str(caught.exception))
        self.assertIn(str(LIMIT), str(caught.exception))

    def test_brackets_just_past_the_limit_are_refused(self):
        text = "[" * (LIMIT + 1) + "1" + "]" * (LIMIT + 1)
        with self.assertRaisesRegex(ValueError, "nests deeper than"):
            loads_signed(text)
        text = '{"a":' * (LIMIT + 1) + "1" + "}" * (LIMIT + 1)
        with self.assertRaisesRegex(ValueError, "nests deeper than"):
            loads_signed(text)

    def test_nesting_at_the_limit_still_parses(self):
        text = "[" * LIMIT + "1" + "]" * LIMIT
        value = loads_signed(text)
        depth = 0
        while isinstance(value, list):
            depth += 1
            value = value[0]
        self.assertEqual(depth, LIMIT)
        self.assertEqual(value, 1)

    def test_nesting_under_the_limit_still_parses(self):
        text = '{"a":' * 50 + "1" + "}" * 50
        value = loads_signed(text)
        for _ in range(50):
            value = value["a"]
        self.assertEqual(value, 1)

    def test_brackets_inside_strings_do_not_count(self):
        # A string may carry any brackets at all; only the brackets
        # that open a container count toward the depth.
        wall = "[" * 5000 + "]" * 5000 + "{" * 5000 + "}" * 5000
        self.assertEqual(loads_signed('{"note": "%s"}' % wall),
                         {"note": wall})

    def test_an_escaped_quote_does_not_end_the_string_for_the_scan(self):
        # The \" inside the string is text, so the brackets after
        # it are still inside the string and do not count; the
        # brackets after the string really closes do.
        text = '{"note": "a\\" ' + "[" * 5000 + '", "x": 1}'
        self.assertEqual(loads_signed(text)["x"], 1)
        deep = ('{"note": "a\\" b", "deep": '
                + "[" * (LIMIT + 1) + "1" + "]" * (LIMIT + 1) + "}")
        with self.assertRaisesRegex(ValueError, "nests deeper than"):
            loads_signed(deep)

    def test_an_escaped_backslash_before_a_quote_for_the_scan(self):
        # "a\\" is a string holding one backslash: the quote after
        # the doubled backslash really closes it, so the deep
        # brackets that follow are containers and are refused.
        deep = ('{"note": "a\\\\", "deep": '
                + "[" * (LIMIT + 1) + "1" + "]" * (LIMIT + 1) + "}")
        with self.assertRaisesRegex(ValueError, "nests deeper than"):
            loads_signed(deep)


if __name__ == "__main__":
    unittest.main()
