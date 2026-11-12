#!/usr/bin/env python3
"""
Install the homing-pigeon runner as a boot-start service.

Detects the platform and installs the native mechanism:
  Windows : Scheduled Task (schtasks, runs at startup as SYSTEM)
  Linux   : systemd user unit (or --system for a system unit)
  macOS   : launchd agent (~/Library/LaunchAgents)
  FreeBSD : cron @reboot entry (native rc.d also works; cron is simpler)

Usage:
    python3 install.py [--dir DIR] [--config CONFIG] [--system] [--uninstall]
"""
# Python 3.9 is the floor (pyproject): PEP 604 unions in annotations
# must not be evaluated at definition time. Found by the platform
# matrix on Rocky 9 and python:3.9; see runner/tests/test_build_config.py.
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import math
import threading
import time
import zipfile
from xml.sax.saxutils import escape


def _load_by_path(path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("hp_atomicio", path)
    if spec is None or spec.loader is None:
        raise ImportError("%s not loadable" % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _import_atomicio():
    """runner/guard/atomicio.py, whichever way this file is running.

    The frozen installer first: it carries the file as data
    (`--add-data runner/guard/atomicio.py`), because importing it as
    `runner.guard.atomicio` would run `runner/__init__.py`, which
    imports the whole runner -- more than the installer bundles.
    Then the package (`runner.guard`), the install layout (`guard`
    beside `ops`), and this script started by path from a source
    tree.
    """
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        cand = os.path.join(frozen, "pigeon-guard", "atomicio.py")
        if os.path.isfile(cand):
            return _load_by_path(cand)
        # The frozen runner imports this module too; it bundles the
        # whole package, so the import below is the one that works.
    try:
        from runner.guard import atomicio
        return atomicio
    except ImportError:
        pass
    try:
        from guard import atomicio  # type: ignore
        return atomicio
    except ImportError:
        pass
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return _load_by_path(os.path.join(here, "guard", "atomicio.py"))


_atomicio = _import_atomicio()


def _import_panic():
    """runner/guard/panic.py (Q100), the same four ways as atomicio."""
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        cand = os.path.join(frozen, "pigeon-guard", "panic.py")
        if os.path.isfile(cand):
            return _load_by_path(cand)
    try:
        from runner.guard import panic
        return panic
    except ImportError:
        pass
    try:
        from guard import panic  # type: ignore
        return panic
    except ImportError:
        pass
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return _load_by_path(os.path.join(here, "guard", "panic.py"))


def _print_panic_word(word: str) -> None:
    print("panic word (shown once, keep it off this machine): " + word)
    print("  to stop this box from any phone, send the runner's mailbox a "
          "message with the subject")
    print(f"  [HOMING-PIGEON] panic {word}")
    print("  it needs no secret; the box stays stopped until "
          "install.py --rearm is run here")


def ensure_panic_word(cfg_path: str) -> None:
    """Arm the panic word on a fresh install, or say it is armed (Q100).
    The word is printed once and never stored; only its salted digest
    is kept, in panic.json in the runner's state dir."""
    base = _cfg_base_dir(cfg_path)
    try:
        panic = _import_panic()
        os.makedirs(base, exist_ok=True)
        if panic.state(base) != "not armed":
            print("panic word: armed (install.py --rearm prints a new one)")
            return
        _print_panic_word(panic.arm(base))
    except Exception as e:
        print(f"panic word: not armed ({e}); run install.py --rearm")


def do_rearm(cfg_path: str) -> int:
    """Clear a fired panic and print a new word. Only on the box."""
    base = _cfg_base_dir(cfg_path)
    try:
        panic = _import_panic()
        os.makedirs(base, exist_ok=True)
        was = panic.state(base)
        word = panic.arm(base)
    except Exception as e:
        print(f"error: the panic word was not re-armed: {e}", file=sys.stderr)
        return 1
    if was == "fired":
        print("the stopped box is released; restart the runner (or its "
              "service) and it polls again")
    _print_panic_word(word)
    return 0

# Frozen binaries cannot import the package the same way a live run can.
# The constant is the source of truth for --version; runner/tests/test_version.py
# fails the build if it drifts from pyproject.toml.
__version__ = "3.16.20.7"

SERVICE_NAME = "homing-pigeon"
FILES = ["runner.py", "wire/__init__.py", "wire/oauth.py",
         "ops/__init__.py", "ops/winlog.py"]

# A source install copies the runtime the way the wheel ships it:
# runner.py, its version, and every role folder it imports from
# (AGENTS.md, "Where things live"). The suite, the build tools and
# the shipped extensions stay behind. FILES alone was the layout
# before the role folders; an install from it could not start
# ("runner/guard/textutil.py is missing").
# (Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab)
_RUNTIME_TOP = ("_version.py",)
_RUNTIME_DIRS = ("guard", "oracle", "wire", "ops", "transport_extensions")
_RUNTIME_SUFFIXES = (".py", ".json")


def _runtime_files(src_dir: str) -> list:
    """FILES, plus the role folders and version file src_dir carries."""
    names = list(FILES)
    for name in _RUNTIME_TOP:
        if os.path.isfile(os.path.join(src_dir, name)):
            names.append(name)
    for top in _RUNTIME_DIRS:
        base = os.path.join(src_dir, top)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
            for fname in sorted(filenames):
                if fname.endswith(_RUNTIME_SUFFIXES):
                    rel = os.path.relpath(os.path.join(dirpath, fname),
                                          src_dir)
                    names.append(rel.replace(os.sep, "/"))
    seen = set()
    return [n for n in names if not (n in seen or seen.add(n))]

# When frozen with PyInstaller (the release binaries), there is no Python
# on the target machine: the runner ships as a sibling binary
# (homing-pigeon / homing-pigeon.exe) and services point at it directly.
FROZEN = getattr(sys, "frozen", False)
RUNNER_BIN = "homing-pigeon.exe" if os.name == "nt" else "homing-pigeon"


def _src_dir() -> str:
    if FROZEN:
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _runner_argv(dst_dir: str):
    """Argv that starts the installed runner (list, no shell)."""
    if FROZEN:
        return [os.path.join(dst_dir, RUNNER_BIN)]
    return [sys.executable, os.path.join(dst_dir, "runner.py")]


def _forwarded_args(args) -> list:
    """Runner CLI flags to bake into the installed service command."""
    out = []
    for name in ("dry_run", "no_send", "pdb", "allow_cleartext",
                 "ignore_personal_documents"):
        if getattr(args, name, False):
            out.append("--" + name.replace("_", "-"))
    # verbose is the runner default. Only bake the off switch.
    if getattr(args, "verbose", True) is False:
        out.append("--quiet")
    for name in ("poll_interval", "max_output_bytes", "timeout", "workers"):
        v = getattr(args, name, None)
        if v is not None:
            out.extend(["--" + name.replace("_", "-"), str(v)])
    return out


def run(cmd, **kw):
    print("+ " + " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def _installer_cmd():
    """How this box runs the installer, for a hint (Q98 item 11): the
    frozen binary the release archive carries (install.exe on
    Windows, ./install elsewhere), or the script by path from source."""
    if getattr(sys, "frozen", False):
        return "install.exe" if sys.platform == "win32" else "./install"
    if sys.platform == "win32":
        return "python runner\\ops\\install.py"
    return "python3 runner/ops/install.py"


def _looks_like_placeholder(secret: str) -> bool:
    """Mirror of the runner's placeholder check (install.py is standalone,
    so the logic is duplicated here rather than imported)."""
    if not isinstance(secret, str):
        return False
    low = secret.lower()
    return any(p in low for p in ("generate", "changeme", "example",
                                  "placeholder", "your-secret", "your_secret",
                                  "todo", "xxx"))


def _looks_patterned(secret: str) -> bool:
    """Mirror of the runner's periodic-pattern check (see _looks_like_placeholder)."""
    if not isinstance(secret, str):
        return False
    n = len(secret)
    for period in range(1, n // 2 + 1):
        unit = secret[:period]
        if secret == (unit * ((n // period) + 1))[:n]:
            return True
    return False


_KEY_ID_LABEL = b"homing-pigeon key id v1\n"


def key_fingerprint(secret: str) -> str:
    """The name a secret carries by default (Q94): `k-` and the first
    eight hex digits of SHA-384 over a fixed label and the secret.
    The runner computes the same (runner/guard/security.py); this
    file runs by path, so it carries its own copy. The name is public
    by design, like a user name; it gives an attacker nothing a
    signed message does not already."""
    import hashlib
    digest = hashlib.sha384(_KEY_ID_LABEL + secret.encode("utf-8")).hexdigest()
    return "k-" + digest[:8]


def ensure_shared_secret(cfg_path: str, provided: str | None,
                         key_id: str | None = None) -> None:
    """Write a shared_secret into config.json, and say its name.

    Uses the --shared-secret value when given (automated deployments);
    otherwise generates a random 256-bit secret. Either way the user
    retrieves it from config.json afterwards and hands it to their
    cloud SI together with its key id: the fingerprint the runner
    answers to (Q94), printed here, and a chosen name under --key-id
    when one was given, stored as an additional key with the same
    value. A provided secret gets the same entropy bar as the
    runner's startup check.
    """
    cfg = _read_config(cfg_path)
    current = cfg.get("shared_secret") or ""
    if current and not provided and not _looks_like_placeholder(current):
        if key_id:
            _name_first_key(cfg_path, current, key_id)
        print(f"the runner's key is named {key_fingerprint(current)}"
              + (f" (and {key_id})" if key_id else "")
              + " -- a sender gives that key id with the secret")
        return  # user-set real secret; leave it alone
    # Missing, empty, or a placeholder: generate or use the provided value.
    import secrets
    secret = provided if provided else secrets.token_hex(32)
    if not isinstance(secret, str) or len(secret) < 32 or _looks_like_placeholder(secret) or _looks_patterned(secret):
        print("error: the shared secret is too short, patterned, or a placeholder", file=sys.stderr)
        return
    cfg["shared_secret"] = secret
    if key_id:
        _name_first_key(cfg_path, secret, key_id)
    _write_json(cfg_path, cfg)
    print(f"the runner's key is named {key_fingerprint(secret)}"
          + (f" (and {key_id})" if key_id else "")
          + " -- a sender gives that key id with the secret")
