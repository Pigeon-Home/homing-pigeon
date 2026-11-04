# Findings — docs/steady/reports/live-2026-10-25-readme.md

Source: docs/steady/reports/live-2026-10-25-readme.md, reviewed at main cbb52068.
Sentence units: 35. Flagged: 0. Categories: pre-release 35, post-release 0.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Real files from a live homing-pigeon system, captured…" | pre-release | flows |  |
| 2 | "The system is the campaign rig: a Linux…" | pre-release | flows |  |
| 3 | "Runner version: **3.12.51**, first start 2026-10-22 19:09, last…" | pre-release | flows |  |
| 4 | "The campaign records (`campaign-results.jsonl.gz`, one record per line…" | pre-release | flows |  |
| 5 | "Modes the rig ran, per the log's startup…" | pre-release | flows |  |
| 6 | "The first two starts on 2026-10-22 show `judge=advisory…" | pre-release | flows |  |
| 7 | "Transports: email in the first era, then **file…" | pre-release | flows |  |
| 8 | "The reports in `audit-report.txt`, `audit-report-since-7d.txt`, and `posture.txt` were…" | pre-release | flows |  |
| 9 | "Both audit reports are empty because this rig…" | pre-release | flows |  |
| 10 | "`rig-facts.txt` holds the rig's `uname -a`, `python3 --version`,…" | pre-release | flows |  |
| 11 | "Per the owner's rule for this capture:" | pre-release | flows |  |
| 12 | "Every email address became `runner@example.test` (the runner's mailbox)…" | pre-release | flows |  |
| 13 | "Test addresses already in the corpus (`@example.com`) were…" | pre-release | flows |  |
| 14 | "Host names became `rig`, user names `runner`, and…" | pre-release | flows |  |
| 15 | "The shared secret and every credential value in…" | pre-release | flows |  |
| 16 | "(The HMAC signatures and `hp_enc` ciphertexts in the…" | pre-release | flows |  |
| 17 | "Lines naming a person were to be dropped;…" | pre-release | flows |  |
| 18 | "The CLI captures had the capture shell's own…" | pre-release | flows |  |
| 19 | "**Owner: rotate the rig's shared secret before its…" | pre-release | flows |  |
| 20 | "`runner.log` is 25,265,682 bytes on the rig." | pre-release | flows |  |
| 21 | "Per the capture rule it is included as…" | pre-release | flows |  |
| 22 | "There are no rotated backups on this rig." | pre-release | flows |  |
| 23 | "These files from the capture list were never…" | pre-release | flows |  |
| 24 | "`oracle.log`, `oracle-briefs.jsonl`, `oracle-chat.jsonl` (the deterministic Oracle wrote no…" | pre-release | flows |  |
| 25 | "`security-audit.jsonl`, its rotation, and `security-audit-counts.json`." | pre-release | flows |  |
| 26 | "`board.json`, a senses alert store, and `retained/`." | pre-release | flows |  |
| 27 | "A v2 answers folder, and question / task-offer…" | pre-release | flows |  |
| 28 | "`daemon.out`, the daemon's shell capture, was not on…" | pre-release | flows |  |
| 29 | "`transport-*.txt.gz` are file-name listings of the transport channel…" | pre-release | flows |  |
| 30 | "`campaign-results.jsonl.gz` holds the loop's records themselves, all of…" | pre-release | flows |  |
| 31 | "`mutation-survivors.txt` was regenerated from the D4 mutation reproduction's…" | pre-release | flows |  |
| 32 | "The capture was first posted as 19,227 record…" | pre-release | flows |  |
| 33 | "Every release snapshot carries every tracked file onto…" | pre-release | flows |  |
| 34 | "`python3 runner/tools/live_capture.py` prints the run's facts; `docs/use/live-examples.md` quotes…" | pre-release | flows |  |
| 35 | "`zcat campaign-results.jsonl.gz \| head -1` reads the first…" | pre-release | flows |  |
