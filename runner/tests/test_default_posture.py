# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The default posture, pinned across its three layers.

The evidence page (docs/steady/security/default-posture.md) states
what a first-time install does by default. Three different things
are each called "the default": the config-file defaults (the
shipped seed, runner/config.example.json, and the code fallbacks
behind absent keys), the installer profile a fresh install
applies on top of the seed, and the security-mode defaults (a
feature the config does not set reads as enforce). These tests
pin the deterministic claims that hold the three layers
together:

- the seed states every security feature at enforce, and the
  feature names it states are exactly the code's feature list;
- a config with no security block reads every feature as
  enforce, so the permissive side of a first run is the non-mode
  keys (judge off, result view attested), never the modes;
- applying any built-in profile to the seed leaves the effective
  modes all-enforce, except the hosted profile, which sets
  exactly the modes it names;
- the result-view code default, with no key anywhere, is attested.

The behavioral half of the evidence (startup refusals, the
job-time fallback chains) is pinned by the suites that own it:
the test_decision1_startup_* family, test_windows_platform_proofs,
test_confinement, test_security_parity.
"""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.guard import security as SEC  # noqa: E402
from runner.ops import install as I  # noqa: E402
from runner.ops import policy as POLICY  # noqa: E402

SEED_PATH = os.path.join(REPO, "runner", "config.example.json")


def _seed():
    with open(SEED_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _applied(profile):
    """The seed config after the installer applies `profile`."""
    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(_seed(), fh)
        I.apply_profile(path, profile)
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    finally:
        os.unlink(path)


class SeedEnumerationTests(unittest.TestCase):
    def test_seed_modes_are_exactly_the_feature_list(self):
        modes = _seed()["security"]["modes"]
        self.assertEqual(set(modes), set(SEC.FEATURES))
        self.assertEqual(set(modes.values()), {"enforce"})

    def test_seed_effective_modes_all_enforce(self):
        eff = SEC.effective_modes(_seed())
        self.assertEqual(eff, {f: "enforce" for f in SEC.FEATURES})

    def test_absent_security_block_reads_all_enforce(self):
        want = {f: "enforce" for f in SEC.FEATURES}
        self.assertEqual(SEC.effective_modes({}), want)
        self.assertEqual(SEC.effective_modes({"security": None}), want)
        self.assertEqual(SEC.effective_modes({"security": {}}), want)
        self.assertEqual(
            SEC.effective_modes({"security": {"modes": {}}}), want)

    def test_seed_states_the_permissive_layer(self):
        # The "just run it" row of the README posture table, as the
        # seed states it: judge off, attested result view. The fresh
        # install tightens the judge through its profile (below); a
        # hand-written config that omits them gets these.
        seed = _seed()
        self.assertEqual(seed["judge"], "off")
        self.assertEqual(seed["max_result_view"], "attested")
        self.assertIs(seed["security"]["require_posture"], False)

    def test_seed_names_no_job_user(self):
        # The job-user control at enforce has nothing to demote to
        # until the owner names a user; the seed names none.
        sec = _seed()["security"]
        self.assertNotIn("job_user", sec)
        self.assertNotIn("confinement", sec)


class ProfileChainTests(unittest.TestCase):
    def test_only_the_hosted_profile_names_security_modes(self):
        for name, spec in I.BUILTIN_PROFILES.items():
            if name == "hosted":
                self.assertEqual(
                    set(spec["security"]["modes"]),
                    {"confinement", "audience"})
            else:
                self.assertNotIn("security", spec, name)

    def test_profiles_leave_effective_modes_alone(self):
        for name in I.BUILTIN_PROFILES:
            eff = SEC.effective_modes(_applied(name))
            if name == "hosted":
                self.assertEqual(eff["audience"], "audit", name)
                lowered = {f for f, m in eff.items() if m != "enforce"}
                self.assertEqual(lowered, {"audience"}, name)
            else:
                self.assertEqual(
                    eff, {f: "enforce" for f in SEC.FEATURES}, name)

    def test_profiles_tighten_judge_and_view(self):
        for name in ("password-only", "pi-light", "raspberry-pi-home",
                     "display-board", "hosted"):
            cfg = _applied(name)
            self.assertEqual(cfg["judge"], "advisory", name)
            self.assertEqual(cfg["max_result_view"], "attested", name)


class JobUserEngagementTests(unittest.TestCase):
    """Phase 2, item 3's predicate: job_user at enforce with no
    user named engages nothing, and the surfaces that report
    posture name it through this one reader."""

    def test_seed_is_not_engaged(self):
        # The shipped seed: every mode enforce, no job_user block.
        self.assertIsNone(SEC.job_user_configured_user(_seed()))
        self.assertTrue(SEC.job_user_not_engaged(_seed()))

    def test_a_named_user_engages(self):
        cfg = {"security": {"job_user": {"user": "pigeon-jobs"}}}
        self.assertEqual(SEC.job_user_configured_user(cfg),
                         "pigeon-jobs")
        self.assertFalse(SEC.job_user_not_engaged(cfg))

    def test_lower_modes_are_not_the_gap(self):
        for mode in ("audit", "off"):
            cfg = {"security": {"modes": {"job_user": mode}}}
            self.assertFalse(SEC.job_user_not_engaged(cfg), mode)

    def test_shapes_that_name_no_user(self):
        for cfg in ({},
                    {"security": None},
                    {"security": {}},
                    {"security": {"job_user": None}},
                    {"security": {"job_user": "pigeon-jobs"}},
                    {"security": {"job_user": {}}},
                    {"security": {"job_user": {"user": ""}}},
                    {"security": {"job_user": {"user": 123}}},
                    {"security": {"job_user": {"user": None}}}):
            self.assertIsNone(SEC.job_user_configured_user(cfg), cfg)
            self.assertTrue(SEC.job_user_not_engaged(cfg), cfg)

    def test_a_malformed_security_block_reads_off_not_engaged(self):
        # sec_mode reads a malformed block as off; the predicate
        # follows the mode reader, so the answer is not-engaged
        # False (validate_security_config refuses the shape at
        # startup -- a different, louder naming).
        self.assertFalse(SEC.job_user_not_engaged({"security": []}))


class CodeDefaultTests(unittest.TestCase):
    def test_result_view_default_is_attested(self):
        # No ceiling in the config, no view in the job: the result
        # is attested -- the digest and attestations ride, the
        # job's output does not.
        result, retain = POLICY.apply_result_policy(
            {}, {"job_id": "posture-1", "kind": "exec"},
            {"exit_code": 0, "stdout": "hello", "stderr": ""}, {}, True)
        self.assertEqual(result["view"], "attested")
        self.assertEqual(result["stdout"], "")
        self.assertNotIn("hello", json.dumps(result))
        self.assertTrue(retain)

    def test_unset_job_view_reads_attested_under_a_full_ceiling(self):
        # The ask-side fallback, isolated: even under the widest
        # explicit ceiling, a job that asks for nothing reads as
        # the attested default, not as the ceiling.
        result, retain = POLICY.apply_result_policy(
            {"max_result_view": "full"},
            {"job_id": "posture-1a", "kind": "exec"},
            {"exit_code": 0, "stdout": "hello", "stderr": ""}, {}, True)
        self.assertEqual(result["view"], "attested")
        self.assertTrue(retain)

    def test_unset_ceiling_reads_attested_under_a_full_request(self):
        # The ceiling-side fallback, isolated: a job that asks
        # for full in so many words is clamped by the attested
        # default when the owner set no ceiling.
        result, retain = POLICY.apply_result_policy(
            {}, {"job_id": "posture-1b", "kind": "exec",
                 "result_policy": {"view": "full"}},
            {"exit_code": 0, "stdout": "hello", "stderr": ""}, {}, True)
        self.assertEqual(result["view"], "attested")
        self.assertTrue(retain)

    def test_unrecognised_view_reads_attested(self):
        # An unrecognised ask is the documented default, under
        # the widest ceiling and under none alike.
        for cfg in ({"max_result_view": "full"}, {}):
            result, retain = POLICY.apply_result_policy(
                cfg, {"job_id": "posture-1c", "kind": "exec",
                      "result_policy": {"view": "sideways"}},
                {"exit_code": 0, "stdout": "hello", "stderr": ""},
                {}, True)
            self.assertEqual(result["view"], "attested", cfg)
            self.assertTrue(retain, cfg)

    def test_unusable_ceiling_reads_attested(self):
        # A ceiling that is not a view at all -- an unrecognised
        # string or a non-string -- reads as the documented
        # default, so it clamps a full request to attested.
        for ceiling in ("sideways", "FULL", 5, ["full"]):
            result, retain = POLICY.apply_result_policy(
                {"max_result_view": ceiling},
                {"job_id": "posture-1d", "kind": "exec",
                 "result_policy": {"view": "full"}},
                {"exit_code": 0, "stdout": "hello", "stderr": ""},
                {}, True)
            self.assertEqual(result["view"], "attested", ceiling)
            self.assertTrue(retain, ceiling)

    def test_result_view_attested_withholds_output(self):
        # The profile layer's ceiling, for contrast: attested
        # keeps the digest and empties the body (the fields ride
        # along, blank -- measured, not assumed).
        result, retain = POLICY.apply_result_policy(
            {"max_result_view": "attested"},
            {"job_id": "posture-2", "kind": "exec"},
            {"exit_code": 0, "stdout": "hello", "stderr": ""}, {}, True)
        self.assertEqual(result["view"], "attested")
        self.assertEqual(result["stdout"], "")
        self.assertNotIn("hello", json.dumps(result))
        self.assertTrue(retain)


if __name__ == "__main__":
    unittest.main()
