#!/usr/bin/env python3
"""L1 and L2 of the ladder.

docs/infrastructure-documents/proofs/v4-the-ladder.md. L1 is
the ratio table, on made-up quantities. L2 is M's table: a
joined row's result is made from the 2 rows' tables, with no
walk through the atoms, and it equals the walk. No shell and
no gate.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tests import test_v4_at_a_bound as BOUND  # noqa: E402

PAGE = os.path.join(
    ROOT, "docs", "infrastructure-documents", "proofs",
    "v4-the-ladder.md")

# Step n is the nth Fibonacci number, from 0.
SERIES = [0, 1]
while len(SERIES) <= 31:
    SERIES.append(SERIES[-1] + SERIES[-2])

TABLE = ((0, 0.50), (1, 1.00), (2, 1.89), (3, 3.43))


def value(power, step, slope=1, aside=0):
    """A made-up quantity. Power 0 is the fixed amount. A slope
    and an aside are the sharper case: so much per character,
    and a fixed amount besides."""
    if power == 0:
        return aside
    return slope * SERIES[step] ** power + aside


def ratio(power, step):
    aside = 1 if power == 0 else 0
    got = value(power, step, aside=aside)
    return got / (value(power, step - 1, aside=aside)
                  + value(power, step - 2, aside=aside))


def difference(power, step, slope=1, aside=0):
    return (value(power, step, slope, aside)
            - value(power, step - 1, slope, aside)
            - value(power, step - 2, slope, aside))


class TheRatioTable(unittest.TestCase):
    """L1, and nothing past it."""

    def test_the_series_reaches_the_cap_at_step_30(self):
        self.assertEqual(832040, SERIES[30])
        self.assertEqual(1346269, SERIES[31])
        self.assertLess(SERIES[30], 1048576)
        self.assertGreater(SERIES[31], 1048576)

    def test_the_ratio_at_steps_20_to_30_is_the_table(self):
        for power, stated in TABLE:
            worst = max(abs(ratio(power, step) - stated)
                        for step in range(20, 31))
            self.assertLess(worst, 0.01, (power, worst))
        self.assertEqual(
            [0.5] * 11, [ratio(0, step) for step in range(20, 31)])
        self.assertEqual(
            [1.0] * 11, [ratio(1, step) for step in range(20, 31)])

    def test_the_difference_is_exact_for_the_first_2(self):
        self.assertEqual(
            {-7}, {difference(0, step, aside=7) for step in range(2, 31)})
        self.assertEqual(
            {-5}, {difference(1, step, slope=3, aside=5)
                   for step in range(2, 31)})
        squares = [difference(2, step) for step in range(2, 31)]
        self.assertEqual([0, 2, 4, 12], squares[:4])
        self.assertTrue(all(b > a for a, b in zip(squares, squares[1:])))

    def test_the_page_records_l1_and_not_the_rest(self):
        with open(PAGE, encoding="utf-8") as handle:
            page = " ".join(handle.read().split())
        for stated in (
                "L1's figures are recorded here.",
                "Step 30 is 832,040.",
                "0.00443 from 1.89",
                "0.00295 from 3.43",
                "difference -7",
                "difference -5",
                "holds these figures."):
            self.assertIn(stated, page, stated)


# ---- L2. The table joins.

STATES = ((0, True), (0, False), (1, True), (1, False))
DEN = BOUND.denotation("/work", "/home")
AND, OR, SEMI, PIPE = BOUND.AND, BOUND.OR, BOUND.SEMI, BOUND.PIPE


def atom_table(atom):
    """The 16 entries for one atom. An entry is (fate, own
    output, pending, status, running). Fate is what becomes
    of the output still pending in front of the row."""
    out, status = DEN[atom]
    table = {}
    for old, running in STATES:
        row = {}
        for joiner in BOUND.JOINERS:
            if joiner == SEMI:
                row[joiner] = ("flush", "", out, status, True)
            elif joiner == PIPE:
                if running:
                    row[joiner] = ("drop", "", out, status, True)
                else:
                    row[joiner] = ("keep", "", None, old, False)
            elif (old == 0) == (joiner == AND):
                row[joiner] = ("flush", "", out, status, True)
            else:
                row[joiner] = ("flush", "", "", old, False)
        table[(old, running)] = row
    return table


def combine(left, right, mid):
    fate, own, pending, status, running = left
    if fate == "keep":
        got = right[(status, running)][mid]
        if got[0] == "keep":
            return ("keep", "", None, status, running)
        return got
    got = right[(status, running)][mid]
    if got[0] == "keep":
        return left
    if got[0] == "flush":
        return (fate, own + (pending or "") + got[1], got[2],
                got[3], got[4])
    return (fate, own + got[1], got[2], got[3], got[4])


def compose(left, right, mid):
    return {state: {front: combine(left[state][front], right, mid)
                    for front in BOUND.JOINERS}
            for state in STATES}


def leaf_end(atom):
    out, status = DEN[atom]
    return ("", out, status, True)


def join_end(end, right, mid):
    committed, pending, status, running = end
    fate, own, pend, status2, running2 = right[(status, running)][mid]
    if fate == "keep":
        return end
    if fate == "flush":
        return (committed + (pending or "") + own, pend, status2, running2)
    return (committed + own, pend, status2, running2)


def printed(end):
    committed, pending, status, _running = end
    return committed + (pending or ""), status


def kind_of(table):
    cells = []
    for state in STATES:
        for joiner in BOUND.JOINERS:
            fate, _own, _pend, status, running = table[state][joiner]
            cells.append(("keep",) if fate == "keep"
                         else (fate, status, running))
    return tuple(cells)


class TheJoin(unittest.TestCase):
    """L2. The table's result is the walk's, and the kinds
    are 14, closed."""

    def test_the_table_matches_the_walk_on_every_row(self):
        tables = {atom: atom_table(atom) for atom in BOUND.ATOMS}
        ends = {atom: leaf_end(atom) for atom in BOUND.ATOMS}
        ways = [(joiner,) for joiner in BOUND.JOINERS] + ["turn"]
        rows = differences = longest = 0
        seen = {kind_of(table) for table in tables.values()}
        for first in BOUND.ATOMS:
            for second in BOUND.ATOMS:
                for way in ways:
                    step_end = [None, ends[first], ends[second]]
                    step_table = [None, tables[first], tables[second]]
                    step_atoms = [None, (first,), (second,)]
                    step_joiners = [None, (), ()]
                    for step in range(3, 16):
                        mid = (BOUND.JOINERS[(step - 3) % 4]
                               if way == "turn" else way[0])
                        end = join_end(step_end[step - 1],
                                       step_table[step - 2], mid)
                        table = compose(step_table[step - 1],
                                        step_table[step - 2], mid)
                        atoms = step_atoms[step - 1] + step_atoms[step - 2]
                        joiners = (step_joiners[step - 1] + (mid,)
                                   + step_joiners[step - 2])
                        rows += 1
                        longest = max(longest, len(atoms))
                        if printed(end) != BOUND.run(atoms, joiners, DEN):
                            differences += 1
                        seen.add(kind_of(table))
                        step_end.append(end)
                        step_table.append(table)
                        step_atoms.append(atoms)
                        step_joiners.append(joiners)
        self.assertEqual((31460, 0, 610), (rows, differences, longest))
        self.assertEqual(14, len(seen))

    def test_every_row_is_one_of_14_kinds(self):
        tables = [atom_table(atom) for atom in BOUND.ATOMS]
        found = {kind_of(table) for table in tables}
        self.assertEqual(2, len(found))
        self.assertEqual(
            ["false"],
            [atom for atom in BOUND.ATOMS if DEN[atom][1] != 0])
        horizon = list(found)
        while horizon:
            current = horizon.pop()
            for other in list(found):
                for mid in BOUND.JOINERS:
                    for nxt in (compose_kind(current, other, mid),
                                compose_kind(other, current, mid)):
                        if nxt not in found:
                            found.add(nxt)
                            horizon.append(nxt)
        self.assertEqual(14, len(found))

    def test_the_page_records_l2(self):
        with open(PAGE, encoding="utf-8") as handle:
            page = " ".join(handle.read().split())
        for stated in (
                "L2's figures are recorded here.",
                "| Rows, steps 3 to 15, 484 pairs, 5 ways | 31,460 |",
                "| Differences between the table and M's walk | 0 |",
                "| The longest row, in atoms | 610 |",
                "The number is 14.",
                "The shell was not asked."):
            self.assertIn(stated, page, stated)


def compose_kind(left, right, mid):
    """The kind of a join, from the 2 kinds. The output text
    is not part of a kind, and it is not used here."""
    index = {joiner: i for i, joiner in enumerate(BOUND.JOINERS)}

    def cell(kind, state, joiner):
        return kind[STATES.index(state) * 4 + index[joiner]]

    cells = []
    for state in STATES:
        for front in BOUND.JOINERS:
            got = cell(left, state, front)
            if got[0] == "keep":
                other = cell(right, state, mid)
                cells.append(("keep",) if other[0] == "keep" else other)
                continue
            left_state = (got[1], got[2])
            other = cell(right, left_state, mid)
            if other[0] == "keep":
                cells.append(got)
            else:
                cells.append((got[0], other[1], other[2]))
    return tuple(cells)


# ---- L3. The shell.

TRACE = {
    "(echo a)": ("echo a",),
    "echo $(:)": ("echo $(:)", ":"),
    "if true; then echo a; fi": ("true", "echo a"),
}


def commands_of(atoms, joiners):
    """The commands M says run, in the order a walk sees them.
    A pipe starts its two sides together, so this order is not
    the shell's trace order across a pipe."""
    ran = list(TRACE.get(atoms[0], (atoms[0],)))
    status, running = DEN[atoms[0]][1], True
    for joiner, atom in zip(joiners, atoms[1:]):
        if joiner == SEMI or joiner == PIPE and running \
                or joiner in (AND, OR) and (status == 0) == (joiner == AND):
            ran.extend(TRACE.get(atom, (atom,)))
        if joiner == SEMI:
            status, running = DEN[atom][1], True
        elif joiner == PIPE and running:
            status = DEN[atom][1]
        elif joiner in (AND, OR):
            if (status == 0) == (joiner == AND):
                status, running = DEN[atom][1], True
            else:
                running = False
    return ran


def shell_batch(scripts, cwd):
    """Each script in a subshell of its own, with the shell's
    trace of the commands that ran. [(output, status, commands)]."""
    lines = []
    for index, script in enumerate(scripts):
        lines.append("printf '\\036%d\\037' %d\n" % (index, index))
        lines.append("printf '\\036%d\\037' %d >&2\n" % (index, index))
        lines.append("(\nset -T\n"
                     "trap 'printf \"CMD:%%s\\n\" \"$BASH_COMMAND\" >&2' DEBUG\n"
                     "%s\n)\n" % script)
        lines.append("code=$?\nprintf '\\035%d\\034' \"$code\"\n")
        lines.append("printf '\\035%d\\034' %d >&2\n" % (index, index))
    path = os.path.join(os.path.dirname(cwd), "driver.sh")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.writelines(lines)
    done = subprocess.run(BOUND.BASH + [path], cwd=cwd, env=BOUND.ENV,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if done.returncode != 0:
        raise AssertionError(done.stderr[:300])
    out, err = {}, {}
    for part in done.stdout.decode("utf-8").split("\036")[1:]:
        index, rest = part.split("\037", 1)
        body, tail = rest.rsplit("\035", 1)
        out[int(index)] = (body, int(tail.rstrip("\034")))
    for part in done.stderr.decode("utf-8").split("\036")[1:]:
        index, rest = part.split("\037", 1)
        body, _tail = rest.rsplit("\035", 1)
        err[int(index)] = [line[4:] for line in body.splitlines()
                           if line.startswith("CMD:")]
    return [(out[i][0], out[i][1], err[i]) for i in range(len(scripts))]


def ladder_rows(last, families=None):
    """(atoms, joiners) for each family at each step from 3 to
    `last`. Families are every 2 atoms and the 5 ways, in that
    order, or the first `families` of them."""
    made = []
    count = 0
    for first in BOUND.ATOMS:
        for second in BOUND.ATOMS:
            for way in list(BOUND.JOINERS) + ["turn"]:
                count += 1
                if families is not None and count > families:
                    return made
                atoms = [None, (first,), (second,)]
                joiners = [None, (), ()]
                for step in range(3, last + 1):
                    mid = (BOUND.JOINERS[(step - 3) % 4]
                           if way == "turn" else way)
                    atoms.append(atoms[step - 1] + atoms[step - 2])
                    joiners.append(joiners[step - 1] + (mid,)
                                   + joiners[step - 2])
                    made.append((atoms[step], joiners[step]))
    return made


class TheShell(unittest.TestCase):
    """L3. The output, the status, and the commands that ran.
    Not the order of a pipe's two sides."""

    def setUp(self):
        if os.name == "nt":
            self.skipTest("POSIX only")
        self.folder = tempfile.mkdtemp()
        self.cwd = os.path.join(self.folder, "cwd")
        os.mkdir(self.cwd)
        self.den = BOUND.denotation(
            os.path.realpath(self.cwd), BOUND.ENV["HOME"])

    def tearDown(self):
        folder = getattr(self, "folder", None)
        if folder and os.path.isdir(folder):
            shutil.rmtree(folder)

    def agree(self, atoms, joiners, got):
        out, status = BOUND.run(atoms, joiners, self.den)
        ran = commands_of(atoms, joiners)
        self.assertEqual((out, status), (got[0], got[1]),
                         BOUND.text(atoms, joiners)[:60])
        self.assertEqual(sorted(ran), sorted(got[2]),
                         BOUND.text(atoms, joiners)[:60])

    def test_every_atom(self):
        got = shell_batch(list(BOUND.ATOMS), self.cwd)
        for atom, row in zip(BOUND.ATOMS, got):
            self.agree((atom,), (), row)
            self.assertEqual(list(TRACE.get(atom, (atom,))), row[2], atom)

    def test_every_row_of_2_atoms(self):
        rows = [( (first, second), (joiner,) )
                for first in BOUND.ATOMS
                for second in BOUND.ATOMS
                for joiner in BOUND.JOINERS]
        self.assertEqual(1936, len(rows))
        got = shell_batch([BOUND.text(*row) for row in rows], self.cwd)
        for row, result in zip(rows, got):
            self.agree(row[0], row[1], result)

    def test_the_first_20_families_at_step_17(self):
        rows = [row for row in ladder_rows(17, families=20)
                if len(row[0]) == 1597]
        self.assertEqual(20, len(rows))
        got = shell_batch([BOUND.text(*row) for row in rows], self.cwd)
        for row, result in zip(rows, got):
            self.agree(row[0], row[1], result)

    def test_the_page_records_l3(self):
        with open(PAGE, encoding="utf-8") as handle:
            page = " ".join(handle.read().split())
        for stated in (
                "L3 was run in the shell, bash 5.2.15.",
                "19,360 rows, the longest 55 atoms.",
                "| The output and the status, against M | 0 |",
                "| The commands that ran, against M | 0 |",
                "The order is not claimed.",
                "1,597 atoms."):
            self.assertIn(stated, page, stated)


MOTOR = os.path.join(
    ROOT, "docs", "infrastructure-documents", "proofs",
    "v4-the-motor.md")
TURN_PAGES = (
    "v4-the-join.md", "v4-the-grammar.md",
    "v4-the-folder.md", "v4-the-place.md")


class TheMotor(unittest.TestCase):
    """The motor page names the goal and each turn."""

    def test_the_page_names_the_goal_and_every_turn(self):
        with open(MOTOR, encoding="utf-8") as handle:
            page = " ".join(handle.read().split())
        for stated in (
                "from 30 million to 38 million",
                "runner/ops/version4.py",
                "The goal is not a number of tokens to add.",
                "30,191,271",
                "There are 14, and they are closed.",
                "The shell was not asked inside the sandbox.",
                "v4-the-join.md",
                "v4-the-grammar.md",
                "v4-the-folder.md",
                "v4-the-place.md",
                "The file still holds `x`.",
                "The commands that ran are the machine's.",
                "The shell's bars, climbed under enforce."):
            self.assertIn(stated, page, stated)
        line = "One turn of the motor, `v4-the-motor.md`."
        folder = os.path.dirname(MOTOR)
        for name in TURN_PAGES:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                text = " ".join(handle.read().split())
            self.assertIn(line, text, name)


if __name__ == "__main__":
    unittest.main()
