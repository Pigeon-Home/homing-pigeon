# Findings — docs/steady/reports/v3.15.1-coverage-gaps.md

Source: docs/steady/reports/v3.15.1-coverage-gaps.md, reviewed at main 3b99fe45.
Sentence units: 103. Flagged: 1. Categories: pre-release 103, post-release 0.

A coverage-gaps table with a 3-sentence head: the totals, the counting rule, and what a row is for. The head chains cleanly into the table. The table's 99 data rows are counted as units and flow as records under the head's rule; its header row (unit 4) is structure and is flagged on that ground alone.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Statements 33197, never executed 348; branches 13110, never…" | pre-release | flows |  |
| 2 | "Lines counted are the function's own, nested functions…" | pre-release | flows |  |
| 3 | "Each row is a hunt target: a test…" | pre-release | flows |  |
| 4 | "Missed \| Of \| Function \| Never-executed lines" | pre-release | flagged | Table header row, structure rather than a sentence |
| 5 | "30 \| 672 \| `runner/ops/mail.py:handle_mail` \| 387, 389,…" | pre-release | flows |  |
| 6 | "22 \| 23 \| `runner/cloud/send_job.py:_in_root_object_at` \| 283-304" | pre-release | flows |  |
| 7 | "22 \| 23 \| `runner/wire/verify.py:_in_root_object_at` \| 210-231" | pre-release | flows |  |
| 8 | "11 \| 110 \| `runner/transport_extensions/queues/__main__.py:QueuePipe.push_results` \| 357-358, 408-409,…" | pre-release | flows |  |
| 9 | "9 \| 52 \| `runner/runner.py:_deliver_stash_held` \| 1758, 1765,…" | pre-release | flows |  |
| 10 | "9 \| 19 \| `runner/runner.py:_warm_oracle_model` \| 6466-6468, 6473-6477,…" | pre-release | flows |  |
| 11 | "7 \| 77 \| `runner/cloud/send_job.py:cmd_dlq` \| 1264-1265, 1271-1273,…" | pre-release | flows |  |
| 12 | "7 \| 72 \| `runner/ops/cancel.py:handle_cancel_mail` \| 181-183, 206-207,…" | pre-release | flows |  |
| 13 | "7 \| 346 \| `runner/ops/exec.py:execute_job` \| 370, 403-404,…" | pre-release | flows |  |
| 14 | "6 \| 14 \| `runner/oracle/opinion.py:with_lesson_notes` \| 526-531" | pre-release | flows |  |
| 15 | "5 \| 86 \| `runner/cloud/send_job.py:cmd_results` \| 1167-1169, 1206,…" | pre-release | flows |  |
| 16 | "5 \| 179 \| `runner/ops/queries.py:handle_query_mail` \| 172-173, 202,…" | pre-release | flows |  |
| 17 | "5 \| 129 \| `runner/ops/startup.py:handle_board_mail` \| 171-173, 218-219" | pre-release | flows |  |
| 18 | "5 \| 33 \| `runner/runner.py:_env_salt` \| 2501, 2515-2516,…" | pre-release | flows |  |
| 19 | "4 \| 66 \| `runner/cloud/send_job.py:write_outputs` \| 1060-1063" | pre-release | flows |  |
| 20 | "4 \| 38 \| `runner/ops/changes.py:stage` \| 128, 138,…" | pre-release | flows |  |
| 21 | "4 \| 16 \| `runner/ops/changes.py:write_result_diff` \| 163-164, 168-169" | pre-release | flows |  |
| 22 | "4 \| 141 \| `runner/ops/install.py:do_check` \| 1037-1038, 1055-1056" | pre-release | flows |  |
| 23 | "4 \| 37 \| `runner/runner.py:_learning_freeze` \| 4412, 4418-4419,…" | pre-release | flows |  |
| 24 | "4 \| 20 \| `runner/runner.py:env_fingerprint` \| 2542, 2545,…" | pre-release | flows |  |
| 25 | "4 \| 25 \| `runner/transport_extensions/channel.py:refuse_symlink_result` \| 246, 258-260" | pre-release | flows |  |
| 26 | "4 \| 20 \| `runner/transport_extensions/dtls/__main__.py:directory_lookup.look` \| 121, 124-125,…" | pre-release | flows |  |
| 27 | "4 \| 23 \| `runner/transport_extensions/nats/__main__.py:NatsClient.flush` \| 297-298, 300,…" | pre-release | flows |  |
| 28 | "4 \| 45 \| `runner/transport_extensions/nats/__main__.py:NatsPipe.run` \| 434-437" | pre-release | flows |  |
| 29 | "4 \| 15 \| `runner/wire/dtlsproto.py:key_id_for` \| 651, 658-660" | pre-release | flows |  |
| 30 | "3 \| 7 \| `runner/cloud/send_dtls.py:_forget_ticket` \| 95, 98-99" | pre-release | flows |  |
| 31 | "3 \| 77 \| `runner/oracle/senses.py:gate_alert` \| 226-228" | pre-release | flows |  |
| 32 | "3 \| 48 \| `runner/runner.py:_early_dispatch` \| 4672-4674" | pre-release | flows |  |
| 33 | "3 \| 13 \| `runner/runner.py:_unclaim_stash` \| 1742-1743, 1745" | pre-release | flows |  |
| 34 | "3 \| 4 \| `runner/transport_extensions/nats/__main__.py:NatsClient.subscribe` \| 225-227" | pre-release | flows |  |
| 35 | "3 \| 6 \| `runner/transport_extensions/nats/__main__.py:NatsPipe._connect` \| 374, 377-378" | pre-release | flows |  |
| 36 | "3 \| 4 \| `runner/wire/oauth.py:_ConsentServer.get_request` \| 249-251" | pre-release | flows |  |
| 37 | "3 \| 50 \| `runner/wire/verify.py:check_door_policy` \| 855-856, 872" | pre-release | flows |  |
| 38 | "3 \| 94 \| `runner/wire/verify.py:check_policy_constraints` \| 1087, 1097,…" | pre-release | flows |  |
| 39 | "2 \| 24 \| `runner/extensions/pi-health/pi_health.py:_read_throttled` \| 203-204" | pre-release | flows |  |
| 40 | "2 \| 235 \| `runner/extensions/training-watch/training_watch.py:decide` \| 611-612" | pre-release | flows |  |
| 41 | "2 \| 11 \| `runner/guard/security.py:_rx_subpatterns` \| 226, 228" | pre-release | flows |  |
| 42 | "2 \| 14 \| `runner/ops/cancel.py:_kill_running` \| 71-72" | pre-release | flows |  |
| 43 | "2 \| 5 \| `runner/ops/cancel.py:_save` \| 99-100" | pre-release | flows |  |
| 44 | "2 \| 144 \| `runner/ops/handlers.py:handle_v2_mail` \| 202-203" | pre-release | flows |  |
| 45 | "2 \| 14 \| `runner/ops/install.py:ensure_panic_word` \| 124-125" | pre-release | flows |  |
| 46 | "2 \| 385 \| `runner/ops/install.py:main` \| 3608, 3667" | pre-release | flows |  |
| 47 | "2 \| 397 \| `runner/ops/main.py:main` \| 61, 338" | pre-release | flows |  |
| 48 | "2 \| 140 \| `runner/ops/poll.py:poll_once` \| 32-33" | pre-release | flows |  |
| 49 | "2 \| 5 \| `runner/ops/queries.py:_read_line._read` \| 361-362" | pre-release | flows |  |
| 50 | "2 \| 29 \| `runner/oracle/dri.py:send_telegram` \| 486-487" | pre-release | flows |  |
| 51 | "2 \| 27 \| `runner/oracle/remediation.py:sample_tree_windows` \| 470, 483" | pre-release | flows |  |
| 52 | "2 \| 67 \| `runner/oracle/senses.py:load_alerts` \| 429-430" | pre-release | flows |  |
| 53 | "2 \| 7 \| `runner/runner.py:_start_brief_thread._go` \| 4064-4065" | pre-release | flows |  |
| 54 | "2 \| 32 \| `runner/runner.py:pong_platform` \| 2562, 2565" | pre-release | flows |  |
| 55 | "2 \| 10 \| `runner/runner.py:result_digest` \| 1955-1956" | pre-release | flows |  |
| 56 | "2 \| 11 \| `runner/transport_extensions/email/__main__.py:EmailPipe._result_waiting` \| 156-157" | pre-release | flows |  |
| 57 | "2 \| 48 \| `runner/transport_extensions/email/__main__.py:EmailPipe.flush_results` \| 213, 230" | pre-release | flows |  |
| 58 | "2 \| 34 \| `runner/transport_extensions/nats/__main__.py:NatsClient.__init__` \| 128-129" | pre-release | flows |  |
| 59 | "2 \| 21 \| `runner/transport_extensions/nats/__main__.py:NatsClient._fill` \| 157-158" | pre-release | flows |  |
| 60 | "2 \| 34 \| `runner/transport_extensions/queues/__main__.py:QueueClient.post_result` \| 227-228" | pre-release | flows |  |
| 61 | "2 \| 11 \| `runner/transport_extensions/queues/__main__.py:QueuePipe._note_earlier_results` \| 335-336" | pre-release | flows |  |
| 62 | "2 \| 26 \| `runner/transport_extensions/queues/__main__.py:queue_base_allowed` \| 62-63" | pre-release | flows |  |
| 63 | "2 \| 33 \| `runner/wire/dtlsproto.py:x25519` \| 186-187" | pre-release | flows |  |
| 64 | "2 \| 13 \| `runner/wire/platformcard.py:_tool_identity` \| 123-124" | pre-release | flows |  |
| 65 | "Covered \| Statements \| Missed \| Module" | pre-release | flows |  |
| 66 | "89% \| 387 \| 30 \| `runner/ops/mail.py`" | pre-release | flows |  |
| 67 | "91% \| 160 \| 12 \| `runner/ops/cancel.py`" | pre-release | flows |  |
| 68 | "92% \| 274 \| 21 \| `runner/transport_extensions/nats/__main__.py`" | pre-release | flows |  |
| 69 | "93% \| 735 \| 46 \| `runner/wire/verify.py`" | pre-release | flows |  |
| 70 | "93% \| 106 \| 8 \| `runner/ops/changes.py`" | pre-release | flows |  |
| 71 | "94% \| 986 \| 44 \| `runner/cloud/send_job.py`" | pre-release | flows |  |
| 72 | "95% \| 95 \| 2 \| `runner/ops/poll.py`" | pre-release | flows |  |
| 73 | "95% \| 311 \| 17 \| `runner/transport_extensions/queues/__main__.py`" | pre-release | flows |  |
| 74 | "95% \| 151 \| 4 \| `runner/transport_extensions/channel.py`" | pre-release | flows |  |
| 75 | "96% \| 159 \| 5 \| `runner/transport_extensions/email/__main__.py`" | pre-release | flows |  |
| 76 | "96% \| 203 \| 7 \| `runner/wire/oauth.py`" | pre-release | flows |  |
| 77 | "96% \| 230 \| 2 \| `runner/ops/main.py`" | pre-release | flows |  |
| 78 | "97% \| 163 \| 5 \| `runner/ops/startup.py`" | pre-release | flows |  |
| 79 | "97% \| 309 \| 8 \| `runner/oracle/opinion.py`" | pre-release | flows |  |
| 80 | "97% \| 208 \| 4 \| `runner/transport_extensions/dtls/__main__.py`" | pre-release | flows |  |
| 81 | "98% \| 3946 \| 62 \| `runner/runner.py`" | pre-release | flows |  |
| 82 | "98% \| 181 \| 3 \| `runner/cloud/send_dtls.py`" | pre-release | flows |  |
| 83 | "98% \| 452 \| 7 \| `runner/ops/exec.py`" | pre-release | flows |  |
| 84 | "98% \| 449 \| 8 \| `runner/ops/queries.py`" | pre-release | flows |  |
| 85 | "98% \| 70 \| 2 \| `runner/wire/platformcard.py`" | pre-release | flows |  |
| 86 | "98% \| 272 \| 4 \| `runner/guard/security.py`" | pre-release | flows |  |
| 87 | "98% \| 1112 \| 8 \| `runner/wire/dtlsproto.py`" | pre-release | flows |  |
| 88 | "98% \| 297 \| 1 \| `runner/hosting/cli.py`" | pre-release | flows |  |
| 89 | "99% \| 311 \| 5 \| `runner/oracle/senses.py`" | pre-release | flows |  |
| 90 | "99% \| 63 \| 1 \| `runner/hosting/fly.py`" | pre-release | flows |  |
| 91 | "99% \| 232 \| 2 \| `runner/ops/handlers.py`" | pre-release | flows |  |
| 92 | "99% \| 186 \| 1 \| `runner/ops/remediation_ops.py`" | pre-release | flows |  |
| 93 | "99% \| 384 \| 4 \| `runner/oracle/dri.py`" | pre-release | flows |  |
| 94 | "99% \| 805 \| 1 \| `runner/extensions/job-fuzz/job_fuzz.py`" | pre-release | flows |  |
| 95 | "99% \| 379 \| 2 \| `runner/wire/protocol_v2.py`" | pre-release | flows |  |
| 96 | "99% \| 1433 \| 1 \| `runner/ops/extsources.py`" | pre-release | flows |  |
| 97 | "99% \| 296 \| 2 \| `runner/wire/board.py`" | pre-release | flows |  |
| 98 | "99% \| 2037 \| 10 \| `runner/ops/install.py`" | pre-release | flows |  |
| 99 | "99% \| 380 \| 1 \| `runner/oracle/learning.py`" | pre-release | flows |  |
| 100 | "99% \| 338 \| 1 \| `runner/extensions/sky-watcher/sky_watcher.py`" | pre-release | flows |  |
| 101 | "99% \| 276 \| 2 \| `runner/extensions/pi-health/pi_health.py`" | pre-release | flows |  |
| 102 | "100% \| 903 \| 3 \| `runner/oracle/remediation.py`" | pre-release | flows |  |
| 103 | "100% \| 414 \| 2 \| `runner/extensions/training-watch/training_watch.py`" | pre-release | flows |  |
