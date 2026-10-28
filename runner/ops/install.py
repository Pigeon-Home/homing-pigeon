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
__version__ = "3.14.14"

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
    # Missing, empty, or still the example placeholder: (re)generate.
    secret = provided or secrets.token_hex(32)
    # The runner's own estimate (runner/guard/security.py,
    # _estimate_secret_entropy: length x log2 of the alphabet), so the
    # installer never refuses a secret the runner accepts (Q98 item 8).
    alphabet = len(set(secret))
    bits = len(secret) * math.log2(alphabet) if alphabet > 1 else 0
    if bits < 128 or _looks_like_placeholder(secret) or _looks_patterned(secret):
        print("error: --shared-secret is too weak (needs 128+ bits of real "
              "entropy, not a placeholder or repeating pattern)",
              file=sys.stderr)
        sys.exit(2)
    cfg["shared_secret"] = secret
    _write_json(cfg_path, cfg)
    name = key_fingerprint(secret)
    if key_id:
        _name_first_key(cfg_path, secret, key_id)
    pair = (f"key id {name}" + (f" (and {key_id})" if key_id else "")
            + " -- give your cloud SI the pair, this key id and the "
            "shared_secret value in config.json")
    if provided:
        print(f"wrote --shared-secret into config.json: {pair}")
    else:
        print(f"generated the runner's key into {cfg_path}: {pair}")
    ensure_runner_id(cfg_path)


def _name_first_key(cfg_path: str, secret: str, key_id: str) -> None:
    """A chosen name for the first key, beside its fingerprint: the
    same value under additional_secrets[key_id]."""
    if not isinstance(key_id, str) or not _KEY_ID.match(key_id):
        print("error: --key-id must match [A-Za-z0-9._-]{1,64}",
              file=sys.stderr)
        sys.exit(2)
    cfg = _read_config(cfg_path)
    extra = cfg.get("additional_secrets")
    if extra is None:
        extra = {}
    if not isinstance(extra, dict):
        print("error: additional_secrets in config is not an object",
              file=sys.stderr)
        sys.exit(2)
    if extra.get(key_id) not in (None, secret):
        print(f"error: additional_secrets already holds a different key "
              f"under {key_id}", file=sys.stderr)
        sys.exit(2)
    extra[key_id] = secret
    cfg["additional_secrets"] = extra
    _write_json(cfg_path, cfg)


def ensure_runner_id(cfg_path: str) -> None:
    """Hardening M5: generate a 128-bit runner_id when absent.

    Never overwrites an existing one: changing it would invalidate
    previously signed jobs.
    """
    cfg = _read_config(cfg_path)
    if cfg.get("runner_id"):
        return
    cfg["runner_id"] = secrets.token_hex(16)
    _write_json(cfg_path, cfg)
    print(f"generated runner_id into {cfg_path}")


_KEY_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def store_additional_secret(cfg_path: str, key_id: str) -> None:
    """Generate a 256-bit secret and store it under additional_secrets.

    The value is written into config.json and never printed.
    """
    if not isinstance(key_id, str) or not _KEY_ID.match(key_id):
        print("error: --additional-secret KEY_ID must match "
              "[A-Za-z0-9._-]{1,64}", file=sys.stderr)
        sys.exit(2)
    cfg = _read_config(cfg_path)
    extra = cfg.get("additional_secrets")
    if extra is None:
        extra = {}
    if not isinstance(extra, dict):
        print("error: additional_secrets in config is not an object",
              file=sys.stderr)
        sys.exit(2)
    secret = secrets.token_urlsafe(32)
    extra[key_id] = secret
    cfg["additional_secrets"] = extra
    _write_json(cfg_path, cfg)
    # The value stays in the file. This line names the key only.
    # codeql[py/clear-text-logging-sensitive-data]
    print(f"additional secret stored for {key_id}")


def _cfg_base_dir(cfg_path: str) -> str:
    """The state dir the runner will use for this config: an explicit
    base_dir wins, else the config file's directory (runner
    _base_dir_for)."""
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        cfg = {}
    bd = cfg.get("base_dir") if isinstance(cfg, dict) else None
    if isinstance(bd, str) and bd.strip():
        return bd
    return os.path.dirname(os.path.abspath(cfg_path))


def install_project_snapshot(src_dir: str, base_dir: str) -> bool:
    """Install the release's project snapshot as <base_dir>/project.

    A release archive carries project/ (runner/tools/make_snapshot.py): every
    tracked file, the full history as a git bundle, and the build's CI
    facts. It lands in the state dir so the Oracle's file tools reach
    it. An upgrade replaces it whole; nothing else in the state dir is
    touched. No snapshot in the archive (a source install) is not an
    error. Returns True when a snapshot was installed.
    """
    src = os.path.join(src_dir, "project")
    if not os.path.isfile(os.path.join(src, "PROJECT-SNAPSHOT.md")):
        return False
    os.makedirs(base_dir, exist_ok=True)
    dst = os.path.join(base_dir, "project")
    staging = dst + ".new"
    retired = dst + ".old"
    for leftover in (staging, retired):
        if os.path.exists(leftover):
            shutil.rmtree(leftover, ignore_errors=True)
    try:
        shutil.copytree(src, staging, symlinks=True)
        if os.path.exists(dst):
            os.replace(dst, retired)
        os.replace(staging, dst)
    except OSError as e:
        print(f"install: warning: project snapshot not installed: {e}")
        shutil.rmtree(staging, ignore_errors=True)
        if not os.path.exists(dst) and os.path.exists(retired):
            os.replace(retired, dst)
        return False
    shutil.rmtree(retired, ignore_errors=True)
    print(f"project snapshot: {dst} (index: PROJECT-SNAPSHOT.md)")
    return True


def install_files(src_dir: str, bin_dir: str,
                  cfg_path: str | None = None) -> bool:
    """Copy binaries into bin_dir; seed cfg_path from the example when absent.

    cfg_path defaults to bin_dir/config.json (the legacy layout). Also
    installs the installer itself into bin_dir, so the ops commands
    (--check/--console/--logs) are always at hand. Never replaces the
    binary that is currently running. Returns False when a binary could
    not be replaced (e.g. the agent is still running it).
    """
    if cfg_path is None:
        cfg_path = os.path.join(bin_dir, "config.json")
    os.makedirs(bin_dir, exist_ok=True)
    if FROZEN:
        pairs = [(os.path.join(src_dir, RUNNER_BIN),
                  os.path.join(bin_dir, RUNNER_BIN))]
        me_src = os.path.join(src_dir,
                              "install.exe" if os.name == "nt" else "install")
        me_dst = os.path.join(bin_dir, os.path.basename(me_src))
        if (os.path.normcase(os.path.abspath(me_src))
                != os.path.normcase(os.path.abspath(me_dst))):
            pairs.append((me_src, me_dst))
        else:
            print("install: running from the home bin dir; "
                  "leaving this install.exe in place")
        for src, dst in pairs:
            if not os.path.isfile(src):
                print(f"install: error: {src} not found next to the installer")
                return False
            try:
                shutil.copy2(src, dst)
            except OSError as e:
                print(f"install: error: could not replace {dst}: {e}")
                print("install: is the agent still running it? stop the "
                      "HomingPigeon task and re-run")
                return False
            if os.name != "nt":
                os.chmod(dst, 0o755)
    else:
        for name in _runtime_files(src_dir):
            dst = os.path.join(bin_dir, *name.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(src_dir, *name.split("/")), dst)
    if not os.path.exists(cfg_path):
        example = os.path.join(src_dir, "config.example.json")
        if not os.path.isfile(example):
            print(f"install: error: {example} not found; cannot seed config")
            return False
        os.makedirs(os.path.dirname(os.path.abspath(cfg_path)), exist_ok=True)
        shutil.copy2(example, cfg_path)
        try:
            os.chmod(cfg_path, 0o600)
        except OSError:
            pass
        print(f"wrote {cfg_path} -- EDIT IT before starting "
              "(mailbox_user, mailbox_password, shared_secret)")
    return True


def install_windows(dst_dir: str, cfg_path: str, extra=(), run_as="SYSTEM"):
    """Register the runner as a Windows Scheduled Task.

    run_as: the account the task runs as. The default SYSTEM needs no
    password. Well-known service accounts and gMSA names (ending in $)
    also need none; any other account makes schtasks prompt for its
    password interactively. Named (non-SYSTEM) accounts get /RL LIMITED
    instead of HIGHEST: least privilege is the point of --run-as.
    """
    tr = windows_task_command(dst_dir, cfg_path, extra)
    run_as = run_as or "SYSTEM"
    level = "HIGHEST" if run_as.upper() in ("SYSTEM", "NT AUTHORITY\\SYSTEM") \
        else "LIMITED"
    run(["schtasks", "/Create", "/TN", "HomingPigeon", "/TR", tr,
         "/SC", "ONSTART", "/RU", run_as, "/RL", level, "/F"])
    run(["schtasks", "/Run", "/TN", "HomingPigeon"])
    print(f"installed: Scheduled Task 'HomingPigeon' "
          f"(runs at boot as {run_as}, run level {level})")


def uninstall_windows():
    run(["schtasks", "/Delete", "/TN", "HomingPigeon", "/F"])


# --- --wipe / --migrate: state discovery, backup, and consolidation ---
#
# Uninstall removes the scheduled task but leaves every state dir
# behind, so a box accumulates them: the user's, the SYSTEM profile's,
# older copies. --wipe backs them all up into one zip and then deletes
# them ("as if never installed"). --migrate copies them into --dir
# without overwriting. Both print exactly what they did, because the
# first thing anyone does with these options is back everything up.

def _run_quiet(cmd):
    """Best-effort command. Never raises, never prints."""
    try:
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _candidate_state_dirs():
    """Everywhere a .homing-pigeon state dir could live on this box.

    Existing directories only, deduplicated, current user's first.
    """
    cands = []
    home = os.path.expanduser("~")
    if home:
        cands.append(os.path.join(home, ".homing-pigeon"))
    if sys.platform == "win32":
        drive = os.environ.get("SystemDrive", "C:")
        users = drive + os.sep + "Users"
        try:
            names = os.listdir(users)
        except OSError:
            names = []
        for n in sorted(names):
            cands.append(os.path.join(users, n, ".homing-pigeon"))
        sysroot = os.environ.get("SystemRoot", r"C:\Windows")
        cands.append(os.path.join(sysroot, "System32", "config",
                                  "systemprofile", ".homing-pigeon"))
    else:
        for h in ("/root", "/var/lib/homing-pigeon"):
            cands.append(os.path.join(h, ".homing-pigeon"))
    seen = set()
    out = []
    for c in cands:
        try:
            key = os.path.normcase(os.path.abspath(c))
        except Exception:
            continue
        if key in seen:
            continue
        seen.add(key)
        try:
            if os.path.isdir(c):
                out.append(c)
        except OSError:
            pass
    return out


def _dir_summary(path):
    """(file_count, total_bytes) for the printed report."""
    n = 0
    size = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            n += 1
            try:
                size += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return n, size


def _kill_runner_processes():
    """Stop pigeon runner processes. Never matches this installer."""
    if sys.platform == "win32":
        _run_quiet(["taskkill", "/F", "/IM", "homing-pigeon.exe"])
    else:
        _run_quiet(["pkill", "-f", "[h]oming-pigeon"])


def _backup_dirs_to_zip(dirs, zip_path):
    """Zip each dir under its own top-level folder. Returns file count."""
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in dirs:
            label = re.sub(r"[^A-Za-z0-9]+", "_", d).strip("_") or "pigeon"
            for root, _dirs, files in os.walk(d):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, d)
                    try:
                        zf.write(full, os.path.join(label, rel))
                        count += 1
                    except OSError:
                        pass
    return count


def do_wipe(backup_dir=None, no_backup=False):
    """Back up every state dir into one zip, then remove everything.

    Removes the scheduled task / service entries (best effort),
    kills runner processes, and deletes the state dirs. Ollama and
    its models are left alone: they are a separate program.
    """
    print("wipe: stopping pigeon processes...")
    _kill_runner_processes()
    if sys.platform == "win32":
        _run_quiet(["schtasks", "/Delete", "/TN", "HomingPigeon", "/F"])
        print("wipe: scheduled task 'HomingPigeon' deleted (if it existed)")
    elif sys.platform.startswith("linux"):
        _run_quiet(["systemctl", "--user", "disable", "--now",
                    "homing-pigeon.service"])
        _run_quiet(["sudo", "-n", "systemctl", "disable", "--now",
                    "homing-pigeon.service"])
        print("wipe: systemd units disabled (if they existed)")
    elif sys.platform == "darwin":
        _run_quiet(["launchctl", "bootout", "gui/%s" % _posix_uid(),
                    os.path.expanduser(
                        "~/Library/LaunchAgents/com.homing-pigeon.runner.plist")])
        print("wipe: launchd job unloaded (if it existed)")

    dirs = _candidate_state_dirs()
    if sys.platform == "win32":
        # The one home is wiped too: bin/, config.json, state/, receipt.
        home = _default_home()
        hkey = os.path.normcase(os.path.abspath(home))
        if os.path.isdir(home) and all(
                os.path.normcase(os.path.abspath(d)) != hkey for d in dirs):
            dirs.append(home)
            print(f"wipe: including the one home {home}")
    if not dirs:
        print("wipe: no .homing-pigeon state dirs found on this box")
    backup_path = None
    if dirs and not no_backup:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        bdir = os.path.abspath(backup_dir) if backup_dir else tempfile.gettempdir()
        try:
            os.makedirs(bdir, exist_ok=True)
        except OSError as e:
            print(f"wipe: cannot create backup dir {bdir}: {e}")
            return 1
        backup_path = os.path.join(bdir, f"homing-pigeon-backup-{ts}.zip")
        try:
            n = _backup_dirs_to_zip(dirs, backup_path)
        except OSError as e:
            print(f"wipe: backup failed: {e}; nothing deleted")
            return 1
        print(f"wipe: backed up {n} file(s) from {len(dirs)} location(s):")
        for d in dirs:
            nfiles, size = _dir_summary(d)
            print(f"wipe:   {d} ({nfiles} files)")
        print(f"wipe: backup is {backup_path}")
    elif dirs:
        print("wipe: --no-backup given; deleting without a backup")

    for d in dirs:
        nfiles, _size = _dir_summary(d)
        try:
            shutil.rmtree(d)
            print(f"wipe: deleted {d} ({nfiles} files)")
        except OSError as e:
            print(f"wipe: could not delete {d}: {e}")
    print("wipe: done. Ollama and its models were left in place; "
          "uninstall Ollama separately if you want it gone.")
    print("wipe: reinstall with install.exe to start fresh.")
    return 0


def _merge_tree(src, dst):
    """Copy files from src into dst, never overwriting.

    Returns (copied, skipped).
    """
    copied = 0
    skipped = 0
    for root, _dirs, files in os.walk(src):
        for f in files:
            s = os.path.join(root, f)
            rel = os.path.relpath(s, src)
            t = os.path.join(dst, rel)
            if os.path.exists(t):
                skipped += 1
                continue
            try:
                os.makedirs(os.path.dirname(t), exist_ok=True)
            except OSError:
                skipped += 1
                continue
            try:
                shutil.copy2(s, t)
                copied += 1
            except OSError:
                skipped += 1
    return copied, skipped


def do_migrate(target_dir):
    """Copy state found in other locations into target_dir.

    Never overwrites. Sources are left in place; verify the result,
    then 'install.exe --wipe' removes the old locations.
    """
    target = os.path.abspath(target_dir)
    try:
        os.makedirs(target, exist_ok=True)
    except OSError as e:
        print(f"migrate: cannot create {target}: {e}")
        return 1
    print(f"migrate: target {target}")
    tkey = os.path.normcase(target)
    sources = [d for d in _candidate_state_dirs()
               if os.path.normcase(os.path.abspath(d)) != tkey]
    if not sources:
        print("migrate: no other state dirs found; nothing to do")
        return 0
    print(f"migrate: found {len(sources)} other location(s):")
    for s in sources:
        print(f"migrate:   {s}")
    total_copied = 0
    total_skipped = 0
    for src in sources:
        copied, skipped = _merge_tree(src, target)
        total_copied += copied
        total_skipped += skipped
        print(f"migrate: {src}: {copied} copied, "
              f"{skipped} skipped (already present)")
    print(f"migrate: done. {total_copied} file(s) consolidated into {target}; "
          f"{total_skipped} skipped.")
    print("migrate: sources left in place. Verify, then "
          f"'{_installer_cmd()} --wipe' removes the old locations.")
    return 0


# --- The one home (Windows) ---
#
# One folder per box: C:\homing-pigeon holding bin/, config.json,
# state/, and install-receipt.json. The installer runs once as admin,
# ACLs the home for SYSTEM + Administrators, and every way of running
# the agent (service task, terminal, --oracle) points at the same
# config, so there is no more SYSTEM-vs-user state split.
# Re-running the installer is idempotent: it upgrades the binaries in
# place and never touches config.json or state/.

RECEIPT_NAME = "install-receipt.json"
LAYOUT_VERSION = 1


def _default_home() -> str:
    drive = os.environ.get("SystemDrive", "C:")
    return os.path.join(drive + os.sep, "homing-pigeon")


def _resolve_home(args):
    """Windows one-home paths, or None when the one-home does not apply.

    Returns (home, bin_dir, cfg_path, state_dir). None on non-Windows,
    or when --dir is given without --home (legacy layout: the binaries
    and config.json both live in --dir, no receipt, no ACL).
    """
    if sys.platform != "win32":
        return None
    if getattr(args, "dir", None) and not getattr(args, "home", None):
        return None
    home = os.path.abspath(getattr(args, "home", None) or _default_home())
    bin_dir = (os.path.abspath(args.dir) if getattr(args, "dir", None)
               else os.path.join(home, "bin"))
    cfg_path = (os.path.abspath(args.config) if getattr(args, "config", None)
                else os.path.join(home, "config.json"))
    return home, bin_dir, cfg_path, os.path.join(home, "state")


def _is_admin() -> bool:
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # pyrefly: ignore[missing-attribute]  # win32-only; guarded by sys.platform above
    except Exception:
        return False


def _acl_home(home, run_as=None) -> bool:
    """Lock the home to SYSTEM + Administrators. A named --run-as account
    gets full control too, or the agent could not read its own config.
    Best effort: warns, never aborts the install."""
    if sys.platform != "win32":
        return True
    grants = ["SYSTEM:(OI)(CI)F", "Administrators:(OI)(CI)F"]
    names = ["SYSTEM", "Administrators"]
    who = (run_as or "SYSTEM").upper()
    if who not in ("SYSTEM", "NT AUTHORITY\\SYSTEM") and run_as:
        grants.append(f"{run_as}:(OI)(CI)F")
        names.append(run_as)
    cmd = ["icacls", home, "/inheritance:r"]
    for g in grants:
        cmd += ["/grant:r", g]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           errors="replace")
    except Exception as e:
        print(f"home: warn: could not set ACLs on {home} ({e})")
        return False
    if p.returncode != 0:
        detail = (p.stderr or p.stdout).strip().splitlines()
        print(f"home: warn: icacls failed on {home}: "
              f"{detail[0] if detail else 'unknown error'}")
        return False
    print(f"home: {home} is now {' + '.join(names)} only")
    return True


def _receipt_path(home: str) -> str:
    return os.path.join(home, RECEIPT_NAME)


def _read_receipt(home):
    """The receipt dict, None when there is none, 'corrupt' when unreadable.

    A symlink is not followed. It is treated as corrupt so the next
    write replaces the name instead of trusting the target.
    """
    path = _receipt_path(home)
    if os.path.islink(path):
        return "corrupt"
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else "corrupt"
    except FileNotFoundError:
        return None
    except Exception:
        return "corrupt"


def _write_receipt(home, fresh: bool) -> None:
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"
    domain = os.environ.get("USERDOMAIN")
    who = f"{domain}\\{user}" if domain else user
    prev = _read_receipt(home)
    data = dict(prev) if isinstance(prev, dict) else {}
    data.update({
        "version": __version__,
        "layout_version": LAYOUT_VERSION,
        "home": home,
    })
    if fresh:
        data["installed_at"] = now
        data["installed_by"] = who
    else:
        data.setdefault("installed_by", who)
        data["upgraded_at"] = now
    _write_json(_receipt_path(home), data)
    print(f"home: receipt written "
          f"({'fresh install' if fresh else 'upgrade'} v{__version__})")


def _ensure_base_dir(cfg_path: str, state_dir: str) -> None:
    """Point a fresh home config at the home's state dir, so the home
    root stays clean and state never depends on who runs the agent."""
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    if not cfg.get("base_dir"):
        cfg["base_dir"] = state_dir
        _write_json(cfg_path, cfg)


# --- Scheduled-task helpers (Windows) ---

def _task_exists() -> bool:
    p = subprocess.run(["schtasks", "/Query", "/TN", "HomingPigeon"],
                       capture_output=True)
    return p.returncode == 0


def _task_command():
    """The 'Task To Run' line of the HomingPigeon task, or None."""
    p = subprocess.run(["schtasks", "/Query", "/TN", "HomingPigeon",
                        "/V", "/FO", "LIST"],
                       capture_output=True, text=True, errors="replace")
    if p.returncode != 0:
        return None
    for line in p.stdout.splitlines():
        if line.strip().lower().startswith("task to run:"):
            return line.split(":", 1)[1].strip()
    return None


def _task_end() -> int:
    p = subprocess.run(["schtasks", "/End", "/TN", "HomingPigeon"],
                       capture_output=True, text=True, errors="replace")
    return p.returncode


def _task_run() -> int:
    p = subprocess.run(["schtasks", "/Run", "/TN", "HomingPigeon"],
                       capture_output=True, text=True, errors="replace")
    return p.returncode


def _process_running(image: str) -> bool:
    p = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}"],
                       capture_output=True, text=True, errors="replace")
    out = p.stdout.lower()
    return image.lower() in out and "no tasks" not in out


def _wait_for_exit(image: str, timeout: int = 15) -> bool:
    for _ in range(int(timeout * 2)):
        if not _process_running(image):
            return True
        time.sleep(0.5)
    print(f"warn: {image} is still running after {timeout}s")
    return False


def _stop_task_for_upgrade() -> None:
    """Best effort: stop the task so its binary can be replaced."""
    if sys.platform != "win32" or not _task_exists():
        return
    print("install: stopping the HomingPigeon task for the upgrade...")
    if _task_end() == 0:
        _wait_for_exit(RUNNER_BIN, timeout=20)
    else:
        print("install: warn: could not stop the task; the binary "
              "replacement may fail if the agent is still running it")


def _split_host_port(url):
    """(host, port) from an http(s) URL. Port None when absent."""
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url)
        return p.hostname, p.port
    except Exception:
        return None, None


def _tcp_reachable(host, port, timeout=2.0) -> bool:
    import socket
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def do_check(home, bin_dir, cfg_path, state_dir) -> int:
    """Doctor: verify the one-home install. Plain-language PASS/WARN/FAIL
    lines; exits non-zero when anything structural is broken."""
    rows = []

    def rec(status, label, detail=""):
        rows.append((status, label, detail))

    rec("PASS" if os.path.isdir(home) else "FAIL", f"home dir {home}",
        "" if os.path.isdir(home) else "run install.exe to create it")
    exe = os.path.join(bin_dir, RUNNER_BIN)
    rec("PASS" if os.path.isfile(exe) else "FAIL", f"runner {exe}",
        "" if os.path.isfile(exe) else "re-run install.exe")
    if FROZEN:
        me = os.path.join(bin_dir,
                          "install.exe" if os.name == "nt" else "install")
        present = os.path.isfile(me)
        rec("PASS" if present else "WARN", f"installer {me}",
            "" if present else
            "ops commands (--check/--console/--logs) want install.exe "
            "in the home bin")
    receipt = _read_receipt(home)
    if receipt is None:
        rec("FAIL", "install-receipt.json",
            "missing: this is not a one-home install")
    elif receipt == "corrupt":
        rec("WARN", "install-receipt.json",
            "unreadable; re-run install.exe to rewrite it")
    else:
        rec("PASS", "install-receipt.json",
            f"v{receipt.get('version', '?')} installed "
            f"{receipt.get('installed_at', '?')} "
            f"by {receipt.get('installed_by', '?')}")
    cfg = None
    if not os.path.isfile(cfg_path):
        rec("FAIL", f"config {cfg_path}", "missing: re-run install.exe")
    else:
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                cfg = json.load(fh)
            rec("PASS", f"config {cfg_path}", "parses as JSON")
        except Exception as e:
            rec("FAIL", f"config {cfg_path}", f"does not parse: {e}")
    if isinstance(cfg, dict):
        if not cfg.get("shared_secret"):
            rec("WARN", "shared_secret",
                "not set in config.json; signed jobs cannot verify")
        else:
            # The key ids this runner holds, names only: a sender who
            # must say which key signs can read them here, since the
            # default secret has no name of its own (its key id is
            # the empty string) and nothing else lists them.
            extra = cfg.get("additional_secrets")
            names = sorted(k for k in extra if isinstance(k, str)) \
                if isinstance(extra, dict) else []
            default = cfg.get("shared_secret")
            try:
                first = key_fingerprint(default)
            except Exception:
                first = "?"
            rec("PASS", "shared_secret",
                f"set (the runner's key, key id {first}; the unnamed "
                "default, key id \"\", is the same key)"
                + (f"; additional key ids: {', '.join(names)}"
                   if names else "; no additional key ids"))
        try:
            panic = _import_panic()
            pbase = _cfg_base_dir(cfg_path)
            pstate = panic.state(pbase)
            rec({"armed": "PASS", "fired": "FAIL"}.get(pstate, "WARN"),
                "panic word",
                {"armed": "armed",
                 "fired": "fired: the box is stopped; install.py --rearm "
                          "releases it",
                 }.get(pstate, "not armed: install.py --rearm arms it")
                + "; " + panic.protection(cfg))
        except Exception as e:
            rec("WARN", "panic word", f"not read: {e}")
        bd = cfg.get("base_dir")
        if (bd and os.path.normcase(os.path.abspath(bd))
                != os.path.normcase(os.path.abspath(state_dir))):
            rec("WARN", "base_dir",
                f"config points at {bd}, not the home state dir")
    rec("PASS" if os.path.isdir(state_dir) else "WARN",
        f"state dir {state_dir}",
        "" if os.path.isdir(state_dir) else "created on the agent's first run")
    if sys.platform == "win32":
        if not _task_exists():
            rec("FAIL", "scheduled task HomingPigeon",
                "not registered; run install.exe to register it")
        else:
            cmd = _task_command()
            if cmd and os.path.normcase(bin_dir) in os.path.normcase(cmd):
                rec("PASS", "scheduled task HomingPigeon",
                    "points at the home bin")
            elif cmd:
                rec("WARN", "scheduled task HomingPigeon", f"runs: {cmd}")
            else:
                rec("WARN", "scheduled task HomingPigeon",
                    "exists but its command could not be read")
    inf = (cfg.get("inference") or {}) if isinstance(cfg, dict) else {}
    url = inf.get("endpoint") if isinstance(inf, dict) else None
    if isinstance(cfg, dict) and cfg.get("oracle_mode") == "deterministic":
        rec("PASS", "oracle mode",
            "deterministic (Pi Light): no local model by design; "
            "briefs and answers come from the box's records")
    elif not url:
        rec("WARN", "inference",
            "not configured; the Oracle chat stays off "
            f"({_installer_cmd()} --inference-only to set it up)")
    else:
        host, port = _split_host_port(url)
        if host in ("127.0.0.1", "localhost", "::1"):
            if _tcp_reachable(host, port or 11434):
                rec("PASS", "inference", f"{url} answers")
            else:
                rec("WARN", "inference",
                    f"{url} not reachable; is Ollama running?")
        else:
            rec("WARN", "inference",
                f"{url} is not a loopback endpoint")

    # Collector health: the state word is reported verbatim
    # (WORKS / INSTALLED-BUT-CANNOT-RUN / ABSENT). Absence is a
    # legitimate state, not a fault, so it does not warn; a
    # collector that is present but cannot collect does.
    for cname, cstate, cdetail in collector_health_rows(
            collector_health_facts()):
        rec({"WORKS": "PASS",
             "INSTALLED-BUT-CANNOT-RUN": "WARN",
             "ABSENT": "PASS"}[cstate],
            f"collector {cname}", f"{cstate} -- {cdetail}")

    npass = sum(1 for s, _, _ in rows if s == "PASS")
    nwarn = sum(1 for s, _, _ in rows if s == "WARN")
    nfail = sum(1 for s, _, _ in rows if s == "FAIL")
    for s, label, detail in rows:
        line = f"{s}: {label}"
        if detail:
            line += f" -- {detail}"
        print(line)
    print(f"check: {npass} passed, {nwarn} warnings, {nfail} failed")
    return 1 if nfail else 0


def do_console(home, bin_dir, cfg_path) -> int:
    """Stop the HomingPigeon task, run the agent in this terminal with
    live logs, and restart the task on exit -- even on Ctrl+C."""
    if sys.platform != "win32":
        print("console: only supported on Windows (it manages the "
              "HomingPigeon scheduled task)")
        return 2
    exe = os.path.join(bin_dir, RUNNER_BIN)
    if not os.path.isfile(exe):
        print(f"console: runner not found at {exe}; run install.exe first")
        return 1
    if not os.path.isfile(cfg_path):
        print(f"console: config not found at {cfg_path}; "
              "run install.exe first")
        return 1
    stopped = False
    if _task_exists():
        print("console: stopping the HomingPigeon scheduled task...")
        _task_end()  # best effort; the process check below is the real gate
        stopped = True
        _wait_for_exit(os.path.basename(exe), timeout=15)
        if _process_running(os.path.basename(exe)):
            print("console: the agent would not stop; starting a second "
                  "one would double-poll the mailbox -- aborting")
            print("console: kill homing-pigeon.exe by hand and try again")
            return 1
    else:
        print("console: no HomingPigeon task found; running the agent directly")
    print(f"console: starting {exe} --config {cfg_path} "
          "(Ctrl+C stops it and restores the task)")
    restart_failed = False
    try:
        subprocess.run([exe, "--config", cfg_path])
    except KeyboardInterrupt:
        print("console: interrupted")
    finally:
        if stopped:
            print("console: restarting the HomingPigeon scheduled task...")
            if _task_run() != 0:
                print("console: WARNING: could not restart the task; "
                      "start it by hand: schtasks /Run /TN HomingPigeon")
                restart_failed = True
            else:
                print("console: task restarted")
    return 1 if restart_failed else 0


def _runner_log_path(cfg_path) -> str:
    cfg = {}
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except Exception:
        pass
    base = cfg.get("base_dir") if isinstance(cfg, dict) else None
    if not base or not isinstance(base, str):
        base = os.path.dirname(os.path.abspath(cfg_path))
    return os.path.join(base, "runner.log")


def _tail_file(path, n):
    """Last n lines of a file, without reading the whole thing."""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        pos = fh.tell()
        buf = b""
        while pos > 0 and buf.count(b"\n") <= n:
            step = min(65536, pos)
            pos -= step
            fh.seek(pos)
            buf = fh.read(step) + buf
    lines = buf.decode("utf-8", errors="replace").splitlines()
    return lines[-n:] if n > 0 else []


def _follow_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        fh.seek(0, os.SEEK_END)
        while True:
            line = fh.readline()
            if line:
                sys.stdout.write(line if line.endswith("\n") else line + "\n")
                sys.stdout.flush()
            else:
                time.sleep(0.5)


def do_logs(cfg_path, follow=False, lines=50) -> int:
    path = _runner_log_path(cfg_path)
    if not os.path.isfile(path):
        print(f"logs: no log file at {path} yet; "
              "the agent writes it on its first run")
        return 1
    if not follow:
        for line in _tail_file(path, lines):
            print(line)
        return 0
    print(f"logs: following {path} (Ctrl+C to stop)")
    try:
        _follow_file(path)
    except KeyboardInterrupt:
        print("logs: stopped")
    return 0


def do_oracle(bin_dir, cfg_path) -> int:
    exe = os.path.join(bin_dir, RUNNER_BIN)
    if not os.path.isfile(exe):
        print(f"oracle: runner not found at {exe}; run install.exe first")
        return 1
    print(f"oracle: opening the chat against {cfg_path}")
    p = subprocess.run([exe, "--oracle", "--config", cfg_path])
    return p.returncode


def _pi_light_skip(args, profile) -> bool:
    """True when this install is Pi Light and must download nothing.

    The profile asks for the deterministic Oracle (oracle_mode in
    its spec). An explicit --inference-model or --faster is the
    owner overriding that by hand; those install a model as usual.
    """
    if profile_oracle_mode(profile) != "deterministic":
        return False
    explicit = getattr(args, "inference_model", None)
    if isinstance(explicit, str) and explicit.strip():
        return False
    if getattr(args, "faster", False):
        return False
    return True


def _cfg_oracle_mode(cfg_path):
    """The oracle_mode an existing config.json asks for, or None.

    The documented Pi Light upgrade is an in-place flip: the owner
    sets oracle_mode to llm in config.json and re-runs
    --inference-only. The profile alone cannot see that flip (a Pi
    still detects as Pi Light), so the --inference-only path
    consults the config it is upgrading before it skips.
    """
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return None
    if isinstance(cfg, dict):
        mode = cfg.get("oracle_mode")
        if isinstance(mode, str) and mode.strip():
            return mode.strip()
    return None


def _setup_fresh_config(args, cfg_path):
    """Secrets, mailbox wizard, profile, instructions, Ollama.

    Fresh installs only. Returns (inference_ok, model, pi_light).
    pi_light marks an install that deliberately set up no model:
    nothing was installed or downloaded for inference, and the
    profile wrote oracle_mode deterministic into the config."""
    _blob_spec = getattr(args, "config_json", None)
    if isinstance(_blob_spec, str):
        merge_config_blob(cfg_path, _blob_spec)
    first_key_id = getattr(args, "key_id", None)
    ensure_shared_secret(cfg_path, args.shared_secret,
                         first_key_id if isinstance(first_key_id, str)
                         else None)
    ensure_panic_word(cfg_path)
    # Mailbox auth is the one thing install cannot invent. On a TTY,
    # offer the same Thunderbird-style wizard the runner uses, so a
    # fresh install ends with a working service and no hand-edited
    # JSON. Headless installs keep today's behavior (fail at first
    # run with a config error pointing at --setup).
    try:
        from runner.ops import setup as _setup
    except ImportError:
        try:
            from ops import setup as _setup
        except ImportError:
            _setup = None
    if _setup is not None:
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                _cfg = json.load(fh)
        except (OSError, ValueError):
            _cfg = {}
        _reason = _setup.needs_setup(_cfg)
        if _reason and sys.stdin.isatty() and _setup.prompt_yes_no(
                f"Mailbox auth not configured ({_reason}). "
                f"Sign in now? [Y/n] "):
            _setup.run_setup_wizard(cfg_path, _cfg)
    for kid in args.additional_secret:
        store_additional_secret(cfg_path, kid)
    profile = chosen_profile(args.profile, args.no_profile)
    pi_light = _pi_light_skip(args, profile)
    model = inference_model_for(profile, args.inference_model,
                                faster=getattr(args, "faster", False))
    if pi_light:
        # Pi Light: install_ollama_and_model is not called at all.
        # No Ollama install, no model pull, nothing downloaded --
        # the Oracle runs deterministically on the records the
        # runner itself keeps.
        print("inference: skipped (Pi Light) -- no model is installed "
              "or downloaded; the Oracle runs deterministically. To "
              "add a model later, set oracle_mode to llm in "
              "config.json and re-run the installer with "
              "--inference-only.")
        inference_ok = False
        model = None
    else:
        inference_ok = install_ollama_and_model(cfg_path, model,
                                                args.no_inference)
    if profile:
        apply_profile(cfg_path, profile)
    collectors = chosen_collectors(args, profile)
    if collectors:
        install_collectors(collectors, args)
    elif profile_oracle_mode(profile) == "deterministic" \
            and not getattr(args, "no_collector", False) \
            and not getattr(args, "collector", None):
        print("collectors: none by default on Pi Light -- the "
              "light profile installs no collector. Pass "
              "--collector NAME to add one explicitly.")
    apply_instruction_flags(cfg_path, args.instructions, args.instructions_add)
    return inference_ok, model, pi_light


def do_install_home(args, home, bin_dir, cfg_path, state_dir, src_dir) -> int:
    """Windows one-home install. Idempotent: a re-run upgrades the
    binaries in place and never touches config.json or state/."""
    receipt = _read_receipt(home)
    fresh = not isinstance(receipt, dict)
    prev_version = (receipt.get("version", "?")
                    if isinstance(receipt, dict) else "?")
    if fresh and not _is_admin():
        print(f"error: creating {home} needs elevation; "
              "re-run install.exe as administrator")
        return 2
    for d in (home, bin_dir, state_dir):
        os.makedirs(d, exist_ok=True)
    if fresh:
        print(f"install: creating the one home at {home}")
        _acl_home(home, args.run_as)
    else:
        if getattr(args, "faster", False) and not args.no_inference:
            print(f"install: one home already installed (v{prev_version}); "
                  "upgrading binaries, and switching the model to the faster qwen2.5:3b")
        else:
            print(f"install: one home already installed (v{prev_version}); "
                  "upgrading binaries in place -- config.json and state/ "
                  "are untouched")
        if getattr(args, "shared_secret", None):
            # An upgrade never rewrites config.json, so a secret given
            # here would be dropped without a word (Q98 item 7).
            print("install: --shared-secret is not applied to an existing "
                  f"install; edit shared_secret in {cfg_path} (or "
                  "shared_secret_file) and restart the task",
                  file=sys.stderr)
        _stop_task_for_upgrade()
    if not install_files(src_dir, bin_dir, cfg_path):
        return 1
    install_project_snapshot(src_dir, state_dir)
    inference_ok, model, pi_light = False, None, False
    if fresh:
        _ensure_base_dir(cfg_path, state_dir)
        inference_ok, model, pi_light = _setup_fresh_config(args, cfg_path)
    elif getattr(args, "faster", False) and not args.no_inference:
        model = inference_model_for(None, args.inference_model, faster=True)
        inference_ok = install_ollama_and_model(cfg_path, model, False)
    _write_receipt(home, fresh)
    extra = _forwarded_args(args)
    if extra:
        print(f"forwarding runner flags into service: {' '.join(extra)}")
    install_windows(bin_dir, cfg_path, extra, run_as=args.run_as)
    print(f"config: {cfg_path}")
    if inference_ok:
        print(f"inference: READY - local model {model} configured; "
              "the Oracle chat will answer")
    elif fresh and not args.no_inference and not pi_light:
        print("inference: NOT configured - ask stays off. "
              "Re-run install.exe --inference-only to retry, or set "
              "inference.endpoint in config.json to your local Ollama server.")
    print("one home ready:")
    print(f"  home:   {home}")
    print(f"  bin:    {bin_dir}")
    print(f"  config: {cfg_path}")
    print(f"  state:  {state_dir}")
    print("commands to learn:")
    print("  install.exe --check    doctor: verify the install")
    print("  install.exe --console  run the agent here; the task restarts after")
    print("  install.exe --oracle   the Oracle chat")
    print("  install.exe --logs     tail the runner log (--follow to watch)")
    print("  install.exe --wipe     back up and remove everything")
    print("  install.exe --faster   pull qwen2.5:3b, the faster small model")
    return 0


def _write_text(path: str, text: str, mode: int = 0o644) -> None:
    """Write text without following a symlink. Used for the systemd unit."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(path, flags, mode)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def install_linux(dst_dir: str, cfg_path: str, system: bool, extra=()):
    for arg in extra:
        if not isinstance(arg, str) or "\n" in arg or "\r" in arg or "\x00" in arg:
            raise ValueError("systemd extra argument must be a single line")
    exec_start = " ".join(shlex.quote(a) for a in _runner_argv(dst_dir)) + " --config " + shlex.quote(cfg_path) + \
        "".join(f" {shlex.quote(a)}" for a in extra)
    unit = f"""[Unit]
Description=Homing Pigeon runner agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=always
RestartSec=10

[Install]
WantedBy={"multi-user.target" if system else "default.target"}
"""
    if system:
        path = "/etc/systemd/system/homing-pigeon.service"
        _write_text(path, unit)
        run(["systemctl", "daemon-reload"])
        run(["systemctl", "enable", "--now", "homing-pigeon.service"])
    else:
        udir = os.path.expanduser("~/.config/systemd/user")
        os.makedirs(udir, exist_ok=True)
        path = os.path.join(udir, "homing-pigeon.service")
        _write_text(path, unit)
        run(["systemctl", "--user", "daemon-reload"])
        run(["systemctl", "--user", "enable", "--now", "homing-pigeon.service"])
        _enable_linger()
    print(f"installed: systemd unit at {path}")


def _enable_linger():
    """A user unit starts at login unless the user lingers (Q98 item 9).
    Ask logind for it; a box that will not grant it is told what that
    means instead of being left to find out at the next reboot."""
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    try:
        # Through run(), the installer's one command seam, so a test
        # that fakes the service manager fakes this too.
        run(["loginctl", "enable-linger"] + ([user] if user else []))
        print("installed: lingering enabled, so the runner starts at boot")
    except (OSError, subprocess.CalledProcessError):
        print("note: the user unit starts at login, not at boot; run "
              "'loginctl enable-linger' (as root if asked) for boot start, "
              "or install with --system")


SYSTEM_UNIT = "/etc/systemd/system/homing-pigeon.service"
USER_UNIT = "~/.config/systemd/user/homing-pigeon.service"


def uninstall_linux(system: bool):
    """Remove whichever unit is there: the one --system names first,
    then the other, so an uninstall without --system still finds a
    system install (Q98 item 10). Neither present is said, not raised."""
    user_unit = os.path.expanduser(USER_UNIT)
    order = [(True, SYSTEM_UNIT), (False, user_unit)]
    if not system:
        order.reverse()
    removed = False
    for is_system, path in order:
        if not os.path.exists(path):
            continue
        scope = [] if is_system else ["--user"]
        run(["systemctl", *scope, "disable", "--now", "homing-pigeon.service"])
        os.remove(path)
        run(["systemctl", *scope, "daemon-reload"])
        removed = True
    if not removed:
        print("uninstall: no homing-pigeon systemd unit found "
              f"({SYSTEM_UNIT} or {user_unit})")


def _posix_uid() -> int:
    """Uid for a launchd gui domain.

    Windows has no getuid. These functions are not what the installer
    dispatches to there, but tests call them directly; 0 keeps the
    command shape instead of raising AttributeError.
    """
    getuid = getattr(os, "getuid", None)
    if getuid is None:
        return 0
    return getuid()


def install_macos(dst_dir: str, cfg_path: str, extra=()):
    pargs = "\n".join(
        f"    <string>{escape(a)}</string>"
        for a in (*_runner_argv(dst_dir), "--config", cfg_path, *extra))
    log_path = escape(os.path.join(dst_dir, "runner.log"))
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.homing-pigeon.runner</string>
  <key>ProgramArguments</key>
  <array>
{pargs}
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{log_path}</string>
  <key>StandardErrorPath</key><string>{log_path}</string>
</dict>
</plist>
"""
    adir = os.path.expanduser("~/Library/LaunchAgents")
    os.makedirs(adir, exist_ok=True)
    path = os.path.join(adir, "com.homing-pigeon.runner.plist")
    with open(path, "w") as fh:
        fh.write(plist)
    uid = _posix_uid()
    loaded = _launchd_load(uid, path)
    print(f"installed: launchd agent at {path}"
          + ("" if loaded else " (not loaded yet)"))


LAUNCHD_LABEL = "com.homing-pigeon.runner"


def _launchd_load(uid: int, path: str) -> bool:
    """Load the agent now, if this session can. True when it is
    running after this call.

    `launchctl bootstrap gui/<uid>` needs a logged-in GUI session:
    over SSH, in CI, on a headless Mac it exits 5 (Input/output
    error), and over a loaded agent (an upgrade) it refuses too. The
    install is complete either way, since the agent file is in
    place and launchd loads it at the user's next login (Q39,
    2026-10-25). An upgrade over a loaded agent is restarted with
    kickstart so the new code runs; anything else gets the command
    to run from a logged-in session.
    """
    try:
        run(["launchctl", "bootstrap", f"gui/{uid}", path])
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        problem = str(e)
    try:
        kick = subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/{LAUNCHD_LABEL}"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if kick.returncode == 0:
            print("launchd agent was already loaded; restarted it on the "
                  "new install")
            return True
    except (OSError, ValueError):
        pass
    print(f"warning: launchctl bootstrap did not load the agent now "
          f"({problem}); the agent file is installed and loads at this "
          f"user's next login. To load it now, from a logged-in session: "
          f"launchctl bootstrap gui/{uid} {path}")
    return False


def uninstall_macos():
    path = os.path.expanduser("~/Library/LaunchAgents/com.homing-pigeon.runner.plist")
    uid = _posix_uid()
    run(["launchctl", "bootout", f"gui/{uid}", path])
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def install_freebsd(dst_dir: str, cfg_path: str, extra=()):
    line = "@reboot " + " ".join(shlex.quote(a) for a in _runner_argv(dst_dir)) + " --config " + shlex.quote(cfg_path) + \
        "".join(f" {shlex.quote(a)}" for a in extra)
    p = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = p.stdout if p.returncode == 0 else ""
    if "homing-pigeon" in existing:
        print("crontab already has a homing-pigeon entry")
        return
    new = (existing.rstrip("\n") + "\n" if existing.strip() else "") + line + "\n"
    p2 = subprocess.run(["crontab", "-"], input=new, text=True)
    p2.check_returncode()
    print("installed: cron @reboot entry")
    print("note: for a native rc.d service instead, wrap the same command in "
          "/usr/local/etc/rc.d/homing_pigeon (requires root)")


def uninstall_freebsd():
    p = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines = [line for line in (p.stdout if p.returncode == 0 else "").splitlines()
             if "homing-pigeon" not in line]
    subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True,
                   check=True)



def _which(cmd):
    from shutil import which
    return which(cmd)


def _ollama_bin():
    """Absolute path to the ollama binary, or None.

    The installer often runs with a stale PATH: on Windows, winget drops
    Ollama into %LOCALAPPDATA%\\Programs\\Ollama and updates the registry
    PATH, which this process never picks up. Same story for the macOS
    .app bundle. So check the well-known install locations first and
    fall back to PATH.
    """
    candidates = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            candidates.append(os.path.join(local, "Programs", "Ollama", "ollama.exe"))
    elif sys.platform == "darwin":
        candidates.append("/Applications/Ollama.app/Contents/Resources/ollama")
    else:
        candidates.append(os.path.expanduser("~/.ollama/bin/ollama"))
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return _which("ollama")



_PI_HOME_SPEC = {
    "description": "Raspberry Pi Light: full runner and protocol, "
                   "deterministic Oracle, no local model",
    "redact_patterns_extra": {
        "shadow_hash": r"\$[0-9a-z]+\$[A-Za-z0-9./]{20,}",
    },
    "protected_paths": ["/etc/shadow", "/home/pi/docs/manuals"],
    "max_result_view": "attested",
    "judge": "advisory",
    # Pi Light: no model at all. Nothing for inference is installed
    # or downloaded -- the Oracle runs deterministically (see
    # oracle_mode in the runner). A Pi gains a model only when the
    # owner flips oracle_mode and sets inference up by hand.
    "oracle_mode": "deterministic",
}


BUILTIN_PROFILES = {
    "pi-light": _PI_HOME_SPEC,
    # The former name of pi-light. Kept so existing --profile
    # invocations and written configs keep working; it now means
    # the same light install (no model), not the old 1B pull.
    "raspberry-pi-home": _PI_HOME_SPEC,
    # A Linux board behind a screen. Not a television, and not a
    # USB accelerator: those cannot exec a job. Same deterministic
    # Oracle as Pi Light, chosen by name, never by guessing that
    # every arm64 machine is an appliance.
    "display-board": {
        "description": "Dedicated Linux board (a screen in front "
                       "of it is only a screen). Deterministic "
                       "Oracle, no local model.",
        "redact_patterns_extra": {
            "shadow_hash": r"\$[0-9a-z]+\$[A-Za-z0-9./]{20,}",
        },
        "protected_paths": ["/etc/shadow"],
        "max_result_view": "attested",
        "judge": "advisory",
        "oracle_mode": "deterministic",
    },
    "password-only": {
        "description": "Only the password hash matters on this box",
        "redact_patterns_extra": {
            "shadow_hash": r"\$[0-9a-z]+\$[A-Za-z0-9./]{20,}",
            "password_assignment": r"(?i)(password|passwd|pwd)\s*[=:]\s*\S+",
        },
        "protected_paths": ["/etc/shadow"],
        "max_result_view": "attested",
        "judge": "advisory",
    },
    # A box somebody else provisions for a tenant (docs/project/
    # hosting.md): password-only's redaction and ceiling, plus the
    # sandbox enforced, the audience check auditing, and no local
    # signal listener (nothing else runs on a hosted box). The
    # workspace root and runner_id come from the one-blob config
    # the provisioner writes (--config-json), not from here.
    "hosted": {
        "description": "A tenant's hosted runner: attested results, "
                       "advisory judge, bwrap enforced, no local "
                       "signals",
        "redact_patterns_extra": {
            "shadow_hash": r"\$[0-9a-z]+\$[A-Za-z0-9./]{20,}",
            "password_assignment": r"(?i)(password|passwd|pwd)\s*[=:]\s*\S+",
        },
        "protected_paths": ["/etc/shadow"],
        "max_result_view": "attested",
        "judge": "advisory",
        "local_signals": False,
        "security": {"modes": {"confinement": "enforce",
                               "audience": "audit"}},
    },
}


# The project default, set by the full eval battery (2026-10-18,
# hp-vmtest EVAL.md) under the owner's ranking: a clean catch
# with no invention first, then history/detail accuracy, then
# latency. qwen3:1.7b was one of only two models with two clean
# catches and no invented findings (the other, hermes3:8b,
# failed history and needs 8B-class RAM), and the only one of
# the two that also passed history and detail. llama3.2:3b, the
# previous default, stays the most reliable answerer but
# transplants the notable line onto the benign job under two of
# three phrasings -- an invention, which the ranking gates out.
# The known cost: qwen3 thinks before answering, and a thinking
# runaway can eat the per-question timeout; the catch ranking
# was bought with that latency on purpose.
DEFAULT_INFERENCE_MODEL = "qwen3:1.7b"

# --faster's model. qwen2.5:1.5b held this slot first: it follows
# format instructions far better than llama3.2:1b (which echoed the
# job index as raw JSON in field runs on a 2-core laptop). But in
# the Flag321 eval battery (2026-10-17, hp-vmtest EVAL.md) the
# 1.5B's verdicts were inconsistent across paraphrases -- flagging
# every job as malicious under one phrasing and none under another.
# qwen2.5:3b was the smallest model whose catch stayed steady in
# the field tests and the battery. The owner's rule for this slot:
# the faster option must still work when it ships. The pi-light
# profile pulls no model at all.
FASTER_INFERENCE_MODEL = "qwen2.5:3b"


def _profile_spec(profile) -> dict:
    """Spec dict for a builtin profile name or a JSON profile file.

    Used for profile keys the installer itself reads (oracle_mode).
    {} when the profile is unknown or unreadable.
    """
    if not isinstance(profile, str) or not profile:
        return {}
    if os.path.isfile(profile):
        try:
            with open(profile, encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    spec = BUILTIN_PROFILES.get(profile)
    return spec if isinstance(spec, dict) else {}


def profile_oracle_mode(profile):
    """The oracle_mode a profile asks for, or None.

    "deterministic" is Pi Light: the install must not install
    Ollama or download any model for it (see _setup_fresh_config).
    """
    mode = _profile_spec(profile).get("oracle_mode")
    if isinstance(mode, str) and mode.strip():
        return mode.strip()
    return None


def inference_model_for(profile, explicit=None, faster=False) -> str:
    """Which Ollama tag to pull.

    An explicit --inference-model always wins. --faster pulls
    FASTER_INFERENCE_MODEL (qwen2.5:3b). Otherwise a profile's own
    inference_model when it names one, and every other install
    keeps the project default. The pi-light profile names none:
    its installs skip inference entirely and never reach the pull.
    """
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    if faster:
        return FASTER_INFERENCE_MODEL
    name = profile or ""
    if name and os.path.isfile(name):
        try:
            with open(name, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and isinstance(data.get("profile"), str):
                name = data["profile"]
        except Exception:
            name = ""
    spec = BUILTIN_PROFILES.get(name) or {}
    model = spec.get("inference_model")
    if isinstance(model, str) and model.strip():
        return model.strip()
    return DEFAULT_INFERENCE_MODEL




# --- the one-blob config a provisioner hands a hosted box -----------

# Keys a blob may set. Everything a hosted runner needs that the
# profile cannot know: the secret, where the transport is, which box
# this is. A key outside this set is refused, so a blob cannot flip a
# security mode or widen the result view past what the profile set.
CONFIG_BLOB_KEYS = frozenset((
    "shared_secret", "runner_id", "workspace_root", "base_dir",
    "owner_instructions", "poll_interval_sec",
    "transport_queues", "transport_nats", "transport_dtls",
    "transports", "mailbox_user", "mailbox_password",
    "imap_host", "imap_port", "smtp_host", "smtp_port",
    "inference", "oracle_mode", "pong_platform",
))


def read_config_blob(spec):
    """The blob --config-json names: a JSON object inline, ``@path``
    for a file, or ``env:NAME`` for an environment variable holding
    the JSON. Returns a dict, or raises ValueError saying why not."""
    if spec is None:
        return {}
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError("config blob: empty")
    text = spec.strip()
    if text.startswith("@"):
        try:
            with open(text[1:], encoding="utf-8") as fh:
                text = fh.read()
        except OSError as e:
            raise ValueError(f"config blob: cannot read {text[1:]}: {e}")
    elif text.startswith("env:"):
        name = text[4:]
        text = os.environ.get(name)
        if text is None:
            raise ValueError(f"config blob: {name} is not set")
    try:
        data = json.loads(text)
    except ValueError as e:
        raise ValueError(f"config blob: not JSON: {e}")
    if not isinstance(data, dict):
        raise ValueError("config blob: must be a JSON object")
    bad = sorted(k for k in data if k not in CONFIG_BLOB_KEYS)
    if bad:
        raise ValueError("config blob: refused key(s) "
                         + ", ".join(bad)
                         + " (a profile sets security and the view)")
    return data


def merge_config_blob(cfg_path: str, spec) -> dict:
    """Write the blob's keys into config.json before the profile runs.

    The provisioner's one secret becomes the config: shared secret,
    transport block, runner id, workspace root. Keys already in the
    file are overwritten, since the blob is the deployment's word;
    the profile applied afterwards still owns security and the view.
    Returns the keys written."""
    data = read_config_blob(spec)
    if not data:
        return {}
    cfg = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (OSError, ValueError):
            cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
    cfg.update(data)
    _write_json(cfg_path, cfg)
    print(f"config blob: wrote {', '.join(sorted(data))}")
    return data



_INSTRUCTIONS_LOCK = threading.Lock()


def _read_config(path: str) -> dict:
    """Load a config object. A symlink is not followed."""
    if os.path.islink(path):
        raise OSError("refusing to follow a symlink config: %s" % path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config must be an object")
    return data


def _write_json(path: str, cfg: dict) -> None:
    """Atomic config write: whole or not at all, mode 0600, a symlink
    at path replaced rather than written through (guard/atomicio)."""
    _atomicio.write_json(path, cfg, indent=2, newline=True)


def set_instructions(cfg_path: str, text_in: str, append: bool) -> None:
    """Store a human-readable instruction string in config.json.

    --instructions replaces. --instructions-add appends a new paragraph.
    The value is a plain string, not a profile. Blank text is a no-op.
    Serialized so concurrent callers cannot tear the file.
    """
    text = (text_in or "").strip()
    if not text:
        return
    with _INSTRUCTIONS_LOCK:
        cfg = {}
        if os.path.islink(cfg_path):
            raise OSError("refusing to follow a symlink config: %s" % cfg_path)
        if os.path.exists(cfg_path):
            cfg = _read_config(cfg_path)
        current = cfg.get("owner_instructions") or ""
        if not isinstance(current, str):
            current = ""
        if append and current.strip():
            cfg["owner_instructions"] = current.rstrip() + "\n\n" + text
        else:
            cfg["owner_instructions"] = text
        _write_json(cfg_path, cfg)
        action = "appended" if append and current.strip() else "replaced"
        print(f"instructions: {action} ({len(cfg['owner_instructions'])} chars)")


def apply_instruction_flags(cfg_path: str, replace, add) -> None:
    """Apply installer instruction flags. --instructions-add wins if both are set."""
    if add:
        set_instructions(cfg_path, add, append=True)
    elif replace:
        set_instructions(cfg_path, replace, append=False)


# A release archive can bake in its default profile: the staged
# tree carries this marker file next to the installer, naming the
# profile to apply when the user names none. The pi-light archive
# ships one (its content is "pi-light"); the ordinary archives and
# the source tree carry none, so their defaults are exactly what
# they were before the marker existed.
PROFILE_MARKER = "default_profile"


def _bundled_default_profile(src_dir=None):
    """Profile named by the default_profile marker, or None.

    The marker lives beside the installer, in its own directory:
    the extracted archive folder for the release binary, runner/
    for a source checkout. Only a known built-in profile name is
    honored; a missing, empty, or unknown marker changes nothing.
    """
    if src_dir is None:
        src_dir = _src_dir()
    try:
        with open(os.path.join(src_dir, PROFILE_MARKER),
                  encoding="utf-8") as fh:
            name = fh.read().strip()
    except Exception:
        return None
    if name in BUILTIN_PROFILES:
        return name
    return None


def chosen_profile(explicit, skip: bool):
    """Profile name or path to apply. None when --no-profile is set.

    An explicit --profile wins. Otherwise the archive's bundled
    default (the default_profile marker), if it carries one.
    Otherwise detect_default_profile() picks.
    """
    if skip:
        return None
    if explicit:
        return explicit
    bundled = _bundled_default_profile()
    if bundled:
        return bundled
    return detect_default_profile()


# Hardware the CI proofs do not cover. Each one is refused with a
# reason, and the tests simulate them: a green job that claimed to
# boot a television would be a lie. A USB accelerator is not a
# computer either. Docker is Linux packaged, so it is allowed, and
# it is not treated as a new kind of machine.
_APPLIANCE_OS = ("tizen", "webos", "roku", "tvos")
# Android-class sets (Android TV, Google TV, Fire TV, Shield) are the
# one television family where a shell is obtainable: a sideloaded
# terminal environment gives the runner a real Python and the runner
# only needs outbound mail. The owner's decision (2026-10-21): warn,
# do not refuse. What decides is still the shell -- an Android
# environment that cannot exec (a signed TV app) is refused by the
# no-exec case below, exactly like any other set.
_ANDROID_OS = ("android",)
_ACCEL_VENDORS = {
    "1a6e": "coral",   # Coral USB, before the firmware load
    "18d1": "coral",   # Google, after the firmware load
    "03e7": "ncs",     # Intel Movidius / NCS
    "1e60": "hailo",
}


def host_decision(facts):
    """What an install should do on this machine.

    facts: platform, machine, device_model, in_container,
    accelerators (list of names), can_exec. Returns action
    "run" or "refuse", the profile a Linux install would
    suggest, and a note. An empty note means say nothing.
    """
    if not isinstance(facts, dict):
        facts = {}
    platform = str(facts.get("platform") or "")
    machine = str(facts.get("machine") or "").lower()
    model = str(facts.get("device_model") or "").lower()
    accels = [a for a in (facts.get("accelerators") or []) if a]
    container = bool(facts.get("in_container"))
    can_exec = facts.get("can_exec", True)
    plat = platform.lower()
    appliance = next((name for name in _APPLIANCE_OS if name in plat), None)
    if appliance:
        return _refuse_appliance(appliance, accels)
    android = any(name in plat for name in _ANDROID_OS)
    if android and can_exec is not False:
        return _warn_android(accels)
    if can_exec is False:
        return {
            "case": "no-exec",
            "action": "refuse",
            "profile": None,
            "note": "This environment cannot execute a shell, so "
                    "it cannot run a job. A signed app on a "
                    "television is that kind of environment. Put "
                    "a Linux board behind the screen and install "
                    "there with --profile display-board.",
        }
    runnable = plat.startswith("linux") or plat.startswith("freebsd") \
        or plat in ("win32", "darwin")
    if accels and not runnable:
        return _refuse_accelerator(accels)
    pi = "raspberry pi" in model
    if plat.startswith("linux") and pi:
        note = _accel_note(accels)
        return {"case": "pi", "action": "run",
                "profile": "pi-light", "note": note}
    if plat.startswith("linux") and container:
        note = ("Docker is the published Linux image, not a "
                "different machine. The proof that repair works "
                "with no bash is the minimal-userland job, not "
                "this image.")
        extra = _accel_note(accels)
        if extra:
            note = note + " " + extra
        return {"case": "docker", "action": "run",
                "profile": "password-only", "note": note}
    if plat.startswith("linux") and machine in ("aarch64", "arm64", "armv7l"):
        note = ("This is a Linux board, not a television. If the "
                "board is dedicated and a screen is only a "
                "screen, install with --profile display-board. "
                "That profile installs no model.")
        extra = _accel_note(accels)
        if extra:
            note = note + " " + extra
        return {"case": "display-candidate", "action": "run",
                "profile": "password-only", "note": note}
    if plat.startswith("linux") and accels:
        return {"case": "linux", "action": "run",
                "profile": "password-only", "note": _accel_note(accels)}
    if runnable:
        return {"case": plat.split()[0] if plat else "host",
                "action": "run", "profile": "password-only", "note": ""}
    return {"case": "other", "action": "run", "profile": None, "note": ""}


def _warn_android(accels):
    """Android with a shell: run, and say what the set will not do.

    The set can host the runner through a sideloaded terminal
    environment. What it cannot promise: a service that survives
    standby (the installer has no init to register with; the user
    keeps the terminal app alive or uses its boot hook), a model
    (no profile installs one here), or a sandbox (bwrap is not
    available). None of that is a reason to refuse a box that can
    execute a job; all of it is a reason to say so before copying
    files.
    """
    note = ("This machine is Android, including Android TV, Google "
            "TV, Fire TV, and Shield, with a shell available. The "
            "installer will proceed, with these limits stated: no "
            "service is registered here (keep the terminal "
            "environment running, or use its boot hook); no model "
            "is installed; no sandbox is available. Jobs run "
            "unsandboxed as the terminal app's user. A dedicated "
            "Linux board behind the screen is the stronger host: "
            "--profile display-board.")
    extra = _accel_note(accels)
    if extra:
        note = note + " " + extra
    return {"case": "android", "action": "run",
            "profile": "display-board", "note": note}


def _refuse_appliance(name, accels):
    names = {
        "tizen": "a Samsung Tizen television",
        "webos": "an LG webOS television",
        "roku": "a Roku",
        "tvos": "an Apple TV",
    }
    what = names.get(name, name)
    note = (f"This machine is {what}. Code signing can put an "
            f"app on the screen. It cannot give Homing Pigeon a "
            f"shell, and a job runs by executing a shell. The "
            f"installer will not install here. A Linux board "
            f"behind the set can: install on that board with "
            f"--profile display-board. The television stays a "
            f"screen.")
    extra = _accel_note(accels)
    if extra:
        note = note + " " + extra
    return {"case": name, "action": "refuse", "profile": None,
            "note": note}


def _refuse_accelerator(accels):
    listed = ", ".join(sorted(set(accels)))
    return {
        "case": "accelerator",
        "action": "refuse",
        "profile": None,
        "note": f"A USB accelerator ({listed}) is not a computer. "
                f"It cannot run the runner, and plugging it into "
                f"a television does not create a host. Install on "
                f"a Linux board. Pi Light and display-board do "
                f"not use the accelerator; a model is a later, "
                f"explicit choice.",
    }


def _accel_note(accels):
    if not accels:
        return ""
    listed = ", ".join(sorted(set(accels)))
    return (f"A USB accelerator is attached ({listed}). It is "
            f"not the runner, and this install will not use it. "
            f"Pi Light and display-board install no model.")


def _read_text(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception:
        return ""


def _path_exists(path):
    try:
        return os.path.exists(path)
    except Exception:
        return False


def _usb_accelerators():
    root = "/sys/bus/usb/devices"
    found = []
    try:
        names = os.listdir(root)
    except Exception:
        return found
    for name in names:
        vendor = _read_text(os.path.join(root, name, "idVendor")).strip().lower()
        kind = _ACCEL_VENDORS.get(vendor)
        if kind and kind not in found:
            found.append(kind)
    return found


def gather_host_facts(read_text=None, exists=None, platform_name=None,
                      machine=None, environ=None, usb_ids=None,
                      can_exec=True):
    """Facts for host_decision, from this machine or from probes.

    The probes are optional so a test can simulate a television
    without one being present.
    """
    read_text = read_text or _read_text
    exists = exists or _path_exists
    environ = os.environ if environ is None else environ
    if platform_name is None:
        platform_name = sys.platform
    if machine is None:
        import platform as _platform
        machine = _platform.machine()
    os_release = read_text("/etc/os-release")
    identity = os_release.lower()
    plat = str(platform_name)
    for marker, name in (("/etc/tizen-release", "tizen"),
                         ("/etc/webos-release", "webos")):
        if exists(marker):
            plat = name
    if "id=tizen" in identity or "id=webos" in identity:
        plat = "tizen" if "id=tizen" in identity else plat
        if "id=webos" in identity:
            plat = "webos"
    if environ.get("ANDROID_ROOT") or environ.get("ANDROID_DATA") \
            or "id=android" in identity or "android" in plat.lower():
        plat = "android"
    model = read_text("/proc/device-tree/model")
    if "raspberry pi" not in model.lower():
        cpu = read_text("/proc/cpuinfo")
        if "raspberry pi" in cpu.lower():
            model = cpu
    if usb_ids is None:
        accels = _usb_accelerators()
    else:
        accels = []
        for vendor in usb_ids:
            kind = _ACCEL_VENDORS.get(str(vendor).lower())
            if kind and kind not in accels:
                accels.append(kind)
    in_container = exists("/.dockerenv") or exists("/run/.containerenv")
    if not in_container:
        cgroup = read_text("/proc/1/cgroup")
        in_container = "docker" in cgroup or "containerd" in cgroup
    return {
        "platform": plat,
        "machine": machine,
        "device_model": model,
        "in_container": in_container,
        "accelerators": accels,
        "can_exec": can_exec,
    }


def host_install_gate(facts=None):
    """Print the hardware note. Return 2 when install must stop.

    Check, logs, uninstall, and wipe do not call this: a box
    that already has an install can still be inspected.
    """
    decision = host_decision(facts if facts is not None
                             else gather_host_facts())
    if decision.get("note"):
        print(decision["note"])
    if decision.get("action") != "run":
        return 2
    return None


def detect_default_profile() -> str:
    """Pick a profile automatically when the user did not name one.

    Raspberry Pi gets pi-light (full runner, deterministic Oracle,
    no model). Everything else gets password-only so the common
    case (only the password matters) is the default. --no-profile
    disables this.
    """
    # An Android-class box gets the profile the host check suggests for
    # it, display-board, not password-only and a pulled model (Q98
    # item 6); the same environment test gather_host_facts uses.
    if os.environ.get("ANDROID_ROOT") or os.environ.get("ANDROID_DATA"):
        return "display-board"
    # Pi detection: device-tree model or the classic cpuinfo hardware line.
    for path in ("/proc/device-tree/model", "/proc/cpuinfo"):
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                blob = f.read().lower()
            if "raspberry pi" in blob:
                return "pi-light"
        except Exception:
            pass
    return "password-only"


def apply_profile(cfg_path: str, profile: str) -> None:
    """Merge a named built-in profile or a JSON file into config.json.

    Mailbox credentials and shared_secret are never overwritten.
    """
    import json
    if not profile:
        return
    if os.path.isfile(profile):
        with open(profile, encoding="utf-8") as f:
            data = json.load(f)
        name = data.get("profile", profile)
    else:
        data = BUILTIN_PROFILES.get(profile)
        if not data:
            known = ", ".join(sorted(BUILTIN_PROFILES))
            print(f"profile: unknown {profile!r} (known: {known}); skipping")
            return
        name = profile
    cfg = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    # Dict keys merge so a profile cannot wipe patterns the owner already set.
    # A profile entry wins when the name clashes. Lists and scalars replace.
    for key in ("redact_patterns_extra", "worker_compartments"):
        if key not in data or not isinstance(data[key], dict):
            continue
        current = cfg.get(key)
        merged = dict(current) if isinstance(current, dict) else {}
        merged.update(data[key])  # pyrefly: ignore[no-matching-overload]  # guarded by isinstance dict above; data is unannotated config
        cfg[key] = merged
    for key in ("protected_paths", "max_result_view", "judge", "workspace_root",
                "max_query_budget", "output_retention_days", "worker_allowlist",
                "dag_mode", "require_review", "oracle_mode", "local_signals"):
        if key in data:
            cfg[key] = data[key]
    # security.modes merges one mode at a time, so a profile that
    # enforces confinement leaves the owner's other modes alone.
    modes = (data.get("security") or {}).get("modes") \
        if isinstance(data.get("security"), dict) else None
    if isinstance(modes, dict):
        sec = cfg.get("security") if isinstance(cfg.get("security"), dict) \
            else {}
        cur = sec.get("modes") if isinstance(sec.get("modes"), dict) else {}
        merged_modes = dict(cur)
        merged_modes.update({k: v for k, v in modes.items()
                             if isinstance(k, str) and isinstance(v, str)})
        sec = dict(sec)
        sec["modes"] = merged_modes
        cfg["security"] = sec
    cfg["profile"] = name
    _write_json(cfg_path, cfg)
    print(f"profile: applied {name}")


# --- sense collectors -------------------------------------------------
#
# The collectors docs/extend/senses.md names as sense suppliers: the
# installer can set them up next to the runner, and the matching
# runner/extensions/<name>-feed producer turns each one's
# output into signed alerts. The measured comparison behind
# these choices (footprints on a 2 vCPU / 7.7 GB box, next to
# the local model) is the campaign the senses doc cites; the
# short version: osquery is the lightest host-telemetry daemon
# that runs on every platform this installer targets (27 MB,
# JSON-lines differentials, no kernel privileges in scheduled-
# query mode), so it is the default. Zeek is supported and
# never a default (230 MB at idle). Falco and Sysmon for Linux
# can install successfully and still not function where the
# kernel denies BPF -- collector_health_rows() exists so
# --check reports that state instead of install-and-pray.

COLLECTOR_NAMES = ("osquery", "falco", "suricata", "zeek", "aide",
                   "softflowd", "sysmon", "wazuh")
COLLECTOR_DEFAULT = "osquery"
OSQUERY_RESULTS_LOG = "/var/log/osquery/osqueryd.results.log"
FALCO_ALERTS_LOG = "/var/log/falco/falco.json"
SURICATA_EVE_LOG = "/var/log/suricata/eve.json"
AIDE_REPORT_PATH = "/var/log/aide/aide.log"

# The installer's light osquery pack: name -> (query, interval
# seconds). The names are the contract osquery-feed reads: a
# name containing "processes" is a process query, "users" a
# user query, "listening_ports" a listener query.
OSQUERY_LIGHT_PACK = {
    "hp_processes": (
        "SELECT pid, name, path, cmdline FROM processes;", 300),
    "hp_users": (
        "SELECT uid, gid, username, shell FROM users;", 3600),
    "hp_listening_ports": (
        "SELECT port, protocol, address, pid FROM listening_ports;",
        300),
}


def osquery_config_text() -> str:
    """The osquery.conf this installer writes: the light pack.

    Schedule only. Logger and database settings live in the
    flags file, not here -- several of them are flags-only and
    a config copy is ignored with a warning (measured during
    the collector campaign). "removed": true so the results
    log carries removals; osquery-feed files them.
    """
    schedule = {}
    for name, (query, interval) in sorted(OSQUERY_LIGHT_PACK.items()):
        schedule[name] = {"query": query, "interval": interval,
                          "removed": True}
    return json.dumps({"schedule": schedule}, indent=2,
                      sort_keys=True) + "\n"


def osquery_flags_text(config_path, log_dir, database_path,
                       pidfile) -> str:
    """The osquery.flags this installer writes, one flag a line."""
    lines = [
        f"--config_path={config_path}",
        f"--database_path={database_path}",
        "--logger_plugin=filesystem",
        f"--logger_path={log_dir}",
        f"--pidfile={pidfile}",
        "--watchdog_level=1",
    ]
    return "\n".join(lines) + "\n"


def osquery_systemd_unit_text(binary) -> str:
    """The systemd unit for osqueryd; the package ships none."""
    return f"""[Unit]
Description=osquery daemon (Homing Pigeon light pack)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={binary} --flagfile=/etc/osquery/osquery.flags
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""


AIDE_WATCH_DIRS = ("/etc", "/bin", "/sbin", "/usr/bin", "/usr/sbin",
                   "/boot")


def aide_rules_text() -> str:
    """The scoped AIDE rules this installer ships.

    The vendor default walks the whole tree; on the campaign
    box its first database build did not finish in 9 minutes.
    Cost scales with the watched tree, so the scope is the
    system directories a tamperer cares about -- the same set
    the campaign measured (2,489 entries, ~3 s to build).
    """
    lines = [
        "# Homing Pigeon: scoped AIDE rules (see aide-feed).",
        "# The vendor whole-tree default does not scale; this",
        "# scope is deliberate. Add directories with the same",
        "# HP rule if the box earns them.",
        "HP = p+i+n+u+g+s+m+c+sha256",
    ]
    lines += [f"{d} HP" for d in AIDE_WATCH_DIRS]
    return "\n".join(lines) + "\n"


def aide_cron_text() -> str:
    """The daily AIDE check; its report is aide-feed's input."""
    return ("#!/bin/sh\n"
            "# Homing Pigeon: nightly AIDE check. The report is\n"
            "# consumed by the aide-feed extension; a nonzero\n"
            "# exit just means differences were found.\n"
            f"/usr/bin/aide --check > {AIDE_REPORT_PATH} 2>&1 "
            "|| true\n")


def chosen_collectors(args, profile) -> list:
    """Which collectors a fresh install sets up.

    An explicit --collector (repeatable) wins, even on Pi
    Light; --no-collector means none. Otherwise the default
    is osquery -- except a deterministic profile (Pi Light),
    whose whole point is that nothing extra runs: there the
    default is none and a collector is an explicit act.
    """
    if getattr(args, "no_collector", False):
        return []
    explicit = getattr(args, "collector", None)
    if explicit:
        out = []
        for name in explicit:
            if name in COLLECTOR_NAMES and name not in out:
                out.append(name)
        return out
    if profile_oracle_mode(profile) == "deterministic":
        return []
    return [COLLECTOR_DEFAULT]


def requested_collectors(args) -> list:
    """Explicit --collector/--no-collector only (existing
    installs): the names asked for, with no defaulting."""
    if getattr(args, "no_collector", False):
        return []
    out = []
    for name in getattr(args, "collector", None) or []:
        if name in COLLECTOR_NAMES and name not in out:
            out.append(name)
    return out


def install_collectors(names, args) -> list:
    """Set up each named collector; one outcome line per name.

    Returns the lines (also printed). Never raises: a failed
    collector is a reported outcome, not an aborted install.
    Wazuh installs only with --wazuh-manager -- the agent
    alone produces nothing on the box, so enrolling it
    against nothing would be a silent no-op install.
    """
    lines = []
    for name in names:
        try:
            if name == "wazuh" and not getattr(
                    args, "wazuh_manager", None):
                line = ("collector wazuh: skipped -- the agent "
                        "needs its manager; pass --wazuh-manager "
                        "ADDRESS. Without one it enrolls against "
                        "nothing and produces no alerts here.")
            elif sys.platform.startswith("linux"):
                line = _install_collector_linux(name, args)
            elif sys.platform == "darwin":
                line = _install_collector_darwin(name, args)
            elif sys.platform == "win32":
                line = _install_collector_windows(name, args)
            else:
                line = (f"collector {name}: no install channel "
                        f"on this platform; see docs/extend/senses.md")
        except Exception as e:
            line = f"collector {name}: install failed: {e}"
        lines.append(line)
        print(line)
    return lines


def _download(url) -> bytes:
    import urllib.request
    req = urllib.request.Request(
        url, headers={"User-Agent": "homing-pigeon-install"})
    with urllib.request.urlopen(req, timeout=180) as fh:
        return fh.read()


def _write_keyring(urls, dest) -> str:
    """Fetch an apt signing key (first URL that answers) and
    write it as a binary keyring; armored keys are dearmored."""
    data = b""
    for url in urls:
        try:
            data = _download(url)
        except Exception:
            data = b""
        if data:
            break
    if not data:
        raise RuntimeError(f"no signing key from {urls[0]}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if data.startswith(b"-----BEGIN PGP"):
        subprocess.run(["gpg", "--batch", "--yes", "--dearmor",
                        "-o", dest], input=data, check=True)
    else:
        with open(dest, "wb") as fh:
            fh.write(data)
    return dest


def _apt_repo(name, line, key_urls) -> None:
    keyring = f"/usr/share/keyrings/{name}-archive-keyring.gpg"
    _write_keyring(key_urls, keyring)
    with open(f"/etc/apt/sources.list.d/{name}.list", "w",
              encoding="utf-8") as fh:
        fh.write(line.replace("{keyring}", keyring) + "\n")
    run(["apt-get", "update"])


def _apt_install(packages) -> None:
    run(["apt-get", "install", "-y", *packages])


def _os_release_version() -> str:
    try:
        with open("/etc/os-release", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VERSION_ID="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def _newest_from_listing(url, pattern):
    """Newest versioned filename in a vendor directory listing."""
    text = _download(url).decode("utf-8", errors="replace")
    found = {}
    for name, ver in re.findall(pattern, text):
        found[tuple(int(p) for p in ver.split("."))] = name
    if not found:
        raise RuntimeError(f"no package matching in {url}")
    return url + found[max(found)]


def _osquery_binary() -> str:
    return (shutil.which("osqueryd")
            or "/opt/osquery/bin/osqueryd")


def _install_osquery_linux() -> str:
    _apt_repo(
        "osquery",
        "deb [arch=amd64,arm64 signed-by={keyring}] "
        "https://pkg.osquerypackages.com/deb deb main",
        ["https://pkg.osquerypackages.com/deb/"
         "osquery-archive-keyring.gpg",
         "https://pkg.osquerypackages.com/deb/pubkey.gpg"])
    _apt_install(["osquery"])
    for d in ("/etc/osquery", "/var/osquery", "/var/log/osquery"):
        os.makedirs(d, exist_ok=True)
    _write_text("/etc/osquery/osquery.conf", osquery_config_text())
    _write_text("/etc/osquery/osquery.flags", osquery_flags_text(
        "/etc/osquery/osquery.conf", "/var/log/osquery",
        "/var/osquery/osquery.db", "/var/run/osqueryd.pidfile"))
    _write_text("/etc/systemd/system/osqueryd.service",
                osquery_systemd_unit_text(_osquery_binary()))
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", "osqueryd.service"])
    pack = ", ".join(sorted(OSQUERY_LIGHT_PACK))
    return (f"collector osquery: installed and enabled with the "
            f"light pack ({pack}); results log "
            f"{OSQUERY_RESULTS_LOG} feeds osquery-feed "
            f"(measured ~27 MB RSS, ~0.1% CPU)")


def _install_falco_linux() -> str:
    import glob as _glob
    channel = "vendor apt repo"
    try:
        _apt_repo(
            "falcosecurity",
            "deb [signed-by={keyring}] "
            "https://download.falco.org/packages/deb stable main",
            ["https://falco.org/repo/falcosecurity-packages.asc"])
        _apt_install(["falco"])
    except Exception:
        # The repo's CDN redirect defeats some apt fetchers
        # (measured through this project's own proxy); the
        # vendor .deb, fetched directly, is the fallback.
        import platform as _platform
        arch = {"x86_64": "x86_64", "aarch64": "aarch64"}.get(
            _platform.machine(), "x86_64")
        url = _newest_from_listing(
            "https://download.falco.org/packages/deb/stable/",
            r"(falco-(\d+\.\d+\.\d+)-" + arch + r"\.deb)")
        path = os.path.join(tempfile.gettempdir(),
                            os.path.basename(url))
        with open(path, "wb") as fh:
            fh.write(_download(url))
        try:
            run(["dpkg", "-i", path])
        except Exception:
            run(["apt-get", "install", "-f", "-y"])
            run(["dpkg", "-i", path])
        channel = "vendor .deb (apt repo unreachable)"
    os.makedirs("/var/log/falco", exist_ok=True)
    units = sorted(
        _glob.glob("/lib/systemd/system/falco*.service")
        + _glob.glob("/etc/systemd/system/falco*.service"))
    units = [u for u in units if not u.endswith(".d")]
    routed = ""
    if units:
        unit = os.path.basename(units[0])
        drop = f"/etc/systemd/system/{unit}.d"
        os.makedirs(drop, exist_ok=True)
        binary = shutil.which("falco") or "/usr/bin/falco"
        _write_text(
            os.path.join(drop, "10-homing-pigeon.conf"),
            "[Service]\nExecStart=\n"
            f"ExecStart={binary} -o json_output=true "
            f"-o file_output.enabled=true "
            f"-o file_output.filename={FALCO_ALERTS_LOG} "
            f"-o stdout_output.enabled=false\n")
        run(["systemctl", "daemon-reload"])
        run(["systemctl", "enable", "--now", unit])
        routed = f"; JSON alerts routed to {FALCO_ALERTS_LOG}"
    return (f"collector falco: installed via {channel}{routed}. "
            f"Falco runs only where the kernel allows its "
            f"driver/BPF -- install.exe --check probes that "
            f"and reports it; an install success here is not a "
            f"collection guarantee.")


def _install_collector_linux(name, args) -> str:
    if name == "osquery":
        return _install_osquery_linux()
    if name == "falco":
        return _install_falco_linux()
    if name == "suricata":
        _apt_install(["suricata"])
        run(["systemctl", "enable", "--now", "suricata"])
        return (f"collector suricata: installed and enabled; "
                f"eve.json at {SURICATA_EVE_LOG} feeds "
                f"suricata-feed. Measured ~52 MB RSS with the "
                f"distro's minimal ruleset only -- a production "
                f"ruleset is several times that (unmeasured).")
    if name == "zeek":
        ver = _os_release_version()
        base = ("https://download.opensuse.org/repositories/"
                f"security:/zeek/xUbuntu_{ver}")
        _apt_repo("zeek",
                  f"deb [signed-by={{keyring}}] {base}/ /",
                  [f"{base}/Release.key"])
        _apt_install(["zeek"])
        return ("collector zeek: installed (vendor OBS repo). "
                "Measured ~230 MB RSS at idle -- the heavyweight "
                "of the slate, supported and never a default. "
                "It starts per interface by the owner's hand: "
                "/opt/zeek/bin/zeek -i <iface> local; logs land "
                "in /opt/zeek/logs and feed zeek-feed.")
    if name == "aide":
        _apt_install(["aide"])
        os.makedirs("/etc/aide/aide.conf.d", exist_ok=True)
        os.makedirs("/var/lib/aide", exist_ok=True)
        os.makedirs("/var/log/aide", exist_ok=True)
        _write_text("/etc/aide/aide.conf.d/99-homing-pigeon",
                    aide_rules_text())
        _write_text("/etc/cron.daily/homing-pigeon-aide",
                    aide_cron_text(), 0o755)
        run(["aide", "--init"])
        for cand in ("/var/lib/aide/aide.db.new.gz",
                     "/var/lib/aide/aide.db.new"):
            if os.path.isfile(cand):
                os.replace(cand, "/var/lib/aide/aide.db"
                           + (".gz" if cand.endswith(".gz") else ""))
                break
        dirs = ", ".join(AIDE_WATCH_DIRS)
        return (f"collector aide: installed with the scoped "
                f"config ({dirs} -- the vendor whole-tree "
                f"default did not finish its first build in 9 "
                f"minutes on the campaign box), database "
                f"initialized, daily check in cron writing "
                f"{AIDE_REPORT_PATH} for aide-feed. No daemon: "
                f"0 MB between scans.")
    if name == "softflowd":
        _apt_install(["softflowd"])
        return ("collector softflowd: installed (measured "
                "~7 MB RSS, ~0% CPU -- the lightest always-on "
                "collector measured). It runs per interface by "
                "the owner's hand: softflowd -i <iface> "
                "-n 127.0.0.1:2055 exports flows to the "
                "softflowd-feed producer, which is the "
                "collector that decodes them.")
    if name == "sysmon":
        ver = _os_release_version()
        path = os.path.join(tempfile.gettempdir(),
                            "packages-microsoft-prod.deb")
        with open(path, "wb") as fh:
            fh.write(_download(
                "https://packages.microsoft.com/config/ubuntu/"
                f"{ver}/packages-microsoft-prod.deb"))
        run(["dpkg", "-i", path])
        run(["apt-get", "update"])
        _apt_install(["sysmonforlinux"])
        return ("collector sysmon: Sysmon for Linux installed "
                "from the Microsoft repo. Whether it collects "
                "depends on the kernel allowing its BPF objects "
                "-- install.exe --check probes that and reports "
                "INSTALLED-BUT-CANNOT-RUN where the kernel "
                "says no.")
    if name == "wazuh":
        _apt_repo("wazuh",
                  "deb [signed-by={keyring}] "
                  "https://packages.wazuh.com/4.x/apt/ stable main",
                  ["https://packages.wazuh.com/key/GPG-KEY-WAZUH"])
        env = dict(os.environ)
        env["WAZUH_MANAGER"] = str(args.wazuh_manager)
        print("+ apt-get install -y wazuh-agent "
              f"(WAZUH_MANAGER={args.wazuh_manager})")
        subprocess.run(["apt-get", "install", "-y", "wazuh-agent"],
                       check=True, env=env)
        run(["systemctl", "enable", "--now", "wazuh-agent"])
        return (f"collector wazuh: agent installed and set to "
                f"enroll against manager {args.wazuh_manager}. "
                f"Its alerts live on that manager, not on this "
                f"box; wazuh-feed reads an alerts.json the "
                f"owner lands here (see docs/extend/senses.md).")
    return f"collector {name}: unknown collector"


def _install_collector_darwin(name, args) -> str:
    if name == "osquery":
        if shutil.which("brew"):
            run(["brew", "install", "--cask", "osquery"])
        else:
            return ("collector osquery: not installed -- no "
                    "Homebrew on this box to fetch the official "
                    "pkg. Install osquery from osquery.io, then "
                    "the config below is all this installer "
                    "would have added.")
        os.makedirs("/var/osquery", exist_ok=True)
        os.makedirs("/var/log/osquery", exist_ok=True)
        _write_text("/var/osquery/osquery.conf",
                    osquery_config_text())
        _write_text("/var/osquery/osquery.flags",
                    osquery_flags_text(
                        "/var/osquery/osquery.conf",
                        "/var/log/osquery",
                        "/var/osquery/osquery.db",
                        "/var/run/osqueryd.pidfile"))
        for plist in ("/Library/LaunchDaemons/"
                      "com.osquery.osqueryd.plist",
                      "/Library/LaunchDaemons/io.osquery.agent.plist"):
            if os.path.isfile(plist):
                subprocess.run(["launchctl", "bootout", "system",
                                plist], check=False)
                subprocess.run(["launchctl", "bootstrap", "system",
                                plist], check=False)
                break
        return ("collector osquery: installed with the light "
                "pack; results log "
                "/var/log/osquery/osqueryd.results.log feeds "
                "osquery-feed.")
    if name == "sysmon":
        return ("collector sysmon: not installed -- Sysmon "
                "for macOS is a Sysinternals download this "
                "installer does not fetch. sysmon-feed reads "
                "its events once it is in place.")
    return (f"collector {name}: no first-class macOS install "
            f"channel in this installer; see docs/extend/senses.md "
            f"for what upstream offers.")


def _install_collector_windows(name, args) -> str:
    if name == "osquery":
        if not shutil.which("winget"):
            return ("collector osquery: not installed -- no "
                    "winget on this box to fetch the official "
                    "MSI. Install osquery from osquery.io; the "
                    "light pack config is osquery_config_text() "
                    "in runner/ops/install.py.")
        run(["winget", "install", "--id", "osquery.osquery",
             "-e", "--silent", "--accept-source-agreements",
             "--accept-package-agreements"])
        home = r"C:\Program Files\osquery"
        if os.path.isdir(home):
            _write_text(os.path.join(home, "osquery.conf"),
                        osquery_config_text())
            _write_text(os.path.join(home, "osquery.flags"),
                        osquery_flags_text(
                            os.path.join(home, "osquery.conf"),
                            os.path.join(home, "log"),
                            os.path.join(home, "osquery.db"),
                            os.path.join(home, "osqueryd.pid")))
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Restart-Service osqueryd -ErrorAction "
                 "SilentlyContinue"], check=False)
        return ("collector osquery: installed with the light "
                "pack; its results log (osqueryd.results.log "
                "in the osquery log directory) feeds "
                "osquery-feed.")
    if name == "sysmon":
        return ("collector sysmon: not installed -- Sysmon is "
                "a Sysinternals download this installer does "
                "not fetch. sysmon-feed reads its ProcessCreate "
                "events once it is in place; it is the original "
                "the Linux port mirrors.")
    if name == "wazuh":
        url = _newest_from_listing(
            "https://packages.wazuh.com/4.x/windows/",
            r"(wazuh-agent-(\d+\.\d+\.\d+)-\d+\.msi)")
        path = os.path.join(tempfile.gettempdir(),
                            os.path.basename(url))
        with open(path, "wb") as fh:
            fh.write(_download(url))
        run(["msiexec", "/i", path, "/q",
             f"WAZUH_MANAGER={args.wazuh_manager}"])
        return (f"collector wazuh: agent installed against "
                f"manager {args.wazuh_manager}. Its alerts "
                f"live on that manager; wazuh-feed reads an "
                f"alerts.json the owner lands on this box.")
    return (f"collector {name}: Linux/BSD-only upstream; no "
            f"Windows install channel. See docs/extend/senses.md.")


# --- collector health (the --check rows) ------------------------------
#
# collector_health_rows() is pure: it judges a facts dict, so
# the states are unit-tested with fakes and --check never has
# to be run against a machine that happens to have a collector.
# States are exactly WORKS / INSTALLED-BUT-CANNOT-RUN / ABSENT.
# The measured reason this exists: Falco and Sysmon for Linux
# install cleanly and then silently collect nothing where the
# kernel denies BPF. An installer that cannot say that is
# install-and-pray.

COLLECTOR_HEALTH_STATES = ("WORKS", "INSTALLED-BUT-CANNOT-RUN",
                           "ABSENT")


def _bpf_loadable():
    """Can this kernel load a trivial BPF program?

    True/False on Linux when the syscall answers; None when
    the question cannot be asked here (other platform, unknown
    architecture, no libc). A two-instruction socket-filter
    program: r0 = 0; exit. The probe is the measurement
    campaign's own test -- the host denied it to a container
    holding CAP_BPF, which is exactly the silent-failure mode
    the health rows exist to name.
    """
    if not sys.platform.startswith("linux"):
        return None
    try:
        import ctypes
        import platform as _platform
        nr = {"x86_64": 321, "amd64": 321, "aarch64": 280}.get(
            _platform.machine())
        if nr is None:
            return None
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        insns = (ctypes.c_ubyte * 16)(
            0xB7, 0, 0, 0, 0, 0, 0, 0,
            0x95, 0, 0, 0, 0, 0, 0, 0)
        license_buf = ctypes.create_string_buffer(b"GPL", 4)
        attr = (ctypes.c_ubyte * 128)()
        import struct as _struct
        _struct.pack_into("<I", attr, 0, 1)  # BPF_PROG_TYPE_SOCKET_FILTER
        _struct.pack_into("<I", attr, 4, 2)  # insn count
        _struct.pack_into("<Q", attr, 8, ctypes.addressof(insns))
        _struct.pack_into("<Q", attr, 16,
                          ctypes.addressof(license_buf))
        fd = libc.syscall(nr, 5, attr, 128)  # 5 = BPF_PROG_LOAD
        if fd >= 0:
            os.close(fd)
            return True
        return False
    except Exception:
        return None


def _service_active(unit) -> bool:
    try:
        out = subprocess.run(["systemctl", "is-active", unit],
                             capture_output=True, text=True,
                             timeout=10)
        return out.stdout.strip() == "active"
    except Exception:
        return False


def _proc_running(comm) -> bool:
    """True when a process with this exact comm name exists."""
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open(os.path.join("/proc", pid, "comm"),
                          encoding="utf-8") as fh:
                    if fh.read().strip() == comm:
                        return True
            except OSError:
                continue
    except OSError:
        pass
    return False


def _artifact_age(path):
    try:
        return max(0.0, time.time() - os.path.getmtime(path))
    except OSError:
        return None


def _which_safe(binary):
    """shutil.which that cannot raise: on a platform where the
    interpreter's win32 helpers are absent (tests patch
    sys.platform on a POSIX interpreter), which() itself blows
    up -- a health probe must answer falsely instead."""
    try:
        return shutil.which(binary)
    except Exception:
        return None


def collector_health_facts() -> dict:
    """Gather what collector_health_rows() judges. Thin and
    defensive: every probe that can fail answers falsely."""
    import glob as _glob
    facts = {"installed": {}, "service_active": {},
             "running": {}, "bpf_ok": None, "falco_device": False,
             "sysmon_telemetry_error": False, "aide_db": False,
             "wazuh_manager": False, "artifact_age_sec": {}}
    paths = {"osquery": ["/opt/osquery/bin/osqueryd"],
             "zeek": ["/opt/zeek/bin/zeek"]}
    for name in COLLECTOR_NAMES:
        if name == "wazuh":
            facts["installed"][name] = os.path.isdir("/var/ossec")
            continue
        binary = {"osquery": "osqueryd", "sysmon": "sysmon"}.get(
            name, name)
        found = _which_safe(binary) is not None
        if not found:
            found = any(os.path.isfile(p)
                        for p in paths.get(name, []))
        facts["installed"][name] = found
    units = {"osquery": "osqueryd", "suricata": "suricata",
             "sysmon": "sysmon", "wazuh": "wazuh-agent"}
    falco_units = [os.path.basename(u)[:-len(".service")] for u in
                   _glob.glob("/lib/systemd/system/falco*.service")]
    if falco_units:
        units["falco"] = sorted(falco_units)[0]
    for name, unit in units.items():
        facts["service_active"][name] = _service_active(unit)
    for name in ("zeek", "softflowd"):
        facts["running"][name] = _proc_running(name)
    linux = sys.platform.startswith("linux")
    if linux and (facts["installed"].get("falco")
                  or facts["installed"].get("sysmon")):
        facts["bpf_ok"] = _bpf_loadable()
    facts["falco_device"] = os.path.exists("/dev/falco0")
    if linux and facts["installed"].get("sysmon"):
        try:
            out = subprocess.run(
                ["journalctl", "-u", "sysmon", "--no-pager",
                 "-n", "300"], capture_output=True, text=True,
                timeout=15)
            text = out.stdout + out.stderr
            facts["sysmon_telemetry_error"] = (
                "Telemetry failed" in text
                or "bpf_object__probe_loading" in text)
        except Exception:
            pass
    facts["aide_db"] = (os.path.isfile("/var/lib/aide/aide.db")
                        or os.path.isfile(
                            "/var/lib/aide/aide.db.gz"))
    try:
        with open("/var/ossec/etc/ossec.conf",
                  encoding="utf-8") as fh:
            text = fh.read()
        facts["wazuh_manager"] = ("<address>" in text
                                  and "MANAGER_IP" not in text)
    except OSError:
        pass
    for name, path in (("osquery", OSQUERY_RESULTS_LOG),
                       ("suricata", SURICATA_EVE_LOG),
                       ("falco", FALCO_ALERTS_LOG)):
        facts["artifact_age_sec"][name] = _artifact_age(path)
    return facts


def collector_health_rows(facts) -> list:
    """Judge facts -> [(name, state, detail)] per collector.

    The states are the contract: WORKS,
    INSTALLED-BUT-CANNOT-RUN, ABSENT. Detail says why, in the
    operator's vocabulary, including the artifact age where a
    feed file exists.
    """
    inst = facts.get("installed") or {}
    active = facts.get("service_active") or {}
    running = facts.get("running") or {}
    ages = facts.get("artifact_age_sec") or {}
    bpf = facts.get("bpf_ok")
    rows = []

    def age_note(name):
        age = ages.get(name)
        if age is None:
            return ""
        return f"; last output {int(age)}s ago"

    if not inst.get("osquery"):
        rows.append(("osquery", "ABSENT",
                     "not installed (it is the default collector "
                     "on a fresh install)"))
    elif active.get("osquery"):
        rows.append(("osquery", "WORKS",
                     "osqueryd is running the light pack"
                     + age_note("osquery")))
    else:
        rows.append(("osquery", "INSTALLED-BUT-CANNOT-RUN",
                     "installed but osqueryd is not running"))
    if not inst.get("falco"):
        rows.append(("falco", "ABSENT", "not installed"))
    elif bpf is False and not facts.get("falco_device"):
        rows.append(("falco", "INSTALLED-BUT-CANNOT-RUN",
                     "the kernel denied its driver/BPF in this "
                     "environment -- installed, but it cannot "
                     "collect here"))
    elif active.get("falco"):
        rows.append(("falco", "WORKS",
                     "service is running" + age_note("falco")))
    elif facts.get("falco_device"):
        rows.append(("falco", "INSTALLED-BUT-CANNOT-RUN",
                     "driver device present but the service is "
                     "not running"))
    else:
        rows.append(("falco", "INSTALLED-BUT-CANNOT-RUN",
                     "service is not running (BPF capability "
                     + ("probes OK" if bpf else "unknown") + ")"))
    if not inst.get("suricata"):
        rows.append(("suricata", "ABSENT", "not installed"))
    elif active.get("suricata"):
        rows.append(("suricata", "WORKS",
                     "service is running" + age_note("suricata")))
    else:
        rows.append(("suricata", "INSTALLED-BUT-CANNOT-RUN",
                     "installed but the service is not running"))
    if not inst.get("zeek"):
        rows.append(("zeek", "ABSENT", "not installed"))
    elif running.get("zeek"):
        rows.append(("zeek", "WORKS",
                     "running (started per interface)"))
    else:
        rows.append(("zeek", "INSTALLED-BUT-CANNOT-RUN",
                     "installed, not running -- Zeek starts per "
                     "interface by the owner's hand, and idles "
                     "near 230 MB: never a default"))
    if not inst.get("aide"):
        rows.append(("aide", "ABSENT", "not installed"))
    elif not facts.get("aide_db"):
        rows.append(("aide", "INSTALLED-BUT-CANNOT-RUN",
                     "installed but its database is not "
                     "initialized (aide --init)"))
    else:
        rows.append(("aide", "WORKS",
                     "batch: checks run from the schedule; "
                     "detection latency is the schedule, and "
                     "idle cost is zero"))
    if not inst.get("softflowd"):
        rows.append(("softflowd", "ABSENT", "not installed"))
    elif running.get("softflowd"):
        rows.append(("softflowd", "WORKS",
                     "running (started per interface)"))
    else:
        rows.append(("softflowd", "INSTALLED-BUT-CANNOT-RUN",
                     "installed, not running -- it starts per "
                     "interface by the owner's hand"))
    if not inst.get("sysmon"):
        rows.append(("sysmon", "ABSENT", "not installed"))
    elif facts.get("sysmon_telemetry_error"):
        rows.append(("sysmon", "INSTALLED-BUT-CANNOT-RUN",
                     "telemetry failed to start: the kernel "
                     "denied its BPF objects"))
    elif bpf is False:
        rows.append(("sysmon", "INSTALLED-BUT-CANNOT-RUN",
                     "the kernel denies trivial BPF loads in "
                     "this environment, which Sysmon needs"))
    elif active.get("sysmon"):
        rows.append(("sysmon", "WORKS", "service is running"))
    else:
        rows.append(("sysmon", "INSTALLED-BUT-CANNOT-RUN",
                     "installed but the service is not running"))
    if not inst.get("wazuh"):
        rows.append(("wazuh", "ABSENT",
                     "not installed (it needs a manager; see "
                     "docs/extend/senses.md)"))
    elif not facts.get("wazuh_manager"):
        rows.append(("wazuh", "INSTALLED-BUT-CANNOT-RUN",
                     "agent installed with no manager configured: "
                     "it forwards to nothing and produces no "
                     "alerts on this box"))
    elif active.get("wazuh"):
        rows.append(("wazuh", "WORKS",
                     "agent is running against its manager; "
                     "alerts live on the manager, and wazuh-feed "
                     "reads an alerts.json landed on this box"))
    else:
        rows.append(("wazuh", "INSTALLED-BUT-CANNOT-RUN",
                     "manager configured but the agent service "
                     "is not running"))
    return rows


def _ollama_up(port=11434) -> bool:
    import socket
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def daemon_popen_kwargs(windows: bool) -> dict:
    """Popen kwargs for a helper that must outlive this process.

    start_new_session is POSIX-only. On Windows it raises ValueError
    before the process is created.
    """
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if windows:
        detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        kw["creationflags"] = detached | group
    else:
        kw["start_new_session"] = True
    return kw


def _win_quote(arg: str) -> str:
    """Quote one argument for schtasks /TR. Not POSIX shlex quoting."""
    if arg == "" or any(c in arg for c in ' \t"'):
        return '"' + arg.replace('"', r'\"') + '"'
    return arg


def windows_task_command(dst_dir: str, cfg_path: str, extra=()) -> str:
    argv = [*_runner_argv(dst_dir), "--config", cfg_path, *list(extra or ())]
    return " ".join(_win_quote(str(a)) for a in argv)


def ensure_ollama_running() -> bool:
    """Start the Ollama daemon if it is not already listening on loopback."""
    if _ollama_up():
        return True
    exe = _ollama_bin()
    if not exe:
        print("inference: ollama installed but the binary is not on PATH; "
              "open a fresh terminal so PATH picks it up, then re-run install.exe")
        return False
    import subprocess
    try:
        subprocess.Popen(
            [exe, "serve"],
            **daemon_popen_kwargs(os.name == "nt"),
        )
    except Exception as e:
        print(f"inference: could not start ollama serve ({e})")
        return False
    for _ in range(20):
        if _ollama_up():
            print("inference: ollama daemon started")
            return True
        time.sleep(0.5)
    print("inference: ollama daemon did not become ready")
    return False


def install_ollama_and_model(cfg_path: str, model: str, skip: bool) -> bool:
    """Install Ollama and pull a model so the Oracle ask op works out of the box.

    Skipped entirely when skip is True (--no-inference). Failures are
    non-fatal: the runner still installs; ask stays off until the owner
    sets a loopback endpoint. Returns True when the inference block was
    written to the config.
    """
    if skip:
        print("inference: skipped (--no-inference)")
        return False
    plat = sys.platform
    if _ollama_bin():
        print("inference: ollama already present")
    else:
        print("inference: installing ollama (this may take a few minutes)...")
        try:
            if plat.startswith("linux"):
                run(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"])
            elif plat == "darwin":
                if _which("brew"):
                    run(["brew", "install", "ollama"])
                else:
                    print("inference: Homebrew not found; install Ollama from https://ollama.com and re-run, or pass --no-inference")
                    return False
            elif plat == "win32":
                if _which("winget"):
                    run(["winget", "install", "--id", "Ollama.Ollama", "-e", "--accept-source-agreements", "--accept-package-agreements"])
                else:
                    print("inference: winget not found; install Ollama from https://ollama.com and re-run, or pass --no-inference")
                    return False
            else:
                print(f"inference: no automatic Ollama install for {plat}; pass --no-inference or install manually")
                return False
        except Exception as e:
            print(f"inference: Ollama install failed ({e}); ask is off. Pass --no-inference to silence this.")
            return False
    # Ensure the daemon is reachable, then pull the model.
    exe = _ollama_bin()
    if not exe:
        print("inference: ollama binary not found after install; "
              "open a fresh terminal and re-run install.exe --inference-only")
        return False
    if not ensure_ollama_running():
        return False
    try:
        run([exe, "pull", model])
    except Exception as e:
        print(f"inference: model pull failed ({e}); ask is off until a loopback model is configured")
        return False
    # Point config at the local server.
    try:
        import json
        cfg = {}
        if os.path.exists(cfg_path):
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["inference"] = {
            "endpoint": "http://127.0.0.1:11434/v1",
            "model": model,
            "max_answer_chars": 2000,
            "timeout_sec": 180,
        }
        _write_json(cfg_path, cfg)
        print(f"inference: configured endpoint http://127.0.0.1:11434/v1 model {model}")
        return True
    except Exception as e:
        print(f"inference: could not write config ({e})")
        return False


def _warn_personal_documents():
    """Best effort. A missing module must not stop an install."""
    try:
        try:
            from runner.oracle.personal_docs import warn_if_personal_documents
        except ImportError:
            from oracle.personal_docs import warn_if_personal_documents
        warn_if_personal_documents()
    except Exception:
        return


def main() -> int:
    # --help is a document here too, same hand as the runner's:
    # chapters in reading order, worked examples in the epilog.
    ap = argparse.ArgumentParser(
        description=(
            "Install Homing Pigeon as a service on this machine.\n"
            "Copies the runner into place, writes config.json,\n"
            "and registers the service so the agent starts at\n"
            "boot and runs the jobs your cloud SI signs."),
        epilog=(
            "examples:\n"
            "  install.py\n"
            "      install with the defaults\n"
            "  install.py --verbose --poll-interval 30\n"
            "      bake the flags you tested with into the "
            "service\n"
            "  install.py --check\n"
            "      verify an existing install; change nothing\n"
            "  install.py --logs --follow\n"
            "      watch the runner log\n"
            "\n"
            "The flags in the last group are written into the\n"
            "service command, so the installed agent runs with\n"
            "exactly the flags you tested with."),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version",
                    version="%(prog)s " + __version__)
    g = ap.add_argument_group(
        "where it installs",
        "The one-home layout on Windows puts binaries, config,\n"
        "and state under one root; elsewhere the runner lives\n"
        "in ~/.homing-pigeon.")
    g.add_argument("--dir", default=None, metavar="DIR",
                   help="binary install dir (default: <home>/bin on "
                        "Windows, ~/.homing-pigeon elsewhere). On "
                        "Windows, --dir without --home keeps the "
                        "legacy layout: binaries and config.json "
                        "both land in --dir.")
    g.add_argument("--home", default=None, metavar="DIR",
                   help="Windows: the one-home root (default: "
                        "C:\\homing-pigeon). Holds bin/, config.json, "
                        "state/, install-receipt.json.")
    g.add_argument("--config", default=None, metavar="PATH",
                   help="config file to use "
                        "(default: <dir>/config.json)")
    g.add_argument("--system", action="store_true",
                   help="Linux: install a system-wide systemd unit "
                        "(needs root)")
    g.add_argument("--run-as", default=None, metavar="USER",
                   help="Windows: run the scheduled task as USER "
                        "instead of SYSTEM (least privilege; "
                        "schtasks prompts for the account password "
                        "unless it is a service account)")
    g = ap.add_argument_group(
        "instead of installing",
        "Do one of these and exit; nothing is installed.")
    g.add_argument("--rearm", action="store_true",
                   help="arm the panic word, or release a box it "
                        "stopped, and print a new word (Q100)")
    g.add_argument("--check", action="store_true",
                   help="doctor: verify the one-home layout, "
                        "receipt, service task, config, and "
                        "inference endpoint")
    g.add_argument("--console", action="store_true",
                   help="Windows: stop the HomingPigeon task, run "
                        "the agent in this terminal with live logs, "
                        "restart the task on exit")
    g.add_argument("--logs", action="store_true",
                   help="print the tail of the runner log")
    g.add_argument("--follow", action="store_true",
                   help="with --logs: keep following the log "
                        "(Ctrl+C stops)")
    g.add_argument("--lines", type=int, default=50, metavar="COUNT",
                   help="with --logs: how many lines to print "
                        "(default: 50)")
    g.add_argument("--oracle", action="store_true",
                   help="open the Oracle chat against the home "
                        "config")
    g.add_argument("--migrate", action="store_true",
                   help="copy state found in other locations into "
                        "the install's state folder (--dir, or "
                        "<home>\\state on a Windows one-home install; "
                        "never overwrites) and report what moved")
    g.add_argument("--uninstall", action="store_true",
                   help="remove the service entry (the installed files "
                        "and the state stay; --wipe removes those)")
    g.add_argument("--wipe", action="store_true",
                   help="back up every pigeon state dir on this box "
                        "into one zip, then delete the state dirs, "
                        "the scheduled task/service, and running "
                        "processes")
    g.add_argument("--backup-dir", default=None, metavar="DIR",
                   help="where --wipe writes its backup zip "
                        "(default: system temp dir)")
    g.add_argument("--no-backup", action="store_true",
                   help="with --wipe, delete without backing up "
                        "first")
    g = ap.add_argument_group(
        "what gets installed",
        "The config and identity written on a fresh install.")
    g.add_argument("--shared-secret", default=None, metavar="SECRET",
                   help="shared secret to write into config.json "
                        "(default: generate a random one)")
    g.add_argument("--key-id", default=None, metavar="KEY_ID",
                   help="a chosen name for the runner's first key, "
                        "beside the fingerprint it answers to by "
                        "default (k-<8 hex>); stored as an additional "
                        "key with the same value")
    g.add_argument("--instructions", default=None, metavar="TEXT",
                   help="human-readable instructions for this box "
                        "(replaces any existing)")
    g.add_argument("--instructions-add", default=None, metavar="TEXT",
                   help="append a paragraph to the existing "
                        "instructions")
    g.add_argument("--profile", default=None, metavar="NAME_OR_PATH",
                   help="apply a deployment profile (pi-light, "
                        "display-board, password-only, hosted, or a JSON "
                        "file; raspberry-pi-home is pi-light's "
                        "former name). display-board is a dedicated "
                        "Linux board behind a screen: no model. "
                        "A television is not a board, and the "
                        "installer refuses one. If omitted, a "
                        "profile is chosen automatically.")
    g.add_argument("--no-profile", action="store_true",
                   help="do not apply any deployment profile")
    g.add_argument("--config-json", default=None, metavar="JSON|@FILE|env:NAME",
                   help="a provisioner's one-blob config, merged into "
                        "config.json before the profile: shared_secret, "
                        "runner_id, workspace_root, a transport block. "
                        "Security modes and the result view are refused "
                        "here; the profile owns them (hosted installs)")
    g.add_argument("--additional-secret", action="append", default=[],
                   metavar="KEY_ID",
                   help="register an additional key under KEY_ID "
                        "(generates a 256-bit secret, never printed)")
    g = ap.add_argument_group(
        "inference",
        "The local model the Oracle thinks with.")
    g.add_argument("--no-inference", action="store_true",
                   help="do not install Ollama or pull a model "
                        "(ask stays off)")
    g.add_argument("--inference-only", action="store_true",
                   help="only install Ollama / pull the model and "
                        "write the inference block; leaves the rest "
                        "of the install alone. Safe to re-run when "
                        "a previous install did not finish the "
                        "model setup.")
    g.add_argument("--inference-model", default=None, metavar="MODEL",
                   help="Ollama model to pull when inference is "
                        "enabled (default: qwen3:1.7b, qwen2.5:3b "
                        "with --faster; the pi-light profile "
                        "installs no model at all)")
    g.add_argument("--faster", action="store_true",
                   help="pull qwen2.5:3b, the faster model. "
                        "Does not change protected paths. "
                        "--inference-model still wins.")
    g = ap.add_argument_group(
        "collectors",
        "Sense collectors (docs/extend/senses.md) set up next to\n"
        "the runner on a fresh install. On an existing\n"
        "install, naming collectors performs just that\n"
        "setup and exits, like --inference-only.")
    g.add_argument("--collector", action="append", default=None,
                   metavar="NAME", choices=list(COLLECTOR_NAMES),
                   help="install this collector too (repeatable): "
                        "osquery, falco, suricata, zeek, aide, "
                        "softflowd, sysmon, wazuh. A fresh install "
                        "sets up osquery by default; the pi-light "
                        "profile sets up none by default")
    g.add_argument("--no-collector", action="store_true",
                   help="install no collectors, not even the "
                        "osquery default")
    g.add_argument("--wazuh-manager", default=None,
                   metavar="ADDRESS",
                   help="Wazuh manager address; --collector wazuh "
                        "installs the agent only when this is "
                        "given (its alerts live on the manager)")
    # Runner flags forwarded into the installed service command, so the
    # installed agent runs with exactly the flags you tested with.
    g = ap.add_argument_group(
        "baked into the service",
        "Runner flags written into the installed service\n"
        "command; the agent on boot runs what you tested.")
    g.add_argument("--dry-run", action="store_true",
                   help="install with --dry-run baked into the "
                        "service")
    g.add_argument("--workers", type=int, default=None,
                   metavar="COUNT",
                   help="concurrent job executions")
    g.add_argument("--poll-interval", type=int, default=None,
                   metavar="SECONDS",
                   help="seconds between poll cycles")
    g.add_argument("--max-output-bytes", type=int, default=None,
                   metavar="BYTES",
                   help="truncate stdout/stderr beyond this many "
                        "bytes")
    g.add_argument("--no-send", action="store_true",
                   help="install with --no-send baked into the "
                        "service")
    g.add_argument("--timeout", type=int, default=None,
                   metavar="SECONDS",
                   help="default per-job timeout in seconds")
    g.add_argument("--verbose", action="store_true", default=True,
                   help="bake verbose logging into the service "
                        "(the default)")
    g.add_argument("--quiet", action="store_false", dest="verbose",
                   help="bake quiet logging into the service")
    g.add_argument("--pdb", action="store_true",
                   help="drop the runner into pdb on unhandled "
                        "exceptions")
    g.add_argument("--allow-cleartext", action="store_true",
                   help="bake the runner's --allow-cleartext "
                        "into the service: the installed runner "
                        "accepts signed cleartext (HMAC-only) jobs. "
                        "This is the one place the flag persists -- "
                        "written into the service command at install "
                        "time, exactly like the other flags in this "
                        "group; there is no config key for it")
    g.add_argument("--ignore-personal-documents", action="store_true",
                   help="skip the personal-documents warning, and "
                        "bake the runner's --ignore-personal-documents "
                        "into the service so a boot start stays quiet "
                        "too")
    args = ap.parse_args()

    if not (args.uninstall or args.check or args.logs or args.rearm
            or args.ignore_personal_documents):
        _warn_personal_documents()

    print(f"install {__version__}")
    plat = sys.platform
    src_dir = _src_dir()

    if args.uninstall:
        if plat == "win32":
            uninstall_windows()
        elif plat == "darwin":
            uninstall_macos()
        elif plat.startswith("linux"):
            uninstall_linux(args.system)
        elif plat.startswith("freebsd"):
            uninstall_freebsd()
        else:
            print(f"unsupported platform: {plat}")
            return 2
        print("uninstalled")
        return 0

    if args.wipe:
        return do_wipe(backup_dir=args.backup_dir, no_backup=args.no_backup)

    if args.migrate:
        info = _resolve_home(args)
        if info is not None:
            # The one home is the default consolidation target: its state dir.
            return do_migrate(info[3])
        return do_migrate(os.path.abspath(args.dir) if args.dir
                          else os.path.expanduser("~/.homing-pigeon"))

    if args.home and plat != "win32":
        print("note: --home is Windows-only; ignoring it on this platform")

    info = _resolve_home(args)
    if info is not None:
        home, bin_dir, cfg_path, state_dir = info
        if args.rearm:
            return do_rearm(cfg_path)
        if args.check:
            return do_check(home, bin_dir, cfg_path, state_dir)
        if args.console:
            return do_console(home, bin_dir, cfg_path)
        if args.logs:
            return do_logs(cfg_path, follow=args.follow, lines=args.lines)
        if args.follow:
            print("note: --follow needs --logs")
            return 2
        if args.oracle:
            return do_oracle(bin_dir, cfg_path)
        if args.inference_only:
            profile = chosen_profile(args.profile, args.no_profile)
            if _pi_light_skip(args, profile) \
                    and _cfg_oracle_mode(cfg_path) != "llm":
                print("inference: Pi Light -- no model to install or "
                      "download; the Oracle runs deterministically. "
                      "To add a model, set oracle_mode to llm in "
                      "config.json first.")
                return 0
            model = inference_model_for(profile, args.inference_model,
                                         faster=args.faster)
            ok = install_ollama_and_model(cfg_path, model, args.no_inference)
            if ok:
                print(f"inference: READY - local model {model} configured; "
                      "restart the runner and the Oracle chat will answer")
            else:
                print("inference: NOT configured - ask stays off. "
                      "Re-run install.exe --inference-only to retry, or set "
                      "inference.endpoint in config.json to your local Ollama server.")
            return 0
        if (args.collector is not None or args.no_collector) \
                and os.path.isfile(cfg_path):
            # Existing install + collector flags: set up just
            # the collectors, like --inference-only. On a
            # fresh install (no config yet) the flags flow
            # into _setup_fresh_config instead.
            install_collectors(requested_collectors(args), args)
            return 0
        refused = host_install_gate()
        if refused:
            return refused
        return do_install_home(args, home, bin_dir, cfg_path, state_dir,
                               src_dir)

    if args.check or args.console or args.oracle:
        print("error: --check/--console/--oracle need the Windows one-home "
              "install; this box uses the legacy per-user layout")
        return 2
    if args.follow and not args.logs:
        print("note: --follow needs --logs")
        return 2

    dst_dir = (os.path.abspath(args.dir) if args.dir
               else os.path.expanduser("~/.homing-pigeon"))
    cfg_path = os.path.abspath(args.config) if args.config \
        else os.path.join(dst_dir, "config.json")
    if args.rearm:
        return do_rearm(cfg_path)
    if args.logs:
        return do_logs(cfg_path, follow=args.follow, lines=args.lines)
    if args.inference_only:
        profile = chosen_profile(args.profile, args.no_profile)
        if _pi_light_skip(args, profile) \
                and _cfg_oracle_mode(cfg_path) != "llm":
            print("inference: Pi Light -- no model to install or "
                  "download; the Oracle runs deterministically. "
                  "To add a model, set oracle_mode to llm in "
                  "config.json first.")
            return 0
        model = inference_model_for(profile, args.inference_model,
                                     faster=args.faster)
        ok = install_ollama_and_model(cfg_path, model, args.no_inference)
        if ok:
            print(f"inference: READY - local model {model} configured; "
                  "restart the runner and the Oracle chat will answer")
        else:
            print("inference: NOT configured - ask stays off. "
                  "Re-run install.exe --inference-only to retry, or set "
                  "inference.endpoint in config.json to your local Ollama server.")
        return 0
    if (args.collector is not None or args.no_collector) \
            and os.path.isfile(cfg_path):
        install_collectors(requested_collectors(args), args)
        return 0
    refused = host_install_gate()
    if refused:
        return refused
    if not install_files(src_dir, dst_dir, os.path.join(dst_dir,
                                                        "config.json")):
        return 1
    install_project_snapshot(src_dir, _cfg_base_dir(cfg_path))
    inference_ok, model, pi_light = _setup_fresh_config(args, cfg_path)
    extra = _forwarded_args(args)
    if extra:
        print(f"forwarding runner flags into service: {' '.join(extra)}")

    if plat == "win32":
        install_windows(dst_dir, cfg_path, extra, run_as=args.run_as)
    elif plat == "darwin":
        install_macos(dst_dir, cfg_path, extra)
    elif plat.startswith("linux"):
        install_linux(dst_dir, cfg_path, args.system, extra)
    elif plat.startswith("freebsd"):
        install_freebsd(dst_dir, cfg_path, extra)
    else:
        print(f"unsupported platform: {plat} -- files copied to {dst_dir}, "
              "start manually: "
              f"{sys.executable} {dst_dir}/runner.py --config {cfg_path}")
    print(f"config: {cfg_path}")
    if inference_ok:
        print(f"inference: READY - local model {model} configured; "
              "the Oracle chat will answer")
    elif not args.no_inference and not pi_light:
        print("inference: NOT configured - ask stays off. "
              "Re-run install.exe --inference-only to retry, or set "
              "inference.endpoint in config.json to your local Ollama server.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
