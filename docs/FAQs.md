# FAQs

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
   has the agent dial out and poll, so the box needs no
   listening port at all.
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
that encryption is on by default; each mail hop runs over
TLS as a requirement, not an option. The mail system is
transport, not a security layer.
