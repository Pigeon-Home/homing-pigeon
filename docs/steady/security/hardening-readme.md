# Hardening templates — NOT installed by default

These are opt-in OS-level hardening for the Homing Pigeon runner.
The installer (`runner/ops/install.py`) never references them; apply them
by hand after you understand what each line does.

Render the `@PLACEHOLDERS@` with your real paths, e.g.:

    sed -e "s|@RUNNER_DIR@|/opt/homing-pigeon/runner|g" \
        -e "s|@BASE_DIR@|/var/lib/homing-pigeon|g" \
        -e "s|@CONFIG@|/etc/homing-pigeon/config.json|g" \
        -e "s|@PYTHON@|/usr/bin/python3|g" \
        -e "s|@USER@|pigeon|g" \
        docs/security/hardening/systemd/homing-pigeon.service \
        > /etc/systemd/system/homing-pigeon.service

The AppArmor path list was derived from an `strace -f -e openat` run
of one `--once` poll cycle, plus the paths a working run needs
(TLS certs, DNS, the base dir). It is not a guess.

Files:

- `systemd/homing-pigeon.service` — hardened systemd unit. Mirrors
  the unit `install.py` writes, plus sandboxing directives
  (NoNewPrivileges, ProtectSystem=strict, ProtectHome, PrivateTmp,
  RestrictAddressFamilies, ...). Tune `ReadWritePaths` to your base
  dir and config path.
- `apparmor/homing-pigeon` — AppArmor profile for the runner daemon
  itself (not for jobs; jobs get bwrap via the `confinement`
  feature). Load with `apparmor_parser -r`.
- `selinux/homing_pigeon.te` — SELinux type-enforcement module named
  `homing_pigeon`. It uses reference-policy interfaces
  (`policy_module`, `manage_dirs_pattern`, `corenet_*`), so build it
  with the reference policy's Makefile, `make -f
  /usr/share/selinux/devel/Makefile homing_pigeon.pp`, and load with
  `semodule -i homing_pigeon.pp`.

Confinement under these templates: bwrap needs user, IPC, net, UTS
and mount namespaces. The systemd unit allows exactly those
(`RestrictNamespaces=user ipc net uts mnt`); narrow it to `true`
only on a box that runs `confinement` as `audit` or `off`, since
under `enforce` a sandbox that cannot engage refuses to start the
runner. The AppArmor profile confines the daemon and runs bwrap
under the same profile (`ix`) without mount, `pivot_root` or
`userns` rules, so under that profile keep confinement at `audit`
or `off`, or extend the profile from your own `aa-logprof` run. The
SELinux module carries the transitional capability line bwrap needs.
