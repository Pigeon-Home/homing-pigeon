# Homing Pigeon — project overview and campaign status

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

*Posted by Muse at the conductor's word, 29-Oct-2026. A snapshot;
the ledgers and the questions file are the living record.*

## The project

Homing Pigeon is a runner that sits on hardware the owner holds.
In the conductor's approved plain words: you let an SI like me
work on your machine, but only through a door you designed, with
rules you wrote.

A cloud SI sends the runner a signed job. The runner verifies it,
runs it, and returns a signed result. Jobs are protocol v1
objects: HMAC-SHA-384 authentication on every message, per-job
AES-256-GCM encryption on by default, cleartext refused unless
the owner starts the runner with the acceptance flag.

Email is the default transport because every SI can send email
and the runner only polls outward — no listener, no open port.
The protocol is the signed object, not the transport. Shipped
transports are extensions: email, file, NATS, DTLS, and a hosted
HTTPS queue. A transport's own credentials, where it has them,
are a second required gate beside the signature.

The local Oracle works for the machine's owner, not for the
sending SI: it reviews jobs before and while they run, keeps a
frozen pre-execution opinion that is scored against the outcome,
and the owner sets how much crosses the wire back — full output,
or a narrower view down to signed attestations. Pi Light is the
same runner with a deterministic Oracle and no local model.

Every secret has a public name, its fingerprint. The key
directory shipped in the current release line: a file the runner
reads, one entry per key — fingerprint, state, valid window,
never the secret — and every door refuses a key whose state says
so, DTLS resumption tickets included.

The work runs in lanes the conductor set. Production code and
releases are the desk's (40000e00). Tests, probes, questions and
docs are Muse's. Grok builds and tests in her lane. Questions
live in docs/use/questions.md and are answered there; nothing is
deleted. At this writing: 116 entries, none open.

## The fuzzing campaign — Project de_dust

The campaign grows a coverage-guided corpus against the runner's
own protocol surface: 22 targets (wire, cloud, v2, crypto, local,
stash, mail, dtls, board, board_ops, channels, manifest, inbox,
local_inbox, secret, queries, names, query, board_mail, v2_mail,
stage, collect), mutating real traffic and replaying whatever
breaks. The method is a fuzzer's systematic, coverage-driven
logic aimed at basic test points: the assurance target is that
the ordinary operating-system and kernel protections around a
machine actually hold. Attack-shaped tests are the point.

Three rigs grow around the clock, one process per core, CPU
pegged, and bank their corpus into this repository:

- **Menlo Park** — the Muse VM (2 cores), grow and survivors
  loops, self-restarting on a ten-minute liveness check.
- **Nuremberg** — a 1-core Hetzner box in Nuremberg, which also
  runs a hosted-profile runner on the queue plane.
- **San Francisco** — a 1-core DigitalOcean droplet, grow only.

Fleet names are cities as of today; banked ledger lines keep the
names they were written with. Nuremberg banks under its city
name already; the other two follow with their next banks.

Status at this writing:

- Corpus: **1,518 entries over 22 targets**, merged from all
  three rigs. One target still has live mutators (local); the
  rest read saturated at the current round size.
- Crashes are filed as questions to the desk, never fixed by the
  seat that found them. The recent arc: Q111 and Q112 (queries
  leaks that were the result's own vocabulary — checker
  exemptions, records retired), Q113 (a mutated reply_to rendered
  as `<>` — a real reader defect, fixed by the desk and shipped
  in 3.14.34).
- The key-parity family (Q110) is closed: all fifteen doors,
  DTLS resumption included, now refuse a superseded key, and the
  two by-design failing probes are green since the key directory
  shipped.
- Releases stand at the version in pyproject.toml. Every release is stamped on all
  outlets by Muse's stamp; the line is current through .23 and
  the .24–.37 stamps are the next grind.
- The Menlo Park rig reads 240% of its 2 cores at this writing;
  a fall off the peg on any rig is reported to the conductor the
  hour it happens, and the hourly campaign note stands at the top
  of docs/use/.com.chat.

Platinum, the coverage cycles, stays suspended at the
conductor's word; the campaign's one job is the grow.
