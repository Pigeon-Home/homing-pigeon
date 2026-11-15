#!/usr/bin/env python3
"""Tests for the setup wizard's third sign-in choice (CS_canoe
option 3): browser sign-in under the project's own OAuth client,
plus a locally generated shared secret carried to the owner by an
install-record email to the mailbox itself.

Every send is mocked: no test here touches a real mailbox.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import setup as SU  # noqa: E402

REAL_SECRET = (
    "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
)


def _hex(n):
    return "cd" * n


class AutogenGateTest(unittest.TestCase):
    def test_absent_key_is_on(self):
        self.assertTrue(SU._autogen_login_enabled({}))

    def test_true_is_on(self):
        self.assertTrue(SU._autogen_login_enabled({"autogen_login": True}))

    def test_string_false_is_on(self):
        # The job_encryption convention: only literal false is off.
        self.assertTrue(SU._autogen_login_enabled({"autogen_login": "false"}))

    def test_literal_false_is_off(self):
        self.assertFalse(SU._autogen_login_enabled({"autogen_login": False}))


class InstallRecordTest(unittest.TestCase):
    FACTS = {
        "platform": "TestOS 1.0",
        "hostname": "test-host",
        "ip_address": "192.0.2.10",
        "memory": "16.0 GB",
        "hard_drive": "500.0 GB",
    }

    def test_body_carries_subject_secret_and_facts(self):
        body = SU.install_record_body("s3cr3t-fixture", self.FACTS)
        self.assertIn(SU.INSTALL_RECORD_SUBJECT, body)
        self.assertIn(
            "Homing Pigeon shared secret installed on this system", body)
        self.assertIn("s3cr3t-fixture", body)
        for label in ("Platform:", "Hostname:", "IP address:",
                      "Memory:", "Hard drive:"):
            self.assertIn(label, body)
        for value in self.FACTS.values():
            self.assertIn(value, body)

    def test_system_facts_shape(self):
        facts = SU.system_facts()
        self.assertEqual(
            set(facts),
            {"platform", "hostname", "ip_address", "memory", "hard_drive"})
        for value in facts.values():
            self.assertIsInstance(value, str)
            self.assertTrue(value)


class WizardCanoeTest(unittest.TestCase):
    def _run(self, inputs, cfg=None, email_result=None):
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            if cfg is not None:
                with open(path, "w") as fh:
                    json.dump(cfg, fh)
            with mock.patch("builtins.input", side_effect=inputs), \
                 mock.patch.object(SU, "browser_consent",
                                   return_value="refresh-123"), \
                 mock.patch.object(SU, "_mailbox_probe", return_value=None), \
                 mock.patch.object(SU, "_email_install_record",
                                   return_value=email_result) as mail, \
                 mock.patch.object(SU.secrets, "token_hex",
                                   side_effect=_hex), \
                 redirect_stdout(out), redirect_stderr(err):
                got = SU.run_setup_wizard(path, cfg)
            with open(path) as fh:
                written = json.load(fh)
        return got, written, mail, out.getvalue() + err.getvalue()

    def test_option3_happy_path(self):
        got, written, mail, text = self._run(
            ["3", ""], cfg={"mailbox_user": "runner@example.com"})
        self.assertIn("[3] Sign in with Google and generate a shared "
                      "secret", text)
        self.assertEqual(written["auth"], "oauth")
        # The baked-in project client: no client-ID prompt was fed.
        self.assertEqual(written["oauth_client_id"],
                         SU.DEFAULT_OAUTH_CLIENT_ID)
        self.assertEqual(written["oauth_refresh_token"], "refresh-123")
        self.assertEqual(written["shared_secret"], "cd" * 32)
        self.assertEqual(got["shared_secret"], "cd" * 32)
        # The record email carried the generated secret, exactly once.
        mail.assert_called_once()
        self.assertEqual(mail.call_args[0][1], "cd" * 32)
        # The generated secret is never printed to the console.
        self.assertNotIn("cd" * 32, text)
        self.assertIn("Install record emailed", text)

    def test_option3_config_client_id_wins(self):
        _, written, mail, _ = self._run(
            ["3", ""], cfg={"mailbox_user": "runner@example.com",
                            "oauth_client_id": "my-own-client-id"})
        self.assertEqual(written["oauth_client_id"], "my-own-client-id")
        self.assertEqual(written["shared_secret"], "cd" * 32)
        mail.assert_called_once()

    def test_option3_decline_generate_falls_back(self):
        _, written, mail, _ = self._run(
            ["3", "n", "y"], cfg={"mailbox_user": "runner@example.com"})
        # Declining the autogen offer takes the shown-secret path.
        self.assertEqual(written["shared_secret"], "cd" * 32)
        mail.assert_not_called()

    def test_option3_existing_secret_kept_no_email(self):
        _, written, mail, _ = self._run(
            ["3", ""], cfg={"mailbox_user": "runner@example.com",
                            "shared_secret": REAL_SECRET})
        self.assertEqual(written["shared_secret"], REAL_SECRET)
        mail.assert_not_called()

    def test_option3_disabled_shows_error_and_signs_in_plain(self):
        _, written, mail, text = self._run(
            ["3", "typed-client-id", "y"],
            cfg={"mailbox_user": "runner@example.com",
                 "autogen_login": False})
        self.assertIn("turned off", text)
        # The plain browser path ran: it asked for a client ID.
        self.assertEqual(written["oauth_client_id"], "typed-client-id")
        self.assertEqual(written["oauth_refresh_token"], "refresh-123")
        mail.assert_not_called()

    def test_option3_email_failure_is_not_fatal(self):
        got, written, mail, text = self._run(
            ["3", ""], cfg={"mailbox_user": "runner@example.com"},
            email_result="install record email failed: boom")
        self.assertEqual(written["shared_secret"], "cd" * 32)
        self.assertEqual(got["shared_secret"], "cd" * 32)
        self.assertIn("warning", text)
        mail.assert_called_once()

    def test_option1_never_emails_a_record(self):
        _, written, mail, _ = self._run(
            ["", "my-client-id", "y"],
            cfg={"mailbox_user": "runner@example.com"})
        self.assertEqual(written["oauth_client_id"], "my-client-id")
        mail.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
