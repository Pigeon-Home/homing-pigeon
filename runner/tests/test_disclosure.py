"""runner/tools/disclosure.py: disclosure postures, declared in data.

A posture is what may be said publicly about a cs_office project,
and where its material may live. The registry declares the
postures; a tagging file categorizes projects by tag; the tool
resolves each project's effective posture. These tests hold both
formats shut (every malformed shape refused, by name — per field,
not per file), the resolution rules (an active posture resolves,
an undeclared tag is unknown and never guessed, a retired
posture is flagged with its successor named), the extensibility
the design rests on (adding, retiring, and re-categorizing are
data edits), the shipped example registry (fake entries only),
and the command line's exit codes.

Every posture and project in this file is fake. A real registry
and a real tagging name what an operator is working on, and
neither lives in the repository.
"""
import contextlib
import io
import json
import os
import string
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.tools import disclosure as P  # noqa: E402

SAY = "Nothing is said in public."
SHELF = "Private shelf only."


def _posture(pid="nothing-said", tag="A", **kw):
    entry = {"id": pid, "tag": tag, "say": SAY, "shelf": SHELF}
    entry.update(kw)
    return entry


def _registry(*entries, **top):
    data = {"format": P.REGISTRY_FORMAT, "version": 1,
            "postures": list(entries)}
    data.update(top)
    return P.parse_registry(data)


def _tagging(*entries, **top):
    data = {"format": P.TAGGING_FORMAT, "version": 1,
            "projects": list(entries)}
    data.update(top)
    return P.parse_tagging(data)


def _project(name="example-project-one", tag="A", **kw):
    entry = {"project": name, "posture": tag}
    entry.update(kw)
    return entry


def _three_postures():
    return _registry(
        _posture("nothing-said", "A"),
        _posture("named-and-described", "B",
                 say="Named, and the work described in general terms.",
                 shelf="Public shelf for the name and the description."),
        _posture("named-only", "C",
                 say="Named. Nothing about the work is said.",
                 shelf="Public shelf for the name alone."))


class RegistryFormatTest(unittest.TestCase):
    def test_minimal_registry_parses(self):
        reg = _registry()
        self.assertEqual(reg.postures, ())

    def test_defaults_are_applied(self):
        (posture,) = _registry(_posture()).postures
        self.assertEqual(posture, P.Posture("nothing-said", "A", SAY,
                                            SHELF, "active", None, None))

    def test_full_entry_parses(self):
        reg = _registry(
            _posture("old-posture", "Z", status="retired",
                     successor="nothing-said", note="a fake note"),
            _posture())
        old = reg.by_id("old-posture")
        self.assertEqual(old, P.Posture("old-posture", "Z", SAY, SHELF,
                                        "retired", "nothing-said",
                                        "a fake note"))

    def test_top_level_must_be_an_object(self):
        for bad in ([], "text", 7, None, True):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    P.parse_registry(bad)

    def test_format_must_be_the_declared_string(self):
        for bad in ("hp-posture", "", None, 1):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(format=bad)
        with self.assertRaises(P.RegistryError):
            P.parse_registry({"version": 1, "postures": []})

    def test_version_must_be_the_integer_1(self):
        for bad in (0, 2, "1", 1.0, True, None):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(version=bad)

    def test_unknown_top_level_key_is_refused(self):
        with self.assertRaises(P.RegistryError):
            _registry(posturs=[])

    def test_postures_must_be_present_and_a_list(self):
        with self.assertRaises(P.RegistryError):
            P.parse_registry({"format": P.REGISTRY_FORMAT, "version": 1})
        for bad in ({}, "posture", 7):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(postures=bad)

    def test_entry_must_be_an_object(self):
        for bad in ("posture", 7, None, []):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(bad)

    def test_unknown_entry_key_is_refused(self):
        with self.assertRaises(P.RegistryError):
            _registry(_posture(sayy="a typo'd key"))

    def test_each_required_field_must_be_present(self):
        for field in ("id", "tag", "say", "shelf"):
            with self.subTest(field=field):
                entry = _posture()
                del entry[field]
                with self.assertRaises(P.RegistryError):
                    _registry(entry)


class PostureIdTest(unittest.TestCase):
    def test_id_shapes_that_parse(self):
        for good in ("a", "abc", "a-b", "stage-2", "a1-b2-c3", "x" * 64):
            with self.subTest(good=good):
                (posture,) = _registry(_posture(pid=good)).postures
                self.assertEqual(posture.id, good)

    def test_id_must_be_a_str(self):
        for bad in (7, None, ["a"], True):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(_posture(pid=bad))

    def test_id_shape_refusals(self):
        for bad in ("", "A", "Nothing-Said", "a b", "a--b", "-a", "a-",
                    "a_b", "a.b", "a/b", "café", "x" * 65):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(_posture(pid=bad))

    def test_id_whitespace_and_control_refusals(self):
        for bad in (" a", "a ", "a\tb", "a\nb", "a\x00b", "a\x7fb"):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(_posture(pid=bad))

    def test_id_punctuation_bookends_are_refused(self):
        for ch in string.punctuation:
            for bad in (ch + "abc", "abc" + ch, ch + "abc" + ch):
                with self.subTest(bad=bad):
                    with self.assertRaises(P.RegistryError):
                        _registry(_posture(pid=bad))

    def test_duplicate_id_is_refused(self):
        with self.assertRaises(P.RegistryError):
            _registry(_posture("same-id", "A"), _posture("same-id", "B"))


class PostureTagTest(unittest.TestCase):
    def test_tag_shapes_that_parse(self):
        for good in ("A", "b", "A1", "named", "x" * 16, "!"):
            with self.subTest(good=good):
                (posture,) = _registry(_posture(tag=good)).postures
                self.assertEqual(posture.tag, good)

    def test_tag_must_be_a_str(self):
        for bad in (7, None, ["A"], True):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(_posture(tag=bad))

    def test_tag_shape_refusals(self):
        for bad in ("", "x" * 17):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(_posture(tag=bad))

    def test_tag_whitespace_and_control_refusals(self):
        for bad in (" A", "A ", "A B", "A\tB", "\tA", "A\n", "A\rB",
                    "A\x00", "\x7fA", "A\u200b"):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(_posture(tag=bad))

    def test_duplicate_tag_is_refused(self):
        with self.assertRaises(P.RegistryError):
            _registry(_posture("one-id", "A"), _posture("two-id", "A"))

    def test_tag_differing_only_in_case_is_refused(self):
        with self.assertRaises(P.RegistryError):
            _registry(_posture("one-id", "A"), _posture("two-id", "a"))

    def test_retired_postures_tag_stays_reserved(self):
        with self.assertRaises(P.RegistryError):
            _registry(_posture("old-id", "A", status="retired"),
                      _posture("new-id", "A"))


class PostureTextFieldsTest(unittest.TestCase):
    def test_say_and_shelf_refusal_family(self):
        for field in ("say", "shelf"):
            for bad in ("", " leading", "trailing ", "line\nbreak",
                        "tab\there", "nul\x00char", 7, None, ["x"]):
                with self.subTest(field=field, bad=bad):
                    with self.assertRaises(P.RegistryError):
                        _registry(_posture(**{field: bad}))

    def test_status_must_be_a_declared_value(self):
        for bad in ("Active", "gone", "live", 1, None, True):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(_posture(status=bad))

    def test_note_must_be_a_str_when_present(self):
        for bad in (7, ["x"], {"x": 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(_posture(note=bad))
        (posture,) = _registry(_posture(note="")).postures
        self.assertEqual(posture.note, "")


class SuccessorTest(unittest.TestCase):
    def test_successor_on_an_active_posture_is_refused(self):
        with self.assertRaises(P.RegistryError):
            _registry(_posture(successor="nothing-said"))

    def test_successor_must_name_a_posture_in_the_registry(self):
        with self.assertRaises(P.RegistryError):
            _registry(_posture(status="retired", successor="no-such"))

    def test_successor_must_not_name_the_posture_itself(self):
        with self.assertRaises(P.RegistryError):
            _registry(_posture(status="retired",
                               successor="nothing-said"))

    def test_successor_must_be_a_valid_id(self):
        for bad in (7, "Not An Id", "", ["x"]):
            with self.subTest(bad=bad):
                with self.assertRaises(P.RegistryError):
                    _registry(_posture(status="retired", successor=bad),
                              _posture("other-id", "B"))

    def test_successor_cycle_is_refused(self):
        with self.assertRaises(P.RegistryError):
            _registry(
                _posture("posture-a", "A", status="retired",
                         successor="posture-b"),
                _posture("posture-b", "B", status="retired",
                         successor="posture-a"))

    def test_successor_chain_parses_and_resolves_to_its_end(self):
        reg = _registry(
            _posture("posture-a", "A", status="retired",
                     successor="posture-b"),
            _posture("posture-b", "B", status="retired",
                     successor="posture-c"),
            _posture("posture-c", "C"))
        end = reg.successor_of(reg.by_id("posture-a"))
        self.assertEqual(end.id, "posture-c")

    def test_chain_ending_without_successor_resolves_to_none(self):
        reg = _registry(_posture("posture-a", "A", status="retired"))
        self.assertIsNone(reg.successor_of(reg.by_id("posture-a")))

    def test_successor_of_an_active_posture_is_itself(self):
        reg = _three_postures()
        posture = reg.by_id("nothing-said")
        self.assertEqual(reg.successor_of(posture), posture)


class TaggingFormatTest(unittest.TestCase):
    def test_minimal_tagging_parses(self):
        self.assertEqual(_tagging().assignments, ())

    def test_full_entry_parses(self):
        (assignment,) = _tagging(
            _project(note="a fake note")).assignments
        self.assertEqual(assignment,
                         P.Assignment("example-project-one", "A",
                                      "a fake note"))

    def test_top_level_must_be_an_object(self):
        for bad in ([], "text", 7, None, True):
            with self.subTest(bad=bad):
                with self.assertRaises(P.TaggingError):
                    P.parse_tagging(bad)

    def test_format_and_version_are_held(self):
        for bad in ("hp-posture", "", None, 1):
            with self.subTest(bad=bad):
                with self.assertRaises(P.TaggingError):
                    _tagging(format=bad)
        for bad in (0, 2, "1", 1.0, True, None):
            with self.subTest(bad=bad):
                with self.assertRaises(P.TaggingError):
                    _tagging(version=bad)

    def test_unknown_keys_are_refused(self):
        with self.assertRaises(P.TaggingError):
            _tagging(projets=[])
        with self.assertRaises(P.TaggingError):
            _tagging(_project(projets="a typo'd key"))

    def test_projects_must_be_present_and_a_list(self):
        with self.assertRaises(P.TaggingError):
            P.parse_tagging({"format": P.TAGGING_FORMAT, "version": 1})
        for bad in ({}, "project", 7):
            with self.subTest(bad=bad):
                with self.assertRaises(P.TaggingError):
                    _tagging(projects=bad)

    def test_entry_must_be_an_object_with_both_fields(self):
        for bad in ("project", 7, None, []):
            with self.subTest(bad=bad):
                with self.assertRaises(P.TaggingError):
                    _tagging(bad)
        for field in ("project", "posture"):
            with self.subTest(field=field):
                entry = _project()
                del entry[field]
                with self.assertRaises(P.TaggingError):
                    _tagging(entry)

    def test_project_refusal_family(self):
        for bad in ("", " leading", "trailing ", "line\nbreak",
                    "nul\x00char", "x" * 129, 7, None, ["x"]):
            with self.subTest(bad=bad):
                with self.assertRaises(P.TaggingError):
                    _tagging(_project(name=bad))

    def test_posture_reference_refusal_family(self):
        for bad in ("", " A", "A ", "A B", "A\tB", "A\x00", "x" * 17,
                    7, None):
            with self.subTest(bad=bad):
                with self.assertRaises(P.TaggingError):
                    _tagging(_project(tag=bad))

    def test_note_must_be_a_str_when_present(self):
        with self.assertRaises(P.TaggingError):
            _tagging(_project(note=7))

    def test_duplicate_project_is_refused(self):
        with self.assertRaises(P.TaggingError):
            _tagging(_project("same-project", "A"),
                     _project("same-project", "B"))

    def test_an_undeclared_tag_still_parses(self):
        # Unknown is a check finding, not a format error.
        (assignment,) = _tagging(_project(tag="Z")).assignments
        self.assertEqual(assignment.posture, "Z")


class CheckTest(unittest.TestCase):
    def test_active_posture_resolves_with_its_declaration(self):
        reg = _three_postures()
        (r,) = P.check_tagging(reg, _tagging(_project(tag="B")))
        self.assertIsNone(r.problem)
        self.assertEqual(r.posture.id, "named-and-described")
        self.assertEqual(r.tag, "B")

    def test_unknown_tag_is_flagged_and_never_guessed(self):
        reg = _three_postures()
        (r,) = P.check_tagging(reg, _tagging(_project(tag="Z")))
        self.assertEqual(r.problem, "unknown-tag")
        self.assertIsNone(r.posture)

    def test_unknown_tag_near_a_real_one_is_still_unknown(self):
        reg = _three_postures()
        for near in ("a", "AA", "D"):
            with self.subTest(near=near):
                tagging = P.Tagging((P.Assignment("p", near),))
                (r,) = P.check_tagging(reg, tagging)
                self.assertEqual(r.problem, "unknown-tag")

    def test_retired_posture_is_flagged(self):
        reg = _registry(
            _posture("old-id", "A", status="retired",
                     successor="nothing-said"),
            _posture("nothing-said", "B"))
        (r,) = P.check_tagging(reg, _tagging(_project(tag="A")))
        self.assertEqual(r.problem, "retired")
        self.assertEqual(r.posture.id, "old-id")
        self.assertEqual(reg.successor_of(r.posture).id, "nothing-said")

    def test_every_project_is_reported_in_tagging_order(self):
        reg = _three_postures()
        tagging = _tagging(_project("p-one", "A"),
                           _project("p-two", "Z"),
                           _project("p-three", "C"))
        results = P.check_tagging(reg, tagging)
        self.assertEqual([r.project for r in results],
                         ["p-one", "p-two", "p-three"])
        self.assertEqual([r.problem for r in results],
                         [None, "unknown-tag", None])

    def test_empty_tagging_checks_clean(self):
        self.assertEqual(P.check_tagging(_three_postures(), _tagging()),
                         [])

    def test_empty_registry_makes_every_tag_unknown(self):
        results = P.check_tagging(_registry(),
                                  _tagging(_project(tag="A")))
        self.assertEqual([r.problem for r in results], ["unknown-tag"])

    def test_check_holds_its_argument_types(self):
        with self.assertRaises(TypeError):
            P.check_tagging({"not": "a registry"}, _tagging())
        with self.assertRaises(TypeError):
            P.check_tagging(_three_postures(), {"not": "a tagging"})

    def test_recategorization_is_a_data_edit(self):
        # The supposition's core operation: same tool, same
        # registry — only the tagging entry changes.
        reg = _three_postures()
        before = P.check_tagging(reg, _tagging(_project(tag="A")))[0]
        after = P.check_tagging(reg, _tagging(_project(tag="C")))[0]
        self.assertEqual(before.posture.id, "nothing-said")
        self.assertEqual(after.posture.id, "named-only")


class ExtensibilityTest(unittest.TestCase):
    """The operations the design note's supposition prices at one
    data edit each, exercised as data edits."""

    def test_adding_a_fourth_posture_is_data_only(self):
        reg = _registry(
            _posture("nothing-said", "A"),
            _posture("named-and-described", "B"),
            _posture("named-only", "C"),
            _posture("named-with-embargo", "D",
                     say="Named; the work described after an embargo.",
                     shelf="Public shelf, after the embargo date."))
        (r,) = P.check_tagging(reg, _tagging(_project(tag="D")))
        self.assertIsNone(r.problem)
        self.assertEqual(r.posture.id, "named-with-embargo")

    def test_retiring_a_posture_keeps_old_references_resolving(self):
        reg = _registry(
            _posture("nothing-said", "A", status="retired",
                     successor="named-only"),
            _posture("named-only", "C"))
        (r,) = P.check_tagging(reg, _tagging(_project(tag="A")))
        self.assertEqual(r.problem, "retired")
        self.assertEqual(reg.successor_of(r.posture).id, "named-only")


class StampTest(unittest.TestCase):
    def test_roundtrip_for_every_active_posture(self):
        reg = _three_postures()
        for posture in reg.postures:
            with self.subTest(posture=posture.id):
                stamp = P.format_stamp(reg, posture.id)
                self.assertEqual(
                    stamp, "hp-posture-1-%s" % posture.id)
                parsed = P.parse_stamp(stamp)
                self.assertEqual(parsed, P.Stamp(1, posture.id))
                self.assertEqual(P.validate_stamp(reg, parsed),
                                 posture)
                self.assertEqual(P.validate_stamp(reg, stamp),
                                 posture)

    def test_roundtrip_against_the_shipped_example(self):
        reg = P.load_registry(ExampleRegistryTest.EXAMPLE)
        for posture in reg.postures:
            if posture.status != "active":
                continue
            with self.subTest(posture=posture.id):
                stamp = P.format_stamp(reg, posture.id)
                self.assertEqual(P.validate_stamp(reg, stamp),
                                 posture)

    def test_format_refuses_an_unknown_id(self):
        with self.assertRaises(P.StampError):
            P.format_stamp(_three_postures(), "no-such-posture")

    def test_format_refuses_a_retired_posture(self):
        reg = _registry(
            _posture("old-id", "A", status="retired",
                     successor="nothing-said"),
            _posture("nothing-said", "B"))
        with self.assertRaises(P.StampError):
            P.format_stamp(reg, "old-id")

    def test_format_refuses_a_non_str_id(self):
        for bad in (7, None, ["named-only"]):
            with self.subTest(bad=bad):
                with self.assertRaises(P.StampError):
                    P.format_stamp(_three_postures(), bad)

    def test_parse_refusal_family(self):
        for bad in ("", "hp-posture-", "hp-posture-1",
                    "hp-posture-1-", "posture-1-named-only",
                    "hp-posture-a-named-only",
                    "hp-posture--named-only",
                    "hp-posture-1-Named-Only",
                    "hp-posture-1-named_only",
                    "hp-posture-1-named--only",
                    "hp-posture-1-named-only-",
                    " hp-posture-1-named-only",
                    "hp-posture-1-named-only ",
                    "hp-posture-1-named-only\n",
                    "xhp-posture-1-named-only",
                    "hp-posture-1-named-onlyx y",
                    "hp-posture-1-" + "x" * 65):
            with self.subTest(bad=bad):
                with self.assertRaises(P.StampError):
                    P.parse_stamp(bad)

    def test_parse_refuses_non_canonical_versions(self):
        for bad in ("hp-posture-0-named-only",
                    "hp-posture-00-named-only",
                    "hp-posture-01-named-only"):
            with self.subTest(bad=bad):
                with self.assertRaises(P.StampError):
                    P.parse_stamp(bad)

    def test_parse_punctuation_bookends_are_refused(self):
        stamp = P.format_stamp(_three_postures(), "named-only")
        for ch in string.punctuation:
            for bad in (ch + stamp, stamp + ch, ch + stamp + ch):
                with self.subTest(bad=bad):
                    with self.assertRaises(P.StampError):
                        P.parse_stamp(bad)

    def test_parse_refuses_non_str(self):
        for bad in (None, 7, b"hp-posture-1-named-only", ["x"]):
            with self.subTest(bad=bad):
                with self.assertRaises(P.StampError):
                    P.parse_stamp(bad)

    def test_validate_fails_closed_on_an_unknown_id(self):
        reg = _three_postures()
        for stamp in (P.Stamp(1, "no-such-posture"),
                      "hp-posture-1-no-such-posture"):
            with self.subTest(stamp=stamp):
                with self.assertRaises(P.StampError):
                    P.validate_stamp(reg, stamp)

    def test_validate_fails_closed_on_a_version_mismatch(self):
        reg = _three_postures()
        for stamp in (P.Stamp(2, "named-only"),
                      P.Stamp(99, "named-only"),
                      "hp-posture-2-named-only"):
            with self.subTest(stamp=stamp):
                with self.assertRaises(P.StampError):
                    P.validate_stamp(reg, stamp)

    def test_a_retired_postures_stamp_still_validates(self):
        # Old records stay readable; the status says what it is.
        reg = _registry(
            _posture("old-id", "A", status="retired",
                     successor="nothing-said"),
            _posture("nothing-said", "B"))
        posture = P.validate_stamp(reg, "hp-posture-1-old-id")
        self.assertEqual(posture.id, "old-id")
        self.assertEqual(posture.status, "retired")

    def test_helpers_hold_their_argument_types(self):
        with self.assertRaises(TypeError):
            P.format_stamp({"not": "a registry"}, "named-only")
        with self.assertRaises(TypeError):
            P.validate_stamp({"not": "a registry"},
                             "hp-posture-1-named-only")
        with self.assertRaises(TypeError):
            P.validate_stamp(_three_postures(), 7)


class LoadersTest(unittest.TestCase):
    def _write(self, text):
        fh = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8")
        with fh:
            fh.write(text)
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def test_load_registry_roundtrip(self):
        path = self._write(json.dumps(
            {"format": P.REGISTRY_FORMAT, "version": 1,
             "postures": [_posture()]}))
        self.assertEqual(P.load_registry(path).postures[0].id,
                         "nothing-said")

    def test_load_registry_missing_file(self):
        with self.assertRaises(P.RegistryError):
            P.load_registry("/nonexistent/posture-registry.json")

    def test_load_registry_bad_json(self):
        with self.assertRaises(P.RegistryError):
            P.load_registry(self._write("{not json"))

    def test_load_tagging_roundtrip_and_errors(self):
        path = self._write(json.dumps(
            {"format": P.TAGGING_FORMAT, "version": 1,
             "projects": [_project()]}))
        self.assertEqual(P.load_tagging(path).assignments[0].project,
                         "example-project-one")
        with self.assertRaises(P.TaggingError):
            P.load_tagging("/nonexistent/tagging.json")
        with self.assertRaises(P.TaggingError):
            P.load_tagging(self._write("{not json"))


class ExampleRegistryTest(unittest.TestCase):
    ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    EXAMPLE = os.path.join(ROOT, "runner", "tools",
                           "disclosure-registry.example.json")

    def test_the_shipped_example_is_valid(self):
        reg = P.load_registry(self.EXAMPLE)
        active = [p for p in reg.postures if p.status == "active"]
        retired = [p for p in reg.postures if p.status == "retired"]
        self.assertEqual(len(active), 3)
        self.assertEqual(len(retired), 1)

    def test_the_examples_retired_posture_resolves_to_an_active_one(self):
        reg = P.load_registry(self.EXAMPLE)
        (retired,) = [p for p in reg.postures if p.status == "retired"]
        end = reg.successor_of(retired)
        self.assertIsNotNone(end)
        self.assertEqual(end.status, "active")

    def test_the_example_declares_the_three_standing_postures(self):
        reg = P.load_registry(self.EXAMPLE)
        ids = {p.id for p in reg.postures if p.status == "active"}
        self.assertEqual(ids, {"nothing-said", "named-and-described",
                               "named-only"})


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.registry_path = self._dump(
            "registry.json",
            {"format": P.REGISTRY_FORMAT, "version": 1,
             "postures": [
                 _posture("nothing-said", "A"),
                 _posture("named-only", "C"),
                 _posture("old-posture", "D", status="retired",
                          successor="named-only")]})

    def _dump(self, name, data):
        path = os.path.join(self.dir.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return path

    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = P.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_validate_a_good_registry_exits_0(self):
        code, out, _ = self._run(
            ["validate", "--registry", self.registry_path])
        self.assertEqual(code, 0)
        self.assertIn("3 posture(s), 2 active, 1 retired", out)

    def test_validate_a_bad_registry_exits_2(self):
        bad = self._dump("bad.json", {"format": "nope", "version": 1,
                                      "postures": []})
        code, _, err = self._run(["validate", "--registry", bad])
        self.assertEqual(code, 2)
        self.assertIn("disclosure:", err)

    def test_validate_a_missing_registry_exits_2(self):
        code, _, _ = self._run(
            ["validate", "--registry",
             os.path.join(self.dir.name, "absent.json")])
        self.assertEqual(code, 2)

    def test_check_clean_tagging_exits_0_and_reports_the_posture(self):
        tagging = self._dump(
            "tagging.json",
            {"format": P.TAGGING_FORMAT, "version": 1,
             "projects": [_project(tag="A")]})
        code, out, _ = self._run(
            ["check", "--registry", self.registry_path, tagging])
        self.assertEqual(code, 0)
        self.assertIn("nothing-said (active)", out)
        self.assertIn(SAY, out)

    def test_check_unknown_tag_exits_1(self):
        tagging = self._dump(
            "tagging.json",
            {"format": P.TAGGING_FORMAT, "version": 1,
             "projects": [_project(tag="Z")]})
        code, out, _ = self._run(
            ["check", "--registry", self.registry_path, tagging])
        self.assertEqual(code, 1)
        self.assertIn("UNKNOWN TAG", out)

    def test_check_retired_posture_exits_1_and_names_the_successor(self):
        tagging = self._dump(
            "tagging.json",
            {"format": P.TAGGING_FORMAT, "version": 1,
             "projects": [_project(tag="D")]})
        code, out, _ = self._run(
            ["check", "--registry", self.registry_path, tagging])
        self.assertEqual(code, 1)
        self.assertIn("RETIRED", out)
        self.assertIn("successor: named-only", out)

    def test_check_malformed_tagging_exits_2(self):
        path = os.path.join(self.dir.name, "broken.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        code, _, _ = self._run(
            ["check", "--registry", self.registry_path, path])
        self.assertEqual(code, 2)

    def test_check_missing_tagging_exits_2(self):
        code, _, _ = self._run(
            ["check", "--registry", self.registry_path,
             os.path.join(self.dir.name, "absent.json")])
        self.assertEqual(code, 2)

    def test_check_aggregates_problems_across_files(self):
        one = self._dump(
            "one.json",
            {"format": P.TAGGING_FORMAT, "version": 1,
             "projects": [_project("p-one", "Z")]})
        two = self._dump(
            "two.json",
            {"format": P.TAGGING_FORMAT, "version": 1,
             "projects": [_project("p-two", "D")]})
        code, _, err = self._run(
            ["check", "--registry", self.registry_path, one, two])
        self.assertEqual(code, 1)
        self.assertIn("2 problem(s)", err)


if __name__ == "__main__":
    unittest.main()
