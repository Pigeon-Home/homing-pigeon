# Findings — docs/steady/reports/v3.13.30-coverage-gaps.md

Source: docs/steady/reports/v3.13.30-coverage-gaps.md, reviewed at main e2a8e8e2.
Sentence units: 26. Flagged: 2. Categories: pre-release 26, post-release 0.

A generated coverage-gaps snapshot for 3.13.30: 1 table with a short frame. The frame connects; the table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90 -->" | pre-release | flows |  |
| 2 | "Every function with two or more never-executed statements…" | pre-release | flows |  |
| 3 | "Classes are read from the AST by `runner/tools/coverage_targets.py`:…" | pre-release | flows |  |
| 4 | "Project Platinum (standing orders, queue P) refreshes this…" | pre-release | flows |  |
| 5 | "Cycle 4 closed 15 statements and 6 branch…" | pre-release | flows |  |
| 6 | "One live row remains at this threshold --…" | pre-release | flows |  |
| 7 | "Every other row is recorded dead, defensive, platform,…" | pre-release | flows |  |
| 8 | "The wire/ rows are the test legs seat's…" | pre-release | flows |  |
| 9 | "statements 99.4% covered, 170 missing of 30283" | pre-release | flows |  |
| 10 | "| class | file:function | missing | branches…" | pre-release | flagged | A table header row — structure, not a sentence |
| 11 | "|---|---|---:|---:|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 12 | "| logic | `extensions/port-watch/port_watch.py:main` L341 | 3 (400,403,406)…" | pre-release | flows |  |
| 13 | "| logic | `ops/startup.py:handle_board_mail` L104 | 2 (166,167)…" | pre-release | flows |  |
| 14 | "| logic | `wire/dtlsproto.py:x25519` L157 | 2 (186,187)…" | pre-release | flows |  |
| 15 | "| logic | `wire/transports.py:discover_transport_extensions` L245 | 2 (285,290)…" | pre-release | flows |  |
| 16 | "| guard | `wire/verify.py:verify_body_keyed` L693 | 2 (717,743)…" | pre-release | flows |  |
| 17 | "| except | `guard/extreview.py:_scan_python` L324 | 3 (332,337,339)…" | pre-release | flows |  |
| 18 | "| except | `extensions/pi-health/pi_health.py:_read_throttled` L181 | 2 (203,204)…" | pre-release | flows |  |
| 19 | "| except | `extensions/softflowd-feed/softflowd_feed.py:decode_datagram` L374 | 2 (401,402)…" | pre-release | flows |  |
| 20 | "| except | `extensions/training-watch/training_watch.py:decide` L465 | 2 (611,612)…" | pre-release | flows |  |
| 21 | "| except | `ops/oracle_server.py:make_oracle_server` L25 | 2 (184,185)…" | pre-release | flows |  |
| 22 | "| except | `ops/oracle_server.py:Handler.do_POST` L116 | 2 (184,185)…" | pre-release | flows |  |
| 23 | "| except | `oracle/dri.py:send_telegram` L468 | 2 (486,487)…" | pre-release | flows |  |
| 24 | "| except | `oracle/senses.py:load_alerts` L379 | 2 (426,427)…" | pre-release | flows |  |
| 25 | "| platform | `extensions/pi-health/pi_health.py:_mem_avail_pct_windows` L262 | 14 (270,271,273,274,286,287,288,290…)…" | pre-release | flows |  |
| 26 | "| platform | `oracle/remediation.py:sample_tree_windows` L458 | 2 (470,483)…" | pre-release | flows |  |
