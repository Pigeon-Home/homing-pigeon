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
import json
import os
import platform
import secrets
import shlex
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

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
    for name in ("dry_run", "no_oracle", "no_send", "verbose", "pdb"):
        if getattr(args, name, False):
            out.append("--" + name.replace("_", "-"))
    for name in ("poll_interval", "max_output_bytes", "timeout", "workers"):
        v = getattr(args, name, None)
        if v is not None:
            out.extend(["--" + name.replace("_", "-"), str(v)])
    return out


def run(cmd, **kw):
    print("+ " + " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


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
    if cfg.get("shared_secret") and not provided:
        return  # already set by the user; leave it alone
    secret = provided or secrets.token_hex(32)
    # Light entropy gate (the runner does the full check at startup).
    alphabet = len(set(secret))
    bits = len(secret) * (alphabet.bit_length() - 1) if alphabet > 1 else 0
    if bits < 128:
        print(f"error: --shared-secret is too weak (~{bits} bits estimated, "
              f"need at least 128)", file=sys.stderr)
        sys.exit(2)
    cfg["shared_secret"] = secret
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    os.chmod(cfg_path, 0o600)  # secrets on disk: owner read/write only
    if provided:
        print("wrote --shared-secret into config.json")
    else:
        print(f"generated a random shared_secret into {cfg_path} -- "
              f"give this string to your cloud SI")


def install_files(src_dir: str, dst_dir: str):
    os.makedirs(dst_dir, exist_ok=True)
    if FROZEN:
        src = os.path.join(src_dir, RUNNER_BIN)
        dst = os.path.join(dst_dir, RUNNER_BIN)
        shutil.copy2(src, dst)
        if os.name != "nt":
            os.chmod(dst, 0o755)
    else:
        for name in FILES:
            shutil.copy2(os.path.join(src_dir, name), os.path.join(dst_dir, name))
    cfg_dst = os.path.join(dst_dir, "config.json")
    if not os.path.exists(cfg_dst):
        shutil.copy2(os.path.join(src_dir, "config.example.json"), cfg_dst)
        print(f"wrote {cfg_dst} -- EDIT IT before starting "
              "(mailbox_user, mailbox_password, shared_secret)")


def install_windows(dst_dir: str, cfg_path: str, extra=()):
    tr = " ".join(f'"{a}"' for a in _runner_argv(dst_dir)) + \
        f' --config "{cfg_path}"' + \
        "".join(f" {shlex.quote(a)}" for a in extra)
    run(["schtasks", "/Create", "/TN", "HomingPigeon", "/TR", tr,
         "/SC", "ONSTART", "/RU", "SYSTEM", "/RL", "HIGHEST", "/F"])
    run(["schtasks", "/Run", "/TN", "HomingPigeon"])
    print("installed: Scheduled Task 'HomingPigeon' (runs at boot as SYSTEM)")


def uninstall_windows():
    run(["schtasks", "/Delete", "/TN", "HomingPigeon", "/F"])


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


def main() -> int:
    ap = argparse.ArgumentParser(description="Install homing-pigeon as a service")
    ap.add_argument("--dir", default=os.path.expanduser("~/.homing-pigeon"),
                    help="install directory (default ~/.homing-pigeon)")
    ap.add_argument("--config", default=None,
                    help="config file to use (default <dir>/config.json)")
    ap.add_argument("--system", action="store_true",
                    help="Linux: install a system-wide systemd unit (needs root)")
    ap.add_argument("--uninstall", action="store_true")
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
    ap.add_argument("--no-oracle", action="store_true")
    ap.add_argument("--max-output-bytes", type=int, default=None, metavar="N")
    ap.add_argument("--no-send", action="store_true")
    ap.add_argument("--timeout", type=int, default=None, metavar="SEC")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--pdb", action="store_true")
    args = ap.parse_args()

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

    dst_dir = os.path.abspath(args.dir)
    cfg_path = os.path.abspath(args.config) if args.config \
        else os.path.join(dst_dir, "config.json")
    install_files(src_dir, dst_dir)
    ensure_shared_secret(cfg_path, args.shared_secret)
    extra = _forwarded_args(args)
    if extra:
        print(f"forwarding runner flags into service: {' '.join(extra)}")

    if plat == "win32":
        install_windows(dst_dir, cfg_path, extra)
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
