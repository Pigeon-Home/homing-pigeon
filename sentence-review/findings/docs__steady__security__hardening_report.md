# Findings — docs/steady/security/hardening_report.md

Source: docs/steady/security/hardening_report.md, reviewed at main 8696f0cc.
Sentence units: 79. Flagged: 2. Categories: pre-release 79, post-release 0.

The hardening effort's report: standing orders, the milestone table, and per-milestone outcomes in terse list entries. The table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "*Written 2026-10-15 as branch work against v3.5.2; those…" | pre-release | flows |  |
| 2 | "The "do not merge" lines below are the…" | pre-release | flows |  |
| 3 | "Every control except the M1 size caps (`max_job_bytes`…" | pre-release | flows |  |
| 4 | "Implemented Claude's security hardening runbook (M0–M11) against `main`…" | pre-release | flows |  |
| 5 | "Standing orders for the whole effort:" | pre-release | flows |  |
| 6 | "**D9**: everything off by default." | pre-release | flows |  |
| 7 | "With no `security` block the runner behaves exactly…" | pre-release | flows |  |
| 8 | "The design stays intact: signature-first verification, at-least-once delivery,…" | pre-release | flows |  |
| 9 | "Hardening hooks into them, it doesn't replace them." | pre-release | flows |  |
| 10 | "All security restrictions left at "almost 0": every…" | pre-release | flows |  |
| 11 | "Ship history: the twelve milestones were built on…" | pre-release | flows |  |
| 12 | "Post-ship review fixes (review findings 1, 4, 5)…" | pre-release | flows |  |
| 13 | "Follow-up items from the second review round (dangerous-env…" | pre-release | flows |  |
| 14 | "| Milestone | Branch | What landed |" | pre-release | flagged | A table header row — structure, not a sentence |
| 15 | "|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 16 | "| M0 | `hardening/m0-plumbing` | `runner/security.py`: `sec_mode`/`sec_decide` (off/audit/enforce),…" | pre-release | flows |  |
| 17 | "Startup hook in `main()`." | pre-release | flows |  |
| 18 | "Parity harness (`tests/security_parity.py`): 12-job corpus, normalized comparison across…" | pre-release | flows |  |
| 19 | "| M1 | `hardening/m1-fixes` | Two defect fixes.…" | pre-release | flows |  |
| 20 | "| M2 | `hardening/m2-policy` | `key_policies` gains `allowed_env`,…" | pre-release | flows |  |
| 21 | "`DANGEROUS_ENV_NAMES` (BASH_ENV, LD_PRELOAD, PYTHONPATH, …) denied for policy…" | pre-release | flows |  |
| 22 | "Pinned scripts carrying unlisted env/files are denied." | pre-release | flows |  |
| 23 | "`args_pattern` validated at startup with a backtracking probe;…" | pre-release | flows |  |
| 24 | "PROTOCOL.md's "cannot be repurposed" claim is now backed…" | pre-release | flows |  |
| 25 | "| M3 | `hardening/m3-audit-report` | `--audit-report [--since 14d\|48h]`:…" | pre-release | flows |  |
| 26 | "Dangerous env names and URL file sources are…" | pre-release | flows |  |
| 27 | "Works without mailbox credentials; never writes `config.json` (mtime+hash…" | pre-release | flows |  |
| 28 | "| M4 | `hardening/m4-posture` | `--posture`: exit 0/1/2…" | pre-release | flows |  |
| 29 | "`validate_shared_secret` moved to `security.py` (re-exported, not copied)." | pre-release | flows |  |
| 30 | "0600 checks on Linux; best-effort Windows DACL check…" | pre-release | flows |  |
| 31 | "| M5 | `hardening/m5-audience` | `audience` feature (off/audit/enforce)." | pre-release | flows |  |
| 32 | "Config `runner_id` (wizard generates one for fresh configs);…" | pre-release | flows |  |
| 33 | "Enforced for jobs, queries (covers the `ask` op),…" | pre-release | flows |  |
| 34 | "Replay-cache keys namespaced by `runner_id` when set. |" | pre-release | flows |  |
| 35 | "| M6 | `hardening/m6-confinement` | `confinement` feature: `exec`…" | pre-release | flows |  |
| 36 | "Proven on this machine (see below)." | pre-release | flows |  |
| 37 | "Fallback chain: unavailable → loud WARN + audit…" | pre-release | flows |  |
| 38 | "| M7 | `hardening/m7-templates` | `hardening/`: systemd unit,…" | pre-release | flows |  |
| 39 | "Opt-in only; `install.py --help` doesn't mention them. |" | pre-release | flows |  |
| 40 | "| M8 | `hardening/m8-secrets` | `shared_secret_file` / `additional_secrets_files`…" | pre-release | flows |  |
| 41 | "`job_user` feature: jobs run as another POSIX user…" | pre-release | flows |  |
| 42 | "| M9 | `hardening/m9-m10-design-docs` | `docs/asymmetric-signing-design.md`: Ed25519 migration…" | pre-release | flows |  |
| 43 | "Not implemented. |" | pre-release | flows |  |
| 44 | "| M10 | `hardening/m9-m10-design-docs` | `docs/approval-gate-design.md`: human approval…" | pre-release | flows |  |
| 45 | "Not implemented. |" | pre-release | flows |  |
| 46 | "| M11 | `hardening/m11-windows-run-as` | `install.py --run-as USER`:…" | pre-release | flows |  |
| 47 | "Named accounts get `/RL LIMITED`." | pre-release | flows |  |
| 48 | "Docs in INSTALL.md." | pre-release | flows |  |
| 49 | "Verified via schtasks argv inspection. |" | pre-release | flows |  |
| 50 | "Final suite at ship: **1093 tests green** (945…" | pre-release | flows |  |
| 51 | "Post-ship follow-ups add more; see the test files." | pre-release | flows |  |
| 52 | "The companion `security-hardening-plan.md` was not in the repo,…" | pre-release | flows |  |
| 53 | "**Feature names**: `audience` (not `audience_binding`) to match the…" | pre-release | flows |  |
| 54 | "**Confinement fallback**: unavailable bwrap / non-Linux → warn…" | pre-release | flows |  |
| 55 | "Availability wins; every fallback is audited and loud." | pre-release | flows |  |
| 56 | "Owner decision 2026-10-15: keep fail-open (option C) as…" | pre-release | flows |  |
| 57 | "**`--unshare-pid` omitted** from the bwrap flags: on this…" | pre-release | flows |  |
| 58 | "Without it `--proc` mounts fine." | pre-release | flows |  |
| 59 | "**M4 Windows DACL check**: best-effort ctypes; untested on…" | pre-release | flows |  |
| 60 | "**M8 `job_user`**: `preexec_fn` setuid; needs root." | pre-release | flows |  |
| 61 | "Non-root falls back loudly rather than refusing jobs." | pre-release | flows |  |
| 62 | "Owner decision 2026-10-15: keep fail-open (option C), same…" | pre-release | flows |  |
| 63 | "**M9/M10**: docs only, as specified." | pre-release | flows |  |
| 64 | "**Secret files** and the **confinement config schema** (`extra_flags`,…" | pre-release | flows |  |
| 65 | "bwrap was **not** installed; installed `bubblewrap 0.9.0` via…" | pre-release | flows |  |
| 66 | "`/usr/bin/python3` → `/usr/bin/python3.12`. usr-merged system: `/bin`, `/lib`, `/lib64`…" | pre-release | flows |  |
| 67 | "Overlayfs root; user namespaces available (`kernel.unprivileged_userns_clone=1`)." | pre-release | flows |  |
| 68 | "Sandbox proven: `/usr` read-only, no `/home`, no network,…" | pre-release | flows |  |
| 69 | "Full suite green on every branch at commit…" | pre-release | flows |  |
| 70 | "Parity harness: no-block / all-off / all-audit produce…" | pre-release | flows |  |
| 71 | "M2 differential: 5000 random inputs, old regex vs…" | pre-release | flows |  |
| 72 | "M5: signed job without `runner_id` rejected in enforce;…" | pre-release | flows |  |
| 73 | "M6: real bwrap run — isolation, env, workdir…" | pre-release | flows |  |
| 74 | "M8: real setuid run as `pigeon-test` (root on…" | pre-release | flows |  |
| 75 | "M11: schtasks argv asserted (SYSTEM/HIGHEST default, named/LIMITED)." | pre-release | flows |  |
| 76 | "~~Merge order~~ — done: merged to `main`, tagged…" | pre-release | flows |  |
| 77 | "Whether any feature should be on by default…" | pre-release | flows |  |
| 78 | "M9/M10: approve the designs before any implementation." | pre-release | flows |  |
| 79 | "The `pigeon-test` user and the apt-installed bwrap are…" | pre-release | flows |  |
