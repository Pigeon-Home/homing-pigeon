# Coverage gaps: this measurement

Statements 30412, never executed 143; branches 12026, never taken 311; 98.9% covered overall (shipped code only: runner/ without tests/ and tools/).

## Functions with the most never-executed lines

Lines counted are the function's own, nested functions excluded. Each row is a hunt target: a test that makes these lines run, and asserts what the docs say they do.

| Missed | Of | Function | Never-executed lines |
|---:|---:|---|---|
| 14 | 35 | `runner/extensions/pi-health/pi_health.py:_mem_avail_pct_windows` | 270-271, 273-274, 286-288, 290-296 |
| 2 | 24 | `runner/extensions/pi-health/pi_health.py:_read_throttled` | 203-204 |
| 2 | 30 | `runner/extensions/softflowd-feed/softflowd_feed.py:decode_datagram` | 401-402 |
| 2 | 235 | `runner/extensions/training-watch/training_watch.py:decide` | 611-612 |
| 2 | 11 | `runner/guard/security.py:_rx_subpatterns` | 203, 205 |
| 2 | 97 | `runner/ops/handlers.py:run_variant` | 366-367 |
| 2 | 603 | `runner/ops/mail.py:handle_mail` | 116, 118 |
| 2 | 71 | `runner/ops/oracle_server.py:make_oracle_server.Handler.do_POST` | 184-185 |
| 2 | 76 | `runner/ops/startup.py:handle_board_mail` | 166-167 |
| 2 | 29 | `runner/oracle/dri.py:send_telegram` | 486-487 |
| 2 | 27 | `runner/oracle/remediation.py:sample_tree_windows` | 470, 483 |
| 2 | 64 | `runner/oracle/senses.py:load_alerts` | 426-427 |
| 2 | 33 | `runner/wire/dtlsproto.py:x25519` | 186-187 |
| 2 | 78 | `runner/wire/transports.py:discover_transport_extensions` | 285, 290 |
| 1 | 24 | `runner/cloud/send_job.py:_has_lone_surrogate` | 285 |
| 1 | 22 | `runner/cloud/send_job.py:verify_body` | 262 |
| 1 | 9 | `runner/extensions/job-fuzz/job_fuzz.py:_mut_blank_line` | 391 |
| 1 | 32 | `runner/extensions/sky-watcher/sky_watcher.py:sun_elevation_deg` | 231 |
| 1 | 36 | `runner/guard/sandbox.py:startup_problem` | 73 |
| 1 | 24 | `runner/guard/security.py:_rx_walk` | 230 |
| 1 | 31 | `runner/hosting/cli.py:main` | 316 |
| 1 | 13 | `runner/hosting/fly.py:FlyMachines.ensure_app` | 57 |
| 1 | 279 | `runner/ops/exec.py:execute_job` | 346 |
| 1 | 26 | `runner/ops/extsources.py:_clean_rel_path` | 289 |
| 1 | 68 | `runner/ops/install.py:_setup_fresh_config` | 1122 |
| 1 | 381 | `runner/ops/main.py:main` | 302 |
| 1 | 10 | `runner/oracle/remediation.py:sample_tree_ps` | 558 |
| 1 | 36 | `runner/runner.py:_oracle_instruction_kind` | 1330 |
| 1 | 34 | `runner/runner.py:ask_model` | 774 |
| 1 | 34 | `runner/runner.py:ensure_inference_ready` | 4993 |
| 1 | 22 | `runner/runner.py:load_retained` | 2195 |
| 1 | 7 | `runner/runner.py:save_seen.merge` | 4575 |
| 1 | 20 | `runner/transport_extensions/email/__main__.py:_subject_body` | 61 |
| 1 | 115 | `runner/wire/board.py:Board._offer_unlocked` | 269 |
| 1 | 35 | `runner/wire/dtlsproto.py:DtlsClientCore._on_handshake_bytes` | 1002 |
| 1 | 25 | `runner/wire/dtlsproto.py:_ServerSession._on_handshake_bytes` | 1401 |
| 1 | 9 | `runner/wire/protocol_v2.py:should_ask` | 201 |
| 1 | 47 | `runner/wire/verify.py:_object_start` | 143 |
| 1 | 14 | `runner/wire/verify.py:audience_allows` | 689 |
| 1 | 30 | `runner/wire/verify.py:verify_body` | 210 |
| 1 | 54 | `runner/wire/verify.py:verify_body_keyed` | 730 |

## Modules, least covered first

| Covered | Statements | Missed | Module |
|---:|---:|---:|---|
| 94% | 368 | 23 | `runner/cloud/send_job.py` |
| 94% | 276 | 17 | `runner/extensions/pi-health/pi_health.py` |
| 95% | 210 | 8 | `runner/hosting/cli.py` |
| 95% | 101 | 4 | `runner/ops/cli.py` |
| 96% | 142 | 1 | `runner/transport_extensions/file/__main__.py` |
| 97% | 217 | 1 | `runner/ops/main.py` |
| 97% | 228 | 2 | `runner/ops/handlers.py` |
| 98% | 265 | 3 | `runner/guard/security.py` |
| 98% | 203 | 3 | `runner/wire/oauth.py` |
| 98% | 357 | 2 | `runner/ops/mail.py` |
| 98% | 123 | 2 | `runner/ops/startup.py` |
| 98% | 143 | 1 | `runner/transport_extensions/email/__main__.py` |
| 98% | 394 | 1 | `runner/extensions/job-watcher/job_watcher.py` |
| 99% | 152 | 2 | `runner/ops/oracle_server.py` |
| 99% | 63 | 1 | `runner/hosting/fly.py` |
| 99% | 164 | 1 | `runner/transport_extensions/queues/__main__.py` |
| 99% | 461 | 6 | `runner/wire/verify.py` |
| 99% | 1091 | 4 | `runner/wire/dtlsproto.py` |
| 99% | 236 | 1 | `runner/extensions/cert-sentinel/cert_sentinel.py` |
| 99% | 473 | 2 | `runner/extensions/softflowd-feed/softflowd_feed.py` |
| 99% | 237 | 1 | `runner/extensions/wire-arrivals/wire_arrivals.py` |
| 99% | 3702 | 10 | `runner/runner.py` |
| 99% | 805 | 2 | `runner/extensions/job-fuzz/job_fuzz.py` |
| 99% | 194 | 1 | `runner/extensions/backup-freshness/backup_freshness.py` |
| 99% | 338 | 2 | `runner/extensions/sky-watcher/sky_watcher.py` |
| 99% | 566 | 2 | `runner/wire/transports.py` |
| 99% | 384 | 4 | `runner/oracle/dri.py` |
| 99% | 1426 | 4 | `runner/ops/extsources.py` |
| 99% | 273 | 1 | `runner/extensions/failed-login-watch/failed_login_watch.py` |
| 99% | 287 | 1 | `runner/extensions/log-sentinel/log_sentinel.py` |
| 99% | 138 | 1 | `runner/guard/sandbox.py` |
| 99% | 223 | 1 | `runner/extensions/port-watch/port_watch.py` |
| 99% | 293 | 1 | `runner/extensions/suricata-feed/suricata_feed.py` |
| 99% | 431 | 1 | `runner/extensions/airwaves/airwaves.py` |
| 99% | 312 | 1 | `runner/ops/exec.py` |
| 99% | 233 | 1 | `runner/extensions/aide-feed/aide_feed.py` |
| 99% | 166 | 1 | `runner/extensions/lab-results/lab_results.py` |
| 99% | 249 | 1 | `runner/extensions/service-watch/service_watch.py` |
| 99% | 341 | 1 | `runner/extensions/sysmon-feed/sysmon_feed.py` |
| 99% | 271 | 1 | `runner/extensions/wazuh-feed/wazuh_feed.py` |
| 99% | 278 | 1 | `runner/extensions/falco-feed/falco_feed.py` |
| 99% | 355 | 1 | `runner/extensions/zeek-feed/zeek_feed.py` |
| 99% | 204 | 1 | `runner/extensions/release-drop/release_drop.py` |
| 99% | 290 | 1 | `runner/extensions/osquery-feed/osquery_feed.py` |
| 99% | 288 | 1 | `runner/wire/board.py` |
| 99% | 414 | 3 | `runner/extensions/training-watch/training_watch.py` |
| 99% | 214 | 1 | `runner/extensions/crash-watch/crash_watch.py` |
| 99% | 227 | 1 | `runner/extensions/usb-arrivals/usb_arrivals.py` |
| 99% | 311 | 2 | `runner/oracle/senses.py` |
| 99% | 229 | 1 | `runner/extensions/latency-post/latency_post.py` |
| 99% | 232 | 1 | `runner/extensions/tripwire/tripwire.py` |
| 99% | 249 | 1 | `runner/extensions/resource-sentinel/resource_sentinel.py` |
| 99% | 375 | 1 | `runner/wire/protocol_v2.py` |
| 100% | 903 | 3 | `runner/oracle/remediation.py` |
| 100% | 1907 | 1 | `runner/ops/install.py` |
