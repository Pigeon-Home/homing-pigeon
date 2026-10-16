# Gap analysis: hardening implementation vs plan + runbook

*Reviewer: Muse (subagent). Date: 2026-10-15. Sources:
`claude-plan/security-hardening-plan.md` (769 lines, "the plan"),
`claude-plan/security-hardening-runbook.md` (586 lines, "the runbook").
Implementation: `main` at `eb43897` (post-merge of `hardening/m0-*`
through `hardening/m11-*`), plus the two CI-fix commits. Nothing was
modified for this review — report only.*

Method: read both documents fully, then read `runner/security.py`,
`runner/sandbox.py`, `runner/auditreport.py`, `runner/posture.py`, the
M2/M5/M6/M8 sections of `runner/runner.py`, `runner/review.py` (M1a),
`runner/setup.py`, `runner/install.py`, `cloud/send_job.py`,
`hardening/*`, `docs/asymmetric-signing-design.md`,
`docs/approval-gate-design.md`, `PROTOCOL.md`, `SECURITY.md`,
`docs/threat-model.md`, `README.md`, `INSTALL.md`,
`HARDENING_REPORT.md`, and the hardening test files.

Overall: the work is real and substantially complete. Every milestone
has code, tests, and docs. The gaps below are specific and fixable;
none suggests the effort needs redoing. Items are ordered by severity
within each section.

---

## (a) Verdict per milestone

| Milestone | Verdict | One-line summary |
|---|---|---|
| M0 plumbing | **Diverged (minor)** | Works, but `sec_decide` returns strings not bool; audit entries lack `mode`; counts file tracks findings only, not evaluations; `approval` missing from `FEATURES`; `audit_log` config option missing |
| M1a regex | **Done** | Quote-walk replaces regex; 5000-case differential; 1M-char < 2s test |
| M1b size caps | **Done** | Defaults 1MiB/4MiB, 0=unlimited, pre-signature check, config errors |
| M2 policy constraints | **Partial** | Core works; `allow_file_urls` and `max_args` missing; `args_pattern` 200-char limit missing; dangerous-names list short; `allow_dangerous_env` escape hatch missing (weaker substitute in place) |
| M3 `--audit-report` | **Partial** | Read-only, no-mailbox, refused-to-suggest all work; but no `--key`/`--feature` filters, no per-key `key_policies` fragments (the audit2allow core), no "jobs evaluated" counts |
| M4 `--posture` | **Partial** | Solid base; missing 5 of the plan's checks and the startup summary line; exit codes 0/1/2 vs plan's 0/1 |
| M5 audience | **Partial** | Enforcement solid (jobs, queries, board, sensor); `send_job.py --aud` missing; `runner_id` is 64-bit not 128-bit; installer doesn't generate it; wire field named `runner_id` not `aud` |
| M6 confinement | **Diverged (documented)** | bwrap path proven; but fail-open on missing backend contradicts plan; no `backend` selection, no systemd-run, no `network` option; schema renamed; no Win/macOS design notes |
| M7 templates | **Partial** | Files exist and are reasonable; AppArmor profile lacks the complain flag (ships enforcing); no tested/untested headers; SELinux not labeled experimental/permissive; no `systemd-analyze verify` record |
| M8 secrets + job_user | **Partial** | `shared_secret_file` + `additional_secrets_files` work; `mailbox_password_file` missing; mutual-exclusion instead of value-wins+warning; preexec_fn instead of Popen `user=`; fail-open instead of deny; no world-readable warning |
| M9 design doc | **Partial** | Good doc; missing the plan's 3-option comparison (ssh-keygen -Y not evaluated); thin threat review of the new mechanism; no signed-`alg` field spec |
| M10 design doc | **Partial** | Good doc; no three-state audit/enforce integration; approval message format (job id + script SHA-384) unspecified; recommends CLI first vs plan's signed-email first |
| M11 Windows --run-as | **Partial** | Flag works, default stays SYSTEM, INSTALL.md documents it; `hardening/windows.md` missing; no icacls guidance; `--posture` doesn't mention the SYSTEM default |

---

## High severity

### H1. `runner/security.py:79` uses `str | None` — breaks Python 3.9
`pyproject.toml` declares `requires-python = ">=3.9"` (plan D5, runbook
rule 6: no `X | Y` unions evaluated at runtime). `security.py` has no
`from __future__ import annotations`, so `def _secret_pattern_reason(secret: str) -> str | None` raises `TypeError` at **import** time on 3.9 — the entire security module (and everything importing it) fails to load. `runner/setup.py:51,183` already had this pattern pre-hardening, but `security.py` is new hardening code repeating the violation. Fix: `Optional[str]` or add the future import.

### H2. M6/M8 fail open where the plan demands fail closed (documented divergence — needs explicit owner sign-off)
- Plan principle 3: "Enforce fails closed. A control that cannot evaluate (missing backend, malformed policy) denies in enforce mode." Plan M6: "**If the backend is missing or fails to start, the job is denied**, never run unconfined."
- Implementation (`runner/runner.py`, `_confinement_argv`): missing bwrap / non-Linux / build failure → loud WARN + `fallback` audit entry + **job runs normally**. Same for M8 `job_user` when not root or user missing (`_job_user_preexec` → WARN + fallback + runs as current user; plan M8: "enforce runs as `job_user` and denies if the switch fails").
- `HARDENING_REPORT.md` documents this as "Availability wins" and `SECURITY.md` describes the fallback honestly, so it is not hidden — but it directly contradicts a plan principle and the runbook's stop conditions ("A milestone needs..." / principle 3). The owner must explicitly accept fail-open, or the behavior must change. Do not leave this as an undocumented default.

### H3. `DANGEROUS_ENV_NAMES` is missing `PATH` and most of appendix A
`runner/security.py:33-49` lists 14 names. Plan appendix A lists ~30,
including `PATH`, `IFS`, `SHELLOPTS`, `BASHOPTS`, `PS4`, `PROMPT_COMMAND`,
`DYLD_*`, `PYTHONINSPECT`, `PYTHONUSERBASE`, `NODE_PATH`, `PERL5OPT`,
`JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS`, `CLASSPATH`, `GIT_EXEC_PATH`,
`GIT_CONFIG_*`, `COMSPEC`, `PATHEXT`, `PSModulePath`. The runbook (M2.4)
requires "a test that checks it contains the documented names" —
`tests/test_policy_constraints.py::DangerousNamesTest::test_constant_contains_documented_names`
passes against the *short* list, so the test does not catch this. A
policy with `allowed_env: ["PATH", ...]` on a pinned script currently
permits `PATH` hijacking with no finding at all.

### H4. No `allow_dangerous_env` gate — dangerous names are allowable via plain `allowed_env`
Plan M2: "Even when allowed explicitly, these names are refused unless
the policy sets `allow_dangerous_env: true`." Implementation
(`runner/runner.py:647-649`): a dangerous name is refused **unless
listed in `allowed_env`** — i.e. the plan's explicit second opt-in was
replaced by the ordinary allowlist. `tests/test_policy_constraints.py::test_dangerous_env_allowed_when_listed`
enshrines this weaker semantic. Combined with H3, the F1 fix is
softer than specified.

### H5. `PROTOCOL.md:87` documents the feature as `audience_binding`; the code only accepts `audience`
`validate_security_config` (`runner/security.py:160-165`) rejects
unknown feature names. A user following PROTOCOL.md will write
`security.modes.audience_binding: "enforce"` and get a startup error
naming it unknown. Doc-vs-code breakage, user-facing.

### H6. AppArmor profile ships without the complain flag — it would enforce
Plan M7: "a profile that ships in **complain** mode." `hardening/apparmor/homing-pigeon` has no `flags=(complain)` (verified by grep). Anyone loading it as documented (`apparmor_parser -r`) gets an enforcing profile that was never validated on their distro — the exact leap-of-faith the plan's permissive-first ladder exists to prevent.

---

## Medium severity

### M2.1 `allow_file_urls` and `max_args` are not implemented
Plan M2's field table specifies both; the plan's reason list includes
`file_url_not_allowed` and `args_too_many`. `build_key_policies`
(`runner/runner.py:440-504`) parses `allowed_env`, `denied_env`
(unplanned addition), `allowed_files`, `args_pattern` only. Grep for
`allow_file_urls` / `max_args` across `runner/`: no hits. URL file
sources are therefore unrestricted by key policy in every mode.

### M2.2 `args_pattern` has no 200-character length cap
Plan M2: "validated at startup (length at most 200, must compile,
rejected if it contains nested quantifiers on a wildcard)." The
implementation (`runner/runner.py:480-502`) checks non-empty,
compiles, and runs a timing probe (30 a's, 1.0 s bound — a reasonable
substitute for the structural nested-quantifier check), but never
checks length. A 10 KB pattern compiles fine and is probed only
against one hostile input.

### M2.3 Field renamed: `allowed_file_names` → `allowed_files`
Plan M2 specifies `allowed_file_names`. Code, `PROTOCOL.md`, and
`config.example.json` consistently use `allowed_files`. Internally
consistent, but diverges from the plan's schema; anyone writing
config from the plan document gets a silently-ignored unknown key
(`build_key_policies` drops unknown keys without error).

### M3.1 `--audit-report` never suggests a `key_policies` fragment
Plan M3's core deliverable: "For each key, a suggested `key_policies`
fragment containing only the observed, non-dangerous env names, file
names and arg shapes that triggered findings, each with counts."
`runner/auditreport.py::build_report` emits only generic lines
('key "x": N "reason" findings in audit mode; consider tightening the
policy or switching the feature to enforce'). The audit2allow value
proposition is not implemented.

### M3.2 `--audit-report` lacks `--key` and `--feature` filters
Plan M3: `--audit-report [--since 14d] [--key KEY] [--feature NAME]`.
Argparse (`runner/runner.py:4372-4377`) defines only `--since`.

### M3.3 Report table lacks mode, evaluated counts, first/last seen
Plan M3 requires: "feature, mode, jobs evaluated, would-deny count,
distinct reasons, first and last seen." Implementation prints
feature/decision/reason/count. "Jobs evaluated" is unimplementable
as built: the counter file (`security-audit-counts.json`) is bumped
only in `write_audit_entry`, i.e. only on findings, never on every
evaluation as plan 5.3 requires ("updated on every evaluation in
audit and enforce modes"). Plan appendix C's example `EVALUATED 412`
column cannot be produced.

### M4.1 Five plan checks missing from `--posture`
Plan M4 requires: running as root/SYSTEM; `workspace_root` unset;
confinement backend installed (M6); service unit hardening directives
(M7); "any feature in `off` mode that the posture considers
recommended." `runner/posture.py::build_posture` checks: config
readable, file perms, secret strength, audit log presence, base dir,
active modes, key-policy entries. It also doesn't flag individual
additional keys lacking policies (only counts entries) nor report
`key_policies_default_deny`. And "A startup log line prints a one-line
summary" — no such line exists in `runner.py` startup.

### M4.2 `--posture` exit codes are 0/1/2; plan says 0/1
Plan M4: "Exit code 0 when nothing fails, 1 on any fail."
Implementation: 0=all-OK, 1=WARN, 2=FAIL (`runner/posture.py:219-224`).
Arguably better, but the README flag table documents 0/1/2 while the
plan specifies 0/1 — pick one and reconcile.

### M5.1 `cloud/send_job.py` has no `--aud` flag
Plan M5: "`cloud/send_job.py` gains `--aud RUNNER_ID`." Grep confirms:
no `aud` argument exists. There is currently no supported way to set
the audience claim from the sender tool (the wire field is
`runner_id`, see M5.4).

### M5.2 `runner_id` is 64-bit, not 128-bit; installer doesn't generate one
Plan M5: "generate a random 128-bit identifier (hex)". `runner/setup.py:290` uses `secrets.token_hex(8)` = 8 bytes = **64 bits**. `runner/install.py` never generates a `runner_id` at all (plan: "The setup wizard and installer generate").

### M5.3 Wire field is `runner_id`, not `aud`
Plan M5: 'Optional signed field `aud` (string)'. Implementation and
`PROTOCOL.md` consistently use `runner_id` in the signed body. Code
and docs agree with each other; both diverge from the plan. Lower
risk than H5 since it's consistent, but the plan's name should be
adopted or the divergence recorded.

### M5.4 Single reason `runner_id_mismatch`; plan wants `aud_missing` / `aud_mismatch`
`check_audience` (`runner/runner.py:705-722`) collapses absent and
mismatched into one reason, so operators can't distinguish
not-yet-migrated senders from cross-runner replays in the audit log.

### M6.1 No `backend` selection, no systemd-run, no `network` option
Plan M6 config: `{"backend": "auto"|"bwrap"|"systemd-run"|"none", "network": "inherit", "hide_base_dir": true, "extra_ro_paths": []}`.
Implementation (`runner/sandbox.py`) hardcodes bwrap, always passes
`--unshare-net` (no `network: inherit` option), and uses a different
schema (`extra_flags`, `extra_ro_binds`, `work_mount`). The report
notes "the plan's versions were unavailable" — they were in the plan
document. Base-dir hiding is achieved implicitly (base dir is never
mounted), which is fine, but the operator-facing schema diverged.

### M6.2 No Windows/macOS confinement design notes
Plan M6 and runbook M6.6: "Windows (Job Objects, restricted tokens),
macOS (the sandbox tooling is deprecated). Each gets a short design
note, not code" in `hardening/`. No such notes exist.

### M7.1 Template headers lack tested/untested status; SELinux not labeled experimental/permissive
Runbook M7.3: 'Each template starts with a header comment stating its
status: "untested" or "tested on <distribution, version>".' None of
the three templates has such a header (verified by grep). Plan M7:
SELinux skeleton "shipped **permissive** and labeled experimental"
— `homing_pigeon.te` contains no `permissive` statement and no
"experimental" label. Runbook M7.4 (`systemd-analyze verify`) has no
record of being run.

### M8.1 `mailbox_password_file` missing
Plan M8: "Support `shared_secret_file` and `mailbox_password_file`."
Only the former (plus the unplanned `additional_secrets_files`) exists.

### M8.2 Both-inline-and-file is a hard error; plan says value wins + warning
Plan M8: "If both a value and a file are present, the value wins and a
warning is logged." `build_secrets` (`runner/runner.py:355-357, 384-387`)
raises `RuntimeError` (mutually exclusive). Stricter than specified;
the plan's leniency was presumably to ease migration.

### M8.3 `job_user` uses preexec_fn setuid, not Popen `user=`/`group=`/`extra_groups=`
Plan M8 explicitly names the Popen parameters (available since 3.9, the
stated reason D5 stays at 3.9). Implementation (`_job_user_preexec`,
`runner/runner.py:802-870`) uses `preexec_fn` + `os.setuid/setgid`.
Functionally similar, but diverges from the specified mechanism, and
`extra_groups=` support is absent (no group/extra_groups handling at
all — only uid/gid via setuid/setgid).

### M8.4 No world-readable warning on secret files
Plan M8: "Files are read once at startup and must not be
world-readable on POSIX (warn if they are)." `_read_secret_file`
(`runner/runner.py:326-340`) checks readability and non-emptiness
only; no mode check, no warning.

### M9.1 Design doc doesn't evaluate the plan's three options
Plan M9 requires comparing (1) `ssh-keygen -Y sign/verify`, (2)
vendored pure-Python Ed25519, (3) optional `cryptography`
dependency, with "the likely recommendation" being option 1.
`docs/asymmetric-signing-design.md` proposes Ed25519-with-public-keys
without evaluating option 1 at all, discusses only the dependency
question for option 2/3, specifies no signed `alg` field on the wire
(only an audit-log `alg` tag), and its threat review covers why HMAC
is weak, not what new risks the Ed25519 mechanism adds (SI private-key
custody, key distribution ceremony).

### M10.1 Design doc has no three-state audit/enforce integration
Plan M10: "Modes: `audit` logs 'would require approval' and runs the
job; `enforce` holds it." The doc's modes are per-key
`off/all/review-flagged/destructive` with no mapping to the
off/audit/enforce model. It also recommends the local CLI first vs
the plan's "signed email first," and never specifies the approval
message format the plan requires (job id + SHA-384 of script) or a
dedicated approval secret (it leans on the M9 owner keypair instead —
reasonable, but a divergence from the specified separate secret).

### M11.1 `hardening/windows.md` missing; no icacls guidance
Plan M11 requires the doc, "and notes the Windows constraint that
`os.chmod` cannot set Unix permission bits, so file ACLs need to be
set with `icacls`." Neither `hardening/windows.md` nor any icacls
mention exists (INSTALL.md covers `--run-as` well otherwise). Plan
also says "The install output and `--posture` both mention it [the
SYSTEM default]" — install output does; `--posture` has no
running-as-SYSTEM check at all.

### M0.1 `sec_decide` returns `"allow"`/`"deny"` strings, not bool
Runbook M0.1: 'Add `sec_mode` and `sec_decide` **exactly as plan
section 5.2 specifies**' — which specifies bool returns (`return True`
/ `return False`). `runner/security.py:284-322` returns strings.
Callers (`runner/runner.py:3320-3344`, `audience_allows`) compare
against `"deny"`. Works, but not as specified; a future caller
following the plan's spec (`if not sec_decide(...)`) would treat
`"deny"` (truthy) as allow — a latent footgun worth fixing now.

### M0.2 Audit entries lack the `mode` field; `approval` not a recognized feature
Plan 5.3's entry format includes `"mode":"audit"`. `write_audit_entry`
(`runner/security.py:254-282`) writes ts/feature/decision/reason/
key_id/job_id/detail — no `mode`. Plan 5.1's config shape lists
`approval` under modes and runbook M0.2 says "accept the whole list
from the start"; `FEATURES` (`runner/security.py:26-34`) omits
`approval`, so a config written from the plan is rejected at startup.
Also plan 5.1's `audit_log` path option is not implemented at all —
the path is hardcoded to `security-audit.jsonl`.

---

## Low severity / doc accuracy

- **L1. `SECURITY.md:126-127`** says "The config file is read once at
  startup; it is not re-read each poll cycle." False: `runner.py`
  hot-reloads `HOT_KEYS`/`LIVE_KEYS` every cycle (`_reload_config`,
  ~line 3585). The effective claim — "changing a mode requires a
  restart" — is true (`security` is not a hot key), but the sentence
  as written is inaccurate.
- **L2. `HARDENING_REPORT.md` is stale and mis-structured.** It says
  "Branch-only work. Nothing here touches `main`" (main has since been
  pushed and tagged-tracked), claims "1093 tests green" (now 1153+),
  doesn't mention the post-merge CI fixes (M6 audit-semantics change,
  backtrack-probe bump), and doesn't follow the runbook §9 report
  structure ("Use exactly this structure"). It also claims
  `validate_security_config` etc. without noting the divergences in
  the "Divergences" section (e.g. the fail-open decisions are there,
  but the `aud`→`runner_id` rename, `allowed_files` rename,
  `denied_env` addition, and `allow_dangerous_env` removal are not).
- **L3. Dangerous-name matching is case-insensitive on POSIX too.**
  Plan appendix A: "matched case-insensitively on Windows and
  case-sensitively elsewhere." Implementation (`runner/runner.py:647`)
  upper-cases everywhere. Errs toward safety; fine, but undocumented.
- **L4. `docs/threat-model.md` was not updated.** Plan §9: "link to
  this plan and say which findings are addressed by which shipped
  milestones." No mention of the hardening plan or milestones (grep).
- **L5. PROTOCOL.md lacks the `runner_id` rotation story.** Plan M5
  requires documenting that changing `runner_id` invalidates
  previously signed jobs. The field is documented; rotation is not.
- **L6. M2 reason names diverged from the plan's list.** Plan:
  `env_not_allowed`, `env_dangerous`, `files_not_allowed`,
  `file_url_not_allowed`, `args_too_many`, `args_not_allowed`,
  `pinned_script_with_env`, `pinned_script_with_files`. Code:
  `env_not_allowed`, `dangerous_env`, `denied_env`,
  `file_not_allowed`, `arg_too_long`, `arg_pattern_mismatch`,
  `pinned_script_with_env`, `pinned_script_with_files`. Consistent
  internally; anyone correlating against the plan will mismatch.
- **L7. Case-sensitivity helper `_env_name_in`** (`runner/runner.py:612-619`)
  is case-insensitive on Windows for allow/deny lists, exact elsewhere
  — matches the plan. Fine; noting because L3 differs.

---

## (b) Doc-vs-code inconsistencies (user-facing)

1. `PROTOCOL.md:87` — `audience_binding` vs code's `audience` (**H5**).
   Startup-rejecting typo trap.
2. `SECURITY.md` confinement section describes fail-open accurately —
   consistent with code, contradicts the plan (see H2). Docs are
   honest; the plan is what's violated.
3. `PROTOCOL.md` §14.1 documents `denied_env`, `allowed_files`, and
   dangerous-names-allowed-when-listed — matches code, diverges from
   plan (M2.3, H4). Consistent internally.
4. `README.md:429-430` documents `--audit-report`/`--posture` flags —
   accurate as far as they go; doesn't mention the missing
   `--key`/`--feature` filters (M3.2).
5. `SECURITY.md:126-127` restart claim — inaccurate per L1.
6. `runner/config.example.json` — all features `off` ✓, matches D9.

---

## (c) Missing proofs (runbook §8 / §11 items not evidenced)

1. **Runbook M5.1** — no test that the signature verifier tolerates an
   unknown signed field (searched `tests/` for unknown/extra/bogus
   field tests; none). The `runner_id` claim rides in the signed body,
   so this proof matters.
2. **Runbook M7.4** — no record of `systemd-analyze verify` on the
   unit (run or "not run").
3. **Runbook M6.6 / plan M6** — no Windows/macOS confinement design
   notes, so nothing to review.
4. **M3's core proof** — `tests/test_audit_report.py` tests the table
   and refused-to-suggest, but there is no test (and no code) for the
   per-key `key_policies` fragment suggestions (M3.1).
5. **Dangerous-names test is tautological** — `test_constant_contains_documented_names`
   checks the constant against a test-local list, not against plan
   appendix A, so H3 passes the suite silently.
6. **Counts file** — `test_counts_file` (`tests/test_security_config.py:162`)
   asserts findings are counted; nothing asserts per-evaluation
   counting because the code doesn't do it (M3.3).
7. **Python 3.9** — runbook §8.6's `python3.9 -m py_compile` check; the
   `str | None` union (H1) would fail it. No 3.9 interpreter on this
   machine to confirm, but the syntax is unambiguous.

What *is* well-proven: the three-mode matrix for policy_env/files/args
(off/audit/enforce with mail-identity in audit), the parity harness
(no-block = all-off = all-audit, 12-job corpus), M1a differential
(5000 random inputs) + 1M-char timing, M1b caps (pre-signature, 0 =
unlimited, bad values rejected), M5 cross-runner rejection and seen
namespacing, M6 bwrap builder unit tests + enforce/skip behavior, M8
secret-file validation, M11 schtasks argv. No existing tests were
edited to make the suite pass (`tests/test_runner.py` untouched since
pre-hardening).

---

## (d) Scope additions beyond the plan (flagged, not judged)

1. **`denied_env`** key-policy field — not in plan M2. A blocklist
   complement to `allowed_env`. Harmless, arguably useful.
2. **Audience enforced for board messages, sensor alerts, and task_***
   — plan M5 says "jobs and queries." `audience_allows` is called on
   more paths. Broader than specified.
3. **Replay-cache namespacing by `runner_id`** (`_seen_key`,
   `runner/runner.py:738-745`) — unplanned, sensible.
4. **`additional_secrets_files`** — plan M8 asked only for
   `shared_secret_file` + `mailbox_password_file`; this adds
   per-key-id file indirection. Useful; `mailbox_password_file` itself
   is still missing (M8.1).
5. **Confinement schema** (`extra_flags`, `extra_ro_binds`,
   `work_mount`) — invented in place of the plan's
   (`backend`, `network`, `hide_base_dir`, `extra_ro_paths`).
6. **`validate_shared_secret` moved to `runner/security.py`**
   (re-exported from `runner.py`) — refactor, no behavior change.
7. **`--unshare-pid` omitted** from bwrap flags (documented: breaks
   /proc mount on the build VM). Reasonable, recorded.
8. **`_env_name_in` / platform case rules** — matches plan; the
   *global* case-insensitive dangerous match (L3) is the addition.

---

## Suggested fix order (if the owner wants a hardening pass 2)

1. H1 (3.9 import break) — one-line fix, blocks the stated platform floor.
2. H5 (PROTOCOL `audience_binding`) — one-word doc fix, user-facing trap.
3. H6 (AppArmor complain flag) — one-line template fix, safety-relevant.
4. H3+H4 (dangerous names: restore appendix-A list, add `allow_dangerous_env`) — the F1 fix's core.
5. H2 (fail-open vs fail-closed) — needs an owner decision first; code either way is small.
6. M5.1+M5.2 (`--aud`, 128-bit `runner_id`, installer generation) — completes the milestone's wire story.
7. M2.1+M2.2 (`allow_file_urls`, `max_args`, pattern length cap).
8. M3.1 (per-key fragments) or descope M3's audit2allow claim in docs.
9. M0.1 (`sec_decide` bool), M0.2 (`mode` field, `approval` feature) — spec-alignment cleanup.
10. Everything else is docs/labels/tests.

*End of report.*
