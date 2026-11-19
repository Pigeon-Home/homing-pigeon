---------------------------- MODULE SecretFloor ----------------------------
\* P13 of v4-properties.md: the runner does not start on a
\* secret under the entropy floor. The floor is applied where
\* the key map is built, build_secrets in runner/wire/verify.py,
\* to the default key and to every additional key alike, and a
\* secret under it raises a config error, which costs the start
\* (P6 clause 4, the refuse class).
\*
\* This is one decision, not a trace of jobs, in the shape of
\* decision.tla. The key map has a default key and 2 additional
\* keys; each is absent, strong (at or over the floor), or weak
\* (under it). 2 additional keys are enough to tell "an
\* additional key" from "every additional key". The estimate
\* itself, _estimate_secret_entropy, is outside this model: a
\* secret arrives here already judged.
\*
\* named is the key the refusal names. P6 clause 4 asks that
\* the error name the setting, so the model lets the refusal
\* name any key that is a cause of it, and no other.
\*
\* This file was run with TLC on 2026-11-18, and the checker
\* found the count the search had predicted. The model it
\* states is searched by runner/tests/test_v4_models.py; the
\* state counts in v4-search.md are that search's, and the
\* checker's verdicts are in v4-working.md.

EXTENDS Integers

Keys == {"default", "extra1", "extra2"}
Standing == {"absent", "strong", "weak"}

VARIABLES map, decided, started, named

vars == <<map, decided, started, named>>

\* The keys that, each alone, cost the start: a weak key, or a
\* default key that is not there.
Causes(m) ==
  {k \in Keys : m[k] = "weak"}
    \cup (IF m["default"] = "absent" THEN {"default"} ELSE {})

Init ==
  /\ map \in [Keys -> Standing]
  /\ decided = FALSE
  /\ started = FALSE
  /\ named = "none"

\* The start: it happens when nothing costs it, and a start
\* that is refused names one of its causes.
Decide ==
  /\ ~decided
  /\ decided' = TRUE
  /\ IF Causes(map) = {}
       THEN started' = TRUE /\ named' = "none"
       ELSE started' = FALSE /\ named' \in Causes(map)
  /\ UNCHANGED map

Next ==
  \/ Decide
  \/ /\ decided
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars

\* P13. A runner that started holds no weak key, and holds its
\* default key. The floor is every key's, not the default's
\* alone.
P13Inv ==
  (decided /\ started) =>
    /\ map["default"] = "strong"
    /\ \A k \in Keys : map[k] /= "weak"

\* P6 clause 4, for this refusal: a start that is refused names
\* a key that cost it.
NamesACause ==
  (decided /\ ~started) => named \in Causes(map)

\* Witness probes. Both are expected to FAIL; their
\* counterexamples are the evidence that the model decides both
\* ways.
NothingStarts == ~(decided /\ started)
NothingIsRefused == ~(decided /\ ~started)

=============================================================================
