"""The v4 binding's models, searched and held to the code.

FUTURE.md item 1, step C continued. diskguard.tla states P7 of
v4-properties.md: the disk guard gives up the runner's own
material in a fixed order, records what it did, and never stops
the runner. The model was written and not yet run with TLC. This
module does the 3 things that need no checker, on every run of
the suite:

  the search        the same model, written here apart from the
                    TLA+ file, searched to the fixed point: every
                    reachable state, the 3 invariants in each,
                    and the witnesses that show the model moves.
                    The counts are this module's prediction for
                    the TLC run, written down before that run.
  the conformance   the real guard_disk, on a real directory,
                    driven down every path its own re-measuring
                    allows, over every combination of the 4
                    material classes. The invariants are read
                    off what the pass did to the disk, not off a
                    second copy of the code.
  the findings      where the code and the model, or the code and
                    P7's own words, part ways, each held as a
                    test so it cannot fade. The record is
                    docs/infrastructure-documents/proofs/v4-search.md.

secretfloor.tla and probegate.tla, the models of P13 and P10 that
the working record named as small steps, are treated the same way
at the foot of this module: each searched, then held to the real
code, build_secrets over every standing of 3 keys and the
confinement gate over every start.

localgate.tla, the model of P12, follows them: searched, then
held to the real inbox scan and the real listener's read, on
every arrival at the real cap.

The finishing pass adds the last 2 models the continued
record names, in the same shape and treated the same way:
hybridselect.tla (P8, the DTLS group selection) and
resultfit.tla (P11, the result fitting before signing).
Finding F7, the fitting's floor, is held the way F1 to F6
are held. P9, the framing scope claim, is not a checker
claim: the last class pins it by reading the documents it
is a claim about. The record for these 2 is v4-search-2.md.
"""
import hashlib
import itertools
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from runner import runner as RUNNER  # noqa: E402,F401
from runner.guard import security as SECURITY  # noqa: E402
from runner.ops import remediation_ops as GATE  # noqa: E402
from runner.oracle import resources as RES  # noqa: E402
from runner.tests.test_dtls import SECRET as DTLS_SECRET  # noqa: E402
from runner.tests.test_dtls import _pump as dtls_pump  # noqa: E402
from runner.wire import dtlsproto as DTLS  # noqa: E402
from runner.wire import verify as VERIFY  # noqa: E402

PROOFS = os.path.join(ROOT, "docs", "infrastructure-documents", "proofs")
RECORD = os.path.join(PROOFS, "v4-search.md")
RECORD2 = os.path.join(PROOFS, "v4-search-2.md")

CLASSES = (1, 2, 3, 4)
OVER, UNDER = 0.95, 0.50
NOW = 1_800_000_000.0


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _flat(path):
    return " ".join(_read(path).split())


def _said(number):
    return format(number, ",")


# ---- The model: diskguard.tla, written apart from it

READINGS = ("over", "under", "failed")


def model_init():
    """Init: the first measurement any of 3 ways, any of the 16
    combinations of classes with material, nothing acted on. A
    state ends with `at`, the class whose turn it is: 0 before
    the first measurement is acted on, 5 past the last class."""
    for reading in READINGS:
        for bits in range(16):
            present = frozenset(c for c in CLASSES if bits >> (c - 1) & 1)
            yield (reading, present, (), "run", False, True, 0)


def model_next(state):
    """Next: Open, Act or Leave, each followed by the next
    measurement any of 3 ways; or End."""
    reading, present, acted, phase, recorded, alive, at = state
    if phase != "run":
        return
    if at == 0 and reading == "over":
        moved = acted                                          # Open
    elif at in CLASSES and at in present and reading == "over":
        moved = acted + (at,)                                  # Act
    elif at in CLASSES and reading != "failed":
        moved = acted                                          # Leave
    else:                                                      # End
        yield (reading, present, acted, "done", bool(acted), alive, at)
        return
    for again in READINGS:
        yield (again, present, moved, phase, recorded, alive, at + 1)


def never_stops(state):
    return state[5] is True


def order_respected(state):
    present, acted = state[1], state[2]
    return (all(c in present for c in acted)
            and all(a < b for a, b in zip(acted, acted[1:])))


def recorded_faithfully(state):
    acted, phase, recorded = state[2], state[3], state[4]
    return ((not (phase == "done" and acted) or recorded)
            and (not recorded or bool(acted)))


def never_leaves_material(state):
    """NeverLeavesMaterial, the third witness probe: no class is
    acted on with an earlier class's material left standing."""
    present, acted = state[1], state[2]
    return all(c in acted for a in acted for c in present if c < a)


INVARIANTS = (("NeverStops", never_stops),
              ("OrderRespected", order_respected),
              ("RecordedFaithfully", recorded_faithfully))


def search(initial, successors):
    """Every reachable state, each with the state it was first
    reached from, so a counterexample comes with its path."""
    came_from = {state: None for state in initial}
    frontier = list(came_from)
    steps = 0
    while frontier:
        state = frontier.pop()
        for following in successors(state):
            steps += 1
            if following not in came_from:
                came_from[following] = state
                frontier.append(following)
    return came_from, steps


def path_to(came_from, state):
    path = [state]
    while came_from[path[-1]] is not None:
        path.append(came_from[path[-1]])
    return path[::-1]


def first_breaking(came_from, holds):
    """A reachable state where `holds` is false, with its path;
    or None."""
    for state in sorted(came_from, key=repr):
        if not holds(state):
            return path_to(came_from, state)
    return None


class ModelSearch(unittest.TestCase):
    """diskguard.tla's Init and Next, searched to the fixed point."""

    @classmethod
    def setUpClass(cls):
        cls.initial = list(model_init())
        cls.reached, cls.steps = search(cls.initial, model_next)

    def test_the_3_invariants_hold_in_every_reachable_state(self):
        for name, holds in INVARIANTS:
            self.assertIsNone(first_breaking(self.reached, holds), name)

    def test_the_counts_are_the_prediction_for_the_checker(self):
        # 48 initial states: 3 readings by 16 combinations. At
        # the door of class k a pass stands in 1 way for a class
        # before k with no material and 2 for one with it, acted
        # on or left: 3 to the k - 1, by 2 for each class from k
        # on, by the 3 readings. A pass ends before the first
        # class on 2 readings, at a class on 1, and past the last
        # on all 3.
        self.assertEqual(48, len(self.initial))
        done = [s for s in self.reached if s[3] == "done"]
        self.assertEqual((1_086, 405), (len(self.reached), len(done)))
        doors = [3 * 3 ** (k - 1) * 2 ** (5 - k) for k in range(1, 6)]
        self.assertEqual([48, 72, 108, 162, 243], doors)
        self.assertEqual(len(self.reached) - len(done), 48 + sum(doors))
        self.assertEqual(len(done),
                         32 + sum(d // 3 for d in doors[:4]) + doors[4])
        text = _flat(RECORD)
        self.assertIn("48 initial states, %s distinct states, %s of them "
                      "finished passes" % (_said(len(self.reached)),
                                           _said(len(done))), text)

    def test_the_finished_passes_are_the_classes_in_order_any_left_out(self):
        # Over a combination of n classes a pass can end having
        # acted on any of them and left the others, in order:
        # 2 to the n finished passes.
        for bits in range(16):
            present = frozenset(c for c in CLASSES if bits >> (c - 1) & 1)
            ended = {s[2] for s in self.reached
                     if s[1] == present and s[3] == "done"}
            every = {tuple(c for c in sorted(present) if pick >> c & 1)
                     for pick in range(32)}
            self.assertEqual(every, ended, sorted(present))
            self.assertEqual(2 ** len(present), len(ended))

    def test_the_model_file_states_what_was_searched(self):
        text = _read(os.path.join(PROOFS, "diskguard.tla"))
        for stated in (
                "Readings == {\"over\", \"under\", \"failed\"}\n",
                "  /\\ reading \\in Readings\n"
                "  /\\ present \\in SUBSET Classes\n"
                "  /\\ acted = <<>>\n"
                "  /\\ at = 0\n",
                "  /\\ at \\in present\n"
                "  /\\ reading = \"over\"\n"
                "  /\\ acted' = Append(acted, at)\n"
                "  /\\ at' = at + 1\n"
                "  /\\ reading' \\in Readings\n",
                "  /\\ reading /= \"failed\"\n"
                "  /\\ (at \\notin present \\/ reading = \"under\")\n"
                "  /\\ at' = at + 1\n",
                "  /\\ \\/ at = 0 /\\ reading /= \"over\"\n"
                "     \\/ at \\in Classes /\\ reading = \"failed\"\n"
                "     \\/ at = 5\n"
                "  /\\ phase' = \"done\"\n"
                "  /\\ recorded' = (acted /= <<>>)\n",
                "NeverStops == alive = TRUE",
                "  /\\ \\A i, j \\in DOMAIN acted : i < j => "
                "acted[i] < acted[j]"):
            self.assertIn(stated, text, stated)
        self.assertEqual(
            "SPECIFICATION Spec\nINVARIANT NeverStops\n"
            "INVARIANT OrderRespected\nINVARIANT RecordedFaithfully\n",
            _read(os.path.join(PROOFS, "diskguard.cfg")))


class ModelWitnesses(unittest.TestCase):
    """A model in which the pass never acted would hold all 3
    invariants and show nothing. These are reached, and each
    probe a witness configuration names is false somewhere."""

    @classmethod
    def setUpClass(cls):
        cls.reached, _steps = search(list(model_init()), model_next)

    def test_a_pass_gives_up_all_4_classes_in_order_and_records_it(self):
        path = first_breaking(
            self.reached,
            lambda s: not (s[2] == (1, 2, 3, 4) and s[3] == "done"))
        self.assertIsNotNone(path)
        self.assertEqual(7, len(path))      # Init, Open, 4 actions, End
        self.assertTrue(path[-1][4])
        self.assertEqual([(), (), (1,), (1, 2), (1, 2, 3), (1, 2, 3, 4),
                          (1, 2, 3, 4)], [s[2] for s in path])
        self.assertEqual([0, 1, 2, 3, 4, 5, 5], [s[6] for s in path])

    def test_no_pass_opens_but_on_a_first_reading_of_over(self):
        for state in self.reached:
            if state[3] == "done" and state[6] == 0:
                self.assertIn(state[0], ("under", "failed"))
                self.assertEqual(((), False), (state[2], state[4]))

    def test_a_reading_that_fails_ends_the_pass_where_it_stands(self):
        # A pass ends at a class only on a failed reading, and
        # every action was taken on a reading of over: the state
        # an action leads from reads over.
        at_a_class = [s for s in self.reached
                      if s[3] == "done" and s[6] in CLASSES]
        self.assertEqual(130, len(at_a_class))
        self.assertEqual({"failed"}, {s[0] for s in at_a_class})
        for state in self.reached:
            for following in model_next(state):
                if following[2] != state[2]:
                    self.assertEqual("over", state[0])

    def test_a_pass_under_the_threshold_acts_on_nothing(self):
        for state in self.reached:
            if state[3] == "done" and not state[2]:
                self.assertFalse(state[4])

    def test_the_3_probes_are_false_somewhere_as_they_must_be(self):
        # NeverActs, NeverRecords and NeverLeavesMaterial, the 3
        # witness configurations: each expected to fail under the
        # checker. The third fails on a disk that fills up again:
        # the shortest such pass leaves class 1 at a reading of
        # under and acts on class 2 at a reading of over.
        self.assertIsNotNone(first_breaking(self.reached,
                                            lambda s: s[2] == ()))
        self.assertIsNotNone(first_breaking(self.reached,
                                            lambda s: s[4] is False))
        refill = first_breaking(self.reached, never_leaves_material)
        self.assertIsNotNone(refill)
        left = [s for s in self.reached
                if s[3] == "done" and s[2] == (2,) and 1 in s[1]]
        self.assertTrue(left)
        for name, probe in (
                ("diskguardwitnessacts.cfg", "NeverActs"),
                ("diskguardwitnessrecords.cfg", "NeverRecords"),
                ("diskguardwitnessrefill.cfg", "NeverLeavesMaterial")):
            held = _read(os.path.join(PROOFS, name))
            self.assertTrue(held.startswith("\\* Expected to fail."), name)
            self.assertTrue(held.endswith(
                "SPECIFICATION Spec\nINVARIANT %s\n" % probe), name)
        self.assertIn(
            "NeverLeavesMaterial ==\n"
            "  \\A i \\in DOMAIN acted : \\A c \\in present :\n"
            "    c < acted[i] => \\E j \\in DOMAIN acted : acted[j] = c\n",
            _read(os.path.join(PROOFS, "diskguard.tla")))


PROTECTED = ("config.json", "seen.json", "security-events.jsonl",
             os.path.join("outbox", "pending.txt"))


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def build_state(base, present, empty=False):
    """A runner state directory with material in the classes
    named, the protected files beside it, and 2 symlinks that
    lead outside it. `empty` makes the removable material 0
    bytes."""
    outside = base + "-outside"
    os.makedirs(outside)
    _write(os.path.join(outside, "keep.txt"), b"not the runner's\n")
    for name in PROTECTED:
        _write(os.path.join(base, name), b"protected " + name.encode())
    body = b"" if empty else b"history\n" * 40
    if 1 in present:
        _write(os.path.join(base, "runner.log.1"), body)
    if 2 in present:
        _write(os.path.join(base, "runner.log"), b"a log line\n" * 60)
    if 3 in present:
        _write(os.path.join(base, "sent", "old-result.txt"), body)
    if 4 in present:
        work = os.path.join(base, "work", "old-job")
        os.makedirs(work)
        if not empty:
            _write(os.path.join(work, "leftover.bin"), body)
        os.utime(work, (NOW - 7200, NOW - 7200))
    if hasattr(os, "symlink"):
        try:
            os.makedirs(os.path.join(base, "sent"), exist_ok=True)
            os.symlink(os.path.join(outside, "keep.txt"),
                       os.path.join(base, "sent", "link-out.txt"))
            os.symlink(os.path.join(outside, "keep.txt"),
                       os.path.join(base, "runner.log.9"))
        except OSError:
            pass
    return outside


def snapshot(top):
    """{relative path: bytes, or the link's target} under top."""
    seen = {}
    for folder, dirs, files in os.walk(top):
        for name in dirs + files:
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, top)
            if os.path.islink(path):
                seen[rel] = "-> " + os.readlink(path)
            elif os.path.isfile(path):
                with open(path, "rb") as fh:
                    seen[rel] = fh.read()
            else:
                seen[rel] = "dir"
    return seen


def class_of(rel):
    """Which of C28's 4 classes a path under the state directory
    belongs to, or 0 for anything else."""
    parts = rel.split(os.sep)
    if len(parts) == 1 and parts[0] in ("runner.log", "oracle.log",
                                        "oracle-chat.jsonl"):
        return 2
    if len(parts) == 1 and parts[0].startswith(
            ("runner.log.", "oracle.log.", "oracle-chat.jsonl.")):
        return 1
    if parts[0] in ("sent", "retained") or parts[:2] == ["outbox", "failed"]:
        return 3
    if parts[0] == "work":
        return 4
    return 0


class Pass:
    """One guard pass with the disk's readings scripted. A reading
    past the end of the script reads over, and is counted, so the
    caller can tell the script was too short."""

    def __init__(self, test, present, script, empty=False, cfg=None):
        self.script = tuple(script)
        self.readings = []
        self.trace = []                # ("read", value) and ("act", class)
        self.base = tempfile.mkdtemp(prefix="hp-v4-guard-")
        test.addCleanup(shutil.rmtree, self.base, True)
        test.addCleanup(shutil.rmtree, self.base + "-outside", True)
        self.outside = build_state(self.base, present, empty=empty)
        before = snapshot(self.base)
        outside_before = snapshot(self.outside)

        def fraction(_path):
            at = len(self.readings)
            value = self.script[at] if at < len(self.script) else OVER
            self.readings.append(value)
            self.trace.append(("read", value))
            return value

        def traced(real):
            def act(path, *rest):
                was = snapshot(self.base)
                freed = real(path, *rest)
                now = snapshot(self.base)
                if was != now:
                    rel = os.path.relpath(path, self.base)
                    self.trace.append(("act", class_of(rel)))
                return freed
            return act

        saved = {name: getattr(RES, name) for name in (
            "_disk_fraction", "_guard_remove_file", "_guard_truncate_log",
            "_guard_remove_tree", "DISK_GUARD_LOG_KEEP_BYTES")}
        RES._disk_fraction = fraction
        RES.DISK_GUARD_LOG_KEEP_BYTES = 64
        for name in ("_guard_remove_file", "_guard_truncate_log",
                     "_guard_remove_tree"):
            setattr(RES, name, traced(saved[name]))
        try:
            self.raised = None
            try:
                self.event = RES.guard_disk({} if cfg is None else cfg,
                                            self.base, now=NOW)
            except Exception as exc:        # P7 clause 1 says: never
                self.raised = exc
                self.event = None
        finally:
            for name, value in saved.items():
                setattr(RES, name, value)
        after = snapshot(self.base)
        self.outside_changed = snapshot(self.outside) != outside_before
        self.changed = sorted(
            rel for rel in set(before) | set(after)
            if before.get(rel) != after.get(rel) and rel != RES.STATE_FILE)
        # A removed folder shows as itself and all it held: the
        # roots are what the pass acted on.
        self.roots = [rel for rel in self.changed if not any(
            rel.startswith(other + os.sep) for other in self.changed)]
        self.acted = [c for kind, c in self.trace if kind == "act"]

    @property
    def classes(self):
        """The classes acted on, each once, in the order of their
        first action."""
        seen = []
        for c in self.acted:
            if c not in seen:
                seen.append(c)
        return tuple(seen)

    @property
    def steady(self):
        """No reading of under is followed by a reading of over
        with no action between: the disk did not fill up again on
        its own between 2 measurements."""
        under = False
        for kind, value in self.trace:
            if kind == "act":
                under = False
            elif value == UNDER:
                under = True
            elif under:
                return False
        return True


def every_path(test, present):
    """Every pass the guard's own re-measuring allows over this
    combination: scripts grown 1 reading at a time, each way,
    until the pass reads no further than its script."""
    finished, waiting = [], [()]
    while waiting:
        script = waiting.pop()
        run = Pass(test, present, script)
        if len(run.readings) > len(script):
            waiting.append(script + (OVER,))
            waiting.append(script + (UNDER,))
        else:
            finished.append(run)
    return finished


class Conformance(unittest.TestCase):
    """The real guard_disk, held to P7 on every path."""

    @classmethod
    def setUpClass(cls):
        holder = unittest.TestCase()
        cls.addClassCleanup(holder.doCleanups)
        cls.paths = {}
        for bits in range(16):
            present = frozenset(c for c in CLASSES if bits >> (c - 1) & 1)
            cls.paths[present] = every_path(holder, present)
        cls.every = [(present, run) for present, runs in cls.paths.items()
                     for run in runs]

    def test_the_paths_are_counted(self):
        steady = [run for _present, run in self.every if run.steady]
        self.assertEqual((1_516, 168), (len(self.every), len(steady)))
        text = _flat(RECORD)
        self.assertIn("%s passes in all, %s of them steady"
                      % (_said(len(self.every)), _said(len(steady))), text)

    def test_p7_1_no_pass_stops_the_runner(self):
        for present, run in self.every:
            self.assertIsNone(run.raised, (sorted(present), run.script))

    def test_p7_2_only_the_4_classes_in_their_order(self):
        for present, run in self.every:
            where = (sorted(present), run.script)
            self.assertNotIn(0, run.acted, where)
            self.assertEqual(sorted(run.acted), run.acted, where)
            self.assertLessEqual(set(run.acted), set(present), where)
            for rel in run.changed:
                self.assertIn(class_of(rel), present, (where, rel))

    def test_p7_2_every_action_follows_a_reading_of_over(self):
        for present, run in self.every:
            last = None
            for kind, value in run.trace:
                if kind == "read":
                    last = value
                else:
                    self.assertEqual(OVER, last,
                                     (sorted(present), run.script))

    def test_p7_3_nothing_protected_and_nothing_outside_is_touched(self):
        for present, run in self.every:
            where = (sorted(present), run.script)
            self.assertFalse(run.outside_changed, where)
            for rel in run.changed:
                self.assertNotIn(rel, PROTECTED, where)
                self.assertFalse(rel.endswith(("link-out.txt",
                                               "runner.log.9")), where)

    def test_p7_4_a_pass_is_recorded_exactly_when_it_acted(self):
        for present, run in self.every:
            where = (sorted(present), run.script)
            self.assertEqual(bool(run.changed), run.event is not None, where)
            if run.event is None:
                continue
            self.assertEqual("disk_truncation", run.event["type"], where)
            named = sorted(a["path"] for a in run.event["actions"])
            self.assertEqual(run.roots, named, where)
            self.assertGreater(run.event["freed_bytes"], 0, where)
            self.assertEqual(run.readings[-1] >= RES.DISK_GUARD_THRESHOLD,
                             run.event["still_over"], where)

    def test_on_every_disk_the_pass_is_one_of_the_model_s(self):
        # The model's finished passes over a combination are its
        # classes in order, any of them left out: a disk can read
        # under at one class and over again at the next. The
        # code's passes, on every path, are those and only those,
        # and it reaches them all.
        reached, _steps = search(list(model_init()), model_next)
        for present, runs in self.paths.items():
            model = {s[2] for s in reached
                     if s[1] == present and s[3] == "done"}
            code = {run.classes for run in runs}
            self.assertEqual(model, code, sorted(present))
            self.assertEqual(2 ** len(present), len(code))

    def test_on_a_steady_disk_a_pass_gives_up_its_classes_from_the_first(self):
        # On a disk that does not fill up again between 2
        # measurements, the passes are the prefixes of the
        # combination in order, all of them and no others.
        for present, runs in self.paths.items():
            prefixes = {tuple(sorted(present))[:n]
                        for n in range(len(present) + 1)}
            steady = {run.classes for run in runs if run.steady}
            self.assertEqual(prefixes, steady, sorted(present))

    def test_off_a_steady_disk_a_pass_can_leave_material_and_go_on(self):
        # F1, closed in the model: the passes that end with an
        # earlier class's material left standing and a later
        # class acted on. None of them is steady, each keeps
        # P7's order, and each is one of the model's.
        left = 0
        for present, runs in self.paths.items():
            prefixes = {tuple(sorted(present))[:n]
                        for n in range(len(present) + 1)}
            for run in runs:
                if run.classes not in prefixes:
                    self.assertFalse(run.steady)
                    self.assertEqual(sorted(run.acted), run.acted)
                    self.assertFalse(never_leaves_material(
                        ("over", present, run.classes, "done", True,
                         True, 5)))
                    left += 1
        self.assertEqual(412, left)
        self.assertIn("%s of them leave an earlier class's material "
                      "standing" % _said(left), _flat(RECORD))

    def test_a_reading_that_fails_ends_the_pass_at_every_point(self):
        # F3, closed in the code. Over each combination, the
        # pass that reads over all the way is cut short at each
        # of its readings in turn: the reading fails, nothing is
        # given up after it, and no reading is asked for but the
        # last one, which says how the pass left the disk.
        cut = 0
        for present, runs in self.paths.items():
            (whole,) = [run for run in runs if set(run.readings) == {OVER}]
            for at in range(1, len(whole.readings)):
                run = Pass(self, present,
                           (OVER,) * at + (None,) + (OVER,) * 20)
                where = (sorted(present), at)
                failed = run.trace.index(("read", None))
                self.assertNotIn("act", [kind for kind, _value
                                         in run.trace[failed:]], where)
                self.assertLessEqual(len(run.readings), at + 2, where)
                self.assertIsNone(run.raised, where)
                self.assertEqual(bool(run.changed), run.event is not None,
                                 where)
                if run.event is not None:
                    self.assertTrue(run.event["still_over"], where)
                cut += 1
        self.assertEqual(136, cut)
        self.assertIn("%s passes over the 16 combinations" % cut,
                      _flat(RECORD))

    def test_material_of_0_bytes_is_recorded_on_every_combination(self):
        # F2, closed in the code. The pass that reads over all
        # the way, over material of 0 bytes: the event names
        # exactly what the pass removed, whatever it freed.
        for bits in range(16):
            present = frozenset(c for c in CLASSES if bits >> (c - 1) & 1)
            run = Pass(self, present, (OVER,) * 20, empty=True)
            where = sorted(present)
            self.assertLess(len(run.readings), 20, where)
            self.assertEqual(bool(run.changed), run.event is not None, where)
            if run.event is None:
                self.assertEqual(frozenset(), present, where)
                continue
            self.assertEqual(
                run.roots, sorted(a["path"] for a in run.event["actions"]),
                where)
            self.assertEqual(present, frozenset(run.classes), where)
            self.assertEqual(2 not in present,
                             run.event["freed_bytes"] == 0, where)


class Findings(unittest.TestCase):
    """Where the code and the model, or the code and P7's words,
    parted ways when the model was first held to the guard. Each
    is closed, and each is held here as it stands now, so a
    change to either side shows up as a change to this class."""

    def test_f1_a_disk_that_refills_takes_the_pass_on_as_the_model_says(self):
        # Before any action, the code measures twice: once at the
        # head of a class's loop and once at the next class's
        # door. Under, then over, and the pass moves on to class
        # 2 with class 1's material still on the disk. The model
        # has that pass: it leaves class 1 at a reading of under
        # and acts on class 2 at a reading of over.
        run = Pass(self, frozenset(CLASSES),
                   (OVER, UNDER, OVER, OVER) + (UNDER,) * 4)
        self.assertEqual(len(run.script), len(run.readings))
        self.assertFalse(run.steady)
        self.assertEqual((2,), run.classes)
        self.assertIn("runner.log.1", snapshot(run.base))
        reached, _steps = search(list(model_init()), model_next)
        self.assertIn((2,), {s[2] for s in reached
                             if s[1] == frozenset(CLASSES)
                             and s[3] == "done"})
        self.assertIsNotNone(run.event)

    def test_f2_material_of_0_bytes_is_given_up_on_the_record(self):
        # P7 clause 4: every pass that acts leaves 1 event. A pass
        # that removes only 0 byte material acts, and its event
        # names each removal with the 0 bytes it freed.
        run = Pass(self, frozenset((1, 3, 4)), (OVER,) * 12, empty=True)
        self.assertEqual(["runner.log.1",
                          os.path.join("sent", "old-result.txt"),
                          os.path.join("work", "old-job")], run.roots)
        self.assertIsNone(run.raised)
        self.assertEqual("disk_truncation", run.event["type"])
        self.assertEqual(
            [("runner.log.1", "remove", 0),
             (os.path.join("sent", "old-result.txt"), "remove", 0),
             (os.path.join("work", "old-job"), "remove", 0)],
            [(a["path"], a["action"], a["bytes"])
             for a in run.event["actions"]])
        self.assertEqual(0, run.event["freed_bytes"])

    def test_f3_a_reading_that_fails_mid_pass_ends_the_pass(self):
        # The first reading failing means no pass. A later one
        # failing ends the pass: nothing is given up without a
        # measurement that says the disk is at or over the
        # threshold, and the event of a pass that had acted says
        # the disk may still be over.
        self.assertEqual([], Pass(self, frozenset(CLASSES), (None,)).changed)
        run = Pass(self, frozenset(CLASSES), (OVER,) + (None,) * 12)
        self.assertEqual(((), []), (run.classes, run.changed))
        self.assertIsNone(run.event)
        self.assertEqual([OVER, None, None], run.readings)
        run = Pass(self, frozenset(CLASSES), (OVER, OVER) + (None,) * 12)
        self.assertEqual((1,), run.classes)
        self.assertEqual(["runner.log.1"], run.roots)
        self.assertEqual([OVER, OVER, None, None], run.readings)
        self.assertTrue(run.event["still_over"])
        self.assertIsNone(run.event["disk_after"])

    def test_a_workspace_removed_part_way_is_on_the_record(self):
        # A removal that stops part way freed what it freed: the
        # workspace stands, smaller, and the event says so.
        present = frozenset((4,))
        plain = shutil.rmtree
        workspace = os.path.join("work", "old-job")

        def held_open(first):
            # rmtree, failing on the workspace alone: after its
            # 1 file when `first` is set, before anything when
            # it is not. Every other tree is removed as usual.
            def rmtree(path, *rest, **more):
                if not str(path).endswith(workspace):
                    return plain(path, *rest, **more)
                if first:
                    os.remove(os.path.join(path, "leftover.bin"))
                raise OSError("held open")
            return rmtree

        with mock.patch.object(shutil, "rmtree", held_open(True)):
            run = Pass(self, present, (OVER,) * 12)
        self.assertIs(plain, shutil.rmtree)
        self.assertIsNone(run.raised)
        self.assertEqual([os.path.join(workspace, "leftover.bin")],
                         run.changed)
        self.assertEqual(
            [(workspace, "remove", 320)],
            [(a["path"], a["action"], a["bytes"])
             for a in run.event["actions"]])
        with mock.patch.object(shutil, "rmtree", held_open(False)):
            run = Pass(self, present, (OVER,) * 12)
        self.assertEqual(([], None), (run.changed, run.event))

    def test_the_opt_out_is_a_pass_that_never_measures(self):
        # Not a gap: the model starts where the guard is enabled,
        # and this pins the edge it starts from.
        run = Pass(self, frozenset(CLASSES), (),
                   cfg={"no_90_disk_truncation": True})
        self.assertEqual(([], []), (run.readings, run.changed))
        self.assertIsNone(run.event)


# ---- The second model: secretfloor.tla, P13

KEYS = ("default", "extra1", "extra2")
STANDING = ("absent", "strong", "weak")


def floor_init():
    """Init: every standing of the default key and 2 additional
    keys, nothing decided."""
    for standing in itertools.product(STANDING, repeat=len(KEYS)):
        yield (standing, False, False, "none")


def causes(standing):
    """Causes: the keys that, each alone, cost the start."""
    found = {key for key, how in zip(KEYS, standing) if how == "weak"}
    if standing[0] == "absent":
        found.add("default")
    return found


def floor_next(state):
    """Decide: a start when nothing costs it, else a refusal that
    names one of its causes."""
    standing, decided, _started, _named = state
    if decided:
        return
    cost = causes(standing)
    if not cost:
        yield (standing, True, True, "none")
    for key in sorted(cost):
        yield (standing, True, False, key)


def p13_inv(state):
    standing, decided, started, _named = state
    return (not (decided and started)
            or (standing[0] == "strong" and "weak" not in standing))


def names_a_cause(state):
    standing, decided, started, named = state
    return not (decided and not started) or named in causes(standing)


class SecretFloorSearch(unittest.TestCase):
    """secretfloor.tla's Init and Next, searched to the fixed
    point."""

    @classmethod
    def setUpClass(cls):
        cls.initial = list(floor_init())
        cls.reached, _steps = search(cls.initial, floor_next)

    def test_the_2_invariants_hold_in_every_reachable_state(self):
        self.assertIsNone(first_breaking(self.reached, p13_inv))
        self.assertIsNone(first_breaking(self.reached, names_a_cause))

    def test_the_counts_are_the_prediction_for_the_checker(self):
        # 27 key maps. 4 of them start. Each of the other 23 is
        # refused once for every key that could be named.
        started = [s for s in self.reached if s[1] and s[2]]
        refused = [s for s in self.reached if s[1] and not s[2]]
        self.assertEqual((27, 4, 36), (len(self.initial), len(started),
                                       len(refused)))
        self.assertEqual(27 + 4 + 36, len(self.reached))
        self.assertIn("27 initial states, %d distinct states"
                      % len(self.reached), _flat(RECORD))

    def test_the_2_probes_are_false_somewhere_as_they_must_be(self):
        self.assertIsNotNone(first_breaking(
            self.reached, lambda s: not (s[1] and s[2])))
        self.assertIsNotNone(first_breaking(
            self.reached, lambda s: not (s[1] and not s[2])))
        text = _read(os.path.join(PROOFS, "secretfloor.tla"))
        for stated in (
                "Causes(m) ==\n  {k \\in Keys : m[k] = \"weak\"}\n"
                "    \\cup (IF m[\"default\"] = \"absent\" THEN "
                "{\"default\"} ELSE {})",
                "       THEN started' = TRUE /\\ named' = \"none\"\n"
                "       ELSE started' = FALSE /\\ named' \\in Causes(map)",
                "This file was run with TLC on 2026-11-18"):
            self.assertIn(stated, text, stated)
        self.assertTrue(_read(os.path.join(PROOFS, "secretfloor.cfg"))
                        .endswith("SPECIFICATION Spec\nINVARIANT P13Inv\n"
                                  "INVARIANT NamesACause\n"))
        for name, probe in (
                ("secretfloorwitnessstarts.cfg", "NothingStarts"),
                ("secretfloorwitnessrefused.cfg", "NothingIsRefused")):
            held = _read(os.path.join(PROOFS, name))
            self.assertTrue(held.startswith("\\* Expected to fail."), name)
            self.assertTrue(held.endswith(
                "SPECIFICATION Spec\nINVARIANT %s\n" % probe), name)


STRONG = {key: hashlib.sha384(("v4 floor " + key).encode()).hexdigest()
          for key in KEYS}
WEAK = {"default": "abcabcabcabc", "extra1": "a" * 40, "extra2": "q7T!x"}


def key_map_config(standing, forms, folder):
    """The configuration a standing of the 3 keys reads as, each
    present key given inline or from a file of its own."""
    cfg = {}
    for key, how, form in zip(KEYS, standing, forms):
        if how == "absent":
            continue
        value = STRONG[key] if how == "strong" else WEAK[key]
        path = os.path.join(folder, key + ".secret")
        if form == "file":
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(value)
            os.chmod(path, 0o600)
        if key == "default":
            cfg["shared_secret_file" if form == "file"
                else "shared_secret"] = path if form == "file" else value
        elif form == "file":
            cfg.setdefault("additional_secrets_files", {})[key] = path
        else:
            cfg.setdefault("additional_secrets", {})[key] = value
    return cfg


def named_key(said):
    """The key a refusal names and the setting it names it by."""
    for key in KEYS[1:]:
        for setting in ("additional_secrets", "additional_secrets_files"):
            if said.startswith("config error: %s[%r] is " % (setting, key)):
                return key, setting
    if said.startswith("config error: shared_secret is "):
        return "default", "shared_secret"
    return None, None


class SecretFloorConformance(unittest.TestCase):
    """The real build_secrets, on every standing of the 3 keys and
    every way of giving each present key."""

    @classmethod
    def setUpClass(cls):
        folder = tempfile.mkdtemp(prefix="hp-v4-floor-")
        cls.addClassCleanup(shutil.rmtree, folder, True)
        cls.runs = []
        for standing in itertools.product(STANDING, repeat=len(KEYS)):
            ways = [("-",) if how == "absent" else ("inline", "file")
                    for how in standing]
            for forms in itertools.product(*ways):
                cfg = key_map_config(standing, forms, folder)
                try:
                    built, said = VERIFY.build_secrets(cfg), None
                except RuntimeError as exc:
                    built, said = None, str(exc)
                cls.runs.append((standing, forms, built, said))

    def test_the_start_is_the_model_s_on_every_configuration(self):
        started = 0
        for standing, forms, built, said in self.runs:
            where = (standing, forms)
            self.assertEqual(not causes(standing), built is not None, where)
            if built is None:
                self.assertTrue(said.startswith("config error: "), where)
                continue
            started += 1
            # A key map that was built holds the default key under
            # its 2 names and each additional key under its own,
            # and nothing in it is under the floor.
            names = {key for key, how in zip(KEYS[1:], standing[1:])
                     if how != "absent"}
            self.assertEqual(names | {""}, {
                k for k in built if not k.startswith("k-")}, where)
            for secret in built.values():
                self.assertGreaterEqual(
                    SECURITY._estimate_secret_entropy(secret), 128, where)
        self.assertEqual((125, 18), (len(self.runs), started))
        self.assertIn("125 configurations, 18 of them start and 107 are "
                      "refused", _flat(RECORD))

    def test_a_refusal_names_a_key_that_cost_the_start(self):
        # F5, closed. NamesACause on the code: the refusal names
        # the setting of a key that cost the start. The default
        # key is named as shared_secret, and an additional key
        # by its own setting, the inline one or the file one,
        # whichever way it was given. P6 clause 4 asks that the
        # error name the setting.
        refused = [run for run in self.runs if run[2] is None]
        its_own = 0
        for standing, forms, _built, said in refused:
            where = (standing, forms, said)
            named, setting = named_key(said)
            self.assertIn(named, causes(standing), where)
            if "default" in causes(standing):
                self.assertEqual("default", named, where)
                continue
            its_own += 1
            self.assertEqual(
                "additional_secrets_files"
                if forms[KEYS.index(named)] == "file"
                else "additional_secrets", setting, where)
            self.assertRegex(said, r" is too weak \(", where)
        self.assertEqual((107, 32), (len(refused), its_own))
        self.assertIn("32 of the 107 refusals", _flat(RECORD))


# ---- The third model: probegate.tla, P10

MODES = ("enforce", "audit", "off")
PLATFORMS = ("darwin", "freebsd", "win32", "other")
BACKENDS = ("none", "stub", "noprobe", "real")
PROBES = ("passes", "problem", "raises")


def gated(start):
    """Gated: the starts where this gate decides."""
    mode, platform, _backend, _probe = start
    return mode == "enforce" and platform != "other"


def goes_ahead(start):
    """GoesAhead: the start goes ahead unless the gate names a
    problem."""
    _mode, _platform, backend, probe = start
    return not gated(start) or (backend == "real" and probe == "passes")


def gate_init():
    for start in itertools.product(MODES, PLATFORMS, BACKENDS, PROBES):
        yield (start, False, False)


def gate_next(state):
    start, decided, _started = state
    if not decided:
        yield (start, True, goes_ahead(start))


def p10_inv(state):
    start, decided, started = state
    return (not (decided and started and gated(start))
            or (start[2] == "real" and start[3] == "passes"))


def refuses_only_its_own(state):
    start, decided, started = state
    return not (decided and not started) or gated(start)


class ProbeGateSearch(unittest.TestCase):
    """probegate.tla's Init and Next, searched to the fixed
    point."""

    @classmethod
    def setUpClass(cls):
        cls.initial = list(gate_init())
        cls.reached, _steps = search(cls.initial, gate_next)

    def test_the_2_invariants_hold_in_every_reachable_state(self):
        self.assertIsNone(first_breaking(self.reached, p10_inv))
        self.assertIsNone(first_breaking(self.reached, refuses_only_its_own))

    def test_the_counts_are_the_prediction_for_the_checker(self):
        # 144 starts. 36 are at enforce on a platform with a
        # backend of its own; 3 of those go ahead, 1 a platform,
        # and 33 are refused.
        decided = [s for s in self.reached if s[1]]
        at_the_gate = [s for s in decided if gated(s[0])]
        refused = [s for s in decided if not s[2]]
        self.assertEqual((144, 288, 36, 33),
                         (len(self.initial), len(self.reached),
                          len(at_the_gate), len(refused)))
        self.assertEqual(
            {"darwin", "freebsd", "win32"},
            {s[0][1] for s in at_the_gate if s[2]})
        self.assertIn("144 initial states, 288 distinct states",
                      _flat(RECORD))

    def test_the_2_probes_are_false_somewhere_as_they_must_be(self):
        self.assertIsNotNone(first_breaking(
            self.reached, lambda s: not (s[1] and s[2] and gated(s[0]))))
        self.assertIsNotNone(first_breaking(
            self.reached, lambda s: not (s[1] and not s[2])))
        text = _read(os.path.join(PROOFS, "probegate.tla"))
        for stated in (
                "Gated(s) == s.mode = \"enforce\" /\\ s.platform /= "
                "\"other\"",
                "GoesAhead(s) ==\n  \\/ ~Gated(s)\n"
                "  \\/ s.backend = \"real\" /\\ s.probe = \"passes\"",
                "This file was run with TLC on 2026-11-18"):
            self.assertIn(stated, text, stated)
        self.assertTrue(_read(os.path.join(PROOFS, "probegate.cfg"))
                        .endswith("SPECIFICATION Spec\nINVARIANT P10Inv\n"
                                  "INVARIANT RefusesOnlyItsOwn\n"))
        for name, probe in (
                ("probegatewitnessstarts.cfg", "NothingStartsAtEnforce"),
                ("probegatewitnessrefused.cfg", "NothingIsRefused")):
            held = _read(os.path.join(PROOFS, name))
            self.assertTrue(held.startswith("\\* Expected to fail."), name)
            self.assertTrue(held.endswith(
                "SPECIFICATION Spec\nINVARIANT %s\n" % probe), name)


REAL_PLATFORM = {"darwin": "darwin", "freebsd": "freebsd14",
                 "win32": "win32", "other": "linux"}
FLAG = {"darwin": "IS_MACOS_BACKEND", "freebsd": "IS_FREEBSD_BACKEND",
        "win32": "IS_WINDOWS_BACKEND"}
PROBE_NAME = {"darwin": "macos_confinement_problem",
              "freebsd": "freebsd_confinement_problem",
              "win32": "windows_confinement_problem"}
RESOLVER = {"darwin": "_macos_confine", "freebsd": "_freebsd_confine",
            "win32": "_windows_confine"}


class _Backend:
    """What stands in a platform backend's place for 1 start."""

    def __init__(self, platform, backend, probe):
        self.asked = 0
        setattr(self, FLAG[platform], backend in ("noprobe", "real"))
        if backend != "real":
            return

        def answer(cfg, *rest):
            self.asked += 1
            if probe == "raises":
                raise OSError("the trial process could not be started")
            return None if probe == "passes" else "the trial was refused"
        setattr(self, PROBE_NAME[platform], answer)


def ask_the_gate(start):
    """The real gate's answer for 1 start: (the problem it names
    or None, how often the probe was asked)."""
    mode, platform, backend, probe = start
    cfg = {"security": {"modes": {"confinement": mode}}}
    if platform == "other":
        return GATE.confinement_startup_problem(
            cfg, platform=REAL_PLATFORM[platform]), 0
    if backend == "none":
        with mock.patch.object(GATE, RESOLVER[platform],
                               lambda backend=None: None):
            return GATE.confinement_startup_problem(
                cfg, platform=REAL_PLATFORM[platform]), 0
    stand_in = _Backend(platform, backend, probe)
    return GATE.confinement_startup_problem(
        cfg, platform=REAL_PLATFORM[platform], backend=stand_in), \
        stand_in.asked


class ProbeGateConformance(unittest.TestCase):
    """The real confinement_startup_problem on every start of the
    model."""

    def test_the_gate_s_answer_is_the_model_s_on_every_start(self):
        refused = 0
        for start in itertools.product(MODES, PLATFORMS, BACKENDS, PROBES):
            problem, asked = ask_the_gate(start)
            self.assertEqual(goes_ahead(start), problem is None, start)
            # The probe is asked only where the gate decides, and
            # there exactly once.
            self.assertEqual(
                1 if gated(start) and start[2] == "real" else 0, asked,
                start)
            if problem is None:
                continue
            refused += 1
            # A refusal names the platform, and carries the
            # probe's own words when the probe spoke.
            self.assertIn(start[1], problem, start)
            if start[2] == "real" and start[3] == "problem":
                self.assertEqual("confinement cannot engage on %s: the "
                                 "trial was refused" % start[1], problem)
            if start[2] == "real" and start[3] == "raises":
                self.assertIn("could not be started", problem, start)
        self.assertEqual(33, refused)
        self.assertIn("144 starts, 33 of them refused", _flat(RECORD))

    def test_a_model_that_is_wrong_either_way_is_caught(self):
        # The comparison above bites in both directions: a model
        # that lets a raising probe through, and a model that
        # gates a mode below enforce, each disagree with the gate
        # on a start that can be named.
        def differs(model):
            return [start for start in itertools.product(
                MODES, PLATFORMS, BACKENDS, PROBES)
                if model(start) != (ask_the_gate(start)[0] is None)]
        self.assertEqual([], differs(goes_ahead))
        lenient = differs(lambda start: goes_ahead(start) or (
            start[2] == "real" and start[3] == "raises"))
        self.assertEqual(
            [("enforce", platform, "real", "raises")
             for platform in ("darwin", "freebsd", "win32")], lenient)
        strict = differs(lambda start: goes_ahead(start) and not (
            start[0] == "audit" and start[1] != "other"))
        self.assertEqual(36, len(strict))
        self.assertEqual({"audit"}, {start[0] for start in strict})

    def test_the_startup_refuses_where_the_gate_names_a_problem(self):
        # The gate's caller: at enforce, on each of the 3
        # platforms, the startup asks this gate and a problem is
        # exit 2 with the reason.
        text = _read(os.path.join(ROOT, "runner", "ops", "main.py"))
        self.assertEqual(3, text.count(
            "problem = R._confinement_startup_problem(cfg)"))
        self.assertIn(
            '            if problem:\n'
            '                print("config error: security.modes.confinement '
            'is "\n'
            '                      "enforce but the sandbox cannot engage: "\n'
            '                      + problem + ". Refusing to start; fix the "\n'
            '                      "sandbox, or set confinement to audit or '
            'off.",\n'
            '                      file=sys.stderr)\n'
            '                return 2\n', text)
        self.assertIs(GATE.confinement_startup_problem,
                      RUNNER._confinement_startup_problem)


# ---- The fourth model: localgate.tla, P12

CAP, CHUNK = 2, 2
FORMS = ("file", "symlink", "directory", "stream")
CUTS = ("clean", "splits")


def local_reads(arrival, cap=CAP, chunk=CHUNK):
    """Reads: what a door may read of an arrival."""
    form, size, _decodes, _cut = arrival
    if form == "file":
        return range(min(size, cap + 1), min(size, cap + 1) + 1)
    if form == "stream" and size > cap:
        return range(cap + 1, min(size, cap + chunk) + 1)
    return range(size, size + 1) if form == "stream" else range(1)


def garbled(arrival, read):
    """Garbled: the bytes read do not decode."""
    return read > 0 and not arrival[2]


def local_outcome(arrival, read, cap=CAP):
    """Outcome: what the gate does with what it read. Each door
    looks at the size of what it read before it decodes
    anything."""
    form = arrival[0]
    if form == "directory":
        return "left"
    if form == "symlink":
        return "symlink"
    if read > cap:
        return "too large"
    if read == 0:
        return "empty" if form == "file" else "nothing"
    return "not utf-8" if garbled(arrival, read) else "verify"


def local_init():
    for arrival in itertools.product(FORMS, range(CAP + CHUNK + 2),
                                     (True, False), CUTS):
        yield (arrival, False, "none", 0)


def local_next(state):
    arrival, decided, _outcome, _read = state
    if not decided:
        for read in local_reads(arrival):
            yield (arrival, True, local_outcome(arrival, read), read)


def p12_inv(state):
    arrival, decided, outcome, read = state
    return (not (decided and outcome == "verify")
            or (arrival[1] <= CAP and read == arrival[1]))


def symlink_unread(state):
    arrival, _decided, _outcome, read = state
    return arrival[0] != "symlink" or read == 0


def read_bounded(state):
    arrival, _decided, _outcome, read = state
    return read <= {"file": CAP + 1, "stream": CAP + CHUNK}.get(arrival[0], 0)


def over_cap_refused_for_size(state):
    arrival, decided, outcome, _read = state
    return (not (decided and arrival[1] > CAP
                 and arrival[0] in ("file", "stream"))
            or outcome == "too large")


LOCAL_INVARIANTS = (("P12Inv", p12_inv), ("SymlinkUnread", symlink_unread),
                    ("ReadBounded", read_bounded),
                    ("OverCapRefusedForSize", over_cap_refused_for_size))


def tally(outcomes):
    counted = {}
    for outcome in outcomes:
        counted[outcome] = counted.get(outcome, 0) + 1
    return counted


class LocalGateSearch(unittest.TestCase):
    """localgate.tla's Init and Next, searched to the fixed
    point."""

    @classmethod
    def setUpClass(cls):
        cls.initial = list(local_init())
        cls.reached, _steps = search(cls.initial, local_next)
        cls.decided = [s for s in cls.reached if s[1]]

    def test_the_4_invariants_hold_in_every_reachable_state(self):
        for name, holds in LOCAL_INVARIANTS:
            self.assertIsNone(first_breaking(self.reached, holds), name)

    def test_the_counts_are_the_prediction_for_the_checker(self):
        # 96 arrivals. A stream over the cap by 2 or more can
        # stop on 2 totals, so 8 arrivals decide 2 ways and the
        # other 88 decide 1 way: 104 decisions.
        self.assertEqual((96, 200, 104), (len(self.initial),
                                          len(self.reached),
                                          len(self.decided)))
        self.assertEqual(
            {"verify": 8, "too large": 32, "not utf-8": 8, "empty": 4,
             "nothing": 4, "symlink": 24, "left": 24},
            tally(s[2] for s in self.decided))
        self.assertEqual(
            {"file": 4, "stream": 4},
            tally(s[0][0] for s in self.decided if s[2] == "verify"))
        self.assertIn("96 initial states, 200 distinct states",
                      _flat(RECORD))

    def test_the_2_probes_are_false_somewhere_as_they_must_be(self):
        self.assertIsNotNone(first_breaking(
            self.reached, lambda s: not (s[1] and s[2] == "verify")))
        self.assertIsNotNone(first_breaking(
            self.reached, lambda s: not (s[1] and s[2] == "too large")))
        text = _read(os.path.join(PROOFS, "localgate.tla"))
        for stated in (
                "Cap == 2\nChunk == 2\n",
                "Reads(a) ==\n"
                "  IF a.form = \"file\" THEN {Min(a.size, Cap + 1)}\n"
                "  ELSE IF a.form = \"stream\" /\\ a.size > Cap\n"
                "    THEN (Cap + 1)..Min(a.size, Cap + Chunk)\n"
                "  ELSE IF a.form = \"stream\" THEN {a.size}\n"
                "  ELSE {0}\n",
                "Garbled(a, r) == r > 0 /\\ ~a.decodes\n",
                "  ELSE IF r > Cap THEN \"too large\"\n"
                "  ELSE IF r = 0 THEN\n"
                "    (IF a.form = \"file\" THEN \"empty\" ELSE "
                "\"nothing\")\n"
                "  ELSE IF Garbled(a, r) THEN \"not utf-8\"\n"
                "  ELSE \"verify\"\n",
                "This file was run with TLC on 2026-11-18"):
            self.assertIn(stated, text, stated)
        self.assertTrue(_read(os.path.join(PROOFS, "localgate.cfg"))
                        .endswith("SPECIFICATION Spec\nINVARIANT P12Inv\n"
                                  "INVARIANT SymlinkUnread\n"
                                  "INVARIANT ReadBounded\n"
                                  "INVARIANT OverCapRefusedForSize\n"))
        for name, probe in (
                ("localgatewitnessverifies.cfg", "NothingReachesTheVerifier"),
                ("localgatewitnesssize.cfg", "NothingIsRefusedForSize")):
            held = _read(os.path.join(PROOFS, name))
            self.assertTrue(held.startswith("\\* Expected to fail."), name)
            self.assertTrue(held.endswith(
                "SPECIFICATION Spec\nINVARIANT %s\n" % probe), name)

    def test_where_the_cut_falls_changes_nothing_in_the_model(self):
        # F6, closed. The cut is in the arrival and nothing the
        # gate does depends on it: 2 arrivals that differ only
        # in the cut decide the same way, read for read.
        def decisions(cut):
            return sorted((s[0][:3], s[2], s[3]) for s in self.decided
                          if s[0][3] == cut)
        self.assertEqual(decisions("clean"), decisions("splits"))
        self.assertEqual(52, len(decisions("splits")))
        over = [s for s in self.decided
                if s[0][0] == "file" and s[0][1] > CAP]
        self.assertEqual({"too large": 12}, tally(s[2] for s in over))


# ---- The real doors, asked at the real cap

REAL_CAP = RUNNER._LOCAL_ENVELOPE_MAX_BYTES
REAL_CHUNK = 65536
REAL_SIZES = (0, 1000, REAL_CAP, REAL_CAP + 1, REAL_CAP + 2,
              REAL_CAP + REAL_CHUNK, REAL_CAP + REAL_CHUNK + 1)
CHUNKINGS = (REAL_CHUNK, 1000)
SAID = (("symlink refused", "symlink"),
        ("envelope too large", "too large"),
        ("envelope is not UTF-8", "not utf-8"),
        ("rejected: empty envelope", "empty"))


class _Held(Exception):
    """The stand-in verifier's answer: the envelope got here."""


class _Counted:
    """A file the scan opened, counting what is read of it."""

    def __init__(self, handle, counts):
        self.handle, self.counts = handle, counts

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.handle.close()
        return False

    def read(self, size=-1):
        data = self.handle.read(size)
        self.counts.append(len(data))
        return data


class _Stream:
    """A connection that hands its bytes out a chunk at a time
    and counts what it handed out."""

    def __init__(self, data, chunk):
        self.data, self.chunk, self.handed = data, chunk, 0

    def settimeout(self, _seconds):
        pass

    def recv(self, size):
        data = self.data[self.handed:self.handed + min(size, self.chunk)]
        self.handed += len(data)
        return data


def real_bytes(arrival):
    """The bytes of a real arrival: plain where it decodes, a
    byte no UTF-8 text begins with where it does not, and a
    2 byte character astride the scan's cut where the cut
    splits."""
    _form, size, decodes, cut = arrival
    if size == 0:
        return b""
    if not decodes:
        return b"\xff" + b"a" * (size - 1)
    if cut == "splits" and size > REAL_CAP + 1:
        return (b"a" * REAL_CAP + "é".encode("utf-8")
                + b"a" * (size - REAL_CAP - 2))
    return b"a" * size


class Asked:
    """One real arrival at its real door: what the gate did, in
    the model's words, and what the tests read off it."""

    def __init__(self, arrival, chunk=REAL_CHUNK, cap=REAL_CAP):
        form = arrival[0]
        self.arrival, self.data = arrival, real_bytes(arrival)
        self.said, self.reached, self.opened, counts = [], [], [], []
        base = tempfile.mkdtemp(prefix="v4-localgate-")
        inbox = os.path.join(base, RUNNER.LOCAL_INBOX_DIRNAME)
        path = os.path.join(inbox, "arrival.json")
        target = os.path.join(base, "elsewhere", "target")
        plain_open = open

        def counting_open(name, *args, **kwargs):
            if isinstance(name, str) and os.path.dirname(name) == inbox:
                self.opened.append(name)
                return _Counted(plain_open(name, *args, **kwargs), counts)
            return plain_open(name, *args, **kwargs)

        def verifier(text, _secrets):
            self.reached.append(text)
            raise _Held("held at the verifier")

        try:
            os.makedirs(inbox)
            if form == "file":
                _write(path, self.data)
            elif form == "symlink":
                _write(target, self.data)
                os.symlink(target, path)
            elif form == "directory":
                os.makedirs(path)
            stream = _Stream(self.data, chunk)
            config = {"shared_secret": STRONG["default"]}
            with mock.patch.object(
                    RUNNER, "log",
                    side_effect=lambda line, level="INFO":
                    self.said.append((level, line))), \
                    mock.patch.object(RUNNER, "vlog"), \
                    mock.patch.object(RUNNER, "verify_body_keyed",
                                      side_effect=verifier), \
                    mock.patch.object(RUNNER, "open", counting_open,
                                      create=True), \
                    mock.patch.object(RUNNER, "_LOCAL_ENVELOPE_MAX_BYTES",
                                      cap):
                if form == "stream":
                    self.handled = None
                    RUNNER._handle_local_signal_conn(config, base, stream)
                else:
                    self.handled = RUNNER._scan_local_inbox(config, base)
            self.read = stream.handed if form == "stream" else sum(counts)
            self.still_there = os.path.lexists(path)
            self.target_kept = (form != "symlink"
                                or _read_bytes(target) == self.data)
        finally:
            shutil.rmtree(base, ignore_errors=True)
        self.outcome = self._outcome()

    def _outcome(self):
        if self.reached:
            return "verify"
        for words, outcome in SAID:
            if any(words in line for _level, line in self.said):
                return outcome
        if self.arrival[0] == "directory":
            return "left"
        return "nothing"


def _read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def can_symlink():
    probe = tempfile.mkdtemp(prefix="v4-localgate-")
    try:
        os.symlink(probe, os.path.join(probe, "link"))
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False
    finally:
        shutil.rmtree(probe, ignore_errors=True)


class LocalGateConformance(unittest.TestCase):
    """The real inbox scan and the real listener's read, asked
    on every arrival at the real cap, against the model."""

    @classmethod
    def setUpClass(cls):
        cls.symlinks = can_symlink()
        cls.asked = {}
        for arrival in itertools.product(FORMS, REAL_SIZES,
                                         (True, False), CUTS):
            if arrival[0] == "symlink" and not cls.symlinks:
                continue
            for chunk in (CHUNKINGS if arrival[0] == "stream"
                          else (REAL_CHUNK,)):
                cls.asked[arrival, chunk] = Asked(arrival, chunk)

    def of(self, *forms):
        return [asked for (arrival, _chunk), asked in sorted(
            self.asked.items()) if arrival[0] in forms]

    def agrees(self, arrival, asked):
        return (asked.read in local_reads(arrival, REAL_CAP, REAL_CHUNK)
                and asked.outcome == local_outcome(arrival, asked.read,
                                                   REAL_CAP))

    def test_the_gate_is_the_model_on_every_arrival(self):
        for (arrival, chunk), asked in sorted(self.asked.items()):
            self.assertTrue(self.agrees(arrival, asked),
                            (arrival, chunk, asked.read, asked.said))
        # 28 files and 28 directories at the scan, and 28
        # streams at the listener, each in 2 chunkings.
        self.assertEqual((28, 28, 56), (len(self.of("file")),
                                        len(self.of("directory")),
                                        len(self.of("stream"))))
        self.assertEqual(
            {"verify": 4, "too large": 16, "not utf-8": 4, "empty": 4},
            tally(asked.outcome for asked in self.of("file")))
        self.assertEqual(
            {"verify": 8, "too large": 32, "not utf-8": 8, "nothing": 8},
            tally(asked.outcome for asked in self.of("stream")))
        self.assertEqual(140 if self.symlinks else 112, len(self.asked))
        self.assertIn("112 arrivals, 140 runs", _flat(RECORD))
        self.assertEqual(262144, REAL_CAP)
        self.assertEqual(1, _read(os.path.join(
            ROOT, "runner", "runner.py")).count(
                "            data = conn.recv(%d)\n" % REAL_CHUNK))

    def test_nothing_over_the_cap_reaches_the_verifier(self):
        # P12 on the code. What reaches the verifier is at most
        # the cap, and it is the whole envelope.
        over = [asked for asked in self.of("file", "stream")
                if asked.arrival[1] > REAL_CAP]
        self.assertEqual(48, len(over))
        for asked in over:
            self.assertEqual([], asked.reached, asked.arrival)
        through = [asked for asked in self.asked.values() if asked.reached]
        self.assertEqual(12, len(through))
        for asked in through:
            self.assertEqual([asked.data],
                             [text.encode("utf-8") for text in asked.reached])
            self.assertLessEqual(len(asked.data), REAL_CAP)
        # The cap itself is let through, and 1 byte more is not.
        at_the_cap = {asked.arrival[1] for asked in through}
        self.assertEqual({1000, REAL_CAP}, at_the_cap)

    def test_the_read_is_bounded_at_both_doors(self):
        for asked in self.of("file"):
            self.assertEqual(1, len(asked.opened), asked.arrival)
            self.assertEqual(min(asked.arrival[1], REAL_CAP + 1), asked.read)
        for asked in self.of("directory"):
            self.assertEqual(([], 0), (asked.opened, asked.read))
        reads = [asked.read for asked in self.of("stream")]
        self.assertEqual(REAL_CAP + REAL_CHUNK, max(reads))
        self.assertEqual(327680, max(reads))

    def test_a_symlink_is_refused_unread(self):
        if not self.symlinks:
            self.skipTest("symlinks unavailable")
        links = self.of("symlink")
        self.assertEqual(28, len(links))
        for asked in links:
            self.assertEqual("symlink", asked.outcome, asked.arrival)
            self.assertEqual(([], 0, []), (asked.opened, asked.read,
                                           asked.reached))
            self.assertTrue(asked.target_kept, asked.arrival)
            self.assertFalse(asked.still_there, asked.arrival)
            self.assertEqual(
                [("WARN", "local signal (file): arrival.json: "
                          "symlink refused")], asked.said)

    def test_every_refusal_over_the_cap_is_recorded_as_its_size(self):
        # OverCapRefusedForSize on the code: 1 line at WARN,
        # naming the door and the size, whatever the bytes are
        # and wherever the scan's cut falls.
        said = {
            "file": "local signal (file): arrival.json: envelope too "
                    "large; dropped",
            "stream": "local signal (socket): envelope too large; dropped"}
        over = [asked for asked in self.of("file", "stream")
                if asked.arrival[1] > REAL_CAP]
        self.assertEqual(48, len(over))
        for asked in over:
            self.assertEqual("too large", asked.outcome, asked.arrival)
            self.assertEqual([("WARN", said[asked.arrival[0]])], asked.said)

    def test_the_scan_removes_a_file_and_leaves_a_directory(self):
        for asked in self.of("file"):
            self.assertEqual((1, False), (asked.handled, asked.still_there))
        for asked in self.of("directory"):
            self.assertEqual((0, True, []), (asked.handled,
                                             asked.still_there, asked.said))

    def test_a_file_cut_inside_a_character_is_refused_for_its_size(self):
        # F6, closed. A file over the cap that is UTF-8 when
        # read whole, with a 2 byte character astride the
        # scan's cut at 1 byte past the cap. What was read does
        # not decode, and the scan does not ask: it looks at
        # the size first. The file is refused as too large, as
        # the same bytes are at the listener.
        astride = [asked for asked in self.of("file")
                   if asked.arrival[1] > REAL_CAP + 1 and asked.arrival[2]
                   and asked.arrival[3] == "splits"]
        self.assertEqual(3, len(astride))
        self.assertIn("3 files with a character astride the cut",
                      _flat(RECORD))
        for asked in astride:
            self.assertEqual(len(asked.data),
                             len(asked.data.decode("utf-8").encode("utf-8")))
            with self.assertRaises(UnicodeDecodeError):
                asked.data[:REAL_CAP + 1].decode("utf-8")
            self.assertEqual("too large", asked.outcome)
            for chunk in CHUNKINGS:
                same_bytes = self.asked[("stream",) + asked.arrival[1:],
                                        chunk]
                self.assertEqual(asked.data, same_bytes.data)
                self.assertEqual("too large", same_bytes.outcome)

    def test_a_gate_with_its_cap_1_byte_higher_is_caught(self):
        # The comparison has teeth: run the real doors with the
        # cap 1 byte too high and the model at the true cap
        # parts from them on 24 runs. Every file over the cap
        # and every stream of 1 byte over. Nothing at or under
        # the cap: the 2 gates agree there.
        caught = sorted(
            (arrival, chunk) for (arrival, chunk) in self.asked
            if arrival[0] in ("file", "stream")
            and not self.agrees(arrival, Asked(arrival, chunk,
                                               cap=REAL_CAP + 1)))
        self.assertEqual(24, len(caught))
        self.assertEqual(
            {("file", 1): 4, ("file", 2): 4, ("file", REAL_CHUNK): 4,
             ("file", REAL_CHUNK + 1): 4, ("stream", 1): 8},
            tally((arrival[0], arrival[1] - REAL_CAP)
                  for arrival, _chunk in caught))


# ---- The third model: hybridselect.tla, P8

GROUPS = ("hybrid", "x25519")


def hybrid_init():
    """Init: every offer set, both profiles, nothing decided."""
    for bits in range(4):
        offered = frozenset(g for i, g in enumerate(GROUPS)
                            if bits >> i & 1)
        for profile in ("v1", "v3"):
            yield (offered, profile, False, "none")


def hybrid_next(state):
    """Decide: the hybrid exactly when the v3 profile carries
    the option and the hello offered it; else X25519 when
    offered; else refused."""
    offered, profile, decided, _outcome = state
    if decided:
        return
    if profile == "v3" and "hybrid" in offered:
        outcome = "hybrid"
    elif "x25519" in offered:
        outcome = "x25519"
    else:
        outcome = "refused"
    yield (offered, profile, True, outcome)


def p8_inv(state):
    offered, profile, decided, outcome = state
    return (not (decided and profile == "v3" and "hybrid" in offered)
            or outcome == "hybrid")


def only_offered(state):
    offered, profile, decided, outcome = state
    if not decided:
        return True
    selectable = ("x25519" in offered
                  or (profile == "v3" and "hybrid" in offered))
    return ((outcome != "hybrid" or "hybrid" in offered)
            and (outcome != "x25519" or "x25519" in offered)
            and ((outcome == "refused") == (not selectable)))


class HybridSelectSearch(unittest.TestCase):
    """hybridselect.tla's Init and Next, searched to the fixed
    point."""

    @classmethod
    def setUpClass(cls):
        cls.initial = list(hybrid_init())
        cls.reached, _steps = search(cls.initial, hybrid_next)

    def test_the_2_invariants_hold_in_every_reachable_state(self):
        self.assertIsNone(first_breaking(self.reached, p8_inv))
        self.assertIsNone(first_breaking(self.reached, only_offered))

    def test_the_counts_are_the_prediction_for_the_checker(self):
        # 4 offer sets by 2 profiles. The decision is
        # deterministic, so each hello has exactly 1 decided
        # state: 8 and 8.
        decided = [s for s in self.reached if s[2]]
        self.assertEqual((8, 8), (len(self.initial), len(decided)))
        self.assertEqual(16, len(self.reached))
        self.assertIn("8 initial states, %d distinct states"
                      % len(self.reached), _flat(RECORD2))

    def test_the_2_probes_are_false_somewhere_as_they_must_be(self):
        self.assertIsNotNone(first_breaking(
            self.reached, lambda s: not (s[2] and s[3] == "hybrid")))
        self.assertIsNotNone(first_breaking(
            self.reached, lambda s: not (s[2] and s[3] == "refused")))
        text = _read(os.path.join(PROOFS, "hybridselect.tla"))
        for stated in (
                "  /\\ outcome' = IF profile = \"v3\" /\\ \"hybrid\""
                " \\in offered\n",
                "                         THEN \"x25519\"\n"
                "                         ELSE \"refused\"",
                "This file was run with TLC on 2026-11-18"):
            self.assertIn(stated, text, stated)
        self.assertTrue(_read(os.path.join(PROOFS, "hybridselect.cfg"))
                        .endswith("SPECIFICATION Spec\nINVARIANT P8Inv\n"
                                  "INVARIANT OnlyOffered\n"))
        for name, probe in (
                ("hybridselectwitnesshybrid.cfg", "NothingSelectsHybrid"),
                ("hybridselectwitnessrefused.cfg", "NothingIsRefused")):
            held = _read(os.path.join(PROOFS, name))
            self.assertTrue(held.startswith("\\* Expected to fail."), name)
            self.assertTrue(held.endswith(
                "SPECIFICATION Spec\nINVARIANT %s\n" % probe), name)


class HybridSelectConformance(unittest.TestCase):
    """The real DTLS cores, pumped through a handshake for
    every combination of the client's offer and the server's
    profile."""

    def test_the_group_numbers_are_c29_s(self):
        self.assertEqual(4588, DTLS.GROUP_X25519MLKEM768)
        self.assertEqual(0x001D, DTLS.GROUP_X25519)

    def test_every_combination_agrees_with_the_model(self):
        # The model decides from the offer set and the profile;
        # the cores are driven through the same 4 combinations
        # and must land on the model's group every time.
        reached, _steps = search(list(hybrid_init()), hybrid_next)
        decided = {(s[0], s[1]): s[3] for s in reached if s[2]}
        groups = {"hybrid": DTLS.GROUP_X25519MLKEM768,
                  "x25519": DTLS.GROUP_X25519}
        handshakes = 0
        for client_hybrid in (False, True):
            for server_hybrid in (False, True):
                offered = (frozenset(GROUPS) if client_hybrid
                           else frozenset(("x25519",)))
                profile = "v3" if server_hybrid else "v1"
                server = DTLS.DtlsServerCore(
                    secret_lookup=DTLS.make_secret_lookup(DTLS_SECRET),
                    hybrid=server_hybrid)
                client = DTLS.DtlsClientCore(DTLS_SECRET,
                                              hybrid=client_hybrid)
                dtls_pump(client, server, addr=("127.0.0.1", 50001),
                          now=1000.0)
                sessions = list(server.sessions.values())
                self.assertEqual(1, len(sessions))
                want = groups[decided[(offered, profile)]]
                self.assertEqual(want, sessions[0].negotiated_group,
                                 (client_hybrid, server_hybrid))
                self.assertEqual(want, client.negotiated_group,
                                 (client_hybrid, server_hybrid))
                handshakes += 1
        self.assertEqual(4, handshakes)
        self.assertIn("4 handshakes", _flat(RECORD2))


# ---- The fifth model: resultfit.tla, P11

BODIES = ("fits", "shrinkable", "fixed")


def fit_init():
    """Init: both cap classes, the 3 body classes, nothing
    decided."""
    for cap in ("zero", "set"):
        for body in BODIES:
            yield (cap, body, False, "none", False)


def fit_next(state):
    """Decide: unlimited, or already within the cap, leaves as
    built; a body the cutting can fit leaves shrunk and
    marked; a body over even at the third pass shape leaves
    over the cap, marked."""
    cap, body, decided, _sent, _marked = state
    if decided:
        return
    if cap == "zero" or body == "fits":
        yield (cap, body, True, "asis", False)
    elif body == "shrinkable":
        yield (cap, body, True, "shrunk", True)
    else:
        yield (cap, body, True, "over", True)


def marked_when_cut(state):
    _cap, _body, decided, sent, marked = state
    return (not decided
            or ((sent not in ("shrunk", "over") or marked)
                and (sent != "asis" or not marked)))


def cap_zero_asis(state):
    cap, _body, decided, sent, _marked = state
    return not (decided and cap == "zero") or sent == "asis"


def fits_asis(state):
    _cap, body, decided, sent, _marked = state
    return not (decided and body == "fits") or sent == "asis"


def p11_floor(state):
    """P11Floor: P11 as it is worded, with its floor."""
    cap, body, decided, sent, marked = state
    return (not (decided and cap == "set")
            or ((body == "fixed" or sent != "over")
                and (sent != "over" or marked)))


def p11_inv(state):
    """P11Inv: the cap with no floor, the witness's probe."""
    cap, _body, decided, sent, _marked = state
    return not (decided and cap == "set") or sent != "over"


class ResultFitSearch(unittest.TestCase):
    """resultfit.tla's Init and Next, searched to the fixed
    point."""

    @classmethod
    def setUpClass(cls):
        cls.initial = list(fit_init())
        cls.reached, _steps = search(cls.initial, fit_next)

    def test_the_4_invariants_hold_in_every_reachable_state(self):
        # The 3 the fitting keeps, and P11 as it is worded,
        # the cap down to the fitting's floor.
        for holds in (marked_when_cut, cap_zero_asis, fits_asis,
                      p11_floor):
            self.assertIsNone(first_breaking(self.reached, holds),
                              holds.__name__)

    def test_the_cap_with_no_floor_breaks_at_exactly_the_fixed_class(self):
        # The witness configuration's invariant, the cap with
        # no floor: it fails, and every state it fails on is
        # the fixed class under a set cap, and there is exactly
        # 1 such decided state. That class is the floor P11's
        # words name.
        breaking = [s for s in self.reached if not p11_inv(s)]
        self.assertEqual(1, len(breaking))
        cap, body, decided, sent, marked = breaking[0]
        self.assertEqual(("set", "fixed", True, "over", True),
                         (cap, body, decided, sent, marked))

    def test_the_counts_are_the_prediction_for_the_checker(self):
        # 2 cap classes by 3 body classes, the decision
        # deterministic: 6 initial states, 6 decided.
        decided = [s for s in self.reached if s[2]]
        self.assertEqual((6, 6), (len(self.initial), len(decided)))
        self.assertEqual(12, len(self.reached))
        self.assertIn("6 initial states, %d distinct states"
                      % len(self.reached), _flat(RECORD2))

    def test_the_probes_are_false_somewhere_as_they_must_be(self):
        self.assertIsNotNone(first_breaking(
            self.reached, lambda s: not (s[2] and s[3] == "shrunk")))
        text = _read(os.path.join(PROOFS, "resultfit.tla"))
        for stated in (
                "       THEN sent' = \"asis\" /\\ marked' = FALSE\n",
                "              THEN sent' = \"shrunk\" /\\ marked' = TRUE\n"
                "              ELSE sent' = \"over\" /\\ marked' = TRUE",
                "This file was run with TLC on 2026-11-18"):
            self.assertIn(stated, text, stated)
        self.assertIn(
            "P11Floor ==\n"
            "  (decided /\\ cap = \"set\") =>\n"
            "    /\\ (body /= \"fixed\" => sent /= \"over\")\n"
            "    /\\ (sent = \"over\" => marked)\n", text)
        self.assertTrue(_read(os.path.join(PROOFS, "resultfit.cfg"))
                        .endswith("INVARIANT MarkedWhenCut\n"
                                  "INVARIANT CapZeroAsIs\n"
                                  "INVARIANT FitsAsIs\n"
                                  "INVARIANT P11Floor\n"))
        for name, probe in (
                ("resultfitwitnessshrunk.cfg", "NothingIsShrunk"),
                ("resultfitwitnesscap.cfg", "P11Inv")):
            held = _read(os.path.join(PROOFS, name))
            self.assertTrue(held.startswith("\\* Expected to fail."), name)
            self.assertTrue(held.endswith(
                "SPECIFICATION Spec\nINVARIANT %s\n" % probe), name)


FIT_SECRET = "v4 fit secret " + hashlib.sha384(b"v4 fit").hexdigest()


def _fit_result(out, err):
    return {"v": 1, "type": "result", "job_id": "j1",
            "kind": "exec", "completed_at": "2026-10-25T00:00:00Z",
            "exit_code": 0, "timed_out": False, "stdout": out,
            "stderr": err, "stdout_truncated": False,
            "stderr_truncated": False, "duration_sec": 0.5,
            "runner": "box", "review": None}


def _fit(cap, out="A" * 40000, err="x" * 40000):
    return RUNNER._fit_result_body(_fit_result(out, err), FIT_SECRET,
                                   False, "j1", "", cap)


class ResultFitConformance(unittest.TestCase):
    """The real _fit_result_body, over the cap classes the
    model names."""

    def test_a_cap_of_0_is_unlimited(self):
        res, body = _fit(0)
        self.assertNotIn("result_truncated", res)
        self.assertGreater(len(body.encode("utf-8")), 80000)

    def test_a_body_within_the_cap_leaves_as_built(self):
        res, body = _fit(100000, "hello", "")
        self.assertNotIn("result_truncated", res)
        self.assertLessEqual(len(body.encode("utf-8")), 100000)
        self.assertEqual("hello", res["stdout"])

    def test_a_shrinkable_body_is_cut_marked_and_fits(self):
        res, body = _fit(20000)
        self.assertLessEqual(len(body.encode("utf-8")), 20000)
        self.assertEqual("max_result_bytes",
                         res["result_truncated"]["reason"])
        self.assertGreater(res["result_truncated"]["dropped"], 0)
        self.assertTrue(res["stdout_truncated"])

    def test_the_floor_is_sharp_and_is_4625(self):
        # The smallest cap the 40,000 by 40,000 result fits
        # under, found by search over the real function. At
        # the floor the body fits and is marked; 1 byte under
        # it, and at every smaller cap tried, the same body
        # leaves at the floor's size, over the cap, marked.
        lo, hi = 1, 30000
        while lo < hi:
            mid = (lo + hi) // 2
            if len(_fit(mid)[1].encode("utf-8")) <= mid:
                hi = mid
            else:
                lo = mid + 1
        self.assertEqual(4625, lo)
        res, body = _fit(lo)
        self.assertEqual(lo, len(body.encode("utf-8")))
        self.assertIn("result_truncated", res)
        for cap in (1, 100, lo - 1):
            res, body = _fit(cap)
            self.assertEqual(lo, len(body.encode("utf-8")), cap)
            self.assertGreater(len(body.encode("utf-8")), cap)
            self.assertEqual("max_result_bytes",
                             res["result_truncated"]["reason"], cap)
        self.assertIn("the floor is %s bytes" % _said(lo),
                      _flat(RECORD2))

    def test_f7_the_cap_holds_down_to_the_floor_and_p11_says_so(self):
        # Finding F7, closed in the property's words. P11 says
        # the body leaves within the cap, down to the fitting's
        # floor. Over a sweep of caps from 1 to past the floor,
        # the real body is never over both the cap and the
        # floor, a body at the floor is marked, and under the
        # floor it leaves at the floor, over the cap. A change
        # on either side, the property's words or the fitting's
        # last pass, shows up here.
        floor = 4625
        caps = sorted(set(range(1, floor + 400, 37))
                      | {floor - 1, floor, floor + 1, 9000, 20000})
        self.assertEqual(140, len(caps))
        under = 0
        for cap in caps:
            res, body = _fit(cap)
            size = len(body.encode("utf-8"))
            self.assertLessEqual(size, max(cap, floor), cap)
            self.assertEqual("max_result_bytes",
                             res["result_truncated"]["reason"], cap)
            if cap < floor:
                self.assertEqual(floor, size, cap)
                under += 1
            else:
                self.assertLessEqual(size, cap, cap)
        self.assertEqual(126, under)
        words = _flat(os.path.join(PROOFS, "v4-properties.md"))
        self.assertIn("P11. A result body leaves within "
                      "`max_result_bytes`, down to the fitting's floor",
                      words)
        self.assertIn("larger than that result's floor", words)
        self.assertIn("Finding F7", _flat(RECORD2))


class FramingScopePin(unittest.TestCase):
    """P9: no session is claimed across the framing break.
    Not a checker claim: a claim about what the documents
    claim, pinned by reading them."""

    def test_the_framing_record_states_the_break(self):
        text = _flat(os.path.join(
            PROOFS, "dtls-record-layer-and-framing.md"))
        self.assertIn("Mixed-version DTLS interoperability is "
                      "not supported across this landing", text)
        self.assertIn("Both ends must run the same side of it",
                      text)

    def test_the_support_matrix_claims_no_mixed_version_session(self):
        text = _flat(os.path.join(ROOT, "docs", "support-matrix.md"))
        self.assertNotIn("mixed-version", text.lower())
        self.assertNotIn("mixed version", text.lower())

    def test_p9_is_stated_in_the_binding_index(self):
        text = _flat(os.path.join(PROOFS, "v4-properties.md"))
        self.assertIn("P9. No session is claimed across the "
                      "framing break", text)


if __name__ == "__main__":
    unittest.main()
