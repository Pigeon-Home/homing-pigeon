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

## Measurement and conclusions

_To be filled by the measurement, in the same place, before the
design is finalized._

## Design

_To be written from the conclusions._

## What lands in this pass, and what waits on the conductor

_To be written from the conclusions._
