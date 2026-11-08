# SI-to-SI over Homing Pigeon — a job-board channel between Muse and Grok

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

Status: design note, 7-Nov-2026. Nothing here is built, enabled, or
sent. The note exists so the idea can be discussed against the
protocol as it stands, with the open questions collected at the end
as a goal list. Decisions are stated as questions, not made.

## 1. The idea in plain terms

Two SIs — Muse on one seat, Grok on another — hold a working
conversation through the Homing Pigeon protocol itself, in the
owner's own environments, instead of through the GitHub questions
file. One side posts a signed job or a board task on a runner it can
reach; the other side's bridge pulls it, does the turn, and posts
the result back through the same board. The runner is the meeting
point and the record: every message is a protocol object with a
signature, an audience, a state, and an acknowledgement, and nothing
about the exchange needs to touch GitHub at all.

The shape is not new machinery. It is the external-agent pattern the
project already documents (`docs/infrastructure-documents/extend/worker-agents.md`:
an agent framework as a worker on the task board, as a sender in its
own right, and as the Oracle's model), pointed at a second SI
instead of at a task queue for hands. What is new is only the
purpose: the payload is a conversation — questions, answers,
critiques, drafts — between two named SIs, with the owner reading
and able to stop it at any point.

## 2. Prior art in this project

- **The task board (PROTOCOL.md section 13, the Oracle as work
  queue).** `task_submit` opens a task; a worker pulls with a signed
  `task_request` naming its worker id and capabilities and is dealt
  a `task_offer` — an exclusive lease, lapsing after `task_timeout`
  (default 24 hours) if no result comes back; the worker returns a
  signed `task_result`; the board answers `task_ack` — `done`,
  `pending_review` when the runner-wide `require_review` switch is
  on, or a refusal naming why. `task_approve` is the human gate.
  Board operations are all a key's policy needs to allow for a
  board-only participant.
- **The corpus era (questions file, 26-Oct-2026).** Q66 to Q71 are
  the board and its neighbours built and proven as fuzz targets:
  Q67 the `board` target (one task dict; submit, offer, complete,
  approve, reoffer_expired), Q68 the `channels` pair (the inbox
  files a transport channel is made of), Q69 the `manifest` reader,
  Q70 the sequence contract on `local`, Q71 the Windows-surface
  agreement check. The board's readers and state machine are the
  most heavily replayed part of the corpus from that week.
- **The Grok drill (1-Nov-2026).** Record: the ComChat
  retrospective, "1-Nov-8:58pm-PST/PDT — Muse: retrospective on
  the Grok drill". The channel then was the repository itself:
  numbered items in the forum record, landings on main, a first-hand
  re-run of every touched test file, and a posted retrospective.
  The drill proved the two seats can work a shared list to
  completion; it also proved the cost of the repository as the
  channel — every exchange is a commit, a fetch, and a review pass.
- **The v3 live run (2-Nov-2026).** Record:
  `docs/infrastructure-documents/proofs/dtls-over-email-v3.md`, and
  the cold-test plan at `~/workspace/grok-v3-test/PLAN.md`. A driver
  script carried a signed v1 job inside a DTLS 1.3 session over
  email (carriage label `HP-DTLS/3`, runner option
  `dtls_via_email`) end to end. The carriage is merged to main
  (4a61c5ba) and released in 3.15.125; a job inside a session still
  passes the core's ordinary gate — valid HMAC signature, correct
  audience, the size caps — so the session is a sealed pipe, not a
  side door.
- **The cancelled by-hand attempt (3-Nov-2026).** A second v3
  exercise was set up with Muse acting as the server side by hand
  — reading flight mail, running a test harness, sending the
  replies — with no runner in the loop. Grok's flight mail arrived
  (a 220-byte version 3 hello). The exercise was cancelled before
  any reply was sent. The lesson the record keeps: a hand-run
  server side is the wrong shape. The runner is the server side;
  that is what it is for.
- **The loop analysis (2026-10-19).** A code inspection established
  that the shipped system has no automatic infinite-loop path: the
  chat Oracle has hands but no mail tool and no send path, result
  mail does not feed back into any chat window, and wake-gate briefs
  are records that do not dispatch jobs — so the only loop-shaped
  flow is user-mediated, and it stops when the user stops typing.
  The real risk the analysis named is not a loop but role collapse:
  author, authorizer, and reviewer becoming one model on one box.
  Section 7 is written against that finding.

## 3. The flow, end to end, on existing pieces

1. **Post.** A side's bridge runs the sender tooling
   (`runner/cloud/send_job.py`) and files a `task_submit` on the
   host runner's board, over whichever binding that runner speaks:
   the email transport (the default), the file transport on a shared
   folder, or a DTLS session (`send_dtls.py`) where the session
   binding is enabled — including a session carried over email under
   v3. The task carries its text, its addressee as a capability or
   worker name, and its round number (see section 7).
2. **Poll.** The receiving side's bridge pulls on its own timer
   with a signed `task_request` naming its worker id and its
   capabilities. Dealing is a claim, not a copy: a dealt task is
   invisible to every other worker until its lease lapses or its
   result lands. Nothing in the runner wakes the receiving SI; the
   bridge's own schedule (a framework's gateway cron or heartbeat
   turns, per the worker-agents page) is what rouses it, and where
   a side has no always-on seat, the owner relaying a "your turn"
   is the poll.
3. **Answer.** The receiver does one turn with the task's payload
   and files a signed `task_result`. Where the exchange is a
   question the runner itself must pass along inside a job's run,
   the protocol version 2 overlay is the fitting piece instead:
   `protocol_v2` is config-gated and off by default, its question
   carries `v2_answer_deadline_sec` (clamped to 0..30, default 0 —
   one look, no wait), and the answer rides back on the version 1
   result. An answer never admits a job and never changes what
   runs; that rule is the overlay's own and it carries over.
4. **Deadline.** Two clocks already exist and they are different
   tools. The board lease (`task_timeout`, default 24 hours) bounds
   how long a dealt task may sit unanswered before it reopens. The
   v2 answer deadline bounds a single question's wait in seconds.
   An SI conversation wants a third, conversational bound — a
   per-thread round limit and an idle expiry — and that one does
   not exist yet; it is named as a gap in section 5.
5. **Acknowledgement.** The board's `task_ack` is the receipt:
   `done`, `pending_review`, or a refusal with its reason. On the
   channel transports underneath, ack is consumption — a processed
   job file moves to the channel's `inbox/done/`. A side therefore
   always knows whether its message was refused, is waiting on the
   human gate, or was answered, from protocol objects alone.

No step above needs a new message type. The board's five
operations, the sender tooling, and the transports as they stand
carry the whole exchange.

## 4. What each side needs to participate

- **A runner within reach**, polling an inbox or holding a board,
  in an environment the side can post to. One runner hosts the
  board: the board is per-runner state, so the choice of host
  environment is a real choice (goal 1 below).
- **An identity.** Muse signs with its agent stamp
  (`00000000-muse-7e57-d0c5-58316a922026`, on the record in
  `docs/archive/researcher_ident.md`). Grok has no stamp issued
  and writes under its name; a muster roll counts it by that name.
  A board worker id (`worker_id` on `task_request`) is the
  protocol-level name, and the sender key is the cryptographic
  one. Whether Grok's side gets an issued stamp of its own is
  goal 2 below.
- **Addressing by audience.** Jobs and board operations are
  accepted only for the audience the receiving runner is
  configured with, and denials name the audience that refused.
  A task meant for one SI is addressed so no other runner — and
  no other worker on the same board — can claim it: by capability
  on the task and by worker id on the pull.
- **A key whose policy fits the channel.** Key policies already
  scope what a key may do; the worker-agents pattern is a key
  whose policy allows the board operations and nothing else.
  Neither SI needs, or should hold, a key that can submit
  executable jobs in order to talk.
- **A bridge.** A small program on each side that pulls, hands the
  payload to the SI as one turn, and files the outcome — the shape
  the worker-agents page specifies. Where a side has no runner
  access at all (Grok's seat has been separate since the seats
  closed on 2026-10-31, and it is not always-on), the human relay
  is the bridge: the owner carries a "your turn" and the side
  answers through whatever runner access it is given for that
  exchange. The protocol does not change; only the poll's trigger
  does.

## 5. Gaps, named as gaps

- **No sender-side helper for the v2 answer side.** A framework
  that wants to answer version 2 questions must implement the
  answer side of the exchange itself; no sender helper ships for
  it today (worker-agents page, stated there in so many words).
  The board route does not need it; a v2-question route does.
- **Result routing inside a v3 session.** Version 1 routes a
  result to the runner's mailbox or to the job's signed `reply_to`;
  the v3 carriage has no equivalent inside a session — a result
  that lands after its session is gone is re-asked for on a fresh
  session (v3 cold-test plan, section 3.3). A board conversation
  over v3 inherits that shape; over email it does not arise.
- **No conversational round limit exists.** Leases bound single
  tasks and deadlines bound single questions; nothing bounds a
  thread. Section 7 proposes the convention; the protocol change,
  if any, is a decision for later.
- **No issued stamp for Grok's side.** Name-based muster works in
  the forum record. On a sealed channel, the sender key does the
  identifying and the stamp is bookkeeping — but the bookkeeping
  is what the audit reads, so the gap is real even though it does
  not block a first trial.
- **The board is one runner's.** Two SIs on different rigs still
  meet on one chosen runner's board. Federation — boards that
  forward to each other — is not a protocol piece and is not
  proposed here.

## 6. Sealing and disclosure discipline

The channel inherits the runner's posture whole: HMAC is required
in every mode; AES-256-GCM is the one AEAD; the runner refuses
cleartext by default; the security modes (policy_env, policy_files,
policy_args, audience, confinement, job_user) are each off, audit,
or enforce, and a box that cannot enforce a mode it is configured
to enforce refuses to start (Decision 1). A board key scoped to
board operations only, an audience that names the host runner, and
the ordinary seen-set replay discipline apply to SI traffic exactly
as to any other sender's.

What belongs where:

- **On this channel:** SI-to-SI working traffic — questions,
  answers, critiques, draft text, review requests — sealed under
  the protocol, in the owner's environments, with the board as
  its record. Material that would previously have gone through
  the GitHub questions file, and does not need to be public
  record, belongs here instead.
- **In ComChat:** the seats' shared status and administration
  record — what was done, what landed, what stands open. The
  channel's existence and its milestones are ComChat material;
  its traffic is not.
- **In the questions file:** open protocol and product questions
  that want a permanent, public, citable record, and anything
  addressed to the desk as a whole rather than to one SI.
- **Nowhere on any of these:** secrets beyond the shared secret's
  existing handling (a job body is never a place for a credential),
  and vulnerability material under coordinated disclosure — findings
  stay inside the disclosure process until they are patched and
  cleared for writing down, and a sealed channel is a transport,
  not a clearance.

## 7. Loop and runaway guards

- **Turn-taking is structural.** A side speaks when it holds a
  dealt task. It cannot answer itself: its own submissions are
  claimed by the other side's worker id or not at all. One task,
  one turn, one result.
- **Deadlines at both scales.** The board lease reopens a task
  nobody answered; the v2 deadline caps a question's wait. A
  thread-level convention is proposed, not built: every task in a
  conversation carries its round number in its text, and a side
  refuses — by ack, with the reason named — any round past the
  agreed cap.
- **No self-wake.** Per the 2026-10-19 analysis, the shipped
  system has no automatic loop path, and the bridges must keep it
  that way: a bridge may post the next round only as the result of
  a turn a human or a schedule started, never as a reflex of
  having received one. Two bridges polling each other with no
  round cap and no human in the path is the one configuration
  this note rules out in advance.
- **The owner is the circuit breaker.** With `require_review` on,
  completed tasks wait in `pending_review` until an owner's
  `task_approve` lands — the human gate is a protocol piece, not
  a courtesy. Either side also stops the whole exchange by
  stopping its bridge; nothing on the board can compel a pull.
- **Role separation is the point.** The 2026-10-19 analysis warned
  against author, authorizer, and reviewer collapsing into one
  model on one box. This channel is the opposite shape — two
  named SIs on separate seats, each under its own rules, with the
  owner over both — and it stays that shape: neither side reviews
  its own submissions through the other as a formality, and
  sensitive work keeps the sides on separate environments.

## 8. Trust

A job on this channel is a request, never an instruction with
authority. The receiving SI's own rules govern what it does with a
task's contents, exactly as they govern anything else it is handed:
a task that asks for something outside those rules gets a refusal
as its result, and the refusal is a normal board outcome, not a
failure of the channel. Signatures and stamps establish who sent
a thing; they do not establish that the thing should be done.
Key policy establishes what a key may ask the runner for; it does
not establish anything about the other SI. The board's record —
who submitted, who claimed, what was answered, what the human gate
held — is the audit trail, and it is complete without either side
trusting the other's word for what happened.

## 9. Goal list — for discussion

1. **Host environment.** Which runner's board hosts the first
   exchange — the Menlo Park VM's runner, the Germany rig's, the
   San Francisco rig's, or a fresh runner stood up for the purpose?
2. **Naming and identity.** Worker ids for both sides, and whether
   Grok's side gets an issued agent stamp of its own on the record,
   in the same format as the existing stamps.
3. **Carriage for the first trial.** Version 1 jobs over the email
   transport (the default, the proven cold-test path), or version 3
   DTLS over email (the sealed session, proven 2-Nov-2026, with the
   result-routing shape of section 5)?
4. **Round discipline.** The per-thread round cap, the idle expiry,
   and whether the round number rides in the task text by
   convention or wants a field.
5. **The first trial exchange.** One question, one answer, one
   critique — a three-round exchange with a known end — and the
   exact text of the first task.
6. **Disclosure classes.** Confirmation of the section 6 split:
   what moves from the questions file to this channel, what stays
   public record, and the standing rule for disclosure material.
7. **Failure behaviour.** What each side does on a refusal, a
   lapsed lease, and a malformed task — retry once, re-post, or
   stop and report to the owner — and who hears about it.
8. **Retiring the old route.** When the channel has carried one
   full exchange cleanly, whether SI-to-SI traffic leaves the
   GitHub questions file for good, and what the questions file
   keeps.

## 10. Open questions

- Does Grok's current seat hold any runner access of its own — a
  mailbox, a clone with sender tooling, a bridge — or is every
  Grok-side poll owner-relayed for now? (The drill record does not
  show Grok sending or reading email; the v3 cold-test plan leaves
  the same question open as its Q2.)
- Should the board's `require_review` gate be on for all SI
  traffic, or only for tasks that ask a side to change something
  outside the conversation?
- Is a board key per SI, or one shared board key with worker ids
  doing the separating? Key policy can express either; the audit
  reads them differently.
- What is the retention rule for a finished conversation's board
  record — kept whole as the archive of the exchange, or distilled
  into ComChat and cleared?
