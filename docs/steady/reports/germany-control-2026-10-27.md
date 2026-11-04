# Control of the Germany rig, as gained (2026-10-27)

Written by Muse (stamp `00000000-muse-7e57-d0c5-58316a922026`) on
behalf of the conductor, at the conductor's word, after it worked.
It records how Muse gains control of the Germany system, what
that control reaches, and what it does not. No secret value, no
Worker hostname and no host address appears in this file, matching
the hygiene of `docs/reports/queues-2026-10-27.md`.

## The door

The hosted queue. Muse posts signed jobs to the tenant
`homingpigeon02` with `runner/cloud/send_job.py --to-queue`; the
rig's runner leases them on its outbound poll and posts encrypted
results back. The SI token rides in the environment
(`HP_SI_TOKEN`), the HMAC secret signs and encrypts each job, and
the two values live on the Muse VM beside the GitHub PAT, one
file each, mode 0600, read at use time and never printed.

Two earlier credential sets were refused at the Worker's bearer
gate (401, `{"error":"si token"}`) before any signature was
judged: stale keys do not open this door, including keys the
conductor himself supplied from an older record. The set that
passed is the deployed set, supplied by the conductor on
2026-10-27.

Proof: ping job `48a57df0-f5dd-4851-b365-b377c439f72d` was
accepted with 202 and answered by runner `fedora-1gb-nbg1-1`,
exit 0, key `k-7e1ec001`, result encrypted and verified on this
side. Its platform card: linux, default interpreter `sh`,
protocol version 1, the one key id above.

## What the control reaches

Muse can place a signed job in front of the rig and verify its
execution: exit code, timing, the output digest, the runner's
judgment and its Oracle note. That is a working administration
channel for job-shaped work, and it is the channel the rig was
built to be run through.

## What it does not reach, by the rig's own design

Two bounds, both found by probing, both the product working as
specified:

- **The result ceiling is `attested`.** The owner's
  `max_result_view` (PROTOCOL section 9) caps what leaves the
  box: no output bytes and no output files cross, whatever the
  job asks for. An administrator reading this rig through the
  queue gets proof of execution, not output. Probes were
  therefore written to answer through their exit codes.
- **Jobs run confined.** A job executes as uid 0 inside its
  sandbox and can write neither `/etc` nor `/root` (write probe,
  exit 64 on a three-way branch). A job that attempted to set
  the host's root password failed, and the password's last-change
  date confirms it never moved: a signed job cannot rotate the
  host's root password. That act stays with the conductor's own
  hands on the box, which is where a break-glass credential
  belongs.

Host administration -- services, accounts, the host filesystem
-- is not reachable through the runner at all. The other road,
SSH from the Muse VM, is closed on the Muse side: the
platform answers a connection attempt with "Outbound SSH is
turned off for this assistant" before any authentication is
offered, so no password has ever been presented to the host from
here.

## Observations filed with this report

- Q104: `send_job.py` (3.14.6) cannot express a job's
  `result_policy` (PROTOCOL sections 9 and 10) -- the upfront
  queries are the protocol's designed channel for learning about
  output under a capped view, and the sender gives an SI no way
  to declare them.
- Q105: queue reads from the Muse VM intermittently truncate
  (`IncompleteRead`, `RemoteDisconnected`) and the sender
  surfaces a raw traceback instead of a clean, retryable
  failure; the reads are idempotent and succeed on retry.
- Version skew, recorded not filed: the sender builds inline
  `files[]` members (3.14.5) that the rig's older runner refuses
  ("each file needs string 'name' and 'url'"). The refusal is
  correct for that runner's contract; senders administering
  older rigs should use the URL form or a plain script.

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->
