#!/usr/bin/env python3
"""Phase 0 of the hosting plan (docs/project/hosting.md): a runner a
provisioner can bring up with one blob and no human on the box.

Three pieces: the `hosted` install profile (attested, advisory,
bwrap enforced, no local signals), the one-blob config
(`--config-json`, refused outside its key set), and the drain plan
behind `--once --drain`, which gives an ephemeral VM a bounded life.
"""
import json
import os
import sys
import tempfile
import types
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import install  # noqa: E402
from runner import runner as R  # noqa: E402


class HostedProfileTest(unittest.TestCase):
    def _apply(self, existing):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(existing, fh)
            install.apply_profile(path, "hosted")
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)

    def test_hosted_is_a_builtin_profile(self):
        self.assertIn("hosted", install.BUILTIN_PROFILES)
        self.assertEqual(install._profile_spec("hosted")["judge"], "advisory")

    def test_hosted_sets_the_ceiling_the_sandbox_and_no_signals(self):
        cfg = self._apply({"shared_secret": "s" * 64})
        self.assertEqual(cfg["max_result_view"], "attested")
        self.assertEqual(cfg["judge"], "advisory")
        self.assertIs(cfg["local_signals"], False)
        self.assertEqual(cfg["security"]["modes"]["confinement"], "enforce")
        self.assertEqual(cfg["security"]["modes"]["audience"], "audit")
        self.assertEqual(cfg["profile"], "hosted")
        self.assertEqual(cfg["shared_secret"], "s" * 64)

    def test_security_modes_merge_one_mode_at_a_time(self):
        cfg = self._apply({"security": {"modes": {"policy_env": "enforce",
                                                  "confinement": "off"},
                                        "other": 1}})
        self.assertEqual(cfg["security"]["modes"]["policy_env"], "enforce")
        self.assertEqual(cfg["security"]["modes"]["confinement"], "enforce")
        self.assertEqual(cfg["security"]["other"], 1)

    def test_other_profiles_do_not_touch_security(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"security": {"modes": {"audience": "off"}}}, fh)
            install.apply_profile(path, "password-only")
            with open(path, encoding="utf-8") as fh:
                cfg = json.load(fh)
        self.assertEqual(cfg["security"], {"modes": {"audience": "off"}})
        self.assertNotIn("local_signals", cfg)


class ConfigBlobTest(unittest.TestCase):
    GOOD = {"shared_secret": "x" * 64, "runner_id": "box-1",
            "workspace_root": "/srv/hp/work",
            "transport_queues": {"url": "https://q.example.test",
                                 "token_env": "HP_QUEUE_TOKEN"}}

    def test_inline_file_and_env_forms_read_the_same(self):
        text = json.dumps(self.GOOD)
        self.assertEqual(install.read_config_blob(text), self.GOOD)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "blob.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.assertEqual(install.read_config_blob("@" + path), self.GOOD)
        os.environ["HP_TEST_BLOB"] = text
        try:
            self.assertEqual(install.read_config_blob("env:HP_TEST_BLOB"),
                             self.GOOD)
        finally:
            del os.environ["HP_TEST_BLOB"]

    def test_none_is_no_blob(self):
        self.assertEqual(install.read_config_blob(None), {})

    def test_security_and_view_keys_are_refused(self):
        for bad in ({"security": {"modes": {"confinement": "off"}}},
                    {"max_result_view": "full"},
                    {"judge": "off"},
                    {"shared_secret": "x", "allow_cleartext": True}):
            with self.subTest(bad=sorted(bad)):
                with self.assertRaises(ValueError) as cm:
                    install.read_config_blob(json.dumps(bad))
                self.assertIn("refused key", str(cm.exception))

    def test_malformed_blobs_say_why(self):
        for spec, needle in (("{not json", "not JSON"),
                             ("[1, 2]", "JSON object"),
                             ("   ", "empty"),
                             ("@/nonexistent/blob.json", "cannot read"),
                             ("env:HP_UNSET_BLOB_XYZ", "not set")):
            with self.subTest(spec=spec):
                with self.assertRaises(ValueError) as cm:
                    install.read_config_blob(spec)
                self.assertIn(needle, str(cm.exception))

    def test_merge_writes_the_blob_over_the_file_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"poll_interval_sec": 5, "judge": "off"}, fh)
            written = install.merge_config_blob(path, json.dumps(self.GOOD))
            with open(path, encoding="utf-8") as fh:
                cfg = json.load(fh)
        self.assertEqual(set(written), set(self.GOOD))
        self.assertEqual(cfg["runner_id"], "box-1")
        self.assertEqual(cfg["judge"], "off")
        self.assertEqual(cfg["poll_interval_sec"], 5)
        self.assertEqual(cfg["transport_queues"]["url"],
                         "https://q.example.test")

    def test_merge_with_no_blob_leaves_the_file_alone(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "config.json")
            self.assertEqual(install.merge_config_blob(path, None), {})
            self.assertFalse(os.path.exists(path))

    def test_blob_then_profile_is_the_hosted_install(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "config.json")
            install.merge_config_blob(path, json.dumps(self.GOOD))
            install.apply_profile(path, "hosted")
            with open(path, encoding="utf-8") as fh:
                cfg = json.load(fh)
        self.assertEqual(cfg["shared_secret"], "x" * 64)
        self.assertEqual(cfg["workspace_root"], "/srv/hp/work")
        self.assertEqual(cfg["security"]["modes"]["confinement"], "enforce")
        self.assertEqual(cfg["max_result_view"], "attested")


class DrainPlanTest(unittest.TestCase):
    def _args(self, **kw):
        base = {"once": True, "drain": 0, "drain_seconds": 0}
        base.update(kw)
        return types.SimpleNamespace(**base)

    def test_plain_once_has_no_plan(self):
        self.assertIsNone(R.drain_plan(self._args()))
        self.assertIsNone(R.drain_plan(self._args(once=False, drain=5)))

    def test_job_cap_counts_seen_growth_from_the_start(self):
        plan = R.drain_plan(self._args(drain=3), seen_size=10)
        self.assertTrue(plan.more(10))
        self.assertTrue(plan.more(12))
        self.assertFalse(plan.more(13))
        self.assertFalse(plan.more(40))

    def test_time_cap_uses_the_clock(self):
        now = [100.0]
        plan = R.DrainPlan(0, 30, clock=lambda: now[0])
        self.assertTrue(plan.more(0))
        now[0] = 129.9
        self.assertTrue(plan.more(0))
        now[0] = 130.0
        self.assertFalse(plan.more(0))

    def test_either_cap_ends_the_drain(self):
        now = [0.0]
        plan = R.DrainPlan(2, 60, start_seen=0, clock=lambda: now[0])
        self.assertTrue(plan.more(1))
        now[0] = 61
        self.assertFalse(plan.more(1))
        plan = R.DrainPlan(2, 60, start_seen=0, clock=lambda: 0.0)
        self.assertFalse(plan.more(2))

    def test_unusable_values_read_as_off(self):
        for bad in (-1, "x", None, float("nan"), 10 ** 400):
            with self.subTest(bad=repr(bad)):
                self.assertIsNone(R.drain_plan(self._args(drain=bad)))
        plan = R.drain_plan(self._args(drain="4"))
        self.assertEqual(plan.jobs, 4)

    def test_seen_shrinking_never_counts_negative(self):
        plan = R.DrainPlan(1, 0, start_seen=50)
        self.assertEqual(plan.done_jobs(40), 0)
        self.assertTrue(plan.more(40))


if __name__ == "__main__":
    unittest.main(verbosity=2)
