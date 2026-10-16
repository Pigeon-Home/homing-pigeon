# Security hardening plan — permissive first

Status: **spec only**. Nothing in this document is implemented yet.
Written by Claude at the owner's request, against Homing Pigeon v3.5.1
(422 tests passing at the time of writing). Companion file:
`security-hardening-runbook.md`, the step-by-step procedure for the LLM
that will implement this plan.

Persona note, since this project has a sense of humor: the author of
this plan is the project's designated grump. The grump's job is to say
"that is a hole" early and politely, then help fill it in without
breaking the fun. Every control below ships **off**. Nothing here is
allowed to surprise an existing deployment.

---

## 1. Purpose

Homing Pigeon lets a cloud SI run code on a machine you own. The
signature is the only gate, and the project says so plainly in
`SECURITY.md` and `docs/threat-model.md`. This plan does not try to
change that stance. It adds optional controls that shrink what a valid
signature can do, and a way to turn each control on safely.

The model for adoption is SELinux, specifically its permissive mode:

1. Ship the control, off.
2. Turn it on in **audit** mode, where it evaluates every job and logs
   "would have denied" but blocks nothing.
3. Read the log against real traffic. Fix policies, or accept the
   findings as true positives.
4. Turn it on in **enforce** mode, one feature at a time.
5. If it breaks something, drop back to audit. No data migration, no
   downtime.

The goal is that tightening the box is a reviewed, reversible, boring
operation, not a leap of faith.

## 2. Principles

These apply to every milestone. A change that violates one is wrong,
even if its tests pass.

1. **Off is the default, and off means byte-identical behavior.** With
   no `security` block in `config.json`, the runner must behave exactly
   as v3.5.1 does. A parity test enforces this (section 8).
2. **Audit never changes outcomes.** A job that runs in `off` mode must
   run, with the same result mail, in `audit` mode. The only difference
   is a line in the audit log.
3. **Enforce fails closed.** A denied job is rejected through the existing
   reject path: logged, marked seen, never retried. A control that cannot
   evaluate (missing backend, malformed policy) denies in enforce mode
   and refuses to start on a malformed config, as `key_policies` already
   does.
4. **Malformed config stops startup.** Unknown mode strings, wrong types,
   and unknown feature names are config errors with a clear message. Do
   not silently treat a typo as "off". A typo in a security setting should
   be loud.
5. **Stdlib only.** The project's identity is Python 3.9+ standard
   library. Anything that needs a dependency is a design spike that waits
   for owner approval.
6. **No secrets in logs.** Audit entries carry names, counts, key ids,
   job ids and hashes. They never carry env values, script text, file
   contents, shared secrets or mailbox credentials.
7. **The Oracle stays advisory.** Nothing in this plan makes the Oracle
   an enforcement authority. Enforcement is deterministic code and the
   operating system. The Oracle may read the audit log and comment on it.
8. **Every control has a rollback.** The runbook for each milestone says
   how to turn it off again, and that path is tested.
9. **Bug fixes are not features.** A quadratic regex is not an opt-in
   hardening option. Real bugs are fixed outright, with tests proving
   existing behavior is preserved.
10. **Small, reviewable steps.** One branch per milestone, one concern
    per commit, tests in the same commit as the code.

## 3. Baseline — what exists today

Observed in v3.5.1. Treat function names as the stable reference and line
numbers as drifting.

- **Signing.** HMAC-SHA-384 over a signed JSON object inside the mail body.
  The key is the UTF-8 bytes of a dedicated `shared_secret`. Additional
  keys live in `additional_secrets`, selected by a signed `key_id`. The
  runner rejects weak secrets at startup.
- **Freshness and replay.** A signed `issued_at` must fall inside
  `max_job_age_sec` (default 3600). A persisted seen-set rejects repeats.
- **Key policies.** `key_policies` can restrict a key by `allowed_kinds`,
  `allowed_interpreters`, `max_timeout_sec` and `allowed_script_sha384`.
  Keys without an entry are unrestricted, unless `key_policies_default_deny`
  is set, which refuses additional keys that have no entry. The default key
  (empty key id) is always unrestricted. A startup warning lists additional
  keys with no policy.
- **Execution.** `execute_job` runs the script with the job's interpreter,
  copies the runner's environment, scrubs `PIGEON_*` variables, then layers
  the job's `env` on top. It also stages the job's `files` and passes the
  job's `args`.
- **Review and Oracle.** `review.py` runs advisory regex checks before
  execution. Results go through result policies, redaction, secret-fragment
  checks and optional local-model `ask` queries.
- **Events.** `_append_security_event` writes `security-events.jsonl`
  (capped at 5000 lines), which the DRI paging triggers read.
- **Tests.** `python3 -m unittest discover -s tests -t .` runs all of them.

## 4. Findings this plan responds to

Each finding names the milestone that addresses it.

| # | Finding | Severity | Milestone |
|---|---------|----------|-----------|
| F1 | `check_key_policy` ignores `env`, `args` and `files`. A hash-pinned script can still be steered by `BASH_ENV`, `PATH`, `LD_PRELOAD`, `PYTHONPATH`, or by a staged file the interpreter loads. | High | M2 |
| F2 | The review regex `_FILENAME_RE` is quadratic on a long run of characters after an unclosed quote. Measured at v3.5.1: 40,000 characters took about 1.7 s, 160,000 about 28 s. No script or body size cap was found. | Medium | M1 |
| F3 | Nothing in the signed payload names which runner a job is for. A secret reused across machines verifies on all of them inside the freshness window. | Medium | M5 |
| F4 | The key is symmetric, so whatever signs jobs holds the key the runner uses to verify. | Medium | M9 |
| F5 | A job runs as the runner's user and can read `config.json`, which holds the shared secret and mailbox credentials. Scrubbing `PIGEON_*` env vars does not cover this. | Medium | M8 |
| F6 | On Windows the installer registers the task as SYSTEM, so every job runs with full machine privilege. | Medium | M11 |
| F7 | Jobs are not confined. Confinement today is detection (workspace snapshots and attestations), not prevention. | Medium | M6, M7 |
| F8 | Keys without a policy are unrestricted by default. Default-deny exists but is opt-in. | Low | covered by M3 and M4 |
| F9 | High-risk jobs have no human gate. | Low | M10 |

The owner has said some of these are not a current worry (F5, F6, F8).
They stay in the plan because everything here is optional and off by
default. The owner can cut any milestone without affecting the others.

## 5. The three-state model

Every security feature has a name and one of three modes.

| Mode | Evaluates the control | Logs findings | Blocks jobs |
|------|-----------------------|---------------|-------------|
| `off` | no | no | no |
| `audit` | yes | yes (`would_deny`) | no |
| `enforce` | yes | yes (`denied`) | yes |

The default for every feature is `off`.

### 5.1 Configuration shape

```json
"security": {
  "audit_log": "security-audit.jsonl",
  "audit_max_lines": 20000,
  "modes": {
    "policy_env": "off",
    "policy_files": "off",
    "policy_args": "off",
    "audience": "off",
    "confinement": "off",
    "job_user": "off",
    "approval": "off"
  }
}
```

Rules:

- The whole `security` block is optional. Absent means every feature is off.
- Valid mode values are exactly `off`, `audit`, `enforce`. Anything else
  is a startup error that names the feature and the bad value.
- Unknown feature names under `modes` are a startup error, so a misspelled
  feature does not quietly stay off.
- `audit_log` is relative to the runner's base directory. It is a
  separate file from `security-events.jsonl` on purpose: audit findings
  must never feed the DRI paging triggers.
- `audit_max_lines` bounds the log. When exceeded, roll to a single `.1`
  file, the same pattern the Oracle chat log uses.

### 5.2 Shared helpers (milestone M0)

Two small functions carry the whole model, so every feature behaves the
same way.

```text
sec_mode(cfg, feature) -> "off" | "audit" | "enforce"

sec_decide(cfg, base_dir, feature, reason, ctx) -> bool
    reason is None when the job passes the control.
    off      -> return True, log nothing
    audit    -> if reason: log would_deny; return True
    enforce  -> if reason: log denied; return False; else return True
```

Callers treat `False` as a rejection through the existing reject path and
emit the existing `auth_rejection` security event with a `reason` naming
the feature. They never invent a second rejection path.

### 5.3 Audit log entry

One JSON object per line.

```json
{"ts":"2026-10-16T14:03:11Z","feature":"policy_env","mode":"audit",
 "decision":"would_deny","key_id":"test-runner","job_id":"j-1842",
 "reason":"env_not_allowed",
 "detail":{"env_names":["BASH_ENV"],"script_sha384":"3f9a..."}}
```

Fields:

- `decision` is `would_deny` (audit) or `denied` (enforce). Passing jobs
  are not logged, to keep the log small. A `--audit-report` run also
  needs the count of jobs seen, so the runner keeps a tiny per-feature
  counter file (`security-audit-counts.json`) updated on every evaluation
  in audit and enforce modes.
- `detail` is an allowlisted structure per reason. Names and counts only.

### 5.4 Graduation checklist, audit to enforce

A feature moves from `audit` to `enforce` when the owner can answer yes to
all of these. The runbook produces the evidence. The owner decides.

1. The feature has run in audit mode for at least 14 days **or** 200 real
   jobs, whichever comes later.
2. Every distinct `would_deny` reason has been reviewed and is either a
   true positive (leave it denied) or fixed by a policy change.
3. `--audit-report` has suggested no new policy changes for 7 days.
4. The rollback (enforce back to audit) has been tried once on this host.
5. A known-good job and a known-bad job have both been sent on purpose
   after the switch, and behaved as expected.

### 5.5 Rollback

Changing a mode is a config edit plus a restart. The runbook for M0 must
confirm whether the runner re-reads `config.json` each poll cycle. If it
does not, the documentation says "restart the service" and the installer
prints the exact command per platform.

## 6. Milestones

Order matters: plumbing first, then fixes, then the controls that rely on
the plumbing, then the heavier work. Each milestone is its own branch.

---

### M0 — Mode plumbing and parity harness

**Goal.** Add `sec_mode`, `sec_decide`, config validation, the audit log
writer and the parity test harness. No feature uses them yet.

**Why first.** Everything later depends on one consistent mode model. The
parity harness is the safety net for every later milestone.

**Design.**
- Config parser: validates the `security` block at startup, next to
  `build_key_policies`.
- Audit writer: append-only, bounded, creates the file with mode 0600 on
  POSIX, never raises into the poll loop (best effort, like
  `_append_security_event`).
- Parity harness: a test helper that runs a corpus of representative jobs
  through `poll_once` with fake IMAP and SMTP (the existing tests already
  have `FakeIMAP` and `FakeSMTP`) and returns the normalized result mails.
  Normalize timestamps, durations and hostnames.
- `runner/config.example.json` gains a `security` block with every feature
  `off`.

**Tests.** Mode parsing (valid, invalid, unknown feature, wrong type),
audit writer (bounded, rolls, 0600, never raises), parity (no `security`
block versus all features `off` gives identical output).

**Done when.** Existing 422 tests still pass, new tests pass, and a diff of
runtime behavior with default config is empty.

---

### M1 — Bug fixes with no flag

**Goal.** Fix F2. These are the only changes that apply by default,
because they remove a defect and do not add a restriction.

**M1a, review regex.** Replace the lazy-quantifier pattern in
`review.py` with a bounded, linear approach:

- Find quoted candidates with a pattern that cannot backtrack across the
  whole script, for example `['"]([^'"\n]{1,260})['"]`, then test each
  candidate (at most 260 characters) against a separate filename check.
- Cap how much of the script the review scans (`review_scan_bytes`,
  default 65536). Bytes past the cap are not scanned. Add a review note
  saying the scan was truncated.
- A differential test keeps the old pattern inside the test file and
  asserts the new code gives the same notes for candidate strings of 260
  characters or fewer.
- A timing test asserts a 1,000,000-character hostile script reviews in
  well under a second.

**M1b, size caps.** Add `max_script_bytes` and `max_job_bytes`.

- Locate where the mail body is read and where a job is parsed, and
  reject oversized input before signature work where possible.
- Rejection uses the existing reject path: logged, marked seen, never
  retried.
- **Default-on with generous values** (1 MiB script, 4 MiB job). This is the
  one place this plan deviates from "everything off". The owner may
  override by setting the values to `0` (unlimited). See section 10, Q1.

**Done when.** The 160,000-character script that took 28 seconds reviews in
milliseconds, the differential test passes, and legitimate jobs near the
caps still run.

---

### M2 — Key policy constraints for env, files and args

**Goal.** Fix F1 so a hash-pinned or kind-limited key cannot be steered
through the parts of a job the policy never looked at.

**New policy fields** (inside a `key_policies` entry):

| Field | Meaning |
|-------|---------|
| `allowed_env` | List of environment variable names the job may set. Empty list means none. Absent means "no constraint" unless the policy has `allowed_script_sha384` (below). |
| `allowed_file_names` | List of staged file names the job may carry. Empty list means none. |
| `allow_file_urls` | Boolean. When false, any `files` entry with a URL is refused. Default true when absent. |
| `max_args` | Integer cap on the number of args. |
| `args_pattern` | One anchored regex each arg must fully match. |

**Pinned-script rule.** If a policy has `allowed_script_sha384`, then
absent `allowed_env` means "no env at all", and absent `allowed_file_names`
means "no staged files". A pinned script is only pinned when nothing
else can change what it does. Operators who need env or files list them
explicitly. This is the core fix for F1 and should be called out in
`PROTOCOL.md`.

**Dangerous names.** Even when allowed explicitly, these names are
refused unless the policy sets `allow_dangerous_env: true` (appendix A):
loader and interpreter hooks such as `BASH_ENV`, `ENV`, `PATH`,
`LD_PRELOAD`, `LD_LIBRARY_PATH`, `PYTHONPATH`, `PYTHONSTARTUP`,
`PYTHONHOME`, `NODE_OPTIONS`, `PERL5OPT`, `RUBYOPT`, `DYLD_*`.

**Modes.** Three independent features: `policy_env`, `policy_files`,
`policy_args`. This lets the owner enforce env rules while still auditing
args.

**Regex safety.** `args_pattern` is validated at startup (length at most
200, must compile, rejected if it contains nested quantifiers on a
wildcard) and applied only to args of at most 1024 characters. Longer
args are denied. This is the lesson of F2 applied up front.

**Reasons logged.** `env_not_allowed`, `env_dangerous`,
`files_not_allowed`, `file_url_not_allowed`, `args_too_many`,
`args_not_allowed`, `pinned_script_with_env`, `pinned_script_with_files`.

**Scope.** Applies to keys that have a policy entry. The default key
(owner) is unrestricted unless the owner explicitly adds an entry under
`""`. Open question Q3 in section 10.

**Tests.** For each field and mode: allowed job passes, violating job is
logged in audit and still runs, violating job is denied in enforce. A
pinned job carrying `BASH_ENV` is denied in enforce. A test confirms the
default key is untouched. A test confirms no policy entry means no new
behavior.

**Done when.** The example in `PROTOCOL.md` ("a key issued to run the test
suite cannot be repurposed to run arbitrary shell") is actually true, with a
test that tries and fails.

---

### M3 — `--audit-report`, the audit2allow helper

**Goal.** Make tightening a review, not a guess.

**Behavior.** `python3 runner/runner.py --audit-report [--since 14d]
[--key KEY] [--feature NAME]` reads the audit log and counter file and
prints:

1. A table: feature, mode, jobs evaluated, would-deny count, distinct
   reasons, first and last seen.
2. For each key, a suggested `key_policies` fragment containing only the
   observed, non-dangerous env names, file names and arg shapes that
   triggered findings, each with counts.
3. A **refused to suggest** section listing dangerous env names that
   appeared, so the owner sees them without a tool endorsing them.

**Rules.**
- Read-only. It never writes `config.json`.
- It never emits a suggestion that would allow a dangerous name or a URL
  file source. Those require a human to type them.
- Output is plain text on stdout, so it can be pasted to the SI.
- It must work without the runner's mailbox credentials (no IMAP), like
  `--dry-run` style tooling.

**Tests.** Seed a fake audit log, assert the report, assert dangerous
names are refused, assert nothing is written.

---

### M4 — Posture check

**Goal.** One command that tells the owner where the box stands.

`python3 runner/runner.py --posture` prints pass, warn or fail for:

- Running as root or SYSTEM.
- `config.json` mode is not 0600, or is readable by group or other.
- `workspace_root` unset (confinement attestations are off).
- Additional keys with no policy, and whether `key_policies_default_deny`
  is set.
- Any feature in `off` mode that the posture considers recommended.
- Whether a confinement backend is installed (M6).
- Whether the service unit has hardening directives (M7), where it can
  tell.
- Secrets that look weak or patterned.

**Rules.** Read-only. Exit code 0 when nothing fails, 1 on any fail.
A startup log line prints a one-line summary but never blocks startup. A
`posture` enforce mode is deliberately not offered: a check that can
brick the runner on boot is a trap.

---

### M5 — Audience binding

**Goal.** Fix F3 so a job signed for one runner does not verify on another.

**Design.**
- Optional signed field `aud` (string) in jobs and queries. Because it is
  inside the signed body, the signature covers it.
- Config gains `runner_id`. The setup wizard and installer generate a
  random 128-bit identifier (hex) and store it. Hostnames collide, so do
  not default to the hostname.
- `cloud/send_job.py` gains `--aud RUNNER_ID`.

**Modes.** `audience`:
- `off`: `aud` ignored.
- `audit`: log `aud_missing` or `aud_mismatch` as would-deny.
- `enforce`: deny when `aud` is absent or not equal to `runner_id`.

**Compatibility.** Older senders omit `aud`. They keep working in `off`
and `audit`, and stop working in `enforce`, which is the point. The
runbook must verify that the current verifier tolerates an unknown signed
field and add a test that proves it.

---

### M6 — Per-job confinement (Linux first)

**Goal.** Fix F7 on Linux with prevention, not detection.

**Config.**

```json
"confinement": {
  "backend": "auto",
  "network": "inherit",
  "hide_base_dir": true,
  "extra_ro_paths": []
}
```

`backend` is `auto`, `bwrap`, `systemd-run`, or `none`.

**Behavior by mode** (feature `confinement`):
- `off`: today's behavior.
- `audit`: probe whether a backend is usable (for example `bwrap
  --version`), build the sandbox command line the job **would** run under,
  log it (without script content or env values) and run the job exactly
  as before.
- `enforce`: run the job inside the sandbox. Read-only root, writable job
  work directory, private `/tmp`, no new privileges, the runner's base
  directory (and therefore `config.json`) hidden, optional network
  unshare. **If the backend is missing or fails to start, the job is
  denied**, never run unconfined.

**Out of scope for the first pass.** Windows (Job Objects, restricted
tokens), macOS (the sandbox tooling is deprecated). Each gets a short
design note, not code.

**Tests.** Command-line builder is a pure function with unit tests. Real
sandbox tests run only when a backend is available and skip cleanly
otherwise. Enforce tests with a fake missing backend assert denial.

---

### M7 — OS hardening templates

**Goal.** Ship the operating-system layer the project's own docs point to,
as templates in a new `hardening/` directory.

Contents:

- `homing-pigeon.service.hardened`: a systemd unit with
  `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ProtectHome=read-only`,
  `PrivateTmp=yes`, `ReadWritePaths=` limited to the base directory,
  `RestrictAddressFamilies=`, `CapabilityBoundingSet=` empty, and a
  `SystemCallFilter=@system-service`.
- `apparmor/homing-pigeon`: a profile that ships in **complain** mode.
- `selinux/`: notes and a skeleton type-enforcement module for a
  `homing_pigeon_t` domain, shipped **permissive** and labeled
  experimental, because it cannot be validated on every distribution.
- `README.md`: the permissive-to-enforcing ladder, in the same spirit as
  this whole plan: complain or permissive first, read the denials, tighten,
  then enforce.

**Rules.** Nothing here is applied automatically. The installer may offer
the hardened unit behind an explicit flag. Each template says plainly
which distributions it was tested on. Untested means labeled untested.

---

### M8 — Secret and config isolation, `job_user`

**Goal.** Fix F5.

- Support `shared_secret_file` and `mailbox_password_file` so secrets can
  live in files the runner user owns (0600) and the job user cannot read.
- Support `job_user` (POSIX, runner started as root or with the needed
  capability): jobs run with `subprocess`'s `user=`, `group=` and
  `extra_groups=` parameters, available since Python 3.9.
- Feature `job_user`: `audit` logs "job would run as X, currently runs as
  Y, and config is readable by that user"; `enforce` runs as `job_user`
  and denies if the switch fails.

The owner said this is not a current priority. It is listed so the option
exists, and it is the first milestone to cut if scope needs trimming.

---

### M9 — Asymmetric signing (design spike only)

**Goal.** Fix F4. **Stop after a written design. Do not implement without
owner approval.**

Python's standard library has no Ed25519, so the stdlib-only rule forces a
choice. The design document compares:

1. **`ssh-keygen -Y sign` and `-Y verify`.** No Python dependency, widely
   installed (including recent Windows), uses an `allowed_signers` file with
   a namespace such as `homing-pigeon`. Cost: shelling out per verify, and
   a dependency on OpenSSH being present.
2. **A vendored pure-Python Ed25519 verifier** (RFC 8032) on the runner,
   with signing on the SI side. Verification handles only public data, so
   timing side channels matter far less than they would for signing. Cost:
   vendored crypto code the project must own and test against the RFC
   vectors.
3. **An optional `cryptography` dependency** with fallback to HMAC. Cost:
   breaks the no-dependency identity for those who opt in.

The deliverable is `docs/asymmetric-signing-design.md` with a
recommendation, the wire format change (a signed `alg` field, `sig`
encoding), compatibility with `key_id`, and rotation story. The likely
recommendation is option 1 behind a `signature_scheme` config key.

---

### M10 — Human approval gate (design spike only)

**Goal.** Fix F9. **Design only until the owner approves.**

Idea: a key policy field `needs_approval` (or a runner-computed flag from
the pre-execution review) holds a job in `pending_review` until a human
approves it.

Key design point: approval must not be signable by the same secret as
jobs, or a compromised SI approves its own jobs. The design should use a
**separate approval secret**, with a signed approval message
that names the job id and the SHA-384 of the script. The first transport
for approvals should be a signed email, which needs no new listener.
Telegram inline buttons (inbound) come later and need their own threat
review, because a Telegram bot token that can approve jobs is a new
credential and a new channel.

Modes: `audit` logs "would require approval" and runs the job; `enforce`
holds it. Deliverable: `docs/approval-gate-design.md`.

---

### M11 — Windows least privilege

**Goal.** Fix F6 without changing the default.

- `install.py` gains `--run-as USER` for the Scheduled Task on Windows and
  documents the permissions that user needs.
- The default stays SYSTEM. The install output and `--posture` both
  mention it.
- A `hardening/windows.md` explains running under a dedicated limited
  account, and notes the Windows constraint that `os.chmod` cannot set Unix
  permission bits, so file ACLs need to be set with `icacls`.

---

## 7. Dependencies between milestones

```text
M0 ──┬── M2 ── M3
     ├── M4
     ├── M5
     ├── M6 ── M7
     └── M8
M1 is independent and should land first or in parallel with M0.
M9, M10 are design spikes and block nothing.
M11 is independent.
```

Recommended order: M0, M1, M2, M3, M4, M5, M6, M7, M11, M8, then the
spikes. M2 and M3 together deliver the most value for the least risk.

## 8. Test strategy

**Per feature, three modes.** Every feature has a test class with at least:

- `off`: a violating job runs, no audit entry is written.
- `audit`: the same job runs, result mail identical to `off`, one audit
  entry written with the expected reason.
- `enforce`: the same job is rejected, marked seen, never retried, an
  `auth_rejection` security event is written, and a compliant job still
  runs.

**Parity test.** The harness from M0 runs the standard job corpus with (a)
no `security` block, (b) every feature `off`, (c) every feature `audit`,
and asserts (a) equals (b) equals (c) after normalization. This is the
executable form of principles 1 and 2. It runs in the normal suite.

**Hostile input.** Every new parser or regex gets a timing test with an
adversarial input, a malformed-type test (list where a string is expected,
and so on), and an oversized-input test. This follows the pattern in
`test_extension_poison.py`.

**No leakage.** A test greps audit log output for sentinel secrets and
env values placed in the test job. None may appear.

**Skips are honest.** Tests that need `bwrap`, `systemd-analyze`, or other
host tools skip with a message, and the runbook's report must list what
was skipped and why.

**Command.** `python3 -m unittest discover -s tests -t .` from the repo
root. The suite must pass without setting `PYTHONPATH` (a past wrinkle
that was fixed in v3.3.0).

## 9. Documentation to update

As each milestone lands, update the matching docs in the same commit:

- `PROTOCOL.md`: key policy section (new fields, pinned-script rule),
  signed `aud` field, modes.
- `SECURITY.md`: describe the modes and the audit log, and restate that
  the Oracle is advisory.
- `README.md`: config table, the `--audit-report` and `--posture` flags.
- `docs/threat-model.md`: link to this plan and say which findings are
  addressed by which shipped milestones.
- `runner/config.example.json`: the `security` block, every feature `off`.
- `hardening/README.md`: new, per M7.
- Docs must say "spec only" for anything not yet implemented. The docs
  audit already caught false "implemented" claims once.

## 10. Open questions for the owner

Each has a default the runbook uses unless the owner overrides it.

1. **Size caps default.** Default-on generous (1 MiB script, 4 MiB job), or
   off like everything else? *Default used: on.* Reason: it is a defect fix,
   and a cap of that size will not touch real jobs.
2. **Review scan cap.** 64 KiB scanned. *Default used: 65536.*
3. **Does M2 apply to the default key?** *Default used: only when the
   owner adds an explicit entry under `""`.* The default key is "the
   owner" in the project's own words.
4. **Audit log location.** In the base directory, mode 0600. *Default
   used.*
5. **Minimum Python.** Stay at 3.9. `subprocess`'s `user=` and `group=`
   arrive in 3.9, which is enough for M8. *Default used.*
6. **M9 mechanism.** Recommended: `ssh-keygen -Y` first. *Spike decides.*
7. **M10 approval transport.** Signed email first, Telegram later. *Spike
   decides.*
8. **Windows scope for M6.** Deferred to a design note. *Default used.*
9. **Release cadence.** One minor version per milestone group, for
   example 3.6.0 for M0 to M2. *Default used.*

## 11. Non-goals

- Replacing the HMAC protocol. M9 is additive and opt-in.
- Making the Oracle an enforcement point.
- New network listeners. The Oracle chat is loopback-only and stays so.
- New third-party dependencies, without explicit owner approval.
- Telemetry, auto-update, or any outbound call that was not already there.
- Changing or deleting the project's jokes. The VR Oracle stays.
- Removing or reintroducing `oracle_enabled` or `--no-oracle`.

## 12. Risks of this plan itself

- **Audit mode can create false confidence.** A clean audit log only
  means the traffic you sent was fine. The graduation checklist requires
  sending a deliberately bad job after the switch to enforce.
- **Policy sprawl.** More fields mean more ways to misconfigure.
  `--audit-report` and `--posture` exist to keep the operator oriented.
- **Allowlists can bake in bad habits.** If a suggested policy encodes
  whatever an attacker did during the audit window, you have allowlisted the
  attack. M3 refuses to suggest dangerous names for this reason, and a
  human must read the report.
- **Sandbox backends differ.** `bwrap` behavior varies by kernel and
  distro. M6 fails closed in enforce mode, which can be an availability
  problem. That is why it has an audit mode.
- **Complexity in the hot path.** Every control runs for every job. Keep
  checks cheap and bounded. The parity and timing tests guard this.

---

## Appendix A — Dangerous environment names

Refused under `policy_env` even when listed in `allowed_env`, unless the
policy sets `allow_dangerous_env: true`:

```text
BASH_ENV  ENV  PATH  IFS  SHELLOPTS  BASHOPTS  PS4  PROMPT_COMMAND
LD_PRELOAD  LD_LIBRARY_PATH  LD_AUDIT  DYLD_*
PYTHONPATH  PYTHONSTARTUP  PYTHONHOME  PYTHONINSPECT  PYTHONUSERBASE
NODE_OPTIONS  NODE_PATH
PERL5OPT  PERL5LIB  RUBYOPT  RUBYLIB
JAVA_TOOL_OPTIONS  _JAVA_OPTIONS  CLASSPATH
GIT_SSH_COMMAND  GIT_EXEC_PATH  GIT_CONFIG_*
COMSPEC  PATHEXT  PSModulePath  (Windows)
```

The list is a starting point, matched case-insensitively on Windows and
case-sensitively elsewhere. Keep it in one constant with a test, so
additions are a one-line change.

## Appendix B — Example hardened config

A key that may run exactly one test script, nothing else:

```json
"additional_secrets": { "test-runner": "<generated 256-bit secret>" },
"key_policies": {
  "test-runner": {
    "allowed_kinds": ["exec"],
    "allowed_interpreters": [["bash"]],
    "max_timeout_sec": 600,
    "allowed_script_sha384": ["<sha384 of the exact script>"],
    "allowed_env": ["CI", "TEST_FILTER"],
    "allowed_file_names": [],
    "max_args": 2,
    "args_pattern": "[A-Za-z0-9_./-]{1,120}"
  }
},
"key_policies_default_deny": true,
"security": {
  "modes": { "policy_env": "audit", "policy_files": "audit",
             "policy_args": "audit" }
}
```

## Appendix C — Example `--audit-report` output

```text
FEATURE      MODE   EVALUATED  WOULD-DENY  REASONS
policy_env   audit  412        3           env_not_allowed(2) env_dangerous(1)
policy_files audit  412        0           -
policy_args  audit  412        1           args_not_allowed(1)

KEY: test-runner
  suggested additions to key_policies["test-runner"]:
    "allowed_env": add "TEST_SEED"          (2 jobs, last seen 2026-10-14)
    args_pattern: review manually            (1 job, arg length 311)

REFUSED TO SUGGEST (needs a human decision):
  BASH_ENV  (1 job, key test-runner, 2026-10-13)  <- investigate this one

Nothing was written. Edit config.json yourself, then restart.
```

## Appendix D — Glossary

- **Audit mode**: evaluate and log, never block. SELinux's permissive mode.
- **Enforce mode**: evaluate, log and block.
- **Pinned script**: a job whose inline script hash is on the key's
  allowlist.
- **Would-deny**: an audit-mode finding that enforce mode would have
  turned into a rejection.
- **Posture**: the static security state of the host and config, as
  reported by `--posture`.
- **Parity test**: a test proving default behavior did not change.
