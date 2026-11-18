---------------------------- MODULE DiskGuard ----------------------------
\* P7 of v4-properties.md: the disk guard, guard_disk in
\* runner/oracle/resources.py, called from the poll cycle. One
\* pass of the guard, at the abstraction the property states:
\* the four material classes of C28 in their order (rolled log
\* backups, the live logs, the recorded results and retained
\* outputs, job workspaces past their age floor), each class
\* present or absent on the disk as it stands, and the disk
\* measured before every action and again at the door of every
\* class.
\*
\* A measurement comes out one of 3 ways: at or over the
\* threshold, under it, or not at all. The model lets every
\* measurement come out any of the 3, whatever the last one
\* said: a disk can fill up again between 2 measurements with
\* no action between them, and the pass then goes on to a
\* later class with an earlier one's material still standing.
\* A measurement that fails ends the pass: nothing is given up
\* without a measurement that says the disk is at or over the
\* threshold.
\*
\* File level multiplicity inside a class, the annotation's
\* 512 action cap, and the still-over cooldown are outside
\* this model; the claims checked are the order, the
\* threshold, the recording, and that the runner is never
\* stopped.

EXTENDS Integers, Sequences

VARIABLES reading, present, acted, at, phase, recorded, alive

vars == <<reading, present, acted, at, phase, recorded, alive>>

Classes == {1, 2, 3, 4}
Readings == {"over", "under", "failed"}

\* at is the class whose turn it is: 0 before the first
\* measurement is acted on, 5 past the last class. acted is a
\* sequence of classes in the order the pass acted on them.
Init ==
  /\ reading \in Readings
  /\ present \in SUBSET Classes
  /\ acted = <<>>
  /\ at = 0
  /\ phase = "run"
  /\ recorded = FALSE
  /\ alive = TRUE

\* The first measurement reads at or over the threshold: the
\* pass opens at the first class, and measures again there.
Open ==
  /\ phase = "run"
  /\ at = 0
  /\ reading = "over"
  /\ at' = 1
  /\ reading' \in Readings
  /\ UNCHANGED <<present, acted, phase, recorded, alive>>

\* One action of the pass: the class whose turn it is has
\* material and the disk measures at or over the threshold.
\* The pass acts on the class, and measures again at the door
\* of the next one.
Act ==
  /\ phase = "run"
  /\ at \in Classes
  /\ at \in present
  /\ reading = "over"
  /\ acted' = Append(acted, at)
  /\ at' = at + 1
  /\ reading' \in Readings
  /\ UNCHANGED <<present, phase, recorded, alive>>

\* The pass leaves a class as it stands: the class has no
\* material, or the disk measures under the threshold. It
\* measures again at the door of the next class.
Leave ==
  /\ phase = "run"
  /\ at \in Classes
  /\ reading /= "failed"
  /\ (at \notin present \/ reading = "under")
  /\ at' = at + 1
  /\ reading' \in Readings
  /\ UNCHANGED <<present, acted, phase, recorded, alive>>

\* The pass ends: the first measurement did not read at or
\* over the threshold, or a later measurement failed, or the
\* last class has had its turn. A pass that acted records its
\* disk_truncation event; a pass that acted on nothing records
\* none, as the code returns no event then. Ending the pass
\* never touches alive: no outcome of a pass stops the runner.
End ==
  /\ phase = "run"
  /\ \/ at = 0 /\ reading /= "over"
     \/ at \in Classes /\ reading = "failed"
     \/ at = 5
  /\ phase' = "done"
  /\ recorded' = (acted /= <<>>)
  /\ UNCHANGED <<reading, present, acted, at, alive>>

Next ==
  \/ Open
  \/ Act
  \/ Leave
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

\* Witness probes. All 3 are expected to FAIL; their
\* counterexamples are the evidence that the model moves.
\* NeverActs says no pass ever acts: its counterexample is a
\* disk over the threshold with material in a class, and 1
\* action on it.
NeverActs == acted = <<>>

\* NeverRecords says no pass ever records an event: its
\* counterexample is a pass that acted and ended.
NeverRecords == recorded = FALSE

\* NeverLeavesMaterial says a pass never acts on a class while
\* an earlier class with material was left as it stood: its
\* counterexample is a disk that read under at the earlier
\* class and over again at the later one.
NeverLeavesMaterial ==
  \A i \in DOMAIN acted : \A c \in present :
    c < acted[i] => \E j \in DOMAIN acted : acted[j] = c

=============================================================================
