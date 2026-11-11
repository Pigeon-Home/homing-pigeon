# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

# Feature tiers: what carries which promise

The suite ships more than its centre. This page sorts the
shipped features into three tiers by the promise each one
carries — the supported core, the advanced tier, and the
experimental tier — and shows the evidence each placement
rests on, so a reader can check the sorting instead of
trusting it.

## The supposition

Written before the inventory on this page was taken, so the
record shows what was expected against what was found:

1. Every feature the README names will already be sorted
   by the tree's own signals — a config gate in
   `runner/config.example.json`, an "(optional)" or
   "(opt-in)" marker in PROTOCOL.md, or a shipped /
   design-notes label in the transports document — and no
   placement will need a judgment the tree does not make
   itself.
2. The narrow core — the runner, job verification, one
   transport, key management, the audit log, confinement,
   the separate job user, simple result handling — will
   match what is on by default or ungated, with one split:
   parts of key management are marked opt-in in
   PROTOCOL.md's own section 14 headings, so key
   management will land in two tiers, not one.
3. At least one feature that sounds like research from its
   name will prove to be on by default in the example
   config; the Oracle's learning loop is the candidate
   (`oracle_learning` is expected to read true).
4. The transports document will name at least one
   transport that has no shipped code: a design-notes
   section with no folder in `runner/transport_extensions/`.

## How the inventory was taken

Taken on 2026-11-09, against the tree whose newest release
commit is 654de37cd8a0dfa152e07fe4a2093d9b1b015c1b:

- The README's claims: its Status paragraph ("the agent,
  the Oracle (opinions, self-learning, remediation), five
  job transports, and the example senses") and its section
  headings.
- PROTOCOL.md's section headings, including the
  "(optional)" and "(opt-in)" markers the document puts on
  its own sections.
- `runner/config.example.json`: every gate named in the
  tables below, read at its documented default.
- `runner/transport_extensions/` — the shipped transports —
  set against the sections of
  `docs/infrastructure-documents/extend/transports.md`.
- `runner/extensions/`, the shipped senses, counted.
- `runner/tests/`: 452 test files, counted by the area
  their file names carry. A coverage signal, not a proof:
  it shows where the suite's weight sits, and a placement
  below never rests on it alone.

## Conclusions

1. **Held in part.** Every feature the README names
   carried tree evidence — a gate, a marker, or a label —
   but 3 placements needed a judgment the tree states only
   in part, and they are named here rather than smoothed
   over. Confinement: PROTOCOL.md calls it "(optional)"
   while the shipped default is `enforce`; the placement
   follows the shipped default, the thing a user actually
   runs. The Oracle's deterministic watch: on by default,
   yet a layer the job loop runs without (its mode key
   reads `off` as a real setting); it sits in the advanced
   tier on that evidence. Hosting: built and tested, and
   never in the job path; advanced on that evidence.
2. **Held.** The core is what is on by default or ungated,
   and key management split where section 14's own markers
   fall: 14.1 and 14.4 are marked "(opt-in)" and sit in
   the advanced tier, while the secret itself, its name
   (14.2), its rotation, and the panic word (14.3) carry
   no marker and sit in the core.
3. **Held.** `oracle_learning` reads true in the example
   config: the learning loop's verified facts are
   default-on shipped behaviour, in the advanced tier. The
   loop's model channel reads false
   (`oracle_learning_model`), and that half sits in the
   experimental tier — the split runs through the feature,
   not around it.
4. **Held, and understated.** The transports document
   carries 6 sections with no shipped code behind them —
   one is labeled "design notes" in its own heading, one
   is labeled "cut" — against exactly 5 shipped transport
   folders: the README's "five job transports" to the
   letter.

## The three tiers

- **The supported core.** What a first run exercises and
  what the suite exists to keep working: on by default or
  ungated. If a core feature breaks, the release is
  broken; there is no posture in which the suite is
  itself without it.
- **Advanced, supported.** Shipped, tested, and
  documented, but opt-in or off the first-run path: the
  owner turns it on, and when it runs it carries the
  same promise as the core. Nothing in the core depends
  on it.
- **Experimental and research.** Shipped behind a
  default-off gate whose output is a local model's, or is
  labeled uncorroborated by the design itself — or
  present only as a draft or as design notes, with no
  shipped code at all. It may change shape or be cut;
  nothing else in the suite is promised on top of it.

## Tier 1 — the supported core

| Feature | Evidence |
|---|---|
| The runner: poll, verify, execute, reply | PROTOCOL.md sections 1–8; `runner/runner.py`; no gate turns it off |
| Job verification: the HMAC-SHA-384 signature check, size caps before the check, staleness and replay refusal, at-most-once execution from the outbox stash | PROTOCOL.md sections 4–6; `max_job_bytes` (default 4 MiB) bounds a job before its signature is checked |
| Per-job encryption: the AES-256-GCM envelope | `job_encryption` true in the example config; a cleartext body is refused unless the runner is started with `--allow-cleartext` |
| The email transport | `"transports": ["email"]` in the example config; the default every install walks |
| Key management in its base form: the one shared secret, its fingerprint name, rotation, the panic word | PROTOCOL.md section 14 marks only 14.1 and 14.4 "(opt-in)"; 14.2 (names) and 14.3 (the panic word, installer-generated) carry no marker; `docs/steady/secret-rotation.md` |
| The audit log | The `security` block in the example config (`audit_max_lines`); `runner/tests/test_audit_chain.py` |
| Confinement: the platform backends — the Linux bubblewrap sandbox, the Windows Job Object + restricted token + low integrity backend, the FreeBSD per-job jail — and the workspace snapshot check | `security.modes.confinement` reads `enforce` in the example config; the README: a sandbox that cannot engage refuses to start the runner at that default. PROTOCOL.md 9.4 calls confinement "(optional)" — the protocol does not require it; the shipped runner turns it on |
| The separate job user | `security.modes.job_user` reads `enforce` in the example config |
| Simple result handling: the signed result at the full view, stashed in the outbox and resent until delivered | `max_result_view` reads `full` in the example config; the stash is PROTOCOL.md section 5 |

## Tier 2 — advanced, supported

| Feature | Evidence |
|---|---|
| The file transport | The transports document: "File — shipped"; off until named in `transports` |
| The NATS transport | The transports document: "NATS (core) — shipped" — "core" there is the messaging system's own name, not this page's tier; the broker credentials are its first gate, the signature its second |
| The DTLS transport (the session binding) | The transports document: "DTLS — shipped (the session binding)"; the example config: "off unless enabled"; 12 test files name dtls |
| The hosted queue transport | The transports document: "Queues — the hosted pipe (built)"; `runner/cloud/queues-worker/`, `runner/transport_extensions/queues/` |
| Result policies: the attested view and its attestations | PROTOCOL.md sections 9, 9.1, 9.2; the eyes-open and lockdown postures set `max_result_view` to `attested` |
| The judge (pre-execution judgment) | PROTOCOL.md 9.3, "(optional)"; `judge` reads `off` in the example config and `advisory` in the installer's password-only profile |
| Per-key policies | PROTOCOL.md 14.1, "(opt-in)"; `key_policies` in the example config |
| The key directory | PROTOCOL.md 14.4, "(opt-in)" |
| The Oracle's deterministic watch: tier-1 opinions at the repair latitude, the resources watch, sensor fusion | `oracle_opinion_mode` reads `repair` by default and `resources.enabled` true; 35 test files name the Oracle; `docs/steady/design/oracle-opinion-design.md` |
| Deterministic remediation | `remediation_mode` reads `deterministic` by default; a closed tripwire list; `docs/steady/design/remediation-design.md` |
| The learning loop's verified facts | `oracle_learning` true by default; the example config's own note: lessons are "verified facts derived by code from execution records" |
| Senses: the extension system and the shipped senses | `extension_review` reads `enforce` by default; 28 folders in `runner/extensions/`; `local_signals` true; `docs/steady/extensions.md` |
| The task board | PROTOCOL.md section 13; `dag_mode` reads `off` and `require_review` false in the example config — the board's gates are the owner's to raise |
| DRI paging | `dri.enabled` reads false in the example config; the trigger table is owner-set |
| Mailbox OAuth sign-in | The README's Status: "A Thunderbird-style OAuth sign-in is shipped for the mailbox"; `runner/wire/oauth.py` |
| The hosting control plane | `runner/hosting/`; the "What is built" table in `docs/steady/project/hosting.md`, phases 0–4 with their tests; a provisioner that never sits in the job path |
| Advisory detection on results | `runner/oracle/detection.py`; the example config's note: optional, records `detection_hits`, "All advisory; never raises" |
| The cleartext job form | PROTOCOL.md section 8, "Debug: cleartext"; accepted only under the `--allow-cleartext` startup flag — a compatibility exception, fenced by a flag that has no config key |

## Tier 3 — experimental and research

| Feature | Evidence |
|---|---|
| Local inference: the `ask` op | PROTOCOL.md 10.1; `inference.endpoint` reads `""` — nothing configured — in the example config; the Pi Light mode keeps the `ask` op off by design |
| Model-formed opinion notes (opinion tier 2) | `oracle_opinion_model` reads false by default; the model's note joins an opinion only on that opt-in |
| Model-distilled learning candidates | `oracle_learning_model` reads false by default; the example config's note: candidates are "labeled uncorroborated wherever they surface" until verified outcomes corroborate them |
| Model-driven remediation | `remediation_mode` set to `oracle`; the default is `deterministic` — a model kill order for a lesser divergence is the only addition |
| Extension source fetching for the Oracle | `extension_sources` reads `auto`: what a `sources.json` declares is fetched for the local model to read; nothing fetched ships; an unpinned entry waits for the owner's allowance; a deterministic box makes no request |
| Protocol version 2 | `runner/wire/protocol_v2.py` opens version 2 only when the config's `protocol_v2` is exactly true; jobs are protocol 1; version 2 rides its own Internet-Draft |
| The DTLS hybrid group, X25519MLKEM768 | `runner/wire/mlkem.py`, `runner/wire/dtlsproto.py`: the hybrid share is "accepted only under the hybrid profile option", and the session constructor's default is `hybrid=False` |
| Protocol version 3 | A draft under `docs/ietf/`; shipped code speaks it — `runner/wire/dtls_mailbox.py` carries the version 3 carriage and the DTLS transport rides it — enabled only with `dtls_via_email` set to true, off by default on every platform |
| Transports with no shipped code | Sections of the transports document with no folder in `runner/transport_extensions/`: NATS JetStream ("design notes"), MQTT, Redis Streams, Postgres, Cloudflare Durable Objects; and "Local socket — cut" |
| The FUTURE sketches | `docs/FUTURE.md`: one-tap approval, signatures with no shared secret, a dashboard — written as imagining, not as shipped features |

## Boundary notes

- This page's "core" is a promise about features. The
  tree uses the same word for two other things:
  `runner/ops/core.py`, the canonical list of the code
  files that run — a code list, not a promise — and "NATS
  (core)", the messaging system's own name. The three
  senses are kept apart by stating each in full.
- `docs/support-matrix.md` sorts platforms, not features:
  its "Experimental" means a CI leg or a documented
  target exists, with no release guarantee. A platform
  can be experimental while the core features on it are
  tier 1, and the other way around.
- Installer profiles (password-only, pi-light) change
  which features a given install turns on; they do not
  move a feature between tiers. A tier is the promise a
  feature carries when it runs.
- Nothing in `docs/FUTURE.md` is in a tier until it
  ships. The table above names the sketches only to draw
  the boundary of "shipped".
