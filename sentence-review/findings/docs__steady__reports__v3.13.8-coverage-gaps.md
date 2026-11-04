# Findings — docs/steady/reports/v3.13.8-coverage-gaps.md

Source: docs/steady/reports/v3.13.8-coverage-gaps.md, reviewed at main cbb52068.
Sentence units: 57. Flagged: 1. Categories: pre-release 57, post-release 0.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Every function with two or more never-executed statements…" | pre-release | flows |  |
| 2 | "Classes are read from the AST by `runner/tools/coverage_targets.py`:…" | pre-release | flows |  |
| 3 | "Project Platinum (standing orders, queue P) refreshes this…" | pre-release | flows |  |
| 4 | "statements 98.8% covered, 356 missing of 28986" | pre-release | flows |  |
| 5 | "class ; file:function ; missing ; branches ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 6 | "logic ; `hosting/httpdoor.py:UrllibHttp.request` L64 ; 19 (66,67,68,69,70,71,72,73…) ;…" | pre-release | flows |  |
| 7 | "logic ; `hosting/cli.py:main` L286 ; 17 (293,294,295,296,297,298,299,300…) ;…" | pre-release | flows |  |
| 8 | "logic ; `runner.py:_sweep_channel_refusals` L1981 ; 9 (1991,1997,2013,2014,2041,2043,2045,2053…) ;…" | pre-release | flows |  |
| 9 | "logic ; `wire/dtlsproto.py:_RecordSealer.open` L432 ; 9 (446,450,454,455,456,457,460,464…) ;…" | pre-release | flows |  |
| 10 | "logic ; `wire/dtlsproto.py:_split_records` L355 ; 6 (371,375,378,386,390,391) ;…" | pre-release | flows |  |
| 11 | "logic ; `hosting/billing.py:handle_stripe_event` L205 ; 5 (213,215,239,242,249) ;…" | pre-release | flows |  |
| 12 | "logic ; `hosting/cli.py:cmd_status` L116 ; 5 (123,124,128,129,130) ;…" | pre-release | flows |  |
| 13 | "logic ; `ops/queries.py:handle_query_mail` L22 ; 5 (62,63,64,65,135) ;…" | pre-release | flows |  |
| 14 | "logic ; `ops/startup.py:handle_board_mail` L104 ; 5 (127,128,129,166,167) ;…" | pre-release | flows |  |
| 15 | "logic ; `wire/protocol_v2.py:platform_facts` L131 ; 5 (146,147,149,150,152) ;…" | pre-release | flows |  |
| 16 | "logic ; `runner.py:undeliver_stash` L1688 ; 4 (1695,1699,1711,1712) ;…" | pre-release | flows |  |
| 17 | "logic ; `runner.py:_keep_original_result` L1948 ; 4 (1954,1957,1965,1966) ;…" | pre-release | flows |  |
| 18 | "logic ; `transport_extensions/queues/__main__.py:main` L213 ; 4 (217,218,241,244) ;…" | pre-release | flows |  |
| 19 | "logic ; `ops/extsources.py:status` L2165 ; 3 (2179,2184,2186) ;…" | pre-release | flows |  |
| 20 | "logic ; `ops/install.py:_import_atomicio` L46 ; 3 (59,60,61) ;…" | pre-release | flows |  |
| 21 | "logic ; `oracle/learning.py:feature_keys` L163 ; 3 (173,178,184) ;…" | pre-release | flows |  |
| 22 | "logic ; `runner.py:_refresh_log_settings` L3016 ; 3 (3022,3023,3024) ;…" | pre-release | flows |  |
| 23 | "logic ; `cloud/send_job.py:cmd_new` L243 ; 2 (315,317) ;…" | pre-release | flows |  |
| 24 | "logic ; `guard/extreview.py:apply` L586 ; 2 (612,613) ;…" | pre-release | flows |  |
| 25 | "logic ; `ops/install.py:merge_config_blob` L1671 ; 2 (1688,1690) ;…" | pre-release | flows |  |
| 26 | "logic ; `ops/live.py:_runner` L17 ; 2 (22,23) ;…" | pre-release | flows |  |
| 27 | "logic ; `ops/main.py:main` L17 ; 2 (26,302) ;…" | pre-release | flows |  |
| 28 | "logic ; `runner.py:_delivery_audit` L1618 ; 2 (1620,1625) ;…" | pre-release | flows |  |
| 29 | "logic ; `runner.py:process_transport_message` L4808 ; 2 (4862,4863) ;…" | pre-release | flows |  |
| 30 | "logic ; `runner.py:rollback` L4861 ; 2 (4862,4863) ;…" | pre-release | flows |  |
| 31 | "logic ; `runner.py:run_inspect` L5023 ; 2 (5054,5055) ;…" | pre-release | flows |  |
| 32 | "logic ; `transport_extensions/email/__main__.py:_permanent` L64 ; 2 (69,71) ;…" | pre-release | flows |  |
| 33 | "logic ; `wire/dtlsproto.py:x25519` L157 ; 2 (186,187) ;…" | pre-release | flows |  |
| 34 | "logic ; `wire/dtlsproto.py:DtlsServerCore._feed_record` L1524 ; 2 (1549,1550) ;…" | pre-release | flows |  |
| 35 | "logic ; `wire/transports.py:discover_transport_extensions` L245 ; 2 (285,290) ;…" | pre-release | flows |  |
| 36 | "guard ; `ops/cli.py:_transports_arg` L23 ; 3 (34,35,39) ;…" | pre-release | flows |  |
| 37 | "guard ; `wire/protocol_v2.py:validate` L271 ; 3 (307,310,312) ;…" | pre-release | flows |  |
| 38 | "guard ; `guard/extreview.py:_review_entry` L402 ; 2 (408,414) ;…" | pre-release | flows |  |
| 39 | "guard ; `hosting/cli.py:_provider` L65 ; 2 (68,73) ;…" | pre-release | flows |  |
| 40 | "guard ; `hosting/cli.py:cmd_redeploy` L149 ; 2 (158,163) ;…" | pre-release | flows |  |
| 41 | "guard ; `runner.py:_record_payload` L1928 ; 2 (1939,1946) ;…" | pre-release | flows |  |
| 42 | "guard ; `runner.py:_sweep_workspace` L2522 ; 2 (2536,2546) ;…" | pre-release | flows |  |
| 43 | "guard ; `transport_extensions/queues/__main__.py:QueueClient.pull` L99 ; 2 (109,114) ;…" | pre-release | flows |  |
| 44 | "guard ; `wire/dtlsproto.py:_parse_extensions` L285 ; 2 (288,293) ;…" | pre-release | flows |  |
| 45 | "guard ; `wire/verify.py:_estimate_secret_entropy` L514 ; 2 (514,515) ;…" | pre-release | flows |  |
| 46 | "guard ; `wire/verify.py:_secret_pattern_reason` L517 ; 2 (517,518) ;…" | pre-release | flows |  |
| 47 | "guard ; `wire/verify.py:validate_shared_secret` L520 ; 2 (520,521) ;…" | pre-release | flows |  |
| 48 | "guard ; `wire/verify.py:verify_body_keyed` L693 ; 2 (717,743) ;…" | pre-release | flows |  |
| 49 | "except ; `cloud/send_job.py:post_to_queue` L334 ; 4 (363,364,366,367) ;…" | pre-release | flows |  |
| 50 | "except ; `hosting/billing.py:Ledger.save` L83 ; 4 (96,97,99,100) ;…" | pre-release | flows |  |
| 51 | "except ; `hosting/inventory.py:Inventory.save` L42 ; 4 (55,56,58,59) ;…" | pre-release | flows |  |
| 52 | "except ; `guard/extreview.py:_scan_python` L324 ; 2 (337,339) ;…" | pre-release | flows |  |
| 53 | "except ; `ops/extensions.py:load_extensions` L351 ; 2 (392,393) ;…" | pre-release | flows |  |
| 54 | "except ; `runner.py:_stash_move` L1606 ; 2 (1614,1616) ;…" | pre-release | flows |  |
| 55 | "except ; `runner.py:deliver_stash` L1635 ; 2 (1666,1669) ;…" | pre-release | flows |  |
| 56 | "platform ; `extensions/pi-health/pi_health.py:_mem_avail_pct_windows` L262 ; 13 (270,271,273,274,286,287,288,290…) ;…" | pre-release | flows |  |
| 57 | "platform ; `oracle/remediation.py:sample_tree_windows` L458 ; 2 (470,483) ;…" | pre-release | flows |  |
