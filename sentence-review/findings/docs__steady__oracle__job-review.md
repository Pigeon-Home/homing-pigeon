# Findings — docs/steady/oracle/job-review.md

Source: docs/steady/oracle/job-review.md, reviewed at main 16957c7d.
Sentence units: 33. Flagged: 2. Categories: pre-release 33, post-release 0.

How the Oracle's per-job review works: the 2 tiers, the notes table, and operator patterns. The prose connects throughout; the table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The Oracle is always on." | pre-release | flows |  |
| 2 | "So it might as well read the job…" | pre-release | flows |  |
| 3 | "`review_job()` inspects each verified job after the signature…" | pre-release | flows |  |
| 4 | "It returns notes about likely failures: things that…" | pre-release | flows |  |
| 5 | "The notes are attached to the result as…" | pre-release | flows |  |
| 6 | "The review is **advisory, never a gate**." | pre-release | flows |  |
| 7 | "The job runs regardless, because the Oracle can…" | pre-release | flows |  |
| 8 | "Policy ("should this run") stays with the judge;…" | pre-release | flows |  |
| 9 | "Two tiers, split by whether the check needs…" | pre-release | flows |  |
| 10 | "**Metadata tier** needs no content access: job shape,…" | pre-release | flows |  |
| 11 | "It works even when job bodies are encrypted." | pre-release | flows |  |
| 12 | "**Content tier** reads the script text: known-failure patterns…" | pre-release | flows |  |
| 13 | "Under per-job encryption it needs the decrypt credential…" | pre-release | flows |  |
| 14 | "The Oracle reads what the runner legitimately decrypted." | pre-release | flows |  |
| 15 | "The notes ride in the already-HMAC-signed result message,…" | pre-release | flows |  |
| 16 | "The Oracle is an authenticated party with an…" | pre-release | flows |  |
| 17 | "A dedicated Oracle signing key is listed in…" | pre-release | flows |  |
| 18 | "| id | tier | severity | what…" | pre-release | flagged | A table header row — structure, not a sentence |
| 19 | "|----|------|----------|-----------------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 20 | "| no_script_source | metadata | warn | neither…" | pre-release | flows |  |
| 21 | "| script_url_no_integrity | metadata | info | `script_url`…" | pre-release | flows |  |
| 22 | "| file_no_integrity | metadata | info | file…" | pre-release | flows |  |
| 23 | "| absolute_file_name | metadata | warn | absolute…" | pre-release | flows |  |
| 24 | "| interpreter_not_list | metadata | warn | interpreter…" | pre-release | flows |  |
| 25 | "| shebang_platform_mismatch | metadata | warn | `#!/bin/bash`…" | pre-release | flows |  |
| 26 | "| timeout_clamped | metadata | info | `timeout_sec`…" | pre-release | flows |  |
| 27 | "| dangling_file_ref | content | warn | script…" | pre-release | flows |  |
| 28 | "| review_scan_truncated | metadata | info | script…" | pre-release | flows |  |
| 29 | "| review_config_error | metadata | warn | an…" | pre-release | flows |  |
| 30 | "Operator patterns go in `review_patterns_extra` (see `docs/archive/known-failures.md` for…" | pre-release | flows |  |
| 31 | "Every diagnosed recurring failure gets its pattern written…" | pre-release | flows |  |
| 32 | "Filing alone changes no matching: the reviewer matches…" | pre-release | flows |  |
| 33 | "The Oracle gets smarter the way an on-call…" | pre-release | flows |  |
