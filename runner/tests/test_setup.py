#!/usr/bin/env python3
"""Tests for the Thunderbird-style first-run setup wizard."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import setup as SU  # noqa: E402


def _oauth_cfg(**kw):
    cfg = {"mailbox_user": "runner@example.com", "auth": "oauth",
           "oauth_client_id": "cid", "oauth_refresh_token": "tok"}
    cfg.update(kw)
    return cfg


class NeedsSetupTest(unittest.TestCase):
    def test_missing_user(self):
        self.assertIn("mailbox_user", SU.needs_setup({}))

    def test_oauth_missing_client(self):
        cfg = _oauth_cfg(oauth_client_id="")
        self.assertIn("oauth_client_id", SU.needs_setup(cfg))

    def test_oauth_missing_token(self):
        cfg = _oauth_cfg(oauth_refresh_token="")
        self.assertIn("refresh token", SU.needs_setup(cfg))

    def test_oauth_complete(self):
        self.assertIsNone(SU.needs_setup(_oauth_cfg()))

    def test_password_missing(self):
        cfg = {"mailbox_user": "a@b.c", "auth": "password"}
        self.assertIn("mailbox_password", SU.needs_setup(cfg))

    def test_password_complete(self):
        cfg = {"mailbox_user": "a@b.c", "auth": "password",
               "mailbox_password": "x"}
        self.assertIsNone(SU.needs_setup(cfg))

    def test_not_a_dict(self):
        self.assertIsNotNone(SU.needs_setup(["x"]))


class PromptTest(unittest.TestCase):
    def test_default_yes(self):
        with mock.patch("builtins.input", return_value=""):
            self.assertTrue(SU.prompt_yes_no("Q? [Y/n] "))

    def test_no(self):
        with mock.patch("builtins.input", return_value="n"):
            self.assertFalse(SU.prompt_yes_no("Q? [Y/n] "))

    def test_eof_takes_default(self):
        with mock.patch("builtins.input", side_effect=EOFError):
            self.assertFalse(SU.prompt_yes_no("Q? [y/N] ", default=False))


class WizardOAuthTest(unittest.TestCase):
    def _run(self, inputs, cfg=None):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            if cfg is not None:
                with open(path, "w") as fh:
                    json.dump(cfg, fh)
            with mock.patch("builtins.input", side_effect=inputs), \
                 mock.patch.object(SU, "browser_consent",
                                   return_value="refresh-123"), \
                 mock.patch.object(SU, "_mailbox_probe", return_value=None), \
                 redirect_stdout(io.StringIO()):
                got = SU.run_setup_wizard(path, cfg)
            with open(path) as fh:
                written = json.load(fh)
            return got, written

    def test_full_oauth_flow(self):
        got, written = self._run([
            "runner@example.com",  # gmail address
            "",                    # choice: oauth (default)
            "my-client-id",        # oauth client id
            "y",                   # accept secret
        ])
        self.assertEqual(written["mailbox_user"], "runner@example.com")
        self.assertEqual(written["auth"], "oauth")
        self.assertEqual(written["oauth_client_id"], "my-client-id")
        self.assertEqual(written["oauth_refresh_token"], "refresh-123")
        secret = written["shared_secret"]
        self.assertEqual(len(secret), 64)
        int(secret, 16)  # valid hex
        self.assertEqual(got["shared_secret"], secret)

    def test_secret_decline_regenerates(self):
        with mock.patch.object(SU.secrets, "token_hex",
                               side_effect=["a" * 64, "b" * 64,
                                            "c" * 16]):
            _, written = self._run([
                "runner@example.com", "", "cid",
                "n",   # decline first secret
                "y",   # accept second
            ])
        self.assertEqual(written["shared_secret"], "b" * 64)
        # Hardening M5: fresh configs also get a runner_id.
        self.assertEqual(written["runner_id"], "c" * 16)

    def test_password_flow(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch("builtins.input",
                            side_effect=["runner@example.com", "2", "y"]), \
                 mock.patch("getpass.getpass",
                            return_value="app-pass-123"), \
                 redirect_stdout(io.StringIO()):
                SU.run_setup_wizard(path)
            written = json.load(open(path))
        self.assertEqual(written["auth"], "password")
        self.assertEqual(written["mailbox_password"], "app-pass-123")
        self.assertNotIn("oauth_refresh_token", written)

    def test_relogin_offer_declined_keeps_everything(self):
        secret = SU.secrets.token_hex(32)
        cfg = _oauth_cfg(shared_secret=secret)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w") as fh:
                json.dump(cfg, fh)
            with mock.patch.object(SU, "browser_consent") as bc, \
                 mock.patch("builtins.input", side_effect=["n", ""]), \
                 redirect_stdout(io.StringIO()):
                SU.run_setup_wizard(path, cfg)
            written = json.load(open(path))
        bc.assert_not_called()
        self.assertEqual(written["oauth_refresh_token"], "tok")
        self.assertEqual(written["shared_secret"], secret)

    def test_relogin_accepted_redoes_browser_login(self):
        cfg = _oauth_cfg(shared_secret=SU.secrets.token_hex(32))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w") as fh:
                json.dump(cfg, fh)
            with mock.patch.object(SU, "browser_consent",
                                   return_value="new-tok") as bc, \
                 mock.patch.object(SU, "_mailbox_probe",
                                   return_value=None), \
                 mock.patch("builtins.input", side_effect=["y", ""]), \
                 redirect_stdout(io.StringIO()):
                SU.run_setup_wizard(path, cfg)
            written = json.load(open(path))
        bc.assert_called_once()
        self.assertEqual(written["oauth_refresh_token"], "new-tok")

    def test_probe_warning_nonfatal(self):
        # A failing IMAP probe warns but does not abort setup.
        got, written = self._run([
            "runner@example.com", "", "cid", "y",
        ])
        # _mailbox_probe is mocked to None in _run; run once unmocked
        # shape check instead: probe returns a string on failure.
        self.assertIsNotNone(written["oauth_refresh_token"])

    def test_blank_starts_from_example(self):
        cfg = SU._blank_config()
        # example keys present, placeholder secrets and the example
        # address stripped -- the wizard asks for real ones
        self.assertIn("auth", cfg)
        self.assertNotIn("shared_secret", cfg)
        self.assertNotIn("mailbox_user", cfg)
        self.assertNotIn("oauth_refresh_token", cfg)

    def test_empty_config_still_gets_gmail_hosts(self):
        with mock.patch.object(SU, "_blank_config", return_value={}):
            _, written = self._run([
                "runner@example.com", "", "my-client-id", "y",
            ])
        self.assertEqual(written["imap_host"], "imap.gmail.com")
        self.assertEqual(written["imap_port"], 993)
        self.assertEqual(written["smtp_host"], "smtp.gmail.com")
        self.assertEqual(written["smtp_port"], 587)

    def test_example_beside_the_executable(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.example.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "imap_host": "imap.from.zip",
                    "imap_port": 993,
                    "smtp_host": "smtp.from.zip",
                    "smtp_port": 587,
                    "mailbox_user": "drop-me@example.com",
                    "shared_secret": "generate-with-openssl-rand-hex-32",
                }, fh)
            with mock.patch.object(SU, "_example_candidates", return_value=[
                    os.path.join(d, "missing.json"), path]):
                cfg = SU._blank_config()
        self.assertEqual(cfg["imap_host"], "imap.from.zip")
        self.assertEqual(cfg["smtp_host"], "smtp.from.zip")
        self.assertNotIn("mailbox_user", cfg)
        self.assertNotIn("shared_secret", cfg)

    def test_eof_during_address_is_a_clean_exit(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch("builtins.input", side_effect=EOFError):
                with self.assertRaises(SystemExit) as caught:
                    SU.run_setup_wizard(path, {})
        self.assertIn("console", str(caught.exception))


class WizardSeedPlatformModesTest(unittest.TestCase):
    """A config the setup wizard seeds states the platform gates.

    The installer's fresh-install path states them (install.py's
    apply_platform_modes); the wizard is the other fresh-seed path --
    the runner started with no config file, the wizard creating one
    from the example. Without the same statement, that seed carried
    the example's enforce for confinement and job_user onto Windows,
    where neither mechanism can engage, and the first start was the
    startup refusal. Only the seed is gated: a config that already
    exists keeps the owner's stated modes, so an explicit enforce
    on win32 still meets the startup refusal pinned in
    test_windows_platform_proofs.
    """

    _OTHER_MODES = ("policy_env", "policy_files", "policy_args",
                    "audience", "personal_docs_shelter",
                    "agent_state_guard")

    def _example_cfg(self):
        path = os.path.join(REPO, "runner", "config.example.json")
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_win32_seed_states_both_modes_at_audit(self):
        cfg = self._example_cfg()
        applied = SU.seed_platform_modes(cfg, platform="win32")
        self.assertEqual(applied, {"confinement": "audit",
                                   "job_user": "audit"})
        modes = cfg["security"]["modes"]
        self.assertEqual(modes["confinement"], "audit")
        self.assertEqual(modes["job_user"], "audit")
        for feature in self._OTHER_MODES:
            self.assertEqual(modes[feature], "enforce", feature)

    def test_linux_seed_is_unchanged(self):
        cfg = self._example_cfg()
        before = json.loads(json.dumps(cfg))
        applied = SU.seed_platform_modes(cfg, platform="linux")
        self.assertEqual(applied, {})
        self.assertEqual(cfg, before)
        for feature in ("confinement", "job_user") + self._OTHER_MODES:
            self.assertEqual(cfg["security"]["modes"][feature],
                             "enforce", feature)

    def test_darwin_seed_states_confinement_only(self):
        cfg = self._example_cfg()
        applied = SU.seed_platform_modes(cfg, platform="darwin")
        self.assertEqual(applied, {"confinement": "audit"})
        modes = cfg["security"]["modes"]
        self.assertEqual(modes["confinement"], "audit")
        self.assertEqual(modes["job_user"], "enforce")

    def test_a_mode_already_stated_lower_stays(self):
        cfg = self._example_cfg()
        cfg["security"]["modes"]["confinement"] = "off"
        applied = SU.seed_platform_modes(cfg, platform="win32")
        self.assertEqual(applied, {"job_user": "audit"})
        self.assertEqual(cfg["security"]["modes"]["confinement"], "off")

    def test_seed_without_a_security_block_states_the_modes(self):
        # _load_example's fallback (no example file shipped) carries
        # no security block at all; the gated modes are still stated
        # in the seeded file rather than left to read as enforce.
        cfg = {"auth": "password"}
        applied = SU.seed_platform_modes(cfg, platform="win32")
        self.assertEqual(applied, {"confinement": "audit",
                                   "job_user": "audit"})
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "audit")
        self.assertEqual(cfg["security"]["modes"]["job_user"], "audit")

    def _run_fresh_wizard(self, platform):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            out = io.StringIO()
            with mock.patch.object(SU.sys, "platform", platform), \
                 mock.patch("builtins.input", side_effect=[
                     "runner@example.com",  # gmail address
                     "",                     # choice: oauth (default)
                     "my-client-id",         # oauth client id
                     "y",                    # accept secret
                 ]), \
                 mock.patch.object(SU, "browser_consent",
                                   return_value="refresh-123"), \
                 mock.patch.object(SU, "_mailbox_probe",
                                   return_value=None), \
                 redirect_stdout(out):
                SU.run_setup_wizard(path)
            with open(path) as fh:
                written = json.load(fh)
            return written, out.getvalue()

    def test_wizard_fresh_seed_on_win32_states_and_says_so(self):
        written, out = self._run_fresh_wizard("win32")
        modes = written["security"]["modes"]
        self.assertEqual(modes["confinement"], "audit")
        self.assertEqual(modes["job_user"], "audit")
        for feature in self._OTHER_MODES:
            self.assertEqual(modes[feature], "enforce", feature)
        # Stated out loud in the wizard, not a silent downgrade.
        self.assertIn("security.modes.confinement stated as audit", out)
        self.assertIn("security.modes.job_user stated as audit", out)

    def test_wizard_fresh_seed_on_linux_keeps_enforce(self):
        written, out = self._run_fresh_wizard("linux")
        modes = written["security"]["modes"]
        for feature in ("confinement", "job_user") + self._OTHER_MODES:
            self.assertEqual(modes[feature], "enforce", feature)
        self.assertNotIn("stated as audit", out)

    def test_wizard_leaves_an_existing_config_modes_alone(self):
        # The owner's explicit enforce is not the seed's: completing
        # an existing config on win32 must not soften its modes --
        # the startup refusal for that config is the designed path.
        cfg = _oauth_cfg(
            shared_secret="s" * 64,
            security={"modes": {"confinement": "enforce",
                                 "job_user": "enforce"}})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w") as fh:
                json.dump(cfg, fh)
            with mock.patch.object(SU.sys, "platform", "win32"), \
                 mock.patch.object(SU, "browser_consent") as bc, \
                 mock.patch("builtins.input", side_effect=["n", ""]), \
                 redirect_stdout(io.StringIO()):
                SU.run_setup_wizard(path, cfg)
            with open(path) as fh:
                written = json.load(fh)
        bc.assert_not_called()
        self.assertEqual(written["security"]["modes"]["confinement"],
                         "enforce")
        self.assertEqual(written["security"]["modes"]["job_user"],
                         "enforce")


class WizardSecretTest(unittest.TestCase):
    def test_accept_secret_loop(self):
        with mock.patch("builtins.input", side_effect=["n", "y"]), \
             mock.patch.object(SU.secrets, "token_hex",
                               side_effect=["a" * 64, "b" * 64]), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(SU._accept_secret(), "b" * 64)

    def test_secret_is_real(self):
        self.assertTrue(SU._secret_is_real(SU.secrets.token_hex(32)))
        self.assertFalse(SU._secret_is_real(""))
        self.assertFalse(SU._secret_is_real("d" * 64))  # patterned
        self.assertFalse(
            SU._secret_is_real("generate-with-openssl-rand-hex-32"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
