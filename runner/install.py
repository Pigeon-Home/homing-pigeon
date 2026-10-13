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
import shutil
import subprocess
import sys

SERVICE_NAME = "homing-pigeon"
FILES = ["runner.py"]


def run(cmd, **kw):
    print("+ " + " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def install_files(src_dir: str, dst_dir: str):
    os.makedirs(dst_dir, exist_ok=True)
    for name in FILES:
        shutil.copy2(os.path.join(src_dir, name), os.path.join(dst_dir, name))
    cfg_dst = os.path.join(dst_dir, "config.json")
    if not os.path.exists(cfg_dst):
        shutil.copy2(os.path.join(src_dir, "config.example.json"), cfg_dst)
        print(f"wrote {cfg_dst} -- EDIT IT before starting "
              "(mailbox_user, mailbox_password)")


def install_windows(dst_dir: str, cfg_path: str):
    py = sys.executable
    runner = os.path.join(dst_dir, "runner.py")
    tr = f'"{py}" "{runner}" --config "{cfg_path}"'
    run(["schtasks", "/Create", "/TN", "HomingPigeon", "/TR", tr,
         "/SC", "ONSTART", "/RU", "SYSTEM", "/RL", "HIGHEST", "/F"])
    run(["schtasks", "/Run", "/TN", "HomingPigeon"])
    print("installed: Scheduled Task 'HomingPigeon' (runs at boot as SYSTEM)")


def uninstall_windows():
    run(["schtasks", "/Delete", "/TN", "HomingPigeon", "/F"])


def install_linux(dst_dir: str, cfg_path: str, system: bool):
    unit = f"""[Unit]
Description=Homing Pigeon runner agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={sys.executable} {dst_dir}/runner.py --config {cfg_path}
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


def install_macos(dst_dir: str, cfg_path: str):
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.homing-pigeon.runner</string>
  <key>ProgramArguments</key>
  <array>
    <string>{sys.executable}</string>
    <string>{dst_dir}/runner.py</string>
    <string>--config</string>
    <string>{cfg_path}</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{dst_dir}/runner.log</string>
  <key>StandardErrorPath</key><string>{dst_dir}/runner.log</string>
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


def install_freebsd(dst_dir: str, cfg_path: str):
    line = f"@reboot {sys.executable} {dst_dir}/runner.py --config {cfg_path}"
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
    args = ap.parse_args()

    plat = sys.platform
    src_dir = os.path.dirname(os.path.abspath(__file__))

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
