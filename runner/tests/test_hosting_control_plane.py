#!/usr/bin/env python3
# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""The control plane around the adapters: the inventory and its
isolation rule, the prepaid ledger and the Stripe webhook, and the
`homing-pigeon-host` CLI driven end to end against recorded exchanges
(docs/project/hosting.md, Phases 1 and 4). No live calls.
"""
import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import types
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.hosting import base, billing, cli, inventory  # noqa: E402
from runner.hosting import github_actions  # noqa: E402
from runner.tests.hosting_player import Player  # noqa: E402


def machine(provider="fly", mid="m1", tenant=None, state="created"):
    return base.Machine(provider, mid, name=f"hp-{tenant or 'x'}",
                        region="iad", state=state, tenant=tenant,
                        version="3.13.2")


class InventoryTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.td.name, "sub", "hosting.json")

    def tearDown(self):
        self.td.cleanup()

    def test_place_save_reload(self):
        inv = inventory.Inventory(self.path)
        rec = inv.place(machine(tenant="alice"), "alice")
        self.assertEqual(rec["tenant"], "alice")
        inv.save()
        self.assertEqual(oct(os.stat(self.path).st_mode & 0o777), "0o600")
        again = inventory.Inventory(self.path)
        self.assertEqual(again.machines["fly:m1"]["tenant"], "alice")
        self.assertEqual(again.resident_for("alice")[0]["id"], "m1")

    def test_one_resident_per_tenant_per_provider(self):
        inv = inventory.Inventory(self.path)
        inv.place(machine(mid="m1"), "alice")
        with self.assertRaises(inventory.IsolationError):
            inv.place(machine(mid="m2"), "alice")
        # Another provider is fine; a gone machine frees the slot.
        inv.place(machine(provider="hetzner", mid="7"), "alice")
        inv.update(machine(mid="m1", state="gone"))
        inv.place(machine(mid="m3"), "alice")

    def test_a_machine_never_changes_tenant(self):
        inv = inventory.Inventory(self.path)
        inv.place(machine(mid="m1"), "alice")
        with self.assertRaises(inventory.IsolationError):
            inv.place(machine(mid="m1"), "bob")
        # Re-placing for the same tenant refreshes, keeps placed_at.
        first = inv.machines["fly:m1"]["placed_at"]
        inv.place(machine(mid="m1", state="running"), "alice")
        self.assertEqual(inv.machines["fly:m1"]["placed_at"], first)
        self.assertEqual(inv.machines["fly:m1"]["state"], "running")

    def test_update_and_forget(self):
        inv = inventory.Inventory(self.path)
        self.assertIsNone(inv.update(machine(mid="zz")))
        inv.place(machine(mid="m1"), "alice")
        m = machine(mid="m1", state="running")
        m.ip = "203.0.113.9"
        inv.update(m)
        self.assertEqual(inv.machines["fly:m1"]["ip"], "203.0.113.9")
        self.assertIsNotNone(inv.forget("fly", "m1"))
        self.assertIsNone(inv.forget("fly", "m1"))

    def test_corrupt_file_reads_as_empty(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        inv = inventory.Inventory(self.path)
        self.assertEqual(inv.machines, {})

    def test_dispatches_are_recorded(self):
        inv = inventory.Inventory(self.path)
        d = github_actions.Dispatch("t1", "macos-ephemeral", run_id=5,
                                    status="completed", conclusion="success",
                                    billable_ms=61000)
        rec = inv.record_dispatch(d, "alice")
        self.assertEqual(rec["minutes"], 2)
        inv.save()
        self.assertEqual(inventory.Inventory(self.path).dispatches[0]["tenant"],
                         "alice")


class PriceTableTest(unittest.TestCase):
    def test_ratios_follow_the_platforms(self):
        self.assertEqual(billing.price_for("linux-ephemeral", 10), 10)
        self.assertEqual(billing.price_for("windows-ephemeral", 10), 20)
        self.assertEqual(billing.price_for("macos-ephemeral", 10), 100)
        self.assertEqual(billing.price_for("linux-resident", 1), 500)
        with self.assertRaises(ValueError):
            billing.price_for("solaris", 1)
        with self.assertRaises(ValueError):
            billing.price_for("linux-ephemeral", -1)

    def test_reserve_is_the_drain_window_at_the_rate(self):
        self.assertEqual(billing.reserve_for("macos-ephemeral"), 150)
        self.assertEqual(billing.reserve_for("windows-ephemeral", minutes=10), 20)
        self.assertEqual(billing.reserve_for("linux-resident"), 500)


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.td.name, "ledger.json")

    def tearDown(self):
        self.td.cleanup()

    def test_balance_is_rebuilt_from_events(self):
        led = billing.Ledger(self.path)
        led.topup("alice", 2000, stripe_event="evt_1")
        led.usage("alice", "macos-ephemeral", 5, job_id="j1")
        led.usage("alice", "windows-ephemeral", 3, job_id="j2")
        led.refund("alice", 100, stripe_event="evt_2")
        self.assertEqual(led.balance("alice"), 2000 - 50 - 6 - 100)
        self.assertEqual(led.balance("bob"), 0)
        led.save()
        again = billing.Ledger(self.path)
        self.assertEqual(again.balance("alice"), 1844)
        st = again.statement("alice")
        self.assertEqual(st["balance_cents"], 1844)
        self.assertEqual(len(st["events"]), 4)

    def test_stripe_events_apply_once(self):
        led = billing.Ledger(self.path)
        self.assertIsNotNone(led.topup("alice", 500, stripe_event="evt_x"))
        self.assertIsNone(led.topup("alice", 500, stripe_event="evt_x"))
        self.assertEqual(led.balance("alice"), 500)
        with self.assertRaises(ValueError):
            led.topup("alice", 0)
        with self.assertRaises(ValueError):
            led.refund("alice", -5)

    def test_can_cover_checks_reserve_and_freeze(self):
        led = billing.Ledger(self.path)
        ok, why = led.can_cover("alice", "macos-ephemeral")
        self.assertFalse(ok)
        self.assertIn("reserve", why)
        led.topup("alice", 150)
        self.assertTrue(led.can_cover("alice", "macos-ephemeral")[0])
        self.assertTrue(led.can_cover("alice", "linux-ephemeral")[0])
        self.assertFalse(led.can_cover("alice", "linux-resident")[0])
        led.freeze("alice", "dispute")
        ok, why = led.can_cover("alice", "linux-ephemeral")
        self.assertFalse(ok)
        self.assertIn("frozen", why)
        led.save()
        self.assertIn("alice", billing.Ledger(self.path).frozen)


def _signed(payload, secret, ts=None):
    ts = int(time.time()) if ts is None else ts
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body,
                   hashlib.sha256).hexdigest()
    return body, f"t={ts},v1={sig}"


# Recorded Stripe event shapes (2024-06-20 API), trimmed to the
# fields the handler reads; metadata.tenant is set at Checkout
# creation by our side.
CHECKOUT_PAID = {
    "id": "evt_1QAbCdEfGhIjKlMn", "object": "event",
    "type": "checkout.session.completed",
    "data": {"object": {"id": "cs_test_a1", "object": "checkout.session",
                        "amount_total": 2500, "currency": "usd",
                        "payment_status": "paid",
                        "metadata": {"tenant": "alice"}}}}
REFUND = {
    "id": "evt_2QAbCdEfGhIjKlMn", "object": "event", "type": "charge.refunded",
    "data": {"object": {"id": "ch_1", "object": "charge",
                        "amount_refunded": 500,
                        "metadata": {"tenant": "alice"}}}}
DISPUTE = {
    "id": "evt_3QAbCdEfGhIjKlMn", "object": "event",
    "type": "charge.dispute.created",
    "data": {"object": {"id": "du_1", "object": "dispute", "amount": 2500,
                        "charge": "ch_1", "metadata": {"tenant": "alice"}}}}


class StripeWebhookTest(unittest.TestCase):
    SECRET = "whsec_test_0123456789abcdef"

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.led = billing.Ledger(os.path.join(self.td.name, "ledger.json"))

    def tearDown(self):
        self.td.cleanup()

    def test_signature_verification(self):
        body, header = _signed(CHECKOUT_PAID, self.SECRET, ts=1_000_000)
        self.assertTrue(billing.verify_stripe_signature(
            body, header, self.SECRET, now=1_000_100))
        with self.assertRaises(billing.SignatureError):
            billing.verify_stripe_signature(body, header, "whsec_other",
                                            now=1_000_100)
        with self.assertRaises(billing.SignatureError):
            billing.verify_stripe_signature(body, header, self.SECRET,
                                            now=1_000_000 + 301)
        with self.assertRaises(billing.SignatureError):
            billing.verify_stripe_signature(body + b" ", header, self.SECRET,
                                            now=1_000_100)
        for bad in (None, "", "t=abc,v1=00", "v1=00", "t=1000000"):
            with self.subTest(bad=bad):
                with self.assertRaises(billing.SignatureError):
                    billing.verify_stripe_signature(body, bad, self.SECRET,
                                                    now=1_000_100)

    def test_topup_refund_dispute_and_replay(self):
        now = 1_000_000
        body, header = _signed(CHECKOUT_PAID, self.SECRET, ts=now)
        out = billing.handle_stripe_event(self.led, body, header, self.SECRET,
                                          now=now)
        self.assertEqual(out["kind"], "topup")
        self.assertTrue(out["applied"])
        self.assertEqual(self.led.balance("alice"), 2500)
        out = billing.handle_stripe_event(self.led, body, header, self.SECRET,
                                          now=now)
        self.assertFalse(out["applied"])
        self.assertEqual(out["why"], "duplicate")
        body, header = _signed(REFUND, self.SECRET, ts=now)
        out = billing.handle_stripe_event(self.led, body, header, self.SECRET,
                                          now=now)
        self.assertEqual(out["kind"], "refund")
        self.assertEqual(self.led.balance("alice"), 2000)
        body, header = _signed(DISPUTE, self.SECRET, ts=now)
        out = billing.handle_stripe_event(self.led, body, header, self.SECRET,
                                          now=now)
        self.assertEqual(out["kind"], "freeze")
        self.assertFalse(self.led.can_cover("alice", "linux-ephemeral")[0])

    def test_unknown_unpaid_and_tenantless_events_do_nothing(self):
        now = 1_000_000
        for payload, why in (
                (dict(CHECKOUT_PAID, type="invoice.paid"), "ignored"),
                ({"id": "e", "type": "checkout.session.completed",
                  "data": {"object": {"amount_total": 100,
                                      "payment_status": "unpaid",
                                      "metadata": {"tenant": "alice"}}}},
                 "not paid"),
                ({"id": "e2", "type": "checkout.session.completed",
                  "data": {"object": {"amount_total": 100,
                                      "payment_status": "paid",
                                      "metadata": {}}}}, "no tenant"),
                ({"id": "e3", "type": "payment_intent.succeeded",
                  "data": {"object": {"amount_received": 0,
                                      "metadata": {"tenant": "alice"}}}},
                 "positive amount")):
            with self.subTest(why=why):
                body, header = _signed(payload, self.SECRET, ts=now)
                out = billing.handle_stripe_event(self.led, body, header,
                                                  self.SECRET, now=now)
                self.assertFalse(out["applied"])
                self.assertIn(why, out["why"])
        self.assertEqual(self.led.balance("alice"), 0)


class CliTest(unittest.TestCase):
    """The CLI against recorded exchanges: token from the environment,
    blob from a file, inventory enforced, output JSON."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.inv = os.path.join(self.td.name, "hosting.json")
        self.blob = os.path.join(self.td.name, "blob.json")
        with open(self.blob, "w", encoding="utf-8") as fh:
            json.dump({"shared_secret": "b" * 64, "runner_id": "alice-1",
                       "workspace_root": "/srv/hp/work"}, fh)
        os.environ["HP_TEST_FLY"] = "fo1_token"

    def tearDown(self):
        os.environ.pop("HP_TEST_FLY", None)
        self.td.cleanup()

    def _args(self, **kw):
        base_args = {"inventory": self.inv, "token_env": "HP_TEST_FLY",
                     "provider": "fly", "tenant": "alice", "region": "iad",
                     "version": "3.13.2", "blob": "@" + self.blob,
                     "size": None, "image": None, "profile": "hosted",
                     "wait": 60, "no_wait": False}
        base_args.update(kw)
        return types.SimpleNamespace(**base_args)

    def test_up_provisions_waits_and_records(self):
        http = Player("fly", ["create-app-ok", "create-machine-ok",
                              "get-machine-starting", "get-machine-started"])
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.cmd_up(self._args(), http=http, sleep=lambda s: None)
        self.assertEqual(rc, 0)
        self.assertTrue(http.exhausted())
        shown = json.loads(out.getvalue().split("\n{", 1)[-1].join(["{", ""])
                           if not out.getvalue().startswith("{")
                           else out.getvalue())
        self.assertEqual(shown["machine"], "fly:e784079b561e58")
        self.assertEqual(shown["state"], "running")
        self.assertEqual(shown["shared_secret"], "b" * 64)
        inv = inventory.Inventory(self.inv)
        self.assertEqual(inv.machines["fly:e784079b561e58"]["tenant"], "alice")
        self.assertEqual(inv.machines["fly:e784079b561e58"]["state"], "running")

    def test_up_refuses_a_second_resident_for_the_tenant(self):
        inv = inventory.Inventory(self.inv)
        inv.place(machine(mid="old", tenant="alice"), "alice")
        inv.save()
        with self.assertRaises(SystemExit) as cm:
            cli.cmd_up(self._args(), http=Player("fly", []))
        self.assertIn("already has a resident machine", str(cm.exception))

    def test_token_must_come_from_the_environment(self):
        with self.assertRaises(SystemExit):
            cli.cmd_up(self._args(token_env="HP_UNSET_TOKEN_XYZ"),
                       http=Player("fly", []))
        with self.assertRaises(SystemExit):
            cli.cmd_up(self._args(token_env=None), http=Player("fly", []))

    def test_up_generates_a_secret_when_the_blob_has_none(self):
        with open(self.blob, "w", encoding="utf-8") as fh:
            json.dump({"runner_id": "alice-1"}, fh)
        http = Player("fly", ["create-app-ok", "create-machine-ok"])
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.cmd_up(self._args(no_wait=True), http=http)
        self.assertEqual(rc, 0)
        sent = json.loads(http.calls[1]["body"]["config"]["env"]["HP_CONFIG_BLOB"])
        self.assertEqual(len(sent["shared_secret"]), 64)
        self.assertIn(sent["shared_secret"], out.getvalue())

    def test_redeploy_replaces_then_destroys_the_old_machine(self):
        inv = inventory.Inventory(self.inv)
        old = machine(mid="old1", tenant="alice", state="running")
        inv.place(old, "alice")
        inv.save()
        http = Player("fly", ["create-app-exists", "create-machine-ok",
                              "get-machine-started", "destroy-old-ok"])
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            rc = cli.cmd_redeploy(
                types.SimpleNamespace(inventory=self.inv, token_env="HP_TEST_FLY",
                                      machine="fly:old1", version="3.13.3",
                                      blob="@" + self.blob, size=None,
                                      image=None, profile="hosted", wait=60),
                http=http, sleep=lambda s: None)
        self.assertEqual(rc, 0)
        self.assertTrue(http.exhausted())
        self.assertEqual(http.calls[1]["body"]["config"]["image"],
                         "ghcr.io/pigeon-home/homing-pigeon:3.13.3")
        self.assertTrue(http.calls[-1]["url"].endswith("/machines/old1?force=true"))
        inv = inventory.Inventory(self.inv)
        self.assertNotIn("fly:old1", inv.machines)
        self.assertEqual(inv.machines["fly:e784079b561e58"]["tenant"], "alice")

    def test_rotate_prints_the_new_secret_once_and_ships_it(self):
        inv = inventory.Inventory(self.inv)
        inv.place(machine(mid="old1", tenant="alice", state="running"), "alice")
        inv.save()
        http = Player("fly", ["create-app-exists", "create-machine-ok",
                              "get-machine-started", "destroy-old-ok"])
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.cmd_rotate(
                types.SimpleNamespace(inventory=self.inv, token_env="HP_TEST_FLY",
                                      machine="fly:old1", version=None,
                                      blob="@" + self.blob, size=None,
                                      image=None, profile="hosted", wait=60),
                http=http, sleep=lambda s: None)
        self.assertEqual(rc, 0)
        shipped = json.loads(http.calls[1]["body"]["config"]["env"]["HP_CONFIG_BLOB"])
        self.assertNotEqual(shipped["shared_secret"], "b" * 64)
        self.assertIn(shipped["shared_secret"], out.getvalue())
        self.assertNotIn(shipped["shared_secret"],
                         json.dumps(inventory.Inventory(self.inv).machines))

    def test_destroy_forgets(self):
        inv = inventory.Inventory(self.inv)
        inv.place(machine(mid="e784079b561e58", tenant="alice"), "alice")
        inv.save()
        http = Player("fly", ["destroy-ok"])
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            rc = cli.cmd_destroy(types.SimpleNamespace(
                inventory=self.inv, token_env="HP_TEST_FLY",
                machine="fly:e784079b561e58"), http=http)
        self.assertEqual(rc, 0)
        self.assertEqual(inventory.Inventory(self.inv).machines, {})

    def test_dispatch_records_minutes(self):
        os.environ["HP_TEST_GH"] = "ghp_x"
        try:
            http = Player("github_actions", ["dispatch-ok", "list-runs-found",
                                             "get-run-completed",
                                             "timing-macos"])
            import io
            from contextlib import redirect_stdout
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli.cmd_dispatch(types.SimpleNamespace(
                    inventory=self.inv, token_env="HP_TEST_GH",
                    target="macos-ephemeral", tenant="alice",
                    version="3.13.2", repo="pigeon-home/hosted-runners",
                    workflow="hp-ephemeral.yml", ref="main",
                    blob_ref="QUEUE_URL_ALICE", drain=1, drain_seconds=900,
                    ticket="t1c2k3e4t5a6", wait=600, no_wait=False),
                    http=http, sleep=lambda s: None)
        finally:
            del os.environ["HP_TEST_GH"]
        self.assertEqual(rc, 0)
        self.assertTrue(http.exhausted())
        sent = http.calls[0]["body"]["inputs"]
        self.assertEqual(sent["runs_on"], "macos-latest")
        self.assertEqual(sent["ticket"], "t1c2k3e4t5a6")
        inv = inventory.Inventory(self.inv)
        self.assertEqual(len(inv.dispatches), 1)
        self.assertEqual(inv.dispatches[0]["target"], "macos-ephemeral")
        self.assertEqual(inv.dispatches[0]["minutes"], 5)
        self.assertEqual(inv.dispatches[0]["conclusion"], "success")

    def test_main_maps_errors_to_exit_codes(self):
        http = Player("fly", ["unauthorized"])
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from unittest import mock
        err = io.StringIO()
        with mock.patch.object(cli, "UrllibHttp", lambda: http), \
                redirect_stdout(io.StringIO()), redirect_stderr(err):
            rc = cli.main(["--inventory", self.inv, "up", "--provider", "fly",
                           "--tenant", "alice", "--region", "iad",
                           "--version", "3.13.2", "--blob", "@" + self.blob,
                           "--token-env", "HP_TEST_FLY"])
        self.assertEqual(rc, 3)
        self.assertIn("auth", err.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["--inventory", self.inv, "status"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
