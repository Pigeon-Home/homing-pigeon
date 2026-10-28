# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Q98's installer items, held where the installer meets the user.

Item 4: a config still holding runner/config.example.json's
placeholders needs setup, so the installer offers sign-in on a fresh
install. Item 5: `--setup` with no `--config` writes the installed
home's config.json when an installed home exists, not ./config.json
the service never reads.
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from runner.ops import main as MAIN  # noqa: E402
from runner.ops import setup  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PlaceholdersAreUnsetTest(unittest.TestCase):
    def test_the_example_config_needs_setup(self):
        with open(os.path.join(REPO, "runner", "config.example.json"),
                  encoding="utf-8") as fh:
            example = json.load(fh)
        self.assertEqual(setup.needs_setup(example), "mailbox_user is not set")
        filled_user = dict(example, mailbox_user="me@example.com")
        self.assertEqual(setup.needs_setup(filled_user), "mailbox_password is not set")
        filled = dict(filled_user, mailbox_password="an app password")
        self.assertIsNone(setup.needs_setup(filled))

    def test_the_placeholders_are_the_examples_own(self):
        with open(os.path.join(REPO, "runner", "config.example.json"),
                  encoding="utf-8") as fh:
            example = json.load(fh)
        for key, value in setup.EXAMPLE_PLACEHOLDERS.items():
            self.assertEqual(example[key], value, key)


class SetupWritesTheInstalledConfigTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="hp-q98-home-")
        self.addCleanup(shutil.rmtree, self.home, True)

    def test_an_installed_home_is_found(self):
        cfg = os.path.join(self.home, ".homing-pigeon", "config.json")
        os.makedirs(os.path.dirname(cfg))
        with open(cfg, "w") as fh:
            fh.write("{}")
        with mock.patch.object(MAIN.sys, "platform", "linux"), \
                mock.patch.object(MAIN.os.path, "expanduser", return_value=self.home):
            self.assertEqual(MAIN._installed_config(), cfg)

    def test_no_installed_home_is_none(self):
        with mock.patch.object(MAIN.sys, "platform", "linux"), \
                mock.patch.object(MAIN.os.path, "expanduser", return_value=self.home):
            self.assertIsNone(MAIN._installed_config())

    def test_a_named_config_is_always_the_one_written(self):
        self.assertTrue(MAIN._config_given(["--setup", "--config", "x.json"]))
        self.assertTrue(MAIN._config_given(["--config=x.json", "--setup"]))
        self.assertFalse(MAIN._config_given(["--setup"]))



class UninstallFindsTheUnitTest(unittest.TestCase):
    def test_a_system_unit_is_found_without_system(self):
        from runner.ops import install as inst
        removed, cmds = [], []
        real_exists = os.path.exists
        with mock.patch.object(inst, "run", cmds.append), \
                mock.patch.object(os, "remove", removed.append), \
                mock.patch.object(os.path, "exists",
                                  lambda p: p == inst.SYSTEM_UNIT or real_exists(p)):
            inst.uninstall_linux(False)
        self.assertEqual(removed, [inst.SYSTEM_UNIT])
        self.assertIn(["systemctl", "disable", "--now", "homing-pigeon.service"], cmds)

    def test_no_unit_is_said_not_raised(self):
        from runner.ops import install as inst
        home = tempfile.mkdtemp(prefix="hp-q98-nounit-")
        self.addCleanup(shutil.rmtree, home, True)
        with mock.patch.object(inst, "run", lambda c: None), \
                mock.patch.object(os.path, "expanduser",
                                  lambda p: p.replace("~", home)), \
                mock.patch.object(inst, "SYSTEM_UNIT",
                                  os.path.join(home, "nope.service")):
            inst.uninstall_linux(False)


class InstallerEntropyGateTest(unittest.TestCase):
    def test_a_secret_the_runner_accepts_the_installer_accepts(self):
        from runner.guard import security
        from runner.ops import install as inst
        import random
        rng = random.Random(98)
        alphabet = "abcdefghijklmno"            # 15 symbols
        while True:
            secret = "".join(rng.choice(alphabet) for _ in range(33))
            if len(set(secret)) == 15 and not inst._looks_patterned(secret):
                break
        self.assertGreaterEqual(security._estimate_secret_entropy(secret), 128)
        d = tempfile.mkdtemp(prefix="hp-q98-gate-")
        self.addCleanup(shutil.rmtree, d, True)
        cfg = os.path.join(d, "config.json")
        with open(cfg, "w") as fh:
            json.dump({}, fh)
        patterned = False
        security.validate_shared_secret(secret)   # the runner takes it
        try:
            inst.ensure_shared_secret(cfg, provided=secret)
            refused = False
        except SystemExit:
            refused = True
        # the installer refuses it only for the pattern rule the runner
        # also applies, never for the estimate
        self.assertEqual(refused, patterned)


if __name__ == "__main__":
    unittest.main()
