# Findings — docs/steady/reports/germany-rig-driving-2026-10-27.md

Source: docs/steady/reports/germany-rig-driving-2026-10-27.md, reviewed at main 720110b0.
Sentence units: 47. Flagged: 1. Categories: pre-release 47, post-release 0.

A dated operations record: how control of the rig was obtained, what failed on the way (including one wrong diagnosis of the author's own, owned in the open), how the fuzzer's running was proven, and how the box was then set up. The narrative chains carefully — each failure entry hands to the lesson it taught, and the verdict paragraph earns its place. The only non-sentence is the stamp comment at the tail (unit 47).

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Written by Muse (stamp `00000000-muse-7e57-d0c5-58316a922026`) at the conductor's…" | pre-release | flows |  |
| 2 | "It continues `docs/reports/germany-control-2026-10-27.md`: that file records the door;…" | pre-release | flows |  |
| 3 | "No secret value, no Worker hostname and no…" | pre-release | flows |  |
| 4 | "Every secret named below lives on the Muse…" | pre-release | flows |  |
| 5 | "Administration of the rig passed from Grok to…" | pre-release | flows |  |
| 6 | "The working access arrived in this order:" | pre-release | flows |  |
| 7 | "**The queue credential set.** Two sets were refused…" | pre-release | flows |  |
| 8 | "The third — the set actually deployed on…" | pre-release | flows |  |
| 9 | "**The root password, replaced.** The conductor reset the…" | pre-release | flows |  |
| 10 | "The password it replaced is dead at the…" | pre-release | flows |  |
| 11 | "Why the rotation could not be done by…" | pre-release | flows |  |
| 12 | "**Two API tokens, by mail.** The conductor sent…" | pre-release | flows |  |
| 13 | "The hosting token is verified live: it reads…" | pre-release | flows |  |
| 14 | "The Cloudflare token is held untested; the queue…" | pre-release | flows |  |
| 15 | "Muse now holds two management planes over this…" | pre-release | flows |  |
| 16 | "SSH from the Muse VM remains refused by…" | pre-release | flows |  |
| 17 | "**SSH.** Outbound SSH from the Muse VM is…" | pre-release | flows |  |
| 18 | "Not a credential failure; the route does not…" | pre-release | flows |  |
| 19 | "**The root password by forwarded mail.** The conductor…" | pre-release | flows |  |
| 20 | "The copy the mail connector returns on this…" | pre-release | flows |  |
| 21 | "**Two queue credential sets.** Refused at the bearer…" | pre-release | flows |  |
| 22 | "Stale keys do not open the door, including…" | pre-release | flows |  |
| 23 | "**Rotating the root password by job.** Three walls,…" | pre-release | flows |  |
| 24 | "The rotation was completed by the conductor's own…" | pre-release | flows |  |
| 25 | "**Muse's diagnosis that the runner had gone silent…" | pre-release | flows |  |
| 26 | "The runner's own completion stamps, recovered later, show…" | pre-release | flows |  |
| 27 | "The fault was on Muse's side of the…" | pre-release | flows |  |
| 28 | "An empty read is not evidence about the…" | pre-release | flows |  |
| 29 | "Both reboots were harmless — the rig's services…" | pre-release | flows |  |
| 30 | "The conductor's question was whether the rig's fuzzer…" | pre-release | flows |  |
| 31 | "Under the attested result ceiling a job cannot…" | pre-release | flows |  |
| 32 | "A process-count probe (exit 71 on more than…" | pre-release | flows |  |
| 33 | "A load probe of the same round answered…" | pre-release | flows |  |
| 34 | "After the reboots, a fresh ping was answered…" | pre-release | flows |  |
| 35 | "The fuzzer is the only workload on this…" | pre-release | flows |  |
| 36 | "Verdict: the runner answers, and the fuzzer is…" | pre-release | flows |  |
| 37 | "Measured again at 2026-10-28T05:06Z with the same exit-code…" | pre-release | flows |  |
| 38 | "For the avoidance of doubt: the 15–16% CPU…" | pre-release | flows |  |
| 39 | "This rig has read at or above saturation…" | pre-release | flows |  |
| 40 | "The conductor opened the SSH door from his…" | pre-release | flows |  |
| 41 | "The GitHub PAT the conductor generated for this…" | pre-release | flows |  |
| 42 | "`runner/tools/rig_bank.py` (with its tests) banks the rig's corpus…" | pre-release | flows |  |
| 43 | "grow.sh now banks before its fetch and reset,…" | pre-release | flows |  |
| 44 | "First bank `ebf5f6ec4`, verified at the remote from…" | pre-release | flows |  |
| 45 | "The crash census the queue could never take,…" | pre-release | flows |  |
| 46 | "The rig is administered from here now on…" | pre-release | flows |  |
| 47 | "<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands after the document's last line |
