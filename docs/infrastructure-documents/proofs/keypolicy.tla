---------------------------- MODULE KeyPolicy ----------------------------
\* Property P4 (properties.md): a named key can do only what its
\* key policy allows. Above all the upgrade key: its policy pins
\* one exact staging script by SHA-384 and admits execution
\* only, so a job signed with that key runs that one script and
\* nothing else -- a clock job signed with it is refused.
\*
\* The gate (Gate.tla) decides whether a job runs; this model
\* isolates the one step of that gate that speaks for the key:
\* check_key_policy (runner/wire/verify.py, called from
\* runner/ops/mail.py, handle_mail, after signature verification
\* and freshness). The signature has already verified when this
\* step runs, and the key_id it receives is the key whose secret
\* verified -- key selection refuses an unknown id before any
\* MAC is computed (verify_body_keyed), so an attempt in this
\* model is a job genuinely signed under the key it names. A
\* holder of one key's secret cannot present under another key,
\* and cannot escape a policy by naming no key: the unnamed form
\* selects the default secret, whose signature the holder cannot
\* produce. Execution past this step is P1's claim composed with
\* this one; acceptance here is the policy's verdict, nothing
\* more.
\*
\* Inside the code step, the order is fixed and the model keeps
\* it: the key directory's verdict speaks first (a configured
\* directory that refuses the key refuses it whatever its policy
\* says -- a deployment gate in front of the policy, as P3's
\* gates stand in front of the signature; it is constant across
\* this model's space and is recorded in stage4-p4.md, not
\* modelled as a variable). Then the entry question: a key with
\* no policy entry is unrestricted unless the deployment sets
\* key_policies_default_deny, and the default (owner) key is
\* exempt from that flag under every name it answers to. Then
\* the fences, in the code's order: kinds, recipes, interpreters,
\* timeout, and last the script pinning -- the pinning branch
\* runs for execution jobs only, refuses a script_url outright
\* (its content cannot be checked before download), refuses a
\* missing or non-string script, and admits only a script whose
\* SHA-384 digest is in the policy's list.
\*
\* The attempt record (a) carries the key, the job's shape, and
\* the three per-field outcomes the remaining fences read:
\*
\*   - key: "default" (the owner's key), "upgrade" (the pinned
\*     key of the recorded arrangement), or "other" (any other
\*     additional key; the policy machinery is one code path for
\*     every additional key, and the model keeps a second
\*     restricted name so the claim is not stated about one
\*     string).
\*   - shape: the job reduced to what the pinning branch and
\*     the kinds fence branch on. execPinned is an execution job
\*     carrying an inline script whose SHA-384 is the pinned
\*     value; execOther, an inline script with any other digest;
\*     execUrl, an execution job carrying a script_url (alone or
\*     beside an inline script -- the code refuses both under a
\*     pinning policy); execNoScript, an execution job with no
\*     usable inline script; ping and sensor, kinds with no
\*     script; recipe, the kind whose interpreter is the owner's
\*     and which the recipes fence governs; other, any remaining
\*     kind.
\*   - interpOK, timeoutOK, recipeOK: whether the job's
\*     effective interpreter is in the policy's list, whether
\*     its effective timeout is within the policy's cap, and
\*     whether its recipe is listed. Each is read only on the
\*     branch the code reads it on, as an unread field is in the
\*     earlier models.
\*
\* The deployment record (d) carries the policy as the code
\* builds it: for each fence, whether the entry carries it
\* ("present") or not ("absent") -- an absent fence constrains
\* nothing, because build_key_policies carries only the fields
\* the owner wrote -- plus entry itself (whether the deployment
\* has a policy entry for its additional keys at all) and
\* denyExtra (key_policies_default_deny). The upgrade
\* arrangement of docs/use/sending.md is one point of this
\* space: entry, kinds, and pin present, a timeout cap of 300
\* seconds present -- and its allowed_files fence, which the
\* code applies through the mode-gated findings behind this
\* step (policy_files), is not one of this model's fences;
\* stage4-p4.md records that boundary rather than modelling it
\* away.
\*
\* The policy is a property of the key, not of the name it was
\* presented under: the code resolves the entry under any of the
\* key's names and refuses a configuration that enters one key
\* twice, so the model has no name variable. The default key is
\* modelled as never bound by the deployment's entry: that is
\* the code for entries written for other keys, and it is also
\* the code under the deny flag. An entry the owner writes for
\* the default key itself (under the empty id) is a real
\* configuration the code honours; it is outside this model's
\* space, and stage4-p4.md says so.

Keys == {"default", "upgrade", "other"}

Shapes == {"execPinned", "execOther", "execUrl", "execNoScript",
           "ping", "sensor", "recipe", "other"}

Present == {"present", "absent"}

Attempts == [
  key:       Keys,
  shape:     Shapes,
  interpOK:  BOOLEAN,
  timeoutOK: BOOLEAN,
  recipeOK:  BOOLEAN
]

Deployments == [
  entry:      Present,
  pin:        Present,
  kinds:      Present,
  interps:    Present,
  timeoutCap: Present,
  recipes:    Present,
  denyExtra:  BOOLEAN
]

VARIABLES a, d, o, done

vars == <<a, d, o, done>>

\* Whether a policy entry governs this attempt's key. The
\* default key is never governed by an entry written for the
\* deployment's additional keys, and is exempt from the deny
\* flag; an additional key is governed exactly when the
\* deployment carries an entry for it.
PolicyPresent == (a.key # "default") /\ (d.entry = "present")

\* The job's kind, as the fences read it: the four execution
\* shapes are one kind to the code.
KindOf ==
  CASE a.shape \in {"execPinned", "execOther", "execUrl",
                    "execNoScript"} -> "exec"
    [] a.shape = "ping"   -> "ping"
    [] a.shape = "sensor" -> "sensor_alert"
    [] a.shape = "recipe" -> "recipe"
    [] OTHER              -> "other"

\* The fences, in the code's order. Each is the code's branch
\* stated as a permission: an absent fence permits, because the
\* built policy carries only the fields the owner wrote.
KindsOK ==
  (d.kinds = "absent") \/ (KindOf = "exec")

RecipesOK ==
  (d.recipes = "absent") \/ (KindOf # "recipe") \/ a.recipeOK

\* A recipe's interpreter is the owner's; the interpreter fence
\* does not read recipe jobs.
InterpsOK ==
  (d.interps = "absent") \/ (KindOf = "recipe") \/ a.interpOK

TimeoutOK ==
  (d.timeoutCap = "absent") \/ a.timeoutOK

\* The pinning branch: it runs for execution jobs only. Under a
\* pinning policy an execution job is permitted only in its one
\* pinned shape -- a script_url, any other digest, or no usable
\* inline script is refused. Non-execution kinds carry no
\* script and are governed by the kinds fence alone.
PinOK ==
  (d.pin = "absent") \/ (KindOf # "exec") \/ (a.shape = "execPinned")

\* The step's verdict. A key with no governing entry is
\* permitted unless the deny flag is set and the key is not the
\* owner's; a governed key must pass every fence its entry
\* carries.
PolicyAllows ==
  IF ~PolicyPresent
  THEN (a.key = "default") \/ ~d.denyExtra
  ELSE KindsOK /\ RecipesOK /\ InterpsOK /\ TimeoutOK /\ PinOK

\* The recorded upgrade arrangement, as a point of the space:
\* an entry carrying kinds, the pin, and the timeout cap of
\* docs/use/sending.md (300 seconds) -- and its files fence,
\* which the code applies through the mode-gated findings
\* behind this step, is not one of this model's fences;
\* stage4-p4.md records that boundary rather than modelling it
\* away.
PinnedProfile ==
  /\ d.entry = "present"
  /\ d.kinds = "present"
  /\ d.pin = "present"
  /\ d.timeoutCap = "present"

Init ==
  /\ a \in Attempts
  /\ d \in Deployments
  /\ done = FALSE
  /\ o = "unset"

\* One decision step: check_key_policy computes its verdict
\* from the attempt and the deployment and nothing else.
Decide ==
  /\ ~done
  /\ done' = TRUE
  /\ o' = [ accepted      |-> PolicyAllows,
            policyApplied |-> PolicyPresent ]
  /\ UNCHANGED <<a, d>>

Done ==
  /\ done
  /\ UNCHANGED vars

Next == Decide \/ Done

Spec == Init /\ [][Next]_vars

\* P4, the security claim, in closed form: a job this step
\* accepts under a governing policy passed every fence that
\* policy carries. (Stated with disjunctions: nested
\* implications do not parse.)
P4Inv ==
  done =>
    (~o.accepted
     \/ ~PolicyPresent
     \/ (KindsOK /\ RecipesOK /\ InterpsOK /\ TimeoutOK /\ PinOK))

\* The pinning core of P4, isolated: under a pinning policy, an
\* accepted execution job is the pinned shape -- no other
\* digest, no script_url, no missing script.
PinBinds ==
  done =>
    (~(o.accepted /\ PolicyPresent /\ (d.pin = "present"))
     \/ (KindOf # "exec")
     \/ (a.shape = "execPinned"))

\* The computation's fidelity to the code: the verdict is
\* exactly the rule above, not merely bounded by it. A model
\* that refused everything would satisfy the two claims above
\* and fail this one.
PolicyExact == done => o.accepted = PolicyAllows

\* Witness probes. Both are expected to FAIL; their
\* counterexamples are the evidence the discipline requires.
\* PinnedNeverAccepted says the pinned key's one permitted
\* shape is never accepted even under its own arrangement --
\* its counterexample is forced to be that acceptance: the
\* upgrade key, the pinned script, every other fence of the
\* arrangement satisfied.
PinnedNeverAccepted ==
  done => ~(PinnedProfile /\ (a.key = "upgrade")
            /\ (a.shape = "execPinned") /\ o.accepted)

\* DefaultNeverRuns says the owner's key never runs an ordinary
\* job even in a deployment whose additional keys are pinned --
\* its counterexample is forced to be the default key running
\* an unpinned execution script under the pinned profile: one
\* key's entry fences that key, and no key but the owner's is
\* the owner's.
DefaultNeverRuns ==
  done => ~(PinnedProfile /\ (a.key = "default")
            /\ (a.shape = "execOther") /\ o.accepted)

=============================================================================
