---------------------------- MODULE DiskGuard ----------------------------
\* P7 of v4-properties.md: the disk guard, guard_disk in
\* runner/oracle/resources.py, called from the poll cycle. One
\* pass of the guard, at the abstraction the property states:
\* the four material classes of C28 in their order (rolled log
\* backups, the live logs, the recorded results and retained
\* outputs, job workspaces past their age floor), each class
\* present or absent on the disk as it stands, and the disk
\* re-measured after every action, which the model states as a
\* nondeterministic over flag after each action. File level
\* multiplicity inside a class, the annotation's 512 action
\* cap, and the still-over cooldown are outside this model;
\* the claims checked are the order, the threshold, the
\* recording, and that the runner is never stopped.

EXTENDS Integers, Sequences

VARIABLES over, present, acted, phase, recorded, alive

vars == <<over, present, acted, phase, recorded, alive>>

Classes == {1, 2, 3, 4}

\* The smallest class with material that has not been acted on
\* yet, or 0 when there is none. acted is a sequence of classes
\* in the order the pass acted on them.
NextClass ==
  LET done == {acted[i] : i \in DOMAIN acted}
  IN  IF \E c \in present : c \notin done
        THEN CHOOSE c \in present : c \notin done
               /\ \A d \in present : d \notin done => c <= d
        ELSE 0

Init ==
  /\ over \in {TRUE, FALSE}
  /\ present \in SUBSET Classes
  /\ acted = <<>>
  /\ phase = "run"
  /\ recorded = FALSE
  /\ alive = TRUE

\* One action of the pass: the disk measures at or over the
\* threshold, and the pass acts on the next class in the
\* order. After the action the disk is re-measured; the model
\* lets the re-measurement come out either way.
Act ==
  /\ phase = "run"
  /\ over = TRUE
  /\ NextClass /= 0
  /\ acted' = Append(acted, NextClass)
  /\ over' \in {TRUE, FALSE}
  /\ UNCHANGED <<present, phase, recorded, alive>>

\* The pass ends: the disk is under the threshold, or every
\* class with material has been acted on. A pass that acted
\* records its disk_truncation event; a pass that acted on
\* nothing records none, as the code returns no event then.
\* Ending the pass never touches alive: no outcome of a pass
\* stops the runner.
End ==
  /\ phase = "run"
  /\ (~over \/ NextClass = 0)
  /\ phase' = "done"
  /\ recorded' = (acted /= <<>>)
  /\ UNCHANGED <<over, present, acted, alive>>

Next ==
  \/ Act
  \/ End
  \/ /\ phase = "done"
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars

\* The runner is never stopped by a pass.
NeverStops == alive = TRUE

\* Actions happen in the classes' stated order, each at most
\* once, and only on a class that has material.
OrderRespected ==
  /\ \A i \in DOMAIN acted : acted[i] \in present
  /\ \A i, j \in DOMAIN acted : i < j => acted[i] < acted[j]

\* A finished pass that acted has its event recorded, and no
\* event is ever recorded for a pass that did not act.
RecordedFaithfully ==
  /\ (phase = "done" /\ acted /= <<>>) => recorded = TRUE
  /\ recorded = TRUE => acted /= <<>>

\* Witness probes. Both are expected to FAIL; their
\* counterexamples are the evidence that the model moves.
\* NeverActs says no pass ever acts: its counterexample is a
\* disk over the threshold with material in a class, and 1
\* action on it.
NeverActs == acted = <<>>

\* NeverRecords says no pass ever records an event: its
\* counterexample is a pass that acted and ended.
NeverRecords == recorded = FALSE

=============================================================================
