#!/usr/bin/env python3
"""Thunderbird-style first-run setup for the runner.

When the app starts without working mailbox auth, it offers this
wizard instead of dying with "config error". Browser sign-in
(OAuth, the way Thunderbird does it), a fresh shared secret shown
once for the owner to accept, config written. Automation stays
safe: every prompt is TTY-gated, so headless runs fail fast exactly
as before.

A third choice (CS_canoe's option 3) pairs the same browser
sign-in with an autogen shared secret: when the owner agrees, the
secret is generated locally at random, written to the config, and
emailed to the mailbox itself as the install record, so the inbox
holds the record of the install. The sign-in runs under the
project's own OAuth client by default, so the owner is never
asked to paste a client ID; a client ID already in the config
still wins.

Entry points: `runner.py --setup`, the auto-offer in `main()` when
auth is missing/broken, and `install.py` after the shared-secret
step. One implementation for all three.
"""
# Python 3.9 is the floor (pyproject): PEP 604 unions in annotations
# must not be evaluated at definition time. Found by the platform
# matrix on Rocky 9 and python:3.9; see runner/tests/test_build_config.py.
from __future__ import annotations
import getpass
import imaplib
import json
import os
import platform
import secrets
import shutil
import socket
import ssl
import sys

try:
    from runner.guard import atomicio as _atomicio
except ImportError:  # running from inside runner/ as __main__
    from guard import atomicio as _atomicio  # type: ignore

try:
    from runner.ops import identity as _identity
except ImportError:  # running from inside runner/ as __main__
    try:
        from ops import identity as _identity  # type: ignore
    except ImportError:
        _identity = None

try:
    from runner.wire.oauth import browser_consent, refresh_access_token
except ImportError:  # running from inside runner/ as __main__
    try:
        from wire.oauth import browser_consent, refresh_access_token
    except ImportError:
        browser_consent = None
        refresh_access_token = None

try:
    from runner.ops.install import _looks_like_placeholder as _placeholder
    from runner.ops.install import _looks_patterned as _patterned
    from runner.ops.install import platform_modes as _platform_modes
    from runner.ops.install import (
        fresh_platform_modes as _fresh_platform_modes,
        fresh_job_user as _fresh_job_user,
        seed_kept_lines as _seed_kept_lines,
        seed_reason as _seed_reason)
except ImportError:
    try:
        from ops.install import _looks_like_placeholder as _placeholder
        from ops.install import _looks_patterned as _patterned
        from ops.install import platform_modes as _platform_modes
        from ops.install import (
            fresh_platform_modes as _fresh_platform_modes,
            fresh_job_user as _fresh_job_user,
            seed_kept_lines as _seed_kept_lines,
            seed_reason as _seed_reason)
    except ImportError:
        _placeholder = _patterned = None
        _platform_modes = None
        _fresh_platform_modes = _fresh_job_user = None
        _seed_kept_lines = _seed_reason = None


def is_tty() -> bool:
    return sys.stdin.isatty()


def _use_oauth(cfg: dict) -> bool:
    return str(cfg.get("auth") or "password").lower() == "oauth"


# The values runner/config.example.json seeds. A config still holding
# one was copied and never filled in: it is unset, so the installer
# offers sign-in on a fresh install (Q98 item 4).
EXAMPLE_PLACEHOLDERS = {
    "mailbox_user": "homing-pigeon-runner@gmail.com",
    "mailbox_password": "paste-app-password-here-in-plaintext",
}

# The Homing Pigeon Org's desktop OAuth client, baked in whole —
# ID and secret together — so the option-3 sign-in never asks the
# owner to paste or type anything: the wizard goes directly to
# the browser, Thunderbird-style. Thunderbird ships its own
# desktop client exactly this way, because an installed app
# cannot keep its client's secret from the person holding the
# app; the secret is therefore not a credential this design
# leans on (the mailbox's safety rests on the owner's own Google
# sign-in and the refresh token it grants). Google still
# requires the secret at the token exchange, so it rides here
# beside the ID. A client ID or a client secret already present
# in the config still wins over these defaults (see
# _ensure_oauth_client_secret).
DEFAULT_OAUTH_CLIENT_ID = (
    "40959958324-1q02ndgro7dr4gj8gm5gr4bi8g3f1064"
    ".apps.googleusercontent.com"
)

DEFAULT_OAUTH_CLIENT_SECRET = (
    "GOCSPX-ntL2RE4c2I8qzlxrZz9"
    "pRGEI3D1S"
)

INSTALL_RECORD_SUBJECT = (
    "Homing Pigeon shared secret installed on this system"
)


def _set(cfg, key):
    value = cfg.get(key)
    return bool(value) and value != EXAMPLE_PLACEHOLDERS.get(key)


def needs_setup(cfg: dict) -> str | None:
    """Reason mailbox auth cannot work, or None when it can."""
    if not isinstance(cfg, dict):
        return "config is not an object"
    if not _set(cfg, "mailbox_user"):
        return "mailbox_user is not set"
    if _use_oauth(cfg):
        if not cfg.get("oauth_client_id"):
            return "oauth_client_id is not set"
        if not cfg.get("oauth_refresh_token"):
            return "no OAuth refresh token (sign-in never completed)"
        return None
    if not _set(cfg, "mailbox_password"):
        return "mailbox_password is not set"
    return None


def mailbox_gate_reason(cfg: dict, transports) -> str | None:
    """The startup gate's reason, or None when startup may proceed.

    The gate guards mailbox auth, so it applies only when the
    email transport is enabled. A runner with the email transport
    off (a file-transport-only box) has no mailbox to set up: the
    gate firing there sat the Germany rig's first boot forever at
    a setup prompt for a mailbox it will never use (2026-10-31).
    transports=None (the enabled set could not be read) keeps the
    gate: fail toward asking, and the transport error itself is
    reported by its own check later in startup.
    """
    if transports is not None and "email" not in transports:
        return None
    return needs_setup(cfg)


def prompt_yes_no(text: str, default: bool = True) -> bool:
    """Yes/no prompt. Default shown in caps. EOF counts as the default."""
    try:
        answer = input(text).strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


def _example_candidates():
    """Where a shipped config.example.json might be.

    Source checkouts keep it next to this file. A Windows zip keeps it
    next to homing-pigeon.exe. A frozen build may also unpack it under
    _MEIPASS. The first readable file wins.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    found = [os.path.join(here, "config.example.json")]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        found.append(os.path.join(meipass, "config.example.json"))
        found.append(os.path.join(meipass, "runner", "config.example.json"))
    exe = getattr(sys, "executable", "") or ""
    if exe:
        found.append(os.path.join(os.path.dirname(os.path.abspath(exe)),
                                  "config.example.json"))
    found.append(os.path.join(os.getcwd(), "config.example.json"))
    return found


def _load_example() -> dict:
    for path in _example_candidates():
        try:
            with open(path, encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(cfg, dict):
            return cfg
    # The onefile binary does not contain the example unless the zip
    # put it beside the exe. Gmail endpoints still have to be present
    # or the first poll raises KeyError.
    return {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "poll_interval_sec": 20,
        "max_output_bytes": 100000,
        "max_job_age_sec": 3600,
        "workers": 1,
        "auth": "password",
    }


def _blank_config() -> dict:
    """Start from the example config when it ships alongside us."""
    cfg = _load_example()
    # Example ships with placeholder secrets and an example address;
    # the wizard fills real ones below.
    cfg.pop("shared_secret", None)
    cfg.pop("mailbox_user", None)
    cfg.pop("mailbox_password", None)
    cfg.pop("oauth_refresh_token", None)
    return cfg


def seed_platform_modes(cfg: dict, platform=None, probe=None,
                        asked=None, trial=None, account=None) -> dict:
    """State the platform gates in a config the wizard just seeded.

    The installer states them on its fresh-install path (install.py's
    apply_platform_modes); a config seeded here -- the runner started
    with no config file, the wizard creating one from the example --
    takes the same statement, from the same platform map, so a first
    start on a platform where a mechanism cannot engage is not a
    refusal the owner must edit their way out of. Only a mode still
    at enforce moves; that is the seed's value. An existing config
    the wizard is merely completing is never rewritten by this: the
    caller applies it only to a config that came from _blank_config.
    Returns the modes actually stated.

    The same statement includes the one that asks the machine:
    on a FreeBSD host the jail backend's probe is asked the
    startup gate's question, and on a macOS host the macOS
    backend's (install.py's fresh_platform_modes), and where
    it passes confinement is not stated down. On FreeBSD a
    job user is named for the jail's jobs as well, where the
    config names none (install.py's fresh_job_user). This seed writes
    a config and nothing else, so it makes no account: it
    names the jobs' own account where the machine already has
    it, and the shared user where it does not. `probe`, `trial`
    and `account` are the tests' doors, as they are there.
    `asked`, when a list is handed in, receives what the
    machine was asked and answered -- (answer, user, door): the
    probe's answer, the job user named or None, and the record
    of the second question or None -- so the caller can say
    what was decided and why.
    """
    if _platform_modes is None or not isinstance(cfg, dict):
        return {}
    user = None
    if _fresh_platform_modes is not None:
        modes, answer = _fresh_platform_modes(cfg, platform, probe)
        door = None
        if _fresh_job_user is not None:
            user, door = _fresh_job_user(cfg, answer, platform, trial,
                                         account, make=False)
        if answer is not None and asked is not None:
            asked.append((answer, user, door))
    else:
        modes = _platform_modes(platform)
    sec = cfg.get("security") if isinstance(cfg.get("security"), dict) \
        else {}
    cur = sec.get("modes") if isinstance(sec.get("modes"), dict) else {}
    new_modes = dict(cur)
    applied = {}
    for feature, mode in modes.items():
        if cur.get(feature, "enforce") == "enforce":
            new_modes[feature] = mode
            applied[feature] = mode
    if not applied and user is None:
        return {}
    sec = dict(sec)
    if applied:
        sec["modes"] = new_modes
    if user is not None:
        sec["job_user"] = {"user": user}
    cfg["security"] = sec
    return applied


def _ensure_mail_hosts(cfg: dict) -> None:
    """Fill Gmail endpoints when a partial config left them out."""
    defaults = {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
    }
    for key, value in defaults.items():
        if not cfg.get(key):
            cfg[key] = value


def _ask(prompt: str) -> str:
    """input() that exits cleanly when there is no console."""
    try:
        return input(prompt).strip()
    except EOFError:
        raise SystemExit("setup needs a console (no input available)")


def _write_config(cfg_path: str, cfg: dict) -> None:
    """Write config.json whole or not at all, mode 0600, a symlink at
    cfg_path replaced rather than written through (guard/atomicio)."""
    if not isinstance(cfg, dict):
        raise TypeError("config must be an object")
    parent = os.path.dirname(os.path.abspath(cfg_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    _atomicio.write_json(cfg_path, cfg, indent=2, newline=True)


def _secret_is_real(secret: str) -> bool:
    if not isinstance(secret, str):
        return False
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
            from runner.wire.oauth import xoauth2_raw
        except ImportError:
            from wire.oauth import xoauth2_raw
        auth_str = xoauth2_raw(cfg["mailbox_user"], token)
        imap.authenticate("XOAUTH2", lambda _: auth_str)  # pyrefly: ignore[bad-argument-type]  # imaplib accepts the str at runtime; typeshed wants bytes
        imap.logout()
        return None
    except Exception as e:
        return f"IMAP login failed: {e}"


def _autogen_login_enabled(cfg: dict) -> bool:
    """Option 3's kill switch (CS_canoe): the autogen sign-in is on
    unless the config says literal false -- the job_encryption
    convention, where a missing key or a string "false" leaves the
    feature on and only a real false turns it off. Options 1 and 2
    are not governed by this key and keep working either way."""
    return cfg.get("autogen_login") is not False


def _gb(num_bytes) -> str:
    try:
        return f"{num_bytes / float(1024 ** 3):.1f} GB"
    except (TypeError, ValueError, OverflowError):
        return "unknown"


def _total_memory() -> str:
    """Total physical memory as a display string; never raises."""
    try:
        if hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            size = os.sysconf("SC_PAGE_SIZE")
            if pages > 0 and size > 0:
                return _gb(pages * size)
    except (ValueError, OSError, AttributeError):
        pass
    try:
        import ctypes

        class _MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(  # type: ignore[attr-defined]
                ctypes.byref(status)):
            return _gb(status.ullTotalPhys)
    except Exception:
        pass
    return "unknown"


def system_facts() -> dict:
    """The install record's facts about this system. Every value is
    a display string; anything that cannot be read is "unknown".
    Never raises: the record is a courtesy, not a gate."""
    try:
        hostname = socket.gethostname() or "unknown"
    except Exception:
        hostname = "unknown"
    try:
        ip_address = socket.gethostbyname(hostname)
    except Exception:
        ip_address = "unknown"
    try:
        disk = _gb(shutil.disk_usage(os.path.expanduser("~")).total)
    except Exception:
        disk = "unknown"
    return {
        "platform": platform.platform() or "unknown",
        "hostname": hostname,
        "ip_address": ip_address,
        "memory": _total_memory(),
        "hard_drive": disk,
    }


def install_record_body(secret: str, facts: dict | None = None) -> str:
    """The install-record note's body: the shared secret, then the
    facts of the system it was installed on."""
    if facts is None:
        facts = system_facts()
    lines = [
        INSTALL_RECORD_SUBJECT,
        "",
        f"Shared secret: {secret}",
        "",
        f"Platform: {facts['platform']}",
        f"Hostname: {facts['hostname']}",
        f"IP address: {facts['ip_address']}",
        f"Memory: {facts['memory']}",
        f"Hard drive: {facts['hard_drive']}",
        "",
        "Keep this note: it is the record of this install, and the",
        "shared secret in it is the one the runner signs with.",
    ]
    return "\n".join(lines) + "\n"


def _email_install_record(cfg: dict, secret: str) -> str | None:
    """Email the install record to the mailbox itself, through the
    sign-in that just completed (send_mail defaults To to the
    mailbox's own address). Returns an error string, or None on
    success. Non-fatal by design, like the mailbox probe: a failed
    record email must not block a completed setup."""
    try:
        try:
            from runner.wire.mailbox import connect_smtp, send_mail
        except ImportError:
            from wire.mailbox import connect_smtp, send_mail
        smtp = connect_smtp(cfg)
        try:
            send_mail(smtp, cfg, INSTALL_RECORD_SUBJECT,
                      install_record_body(secret))
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
        return None
    except Exception as e:
        return f"install record email failed: {e}"


def run_setup_wizard(cfg_path: str, cfg: dict | None = None) -> dict:
    """Interactive first-run / re-login setup. Returns the new config.

    Creates the config from the example when missing, signs in with
    Google in the browser (or takes an app password), shows a fresh
    shared secret once for the owner to accept, writes the file.
    """
    if browser_consent is None:
        raise SystemExit("setup needs runner/wire/oauth.py on the path")
    if cfg is None:
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (OSError, ValueError):
            cfg = None
    fresh_seed = False
    if not isinstance(cfg, dict):
        cfg = _blank_config()
        fresh_seed = True
    _ensure_mail_hosts(cfg)

    # The build identity opens the wizard, at CRITICAL, before
    # the header: version, platform, build stamp and checksum
    # (runner/ops/identity.py), once per process.
    if _identity is not None:
        _identity.announce("runner.ops.setup")

    print("=== Homing Pigeon setup ===")
    print("Thunderbird-style sign-in: a browser window, no password on")
    print("the command line. The Google password never lands in config.")

    # 1. The dedicated mailbox address. Coerced to str: a poisoned
    # config may hold a non-string here, which must not crash .strip().
    while not str(cfg.get("mailbox_user") or "").strip():
        cfg["mailbox_user"] = _ask(
            "Gmail address for the runner's dedicated mailbox: ")
    user = str(cfg["mailbox_user"]).strip()
    cfg["mailbox_user"] = user

    # 2. Auth. Already working? Offer a re-login, nothing else.
    autogen = False
    if needs_setup(cfg) is None and cfg.get("oauth_refresh_token"):
        if prompt_yes_no("Already signed in. Sign in again anyway? [y/N] ",
                         default=False):
            cfg["oauth_refresh_token"] = _browser_login_loop(cfg)
    else:
        print("[1] Sign in with Google (browser, recommended)")
        print("[2] Use a Gmail app password")
        print("[3] Sign in with Google and generate a shared secret")
        choice = _ask("Choice [1]: ")
        if choice == "2":
            cfg["auth"] = "password"
            cfg.pop("oauth_refresh_token", None)
            try:
                cfg["mailbox_password"] = getpass.getpass(
                    "Gmail app password (stored in config.json): ")
            except EOFError:
                raise SystemExit("setup needs a console (no input available)")
        else:
            cfg["auth"] = "oauth"
            cfg.pop("mailbox_password", None)
            if choice == "3":
                if not _autogen_login_enabled(cfg):
                    print("Sorry, option 3 is turned off in this "
                          "config, so it is not available right now.")
                    print("Continuing with the plain browser sign-in.")
                else:
                    autogen = True
                    if not cfg.get("oauth_client_id"):
                        cfg["oauth_client_id"] = DEFAULT_OAUTH_CLIENT_ID
                        print("Signing in with the Homing Pigeon "
                              "client; no client ID to paste.")
            if not cfg.get("oauth_client_id"):
                print("One-time: Google Cloud Console -> APIs & Services ->")
                print("Credentials -> Create OAuth client ID -> Desktop app,")
                print("then add http://127.0.0.1:8765/ as a redirect URI.")
                while not str(cfg.get("oauth_client_id") or "").strip():
                    cfg["oauth_client_id"] = _ask("OAuth client ID: ")
            cfg["oauth_refresh_token"] = _browser_login_loop(cfg)
            # The token belongs to whoever just signed in; make sure the
            # address matches before we go further.
            probe = _mailbox_probe(cfg)
            if probe:
                print(f"warning: {probe}", file=sys.stderr)
                print("Continuing anyway; check the address and try again "
                      "with --setup if mail fails.")

    # 3. Shared secret: show the new one once, let the owner accept it.
    #    On the option-3 path with no secret yet, offer to generate
    #    one instead: generated locally at random, never shown on
    #    the console, and carried to the owner by the install-record
    #    email below.
    record_secret = None
    if _secret_is_real(cfg.get("shared_secret") or ""):
        if not prompt_yes_no(
                "A shared secret is already set. Replace it with a new "
                "one? [y/N] ", default=False):
            print("keeping the existing shared secret")
        else:
            cfg["shared_secret"] = _accept_secret()
    elif autogen and prompt_yes_no(
            "You don't have a shared secret. Do you want to generate "
            "one? [Y/n] "):
        cfg["shared_secret"] = secrets.token_hex(32)  # 256-bit, as install.py
        record_secret = cfg["shared_secret"]
    else:
        cfg["shared_secret"] = _accept_secret()

    # Hardening M5: a fresh config gets a runner_id (the audience that
    # signed jobs must claim). Existing configs keep theirs; hand-made
    # configs without one simply skip audience binding.
    if not cfg.get("runner_id"):
        cfg["runner_id"] = secrets.token_hex(16)
        # The audience a job must name. Not a key.
        # codeql[py/clear-text-logging-sensitive-data]
        print(f"generated runner_id: {cfg['runner_id']}")
    if fresh_seed:
        # A config this wizard seeded states the platform gates the
        # way the installer's fresh-install path states them: a
        # mechanism that cannot engage on this platform is written
        # at audit, in the file and out loud here, rather than left
        # at the seed's enforce to refuse the first start. A config
        # that already existed keeps the owner's stated modes.
        # On FreeBSD and on macOS the statement is the machine's
        # answer: the backend's probe is asked here, and a pass
        # leaves confinement at enforce and says so; on FreeBSD
        # it names a job user for the jail's jobs as well.
        answers = []
        stated = seed_platform_modes(cfg, asked=answers)
        answer, user, door = answers[0] if answers \
            else (None, None, None)
        if _seed_kept_lines is not None:
            for line in _seed_kept_lines(answer, cfg_path, user, door):
                print(line)
        for feature, mode in stated.items():
            why = f"{feature} cannot engage on {sys.platform}"
            if _seed_reason is not None:
                why = _seed_reason(answer, feature, why)
            print(f"platform: security.modes.{feature} stated as "
                  f"{mode} in {cfg_path} ({why}; the mode is "
                  f"stated in the file rather than left to refuse "
                  f"the first start)")
    _write_config(cfg_path, cfg)
    print(f"\nwrote {cfg_path} (owner read/write only)")
    if record_secret is not None:
        err = _email_install_record(cfg, record_secret)
        if err:
            print(f"warning: {err}", file=sys.stderr)
            print("The install record could not be emailed; the "
                  "shared secret is in the config file above. Keep "
                  "it safe.")
        else:
            print("Install record emailed to your mailbox: it holds "
                  "the shared secret and the record of this install.")
            print("Give the shared secret in that note to your cloud "
                  "SI so it can sign jobs.")
    else:
        print("Give the shared secret above to your cloud SI so it can sign jobs.")
    print("Start the runner; it will poll the mailbox now.")
    return cfg


def _ensure_oauth_client_secret(cfg: dict) -> None:
    """The client secret the token exchange cannot finish without.

    Google requires the desktop client's secret at the code
    exchange (and at refresh). The wizard never asks for it: the
    Homing Pigeon client's secret is baked in beside its ID
    (DEFAULT_OAUTH_CLIENT_SECRET, Thunderbird-style), and this
    step fills it in before the browser opens, so the sign-in
    goes directly to the browser with nothing to paste or type.
    A secret already in the config — the owner's own client, an
    earlier run — still wins and is left exactly as it stands;
    a missing or whitespace-only value takes the default. (The
    first remedy for the option-3 first-run failure of
    2026-11-14 asked once, hidden, at this seam; the conductor's
    design carries the secret in the client instead, so there
    is no prompt to answer and no typed value to mistype.)
    """
    if str(cfg.get("oauth_client_secret") or "").strip():
        return
    cfg["oauth_client_secret"] = DEFAULT_OAUTH_CLIENT_SECRET


def _browser_login_loop(cfg: dict) -> str:
    """browser_consent with a retry offer instead of a traceback."""
    _ensure_oauth_client_secret(cfg)
    while True:
        try:
            return browser_consent(cfg)  # pyrefly: ignore[not-callable]  # None only if oauth.py is absent, which cannot happen in a real install
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
