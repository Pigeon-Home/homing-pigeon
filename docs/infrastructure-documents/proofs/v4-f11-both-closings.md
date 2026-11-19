# Finding F11: both closings, and why

The research record for Q204, written 2026-11-19 by Muse's
seat at the conductor's direction. The question was which of
2 closings finding F11 should take. The conductor's decision
is both. This page expands each closing, states what the
published literature says about each, and says why the
conjunction is the sound position and why it helps the
proof work that candidate constraint C32 and candidate
property P14 (on the branch, in `v4-before-the-mac.md`)
have opened. The implementations are the branch's work
under that candidate. Nothing here changes how the runner
behaves.

## The finding, briefly

A signed job whose id is 78 to 128 characters long is
refused with "job_id mismatch between subject and body"
when the sending side is Python's mail library. The library
writes a long subject as encoded words under RFC 2047.
`handle_mail` reads the subject as written and does not
decode them, so the id it reads from the subject is not the
id in the signed body. The refusal fails closed. The
runner's own sender uses the same library, so our own side
can produce the shape the gate refuses. The full record,
with the measurements, stands in `v4-bindings.md` under
finding F11.

2 closings stood:

1. The gate decodes encoded words in the subject before it
   reads the id.
2. The protocol states that a subject is read as written,
   and senders keep a long id on 1 plain line.

## Closing 1 expanded: the gate decodes, inside a bound

Decoding before the id comparison is a canonicalization
step: the gate reduces the subject's spelling to the text
the sender meant, and only then compares. Mail already has
a standards track precedent for treating canonicalization
as part of a signature scheme rather than as an improvisation
at the receiver. DKIM (RFC 6376) signs a canonicalized form
of selected headers, names the canonicalization in the
signature itself, and bounds what each form tolerates:
`simple` tolerates almost nothing, and `relaxed` tolerates
header unfolding, case folding of field names and whitespace
compression, and nothing beyond that list. The lesson the
precedent carries is not that receivers should normalize.
It is that a normalization a verifier performs must be
specified, named and bounded, or it is not part of the
protocol at all.

The risk in decoding is the classic one, and F11 is its
benign face. Where 2 readers read the same bytes, the bytes
have 2 meanings, and a security decision made between the
readers inherits the gap. LangSec names this the parse tree
differential (Sassaman and others, "Security Applications
of Formal Language Theory", Dartmouth technical report
TR2011-709, 2011; journal version in IEEE Systems Journal,
2013), and counts differing interpretations of the input
language among its recurring error classes (Momot, Bratus,
Hallberg and Patterson, "The Seven Turrets of Babel", IEEE
SecDev, 2016). The production proof of the class is HTTP
request smuggling, where a front end and a back end disagree
about where a request ends (Linhart, Klein, Heled and Orrin,
"HTTP Request Smuggling", Watchfire, 2005; Kettle, "HTTP
Desync Attacks: Request Smuggling Reborn", Black Hat USA,
2019). In F11 the 2 readers are the sending library and the
gate: the library reads the subject as the id's encoding,
the gate reads it as plain text, and a correctly signed job
falls into the gap. Decoding at the gate closes the gap by
making the gate's reading the protocol's reading, stated in
1 place.

The cost is what keeps closing 1 from being taken raw, and
the F11 record measures it. The standard library's decoders
grow about with the square of the subject: `decode_header`
took 7.63 seconds on a subject of 1,000,011 bytes, and the
default policy's reading took 2.05 seconds at 256,009 bytes.
Nothing bounds a subject below C1's 4,194,304 bytes, so an
unbounded decoder in front of the MAC would be a reader of
F10's kind: a stranger with no key sets its cost. The bound
is what makes the closing sound. A subject past 2,048 bytes
is refused before any decoding, and at 2,063 bytes the 2
decoders took 0.0003 and 0.0012 seconds. Every honest
spelling of a 128 character id fits inside the bound: 188
bytes as the library writes it, and 1,811 bytes written 1
character to an encoded word, the longest spelling there
is. RFC 2047's own shape supports a bound of this kind: an
encoded word may not exceed 75 characters including its
delimiters, a line carrying encoded words may not exceed 76
characters, and longer text is carried as a sequence of
small encoded words (Moore, RFC 2047, 1996). The standard
builds the encoding out of small pieces; a verifier that
caps the whole subject at a size every honest piece fits
is reading the standard in its own grain. With the bound,
decoding is a total function with a stated constant cost,
defined on every subject the gate can be handed, and what
it cannot read it refuses. That is Saltzer and Schroeder's
fail-safe defaults in this small place: access decisions
based on permission rather than exclusion, with refusal the
default the mechanism falls back to ("The Protection of
Information in Computer Systems", Proceedings of the IEEE,
1975). Decoding grants nothing by itself. The decoded id
must still match the body, and the signature must still
verify.

## Closing 2 expanded: senders keep a long id on 1 plain line

Closing 2 puts a well-formedness obligation on producers:
the protocol reads a subject as written, and a sender that
names a job with a long id writes that id on 1 plain line.
The room for it is already in the message format. RFC 5322
limits a line to 998 characters at most, and recommends 78
as a display accommodation (Resnick, editor, RFC 5322,
section 2.1.1, 2008). The library's folding at 78 is the
recommendation doing work it was never meant to do at a
machine boundary, and the F11 record measures the fix as
free at the gate: a sender that sets its line length to 998
writes a subject with a 128 character id plain.

The academic position behind closing 2 is the modern
strictness position, stated from 2 directions. The IAB's
RFC 9413 (Thomson and Schinazi, "Maintaining Robust
Protocols", 2023) argues that the robustness principle,
be liberal in what you accept, harms a protocol that is
actively maintained: tolerated deviations go unreported,
spread, and harden into obligations every later
implementation must reproduce, which the document calls
protocol decay, and its counter is active maintenance with
virtuous intolerance, a fatal error on a violation so bugs
surface early. Its headline sentence is that for a protocol
that is actively maintained, the robustness principle can,
and should, be avoided. The LangSec literature reaches the
same place from language theory: Sassaman, Patterson and
Bratus propose a patch for the principle whose first clause
is to be definite about what you accept, and to treat the
computational power spent handling input as a privilege the
input has not earned ("A Patch for Postel's Robustness
Principle", IEEE Security and Privacy, 2012). A protocol
that states how its subjects are written, and holds its
senders to the statement, is being definite. A gate that
silently absorbs every spelling habit of every library is
the opposite, and the absorbed habits become part of the
protocol whether anyone chose them or not.

Closing 2 also does direct work on the input language. With
it, the honest subject that names a job is 1 plain line over
a stated alphabet, at most 998 characters, carrying an id of
at most 128 characters. That is a regular language, the
lowest rung of the Chomsky hierarchy, and keeping an input
language at the lowest level that suffices is the LangSec
prescription in its plainest form (TR2011-709, above): a
language that small can be recognized completely, by a
recognizer simple enough to hold in the head, before any
processing acts on it.

## Why both, and not either one alone

Each closing, taken alone, leaves the other's gap open.

Closing 1 alone leaves the producer side unbounded. Every
spelling any present or future library invents for a subject
becomes the gate's obligation, the decoder's correctness and
cost stay inside the trusted surface for good, and the
honest input language stays as large as the set of all
encodings of it. That is protocol decay adopted as a design:
the wire detail of 1 library, absorbed silently, becomes
load-bearing for every sender after it.

Closing 2 alone leaves the gate's behavior on input that
does not conform unspecified. A stranger's mail does not
obey our sender rule, and unspecified behavior in front of
the MAC is the exact ground both gate findings grew on: F10
was an unbounded reader in that space, and F11 is an
unreadable subject in that space. A sender rule also cannot
reach third party senders the protocol does not govern, and
every such sender on the standard library stays 1 long id
away from the silent refusal F11 records, which is an
availability loss the protocol allows and no one chose.

Taken together, the 2 closings divide the work the way the
literature divides it. The producer rule shrinks the honest
language to a plain line, small enough to state in 1
sentence and recognize in full. The bounded decode then
gives every other spelling a defined treatment: decode
inside the bound and compare what the sender meant, or
refuse, at a cost that is constant and stated. Nothing in
front of the MAC is left to implication. The gate's reading
of a subject becomes a total function of the message, the
sender's obligation becomes a property of the protocol
rather than a habit of a library, and refusal stays the
default everywhere the function cannot speak.

## Why the conjunction helps the proof

Candidate constraint C32, clause 4, and candidate property
P14 ask for work in front of the MAC that is bounded by a
count of the message's length, with a constant that does not
depend on the message. That shape is what each closing alone
puts out of reach, and what both together restore.

Unbounded decoding breaks the shape outright: its cost grows
with the square of a subject that only C1 bounds, so the
constant would have to depend on the message after all. The
2,048 byte bound turns the decode step into a constant term
in the count, measured at about a millisecond at the bound,
which the model can carry as a number rather than as a
function. The opener search's bound from F10, 16 times the
message's length in characters read, then stands as the
largest term in front of the MAC, and S5's supposition has a
count it can be checked against.

Closing 2 is what lets the model's first step be stated at
all. The candidate's step list begins with the mail parsed
and its subject read. Under closing 2 the honest case of
that step has a 1 line description, and under closing 1 the
step's output is defined for every other case too: a plain
line, a decoded subject inside the bound, or a refusal. A
step whose output is defined on the whole input space is a
step a model can take without an assumption that the input
conforms, and assumptions of exactly that kind are what kept
the pre-MAC space outside the inventory: the proofs began
where a signature had verified, and the campaign's refused
inputs, 4 in 5 of everything it sends, never met them. With
both closings, the subject the gate compares is a function
of the message defined by the protocol, not an artifact of
which library wrote the mail, so the equality the gate
checks, the subject's id against the signed body's id, is a
statement about 1 id. That is the statement P14's ledger
reasoning needs at step 1, and it is the first statement of
that kind the pre-MAC space has had.

The implementations land on the branch under the candidate,
test first, with the measured costs above re-checked against
suppositions S1 to S8 as that pass measures the space. Where
the measure disagrees with this page, the measure wins and
this page is corrected, in the standing way.

## Sources

- Moore, K. "MIME (Multipurpose Internet Mail Extensions)
  Part Three: Message Header Extensions for Non-ASCII Text."
  RFC 2047, IETF, November 1996.
- Resnick, P., editor. "Internet Message Format." RFC 5322,
  IETF, October 2008. Line length limits at section 2.1.1.
- Crocker, D., Hansen, T. and M. Kucherawy. "DomainKeys
  Identified Mail (DKIM) Signatures." RFC 6376, IETF,
  September 2011. Canonicalization at section 3.4.
- Thomson, M. and D. Schinazi. "Maintaining Robust
  Protocols." RFC 9413, Internet Architecture Board,
  June 2023.
- Sassaman, L., Patterson, M. L., Bratus, S., Locasto, M. E.
  and A. Shubina. "Security Applications of Formal Language
  Theory." Dartmouth College Computer Science Technical
  Report TR2011-709, November 2011. Journal version: IEEE
  Systems Journal, volume 7, issue 3, September 2013.
- Sassaman, L., Patterson, M. L. and S. Bratus. "A Patch for
  Postel's Robustness Principle." IEEE Security and Privacy,
  volume 10, issue 2, March and April 2012, pages 87 to 91.
- Momot, F., Bratus, S., Hallberg, S. and M. L. Patterson.
  "The Seven Turrets of Babel: A Taxonomy of LangSec Errors
  and How to Expunge Them." IEEE Cybersecurity Development
  (SecDev), 2016.
- Saltzer, J. H. and M. D. Schroeder. "The Protection of
  Information in Computer Systems." Proceedings of the IEEE,
  volume 63, issue 9, September 1975, pages 1278 to 1308.
- Linhart, C., Klein, A., Heled, R. and S. Orrin. "HTTP
  Request Smuggling." Watchfire whitepaper, 2005.
- Kettle, J. "HTTP Desync Attacks: Request Smuggling
  Reborn." PortSwigger Research, Black Hat USA, 2019.
