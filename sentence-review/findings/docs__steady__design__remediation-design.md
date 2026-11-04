# Findings — docs/steady/design/remediation-design.md

Source: docs/steady/design/remediation-design.md, reviewed at main b2a9d030.
Sentence units: 120. Flagged: 0. Categories: pre-release 120, post-release 0.

The remediation design of record: the gap it fills (nothing acts while a job runs), the 3 fix stories kept separate, the intent envelope as the trigger's basis, the divergences recognized, the 2 authorities (deterministic tripwires and the Oracle's judgment), and the as-built deltas. Written before the code and transcribed into it the same day; the argument is linear — doctrine, trigger, authority, action — and every section hands to the next. Nothing is flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Status: design, recorded 2026-10-18, expanded the same evening…" | pre-release | flows |  |
| 2 | "Built 2026-10-18 (`runner/oracle/remediation.py`, wired into `execute_job`; tests in…" | pre-release | flows |  |
| 3 | "This document is the design of record: the…" | pre-release | flows |  |
| 4 | "The project can already refuse a job before…" | pre-release | flows |  |
| 5 | "What it cannot do is act *while* a…" | pre-release | flows |  |
| 6 | "If the agent determines that something from a…" | pre-release | flows |  |
| 7 | "The DRI playbook pages the owner, and its…" | pre-release | flows |  |
| 8 | "That was the right doctrine when the system…" | pre-release | flows |  |
| 9 | "The owner has since directed otherwise: the system…" | pre-release | flows |  |
| 10 | "This document gets that design right before it…" | pre-release | flows |  |
| 11 | "Three different "fix" stories live in this project…" | pre-release | flows |  |
| 12 | "**The judge** gates *entry* -- when it is…" | pre-release | flows |  |
| 13 | "It is off by default and reads for…" | pre-release | flows |  |
| 14 | "In the default posture there is no entry…" | pre-release | flows |  |
| 15 | "**Opinion repair** fixes the *job*: a job that…" | pre-release | flows |  |
| 16 | "**Remediation** stops a *running* job whose observed behavior…" | pre-release | flows |  |
| 17 | "Every job that runs under an opinion carries…" | pre-release | flows |  |
| 18 | "That envelope is the record of *what the…" | pre-release | flows |  |
| 19 | "Remediation watches the running job against it." | pre-release | flows |  |
| 20 | "A job doing what its envelope said —…" | pre-release | flows |  |
| 21 | "A job doing what its envelope did not…" | pre-release | flows |  |
| 22 | "Expectation versus outcome is a genuine field of…" | pre-release | flows |  |
| 23 | "The system never has to know what malice…" | pre-release | flows |  |
| 24 | "It has to know what *this job promised*,…" | pre-release | flows |  |
| 25 | "Concretely, the divergences the design recognizes today:" | pre-release | flows |  |
| 26 | "**Undeclared reach.** The running job touches a credential…" | pre-release | flows |  |
| 27 | "(Writes outside the workdir are not visible mid-run;…" | pre-release | flows |  |
| 28 | "**Adversary-shaped resources.** The job's window fills with the…" | pre-release | flows |  |
| 29 | "**Confinement events.** A job straining or escaping its…" | pre-release | flows |  |
| 30 | "**A sense fires about this job.** Any sense…" | pre-release | flows |  |
| 31 | "Detection may come from anywhere (see Placement)." | pre-release | flows |  |
| 32 | "A divergence is evidence, not yet a verdict." | pre-release | flows |  |
| 33 | "What happens next depends on which authority is…" | pre-release | flows |  |
| 34 | "The owner was asked to choose between deterministic…" | pre-release | flows |  |
| 35 | "The selection this design records:" | pre-release | flows |  |
| 36 | "**Deterministic tripwires** — a short, enumerated list of…" | pre-release | flows |  |
| 37 | "These are the owner's pre-authorized reflexes." | pre-release | flows |  |
| 38 | "No model is consulted, the list is closed,…" | pre-release | flows |  |
| 39 | "**The Oracle's judgment** — where inference is configured,…" | pre-release | flows |  |
| 40 | "It judges with the context the build assembles…" | pre-release | flows |  |
| 41 | "Its order is recorded *as its judgment* —…" | pre-release | flows |  |
| 42 | "On a box without inference (Pi Light), this…" | pre-release | flows |  |
| 43 | "The option surface is one key, `remediation_mode` (`off…" | pre-release | flows |  |
| 44 | "**Default: `deterministic`** — the reflexes are armed out…" | pre-release | flows |  |
| 45 | "`off` restores the original doctrine in full: the…" | pre-release | flows |  |
| 46 | "**Kill the tree.** The job's whole process tree,…" | pre-release | flows |  |
| 47 | "A divergence that survives its parent is not…" | pre-release | flows |  |
| 48 | "The result records the job as failed-by-remediation, distinctly…" | pre-release | flows |  |
| 49 | "**Quarantine the outputs.** The job's work directory and…" | pre-release | flows |  |
| 50 | "Nothing is deleted by the system, ever." | pre-release | flows |  |
| 51 | "The owner's release path (`--remediation-release <job_id>`, plus the…" | pre-release | flows |  |
| 52 | "Quarantine is also where a merely-failed job's outputs…" | pre-release | flows |  |
| 53 | "**Refer the file to the box's antivirus.** A…" | pre-release | flows |  |
| 54 | "The Oracle knows things the AV does not:…" | pre-release | flows |  |
| 55 | "So after a kill or quarantine, the system…" | pre-release | flows |  |
| 56 | "There is no prior "judged malicious" step and…" | pre-release | flows |  |
| 57 | "On Windows, a Defender custom scan (`MpCmdRun -Scan…" | pre-release | flows |  |
| 58 | "A consumer antivirus accepts a scan request, not…" | pre-release | flows |  |
| 59 | "But an AV that confirms takes ownership with…" | pre-release | flows |  |
| 60 | "The enterprise form of the same idea (Defender…" | pre-release | flows |  |
| 61 | "The AV's verdict — `confirmed`, `clean`, or `unavailable`…" | pre-release | flows |  |
| 62 | "**Page the owner.** Through the DRI channel, carrying…" | pre-release | flows |  |
| 63 | "Remediation acts first and pages after — the…" | pre-release | flows |  |
| 64 | "In `off` mode the same page is all…" | pre-release | flows |  |
| 65 | "Every act lands twice." | pre-release | flows |  |
| 66 | "In the job's result, as a `remediation` member…" | pre-release | flows |  |
| 67 | "The sender learns their job was stopped and…" | pre-release | flows |  |
| 68 | "And in the audit log, as the operator's…" | pre-release | flows |  |
| 69 | "A remediation the owner cannot reconstruct from the…" | pre-release | flows |  |
| 70 | "The quarantine area is bounded like the other…" | pre-release | flows |  |
| 71 | "The owner asked whether remediation is an extension…" | pre-release | flows |  |
| 72 | "The design's answer is both, split at the…" | pre-release | flows |  |
| 73 | "**The acts are core.** Only the runner holds…" | pre-release | flows |  |
| 74 | "An extension *cannot* kill a job, and must…" | pre-release | flows |  |
| 75 | "A kill switch reachable from extension code would…" | pre-release | flows |  |
| 76 | "**The detection is extension-shaped.** A sense that notices…" | pre-release | flows |  |
| 77 | "An owner who writes a sense that watches…" | pre-release | flows |  |
| 78 | "That is the ecosystem working as designed." | pre-release | flows |  |
| 79 | "**Scope is the job.** The kill is the…" | pre-release | flows |  |
| 80 | "Remediation never widens to the box, the sender's…" | pre-release | flows |  |
| 81 | "**No sender surface.** A job cannot request, widen,…" | pre-release | flows |  |
| 82 | "It is not latitude; it is not in…" | pre-release | flows |  |
| 83 | "The `oracle_opinion` member a sender sets has no…" | pre-release | flows |  |
| 84 | "**False kills are the existential failure.** A system…" | pre-release | flows |  |
| 85 | "Hence the trigger discipline: divergence from a *recorded*…" | pre-release | flows |  |
| 86 | "**The model is never the only witness for…" | pre-release | flows |  |
| 87 | "The observation loop: how the running job's tree…" | pre-release | flows |  |
| 88 | "The Defender path: locating `MpCmdRun.exe` across Defender install…" | pre-release | flows |  |
| 89 | "Whether the Oracle's judgment call is synchronous (ask…" | pre-release | flows |  |
| 90 | "The open items above, as the build closed…" | pre-release | flows |  |
| 91 | "**Observation loop (closed).** Each running exec job gets…" | pre-release | flows |  |
| 92 | "Per-sample cost is one walk of the job's…" | pre-release | flows |  |
| 93 | "Correlation rule, as built: the box's own clock…" | pre-release | flows |  |
| 94 | "`resource_pressure` events inside the window are box-level evidence…" | pre-release | flows |  |
| 95 | "Sense alerts are read through the same store…" | pre-release | flows |  |
| 96 | "**What mid-run observation can honestly see (delta).** The…" | pre-release | flows |  |
| 97 | "Writes outside the workdir are not visible mid-run…" | pre-release | flows |  |
| 98 | "The cage's only live report today is its…" | pre-release | flows |  |
| 99 | "**Saturation tells are named constants.** Tree CPU at…" | pre-release | flows |  |
| 100 | "They are divergences for the authority layer, never…" | pre-release | flows |  |
| 101 | "The storm ceiling is the one tunable tripwire…" | pre-release | flows |  |
| 102 | "**Windows sampling, honestly.** Tree membership via a Toolhelp32…" | pre-release | flows |  |
| 103 | "Per-process CPU and working set come from `OpenProcess`…" | pre-release | flows |  |
| 104 | "On every platform, a process that starts and…" | pre-release | flows |  |
| 105 | "**The Defender path (narrowed, still open).** `MpCmdRun.exe` is…" | pre-release | flows |  |
| 106 | "The exit-code mapping (0 = clean, 2 =…" | pre-release | flows |  |
| 107 | "The ClamAV mapping is `clamdscan`'s documented 0/1/2, and…" | pre-release | flows |  |
| 108 | "**The Oracle's call (resolved).** Synchronous at divergence time,…" | pre-release | flows |  |
| 109 | "On timeout or error the Oracle *abstains* —…" | pre-release | flows |  |
| 110 | "An abstention never kills; it is written to…" | pre-release | flows |  |
| 111 | "One call per divergence kind per job, so…" | pre-release | flows |  |
| 112 | "**The final scan (addition).** When a job exits,…" | pre-release | flows |  |
| 113 | "A short job can write a tripping artifact…" | pre-release | flows |  |
| 114 | "The recorded act for a final-scan tripwire is…" | pre-release | flows |  |
| 115 | "The same honesty rule applies to a mid-run…" | pre-release | flows |  |
| 116 | "**The release door.** `--remediation-release <job_id>` is the one…" | pre-release | flows |  |
| 117 | "There is deliberately no second release implementation to…" | pre-release | flows |  |
| 118 | "**The record, as built.** The result member is…" | pre-release | flows |  |
| 119 | "Audit decisions: `acted`, `abstained`, `spared`, `observed`, `released`." | pre-release | flows |  |
| 120 | "The page rides a new DRI trigger (`dri.triggers.remediation`,…" | pre-release | flows |  |
