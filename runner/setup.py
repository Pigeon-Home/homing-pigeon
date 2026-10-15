#!/usr/bin/env python3
"""Thunderbird-style first-run setup for the runner.

When the app starts without working mailbox auth, it offers this
wizard instead of dying with "config error". Browser sign-in
(OAuth, the way Thunderbird does it), a fresh shared secret shown
once for the owner to accept, config written. Automation stays
safe: every prompt is TTY-gated, so headless runs fail fast exactly
as before.

Entry points: `runner.py --setup`, the auto-offer in `main()` when
auth is missing/broken, and `install.py` after the shared-secret
step. One implementation for all three.
"""
import getpass
import imaplib
import json
import os
import secrets
import ssl
import sys

try:
    from runner.oauth import browser_consent, refresh_access_token
except ImportError:  # running from inside runner/ as __main__
    try:
        from oauth import browser_consent, refresh_access_token
    except ImportError:
        browser_consent = None
        refresh_access_token = None

try:
    from runner.install import _looks_like_placeholder as _placeholder
    from runner.install import _looks_patterned as _patterned
except ImportError:
    try:
        from install import _looks_like_placeholder as _placeholder
        from install import _looks_patterned as _patterned
    except ImportError:
        _placeholder = _patterned = None


def is_tty() -> bool:
    return sys.stdin.isatty()


def _use_oauth(cfg: dict) -> bool:
    return str(cfg.get("auth") or "password").lower() == "oauth"


def needs_setup(cfg: dict) -> str | None:
    """Reason mailbox auth cannot work, or None when it can."""
    if not isinstance(cfg, dict):
        return "config is not an object"
    if not cfg.get("mailbox_user"):
        return "mailbox_user is not set"
    if _use_oauth(cfg):
        if not cfg.get("oauth_client_id"):
            return "oauth_client_id is not set"
        if not cfg.get("oauth_refresh_token"):
            return "no OAuth refresh token (sign-in never completed)"
        return None
    if not cfg.get("mailbox_password"):
        return "mailbox_password is not set"
    return None


def prompt_yes_no(text: str, default: bool = True) -> bool:
    """Yes/no prompt. Default shown in caps. EOF counts as the default."""
    try:
        answer = input(text).strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


def _blank_config() -> dict:
    """Start from the example config when it ships alongside us."""
    example = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "config.example.json")
    try:
        with open(example, encoding="utf-8") as fh:
            cfg = json.load(fh)
        if isinstance(cfg, dict):
            # Example ships with placeholder secrets and an example
            # address; the wizard fills real ones below.
            cfg.pop("shared_secret", None)
            cfg.pop("mailbox_user", None)
            cfg.pop("mailbox_password", None)
            cfg.pop("oauth_refresh_token", None)
            return cfg
    except (OSError, ValueError):
        pass
    return {}


def _write_config(cfg_path: str, cfg: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(cfg_path)), exist_ok=True)
    tmp = cfg_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, cfg_path)
    try:
        os.chmod(cfg_path, 0o600)
    except OSError:
        pass  # Windows: ACLs come from the parent directory


def _secret_is_real(secret: str) -> bool:
    if not secret:
        return False
    if _placeholder and _placeholder(secret):
        return False
    if _patterned and _patterned(secret):
        return False
    return True


def _mailbox_probe(cfg: dict) -> str | None:
    """Quick IMAP login check. Returns an error string, or None if ok.

    Non-fatal by design: a restricted network should not block setup.
    """
    if refresh_access_token is None:
        return "oauth helper unavailable"
    try:
        token = refresh_access_token(cfg)
    except Exception as e:
        return f"token refresh failed: {e}"
    try:
        ctx = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ctx)
        try:
            from runner.oauth import xoauth2_raw
        except ImportError:
            from oauth import xoauth2_raw
        auth_str = xoauth2_raw(cfg["mailbox_user"], token)
        imap.authenticate("XOAUTH2", lambda _: auth_str)
        imap.logout()
        return None
    except Exception as e:
        return f"IMAP login failed: {e}"


def run_setup_wizard(cfg_path: str, cfg: dict | None = None) -> dict:
    """Interactive first-run / re-login setup. Returns the new config.

    Creates the config from the example when missing, signs in with
    Google in the browser (or takes an app password), shows a fresh
    shared secret once for the owner to accept, writes the file.
    """
    if browser_consent is None:
        raise SystemExit("setup needs runner/oauth.py on the path")
    if cfg is None:
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (OSError, ValueError):
            cfg = None
    if not isinstance(cfg, dict):
        cfg = _blank_config()

    print("=== Homing Pigeon setup ===")
    print("Thunderbird-style sign-in: a browser window, no password on")
    print("the command line. The Google password never lands in config.")

    # 1. The dedicated mailbox address.
    while not (cfg.get("mailbox_user") or "").strip():
        cfg["mailbox_user"] = input(
            "Gmail address for the runner's dedicated mailbox: ").strip()
    user = cfg["mailbox_user"].strip()
    cfg["mailbox_user"] = user

    # 2. Auth. Already working? Offer a re-login, nothing else.
    if needs_setup(cfg) is None and cfg.get("oauth_refresh_token"):
        if prompt_yes_no("Already signed in. Sign in again anyway? [y/N] ",
                         default=False):
            cfg["oauth_refresh_token"] = _browser_login_loop(cfg)
    else:
        print("[1] Sign in with Google (browser, recommended)")
        print("[2] Use a Gmail app password")
        choice = input("Choice [1]: ").strip()
        if choice == "2":
            cfg["auth"] = "password"
            cfg.pop("oauth_refresh_token", None)
            cfg["mailbox_password"] = getpass.getpass(
                "Gmail app password (stored in config.json): ")
        else:
            cfg["auth"] = "oauth"
            cfg.pop("mailbox_password", None)
            if not cfg.get("oauth_client_id"):
                print("One-time: Google Cloud Console -> APIs & Services ->")
                print("Credentials -> Create OAuth client ID -> Desktop app,")
                print("then add http://127.0.0.1:8765/ as a redirect URI.")
                while not (cfg.get("oauth_client_id") or "").strip():
                    cfg["oauth_client_id"] = input(
                        "OAuth client ID: ").strip()
            cfg["oauth_refresh_token"] = _browser_login_loop(cfg)
            # The token belongs to whoever just signed in; make sure the
            # address matches before we go further.
            probe = _mailbox_probe(cfg)
            if probe:
                print(f"warning: {probe}", file=sys.stderr)
                print("Continuing anyway; check the address and try again "
                      "with --setup if mail fails.")

    # 3. Shared secret: show the new one once, let the owner accept it.
    if _secret_is_real(cfg.get("shared_secret") or ""):
        if not prompt_yes_no(
                "A shared secret is already set. Replace it with a new "
                "one? [y/N] ", default=False):
            print("keeping the existing shared secret")
        else:
            cfg["shared_secret"] = _accept_secret()
    else:
        cfg["shared_secret"] = _accept_secret()

    _write_config(cfg_path, cfg)
    print(f"\nwrote {cfg_path} (owner read/write only)")
    print("Give the shared secret above to your cloud SI so it can sign jobs.")
    print("Start the runner; it will poll the mailbox now.")
    return cfg


def _browser_login_loop(cfg: dict) -> str:
    """browser_consent with a retry offer instead of a traceback."""
    while True:
        try:
            return browser_consent(cfg)
        except SystemExit as e:
            print(f"sign-in failed: {e}", file=sys.stderr)
            if not prompt_yes_no("Try again? [Y/n] "):
                raise SystemExit(2)


def _accept_secret() -> str:
    """Generate, display, and get explicit acceptance for a secret."""
    while True:
        new = secrets.token_hex(32)  # 256-bit, matches install.py
        print("\nNew shared secret -- give this string to your cloud SI:")
        print(f"  {new}\n")
        if prompt_yes_no("Accept this shared secret? [Y/n] "):
            return new
        print("generating another...")


if __name__ == "__main__":
    ap_cfg = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    run_setup_wizard(ap_cfg)
