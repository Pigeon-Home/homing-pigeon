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
  keys (judge off, result view full), never the modes;
- applying any built-in profile to the seed leaves the effective
  modes all-enforce, except the hosted profile, which sets
  exactly the modes it names;
- the result-view code default, with no key anywhere, is full.

The behavioral half of the evidence (startup refusals, the
job-time fallback chains) is pinned by the suites that own it:
test_decision1_startup, test_windows_platform_proofs,
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
        # seed states it: judge off, full result view. The fresh
        # install tightens both through its profile (below); a
        # hand-written config that omits them gets these.
        seed = _seed()
        self.assertEqual(seed["judge"], "off")
        self.assertEqual(seed["max_result_view"], "full")
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


class CodeDefaultTests(unittest.TestCase):
    def test_result_view_default_is_full(self):
        # No ceiling in the config, no view in the job: the result
        # carries the job's output in full.
        result, retain = POLICY.apply_result_policy(
            {}, {"job_id": "posture-1", "kind": "exec"},
            {"exit_code": 0, "stdout": "hello", "stderr": ""}, {}, True)
        self.assertEqual(result["view"], "full")
        self.assertEqual(result["stdout"], "hello")
        self.assertFalse(retain)

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
