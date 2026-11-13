# The fleet: every machine, what it is for, and what it costs

One line per machine the project rents or runs, and per service
with a bill (AGENTS.md rule 17, the owner's decision of
2026-11-12, Q171). A line says what the machine is for, the
provider and plan, what it costs a month, the day it was stood
up, and the day it ends or is next reviewed. The seat that holds
a machine keeps its line true.

Two rules stand with the page:

- **Nothing that reaches a machine goes here.** No address,
  hostname, key, token or account identifier. A machine is named
  by the place-name the record already uses for it.
- **Spending waits for the owner's word.** A new machine, a
  bigger plan or a paid API tier is asked in
  `docs/steady/seats/questions.md` and waits there.

And one from the order of work
(`campaign-standing-orders.md`, item 4): a rented rig with
nothing banked since its last review goes back to fuzzing or is
given back, named here a day before it is done and banked first.

## The lines

Seeded on 2026-11-12 from what the tree itself says, and from
nothing else; "not on the record" marks what only the seat that
holds the machine can state (Q173). The fuzz columns are the
corpus's own run records (`runner/tests/de_dust/runs.jsonl`),
counted by the rig name each record carries.

| Machine | What it is for | Provider and plan | A month | Stood up | Ends, or next review | Fuzz records: count, first, last | Standing today |
|---|---|---|---|---|---|---|---|
| Germany | The fleet's Windows seat: the Windows half of the suite live, and 8 cores of fuzzing | Hetzner Cloud, CX43 (8 shared vCPU, 16 GB), Falkenstein | $20.63 (EUR 18.49 at the rate of 2026-10-31), billed hourly to the monthly cap | 2026-10-31 | not on the record | 11,423; 2026-11-01; 2026-11-12 | banking; not on the record beyond that |
| Menlo Park | The Linux VM that hosts the Muse seat: 4 cores for the suite's shard lanes, the rotation lane and fuzz lanes | not on the record | not on the record | not on the record | not on the record | 7,025; 2026-10-30; 2026-11-01 | not on the record |
| San Francisco | One core: a second, small machine reaching the suite's verdicts independently | a droplet; the plan is not on the record | $12, as the Germany rig's report recorded it | not on the record | not on the record | 399; 2026-10-30; 2026-11-01 | recorded on 2026-11-01 as kept, its fuzzing stopped, idle; on 2026-11-03 as carrying a suite-shard lane; not on the record since |
| Nuremberg | The second rig of the campaign | Hetzner Cloud, 1 vCPU (AMD EPYC-Genoa), 917 MiB | not on the record | 2026-10-27 | not on the record | 1,250; 2026-10-30; 2026-10-31 | absent from the three-machine inventory of 2026-11-03; not on the record since |
| The FreeBSD node | The FreeBSD proof on a kernel of its own | a dedicated host; the provider and plan are not on the record | not on the record | 2026-11-10 | not on the record | none (not a fuzzing rig) | installed and proven by a local job; its mailbox pairing is still owed |

Where each seeded fact stands: the Germany rig's report
(`docs/infrastructure-documents/reports/falkenstein-rig-2026-10-31.md`),
which also carries San Francisco's line as of that day; the
forum's inventory of 2026-11-03 ("tasking: what the cores are
doing"); the standing orders' ledger line of 2026-10-27 for
Nuremberg; and the desk's record of the FreeBSD node
(`desk.md`, "Where the work stands").

## Q173 completion: suppositions, recorded before the measuring

Recorded by the Muse seat on 2026-11-12, before the recount
and the workspace-record check this completion rests on (the
conductor's supposition-first rule). Each is settled in the
conclusions under the completed lines below.

- **Q173-S1.** A recount of `runner/tests/de_dust/runs.jsonl`
  by the rig name each record carries reproduces the seeded
  counts and last dates exactly -- Germany 11,423 to
  2026-11-12, Menlo Park 7,025 to 2026-11-01, San Francisco
  399 to 2026-11-01, Nuremberg 1,250 to 2026-10-31 -- plus
  one stray record under a clipped form of San Francisco's
  name, dated 2026-10-31, which the forum already explains
  as a timer line that split on the space.
- **Q173-S2.** No machine beyond the five lines stands in the
  tree or the workspace record as a fleet machine today: the
  first Falkenstein machine was created and deleted the same
  day (2026-10-31) during a location comparison, and no Mac
  joins the fleet (the desk's record, 2026-11-11).
- **Q173-S3.** Nuremberg is the only rented rig idle with
  nothing banked since its last review: it was stopped into
  reserve at the conductor's word on 2026-10-31, every project
  service on it stopped and disabled, and no record of it
  working stands after that day.
- **Q173-S4.** San Francisco's later record supersedes its
  2026-11-01 idle line: a suite-shard lane on 2026-11-03, and
  by 2026-11-10 the fleet's fuzz lane and the preview loop's
  Linux leg. It has gone back to work and is not a give-back
  candidate.
- **Q173-S5.** The FreeBSD node's provider, plan and cost are
  provable from the workspace record (the Phase 2 report of
  2026-11-10) though the tree alone calls it only a dedicated
  host; Menlo Park's provider, plan, cost and stood-up day
  are provable nowhere -- the workspace record calls it the
  conductor's own VM -- and those cells will stay stated as
  gaps rather than be filled by inference.
- **Q173-S6.** Of the services, only the hosted queue's bill
  is provable from the tree (inside the provider's free tier
  at the recorded use); the outside-model API access carries
  no monthly figure on any record the seat can read, and
  that cell will stand as a gap for the conductor to supply.

## Services with a bill

Not on the record as lines yet. The seat that holds each one
states it here in the same shape -- what it is for, the plan,
what it costs a month, since when, the next review -- or states
that it bills nothing: the hosted queue's Worker and its account,
the outside-model API access the desk holds, any hosting account
the control plane's adapters are exercised against, and anything
else that draws on a card.
