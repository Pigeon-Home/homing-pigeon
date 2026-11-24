# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The corpus controls: one entry the reader must accept and one
it must refuse, per target that has a pair (23 November 2026).

The research mail of 23 November 2026 named the controls a corpus
claim needs: a positive control, a negative control, and the
discipline that neither is taken on trust. runner/tools/
de_dust_corpus.py builds the pair (its Controls section); this
module pins the pair against the live reader, through the same
paths the corpus itself travels: the checker directly, a Session
run, and a corpus file written and read back by the tool's own
load. The last test breaks a reader on purpose and pins that the
controls catch it: a control that cannot fail is decoration.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tools import de_dust_corpus as B  # noqa: E402


class ControlPairTest(unittest.TestCase):
    """The pair itself: shape, provenance, and the two outcomes."""

    def test_every_registered_target_is_a_real_target(self):
        for target in B.CONTROL_PAIRS:
            self.assertIn(target, B.TARGETS)

    def test_the_pair_is_two_distinct_control_entries(self):
        for target in B.CONTROL_PAIRS:
            pair = B.control_entries(target)
            self.assertIsNotNone(pair, target)
            positive, negative = pair
            self.assertNotEqual(positive["id"], negative["id"],
                                target)
            for entry, origin in ((positive, "control:positive"),
                                  (negative, "control:negative")):
                self.assertEqual(entry["mutator"], "control", target)
                self.assertEqual(entry["from"], origin, target)
                self.assertEqual(entry["id"],
                                 B.entry_id(entry["kind"],
                                            entry["data"]), target)

    def test_positive_accepted_and_negative_refused(self):
        for target in B.CONTROL_PAIRS:
            with self.subTest(target=target):
                self.assertEqual(B.check_controls(target),
                                 ("accepted", "refused"))

    def test_a_target_without_a_pair_names_the_gap(self):
        self.assertIsNone(B.control_entries("dtls"))
        with self.assertRaises(B.Crash) as caught:
            B.check_controls("dtls")
        self.assertEqual(caught.exception.kind, "control")


class ControlPathsTest(unittest.TestCase):
    """The controls through the corpus's own machinery."""

    def test_through_a_session(self):
        for target in B.CONTROL_PAIRS:
            with self.subTest(target=target):
                positive, negative = B.control_entries(target)
                session = B.Session(target, [positive, negative])
                B._with_rig(lambda: [
                    session.run(e, trace=False)
                    for e in (positive, negative)])
                self.assertEqual(session.outcomes["accepted"], 1,
                                 target)
                self.assertEqual(session.outcomes["refused"], 1,
                                 target)
                self.assertEqual(session.crashes, [], target)

    def test_through_a_corpus_file_and_back(self):
        # Written by the tool's save, read by the tool's load: the
        # pair that comes back still calibrates the reader.
        for target in B.CONTROL_PAIRS:
            with self.subTest(target=target):
                pair = list(B.control_entries(target))
                with tempfile.TemporaryDirectory() as td:
                    path = os.path.join(td, target + ".jsonl")
                    B.save(path, target, pair)
                    back = B.load(path)
                self.assertEqual([e["id"] for e in back],
                                 [e["id"] for e in pair], target)
                got = tuple(B.check(target, e) for e in back)
                self.assertEqual(got, ("accepted", "refused"),
                                 target)


class ControlsBiteTest(unittest.TestCase):
    """A reader gone uniformly one way fails its controls."""

    def _broken(self, target, outcome):
        spec = dict(B.TARGETS[target])
        spec["check"] = lambda entry: outcome
        return mock.patch.dict(B.TARGETS, {target: spec})

    def test_an_accept_everything_reader_is_caught(self):
        for target in B.CONTROL_PAIRS:
            with self.subTest(target=target):
                with self._broken(target, "accepted"):
                    with self.assertRaises(B.Crash) as caught:
                        B.check_controls(target)
                self.assertEqual(caught.exception.kind, "control")

    def test_a_refuse_everything_reader_is_caught(self):
        for target in B.CONTROL_PAIRS:
            with self.subTest(target=target):
                with self._broken(target, "refused"):
                    with self.assertRaises(B.Crash) as caught:
                        B.check_controls(target)
                self.assertEqual(caught.exception.kind, "control")


if __name__ == "__main__":
    unittest.main()
