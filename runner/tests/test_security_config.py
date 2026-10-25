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

    def test_a_failed_roll_keeps_writing_on_the_same_file(self):
        # Queue A (_enforce_bound's failed-replace arm): when
        # the roll itself fails -- here the rolled name is a
        # directory, so the rename cannot land -- the writer
        # does not raise and does not lose the decision: the
        # entry is appended to the un-rolled log and the
        # bound is simply tried again on the next write.
        with tempfile.TemporaryDirectory() as d:
            cfg = {"security": {"audit_max_lines": 2}}
            os.makedirs(os.path.join(d, S.AUDIT_ROLLED_FILE))
            for i in range(3):
                S.write_audit_entry(d, "policy_env", "would_deny",
                                    "r", job_id="j%d" % i, cfg=cfg)
            lines = open(os.path.join(d, S.AUDIT_FILE)).readlines()
            self.assertEqual(len(lines), 3)
            self.assertEqual(
                [json.loads(line)["job_id"] for line in lines],
                ["j0", "j1", "j2"])

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


class BumpCountsFallbacksTest(unittest.TestCase):
    """Queue A refill: _bump_counts' guard and cleanup
    lines (coverage run 40187685363: the base_dir guard
    unrun on Windows, the fd-cleanup finally unrun on
    both). The counts file is best-effort bookkeeping
    behind the audit report: a bad base_dir bumps
    nothing, and a write that fails after the temp file
    is opened must close the descriptor it opened --
    a leaked fd per audit entry would exhaust the
    runner's table -- while still swallowing the
    failure, because counting must never sink a job.
    The two flag lines in the residue are the platform
    pair (O_NOFOLLOW inapplicable on Windows, O_BINARY
    on Linux), each covered where it applies.
    """

    def test_a_non_string_base_dir_bumps_nothing(self):
        self.assertIsNone(S._bump_counts(None, "audience",
                                         "denied"))
        self.assertIsNone(S._bump_counts("", "audience",
                                         "denied"))
        self.assertIsNone(S._bump_counts(42, "audience",
                                         "denied"))

    def test_an_fdopen_failure_closes_the_fd(self):
        opened, closed = [], []
        real_open, real_close = os.open, os.close

        def tracking_open(path, flags, mode=0o777):
            fd = real_open(path, flags, mode)
            opened.append(fd)
            return fd

        def tracking_close(fd):
            closed.append(fd)
            return real_close(fd)

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(os, "open", tracking_open), \
                    mock.patch.object(os, "close",
                                      tracking_close), \
                    mock.patch.object(
                        os, "fdopen",
                        side_effect=OSError("cannot wrap")):
                got = S._bump_counts(d, "audience", "denied")
            self.assertIsNone(got)
            self.assertFalse(os.path.exists(
                os.path.join(d, S.COUNTS_FILE)))
        self.assertEqual(len(opened), 1)
        self.assertEqual(closed, opened)

    def test_a_close_failure_is_swallowed_too(self):
        real_close = os.close

        def raising_close(fd):
            real_close(fd)
            raise OSError("close says no")

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(os, "close",
                                   raising_close), \
                    mock.patch.object(
                        os, "fdopen",
                        side_effect=OSError("cannot wrap")):
                got = S._bump_counts(d, "audience", "denied")
            self.assertIsNone(got)
            self.assertFalse(os.path.exists(
                os.path.join(d, S.COUNTS_FILE)))


class ValidateMessageTextTest(unittest.TestCase):
    """D4 mutation triage (run 40205330969; local reproduction
    in hp-mut-d4): the validate_* survivors were almost all
    string mutations inside the RuntimeError messages -- the
    older tests match the messages loosely (assertRaisesRegex
    with a word or two), so a wrapped or upper-cased message
    still matched. These tests pin the whole message, including
    the interpolated type name and value, which is also the
    startup contract: Decision 1 names the bad value in the
    refusal. Each test names the mutants it kills."""

    def _message(self, cfg):
        with self.assertRaises(RuntimeError) as cm:
            S.validate_security_config(cfg)
        return str(cm.exception)

    def test_security_not_an_object_names_its_type(self):
        # kills validate_security_config mutmut_10, _12
        self.assertEqual(
            self._message({"security": "off"}),
            "config error: security must be an object, got str")

    def test_modes_not_an_object_names_its_type(self):
        # kills validate_security_config mutmut_23, _25
        self.assertEqual(
            self._message({"security": {"modes": "off"}}),
            "config error: security.modes must be an object, got str")

    def test_unknown_feature_message_is_exact(self):
        # kills validate_security_config mutmut_29
        self.assertEqual(
            self._message({"security": {"modes": {"nope": "off"}}}),
            "config error: security.modes.nope is not a known feature")

    def test_bad_mode_message_is_exact(self):
        # kills validate_security_config mutmut_36, _38
        self.assertEqual(
            self._message({"security": {"modes": {"policy_env": "maybe"}}}),
            "config error: security.modes.policy_env must be one of "
            "off, audit, enforce (got 'maybe')")

    def test_non_integer_max_lines_message_is_exact(self):
        # kills validate_security_config mutmut_51, _53
        self.assertEqual(
            self._message({"security": {"audit_max_lines": "many"}}),
            "config error: security.audit_max_lines must be an "
            "integer (got 'many')")

    def test_zero_max_lines_message_is_exact(self):
        # kills validate_security_config mutmut_59, _61
        self.assertEqual(
            self._message({"security": {"audit_max_lines": 0}}),
            "config error: security.audit_max_lines must be at "
            "least 1 (got 0)")

    def test_one_max_line_is_accepted(self):
        # kills validate_security_config mutmut_55 (<= 1), _56 (< 2):
        # the bound is "at least 1", so 1 itself validates.
        S.validate_security_config({"security": {"audit_max_lines": 1}})

    def test_job_user_not_an_object_message_is_exact(self):
        # kills validate_security_config mutmut_86, _88
        self.assertEqual(
            self._message({"security": {"job_user": []}}),
            "config error: security.job_user must be an object with "
            "a non-empty string 'user' (got [])")

    def test_job_user_bad_character_message_is_exact(self):
        # kills validate_security_config mutmut_98, _100, _101
        self.assertEqual(
            self._message({"security": {"job_user": {"user": "a/b"}}}),
            "config error: security.job_user.user 'a/b' is not a "
            "username")

    def test_job_user_nonexistent_message_is_exact(self):
        # kills validate_security_config mutmut_110, _112, _113
        if os.name == "nt":
            self.skipTest("POSIX only")
        self.assertEqual(
            self._message({"security": {"job_user":
                                         {"user": "hp-no-such-user-zz9"}}}),
            "config error: security.job_user.user "
            "'hp-no-such-user-zz9' does not exist")

    def test_job_user_with_an_x_is_not_a_bad_character(self):
        # kills validate_security_config mutmut_95: its forbidden
        # set gains the letter X, so a name containing one is
        # refused as "not a username" where the real code passes
        # the character check and (POSIX) reports the name as
        # nonexistent instead; on Windows it validates outright.
        cfg = {"security": {"job_user": {"user": "Xhp-no-such-user"}}}
        if os.name == "nt":
            S.validate_security_config(cfg)
        else:
            self.assertEqual(
                self._message(cfg),
                "config error: security.job_user.user "
                "'Xhp-no-such-user' does not exist")

    def test_windows_skips_the_existence_check(self):
        # kills validate_security_config mutmut_103, _104 on POSIX
        # hosts (on Windows the mutant's pwd import fails and it
        # cannot be told apart there): with os.name reading "nt"
        # a nonexistent user validates, because the existence
        # check is POSIX-only behind that gate.
        with mock.patch.object(os, "name", "nt"):
            S.validate_security_config(
                {"security": {"job_user":
                              {"user": "hp-no-such-user-zz9"}}})


class SharedSecretBoundaryTest(unittest.TestCase):
    """D4 triage, the validate_shared_secret family: the hint
    text and the 128-bit floor had no exact pins."""

    def test_missing_secret_message_carries_the_hint_verbatim(self):
        # kills validate_shared_secret mutmut_1 (hint None), _2, _3
        # (hint text), _6 (the required text): the refusal must
        # tell the operator how to generate a secret, word for word.
        for missing in ("", None):
            with self.subTest(missing=missing):
                with self.assertRaises(RuntimeError) as cm:
                    S.validate_shared_secret(missing)
                self.assertEqual(
                    str(cm.exception),
                    "config error: shared_secret is required (a "
                    "dedicated high-entropy secret, separate from "
                    "the mailbox password). generate one with: "
                    "openssl rand -hex 32  or: python3 -c \"import "
                    "secrets; print(secrets.token_hex(32))\"")

    def test_non_string_secret_reason_is_exact(self):
        # kills _secret_pattern_reason mutmut_2, _3
        self.assertEqual(S._secret_pattern_reason(123),
                         "secret must be a string")

    def test_every_placeholder_word_is_flagged(self):
        # kills _secret_pattern_reason mutmut_9.._14 (the changeme,
        # example and placeholder literals, wrapped and upper-case
        # forms); the other words are pinned beside them so the
        # whole tuple is covered by one test each.
        for word in ("generate", "changeme", "example", "placeholder",
                     "your-secret", "your_secret", "todo", "xxx"):
            with self.subTest(word=word):
                self.assertEqual(
                    S._secret_pattern_reason("Zq9" + word + "Wk7Pm"),
                    "it looks like an example placeholder value")

    def test_exactly_128_bits_is_accepted(self):
        # kills validate_shared_secret mutmut_14 (<= 128), _15
        # (< 129): 32 characters over a 16-symbol alphabet
        # estimates at exactly 32 * log2(16) = 128 bits, and the
        # floor is "at least 128".
        secret = "0123456789abcdef" + "fedcba9876543210"
        self.assertEqual(S._estimate_secret_entropy(secret), 128.0)
        self.assertIsNone(S._secret_pattern_reason(secret))
        S.validate_shared_secret(secret)

    def test_single_character_alphabet_estimates_zero(self):
        # _estimate_secret_entropy mutmut_6 (alphabet < 1) is
        # provably equivalent -- log2(1) is 0, so the early return
        # and the fallthrough both give 0.0 -- and is recorded as
        # such in the ledger, not chased. This pins the value.
        self.assertEqual(S._estimate_secret_entropy("aaaaaaaa"), 0.0)


class _MappingOnly:
    """A mapping that is not a dict: it has .get but fails
    sec_decide's isinstance(ctx, dict) gate."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


class _HostileStr:
    def __str__(self):
        raise ValueError("hostile __str__")


class SecDecideAuditFieldTest(unittest.TestCase):
    """D4 triage, the sec_decide family: the decision was pinned
    everywhere, the audit entry's identifier VALUES were not --
    so mutants that dropped, nulled or misread key_id, job_id,
    detail and cfg on either write path survived. These tests
    read the entry back and pin every field, per path."""

    CTX = {"key_id": "k1", "job_id": "j1", "detail": "d1"}

    def _entry(self, cfg, ctx, mode_feature="policy_env"):
        with tempfile.TemporaryDirectory() as d:
            allowed = S.sec_decide(cfg, d, mode_feature, "bad_env", ctx)
            lines = open(os.path.join(d, S.AUDIT_FILE)).readlines()
            self.assertEqual(len(lines), 1)
            return allowed, json.loads(lines[0])

    def test_audit_path_entry_carries_the_ctx_values(self):
        # kills sec_decide mutmut_52 (job_id None), _60 (key_id
        # dropped), _61 (job_id dropped), and the shared coercion
        # mutants _15, _19, _20 (wrong key name).
        cfg = {"security": {"modes": {"policy_env": "audit"}}}
        allowed, entry = self._entry(cfg, dict(self.CTX))
        self.assertTrue(allowed)
        self.assertEqual(entry["key_id"], "k1")
        self.assertEqual(entry["job_id"], "j1")
        self.assertEqual(entry["detail"], "d1")
        self.assertEqual(entry["mode"], "audit")

    def test_enforce_path_entry_carries_the_ctx_values(self):
        # kills sec_decide mutmut_72 (key_id None), _74 (detail
        # None), _81 (key_id dropped), _83 (detail dropped),
        # _84 (mode dropped, in part).
        cfg = {"security": {"modes": {"policy_env": "enforce"}}}
        allowed, entry = self._entry(cfg, dict(self.CTX))
        self.assertFalse(allowed)
        self.assertEqual(entry["key_id"], "k1")
        self.assertEqual(entry["job_id"], "j1")
        self.assertEqual(entry["detail"], "d1")
        self.assertEqual(entry["mode"], "enforce")

    def test_absent_keys_write_empty_strings_and_no_detail(self):
        # kills sec_decide mutmut_16, _18, _21 (key_id defaults),
        # _25, _27, _30 (job_id), _34, _36, _39 (detail): an
        # absent key must read as "", never "None" or "XXXX",
        # and an empty detail stays out of the entry entirely.
        for mode in ("audit", "enforce"):
            with self.subTest(mode=mode):
                cfg = {"security": {"modes": {"policy_env": mode}}}
                _, entry = self._entry(cfg, {})
                self.assertEqual(entry["key_id"], "")
                self.assertEqual(entry["job_id"], "")
                self.assertNotIn("detail", entry)

    def test_a_non_dict_mapping_ctx_reads_as_empty(self):
        # kills sec_decide mutmut_12 (the isinstance gate OR'd
        # away): a mapping that is not a dict is replaced by {}
        # before any key is read, so its values never land.
        cfg = {"security": {"modes": {"policy_env": "audit"}}}
        _, entry = self._entry(cfg, _MappingOnly(dict(self.CTX)))
        self.assertEqual(entry["key_id"], "")
        self.assertEqual(entry["job_id"], "")
        self.assertNotIn("detail", entry)

    def test_a_hostile_str_resets_all_three_identifiers(self):
        # kills sec_decide mutmut_42 (the except path's job_id
        # reset mutated): when one coercion raises, all three
        # identifiers fall back to "" together.
        cfg = {"security": {"modes": {"policy_env": "audit"}}}
        ctx = {"key_id": _HostileStr(), "job_id": "j1", "detail": "d1"}
        _, entry = self._entry(cfg, ctx)
        self.assertEqual(entry["key_id"], "")
        self.assertEqual(entry["job_id"], "")
        self.assertNotIn("detail", entry)

    def test_enforce_path_rolls_the_audit_log_at_the_cfg_bound(self):
        # kills sec_decide mutmut_75 and the cfg leg of _84 (cfg
        # dropped at the enforce write): the writer must see the
        # caller's cfg, whose audit_max_lines of 1 rolls the
        # one-line log before the denied entry is written.
        cfg = {"security": {"modes": {"policy_env": "enforce"},
                            "audit_max_lines": 1}}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, S.AUDIT_FILE)
            with open(path, "w") as fh:
                fh.write('{"old": true}\n')
            self.assertFalse(
                S.sec_decide(cfg, d, "policy_env", "bad_env",
                             dict(self.CTX)))
            self.assertTrue(os.path.exists(
                os.path.join(d, S.AUDIT_ROLLED_FILE)))
            lines = open(path).readlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["decision"], "denied")


if __name__ == "__main__":
    unittest.main(verbosity=2)
