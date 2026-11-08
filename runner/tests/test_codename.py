"""runner/tools/codename.py: the cs_office code-name shape, held hard.

A code name is hp<marking>-<guid> with an optional sub-name. The
marking is 0-3, the GUID is a canonical lowercase UUID4 that carries
no information, and the sub-name is lowercase [a-z0-9] segments
joined by single dashes (32 characters at most, the whole reference
128 at most). Parsing is strict and full-string: no stripping, no
near misses. These tests hold the roundtrip for every marking, the
shelf names, every named failure shape for the marking, the GUID
and the sub-name, the non-string inputs, and the bookend family:
every ASCII punctuation character at either end of a valid
reference, control characters and unicode inside it, repetition
runs, and a 10,000-character input.
"""
import contextlib
import io
import os
import string
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.tools import codename as CN  # noqa: E402

GUID = "bebd8c71-ecb9-4d68-87aa-c0dc38d118b7"
VALID = "hp1-%s" % GUID
EXAMPLE = VALID + "-a"


def _ref(marking=1, guid=GUID, sub=None):
    text = "hp%s-%s" % (marking, guid)
    if sub is not None:
        text += "-" + sub
    return text


class MintParseRoundtripTest(unittest.TestCase):
    def test_the_documented_example_parses(self):
        name = CN.parse(EXAMPLE)
        self.assertEqual(name, CN.CodeName(1, GUID, "a"))
        self.assertEqual(name.marking, 1)
        self.assertEqual(name.guid, GUID)
        self.assertEqual(name.sub, "a")
        self.assertEqual(str(name), EXAMPLE)

    def test_mint_parse_roundtrip_for_every_marking(self):
        for marking in (0, 1, 2, 3):
            for sub in (None, "a", "corpus", "stage-2"):
                with self.subTest(marking=marking, sub=sub):
                    ref = CN.mint(marking, sub)
                    name = CN.parse(ref)
                    self.assertEqual(name.marking, marking)
                    self.assertEqual(name.sub, sub)
                    self.assertEqual(str(name), ref)
                    self.assertTrue(CN.is_valid(ref))
                    self.assertEqual(CN.marking_of(ref), marking)

    def test_mint_defaults_to_public_with_no_sub(self):
        name = CN.parse(CN.mint())
        self.assertEqual(name.marking, 0)
        self.assertIsNone(name.sub)

    def test_minted_guids_are_uuid4_shaped(self):
        for _ in range(50):
            guid = CN.parse(CN.mint(3)).guid
            parts = guid.split("-")
            self.assertEqual([len(p) for p in parts], [8, 4, 4, 4, 12])
            self.assertEqual(parts[2][0], "4")
            self.assertIn(parts[3][0], "89ab")
            self.assertEqual(guid, guid.lower())

    def test_200_mints_are_all_unique_and_all_parse(self):
        refs = [CN.mint(i % 4) for i in range(200)]
        self.assertEqual(len(set(refs)), 200)
        for ref in refs:
            self.assertTrue(CN.is_valid(ref), ref)
            self.assertEqual(str(CN.parse(ref)), ref)

    def test_str_of_a_hand_built_codename_roundtrips(self):
        cases = (CN.CodeName(0, GUID, None),
                 CN.CodeName(1, GUID, "a"),
                 CN.CodeName(2, GUID, "corpus"),
                 CN.CodeName(3, GUID, "stage-2"),
                 CN.CodeName(2, GUID, "a" * 32))
        for name in cases:
            with self.subTest(name=name):
                self.assertEqual(CN.parse(str(name)), name)

    def test_mint_rejects_markings_outside_0_to_3(self):
        for marking in (4, 9, -1, 100):
            with self.subTest(marking=marking), \
                    self.assertRaises(ValueError):
                CN.mint(marking)
        for marking in ("1", 1.0, None, True, [1]):
            with self.subTest(marking=marking), \
                    self.assertRaises(TypeError):
                CN.mint(marking)

    def test_mint_rejects_bad_sub_names(self):
        for sub in ("", "Corpus", "A", "stage_2", "stage--2", "-a",
                    "a-", "a b", "a!", "a" * 33):
            with self.subTest(sub=sub), self.assertRaises(ValueError):
                CN.mint(0, sub)
        with self.assertRaises(TypeError):
            CN.mint(0, 7)


class ValidSubNameTest(unittest.TestCase):
    def test_valid_sub_shapes(self):
        for sub in ("a", "z", "0", "7", "corpus", "stage-2", "a1",
                    "a-b-c", "x9-y8-z7", "a" * 32, "s" * 30 + "-2"):
            with self.subTest(sub=sub):
                ref = _ref(2, sub=sub)
                self.assertTrue(CN.is_valid(ref), ref)
                self.assertEqual(CN.parse(ref).sub, sub)

    def test_no_sub_means_none_not_empty(self):
        self.assertIsNone(CN.parse(VALID).sub)


class InvalidMarkingTest(unittest.TestCase):
    def test_invalid_markings(self):
        bad = [_ref(4), _ref(9), _ref(5), _ref("x"), _ref("a"),
               _ref(""), _ref(10), _ref("01"), _ref("-1"),
               "hp", "hp-", "hp-%s" % GUID, "HP1-%s" % GUID,
               "Hp1-%s" % GUID, "hp1%s" % GUID, "hp1--%s" % GUID,
               "1-%s" % GUID, "p1-%s" % GUID, "hp1 -%s" % GUID]
        for ref in bad:
            with self.subTest(ref=ref):
                self.assertFalse(CN.is_valid(ref), ref)
                with self.assertRaises(ValueError):
                    CN.parse(ref)


class GuidShapeTest(unittest.TestCase):
    def test_guid_shape_failures(self):
        bad_guids = (
            GUID[:-1],                       # too short
            GUID + "a",                      # too long
            "g" + GUID[1:],                  # non-hex char
            "z" + GUID[1:],                  # non-hex char, later letter
            GUID.upper(),                    # uppercase hex
            GUID.replace("4d68", "5d68"),    # version nibble 5
            GUID.replace("4d68", "1d68"),    # version nibble 1 (v1 style)
            GUID.replace("4d68", "0d68"),    # version nibble 0
            GUID.replace("87aa", "c7aa"),    # variant c
            GUID.replace("87aa", "77aa"),    # variant 7
            GUID.replace("87aa", "07aa"),    # variant 0
            GUID.replace("-", ""),           # missing dashes
            GUID.replace("-", "", 1),        # one missing dash
            GUID.replace("-", "--", 1),      # extra dash
            "-" + GUID,                      # leading dash
            GUID + "-",                      # trailing dash on the guid
            GUID.replace("ecb9", "ecb"),     # a short group
            GUID.replace("ecb9", "ecb99"),   # a long group
            "bebd8c71-ecb9-11d6-87aa-c0dc38d118b7",  # a v1-style uuid
            "bebd8c71ecb94d6887aac0dc38d118b7",      # no dashes at all
            "",                              # no guid
        )
        for guid in bad_guids:
            with self.subTest(guid=guid):
                ref = _ref(1, guid=guid)
                self.assertFalse(CN.is_valid(ref), ref)
                with self.assertRaises(ValueError):
                    CN.parse(ref)

    def test_every_version_and_variant_nibble(self):
        for nibble in "012356789abcdef":
            with self.subTest(version=nibble):
                guid = GUID.replace("4d68", nibble + "d68")
                self.assertFalse(CN.is_valid(_ref(1, guid=guid)))
        for nibble in "01234567cdef":
            with self.subTest(variant=nibble):
                guid = GUID.replace("87aa", nibble + "7aa")
                self.assertFalse(CN.is_valid(_ref(1, guid=guid)))
        for nibble in "89ab":
            with self.subTest(variant=nibble):
                guid = GUID.replace("87aa", nibble + "7aa")
                self.assertTrue(CN.is_valid(_ref(1, guid=guid)))


class SubNameFailureTest(unittest.TestCase):
    def test_sub_name_failures(self):
        bad_subs = ("", "Corpus", "A", "CORPUS", "stage_2", "a_b",
                    "stage--2", "stage-", "-stage", "stage!", "a$b",
                    "a.b", "a/b", "a b", "a--b", "é", "a" * 33,
                    "a" * 100, "a-" * 20)
        for sub in bad_subs:
            with self.subTest(sub=sub):
                ref = VALID + "-" + sub
                self.assertFalse(CN.is_valid(ref), ref)
                with self.assertRaises(ValueError):
                    CN.parse(ref)

    def test_empty_sub_is_a_trailing_dash(self):
        self.assertFalse(CN.is_valid(VALID + "-"))
        with self.assertRaises(ValueError):
            CN.parse(VALID + "-")

    def test_sub_at_the_cap_passes_and_one_over_fails(self):
        self.assertTrue(CN.is_valid(VALID + "-" + "a" * 32))
        self.assertFalse(CN.is_valid(VALID + "-" + "a" * 33))

    def test_total_reference_over_the_cap_fails(self):
        ref = VALID + "-" + "a" * 100
        self.assertGreater(len(ref), 128)
        self.assertFalse(CN.is_valid(ref))
        with self.assertRaises(ValueError):
            CN.parse(ref)


class BookendAndEdgeFuzzTest(unittest.TestCase):
    """Every ASCII punctuation character, at the front and the back.

    The bookend rule: edges are where parsers disagree, so a valid
    reference wrapped in any symbol at either end must stop being
    valid -- including the dash, which would read as an (empty or
    extended) sub-name, and including characters a lenient parser
    might strip or ignore.
    """

    def test_every_ascii_punctuation_char_bookends_to_invalid(self):
        chars = "".join(chr(i) for i in range(33, 127)
                        if not chr(i).isalnum())
        # The sweep really is the whole ASCII symbol set.
        self.assertEqual(set(chars), set(string.punctuation))
        for ch in chars:
            with self.subTest(prefix=ch):
                self.assertFalse(CN.is_valid(ch + VALID), ch + VALID)
            with self.subTest(suffix=ch):
                self.assertFalse(CN.is_valid(VALID + ch), VALID + ch)

    def test_every_ascii_punctuation_char_inside_is_invalid(self):
        for ch in string.punctuation:
            with self.subTest(ch=ch):
                broken = VALID[:12] + ch + VALID[12:]
                self.assertFalse(CN.is_valid(broken), broken)

    def test_empty_and_whitespace_only(self):
        for ref in ("", " ", "   ", "\t", "\n", "\r\n", " \t \n "):
            with self.subTest(ref=ref):
                self.assertFalse(CN.is_valid(ref))
                with self.assertRaises(ValueError):
                    CN.parse(ref)

    def test_surrounding_whitespace_is_not_stripped(self):
        for ref in (" " + VALID, VALID + " ", "\t" + VALID,
                    VALID + "\n", "  " + EXAMPLE + "  "):
            with self.subTest(ref=ref):
                self.assertFalse(CN.is_valid(ref))
                with self.assertRaises(ValueError):
                    CN.parse(ref)

    def test_control_characters_inside(self):
        for ch in ("\x00", "\t", "\r", "\n", "\x0b", "\x0c", "\x7f"):
            with self.subTest(ch=repr(ch)):
                broken = VALID[:20] + ch + VALID[20:]
                self.assertFalse(CN.is_valid(broken))
                self.assertFalse(CN.is_valid(ch + VALID))
                self.assertFalse(CN.is_valid(VALID + ch))

    def test_unicode_letters_and_an_emoji_inside(self):
        for ref in (VALID + "-café", _ref(1, sub="über"),
                    VALID[:10] + "é" + VALID[10:],
                    VALID + "-\U0001f600", VALID[:6] + "\U0001f600" + VALID[6:],
                    "hp1-\U0001f600" + GUID[4:]):
            with self.subTest(ref=ref):
                self.assertFalse(CN.is_valid(ref), ref)
                with self.assertRaises(ValueError):
                    CN.parse(ref)

    def test_a_10000_character_input(self):
        for ref in ("a" * 10000, VALID + "a" * 10000,
                    "hp1-" + "a" * 10000, "-" * 10000):
            with self.subTest(length=len(ref)):
                self.assertFalse(CN.is_valid(ref))
                with self.assertRaises(ValueError):
                    CN.parse(ref)

    def test_repetition_runs(self):
        for ch in ("a", "0", "-", " ", ".", "_", "!"):
            with self.subTest(ch=ch):
                self.assertFalse(CN.is_valid(VALID + ch * 10))
        for ref in (" " * 10 + VALID, "-" * 10 + VALID,
                    VALID[:15] + "a" * 10 + VALID[15:],
                    (VALID + "-") * 10):
            with self.subTest(ref=ref):
                self.assertFalse(CN.is_valid(ref), ref)


class NonStringInputTest(unittest.TestCase):
    def test_parse_raises_type_error(self):
        for value in (None, 0, 1, 42, 1.5, True, b"hp1-x", b"",
                      [VALID], (VALID,), {"ref": VALID}, {VALID}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypeError):
                    CN.parse(value)
                with self.assertRaises(TypeError):
                    CN.marking_of(value)

    def test_is_valid_is_false_never_an_exception(self):
        for value in (None, 0, 42, b"bytes", [VALID], object()):
            with self.subTest(value=repr(value)):
                self.assertFalse(CN.is_valid(value))


class ShelfTest(unittest.TestCase):
    def test_the_constants(self):
        self.assertEqual(CN.MARKINGS, (0, 1, 2, 3))
        self.assertEqual(CN.SHELF, {0: "public",
                                    1: "public with care",
                                    2: "private shelf only",
                                    3: "case file only"})

    def test_shelf_of_every_marking(self):
        self.assertEqual(CN.shelf_of(0), "public")
        self.assertEqual(CN.shelf_of(1), "public with care")
        self.assertEqual(CN.shelf_of(2), "private shelf only")
        self.assertEqual(CN.shelf_of(3), "case file only")

    def test_shelf_of_an_invalid_marking_raises(self):
        for marking in (4, 9, -1, 100):
            with self.subTest(marking=marking), \
                    self.assertRaises(ValueError):
                CN.shelf_of(marking)
        for marking in ("1", None, 1.0, True, [0]):
            with self.subTest(marking=marking), \
                    self.assertRaises(TypeError):
                CN.shelf_of(marking)

    def test_marking_of(self):
        for marking in (0, 1, 2, 3):
            self.assertEqual(CN.marking_of(_ref(marking)), marking)
        with self.assertRaises(ValueError):
            CN.marking_of("not a code name")


class CliTest(unittest.TestCase):
    def _main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = CN.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_mint_prints_a_valid_reference(self):
        rc, out, _err = self._main(["mint", "--marking", "1"])
        self.assertEqual(rc, 0)
        ref = out.strip()
        self.assertTrue(CN.is_valid(ref), ref)
        self.assertEqual(CN.marking_of(ref), 1)

    def test_mint_with_a_sub_name(self):
        rc, out, _err = self._main(["mint", "--marking", "2",
                                    "--sub", "corpus"])
        self.assertEqual(rc, 0)
        self.assertEqual(CN.parse(out.strip()).sub, "corpus")

    def test_mint_with_a_bad_marking_is_exit_2(self):
        rc, _out, err = self._main(["mint", "--marking", "4"])
        self.assertEqual(rc, 2)
        self.assertIn("marking", err)

    def test_parse_prints_the_parts(self):
        rc, out, _err = self._main(["parse", EXAMPLE])
        self.assertEqual(rc, 0)
        self.assertIn("marking: 1", out)
        self.assertIn("guid: %s" % GUID, out)
        self.assertIn("sub: a", out)
        self.assertIn("shelf: public with care", out)

    def test_parse_of_a_bad_reference_is_exit_1(self):
        rc, _out, _err = self._main(["parse", "hp9-nope"])
        self.assertEqual(rc, 1)

    def test_check_exits_0_or_1(self):
        self.assertEqual(self._main(["check", VALID])[0], 0)
        self.assertEqual(self._main(["check", EXAMPLE])[0], 0)
        self.assertEqual(self._main(["check", "hp9-nope"])[0], 1)
        self.assertEqual(self._main(["check", ""])[0], 1)
        self.assertEqual(self._main(["check", " " + VALID])[0], 1)


if __name__ == "__main__":
    unittest.main()
