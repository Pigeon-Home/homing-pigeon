----------------------------- MODULE Confine -----------------------------
\* Property P2 (properties.md): no field in a job or a result can
\* widen or disable the confinement the owner configured.
\*
\* The gate (Gate.tla) decides whether a job runs. This model
\* starts where the gate ends: a job that passed the gate is about
\* to execute, and the question is what shapes that execution and
\* what leaves the box about it. Every input the runner reads for
\* those decisions is enumerated below, on both sides:
\*
\*   - the owner's side (c): the result-view ceiling, the query
\*     budget cap, the confinement mode, whether the sandbox
\*     mechanism works on this machine, and the runner-computed
\*     confinement outcome of the run (the snapshot's verdict,
\*     which the runner computes and no message supplies);
\*   - the job's side (j): every field the execution and result
\*     paths read that could be shaped like a widening attempt --
\*     the requested view, the requested query budget, the declared
\*     queries, a redaction-pattern list, the interpreter choice,
\*     and the presence of confinement-shaped fields the code
\*     never reads at all (fakePresent).
\*
\* The claim the checker searches is the invariant P2Inv: stated
\* in closed form over the outcome, it says the effective view
\* never exceeds the owner's ceiling, the effective budget never
\* exceeds either side's number, the writable set is a function
\* of the owner's mode and the machine alone, the redaction
\* patterns are the owner's, and no answer a query receives is
\* wider than the effective view and the runner's own values
\* allow. Two further invariants (EffViewExact, EffBudgetExact)
\* pin the computation itself to the code's rule -- the narrower
\* of the two views, the smaller of the two budgets -- so a model
\* that answered every job with the narrowest view would fail
\* them: narrowing must happen exactly when the job asks for it,
\* which is the witness discipline the witness configurations
\* exhibit from the other side.
\*
\* The one job influence on the sandbox's shape is stated, not
\* hidden: when the job's interpreter resolves outside /usr, the
\* runner binds that interpreter's own install prefix read-only,
\* so the interpreter can run at all (runner/guard/sandbox.py,
\* interpreter_binds). It is the runner's uniform rule, it is
\* read-only, it is exactly that interpreter's prefix and no path
\* the job names, and the bind is written into the audit record.
\* In the model it is visibleExtra = "interpPrefixRO". It never
\* touches the writable set, the view, or the budget.
\*
\* What the model leaves out, deliberately: the contents of the
\* output (answers are the shapes an answer can take, not text),
\* the snapshot's file walk (confinedState is its three-valued
\* outcome, an input the runner computes), and the attestation
\* list the result itself carries under the attested view, which
\* is built by the same answer function from the same
\* runner-computed values and is bounded by the view the ceiling
\* already fixed. stage4-p2.md records the code sites for each
\* of these and the exact scope of the claim.

EXTENDS Integers

Views == {"attested", "summary", "redacted", "full"}

Ord(v) ==
  CASE v = "attested" -> 0
    [] v = "summary"  -> 1
    [] v = "redacted" -> 2
    [] v = "full"     -> 3

Ops == {"attestC", "attestU", "grep", "tail"}

\* Declared query lists of length at most two. Longer lists spend
\* the same budget position by position; two positions already
\* exhibit an answered query, a budget-rejected query (the
\* effective budgets in this model are 0, 2, 3, and 8, and 0
\* rejects from the first position), and a raw-line answer.
QueryLists == UNION {[1..n -> Ops] : n \in {0, 1, 2}}

\* budgetAsk is -1 for an absent budget (a set mixing the string
\* "absent" with integers is one TLC cannot fingerprint); the
\* other values are budgets a job can ask for: under the default
\* cap, at it, and over it.
Jobs == [
  viewAsk:       Views \cup {"absent", "bogus"},
  budgetAsk:     {-1, 0, 3, 10},
  queries:       QueryLists,
  redactAsk:     BOOLEAN,
  interpOutside: BOOLEAN,
  fakePresent:   BOOLEAN
]

Configs == [
  ceiling:       Views,
  budgetCap:     {2, 8},
  mode:          {"off", "audit", "enforce"},
  sandboxWorks:  BOOLEAN,
  confinedState: {"unconfigured", "confined", "violated"}
]

VARIABLES j, c, o, done

vars == <<j, c, o, done>>

\* The code's defaults (runner/ops/policy.py, runner/runner.py
\* query_budget): an absent or unrecognised requested view reads
\* as "full"; an absent budget reads as 8 on either side.
ReqView == IF j.viewAsk \in Views THEN j.viewAsk ELSE "full"
AskBudget == IF j.budgetAsk = -1 THEN 8 ELSE j.budgetAsk

\* The code's two narrowing rules.
MinView == IF Ord(ReqView) <= Ord(c.ceiling) THEN ReqView ELSE c.ceiling
MinBudget == IF AskBudget <= c.budgetCap THEN AskBudget ELSE c.budgetCap

\* The sandbox decision (runner/runner.py, _confinement_argv):
\* enforce mode and a working mechanism. Audit runs unsandboxed
\* and records what enforce would have done; off never looks.
Sandboxed == (c.mode = "enforce") /\ c.sandboxWorks

\* The writable set. Inside the sandbox it is the job workdir
\* alone; outside it, execution is unsandboxed and the set is the
\* host's -- a function of the owner's mode and the machine,
\* in which no job field appears.
Writable == IF Sandboxed THEN "workOnly" ELSE "host"

\* The one job influence on the sandbox's visible set, bounded as
\* the code bounds it: the chosen interpreter's own prefix,
\* read-only, and only when the job is sandboxed at all.
VisibleExtra ==
  IF Sandboxed /\ j.interpOutside THEN "interpPrefixRO" ELSE "none"

\* The runner-computed confinement verdict an attestation reports
\* (runner/ops/attest.py, build_attestations). The query asks; the
\* value is the runner's.
ConfAnswer ==
  CASE c.confinedState = "confined"     -> "confTrue"
    [] c.confinedState = "violated"     -> "confFalse"
    [] c.confinedState = "unconfigured" -> "unconfigured"

RawAllowed(v) == v \in {"full", "redacted"}

\* One query's answer (runner/ops/queries.py, answer_queries):
\* every query spends one budget unit, answered or rejected, in
\* order; an attestation reports the runner's value or "unknown"
\* for a predicate the runner does not have; a raw-line query is
\* answered only when the effective view allows raw lines.
AnswerFor(op, pos) ==
  IF pos > MinBudget THEN "rejectedBudget"
  ELSE CASE op = "attestC" -> ConfAnswer
         [] op = "attestU" -> "unknownFalse"
         [] op \in {"grep", "tail"} ->
              IF RawAllowed(MinView) THEN "rawLines"
              ELSE "rejectedPolicy"

ExpectedAnswers ==
  [i \in DOMAIN j.queries |-> AnswerFor(j.queries[i], i)]

Init ==
  /\ j \in Jobs
  /\ c \in Configs
  /\ done = FALSE
  /\ o = "unset"

\* One decision step: the runner computes the outcome from the
\* two records and nothing else. The confinement-shaped fields a
\* job may carry (fakePresent) and its redaction list (redactAsk)
\* are read by no part of this step, because the code reads them
\* nowhere; the patterns an answer uses are the owner's.
Decide ==
  /\ ~done
  /\ done' = TRUE
  /\ o' = [ effView      |-> MinView,
            effBudget    |-> MinBudget,
            sandboxed    |-> Sandboxed,
            writable     |-> Writable,
            visibleExtra |-> VisibleExtra,
            patternsFrom |-> "owner",
            answers      |-> ExpectedAnswers ]
  /\ UNCHANGED <<j, c>>

Done ==
  /\ done
  /\ UNCHANGED vars

Next == Decide \/ Done

Spec == Init /\ [][Next]_vars

\* P2, the security claims, in closed form. Read with the two
\* Exact invariants below; these are the half that must hold for
\* every job, including every widening-shaped one.
P2Inv ==
  done =>
    /\ Ord(o.effView) <= Ord(c.ceiling)
    /\ o.effBudget <= c.budgetCap
    /\ o.effBudget <= AskBudget
    /\ o.patternsFrom = "owner"
    /\ o.sandboxed = Sandboxed
    /\ o.writable = Writable
    /\ o.visibleExtra \in {"none", "interpPrefixRO"}
    /\ (o.visibleExtra = "interpPrefixRO" =>
          Sandboxed /\ j.interpOutside)
    /\ o.answers = ExpectedAnswers

\* The computation's fidelity to the code's rules: the effective
\* view and budget are exactly the narrower and the smaller, not
\* merely bounded by them. A model that narrowed everything would
\* satisfy P2Inv and fail here.
EffViewExact == done => o.effView = MinView
EffBudgetExact == done => o.effBudget = MinBudget

\* Witness probes. Both are expected to FAIL; their
\* counterexamples are the evidence the discipline requires.
\* NothingNarrows says the job's asks never take effect -- its
\* counterexample is a handling where a narrower view or a
\* smaller budget the job asked for is the one that ran.
NothingNarrows ==
  done => (o.effView = c.ceiling /\ o.effBudget = c.budgetCap)

\* NoPrefixBind says the interpreter's prefix is never bound --
\* its counterexample is the one bounded, disclosed widening the
\* statement names: a sandboxed job whose interpreter lives
\* outside /usr.
NoPrefixBind ==
  done => o.visibleExtra = "none"

=============================================================================
