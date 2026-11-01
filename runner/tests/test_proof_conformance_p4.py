#!/usr/bin/env python3
"""Stage 5 conformance for P4: a named key can do only what its
policy allows.

The pinning test in test_proof_constraints.py holds the step's
values at the function level. These tests drive the step where
the property lives: at the job's door, through handle_mail,
with the upgrade key's arrangement (C22) as the worked shape,
and at the other doors through check_door_policy. Clause
numbers are properties.md's P4 clauses.
"""
import hashlib
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner import runner  # noqa: E402
from runner.wire import verify as V  # noqa: E402

try:
    from runner.tests import test_proof_conformance as base
except ImportError:  # pragma: no cover - direct-file runs
    import test_proof_conformance as base

SECRET = base.SECRET
UPSECRET = base.UPSECRET
PLAINSECRET = (
    "0f1e2d3c4b5a6978"
    "91a2b3c4d5e6f708"
    "13579bdf02468ace"
    "55aa33cc11ee77ff"
)

PINNED_SCRIPT = "echo stage the release"
PIN = hashlib.sha384(PINNED_SCRIPT.encode("utf-8")).hexdigest()


def _upgrade_cfg(**over):
    cfg = {
        "additional_secrets": {"upgrade": UPSECRET},
        "key_policies": {"upgrade": {
            "allowed_kinds": ["exec"],
            "allowed_script_sha384": [PIN],
            "allowed_files": ["release.zip", "SHA384SUMS"],
            "max_timeout_sec": 300,
        }},
    }
    cfg.update(over)
    return cfg


def _policies(cfg):
    full = {"shared_secret": SECRET}
    full.update(cfg)
    return runner.build_key_policies(full)


def _upgrade_run(job, cfg=None, policies=None):
    cfg = _upgrade_cfg() if cfg is None else cfg
    if policies is None:
        policies = _policies(cfg)
    return base._run(job, None, True, UPSECRET, "upgrade",
                     cfg_extra=cfg, policies=policies)


def _exec(job_id, **extra):
    job = {"kind": "exec", "script": PINNED_SCRIPT}
    job.update(extra)
    return base._job2(job_id, **job)


class UpgradeKeyAtTheDoorTest(base._GateCase):
    """Clauses 5, 7, and 8 in the upgrade arrangement, driven
    through the real gate."""

    def test_the_one_permitted_shape_executes(self):
        out = _upgrade_run(_exec("up-1", timeout_sec=60))
        self.assertEqual(len(out.executed), 1)

    def test_any_other_script_is_refused(self):
        out = _upgrade_run(_exec("up-2", script="echo clock"))
        self.refused(out, "key policy")
        self.said(out, "allowlist")

    def test_a_script_url_is_refused_alone(self):
        job = base._job2("up-3", kind="exec",
                         script_url="https://example.com/stage.sh")
        out = _upgrade_run(job)
        self.refused(out, "key policy")

    def test_a_script_url_beside_the_pinned_script_is_refused(self):
        job = _exec("up-4",
                    script_url="https://example.com/stage.sh")
        out = _upgrade_run(job)
        self.refused(out, "key policy")

    def test_a_missing_script_is_refused(self):
        job = base._job2("up-5", kind="exec")
        out = _upgrade_run(job)
        self.refused(out, "key policy")

    def test_every_other_kind_is_refused(self):
        for kind in ("ping", "sensor_alert", "recipe", "change"):
            job = base._job2("up-kind-" + kind, kind=kind,
                             script=PINNED_SCRIPT)
            out = _upgrade_run(job)
            self.assertEqual(out.executed, [], kind)
            self.said(out, "key policy")

    def test_timeout_at_the_cap_executes(self):
        out = _upgrade_run(_exec("up-6", timeout_sec=300))
        self.assertEqual(len(out.executed), 1)

    def test_timeout_over_the_cap_is_refused(self):
        out = _upgrade_run(_exec("up-7", timeout_sec=301))
        self.refused(out, "exceeds this key's limit")

    def test_the_timeout_default_is_measured_against_the_cap(self):
        cfg = _upgrade_cfg(default_timeout_sec=301)
        out = _upgrade_run(_exec("up-8"), cfg=cfg)
        self.refused(out, "exceeds this key's limit")


class DefaultDenyTest(base._GateCase):
    """Clause 3: no entry means unrestricted, with the one flag,
    and never against the owner."""

    def _cfg(self, **over):
        cfg = {"additional_secrets": {"plain": PLAINSECRET}}
        cfg.update(over)
        return cfg

    def test_entry_less_key_runs_without_the_flag(self):
        job = base._job2("deny-1")
        out = base._run(job, None, True, PLAINSECRET, "plain",
                        cfg_extra=self._cfg(), policies={})
        self.assertEqual(len(out.executed), 1)

    def test_entry_less_key_is_refused_with_the_flag(self):
        job = base._job2("deny-2")
        out = base._run(
            job, None, True, PLAINSECRET, "plain",
            cfg_extra=self._cfg(key_policies_default_deny=True),
            policies={})
        self.refused(out, "key policy")

    def test_the_default_key_is_exempt_from_the_flag(self):
        job = base._job2("deny-3")
        out = base._run(
            job, cfg_extra={"key_policies_default_deny": True},
            policies={})
        self.assertEqual(len(out.executed), 1)

    def test_the_default_key_is_exempt_under_its_fingerprint(self):
        fp = runner._security.key_fingerprint(SECRET)
        job = base._job2("deny-4")
        out = base._run(
            job, None, True, SECRET, fp,
            cfg_extra={"key_policies_default_deny": True},
            policies={})
        self.assertEqual(len(out.executed), 1)


class PolicyIsTheKeysNotTheNamesTest(base._GateCase):
    """Clause 4: the verdict does not depend on which of the
    key's names the sender used."""

    def test_the_fingerprint_name_carries_the_same_fence(self):
        fp = runner._security.key_fingerprint(UPSECRET)
        cfg = _upgrade_cfg()
        policies = _policies(cfg)
        bad = base._run(_exec("name-1", script="echo clock"),
                        None, True, UPSECRET, fp,
                        cfg_extra=cfg, policies=policies)
        self.assertEqual(bad.executed, [])
        good = base._run(_exec("name-2"), None, True, UPSECRET, fp,
                         cfg_extra=cfg, policies=policies)
        self.assertEqual(len(good.executed), 1)


class DirectoryFirstTest(base._GateCase):
    """Clause 2: the key directory's verdict stands in front of
    the policy at the job's door."""

    def test_a_compromised_key_is_refused_though_its_policy_allows(self):
        cfg = _upgrade_cfg(
            key_directory={"upgrade": {"state": "compromised"}})
        out = _upgrade_run(_exec("dir-1"), cfg=cfg)
        self.refused(out, "compromised")

    def test_a_key_with_no_entry_is_refused(self):
        cfg = _upgrade_cfg(
            key_directory={"someone-else": {"state": "in_use"}})
        out = _upgrade_run(_exec("dir-2"), cfg=cfg)
        self.refused(out, "no key directory entry")

    def test_an_unreadable_directory_refuses_the_key(self):
        cfg = _upgrade_cfg(
            key_directory_file="/no/such/directory.json")
        out = _upgrade_run(_exec("dir-3"), cfg=cfg)
        self.assertEqual(out.executed, [])
        self.said(out, "key policy")


class DoorsTest(unittest.TestCase):
    """Clause 9: the same entry binds the query, board, and
    version 2 doors; the cancel door is exempt from the kinds
    list and not from the directory or the deny flag."""

    def _cfg(self, **over):
        cfg = {"shared_secret": SECRET,
               "additional_secrets": {"upgrade": UPSECRET,
                                      "plain": PLAINSECRET},
               "key_policies": {"upgrade": {
                   "allowed_kinds": ["exec"],
                   "allowed_script_sha384": [PIN],
                   "max_timeout_sec": 300}}}
        cfg.update(over)
        return cfg

    def _door(self, cfg, key_id, door):
        secrets = runner.build_secrets(cfg)
        return V.check_door_policy(cfg, secrets, key_id, door)

    def test_the_upgrade_key_is_refused_at_the_other_doors(self):
        cfg = self._cfg()
        for door in ("query", "board", "v2"):
            verdict = self._door(cfg, "upgrade", door)
            self.assertIsNotNone(verdict, door)
            self.assertIn("allowed_kinds", verdict)

    def test_the_cancel_door_is_exempt_from_the_kinds_list(self):
        self.assertIsNone(self._door(self._cfg(), "upgrade", "cancel"))

    def test_the_deny_flag_holds_at_the_cancel_door(self):
        cfg = self._cfg(key_policies_default_deny=True)
        self.assertIsNotNone(self._door(cfg, "plain", "cancel"))

    def test_the_directory_holds_at_the_cancel_door(self):
        cfg = self._cfg(
            key_directory={"upgrade": {"state": "compromised"}})
        self.assertIsNotNone(self._door(cfg, "upgrade", "cancel"))

    def test_an_entry_less_key_passes_the_doors_without_the_flag(self):
        cfg = self._cfg()
        for door in ("query", "board", "v2", "cancel"):
            self.assertIsNone(self._door(cfg, "plain", door), door)


class RecipesAndInterpretersTest(unittest.TestCase):
    """Clause 6 at the step itself: recipes are fenced for
    recipe and change jobs; interpreters are fenced on the
    effective interpreter, and not for recipe or change jobs."""

    def _check(self, pol, job, cfg=None):
        return V.check_key_policy({"k": pol}, "k", cfg or {}, job,
                                  secrets=None)

    def test_recipe_fence(self):
        pol = {"allowed_recipes": ["deploy"]}
        self.assertIsNone(self._check(
            pol, {"kind": "recipe", "recipe": "deploy"}))
        self.assertIsNotNone(self._check(
            pol, {"kind": "recipe", "recipe": "other"}))
        self.assertIsNotNone(self._check(
            pol, {"kind": "change", "recipe": "other"}))
        # The fence does not bind other kinds.
        self.assertIsNone(self._check(pol, {"kind": "exec"}))

    def test_interpreter_fence_uses_the_effective_interpreter(self):
        pol = {"allowed_interpreters": [["sh"]]}
        self.assertIsNone(self._check(
            pol, {"kind": "exec", "interpreter": ["sh"]}))
        self.assertIsNotNone(self._check(
            pol, {"kind": "exec", "interpreter": ["bash"]}))
        # No interpreter of its own: the configured default is
        # the effective one.
        self.assertIsNone(self._check(
            pol, {"kind": "exec"}, cfg={"default_interpreter": ["sh"]}))
        self.assertIsNotNone(self._check(
            pol, {"kind": "exec"}, cfg={"default_interpreter": ["bash"]}))
        # A recipe's interpreter is the owner's: not fenced.
        self.assertIsNone(self._check(
            pol, {"kind": "recipe", "interpreter": ["bash"]}))


class ModeGatedConstraintsTest(base._GateCase):
    """Clause 11: the env, file, and argument constraints behind
    the step are mode-gated -- enforce refuses, audit records
    and runs, off does not compute them."""

    def _cfg(self, mode, feature):
        return {
            "additional_secrets": {"upgrade": UPSECRET},
            "key_policies": {"upgrade": {
                "allowed_kinds": ["exec"],
                "allowed_files": ["release.zip"],
                "allowed_env": ["PATH"],
                "max_args": 1}},
            "security": {"modes": {feature: mode}},
        }

    def _run_mode(self, mode, feature, job, job_id):
        cfg = self._cfg(mode, feature)
        policies = _policies(cfg)
        return base._run(job, None, True, UPSECRET, "upgrade",
                         cfg_extra=cfg, policies=policies)

    def _file_job(self, job_id):
        return base._job2(job_id, kind="exec", script="echo ok",
                          files=[{"name": "evil.txt"}])

    def test_files_enforce_refuses(self):
        out = self._run_mode("enforce", "policy_files",
                             self._file_job("mode-1"), "mode-1")
        self.refused(out, "security policy (policy_files)")

    def test_files_audit_records_and_runs(self):
        out = self._run_mode("audit", "policy_files",
                             self._file_job("mode-2"), "mode-2")
        self.assertEqual(len(out.executed), 1)

    def test_files_off_does_not_compute(self):
        out = self._run_mode("off", "policy_files",
                             self._file_job("mode-3"), "mode-3")
        self.assertEqual(len(out.executed), 1)

    def test_env_enforce_refuses_a_dangerous_name(self):
        job = base._job2("mode-4", kind="exec", script="echo ok",
                         env={"LD_PRELOAD": "/tmp/x.so"})
        out = self._run_mode("enforce", "policy_env", job, "mode-4")
        self.refused(out, "security policy (policy_env)")

    def test_args_enforce_refuses_over_the_cap(self):
        job = base._job2("mode-5", kind="exec", script="echo ok",
                         args=["one", "two"])
        out = self._run_mode("enforce", "policy_args", job, "mode-5")
        self.refused(out, "security policy (policy_args)")


class RepairedJobRejudgedTest(base._GateCase):
    """Clause 10, and stage 3's finding F2 pinned on the real
    path: the one repair the runner makes -- the platform
    interpreter substituted after the claim -- is re-judged
    through the key policy before anything executes, and the
    repair never touches the script."""

    MISSING = ["/no/such/hp-proof-interp"]

    def _repair_run(self, policies):
        job = base._job2("fix-1", kind="exec", script="echo ok",
                         interpreter=self.MISSING)
        return base._run(
            job, cfg_extra={"oracle_opinion_mode": "repair"},
            policies=policies)

    def test_a_repair_the_policy_allows_executes_the_same_script(self):
        platform = runner.platform_interpreter()
        policies = {"": {"allowed_interpreters":
                         [self.MISSING, platform]}}
        out = self._repair_run(policies)
        self.assertEqual(len(out.executed), 1)
        ran = out.executed[0]
        # The job that ran is the repaired one: the platform
        # interpreter, and the script byte-for-byte as received.
        self.assertEqual(ran["interpreter"], platform)
        self.assertEqual(ran["script"], "echo ok")
        self.said(out, "repaired the interpreter")

    def test_a_repaired_job_still_faces_the_pinning_fence(self):
        platform = runner.platform_interpreter()
        pin = hashlib.sha384(b"echo ok").hexdigest()
        policies = {"": {"allowed_script_sha384": [pin],
                         "allowed_interpreters":
                             [self.MISSING, platform]}}
        out = self._repair_run(policies)
        self.assertEqual(len(out.executed), 1)
        self.assertEqual(out.executed[0]["script"], "echo ok")

    def test_a_repair_the_policy_forbids_does_not_execute(self):
        # The pinning holds and the script is the pinned one;
        # only the re-judged interpreter fence can refuse, and
        # it does.
        pin = hashlib.sha384(b"echo ok").hexdigest()
        policies = {"": {"allowed_script_sha384": [pin],
                         "allowed_interpreters": [self.MISSING]}}
        out = self._repair_run(policies)
        self.assertEqual(out.executed, [])
        self.said(out, "repaired job refused")


class MalformedPolicyTest(unittest.TestCase):
    """Clause 12: a malformed policy never reaches the step --
    the builder refuses it as a startup configuration error.
    (The empty-list and boolean-timeout shapes are pinned in
    test_proof_constraints.py; these are the rest of the
    builder's validations.)"""

    def _bad(self, entry):
        with self.assertRaises(RuntimeError):
            V.build_key_policies({"key_policies": {"k": entry}})

    def test_a_non_object_entry(self):
        self._bad("exec")

    def test_a_sub_one_timeout(self):
        self._bad({"max_timeout_sec": 0})

    def test_kinds_as_a_bare_string(self):
        self._bad({"allowed_kinds": "exec"})

    def test_interpreters_as_bare_strings(self):
        self._bad({"allowed_interpreters": ["sh"]})

    def test_an_args_pattern_that_does_not_compile(self):
        self._bad({"args_pattern": "("})

    def test_file_urls_as_a_non_boolean(self):
        self._bad({"allow_file_urls": "yes"})


if __name__ == "__main__":
    unittest.main()
