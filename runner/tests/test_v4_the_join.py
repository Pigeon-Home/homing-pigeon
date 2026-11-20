#!/usr/bin/env python3
"""The join between the gate and the machine M.

docs/infrastructure-documents/proofs/v4-the-join.md states one
sentence. A message that fails C5 never reaches M. A message
that passes C5 reaches M only when its script is at most N
bytes, and the script M is given is that script. N is
max_script_bytes. No new constraint is added.
"""
import copy
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tests import test_v4_at_a_bound as BOUND  # noqa: E402
from runner.tests import test_v4_before_the_mac as PRE  # noqa: E402
from runner.tests import test_v4_bindings as BIND  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-join.md")
RUNGS = (50, 500, 5000)


def raw(payload, job_id, script, turn):
    """The corpus job, its script replaced, signed again.
    With turn, one digit of that signature is changed."""
    job = copy.deepcopy(payload)
    job["script"] = script
    text = BIND._signed(job)
    if text is None:
        raise AssertionError("the signer refused the job")
    if turn:
        text = PRE._turned(text)
    return PRE._mail(PRE._subject(job_id), text)


class TheJoin(unittest.TestCase):
    """C5 is the only door into M, and C2 is the size of what
    is handed through it."""

    @classmethod
    def setUpClass(cls):
        cls.payload, cls.job_id = BOUND.honest_job()

    def arrive(self, script, cap, turn):
        body = raw(self.payload, self.job_id, script, turn)
        with tempfile.TemporaryDirectory() as folder:
            return PRE.arrive(
                body, folder, cfg_extra={"max_script_bytes": cap})

    def test_a_bad_signature_never_reaches_the_machine(self):
        for cap in RUNGS:
            for script in ("#" * cap, "#" * (cap + 1)):
                out = self.arrive(script, cap, turn=True)
                self.assertEqual([], out.executed, (cap, len(script)))
                refusals = [note for note in out.notes
                            if "rejecting" in note]
                self.assertEqual(1, len(refusals), (cap, len(script)))
                self.assertIn("bad signature", refusals[0])
                self.assertNotIn("max_script_bytes", refusals[0])

    def test_a_script_over_the_bound_never_reaches_the_machine(self):
        for cap in RUNGS:
            script = "#" * (cap + 1)
            out = self.arrive(script, cap, turn=False)
            self.assertEqual([], out.executed, cap)
            self.assertTrue(
                any("script exceeds max_script_bytes (%d > %d)"
                    % (cap + 1, cap) in note for note in out.notes),
                out.notes)

    def test_a_script_at_the_bound_is_the_script_m_is_given(self):
        for cap in RUNGS:
            script = "#" * cap
            out = self.arrive(script, cap, turn=False)
            self.assertEqual(1, len(out.executed), cap)
            handed = out.executed[0]["script"]
            self.assertEqual(script, handed)
            self.assertLessEqual(len(handed.encode("utf-8")), cap)

    def test_the_bound_counts_bytes(self):
        under = "é" * 25
        over = "é" * 26
        self.assertEqual((50, 52),
                         (len(under.encode("utf-8")),
                          len(over.encode("utf-8"))))
        held = self.arrive(under, 50, turn=False)
        self.assertEqual([under],
                         [job["script"] for job in held.executed])
        refused = self.arrive(over, 50, turn=False)
        self.assertEqual([], refused.executed)
        self.assertTrue(
            any("script exceeds max_script_bytes (52 > 50)" in note
                for note in refused.notes),
            refused.notes)

    def test_the_page_states_the_sentence(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "A message that fails C5 never reaches M.",
                "adds no constraint",
                "The default in the code stays 1,048,576.",
                "| N bytes, signature turned | no |",
                "| N bytes, signature good | yes, that script |",
                "26 copies of é, N = 50 (52 bytes)"):
            self.assertIn(stated, page, stated)


if __name__ == "__main__":
    unittest.main()
