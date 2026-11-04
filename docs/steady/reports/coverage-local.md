# Local coverage run

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

A regression pass of the whole suite on a two-core Linux box, Python
3.13, traced with the stdlib line monitor (statements only, no
branches). hypothesis does not install on this box, so the Platinum
and property modules did not run; CI runs them and its
`coverage.yml` figure is the one of record. The per-file data is
[coverage-local.json](coverage-local.json).

Two passes, before and after the edge tests landed (`test_panic_edges`,
`test_queue_pipe_edges`, `test_door_policy_edges`, with the desk's
`test_query_worker`). Every failure in both passes was a module that
needs hypothesis.

| Pass | Tests | Statements | Missed | Covered |
|---|---:|---:|---:|---:|
| before | 3565 | 30323 | 319 | 98.95% |
| after, main at 8540cc23 | 3621 | 30323 | 254 | 99.16% |

## What is left, ranked

statements 99.2% covered, 254 missing of 30323 (+0.2 points, +65 lines closed since the last report)

Rows under `runner.py` (the channel sweep, the stash, the kept
result) and `wire/dtlsproto.py` are what the Platinum modules reach
in CI; they show here only because hypothesis is absent.

| class | file:function | missing | branches | args |
|---|---|---:|---:|---|
| logic | `runner.py:_sweep_channel_refusals` L2018 | 9 (2028,2034,2054,2055,2082,2084,2086,2094…) | 0 | base_dir, cfg, names |
| logic | `wire/dtlsproto.py:_RecordSealer.open` L432 | 9 (446,450,454,455,456,457,460,464…) | 0 | epoch, record |
| logic | `cloud/send_job.py:cmd_new` L473 | 8 (519,521,525,526,531,532,573,575) | 0 | args |
| logic | `ops/exec.py:_read_output` L276 | 5 (285,293,302,307,315) | 0 | work, root, name, limit |
| logic | `runner.py:undeliver_stash` L1723 | 4 (1730,1734,1746,1747) | 0 | base_dir, skey, reason |
| logic | `runner.py:_keep_original_result` L1985 | 4 (1991,1994,2002,2003) | 0 | base_dir, rec, secrets |
| logic | `cloud/send_job.py:cmd_verify` L695 | 3 (706,707,708) | 0 | args |
| logic | `ops/extsources.py:status` L2198 | 3 (2212,2217,2219) | 0 | base_dir |
| logic | `ops/install.py:_import_atomicio` L47 | 3 (60,61,62) | 0 |  |
| logic | `ops/install.py:_import_panic` L82 | 3 (86,87,88) | 0 |  |
| logic | `ops/mail.py:handle_mail` L27 | 3 (141,143,692) | 0 | cfg, imap, smtp, seq, raw, base_dir, seen, secrets, opts, key_policies |
| logic | `ops/main.py:main` L37 | 3 (46,61,335) | 0 |  |
| logic | `oracle/learning.py:feature_keys` L163 | 3 (173,178,184) | 0 | facts |
| logic | `guard/extreview.py:apply` L586 | 2 (612,613) | 0 | cfg, base_dir, registry |
| logic | `ops/handlers.py:handle_v2_mail` L130 | 2 (182,183) | 0 | cfg, imap, smtp, seq, raw, subject, secrets, opts, base_dir, seen |
| logic | `ops/install.py:_name_first_key` L324 | 2 (336,338) | 0 | cfg_path, secret, key_id |
| logic | `ops/install.py:merge_config_blob` L1878 | 2 (1895,1897) | 0 | cfg_path, spec |
| logic | `ops/live.py:_runner` L17 | 2 (22,23) | 0 |  |
| logic | `ops/queries.py:answer_queries` L424 | 2 (513,645) | 0 | queries, exec_result, patterns, budget, cfg, view, already_spent, base_dir |
| logic | `ops/startup.py:handle_board_mail` L105 | 2 (205,206) | 0 | cfg, imap, smtp, seq, raw, subject, board, secrets, opts, base_dir |
| logic | `runner.py:_delivery_audit` L1653 | 2 (1655,1660) | 0 | base_dir, decision, reason, job_id, cfg |
| logic | `runner.py:process_transport_message` L4893 | 2 (4947,4948) | 0 | cfg, base_dir, seen, secrets, key_policies, subject, body_text, opts, transport |
| logic | `runner.py:rollback` L4946 | 2 (4947,4948) | 0 | added |
| logic | `runner.py:run_inspect` L5108 | 2 (5139,5140) | 0 | cfg, args |
| logic | `transport_extensions/email/__main__.py:_permanent` L64 | 2 (69,71) | 0 | exc |
| logic | `wire/dtlsproto.py:x25519` L157 | 2 (186,187) | 0 | scalar, u_bytes |
| logic | `wire/transports.py:discover_transport_extensions` L245 | 2 (285,290) | 0 | cfg, base_dir, log, event_sink |
| guard | `ops/cli.py:_transports_arg` L23 | 3 (34,35,39) | 0 | text |
| guard | `ops/exec.py:execute_job` L349 | 3 (408,451,499) | 0 | cfg, job, base_dir |
| guard | `guard/extreview.py:_review_entry` L402 | 2 (408,414) | 0 | manifest, folder, findings, shipped |
| guard | `guard/security.py:_rx_subpatterns` L223 | 2 (226,228) | 0 | op, av |
| guard | `ops/install.py:main` L3342 | 2 (3608,3667) | 0 |  |
| guard | `runner.py:_sweep_workspace` L2589 | 2 (2603,2613) | 0 | work, root, when |
| guard | `wire/verify.py:_estimate_secret_entropy` L744 | 2 (744,745) | 0 | secret |
| guard | `wire/verify.py:_key_fingerprint` L747 | 2 (747,748) | 0 | secret |
| guard | `wire/verify.py:_secret_pattern_reason` L750 | 2 (750,751) | 0 | secret |
| guard | `wire/verify.py:validate_shared_secret` L753 | 2 (753,754) | 0 | secret |
| guard | `wire/verify.py:verify_body_keyed` L926 | 2 (954,983) | 0 | body_text, secrets |
| except | `ops/extensions.py:load_extensions` L351 | 2 (392,393) | 0 | ext_dir, kinds |
| except | `ops/install.py:do_rearm` L128 | 2 (137,138) | 0 | cfg_path |
| except | `ops/install.py:do_check` L979 | 2 (1038,1056) | 0 | home, bin_dir, cfg_path, state_dir |
| except | `runner.py:_stash_move` L1641 | 2 (1649,1651) | 0 | base_dir, skey, folder |
| except | `runner.py:deliver_stash` L1670 | 2 (1701,1704) | 0 | base_dir, skey, sender, cfg, now |
| platform | `ops/main.py:_installed_config` L21 | 2 (26,27) | 0 |  |
| platform | `oracle/remediation.py:sample_tree_windows` L458 | 2 (470,483) | 0 | root_pid |

