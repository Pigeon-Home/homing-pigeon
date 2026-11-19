"""The general statement, searched and held to the code.

FUTURE.md items 1 and 8. general.tla states the 13 properties in
1 model: 1 runner life, every door at its own occasion, and a
world that moves between one occasion and the next. The record
is docs/infrastructure-documents/proofs/v4-general.md.

This module does what test_v4_models.py does for the small
models, on every run of the suite:

  the search        the same model, written here apart from the
                    TLA+ file, searched to the fixed point: every
                    reachable state, every mark of the ledger in
                    each. The counts were this module's
                    prediction for the checker.
  the seams         general.tla has 14 constants. 5 are seams
                    between doors, 1 for each place where a door
                    could have been built to decide at another
                    occasion than its effect's, or to move
                    another door's state. 9 are the doors' own
                    guards, so that every mark of the ledger is
                    one the checker can break. Each is searched
                    the other way, where it must break the
                    property it carries, and each is held to the
                    real code, which must stand where the main
                    configuration says it stands.
  the finding       F8: the disk guard gave up a recorded result
                    that a redelivery the door would still take
                    could need, and the job ran a second time
                    with no priced window used. The search found
                    it, the real code showed it, and it is closed
                    in the code. It is held here as closed.
"""
import collections
import hashlib
import os
import sys
import tempfile
import time
import unittest
from argparse import Namespace
from datetime import datetime, timedelta
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from runner import runner as RUNNER  # noqa: E402
from runner.ops import mail as MAIL  # noqa: E402
from runner.ops import remediation_ops as GATE  # noqa: E402
from runner.oracle import resources as RES  # noqa: E402
from runner.tests import test_proof_conformance as DOOR  # noqa: E402
from runner.tests import test_proof_conformance_p6 as START  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402
from runner.transport_extensions.nats import __main__ as NATS  # noqa: E402

PROOFS = os.path.join(ROOT, "docs", "infrastructure-documents", "proofs")
RECORD = os.path.join(PROOFS, "v4-general.md")

PROPS = tuple("P%d" % n for n in range(1, 14))
BOOL = (False, True)

# What the code does at each seam: the main configuration.
CODE = {"PollRebuilds": True, "SpawnProbes": True,
        "GuardSparesFresh": True, "GuardSparesCache": True,
        "LocalFilesOnly": True, "GateVerifies": True, "GateFresh": True,
        "GatePolicy": True, "TransportGates": True, "StartValidates": True,
        "PrefersHybrid": True, "SameSideOnly": True, "FitMarks": True,
        "LocalBounds": True}

# The property the checker must break when a seam is built the
# other way, and the witness configuration that says so.
SEAMS = (
    ("PollRebuilds", "generalwitnesspoll.cfg", "P13Inv", {"P13"}),
    ("SpawnProbes", "generalwitnessspawn.cfg", "P10Inv", {"P2", "P10"}),
    ("GuardSparesFresh", "generalwitnessreap.cfg", "P5Inv", {"P5"}),
    ("GuardSparesCache", "generalwitnesscache.cfg", "P7Inv", {"P7"}),
    ("LocalFilesOnly", "generalwitnesslocal.cfg", "P1Inv", {"P1", "P5"}),
    # The doors' own guards: each door applies its guard at the
    # step that makes its effect.
    ("GateVerifies", "generalwitnessverifies.cfg", "P1Inv", {"P1"}),
    ("GateFresh", "generalwitnessfresh.cfg", "P5Inv", {"P1", "P5"}),
    ("GatePolicy", "generalwitnesspolicy.cfg", "P4Inv", {"P4"}),
    ("TransportGates", "generalwitnesstransport.cfg", "P3Inv", {"P3"}),
    ("StartValidates", "generalwitnessstart.cfg", "P6Inv", {"P6"}),
    ("PrefersHybrid", "generalwitnessprefers.cfg", "P8Inv", {"P8"}),
    ("SameSideOnly", "generalwitnessframing.cfg", "P9Inv", {"P9"}),
    ("FitMarks", "generalwitnessmarks.cfg", "P11Inv", {"P11"}),
    ("LocalBounds", "generalwitnessbounds.cfg", "P12Inv", {"P12"}),
)

PROBES = (
    ("generalwitnessruns.cfg", "NothingExecutes"),
    ("generalwitnesssecond.cfg", "NoSecondRun"),
    ("generalwitnessfiled.cfg", "NoAlertFiled"),
    ("generalwitnesshybrid.cfg", "NoHybridSession"),
)

FIELDS = ("mode", "cfgfile", "secret", "engage", "disk", "age", "up",
          "inpoll", "stage", "cache", "record", "execs", "bought",
          "session", "filed", "broken")
AT = {name: place for place, name in enumerate(FIELDS)}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _flat(path):
    return " ".join(_read(path).split())


def _said(number):
    return format(number, ",")


def get(state, name):
    return state[AT[name]]


# ---- The model: general.tla, written apart from it

def general_init():
    """Init: either mode, the world any of 16 ways with the job
    fresh, a runner that is not up, and a ledger with every mark
    true. broken holds the properties whose mark is false."""
    for mode in ("enforce", "audit"):
        for cfgfile in ("usable", "unusable"):
            for secret in ("strong", "weak"):
                for engage in BOOL:
                    for disk in ("under", "over"):
                        yield (mode, cfgfile, secret, engage, disk,
                               "fresh", False, False, "idle", False,
                               "none", 0, 0, "none", False, frozenset())


def marked(broken, **found):
    """The ledger after an effect: a property whose guard did not
    hold at this step is broken from here on."""
    return broken | frozenset(p for p, held in found.items() if not held)


def general_steps(state, code=None):
    """Next, as (action, following state). A refusal is no step,
    as in the TLA+ file."""
    code = CODE if code is None else code
    (mode, cfgfile, secret, engage, disk, age, up, inpoll, stage, cache,
     record, execs, bought, session, filed, broken) = state

    def put(**changed):
        following = list(state)
        for name, value in changed.items():
            following[AT[name]] = value
        return tuple(following)

    confined = mode != "enforce" or engage

    # The world moves.
    yield "WorldMoves", put(
        cfgfile="unusable" if cfgfile == "usable" else "usable")
    yield "WorldMoves", put(secret="weak" if secret == "strong" else "strong")
    yield "WorldMoves", put(engage=not engage)
    yield "WorldMoves", put(disk="over" if disk == "under" else "under")
    if age == "fresh":
        yield "WorldMoves", put(age="stale")
    if cache:
        yield "CacheLeaves", put(cache=False)

    if not up:
        if (cfgfile == "usable" or not code["StartValidates"]) \
                and secret == "strong" and confined:
            yield "Start", put(up=True, broken=marked(
                broken, P6=cfgfile == "usable", P13=secret == "strong",
                P10=confined))
        return

    if stage != "ran" or bought == 0:
        yield "Crash", put(up=False, inpoll=False, stage="idle",
                           bought=1 if stage == "ran" else bought)
    if not inpoll and (secret == "strong" or not code["PollRebuilds"]):
        yield "PollBegin", put(inpoll=True, broken=marked(
            broken, P13=secret == "strong"))
    if inpoll and stage == "idle":
        yield "PollEnd", put(inpoll=False)

    for offer in BOOL:
        for support in BOOL:
            for same in ((True,) if code["SameSideOnly"] else BOOL):
                group = "hybrid" if offer and support \
                    and code["PrefersHybrid"] else "x25519"
                yield "Agree", put(session=group, broken=marked(
                    broken, P9=same,
                    P8=not (offer and support) or group == "hybrid"))

    # An arrival is admitted past the gate's clauses. With the
    # seams as the code has them only 1 arrival passes: signed,
    # with its transport's credential, inside its key's policy,
    # and fresh. A seam the other way lets its failing twin in.
    if inpoll and stage == "idle" and not cache \
            and (age == "fresh" or not code["GateFresh"]):
        if record != "none":
            yield "Handle", put(cache=True)
        elif execs < 3 and (mode != "enforce" or not code["SpawnProbes"]
                            or engage):
            for signed in ((True,) if code["GateVerifies"] else BOOL):
                for cred in ((True,) if code["TransportGates"] else BOOL):
                    for policy in ((True,) if code["GatePolicy"] else BOOL):
                        yield "Handle", put(
                            stage="ran", execs=execs + 1, broken=marked(
                                broken, P1=signed and age == "fresh",
                                P3=cred, P4=policy, P5=execs <= bought,
                                P2=confined, P10=confined))

    if stage == "ran":
        yield "Commit", put(stage="idle", record="pending", cache=True,
                            broken=marked(broken, P11=True))
        if not code["FitMarks"]:
            # A body at its floor, over the cap, left unmarked.
            yield "Commit", put(stage="idle", record="pending", cache=True,
                                broken=marked(broken, P11=False))
        if disk == "over" and bought == 0:
            yield "StashFails", put(stage="idle", bought=1)
    if inpoll and record == "pending":
        yield "Deliver", put(record="sent")
    if inpoll and record != "none" and age == "stale":
        yield "RecordLeaves", put(record="none")

    if inpoll and disk == "over":
        for reach in BOOL:
            reap = reach and record == "sent" and (
                age == "stale" or not code["GuardSparesFresh"])
            kept = cache if code["GuardSparesCache"] else False
            yield "Guard", put(record="none" if reap else record, cache=kept,
                               broken=marked(broken, P7=kept == cache))

    if secret == "strong" and age == "fresh":
        for bounded in ((True,) if code["LocalBounds"] else BOOL):
            yield "Local", put(filed=True, broken=marked(
                broken, P12=bounded, P13=secret == "strong"))
            if not code["LocalFilesOnly"] and stage == "idle" and execs < 3:
                yield "Local", put(
                    stage="ran", execs=execs + 1, broken=marked(
                        broken, P1=False, P5=execs <= bought, P12=bounded,
                        P13=secret == "strong"))


def reach(code=None):
    """Every reachable state, breadth first, each with the step
    it was first reached by: a counterexample comes with a
    shortest path. Also the actions taken, and the steps counted."""
    came_from = {state: None for state in general_init()}
    queue = collections.deque(came_from)
    taken = collections.Counter()
    while queue:
        state = queue.popleft()
        for action, following in general_steps(state, code):
            taken[action] += 1
            if following not in came_from:
                came_from[following] = (state, action)
                queue.append(following)
    return came_from, taken


def life(came_from, state):
    """The path to a state, as (action, state) pairs after Init."""
    steps = []
    while came_from[state] is not None:
        before, action = came_from[state]
        steps.append((action, state))
        state = before
    return [(None, state)] + steps[::-1]


def first_breaking(came_from, holds):
    """A shortest life to a state where `holds` is false, or
    None. Breadth first, so the first found is a shortest."""
    for state in came_from:
        if not holds(state):
            return life(came_from, state)
    return None


def general(state):
    return not get(state, "broken")


def at_most_once(state):
    return get(state, "execs") <= 1 + get(state, "bought")


def reads_while_up(state):
    return get(state, "up") or not (
        get(state, "inpoll") or get(state, "stage") == "ran")


def flipped(name):
    code = dict(CODE)
    code[name] = not code[name]
    return code


class GeneralSearch(unittest.TestCase):
    """general.tla's Init and Next with the seams as the code
    has them, searched to the fixed point."""

    @classmethod
    def setUpClass(cls):
        cls.reached, cls.taken = reach()

    def test_every_mark_is_true_in_every_reachable_state(self):
        self.assertIsNone(first_breaking(self.reached, general))
        self.assertIsNone(first_breaking(self.reached, at_most_once))
        self.assertIsNone(first_breaking(self.reached, reads_while_up))

    def test_the_counts_are_the_prediction_for_the_checker(self):
        initial = list(general_init())
        self.assertEqual((32, 14592), (len(initial), len(self.reached)))
        self.assertIn("32 initial states, %s distinct states"
                      % _said(len(self.reached)), _flat(RECORD))

    def test_every_step_of_the_model_is_taken_somewhere(self):
        self.assertEqual(
            {"WorldMoves", "CacheLeaves", "Start", "Crash", "PollBegin",
             "PollEnd", "Agree", "Handle", "Commit", "StashFails",
             "Deliver", "RecordLeaves", "Guard", "Local"},
            set(self.taken))

    def test_a_second_run_is_always_a_bought_one(self):
        runs = collections.Counter(get(s, "execs") for s in self.reached)
        self.assertEqual({0, 1, 2}, set(runs))
        twice = [s for s in self.reached if get(s, "execs") == 2]
        self.assertTrue(twice)
        self.assertTrue(all(get(s, "bought") == 1 for s in twice))
        # And the window is used by a crash or a failed stash,
        # never by the guard.
        path = first_breaking(self.reached, lambda s: get(s, "execs") < 2)
        actions = [action for action, _state in path]
        self.assertTrue({"Crash", "StashFails"} & set(actions), actions)

    def test_the_guard_takes_a_record_only_once_the_job_is_stale(self):
        taken_fresh = []
        for state in self.reached:
            for action, following in general_steps(state):
                if action == "Guard" and get(state, "record") == "sent" \
                        and get(following, "record") == "none" \
                        and get(state, "age") == "fresh":
                    taken_fresh.append(state)
        self.assertEqual([], taken_fresh)
        # It does take one, so the rule above is not empty.
        self.assertTrue(any(
            action == "Guard" and get(following, "record") == "none"
            and get(state, "record") == "sent"
            for state in self.reached
            for action, following in general_steps(state)))

    def test_nothing_is_read_under_a_key_map_that_failed_the_floor(self):
        # A poll opens only on a strong secret, and a start too.
        for state in self.reached:
            for action, _following in general_steps(state):
                if action in ("Start", "PollBegin", "Local"):
                    self.assertEqual("strong", get(state, "secret"))

    def test_the_4_probes_are_false_somewhere_as_they_must_be(self):
        probes = (
            lambda s: get(s, "execs") == 0,
            lambda s: get(s, "execs") < 2,
            lambda s: not get(s, "filed"),
            lambda s: get(s, "session") != "hybrid",
        )
        for probe in probes:
            self.assertIsNotNone(first_breaking(self.reached, probe))


class GeneralSeams(unittest.TestCase):
    """Each seam built the other way, searched: the property it
    carries breaks, and no other."""

    @classmethod
    def setUpClass(cls):
        cls.other = {name: reach(flipped(name))[0]
                     for name, _cfg, _inv, _props in SEAMS}

    def broken_in(self, name):
        return set().union(*(get(s, "broken") for s in self.other[name]))

    def test_each_seam_carries_the_property_its_witness_names(self):
        for name, _cfg, invariant, props in SEAMS:
            with self.subTest(seam=name):
                self.assertEqual(props, self.broken_in(name))
                self.assertIn(invariant[:-3], props)

    def test_the_counts_with_each_seam_the_other_way(self):
        counts = {name: len(self.other[name])
                  for name, _cfg, _inv, _props in SEAMS}
        self.assertEqual({"PollRebuilds": 29184, "SpawnProbes": 21312,
                          "GuardSparesFresh": 39936,
                          "GuardSparesCache": 26112,
                          "LocalFilesOnly": 62208,
                          "GateVerifies": 28032, "GateFresh": 33984,
                          "GatePolicy": 28032, "TransportGates": 28032,
                          "StartValidates": 29184, "PrefersHybrid": 14592,
                          "SameSideOnly": 24320, "FitMarks": 26112,
                          "LocalBounds": 21888}, counts)

    def test_every_mark_can_be_broken_and_every_seam_breaks_one(self):
        # Sufficient: with all 14 as the code has them, no mark
        # is false (GeneralSearch). Necessary: each of the 14,
        # built the other way, breaks a mark, and between them
        # they break all 13.
        breakable = set()
        for name, _cfg, _inv, props in SEAMS:
            self.assertTrue(props, name)
            breakable |= self.broken_in(name)
        self.assertEqual(set(PROPS), breakable)
        self.assertEqual(14, len(SEAMS))
        self.assertEqual(list(CODE), [name for name, *_rest in SEAMS])
        # A door's own guard carries that door's property and no
        # other. The freshness window is the 1 that carries 2.
        own = {name: props for name, _cfg, _inv, props in SEAMS[5:]}
        self.assertEqual(["GateFresh"],
                         [name for name, props in own.items()
                          if len(props) != 1])

    def test_a_stale_job_let_in_runs_past_p1_and_then_a_second_time(self):
        reached = self.other["GateFresh"]
        first = first_breaking(reached, lambda s: "P1" not in get(s, "broken"))
        self.assertEqual("Handle", first[-1][0])
        self.assertEqual(("stale", 1), (get(first[-1][1], "age"),
                                        get(first[-1][1], "execs")))
        second = first_breaking(reached,
                                lambda s: "P5" not in get(s, "broken"))
        actions = [action for action, _state in second
                   if action and action != "WorldMoves"]
        # The record leaves, as it may once the job is stale, the
        # cache lets the id go, and the gate takes the job again.
        self.assertEqual("Handle", actions[-1])
        self.assertIn("RecordLeaves", actions)
        last = second[-1][1]
        self.assertEqual((2, 0, "stale"), (get(last, "execs"),
                                           get(last, "bought"),
                                           get(last, "age")))
        self.assertFalse({"Crash", "StashFails", "Guard"} & set(actions))

    def test_f8_s_counterexample_is_the_life_the_record_tells(self):
        # The guard as it stood: a shortest life to a broken P5.
        path = first_breaking(self.other["GuardSparesFresh"], general)
        actions = [action for action, _state in path
                   if action and action != "WorldMoves"]
        self.assertEqual(
            sorted(["Start", "PollBegin", "Handle", "Commit", "Deliver",
                    "CacheLeaves", "Guard", "Handle"]), sorted(actions))
        # A run and its record, the record delivered, the cache
        # and the record both gone, and then the second run.
        self.assertEqual(["Start", "PollBegin", "Handle", "Commit"],
                         actions[:4])
        self.assertEqual("Handle", actions[-1])
        self.assertLess(actions.index("Deliver"), actions.index("Guard"))
        last = path[-1][1]
        self.assertEqual((2, 0, "fresh", frozenset({"P5"})),
                         (get(last, "execs"), get(last, "bought"),
                          get(last, "age"), get(last, "broken")))
        # No crash and no failed stash stands in it: nothing
        # P5 prices bought the second run.
        self.assertFalse({"Crash", "StashFails", "RecordLeaves"}
                         & set(actions))

    def test_a_poll_that_trusted_the_start_reads_under_a_weak_secret(self):
        path = first_breaking(self.other["PollRebuilds"], general)
        state_before_poll = path[-2][1]
        self.assertEqual("PollBegin", path[-1][0])
        self.assertEqual("weak", get(state_before_poll, "secret"))

    def test_a_spawn_that_carried_the_start_runs_unconfined(self):
        path = first_breaking(self.other["SpawnProbes"], general)
        self.assertEqual("Handle", path[-1][0])
        ran = path[-1][1]
        self.assertEqual(("enforce", False, 1),
                         (get(ran, "mode"), get(ran, "engage"),
                          get(ran, "execs")))

    def test_a_local_door_that_ran_a_script_runs_it_past_p1(self):
        path = first_breaking(self.other["LocalFilesOnly"], general)
        self.assertEqual(["Start", "Local"],
                         [a for a, _s in path if a and a != "WorldMoves"])
        self.assertFalse(get(path[-1][1], "inpoll"))


class GeneralText(unittest.TestCase):
    """The TLA+ file and its configurations say what was searched."""

    def test_the_model_file_states_the_seams_and_the_statement(self):
        text = _read(os.path.join(PROOFS, "general.tla"))
        for stated in (
                "CONSTANTS PollRebuilds, SpawnProbes, GuardSparesFresh, "
                "GuardSparesCache,\n          LocalFilesOnly, GateVerifies, "
                "GateFresh, GatePolicy,\n          TransportGates, "
                "StartValidates, PrefersHybrid, SameSideOnly,\n"
                "          FitMarks, LocalBounds\n",
                "  /\\ StartValidates => cfgfile = \"usable\"\n",
                "  /\\ SameSideOnly => same\n",
                "  /\\ session' = IF offer /\\ support /\\ PrefersHybrid\n",
                "  /\\ (door = \"transport\" /\\ TransportGates) => cred\n",
                "  /\\ GateVerifies => (sig /\\ rest)\n",
                "  /\\ GatePolicy => policy\n",
                "  /\\ GateFresh => age = \"fresh\"\n",
                "Marked(body) == body = \"cut\" \\/ "
                "(body = \"floor\" /\\ FitMarks)\n",
                "  /\\ LocalBounds => (form = \"file\" /\\ "
                "size = \"within\")\n",
                "Confined == mode = \"enforce\" => engage",
                "  /\\ up /\\ ~inpoll\n"
                "  /\\ PollRebuilds => secret = \"strong\"\n"
                "  /\\ inpoll' = TRUE",
                "        /\\ (mode = \"enforce\" /\\ SpawnProbes) => engage",
                "             ![\"P5\"] = @ /\\ execs <= bought,",
                "  /\\ LET reap == /\\ reach /\\ record = \"sent\"\n"
                "                 /\\ GuardSparesFresh => age = \"stale\"\n"
                "         kept == IF GuardSparesCache THEN cache ELSE FALSE",
                "        /\\ held' = [held EXCEPT ![\"P7\"] = @ /\\ kept = cache]",
                "     \\/ /\\ kind = \"script\" /\\ ~LocalFilesOnly",
                "             ![\"P1\"] = FALSE,",
                "General == \\A p \\in Props : held[p]",
                "AtMostOnce == execs <= 1 + bought",
                "ReadsWhileUp == (inpoll \\/ stage = \"ran\") => up",
                "This file was run with TLC on 2026-11-18"):
            self.assertIn(stated, text, stated)

    def test_the_main_configuration_sets_the_seams_as_the_code_has_them(self):
        held = _read(os.path.join(PROOFS, "general.cfg"))
        seams = "CONSTANTS\n" + "".join(
            "  %s = TRUE\n" % name for name in CODE)
        self.assertIn(seams + "SPECIFICATION Spec\n", held)
        invariants = ["TypeOK", "General", "AtMostOnce", "ReadsWhileUp"] \
            + ["%sInv" % p for p in PROPS]
        self.assertTrue(held.endswith(
            "SPECIFICATION Spec\n"
            + "".join("INVARIANT %s\n" % name for name in invariants)))

    def test_each_witness_configuration_names_what_it_breaks(self):
        for name, cfg, invariant, _props in SEAMS:
            held = _read(os.path.join(PROOFS, cfg))
            self.assertTrue(held.startswith("\\* Expected to fail."), cfg)
            self.assertIn("  %s = FALSE\n" % name, held)
            self.assertEqual(len(CODE) - 1, held.count(" = TRUE\n"), cfg)
            self.assertTrue(held.endswith(
                "SPECIFICATION Spec\nINVARIANT %s\n" % invariant), cfg)
        for cfg, probe in PROBES:
            held = _read(os.path.join(PROOFS, cfg))
            self.assertTrue(held.startswith("\\* Expected to fail."), cfg)
            self.assertEqual(len(CODE), held.count(" = TRUE\n"), cfg)
            self.assertTrue(held.endswith(
                "SPECIFICATION Spec\nINVARIANT %s\n" % probe), cfg)

    def test_the_record_carries_the_checker_s_verdicts(self):
        record = _flat(RECORD)
        self.assertIn("14,592 distinct states", record)
        for _name, cfg, invariant, _props in SEAMS:
            self.assertIn("`%s` violates %s" % (cfg, invariant), record)
        for cfg, probe in PROBES:
            self.assertIn("`%s` violates %s" % (cfg, probe), record)


# ---- The seams, held to the real code

STRONG = hashlib.sha384(b"v4 general, a strong secret").hexdigest()
WEAK = "abcabcabcabc"


def _put(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    # A secret file is refused when everyone may read it.
    os.chmod(path, 0o600)


class SeamPoll(unittest.TestCase):
    """PollRebuilds: the real poll builds the key map before it
    reads anything, and one that fails the floor reads nothing."""

    def poll(self, folder, cfg):
        with mock.patch.object(RUNNER, "_service_transports") as service, \
                mock.patch.object(RUNNER, "handle_mail") as handled, \
                mock.patch.object(RES, "guard_disk",
                                  return_value=None) as guard, \
                mock.patch.object(RUNNER, "log"):
            try:
                RUNNER.poll_once(cfg, folder, {},
                                 os.path.join(folder, "seen.json"),
                                 opts=Namespace(dry_run=False, once=True))
                raised = None
            except RuntimeError as exc:
                raised = str(exc)
        return raised, service.call_count, handled.call_count, \
            guard.call_count

    def test_a_secret_gone_weak_after_the_start_ends_the_next_poll(self):
        with tempfile.TemporaryDirectory() as folder:
            held = os.path.join(folder, "secret")
            _put(held, STRONG)
            cfg = {"mailbox_user": "t@example.com", "base_dir": folder,
                   "shared_secret_file": held, "transports": ["file"],
                   "local_signals": False}
            # The start's own reading, and a poll, on the strong
            # secret.
            RUNNER._verify.validate_key_directory(
                cfg, RUNNER.build_secrets(cfg))
            raised, serviced, handled, guarded = self.poll(folder, cfg)
            self.assertIsNone(raised)
            self.assertEqual((1, 1), (serviced, guarded))
            # The world moves: the file now holds a weak secret.
            _put(held, WEAK)
            raised, serviced, handled, guarded = self.poll(folder, cfg)
            self.assertIn("too weak", raised)
            self.assertEqual((0, 0, 0), (serviced, handled, guarded))
            # And back: the next poll reads again, with no restart.
            _put(held, STRONG)
            raised, serviced, handled, guarded = self.poll(folder, cfg)
            self.assertIsNone(raised)
            self.assertEqual(1, serviced)

    def test_the_loop_outlives_a_poll_that_failed(self):
        # The failed poll costs that cycle, not the runner: the
        # loop names it and goes on to the next.
        text = _read(os.path.join(ROOT, "runner", "ops", "main.py"))
        self.assertIn(
            "            except Exception as e:\n"
            "                R.log(f\"poll cycle failed: {e}\", \"ERROR\")\n",
            text)
        poll = _read(os.path.join(ROOT, "runner", "ops", "poll.py"))
        built = poll.index("secrets = _runner().build_secrets(cfg)")
        for later in ("_runner().prune_sent(base_dir, retain_days)",
                      "_runner()._resources.guard_disk(cfg, base_dir)",
                      "_runner()._service_transports(cfg, base_dir"):
            self.assertLess(built, poll.index(later), later)

    def test_the_local_door_builds_a_key_map_of_its_own(self):
        with tempfile.TemporaryDirectory() as folder:
            held = os.path.join(folder, "secret")
            _put(held, WEAK)
            cfg = {"base_dir": folder, "shared_secret_file": held}
            text = DOOR.sign_payload(DOOR._job2("g-local-weak"), STRONG)
            notes = []
            with mock.patch.object(RUNNER, "verify_body_keyed") as verify, \
                    mock.patch.object(RUNNER, "log",
                                      lambda msg, level="INFO":
                                      notes.append(msg)):
                self.assertIsNone(RUNNER._ingest_local_envelope(
                    cfg, folder, text, "file"))
            verify.assert_not_called()
            self.assertTrue(any("too weak" in note for note in notes), notes)


PLATFORMS = {
    "darwin": ("IS_MACOS_BACKEND", "macos_confinement_problem"),
    "freebsd14": ("IS_FREEBSD_BACKEND", "freebsd_confinement_problem"),
    "win32": ("IS_WINDOWS_BACKEND", "windows_confinement_problem"),
}


class _World:
    """A confinement backend whose answer can move between the
    start and a spawn."""

    def __init__(self, platform):
        flag, probe = PLATFORMS[platform]
        self.engages = True
        self.asked = 0
        setattr(self, flag, True)
        setattr(self, probe, self.answer)

    def answer(self, cfg=None, *rest):
        self.asked += 1
        return None if self.engages else "the backend cannot engage"


class SeamSpawn(unittest.TestCase):
    """SpawnProbes: under enforce the real spawn gate asks the
    backend at that step, and a backend gone since the start
    costs the job, never the confinement."""

    ENFORCE = {"security": {"modes": {"confinement": "enforce"}}}

    def spawn(self, folder, platform, backend, cfg=None):
        with mock.patch.object(RUNNER.sys, "platform", platform), \
                mock.patch.object(RUNNER, "log"):
            return RUNNER._confinement_argv(
                self.ENFORCE if cfg is None else cfg, folder, "g-spawn",
                ["sh"], "job.sh", folder, [], {}, backend=backend)

    def test_a_backend_gone_since_the_start_refuses_the_job(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform), \
                    tempfile.TemporaryDirectory() as folder:
                world = _World(platform)
                # The start: the gate asks, and the answer lets
                # the runner up.
                self.assertIsNone(GATE.confinement_startup_problem(
                    self.ENFORCE, platform=platform, backend=world))
                at_start = world.asked
                self.assertGreaterEqual(at_start, 1)
                # A spawn while the backend still engages.
                argv, _shell, _boxed = self.spawn(folder, platform, world)
                self.assertEqual(["sh", "job.sh"], argv)
                self.assertEqual(at_start + 1, world.asked)
                # The world moves, and the next spawn asks again.
                world.engages = False
                argv, _shell, _boxed = self.spawn(folder, platform, world)
                self.assertEqual([], argv)
                self.assertEqual(at_start + 2, world.asked)
                # And back.
                world.engages = True
                argv, _shell, _boxed = self.spawn(folder, platform, world)
                self.assertEqual(["sh", "job.sh"], argv)

    def test_off_and_audit_spawn_without_asking(self):
        for mode in ("off", "audit"):
            cfg = {"security": {"modes": {"confinement": mode}}}
            with tempfile.TemporaryDirectory() as folder:
                world = _World("darwin")
                world.engages = False
                argv, _shell, _boxed = self.spawn(
                    folder, "darwin", world, cfg)
                self.assertEqual(["sh", "job.sh"], argv, mode)
                self.assertEqual(0, world.asked, mode)

    def test_on_linux_the_sandbox_is_asked_at_the_spawn_too(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(RUNNER._sandbox, "sandbox_available",
                                   return_value=False) as asked:
                argv, _shell, _boxed = self.spawn(folder, "linux", None)
            self.assertEqual([], argv)
            self.assertEqual(1, asked.call_count)


def _records(folder):
    found = {}
    for top, _dirs, names in os.walk(folder):
        for name in names:
            path = os.path.join(top, name)
            with open(path, "rb") as fh:
                found[os.path.relpath(path, folder)] = fh.read()
    return found


def _guard_pass(folder, cfg=None, now=None):
    """1 real guard pass on a disk that measures over at every
    reading."""
    with mock.patch.object(RES, "_disk_fraction", lambda _base: 0.99):
        return RES.guard_disk({} if cfg is None else cfg, folder, now=now)


class SeamGuardReplay(DOOR._GateCase):
    """GuardSparesFresh, and finding F8 held as closed: the real
    guard and the real door, in 1 life."""

    def test_f8_a_guard_pass_no_longer_buys_a_second_run(self):
        raw = DOOR._wire2(DOOR._job2("g-f8-1"))
        with tempfile.TemporaryDirectory() as folder:
            first = DOOR._run(raw=raw, base_dir=folder)
            self.assertEqual(1, len(first.executed))
            skey = list(first.seen)[0]
            sent = RUNNER._sent_path(folder, skey)
            self.assertTrue(os.path.exists(sent))
            # The cache lets the id go, as at its cap.
            os.remove(os.path.join(folder, "seen.json"))
            # A guard pass on a disk that measures over. It takes
            # what it may; the recorded result is not among it.
            event = _guard_pass(folder)
            taken = [] if event is None else [
                action["path"] for action in event["actions"]]
            self.assertNotIn(os.path.relpath(sent, folder), taken)
            self.assertTrue(os.path.exists(sent))
            # The redelivery the door still takes is answered
            # from the record, and nothing runs.
            again = DOOR._run(raw=raw, base_dir=folder, seen={})
            self.assertEqual([], again.executed)
            self.assertEqual(1, len(again.sent))
            self.assertEqual(first.sent[0][1], again.sent[0][1])
            self.said(again, "result resent from the record")

    def test_f8_the_life_as_it_ran_before_the_finding_was_closed(self):
        # The same life with the window taken away is the
        # finding itself: the guard takes the record, and the
        # job runs a second time with no crash and no expiry.
        raw = DOOR._wire2(DOOR._job2("g-f8-2"))
        with tempfile.TemporaryDirectory() as folder:
            first = DOOR._run(raw=raw, base_dir=folder)
            skey = list(first.seen)[0]
            sent = RUNNER._sent_path(folder, skey)
            os.remove(os.path.join(folder, "seen.json"))
            with mock.patch.object(RES, "_guard_replay_window",
                                   lambda _cfg: -1):
                _guard_pass(folder)
            self.assertFalse(os.path.exists(sent))
            again = DOOR._run(raw=raw, base_dir=folder, seen={})
            self.assertEqual(1, len(again.executed))

    def test_the_window_covers_every_redelivery_the_door_would_take(self):
        # The door takes a job whose age is from 300 seconds
        # ahead of the clock to max_job_age_sec behind it. The
        # record is written no earlier than the door took the
        # job. So the last instant a redelivery is still fresh
        # is the record's time, plus 300, plus the window.
        door = _read(os.path.join(ROOT, "runner", "ops", "mail.py"))
        self.assertIn("if age < -300 or age > max_age:", door)
        self.assertEqual(300, RES.DISK_GUARD_REPLAY_SKEW_SEC)
        for max_age in (1, 60, 3600, 86400, 604800):
            window = RES._guard_replay_window({"max_job_age_sec": max_age})
            for ahead in (0, 1, 150, 300):
                taken_at = 1_000_000.0
                issued_at = taken_at + ahead
                last_fresh = issued_at + max_age
                for written_after in (0.0, 5.0, 3600.0):
                    record_time = taken_at + written_after
                    # Spared at that instant: not past the window.
                    self.assertLessEqual(last_fresh - record_time, window,
                                         (max_age, ahead, written_after))

    def test_a_record_past_its_window_goes_and_its_job_is_stale_by_then(self):
        with tempfile.TemporaryDirectory() as folder:
            first = DOOR._run(raw=DOOR._wire2(DOOR._job2("g-f8-3")),
                              base_dir=folder)
            skey = list(first.seen)[0]
            sent = RUNNER._sent_path(folder, skey)
            window = RES._guard_replay_window({})
            wrote = os.path.getmtime(sent)
            record = os.path.relpath(sent, folder)
            event = _guard_pass(folder, now=wrote + window)
            self.assertNotIn(record, [] if event is None else [
                a["path"] for a in event["actions"]])
            self.assertTrue(os.path.exists(sent))
            # The next pass the cooldown allows finds it past
            # its window.
            event = _guard_pass(folder, now=wrote + window + 901)
            self.assertIn(record, [a["path"] for a in event["actions"]])
            self.assertFalse(os.path.exists(sent))
        # A redelivery of bytes that old does not reach the claim.
        stale = DOOR._job2("g-f8-4",
                           issued_at=DOOR._issued(seconds=-(3600 + 2)))
        out = DOOR._run(job=stale)
        self.refused(out, "issued_at outside allowed window")


class SeamGuardCache(unittest.TestCase):
    """GuardSparesCache: a real guard pass that takes all it may
    leaves the replay cache and the waiting outbox as they were."""

    def test_the_cache_and_the_waiting_result_outlive_the_pass(self):
        waits = mock.patch.object(RUNNER, "deliver_stash",
                                  lambda *args, **kwargs: None)
        with tempfile.TemporaryDirectory() as folder:
            out = DOOR._run(raw=DOOR._wire2(DOOR._job2("g-cache-1")),
                            base_dir=folder, patches=(waits,))
            self.assertEqual(1, len(out.executed))
            skey = list(out.seen)[0]
            waiting = os.path.relpath(RUNNER._stash_path(folder, skey),
                                      folder)
            _put(os.path.join(folder, "config.json"), "{}")
            _put(os.path.join(folder, "security-events.jsonl"), "")
            before = _records(folder)
            self.assertIn("seen.json", before)
            self.assertIn(waiting, before)
            # Far enough on that every window has run out, so the
            # pass takes everything it is allowed to take.
            event = _guard_pass(folder, now=time.time() + 30 * 86400)
            self.assertIsNotNone(event)
            self.assertTrue(event["still_over"])
            after = _records(folder)
            for kept in ("seen.json", waiting, "config.json",
                         "security-events.jsonl"):
                self.assertEqual(before[kept], after.get(kept), kept)
            # What went was the pass's own to take.
            for action in event["actions"]:
                self.assertTrue(action["path"].split(os.sep)[0] in (
                    "retained", "sent", "work", "outbox")
                    or action["path"].startswith(("runner.log",
                                                  "oracle")), action)
                self.assertNotEqual(waiting, action["path"])
            # And the duplicate is turned away by the cache: the
            # pass bought nothing.
            again = DOOR._run(raw=DOOR._wire2(DOOR._job2("g-cache-1")),
                              base_dir=folder, seen={})
            self.assertEqual([], again.executed)


class SeamLocal(unittest.TestCase):
    """LocalFilesOnly: the real local door runs nothing. A script
    that would pass the mail gate is turned away at its kind."""

    def test_a_signed_script_at_the_local_door_does_not_run(self):
        job = DOOR._job2("g-local-1", api_version=1)
        with tempfile.TemporaryDirectory() as folder:
            cfg = {"base_dir": folder, "shared_secret": DOOR.SECRET}
            notes = []
            with mock.patch.object(RUNNER, "execute_job") as executed, \
                    mock.patch.object(RUNNER, "_sensor_alert_core") as core, \
                    mock.patch.object(RUNNER, "log",
                                      lambda msg, level="INFO":
                                      notes.append(msg)):
                self.assertIsNone(RUNNER._ingest_local_envelope(
                    cfg, folder, DOOR.sign_payload(job, DOOR.SECRET), "file"))
            executed.assert_not_called()
            core.assert_not_called()
            self.assertTrue(any("local delivery files alerts only" in note
                                for note in notes), notes)
            self.assertFalse(os.path.exists(os.path.join(folder, "seen.json")))
        # The same job on the mail path does run: the kind is
        # what the local door turned away, not the signature.
        self.assertEqual(1, len(DOOR._run(job=job).executed))

    def test_the_local_door_s_own_clauses_are_the_ones_the_model_gives_it(self):
        # It bounds, builds its key map, verifies, and checks the
        # kind, the version, the age and the key policy. It asks
        # no cleartext decision, no audience and no replay cache.
        text = _read(os.path.join(ROOT, "runner", "runner.py"))
        start = text.index("def _ingest_local_envelope_inner(")
        body = text[start:text.index("\n# --- the wake gate", start)]
        order = ["_LOCAL_ENVELOPE_MAX_BYTES", "build_secrets(cfg)",
                 "verify_body_keyed(text, secrets)",
                 "job.get(\"kind\") != \"sensor_alert\"",
                 "_version_ok(job.get(\"v\"))", "max_job_age_sec",
                 "check_key_policy(", "_sensor_alert_core("]
        places = [body.index(step) for step in order]
        self.assertEqual(sorted(places), places)
        for absent in ("audience_allows", "_cleartext_jobs_allowed",
                       "seen", "execute_job", "_disk_owns"):
            self.assertNotIn(absent, body, absent)


# ---- The doors' own guards, held to the real code

class _Later(datetime):
    """The gate's clock, 3,700 seconds on."""

    @classmethod
    def now(cls, tz=None):
        return datetime.now(tz) + timedelta(seconds=3700)


class SeamGate(DOOR._GateCase):
    """GateVerifies, GateFresh and GatePolicy: the real gate asks
    each at the arrival, and a job runs only past all 3."""

    def test_a_job_runs_only_under_a_signature_the_runner_can_check(self):
        self.assertEqual(1, len(DOOR._run(job=DOOR._job2("g-gate-1")).executed))
        stranger = hashlib.sha384(b"v4 general, a key not held").hexdigest()
        self.refused(DOOR._run(job=DOOR._job2("g-gate-2"), secret=stranger),
                     "bad signature")

    def test_a_job_runs_only_inside_the_window(self):
        inside = DOOR._job2("g-gate-3", issued_at=DOOR._issued(seconds=-3500))
        self.assertEqual(1, len(DOOR._run(job=inside).executed))
        outside = DOOR._job2("g-gate-4",
                             issued_at=DOOR._issued(seconds=-3700))
        self.refused(DOOR._run(job=outside),
                     "issued_at outside allowed window")

    def test_the_window_is_read_off_the_clock_at_each_arrival(self):
        # The same bytes, fresh at the first arrival and stale at
        # the next, each at a runner with no record of the job:
        # the first runs and the second does not.
        raw = DOOR._wire2(DOOR._job2("g-gate-5"))
        self.assertEqual(1, len(DOOR._run(raw=raw).executed))
        with mock.patch.object(MAIL, "datetime", _Later):
            self.refused(DOOR._run(raw=raw),
                         "issued_at outside allowed window")

    def test_a_key_runs_only_what_its_policy_allows(self):
        fence = {"": {"allowed_kinds": ["ping"]}}
        self.assertEqual(1, len(DOOR._run(
            job=DOOR._job2("g-gate-6"), policies=fence).executed))
        self.refused(DOOR._run(
            job=DOOR._job2("g-gate-7", kind="exec", script="echo no"),
            policies=fence), "key policy")


class SeamTransport(unittest.TestCase):
    """TransportGates: a transport that has a credential does not
    open without it."""

    def test_the_nats_pipe_does_not_start_without_its_credential(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(NATS.TransportError):
                NATS.NatsPipe({}, folder)
            self.assertIsNotNone(NATS.NatsPipe({"token": "tok-abc"}, folder))


class SeamStart(unittest.TestCase):
    """StartValidates: the real start refuses a configuration it
    cannot use, and names the setting."""

    def test_a_start_on_an_unusable_cap_stops_and_names_it(self):
        code, said, _logs = START._startup({"max_job_bytes": "lots"})
        self.assertEqual(2, code)
        self.assertIn("max_job_bytes", said)
        self.assertEqual(0, START._startup({})[0])


class SeamSession(unittest.TestCase):
    """PrefersHybrid and SameSideOnly."""

    def test_a_session_that_can_agree_the_hybrid_group_agrees_it(self):
        dtls = MODELS.DTLS
        server = dtls.DtlsServerCore(
            secret_lookup=dtls.make_secret_lookup(MODELS.DTLS_SECRET),
            hybrid=True)
        client = dtls.DtlsClientCore(MODELS.DTLS_SECRET, hybrid=True)
        MODELS.dtls_pump(client, server, addr=("127.0.0.1", 50002),
                         now=1000.0)
        sessions = list(server.sessions.values())
        self.assertEqual(1, len(sessions))
        self.assertEqual(dtls.GROUP_X25519MLKEM768,
                         sessions[0].negotiated_group)
        self.assertEqual(dtls.GROUP_X25519MLKEM768, client.negotiated_group)

    def test_no_document_claims_a_session_across_the_framing_break(self):
        # P9 is a statement of scope, so its seam is held as P9
        # is: by what the shelf's framing record says.
        text = _flat(os.path.join(PROOFS,
                                  "dtls-record-layer-and-framing.md"))
        self.assertIn("Mixed-version DTLS interoperability is not "
                      "supported across this landing", text)
        self.assertIn("Both ends must run the same side of it", text)


class SeamFit(unittest.TestCase):
    """FitMarks: a body the fitting leaves over its cap is marked."""

    def test_a_body_left_over_its_cap_carries_the_mark(self):
        result = {"v": 1, "type": "result", "job_id": "g-fit-2",
                  "exit_code": 0, "stdout": "o" * 20000,
                  "stderr": "e" * 20000, "timed_out": False}
        fitted, body = RUNNER._fit_result_body(
            dict(result), DOOR.SECRET, False, "g-fit-2", "", 1)
        self.assertGreater(len(body.encode("utf-8")), 1)
        self.assertEqual("max_result_bytes",
                         fitted["result_truncated"]["reason"])
        self.assertGreater(fitted["result_truncated"]["dropped"], 0)
        whole, _body = RUNNER._fit_result_body(
            dict(result), DOOR.SECRET, False, "g-fit-2", "", 10 ** 9)
        self.assertNotIn("result_truncated", whole)


class SeamLocalBounds(unittest.TestCase):
    """LocalBounds: the local door bounds an envelope before it
    reads it."""

    def test_an_envelope_over_the_cap_is_refused_before_any_key_work(self):
        over = "x" * (RUNNER._LOCAL_ENVELOPE_MAX_BYTES + 1)
        with tempfile.TemporaryDirectory() as folder:
            cfg = {"base_dir": folder, "shared_secret": DOOR.SECRET}
            with mock.patch.object(RUNNER, "build_secrets") as keys, \
                    mock.patch.object(RUNNER, "verify_body_keyed") as verify, \
                    mock.patch.object(RUNNER, "log", lambda *a, **k: None):
                self.assertIsNone(RUNNER._ingest_local_envelope(
                    cfg, folder, over, "file"))
            keys.assert_not_called()
            verify.assert_not_called()

    def test_a_symlinked_envelope_is_not_read(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory() as folder, \
                tempfile.TemporaryDirectory() as outside:
            cfg = {"base_dir": folder, "shared_secret": DOOR.SECRET}
            inbox = os.path.join(folder, RUNNER.LOCAL_INBOX_DIRNAME)
            os.makedirs(inbox)
            target = os.path.join(outside, "signed.json")
            _put(target, DOOR.sign_payload(
                DOOR._job2("g-link-1", kind="sensor_alert", api_version=1),
                DOOR.SECRET))
            try:
                os.symlink(target, os.path.join(inbox, "arrival.json"))
            except OSError:
                self.skipTest("symlinks unavailable")
            notes = []
            with mock.patch.object(RUNNER, "_ingest_local_envelope") as read, \
                    mock.patch.object(RUNNER, "log",
                                      lambda msg, level="INFO":
                                      notes.append(msg)):
                RUNNER._scan_local_inbox(cfg, folder)
            read.assert_not_called()
            self.assertTrue(any("symlink refused" in note for note in notes),
                            notes)
            self.assertTrue(os.path.exists(target))


if __name__ == "__main__":
    unittest.main()
