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
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.guard.sandbox import WORK_MOUNT  # noqa: E402
from runner.tests import test_v4_at_a_bound as BOUND  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402
from runner.tests import test_v4_the_folder as FOLDER  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-place.md")
PLACE = ("pwd", "echo $HOME", "echo ${HOME}", "printf x")


def digest(text):
    return hashlib.sha384(text.encode("utf-8")).hexdigest()


def machine(atoms, joiners, cwd, home):
    out, status = BOUND.run(atoms, joiners, BOUND.denotation(cwd, home))
    return status, digest(out)


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
        for atom in PLACE:
            result, notes, _files = FOLDER.run(
                self.payload, self.job_id, atom, "enforce")
            if not FOLDER.ENGAGES:
                self.assertIsNone(result, atom)
                self.assertTrue(
                    any("cannot engage" in note or "unavailable" in note
                        for note in notes),
                    notes)
                continue
            self.expect(result, notes, (atom,), (), WORK_MOUNT)
        if not FOLDER.ENGAGES:
            return
        result, notes, _files = FOLDER.run(
            self.payload, self.job_id, "pwd; printf x", "enforce")
        self.expect(result, notes, ("pwd", "printf x"), ("; ",),
                    WORK_MOUNT)

    def test_off_pwd_is_the_host_folder_and_not_the_mount(self):
        result, notes, _files = FOLDER.run(
            self.payload, self.job_id, "pwd", "off")
        where = None
        for note in notes:
            found = re.search(r"cwd=(\S+)", note)
            if found:
                where = os.path.realpath(found.group(1))
        self.assertIsNotNone(where, notes)
        self.expect(result, notes, ("pwd",), (), where)
        self.assertNotEqual(where, WORK_MOUNT)
        _status, host = machine(("pwd",), (), where, self.home)
        _status, mount = machine(("pwd",), (), WORK_MOUNT, self.home)
        self.assertNotEqual(host, mount)
        self.assertEqual(host, result.get("output_digest"))

    def test_the_page_states_the_place(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "It adds no atom and no constraint.",
                "the work mount, `/work`",
                "`pwd`, `echo $HOME` and `echo ${HOME}`",
                "The other 19 atoms do not read the place.",
                "The default cap stays 1,048,576."):
            self.assertIn(stated, page, stated)


if __name__ == "__main__":
    unittest.main()
