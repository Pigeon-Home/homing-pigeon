# Coverage gaps: local rig, after

Statements 37937, never executed 322; branches 0, never taken 0; 99.2% covered overall (shipped code only: runner/ without tests/ and tools/).

## Functions with the most never-executed lines

Lines counted are the function's own, nested functions excluded. Each row is a hunt target: a test that makes these lines run, and asserts what the docs say they do.

| Missed | Of | Function | Never-executed lines |
|---:|---:|---|---|
| 31 | 34 | `runner/ops/queries.py:worker_main` | 391-421 |
| 17 | 47 | `runner/ops/queries.py:grep_matches` | 356-365, 373-376, 378, 380, 383 |
| 7 | 19 | `runner/ops/install.py:_import_panic` | 86-88, 97-100 |
| 6 | 21 | `runner/ops/queries.py:_stop_worker` | 272-273, 276-277, 282-283 |
| 5 | 49 | `runner/cloud/send_job.py:cmd_results` | 813-816, 824 |
| 5 | 394 | `runner/ops/main.py:main` | 56, 61, 335-337 |
| 5 | 89 | `runner/runner.py:_sweep_channel_refusals` | 2033-2034, 2086-2088 |
| 4 | 31 | `runner/cloud/send_job.py:_queue_call` | 763-764, 778-779 |
| 4 | 314 | `runner/ops/exec.py:execute_job` | 450-452, 499 |
| 4 | 141 | `runner/ops/install.py:do_check` | 1037-1038, 1055-1056 |
| 4 | 639 | `runner/ops/mail.py:handle_mail` | 141, 143, 374, 376 |
| 4 | 11 | `runner/runner.py:_stash_move` | 1648-1651 |
| 4 | 28 | `runner/runner.py:undeliver_stash` | 1734, 1745-1747 |
| 3 | 117 | `runner/cloud/send_job.py:cmd_new` | 573-575 |
| 3 | 16 | `runner/cloud/send_job.py:cmd_verify` | 706-708 |
| 3 | 22 | `runner/ops/install.py:_name_first_key` | 336-338 |
| 3 | 68 | `runner/ops/install.py:do_install_home` | 1378-1379, 1381 |
| 3 | 16 | `runner/ops/install.py:do_rearm` | 136-138 |
| 3 | 24 | `runner/ops/install.py:merge_config_blob` | 1894-1895, 1897 |
| 3 | 21 | `runner/transport_extensions/queues/__main__.py:QueueClient.pull` | 109-110, 115 |
| 3 | 11 | `runner/transport_extensions/queues/__main__.py:QueuePipe.renew_leases` | 182-184 |
| 2 | 10 | `runner/cloud/send_job.py:_named_key_in` | 656-657 |
| 2 | 24 | `runner/extensions/pi-health/pi_health.py:_read_throttled` | 203-204 |
| 2 | 235 | `runner/extensions/training-watch/training_watch.py:decide` | 611-612 |
| 2 | 52 | `runner/guard/extreview.py:_review_entry` | 408, 414 |
| 2 | 11 | `runner/guard/security.py:_rx_subpatterns` | 226, 228 |
| 2 | 14 | `runner/hosting/fly.py:FlyMachines._machine` | 66, 68 |
| 2 | 20 | `runner/ops/extensions.py:api_refusal` | 304-305 |
| 2 | 71 | `runner/ops/extensions.py:load_extensions` | 392-393 |
| 2 | 142 | `runner/ops/handlers.py:handle_v2_mail` | 182-183 |
| 2 | 14 | `runner/ops/install.py:ensure_panic_word` | 124-125 |
| 2 | 385 | `runner/ops/install.py:main` | 3608, 3667 |
| 2 | 14 | `runner/ops/main.py:_installed_config` | 26-27 |
| 2 | 71 | `runner/ops/oracle_server.py:make_oracle_server.Handler.do_POST` | 184-185 |
| 2 | 142 | `runner/ops/poll.py:poll_once` | 32-33 |
| 2 | 5 | `runner/ops/queries.py:_read_line._read` | 328-329 |
| 2 | 117 | `runner/ops/startup.py:handle_board_mail` | 205-206 |
| 2 | 29 | `runner/oracle/dri.py:send_telegram` | 486-487 |
| 2 | 27 | `runner/oracle/remediation.py:sample_tree_windows` | 470, 483 |
| 2 | 27 | `runner/oracle/review.py:review_job` | 296-297 |

## Modules, least covered first

| Covered | Statements | Missed | Module |
|---:|---:|---:|---|
| 89% | 515 | 59 | `runner/ops/queries.py` |
| 95% | 200 | 10 | `runner/transport_extensions/queues/__main__.py` |
| 96% | 657 | 25 | `runner/wire/verify.py` |
| 96% | 300 | 11 | `runner/hosting/cli.py` |
| 96% | 193 | 7 | `runner/guard/panic.py` |
| 97% | 782 | 27 | `runner/cloud/send_job.py` |
| 97% | 95 | 3 | `runner/hosting/fly.py` |
| 97% | 269 | 7 | `runner/ops/main.py` |
| 98% | 111 | 2 | `runner/ops/poll.py` |
| 98% | 168 | 3 | `runner/transport_extensions/email/__main__.py` |
| 98% | 225 | 4 | `runner/ops/cli.py` |
| 98% | 318 | 5 | `runner/guard/security.py` |
| 99% | 75 | 1 | `runner/hosting/hetzner.py` |
| 99% | 234 | 3 | `runner/wire/oauth.py` |
| 99% | 2414 | 29 | `runner/ops/install.py` |
| 99% | 167 | 2 | `runner/ops/oracle_server.py` |
| 99% | 172 | 2 | `runner/ops/startup.py` |
| 99% | 361 | 4 | `runner/ops/extensions.py` |
| 99% | 184 | 2 | `runner/oracle/review.py` |
| 99% | 506 | 5 | `runner/ops/exec.py` |
| 99% | 459 | 4 | `runner/oracle/dri.py` |
| 99% | 351 | 3 | `runner/extensions/pi-health/pi_health.py` |
| 99% | 1256 | 10 | `runner/wire/dtlsproto.py` |
| 99% | 515 | 4 | `runner/ops/mail.py` |
| 99% | 4191 | 31 | `runner/runner.py` |
| 99% | 556 | 4 | `runner/extensions/training-watch/training_watch.py` |
| 99% | 285 | 2 | `runner/ops/handlers.py` |
| 99% | 163 | 1 | `runner/transport_extensions/file/__main__.py` |
| 99% | 333 | 2 | `runner/extensions/log-sentinel/log_sentinel.py` |
| 99% | 333 | 2 | `runner/oracle/senses.py` |
| 99% | 175 | 1 | `runner/ops/policy.py` |
| 99% | 381 | 2 | `runner/extensions/osquery-feed/osquery_feed.py` |
| 99% | 193 | 1 | `runner/cloud/send_dtls.py` |
| 99% | 194 | 1 | `runner/hosting/billing.py` |
| 100% | 206 | 1 | `runner/wire/mailbox.py` |
| 100% | 1053 | 5 | `runner/extensions/job-fuzz/job_fuzz.py` |
| 100% | 212 | 1 | `runner/extensions/lab-results/lab_results.py` |
| 100% | 434 | 2 | `runner/extensions/sky-watcher/sky_watcher.py` |
| 100% | 468 | 2 | `runner/guard/extreview.py` |
| 100% | 240 | 1 | `runner/extensions/backup-freshness/backup_freshness.py` |
| 100% | 249 | 1 | `runner/extensions/release-drop/release_drop.py` |
| 100% | 257 | 1 | `runner/extensions/crash-watch/crash_watch.py` |
| 100% | 263 | 1 | `runner/extensions/port-watch/port_watch.py` |
| 100% | 278 | 1 | `runner/extensions/latency-post/latency_post.py` |
| 100% | 282 | 1 | `runner/extensions/tripwire/tripwire.py` |
| 100% | 287 | 1 | `runner/extensions/aide-feed/aide_feed.py` |
| 100% | 287 | 1 | `runner/extensions/wire-arrivals/wire_arrivals.py` |
| 100% | 299 | 1 | `runner/extensions/usb-arrivals/usb_arrivals.py` |
| 100% | 306 | 1 | `runner/extensions/service-watch/service_watch.py` |
| 100% | 317 | 1 | `runner/wire/board.py` |
| 100% | 323 | 1 | `runner/extensions/cert-sentinel/cert_sentinel.py` |
| 100% | 335 | 1 | `runner/extensions/resource-sentinel/resource_sentinel.py` |
| 100% | 341 | 1 | `runner/extensions/wazuh-feed/wazuh_feed.py` |
| 100% | 1717 | 5 | `runner/ops/extsources.py` |
| 100% | 688 | 2 | `runner/wire/transports.py` |
| 100% | 346 | 1 | `runner/extensions/failed-login-watch/failed_login_watch.py` |
| 100% | 347 | 1 | `runner/extensions/falco-feed/falco_feed.py` |
| 100% | 1049 | 3 | `runner/oracle/remediation.py` |
| 100% | 388 | 1 | `runner/extensions/suricata-feed/suricata_feed.py` |
| 100% | 415 | 1 | `runner/extensions/sysmon-feed/sysmon_feed.py` |
| 100% | 418 | 1 | `runner/wire/protocol_v2.py` |
| 100% | 452 | 1 | `runner/extensions/zeek-feed/zeek_feed.py` |
| 100% | 507 | 1 | `runner/extensions/job-watcher/job_watcher.py` |
| 100% | 553 | 1 | `runner/extensions/airwaves/airwaves.py` |
