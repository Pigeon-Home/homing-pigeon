# Findings — docs/steady/design/approval-gate-design.md

Source: docs/steady/design/approval-gate-design.md, reviewed at main cbb52068.
Sentence units: 52. Flagged: 0. Categories: pre-release 7, post-release 45.

The document is a design for a feature marked not built; its feature-description units are categorized post-release, its present-state framing pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "*Not built." | pre-release | flows |  |
| 2 | "See docs/future.md." | pre-release | flows |  |
| 3 | "This document records the shape of a human…" | pre-release | flows |  |
| 4 | "The starting point this design argues from: a…" | pre-release | flows |  |
| 5 | "That is no longer the whole truth: the…" | pre-release | flows |  |
| 6 | "The signature says *who* sent it, not whether…" | pre-release | flows |  |
| 7 | "The advisory reviewer (`runner/oracle/review.py`) notes concerns but never…" | pre-release | flows |  |
| 8 | "An approval gate adds the missing piece: for…" | post-release | flows |  |
| 9 | "A new `approval` section in `key_policies` (per key,…" | post-release | flows |  |
| 10 | "Modes (what gets gated):" | post-release | flows |  |
| 11 | "`off` (default) — no gate, current behavior." | post-release | flows |  |
| 12 | "`all` — every job from this key waits…" | post-release | flows |  |
| 13 | "`review-flagged` — only jobs the advisory reviewer flags…" | post-release | flows |  |
| 14 | "`destructive` — jobs whose review verdict is `hostile`…" | post-release | flows |  |
| 15 | "(Requires the reviewer to produce a machine-readable risk…" | post-release | flows |  |
| 16 | "The `mode` above selects *what* gets gated." | post-release | flows |  |
| 17 | "*Whether* the gate holds jobs is governed by…" | post-release | flows |  |
| 18 | "`off` (default) — the approval block is parsed…" | post-release | flows |  |
| 19 | "Gated jobs run immediately, no log entries." | post-release | flows |  |
| 20 | "`audit` — the runner evaluates each job against…" | post-release | flows |  |
| 21 | "This is the dry-run: the owner watches `--audit-report`…" | post-release | flows |  |
| 22 | "`enforce` — jobs matching the gate's scope are…" | post-release | flows |  |
| 23 | "This keeps the approval gate consistent with confinement,…" | post-release | flows |  |
| 24 | "The `--posture` check for "features in off mode…" | post-release | flows |  |
| 25 | "The pending-queue entries themselves are audit-logged (held, approved,…" | post-release | flows |  |
| 26 | "Gated jobs land in a pending queue (`pending.json`…" | post-release | flows |  |
| 27 | "The runner keeps polling but does not execute…" | post-release | flows |  |
| 28 | "Expiry (default 1h, configurable) rejects the job like…" | post-release | flows |  |
| 29 | "Approval must come over a channel the job…" | post-release | flows |  |
| 30 | "**Local CLI** (`--approve `) — simplest, strongest." | post-release | flows |  |
| 31 | "The owner SSHes in and approves." | post-release | flows |  |
| 32 | "No new trust boundary." | post-release | flows |  |
| 33 | "**Signed email reply** — the owner replies from…" | post-release | flows |  |
| 34 | "Weaker: email sender addresses are forgeable, so the…" | post-release | flows |  |
| 35 | "**DRI channel** (Telegram/Signal/WhatsApp) — the DRI playbook already…" | post-release | flows |  |
| 36 | "Same forgery concern as email: the tap must…" | post-release | flows |  |
| 37 | "The design recommends (1) first, (2)/(3) only with…" | post-release | flows |  |
| 38 | "An approval over an unauthenticated channel is theater." | post-release | flows |  |
| 39 | "Every approval/rejection/expiry is an audit-log entry with the…" | post-release | flows |  |
| 40 | "Approving the same `job_id` twice is a no-op…" | post-release | flows |  |
| 41 | "A replayed approval for a different job body…" | post-release | flows |  |
| 42 | "A gated job stays unseen until approved or…" | post-release | flows |  |
| 43 | "The pending queue is fsync'd on write." | post-release | flows |  |
| 44 | "**Who approves when the owner is away?** Expiry…" | post-release | flows |  |
| 45 | "Defer." | post-release | flows |  |
| 46 | "**Does the gate apply to queries?** Probably not…" | post-release | flows |  |
| 47 | "Keep the gate to `exec` (and `task_submit` payloads…" | post-release | flows |  |
| 48 | "**UX for the pending queue.** `--pending` to list,…" | post-release | flows |  |
| 49 | "Follows the `--inspect` pattern." | post-release | flows |  |
| 50 | "The gate's security rests entirely on the approval…" | post-release | flows |  |
| 51 | "That is genuinely useful (and small), but the…" | post-release | flows |  |
| 52 | "Sequence: M9, then the CLI gate, then the…" | post-release | flows |  |
