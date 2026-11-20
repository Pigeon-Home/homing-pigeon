#!/usr/bin/env python3
"""The place M is given when confinement is on.

docs/infrastructure-documents/proofs/v4-the-place.md. With
confinement off, pwd prints the host path of the job's folder.
With confinement enforce, the folder M is given is the work
mount. HOME is the HOME the runner passes in. No new atom and
no new constraint.
"""
import hashlib
import os
import random
import re
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.guard.sandbox import WORK_MOUNT  # noqa: E402
from runner.tests import test_v4_at_a_bound as BOUND  # noqa: E402
from runner.tests import test_v4_at_a_limit as LIMIT  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402
from runner.tests import test_v4_the_folder as FOLDER  # noqa: E402
from runner.tests import test_v4_the_grammar as GRAMMAR  # noqa: E402
from runner.tests import test_v4_the_ladder as LADDER  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-place.md")


def digest(text):
    return hashlib.sha384(text.encode("utf-8")).hexdigest()


def machine(atoms, joiners, cwd, home):
    out, status = BOUND.run(atoms, joiners, BOUND.denotation(cwd, home))
    return status, digest(out)


@unittest.skipUnless(FOLDER.LINUX, "the place and the folder are the "
                                   "Linux sandbox's")
class ThePlace(unittest.TestCase):
    """Enforce stands M on the work mount. Off stands it on
    the host folder."""

    @classmethod
    def setUpClass(cls):
        cls.payload, cls.job_id = BOUND.honest_job()
        cls.home = os.environ.get("HOME", "")

    def expect(self, result, notes, atoms, joiners, cwd):
        self.assertIsNotNone(result, notes)
        status, out = machine(atoms, joiners, cwd, self.home)
        self.assertEqual(
            (status, out, "attested"),
            (result.get("exit_code"), result.get("output_digest"),
             result.get("view")),
            (atoms, cwd))

    def test_the_work_mount_is_the_place_the_page_names(self):
        self.assertEqual("/work", WORK_MOUNT)

    def test_under_enforce_the_place_is_the_work_mount(self):
        if not FOLDER.ENGAGES:
            result, notes, _files = FOLDER.run(
                self.payload, self.job_id, "pwd", "enforce")
            FOLDER.refused_under_enforce(self, result)
            self.assertTrue(
                any("cannot engage" in note or "unavailable" in note
                    for note in notes),
                notes)
            return
        for atom in BOUND.ATOMS:
            result, notes, _files = FOLDER.run(
                self.payload, self.job_id, atom, "enforce")
            self.expect(result, notes, (atom,), (), WORK_MOUNT)
        result, notes, _files = FOLDER.run(
            self.payload, self.job_id, "pwd; printf x", "enforce")
        self.expect(result, notes, ("pwd", "printf x"), ("; ",),
                    WORK_MOUNT)

    def test_every_step_of_m_under_enforce(self):
        if not FOLDER.ENGAGES:
            self.skipTest("the sandbox does not engage here")
        table = BOUND.denotation(WORK_MOUNT, self.home)
        asked = list(BOUND.step_rows())
        self.assertEqual(352, len(asked))
        for state, (atoms, joiners) in asked:
            script = BOUND.text(atoms, joiners)
            result, notes, _files = FOLDER.run(
                self.payload, self.job_id, script, "enforce")
            out, status = BOUND.run(atoms, joiners, table)
            self.assertIsNotNone(result, script)
            self.assertEqual(
                (status, digest(out), "attested"),
                (result.get("exit_code"), result.get("output_digest"),
                 result.get("view")),
                script)
            walked, _result = BOUND.steps(atoms, joiners, table)
            self.assertEqual((state, joiners[-1], atoms[-1]),
                             walked[-1], script)

    def test_long_rows_under_enforce_are_m_at_the_work_mount(self):
        if not FOLDER.ENGAGES:
            self.skipTest("the sandbox does not engage here")
        exact = LIMIT.exact_counts(5000)
        rng = random.Random(20261119)
        table = BOUND.denotation(WORK_MOUNT, self.home)
        drawn = []
        for size, count in ((50, 8), (500, 8), (5000, 4)):
            for _draw in range(count):
                atoms, joiners = LIMIT.draw_exact(size, exact, rng)
                script = BOUND.text(atoms, joiners)
                self.assertEqual(size, len(script))
                self.assertEqual((atoms, joiners), GRAMMAR.cut(script))
                drawn.append((atoms, joiners, script))
        self.assertEqual(20, len(drawn))
        for atoms, joiners, script in drawn:
            result, notes, _files = FOLDER.run(
                self.payload, self.job_id, script, "enforce")
            out, status = BOUND.run(atoms, joiners, table)
            self.assertLessEqual(len(out), LIMIT.KEPT, script[:40])
            self.assertIsNotNone(result, script[:40])
            self.assertEqual(
                (status, digest(out), "attested"),
                (result.get("exit_code"), result.get("output_digest"),
                 result.get("view")),
                script[:40])

    # The rows are run by the real bash, as the first rung's
    # shell legs are.
    @unittest.skipIf(os.name == "nt", "POSIX only")
    def test_off_the_host_folder_differs_only_for_pwd(self):
        for atom in BOUND.ATOMS:
            result, notes, _files = FOLDER.run(
                self.payload, self.job_id, atom, "off")
            where = None
            for note in notes:
                found = re.search(r"cwd=(\S+)", note)
                if found:
                    where = os.path.realpath(found.group(1))
            self.assertIsNotNone(where, notes)
            self.expect(result, notes, (atom,), (), where)
            _status, host = machine((atom,), (), where, self.home)
            _status, mount = machine((atom,), (), WORK_MOUNT, self.home)
            self.assertEqual(host, result.get("output_digest"), atom)
            if atom == "pwd":
                self.assertNotEqual(host, mount)
            else:
                self.assertEqual(host, mount, atom)

    def test_the_ladders_first_families_under_enforce(self):
        if not FOLDER.ENGAGES:
            self.skipTest("the sandbox does not engage here")
        table = BOUND.denotation(WORK_MOUNT, self.home)
        rows = [row for row in LADDER.ladder_rows(17, families=20)
                if len(row[0]) in (55, 1597)]
        self.assertEqual(40, len(rows))
        # The runner's watch counts the processes of a job's tree
        # at the job's start and once each second, and kills a
        # tree of more than 64 (finding F20, v4-the-bars.md). A
        # row that is 1 pipeline of 1,597 commands is such a tree
        # for as long as it runs, so the watch killed it on a slow
        # run and let it pass on a quick 1. This test asks the
        # place and not the watch: the watch's ceiling is put out
        # of the rows' reach.
        with mock.patch.object(FOLDER.RUNNER._remediation,
                               "DEFAULT_STORM_CEILING", 1 << 20):
            for atoms, joiners in rows:
                script = BOUND.text(atoms, joiners)
                result, notes, _files = FOLDER.run(
                    self.payload, self.job_id, script, "enforce")
                out, status = BOUND.run(atoms, joiners, table)
                self.assertIsNotNone(result, notes)
                self.assertEqual(
                    (status, digest(out), "attested"),
                    (result.get("exit_code"),
                     result.get("output_digest"), result.get("view")),
                    script[:40])

    def test_the_trace_inside_the_sandbox_names_the_commands(self):
        if not FOLDER.ENGAGES:
            result, _notes, files = FOLDER.run(
                self.payload, self.job_id, "true", "enforce")
            FOLDER.refused_under_enforce(self, result)
            self.assertNotIn("trace", files)
            return
        from collections import Counter
        asked = (
            ("false", "echo a", BOUND.AND, True),
            ("echo $(:)", "true", BOUND.PIPE, False),
        )
        for first, second, way, order_holds in asked:
            atoms = [None, (first,), (second,)]
            joiners = [None, (), ()]
            for step in range(3, 11):
                atoms.append(atoms[step - 1] + atoms[step - 2])
                joiners.append(joiners[step - 1] + (way,)
                               + joiners[step - 2])
            script = (
                "trap 'printf \"%s\\n\" \"$BASH_COMMAND\" >> trace' DEBUG\n"
                "set -T\n"
                + BOUND.text(atoms[10], joiners[10]) + "\n")
            result, notes, files = FOLDER.run(
                self.payload, self.job_id, script, "enforce")
            self.assertIsNotNone(result, notes)
            lines = files.get("trace", b"").decode("utf-8").splitlines()
            self.assertEqual(["set -T"], lines[:1], first)
            body = lines[1:]
            expect = LADDER.commands_of(atoms[10], joiners[10])
            self.assertEqual(Counter(expect), Counter(body), first)
            if order_holds:
                self.assertEqual(expect, body, first)

    def test_the_page_states_the_place(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "It adds no atom and no constraint.",
                "the work mount, `/work`",
                "`pwd`, `echo $HOME` and `echo ${HOME}`",
                "The other 19 atoms do not read the place.",
                "All 22 atoms were run, on and off.",
                "There are 352.",
                "8 of 50 characters, 8 of 500, and 4 of 5,000.",
                "Step 10 is 55 atoms and step 17 is 1,597.",
                "The commands that ran are M's.",
                "The default cap stays 1,048,576."):
            self.assertIn(stated, page, stated)


if __name__ == "__main__":
    unittest.main()
