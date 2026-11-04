# Findings — docs/steady/reports/v3.13.42-coverage-gaps.md

Source: docs/steady/reports/v3.13.42-coverage-gaps.md, reviewed at main 08b61333.
Sentence units: 27. Flagged: 2. Categories: pre-release 27, post-release 0.

A short cycle-6 gaps table with a dense head: what the table is, how the classes are read, and 6 paragraphs of cycle accounting before the stat line. The accounting chains — closures, pins kept live, arms that moved, the dead-by-construction set — each paragraph handing to the next. The non-sentences are the stamp comment (unit 1) and the table's header row (unit 12); the table's data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90 -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "Every function with two or more never-executed statements…" | pre-release | flows |  |
| 3 | "Classes are read from the AST by `runner/tools/coverage_targets.py`:…" | pre-release | flows |  |
| 4 | "Project Platinum (standing orders, queue P) refreshes this…" | pre-release | flows |  |
| 5 | "Cycle 6 closed nine statements gross, five net,…" | pre-release | flows |  |
| 6 | "Two pins the full-suite map does not credit…" | pre-release | flows |  |
| 7 | "Four rarely-hit arms the cycle-5 map showed covered…" | pre-release | flows |  |
| 8 | "Eight more single lines were recorded dead by…" | pre-release | flows |  |
| 9 | "The earlier recorded set stands: `_scan_python`'s second except…" | pre-release | flows |  |
| 10 | "The wire/ rows are the test legs seat's…" | pre-release | flows |  |
| 11 | "statements 99.6% covered, 125 missing of 30283" | pre-release | flows |  |
| 12 | "class \| file:function \| missing \| branches \|…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 13 | "logic \| `extensions/zeek-feed/zeek_feed.py:main` L564 \| 2 (682,688) \|…" | pre-release | flows |  |
| 14 | "logic \| `ops/startup.py:handle_board_mail` L104 \| 2 (166,167) \|…" | pre-release | flows |  |
| 15 | "logic \| `wire/dtlsproto.py:x25519` L157 \| 2 (186,187) \|…" | pre-release | flows |  |
| 16 | "logic \| `wire/transports.py:discover_transport_extensions` L245 \| 2 (285,290) \|…" | pre-release | flows |  |
| 17 | "guard \| `wire/verify.py:verify_body_keyed` L693 \| 2 (717,743) \|…" | pre-release | flows |  |
| 18 | "except \| `guard/extreview.py:_scan_python` L324 \| 3 (332,337,339) \|…" | pre-release | flows |  |
| 19 | "except \| `extensions/pi-health/pi_health.py:_read_throttled` L181 \| 2 (203,204) \|…" | pre-release | flows |  |
| 20 | "except \| `extensions/softflowd-feed/softflowd_feed.py:decode_datagram` L374 \| 2 (401,402) \|…" | pre-release | flows |  |
| 21 | "except \| `extensions/training-watch/training_watch.py:decide` L465 \| 2 (611,612) \|…" | pre-release | flows |  |
| 22 | "except \| `ops/oracle_server.py:make_oracle_server` L25 \| 2 (184,185) \|…" | pre-release | flows |  |
| 23 | "except \| `ops/oracle_server.py:Handler.do_POST` L116 \| 2 (184,185) \|…" | pre-release | flows |  |
| 24 | "except \| `oracle/dri.py:send_telegram` L468 \| 2 (486,487) \|…" | pre-release | flows |  |
| 25 | "except \| `oracle/senses.py:load_alerts` L379 \| 2 (426,427) \|…" | pre-release | flows |  |
| 26 | "platform \| `extensions/pi-health/pi_health.py:_mem_avail_pct_windows` L262 \| 14 (270,271,273,274,286,287,288,290…) \|…" | pre-release | flows |  |
| 27 | "platform \| `oracle/remediation.py:sample_tree_windows` L458 \| 2 (470,483) \|…" | pre-release | flows |  |
