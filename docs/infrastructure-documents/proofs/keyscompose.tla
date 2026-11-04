--------------------------- MODULE KeysCompose ---------------------------
\* Stage 6, item 2. The gate's policy step was one boolean,
\* policyOk: "this key's policy allowed this job". This model
\* opens that bit into a map of three keys. One of them is
\* pinned to one script shape. The others are an owner key,
\* which the policy does not restrict, and a third key, which
\* may run a ping or any script that is not the pinned one.
\*
\* otherOk stands for P1's clauses other than the policy step.
\* Execution requires both, which is how the gate and P4
\* compose: the policy step is one of the nine, and the other
\* eight are unchanged. The fences themselves are
\* KeyPolicy.tla. This model is only the composition.

EXTENDS Integers

Keys == {"owner", "pinned", "other"}
Shapes == {"pinnedScript", "otherScript", "ping"}

PolicyAllows(k, s) ==
  \/ k = "owner"
  \/ k = "pinned" /\ s = "pinnedScript"
  \/ k = "other" /\ s # "pinnedScript"

Attempts == [key: Keys, shape: Shapes, otherOk: BOOLEAN]

VARIABLES a, decided, executed

vars == <<a, decided, executed>>

Init ==
  /\ a \in Attempts
  /\ decided = FALSE
  /\ executed = FALSE

Next ==
  \/ /\ ~decided
     /\ executed' = (a.otherOk /\ PolicyAllows(a.key, a.shape))
     /\ decided' = TRUE
     /\ UNCHANGED a
  \/ /\ decided
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars

\* A script runs only when the rest of the gate passed and
\* this key's policy allows this shape. A pinned key runs
\* only its one script.
KeysInv ==
  decided =>
    /\ executed => (a.otherOk /\ PolicyAllows(a.key, a.shape))
    /\ (a.key = "pinned" /\ executed) => (a.shape = "pinnedScript")

\* Expected to fail: a good job does run.
NothingExecutes == ~executed \/ ~decided

\* Expected to fail: the pinned key's own script runs when
\* the rest of the gate passed.
PinnedNever ==
  ~(decided /\ a.key = "pinned" /\ a.shape = "pinnedScript"
    /\ a.otherOk /\ executed)

=============================================================================
