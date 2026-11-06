# Which CHECKLIST-04 items the -04 drafts apply

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

The -04 revisions of the version 1 and version 2 drafts were cut on
2026-11-06 from the posted -03 texts (the frozen copies in each
draft's `submitted/` folder, byte-identical to the copies at
ietf.org) and placed in each draft's `source/` folder as local
working drafts. They have not been submitted. The living drafts in
`source/` were not edited: the mirror rule stands, and every change
below is in the new -04 files only.

The checklist is the 27 items of the Lane F record
(CHECKLIST-04: 15 known mirror differences, N1/N2, and G1-G10).
Item numbers below are that checklist's.

## Version 1: draft-slutsky-homing-pigeon-04

Applied as wording changes:

- Item 1 (abstract): the signature sentence now reads as the living
  draft's form -- the signature is the object's only authorization,
  a binding may add a gate of its own, and no gate replaces it. The
  section number the living draft's sentence carries was dropped:
  an abstract must not contain a section reference, and idnits
  flagged it as an error on the first -04 render.
- Item 5 (Section 8, the `v` bullet): the version 2 qualifier is
  added -- a receiver that implements the version 2 document opens
  version 2 messages under that document, never as jobs.
- Item 8 (Sections 19.2, 20, 22.3 and the references): the TLS 1.3
  citation moves from RFC 8446 to RFC 9846 everywhere. The checklist
  names Sections 19.2 and 23.1; Sections 20 and 22.3 cite the same
  entry, and a reference entry cannot be renamed under its
  citations, so all of them move together.
- Item 9 (Section 22.1): the hybrid sentence now says the remedy is
  future work for this profile and is specified, as an option, by
  the version 3 document (X25519MLKEM768) for the email carriage.
- Item 16 (N1, Section 20): option (a) taken. `runner_version` (the
  runner software's release string) is named as a member of the
  `standard` level, and of `full` through it. Basis: the reference
  builds the member into its standard and full platform cards when
  a caller supplies it; the ping path supplies it and the DTLS path
  does not yet, so the object definition now names the member the
  reference already produces at those levels.
- Item 18 (G1, Section 7): option (a) taken. Section 7 now
  documents the transport-inserted-control-character fallback: on a
  verification failure the receiver retries over the body with every
  control character (code point below 32) except the tab removed,
  and the sender is never required to sign a cleaned form.
- Item 19 (G2, Section 8): the `kind` sentence is scoped to a base
  version 1 receiver, and now says a receiver that implements the
  layered local features also executes the `recipe` and `change`
  kinds, only when the owner has configured them.
- Item 20 (G3, Section 14): the step order is restated to match the
  reference. The parse (bounded: nesting depth bounded, unpaired
  surrogates not well-formed) now precedes key selection, because
  the `key_id` is a member of the parsed object; the LOCAL checks
  that need only the verified object (audience, lone-surrogate, and
  the `max_script_bytes` size check) run at their own step before
  the `v`/`type`, `job_id`, and `issued_at` checks; the per-key
  policy step follows `issued_at`, as before. Cross-references to
  the renumbered steps (Sections 15, 16.2, and the Retry section)
  were renumbered to match.
- Item 21 (G4, Section 11.3): the clarification is added -- the
  clamping rule governs the receiver-wide maximum, a per-key policy
  is a separate LOCAL ceiling at which a job MAY be rejected, and a
  negative `timeout_sec` is clamped to 1 by the reference rather
  than rejected.
- Item 22 (G5, Sections 12 and 14): the draft-side option taken.
  Section 12 now names the two exceptions -- the `max_script_bytes`
  size check and the unpaired-surrogate check (Section 14, step 7)
  MAY reject without producing a result; the code is unchanged.

Guarded (the posted form kept; the living draft's form kept out):

- Item 2: no session greeting anywhere; the disclosure stays in the
  handshake's EncryptedExtensions.
- Item 3: the posted subject grammar stands (the gap set, the
  ECMAScript-derived set with %xFEFF, "result" and "qresult", the
  control-character rule).
- Item 4: the `sensor_alert` bullet names no file.
- Item 6: Section 18 keeps "This document has one IANA action."
- Item 7: the companion citation in Section 1.2 stays unpinned.

One production fix outside the checklist: the result-subject ABNF
line, 77 columns wide in the posted -03 text, is wrapped in the -04
source so the rendered text has no over-long line.

Render and check: kramdown-rfc 1.7.43, xml2rfc 3.35.0, idnits 3.3.0
offline. Text: 0 errors, 1 warning (the [HOMING-PIGEON] subject
marker read as a citation, as in every posted revision), 2 comments.
XML: 0 errors, 1 warning (text that looks like a document reference
in the Section 20 artwork, also in the -02 record), 2 comments. The
run is recorded in the draft's `source/` folder.

## Version 2: draft-slutsky-homing-pigeon-v2-04

Applied as wording changes:

- Item 12: Section 5 now borrows the marker and gap conventions of
  version 1 Section 6, with the message type in the subject as
  Sections 6, 7, and 8 of this document specify (the citation stays
  unpinned, per item 11).
- Item 13: the addressing rule is the two-case form -- messages are
  addressed to the job's `reply_to`; where the bindings make that
  address and the polled mailbox the same, the receiver separates
  them by type before any job processing.
- Item 14: the `issued_at` window names the future allowance of
  version 1 Section 11.1 (300 seconds in the reference software);
  the "five minutes" form is gone.
- Item 15: the `msg_id` shortening is stated in both places
  (Sections 7 and 8) in the head-plus-digest form.
- Item 24 (G7, Section 5): the addressing clarification is added to
  the same passage as item 13 -- determinations and questions are
  addressed to the job's `reply_to`; answers are addressed to the
  runner's own mailbox (or channel), because a question carries no
  `reply_to` of its own.
- Item 25 (G8, Section 10): the draft-side option taken. Section 10
  now states that the member limits bind what a sender produces
  (the reference sender truncates every field), and that on an
  incoming question the reference receiver structurally validates
  only `text`; `seg_id`, `by`, and `kind` of an incoming segment are
  not structurally validated. The code is unchanged.
- Item 26 (G9, Section 12): "not an answerer" is reworded to name
  the mode -- a process not in `answer_only` mode does not answer
  and does not mark seen; the `v2_answerers` list gates which keys'
  messages a process acts on, not whether the process answers.

Guarded (the posted form kept; the living draft's form kept out):

- Item 10: Section 1 carries no parenthetical list of the other
  message families.
- Item 11: the version 1 citations in the abstract and Sections 3
  and 5 stay unpinned.

Render and check: same tooling. Text: 0 errors, 2 warnings (the
normative reference to the version 1 draft, and the [HOMING-PIGEON]
marker), 1 comment. XML: 0 errors, 1 warning (the normative
reference), 2 comments. The run is recorded in the draft's `source/`
folder.

## Items with no -04 draft change

- Item 17 (N2): a code alignment, already landed on main before
  this cut (the send path's result-identifier scan uses the shared
  subject grammar; recorded in the Lane F record as landed in
  release 3.15.17.164).
- Item 23 (G6): a code alignment, already landed on main before
  this cut (the send path compares inner and envelope `key_id` in
  Section 10's sense; same record).
- Item 27 (G10): recorded only. The posted sentence "a dry run
  records nothing" stands in the -04 text unchanged. The checklist
  leaves the code side open: gate the model call in the version 2
  question branch on the dry-run flag, or state the exception in
  Section 5 if the call is intended. No code change was made in
  this pass.

## Version 3 source

The version 3 draft is exempt from the mirror rule; two verified
defects were fixed directly in its source, and a fresh idnits check
was run (2026-11-06, recorded in the source folder):

- The abstract named Sections 19 and 20 of version 1; an abstract
  must not contain section references (an error in the earlier
  recorded run). The section numbers are removed; the sentence is
  otherwise unchanged.
- The normative reference to the version 1 draft was defined in the
  front matter but never cited in the text (a warning in the same
  run). The Introduction now cites it where version 1 is introduced
  as the base document.

Fresh check result: text 0 errors, 3 warnings (the standing -00
local draft's date, the normative reference to a draft, and the
[HOMING-PIGEON] marker); XML 0 errors, 2 warnings, 64 comments, the
comments being the long-standing BCP14 boilerplate-tag notes. The
obsolete-TLS-citation error of the earlier run is also gone: the
draft already cites RFC 9846.
