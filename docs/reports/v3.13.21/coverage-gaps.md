# Coverage gaps, 3.13.21 (Platinum cycle 1)

<!-- Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90 -->

Every function with two or more never-executed statements in the full
suite as measured on this rig at db3bcc46 (Linux, coverage.py run the
way `.github/workflows/coverage.yml` runs it: the `.pth` hook so child
processes count, `--rcfile=.github/coveragerc`, combine, json).
Classes are read from the AST by `runner/tools/coverage_targets.py`:
`logic` is the main flow, `guard` one early refusal, `except` a handler,
`platform` code for another OS, `shadowed` a def rebound later.
Project Platinum (standing orders, queue P) refreshes this table each
cycle. Cycle 1 closed 36 statements and 18 branch arcs against the
cycle baseline (99.0% / 294 missing at 90445244); `wire/` was covered
the same day by stamp 40000e00's `test_platinum_wire.py` and shows
here only where this rig's tree predates that module.

statements 99.1% covered, 258 missing of 30278

| class | file:function | missing | branches | args |
|---|---|---:|---:|---|
| logic | `ops/extsources.py:status` L2198 | 5 (2211,2212,2216,2217,2219) | 1 | base_dir |
| logic | `transport_extensions/queues/__main__.py:main` L213 | 5 (217,218,240,241,244) | 2 | argv, opener, passes |
| logic | `ops/install.py:_import_atomicio` L46 | 3 (59,60,61) | 3 |  |
| logic | `ops/install.py:merge_config_blob` L1671 | 3 (1687,1688,1690) | 1 | cfg_path, spec |
| logic | `cloud/send_job.py:cmd_new` L243 | 2 (315,317) | 3 | args |
| logic | `guard/extreview.py:apply` L586 | 2 (612,613) | 1 | cfg, base_dir, registry |
| logic | `ops/live.py:_runner` L17 | 2 (22,23) | 1 |  |
| logic | `ops/main.py:main` L17 | 2 (26,302) | 11 |  |
| logic | `ops/startup.py:handle_board_mail` L104 | 2 (166,167) | 1 | cfg, imap, smtp, seq, raw, subject, board, secrets, opts, base_dir |
| logic | `runner.py:process_transport_message` L4808 | 2 (4862,4863) | 3 | cfg, base_dir, seen, secrets, key_policies, subject, body_text, opts, transport |
| logic | `runner.py:rollback` L4861 | 2 (4862,4863) | 2 | added |
| logic | `runner.py:run_inspect` L5023 | 2 (5054,5055) | 1 | cfg, args |
| logic | `transport_extensions/email/__main__.py:_permanent` L64 | 2 (69,71) | 3 | exc |
| logic | `wire/dtlsproto.py:x25519` L157 | 2 (186,187) | 1 | scalar, u_bytes |
| logic | `wire/dtlsproto.py:_split_records` L355 | 2 (390,391) | 1 | data |
| logic | `wire/dtlsproto.py:DtlsServerCore._feed_record` L1524 | 2 (1549,1550) | 2 | record, addr, now |
| logic | `wire/transports.py:discover_transport_extensions` L245 | 2 (285,290) | 4 | cfg, base_dir, log, event_sink |
| guard | `ops/cli.py:_transports_arg` L23 | 3 (34,35,39) | 4 | text |
| guard | `runner.py:_sweep_workspace` L2522 | 3 (2535,2536,2546) | 1 | work, root, when |
| guard | `transport_extensions/queues/__main__.py:QueueClient.pull` L99 | 3 (108,109,114) | 2 | max_jobs |
| guard | `wire/protocol_v2.py:validate` L271 | 3 (307,310,312) | 3 | obj |
| guard | `guard/extreview.py:_review_entry` L402 | 2 (408,414) | 4 | manifest, folder, findings, shipped |
| guard | `hosting/cli.py:_provider` L65 | 2 (68,73) | 2 | name, token, http, app |
| guard | `hosting/cli.py:cmd_redeploy` L149 | 2 (158,163) | 2 | args, http, sleep, new_secret |
| guard | `wire/verify.py:verify_body_keyed` L693 | 2 (717,743) | 2 | body_text, secrets |
| except | `cloud/send_job.py:post_to_queue` L334 | 6 (362,363,364,365,366,367) | 0 | url, envelope, token_env, opener |
| except | `guard/extreview.py:_scan_python` L324 | 3 (332,337,339) | 1 | rel, text, observed, findings, signals_in_code |
| except | `extensions/pi-health/pi_health.py:_read_throttled` L181 | 2 (203,204) | 0 |  |
| except | `extensions/softflowd-feed/softflowd_feed.py:decode_datagram` L374 | 2 (401,402) | 0 | data, templates, now, stats |
| except | `extensions/training-watch/training_watch.py:decide` L465 | 2 (611,612) | 0 | readings, manifest, state |
| except | `guard/extreview.py:_under` L391 | 2 (395,396) | 0 | path, folder |
| except | `guard/filenames.py:validate_file_name` L101 | 2 (110,111) | 0 | name |
| except | `hosting/bootstrap.py:hosted_config_from_env` L94 | 2 (108,109) | 1 | cfg_path, environ, install |
| except | `hosting/digitalocean.py:DigitalOcean.destroy` L90 | 2 (94,95) | 0 | machine_id |
| except | `hosting/fly.py:FlyMachines.destroy` L112 | 2 (117,118) | 0 | machine_id |
| except | `hosting/github_actions.py:GitHubActions._call` L90 | 2 (100,101) | 0 | method, path, body, what |
| except | `hosting/hetzner.py:HetznerCloud.destroy` L86 | 2 (90,91) | 0 | machine_id |
| except | `hosting/httpdoor.py:UrllibHttp.request` L64 | 2 (86,87) | 0 | method, url, headers, body, timeout |
| except | `hosting/inventory.py:Inventory.save` L42 | 2 (57,58) | 0 |  |
| except | `ops/mail.py:handle_mail` L27 | 2 (655,656) | 7 | cfg, imap, smtp, seq, raw, base_dir, seen, secrets, opts, key_policies |
| except | `ops/oracle_server.py:make_oracle_server` L25 | 2 (184,185) | 1 | cfg, host, port, base_dir |
| except | `ops/oracle_server.py:Handler.do_POST` L116 | 2 (184,185) | 0 |  |
| except | `oracle/dri.py:evaluate_page_triggers` L255 | 2 (314,315) | 2 | dcfg, base_dir, since_ts, now |
| except | `oracle/dri.py:_one` L311 | 2 (314,315) | 0 | rec |
| except | `oracle/dri.py:send_telegram` L468 | 2 (486,487) | 0 | bot_token, chat_id, text |
| except | `oracle/senses.py:load_alerts` L379 | 2 (426,427) | 0 | base_dir, sensor, severity_floor, since, until, limit |
| except | `runner.py:_stash_rewrite` L1599 | 2 (1602,1603) | 0 | base_dir, skey, rec |
| except | `runner.py:deliver_stash` L1635 | 2 (1666,1669) | 1 | base_dir, skey, sender, cfg, now |
| except | `runner.py:_stash_fail_sent` L2067 | 2 (2079,2080) | 0 | base_dir, skey, rec, reason, cfg |
| except | `runner.py:_staged_dest` L2462 | 2 (2498,2499) | 0 | work, name, root |
| except | `runner.py:_bounce_of` L4279 | 2 (4291,4292) | 0 | subject, raw |
| except | `transport_extensions/channel.py:refuse_result` L152 | 2 (170,171) | 0 | channel, fname, reason |
| except | `transport_extensions/queues/__main__.py:QueueClient._request` L81 | 2 (95,96) | 0 | method, path, body, content_type |
| platform | `extensions/pi-health/pi_health.py:_mem_avail_pct_windows` L262 | 14 (270,271,273,274,286,287,288,290…) | 5 |  |
| platform | `oracle/remediation.py:sample_tree_windows` L458 | 2 (470,483) | 2 | root_pid |
