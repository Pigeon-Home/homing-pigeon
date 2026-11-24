#!/usr/bin/env python3
"""The join between the gate and the machine M.

docs/infrastructure-documents/proofs/v4-the-join.md states one
sentence. A message that fails C5 never reaches M. A message
that passes C5 reaches M only when its script is at most N
bytes and every other applicable gate in P1 also passes, and
the script M is given is that script. N is max_script_bytes.
No new constraint is added.
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

    def arrive_payload(self, payload, script, extra=None, seen=None,
                       policies=None, folder=None):
        """1 arrival of a varied corpus job, signed again, at a
        script cap of 50 unless `extra` says otherwise."""
        body = raw(payload, self.job_id, script, False)
        cfg = {"max_script_bytes": 50}
        cfg.update(extra or {})
        if folder is not None:
            return PRE.arrive(body, folder, cfg_extra=cfg, seen=seen,
                              policies=policies)
        with tempfile.TemporaryDirectory() as fold:
            return PRE.arrive(body, fold, cfg_extra=cfg, seen=seen,
                              policies=policies)

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

    def test_a_good_signature_and_a_script_at_the_bound_are_not_enough(self):
        # Freshness: the same job, signed again, dated outside
        # the window of C12.
        stale = copy.deepcopy(self.payload)
        stale["issued_at"] = BIND._stamp(-3700)
        out = self.arrive_payload(stale, "#" * 50)
        self.assertEqual([], out.executed)
        self.assertTrue(
            any("issued_at outside allowed window" in note
                for note in out.notes), out.notes)
        # Audience: the same job naming another box, with C10
        # in enforce mode and a runner id configured.
        moved = copy.deepcopy(self.payload)
        moved["aud"] = "other-box"
        out = self.arrive_payload(
            moved, "#" * 50,
            extra={"runner_id": "this-box",
                   "security": {"modes": {"audience": "enforce"}}})
        self.assertEqual([], out.executed)
        self.assertTrue(
            any("security policy (audience)" in note
                for note in out.notes), out.notes)
        # Key policy: the job's kind is exec, and the key's
        # policy under C14 allows ping only.
        out = self.arrive_payload(
            self.payload, "#" * 50,
            policies={"": {"allowed_kinds": ["ping"]}})
        self.assertEqual([], out.executed)
        self.assertTrue(
            any("key policy" in note for note in out.notes),
            out.notes)

    def test_a_second_delivery_of_a_claimed_job_does_not_reach_m_again(self):
        with tempfile.TemporaryDirectory() as folder:
            first = self.arrive_payload(
                self.payload, "#" * 50, folder=folder)
            self.assertEqual(1, len(first.executed))
            second = self.arrive_payload(
                self.payload, "#" * 50, folder=folder,
                seen=first.seen)
            self.assertEqual([], second.executed)

    def test_a_script_cap_of_zero_is_unlimited_not_zero_bytes(self):
        out = self.arrive("#" * 5001, 0, turn=False)
        self.assertEqual(1, len(out.executed))
        self.assertEqual("#" * 5001, out.executed[0]["script"])

    def test_the_page_states_the_sentence(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "A message that fails C5 never reaches M.",
                "adds no constraint",
                "The default in the code stays 1,048,576.",
                "A message that passes C5, and whose script is at "
                "most N bytes, does not reach M on those 2 facts alone.",
                "freshness under C12",
                "the audience decision under C10",
                "key policy under C14",
                "the claim under C15",
                "Once in this handling means the script is handed "
                "to M at most once in that handling.",
                "The words longer than N are read with N > 0: at "
                "N = 0 the cap is off",
                "its UTF-8 length satisfies N = 0 or "
                "utf8_length(script) <= N",
                "no unconditional claim of exactly once across "
                "deliveries",
                "| N bytes, signature turned | no |",
                "| N bytes, signature good | yes, that script |",
                "| N bytes, signature good, stale under C12 | no |",
                "| N bytes, signature good, wrong audience with "
                "C10 in enforce mode | no |",
                "| N bytes, signature good, kind forbidden by "
                "C14 | no |",
                "| N bytes, signature good, job id already claimed "
                "under C15 | no |",
                "26 copies of é, N = 50 (52 bytes)"):
            self.assertIn(stated, page, stated)


if __name__ == "__main__":
    unittest.main()
