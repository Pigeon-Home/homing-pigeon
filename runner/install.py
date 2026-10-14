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
import os
import platform
import shlex
import shutil
import subprocess
import sys

SERVICE_NAME = "homing-pigeon"
FILES = ["runner.py"]

# When frozen with PyInstaller (the release binaries), there is no Python
# on the target machine: the runner ships as a sibling binary
# (homing-pigeon / homing-pigeon.exe) and services point at it directly.
FROZEN = getattr(sys, "frozen", False)
RUNNER_BIN = "homing-pigeon.exe" if os.name == "nt" else "homing-pigeon"
IN_VENV = sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _xml_escape(s: str) -> str:
    amp = "&" + "amp;"
    lt = "&" + "lt;"
    gt = "&" + "gt;"
    quot = "&" + "quot;"
    return (s.replace("&", amp).replace("<", lt)
            .replace(">", gt).replace('"', quot))


def run(cmd, **kw):
    print("+ " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, **kw)


def run_ok(cmd, **kw):
    """Run and return True on success, False on failure (no raise)."""
    r = run(cmd, **kw)
    return r.returncode == 0


def _src_dir() -> str:
    if FROZEN:
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _runner_argv(dst_dir: str):
    """Argv that starts the installed runner (list, no shell)."""
    if FROZEN:
        return [os.path.join(dst_dir, RUNNER_BIN)]
    return [sys.executable, os.path.join(dst_dir, "runner.py")]


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
        example = os.path.join(src_dir, "config.example.json")
        if os.path.exists(example):
            shutil.copy2(example, cfg_dst)
        else:
            with open(cfg_dst, "w") as fh:
                fh.write('{"mailbox_user":"","mailbox_password":""}\n')
        print(f"wrote {cfg_dst} -- EDIT IT before starting "
              "(mailbox_user, mailbox_password)")
    if IN_VENV and not FROZEN:
        print("note: installed from a virtualenv; the service will use "
              f"{sys.executable}. Keep that venv installed.")


def install_windows(dst_dir: str, cfg_path: str):
    tr = " ".join(f'"{a}"' for a in _runner_argv(dst_dir)) + \
        f' --config "{cfg_path}"'
    # Prefer SYSTEM; fall back to the current user if not elevated.
    if not run_ok(["schtasks", "/Create", "/TN", "HomingPigeon", "/TR", tr,
                   "/SC", "ONSTART", "/RU", "SYSTEM", "/RL", "HIGHEST", "/F"]):
        print("SYSTEM task failed (not elevated?); installing for current user")
        run(["schtasks", "/Create", "/TN", "HomingPigeon", "/TR", tr,
             "/SC", "ONLOGON", "/F"], check=True)
    # First run may fail if config is still the example. Do not abort install.
    if not run_ok(["schtasks", "/Run", "/TN", "HomingPigeon"]):
        print("note: immediate start failed (edit config.json, then start the task)")
    print("installed: Scheduled Task 'HomingPigeon'")


def uninstall_windows():
    run_ok(["schtasks", "/Delete", "/TN", "HomingPigeon", "/F"])


def _linux_unit(dst_dir: str, cfg_path: str, system: bool) -> str:
    exec_start = (" ".join(shlex.quote(a) for a in _runner_argv(dst_dir))
                  + " --config " + shlex.quote(cfg_path))
    wanted = "multi-user.target" if system else "default.target"
    return (
        "[Unit]\n"
        "Description=Homing Pigeon runner agent\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={shlex.quote(dst_dir)}\n"
        f"ExecStart={exec_start}\n"
        "Restart=always\n"
        "RestartSec=10\n"
        "\n"
        "[Install]\n"
        f"WantedBy={wanted}\n"
    )


def install_linux(dst_dir: str, cfg_path: str, system: bool):
    unit = _linux_unit(dst_dir, cfg_path, system)
    if system:
        path = "/etc/systemd/system/homing-pigeon.service"
        with open(path, "w") as fh:
            fh.write(unit)
        run_ok(["systemctl", "daemon-reload"])
        if not run_ok(["systemctl", "enable", "--now", "homing-pigeon.service"]):
            print("note: enable failed (need root? edit config then start manually)")
    else:
        udir = os.path.expanduser("~/.config/systemd/user")
        os.makedirs(udir, exist_ok=True)
        path = os.path.join(udir, "homing-pigeon.service")
        with open(path, "w") as fh:
            fh.write(unit)
        # Linger so the user unit starts at boot even without a login session.
        run_ok(["loginctl", "enable-linger", os.environ.get("USER", "")])
        run_ok(["systemctl", "--user", "daemon-reload"])
        if not run_ok(["systemctl", "--user", "enable", "--now",
                       "homing-pigeon.service"]):
            print("note: user unit enable failed (no user session?). "
                  "Unit file is written; start it after login or enable linger.")
    print(f"installed: systemd unit at {path}")


def uninstall_linux(system: bool):
    if system:
        run_ok(["systemctl", "disable", "--now", "homing-pigeon.service"])
        try:
            os.remove("/etc/systemd/system/homing-pigeon.service")
        except FileNotFoundError:
            pass
        run_ok(["systemctl", "daemon-reload"])
    else:
        run_ok(["systemctl", "--user", "disable", "--now",
                "homing-pigeon.service"])
        try:
            os.remove(os.path.expanduser(
                "~/.config/systemd/user/homing-pigeon.service"))
        except FileNotFoundError:
            pass
        run_ok(["systemctl", "--user", "daemon-reload"])


def install_macos(dst_dir: str, cfg_path: str):
    pargs = "\n".join(
        f"    <string>{_xml_escape(a)}</string>"
        for a in (*_runner_argv(dst_dir), "--config", cfg_path))
    log = _xml_escape(os.path.join(dst_dir, "runner.log"))
    plist = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        '<dict>\n'
        '  <key>Label</key><string>com.homing-pigeon.runner</string>\n'
        '  <key>ProgramArguments</key>\n'
        '  <array>\n'
        f'{pargs}\n'
        '  </array>\n'
        '  <key>RunAtLoad</key><true/>\n'
        '  <key>KeepAlive</key><true/>\n'
        f'  <key>StandardOutPath</key><string>{log}</string>\n'
        f'  <key>StandardErrorPath</key><string>{log}</string>\n'
        '</dict>\n'
        '</plist>\n'
    )
    adir = os.path.expanduser("~/Library/LaunchAgents")
    os.makedirs(adir, exist_ok=True)
    path = os.path.join(adir, "com.homing-pigeon.runner.plist")
    with open(path, "w") as fh:
        fh.write(plist)
    uid = os.getuid()
    # Unload first so a re-install does not fail with "already loaded".
    run_ok(["launchctl", "bootout", f"gui/{uid}", path])
    if not run_ok(["launchctl", "bootstrap", f"gui/{uid}", path]):
        print("note: launchctl bootstrap failed; plist is written, load it manually")
    print(f"installed: launchd agent at {path}")


def uninstall_macos():
    path = os.path.expanduser("~/Library/LaunchAgents/com.homing-pigeon.runner.plist")
    uid = os.getuid()
    run_ok(["launchctl", "bootout", f"gui/{uid}", path])
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def install_freebsd(dst_dir: str, cfg_path: str):
    line = ("@reboot " + " ".join(shlex.quote(a) for a in _runner_argv(dst_dir))
            + " --config " + shlex.quote(cfg_path))
    p = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = p.stdout if p.returncode == 0 else ""
    if "homing-pigeon" in existing:
        print("crontab already has a homing-pigeon entry")
        return
    new = (existing.rstrip("\n") + "\n" if existing.strip() else "") + line + "\n"
    p2 = subprocess.run(["crontab", "-"], input=new, text=True)
    if p2.returncode != 0:
        print("note: crontab install failed; add this line manually:")
        print(line)
        return
    print("installed: cron @reboot entry")
    print("note: for a native rc.d service instead, wrap the same command in "
          "/usr/local/etc/rc.d/homing_pigeon (requires root)")


def uninstall_freebsd():
    p = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines = [l for l in (p.stdout if p.returncode == 0 else "").splitlines()
             if "homing-pigeon" not in l]
    subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Install homing-pigeon as a service")
    ap.add_argument("--dir", default=os.path.expanduser("~/.homing-pigeon"),
                    help="install directory (default ~/.homing-pigeon)")
    ap.add_argument("--config", default=None,
                    help="config file to use (default <dir>/config.json)")
    ap.add_argument("--system", action="store_true",
                    help="Linux: install a system-wide systemd unit (needs root)")
    ap.add_argument("--uninstall", action="store_true")
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

    if plat == "win32":
        install_windows(dst_dir, cfg_path)
    elif plat == "darwin":
        install_macos(dst_dir, cfg_path)
    elif plat.startswith("linux"):
        install_linux(dst_dir, cfg_path, args.system)
    elif plat.startswith("freebsd"):
        install_freebsd(dst_dir, cfg_path)
    else:
        print(f"unsupported platform: {plat} -- files copied to {dst_dir}, "
              "start manually: "
              f"{sys.executable} {dst_dir}/runner.py --config {cfg_path}")
    print(f"config: {cfg_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
