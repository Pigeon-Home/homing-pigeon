#!/usr/bin/env python3
"""Poison-input tests for the setup wizard and installer helpers.

Grok is hardening the runner's poll loop; this file covers the setup
path she isn't touching: non-string values in a hand-edited config
must not crash the wizard.
"""
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
from runner.ops import install as IN  # noqa: E402


class PlaceholderPoisonTest(unittest.TestCase):
    """Findings: _looks_like_placeholder called .lower() and
    _looks_patterned called len() on whatever the config held. A
    numeric secret crashed both with AttributeError/TypeError."""

    def test_placeholder_nonstring(self):
        self.assertFalse(IN._looks_like_placeholder(12345))
        self.assertFalse(IN._looks_like_placeholder(None))
        self.assertFalse(IN._looks_like_placeholder(["x"]))

    def test_patterned_nonstring(self):
        self.assertFalse(IN._looks_patterned(12345))
        self.assertFalse(IN._looks_patterned(None))

    def test_secret_is_real_nonstring(self):
        self.assertFalse(SU._secret_is_real(12345))
        self.assertFalse(SU._secret_is_real(None))
        self.assertFalse(SU._secret_is_real(["x"]))

    def test_real_secrets_still_real(self):
        self.assertTrue(SU._secret_is_real(SU.secrets.token_hex(32)))
        self.assertFalse(SU._secret_is_real("changeme-123"))
        self.assertFalse(SU._secret_is_real(""))


class WizardPoisonTest(unittest.TestCase):
    """Finding: a non-string mailbox_user or oauth_client_id in the
    config crashed the wizard's .strip() loops with AttributeError."""

    def _run(self, cfg, inputs):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w") as fh:
                json.dump(cfg, fh)
            with mock.patch("builtins.input", side_effect=inputs), \
                 mock.patch.object(SU, "browser_consent",
                                   return_value="tok"), \
                 mock.patch.object(SU, "_mailbox_probe",
                                   return_value=None), \
                 redirect_stdout(io.StringIO()):
                got = SU.run_setup_wizard(path, cfg)
            with open(path) as fh:
                written = json.load(fh)
            return got, written

    def test_numeric_mailbox_user_normalized(self):
        cfg = {"mailbox_user": 12345, "auth": "oauth",
               "oauth_client_id": "cid", "oauth_refresh_token": "tok",
               "shared_secret": SU.secrets.token_hex(32)}
        _, written = self._run(cfg, ["n", ""])
        self.assertEqual(written["mailbox_user"], "12345")

    def test_numeric_client_id_no_crash(self):
        cfg = {"mailbox_user": "a@b.c", "auth": "oauth",
               "oauth_client_id": 999, "shared_secret": "x" * 63 + "y"}
        # secret is 64 hex-ish chars, not patterned: kept as-is.
        # re-login "y", then keep secret with "".
        _, written = self._run(cfg, ["y", ""])
        self.assertEqual(written["oauth_client_id"], 999)

    def test_none_secret_replaced(self):
        cfg = {"mailbox_user": "a@b.c", "auth": "password",
               "mailbox_password": "p", "shared_secret": None}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch("builtins.input",
                            side_effect=["2", "y"]), \
                 mock.patch("getpass.getpass", return_value="p"), \
                 redirect_stdout(io.StringIO()):
                SU.run_setup_wizard(path, cfg)
            written = json.load(open(path))
        self.assertTrue(SU._secret_is_real(written["shared_secret"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
