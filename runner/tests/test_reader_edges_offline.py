# Agent-Stamp: b000092f-e5ef-4e93-bcc6-e35f92ee2ab1
"""Reader refusals in guard, wire and oracle that only the property suites ran.

A box without hypothesis (the air-gapped bench, a rig with no package
index) skips the property and fuzz modules, and these lines went unrun
there. Each is input a sender or a probe controls, so each is pinned
with a plain test that runs everywhere:

- the DTLS record opener on the short header forms (8-bit sequence,
  no length field) a peer may send: they decrypt, and the header is
  authenticated (the truncated forms are refused in test_coverage_lane);
- the backtracking check on a nested repeat hidden in an alternation arm;
- the learning ledger's feature keys on facts of the wrong shape;
- the extension review on an entry that is not an argv, an argv part
  that is not text, and a registry row with no folder.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.guard import extreview as XR  # noqa: E402
from runner.guard import security as S  # noqa: E402
from runner.oracle import learning as L  # noqa: E402
from runner.wire import dtlsproto as D  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402

SECRET = bytes(range(48))


def _short_record(sealer, epoch, seq, content_type, payload, *,
                  length_field):
    """A unified record with an 8-bit sequence number, built by hand:
    the sealer only writes the 16-bit form, and a peer may send either."""
    first = 0x20 | (0x08 if length_field else 0) | (epoch & 0x3)
    header = bytes([first, seq & 0xFF])
    inner = payload + bytes([content_type])
    if length_field:
        header += (len(inner) + 16).to_bytes(2, "big")
    return header + jobcrypto.aead_encrypt(
        sealer.key, sealer._nonce(epoch, seq), inner, header)


class DtlsRecordOpenTest(unittest.TestCase):
    def setUp(self):
        self.tx = D._RecordSealer(SECRET)
        self.rx = D._RecordSealer(SECRET)

    def test_an_8_bit_sequence_with_a_length_opens(self):
        rec = _short_record(self.tx, 2, 0, 23, b"ping", length_field=True)
        self.assertEqual(self.rx.open(2, rec), (23, b"ping", 0))

    def test_an_8_bit_sequence_without_a_length_opens(self):
        rec = _short_record(self.tx, 2, 0, 23, b"ping\x00", length_field=False)
        # The content keeps its own trailing zero; only padding after
        # the type octet is stripped.
        self.assertEqual(self.rx.open(2, rec), (23, b"ping\x00", 0))

    def test_a_tampered_short_header_fails_authentication(self):
        rec = bytearray(_short_record(self.tx, 2, 0, 23, b"ping",
                                      length_field=False))
        rec[1] ^= 0x01  # the sequence octet is in the AAD
        with self.assertRaisesRegex(jobcrypto.JobCryptoError, "tag mismatch"):
            self.rx.open(2, bytes(rec))


class BacktrackInAlternationTest(unittest.TestCase):
    def test_a_nested_repeat_in_an_arm_is_found(self):
        self.assertEqual(S.regex_backtracks(r"x|(a+)+"), "nested repeat")
        self.assertEqual(S.regex_backtracks(r"x|(?:y|(\w+\s?)*)"),
                         "nested repeat")

    def test_plain_arms_are_bounded(self):
        self.assertIsNone(S.regex_backtracks(r"x|a+|b*c"))


class FeatureKeysShapeTest(unittest.TestCase):
    def test_a_string_interpreter_is_not_read_letter_by_letter(self):
        self.assertEqual(L.feature_keys(
            {"interpreter": "sh", "interpreter_present": False}), [])

    def test_tools_and_paths_that_are_not_maps_name_nothing(self):
        self.assertEqual(L.feature_keys(
            {"tools": ["git"], "paths": "C:\\x"}), [])

    def test_well_formed_facts_still_name_their_keys(self):
        self.assertEqual(L.feature_keys({
            "interpreter": ["pwsh"], "interpreter_present": False,
            "tools": {"git": False, "sh": True},
            "paths": {"/opt/x": False, "C:\\y": None}}),
            ["interpreter:pwsh", "tool:git", "path:/opt/x", "pathshape:C:\\y"])


class ExtensionReviewShapeTest(unittest.TestCase):
    def test_an_entry_that_is_not_an_argv_adds_no_finding(self):
        for entry in (None, "python x.py", [], {"argv": ["x"]}):
            with self.subTest(entry=entry):
                findings = []
                XR._review_entry({"entry": entry}, "/ext", findings, False)
                self.assertEqual(findings, [])

    def test_a_part_that_is_not_text_is_passed_over(self):
        with tempfile.TemporaryDirectory() as d:
            findings = []
            XR._review_entry({"entry": [7, None, "{python}"]}, d,
                             findings, False)
            self.assertEqual(findings, [])

    def test_a_row_with_no_folder_is_kept_as_is(self):
        registry = {"bare": {"name": "bare"}, "odd": "not a manifest"}
        out, problems, report = XR.apply(
            {"extension_review": "enforce"}, tempfile.gettempdir(),
            registry, kind="sense")
        self.assertEqual(out, registry)
        self.assertEqual(problems, [])
        self.assertEqual(report["extensions"], {})

    def test_an_unresolvable_path_is_not_under_any_folder(self):
        self.assertFalse(XR._under("a\x00b", "/ext"))


if __name__ == "__main__":
    unittest.main()
