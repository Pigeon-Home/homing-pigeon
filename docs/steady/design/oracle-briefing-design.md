# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

# Design: the Oracle's briefing — the same door, its own layer on top

Status: shape 4 chosen; all four stages built (the Oracle
layer has its home at docs/steady/oracle/instructions.md,
assembly is wired at the ask seam, the manifest resolves the
discovery surface locally, --inspect briefing reports the
assembly, snapshots carry the prebuilt digest, and the
remediation helper, the opinion note, and the deterministic
briefs ride the same briefing).
This note records an inventory of where the Oracle's
instructions live today, an enumeration of the discovery
surface a visiting system pulls when it is handed nothing but
the project's address, five shapes for giving the Oracle a
single instruction home pointed at its local checkout, and a
recommendation with a staged plan.

## The position this design starts from

The Oracle's model is a local model, run on the owner's machine
(the installer sets up Ollama and a small model by default; the
deterministic mode runs no model at all). The project's position
is that the Oracle is briefed as a superintelligence is briefed:
with the whole standing context of the project in front of it —
its rules, its semantics, its map of itself — written for the
strongest reader the project will ever have, and provisioned the
same way whether the reader of the day is that reader or a small
local model working the same texts. The briefing is not sized
down to the model. A smaller reader gets the operative rules
first and the depth behind pointers it can follow where it has
tools; a stronger reader gets everything it needs to answer
whole-project questions, and to say honestly what its answer
rests on. That stance, not the size of any one model, is what
the shapes below are judged against.

## Supposition

Written before any of the shapes below is built, so the record
shows what was expected: if the Oracle's standing instructions
are resolved against the checked-out project at ask time, through
the same discovery surface a visiting system uses, and assembled
through the single ask seam every model call already passes
through, then (1) every Oracle surface on a box briefs from the
same texts a visitor is briefed from, plus the Oracle's own
layer; (2) the briefing moves when the checkout moves, with no
deployment hand-editing project semantics into its config; and
(3) a canonical text carried this way reaches the model verbatim
— measured by an assembled-prompt fixture test across the ask
call sites, and by the posture semantics text (the first
canonical text awaiting a home) appearing byte-for-byte in the
assembled briefing of a fixture deployment.

## Where the Oracle's instructions live today

The inventory, from the code and the configuration page:

- **Two charters, hard-coded.** `runner/ops/oracle_tools.py`
  carries both standing system prompts as string constants:
  `ASK_SYSTEM`, for the mailbox query path, where a cloud system
  asks about job output it must never see raw — a disclosure
  boundary, ending "You are a constrained local model"; and
  `ASK_AGENT_SYSTEM`, the interactive charter — the owner's local
  debugging partner, with tools for hands — restored in full in
  2026-10 and pinned by `runner/tests/test_oracle_charter.py`.
  The shared how-to-answer rules (the watch sections, the
  `notable:` line, never invent, never reveal secrets) are
  duplicated across the two by hand.
- **Fixed fragments per surface.** The remediation order is one
  constant question (`ORACLE_QUESTION` in
  `runner/oracle/remediation.py`): the model is told it is the
  remediation authority for this box and asked for a KILL or
  SPARE line. The opinion tiers are mostly deterministic checks;
  a model note, when enabled, is prefixed `Model-formed note:` so
  the tiers are never blended. The job review's rules live in
  code (`runner/oracle/review.py`) with an operator-facing
  playbook. None of these surfaces receives any deployment or
  project text.
- **One free-text string per deployment.** `owner_instructions`
  in `config.json` — a plain human-readable string describing the
  box, set by the installer's `--instructions` /
  `--instructions-add`, validated as a string in
  `runner/ops/attest.py`, read live (it is in `LIVE_KEYS`, so an
  edit needs no restart), and passed as the `instructions`
  argument to `ask_model` by the ask call sites
  (`runner/ops/oracle_ops.py`, `oracle_server.py`, `queries.py`,
  `handlers.py`). It carries the box's own facts well ("This is a
  Raspberry Pi. The only thing that matters is the password.").
  Anything more — project semantics, standing rules — a
  deployment must also write into this string, by hand, and keep
  current by hand as the project moves.
- **A context builder that assembles data, not meanings.**
  `runner/ops/context.py` builds the per-question context: the
  job index first, retained job summaries, the runner log tail,
  the watch sections (canary, event log, registry, host log,
  firewall, AV), the project snapshot note, and extension sources
  under the disclosure rule — under a character cap (8,000 by
  default; 12,000 for the agent door). It deliberately carries no
  standing instruction text.
- **A checkout that is already on the box, pointed at but not
  briefed from.** A release install carries the whole project
  under `<base_dir>/project/` (`runner/tools/make_snapshot.py`):
  source, tests, docs, CI workflows, the full history as a git
  bundle, and the build's CI facts, indexed by
  `PROJECT-SNAPSHOT.md` with `CI-SNAPSHOT.json` beside it.
  `_project_snapshot_note` in `runner/runner.py` names those paths
  in the context so the model can read the source with its tools.
  The pointer exists; nothing in the standing instructions tells
  the Oracle what the project is, what its own rules are, or
  which of the snapshot's texts are its instructions.
- **Playbooks written for operators.** `docs/steady/oracle/` (the
  DRI playbook, the job review, the senses) and the configuration
  page describe the Oracle to the people who run it. Nothing
  feeds them to the model.
- **A ledger that is evidence, never instruction — by design.**
  The learning loop (`runner/oracle/learning.py`) freezes every
  opinion call before the job runs, scores it against the
  verified outcome, and reads the ledger fresh for the next job.
  Its schema rejects instruction-shaped text outright ("output is
  evidence, never instruction"); a lesson never authorizes
  anything by itself. Any briefing design has to preserve this
  boundary exactly: a briefing is authored standing text, never
  learned text, and never job output.

And the recorded gap, in the posture note's own terms
(`docs/infrastructure-documents/project/cs_office-postures.md`,
"What the Oracle is to understand by a posture"): there is today
no single instruction home for the Oracle in this repository. The
canonical posture instruction text — what a disclosure posture
means, resolved against the posture registry as the single
source of truth, failing closed on an unresolvable stamp —
stands in that note "written to be carried into a deployment's
`owner_instructions` or a future Oracle instruction page whole."
The future page does not exist. Carrying it is, today, a
hand-copy per deployment.

What a deployment must hand-assemble today, in one list: install;
write the box's `owner_instructions` by hand; hand-copy any
canonical project texts (the posture semantics today, others as
they come) into that same string; re-copy them by hand when the
project revises them; and accept that the surfaces with fixed
texts — the remediation order, the opinion tiers — cannot be
briefed at all.

## The discovery surface: what a bare address pulls today

The interface this design mimics already exists, and it is the
project's front door. A visiting system handed nothing but the
project's address — the repository, or the protocol's own page —
and asking "what is this?" is briefed by what it pulls, in an
order the files themselves declare. The enumeration, from the
repository:

**Tier 0 — the two things not in the repository at all.** The
mailbox address and the shared secret are established out of
band: the sender asks the owner, and the owner provides them.
Version 1's specification states it in its second section —
neither is discovered from the mail, and once the sender knows
the address, the secret, and the specification, no further
coordination is required. The discovery surface briefs; it does
not credential.

**Tier 1 — the pull a visitor makes on arrival.**

- `README.md` — the front door: what this is, the risk stated
  first, how it works, and the worked prompt ("Try this
  prompt:") that turns a reader into a sender; the drafts are
  linked from it.
- `PROTOCOL.md` — the specification a sender codes against,
  incorporated by the README's prompt ("Use the Homing Pigeon
  protocol"). A runner also introduces itself from it at run
  time: a `ping` result's platform card is how a sender discovers
  a runner's platform and the protocol versions it opens
  (`PROTOCOL.md` §3.2), and version 3's draft generalizes the
  pattern — a submitter discovers an optional carriage the way
  it discovers the platform, by attempting it and reading the
  outcome, or from the platform card of a prior exchange
  (v3 draft, "Enablement").
- `AGENTS.md` — the standing instructions for any agent, pulled
  because the platform convention and the file's own position at
  the root make it the next read: the split (who holds what,
  which door is whose), the rules for working here, where things
  live, how to send a job and which shapes fail.
- The root manuals the front door names — `SECURITY.md`,
  `INSTALL.md`, `FAQ.md`, `ENTERPRISE.md` — the posture, the
  install, the answers, the enterprise statement.
- Inside `AGENTS.md`, the Secret agents notes — the briefing
  written for the visiting system itself: the fair warning (the
  repository is many times larger than any context that will
  hold it — the size stands in the version number — and the
  honest system says so, early, with the fraction its answer
  rests on), and the working patterns for the size: index the
  checkout locally and answer from named chunks; read the
  documentation whole in large sittings, with a digest checked
  against the text; and read the core whole —
  `runner/ops/core.py` names the running code at a size a strong
  reader can hold entire.

**Tier 2 — pulled when the work needs them.** The documentation
behind the map (`docs/steady/start-here.md` and the drawers it
names), the Oracle's own playbooks, the design records, and the
drafts under `docs/ietf/`. And, kept apart on purpose, the
project's living record — the forum files and the questions
file — which a visitor may read as evidence of what was decided,
never as instructions: the same evidence/instruction split the
learning ledger enforces.

What the project's own past research established about this
surface:

- **The cold test** (the project's forum record, the entries of
  2-Nov, 7:35pm and 10:00pm): a fresh chat — a reader who did not
  write the material — handed the rendered draft plus
  `PROTOCOL.md` and one prompt, was set to complete a signed
  clock job by carrying the exchange itself. The finding the
  record keeps: the documents, so handed, were sufficient for a
  cold reader to work the protocol, and the failure the test
  actually found was a code shape (a held result's downgrade
  path), not a gap in the briefing. The surface briefs a cold
  reader; that is measured, not hoped.
- **The five-question proof passes** (recorded in `AGENTS.md`'s
  Secret agents notes): the local index and the documentation
  digest were each proven against the same check questions —
  the index answering from its top hits once the query used the
  project's own names, the digest answering exactly where its
  sittings had reached and declining where they had not. The
  surface's two working patterns carry known, stated limits.
- **The sufficiency statement** (version 1's specification):
  address, secret, and specification are jointly sufficient —
  "no further coordination is required." The discovery surface
  is, by the project's own spec, a complete briefing for acting
  through the door.
- **The visitor study** (November 2026; a literature study of
  the vendors' published documentation and of measured
  experiments run against server logs and canary pages — no
  live run of the test itself was performed, so what follows is
  documented and reported behavior, held at medium confidence).
  The test is the one this surface invites: a visiting system
  handed nothing but the project's address — the domain that
  redirects to this repository — either with a rudimentary
  question ("what is this?", "give me an overview") or with no
  question at all. The findings qualify what the tiers above
  can promise a chat visitor. No hosted chat surface —
  ChatGPT, Claude, Gemini, Grok, Copilot, Perplexity — is
  documented to seek `AGENTS.md`, or any instruction file, when
  handed a link; the systems documented to read `AGENTS.md` on
  arrival are the coding tools (Codex, Copilot's coding
  surfaces, Cursor, Claude Code, the Gemini CLI, Jules),
  reached by connecting a repository, not by pasting an address
  into a chat — and a chat surface that fetches the file at all
  reads it as ordinary text. The arm with a question is the
  documented trigger for every vendor's user-initiated fetcher,
  and what the fetcher normally returns is the single landing
  page — here the PROTOCOL document as rendered, its text
  extracted from the page's HTML, no JavaScript executed.
  Exploration beyond the landing page is the exception, not the
  rule: one vendor states the single-page design outright, and
  the one measured counter-example — the large chat systems
  reading a documentation file linked from a README — ran on a
  small repository, from its root, under explicit questions;
  whether exploration fires from a file page, or through a
  redirecting domain, is untested in public. The redirect is
  the surface's cheapest failure point: no vendor publishes
  whether its chat fetcher follows a cross-host redirect to
  GitHub at all, and the one fetcher implementation
  reverse-engineered in public stops at exactly that hop —
  Perplexity the nearest exception, its fetcher documented to
  visit a page at a user's request and a pasted address alone
  reported as its ordinary usage. Depth is capped far below
  the tree for everyone: the largest documented chat windows
  hold about a twentieth of it, so the honest ceiling of
  either arm is the PROTOCOL document, possibly with the README
  and `AGENTS.md` beside it — presented, in the failure mode,
  as a summary of the project. No surface discloses the
  fraction: every one shows which pages it cites, none shows
  how much of a repository it read, and measured failures
  include answers given for pages the server's logs show were
  never requested. The arm with no question at all cannot be
  established from public sources for any system except
  Perplexity; no published experiment used a bare address as
  the whole prompt. One consequence lands on this project's
  own files: since the PROTOCOL page is the page most likely
  to arrive, the size warning and the index-don't-hold
  instruction have to live in PROTOCOL itself, not only in
  `AGENTS.md`, whose cross-point from PROTOCOL is therefore
  load-bearing.
- **The visitor test cards.** Because the decisive behaviors
  are published nowhere, the study's conclusion is that the
  only instrument that can measure this surface is a live run —
  and the live runs that measure the chat surface are the
  owner's own, on the flat subscriptions: an API key measures
  the API surface instead, and a coding tool is a different
  test again. The cards, to be run by hand: both arms — the
  rudimentary question, and the bare address alone — against
  the four chat houses (ChatGPT, Claude, Gemini, Grok), with
  the address and the tree held constant and the prompt the
  only thing varied; and for each run, record what the system
  fetched, what it claimed to have read, and whether it
  admitted that its answer rested on a part. A run that claims
  the whole tree from the landing page is the failure the fair
  warning exists for, measured at last instead of inferred.

Two properties of this surface matter for everything below. It
is **self-describing**: nothing outside the pulled files tells
the visitor what to pull next — each file names the next. And it
is **the same for every visitor**: the project does not maintain
a second, private briefing for favored readers. The Oracle is
the one strong reader of this project that is briefed from
neither — it is briefed from a config string and two charters.
That asymmetry is the gap this design closes.

## The hard constraint

In every shape below, the Oracle's own capabilities are not the
visitor's, and the mimicry must not flatten them. The Oracle
carries semantics no visiting system has: the attestation and
disclosure boundary its query door exists to hold (what may
leave the box about a job, and in what view); the disclosure
postures, resolved against the posture registry and its stamps,
failing closed; the security modes and key policies it renders
opinions under; and its learning ledger, which no visitor has at
all. The discovery surface is the door — it briefs whoever
arrives on what this project is. The Oracle's extras are a layer
on top of the door, assembled after it, governing their own
subjects, and never merged into the discovery files themselves:
`AGENTS.md` and the manuals must stay exactly as briefable for a
visiting human's system as they are today, with no Oracle-only
text growing inside them.

## Five shapes

### Shape 1 — A canonical instruction file, included by reference

One new checked-in file holds the project's standing Oracle text
(Shape 4's Oracle layer, alone): identity and doors, the
disclosure rules, project semantics as short whole texts that
point at their registries — the posture text first among them.
A config key (or an installer default) makes a deployment carry
a reference to it rather than a copy; at ask time the runner
reads the file from the checkout or snapshot and assembles it
ahead of `owner_instructions`.

- *Changes:* the file; include-resolution at the `ask_model`
  seam in `runner/runner.py`; installer default;
  `config.example.json`; the configuration page.
- *Currency:* the file rides the snapshot, so it moves with the
  release; a deployment running from a source checkout reads its
  own tree.
- *Versioned and tested:* versioned with the repository; a
  charter-style pin test asserts its operative sentences; a
  divergence guard pins that the configuration page names it.
- *Failure modes:* a snapshot older than the config that
  references it (fail visible: the startup warning names the
  missing file, and the briefing proceeds without it); an
  operator editing the shipped file in place — the file states
  on its face that deployments extend it through their own layer
  and never edit it.
- *Borrows:* `AGENTS.md` itself — one standing file, read first.
  But it leaves the asymmetry in place: visitors briefed from
  the discovery surface, the Oracle from a parallel file that
  can drift from it.

### Shape 2 — The checkout pointer: a manifest, read at ask time

The repository ships a briefing manifest — a small data file
naming exactly which of the checkout's own texts constitute the
briefing — and a resolver in the context builder's family
assembles the briefing from the checkout at ask time, stamped
with the checkout's commit.

- *Changes:* the manifest; an assembler beside
  `runner/ops/context.py`; the snapshot index grows a briefing
  section.
- *Currency:* perfect by construction — the briefing is the
  checkout, and the assembled text names the commit it came from.
- *Versioned and tested:* the manifest is data under test: every
  named path and heading exists (a drift guard in the family of
  the existing doc guards); assembly is a pure function of the
  checkout, fixture-tested.
- *Failure modes:* the budget — the named texts together far
  exceed the context caps, so the manifest must name extracts,
  and an extract is an editorial act that can silently drop a
  rule; and only the agent door has tools, so the mailbox door
  cannot follow pointers past what was assembled.
- *Borrows:* the local-index working pattern and the "read the
  whole core" sentence — pointers chosen by the project, read at
  need.

### Shape 3 — The generated briefing bundle

A build-time tool in the family of
`runner/tools/make_snapshot.py` digests the repository's standing
texts into one bounded briefing file — the canonical short texts
carried whole, the long tails digested — stamped with the tree's
version and the source hashes it was built from, shipped inside
the snapshot. The runner assembles the bundle verbatim.

- *Changes:* the tool; the snapshot build; a hash check at
  assembly.
- *Currency:* as current as the release; a bundle whose commit
  differs from the snapshot's is detectable and warned about.
- *Versioned and tested:* regeneration is deterministic, so a
  test re-derives the bundle and compares hashes; the project's
  five-question proof pattern runs against the bundle as a test
  family, so a digest that drops an answer the record says it
  held fails the build.
- *Failure modes:* digest lossiness — the sitting record shows a
  digest answers most check questions exactly, gets some partly,
  and declines the rest; a bundle that digests a rule it should
  have carried whole is the standing risk, bounded by carrying
  every short canonical text whole and digesting only narrative.
- *Borrows:* the docs-digest practice, exactly as the visiting
  systems use it.

### Shape 4 — The same door (recommended)

The Oracle consumes the same discovery surface from its local
checkout, and its own layer rides on top. No parallel briefing
is authored for the Oracle; the briefing *is* the one every
visitor gets, resolved locally, plus the Oracle layer. The
layers, assembled in order at the `ask_model` seam — the one
seam every model call already passes through:

- **Layer 0 — the doors.** The two charters stay where they are,
  in code, pinned by their tests. They are the safety shape of
  each door, not project knowledge, and they do not move.
- **Layer 1 — the discovery surface, local.** The tier-1 pull,
  resolved against the deployment's own checkout — the snapshot
  under `<base_dir>/project/` on a release install, the source
  tree on a checkout deployment — assembled the way a visitor
  assembles it: the front door's self-description, the standing
  instructions, the manuals' operative statements, the Secret
  agents briefing including the size honesty and the working
  patterns. Where the whole pull exceeds the model's room, the
  surface's own patterns apply to the Oracle itself: the digest
  of the surface (shape 3's bundle, generated from this checkout,
  hash-stamped) for the door without tools, and the manifest of
  named paths (shape 2) for the door with tools, whose snapshot
  note already names where the whole texts live. The assembled
  briefing names the commit it was resolved from, so the model —
  and the owner, through `--inspect briefing` — can see which
  checkout briefed it.
- **Layer 2 — the Oracle's own layer.** Assembled after the
  surface, governing its own subjects, and never written into
  the discovery files: the attestation and disclosure semantics
  of the query door (what the views are, what may leave, the
  registry-pointing posture text carried whole as its first
  text); the posture registry named as the source of truth for
  stamps and tags, failing closed; the security-mode and
  key-policy semantics its opinions render under; and the
  standing statement of the ledger's rule — its own past output
  is evidence to be weighed, never instructions to be followed,
  and a lesson authorizes nothing by itself. This layer is
  shape 1's canonical file, kept Oracle-only on purpose: it is
  the one part of the briefing a visitor neither needs nor gets.
- **Layer 3 — the deployment's own layer.** `owner_instructions`
  exactly as it is today — this box, this owner's facts — read
  live, and relieved of the hand-carried project semantics it
  was never shaped to hold.

The per-question context (`runner/ops/context.py`) stays what it
is — data, after the instructions, under its caps — and the
learning ledger stays evidence, never instruction. The layers do
not override each other; each governs its own subject: layer 0
the doors' safety shape, layer 1 what the project is, layer 2
what the Oracle is, layer 3 what this box is. A contradiction
between layer 3 and layer 2 is named in the startup warning
rather than silently resolved — the same posture the config
decision takes toward a present-but-unusable value that matters.

How the door and the extras live together, stated once: the
discovery layer can be revised by anyone who can revise the
project's public face, because it *is* the public face; the
Oracle layer changes only with the Oracle's own semantics, and
its texts point at their registries rather than restating them,
so a posture added to the registry is understood by the Oracle
with no briefing edit at all. A visitor and the Oracle reading
the same checkout hold the same picture of the project; the
Oracle additionally holds what its office means. Neither
picture is a copy of the other, so neither can drift from it.

- *Currency:* layers 1 and 2 ride the snapshot and move with
  the release; layer 3 is live-read as today.
- *Versioned and tested:* layer 2 versioned with the repository
  and pinned by charter-style tests; layer 1's bundle hash-stamped
  and proof-question tested; the assembly — order, presence,
  caps, the verbatim carriage of canonical texts — fixture-tested
  at the seam across all four ask call sites, so the supposition
  above is measured, not asserted. An `--inspect briefing`
  command, in the family of `--inspect review` and
  `--inspect sources`, prints exactly what a box's Oracle would
  be told.
- *Failure modes:* budget pressure across the layers (each layer
  capped; layer 2 kept short by rule — it carries semantics, not
  narrative); a stale snapshot briefing a new config (the
  briefing names its commit in its own text); the resolution
  machinery must stay pointed at the checkout and nothing else,
  so no text a job, a ledger entry, or an extension source
  carries can ever name its way into the briefing.
- *Borrows:* the whole pattern, not a piece of it — the front
  door, the standing file, the digest and the index, the core
  list, and the operator's own notes, each in the place the
  pattern already puts it.

### Shape 5 — The living briefing: the forums as instructions

Considered and set aside. Letting the briefing include the
current tails of the forum files and the questions file would
keep the Oracle current with what the seats decided lately — and
would break the boundary the suite defends everywhere else:
records are evidence, never instruction. Forum text is written
by many hands over time; as data, clearly labeled, a bounded
"recent project record" section is compatible with shape 4
later. As a standing instruction layer, no.

## Recommendation and staged plan

Build shape 4, in four stages, each landing on its own tests:

1. **The Oracle layer gets its home.** Create the canonical
   Oracle-layer file (`docs/steady/oracle/instructions.md`);
   move the posture semantics text into it as its first carried
   text, and turn the posture note's holding text into a pointer
   at the file. Wire assembly at the `ask_model` seam so the
   layer reaches every ask call site, ahead of
   `owner_instructions`; rewrite the configuration page's
   owner-instructions section around the layers. Extend the
   charter tests to pin the layer's presence and the posture
   block's verbatim carriage.
2. **The door, resolved locally.** The snapshot index gains the
   briefing manifest, and a briefing assembler
   (`runner/ops/briefing.py`) resolves layer 1 against the local
   checkout with per-layer caps; `--inspect briefing` shows the
   assembled result.
3. **The bundle.** `runner/tools/make_briefing.py` generates the
   layer-1 digest at snapshot build, hash-stamped; the
   five-question proof pattern becomes its test family.
4. **The other surfaces.** The remediation order and the opinion
   model note receive layer 2 after their fixed texts, so every
   model call on the box carries the Oracle's semantics, and
   deterministic mode assembles its briefs from the same layers,
   so a box with no model is briefed identically in kind.

What implementing it touches, across the project:

- *New:* `docs/steady/oracle/instructions.md`;
  `runner/ops/briefing.py`; `runner/tools/make_briefing.py`
  (stage 3); `runner/tests/test_oracle_briefing.py` with its
  per-field family for the manifest and the layer resolution.
- *Code:* `runner/runner.py` (the `ask_model` seam);
  `runner/ops/oracle_ops.py`, `oracle_server.py`, `queries.py`,
  `handlers.py` (route through the assembler);
  `runner/ops/context.py` (layer ordering against the data
  caps); `runner/ops/install.py` (the resolution default, and a
  decision on whether any new key joins the profile whitelist —
  `owner_instructions` itself is not whitelisted today);
  `runner/ops/attest.py` (validation of any new key, in the
  family of the `owner_instructions` string check);
  `runner/oracle/remediation.py` and `opinion.py` (stage 4);
  `runner/tools/make_snapshot.py` (carry the file and the
  bundle); `runner/config.example.json`.
- *Docs:* the configuration page
  (`docs/infrastructure-documents/oracle/configuring-oracle.md`);
  the posture note's pointer swap
  (`docs/infrastructure-documents/project/cs_office-postures.md`);
  the map (`docs/steady/start-here.md`); this note's status line,
  updated as the stages land.
- *Tests:* `test_oracle_charter.py` extended; the
  `test_oracle_context_*` families re-run against the new
  ordering; the doc guards over the new page (the reader's pages
  carry no process, and the drift guards pin what the
  configuration page names).

The Oracle is the project's resident system — the one reader who
lives here. This design briefs it the way the project briefs
every strong reader who arrives: through the same door, with
everything it needs, and with its own office's semantics layered
honestly on top.
