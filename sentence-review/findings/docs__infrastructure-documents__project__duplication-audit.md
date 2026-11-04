# Findings — docs/infrastructure-documents/project/duplication-audit.md

Source: docs/infrastructure-documents/project/duplication-audit.md, reviewed at main cbb52068.
Sentence units: 131. Flagged: 0. Categories: pre-release 131, post-release 0.

The verdicts are 2-sentence bold blocks (units 36-37, 52-53, 95-96, 108-109), recorded as extracted. Units 56-64 are the feed-file list under unit 55's lead-in; each names a file and its duplicated-line count.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Dated 2026-11-03." | pre-release | flows |  |
| 2 | "Measured on main at commit ea94da55, with the…" | pre-release | flows |  |
| 3 | "The full audit output is the project's own…" | pre-release | flows |  |
| 4 | "This is written for whoever arrives next —…" | pre-release | flows |  |
| 5 | "The short version: the duplication here is small,…" | pre-release | flows |  |
| 6 | "Do not "clean it up" on sight." | pre-release | flows |  |
| 7 | "Several of these repetitions are load-bearing." | pre-release | flows |  |
| 8 | "The whole tree is 1,145,913 lines." | pre-release | flows |  |
| 9 | "Python is 327,510 of them, in 599 files." | pre-release | flows |  |
| 10 | "The rest is data and records, not code." | pre-release | flows |  |
| 11 | "Near-duplicate Python (lines sitting in an 8-line block…" | pre-release | flows |  |
| 12 | "That is 3.65% of the whole tree, and…" | pre-release | flows |  |
| 13 | "Tests carry 36,820 of those lines (3.21% of…" | pre-release | flows |  |
| 14 | "Production carries 4,962 (0.43% of the tree; 6.0%…" | pre-release | flows |  |
| 15 | "Exact copies: 340 lines beyond the first copy,…" | pre-release | flows |  |
| 16 | "Latent code: the orphan scan found 0 unreferenced…" | pre-release | flows |  |
| 17 | "The one not-run tree is the airgap harness…" | pre-release | flows |  |
| 18 | "How to read the near-duplicate number honestly: it…" | pre-release | flows |  |
| 19 | "The window method counts boilerplate, and it counts…" | pre-release | flows |  |
| 20 | "It also misses clones shorter than 8 lines…" | pre-release | flows |  |
| 21 | "Treat 41,782 as "no more than this," and…" | pre-release | flows |  |
| 22 | "`runner/tests/airgap/interesting.example/OVERVIEW.py` is 20,071 lines, and 11,167 of them…" | pre-release | flows |  |
| 23 | "It is the single largest contributor to the…" | pre-release | flows |  |
| 24 | "What it is: a held-cases fixture for the…" | pre-release | flows |  |
| 25 | "The file's own header states the recipe: 1,801…" | pre-release | flows |  |
| 26 | "Why it repeats: the repetition is the fixture." | pre-release | flows |  |
| 27 | "A held set only works as a control…" | pre-release | flows |  |
| 28 | "The harvest deliberately excludes exact copies, so what…" | pre-release | flows |  |
| 29 | "The honest cost: if a harvested case's source…" | pre-release | flows |  |
| 30 | "That is not drift to repair; it is…" | pre-release | flows |  |
| 31 | "The real risk is the opposite one —…" | pre-release | flows |  |
| 32 | "Remedy: leave it." | pre-release | flows |  |
| 33 | "Lines saved by the correct remedy: 0." | pre-release | flows |  |
| 34 | "Regenerating the fixture from sources on demand would…" | pre-release | flows |  |
| 35 | "If anything is worth adding, it is a…" | pre-release | flows |  |
| 36 | "**Verdict: deliberate." | pre-release | flows |  |
| 37 | "Should stay.**" | pre-release | flows |  |
| 38 | "`runner/tests/test_doc_default_divergences.py` is 47,293 lines, the largest Python file…" | pre-release | flows |  |
| 39 | "5,479 of its lines repeat blocks found elsewhere…" | pre-release | flows |  |
| 40 | "What it is: a museum of known bugs,…" | pre-release | flows |  |
| 41 | "The file header is explicit: each test asserts…" | pre-release | flows |  |
| 42 | "It passes only when the bug described in…" | pre-release | flows |  |
| 43 | "Each exhibit carries the same 4-part docstring scaffold…" | pre-release | flows |  |
| 44 | "Why it repeats: each exhibit has to stand…" | pre-release | flows |  |
| 45 | "A reader (human or SI) who opens the…" | pre-release | flows |  |
| 46 | "The scaffold repetition is documentation, and the arrange-act…" | pre-release | flows |  |
| 47 | "The honest cost: a change to the shared…" | pre-release | flows |  |
| 48 | "Factoring the scaffolding into helpers would make the…" | pre-release | flows |  |
| 49 | "Remedy: leave it." | pre-release | flows |  |
| 50 | "A helper layer for the temporary-directory and store/read-back…" | pre-release | flows |  |
| 51 | "Lines saved by the correct remedy: 0." | pre-release | flows |  |
| 52 | "**Verdict: deliberate." | pre-release | flows |  |
| 53 | "Should stay.**" | pre-release | flows |  |
| 54 | "This is the family worth an arriving system's…" | pre-release | flows |  |
| 55 | "What repeats: 9 sibling senses under `runner/extensions/` are…" | pre-release | flows |  |
| 56 | "`falco-feed/falco_feed.py`: 292 of 538 lines duplicated" | pre-release | flows |  |
| 57 | "`suricata-feed/suricata_feed.py`: 298 of 580" | pre-release | flows |  |
| 58 | "`zeek-feed/zeek_feed.py`: 207 of 702" | pre-release | flows |  |
| 59 | "`failed-login-watch/failed_login_watch.py`: 201 of 507" | pre-release | flows |  |
| 60 | "`osquery-feed/osquery_feed.py`: 199 of 610" | pre-release | flows |  |
| 61 | "`wazuh-feed/wazuh_feed.py`: 185 of 535" | pre-release | flows |  |
| 62 | "`job-watcher/job_watcher.py`: 148 of 771" | pre-release | flows |  |
| 63 | "`sysmon-feed/sysmon_feed.py`: 139 of 631" | pre-release | flows |  |
| 64 | "`log-sentinel/log_sentinel.py`: 131 of 513" | pre-release | flows |  |
| 65 | "The strongest pairs share over 100 windows (falco…" | pre-release | flows |  |
| 66 | "The same skeleton also runs through the other…" | pre-release | flows |  |
| 67 | "The shared skeleton, function by function:" | pre-release | flows |  |
| 68 | "`_is_number(value)` — the finite-number tunable check, identical everywhere…" | pre-release | flows |  |
| 69 | "Timestamp parsing — `_parse_ts()` plus the same fraction/offset…" | pre-release | flows |  |
| 70 | "`parse_event(line)` — one line of the source log…" | pre-release | flows |  |
| 71 | "`read_new_events(paths, reader_state)` — the log tailer: a state…" | pre-release | flows |  |
| 72 | "`_fresh_state()`, `_clean_state(state)`, `_clean_event(entry)` — state hygiene between passes." | pre-release | flows |  |
| 73 | "`decide(readings, manifest, state)` — the pure decision: readings…" | pre-release | flows |  |
| 74 | "`_deliver_local(alerts, args)` — about 50 lines, identical except…" | pre-release | flows |  |
| 75 | "Notably, it does not re-implement signing: it imports…" | pre-release | flows |  |
| 76 | "`main()` — the same argument surface everywhere: `--readings…" | pre-release | flows |  |
| 77 | "What differs per feed is everything that should:…" | pre-release | flows |  |
| 78 | "Why it exists: each extension is a self-contained…" | pre-release | flows |  |
| 79 | "The senses are examples as much as features:…" | pre-release | flows |  |
| 80 | "That is a real design value, and it…" | pre-release | flows |  |
| 81 | "The honest cost: the skeleton is maintained 9+…" | pre-release | flows |  |
| 82 | "A bug fixed in 1 tailer — say…" | pre-release | flows |  |
| 83 | "This is exactly how parallel implementations drift: 1…" | pre-release | flows |  |
| 84 | "Of all the families in this document, this…" | pre-release | flows |  |
| 85 | "The remedies, honestly priced:" | pre-release | flows |  |
| 86 | "**A shared base module** (a feedkit the senses…" | pre-release | flows |  |
| 87 | "Saves roughly 1,500 to 1,800 of the measured…" | pre-release | flows |  |
| 88 | "Cost: an extension folder is no longer standalone…" | pre-release | flows |  |
| 89 | "**Generate the feeds from 1 template.** Keeps the…" | pre-release | flows |  |
| 90 | "This tree currently checks in 0 generated files,…" | pre-release | flows |  |
| 91 | "**Keep the copies; guard them like the signers.**…" | pre-release | flows |  |
| 92 | "Saves 0 lines and removes the actual risk,…" | pre-release | flows |  |
| 93 | "Recommendation: remedy 3 first." | pre-release | flows |  |
| 94 | "Remedy 1 becomes the right answer only if…" | pre-release | flows |  |
| 95 | "**Verdict: a real defect (unguarded hand-carried copies), with…" | pre-release | flows |  |
| 96 | "Guard the copies; do not merge them blindly.**" | pre-release | flows |  |
| 97 | "`runner/cloud/send_job.py` (the cloud-side helper an SI runs) and…" | pre-release | flows |  |
| 98 | "A 3rd implementation of the signing step, `sign_envelope()`,…" | pre-release | flows |  |
| 99 | "The secret-strength check in send_job.py likewise mirrors `runner/guard/security.py`." | pre-release | flows |  |
| 100 | "Why it repeats: these are independent implementations of…" | pre-release | flows |  |
| 101 | "The code says so, in terms an arriving…" | pre-release | flows |  |
| 102 | "Where sharing was safe, it has already been…" | pre-release | flows |  |
| 103 | "And the suite cross-exercises the pair: `runner/tests/security_parity.py` signs…" | pre-release | flows |  |
| 104 | "The honest cost, stated plainly because the comments…" | pre-release | flows |  |
| 105 | "A canonicalization difference that slipped the tests would…" | pre-release | flows |  |
| 106 | "Remedy: leave it, and keep the parity tests…" | pre-release | flows |  |
| 107 | "Merging the 2 sides into 1 shared signer…" | pre-release | flows |  |
| 108 | "**Verdict: deliberate, security-bearing." | pre-release | flows |  |
| 109 | "Should stay.**" | pre-release | flows |  |
| 110 | "Everything else the audit names, briefly:" | pre-release | flows |  |
| 111 | "**Ordinary test boilerplate.** After families 1 and 2,…" | pre-release | flows |  |
| 112 | "The densest files are fuzz and intake tests…" | pre-release | flows |  |
| 113 | "Remedy: none globally." | pre-release | flows |  |
| 114 | "Factor a file when its own repetition starts…" | pre-release | flows |  |
| 115 | "**`runner/tools/de_dust_corpus.py`: 173 duplicated lines of 11,894 (about 1.5%).**…" | pre-release | flows |  |
| 116 | "Below any reasonable action threshold; leave it." | pre-release | flows |  |
| 117 | "**Vendored upstream code: 30 files, 23,265 lines** under…" | pre-release | flows |  |
| 118 | "Copied by definition, but these are pinned live…" | pre-release | flows |  |
| 119 | "Leave them; the pin test is the guard." | pre-release | flows |  |
| 120 | "**The exact copies (340 lines)** are 339 lines…" | pre-release | flows |  |
| 121 | "Each upstream folder carries its own license because…" | pre-release | flows |  |
| 122 | "Leave them." | pre-release | flows |  |
| 123 | "For the next maintainer or SI system deciding…" | pre-release | flows |  |
| 124 | "**Do first:** guard the feed-extension skeleton (family 3,…" | pre-release | flows |  |
| 125 | "It is the only family where repetition can…" | pre-release | flows |  |
| 126 | "**Leave alone:** the OVERVIEW fixture, the divergence exhibits,…" | pre-release | flows |  |
| 127 | "Their repetition is the mechanism — a frozen…" | pre-release | flows |  |
| 128 | "Deduplicating any of them makes the tree smaller…" | pre-release | flows |  |
| 129 | "**The standing limit:** duplicate or latent code stays…" | pre-release | flows |  |
| 130 | "The current measure is 3.65% near-duplicate (upper bound)…" | pre-release | flows |  |
| 131 | "The limit is a tripwire, not a target:…" | pre-release | flows |  |
