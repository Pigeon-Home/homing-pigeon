# Findings — docs/steady/reports/v3.13.29-coverage-gaps.md

Source: docs/steady/reports/v3.13.29-coverage-gaps.md, reviewed at main 720110b0.
Sentence units: 29. Flagged: 2. Categories: pre-release 29, post-release 0.

A coverage-gaps table with a prose head: what the table lists, how the classes are read, who refreshes it, and what the last cycle closed. The prose chain is clean and the summary line (unit 8) hands straight into the table. The table's rows are counted as units and flow as records under the rule the head states; its header row (unit 9) is structure. Unit 1 is the file's stamp comment, not a sentence.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90 -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "Every function with two or more never-executed statements…" | pre-release | flows |  |
| 3 | "Classes are read from the AST by `runner/tools/coverage_targets.py`:…" | pre-release | flows |  |
| 4 | "Project Platinum (standing orders, queue P) refreshes this…" | pre-release | flows |  |
| 5 | "Cycle 3 closed 36 statements and 15 branch…" | pre-release | flows |  |
| 6 | "Of the rows below, six are recorded here…" | pre-release | flows |  |
| 7 | "The wire/ rows are the test legs seat's…" | pre-release | flows |  |
| 8 | "statements 99.4% covered, 185 missing of 30283" | pre-release | flows |  |
| 9 | "class \| file:function \| missing \| branches \|…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 10 | "logic \| `cloud/send_job.py:cmd_new` L266 \| 6 (345,346,347,348,349,350) \|…" | pre-release | flows |  |
| 11 | "logic \| `cloud/send_dtls.py:main` L159 \| 3 (242,243,244) \|…" | pre-release | flows |  |
| 12 | "logic \| `extensions/osquery-feed/osquery_feed.py:main` L470 \| 2 (590,596) \|…" | pre-release | flows |  |
| 13 | "logic \| `guard/extreview.py:apply` L586 \| 2 (612,613) \|…" | pre-release | flows |  |
| 14 | "logic \| `ops/startup.py:handle_board_mail` L104 \| 2 (166,167) \|…" | pre-release | flows |  |
| 15 | "logic \| `runner.py:run_inspect` L5027 \| 2 (5058,5059) \|…" | pre-release | flows |  |
| 16 | "logic \| `wire/dtlsproto.py:x25519` L157 \| 2 (186,187) \|…" | pre-release | flows |  |
| 17 | "logic \| `wire/transports.py:discover_transport_extensions` L245 \| 2 (285,290) \|…" | pre-release | flows |  |
| 18 | "guard \| `wire/verify.py:verify_body_keyed` L693 \| 2 (717,743) \|…" | pre-release | flows |  |
| 19 | "except \| `guard/extreview.py:_scan_python` L324 \| 3 (332,337,339) \|…" | pre-release | flows |  |
| 20 | "except \| `extensions/pi-health/pi_health.py:_read_throttled` L181 \| 2 (203,204) \|…" | pre-release | flows |  |
| 21 | "except \| `extensions/softflowd-feed/softflowd_feed.py:decode_datagram` L374 \| 2 (401,402) \|…" | pre-release | flows |  |
| 22 | "except \| `extensions/training-watch/training_watch.py:decide` L465 \| 2 (611,612) \|…" | pre-release | flows |  |
| 23 | "except \| `hosting/inventory.py:Inventory.save` L42 \| 2 (57,58) \|…" | pre-release | flows |  |
| 24 | "except \| `ops/oracle_server.py:make_oracle_server` L25 \| 2 (184,185) \|…" | pre-release | flows |  |
| 25 | "except \| `ops/oracle_server.py:Handler.do_POST` L116 \| 2 (184,185) \|…" | pre-release | flows |  |
| 26 | "except \| `oracle/dri.py:send_telegram` L468 \| 2 (486,487) \|…" | pre-release | flows |  |
| 27 | "except \| `oracle/senses.py:load_alerts` L379 \| 2 (426,427) \|…" | pre-release | flows |  |
| 28 | "platform \| `extensions/pi-health/pi_health.py:_mem_avail_pct_windows` L262 \| 14 (270,271,273,274,286,287,288,290…) \|…" | pre-release | flows |  |
| 29 | "platform \| `oracle/remediation.py:sample_tree_windows` L458 \| 2 (470,483) \|…" | pre-release | flows |  |
