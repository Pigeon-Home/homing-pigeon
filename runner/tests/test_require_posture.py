#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""S5 residue: the --require-posture startup assertion switch.

The default security profile already is the strict one (every
security.modes feature defaults to enforce), so there is no named
"commercial profile" to add. What an operator can pin instead is
one assertion: when require_posture is on, the runner refuses to
start if any security feature sits below enforce, and the refusal
names the lowered feature(s) -- so a later config edit cannot
silently weaken a box that was deployed strict.

Pinned here:

- the config key security.require_posture (a boolean; any other
  shape is a startup config error naming the key);
- the CLI flags --require-posture / --no-require-posture, which
  write the flat require_posture key for one process like every
  other flag, and the flat key beats the config block;
- unpinned (the default): startup behavior is unchanged, lowered
  modes and all;
- pinned with every feature at enforce: startup proceeds;
- pinned with a feature lowered (off or audit): startup refuses
  through main() with exit 2 and the feature named on stderr;
- --posture reports the pin's state.
"""
import contextlib
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

from runner import runner as R  # noqa: E402
from runner.guard import security as S  # noqa: E402
from runner.ops import posture as P  # noqa: E402

STRONG_SECRET = ("9f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c5b4a3928"
                 "a3bf4f1b2b0b822cd15d6c15b0f00a08")


class EnabledTest(unittest.TestCase):
    def test_unpinned_by_default(self):
        self.assertFalse(S.require_posture_enabled({}))
        self.assertFalse(S.require_posture_enabled(None))
        self.assertFalse(S.require_posture_enabled(
            {"security": {"modes": {"confinement": "off"}}}))
        self.assertFalse(S.require_posture_enabled(
            {"security": {"require_posture": False}}))

    def test_config_key_pins_it(self):
        self.assertTrue(S.require_posture_enabled(
            {"security": {"require_posture": True}}))

    def test_flat_key_pins_it(self):
        # The CLI override writes the flat key.
        self.assertTrue(S.require_posture_enabled(
            {"require_posture": True}))

    def test_flat_key_beats_the_config_block(self):
        # --no-require-posture must be able to lift a config pin for
        # one process, the way every other flag beats the file.
        cfg = {"require_posture": False,
               "security": {"require_posture": True}}
        self.assertFalse(S.require_posture_enabled(cfg))
        cfg = {"require_posture": True,
               "security": {"require_posture": False}}
        self.assertTrue(S.require_posture_enabled(cfg))

    def test_only_boolean_true_pins_it(self):
        self.assertFalse(S.require_posture_enabled(
            {"security": {"require_posture": "yes"}}))
        self.assertFalse(S.require_posture_enabled(
            {"security": {"require_posture": 1}}))


class ValidateTest(unittest.TestCase):
    def test_boolean_shapes_pass(self):
        S.validate_security_config(
            {"security": {"require_posture": True}})
        S.validate_security_config(
            {"security": {"require_posture": False}})
        S.validate_security_config({"security": {}})

    def test_non_boolean_is_named(self):
        for bad in ("yes", 1, 0, ["true"]):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(
                        RuntimeError, "security.require_posture"):
                    S.validate_security_config(
                        {"security": {"require_posture": bad}})


class ProblemTest(unittest.TestCase):
    def test_unpinned_never_a_problem(self):
        cfg = {"security": {"modes": {"confinement": "off",
                                      "audience": "audit"}}}
        self.assertIsNone(S.require_posture_problem(cfg))

    def test_pinned_all_enforce_is_no_problem(self):
        self.assertIsNone(S.require_posture_problem(
            {"security": {"require_posture": True}}))
        self.assertIsNone(S.require_posture_problem(
            {"require_posture": True}))

    def test_pinned_names_each_lowered_feature(self):
        cfg = {"security": {
            "require_posture": True,
            "modes": {"confinement": "off", "audience": "audit",
                      "policy_env": "enforce"}}}
        problem = S.require_posture_problem(cfg)
        self.assertIsNotNone(problem)
        self.assertIn("confinement", problem)
        self.assertIn("audience", problem)
        self.assertNotIn("policy_env", problem)
        self.assertNotIn("job_user", problem)

    def test_lowered_features_helper(self):
        cfg = {"security": {"modes": {"confinement": "off"}}}
        self.assertEqual(S.lowered_features(cfg), ["confinement"])
        self.assertEqual(S.lowered_features({}), [])


class CliFlagTest(unittest.TestCase):
    def test_flags_parse_and_override(self):
        ap = R._cli.build_parser()
        args = ap.parse_args(["--require-posture"])
        self.assertIs(args.require_posture, True)
        cfg = {}
        applied = R.apply_cli_overrides(cfg, args)
        self.assertIs(cfg.get("require_posture"), True)
        self.assertIn("require_posture", applied)

        args = ap.parse_args(["--no-require-posture"])
        self.assertIs(args.require_posture, False)
        cfg = {"security": {"require_posture": True}}
        R.apply_cli_overrides(cfg, args)
        self.assertIs(cfg.get("require_posture"), False)
        self.assertFalse(S.require_posture_enabled(cfg))

    def test_no_flag_leaves_config_alone(self):
        ap = R._cli.build_parser()
        args = ap.parse_args([])
        self.assertIsNone(args.require_posture)
        cfg = {}
        R.apply_cli_overrides(cfg, args)
        self.assertNotIn("require_posture", cfg)


BASE = {"mailbox_user": "a@b.c", "mailbox_password": "p",
        "shared_secret": STRONG_SECRET}


def _run_main(extra, argv_extra=("--posture",), sandbox_ok=True):
    """One real startup through main(). (rc, stdout, stderr)."""
    tmpdir = tempfile.mkdtemp(prefix="hp-s5-")
    cfg = dict(BASE, base_dir=tmpdir)
    cfg.update(extra)
    cfg_path = os.path.join(tmpdir, "config.json")
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    out, err = io.StringIO(), io.StringIO()
    argv = ["runner", "--config", cfg_path, *argv_extra]
    with contextlib.ExitStack() as stack:
        if sandbox_ok:
            # The all-enforce config reaches the confinement gate;
            # script the backend as able so the require-posture
            # assertion is the only gate under test.
            stack.enter_context(mock.patch.object(
                R._sandbox, "startup_problem", lambda: None))
        stack.enter_context(mock.patch.object(sys, "argv", argv))
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = R.main()
    return rc, out.getvalue(), err.getvalue()


class StartupAssertionTest(unittest.TestCase):
    def test_pinned_with_lowered_modes_refuses_naming_them(self):
        rc, _out, err = _run_main({"security": {
            "require_posture": True,
            "modes": {"confinement": "off", "job_user": "off"}}})
        self.assertEqual(rc, 2)
        self.assertIn("require_posture", err)
        self.assertIn("confinement", err)
        self.assertIn("job_user", err)

    def test_pinned_via_cli_flag_refuses(self):
        rc, _out, err = _run_main(
            {"security": {"modes": {"confinement": "off",
                                    "job_user": "off"}}},
            argv_extra=("--posture", "--require-posture"))
        self.assertEqual(rc, 2)
        self.assertIn("confinement", err)

    def test_pinned_all_enforce_starts(self):
        rc, out, err = _run_main(
            {"security": {"require_posture": True}})
        self.assertNotEqual(rc, 2, err)
        self.assertIn("Security posture", out)

    def test_unpinned_lowered_modes_start_unchanged(self):
        rc, out, err = _run_main({"security": {
            "modes": {"confinement": "off", "job_user": "off"}}})
        self.assertNotEqual(rc, 2, err)
        self.assertIn("Security posture", out)

    def test_non_boolean_require_posture_refuses_naming_the_key(self):
        rc, _out, err = _run_main(
            {"security": {"require_posture": "yes"}})
        self.assertEqual(rc, 2)
        self.assertIn("security.require_posture", err)


class PostureReportTest(unittest.TestCase):
    def _results(self, cfg):
        d = tempfile.mkdtemp(prefix="hp-s5-posture-")
        cfg_path = os.path.join(d, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        return P.build_posture(cfg, cfg_path, d)

    def test_pinned_and_clean_is_ok(self):
        results = self._results(
            {"security": {"require_posture": True}})
        self.assertTrue(any(
            "require_posture" in msg and level == "OK"
            for level, _, msg in results), results)

    def test_pinned_and_lowered_is_a_fail(self):
        results = self._results({"security": {
            "require_posture": True,
            "modes": {"confinement": "off"}}})
        self.assertTrue(any(
            level == "FAIL" and "confinement" in msg
            for level, _, msg in results), results)

    def test_unpinned_adds_no_require_posture_line(self):
        results = self._results({})
        self.assertFalse(any(
            "require_posture" in msg for _, _, msg in results),
            results)


if __name__ == "__main__":
    unittest.main(verbosity=2)
