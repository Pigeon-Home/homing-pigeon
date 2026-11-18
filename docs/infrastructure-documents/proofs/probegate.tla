----------------------------- MODULE ProbeGate -----------------------------
\* P10 of v4-properties.md: on macOS, confinement at enforce
\* means the startup probe passed, or there is no run. The gate
\* is confinement_startup_problem in runner/ops/remediation_ops.py,
\* asked by the startup in runner/ops/main.py, which refuses the
\* start with exit 2 when the gate names a problem.
\*
\* The same function is the gate on the 3 platforms that have a
\* confinement backend of their own, darwin, freebsd and win32,
\* and it treats them alike. So the model states P10 for all 3:
\* the darwin rows are P10 as written, and the freebsd and win32
\* rows are the same claim, which the code makes and the index
\* does not yet state.
\*
\* This is one decision, not a trace of jobs, in the shape of
\* decision.tla. A start is a mode, a platform, what stands in
\* the backend's place, and what the backend's probe answers:
\*
\*   backend "none"     the backend module cannot be loaded
\*           "stub"     it loads and says it is not this
\*                      platform's backend
\*           "noprobe"  it is the backend and has no probe
\*           "real"     it is the backend, with its probe
\*
\* On any other platform this gate has no say: the bwrap gate in
\* runner/ops/main.py decides there, outside this model.
\*
\* This file has not been run with TLC. The model it states is
\* searched by runner/tests/test_v4_models.py; the state counts
\* in v4-search.md are that search's, written as the prediction
\* for the checker.

EXTENDS Integers

Modes == {"enforce", "audit", "off"}
Platforms == {"darwin", "freebsd", "win32", "other"}
Backends == {"none", "stub", "noprobe", "real"}
Probes == {"passes", "problem", "raises"}

Starts == [mode: Modes, platform: Platforms,
           backend: Backends, probe: Probes]

\* The platforms where this gate decides.
Gated(s) == s.mode = "enforce" /\ s.platform /= "other"

\* The start goes ahead unless the gate names a problem.
GoesAhead(s) ==
  \/ ~Gated(s)
  \/ s.backend = "real" /\ s.probe = "passes"

VARIABLES s, decided, started

vars == <<s, decided, started>>

Init ==
  /\ s \in Starts
  /\ decided = FALSE
  /\ started = FALSE

Decide ==
  /\ ~decided
  /\ decided' = TRUE
  /\ started' = GoesAhead(s)
  /\ UNCHANGED s

Next ==
  \/ Decide
  \/ /\ decided
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars

\* P10, for each of the 3 platforms. A start at enforce means
\* the platform's own backend stood there and its probe passed.
\* A probe that names a problem, a probe that raises, a backend
\* with no probe, a stub, and no backend at all each cost the
\* start: there is no weaker run.
P10Inv ==
  (decided /\ started /\ Gated(s)) =>
    /\ s.backend = "real"
    /\ s.probe = "passes"

\* The gate refuses nothing outside its own ground: a mode
\* below enforce is the owner's stated choice, and another
\* platform is another gate's.
RefusesOnlyItsOwn ==
  (decided /\ ~started) => Gated(s)

\* Witness probes. Both are expected to FAIL; their
\* counterexamples are the evidence that the gate decides both
\* ways.
NothingStartsAtEnforce == ~(decided /\ started /\ Gated(s))
NothingIsRefused == ~(decided /\ ~started)

=============================================================================
