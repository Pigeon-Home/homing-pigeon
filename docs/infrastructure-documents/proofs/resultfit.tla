---------------------------- MODULE ResultFit ----------------------------
\* P11 of v4-properties.md: a result body leaves within
\* max_result_bytes, down to the fitting's floor. The fitting
\* sits in _fit_result_body in runner/runner.py, called on
\* the mail path before signing: the body is built, and
\* while it measures over the cap the streams are cut to
\* head and tail and the body rebuilt, 3 passes at most, the
\* third keeping the first and last 2 KiB of each stream.
\* The result carries a result_truncated member whenever a
\* cut happened. A cap of 0 is unlimited: the body leaves as
\* built, unmarked.
\*
\* This is one decision, in the shape of secretfloor.tla.
\* The body's size stands in 1 of 3 classes against the cap:
\* "fits" (within the cap as built), "shrinkable" (over as
\* built, within it once the streams are cut), and "fixed"
\* (over even with the streams at the third pass shape: the
\* fixed envelope around them is itself over the cap). sent
\* is "asis", "shrunk", or "over". The third class leaves
\* over the cap, marked, because the fitting has nothing
\* left to cut: that is the boundary supposition U2 of
\* v4-working.md states. It is the floor P11's words name,
\* and P11Floor is their statement here. The witness
\* configuration resultfitwitnesscap.cfg states the cap with
\* no floor, so the checker yields the class the floor is
\* for.
\*
\* This file was run with TLC on 2026-11-18, and the checker
\* found the count the search had predicted. The model it
\* states is searched by runner/tests/test_v4_models.py; the
\* state counts in v4-search-2.md are that search's, and the
\* checker's verdicts are in v4-working.md.

EXTENDS Integers

Caps == {"zero", "set"}
Bodies == {"fits", "shrinkable", "fixed"}

VARIABLES cap, body, decided, sent, marked

vars == <<cap, body, decided, sent, marked>>

Init ==
  /\ cap \in Caps
  /\ body \in Bodies
  /\ decided = FALSE
  /\ sent = "none"
  /\ marked = FALSE

Decide ==
  /\ ~decided
  /\ decided' = TRUE
  /\ IF cap = "zero" \/ body = "fits"
       THEN sent' = "asis" /\ marked' = FALSE
       ELSE IF body = "shrinkable"
              THEN sent' = "shrunk" /\ marked' = TRUE
              ELSE sent' = "over" /\ marked' = TRUE
  /\ UNCHANGED <<cap, body>>

Next ==
  \/ Decide
  \/ /\ decided
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars

\* A cut is always marked, and an untouched body never is.
MarkedWhenCut ==
  decided =>
    /\ (sent \in {"shrunk", "over"} => marked)
    /\ (sent = "asis" => ~marked)

\* A cap of 0 is unlimited: the body leaves as built.
CapZeroAsIs ==
  (decided /\ cap = "zero") => sent = "asis"

\* A body that fits as built is never cut.
FitsAsIs ==
  (decided /\ body = "fits") => sent = "asis"

\* P11 as it is worded, with its floor: under a set cap a
\* body leaves over the cap only at the "fixed" class, where
\* the streams stand at the last pass's shape and the fitting
\* has nothing left to cut, and it leaves marked.
P11Floor ==
  (decided /\ cap = "set") =>
    /\ (body /= "fixed" => sent /= "over")
    /\ (sent = "over" => marked)

\* The cap with no floor, stated on the witness
\* configuration. Expected to FAIL there: at the "fixed"
\* class the body leaves over the cap, marked. The
\* counterexample is the class P11's floor is for, finding
\* F7 of v4-search-2.md.
P11Inv ==
  (decided /\ cap = "set") => sent /= "over"

\* Witness probe. Expected to FAIL; its counterexample is
\* the evidence that the fitting does cut.
NothingIsShrunk == ~(decided /\ sent = "shrunk")

=============================================================================
