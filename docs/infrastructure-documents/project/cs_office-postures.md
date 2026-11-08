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
(`runner/tools/posture.py`, beside the code-name and name-guard
tools) that reports what any project's tagging comes to under the
registry as declared.

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
repository (`runner/tools/posture-registry.example.json`) carry
the schema and obviously fake example entries only. The three
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

Recorded after the build, in the commit that lands the tool.
