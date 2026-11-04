# Findings — docs/steady/design/oracle-opinion-design.md

Source: docs/steady/design/oracle-opinion-design.md, reviewed at main 16957c7d.
Sentence units: 81. Flagged: 3. Categories: pre-release 80, post-release 1.

The Oracle opinion design as built: the idea, the 3 modes, the 2 tiers, the learning loop, and the resolved defaults, with a measured run from 2026-10-25. 1 unit looks at a future mode; the 3 short principle labels are the breaks. The rest is pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Status: implemented 2026-10-18." | pre-release | flows |  |
| 2 | "The member is specified in PROTOCOL 3.1/3.2 and…" | pre-release | flows |  |
| 3 | "DRU's proposal (2026-10-15), elaborated 2026-10-18; built, and recorded…" | pre-release | flows |  |
| 4 | "This document remains the design record the build…" | pre-release | flows |  |
| 5 | "A job that arrives written for the wrong…" | pre-release | flows |  |
| 6 | "The sender's intent is legible and the mismatch…" | pre-release | flows |  |
| 7 | "A system that refuses such a job teaches…" | pre-release | flows |  |
| 8 | "Repair converts the hard stop into a recorded…" | pre-release | flows |  |
| 9 | "The job runs; the result states plainly what…" | pre-release | flows |  |
| 10 | "The discipline that makes this safe rather than…" | pre-release | flows |  |
| 11 | "Where the evidence is inconclusive, the system does…" | pre-release | flows |  |
| 12 | "The Oracle reads a job against the box…" | pre-release | flows |  |
| 13 | "Today the sender learns a job failed from…" | pre-release | flows |  |
| 14 | "The opinion closes that gap in three ways,…" | pre-release | flows |  |
| 15 | "The sender grants a latitude per job (a…" | pre-release | flows |  |
| 16 | "The Oracle can be wrong in every mode;…" | pre-release | flows |  |
| 17 | "**advise** — before the job runs, the Oracle…" | pre-release | flows |  |
| 18 | "The job runs exactly as sent." | pre-release | flows |  |
| 19 | "The prediction rides the result (below), so the…" | pre-release | flows |  |
| 20 | "**repair** — if the prediction is an obvious…" | pre-release | flows |  |
| 21 | "A repair is never silent: the result states…" | pre-release | flows |  |
| 22 | "**diagnose** — after a failure, the Oracle attaches…" | pre-release | flows |  |
| 23 | "The sender gets the "why", not just the…" | pre-release | flows |  |
| 24 | "This mode changes nothing and blocks nothing." | pre-release | flows |  |
| 25 | "**off** — no opinion is formed, nothing is…" | pre-release | flows |  |
| 26 | "The latitude ladder the self-learning loop (below) climbs…" | pre-release | flows |  |
| 27 | "The result message (PROTOCOL §3.2) gains one OPTIONAL…" | pre-release | flows |  |
| 28 | "`mode` is the latitude the opinion was formed…" | pre-release | flows |  |
| 29 | "`verdict` is `likely_success`, `likely_failure`, or `no_opinion` (the Oracle…" | pre-release | flows |  |
| 30 | "`note` is bounded plain text, written for the…" | pre-release | flows |  |
| 31 | "`repaired` and `received_digest` appear only when a repair…" | pre-release | flows |  |
| 32 | "Receivers that do not know the member ignore…" | pre-release | flows |  |
| 33 | "A bash-only script is not a repair." | pre-release | flows |  |
| 34 | "An array assignment, process substitution, or a substring…" | pre-release | flows |  |
| 35 | "The specimens in `docs/specimens/repair-results.json` are the two results…" | pre-release | flows |  |
| 36 | "`send_job.py verify` prints one line to stderr when…" | pre-release | flows |  |
| 37 | "Two tiers, in order:" | pre-release | flows |  |
| 38 | "**Deterministic checks.** Platform and interpreter presence, named tools…" | pre-release | flows |  |
| 39 | "These cover the "it's so obvious why" cases,…" | pre-release | flows |  |
| 40 | "**The local model, when inference is configured.** The…" | pre-release | flows |  |
| 41 | "A model-formed opinion is labeled as such in…" | pre-release | flows |  |
| 42 | "The result is signed with the secret that…" | pre-release | flows |  |
| 43 | "Under a future confidentiality-on or asymmetric mode (docs/design/asymmetric-signing-design.md),…" | post-release | flows | Looks forward to a future confidentiality-on or asymmetric mode — post-release by its own terms |
| 44 | "Not a gate." | pre-release | flagged | A free-standing label ("Not a gate."); the principle it names is stated in the next unit |
| 45 | "The opinion never blocks, holds, or approves a…" | pre-release | flows |  |
| 46 | "Not silent." | pre-release | flagged | A free-standing label ("Not silent."); the principle it names is stated in the next unit |
| 47 | "Advice is labeled advice, a repair is reported…" | pre-release | flows |  |
| 48 | "Not a guarantee." | pre-release | flagged | A free-standing label ("Not a guarantee."); the principle it names is stated in the next unit |
| 49 | "`verdict` is an expectation formed from the environment,…" | pre-release | flows |  |
| 50 | "*Measured (2026-10-25): on a test box's deterministic Oracle,…" | pre-release | flows |  |
| 51 | "Every miss was a plain `exit 3`, which…" | pre-release | flows |  |
| 52 | "The numbers and the ledger are in `docs/use/live-examples.md`." | pre-release | flows |  |
| 53 | "The gap this shows, a repeating failure with…" | pre-release | flows |  |
| 54 | "DRU's direction, built in `runner/oracle/learning.py`: the Oracle compares…" | pre-release | flows |  |
| 55 | "This is auditable episodic learning, not model retraining:…" | pre-release | flows |  |
| 56 | "The loop, per job:" | pre-release | flows |  |
| 57 | "**Freeze.** When the opinion machinery forms its pre-execution…" | pre-release | flows |  |
| 58 | "**Reconcile.** The moment execution completes — before the…" | pre-release | flows |  |
| 59 | "A learning-write failure is logged and never blocks…" | pre-release | flows |  |
| 60 | "**Learn, through two channels.** *Verified facts* are derived…" | pre-release | flows |  |
| 61 | "A candidate must pass a strict schema —…" | pre-release | flows |  |
| 62 | "It is promoted to corroborated only when later…" | pre-release | flows |  |
| 63 | "Repetition of a claim is not corroboration —…" | pre-release | flows |  |
| 64 | "**Refresh.** Each new job's opinion evaluation reads the…" | pre-release | flows |  |
| 65 | "A fresh probe supersedes a stale fact at…" | pre-release | flows |  |
| 66 | "The authority rule, unchanged by learning: **a lesson…" | pre-release | flows |  |
| 67 | "A candidate never drives a repair, and no…" | pre-release | flows |  |
| 68 | "Poisoning discipline: raw job output is evidence, never…" | pre-release | flows |  |
| 69 | "Facts are derived by code from verified probes…" | pre-release | flows |  |
| 70 | "A candidate claim phrased as an instruction ("ignore…" | pre-release | flows |  |
| 71 | "The ledger is local state, not wire format:…" | pre-release | flows |  |
| 72 | "`oracle_learning` (default true) turns the whole loop off;…" | pre-release | flows |  |
| 73 | "Each question was resolved as a default plus…" | pre-release | flows |  |
| 74 | "Default latitude: `diagnose` at the first build; raised…" | pre-release | flows |  |
| 75 | "The runner config key `oracle_opinion_mode` is both the…" | pre-release | flows |  |
| 76 | "The runner flag `--oracle-opinion <mode>` overrides for one…" | pre-release | flows |  |
| 77 | "Predictions: deterministic tier-1 only, and only at advise…" | pre-release | flows |  |
| 78 | "`oracle_opinion_predict` is `requested` (default), `always`, or `never`." | pre-release | flows |  |
| 79 | "Diagnose needs no prediction and runs on any…" | pre-release | flows |  |
| 80 | "The model tier runs only when inference is…" | pre-release | flows |  |
| 81 | "Repair re-authorization: `oracle_opinion_repair` is `rejudge` (default — the…" | pre-release | flows |  |
