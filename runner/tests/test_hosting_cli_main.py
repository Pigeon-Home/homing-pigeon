"""homing-pigeon-host through main(): every subcommand and every exit code.

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854

The control-plane tests drive cmd_up and its siblings directly, so
main()'s dispatch and four of its five error mappings had never run
(coverage, 2026-10-25: 21 of 31 lines). These go in through argv the
way an operator does, against the recorded exchanges, and pin the
exit code each failure class maps to: 2 a bad blob, 3 auth, 4 rate
limited, 5 the provider, 6 the inventory's isolation rule.
"""
import io
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.hosting import base, cli, inventory  # noqa: E402
from runner.tests.hosting_player import Player  # noqa: E402


def _machine(mid, tenant, provider="fly"):
    return base.Machine(provider, mid, name=f"hp-{tenant}", region="iad",
                        state="running", tenant=tenant, version="3.13.2")


class MainTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.inv = os.path.join(self.td.name, "hosting.json")
        self.blob = os.path.join(self.td.name, "blob.json")
        with open(self.blob, "w", encoding="utf-8") as fh:
            json.dump({"shared_secret": "b" * 64, "runner_id": "alice-1",
                       "workspace_root": "/srv/hp/work"}, fh)
        os.environ["HP_TEST_FLY"] = "fo1_token"
        os.environ["HP_TEST_GH"] = "ghp_x"

    def tearDown(self):
        os.environ.pop("HP_TEST_FLY", None)
        os.environ.pop("HP_TEST_GH", None)
        self.td.cleanup()

    def _run(self, player, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(cli, "UrllibHttp", lambda: player), \
                redirect_stdout(out), redirect_stderr(err):
            rc = cli.main(["--inventory", self.inv] + list(argv))
        return rc, out.getvalue(), err.getvalue()

    def _place(self, mid, tenant):
        inv = inventory.Inventory(self.inv)
        inv.place(_machine(mid, tenant), tenant)
        inv.save()

    # -- the subcommands, through argv --------------------------------

    def test_up_then_status(self):
        rc, out, _ = self._run(
            Player("fly", ["create-app-ok", "create-machine-ok",
                           "get-machine-started"]),
            "up", "--provider", "fly", "--tenant", "alice", "--region", "iad",
            "--version", "3.13.2", "--blob", "@" + self.blob,
            "--token-env", "HP_TEST_FLY")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["tenant"], "alice")
        rc, out, _ = self._run(Player("fly", []), "status")
        self.assertEqual(rc, 0)
        self.assertIn("e784079b561e58", out)

    def test_destroy(self):
        self._place("e784079b561e58", "alice")
        rc, out, _ = self._run(Player("fly", ["destroy-ok"]),
                               "destroy", "fly:e784079b561e58",
                               "--token-env", "HP_TEST_FLY")
        self.assertEqual(rc, 0)
        self.assertIn("destroyed fly:e784079b561e58", out)
        self.assertEqual(inventory.Inventory(self.inv).machines, {})

    def test_redeploy(self):
        self._place("old1", "alice")
        rc, out, _ = self._run(
            Player("fly", ["create-app-exists", "create-machine-ok",
                           "get-machine-started", "destroy-old-ok"]),
            "redeploy", "fly:old1", "--version", "3.13.3",
            "--blob", "@" + self.blob, "--token-env", "HP_TEST_FLY")
        self.assertEqual(rc, 0, out)
        self.assertEqual(json.loads(out)["replaced"], "fly:old1")

    def test_rotate_prints_the_secret_once(self):
        self._place("old1", "alice")
        rc, out, _ = self._run(
            Player("fly", ["create-app-exists", "create-machine-ok",
                           "get-machine-started", "destroy-old-ok"]),
            "rotate", "fly:old1", "--token-env", "HP_TEST_FLY")
        self.assertEqual(rc, 0, out)
        self.assertIn("new_shared_secret", out)
        self.assertNotIn("new_shared_secret", open(self.inv).read())

    def test_dispatch(self):
        rc, out, _ = self._run(
            Player("github_actions", ["dispatch-ok", "list-runs-found",
                                      "get-run-completed", "timing-macos"]),
            "dispatch", "--target", "macos-ephemeral", "--tenant", "alice",
            "--version", "3.13.2", "--repo", "pigeon-home/hosted-runners",
            "--blob-ref", "QUEUE_URL_ALICE", "--ticket", "t1c2k3e4t5a6",
            "--token-env", "HP_TEST_GH")
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(inventory.Inventory(self.inv).dispatches), 1)

    # -- the exit codes --------------------------------------------------

    def _up(self, player, blob=None):
        return self._run(player, "up", "--provider", "fly", "--tenant",
                         "alice", "--region", "iad", "--version", "3.13.2",
                         "--blob", blob or "@" + self.blob,
                         "--token-env", "HP_TEST_FLY")

    def test_auth_is_3(self):
        rc, _, err = self._up(Player("fly", ["unauthorized"]))
        self.assertEqual((rc, "auth:" in err), (3, True))

    def test_rate_limited_is_4(self):
        rc, _, err = self._up(Player("fly", ["create-app-ok", "rate-limited"]))
        self.assertEqual(rc, 4)
        self.assertIn("rate limited", err)
        self.assertIn("retry after", err)

    def test_provider_error_is_5(self):
        rc, _, err = self._up(Player("fly", ["create-app-ok", "server-error"]))
        self.assertEqual((rc, "provider:" in err), (5, True))

    def test_isolation_error_is_6(self):
        # The replacement the provider hands back is a machine the
        # inventory already holds for another tenant.
        self._place("old1", "alice")
        self._place("e784079b561e58", "bob")
        rc, _, err = self._run(
            Player("fly", ["create-app-exists", "create-machine-ok"]),
            "redeploy", "fly:old1", "--blob", "@" + self.blob,
            "--token-env", "HP_TEST_FLY")
        self.assertEqual(rc, 6)
        self.assertIn("isolation:", err)
        self.assertIn("bob", err)

    def test_bad_blob_is_2(self):
        bad = os.path.join(self.td.name, "bad.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        rc, _, err = self._up(Player("fly", []), blob="@" + bad)
        self.assertEqual(rc, 2)
        self.assertIn("config blob", err)

    def test_missing_token_variable_exits_with_a_message(self):
        with self.assertRaises(SystemExit) as cm:
            self._run(Player("fly", []), "up", "--provider", "fly",
                      "--tenant", "alice", "--region", "iad", "--version",
                      "3.13.2", "--blob", "@" + self.blob,
                      "--token-env", "HP_UNSET_TOKEN_XYZ")
        self.assertIn("HP_UNSET_TOKEN_XYZ", str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
