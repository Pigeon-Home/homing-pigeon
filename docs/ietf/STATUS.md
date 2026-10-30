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

- Stream: Independent Submission, category Informational.
- Both drafts confirmed and posted by 29-OCT 10:52PM PDT, ahead of the
  IETF-127 submission cutoff.
- Both drafts expire 3 May 2027 unless a new revision is posted first.
- Sources and renders live beside this file: the kramdown-rfc `.md`,
  the submitted `.xml`, the `.txt` and `.html` renders, and the idnits
  output for each draft.

## Sent

- 29-OCT 10:56PM PDT: request to rfc-ise@rfc-editor.org for
  Informational publication of draft-slutsky-homing-pigeon-00 and
  draft-slutsky-homing-pigeon-v2-00 via the Independent Submission
  stream.

## Waiting on

1. The ISE's acknowledgment of the request.
2. Reviewer assignment by the ISE.
3. IESG conflict review (RFC 5742), once the ISE accepts the drafts.

## Next

- Answer reviewer and ISE questions by email.
- Rev to -01 as review asks, and before 3 May 2027 so the drafts stay
  live. The submitted -00 is what the datatracker has; this tree does
  not silently diverge from it.
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

None of these is a reason to post -01 before a reviewer asks.
