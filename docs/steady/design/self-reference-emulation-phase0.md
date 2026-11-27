# Emulation plan, Phase 0: eligibility record

Written 26-Nov-2026 (late evening PST) by the land-and-execute lane, under DRU's
direction "Land and begin executing this" (main chat, ~23:39 PST). This is
bookkeeping only: no emulation run was started, and nothing was spent. The tier
pick beyond the existing fleet remains DRU's.

## Basis

Phase 0 of docs/steady/design/self-reference-emulation-plan.md makes a component
eligible for emulation when BOTH stand:

1. Its seat card exists (R1), checked against the code and PROTOCOL.
2. Its reflexive round is complete (R3): the 4 questions answered from its seat
   and delineated.

Both halves landed on main tonight, 26-Nov-2026:

- Seat cards: docs/steady/design/seat-cards-v1-diagram.md, landed 23:42 PST,
  with coverage test runner/tests/test_seat_cards.py (the test parses
  assets/how-it-fits-together-wide.svg itself and fails if a label and its
  card drift apart). One card per labeled part of the v1 diagram.
- Reflexive round: docs/steady/design/reflexive-round-v1-diagram.md, landed
  23:44 PST, one section per seat answering the 4 questions from inside the
  seat, with the cross seat findings at the end. Summary entry in ComChat.

## Eligibility, per component

All 17 labeled seats meet both entry conditions. Eligibility is recorded in
the plan's own classes, because the class decides how a cycle may run:

Class A, runnable inside one emulated runner (11), all eligible:
The Door; Signature Check; Shared-Secret Check; Job Queue; The Runner;
The Cage; The Oracle; Size Guard; Transports; The Work Loop; The Way Back.

Class B, exchange components, emulated with two parties (2), all eligible:
Runner-to-SI Exchange (v2); DTLS (v3).

Class C, seats emulated by stand-in (4), all eligible with the plan's stated
limit (a stand-in shows the system's behavior toward the seat, never the
seat's own behavior):
a job; The SI's Mind (outside the box); Reply to Your SI / Signed Result;
You (NOT emulated: where a cycle needs the human seat, the cycle stops at
that step and the stop itself is the finding).

## State after Phase 0

- Eligible: 17 of 17 (11 Class A, 2 Class B, 4 Class C).
- Cycles run: 0. No emulation run was started tonight, per instructions.
- Spend: none. The no-spend tier (existing fleet only) is the only tier in
  effect; any tier beyond it is DRU's pick, not taken here.
- Next step, when directed: the first Class A cycle, supposition written
  first, per the plan's reconciliation step (freeze, run and watch,
  reconcile, candidate findings, promotion only on verified corroboration).
