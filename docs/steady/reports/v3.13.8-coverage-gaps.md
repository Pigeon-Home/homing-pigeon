# Coverage gaps, 3.13.8 (Platinum baseline)

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

Every function with two or more never-executed statements in the full
suite on main at 933dbf4b (Linux, Python 3.13, statement coverage by the
stdlib tracer; see coverage.md for how this differs from the CI figure).
Classes are read from the AST by `runner/tools/coverage_targets.py`:
`logic` is the main flow, `guard` one early refusal, `except` a handler,
`platform` code for another OS, `shadowed` a def rebound later.
Project Platinum (standing orders, queue P) refreshes this table each cycle.

statements 98.8% covered, 356 missing of 28986

| class | file:function | missing | branches | args |
|---|---|---:|---:|---|
| logic | `hosting/httpdoor.py:UrllibHttp.request` L64 | 19 (66,67,68,69,70,71,72,73…) | 0 | method, url, headers, body, timeout |
| logic | `hosting/cli.py:main` L286 | 17 (293,294,295,296,297,298,299,300…) | 0 | argv |
| logic | `runner.py:_sweep_channel_refusals` L1981 | 9 (1991,1997,2013,2014,2041,2043,2045,2053…) | 0 | base_dir, cfg, names |
| logic | `wire/dtlsproto.py:_RecordSealer.open` L432 | 9 (446,450,454,455,456,457,460,464…) | 0 | epoch, record |
| logic | `wire/dtlsproto.py:_split_records` L355 | 6 (371,375,378,386,390,391) | 0 | data |
| logic | `hosting/billing.py:handle_stripe_event` L205 | 5 (213,215,239,242,249) | 0 | ledger, payload, sig_header, secret, now |
| logic | `hosting/cli.py:cmd_status` L116 | 5 (123,124,128,129,130) | 0 | args, http |
| logic | `ops/queries.py:handle_query_mail` L22 | 5 (62,63,64,65,135) | 0 | cfg, imap, smtp, seq, raw, subject, secrets, opts, base_dir, seen |
| logic | `ops/startup.py:handle_board_mail` L104 | 5 (127,128,129,166,167) | 0 | cfg, imap, smtp, seq, raw, subject, board, secrets, opts, base_dir |
| logic | `wire/protocol_v2.py:platform_facts` L131 | 5 (146,147,149,150,152) | 0 |  |
| logic | `runner.py:undeliver_stash` L1688 | 4 (1695,1699,1711,1712) | 0 | base_dir, skey, reason |
| logic | `runner.py:_keep_original_result` L1948 | 4 (1954,1957,1965,1966) | 0 | base_dir, rec, secrets |
| logic | `transport_extensions/queues/__main__.py:main` L213 | 4 (217,218,241,244) | 0 | argv, opener, passes |
| logic | `ops/extsources.py:status` L2165 | 3 (2179,2184,2186) | 0 | base_dir |
| logic | `ops/install.py:_import_atomicio` L46 | 3 (59,60,61) | 0 |  |
| logic | `oracle/learning.py:feature_keys` L163 | 3 (173,178,184) | 0 | facts |
| logic | `runner.py:_refresh_log_settings` L3016 | 3 (3022,3023,3024) | 0 | cfg, base_dir |
| logic | `cloud/send_job.py:cmd_new` L243 | 2 (315,317) | 0 | args |
| logic | `guard/extreview.py:apply` L586 | 2 (612,613) | 0 | cfg, base_dir, registry |
| logic | `ops/install.py:merge_config_blob` L1671 | 2 (1688,1690) | 0 | cfg_path, spec |
| logic | `ops/live.py:_runner` L17 | 2 (22,23) | 0 |  |
| logic | `ops/main.py:main` L17 | 2 (26,302) | 0 |  |
| logic | `runner.py:_delivery_audit` L1618 | 2 (1620,1625) | 0 | base_dir, decision, reason, job_id, cfg |
| logic | `runner.py:process_transport_message` L4808 | 2 (4862,4863) | 0 | cfg, base_dir, seen, secrets, key_policies, subject, body_text, opts, transport |
| logic | `runner.py:rollback` L4861 | 2 (4862,4863) | 0 | added |
| logic | `runner.py:run_inspect` L5023 | 2 (5054,5055) | 0 | cfg, args |
| logic | `transport_extensions/email/__main__.py:_permanent` L64 | 2 (69,71) | 0 | exc |
| logic | `wire/dtlsproto.py:x25519` L157 | 2 (186,187) | 0 | scalar, u_bytes |
| logic | `wire/dtlsproto.py:DtlsServerCore._feed_record` L1524 | 2 (1549,1550) | 0 | record, addr, now |
| logic | `wire/transports.py:discover_transport_extensions` L245 | 2 (285,290) | 0 | cfg, base_dir, log, event_sink |
| guard | `ops/cli.py:_transports_arg` L23 | 3 (34,35,39) | 0 | text |
| guard | `wire/protocol_v2.py:validate` L271 | 3 (307,310,312) | 0 | obj |
| guard | `guard/extreview.py:_review_entry` L402 | 2 (408,414) | 0 | manifest, folder, findings, shipped |
| guard | `hosting/cli.py:_provider` L65 | 2 (68,73) | 0 | name, token, http, app |
| guard | `hosting/cli.py:cmd_redeploy` L149 | 2 (158,163) | 0 | args, http, sleep, new_secret |
| guard | `runner.py:_record_payload` L1928 | 2 (1939,1946) | 0 | rec, secrets |
| guard | `runner.py:_sweep_workspace` L2522 | 2 (2536,2546) | 0 | work, root, when |
| guard | `transport_extensions/queues/__main__.py:QueueClient.pull` L99 | 2 (109,114) | 0 | max_jobs |
| guard | `wire/dtlsproto.py:_parse_extensions` L285 | 2 (288,293) | 0 | data, offset |
| guard | `wire/verify.py:_estimate_secret_entropy` L514 | 2 (514,515) | 0 | secret |
| guard | `wire/verify.py:_secret_pattern_reason` L517 | 2 (517,518) | 0 | secret |
| guard | `wire/verify.py:validate_shared_secret` L520 | 2 (520,521) | 0 | secret |
| guard | `wire/verify.py:verify_body_keyed` L693 | 2 (717,743) | 0 | body_text, secrets |
| except | `cloud/send_job.py:post_to_queue` L334 | 4 (363,364,366,367) | 0 | url, envelope, token_env, opener |
| except | `hosting/billing.py:Ledger.save` L83 | 4 (96,97,99,100) | 0 |  |
| except | `hosting/inventory.py:Inventory.save` L42 | 4 (55,56,58,59) | 0 |  |
| except | `guard/extreview.py:_scan_python` L324 | 2 (337,339) | 0 | rel, text, observed, findings, signals_in_code |
| except | `ops/extensions.py:load_extensions` L351 | 2 (392,393) | 0 | ext_dir, kinds |
| except | `runner.py:_stash_move` L1606 | 2 (1614,1616) | 0 | base_dir, skey, folder |
| except | `runner.py:deliver_stash` L1635 | 2 (1666,1669) | 0 | base_dir, skey, sender, cfg, now |
| platform | `extensions/pi-health/pi_health.py:_mem_avail_pct_windows` L262 | 13 (270,271,273,274,286,287,288,290…) | 0 |  |
| platform | `oracle/remediation.py:sample_tree_windows` L458 | 2 (470,483) | 0 | root_pid |
