"""Project Platinum, cycle 3: the hosting control plane.

Targets from the cycle-2 refreshed table
(`docs/reports/v3.13.27/coverage-gaps.md`), guards and
excepts in the hosting package:

  guard  hosting/cli.py:_provider (2) -- fly takes its app
         as a keyword; every other provider is built from
         (http, token) alone.
  guard  hosting/cli.py:cmd_redeploy (2) -- a machine that
         is not in the inventory, and a redeploy with no
         shared secret anywhere, are SystemExits naming why.
  except hosting/bootstrap.py:hosted_config_from_env (2) --
         when the package import of the installer fails, the
         script-layout import is attempted in its place.
  except hosting/inventory.py:Inventory.save (2) -- a save
         that fails mid-write removes its temp file and
         re-raises; a good save leaves the JSON.
  except hosting/httpdoor.py:UrllibHttp.request (2) -- an
         HTTP error whose body cannot be read answers with
         the status and an empty payload.
  except the providers' destroy (hetzner, digitalocean,
         fly): a machine the provider says is gone is a
         successful destroy.
  except hosting/github_actions.py:_call (2) -- a rate
         limit whose reset header is not a number retries
         after None (unknown), not a crash.

The providers' http seam is a scripted object returning
`httpdoor.Response`s; nothing leaves the machine.

Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90
"""
import argparse
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

from runner.hosting import base, bootstrap, cli, httpdoor, inventory
from runner.hosting import digitalocean, fly, github_actions, hetzner


class _Http:
    def __init__(self, response=None):
        self.response = response
        self.calls = []

    def request(self, method, url, headers=None, body=None,
                timeout=None):
        self.calls.append((method, url))
        return self.response


class ProviderShapeTest(unittest.TestCase):
    def test_fly_takes_its_app_as_a_keyword(self):
        prov = cli._provider("fly", "tok", http=_Http(), app="app1")
        self.assertIsInstance(prov, fly.FlyMachines)
        self.assertEqual(prov.app, "app1")

    def test_another_provider_is_built_from_http_and_token(self):
        prov = cli._provider("hetzner", "tok", http=_Http())
        self.assertIsInstance(prov, hetzner.HetznerCloud)

    def test_an_unknown_provider_is_a_system_exit(self):
        with self.assertRaises(SystemExit):
            cli._provider("carrier-pigeon", "tok", http=_Http())


class RedeployRefusalsTest(unittest.TestCase):
    def _args(self, td, **over):
        args = argparse.Namespace(
            machine="fly:m1", inventory=os.path.join(td, "inv.json"),
            blob=None, version=None, token_env="HP_PLATINUM_TOKEN")
        for key, value in over.items():
            setattr(args, key, value)
        return args

    def test_a_machine_not_in_the_inventory_is_refused(self):
        td = tempfile.mkdtemp(prefix="hp-plat-host-")
        try:
            with mock.patch.dict(
                    os.environ, {"HP_PLATINUM_TOKEN": "tok"}):
                with self.assertRaises(SystemExit):
                    cli.cmd_redeploy(self._args(td), http=_Http())
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_a_redeploy_without_a_secret_is_refused(self):
        td = tempfile.mkdtemp(prefix="hp-plat-host-")
        try:
            inv = inventory.Inventory(os.path.join(td, "inv.json"))
            inv.machines[inventory.Inventory.key("fly", "m1")] = {
                "tenant": "alice", "region": "iad"}
            inv.save()
            with mock.patch.dict(
                    os.environ, {"HP_PLATINUM_TOKEN": "tok"}):
                with self.assertRaises(SystemExit):
                    cli.cmd_redeploy(self._args(td), http=_Http(),
                                     new_secret=None)
        finally:
            shutil.rmtree(td, ignore_errors=True)


class BootstrapFallbackTest(unittest.TestCase):
    def test_a_failed_package_import_tries_the_script_layout(self):
        # Both import spellings are blocked (a None entry makes
        # the import raise ImportError wherever it is tried):
        # the first failure is what fires the fallback arm, and
        # the fallback's own failure is what propagates.
        from runner import ops as ops_pkg
        keys = ("runner.ops.install", "ops", "ops.install")
        saved = {k: sys.modules.get(k) for k in keys}
        saved_attr = getattr(ops_pkg, "install", None)
        if hasattr(ops_pkg, "install"):
            delattr(ops_pkg, "install")
        for key in keys:
            sys.modules[key] = None
        try:
            with self.assertRaises(ImportError):
                bootstrap.hosted_config_from_env(
                    "/nowhere/config.json",
                    {bootstrap.BLOB_ENV: "{}"}, install=None)
        finally:
            for key, value in saved.items():
                if value is not None:
                    sys.modules[key] = value
                else:
                    sys.modules.pop(key, None)
            if saved_attr is not None:
                ops_pkg.install = saved_attr

    def test_an_installer_given_is_used(self):
        fake = mock.Mock()
        got = bootstrap.hosted_config_from_env(
            "/nowhere/config.json", {bootstrap.BLOB_ENV: "{}"},
            install=fake)
        self.assertTrue(got)
        fake.merge_config_blob.assert_called_once()


class InventorySaveTest(unittest.TestCase):
    def test_a_failed_save_leaves_no_temp_and_reraises(self):
        td = tempfile.mkdtemp(prefix="hp-plat-host-")
        try:
            inv = inventory.Inventory(os.path.join(td, "inv.json"))
            with mock.patch.object(
                    os, "replace",
                    side_effect=OSError("the disk is full")):
                with self.assertRaises(OSError):
                    inv.save()
            self.assertEqual(
                [n for n in os.listdir(td)
                 if n.startswith(".inventory-")], [])
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_a_failed_save_and_a_failed_unlink_still_reraises(self):
        # Cycle 4 target, except class: `Inventory.save`
        # (57,58) -- when the cleanup unlink also fails, the
        # swallow keeps it quiet and the original error is
        # the one that propagates.
        td = tempfile.mkdtemp(prefix="hp-plat-host-")
        try:
            inv = inventory.Inventory(os.path.join(td, "inv.json"))
            with mock.patch.object(
                    os, "replace",
                    side_effect=OSError("the disk is full")), \
                    mock.patch.object(
                        os, "unlink",
                        side_effect=OSError("cannot remove it")):
                with self.assertRaises(OSError) as cm:
                    inv.save()
            self.assertIn("disk is full", str(cm.exception))
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_a_good_save_writes_the_json(self):
        td = tempfile.mkdtemp(prefix="hp-plat-host-")
        try:
            path = os.path.join(td, "inv.json")
            inv = inventory.Inventory(path)
            inv.machines["fly:m1"] = {"tenant": "alice"}
            inv.save()
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["machines"],
                                 {"fly:m1": {"tenant": "alice"}})
        finally:
            shutil.rmtree(td, ignore_errors=True)


class HttpDoorTest(unittest.TestCase):
    def test_an_unreadable_error_body_answers_empty(self):
        err = urllib.error.HTTPError(
            "https://example.test", 502, "scripted", {},
            io.BytesIO(b""))

        def boom():
            raise OSError("the error body is unreadable")
        err.read = boom
        with mock.patch.object(urllib.request, "urlopen",
                               side_effect=err):
            resp = httpdoor.UrllibHttp().request(
                "GET", "https://example.test")
        self.assertEqual(resp.status, 502)
        self.assertEqual(resp.body, b"")


class DestroyGoneTest(unittest.TestCase):
    def test_destroying_a_gone_machine_is_a_success(self):
        for prov in (hetzner.HetznerCloud(_Http(), "tok"),
                     digitalocean.DigitalOcean(_Http(), "tok"),
                     fly.FlyMachines(_Http(), "tok", app="a")):
            with mock.patch.object(
                    prov, "_call",
                    side_effect=base.NotFound("gone")):
                self.assertIsNone(prov.destroy("m1"))


class GitHubRateLimitTest(unittest.TestCase):
    def _gh(self, reset):
        resp = httpdoor.Response(
            403, {"x-ratelimit-remaining": "0",
                  "x-ratelimit-reset": reset},
            b'{"message": "rate limited"}')
        return github_actions.GitHubActions(
            _Http(resp), "tok", "owner", "repo")

    def test_a_non_numeric_reset_retries_after_unknown(self):
        with self.assertRaises(base.RateLimited) as cm:
            self._gh("soon")._call("GET", "/x", what="probe")
        self.assertIsNone(cm.exception.retry_after)

    def test_a_numeric_reset_retries_after_a_delay(self):
        with self.assertRaises(base.RateLimited) as cm:
            self._gh("9999999999")._call("GET", "/x", what="probe")
        self.assertIsInstance(cm.exception.retry_after, float)
        self.assertGreater(cm.exception.retry_after, 0)


class StripeSignatureTest(unittest.TestCase):
    """Cycle 5 target, logic class:
    `hosting/billing.py:verify_stripe_signature` (181) --
    the payload may arrive as text: it is encoded before
    the HMAC is compared, so a correctly signed text
    payload verifies exactly as its bytes do.
    """

    def test_a_text_payload_verifies(self):
        import hashlib
        import hmac as hmac_mod
        from runner.hosting import billing
        secret = "whsec_platinum"
        ts = 1700000000
        payload = '{"id": "evt_1", "type": "invoice.paid"}'
        sig = hmac_mod.new(
            secret.encode(), f"{ts}.{payload}".encode(),
            hashlib.sha256).hexdigest()
        header = f"t={ts},v1={sig}"
        self.assertTrue(billing.verify_stripe_signature(
            payload, header, secret, now=ts))
        self.assertTrue(billing.verify_stripe_signature(
            payload.encode(), header, secret, now=ts))
        with self.assertRaises(billing.SignatureError):
            billing.verify_stripe_signature(
                payload + " ", header, secret, now=ts)


class CmdStatusDispatchesTest(unittest.TestCase):
    """Cycle 5 target, logic class: `hosting/cli.py:
    cmd_status` (129) -- with ephemeral dispatches on the
    inventory, status says how many, after the machines.
    """

    def test_status_counts_the_dispatches(self):
        import contextlib
        import io
        td = tempfile.mkdtemp(prefix="hp-plat-host-")
        try:
            inv = inventory.Inventory(os.path.join(td, "inv.json"))
            inv.machines[inventory.Inventory.key("fly", "m1")] = {
                "provider": "fly", "id": "m1", "tenant": "alice"}
            inv.dispatches = [{"id": "d1"}, {"id": "d2"}]
            inv.save()
            args = argparse.Namespace(
                inventory=os.path.join(td, "inv.json"))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.cmd_status(args, http=_Http())
            self.assertEqual(rc, 0)
            self.assertIn("2 ephemeral dispatch(es)", out.getvalue())
        finally:
            shutil.rmtree(td, ignore_errors=True)


class ProviderBaseTest(unittest.TestCase):
    """Cycle 5 targets, guard class, `hosting/base.py`: a
    Machine's repr (87) names provider:id, state and ip; the
    abstract Provider's create/get/destroy (98,101,104) are
    NotImplementedError; and the shared wait_running (118)
    raises the gone ProviderError for a machine that
    vanished while starting.
    """

    def test_a_machine_reprs_as_provider_id_state_ip(self):
        m = base.Machine("fly", "m1", tenant="alice",
                         state="running", ip="1.2.3.4")
        self.assertEqual(repr(m), "Machine(fly:m1 running 1.2.3.4)")

    def test_the_abstract_provider_refuses_each_verb(self):
        prov = base.Provider()
        spec = base.MachineSpec("alice", "iad", "small", "1.0",
                                blob={})
        with self.assertRaises(NotImplementedError):
            prov.create(spec)
        with self.assertRaises(NotImplementedError):
            prov.get("m1")
        with self.assertRaises(NotImplementedError):
            prov.destroy("m1")

    def test_wait_running_names_a_vanished_machine(self):
        class Gone(base.Provider):
            def get(self, machine_id):
                return base.Machine("gone", machine_id, state="gone")
        with self.assertRaises(base.ProviderError) as cm:
            Gone().wait_running("m1", timeout=1, interval=0)
        self.assertEqual(cm.exception.code, "gone")


class BillingGuardsTest(unittest.TestCase):
    """Cycle 5 targets, guard class, `hosting/billing.py`:
    reserve_for (52) refuses an unknown target; the balance
    (116) skips an event whose cents are not an int; a
    refund (138) whose Stripe event was already seen is a
    no-op returning None.
    """

    def test_reserve_for_an_unknown_target_raises(self):
        from runner.hosting import billing
        with self.assertRaises(ValueError):
            billing.reserve_for("carrier-pigeon")

    def test_balance_skips_a_non_int_cents_event(self):
        td = tempfile.mkdtemp(prefix="hp-plat-host-")
        try:
            from runner.hosting import billing
            ledger = billing.Ledger(os.path.join(td, "l.json"))
            ledger.topup("alice", 500, stripe_event="e1")
            ledger.events.append(
                {"tenant": "alice", "cents": "50", "kind": "topup"})
            self.assertEqual(ledger.balance("alice"), 500)
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_a_refund_with_a_seen_event_is_a_no_op(self):
        td = tempfile.mkdtemp(prefix="hp-plat-host-")
        try:
            from runner.hosting import billing
            ledger = billing.Ledger(os.path.join(td, "l.json"))
            ledger.topup("alice", 500, stripe_event="e1")
            self.assertIsNone(
                ledger.refund("alice", 100, stripe_event="e1"))
            self.assertEqual(ledger.balance("alice"), 500)
        finally:
            shutil.rmtree(td, ignore_errors=True)


class CliGuardsTest(unittest.TestCase):
    """Cycle 5 targets, guard class, `hosting/cli.py`:
    _split_key (79) refuses a key without provider and id;
    cmd_dispatch (201) refuses a repo that is not
    owner/name; main (316) with no subcommand returns 2.
    """

    def test_split_key_refusals(self):
        for bad in ("nocolon", ":m1", "fly:", ""):
            with self.assertRaises(SystemExit):
                cli._split_key(bad)
        self.assertEqual(cli._split_key("fly:m1"), ("fly", "m1"))

    def test_dispatch_without_an_owner_repo_is_refused(self):
        args = argparse.Namespace(
            repo="justaname", token_env="HP_PLATINUM_TOKEN",
            workflow="w.yml", ref="main", target=None,
            tenant=None, version=None, blob=None, drain=1,
            drain_seconds=1, inventory=None)
        with mock.patch.dict(os.environ,
                             {"HP_PLATINUM_TOKEN": "tok"}):
            with self.assertRaises(SystemExit):
                cli.cmd_dispatch(args, http=_Http())

    def test_main_without_a_subcommand_is_an_argparse_refusal(self):
        # The parser requires a subcommand, so main's trailing
        # return 2 (cli.py:316) sits behind an exhaustive
        # dispatch: argparse refuses first, with its own 2.
        # Recorded in cycle 5's ledger as unreachable by
        # construction.
        with self.assertRaises(SystemExit) as cm:
            cli.main([])
        self.assertEqual(cm.exception.code, 2)


class ProviderRecordGuardsTest(unittest.TestCase):
    """Cycle 5 targets, guard class: each provider's record
    reader refuses a record that is not an object --
    DigitalOcean._machine (43), FlyMachines._machine (64),
    HetznerCloud._machine (46) -- with its own ProviderError;
    HttpClient.request (httpdoor 53) is the interface's
    NotImplementedError; and FlyMachines.ensure_app
    answers False for 422-already-exists and True for an ok
    POST. (Its trailing return False at line 57 sits under
    base.raise_for, whose tail raises for every answer
    that reaches it: unreachable by construction, recorded
    in cycle 5's ledger.)
    """

    def test_malformed_records_are_refused_per_provider(self):
        http = _Http()
        providers = [
            digitalocean.DigitalOcean(http, "tok", "sfo3"),
            fly.FlyMachines(http, "tok", "org"),
            hetzner.HetznerCloud(http, "tok", "nbg1"),
        ]
        for prov in providers:
            with self.assertRaises(base.ProviderError):
                prov._machine("not a record")

    def test_the_http_interface_refuses_to_run(self):
        with self.assertRaises(NotImplementedError):
            httpdoor.HttpClient().request("GET", "http://x/")

    def test_ensure_app_answers(self):
        http2 = _Http(httpdoor.Response(
            422, {}, b'{"error": "app already exists"}'))
        self.assertFalse(
            fly.FlyMachines(http2, "tok", "org").ensure_app("hp-alice"))
        http3 = _Http(httpdoor.Response(200, {}, b'{}'))
        self.assertTrue(
            fly.FlyMachines(http3, "tok", "org").ensure_app("hp-alice"))


class GitHubActionsGuardsTest(unittest.TestCase):
    """Cycle 5 targets, guard class, `hosting/
    github_actions.py`: Dispatch.minutes (60) is None
    until a billable time exists; find_run (135) steps
    over run entries that are not objects; timing (159)
    answers None for a dispatch with no run yet.
    """

    def test_minutes_is_none_without_a_billable_time(self):
        d = github_actions.Dispatch("t1", "linux")
        self.assertIsNone(d.minutes)
        d.billable_ms = 61_000
        self.assertEqual(d.minutes, 2)

    def test_find_run_steps_over_junk_entries(self):
        http = _Http(httpdoor.Response(
            200, {}, b'{"workflow_runs": ["junk", '
            b'{"display_title": "hp t1", "id": 7}]}'))
        gh = github_actions.GitHubActions(
            http, "tok", "owner", "repo")
        d = github_actions.Dispatch("t1", "linux")
        gh.find_run(d)
        self.assertEqual(d.run_id, 7)

    def test_timing_without_a_run_is_none(self):
        gh = github_actions.GitHubActions(
            _Http(), "tok", "owner", "repo")
        d = github_actions.Dispatch("t1", "linux")
        self.assertIsNone(gh.timing(d))


if __name__ == "__main__":
    unittest.main()
