#!/usr/bin/env python3
"""Version 4 at a bound: the first rung, and the machine M.

docs/infrastructure-documents/proofs/v4-at-a-bound.md states the
claim: lock a size in the specification, and prove at that size.
At the first rung a script is at most 49 characters, built from
the 22 atoms and 4 joiners of the earlier record
(test_proof_content_rung49.py). This module holds 4 things:

  the closure   how many scripts the atoms build, counted exactly
  the machine   M, which gives every such script its output and
                its exit status, in 2 forms that must agree
  the shell     the real bash, asked on M's every step
  the runner    the real gate and the real execution, asked on
                M's every step, and the door at 3 bounds

The whole measure (858,319 scripts in the real shell) is recorded
on the page. What runs here on every suite run is the part that
carries the argument: every step of M, in the shell and through
the runner.
"""
import contextlib
import copy
import hashlib
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner as RUNNER  # noqa: E402
from runner.tests import test_proof_conformance as DOOR  # noqa: E402
from runner.tests import test_proof_content_rung49 as R49  # noqa: E402
from runner.tests import test_v4_before_the_mac as PRE  # noqa: E402
from runner.tests import test_v4_bindings as BIND  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-at-a-bound.md")
ATOMS = R49.BASH_ATOMS
JOINERS = R49.BASH_JOINERS
AND, OR, SEMI, PIPE = JOINERS
BOUND = R49.BOUND
CLOSURE = 74072330493
RUNGS = (50, 500, 5000)
OFF = {"security": {"modes": {"confinement": "off"}}}


# ---- The machine M

def denotation(cwd, home):
    """Each atom's (output, exit status) under bash, for a job
    that runs in `cwd` with HOME set to `home`."""
    table = {
        "true": ("", 0), ":": ("", 0), "pwd": (cwd + "\n", 0),
        "false": ("", 1), "echo a": ("a\n", 0), "echo b": ("b\n", 0),
        "echo c": ("c\n", 0), "printf x": ("x", 0),
        "echo ok": ("ok\n", 0), "echo 'a'": ("a\n", 0),
        'echo "a"': ("a\n", 0), "echo 'a b'": ("a b\n", 0),
        'echo "x y"': ("x y\n", 0), "echo $HOME": (home + "\n", 0),
        "echo ${HOME}": (home + "\n", 0), "echo $((1))": ("1\n", 0),
        "echo $(:)": ("\n", 0), "echo $((1+2))": ("3\n", 0),
        "echo {a,b}": ("a b\n", 0), "(echo a)": ("a\n", 0),
        "echo a > /dev/null": ("", 0),
        "if true; then echo a; fi": ("a\n", 0),
    }
    assert set(table) == set(ATOMS) and len(table) == len(ATOMS)
    return table


def text(atoms, joiners):
    """A row's text: its atoms with a joiner between each 2."""
    out = [atoms[0]]
    for joiner, atom in zip(joiners, atoms[1:]):
        out.append(joiner)
        out.append(atom)
    return "".join(out)


def run(atoms, joiners, table):
    """M as the shell's 3 layers: (output, exit status).
    Semicolons split a row into lists, && and || split a list
    into pipelines read from the left, and a pipe makes the
    last command the one whose output and status count."""
    lists, l_atoms, l_joiners = [], [atoms[0]], []
    for joiner, atom in zip(joiners, atoms[1:]):
        if joiner == SEMI:
            lists.append((l_atoms, l_joiners))
            l_atoms, l_joiners = [atom], []
        else:
            l_atoms.append(atom)
            l_joiners.append(joiner)
    lists.append((l_atoms, l_joiners))
    out, status = [], 0
    for l_atoms, l_joiners in lists:
        pipelines, ops, pipe = [], [], [l_atoms[0]]
        for joiner, atom in zip(l_joiners, l_atoms[1:]):
            if joiner == PIPE:
                pipe.append(atom)
            else:
                pipelines.append(pipe)
                ops.append(joiner)
                pipe = [atom]
        pipelines.append(pipe)
        p_out, status = table[pipelines[0][-1]]
        out.append(p_out)
        for op, pipe in zip(ops, pipelines[1:]):
            if (op == AND and status == 0) or (op == OR and status != 0):
                p_out, status = table[pipe[-1]]
                out.append(p_out)
    return "".join(out), status


def steps(atoms, joiners, table):
    """M as a walk: the (state, joiner, atom) steps a row takes,
    and its (output, exit status). A state is (the status so
    far, whether the pipeline in hand is running)."""
    taken = []
    p_out, status = table[atoms[0]]
    running, out = True, []
    for joiner, atom in zip(joiners, atoms[1:]):
        taken.append(((status, running), joiner, atom))
        a_out, a_status = table[atom]
        if joiner == SEMI:
            out.append(p_out)
            p_out, status, running = a_out, a_status, True
        elif joiner == PIPE:
            # The command in front of a pipe is read by nobody.
            if running:
                p_out, status = a_out, a_status
        else:
            out.append(p_out)
            if (status == 0) == (joiner == AND):
                p_out, status, running = a_out, a_status, True
            else:
                p_out, running = "", False
    out.append(p_out)
    return taken, ("".join(out), status)


def count_by_length(bound=BOUND):
    """How many rows the atoms build at each exact length."""
    exact = [0] * (bound + 1)
    for length in range(1, bound + 1):
        n = sum(1 for atom in ATOMS if len(atom) == length)
        for atom in ATOMS:
            for joiner in JOINERS:
                rest = length - len(atom) - len(joiner)
                if rest >= 1:
                    n += exact[rest]
        exact[length] = n
    return exact


def rows(max_atoms=None, max_chars=BOUND):
    """Every (atoms, joiners) row of at most `max_atoms` atoms
    and at most `max_chars` characters."""
    def grow(atoms, joiners, length):
        yield atoms, joiners
        if max_atoms is not None and len(atoms) >= max_atoms:
            return
        for joiner in JOINERS:
            for atom in ATOMS:
                more = length + len(joiner) + len(atom)
                if more <= max_chars:
                    yield from grow(atoms + (atom,),
                                    joiners + (joiner,), more)
    for atom in ATOMS:
        if len(atom) <= max_chars:
            yield from grow((atom,), (), len(atom))


# The shortest row that leaves M in each of its 4 states.
INTO = {(0, True): ((":",), ()),
        (1, True): (("false",), ()),
        (0, False): ((":", ":"), (OR,)),
        (1, False): (("false", ":"), (AND,))}


def step_rows():
    """1 row for each of M's 352 steps: the shortest way into
    the state, then the joiner and the atom."""
    for state in sorted(INTO):
        atoms, joiners = INTO[state]
        for joiner in JOINERS:
            for atom in ATOMS:
                yield state, (atoms + (atom,), joiners + (joiner,))


# ---- The real shell

ENV = {"HOME": "/home/pigeon-proof", "PATH": "/usr/bin:/bin",
       "LC_ALL": "C"}
BASH = ["bash", "--noprofile", "--norc"]


def in_the_shell(scripts, cwd):
    """Run every script in 1 bash process, each in a subshell
    of its own: [(output, exit status)], in the order given."""
    lines = []
    for index, script in enumerate(scripts):
        lines.append("printf '\\036%%d\\037' %d; ( %s ); "
                     "printf '\\035%%d\\034' $?\n" % (index, script))
    path = os.path.join(cwd, "..", "driver.sh")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.writelines(lines)
    done = subprocess.run(BASH + [path], cwd=cwd, env=ENV,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if done.returncode != 0 or done.stderr:
        raise AssertionError(done.stderr[:300])
    got = {}
    for part in done.stdout.decode("utf-8").split("\036")[1:]:
        index, rest = part.split("\037", 1)
        body, tail = rest.rsplit("\035", 1)
        got[int(index)] = (body, int(tail.rstrip("\034")))
    return [got[index] for index in range(len(scripts))]


# ---- The real runner

def honest_job():
    """The corpus's first fresh job that runs when it is signed
    by the key it names: (payload, job id)."""
    for _entry, payload, job_id in BIND.fresh_jobs():
        signed = BIND._signed(payload)
        if signed is None:
            continue
        with tempfile.TemporaryDirectory() as folder:
            if PRE.arrive(PRE._mail(PRE._subject(job_id), signed),
                          folder).executed:
                return payload, job_id
    raise AssertionError("the corpus holds no job that runs")


def ask_the_runner(payload, job_id, script, extra=None):
    """1 job through the real gate and the real execution:
    (the result as the runner sent it, where the job ran)."""
    job = copy.deepcopy(payload)
    job["script"] = script
    job["interpreter"] = ["bash"]
    job.pop("shell", None)
    raw = PRE._mail(PRE._subject(job_id), BIND._signed(job))
    sent, notes = [], []
    with tempfile.TemporaryDirectory() as folder:
        cfg = {"mailbox_user": "t@example.com", "base_dir": folder,
               "oracle_opinion_mode": "off"}
        cfg.update(BIND.KEYS)
        cfg.update(extra or {})
        RUNNER._set_allow_cleartext_jobs(True)
        try:
            with mock.patch.object(
                    RUNNER, "send_mail",
                    lambda _smtp, _cfg, subject, body, to=None:
                    sent.append(body)), \
                mock.patch.object(
                    RUNNER, "log",
                    lambda msg, level="INFO": notes.append(msg)), \
                    contextlib.redirect_stdout(io.StringIO()):
                RUNNER.handle_mail(
                    cfg, DOOR._IMAP2(), DOOR._SMTP2(), 3, raw, folder, {},
                    RUNNER.build_secrets(cfg),
                    Namespace(dry_run=False, no_send=False), None)
        finally:
            RUNNER._set_allow_cleartext_jobs(False)
    where = None
    for note in notes:
        found = re.search(r"cwd=(\S+)", note)
        if found:
            where = found.group(1)
    return (json.loads(sent[0]) if sent else None), where


def admitted(payload, job_id, script, cap):
    """Whether the gate admits `script` at a bound of `cap`
    bytes, and the gate's lines. The execution is a stub: the
    decision is the gate's."""
    job = copy.deepcopy(payload)
    job["script"] = script
    raw = PRE._mail(PRE._subject(job_id), BIND._signed(job))
    with tempfile.TemporaryDirectory() as folder:
        out = PRE.arrive(raw, folder, cfg_extra={"max_script_bytes": cap})
    return len(out.executed) == 1, out.notes


def corpus_scripts():
    """The byte length of the longest script in each corpus
    entry that carries one."""
    def inside(value, depth=0):
        if depth > 6:
            return
        if isinstance(value, dict):
            for key, held in value.items():
                if key == "script" and isinstance(held, str):
                    yield held
                else:
                    yield from inside(held, depth + 1)
        elif isinstance(value, list):
            for held in value:
                yield from inside(held, depth + 1)
        elif isinstance(value, str) and "script" in value and "{" in value:
            start = value.find("{")
            while start != -1:
                try:
                    held, end = json.JSONDecoder().raw_decode(value[start:])
                except ValueError:
                    start = value.find("{", start + 1)
                    continue
                yield from inside(held, depth + 1)
                start = value.find("{", start + end)
    sizes = []
    folder = os.path.join(ROOT, "runner", "tests", "de_dust")
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".jsonl") or name == "runs.jsonl":
            continue
        with open(os.path.join(folder, name), encoding="utf-8",
                  errors="surrogatepass") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                found = [len(script.encode("utf-8", "surrogatepass"))
                         for script in inside(entry)]
                if found:
                    sizes.append(max(found))
    return sizes


class TheClosureCounted(unittest.TestCase):
    """How many scripts the record's own atoms and joiners
    build at the first rung."""

    def test_the_closure_at_49_characters(self):
        exact = count_by_length()
        self.assertEqual(CLOSURE, sum(exact))
        self.assertEqual(
            [95, 1325, 18337, 252747, 3481245, 660089747, CLOSURE],
            [sum(exact[:most + 1]) for most in (10, 15, 20, 25, 30, 40, 49)])
        by_atoms = {}
        for atoms, _joiners in rows(max_atoms=3):
            by_atoms[len(atoms)] = by_atoms.get(len(atoms), 0) + 1
        self.assertEqual({1: 22, 2: 1932, 3: 162404}, by_atoms)

    def test_the_earlier_record_is_1_in_20_million_of_it(self):
        record = R49._pairs(ATOMS, JOINERS)
        self.assertEqual(3682, len(record))
        self.assertEqual(20117417, CLOSURE // len(record))
        # Every script of the record is a row of the closure.
        built = {text(atoms, joiners) for atoms, joiners in rows(max_atoms=3)}
        self.assertTrue(set(record) <= built)

    def test_the_counted_rows_are_the_generated_rows(self):
        # The count is a sum over lengths, and the rows are a
        # walk. At 25 characters they are the same number.
        exact = count_by_length(25)
        made = [text(atoms, joiners) for atoms, joiners in rows(max_chars=25)]
        self.assertEqual(sum(exact), len(made))
        self.assertEqual(len(made), len(set(made)))
        self.assertTrue(all(len(script) <= 25 for script in made))


class TheMachine(unittest.TestCase):
    """M's 2 forms, its states and its steps."""

    @classmethod
    def setUpClass(cls):
        cls.table = denotation("/where/the/job/runs", "/its/home")

    def test_the_2_forms_agree_and_every_step_is_taken(self):
        taken, states = set(), set()
        for atoms, joiners in rows(max_atoms=3):
            walked, result = steps(atoms, joiners, self.table)
            self.assertEqual(run(atoms, joiners, self.table), result)
            taken.update(walked)
        states = {state for state, _joiner, _atom in taken}
        self.assertEqual(4, len(states))
        self.assertEqual(4 * len(JOINERS) * len(ATOMS), len(taken))
        self.assertEqual(352, len(taken))

    def test_the_step_rows_take_each_step_once(self):
        seen = {}
        for state, (atoms, joiners) in step_rows():
            self.assertLessEqual(len(text(atoms, joiners)), BOUND)
            walked, _result = steps(atoms, joiners, self.table)
            self.assertEqual(state, walked[-1][0])
            seen[walked[-1]] = seen.get(walked[-1], 0) + 1
        self.assertEqual(352, len(seen))
        self.assertEqual({1}, set(seen.values()))

    def test_the_atoms_keep_no_state(self):
        # Premise P-a, as a fact about 22 short texts: no atom
        # sets a variable, changes the directory, reads its
        # input, or writes anywhere but to its output and to
        # /dev/null.
        for atom in ATOMS:
            self.assertIsNone(re.search(
                r"\b(cd|export|exec|read|set|shopt|unset|trap|exit"
                r"|return|eval|source|pushd|popd|alias|declare|local"
                r"|cat|tee)\b|\$\{?[A-Za-z_]+\}?=|[A-Za-z_]=|>>|<",
                atom), atom)
            if ">" in atom:
                self.assertTrue(atom.endswith("> /dev/null"), atom)
        self.assertEqual(
            ["false"],
            [atom for atom in ATOMS if self.table[atom][1] != 0])
        self.assertEqual(
            ["echo $HOME", "echo ${HOME}", "pwd"],
            sorted(atom for atom in ATOMS
                   if denotation("x", "y")[atom]
                   != denotation("p", "q")[atom]))


class TheShellAgreesWithTheMachine(unittest.TestCase):
    """The real bash, asked on every step of M and on a
    sample of the rest."""

    def shell(self, asked):
        with tempfile.TemporaryDirectory() as folder:
            cwd = os.path.join(folder, "cwd")
            os.mkdir(cwd)
            table = denotation(os.path.realpath(cwd), ENV["HOME"])
            got = in_the_shell([text(*row) for row in asked], cwd)
        return [(row, run(row[0], row[1], table), result)
                for row, result in zip(asked, got)]

    # The shell legs are POSIX-only, as the earlier rung's
    # are: on Windows the bash name is answered by the WSL
    # launcher, which is not a bash.
    @unittest.skipIf(os.name == "nt", "POSIX only")
    def test_bash_takes_every_step_of_m_as_m_does(self):
        asked = [row for _state, row in step_rows()]
        for row, want, got in self.shell(asked):
            self.assertEqual(want, got, text(*row))

    @unittest.skipIf(os.name == "nt", "POSIX only")
    def test_bash_agrees_on_every_row_of_up_to_2_atoms(self):
        asked = list(rows(max_atoms=2))
        self.assertEqual(1954, len(asked))
        wrong = [text(*row) for row, want, got in self.shell(asked)
                 if want != got]
        self.assertEqual([], wrong)

    @unittest.skipIf(os.name == "nt", "POSIX only")
    def test_bash_agrees_on_a_sample_of_the_long_rows(self):
        # 2,000 rows drawn the same way on every run, each of
        # 4 atoms or more, and the 1 row of 17 atoms.
        rng = random.Random(20261119)
        asked = {((":",) * 17, (SEMI,) * 16)}
        while len(asked) < 2001:
            atoms, joiners = [rng.choice(ATOMS)], []
            length = len(atoms[0])
            while True:
                fits = [(joiner, atom) for joiner in JOINERS
                        for atom in ATOMS
                        if length + len(joiner) + len(atom) <= BOUND]
                if not fits or rng.random() < 0.15:
                    break
                joiner, atom = rng.choice(fits)
                atoms.append(atom)
                joiners.append(joiner)
                length += len(joiner) + len(atom)
            if len(atoms) >= 4:
                asked.add((tuple(atoms), tuple(joiners)))
        asked = sorted(asked)
        self.assertEqual(17, max(len(row[0]) for row in asked))
        wrong = [text(*row) for row, want, got in self.shell(asked)
                 if want != got]
        self.assertEqual([], wrong)


class TheRunnerReturnsTheMachinesResult(unittest.TestCase):
    """The real gate and the real execution, asked on every
    step of M. Confinement is set to off for these runs: they
    ask whether the runner returns what the script did, and
    the atoms touch nothing a confinement would deny."""

    @classmethod
    def setUpClass(cls):
        cls.payload, cls.job_id = honest_job()

    @unittest.skipIf(os.name == "nt", "POSIX only")
    def test_the_runner_returns_m_s_result_on_every_step(self):
        asked = [row for _state, row in step_rows()]
        asked += [((atom,), ()) for atom in ATOMS]
        home = os.environ.get("HOME", "")
        for atoms, joiners in asked:
            script = text(atoms, joiners)
            got, where = ask_the_runner(self.payload, self.job_id, script,
                                        extra=OFF)
            self.assertIsNotNone(got, script)
            self.assertIsNotNone(where, script)
            out, status = run(atoms, joiners,
                              denotation(os.path.realpath(where), home))
            # The default view: the exit code and the digest of
            # the output leave, and the output stays home.
            self.assertEqual(
                (status, hashlib.sha384(out.encode("utf-8")).hexdigest(),
                 "attested", "", ""),
                (got.get("exit_code"), got.get("output_digest"),
                 got.get("view"), got.get("stdout"), got.get("stderr")),
                script)


class TheDoorAtTheBound(unittest.TestCase):
    """B1: the software holds the bound as a constraint today."""

    @classmethod
    def setUpClass(cls):
        cls.payload, cls.job_id = honest_job()

    def test_the_startup_check_puts_no_floor_under_the_bound(self):
        for cap in RUNGS + (1,):
            self.assertIsNone(
                RUNNER._validate_size_caps({"max_script_bytes": cap}), cap)
        self.assertIsNotNone(
            RUNNER._validate_size_caps({"max_script_bytes": -1}))

    def test_at_50_bytes_every_length_is_decided_by_the_bound(self):
        for length in range(1, 52):
            ok, notes = admitted(self.payload, self.job_id, "#" * length, 50)
            self.assertEqual(length <= 50, ok, length)
        self.assertIn(
            "rejecting seq 3: script exceeds max_script_bytes (51 > 50)",
            notes)

    def test_at_500_and_5000_the_edge_is_the_bound(self):
        for cap in (500, 5000):
            for length in (1, cap - 1, cap, cap + 1, cap + 2):
                ok, _notes = admitted(self.payload, self.job_id,
                                      "#" * length, cap)
                self.assertEqual(length <= cap, ok, (cap, length))

    def test_where_a_character_is_wide_the_bytes_decide(self):
        for cap in RUNGS:
            for char, width in (("é", 2), ("€", 3),
                                ("\U0001f600", 4)):
                for count in (cap // width - 1, cap // width,
                              cap // width + 1):
                    script = char * count
                    ok, _notes = admitted(self.payload, self.job_id,
                                          script, cap)
                    self.assertEqual(count * width <= cap, ok,
                                     (cap, width, count))
            # As many characters as the bound, and 1 byte more.
            script = "#" * (cap - 1) + "é"
            self.assertEqual((cap, cap + 1),
                             (len(script), len(script.encode("utf-8"))))
            ok, _notes = admitted(self.payload, self.job_id, script, cap)
            self.assertFalse(ok, cap)


class TheFuzzDataAtTheRungs(unittest.TestCase):
    """B4: where the corpus's scripts stand on the 3 rungs."""

    def test_the_corpus_s_scripts_stand_on_the_first_rung(self):
        sizes = corpus_scripts()
        self.assertGreater(len(sizes), 400)
        first = sum(1 for size in sizes if size <= 50)
        second = sum(1 for size in sizes if 50 < size <= 500)
        # More than 9 in 10 at the first rung, and fewer on the
        # second rung than 1 in 20: the evidence for scripts is
        # where the first proof is.
        self.assertGreater(first * 10, len(sizes) * 9)
        self.assertLess(second * 20, len(sizes))


class ThePageRecordsTheMeasure(unittest.TestCase):
    """The figures this module computes are the page's."""

    def test_the_page_states_what_was_counted_and_run(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "74,072,330,493 scripts of at most 49 characters",
                "| 25 | 252,747 |",
                "4 × 4 × 22 = 352 steps",
                "858,319 scripts",
                "0 disagreements"):
            self.assertIn(stated, page, stated)


if __name__ == "__main__":
    unittest.main()
