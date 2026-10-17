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

import argparse
import datetime
import json
import os
import platform
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from xml.sax.saxutils import escape

try:
    from runner._version import __version__
except ImportError:  # running from inside runner/ as __main__
    try:
        from _version import __version__
    except ImportError:
        __version__ = "unknown"

SERVICE_NAME = "homing-pigeon"
FILES = ["runner.py", "oauth.py", "winlog.py"]

# When frozen with PyInstaller (the release binaries), there is no Python
# on the target machine: the runner ships as a sibling binary
# (homing-pigeon / homing-pigeon.exe) and services point at it directly.
FROZEN = getattr(sys, "frozen", False)
RUNNER_BIN = "homing-pigeon.exe" if os.name == "nt" else "homing-pigeon"


def _src_dir() -> str:
    if FROZEN:
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _runner_argv(dst_dir: str):
    """Argv that starts the installed runner (list, no shell)."""
    if FROZEN:
        return [os.path.join(dst_dir, RUNNER_BIN)]
    return [sys.executable, os.path.join(dst_dir, "runner.py")]


def _forwarded_args(args) -> list:
    """Runner CLI flags to bake into the installed service command."""
    out = []
    for name in ("dry_run", "no_send", "pdb"):
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


def ensure_shared_secret(cfg_path: str, provided: str | None) -> None:
    """Write a shared_secret into config.json.

    Uses the --shared-secret value when given (automated deployments);
    otherwise generates a random 256-bit secret. Either way the user
    retrieves it from config.json afterwards and hands it to their
    cloud SI. A provided secret gets the same entropy bar as the
    runner's startup check.
    """
    with open(cfg_path) as f:
        cfg = json.load(f)
    current = cfg.get("shared_secret") or ""
    if current and not provided and not _looks_like_placeholder(current):
        return  # user-set real secret; leave it alone
    # Missing, empty, or still the example placeholder: (re)generate.
    secret = provided or secrets.token_hex(32)
    # Light entropy gate (the runner does the full check at startup).
    alphabet = len(set(secret))
    bits = len(secret) * (alphabet.bit_length() - 1) if alphabet > 1 else 0
    if bits < 128 or _looks_like_placeholder(secret) or _looks_patterned(secret):
        print("error: --shared-secret is too weak (needs 128+ bits of real "
              "entropy, not a placeholder or repeating pattern)",
              file=sys.stderr)
        sys.exit(2)
    cfg["shared_secret"] = secret
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    os.chmod(cfg_path, 0o600)  # secrets on disk: owner read/write only
    # (On Windows os.chmod cannot set Unix permission bits; the file
    # inherits the parent directory's ACLs, which is the platform's
    # equivalent protection.)
    if provided:
        print("wrote --shared-secret into config.json")
    else:
        print(f"generated a random shared_secret into {cfg_path} -- "
              f"give this string to your cloud SI")
    ensure_runner_id(cfg_path)


def ensure_runner_id(cfg_path: str) -> None:
    """Hardening M5: generate a 128-bit runner_id when absent.

    Never overwrites an existing one: changing it would invalidate
    previously signed jobs.
    """
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    if cfg.get("runner_id"):
        return
    cfg["runner_id"] = secrets.token_hex(16)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
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
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    extra = cfg.get("additional_secrets") or {}
    if not isinstance(extra, dict):
        print("error: additional_secrets in config is not an object",
              file=sys.stderr)
        sys.exit(2)
    secret = secrets.token_urlsafe(32)
    extra[key_id] = secret
    cfg["additional_secrets"] = extra
    tmp = cfg_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    os.replace(tmp, cfg_path)
    os.chmod(cfg_path, 0o600)
    print(f"additional secret stored for {key_id}")


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
        for name in FILES:
            shutil.copy2(os.path.join(src_dir, name),
                         os.path.join(bin_dir, name))
    if not os.path.exists(cfg_path):
        example = os.path.join(src_dir, "config.example.json")
        if not os.path.isfile(example):
            print(f"install: error: {example} not found; cannot seed config")
            return False
        os.makedirs(os.path.dirname(os.path.abspath(cfg_path)), exist_ok=True)
        shutil.copy2(example, cfg_path)
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
        _run_quiet(["launchctl", "unload",
                    os.path.expanduser("~/Library/LaunchAgents/homing-pigeon.plist")])
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
          "'install.exe --wipe' removes the old locations.")
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
    """The receipt dict, None when there is none, 'corrupt' when unreadable."""
    try:
        with open(_receipt_path(home), encoding="utf-8") as fh:
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
    tmp = _receipt_path(home) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, _receipt_path(home))
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
    if not url:
        rec("WARN", "inference",
            "not configured; the Oracle chat stays off "
            "(install.exe --inference-only to set it up)")
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
                return 1
            print("console: task restarted")
    return 0


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


def _setup_fresh_config(args, cfg_path):
    """Secrets, mailbox wizard, profile, instructions, Ollama.

    Fresh installs only. Returns (inference_ok, model)."""
    ensure_shared_secret(cfg_path, args.shared_secret)
    # Mailbox auth is the one thing install cannot invent. On a TTY,
    # offer the same Thunderbird-style wizard the runner uses, so a
    # fresh install ends with a working service and no hand-edited
    # JSON. Headless installs keep today's behavior (fail at first
    # run with a config error pointing at --setup).
    try:
        from runner import setup as _setup
    except ImportError:
        try:
            import setup as _setup
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
    model = inference_model_for(profile, args.inference_model,
                                faster=getattr(args, "faster", False))
    inference_ok = install_ollama_and_model(cfg_path, model, args.no_inference)
    if profile:
        apply_profile(cfg_path, profile)
    apply_instruction_flags(cfg_path, args.instructions, args.instructions_add)
    return inference_ok, model


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
                  "upgrading binaries, and switching the model to the lighter Llama")
        else:
            print(f"install: one home already installed (v{prev_version}); "
                  "upgrading binaries in place -- config.json and state/ "
                  "are untouched")
        _stop_task_for_upgrade()
    if not install_files(src_dir, bin_dir, cfg_path):
        return 1
    inference_ok, model = False, None
    if fresh:
        _ensure_base_dir(cfg_path, state_dir)
        inference_ok, model = _setup_fresh_config(args, cfg_path)
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
    elif fresh and not args.no_inference:
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
    print("  install.exe --faster   pull llama3.2:1b, the lighter Llama")
    return 0


def install_linux(dst_dir: str, cfg_path: str, system: bool, extra=()):
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
        with open(path, "w") as fh:
            fh.write(unit)
        run(["systemctl", "daemon-reload"])
        run(["systemctl", "enable", "--now", "homing-pigeon.service"])
    else:
        udir = os.path.expanduser("~/.config/systemd/user")
        os.makedirs(udir, exist_ok=True)
        path = os.path.join(udir, "homing-pigeon.service")
        with open(path, "w") as fh:
            fh.write(unit)
        run(["systemctl", "--user", "daemon-reload"])
        run(["systemctl", "--user", "enable", "--now", "homing-pigeon.service"])
    print(f"installed: systemd unit at {path}")


def uninstall_linux(system: bool):
    if system:
        run(["systemctl", "disable", "--now", "homing-pigeon.service"])
        os.remove("/etc/systemd/system/homing-pigeon.service")
        run(["systemctl", "daemon-reload"])
    else:
        run(["systemctl", "--user", "disable", "--now", "homing-pigeon.service"])
        os.remove(os.path.expanduser("~/.config/systemd/user/homing-pigeon.service"))
        run(["systemctl", "--user", "daemon-reload"])


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
    uid = os.getuid()
    run(["launchctl", "bootstrap", f"gui/{uid}", path])
    print(f"installed: launchd agent at {path}")


def uninstall_macos():
    path = os.path.expanduser("~/Library/LaunchAgents/com.homing-pigeon.runner.plist")
    uid = os.getuid()
    run(["launchctl", "bootout", f"gui/{uid}", path])
    os.remove(path)


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
    lines = [l for l in (p.stdout if p.returncode == 0 else "").splitlines()
             if "homing-pigeon" not in l]
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



BUILTIN_PROFILES = {
    "raspberry-pi-home": {
        "description": "Pi; watch root password hash and home manuals",
        "redact_patterns_extra": {
            "shadow_hash": r"\$[0-9a-z]+\$[A-Za-z0-9./]{20,}",
        },
        "protected_paths": ["/etc/shadow", "/home/pi/docs/manuals"],
        "max_result_view": "attested",
        "judge": "advisory",
        # 1B fits a Pi. The 3B default is for machines with more RAM.
        "inference_model": "llama3.2:1b",
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
}


DEFAULT_INFERENCE_MODEL = "llama3.2:3b"


def inference_model_for(profile, explicit=None, faster=False) -> str:
    """Which Ollama tag to pull.

    An explicit --inference-model always wins. --faster pulls the same
    lighter Llama as the raspberry-pi-home profile, without the rest of
    that profile. Otherwise the raspberry-pi-home profile, whether
    detected or passed with --profile, pulls that lighter Llama, and
    every other install keeps the 3B default.
    """
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    if faster:
        light = BUILTIN_PROFILES["raspberry-pi-home"].get("inference_model")
        if isinstance(light, str) and light.strip():
            return light.strip()
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




_INSTRUCTIONS_LOCK = threading.Lock()


def _write_json(path: str, cfg: dict) -> None:
    """Atomic config write. The replacement must stay owner-only."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    os.chmod(path, 0o600)


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
        if os.path.exists(cfg_path):
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
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


def chosen_profile(explicit, skip: bool):
    """Profile name or path to apply. None when --no-profile is set.

    An explicit --profile wins. Otherwise detect_default_profile() picks.
    """
    if skip:
        return None
    if explicit:
        return explicit
    return detect_default_profile()


def detect_default_profile() -> str:
    """Pick a profile automatically when the user did not name one.

    Raspberry Pi gets the password-focused Pi profile. Everything else
    gets password-only so the common case (only the password matters)
    is the default. --no-profile disables this.
    """
    # Pi detection: device-tree model or the classic cpuinfo hardware line.
    for path in ("/proc/device-tree/model", "/proc/cpuinfo"):
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                blob = f.read().lower()
            if "raspberry pi" in blob:
                return "raspberry-pi-home"
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
                "dag_mode", "require_review"):
        if key in data:
            cfg[key] = data[key]
    cfg["profile"] = name
    _write_json(cfg_path, cfg)
    print(f"profile: applied {name}")



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


def main() -> int:
    ap = argparse.ArgumentParser(description="Install homing-pigeon as a service")
    ap.add_argument("--version", action="version",
                    version="%(prog)s " + __version__)
    ap.add_argument("--dir", default=None,
                    help="binary install dir (default <home>/bin on Windows, "
                         "~/.homing-pigeon elsewhere). On Windows, --dir "
                         "without --home keeps the legacy layout: binaries "
                         "and config.json both land in --dir.")
    ap.add_argument("--home", default=None, metavar="DIR",
                    help="Windows: the one-home root (default "
                         "C:\\homing-pigeon). Holds bin/, config.json, "
                         "state/, install-receipt.json.")
    ap.add_argument("--check", action="store_true",
                    help="doctor: verify the one-home layout, receipt, "
                         "service task, config, and inference endpoint")
    ap.add_argument("--console", action="store_true",
                    help="Windows: stop the HomingPigeon task, run the agent "
                         "in this terminal with live logs, restart the task "
                         "on exit")
    ap.add_argument("--logs", action="store_true",
                    help="print the tail of the runner log")
    ap.add_argument("--follow", action="store_true",
                    help="with --logs: keep following the log (Ctrl+C stops)")
    ap.add_argument("--lines", type=int, default=50, metavar="N",
                    help="with --logs: how many lines to print (default 50)")
    ap.add_argument("--oracle", action="store_true",
                    help="open the Oracle chat against the home config")
    ap.add_argument("--config", default=None,
                    help="config file to use (default <dir>/config.json)")
    ap.add_argument("--system", action="store_true",
                    help="Linux: install a system-wide systemd unit (needs root)")
    ap.add_argument("--run-as", default=None, metavar="USER",
                    help="Windows: run the scheduled task as USER instead "
                         "of SYSTEM (least privilege; schtasks prompts "
                         "for the account password unless it is a "
                         "service account)")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--wipe", action="store_true",
                    help="back up every pigeon state dir on this box into one "
                         "zip, then delete the state dirs, the scheduled "
                         "task/service, and running processes")
    ap.add_argument("--backup-dir", default=None, metavar="DIR",
                    help="where --wipe writes its backup zip "
                         "(default: system temp dir)")
    ap.add_argument("--no-backup", action="store_true",
                    help="with --wipe, delete without backing up first")
    ap.add_argument("--migrate", action="store_true",
                    help="copy state found in other locations into --dir "
                         "(never overwrites) and report what moved")
    ap.add_argument("--shared-secret", default=None, metavar="SECRET",
                    help="shared secret to write into config.json "
                         "(default: generate a random one)")
    # Runner flags forwarded into the installed service command, so the
    # installed agent runs with exactly the flags you tested with.
    ap.add_argument("--dry-run", action="store_true",
                    help="install with --dry-run baked into the service")
    ap.add_argument("--workers", type=int, default=None, metavar="N",
                    help="concurrent job executions")
    ap.add_argument("--poll-interval", type=int, default=None, metavar="SEC")
    ap.add_argument("--no-inference", action="store_true",
                    help="do not install Ollama or pull a model (ask stays off)")
    ap.add_argument("--inference-only", action="store_true",
                    help="only install Ollama / pull the model and write the "
                         "inference block; leaves the rest of the install alone. "
                         "Safe to re-run when a previous install did not finish "
                         "the model setup.")
    ap.add_argument("--instructions", default=None, metavar="TEXT",
                    help="human-readable instructions for this box (replaces any existing)")
    ap.add_argument("--instructions-add", default=None, metavar="TEXT",
                    help="append a paragraph to the existing instructions")
    ap.add_argument("--profile", default=None, metavar="NAME_OR_PATH",
                    help="apply a deployment profile (raspberry-pi-home, password-only, or a JSON file). "
                         "If omitted, a profile is chosen automatically.")
    ap.add_argument("--no-profile", action="store_true",
                    help="do not apply any deployment profile")
    ap.add_argument("--inference-model", default=None,
                    help="Ollama model to pull when inference is enabled "
                         "(default llama3.2:3b, llama3.2:1b with "
                         "--faster or the raspberry-pi-home profile)")
    ap.add_argument("--faster", action="store_true",
                    help="pull llama3.2:1b, the lighter Llama the "
                         "Raspberry Pi profile uses. Does not change "
                         "protected paths. --inference-model still wins.")
    ap.add_argument("--additional-secret", action="append", default=[],
                    help="KEY_ID (generates 256-bit secret, never printed)")
    ap.add_argument("--max-output-bytes", type=int, default=None, metavar="N")
    ap.add_argument("--no-send", action="store_true")
    ap.add_argument("--timeout", type=int, default=None, metavar="SEC")
    ap.add_argument("--verbose", action="store_true", default=True)
    ap.add_argument("--quiet", action="store_false", dest="verbose")
    ap.add_argument("--pdb", action="store_true")
    args = ap.parse_args()

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
    if args.logs:
        return do_logs(cfg_path, follow=args.follow, lines=args.lines)
    if args.inference_only:
        profile = chosen_profile(args.profile, args.no_profile)
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
    if not install_files(src_dir, dst_dir, os.path.join(dst_dir,
                                                        "config.json")):
        return 1
    inference_ok, model = _setup_fresh_config(args, cfg_path)
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
    elif not args.no_inference:
        print("inference: NOT configured - ask stays off. "
              "Re-run install.exe --inference-only to retry, or set "
              "inference.endpoint in config.json to your local Ollama server.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
