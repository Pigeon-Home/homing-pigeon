#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Decision 1 startup family: one test per config field.

Decision 1 (docs/design/present-but-invalid-config.md, settled
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
BASE = {"mailbox_user": "a@b.c", "mailbox_password": "p",
        "shared_secret": STRONG_SECRET}


def run_main(extra, argv_extra=()):
    """One real startup through main(). Returns (rc, stdout, stderr).

    The config lives in a fresh temp dir whose path is also the
    runner's base_dir, so a startup that proceeds cannot touch
    real state; --audit-report (used by the default-class tests)
    returns before any mailbox work.
    """
    tmpdir = tempfile.mkdtemp(prefix="hp-d1-")
    cfg = dict(BASE, base_dir=tmpdir)
    cfg.update(extra)
    cfg_path = os.path.join(tmpdir, "config.json")
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    out, err = io.StringIO(), io.StringIO()
    argv = ["runner", "--config", cfg_path, *argv_extra]
    with mock.patch.object(sys, "argv", argv):
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
