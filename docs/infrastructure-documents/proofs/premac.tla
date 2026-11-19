------------------------------ MODULE PreMac ------------------------------
\* P14, a candidate, of v4-before-the-mac.md: the work in front
\* of the MAC. For a message whose signature does not verify,
\* the runner runs nothing, sends nothing, keeps nothing of the
\* message but the seen mark, 1 refusal record and lines of a
\* bounded size in its log, and does work bounded by a count of
\* the message's length. The gate is handle_mail in
\* runner/ops/mail.py, and its steps in front of the signature
\* are 6:
\*
\*   1  the mail is parsed and its subject is read
\*   2  the panic word            (runner/guard/panic.py)
\*   3  the size cap, C1
\*   4  the dispatcher            (_early_dispatch)
\*   5  1 line that names the job by the subject's id
\*   6  the signature             (_verify_and_decrypt)
\*
\* This is one decision, not a trace of jobs, in the shape of
\* decision.tla and localgate.tla. An arrival is what a
\* stranger chooses:
\*
\*   kind  "panic"  the subject is the armed panic word
\*         "job"    the subject names a job
\*         "other"  anything else: not ours
\*   over  the message is over the size cap
\*   seen  the job's id is in the seen set
\*   sig   what the signature step finds:
\*         "good", "bad", "unknown key", "malformed"
\*   id, snd, sub, key
\*         the lengths, in characters, of the 4 texts the
\*         gate's lines name: the id, the sender's address, the
\*         subject, and the key id of the body
\*
\* and the box it meets is "armed" or "stopped": stopped is a
\* box whose panic word fired before this arrival.
\*
\* The lengths stand on 3 rungs, 50, 500 and 5000. 50 is under
\* every limit, an honest length. 500 is past the limits of the
\* id, the address and the subject, and under the limits of the
\* reason and of the panic step. 5000 is past every limit. A
\* subject holds its id, so it is at least as long, and a
\* panic subject is at most its longest spelling, 815.
\*
\* The gate is "as it was" or "bounded". Bounded is the gate
\* after findings F12 and F13 were closed: a text past its
\* limit is written cut, with its length said, and the panic
\* step reads a subject of at most 2048 characters. As it was,
\* each text reached the log whole and the panic step read the
\* whole subject. Spec is the bounded gate. SpecAsItWas is the
\* gate before, kept so that the 2 findings stay stated: under
\* it LogBounded and DecoderBounded fail, and their
\* counterexamples are F12 and F13.
\*
\* What a decision records:
\*
\*   outcome  "panic"         the word fired, or fired again
\*            "left"          the box is stopped: untouched
\*            "too large"     refused at the size cap
\*            "not a job"     marked, nothing more
\*            "already seen"  marked, nothing more
\*            "refused"       refused at the signature
\*            "verified"      the signature verified
\*   marked   the mailbox's mark that the message was seen
\*   records  records added to the security events file
\*   lines    lines added to the log
\*   copied   the stranger's characters in those lines
\*   passes   passes over the message: 1 for the mail's parse,
\*            1 for the body's parse, 1 for the MAC
\*
\* and beside it, decoded: the characters of the subject that
\* the panic step hands to the decoder for encoded words. That
\* decoder's time grows with the square of what it is given,
\* so the bound on decoded is the bound on the step's work.
\*
\* Behind a verified signature the job may run. The model lets
\* it, with 1 step, so that "nothing runs" is a claim about
\* everything else. general.tla has the rest of that life.
\*
\* What the model leaves out: a subject that is ours and names
\* no job (over the cap it is refused for its size, under it
\* the dispatcher marks it); the other kinds the dispatcher
\* reads before their own signature checks (a cancel, a query,
\* the board, a chain, a version 2 message, a bounce); the
\* minute budget of the log; a verbose run's third line; and
\* everything from a verified signature on.
\*
\* The model it states is searched by
\* runner/tests/test_v4_before_the_mac.py, which also asks the
\* real gate on the model's arrivals. The state counts in
\* v4-before-the-mac.md are that search's, written down before
\* the checker ran.

EXTENDS Integers

Rungs == {50, 500, 5000}

IdMax == 128
SenderMax == 254
SubjectMax == 256
ReasonMax == 512
Mark == 24
PanicMax == 2048
PanicLongest == 815

\* The most a stranger's characters come to in 1 message's
\* lines: every text past its limit, each cut and marked.
Bound == IdMax + SenderMax + SubjectMax + ReasonMax + 4 * Mark

Kinds == {"panic", "job", "other"}
Sigs == {"good", "bad", "unknown key", "malformed"}
Boxes == {"armed", "stopped"}

Arrivals ==
  {x \in [kind: Kinds, over: BOOLEAN, seen: BOOLEAN, sig: Sigs,
          id: Rungs, snd: Rungs, sub: Rungs, key: Rungs] :
     /\ x.sub >= x.id
     /\ x.kind = "panic" => x.sub <= PanicLongest}

\* A text of n characters as a line carries it.
Shown(gate, n, limit) ==
  IF gate = "bounded" /\ n > limit THEN limit + Mark ELSE n

\* Step 2: what the panic step hands to the decoder.
Decoded(gate, x) ==
  IF gate = "bounded" /\ x.sub > PanicMax THEN 0 ELSE x.sub

\* Step 5: the stranger's characters in the line that names
\* the job.
Named(gate, x) ==
  Shown(gate, x.id, IdMax) + Shown(gate, x.snd, SenderMax)
    + Shown(gate, x.sub, SubjectMax)

\* Step 6: the stranger's characters in the refusal's line.
\* Only an unknown key id is repeated there.
Reasoned(gate, x) ==
  IF x.sig = "unknown key" THEN Shown(gate, x.key, ReasonMax)
  ELSE 0

\* Step 6: passes over the message. The body is parsed, and
\* the MAC is computed when the body parsed and named a key
\* the runner holds.
SigPasses(x) == IF x.sig \in {"good", "bad"} THEN 2 ELSE 1

Quiet(o, m) ==
  [outcome |-> o, marked |-> m, records |-> 0, lines |-> 0,
   copied |-> 0, passes |-> 1]

Decision(gate, b, x) ==
  IF x.kind = "panic" THEN
    [outcome |-> "panic", marked |-> 1,
     records |-> IF b = "armed" THEN 1 ELSE 0,
     lines |-> 1, copied |-> 0, passes |-> 1]
  ELSE IF b = "stopped" THEN Quiet("left", 0)
  ELSE IF x.kind = "job" /\ x.over THEN
    [outcome |-> "too large", marked |-> 1, records |-> 0,
     lines |-> 1, copied |-> 0, passes |-> 1]
  ELSE IF x.kind = "other" THEN Quiet("not a job", 1)
  ELSE IF x.seen THEN Quiet("already seen", 1)
  ELSE IF x.sig = "good" THEN
    [outcome |-> "verified", marked |-> 0, records |-> 0,
     lines |-> 1, copied |-> Named(gate, x), passes |-> 3]
  ELSE
    [outcome |-> "refused", marked |-> 1, records |-> 1,
     lines |-> 2, copied |-> Named(gate, x) + Reasoned(gate, x),
     passes |-> 1 + SigPasses(x)]

Undecided ==
  [outcome |-> "none", marked |-> 0, records |-> 0, lines |-> 0,
   copied |-> 0, passes |-> 0]

VARIABLES a, box, g, decided, d, decoded, ran

vars == <<a, box, g, decided, d, decoded, ran>>

InitWith(gate) ==
  /\ a \in Arrivals
  /\ box \in Boxes
  /\ g = gate
  /\ decided = FALSE
  /\ d = Undecided
  /\ decoded = 0
  /\ ran = FALSE

Init == InitWith("bounded")
InitAsItWas == InitWith("as it was")

Decide ==
  /\ ~decided
  /\ decided' = TRUE
  /\ d' = Decision(g, box, a)
  /\ decoded' = Decoded(g, a)
  /\ UNCHANGED <<a, box, g, ran>>

\* Behind a verified signature the job may run.
Admit ==
  /\ decided
  /\ d.outcome = "verified"
  /\ ~ran
  /\ ran' = TRUE
  /\ UNCHANGED <<a, box, g, decided, d, decoded>>

Next ==
  \/ Decide
  \/ Admit
  \/ /\ decided
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars
SpecAsItWas == InitAsItWas /\ [][Next]_vars

\* P14. Nothing runs but a job whose signature verified, on an
\* armed box, under the cap and not seen before. A message that
\* does not verify adds at most 1 record and 2 lines, and one
\* refused at the signature is marked and leaves exactly 1
\* record.
P14Inv ==
  /\ ran =>
       /\ decided
       /\ d.outcome = "verified"
       /\ a.sig = "good"
       /\ a.kind = "job"
       /\ ~a.over
       /\ ~a.seen
       /\ box = "armed"
  /\ (decided /\ d.outcome # "verified") =>
       /\ d.records <= 1
       /\ d.lines <= 2
  /\ (decided /\ d.outcome = "refused") =>
       /\ d.marked = 1
       /\ d.records = 1

\* Clause 3 with the log counted: the stranger's characters in
\* the log's lines do not grow with the message. Finding F12.
LogBounded == decided => d.copied <= Bound

\* Clause 4 at the panic step: the decoder is handed a subject
\* of bounded length. Finding F13.
DecoderBounded == decoded <= PanicMax

\* Clause 4 at the rest: at most 3 passes over the message, and
\* 1 pass when the gate decides in front of the signature.
WorkBounded ==
  /\ d.passes <= 3
  /\ (decided /\ d.outcome \notin {"verified", "refused"}) =>
       d.passes = 1

\* The panic word is read first: whatever the size, the
\* signature and the box, a panic subject is a panic.
PanicFirst == (decided /\ a.kind = "panic") => d.outcome = "panic"

\* A stopped box leaves everything else as it is: no mark, no
\* line.
StoppedLeaves ==
  (decided /\ box = "stopped" /\ a.kind # "panic") =>
    /\ d.outcome = "left"
    /\ d.marked = 0
    /\ d.lines = 0

\* The size cap stands in front of the signature: a job over
\* the cap costs 1 pass, and none of its texts is copied.
CapBeforeTheSignature ==
  (decided /\ d.outcome = "too large") =>
    /\ d.passes = 1
    /\ d.copied = 0

\* Witness probes. All 3 are expected to FAIL; their
\* counterexamples are the evidence that the gate refuses, that
\* it admits, and that the bound is at work.
NothingIsRefused == ~(decided /\ d.outcome = "refused")
NothingRuns == ~ran
NothingIsCut ==
  ~(decided /\ d.outcome = "refused"
    /\ d.copied < Named("as it was", a) + Reasoned("as it was", a))

=============================================================================
