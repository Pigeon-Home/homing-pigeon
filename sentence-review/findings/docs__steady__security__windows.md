# Findings — docs/steady/security/windows.md

Source: docs/steady/security/windows.md, reviewed at main ff2ea758.
Sentence units: 23. Flagged: 0. Categories: pre-release 23, post-release 0.

A short Windows hardening guide: a dedicated local user, what the account needs, and the confinement difference. Connected throughout; nothing is flagged. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The runner installs on Windows as a Scheduled…" | pre-release | flows |  |
| 2 | "The default is SYSTEM: it needs no password…" | pre-release | flows |  |
| 3 | "This page is for when you want less…" | pre-release | flows |  |
| 4 | "Create a local user for the runner (no…" | pre-release | flows |  |
| 5 | "Named (non-SYSTEM) accounts get run level `LIMITED` instead…" | pre-release | flows |  |
| 6 | "Well-known service accounts and gMSA names (ending in…" | pre-release | flows |  |
| 7 | "The account needs:" | pre-release | flows |  |
| 8 | "**Read/write** on the install directory (the runner, its…" | pre-release | flows |  |
| 9 | "**Read** on anything jobs are expected to read;…" | pre-release | flows |  |
| 10 | "Jobs run as this user, so the account…" | pre-release | flows |  |
| 11 | "**Log on as a batch job** (`SeBatchLogonRight`) if…" | pre-release | flows |  |
| 12 | "What the limited account loses: binding privileged ports,…" | pre-release | flows |  |
| 13 | "`os.chmod` cannot set Unix permission bits on Windows." | pre-release | flows |  |
| 14 | "The `config.json` 0600 story from POSIX ("owner read/write…" | pre-release | flows |  |
| 15 | "To lock down `config.json` (which holds the shared…" | pre-release | flows |  |
| 16 | "`/inheritance:r` removes inherited grants; the second line grants…" | pre-release | flows |  |
| 17 | "Verify with `icacls config.json` — no other principal…" | pre-release | flows |  |
| 18 | "The runner's `--posture` check reports the Windows ACL…" | pre-release | flows |  |
| 19 | "There is no bwrap on Windows, so the…" | pre-release | flows |  |
| 20 | "The equivalent containment is the limited account above…" | pre-release | flows |  |
| 21 | "`--posture` reports confinement as not-applicable on Windows rather…" | pre-release | flows |  |
| 22 | "The Scheduled Task itself supports no equivalent of…" | pre-release | flows |  |
| 23 | "The account boundary is the mechanism; keep the…" | pre-release | flows |  |
