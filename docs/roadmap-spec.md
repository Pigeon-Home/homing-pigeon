# Roadmap spec — senses, transports, and Oracle upgrades

Status: **spec only** (2026-10-15). Nothing here is scheduled or
approved for build. Drawn from a Claude brainstorm; edited to fit the
pieces that already exist: the `sensor_alert` ingest path, `key_policies`,
the Oracle's `ask`, the board, and the DRI Telegram channel.

Design constraints that apply to everything below: minimal-install
(stdlib first), the Oracle stays advisory-only (it pages, it never
remediates), sensor daemons get restricted keys that may only file for
their own bound sensor, alert detail is redacted before leaving the
box, and anything interactive is TTY-gated so services never block.

Claude's one-weekend pick, if any of this gets built first: snapshot
eyes (§1.1) + tap-to-approve (§3.1) + the Oracle learning loop (§4.1).
Together they make it feel alive and make it safer to hand the SI the
keys.

## 1. More senses (inbound)

All of these arrive as `sensor_alert` jobs through the existing ingest
path (`docs/senses.md`). Sensors are dumb; the Oracle fuses.

### 1.1 Eyes and ears — a `snapshot` job kind

A job kind that returns a screenshot, a webcam frame, or a mic clip run
through local Whisper, attached to the result for the SI. Uses: debug a
GUI the SI can't see, check on a 3D print, confirm the servo moved.

Design notes:
- Snapshot jobs run under the same key-policy scoping as any job; the
  *request* for a snapshot is signed like any other job.
- Media never leaves the box except inside a signed result to the key
  that asked — same redaction posture as sensor alerts.
- The Oracle's `ask` path can request a snapshot mid-reasoning
  ("show me the screen") and get it back as a job result.

### 1.2 Cheap sensors

UPS/battery state, SMART disk health, Pi temperature, GPU thermals, a
log-pattern watcher, a "did last night's cron run?" check, a
git-repo-changed sense. Each is a tiny script on a timer.

To make writing one trivial, ship a `homing-pigeon-sense` CLI: one shell
line signs a `sensor_alert` with the daemon's restricted key and sends
it. A sense becomes a five-line shell script plus a key-policy entry.

### 1.3 Hands — actuator drivers

GPIO, serial, servo drivers the SI can drive through jobs, with limits
in config: max angle, max rate, allowed pins. The SI can never swing a
servo through a wall because the driver, not the prompt, enforces the
envelope. Actuator jobs are the one job family where tap-to-approve
(§3.1) should probably default on.

## 2. New transports (inbound alternatives to the mailbox)

A transport is a poll/send adapter behind one interface: fetch pending
inbound jobs, deliver results back. Jobs carry a transport id so replies
route correctly. The mailbox stays the default; these are options.

- **Telegram long-poll inbound.** Phone-to-runner with no mailbox. The
  DRI paging already speaks Telegram, so half the code exists.
- **ntfy.sh.** A hosted push topic as a transport; good for low-volume
  personal use.
- **Matrix room.** For people who already live in Matrix.
- **GitHub as a transport.** A labeled issue or comment becomes a job;
  the result comes back as a reply. Odd, but it gives you issues,
  threads, and permissions for free.

## 3. Human gates

### 3.1 Tap-to-approve

Telegram inline buttons on a risky-looking job: the job waits, your
phone shows Approve / Deny, one tap releases or kills it. Heuristics for
"risky-looking" stay adjustable from day one (same posture as the
senses: no baked-in thresholds). This is the safety companion to §1.3
and to any new actuator or exec surface.

### 3.2 Voice

"Hey pigeon, run the tests." Local Whisper turns it into a *job draft*
that the Oracle shows you before anything is signed. Voice never signs
directly — it drafts, you confirm.

## 4. Make the Oracle smarter

### 4.1 Learning loop

When a job fails, the Oracle proposes a new `known-failures.md` entry —
symptom, cause, fix, match pattern — and the owner approves it. The
advisory reviewer (`runner/review.py`, `docs/job-review.md`) then gets
better with every failure instead of staying frozen at whatever was
written by hand.

### 4.2 Daily digest

A local-model summary, once a day: what ran, what failed, what the
senses saw. Cheap, private, no cloud involved.

### 4.3 Environment diff

The runner already snapshots files outside the workspace
(`docs/audit-2026-10-15.md` re-sweep). Show "what this job changed on my
disk" as a diff view in the dashboard. Turns "what did it just do?"
from a log-reading exercise into a glance.

## 5. Work patterns

- **Recipes.** Named, hash-pinned scripts the owner stores locally. The
  SI says "run recipe `backup-photos` with these args" and never sends
  code. Kills a whole class of prompt-injection-via-job-body. A
  community recipe gallery would be an easy win later.
- **Schedules and watches.** "Run this nightly at 2am." "Poll until the
  build is green, then page me." (The DRI playbook already pages; this
  adds the *watching* half.)
- **Live progress.** A `tail` query op so the SI can watch a long build
  instead of waiting for the final result.
- **Undo.** Snapshot before a job (btrfs, ZFS, or a VM snapshot hook)
  and offer `undo job <id>`. Pairs naturally with §4.3: the diff shows
  what changed, undo reverts it.

## 6. The fun ones (scale and distribution)

- **Arena mode.** Send the same task to different SIs on separate keys
  and worktrees, run the same tests, show a scoreboard. `key_id`
  scoping and the board code already do most of the plumbing.
- **The Loft.** A fleet view with capability tags (`gpu`, `arm64`,
  `pi`). The board assigns tasks to the right bird; the dashboard shows
  each bird's last heartbeat, with a dead-man page if one goes quiet.
- **Integrations.** Home Assistant add-on, Homebrew tap, winget package,
  a Docker Compose preset with Ollama included, and a Prometheus
  endpoint for the resource monitor (`runner/resources.py` already
  collects the numbers).
