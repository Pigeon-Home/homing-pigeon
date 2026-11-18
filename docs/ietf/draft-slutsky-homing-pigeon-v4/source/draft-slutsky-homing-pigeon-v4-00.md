---
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
# Render: kramdown-rfc draft-slutsky-homing-pigeon-v4-00.md > draft-slutsky-homing-pigeon-v4-00.kr.xml
#         xml2rfc --v2v3 draft-slutsky-homing-pigeon-v4-00.kr.xml -o draft-slutsky-homing-pigeon-v4-00.xml
#         xml2rfc --text --html draft-slutsky-homing-pigeon-v4-00.xml
#         idnits draft-slutsky-homing-pigeon-v4-00.txt
# Status: WORKING DRAFT, NOT POSTED. This -00 text has not been
#         submitted to the IETF datatracker. The author posts
#         drafts himself; this file is the working text, dated
#         2026-11-18. The text requests no IANA action
#         (Section 9).
title: "Homing Pigeon Message Protocol, Version 4: The Provable Model"
abbrev: "Homing Pigeon v4"
docname: draft-slutsky-homing-pigeon-v4-00
category: info
submissiontype: independent
ipr: trust200902
date: 2026-11-18
v: 3
keyword: [formal methods, TLA+, model checking, provable security]
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
      Internet-Draft: draft-slutsky-homing-pigeon-04
  I-D.slutsky-homing-pigeon-v2:
    title: "Homing Pigeon Message Protocol, Version 2: Determinations, Questions, and Shared Context"
    author:
      - name: "Andrew Slutsky"
        ins: "A. Slutsky"
    date: 2026-11
    seriesinfo:
      Internet-Draft: draft-slutsky-homing-pigeon-v2-04
  I-D.slutsky-homing-pigeon-v3:
    title: "Homing Pigeon Message Protocol, Version 3: DTLS 1.3 via Email"
    author:
      - name: "Andrew Slutsky"
        ins: "A. Slutsky"
    date: 2026-11
    seriesinfo:
      Internet-Draft: draft-slutsky-homing-pigeon-v3-00
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

informative:
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
  TLA:
    title: "Specifying Systems: The TLA+ Language and Tools for Hardware and Software Engineers"
    author:
      - name: "L. Lamport"
    date: 2002-07
    target: https://lamport.azurewebsites.net/tla/book.html

--- abstract

This document specifies version 4 of the Homing Pigeon message
protocol. Version 4 defines no new wire format and changes no
message of versions 1, 2, or 3. It binds those versions to a
formal model of the running implementation: a constraint
inventory harvested from the code, a set of numbered
properties stated against that inventory, a TLA+ model of
each property checked with the TLC model checker, and a
conformance suite that holds every model to the code it
models. The document states each property, the verdict the
checker returned, and the findings where the implementation's
behaviour bounds a property's strongest reading, so that a
reader can tell exactly which claims about the running
software have been machine-checked, and how far each claim
reaches.

--- middle

# Introduction

The Homing Pigeon protocol is specified by three documents.
Version 1 {{I-D.slutsky-homing-pigeon}} defines the message
protocol: signed job envelopes, an acceptance gate, key
policies, confinement of the work a job can do, and delivery
of results. Version 2 {{I-D.slutsky-homing-pigeon-v2}}
records the determinations and shared context the protocol's
terms rest on. Version 3 {{I-D.slutsky-homing-pigeon-v3}}
carries the version 1 DTLS 1.3 {{RFC9147}} session profile
over email,
with the hybrid key agreement group of {{RFC10024}}.

Version 4 answers a different question about the same
software: which statements about the running implementation
have been proven, in the precise sense that a finite model
of the relevant decision has been exhaustively checked, and
the model has been held to the code by tests that drive the
real decision over its whole input space. This document is
that binding. It is a claim about one implementation, the
reference runner, at the head its working record names. It
is not a claim about every conforming implementation, and
Section 10 says plainly what the checking does not reach.

The model's working papers live with the implementation:
the constraint inventory, the property files, the TLA+
models and their configurations, the search and checker
records, and the conformance suite. This document restates
their substance in specification form. Where this document
and the working papers disagree, the working papers are the
record and this document is in error; the unit tests
described in Section 4.4 exist to keep the two from drifting
apart unnoticed.

# Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL",
"SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED",
"NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document
are to be interpreted as described in BCP 14 {{RFC2119}}
{{RFC8174}} when, and only when, they appear in all
capitals, as shown here.

# Terminology

Constraint:
: A single harvested fact about the implementation: a named
  value, a fixed behaviour, or a refusal, with the code that
  carries it and the class of configuration handling it
  belongs to. Constraints are numbered C1 to C31.

Property:
: A statement about the implementation, numbered P1 to P13,
  that a counterexample can be exhibited for. Each property
  names the constraints it rests on.

Model:
: A TLA+ {{TLA}} specification of one decision the
  implementation makes, small enough for exhaustive
  checking, whose states stand in classes the code's inputs
  fall into.

Witness configuration:
: A checker configuration whose stated invariant is expected
  to fail, included so that a pass of the main configuration
  cannot be vacuous: the witness proves the checker can
  reach the behaviour the property talks about.

Finding:
: A recorded place where the implementation and a property's
  words, or a model and the implementation, differ. Findings
  are numbered F1 to F7 and are stated, not resolved, by the
  model work.

# The Method

## Harvest the constraints first

The inventory was harvested from the code at a named head:
every size cap, every constant the security decisions read,
every refusal class, read out of the source and pinned by
unit tests that fail when a value changes. A property may
only rest on constraints in the inventory, so that the
distance between a claim and the code is a list that can be
audited.

## State the property so it can fail

Each property is stated with its counterexample shape: the
single observable event that would refute it. A statement
that no event could refute is not admitted as a property.

## Write the supposition before the measurement

For each model, the expected state counts and verdicts are
written into the working record before the search or the
checker is run. The record then states what was measured
against what was predicted. A prediction that fails is
itself a finding about the model, the code, or the
prediction, and is recorded as one.

## Search, check, and hold to the code

Each model is treated three ways. First, a twin of the
model written in the test suite's language is searched to
its fixed point, and the properties are evaluated over
every reachable state. Second, the TLA+ model itself is
checked with TLC under its main configuration and its
witness configurations. Third, a conformance test drives
the real code over the decision's whole input space, as
far as the code exposes one, and reads the outcomes against
the model's. The three treatments must agree; where they
cannot, the gap is a finding.

## The pin suite

Every named value in this document is pinned by a unit test
against the code or against the working papers, so that a
change to a value the document states turns a test red
before it turns this document wrong.

# The Constraint Inventory in Brief

The full inventory states C1 to C31 with code and test
evidence for each. The values the properties below read
most directly are these. The maximum job body is 4194304
bytes (C1), the maximum script 1048576 bytes (C2), and the
maximum result body 5242880 bytes, with 0 meaning unlimited
(C3). A local envelope is capped at 262144 bytes (C4).
Signatures are HMAC-SHA-384 (C5) over a shared secret whose
estimated entropy is at least 128 bits, a refuse-class
startup condition (C6). The one AEAD is AES-256-GCM (C9).
The disk guard acts at 90 percent full, keeps the newest
65536 bytes of a truncated live log, leaves workspaces
untouched for 3600 seconds alone, and takes at most 512
actions in a pass (C28). The version 3 hybrid group is
X25519MLKEM768, group 4588, beside X25519, group 29 (C29).
Both ends of a DTLS session run the same side of the
framing change, and the replay window is 32768 records
(C30). On macOS, confinement at enforce is gated on a probe
of the host (C31).

# The Properties and Their Verdicts

## P1. The acceptance gate

A job is accepted, and only then run, when every check of
the acceptance gate passes, in the gate's stated order:
the gate is the only door from a presented envelope to
execution. The model is the gate model, checked with TLC
under its main and witness configurations, and the claim
model covers the gate's final step, the at-most-once claim
on a job identifier. Verdict: the invariants hold; the
witness configurations fail as designed.

## P2. Result policies cannot widen confinement

No field of a job or of a result policy can widen the
confinement the runner applies: the views a result policy
grants are ordered, and the effective confinement is the
narrower of what the job asks and what the policy allows.
The model is the confinement model, checked at its stated
rungs including the production ceiling rung. Verdict: the
invariants hold; the witness configurations fail as
designed.

## P3. A transport's credentials are a required second gate

Where a transport has credentials of its own, presenting a
validly signed envelope is not sufficient: the transport's
credential gate must also pass, and no waiver exists on the
DTLS carriage. The model is the transport gate model.
Verdict: the invariants hold; the witness configurations
fail as designed.

## P4. A named key can do only what its policy allows

A job signed under a named key is accepted only for the
kinds and, where the policy pins one, the exact script the
key's policy allows. The models are the key policy model
and the composition model, which checks that the gate and
the policy decision compose: execution requires both.
Verdict: the invariants hold; the witness configurations
fail as designed.

## P5. Replay cannot re-execute

Execution is at most once per job identifier: a replayed
envelope, however it is presented, does not run the job a
second time. The model is the replay model, with the claim
model at the gate's final step. Verdict: the invariants
hold; the witness configurations fail as designed.

## P6. Refuse-class configuration behaves as required

A present but unusable value in the refuse class of
settings stops the runner at startup, and the error names
the setting that cost the start. The model is the decision
model. Verdict: the invariants hold; the witness
configurations fail as designed. Finding F5 records the
one place the code's naming falls short of this property,
at the secret floor.

## P7. The disk guard cannot stop the runner

When the disk under the runner's state directory measures
at or over 90 percent full, a guard pass gives up only the
runner's own material, in the order of C28, records what it
did, and the runner continues: no pass terminates the
runner, follows a symlink, or touches the pending outbox,
the configuration, or the security event log. The model is
the disk guard model: 160 distinct states under search, its
invariants holding in every one, and TLC returns the same
count with no error. The witness configurations fail as
designed. Findings F1, F2, and F3 bound this property: the
model ends a pass sooner than the code does, a removal of
0 bytes leaves no record, and a measurement that fails in
the middle of a pass is taken as over. F2 and F3 are
differences from the property's own words, held by tests
as the tree stands.

## P8. A v3 session that can agree the hybrid group does so

When the client offers the hybrid share and the server's
carriage profile carries the hybrid option, the agreed
group is 4588, the X25519MLKEM768 hybrid, not X25519
alone. A hello offering no group the profile can select is
refused. The model is the hybrid selection model: 16
distinct states under search, its invariants holding in
every one, and TLC returns the same count with no error.
The conformance drives the real client and server cores
through 4 handshakes, every combination of offer and
profile, and the negotiated group is the model's outcome on
all 4. The witness configurations fail as designed.

## P9. No session is claimed across the framing break

Both ends of a DTLS session run the same side of the
framing change of C30, and no document of this protocol
presents a session across the break as supported. This
property is a claim about what the documents claim, so it
is held by a pin that reads them, not by a checker model:
the framing record states that mixed-version DTLS
interoperability is not supported across the landing, and
the support matrix claims no mixed-version session.

## P10. On macOS, enforce means the probe passed

For every start on macOS with confinement in enforce mode,
either the probe of C31 passed on that host or the runner
does not start; there is no weaker run. The gate the
startup asks is one gate for the 3 platforms that have a
confinement backend of their own, darwin, freebsd, and
win32, and the model states the claim for all 3; the index
states it for macOS. The model is the probe gate model:
288 distinct states under search, its invariants holding
in every one, and TLC returns the same count with no
error. The conformance drives the real gate over all 144
starts the model stands in, and the gate's answer is the
model's on every one. The witness configurations fail as
designed.

## P11. A result body never leaves over the cap

When max_result_bytes is set to a non-zero value, the body
that is signed and sent is at most that many bytes, and a
cut is marked result_truncated. The model is the result
fitting model: 12 distinct states under search, the
marking and unlimited and fitting invariants holding in
every one, and TLC returns the same count with no error.
The configuration that states the property's own words is
expected to fail, at exactly one class: finding F7. The
fitting cannot cut below the size of its own last pass,
the fixed envelope plus both streams at their first and
last 2 KiB; for a result with 40000 bytes on each stream
that floor is 4625 bytes, and a cap under the floor gets
the body at the floor's size, over the cap, marked. The
marking is honest and the signature covers what is sent;
what fails is the cap itself.

## P12. A local envelope over the cap is refused unread

An envelope over 262144 bytes on the local path is refused
before any verification work, at both doors of the path:
the inbox scan reads at most one byte past the cap, a
symlink is refused unread, and the loopback listener reads
at most one chunk past the cap before the same check. The
model is the local gate model: 200 distinct states under
search, its 4 invariants holding in every one, and TLC
returns the same count with no error. The conformance
drives the real doors over 112 arrivals in 140 runs at the
real cap, counting the bytes read at the door itself and
standing in for the verifier: nothing over the cap reaches
it, and an envelope of exactly the cap goes through. The
witness configurations fail as designed. Finding F6
records that a file whose cut at the cap falls inside a
character is refused with the reason that it is not UTF-8:
the refusal is right, and the reason is true of what was
read, not of the envelope.

## P13. The runner does not start on a weak secret

For every start, every key in the key map, the default and
the additional keys alike, estimates at or over 128 bits of
entropy, or the start refuses. The model is the secret
floor model: 67 distinct states under search, its
invariants holding in every one, and TLC returns the same
count with no error. The conformance builds the real key
map over every standing of 3 keys, 125 configurations, and
the start is the model's on every one. The witness
configurations fail as designed. Finding F5 records that a
refusal caused by a weak additional key names the default
key instead: the refusal is right, and the name is wrong,
in 32 of the 107 refused configurations.

# The Findings

The model work states 7 findings. None is resolved by this
document; each is held by a test as the tree stands, so a
change on either side, the code's or the words', shows as a
test change.

F1:
: The disk guard model ends a pass sooner than the code
  does. The code measures again at the door of the next
  class, and a pass can continue where the model stopped.
  The property as worded holds; the model's reach is the
  gap.

F2:
: Material of 0 bytes is removed by the disk guard with no
  record, against P7's clause that every acting pass
  leaves an event.

F3:
: A disk measurement that fails in the middle of a guard
  pass is taken as over, and the pass continues giving up
  material, against P7's clause that a later class is
  touched only while the disk measures at or over the
  threshold.

F4:
: The disk guard model once had no witness configurations
  in its own files. Closed by adding them.

F5:
: A weak additional key is refused in the default key's
  name, against P6's clause that the error names the
  setting that cost the start.

F6:
: A file cut inside a character at the local cap is
  refused as not UTF-8, though it is UTF-8 read whole and
  its fault is its size, against P12's clause that the
  recorded reason is the envelope's.

F7:
: A result cap under the fitting's floor sends the body
  over the cap, marked, against P11's words. The floor is
  a property of the fitting's last pass, not of any one
  result.

# Operational Considerations

The model is a model of decisions, not of the whole
program. Each model abstracts one decision into the
classes its inputs fall into, and the conformance suite is
what ties a class back to the inputs it stands for. An
operator should read a verdict as: this decision, over the
inputs the classes cover, behaves as the property states,
except where a finding says otherwise. Values in the
inventory change as the code changes; the pin suite is the
mechanism that keeps this document honest between
revisions, and a deployment that changes a pinned value
has changed the claims of this document whether or not the
document has been reissued.

# IANA Considerations

This document requests no IANA action. It defines no new
registrations, code points, or parameters. The group value
4588 for X25519MLKEM768 is registered by {{RFC10024}} and
is only cited here.

# Security Considerations

The security value of this document is the precision of its
claims. A property that has been checked is stated with the
model that checks it and the count of states the checker
examined, and the findings state where the implementation
falls short of a property's strongest reading, including
the two places, F2 and F3, where it falls short of the
property's own words, and F7, where a stated cap does not
hold under a floor the fitting cannot go below. A reader
deciding how much to trust the runner should weigh the
findings as part of the protocol's security posture, not
as footnotes to it.

The checking itself has limits. The models are finite
abstractions written by the same hands as the code, and a
mistake shared by both is invisible to the conformance
suite; the witness configurations guard against vacuous
passes, not against a wrongly drawn class boundary. The
checker examines the model, not the compiled program. The
claims of this document are therefore claims of checked
models held to the code by tests, which is a stronger
position than untested assertion and a weaker one than a
proof of the program itself, and the document asks to be
read as exactly that.

--- back

# Acknowledgments

The model work stands on the TLA+ language and the TLC
model checker {{TLA}}, and on the project's own proof
shelf, where the constraint inventory, the property files,
the models, and their records are kept with the code they
describe.
