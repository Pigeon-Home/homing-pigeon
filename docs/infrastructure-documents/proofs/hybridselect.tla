--------------------------- MODULE HybridSelect ---------------------------
\* P8 of v4-properties.md: a v3 session that can agree the
\* hybrid group does so. The selection sits in the server
\* core's ClientHello handling in runner/wire/dtlsproto.py:
\* the hybrid group (4588, X25519MLKEM768, C29) is selected
\* when the server core carries the hybrid profile option
\* and the client offered a hybrid key share; otherwise the
\* X25519 share (29), when offered; a hello offering no
\* group the profile can select is refused. The profile option is the version 3 carriage
\* profile's (DtlsMailServer enables it); the version 1
\* profile leaves it off, and a hybrid share offered to it
\* is not selected, exactly as before.
\*
\* This is one decision, not a trace of handshakes, in the
\* shape of secretfloor.tla. offered is the set of groups
\* with a key share in the ClientHello. The client's own
\* fail-closed check (a hybrid selection it never offered
\* fails the handshake, _hybrid_shared in the same file) is
\* the same claim read from the other side: OnlyOffered.
\*
\* This file was run with TLC on 2026-11-18, and the checker
\* found the count the search had predicted. The model it
\* states is searched by runner/tests/test_v4_models.py; the
\* state counts in v4-search-2.md are that search's, and the
\* checker's verdicts are in v4-working.md.

EXTENDS Integers

Groups == {"hybrid", "x25519"}
Profiles == {"v1", "v3"}

VARIABLES offered, profile, decided, outcome

vars == <<offered, profile, decided, outcome>>

Init ==
  /\ offered \in SUBSET Groups
  /\ profile \in Profiles
  /\ decided = FALSE
  /\ outcome = "none"

Decide ==
  /\ ~decided
  /\ decided' = TRUE
  /\ outcome' = IF profile = "v3" /\ "hybrid" \in offered
                  THEN "hybrid"
                  ELSE IF "x25519" \in offered
                         THEN "x25519"
                         ELSE "refused"
  /\ UNCHANGED <<offered, profile>>

Next ==
  \/ Decide
  \/ /\ decided
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars

\* P8. In a v3 handshake that offered the hybrid share, the
\* agreed group is the hybrid group.
P8Inv ==
  (decided /\ profile = "v3" /\ "hybrid" \in offered)
    => outcome = "hybrid"

\* The agreed group is one the client offered, and a hello
\* is refused exactly when it offers no group the profile
\* can select: a hybrid share alone, offered to a v1
\* profile, is refused, not agreed.
OnlyOffered ==
  decided =>
    /\ (outcome = "hybrid" => "hybrid" \in offered)
    /\ (outcome = "x25519" => "x25519" \in offered)
    /\ (outcome = "refused" <=>
          ~("x25519" \in offered
            \/ (profile = "v3" /\ "hybrid" \in offered)))

\* Witness probes. Both are expected to FAIL; their
\* counterexamples are the evidence that the model decides
\* both ways.
NothingSelectsHybrid == ~(decided /\ outcome = "hybrid")
NothingIsRefused == ~(decided /\ outcome = "refused")

=============================================================================
