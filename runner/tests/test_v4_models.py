"""The v4 binding's first 3 models, searched and held to the code.

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
"""
import hashlib
import itertools
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from runner import runner as RUNNER  # noqa: E402,F401
from runner.guard import security as SECURITY  # noqa: E402
from runner.ops import remediation_ops as GATE  # noqa: E402
from runner.oracle import resources as RES  # noqa: E402
from runner.wire import verify as VERIFY  # noqa: E402

PROOFS = os.path.join(ROOT, "docs", "infrastructure-documents", "proofs")
RECORD = os.path.join(PROOFS, "v4-search.md")

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

def model_init():
    """Init: the disk over or under, any of the 16 combinations of
    classes with material, nothing acted on."""
    for over in (True, False):
        for bits in range(16):
            present = frozenset(c for c in CLASSES if bits >> (c - 1) & 1)
            yield (over, present, (), "run", False, True)


def next_class(present, acted):
    """NextClass: the smallest class with material not acted on
    yet, or 0."""
    left = sorted(c for c in present if c not in acted)
    return left[0] if left else 0


def model_next(state):
    """Next: Act, then the re-measurement either way; or End."""
    over, present, acted, phase, recorded, alive = state
    if phase != "run":
        return
    following = next_class(present, acted)
    if over and following:
        for again in (True, False):
            yield (again, present, acted + (following,), phase, recorded,
                   alive)
    if not over or not following:
        yield (over, present, acted, "done", bool(acted), alive)


def never_stops(state):
    return state[5] is True


def order_respected(state):
    _over, present, acted, _phase, _recorded, _alive = state
    return (all(c in present for c in acted)
            and all(a < b for a, b in zip(acted, acted[1:])))


def recorded_faithfully(state):
    _over, _present, acted, phase, recorded, _alive = state
    return ((not (phase == "done" and acted) or recorded)
            and (not recorded or bool(acted)))


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
        # 32 initial states: 2 readings by 16 combinations. Over
        # a combination of n classes a running pass stands at any
        # of its n + 1 prefixes with the disk over or under, and
        # a finished one at any prefix with the disk under, or at
        # the whole of it with the disk still over: 3n + 4 states.
        self.assertEqual(32, len(self.initial))
        done = [s for s in self.reached if s[3] == "done"]
        self.assertEqual((160, 64), (len(self.reached), len(done)))
        sizes = [bin(bits).count("1") for bits in range(16)]
        self.assertEqual(len(self.reached), sum(3 * n + 4 for n in sizes))
        self.assertEqual(len(done), sum(n + 2 for n in sizes))
        text = _flat(RECORD)
        self.assertIn("32 initial states, %s distinct states, %s of them "
                      "finished passes" % (_said(len(self.reached)),
                                           _said(len(done))), text)

    def test_the_model_file_states_what_was_searched(self):
        text = _read(os.path.join(PROOFS, "diskguard.tla"))
        for stated in (
                "  /\\ over \\in {TRUE, FALSE}\n"
                "  /\\ present \\in SUBSET Classes\n",
                "  /\\ acted' = Append(acted, NextClass)\n"
                "  /\\ over' \\in {TRUE, FALSE}\n",
                "  /\\ (~over \\/ NextClass = 0)\n"
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
        self.assertEqual(6, len(path))            # Init, 4 actions, End
        self.assertTrue(path[-1][4])
        self.assertEqual([(), (1,), (1, 2), (1, 2, 3), (1, 2, 3, 4),
                          (1, 2, 3, 4)], [s[2] for s in path])

    def test_a_pass_stops_as_soon_as_the_disk_reads_under(self):
        stopped = [s for s in self.reached
                   if s[3] == "done" and s[2] == (1,)
                   and s[1] == frozenset(CLASSES)]
        self.assertEqual(1, len(stopped))
        self.assertFalse(stopped[0][0])

    def test_a_pass_under_the_threshold_acts_on_nothing(self):
        for state in self.reached:
            if state[3] == "done" and not state[2]:
                self.assertFalse(state[4])

    def test_the_2_probes_are_false_somewhere_as_they_must_be(self):
        # NeverActs and NeverRecords, the 2 witness
        # configurations: each expected to fail under the checker.
        self.assertIsNotNone(first_breaking(self.reached,
                                            lambda s: s[2] == ()))
        self.assertIsNotNone(first_breaking(self.reached,
                                            lambda s: s[4] is False))
        text = _read(os.path.join(PROOFS, "diskguard.tla"))
        self.assertIn("NeverActs == acted = <<>>", text)
        self.assertIn("NeverRecords == recorded = FALSE", text)
        for name, probe in (("diskguardwitnessacts.cfg", "NeverActs"),
                            ("diskguardwitnessrecords.cfg", "NeverRecords")):
            held = _read(os.path.join(PROOFS, name))
            self.assertTrue(held.startswith("\\* Expected to fail."), name)
            self.assertTrue(held.endswith(
                "SPECIFICATION Spec\nINVARIANT %s\n" % probe), name)


# ---- The code: one real pass over a real directory

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

    def test_on_a_steady_disk_the_pass_is_one_of_the_model_s(self):
        # The model's finished passes over a combination are the
        # prefixes of its classes in order. On a disk that does
        # not fill up again between 2 measurements, the code's
        # passes are those and only those, and it reaches them all.
        reached, _steps = search(list(model_init()), model_next)
        for present, runs in self.paths.items():
            model = {s[2] for s in reached
                     if s[1] == present and s[3] == "done"}
            code = {run.classes for run in runs if run.steady}
            self.assertEqual(model, code, sorted(present))

    def test_off_a_steady_disk_the_pass_can_end_outside_the_model(self):
        # Finding F1, counted: every such pass still keeps P7's
        # order, and none of them is steady.
        outside = 0
        for present, runs in self.paths.items():
            prefixes = {tuple(sorted(present))[:n]
                        for n in range(len(present) + 1)}
            for run in runs:
                if run.classes not in prefixes:
                    self.assertFalse(run.steady)
                    self.assertEqual(sorted(run.acted), run.acted)
                    outside += 1
        self.assertEqual(412, outside)
        self.assertIn("%s of them end outside the model's finished passes"
                      % _said(outside), _flat(RECORD))


class Findings(unittest.TestCase):
    """Where the code and the model, or the code and P7's words,
    part ways. Each is held here as the tree stands, so a change
    to either side shows up as a change to this class."""

    def test_f1_a_disk_that_refills_takes_the_pass_past_the_model(self):
        # Before any action, the code measures twice: once at the
        # head of a class's loop and once at the next class's
        # door. Under, then over, and the pass moves on to class
        # 2 with class 1's material still on the disk. The model
        # ends the pass at the first reading of under.
        run = Pass(self, frozenset(CLASSES),
                   (OVER, UNDER, OVER, OVER) + (UNDER,) * 4)
        self.assertEqual(len(run.script), len(run.readings))
        self.assertFalse(run.steady)
        self.assertEqual((2,), run.classes)
        self.assertIn("runner.log.1", snapshot(run.base))
        # It is outside the model, and inside P7: in order, after
        # a reading of over, recorded.
        reached, _steps = search(list(model_init()), model_next)
        self.assertNotIn((2,), {s[2] for s in reached
                                if s[1] == frozenset(CLASSES)})
        self.assertIsNotNone(run.event)

    def test_f2_material_of_0_bytes_goes_with_no_record(self):
        # P7 clause 4: every pass that acts leaves 1 event. A pass
        # that removes only 0 byte material acts, and leaves none:
        # the action is noted only when it freed bytes.
        run = Pass(self, frozenset((1, 3, 4)), (OVER,) * 12, empty=True)
        self.assertEqual(["runner.log.1",
                          os.path.join("sent", "old-result.txt"),
                          os.path.join("work", "old-job")], run.roots)
        self.assertIsNone(run.event)
        self.assertIsNone(run.raised)

    def test_f3_a_reading_that_fails_mid_pass_reads_as_over(self):
        # The first reading failing means no pass. A later one
        # failing is taken as over: the pass goes on giving up
        # material with no measurement that says the disk is full.
        self.assertEqual([], Pass(self, frozenset(CLASSES), (None,)).changed)
        run = Pass(self, frozenset(CLASSES), (OVER,) + (None,) * 12)
        self.assertEqual((1, 2, 3, 4), run.classes)
        self.assertIsNotNone(run.event)
        self.assertTrue(run.event["still_over"])
        self.assertIsNone(run.event["disk_after"])

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
                "This file has not been run with TLC."):
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

    def test_f5_a_weak_additional_key_is_refused_in_the_default_s_name(self):
        # The refusal is right. The name in it is the default
        # key's setting whichever key was weak, so when only an
        # additional key is weak the error names a key that did
        # not cost the start. P6 clause 4 asks that the error
        # name the setting.
        refused = [run for run in self.runs if run[2] is None]
        wrong = 0
        for standing, forms, _built, said in refused:
            self.assertRegex(said, r"^config error: shared_secret is "
                                   r"(too weak|required)", (standing, forms))
            for key in KEYS[1:]:
                self.assertNotIn(key, said)
            self.assertNotIn("additional_secrets", said)
            if "default" not in causes(standing):
                wrong += 1
        self.assertEqual((107, 32), (len(refused), wrong))
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
                "This file has not been run with TLC."):
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


if __name__ == "__main__":
    unittest.main()
