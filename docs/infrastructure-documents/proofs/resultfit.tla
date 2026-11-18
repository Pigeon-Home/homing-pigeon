---------------------------- MODULE ResultFit ----------------------------
\* P11 of v4-properties.md: a result body never leaves over
\* max_result_bytes. The fitting sits in _fit_result_body in
\* runner/runner.py, called on the mail path before signing:
\* the body is built, and while it measures over the cap the
\* streams are cut to head and tail and the body rebuilt, 3
\* passes at most, the third keeping the first and last
\* 2 KiB of each stream. The result carries a
\* result_truncated member whenever a cut happened. A cap
\* of 0 is unlimited: the body leaves as built, unmarked.
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
\* v4-working.md states, and the witness configuration
\* resultfitwitnesscap.cfg states P11's own words so the
\* checker yields that counterexample.
\*
\* Not yet run with TLC. The model it states is searched by
\* runner/tests/test_v4_models.py; the state counts in
\* v4-search-2.md are that search's, written as the
\* prediction for the checker.

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

\* P11's own words, stated on the witness configuration.
\* Expected to FAIL there: at the "fixed" class the body
\* leaves over the cap, marked. The counterexample is the
\* boundary finding of v4-search-2.md.
P11Inv ==
  (decided /\ cap = "set") => sent /= "over"

\* Witness probe. Expected to FAIL; its counterexample is
\* the evidence that the fitting does cut.
NothingIsShrunk == ~(decided /\ sent = "shrunk")

=============================================================================
