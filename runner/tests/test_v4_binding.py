"""Pins for the v4 binding harvest (FUTURE.md item 1, steps A and B).

The claims pinned here are the ones stated in
docs/infrastructure-documents/proofs/v4-properties.md: the newly
harvested constraints C28 to C31 and the three standing
constraints no property in properties.md stated (C3, C4, C6).
Each pin reads the value from the code itself, so a silent
change to a harvested value fails a test instead of quietly
changing what the v4 model is about. The standing inventory
C1 to C27 keeps its own pins in test_proof_constraints.py.
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from runner import runner as R  # noqa: E402
from runner.guard import security as S  # noqa: E402
from runner.oracle import resources as RES  # noqa: E402
from runner.wire import dtlsproto as DTLS  # noqa: E402

PROOFS = os.path.join(ROOT, "docs", "infrastructure-documents", "proofs")


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class DiskGuardConstantPins(unittest.TestCase):
    """C28: the disk guard's named constants, as harvested."""

    def test_threshold_is_90_percent(self):
        self.assertEqual(RES.DISK_GUARD_THRESHOLD, 0.90)

    def test_log_keep_bytes(self):
        self.assertEqual(RES.DISK_GUARD_LOG_KEEP_BYTES, 65536)

    def test_work_min_age(self):
        self.assertEqual(RES.DISK_GUARD_WORK_MIN_AGE_SEC, 3600)

    def test_max_actions(self):
        self.assertEqual(RES.DISK_GUARD_MAX_ACTIONS, 512)


class DiskGuardOptOutPins(unittest.TestCase):
    """C28: only a literal true of no_90_disk_truncation opts out."""

    def test_absent_key_leaves_guard_on(self):
        self.assertTrue(RES.disk_guard_enabled({}))

    def test_literal_true_turns_guard_off(self):
        self.assertFalse(RES.disk_guard_enabled(
            {"no_90_disk_truncation": True}))

    def test_false_leaves_guard_on(self):
        self.assertTrue(RES.disk_guard_enabled(
            {"no_90_disk_truncation": False}))

    def test_string_true_is_not_the_literal(self):
        self.assertTrue(RES.disk_guard_enabled(
            {"no_90_disk_truncation": "true"}))

    def test_non_dict_config_leaves_guard_on(self):
        self.assertTrue(RES.disk_guard_enabled(None))


class DiskGuardOrderPins(unittest.TestCase):
    """P7: rolled log backups are given up before the live logs,
    and a pass under the threshold touches nothing."""

    def _fraction_patch(self, fn):
        orig = RES._disk_fraction
        RES._disk_fraction = fn
        self.addCleanup(setattr, RES, "_disk_fraction", orig)

    def test_under_threshold_pass_touches_nothing(self):
        with tempfile.TemporaryDirectory() as base:
            log = os.path.join(base, "runner.log")
            with open(log, "w", encoding="utf-8") as fh:
                fh.write("x" * 4096)
            self._fraction_patch(lambda path: 0.50)
            self.assertIsNone(RES.guard_disk({}, base))
            with open(log, encoding="utf-8") as fh:
                self.assertEqual(len(fh.read()), 4096)

    def test_backups_go_before_live_logs(self):
        with tempfile.TemporaryDirectory() as base:
            backup = os.path.join(base, "runner.log.1")
            with open(backup, "w", encoding="utf-8") as fh:
                fh.write("b" * 2048)
            log = os.path.join(base, "runner.log")
            with open(log, "w", encoding="utf-8") as fh:
                fh.write("x" * 100000)

            def fraction(path):
                # Over the threshold until the backup is gone,
                # under it from then on.
                return 0.50 if not os.path.exists(backup) else 0.95

            self._fraction_patch(fraction)
            event = RES.guard_disk({}, base)
            self.assertIsNotNone(event)
            self.assertEqual(event["type"], "disk_truncation")
            self.assertFalse(os.path.exists(backup))
            # The live log was never reached: the disk came
            # under the threshold at the first stage.
            with open(log, encoding="utf-8") as fh:
                self.assertEqual(len(fh.read()), 100000)
            removes = [a for a in event["actions"]
                       if a["action"] == "remove"]
            self.assertEqual(len(removes), 1)


class HybridGroupPins(unittest.TestCase):
    """C29 / P8: the v3 hybrid group and its number."""

    def test_hybrid_group_number(self):
        self.assertEqual(DTLS.GROUP_X25519MLKEM768, 4588)

    def test_x25519_group_number(self):
        self.assertEqual(DTLS.GROUP_X25519, 0x001D)


class StandingGapPins(unittest.TestCase):
    """C3, C4, C6: the standing constraints P11 to P13 state."""

    def test_c3_result_cap_default(self):
        self.assertEqual(R.MAX_RESULT_BYTES, 5242880)
        self.assertEqual(R._max_result_bytes({}), 5242880)
        self.assertEqual(R._max_result_bytes(
            {"max_result_bytes": 0}), 0)

    def test_c4_local_envelope_cap(self):
        self.assertEqual(R._LOCAL_ENVELOPE_MAX_BYTES, 262144)

    def test_c6_entropy_floor_refuses_a_weak_secret(self):
        with self.assertRaises(RuntimeError):
            S.validate_shared_secret("ab" * 8)

    def test_c6_entropy_floor_admits_a_strong_secret(self):
        # A 64 character hex secret with no repeating unit: the
        # shape the code's own hint recommends (token_hex(32)).
        S.validate_shared_secret(
            "9f86d081884c7d659a2feaa0c55ad015"
            "a3bf4f1b2b0b822cd15d6c15b0f00a08")


class DocStatementPins(unittest.TestCase):
    """The v4 statements name the values the code carries, and
    the framing ratification stands in its record (C30, C31)."""

    def test_v4_properties_name_the_harvested_values(self):
        text = _read("docs", "infrastructure-documents", "proofs",
                     "v4-properties.md")
        for needle in ("C28", "no_90_disk_truncation", "0.90",
                       "65536", "4588", "262144", "P7", "P13"):
            self.assertIn(needle, text)

    def test_framing_ratification_stands(self):
        text = _read("docs", "infrastructure-documents", "proofs",
                     "dtls-record-layer-and-framing.md")
        self.assertIn("Both ends must run the same side of it", text)

    def test_macos_backend_states_fail_closed(self):
        text = _read("runner", "guard", "macos_confine.py")
        self.assertIn("fail-closed", text)

    def test_diskguard_model_names_its_properties(self):
        text = _read("docs", "infrastructure-documents", "proofs",
                     "diskguard.tla")
        for needle in ("NeverStops", "OrderRespected",
                       "RecordedFaithfully"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
