------------------------------ MODULE Claim -----------------------------
\* Step 15 of properties.md, the claim, which is the one step two
\* handlers can race. Both have already passed steps 0 through 14
\* for the same fresh job id; that order is Gate.tla. Under the
\* mail lock one of them takes the slot and executes. The other
\* finds the slot held and does not. C15, at the P1(49) rung.

EXTENDS Integers

VARIABLES slot, pc, ran

vars == <<slot, pc, ran>>

Proc == {1, 2}

Init ==
  /\ slot = "free"
  /\ pc = [p \in Proc |-> "claim"]
  /\ ran = [p \in Proc |-> FALSE]

\* A handler at the claim step. A free slot is taken and that
\* handler executes. A held slot is "another worker claimed it
\* first": that handler finishes without executing.
Take(p) ==
  /\ pc[p] = "claim"
  /\ IF slot = "free"
     THEN /\ slot' = "held"
          /\ ran' = [ran EXCEPT ![p] = TRUE]
          /\ pc' = [pc EXCEPT ![p] = "done"]
     ELSE /\ pc' = [pc EXCEPT ![p] = "done"]
          /\ UNCHANGED <<slot, ran>>

Next ==
  \/ \E p \in Proc : Take(p)
  \/ /\ \A p \in Proc : pc[p] = "done"
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars

\* At most one of the two handlers executes.
AtMostOnce ==
  ~(ran[1] /\ ran[2])

=============================================================================
