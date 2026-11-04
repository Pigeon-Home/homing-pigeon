# Findings — docs/infrastructure-documents/proofs/stage4-p3.md

Source: docs/infrastructure-documents/proofs/stage4-p3.md, reviewed at main cbb52068.
Sentence units: 74. Flagged: 1. Categories: pre-release 73, post-release 1.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This is the record of P3's pass through…" | pre-release | flows |  |
| 2 | "P3 is the second of stage 4's five…" | post-release | flows |  |
| 3 | "The statement is in `properties.md` (P3, nine clauses);…" | pre-release | flows |  |
| 4 | "The code read for this stage is the…" | pre-release | flows |  |
| 5 | "A message reaches the signature check only by…" | pre-release | flows |  |
| 6 | "Where a transport has credentials of its own,…" | pre-release | flows |  |
| 7 | "A message that has passed them still faces…" | pre-release | flows |  |
| 8 | "Where a transport has no credentials — email…" | pre-release | flows |  |
| 9 | "**The composition point, common to all five.** The…" | pre-release | flows |  |
| 10 | "The core performs no transport-credential check and is…" | pre-release | flows |  |
| 11 | "An envelope exists in a channel only because…" | pre-release | flows |  |
| 12 | "The core also decides what each pipe may…" | pre-release | flows |  |
| 13 | "No other pipe ever holds the shared secret,…" | pre-release | flows |  |
| 14 | "**Email — no sender gate.** The email extension…" | pre-release | flows |  |
| 15 | "That login is the runner's credential to its…" | pre-release | flows |  |
| 16 | "P3 claims nothing for email beyond the signature,…" | pre-release | flows |  |
| 17 | "**File — the gate is the operating system's.**…" | pre-release | flows |  |
| 18 | "`FilePipe.scan_jobs` (line 90) applies shape discipline only: symlinks…" | pre-release | flows |  |
| 19 | "Who may present a file at all is…" | pre-release | flows |  |
| 20 | "The claim for file is therefore conditional on…" | pre-release | flows |  |
| 21 | "**NATS — broker authentication, required by default.** `NatsPipe.__init__`…" | pre-release | flows |  |
| 22 | "With credentials, the broker enforces them at CONNECT:…" | pre-release | flows |  |
| 23 | "The publisher side faces the same broker rule." | pre-release | flows |  |
| 24 | "The waiver, when taken, is loud: the pipe…" | pre-release | flows |  |
| 25 | "**DTLS — the secret itself, in a second…" | pre-release | flows |  |
| 26 | "The gate is the handshake: `_ServerSession` (`runner/wire/dtlsproto.py`, line…" | pre-release | flows |  |
| 27 | "The extension delivers only on the session core's…" | pre-release | flows |  |
| 28 | "A resumption PSK is minted only inside an…" | pre-release | flows |  |
| 29 | "**Queues — two bearer tokens at the hosted…" | pre-release | flows |  |
| 30 | "Submission (POST jobs) checks the SI token first…" | pre-release | flows |  |
| 31 | "The runner direction is gated by the runner…" | pre-release | flows |  |
| 32 | "The edge signature check is a second copy…" | pre-release | flows |  |
| 33 | "`TransGate.tla` is a single-decision model, in the shape…" | pre-release | flows |  |
| 34 | "The attempt record carries the transport (all five),…" | pre-release | flows |  |
| 35 | "The deployment record carries the two posture switches…" | pre-release | flows |  |
| 36 | "The counts multiply out and match the checker's…" | pre-release | flows |  |
| 37 | "TLC 2.19 (the `v1.7.4` tools jar) on Java…" | pre-release | flows |  |
| 38 | "Each run is exhaustive." | pre-release | flows |  |
| 39 | "Trace output TLC writes beside the model (`*_TTrace_*`,…" | pre-release | flows |  |
| 40 | "Configuration ; File ; Invariants ; Result ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 41 | "Full composition space ; `TransGate.cfg` ; `P3Inv`, `GateBlocks`,…" | pre-release | flows |  |
| 42 | "Both-gates witness ; `TransWitnessBoth.cfg` ; `BothGatesNeverEnough` ; fails,…" | pre-release | flows |  |
| 43 | "No-gate witness ; `TransWitnessNoGate.cfg` ; `NoGateNoAccept` ; fails,…" | pre-release | flows |  |
| 44 | "The depth of the composition search is 2:…" | pre-release | flows |  |
| 45 | "The fingerprint collision estimate TLC printed for the…" | pre-release | flows |  |
| 46 | "The witness runs stop at their counterexamples, so…" | pre-release | flows |  |
| 47 | "`P3Inv` is the security half: an accepted job…" | pre-release | flows |  |
| 48 | "`GateBlocks` places the block at presentation, not at…" | pre-release | flows |  |
| 49 | "`PresentedExact` and `AcceptedExact` are the fidelity half: presentation…" | pre-release | flows |  |
| 50 | "To re-run from a bare machine: install a…" | pre-release | flows |  |
| 51 | "`TransWitnessBoth.cfg` checks `BothGatesNeverEnough` — the claim that even…" | pre-release | flows |  |
| 52 | "TLC's counterexample is a file-transport arrival whose credential…" | pre-release | flows |  |
| 53 | "Both gates passing lets a job through; a…" | pre-release | flows |  |
| 54 | "`TransWitnessNoGate.cfg` checks `NoGateNoAccept` — the claim that nothing…" | pre-release | flows |  |
| 55 | "TLC's counterexample is an email arrival with a…" | pre-release | flows |  |
| 56 | "That is clause 4 exhibited rather than asserted:…" | pre-release | flows |  |
| 57 | "No finding came out of the code read." | pre-release | flows |  |
| 58 | "In particular, no transport was found where a…" | pre-release | flows |  |
| 59 | "Two near-things were found and are recorded as…" | pre-release | flows |  |
| 60 | "The model composes the transport gate with the…" | pre-release | flows |  |
| 61 | "Whether a presented job executes is P1: the…" | pre-release | flows |  |
| 62 | "The credential and signature outcomes are independent bits." | pre-release | flows |  |
| 63 | "For DTLS they draw on one secret in…" | pre-release | flows |  |
| 64 | "Clause 7 carries it in words." | pre-release | flows |  |
| 65 | "File's refused attempts are enumerated by the model,…" | pre-release | flows |  |
| 66 | "The model's claim for file is the composition…" | pre-release | flows |  |
| 67 | "The NATS claim is likewise conditional on the…" | pre-release | flows |  |
| 68 | "The extension's half — refuse to start unauthenticated,…" | pre-release | flows |  |
| 69 | "The model's credential bit for queues is the…" | pre-release | flows |  |
| 70 | "The runner-side token (lease, ack, result posts) is…" | pre-release | flows |  |
| 71 | "The composition rests on the channel boundary: the…" | pre-release | flows |  |
| 72 | "The channel directories live under the runner's base…" | pre-release | flows |  |
| 73 | "Results travel the other direction over the same…" | pre-release | flows |  |
| 74 | "Nothing here claims anything about results; P3 is…" | pre-release | flows |  |
