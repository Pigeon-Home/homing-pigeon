#!/usr/bin/env python3
"""M0 tests: mode plumbing, config validation, audit writer.

UID (phase 2.3): no job executes in this file. sec_decide and
the mode plumbing run in the runner process BEFORE execution,
deciding whether a guard feature is off, auditing, or
enforcing; they neither change nor test a uid. Any job a
feature later admits runs as the SAME uid as the runner
unless the separate job_user feature is configured (its own
corpus). Recorded as a design fact, not a failure. The
off/audit/enforce cases in SecDecideTest are each other's
negative controls (phase 2.2), and SecDecideNegativeControl
below asserts all three modes for one identical check inside
a single test, so a decision that came out the same with the
protection off and enforcing would fail there directly.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.guard import security as S  # noqa: E402

SENTINEL = "SENTINEL-SECRET-VALUE-9f8e"


class ValidateTest(unittest.TestCase):
    def test_missing_block_ok(self):
        S.validate_security_config({})
        S.validate_security_config({"security": None})

    def test_all_off_ok(self):
        S.validate_security_config(
            {"security": {"modes": {f: "off" for f in S.FEATURES}}})

    def test_all_audit_ok(self):
        S.validate_security_config(
            {"security": {"modes": {f: "audit" for f in S.FEATURES},
                          "audit_max_lines": 100}})

    def test_non_object_security(self):
        with self.assertRaisesRegex(RuntimeError, "security.*object"):
            S.validate_security_config({"security": "off"})

    def test_non_object_modes(self):
        with self.assertRaisesRegex(RuntimeError, "security.modes.*object"):
            S.validate_security_config({"security": {"modes": "off"}})

    def test_unknown_feature(self):
        with self.assertRaisesRegex(RuntimeError, "nope"):
            S.validate_security_config(
                {"security": {"modes": {"nope": "off"}}})

    def test_bad_mode_value(self):
        with self.assertRaisesRegex(RuntimeError, "maybe"):
            S.validate_security_config(
                {"security": {"modes": {"policy_env": "maybe"}}})

    def test_non_integer_max_lines(self):
        with self.assertRaisesRegex(RuntimeError, "audit_max_lines"):
            S.validate_security_config(
                {"security": {"audit_max_lines": "many"}})

    def test_zero_max_lines_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "audit_max_lines"):
            S.validate_security_config(
                {"security": {"audit_max_lines": 0}})


class SecModeTest(unittest.TestCase):
    def test_default_off(self):
        self.assertEqual(S.sec_mode({}, "policy_env"), "off")
        self.assertEqual(S.sec_mode({"security": None}, "policy_env"), "off")
        self.assertEqual(S.sec_mode(
            {"security": {"modes": {}}}, "policy_env"), "off")

    def test_reads_mode(self):
        cfg = {"security": {"modes": {"policy_env": "enforce"}}}
        self.assertEqual(S.sec_mode(cfg, "policy_env"), "enforce")
        self.assertEqual(S.sec_mode(cfg, "audience"), "off")

    def test_bad_value_reads_off(self):
        # validate_security_config rejects this at startup; sec_mode
        # stays defensive so a bad value can never enable enforcement.
        cfg = {"security": {"modes": {"policy_env": "maybe"}}}
        self.assertEqual(S.sec_mode(cfg, "policy_env"), "off")


class SecDecideTest(unittest.TestCase):
    def test_off_allows_without_entry(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"security": {"modes": {"policy_env": "off"}}}
            self.assertTrue(
                S.sec_decide(cfg, d, "policy_env", "r",
                             {"key_id": "k", "job_id": "j"}))
            self.assertFalse(os.path.exists(
                os.path.join(d, S.AUDIT_FILE)))

    def test_audit_allows_and_logs_would_deny(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"security": {"modes": {"policy_env": "audit"}}}
            self.assertTrue(
                S.sec_decide(cfg, d, "policy_env", "bad_env",
                             {"key_id": "k", "job_id": "j"}))
            lines = open(os.path.join(d, S.AUDIT_FILE)).readlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["decision"], "would_deny")
            self.assertEqual(entry["feature"], "policy_env")
            self.assertEqual(entry["reason"], "bad_env")
            self.assertEqual(entry["mode"], "audit")

    def test_enforce_denies_and_logs_denied(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"security": {"modes": {"policy_env": "enforce"}}}
            self.assertFalse(
                S.sec_decide(cfg, d, "policy_env", "bad_env",
                             {"key_id": "k", "job_id": "j"}))
            entry = json.loads(
                open(os.path.join(d, S.AUDIT_FILE)).readline())
            self.assertEqual(entry["decision"], "denied")
            self.assertEqual(entry["mode"], "enforce")

    def test_entry_carries_identifiers_only(self):
        # Callers may stuff extra keys into ctx; the writer's field
        # allowlist drops them. Sentinel secrets must never land
        # in the audit log.
        with tempfile.TemporaryDirectory() as d:
            cfg = {"security": {"modes": {"policy_env": "audit"}}}
            S.sec_decide(cfg, d, "policy_env", "r", {
                "key_id": "k", "job_id": "j", "detail": "d",
                "shared_secret": SENTINEL, "env": {"X": SENTINEL}})
            raw = open(os.path.join(d, S.AUDIT_FILE)).read()
            self.assertNotIn(SENTINEL, raw)
            entry = json.loads(raw.strip())
            self.assertEqual(set(entry),
                             {"ts", "feature", "decision", "reason",
                              "key_id", "job_id", "detail", "mode"})


class AuditWriterTest(unittest.TestCase):
    def test_bound_and_rollover(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"security": {"audit_max_lines": 3}}
            for i in range(4):
                S.write_audit_entry(d, "policy_env", "would_deny", "r",
                                    job_id="j%d" % i, cfg=cfg)
            rolled = os.path.join(d, S.AUDIT_ROLLED_FILE)
            self.assertTrue(os.path.exists(rolled))
            self.assertEqual(len(open(rolled).readlines()), 3)
            self.assertEqual(
                len(open(os.path.join(d, S.AUDIT_FILE)).readlines()), 1)

    def test_posix_permissions(self):
        if os.name == "nt":
            self.skipTest("POSIX only")
        with tempfile.TemporaryDirectory() as d:
            S.write_audit_entry(d, "policy_env", "would_deny", "r")
            mode = stat.S_IMODE(os.stat(
                os.path.join(d, S.AUDIT_FILE)).st_mode)
            self.assertEqual(mode, 0o600)

    def test_unwritable_dir_swallows(self):
        # base_dir is a file: the join fails. Must not raise.
        with tempfile.TemporaryDirectory() as d:
            not_a_dir = os.path.join(d, "not-a-dir")
            open(not_a_dir, "w").write("x")
            S.write_audit_entry(not_a_dir, "policy_env", "would_deny", "r")
            S.sec_decide({"security": {"modes": {"policy_env": "audit"}}},
                         not_a_dir, "policy_env", "r", {})

    def test_counts_file(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"security": {"modes": {"policy_env": "audit"}}}
            S.sec_decide(cfg, d, "policy_env", "r", {})
            S.sec_decide(cfg, d, "policy_env", "r", {})
            counts = json.load(
                open(os.path.join(d, S.COUNTS_FILE)))
            self.assertEqual(
                counts["policy_env"]["would_deny"], 2)

    def test_bump_evaluated(self):
        with tempfile.TemporaryDirectory() as d:
            S.bump_evaluated(d, "audience")
            S.bump_evaluated(d, "audience")
            S.bump_evaluated(d, "confinement")
            counts = json.load(
                open(os.path.join(d, S.COUNTS_FILE)))
            self.assertEqual(counts["audience"]["evaluated"], 2)
            self.assertEqual(counts["confinement"]["evaluated"], 1)


class SecDecideNegativeControl(unittest.TestCase):
    """Phase 2.2 paired control: ONE identical failing check
    decided under all three modes inside a single test -- off
    and audit must allow it, enforce must deny it. A sec_decide
    change that denied (or allowed) in every mode would fail
    here even if the separate per-mode tests were edited to
    match. UID: no job runs; the decision is the runner's own,
    pre-execution (see the module note)."""

    def test_same_check_allows_off_and_audit_denies_enforce(self):
        ctx = {"key_id": "k", "job_id": "j"}
        with tempfile.TemporaryDirectory() as d:
            off_cfg = {"security": {"modes": {"policy_env": "off"}}}
            self.assertTrue(S.sec_decide(
                off_cfg, d, "policy_env", "bad_env", dict(ctx)))
            self.assertFalse(os.path.exists(
                os.path.join(d, S.AUDIT_FILE)))
        with tempfile.TemporaryDirectory() as d:
            audit_cfg = {"security": {"modes": {"policy_env": "audit"}}}
            self.assertTrue(S.sec_decide(
                audit_cfg, d, "policy_env", "bad_env", dict(ctx)))
            entry = json.loads(
                open(os.path.join(d, S.AUDIT_FILE)).readline())
            self.assertEqual(entry["decision"], "would_deny")
        with tempfile.TemporaryDirectory() as d:
            enf_cfg = {"security": {"modes": {"policy_env": "enforce"}}}
            self.assertFalse(S.sec_decide(
                enf_cfg, d, "policy_env", "bad_env", dict(ctx)))
            entry = json.loads(
                open(os.path.join(d, S.AUDIT_FILE)).readline())
            self.assertEqual(entry["decision"], "denied")


class StartupHookTest(unittest.TestCase):
    def test_malformed_security_config_stops_startup(self):
        from runner.runner import main
        with tempfile.TemporaryDirectory() as d:
            cfg_path = os.path.join(d, "config.json")
            json.dump({
                "mailbox_user": "a@b.c",
                "mailbox_password": "p",
                "shared_secret": "ab" * 32,
                "security": {"modes": {"nope": "off"}},
            }, open(cfg_path, "w"))
            with mock.patch.object(sys, "argv",
                                   ["runner", "--config", cfg_path]):
                self.assertEqual(main(), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
