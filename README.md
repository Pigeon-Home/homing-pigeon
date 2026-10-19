# Homing Pigeon

**Works with Muse, Grok, ChatGPT, Claude, Gemini, Copilot, etc.**

> ⚠️ **USE AT YOUR OWN RISK.** This tool hands **full administrative control**
> of the machine to whoever holds the shared secret. It reads inbound messages
> and executes what it finds — blindly, as a privileged user. It can install
> software, read, files, add users, pivot to your network.
> PROTOCOL.md before you deploy it.

Your cloud SI is smart, but it can't touch your computer. Homing Pigeon
fixes that: tell your SI to complete a task and it will do it on your
machine. The results return so that your SI can iterate — run the tests,
read the failure, fix, repeat. From your phone or anywhere.

Install the Homing Pigeon agent/runner on your system. It will prompt
for login credentials to an email address, the default. The agent bares
similarity to GitHub self-hosted runners.

Then try this prompt in your cloud SI, it should return in less than 30 seconds.

```
Send an email to YOUR_RUNNER_EMAIL
Use this protocol: https://pigeon-home.com/PROTOCOLv1
Shared Secret: "YOUR_SECRET_STRING"
I have a Windows computer. Retrieve the system clock from it and display it here.
```
IETF Homing Pigeon Draft: https://github.com/Pigeon-Home/homing-pigeon/blob/main/docs/ietf/draft-homing-pigeon-00.md

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
real machines. So instead we will point one at a disposable box, give
it a signed channel, and let it do tasks from start to finish. The
upside is an assistant that operates, not just advises. If the
capability is real, there is very little downside to exercising it.

A new model claims to be good at something — robotics, automation,
data work? Point it at a box and find out.

It belongs to the same family as GitHub self-hosted runners, VS Code
Remote tunnels, and Tailscale — legitimate tools for administering your
own hardware remotely. And like all of those, its power is the point,
not an accident: whoever holds the shared secret has full control of
the machine. That's exactly why this project states its threat model
plainly instead of burying it. Keep the secret like a password, use a
throwaway account, and only ever install the agent on machines you own
and operate.

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

**Why email?** Because it's the only transport with all five properties
on day one: reachable from anywhere, outbound-only polling (no inbound
ports — NAT-proof), at-least-once delivery, and
zero infrastructure to operate. The protocol does not care about the
pipe, but email is the only transport wired in today. Anything else
is in [FUTURE.md](FUTURE.md).

**Runbooks, not prompts.** The SI doesn't chat about the task — it ships
a runbook: deterministic steps, each with a check that proves the step
worked. The runner executes it and reports back what actually happened,
and that feedback goes into the next runbook. Each cycle is a little
smarter than the last, because the failures are data. If you've ever
debugged something by running it, reading the output, and trying again
with what you learned — that's the whole product. The SI is just the
part that writes the next attempt.

## The Oracle: answers, not output

The **Oracle** is a black box the SI can question but never inspect.

The SI asks "did the tests pass?" or "does the output contain secrets?"
and gets back HMAC-signed *attestations*: proofs about the output that
reveal nothing else. It's the zero-knowledge shape applied at the trust
boundary — prove things about your data without showing your data. The
raw output never leaves your disk.

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
   The SI learns answers. Never the raw output.
```

Queries are declared upfront (no adaptive probing), each job gets a
privacy budget bounding total leakage, and the disclosure ceiling is
set by *you* in config — never by the SI.

Your machine runs two roles in one box:

```
+-----------------------------+-----------------------------+
| RUNNER (faces the SI)        | ORACLE (faces you)           |
+-----------------------------+-----------------------------+
| polls the mailbox            | reviews every job            |
| verifies HMAC + key policy   | before it runs               |
| judge: the policy gate      | fuses sensor alerts          |
| executes jobs, confined     | watches resources            |
| answers queries with        | pages you when a             |
| attestations -- never       | threshold trips              |
| raw output                  | never remediates             |
+-----------------------------+-----------------------------+
```

The runner does what the SI asks. The Oracle watches what happens
and tells you about it.

### Operating modes

Five knobs set the posture. They are independent — these are three
coherent postures, not the only combinations.

```
  knob                  just run it  eyes open    lockdown
  ------------------    -----------  ---------    --------
  judge                 off          advisory     enforce
  sensors               off          on           on
  resources             on           on           on
  dri                   off          on           on
  max_result_view       full         attested     attested
```

**just run it** (the defaults). Runner: executes any signed job,
answers queries with full output. Oracle: reviews every job anyway
(notes ride in the result), logs resource pressure. Quiet — nothing
pages, nothing blocks.

**eyes open** (recommended). Runner: executes, attaches the policy
verdict to each result, answers queries with attestations only.
Oracle: reviews, fuses sensor alerts, pages you when a trigger
trips. Still takes no action itself.

**lockdown**. Runner: refuses anything the policy rejects; the SI
gets attestations. Oracle: same as eyes-open, and every refusal is
page-worthy. Nothing moves unless the policy allows it.

The Oracle ships two confinement capabilities:

- **Local inference.** Point it at a model running on your own box and
  the SI can `ask` questions in plain English — *"why did the tests
  fail?"* — answered locally, with only the answer crossing the
  boundary. The endpoint must be loopback (fail closed), and every
  answer is truncated, redacted, and secret-scanned before it's sent.
  The SI gets useful answers, and your raw data never leaves the machine.
- **Execution confinement.** Two different checks, both shipped.
  Set `workspace_root` and the Oracle snapshots file metadata outside
  that folder before and after the job, then attests
  `confined_to_workspace`. That one is a snapshot, not a sandbox. The
  walk stops at 50000 files. Separately, on Linux, set
  `security.modes.confinement` to `enforce` and the job runs inside
  bubblewrap (`bwrap`): `/usr` read-only, no network, and only the job
  workdir writable. It is off by default. If `bwrap` is missing, or the
  machine is not Linux, the job runs normally and the audit log records
  the fallback. See SECURITY.md.

Full spec in PROTOCOL.md (sections 9–12). Oracle fields are optional
members of a `"v": 1` message. They are not a separate message version.

## Extending the agent: your own senses

Extensions let you teach the agent a new sense without forking it.
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
- `TRANSPORTS.md` — email is the only transport in the runner.
  The rest of that file is design notes, not code.
- `SAFEGUARDS.md` — how to run this without getting burned: the
  non-negotiables, containment, the Oracle as a safeguard, and what
  to do when something goes wrong.
- `runner/runner.py` — the agent. Polls IMAP, verifies, executes,
  replies via SMTP. No dependencies beyond Python 3.9 stdlib.
- `runner/install.py` — installs it as a boot-start service: systemd
  (Linux), launchd (macOS), cron @reboot (FreeBSD), Scheduled Task
  (Windows).
- `runner/config.example.json` — copy to `config.json` and fill in.
- `cloud/send_job.py` — cloud-side helper: builds signed job messages,
  verifies result messages. (Your SI uses this logic when dispatching jobs.)
- `tests/test_runner.py` — end-to-end tests with fake IMAP/SMTP servers.
- `RUNBOOK.md` — step-by-step instructions (written for a 5-year-old):
  cloning, pushing, cutting a release, installing, sending a job.
- `examples/hello-world.json` — unsigned example job payload.

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
| `--workers N` | Concurrent job executions (default 1) |
| `--verbose` | Debug logging: every accept/reject decision |
| `--pdb` | Drop into pdb on unhandled exceptions |
| `--no-send` | Execute, but log results instead of emailing them |
| `--once` | Single poll cycle, then exit |
| `--inspect {board,budget,job,redact}` | Read local Oracle state and exit; no mailbox |
| `--audit-report [--since 14d|48h]` | Summarize the security audit log and exit; no mailbox, read-only |
| `--posture` | Report the runner's security posture (exit 0/1/2) and exit; no mailbox |
| `--oracle` | Open a loopback chat with the Oracle in your browser. Does not poll mail. Turns are appended to `oracle-chat.jsonl` in the base dir (1 MiB, then one backup). See `CONTRIBUTING.md` (maintainer notes: the `--oracle` flag). |
| `--poll-interval SEC`, `--timeout SEC`, `--max-output-bytes N` | Override config |

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
  what this is, what it isn't, and what "anyone holding the shared
  secret effectively owns the box" means for how you deploy it. Its
  companion [docs/security-gaps.md](docs/security-gaps.md) covers
  what the defaults don't protect you from, and the order to turn
  things on.
- Industry map: [docs/industry-map.md](docs/industry-map.md) — five years
  of commercial detection (2021–2026) read honestly against this project,
  sorted by local footprint cost.
- The runner is a **full-trust execution environment**: a valid signed
  job message means arbitrary code as a privileged user. The app password sits in
  **plaintext** in config.json (your explicit
  choice: throwaway account, fresh box). Anyone holding it gets mailbox access.
  The HMAC shared secret is a separate value — anyone holding *it* can sign jobs.
  Don't use this setup with an account you care about.
- Every job is HMAC-SHA-384 signed; the signature is the sole
  authentication gate. Timestamp window and
  replay protection (seen-set) are enforced before anything runs; the
  sender address is logged but never trusted.
- Delivery is at-least-once: if a result email fails to send, the job
  stays unseen and will be re-executed next cycle. Make jobs idempotent
  or check the seen behavior accordingly.
- Size caps: `max_job_bytes` (default 4 MiB) bounds the raw mail before
  the signature is even checked; `max_script_bytes` (default 1 MiB)
  bounds the script after verification. Either rejects through the
  normal reject path; `0` means unlimited. A negative or non-integer
  value is a startup config error.
- Optional hardening controls (all off by default): see [SECURITY.md](SECURITY.md).
  The Oracle is implemented: result policies, signed attestations,
  and a query budget, so a cloud SI learns *answers* about your output
  without ever seeing it.

The download version and the message field `"v"` are different
numbers. The runner is 3.7.x and speaks `"v": 1`.

## Not built

The list is [FUTURE.md](FUTURE.md).

## Status

The current release is in [CHANGELOG.md](CHANGELOG.md). The download
version is the number in `pyproject.toml`.

Still true from earlier releases. Any sender may submit a job, and the
HMAC is the only gate. `config.json` hot-reloads poll interval,
workers, timeouts, output limits, and max job age. A `security` mode
change still needs a restart. Thunderbird-style Google sign-in is
shipped. PowerShell jobs stage as `script.ps1`. Release binaries carry
Sigstore build provenance. The suite is
`python3 -m unittest discover -s tests -t .`.

## Mirrors

- GitLab: https://gitlab.com/pigeon-home/homing-pigeon
- SourceForge: https://sourceforge.net/projects/homing-pigeon/
- Randall Munroe: [xkcd 568](https://xkcd.com/568/) "You'll never find a programming language that frees you from the burden of clarifying your ideas." (Except with English + SI + a long context paragraph clarifying your ideas => the cycle begins again)
- http://pigeon-home.com/
