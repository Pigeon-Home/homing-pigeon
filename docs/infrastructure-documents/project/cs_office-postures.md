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
