#!/usr/bin/env python3
# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""The hosting adapters against recorded API exchanges (Phase 1 and
Phase 3 of docs/project/hosting.md). No live calls: every request is
answered by runner/tests/hosting_player.py from the fixtures.

Per provider: create, poll to running, destroy, and the error shapes
(401, 429 with its retry hint, 404 as `gone`, a 5xx, a transport
failure, a machine that never comes up). Then the bootstrap that
every provider hands a fresh machine, and the GitHub Actions
ephemeral backend end to end: dispatch, find the run, wait, bill.
"""
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.hosting import base, bootstrap, digitalocean, fly  # noqa: E402
from runner.hosting import github_actions, hetzner  # noqa: E402
from runner.hosting.httpdoor import Response, TransportError  # noqa: E402
from runner.tests.hosting_player import Player  # noqa: E402

BLOB = {"shared_secret": "a" * 64, "runner_id": "alice-1",
        "workspace_root": "/srv/hp/work",
        "transport_queues": {"url": "https://q.example.test/alice",
                             "token_env": "HP_QUEUE_TOKEN"}}


def spec(**kw):
    args = {"tenant": "alice", "region": "iad", "size": None,
            "version": "3.13.2", "blob": BLOB}
    args.update(kw)
    return base.MachineSpec(**args)


class NoSleep:
    def __init__(self):
        self.calls = []

    def __call__(self, s):
        self.calls.append(s)


class ResponseTest(unittest.TestCase):
    def test_json_is_lazy_and_forgiving(self):
        self.assertIsNone(Response(200, {}, b"").json())
        self.assertIsNone(Response(502, {}, b"<html>").json())
        self.assertEqual(Response(200, {}, b'{"a": 1}').json(), {"a": 1})
        r = Response(429, {"Retry-After": "7"}, "x")
        self.assertEqual(r.header("retry-after"), "7")
        self.assertFalse(r.ok)
        self.assertTrue(Response(204).ok)

    def test_raise_for_picks_the_typed_error(self):
        with self.assertRaises(base.AuthError):
            base.raise_for(Response(401), "p", "x")
        with self.assertRaises(base.AuthError):
            base.raise_for(Response(403), "p", "x")
        with self.assertRaises(base.NotFound):
            base.raise_for(Response(404), "p", "x")
        with self.assertRaises(base.RateLimited) as cm:
            base.raise_for(Response(429, {"Retry-After": "12"}), "p", "x")
        self.assertEqual(cm.exception.retry_after, 12.0)
        with self.assertRaises(base.RateLimited) as cm:
            base.raise_for(Response(429, {"Retry-After": "soon"}), "p", "x")
        self.assertIsNone(cm.exception.retry_after)
        with self.assertRaises(base.ProviderError) as cm:
            base.raise_for(Response(500), "p", "x", code="boom",
                           message="it broke")
        self.assertEqual(cm.exception.status, 500)
        self.assertIn("it broke", str(cm.exception))


class MachineSpecTest(unittest.TestCase):
    def test_tenant_is_required_and_labels_carry_tenant_and_version(self):
        with self.assertRaises(ValueError):
            base.MachineSpec("", "iad", None, "3.13.2", {})
        s = spec()
        self.assertEqual(s.name, "hp-alice")
        self.assertEqual(s.labels["homing-pigeon.tenant"], "alice")
        self.assertEqual(s.labels["homing-pigeon.version"], "3.13.2")
        self.assertEqual(s.blob["runner_id"], "alice-1")
        self.assertIsNot(s.blob, BLOB)


class FlyTest(unittest.TestCase):
    def _fly(self, script):
        http = Player("fly", script)
        return fly.FlyMachines(http, "fo1_token"), http

    def test_create_makes_the_app_then_the_machine(self):
        f, http = self._fly(["create-app-ok", "create-machine-ok"])
        m = f.create(spec())
        self.assertEqual(m.id, "e784079b561e58")
        self.assertEqual(m.state, "created")
        self.assertEqual(m.region, "iad")
        self.assertEqual(m.tenant, "alice")
        self.assertEqual(m.version, "3.13.2")
        self.assertTrue(http.exhausted())
        app_call, machine_call = http.calls
        self.assertEqual(app_call["body"]["app_name"], "hp-alice")
        cfg = machine_call["body"]["config"]
        self.assertEqual(cfg["image"], "ghcr.io/pigeon-home/homing-pigeon:3.13.2")
        self.assertEqual(cfg["guest"], {"cpu_kind": "shared", "cpus": 1,
                                        "memory_mb": 256})
        self.assertEqual(json.loads(cfg["env"]["HP_CONFIG_BLOB"]), BLOB)
        self.assertEqual(cfg["env"]["HP_PROFILE"], "hosted")
        self.assertEqual(cfg["metadata"]["homing-pigeon.tenant"], "alice")
        self.assertEqual(machine_call["headers"]["Authorization"],
                         "Bearer fo1_token")

    def test_an_existing_app_is_not_an_error(self):
        f, http = self._fly(["create-app-exists", "create-machine-ok"])
        self.assertEqual(f.create(spec()).id, "e784079b561e58")

    def test_wait_polls_until_started(self):
        f, http = self._fly(["get-machine-starting", "get-machine-starting",
                             "get-machine-started"])
        f.app = "hp-alice"
        sleep = NoSleep()
        m = f.wait_running("e784079b561e58", timeout=60, interval=5,
                           sleep=sleep, clock=lambda: 0.0)
        self.assertEqual(m.state, "running")
        self.assertEqual(sleep.calls, [5, 5])

    def test_wait_gives_up_on_the_budget(self):
        f, http = self._fly(["get-machine-starting"] * 3)
        f.app = "hp-alice"
        ticks = iter([0, 30, 61, 100])
        with self.assertRaises(base.ProvisionTimeout):
            f.wait_running("e784079b561e58", timeout=60, interval=5,
                           sleep=lambda s: None, clock=lambda: next(ticks))

    def test_a_404_reads_as_gone_and_destroy_is_idempotent(self):
        f, http = self._fly(["get-machine-gone", "destroy-ok"])
        f.app = "hp-alice"
        self.assertEqual(f.get("nope").state, "gone")
        self.assertIsNone(f.destroy("e784079b561e58"))
        self.assertEqual(http.calls[-1]["method"], "DELETE")
        self.assertTrue(http.calls[-1]["url"].endswith("?force=true"))

    def test_error_shapes(self):
        f, _ = self._fly(["unauthorized"])
        with self.assertRaises(base.AuthError):
            f.create(spec())
        f, _ = self._fly(["create-app-ok", "rate-limited"])
        with self.assertRaises(base.RateLimited) as cm:
            f.create(spec())
        self.assertEqual(cm.exception.retry_after, 7.0)
        f, _ = self._fly(["create-app-ok", "server-error"])
        with self.assertRaises(base.ProviderError) as cm:
            f.create(spec())
        self.assertEqual(cm.exception.status, 502)
        f, _ = self._fly(["TRANSPORT-FAIL"])
        with self.assertRaises(TransportError):
            f.create(spec())


class HetznerTest(unittest.TestCase):
    def _hz(self, script):
        http = Player("hetzner", script)
        return hetzner.HetznerCloud(http, "hz_token"), http

    def test_create_sends_cloud_init_and_labels(self):
        hz, http = self._hz(["create-ok"])
        m = hz.create(spec(region="nbg1"))
        self.assertEqual(m.id, "42")
        self.assertEqual(m.state, "starting")
        self.assertEqual(m.ip, "203.0.113.10")
        self.assertEqual(m.region, "nbg1")
        self.assertEqual(m.tenant, "alice")
        body = http.calls[0]["body"]
        self.assertEqual(body["server_type"], "cx23")
        self.assertEqual(body["image"], "ubuntu-24.04")
        self.assertEqual(body["location"], "nbg1")
        self.assertIn("homing-pigeon-install --system --no-inference "
                      "--profile hosted", body["user_data"])
        self.assertIn("pigeon-home-runner==3.13.2", body["user_data"])
        self.assertNotIn("hz_token", body["user_data"])

    def test_wait_and_destroy(self):
        hz, http = self._hz(["get-initializing", "get-running", "delete-ok"])
        m = hz.wait_running("42", timeout=30, interval=1,
                            sleep=lambda s: None, clock=lambda: 0.0)
        self.assertEqual(m.state, "running")
        self.assertIsNone(hz.destroy("42"))

    def test_error_shapes(self):
        hz, _ = self._hz(["get-gone"])
        self.assertEqual(hz.get("999").state, "gone")
        hz, _ = self._hz(["unauthorized"])
        with self.assertRaises(base.AuthError) as cm:
            hz.create(spec(region="nbg1"))
        self.assertEqual(cm.exception.code, "unauthorized")
        hz, _ = self._hz(["rate-limited"])
        with self.assertRaises(base.RateLimited) as cm:
            hz.create(spec(region="nbg1"))
        self.assertEqual(cm.exception.retry_after, 30.0)
        self.assertEqual(cm.exception.code, "rate_limit_exceeded")
        hz, _ = self._hz(["uniqueness"])
        with self.assertRaises(base.ProviderError) as cm:
            hz.create(spec(region="nbg1"))
        self.assertEqual(cm.exception.code, "uniqueness_error")
        self.assertEqual(cm.exception.status, 409)


class DigitalOceanTest(unittest.TestCase):
    def _do(self, script):
        http = Player("digitalocean", script)
        return digitalocean.DigitalOcean(http, "dop_token"), http

    def test_create_tags_carry_tenant_and_version(self):
        do, http = self._do(["create-ok"])
        m = do.create(spec(region="nyc3"))
        self.assertEqual(m.id, "3164494")
        self.assertEqual(m.state, "starting")
        self.assertIsNone(m.ip)
        self.assertEqual(m.tenant, "alice")
        self.assertEqual(m.version, "3.13.2")
        body = http.calls[0]["body"]
        self.assertEqual(body["size"], "s-1vcpu-512mb-10gb")
        self.assertEqual(body["tags"], ["hp-tenant-alice", "hp-version-3-13-2"])
        self.assertIn("#!/bin/sh", body["user_data"])

    def test_public_ip_appears_when_active(self):
        do, http = self._do(["get-new", "get-active", "delete-ok"])
        m = do.wait_running("3164494", timeout=30, interval=1,
                            sleep=lambda s: None, clock=lambda: 0.0)
        self.assertEqual(m.state, "running")
        self.assertEqual(m.ip, "198.51.100.7")
        self.assertIsNone(do.destroy("3164494"))

    def test_error_shapes(self):
        do, _ = self._do(["get-gone"])
        self.assertEqual(do.get("1").state, "gone")
        do, _ = self._do(["unauthorized"])
        with self.assertRaises(base.AuthError):
            do.create(spec(region="nyc3"))
        do, _ = self._do(["rate-limited"])
        with self.assertRaises(base.RateLimited) as cm:
            do.create(spec(region="nyc3"))
        self.assertEqual(cm.exception.retry_after, 45.0)
        do, _ = self._do(["unprocessable"])
        with self.assertRaises(base.ProviderError) as cm:
            do.create(spec(region="nyc3"))
        self.assertEqual(cm.exception.code, "unprocessable_entity")
        self.assertIn("invalid region", str(cm.exception))


class BootstrapTest(unittest.TestCase):
    def test_pinned_requirement_takes_only_a_release(self):
        self.assertEqual(bootstrap.pinned_requirement("3.13.2"),
                         "pigeon-home-runner==3.13.2")
        self.assertEqual(bootstrap.pinned_requirement("v3.13.2"),
                         "pigeon-home-runner==3.13.2")
        for bad in ("", "latest", "3.13", "3.13.2; rm -rf /", None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    bootstrap.pinned_requirement(bad)

    def test_image_for_pins_the_tag(self):
        self.assertEqual(bootstrap.image_for("3.13.2"),
                         "ghcr.io/pigeon-home/homing-pigeon:3.13.2")
        self.assertEqual(bootstrap.image_for("3.13.2", "registry.test/x:dev"),
                         "registry.test/x:dev")
        self.assertEqual(bootstrap.image_for("3.13.2", "registry.test/x"),
                         "registry.test/x:3.13.2")

    def test_user_data_is_a_root_only_idempotent_shell_script(self):
        text = bootstrap.user_data(spec())
        self.assertTrue(text.startswith("#!/bin/sh\n"))
        self.assertIn("set -eu", text)
        self.assertIn("umask 077", text)
        self.assertIn("/etc/homing-pigeon/blob.json", text)
        self.assertIn(json.dumps(BLOB, sort_keys=True), text)
        self.assertIn("bubblewrap", text)
        self.assertIn("--config-json @/etc/homing-pigeon/blob.json", text)
        self.assertNotIn("Bearer", text)

    def test_blob_with_quotes_survives_shell_quoting(self):
        import shlex
        tricky = dict(BLOB, owner_instructions="it's \"quoted\" $HOME `x`")
        text = bootstrap.user_data(spec(blob=tricky))
        line = [ln for ln in text.splitlines() if "printf" in ln][0]
        argv = shlex.split(line.split(">")[0])
        self.assertEqual(json.loads(argv[-1]), tricky)

    def test_container_env_and_ephemeral_command(self):
        env = bootstrap.container_env(spec())
        self.assertEqual(json.loads(env["HP_CONFIG_BLOB"]), BLOB)
        self.assertEqual(env["HP_VERSION"], "3.13.2")
        cmds = bootstrap.ephemeral_command(spec(), drain_jobs=3,
                                           drain_seconds=600)
        self.assertEqual(cmds[0][-1], "pigeon-home-runner==3.13.2")
        self.assertEqual(cmds[2], ["homing-pigeon", "--once", "--drain", "3",
                                   "--drain-seconds", "600"])


class GitHubActionsTest(unittest.TestCase):
    def _gh(self, script):
        http = Player("github_actions", script)
        return github_actions.GitHubActions(http, "ghp_token", "pigeon-home",
                                            "hosted-runners"), http

    def test_dispatch_sends_the_inputs_and_not_the_blob(self):
        gh, http = self._gh(["dispatch-ok"])
        d = gh.dispatch("macos-ephemeral", "alice", "v3.13.2",
                        blob_ref="QUEUE_URL_ALICE", drain_jobs=2,
                        drain_seconds=600, ticket="t1c2k3e4t5a6")
        self.assertEqual(d.status, "requested")
        body = http.calls[0]["body"]
        self.assertEqual(body["ref"], "main")
        self.assertEqual(body["inputs"]["runs_on"], "macos-latest")
        self.assertEqual(body["inputs"]["version"], "3.13.2")
        self.assertEqual(body["inputs"]["drain_jobs"], "2")
        self.assertEqual(body["inputs"]["blob_ref"], "QUEUE_URL_ALICE")
        self.assertNotIn("shared_secret", json.dumps(body))
        self.assertEqual(http.calls[0]["headers"]["X-GitHub-Api-Version"],
                         "2022-11-28")
        with self.assertRaises(ValueError):
            gh.dispatch("solaris-ephemeral", "alice", "3.13.2", "x")

    def test_find_run_matches_the_ticket_in_the_run_name(self):
        gh, http = self._gh(["list-runs-pending", "list-runs-found"])
        d = github_actions.Dispatch("t1c2k3e4t5a6", "macos-ephemeral")
        self.assertIsNone(gh.find_run(d))
        self.assertIs(gh.find_run(d), d)
        self.assertEqual(d.run_id, 40250000001)
        self.assertEqual(d.status, "queued")

    def test_wait_fills_in_billable_minutes_rounded_up(self):
        gh, http = self._gh(["list-runs-found", "get-run-in-progress",
                             "get-run-completed", "timing-macos"])
        d = github_actions.Dispatch("t1c2k3e4t5a6", "macos-ephemeral")
        sleep = NoSleep()
        gh.wait(d, timeout=600, interval=10, sleep=sleep, clock=lambda: 0.0)
        self.assertEqual(d.status, "completed")
        self.assertEqual(d.conclusion, "success")
        self.assertEqual(d.billable_ms, 272000)
        self.assertEqual(d.minutes, 5)
        self.assertEqual(sleep.calls, [10, 10])
        rec = d.to_record()
        self.assertEqual(rec["minutes"], 5)
        self.assertEqual(rec["run_id"], 40250000001)

    def test_timing_falls_back_to_run_duration(self):
        gh, http = self._gh(["timing-duration-only"])
        d = github_actions.Dispatch("t", "linux-ephemeral", run_id=40250000001)
        self.assertEqual(gh.timing(d), 61000)
        self.assertEqual(d.minutes, 2)

    def test_wait_times_out(self):
        gh, http = self._gh(["get-run-in-progress"] * 3)
        d = github_actions.Dispatch("t", "linux-ephemeral", run_id=40250000001)
        ticks = iter([0, 10, 20, 1801, 1900])
        with self.assertRaises(base.ProvisionTimeout):
            gh.wait(d, timeout=1800, interval=10, sleep=lambda s: None,
                    clock=lambda: next(ticks))

    def test_error_shapes(self):
        gh, _ = self._gh(["bad-credentials"])
        with self.assertRaises(base.AuthError):
            gh.dispatch("linux-ephemeral", "a", "3.13.2", "x")
        gh, _ = self._gh(["rate-limited"])
        with self.assertRaises(base.RateLimited) as cm:
            gh.find_run(github_actions.Dispatch("t", "linux-ephemeral"))
        self.assertIsNotNone(cm.exception.retry_after)
        gh, _ = self._gh(["workflow-missing"])
        with self.assertRaises(base.NotFound):
            gh.dispatch("linux-ephemeral", "a", "3.13.2", "x")
        gh, _ = self._gh(["unprocessable-ref"])
        with self.assertRaises(base.ProviderError) as cm:
            gh.dispatch("linux-ephemeral", "a", "3.13.2", "x")
        self.assertEqual(cm.exception.status, 422)
        self.assertIn("No ref found", str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
