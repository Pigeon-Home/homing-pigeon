# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

# cs_office — disclosure postures, declared in data

Marking: hp0.

A cs_office project is not simply public or private. Between
those poles sit the arrangements the work actually uses: a
project nothing is ever said about in public; a project that may
be named in public while nothing about the work on it is said; a
project that may be named and the work on it described in general
terms. Those arrangements are the project's **disclosure
postures**, and this note records the decision that a posture is
declared data, not code — written down in a registry an operator
edits, and read by a small tool
(`runner/tools/disclosure.py`, beside the code-name and name-guard
tools) that reports what any project's tagging comes to under the
registry as declared. The tool is named for the judgment it
checks rather than for the posture itself, because the tree
already carries a posture module of a different kind —
`runner/ops/posture.py`, the runner's startup security posture,
with its own tests — and two tools answering to one name would
invite exactly the misreading this work exists to prevent.

The split mirrors the two-shelf rule on the cs_office page. The
shelf rule says what material may live where. A posture is the
same judgment made per project, about the project itself: what
may be said publicly about it, and where its material may live.
The hp0-hp3 sensitivity markings classify material; postures
classify projects. The two schemes sit side by side and neither
replaces the other.

## The posture model

A posture declares, at minimum:

- a **stable id** — the posture's identity. An id is issued
  once and never reused or renamed; it is what a successor
  pointer and an audit trail refer to.
- a **short tag** — the token a tagging file writes beside a
  project. Tags are unique across the whole registry, retired
  postures included, so a tag always means at most one thing.
- **say** — what may be said publicly about a project under
  this posture, in the operator's own words.
- **shelf** — where the project's material may live, in the
  operator's own words.
- a **status** — `active`, or `retired`. A retired posture
  stays in the registry so old references still resolve; it may
  declare a **successor**, the id of the posture that replaces
  it.
- a **note** — anything else the operator wants on the record.

A project is categorized in a **tagging file**: one entry per
project, naming the project and the tag of its posture. A
project has exactly one entry, so it has exactly one effective
posture at a time.

Both formats are declared in the tool's own text and enforced
exactly, in the house style of the sibling tools: unknown keys,
duplicate ids or tags, malformed shapes, and dangling successor
pointers are refused loudly, by name, rather than guessed at.
The registry and the tagging file are the operator's data, kept
where the operator keeps such data; the copies that ship in the
repository (`runner/tools/disclosure-registry.example.json`)
carry the schema and obviously fake example entries only. The three
standing postures, described abstractly:

- **nothing-said** — the project is not named, described, or
  acknowledged in public writing.
- **named-only** — the project may be named in public writing;
  nothing about the work on it is said.
- **named-and-described** — the project may be named, and the
  work on it described in general terms; findings and case
  material still move only through the formal channels, as the
  cs_office page's industry-practice section states.

## The exemplar letters

The cs_office document letters its exemplar projects, and the
letters map onto the postures like this:

- **A — the hidden posture** (nothing-said). A is never
  exemplified in this repository: the posture's own rule is
  that there is nothing public to point at.
- **B — the open posture** (named-and-described): named, and
  the work on it described, as the cs_office document carries
  it.
- **C — BOOKEND, the hybrid posture** (named-only). Its
  target is Homing Pigeon itself — this suite, the
  repository's own project — named, with nothing about work
  against it said.
- **D — DELTA, a documented example.** Meta, a company whose
  bug-bounty program terms welcome being named, carried as an
  example of a target that may be named in the open where its
  own program invites it. The letter is example-only; no work
  stands behind it.

The letters name exemplar projects in prose. They are not
registry tags: a registry's tags are the operator's own
tokens, and the shipped example registry's entries remain
fake schema demonstrations, lettered independently of this
mapping.

## Extensibility rules

The taxonomy lives in the registry, so reworking it is editing
data under these rules:

- **Adding a posture** is appending one entry with a fresh id
  and a fresh tag. No tool change, and no existing tagging file
  is affected.
- **Changing what a posture permits** is editing its `say` or
  `shelf` text in place. The id is the identity; the text is the
  registry's current word on what the posture means, and the
  registry's own history is the record of the change.
- **Renaming** is never an in-place edit of an id. A posture
  that is being replaced is retired, with its `successor`
  naming the new posture's id, so anything still pointing at
  the old posture resolves to a plain statement of what
  replaced it. A tag may be re-lettered in place on its
  posture; tagging files are updated in the same edit, and the
  checker proves nothing still points at the old tag, because
  an undeclared tag is reported as unknown, never guessed at.
- **Re-categorizing a project** is editing its one entry in
  the tagging file. The tool holds no state between runs, so
  the new categorization is simply what the next check reads.
- **Retiring a posture** sets its status to `retired`, with a
  successor where one exists. The entry stays. The checker
  flags every project still assigned a retired posture, and
  names the successor when one is declared — plainly, in the
  report, not as a silent rewrite of the project's tagging.
- **An old tag** that no longer appears in the registry is
  unknown, and the checker says so. A tag on a retired posture
  still resolves, and is reported as retired. Neither case is
  ever silently mapped to a live posture: a checker that
  guessed would be a checker that could put a project under
  the wrong disclosure rule without anyone deciding it.

## Supposition

Written before the tool exists, to be judged against the build:

Re-categorizing a project, adding a fourth posture, and
retiring one of the three standing postures will each cost
exactly one edit to a data file and zero edits to the tool and
zero changes to what the tool's tests expect of any specific
posture. The check run against a tagging file that still uses
a retired posture will exit 1 and name the successor; the
check run against a tagging file using a tag the registry no
longer declares will exit 1 and call the tag unknown rather
than guessing. If any of those operations needs a code change,
the registry shape is wrong, and the shape — not the code —
is what gets reworked.

## Outcome

The supposition held, measured against the build that lands
with this note. Re-categorizing a project is one edit to its
tagging entry, exercised in the tests as a data edit against an
unchanged registry. A fourth posture (named-with-embargo) is
appended registry data and resolves on the next check. Retiring
one of the standing postures keeps old tagging resolving: the
check exits 1, flags the assignment as retired, and names the
successor where the registry declares one — through a successor
chain, the active posture the chain ends at. A tag the registry
no longer declares is reported UNKNOWN TAG, exit 1, never
guessed at. No operation needed a code change, and no test
expects anything of a specific posture; the suite's expectations
are of the formats and the resolution rules only.

Two strengthenings the build itself forced, both in validation
rather than in the registry's shape. Declared text refuses the
zero-width characters the name guard's normalization removes —
invisible in a declaration, and a confusable wherever one slips
in. And a tag differing only in case from another tag is
refused at load: a tag that near another tag will be mistyped
onto the wrong project, and the registry is the place to catch
it.

Proof of work. The tool stands at runner/tools/disclosure.py,
stdlib only, in the sibling tools' shape: both formats declared
in its own text and enforced exactly, `validate` and `check`
subcommands, exit codes 0 (clean or valid), 1 (findings), and 2
(malformed or unreadable input). The unit tests stand at
runner/tests/test_disclosure.py: 74 tests, 248 subtests,
covering the registry format per field (unknown keys, duplicate
ids, duplicate and case-colliding tags, whitespace-, control-
and zero-width-edged values, the id's punctuation bookend
family), successor integrity (dangling, self, and cyclic
pointers refused; chains resolving to their end), the tagging
format per field, the resolution rules, the extensibility
operations above, the shipped example registry, and the
command line's exit codes. The suite ran green under both
pytest and unittest discovery, with the sibling tools' suites
alongside — codename, nameguard, and the startup posture's own
tests, 216 tests in the four. The guard families that run for a
new tool — layout, skip registry, reader-docs quiet, design
docs, doc version rot, personal docs — ran green; the layout
stale-path guard caught one path shape in the new tests during
this landing (a relative "tools" join in the example-path
construction), fixed in the same landing and re-run green. The
forums record this proof as well, in the cs_office forum and
the seats' forum.

## Industry grounding, and the open refinements

A sourced research pass on classification practice (the
Traffic Light Protocol, ISO/IEC 29147 and 30111, the CERT
coordinated-disclosure phases, and the sensitivity-label
machinery of the large platform vendors) landed alongside
this build. Its central finding shapes what happens next: no
single scheme tags projects by sayability. Practice composes
three different kinds of scheme — a sharing-boundary label for
information in an exchange, a process-state scheme for where
a case stands in its disclosure lifecycle, and label
machinery that carries handling and enforcement. A posture
registry for projects should therefore grow into three
orthogonal axes rather than a longer ladder:

- the **posture** itself — what may be said, the axis this
  note's registry declares;
- a **disclosure state** per project, in the CERT manner
  (discovered, reported, validated, remediation, public
  awareness, deployed, and closure) — expected to change over
  a project's life, with closure modeled as a state carrying
  a reason, never as a posture; and
- **handling flags** that cut across postures and can only
  tighten handling, never loosen a posture.

Against that yardstick, some of the research's principles are
already this build's behavior: postures are deprecated, never
deleted (a retired posture stays declared and resolvable,
with its successor named); ids are issued once and never
reused; an unknown tag fails closed; the taxonomy lives in
data under declared formats, not in prose. The mapping of the
three standing postures onto the research's recommended set
is direct: nothing-said is its *sealed*, named-and-described
is its *published* track, and named-only is its
*existence-public*. Its remaining two — *internal* and
*embargoed* — are candidate postures an operator may add by
registry edit under the rules above, when a project needs
them.

Recorded as open refinements for the formats' next version,
to be taken up as one deliberate revision rather than piecemeal:

- A posture declares **what may be said as a matrix**, not
  prose alone: existence, codename, topic area, target name,
  partner name, findings summary, technical details, exploit
  or proof-of-concept, and timeline dates, each sayable or
  not — alongside an audience, allowed and prohibited
  locations, a handling declaration (encryption, sharing, the
  guard action tooling takes), a TLP equivalent for outbound
  material, a review cadence, and an owner.
- A posture record gains a display name with **aliases** (an
  old name kept working after a rename), a **rank** on the
  ladder (so tooling can tell a loosening from a tightening),
  the registry version it was introduced in, and **examples
  and non-examples** — what the posture is not being the field
  that prevents boundary drift.
- **Transitions are governed:** loosening a project's posture
  requires an approver and a justification, and the
  justification is logged; a forced transition (material
  public ahead of plan) moves a project to review at once.
- A project record carries the registry version it was tagged
  under, its disclosure state and flags from the axes above,
  and an **appended history** — re-categorization recorded as
  a dated event, never an overwrite that erases the old
  categorization.
- The scheme itself is **versioned in the semantic manner**:
  a clarification is a patch, an added posture or optional
  field a minor, a redefinition a major — with deprecation in
  a minor before any removal in a major, and a migration map
  when a major lands.

None of these change the supposition's verdict: each is a
format revision and data edit when it comes, taken up in the
open, not a rewrite of how postures are declared.

## The log stamp

A posture governs a project; the records the project leaves —
log lines, run records, ledger entries — need to carry that
governance with them, in a form a reader or a tool can parse
without judgment calls. The tool therefore also declares a
**stamp**: a single whitespace-free token,

    hp-posture-<version>-<posture id>

as in `hp-posture-1-named-only`. The stamp carries the
posture's stable id — never its tag, which an operator may
re-letter — and the registry format version it was minted
under, so a reader holding a different version fails closed
instead of misreading. The tool provides the three helpers,
in the code-name tool's discipline: `format_stamp` mints a
stamp from a loaded registry (refusing an unknown id, and
refusing a retired posture — new records are not stamped
with a posture that has been replaced), `parse_stamp` reads
a stamp strictly (the whole string, exactly this shape;
wrapping punctuation, a leading-zero or zero version, or an
id outside the id grammar are all refused), and
`validate_stamp` resolves a stamp against a registry,
raising on a version mismatch or an unknown id. A stamp
naming a retired posture still validates — old records stay
readable — and its posture's status says what it is.

Supposition, written before the helpers: a stamp minted from
the shipped example registry will round-trip through parse
and validate for every active posture in it; a stamp naming
an undeclared id, and a stamp minted under any other version,
will fail closed at validate; and the malformed family —
missing segments, bookend punctuation, whitespace, a
case-flipped id — will fail at parse, never be repaired.

Where producers stamp it: on any record that concerns a
cs_office project, at the moment the record is written — the
job record, the run record, the result envelope, the ledger
entry, and a log line that names the project. A consumer
that cannot parse a stamp, or cannot validate it against
the registry it holds, treats the record as carrying no
clearance at all. Wiring, stated plainly: this landing
provides the format, the helpers, and this guidance, and
wires **no** producer — the runner's job records, run
records, and log lines do not stamp yet. Wiring each
producer is follow-on work, one producer at a time, each
with its own tests.

Outcome, measured against the build that lands the helpers:
the supposition held. The suite's stamp family round-trips
every active posture of the shipped example registry through
mint, parse, and validate; a stamp naming an undeclared id,
and one minted under any other version, fail closed at
validate; the malformed family — missing segments, bookend
punctuation, whitespace, a case-flipped or over-long id, a
zero or leading-zero version — fails at parse, unrepaired.
The suite stands at 87 tests and 382 subtests, green under
both pytest and unittest discovery, with the sibling tools'
suites alongside (229 tests in the four).

## What the Oracle is to understand by a posture

The Oracle renders opinions inside this suite, so its
understanding of a posture lives where the Oracle's
instructions live. The Oracle has a single instruction home
now: its standing instructions stand at
`docs/steady/oracle/instructions.md`, and the canonical
posture text is the first text that file carries, under its
"Disclosure postures" heading. The runner assembles that
file into every ask on a box (the briefing design record is
`docs/steady/design/oracle-briefing-design.md`), so no
deployment hand-copies the text into its `owner_instructions`
any more. The text defines the semantics by pointing at the
registry — the single source of truth — rather than
restating any posture's declaration, so the text cannot
drift from the data. It stands there, not here; this note
keeps the model, the registry format, and the extensibility
rules.
