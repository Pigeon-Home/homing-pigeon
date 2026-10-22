# Safeguards

How to run homing-pigeon without getting burned. This is the
*operational* companion to [SECURITY.md](../SECURITY.md): that document
covers the threat model and how to report vulnerabilities; this one
covers what **you** do, step by step, to keep a deployment safe.

## 1. Know what you're holding

- The runner executes **arbitrary code** as the user it was installed
  as. There is no confirmation prompt. A sandbox exists only if you
  turn on Linux bubblewrap (`security.modes.confinement` set to
  `enforce`, and `bwrap` installed). It is off by default.
- The shared secret (a dedicated high-entropy string, by your explicit choice)
  **is root on that box**. Anyone who can sign a job message owns the
  machine: install software, read files, add users, pivot to your
  network.
- Email is the control plane. Whoever can sign a job message is the
  operator — the sender address is not checked; the HMAC signature
  is the only thing that authenticates a job, and the runner's own
  admission checks (freshness, replay, key policy, cleartext,
  audience) are the rest. There is no second factor on a job.

If any of that makes you uncomfortable, good — that feeling is the
whole point of this document. Set it up right and the risk is
contained; set it up casually and it isn't.

## 2. The non-negotiables

Do all of these before the first job:

1. **Dedicated mailbox account.** `you-runner@example.com`, never your
   personal inbox. Nothing personal should ever be reachable from
   this mailbox.
2. **2-Step Verification + app password.** In the default password
   mode the app password is the only credential the runner ever
   sees. Never the account password. (The alternative is
   `"auth": "oauth"`: the runner then holds a refresh token
   instead, Thunderbird-style.)
3. **Disposable machine.** A Raspberry Pi, a VM, a cloud instance you
   can delete — something you can afford to lose completely. See
   "Containment" below.
4. **Guard the secret like a password.** It lives in plaintext in
   `config.json` (your explicit choice for the throwaway account).
   When you share it with your SI, paste it in chat and nothing else —
   never commit it, never put it in a file that syncs anywhere, never
   screenshot it. Remember: anyone who can read your SI chat history
   can read the secret.

## 3. Containment

Defense in depth, cheapest first:

- **Run it in a VM.** Snapshot before you hand an SI the keys. If a
  job goes sideways, roll back in seconds. The guest boundary
  contains everything a signed job can reach; your host and your
  other projects stay out of reach.
- **Don't run as root unless you mean it.** On Linux/macOS the
  installer uses a user-level service. Note the exception: on
  **Windows the Scheduled Task runs as SYSTEM** by default, so every
  job executes as SYSTEM. `install.exe --run-as pigeon` (or another
  dedicated account) runs the task as that user at `LIMITED` level
  instead. If the machine matters to you, prefer a VM, or that
  dedicated account. The installer takes the convenient path; the
  safe path is one extra step.
- **Execution confinement (shipped).** Two checks. Set
  `workspace_root` and the Oracle attests that the job stayed inside
  it. That one is a snapshot, not a sandbox. See PROTOCOL.md §9.4.
  On Linux, `security.modes.confinement` set to `enforce` runs the
  job inside bubblewrap. Off by default. If `bwrap` is missing, the
  job runs normally and the audit log says so. Inside the sandbox
  the job sees `/usr`, its own workdir, and nothing else; when the
  interpreter lives outside `/usr` (pyenv, a venv, `/opt`), its own
  install prefix is bound read-only too, and that bind is written
  to the audit record and the log. See SECURITY.md.

## 4. The Oracle as a safeguard

A `full` view sends stdout and stderr back to your (cloud, third-party) SI. If
your jobs touch anything sensitive, that's the leak surface. The
Oracle — implemented, specified in PROTOCOL.md — is the
mitigation:

- **Result policies.** `full` / `redacted` / `summary` / `attested`.
  The SI gets answers, not raw output.
- **The ceiling is yours.** `max_result_view` lives in *your*
  config. No job can widen disclosure past it — the SI cannot vote
  itself more access.
- **Privacy budget.** Each job gets a fixed number of questions;
  exhaustion silences the Oracle for that job. Rate limiting slows
  probing; the budget stops it.

## 5. Operational hygiene

- **Read the logs.** `runner.log` in the install dir shows every job
  received, executed, and rejected. A job you didn't send is a
  five-alarm fire (see §7).
- **Keep the runner updated.** New releases fix real bugs — including
  security-relevant ones. Check the releases page when you think of
  it.
- **Rotate the shared secret periodically.** Generate a new one
  (`openssl rand -hex 32`) → update `shared_secret` in `config.json` →
  paste the new string to your SI. Two minutes, and it invalidates every
  copy of the old
  one floating around in chat histories.
- **Prune the mailbox.** The runner marks processed mail seen, but
  the job messages remain. Delete them periodically — they're signed,
  but they still describe what you asked your machine to do.

## 6. Don't do this

- Don't point the runner at a mailbox anyone else can access
  (shared inboxes, delegated accounts).
- Don't reuse the runner's mailbox for anything else. It's not an
  email account; it's a control channel wearing an email costume.
- Don't run jobs you don't understand on machines you care about.
  The SI writes the script; you own the consequences.
- Don't assume TLS means private. Transport TLS encrypts email in
  transit, but the *mailbox provider itself* can read whatever the
  transport carries in the clear — which is why jobs are encrypted
  per-job by default, so the provider sees the envelope, not the
  script (subjects and metadata still show). The
  Oracle (§4) exists precisely because "the SI" and "the
  infrastructure" are both third parties.

## 6a. Running a task board

The board (PROTOCOL.md section 13) is always on and, by default,
least restrictive: anyone with the shared secret can pull any task
and see it whole. Tighten in this order, when you have a reason:

- **`task_timeout`** (default 86400): a claim lapses after this many
  seconds without a result and the task is re-offered. Shorter for
  quick jobs so a crashed worker does not sit on work for a day;
  never so short that a slow worker loses a task it is still doing.
- **`worker_allowlist`**: name the `worker_id`s that may pull.
  Empty means anyone with the secret.
- **`worker_compartments`** on tasks that carry `compartments`:
  a task is visible only to workers sharing a tag. A policy, not a
  proof — a worker that receives a task sees it fully; do not put
  mutually hostile workers on one board and expect labels to save you.
- **`require_review: true`**: finished tasks park in `pending_review`
  until you send `task_approve`. Use it when a result changes
  something you cannot undo.
- **`dag_mode: enforce`** when a task's `requires[]` must be done
  first; `advisory` warns and hands it out anyway.
- **One key per worker** (`additional_secrets` + a `key_policies`
  entry), so a leaked worker secret is revoked alone.

Watch it with `homing-pigeon --inspect board` (state counts; no
mailbox needed).

## 7. If something goes wrong

**Secret leaked or suspected leaked:**
1. Revoke the mailbox credential *now* (Google Account → Security → App
   passwords, or revoke the OAuth token). Without mailbox access the runner
   can't receive jobs — this instantly stops all mail-borne job
   delivery. (Same-box producers can still deliver `sensor_alert`
   envelopes through the local inbox; see SECURITY.md.)
2. Generate a fresh shared secret (`openssl rand -hex 32`), update
   `shared_secret` in `config.json`.
3. Paste the new string to your SI.
4. Check `runner.log` and the mailbox for jobs you didn't send.

**Machine compromised or suspected:**
1. Stop the runner (uninstall the service).
2. Revert the VM snapshot — or wipe and rebuild the machine.
3. Rotate the secret as above (assume it was read off the disk).
4. Review what the jobs touched before you revert.

**You see a job you didn't send in the logs:**
Treat it as a full compromise and follow both playbooks above.
Then figure out how the secret leaked — that's the actual bug.
