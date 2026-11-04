# Findings — docs/steady/reports/v3.13.27-coverage-gaps.md

Source: docs/steady/reports/v3.13.27-coverage-gaps.md, reviewed at main cbb52068.
Sentence units: 51. Flagged: 1. Categories: pre-release 51, post-release 0.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Every function with two or more never-executed statements…" | pre-release | flows |  |
| 2 | "Classes are read from the AST by `runner/tools/coverage_targets.py`:…" | pre-release | flows |  |
| 3 | "Project Platinum (standing orders, queue P) refreshes this…" | pre-release | flows |  |
| 4 | "Cycle 2 closed 29 statements and 10 branch…" | pre-release | flows |  |
| 5 | "Two rows remain, and neither is a target…" | pre-release | flows |  |
| 6 | "statements 99.3% covered, 221 missing of 30278" | pre-release | flows |  |
| 7 | "class ; file:function ; missing ; branches ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 8 | "logic ; `cloud/send_job.py:cmd_new` L243 ; 2 (315,317) ;…" | pre-release | flows |  |
| 9 | "logic ; `extensions/service-watch/service_watch.py:main` L369 ; 2 (431,434) ;…" | pre-release | flows |  |
| 10 | "logic ; `guard/extreview.py:apply` L586 ; 2 (612,613) ;…" | pre-release | flows |  |
| 11 | "logic ; `ops/live.py:_runner` L17 ; 2 (22,23) ;…" | pre-release | flows |  |
| 12 | "logic ; `ops/main.py:main` L17 ; 2 (26,302) ;…" | pre-release | flows |  |
| 13 | "logic ; `ops/startup.py:handle_board_mail` L104 ; 2 (166,167) ;…" | pre-release | flows |  |
| 14 | "logic ; `runner.py:process_transport_message` L4812 ; 2 (4866,4867) ;…" | pre-release | flows |  |
| 15 | "logic ; `runner.py:rollback` L4865 ; 2 (4866,4867) ;…" | pre-release | flows |  |
| 16 | "logic ; `runner.py:run_inspect` L5027 ; 2 (5058,5059) ;…" | pre-release | flows |  |
| 17 | "logic ; `transport_extensions/email/__main__.py:_permanent` L64 ; 2 (69,71) ;…" | pre-release | flows |  |
| 18 | "logic ; `wire/dtlsproto.py:x25519` L157 ; 2 (186,187) ;…" | pre-release | flows |  |
| 19 | "logic ; `wire/transports.py:discover_transport_extensions` L245 ; 2 (285,290) ;…" | pre-release | flows |  |
| 20 | "guard ; `guard/extreview.py:_review_entry` L402 ; 2 (408,414) ;…" | pre-release | flows |  |
| 21 | "guard ; `hosting/cli.py:_provider` L65 ; 2 (68,73) ;…" | pre-release | flows |  |
| 22 | "guard ; `hosting/cli.py:cmd_redeploy` L149 ; 2 (158,163) ;…" | pre-release | flows |  |
| 23 | "guard ; `wire/verify.py:verify_body_keyed` L693 ; 2 (717,743) ;…" | pre-release | flows |  |
| 24 | "except ; `guard/extreview.py:_scan_python` L324 ; 3 (332,337,339) ;…" | pre-release | flows |  |
| 25 | "except ; `extensions/pi-health/pi_health.py:_read_throttled` L181 ; 2 (203,204) ;…" | pre-release | flows |  |
| 26 | "except ; `extensions/softflowd-feed/softflowd_feed.py:decode_datagram` L374 ; 2 (401,402) ;…" | pre-release | flows |  |
| 27 | "except ; `extensions/training-watch/training_watch.py:decide` L465 ; 2 (611,612) ;…" | pre-release | flows |  |
| 28 | "except ; `guard/extreview.py:_under` L391 ; 2 (395,396) ;…" | pre-release | flows |  |
| 29 | "except ; `guard/filenames.py:validate_file_name` L101 ; 2 (110,111) ;…" | pre-release | flows |  |
| 30 | "except ; `hosting/bootstrap.py:hosted_config_from_env` L94 ; 2 (108,109) ;…" | pre-release | flows |  |
| 31 | "except ; `hosting/digitalocean.py:DigitalOcean.destroy` L90 ; 2 (94,95) ;…" | pre-release | flows |  |
| 32 | "except ; `hosting/fly.py:FlyMachines.destroy` L112 ; 2 (117,118) ;…" | pre-release | flows |  |
| 33 | "except ; `hosting/github_actions.py:GitHubActions._call` L90 ; 2 (100,101) ;…" | pre-release | flows |  |
| 34 | "except ; `hosting/hetzner.py:HetznerCloud.destroy` L86 ; 2 (90,91) ;…" | pre-release | flows |  |
| 35 | "except ; `hosting/httpdoor.py:UrllibHttp.request` L64 ; 2 (86,87) ;…" | pre-release | flows |  |
| 36 | "except ; `hosting/inventory.py:Inventory.save` L42 ; 2 (57,58) ;…" | pre-release | flows |  |
| 37 | "except ; `ops/mail.py:handle_mail` L27 ; 2 (655,656) ;…" | pre-release | flows |  |
| 38 | "except ; `ops/oracle_server.py:make_oracle_server` L25 ; 2 (184,185) ;…" | pre-release | flows |  |
| 39 | "except ; `ops/oracle_server.py:Handler.do_POST` L116 ; 2 (184,185) ;…" | pre-release | flows |  |
| 40 | "except ; `oracle/dri.py:evaluate_page_triggers` L255 ; 2 (314,315) ;…" | pre-release | flows |  |
| 41 | "except ; `oracle/dri.py:_one` L311 ; 2 (314,315) ;…" | pre-release | flows |  |
| 42 | "except ; `oracle/dri.py:send_telegram` L468 ; 2 (486,487) ;…" | pre-release | flows |  |
| 43 | "except ; `oracle/senses.py:load_alerts` L379 ; 2 (426,427) ;…" | pre-release | flows |  |
| 44 | "except ; `runner.py:_stash_rewrite` L1599 ; 2 (1602,1603) ;…" | pre-release | flows |  |
| 45 | "except ; `runner.py:deliver_stash` L1635 ; 2 (1666,1669) ;…" | pre-release | flows |  |
| 46 | "except ; `runner.py:_stash_fail_sent` L2071 ; 2 (2083,2084) ;…" | pre-release | flows |  |
| 47 | "except ; `runner.py:_staged_dest` L2466 ; 2 (2502,2503) ;…" | pre-release | flows |  |
| 48 | "except ; `runner.py:_bounce_of` L4283 ; 2 (4295,4296) ;…" | pre-release | flows |  |
| 49 | "except ; `transport_extensions/channel.py:refuse_result` L152 ; 2 (170,171) ;…" | pre-release | flows |  |
| 50 | "platform ; `extensions/pi-health/pi_health.py:_mem_avail_pct_windows` L262 ; 14 (270,271,273,274,286,287,288,290…) ;…" | pre-release | flows |  |
| 51 | "platform ; `oracle/remediation.py:sample_tree_windows` L458 ; 2 (470,483) ;…" | pre-release | flows |  |
