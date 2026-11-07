# Deferred -02 items reconciled against the -04 working drafts: one approval delta

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

## What this document is

This is the single delta document for the "-02 edits" that were
asked for covering ONLY two things, across both drafts
(draft-slutsky-homing-pigeon, version 1, and
draft-slutsky-homing-pigeon-v2, version 2):

1. the deferred em dash fixes, and
2. the subject-gap ABNF edit.

Every change is shown exactly as it would appear, before and
after, so the whole document can be approved or refused with
one yes or one no. Nothing in this document edits any draft.
It is a proposal and a reconciliation record only.

## The numbering mismatch, stated plainly

The request was framed against the -01/-02 text. That framing
no longer matches the live line:

- Both drafts stand at -03 POSTED on the IETF site
  (version 1: submission 171771; version 2: submission 171786,
  both on 2 November 2026).
- The -04 working drafts were already cut on main (commit
  b6a7277a, "cut the -04 working drafts from the posted -03
  texts") applying the CHECKLIST-04 draft-word items. They
  stand in each draft's `source/` folder and have not been
  submitted.

This delta is therefore written against the CURRENT line: the
-04 working drafts. Reconciling the two requested item groups
against that line gives the result this document is built on:

- Every em dash fix in the request was already carried into
  the -02 revisions, stands in the posted -03 texts, and
  stands in the -04 working drafts. Part 1 shows each one and
  marks it ALREADY APPLIED. None of them is a proposed change.
- The subject-gap ABNF edit was likewise carried into -02,
  stands in -03, and stands in -04. Part 2 shows it and marks
  it ALREADY APPLIED.
- Exactly ONE limb of the later subject-grammar proposal in
  `notes/delta-03.txt` was never carried into any posted or
  working revision: the `job-id` rule. That limb is the single
  PROPOSED CHANGE in this document (item S4). A yes approves
  that one change, to be made to the -04 working drafts only.
  A no leaves the -04 working drafts exactly as they stand.

## Sources

The items below are taken from the project's own records, and
each status was verified directly against the -04 working
draft files on main:

- `docs/ietf/status.md` -- the "Known nits" list ("Six em
  dashes in version 1 and four in version 2. idnits asks that
  each one be needed. An ASCII hyphen is the dull fix.") and
  "The subject gap, for that revision (30-OCT)", which defines
  the subject-gap ABNF edit; the same file records that both
  -02 revisions "replace the em dashes with hyphens" and that
  version 1's -02 "states the subject-gap ABNF".
- `docs/ietf/notes/delta-02.txt` -- the recorded -01 to -02
  diff for both drafts, which shows each em dash replacement
  and the subject grammar replacement as they were made.
- `docs/ietf/notes/delta-03.txt` -- the proposed -02 to -03
  delta whose "subject grammar" section proposes closing
  `word-char` in ABNF and rewriting the `job-id` rule.
- The CHECKLIST-04 record (27 items; Lane F, Phase 2) and
  `docs/ietf/notes/checklist-04-applied.md` -- item 3 guards
  the posted subject grammar in -04 with no change;
  items 12 and 11 govern the version 2 subject-conventions
  sentence and its unpinned citation in -04.
- `docs/infrastructure-documents/design/v1-v2-sentence-review.md`
  -- the sentence-by-sentence review of the -03 texts: rows
  V1-033, V1-034 and V1-036 settle the Section 6 grammar, and
  its "Local drafts" section records that the living version 1
  draft still gives the subject grammar "in its pre--02
  single-SP form".
- `docs/infrastructure-documents/design/v3-sentence-review.md`
  -- row 34 treats version 1 Section 6's `job-id-char` as the
  standing form the version 3 alphabet is identical to.

Verification counts, made on the files named: the living
drafts (`source/draft-homing-pigeon-00.md` and
`source/draft-homing-pigeon-v2-00.md`) contain exactly 6 and
exactly 4 em dash characters respectively -- the counts in the
status file's nit list. The -04 working drafts
(`source/draft-slutsky-homing-pigeon-04.md` and
`source/draft-slutsky-homing-pigeon-v2-04.md`, and their
`.txt` renders) contain 0 em dash characters each, as do the
posted -02 and -03 sources.

## Part 1 -- the em dash fixes (all ALREADY APPLIED)

Each item: the passage as it stands in the living draft (the
pre-fix text; `notes/delta-02.txt` records the same passages
against the -01 submitted text), then the passage as it stands
in the -04 working draft. The only change in each pair is the
em dash (U+2014) replaced by a spaced ASCII hyphen " - ", the
fix the status file's nit list prescribes. Where an -04 passage
also differs in some other word, that difference is another
item's work, already landed, and is noted under the item; it
is not part of this delta.

### Version 1 -- 6 em dashes in 5 passages

E1. Abstract, the cleartext-acceptance sentence (1 em dash).

Before:

> a receiver refuses a cleartext job unless the operator has
> explicitly enabled cleartext acceptance — in the reference
> software, only by a command-line parameter.

After (in -04):

> a receiver refuses a cleartext job unless the operator has
> explicitly enabled cleartext acceptance - in the reference
> software, only by a command-line parameter.

Status: ALREADY APPLIED (in -02; stands in -03 and -04). The
-04 abstract's signature sentence differs from the living
draft's for a different reason -- CHECKLIST-04 item 1 -- and
is not part of this item.

E2. Section 16.1, the plaintext sentence (1 em dash).

Before:

> The plaintext is the complete signed job body in its
> Section 7 form — the payload object with the signature
> spliced in.

After (in -04):

> The plaintext is the complete signed job body in its
> Section 7 form - the payload object with the signature
> spliced in.

Status: ALREADY APPLIED (in -02; stands in -03 and -04).

E3. Section 16.1, the transmitted-body sentence (1 em dash).

Before:

> The transmitted body is a JSON envelope object, signed
> exactly as Section 7 specifies — the MAC covers the
> envelope as transmitted:

After (in -04):

> The transmitted body is a JSON envelope object, signed
> exactly as Section 7 specifies - the MAC covers the
> envelope as transmitted:

Status: ALREADY APPLIED (in -02; stands in -03 and -04).

E4. Section 16.2, step 2 (1 em dash).

Before:

> 2. The envelope's MAC is verified — step 5 applied to the
> envelope. On failure, reject as step 5 specifies.

After (in -04):

> 2. The envelope's MAC is verified - step 6 applied to the
> envelope. On failure, reject as step 6 specifies.

Status: ALREADY APPLIED (the em dash fix in -02; stands in
-03 and -04). The step number differs (5 in the living draft,
6 in -04) because CHECKLIST-04 item 20 restated the Section 14
step order in -04; that renumbering is not part of this item.

E5. Section 16.2, step 3 (2 em dashes).

Before:

> 3. Decrypt. Any failure — an unknown `alg`, a malformed
> member, a tag mismatch — is a rejection with no result,
> marked seen, as in step 5.

After (in -04):

> 3. Decrypt. Any failure - an unknown `alg`, a malformed
> member, a tag mismatch - is a rejection with no result,
> marked seen, as in step 6.

Status: ALREADY APPLIED (the em dash fixes in -02; stand in
-03 and -04). The step number difference is the same
CHECKLIST-04 item 20 renumbering as in E4.

### Version 2 -- 4 em dashes in 2 passages

E6. Section 1, the first gap (2 em dashes).

Before:

> A runner that expects a job to fail — because the box is
> hot, the disk is failing, or the same job failed an hour
> ago — has no way to say so until the result returns.

After (in -04):

> A runner that expects a job to fail - because the box is
> hot, the disk is failing, or the same job failed an hour
> ago - has no way to say so until the result returns.

Status: ALREADY APPLIED (in -02; stands in -03 and -04).

E7. Section 1, the fallback paragraph (2 em dashes).

Before:

> Realizing a runner does not support version 2 — because no
> version 2 message ever arrives from it, or because the
> operator says so — is not an error and needs no machinery:

After (in -04):

> Realizing a runner does not support version 2 - because no
> version 2 message ever arrives from it, or because the
> operator says so - is not an error and needs no machinery:

Status: ALREADY APPLIED (in -02; stands in -03 and -04).

No other em dash item exists in the records named above:
CHECKLIST-04 contains no em dash item at all, and the two
sentence reviews record none. The 6 + 4 passages above are
the whole of the requested em dash group.

## Part 2 -- the subject-gap ABNF edit

### S1. Version 1, Section 6 -- the gap grammar (ALREADY APPLIED)

The edit defined in `docs/ietf/status.md` under "The subject
gap, for that revision (30-OCT)": the gaps between subject
words were written as `SP` (in RFC 5234, exactly one %x20) and
`word` as one or more visible characters; the edit states the
gap as one or more characters of one explicit set, the
ECMAScript WhiteSpace and LineTerminator code points, because
a folded email subject unfolds to runs of spaces and tabs
(RFC 5322, Section 2.2.3) and a receiver that insisted on
exactly one %x20 would drop a legal job.

Before (the pre--02 text, as the living draft still gives it):

> A job subject matches this pattern, in the sense of a
> search, not a full-string match:
>
> ~~~
> [HOMING-PIGEON] (SP word)* SP job SP job-id
> ~~~
>
> `word` is one or more visible characters. `job-id` is one
> or more visible characters with no space, further
> constrained below. The words between the marker and `job`
> are decoration. `TEST` is a legal decoration.
>
> A result subject matches:
>
> ~~~
> [HOMING-PIGEON] SP result SP job-id
> ~~~
>
> ABNF for the identifier only:
>
> ~~~
> job-id      = 1*128 job-id-char
> job-id-char = ALPHA / DIGIT / "." / "_" / "-"
> ~~~

After (as it stands in the -04 working draft, Section 6):

> A job or result subject matches this grammar, in the sense
> of a search, not a full-string match. The grammar is ABNF
> {{RFC5234}} written over Unicode code points in the style
> of {{RFC3987}}. A gap is one or more characters of one
> explicit set, not the single character SP: an email subject
> that was folded in transit unfolds to runs of spaces and
> tabs ({{RFC5322}}, Section 2.2.3), and a receiver that
> insisted on exactly one %x20 would drop a legal job. The
> set is the ECMAScript WhiteSpace and LineTerminator code
> points:
>
> ~~~
> job-subject    = marker *( gap word ) gap "job" gap job-id
> result-subject = marker *( gap word ) gap ( "result" / "qresult" )
>                gap job-id
> marker         = "[HOMING-PIGEON]"
> gap            = 1*gap-char
> gap-char       = WSP / %x0A / %x0B / %x0C / %x0D / %xA0 / %x1680
>                / %x2000-200A / %x2028 / %x2029 / %x202F / %x205F
>                / %x3000 / %xFEFF
> word           = 1*word-char
> ; every code point that is not a gap-char
> word-char      = %x00-08 / %x0E-1F / %x21-9F / %xA1-167F
>                / %x1681-1FFF / %x200B-2027 / %x202A-202E
>                / %x2030-205E / %x2060-2FFF / %x3001-FEFE
>                / %xFF00-10FFFF
> job-id         = 1*128 job-id-char
> job-id-char    = ALPHA / DIGIT / "." / "_" / "-"
> ~~~
>
> A control character other than those listed in `gap-char`
> is part of a word, not a gap between two, so
> `[HOMING-PIGEON]<US>job x` names no job. The words between
> the marker and `job` are decoration. `TEST` is a legal
> decoration.

Status: ALREADY APPLIED. The gap grammar was carried into
-02 in exactly this shape except for the `word-char` rule
(see S2), stands in the posted -03, and stands in -04, where
CHECKLIST-04 item 3 guards it ("KEEP POSTED", no -04 change)
and the applied record notes one production fix only: the
result-subject line, 77 columns wide in the posted -03 text,
is wrapped in the -04 source as shown above so the rendered
text has no over-long line. That wrap is the only difference
between the -03 and -04 forms of this grammar.

### S2. Version 1, Section 6 -- the `word-char` closure (ALREADY APPLIED)

`notes/delta-03.txt` proposed, for -03, closing `word-char`
in the ABNF itself instead of leaving the gap-set exclusion
to the prose, and deleting the sentence that asked the reader
to close it.

Before (the -02 form):

> ~~~
> word-char      = %x21-10FFFF ; any code point that is not a gap-char
> ~~~
>
> `word-char` excludes the gap set by the prose of this
> section; a reader that wants it closed in ABNF writes the
> ranges out.

After (as it stands in the -04 working draft):

> ~~~
> word           = 1*word-char
> ; every code point that is not a gap-char
> word-char      = %x00-08 / %x0E-1F / %x21-9F / %xA1-167F
>                / %x1681-1FFF / %x200B-2027 / %x202A-202E
>                / %x2030-205E / %x2060-2FFF / %x3001-FEFE
>                / %xFF00-10FFFF
> ~~~

and the "excludes the gap set by the prose" sentence is gone;
the control-character sentence that followed it stands, as
shown in S1.

Status: ALREADY APPLIED (in the posted -03; stands in -04).
The status file's -03 entry records it: "the word-char
grammar is closed as the complement of the gap set".

### S3. Version 2, Section 5 -- the inherited subject conventions (ALREADY APPLIED)

Version 2 has no subject ABNF of its own; it inherits
version 1 Section 6. The subject-gap edit reached version 2
through that inheritance in -02. The sentence that states the
inheritance was itself narrowed in -04 under CHECKLIST-04
item 12 (living correction F-V2-2 in the sentence review:
version 1 Section 6 defines job and result subjects only, so
the posted sentence over-inherited), with the citation kept
unpinned under item 11.

Before (the posted -03 sentence):

> the subject conventions of draft-slutsky-homing-pigeon
> Section 6, with the message type in the subject;

After (as it stands in the -04 working draft, Common Form):

> the marker and gap conventions of
> draft-slutsky-homing-pigeon Section 6, with the message
> type in the subject as Sections 6, 7, and 8 of this
> document specify;

Status: ALREADY APPLIED (in -04, CHECKLIST-04 item 12, per
`notes/checklist-04-applied.md`). No version 2 ABNF change
was requested or exists in the records: the version 2
subjects themselves (`[HOMING-PIGEON] determination
<msg_id>`, `question <msg_id>`, `answer <msg_id>`) are
unchanged in every revision.

### S4. Version 1, Section 6 -- the `job-id` rule (THE ONE PROPOSED CHANGE)

The same "subject grammar" section of `notes/delta-03.txt`
that S2 came from also proposed rewriting the `job-id` rule.
That limb was NOT carried into -03 (the status file's -03
entry names only the `word-char` closure) and is NOT in -04.
It is the only item in the requested groups that is still
open, and it is the only change a yes to this document
approves.

Before (as it stands in the -04 working draft, Section 6):

> ~~~
> job-id         = 1*128 job-id-char
> job-id-char    = ALPHA / DIGIT / "." / "_" / "-"
> ~~~

After (exactly as `notes/delta-03.txt` proposes it; the
`job-id-char` rule is deleted):

> ~~~
> job-id         = 1*128 word-char
> ~~~

Nothing else in Section 6 changes. The prose that stands
around the grammar is untouched, including "`job-id` MUST
NOT be `.` or `..`."

Basis, as the record states it (`notes/delta-03.txt`): the
reference subject pattern accepts any non-gap token as the
identifier -- in `runner/wire/subject.py` the identifier is
the complement of the gap set -- so a colon in an id is a job
in the code and was not a job in the -02 grammar; the
proposed rule uses the same characters as a word, capped at
128; the reference does not enforce the 128 cap, and that
enforcement is not part of the proposal.

The contrary record, stated as plainly: CHECKLIST-04 item 3
says the posted subject grammar -- including this `job-id`
rule -- is KEPT with no -04 change, and the sentence review
settles the current rule as holding (row V1-036: "`job-id` is
1 to 128 characters of ALPHA / DIGIT / "." / "_" / "-";
subject grammar and job-id validation in verify), with the
version 3 review (row 34) treating `job-id-char` as version
1's standing form. The original -02 subject-gap edit in the
status file also kept the identifier as it was: "with
`job-id` as -00 already constrains it". This item is
therefore a decision the records argue both ways, which is
why it is put on its own: it is not presented as a correction
the records agree on.

Effect of a yes: the two lines above are replaced by the one
line above in the version 1 -04 working draft
(`source/draft-slutsky-homing-pigeon-04.md`) and the draft is
re-rendered and re-checked there, as the -04 cut was. Version
2 has no `job-id` rule of its own and needs no edit for this
item. Effect of a no: nothing changes anywhere.

## What a yes does not do

- Nothing is submitted to the IETF. The -04 working drafts
  remain local working drafts either way.
- The living version 1 and version 2 drafts are not edited.
  Under the mirror rule they match the posted IETF text
  exactly, and they stay that way.
- No other draft text changes: not the trim list in
  `notes/trim-02.md`, not any CHECKLIST-04 item, not the
  version 3 draft.
- The code is not changed. Item S4's proposal, as recorded
  in `notes/delta-03.txt`, is a draft-text change only; the
  128-character cap it keeps is a grammar statement the
  reference does not enforce, exactly as that record says.

## Items not found

For completeness, what the records do NOT contain, so that
nothing here rests on an invented item:

- No em dash fix beyond the 6 version 1 and 4 version 2
  passages in Part 1 appears in any of the records named
  under Sources. CHECKLIST-04 has no em dash item.
- No subject-gap ABNF item for version 2 beyond the
  inheritance sentence in S3 appears in the records;
  version 2 defines no subject ABNF of its own in any
  revision.
- No record names any further deferred item in either
  requested group. The deferred set is Part 1, S1, S2 and S3
  (all already applied) and S4 (the one proposed change).
