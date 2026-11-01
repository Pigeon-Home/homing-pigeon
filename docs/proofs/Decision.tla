---------------------------- MODULE Decision ---------------------------
\* Property P6 (properties.md): a present-but-unusable setting
\* behaves as Decision 1 requires. The refuse class stops the
\* runner at startup and names the setting. The default class
\* reads as its documented default and is named. A refuse-class
\* write while the process is running does not change the
\* binding and does not stop the process.
\*
\* This is one decision, not a trace of jobs. An attempt is a
\* setting of one class, present or not, usable or not, read
\* either at startup or by the live reload. The readers are
\* runner/guard/confval.py and runner/guard/defaulted.py for
\* the default class, the startup checks in runner/ops/main.py
\* for the refuse class, and runner/ops/attest.py
\* reload_hot_config for a write while running. Stage 4's
\* record (stage4-p6.md) names the lines.
\*
\* "named" means the startup warning or the config error
\* contains the key. A refuse-class key written while running
\* is not in the reload set, so the model does not mark it
\* named: the code keeps the prior binding and emits no line
\* for that key. The decision's sentence also asks for a log
\* line. That gap is finding F1 in stage4-p6.md, not a bit
\* this model pretends is set.

EXTENDS Integers

Klass == {"refuse", "default"}
Presence == {"absent", "usable", "unusable"}
Moment == {"startup", "reload"}

Attempts == [
  klass: Klass,
  presence: Presence,
  moment: Moment
]

\* running: the process comes up, or stays up.
\* value: what a reader that continues will use.
\*   "written"     the value in the file
\*   "documented"  the documented default
\*   "prior"       the binding the process already holds
\*   "none"        no value, because the process did not start
\* named: the key is in the warning or the error.
\* kept: the running binding was left as it was.
Outcome(a) ==
  IF a.moment = "startup"
  THEN IF a.presence = "unusable" /\ a.klass = "refuse"
       THEN [running |-> FALSE, value |-> "none",
             named |-> TRUE, kept |-> FALSE]
       ELSE IF a.presence = "unusable"
       THEN [running |-> TRUE, value |-> "documented",
             named |-> TRUE, kept |-> FALSE]
       ELSE IF a.presence = "absent"
       THEN [running |-> TRUE, value |-> "documented",
             named |-> FALSE, kept |-> FALSE]
       ELSE [running |-> TRUE, value |-> "written",
             named |-> FALSE, kept |-> FALSE]
  ELSE IF a.presence = "usable"
  THEN [running |-> TRUE, value |-> "written",
        named |-> FALSE, kept |-> FALSE]
  ELSE IF a.presence = "absent" \/ a.klass = "refuse"
  THEN [running |-> TRUE, value |-> "prior",
        named |-> FALSE, kept |-> TRUE]
  ELSE [running |-> TRUE, value |-> "documented",
        named |-> TRUE, kept |-> FALSE]

VARIABLES a, decided, o

vars == <<a, decided, o>>

Init ==
  /\ a \in Attempts
  /\ decided = FALSE
  /\ o = [running |-> FALSE, value |-> "none",
          named |-> FALSE, kept |-> FALSE]

Next ==
  \/ /\ ~decided
     /\ o' = Outcome(a)
     /\ decided' = TRUE
     /\ UNCHANGED a
  \/ /\ decided
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars

\* P6. The process stops only for a refuse-class value that
\* is present and unusable at startup, and that stop names
\* the setting. A reload never stops it. An unusable
\* default-class value, at either moment, is the documented
\* default and is named. An unusable refuse-class value
\* written while running leaves the prior binding in place.
P6Inv ==
  \/ ~decided
  \/ /\ (o.running = FALSE) <=>
          /\ a.moment = "startup"
          /\ a.klass = "refuse"
          /\ a.presence = "unusable"
     /\ o.running = FALSE => o.named /\ o.value = "none"
     /\ a.moment = "reload" => o.running
     /\ (a.klass = "default" /\ a.presence = "unusable") =>
          /\ o.running
          /\ o.value = "documented"
          /\ o.named
          /\ ~o.kept
     /\ (a.moment = "reload" /\ a.klass = "refuse"
          /\ a.presence # "usable") =>
          /\ o.value = "prior"
          /\ o.kept
          /\ o.running

\* Witness probes. Both are expected to FAIL.
NothingStops ==
  o.running \/ ~decided

DefaultStaysUnusable ==
  ~(decided /\ a.klass = "default" /\ a.presence = "unusable"
    /\ o.value = "documented" /\ o.named)

=============================================================================
