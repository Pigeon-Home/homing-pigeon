# FAQs

## What can I actually use this for?

Anything with a processor, a job worth doing, and a network that is
slow, flaky, or absent. A few that show the shape:

**Plug in a soil monitor and hand the SI the whole job.** Install the
runner on a Raspberry Pi in the barn and the software side is done:
the installer detects the Pi and applies Pi Light by itself, with no
model to download. Wire in a soil-moisture sensor and give your SI a
broad task — "read this sensor every hour and tell me when the beds
need water." The SI writes the driver, runs it, reads the failure,
fixes it, and iterates, all through signed jobs. A cellular link that
drops for a day just means the jobs wait in the mailbox. Same can be
done with fermentation, growing rooms, and small bioreactors. 
Homebrewers, mushroom and microgreen growers, cheesemakers, and the
technicians in an agriculture or food-science lab can let an SI
iterate on the scripts that hold a temperature or a humidity band.

**Field equipment across an air gap.** The file transport turns the
protocol into an auditable sneakernet. `send_job.py new --to-file`
writes a signed, encrypted job to a file; someone carries it on a USB
stick into a watched folder on a machine with no network at all; the
result lands in the outbox as `<job_id>.result.txt` and rides back the
same way. Vehicle and generator diagnostics, maintenance and logistics
boxes in disaster zones or remote sites: with `max_result_view` set to
`attested`, only pass/fail, digests, and signed claims leave the box,
never the raw logs (`docs/extend/transports.md`, PROTOCOL.md section 9).

**A data clean room, lite.** A researcher's script runs against data
that never leaves the machine, such as a clinic's records or a lab's
unpublished results. They get attestations ("exit zero", "no secrets
in the output", an output digest) and, with a local model, plain-
English `ask` answers that are truncated, secret-scanned, and redacted
before they are sent. The owner's ceiling caps what any job can see,
and a per-job privacy budget caps how much it can learn by asking
(PROTOCOL.md sections 9-11).

**Make a new model prove itself on real hardware.** Put a servo board
on a Pi and tell the SI to balance an inverted pendulum. It has to
write the firmware, flash it, read the sensors, and debug the hardware
into motion through signed jobs, with the results coming back each
round. It is the fastest honest benchmark there is for whether a model
can operate, not just talk.

**Camera traps and field recorders.** A Pi on a trail camera or a
bioacoustic recorder runs a small classifier as its own sense: an
extension (`docs/extend/extensions.md`) that declares signals such as
`animal_detected` or `low_confidence_frame` and files them signed
with the Oracle. Only the labels and a digest leave the box; when a
frame is a toss-up, your SI sends one more job for just that frame
instead of pulling the whole card. A runner that asks the cloud its
own free-form question ("lynx or bobcat?") is the Mirror idea in
`docs/project/future.md`, not built yet.

And for the box that cannot decide on its own: with protocol version
2 turned on, a Pi Light runner can send the question it would have
asked a model up to a laptop or a cloud SI, and the answer rides back
on the result without ever holding the job past its deadline (30
seconds at most; `docs/ietf/draft-homing-pigeon-v2-00.md`).

## Isn't this just remote code execution by email?

Yes, and it says so in the first lines of the README. A runner runs
whatever a correctly signed job tells it to, as the user it runs
as. So did every CI runner, SSH daemon, and remote-management agent
before it. The honest question is what stands between the mailbox
and the shell. Three things: a SHA-384 HMAC under a secret that
never travels in email, a replay and age check (`issued_at` within
`max_job_age_sec`, default one hour, plus a seen-set of job ids), and
an AES-256-GCM envelope keyed from the same secret, so a mailbox
reader cannot read the job. Nothing executes before the signature
verifies. Everything past that is opt-in containment: the
Oracle's `judge`, a bubblewrap sandbox, and AppArmor and SELinux
templates in `docs/security/hardening/`. Run it as a locked-down user
on a box you can wipe (`docs/security/threat-model.md`).

## Why not SSH, Tailscale, or a self-hosted CI runner?

Use them if you can. They are good. This exists for the case where
the thing giving the orders is a cloud assistant that can send a
message but cannot open a socket to your machine, hold your keys, or
sit on your tailnet. Email is the one channel nearly every assistant
already has. The runner only polls outward, so there is no inbound
port to expose. What you also get over a bare shell: the job format
is a signed runbook rather than a free-form session, the result comes
back signed, and the Oracle can watch each run and cap what the SI
sees (`max_result_view`). If you can give your assistant SSH, you
probably don't need this.

## What happens if the shared secret leaks?

Whoever holds it can run jobs, full stop. Treat it like a root
password. Rotate it with `docs/use/secret-rotation.md`. Two honest
limits: there is no forward secrecy at the envelope layer unless the
transport provides it, so a leaked secret exposes captured traffic
that used it. And revocation is manual, since there is one shared
secret rather than per-sender keys. Asymmetric signing would fix
the second and is sketched in `docs/design/asymmetric-signing-design.md`.

## Is this safe to run on my main machine?

No, and we'd rather you hear it from us. Run it on a spare box, a VM,
or a Raspberry Pi, under a dedicated user, with `max_result_view` on
`attested` if the data matters. Turn on the sandbox and the OS
profiles if the box has anything to lose. The defaults favor "it just
works"; the posture table in the README (`just run it`, `eyes open`,
`lockdown`) is how you choose otherwise.

## How often does the Oracle refresh what's happening on the system? Does it poll, or does a signal wake it up?

Short answer: it polls -- and a local signal can also wake the
model. The base rhythm is polling: nothing interrupts the runner,
and the model is not running all the time. The deterministic code
around the model does the watching on the runner's poll cycle --
every 20 seconds by default (`poll_interval_sec`). The model
itself only runs when it is asked a question, when a configured
trigger decides a human gets paged, or when a local signal passes
the wake gate described below.

How it works, in order:

1. **Every poll cycle**, the runner takes one cheap look at the
   box (unless the operator turned it off with
   `inference.watch_system=false`; on by default): canary tripwire
   files are re-hashed and diffed against their snapshot; on
   Windows, a bounded tail of the Event Log and a diff of the
   registry persistence locations (autorun keys, services); on
   any platform, firewall posture and antivirus posture; plus a
   built-in resource monitor whose threshold crossings become
   security events.
2. **If something tripped, the watch files the alert itself** --
   it lands in the same senses store as external sensor alerts.
   It does not need the model awake to notice, and it is filed
   before the page check runs, so a trip since the last poll can
   page on that same cycle.
3. **Paging is deterministic, not the model's idea.** A trigger
   evaluation runs once per poll (the DRI playbook: e.g. a fused
   sensor score crossing a threshold, a high-severity alert).
   If a trigger fires and a channel is configured, it pages the
   operator. This is off by default and entirely rule-based.
4. **Signals arrive two ways, and one of them can wake the
   model.** A remote sensor sends its alert as a signed email
   job: it lands in the runner's mailbox and is picked up on the
   next poll, verified like any other job, and filed. A sensor
   on the *same box* -- a built-in sense or an owner's
   extension -- skips the mailbox: its signed envelope goes
   straight to the runner's local inbox (a watched folder, or a
   loopback socket) and through the same ingest core, usually
   within about a second. Either way the alert is filed; the
   local path adds the **wake gate**: a deterministic check
   (severity at least high, first occurrence of that sensor +
   signal inside the cooldown -- `local_wake_cooldown_sec`,
   default 900 -- and only one wake at a time) that may start
   the model to write a short assessment, appended to
   `oracle-briefs.jsonl`. The wake never takes an action; it
   writes a brief. With no inference configured the brief is
   the deterministic fallback, and in deterministic (Pi Light)
   mode no model is ever loaded: the gate files its brief from
   the record alone.
5. **When the owner asks the Oracle a question** (the loopback
   chat or a signed query by email), the context handed to the
   model is assembled at that moment: recent retained jobs, the
   runner's log tail, and a fresh run of the same watches --
   canary state, Event Log tail, registry diff -- so the answer
   describes the box as of the ask, not as of some older
   snapshot. The watch sections tell the model what changed
   and, just as importantly, say "unreadable" when something
   cannot be read, rather than reporting it clean.

One sentence version, for when someone asks quickly:

> "It polls every 20 seconds, and a serious local signal can
> also wake it -- the watching is ordinary deterministic code;
> the model runs only when you ask it something or the wake
> gate lets a signal through; a page is a rule firing, no
> model involved; and that's deliberate: a watcher that only
> runs when an LLM feels like it isn't a watcher."

## If the default latitude is repair, can't a malicious job use repair to get itself run?

Short answer: no — repair never grants a sender anything they
didn't already have, and it never waves a job past the judge.

The chain, in order:

1. **Admission comes first.** The opinion layer only ever sees
   jobs that already passed the HMAC signature check. An
   unsigned job never reaches it. So the only jobs repair can
   touch come from key-holders — senders who could already
   send any job they want, written correctly.
2. **The fix adds no capability.** The one mechanical repair is
   narrow: an absent interpreter is replaced by the platform
   default, and only when the script's shape does not
   contradict that interpreter — a neutral shape fits; a
   contradicting tell (a POSIX script under a Windows
   default, say) stops the repair. The result is a job the
   sender was always authorized to send — repair just
   absorbs their typo.
3. **Judgment runs on both sides of repair.** The job as
   received is judged first; a repaired job then goes back
   through the judge and the key policy before it executes
   (`oracle_opinion_repair: rejudge`, the default). The
   `refuse` setting instead degrades a repair finding to
   advise: the fix is proposed on the result, not applied,
   and the job runs exactly as received.
4. **The opinion never claims to detect malice.** Its question
   is "will this run here?", not "is this good?" Malice is
   carried by the layers that always carried it: the
   signature, the judge, the post-run findings, remediation's
   tripwires. A bad job stopped only because its interpreter
   was misspelled was stopped by accident, and an accident is
   not a control.
5. **The owner holds the ceiling.** `oracle_opinion_mode` is
   both the default latitude and the owner's cap: set it to
   `diagnose` and nothing on the box is ever repaired, whatever
   a job requests. A job may narrow its own latitude, never
   widen it. The model-formed tier stays off unless the owner
   separately enables `oracle_opinion_model`.

Every repair that does happen is recorded on the result —
what changed, and the digest of the job as received — so
"what ran versus what was sent" is always answerable. The
honest edge is polyglot scripts, valid under two interpreters
with two meanings: where a shape tell *contradicts* the
platform default, no repair happens — and where the tier-1
evidence itself is inconclusive, the system does not
improvise. It diagnoses, and talks.

## Why is the protocol bound to email — what other transports do SI providers actually support?

Short answer: email is the one channel every major cloud SI
provider already reaches out of the box. The binding is a fact
about the ecosystem, not a preference.

Run down the alternatives a sender-side SI actually has:

1. **Email is universal.** Every major provider's connector
   set includes sending and reading mail. A signed job needs
   no new account, no API registration, and no setup on the
   sender's side beyond the shared secret — the pipe is
   already there before Homing Pigeon enters the picture.
2. **HTTPS and webhooks are not universal.** Some ecosystems
   offer general HTTP calls; others do not. They also invert
   the connection: an inbound webhook needs the agent to
   expose a publicly reachable endpoint and accept
   connections from the internet. This design deliberately
   has the agent dial out and poll, so on the email binding
   the box needs no listening port at all — the one
   listening transport, DTLS, is off unless the owner
   enables it, and the loopback listeners are local only.
3. **Chat platforms are partial and gated.** Slack, Telegram,
   and their kin show up as human chat integrations in some
   ecosystems only. Each is gated on its own account and API
   registration, and none is offered by every provider — a
   binding to any of them would exclude the senders who
   cannot reach it.

So the protocol is married to email because email is what
the providers have in common. That is a statement about
today's connectors, not a law of the design: the protocol's
messages are transport-agnostic, and where another pipe
exists the same signed jobs can ride it unchanged — the
runner already carries a watched-folder transport and a
NATS transport as extensions, with email simply the default
binding.

## Why doesn't the protocol use PGP or S/MIME encrypted email?

Two reasons, either one sufficient.

A cloud SI has no mail client. It has a connector with a
send function, and mail-layer crypto would require every
provider's connector to implement PGP or S/MIME, key
management included — a surface that does not exist, on
exactly the side of the wire the protocol cannot control.

And it is not needed. Confidentiality belongs to the layer
that can actually provide it: a job is encrypted as an
object, under a key derived from the shared secret, and
that encryption is on by default. Each mail hop also runs
over TLS, which the draft requires of the email binding.
`mail_tls_required: false` relaxes certificate verification
on that hop. It does not turn the hop into the
confidentiality property: the mailbox provider can still
read a cleartext job, verified TLS or not. The mail system
is transport, not a security layer.

For the record, the protocol also permits the other
arrangement: an implementation MAY support PGP on the
mail binding (the draft, Section 5). It is not required,
and the reference implementation does not do it, because
the job encrypts itself (the draft, Section 16).

## Why does the protocol use no public-key (asymmetric) cryptography?

Short answer: it has no strangers to introduce. Public-key
cryptography exists to establish trust and keys between
parties who share nothing. The two endpoints here already
share a secret, installed out of band — so authentication
is HMAC-SHA-384, and confidentiality is AES-256-GCM
under a key the shared secret derives. Symmetric, end to
end.

Asymmetric machinery would add nothing and subtract
something. RSA and elliptic-curve schemes fall to a large
enough quantum computer, including retroactively against
recorded traffic. The symmetric constructions do not: the
generic quantum speedup is answered by key size, and the
shared secret's floor is 128 bits, with 256-bit generation.

The one deliberate exception proves the rule. The DTLS
binding uses ephemeral Diffie-Hellman to get
forward secrecy, and the draft's security considerations
say plainly that recorded sessions of that binding do not
share the core protocol's quantum posture. Post-quantum
key exchange would close that too — at the cost of asking
every provider to ship it, which, per the entry above, is
asking a real lot.

## Is it safe to use the same shared secret for the HMAC signature and the job encryption?

Using the one shared secret for both is not insecure. The
AES key is not the secret itself. It is an HKDF output
under a fixed info string and a fresh nonce, and neither
construction's output is fed into the other. That
composition holds if HMAC-SHA-384 is a pseudorandom
function, which is the usual assumption for this kind of
reuse. The real cost is the one the draft already states:
a compromised secret opens both the signatures and every
recorded envelope.

## Why doesn't the runner protect a beginner from installing this on the wrong computer?

Short answer: because every SI vendor claims their model
understands context and acts responsibly, and this project takes
them at their word. The runner is the dumb end of the wire on
purpose. If the smart end can't handle a novice and a family PC,
that is the vendor's failure, not a gap in the installer.

The runner verifies a signature and executes a job. That is all it
knows how to do. The intelligence sits on the other side: the SI
composing the job is also the one reading the user's intent,
holding the context of who they are, and quoting this project's
documentation back to them. The first line of the README says this
tool hands full administrative control of the machine to whoever
holds the shared secret. `docs/security/safeguards.md` and
`docs/security/personal-documents-warning.md` say what that means on a
shared or personal computer. Those warnings are written for the
SI as much as for the human.

So the bet is explicit. An unexperienced user is going to get hold
of this and break their own computer; that is fine, and it is how
most of us learned. Every vendor sells a model that would notice,
say so, and recommend a spare box or a VM. An SI that reads the
README's first line and helps a novice install onto like a family PC
without a word has failed at the exact thing it is marketed for.
No runner-side guardrail should have to cover for that, and
building one would mean conceding the claim is false.

That is what makes this project a clean test of the claim: a
novice, a shared machine, a README that says what it says. Point
a model at it and find out. The warnings are placed where an
assistant will read them -- the README, `docs/security/safeguards.md`,
`AGENTS.md`, and the personal-documents check that prints at
install and at startup. The check is a speed bump, not a
protection. It exists so the assistant and the human both see it.
What happens next is on them -- and on the vendor who said their
model could handle it.

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854
