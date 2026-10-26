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


if __name__ == "__main__":
    unittest.main()
