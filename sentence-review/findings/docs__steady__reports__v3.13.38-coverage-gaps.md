# Findings — docs/steady/reports/v3.13.38-coverage-gaps.md

Source: docs/steady/reports/v3.13.38-coverage-gaps.md, reviewed at main cbb52068.
Sentence units: 25. Flagged: 1. Categories: pre-release 24, post-release 1.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Every function with two or more never-executed statements…" | pre-release | flows |  |
| 2 | "Classes are read from the AST by `runner/tools/coverage_targets.py`:…" | pre-release | flows |  |
| 3 | "Project Platinum (standing orders, queue P) refreshes this…" | pre-release | flows |  |
| 4 | "Cycle 5 closed 40 statements and 39 branch…" | pre-release | flows |  |
| 5 | "The one live row is execute_job's script-shape refusal…" | post-release | flows |  |
| 6 | "Every other row is recorded dead, defensive, platform,…" | pre-release | flows |  |
| 7 | "Five more single lines were recorded dead by…" | pre-release | flows |  |
| 8 | "The wire/ rows are the test legs seat's…" | pre-release | flows |  |
| 9 | "statements 99.6% covered, 130 missing of 30283" | pre-release | flows |  |
| 10 | "class ; file:function ; missing ; branches ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 11 | "logic ; `ops/exec.py:execute_job` L225 ; 4 (346,491,492,493) ;…" | pre-release | flows |  |
| 12 | "logic ; `ops/startup.py:handle_board_mail` L104 ; 2 (166,167) ;…" | pre-release | flows |  |
| 13 | "logic ; `wire/dtlsproto.py:x25519` L157 ; 2 (186,187) ;…" | pre-release | flows |  |
| 14 | "logic ; `wire/transports.py:discover_transport_extensions` L245 ; 2 (285,290) ;…" | pre-release | flows |  |
| 15 | "except ; `guard/extreview.py:_scan_python` L324 ; 3 (332,337,339) ;…" | pre-release | flows |  |
| 16 | "except ; `extensions/pi-health/pi_health.py:_read_throttled` L181 ; 2 (203,204) ;…" | pre-release | flows |  |
| 17 | "except ; `extensions/softflowd-feed/softflowd_feed.py:decode_datagram` L374 ; 2 (401,402) ;…" | pre-release | flows |  |
| 18 | "except ; `extensions/training-watch/training_watch.py:decide` L465 ; 2 (611,612) ;…" | pre-release | flows |  |
| 19 | "except ; `ops/oracle_server.py:make_oracle_server` L25 ; 2 (184,185) ;…" | pre-release | flows |  |
| 20 | "except ; `ops/oracle_server.py:Handler.do_POST` L116 ; 2 (184,185) ;…" | pre-release | flows |  |
| 21 | "except ; `oracle/dri.py:send_telegram` L468 ; 2 (486,487) ;…" | pre-release | flows |  |
| 22 | "except ; `oracle/senses.py:load_alerts` L379 ; 2 (426,427) ;…" | pre-release | flows |  |
| 23 | "except ; `wire/protocol_v2.py:store_answer` L395 ; 2 (424,425) ;…" | pre-release | flows |  |
| 24 | "platform ; `extensions/pi-health/pi_health.py:_mem_avail_pct_windows` L262 ; 14 (270,271,273,274,286,287,288,290…) ;…" | pre-release | flows |  |
| 25 | "platform ; `oracle/remediation.py:sample_tree_windows` L458 ; 2 (470,483) ;…" | pre-release | flows |  |
