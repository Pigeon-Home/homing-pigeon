# Homing Pigeon

**Works with Muse, Grok, ChatGPT, Claude, Gem..., Copilot, etc.**

Your cloud SI is smart, but it can't touch your computer. Homing Pigeon
fixes that: tell your SI to complete a task and it will do it on your
machine. The results return so that your SI can iterate — run the tests,
read the failure, fix, repeat. From your phone or anywhere.

Install the Homing Pigeon agent on a machine you own. At setup it asks
for the login credentials of a dedicated email account — email is the
default transport. The agent bears a resemblance to GitHub self-hosted
runners: a small program on your hardware that takes jobs from
somewhere else and runs them here.

Then try this prompt in your cloud SI, it should return in less than 30 seconds.

```
Send an email to YOUR_RUNNER_EMAIL
Use this protocol: https://pigeon-home.com/PROTOCOLv1
Shared Secret: "YOUR_SECRET_STRING"
I have a Windows computer. Retrieve the system clock from it and display it here.
```
IETF Homing Pigeon Draft: https://github.com/Pigeon-Home/homing-pigeon/blob/main/docs/ietf/draft-homing-pigeon-01.md

> ⚠️ **USE AT YOUR OWN RISK.** This tool hands **full administrative
> control** of the machine to whoever holds the shared secret. The
> runner verifies a message's signature and then executes what the
> signed job says, as a privileged user — it can install software,
> read files, add users, and pivot to your network. That is the
> product working as designed, so treat it that way: keep the secret
> like a password, use a dedicated throwaway mail account, install
> only on machines you own and operate, and review PROTOCOL.md
> before you deploy. The threat model is stated once, here; the
> long form is [docs/threat-model.md](docs/threat-model.md).

## What this is for

Homing Pigeon is a personal remote-development agent. The point is not
that the SI becomes smarter. It is that the SI gets a way to delegate
work to a computer it could not otherwise reach. The most powerful
computer you have access to should not stop being useful the moment you
walk away from your desk, and neither should your SI assistant.

Concrete uses:

- **Remote test runs.** Ask your SI to run the suite, read the
  failures, patch the code, rerun, and report back, all while you are
  away from the machine.
- **Your hardware as a worker.** Long builds, data crunching, batch
  jobs, on the workstation you own, without a remote-desktop session
  open.
- **Scheduled-style automation.** Maintenance scripts, reports, and
  repetitive technical tasks, dispatched from your phone.
- **Cloud SI, local resources.** Your files, your dev environment,
  your GPU, reachable by an assistant that lives in the cloud.
- **Physical peripherals.** Plug a sensor or servo board into a
  Raspberry Pi, point your SI at it, and let it write the control
  code and debug the hardware into motion. You do the soldering,
  it does the head-scratching. Let SI build a robot.

Send a job from your phone, let the big machine run the tests, crunch
the data, or grind through the refactor, and read the results when they
land in your inbox.

The SI systems are brilliant, but they are kept fenced off from our
real machines. Homing Pigeon gives one a signed channel to a machine
of yours and lets it do tasks from start to finish — an assistant
that operates, not just advises. Which machine is your choice: the
workstation on your desk, a spare box in the corner, a Raspberry Pi.
How much rope it gets there is also your choice — that is what the
postures in Operating modes (below) are for.

A new model claims to be good at something — robotics, automation,
data work? Point it at a box and find out.

It belongs to the same family as GitHub self-hosted runners, VS Code
Remote tunnels, and Tailscale — legitimate tools for administering your
own hardware remotely. And like all of those, its power is the point,
not an accident.

```
  SI (cloud)                        Your machine
  ------------                      ------------------
  send_job.py --sign--> job message -->  runner.py
       |                  |              |  poll IMAP
       |                  |              |  verify HMAC
       |                  |              v
       |                  |           run script
       |                  |              |
       |             result message <--+ sign
       v                  |
  verify result <----------+
```

Large inputs don't go through email: your SI uploads them to file hosting
and the job message carries download URLs (with optional SHA-384).

**Why email?** Because it's the only transport with all four properties
on day one: reachable from anywhere, outbound-only polling (no inbound
ports — NAT-proof), at-least-once delivery, and
zero infrastructure to operate. The protocol does not care about the
pipe — every transport is an extension the runner supervises (a
watched folder, core NATS, and a direct DTLS session binding
ship alongside email) — but email
stays the default; a credentialed transport adds
its own required gate beside the signature, which makes it the
more secure option even though it is not the default. (A
sensor on the same box also delivers its signed alerts directly,
by local inbox or loopback socket -- alerts, not jobs.) Anything
else is in [FUTURE.md](FUTURE.md).

**Runbooks, not prompts.** The SI doesn't chat about the task — it ships
a runbook: deterministic steps, each with a check that proves the step
worked. The runner executes it and reports back what actually happened,
and that feedback goes into the next runbook. Each cycle is a little
smarter than the last, because the failures are data. If you've ever
debugged something by running it, reading the output, and trying again
with what you learned — that's the whole product. The SI is just the
part that writes the next attempt.

## The Oracle: the witness on your side of the wire

The runner faces the SI. The **Oracle** faces you. It is the part of
the agent that works for the owner of the box: it watches every job
as it runs, checks each job against this machine before it runs
(opinions, below), fuses the box's sensor alerts with job activity,
and — in the watching postures — pages you when something trips.
It also answers the SI's questions about job output, at the
disclosure ceiling you set, and not one byte past it.

That ceiling is the thing to understand. By default it is **full
output**: the SI sees what the job printed, because that is what
makes the runbook loop above useful. Tighten it, and the shape
changes: the SI questions the Oracle rather than inspecting output,
and gets back HMAC-signed *attestations* — "did the tests pass?",
"does the output contain secrets?" — proofs about the output that
reveal nothing else. It's the interactive-proof shape applied at
the trust boundary — prove things about your data without showing
your data — without any zero-knowledge proving machinery: the
attestation is an HMAC, and the runner itself is trusted. The
attestation shape is there when you want it; it is not the posture
the box ships in.

```
  Cloud SI                                Your machine
  --------                                --------------------
  "Did the tests pass?" --signed------> +-------------+
                                        |  The Oracle |
  "Any secrets in there?" ------------> |             |
                                        | output stays|
   +---------------------+             | on your disk|
   | signed attestation   | <--signed-- |             |
   | { exit_zero: true,   |             | answers only|
   |   no_secrets: true } |             | what policy |
   +---------------------+             | allows      |
                                        +------------+
   The SI learns what your ceiling allows.
```

Queries are declared upfront (no adaptive probing), each job gets a
privacy budget bounding total leakage, and the disclosure ceiling is
set by *you* in config — never by the SI.

Your machine runs two roles in one box:

```
+-----------------------------+-----------------------------+
| RUNNER (faces the SI)        | ORACLE (faces you)           |
+-----------------------------+-----------------------------+
| polls the mailbox            | watches jobs as they run;    |
| verifies HMAC + key policy   | its opinions ride results    |
| judge: an opt-in gate        | fuses sensor alerts          |
| executes jobs; cage opt-in   | watches resources            |
| answers queries at the       | pages you when a             |
| ceiling you set -- the       | threshold trips              |
| default is full output       | orders kills in oracle mode  |
+-----------------------------+-----------------------------+
```

The runner does what the SI asks. The Oracle watches what happens
and tells you about it.

**Opinions, before anything runs.** By default the Oracle checks
each job against this box first — is the named interpreter here?
are the tools it invokes on PATH? does the script's shape fit this
OS? Its default latitude is **repair**: the one mechanical fix
those checks can prove — an absent interpreter, replaced with the
platform default when the script's shape fits it — is applied,
and never silently. The result says what changed and carries
`received_digest`, the digest of the job exactly as received, and
the repaired job is judged again before it runs. When a job asks
for an opinion, the prediction rides its result too. The owner's
`oracle_opinion_mode` is both the default latitude and the
ceiling: a job may ask for less, never more. Design:
`docs/oracle-opinion-design.md`.

### Operating modes

Five knobs set the posture. They are independent — these are three
coherent postures, not the only combinations. The postures are
choices about trust: how much you watch, and how much the box may
refuse, is yours to pick per machine.

```
  knob                  just run it  eyes open    lockdown
  ------------------    -----------  ---------    --------
  judge                 off          advisory     enforce
  sensors               off          on           on
  resources             on           on           on
  dri                   off          on           on
  max_result_view       full         attested     attested
```

**just run it** (the defaults) — you trust the signer, so the box
just works. Runner: executes any signed job, answers queries with
full output. Oracle: reviews every job anyway (its notes ride in
the result) and logs resource pressure. Quiet by choice: nothing
pages, and the judge never blocks a job at the door.

**eyes open** (recommended) — same trust, but now you watch.
Runner: executes, attaches the policy verdict to each result,
answers queries with attestations only. Oracle: reviews, fuses
sensor alerts, and pages you when a trigger trips. This posture
is about seeing; the acting, when any happens, belongs to the
remediation reflexes below — they answer to their own switch,
not to this table.

**lockdown** — the box refuses what the policy rejects. Runner:
refuses anything the policy rejects; the SI gets attestations.
Oracle: same as eyes-open, and every refusal is page-worthy.
Nothing moves unless the policy allows it.

Two more dials stand outside the table. **Remediation**
(`remediation_mode`, default `deterministic`) watches each job
while it runs: on a closed list of tripwires — confinement
escape, a process storm past the ceiling, an undeclared
credential-store reference in something the job produced — it
kills the job's process tree, quarantines its outputs (moved,
never deleted; you release them), refers suspect files to the
box's own antivirus for the antivirus's verdict, and files the
whole story with the DRI, which pages you when paging is on.
That happens in every posture above. `oracle` mode additionally
lets the local model order a kill for a lesser divergence;
`off` watches and records only, and the page is all that
happens. **The opinion latitude** (`oracle_opinion_mode`,
default `repair`) is the other dial — it is covered under
Opinions, above.

Confinement ships in two kinds, and they are not the same kind
of thing:

- **A snapshot is not a sandbox.** The workspace check compares
  file metadata outside the job's workspace before and after the
  run, then attests `confined_to_workspace`: it *detects* a job
  that reached outside, it does not prevent one. The walk stops
  at 50000 files, so a huge tree yields a partial snapshot and
  the log records the cap being hit. The key is `workspace_root`.
- **The sandbox** (Linux only) actually walls the job in:
  bubblewrap runs it with `/usr` read-only, no network, and only
  the job workdir writable. It is off by default; if `bwrap` is
  missing, or the machine is not Linux, the job runs normally
  and the audit log records the fallback. The key is
  `security.modes.confinement` set to `enforce`. See SECURITY.md.

**Local inference.** Point the Oracle at a model running on your
own box and the SI can `ask` questions in plain English — *"why
did the tests fail?"* — answered locally, with only the answer
crossing the boundary. The endpoint must be loopback (fail
closed), and every answer is truncated, redacted, and
secret-scanned before it's sent. The SI gets useful answers,
and your raw data never leaves the machine.

**Two Oracle modes.** With `oracle_mode: "llm"` (the default) the
Oracle narrates with the local model above. With `"deterministic"` —
the Pi Light mode, for a box with no model worth running — no model
is installed or ever called: the watch, the wake gate, and the briefs
still run, but briefs and answers are assembled from the box's own
records (the job index, retained jobs, notable lines, the log tail),
and the `ask` op stays off. The mode reads live from `config.json`;
flipping it is the upgrade path when a box gains a model worth
running. See `docs/configuring-oracle.md`.

**The Oracle learns from its own calls.** Before a job runs, its
opinion — *this will probably succeed here; this will faceplant,
and here is why* — is frozen. The moment the job finishes, the call
is compared against what actually happened, and the comparison is
written to a local ledger (`oracle-learning.jsonl`) immediately;
the next job's opinion is formed with that ledger read fresh, no
restart. Two kinds of lessons accumulate: **verified facts**,
derived by code from execution records (an interpreter was absent
and the fix worked; a named tool is not on this box), and — only
when the owner enables the model channel — **model candidates**,
distilled from a job's outcome and output, labeled uncorroborated
wherever they surface until later verified outcomes corroborate
them. A lesson never authorizes anything by itself: a repair still
requires the repair latitude, the mismatch re-verified on the
current job, and the repaired job judged again before it runs.
Set `oracle_learning` to false to turn the loop off. Design:
`docs/oracle-opinion-design.md`.

Full spec in PROTOCOL.md (sections 9–12). Oracle fields are optional
members of a `"v": 1` message. They are not a separate message version.

## Extending the agent: your own senses

Extensions let you teach the agent a new sense.
An extension is a folder with a manifest (`extension.json`) that
declares, in advance, the signals it may send the Oracle — each
signal named, with a one-line description. That declaration is the
context the Oracle receives alongside the alerts: a signal the
manifest does not declare is rejected at ingest and logged, never
passed through, so the Oracle is never asked to interpret a signal
nobody defined.

The research loop is the point. Clone the repo, copy the example
extension, and iterate on your own package — your data, your
heuristics, your version number, revved as often as you like. The
extension API the manifest is written against is version 1 and is
designed to stay there: fields may be added, never removed or
reinterpreted, so an extension written today keeps loading. An
extension binds to its own signing key, exactly like the built-in
senses, and files alerts the Oracle fuses with job activity.

The example is a lab-results sense: it watches a folder where
experiment runs drop result files and files signals like
`experiment_finished` and `metric_threshold_crossed` when a run
lands. Full walkthrough: [docs/extensions.md](docs/extensions.md).

## Layout

- `PROTOCOL.md` — the full wire protocol (message formats, signatures,
  verification rules, security model).
- `FUTURE.md` — work that is not built. The only list.
- `TRANSPORTS.md` — the job transports as shipped: email (default),
  file, core NATS, and the DTLS session binding (off unless
  enabled — it is the one transport that listens). Everything
  past those in that file is design notes, not code.
- `SAFEGUARDS.md` — how to run this without getting burned: the
  non-negotiables, containment, the Oracle as a safeguard, and what
  to do when something goes wrong.
- `docs/` — the long shelf: the threat model and security gaps,
  configuring the Oracle, the extensions walkthrough, and the
  design records (opinions and self-learning, remediation).
- `runner/runner.py` — the agent. Polls, verifies, executes,
  replies. No dependencies beyond the Python 3.9+ standard library.
- `runner/transports.py` — the transport-extension contract
  (v1), discovery, and supervision: the core is transport-blind,
  and email, the watched folder, core NATS, and the DTLS
  listener all run as supervised extension programs under
  `runner/transport_extensions/`, enabled by the `transports`
  config key.
- `runner/opinion.py` — the Oracle's opinion: the pre-run checks,
  the prediction, and the one mechanical repair.
- `runner/learning.py` — the self-learning ledger: frozen calls,
  scored outcomes, and the lessons the next opinion reads.
- `runner/remediation.py` — the running-job monitor: tripwires,
  quarantine, antivirus referral, the page.
- `runner/install.py` — installs it as a boot-start service: systemd
  (Linux), launchd (macOS), cron @reboot (FreeBSD), Scheduled Task
  (Windows).
- `runner/config.example.json` — copy to `config.json` and fill in.
- `cloud/send_job.py` — cloud-side helper: builds signed job messages,
  verifies result messages. (Your SI uses this logic when dispatching jobs.)
- `tests/` — the suite: the real runner driven against fake
  IMAP/SMTP servers and a fake NATS broker.
- `RUNBOOK.md` — step-by-step instructions (written for a 5-year-old):
  cloning, pushing, cutting a release, installing, sending a job.
- `examples/extensions/` — the example senses: 27 folders ship,
  from the lab-results sense to the IDS feeds; 24 of them are the
  pinned catalog in `docs/extensions.md`.

## Setup

Setup lives in [INSTALL.md](INSTALL.md): the three install
paths (Docker, pip, release binary) and the full first-run
walkthrough — dedicated mail account, app password, shared
secret, first job.

## How scripts run

Jobs carry a `script` (or `script_url`) plus an optional `interpreter`
list, e.g. `["bash"]` or `["pwsh", "-File"]`. The runner writes the
script to the job's work dir and runs `<interpreter...> script <args...>`.
Defaults: PowerShell on Windows, `sh` elsewhere; override per-install
with `default_interpreter` in config.json, per-job with `interpreter`
in the job (`send_job.py new --interpreter '["bash"]'`).

## Sending a job (any SI)

The runner is SI-agnostic: anything that can send email to the runner's
mailbox and sign the body can drive it — your SI of choice, a cron
script, whatever. The SI needs the `shared_secret` string from your
`config.json` — the random value the installer generated, not the
mailbox password. Then:

```bash
python3 cloud/send_job.py new --kind ping --secret <the-string>
# prints: subject line, blank line, signed body -> send as email to the runner mailbox

python3 cloud/send_job.py new --kind exec --script-file job.sh \
  --interpreter '["bash"]' --file data.csv=https://... --timeout 300 \
  --secret <the-string>
```

Or paste the string to your SI in chat — it composes, signs, and sends
the job message itself, and reads the result message when it arrives. Large files
are uploaded to cloud storage first; the job message carries the URLs.

Verify a result body:

```bash
python3 cloud/send_job.py verify --secret <the-string> result.txt
```

## Testing

**Watch before you trust.** The runner is fully inspectable — these flags
exist so you can audit everything it would do before it does it:

```bash
python3 runner/runner.py --config config.json --once --dry-run --verbose
# verifies signatures, prints what each job WOULD do, executes nothing,
# sends nothing, changes nothing (mail stays unseen)
```

| Flag | What it does |
|------|--------------|
| `--dry-run` | Verify and describe; execute nothing, send nothing |
| `--workers COUNT` | Concurrent job executions (default 1) |
| `-v`, `--verbose` | Decision lines: every poll, ingest, wake-gate, judge and board call, with reasons. `-vv` adds more; `--quiet` turns them off. Also a config key: `"verbose": true` |
| `--pdb` | Drop into pdb on unhandled exceptions |
| `--no-send` | Execute, but log results instead of emailing them |
| `--once` | Single poll cycle, then exit |
| `--inspect {board,budget,job,redact}` | Read local Oracle state and exit; no mailbox |
| `--audit-report [--since 14d|48h]` | Summarize the security audit log and exit; no mailbox, read-only |
| `--posture` | Report the runner's security posture (exit 0/1/2) and exit; no mailbox |
| `--oracle` | Open a loopback chat with the Oracle in your browser. Does not poll mail. Turns are appended to `oracle-chat.jsonl` in the base dir (1 MiB, then one backup). See `CONTRIBUTING.md` (maintainer notes: the `--oracle` flag). |
| `--poll-interval SECONDS`, `--timeout SECONDS`, `--judge MODE`, `--dag-mode MODE`, `--oracle-mode MODE`, … | One-process config overrides: one flag per key, `config.json` untouched, and a flag beats a later config edit. The full map is in `--help` and `docs/configuring-oracle.md` |

`install.py` accepts the same flags and bakes them into the installed
service, so the agent on boot runs exactly what you tested:
`python3 runner/install.py --verbose --poll-interval 30`.

```bash
python3 -m unittest discover -s tests -t .
```

The suite drives the real runner code against fake IMAP/SMTP servers:
ping roundtrip, script execution, timeout kill, poison-job rejection,
signature/tamper rejection, any-sender acceptance.

End-to-end without your SI:

1. `python3 cloud/send_job.py new --kind ping --secret <the-string>` → copy the
   subject + body.
2. From any email account, send it to the
   runner mailbox.
3. On the target machine: `python3 runner.py --config config.json --once`.
4. A result message with `stdout: "pong"` should arrive in the mailbox
   (or at the job's `reply_to` address, if you set one).

## Security notes

- Honest threat model: [docs/threat-model.md](docs/threat-model.md) —
  the long form of the warning at the top of this file. Its
  companion [docs/security-gaps.md](docs/security-gaps.md) covers
  what the defaults don't protect you from, and the order to turn
  things on.
- Industry map: [docs/industry-map.md](docs/industry-map.md) — five years
  of commercial detection (2021–2026) read honestly against this project,
  sorted by local footprint cost.
- The mailbox app password sits in **plaintext** in config.json
  (your explicit choice: throwaway account, fresh box). Anyone
  holding it gets mailbox access. The HMAC shared secret is a
  separate value — anyone holding *it* can sign jobs. Don't use
  this setup with an account you care about.
- Every job is HMAC-SHA-384 signed; over email the signature is
  the only gate (a credentialed transport adds its own — see
  *Why email?*, above). Timestamp window and replay protection
  (seen-set) are enforced before anything runs; the sender
  address is logged but never trusted.
- Jobs are also **encrypted by default**: `send_job.py` wraps the
  signed body in a ChaCha20-Poly1305 envelope keyed from the
  shared secret, so the mailbox provider — and anyone else who
  can read the transport — sees ciphertext, not your script or
  its output. Results mirror the job: encrypted job, encrypted
  result. `--cleartext` sends the plain signed body instead
  (deliberately, never silently), and a runner that receives a
  cleartext job logs that it arrived in clear text. One honest
  limit, stated wherever this is described: there is **no
  forward secrecy** — the key derives from the static shared
  secret, so a compromised secret exposes every recorded
  encrypted job and result, past and future.
- Delivery is at-least-once: if a result email fails to send, the job
  stays unseen and will be re-executed next cycle. Make jobs idempotent
  or check the seen behavior accordingly.
- Size caps: `max_job_bytes` (default 4 MiB) bounds the raw mail before
  the signature is even checked; `max_script_bytes` (default 1 MiB)
  bounds the script after verification. Either rejects through the
  normal reject path; `0` means unlimited. A negative or non-integer
  value is a startup config error.
- Optional hardening controls (all off by default): see [SECURITY.md](SECURITY.md).

## Not built

The list is [FUTURE.md](FUTURE.md).

## Status

What ships today is what's described above: the agent, the Oracle
(opinions, self-learning, remediation), four job transports, and
the example senses. The current release is in
[CHANGELOG.md](CHANGELOG.md); the version number lives in
`pyproject.toml`, and the message field `"v"` is a different
number — the protocol's version and the release number move on
separate tracks.

Current-state facts worth knowing: `config.json` hot-reloads poll
interval, workers, timeouts, output limits, and max job age (a
`security` mode change still needs a restart). A Thunderbird-style
OAuth sign-in is shipped for the mailbox. PowerShell jobs stage
as `script.ps1`. Release files carry Sigstore build provenance
(`docs/verification.md`).

## Mirrors

- GitLab: https://gitlab.com/pigeon-home/homing-pigeon
- SourceForge: https://sourceforge.net/projects/homing-pigeon/
- Randall Munroe: [xkcd 568](https://xkcd.com/568/) "You'll never find a programming language that frees you from the burden of clarifying your ideas." (Except with English + SI + a long context paragraph clarifying your ideas => the cycle begins again)
- https://pigeon-home.com/
