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

## The measure

`runner/tests/test_v4_before_the_mac.py`, run on 2026-11-19.
The wire corpus's 41 fresh jobs that run under a key the
runner holds were each made to fail at the signature 2 ways:
signed by a key the runner does not hold, and with 1 digit
of the signature turned. That is 82 messages. Each went to
`handle_mail` as it is, with its subject grown to 1,000,
10,000 and 100,000 bytes, and with its body grown to 10,000
and 100,000 bytes: 492 arrivals, of 336 to 100,602 bytes.

| What was counted | Over the 492 arrivals |
|------------------|-----------------------|
| Jobs run | 0 |
| Mails sent | 0 |
| Entries added to the seen set | 0 |
| Files left under the runner's folder | 1, the security events file |
| Records added to it | 1 for each arrival, of 84 bytes every time |
| Seen marks set in the mailbox | 1 for each arrival |
| Characters given to the parser | at most 1.42 times the message |
| MACs computed | 1 for each arrival, with 6 keys held |
| Bytes given to the MAC | at most 0.58 times the message |

The 41 messages under a strange key were also sealed, as
they were and with 1 digit of the envelope's signature
turned. None of the 82 was opened before its signature.

The log, for 1 refused message, by the size of its subject:

| Subject | The mail | Added to the log file | Printed |
|---------|----------|-----------------------|---------|
| as it is | 393 bytes | 195 bytes | 195 characters |
| 1,000 bytes | 1,361 | 1,163 | 1,163 |
| 10,000 bytes | 10,361 | 10,163 | 10,163 |
| 100,000 bytes | 100,361 | 100,163 | 100,163 |
| 4,000,000 bytes | 4,000,361 | 4,000,163 | 4,000,163 |

## Conclusions against the suppositions

- **S1 held.** Nothing ran and nothing was sent, on all 492.
- **S2 held.** The seen set gained nothing, and no record of
  a job was left.
- **S3 held.** 1 refusal record for each arrival, of 84
  bytes whatever the message's size.
- **S4 held, and it is a finding.** It is F12, below.
- **S5 held, with room.** The parser was given at most 1.42
  times the message, against the 16 supposed. The MAC was
  computed once, and not twice for each key: the runner
  asks only for the key a message names.
  *Added 2026-11-19.* 1.42 is the most over these 492
  arrivals, which grow a subject or a note and leave the
  signed text small. `v4-the-ladder.md` grows the signed
  text itself, at every size of its series, and there a
  message that fails at the signature gives the parser up
  to 3.30 times its length. The reader's looks grow by 4,
  so the count sits in a band, and its top by the code as
  read is 3 and a third. The 16 supposed still stands.
- **S6 held.** No sealed body was opened before its
  signature.
- **S7 held.** Each refused message was marked seen once.
- **S8 stands in part.** The model is made: see "The model:
  S8" below. It holds P14 and 6 more invariants, and the
  suite searches it. Its witnesses are 3 probes and the 2
  findings it has at the gate as it was. A witness for each
  step moved out of its place is not made: the model states
  the order as 1 decision, and the suite reads the order
  off the gate's source.

So clauses 1, 2 and 4 of the candidate hold on the gate as
it stands, for every message tried. Clause 3 holds for what
is kept under the runner's folder, and it fails for the log.

## Finding F12: a refused message writes its whole subject to the log

**Found by supposition S4 and the measure. Closed on the
branch, 2026-11-19: see the closing below.**

Before it asks for the signature, the gate logs 1 line that
names the job and carries the subject as it is written. The
line is as long as the subject, and a subject is bounded
only by C1. A refused message with a subject of 4,000,000
bytes added 4,000,163 bytes to the log file, and as many
characters to the console.

The log file is bounded: 33,554,432 bytes, with 4 older
files kept, 167,772,160 bytes in all. So this does not fill
a disk. What it does is turn the log over. 42 such messages
are more than the log holds. None of them needs a key, and
all 42 fit inside the 50 lines a minute that the log lets
through. After them, the log's history is their subjects.

The security events file is another file, and this does not
touch it: the 84 byte record of each refusal stands.

Clause 3 of the candidate is what names this. 1 way to close
it: the line is bounded. The subject is logged up to a fixed
length, with its full length as a number. A subject that
carries a job needs at most 1,811 bytes in its longest
spelling, by finding F11's measure on the binding page. The
suite pinned the gap as it stood, and the closing below
turned that pin.

## Closing F12: suppositions, written before the measure

The closing was taken up on 2026-11-19, at the owner's word.
These were written before any field but the subject was
grown, and before the gate's code was changed.

- **K1. The subject is not the only field.** 4 texts that a
  stranger chooses reach the log in front of the signature,
  each whole: the subject; the id, which is 1 token of the
  subject and is written a second time beside it; the
  sender's address; and the key id of the body, which the
  refusal's line repeats. The measure so far grew only the
  subject. Supposed: each of the 4 grows the log in step
  with its size, and the id grows it twice over.
- **K2. The refusal's line stands outside the minute
  budget.** It is written as a warning, and warnings always
  pass. Supposed: a stranger who grows the key id is not
  held to 50 lines a minute.
- **K3. A stranger can break a line.** Only the subject is
  written quoted. Supposed: a control character in the id
  or in the sender's address reaches the log file as it is.
- **K4. With every such text bounded, 1 refused message adds
  a fixed amount.** Supposed: under 4,096 bytes, whatever
  field is grown, up to the C1 cap.
- **K5. An honest job's lines do not change.** Supposed: for
  an id of up to 128 characters, an address of up to 254
  and a subject of up to 256, the gate writes the same
  bytes as before.
- **K6. Nothing is lost that the gate needs.** Supposed: the
  id the gate works with is the whole id, not the cut copy.
  Only the log's copy is cut, and the cut says the full
  length.

Outside this closing: the other kinds of message the
dispatcher reads before their own signature checks (a
cancel, a query, the board, a chain, a version 2 message, a
bounce). Supposed to have the same shape. Not measured here.

### The measure for the closing

1 job from the fuzz corpus, signed by a key the runner does
not hold, with 1 text grown at a time. The log file is the
runner's own. The message as it is sent adds 195 bytes, in
2 lines: the line that names the job, and the refusal. The
table is what a grown text adds over those 195.

| Text grown to 1,000,000 | Before, bytes | After, bytes |
|-------------------------|--------------:|-------------:|
| The subject | 999,968 | 248 |
| The id | 1,999,976 | 390 |
| The sender's address | 999,998 | 266 |
| The key id | 1,000,004 | 508 |
| A key id that is not a string | 999,994 | 508 |
| The body, elsewhere | 0 | 0 |

After the change, grown to 1,000 and to 100,000, each text
adds the same as at 1,000,000, less 1 or 2 digits.

Every text grown at once, in the characters the quoting
writes longest (an escape in the 2 headers, a 4 byte letter
in the key id): 2,788 bytes of log at 1,000 characters each,
and 2,796 at 100,000 each, where the message is 700,392
bytes. At 1,000,000 each the message is past the C1 cap, and
the gate's line for that is 91 bytes.

### Conclusions against K1 to K6

- **K1 stands, and it is the larger part of the finding.**
  Each of the 4 texts reached the log whole. The id reached
  it twice, as supposed: 1,999,976 bytes for 1,000,000. A
  key id that is a list reached it as a string does. The
  rest of the body never reached it.
- **K2 stands.** 60 refused messages inside 1 minute wrote
  60 refusal lines and 25 of the 60 lines that name the
  job. The budget counted 50 lines and then let only the
  warnings through. So the key id was the wider door: no
  count of lines held it, only the size of each line.
- **K3 stands for the id, and is corrected for the
  address.** An escape character in the id reached the log
  file as it is. From the sender's address it did not, in
  the 2 shapes tried, and a folded address added no line:
  the mail library's address reader did not hand them on.
- **K4 stands.** No text adds more than 508 bytes, and every
  text at once adds 2,796 at the most. The suite holds 1
  refused message to 4,096 bytes of log.
- **K5 stands.** The message as it is sent writes the same
  195 bytes as before, byte for byte. At each limit the
  text is written whole, and 1 character past it the cut
  begins.
- **K6 stands.** A job the runner holds the key for, under
  a subject of 1,000 bytes, ran. Its result named the whole
  id. Its line in the log named the whole id, and cut only
  the subject, saying 1,000.

1 correction came in the making. The quoting can grow a
text: an escape is written as 4 characters. A cut that
counts the text's characters let a text of control
characters write 4 times its limit. The cut counts what is
written, and reads only the first characters of the text to
do it: on a text of 4,000,000 characters it took 0.00001
seconds.

### What was changed

- The gate writes each text a stranger chooses at a bounded
  length, in the 2 lines it writes in front of the
  signature and in the 1 line of the answer-only mode: the
  id up to 128 characters, the sender's address up to 254,
  the subject up to 256, the refusal's reason up to 512.
  Past its limit a text is cut and its full length is
  written as a number. A text with a control character in
  it is written quoted.
- The limits are the longest an honest message needs: 128 is
  the job's own rule for an id, 254 is the longest address
  a mail path carries, and a subject with the longest id
  is 148 characters as it is sent.
- The gate works with the whole id. Only the log's copy is
  cut.
- The suite turned its pin. 8 tests hold the closing, in
  `runner/tests/test_v4_before_the_mac.py`. On the code as
  it was, all 8 fail.

With the closing, clause 3 of the candidate holds with the
log counted: the seen mark, 1 refusal record of 84 bytes,
and 2 lines of at most 4,096 bytes together. In a verbose
run a third line repeats the reason, under the same limit.

## Finding F13: the panic step decodes the whole subject

**Found in writing the model for S8, 2026-11-19.**

The second step in front of the MAC is the panic word. To
read it, the gate hands the subject to the mail library's
decoder for encoded words: the whole subject, before the
size cap and before the dispatcher. On a subject made of
encoded words, the decoder's time grows with the square of
the subject.

| Subject, bytes | The panic step, seconds |
|---------------:|------------------------:|
| 15,992 | 0.003 |
| 63,984 | 0.034 |
| 255,980 | 0.486 |
| 1,000,008 | 8.55 |

The whole gate spent 0.557 seconds on a refused message
under the subject of 255,980 bytes. By that curve a subject
at the C1 cap costs about 150 seconds. That last figure is
not measured. None of it needs a key.

Clause 4 of the candidate is what names this. The work is to
be bounded by a count of the message's length, and the
square of the length is not that. Supposition S5 held on its
own count, which read the parser and the MAC and did not
read this step. So S5 is corrected: it holds for the 2 it
counted, and the panic step stood outside its count.

A panic subject is short. As typed it is 51 characters. In
1 base64 word it is 80. In its longest spelling, 1 character
to an encoded word and each escaped, it is 815.

### Closing F13: suppositions, written before the change

- **N1. A bound on what the step reads closes it.**
  Supposed: with a subject over 2,048 characters never
  handed to the decoder, the gate's time on the refused
  message of 255,980 bytes falls under 0.05 seconds, and
  from there it grows no faster than the message.
- **N2. Every honest panic subject still fires.** Supposed:
  the 3 spellings match as before, and so does a typed word
  padded with white space up to 2,048 characters. At 2,049
  it is not a panic.
- **N3. No other step in front of the signature uses that
  decoder.** Supposed from a search of the code: the panic
  step is its only caller in the gate.

Outside this closing: the DTLS mailbox reads its mail under
the mail library's default policy, which decodes headers as
it reads them. Not measured here.

### The measure for the closing of F13

The same refused message as in the finding, under a subject
of encoded words, at the gate.

| Subject, bytes | The gate before, seconds | The gate after, seconds |
|---------------:|-------------------------:|------------------------:|
| 15,992 | 0.005 | 0.0021 |
| 63,984 | 0.043 | 0.0071 |
| 255,980 | 0.557 | 0.0256 |
| 999,982 | not measured | 0.1034 |
| 3,999,986 | not measured | 0.4142 |

Before the change the panic step alone took 8.55 seconds at
1,000,008 bytes. After it, the gate spends about 0.0001
seconds for each 1,000 bytes of message, at every size in
the table.

### Conclusions against N1 to N3

- **N1 stands.** The gate's time on the message of 255,980
  bytes is 0.0256 seconds. From 63,984 bytes to 3,999,986
  the subject is 62.5 times as long and the time is 58
  times as long. Past the limit the decoder is handed 0
  characters, at the step and at the gate.
- **N2 stands.** The 3 spellings fire as before. A typed
  word padded with white space to 2,048 characters fires,
  and at 2,049 it does not.
- **N3 stands.** In the runner's code outside its tests the
  decoder is named in 1 file, the panic word's.

### What was changed for F13

- The panic step reads a subject of at most 2,048
  characters. A longer subject is not a panic, and the
  decoder never sees it. 2,048 is 2.5 times the longest
  honest spelling.
- 7 tests hold the step in the suite. On the code as it was,
  5 of them fail. The other 2 hold both ways: the decoder
  has 1 caller, and the panic word fires in front of the
  size cap and in front of the signature.

With the closing, clause 4 of the candidate holds with the
panic step counted.

## The model: S8

`premac.tla` states the gate's 6 steps as 1 decision, in the
shape of `decision.tla` and `localgate.tla`. An arrival is
what a stranger chooses: the kind of subject (the panic
word, a job, anything else), whether the message is over the
size cap, whether its id was seen, what the signature step
finds, and the lengths of the 4 texts the gate's lines name.
The box it meets is armed or stopped.

The lengths stand on 3 rungs: 50, 500 and 5,000. 50 is
under every limit. 500 is past the limits of the id, the
address and the subject. 5,000 is past every limit.

The gate in the model is the bounded gate, or the gate as it
was before F12 and F13 were closed. `Spec` is the bounded
gate. `SpecAsItWas` is kept so that the 2 findings stay
stated.

**7 invariants, at the bounded gate.**

| Invariant | What it says |
|-----------|--------------|
| `P14Inv` | Nothing runs but a job whose signature verified, on an armed box, under the cap, not seen before. A message that does not verify adds at most 1 record and 2 lines. One refused at the signature is marked and leaves exactly 1 record. |
| `LogBounded` | The stranger's characters in the lines come to at most 1,246. |
| `DecoderBounded` | The panic step hands the decoder at most 2,048 characters. |
| `WorkBounded` | At most 3 passes over the message, and 1 when the gate decides in front of the signature. |
| `PanicFirst` | A panic subject is a panic, whatever the size, the signature and the box. |
| `StoppedLeaves` | A stopped box leaves everything else with no mark and no line. |
| `CapBeforeTheSignature` | A job over the cap costs 1 pass, and none of its texts is copied. |

**The search, in the suite.** The same model is written
apart from the TLA+ file, in
`runner/tests/test_v4_before_the_mac.py`, and searched to
the fixed point on every suite run. Its counts are the
prediction for the checker, written down before the checker
ran: 2,160 arrivals on 2 boxes, which is 4,320 initial
states, 8,694 distinct states. The 4,320 decisions:

| Outcome | Decisions |
|---------|----------:|
| The box is stopped: left as it is | 1,728 |
| The panic word | 864 |
| Not a job | 864 |
| Too large | 432 |
| Already seen | 216 |
| Refused at the signature | 162 |
| Verified | 54 |

All 7 invariants hold in every state. The most a stranger's
characters come to is 1,246, which is the bound: it is met
and never passed. 154 of the 162 refusals carry a cut text.

**The 2 findings as counterexamples.** At the gate as it
was, 5 invariants hold and 2 fail. `LogBounded` fails in 202
states: 124 refusals, 39 verified jobs, and those 39 again
once run. Every one has a text at 500 or more, and the most
copied is 20,000 characters. `DecoderBounded` fails in 1,755
states, every one under a subject of 5,000. A message whose
texts all stand at 50 breaks neither: the findings need a
long text.

**The real gate, asked on the model's arrivals.** 281
arrivals: every kind, size, seen, signature and box at rung
50, and every rung of every text where the gate reaches the
signature. On each, the real gate did what the model's
decision says: what ran, what was sent, the mark, the
records, the lines, and the lines' length to within the
gate's own words. The order of the 6 steps is read off the
gate's source.

**The checker.** TLC, version 2.19, ran on `premac.tla` on
2026-11-19, with each of the 6 configurations.

| Configuration | The checker's verdict |
|---------------|-----------------------|
| `premac.cfg` | No error. 4,320 initial states, 13,068 states generated, 8,694 distinct states, depth 3. |
| `premacwitnessrefused.cfg` | Fails, as it must. A job at rung 50 with a bad signature is refused: 1 record, 2 lines, 150 characters copied. |
| `premacwitnessruns.cfg` | Fails, as it must. A job at rung 50 whose signature verified is run. |
| `premacwitnesscut.cfg` | Fails, as it must. A refused job under a subject of 500 has 380 characters copied: 50, 50, and the subject cut to 256 with its mark of 24. |
| `premacwitnessf12.cfg` | Fails, as it must. At the gate as it was, a job under a subject of 5,000 has 5,100 characters copied in 1 line. That is F12. |
| `premacwitnessf13.cfg` | Fails, as it must. At the gate as it was, the decoder is handed a subject of 5,000 whole. That is F13. |

The checker found the counts the search had predicted: 4,320
initial states and 8,694 distinct states.

**What the model leaves out.** A subject that is ours and
names no job. The other kinds the dispatcher reads before
their own signature checks. The log's minute budget, and a
verbose run's third line. Everything from a verified
signature on, which `general.tla` has.

## What is made, and what is next

- Made: the suite, which holds S1 to S7 and the 2 closings
  on every suite run.
- Made: the model of the 6 steps, `premac.tla`, with the log
  in its ledger, 6 configurations, its search in the suite
  and the real gate asked on its arrivals.
- Made: the checker's run on the model, with no error and
  the predicted counts.
- Next: a row for the candidate in the registry, kept apart
  from the 31 until the owner's word.
- F12 and F13 are closed on the branch. They reach main at
  the owner's word.
- F11's 2 closings are decided on the desk. They are not yet
  made.
- Not measured: the other kinds of message the dispatcher
  reads before their own signature checks.
