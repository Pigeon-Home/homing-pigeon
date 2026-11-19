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
- **S6 held.** No sealed body was opened before its
  signature.
- **S7 held.** Each refused message was marked seen once.
- **S8 is not tried yet.** The model is the next step.

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

## What is made, and what is next

- Made: the suite, which holds S1 to S7 on every suite run.
- Next: a model of the 6 steps before the MAC, with the log
  in its ledger, its configuration and its witnesses, and
  its search in the suite. That is S8.
- Next: a row for the candidate in the registry, kept apart
  from the 31 until the owner's word.
- F12 is closed on the branch. It reaches main at the
  owner's word.
- F11's 2 closings are decided on the desk. They are not yet
  made.
- Not measured: the other kinds of message the dispatcher
  reads before their own signature checks.
