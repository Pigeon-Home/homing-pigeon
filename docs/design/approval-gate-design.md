# Approval gate — design

*Not built. See docs/project/future.md. This document records the shape of a
human approval step before job execution, so the work can be picked
up without re-deriving the tradeoffs.*

## The problem it solves

The starting point this design argues from: a valid signature as
the sole gate — any signed job executes (PROTOCOL.md section 5).
That is no longer the whole truth: the judge in enforce mode, key
policy, and the security-policy modes also refuse signed jobs; the
M2 constraints noted below are part of that. The signature says *who* sent it, not
whether the owner would approve *this* job. The advisory reviewer
(`runner/oracle/review.py`) notes concerns but never blocks, and the M2
policy constraints bound *how* a key may act but not *whether* a
particular job should run. An approval gate adds the missing piece:
for jobs the policy flags, a human says yes before execution.

## Proposed design

### What gets gated

A new `approval` section in `key_policies` (per key, opt-in, like the
M2 constraints):

```json
"key_policies": {
  "cloud-si": {
    "allowed_kinds": ["exec"],
    "approval": {
      "mode": "review-flagged",
      "timeout_sec": 3600
    }
  }
}
```

Modes (what gets gated):

- `off` (default) — no gate, current behavior.
- `all` — every job from this key waits for approval.
- `review-flagged` — only jobs the advisory reviewer flags wait.
- `destructive` — jobs whose review verdict is `hostile` or whose
  script matches destructive patterns wait. (Requires the reviewer to
  produce a machine-readable risk signal; today it produces notes.)

### Audit/enforce integration

The `mode` above selects *what* gets gated. *Whether* the gate holds
jobs is governed by the M0 three-mode system like every other
hardening feature, via `security.modes.approval`:

- `off` (default) — the approval block is parsed but changes nothing.
  Gated jobs run immediately, no log entries.
- `audit` — the runner evaluates each job against the gate, logs
  `would_deny` / `would_require_approval` to the security audit log,
  and runs the job anyway. This is the dry-run: the owner watches
  `--audit-report` for a week to see what *would* have waited before
  turning the gate on.
- `enforce` — jobs matching the gate's scope are held in the pending
  queue instead of executing.

This keeps the approval gate consistent with confinement, audience
binding, and the M2 constraints: one mode vocabulary, one audit log,
one `--audit-report` view. The `--posture` check for "features in
off mode that are recommended" does not nag about `approval`,
because a human-in-the-loop gate is a workflow decision, not a
missing default.

The pending-queue entries themselves are audit-logged (held,
approved, rejected, expired), so the full lifecycle is visible in
`--audit-report` under the `approval` feature.

### The pending queue

Gated jobs land in a pending queue (`pending.json` in the base dir,
0600): job body, key_id, received time, review notes, expiry. The
runner keeps polling but does not execute them. Expiry (default 1h,
configurable) rejects the job like any other bad job: logged, marked
seen, never retried.

### Approving

Approval must come over a channel the job sender cannot forge:

1. **Local CLI** (`--approve <job_id>`) — simplest, strongest. The
   owner SSHes in and approves. No new trust boundary.
2. **Signed email reply** — the owner replies from an approved
   address with a signed `approve` message. Weaker: email sender
   addresses are forgeable, so the approval itself must be signed
   with a key only the owner holds (the M9 asymmetric keypair fits
   here — the owner signs approvals with their private key).
3. **DRI channel** (Telegram/Signal/WhatsApp) — the DRI playbook
   already pages the owner; "tap to approve" was in the roadmap spec.
   Same forgery concern as email: the tap must authenticate the
   owner, not just the device.

The design recommends (1) first, (2)/(3) only with owner-held signing
keys. An approval over an unauthenticated channel is theater.

### Audit and replay

- Every approval/rejection/expiry is an audit-log entry with the
  approver identity and the job hash.
- Approving the same `job_id` twice is a no-op (idempotent).
- A replayed approval for a different job body does not match the
  queued hash and is ignored.

### Interaction with at-least-once delivery

A gated job stays unseen until approved or expired, so a runner
restart does not lose it and does not double-execute it. The pending
queue is fsync'd on write.

## Open questions

- **Who approves when the owner is away?** Expiry handles it (the job
  dies), but a "delegate approver" key would need its own policy —
  probably a second key_id with `approval.delegate: true`. Defer.
- **Does the gate apply to queries?** Probably not — queries don't
  execute code. Keep the gate to `exec` (and `task_submit` payloads
  that contain exec).
- **UX for the pending queue.** `--pending` to list, `--approve` /
  `--reject` to decide. Follows the `--inspect` pattern.

## Why not now

The gate's security rests entirely on the approval channel, and the
only channel that needs no new trust boundary is the local CLI —
which is just SSH plus a command. That is genuinely useful (and
small), but the fancier channels (email tap, Telegram tap) need the
M9 owner keypair first. Sequence: M9, then the CLI gate, then the
remote channels.
