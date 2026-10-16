# Approval gate — design (M10)

*Design only. Not implemented. This document records the shape of a
human approval step before job execution, so the work can be picked
up without re-deriving the tradeoffs.*

## The problem it solves

Today a valid signature is the sole gate: any signed job executes
(PROTOCOL.md section 5). The signature says *who* sent it, not
whether the owner would approve *this* job. The advisory reviewer
(`runner/review.py`) notes concerns but never blocks, and the M2
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

Modes:

- `off` (default) — no gate, current behavior.
- `all` — every job from this key waits for approval.
- `review-flagged` — only jobs the advisory reviewer flags wait.
- `destructive` — jobs whose review verdict is `hostile` or whose
  script matches destructive patterns wait. (Requires the reviewer to
  produce a machine-readable risk signal; today it produces notes.)

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
