#!/usr/bin/env python3
"""The held output: finding F17, closed.

docs/infrastructure-documents/proofs/v4-the-bars.md found that the
runner held all that a job wrote before it cut each stream to the
output cap. The rule that closes it: the runner holds at most a
fixed number of bytes of each stream of a job, whatever the job
writes, and the result is what it was.

This module holds the model of the reader, `held.tla`, by a twin
written apart from the checker, whose counts were the prediction
the checker met.
"""
import collections
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-bars.md")

# ---- The model's twin
#
# The world of held.tla: what a job may write, what a pipe holds,
# the most 1 read takes, the output cap, and the bar.
WORLD = collections.OrderedDict((
    ("MaxWrite", 24), ("PipeRoom", 5), ("Chunk", 3), ("Cap", 6),
    ("Keep", 9)))
INVARIANTS = ("TypeOK", "NothingIsLost", "HeldUnderTheBar",
              "HeldIsTheFirstPart", "TheResultIsAsItWas",
              "ACutIsATruncation", "NeverHeldWhole")
CONFIGURATIONS = {
    "heldbar.cfg": (True, 9, INVARIANTS),
    "heldasitwas.cfg": (False, 9, tuple(
        name for name in INVARIANTS if name != "HeldUnderTheBar")),
    "heldwitnessasitwas.cfg": (False, 9, ("HeldUnderTheBar",)),
    "heldwitnessshortbar.cfg": (True, 4, ("TheResultIsAsItWas",)),
}


def broken_by(state, keep, bounded, world=WORLD):
    """The invariants of held.tla that 1 state breaks."""
    written, pipe, seen, held, job, result = state
    cap, most = world["Cap"], world["MaxWrite"]
    out = []
    if not (0 <= written <= most and 0 <= pipe <= world["PipeRoom"]
            and 0 <= seen <= most and 0 <= held <= most
            and job in ("running", "ended") and -1 <= result <= cap):
        out.append("TypeOK")
    if written != pipe + seen:
        out.append("NothingIsLost")
    if held > keep:
        out.append("HeldUnderTheBar")
    if held != (min(seen, keep) if bounded else seen):
        out.append("HeldIsTheFirstPart")
    if result != -1 and result != min(written, cap):
        out.append("TheResultIsAsItWas")
    if seen > held and not seen > cap:
        out.append("ACutIsATruncation")
    if bounded and seen > keep and not held < seen:
        out.append("NeverHeldWhole")
    return out


def steps(state, keep, bounded, world=WORLD):
    """Every state 1 step of held.tla leads to, with repeats."""
    written, pipe, seen, held, job, result = state
    chunk = world["Chunk"]
    out = []
    if job == "running":
        for more in range(1, chunk + 1):
            if written + more <= world["MaxWrite"] \
                    and pipe + more <= world["PipeRoom"]:
                out.append((written + more, pipe + more, seen, held, job,
                            result))
    if pipe > 0 and result == -1:
        took = min(pipe, chunk)
        out.append((written, pipe - took, seen + took,
                    min(keep, held + took) if bounded else held + took,
                    job, result))
    if job == "running":
        out.append((written, pipe, seen, held, "ended", result))
    if job == "ended" and pipe == 0 and result == -1:
        out.append((written, pipe, seen, held, job,
                    min(held, world["Cap"])))
    if result != -1:
        out.append(state)
    return out


def walk(keep, bounded, world=WORLD):
    """The whole of held.tla's world, breadth first: (distinct
    states, states generated, depth, {invariant: states that
    break it})."""
    start = (0, 0, 0, 0, "running", -1)
    depth_of = {start: 1}
    queue = collections.deque([start])
    generated = 1
    while queue:
        state = queue.popleft()
        for after in steps(state, keep, bounded, world):
            generated += 1
            if after not in depth_of:
                depth_of[after] = depth_of[state] + 1
                queue.append(after)
    broken = collections.Counter()
    for state in depth_of:
        broken.update(broken_by(state, keep, bounded, world))
    return (len(depth_of), generated, max(depth_of.values()),
            dict(broken))


def cfg_of(name):
    """A configuration of held.tla as its file states it:
    ({constant: value}, [invariants])."""
    with open(os.path.join(MODELS.PROOFS, name), encoding="utf-8") as handle:
        text = re.sub(r"\\\*.*", "", handle.read())
    constants = {key: value for key, value in re.findall(
        r"(?m)^\s*(\w+) = (\w+)\s*$", text)}
    invariants = text.split("INVARIANT", 1)[1].split()
    return constants, invariants


class TheModelOfTheReader(unittest.TestCase):
    """held.tla, walked by its twin."""

    def test_the_twin_counted_what_the_checker_then_counted(self):
        # The twin's counts stood first. TLC 2.19 then found the
        # same 295 distinct states among 665 generated, to a
        # depth of 19, with the bar and as it was.
        for bounded in (True, False):
            distinct, generated, depth, _broken = walk(WORLD["Keep"],
                                                       bounded)
            self.assertEqual((295, 665, 19), (distinct, generated, depth))

    def test_with_the_bar_every_invariant_holds(self):
        self.assertEqual({}, walk(WORLD["Keep"], True)[3])

    def test_the_reader_as_it_was_breaks_the_bar_and_nothing_else(self):
        self.assertEqual({"HeldUnderTheBar": 165},
                         walk(WORLD["Keep"], False)[3])
        # The first state past the bar: the job has written 10,
        # and all 10 are held.
        past = sorted(
            state for state in self._reached(WORLD["Keep"], False)
            if state[3] > WORLD["Keep"])
        self.assertEqual((10, 0, 10, 10, "ended", -1), past[0])

    def _reached(self, keep, bounded):
        seen, queue = set(), collections.deque([(0, 0, 0, 0, "running", -1)])
        while queue:
            state = queue.popleft()
            if state in seen:
                continue
            seen.add(state)
            queue.extend(steps(state, keep, bounded))
        return seen

    def test_a_bar_under_the_cap_changes_the_result(self):
        broken = walk(4, True)[3]
        self.assertEqual(["ACutIsATruncation", "TheResultIsAsItWas"],
                         sorted(broken))
        # The least such job writes 5, and its result carries 4.
        short = min(state for state in self._reached(4, True)
                    if "TheResultIsAsItWas" in broken_by(state, 4, True))
        self.assertEqual((5, 0, 5, 4, "ended", 4), short)

    def test_the_bar_is_not_passed_whatever_the_job_writes(self):
        # The job's writing has no size in the claim: in worlds
        # where the job may write 3 to 60, the most the reader
        # with the bar holds is the lesser of the bar and what
        # was written, and the reader as it was holds it all.
        for most in (3, 9, 24, 60):
            world = collections.OrderedDict(WORLD, MaxWrite=most)
            for bounded, top in ((True, min(most, WORLD["Keep"])),
                                 (False, most)):
                seen, queue = set(), collections.deque(
                    [(0, 0, 0, 0, "running", -1)])
                while queue:
                    state = queue.popleft()
                    if state in seen:
                        continue
                    seen.add(state)
                    queue.extend(steps(state, WORLD["Keep"], bounded, world))
                self.assertEqual(top, max(state[3] for state in seen),
                                 (most, bounded))

    def test_the_files_state_the_world_the_twin_walks(self):
        with open(os.path.join(MODELS.PROOFS, "held.tla"),
                  encoding="utf-8") as handle:
            model = handle.read()
        for name in INVARIANTS:
            self.assertRegex(model, r"(?m)^%s ==" % name)
        self.assertIn("CONSTANTS MaxWrite, PipeRoom, Chunk, Cap, Keep, "
                      "Bounded", model)
        for cfg, (bounded, keep, invariants) in sorted(
                CONFIGURATIONS.items()):
            constants, stated = cfg_of(cfg)
            wanted = {key: str(value) for key, value in WORLD.items()}
            wanted["Keep"] = str(keep)
            wanted["Bounded"] = "TRUE" if bounded else "FALSE"
            self.assertEqual(wanted, constants, cfg)
            self.assertEqual(list(invariants), stated, cfg)

    def test_each_witness_names_an_invariant_its_world_breaks(self):
        for cfg, (bounded, keep, invariants) in sorted(
                CONFIGURATIONS.items()):
            broken = walk(keep, bounded)[3]
            if "witness" in cfg:
                self.assertEqual(1, len(invariants), cfg)
                self.assertIn(invariants[0], broken, cfg)
            else:
                for name in invariants:
                    self.assertNotIn(name, broken, (cfg, name))


class ThePageRecordsTheModel(unittest.TestCase):
    """The figures of the model on the page are this module's."""

    def test_the_page_states_the_rule_the_bar_and_the_checker_s_word(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "**The rule.** The runner holds at most a fixed number of "
                "bytes of each stream of a job, whatever the job writes.",
                "4 bytes for each character of the output cap, and 4 more",
                "295 distinct states among 665 generated, to a depth of 19",
                "| `heldbar.cfg` | with the bar | 7 invariants hold on all "
                "295 states |",
                "| `heldasitwas.cfg` | as it was | the 6 that are not the "
                "bar hold |",
                "a job writes 10 and all 10 are held, past a bar of 9",
                "a job writes 5 and its result carries 4",
                "breaks the bar on 165 of its 295 states"):
            self.assertIn(stated, page, stated)
        self.assertEqual((7, 6), (
            len(CONFIGURATIONS["heldbar.cfg"][2]),
            len(CONFIGURATIONS["heldasitwas.cfg"][2])))
        # The bar with the log on at its default size.
        self.assertIn("33,816,576 bytes a stream", page)
        self.assertEqual(33816576, 33554432 + 4 * 65536)


if __name__ == "__main__":
    unittest.main()
