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

## The measure

Run on 2026-11-19 on 1 machine: Linux, 2 cores, Python
3.13.18. The checker is TLC 2.19 on Java 21.

### B1 and B2. The model

`gate.tla` gained 2 variables, 1 constant and 2 invariants.
`named` says a record names the job. `read` says the gate
has acted on a member of the body other than its version,
its type and its id. `BindFirst` is the order of the
stretch: true is the order that stands, false is the order
as the code performed it.

- `NamedByTheSignedId`: `named => m.idOk`.
- `OneVersionBeforeTheBody`: `read => (m.versionOk /\
  m.typeOk)`.

The model was first written apart from the file, in the
suite, and walked whole: every 1 of 786,432 messages, in
both orders, in every configuration. Its counts were the
prediction. The checker was run after, and gave the same.

| Configuration | Distinct states | Generated | The 5 invariants |
|---------------|----------------:|----------:|------------------|
| `gateenforce.cfg` | 2,291,720 | 3,078,152 | hold |
| `gatedefault.cfg` | 2,293,264 | 3,079,696 | hold |
| `gateaudit.cfg` | 2,293,264 | 3,079,696 | hold |
| `gatecleartext.cfg`, new: clear text allowed | 2,294,800 | 3,081,232 | hold |

The default and the audit forms check 4 of the 5, as they
did 2 of the 3 before: the fifth is the audience's own.

With the order turned back, the 3 forms that stood give
2,309,000, 2,320,144 and 2,320,144 distinct states. That is
the checker's own record of the model before this change,
in `stage2.md`, to the state. So the file is the model that
was, with 1 seam added.

Then the witnesses, each with the order turned back. Each
fails, as it must.

| Witness | The form | The invariant | The checker | States that break it, by the walk |
|---------|----------|---------------|-------------|----------------------------------:|
| `gatewitnessunbound.cfg` | Enforce, clear text allowed | `NamedByTheSignedId` | Violated in 6 states | 20,736 |
| `gatewitnessnamed.cfg` | Audit, clear text refused | `NamedByTheSignedId` | Violated in 7 states | 8,448 |
| `gatewitnessversion.cfg` | Enforce, clear text refused | `OneVersionBeforeTheBody` | Violated in 7 states | 17,280 |

The shortest is 5 steps: panic, raw size, dispatch,
verification, and then the line for a job in clear text,
written for a message whose id is not the body's.

2 things the walk showed that were not supposed:

- **The strong form had it too.** `gateenforce.cfg` is the
  configuration the model was always checked in. With the
  order as it was, 3,072 of its states break
  `NamedByTheSignedId`: the audit's entry for a wrong
  audience. No invariant asked.
- **The second invariant breaks in every form**, the
  default among them: 25,344 states with the audience off.
  The audience is read in every mode.

**The same messages run.** In each configuration the count
of handlings by how they end is the same in both orders.

| Configuration | Execute | Dry run | Resent from the record | Sensor branch | Refused |
|---------------|--------:|--------:|-----------------------:|--------------:|--------:|
| `gateenforce.cfg` | 1 | 6 | 2 | 12 | 786,411 |
| The other 3 | 2 | 12 | 4 | 24 | 786,390 |

### B3 and B4. The code

The check of C13 is now the 2 statements that follow the
call that asks for the signature, in `handle_mail`. Nothing
else in the function changed its place.

384 arrivals were then sent to the real gate: 6 members of
the message, 3 modes of the audience, with clear text
allowed and not. Every body is signed by the runner's own
key.

| What the model says | Arrivals | The real gate |
|---------------------|---------:|---------------|
| Refused for the version or the type | 288 | The same refusal, on each |
| Refused for the id | 48 | The same |
| Refused for clear text | 12 | The same |
| Refused for the audience | 6 | The same |
| Refused for the script's size | 15 | The same |
| Runs | 15 | Runs |

336 of the 384 carry an id that is not the body's, or a
body of another version. For each, everything the gate
wrote was read: every line of the log, with the verbose
lines, and every byte of every file under its folder.

- The subject's id is in the gate's first line, cut, and
  in nothing else.
- The security audit has no entry.
- No line says the job arrived in clear text.

The arrival of the finding itself is held by name: this
runner's signed body in clear text that is allowed, under a
subject whose id is 100,000 escape characters, with a wrong
audience in audit mode. The gate writes 2 lines of under
4,096 characters together, with no escape in them, and no
file.

A body with a lone surrogate is not among the 384. That
check also stands in the verification step, so such a body
never reaches the stretch.

With the change taken out, 5 of the 6 tests of that class
fail. The sixth is the honest job's lines, B7.

### B5. The labels, walked in the source

The walk reads `handle_mail` in the order of its source.
It gives every name 1 of the 3 labels, and a fourth mark,
cut, for a stranger's text that a call has written at a
bounded length. A name made from other names has the
highest of theirs. It knows 3 things about the gate's
calls: which write a record, which cut a text to a bar, and
which only answer yes or no. It finds where the signature
is asked for, and the `if` that sets a stranger's name
against a signed text and ends the handling when they
differ. That `if` is the binding, and past it the name is
signed.

| The gate | Records with a stranger's text, uncut | Uses of a stranger's name behind the signature |
|----------|--------------------------------------:|-----------------------------------------------:|
| As it stands on main | 7 | 2 |
| On this branch, binding first | 0 | 0 |

The 7 on main are every finding of this kind, with nobody
pointing at them. 5 are in front of the signature and are
F12: the refusal's reason in 2 lines, and the id, the
sender and the subject in the first line. 2 are behind it
and are F16: the line for a job in clear text, and the call
that writes the security audit. Those 2 are also the only 2
uses of the subject's id behind the signature.

The suite cannot read main's file. It makes the gate as it
was from the source that stands, by putting the check back
last of the stretch and undoing each cut, and the walk
finds the same 7 there.

The walk also counts what is not a fault. Behind the
binding the id is the signer's, and 21 lines of the gate
write a signed text whole. 15 of them carry the id before
the job is run, which is where the id's shape is checked.
A holder of the key writes those lines.

### B6. The ladder, behind the signature

9 ladders of 24 steps, 216 arrivals. Every body is this
runner's signed job in clear text, and 1 text outside the
signature is grown on the series.

| The text grown | Units | To | At every step |
|----------------|-------|---:|---------------|
| The id in the subject | A letter, an escape, an encoded word | 46,368 characters, and 602,784 for the encoded word | Nothing runs. 2 lines, 129 to 539 characters together. 0 bytes written |
| A word of the subject | A letter, an escape | 46,368 | The same job runs. 5 lines, 524 characters at the most |
| The sender | A letter, an escape | 46,368 | The same job runs. 5 lines, 539 at the most |
| A note beside the signed object | A letter, a line end | 46,368 | The same job runs. 5 lines, 275 at the most |

What the gate keeps of a job that ran is 2,128 to 2,138
bytes at every step. The 10 are the digits of the step's
number in the job's id.

### B7. An honest job

Its lines are the same, to the letter, in clear text and
sealed: the first line, the line for clear text where it
applies, and the line that says the job is run.

### B8. The fuzz data

On this branch no corpus entry enters `handle_mail`. The
registry said so for C1, C2, C12 and C15, and its own
measure says so for C13's new place. So here there was
nothing to replay.

The fuzz reader that holds the gate stands on main, since
2026-11-19. On a scratch joining with main, thrown away
after:

- main's own check of that reader over its corpus is green
  on the gate binding first;
- 15 of its entries enter `handle_mail`, of 0 to 11,642
  bytes, and 3 of them reach the check of C13;
- the reader climbs the ladder as it did before: 60
  ladders from its 15 seeds, each verdict its seed's.

So on the day the branch meets main, C13's place has fuzz
data beside it.

### B9. The whole suite

14,321 tests in 1,457 seconds. 273 skipped, and 2 red: the
2 bench tests this machine had red before the branch. The
guard is green on the 3 test modules this change touches.

## Conclusions, against the suppositions

| | Supposed | Found | Held |
|--|---------|-------|------|
| B1 | The model as it was shows the finding, in 7 states or fewer | 3 witnesses, in 6, 7 and 7 states | Yes. And the strong form had it too, which was not supposed |
| B2 | Binding first, the 2 invariants hold, and the same handlings execute | They hold in 4 configurations. Every ending has the same count in both orders | Yes |
| B3 | No decision changes. 3 tests or fewer pin the old place | 1 test pinned it: this seat's own, written the same day for the line | Yes |
| B4 | The real gate is the model's on every arrival of the stretch | 384 of 384 | Yes |
| B5 | The walk names the 2 uses on main and 0 here. 5 to 15 records carry the signed id whole | 2 and 0. 15 | Yes, at the top of its range |
| B6 | An envelope with another id adds the same 2 lines and nothing else | 2 lines, under 540 characters, 0 bytes, at 72 steps | Yes |
| B7 | An honest job's lines are as they were | To the letter | Yes |
| B8 | Every corpus entry keeps its verdict | On the branch there is nothing to replay. On a scratch joining with main, 15 entries, each kept | Yes, on main's data. Here it was empty |
| B9 | The 2 reds this machine had, and no other | 14,321 tests, and those 2 | Yes |

## What was changed

| What | Where |
|------|-------|
| The check of C13 stands first behind the signature | `runner/ops/mail.py` |
| C13 states its place | `constraints.md` |
| P1's recorded order has the check fourth, and says what the order holds | `properties.md` |
| The list of checks is in the order the sentence in it already gave | `PROTOCOL.md` |
| 2 variables, 1 seam, 2 invariants | `gate.tla` |
| 1 new configuration and 3 new witnesses. The 5 that stood name the seam | `gatecleartext.cfg`, `gatewitnessunbound.cfg`, `gatewitnessnamed.cfg`, `gatewitnessversion.cfg` |
| C13 is tied to its place and to 3 more tests, and P1 to its 2 new invariants and to this suite | `v4-bindings.json`, `v4-bindings.md` |
| The suite: 22 tests | `runner/tests/test_v4_behind_the_mac.py` |

No row was added to the constraint inventory, and no
default changed. The drafts are not touched.

## The technique, as any seat can run it

The finding was a fault in 1 line. Read as a technique it
is a walk that can be taken through any reader.

1. **Say what the signature covers.** Everything else is a
   stranger's, in front of the signature and behind it.
2. **Name the bindings.** For each text outside the
   signature that the reader uses as the message's own,
   find the step that sets it equal to a signed text. If
   there is none, that is the finding.
3. **Bind first.** Put that step straight behind the
   signature. Then the stretch in which a stranger's text
   stands for a signed text has no length.
4. **Walk the labels in the source.** Give every name its
   label, and follow it to every record. A stranger's text
   is cut. Behind the signature a stranger's name is used
   to bind it, and for nothing else.
5. **Put the order in the model as a seam.** A constant
   that turns the order back, an invariant that breaks when
   it is turned, and a witness that shows the break. The
   order is then held by the checker and not by a reading.
6. **Climb the ladder behind the signature too.** Grow
   each text outside the signature under a body that the
   runner's own key signed. F12's measure grew them only
   under a signature that fails, and missed the line.

## What this opens

Each is named and none is measured here.

1. **The other half of P1.** P1 says when a job runs. It
   says nothing of a message that does not run. The
   candidate P14, on `v4-before-the-mac.md`, says it for a
   message that fails at the signature. This page reaches
   1 step further, to a message that fails at the id.
   Stated whole it is 1 sentence: a message that does not
   run leaves nothing behind that grows with a text its
   signer did not sign.
2. **Every surface has an envelope.** A query, a
   cancellation, board mail, version 2 mail, a chain, a
   local envelope and a session are each read by their own
   handler, in front of this gate. Each has a subject
   outside its signature. Where each binds it is not on
   this page.
3. **The id's shape, at the binding.** The id is checked
   for its 128 safe characters where the job is run. If
   C13 checked it too, the 15 records above would carry a
   text of a known shape, and no later line would need a
   cut. It changes 1 answer on the wire: a job whose id is
   not of that shape would be refused with no result,
   where today a result says why. That is the owner's.
4. **The walk past 1 function.** It reads `handle_mail`.
   The functions the gate calls are known to it by name
   only. The core is 136 files. A walk that follows a text
   through a call would hold the rule for all of them.
5. **A third kind of use.** This page walks records. A
   name is the stronger case: a file's name, a key of the
   seen set, the result's subject. The walk's second list
   holds it for the gate. It is not yet a list by kind.
6. **Version 4's text.** The model's 2 invariants are 2
   sentences the draft does not have. They are offered to
   the seat that keeps the draft: a receiver acts on
   nothing in a signed body before its version is known,
   and it names a message in a record only by an id the
   signature covers.

## What would show this wrong

- A message that ran before and does not run now, or the
  other way.
- A use of the subject's id as a name that the walk does
  not see.
- A sender's honest mail that the binding refuses, as F11
  was.
