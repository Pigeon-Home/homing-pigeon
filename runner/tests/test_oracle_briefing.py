# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The Oracle's briefing (shape 4): the same door, its own layer
on top. The design record is
docs/steady/design/oracle-briefing-design.md; its supposition,
written before the build: if the Oracle's standing instructions
are resolved against the checked-out project at ask time,
through the same discovery surface a visiting system uses, and
assembled through the single ask seam, then every Oracle
surface briefs from the same texts a visitor is briefed from,
plus the Oracle's own layer; the briefing moves when the
checkout moves; and a canonical text carried this way reaches
the model verbatim -- measured here by the posture semantics
text appearing byte-for-byte in the assembled briefing of a
fixture deployment.

Stage 1: the Oracle layer gets its home. These tests pin the
resolution (a snapshot root wins; the source tree is the
fallback; nothing else can name a path into the briefing), the
verbatim carriage of the layer's first text, and the assembly's
totality -- a briefing failure is an absent layer, never an
exception at the seam.
"""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import briefing  # noqa: E402

LAYER_REL = os.path.join("docs", "steady", "oracle",
                         "instructions.md")
POSTURE_OPENING = ("A disclosure posture is declared in the "
                   "posture registry")


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _posture_block():
    """The canonical posture paragraph, read out of the shipped
    layer file the way the fixture test in the design names it:
    the first paragraph under the postures heading."""
    with open(os.path.join(REPO, LAYER_REL),
              encoding="utf-8") as fh:
        text = fh.read()
    marker = "## Disclosure postures"
    start = text.index(marker) + len(marker)
    body = text[start:].strip()
    return body.split("\n\n", 1)[0].strip()


def _snapshot_base(tmp, layer_text=None, commit="abc123"):
    """A fixture deployment: a state dir whose project/ snapshot
    carries an index, CI facts, and (unless layer_text is None)
    the Oracle layer file."""
    project = os.path.join(tmp, "project")
    _write(os.path.join(project, "PROJECT-SNAPSHOT.md"),
           "# fixture snapshot\n")
    _write(os.path.join(project, "CI-SNAPSHOT.json"),
           json.dumps({"version": "0", "commit": commit}))
    if layer_text is not None:
        _write(os.path.join(project, LAYER_REL), layer_text)
    return tmp


class ResolveRootTest(unittest.TestCase):
    def test_snapshot_root_wins_over_the_source_tree(self):
        with tempfile.TemporaryDirectory() as d:
            base = _snapshot_base(d, layer_text="# fixture\n")
            self.assertEqual(os.path.join(d, "project"),
                             briefing.resolve_root(base))

    def test_source_tree_is_the_fallback(self):
        root = briefing.resolve_root(None)
        self.assertTrue(os.path.isfile(
            os.path.join(root, LAYER_REL)))

    def test_base_without_a_snapshot_falls_back(self):
        with tempfile.TemporaryDirectory() as d:
            root = briefing.resolve_root(d)
            self.assertTrue(os.path.isfile(
                os.path.join(root, LAYER_REL)))

    def test_non_string_base_dir_falls_back(self):
        for bad in (None, 123, b"/tmp", ["x"]):
            with self.subTest(bad=bad):
                root = briefing.resolve_root(bad)
                self.assertTrue(os.path.isfile(
                    os.path.join(root, LAYER_REL)))


class OracleLayerTest(unittest.TestCase):
    def test_the_posture_text_is_carried_verbatim(self):
        root = briefing.resolve_root(None)
        layer = briefing.oracle_layer(root)
        self.assertIn(_posture_block(), layer)

    def test_the_stamp_line_does_not_ride(self):
        root = briefing.resolve_root(None)
        layer = briefing.oracle_layer(root)
        self.assertNotIn("Agent-Stamp", layer)

    def test_a_fixture_deployment_briefs_from_its_own_text(self):
        # The briefing moves when the checkout moves: a snapshot
        # carrying its own layer text briefs from that text, not
        # from the source tree's.
        fixture = ("# Agent-Stamp: fixture\n\n# Fixture layer\n\n"
                   + POSTURE_OPENING + ", fixture wording.\n")
        with tempfile.TemporaryDirectory() as d:
            base = _snapshot_base(d, layer_text=fixture)
            layer = briefing.oracle_layer(briefing.resolve_root(base))
            self.assertIn("fixture wording", layer)
            self.assertNotIn("Agent-Stamp", layer)

    def test_a_missing_layer_is_absent_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            base = _snapshot_base(d, layer_text=None)
            root = briefing.resolve_root(base)
            self.assertEqual("", briefing.oracle_layer(root))
            self.assertEqual("", briefing.assemble_briefing(base))

    def test_an_unreadable_layer_is_absent(self):
        with tempfile.TemporaryDirectory() as d:
            base = _snapshot_base(d, layer_text=None)
            os.makedirs(os.path.join(d, "project", LAYER_REL))
            self.assertEqual("", briefing.assemble_briefing(base))


class AssembleTest(unittest.TestCase):
    def test_the_layer_rides_under_its_header(self):
        text = briefing.assemble_briefing(None)
        self.assertIn(briefing.ORACLE_HEADER, text)
        self.assertIn(POSTURE_OPENING, text)

    def test_assembly_is_deterministic(self):
        self.assertEqual(briefing.assemble_briefing(None),
                         briefing.assemble_briefing(None))

    def test_the_oracle_scope_carries_no_surface_text(self):
        # Stage 4's surfaces receive layer 2 only; the scope must
        # never grow the discovery surface.
        text = briefing.assemble_briefing(None, scope="oracle")
        self.assertIn(POSTURE_OPENING, text)
        self.assertNotIn(briefing.SURFACE_HEADER, text)

    def test_assembly_never_raises(self):
        for bad in (None, 123, b"x", object()):
            with self.subTest(bad=type(bad).__name__):
                self.assertIsInstance(
                    briefing.assemble_briefing(bad), str)
                self.assertIsInstance(
                    briefing.assemble_briefing(bad, scope="oracle"),
                    str)


class ReportTest(unittest.TestCase):
    def test_the_report_names_root_commit_and_layer(self):
        with tempfile.TemporaryDirectory() as d:
            base = _snapshot_base(d, layer_text="# fixture\n\nbody\n",
                                  commit="deadbeefcafe")
            report = briefing.briefing_report(base)
            self.assertEqual(os.path.join(d, "project"),
                             report["root"])
            self.assertEqual("deadbeefcafe", report["commit"])
            layer = report["layers"]["oracle"]
            self.assertEqual(briefing.ORACLE_LAYER_PATH,
                             layer["path"])
            self.assertTrue(layer["present"])
            self.assertGreater(layer["chars"], 0)

    def test_the_report_records_an_absent_layer(self):
        with tempfile.TemporaryDirectory() as d:
            base = _snapshot_base(d, layer_text=None)
            layer = briefing.briefing_report(base)["layers"]["oracle"]
            self.assertFalse(layer["present"])
            self.assertEqual(0, layer["chars"])


class ManifestTest(unittest.TestCase):
    """Stage 2: the door, resolved locally. The manifest is the
    curation; these tests pin its shape -- every named file
    stands in the tree, every named heading resolves to a real
    section, caps are positive, and the total stays inside the
    declared surface budget."""

    def test_paths_are_unique_and_stand_in_the_tree(self):
        paths = [e["path"] for e in briefing.BRIEFING_MANIFEST]
        self.assertEqual(len(paths), len(set(paths)))
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(os.path.isfile(
                    os.path.join(REPO, path)))

    def test_every_entry_declares_a_positive_carry(self):
        for entry in briefing.BRIEFING_MANIFEST:
            with self.subTest(path=entry["path"]):
                if "whole" in entry:
                    self.assertGreater(entry["whole"], 0)
                else:
                    self.assertTrue(entry["sections"])
                    for heading, cap in entry["sections"]:
                        self.assertTrue(heading)
                        self.assertGreater(cap, 0)

    def test_the_total_stays_inside_the_surface_budget(self):
        total = 0
        for entry in briefing.BRIEFING_MANIFEST:
            if "whole" in entry:
                total += entry["whole"]
            else:
                total += sum(cap for _h, cap in entry["sections"])
        self.assertLessEqual(total, briefing.SURFACE_TOTAL_CAP)

    def test_every_named_heading_resolves(self):
        root = briefing.resolve_root(None)
        for entry in briefing.BRIEFING_MANIFEST:
            if "whole" in entry:
                continue
            with open(os.path.join(REPO, entry["path"]),
                      encoding="utf-8") as fh:
                text = fh.read()
            for heading, cap in entry["sections"]:
                with self.subTest(path=entry["path"],
                                  heading=heading):
                    self.assertTrue(briefing._section_extract(
                        text, heading, cap))


class SurfaceTest(unittest.TestCase):
    """The assembled surface: extracts from the local checkout,
    in manifest order, bounded, and offered to the agent door
    as pointers rather than text."""

    def test_the_source_tree_assembles_as_extracts(self):
        root = briefing.resolve_root(None)
        text, mode = briefing.surface_text(root)
        self.assertEqual("extracts", mode)
        # The split is the two-sides statement of the door.
        self.assertIn("There are two sides. They do not share "
                      "credentials.", text)
        # The size warning survives its cap.
        self.assertIn("fair warning", text)

    def test_the_surface_is_bounded(self):
        root = briefing.resolve_root(None)
        text, _mode = briefing.surface_text(root)
        # Section caps sum to the budget; per-file headers and
        # cut markers are the only overhead.
        self.assertLessEqual(len(text),
                             briefing.SURFACE_TOTAL_CAP + 1000)

    def test_ask_scope_orders_surface_before_oracle_layer(self):
        text = briefing.assemble_briefing(None, scope="ask")
        self.assertLess(text.index("discovery surface"),
                        text.index(briefing.ORACLE_HEADER))

    def test_agent_scope_carries_pointers_not_text(self):
        root = briefing.resolve_root(None)
        text = briefing.assemble_briefing(None, scope="agent")
        self.assertIn(root, text)
        self.assertIn("PROTOCOL.md", text)
        self.assertNotIn("There are two sides. They do not "
                         "share credentials.", text)
        self.assertIn(POSTURE_OPENING, text)

    def test_a_fixture_snapshot_briefs_its_own_surface(self):
        with tempfile.TemporaryDirectory() as d:
            base = _snapshot_base(d, layer_text="# layer\n")
            project = os.path.join(d, "project")
            _write(os.path.join(project, "AGENTS.md"),
                   "# Agents\n\n## The split\n\nThere are two "
                   "sides. They do not share credentials.\n")
            text = briefing.assemble_briefing(base, scope="ask")
            self.assertIn("credentials", text)
            self.assertIn("commit abc123", text)


class InspectBriefingTest(unittest.TestCase):
    """--inspect briefing prints the report (sizes and sources
    only) and exits 0 without a mailbox."""

    def test_inspect_briefing(self):
        import contextlib
        import io
        from types import SimpleNamespace
        from runner.runner import run_inspect
        args = SimpleNamespace(inspect="briefing", config=None,
                               job_id=None)
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d}
            with contextlib.redirect_stdout(buf):
                rc = run_inspect(cfg, args)
        self.assertEqual(0, rc)
        data = json.loads(buf.getvalue())
        self.assertIn("root", data)
        self.assertIn("surface", data)
        self.assertTrue(data["layers"]["oracle"]["present"])
        self.assertGreater(data["assembled_chars"]["ask"],
                           data["assembled_chars"]["oracle"])
        self.assertGreater(data["assembled_chars"]["oracle"], 0)


class SnapshotIndexBriefingTest(unittest.TestCase):
    """The snapshot index renders its briefing section from the
    same manifest the runner assembles from."""

    def test_the_index_names_the_briefing(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "make_snapshot_for_briefing",
            os.path.join(REPO, "runner", "tools",
                         "make_snapshot.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        snap = {"commit": "abc123", "version": "3.15.20.6",
                "run_url": "", "workflows": [], "tests": None}
        index = mod.index_markdown(snap, "note", False, 3)
        self.assertIn("## Briefing", index)
        self.assertIn("docs/steady/oracle/instructions.md", index)
        for entry in briefing.BRIEFING_MANIFEST:
            with self.subTest(path=entry["path"]):
                self.assertIn("`%s`" % entry["path"], index)


if __name__ == "__main__":
    unittest.main()
