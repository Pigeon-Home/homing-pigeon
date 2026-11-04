# Findings — docs/steady/reports/known-failures.md

Source: docs/steady/reports/known-failures.md, reviewed at main cbb52068.
Sentence units: 36. Flagged: 1. Categories: pre-release 36, post-release 0.

An archived failure catalogue: an archive warning first, then the reviewer's contract, then 5 entries in symptom, cause, fix, reviewer order, then how to add a 6th. Each entry is a closed chain and the entries connect by the shared format. Unit 7 is the bare label that introduces the format's code block and is flagged as a label, not a sentence; nothing else is flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "**Archived.** This file is kept in `docs/archive/` as…" | pre-release | flows |  |
| 2 | "It is undated and written in the present…" | pre-release | flows |  |
| 3 | "([docs/job-review.md](../job-review.md) points here for the reviewer-pattern format." | pre-release | flows |  |
| 4 | "The Oracle's pre-execution reviewer matches incoming jobs against…" | pre-release | flows |  |
| 5 | "Each entry is a failure that actually happened,…" | pre-release | flows |  |
| 6 | "When you diagnose a new recurring failure, add…" | pre-release | flows |  |
| 7 | "Format for reviewer patterns (`review_patterns_extra` in config):" | pre-release | flagged | A bare label ending in a colon, not a sentence; it introduces the format block without leading into it as prose |
| 8 | "Severity is `info` or `warn`." | pre-release | flows |  |
| 9 | "Patterns are advisory: the job still runs." | pre-release | flows |  |
| 10 | "**Symptom:** every PowerShell job failed immediately on Windows." | pre-release | flows |  |
| 11 | "**Cause:** `powershell -File` refuses a script file without…" | pre-release | flows |  |
| 12 | "**Fix:** the runner now names the staged script…" | pre-release | flows |  |
| 13 | "See `script_filename()`." | pre-release | flows |  |
| 14 | "**Reviewer:** built in — no live pattern needed." | pre-release | flows |  |
| 15 | "Kept here as the format example and a…" | pre-release | flows |  |
| 16 | "**Symptom:** long jobs died at exactly 3600s with…" | pre-release | flows |  |
| 17 | "**Cause:** the runner clamps `timeout_sec` to a maximum…" | pre-release | flows |  |
| 18 | "A job asking for 7200 gets 3600 without…" | pre-release | flows |  |
| 19 | "**Fix:** ask for what you need up to…" | pre-release | flows |  |
| 20 | "**Reviewer:** built in (`timeout_clamped`, info)." | pre-release | flows |  |
| 21 | "**Symptom:** a job fetched a `script_url` or file…" | pre-release | flows |  |
| 22 | "**Cause:** no `sha384` on the download, so there…" | pre-release | flows |  |
| 23 | "**Fix:** pin `script_sha384` / file `sha384` on anything…" | pre-release | flows |  |
| 24 | "**Reviewer:** built in (`script_url_no_integrity`, `file_no_integrity`, info)." | pre-release | flows |  |
| 25 | "**Symptom:** `FileNotFoundError` a few seconds into the run." | pre-release | flows |  |
| 26 | "**Cause:** the script opened a file that was…" | pre-release | flows |  |
| 27 | "**Fix:** list every input file in `files[]`." | pre-release | flows |  |
| 28 | "**Reviewer:** built in (`dangling_file_ref`, warn) — matches quoted…" | pre-release | flows |  |
| 29 | "**Symptom:** job rejected before running: "unsafe file name"." | pre-release | flows |  |
| 30 | "**Cause:** `files[]` entries must be relative; absolute paths…" | pre-release | flows |  |
| 31 | "**Fix:** use relative names." | pre-release | flows |  |
| 32 | "**Reviewer:** built in (`absolute_file_name`, warn)." | pre-release | flows |  |
| 33 | "Diagnose the failure and confirm it recurs." | pre-release | flows |  |
| 34 | "Add a section above (next KF number), with…" | pre-release | flows |  |
| 35 | "If it is script-text-shaped, add a `review_patterns_extra` entry…" | pre-release | flows |  |
| 36 | "If it is job-shape-shaped, propose it as a…" | pre-release | flows |  |
