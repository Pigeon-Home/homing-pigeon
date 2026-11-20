#!/usr/bin/env python3
"""Version 4 at a limit: the first rung's claim with the size
left open.

docs/infrastructure-documents/proofs/v4-at-a-limit.md writes the
claim of v4-at-a-bound.md with the size as a number N, and names
the bars a row of atoms meets as N grows. This module holds 5
things:

  the count     rows at any N, and why a script is 1 row
  the formulas  what grows with N, against every row of at most
                22 characters
  the shell     the real bash past 50 characters: rows drawn
                evenly at every length from 50 to 500, every
                step of M at the end of a long row, the rows
                that strain it most, and the 2 bars the shell
                and the machine set
  the runner    the real gate and the real execution past 50,
                the output cap's cut, the 2 doors, and what a
                row over a bar gets
  the gate      finding F14: the reader of a script's shape
                answers as it did, and blank lines no longer
                hold the gate

The machine M, the shell harness and the runner harness are the
first rung's (test_v4_at_a_bound.py). The whole measure is on
the page. What runs here on every suite run is the part that
carries the argument past the first rung.
"""
import copy
import hashlib
import math
import os
import itertools
import random
import re
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.oracle import opinion as OPINION  # noqa: E402
from runner.tests import test_v4_at_a_bound as RUNG  # noqa: E402
from runner.tests import test_v4_before_the_mac as PRE  # noqa: E402
from runner.tests import test_v4_bindings as BIND  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-at-a-limit.md")
ATOMS = RUNG.ATOMS
JOINERS = RUNG.JOINERS
AND, OR, SEMI, PIPE = JOINERS
PAIRS = [(joiner, atom) for joiner in JOINERS for atom in ATOMS]
CAP = 1048576
JOB_DOOR = 4194304
KEPT = 100000
POSIX = os.name != "nt"
LINUX = sys.platform.startswith("linux")
# The shell legs are POSIX-only, as the first rung's are. The
# 2 bars are measured where the page measured them, on Linux:
# the system bash of macOS is another build with its own
# numbers.


# ---- The count at any N

def exact_counts(bound):
    """e[L]: how many rows are exactly L characters long. A row
    is an atom, or a shorter row with 1 joiner and 1 atom after
    it."""
    exact = [0] * (bound + 1)
    for length in range(1, bound + 1):
        count = sum(1 for atom in ATOMS if len(atom) == length)
        for joiner, atom in PAIRS:
            rest = length - len(joiner) - len(atom)
            if rest >= 1:
                count += exact[rest]
        exact[length] = count
    return exact


def growth():
    """The number each character multiplies the count by: the
    root x of the sum, over the 88 pairs of a joiner and an
    atom, of x to the power of minus the pair's length = 1."""
    low, high = 1.0, 4.0
    for _round in range(200):
        middle = (low + high) / 2
        if sum(middle ** -(len(joiner) + len(atom))
               for joiner, atom in PAIRS) > 1:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def draw_exact(length, exact, rng):
    """A row of exactly `length` characters, each such row as
    likely as any other: the count is walked backwards."""
    atoms, joiners = [], []
    while True:
        pick = rng.randrange(exact[length])
        alone = [atom for atom in ATOMS if len(atom) == length]
        if pick < len(alone):
            atoms.append(alone[pick])
            break
        pick -= len(alone)
        for joiner, atom in PAIRS:
            rest = length - len(joiner) - len(atom)
            if rest >= 1:
                if pick < exact[rest]:
                    atoms.append(atom)
                    joiners.append(joiner)
                    length = rest
                    break
                pick -= exact[rest]
    return tuple(reversed(atoms)), tuple(reversed(joiners))


def cuts(script):
    """Every (atoms, joiners) row whose text is the script."""
    found = []

    def walk(at, atoms, joiners):
        for atom in ATOMS:
            if script.startswith(atom, at):
                end = at + len(atom)
                if end == len(script):
                    found.append((atoms + (atom,), joiners))
                for joiner in JOINERS:
                    if script.startswith(joiner, end):
                        walk(end + len(joiner), atoms + (atom,),
                             joiners + (joiner,))
    walk(0, (), ())
    return found


# ---- What grows with N

def most_atoms(size):
    return (size + 2) // 3


def longest_pipeline(size):
    return (size + 3) // 4


def pipeline_of(joiners):
    """The most commands in 1 pipeline of a row."""
    best = run = 1
    for joiner in joiners:
        run = run + 1 if joiner == PIPE else 1
        best = max(best, run)
    return best


def most_output(size, table):
    """The most characters a row of at most `size` characters
    prints, and the atoms of a row that prints it (joined by
    semicolons). An atom of length L costs L + 2 of the
    size + 2 characters there are to spend."""
    gain = {}
    for atom in ATOMS:
        printed = len(table[atom][0])
        if printed > gain.get(len(atom), (0, None))[0]:
            gain[len(atom)] = (printed, atom)
    best = [(0, None)] * (size + 3)
    for room in range(1, size + 3):
        held = (best[room - 1][0], None)
        for length, (printed, atom) in gain.items():
            if length + 2 <= room \
                    and best[room - length - 2][0] + printed > held[0]:
                held = (best[room - length - 2][0] + printed, atom)
        best[room] = held
    room, atoms = size + 2, []
    while room > 0:
        atom = best[room][1]
        if atom is None:
            room -= 1
        else:
            atoms.append(atom)
            room -= len(atom) + 2
    return best[size + 2][0], tuple(atoms)


def first_cut(kept, table):
    """The first N at which some row prints more than `kept`
    characters."""
    low, high = 1, 1
    while most_output(high, table)[0] <= kept:
        low, high = high, high * 2
    while high - low > 1:
        middle = (low + high) // 2
        if most_output(middle, table)[0] > kept:
            high = middle
        else:
            low = middle
    return high


# ---- The real shell, 1 row as the only line of a file

def own_process(script, stack_kb=None, read_only=False):
    """The script as bash runs a job's file: (stdout, stderr,
    status). `stack_kb` sets the stack the shell is given, and
    `read_only` asks bash to read the row and not run it."""
    def room():
        if stack_kb is not None:
            import resource
            resource.setrlimit(resource.RLIMIT_STACK,
                               (stack_kb * 1024, stack_kb * 1024))
    with tempfile.TemporaryDirectory() as folder:
        cwd = os.path.join(folder, "cwd")
        os.mkdir(cwd)
        path = os.path.join(folder, "row.sh")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(script)
        done = subprocess.run(
            RUNG.BASH + (["-n"] if read_only else []) + [path],
            cwd=cwd, env=RUNG.ENV, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=room if stack_kb is not None else None)
        table = RUNG.denotation(os.path.realpath(cwd), RUNG.ENV["HOME"])
    return done.stdout.decode("utf-8", "replace"), done.stderr, \
        done.returncode, table


def agrees(atoms, joiners, stack_kb=None):
    """Whether bash, given the row as a file of its own, ends
    with M's output, M's status and a silent error stream."""
    out, err, status, table = own_process(RUNG.text(atoms, joiners),
                                          stack_kb)
    return (out, status) == RUNG.run(atoms, joiners, table) and err == b""


def strain(name, size):
    """The rows that ask the most of the shell at a size."""
    if name == "atoms":
        count = most_atoms(size)
        return (":",) * count, (SEMI,) * (count - 1)
    if name == "and":
        count = (size + 4) // 5
        return (":",) * count, (AND,) * (count - 1)
    if name == "or":
        count = (size + 4) // 9
        return ("false",) * count, (OR,) * (count - 1)
    if name == "pipeline":
        count = longest_pipeline(size)
        return (":",) * count, (PIPE,) * (count - 1)
    if name == "pairs":
        count = (size + 2) // 7
        return (":",) * (2 * count), tuple(
            PIPE if at % 2 == 0 else SEMI for at in range(2 * count - 1))
    if name == "output":
        count = (size + 2) // 5
        return ("pwd",) * count, (SEMI,) * (count - 1)
    if name == "subshells":
        count = (size + 2) // 10
        return ("(echo a)",) * count, (SEMI,) * (count - 1)
    raise KeyError(name)


def bash_version():
    done = subprocess.run(["bash", "-c", "echo $BASH_VERSION"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return done.stdout.decode("utf-8", "replace").strip()


# ---- The real runner

def mail_for(payload, job_id, script):
    """The mail that carries `script` in the honest job."""
    job = copy.deepcopy(payload)
    job["script"] = script
    return PRE._mail(PRE._subject(job_id), BIND._signed(job))


def at_the_gate(raw, cfg_extra=None):
    """Whether the gate admits the mail, and the gate's lines.
    The execution is a stub: the decision is the gate's."""
    with tempfile.TemporaryDirectory() as folder:
        out = PRE.arrive(raw, folder, cfg_extra=cfg_extra)
    return len(out.executed) == 1, out.notes


def digest(text):
    return hashlib.sha384(text.encode("utf-8")).hexdigest()


# ---- Finding F14: the reader of a script's shape

# The reader's 2 patterns as they stood before finding F14,
# kept here so that the patterns that stand now are held to
# them on every small text.
WAS_BASH_ONLY = re.compile(
    r"(?m)"
    r"^\s*[A-Za-z_]\w*\+?=\("
    r"|\$\{\#?[A-Za-z_]\w*\["
    r"|<<<"
    r"|<\("
    r"|>\("
    r"|\$\{[A-Za-z_]\w*:[0-9]"
    r"|^\s*(?:declare|mapfile|readarray)\b")
WAS_EXPORT = re.compile(r"(?m)^\s*export\s+[A-Za-z_][A-Za-z0-9_]*=")
UNITS = ("\n", " ", "\t", "\r", "\x0b", "\u2028", "a=(", "a+=(",
         "declare", "mapfile x", "export A=", "export", "A=1", "x",
         "#", ";", "1")
BLANK_LINES = ("\n", "\n ", " \n", "\t\n", "\r\n")


class TheCountAtAnyN(unittest.TestCase):
    """C(N): the count of rows has no size in it."""

    @classmethod
    def setUpClass(cls):
        cls.exact = exact_counts(5000)

    def test_the_count_is_the_first_rung_s_count(self):
        self.assertEqual(RUNG.count_by_length(), self.exact[:50])
        self.assertEqual(RUNG.CLOSURE, sum(self.exact[:50]))
        self.assertEqual(
            (114, 1139),
            (len(str(sum(self.exact[:501]))), len(str(sum(self.exact)))))

    def test_each_character_adds_a_fixed_share_of_a_digit(self):
        rate = math.log10(growth())
        self.assertAlmostEqual(0.227783, rate, places=6)
        # From the exact count at 5,000, by the rate: the length
        # of the count at the 3 rungs above.
        base = math.log10(sum(self.exact))
        self.assertEqual(
            [11389, 113892, 238848],
            [int(base + (size - 5000) * rate) + 1
             for size in (50000, 500000, CAP)])

    def test_a_script_is_1_row(self):
        # The count of rows is the count of scripts: no text
        # can be cut into atoms and joiners in 2 ways.
        for atoms, joiners in RUNG.rows(max_chars=18):
            self.assertEqual([(atoms, joiners)],
                             cuts(RUNG.text(atoms, joiners)))
        rng = random.Random(20261119)
        for _draw in range(200):
            row = draw_exact(500, self.exact, rng)
            self.assertEqual([row], cuts(RUNG.text(*row)))
        # 1 atom begins another, and no joiner can follow it
        # inside the longer one.
        self.assertEqual(
            [("echo a", "echo a > /dev/null")],
            [(short, long) for short in ATOMS for long in ATOMS
             if short != long and long.startswith(short)])

    def test_the_even_draw_gives_rows_of_the_asked_length(self):
        rng = random.Random(7)
        for length in (1, 3, 4, 49, 50, 51, 500, 4999, 5000):
            atoms, joiners = draw_exact(length, self.exact, rng)
            self.assertEqual(length, len(RUNG.text(atoms, joiners)))
        self.assertEqual(0, self.exact[2])
        self.assertTrue(all(self.exact[length] > 0
                            for length in range(3, 5001)))
        # At a length with few rows, every row is drawn.
        want = {row for row in RUNG.rows(max_chars=9)
                if len(RUNG.text(*row)) == 9}
        self.assertEqual(self.exact[9], len(want))
        got = {draw_exact(9, self.exact, rng) for _draw in range(4000)}
        self.assertEqual(want, got)


class WhatGrowsWithN(unittest.TestCase):
    """The formulas, against every row of at most 22
    characters."""

    @classmethod
    def setUpClass(cls):
        cls.top = 22
        cls.tables = {
            "short": RUNG.denotation("/w", "/h"),
            "a long folder": RUNG.denotation("/" + "w" * 88, "/home/x"),
            "a long home": RUNG.denotation("/w", "/" + "h" * 200),
        }
        cls.atoms = [0] * (cls.top + 1)
        cls.pipes = [0] * (cls.top + 1)
        cls.printed = {name: [0] * (cls.top + 1) for name in cls.tables}
        for atoms, joiners in RUNG.rows(max_chars=cls.top):
            length = len(RUNG.text(atoms, joiners))
            cls.atoms[length] = max(cls.atoms[length], len(atoms))
            cls.pipes[length] = max(cls.pipes[length], pipeline_of(joiners))
            for name, table in cls.tables.items():
                cls.printed[name][length] = max(
                    cls.printed[name][length],
                    len(RUNG.run(atoms, joiners, table)[0]))

    def test_the_most_atoms_and_the_longest_pipeline(self):
        for size in range(1, self.top + 1):
            self.assertEqual(most_atoms(size),
                             max(self.atoms[:size + 1]), size)
            self.assertEqual(longest_pipeline(size),
                             max(self.pipes[:size + 1]), size)
        self.assertEqual(17, most_atoms(RUNG.BOUND))
        self.assertEqual((349526, 262144),
                         (most_atoms(CAP), longest_pipeline(CAP)))

    def test_the_most_output(self):
        for name, table in self.tables.items():
            folder = len(table["pwd"][0]) - 1
            home = len(table["echo $HOME"][0]) - 1
            rate = max((folder + 1) / 5, (home + 1) / 12)
            for size in range(1, self.top + 1):
                most, atoms = most_output(size, table)
                self.assertEqual(most, max(self.printed[name][:size + 1]),
                                 (name, size))
                self.assertLessEqual(most, rate * (size + 2) + 1e-9)
                if atoms:
                    joiners = (SEMI,) * (len(atoms) - 1)
                    self.assertLessEqual(
                        len(RUNG.text(atoms, joiners)), size)
                    self.assertEqual(
                        most, len(RUNG.run(atoms, joiners, table)[0]))

    def test_where_the_output_cap_is_first_reached(self):
        # With a short home the row of `pwd` gets there first:
        # 5 characters of script for the path and a line end.
        for folder in (20, 36, 37, 60, 89, 98, 99, 160):
            table = RUNG.denotation("/" + "w" * (folder - 1), "/root")
            self.assertEqual(5 * (KEPT // (folder + 1)) + 3,
                             first_cut(KEPT, table), folder)
        # With a long home the count can put it a little lower,
        # and never past what the rate allows: no row of N
        # characters is cut while rate x (N + 2) is at most K.
        for folder, home, first in ((34, 80, 14285), (60, 200, 5972),
                                    (89, 200, 5555)):
            table = RUNG.denotation("/" + "w" * (folder - 1),
                                    "/" + "h" * (home - 1))
            self.assertEqual(first, first_cut(KEPT, table))
            self.assertLessEqual(first, 5 * (KEPT // (folder + 1)) + 3)
            rate = max((folder + 1) / 5, (home + 1) / 12)
            self.assertGreater(rate * (first + 2), KEPT)
        # The owner's rung of 5,000 is under it when the path is
        # at most 99 characters, and the rung of 500 when it is
        # at most 999.
        for rung, longest in ((5000, 99), (500, 999)):
            self.assertGreater(first_cut(KEPT, RUNG.denotation(
                "/" + "w" * (longest - 1), "/root")), rung)
            self.assertLessEqual(first_cut(KEPT, RUNG.denotation(
                "/" + "w" * longest, "/root")), rung)
        # The 3 numbers the page gives.
        self.assertEqual(
            [14288, 8198, 5003, 13513, 13158],
            [5 * (KEPT // (folder + 1)) + 3
             for folder in (34, 60, 99, 36, 37)])


@unittest.skipIf(not POSIX, "POSIX only")
class TheShellPastTheFirstRung(unittest.TestCase):
    """The real bash on rows of more than 49 characters."""

    @classmethod
    def setUpClass(cls):
        cls.exact = exact_counts(5000)

    def shell(self, asked):
        with tempfile.TemporaryDirectory() as folder:
            cwd = os.path.join(folder, "cwd")
            os.mkdir(cwd)
            table = RUNG.denotation(os.path.realpath(cwd), RUNG.ENV["HOME"])
            got = RUNG.in_the_shell([RUNG.text(*row) for row in asked], cwd)
        return [RUNG.text(*row) for row, result in zip(asked, got)
                if result != RUNG.run(row[0], row[1], table)]

    def test_bash_agrees_at_every_length_from_50_to_500(self):
        # 2 rows at each exact length, drawn evenly from all the
        # rows of that length, the same rows on every run.
        rng = random.Random(20261119)
        asked = [draw_exact(length, self.exact, rng)
                 for length in range(50, 501) for _draw in range(2)]
        self.assertEqual(902, len(asked))
        self.assertEqual(list(range(50, 501)),
                         sorted({len(RUNG.text(*row)) for row in asked}))
        self.assertEqual([], self.shell(asked))

    def test_bash_takes_every_step_of_m_at_the_end_of_a_long_row(self):
        # Premise P-b asked directly: each of the 352 steps as
        # the last step of a row of exactly 500 characters, and
        # every 8th of them at exactly 5,000.
        rng = random.Random(20261119)
        table = RUNG.denotation("/where", "/home")
        asked = []
        for size, every in ((500, 1), (5000, 8)):
            for at, (state, (atoms, joiners)) in enumerate(RUNG.step_rows()):
                if at % every:
                    continue
                tail = len(RUNG.text(atoms, joiners))
                front = draw_exact(size - tail - len(SEMI), self.exact, rng)
                row = front[0] + atoms, front[1] + (SEMI,) + joiners
                self.assertEqual(size, len(RUNG.text(*row)))
                walked, _result = RUNG.steps(row[0], row[1], table)
                self.assertEqual((state, joiners[-1], atoms[-1]), walked[-1])
                asked.append(row)
        self.assertEqual(352 + 44, len(asked))
        self.assertEqual([], self.shell(asked))

    @unittest.skipUnless(LINUX, "the shell's 2 bars are measured on Linux")
    def test_bash_agrees_on_the_rows_that_strain_it_most(self):
        # Under every bar the page finds: the deepest lists at
        # 50,000 characters, the longest pipeline at 13,000, and
        # the rows that start the most processes at 5,000.
        for name, size in (("atoms", 50000), ("and", 50000), ("or", 50000),
                           ("output", 50000), ("pipeline", 13000),
                           ("pairs", 5000), ("subshells", 5000)):
            atoms, joiners = strain(name, size)
            self.assertLessEqual(len(RUNG.text(atoms, joiners)), size)
            self.assertGreater(len(RUNG.text(atoms, joiners)), size - 10)
            self.assertTrue(agrees(atoms, joiners), (name, size))


@unittest.skipUnless(LINUX, "the shell's 2 bars are measured on Linux")
class TheBarsTheShellAndTheMachineSet(unittest.TestCase):
    """Premise P-c: where the shell's room ends, it ends
    loudly."""

    def most_read(self, front, last):
        """The most commands in 1 pipeline, after `front` and
        ending in `last`, that bash will read."""
        def reads(count):
            script = front + ": | " * (count - 1) + last
            return own_process(script, read_only=True)[2] == 0
        low, high = 1000, 20000
        self.assertTrue(reads(low))
        if reads(high):
            return None
        while high - low > 1:
            middle = (low + high) // 2
            if reads(middle):
                low = middle
            else:
                high = middle
        return low

    def test_the_grammar_s_bar_refuses_the_whole_row_and_says_so(self):
        most = self.most_read("", ":")
        if most is None:
            self.skipTest("this bash reads a pipeline of 20,000 commands")
        if bash_version().startswith("5.2.21"):
            # The page's numbers, for the bash the page names.
            self.assertEqual(3333, most)
            self.assertEqual(3332, self.most_read(":; ", ":"))
            self.assertEqual(13332, len(":; " + ": | " * 3332 + ":"))
        # Under the bar the row runs and M has its result.
        self.assertTrue(agrees((":",) * most, (PIPE,) * (most - 1)))
        # 1 command over it: status 2, words on the error
        # stream, and nothing of the row has run, not even the
        # command in front of the pipeline.
        over = "echo a; " + ": | " * most + ":"
        out, err, status, _table = own_process(over)
        self.assertEqual(("", 2), (out, status))
        self.assertIn(b"syntax error", err)

    def test_the_stack_s_bar_ends_the_shell_by_a_signal_and_moves(self):
        deep = (":",) * 8000, (SEMI,) * 7999
        # With 1 megabyte of stack a row of 500 commands is
        # held and a row of 8,000 is not: the shell is ended
        # by a signal, which no result of M can be taken for.
        self.assertTrue(agrees((":",) * 500, (SEMI,) * 499, stack_kb=1024))
        out, err, status, _table = own_process(RUNG.text(*deep),
                                               stack_kb=1024)
        self.assertLess(status, 0)
        self.assertEqual(("", b""), (out, err))
        # With 4 megabytes the same row is held: the bar is
        # the machine's, and it moves with the stack.
        self.assertTrue(agrees(deep[0], deep[1], stack_kb=4096))


class TheRunnerPastTheFirstRung(unittest.TestCase):
    """B1(N) and B3(N): the real gate and the real execution,
    with the size door moved past 50."""

    @classmethod
    def setUpClass(cls):
        cls.payload, cls.job_id = RUNG.honest_job()
        cls.exact = exact_counts(5001)

    def ask(self, script, extra=None, view=None):
        payload = copy.deepcopy(self.payload)
        cfg = dict(RUNG.OFF)
        cfg.update(extra or {})
        if view is not None:
            payload["result_policy"] = {"view": view}
            cfg["max_result_view"] = view
        return RUNG.ask_the_runner(payload, self.job_id, script, extra=cfg)

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_the_runner_returns_m_s_result_past_50(self):
        rng = random.Random(20261119)
        home = os.environ.get("HOME", "")
        for size, count in ((500, 8), (5000, 2)):
            for _draw in range(count):
                atoms, joiners = draw_exact(size, self.exact, rng)
                script = RUNG.text(atoms, joiners)
                got, where = self.ask(script,
                                      extra={"max_script_bytes": size})
                self.assertIsNotNone(got, script[:60])
                out, status = RUNG.run(
                    atoms, joiners,
                    RUNG.denotation(os.path.realpath(where), home))
                self.assertLessEqual(len(out), KEPT)
                self.assertEqual(
                    (status, digest(out), "attested", "", ""),
                    (got.get("exit_code"), got.get("output_digest"),
                     got.get("view"), got.get("stdout"), got.get("stderr")),
                    script[:60])
            # 1 character more does not pass this door.
            atoms, joiners = draw_exact(size + 1, self.exact, rng)
            got, _where = self.ask(RUNG.text(atoms, joiners),
                                   extra={"max_script_bytes": size})
            self.assertIsNone(got, size)

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_over_the_output_cap_the_digest_is_of_what_is_kept(self):
        home = os.environ.get("HOME", "")
        _probe, where = self.ask("pwd")
        table = RUNG.denotation(os.path.realpath(where), home)
        folder = len(table["pwd"][0]) - 1
        for kept, extra in ((KEPT, {}), (1000, {"max_output_bytes": 1000})):
            bar = first_cut(kept, table)
            self.assertLessEqual(bar, 5 * (kept // (folder + 1)) + 3)
            if folder >= 20 and len(home) <= 12:
                # A short home: the row of `pwd` is first.
                self.assertEqual(5 * (kept // (folder + 1)) + 3, bar)
            for size in (bar - 1, bar):
                most, atoms = most_output(size, table)
                joiners = (SEMI,) * (len(atoms) - 1)
                script = RUNG.text(atoms, joiners)
                self.assertLessEqual(len(script), size)
                over = size == bar
                self.assertEqual(over, most > kept)
                for view in (None, "full"):
                    got, where = self.ask(script, extra=extra, view=view)
                    out, status = RUNG.run(
                        atoms, joiners,
                        RUNG.denotation(os.path.realpath(where), home))
                    self.assertEqual(most, len(out))
                    # The exit code is M's, and the digest is of
                    # the first `kept` characters of M's output.
                    self.assertEqual(
                        (status, digest(out[:kept])),
                        (got.get("exit_code"), got.get("output_digest")),
                        (kept, size, view))
                    self.assertEqual(over, digest(out) != digest(out[:kept]))
                    said = sorted(key for key in got if "trunc" in key)
                    if view == "full":
                        # The full view says that it was cut.
                        self.assertEqual(
                            (over, False),
                            (got.get("stdout_truncated"),
                             got.get("stderr_truncated")))
                        self.assertEqual(out[:kept], got.get("stdout"))
                    else:
                        # The default view does not: it carries
                        # nothing else derived from the output.
                        self.assertEqual([], said)
                        self.assertEqual("attested", got.get("view"))

    @unittest.skipUnless(LINUX, "the shell's 2 bars are measured on Linux")
    def test_over_the_time_limit_the_result_says_so(self):
        # The limit is set to 1 second, and the row starts
        # 28,572 processes.
        atoms, joiners = strain("pairs", 100000)
        got, _where = self.ask(RUNG.text(atoms, joiners),
                               extra={"default_timeout_sec": 1})
        self.assertEqual((-1, True),
                         (got.get("exit_code"), got.get("timed_out")))

    @unittest.skipUnless(LINUX, "the shell's 2 bars are measured on Linux")
    def test_over_the_grammar_s_bar_the_exit_code_is_not_m_s(self):
        row = (":",) * 20000, (PIPE,) * 19999
        script = RUNG.text(*row)
        if own_process(script, read_only=True)[2] == 0:
            self.skipTest("this bash reads a pipeline of 20,000 commands")
        got, where = self.ask(script, view="full")
        out, status = RUNG.run(row[0], row[1], RUNG.denotation(
            os.path.realpath(where), os.environ.get("HOME", "")))
        self.assertEqual(("", 0), (out, status))
        self.assertEqual((2, ""), (got.get("exit_code"), got.get("stdout")))
        self.assertIn("syntax error", got.get("stderr"))
        self.assertNotEqual(digest(out), got.get("output_digest"))

    def test_the_size_door_at_the_upper_rungs(self):
        for size in (50000, 500000, CAP):
            for length in (size, size + 1):
                ok, notes = at_the_gate(
                    mail_for(self.payload, self.job_id, "#" * length),
                    {"max_script_bytes": size})
                self.assertEqual(length <= size, ok, (size, length))
            self.assertIn(
                "rejecting seq 3: script exceeds max_script_bytes "
                "(%d > %d)" % (size + 1, size), notes)
            # A character of 3 bytes: the bytes decide.
            for count in (size // 3, size // 3 + 1):
                ok, _notes = at_the_gate(
                    mail_for(self.payload, self.job_id, "€" * count),
                    {"max_script_bytes": size})
                self.assertEqual(count * 3 <= size, ok, (size, count))

    def test_a_script_that_must_be_escaped_meets_the_job_door_first(self):
        # At the defaults. A control character is 6 bytes in
        # the mail, so the job door, 4,194,304 bytes, stands in
        # front of the size door for such a script.
        def length_of(count):
            return len(mail_for(self.payload, self.job_id, "\x01" * count))
        apart = length_of(1) - 6
        self.assertEqual(apart + 6 * 1000, length_of(1000))
        most = (JOB_DOOR - apart) // 6
        # The page's number, for the mail this suite builds.
        self.assertEqual(698986, most)
        ok, _notes = at_the_gate(
            mail_for(self.payload, self.job_id, "\x01" * most))
        self.assertTrue(ok)
        ok, notes = at_the_gate(
            mail_for(self.payload, self.job_id, "\x01" * (most + 1)))
        self.assertFalse(ok)
        self.assertTrue(any("mail exceeds max_job_bytes" in note
                            for note in notes), notes[-3:])
        self.assertFalse(any("max_script_bytes" in note for note in notes))
        # Plain text passes the job door at every size up to
        # the cap, and the size door decides.
        ok, _notes = at_the_gate(
            mail_for(self.payload, self.job_id, "#" * CAP))
        self.assertTrue(ok)
        ok, notes = at_the_gate(
            mail_for(self.payload, self.job_id, "#" * (CAP + 1)))
        self.assertFalse(ok)
        self.assertTrue(any("script exceeds max_script_bytes" in note
                            for note in notes))


class TheGateReadsAScriptInProportion(unittest.TestCase):
    """Finding F14. The reader of a script's shape stands
    behind the signature and the size door, and runs for every
    exec job that verifies. Its patterns take the white space
    of 1 line, so a run of blank lines is read once."""

    def test_the_reader_answers_as_it_did_on_every_small_text(self):
        texts, found = 0, [0, 0]
        for size in range(5):
            for units in itertools.product(UNITS, repeat=size):
                text = "".join(units)
                texts += 1
                for at, (was, now) in enumerate((
                        (WAS_BASH_ONLY, OPINION._BASH_ONLY_RE),
                        (WAS_EXPORT, OPINION._EXPORT_RE))):
                    answer = bool(was.search(text))
                    self.assertEqual(answer, bool(now.search(text)),
                                     repr(text))
                    found[at] += answer
        self.assertEqual(88741, texts)
        # The comparison has teeth: both patterns find a
        # large share of the texts, across line ends too.
        self.assertGreater(min(found), 5000)
        self.assertTrue(WAS_BASH_ONLY.search("\n \n\ta=("))
        self.assertTrue(OPINION._BASH_ONLY_RE.search("\n \n\ta=("))
        self.assertEqual("bash", OPINION.script_shape("x\n\n  declare y"))
        self.assertEqual("posix", OPINION.script_shape("x\n\n\texport A=1"))

    def test_the_patterns_take_the_white_space_of_1_line(self):
        for pattern in (OPINION._BASH_ONLY_RE, OPINION._EXPORT_RE):
            self.assertNotIn(r"^\s", pattern.pattern)
            self.assertIn(r"^[^\S\n]*", pattern.pattern)

    def test_blank_lines_do_not_hold_the_reader(self):
        # 200,000 blank lines held the reader for about 6
        # minutes when its patterns crossed line ends. The
        # bound here is wide: a reading in proportion takes a
        # few hundredths of a second.
        for unit in BLANK_LINES:
            script = unit * (200000 // len(unit))
            began = time.monotonic()
            self.assertEqual("neutral", OPINION.script_shape(script))
            self.assertLess(time.monotonic() - began, 10.0, repr(unit))

    def test_a_script_of_line_ends_at_the_cap_passes_the_gate(self):
        payload, job_id = RUNG.honest_job()
        began = time.monotonic()
        ok, _notes = at_the_gate(mail_for(payload, job_id, "\n" * CAP))
        self.assertTrue(ok)
        self.assertLess(time.monotonic() - began, 120.0)


class ThePageRecordsTheMeasure(unittest.TestCase):
    """The figures this module computes are the page's."""

    def test_the_page_states_what_was_counted_and_run(self):
        page = MODELS._flat(PAGE)
        exact = exact_counts(5000)
        for stated in (
                "| 5,000 | %s |" % format(len(str(sum(exact))), ","),
                "| 1,048,576 | 238,848 |",
                "3,481,245 rows",
                "| Every row of up to 3 atoms, at any length | 172,326 | 0 |",
                "186,902 rows",
                "13,332 characters",
                "| 14,288 | 100,030 characters "
                "| of the first 100,000 characters |",
                "698,987",
                "1,508,598 texts",
                "0 disagreements"):
            self.assertIn(stated, page, stated)
        self.assertEqual(13332, len(":; " + ": | " * 3332 + ":"))
        self.assertEqual(172326, 22 + 22 * 88 + 22 * 88 * 88)


if __name__ == "__main__":
    unittest.main()
