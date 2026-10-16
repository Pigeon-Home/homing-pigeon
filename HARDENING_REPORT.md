# Security hardening report (M0–M11)

*Written 2026-10-15 as branch work against v3.5.2. Those controls
shipped on `main` in v3.6.0. The "do not merge" lines below are the
record of how the work was done, not the current rule. Every control
is still off unless the owner turns it on.*

## Scope and constraints

Implemented Claude's security hardening runbook (M0–M11) against
`main` at v3.5.2. Standing orders for the whole effort:

- **D9**: everything off by default. With no `security` block the
  runner behaves exactly as before (proven by the parity harness).
- Branch-only (`hardening/mN-*`); never push/merge/tag `main`.
- The design stays intact: signature-first verification, at-least-once
  delivery, the existing reject paths. Hardening hooks into them, it
  doesn't replace them.
- All security restrictions left at "almost 0": every feature ships
  `off`, the owner opts in per feature.

## Per-milestone summary

| Milestone | Branch | What landed |
|---|---|---|
| M0 | `hardening/m0-plumbing` | `runner/security.py`: `sec_mode`/`sec_decide` (off/audit/enforce), `validate_security_config` (malformed block stops startup naming key+value), best-effort bounded audit writer (0600, `.1` rollover, counts file). Startup hook in `main()`. Parity harness (`tests/security_parity.py`): 12-job corpus, normalized comparison across no-block/off/audit. |
| M1 | `hardening/m1-fixes` | Two defect fixes. **M1a**: the review regex's catastrophic backtracking replaced with a quote-position walk + linear reverse tail check — 5000-case differential, zero mismatches; 1M-char scripts review in ms (was 29s at 160k). **M1b**: `max_job_bytes` (4MiB, raw mail pre-signature) and `max_script_bytes` (1MiB, post-verify); 0=unlimited; bad values are startup errors. |
| M2 | `hardening/m2-policy` | `key_policies` gains `allowed_env`, `denied_env`, `allowed_files`, `args_pattern`. `DANGEROUS_ENV_NAMES` (BASH_ENV, LD_PRELOAD, PYTHONPATH, …) denied for policy keys unless explicitly allowed. Pinned scripts carrying unlisted env/files are denied. `args_pattern` validated at startup with a backtracking probe; args capped at 1024 chars. PROTOCOL.md's "cannot be repurposed" claim is now backed by a test. |
| M3 | `hardening/m3-audit-report` | `--audit-report [--since 14d\|48h]`: read-only audit summary (table, per-key suggestions, "refused to suggest"). Dangerous env names and URL file sources are never suggested. Works without mailbox credentials; never writes `config.json` (mtime+hash tested). |
| M4 | `hardening/m4-posture` | `--posture`: exit 0/1/2 report (config file, secrets, audit log, base dir, modes, policies). `validate_shared_secret` moved to `security.py` (re-exported, not copied). 0600 checks on Linux; best-effort Windows DACL check (True→OK, False→WARN, unknown→WARN, never FAIL). |
| M5 | `hardening/m5-audience` | `audience` feature (off/audit/enforce). Config `runner_id` (wizard generates one for fresh configs); the expected value always comes from the loaded config, never the body. Enforced for jobs, queries (covers the `ask` op), board messages, sensor alerts. Replay-cache keys namespaced by `runner_id` when set. |
| M6 | `hardening/m6-confinement` | `confinement` feature: `exec` jobs run inside bwrap (`/usr` ro, no net, no home, workdir rw at `/work`, env via `--setenv`). Proven on this machine (see below). Fallback chain: unavailable → loud WARN + audit + run normally; audit → run + `would_run_sandboxed`. |
| M7 | `hardening/m7-templates` | `hardening/`: systemd unit, AppArmor profile (paths from `strace -f -e openat`), SELinux module `homing_pigeon`. Opt-in only; `install.py --help` doesn't mention them. |
| M8 | `hardening/m8-secrets` | `shared_secret_file` / `additional_secrets_files` (mutually exclusive with inline; fail closed). `job_user` feature: jobs run as another POSIX user via setuid (root only; workdir chown'd, parents traverse-only). |
| M9 | `hardening/m9-m10-design-docs` | `docs/asymmetric-signing-design.md`: Ed25519 migration design (public keys per key_id, migration path, dependency question). Not implemented. |
| M10 | `hardening/m9-m10-design-docs` | `docs/approval-gate-design.md`: human approval before execution (per-key modes, pending queue, channel ranking). Not implemented. |
| M11 | `hardening/m11-windows-run-as` | `install.py --run-as USER`: scheduled task runs as USER (default SYSTEM). Named accounts get `/RL LIMITED`. Docs in INSTALL.md. Verified via schtasks argv inspection (no live Windows QA on this box). |

Final suite: **1093 tests green** (945 at v3.5.2 baseline).

## Divergences and plan-detail gaps

The companion `security-hardening-plan.md` was not in the repo, so the
following are my designs, recorded here per runbook rule 15:

- **Feature names**: `audience` (not `audience_binding`) to match the
  SECURITY.md table written in M0.
- **Confinement fallback**: unavailable bwrap / non-Linux → warn + run
  normally, not fail closed. Availability wins; every fallback is
  audited and loud. Owner decision 2026-10-15: keep fail-open
  (option C) as a deliberate, documented deviation from the plan's
  "denied, never run unconfined."
- **`--unshare-pid` omitted** from the bwrap flags: on this VM it
  breaks the `/proc` mount (AppArmor/seccomp). Without it `--proc`
  mounts fine.
- **M4 Windows DACL check**: best-effort ctypes; untested on Windows
  (Linux-only QA here); degrades to WARN, never FAIL.
- **M8 `job_user`**: `preexec_fn` setuid; needs root. Non-root falls
  back loudly rather than refusing jobs. Owner decision 2026-10-15:
  keep fail-open (option C), same rationale as confinement.
- **M9/M10**: docs only, as specified.
- **Secret files** and the **confinement config schema** (`extra_flags`,
  `extra_ro_binds`, `work_mount`) are my schemas; the plan's versions
  were unavailable.

## This machine's real paths (M6)

- bwrap was **not** installed; installed `bubblewrap 0.9.0` via apt
  for the spike (ephemeral — the code handles its absence).
- `/usr/bin/python3` → `/usr/bin/python3.12`. usr-merged system:
  `/bin`, `/lib`, `/lib64` are symlinks into `/usr` — the sandbox
  needs `--symlink usr/lib /lib` etc. or the ELF interpreter is
  missing (this was the actual spike failure, not the mounts).
- Overlayfs root; user namespaces available
  (`kernel.unprivileged_userns_clone=1`).
- Sandbox proven: `/usr` read-only, no `/home`, no network, workdir
  writable, job env via `--setenv`, scrubbed credential vars absent.

## Verification

- Full suite green on every branch at commit time (1093 on the last).
- Parity harness: no-block / all-off / all-audit produce identical
  mail outputs; audit mode may log `would_*` decisions (M6+).
- M2 differential: 5000 random inputs, old regex vs new walk, zero
  mismatches.
- M5: signed job without `runner_id` rejected in enforce; job signed
  for runner A rejected by runner B.
- M6: real bwrap run — isolation, env, workdir write, result parity.
- M8: real setuid run as `pigeon-test` (root on this VM).
- M11: schtasks argv asserted (SYSTEM/HIGHEST default, named/LIMITED).

## Owner decisions needed

1. Merge order: the branches stack conceptually (m0 → m11) but each
   was cut from the previous tip; review/merge in order.
2. Whether any feature should be on by default (D9 says no; the
   recommendation stands).
3. M9/M10: approve the designs before any implementation.
4. The `pigeon-test` user and the apt-installed bwrap are VM-local;
   production boxes need their own.
