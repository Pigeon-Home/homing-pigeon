# Behind the signature: whose text is it

The audit of this branch found a line of the log that named
a job by a text the signature does not cover. The line was
cut the same day. The owner's direction for it is the
subject of this page: do not only mend the line. Say what
the constraint spec was missing, put it in the spec, and
prove it, the way every constraint of version 4 is proven.

What follows is that work in the method's order. The rule
comes first, then what is supposed, written before anything
was run. The measure and the conclusions are added below
them when they are made.

## In short

- **The signature covers the body. It does not cover the
  subject, the sender, or anything else around the body.**
- **So a text from outside the signature is a stranger's**,
  even in a mail whose signature is good, until the gate
  has set it equal to a signed text.
- **The gate set the subject's id against the body's id
  late**, after 2 uses of it. That stretch is the finding,
  F16.
- **The rule is the protocol's own sentence, kept.** The
  version, the type and the id are checked first behind the
  signature, before anything else in the body is acted on.
- **It needs no new number.** It is C13, with its place
  made part of it.

## How this came about

`v4-before-the-mac.md` measured what a message costs when it
fails at the signature, and closed F12 there: every text a
stranger chooses is written to the log at a bounded length.

The audit of 2026-11-19 then met a line that F12's measure
had never reached. It is written behind the signature. A
body this runner's own key signed, sent again under a
subject that names another id, passes the signature. The
gate refused it only when it set the 2 ids side by side,
and by then it had named the job by the subject's id twice:
in 1 line of the log when clear text is allowed, and in the
security audit when the audience does not match.

F12, F13 and F15 were each found as a fault and closed as a
fault. This page takes the fourth of that kind another way.
It asks what all 4 are cases of.

## 3 labels, and 3 kinds of use

Every text the gate handles has 1 of 3 labels at each step.

| Label | What it is |
|-------|------------|
| A stranger's | Not under a signature that has verified. In front of the signature that is every text of the mail. Behind it, it is still every text outside the signed body: the subject, the sender, every other header, and what stands beside the signed object |
| Signed | Inside the signed body, once the signature has verified. It is the word of a holder of the key, and no more than that: the key's policy still decides what the holder may ask |
| The runner's own | Its configuration, its state, and its constants |

And the gate uses a text in 1 of 3 ways.

| Use | What it is | The rule for a stranger's text |
|-----|------------|--------------------------------|
| A record | A line of the log, an entry of the security audit, an event | Only a copy cut to a bar |
| Work | Parsing, decoding, hashing | Only work bounded by a count of the text's length |
| A name | The job's identity: in a record that says "job", in the seen set, in a file's name, in the result | Never |

There is 1 way for a stranger's text to change its label.
The gate sets it equal to a signed text. That step is a
binding. The id has 2 of them. For a sealed body the id is
bound by the cipher: the body does not open under another
subject. For a body in clear text it is bound by the
check of C13, and only there.

## The findings, read by the labels

| Finding | The text | Its label | The use | What was wrong |
|---------|----------|-----------|---------|----------------|
| F10 | The text in front of the signed object | A stranger's | Work | The search grew with the square |
| F11 | The subject, as a mail library writes it | A stranger's | The binding itself | An honest subject did not bind |
| F12 | The id, the subject, the sender, the key id | A stranger's | A record | Written whole |
| F13 | The subject | A stranger's | Work | The decoder grew with the square |
| F14 | The script | Signed | Work | The reader grew with the square |
| F15 | The mail's own shape | A stranger's | Work | The gate had no answer |
| F16 | The subject's id, behind the signature | A stranger's | A name | Used as the job's name before it was bound |

F16 is the first of them in the third row of uses. The
others are a record or work that was not bounded. F16 is a
stranger's text standing where only a signed text may.

## Finding F16: the unbound stretch

P1 records the order of the gate's checks, and says why the
order is part of the property: 2 checks in the wrong order
can leak what the later check exists to hide. The order as
the code performed it:

| Step | The check | What it reads |
|-----:|-----------|---------------|
| 3 | Verification and decryption | The body, and the subject's id for a sealed body |
| 4 | The clear text decision | Whether the body was sealed. With clear text allowed it writes 1 line that names the job |
| 5 | The audience | The body's audience. A mismatch is written into the security audit, with the job's name |
| 6 | Encodability | Every text of the body |
| 7 | The script's size | The body's script |
| 8 | Version, type, identity | The body's version, type and id, and the subject's id |

Between step 3 and step 8 the gate holds 2 things it has
not yet set right. The first is the job's name, which is
still the subject's id. The second is the body's version:
steps 5, 6 and 7 read a body as a version 1 job before
step 8 has said that it is 1.

`PROTOCOL.md` says of the version that it is "checked once
the signature has verified, before anything else in the
body is acted on". The code did not keep that sentence, and
the list around the sentence did not either.

The model has the same stretch. `gate.tla` follows the
recorded order step for step. It has a variable for the
audit's record, and it sets it at step 5 for a message
whose id is wrong. No invariant asked about that. And no
configuration of the model allows clear text, so the line
of step 4 was never in a checked run.

## The rule

**C13, with its place.** A job's `v` is the integer 1, its
`type` is `job`, and the body's id is the subject's id.
These 3 are checked first behind the signature. Until they
pass, the gate acts on nothing else in the body, and no
record names the job.

Said by the labels: behind the signature the gate first
binds. After that step the job has 1 name, and it is the
signer's.

This adds no row to the constraint inventory. C13 is there.
What it gains is its place, which the protocol's page
already gave it in words.

## Suppositions, written before the measure

Nothing below was run when this was written. The model was
read, and the code was read.

- **B1. The model as it was shows the finding.** With the
  steps in the order above, and a configuration that allows
  clear text, the checker finds a handling in which a
  record names a job whose id is not the body's. Supposed:
  it finds a second, in which the audience is read from a
  body whose version is not 1. Supposed: both are found in
  7 states or fewer.
- **B2. The model, binding first, holds.** With step 8
  moved to stand behind step 3, 2 new invariants hold in
  every configuration: the 3 that stand, and a fourth that
  allows clear text. P1's own invariants hold as before.
  Supposed: the count of handlings that end in execution
  is the same in both orders, to the handling. The order
  changes which refusal a message gets. It does not change
  which messages run.
- **B3. The code, binding first, changes no decision.**
  Supposed: with the check moved in `handle_mail`, every
  message that ran still runs and every message that was
  refused is still refused. The 6 orders the conformance
  suite pins still hold. Supposed: 3 tests or fewer in the
  tree pin the old place of the check.
- **B4. The real gate is the model's, on every arrival of
  the stretch.** A message is built for each way the 5
  checks of the stretch can pass or fail, in clear text and
  sealed, with clear text allowed and not, in each mode of
  the audience. Supposed: on each, the refusal the real
  gate records is the model's, and nothing the gate writes
  carries the subject's id unless the id was bound.
- **B5. The labels can be walked in the code.** A walk of
  `handle_mail` that gives each name its label and follows
  it to each use. Supposed: on the gate as it stands on
  main, the walk names 2 uses of the subject's id between
  the signature and the id's check, and they are the 2 the
  audit found. Supposed: on the gate binding first, it
  names 0. Supposed: it finds between 5 and 15 records that
  carry a signed id before the id's shape is checked.
- **B6. A signed body under a stranger's envelope adds a
  fixed amount.** The ladder of `v4-the-ladder.md`, climbed
  behind the signature: 4 texts outside the signature, each
  grown on the series under a body this runner's key
  signed. Supposed: for an envelope whose id is not the
  body's, the gate writes the same 2 lines at every step,
  under 4,096 bytes, and writes nothing else anywhere.
  Supposed: for an envelope whose id is the body's, the job
  runs at every step and its result is the same.
- **B7. An honest job is as it was.** Supposed: its lines
  in the log are the same, byte for byte, in clear text and
  sealed.
- **B8. The fuzz data beside it.** The corpus of every
  target that enters `handle_mail` is replayed on the gate
  binding first. Supposed: every entry keeps its verdict.
- **B9. The whole suite.** Supposed: the 2 reds this
  machine had before, and no other.

## What would show this wrong

- A message that ran before and does not run now, or the
  other way.
- A use of the subject's id as a name that the walk does
  not see.
- A sender's honest mail that the binding refuses, as F11
  was.
