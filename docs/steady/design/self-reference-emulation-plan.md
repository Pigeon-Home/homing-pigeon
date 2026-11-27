# Emulation and simulation plan: the v1 components, and PUB_POLICY put through the same
## Continuing the self-reference program (R4/R5), from DRU's FUTURE.md closing bullet
## Drafted 26-Nov-2026. Nothing in this plan is bought or sent; the tier pick is DRU's.

Source text (docs/FUTURE.md, his hand): after the reflexive round and the think-like-a-component pass, "Maybe ask to emulate item after completion and watch what happens? Them simulate the same and/or with PUB_POLICY and document findings." This plan makes that sentence executable. It builds on docs/steady/design/self-reference-and-components.md (the seat-binding write-up, requirements R1 to R9) and covers R4 (emulate-after-completion) and R5 (simulate the same with PUB_POLICY), plus the goalpost re-measure protocol from R7.

## 0. Words, used exactly

- **Emulate a component**: run the real component, standalone, in a harness the project controls, doing its real job on synthetic inputs, and watch what it actually does. The runner instance in a scratch directory or on a rig IS the emulation pattern the project already runs (the full-attestation preview battery: a real runner, a real install, real signed jobs, on a machine that is not production).
- **Simulate**: model the exchange without the real component: a scripted peer plays the other side of a protocol, or a document is treated as if it were a component and put through the component questions. Simulation answers "what would the shape do"; emulation answers "what does the thing do".
- **Watch**: the record produced while it runs (logs, the learning ledger, signed results, timings), read against a supposition written before the run. Per DRU's standing rule, the supposition is written down BEFORE the run, the conclusions after, in the same place.

## 1. The machinery that already exists (nothing new to invent)

- **The runner itself** is the emulation substrate. A scratch install under a test directory (the Linux rig pattern) or on the Windows rig's test folder runs the genuine Door, Signature Check, Shared-Secret Check, Job Queue, Runner, Cage, Oracle, Size Guard, Work Loop, Transports and Way Back, because those components are the runner.
- **The Oracle's learning loop** (runner/oracle/learning.py) is the findings engine, and the plan rides it exactly as R6 requires:
  - *Prediction freeze*: before a job runs, the Oracle's opinion is written as a frozen record (`prediction_record` / `freeze`); it cannot be edited afterward.
  - *Reconciliation scoring*: after the outcome, `reconcile` / `classify` score the frozen prediction against what actually happened (correct / incorrect), and write one fact record per feature the job touched.
  - *Candidate lessons*: a candidate is promoted to corroborated only after `oracle_learning_promote_after` verified corroborations (default 2) with NO intervening contradiction. A single contradiction retires the candidate permanently; promotion is derived from the event counts, never self-asserted. Promoted lessons are what `relevant_lessons` feeds back into later briefings.
  - The emulation plan treats every finding the same way: a finding enters as a candidate, and it counts as learned only when a test or a rig run corroborates it the configured number of times. Nothing in this plan self-modifies on a single say-so.
- **The scripted SI peer**: runner/cloud/send_job.py is the SI-side harness; a script driving it is a stand-in SI for exchange tests (it signs, sends, reads results, acks) without any cloud system in the loop.
- **The desk and ComChat**: findings that are about the system (not about a target) are delineated in ComChat and the design docs, per the write-up's section 5; findings from this plan specifically are kept local until DRU rules on landing (see section 6).

## 2. Phase 0: entry conditions (per component)

A component becomes eligible for emulation when BOTH stand:

1. Its seat card exists (R1: what it sees, holds, can do, must never do, how it speaks), checked against the code and PROTOCOL.
2. Its reflexive round is complete (R3: the 4 questions answered from its seat: What are you? What can you not see? What do you trust, and why? What would make you fail honestly?), with the answers delineated.

Eligibility is per component, not all-or-nothing: the plan runs component by component, in the order the cards complete, one emulated component per cycle (R4's acceptance), findings written before the next cycle starts.

## 3. Phase 1: emulate each of the 17 components

The 17 labels fall into 3 classes by how they can be emulated. For every component the cycle is the same: supposition written first (what the seat card predicts the component will do on the planned inputs, including at least one input the card says it must refuse), the run, the watch, the reconciliation (section 5), findings written.

### Class A: runnable inside one emulated runner (11 components)

One scratch runner instance emulates all of these at once; the watch is per component, read off the runner's own records.

| Component | Emulated how | Watched for |
|---|---|---|
| The Door | The scratch runner's real gate; synthetic jobs arrive by file and mailbox drop | Admits only signed jobs; refuses unsigned, malformed, and oversized envelopes without reading bodies for curiosity |
| Signature Check | Jobs signed with the right secret, a wrong secret, a retired key, and a signature over a tampered body | Valid signature never treated as permission by itself (authentication and trust stay apart) |
| Shared-Secret Check | Same battery from the secret's side | Speaks only match / no match; the secret itself never appears in any log or result |
| Job Queue | Jobs submitted faster than the runner drains; duplicate ids; a dead-lettered id resubmitted | Order and patience hold; a duplicate is answered, not re-run; a dead id refuses until dropped or requeued |
| The Runner | The scratch instance itself, end to end | Never initiates outward; every effect traceable to an admitted job |
| The Cage | Jobs that attempt to write outside their allowance, read outside their task, and spawn past their mode, in each security mode | Denials are loud and recorded; enforce is the default posture; a misspelled mode is refused at startup |
| The Oracle | The scratch runner's real Oracle, in model mode and in deterministic (no-model) mode | Prediction frozen before execution on every job; reconciliation written after; advisory only: a questioned job still runs; it never sees more than its curated briefing |
| Size Guard | Jobs and results at, just under, and just over each cap | Caps enforced in numbers, on the job and on the result, both directions |
| Transports | The same job sent by file, by mailbox, and (where configured) by queue | Sealed in transit on every path; the transport speaks in deliveries and receipts, never contents |
| The Work Loop | A spread of jobs: clean run, failing script, timeout-shaped job, huge output | Run, capture, sign holds in all four shapes; a failing job still produces a signed result |
| The Way Back | Jobs with reply_to set to self, to another address, and unset | The result goes only where the signed job named; unset defaults to self; nothing leaks to a third address |

### Class B: exchange components, emulated with two parties (2 components)

| Component | Emulated how | Watched for |
|---|---|---|
| Runner-to-SI Exchange (v2) | The scratch runner plus the scripted SI peer (send_job.py driven by a script): the runner asks, the peer answers, over the same transports | The asking runner gets answers only from the SI the job named; every exchange message is signed; a stranger's answer is refused |
| DTLS (v3) | Two local endpoints (the in-process/mailbox DTLS carriage the project already tests), session keyed by the shared secret | The session opens only after the cookie and binder checks; every job inside the session still passes The Door; resumption does not skip verification |

### Class C: seats that cannot be run, emulated by stand-in (4 components)

These are not code. They are emulated by playing their part with a script or a corpus, and the watch is on what the REST of the system does with the stand-in. The limit is stated in every finding from this class: a stand-in shows the system's behavior toward the seat, never the seat's own behavior.

| Component | Emulated how | Watched for |
|---|---|---|
| a job | A fixed corpus of synthetic jobs (clean, hostile, malformed, oversized, replayed), replayed identically into every Class A cycle | The corpus is the constant: differences between cycles are then the system's, not the input's |
| The SI's Mind (outside the box) | The scripted SI peer, extended: it plans a small task, decomposes it into jobs, reads signed results, revises its plan once | The runner's side of the exchange stays inside the protocol even when the peer behaves badly (revised plans, duplicate sends, an answer addressed wrong) |
| Reply to Your SI / Signed Result | The peer's mailbox as the destination; results inspected exactly as an SI would receive them | The signed result is verifiable by the receiver alone, carries no more than the configured disclosure view, and arrives at the named address only |
| You | NOT emulated. The owner stays human. Where a cycle needs the human seat (an approval, a key paste, a judgment call), the cycle stops at that step and the stop itself is the finding | Recorded plainly each time: which step needed the person, and what the system did while it waited (the honest answer must be: nothing outward) |

## 4. Phase 2: simulate the same with PUB_POLICY (R5)

The policy document is treated as a component and put through the same discipline, in 3 passes. PUB_POLICY is a public document; this phase's findings are about the document's own shape, and the two-shelf rule still applies: the local, non-public artifact the policy references is never used as simulation input, and nothing about it is inferred in the findings.

- **Pass 1, the policy as a job.** PUB_POLICY.md, whole and then section by section (the online-safety plank, the five checking questions, Requirements 1 to 5, Policies A to D, the demarcation line), is sent as signed job content through the Class A emulated runner. Watched: what the pipeline does with a large, structured, non-code job (size caps, the Oracle's frozen prediction about it, reconciliation against the run), and whether the document survives the trip byte-identical on the way back.
- **Pass 2, the reflexive set put to the policy.** The same 4 questions, answered from the document's seat, in writing: What are you? (a public platform draft whose four policies were proposals until the candidate settles them, by its own status note). What can you not see? (its own review flags say it plainly: quotations pending a check against the official transcript; figures compiled from named sources). What do you trust, and why? (records that cannot be quietly rewritten, predictions frozen before outcomes: the checking habits it demands of vendors are the ones it was written under). What would make you fail honestly? (a claim that outruns its evidence: the document already models the failure by flagging its own unverified quotes; the simulation checks whether that honesty survives being read as a component spec).
- **Pass 3, the policy's five questions put to the emulated system.** The standard the policy states for any AI system doing consequential work (Who sent this work, and who approved it? What was expected to happen? What actually happened? What information left the machine? Can any of this be checked later?) is run as a test script against the Class A and B emulations. Each emulation cycle's watch is scored against the 5 questions; a cycle that cannot answer all 5 from its own records produces a finding, in the policy's own terms.

Findings from Phase 2 are documented the same way as Phase 1 (section 6), with one addition: any place where the policy-as-component and the system-as-built disagree is written as a pair (what the policy says, what the emulation did), never smoothed over.

## 5. The reconciliation step (every cycle, both phases)

Each cycle closes the loop the Oracle's machinery already defines:

1. **Freeze**: before the run, the supposition and the seat card's predictions are written down, dated, uneditable afterward.
2. **Run and watch**: the records are kept whole (logs, ledger entries, signed results, timings).
3. **Reconcile**: predictions are scored against the watch, correct / incorrect, one fact record per claim.
4. **Candidate findings**: every incorrect prediction and every surprise becomes a candidate lesson, stated in one sentence with its evidence attached.
5. **Promotion**: a candidate counts as learned only on verified corroboration (a unit test, a rig battery, or a repeated emulation cycle agreeing), the configured number of times, with no contradiction in between. A contradiction retires it permanently, and the retirement is recorded, not deleted.
6. **Improvement, measured**: the program's self-improvement figure is the promoted-lesson count and the measured deltas those lessons produced (runs pruned, waits removed, refusals made correct). It is never reported as a feeling.

## 6. Where findings are documented

- **During the work (local)**: a findings file beside this plan, one entry per cycle: supposition, watch summary, reconciliation verdicts, candidate lessons and their status (candidate / corroborated / promoted / retired). Supposition first, conclusions after, same file.
- **To the project (on DRU's word)**: delineated results in ComChat and, where a seat card or design doc changes because of a promoted lesson, a design-doc landing checked across the whole doc set, with proof-of-work tests per the standing rules. Nothing from this plan lands unbidden.
- **Never**: target-identifying or case material from the fuzzing work (the D-Inferno private shelf) is not simulation input and never appears in findings; the PUB_POLICY simulation uses the public document only.

## 7. The 30 week goalpost: honest re-measure protocol (R7)

The goalpost is the D-Inferno completeness estimate: the standing figure of roughly 30 weeks of serial work to completeness, first framed as a thought experiment and carried since as the number to move. This plan does not move it by assertion. It re-measures it, on a stated basis, the way the project reports its token counts (a number, its basis, and its date, checkable against a record).

- **Basis, stated every time**: remaining work = the enumerated completeness items still open (surfaces unexamined, classes of runs unrun, derivations unchecked), each with its measured cost from completed work (runs per hour on the current fleet, findings per run class, lessons promoted per cycle). Estimate = remaining items at measured rates, under the current lane count. If an item has no measured rate yet, it is listed as unmeasured and excluded from the arithmetic rather than guessed into it; the report says how much of the remainder is unmeasured.
- **The 3 levers, credited only when measured**: (a) parallel lanes divide serial waiting, credited at the measured throughput of the added lanes, not their nameplate cores; (b) simulation and emulation run ahead of the real fleet (an emulated component's cycle that retires a question the real fleet would have spent wall-clock on is credited at the real time it replaced, measured from the cycle that proved the replacement valid); (c) pruning: a promoted lesson that kills a class of runs is credited with that class's whole remaining cost, once, when the promotion lands.
- **Cadence**: re-measure at the end of each emulation cycle and at each tier change; every re-measure is appended to the findings file with its basis, so the series can be checked, not just the latest number.
- **The honesty rule, verbatim from the standing practice**: report the goalpost as a number with its basis; never claim a crossing the numbers do not show. If a re-measure goes UP (new work discovered, a rate re-measured slower), it is reported up, with the reason. A goalpost that only ever moves one way is a story, not a measure.

## 8. Proposal tiers (options only; NO spend is authorized)

From the write-up's section 7, unchanged in substance. The 2 hard limits stand: nothing on a credit card, and any specific option needs DRU's fresh word. The tiers front-load machinery for the learning loop, not raw cores, because the 30 weeks is mostly serial waiting and repeated similar runs: parallelism divides the waiting, promoted lessons divide the repetitions, and the loop is nearly free.

- **Tier $100 (one month, roughly)**: no new rigs. The existing fleet (San Francisco, the FreeBSD node, this VM, Germany) re-tasked in parallel lanes. Buys: the full R1 to R5 pass (seat cards, reflexive round, Phase 1 Class A cycles on the existing rig pattern, Phase 2 in full) and the first honest goalpost re-measure. Expected effect: the estimate itself gets honest, which is the first move of the goalpost.
- **Tier $1,000**: adds 2 dedicated narrow-purpose rigs in the "throw more cores" pattern (~$20/month class each; the tier is mostly time, about a year of them, plus burst), dedicated to emulation lanes: one emulating the runner end to end, one emulating single components. Plus a paid big-window API tier so whole-folder reads are not rate-limited. Buys: Phase 1 running ahead of the real fleet continuously, Class B exchange cycles at volume, simulation results banked daily.
- **Tier $10,000**: adds a small dedicated fleet (4 to 6 machines) running a permanent emulation mesh: runner instances talking DTLS to each other (Class B at scale), component seats emulated continuously, and a formal-checking lane for the proof candidates with enough CPU to run the large replays and decisions without queueing behind fuzzing. Buys: the goalpost attacked on all 3 fronts at once (parallel, simulated, pruned), with weekly re-measures on the section 7 protocol.
- **Tier $100,000 (the ceiling DRU named, not a recommendation to spend it)**: burst cloud compute for the combinatorics sweeps at full scale, plus the $10,000 fleet kept for a year. Honest note: past the $10,000 tier the marginal week bought per dollar falls off hard, because the binding constraint becomes lesson promotion and verification (human-shaped work), not cores. If the goalpost is to move fastest, the $1,000 and $10,000 tiers do the real work; the rest is insurance.

## 9. Limits of this plan, stated plainly

- An emulated runner is the real code on a non-production machine; it proves behavior of the code, not of any specific production host, its mail provider, or its network.
- Class C stand-ins show the system's behavior toward a seat, never the seat itself. "You" is not emulated at all, on purpose.
- A simulation of PUB_POLICY tests the document's shape and the pipeline's handling of it; it does not test the policy's politics, and findings must not pretend otherwise.
- The goalpost is an estimate with a basis, not a deadline and not a promise; section 7's rule governs every report of it.
