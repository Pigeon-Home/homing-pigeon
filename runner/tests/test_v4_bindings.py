#!/usr/bin/env python3
"""The v4 binding's constraint spec, held to the tree, and the fuzz
corpus at the real doors.

docs/infrastructure-documents/proofs/v4-bindings.json is the
registry. It ties every constraint of constraints.md (C1 to C31)
to the properties that state it, the code that keeps it, the
tests that pin it and the fuzz data that has reached it, and it
ties every property (P1 to P13) to its model, the invariants its
configuration checks, its conformance suite and its steps in
general.tla. v4-bindings.md is the same registry as a page.

The first half of this module holds each tie. A constraint with
no property, a code site that moved, a pin that was renamed, a
model that lost an invariant, a fuzz target that no longer
reaches the function it is bound to: each fails here, by name.

The fuzz part of the registry is measured, not written. `measure`
replays every corpus entry of every target under a profiler and
counts, for each constraint's code site, the entries that enter
it, and it notes the size of each by the campaign's own count of
an entry's bytes. A suite run does not repeat the whole count. It
replays 1 witness entry for each tie and looks again only where
the witness has gone.

    python3 runner/tests/test_v4_bindings.py measure
    python3 runner/tests/test_v4_bindings.py measure --write
    python3 runner/tests/test_v4_bindings.py page

The second half takes the fuzz corpus to the doors themselves.
No fuzz target enters handle_mail, the gate P1 is about, so the
wire, crypto and mail corpora are sent through it here, and each
run it allows is held to P1's clauses by this module's own
reading of the bytes. The local corpus goes to the local door
with a watch on the run, the secret corpus to the floor at each
place that applies it, and corpus text through the result
fitting.
"""
import ast
import collections
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner as RUNNER  # noqa: E402
from runner.guard import security as SECURITY  # noqa: E402
from runner.tests import test_proof_conformance as DOOR  # noqa: E402
from runner.tests import test_proof_constraints as PINS  # noqa: E402
from runner.tests import test_v4_general as GENERAL  # noqa: E402
from runner.tools import de_dust_corpus as DD  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402

PROOFS = os.path.join(ROOT, "docs", "infrastructure-documents", "proofs")
REGISTRY_PATH = os.path.join(PROOFS, "v4-bindings.json")
PAGE_PATH = os.path.join(PROOFS, "v4-bindings.md")
REPLAY = "runner/tests/test_de_dust_corpus.py"

_RUNNER_DIR = os.path.join(ROOT, "runner") + os.sep
_TESTS_DIR = os.path.join(ROOT, "runner", "tests") + os.sep
_TOOL = os.path.join(ROOT, "runner", "tools", "de_dust_corpus.py")
_CFG_WORDS = {
    "SPECIFICATION", "CONSTANT", "CONSTANTS", "INIT", "NEXT", "PROPERTY",
    "PROPERTIES", "INVARIANT", "INVARIANTS", "CHECK_DEADLOCK", "VIEW",
    "SYMMETRY", "CONSTRAINT", "CONSTRAINTS", "ACTION_CONSTRAINT", "ALIAS"}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def registry():
    with open(REGISTRY_PATH, encoding="utf-8") as fh:
        return json.load(fh, object_pairs_hook=collections.OrderedDict)


# ---- reading the tree

def functions_in(path):
    """Every function a source file defines, at any depth."""
    text = _read(os.path.join(ROOT, path))
    if path.endswith(".js"):
        return set(re.findall(r"\bfunction\s+(\w+)\s*\(", text))
    return {node.name for node in ast.walk(ast.parse(text))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def methods_by_class_in(path):
    """{class: [test methods]} of a test module."""
    out = {}
    for node in ast.parse(_read(os.path.join(ROOT, path))).body:
        if isinstance(node, ast.ClassDef):
            out[node.name] = [item.name for item in node.body
                              if isinstance(item, ast.FunctionDef)
                              and item.name.startswith("test_")]
    return out


def cfg_invariants(name):
    """The invariants a model configuration checks, in its order."""
    text = re.sub(r"\\\*.*", "", _read(os.path.join(PROOFS, name)))
    out, reading = [], False
    for word in text.split():
        if word in _CFG_WORDS:
            reading = word in ("INVARIANT", "INVARIANTS")
        elif reading and word not in out:
            out.append(word)
    return out


def general_marks():
    """{property: [steps of general.tla that mark it]}, in the
    file's order."""
    text = re.sub(r"\\\*.*", "", _read(os.path.join(PROOFS, "general.tla")))
    marks, step = collections.OrderedDict(), None
    for line in text.splitlines():
        head = re.match(r"^(\w+)(\([^)]*\))? ==", line)
        if head:
            step = head.group(1)
        for prop in re.findall(r'!\["(P\d+)"\]', line):
            if step not in marks.setdefault(prop, []):
                marks[prop].append(step)
    return marks


def index_ties():
    """{constraint: {property: clauses}} as v4-properties.md gives
    it: Part 1's table for C1 to C27, and for the rest the
    property stated beside or for each constraint."""
    text = _read(os.path.join(PROOFS, "v4-properties.md"))
    ties = collections.OrderedDict()
    for cid, cell in re.findall(
            r"(?m)^\| (C\d+) \| [^|]+ \| ([^|]+) \|$", text):
        row = collections.OrderedDict()
        for part in cell.split(";"):
            hit = re.search(r"\b(P\d+)\b(.*)", part.strip())
            if hit:
                rest = hit.group(2).strip(" ,")
                row[hit.group(1)] = ("the whole property"
                                     if rest in ("", "below") else rest)
        ties[cid] = row
    # Part 2 states each harvested constraint and then its
    # property, heading after heading.
    heads = re.findall(r"(?m)^### ([CP]\d+)\.", text)
    for here, after in zip(heads, heads[1:]):
        if here.startswith("C") and after.startswith("P"):
            ties[here] = collections.OrderedDict(
                [(after, "the whole property")])
    return ties


def corpus(target):
    return [entry for entry in DD.load(DD.corpus_path(target))
            if isinstance(entry, dict) and "data" in entry]


# The edges of the size bands, in bytes: under 100, 100 to 999,
# 1,000 to 9,999, and 10,000 and over.
BANDS = (100, 1000, 10000)


def size_of(entry):
    """The bytes of 1 corpus entry by the campaign's own count: a
    text entry's UTF-8 bytes, a payload entry's JSON as the tool
    writes it. The tool holds a child to its cap by this count."""
    data = entry["data"]
    if entry.get("kind") == "text":
        return len(data.encode("utf-8", "surrogatepass"))
    return len(json.dumps(data, ensure_ascii=True))


def band_of(size):
    return sum(1 for edge in BANDS if size >= edge)


def sized(sizes):
    """Sizes as the registry carries them: the smallest, the
    largest, and how many fall in each band."""
    bands = [0] * (len(BANDS) + 1)
    for size in sizes:
        bands[band_of(size)] += 1
    return collections.OrderedDict([
        ("smallest", min(sizes) if sizes else None),
        ("largest", max(sizes) if sizes else None),
        ("bands", bands)])


def leave_no_trace(case):
    """The corpus tool keeps 1 temp folder for the process, and a
    check may add to the import path. A test that runs the tool's
    checks puts both back when it ends."""
    path = list(sys.path)

    def restore():
        sys.path[:] = path
        DD._remove_own_tmp()

    case.addCleanup(restore)


# ---- the fuzz part, measured

def entered(target, entry):
    """The runner functions 1 corpus entry enters under its
    target's check, as path:function. The caller holds the rig."""
    seen = set()

    def watch(frame, event, _arg):
        if event == "call":
            code = frame.f_code
            name = code.co_filename
            if name.startswith(_RUNNER_DIR) and name != _TOOL \
                    and not name.startswith(_TESTS_DIR):
                seen.add("%s:%s" % (
                    name[len(ROOT) + 1:].replace(os.sep, "/"),
                    code.co_name))

    was, was_threads = sys.getprofile(), threading.getprofile()
    threading.setprofile(watch)
    sys.setprofile(watch)
    try:
        try:
            DD.check(target, entry)
        except DD.Crash:
            pass
    finally:
        sys.setprofile(was)
        threading.setprofile(was_threads)
    return seen


def traces(target, site):
    """Does the target's own tracer follow the site's file?"""
    path = site.split(":")[0]
    return any(os.path.relpath(name, ROOT).replace(os.sep, "/") == path
               for name in DD.TARGETS[target]["files"])


def run_log():
    """{target: totals of its grow runs} from the campaign's log."""
    totals = collections.defaultdict(collections.Counter)
    with open(os.path.join(ROOT, "runner", "tests", "de_dust",
                           "runs.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            run = json.loads(line)
            if run.get("kind") != "grow":
                continue
            row = totals[run["target"]]
            row["runs"] += 1
            row["tried"] += run.get("tried", 0)
            for name, count in (run.get("outcomes") or {}).items():
                row[name] += count
    return totals


def measure():
    """The registry's fuzz part as the tree gives it now: (ties
    by constraint, sites no entry enters, targets, each
    constraint's reach by size)."""
    reg = registry()
    sites = {site for row in reg["constraints"] for site in row["code"]}
    # {target: {site: {place in the corpus: size}}}
    inside = collections.defaultdict(
        lambda: collections.defaultdict(collections.OrderedDict))
    witness = collections.defaultdict(dict)
    whole = {}

    def replay():
        for target in sorted(DD.TARGETS):
            entries = corpus(target)
            whole[target] = [size_of(entry) for entry in entries]
            for place, entry in enumerate(entries):
                for site in entered(target, entry) & sites:
                    inside[target][site][place] = whole[target][place]
                    witness[target].setdefault(site, entry["id"])

    DD._with_rig(replay)
    ties, bare, bound = collections.OrderedDict(), {}, set()
    reach = collections.OrderedDict()
    for row in reg["constraints"]:
        ties[row["id"]], bare[row["id"]] = [], []
        within = {}
        for site in row["code"]:
            reached = sorted(((target, len(hits[site]))
                              for target, hits in inside.items()
                              if site in hits),
                             key=lambda pair: (-pair[1], pair[0]))
            own = [pair for pair in reached if traces(pair[0], site)]
            # A target whose tracer follows the file is bound
            # first. Where none does, the 2 targets with the most
            # entries inside stand for the rest.
            chosen = own or reached[:2]
            if not chosen:
                bare[row["id"]].append(site)
            for target, hits in chosen:
                tie = collections.OrderedDict([
                    ("site", site), ("target", target), ("entries", hits),
                    ("traced", traces(target, site)),
                    ("witness", witness[target][site])])
                tie.update(sized(list(inside[target][site].values())))
                ties[row["id"]].append(tie)
                bound.add(target)
                # An entry inside 2 of the constraint's functions
                # is 1 entry of the constraint's reach.
                for place, size in inside[target][site].items():
                    within[(target, place)] = size
        reach[row["id"]] = None
        if within:
            reach[row["id"]] = collections.OrderedDict(
                [("entries", len(within))])
            reach[row["id"]].update(sized(list(within.values())))
    log = run_log()
    targets = collections.OrderedDict()
    for target in sorted(DD.TARGETS):
        row = log[target]
        targets[target] = collections.OrderedDict([
            ("runs", row["runs"]), ("tried", row["tried"]),
            ("accepted", row["accepted"]), ("refused", row["refused"]),
            ("crash", row["crash"]), ("slow", row["slow"]),
            ("entries", len(whole[target])), ("bound", target in bound)])
        targets[target].update(sized(whole[target]))
    return ties, bare, targets, reach


# ---- the page's tables, rendered from the registry

def _n(number):
    return "{:,}".format(number)


def _code(site):
    path, name = site.split(":")
    return "`%s` in `%s`" % (name, path)


def render_constraints(reg):
    lines = ["| ID | Constraint | Stated by | Code | Pins | Fuzz data |",
             "|----|------------|-----------|------|------|-----------|"]
    for row in reg["constraints"]:
        stated = "; ".join("%s %s" % pair if pair[1] != "the whole property"
                           else "%s, the whole property" % pair[0]
                           for pair in row["properties"].items())
        by_target = collections.OrderedDict()
        for tie in row["fuzz"]:
            by_target[tie["target"]] = max(
                by_target.get(tie["target"], 0), tie["entries"])
        fuzz = ", ".join("`%s` %s" % (target, _n(hits))
                         for target, hits in by_target.items()) or "none"
        lines.append("| %s | %s | %s | %s | %d | %s |" % (
            row["id"], row["name"], stated,
            "; ".join(_code(site) for site in row["code"]),
            len(row["pins"]), fuzz))
    return "\n".join(lines)


def render_properties(reg):
    lines = ["| Property | Stated in | Model | Checked invariants | "
             "Conformance | Steps in `general.tla` | "
             "Seams that carry it |",
             "|----------|-----------|-------|--------------------|"
             "-------------|-------------------------|"
             "---------------------|"]
    for pid, row in reg["properties"].items():
        lines.append("| %s | `%s` | %s | %s | %s | %s | %s |" % (
            pid, row["stated"],
            "`%s`" % row["model"] if row["model"] else "none",
            ", ".join("`%s`" % name for name in row["holds"]) or "none",
            ", ".join("`%s`" % name.split("/")[-1]
                      for name in row["conformance"]),
            ", ".join("`%s`" % step for step in row["general"]),
            ", ".join("`%s`" % seam for seam in row["seams"])))
    return "\n".join(lines)


def render_fuzz(reg):
    reach = collections.defaultdict(list)
    for row in reg["constraints"]:
        for tie in row["fuzz"]:
            if row["id"] not in reach[tie["target"]]:
                reach[tie["target"]].append(row["id"])
    lines = ["| Target | Grow runs | Inputs tried | Refused | Accepted | "
             "Corpus entries | Constraints it reaches |",
             "|--------|-----------|--------------|---------|----------|"
             "----------------|------------------------|"]
    for target, row in reg["fuzz"].items():
        if row["bound"]:
            lines.append("| `%s` | %s | %s | %s | %s | %s | %s |" % (
                target, _n(row["runs"]), _n(row["tried"]),
                _n(row["refused"]), _n(row["accepted"]),
                _n(row["entries"]), ", ".join(reach[target])))
    return "\n".join(lines)


def render_gaps(reg):
    lines = ["| ID | Constraint | Code no corpus entry enters |",
             "|----|------------|-----------------------------|"]
    for row in reg["constraints"]:
        if row["unfuzzed"]:
            lines.append("| %s | %s | %s |" % (
                row["id"], row["name"],
                "; ".join(_code(site) for site in row["unfuzzed"])))
    return "\n".join(lines)


def render_sizes(reg):
    lines = ["| ID | Constraint | Entries inside | Smallest | Largest | "
             "Under 100 bytes | 100 to 999 | 1,000 to 9,999 | "
             "10,000 and over |",
             "|----|------------|----------------|----------|---------|"
             "-----------------|------------|----------------|"
             "-----------------|"]
    for row in reg["constraints"]:
        reach = row["reach"]
        # A constraint with no fuzz data has nothing to size. Its
        # row is empty, which is not the same as small.
        cells = ["none"] + [""] * (len(BANDS) + 3)
        if reach:
            cells = [_n(reach["entries"]), _n(reach["smallest"]),
                     _n(reach["largest"])] + [_n(count)
                                              for count in reach["bands"]]
        lines.append("| %s | %s | %s |" % (
            row["id"], row["name"], " | ".join(cells)))
    return "\n".join(lines)


RENDERS = collections.OrderedDict([
    ("constraints", render_constraints), ("properties", render_properties),
    ("fuzz", render_fuzz), ("sizes", render_sizes), ("gaps", render_gaps)])


def totals(reg):
    """The headline counts the page states."""
    rows = reg["constraints"]
    fuzz = reg["fuzz"].values()
    bound = [row for row in fuzz if row["bound"]]
    return collections.OrderedDict([
        ("constraints", len(rows)),
        ("properties", len(reg["properties"])),
        ("code sites", sum(len(row["code"]) for row in rows)),
        ("pins", sum(len(row["pins"]) for row in rows)),
        ("fuzz ties", sum(len(row["fuzz"]) for row in rows)),
        ("constraints with fuzz data",
         sum(1 for row in rows if row["fuzz"])),
        ("constraints with none", sum(1 for row in rows if not row["fuzz"])),
        ("sites no entry enters", sum(len(row["unfuzzed"]) for row in rows)),
        ("targets", len(reg["fuzz"])),
        ("bound targets", len(bound)),
        ("grow runs", sum(row["runs"] for row in fuzz)),
        ("inputs tried", sum(row["tried"] for row in fuzz)),
        ("inputs tried by bound targets",
         sum(row["tried"] for row in bound)),
        ("corpus entries", sum(row["entries"] for row in fuzz)),
        ("corpus entries of bound targets",
         sum(row["entries"] for row in bound)),
        ("constraints sized", sum(1 for row in rows if row["reach"])),
        ("entries under 100 bytes", sum(row["bands"][0] for row in fuzz)),
        ("entries of 100 to 999 bytes",
         sum(row["bands"][1] for row in fuzz)),
        ("entries of 1,000 to 9,999 bytes",
         sum(row["bands"][2] for row in fuzz)),
        ("entries of 10,000 bytes and over",
         sum(row["bands"][3] for row in fuzz)),
        ("largest entry", max(row["largest"] for row in fuzz
                              if row["largest"] is not None))])


# ---- the ties, held

class Ties(unittest.TestCase):
    """Constraint to property, to code, to pin; property to model,
    to conformance, to its steps in the general model."""

    @classmethod
    def setUpClass(cls):
        cls.reg = registry()
        cls.rows = collections.OrderedDict(
            (row["id"], row) for row in cls.reg["constraints"])

    def test_the_registry_binds_the_inventory_s_31_and_no_other(self):
        text = _read(os.path.join(PROOFS, "constraints.md"))
        heads = re.findall(r"(?m)^## (C\d+)\. ", text)
        self.assertEqual(["C%d" % n for n in range(1, 32)], heads)
        self.assertEqual(heads, list(self.rows))
        names = dict(re.findall(r"(?m)^\| (C\d+) \| ([^|]+?) \|", text))
        for cid, row in self.rows.items():
            self.assertEqual(names[cid], row["name"], cid)

    def test_each_constraint_carries_the_properties_the_index_gives_it(self):
        index = index_ties()
        self.assertEqual(list(self.rows), list(index))
        for cid, row in self.rows.items():
            self.assertEqual(dict(index[cid]), dict(row["properties"]), cid)
            self.assertTrue(row["properties"], cid)

    def test_every_property_states_a_constraint_and_cites_only_its_own(self):
        bound = collections.defaultdict(set)
        for cid, row in self.rows.items():
            for pid in row["properties"]:
                bound[pid].add(cid)
        self.assertEqual(set(self.reg["properties"]), set(bound))
        self.assertEqual(["P%d" % n for n in range(1, 14)],
                         list(self.reg["properties"]))
        # A property's own section may cite fewer constraints than
        # the index binds to it. It cites none the index does not.
        standing = _read(os.path.join(PROOFS, "properties.md"))
        later = _read(os.path.join(PROOFS, "v4-properties.md"))
        for pid, row in self.reg["properties"].items():
            if row["stated"] == "properties.md":
                start = standing.index("\n## %s. " % pid)
                end = standing.index("\n## ", start + 1)
                section = standing[start:end]
            else:
                self.assertEqual("v4-properties.md", row["stated"])
                start = later.index("\n### %s. " % pid)
                ends = [later.find(mark, start + 1)
                        for mark in ("\n### ", "\n## ")]
                section = later[start:min(e for e in ends if e > 0)]
            cited = set(re.findall(r"\bC\d+\b", section))
            self.assertTrue(cited, pid)
            self.assertLessEqual(cited, bound[pid], pid)

    def test_every_code_site_is_a_function_in_the_tree(self):
        seen = {}
        for cid, row in self.rows.items():
            self.assertTrue(row["code"], cid)
            for site in row["code"]:
                path, name = site.split(":")
                if path not in seen:
                    seen[path] = functions_in(path)
                self.assertIn(name, seen[path], "%s: %s" % (cid, site))

    def test_every_pin_is_a_test_in_the_tree(self):
        seen = {}
        for cid, row in self.rows.items():
            self.assertTrue(row["pins"], cid)
            for pin in row["pins"]:
                path, _, rest = pin.partition("::")
                if path not in seen:
                    seen[path] = methods_by_class_in(path)
                if not rest:
                    self.assertTrue(any(seen[path].values()), pin)
                    continue
                name, _, method = rest.partition(".")
                self.assertIn(name, seen[path], pin)
                if method:
                    self.assertIn(method, seen[path][name], pin)
                else:
                    self.assertTrue(seen[path][name], pin)

    def test_a_pin_named_for_a_constraint_is_bound_to_it(self):
        # test_c14_... in either pin file is C14's, and the
        # registry carries every one of them.
        for path in ("runner/tests/test_proof_constraints.py",
                     "runner/tests/test_v4_binding.py"):
            for name, methods in methods_by_class_in(path).items():
                for method in methods:
                    hit = re.match(r"test_c(\d+)_", method)
                    if hit:
                        self.assertIn(
                            "%s::%s.%s" % (path, name, method),
                            self.rows["C" + hit.group(1)]["pins"])

    def test_every_property_names_a_model_the_shelf_carries(self):
        for pid, row in self.reg["properties"].items():
            if row["model"] is None:
                continue
            model = _read(os.path.join(PROOFS, row["model"]))
            self.assertTrue(row["configurations"], pid)
            checked = []
            for name in row["configurations"]:
                for invariant in cfg_invariants(name):
                    if invariant not in checked:
                        checked.append(invariant)
            self.assertEqual(checked, row["holds"], pid)
            for invariant in row["holds"]:
                self.assertRegex(
                    model, r"(?m)^%s ==" % re.escape(invariant), pid)

    def test_p9_is_the_1_property_with_no_model_and_the_shelf_says_why(self):
        bare = [pid for pid, row in self.reg["properties"].items()
                if row["model"] is None]
        self.assertEqual(["P9"], bare)
        self.assertEqual([], self.reg["properties"]["P9"]["holds"])
        self.assertIn("P9 admits no model",
                      _read(os.path.join(PROOFS, "v4-working.md")))

    def test_every_conformance_suite_is_in_the_tree(self):
        seen = {}
        for pid, row in self.reg["properties"].items():
            self.assertTrue(row["conformance"], pid)
            for suite in row["conformance"]:
                path, _, name = suite.partition("::")
                if path not in seen:
                    seen[path] = methods_by_class_in(path)
                if name:
                    self.assertTrue(seen[path].get(name), suite)
                else:
                    self.assertTrue(any(seen[path].values()), suite)

    def test_the_general_model_marks_each_property_where_the_registry_says(
            self):
        marks = general_marks()
        self.assertEqual(set(self.reg["properties"]), set(marks))
        for pid, row in self.reg["properties"].items():
            self.assertEqual(marks[pid], row["general"], pid)

    def test_every_property_is_carried_by_a_seam_the_checker_can_break(self):
        # The seams are general.tla's constants. The search in
        # test_v4_general.py says which marks break with each
        # the other way, and the registry must say the same.
        model = _read(os.path.join(PROOFS, "general.tla"))
        declared = re.search(r"(?s)\nCONSTANTS (.*?)\n\n", model).group(1)
        constants = [name.strip() for name in declared.split(",")]
        self.assertEqual(constants, [seam[0] for seam in GENERAL.SEAMS])
        for pid, row in self.reg["properties"].items():
            carried = [name for name, _cfg, _inv, props in GENERAL.SEAMS
                       if pid in props]
            self.assertEqual(carried, row["seams"], pid)
            self.assertTrue(row["seams"], pid)
        for name, cfg, invariant, props in GENERAL.SEAMS:
            held = _read(os.path.join(PROOFS, cfg))
            self.assertIn("  %s = FALSE\n" % name, held)
            self.assertIn(invariant[:-3], props)


class FuzzTies(unittest.TestCase):
    """Constraint to fuzz data: the target, whether its tracer
    follows the file, and an entry that enters the function."""

    @classmethod
    def setUpClass(cls):
        cls.reg = registry()

    def test_every_tie_names_a_target_and_says_whether_it_traces_the_file(
            self):
        for row in self.reg["constraints"]:
            for tie in row["fuzz"]:
                where = "%s %s" % (row["id"], tie["target"])
                self.assertIn(tie["target"], DD.TARGETS, where)
                self.assertIn(tie["site"], row["code"], where)
                self.assertEqual(traces(tie["target"], tie["site"]),
                                 tie["traced"], where)
                self.assertGreater(tie["entries"], 0, where)
                self.assertLessEqual(
                    tie["entries"],
                    self.reg["fuzz"][tie["target"]]["entries"], where)

    def test_a_code_site_has_a_tie_or_is_named_as_bare(self):
        for row in self.reg["constraints"]:
            tied = {tie["site"] for tie in row["fuzz"]}
            self.assertEqual(set(row["code"]),
                             tied | set(row["unfuzzed"]), row["id"])
            self.assertFalse(tied & set(row["unfuzzed"]), row["id"])

    def test_each_bound_target_still_reaches_its_site(self):
        # 1 replay of the witness entry is the common case. Where
        # the witness has left the corpus, or no longer enters,
        # the target's whole corpus is asked before the tie fails.
        leave_no_trace(self)
        cache, lost = {}, []

        def reaches(target, site, witness):
            entries = corpus(target)
            first = [e for e in entries if e["id"] == witness]
            for entry in first + [e for e in entries if e["id"] != witness]:
                key = (target, entry["id"])
                if key not in cache:
                    cache[key] = entered(target, entry)
                if site in cache[key]:
                    return True
            return False

        def replay():
            for row in self.reg["constraints"]:
                for tie in row["fuzz"]:
                    if not reaches(tie["target"], tie["site"],
                                   tie["witness"]):
                        lost.append("%s: %s no longer enters %s" % (
                            row["id"], tie["target"], tie["site"]))

        DD._with_rig(replay)
        self.assertEqual([], lost)

    def test_the_campaign_s_log_has_only_grown_since_the_count(self):
        log = run_log()
        self.assertEqual(sorted(DD.TARGETS), list(self.reg["fuzz"]))
        for target, row in self.reg["fuzz"].items():
            self.assertGreaterEqual(log[target]["runs"], row["runs"], target)
            self.assertGreaterEqual(log[target]["tried"], row["tried"],
                                    target)

    def test_a_bound_target_is_one_a_tie_names(self):
        named = {tie["target"] for row in self.reg["constraints"]
                 for tie in row["fuzz"]}
        self.assertEqual(named, {target
                                 for target, row in self.reg["fuzz"].items()
                                 if row["bound"]})

    def test_every_bound_target_s_corpus_is_replayed_by_the_suite(self):
        # The contract of a target the registry leans on is held
        # on every suite run, entry by entry, by the replay class.
        replayed = methods_by_class_in(REPLAY)["CorpusReplayTest"]
        for target, row in self.reg["fuzz"].items():
            if row["bound"]:
                self.assertIn("test_" + target, replayed)

    def test_no_crash_stands_open_in_the_corpus(self):
        folder = os.path.join(ROOT, "runner", "tests", "de_dust")
        self.assertEqual([], [name for name in os.listdir(folder)
                              if name.endswith(".crashes.jsonl")])


class Sizes(unittest.TestCase):
    """Constraint to fuzz data, by size: how large the entries
    are that enter each constraint's code."""

    @classmethod
    def setUpClass(cls):
        cls.reg = registry()

    def test_a_size_is_the_campaign_s_own_count_of_an_entry(self):
        # The tool tries a child or drops it by a count of the
        # child's bytes. size_of is that count: the tool drops a
        # child exactly when its size here is past the tool's cap.
        def tried(kind, target, data):
            def grown(_rng, _data, _corpus):
                return data
            parent = {"kind": kind, "data": "" if kind == "text" else {}}
            with mock.patch.object(DD, "pick", return_value=grown):
                return DD.mutate(None, parent, [], target) is not None

        euro = "\u20ac"
        text = euro * (DD.MAX_TEXT // 3) + "a" * (DD.MAX_TEXT % 3)
        frame = len(json.dumps({"a": ""}, ensure_ascii=True))
        for kind, target, cap, at, past in (
                ("text", "wire", DD.MAX_TEXT, text, text + "a"),
                ("text", "wire", DD.MAX_TEXT,
                 "\ud800" * (DD.MAX_TEXT // 3) + "a" * (DD.MAX_TEXT % 3),
                 "\ud800" * (DD.MAX_TEXT // 3 + 1)),
                ("payload", "v2", DD.MAX_PAYLOAD,
                 {"a": "b" * (DD.MAX_PAYLOAD - frame)},
                 {"a": "b" * (DD.MAX_PAYLOAD - frame + 1)}),
                ("payload", "v2", DD.MAX_PAYLOAD,
                 {"a": euro * ((DD.MAX_PAYLOAD - frame) // 6)
                  + "b" * ((DD.MAX_PAYLOAD - frame) % 6)},
                 {"a": euro * ((DD.MAX_PAYLOAD - frame) // 6 + 1)})):
            where = "%s %d" % (kind, cap)
            self.assertEqual(cap, size_of({"kind": kind, "data": at}), where)
            self.assertGreater(size_of({"kind": kind, "data": past}), cap,
                               where)
            self.assertTrue(tried(kind, target, at), where)
            self.assertFalse(tried(kind, target, past), where)

    def test_every_tie_carries_the_sizes_of_the_entries_inside(self):
        for row in self.reg["constraints"]:
            for tie in row["fuzz"]:
                where = "%s %s %s" % (row["id"], tie["target"], tie["site"])
                whole = self.reg["fuzz"][tie["target"]]
                self.assertEqual(len(BANDS) + 1, len(tie["bands"]), where)
                self.assertEqual(tie["entries"], sum(tie["bands"]), where)
                self.assertLessEqual(tie["smallest"], tie["largest"], where)
                for end in (tie["smallest"], tie["largest"]):
                    self.assertGreater(tie["bands"][band_of(end)], 0, where)
                # No entry inside is outside its target's corpus.
                self.assertGreaterEqual(tie["smallest"], whole["smallest"],
                                        where)
                self.assertLessEqual(tie["largest"], whole["largest"], where)
                for count, most in zip(tie["bands"], whole["bands"]):
                    self.assertLessEqual(count, most, where)

    def test_every_target_carries_the_sizes_of_its_corpus(self):
        for target, row in self.reg["fuzz"].items():
            self.assertEqual(row["entries"], sum(row["bands"]), target)
            self.assertLessEqual(row["smallest"], row["largest"], target)
            for end in (row["smallest"], row["largest"]):
                self.assertGreater(row["bands"][band_of(end)], 0, target)

    def test_a_constraint_s_reach_is_its_ties_taken_together(self):
        for row in self.reg["constraints"]:
            reach, ties = row["reach"], row["fuzz"]
            if not ties:
                self.assertIsNone(reach, row["id"])
                continue
            self.assertEqual(reach["entries"], sum(reach["bands"]), row["id"])
            self.assertEqual(min(tie["smallest"] for tie in ties),
                             reach["smallest"], row["id"])
            self.assertEqual(max(tie["largest"] for tie in ties),
                             reach["largest"], row["id"])
            # An entry inside 2 of the constraint's functions is
            # counted once: band by band the reach is no less than
            # each target's fullest tie, and no more than every
            # tie added up.
            for band in range(len(BANDS) + 1):
                fullest = collections.Counter()
                for tie in ties:
                    fullest[tie["target"]] = max(fullest[tie["target"]],
                                                 tie["bands"][band])
                self.assertGreaterEqual(reach["bands"][band],
                                        sum(fullest.values()), row["id"])
                self.assertLessEqual(reach["bands"][band],
                                     sum(tie["bands"][band] for tie in ties),
                                     row["id"])

    def test_a_witness_still_in_the_corpus_is_of_a_size_its_tie_counts(self):
        held = {}
        for row in self.reg["constraints"]:
            for tie in row["fuzz"]:
                if tie["target"] not in held:
                    held[tie["target"]] = {entry["id"]: size_of(entry)
                                           for entry in corpus(tie["target"])}
                size = held[tie["target"]].get(tie["witness"])
                if size is not None:
                    self.assertTrue(
                        tie["smallest"] <= size <= tie["largest"],
                        "%s %s" % (row["id"], tie["target"]))
                    self.assertGreater(tie["bands"][band_of(size)], 0)

    def test_the_campaign_s_cap_on_a_child_is_under_every_size_cap(self):
        # C1 to C4 are caps on size. The tool tries no child past
        # its own cap, so while that cap is under all 4, no input
        # of the campaign is the size of 1 of them, and the page
        # says so.
        child = max(DD.MAX_TEXT, DD.MAX_PAYLOAD)
        caps = collections.OrderedDict([
            ("C1", PINS._mail_default("max_job_bytes")),
            ("C2", PINS._mail_default("max_script_bytes")),
            ("C3", RUNNER.MAX_RESULT_BYTES),
            ("C4", RUNNER._LOCAL_ENVELOPE_MAX_BYTES)])
        names = {row["id"]: row["name"] for row in self.reg["constraints"]}
        flat = " ".join(_read(PAGE_PATH).split())
        for cid, cap in caps.items():
            self.assertIn("bytes", names[cid].lower(), cid)
            self.assertLess(child, cap, cid)
            self.assertIn(_n(cap), flat, cid)
        self.assertIn("at most %s bytes" % _n(child), flat)
        self.assertLessEqual(totals(self.reg)["largest entry"],
                             min(caps.values()))
        # Of the 4, the page names the caps that have entries at
        # their code, and how large the largest of them is.
        reach = {row["id"]: row["reach"] for row in self.reg["constraints"]}
        self.assertEqual(["C4"], [cid for cid in caps if reach[cid]])
        self.assertIn("%s entries, and the largest of them is %s bytes" % (
            _n(reach["C4"]["entries"]), _n(reach["C4"]["largest"])), flat)

    def test_the_page_sizes_the_signature_s_reach_as_the_registry_does(self):
        # The page reads finding F10 against the largest entry
        # that reaches the signature's code.
        reach = {row["id"]: row["reach"] for row in self.reg["constraints"]}
        names = {row["id"]: row["name"] for row in self.reg["constraints"]}
        self.assertEqual("Signature", names["C5"])
        flat = " ".join(_read(PAGE_PATH).split())
        self.assertIn("The largest entry at the signature's code is %s bytes"
                      % _n(reach["C5"]["largest"]), flat)
        self.assertLess(reach["C5"]["largest"],
                        max(DD.MAX_TEXT, DD.MAX_PAYLOAD))


class Page(unittest.TestCase):
    """v4-bindings.md is the registry, and says what it counts."""

    @classmethod
    def setUpClass(cls):
        cls.reg = registry()
        cls.page = _read(PAGE_PATH)

    def test_the_page_carries_each_table_as_the_registry_renders_it(self):
        for name, render in RENDERS.items():
            self.assertIn(render(self.reg), self.page, name)

    def test_the_page_states_the_registry_s_counts(self):
        count = totals(self.reg)
        for words in (
                "%d constraints" % count["constraints"],
                "%d properties" % count["properties"],
                "%d code sites" % count["code sites"],
                "%d named pins" % count["pins"],
                "%d fuzz ties" % count["fuzz ties"],
                "%d of the %d constraints" % (
                    count["constraints with fuzz data"],
                    count["constraints"]),
                "%d constraints have none" % count["constraints with none"],
                "%d code sites that no corpus entry enters" %
                count["sites no entry enters"],
                "%d of the %d targets" % (count["bound targets"],
                                          count["targets"]),
                "%s grow runs" % _n(count["grow runs"]),
                "%s inputs" % _n(count["inputs tried"]),
                "%s of those inputs" % _n(
                    count["inputs tried by bound targets"]),
                "%s corpus entries" % _n(count["corpus entries"]),
                "%s are under 100 bytes" % _n(
                    count["entries under 100 bytes"]),
                "%s are of 100 to 999 bytes" % _n(
                    count["entries of 100 to 999 bytes"]),
                "%s are of 1,000 to 9,999 bytes" % _n(
                    count["entries of 1,000 to 9,999 bytes"]),
                "%s are of 10,000 bytes or more" % _n(
                    count["entries of 10,000 bytes and over"]),
                "The largest is %s bytes" % _n(count["largest entry"]),
                "%d of the %d constraints have entries to size" % (
                    count["constraints sized"], count["constraints"]),
                "counted on %s" % self.reg["counted"]):
            self.assertIn(words, " ".join(self.page.split()), words)

    def test_the_page_names_every_constraint_with_no_fuzz_data(self):
        bare = [row["id"] for row in self.reg["constraints"]
                if not row["fuzz"]]
        flat = " ".join(self.page.split())
        self.assertIn(", ".join(bare[:-1]) + " and " + bare[-1], flat)

    def test_the_shelf_s_index_names_the_page_and_the_registry(self):
        index = _read(os.path.join(PROOFS, "readme.md"))
        self.assertIn("v4-bindings.md", index)
        self.assertIn("v4-bindings.json", index)
        self.assertIn("test_v4_bindings.py", index)


# ---- the corpus at the mail gate

KEYS = {"shared_secret": DD.SECRET,
        "additional_secrets": dict(DD.LOCAL_CFG["additional_secrets"])}
STRANGER = "9f8e7d6c5b4a39281706f5e4d3c2b1a00a1b2c3d4e5f60718293a4b5c6d7e8f9"
_SAFE = "g-fuzz-1"


def _stamp(seconds=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_mail(job_id, body):
    """1 job mail. A body the mail library will not carry goes in
    as the octets a mailbox could still hand over."""
    subject = "[HOMING-PIGEON] job " + job_id
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = "si@example.com"
        msg.set_content(body)
        return msg.as_bytes()
    except (UnicodeError, ValueError):
        return (("Subject: %s\r\nFrom: si@example.com\r\n"
                 "MIME-Version: 1.0\r\n"
                 "Content-Type: text/plain; charset=utf-8\r\n"
                 "Content-Transfer-Encoding: 8bit\r\n\r\n" % subject
                 ).encode("ascii")
                + body.encode("utf-8", "surrogatepass"))


def _subject_id(value):
    return value if isinstance(value, str) \
        and RUNNER._SAFE_JOB_ID.match(value) else _SAFE


def _at_the_gate(raw, clear, folder, seen=None):
    RUNNER._set_allow_cleartext_jobs(clear)
    try:
        return DOOR._run(raw=raw, base_dir=folder, cfg_extra=KEYS, seen=seen)
    finally:
        RUNNER._set_allow_cleartext_jobs(False)


def _signed(payload):
    """The payload signed with the key it names, as the corpus tool
    signs it, or None where the signer refuses it."""
    secret, _ = DD._signing_secret(payload)
    try:
        return RUNNER.sign_payload(payload, secret or DD.SECRET)
    except ValueError:
        return None


def recorded_arrivals():
    """(target, entry id, raw mail) for the wire, crypto and mail
    corpora as they stand in the tree."""
    out = []
    for entry in corpus("wire"):
        data = entry["data"]
        if entry["kind"] == "text":
            text = data
            try:
                inside = json.loads(text)
            except ValueError:
                inside = None
            name = inside.get("job_id") if isinstance(inside, dict) else None
        elif isinstance(data, dict):
            text, name = _signed(data), data.get("job_id")
        else:
            text, name = json.dumps(data), None
        if text is not None:
            out.append(("wire", entry["id"],
                        _as_mail(_subject_id(name), text)))
    for entry in corpus("crypto"):
        spec = entry["data"]
        envelope = spec.get("envelope")
        text = _signed(envelope) if isinstance(envelope, dict) else None
        if text is None:
            try:
                text = json.dumps(envelope)
            except (TypeError, ValueError):
                continue
        out.append(("crypto", entry["id"],
                    _as_mail(_subject_id(spec.get("job_id")), text)))
    for entry in corpus("mail"):
        out.append(("mail", entry["id"],
                    entry["data"].encode("utf-8", "surrogateescape")))
    return out


def fresh_jobs():
    """The wire corpus's payloads, each given the present for its
    issued_at and signed with the key it names: (entry id,
    payload, subject id)."""
    out = []
    for entry in corpus("wire"):
        data = entry["data"]
        if entry["kind"] != "payload" or not isinstance(data, dict):
            continue
        payload = dict(data)
        if "issued_at" in payload:
            payload["issued_at"] = _stamp()
        out.append((entry["id"], payload, _subject_id(payload.get("job_id"))))
    return out


def clauses(payload, text, subject, secrets, clear, sealed):
    """P1's clauses for 1 arrival, read by this module off the
    payload and the bytes. The signature is this module's own
    HMAC, under the secret the runner's key map gives the key the
    payload names."""
    key_id = payload.get("key_id", "")
    try:
        secret = RUNNER.secret_named(secrets, key_id)
    except Exception:
        secret = None
    yield "the key is one the runner holds", isinstance(secret, str)
    yield "the signature verifies under that key", isinstance(secret, str) \
        and DD._sig_verdict(text, secret) in ("accept", "accept-cleaned")
    yield "the body is sealed, or cleartext is allowed", sealed or clear
    version = payload.get("v")
    yield "version 1 and type job", type(version) is int and version == 1 \
        and payload.get("type") == "job"
    yield "the body's id is the subject's", payload.get("job_id") == subject
    try:
        issued = datetime.strptime(payload.get("issued_at"),
                                   "%Y-%m-%dT%H:%M:%SZ")
        age = (datetime.now(timezone.utc).replace(tzinfo=None)
               - issued).total_seconds()
        fresh = -300 <= age <= 3600
    except (TypeError, ValueError):
        fresh = False
    yield "issued inside the window", fresh
    script = payload.get("script")
    yield "the script is within its cap", not isinstance(script, str) \
        or len(script.encode("utf-8", "surrogatepass")) <= 1048576
    yield "it is not an alert", payload.get("kind") != "sensor_alert"


class CorpusAtTheGate(unittest.TestCase):
    """P1 and P5 on fuzz data, at handle_mail itself."""

    @classmethod
    def setUpClass(cls):
        cls.jobs = fresh_jobs()
        cls.secrets = RUNNER.build_secrets(dict(KEYS))

    def test_no_recorded_entry_runs_and_the_gate_never_raises(self):
        arrivals = recorded_arrivals()
        by_target = collections.Counter(a[0] for a in arrivals)
        self.assertEqual({"wire", "crypto", "mail"}, set(by_target))
        self.assertGreaterEqual(len(arrivals), 200)
        for target, entry_id, raw in arrivals:
            for clear in (False, True):
                with tempfile.TemporaryDirectory() as folder:
                    first = _at_the_gate(raw, clear, folder)
                    again = _at_the_gate(raw, clear, folder, seen={})
                self.assertEqual([], first.executed, (target, entry_id))
                self.assertEqual([], again.executed, (target, entry_id))

    def test_a_fresh_job_runs_only_past_every_clause_and_only_once(self):
        ran = 0
        for entry_id, payload, subject in self.jobs:
            text = _signed(payload)
            if text is None:
                continue
            raw = _as_mail(subject, text)
            with tempfile.TemporaryDirectory() as folder:
                first = _at_the_gate(raw, True, folder)
                same_cache = _at_the_gate(raw, True, folder, seen=first.seen)
                no_cache = _at_the_gate(raw, True, folder, seen={})
            self.assertLessEqual(len(first.executed), 1, entry_id)
            self.assertEqual([], same_cache.executed, entry_id)
            self.assertEqual([], no_cache.executed, entry_id)
            if first.executed:
                ran += 1
                for clause, held in clauses(payload, text, subject,
                                            self.secrets, True, False):
                    self.assertTrue(held, "%s ran: %s" % (entry_id, clause))
        self.assertGreaterEqual(ran, 20)

    def test_with_cleartext_refused_no_unsealed_job_runs(self):
        for entry_id, payload, subject in self.jobs:
            text = _signed(payload)
            if text is None:
                continue
            with tempfile.TemporaryDirectory() as folder:
                out = _at_the_gate(_as_mail(subject, text), False, folder)
            self.assertEqual([], out.executed, entry_id)

    def test_a_sealed_fresh_job_runs_under_the_default_past_every_clause(
            self):
        ran = 0
        for entry_id, payload, subject in self.jobs:
            text = _signed(payload)
            secret, key_id = DD._signing_secret(payload)
            if text is None or secret is None:
                continue
            body = jobcrypto.encrypt_body(
                text, secret, job_id=subject, key_id=key_id,
                sign=RUNNER.sign_payload)
            with tempfile.TemporaryDirectory() as folder:
                first = _at_the_gate(_as_mail(subject, body), False, folder)
                again = _at_the_gate(_as_mail(subject, body), False, folder,
                                     seen={})
            self.assertEqual([], again.executed, entry_id)
            if first.executed:
                ran += 1
                for clause, held in clauses(payload, text, subject,
                                            self.secrets, False, True):
                    self.assertTrue(held, "%s ran: %s" % (entry_id, clause))
        self.assertGreaterEqual(ran, 20)

    def _runners(self):
        """The fresh jobs that do run in the clear."""
        out = []
        for entry_id, payload, subject in self.jobs:
            text = _signed(payload)
            if text is None:
                continue
            with tempfile.TemporaryDirectory() as folder:
                if _at_the_gate(_as_mail(subject, text), True,
                                folder).executed:
                    out.append((entry_id, payload, subject, text))
        self.assertGreaterEqual(len(out), 20)
        return out

    def test_a_job_that_runs_does_not_run_once_its_bytes_are_touched(self):
        for entry_id, payload, subject, text in self._runners():
            mark = text.rindex('"sig"')
            digit = text.index('"', text.index(":", mark) + 1) + 1
            turned = text[:digit] + ("0" if text[digit] != "0" else "1") \
                + text[digit + 1:]
            later = dict(payload)
            later["issued_at"] = _stamp(2)
            moved = RUNNER.sign_payload(later, DD.SECRET)
            moved = moved[:moved.rindex('"sig"')] + text[mark:]
            stranger = RUNNER.sign_payload(payload, STRANGER)
            for name, body in (("a signature with 1 digit turned", turned),
                               ("a body changed under its signature", moved),
                               ("a key the runner does not hold", stranger)):
                self.assertNotEqual(text, body, name)
                with tempfile.TemporaryDirectory() as folder:
                    out = _at_the_gate(_as_mail(subject, body), True, folder)
                self.assertEqual([], out.executed, (entry_id, name))

    def test_a_job_that_runs_does_not_run_outside_the_window(self):
        for entry_id, payload, subject, _text in self._runners():
            for seconds, runs in ((-3700, 0), (-3500, 1), (200, 1),
                                  (400, 0)):
                dated = dict(payload)
                dated["issued_at"] = _stamp(seconds)
                with tempfile.TemporaryDirectory() as folder:
                    out = _at_the_gate(
                        _as_mail(subject, _signed(dated)), True, folder)
                self.assertEqual(runs, len(out.executed),
                                 (entry_id, seconds))

    def test_a_job_sealed_under_a_strange_key_does_not_run(self):
        for entry_id, payload, subject, _text in self._runners():
            inner = RUNNER.sign_payload(payload, STRANGER)
            body = jobcrypto.encrypt_body(
                inner, STRANGER, job_id=subject, key_id="",
                sign=RUNNER.sign_payload)
            with tempfile.TemporaryDirectory() as folder:
                out = _at_the_gate(_as_mail(subject, body), False, folder)
            self.assertEqual([], out.executed, entry_id)


# ---- the corpus at the local door

class CorpusAtTheLocalDoor(unittest.TestCase):
    """P12, and finding F9 of v4-general.md, on fuzz data: the
    local door bounds what it reads and runs nothing."""

    def test_no_entry_of_the_local_corpus_runs_anything(self):
        leave_no_trace(self)
        entries = corpus("local")
        self.assertGreaterEqual(len(entries), 400)
        outcomes = collections.Counter()

        def replay():
            for entry in entries:
                try:
                    outcomes[DD.check("local", entry)] += 1
                except DD.Crash as crash:
                    self.fail("%s: %s" % (entry["id"], crash))

        with mock.patch.object(RUNNER, "execute_job") as executed:
            DD._with_rig(replay)
        executed.assert_not_called()
        # Both halves are in the corpus: alerts the door files and
        # envelopes it turns away.
        self.assertGreater(outcomes["accepted"], 0)
        self.assertGreater(outcomes["refused"], 0)

    def test_a_job_the_mail_gate_runs_does_not_run_at_the_local_door(self):
        ran_by_mail = 0
        for entry_id, payload, subject in fresh_jobs():
            payload = dict(payload, api_version=1)
            text = _signed(payload)
            if text is None:
                continue
            with tempfile.TemporaryDirectory() as folder:
                ran_by_mail += len(_at_the_gate(
                    _as_mail(subject, text), True, folder).executed)
            with tempfile.TemporaryDirectory() as folder:
                cfg = dict(KEYS, base_dir=folder)
                with mock.patch.object(RUNNER, "execute_job") as executed, \
                        mock.patch.object(RUNNER, "log",
                                          lambda *a, **k: None), \
                        mock.patch.object(RUNNER, "_maybe_wake_oracle",
                                          lambda *a, **k: False):
                    RUNNER._ingest_local_envelope(cfg, folder, text, "file")
                executed.assert_not_called()
                self.assertFalse(
                    os.path.exists(os.path.join(folder, "seen.json")),
                    entry_id)
        self.assertGreaterEqual(ran_by_mail, 20)

    def test_an_entry_grown_past_the_cap_is_refused_before_any_key_work(
            self):
        cap = RUNNER._LOCAL_ENVELOPE_MAX_BYTES
        self.assertEqual(262144, cap)
        seen = 0
        for entry in corpus("local"):
            if entry["kind"] != "text":
                continue
            try:
                size = len(entry["data"].encode("utf-8"))
            except UnicodeEncodeError:
                continue
            grown = entry["data"] + " " * (cap + 1 - size)
            self.assertEqual(cap + 1, len(grown.encode("utf-8")))
            with tempfile.TemporaryDirectory() as folder:
                cfg = dict(KEYS, base_dir=folder)
                with mock.patch.object(RUNNER, "build_secrets") as keys, \
                        mock.patch.object(RUNNER,
                                          "verify_body_keyed") as verify, \
                        mock.patch.object(RUNNER, "log",
                                          lambda *a, **k: None):
                    self.assertIsNone(RUNNER._ingest_local_envelope(
                        cfg, folder, grown, "file"))
                keys.assert_not_called()
                verify.assert_not_called()
            seen += 1
        self.assertGreaterEqual(seen, 300)


# ---- the corpus at the floor

class CorpusAtTheFloor(unittest.TestCase):
    """P13 on fuzz data: the start's check and the key map every
    poll builds are 1 floor, for the default key and for any
    other."""

    def test_the_start_and_the_key_map_refuse_the_same_secrets(self):
        refused = passed = 0
        for entry in corpus("secret"):
            secret = entry["data"]

            def raises(call, *args):
                try:
                    call(*args)
                except RuntimeError:
                    return True
                return False

            at_start = raises(SECURITY.validate_shared_secret, secret)
            as_default = raises(RUNNER.build_secrets,
                                {"shared_secret": secret})
            as_other = raises(RUNNER.build_secrets, {
                "shared_secret": DOOR.SECRET,
                "additional_secrets": {"fuzz": secret}})
            self.assertEqual({at_start}, {as_default, as_other}, entry["id"])
            refused += at_start
            passed += not at_start
        self.assertGreater(refused, 0)
        self.assertGreater(passed, 0)


# ---- corpus text through the result fitting

def _result(out, err):
    return {"v": 1, "type": "result", "job_id": "g-fit-1", "exit_code": 0,
            "stdout": out, "stderr": err, "timed_out": False}


def _cut(text, keep=4096):
    """The floor's cut by this module's hand: a stream's first and
    last 2,048 characters, with the fitting's marker between."""
    if len(text) <= keep:
        return text, 0
    gone = len(text) - keep
    return (text[:keep // 2]
            + "\n... [%d characters dropped to fit max_result_bytes] ...\n"
            % gone + text[-(keep // 2):]), gone


def fuzz_streams(limit=None):
    """{corpus: its entries as 1 stream}, for the corpora whose
    data is text a job could print. An entry a result cannot
    carry (an unpaired surrogate) is left out."""
    out = collections.OrderedDict()
    for target in ("cloud", "wire", "mail", "queries", "names", "local"):
        parts = []
        for entry in corpus(target):
            data = entry["data"]
            text = data if isinstance(data, str) \
                else json.dumps(data, ensure_ascii=False)
            if RUNNER._textutil._lone_surrogate(text):
                continue
            parts.append(text)
        stream = "\n".join(parts)
        out[target] = stream if limit is None else stream[:limit]
    return out


class CorpusThroughTheFitting(unittest.TestCase):
    """P11 on fuzz text: a body leaves within the cap, or at its
    floor and marked, and what is signed is what is sent."""

    @classmethod
    def setUpClass(cls):
        cls.secrets = RUNNER.build_secrets({"shared_secret": DOOR.SECRET})

    def _fit(self, out, err, seal, cap):
        result, body = RUNNER._fit_result_body(
            _result(out, err), DOOR.SECRET, seal, "g-fit-1", "", cap)
        sent, key_id = RUNNER.verify_body_keyed(body, self.secrets)
        if seal:
            sent, _ = RUNNER.verify_body_keyed(jobcrypto.decrypt_body(
                sent, DOOR.SECRET, "g-fit-1", key_id), self.secrets)
        self.assertEqual(result["stdout"], sent["stdout"])
        self.assertEqual(result["stderr"], sent["stderr"])
        self.assertEqual(result.get("result_truncated"),
                         sent.get("result_truncated"))
        return result, len(body.encode("utf-8"))

    def _floor(self, out, err, seal):
        """The floor's size, built here and not by the fitting."""
        floor = _result(out, err)
        floor["stdout"], gone_out = _cut(out)
        floor["stderr"], gone_err = _cut(err)
        floor["stdout_truncated"] = floor["stderr_truncated"] = True
        floor["result_truncated"] = {"reason": "max_result_bytes",
                                     "dropped": gone_out + gone_err}
        return len(RUNNER._outgoing_result_body(
            floor, DOOR.SECRET, seal, "g-fit-1", "").encode("utf-8"))

    def _hold(self, out, err, seal):
        whole = len(RUNNER._outgoing_result_body(
            _result(out, err), DOOR.SECRET, seal, "g-fit-1", ""
        ).encode("utf-8"))
        floor = self._floor(out, err, seal)
        shapes = collections.Counter()
        for cap in (whole, whole - 1, whole // 2, whole // 4, 9000, 1):
            result, left = self._fit(out, err, seal, cap)
            marked = "result_truncated" in result
            if left <= cap and not marked:
                self.assertEqual(out, result["stdout"])
                self.assertEqual(err, result["stderr"])
                shapes["as it was"] += 1
            elif left <= cap:
                self.assertGreater(result["result_truncated"]["dropped"], 0)
                shapes["cut to fit"] += 1
            else:
                # Over the cap: marked, and no larger than the
                # floor. The slack is the fitting's own markers.
                self.assertTrue(marked, (cap, left))
                self.assertLessEqual(left, floor + 256, (cap, left, floor))
                shapes["at the floor"] += 1
        return shapes

    def test_fuzz_text_as_the_streams_of_an_unsealed_result(self):
        streams = fuzz_streams(limit=30000)
        names = list(streams)
        shapes = collections.Counter()
        for place, name in enumerate(names):
            other = streams[names[(place + 2) % len(names)]][::-1]
            shapes.update(self._hold(streams[name], other, False))
        for shape in ("as it was", "cut to fit", "at the floor"):
            self.assertGreater(shapes[shape], 0, shape)

    def test_fuzz_text_as_the_streams_of_a_sealed_result(self):
        streams = fuzz_streams(limit=6000)
        shapes = collections.Counter()
        shapes.update(self._hold(streams["wire"], streams["names"], True))
        shapes.update(self._hold(streams["queries"], "", True))
        for shape in ("as it was", "cut to fit", "at the floor"):
            self.assertGreater(shapes[shape], 0, shape)

    def test_a_cap_of_0_leaves_fuzz_text_as_it_was(self):
        for name, stream in fuzz_streams(limit=8000).items():
            result, _ = self._fit(stream, stream[::-1], False, 0)
            self.assertEqual(stream, result["stdout"], name)
            self.assertNotIn("result_truncated", result, name)


def _steady(ties):
    """Ties as 2 counts can be compared. A race target interleaves
    threads, so the entries that enter a function, and the first
    of them, move from one count to the next: for those the tie
    is the target, the site and whether the file is traced."""
    return [tie if not _races(tie)
            else {key: tie[key] for key in ("site", "target", "traced")}
            for tie in ties]


def _races(tie):
    return tie["target"].startswith("race_")


def _main(argv):
    if argv[:1] == ["measure"]:
        reg = registry()
        ties, bare, targets, reach = measure()
        moved = []
        for row in reg["constraints"]:
            # A reach that a race target feeds moves with it.
            still = not any(_races(tie) for tie in ties[row["id"]])
            if _steady(row["fuzz"]) != _steady(ties[row["id"]]) \
                    or row["unfuzzed"] != bare[row["id"]] \
                    or (still and row.get("reach") != reach[row["id"]]):
                moved.append(row["id"])
            row["fuzz"], row["unfuzzed"] = ties[row["id"]], bare[row["id"]]
            row["reach"] = reach[row["id"]]
        if reg["fuzz"] != targets:
            moved.append("the targets' totals")
        reg["fuzz"] = targets
        print("moved since the registry's count: %s"
              % (", ".join(moved) or "nothing"))
        if "--write" in argv:
            reg["counted"] = datetime.now().strftime("%Y-%m-%d")
            with open(REGISTRY_PATH, "w", encoding="utf-8",
                      newline="\n") as fh:
                json.dump(reg, fh, indent=1)
                fh.write("\n")
            print("written: %s" % os.path.relpath(REGISTRY_PATH, ROOT))
        return 0
    if argv[:1] == ["page"]:
        reg = registry()
        for name, count in totals(reg).items():
            print("%s: %s" % (name, _n(count)))
        for name, render in RENDERS.items():
            print("\n[%s]\n%s" % (name, render(reg)))
        return 0
    unittest.main()
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
