# Findings — docs/steady/security/hardening-readme.md

Source: docs/steady/security/hardening-readme.md, reviewed at main cbb52068.
Sentence units: 18. Flagged: 0. Categories: pre-release 18, post-release 0.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "These are opt-in OS-level hardening for the Homing…" | pre-release | flows |  |
| 2 | "The installer (`runner/ops/install.py`) never references them; apply them…" | pre-release | flows |  |
| 3 | "Render the `@PLACEHOLDERS@` with your real paths, e.g.:" | pre-release | flows |  |
| 4 | "sed -e "s\|@RUNNER_DIR@\|/opt/homing-pigeon/runner\|g" \ -e "s\|@BASE_DIR@\|/var/lib/homing-pigeon\|g" \ -e…" | pre-release | flows |  |
| 5 | "The AppArmor path list was derived from an…" | pre-release | flows |  |
| 6 | "It is not a guess." | pre-release | flows |  |
| 7 | "Files:" | pre-release | flows |  |
| 8 | "`systemd/homing-pigeon.service` — hardened systemd unit." | pre-release | flows |  |
| 9 | "Mirrors the unit `install.py` writes, plus sandboxing directives…" | pre-release | flows |  |
| 10 | "Tune `ReadWritePaths` to your base dir and config…" | pre-release | flows |  |
| 11 | "`apparmor/homing-pigeon` — AppArmor profile for the runner daemon…" | pre-release | flows |  |
| 12 | "Load with `apparmor_parser -r`." | pre-release | flows |  |
| 13 | "`selinux/homing_pigeon.te` — SELinux type-enforcement module named `homing_pigeon`." | pre-release | flows |  |
| 14 | "It uses reference-policy interfaces (`policy_module`, `manage_dirs_pattern`, `corenet_*`), so…" | pre-release | flows |  |
| 15 | "Confinement under these templates: bwrap needs user, IPC,…" | pre-release | flows |  |
| 16 | "The systemd unit allows exactly those (`RestrictNamespaces=user ipc…" | pre-release | flows |  |
| 17 | "The AppArmor profile confines the daemon and runs…" | pre-release | flows |  |
| 18 | "The SELinux module carries the transitional capability line…" | pre-release | flows |  |
