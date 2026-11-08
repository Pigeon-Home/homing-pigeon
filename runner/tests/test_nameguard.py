"""runner/tools/nameguard.py: declared protected terms, scanned for.

The name guard is the shelf boundary made mechanical (SECURITY.md,
"Spillage"): an operator declares protected terms in a registry in
the format the tool declares, and the guard reports every place a
declared term appears in candidate public text. These tests hold
the registry format shut (every malformed shape refused, by name),
the normalization (NFKC, zero-width removal, the fixed lookalike
table), the matching rules (word boundaries and the punctuation
bookend family, substring, case fold and exact, phrases across line
breaks), the private-reference rule, the shipped example registry
(fake entries only), and the command line's exit codes.

Every term in this file is fake. A real registry never lives in the
repository, and neither do its terms.
"""
import contextlib
import io
import json
import os
import string
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.tools import nameguard as NG  # noqa: E402

LANTERN = "Project Fake Lantern"
NEVERREAL = "Neverreal Dynamics"
FRAGMENT = "fictional-target.invalid"
FAKE_GUID = "11111111-2222-4333-8444-555555555555"


def _registry(*entries, **top):
    data = {"format": NG.REGISTRY_FORMAT, "version": 1,
            "terms": list(entries)}
    data.update(top)
    return NG.parse_registry(data)


def _one(term, **kw):
    entry = {"term": term}
    entry.update(kw)
    return _registry(entry)


def _hits(text, registry):
    return NG.scan_text(text, registry)


class RegistryFormatTest(unittest.TestCase):
    def test_minimal_registry_parses(self):
        reg = _registry()
        self.assertEqual(reg.terms, ())
        self.assertEqual(reg.private_refs, "off")

    def test_defaults_are_applied(self):
        (term,) = _one(LANTERN).terms
        self.assertEqual(term, NG.Term(LANTERN, "word", "fold",
                                       None, None))

    def test_full_entry_parses(self):
        (term,) = _one(LANTERN, match="substring", case="exact",
                       marking=3, note="a fake note").terms
        self.assertEqual(term, NG.Term(LANTERN, "substring", "exact",
                                       3, "a fake note"))

    def test_same_term_under_different_rules_is_not_a_duplicate(self):
        reg = _registry({"term": LANTERN},
                        {"term": LANTERN, "match": "substring"})
        self.assertEqual(len(reg.terms), 2)

    def test_private_refs_flag_parses(self):
        reg = _registry(private_refs="flag")
        self.assertEqual(reg.private_refs, "flag")

    def test_top_level_must_be_an_object(self):
        for bad in ([], "text", 7, None, True):
            with self.subTest(bad=bad):
                with self.assertRaises(NG.RegistryError):
                    NG.parse_registry(bad)

    def test_format_must_be_the_declared_string(self):
        for bad in ("hp-nameguard", "", None, 1):
            with self.subTest(bad=bad):
                with self.assertRaises(NG.RegistryError):
                    _registry(format=bad)
        data = {"version": 1, "terms": []}
        with self.assertRaises(NG.RegistryError):
            NG.parse_registry(data)

    def test_version_must_be_the_integer_1(self):
        for bad in (0, 2, "1", 1.0, True, None):
            with self.subTest(bad=bad):
                with self.assertRaises(NG.RegistryError):
                    _registry(version=bad)

    def test_unknown_top_level_key_is_refused(self):
        with self.assertRaises(NG.RegistryError):
            _registry(tems=[])

    def test_terms_must_be_present_and_a_list(self):
        with self.assertRaises(NG.RegistryError):
            NG.parse_registry({"format": NG.REGISTRY_FORMAT,
                               "version": 1})
        for bad in ({}, "term", 7):
            with self.subTest(bad=bad):
                with self.assertRaises(NG.RegistryError):
                    _registry(terms=bad)

    def test_term_entry_must_be_an_object(self):
        for bad in ("term", 7, None, []):
            with self.subTest(bad=bad):
                with self.assertRaises(NG.RegistryError):
                    _registry(bad)

    def test_term_entry_unknown_key_is_refused(self):
        with self.assertRaises(NG.RegistryError):
            _one(LANTERN, mathc="word")

    def test_term_must_be_a_nonempty_string(self):
        for bad in ("", 7, None, ["x"]):
            with self.subTest(bad=bad):
                with self.assertRaises(NG.RegistryError):
                    _registry({"term": bad})
        with self.assertRaises(NG.RegistryError):
            _registry({"match": "word"})

    def test_term_with_whitespace_edges_is_refused(self):
        for bad in (" Lantern", "Lantern ", "\tLantern", "Lantern\n"):
            with self.subTest(bad=bad):
                with self.assertRaises(NG.RegistryError):
                    _registry({"term": bad})

    def test_term_with_control_characters_is_refused(self):
        for bad in ("Fake\x00Lantern", "Fake\x1bLantern",
                    "Fake\x7fLantern", "Fake\tLantern",
                    "Fake\nLantern"):
            with self.subTest(bad=bad):
                with self.assertRaises(NG.RegistryError):
                    _registry({"term": bad})

    def test_match_and_case_rules_are_enumerated(self):
        for bad in ("words", "WORD", "", None, 1):
            with self.subTest(bad=bad):
                with self.assertRaises(NG.RegistryError):
                    _one(LANTERN, match=bad)
                with self.assertRaises(NG.RegistryError):
                    _one(LANTERN, case=bad)

    def test_marking_must_be_an_int_0_to_3(self):
        for bad in (4, -1, "2", 2.0, True, False):
            with self.subTest(bad=bad):
                with self.assertRaises(NG.RegistryError):
                    _one(LANTERN, marking=bad)
        for good in (0, 1, 2, 3):
            with self.subTest(good=good):
                self.assertEqual(_one(LANTERN, marking=good)
                                 .terms[0].marking, good)

    def test_note_must_be_a_string(self):
        with self.assertRaises(NG.RegistryError):
            _one(LANTERN, note=7)

    def test_duplicate_entry_is_refused(self):
        with self.assertRaises(NG.RegistryError):
            _registry({"term": LANTERN}, {"term": LANTERN})
        with self.assertRaises(NG.RegistryError):
            _registry({"term": LANTERN, "case": "exact"},
                      {"term": LANTERN, "case": "exact"})

    def test_private_refs_must_be_off_or_flag(self):
        for bad in ("on", "FLAG", "", None, 1, True):
            with self.subTest(bad=bad):
                with self.assertRaises(NG.RegistryError):
                    _registry(private_refs=bad)


class RegistryFileTest(unittest.TestCase):
    def _write(self, text):
        fh = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8")
        with fh:
            fh.write(text)
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def test_load_a_valid_registry(self):
        path = self._write(json.dumps(
            {"format": NG.REGISTRY_FORMAT, "version": 1,
             "terms": [{"term": LANTERN, "marking": 2}]}))
        reg = NG.load_registry(path)
        self.assertEqual(reg.terms[0].term, LANTERN)
        self.assertEqual(reg.terms[0].marking, 2)

    def test_missing_registry_is_an_error(self):
        with self.assertRaises(NG.RegistryError):
            NG.load_registry("/nonexistent/nameguard-registry.json")

    def test_malformed_json_is_an_error(self):
        with self.assertRaises(NG.RegistryError):
            NG.load_registry(self._write("{not json"))

    def test_a_directory_is_an_error(self):
        with self.assertRaises(NG.RegistryError):
            NG.load_registry(tempfile.gettempdir())


class NormalizeTest(unittest.TestCase):
    def test_plain_text_is_unchanged(self):
        self.assertEqual(NG.normalize("Plain ASCII text 123."),
                         "Plain ASCII text 123.")

    def test_fullwidth_folds_to_ascii(self):
        self.assertEqual(NG.normalize("\uff30\uff52\uff4f\uff4a\uff45\uff43\uff54"), "Project")

    def test_ligatures_fold(self):
        self.assertEqual(NG.normalize("\ufb01le"), "file")

    def test_zero_width_characters_are_removed(self):
        for zw in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"):
            with self.subTest(zw=hex(ord(zw))):
                self.assertEqual(NG.normalize("Fake%sLantern" % zw),
                                 "FakeLantern")

    def test_cyrillic_lookalikes_fold(self):
        self.assertEqual(NG.normalize("Pr\u043eject"), "Project")
        self.assertEqual(NG.normalize("\u0430\u0435\u043e\u0440\u0441"), "aeopc")
        self.assertEqual(NG.normalize("\u0410\u0415\u041e\u0420\u0421"), "AEOPC")

    def test_greek_lookalikes_fold(self):
        self.assertEqual(NG.normalize("\u03bf\u03c1\u03c7"), "opx")
        self.assertEqual(NG.normalize("\u039f\u03a1\u03a7"), "OPX")

    def test_newlines_survive_normalization(self):
        self.assertEqual(NG.normalize("a\r\nb\nc").count("\n"), 2)

    def test_normalization_is_idempotent(self):
        text = "\uff30r\u043e\u200bject"
        self.assertEqual(NG.normalize(NG.normalize(text)),
                         NG.normalize(text))

    def test_non_string_is_a_type_error(self):
        for bad in (None, 7, b"bytes", ["x"]):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    NG.normalize(bad)


class WordMatchTest(unittest.TestCase):
    def setUp(self):
        self.reg = _one(LANTERN, marking=2)

    def test_a_plain_occurrence_is_found(self):
        (hit,) = _hits("Notes on %s today." % LANTERN, self.reg)
        self.assertEqual(hit.term, LANTERN)
        self.assertEqual(hit.marking, 2)
        self.assertEqual(hit.kind, "term")
        self.assertEqual((hit.line, hit.column), (1, 10))

    def test_no_occurrence_no_finding(self):
        self.assertEqual(_hits("Nothing declared here.", self.reg),
                         [])

    def test_case_folds_by_default(self):
        for variant in ("project fake lantern",
                        "PROJECT FAKE LANTERN",
                        "PrOjEcT fAkE LaNtErN"):
            with self.subTest(variant=variant):
                self.assertEqual(len(_hits(variant, self.reg)), 1)

    def test_bookends_every_ascii_punctuation(self):
        # Underscore is not a bookend: it is a word character, so a
        # term wrapped in underscores is inside a larger word (see
        # test_inside_a_larger_word_is_not_a_match).
        for ch in string.punctuation.replace("_", ""):
            with self.subTest(ch=ch):
                self.assertEqual(
                    len(_hits("%s%s%s" % (ch, LANTERN, ch),
                              self.reg)), 1)
                self.assertEqual(
                    len(_hits("say %s%s%s now" % (ch, LANTERN, ch),
                              self.reg)), 1)

    def test_bookend_runs_and_mixed_pairs(self):
        for text in ("---%s---" % LANTERN,
                     "((%s))" % LANTERN,
                     "\"'%s'\"" % LANTERN,
                     "==%s==\n" % LANTERN):
            with self.subTest(text=text):
                self.assertEqual(len(_hits(text, self.reg)), 1)

    def test_inside_a_larger_word_is_not_a_match(self):
        reg = _one("Lantern")
        for text in ("Lanterns", "aLantern", "Lantern2", "2Lantern",
                     "my_Lantern", "Lantern_fish"):
            with self.subTest(text=text):
                self.assertEqual(_hits(text, reg), [])

    def test_hyphen_and_slash_neighbours_are_boundaries(self):
        reg = _one("Lantern")
        for text in ("anti-Lantern", "Lantern/fish", "the-Lantern-"):
            with self.subTest(text=text):
                self.assertEqual(len(_hits(text, reg)), 1)

    def test_string_edges_are_boundaries(self):
        reg = _one("Lantern")
        self.assertEqual(len(_hits("Lantern", reg)), 1)
        self.assertEqual(len(_hits("Lantern ", reg)), 1)
        self.assertEqual(len(_hits(" Lantern", reg)), 1)

    def test_multiple_occurrences_in_reading_order(self):
        hits = _hits("%s and %s" % (LANTERN, LANTERN), self.reg)
        self.assertEqual(len(hits), 2)
        self.assertLess(hits[0].column, hits[1].column)

    def test_line_and_column_across_lines(self):
        (hit,) = _hits("ab\nxx %s yy\nzz" % LANTERN, self.reg)
        self.assertEqual((hit.line, hit.column), (2, 4))

    def test_a_punctuation_edged_term_takes_no_boundary_there(self):
        reg = _one("fake-lantern.invalid")
        self.assertEqual(len(_hits("a fake-lantern.invalid b", reg)),
                         1)
        self.assertEqual(_hits("afake-lantern.invalid", reg), [])
        self.assertEqual(_hits("fake-lantern.invalide", reg), [])


class PhraseMatchTest(unittest.TestCase):
    def setUp(self):
        self.reg = _one(LANTERN)

    def test_a_phrase_split_across_lines_matches(self):
        (hit,) = _hits("Project Fake\nLantern", self.reg)
        self.assertEqual((hit.line, hit.column), (1, 1))

    def test_a_phrase_with_wide_whitespace_matches(self):
        for text in ("Project  Fake   Lantern",
                     "Project\tFake\tLantern",
                     "Project \n Fake \n Lantern"):
            with self.subTest(text=text):
                self.assertEqual(len(_hits(text, self.reg)), 1)

    def test_a_single_word_split_across_lines_does_not_match(self):
        self.assertEqual(_hits("Project Fake Lant\nern", self.reg),
                         [])

    def test_word_order_matters(self):
        self.assertEqual(_hits("Lantern Fake Project", self.reg), [])


class CaseRulesTest(unittest.TestCase):
    def test_exact_case_matches_only_itself(self):
        reg = _one("Case Sensitive Codename", case="exact")
        self.assertEqual(len(_hits("Case Sensitive Codename", reg)),
                         1)
        for variant in ("case sensitive codename",
                        "CASE SENSITIVE CODENAME",
                        "Case sensitive codename"):
            with self.subTest(variant=variant):
                self.assertEqual(_hits(variant, reg), [])

    def test_exact_case_still_normalizes(self):
        reg = _one("Project", case="exact")
        self.assertEqual(len(_hits("Pr\u043eject", reg)), 1)
        self.assertEqual(len(_hits("\uff30roject", reg)), 1)


class SubstringMatchTest(unittest.TestCase):
    def setUp(self):
        self.reg = _one(FRAGMENT, match="substring", marking=3)

    def test_inside_a_larger_word_matches(self):
        for text in ("xx%syy" % FRAGMENT,
                     "host.%s.example" % FRAGMENT,
                     "https://%s/path" % FRAGMENT):
            with self.subTest(text=text):
                self.assertEqual(len(_hits(text, self.reg)), 1)

    def test_case_still_folds(self):
        self.assertEqual(
            len(_hits("FICTIONAL-TARGET.INVALID", self.reg)), 1)

    def test_absent_fragment_is_clean(self):
        self.assertEqual(_hits("fictional-target.example", self.reg),
                         [])

    def test_word_rule_would_not_match_these(self):
        reg = _one(FRAGMENT, match="word")
        self.assertEqual(_hits("xx%syy" % FRAGMENT, reg), [])
        self.assertEqual(len(_hits("a %s b" % FRAGMENT, reg)), 1)


class LookalikeScanTest(unittest.TestCase):
    def setUp(self):
        self.reg = _one(LANTERN)

    def test_cyrillic_substitution_matches(self):
        self.assertEqual(
            len(_hits("Pr\u043eject Fake Lantern", self.reg)), 1)
        self.assertEqual(
            len(_hits("Project Fake L\u0430ntern", self.reg)), 1)

    def test_zero_width_inside_a_word_matches(self):
        reg = _one(NEVERREAL.split()[0])
        self.assertEqual(len(_hits("Never\u200breal", reg)), 1)
        self.assertEqual(len(_hits("N\u200c\u200ceverreal", reg)), 1)

    def test_fullwidth_text_matches(self):
        self.assertEqual(
            len(_hits("\uff30roject Fake Lantern", self.reg)), 1)

    def test_an_unrelated_word_does_not_match(self):
        self.assertEqual(_hits("Project Real Lantern", self.reg), [])


class ScanShapeTest(unittest.TestCase):
    def test_empty_text_is_clean(self):
        self.assertEqual(_hits("", _one(LANTERN)), [])

    def test_empty_registry_scans_clean(self):
        reg = _registry()
        self.assertEqual(_hits("%s and %s" % (LANTERN, NEVERREAL),
                               reg), [])

    def test_several_terms_report_together_sorted(self):
        reg = _registry({"term": NEVERREAL}, {"term": LANTERN})
        hits = _hits("%s\n%s" % (LANTERN, NEVERREAL), reg)
        self.assertEqual([h.term for h in hits],
                         [LANTERN, NEVERREAL])
        self.assertEqual([h.line for h in hits], [1, 2])

    def test_scan_rejects_a_non_registry(self):
        with self.assertRaises(TypeError):
            NG.scan_text("text", {"terms": []})


class PrivateRefTest(unittest.TestCase):
    def setUp(self):
        self.reg = _registry(private_refs="flag")

    def _ref(self, marking, sub=None):
        text = "hp%d-%s" % (marking, FAKE_GUID)
        if sub is not None:
            text += "-" + sub
        return text

    def test_hp2_and_hp3_references_are_flagged(self):
        for marking in (2, 3):
            with self.subTest(marking=marking):
                (hit,) = _hits("see %s for it" % self._ref(marking),
                               self.reg)
                self.assertEqual(hit.kind, "private-ref")
                self.assertEqual(hit.marking, marking)

    def test_hp0_and_hp1_references_are_public(self):
        for marking in (0, 1):
            with self.subTest(marking=marking):
                self.assertEqual(
                    _hits("see %s" % self._ref(marking), self.reg), [])

    def test_a_reference_with_a_sub_name_is_flagged(self):
        (hit,) = _hits(self._ref(2, "corpus"), self.reg)
        self.assertEqual(hit.kind, "private-ref")

    def test_malformed_hp_like_strings_are_not_flagged(self):
        for text in ("hp2-not-a-guid",
                     "hp9-%s" % FAKE_GUID,
                     "hp2-%s" % FAKE_GUID.replace("4333", "1333"),
                     "hp2-"):
            with self.subTest(text=text):
                self.assertEqual(_hits(text, self.reg), [])

    def test_an_overlong_sub_name_is_not_a_reference(self):
        self.assertEqual(
            _hits(self._ref(2, "a" * 33), self.reg), [])
        self.assertEqual(
            len(_hits(self._ref(2, "a" * 32), self.reg)), 1)

    def test_off_means_no_ref_findings(self):
        reg = _registry(private_refs="off")
        self.assertEqual(_hits(self._ref(3), reg), [])

    def test_default_is_off(self):
        self.assertEqual(_hits(self._ref(3), _registry()), [])


class ExampleRegistryTest(unittest.TestCase):
    ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    PATH = os.path.join(ROOT, "runner", "tools",
                        "nameguard-registry.example.json")

    def setUp(self):
        self.reg = NG.load_registry(self.PATH)

    def test_the_example_registry_loads(self):
        self.assertEqual(len(self.reg.terms), 4)
        self.assertEqual(self.reg.private_refs, "off")

    def test_every_example_term_is_fake_on_its_face(self):
        for term in self.reg.terms:
            with self.subTest(term=term.term):
                self.assertTrue(
                    any(mark in term.term for mark in
                        ("Fake", "Neverreal", "fictional")),
                    term.term)

    def test_the_fake_terms_are_found(self):
        text = ("The %s notes mention %s and a host at %s."
                % (LANTERN, NEVERREAL, FRAGMENT))
        self.assertEqual(len(_hits(text, self.reg)), 3)

    def test_ordinary_prose_is_clean(self):
        text = ("The runner polls its mailbox, verifies the "
                "signature, and runs the job it was sent.")
        self.assertEqual(_hits(text, self.reg), [])


class ScanFileTest(unittest.TestCase):
    def _write_bytes(self, data):
        fh = tempfile.NamedTemporaryFile("wb", delete=False)
        with fh:
            fh.write(data)
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def test_scan_file_finds_terms(self):
        path = self._write_bytes(
            ("clean line\n%s\n" % LANTERN).encode("utf-8"))
        (hit,) = NG.scan_file(path, _one(LANTERN))
        self.assertEqual(hit.line, 2)

    def test_undecodable_bytes_do_not_stop_the_scan(self):
        path = self._write_bytes(
            b"\xff\xfe binary \x00 " + LANTERN.encode("utf-8"))
        self.assertEqual(len(NG.scan_file(path, _one(LANTERN))), 1)

    def test_a_missing_file_raises_oserror(self):
        with self.assertRaises(OSError):
            NG.scan_file("/nonexistent/file.txt", _one(LANTERN))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.registry = os.path.join(self.dir, "registry.json")
        with open(self.registry, "w", encoding="utf-8") as fh:
            json.dump({"format": NG.REGISTRY_FORMAT, "version": 1,
                       "terms": [{"term": LANTERN, "marking": 2}]},
                      fh)

    def _cleanup(self):
        for name in os.listdir(self.dir):
            os.unlink(os.path.join(self.dir, name))
        os.rmdir(self.dir)

    def _file(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def _run(self, argv, stdin_text=None):
        out, err = io.StringIO(), io.StringIO()
        stdin = io.StringIO(stdin_text or "")
        with mock.patch.object(sys, "stdin", stdin), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = NG.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_validate_a_good_registry(self):
        code, out, _ = self._run(
            ["validate", "--registry", self.registry])
        self.assertEqual(code, 0)
        self.assertIn("1 term(s)", out)

    def test_validate_a_missing_registry_is_2(self):
        code, _, err = self._run(
            ["validate", "--registry",
             os.path.join(self.dir, "nope.json")])
        self.assertEqual(code, 2)
        self.assertIn("nameguard:", err)

    def test_a_clean_file_exits_0_silently(self):
        path = self._file("clean.txt", "ordinary prose\n")
        code, out, _ = self._run(
            ["check", "--registry", self.registry, path])
        self.assertEqual((code, out), (0, ""))

    def test_a_dirty_file_exits_1_and_reports_the_place(self):
        path = self._file("dirty.txt", "one\n%s\n" % LANTERN)
        code, out, err = self._run(
            ["check", "--registry", self.registry, path])
        self.assertEqual(code, 1)
        self.assertIn("%s:2:1:" % path, out)
        self.assertIn(LANTERN, out)
        self.assertIn("marking hp2", out)
        self.assertIn("1 finding(s)", err)

    def test_a_missing_scan_file_is_2(self):
        code, _, _ = self._run(
            ["check", "--registry", self.registry,
             os.path.join(self.dir, "nope.txt")])
        self.assertEqual(code, 2)

    def test_nothing_to_scan_is_2(self):
        code, _, _ = self._run(["check", "--registry", self.registry])
        self.assertEqual(code, 2)

    def test_stdin_scans(self):
        code, out, _ = self._run(
            ["check", "--registry", self.registry, "--stdin"],
            stdin_text="piped %s text\n" % LANTERN)
        self.assertEqual(code, 1)
        self.assertIn("<stdin>:1:7:", out)

    def test_stdin_with_files_is_2(self):
        path = self._file("x.txt", "x")
        code, _, _ = self._run(
            ["check", "--registry", self.registry, "--stdin", path])
        self.assertEqual(code, 2)

    def test_a_bad_registry_is_2_for_check_too(self):
        bad = self._file("bad.json", "{}")
        code, _, _ = self._run(["check", "--registry", bad, bad])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
