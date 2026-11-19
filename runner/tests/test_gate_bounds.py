# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The gate's bounds in front of the MAC (the v4 proofs'
candidate C32, and finding F12).

F12 is the one unbounded thing the v4 measure found at the
gate: a refused message's whole subject is written to the log,
so the log grows with the subject. The v4 suite pins that as
it stands. What this family pins, on main, is everything
around it that IS bounded, over the shapes a fuzz-found bug
earns: a family derived at run time from the tables below
(subject growths, body growths, bookend wrappings in the
campaign's bookend shape, signature shapes, and the size
cap's own rungs). For every refused arrival, however the
message grew: nothing runs, nothing is sent, the seen set is
untouched, the mail is marked seen exactly once, exactly one
refusal record is kept and it stays under the supposed bound
(200 bytes), it is the only file under the runner's base, no
sealed body is opened before its signature verifies, the MAC
is computed at most twice per key held, and the parser is
given at most 16 times the message's length. Over the size
cap, the refusal happens in front of the MAC: no MAC at all,
no submission line, no record, the mark still set.
"""
import os
import shutil
import string
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.tools import de_dust_corpus as DD  # noqa: E402

_SUBJECT = "[HOMING-PIGEON] job bm-exec-0001"
_JOB = DD._job(script="echo gate")
_KEYS_HELD = len(DD.SECRETS)


def _wrong_signed(script="echo gate"):
    return DD.V.sign_payload(DD._job(script=script), DD.WRONG)


def _raw(subject, body):
    return DD._mail(subject, body).encode("utf-8", "surrogateescape")


class GateBoundsTest(unittest.TestCase):
    """One arrival per derived case, under the campaign's gate
    rig (runner/tools/de_dust_corpus.py's _GateRig), judged by
    the bounded bundle a refusal must keep."""

    def _base(self):
        base = tempfile.mkdtemp(prefix="hp-gate-bounds-")
        self.addCleanup(shutil.rmtree, base, True)
        return base

    def _arrive(self, raw, cap=None):
        base = self._base()
        cfg = dict(DD._GATE_CFG, base_dir=base)
        if cap is not None:
            cfg["max_job_bytes"] = cap
        rig = DD._GateRig()
        seen = {}
        imap = DD._gate_arrive(rig, cfg, raw, base, seen, 3)
        return rig, base, seen, imap

    def _assert_refusal_bundle(self, raw, rig, base, seen, imap):
        self.assertEqual(rig.ran, [])
        self.assertEqual(rig.sent, [])
        self.assertEqual(seen, {})
        self.assertEqual(len(imap.marked), 1)
        events = DD._gate_events(base)
        self.assertEqual(len(events), 1)
        self.assertLessEqual(len(events[0]), DD._GATE_EVENT_MAX)
        self.assertEqual(DD._gate_kept(base), ["security-events.jsonl"])
        self.assertEqual(rig.opens, 0)
        self.assertLessEqual(rig.macs, 2 * _KEYS_HELD)
        self.assertLessEqual(rig.parse_chars, 16 * max(1, len(raw)))

    def test_refusal_stays_bounded_as_the_subject_grows(self):
        cases = []
        for filler in ("x", " ", "é"):
            for count in (0, 1, 10, 100, 1000, 10000, 100000):
                cases.append((filler, count))
        cases.append(("x", 4000000))
        for filler, count in cases:
            with self.subTest(filler=filler, count=count):
                raw = _raw(_SUBJECT + " " + filler * count,
                           _wrong_signed())
                rig, base, seen, imap = self._arrive(raw)
                self._assert_refusal_bundle(raw, rig, base, seen, imap)

    def test_refusal_stays_bounded_under_bookends(self):
        # The campaign's bookend shape: every ASCII punctuation
        # character, a run of ten at the front and the back.
        for ch in string.punctuation:
            with self.subTest(bookend=ch):
                raw = _raw(_SUBJECT + " " + ch * 10 + "x" * 100
                           + ch * 10, _wrong_signed())
                rig, base, seen, imap = self._arrive(raw)
                self._assert_refusal_bundle(raw, rig, base, seen, imap)

    def test_refusal_stays_bounded_as_the_body_grows(self):
        for count in (0, 100, 10000, 100000, 1048575, 1048576,
                      1048577):
            with self.subTest(body=count):
                raw = _raw(_SUBJECT,
                           _wrong_signed("echo " + "y" * count))
                rig, base, seen, imap = self._arrive(raw)
                self._assert_refusal_bundle(raw, rig, base, seen, imap)

    def test_sealed_refusal_stays_bounded_as_the_body_grows(self):
        for count in (0, 1000, 100000, 250000):
            with self.subTest(sealed_body=count):
                sealed = DD._sealed_mail(
                    _SUBJECT, "bm-exec-0001",
                    DD._job(script="echo " + "y" * count), "").decode(
                    "utf-8", "surrogateescape")
                raw = DD._gate_flip_sig(sealed).encode(
                    "utf-8", "surrogateescape")
                rig, base, seen, imap = self._arrive(raw)
                self._assert_refusal_bundle(raw, rig, base, seen, imap)

    def test_signature_shapes_all_refuse_the_same_bounded_way(self):
        signed = DD.V.sign_payload(_JOB, DD.SECRET)
        head, sig = signed.rsplit('"sig":"', 1)
        shapes = {
            "wrong_key": DD.V.sign_payload(_JOB, DD.WRONG),
            "one_digit_turned": DD._gate_flip_sig(signed),
            "truncated": head + '"sig":"' + sig[:48] + '"}',
            "empty": head + '"sig":"' + '"}',
            "not_a_signature": "echo hello, no signed object here",
        }
        for name, body in shapes.items():
            with self.subTest(shape=name):
                raw = _raw(_SUBJECT, body)
                rig, base, seen, imap = self._arrive(raw)
                self._assert_refusal_bundle(raw, rig, base, seen, imap)

    def test_uppercase_signature_verifies_and_still_refuses(self):
        # Hex is case-insensitive (AGENTS.md's sending table): the
        # chain verifies, the cleartext form is refused after the
        # MAC, and the refusal keeps at most one bounded record.
        signed = DD.V.sign_payload(_JOB, DD.SECRET)
        head, sig = signed.rsplit('"sig":"', 1)
        raw = _raw(_SUBJECT, head + '"sig":"' + sig.upper())
        rig, base, seen, imap = self._arrive(raw)
        self.assertEqual(rig.ran, [])
        self.assertEqual(rig.sent, [])
        self.assertEqual(seen, {})
        self.assertEqual(len(imap.marked), 1)
        events = DD._gate_events(base)
        self.assertLessEqual(len(events), 1)
        for event in events:
            self.assertLessEqual(len(event), DD._GATE_EVENT_MAX)

    def test_the_cap_refuses_in_front_of_the_mac_at_its_rungs(self):
        plain = _raw(_SUBJECT, _wrong_signed())
        for size in (1023, 1024, 1025, 2048):
            with self.subTest(size=size):
                pad = size - len(plain)
                self.assertGreaterEqual(pad, 1)
                raw = _raw(_SUBJECT + " " + "x" * (pad - 1),
                           _wrong_signed())
                self.assertEqual(len(raw), size)
                rig, base, seen, imap = self._arrive(raw, cap=1024)
                self.assertEqual(rig.ran, [])
                self.assertEqual(rig.sent, [])
                self.assertEqual(seen, {})
                self.assertEqual(len(imap.marked), 1)
                if size > 1024:
                    self.assertEqual(rig.macs, 0)
                    self.assertFalse(any(" submitted by " in ln
                                         for ln in rig.lines))
                    self.assertEqual(DD._gate_events(base), [])
                    self.assertEqual(DD._gate_kept(base), [])
                else:
                    self._assert_refusal_bundle(raw, rig, base, seen,
                                                imap)


if __name__ == "__main__":
    unittest.main()
