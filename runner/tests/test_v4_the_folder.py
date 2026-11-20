#!/usr/bin/env python3
"""One atom that writes, and the folder it may write in.

docs/infrastructure-documents/proofs/v4-the-folder.md. The atom
is not one of the 22. C18, already defined, says the job's
folder is the only writable mount when confinement is enforce.
No new constraint.
"""
import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
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
from runner.guard import sandbox as SB  # noqa: E402
from runner.ops import exec as EX  # noqa: E402
from runner.tests import test_proof_conformance as DOOR  # noqa: E402
from runner.tests import test_v4_at_a_bound as BOUND  # noqa: E402
from runner.tests import test_v4_before_the_mac as PRE  # noqa: E402
from runner.tests import test_v4_bindings as BIND  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-folder.md")
INSIDE = "printf x > kept"
ENGAGES = SB.startup_problem() is None


def refused_under_enforce(case, result):
    """Where the sandbox does not engage, the runner is not
    silent under enforce. It answers with a signed refusal,
    and nothing of the job has run."""
    case.assertIsNotNone(result)
    case.assertEqual(-2, result.get("exit_code"))
    case.assertEqual("", result.get("stdout"))
    case.assertIn("confinement cannot engage", result.get("stderr", ""))


def run(payload, job_id, script, mode):
    """1 job through the real gate and the real execution.
    (the result, the log lines, the files left in the job's
    folder)."""
    job = copy.deepcopy(payload)
    job["script"] = script
    job["interpreter"] = ["bash"]
    job.pop("shell", None)
    raw = PRE._mail(PRE._subject(job_id), BIND._signed(job))
    sent, notes, files = [], [], {}
    real_reap = EX.reap_work_dir

    def snap(work):
        if os.path.isdir(work):
            for name in os.listdir(work):
                path = os.path.join(work, name)
                if os.path.isfile(path):
                    with open(path, "rb") as handle:
                        files[name] = handle.read()
        return real_reap(work)

    with tempfile.TemporaryDirectory() as folder:
        cfg = {"mailbox_user": "t@example.com", "base_dir": folder,
               "oracle_opinion_mode": "off",
               "security": {"modes": {"confinement": mode}}}
        cfg.update(BIND.KEYS)
        RUNNER._set_allow_cleartext_jobs(True)
        try:
            with mock.patch.object(
                    RUNNER, "send_mail",
                    lambda _smtp, _cfg, subject, body, to=None:
                    sent.append(body)), \
                mock.patch.object(
                    RUNNER, "log",
                    lambda msg, level="INFO": notes.append(msg)), \
                mock.patch.object(EX, "reap_work_dir", snap), \
                    contextlib.redirect_stdout(io.StringIO()):
                RUNNER.handle_mail(
                    cfg, DOOR._IMAP2(), DOOR._SMTP2(), 3, raw, folder, {},
                    RUNNER.build_secrets(cfg),
                    Namespace(dry_run=False, no_send=False), None)
        finally:
            RUNNER._set_allow_cleartext_jobs(False)
    result = json.loads(sent[0]) if sent else None
    return result, notes, files


class TheFolder(unittest.TestCase):
    """The writer stays in the job's folder, or the job is
    refused."""

    @classmethod
    def setUpClass(cls):
        cls.payload, cls.job_id = BOUND.honest_job()

    def test_the_atom_is_not_one_of_the_22(self):
        self.assertNotIn(INSIDE, BOUND.ATOMS)
        self.assertEqual(22, len(BOUND.ATOMS))

    def test_a_write_inside_the_folder(self):
        result, notes, files = run(
            self.payload, self.job_id, INSIDE, "enforce")
        if not ENGAGES:
            refused_under_enforce(self, result)
            self.assertTrue(
                any("cannot engage" in note or "unavailable" in note
                    for note in notes),
                notes)
            self.assertNotIn("kept", files)
            return
        self.assertIsNotNone(result, notes)
        self.assertEqual(0, result.get("exit_code"), notes)
        self.assertEqual(b"x", files.get("kept"), sorted(files))
        self.assertTrue(any("sandbox" in note for note in notes), notes)

    def test_a_write_outside_does_not_land_on_the_host(self):
        host = tempfile.mkdtemp(prefix="hp-proof-escape-")
        target = os.path.join(host, "escape")
        script = "printf y > %s" % target
        try:
            result, notes, _files = run(
                self.payload, self.job_id, script, "enforce")
            self.assertFalse(os.path.exists(target), notes)
            if not ENGAGES:
                refused_under_enforce(self, result)
                return
            self.assertIsNotNone(result, notes)
            # The same script, confinement off, does write on
            # the host. That is the difference.
            run(self.payload, self.job_id, script, "off")
            with open(target, "rb") as handle:
                self.assertEqual(b"y", handle.read())
        finally:
            shutil.rmtree(host, ignore_errors=True)

    def test_the_writer_after_all_22_stays_in_the_folder(self):
        atoms = BOUND.ATOMS
        joiners = ("; ",) * (len(atoms) - 1)
        prefix = BOUND.text(atoms, joiners)
        result, notes, files = run(
            self.payload, self.job_id, prefix + "; printf x > kept",
            "enforce")
        if not ENGAGES:
            refused_under_enforce(self, result)
            self.assertNotIn("kept", files)
            return
        out, status = BOUND.run(
            atoms, joiners,
            BOUND.denotation(SB.WORK_MOUNT, os.environ.get("HOME", "")))
        digest = hashlib.sha384(out.encode("utf-8")).hexdigest()
        self.assertEqual(0, result.get("exit_code"), notes)
        self.assertEqual(status, result.get("exit_code"))
        self.assertEqual(digest, result.get("output_digest"), notes)
        self.assertEqual(b"x", files.get("kept"), sorted(files))
        host = tempfile.mkdtemp(prefix="hp-proof-escape-")
        target = os.path.join(host, "escape")
        try:
            run(self.payload, self.job_id,
                prefix + "; printf y > %s" % target, "enforce")
            self.assertFalse(os.path.exists(target))
        finally:
            shutil.rmtree(host, ignore_errors=True)

    def test_each_atom_after_the_writer_leaves_the_file(self):
        if not ENGAGES:
            result, _notes, files = run(
                self.payload, self.job_id,
                "printf x > kept; true", "enforce")
            refused_under_enforce(self, result)
            self.assertNotIn("kept", files)
            return
        table = BOUND.denotation(
            SB.WORK_MOUNT, os.environ.get("HOME", ""))
        for atom in BOUND.ATOMS:
            result, notes, files = run(
                self.payload, self.job_id,
                "printf x > kept; " + atom, "enforce")
            out, status = BOUND.run((atom,), (), table)
            digest = hashlib.sha384(out.encode("utf-8")).hexdigest()
            self.assertEqual(b"x", files.get("kept"), atom)
            self.assertEqual(status, result.get("exit_code"), atom)
            self.assertEqual(digest, result.get("output_digest"), notes)

    def test_the_page_states_the_atom_and_c18(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "No new constraint.",
                "`printf x > kept`",
                "This is C18, already defined.",
                "The 22 atoms are not changed",
                "after all 22, joined on with `; `",
                "The file still holds `x`.",
                "The default cap stays 1,048,576."):
            self.assertIn(stated, page, stated)


if __name__ == "__main__":
    unittest.main()
