#!/usr/bin/env python3
"""Version 4 on a ladder: a fault found by the proof becomes a
technique of the proof.

docs/infrastructure-documents/proofs/v4-the-ladder.md takes the
technique from finding F14. Sizes stand on the Fibonacci series
from 0. Each step is the 2 steps before it, joined, and each
step has 3 kinds of data: what the constraints decide with
nothing run (the data before), what the 2 steps before it
forecast (the data ahead), and what the run shows from inside
(the data inside). This module holds the ladder and runs it in
6 places:

  the series      31 steps to the cap, and the ratio that reads
                  the law a quantity follows
  the operations  M joined by rule, the 14 kinds of row, and the
                  real bash with its trace of which commands ran
  the bars        the shell's 2 bars, met by rule
  the gate        every text a sender controls, timed and counted
                  at each step, and finding F14 found again by
                  the ladder with nobody pointing at it
  finding F15     3 shapes of a mail that the gate had no answer
                  for, met by the ladder in front of the
                  signature: the gate now refuses them, marked
  the fuzzers     the readers the fuzz driver holds, climbed from
                  their own seeds past the driver's ceiling of
                  16,384 bytes

The machine M, the atoms and the harnesses are the first rung's
(test_v4_at_a_bound.py) and the limit's (test_v4_at_a_limit.py).
The whole measure is on the page.
"""
import collections
import contextlib
import copy
import io
import itertools
import os
import statistics
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner as RUNNER  # noqa: E402
from runner.oracle import opinion as OPINION  # noqa: E402
from runner.tests import test_v4_at_a_bound as RUNG  # noqa: E402
from runner.tests import test_v4_at_a_limit as LIMIT  # noqa: E402
from runner.tests import test_v4_before_the_mac as PRE  # noqa: E402
from runner.tests import test_v4_bindings as BIND  # noqa: E402
from runner.tests import test_proof_conformance as DOOR  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-ladder.md")
ATOMS = RUNG.ATOMS
JOINERS = RUNG.JOINERS
AND, OR, SEMI, PIPE = JOINERS
CAP = LIMIT.CAP
JOB_DOOR = LIMIT.JOB_DOOR
GOLDEN = (1 + 5 ** 0.5) / 2
POSIX = os.name != "nt"
LINUX = sys.platform.startswith("linux")


# ---- The series

def series(top):
    """0, 1, 1, 2, 3, 5 and on, up to the first number over
    `top`."""
    steps = [0, 1]
    while steps[-1] <= top:
        steps.append(steps[-1] + steps[-2])
    return steps


def ratio_for(power):
    """Where the ratio of a step's value to the sum of the 2
    values before settles, for a quantity that grows as the
    size to the power `power`."""
    return 1 / (GOLDEN ** -power + GOLDEN ** (-2 * power))


def ratios(values):
    """Each step's value over the sum of the 2 before it."""
    return [values[at] / (values[at - 1] + values[at - 2])
            for at in range(2, len(values))
            if values[at - 1] + values[at - 2]]


def differences(values):
    """Each step's value, less the 2 values before it. For a
    quantity that is so much for each character and a fixed
    amount besides, this is the same number at every step."""
    return [values[at] - values[at - 1] - values[at - 2]
            for at in range(2, len(values))]


def ratios_apart(values, apart=3):
    """Each step's value over the value `apart` steps before
    it. Every third number of the series is even, so 3 steps
    apart the series keeps its parity, and a quantity with 1
    law for an even size and another for an odd size is read
    inside each of its 2 classes."""
    return [values[at] / values[at - apart]
            for at in range(apart, len(values)) if values[at - apart]]


# ---- M joined by rule

STATES = [(0, True), (1, True), (0, False), (1, False)]
WAYS_IN = [(status, running, joiner)
           for status, running in STATES for joiner in JOINERS]


def table_of_atom(atom, table):
    """What 1 atom does to what follows it. For each state M
    may be in and each joiner that may stand in front of the
    atom: what becomes of the output in hand ("emit" or
    "drop"), what is printed, the status, whether the pipeline
    in hand runs, the output in hand after, and the atoms that
    ran."""
    printed, status = table[atom]
    ran = collections.Counter({atom: 1})
    idle = collections.Counter()
    made = {}
    for was, running, joiner in WAYS_IN:
        if joiner == SEMI:
            made[(was, running, joiner)] = (
                "emit", "", status, True, printed, ran)
        elif joiner == PIPE:
            if running:
                # The command in front of a pipe is read by
                # nobody: its output is dropped.
                made[(was, running, joiner)] = (
                    "drop", "", status, True, printed, ran)
            else:
                made[(was, running, joiner)] = (
                    "emit", "", was, False, "", idle)
        elif (was == 0) == (joiner == AND):
            made[(was, running, joiner)] = (
                "emit", "", status, True, printed, ran)
        else:
            made[(was, running, joiner)] = (
                "emit", "", was, False, "", idle)
    return made


def join(first, joiner, second):
    """The table of `first joiner second`, from the 2 tables
    and nothing else: no walk through either row."""
    made = {}
    for way in WAYS_IN:
        _mode1, out1, status1, running1, hand1, ran1 = first[way]
        mode2, out2, status2, running2, hand2, ran2 = second[
            (status1, running1, joiner)]
        made[way] = (first[way][0],
                     out1 + (hand1 if mode2 == "emit" else "") + out2,
                     status2, running2, hand2, ran1 + ran2)
    return made


def result_of(row_table):
    """A row as a whole script: (output, status, atoms that
    ran)."""
    _mode, printed, status, _running, hand, ran = row_table[
        (0, True, SEMI)]
    return printed + hand, status, ran


def kind_of(row_table):
    """The part of a row's table that M's state sees: for each
    of the 16 ways in, the state the row leaves."""
    return tuple((row_table[way][2], row_table[way][3]) for way in WAYS_IN)


def table_of_row(atoms, joiners, table):
    made = table_of_atom(atoms[0], table)
    for joiner, atom in zip(joiners, atoms[1:]):
        made = join(made, joiner, table_of_atom(atom, table))
    return made


def walk(atoms, joiners, table):
    """M's walk through a row, with the atoms that ran:
    (output, status, ran)."""
    ran = collections.Counter({atoms[0]: 1})
    hand, status = table[atoms[0]]
    running, out = True, []
    for joiner, atom in zip(joiners, atoms[1:]):
        printed, after = table[atom]
        if joiner == SEMI:
            out.append(hand)
            hand, status, running = printed, after, True
            ran[atom] += 1
        elif joiner == PIPE:
            if running:
                hand, status = printed, after
                ran[atom] += 1
        else:
            out.append(hand)
            if (status == 0) == (joiner == AND):
                hand, status, running = printed, after, True
                ran[atom] += 1
            else:
                hand, running = "", False
    out.append(hand)
    return "".join(out), status, ran


WAYS_TO_JOIN = list(JOINERS) + ["in turn"]


def joiner_at(way, step):
    """The joiner between the 2 parts at a step: 1 joiner at
    every step, or the 4 in turn."""
    return JOINERS[step % 4] if way == "in turn" else way


def family(first, second, way, top, table):
    """A family of rows on the series. Step 1 is the atom
    `first` and step 2 is the atom `second`. Each later step
    is the step before, a joiner, and the step before that.
    Yields (step, atoms, joiners, the row's table)."""
    rows = {1: ((first,), ()), 2: ((second,), ())}
    tables = {1: table_of_atom(first, table),
              2: table_of_atom(second, table)}
    yield 1, rows[1][0], rows[1][1], tables[1]
    yield 2, rows[2][0], rows[2][1], tables[2]
    for step in range(3, top + 1):
        joiner = joiner_at(way, step)
        rows[step] = (rows[step - 1][0] + rows[step - 2][0],
                      rows[step - 1][1] + (joiner,) + rows[step - 2][1])
        tables[step] = join(tables[step - 1], joiner, tables[step - 2])
        yield step, rows[step][0], rows[step][1], tables[step]
        del rows[step - 2], tables[step - 2]


def kinds(table):
    """Every kind a row can be by what it does to M's state:
    the 22 atoms, closed under joining. {kind: a shortest row
    of that kind}."""
    found = {}
    for atom in ATOMS:
        found.setdefault(kind_of(table_of_atom(atom, table)),
                         ((atom,), ()))
    grew = True
    while grew:
        grew = False
        for left, right in itertools.product(list(found.values()),
                                             repeat=2):
            for joiner in JOINERS:
                made = kind_of(join(table_of_row(left[0], left[1], table),
                                    joiner,
                                    table_of_row(right[0], right[1], table)))
                if made not in found:
                    found[made] = (left[0] + right[0],
                                   left[1] + (joiner,) + right[1])
                    grew = True
    return found


# ---- The real shell, with its trace: the data inside

def traced(scripts, cwd):
    """Run every script in 1 bash process, each in a subshell
    of its own with the trace on: [(output, status, the
    trace's lines counted)], in the order given."""
    lines = []
    for index, script in enumerate(scripts):
        lines.append(
            "printf '\\036%%d\\037' %d; printf '\\036%%d\\037' %d >&2; "
            "( set -x; %s ); printf '\\035%%d\\034' $?\n"
            % (index, index, script))
    path = os.path.join(cwd, "..", "driver.sh")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.writelines(lines)
    done = subprocess.run(RUNG.BASH + [path], cwd=cwd, env=RUNG.ENV,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if done.returncode != 0:
        raise AssertionError(done.stderr[-300:])
    outputs, traces = {}, {}
    for part in done.stdout.decode("utf-8").split("\036")[1:]:
        index, rest = part.split("\037", 1)
        body, tail = rest.rsplit("\035", 1)
        outputs[int(index)] = (body, int(tail.rstrip("\034")))
    for part in done.stderr.decode("utf-8").split("\036")[1:]:
        index, rest = part.split("\037", 1)
        traces[int(index)] = collections.Counter(
            line for line in rest.split("\n") if line)
    return [(outputs[index][0], outputs[index][1],
             traces.get(index, collections.Counter()))
            for index in range(len(scripts))]


def trace_ahead(ran, signatures):
    """The trace forecast for a row: the trace of each atom
    that M says runs, as the shell showed it alone."""
    total = collections.Counter()
    for atom, times in ran.items():
        for line, count in signatures[atom].items():
            total[line] += times * count
    return total


# ---- The data before, for a row in the shell

PIPE_HELD, PIPE_OVER = 3330, 3333
LIST_HELD, LIST_OVER = 26000, 26210


def before_the_shell(joiners):
    """What the 2 bars of v4-at-a-limit.md decide about a row
    with nothing run, on the bash and the stack that page
    names: "M's result", "refused", "ended", or "at a bar"."""
    longest = run = 1
    for joiner in joiners:
        run = run + 1 if joiner == PIPE else 1
        longest = max(longest, run)
    entries = 1 + sum(1 for joiner in joiners if joiner != PIPE)
    if longest > PIPE_OVER:
        return "refused"
    if entries > LIST_OVER:
        return "ended"
    if longest > PIPE_HELD or entries > LIST_HELD:
        return "at a bar"
    return "M's result"


# ---- The gate on the ladder

def words(first, second, top):
    """(step, text): the empty text, the 2 units, then each
    text is the 2 texts before it, joined."""
    yield 0, ""
    yield 1, first
    yield 2, second
    older, newer = first, second
    for step in range(3, top + 1):
        older, newer = newer, newer + older
        yield step, newer


PLACES = ("script", "subject, a word in it", "subject, in front",
          "subject, behind", "sender", "note above", "note below")


def mail(place, text, payload, job_id, turned=False):
    """The mail that carries `text` in 1 place a sender
    controls. `turned` turns 1 digit of the signature, so the
    message fails there and all of its work is in front of
    it."""
    def head(subject, sender):
        return ("Subject: %s\r\nFrom: %s\r\nMIME-Version: 1.0\r\n"
                "Content-Type: text/plain; charset=utf-8\r\n"
                "Content-Transfer-Encoding: 8bit\r\n\r\n"
                % (subject, sender)).encode("utf-8", "surrogatepass")
    plain = "[HOMING-PIGEON] job %s" % job_id
    job = copy.deepcopy(payload)
    if place == "script":
        job["script"] = text
    signed = BIND._signed(job)
    body = (PRE._turned(signed) if turned else signed).encode(
        "utf-8", "surrogatepass")
    note = text.encode("utf-8", "surrogatepass")
    if place == "script":
        return head(plain, "si@example.com") + body
    if place == "subject, a word in it":
        return head("[HOMING-PIGEON] %s job %s" % (text, job_id),
                    "si@example.com") + body
    if place == "subject, in front":
        return head("%s %s" % (text, plain), "si@example.com") + body
    if place == "subject, behind":
        return head("%s %s" % (plain, text), "si@example.com") + body
    if place == "sender":
        return head(plain, text + "@example.com") + body
    if place == "note above":
        return head(plain, "si@example.com") + note + b"\n" + body
    if place == "note below":
        return head(plain, "si@example.com") + body + b"\n" + note
    raise KeyError(place)


def before_the_gate(place, text, raw):
    """What the 2 doors decide about a mail with nothing run."""
    if len(raw) > JOB_DOOR:
        return "over the job door"
    if place == "script" \
            and len(text.encode("utf-8", "surrogatepass")) > CAP:
        return "over the size door"
    return "under both doors"


def inside_the_gate(raw, repeats=3):
    """1 arrival at the real gate, with the execution a stub:
    (seconds, the gate's own counts, whether the job ran)."""
    best = None
    for _repeat in range(repeats):
        with tempfile.TemporaryDirectory() as folder:
            began = time.perf_counter()
            out = PRE.arrive(raw, folder)
            took = time.perf_counter() - began
        if best is None or took < best[0]:
            best = (took, out)
    took, out = best
    counts = {"parsed": out.count.parsed, "hashed": out.count.hashed,
              "macs": out.count.macs,
              "logged": sum(len(note) for note in out.notes),
              "lines": len(out.notes)}
    return took, counts, len(out.executed) == 1


def gate_ladder(place, first, second, top, payload, job_id,
                turned=False, budget=2.0):
    """Climb 1 family through the gate. At each step: the data
    before (the doors), the data ahead (the 2 times before it,
    added), and the data inside (the time and the counts). The
    climb stops when a step takes more than `budget` seconds,
    or when the data ahead says the next one will."""
    rows, times = [], {}
    for step, text in words(first, second, top):
        raw = mail(place, text, payload, job_id, turned)
        size = len(text.encode("utf-8", "surrogatepass"))
        ahead = times[step - 1] + times[step - 2] if step >= 3 else None
        took, counts, ran = inside_the_gate(
            raw, 3 if size < 60000 else (2 if size < 400000 else 1))
        times[step] = took
        rows.append({"step": step, "size": size, "mail": len(raw),
                     "before": before_the_gate(place, text, raw),
                     "ahead": ahead, "inside": took,
                     "ratio": took / ahead if ahead else None,
                     "counts": counts, "ran": ran, "stopped": ""})
        if took > budget:
            rows[-1]["stopped"] = "over the budget"
            break
        if ahead and step < top and max(took / ahead, 1.0) \
                * (took + times[step - 1]) > budget * 1.5:
            rows[-1]["stopped"] = "the next step is forecast over the budget"
            break
    return rows


SHAPES = ("colons in the sender", "comments nested in the sender",
          "parts nested")


def shaped(shape, count, body, job_id):
    """A mail with 1 of the 3 shapes of finding F15, `count`
    levels deep, around a body."""
    subject = "Subject: [HOMING-PIGEON] job %s\r\n" % job_id
    text = ("Content-Type: text/plain; charset=utf-8\r\n"
            "Content-Transfer-Encoding: 8bit\r\n\r\n" + body)
    if shape == "colons in the sender":
        sender = ":" * count + "@example.com"
    elif shape == "comments nested in the sender":
        sender = "(" * count + ")" * count + " si@example.com"
    else:
        sender = "si@example.com"
        for level in range(count):
            text = ('Content-Type: multipart/mixed; boundary="b%d"\r\n'
                    "\r\n--b%d\r\n%s\r\n--b%d--\r\n"
                    % (level, level, text, level))
    return (subject + "From: %s\r\nMIME-Version: 1.0\r\n" % sender
            + text).encode("utf-8")


class Mailbox:
    """A mailbox that keeps the seen mark and counts how often
    each mail is fetched, for whole polls."""

    def __init__(self, raws):
        self.raws = list(raws)
        self.seen = set()
        self.fetched = [0] * len(self.raws)

    def search(self, *_args):
        unseen = [str(at + 1).encode() for at in range(len(self.raws))
                  if at not in self.seen]
        return "OK", [b" ".join(unseen)]

    def fetch(self, number, _what):
        self.fetched[int(number) - 1] += 1
        return "OK", [(None, self.raws[int(number) - 1])]

    def store(self, number, *_args):
        self.seen.add(int(number) - 1)
        return "OK", None

    def expunge(self):
        return "OK", None

    def logout(self):
        return "OK", None


class _Once:
    workers = 1
    once = True
    dry_run = False
    verbose = False
    no_send = True
    inspect = False
    oracle = False
    pdb = False


def polls(raws, count):
    """Whole polls over a mailbox: (the mailbox, the jobs that
    ran, the log's lines)."""
    box, ran, notes = Mailbox(raws), [], []

    def execute(_cfg, job, _base):
        ran.append(job.get("job_id"))
        return dict(DOOR._OK_RESULT)

    with tempfile.TemporaryDirectory() as folder:
        cfg = {"mailbox_user": "t@example.com", "base_dir": folder,
               "oracle_opinion_mode": "off"}
        cfg.update(BIND.KEYS)
        RUNNER._set_allow_cleartext_jobs(True)
        try:
            with mock.patch.object(RUNNER, "execute_job", execute), \
                    mock.patch.object(RUNNER, "send_mail",
                                      lambda *_a, **_k: None), \
                    mock.patch.object(
                        RUNNER, "log",
                        lambda msg, level="INFO": notes.append(msg)), \
                    contextlib.redirect_stdout(io.StringIO()):
                seen = {}
                for _poll in range(count):
                    RUNNER.poll_once(cfg, folder, seen,
                                     os.path.join(folder, "seen.json"),
                                     imap=box, smtp=DOOR._SMTP2(),
                                     opts=_Once())
        finally:
            RUNNER._set_allow_cleartext_jobs(False)
    return box, ran, notes


def reading(rows, floor=0.003):
    """The law the time follows: the middle ratio of the last
    steps whose time is above the clock's noise."""
    kept = [row["ratio"] for row in rows
            if row["ratio"] and row["inside"] >= floor
            and row["before"] == "under both doors"][-5:]
    return statistics.median(kept) if len(kept) >= 2 else None


# ---- The readers the fuzz driver holds, on the ladder

def texts_of(value, path=()):
    """Where a seed carries a text: the path to each."""
    if isinstance(value, str):
        yield path
    elif isinstance(value, dict):
        for key, inner in value.items():
            yield from texts_of(inner, path + (key,))
    elif isinstance(value, list):
        for at, inner in enumerate(value):
            yield from texts_of(inner, path + (at,))


def grown(data, path, text):
    """A seed's data with `text` put behind the text at
    `path`."""
    if not path:
        return data + text
    made = copy.deepcopy(data)
    at = made
    for key in path[:-1]:
        at = at[key]
    at[path[-1]] = at[path[-1]] + text
    return made


def reader_ladder(dust, name, seed, path, unit, top=24, budget=2.0):
    """Climb 1 reader the fuzz driver holds, from 1 of its own
    seeds: the growing text is put behind the text at `path`.
    The reader is asked through the driver's own check, which
    clears what a try leaves behind. The data inside is the
    driver's verdict and the time. The driver makes no input
    over 16,384 bytes. Step 24 is 46,368."""
    steps = series(10 ** 9)
    rows, times = [], {}
    for step in range(top + 1):
        entry = dust.make_entry(
            seed["kind"], grown(seed["data"], path, unit * steps[step]),
            "ladder", "ladder")
        began = time.perf_counter()
        try:
            verdict = str(dust.check(name, entry))
        except dust.Crash as broken:
            verdict = "contract: %s" % broken.kind
        except Exception as raised:  # the ladder sees every outcome
            verdict = "raised: %s" % type(raised).__name__
        times[step] = time.perf_counter() - began
        ahead = times[step - 1] + times[step - 2] if step >= 2 else None
        rows.append({"step": step, "size": steps[step] * len(unit),
                     "verdict": verdict, "time": times[step],
                     "ratio": times[step] / ahead if ahead else None})
        if times[step] > budget:
            break
    return rows


class TheSeries(unittest.TestCase):
    """The ladder's sizes, and the ratio that reads a law."""

    def test_31_steps_pass_the_cap(self):
        steps = series(CAP)
        self.assertEqual([0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55], steps[:11])
        self.assertEqual((31, 832040, 1346269),
                         (len(steps) - 1, steps[30], steps[31]))
        # The owner's first rung, 50, holds the first 10 steps,
        # and his 3 rungs each lie between 2 steps.
        self.assertEqual(10, sum(1 for size in steps if size < 50))
        for rung in (50, 500, 5000):
            under = max(size for size in steps if size < rung)
            over = min(size for size in steps if size > rung)
            self.assertLess(over / under, 1.62)
        # Past 13, no step is more than 1.62 times the step
        # below it.
        self.assertTrue(all(steps[at] / steps[at - 1] < 1.62
                            for at in range(8, len(steps))))

    def test_the_ratio_reads_the_law_a_quantity_follows(self):
        steps = series(CAP)
        want = {0: 0.50, 1: 1.00, 2: 1.89, 3: 3.43}
        for power, stated in want.items():
            self.assertAlmostEqual(stated, ratio_for(power), places=2)
            values = [size ** power for size in steps]
            for got in ratios(values)[18:]:
                self.assertAlmostEqual(ratio_for(power), got, delta=0.01)
        # The sharper test, for a quantity counted exactly: so
        # much for each character and a fixed amount besides
        # gives the same difference at every step.
        fixed = [7 * size + 495 for size in steps]
        self.assertEqual({-495}, set(differences(fixed)))
        self.assertEqual({-293}, set(differences([293] * len(steps))))
        square = differences([size * size for size in steps])[10:]
        self.assertTrue(all(later > earlier
                            for earlier, later in zip(square, square[1:])))

    def test_a_law_in_2_classes_is_read_3_steps_apart(self):
        steps = series(CAP)
        self.assertEqual([0, 1, 1] * 10 + [0, 1],
                         [size % 2 for size in steps])
        # 10 for an even size and 4 for an odd size: each
        # class is in proportion, and the plain ratio does not
        # settle. It runs 2.50, 0.52, 0.64, and round again.
        # That is what the gate showed for quotes in the
        # sender's address, where the mail library makes 10
        # calls a quote for an even count and 4 for an odd.
        values = [(10 if size % 2 == 0 else 4) * size for size in steps]
        self.assertEqual([0.64, 2.5, 0.52, 0.64, 2.5, 0.52],
                         [round(got, 2) for got in ratios(values)[-6:]])
        for got in ratios_apart(values)[-9:]:
            self.assertAlmostEqual(GOLDEN ** 3, got, delta=0.01)
        # 3 steps apart, by the law a quantity follows.
        for power, stated in {0: 1.00, 1: 4.24, 2: 17.94, 3: 76.01}.items():
            settled = GOLDEN ** (3 * power)
            self.assertAlmostEqual(stated, settled, places=2)
            values = [size ** power for size in steps]
            for got in ratios_apart(values)[18:]:
                self.assertAlmostEqual(settled, got, delta=settled * 0.001)

    def test_the_series_falls_on_every_phase_of_a_reader_that_grows(self):
        # A reader that takes looks 4 times as long each time
        # is in step with a ladder of 4s, and nearly so with a
        # ladder of 10s. The series' step is 1.618, so its
        # sizes fall on every part of the reader's cycle.
        import math

        def phases(sizes):
            return sorted(math.log(size / 32, 4) % 1 for size in sizes)

        on_the_series = phases(series(CAP)[10:31])
        self.assertEqual(21, len(on_the_series))
        gaps = [later - earlier for earlier, later
                in zip(on_the_series, on_the_series[1:])]
        gaps.append(1 + on_the_series[0] - on_the_series[-1])
        self.assertLess(max(gaps), 0.15)
        on_the_rungs = phases([50, 500, 5000])
        gaps = [later - earlier for earlier, later
                in zip(on_the_rungs, on_the_rungs[1:])]
        gaps.append(1 + on_the_rungs[0] - on_the_rungs[-1])
        self.assertGreater(max(gaps), 0.3)
        # The costly phase is just past a power of 4. The 3
        # rungs have no size there, and the series has.
        self.assertFalse(any(phase < 0.1 for phase in on_the_rungs))
        self.assertTrue(any(phase < 0.1 for phase in on_the_series))
        self.assertEqual({0.0}, {round(math.log(size / 32, 4) % 1, 9)
                                 for size in (32, 128, 512, 2048)})


class MJoinedByRule(unittest.TestCase):
    """The data ahead for the operations: a row's table, and
    the table of 2 rows joined."""

    @classmethod
    def setUpClass(cls):
        cls.table = RUNG.denotation("/where/the/job/runs", "/its/home")

    def test_the_joined_table_gives_the_walk_s_result(self):
        rows = 0
        for first in ATOMS:
            for second in ATOMS:
                for way in WAYS_TO_JOIN:
                    for step, atoms, joiners, made in family(
                            first, second, way, 13, self.table):
                        if step < 3:
                            continue
                        rows += 1
                        got = walk(atoms, joiners, self.table)
                        self.assertEqual(result_of(made), got,
                                         (first, second, way, step))
                        self.assertEqual(
                            RUNG.run(atoms, joiners, self.table), got[:2])
        self.assertEqual(22 * 22 * 5 * 11, rows)
        self.assertEqual(26620, rows)

    def test_every_row_is_1_of_14_kinds(self):
        found = kinds(self.table)
        self.assertEqual(14, len(found))
        # The 2 kinds of atom, by status, and nothing else from
        # 1 atom.
        alone = {kind_of(table_of_atom(atom, self.table)) for atom in ATOMS}
        self.assertEqual(2, len(alone))
        # Closed: 2 kinds joined give a kind of the 14, in all
        # 784 cases.
        cases = 0
        for left, right in itertools.product(found.values(), repeat=2):
            for joiner in JOINERS:
                cases += 1
                made = join(table_of_row(left[0], left[1], self.table),
                            joiner,
                            table_of_row(right[0], right[1], self.table))
                self.assertIn(kind_of(made), found)
        self.assertEqual(784, cases)
        # Every row of a sample is of 1 of them.
        for row in RUNG.rows(max_chars=16):
            self.assertIn(
                kind_of(table_of_row(row[0], row[1], self.table)), found)

    def test_2_forms_of_the_join_written_apart_agree(self):
        # test_v4_the_ladder.py is another seat's L2, with its
        # own form for a row's table: what becomes of the
        # output in hand, what the row prints, and the state
        # it leaves. Neither form was written from the other.
        # They are asked the join of every 2 atoms by every
        # joiner, entered in each of the 16 ways.
        from runner.tests import test_v4_the_ladder as other
        table = RUNG.denotation("/work", "/home")
        self.assertEqual(table, other.DEN)
        asked = 0
        for first in ATOMS:
            for second in ATOMS:
                for joiner in JOINERS:
                    mine = join(table_of_atom(first, table), joiner,
                                table_of_atom(second, table))
                    theirs = other.compose(other.atom_table(first),
                                           other.atom_table(second), joiner)
                    # As a whole script: the same output and status.
                    self.assertEqual(
                        result_of(mine)[:2],
                        other.printed(other.join_end(
                            other.leaf_end(first),
                            other.atom_table(second), joiner)),
                        (first, joiner, second))
                    for status, running, front in WAYS_IN:
                        asked += 1
                        _mode, _printed, left, runs, _hand, _ran = \
                            mine[(status, running, front)]
                        cell = theirs[(status, running)][front]
                        self.assertEqual(
                            (left, runs), (cell[3], cell[4]),
                            (first, joiner, second, status, running, front))
        self.assertEqual(30976, asked)
        # And the count of kinds, each form's own way.
        found = {other.kind_of(other.atom_table(atom)) for atom in ATOMS}
        horizon = list(found)
        while horizon:
            current = horizon.pop()
            for known in list(found):
                for joiner in JOINERS:
                    for made in (other.compose_kind(current, known, joiner),
                                 other.compose_kind(known, current, joiner)):
                        if made not in found:
                            found.add(made)
                            horizon.append(made)
        self.assertEqual((14, 14), (len(found), len(kinds(table))))

    def test_a_step_s_forecast_does_not_walk_the_row(self):
        # Step 30 of a ladder of colons is a row of 832,040
        # atoms. Its table is 28 joins of tables, and says what
        # the row does: every colon runs, or only the first.
        began = time.monotonic()
        for joiner, runs in ((SEMI, 832040), (AND, 832040), (PIPE, 832040),
                             (OR, 1)):
            for step, atoms, _joiners, made in family(
                    ":", ":", joiner, 30, self.table):
                last = (step, len(atoms), result_of(made))
            self.assertEqual(
                (30, 832040, ("", 0, collections.Counter({":": runs}))),
                last, joiner)
        self.assertLess(time.monotonic() - began, 30.0)


@unittest.skipIf(not POSIX, "POSIX only")
class TheShellOnTheLadder(unittest.TestCase):
    """The data inside for the operations: the real bash's
    output, its status, and its trace of which commands ran."""

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.cwd = os.path.join(cls.folder.name, "cwd")
        os.mkdir(cls.cwd)
        cls.table = RUNG.denotation(os.path.realpath(cls.cwd),
                                    RUNG.ENV["HOME"])
        got = traced(list(ATOMS), cls.cwd)
        cls.signatures = {atom: trace
                          for atom, (_out, _status, trace)
                          in zip(ATOMS, got)}

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def ahead(self, row_table):
        printed, status, ran = result_of(row_table)
        return printed, status, trace_ahead(ran, self.signatures)

    def leaves(self, asked):
        """The rows whose run leaves the data ahead."""
        got = traced([script for script, _ahead in asked], self.cwd)
        return [script[:80] for (script, ahead), shown in zip(asked, got)
                if shown != ahead]

    def test_each_atom_alone_has_its_own_trace(self):
        self.assertEqual({"+ :": 1}, dict(self.signatures[":"]))
        self.assertEqual({"++ :": 1, "+ echo": 1},
                         dict(self.signatures["echo $(:)"]))
        self.assertEqual({"+ true": 1, "+ echo a": 1},
                         dict(self.signatures["if true; then echo a; fi"]))
        self.assertTrue(all(self.signatures[atom] for atom in ATOMS))

    def test_the_trace_shows_what_the_output_cannot(self):
        # `false && : | :; :` prints nothing whatever runs. The
        # trace says that the pipeline did not run and the last
        # colon did.
        row = ("false", ":", ":", ":"), (AND, PIPE, SEMI)
        printed, status, trace = traced([RUNG.text(*row)], self.cwd)[0]
        self.assertEqual(("", 0), (printed, status))
        self.assertEqual({"+ false": 1, "+ :": 1}, dict(trace))
        self.assertEqual(self.ahead(table_of_row(row[0], row[1],
                                                 self.table)),
                         (printed, status, trace))

    def test_bash_shows_the_data_ahead_on_the_ladder(self):
        # Every 11th of the 2,420 families, at steps 3 to 10.
        asked, at = [], 0
        for first in ATOMS:
            for second in ATOMS:
                for way in WAYS_TO_JOIN:
                    at += 1
                    if at % 11:
                        continue
                    for step, atoms, joiners, made in family(
                            first, second, way, 10, self.table):
                        if step >= 3:
                            asked.append((RUNG.text(atoms, joiners),
                                          self.ahead(made)))
        self.assertEqual(220 * 8, len(asked))
        self.assertEqual([], self.leaves(asked))

    def test_the_join_holds_in_every_case(self):
        # The joining step, weighed whole at the level of
        # kinds: 14 kinds, 4 joiners, 14 kinds, entered in each
        # of the 16 ways, 12,544 rows. The representatives
        # print, so the output shows what ran as well as the
        # trace does.
        found = kinds(self.table)
        printers = ["echo a", "echo b", "echo c", "echo ok", "printf x",
                    "echo {a,b}", "echo $((1+2))", "pwd"]

        def speaking(row, shift):
            atoms, at = [], shift
            for atom in row[0]:
                if self.table[atom][1] == 0:
                    atoms.append(printers[at % len(printers)])
                    at += 1
                else:
                    atoms.append(atom)
            return tuple(atoms), row[1]

        asked = []
        for (left, right) in itertools.product(found.values(), repeat=2):
            left, right = speaking(left, 0), speaking(right, 3)
            for joiner in JOINERS:
                joined = join(
                    table_of_row(left[0], left[1], self.table), joiner,
                    table_of_row(right[0], right[1], self.table))
                for state in sorted(RUNG.INTO):
                    front = RUNG.INTO[state]
                    for way_in in JOINERS:
                        whole = join(
                            table_of_row(front[0], front[1], self.table),
                            way_in, joined)
                        script = RUNG.text(
                            front[0] + left[0] + right[0],
                            front[1] + (way_in,) + left[1] + (joiner,)
                            + right[1])
                        asked.append((script, self.ahead(whole)))
        self.assertEqual(14 * 4 * 14 * 16, len(asked))
        self.assertEqual([], self.leaves(asked))


@unittest.skipUnless(LINUX, "the shell's 2 bars are measured on Linux")
class TheBarsByRule(unittest.TestCase):
    """The shell's 2 bars, met on the ladder: the data before
    says which step is the first over each bar, and the run
    shows it."""

    def climb(self, joiner, top, stack_kb=None):
        table = RUNG.denotation("/where", "/home")
        shown = {}
        for step, atoms, joiners, made in family(":", ":", joiner, top,
                                                 table):
            if step < top - 2:
                continue
            out, err, status, _table = LIMIT.own_process(
                RUNG.text(atoms, joiners), stack_kb=stack_kb)
            printed, want, _ran = result_of(made)
            if (out, status) == (printed, want) and err == b"":
                shown[step] = "M's result"
            elif status == 2 and b"syntax error" in err:
                shown[step] = "refused"
            elif status < 0:
                shown[step] = "ended"
            else:
                shown[step] = "something else"
        return shown

    def test_the_pipe_ladder_meets_the_grammar_s_bar_at_step_19(self):
        if LIMIT.own_process(": | " * 19999 + ":", read_only=True)[2] == 0:
            self.skipTest("this bash reads a pipeline of 20,000 commands")
        steps = series(CAP)
        self.assertEqual((2584, 4181), (steps[18], steps[19]))
        self.assertEqual(
            ["M's result", "refused"],
            [before_the_shell((PIPE,) * (steps[step] - 1))
             for step in (18, 19)])
        if LIMIT.bash_version().startswith("5.2.21"):
            self.assertEqual({17: "M's result", 18: "M's result",
                              19: "refused"}, self.climb(PIPE, 19))

    def test_a_list_ladder_meets_the_stack_s_bar_by_a_signal(self):
        steps = series(CAP)
        self.assertEqual(
            ["M's result", "ended"],
            [before_the_shell((SEMI,) * (steps[step] - 1))
             for step in (22, 23)])
        # With 1 megabyte of stack the bar is 8 times nearer:
        # steps 15 and 16 are held, and step 20 is not.
        self.assertEqual("M's result", self.climb(SEMI, 16, 1024)[16])
        self.assertEqual("ended", self.climb(SEMI, 20, 1024)[20])


class TheGateOnTheLadder(unittest.TestCase):
    """The gate's own work, at every step from 0."""

    @classmethod
    def setUpClass(cls):
        cls.payload, cls.job_id = RUNG.honest_job()

    def climb(self, place, unit, top=24, turned=False, budget=2.0):
        return gate_ladder(place, unit, unit, top, self.payload, self.job_id,
                           turned=turned, budget=budget)

    def test_the_gate_reads_a_script_in_proportion(self):
        for unit in ("a", "\n", " \n", "\x01", '"', "{", "€"):
            rows = self.climb("script", unit)
            self.assertEqual(24, rows[-1]["step"], repr(unit))
            self.assertTrue(all(row["ran"] for row in rows), repr(unit))
            self.assertLess(reading(rows), 1.35, repr(unit))
            # The exact counts. The MAC is so much for each byte
            # and a fixed amount besides. The log is fixed.
            past = [row["counts"] for row in rows if row["size"] > 5000]
            self.assertEqual(
                1, len(set(differences([c["hashed"] for c in past]))),
                repr(unit))
            fixed = {(c["logged"], c["lines"], c["macs"]) for c in past}
            self.assertEqual(1, len(fixed), repr(unit))
            self.assertLess(max(c["logged"] for c in past), 1000)

    def test_the_ladder_finds_f14_with_nobody_pointing_at_it(self):
        # With the reader's patterns as they stood before the
        # change, the ladder of line ends stops itself: its own
        # forecast says the next step is over the budget. With
        # the patterns that stand now it climbs to the top.
        with mock.patch.object(OPINION, "_BASH_ONLY_RE",
                               LIMIT.WAS_BASH_ONLY), \
                mock.patch.object(OPINION, "_EXPORT_RE", LIMIT.WAS_EXPORT):
            was = self.climb("script", "\n", budget=0.5)
            plain = self.climb("script", "a", budget=0.5)
        now = self.climb("script", "\n", budget=0.5)
        self.assertLess(was[-1]["step"], 24)
        self.assertLess(was[-1]["size"], 100000)
        self.assertTrue(was[-1]["stopped"])
        self.assertGreater(reading(was), 1.5)
        self.assertEqual((24, ""), (now[-1]["step"], now[-1]["stopped"]))
        self.assertEqual((24, ""), (plain[-1]["step"], plain[-1]["stopped"]))
        self.assertLess(reading(now), 1.35)

    def test_in_front_of_the_signature_the_work_has_a_law(self):
        # A message that fails at the signature, with a script
        # of every size on the ladder: 1 MAC, 2 lines of 139
        # characters, and a parser that is given at most 10
        # thirds of the message.
        most = 0.0
        for unit in ("a", "\x01", "{"):
            rows = self.climb("script", unit, turned=True)
            self.assertFalse(any(row["ran"] for row in rows))
            self.assertEqual(
                1, len({row["counts"]["logged"] for row in rows}))
            for row in rows:
                counts = row["counts"]
                self.assertEqual((1, 2), (counts["macs"], counts["lines"]))
                self.assertLess(counts["logged"], 400)
                self.assertLessEqual(counts["hashed"], row["mail"])
                self.assertLessEqual(counts["parsed"],
                                     row["mail"] * 10 / 3 + 1000)
                if row["size"] > 5000:
                    most = max(most, counts["parsed"] / row["mail"])
        # The looks grow by 4, so the count is not the same at
        # every phase: the ladder sees more than 3 times the
        # message, which a few sizes in step with the looks do
        # not.
        self.assertGreater(most, 3.0)


class TheGateHasAnAnswerForEveryMail(unittest.TestCase):
    """Finding F15. 3 shapes of a mail made the gate raise in
    front of the signature, and a message that makes the gate
    raise is never marked: every poll read it again. The gate
    now decides each of them."""

    @classmethod
    def setUpClass(cls):
        cls.payload, cls.job_id = RUNG.honest_job()
        cls.signed = BIND._signed(cls.payload)

    def arrive(self, raw, stopped=False):
        with tempfile.TemporaryDirectory() as folder:
            if stopped:
                PRE.PANIC.arm(folder, " ".join(PRE.PANIC.WORDLIST[-6:]))
                PRE.PANIC.fire(folder)
            try:
                out = PRE.arrive(raw, folder)
            finally:
                if stopped:
                    PRE.PANIC._reset_for_tests()
            return out, PRE.kept(folder)

    def test_an_address_the_library_cannot_follow_does_not_stop_a_job(self):
        for shape, count in (("colons in the sender", 1200),
                             ("comments nested in the sender", 700)):
            out, _kept = self.arrive(
                shaped(shape, count, self.signed, self.job_id))
            self.assertEqual((1, 1), (len(out.executed), out.marks), shape)
            self.assertIn("submitted by (sender could not be read)",
                          out.notes[0])
            # The line that says so is of bounded length.
            self.assertLess(len(out.notes[0]), 400)
            # With a signature that fails, it is refused at the
            # signature like any other, with its 1 record.
            out, kept = self.arrive(shaped(
                shape, count, PRE._turned(self.signed), self.job_id))
            self.assertEqual((0, 1), (len(out.executed), out.marks), shape)
            self.assertIn("rejecting seq 3: bad signature: bad signature",
                          out.notes)
            self.assertIn(PRE.EVENTS, kept)

    def test_a_mail_nested_too_deep_to_read_is_refused_and_marked(self):
        for count in (1200, 20000):
            out, kept = self.arrive(
                shaped("parts nested", count, self.signed, self.job_id))
            self.assertEqual((0, 1), (len(out.executed), out.marks), count)
            self.assertEqual(
                ["seq 3: the mail's shape could not be read"],
                out.notes)
            self.assertEqual({}, kept)
        # Under what the library follows, the job runs.
        out, _kept = self.arrive(
            shaped("parts nested", 500, self.signed, self.job_id))
        self.assertEqual((1, 1), (len(out.executed), out.marks))

    def test_a_stopped_box_leaves_it_as_it_leaves_the_rest(self):
        out, kept = self.arrive(
            shaped("parts nested", 1200, self.signed, self.job_id),
            stopped=True)
        self.assertEqual((0, 0, []), (len(out.executed), out.marks,
                                      out.notes))

    def test_the_mailbox_is_asked_for_it_once(self):
        # 3 polls over 4 mails: a good job, a job whose sender's
        # address is 1,200 colons, a mail of parts nested 1,200
        # deep, and a good job. Each is fetched once and marked.
        jobs = []
        for at in range(4):
            job = copy.deepcopy(self.payload)
            job["job_id"] = "ladder-%d" % at
            jobs.append(BIND._signed(job))
        raws = [
            shaped("colons in the sender", 0, jobs[0], "ladder-0"),
            shaped("colons in the sender", 1200, jobs[1], "ladder-1"),
            shaped("parts nested", 1200, jobs[2], "ladder-2"),
            shaped("colons in the sender", 0, jobs[3], "ladder-3")]
        box, ran, notes = polls(raws, 3)
        self.assertEqual([1, 1, 1, 1], box.fetched)
        self.assertEqual({0, 1, 2, 3}, box.seen)
        self.assertEqual(["ladder-0", "ladder-1", "ladder-3"], sorted(ran))
        self.assertEqual([], [note for note in notes
                              if "worker raised" in note])

    def test_the_gate_returns_at_every_step_of_the_3_shapes(self):
        # The ladder that met the finding: each shape on the
        # series to step 19, 4,181 levels. The data inside is
        # that the gate returns, marks the message, and writes
        # lines of bounded length.
        steps = series(4181)
        self.assertEqual(4181, steps[19])
        for shape in SHAPES:
            ran = []
            for step in range(20):
                out, _kept = self.arrive(shaped(
                    shape, steps[step], self.signed, self.job_id))
                self.assertEqual(1, out.marks, (shape, step))
                self.assertLess(sum(len(note) for note in out.notes), 1000)
                ran.append(len(out.executed))
            if shape == "parts nested":
                # Read while the library follows the nesting,
                # refused past it.
                self.assertEqual([1] * 16, ran[:16], shape)
                self.assertEqual([0, 0], ran[18:], shape)
            else:
                self.assertEqual([1] * 20, ran, shape)


class TheFuzzersReadersOnTheLadder(unittest.TestCase):
    """The ladder's next place: the readers the fuzz driver
    holds to their contracts. The driver varies a shape at a
    size of at most 16,384 bytes. The ladder holds a shape and
    climbs its size."""

    def test_the_driver_s_ceiling_is_under_the_doors(self):
        from runner.tools import de_dust_corpus as dust
        self.assertEqual((16384, 16384), (dust.MAX_TEXT, dust.MAX_PAYLOAD))
        self.assertEqual(30, len(dust.TARGETS))
        steps = series(CAP)
        # The ceiling lies between steps 21 and 22, so the 9
        # steps from 22 to 30 are sizes under the cap that the
        # driver never makes. The cap is 64 times the ceiling
        # and the job door 256 times.
        self.assertLess(steps[21], dust.MAX_TEXT)
        self.assertGreater(steps[22], dust.MAX_TEXT)
        self.assertEqual(9, sum(1 for size in steps
                                if dust.MAX_TEXT < size <= CAP))
        self.assertEqual(64, CAP // dust.MAX_TEXT)
        self.assertEqual(256, JOB_DOOR // dust.MAX_TEXT)

    def test_4_readers_that_bar_a_long_text_decide_at_every_step(self):
        from runner.tools import de_dust_corpus as dust

        def climb_all():
            climbed = []
            for name in ("names", "address", "keydir", "stage"):
                target = dust.TARGETS[name]
                seed = next(seed for seed in target["seeds"]()
                            if list(texts_of(seed["data"])))
                for path in list(texts_of(seed["data"]))[:2]:
                    for unit in ("a", "\n", '"', "{"):
                        climbed.append((name, unit, reader_ladder(
                            dust, name, seed, path, unit)))
            return climbed

        # The driver asks its readers inside its own rig.
        climbed = dust._with_rig(climb_all)
        self.assertGreaterEqual(len(climbed), 16)
        for name, unit, rows in climbed:
            self.assertEqual(24, rows[-1]["step"], (name, unit))
            self.assertEqual(46368, rows[-1]["size"])
            for row in rows:
                self.assertIn(row["verdict"], ("accepted", "refused"),
                              (name, unit))
            # A bar on the text's length stands in front of the
            # reader's work, so the time does not rise.
            self.assertLess(max(row["time"] for row in rows), 0.5,
                            (name, unit))


class ThePageRecordsTheMeasure(unittest.TestCase):
    """The figures this module holds are the page's."""

    def test_the_page_states_what_was_counted_and_run(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "| is in proportion to the size | 1 | 1.00 |",
                "| grows with the square | 2 | 1.89 |",
                "| is in proportion to the size | 4.24 |",
                "| grows with the square | 17.94 |",
                "| Rows, steps 3 to 15 | 31,460 | 31,460 |",
                "| Kinds of row | 14 | 14 |",
                "26,620 rows, 0 differences",
                "30,976 cases",
                "**Every row is 1 of 14 kinds.**",
                "in all 784 cases",
                "| 2,420 families, steps 3 to 10 | 19,360 | 0 |",
                "each of the 16 ways in | 12,544 | 0 |",
                "| All | 44,588 | 0 |",
                "3,333 read, 3,334 refused",
                "signal 11 at step 23",
                "2,139 families",
                "168 families",
                "from 2.31 to 3.34 times the mail",
                "| Colons in the sender's address | 986 | 2,986 | 2,000 | 1 |",
                "| Parts nested inside parts | 981 | 2,981 | 2,000 | 1 |",
                "no input it makes is over 16,384 bytes",
                "That is 224 cases, whatever the size."):
            self.assertIn(stated, page, stated)
        self.assertEqual(31460, 22 * 22 * 5 * 13)
        self.assertEqual(30976, 22 * 22 * 4 * 16)
        self.assertEqual(26620, 22 * 22 * 5 * 11)
        self.assertEqual(19360, 2420 * 8)
        self.assertEqual(44588, 19360 + 140 + 2 * 12544)
        self.assertEqual((12544, 784, 224),
                         (14 * 4 * 14 * 16, 14 * 14 * 4, 14 * 16))
        self.assertEqual(2139, 3 * 167 + 9 * 182)
        self.assertEqual(168, 12 * 14)


if __name__ == "__main__":
    unittest.main()
