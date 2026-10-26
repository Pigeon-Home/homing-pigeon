#!/usr/bin/env python3
"""
Thunderbird-style Gmail sign-in for the runner.

Opens the system browser (the same way Thunderbird does), catches the
redirect on localhost, and stores a refresh token. The Google password
never touches the command line or config.json.

Windows is the target. The same flow works on the other platforms.

One-time setup (you create the Desktop OAuth client; we cannot ship one):
  1. Google Cloud Console -> APIs & Services -> Credentials
     -> Create OAuth client ID -> Desktop app.
  2. Add authorized redirect URI: http://127.0.0.1:8765/
  3. Put the client id (and secret, if Google gave you one) in config.json:
       "auth": "oauth"
       "oauth_client_id": "....apps.googleusercontent.com"
       "oauth_client_secret": ""
       "shared_secret": "<hmac key, not the Google password>"
  4. Run: homing-pigeon-auth --config config.json
     A browser opens. Sign in there. The refresh token is written back.
"""
import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

try:
    from runner.guard import atomicio as _atomicio
except ImportError:  # running from inside runner/ as __main__
    from guard import atomicio as _atomicio  # type: ignore
try:
    from runner._version import __version__
except ImportError:  # running from inside runner/ as __main__
    try:
        from _version import __version__
    except ImportError:
        __version__ = "unknown"

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class OAuthRefreshError(RuntimeError):
    """Google rejected the refresh token (invalid_grant, etc.).

    The stored credential is dead; only a human browser login can fix
    it. Distinct from transient network failures so the caller can
    escalate instead of just retrying.
    """
SCOPE = "https://mail.google.com/"
REDIRECT_PORT = 8765
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/"


def xoauth2_raw(user: str, access_token: str) -> str:
    """SASL XOAUTH2 initial response, unencoded.

    Both libraries base64 this themselves. Pre-encoding it is the bug:
    the server then sees a blob of a blob and rejects it. A non-ASCII
    user or token cannot be a SASL response; fail here instead of
    UnicodeEncodeError mid-poll.
    """
    user = user if isinstance(user, str) else ""
    access_token = access_token if isinstance(access_token, str) else ""
    try:
        user.encode("ascii")
        access_token.encode("ascii")
    except UnicodeEncodeError as e:
        raise OAuthRefreshError(
            "mailbox user or access token is not ASCII. "
            "Re-run the browser login.") from e
    return f"user={user}\x01auth=Bearer {access_token}\x01\x01"


def _pkce() -> tuple:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def refresh_access_token(cfg: dict) -> str:
    """Trade the stored refresh token for a short-lived access token.

    Raises OAuthRefreshError (not plain RuntimeError) when Google rejects
    the refresh — the caller's signal that human re-authentication is
    needed, as opposed to a transient failure.
    """
    form = {
        "client_id": cfg["oauth_client_id"],
        "refresh_token": cfg["oauth_refresh_token"],
        "grant_type": "refresh_token",
    }
    secret = cfg.get("oauth_client_secret") or ""
    if secret:
        form["client_secret"] = secret
    data = urllib.parse.urlencode(form).encode("ascii")
    req = urllib.request.Request(TOKEN_URL, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = {"raw": "unparseable error body"}
        raise OAuthRefreshError(
            f"Google rejected the refresh token "
            f"(HTTP {e.code}: {err_body.get('error')}). "
            f"Re-run the browser login to restore the runner."
        ) from e
    if not isinstance(body, dict):
        raise OAuthRefreshError(
            "token refresh returned a non-object. "
            "Re-run the browser login to restore the runner.")
    token = body.get("access_token")
    if not isinstance(token, str) or not token:
        raise OAuthRefreshError(
            f"token refresh returned no access_token: {body}. "
            f"Re-run the browser login to restore the runner."
        )
    return token


class _Catch(BaseHTTPRequestHandler):
    code = None
    error = None
    expected_state = None

    def do_GET(self):
        q = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(q)
        if params.get("state", [None])[0] != _Catch.expected_state:
            # Not the callback this wait is for: a favicon, a
            # browser preconnect that turned into a GET, or a
            # stale tab's redirect from an earlier attempt (its
            # state belongs to a consent that no longer exists).
            # Answer it and keep waiting -- the one-shot version
            # of this handler let the first such hit end the
            # sign-in, and the real redirect had nowhere to land.
            self._page("Still waiting for the sign-in in progress.")
            return
        if "code" in params:
            _Catch.code = params["code"][0]
            self._page("Signed in. You can close this window.")
        elif "error" in params:
            _Catch.error = params["error"][0]
            self._page(f"Sign-in failed: {_Catch.error}")
        else:
            self._page("Still waiting for the sign-in in progress.")

    def _page(self, text: str):
        body = f"<html><body><p>{text}</p></body></html>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def build_authorize_url(cfg, verifier, challenge, state) -> str:
    """Authorize URL for the browser. Does not open one."""
    client_id = (cfg or {}).get("oauth_client_id") or ""
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code(cfg, code, verifier, opener=None) -> str:
    """Trade an authorization code for a refresh token.

    opener, when set, is called like urlopen(request, timeout=30).
    A bad body or an HTTP error is SystemExit, not a second parse error.
    """
    client_id = (cfg or {}).get("oauth_client_id") or ""
    form = {
        "client_id": client_id,
        "code": code,
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }
    secret = (cfg or {}).get("oauth_client_secret") or ""
    if isinstance(secret, str) and secret:
        form["client_secret"] = secret
    data = urllib.parse.urlencode(form).encode("ascii")
    req = urllib.request.Request(TOKEN_URL, data=data)
    open_fn = opener or urllib.request.urlopen
    try:
        with open_fn(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = {"raw": "unparseable error body"}
        detail = err_body.get("error") if isinstance(err_body, dict) else err_body
        desc = err_body.get("error_description") if isinstance(err_body, dict) else ""
        msg = f"token exchange failed (HTTP {e.code}: {detail})"
        if desc and desc != detail:
            msg += f": {desc}"
        raise SystemExit(msg) from e
    except json.JSONDecodeError as e:
        raise SystemExit("token exchange returned unparseable JSON") from e
    if not isinstance(body, dict):
        raise SystemExit(f"token exchange returned a non-object: {body}")
    refresh = body.get("refresh_token")
    if not isinstance(refresh, str) or not refresh:
        raise SystemExit(f"no refresh_token in response: {body}")
    return refresh


_CONSENT_WAIT_SEC = 300
_ACCEPT_POLL_SEC = 0.5
_REQUEST_READ_TIMEOUT_SEC = 5.0


class _ConsentServer(HTTPServer):
    """The redirect listener, hardened against the field failures
    of 2026-10-22: an accepted connection gets a read deadline, so
    a browser preconnect that never sends a request cannot block
    the wait forever, and a failed read is dropped quietly
    instead of printing a handler traceback over the wizard."""

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(_REQUEST_READ_TIMEOUT_SEC)
        return request, address

    def handle_error(self, request, client_address):
        return


def browser_consent(cfg: dict) -> str:
    """Open the system browser and return a refresh token. Blocks.

    Serves the redirect port until the callback for THIS consent
    arrives (matched by state) or the wait expires. Requests that
    are not that callback -- favicons, preconnects, stale tabs
    from earlier attempts -- are answered and ignored; the
    one-shot listener this replaces let the first of those end
    the sign-in, and its stuck accept thread then held the port
    so the setup's retry died with "address already in use".
    The wait runs in the calling thread and the server is closed
    on every exit, so the port is free for a retry.
    """
    client_id = cfg.get("oauth_client_id") or ""
    if not client_id:
        raise SystemExit("config error: oauth_client_id is required for auth=oauth")
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(16)
    url = build_authorize_url(cfg, verifier, challenge, state)
    _Catch.code = None
    _Catch.error = None
    _Catch.expected_state = state
    server = _ConsentServer(("127.0.0.1", REDIRECT_PORT), _Catch)
    server.timeout = _ACCEPT_POLL_SEC
    print("Opening the browser for Google sign-in.")
    print("If it does not open, paste this URL yourself:")
    print(url)
    webbrowser.open(url)
    deadline = time.monotonic() + _CONSENT_WAIT_SEC
    try:
        while _Catch.code is None and _Catch.error is None \
                and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if _Catch.error:
        raise SystemExit(f"Google sign-in failed: {_Catch.error}")
    if not _Catch.code:
        raise SystemExit("no sign-in code received (timed out or browser closed)")
    return exchange_code(cfg, _Catch.code, verifier, opener=None)


def store_refresh_token(path, cfg, refresh):
    """Write the refresh token. A symlink is not followed.

    The file is mode 0600. The token must be one line so it cannot
    break the JSON writer or smuggle a second record.
    """
    if not isinstance(path, str) or not path:
        raise ValueError("config path is required")
    if os.path.islink(path):
        raise OSError("refusing to follow a symlink config")
    if not isinstance(cfg, dict):
        raise TypeError("config must be an object")
    if not isinstance(refresh, str) or not refresh or any(
            ch in refresh for ch in ("\n", "\r", "\x00")):
        raise ValueError("refresh token must be a single line")
    saved = dict(cfg)
    saved["auth"] = "oauth"
    saved["oauth_refresh_token"] = refresh
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    _atomicio.write_json(path, saved, indent=2, newline=True)
    return saved


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Sign the runner into Gmail the way Thunderbird does: "
                    "browser window, no password on the command line.")
    ap.add_argument("--version", action="version",
                    version="%(prog)s " + __version__)
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()
    print(f"oauth {__version__}")
    if os.path.islink(args.config):
        print("config error: refusing to follow a symlink", file=sys.stderr)
        return 2
    with open(args.config, encoding="utf-8") as fh:
        cfg = json.load(fh)
    refresh = browser_consent(cfg)
    try:
        store_refresh_token(args.config, cfg, refresh)
    except (OSError, ValueError, TypeError) as exc:
        print("config error: %s" % exc, file=sys.stderr)
        return 2
    print(f"wrote refresh token to {args.config}")
    print("The Google password is not in this file. Start the runner.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
