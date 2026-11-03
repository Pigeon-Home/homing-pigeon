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
| draft-slutsky-homing-pigeon-02 | Homing Pigeon Message Protocol, Version 1 | https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon/02/ |
| draft-slutsky-homing-pigeon-03 | Homing Pigeon Message Protocol, Version 1 | https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon/03/ |
| draft-slutsky-homing-pigeon-v2-02 | Homing Pigeon Message Protocol, Version 2: Determinations, Questions, and Shared Context | https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon-v2/02/ |
| draft-slutsky-homing-pigeon-v2-03 | Homing Pigeon Message Protocol, Version 2: Determinations, Questions, and Shared Context | https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon-v2/03/ |

- Stream: Independent Submission, category Informational.
- Both drafts confirmed and posted by 29-OCT 10:52PM PDT, ahead of the
  IETF-127 submission cutoff.
- The current revision of version 1 (-03) expires 1 May 2027 and
  the current revision of version 2 (-03) expires 6 May 2027,
  unless a new revision is posted first.
- The -01 revisions of both drafts were posted on 1 November
  2026, also inside the IETF-127 cutoff: submission status
  171592 for version 1 and 171593 for version 2.
- The -01 revisions remove the mentions of PROTOCOL.md from
  both drafts. Repository file names do not belong in an
  Internet-Draft.
- The -02 revisions of both drafts were posted on 1 November
  2026: submission status 171736 for version 1 and 171737 for
  version 2. Version 1's -02 carries the platform disclosure
  inside the handshake, states the subject-gap ABNF, and
  requests the extension code point; both -02 revisions replace
  the em dashes with hyphens. The datatracker now expects -03
  as the next revision of each draft.
- The -03 revision of version 1 was posted on 2 November 2026:
  submission status 171771, "New version accepted." Version 1's
  -03 aligns the text with the running code: the disclosure
  object is exactly the object the code sends, the interim
  extension code point 0xFFA0 is named as Private Use pending
  assignment, the disclosure is sent only to an initiator that
  offered the extension, the word-char grammar is closed as the
  complement of the gap set, and the companion citation carries
  no revision number.
- The -03 revision of version 2 was posted on 2 November 2026:
  submission status 171786, "New version accepted." Its only
  changes are the companion citations: the 4 places that cited
  the version 1 draft at its -00 revision now cite it without a
  revision number. The datatracker expects -04 as the next
  revision of each draft.
- Sources and renders live beside this file: the kramdown-rfc `.md`,
  the submitted `.xml`, the `.txt` and `.html` renders, and the idnits
  output for each draft.
- The -01 renders, and the idnits runs for -01 and -02, were produced
  by Claude on 1 November (kramdown-rfc 1.7.43, xml2rfc 3.35.0, idnits
  3.3.0, offline) and landed on 2 November. The sources of those
  revisions have not changed since the render, so the files were taken
  as they stand. idnits reported 0 errors on each. The warnings that
  remain are not a reason to revise a posted draft: an em dash or a
  u-umlaut, a `[HOMING-PIGEON]` citation that is not a reference, one
  artwork line past 72 columns, and version 2's normative citation of
  the version 1 draft. The `/rfc/rfcN` links are how xml2rfc renders a
  reference that has no explicit target; the source does not need a
  change for them. Offline downref and status lines are lookups the
  host could not make.

## Version 3, local

Version 3 is not posted and will not be submitted for at least several
weeks. `PROTOCOL.md` links the local source
`draft-slutsky-homing-pigeon-v3-00.md`. There is no datatracker URL.

The carriage behavior in that draft is the behavior on `main`. Three
of its rules were taken from Claude's carriage pass on 2 November,
because each one closes a hole the earlier text left open:

- A bit-identical copy of a handshake flight re-posts the saved answer
  once. Further copies of those same bytes are dropped. That is the
  repair RFC 9147 Section 5.8.1 asks for, without letting a captured
  hello spend a mail per copy. A retransmission is a new record
  (RFC 9147 Section 5.2). It misses the digest cache and is not
  limited by the budget.
- The cookie is an HMAC under a key kept in the channel. Keeping that
  key is enough for a cookied ClientHello to survive a restart of the
  process. Traffic keys are not kept in order to save it.
- A held result leaves only inside the session that carried the job,
  or inside a later session under the same PSK identity that carries
  the same job ident again. A different identity using that ident is
  dropped. The identity is only as fine as the key directory: two
  peers that share one secret are one submitter, and distinct
  submitters are distinct keys. A mail session-id is not a submitter.
  That last sentence is the limit on the rule, not a second rule.
- The hold itself is kept on disk, as a `<ident>.session.txt` sidecar
  written when the job is delivered from the session, so a restart of
  the email process does not send the held result as ordinary mail on
  the next pass. An expiry of held results drops only the holds whose
  results it dropped; a hold whose job is still in flight survives
  another result's expiry.

Two further closures are in the same draft. A fragmented first
handshake is consumed and draws no HelloRetryRequest. The unaddressed
test shape is not fed to DTLS on a deployment mailbox.

The rendered `.txt`, `.html`, and `.xml` beside the version 3 source
were regenerated with the final-pass text (2-Nov-2026) and match the
source. idnits 3.3.0 has been run on the render; its report stands
beside the source as `draft-slutsky-homing-pigeon-v3-00.idnits.txt`.
It reports 3 errors -- the abstract's references to sections and to
version 1, and RFC 8446 listed as obsolete (succeeded by RFC 9846) --
all submission-time edits, recorded in the forum. Its other warning
is the tool reading the `[HOMING-PIGEON]` subject marker as a
citation, the same reading the version 1 reports carry.

## Discussion

Review of either draft is welcome in the repository's GitHub
Discussions: https://github.com/Pigeon-Home/homing-pigeon/discussions

Comments that land there feed the -03 revision. Posts by AI agents
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
