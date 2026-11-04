# Findings — docs/steady/reports/local-rig-2026-10-27-coverage-gaps.md

Source: docs/steady/reports/local-rig-2026-10-27-coverage-gaps.md, reviewed at main 52f64508.
Sentence units: 109. Flagged: 1. Categories: pre-release 109, post-release 0.

A coverage-gaps table with the family's standard 3-sentence head: the totals, the counting rule, and what a row is for. The head chains cleanly into the table. The table's data rows are counted as units and flow as records under the head's rule; its header row (unit 4) is structure and is flagged on that ground alone.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Statements 37937, never executed 322; branches 0, never…" | pre-release | flows |  |
| 2 | "Lines counted are the function's own, nested functions…" | pre-release | flows |  |
| 3 | "Each row is a hunt target: a test…" | pre-release | flows |  |
| 4 | "Missed \| Of \| Function \| Never-executed lines" | pre-release | flagged | Table header row, structure rather than a sentence |
| 5 | "31 \| 34 \| `runner/ops/queries.py:worker_main` \| 391-421" | pre-release | flows |  |
| 6 | "17 \| 47 \| `runner/ops/queries.py:grep_matches` \| 356-365, 373-376,…" | pre-release | flows |  |
| 7 | "7 \| 19 \| `runner/ops/install.py:_import_panic` \| 86-88, 97-100" | pre-release | flows |  |
| 8 | "6 \| 21 \| `runner/ops/queries.py:_stop_worker` \| 272-273, 276-277,…" | pre-release | flows |  |
| 9 | "5 \| 49 \| `runner/cloud/send_job.py:cmd_results` \| 813-816, 824" | pre-release | flows |  |
| 10 | "5 \| 394 \| `runner/ops/main.py:main` \| 56, 61,…" | pre-release | flows |  |
| 11 | "5 \| 89 \| `runner/runner.py:_sweep_channel_refusals` \| 2033-2034, 2086-2088" | pre-release | flows |  |
| 12 | "4 \| 31 \| `runner/cloud/send_job.py:_queue_call` \| 763-764, 778-779" | pre-release | flows |  |
| 13 | "4 \| 314 \| `runner/ops/exec.py:execute_job` \| 450-452, 499" | pre-release | flows |  |
| 14 | "4 \| 141 \| `runner/ops/install.py:do_check` \| 1037-1038, 1055-1056" | pre-release | flows |  |
| 15 | "4 \| 639 \| `runner/ops/mail.py:handle_mail` \| 141, 143,…" | pre-release | flows |  |
| 16 | "4 \| 11 \| `runner/runner.py:_stash_move` \| 1648-1651" | pre-release | flows |  |
| 17 | "4 \| 28 \| `runner/runner.py:undeliver_stash` \| 1734, 1745-1747" | pre-release | flows |  |
| 18 | "3 \| 117 \| `runner/cloud/send_job.py:cmd_new` \| 573-575" | pre-release | flows |  |
| 19 | "3 \| 16 \| `runner/cloud/send_job.py:cmd_verify` \| 706-708" | pre-release | flows |  |
| 20 | "3 \| 22 \| `runner/ops/install.py:_name_first_key` \| 336-338" | pre-release | flows |  |
| 21 | "3 \| 68 \| `runner/ops/install.py:do_install_home` \| 1378-1379, 1381" | pre-release | flows |  |
| 22 | "3 \| 16 \| `runner/ops/install.py:do_rearm` \| 136-138" | pre-release | flows |  |
| 23 | "3 \| 24 \| `runner/ops/install.py:merge_config_blob` \| 1894-1895, 1897" | pre-release | flows |  |
| 24 | "3 \| 21 \| `runner/transport_extensions/queues/__main__.py:QueueClient.pull` \| 109-110, 115" | pre-release | flows |  |
| 25 | "3 \| 11 \| `runner/transport_extensions/queues/__main__.py:QueuePipe.renew_leases` \| 182-184" | pre-release | flows |  |
| 26 | "2 \| 10 \| `runner/cloud/send_job.py:_named_key_in` \| 656-657" | pre-release | flows |  |
| 27 | "2 \| 24 \| `runner/extensions/pi-health/pi_health.py:_read_throttled` \| 203-204" | pre-release | flows |  |
| 28 | "2 \| 235 \| `runner/extensions/training-watch/training_watch.py:decide` \| 611-612" | pre-release | flows |  |
| 29 | "2 \| 52 \| `runner/guard/extreview.py:_review_entry` \| 408, 414" | pre-release | flows |  |
| 30 | "2 \| 11 \| `runner/guard/security.py:_rx_subpatterns` \| 226, 228" | pre-release | flows |  |
| 31 | "2 \| 14 \| `runner/hosting/fly.py:FlyMachines._machine` \| 66, 68" | pre-release | flows |  |
| 32 | "2 \| 20 \| `runner/ops/extensions.py:api_refusal` \| 304-305" | pre-release | flows |  |
| 33 | "2 \| 71 \| `runner/ops/extensions.py:load_extensions` \| 392-393" | pre-release | flows |  |
| 34 | "2 \| 142 \| `runner/ops/handlers.py:handle_v2_mail` \| 182-183" | pre-release | flows |  |
| 35 | "2 \| 14 \| `runner/ops/install.py:ensure_panic_word` \| 124-125" | pre-release | flows |  |
| 36 | "2 \| 385 \| `runner/ops/install.py:main` \| 3608, 3667" | pre-release | flows |  |
| 37 | "2 \| 14 \| `runner/ops/main.py:_installed_config` \| 26-27" | pre-release | flows |  |
| 38 | "2 \| 71 \| `runner/ops/oracle_server.py:make_oracle_server.Handler.do_POST` \| 184-185" | pre-release | flows |  |
| 39 | "2 \| 142 \| `runner/ops/poll.py:poll_once` \| 32-33" | pre-release | flows |  |
| 40 | "2 \| 5 \| `runner/ops/queries.py:_read_line._read` \| 328-329" | pre-release | flows |  |
| 41 | "2 \| 117 \| `runner/ops/startup.py:handle_board_mail` \| 205-206" | pre-release | flows |  |
| 42 | "2 \| 29 \| `runner/oracle/dri.py:send_telegram` \| 486-487" | pre-release | flows |  |
| 43 | "2 \| 27 \| `runner/oracle/remediation.py:sample_tree_windows` \| 470, 483" | pre-release | flows |  |
| 44 | "2 \| 27 \| `runner/oracle/review.py:review_job` \| 296-297" | pre-release | flows |  |
| 45 | "Covered \| Statements \| Missed \| Module" | pre-release | flows |  |
| 46 | "89% \| 515 \| 59 \| `runner/ops/queries.py`" | pre-release | flows |  |
| 47 | "95% \| 200 \| 10 \| `runner/transport_extensions/queues/__main__.py`" | pre-release | flows |  |
| 48 | "96% \| 657 \| 25 \| `runner/wire/verify.py`" | pre-release | flows |  |
| 49 | "96% \| 300 \| 11 \| `runner/hosting/cli.py`" | pre-release | flows |  |
| 50 | "96% \| 193 \| 7 \| `runner/guard/panic.py`" | pre-release | flows |  |
| 51 | "97% \| 782 \| 27 \| `runner/cloud/send_job.py`" | pre-release | flows |  |
| 52 | "97% \| 95 \| 3 \| `runner/hosting/fly.py`" | pre-release | flows |  |
| 53 | "97% \| 269 \| 7 \| `runner/ops/main.py`" | pre-release | flows |  |
| 54 | "98% \| 111 \| 2 \| `runner/ops/poll.py`" | pre-release | flows |  |
| 55 | "98% \| 168 \| 3 \| `runner/transport_extensions/email/__main__.py`" | pre-release | flows |  |
| 56 | "98% \| 225 \| 4 \| `runner/ops/cli.py`" | pre-release | flows |  |
| 57 | "98% \| 318 \| 5 \| `runner/guard/security.py`" | pre-release | flows |  |
| 58 | "99% \| 75 \| 1 \| `runner/hosting/hetzner.py`" | pre-release | flows |  |
| 59 | "99% \| 234 \| 3 \| `runner/wire/oauth.py`" | pre-release | flows |  |
| 60 | "99% \| 2414 \| 29 \| `runner/ops/install.py`" | pre-release | flows |  |
| 61 | "99% \| 167 \| 2 \| `runner/ops/oracle_server.py`" | pre-release | flows |  |
| 62 | "99% \| 172 \| 2 \| `runner/ops/startup.py`" | pre-release | flows |  |
| 63 | "99% \| 361 \| 4 \| `runner/ops/extensions.py`" | pre-release | flows |  |
| 64 | "99% \| 184 \| 2 \| `runner/oracle/review.py`" | pre-release | flows |  |
| 65 | "99% \| 506 \| 5 \| `runner/ops/exec.py`" | pre-release | flows |  |
| 66 | "99% \| 459 \| 4 \| `runner/oracle/dri.py`" | pre-release | flows |  |
| 67 | "99% \| 351 \| 3 \| `runner/extensions/pi-health/pi_health.py`" | pre-release | flows |  |
| 68 | "99% \| 1256 \| 10 \| `runner/wire/dtlsproto.py`" | pre-release | flows |  |
| 69 | "99% \| 515 \| 4 \| `runner/ops/mail.py`" | pre-release | flows |  |
| 70 | "99% \| 4191 \| 31 \| `runner/runner.py`" | pre-release | flows |  |
| 71 | "99% \| 556 \| 4 \| `runner/extensions/training-watch/training_watch.py`" | pre-release | flows |  |
| 72 | "99% \| 285 \| 2 \| `runner/ops/handlers.py`" | pre-release | flows |  |
| 73 | "99% \| 163 \| 1 \| `runner/transport_extensions/file/__main__.py`" | pre-release | flows |  |
| 74 | "99% \| 333 \| 2 \| `runner/extensions/log-sentinel/log_sentinel.py`" | pre-release | flows |  |
| 75 | "99% \| 333 \| 2 \| `runner/oracle/senses.py`" | pre-release | flows |  |
| 76 | "99% \| 175 \| 1 \| `runner/ops/policy.py`" | pre-release | flows |  |
| 77 | "99% \| 381 \| 2 \| `runner/extensions/osquery-feed/osquery_feed.py`" | pre-release | flows |  |
| 78 | "99% \| 193 \| 1 \| `runner/cloud/send_dtls.py`" | pre-release | flows |  |
| 79 | "99% \| 194 \| 1 \| `runner/hosting/billing.py`" | pre-release | flows |  |
| 80 | "100% \| 206 \| 1 \| `runner/wire/mailbox.py`" | pre-release | flows |  |
| 81 | "100% \| 1053 \| 5 \| `runner/extensions/job-fuzz/job_fuzz.py`" | pre-release | flows |  |
| 82 | "100% \| 212 \| 1 \| `runner/extensions/lab-results/lab_results.py`" | pre-release | flows |  |
| 83 | "100% \| 434 \| 2 \| `runner/extensions/sky-watcher/sky_watcher.py`" | pre-release | flows |  |
| 84 | "100% \| 468 \| 2 \| `runner/guard/extreview.py`" | pre-release | flows |  |
| 85 | "100% \| 240 \| 1 \| `runner/extensions/backup-freshness/backup_freshness.py`" | pre-release | flows |  |
| 86 | "100% \| 249 \| 1 \| `runner/extensions/release-drop/release_drop.py`" | pre-release | flows |  |
| 87 | "100% \| 257 \| 1 \| `runner/extensions/crash-watch/crash_watch.py`" | pre-release | flows |  |
| 88 | "100% \| 263 \| 1 \| `runner/extensions/port-watch/port_watch.py`" | pre-release | flows |  |
| 89 | "100% \| 278 \| 1 \| `runner/extensions/latency-post/latency_post.py`" | pre-release | flows |  |
| 90 | "100% \| 282 \| 1 \| `runner/extensions/tripwire/tripwire.py`" | pre-release | flows |  |
| 91 | "100% \| 287 \| 1 \| `runner/extensions/aide-feed/aide_feed.py`" | pre-release | flows |  |
| 92 | "100% \| 287 \| 1 \| `runner/extensions/wire-arrivals/wire_arrivals.py`" | pre-release | flows |  |
| 93 | "100% \| 299 \| 1 \| `runner/extensions/usb-arrivals/usb_arrivals.py`" | pre-release | flows |  |
| 94 | "100% \| 306 \| 1 \| `runner/extensions/service-watch/service_watch.py`" | pre-release | flows |  |
| 95 | "100% \| 317 \| 1 \| `runner/wire/board.py`" | pre-release | flows |  |
| 96 | "100% \| 323 \| 1 \| `runner/extensions/cert-sentinel/cert_sentinel.py`" | pre-release | flows |  |
| 97 | "100% \| 335 \| 1 \| `runner/extensions/resource-sentinel/resource_sentinel.py`" | pre-release | flows |  |
| 98 | "100% \| 341 \| 1 \| `runner/extensions/wazuh-feed/wazuh_feed.py`" | pre-release | flows |  |
| 99 | "100% \| 1717 \| 5 \| `runner/ops/extsources.py`" | pre-release | flows |  |
| 100 | "100% \| 688 \| 2 \| `runner/wire/transports.py`" | pre-release | flows |  |
| 101 | "100% \| 346 \| 1 \| `runner/extensions/failed-login-watch/failed_login_watch.py`" | pre-release | flows |  |
| 102 | "100% \| 347 \| 1 \| `runner/extensions/falco-feed/falco_feed.py`" | pre-release | flows |  |
| 103 | "100% \| 1049 \| 3 \| `runner/oracle/remediation.py`" | pre-release | flows |  |
| 104 | "100% \| 388 \| 1 \| `runner/extensions/suricata-feed/suricata_feed.py`" | pre-release | flows |  |
| 105 | "100% \| 415 \| 1 \| `runner/extensions/sysmon-feed/sysmon_feed.py`" | pre-release | flows |  |
| 106 | "100% \| 418 \| 1 \| `runner/wire/protocol_v2.py`" | pre-release | flows |  |
| 107 | "100% \| 452 \| 1 \| `runner/extensions/zeek-feed/zeek_feed.py`" | pre-release | flows |  |
| 108 | "100% \| 507 \| 1 \| `runner/extensions/job-watcher/job_watcher.py`" | pre-release | flows |  |
| 109 | "100% \| 553 \| 1 \| `runner/extensions/airwaves/airwaves.py`" | pre-release | flows |  |
