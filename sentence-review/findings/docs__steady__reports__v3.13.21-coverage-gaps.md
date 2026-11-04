# Findings — docs/steady/reports/v3.13.21-coverage-gaps.md

Source: docs/steady/reports/v3.13.21-coverage-gaps.md, reviewed at main e2a8e8e2.
Sentence units: 63. Flagged: 2. Categories: pre-release 63, post-release 0.

A generated coverage-gaps snapshot for 3.13.21: the uncovered lines by module in 1 table with a short frame. The frame connects; the table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90 -->" | pre-release | flows |  |
| 2 | "Every function with two or more never-executed statements…" | pre-release | flows |  |
| 3 | "Classes are read from the AST by `runner/tools/coverage_targets.py`:…" | pre-release | flows |  |
| 4 | "Project Platinum (standing orders, queue P) refreshes this…" | pre-release | flows |  |
| 5 | "Cycle 1 closed 36 statements and 18 branch…" | pre-release | flows |  |
| 6 | "statements 99.1% covered, 258 missing of 30278" | pre-release | flows |  |
| 7 | "| class | file:function | missing | branches…" | pre-release | flagged | A table header row — structure, not a sentence |
| 8 | "|---|---|---:|---:|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 9 | "| logic | `ops/extsources.py:status` L2198 | 5 (2211,2212,2216,2217,2219)…" | pre-release | flows |  |
| 10 | "| logic | `transport_extensions/queues/__main__.py:main` L213 | 5 (217,218,240,241,244)…" | pre-release | flows |  |
| 11 | "| logic | `ops/install.py:_import_atomicio` L46 | 3 (59,60,61)…" | pre-release | flows |  |
| 12 | "| logic | `ops/install.py:merge_config_blob` L1671 | 3 (1687,1688,1690)…" | pre-release | flows |  |
| 13 | "| logic | `cloud/send_job.py:cmd_new` L243 | 2 (315,317)…" | pre-release | flows |  |
| 14 | "| logic | `guard/extreview.py:apply` L586 | 2 (612,613)…" | pre-release | flows |  |
| 15 | "| logic | `ops/live.py:_runner` L17 | 2 (22,23)…" | pre-release | flows |  |
| 16 | "| logic | `ops/main.py:main` L17 | 2 (26,302)…" | pre-release | flows |  |
| 17 | "| logic | `ops/startup.py:handle_board_mail` L104 | 2 (166,167)…" | pre-release | flows |  |
| 18 | "| logic | `runner.py:process_transport_message` L4808 | 2 (4862,4863)…" | pre-release | flows |  |
| 19 | "| logic | `runner.py:rollback` L4861 | 2 (4862,4863)…" | pre-release | flows |  |
| 20 | "| logic | `runner.py:run_inspect` L5023 | 2 (5054,5055)…" | pre-release | flows |  |
| 21 | "| logic | `transport_extensions/email/__main__.py:_permanent` L64 | 2 (69,71)…" | pre-release | flows |  |
| 22 | "| logic | `wire/dtlsproto.py:x25519` L157 | 2 (186,187)…" | pre-release | flows |  |
| 23 | "| logic | `wire/dtlsproto.py:_split_records` L355 | 2 (390,391)…" | pre-release | flows |  |
| 24 | "| logic | `wire/dtlsproto.py:DtlsServerCore._feed_record` L1524 | 2 (1549,1550)…" | pre-release | flows |  |
| 25 | "| logic | `wire/transports.py:discover_transport_extensions` L245 | 2 (285,290)…" | pre-release | flows |  |
| 26 | "| guard | `ops/cli.py:_transports_arg` L23 | 3 (34,35,39)…" | pre-release | flows |  |
| 27 | "| guard | `runner.py:_sweep_workspace` L2522 | 3 (2535,2536,2546)…" | pre-release | flows |  |
| 28 | "| guard | `transport_extensions/queues/__main__.py:QueueClient.pull` L99 | 3 (108,109,114)…" | pre-release | flows |  |
| 29 | "| guard | `wire/protocol_v2.py:validate` L271 | 3 (307,310,312)…" | pre-release | flows |  |
| 30 | "| guard | `guard/extreview.py:_review_entry` L402 | 2 (408,414)…" | pre-release | flows |  |
| 31 | "| guard | `hosting/cli.py:_provider` L65 | 2 (68,73)…" | pre-release | flows |  |
| 32 | "| guard | `hosting/cli.py:cmd_redeploy` L149 | 2 (158,163)…" | pre-release | flows |  |
| 33 | "| guard | `wire/verify.py:verify_body_keyed` L693 | 2 (717,743)…" | pre-release | flows |  |
| 34 | "| except | `cloud/send_job.py:post_to_queue` L334 | 6 (362,363,364,365,366,367)…" | pre-release | flows |  |
| 35 | "| except | `guard/extreview.py:_scan_python` L324 | 3 (332,337,339)…" | pre-release | flows |  |
| 36 | "| except | `extensions/pi-health/pi_health.py:_read_throttled` L181 | 2 (203,204)…" | pre-release | flows |  |
| 37 | "| except | `extensions/softflowd-feed/softflowd_feed.py:decode_datagram` L374 | 2 (401,402)…" | pre-release | flows |  |
| 38 | "| except | `extensions/training-watch/training_watch.py:decide` L465 | 2 (611,612)…" | pre-release | flows |  |
| 39 | "| except | `guard/extreview.py:_under` L391 | 2 (395,396)…" | pre-release | flows |  |
| 40 | "| except | `guard/filenames.py:validate_file_name` L101 | 2 (110,111)…" | pre-release | flows |  |
| 41 | "| except | `hosting/bootstrap.py:hosted_config_from_env` L94 | 2 (108,109)…" | pre-release | flows |  |
| 42 | "| except | `hosting/digitalocean.py:DigitalOcean.destroy` L90 | 2 (94,95)…" | pre-release | flows |  |
| 43 | "| except | `hosting/fly.py:FlyMachines.destroy` L112 | 2 (117,118)…" | pre-release | flows |  |
| 44 | "| except | `hosting/github_actions.py:GitHubActions._call` L90 | 2 (100,101)…" | pre-release | flows |  |
| 45 | "| except | `hosting/hetzner.py:HetznerCloud.destroy` L86 | 2 (90,91)…" | pre-release | flows |  |
| 46 | "| except | `hosting/httpdoor.py:UrllibHttp.request` L64 | 2 (86,87)…" | pre-release | flows |  |
| 47 | "| except | `hosting/inventory.py:Inventory.save` L42 | 2 (57,58)…" | pre-release | flows |  |
| 48 | "| except | `ops/mail.py:handle_mail` L27 | 2 (655,656)…" | pre-release | flows |  |
| 49 | "| except | `ops/oracle_server.py:make_oracle_server` L25 | 2 (184,185)…" | pre-release | flows |  |
| 50 | "| except | `ops/oracle_server.py:Handler.do_POST` L116 | 2 (184,185)…" | pre-release | flows |  |
| 51 | "| except | `oracle/dri.py:evaluate_page_triggers` L255 | 2 (314,315)…" | pre-release | flows |  |
| 52 | "| except | `oracle/dri.py:_one` L311 | 2 (314,315)…" | pre-release | flows |  |
| 53 | "| except | `oracle/dri.py:send_telegram` L468 | 2 (486,487)…" | pre-release | flows |  |
| 54 | "| except | `oracle/senses.py:load_alerts` L379 | 2 (426,427)…" | pre-release | flows |  |
| 55 | "| except | `runner.py:_stash_rewrite` L1599 | 2 (1602,1603)…" | pre-release | flows |  |
| 56 | "| except | `runner.py:deliver_stash` L1635 | 2 (1666,1669)…" | pre-release | flows |  |
| 57 | "| except | `runner.py:_stash_fail_sent` L2067 | 2 (2079,2080)…" | pre-release | flows |  |
| 58 | "| except | `runner.py:_staged_dest` L2462 | 2 (2498,2499)…" | pre-release | flows |  |
| 59 | "| except | `runner.py:_bounce_of` L4279 | 2 (4291,4292)…" | pre-release | flows |  |
| 60 | "| except | `transport_extensions/channel.py:refuse_result` L152 | 2 (170,171)…" | pre-release | flows |  |
| 61 | "| except | `transport_extensions/queues/__main__.py:QueueClient._request` L81 | 2 (95,96)…" | pre-release | flows |  |
| 62 | "| platform | `extensions/pi-health/pi_health.py:_mem_avail_pct_windows` L262 | 14 (270,271,273,274,286,287,288,290…)…" | pre-release | flows |  |
| 63 | "| platform | `oracle/remediation.py:sample_tree_windows` L458 | 2 (470,483)…" | pre-release | flows |  |
