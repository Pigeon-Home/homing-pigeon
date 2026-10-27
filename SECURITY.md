# Security Policy

Homing Pigeon is, by design, a remote code execution tool: anyone
holding the shared secret gets full control of the machine the runner
runs on. That makes its security posture load-bearing, not decorative.
This document explains how to report problems and what to expect.

## Reporting a vulnerability

**Do not open a public issue for security problems.** Public issues
get scraped, and a disclosed-but-unfixed hole in a tool like this
puts every deployment at risk.

Instead, use GitHub's **private vulnerability reporting**:

1. Go to the repo's **Security** tab.
2. Click **Report a vulnerability**.
3. Describe the issue: what you found, how to reproduce it, and what
   you think the impact is.

If private reporting isn't available to you, open a minimal public
issue that says you've found a security problem and ask for a contact —
no details.

### What happens next

- You'll get an acknowledgment as soon as the report is seen.
- The issue will be assessed for impact and reproducibility.
- A fix will be developed privately, then released with a clear
  description of what was wrong and which versions are affected.
- You'll be credited in the release notes unless you'd rather stay
  anonymous.

## Scope

In scope: the runner (`runner/runner.py`), the installer
(`runner/ops/install.py`), the cloud helper (`runner/cloud/send_job.py`), the
protocol itself (PROTOCOL.md), and the build/release pipeline
(`.github/workflows/`).

Out of scope: the security of the mailbox provider itself, the secrecy of a
shared secret the user chose to share, and deployments that ignore
the documented threat model (e.g., running the agent on a machine
with irreplaceable data and no VM snapshot).

## A note on the threat model

This project is explicit that the runner is a **full-trust execution
environment**. Reports along the lines of "anyone with the secret can
run arbitrary code" describe the intended design, not a vulnerability.
A vulnerability is something that breaks the documented guarantees:
signature forgery, a job executing without a valid
signature, sandbox/workdir escape, or secret leakage through logs,
emails, or error messages. Sender spoofing is not in scope: the sender
address is not validated, so there is nothing to spoof — the signature
is the only thing the runner trusts.

**What the signature proves, and what it does not.** The HMAC signature
answers two questions: was this job sent by someone holding the shared
secret, and has it been tampered with in transit? It does not answer a
third question: is this job safe to execute? A compromised SI, a
prompt-injected SI, or a careless human with the secret can sign a
perfectly valid, perfectly destructive job, and the runner will run it.
Authentication is not authorization to be safe. That is why the
deployment model matters more than the cryptography: throwaway account,
disposable machine, secret kept like a password. The crypto keeps
strangers out. Only your own judgment keeps bad jobs out.

## Dual-use: yes, this looks like email-C2

Saying it plainly: a program that polls an inbox and executes signed
messages is the same *shape* as email-based command-and-control malware.
The difference is not the mechanism — it is consent, control, and
auditability:

- **Consent:** you install it on your own machine, on purpose, to run
  your own jobs. It does nothing you did not ask it to do.
- **Control:** the shared secret is yours, the mailbox is yours, and
  revoking the mailbox credential stops mail delivery — without
  mailbox access the runner can't receive jobs by email. It is not
  the only channel, though: a same-box producer can still deliver
  signed `sensor_alert` envelopes through the local inbox or the
  loopback signal socket, so a leaked signing secret does have a
  delivery channel on the box itself — which is why rotating the
  secret matters more than the mailbox. To rotate a compromised
  secret, generate a new one and update `shared_secret` in config.json
  on the runner (and hand the new string to your SI).
- **Auditability:** the runner is inspectable by design. `--dry-run`
  verifies signatures and prints exactly what a job *would* do without
  executing anything; `--verbose` logs every accept/reject decision;
  `--pdb` drops into the Python debugger on errors. Malware hides.
  This tool is built to be watched.

It belongs to the same family as GitHub self-hosted runners, VS Code
Remote tunnels, and Tailscale: legitimate remote-administration tools
whose power is the point. If your antivirus flags the prebuilt
binaries, that is a known PyInstaller false-positive pattern — verify
the `SHA384SUMS` file attached to the release, or build from source
(`pip install` the wheel, or run `runner/runner.py` directly).

---

## Optional security controls

Homing Pigeon ships with optional, off-by-default security controls.
With no `security` block in `config.json`, the runner behaves exactly
as it always has. Every control has three modes:

- `off` — the control does nothing. This is the default.
- `audit` — the job proceeds exactly as with `off`, but a line is
  written to `security-audit.jsonl` describing what `enforce` mode
  would have decided.
- `enforce` — for the `policy_*` features and `audience`,
  violations are rejected through the existing reject path. For
  `confinement` and `job_user`, enforce changes how the job runs, as
  described under each below.

```json
"security": {
  "modes": {
    "policy_env": "off",
    "policy_files": "off",
    "policy_args": "off",
    "audience": "off",
    "confinement": "off",
    "job_user": "off"
  },
  "audit_max_lines": 20000
}
```

**Changing a mode requires a restart.** Poll interval, workers,
timeouts, output limits, max job age, the result stash's retention
and resend backoff, and the live keys (`owner_instructions`,
`inference`, `oracle_mode`, `verbose`, `extension_sources`) reload
when `config.json` changes. The `security` block does not.

**A malformed security block stops startup** with an error naming the
key (and, for a mode value and `audit_max_lines`, the bad value). It never silently falls back to `off`.

The audit log lives at `security-audit.jsonl` in the runner base
directory, created `0600` on POSIX, bounded by `audit_max_lines`
(default 20000) with rollover to one `.1` file. A small counter file,
`security-audit-counts.json`, tracks decisions per feature. Audit
entries carry identifiers only — never secret values, script text,
or file contents.

### What a wide-open box looks like

The campaign rig ran as root with confinement and every security
mode off, at `max_result_view: full`
([live-examples.md](docs/use/live-examples.md)). Three things from
its 19,227 jobs are worth knowing before loosening a real box:

- At view `full` the SI receives what the script printed. The run's
  `flagread` job printed a planted fake credential file;
  `runner.log` redacted the key, the result carried it verbatim.
  The installer's profiles set the ceiling to `attested` for that
  reason; the bare config default is `full`.
- A job running as root read `/etc/shadow` and returned it. Only
  confinement and `job_user` stop that; a signature does not.
- `--posture` warns when `audience` or a `policy_*` mode is off and
  when bwrap is missing. It does not flag running as root,
  confinement or `job_user` off, or `max_result_view: full`; those
  are on the operator to read in the config. `--audit-report` shows
  no entry from the six security features while they are off, since
  no decision was made to record; remediation (on by default in
  deterministic mode) still writes its own entries there.

### Features

| Feature | Milestone | What it does |
|---|---|---|
| `policy_env` | M2 | Constrains env vars for keys with a policy entry |
| `policy_files` | M2 | Constrains staged files for keys with a policy entry |
| `policy_args` | M2 | Constrains job args for keys with a policy entry |
| `audience` | M5 | Binds signed jobs to this runner's id |
| `confinement` | M6 | Runs jobs inside a Linux sandbox (bwrap) |
| `job_user` | M8 | Runs jobs as a different POSIX user |

### Confinement (M6)

With `security.modes.confinement: enforce` on Linux and `bwrap`
installed, each `exec` job runs inside a bubblewrap sandbox: `/usr`
read-only, no network, no access to home, and the job workdir
writable (mounted at `/work`), plus a writable tmpfs at `/tmp`,
`/proc` and `/dev`. When the job's interpreter lives outside `/usr`
(pyenv, a venv, `/opt`), its install folder is bound read-only too,
and that is logged and recorded in the audit entry. `PATH` inside is
`/usr/bin:/bin`.
The job's scrubbed env arrives via
`--setenv`. At startup under `enforce` the runner starts bwrap once
with the built-in namespace flags (not `extra_flags` or extra binds); when it cannot (bwrap missing, a non-Linux
machine, or a kernel that blocks the user namespace, such as
`kernel.apparmor_restrict_unprivileged_userns=1` on Ubuntu 24.04)
the runner refuses to start and names the cause — a security mode
whose mechanism cannot engage is a config error, not a silent
downgrade (`docs/design/present-but-invalid-config.md`). If bwrap
leaves `PATH` after a successful start, or the sandbox command
cannot be built, a job falls back loudly: the runner warns, audits a
`fallback` decision, and runs it normally. If bwrap is still present
but fails to start, the job fails. Each sandboxed job is audited as
`sandboxed`. `audit` mode runs normally and records a `would_sandbox`
decision (reason `would_run_sandboxed`), with or without bwrap.

Optional tuning under `security.confinement` (all optional):

```json
"confinement": {
  "extra_flags": ["--unshare-pid"],
  "extra_ro_binds": [["/opt/data", "/data"]],
  "work_mount": "/work"
}
```

### Running jobs as another user (M8)

With `security.modes.job_user: enforce` and
`security.job_user: {"user": "pigeon-jobs"}`, each `exec` job runs as
that POSIX user (via setuid after fork). The job's workdir is chown'd
to the user, and the parent chain up to the base dir gets traverse-only
(`+x`) permission so the job can reach its workdir without listing the
runner's state. Requires the runner itself to run as root; otherwise
it warns loudly, audits a `fallback` decision, and runs the job as the
current user. Each job run that way is audited as `run_as`. `audit` mode runs
normally and records a `would_run_as` decision (reason
`would_run_as_user`).
The user must exist, or startup fails.

### Secret files (M8)

Secrets don't have to live in `config.json`. `shared_secret_file`
and `additional_secrets_files` (`{"key_id": "/path/to/file"}`) read
each secret from a file at startup (whitespace-stripped). A secret
given both inline and via file is a startup error, as is a missing or
empty file. File secrets pass the same entropy gate.

### Multiple secrets (M-key)

`additional_secrets` maps key IDs to further shared secrets
(PROTOCOL.md section 14). Threat notes:

- **A key ID is a label, not a secret.** It travels in the clear
  inside the signed body and may appear in logs. Possession of the
  secret it names is the credential; guessing the label buys nothing.
- **Every secret is root unless its policy says otherwise.** Keys
  without a `key_policies` entry are unrestricted by default. Give
  every delegated key an entry (`allowed_kinds`, `max_timeout_sec`,
  `allowed_script_sha384`, ...), or set `key_policies_default_deny`
  so a new key with no entry is refused.
- **Unknown key IDs are rejected before any MAC is computed**, and
  the runner never falls back to the default secret for them. An
  attacker cannot make a message verify under a key it did not name.
- **Rotation is per key**: add the new ID, hand it out, retire the
  old one (`docs/use/secret-rotation.md`). An inline secret is read at
  startup and rotating it takes a restart; a secret given by file is
  read again on every poll cycle.
- **The dispatcher's trust model** (section 13): a result from a
  worker is bound to that worker's key by the signature, and the
  attestation binds the worker to its claimed output. Neither says
  the output is correct; review (`require_review`, the human gate)
  is the correctness anchor.

### Key names are public (Q94)

Every secret has a name, its fingerprint `k-<8 hex>` (PROTOCOL.md
section 14.2), and the names travel in the open: a result names the
key that verified its job, the pong's platform card lists the names a
runner accepts (unless `pong_platform` is `none`), the installer prints the name beside the secret, and
the reference sender writes the name into every message unless
`--key-id ""` is given. The
questions a reviewer asks about that, and the answers:

- **Is the name a secret?** No. It is a label, like a user name; the
  secret is the credential. A name tells an attacker which key to
  try -- which the empty key id of the default key told them before
  there were names.
- **Does the fingerprint leak the secret?** No. It is eight hex
  digits (32 bits) of SHA-384 over a fixed label and a 256-bit random
  secret: one-way, and too short to constrain the secret (224 bits
  stay free). As an oracle for a guessed secret it adds nothing a
  signed message does not give already, since every HMAC is a full
  oracle for a guess, and the secret's entropy is what defeats both.
- **Can the name be confused with a signature or a key?** No. The
  label (`homing-pigeon key id v1\n`) separates this hash from the
  HMAC over a body and from the HKDF that derives a job key; nothing
  the secret keys starts from the same input.
- **Can a name change what a key may do?** No. The runner reads a
  key by its value: the default key's empty key id, its fingerprint
  and any name `install --key-id` stored the same secret under are
  one key to every rule -- its policy entry, `key_policies_default_
  deny`, the hourly query window, `v2_answerers`, a sense's `key_id`
  binding. Naming the owner's key by fingerprint grants nothing and
  escapes nothing, and a `key_policies` entry under two names of one
  key is refused at startup.
- **What does a runner publish about its keys?** Names, never values:
  `key_ids` in the pong card, `key_id` in a result, the key ids in
  the doctor's line. The card with `key_ids` leaves only in a ping's
  result, which answers a verified job, so an unauthenticated sender
  sees none of it. The DTLS binding's greeting carries a card without
  key names, and only after the PSK handshake has authenticated the
  peer.
- **Where does the sender keep the pair?** `send_job.py keyring`
  (`~/.homing-pigeon/keyring.json`, mode 0600 in a 0700 directory,
  or `HP_KEYRING`), written whole or not at all; `list` prints names
  and runners, never a secret.

See the hardening report (`docs/archive/HARDENING_REPORT.md`) for per-milestone
status, and the threat model (`docs/security/threat-model.md`) for the
overall posture: the Oracle reviews while the operating system
contains.
