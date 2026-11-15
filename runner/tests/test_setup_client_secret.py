#!/usr/bin/env python3
"""The setup wizard and the OAuth client secret: CS_canoe option 3's
first-run failure of 2026-11-14.

SUPPOSITION, recorded before the fix: on a fresh config the wizard's
browser sign-in completes in the browser and then dies at the token
exchange with Google's "client_secret is missing", because the
exchange form carries a client_secret only when the config already
holds one, and nothing in the wizard ever obtains one — the baked
project client ID is filled in, its secret is not (and never will
be: a secret does not ride in the tree). The tests below pin the
remedy: before the exchange, the wizard asks for the secret once,
hidden (getpass), with one plain sentence saying why; the entered
value lands in the config under oauth_client_secret and so in the
exchange form; it never appears on the console; an empty,
whitespace-only, or interrupted answer stops setup with a plain
message naming what is missing and what to do, not Google's raw
error. A config that already carries a secret is never re-asked,
and a retry after a failed sign-in does not ask twice.

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
    """The wizard's obtain-once step, unit by unit."""

    def _ensure(self, cfg, getpass_kw):
        out = io.StringIO()
        with mock.patch("getpass.getpass", **getpass_kw) as gp, \
                redirect_stdout(out):
            SU._ensure_oauth_client_secret(cfg)
        return gp, out.getvalue()

    def test_configured_secret_is_never_reasked(self):
        cfg = {"oauth_client_secret": "already-set"}
        gp, _ = self._ensure(cfg, {"return_value": FIXTURE})
        gp.assert_not_called()
        self.assertEqual(cfg["oauth_client_secret"], "already-set")

    def test_prompt_stores_the_entered_secret(self):
        cfg = {}
        gp, _ = self._ensure(cfg, {"return_value": FIXTURE})
        gp.assert_called_once()
        self.assertEqual(cfg["oauth_client_secret"], FIXTURE)

    def test_surrounding_whitespace_is_stripped(self):
        cfg = {}
        self._ensure(cfg, {"return_value": "  " + FIXTURE + " \t"})
        self.assertEqual(cfg["oauth_client_secret"], FIXTURE)

    def test_whitespace_only_config_counts_as_missing(self):
        cfg = {"oauth_client_secret": "   "}
        gp, _ = self._ensure(cfg, {"return_value": FIXTURE})
        gp.assert_called_once()
        self.assertEqual(cfg["oauth_client_secret"], FIXTURE)

    def test_the_secret_is_never_printed(self):
        _, text = self._ensure({}, {"return_value": FIXTURE})
        self.assertNotIn(FIXTURE, text)
        # The one plain sentence saying why it is asked.
        self.assertIn("client secret", text)

    def _failure(self, getpass_kw):
        cfg = {}
        with mock.patch("getpass.getpass", **getpass_kw), \
                redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                SU._ensure_oauth_client_secret(cfg)
        self.assertNotIn("oauth_client_secret", cfg)
        return str(caught.exception)

    def test_empty_answer_fails_plainly(self):
        msg = self._failure({"return_value": ""})
        self.assertIn("client secret", msg)
        self.assertIn("choice 2", msg)  # what to do instead
        self.assertNotIn("invalid_request", msg)
        self.assertNotIn("HTTP 400", msg)

    def test_whitespace_only_answer_fails_plainly(self):
        msg = self._failure({"return_value": "  \t  "})
        self.assertIn("client secret", msg)

    def test_eof_fails_plainly(self):
        msg = self._failure({"side_effect": EOFError})
        self.assertIn("client secret", msg)

    def test_interrupt_fails_plainly_not_with_a_traceback(self):
        msg = self._failure({"side_effect": KeyboardInterrupt})
        self.assertIn("client secret", msg)


class WizardClientSecretTest(unittest.TestCase):
    """The whole wizard, the way the first-run failure happened."""

    def _run(self, inputs, cfg=None, consent=None, secret_answer=FIXTURE):
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
                    mock.patch("getpass.getpass",
                               return_value=secret_answer) as gp, \
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

    def test_option3_fresh_config_asks_once_and_stores(self):
        _, written, gp, seen_cfg, text = self._run(
            ["3", ""], cfg={"mailbox_user": "runner@example.com"})
        gp.assert_called_once()
        # The consent itself already saw the secret in the config,
        # so the exchange that follows it can carry the field.
        self.assertEqual(seen_cfg[0]["oauth_client_secret"], FIXTURE)
        self.assertEqual(written["oauth_client_secret"], FIXTURE)
        self.assertEqual(written["oauth_refresh_token"], "refresh-123")
        self.assertNotIn(FIXTURE, text)

    def test_option1_fresh_config_asks_and_stores_too(self):
        _, written, gp, _, text = self._run(
            ["", "my-client-id", "y"],
            cfg={"mailbox_user": "runner@example.com"})
        gp.assert_called_once()
        self.assertEqual(written["oauth_client_id"], "my-client-id")
        self.assertEqual(written["oauth_client_secret"], FIXTURE)
        self.assertNotIn(FIXTURE, text)

    def test_configured_secret_skips_the_prompt(self):
        cfg = {"mailbox_user": "runner@example.com",
               "oauth_client_secret": "already-set"}
        _, written, gp, _, _ = self._run(["3", ""], cfg=cfg)
        gp.assert_not_called()
        self.assertEqual(written["oauth_client_secret"], "already-set")

    def test_empty_secret_stops_before_any_sign_in(self):
        consent = mock.Mock(return_value="refresh-123")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch("builtins.input", side_effect=["3"]), \
                    mock.patch("getpass.getpass", return_value=""), \
                    mock.patch.object(SU, "browser_consent", consent), \
                    redirect_stdout(io.StringIO()), \
                    redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    SU.run_setup_wizard(
                        path, {"mailbox_user": "runner@example.com"})
            self.assertFalse(os.path.exists(path))
        consent.assert_not_called()
        msg = str(caught.exception)
        self.assertIn("client secret", msg)
        self.assertNotIn("invalid_request", msg)

    def test_a_retry_does_not_ask_twice(self):
        answers = [SystemExit("boom"), "refresh-123"]

        def consent(cfg):
            result = answers.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result

        _, written, gp, _, _ = self._run(
            ["3", "y", ""], cfg={"mailbox_user": "runner@example.com"},
            consent=consent)
        gp.assert_called_once()
        self.assertEqual(written["oauth_refresh_token"], "refresh-123")
        self.assertEqual(written["oauth_client_secret"], FIXTURE)

    def test_relogin_without_a_secret_asks_and_stores(self):
        cfg = {"mailbox_user": "runner@example.com", "auth": "oauth",
               "oauth_client_id": "cid", "oauth_refresh_token": "tok",
               "shared_secret": "ab" * 32}
        _, written, gp, _, _ = self._run(["y", ""], cfg=cfg)
        gp.assert_called_once()
        self.assertEqual(written["oauth_client_secret"], FIXTURE)
        self.assertEqual(written["oauth_refresh_token"], "refresh-123")


if __name__ == "__main__":
    unittest.main(verbosity=2)
