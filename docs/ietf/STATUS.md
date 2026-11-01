# Internet-Draft status

<!-- Agent-Stamp: a4faf750-7222-4aca-9d25-2c4333483334 -->

Both Homing Pigeon Internet-Drafts are posted and live on the IETF
datatracker, and the request to publish them as Informational RFCs
has gone to the Independent Submissions Editor (ISE).

## Posted

| Draft | Title | Datatracker |
|---|---|---|
| draft-slutsky-homing-pigeon-00 | Homing Pigeon Message Protocol, Version 1 | https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon/ |
| draft-slutsky-homing-pigeon-v2-00 | Homing Pigeon Message Protocol, Version 2: Determinations, Questions, and Shared Context | https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon-v2/ |
| draft-slutsky-homing-pigeon-01 | Homing Pigeon Message Protocol, Version 1 | https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon/01/ |
| draft-slutsky-homing-pigeon-v2-01 | Homing Pigeon Message Protocol, Version 2: Determinations, Questions, and Shared Context | https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon-v2/01/ |

- Stream: Independent Submission, category Informational.
- Both drafts confirmed and posted by 29-OCT 10:52PM PDT, ahead of the
  IETF-127 submission cutoff.
- Both drafts expire 3 May 2027 unless a new revision is posted first.
- The -01 revisions of both drafts were posted on 1 November
  2026, also inside the IETF-127 cutoff: submission status
  171592 for version 1 and 171593 for version 2.
- The -01 revisions remove the mentions of PROTOCOL.md from
  both drafts. Repository file names do not belong in an
  Internet-Draft.
- The datatracker now expects -02 as the next revision of each
  draft. The deferred edits — the em dashes and the subject-gap
  ABNF below — ride -02.
- Sources and renders live beside this file: the kramdown-rfc `.md`,
  the submitted `.xml`, the `.txt` and `.html` renders, and the idnits
  output for each draft.

## Discussion

Review of either draft is welcome in the repository's GitHub
Discussions: https://github.com/Pigeon-Home/homing-pigeon/discussions

Comments that land there feed the -02 revision. Posts by AI agents
are welcome alongside posts by people.

## Sent

- 29-OCT 10:56PM PDT: request to rfc-ise@rfc-editor.org for
  Informational publication of draft-slutsky-homing-pigeon-00 and
  draft-slutsky-homing-pigeon-v2-00 via the Independent Submission
  stream.

## The plan

From 29-OCT 11:50PM PDT, these two posted drafts are the plan. An
earlier launch plan is retired. Do not revive it, and do not name
its venue, in this tree. Older notes keep the words they were
written with.

IETF 127 is 14-20 November 2026. That is two weeks from this note,
and it is not a wait. The Internet-Draft submission cutoff for that
meeting is 2 November 2026, 23:59 UTC. Both -00 drafts were posted
on 30 October, inside that cutoff.

## Waiting on

These move when the other party moves. They are not a hold on the
work in Next.

1. The ISE's acknowledgment of the request.
2. Reviewer assignment by the ISE.
3. IESG conflict review (RFC 5742), once the ISE accepts the drafts.

## Next

- Answer reviewer and ISE questions by email, when they come.
- The known nits below are the text of -02. Do not hold that
  revision until a reviewer asks. Do not edit the submitted -00
  files: the datatracker has those bytes, and this tree does not
  silently diverge from them. -01 is a new revision beside them,
  uploaded by the author. Version 1 is still published first;
  version 2's normative reference becomes that RFC's number.
- A new revision is also due before 3 May 2027, or the drafts expire.
- Update this file when any item above moves.

## Known nits, for that revision

idnits 3.3.0 was run offline on 2026-10-30 (`*.idnits.txt` beside
the drafts). The downref and status errors are that run: the host
could not reach the RFC editor. What is left when those are set
aside:

- The author `organization` element is empty. An independent author
  is "Independent", or the element is left out.
- Six em dashes in version 1 and four in version 2. idnits asks that
  each one be needed. An ASCII hyphen is the dull fix.
- `[HOMING-PIGEON]` is the subject token. idnits reads the brackets
  as a missing reference. It is not one.
- Version 2 references version 1 normatively. A document is not
  published before a draft it cites that way, so version 1 is
  published first and version 2's reference becomes that RFC's
  number.
- Each XML render carries one no-break space, from the tool.

These are the edits for -02. The subject token is not one of them,
and neither is publishing version 2 ahead of version 1.

## The subject gap, for that revision (30-OCT)

A substantive -02 edit, not a nit. Section 6 of version 1 (and the
subject text version 2 inherits) writes the gaps between subject
words as `SP`, which in RFC 5234 is exactly one %x20, and `word` as
one or more visible characters. The implementations do not do that,
and should not: an email subject that was folded in transit unfolds
to runs of spaces and tabs (RFC 5322 section 2.2.3), and a receiver
that insisted on one %x20 would drop a legal job. The runner and
the hosted queue's gate both read a gap as one or more characters
of one explicit set, the ECMAScript WhiteSpace and LineTerminator
code points, since 30-OCT (`runner/wire/subject.py`, PROTOCOL.md
section 2; the two implementations used to differ on
the information-separator controls and a subject routed on one
side and not the other). -02 says what they do. The ABNF, over
Unicode code points as RFC 3987 writes them:

~~~
job-subject    = marker *( gap word ) gap "job" gap job-id
result-subject = marker *( gap word ) gap ( "result" / "qresult" ) gap job-id
marker         = "[HOMING-PIGEON]"
gap            = 1*gap-char
gap-char       = WSP / %x0A / %x0B / %x0C / %x0D / %xA0 / %x1680
               / %x2000-200A / %x2028 / %x2029 / %x202F / %x205F
               / %x3000 / %xFEFF
word           = 1*word-char
word-char      = %x21-10FFFF ; any code point that is not a gap-char
~~~

with `job-id` as -00 already constrains it, and the sentence that
goes with the grammar: a control character other than those listed
is part of a word, not a gap between two, so `[HOMING-PIGEON]<US>job
x` names no job. The match is still a search, case-insensitive, and
`Re:` or other words before the marker are still fine. `word-char`
excludes the gap set by the prose; a reader that wants it closed in
ABNF writes the ranges out.
