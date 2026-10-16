#!/usr/bin/env python3
"""M2 tests: policy constraints for env, files and args.

Three-mode tests (off/audit/enforce) per feature, plus the pinned
key claim from PROTOCOL.md: a pinned script smuggling BASH_ENV is
denied in enforce mode.
"""
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))

from runner import runner as RR  # noqa: E402
from runner.runner import poll_once  # noqa: E402
from tests.security_parity import (  # noqa: E402
    SECRET,
    FakeIMAP,
    FakeSMTP,
    _email,
    _payload,
    base_config,
    normalize,
    read_audit_lines,
)

SENTINEL = "SENTINEL-ENV-VALUE-zz9"
EXTRA = secrets.token_hex(32)


def pin_script(s):
    return hashlib.sha384(s.encode("utf-8")).hexdigest()


def run_job(cfg_extra, payload, secret=SECRET):
    """Run one job through poll_once. Returns (executed, audit, sent)."""
    tmpdir = tempfile.mkdtemp(prefix="hp-m2-")
    cfg = base_config(tmpdir)
    cfg.update(cfg_extra)
    mail = _email(payload, secret)
    imap = FakeIMAP([mail])
    smtp = FakeSMTP()
    poll_once(cfg, tmpdir, {}, os.path.join(tmpdir, "seen.json"),
              imap=imap, smtp=smtp)
    jid = payload["job_id"]
    executed = any(jid in (m["Subject"] or "") for m in smtp.sent)
    audit = []
    for line in read_audit_lines(tmpdir) or []:
        audit.append(json.loads(line))
    sent = [(m["Subject"], normalize(m.get_content(), tmpdir))
            for m in smtp.sent]
    return executed, audit, sent


def policy_cfg(key="k2", secret=EXTRA, sec_modes=None, **policy):
    base = {"allowed_kinds": ["exec"]}
    base.update(policy)
    cfg = {
        "additional_secrets": {key: secret},
        "key_policies": {key: base},
    }
    if sec_modes is not None:
        cfg["security"] = {"modes": sec_modes}
    return cfg


def modes_for(**kw):
    return dict(kw)


class PolicyEnvModesTest(unittest.TestCase):
    """Three-mode test for policy_env."""

    def _job(self, jid, env):
        p = _payload(jid, kind="exec", script="echo hi", env=env,
                     key_id="k2")
        return p

    def run_mode(self, mode, env, jid="env-01"):
        cfg = policy_cfg(
            denied_env=["EVIL_VAR"],
            sec_modes=modes_for(policy_env=mode, policy_files="off",
                                policy_args="off"))
        return run_job(cfg, self._job(jid, env), secret=EXTRA)

    def test_off_runs_and_logs_nothing(self):
        executed, audit, _ = self.run_mode("off", {"EVIL_VAR": "x"})
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_audit_runs_same_as_off_and_logs(self):
        executed_off, _, sent_off = self.run_mode("off", {"EVIL_VAR": "x"})
        executed, audit, sent = self.run_mode("audit", {"EVIL_VAR": "x"})
        self.assertTrue(executed and executed_off)
        self.assertEqual(sent, sent_off)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["decision"], "would_deny")
        self.assertEqual(audit[0]["feature"], "policy_env")
        self.assertEqual(audit[0]["reason"], "denied_env")

    def test_enforce_denies_and_marks_seen(self):
        executed, audit, _ = self.run_mode("enforce", {"EVIL_VAR": "x"})
        self.assertFalse(executed)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["decision"], "denied")

    def test_enforce_still_runs_compliant_job(self):
        cfg = policy_cfg(
            denied_env=["EVIL_VAR"],
            sec_modes=modes_for(policy_env="enforce", policy_files="off",
                                policy_args="off"))
        executed, audit, _ = run_job(
            cfg, self._job("env-ok", {"HARMLESS": "x"}), secret=EXTRA)
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_dangerous_env_denied(self):
        cfg = policy_cfg(
            sec_modes=modes_for(policy_env="enforce", policy_files="off",
                                policy_args="off"))
        executed, audit, _ = run_job(
            cfg, self._job("env-danger", {"BASH_ENV": "/tmp/evil"}),
            secret=EXTRA)
        self.assertFalse(executed)
        self.assertEqual(audit[0]["reason"], "dangerous_env")

    def test_dangerous_env_allowed_when_listed(self):
        cfg = policy_cfg(
            allowed_env=["BASH_ENV"],
            sec_modes=modes_for(policy_env="enforce", policy_files="off",
                                policy_args="off"))
        executed, audit, _ = run_job(
            cfg, self._job("env-listed", {"BASH_ENV": "/tmp/evil"}),
            secret=EXTRA)
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_sentinel_never_in_audit(self):
        cfg = policy_cfg(
            denied_env=["SENTINEL_VAR"],
            sec_modes=modes_for(policy_env="audit", policy_files="off",
                                policy_args="off"))
        _, audit, _ = run_job(
            cfg, self._job("env-sent", {"SENTINEL_VAR": SENTINEL}),
            secret=EXTRA)
        self.assertEqual(len(audit), 1)
        self.assertNotIn(SENTINEL, json.dumps(audit))


class PolicyFilesModesTest(unittest.TestCase):
    """Three-mode test for policy_files."""

    def _job(self, jid, files):
        return _payload(jid, kind="exec", script="echo hi", files=files,
                        key_id="k2")

    def run_mode(self, mode, files, jid="files-01"):
        cfg = policy_cfg(
            allowed_files=["good.txt"],
            sec_modes=modes_for(policy_env="off", policy_files=mode,
                                policy_args="off"))
        return run_job(cfg, self._job(jid, files), secret=EXTRA)

    def _file(self, name):
        return {"name": name, "url": "https://example.invalid/x"}

    def test_off_runs_and_logs_nothing(self):
        with mock.patch.object(RR, "download") as dl:
            dl.side_effect = lambda url, dest: open(dest, "w").write("x")
            executed, audit, _ = self.run_mode("off", [self._file("evil.txt")])
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_audit_runs_same_as_off_and_logs(self):
        with mock.patch.object(RR, "download") as dl:
            dl.side_effect = lambda url, dest: open(dest, "w").write("x")
            _, _, sent_off = self.run_mode("off", [self._file("evil.txt")])
            executed, audit, sent = self.run_mode(
                "audit", [self._file("evil.txt")])
        self.assertTrue(executed)
        self.assertEqual(sent, sent_off)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["decision"], "would_deny")
        self.assertEqual(audit[0]["reason"], "file_not_allowed")

    def test_enforce_denies(self):
        executed, audit, _ = self.run_mode("enforce", [self._file("evil.txt")])
        self.assertFalse(executed)
        self.assertEqual(audit[0]["decision"], "denied")

    def test_enforce_still_runs_compliant_job(self):
        with mock.patch.object(RR, "download") as dl:
            dl.side_effect = lambda url, dest: open(dest, "w").write("x")
            cfg = policy_cfg(
                allowed_files=["good.txt"],
                sec_modes=modes_for(policy_env="off", policy_files="enforce",
                                    policy_args="off"))
            executed, audit, _ = run_job(
                cfg, self._job("files-ok", [self._file("good.txt")]),
                secret=EXTRA)
        self.assertTrue(executed)
        self.assertEqual(audit, [])


class PolicyArgsModesTest(unittest.TestCase):
    """Three-mode test for policy_args."""

    def _job(self, jid, args):
        return _payload(jid, kind="exec", script="echo", args=args,
                        key_id="k2")

    def run_mode(self, mode, args, jid="args-01"):
        cfg = policy_cfg(
            args_pattern=r"[a-z]+",
            sec_modes=modes_for(policy_env="off", policy_files="off",
                                policy_args=mode))
        return run_job(cfg, self._job(jid, args), secret=EXTRA)

    def test_off_runs_and_logs_nothing(self):
        executed, audit, _ = self.run_mode("off", ["BAD"])
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_audit_runs_same_as_off_and_logs(self):
        _, _, sent_off = self.run_mode("off", ["BAD"])
        executed, audit, sent = self.run_mode("audit", ["BAD"])
        self.assertTrue(executed)
        self.assertEqual(sent, sent_off)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["decision"], "would_deny")
        self.assertEqual(audit[0]["reason"], "arg_pattern_mismatch")

    def test_enforce_denies(self):
        executed, audit, _ = self.run_mode("enforce", ["BAD"])
        self.assertFalse(executed)
        self.assertEqual(audit[0]["decision"], "denied")

    def test_enforce_still_runs_compliant_job(self):
        executed, audit, _ = self.run_mode("enforce", ["good"])
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_long_arg_denied(self):
        executed, audit, _ = self.run_mode("enforce", ["x" * 1025])
        self.assertFalse(executed)
        self.assertEqual(audit[0]["reason"], "arg_too_long")


class PinnedScriptTest(unittest.TestCase):
    """PROTOCOL.md claim: a pinned key cannot be repurposed.

    A pinned script smuggling BASH_ENV (or files) is denied in
    enforce mode, even though the script hash itself is allowlisted.
    """

    def _cfg(self, mode, **policy):
        base = {"allowed_kinds": ["exec"],
                "allowed_script_sha384": [pin_script("echo pinned")]}
        base.update(policy)
        return {
            "additional_secrets": {"pinned": EXTRA},
            "key_policies": {"pinned": base},
            "security": {"modes": {"policy_env": mode, "policy_files": mode,
                                   "policy_args": "off"}},
        }

    def _job(self, jid, **kw):
        p = _payload(jid, kind="exec", script="echo pinned",
                     key_id="pinned")
        p.update(kw)
        return p

    def test_pinned_env_denied_in_enforce(self):
        cfg = self._cfg("enforce")
        executed, audit, _ = run_job(
            cfg, self._job("pin-01", env={"SOME_VAR": "x"}),
            secret=EXTRA)
        self.assertFalse(executed)
        reasons = [a["reason"] for a in audit]
        self.assertIn("pinned_script_with_env", reasons)

    def test_pinned_bash_env_denied_as_dangerous(self):
        cfg = self._cfg("enforce")
        executed, audit, _ = run_job(
            cfg, self._job("pin-01b", env={"BASH_ENV": "/tmp/evil"}),
            secret=EXTRA)
        self.assertFalse(executed)
        reasons = [a["reason"] for a in audit]
        self.assertIn("dangerous_env", reasons)

    def test_pinned_env_allowed_when_listed(self):
        cfg = self._cfg("enforce", allowed_env=["BASH_ENV"])
        executed, audit, _ = run_job(
            cfg, self._job("pin-02", env={"BASH_ENV": "/tmp/evil"}),
            secret=EXTRA)
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_pinned_clean_env_runs(self):
        cfg = self._cfg("enforce")
        executed, audit, _ = run_job(cfg, self._job("pin-03"),
                                     secret=EXTRA)
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_pinned_files_denied_in_enforce(self):
        cfg = self._cfg("enforce")
        executed, audit, _ = run_job(
            cfg, self._job("pin-04",
                           files=[{"name": "x", "url": "https://e.i/x"}]),
            secret=EXTRA)
        self.assertFalse(executed)
        reasons = [a["reason"] for a in audit]
        self.assertIn("pinned_script_with_files", reasons)


class DefaultKeyUnaffectedTest(unittest.TestCase):
    """D3: the default key is unaffected without an explicit entry."""

    def test_default_key_no_policy_entry(self):
        cfg = {
            "security": {"modes": {"policy_env": "enforce",
                                   "policy_files": "enforce",
                                   "policy_args": "enforce"}},
        }
        payload = _payload("dk-01", kind="exec", script="echo hi",
                           env={"BASH_ENV": "/tmp/evil"})
        executed, audit, _ = run_job(cfg, payload)
        self.assertTrue(executed)
        self.assertEqual(audit, [])


class NoNewFieldsTest(unittest.TestCase):
    """A policy with none of the new fields behaves as before."""

    def test_old_policy_unaffected(self):
        cfg = policy_cfg(
            sec_modes=modes_for(policy_env="enforce", policy_files="enforce",
                                policy_args="enforce"))
        payload = _payload("nf-01", kind="exec", script="echo hi",
                           env={"ANYTHING": "x"}, key_id="k2")
        executed, audit, _ = run_job(cfg, payload, secret=EXTRA)
        self.assertTrue(executed)
        self.assertEqual(audit, [])


class DangerousNamesTest(unittest.TestCase):
    def test_constant_contains_documented_names(self):
        for name in ("BASH_ENV", "LD_PRELOAD", "PYTHONPATH",
                     "LD_LIBRARY_PATH", "ENV"):
            self.assertIn(name, RR.DANGEROUS_ENV_NAMES)


class ArgsPatternTimingTest(unittest.TestCase):
    def test_hostile_pattern_rejected_at_parse(self):
        with self.assertRaisesRegex(RuntimeError, "backtrack"):
            RR.build_key_policies({
                "key_policies": {"k": {"args_pattern": r"(a+)+$"}}})

    def test_long_arg_is_fast(self):
        cfg = policy_cfg(
            args_pattern=r"[a-z]+",
            sec_modes=modes_for(policy_env="off", policy_files="off",
                                policy_args="enforce"))
        t0 = time.time()
        executed, _, _ = run_job(
            cfg, _payload("t-01", kind="exec", script="echo",
                          args=["a" * 5000], key_id="k2"),
            secret=EXTRA)
        self.assertFalse(executed)
        self.assertLess(time.time() - t0, 5.0)


class PolicyParseTest(unittest.TestCase):
    def test_bad_shapes_rejected(self):
        bad = [
            {"allowed_env": "FOO"},
            {"allowed_env": []},
            {"denied_env": "FOO"},
            {"allowed_files": []},
            {"args_pattern": ""},
            {"args_pattern": "("},
        ]
        for fields in bad:
            with self.assertRaises(RuntimeError, msg=str(fields)):
                RR.build_key_policies({"key_policies": {"k": fields}})

    def test_good_shapes_accepted(self):
        RR.build_key_policies({"key_policies": {"k": {
            "allowed_env": ["FOO"],
            "denied_env": [],
            "allowed_files": ["a.txt"],
            "args_pattern": r"[a-z]+",
        }}})


if __name__ == "__main__":
    unittest.main(verbosity=2)
