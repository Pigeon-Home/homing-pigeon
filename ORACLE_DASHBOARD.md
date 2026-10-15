# Oracle Dashboard — v4 Spec (draft)

**Status:** reviewed. Not started. v4 makes the Oracle visible.
**Identity:** v2 was who signs, v3 is what comes back, v4 is watch the Oracle think.

## 1. Vision

The Oracle currently does its work invisibly — verdicts, attestations,
budget burn, all buried in a log file. v4 gives the runner owner a
window into what the Oracle decided about each job and why. It is a
local operator console, not a cloud service: it shows what the box's
owner could already see, in a form a human can actually read.

Two jobs: show the thinking (per-job timeline of Oracle decisions)
and configure the watching (a humane frontend over the Oracle's
config surface, with full CLI/config-file parity).

## 2. Architecture

- Loopback-bound local web dashboard. Stdlib `http.server` only —
  no new dependencies, no GUI toolkit. Opens in the user's browser.
  Cross-platform for free (Linux, macOS, Windows, FreeBSD).
- Binds loopback only, fail closed. The check is `ipaddress`
  loopback (`127.0.0.0/8` and `::1`), not the string `127.0.0.1`.
  Refuse `0.0.0.0`, `::`, and any LAN address. If the bind is not
  loopback, the process does not start. This mirrors §10.1's rule
  for the inference endpoint.
- Two mutations, both named. Everything else is read-only. The
  dashboard never sends email and never signs anything.
  1. Approving a `pending_review` task. Not a button: the owner
     types the task id. Log the local user and the time.
  2. Writing Oracle config keys. `config.json` is the source of
     truth. The dashboard must not write or display
     `shared_secret`, `additional_secrets`, or the mailbox password.
- Data sources (all local): `board.json` (task board state),
  `retained/` (job outputs, query budgets), `runner.log`
  (judgments, budget tripwires), `config.json` (live configuration).

## 3. Views

### 3.1 Job timeline (the core view)

A reverse-chronological list of jobs. Each entry shows, at a glance:

- job_id, kind, when it ran, result class (success/failure/timeout)
- judgment verdict and reasons (if judged)
- view applied (full/redacted/summary/attested) and why
  (job request vs. owner ceiling)
- attestations returned (exit_zero, no_secrets, output_digest,
  confined_to_workspace)
- queries answered and budget spent vs. remaining
- confinement result

A job that burned its entire privacy budget is visually loud —
budget exhaustion is a tripwire (§11), and the timeline is where
the human sees it. Jobs with `ask` answers (v3.0) show the plain-
language answer inline on the card.

### 3.2 Job detail

Everything the timeline shows, plus the retained output, the full
query/answer exchange, and the redaction families applied. The owner
already has `retained/` on disk. The dashboard shows the owner
everything, and labels what the SI was allowed to see. It does not
hide the owner's files from the owner.

### 3.3 Configuration

Every Oracle config key, editable, with plain-language explanations:

- `max_result_view`, `max_query_budget`, `max_queries_per_hour`,
  `output_retention_days`
- `judge` (off/advisory/enforce), `workspace_root`, protected paths
- `redact_patterns_extra` — "what counts as a secret on this box,"
  with the built-in families listed and testable (paste sample text,
  see what gets redacted)
- `worker_allowlist`, `worker_compartments`, `dag_mode`,
  `task_timeout`, `require_review`
- inference endpoint/model (v3.0)

**Parity rule:** everything the dashboard configures must be
expressible in `config.json`, and everything in `config.json` must
be configurable from the dashboard. No dashboard-only settings,
ever. The config file remains the source of truth; the dashboard
is a frontend over it.

### 3.4 Budget dashboard

Per-job and aggregate privacy-budget burn: how many queries each
job spent, which jobs hit exhaustion, rate-limit events. The
operational answer to "is something probing my box?"

### 3.5 Task board

Read view of the dispatch board (§13): open/claimed/done tasks,
who holds what, expired leases. Approving `pending_review` results
lives here, behind the confirmed-gesture rule.

## 4. Deployment profiles

A profile is a named, shareable config bundle capturing "what
matters on this box":

```json
{
  "profile": "raspberry-pi-home",
  "description": "Pi running VS Code server; watch repo creds and root hash",
  "redact_patterns_extra": {
    "vscode_token": "...",
    "shadow_hash": "..."
  },
  "protected_paths": ["~/docs/manuals"],
  "max_result_view": "attested",
  "judge": "advisory"
}
```

Profiles make the Oracle's per-deployment knowledge explicit:
a user declares what is valuable on their machine, and the Oracle
watches exactly that. The dashboard offers profile creation from a
questionnaire ("what kind of box is this? what credentials live
here? what files matter?"); the result is an ordinary config file,
editable by hand. Profiles are local. A profile that lists what
credentials live on a box is a fingerprint of that box, and is not
published.

## 5. Security considerations

- Loopback-only bind, fail closed (no dashboard rather than a
  network-exposed one). Check is `ipaddress` loopback, not a string.
- Two mutations: task approval (type the task id, logged) and
  Oracle config writes. Nothing else writes.
- The dashboard shows the owner everything in `retained/`. It
  labels what the SI was allowed to see under the job's view. It
  does not hide the owner's files from the owner, and there is no
  elevate gesture.
- No credentials in the dashboard: it reads `config.json` but
  never displays or writes `shared_secret`, `additional_secrets`,
  or the mailbox password.
- Loopback is per-host, not per-user. On a shared Linux box another
  local account can reach `127.0.0.1`. The threat model is a
  single-user box. No account system.

## 6. Scope

**In v4:** dashboard server, the five views above, profiles,
"Configuring the Oracle" documentation (GUI-or-CLI parity,
per-deployment profiles, worked Pi example), and confidentiality
for transport messages.

**Out of v4:** new transports, any native GUI toolkit, multi-user
or remote access (the dashboard is single-owner, loopback-only, by
design). The `ask` op is v3.0 and is already implemented; the
timeline shows its answers.

### 6.1 Confidentiality for transport messages

TLS protects the pipe. It does not protect the message from the
transport operator. A mailbox provider, or a queue operator, can
read the signed JSON today. v4 encrypts the message body so the
pipe carries ciphertext.

- Cipher: AES-256-GCM, as named in PROTOCOL section 8.
- Key: derived from the shared secret already used for HMAC. No
  second secret. `key_id` selects which secret, the same way it
  selects the HMAC key.
- What is encrypted: the signed JSON body. The subject stays
  plaintext so the runner can still find `[HOMING-PIGEON]`
  messages by poll. The signature is inside the ciphertext.
- What is not: TLS stays. This is confidentiality of the message
  at rest on the transport, not a replacement for TLS.
- Fail closed: a message that claims to be encrypted and does not
  decrypt is rejected. A deployment that has not turned this on
  still accepts plaintext, so v3 keep working.

## 7. Decisions

1. No authentication beyond loopback. No login form. The threat
   model is a single-user box. Loopback is per-host, not per-user;
   that is documented, not papered over with accounts.
2. Timeline retention follows `output_retention_days`. The timeline
   is a view of `retained/`, not a second store.
3. Profiles are local. They are not shareable or publishable.
