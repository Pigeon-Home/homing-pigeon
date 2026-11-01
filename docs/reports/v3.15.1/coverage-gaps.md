# Coverage gaps: this measurement

Statements 33197, never executed 437; branches 13110, never taken 472; 98.0% covered overall (shipped code only: runner/ without tests/ and tools/).

## Functions with the most never-executed lines

Lines counted are the function's own, nested functions excluded. Each row is a hunt target: a test that makes these lines run, and asserts what the docs say they do.

| Missed | Of | Function | Never-executed lines |
|---:|---:|---|---|
| 63 | 672 | `runner/ops/mail.py:handle_mail` | 89-91, 141, 143, 148-149, 164-166, 170-171, 194-197, 199, 203-205, 212, 245-247, 262, 264-265, 322-324, 326-328, 387, 389, 391, 400-404, 461, 468, 482, 507-508, 577-581, 585, 589-594, 598, 643, 658, 681, 687 |
| 24 | 33 | `runner/ops/oracle_server.py:make_oracle_server.Handler.do_GET` | 83-94, 99-108, 112, 114 |
| 23 | 71 | `runner/ops/oracle_server.py:make_oracle_server.Handler.do_POST` | 119-120, 122-123, 129-130, 133-134, 138-139, 141, 144, 146, 152, 163-165, 168, 170, 180-181, 184-185 |
| 22 | 23 | `runner/cloud/send_job.py:_in_root_object_at` | 283-304 |
| 22 | 23 | `runner/wire/verify.py:_in_root_object_at` | 210-231 |
| 11 | 72 | `runner/ops/cancel.py:handle_cancel_mail` | 176-179, 181-183, 206-207, 224-225 |
| 11 | 110 | `runner/transport_extensions/queues/__main__.py:QueuePipe.push_results` | 357-358, 408-409, 411-412, 444-445, 447, 449, 451 |
| 9 | 52 | `runner/runner.py:_deliver_stash_held` | 1758, 1765, 1784-1785, 1788-1792 |
| 9 | 19 | `runner/runner.py:_warm_oracle_model` | 6466-6468, 6473-6477, 6480 |
| 7 | 77 | `runner/cloud/send_job.py:cmd_dlq` | 1264-1265, 1271-1273, 1287, 1289 |
| 7 | 346 | `runner/ops/exec.py:execute_job` | 370, 403-404, 453, 592-594 |
| 6 | 14 | `runner/oracle/opinion.py:with_lesson_notes` | 526-531 |
| 5 | 86 | `runner/cloud/send_job.py:cmd_results` | 1167-1169, 1206, 1208 |
| 5 | 29 | `runner/ops/oracle_server.py:make_oracle_server.Handler._take_body` | 62, 66, 75, 78-79 |
| 5 | 179 | `runner/ops/queries.py:handle_query_mail` | 172-173, 202, 206-207 |
| 5 | 129 | `runner/ops/startup.py:handle_board_mail` | 171-173, 218-219 |
| 5 | 33 | `runner/runner.py:_env_salt` | 2501, 2515-2516, 2520, 2527 |
| 4 | 66 | `runner/cloud/send_job.py:write_outputs` | 1060-1063 |
| 4 | 38 | `runner/ops/changes.py:stage` | 128, 138, 148, 150 |
| 4 | 16 | `runner/ops/changes.py:write_result_diff` | 163-164, 168-169 |
| 4 | 141 | `runner/ops/install.py:do_check` | 1037-1038, 1055-1056 |
| 4 | 37 | `runner/runner.py:_learning_freeze` | 4412, 4418-4419, 4421 |
| 4 | 20 | `runner/runner.py:env_fingerprint` | 2542, 2545, 2548-2549 |
| 4 | 25 | `runner/transport_extensions/channel.py:refuse_symlink_result` | 246, 258-260 |
| 4 | 20 | `runner/transport_extensions/dtls/__main__.py:directory_lookup.look` | 121, 124-125, 127 |
| 4 | 23 | `runner/transport_extensions/nats/__main__.py:NatsClient.flush` | 297-298, 300, 308 |
| 4 | 45 | `runner/transport_extensions/nats/__main__.py:NatsPipe.run` | 434-437 |
| 4 | 15 | `runner/wire/dtlsproto.py:key_id_for` | 651, 658-660 |
| 3 | 7 | `runner/cloud/send_dtls.py:_forget_ticket` | 95, 98-99 |
| 3 | 77 | `runner/oracle/senses.py:gate_alert` | 226-228 |
| 3 | 48 | `runner/runner.py:_early_dispatch` | 4672-4674 |
| 3 | 13 | `runner/runner.py:_unclaim_stash` | 1742-1743, 1745 |
| 3 | 4 | `runner/transport_extensions/nats/__main__.py:NatsClient.subscribe` | 225-227 |
| 3 | 6 | `runner/transport_extensions/nats/__main__.py:NatsPipe._connect` | 374, 377-378 |
| 3 | 4 | `runner/wire/oauth.py:_ConsentServer.get_request` | 249-251 |
| 3 | 50 | `runner/wire/verify.py:check_door_policy` | 855-856, 872 |
| 3 | 94 | `runner/wire/verify.py:check_policy_constraints` | 1087, 1097, 1110 |
| 2 | 24 | `runner/extensions/pi-health/pi_health.py:_read_throttled` | 203-204 |
| 2 | 235 | `runner/extensions/training-watch/training_watch.py:decide` | 611-612 |
| 2 | 11 | `runner/guard/security.py:_rx_subpatterns` | 226, 228 |
| 2 | 14 | `runner/ops/cancel.py:_kill_running` | 71-72 |
| 2 | 5 | `runner/ops/cancel.py:_save` | 99-100 |
| 2 | 144 | `runner/ops/handlers.py:handle_v2_mail` | 202-203 |
| 2 | 14 | `runner/ops/install.py:ensure_panic_word` | 124-125 |
| 2 | 385 | `runner/ops/install.py:main` | 3608, 3667 |
| 2 | 397 | `runner/ops/main.py:main` | 61, 338 |
| 2 | 140 | `runner/ops/poll.py:poll_once` | 32-33 |
| 2 | 5 | `runner/ops/queries.py:_read_line._read` | 361-362 |
| 2 | 29 | `runner/oracle/dri.py:send_telegram` | 486-487 |
| 2 | 27 | `runner/oracle/remediation.py:sample_tree_windows` | 470, 483 |
| 2 | 67 | `runner/oracle/senses.py:load_alerts` | 429-430 |
| 2 | 7 | `runner/runner.py:_start_brief_thread._go` | 4064-4065 |
| 2 | 32 | `runner/runner.py:pong_platform` | 2562, 2565 |
| 2 | 10 | `runner/runner.py:result_digest` | 1955-1956 |
| 2 | 11 | `runner/transport_extensions/email/__main__.py:EmailPipe._result_waiting` | 156-157 |
| 2 | 48 | `runner/transport_extensions/email/__main__.py:EmailPipe.flush_results` | 213, 230 |
| 2 | 34 | `runner/transport_extensions/nats/__main__.py:NatsClient.__init__` | 128-129 |
| 2 | 21 | `runner/transport_extensions/nats/__main__.py:NatsClient._fill` | 157-158 |
| 2 | 34 | `runner/transport_extensions/queues/__main__.py:QueueClient.post_result` | 227-228 |
| 2 | 11 | `runner/transport_extensions/queues/__main__.py:QueuePipe._note_earlier_results` | 335-336 |

## Modules, least covered first

| Covered | Statements | Missed | Module |
|---:|---:|---:|---|
| 61% | 152 | 52 | `runner/ops/oracle_server.py` |
| 80% | 387 | 63 | `runner/ops/mail.py` |
| 89% | 160 | 16 | `runner/ops/cancel.py` |
| 92% | 274 | 21 | `runner/transport_extensions/nats/__main__.py` |
| 93% | 735 | 46 | `runner/wire/verify.py` |
| 93% | 106 | 8 | `runner/ops/changes.py` |
| 94% | 986 | 44 | `runner/cloud/send_job.py` |
| 95% | 95 | 2 | `runner/ops/poll.py` |
| 95% | 311 | 17 | `runner/transport_extensions/queues/__main__.py` |
| 95% | 151 | 4 | `runner/transport_extensions/channel.py` |
| 96% | 159 | 5 | `runner/transport_extensions/email/__main__.py` |
| 96% | 203 | 7 | `runner/wire/oauth.py` |
| 96% | 230 | 2 | `runner/ops/main.py` |
| 97% | 163 | 5 | `runner/ops/startup.py` |
| 97% | 309 | 8 | `runner/oracle/opinion.py` |
| 97% | 208 | 4 | `runner/transport_extensions/dtls/__main__.py` |
| 98% | 3946 | 62 | `runner/runner.py` |
| 98% | 181 | 3 | `runner/cloud/send_dtls.py` |
| 98% | 452 | 7 | `runner/ops/exec.py` |
| 98% | 449 | 8 | `runner/ops/queries.py` |
| 98% | 70 | 2 | `runner/wire/platformcard.py` |
| 98% | 272 | 4 | `runner/guard/security.py` |
| 98% | 1112 | 8 | `runner/wire/dtlsproto.py` |
| 98% | 297 | 1 | `runner/hosting/cli.py` |
| 99% | 311 | 5 | `runner/oracle/senses.py` |
| 99% | 63 | 1 | `runner/hosting/fly.py` |
| 99% | 232 | 2 | `runner/ops/handlers.py` |
| 99% | 186 | 1 | `runner/ops/remediation_ops.py` |
| 99% | 384 | 4 | `runner/oracle/dri.py` |
| 99% | 805 | 1 | `runner/extensions/job-fuzz/job_fuzz.py` |
| 99% | 379 | 2 | `runner/wire/protocol_v2.py` |
| 99% | 1433 | 1 | `runner/ops/extsources.py` |
| 99% | 296 | 2 | `runner/wire/board.py` |
| 99% | 2037 | 10 | `runner/ops/install.py` |
| 99% | 380 | 1 | `runner/oracle/learning.py` |
| 99% | 338 | 1 | `runner/extensions/sky-watcher/sky_watcher.py` |
| 99% | 276 | 2 | `runner/extensions/pi-health/pi_health.py` |
| 100% | 903 | 3 | `runner/oracle/remediation.py` |
| 100% | 414 | 2 | `runner/extensions/training-watch/training_watch.py` |
