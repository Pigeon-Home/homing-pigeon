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
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://mail.google.com/"
REDIRECT_PORT = 8765
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/"


def xoauth2_raw(user: str, access_token: str) -> str:
    """SASL XOAUTH2 initial response, unencoded.

    Both libraries base64 this themselves. Pre-encoding it is the bug:
    the server then sees a blob of a blob and rejects it.
    """
    return f"user={user}\x01auth=Bearer {access_token}\x01\x01"


def _pkce() -> tuple:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def refresh_access_token(cfg: dict) -> str:
    """Trade the stored refresh token for a short-lived access token."""
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
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    token = body.get("access_token")
    if not token:
        raise RuntimeError(f"token refresh returned no access_token: {body}")
    return token


class _Catch(BaseHTTPRequestHandler):
    code = None
    error = None

    def do_GET(self):
        q = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(q)
        if "code" in params:
            _Catch.code = params["code"][0]
            self._page("Signed in. You can close this window.")
        else:
            _Catch.error = params.get("error", ["unknown"])[0]
            self._page(f"Sign-in failed: {_Catch.error}")

    def _page(self, text: str):
        body = f"<html><body><p>{text}</p></body></html>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        return


def browser_consent(cfg: dict) -> str:
    """Open the system browser and return a refresh token. Blocks."""
    client_id = cfg.get("oauth_client_id") or ""
    if not client_id:
        raise SystemExit("config error: oauth_client_id is required for auth=oauth")
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(16)
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
    url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    _Catch.code = None
    _Catch.error = None
    server = HTTPServer(("127.0.0.1", REDIRECT_PORT), _Catch)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    print("Opening the browser for Google sign-in.")
    print("If it does not open, paste this URL yourself:")
    print(url)
    webbrowser.open(url)
    thread.join(timeout=300)
    server.server_close()
    if _Catch.error:
        raise SystemExit(f"Google sign-in failed: {_Catch.error}")
    if not _Catch.code:
        raise SystemExit("no sign-in code received (timed out or browser closed)")
    form = {
        "client_id": client_id,
        "code": _Catch.code,
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }
    secret = cfg.get("oauth_client_secret") or ""
    if secret:
        form["client_secret"] = secret
    data = urllib.parse.urlencode(form).encode("ascii")
    req = urllib.request.Request(TOKEN_URL, data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    refresh = body.get("refresh_token")
    if not refresh:
        raise SystemExit(f"no refresh_token in response: {body}")
    return refresh


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Sign the runner into Gmail the way Thunderbird does: "
                    "browser window, no password on the command line.")
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as fh:
        cfg = json.load(fh)
    refresh = browser_consent(cfg)
    cfg["auth"] = "oauth"
    cfg["oauth_refresh_token"] = refresh
    with open(args.config, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")
    print(f"wrote refresh token to {args.config}")
    print("The Google password is not in this file. Start the runner.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
