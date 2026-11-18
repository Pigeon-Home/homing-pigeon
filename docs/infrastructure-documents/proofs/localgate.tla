----------------------------- MODULE LocalGate -----------------------------
\* P12 of v4-properties.md: a local envelope over the cap is
\* refused unread by the gate. The cap is
\* _LOCAL_ENVELOPE_MAX_BYTES in runner/runner.py, 262144 bytes,
\* and the gate has 2 doors there: the inbox scan,
\* _scan_local_inbox, and the loopback listener's read,
\* _handle_local_signal_conn. Behind both stands 1 ingest
\* check, _ingest_local_envelope_inner, and behind that the
\* verifier.
\*
\* This is one decision, not a trace of jobs, in the shape of
\* decision.tla. An arrival is its form, its size in bytes,
\* whether its bytes decode as UTF-8 when read whole, and where
\* a cut at 1 byte past the cap falls:
\*
\*   form "file"       a regular file in the inbox
\*        "symlink"    a symlink in the inbox; the size is
\*                     its target's
\*        "directory"  a directory in the inbox
\*        "stream"     bytes on the loopback listener
\*   cut  "clean"      the cut falls between 2 characters
\*        "splits"     the cut falls inside a character
\*
\* Nothing the gate does depends on the cut: each door looks at
\* the size of what it read before it decodes anything. The
\* cut is in the arrival so that the model says so, and so
\* that the conformance asks the real scan with a character
\* astride it.
\*
\* The model is small on purpose. The cap is 2 and a chunk is
\* 2, so the sizes 0 to 5 stand on both sides of every
\* comparison the 2 doors make: nothing, under the cap, the
\* cap, 1 over, a chunk over, and more than a chunk over. The
\* conformance in runner/tests/test_v4_models.py asks the real
\* doors at the real cap.
\*
\* The inbox scan reads a file once, to at most 1 byte past the
\* cap. The listener reads chunk by chunk and stops at the
\* first total over the cap, so it reads at most 1 chunk past
\* it. How a sender's bytes fall into chunks is the sender's,
\* and the model lets a stream's read be any total the loop can
\* stop on.
\*
\* What the model leaves out: an envelope that is only white
\* space, the local_signals switch, and everything from the
\* verifier on. A local envelope that reaches the verifier
\* faces the same gate the mail path faces, and that gate has
\* its own models.
\*
\* This file has not been run with TLC. The model it states is
\* searched by runner/tests/test_v4_models.py; the state counts
\* in v4-search.md are that search's, written as the prediction
\* for the checker.

EXTENDS Integers

Cap == 2
Chunk == 2

Forms == {"file", "symlink", "directory", "stream"}
Sizes == 0..(Cap + Chunk + 1)
Cuts == {"clean", "splits"}

Arrivals == [form: Forms, size: Sizes, decodes: BOOLEAN, cut: Cuts]

Min(x, y) == IF x < y THEN x ELSE y

\* What a door may read of an arrival.
Reads(a) ==
  IF a.form = "file" THEN {Min(a.size, Cap + 1)}
  ELSE IF a.form = "stream" /\ a.size > Cap
    THEN (Cap + 1)..Min(a.size, Cap + Chunk)
  ELSE IF a.form = "stream" THEN {a.size}
  ELSE {0}

\* The bytes read do not decode.
Garbled(a, r) == r > 0 /\ ~a.decodes

\* What the gate does with what it read. Each door looks at the
\* size of what it read before it decodes anything.
Outcome(a, r) ==
  IF a.form = "directory" THEN "left"
  ELSE IF a.form = "symlink" THEN "symlink"
  ELSE IF r > Cap THEN "too large"
  ELSE IF r = 0 THEN
    (IF a.form = "file" THEN "empty" ELSE "nothing")
  ELSE IF Garbled(a, r) THEN "not utf-8"
  ELSE "verify"

VARIABLES a, decided, outcome, read

vars == <<a, decided, outcome, read>>

Init ==
  /\ a \in Arrivals
  /\ decided = FALSE
  /\ outcome = "none"
  /\ read = 0

Decide ==
  /\ ~decided
  /\ \E r \in Reads(a) :
       /\ read' = r
       /\ outcome' = Outcome(a, r)
  /\ decided' = TRUE
  /\ UNCHANGED a

Next ==
  \/ Decide
  \/ /\ decided
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars

\* P12. What reaches the verifier is at most the cap, and it is
\* the whole envelope, never the head of a longer one.
P12Inv ==
  (decided /\ outcome = "verify") =>
    /\ a.size <= Cap
    /\ read = a.size

\* A symlink is refused unread: nothing of its target is read.
SymlinkUnread == a.form = "symlink" => read = 0

\* The scan reads at most 1 byte past the cap, the listener at
\* most 1 chunk past it, and nothing else is read at all.
ReadBounded ==
  /\ a.form = "file" => read <= Cap + 1
  /\ a.form = "stream" => read <= Cap + Chunk
  /\ a.form \in {"symlink", "directory"} => read = 0

\* An envelope over the cap is refused for its size, whatever
\* its bytes are and wherever the scan's cut falls.
OverCapRefusedForSize ==
  (decided /\ a.size > Cap /\ a.form \in {"file", "stream"}) =>
    outcome = "too large"

\* Witness probes. Both are expected to FAIL; their
\* counterexamples are the evidence that the gate decides both
\* ways.
NothingReachesTheVerifier == ~(decided /\ outcome = "verify")
NothingIsRefusedForSize == ~(decided /\ outcome = "too large")

=============================================================================
