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
import subprocess
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


class ValidateBlocksTest(unittest.TestCase):
    """Queue A: the two blocks validate_security_config
    delegates or checks itself -- confinement (owned by
    the sandbox module) and job_user -- never ran on
    Windows, and the sandbox import's script-mode
    fallback never ran anywhere (coverage run
    40180268696). The startup contract is the docstring's:
    a malformed block is a RuntimeError naming the key
    and the bad value, before any job runs. The shape
    checks are platform-agnostic (the bad-character set
    names the backslash and the colon precisely because
    Windows usernames are in scope); only the existence
    check is POSIX, and it stays behind its os.name gate.
    """

    def test_a_bad_confinement_block_is_named(self):
        with self.assertRaises(RuntimeError) as cm:
            S.validate_security_config(
                {"security": {"confinement": "not-an-object"}})
        self.assertIn("security.confinement", str(cm.exception))
        with self.assertRaises(RuntimeError):
            S.validate_security_config(
                {"security": {"confinement":
                              {"work_mount": "relative/path"}}})
        S.validate_security_config(
            {"security": {"confinement": {}}})

    def test_the_job_user_shape_is_checked(self):
        bad = [
            "not-an-object",
            {},
            {"user": ""},
            {"user": 42},
            {"user": "a/b"},
            {"user": "a\\b"},
            {"user": "a:b"},
            {"user": "a b"},
            {"user": "a\nb"},
        ]
        for ju in bad:
            with self.subTest(job_user=ju):
                with self.assertRaises(RuntimeError) as cm:
                    S.validate_security_config(
                        {"security": {"job_user": ju}})
                self.assertIn("job_user", str(cm.exception))

    def _script_mode(self, prelude):
        code = (
            "import sys\n"
            + prelude
            + "try:\n"
            + "    import runner.guard\n"
            + "    print('RUNNER-IMPORTABLE')\n"
            + "except ImportError:\n"
            + "    print('RUNNER-BLOCKED')\n"
            + "from guard import security as S\n"
            + "try:\n"
            + "    S.validate_security_config({\"security\": "
            + "{\"confinement\": {\"work_mount\": \"relative\"}}})\n"
            + "except RuntimeError as e:\n"
            + "    print(\"RAISED\", e)\n"
            + "else:\n"
            + "    print(\"NOT-RAISED\")\n")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(REPO, "runner")
        # A neutral cwd: with the repo root as cwd, the
        # `runner` package would import from there and the
        # primary import would succeed, testing nothing.
        return subprocess.run(
            [sys.executable, "-c", code], env=env,
            cwd=tempfile.mkdtemp(prefix="hp-sc-mode-"),
            capture_output=True, text=True, timeout=60)

    def test_script_mode_still_validates_confinement(self):
        # With only runner/ on the path, `runner.guard`
        # does not import and the fallback `guard` import
        # must find the sandbox module: the bad block is
        # still refused.
        proc = self._script_mode("")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RUNNER-BLOCKED", proc.stdout)
        self.assertIn("RAISED", proc.stdout)
        self.assertIn("config error", proc.stdout)

    def test_no_sandbox_module_means_confinement_unchecked(self):
        # The fallback's own failure is deliberate: with
        # no sandbox module at all, the confinement block
        # cannot be validated and the call passes -- the
        # pair with the test above pins both sides of the
        # fallback.
        proc = self._script_mode(
            "import sys\nsys.modules['guard.sandbox'] = None\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RUNNER-BLOCKED", proc.stdout)
        self.assertIn("NOT-RAISED", proc.stdout)

    def test_both_sandbox_imports_failing_passes_the_block(self):
        # The same both-imports-dead case, in-process:
        # coverage run 40183585961 still showed the
        # double-failure lines unrun, because the
        # subprocess pair above measures its lines in a
        # child whose coverage data never reaches the map.
        # The behavior was already proven there; this leg
        # makes the map see it, and asserts the same
        # contract -- a bad block is passed over, not
        # refused, when no sandbox module exists to own
        # the schema.
        # The from-import consults the package attribute
        # before the module table, and this process has
        # long since loaded the real sandbox onto it --
        # both must be cleared for the import to fail the
        # way it does in a bare interpreter.
        import runner.guard as guard_pkg
        had_attr = hasattr(guard_pkg, "sandbox")
        saved = getattr(guard_pkg, "sandbox", None)
        if had_attr:
            delattr(guard_pkg, "sandbox")
        try:
            with mock.patch.dict(sys.modules, {
                    "runner.guard.sandbox": None,
                    "guard": None,
                    "guard.sandbox": None}):
                S.validate_security_config(
                    {"security": {"confinement":
                                  {"work_mount": "relative/path"}}})
        finally:
            if had_attr:
                guard_pkg.sandbox = saved

    def test_a_missing_pwd_module_skips_the_existence_check(self):
        # The job_user existence check is POSIX-only and
        # tolerates a platform without pwd: the import
        # failure reads as "no directory to check
        # against", and a user that cannot be looked up
        # is not refused on that ground. (Coverage run
        # 40183585961: the ImportError leg unrun on Linux,
        # where pwd always imports; scripted here through
        # the module table.)
        if os.name == "nt":
            self.skipTest("POSIX only")
        with self.assertRaises(RuntimeError):
            S.validate_security_config(
                {"security": {"job_user":
                              {"user": "hp-no-such-user-zz9"}}})
        with mock.patch.dict(sys.modules, {"pwd": None}):
            S.validate_security_config(
                {"security": {"job_user":
                              {"user": "hp-no-such-user-zz9"}}})


if __name__ == "__main__":
    unittest.main(verbosity=2)
