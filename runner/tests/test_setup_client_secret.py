#!/usr/bin/env python3
"""The setup wizard and the OAuth client secret: CS_canoe option 3's
first-run failure of 2026-11-14, and the remedy's settled shape.

SUPPOSITION, recorded before the first fix: on a fresh config the
wizard's browser sign-in completes in the browser and then dies at
the token exchange with Google's "client_secret is missing",
because the exchange form carries a client_secret only when the
config already holds one, and nothing in the wizard ever obtains
one. The first remedy asked for the secret once, hidden (getpass),
before the browser opened. The conductor's design overruled that
shape the same night: the sign-in is Thunderbird-style, so the
Homing Pigeon desktop client's secret is baked in beside its ID
(DEFAULT_OAUTH_CLIENT_SECRET) and the wizard never asks — the
browser opens directly, with nothing to paste or type. The tests
below pin the settled remedy: before the exchange the config
carries a client secret under oauth_client_secret — its own value
when one is set (a config override always wins), otherwise the
baked-in default — so the exchange form carries the field;
getpass is never called on the browser sign-in paths, not on a
first run, not on a retry, not on a re-login; and the secret
never appears on the console.

Every exchange is mocked: no test here touches the network.
"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import setup as SU  # noqa: E402
from runner.wire import oauth as OA  # noqa: E402

FIXTURE = "client-secret-fixture-9c1e"


class _Resp:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _capturing_opener(seen, body=b'{"refresh_token": "rt-fixture"}'):
    def opener(req, timeout=30):
        seen.append(urllib.parse.parse_qs(req.data.decode("ascii")))
        return _Resp(body)
    return opener


class ExchangeFormTest(unittest.TestCase):
    """The exchange layer, unchanged: the form carries the secret
    exactly when the config holds one."""

    def test_form_carries_secret_when_configured(self):
        seen = []
        refresh = OA.exchange_code(
            {"oauth_client_id": "cid", "oauth_client_secret": FIXTURE},
            "code", "verifier", opener=_capturing_opener(seen))
        self.assertEqual(refresh, "rt-fixture")
        self.assertEqual(seen[0]["client_secret"], [FIXTURE])
        self.assertEqual(seen[0]["client_id"], ["cid"])

    def test_form_omits_secret_when_unconfigured(self):
        seen = []
        OA.exchange_code({"oauth_client_id": "cid"}, "code", "verifier",
                         opener=_capturing_opener(seen))
        self.assertNotIn("client_secret", seen[0])

    def test_refresh_form_carries_secret_when_configured(self):
        seen = []

        def fake_urlopen(req, timeout=30):
            seen.append(urllib.parse.parse_qs(req.data.decode("ascii")))
            return _Resp(b'{"access_token": "ya29.fixture"}')

        with mock.patch("runner.wire.oauth.urllib.request.urlopen",
                        side_effect=fake_urlopen):
            token = OA.refresh_access_token({
                "oauth_client_id": "cid",
                "oauth_refresh_token": "rt",
                "oauth_client_secret": FIXTURE})
        self.assertEqual(token, "ya29.fixture")
        self.assertEqual(seen[0]["client_secret"], [FIXTURE])


class EnsureSecretTest(unittest.TestCase):
    """The wizard's fill-in step, unit by unit: never a prompt."""

    def _ensure(self, cfg):
        out = io.StringIO()
        with mock.patch("getpass.getpass") as gp, \
                redirect_stdout(out):
            SU._ensure_oauth_client_secret(cfg)
        return gp, out.getvalue()

    def test_configured_secret_wins_and_nothing_is_asked(self):
        cfg = {"oauth_client_secret": "already-set"}
        gp, _ = self._ensure(cfg)
        gp.assert_not_called()
        self.assertEqual(cfg["oauth_client_secret"], "already-set")

    def test_missing_secret_gets_the_baked_in_default(self):
        cfg = {}
        gp, _ = self._ensure(cfg)
        gp.assert_not_called()
        self.assertEqual(cfg["oauth_client_secret"],
                         SU.DEFAULT_OAUTH_CLIENT_SECRET)

    def test_whitespace_only_config_counts_as_missing(self):
        cfg = {"oauth_client_secret": "   "}
        gp, _ = self._ensure(cfg)
        gp.assert_not_called()
        self.assertEqual(cfg["oauth_client_secret"],
                         SU.DEFAULT_OAUTH_CLIENT_SECRET)

    def test_the_default_is_a_real_secret_not_a_placeholder(self):
        default = SU.DEFAULT_OAUTH_CLIENT_SECRET
        self.assertTrue(default)
        self.assertNotIn(" ", default)
        self.assertNotIn("paste", default)
        self.assertNotEqual(default, FIXTURE)

    def test_the_secret_is_never_printed(self):
        _, text = self._ensure({})
        self.assertNotIn(SU.DEFAULT_OAUTH_CLIENT_SECRET, text)
        self.assertNotIn("typing hidden", text)


class WizardClientSecretTest(unittest.TestCase):
    """The whole wizard, the way the first-run failure happened —
    and the way it cannot happen now: no prompt stands between
    the menu and the browser, on any browser sign-in path."""

    def _run(self, inputs, cfg=None, consent=None):
        out, err = io.StringIO(), io.StringIO()
        seen_cfg = []
        if consent is None:
            def consent(cfg):  # noqa: F811
                seen_cfg.append(dict(cfg))
                return "refresh-123"
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            if cfg is not None:
                with open(path, "w") as fh:
                    json.dump(cfg, fh)
            with mock.patch("builtins.input", side_effect=inputs), \
                    mock.patch("getpass.getpass") as gp, \
                    mock.patch.object(SU, "browser_consent",
                                      side_effect=consent), \
                    mock.patch.object(SU, "_mailbox_probe",
                                      return_value=None), \
                    mock.patch.object(SU, "_email_install_record",
                                      return_value=None), \
                    redirect_stdout(out), redirect_stderr(err):
                got = SU.run_setup_wizard(path, cfg)
            written = None
            if os.path.exists(path):
                with open(path) as fh:
                    written = json.load(fh)
        return got, written, gp, seen_cfg, out.getvalue() + err.getvalue()

    def test_option3_fresh_config_goes_directly_to_the_browser(self):
        _, written, gp, seen_cfg, text = self._run(
            ["3", ""], cfg={"mailbox_user": "runner@example.com"})
        gp.assert_not_called()
        # The consent itself already saw the secret in the config,
        # so the exchange that follows it can carry the field.
        self.assertEqual(seen_cfg[0]["oauth_client_secret"],
                         SU.DEFAULT_OAUTH_CLIENT_SECRET)
        self.assertEqual(written["oauth_client_secret"],
                         SU.DEFAULT_OAUTH_CLIENT_SECRET)
        self.assertEqual(written["oauth_refresh_token"], "refresh-123")
        self.assertNotIn(SU.DEFAULT_OAUTH_CLIENT_SECRET, text)

    def test_option1_fresh_config_uses_the_default_too(self):
        _, written, gp, _, text = self._run(
            ["", "my-client-id", "y"],
            cfg={"mailbox_user": "runner@example.com"})
        gp.assert_not_called()
        self.assertEqual(written["oauth_client_id"], "my-client-id")
        self.assertEqual(written["oauth_client_secret"],
                         SU.DEFAULT_OAUTH_CLIENT_SECRET)
        self.assertNotIn(SU.DEFAULT_OAUTH_CLIENT_SECRET, text)

    def test_configured_secret_wins_over_the_default(self):
        cfg = {"mailbox_user": "runner@example.com",
               "oauth_client_secret": "already-set"}
        _, written, gp, seen_cfg, _ = self._run(["3", ""], cfg=cfg)
        gp.assert_not_called()
        self.assertEqual(seen_cfg[0]["oauth_client_secret"],
                         "already-set")
        self.assertEqual(written["oauth_client_secret"], "already-set")

    def test_a_retry_never_asks_either(self):
        answers = [SystemExit("boom"), "refresh-123"]

        def consent(cfg):
            result = answers.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result

        _, written, gp, _, _ = self._run(
            ["3", "y", ""], cfg={"mailbox_user": "runner@example.com"},
            consent=consent)
        gp.assert_not_called()
        self.assertEqual(written["oauth_refresh_token"], "refresh-123")
        self.assertEqual(written["oauth_client_secret"],
                         SU.DEFAULT_OAUTH_CLIENT_SECRET)

    def test_relogin_without_a_secret_gets_the_default(self):
        cfg = {"mailbox_user": "runner@example.com", "auth": "oauth",
               "oauth_client_id": "cid", "oauth_refresh_token": "tok",
               "shared_secret": "ab" * 32}
        _, written, gp, _, _ = self._run(["y", ""], cfg=cfg)
        gp.assert_not_called()
        self.assertEqual(written["oauth_client_secret"],
                         SU.DEFAULT_OAUTH_CLIENT_SECRET)
        self.assertEqual(written["oauth_refresh_token"], "refresh-123")


if __name__ == "__main__":
    unittest.main(verbosity=2)
