# The work in front of the MAC: a candidate constraint

The fuzz data has made 2 findings in the gate, F10 and F11,
and both lie in the same place: what the gate does with a
message before its signature has verified. The inventory has
no constraint for that place. The properties do not speak of
it, and no model follows it. P1 says when a job runs. Nothing
says what a sender with no key can make the runner spend,
keep or send.

This page states a candidate for that constraint and for the
property that would carry it, and then the suppositions the
next pass will test. The suppositions stand in their own
commit, written before anything is measured. Nothing in
`constraints.md` or `v4-properties.md` is changed here. A
candidate joins the inventory at the owner's word, once it
has stood its test.

## Why this place

It is where the proof of work points. The run log counts
594,073,949 inputs tried, and 477,622,130 of them were
refused: 4 in 5 of what the campaign sends is what a stranger
sends. The proofs begin where a signature has verified. The
2 do not meet, and the campaign's 2 findings at the gate fell
in the space between them.

## What stands in front of the MAC

In `handle_mail`, in order, for a mail that carries the
marker:

1. the mail is parsed and its subject is read;
2. the panic word is matched against the subject;
3. the size cap, C1, refuses a mail that is too large;
4. the dispatcher routes by the subject and asks the seen
   set;
5. 1 line of log names the job by its subject's id;
6. the signature is asked for: the signed object is found in
   the body, which is the opener search where F10 was, and
   the MAC is computed.

## The candidate

**C32, a candidate. The work in front of the MAC.** For a
message whose signature does not verify, the runner:

1. runs nothing;
2. sends nothing;
3. keeps nothing of the message but the mailbox's mark that
   it was seen and 1 record of the refusal, and the record's
   size does not grow with the message;
4. does work that is bounded by a count of the message's
   length.

The panic word is the 1 effect a message may have with no
key. It has its own rule in the protocol, and it stands
outside this constraint.

**P14, a candidate.** In every run of the gate, a message
that does not pass the signature leaves the ledger as it
found it, but for the seen mark and 1 refusal record of a
fixed size. The count of work done on it is at most K times
its length, for a K that does not depend on the message.

## Suppositions, written before the measure

Each is a guess, set down so that the measure can show it
wrong.

- **S1.** For every entry of the wire, crypto and mail
  corpora sent to the gate under a signature that does not
  verify, nothing runs and nothing is sent. That nothing
  runs was seen when the corpus went to the doors. That
  nothing is sent has not been asked.
- **S2.** Such a message adds nothing to the seen set or to
  the replay record.
- **S3.** What such a message leaves under the runner's
  folder is 1 refusal record. Its size does not grow with
  the subject or the body.
- **S4.** The log is where clause 3 will not hold as the
  code stands. The gate logs the subject as it is written,
  before the signature, and a subject is bounded only by C1.
  So I expect 1 refused mail to be able to add as many bytes
  of log as C1 lets a mail be.
- **S5.** The work before the refusal is bounded by a count.
  The parser is given at most 16 times the message's length
  in characters, which is F10's bound. The MAC is computed
  at most twice for each key the runner holds. No pass over
  the message is made more than a fixed number of times.
- **S6.** For a sealed body, the envelope's own signature is
  checked before any decryption is tried.
- **S7.** A refused message is marked as seen in the
  mailbox, so the same mail is not read twice.
- **S8.** A model of the 6 steps above, with a ledger of what
  ran, what was sent, what was kept and how much was read,
  holds P14 as an invariant, and for each step taken out of
  its place a witness breaks it.

## What the pass will make

- A suite, `runner/tests/test_v4_before_the_mac.py`, that
  sends the corpus and its hostile growths to the gate under
  signatures that do not verify, and counts what ran, what
  was sent, what was kept and how much was read.
- A model of the steps before the MAC, its configuration and
  its witnesses, and its search in the suite.
- A row for the candidate in the registry, kept apart from
  the 31 until the owner's word.
- The conclusions against S1 to S8, on this page.
