---
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
# Render: kramdown-rfc draft-slutsky-homing-pigeon-v3-00.md > draft-slutsky-homing-pigeon-v3-00.kr.xml
#         xml2rfc --v2v3 draft-slutsky-homing-pigeon-v3-00.kr.xml -o draft-slutsky-homing-pigeon-v3-00.xml
#         xml2rfc --text --html draft-slutsky-homing-pigeon-v3-00.xml
#         idnits draft-slutsky-homing-pigeon-v3-00.txt
# Status: LOCAL DRAFT -- UNSUBMITTED. This -00 text is local working
#         text dated 2026-11-02. It has not been submitted to the
#         IETF, has not been posted to the Internet-Drafts directory,
#         and requests no IANA action (Section 15).
title: "Homing Pigeon Message Protocol, Version 3: DTLS 1.3 via Email"
abbrev: "Homing Pigeon v3"
docname: draft-slutsky-homing-pigeon-v3-00
category: info
submissiontype: independent
ipr: trust200902
date: 2026-11-02
v: 3
keyword: [DTLS, email, store-and-forward, perfect forward secrecy, platform_info]
stand_alone: yes
pi: [toc, sortrefs, symrefs]
author:
  - ins: "A. Slutsky"
    name: "Andrew Slutsky"
    organization: "Independent"
    email: "slutsky5544@gmail.com"

normative:
  I-D.slutsky-homing-pigeon:
    title: "Homing Pigeon Message Protocol, Version 1"
    author:
      - name: "Andrew Slutsky"
        ins: "A. Slutsky"
    date: 2026-11
    seriesinfo:
      Internet-Draft: draft-slutsky-homing-pigeon-03
  RFC2119:
    title: "Key words for use in RFCs to Indicate Requirement Levels"
    author:
      - name: "S. Bradner"
    date: 1997-03
    seriesinfo:
      RFC: 2119
      DOI: 10.17487/RFC2119
    target: https://www.rfc-editor.org/info/rfc2119
  RFC8174:
    title: "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words"
    author:
      - name: "B. Leiba"
    date: 2017-05
    seriesinfo:
      RFC: 8174
      DOI: 10.17487/RFC8174
    target: https://www.rfc-editor.org/info/rfc8174
  RFC8446:
    title: "The Transport Layer Security (TLS) Protocol Version 1.3"
    author:
      - name: "E. Rescorla"
    date: 2018-08
    seriesinfo:
      RFC: 8446
      DOI: 10.17487/RFC8446
    target: https://www.rfc-editor.org/info/rfc8446
  RFC5234:
    title: "Augmented BNF for Syntax Specifications: ABNF"
    author:
      - name: "D. Crocker"
      - name: "P. Overell"
    date: 2008-01
    seriesinfo:
      RFC: 5234
      DOI: 10.17487/RFC5234
    target: https://www.rfc-editor.org/info/rfc5234
  RFC4648:
    title: "The Base16, Base32, and Base64 Data Encodings"
    author:
      - name: "S. Josefsson"
    date: 2006-10
    seriesinfo:
      RFC: 4648
      DOI: 10.17487/RFC4648
    target: https://www.rfc-editor.org/info/rfc4648
  RFC7748:
    title: "Elliptic Curves for Security"
    author:
      - name: "A. Langley"
      - name: "M. Hamburg"
      - name: "S. Turner"
    date: 2016-01
    seriesinfo:
      RFC: 7748
      DOI: 10.17487/RFC7748
    target: https://www.rfc-editor.org/info/rfc7748
  RFC9146:
    title: "Connection Identifier for DTLS 1.2"
    author:
      - name: "E. Rescorla"
      - name: "H. Tschofenig"
      - name: "T. Fossati"
      - name: "A. Kraus"
    date: 2022-03
    seriesinfo:
      RFC: 9146
      DOI: 10.17487/RFC9146
    target: https://www.rfc-editor.org/info/rfc9146
  RFC9147:
    title: "The Datagram Transport Layer Security (DTLS) Protocol Version 1.3"
    author:
      - name: "E. Rescorla"
      - name: "H. Tschofenig"
      - name: "N. Modadugu"
    date: 2022-04
    seriesinfo:
      RFC: 9147
      DOI: 10.17487/RFC9147
    target: https://www.rfc-editor.org/info/rfc9147

informative:
  RFC5322:
    title: "Internet Message Format"
    author:
      - name: "P. Resnick"
    date: 2008-10
    seriesinfo:
      RFC: 5322
      DOI: 10.17487/RFC5322
    target: https://www.rfc-editor.org/info/rfc5322
  RFC8551:
    title: "Secure/Multipurpose Internet Mail Extensions (S/MIME) Version 4.0 Message Specification"
    author:
      - name: "B. Ramsdell"
      - name: "S. Turner"
    date: 2019-04
    seriesinfo:
      RFC: 8551
      DOI: 10.17487/RFC8551
    target: https://www.rfc-editor.org/info/rfc8551
  RFC9051:
    title: "Internet Message Access Protocol (IMAP) - Version 4rev2"
    author:
      - name: "A. Melnikov"
      - name: "B. Leiba"
    date: 2021-08
    seriesinfo:
      RFC: 9051
      DOI: 10.17487/RFC9051
    target: https://www.rfc-editor.org/info/rfc9051
  RFC10024:
    title: "Post-Quantum Traditional (PQ/T) Hybrid Key Agreement Mechanisms for TLS 1.3"
    author:
      - name: "K. Kwiatkowski"
      - name: "P. Kampanakis"
      - name: "B. Westerbaan"
      - name: "D. Stebila"
    date: 2026-08
    seriesinfo:
      RFC: 10024
      DOI: 10.17487/RFC10024
    target: https://www.rfc-editor.org/info/rfc10024
  RFC7296:
    title: "Internet Key Exchange Protocol Version 2 (IKEv2)"
    author:
      - name: "C. Kaufman"
      - name: "P. Hoffman"
      - name: "Y. Nir"
      - name: "P. Eronen"
      - name: "T. Kivinen"
    date: 2014-10
    seriesinfo:
      RFC: 7296
      DOI: 10.17487/RFC7296
    target: https://www.rfc-editor.org/info/rfc7296
  RFC9325:
    title: "Recommendations for Secure Use of Transport Layer Security (TLS) and Datagram Transport Layer Security (DTLS)"
    author:
      - name: "Y. Sheffer"
      - name: "P. Saint-Andre"
      - name: "T. Fossati"
    date: 2022-11
    seriesinfo:
      RFC: 9325
      DOI: 10.17487/RFC9325
    target: https://www.rfc-editor.org/info/rfc9325

--- abstract

This document specifies version 3 of the Homing Pigeon message
protocol. Version 3 is a transport extension to version 1
{{I-D.slutsky-homing-pigeon}}, not a replacement for it: every
version 1 message keeps its meaning, the version 1 job
acceptance gate is unchanged, and version 3 changes exactly one
thing -- the carriage of the version 1 DTLS session profile.

Version 1 defines a DTLS 1.3 session profile (its Sections 19
and 20): one cipher suite, a pre-shared key taken from the
protocol's shared secret, ephemeral Diffie-Hellman on every
handshake, and the platform_info disclosure carried in the
server's EncryptedExtensions. Version 1 binds that profile to
a live datagram path. This document binds the same profile to
the email binding: handshake flights and protected records are
carried as email messages over the store-and-forward mailbox,
so a session can be opened by an email, completed over further
emails, and then carry jobs and results inside it, with the
perfect forward secrecy of the version 1 profile intact on a
carrier that has no live path at all.

The objects carried inside the session remain version 1
objects: a job or a result inside a session is the version 1
object, unchanged, carrying the version value version 1
defines. The 3 of this document's title numbers this document
and its carriage; it is not a value of any object's version
field, and nothing in this document mints a version 3 object.
HP-DTLS/3, the frame header of Section 5.2, is a carriage
label whose digit is the carriage generation, not a protocol
version.

This document is a local, unsubmitted draft. It has not been
posted to the Internet-Drafts directory, and it requests no
IANA action (Section 15).

--- middle

# Introduction

Version 1's email binding is store-and-forward: a job object is
an email, a result object is an email, and either can wait in a
mailbox for as long as the mailbox keeps it. Version 1's DTLS
binding is the opposite shape: a live session over datagrams,
with handshake flights exchanged in seconds and records
protected by keys that exist only for that session.

Each binding gives up what the other has. The email binding
carries a job anywhere mail goes, including to a runner that is
only ever reachable through a mailbox, but the object crypto of
version 1 -- a signature and, by default, per-job encryption
under the shared secret -- provides no forward secrecy: the
shared secret is long-lived, and mail is stored. The DTLS
binding provides forward secrecy, because its session keys are
derived from an ephemeral exchange and erased with the
session, but it needs a live path, and a runner behind a
mailbox has none.

Version 3 carries the version 1 DTLS profile, unchanged,
over the email binding. What it removes is the
confidentiality side of the trade: a runner reachable only
through a mailbox gains the session's forward secrecy. What
it does not remove is the rest of the trade -- store-and-
forward delay, a transcript stored at every hop, visible
subjects and sizes, and a pre-authentication surface the
size of the mailbox:

* A DTLS handshake flight is carried as 1 or more email
  messages (Sections 5 and 6).
* The receiver's mailbox parser recognizes a DTLS
  initialization flight and routes it to the DTLS engine,
  never to the job execution path (Section 8).
* Once the session is established, jobs and results travel as
  application data inside it (Section 10), and each job still
  faces the version 1 acceptance gate in full (Section 10.2).
* The platform disclosure rides the handshake on this carrier
  exactly as on the datagram binding, in EncryptedExtensions,
  so the initiator holds it when the session is established
  and no post-handshake poll of the mailbox is needed to learn
  it (Section 11).

Nothing else in version 1 changes. The deltas in this document
are stated as deltas: where this document says a version 1 rule
applies, it applies as written there.

The same profile therefore runs on 2 bindings, and their
names are kept distinct. On the version 1 datagram binding
it is DTLS, with no qualifier: the submitter is told the
runner's IP address and port, and DTLS runs over UDP
datagrams as {{RFC9147}} defines. On this document's
binding it is DTLS via email: the same profile's datagrams
ride email messages, and no inbound UDP listener -- and no
firewall hole for one -- is needed. A deployment MAY offer
either binding, or both; the profile, the handshake, and
the acceptance gate are the same on each.

## Status of this document

This is a local working draft, revision -00, dated 2026-11-02.
It is not an Internet-Draft of record: it has not been
submitted to the IETF datatracker or posted to the
Internet-Drafts directory, no submission is requested by this
text, and the IANA considerations (Section 15) request no
assignment. The carriage this document specifies is implemented
and tested in the Homing Pigeon software suite under an opt-in
configuration option; the option is off by default.

# Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL
NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED",
"MAY", and "OPTIONAL" in this document are to be interpreted
as described in BCP 14 {{RFC2119}} {{RFC8174}} when, and only
when, they appear in all capitals, as shown here.

# Terminology

The terms of version 1 apply: the runner, the submitter, the
shared secret, the job object, the result object, the
acceptance gate, and the platform card. This document adds:

flight mail:
: 1 email message carrying all or part of exactly 1 DTLS
  datagram under this carriage.

mail session-id:
: the identifier in a flight subject (Section 5.1) that names
  1 mail-carried session attempt. It is a routing label chosen
  by the initiator. It is not a credential, not a DTLS
  identity, and not the mailbox's identifier for any message.

transfer:
: the set of flight mails that together carry 1 segmented
  datagram, named by a transfer identifier (Section 5.2).

carriage:
: the rules of Sections 5 to 9: how datagrams become flight
  mail, how flight mail becomes datagrams again, and how the
  mailbox parser dispatches each.

# The DTLS Profile on This Carriage

## The profile is version 1's, unchanged

The session profile of version 1 Sections 19 and 20 applies to
this carriage without modification, except where a later
section of this document states a delta explicitly. In
particular:

* DTLS 1.3 {{RFC9147}} is the session protocol. The 1 cipher
  suite is TLS_AES_256_GCM_SHA384.
* The pre-shared key is the shared secret of version 1 -- the
  "SS" of this version's name for the work, DTLS via email
  using SS. The handshake key is the one version 1 already
  defines; there is no second secret and no new key material
  in this document.
* Only the `psk_dhe_ke` key exchange mode is used. `psk_ke`
  MUST NOT be offered, accepted, or fallen back to, in a full
  handshake or in resumption. Every handshake, full or resumed,
  carries a fresh ephemeral X25519 share. This is the rule the
  perfect forward secrecy property of Section 16.1 rests on,
  and this carriage does not relax it.
* The responder is stateless until a HelloRetryRequest cookie
  validates, exactly as on the datagram binding.
* Connection IDs {{RFC9146}} are used in both directions.
* Early data is not used; there is no 0-RTT on this carriage.
  A ClientHello that carries early data is a malformed
  flight on this carriage and MUST be rejected (Section 13).
* The platform_info extension is offered empty in the
  ClientHello and, when offered, MAY be answered in
  EncryptedExtensions only, exactly as version 1 Section 20
  states (Section 11 of this document).

The UDP port 20220 of version 1 is a local default of the
datagram binding. This carriage has no port: its addresses are
mailboxes.

## What the carriage changes, and what it does not

The carriage changes the unit of transport. DTLS is written
for datagrams that arrive whole, in order or not, within
seconds. Mail arrives whole per message, in no guaranteed
order, after delays of seconds to days, sometimes more than
once, and with a size limit far below a mailbox's own. Sections
5 to 9 exist to bridge exactly those differences -- size,
ordering, duplication, delay -- and nothing else.

The carriage does not change the cryptography, the handshake,
the record protection, the session's authentication, or the
job acceptance gate. An implementation MUST NOT use this
carriage as a reason to alter any of those.

## Enablement

This carriage is opt-in. A runner enables it by explicit
configuration (in the reference implementation, the
`dtls_via_email` option, which only the literal boolean true
enables). A runner that has not enabled it treats flight mail
as it treats any other mail its parser does not dispatch, and
its existing secret boundary is unchanged: the shared secret
is handed to the component that terminates DTLS only when the
carriage is enabled, exactly as it is handed to the datagram
binding's listener when that binding is enabled.

A submitter discovers the carriage the way it discovers the
platform: by attempting it and reading the outcome, or from
the platform card of a prior exchange. There is no negotiation
message, and a failed attempt has no effect on the ordinary
email binding, which continues to work exactly as before.

# Message Format

## The flight subject

Flight mail is recognized by its subject, under the subject
grammar of version 1 (spelled out in the reference
implementation in 1 place, so every reader routes the same
subjects). The flight subject is:

~~~
[HOMING-PIGEON] dtls <mail session-id>
~~~

In ABNF {{RFC5234}}, with the separator set as version 1
defines it:

~~~
flight-subject  = "[HOMING-PIGEON]" 1*gap "dtls" 1*gap
                  session-id
session-id      = 1*128 session-id-char
                  ; and not "." or ".."
session-id-char = ALPHA / DIGIT / "." / "_" / "-"
~~~

The session-id alphabet is stated here in full and does not
inherit version 1's `word-char`: it is the alphabet a mail
header field can carry ({{RFC5322}}, Section 2.2) and a
filesystem can name, and a future widening of version 1's
production MUST NOT widen it.

The mail session-id is chosen by the initiator, 1 per session
attempt; a resumption attempt is a new attempt and takes a new
mail session-id. The responder answers flight mail for an
attempt under the same mail session-id it arrived under.

A mail user agent that replies to flight mail may prepend a
reply prefix to its subject. A receiver MAY accept at most 1
leading "Re:" or "Fwd:" (case-insensitive), and only when the
remainder is exactly a flight subject. A chain of prefixes,
or any other text before the marker, is not a flight subject.

Subjects route; they never authenticate. A receiver MUST NOT
treat a flight subject, a mail session-id, or any mail header
(`From`, `To`, `Reply-To`, `Message-ID`, the mailbox UID, or
arrival order) as evidence of who sent a flight. Authentication
is the DTLS handshake's, applied to the datagram after
reassembly (Section 6), and to nothing else.

An implementation MAY also accept the unaddressed harness
shape -- subject exactly `[HOMING-PIGEON] dtls` and a body that
is the base64 of 1 datagram -- for local testing. That shape
carries no mail session-id, cannot be bound to a session under
Section 9.2, and MUST NOT be required by any deployment.

## The flight frame

The frame of a flight mail is carried in a dedicated MIME
part of the message, whose content type is
`application/hp-dtls3` -- a private type: this document is
local and requests no media type registration for it
(Section 15). The part's content, under
Content-Transfer-Encoding base64, is 1 header line, 1 line
break, and 1 base64 chunk:

~~~
HP-DTLS/3 transfer=<t> part=<i> parts=<n> bytes=<b> sha384=<d>
<base64 chunk>
~~~

where:

* `t` is the transfer identifier: 16 lowercase hexadecimal
  digits, chosen fresh by the sender for each datagram it
  sends under this carriage.
* `i` and `n` are the 0-based index of this part and the total
  number of parts, in decimal. An unsegmented datagram is
  part 0 of 1.
* `b` is the total length of the datagram in octets, in
  decimal. The field publishes the datagram's exact length,
  which is consistent while this document specifies no
  padding (Section 16.2); if padding is ever added, `b` is
  the padded length, or the field would undo the padding.
* `d` is the SHA-384 digest of the whole datagram, as 96
  lowercase hexadecimal digits.
* the chunk is a slice of the base64 encoding ({{RFC4648}}
  Section 4, with padding) of the whole datagram. Slices are
  cut on base64 group boundaries, so each chunk decodes on its
  own and the decoded chunks, concatenated in index order,
  are the datagram exactly.

The digest binds the parts of a transfer to each other and to
the datagram they claim to carry. It is not a signature and
MUST NOT be treated as authentication: a receiver verifies it
to know the datagram is whole, and authenticates the datagram
afterwards, by DTLS.

The frame rides as its own part, and not as text in the
message's text part, precisely so that what intermediate
agents do to text cannot reach it: a mail gateway that
appends a disclaimer or a banner to the text part -- the
routine rewriting of real mail paths -- does not touch the
flight. This is the dedicated-part practice {{RFC8551}}
records for the same reason. Text outside the part is not
the frame and MUST be ignored for framing.

The header line is the part's 1st line. Base64 folding at
76 columns inside the part is accepted: the chunk is read
with its whitespace removed. Quoted-printable MUST NOT be
used for the part and MUST NOT be accepted for it: a part
whose transfer encoding is not base64 carries no frame.

A message with no `application/hp-dtls3` part is read in
the naked shape this carriage began with: the frame as the
1st text/plain part's text, as a job body under version 1
is read, with no preamble and no trailer. When a typed part
is present it is the only frame source: a frame-shaped text
part does not rescue a typed part that does not frame, and
a part that does not frame is malformed flight mail
(Section 8.3).

The naked shape is read for senders that never used the
typed part: a local harness, and senders that predate the
part. It is not a 2nd copy of the frame. A sender that uses
the typed part places the frame there and nowhere else; its
text part carries at most a note for a human, and MUST NOT
carry the frame. A message built with a typed part that
reaches its receiver without one -- an intermediary dropped
the part it did not recognize -- is therefore read in the
naked shape, is found not to frame, and ends that flight
under Section 8.3. The flight is repaired, if at all, by the
DTLS retransmission of Section 7.1 as a new flight mail,
never by a reading of the text part. An intermediary that
drops the typed part from every flight ends every attempt
through it: this carriage does not pass such an
intermediary, and says so rather than pretending the text
part is a fallback.

## Size gates

A flight mail is subject to the version 1 size cap for mail on
this binding, and that cap applies 1st: a receiver MUST refuse
a flight mail whose raw object exceeds the cap before it
decodes any base64, allocates any reassembly state, or feeds
any octet to a DTLS stack.

Within the carriage, a datagram MUST NOT exceed the carriage
datagram limit. The reference implementation's limit is 262144
octets, and its default chunk is 32768 base64 characters (8192
decoded octets at most per part before the header). Both are
local limits, configurable within the bounds of Sections 6
and 16.4; a sender that does not know the receiver's limits
SHOULD keep a datagram within the reference limit. A part
count MUST NOT exceed 1024.

# Segmentation and Reassembly

A sender segments a datagram when its base64 form exceeds 1
chunk. Every part of 1 transfer carries the same transfer
identifier, part count, byte count, and digest, and a distinct
index. A sender MUST NOT place parts of 2 datagrams in 1 flight
mail, and MUST NOT place any datagram octets in a mail whose
subject is not a flight subject.

The receiver's reassembly state is keyed by (mail session-id,
transfer identifier). Its rules are:

* Parts MAY arrive in any order. Duplicate parts are
  idempotent: the same index with the same chunk changes
  nothing.
* A part that contradicts its transfer -- a different chunk
  for an index already held, or different header fields for
  the transfer -- destroys the transfer. The receiver drops
  the state and completes nothing from it. The sender may
  start the transfer again under a new transfer identifier.
* A transfer completes when every index is held and the
  concatenated datagram matches the declared byte count and
  digest. A completed datagram is delivered upward exactly
  once, and the state is discarded.
* Incomplete state is bounded in count, in total size, and in
  age, and expires. The reference implementation holds at most
  64 transfers. A transfer's age runs from its FIRST part as
  well as its last: the reference implementation keeps a
  transfer for at most 3600 seconds from its first part, and
  3600 seconds from its last part, and no arriving part
  extends the first-part deadline -- a sender dripping 1 part
  just inside the idle window would otherwise hold a transfer
  slot indefinitely. Expired parts complete nothing: a part
  that arrives after its transfer expired starts a new,
  incomplete transfer.

Reassembly is deliberately unauthenticated and therefore
deliberately cheap to discard: it holds bytes, it decides
nothing, and the first decision any reassembled datagram faces
is the DTLS stack's.

# Retransmission, Duplicates, and Ordering

## Retransmission is DTLS's

The carriage defines no acknowledgement and no retransmission
timer of its own. Retransmission is the DTLS handshake's, as
version 1's profile inherits it from {{RFC9147}}: each side
re-sends its current flight when its timer expires, and the
timers' values are the profile's. On this carriage a flight's
re-send is a new flight mail, under a new transfer identifier.
The re-sent flight is the DTLS stack's own retransmission --
from the record layer's perspective a new record, with a new
record sequence number ({{RFC9147}} Section 5.2) -- not a
copy of the earlier mail. A sender SHOULD NOT re-send a
flight mail at the mail layer on its own schedule: 2
retransmission machines on 1 path multiply mail without adding
reliability.

Timers that are reasonable on a live path are short on a
store-and-forward one. An implementation on this carriage
SHOULD stretch its retransmission timers toward the mailbox
poll rhythm it operates on: concretely, the initial
retransmission interval SHOULD be at least 2 of the
implementation's mailbox poll periods, and an attempt SHOULD
be given up after about 8 retransmissions -- that give-up is
the attempt deadline of Section 9.4. {{RFC9147}} Section
5.8.2 permits a profile to recommend longer timer values
than its defaults; this paragraph is that recommendation for
a store-and-forward path. Stretching a timer changes no
message and no state machine; it is a local matter.

## Duplicates, at each layer

Mail is delivered at least once by some hops and exactly
observed twice by some pollers; DTLS is written for a network
that duplicates datagrams; and the job layer is written to run
each job at most once. The carriage keeps the 3 layers'
duplicate handling separate, and each layer's rule is its own:

* Mail layer: the carriage suppresses exact duplicates,
  split by phase. A receiver keeps a digest of each datagram
  it has accepted from flight mail, bounded and in arrival
  order; the reference implementation's cache holds 4096
  digests, first in first out. The cache is an optimization
  against a poller or a sender delivering the same mail
  twice; it is not the replay defense (Section 13 names the
  defenses). The connection-id binding check of Section 9.2
  runs before a datagram's digest is recorded, so a
  misaddressed copy cannot poison the cache against the same
  record arriving under its own session's mail. A digest hit
  on a handshake-phase datagram is not fed to the DTLS stack
  again -- nothing is derived twice -- and the receiver
  instead re-posts its saved last outbound flight, under a
  new transfer identifier: the duplicate is the signal that
  the answer was lost ({{RFC9147}} Section 5.8.1). The
  re-post is budgeted, because on this carriage it costs an
  outbound mail that an unauthenticated sender can provoke
  with a captured hello: a receiver MUST re-post a saved
  flight at most once per generation of that flight. A
  digest hit spends the 1 re-post the saved flight carries;
  only a new flight from the DTLS stack -- a new answer, or
  the stack's own retransmission on its timer -- arms
  another; further bit-identical copies of a handshake-phase
  datagram are dropped. A thousand copies of 1 ClientHello
  therefore cost the responder at most 1 HelloRetryRequest
  mail beyond the 1 it already sent (Section 16.4). A digest
  hit on application data is dropped and does nothing. A
  replayed mail is therefore not a new record at either
  layer, and a lost flight is still repaired.
* DTLS layer: records are protected and sequenced by the
  record layer as {{RFC9147}} specifies; a record that does
  not authenticate is dropped by the stack, whether it is a
  forgery, a corruption, or a replay the mail layer did not
  catch.
* Job layer: a job inside a session faces the version 1
  acceptance gate, whose seen-set runs it at most once
  (Section 10.2), under the same priced replay windows as any
  other binding.

A duplicate flight mail MUST NOT create a 2nd session, MUST
NOT deliver an application message twice, and MUST NOT cause
a job to run twice. A duplicate part MUST NOT complete a
transfer twice.

## Ordering

No ordering is assumed anywhere in this carriage. Flight mails
of 1 attempt can arrive in any order; the handshake state
machines of {{RFC9147}} already tolerate reordered flights,
and parts tolerate reordering under Section 6. Application
messages inside a session keep the session's own order, which
the record layer defines; the order in which different jobs'
mails reached the mailbox is not an input to anything.

# The Mailbox Parser: Lane Dispatch and Recognition

## Dispatch order

On a runner that has enabled this carriage, the mailbox parser
classifies each message it fetches before anything is
delivered anywhere. The classification is by subject grammar
and body shape, in this order:

1. A message whose subject matches the flight subject, or the
   unaddressed harness subject, is DTLS input. It goes to the
   carriage, and to nothing else.
2. A message whose subject is a version 1 job subject is a job
   for the acceptance gate, as before.
3. Everything else is other mail, handled as before.

DTLS classification happens in the component that owns the
mailbox (in the reference implementation, the email transport
extension), because that is where the DTLS server for this
carriage runs (Section 4.3). The runner core -- the acceptance
gate -- never sees flight mail.

## Recognizing the initialization flight

A complete datagram is an initialization flight when its 1st
record is a plaintext handshake record whose handshake message
is a ClientHello -- including a fragmented ClientHello whose
message type is ClientHello. A complete datagram that parses
as DTLS records but is not an initialization is a session
datagram. The recognition is of the DTLS bytes, not of the
subject: the subject routes a message to the carriage, and the
bytes decide what the carriage does with it.

An initialization flight is answered as version 1's profile
answers it: statelessly, with a HelloRetryRequest, before any
session state exists.

## Fail closed

A message with a DTLS subject whose body does not frame a
datagram under Section 5.2, whose session-id is not a valid
session-id, whose declared sizes are out of range, whose
digest does not match a completed datagram, or whose datagram
is not a DTLS record at all, is malformed flight mail. It is:

* consumed as DTLS input -- marked seen, so it is not offered
  again on every poll; and
* dropped -- it produces no session, no application message,
  no job, and no result; and
* never reinterpreted as a job or as any other kind of mail.

An implementation MUST NOT fall back from a DTLS-shaped
failure to any other reading of the same message. The lane a
message enters by its subject is the only lane it is ever read
in.

## Seen flags and fetches

Flight mail is consumed by the component that owns the
mailbox, and consumption is what marks it seen. A party MUST
mark a flight message seen only when it has consumed it --
fed it to the carriage, or determined it malformed under
Section 8.3. A fetch made to decide, before consumption,
MUST NOT set the seen flag: over IMAP {{RFC9051}} that is a
BODY.PEEK fetch, because a plain body fetch sets the flag as
a side effect, and a fetcher that marks its peer's flights
seen starves every other consumer of the same mailbox. An
initiator MUST ignore flight mail whose mail session-id is
not an attempt it has open: on a shared mailbox, stale
flights of dead attempts are normal, and they are not input.

# Session Establishment

## The attempt, flight by flight

An attempt proceeds exactly as the datagram binding's
handshake, with mail as the datagram path:

1. The initiator sends its ClientHello as flight mail under a
   fresh mail session-id.
2. The responder, stateless, answers with a HelloRetryRequest
   flight mail under the same mail session-id.
3. The initiator answers with its cookied ClientHello.
4. The responder validates the cookie and the PSK binder,
   derives the handshake keys from the ephemeral exchange, and
   sends its flight: ServerHello, EncryptedExtensions
   (carrying the platform disclosure, Section 11), and
   Finished.
5. The initiator verifies the flight, holds the disclosure
   (Section 11), and sends its Finished. The session is
   established at both ends when the responder verifies that
   Finished.

No step of this exchange is a job, produces a job, or is
visible to the acceptance gate.

## Identity binding at establishment

The responder's DTLS core needs a peer address to bind its
cookie and its session to. On the datagram binding that is the
datagram's source address. On this carriage there is no source
address a receiver may trust: the `From` header is a claim any
sender can write, and the mailbox's identifiers are local to
the mailbox. The peer address on this carriage is the ASCII
string `email:` followed by the mail session-id. That string
is an untrusted routing label: it demultiplexes concurrent
attempts on 1 mailbox, and it is not a credential, not a
mailbox identity, and not a key selector. The cookie key is a
secret of the responder, generated by the responder and not
derived from the address or from anything the message
asserts, so binding the cookie to an attacker-chosen label is
safe exactly while that key stays secret. The key's lifetime
is the matter of Section 9.4. The PSK identity inside the
handshake selects the shared secret, including any
additional secret, exactly as version 1 specifies; the mail
session-id never selects a key.

When a session establishes, the carriage binds the mail
session-id to the session's connection ID. From then on:

* A protected record is accepted under a mail session-id only
  if its destination connection ID is the connection ID bound
  to that mail session-id.
* A record whose connection ID is bound to a different mail
  session-id is dropped, whichever subject it arrived under.

A record therefore cannot be moved from 1 session to another
by relabeling its mail, and a session cannot be entered by
naming it: entry is the record protection itself, which only
the session's keys satisfy.

## Resumption

Resumption over this carriage follows the profile: tickets
MAY be issued and, on this carriage, MUST be single-use --
a ticket is stored mail like any other flight, in the same
archive as the transcript, and a replayed ticket must not
become a second long-lived secret. (Version 1's SHOULD for
the datagram binding is unchanged.) A resumed handshake
is a full handshake in everything that matters here -- a fresh
mail session-id, a fresh ephemeral share, `psk_dhe_ke` only,
and a fresh platform disclosure (Section 11). A deployment MAY
disable resumption on this carriage by configuration; doing so
changes no message, only how often full handshakes happen.

## Attempt deadline and failure

An attempt that cannot complete -- a flight that never comes,
a binder that never verifies, a peer that stops answering --
is abandoned by the side waiting on it when its retransmission
gives up, and its partial state (reassembly state, digest
cache entries, the mail session-id binding) expires with the
bounds of Sections 6 and 7.2. A failed attempt leaves the
ordinary email binding untouched and has no effect on any
other attempt.

The cookie key of Section 9.2 has a lifetime this path tests
and the datagram path never did. On the datagram binding a
HelloRetryRequest is answered within a round trip, inside 1
process lifetime of the responder. On this carriage it is
answered on a later poll -- an hour later on a slow poller --
which may be after the responder's process has restarted. A
responder SHOULD keep its cookie key across its own restarts
for at least the attempt deadline, kept as the shared secret
is kept: in the responder's own state, never in a flight, and
never derived from the address or from anything a message
asserts (Section 9.2). The reference implementation keeps it
beside the mailbox's own state, readable by its owner only.
A responder whose cookie key does not survive a restart
abandons every attempt in flight at that restart: the cookied
ClientHello fails the cookie check and is ignored, each
retransmission of it fails the same way, and the initiator
abandons the attempt when its retransmission gives up.
Recovery is a fresh attempt under a new mail session-id,
never a repair of the old one. Established sessions do not
survive a restart of either end on any binding -- their keys
are erased with the process, as Section 16.1 requires -- and
a result held for such a session follows Section 10.3.

## Session end

A session ends by alert, by the profile's own mechanisms, or
by being forgotten: a store-and-forward peer can vanish
without a farewell, and an implementation MUST NOT keep a
session's keys, or its mail session-id binding, past the
session's configured lifetime. Keys are erased with the
session (Section 16.1). A result that is waiting for a dead
session is not sent on any other path (Section 12); it is
held under Section 10.3's bounds and expires under them --
it is not kept forever, and expiry never sends it.

# Jobs and Results Inside a Session

## Framing

Application data on the session is framed as version 1's
session profile frames it: a 4-octet big-endian length prefix
per message, and each application message is exactly 1
envelope -- the subject line, a blank line, and the object
body -- in the shape the version 1 channel envelope uses. A
job travels as the envelope of its job object. A result
travels as the envelope of its result object.

On the runner, a completed application message is converted
back into that ordinary envelope and delivered to the runner
core through the same channel an ordinary mail job crosses.
The core cannot tell, and does not need to tell, that the
envelope arrived inside a session.

The objects are version 1 objects. A job inside a session is
a version 1 job object and a result inside a session is a
version 1 result object, with the version value version 1
defines; the 3 of this document numbers the document and its
carriage only, and no object in a session carries it.

## The acceptance gate, in full, inside the session

Completing a DTLS handshake MUST NOT bypass, widen, or
substitute for the job acceptance gate. A job carried inside
a session is admitted exactly as the same job arriving as
ordinary mail: it needs its valid HMAC signature under the
shared secret, its correct audience, and its compliance with
the size caps (the whole-job cap, the script cap, and the
envelope cap of version 1), and it is refused on the same
terms -- staleness, key policy, and the rest of version 1
Section 14's checks -- as any other job.

The session authenticates the channel; the signature
authenticates the object. Neither stands in for the other,
and the version 1 rule stands verbatim on this carriage: a
cleartext object inside a session is still refused unless the
operator has enabled cleartext acceptance, because the
session's confidentiality is not the object's provenance.

The 2 keys are checked independently. The PSK identity that
opened the session and the key id that signed a job inside
it need not name the same key: the gate reads the job's own
key id and applies that key's policy, and the session's key
confers nothing on the job and takes nothing from it. A job
signed under 1 key MAY be carried by a session opened under
another, exactly as a signed job may be carried by any
mailbox. An implementation MUST NOT admit, widen, or narrow
a job on the strength of the PSK identity of the session
that carried it: the session does not authorize the job,
and the job does not authorize the session. (The session's
key does decide 1 thing, which is not admission: where the
job's result may go, Section 10.3.)

## Results are session-bound

A result for a job that arrived inside a session is sent
inside that session, sealed as application data. The
carriage remembers, for each job it delivered from a session,
the session's connection ID and the job ident together, and
the PSK identity the session authenticated under -- never the
job ident alone, which the submitter chooses and which
collides across submitters. If that session no longer exists
when the result is ready, the result waits, and it can still
leave on this carriage in exactly 1 way: inside a later
session that authenticated under the same PSK identity and
that carries the same job ident again. The acceptance gate
refuses the repeated job as a replay (Section 13); the held
result is what answers it. A job whose ident is held for
another PSK identity's job is not delivered: it is logged and
dropped, because the hold belongs to the submitter whose job
it was, and delivering it would put that submitter's result,
or that submitter's job file, in the wrong hands. A held
result MUST NOT be sent as an ordinary mail result, MUST NOT
be sent inside a session under a different PSK identity, and
MUST NOT be sent inside a different job's session as if it
were that job's. Section 12 states the general rule this
follows from.

The hold is bounded, as the hold of any state on this
carriage is bounded. A held result expires by age -- the
reference implementation's bound is 7 days -- and the held
set as a whole is bounded in count and in total bytes,
oldest first. An expired result is dropped and the expiry
is logged; it is never sent. Dropping is not downgrade:
downgrade would be sending the result by a weaker path.

# Platform Disclosure on This Carriage

The platform disclosure is the version 1 Section 20 mechanism,
unchanged: the initiator offers the platform_info extension,
empty, in its ClientHello; the responder MAY answer with a
disclosure object, and answers only in EncryptedExtensions;
it MUST NOT send the disclosure unsolicited or in any other
message; the tiers are version 1's (none, family by default,
standard, full); the initiator cannot ask for a wider tier;
and a resumed session carries the disclosure again.

The carriage is why the mechanism matters most here. On a live
path, a post-handshake greeting costs a round trip of
milliseconds. Over a mailbox, it costs a poll cycle at best
and a day of latency at worst -- and for a submitter that
plans work from the platform card, it costs that on
every session, before any work can be planned against the
platform it is about to address. Riding the final handshake
flight -- the pattern version 1 lifts from IKEv2's
Configuration Payload {{RFC7296}}, Section 3.15 -- means the
initiator holds the platform at the moment the session is
established, having sent and received exactly the flights the
handshake already needed. Even a rudimentary exchange counts:
a responder that can say only its disclosure tier and its
operating system family has still saved the round trip.

The precondition that makes the early disclosure acceptable
is stated here, not left to the flight order alone: the
responder sends EncryptedExtensions only in a flight it
builds after the cookie has validated and the PSK binder has
verified (Section 9.1, step 4). A peer that does not hold the
shared secret cannot produce a verifying binder, and never
receives the disclosure; an unauthenticated ClientHello is
not enough to extract a platform card. The accepted cost of
version 1 Section 20 stands on this carriage too: the
disclosure is made a half-step earlier than a post-handshake
mechanism would make it, before the responder has verified
the initiator's Finished. Version 1's security
considerations argue the point; this document adopts the
argument.

# No-Downgrade Rules

The following are stated in 1 place because downgrade is the
failure this carriage is most often suspected of, and each
rule already exists somewhere above or in version 1:

* `psk_ke` MUST NOT be offered, accepted, or fallen back to,
  on this carriage or any other (Section 4.1). A peer that
  offers only `psk_ke` gets no session.
* A session's keys are never a fallback for the object crypto,
  and the object crypto is never a fallback for a session: a
  job that was to travel inside a session does not travel as
  an ordinary encrypted mail job instead when the session
  fails (Section 10.2's gate is the same, but the carriage of
  the object is part of what the submitter chose).
* A cleartext object inside a session is refused on the
  version 1 terms (Section 10.2). DTLS carriage is not a way
  to make cleartext acceptable.
* A result bound to a session is never downgraded to an
  ordinary mail result (Sections 10.3 and 12).
* Flight mail that fails is never reinterpreted as a job
  (Section 8.3). There is no reading of a message under which
  a failed handshake becomes work.
* The mail hop's own TLS (Section 16.2) is never a substitute
  for the session: a deployment MUST NOT accept "the mailbox
  connection was encrypted" as a reason to run a session-less
  job with session-level trust.

# Replay Handling

Replay is handled at 3 layers, each in its own terms, and no
layer is asked to do another's work:

* A replayed flight mail meets the mail layer's rule, split
  by phase (Section 7.2): a handshake-phase replay re-posts
  the saved flight without re-entering the stack -- once per
  generation of that flight, and then it is dropped -- and
  an application-data replay is dropped before it. A replayed
  initialization therefore cannot create a duplicate
  session: at worst, a replay that evades the cache meets the
  cookie exchange and the handshake state machine, which
  answer a retransmitted ClientHello with the flight it
  already produced and derive nothing twice. Early data has
  no layer here at all: a ClientHello carrying early data is
  rejected as a malformed flight (Section 4.1), and this
  profile derives no epoch-1 keys for a replay to use.
  {{RFC8446}} is the reason the rule is a rejection and not
  a quiet skip: 0-RTT data is not forward secret, is
  replayable between connections, and an application
  protocol must not use it without a profile that says how
  ({{RFC8446}} Sections 2.3 and 8, Appendix E.5). A job that
  runs a program is not safe to replay, and on a mailbox the
  ClientHello can sit for a day.
* A replayed record meets the record layer: sequence numbers
  and AEAD verification under {{RFC9147}} decide, and a record
  that does not verify is dropped. A replayed application
  message that somehow reached the core would meet the job
  layer next in any case.
* A replayed job meets the acceptance gate's seen-set: at
  most once, with the 2 priced windows version 1 documents
  (a crash between run and result, and the seen record ageing
  out), and no 3rd window is opened by this carriage -- the
  carriage adds no execution path, so it adds no replay path
  to execution.

Resumption tickets on this carriage MUST be single-use
(Section 9.3); version 1's SHOULD stands for the datagram
binding. A replayed ticket can at most restart a handshake
that still demands fresh ephemeral keys and a fresh binder
under the ticket's key.

# Operational Considerations

The carriage shares the mailbox with the ordinary email
binding. Flight mail and job mail are distinguished by the
parser's dispatch (Section 8.1) and neither delays the other
beyond 1 poll pass; an operator enables the carriage per
runner, and disabling it returns the mailbox to exactly its
previous behavior, with any in-flight attempts expiring under
Section 9.4.

Poll rhythm is the operational dial that matters. A runner
that polls its mailbox every 20 seconds completes a handshake
in about 4 poll cycles when both sides are prompt; a runner
that polls hourly completes it in about 4 hours. Nothing in
the protocol changes -- only the timers an implementation
should choose (Section 7.1) and the patience of the submitter.
Operators pairing this carriage with a slow poll SHOULD say
so in the platform card's customary ways, so a submitter can
tell a slow session from a dead one.

Sessions are state, and state on a store-and-forward path
should be visible to the operator: an implementation SHOULD
log session establishment, abandonment, and expiry, and the
dropping of malformed flight mail, at the same verbosity it
logs refused jobs. It MUST NOT log session keys, ephemeral
material, or the shared secret, on this carriage or any other.

# IANA Considerations

This document requests no IANA action.

The platform_info extension's code point is version 1's IANA
action, stated in version 1 Section 18: a value in the TLS
ExtensionType Values registry, TBD there, with 0xFFA0 in
interim private use. This document reuses that extension
exactly as version 1 defines it, on a new carriage; it does
not request a 2nd value, a new registry, a port, a service
name, a media type, or an OID. The DTLS reference port 20220
remains version 1's local default for the datagram binding and
is not used by this carriage.

The carriage's MIME content type (Section 5.2) is a
private-use type in a local draft; this document requests no
media type registration for it. A future standards-track
revision is where such a request would belong.

As a local, unsubmitted draft, this document could not ground
an assignment in any case: nothing in it is to be read as
requesting that IANA act, early or otherwise.

# Security Considerations

## Perfect forward secrecy

The property this version exists for: a session's keys are
derived from an ephemeral X25519 exchange performed fresh in
that session's handshake -- full or resumed, without exception
(Section 4.1) -- combined with the pre-shared key, and are
erased when the session ends. The shared secret authenticates;
it does not encrypt the session.

It follows that recording every flight mail of a session --
and mail is recorded by design: it is stored by the sender's
provider, the receiver's provider, and the mailbox itself --
and later obtaining the shared secret does not decrypt the
session. The recorded flights are a ClientHello, a
HelloRetryRequest, a cookied ClientHello, a server flight, a
Finished, and protected records. Without the ephemeral private
keys, which never leave the endpoints and do not survive the
session, the protected records stay protected.

The limits of the property are the usual ones, and are stated
plainly: compromise of the shared secret permits impersonation
in future handshakes and an active man-in-the-middle of a
future session, because the PSK is the authentication; it
permits reading ordinary version 1 mail jobs that rely on the
object crypto, which is why this carriage exists; and it does
nothing for an endpoint that is itself compromised while a
session is live. Forward secrecy is a property of recorded
sessions against later key compromise, and that is the
property claimed -- no more, and no less.

One further limit belongs to this carriage in particular,
because mail is archived by design. The ephemeral exchange
is X25519 {{RFC7748}} -- the ephemeral exchange {{RFC9325}}
tells operators to prefer, and the right choice against the
adversary above. A party that records a session's
flights -- and on this carriage the sender's provider, the
receiver's provider, and the mailbox all hold them -- and
that later breaks X25519, by whatever means, decrypts the
recorded session without ever learning the shared secret.
Forward secrecy here is secrecy against later compromise of
the long-term secret; it is not secrecy against a later
break of the ephemeral's algorithm. The slot for the remedy
is named now, so a later revision does not have to argue
for its shape: a hybrid share, X25519MLKEM768 {{RFC10024}},
in place of the bare X25519 share, under the same
`psk_dhe_ke` rule -- the PSK still only authenticates, the
hybrid share is what encrypts, and TLS_AES_256_GCM_SHA384
remains the suite until that revision. This document does
not add the group; it reserves the shape.

## The mailbox as intermediary

On this carriage the mailbox provider, and any hop that stores
flight mail, holds the session's whole transcript in the clear
at the DTLS-record layer: subjects, sizes, timing, counts, and
the handshake's public values are visible to it, and protected
records are visible as ciphertext. The provider cannot read
application data, cannot forge a record that verifies, and
cannot complete a handshake, not holding the shared secret.
It can delay, drop, duplicate, and reorder mail; Sections 7
and 13 are written so that each of those is survivable and
none is profitable. Deployments that care about the metadata
itself should note that the mail session-id, the flight
cadence, and datagram sizes are all observable; this document
specifies no padding or cover traffic.

## Headers are not authentication

Every routing decision in this carriage is made from
untrusted text -- the subject -- and every authentication
decision is made from protected bytes. The synthetic peer
address of Section 9.2 exists precisely so that no spoofable
header becomes a security input: a flight mail that claims
any `From` whatsoever is treated identically, and is worth
exactly what its datagram proves. A deployment MUST NOT add a
sender allowlist as a substitute gate on this carriage; the
version 1 properties already record that the email binding
carries no sender gate and claims none.

## Pre-authentication resource bounds

Everything a receiver does before a binder verifies is a
resource an unauthenticated sender can spend, so the
pre-authentication surface is bounded at each step, and
each action such a sender can cause is listed here with the
number that bounds it:

* A fresh ClientHello costs the responder 1 HelloRetryRequest
  mail and no state: the cookie exchange keeps the responder
  stateless until a cookie validates (Section 4.1). That is
  1 small mail out for 1 mail in -- the price of a stateless
  responder on any binding, with no amplification.
* A bit-identical copy of a handshake-phase flight costs at
  most 1 re-post of the saved flight per generation of that
  flight (Section 7.2), so a captured hello is worth at most
  1 extra outbound mail and never a mail per copy.
* A flight mail is refused above the mail size cap before any
  decoding (Section 5.3).
* A reassembly slot is 1 of at most 64, bounded in total
  size, and held at most 3600 seconds from its first part and
  from its last; a contradiction destroys the transfer rather
  than arbitrating it (Section 6).
* A digest-cache entry is 1 of 4096, first in first out
  (Section 7.2).
* A malformed flight is consumed in 1 pass and 1 log line,
  not re-offered on every poll (Section 8.3).

An action an unauthenticated sender can cause that has no
number in this list is a defect in this document. The platform
disclosure's cost -- disclosure before the initiator's
Finished is verified -- is inherited from version 1
Section 20 and bounded by its tiers; a responder that
discloses at the `none` or `family` tier spends little on an
unauthenticated peer, and the choice of tier is the
responder's.

## Downgrade and substitution

Section 12 collects the no-downgrade rules. The general
statement behind them: at no point does this carriage answer
a failure by doing the same thing more weakly. A failed
handshake is a failed handshake; a dead session holds its
results; a malformed flight is dropped. An implementation
that adds a fallback -- plain job crypto for a session's job,
ordinary mail for a session's result, a job reading for a
flight's bytes -- has left this specification, and should
expect the security properties of Sections 16.1 and 10.2 to
leave with it.

## The gate is the security boundary for execution

It is worth restating the architecture once, because the
carriage can make it look otherwise: DTLS authenticates a
channel between holders of the shared secret, of which there
may be several (version 1's additional secrets and key
policies distinguish them). The acceptance gate -- signature,
audience, caps, key policy, seen-set -- is what decides
whether a job runs, whose it is, and whether it has run
before. Carrying a job inside a session changes the
confidentiality and integrity of its transport and adds
forward secrecy; it changes its admission not at all. Any
future extension of this carriage that proposes to admit a
job on the session's authority alone is proposing to remove
the gate, and should be reviewed as such.
