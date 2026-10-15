# Oracle Dashboard — v4 Spec (draft)

**Status:** draft for review. v4 makes the Oracle visible.
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
- Binds 127.0.0.1 only, fail closed. If the bind address is not
  loopback, the dashboard does not start. This mirrors §10.1's rule
  for the inference endpoint: the Oracle distrusts the network, and
  its dashboard does too.
- Read-only by default. The dashboard renders state; it does not
  act. The single exception is approving a `pending_review` task,
  which requires a deliberate, confirmed gesture — never a casual
  click. The dashboard never sends email and never signs anything;
  it only reads.
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
the human sees it. Jobs with `ask` answers (v3.1) show the plain-
language answer inline on the card.

### 3.2 Job detail

Everything the timeline shows, plus the retained output (subject to
the same view rules — the dashboard does not widen disclosure; an
`attested` job shows attestations, not output), the full query/answer
exchange, and the redaction families applied.

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
- inference endpoint/model (v3.1)

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

Profiles make the Oracle's per-deployment knowledge explicit and
portable: a user declares what is valuable on their machine, and
the Oracle watches exactly that. The dashboard offers profile
creation from a questionnaire ("what kind of box is this? what
credentials live here? what files matter?"); the result is an
ordinary config file, editable by hand.

## 5. Security considerations

- Loopback-only bind, fail closed (no dashboard rather than a
  network-exposed one).
- Read-only default; the one mutating action (task approval) is
  confirmed and logged.
- The dashboard displays retained output under the same view rules
  as email results — it never widens disclosure. What the job's
  view hides from the SI, it hides from the dashboard too, unless
  the owner explicitly elevates (which is itself logged).
- No credentials in the dashboard: it reads `config.json` but
  never displays `shared_secret`, `additional_secrets`, or the
  mailbox password.

## 6. Scope

**In v4:** dashboard server, the five views above, profiles,
"Configuring the Oracle" documentation (GUI-or-CLI parity,
per-deployment profiles, worked Pi example).

**Out of v4:** the `ask` op (v3.1 — the Oracle should be smart
before it's visible), new transports, any native GUI toolkit,
multi-user or remote access (the dashboard is single-owner,
loopback-only, by design).

## 7. Open questions for the owner

1. Should the dashboard require any authentication beyond loopback
   binding? (Default: no — the local user already owns the box.
   Loopback + read-only is the threat model.)
2. Job timeline retention: follow `output_retention_days`, or its
   own setting?
3. Should profiles be shareable/publishable, or strictly local?
