#!/usr/bin/env python3
"""Multi-secret key_id tests (v3 Piece 1)."""
import os
import sys
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

from runner.runner import (build_secrets, verify_body_keyed, poll_once,
                           build_key_policies,
                           check_key_policy, unrestricted_extra_keys)
from send_job import sign_payload

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"
OTHER = "f293c686da58b28fc08f44e13d722e6c0533a94e08c0ae6cb20f2aa1be1a74bf"
SENDER = "runner@example.com"


class MultiSecretTest(unittest.TestCase):
    def test_build_secrets_default(self):
        cfg = {"shared_secret": SECRET}
        s = build_secrets(cfg)
        self.assertEqual(s[""], SECRET)
        self.assertEqual(len(s), 1)

    def test_build_secrets_additional(self):
        cfg = {"shared_secret": SECRET, "additional_secrets": {"worker1": OTHER}}
        s = build_secrets(cfg)
        self.assertEqual(s["worker1"], OTHER)

    def test_build_rejects_weak(self):
        with self.assertRaises(RuntimeError):
            build_secrets({"shared_secret": "short"})

    def test_verify_keyed_default(self):
        payload = {"v": 1, "type": "job", "job_id": "x", "kind": "ping"}
        body = sign_payload(payload, SECRET)
        got, kid = verify_body_keyed(body, {"": SECRET})
        self.assertEqual(kid, "")
        self.assertEqual(got["kind"], "ping")

    def test_verify_keyed_named(self):
        payload = {"v": 1, "type": "job", "job_id": "x", "kind": "ping", "key_id": "worker1"}
        body = sign_payload(payload, OTHER)
        got, kid = verify_body_keyed(body, {"": SECRET, "worker1": OTHER})
        self.assertEqual(kid, "worker1")

    def test_unknown_key_rejected_before_crypto(self):
        payload = {"v": 1, "type": "job", "job_id": "x", "kind": "ping", "key_id": "nope"}
        body = sign_payload(payload, OTHER)
        with self.assertRaises(ValueError) as cm:
            verify_body_keyed(body, {"": SECRET})
        self.assertIn("unknown key_id", str(cm.exception))

    def test_tamper_rejected(self):
        payload = {"v": 1, "type": "job", "job_id": "x", "kind": "ping"}
        body = sign_payload(payload, SECRET).replace('"ping"', '"p1ng"')
        with self.assertRaises(ValueError):
            verify_body_keyed(body, {"": SECRET})


class KeyPolicyTest(unittest.TestCase):
    """Per-key policies are opt-in: no entry means unrestricted."""

    def test_no_policy_unrestricted(self):
        cfg = {}
        job = {"kind": "exec", "script": "rm -rf /",
               "interpreter": ["bash"], "timeout_sec": 3600}
        self.assertIsNone(check_key_policy({}, "worker1", cfg, job))
        self.assertIsNone(check_key_policy({}, "", cfg, job))

    def test_allowed_kinds(self):
        pol = build_key_policies(
            {"key_policies": {"w": {"allowed_kinds": ["ping"]}}})["w"]
        cfg = {}
        self.assertIsNone(
            check_key_policy({"w": pol}, "w", cfg, {"kind": "ping"}))
        self.assertIsNotNone(
            check_key_policy({"w": pol}, "w", cfg,
                             {"kind": "exec", "script": "echo hi"}))

    def test_allowed_interpreters(self):
        pol = build_key_policies(
            {"key_policies": {"w": {"allowed_interpreters": [["bash"]]}}})["w"]
        cfg = {}
        ok = {"kind": "exec", "script": "echo hi", "interpreter": ["bash"]}
        bad = {"kind": "exec", "script": "echo hi",
               "interpreter": ["python3"]}
        self.assertIsNone(check_key_policy({"w": pol}, "w", cfg, ok))
        self.assertIsNotNone(check_key_policy({"w": pol}, "w", cfg, bad))

    def test_interpreter_falls_back_to_config_default(self):
        pol = build_key_policies(
            {"key_policies": {"w": {"allowed_interpreters": [["bash"]]}}})["w"]
        cfg = {"default_interpreter": ["bash"]}
        job = {"kind": "exec", "script": "echo hi"}  # no interpreter field
        self.assertIsNone(check_key_policy({"w": pol}, "w", cfg, job))
        cfg2 = {"default_interpreter": ["python3"]}
        self.assertIsNotNone(check_key_policy({"w": pol}, "w", cfg2, job))

    def test_max_timeout(self):
        pol = build_key_policies(
            {"key_policies": {"w": {"max_timeout_sec": 60}}})["w"]
        cfg = {}
        self.assertIsNone(check_key_policy(
            {"w": pol}, "w", cfg, {"kind": "ping", "timeout_sec": 60}))
        self.assertIsNotNone(check_key_policy(
            {"w": pol}, "w", cfg, {"kind": "ping", "timeout_sec": 61}))

    def test_script_allowlist(self):
        script = "pytest -q"
        digest = hashlib.sha384(script.encode()).hexdigest()
        pol = build_key_policies(
            {"key_policies": {"w": {"allowed_script_sha384": [digest]}}})["w"]
        cfg = {}
        good = {"kind": "exec", "script": script, "interpreter": ["bash"]}
        evil = {"kind": "exec", "script": "rm -rf /",
                "interpreter": ["bash"]}
        url = {"kind": "exec", "script_url": "https://x/y.sh",
               "interpreter": ["bash"]}
        ping = {"kind": "ping"}
        self.assertIsNone(check_key_policy({"w": pol}, "w", cfg, good))
        self.assertIsNotNone(check_key_policy({"w": pol}, "w", cfg, evil))
        self.assertIsNotNone(check_key_policy({"w": pol}, "w", cfg, url))
        # ping has no script; governed by allowed_kinds only
        self.assertIsNone(check_key_policy({"w": pol}, "w", cfg, ping))

    def test_policy_on_default_key(self):
        pol = build_key_policies(
            {"key_policies": {"": {"allowed_kinds": ["ping"]}}})[""]
        cfg = {}
        self.assertIsNone(check_key_policy({"": pol}, "", cfg,
                                            {"kind": "ping"}))
        self.assertIsNotNone(check_key_policy(
            {"": pol}, "", cfg, {"kind": "exec", "script": "x"}))

    def test_policy_enforced_end_to_end(self):
        from tests.test_runner import FakeIMAP, FakeSMTP, job_email
        tmp = tempfile.mkdtemp(prefix="hp-pol-")
        cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": SECRET,
            "shared_secret": SECRET,
            "additional_secrets": {"w": OTHER},
            "key_policies": {"w": {"allowed_kinds": ["ping"]}},
            "base_dir": tmp,
            "workers": 1,
        }
        payload = {
            "v": 1, "type": "job", "job_id": "j-pol",
            "kind": "exec", "script": "echo hello",
            "interpreter": ["bash"],
            "issued_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "key_id": "w",
        }
        imap = FakeIMAP([job_email(payload, secret=OTHER)])
        smtp = FakeSMTP()
        poll_once(cfg, tmp, {}, os.path.join(tmp, "seen.json"),
                  imap=imap, smtp=smtp)
        # policy violation: rejected, nothing executed, no result mailed
        self.assertEqual(smtp.sent, [])
        self.assertIn("1", imap.flagged)

    def test_malformed_policies_rejected(self):
        for bad in ({"w": {"allowed_kinds": "ping"}},
                    {"w": {"allowed_kinds": []}},
                    {"w": {"allowed_interpreters": ["bash"]}},
                    {"w": {"max_timeout_sec": 0}},
                    {"w": {"max_timeout_sec": "lots"}},
                    {"w": {"allowed_script_sha384": []}},
                    {"w": "just-a-string"}):
            with self.assertRaises(RuntimeError, msg=str(bad)):
                build_key_policies({"key_policies": bad})
        with self.assertRaises(RuntimeError):
            build_key_policies({"key_policies": ["not", "a", "dict"]})


class KeyPolicyDefaultDenyTest(unittest.TestCase):
    """key_policies_default_deny: opt-in strict for additional keys.

    The default stays loose: without the flag, a key with no entry is
    unrestricted. The default key ("") is never affected by the flag.
    """

    def _job(self):
        return {"kind": "ping"}

    def test_loose_by_default(self):
        cfg = {}
        self.assertIsNone(check_key_policy({}, "worker1", cfg, self._job()))

    def test_deny_refuses_key_without_entry(self):
        cfg = {"key_policies_default_deny": True}
        reason = check_key_policy({}, "worker1", cfg, self._job())
        self.assertIsNotNone(reason)
        self.assertIn("key_policies_default_deny", reason)

    def test_deny_never_touches_default_key(self):
        cfg = {"key_policies_default_deny": True}
        self.assertIsNone(check_key_policy({}, "", cfg, self._job()))

    def test_deny_policy_entry_still_governs(self):
        cfg = {"key_policies_default_deny": True}
        pol = build_key_policies(
            {"key_policies": {"w": {"allowed_kinds": ["ping"]}}})
        self.assertIsNone(check_key_policy(pol, "w", cfg, {"kind": "ping"}))
        self.assertIsNotNone(
            check_key_policy(pol, "w", cfg, {"kind": "exec",
                                             "script": "x",
                                             "interpreter": ["bash"]}))

    def test_deny_with_none_cfg(self):
        # defensive: truthiness check must not crash on a bare call
        self.assertIsNone(check_key_policy({}, "worker1", None, self._job()))


class UnrestrictedExtraKeysTest(unittest.TestCase):
    def test_lists_missing_entries(self):
        cfg = {"additional_secrets": {"b-key": "s", "a-key": "s"},
               "key_policies": {"a-key": {"allowed_kinds": ["ping"]}}}
        self.assertEqual(unrestricted_extra_keys(cfg), ["b-key"])

    def test_default_key_never_listed(self):
        cfg = {"shared_secret": "s", "additional_secrets": {}}
        self.assertEqual(unrestricted_extra_keys(cfg), [])

    def test_all_covered_quiet(self):
        cfg = {"additional_secrets": {"w": "s"},
               "key_policies": {"w": {"allowed_kinds": ["ping"]}}}
        self.assertEqual(unrestricted_extra_keys(cfg), [])

    def test_bad_shapes(self):
        self.assertEqual(unrestricted_extra_keys({}), [])
        self.assertEqual(
            unrestricted_extra_keys({"additional_secrets": ["x"]}), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
