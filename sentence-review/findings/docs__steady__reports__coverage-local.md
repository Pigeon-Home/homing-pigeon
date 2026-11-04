# Findings — docs/steady/reports/coverage-local.md

Source: docs/steady/reports/coverage-local.md, reviewed at main 720110b0.
Sentence units: 57. Flagged: 2. Categories: pre-release 57, post-release 0.

A local coverage pass record: the setup and its limits, the 2 passes in a small table, then prose on where the missing lines live and why they show on this box. The passes table's rows are counted as units and flow as records; its header row is structure. Unit 1 is the file's stamp comment, not a sentence; the prose itself chains cleanly, each paragraph qualifying the one before.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "A regression pass of the whole suite on…" | pre-release | flows |  |
| 3 | "hypothesis does not install on this box, so…" | pre-release | flows |  |
| 4 | "The per-file data is [coverage-local.json](coverage-local.json)." | pre-release | flows |  |
| 5 | "Two passes, before and after the edge tests…" | pre-release | flows |  |
| 6 | "Every failure in both passes was a module…" | pre-release | flows |  |
| 7 | "Pass \| Tests \| Statements \| Missed \|…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 8 | "before \| 3565 \| 30323 \| 319 \|…" | pre-release | flows |  |
| 9 | "after, main at 8540cc23 \| 3621 \| 30323…" | pre-release | flows |  |
| 10 | "statements 99.2% covered, 254 missing of 30323 (+0.2…" | pre-release | flows |  |
| 11 | "Rows under `runner.py` (the channel sweep, the stash,…" | pre-release | flows |  |
| 12 | "class \| file:function \| missing \| branches \|…" | pre-release | flows |  |
| 13 | "logic \| `runner.py:_sweep_channel_refusals` L2018 \| 9 (2028,2034,2054,2055,2082,2084,2086,2094…) \|…" | pre-release | flows |  |
| 14 | "logic \| `wire/dtlsproto.py:_RecordSealer.open` L432 \| 9 (446,450,454,455,456,457,460,464…) \|…" | pre-release | flows |  |
| 15 | "logic \| `cloud/send_job.py:cmd_new` L473 \| 8 (519,521,525,526,531,532,573,575) \|…" | pre-release | flows |  |
| 16 | "logic \| `ops/exec.py:_read_output` L276 \| 5 (285,293,302,307,315) \|…" | pre-release | flows |  |
| 17 | "logic \| `runner.py:undeliver_stash` L1723 \| 4 (1730,1734,1746,1747) \|…" | pre-release | flows |  |
| 18 | "logic \| `runner.py:_keep_original_result` L1985 \| 4 (1991,1994,2002,2003) \|…" | pre-release | flows |  |
| 19 | "logic \| `cloud/send_job.py:cmd_verify` L695 \| 3 (706,707,708) \|…" | pre-release | flows |  |
| 20 | "logic \| `ops/extsources.py:status` L2198 \| 3 (2212,2217,2219) \|…" | pre-release | flows |  |
| 21 | "logic \| `ops/install.py:_import_atomicio` L47 \| 3 (60,61,62) \|…" | pre-release | flows |  |
| 22 | "logic \| `ops/install.py:_import_panic` L82 \| 3 (86,87,88) \|…" | pre-release | flows |  |
| 23 | "logic \| `ops/mail.py:handle_mail` L27 \| 3 (141,143,692) \|…" | pre-release | flows |  |
| 24 | "logic \| `ops/main.py:main` L37 \| 3 (46,61,335) \|…" | pre-release | flows |  |
| 25 | "logic \| `oracle/learning.py:feature_keys` L163 \| 3 (173,178,184) \|…" | pre-release | flows |  |
| 26 | "logic \| `guard/extreview.py:apply` L586 \| 2 (612,613) \|…" | pre-release | flows |  |
| 27 | "logic \| `ops/handlers.py:handle_v2_mail` L130 \| 2 (182,183) \|…" | pre-release | flows |  |
| 28 | "logic \| `ops/install.py:_name_first_key` L324 \| 2 (336,338) \|…" | pre-release | flows |  |
| 29 | "logic \| `ops/install.py:merge_config_blob` L1878 \| 2 (1895,1897) \|…" | pre-release | flows |  |
| 30 | "logic \| `ops/live.py:_runner` L17 \| 2 (22,23) \|…" | pre-release | flows |  |
| 31 | "logic \| `ops/queries.py:answer_queries` L424 \| 2 (513,645) \|…" | pre-release | flows |  |
| 32 | "logic \| `ops/startup.py:handle_board_mail` L105 \| 2 (205,206) \|…" | pre-release | flows |  |
| 33 | "logic \| `runner.py:_delivery_audit` L1653 \| 2 (1655,1660) \|…" | pre-release | flows |  |
| 34 | "logic \| `runner.py:process_transport_message` L4893 \| 2 (4947,4948) \|…" | pre-release | flows |  |
| 35 | "logic \| `runner.py:rollback` L4946 \| 2 (4947,4948) \|…" | pre-release | flows |  |
| 36 | "logic \| `runner.py:run_inspect` L5108 \| 2 (5139,5140) \|…" | pre-release | flows |  |
| 37 | "logic \| `transport_extensions/email/__main__.py:_permanent` L64 \| 2 (69,71) \|…" | pre-release | flows |  |
| 38 | "logic \| `wire/dtlsproto.py:x25519` L157 \| 2 (186,187) \|…" | pre-release | flows |  |
| 39 | "logic \| `wire/transports.py:discover_transport_extensions` L245 \| 2 (285,290) \|…" | pre-release | flows |  |
| 40 | "guard \| `ops/cli.py:_transports_arg` L23 \| 3 (34,35,39) \|…" | pre-release | flows |  |
| 41 | "guard \| `ops/exec.py:execute_job` L349 \| 3 (408,451,499) \|…" | pre-release | flows |  |
| 42 | "guard \| `guard/extreview.py:_review_entry` L402 \| 2 (408,414) \|…" | pre-release | flows |  |
| 43 | "guard \| `guard/security.py:_rx_subpatterns` L223 \| 2 (226,228) \|…" | pre-release | flows |  |
| 44 | "guard \| `ops/install.py:main` L3342 \| 2 (3608,3667) \|…" | pre-release | flows |  |
| 45 | "guard \| `runner.py:_sweep_workspace` L2589 \| 2 (2603,2613) \|…" | pre-release | flows |  |
| 46 | "guard \| `wire/verify.py:_estimate_secret_entropy` L744 \| 2 (744,745) \|…" | pre-release | flows |  |
| 47 | "guard \| `wire/verify.py:_key_fingerprint` L747 \| 2 (747,748) \|…" | pre-release | flows |  |
| 48 | "guard \| `wire/verify.py:_secret_pattern_reason` L750 \| 2 (750,751) \|…" | pre-release | flows |  |
| 49 | "guard \| `wire/verify.py:validate_shared_secret` L753 \| 2 (753,754) \|…" | pre-release | flows |  |
| 50 | "guard \| `wire/verify.py:verify_body_keyed` L926 \| 2 (954,983) \|…" | pre-release | flows |  |
| 51 | "except \| `ops/extensions.py:load_extensions` L351 \| 2 (392,393) \|…" | pre-release | flows |  |
| 52 | "except \| `ops/install.py:do_rearm` L128 \| 2 (137,138) \|…" | pre-release | flows |  |
| 53 | "except \| `ops/install.py:do_check` L979 \| 2 (1038,1056) \|…" | pre-release | flows |  |
| 54 | "except \| `runner.py:_stash_move` L1641 \| 2 (1649,1651) \|…" | pre-release | flows |  |
| 55 | "except \| `runner.py:deliver_stash` L1670 \| 2 (1701,1704) \|…" | pre-release | flows |  |
| 56 | "platform \| `ops/main.py:_installed_config` L21 \| 2 (26,27) \|…" | pre-release | flows |  |
| 57 | "platform \| `oracle/remediation.py:sample_tree_windows` L458 \| 2 (470,483) \|…" | pre-release | flows |  |
