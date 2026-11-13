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

**The owner's ceiling: $700 a month** (2026-11-12, Q178), for the
machines and the services on this page together. It is a limit
and not an allowance: however far under it the month stands, a
new machine, a bigger plan or a paid API tier still waits for his
word. The seat that holds the page states the month's total
against it, and asks before a month would pass it.

## The month against the ceiling

Stated 2026-11-13 (Q178). The lines whose cost is on the record
sum to **about $52.97 a month** -- Germany $20.63, San Francisco
$12, Nuremberg about $8.34, the FreeBSD node about $12, the
hosted queue $0 and the hosting control-plane accounts $0
beyond the machines -- against the ceiling of $700 a month.
The "about" is the two lines' own: their figures stand as
about-figures on their lines, and the sum carries it. The
total is restated when a line changes.

Beside the sum stand the lines whose cost is not on the
record, so the stated total is the sum of what is on the
record and not a complete month: **Menlo Park,
Outside-model API access and GitHub**. Each of those lines
states below whether the seat can read its month itself.
On the measured total the month does not pass the ceiling,
so no question under Q178's third ask is filed by this
statement; the standing duty stands, and a month whose total
would pass the ceiling is asked in the questions file the
day a seat sees it.

## The lines

Seeded on 2026-11-12 from what the tree itself says, and
completed the same day (Q173) from the tree, the ship records
and the workspace record, each fact verified first-hand by the
seat that completed it. Where no record the seat can read
proves a fact, the line says so plainly and names what the
conductor must supply; nothing is filled in by inference. The
fuzz columns are the corpus's own run records
(`runner/tests/de_dust/runs.jsonl`), counted by the rig name
each record carries, recounted for this completion.

| Machine | What it is for | Provider and plan | A month | Stood up | Ends, or next review | Fuzz records: count, first, last | Standing today |
|---|---|---|---|---|---|---|---|
| Germany | The fleet's Windows seat: the Windows half of the suite live, and 8 cores of fuzzing | Hetzner Cloud, CX43 (8 shared vCPU, 16 GB), Falkenstein | $20.63 (EUR 18.49 at the rate of 2026-10-31), billed hourly to the monthly cap | 2026-10-31 | no fixed end on the record (billed hourly to the monthly cap); the next review day is not on the record -- the conductor to supply it | 11,423; 2026-11-01; 2026-11-12 | Active, and not idle: banking, with fuzz records to 2026-11-12, carrying the Windows seat |
| Menlo Park | The Linux VM that hosts the Muse seat: 4 cores for the suite's shard lanes, the rotation lane and fuzz lanes | not on the record -- the workspace record calls it the conductor's own VM; its provider and plan stand nowhere the seat can read | no rental bill on the record -- the conductor's own VM, per the workspace record; any bill it carries is the conductor's to supply. The seat cannot read a month's usage for it: it holds no provider key or billing page for this machine (stated 2026-11-13, Q178), so the figure stays the conductor's to supply | not on the record | not on the record -- the conductor to supply a review day if the machine carries one | 7,025; 2026-10-30; 2026-11-01 | The seat itself, and not idle: it hosts this seat's suite shard lanes, rotation lane and fuzz lanes (the inventory of 2026-11-03), and its lanes stood alive at the watchdog read of 2026-11-10. Its corpus records end 2026-11-01 because the seat's work moved to the suite lanes, not because the machine stopped. Not rented on the record, so the fuzz-or-give-back rule does not reach it |
| San Francisco | One core: a second, small machine reaching the suite's verdicts independently | DigitalOcean, s-1vcpu-2gb (1 vCPU, 2 GB, 50 GB), San Francisco 2 | $12 | 2026-10-28 | not on the record -- the conductor to supply the next review day | 399; 2026-10-30; 2026-11-01 | **Back to fuzzing.** Its fuzzing was stopped and the box kept idle on 2026-11-01; it carried a suite-shard lane of its own on 2026-11-03, and by 2026-11-10 it runs the fleet's fuzz lane and the preview loop's Linux leg. It stands idle no longer and is not a give-back candidate |
| Nuremberg | The second rig of the campaign: one core of corpus growing, and the hosted runner the hosted queue was first proven on | Hetzner Cloud, CPX02 (1 vCPU, AMD EPYC-Genoa, 1 GB), Nuremberg | about $8.34 (EUR 7.49 at the rate of 2026-10-28) | 2026-10-27 | reviewed 2026-10-31, when it was stopped into reserve (see the standing column) | 1,250; 2026-10-30; 2026-10-31 | **Recommendation: give back.** Stopped at the conductor's word on 2026-10-31 and put in reserve: every project service on it stopped and disabled, the box doing nothing since, absent from the three-machine inventory of 2026-11-03, and nothing banked since 2026-10-31. Named here on 2026-11-12, a day before a give-back could be done, and banked first: its banks stand in the tree to 2026-10-31, and the seat that holds it verifies nothing unbanked remains on the box before anything is deleted. The give-back itself is the conductor's decision and is not executed by this page |
| The FreeBSD node | The FreeBSD proof on a kernel of its own: the platform's confinement backend proven where no VM step inside a Linux CI runner could prove it | Hetzner Cloud, CX33, on the conductor's existing Hetzner account (the workspace record of the Phase 2 report, 2026-11-10) | about $12 all-in: $9.99 gross for the node plus the charge for its primary address, and about $1 for its snapshot (the workspace record, 2026-11-10), inside the $20-a-month cap the conductor set | 2026-11-10 | next review about 2026-12-10: the conductor's stated term is about a month (2026-11-09), a plan on the workspace record, not a provider contract date | none (not a fuzzing rig) | Proven, and not idle: the runner is installed, a first proof job passed end to end through the installed config, and its confinement backend landed and stands field-proven (the desk's record). Its mailbox pairing is still owed. Keep it to its review day; at that review it is given back unless the conductor extends it |

One machine the page does not carry as a line, because it does
not stand: a first machine of the Germany rig's name and shape
was created and deleted the same day, 2026-10-31, during a
location comparison (its rig report carries the fact). It
bills nothing today. No other machine stands in the tree or
the workspace record as a fleet machine: no Mac joins the
fleet (the desk's record, 2026-11-11 -- the macOS backend is
proven on the CI legs), and the locations compared for the
Germany rig and not taken were never stood up.

Where each fact stands: the Germany rig's report
(`docs/infrastructure-documents/reports/falkenstein-rig-2026-10-31.md`),
which also carries San Francisco's line as of that day; San
Francisco's own report, in full in the git history at the
commit its compressed summary names
(`docs/steady/reports/san-francisco-rig-2026-10-28.md`); the
first Germany rig's report, which is Nuremberg's dossier
(`docs/steady/reports/germany-rig-2026-10-28.md`, and
`docs/steady/reports/rig-2026-10-27.md`); the forum's
inventory of 2026-11-03 ("tasking: what the cores are doing");
the desk's record of the FreeBSD node (`desk.md`, "Where the
work stands"), including the Packet 8 conclusions of
2026-11-10 that carry San Francisco's present work; and the
workspace record -- the fleet calculation of 2026-11-01
(Menlo Park the conductor's own VM), the reserve record of
2026-10-31 (Nuremberg stopped, then its runner stopped, at
the conductor's word), the watchdog read of 2026-11-10 (the
seat's lanes alive), and the FreeBSD Phase 2 report of
2026-11-10 (the node's plan and all-in cost, and the
conductor's term of about a month, recorded 2026-11-09).

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

Conclusions (2026-11-12, the same seat, after the measuring):
**Q173-S1 holds** -- the recount, run on the tree this
completion lands on, reads Germany 11,423 (2026-11-01 to
2026-11-12), Menlo Park 7,025 (2026-10-30 to 2026-11-01),
San Francisco 399 (2026-10-30 to 2026-11-01), Nuremberg
1,250 (2026-10-30 to 2026-10-31), and the one clipped record
under "San", 2026-10-31, exactly as supposed. **Q173-S2
holds** -- no sixth standing machine was found in the tree,
the ship records or the workspace record; the deleted first
Falkenstein machine is noted under the lines, not lined.
**Q173-S3 holds** -- Nuremberg's stop into reserve stands on
the workspace record of 2026-10-31 (twice: the rig, then its
runner), its absence from the 2026-11-03 inventory agrees,
and nothing banked from it stands after 2026-10-31; it is
the one rented rig the order of work reaches, and its line
carries the give-back recommendation, named a day ahead and
banked first, for the conductor to decide. **Q173-S4
holds** -- San Francisco's shard lane of 2026-11-03 stands in
the forum inventory, and its fuzz lane and preview-loop leg
stand in the desk's Packet 8 conclusions of 2026-11-10; its
line reads back to fuzzing. **Q173-S5 holds in both
halves** -- the FreeBSD line is completed from the workspace
record (Hetzner, CX33, about $12 a month all-in, review at
about a month), and Menlo Park's provider, plan, cost and
stood-up day were found on no record the seat can read, so
they stand on its line as the gaps they are. **Q173-S6
holds** -- the services below carry the queue at its free-tier
standing, and the API access with its monthly figure stated
as not on the record.

What the conductor must still supply, the whole gap list:
(1) a next review day for Germany and for San Francisco;
(2) Menlo Park's provider, plan, stood-up day and any bill,
if it carries one -- on the present record it is his own VM
with no rental bill; (3) the monthly spend, if any, of the
outside-model API access and of the GitHub account, and the
Cloudflare account's plan standing beyond the free tier the
transports page records; (4) the FreeBSD node's provider
contract date, if one exists beyond his stated term of about
a month; and (5) the decision itself on Nuremberg: give back
(the recommendation on its line) or send it back to fuzzing.
No give-back is executed by this completion.

## Services with a bill

| Service | What it is for | Provider and plan | A month | Since | Ends, or next review |
|---|---|---|---|---|---|
| The hosted queue | The queue the hosted runners poll: jobs in, results out, one tenant | Cloudflare: a one-tenant Worker with one Durable Object per tenant, on the operator's own account | $0 at the recorded use -- a Worker and one Durable Object per tenant sit inside Cloudflare's free tier for any agent that is not extraordinarily busy (the transports page) | 2026-10-27 | not on the record -- the conductor to supply the account's plan standing and a review day |
| Outside-model API access | A second pair of eyes beside the project's own lanes: independent reviews, cross-checks of a finding, breadth on a research question (the desk's record) | Anthropic and OpenAI, the credentials held in the operator's secure vault; no paid tier stands on the record, and none is taken without the conductor's word (rule 17) | not on the record -- no monthly figure stands in the tree or the workspace record; the conductor to supply the spend. The seat cannot read a month's usage for it with the keys it holds (read 2026-11-13, Q178): the Anthropic key returned its organisation record and no usage figure, its data calls standing gated on a workspace identifier the operator supplies, the OpenAI key returned its models list and no usage figure, and neither helper the seat holds carries a usage or billing read -- so the figure stays the conductor's to supply. Reading spent nothing: no completion was run | 2026-11-08 | not on the record. Standing on the desk's record: the OpenAI side is callable and has been exercised; the Anthropic side authenticates, its data calls gated on a workspace identifier the operator supplies |
| GitHub | The tree's home, its releases, and the builders every landing and release runs on | the project's own account; the plan is not on the record | not on the record -- the hosting page notes billable minutes only for an ephemeral dispatch on a user's own account; any plan bill is the conductor's to supply. The seat cannot read a month's bill for it (read 2026-11-13, Q178): the GitHub connection it holds carries repository, issue and search tools and no billing read among them, so the figure stays the conductor's to supply | not on the record | not on the record |
| Hosting control-plane accounts | The provider adapters (Fly, Hetzner, DigitalOcean, GitHub Actions) the provisioner creates machines through | exercised against recorded exchanges only; the provisioner itself is not yet live (the hosting page) | no bill on the record beyond the machines lined above | -- | -- |

Nothing else that draws on a card was found in the tree, the
ship records or the workspace record. A mailbox for the
project's own domain was considered and not bought (the
workspace record, 2026-10-31), so no line stands for it; if a
service with a bill exists that no record names, it is the
conductor's to name, and it takes a line here when he does.
