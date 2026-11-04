---------------------------- MODULE TransGate ----------------------------
\* Property P3 (properties.md): where a transport has credentials
\* of its own, they are a required second gate beside the HMAC
\* signature -- a job arriving over a transport whose own
\* credential check has not passed is not presented to the
\* signature check at all, whatever its signature says.
\*
\* The gate (Gate.tla) decides whether a job runs; this model
\* stands in front of it. A message reaches the gate only by
\* crossing its transport, and the transports compose with the
\* core by position: each transport extension (or the far end it
\* talks to, or the operating system under it) applies its own
\* credential check first, and only a message that passed is
\* written into the channel the core services. The core is
\* transport-blind (runner/runner.py, _service_transports; runner/
\* wire/transports.py, service_channel): it runs every envelope
\* it finds through handle_mail, and an envelope exists in the
\* channel only because a pipe put it there. Acceptance in this
\* model is therefore presented-then-signed: presented to the
\* core, and the signature valid. Execution past that point is
\* P1's claim, not this model's.
\*
\* The attempt record (a) carries the three things the
\* composition branches on:
\*
\*   - the transport the message arrived on;
\*   - sigValid: the body's signature verifies under a secret
\*     the runner holds;
\*   - credPass: the transport's own credential check passed,
\*     where the deployment has one in force. On a transport
\*     with no gate in force the bit is read by nothing, exactly
\*     as Confine.tla's unread fields are: it is in the space
\*     because a sender can present it, and the outcome does not
\*     depend on it there.
\*
\* The deployment record (d) carries the two posture switches
\* the code has:
\*
\*   - natsWaived: the NATS deployment runs with
\*     allow_unauthenticated set and no broker credentials, the
\*     one open waiver of a transport gate in the shipped code
\*     (runner/transport_extensions/nats/__main__.py). Read only
\*     on the nats branch.
\*   - edgeSig: the queues deployment leaves the hosted edge's
\*     own signature check on (REJECT_INVALID_HMAC, default on;
\*     runner/cloud/queues-worker/src/index.js). Read only on
\*     the queues branch: with it on, a job whose signature
\*     fails at the edge is never enqueued, so it is never
\*     presented either -- but the bearer check runs first, and
\*     the core checks the signature again regardless. The edge
\*     check is a duplicate of the second gate, never a
\*     substitute for the first.
\*
\* What credPass is, per transport, is the code's own mechanism,
\* and stage4-p3.md records the sites:
\*
\*   - email: no gate exists. The mailbox login is the runner's
\*     credential to its own mail server and authenticates no
\*     sender, so GateInForce is FALSE on this branch by design.
\*   - file: the gate is the inbox directory's OS access
\*     control. No credential exists in the extension's code;
\*     credPass is whether the presenting principal was admitted
\*     by that control. The model enumerates refused attempts;
\*     that the OS refuses them is the recorded assumption the
\*     claim for this transport rests on, not a mechanism this
\*     model or the runner's code performs.
\*   - nats: broker authentication. The extension refuses to
\*     start credential-less unless waived, and a connection the
\*     broker refuses delivers nothing.
\*   - dtls: the handshake. The shared secret itself is the
\*     PSK, so the two gates draw on one secret in two roles;
\*     credPass is whether the session authenticated (binder
\*     verified under a secret the identity lookup admits).
\*     credPass and sigValid are independent bits because they
\*     are independent checks: a peer can hold the secret and
\*     still send a badly signed job, and a signed job can be
\*     offered by a peer that cannot complete the handshake.
\*     Only the first of those is presented; neither executes
\*     without the other check -- the second is P1's concern,
\*     recorded here as this model's Accepted.
\*   - queues: the SI's bearer token, hash-compared at the edge
\*     before anything is enqueued, and the runner's bearer
\*     token on the lease; credPass is the submission-side check,
\*     the one a job's arrival stands or falls on. The runner-
\*     side token gates delivery to the core in the other
\*     direction and is the same shape: a failed token means
\*     nothing is leased, so nothing is presented.

EXTENDS Integers

Transports == {"email", "file", "nats", "dtls", "queues"}

Attempts == [
  transport: Transports,
  sigValid:  BOOLEAN,
  credPass:  BOOLEAN
]

Deployments == [
  natsWaived: BOOLEAN,
  edgeSig:    BOOLEAN
]

VARIABLES a, d, o, done

vars == <<a, d, o, done>>

\* Whether this deployment's transport gate is in force for the
\* attempt's transport. Email has none by design; NATS has one
\* unless the deployment waived it in the open; file, DTLS, and
\* queues have one in every deployment the code can start.
GateInForce ==
  CASE a.transport = "email" -> FALSE
    [] a.transport = "nats"  -> ~d.natsWaived
    [] OTHER                 -> TRUE

\* The queues edge, when its own signature check is on, refuses
\* a badly signed job before enqueue: the job is not presented.
\* The bearer check runs before this in the code, which is why
\* this term is only reached when the credential gate passed or
\* none is in force.
EdgeBlocks ==
  (a.transport = "queues") /\ d.edgeSig /\ ~a.sigValid

\* A message is presented to the core -- written into the
\* channel, leased, or carried on an established session -- only
\* when the transport gate, where one is in force, passed, and
\* the queues edge did not refuse it first.
Presented ==
  IF GateInForce /\ ~a.credPass THEN FALSE
  ELSE ~EdgeBlocks

\* Acceptance to the signature check is presentation; acceptance
\* of the job is presentation and a valid signature. The whole
\* of P1 stands behind the second conjunct and is not restated
\* here.
Accepted == Presented /\ a.sigValid

Init ==
  /\ a \in Attempts
  /\ d \in Deployments
  /\ done = FALSE
  /\ o = "unset"

\* One decision step: the composition computes the outcome from
\* the attempt and the deployment and nothing else.
Decide ==
  /\ ~done
  /\ done' = TRUE
  /\ o' = [ presented   |-> Presented,
            accepted    |-> Accepted,
            gateApplied |-> GateInForce ]
  /\ UNCHANGED <<a, d>>

Done ==
  /\ done
  /\ UNCHANGED vars

Next == Decide \/ Done

Spec == Init /\ [][Next]_vars

\* P3, the security claim, in closed form: an accepted job
\* carried a valid signature, and where a transport gate was in
\* force, its credential check passed. A signature alone never
\* carries a job past a gate that is in force. (Stated with
\* disjunctions: nested implications do not parse.)
P3Inv ==
  done =>
    (~o.accepted \/ (a.sigValid /\ (~GateInForce \/ a.credPass)))

\* The gate blocks at presentation, not at execution: a failed
\* credential check on a gated transport means the core never
\* sees the message at all.
GateBlocks ==
  done => ~((GateInForce /\ ~a.credPass) /\ o.presented)

\* The computation's fidelity to the code's composition: the
\* outcome is exactly presentation by the rule above, and
\* acceptance exactly presentation plus the signature. A model
\* that presented nothing, or accepted on the credential alone,
\* would fail these.
PresentedExact == done => o.presented = Presented
AcceptedExact == done => o.accepted = Accepted

\* Witness probes. Both are expected to FAIL; their
\* counterexamples are the evidence the discipline requires.
\* BothGatesNeverEnough says even a job passing both gates is
\* never accepted -- its counterexample is forced to be a
\* both-gates acceptance: gate in force, credential passed,
\* signature valid.
BothGatesNeverEnough ==
  done => ~(GateInForce /\ a.credPass /\ a.sigValid /\ o.accepted)

\* NoGateNoAccept says nothing is accepted where no gate is in
\* force -- its counterexample is forced to be a signature-only
\* acceptance, on email by design or on a waived NATS deployment
\* by the owner's open waiver: the transports where P3 claims
\* no second gate, exhibited rather than assumed.
NoGateNoAccept ==
  done => (GateInForce \/ ~o.accepted)

=============================================================================
