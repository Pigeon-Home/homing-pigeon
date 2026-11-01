# Homing Pigeon

Works with Muse, Grok, ChatGPT, Claude, Gemini, Copilot, or any assistant that can send a message.

> ⚠️ **USE AT YOUR OWN RISK.** Installing this application hands full administrative
> control of the system to whoever holds the shared secret. The holder
> can install software, read files, add users, and pivot to your network.

Your cloud AI (called the SI throughout this repo) is smart, but it
can't touch your computer. Homing Pigeon gives it a signed channel to one: ask for a task and it runs on your machine, and
the results come back so the SI can iterate. Run the tests, read the
failure, fix, repeat, from your phone or anywhere.

It works like a GitHub self-hosted runner. A small program on hardware
you own picks up signed jobs from a mailbox you control and runs them.
By default nothing listens on an external interface: the runner
only polls outward, so it works behind NAT with no open ports. The
DTLS binding, off unless enabled, is the one network listener, and a
loopback-only port (127.0.0.1:39271) takes this box's own sensor
signals.

Setup walks you through connecting a dedicated mailbox. The
recommended path is a browser sign-in, so the account password never
lands in config; an app password is the
other choice.
Another provider works by setting `imap_host` and `smtp_host` in
`config.json` with an app password.

Then try this prompt in your cloud SI, it should return in less than 30 seconds.

```
Send an email to YOUR_RUNNER_EMAIL
Use this protocol: https://pigeon-home.com/PROTOCOLv1
Shared Secret: "YOUR_SECRET_STRING"
Run a job that retrieves the system clock and then display it here.
```
IETF Internet-Drafts: ([docs/ietf/STATUS.md](docs/ietf/STATUS.md))
- Homing Pigeon v1: https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon/
- Homing Pigeon v2: https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon-v2/

**No mailbox yet?** `python3 runner/runner.py --config config.json
--local-test` runs the whole loop in process: you play the SI in a
terminal chat, a local model (Ollama on loopback, which the installer
sets up) answers, and nothing is emailed. See
[docs/use/local-si-test.md](docs/use/local-si-test.md).

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
  it does the head-scratching. Let the SI build a robot.

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
watched folder, core NATS, a direct DTLS session binding and the
hosted HTTPS queue ship alongside email) — but email
stays the default; a credentialed transport adds
its own required gate beside the signature, which makes it the
more secure option even though it is not the default. (A
sensor on the same box also delivers its signed alerts directly,
by local inbox or loopback socket: alerts, not jobs.) Want another
pipe? Transports are extensions, and the ones we'd love to see are
sketched in [docs/project/future.md](docs/project/future.md).

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
  Cloud SI                                  Your machine
  --------                                  ------------

  "Did the tests pass?" --signed-------> +-----------------+
                                         | The Oracle      |
  "Any secrets in there?" -------------> |                 |
                                         | output stays    |
                                         | on your disk    |
  +------------------------+             |                 |
  | signed attestation     | <--signed-- | answers only    |
  | { exit_zero: true,     |             | what policy     |
  |   no_secrets: true }   |             | allows          |
  +------------------------+             +-----------------+

  The SI learns what your ceiling allows.
```

Queries are declared upfront (no adaptive probing), each job gets a
privacy budget bounding total leakage, and the disclosure ceiling is
set by *you* in config — never by the SI.

Your machine runs two roles in one box:

```
+------------------------------+------------------------------+
| RUNNER (faces the SI)        | ORACLE (faces you)           |
+------------------------------+------------------------------+
| polls the mailbox            | watches jobs as they run;    |
| verifies HMAC + key policy   | its opinions ride results    |
| judge: an opt-in gate        | fuses sensor alerts          |
| executes jobs; cage opt-in   | watches resources            |
| answers queries at the       | pages you when a             |
| ceiling you set -- the       | threshold trips              |
| default is full output       | orders kills via remediation |
+------------------------------+------------------------------+
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
`docs/design/oracle-opinion-design.md`.

**Fixes mismatched jobs, never silently.** A job that asks for `bash`
but only needs `sh` is repaired and runs on a minimal system like
Alpine (BusyBox, no bash); a job that really needs bash or PowerShell
is left alone. Every repair is stated in the result.
[![minimal-userland](https://github.com/Pigeon-Home/homing-pigeon/actions/workflows/minimal-userland.yml/badge.svg)](https://github.com/Pigeon-Home/homing-pigeon/actions/workflows/minimal-userland.yml)

### Operating modes

Three parties appear below, always under the same names. **The SI** is
the cloud AI that sends jobs. **The owner** is you, the person who
installed this on the box and edits its `config.json`. **The Oracle**
is the part of the agent on the box that works for the owner: it
watches jobs, and pages the owner. The **runner** is the part that
executes what the SI sends.

Five owner-set knobs decide the posture. They are independent; these
are three coherent postures, not the only combinations. Each is a
choice about trust: how closely the Oracle watches, and how much the
box may refuse, is the owner's to pick per machine.

```
  knob                  just run it  eyes open    lockdown
  ------------------    -----------  ---------    --------
  judge                 off          advisory     enforce
  sensors               off          on           on
  resources             on           on           on
  dri                   off          on           on
  max_result_view       full         attested     attested
```

**just run it** (the config-file defaults): the owner trusts the
signer, so the box just works. The runner executes any signed job and
shows the SI full output. The Oracle still reviews every job (its
notes ride in the result) and logs resource pressure, but it never
pages the owner and never blocks a job. A fresh install sits one
notch tighter: on non-Pi hardware the installer applies the
`password-only` profile (judge `advisory`, view `attested`) unless
`--profile` names another or `--no-profile` is passed, and a
Raspberry Pi, or any install from the pi-light archive, gets
`pi-light`. See
docs/use/runbook.md Job 7.

**eyes open** (recommended): same trust, but the Oracle watches on the
owner's behalf. The runner executes and attaches the policy verdict to
each result, and the SI gets attestations only. The Oracle reviews,
fuses sensor alerts, and pages the owner when a trigger trips. This
posture is about seeing; any acting belongs to the remediation
reflexes below, which have their own switch.

**lockdown**: the box refuses what the policy rejects. The runner
refuses those jobs, the SI gets attestations, and the Oracle pages the
owner on every refusal. Nothing runs unless the policy allows it.

Two more dials stand outside the table. **Remediation**
(`remediation_mode`, default `deterministic`) watches each job
while it runs: on a closed list of tripwires — confinement
escape, a process storm past the ceiling, an undeclared
credential-store reference in something the job produced — it
kills the job's process tree, quarantines its outputs (moved,
never deleted; the owner releases them), refers suspect files to the
box's own antivirus for the antivirus's verdict, and files the
whole story with the DRI, which pages the owner when paging is on.
That happens in every posture above. `oracle` mode additionally
lets the local model order a kill for a lesser divergence;
`off` watches and records only, and the page is all that
happens. **The opinion latitude** (`oracle_opinion_mode`,
default `repair`) is the other dial — it is covered under
Opinions, above.

Confinement ships in two kinds, and they are not the same kind
of thing:

- **A snapshot is not a sandbox.** The workspace check compares
  file metadata in the workspace's parent directory (the
  workspace's siblings) before and after the run, then attests `confined_to_workspace`: it *detects* a job
  that reached outside, it does not prevent one. The walk stops
  at 50000 files, so a huge tree yields a partial snapshot and
  the log records the cap being hit. The key is `workspace_root`.
- **The sandbox** (Linux only) actually walls the job in:
  bubblewrap runs it with `/usr` read-only, no network, and only
  the job workdir (at `/work`) and a throwaway tmpfs `/tmp`
  writable. It is off by default. Under `enforce`
  a sandbox that cannot engage (no `bwrap`, user namespaces
  blocked, not Linux) refuses to start the runner; one that
  breaks after a good start falls back loudly and the audit log
  records the fallback. The key is `security.modes.confinement`
  set to `enforce`. See SECURITY.md.

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
running. See `docs/oracle/configuring-oracle.md`.

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
`docs/design/oracle-opinion-design.md`. Measured on a real rig in
deterministic mode: 1,967 of 2,248 reconciled calls right (87.5%), 0 lessons, every
miss a job that simply ran `exit 3`, which leaves no fact for a
model-less Oracle to learn ([live examples](docs/use/live-examples.md)).

Full spec in PROTOCOL.md (sections 9–12). Oracle fields are optional
members of a `"v": 1` message. They are not a separate message version.

## Proven platforms

Every push runs one portable proof on a core set of legs, and the nightly run takes the whole corpus: native runners, distributions, other architectures, maker-board userspaces under QEMU, BSD virtual machines and administrator fat-fingers, and a leg fails unless every test ran and passed. The full table and the board notes are in [docs/use/platforms.md](docs/use/platforms.md).

[![platform-matrix](https://github.com/Pigeon-Home/homing-pigeon/actions/workflows/platform-matrix.yml/badge.svg)](https://github.com/Pigeon-Home/homing-pigeon/actions/workflows/platform-matrix.yml)

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

Nothing signs an extension's code, so the agent reads it against
the manifest before loading it: the manifest's `capabilities` list
(`network`, `listen`, `subprocess`, `native`) has to cover what the
code does, a transport's `entry` has to stay inside its folder,
every file has to compile, and no symlink, bidi control character
or reference to the runner's own state gets through. By default a
folder that contradicts its manifest is refused like a bad one and
the agent runs without it (`extension_review` turns that to
advisory or off; `--inspect review` shows the verdicts).

The example is a lab-results sense: it watches a folder where
experiment runs drop result files and files signals like
`experiment_finished` and `metric_threshold_crossed` when a run
lands. Full walkthrough: [docs/extend/extensions.md](docs/extend/extensions.md).

Every extension, sense or transport, also brings its own code for
the Oracle. On a box where a local model runs the Oracle, the
first time an extension runs, the agent gives the Oracle the
extension's installed code and fetches, in the background,
whatever its optional `sources.json` declares: its published
source, the upstream project it wraps, the specifications it
speaks. The release ships only the declarations and the build's
SHA-384 pins of what they name; the box fetches the sources and
refuses bytes that differ from a pin, and an entry nothing pins
waits until the owner allows it. A deterministic box (Pi Light)
has no model to read the material and makes no request for it
unless its owner turns the fetch on. The Oracle gets what is
pinned by default, and a written disclosure rule lets the owner
(or the author) withhold any of it
([docs/extend/extensions.md](docs/extend/extensions.md), "Sources").

## Layout

`PROTOCOL.md` is the wire protocol, `runner/` the code, `runner/extensions/` the shipped extensions, `docs/` the long shelf and `.github/` the CI. The file-by-file map is in [docs/project/layout.md](docs/project/layout.md).

## Setup

Setup lives in [INSTALL.md](INSTALL.md): the three install
paths (Docker, pip, release binary) and the full first-run
walkthrough — dedicated mail account, app password, shared
secret, first job.

**No spare machine?** One command puts a runner on a small machine
(about $2 a month on Fly, a few dollars on Hetzner or DigitalOcean)
in your own account, with the hosted
profile and nothing listening: [docs/use/own-cloud.md](docs/use/own-cloud.md).
Your account, your bill, your secret.

## How scripts run

A job carries a `script` and an optional `interpreter`; the default is PowerShell on Windows and `sh` elsewhere, and a `ping` first tells you which one a box has. Details are in [docs/use/scripts.md](docs/use/scripts.md).

## Sending a job (any SI)

Anything that can email the runner's mailbox and sign the body can drive it: your SI, a cron script, whatever, using `runner/cloud/send_job.py` and the `shared_secret` from your `config.json`. Commands and verification are in [docs/use/sending.md](docs/use/sending.md).

## Testing

The runner is fully inspectable, so audit what it would do before it does it, and run the suite with `python -m unittest discover -s runner/tests -t .`. The flags and the suite notes are in [docs/project/testing.md](docs/project/testing.md).

## Security notes

- Threat model: [docs/security/threat-model.md](docs/security/threat-model.md) and its
  companion [docs/security/security-gaps.md](docs/security/security-gaps.md).
- Industry map: [docs/project/industry-map.md](docs/project/industry-map.md) — five years
  of commercial detection (2021–2026) read honestly against this project,
  sorted by local footprint cost.
- Jobs are also encrypted by default: `send_job.py` wraps the
  signed body in an AES-256-GCM envelope keyed from the
  shared secret.
- `send_job.py --cleartext` sends the plain HMAC-signed body
  instead, and the runner refuses it unless started with
  `--allow-cleartext`. The shared secret is still required. One honest
  limit, stated wherever this is described: there is **no
  forward secrecy** unless it is provided by the transport layer.
- Execution is at-most-once, delivery at-least-once: a result is
  stashed under `<base_dir>/outbox/` and the job committed as seen
  before the first send; a send that fails is resent from the stash
  on later polls, never produced by a second run, and given up into
  `outbox/failed/` after a day (`--inspect outbox`; PROTOCOL.md
  section 5).
- Size caps: `max_job_bytes` (default 4 MiB) bounds a raw job mail
  before its signature is checked.
- Optional hardening controls (off by default, except the size caps
  above, which are on by default and turned off by 0): see [SECURITY.md](SECURITY.md).

## Questions people ask

The [FAQ](FAQ.md) is where the odd corners get answered.
Does the Oracle poll or get woken by a signal? Can a hostile job
talk its way into a repair? Why email, and why not PGP or public-key
signatures? Is one shared secret really safe for both signing and
encryption? What would you actually use this for? The hard ones come
right after the first two: isn't this just remote code execution by email, why not
SSH, what if the secret leaks, and is it safe on your main machine
(no, and it says why). Read it before you design around the protocol; the reasoning is more interesting than
the rules.

## Where it goes next

Plenty of ideas are already sketched in
[docs/project/future.md](docs/project/future.md), and some are
tempting. Imagine the owner approving a job with one tap before it
runs. Imagine signatures that need no shared secret at all, a
dashboard that lets you watch the Oracle think, a box that notices
its own firewall drifting or a patch going missing, or a Pi that
grows a real model the day an accelerator board arrives. Come pick
one, or add your own.

## Status

What ships today is what's described above: the agent, the Oracle
(opinions, self-learning, remediation), five job transports, and
the example senses. The current release is in
[docs/CHANGELOG.md](docs/CHANGELOG.md); the version number lives in
`pyproject.toml` and `runner/_version.py` (a test keeps them equal), and the message field `"v"` is a different
number — the protocol's version and the release number move on
separate tracks.

What a real box writes, and what 19,227 jobs on a test box
came to, is in [docs/use/live-examples.md](docs/use/live-examples.md).

Current-state facts worth knowing: `config.json` hot-reloads poll
interval, workers, the default job timeout, `max_output_bytes`, max
job age, the
result stash's retention and resend backoff, and the live keys
(`owner_instructions`, `inference`, `oracle_mode`, `verbose`,
`extension_sources`); a `security` mode change still needs a
restart. A Thunderbird-style
OAuth sign-in is shipped for the mailbox. PowerShell jobs stage
as `script.ps1`. Release files carry Sigstore build provenance
(`docs/security/verification.md`).

## Contributing

Welcome, and held to a high bar: standard library only, the protocol
doc changes with anything on the wire, and a security-sensitive change
says so. [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) has the rest.

## Mirrors

- SourceForge: https://sourceforge.net/projects/homing-pigeon
- GitLab: https://gitlab.com/pigeon-home/homing-pigeon
- Randall Munroe: [xkcd 568](https://xkcd.com/568/) "You'll never find a programming language that frees you from the burden of clarifying your ideas." (Except with English + SI + a long context paragraph clarifying your ideas => the cycle begins again)
- https://pigeon-home.com
- "I once saw a forklift lift a crate of forks. And it was way to literal for me" - Mitch Hedberg
- IETF datatracker, Homing Pigeon v1: https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon/
- IETF datatracker, Homing Pigeon v2: https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon-v2/
- CV: https://github.com/Pigeon-Home/homing-pigeon/blob/main/docs/archive/RESUME.txt
The security model — the gate, the key fences, the ceilings a job cannot raise, and the configuration rules — and the formal proof testing that checks it, property by property, are described in [docs/security/model-and-proof-testing.md](docs/security/model-and-proof-testing.md).
