# The release gate: a human signature at Gate 5

Dated 2026-11-09. This document designs the human security gate
at release: the conductor's own checklist and sign-off, standing
at the one hard gate the desk already has (desk.md, Gate 5),
over the candidates the release trains already produce. It
answers the third change an outside peer review of this project
asked for first (2026-11-09): a human security gate at release,
regardless of the AI-native workflow — a human release checklist
and sign-off for any release, and explicit human review for the
change classes where a mistake is expensive.

Nothing here changes how work lands. Landing stays as desk.md
describes it: streams land early, main may be red, the release
is the filter. The gate stands at the exit of that filter, not
at its entrance. The desk document says the collaboration
machinery of many-human projects — required approving reviews,
owner sign-offs, review queues — is not used here; that sentence
is about landing, and it stands. What this document adds is
narrower and different in kind: one named human reads one short
checklist over one finished candidate and signs, or does not
sign, before the tag is cut. No queue, no per-commit review, no
second stream waiting on the signature.

## Supposition (written before the measurement, 2026-11-09)

The design below rests on three suppositions about the tree as
it stands. Each is stated here before it is measured, so the
record shows what was expected against what was found; the
conclusions section that follows the measurement says what the
numbers supported, and the design is the change those numbers
support.

1. **The trains already produce every fact a gate needs.** The
   hourly release train and the conductor-edit release watch
   already establish, for every candidate: the main build green
   on the exact release commit, the tag build green, the publish
   jobs' success, the release published with its full asset set,
   and the stamp check (the wheel, the sdist and the platform
   tarball re-downloaded and matched against the release's sums,
   three matches). The ship record in the ship lane's state file
   carries each of these as a stated fact. If this holds, the
   checklist the conductor reads can be assembled mechanically
   from records that already exist, and the human's minutes go
   to judgment, not to gathering.
2. **The review classes map onto the tree's own folders.** The
   classes the review names — protocol, execution, key handling,
   confinement, job-user behavior, extension loading, disclosure
   controls — correspond to path families this tree already
   keeps apart (the wire folder, the guard folder, the Oracle
   folder, the extension folders, the ops modules), closely
   enough that a declared path registry can classify a release
   range mechanically. The registry is expected to err toward
   over-inclusion: a path that touches two classes asks for both
   reviews, and a class wrongly asked for costs a minute, while
   a class wrongly skipped costs the gate its point.
3. **A sign-off record can be checked mechanically.** A record
   that names the full version, the release commit, the
   conductor, the date, a verdict, and one reviewed-line per
   class the range touched can be validated by a tool — fields
   present, shapes right, every touched class accounted for —
   with no secret and no private material in it. If this holds,
   the enforcing phase, when the conductor orders it, is a check
   a machine already knows how to run.

The measurement: the two most recent release ranges, read from
the git history; the changed paths in each, classified by hand
against the seven classes; the ship record for the latest
release, read against supposition 1's list of facts; and the
classifier, once built, run over the same ranges to compare its
output against the hand classification.

## Measurement and conclusions (2026-11-09)

**Supposition 1 holds.** The ship record for the latest release
(release commit 654de37cd8a0dfa152e07fe4a2093d9b1b015c1b)
states every fact on the supposition's list in one line: the
release published at a named time, draft=false, 13 assets, the
main and tag builds green, the stamp check matched three times.
The tag workflow adds its own guards upstream of that record:
the tag must not already exist, the version carriers must agree,
and the build job on the tagged commit must have concluded
success before a tag lands. No fact the checklist needs has to
be created; each has to be transcribed. The generator therefore
fills what git knows and leaves the ship facts as labelled lines
in the ship record's own wording, so filling the checklist is
transcription, not investigation.

**Supposition 2 holds, with two corrections the measurement
forced.** The two most recent ranges (cf66bef34..654de37cd and
bfc7fb47..cf66bef34: 5 content commits, 11 distinct content
paths) were classified by hand. A naive range diff gets both
ranges wrong, twice:

- *The version carriers ride in the release commit itself.* The
  latest release commit touches exactly five paths — the
  changelog, `pyproject.toml`, `runner/_version.py`,
  `runner/ops/install.py` and the version-pinning test — so a
  range diff flags key handling (install.py, which mints the
  install-time secret) on every release there will ever be.
  Correction: the classifier reads content commits only. Release
  commits are excluded by their shape, and the carriers are
  named in the registry as release machinery.
- *The figure refresh rewrites the manuals mechanically.* The
  trains' statistics-refresh commits refill the generated figure
  slots in `AGENTS.md` and `PROTOCOL.md`, so a path-only rule
  flags protocol on most releases even when not one word of the
  protocol changed — in both measured ranges, PROTOCOL.md's
  changes were slot refills and nothing else. Correction: for a
  file that carries figure slots, the classifier reads the
  changed lines; if every changed line is a slot line, the path
  is recorded as a figure refresh and takes no class, and any
  other changed line gives the file its normal classes.

With both corrections, the two measured ranges flag no class at
all — true to their content, which was documentation and figures
only. As a control, a code-bearing range (the 24 paths behind
the release commit bfc7fb47) was classified the same way: the
registry flags
disclosure controls (`runner/ops/briefing.py`, what the Oracle
is told) and extension loading
(`runner/transport_extensions/email/`), and hand classification
agrees with both. The registry fires when there is something to
review and stays quiet when there is not.

Two scope decisions the measurement settled. Tests are not
classified by path: a test rides with its subject and stands in
the checklist's per-commit list, where the conductor sees it;
the class flags come from the paths that change the running
system. Documentation outside the protocol's own documents is
likewise unclassified — the classes name behaviour of the
running system — and likewise still listed per commit.

**Supposition 3 is settled by construction in this pass**: the
validator described below is built, and its unit tests carry
valid records, malformed records, and records whose reviewed
lines do not match the classes their own checklist declares.

## Design

### The candidate and its record

The gate's unit is the **candidate**: a full version and the
release commit it will be tagged on, produced by a release train
exactly as today. Each candidate gets one **candidate record**:
a markdown file generated by `runner/tools/release_gate.py`,
named for the full version, living at
`docs/infrastructure-documents/project/release-signoffs/<full version>.md`.
One file per release, never an append-shared file, so records
cannot collide the way desk.md's Gate 7 warns shared files do.
The record carries the checklist and, at its foot, the sign-off
block. In the enforcing phase (below) the signed record stands
committed on main before the tag is cut; in this pass nothing
requires it, and the trains run exactly as they do today.

### The checklist, in the order the conductor reads it

The order is deliberate: identity first, then the machine facts,
then the judgments only a human makes. Each item is one line to
read and, where the item is a fact, one line to transcribe from
the ship record.

1. **Candidate identity.** The full version, the release commit,
   the tag that will be cut, and the previous release commit the
   range is measured from. The tag must name the commit the
   record names; a record for any other commit is a record for a
   different candidate.
2. **The range at a glance.** Every content commit in the range,
   listed with its subject; release commits excluded by shape.
   Dark landings in the range are named here, from the landing
   record, so item 7 can be answered from this list.
3. **Builds and publication.** The main build green on the exact
   release commit; the tag build green; the publish jobs
   successful; the release published, draft=false, with its full
   asset set. Transcribed from the ship record.
4. **The stamp check.** The wheel, the sdist and the platform
   tarball, each re-downloaded and matched against the release's
   sums: three match lines, transcribed from the stamp folder's
   result.
5. **The fresh measure.** The version's token component was
   recounted fresh on the tree being shipped, and the figure
   refresh stands committed as the last content commit before
   the release commit — or the skip is recorded here with its
   reason (the ship lane's clone was shallow), never guessed
   around.
6. **The changelog.** The release's changelog section covers
   every content commit listed at item 2. Nothing landed is
   missing from the record of what shipped.
7. **Dark landings.** Each dark landing named at item 2 is
   either activated deliberately for this release or ships dark
   on purpose; the record says which, per landing.
8. **Class reviews.** One line per class the range touched, as
   classified by the registry below: the conductor records
   `Reviewed: <class>` for each. Classes the range did not touch
   are printed by the generator as not touched and ask nothing.
9. **The state of main.** One of the two forms in the next
   section: the tip is green, or the protected-candidate form
   with the red tip acknowledged.
10. **The sign-off.** The block below, filled and signed.

### The seven classes and their path families

The registry is declared in the tool's code, in a fixed format,
and reproduced here so the design can be read without the code.
A path in two families asks for both reviews; over-inclusion is
intended.

| Class | Path families |
|---|---|
| Protocol | `PROTOCOL.md`; `docs/ietf/`; `runner/wire/` |
| Execution | `runner/runner.py`; `runner/ops/` execution modules (`exec.py`, `main.py`, `startup.py`, `poll.py`, `handlers.py`, `cli.py`) |
| Key handling | `runner/wire/jobcrypto.py`, `runner/wire/mlkem.py`; `runner/ops/install.py`; `runner/guard/confval.py`; `runner/config.example.json`; `runner/cloud/` |
| Confinement | `runner/guard/sandbox.py`; `runner/ops/posture.py`; the shipped sandbox policy (`docs/steady/security/homing_pigeon.te`, `docs/steady/security/homing-pigeon.service`) |
| Job-user behavior | Any file whose name carries `job_user` or `job-user`; `runner/ops/posture.py` |
| Extension loading | `runner/extensions/`; `runner/transport_extensions/`; `runner/ops/extensions.py`; `runner/ops/extsources.py`; `runner/guard/extreview.py`; `runner/tools/pin_extension_sources.py` |
| Disclosure controls | `runner/oracle/`; `runner/guard/security.py`; `runner/ops/briefing.py`; `runner/tools/make_briefing.py`; `runner/tools/disclosure.py` |

Two standing exceptions, both measured above: release commits
are not classified at all, and a slot-only change to a
figure-carrying file is a figure refresh, not a class event.

### The protected candidate: shipping while main is red

Desk.md's rule stands: the only thing a red main ever blocks is
a tag, and new work is cut from the recorded last-green. This
path makes that rule signable. When main's tip is red at ship
time:

- The candidate is pinned to the **recorded last-green commit** —
  never the red tip, and never a commit whose green exists only
  in one lane's local run.
- The record states the tip's commit, that it is red, and the
  red guard families or divergences by name, as the ship record
  knows them. A candidate record that hides the red tip is a
  false record.
- The class range is measured to the candidate — what actually
  ships. The commits between the candidate and the red tip are
  listed separately in the record with their classes flagged as
  **deferred**: they are not in this release, and they will ask
  for their reviews again at their own.
- The sign-off verdict takes its protected form (below), so the
  signature itself says the signer knew main was red and shipped
  the pinned candidate anyway.
- No tag is cut on any commit other than the signed candidate's.

### The sign-off block and its validation

The record ends with a block in exactly this shape:

```text
## Sign-off

- Version: <full version, four components>
- Release commit: <40 lowercase hex characters>
- Candidate: standard | protected
- Conductor: <the conductor's name or title>
- Date: <YYYY-MM-DD>
- Verdict: signed | signed (protected candidate) | not signed
- Reviewed: <class>
- Reviewed: <class>
```

The validator (`release_gate.py check-signoff`) fails closed on:
a missing or duplicated field; a version that is not four
numeric components (a shortened version is a false record); a
commit that is not a full SHA; a candidate form that disagrees
with the verdict form (a protected candidate signed with the
standard verdict, or the reverse); a class the checklist
declares touched with no matching reviewed line; a reviewed
line for a class the range did not touch — the copy-paste
signature of a record filled from the previous release's; and a
date that is not an ISO date. A `not signed` verdict is a valid
record: the gate's answer can be no, and the record of the no
stands the same way.

## What lands in this pass, and what waits on the conductor

Landed with this document, as documentation and tooling only:

- This design.
- `runner/tools/release_gate.py`: the candidate-record
  generator (the checklist above, classes classified from a git
  range), the sign-off template, and the sign-off validator.
  Advisory and invoked, never ambient — the approval guard's
  discipline. It is wired into nothing: no hook, no workflow, no
  train reads it, and no ship waits on it.
- `runner/tests/test_release_gate.py`: the unit tests — the
  registry held shut, the two measured corrections (release
  commits excluded; slot-only changes are refreshes), checklist
  rendering, and the validator's accept and refuse cases.

What waits on the conductor, by design — the gate is his hand,
and these are the points where only his hand fits:

1. **The signature itself.** Each release's sign-off is the
   conductor's own act. No lane can sign for him, and the record
   format has no field for a delegate.
2. **The word to enforce.** Directing the release trains to
   refuse a tag when no valid signed record for the candidate
   stands on main. Until that word is given, the trains run as
   they do today and the gate is a practice, not a block.
3. **The workflow guard.** Adding a sign-off check to the tag
   workflow's guards, beside the tag-exists, carrier-agreement
   and build-green guards it already runs. A change to release
   machinery, taken at his word, not a lane's.
4. **The open policy choices.** Whether a class review may be
   accepted from a named seat's reading instead of the
   conductor's own; whether one signature may cover a batch of
   candidates cut together; and whether the records' home named
   here — the release-signoffs drawer in the project documents —
   is where he wants them kept.
5. **The protected verdict.** Whether the protected-candidate
   form is acceptable as designed, since it puts his signature
   on a release shipped while main is red.
