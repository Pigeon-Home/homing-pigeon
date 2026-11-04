# Findings — docs/steady/reports/v3.13.62-coverage-gaps.md

Source: docs/steady/reports/v3.13.62-coverage-gaps.md, reviewed at main e2a8e8e2.
Sentence units: 103. Flagged: 4. Categories: pre-release 103, post-release 0.

A generated coverage-gaps snapshot for 3.13.62: 2 tables with a short frame. The frame connects; the table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Statements 30412, never executed 143; branches 12026, never…" | pre-release | flows |  |
| 2 | "Lines counted are the function's own, nested functions…" | pre-release | flows |  |
| 3 | "Each row is a hunt target: a test…" | pre-release | flows |  |
| 4 | "| Missed | Of | Function | Never-executed…" | pre-release | flagged | A table header row — structure, not a sentence |
| 5 | "|---:|---:|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 6 | "| 14 | 35 | `runner/extensions/pi-health/pi_health.py:_mem_avail_pct_windows` | 270-271,…" | pre-release | flows |  |
| 7 | "| 2 | 24 | `runner/extensions/pi-health/pi_health.py:_read_throttled` | 203-204…" | pre-release | flows |  |
| 8 | "| 2 | 30 | `runner/extensions/softflowd-feed/softflowd_feed.py:decode_datagram` | 401-402…" | pre-release | flows |  |
| 9 | "| 2 | 235 | `runner/extensions/training-watch/training_watch.py:decide` | 611-612…" | pre-release | flows |  |
| 10 | "| 2 | 11 | `runner/guard/security.py:_rx_subpatterns` | 203,…" | pre-release | flows |  |
| 11 | "| 2 | 97 | `runner/ops/handlers.py:run_variant` | 366-367…" | pre-release | flows |  |
| 12 | "| 2 | 603 | `runner/ops/mail.py:handle_mail` | 116,…" | pre-release | flows |  |
| 13 | "| 2 | 71 | `runner/ops/oracle_server.py:make_oracle_server.Handler.do_POST` | 184-185…" | pre-release | flows |  |
| 14 | "| 2 | 76 | `runner/ops/startup.py:handle_board_mail` | 166-167…" | pre-release | flows |  |
| 15 | "| 2 | 29 | `runner/oracle/dri.py:send_telegram` | 486-487…" | pre-release | flows |  |
| 16 | "| 2 | 27 | `runner/oracle/remediation.py:sample_tree_windows` | 470,…" | pre-release | flows |  |
| 17 | "| 2 | 64 | `runner/oracle/senses.py:load_alerts` | 426-427…" | pre-release | flows |  |
| 18 | "| 2 | 33 | `runner/wire/dtlsproto.py:x25519` | 186-187…" | pre-release | flows |  |
| 19 | "| 2 | 78 | `runner/wire/transports.py:discover_transport_extensions` | 285,…" | pre-release | flows |  |
| 20 | "| 1 | 24 | `runner/cloud/send_job.py:_has_lone_surrogate` | 285…" | pre-release | flows |  |
| 21 | "| 1 | 22 | `runner/cloud/send_job.py:verify_body` | 262…" | pre-release | flows |  |
| 22 | "| 1 | 9 | `runner/extensions/job-fuzz/job_fuzz.py:_mut_blank_line` | 391…" | pre-release | flows |  |
| 23 | "| 1 | 32 | `runner/extensions/sky-watcher/sky_watcher.py:sun_elevation_deg` | 231…" | pre-release | flows |  |
| 24 | "| 1 | 36 | `runner/guard/sandbox.py:startup_problem` | 73…" | pre-release | flows |  |
| 25 | "| 1 | 24 | `runner/guard/security.py:_rx_walk` | 230…" | pre-release | flows |  |
| 26 | "| 1 | 31 | `runner/hosting/cli.py:main` | 316…" | pre-release | flows |  |
| 27 | "| 1 | 13 | `runner/hosting/fly.py:FlyMachines.ensure_app` | 57…" | pre-release | flows |  |
| 28 | "| 1 | 279 | `runner/ops/exec.py:execute_job` | 346…" | pre-release | flows |  |
| 29 | "| 1 | 26 | `runner/ops/extsources.py:_clean_rel_path` | 289…" | pre-release | flows |  |
| 30 | "| 1 | 68 | `runner/ops/install.py:_setup_fresh_config` | 1122…" | pre-release | flows |  |
| 31 | "| 1 | 381 | `runner/ops/main.py:main` | 302…" | pre-release | flows |  |
| 32 | "| 1 | 10 | `runner/oracle/remediation.py:sample_tree_ps` | 558…" | pre-release | flows |  |
| 33 | "| 1 | 36 | `runner/runner.py:_oracle_instruction_kind` | 1330…" | pre-release | flows |  |
| 34 | "| 1 | 34 | `runner/runner.py:ask_model` | 774…" | pre-release | flows |  |
| 35 | "| 1 | 34 | `runner/runner.py:ensure_inference_ready` | 4993…" | pre-release | flows |  |
| 36 | "| 1 | 22 | `runner/runner.py:load_retained` | 2195…" | pre-release | flows |  |
| 37 | "| 1 | 7 | `runner/runner.py:save_seen.merge` | 4575…" | pre-release | flows |  |
| 38 | "| 1 | 20 | `runner/transport_extensions/email/__main__.py:_subject_body` | 61…" | pre-release | flows |  |
| 39 | "| 1 | 115 | `runner/wire/board.py:Board._offer_unlocked` | 269…" | pre-release | flows |  |
| 40 | "| 1 | 35 | `runner/wire/dtlsproto.py:DtlsClientCore._on_handshake_bytes` | 1002…" | pre-release | flows |  |
| 41 | "| 1 | 25 | `runner/wire/dtlsproto.py:_ServerSession._on_handshake_bytes` | 1401…" | pre-release | flows |  |
| 42 | "| 1 | 9 | `runner/wire/protocol_v2.py:should_ask` | 201…" | pre-release | flows |  |
| 43 | "| 1 | 47 | `runner/wire/verify.py:_object_start` | 143…" | pre-release | flows |  |
| 44 | "| 1 | 14 | `runner/wire/verify.py:audience_allows` | 689…" | pre-release | flows |  |
| 45 | "| 1 | 30 | `runner/wire/verify.py:verify_body` | 210…" | pre-release | flows |  |
| 46 | "| 1 | 54 | `runner/wire/verify.py:verify_body_keyed` | 730…" | pre-release | flows |  |
| 47 | "| Covered | Statements | Missed | Module…" | pre-release | flagged | A table header row — structure, not a sentence |
| 48 | "|---:|---:|---:|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 49 | "| 94% | 368 | 23 | `runner/cloud/send_job.py`…" | pre-release | flows |  |
| 50 | "| 94% | 276 | 17 | `runner/extensions/pi-health/pi_health.py`…" | pre-release | flows |  |
| 51 | "| 95% | 210 | 8 | `runner/hosting/cli.py`…" | pre-release | flows |  |
| 52 | "| 95% | 101 | 4 | `runner/ops/cli.py`…" | pre-release | flows |  |
| 53 | "| 96% | 142 | 1 | `runner/transport_extensions/file/__main__.py`…" | pre-release | flows |  |
| 54 | "| 97% | 217 | 1 | `runner/ops/main.py`…" | pre-release | flows |  |
| 55 | "| 97% | 228 | 2 | `runner/ops/handlers.py`…" | pre-release | flows |  |
| 56 | "| 98% | 265 | 3 | `runner/guard/security.py`…" | pre-release | flows |  |
| 57 | "| 98% | 203 | 3 | `runner/wire/oauth.py`…" | pre-release | flows |  |
| 58 | "| 98% | 357 | 2 | `runner/ops/mail.py`…" | pre-release | flows |  |
| 59 | "| 98% | 123 | 2 | `runner/ops/startup.py`…" | pre-release | flows |  |
| 60 | "| 98% | 143 | 1 | `runner/transport_extensions/email/__main__.py`…" | pre-release | flows |  |
| 61 | "| 98% | 394 | 1 | `runner/extensions/job-watcher/job_watcher.py`…" | pre-release | flows |  |
| 62 | "| 99% | 152 | 2 | `runner/ops/oracle_server.py`…" | pre-release | flows |  |
| 63 | "| 99% | 63 | 1 | `runner/hosting/fly.py`…" | pre-release | flows |  |
| 64 | "| 99% | 164 | 1 | `runner/transport_extensions/queues/__main__.py`…" | pre-release | flows |  |
| 65 | "| 99% | 461 | 6 | `runner/wire/verify.py`…" | pre-release | flows |  |
| 66 | "| 99% | 1091 | 4 | `runner/wire/dtlsproto.py`…" | pre-release | flows |  |
| 67 | "| 99% | 236 | 1 | `runner/extensions/cert-sentinel/cert_sentinel.py`…" | pre-release | flows |  |
| 68 | "| 99% | 473 | 2 | `runner/extensions/softflowd-feed/softflowd_feed.py`…" | pre-release | flows |  |
| 69 | "| 99% | 237 | 1 | `runner/extensions/wire-arrivals/wire_arrivals.py`…" | pre-release | flows |  |
| 70 | "| 99% | 3702 | 10 | `runner/runner.py`…" | pre-release | flows |  |
| 71 | "| 99% | 805 | 2 | `runner/extensions/job-fuzz/job_fuzz.py`…" | pre-release | flows |  |
| 72 | "| 99% | 194 | 1 | `runner/extensions/backup-freshness/backup_freshness.py`…" | pre-release | flows |  |
| 73 | "| 99% | 338 | 2 | `runner/extensions/sky-watcher/sky_watcher.py`…" | pre-release | flows |  |
| 74 | "| 99% | 566 | 2 | `runner/wire/transports.py`…" | pre-release | flows |  |
| 75 | "| 99% | 384 | 4 | `runner/oracle/dri.py`…" | pre-release | flows |  |
| 76 | "| 99% | 1426 | 4 | `runner/ops/extsources.py`…" | pre-release | flows |  |
| 77 | "| 99% | 273 | 1 | `runner/extensions/failed-login-watch/failed_login_watch.py`…" | pre-release | flows |  |
| 78 | "| 99% | 287 | 1 | `runner/extensions/log-sentinel/log_sentinel.py`…" | pre-release | flows |  |
| 79 | "| 99% | 138 | 1 | `runner/guard/sandbox.py`…" | pre-release | flows |  |
| 80 | "| 99% | 223 | 1 | `runner/extensions/port-watch/port_watch.py`…" | pre-release | flows |  |
| 81 | "| 99% | 293 | 1 | `runner/extensions/suricata-feed/suricata_feed.py`…" | pre-release | flows |  |
| 82 | "| 99% | 431 | 1 | `runner/extensions/airwaves/airwaves.py`…" | pre-release | flows |  |
| 83 | "| 99% | 312 | 1 | `runner/ops/exec.py`…" | pre-release | flows |  |
| 84 | "| 99% | 233 | 1 | `runner/extensions/aide-feed/aide_feed.py`…" | pre-release | flows |  |
| 85 | "| 99% | 166 | 1 | `runner/extensions/lab-results/lab_results.py`…" | pre-release | flows |  |
| 86 | "| 99% | 249 | 1 | `runner/extensions/service-watch/service_watch.py`…" | pre-release | flows |  |
| 87 | "| 99% | 341 | 1 | `runner/extensions/sysmon-feed/sysmon_feed.py`…" | pre-release | flows |  |
| 88 | "| 99% | 271 | 1 | `runner/extensions/wazuh-feed/wazuh_feed.py`…" | pre-release | flows |  |
| 89 | "| 99% | 278 | 1 | `runner/extensions/falco-feed/falco_feed.py`…" | pre-release | flows |  |
| 90 | "| 99% | 355 | 1 | `runner/extensions/zeek-feed/zeek_feed.py`…" | pre-release | flows |  |
| 91 | "| 99% | 204 | 1 | `runner/extensions/release-drop/release_drop.py`…" | pre-release | flows |  |
| 92 | "| 99% | 290 | 1 | `runner/extensions/osquery-feed/osquery_feed.py`…" | pre-release | flows |  |
| 93 | "| 99% | 288 | 1 | `runner/wire/board.py`…" | pre-release | flows |  |
| 94 | "| 99% | 414 | 3 | `runner/extensions/training-watch/training_watch.py`…" | pre-release | flows |  |
| 95 | "| 99% | 214 | 1 | `runner/extensions/crash-watch/crash_watch.py`…" | pre-release | flows |  |
| 96 | "| 99% | 227 | 1 | `runner/extensions/usb-arrivals/usb_arrivals.py`…" | pre-release | flows |  |
| 97 | "| 99% | 311 | 2 | `runner/oracle/senses.py`…" | pre-release | flows |  |
| 98 | "| 99% | 229 | 1 | `runner/extensions/latency-post/latency_post.py`…" | pre-release | flows |  |
| 99 | "| 99% | 232 | 1 | `runner/extensions/tripwire/tripwire.py`…" | pre-release | flows |  |
| 100 | "| 99% | 249 | 1 | `runner/extensions/resource-sentinel/resource_sentinel.py`…" | pre-release | flows |  |
| 101 | "| 99% | 375 | 1 | `runner/wire/protocol_v2.py`…" | pre-release | flows |  |
| 102 | "| 100% | 903 | 3 | `runner/oracle/remediation.py`…" | pre-release | flows |  |
| 103 | "| 100% | 1907 | 1 | `runner/ops/install.py`…" | pre-release | flows |  |
