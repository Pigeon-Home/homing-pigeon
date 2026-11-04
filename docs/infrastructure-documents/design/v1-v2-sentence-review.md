# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

# Sentence review: Homing Pigeon versions 1 and 2 (the -03 texts)

This record is the Phase 2 companion to `docs/design/v3-sentence-review.md`.
Same method as that pass: the two drafts were read sentence by sentence,
every checkable statement was extracted into a ledger row, and each row
was settled against the code and tests on main, against deterministic
machine checks wherever the claim is mechanical, against the other
drafts, and against the cited RFCs. Base head for this pass: main at
394015cb (the Phase 1 landing), so the version 3 text under comparison
is the Phase-1-corrected text.

Rules of this phase, which differ from Phase 1 and were followed
exactly. The phase began under a highlight-only rule; a rule change
from the owner superseded it mid-pass, and both are recorded here so
the record shows what governed:

- As first given: no changes to the version 1 or version 2 drafts
  (posted at the IETF at -03, submissions 171771 and 171786); every
  inconsistency highlighted here and set aside; no code changes
  arising from version 1 / version 2 findings alone; and the standing
  exception — a version 1 or version 2 finding that proves a
  statement in the version 3 draft wrong corrects version 3 (evaluated
  for every finding; outcome in the "Effect on version 3" section).
- As changed: the repository holds two kinds of draft files. The
  IETF submission files — every `draft-slutsky-homing-pigeon-*.md`
  and `draft-slutsky-homing-pigeon-v2-*.md` at -00 through -03, with
  their renders — are frozen and stay byte-identical. The LOCAL
  working drafts — `docs/ietf/draft-homing-pigeon-00.md` (version 1)
  and `docs/ietf/draft-homing-pigeon-v2-00.md` (version 2), the same
  role the version 3 local draft plays for version 3 — are the living
  text, and the corrections this pass proves land there, smallest
  change as in Phase 1, each recorded in the "Local drafts" section
  below alongside what remains set aside. No code changes, and no
  IETF submission, under either form of the rule.

## Headline results

- Version 1 ledger: 120 rows. Version 2 ledger: 66 rows. 186 rows
  in total.
- Verdicts across both ledgers (counted from the finished tables):
  holds 170, holds-with-note 8, inconsistency 8,
  unverifiable-from-here 0.
- Inconsistencies highlighted: 10 findings in the register below —
  the 8 rows that carry the verdict "inconsistency", plus 2 further
  findings (F-V1-3 and F-V1-5) whose rows carry holds-with-note
  because the statement is true in its own scope. Kinds across the
  10: stale citation 1, normative-strength mismatch 2,
  cross-document tension 2, internal tension 2, wording/editorial
  imprecision 3.
- Corrections under the rule change: 8 of the 10 findings are
  corrected in the local drafts (10 edits across the two files);
  F-V1-2 remains set aside as a decision for the -04 revision, and
  F-V1-6 has no counterpart sentence in the local draft. The
  version 1 local draft is also recorded as drifted well behind
  its -03 (its text is the -00-era text); both drifts are stated
  plainly in the "Local drafts" section.
- Effect on version 3: NO version 3 correction. The three near-misses
  that could have triggered the exception (the RFC 8446 citation, the
  single-use ticket strength, the hybrid "future work" sentence) were
  each examined against the version 3 text and each is dispositioned
  in the "Effect on version 3" section. Because no version 3 change
  arose, the Phase 1 record needed no companion entry.

## The defaults sweep (both drafts)

The Phase 1 worry was carried into this phase: the security-modes
default flip (since 3.15.137 every security mode reads ENFORCE when
unset; a box that cannot enforce refuses to start) postdates both
drafts. Every occurrence of "default" in both -03 texts was read and
settled (28 occurrences in version 1, 14 in version 2). Every one is a
default secret / key-selection default, a sending default (encrypted
by default), a binding default (email enabled by default, NATS subject
names, NATS broker authentication required by default), a value
default (timeout 300 / maximum 3600, disclosure tier "family", UDP
20220), a protocol term (the version 2 "local default"), or the
version 2 enablement defaults (deadline 0; version 2 off). Neither
draft states or depends on any security-modes default; neither draft
uses the words "enforce", "audit", "security mode", or "lockdown" as
a runner posture. The flip falsifies nothing in either draft. Rows
V1-003, V1-004, V1-022, V1-030, V1-032, V1-052, V1-079, V1-091,
V1-112, V2-035, V2-054, and V2-060 carry the individual settlements.

## The cross-reference sweep (both drafts)

A script numbered both drafts from their heading order and extracted
every "Section N" reference (125 references in version 1, 19 in
version 2). No reference points at a section that does not exist. The
two apparent misses resolve outside the document: version 1's
"Section 2.2" is RFC 5322 Section 2.2.3, and version 2's "Section 16"
is version 1's Section 16, named as such in its sentence. Every
load-bearing reference was also checked for topic match by hand: all
of version 2's references into version 1 (Sections 6, 7, 9, 14, 16)
land on the sections they name; version 1's internal references to
Sections 5, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17.3, 17.6, 18, 19,
19.2, 19.3, 19.4, 20, 22.1, and 22.5 land correctly. Two references
are imprecise without being wrong targets; they are findings F-V2-2
and (for topic strength, not target) F-V2-1 in the register.

## Inconsistency register

Each entry: the draft and section, the statement, the evidence, the
kind, and the disposition. Dispositions were written under the
highlight-only rule this phase began with ("set aside"); the rule
change recorded at the top of this file then moved most of them
into the local drafts. The per-finding outcome under the changed
rule — applied, set aside, or no counterpart — is in the "Local
drafts" section, which governs.

### F-V1-1 — version 1, References and Sections 19.2 / 20 — stale citation

Version 1 cites RFC 8446 (TLS 1.3, 2018) as a normative reference,
for the ciphersuite name in Section 19.2 and the EncryptedExtensions
message in Section 20. RFC 8446 was obsoleted by RFC 9846 (July 2026,
Standards Track, E. Rescorla) — the same defect Phase 1 fixed in the
version 3 draft. Kind: stale citation. Disposition: set aside for the
version 1 -04 revision; the citation, and the appendix numbering that
goes with it where used, moves to RFC 9846 there.

### F-V1-2 — version 1, Section 19.2 — normative-strength mismatch

"A resumed session ... the ticket SHOULD be single-use." The
reference engine treats resumption tickets as single-use on both
bindings (the ticket store in runner/wire/dtlsproto.py spends a
ticket on use), and the version 3 draft states single-use as a MUST
on its carriage. Version 1's SHOULD is weaker than both the
implementation it describes and the later document. Kind:
normative-strength mismatch (text weaker than code and than
version 3). Disposition: set aside; already recorded as a version 1
-04 question during the Phase 1 pass.

### F-V1-3 — version 1, Section 22.1 — statement overtaken in part

"A hybrid post-quantum key exchange is the known remedy and is
future work for this profile." True for this profile: the version 1
datagram wire is unchanged and offers no hybrid group. But the remedy
now exists one document over — X25519MLKEM768 (4588) is implemented
as a version 3 carriage profile option (main at 192fd424). A reader
of version 1 alone cannot learn that from this sentence. Kind:
cross-document tension (scoped truth, stale in the large). Verdict
in the ledger is holds-with-note; it is registered here because the
owner asked for inconsistencies to be highlighted, and this is the
one most likely to mislead a reader about the state of the work.
Disposition: set aside for -04, where the sentence can name the
version 3 carriage as the place the remedy landed.

### F-V1-4 — version 1, Abstract against Sections 5.2 and 14 — internal tension

The abstract says "The signature is the only authorization." The body
is more precise: the NATS binding stands two gates in series (broker
authentication REQUIRED by default, Section 5.2), and Section 14
step 10 lets LOCAL checks (audience, per-key policy) reject after the
MAC. The body's own statements are the accurate ones; the abstract's
sentence is the loose one. Kind: internal tension (abstract against
body). Disposition: set aside for -04.

### F-V1-5 — version 1, Sections 8 and 14 against version 2 — cross-document tension

Version 1: "`v` other than 1 MUST be rejected." A receiver that also
implements version 2 opens `v` = 2 messages — never as jobs, and
version 2 Section 5 states the interaction from its side. The
version 1 sentence is absolute because version 1 alone is its whole
world; the two documents together describe an overlay the version 1
sentence does not admit. Kind: cross-document tension, by design.
Disposition: set aside; a -04 wording can scope the sentence to
receivers that do not implement version 2.

### F-V2-1 — version 2, Section 5 against version 1 Section 11.1 — normative-strength mismatch

Version 2: a receiver "MUST drop a message outside it [the issued_at
window]" — its past window, "and at most five minutes into the
future". Version 1 Section 11.1 sets that future allowance for jobs
as a RECOMMENDED 300 seconds, a LOCAL-flavoured recommendation.
Version 2 states the reference's value as a MUST for its messages.
The code applies one function to both (runner.py `_issued_at_ok`:
past window from `max_job_age_sec`, default 3600; future bound
hard-coded at 300 seconds), so behaviour is uniform; only the
normative strength differs between the two documents. Kind:
normative-strength mismatch. Disposition: set aside for the
version 2 -04 revision.

### F-V2-2 — version 2, Section 5 — cross-reference imprecision

Version 2 messages take "the subject conventions of
draft-slutsky-homing-pigeon Section 6". Version 1 Section 6's ABNF
defines job and result subjects only; the determination, question,
and answer subjects are defined in version 2's own Sections 6, 7,
and 8, using the same marker and gap conventions but not the
version 1 grammar. The conventions are inherited; the grammar is
not. Kind: wording/editorial imprecision. Disposition: set aside
for -04.

### F-V2-3 — version 2, Sections 7 and 8 — wording against the code

"`msg_id` in the reference software is `q.` plus the job id,
truncated so the identifier stays safe" (and the parallel sentence
for answers). The reference `_msg_id` in runner/wire/protocol_v2.py
does not merely truncate: past the 128-character cap it keeps a head
of the job id plus a 16-hex-digit SHA-256 digest of the whole id —
the code comment records why (plain truncation let two job ids that
differed past the cut share one question and one answer slot). The
draft's one word understates the mechanism that keeps the identifier
both safe and unique. Kind: wording/editorial imprecision.
Disposition: set aside for -04.

### F-V2-4 — version 2, Section 5 against Sections 11 and 12 — internal tension

Section 5: version 2 messages "are addressed to the job's
`reply_to`, never to the mailbox a runner polls for jobs, except
where the deployment's bindings make the two the same". Sections 11
and 12 describe the motivating deployment — the answer-only laptop
and the constrained runner sharing a mailbox a process polls for
questions, with "another reader of the same mailbox" answering. The
exception clause is what keeps Section 5 true, and for the
deployment the document exists for, the exception is the common
case. Kind: internal tension. Disposition: set aside for -04,
where the rule and its exception can trade places.

### F-V1-6 — version 1, Section 20 — wording against the document's own terminology

"A sender MUST NOT add members to the disclosure object defined
above." The disclosure object has exactly one sender: the responder.
Everywhere else in the document "sender" unqualified means the
submitter-side sender of a job or message, so the sentence can be
read as binding the wrong party. The companion rule (a receiver MUST
ignore unrecognized members) is unambiguous and is what the
reference implementation does. Kind: wording/editorial imprecision.
Disposition: set aside for -04 ("A responder MUST NOT...").

## Effect on version 3

The exception rule was applied finding by finding. Three findings
were near-misses and are dispositioned here so the record shows the
exception was exercised, not overlooked:

- F-V1-1 (RFC 8446): version 3 cited RFC 8446 the same way, and
  Phase 1 already corrected version 3 to RFC 9846 and re-rendered.
  The version 1 finding confirms the Phase 1 fix; it proves no
  version 3 statement wrong — version 3 is the corrected side of
  this pair.
- F-V1-2 (ticket SHOULD): version 3's single-use MUST is a
  deliberate, carriage-specific strengthening, decided and recorded
  during the version 3 work (the v1 text's SHOULD against the
  carriage's MUST was dispositioned there as a version 1 -04
  question, not a version 3 defect). A weaker statement in
  version 1 does not falsify a stronger one in version 3.
- F-V1-3 (hybrid "future work"): version 1's sentence is scoped to
  "this profile" — the version 1 datagram profile, which indeed
  offers no hybrid group and whose wire is unchanged. Version 3's
  statements place the hybrid group on the version 3 carriage as a
  profile option, off by default. Both are true in their scopes;
  there is no contradiction to correct.

No other finding touches a version 3 statement: the remaining
findings are local to version 1's abstract and file binding, or to
version 2's window strength, subject provenance, identifier wording,
and addressing rule, none of which version 3 repeats.

Conclusion: Phase 2 causes no version 3 correction, no version 3
re-render, and no addition to the Phase 1 record.

## Local drafts: confirmation, drift, and the corrections applied

Which files are the local drafts. `docs/ietf/STATUS.md` speaks of
the `draft-slutsky-*` files as the posted sources and directs that
the submitted files not be edited; it does not name the two plain
files. The files themselves are plain-markdown texts — no kramdown
front matter, no renders beside them — each headed by its draft
name and a Document line naming draft-slutsky-homing-pigeon-00 and
draft-slutsky-homing-pigeon-v2-00 respectively. Under the owner's
rule change these two files, `docs/ietf/draft-homing-pigeon-00.md`
and `docs/ietf/draft-homing-pigeon-v2-00.md`, are the local working
drafts, and the corrections below were applied to them and to no
other draft file. Every `draft-slutsky-*` source and render was
hashed before and after this pass: all byte-identical.

The drift, stated plainly. The version 1 local draft has drifted
well behind its -03: its text is the -00-era text in plain form.
The differences that matter:

- Section 6 gives the subject grammar in its pre--02 single-SP
  form. The gap grammar of -02 and -03 (the ECMAScript gap set,
  written out as ABNF) is not in it.
- Section 8 cites PROTOCOL.md ("Senses"). Repository file names
  were removed from both drafts in -01.
- Sections 19, 20, and 22.3 specify the session greeting: the
  platform summary as the session's first application message,
  sent after the handshake authenticates the submitter. The -02
  and -03 text specifies the platform disclosure inside the
  handshake, as an extension in the responder's
  EncryptedExtensions — the design the code implements (ledger
  rows V1-008 and V1-110 settle the -03 form against the code).
- Section 18 states the document has no IANA actions and requires
  no TLS extension. The -03 text requests the platform_info code
  point and names 0xFFA0 as the interim Private Use value.
- Section 1.2 cites the companion draft with its revision
  (draft-slutsky-homing-pigeon-v2-00); -03 cites it without one.

The version 2 local draft stands at its -02 text for the citations
of version 1: the places that cite the version 1 draft cite
draft-slutsky-homing-pigeon-00, with the revision, where -03's
only change was to cite it without one. The rest of its text
matches -03 in every section this pass checked. That citation
difference is a submission-side edit, not one of this pass's
findings, and it was not applied here; it is recorded as drift.

No attempt was made to pull either local draft up to its -03.
That would substitute the submission text for the local text,
which this pass does not do. The corrections below were applied
only where the local draft carries the sentence they correct.

Corrections applied to the local drafts (one row per finding;
the register above carries the evidence for each):

| Finding | Local draft outcome |
|---|---|
| F-V1-1 (RFC 8446) | APPLIED, 2 edits in draft-homing-pigeon-00.md: the Section 19.2 ciphersuite citation now reads [RFC9846], and the Section 23.1 entry is the RFC 9846 entry (Rescorla, July 2026, DOI 10.17487/RFC9846). |
| F-V1-2 (ticket SHOULD) | SET ASIDE. Strengthening a SHOULD to a MUST is a decision for the -04 revision, not a correction of a false statement; the local draft keeps SHOULD. The implementation's single-use behaviour and version 3's MUST are on record in the register. |
| F-V1-3 (hybrid future work) | APPLIED in draft-homing-pigeon-00.md, Section 22.1: the sentence now reads that the hybrid exchange is future work for this profile and is specified, as an option, for the email carriage by the version 3 document (X25519MLKEM768). |
| F-V1-4 (abstract authorization) | APPLIED in draft-homing-pigeon-00.md, Abstract: "The signature is the only authorization" now reads "The signature is the object's only authorization: a binding may add a gate of its own (Section 5.2), but no gate replaces it." |
| F-V1-5 (`v` other than 1) | APPLIED in draft-homing-pigeon-00.md, Section 8: the bullet now carries the qualifier "(a receiver that implements the version 2 document opens version 2 messages under that document, never as jobs)". |
| F-V1-6 (Section 20 "sender") | NOT APPLIED — no counterpart. The local draft's Section 20 is the greeting text and contains no member-add rule; the finding stands against the -03 text only and is part of the drift recorded above. |
| F-V2-1 (future window) | APPLIED in draft-homing-pigeon-v2-00.md, Section 5: the window sentence now names "the future allowance of version 1 Section 11.1 (300 seconds in the reference software)" in place of the bare five-minute restatement. |
| F-V2-2 (subject conventions) | APPLIED in draft-homing-pigeon-v2-00.md, Section 5: the phrase now reads "the marker and gap conventions of draft-slutsky-homing-pigeon-00 Section 6, with the message type in the subject as Sections 6, 7, and 8 of this document specify". |
| F-V2-3 (msg_id "truncated") | APPLIED, 2 edits in draft-homing-pigeon-v2-00.md (Sections 7 and 8): the shortened form is now described as keeping a head of the job id plus a short digest of the whole id, so two different job ids never share one identifier. |
| F-V2-4 (addressing rule) | APPLIED in draft-homing-pigeon-v2-00.md, Section 5: the "never ... except" sentence is now two stated cases — addressed to the job's `reply_to`; where that address and the polled mailbox are the same, the receiver separates the messages by type before any job processing. The rule's meaning is unchanged. |

## Version 1 ledger

Evidence is stated in the shortest form that settles the row: a code
path, a constant, a test module, or the cross-reference sweep above.
"Spec-internal" means the statement defines protocol behaviour and
its settlement is internal consistency plus the receiver-processing
section that implements it.

| Row | Section | Statement | Evidence | Verdict |
|---|---|---|---|---|
| V1-001 | Abstract | Signed JSON job and result objects over a transport binding; on email, submitter sends one signed object to a mailbox, runner polls, verifies, executes, returns a signed result | runner/ops/mail.py pipeline; runner/wire/verify.py | holds |
| V1-002 | Abstract | "The signature is the only authorization" | Sections 5.2 and 14 step 10 qualify it; see F-V1-4 | inconsistency |
| V1-003 | Abstract | Per-job AEAD encryption is required: implementations MUST support it; the reference software sends encrypted by default | runner/wire/jobcrypto.py; runner/cloud/send_job.py line 709 (encrypts unless --cleartext) | holds |
| V1-004 | Abstract | A receiver refuses a cleartext job unless explicitly enabled; in the reference software only by a command-line parameter | --allow-cleartext is a CLI parameter; no config key (runner/ops/mail.py) | holds |
| V1-005 | Abstract | The store-and-forward bindings open no inbound listener | email/file/NATS transports poll or subscribe outbound only | holds |
| V1-006 | Abstract | The DTLS binding changes the binding, not the messages; a binding of version 1, not a new version | Section 19; runner/wire/dtlsproto.py carries the same envelopes | holds |
| V1-007 | Abstract | The shared secret is the session's external PSK; ephemeral-only key exchange, so sessions have perfect forward secrecy | dtlsproto.py: PSK_MODE_DHE_KE = 1, "the only mode this profile speaks" | holds |
| V1-008 | Abstract | The runner discloses a tiered, responder-chosen platform summary inside the handshake, in EncryptedExtensions | dtlsproto.py EXT_PLATFORM_CONFIGURATION = 0xFFA0; runner/wire/platformcard.py tiers | holds |
| V1-009 | Abstract | The DTLS binding is off unless the owner enables it; an addition, never a replacement | config.example.json transports comment: dtls "off unless enabled" | holds |
| V1-010 | 1 | Version negotiation is not a handshake; the message carries `v`; this document defines `v` = 1 only; a receiver that does not implement version 1 MUST reject | verify path rejects v other than 1 at receiver-processing step 7. The sentence is absolute in a document whose companion adds an overlay; see F-V1-5 | holds-with-note |
| V1-011 | 1.1 | Two things are established out of band: the mailbox address and the shared secret; neither is discovered from the mail | design of record; runner/cloud/send_job.py takes both as parameters | holds |
| V1-012 | 1.2 | Bindings are the email binding (Section 5), file (5.1), NATS (5.2), DTLS (19), platform disclosure (20) | cross-reference sweep; TOC of the -03 render | holds |
| V1-013 | 1.2 | The companion draft (version 2) is a different document: it specifies protocol version 2 and does not specify a binding | draft-slutsky-homing-pigeon-v2-03 read in full for this pass | holds |
| V1-014 | 1.2 | Job and result objects are the same objects on every binding, byte for byte; a receiver MUST NOT reject an object for carrying `v` = 1 on any binding | transports carry the identical envelope (file binding states the mapping explicitly) | holds |
| V1-015 | 1.2 | The reference implementation implements the bindings this document specifies, including DTLS | transports shipped: email, file, nats, dtls (plus queues, which the draft does not specify and the sentence does not exclude) | holds-with-note |
| V1-016 | 1.2 | The sender requires the shared secret to meet a minimum-entropy floor (Section 17.3); it binds version 1 senders and runners today | runner/guard/security.py line 203 (bits < 128 refused); send_job.py entropy estimator "on the sender as well as the runner" | holds |
| V1-017 | 1.2 | Layered behaviours ride in extra members (Section 8); the Section 13.2 guidance binds only where no disclosure policy is in force | Sections 8 and 13.2 state the same scoping | holds |
| V1-018 | 3 | PSK identity: the default secret's identity is `homing-pigeon`; an additional secret's is `homing-pigeon:` plus its `key_id` | dtlsproto.py IDENTITY_PREFIX = "homing-pigeon:" | holds |
| V1-019 | 3 | Ticket: the opaque resumption identity a runner issues in a NewSessionTicket | dtlsproto.py ticket issue/store | holds |
| V1-020 | 4 | Receivers MUST ignore unknown members (Section 8) and MUST still reject an unknown `v` or unknown job `kind` | Sections 8 and 12; verify path | holds |
| V1-021 | 5 | Conformance is per binding; no binding is mandatory; a conforming implementation offers at least one binding | spec-internal; transports are independently enableable | holds |
| V1-022 | 5 | The reference implementation enables the email binding by default | runner/config.example.json: "transports": ["email"], comment "email (the default...)" | holds |
| V1-023 | 5 | Object authentication (the MAC) attaches to the object, never the transport; no binding authentication satisfies or relaxes it | verify path runs the MAC on every binding | holds |
| V1-024 | 5 | On the email binding the mailbox provider is an intermediary that can read the object, so Section 16 carries confidentiality there | Section 16; jobcrypto | holds |
| V1-025 | 5 | IMAP and SMTP MUST be used over TLS; TLS 1.2 or higher; STARTTLS, where used, MUST be required and the peer certificate verified | reference mail path connects over TLS (IMAP4_SSL in runner/ops/setup.py; implicit TLS is the draft's stated preference); the STARTTLS policy limb is an implementation-facing rule not separately exercised in this pass | holds-with-note |
| V1-026 | 5 | The message MUST be rejected before the MAC if the raw RFC822 object exceeds the receiver's size cap; RECOMMENDED cap 4194304 octets; a cap of 0 means no limit; the cap is LOCAL | core applies max_job_bytes before verification (Phase 1 rows; default 4194304); file binding FILE_MAX_BYTES = 4 * 1024 * 1024 | holds |
| V1-027 | 5.1 | File binding: envelope mapping byte-for-byte the email form; a job is a regular file in the inbox; the name SHOULD be `<ident>.job.txt` but acceptance MUST NOT depend on it; links and directories are not read | runner/transport_extensions/file/__main__.py scan_jobs (directories skipped, symlinks refused unread) | holds |
| V1-028 | 5.1 | Acknowledgement is consumption: the taker moves the file into a sibling `done/` directory; files are never deleted by the binding | file/__main__.py: done directory inside the watched inbox, scan skips it; "sibling" reads as sibling of the files, the path is inbox/done | holds-with-note |
| V1-029 | 5.1 | The size cap of Section 5 applies to envelope files | FILE_MAX_BYTES = 4194304 in runner/transport_extensions/channel.py | holds |
| V1-030 | 5.2 | NATS: jobs on a jobs subject, reference default `homing-pigeon.jobs`; results on `homing-pigeon.results.<job_id>` | nats/__main__.py lines 332-335 (the two defaults) | holds |
| V1-031 | 5.2 | Core NATS is at-most-once; a job published with no runner subscribed is lost; recovery is the submitter's retry (Section 15) plus the seen-set | spec-internal; Section 15 states the same machinery | holds |
| V1-032 | 5.2 | Broker authentication is REQUIRED by default; a receiver MUST NOT consume jobs over an unauthenticated broker connection; relaxation only by explicit local setting | nats/__main__.py: two-gates posture logged; allow_unauthenticated is the named relaxation | holds |
| V1-033 | 6 | Subjects are matched case-insensitively; a preamble such as `Re:` MAY appear; the marker need not be first | runner/wire/subject.py search grammar | holds |
| V1-034 | 6 | The gap set is the ECMAScript WhiteSpace and LineTerminator code points, as tabulated | subject.py builds the same set (Phase 1 verified the identical set for version 3) | holds |
| V1-035 | 6 | The `job_id` in the subject MUST equal the `job_id` member; a mismatch MUST be rejected | receiver processing step 8 | holds |
| V1-036 | 6 | `job-id` is 1 to 128 characters of ALPHA / DIGIT / "." / "_" / "-"; MUST NOT be `.` or `..` | subject grammar and job-id validation in verify | holds |
| V1-037 | 7 | Line endings are normalized before signing and verifying (CRLF to LF, then CR to LF); trailing whitespace is not part of the signed octets | runner/wire/verify.py _normalize | holds |
| V1-038 | 7 | `sig` MUST be last; the receiver finds it as the last occurrence of `,"sig":"`; 96 hex digits follow, then `"` and `}` | verify.py _extract_signed implements the stated search | holds |
| V1-039 | 7.1 | The MAC is HMAC-SHA-384; the key is the UTF-8 octets of the shared secret, never hashed or derived; `sig` is 48 octets as 96 hex digits; senders MUST use lowercase; receivers compare in constant time after case mapping | verify.py MAC path; send_job emits lowercase | holds |
| V1-040 | 7.2 | The compare covers all 96 digits and MUST NOT stop at the first difference in a timeable way; a reject log SHOULD NOT record the expected digest | constant-time compare in verify.py | holds |
| V1-041 | 8 | Unknown members MUST be ignored, except `v` other than 1 (rejected), `type` other than `job` on a job (rejected), `kind` other than exec or ping (not executed) | verify and dispatch path | holds |
| V1-042 | 8 | The reference receiver rejects any other `kind` except `sensor_alert`, which it files as a signed alert and never executes | runner/ops/extensions.py builds and files sensor_alert envelopes | holds |
| V1-043 | 9 | Common members table: `v` REQUIRED integer 1; `type` REQUIRED job or result; `job_id` REQUIRED; `key_id` OPTIONAL; `aud` OPTIONAL; `sig` REQUIRED | verify path member checks | holds |
| V1-044 | 9 | `aud`: enforcement is LOCAL; `runner_id` is accepted as its older spelling; when both are present `aud` is the claim | verify.py check_audience (reads aud, falls back to runner_id) | holds |
| V1-045 | 9 | An unknown `key_id` MUST be rejected before the MAC is computed; the receiver MUST NOT try another secret | verify_body_keyed raises on unknown key before crypto | holds |
| V1-046 | 10 | Key selection: absent `key_id` selects the default; a present string in the map selects that secret; otherwise reject without computing a MAC | verify_body_keyed selection order | holds |
| V1-047 | 10.1 | The fingerprint is `k-` plus the first eight lowercase hex digits of SHA-384 over the label `homing-pigeon key id v1\n` and the secret's UTF-8 octets | KEY_ID_LABEL = b"homing-pigeon key id v1\n" in runner/guard/security.py, runner/cloud/send_job.py, runner/ops/install.py | holds |
| V1-048 | 10.1 | The reference receiver registers the fingerprint as a further identifier for the default secret; one secret MAY have several identifiers; two secrets MUST NOT share one | key_names machinery; handlers use all names of a key | holds |
| V1-049 | 10.1 | The fingerprint is 32 bits of a one-way function over a secret of at least 128 bits of entropy (Section 17.3); publishing the name discloses nothing a signed message does not | arithmetic of the construction; Section 17.3 floor | holds |
| V1-050 | 10.1 | The fingerprint is not a PSK identity unless the operator stored that string as a `key_id` | dtlsproto identity construction (Section 3 settlement, V1-018) | holds |
| V1-051 | 11 | Job members table: `issued_at` REQUIRED; `kind` REQUIRED exec or ping; `script` / `script_url` for exec; `script_sha384` 96 lowercase hex; `interpreter` and `args` arrays; `env` object; `files` per 11.4 | job validation in verify / mail path | holds |
| V1-052 | 11 | `timeout_sec`: positive integer; RECOMMENDED default 300; RECOMMENDED maximum 3600 | runner/guard/defaulted.py default_timeout_sec (300, 1, None); exec.py clamps timeout to at most 3600 | holds |
| V1-053 | 11.1 | `issued_at` MUST carry a timezone designator; a value without one, or unparseable, MUST be rejected | ops/mail.py rejects naive or unparseable issued_at | holds |
| V1-054 | 11.1 | The receiver MUST reject when age exceeds its past window; RECOMMENDED past window 3600 seconds, LOCAL | ops/mail.py: max_age from max_job_age_sec, default 3600 | holds |
| V1-055 | 11.1 | The receiver MUST reject `issued_at` too far in the future; RECOMMENDED future allowance 300 seconds | ops/mail.py and runner.py _issued_at_ok: age < -300 rejected | holds |
| V1-056 | 11.2 | `reply_to`: a single address, at most 254 characters, `local@domain`, domain contains a dot; if absent or invalid the result goes to the runner's own mailbox and the job is not rejected | reply_to validation and result routing in the mail path | holds |
| V1-057 | 11.2 | The result address comes only from `reply_to`; the `From` and `Reply-To` headers MUST NOT select it | mail path takes the address from the member only | holds |
| V1-058 | 11.3 | `ping` carries no script and the runner MUST NOT start one; `exec` requires script or script_url; both present means script_url is used and script ignored | dispatch in handlers / exec path | holds |
| V1-059 | 11.3 | If `script_sha384` is present the receiver MUST hash the script octets with SHA-384 and reject on a differing digest | script hash check in verify path | holds |
| V1-060 | 11.3 | The script is written to a new file in a fresh directory for the job_id and run as interpreter, script file, args; on timeout the receiver MUST kill the process tree; an excessive timeout is reduced to the maximum, not rejected | exec.py job directory, process-tree kill, clamp at 3600 | holds |
| V1-061 | 11.4 | File elements: `name` REQUIRED, `url` REQUIRED https, `sha384` OPTIONAL; name MUST NOT be absolute, contain a `..` segment, or escape the job directory; downloads MUST use HTTPS; a digest mismatch MUST be rejected | file staging checks in the exec path | holds |
| V1-062 | 12 | A job rejected after the MAC verified (kind, script hash, file name) MUST produce a result with exit_code -2 and a reason in stderr, MUST be marked seen, MUST NOT be retried; a job rejected before the MAC produces no result | mail path post-verification reject builds the -2 result; pre-MAC reject sends nothing | holds |
| V1-063 | 13 | The result is signed with the secret that verified the job; `key_id` on the result MUST name that secret; the reference sender includes the job's identifier or the default fingerprint | result construction in ops/mail.py | holds |
| V1-064 | 13 | Result members table: completed_at, kind, exit_code, timed_out, stdout, stderr, both truncated flags, duration_sec, runner — all REQUIRED | result construction in ops/mail.py and ops/exec.py | holds |
| V1-065 | 13.1 | exit_code: 0 success or ping; -1 if and only if timed out (MUST be -1 when timed_out); -2 rejected before execution; otherwise the process status | exec.py: exit_code = -1 if timed_out else the return code | holds |
| V1-066 | 13.2 | Each stream MAY be cut at a LOCAL limit on the decoded text; RECOMMENDED limit 100000 characters; the truncated flags MUST track the cut | exec.py cuts the decoded, redacted text at max_output_bytes (default 100000) — the applied cut counts characters of the decoded string; the config key's name says bytes | holds-with-note |
| V1-067 | 14 | The seen-set key SHOULD be `job_id` prefixed by the configured `runner_id` when one is configured | verify.py _seen_key namespaces by runner_id | holds |
| V1-068 | 14 | The 16-step receiver processing order: subject, seen-set, size cap, key selection, MAC, parse, v/type, subject/member job_id, issued_at, LOCAL checks, kind dispatch, execute, build and sign result, stash before send, send | ops/mail.py and ops/handlers.py follow the stated order, including the Phase 1 flight-mail cap extension on the email binding | holds |
| V1-069 | 14 | Step 10: LOCAL checks (audience, per-key policy) MAY reject; whether a result is sent is LOCAL; the reference receiver sends no result for an audience failure | ops/mail.py line 132: audience failure goes to reject(), which sends no result — unchanged since the modes flip, under enforce as under audit | holds |
| V1-070 | 14 | An encryption envelope is processed inside the steps: decrypt after the envelope's MAC (step 5), re-enter at step 4, the body's own MAC verified again, `key_id` MUST match | jobcrypto / mail path envelope handling | holds |
| V1-071 | 15 | Execution is at most once; result delivery is at least once; a failed send is resent from the stash as the same octets; the job is never executed again for a send failure | stash-and-resend in ops/mail.py (step 15/16 settlement, V1-068) | holds |
| V1-072 | 15 | Two senses of "seen" are kept apart: a reject that produces no result MUST NOT enter the seen-set, so a forger holding a victim's `job_id` cannot block the genuine job | seen-set writes follow the stated rule in the mail path | holds |
| V1-073 | 16 | Per-job encryption is a required part of version 1; implementations MUST support receiving and decrypting; senders SHOULD encrypt; encryption MUST NOT fail silently into cleartext | jobcrypto; send path raises rather than falling back | holds |
| V1-074 | 16 | A receiver MUST NOT execute a cleartext job unless cleartext acceptance is explicitly enabled; in the reference software a command-line parameter, deliberately not a configuration setting; the MAC is verified before the form is considered, in every posture | --allow-cleartext CLI only; envelope handling verifies MAC first | holds |
| V1-075 | 16.1 | Construction: AES-256-GCM; key by HKDF with HMAC-SHA-384, IKM the selected secret's UTF-8 octets, salt the nonce, info "homing-pigeon job-encryption v1", output 32 octets | runner/wire/jobcrypto.py: _KDF_INFO = b"homing-pigeon job-encryption v1", HKDF with HMAC-SHA-384 | holds |
| V1-076 | 16.1 | Nonce 12 octets, freshly random per message; AAD is `job_id`, `key_id` (empty for the default), and the algorithm string, UTF-8, joined by single NUL octets in that order | jobcrypto construction | holds |
| V1-077 | 16.1 | The envelope is `{"hp_enc": {"alg": "aes-256-gcm/hkdf-sha384", "nonce", "ct"}}`; `ct` carries the 16-octet GCM tag appended, base64; `hp_enc` is a reserved member name | jobcrypto envelope build/parse | holds |
| V1-078 | 16.2 | A receiver MUST NOT attempt decryption before the MAC verifies; any decryption failure is a rejection with no result, marked seen; a receiver that does not implement the section rejects an envelope at step 7 | envelope handling in the mail path | holds |
| V1-079 | 16.3 | The result for an encrypted job SHOULD be encrypted in the same construction; the reference receiver exposes the policy as configuration and defaults to mirroring the job | ops/mail.py lines 249-253: encrypt_result mirrors the job unless job_encryption is set explicitly | holds |
| V1-080 | 16.4 | Per-job encryption provides NO forward secrecy: the key derives from the static shared secret, so compromise exposes every recorded encrypted job and result | statement of the construction in V1-075; true by construction | holds |
| V1-081 | 17.1 | A valid MAC is permission to run as the runner's account; the protocol defines no sandbox; LOCAL confinement MUST NOT be assumed by the submitter | statement of the security model; confinement is a local security-modes matter the draft does not promise | holds |
| V1-082 | 17.2 | With per-job encryption an observer learns the subject (the `job_id`), the timing, and the size, and nothing of the content; an enabled cleartext receiver logs each cleartext arrival | jobcrypto covers the body only; cleartext arrivals are logged in the mail path | holds |
| V1-083 | 17.3 | The secret MUST carry at least 128 bits of entropy, estimated as length times log2 of alphabet size; a sender MUST refuse to sign below the floor; the reference runner refuses to start below it | security.py line 203 (bits < 128 refused at startup); send_job.py estimator and refusal on the sender | holds |
| V1-084 | 17.4 | `From`, `Reply-To`, `Sender`, `To` MUST NOT satisfy the MAC or select `reply_to`; an invalid MAC MUST NOT cause any result to be sent | mail path: headers are not inputs to verification or routing | holds |
| V1-085 | 17.5 | Unknown key identifiers fail closed before the MAC, so a typo cannot verify under the default secret and MAC time is not an oracle for identifiers | verify_body_keyed (V1-045) | holds |
| V1-086 | 17.6 | Replay: the past window rejects stale `issued_at`; the seen-set rejects a repeated `job_id`; jobs MUST be safe to repeat | Sections 11.1 and 14/15 machinery as settled above | holds |
| V1-087 | 17.8 | The splitter uses the last `,"sig":"`; a string value containing that sequence will not verify as intended; senders MUST keep it out of values | verify.py _extract_signed takes the last occurrence | holds |
| V1-088 | 17.10 | An attacker who drops the result mail delays delivery only: the stashed result is resent, the job is not executed again; the protocol adds no separate ack | Section 15 settlement (V1-071) | holds |
| V1-089 | 18 | This document has one IANA action: a code point for `platform_info` in the TLS ExtensionType Values registry; the document value is TBD | the -03 text; the standing IANA record agrees (one action, Specification Required registry) | holds |
| V1-090 | 18 | Until assignment the document uses 0xFFA0, Private Use (first byte 255), not an assignment; 0xFE00 is not Private Use and is not this extension | dtlsproto.py EXT_PLATFORM_CONFIGURATION = 0xFFA0; registry ranges as stated | holds |
| V1-091 | 18 | No new port, service name, media type, or OID is required; UDP 20220 is a LOCAL default of the reference implementation, not a registered assignment | dtls listener port default in the DTLS transport; no registration exists | holds |
| V1-092 | 19 | On the DTLS binding the messages do not change; a session buys latency, confidentiality of the objects, and that confidentiality with forward secrecy; enabling it opens an inbound UDP listener, off unless an owner enables it | dtlsproto carries the same envelopes; listener exists only when "dtls" is in transports | holds |
| V1-093 | 19.1 | The submitter initiates; the runner never initiates a session to a submitter; one session carries any number of job and result messages in each direction | dtlsproto roles (client initiates, server listens) | holds |
| V1-094 | 19.2 | DTLS 1.3 only; DTLS 1.2 MUST NOT be negotiated | engine implements the 1.3 profile only | holds |
| V1-095 | 19.2 | Ciphersuite TLS_AES_256_GCM_SHA384 only; no other suite offered or accepted | engine suite constant 0x1302 (Phase 1 machine check) | holds |
| V1-096 | 19.2 | Authentication is pre-shared key only; certificates are not part of the profile in either direction; a secret below the entropy floor MUST NOT be offered as a PSK | engine is PSK-only (Phase 1: a certificate-shaped hello is refused with missing_extension) | holds |
| V1-097 | 19.2 | `psk_dhe_ke` only: the extension MUST offer mode 1 and MUST NOT offer mode 0; a responder MUST refuse a handshake that does not offer it; an ephemeral X25519 key share MUST ride every handshake, full or resumed | dtlsproto.py line 993 offers bytes([1, PSK_MODE_DHE_KE]); line 1439 refuses a peer offering no psk_dhe_ke. The hybrid group 4588 now exists as an engine-level option for the version 3 carriage, off by default; this sentence describes the version 1 profile, whose wire is unchanged | holds-with-note |
| V1-098 | 19.2 | Address validation: the responder MUST perform the HelloRetryRequest cookie exchange before allocating session state, and MUST NOT send any flight larger than the retry itself before the cookie returns; the cookie is stateless and bound to the initiator's address | dtlsproto cookie exchange; cookie key handling (Phase 1 rows) | holds |
| V1-099 | 19.2 | Both sides MUST negotiate the `connection_id` extension and MUST accept records under the negotiated IDs from a changed source address | engine negotiates connection IDs per RFC 9146 | holds |
| V1-100 | 19.2 | Handshake flights are retransmitted on the timers RFC 9147 specifies; duplicate or retransmitted handshake messages are consumed exactly once per handshake | engine retransmission timers (Phase 1: RFC 9147 defaults) | holds |
| V1-101 | 19.2 | Early data: none. 0-RTT MUST NOT be offered, sent, or accepted; epoch 1 keys are never derived | dtlsproto rejects 0-RTT outright (Phase 1 row) | holds |
| V1-102 | 19.2 | Resumption: a responder MAY issue a NewSessionTicket; a resumed session MUST use a fresh ephemeral key share and MUST be treated as a new session for platform disclosure | engine resumption path; Section 20 settlement (V1-113) | holds |
| V1-103 | 19.2 | "the ticket SHOULD be single-use" | the engine spends a ticket on use (single-use in fact), and version 3 states MUST on its carriage; see F-V1-2 | inconsistency |
| V1-104 | 19.2 | KeyUpdate: an implementation MUST NOT initiate it; a received update_requested SHOULD be answered as RFC 9147 requires; an implementation MAY instead ignore it | dtlsproto.py _handle_key_update (line 876): "this profile answers but never starts" | holds |
| V1-105 | 19.2 | A malformed or undecryptable datagram is dropped and logged; it MUST NOT be fatal to the listener or to any session but its own | engine drop-and-log handling | holds |
| V1-106 | 19.3 | Inside a session, application data is a stream of messages each framed by a four-octet big-endian length prefix; each message is the store-and-forward envelope form | dtlsproto framing | holds |
| V1-107 | 19.3 | A result produced after its session died cannot be delivered on it; the submitter re-asks on a fresh session and the seen-set makes the repeat safe | spec-internal with Sections 14/15 | holds |
| V1-108 | 19.4 | Per-job encryption is OPTIONAL on this binding; the Section 16 receiver rule is unchanged; receiver support of Section 16 remains REQUIRED on this binding as on every binding | engine/mail path: envelope support is unconditional; cleartext still gated by explicit enablement | holds |
| V1-109 | 20 | The disclosure pattern is the Configuration Payload of IKEv2 (RFC 7296): responder-chosen attributes inside the authenticated exchange, in the responder's flight | RFC 7296 Section 3.15 pattern; the draft names the lift | holds |
| V1-110 | 20 | An implementing initiator includes `platform_info`, empty, in its ClientHello; a responder MUST NOT send the extension to an initiator that did not offer it, nor in any other handshake message | engine: client offers the extension; server sends only to an offerer, in EncryptedExtensions (Phase 1 rows) | holds |
| V1-111 | 20 | The disclosure is responder-chosen; its tier is LOCAL configuration; the initiator cannot negotiate or widen it; this document defines no mechanism by which it could | platformcard tier_of reads local config only | holds |
| V1-112 | 20 | Tiers: `none` (no platform member), `family` (os_family, default_interpreter, protocol_versions; the reference default), `standard` (plus os_release, python_version), `full` (plus path_tools, a fixed bounded set) | platformcard.py TIERS and DEFAULT_TIER (family); Phase 1 machine check | holds |
| V1-113 | 20 | A resumed session is a new session for this section: the disclosure MUST be carried again, in the resumed handshake, under the tier in force at that time | engine sends the disclosure per handshake | holds |
| V1-114 | 20 | "A sender MUST NOT add members to the disclosure object defined above, and a receiver MUST ignore object members it does not recognize" | the disclosure's sender is the responder; unqualified "sender" reads against the document's own terminology (elsewhere the job sender is the submitter). See F-V1-6 | inconsistency |
| V1-115 | 21 | A conforming submitter for this binding implements the DTLS 1.3 profile itself and needs a UDP path, which is an environment property, not a code property; none of it is required of a store-and-forward-only submitter | statement of the deployment facts; consistent with Section 19 | holds |
| V1-116 | 22.1 | An implementation MUST NOT offer, accept, or fall back to `psk_ke`, including on resumption and including when a peer insists | dtlsproto refuses a peer offering no psk_dhe_ke (line 1439); mode 0 is never offered (line 993) | holds |
| V1-117 | 22.1 | "A hybrid post-quantum key exchange is the known remedy and is future work for this profile" | true for this profile (the version 1 wire offers no hybrid group); the remedy has since landed on the version 3 carriage (4588, main at 192fd424). See F-V1-3 | holds-with-note |
| V1-118 | 22.3 | The disclosure contains no identifiers beyond platform shape (no hostname, addresses, user names, or paths beyond tool presence); its richest tier names a fixed tool set; a future extension letting the initiator ask for more MUST NOT be added compatibly | platformcard build_card member sets per tier (V1-112) | holds |
| V1-119 | 22.4 / 22.5 | The cookie exchange keeps pre-authentication cost to one MAC verification per first hello and nothing larger than the retry flight is sent before it; session establishment MUST NOT be treated as job acceptance, nor session delivery of a result as its acknowledgement | dtlsproto cookie path; the signed result remains the only acknowledgement in the message layer | holds |
| V1-120 | 23.1 | Normative reference RFC 8446 (TLS 1.3) | RFC 8446 was obsoleted by RFC 9846 (July 2026). The remaining normative and informative references were checked and are current. See F-V1-1 | inconsistency |

## Version 2 ledger

| Row | Section | Statement | Evidence | Verdict |
|---|---|---|---|---|
| V2-001 | Abstract | Version 2 is an addition to version 1, not a replacement: every version 1 message keeps its meaning; version 2 adds three messages and one mechanism | runner/wire/protocol_v2.py: "Jobs stay version 1" | holds |
| V2-002 | Abstract | The additions are a determination, a question, an answer, and context segments that travel with these messages and with the version 1 result | protocol_v2.py message builders and segment() | holds |
| V2-003 | Abstract | A version 1 runner never sends a version 2 message and is unaffected; a version 2 submitter faced with a version 1 runner submits version 1 jobs and expects version 1 results | enablement is runner-side (V2-052); nothing in the v1 path emits v2 messages | holds |
| V2-004 | Abstract | There is no version negotiation and no handshake; the messages carry `v`, as in version 1 | protocol_v2 has no negotiation machinery; adaptation is by observation (Section 2 of the draft) | holds |
| V2-005 | Abstract | The motivating deployment is the constrained runner: deterministic local decision machinery, no language model; version 1 leaves it alone with unanswerable questions, version 2 lets it ask | should_ask requires oracle_mode "deterministic" (V2-027) | holds |
| V2-006 | 1 | Version 1's runner decisions are local: it verifies the signature and the further admission checks of version 1's Section 14 | version 1 Section 14 is Receiver Processing, which contains those checks (cross-reference sweep) | holds |
| V2-007 | 1 | The version 1 result may carry the runner's opinion as the `oracle_opinion` member, formed and frozen on the runner alone | v1 result construction carries oracle_opinion | holds |
| V2-008 | 1 (figure) | Decision table: admit or refuse is the runner's, on the signature and its own admission checks; what runs, finally, is the runner's always; no answer admits a job | protocol_v2.py: "Nothing here runs a job"; handlers never admit on an answer | holds |
| V2-009 | 2 | A version 2 runner MUST accept version 1 jobs and MUST answer them with version 1 results | the v1 path is untouched by enablement; v2 messages are additional | holds |
| V2-010 | 2 | A version 2 message is sent only when the operator has enabled version 2 on that runner (Section 11), and only ever concerns a job admissible under version 1 rules | outbound_for returns nothing unless enabled(cfg) | holds |
| V2-011 | 2 | Realizing a runner does not support version 2 is not an error and needs no machinery; the submitter falls back to version 1 with that runner | no fallback machinery exists in the code; behaviour matches the statement | holds |
| V2-012 | 3 | Determination: the runner's pre-execution statement of what it expects, frozen before the job runs and never revised afterwards | determination_for builds it from the pre-execution plan; nothing revises it | holds |
| V2-013 | 3 | Question: a question the local machinery would have put to a local model, sent instead because no local model is available; "The reference software asks only for an exec job, and only when its Oracle is deterministic" | should_ask: enabled, not answer_only, oracle_mode == "deterministic", kind == "exec" | holds |
| V2-014 | 3 | Answer: a signed reply to one question, identified by that question's identifier; the answerer is any holder of a trusted shared secret and need not be the job's submitter; one answer decides; a late or second answer is context | answer_for; store_answer first-answer rule (V2-034) | holds |
| V2-015 | 3 | Local default: every question has one; asking never leaves a decision unmade | question_for always carries local_default "proceed"; deadline path always produces segments | holds |
| V2-016 | 3 | Context segment: a signed, self-describing fragment carrying its author's identity and a seen-once identifier (Section 10) | segment() builds seg_id / by / kind / text | holds |
| V2-017 | 3 | Clean pass: a determination that the job is expected to proceed without incident; the runner's local policy defines the threshold; the protocol defines only that it exists | clean_pass(plan) in protocol_v2.py | holds |
| V2-018 | 4 | The exchange figure: determination ONLY if not a clean pass, ONLY if enabled; an answer never delays execution past the deadline; a determination and a question MAY travel in either order | outbound_for order and content; await_answer bounded by the deadline | holds |
| V2-019 | 5 | A version 2 message takes the subject conventions of version 1 Section 6, the signature and MAC of its Section 7, the per-job encryption of its Section 16, and the common members of its Section 9, with `v` = 2 | the MAC/encryption/common-member references land correctly (sweep); the subject-conventions limb is imprecise — version 1 Section 6's ABNF covers job and result subjects only. See F-V2-2 | inconsistency |
| V2-020 | 5 | A receiver that does not implement this document will reject a message carrying `v` = 2, as version 1 requires; senders MUST NOT send a version 2 message where a version 1 receiver is expected to process it as a job | v1 receiver processing step 7 rejects v other than 1 with no result | holds |
| V2-021 | 5 | Version 2 messages are addressed to the job's `reply_to`, never to the mailbox a runner polls for jobs, except where the bindings make the two the same | the exception carries the shared-mailbox deployments of Sections 11/12, which are the motivating case. See F-V2-4 | inconsistency |
| V2-022 | 5 | Every version 2 message names the job (`job_id`) and its own identifier (`msg_id`) and carries `issued_at` as in version 1; replay follows the version 1 seen-set discipline; a dry run records nothing; a question left for another reader is not recorded by the receiver that left it | validate() requires job_id, msg_id, issued_at; handlers: dry run records nothing; non-answerer leaves the question unseen (V2-058) | holds |
| V2-023 | 5 | A receiver MUST hold `issued_at` to the same window as a version 1 job — its past window, and at most five minutes into the future — and MUST drop a message outside it | the code applies the same function to both (runner.py _issued_at_ok, future bound 300 seconds); version 1 Section 11.1 states that allowance as RECOMMENDED. See F-V2-1 | inconsistency |
| V2-024 | 6 | A determination is sent only when the job is not a clean pass: a missing plan, or a plan with no findings and no repair, is a clean pass and sends nothing; a determination does not refuse the job and is not revised after execution | clean_pass(plan): missing plan is a pass; findings or repair_action are not; determination_for returns None on a pass | holds |
| V2-025 | 6 | Determination form: `v` integer 2; `type` determination; `msg_id` is `d.` plus the job id; `clean_pass` is false; `expect` is `fail` when the plan has findings and `unknown` when it does not but a repair was proposed; receivers also accept `proceed` | determination_for; _EXPECT = ("proceed", "fail", "unknown"); validate() accepts all three | holds |
| V2-026 | 6 | `why` is a string of 1 to 500 characters; it is data, not instructions, and a receiver MUST NOT treat it as any | validate(): why must be a non-empty string of at most _TEXT_CAP (500) | holds |
| V2-027 | 7 | The reference software sends a question only when version 2 is enabled, the process is not in answer-only mode, the Oracle mode is deterministic, and the job's kind is `exec`; a question never by itself refuses a job and does not delay execution past its deadline | should_ask checks exactly those four conditions | holds |
| V2-028 | 7 | Question form: `deadline_sec` an integer from 0 to 30; `question` a non-empty string of at most 500 characters; `local_default` a non-empty string of at most 64 characters; the reference software uses `proceed` | validate() question branch; _DEADLINE_CAP = 30; _TEXT_CAP = 500; question_for sets local_default "proceed" | holds |
| V2-029 | 7 | "`msg_id` in the reference software is `q.` plus the job id, truncated so the identifier stays safe" | _msg_id keeps a head plus a 16-hex SHA-256 digest past the cap, not a plain truncation. See F-V2-3 | inconsistency |
| V2-030 | 7 | The subject is `[HOMING-PIGEON] question <msg_id>`; signing and encryption are as in Section 6, with the object identifier `msg_id` | outbound_for builds that subject; the v2 mail path keys the envelope on the subject identifier | holds |
| V2-031 | 8 | The answerer is any holder of a shared secret the runner already trusts, optionally narrowed to a list of key ids (Section 11); the runner cannot tell which trusted holder produced the answer | answerer_allowed; handlers check the verified key's names only | holds |
| V2-032 | 8 | Answer form: `question_id` is the question's `msg_id`; `msg_id` is `a.` plus that question id, kept inside the safe-identifier limit; `answer` is a non-empty string of at most 500 characters; a runner MUST NOT execute it or treat it as admitting the job | answer_for; validate() answer branch. The identifier construction carries the F-V2-3 caveat | holds-with-note |
| V2-033 | 8 | One answer decides: the reference software records the first answer for a `question_id` and refuses to replace it; a file that is not a readable answer does not occupy the slot, so a crash while saving cannot keep a later answer out | store_answer / _publish_answer: link wins the slot or loses it; an unreadable file is moved aside and the slot retried | holds |
| V2-034 | 8 | A second answer, and any answer after the deadline, is context for a later decision (Section 10); it does not reopen the job and does not vote | _remember_other keeps later answers beside the winner, capped at eight, as late-answer material | holds |
| V2-035 | 9 | The runner sends the determination and question, then looks for an answer until `deadline_sec` elapses; the reference default is 0 — one look and no wait; the cap is 30 seconds | deadline_of: default 0, clamped to 0..30; await_answer waits only inside the deadline | holds |
| V2-036 | 9 | An answer is in time when filed at or before the question's sending moment plus `deadline_sec` plus one second of grace | await_answer classify(): received <= asked + deadline + 1.0 | holds |
| V2-037 | 9 | Time waiting for the question file to leave a channel outbox does not count against `deadline_sec`; that pause itself stops once `deadline_sec` has elapsed; the whole wait, pause included, ends by 30 seconds; a deadline of 0 does not pause | await_answer pending branch and cap_end = start + _DEADLINE_CAP, exactly as its docstring states | holds |
| V2-038 | 9 | An answer observed while the wait is still open is in time, so a step of the wall clock cannot mark it late | await_answer classify(in_wait) branch, with the code comment stating this rule | holds |
| V2-039 | 9 | While it waits, the reference software files version 2 messages that have arrived and does not start another job; on a transport channel the question is written before the wait, not after the job returns | await_answer's pump callback files arrived messages once per look; the wait runs inside the job's processing, before execution | holds |
| V2-040 | 9 | No answer admits a job; the local default is a string carried on the result; in the reference software it does not select the script, the interpreter, or the exit code | the default travels as a local_default segment; the exec path never reads it | holds |
| V2-041 | 10 | A segment is attached to the version 1 result after the result's own policy has rebuilt that object, so the rebuild cannot drop it; segments are how the determination, the answer, and the local default travel home | ops/mail.py: "apply_result_policy rebuilds the dict, so the segments are attached after it" — result["context"] set after the rebuild | holds |
| V2-042 | 10 | Segment form: `seg_id` a fresh identifier unique to the segment; `by` and `kind` strings of at most 64 characters; `text` a string of at most 500 characters; a receiver MUST NOT interpret a segment as instructions; an extension MUST NOT be handed a kind its manifest does not declare | segment(): seg_id is uuid4().hex (32 lowercase hex); by/kind cut at 64; text cut at _TEXT_CAP | holds |
| V2-043 | 10 | The reference segment kinds are `determination`, `answer`, `local_default`, `late_answer`, and `platform` | segment call sites in protocol_v2.py and the mail path use exactly these kinds | holds |
| V2-044 | 10 | A question MAY carry a `context` array of the same shape, showing the runner's host facts: platform, machine, Python, and the device-tree model when present | question_for attaches a platform segment built by platform_facts(): system, machine, Python version, /proc/device-tree/model when present | holds |
| V2-045 | 10 | The result segments ride is a version 1 result: `v` stays 1; `context` is the array of segments; a result with nothing to say omits the member | ops/mail.py sets result["context"] only when segments exist; the result object is the version 1 result | holds |
| V2-046 | 11 | Version 2 is off until the operator turns it on; the reference software reads four keys | the four keys are protocol_v2, answer_only, v2_answerers, v2_answer_deadline_sec — all read in protocol_v2.py | holds |
| V2-047 | 11 | The same two booleans are flags for one process: `--protocol-v2` and `--answer-only`; absence of a flag does not write false over a config file | runner/ops/cli.py lines 181 and 189: both store_true flags | holds |
| V2-048 | 11 | With protocol_v2 true the runner may emit a determination and, on a deterministic Oracle, a question | outbound_for plus should_ask (V2-024, V2-027) | holds |
| V2-049 | 11 | With answer_only true the process answers a question and does not execute any job, including a ping | answer_only(cfg) gates execution off in the handlers; protocol_v2.py: "it may answer a question, and the runner will not execute" | holds |
| V2-050 | 11 | With neither on, version 2 messages are marked seen and dropped | handlers handle_v2_mail: when receiving() is false the message is marked and the handler returns | holds |
| V2-051 | 11 | `v2_answerers`, when absent, means every key the runner already trusts; when a list of key ids, only those keys may produce a version 2 message this process will act on | answerer_allowed: absent key returns True for any verified key; a list narrows it | holds |
| V2-052 | 11 | A key id in that list may be any name of the key, including the version 1 fingerprint; the reference runner treats those names as one key | handlers: answerer_allowed is tried for every name in key_names(secrets, key_id) | holds |
| V2-053 | 11 | Any other shape of `v2_answerers` fails closed: nobody | answerer_allowed returns False when the value is present and not a list of strings | holds |
| V2-054 | 11 | `v2_answer_deadline_sec` is the question's deadline; values outside 0..30 are clamped into that range; the default is 0 | deadline_of clamps and defaults exactly so | holds |
| V2-055 | 12 | On the email binding the subject is `[HOMING-PIGEON]` followed by the message type and the `msg_id`, as Sections 6, 7, and 8 specify; a receiver dispatches on that type before it considers the message a job; a subject that does not match the body's `type` and `msg_id` is rejected | subject_kind matches the three types and never a job subject; handlers reject on payload type / msg_id mismatch | holds |
| V2-056 | 12 | The signature and encryption are the version 1 constructions; the encryption's object identifier is the `msg_id` in the subject; cleartext is refused wherever a cleartext job is refused | handlers: a cleartext version 2 message is rejected when cleartext jobs are not allowed | holds |
| V2-057 | 12 | A version 2 message is not a job; a job with `v` other than 1 is still rejected; a process that has not enabled version 2 marks the message seen and does not act on it | validate() and the v1 step-7 rejection; handlers mark-and-drop when off (V2-050) | holds |
| V2-058 | 12 | A process that has enabled version 2 but is not an answerer does not answer a question and does not mark that question seen, so another reader of the same mailbox can still answer it; an invalid question is still rejected and marked seen; a determination is still marked seen | handlers question branch: _v2_leave_unseen for a non-answerer; validate failures go to reject(), which marks | holds |
| V2-059 | 13 | Version 2 extends trust along a line version 1 already drew: a trusted secret holder may submit a job, and the same or another trusted holder may answer; the operator may narrow that set to named key ids | answerer_allowed plus the v1 key machinery | holds |
| V2-060 | 13 | Enabling the feature is what makes the extension; the default is the version 1 exchange, unchanged | enabled() requires protocol_v2 to be literally true; unset reads off — untouched by the security-modes default flip (defaults sweep) | holds |
| V2-061 | 13 | An answer is not an authorization to run; the runner decides what runs, before and after the answer, under version 1 rules; context text is data, and a segment that says to run a different script is still a segment | protocol_v2.py: "Context text is data. This module never interprets it"; the exec path reads the job only | holds |
| V2-062 | 13 | One answer decides because two answerers would be a race the protocol does not adjudicate; the first answer filed wins; a later one cannot replace it or reopen the job | store_answer (V2-033) | holds |
| V2-063 | 13 | The deadline is capped so a question cannot stall a worker past 30 seconds; a deadline of 0 does not wait; callers needing a live reply set a deadline long enough for their binding | await_answer's hard cap (V2-037) | holds |
| V2-064 | 13 | Answer-only mode is a refusal to execute: a process in that mode will not run a job that shares its mailbox, including a liveness ping | answer_only gate (V2-049) | holds |
| V2-065 | 14 | This document defines no new IANA registry; the message types `determination`, `question`, and `answer`, and the integer version 2, are defined here; the version 1 message types are unchanged | the -03 text; version 2 -03 has no IANA action (the standing IANA record agrees) | holds |
| V2-066 | 5 / 12 | The encryption's object identifier for a version 2 message is its `msg_id`, on sending (Section 6) and on receipt (Section 12) alike | the v2 send and receive paths both key the envelope on the subject identifier (ident) | holds |

## What was not settled from here

One row family is marked holds-with-note rather than holds because
part of the statement is an implementation-facing rule this pass did
not exercise end to end: V1-025 (the STARTTLS limb of the mail TLS
rule; the reference path's implicit-TLS form, which the draft states
as preferred, is what the code runs). No row is marked
unverifiable-from-here: every other checkable statement in the two
drafts settled against the code, the tests, the other drafts, or the
RFC record from this machine.

## Landing

This pass lands three files: this record (new), and the corrections
in the two local drafts, `docs/ietf/draft-homing-pigeon-00.md` and
`docs/ietf/draft-homing-pigeon-v2-00.md`. Every IETF submission
file — all `draft-slutsky-homing-pigeon*.md` sources at -00 through
-03 and their `.txt`, `.html`, `.xml`, and `.idnits.txt` renders —
was hashed before and after: all byte-identical. The version 3
draft and its renders are likewise untouched, per the "Effect on
version 3" section. Committed as Muse <muse@localhost> with the
Agent-Stamp trailer, pushed by hand, and verified at the remote
ref (ls-remote plus a content grep) in the same call as the push.
