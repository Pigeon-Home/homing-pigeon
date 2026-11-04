#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Decision 1 startup family: one test per config field.

Decision 1 (docs/steady/present-but-invalid-config.md, settled
2026-10-23): a present-but-invalid config value REFUSES startup
when the wrong value changes who can reach the box, what it will
execute, or what it protects -- ports and bind addresses, key
policies, the paging thresholds (resources / DRI), secrets and
their floors, security modes. Every other present-but-invalid
value reads as its documented default and is named in the startup
warning ("config: N settings read as their default: ...").

This file enumerates the fields from the validation code itself:

- Refuse class, through main() itself (exit 2, the refusal on
  stderr naming the key): the mailbox ports, the size caps and
  their fellow startup checks in runner._validate_size_caps
  (pong_platform, extension_review, recipes, change_repos), the
  whole security block as validate_security_config reads it
  (runner/guard/security.py, with the confinement block owned by
  runner/guard/sandbox.py), and build_key_policies' fields
  (runner/wire/verify.py). main() checks all of these before any
  mailbox or model work, so each test is a real startup.
- Refuse class, through the refusing reader main (or the
  extension supervisor) calls at startup, for the blocks main's
  own early path does not reach: secrets (build_secrets and its
  entropy floor), the resources and DRI paging thresholds, and
  the DTLS / NATS transport readers the Decision moved from
  default to refuse (Q3, 2026-10-24).
- Default class, one generated test per field of
  runner/guard/defaulted.py's table (17 numeric keys and the
  dtls_greeting enum): the invalid value is named by
  defaulted_keys and by the startup warning line, the documented
  default is the value on record, and a real startup through
  main() (--audit-report, the read-only one-shot that runs after
  the warning) proceeds and prints that warning naming the key.

Two deliberate exclusions, both recorded here so the enumeration
is complete rather than silent:

- key_policies.allow_dangerous_env has no refuse test: the reader
  normalizes it fail-safe (anything that is not boolean True keeps
  the gate shut, runner/wire/verify.py) -- there is no invalid
  value that changes what the box protects, so Decision 1's
  refuse trigger does not exist for it.
- security.job_user on enforce under Windows is refused by
  main()'s platform gate, which cannot fire on a POSIX host; the
  gate's own function is tested directly with the platform passed
  explicitly, the shape test_enforce_races_gaps uses for it.

Strict shape (2026-11-03): enforce means enforce on every
platform. A mode set to enforce on a platform or in an
environment that cannot enforce it refuses startup, naming the
mode and the key -- there is no platform step-down to audit,
ever; recovery is a config edit and a restart, and the refusal
is a designed state. StrictShapeTest below pins that shape
through main() itself, using the platform-simulation seams the
suite already uses (mock.patch.object(sys, "platform", ...) as
in test_windows_platform_proofs.JobUserMainRefusalTest, and the
scripted sandbox startup_problem of test_cli_options), and pins
the negative at the single decision point: sec_mode never reads
a configured "enforce" as anything but "enforce" on any
platform, and sec_decide at enforce never allows and never
writes a would_* (audit) entry. The two job-time fallback chains
(confinement unavailable, job_user drop impossible) are not
step-downs to audit and are not reclassified here: they are
reachable only past the startup gates, they log "fallback"
rather than proceeding as audit, and the parity leg pins their
entries as designed.
"""
import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as RR  # noqa: E402
from runner.guard import defaulted  # noqa: E402
from runner.guard import sandbox as _sandbox  # noqa: E402
from runner.guard.security import FEATURES  # noqa: E402
from runner.oracle.dri import parse_dri  # noqa: E402
from runner.oracle.resources import parse_resources  # noqa: E402

STRONG_SECRET = ("9f86d081884c7d659a2feaa0c55ad015"
                 "a3bf4f1b2b0b822cd15d6c15b0f00a08")
# The platform gates are stated off in the base config: under
# the lockdown default confinement and job_user read enforce and
# refuse first on a host that cannot enforce them, which would
# mask the field each test is about. A test whose extra carries
# its own security block replaces this one wholesale.
BASE = {"mailbox_user": "a@b.c", "mailbox_password": "p",
        "shared_secret": STRONG_SECRET,
        "security": {"modes": {"confinement": "off",
                               "job_user": "off"}}}


def run_main(extra, argv_extra=(), platform=None, sandbox_problem=None):
    """One real startup through main(). Returns (rc, stdout, stderr).

    The config lives in a fresh temp dir whose path is also the
    runner's base_dir, so a startup that proceeds cannot touch
    real state; --audit-report (used by the default-class tests)
    returns before any mailbox work.

    platform patches sys.platform for the duration (the suite's
    win32 simulation seam); sandbox_problem scripts the sandbox
    module's startup_problem answer, so a backend failure can be
    constructed on a host whose sandbox works.
    """
    tmpdir = tempfile.mkdtemp(prefix="hp-d1-")
    cfg = dict(BASE, base_dir=tmpdir)
    cfg.update(extra)
    cfg_path = os.path.join(tmpdir, "config.json")
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    out, err = io.StringIO(), io.StringIO()
    argv = ["runner", "--config", cfg_path, *argv_extra]
    with contextlib.ExitStack() as stack:
        if platform is not None:
            stack.enter_context(
                mock.patch.object(sys, "platform", platform))
        if sandbox_problem is not None:
            stack.enter_context(mock.patch.object(
                RR._sandbox, "startup_problem",
                lambda: sandbox_problem))
        stack.enter_context(mock.patch.object(sys, "argv", argv))
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = RR.main()
    return rc, out.getvalue(), err.getvalue()


class RefuseMainTest(unittest.TestCase):
    """Generated below: one test per refuse-class field, each a
    real startup that must exit 2 with the key named on stderr."""


# (name, cfg_extra, substrings the refusal must contain)
REFUSE_MAIN = [
    ("imap_port", {"imap_port": "not-a-port"}, ["imap_port"]),
    ("smtp_port", {"smtp_port": True}, ["smtp_port"]),
    ("max_job_bytes", {"max_job_bytes": -1}, ["max_job_bytes"]),
    ("max_script_bytes", {"max_script_bytes": "huge"},
     ["max_script_bytes"]),
    ("max_result_bytes", {"max_result_bytes": 1.5},
     ["max_result_bytes"]),
    ("pong_platform", {"pong_platform": "bogus"}, ["pong_platform"]),
    ("extension_review", {"extension_review": "bogus"},
     ["extension_review"]),
    ("recipes", {"recipes": "nope"}, ["recipes"]),
    ("change_repos", {"change_repos": "nope"}, ["change_repos"]),
    ("security", {"security": "off"}, ["security"]),
    ("security_modes", {"security": {"modes": "off"}},
     ["security.modes"]),
    ("security_modes_unknown_feature",
     {"security": {"modes": {"nope": "off"}}}, ["nope"]),
    ("security_audit_max_lines",
     {"security": {"audit_max_lines": 0}}, ["audit_max_lines"]),
    ("security_audit_max_lines_text",
     {"security": {"audit_max_lines": "many"}}, ["audit_max_lines"]),
    ("security_confinement", {"security": {"confinement": "x"}},
     ["security.confinement"]),
    ("security_confinement_work_mount",
     {"security": {"confinement": {"work_mount": "relative/path"}}},
     ["confinement", "work_mount"]),
    ("security_confinement_extra_flags",
     {"security": {"confinement": {"extra_flags": "nope"}}},
     ["extra_flags"]),
    ("security_confinement_extra_ro_binds",
     {"security": {"confinement": {"extra_ro_binds": "nope"}}},
     ["extra_ro_binds"]),
    ("security_job_user", {"security": {"job_user": {}}},
     ["job_user"]),
    ("security_job_user_user_bad_char",
     {"security": {"job_user": {"user": "a/b"}}}, ["job_user"]),
    ("key_policies", {"key_policies": "nope"}, ["key_policies"]),
    ("key_policies_entry", {"key_policies": {"k": "nope"}},
     ["key_policies"]),
]

# One invalid mode value per security feature.
for _feature in FEATURES:
    REFUSE_MAIN.append((
        "security_modes_%s" % _feature,
        {"security": {"modes": {_feature: "maybe"}}},
        ["security.modes.%s" % _feature]))

# One bad value per build_key_policies field that refuses. (The
# twelfth field, allow_dangerous_env, is normalized fail-safe and
# cannot refuse -- see the module docstring.)
POLICY_BAD = [
    ("allowed_kinds", "exec"),
    ("allowed_interpreters", "sh"),
    ("max_timeout_sec", "soon"),
    ("allowed_recipes", []),
    ("allowed_script_sha384", []),
    ("allowed_env", []),
    ("denied_env", "FOO"),
    ("allow_file_urls", "yes"),
    ("allowed_files", []),
    ("max_args", -1),
    ("args_pattern", "("),
]
for _field, _bad in POLICY_BAD:
    REFUSE_MAIN.append((
        "key_policies_%s" % _field,
        {"key_policies": {"k": {_field: _bad}}},
        ["key_policies", _field]))


def _make_refuse_main_tests():
    for name, extra, needles in REFUSE_MAIN:

        def refuse_test(self, extra=extra, needles=needles):
            rc, _out, err = run_main(extra)
            self.assertEqual(rc, 2, err)
            for needle in needles:
                self.assertIn(needle, err)

        setattr(RefuseMainTest, "test_refuses_%s" % name, refuse_test)


_make_refuse_main_tests()


class RefuseStartupGatesTest(unittest.TestCase):
    """The two mechanism gates in main(): a security mode at
    enforce whose mechanism cannot engage on this machine is the
    refuse class in its purest form (Q9)."""

    def test_confinement_enforce_refused_when_sandbox_cannot_engage(self):
        if _sandbox.startup_problem() is None:
            self.skipTest("sandbox engages on this machine "
                          "(startup probe)")
        rc, _out, err = run_main(
            {"security": {"modes": {"confinement": "enforce"}}})
        self.assertEqual(rc, 2, err)
        self.assertIn("confinement", err)

    def test_job_user_enforce_gate_names_job_user_on_windows(self):
        cfg = {"security": {"modes": {"job_user": "enforce"}}}
        problem = RR._job_user_startup_problem(cfg, platform="win32")
        self.assertIsNotNone(problem)
        self.assertIn("job_user", problem)
        # The same config on a POSIX platform has no such problem:
        # the demote exists there.
        self.assertIsNone(
            RR._job_user_startup_problem(cfg, platform="linux"))
        # And with the mode off there is nothing to gate anywhere.
        off = {"security": {"modes": {"job_user": "off"}}}
        self.assertIsNone(
            RR._job_user_startup_problem(off, platform="win32"))

    def test_job_user_nonexistent_user_refused_at_startup(self):
        if os.name == "nt":
            self.skipTest("POSIX only")
        rc, _out, err = run_main(
            {"security": {"job_user": {"user": "hp-no-such-user-zz9"}}})
        self.assertEqual(rc, 2, err)
        self.assertIn("job_user", err)


class StrictShapeTest(unittest.TestCase):
    """Enforce means enforce on every platform (2026-11-03).

    One test per mode per cannot-enforce condition that can be
    honestly constructed, each through main() itself: the startup
    refuses (exit 2), the refusal names the mode and the key, and
    the runner does not proceed in any degraded form -- the
    --audit-report one-shot argv is passed precisely so that a
    step-down would show up as a successful report (exit 0)
    instead of the refusal. The other gate's mode is set off
    explicitly in each config, so each test names the one mode it
    is about, whichever way unset modes are read.

    The cannot-enforce conditions that exist in the code today:
    confinement is Linux+bwrap only (a non-Linux platform, and a
    Linux host whose sandbox backend cannot engage, are two
    distinct conditions), and job_user's setuid demote is
    POSIX-only. policy_env, policy_files, policy_args and
    audience are pure config checks with no platform condition;
    for them the strict pin is the decision-point negative below,
    which covers every feature.
    """

    def test_confinement_enforce_on_win32_refuses_startup(self):
        rc, out, err = run_main(
            {"security": {"modes": {"confinement": "enforce",
                                    "job_user": "off"}}},
            ("--audit-report",), platform="win32")
        self.assertEqual(rc, 2, err)
        self.assertIn("security.modes.confinement", err)
        self.assertNotIn("Security audit report", out)

    def test_job_user_enforce_on_win32_refuses_startup(self):
        rc, out, err = run_main(
            {"security": {"modes": {"job_user": "enforce",
                                    "confinement": "off"},
                          "job_user": {"user": "root"}}},
            ("--audit-report",), platform="win32")
        self.assertEqual(rc, 2, err)
        self.assertIn("security.modes.job_user", err)
        self.assertNotIn("Security audit report", out)

    def test_confinement_enforce_with_a_dead_backend_refuses_startup(self):
        # The Linux-side analogue of the win32 pair, constructed
        # through the scripted startup_problem so it constructs on
        # hosts whose sandbox works too: the backend answer is the
        # environment, and an environment that cannot enforce is a
        # refusal on any platform.
        rc, out, err = run_main(
            {"security": {"modes": {"confinement": "enforce",
                                    "job_user": "off"}}},
            ("--audit-report",),
            sandbox_problem="bwrap is not installed (not found on PATH)")
        self.assertEqual(rc, 2, err)
        self.assertIn("security.modes.confinement", err)
        self.assertIn("bwrap is not installed", err)
        self.assertNotIn("Security audit report", out)

    def test_all_enforce_on_win32_refuses_and_names_a_mode(self):
        # The locked-down posture as a whole on an incapable
        # platform: whichever gate fires first, the startup is a
        # refusal naming a security mode, never a degraded start.
        rc, out, err = run_main(
            {"security": {"modes": {f: "enforce" for f in FEATURES},
                          "job_user": {"user": "root"}}},
            ("--audit-report",), platform="win32")
        self.assertEqual(rc, 2, err)
        self.assertIn("config error: security.modes.", err)
        self.assertNotIn("Security audit report", out)

    def test_no_platform_steps_enforce_down_at_the_decision_point(self):
        # The negative, per feature, on both platform shapes:
        # mode resolution is platform-independent (a configured
        # "enforce" reads "enforce" everywhere), and sec_decide at
        # enforce denies -- it never allows the way audit does and
        # never writes audit's would_* entry. A code path that
        # stepped enforce down to audit on an incapable platform
        # would have to pass through this one decision point, and
        # it would fail here.
        S = RR._security
        for feature in FEATURES:
            cfg = {"security": {"modes": {feature: "enforce"}}}
            for platform in ("linux", "win32"):
                with self.subTest(feature=feature, platform=platform):
                    with mock.patch.object(sys, "platform", platform):
                        self.assertEqual(
                            S.sec_mode(cfg, feature), "enforce")
                        with tempfile.TemporaryDirectory() as d:
                            self.assertFalse(S.sec_decide(
                                cfg, d, feature, "violation",
                                {"key_id": "k", "job_id": "j"}))
                            with open(os.path.join(
                                    d, S.AUDIT_FILE)) as fh:
                                lines = fh.readlines()
                            self.assertEqual(len(lines), 1)
                            entry = json.loads(lines[0])
                            self.assertEqual(entry["decision"], "denied")
                            self.assertEqual(entry["mode"], "enforce")

    def test_audit_and_off_are_unchanged_by_the_platform(self):
        # The control pair for the negative above: the step-down
        # pin would be meaningless if every mode denied. Audit
        # still allows and logs would_deny, off still allows
        # silently, on the simulated incapable platform too --
        # those are the operator's explicit choices, not a
        # platform's substitution for enforce.
        S = RR._security
        with mock.patch.object(sys, "platform", "win32"):
            with tempfile.TemporaryDirectory() as d:
                audit_cfg = {"security": {"modes":
                                          {"policy_env": "audit"}}}
                self.assertTrue(S.sec_decide(
                    audit_cfg, d, "policy_env", "violation", {}))
                with open(os.path.join(d, S.AUDIT_FILE)) as fh:
                    entry = json.loads(fh.readline())
                self.assertEqual(entry["decision"], "would_deny")
            with tempfile.TemporaryDirectory() as d:
                off_cfg = {"security": {"modes":
                                        {"policy_env": "off"}}}
                self.assertTrue(S.sec_decide(
                    off_cfg, d, "policy_env", "violation", {}))
                self.assertFalse(os.path.exists(
                    os.path.join(d, S.AUDIT_FILE)))


class RefuseReaderTest(unittest.TestCase):
    """The refusing readers for blocks main's early path does not
    reach: secrets, the paging thresholds, the transport ports
    and bind. Each raises RuntimeError naming its key."""

    def _refuses(self, fn, *needles):
        with self.assertRaises(RuntimeError) as cm:
            fn()
        for needle in needles:
            self.assertIn(needle, str(cm.exception))

    # -- secrets and their floors --
    def test_shared_secret_missing(self):
        self._refuses(lambda: RR.build_secrets({}), "shared_secret")

    def test_shared_secret_weak(self):
        self._refuses(
            lambda: RR.build_secrets({"shared_secret": "abc123"}),
            "shared_secret", "too weak")

    def test_shared_secret_and_file_both(self):
        self._refuses(
            lambda: RR.build_secrets(
                {"shared_secret": STRONG_SECRET,
                 "shared_secret_file": "/tmp/never-read"}),
            "shared_secret", "shared_secret_file")

    def test_additional_secrets_not_an_object(self):
        self._refuses(
            lambda: RR.build_secrets(
                {"shared_secret": STRONG_SECRET,
                 "additional_secrets": "nope"}),
            "additional_secrets")

    def test_additional_secret_weak(self):
        self._refuses(
            lambda: RR.build_secrets(
                {"shared_secret": STRONG_SECRET,
                 "additional_secrets": {"k2": "weak"}}),
            "shared_secret", "too weak")

    # -- resources: the paging threshold and its companions --
    def test_resources_threshold_not_a_number(self):
        self._refuses(
            lambda: parse_resources({"resources": {"threshold": "high"}}),
            "resources.threshold")

    def test_resources_threshold_out_of_range(self):
        self._refuses(
            lambda: parse_resources({"resources": {"threshold": 1.5}}),
            "resources.threshold")

    def test_resources_cooldown_not_a_number(self):
        self._refuses(
            lambda: parse_resources(
                {"resources": {"cooldown_sec": "soon"}}),
            "resources.cooldown_sec")

    def test_resources_enabled_not_a_boolean(self):
        self._refuses(
            lambda: parse_resources({"resources": {"enabled": "yes"}}),
            "resources.enabled")

    # -- DRI: the other paging thresholds --
    def test_dri_sensor_fused_score_threshold(self):
        self._refuses(
            lambda: parse_dri({"dri": {"triggers": {
                "sensor_fused_score": {"threshold": True}}}}),
            "dri.triggers.sensor_fused_score")

    def test_dri_key_probe_threshold(self):
        self._refuses(
            lambda: parse_dri({"dri": {"triggers": {
                "key_probe": {"threshold": "many"}}}}),
            "dri.triggers.key_probe")

    def test_dri_cooldown_not_a_number(self):
        self._refuses(
            lambda: parse_dri({"dri": {"cooldown_sec": "soon"}}),
            "dri", "cooldown")

    def test_dri_channel_not_offered(self):
        self._refuses(
            lambda: parse_dri({"dri": {"channel": "signal"}}),
            "dri.channel")

    # -- transports: the port and bind reads Q3 moved to refuse --
    def test_transport_dtls_port(self):
        dtls = importlib.import_module(
            "runner.transport_extensions.dtls.__main__")
        self._refuses(lambda: dtls.listen_port({"port": "2O220"}),
                      "transport_dtls.port")
        self._refuses(lambda: dtls.listen_port({"port": 99999}),
                      "transport_dtls.port")
        self._refuses(lambda: dtls.listen_port({"port": True}),
                      "transport_dtls.port")
        # The documented defaults and a usable value still read.
        self.assertEqual(dtls.listen_port({}), 20220)
        self.assertEqual(dtls.listen_port({"port": 20221}), 20221)

    def test_transport_dtls_bind(self):
        dtls = importlib.import_module(
            "runner.transport_extensions.dtls.__main__")
        self._refuses(
            lambda: dtls.bind_address({"bind": "not-an-address"}),
            "transport_dtls.bind")
        self._refuses(lambda: dtls.bind_address({"bind": 42}),
                      "transport_dtls.bind")
        self.assertEqual(dtls.bind_address({}), "0.0.0.0")
        self.assertEqual(dtls.bind_address({"bind": "127.0.0.1"}),
                         "127.0.0.1")

    def test_transport_nats_url_port(self):
        nats = importlib.import_module(
            "runner.transport_extensions.nats.__main__")
        self._refuses(
            lambda: nats.url_port("nats://127.0.0.1:2O220"),
            "transport_nats.url")
        self._refuses(
            lambda: nats.url_port("nats://127.0.0.1:99999"),
            "transport_nats.url")
        self.assertEqual(nats.url_port("nats://127.0.0.1"), 4222)
        self.assertEqual(nats.url_port("nats://127.0.0.1:4223"), 4223)


class DefaultClassTest(unittest.TestCase):
    """Generated below: one test per default-class field. The
    invalid value starts the runner on the documented default,
    and the startup warning names the key."""


# (key, present-but-invalid value, documented default) -- the
# table runner/guard/defaulted.py carries, with the defaults the
# docs promise, pinned here independently of that module.
DEFAULT_FIELDS = [
    ("task_timeout", True, 86400),
    ("default_timeout_sec", True, 300),
    ("max_job_age_sec", True, 3600),
    ("max_plan_steps", True, 8),
    ("max_plan_timeout_sec", True, 600),
    ("oracle_learning_promote_after", True, 2),
    ("review_scan_bytes", True, 65536),
    ("output_retention_days", True, 7),
    ("v2_answer_deadline_sec", True, 0),
    ("query_budget", True, 8),
    ("max_query_budget", True, 8),
    ("local_wake_cooldown_sec", True, 900),
    ("max_output_bytes", True, 100000),
    ("agent_wall_clock_sec", True, 300),
    ("poll_interval_sec", True, 20),
    ("result_stash_retention_sec", True, 86400),
    ("result_resend_backoff_sec", True, 60),
    ("dtls_greeting", "bogus", "family"),
]


def _make_default_tests():
    for key, bad, expected in DEFAULT_FIELDS:

        def default_test(self, key=key, bad=bad, expected=expected):
            # The reader's side: the key is defaulted, the default
            # on record is the documented one, and the summary line
            # (the startup warning's exact text) names the key.
            self.assertTrue(defaulted.is_defaulted(key, bad))
            self.assertEqual(defaulted.default_for(key), expected)
            self.assertEqual(defaulted.defaulted_keys({key: bad}),
                             [key])
            line = defaulted.summary_line([key])
            self.assertIn(key, line)
            # A usable value (the default itself) is not defaulted.
            self.assertFalse(defaulted.is_defaulted(key, expected))
            # The startup side: a real main() proceeds (the
            # read-only --audit-report one-shot returns 0) and its
            # warning line names the key as read-as-default.
            rc, out, err = run_main({key: bad}, ("--audit-report",))
            self.assertEqual(rc, 0, err)
            self.assertIn("read as their default: %s" % key, out)

        setattr(DefaultClassTest, "test_defaults_%s" % key,
                default_test)


_make_default_tests()


class DefaultClassTableTest(unittest.TestCase):
    """The generated family and the module's table are the same
    size: a default-class key added to defaulted.py without a
    test here fails this count instead of slipping through."""

    def test_the_family_covers_the_whole_table(self):
        table = set(defaulted.NUMERIC) | set(defaulted.ENUM)
        self.assertEqual({k for k, _b, _d in DEFAULT_FIELDS}, table)


if __name__ == "__main__":
    unittest.main(verbosity=2)
