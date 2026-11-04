# Findings — docs/steady/reports/v3.12.65-coverage-gaps.md

Source: docs/steady/reports/v3.12.65-coverage-gaps.md, reviewed at main 8a717fd5.
Sentence units: 175. Flagged: 2. Categories: pre-release 175, post-release 0.

A coverage report that argues: the snapshot and its limits first, the first CI run, then the gaps ranked by harm as a question list for the campaign, and the full function table last under the family's standard head. The ranked list is the document's spine — each item names the gap, says why it matters, and hands to the next — and the prose around it chains cleanly. The non-sentences are the stamp comment (unit 1) and the function table's header row (unit 49); the table's data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "This report belongs to package 3.12.65." | pre-release | flows |  |
| 3 | "It answers the owner's question of 2026-10-24: the…" | pre-release | flows |  |
| 4 | "History shows where bugs were fixed." | pre-release | flows |  |
| 5 | "This shows where no test has ever executed…" | pre-release | flows |  |
| 6 | "The full suite (5,695 tests) was run on…" | pre-release | flows |  |
| 7 | "Only shipped code counts: `runner/` without `runner/tests/` and…" | pre-release | flows |  |
| 8 | "The function table is produced by `runner/tools/coverage_gaps.py`, which…" | pre-release | flows |  |
| 9 | "From now on `.github/workflows/coverage.yml` produces the same report…" | pre-release | flows |  |
| 10 | "It is a signal, not a gate: it…" | pre-release | flows |  |
| 11 | "**Limit of this snapshot.** It is the Linux…" | pre-release | flows |  |
| 12 | "Code that runs only on Windows (registry reads,…" | pre-release | flows |  |
| 13 | "The first `coverage-Windows` artifact is the other half;…" | pre-release | flows |  |
| 14 | "**First CI run (coverage run 40164003041, `6ded4b7`).** CI…" | pre-release | flows |  |
| 15 | "CI has bwrap working and every optional tool…" | pre-release | flows |  |
| 16 | "Both CI maps still carry the same largest…" | pre-release | flows |  |
| 17 | "The ranked list below is from the local…" | pre-release | flows |  |
| 18 | "The table further down is ordered by how…" | pre-release | flows |  |
| 19 | "This list is ordered by harm." | pre-release | flows |  |
| 20 | "Each item is filed as a question for…" | pre-release | flows |  |
| 21 | "**The email transport extension: 41% covered** (Q11)." | pre-release | flows |  |
| 22 | "Email is the default transport, the one nearly…" | pre-release | flows |  |
| 23 | "The campaign drove everything through the file inbox…" | pre-release | flows |  |
| 24 | "A broken result send here means a job…" | pre-release | flows |  |
| 25 | "**Running a job as another user, `_job_user_preexec`: 38…" | pre-release | flows |  |
| 26 | "This is the privilege drop behind `security.modes.job_user`, the…" | pre-release | flows |  |
| 27 | "The untested lines are the group, supplementary-group and…" | pre-release | flows |  |
| 28 | "**Stopping a job that is going bad, `_finish_remediation`:…" | pre-release | flows |  |
| 29 | "The kill, the cleanup and the report of…" | pre-release | flows |  |
| 30 | "The decision to remediate is tested; acting on…" | pre-release | flows |  |
| 31 | "**Every sense extension's alert delivery, `_deliver_local`: about 27…" | pre-release | flows |  |
| 32 | "The campaign hunted each extension's decision logic through…" | pre-release | flows |  |
| 33 | "If that step breaks, the extension decides correctly…" | pre-release | flows |  |
| 34 | "**The Oracle agent's tool calls and loop** (Q15):…" | pre-release | flows |  |
| 35 | "This is where a model's output is untrusted…" | pre-release | flows |  |
| 36 | "**The personal-documents warning, `oracle/personal_docs.py`: 26% covered** (Q16)." | pre-release | flows |  |
| 37 | "The check that warns before a box with…" | pre-release | flows |  |
| 38 | "`_walk`, `_sensitive` and `_xdg_dirs` barely run." | pre-release | flows |  |
| 39 | "A bug here is a privacy failure that…" | pre-release | flows |  |
| 40 | "**Protocol v2 waiting for an answer, and the…" | pre-release | flows |  |
| 41 | "The answer window and the job builder are…" | pre-release | flows |  |
| 42 | "Not ranked, worth knowing: `oracle_cli` (75 of 109,…" | pre-release | flows |  |
| 43 | "The shape that worked for the documented-default hunt…" | pre-release | flows |  |
| 44 | "For each row the campaign writes a test…" | pre-release | flows |  |
| 45 | "A test that cannot reach the lines without…" | pre-release | flows |  |
| 46 | "Statements 29005, never executed 4398; branches 12937, never…" | pre-release | flows |  |
| 47 | "Lines counted are the function's own, nested functions…" | pre-release | flows |  |
| 48 | "Each row is a hunt target: a test…" | pre-release | flows |  |
| 49 | "Missed \| Of \| Function \| Never-executed lines" | pre-release | flagged | Table header row, structure rather than a sentence |
| 50 | "75 \| 109 \| `runner/runner.py:oracle_cli` \| 10265-10271, 10273-10282,…" | pre-release | flows |  |
| 51 | "42 \| 95 \| `runner/runner.py:_finish_remediation` \| 3249-3250, 3258-3259,…" | pre-release | flows |  |
| 52 | "41 \| 134 \| `runner/runner.py:_run_oracle_tool` \| 1675, 1693-1694,…" | pre-release | flows |  |
| 53 | "41 \| 96 \| `runner/runner.py:run_variant` \| 7607-7612, 7614-7615,…" | pre-release | flows |  |
| 54 | "40 \| 66 \| `runner/cloud/send_job.py:cmd_new` \| 233, 235,…" | pre-release | flows |  |
| 55 | "38 \| 63 \| `runner/runner.py:_job_user_preexec` \| 447-449, 451-452,…" | pre-release | flows |  |
| 56 | "35 \| 133 \| `runner/wire/verify.py:build_key_policies` \| 274, 281,…" | pre-release | flows |  |
| 57 | "33 \| 672 \| `runner/runner.py:main` \| 10691, 10695,…" | pre-release | flows |  |
| 58 | "31 \| 48 \| `runner/runner.py:_disk_owns.mutate` \| 6755-6757, 6759-6783,…" | pre-release | flows |  |
| 59 | "30 \| 41 \| `runner/extensions/service-watch/service_watch.py:read_live` \| 95-106, 108-115,…" | pre-release | flows |  |
| 60 | "29 \| 196 \| `runner/runner.py:ask_model_agent` \| 2112, 2114,…" | pre-release | flows |  |
| 61 | "28 \| 49 \| `runner/extensions/job-fuzz/job_fuzz.py:_deliver_local` \| 1365-1366, 1368-1373,…" | pre-release | flows |  |
| 62 | "28 \| 71 \| `runner/wire/protocol_v2.py:await_answer` \| 483, 487-488,…" | pre-release | flows |  |
| 63 | "27 \| 48 \| `runner/extensions/aide-feed/aide_feed.py:_deliver_local` \| 310-311, 313-318,…" | pre-release | flows |  |
| 64 | "27 \| 47 \| `runner/extensions/job-watcher/job_watcher.py:_deliver_local` \| 635-636, 638-643,…" | pre-release | flows |  |
| 65 | "27 \| 47 \| `runner/extensions/latency-post/latency_post.py:_deliver_local` \| 303-304, 306-311,…" | pre-release | flows |  |
| 66 | "27 \| 47 \| `runner/extensions/release-drop/release_drop.py:_deliver_local` \| 267-268, 270-275,…" | pre-release | flows |  |
| 67 | "27 \| 48 \| `runner/extensions/resource-sentinel/resource_sentinel.py:_deliver_local` \| 394-395, 397-402,…" | pre-release | flows |  |
| 68 | "27 \| 47 \| `runner/extensions/sky-watcher/sky_watcher.py:_deliver_local` \| 534-535, 537-542,…" | pre-release | flows |  |
| 69 | "27 \| 48 \| `runner/extensions/softflowd-feed/softflowd_feed.py:_deliver_local` \| 727-728, 730-735,…" | pre-release | flows |  |
| 70 | "27 \| 48 \| `runner/extensions/suricata-feed/suricata_feed.py:_deliver_local` \| 423-424, 426-431,…" | pre-release | flows |  |
| 71 | "27 \| 48 \| `runner/extensions/sysmon-feed/sysmon_feed.py:_deliver_local` \| 478-479, 481-486,…" | pre-release | flows |  |
| 72 | "27 \| 48 \| `runner/extensions/training-watch/training_watch.py:_deliver_local` \| 703-704, 706-711,…" | pre-release | flows |  |
| 73 | "27 \| 48 \| `runner/extensions/wazuh-feed/wazuh_feed.py:_deliver_local` \| 391-392, 394-399,…" | pre-release | flows |  |
| 74 | "27 \| 54 \| `runner/extensions/zeek-feed/zeek_feed.py:_deliver_local` \| 516-523, 528-531,…" | pre-release | flows |  |
| 75 | "27 \| 53 \| `runner/oracle/personal_docs.py:personal_documents_present` \| 237, 242-243,…" | pre-release | flows |  |
| 76 | "27 \| 37 \| `runner/transport_extensions/file/__main__.py:FilePipe.scan_results` \| 146-147, 149-156,…" | pre-release | flows |  |
| 77 | "26 \| 249 \| `runner/runner.py:execute_job` \| 3395, 3434,…" | pre-release | flows |  |
| 78 | "24 \| 25 \| `runner/oracle/personal_docs.py:_walk` \| 200-223" | pre-release | flows |  |
| 79 | "24 \| 27 \| `runner/runner.py:_pid_alive` \| 6604-6615, 6617-6628" | pre-release | flows |  |
| 80 | "23 \| 109 \| `runner/extensions/job-fuzz/job_fuzz.py:main` \| 1460-1461, 1463,…" | pre-release | flows |  |
| 81 | "22 \| 28 \| `runner/transport_extensions/email/__main__.py:EmailPipe.flush_results` \| 167-173, 175-177,…" | pre-release | flows |  |
| 82 | "21 \| 25 \| `runner/oracle/personal_docs.py:_sensitive` \| 124-126, 129-133,…" | pre-release | flows |  |
| 83 | "20 \| 68 \| `runner/ops/posture.py:_windows_file_restricted` \| 210, 218,…" | pre-release | flows |  |
| 84 | "20 \| 27 \| `runner/oracle/learning.py:_trim_locked` \| 271-272, 275-285,…" | pre-release | flows |  |
| 85 | "20 \| 38 \| `runner/runner.py:_reg_query` \| 8082, 8088-8096,…" | pre-release | flows |  |
| 86 | "20 \| 226 \| `runner/runner.py:answer_queries` \| 2331, 2360,…" | pre-release | flows |  |
| 87 | "20 \| 33 \| `runner/transport_extensions/email/__main__.py:EmailPipe.pass_once` \| 98-105, 108,…" | pre-release | flows |  |
| 88 | "19 \| 35 \| `runner/extensions/latency-post/latency_post.py:_probe` \| 119-126, 128,…" | pre-release | flows |  |
| 89 | "19 \| 32 \| `runner/oracle/learning.py:_fact_agrees` \| 600, 603,…" | pre-release | flows |  |
| 90 | "19 \| 29 \| `runner/oracle/personal_docs.py:_xdg_dirs` \| 176-178, 181-196" | pre-release | flows |  |
| 91 | "19 \| 68 \| `runner/runner.py:_v2_ingest` \| 5802, 5806,…" | pre-release | flows |  |
| 92 | "19 \| 28 \| `runner/wire/protocol_v2.py:_other_answers` \| 431-432, 437,…" | pre-release | flows |  |
| 93 | "18 \| 47 \| `runner/extensions/backup-freshness/backup_freshness.py:_deliver_local` \| 263, 266-267,…" | pre-release | flows |  |
| 94 | "18 \| 47 \| `runner/extensions/cert-sentinel/cert_sentinel.py:_deliver_local` \| 375, 378-379,…" | pre-release | flows |  |
| 95 | "18 \| 48 \| `runner/extensions/failed-login-watch/failed_login_watch.py:_deliver_local` \| 356, 359-360,…" | pre-release | flows |  |
| 96 | "18 \| 48 \| `runner/extensions/log-sentinel/log_sentinel.py:_deliver_local` \| 371, 374-375,…" | pre-release | flows |  |
| 97 | "18 \| 47 \| `runner/extensions/port-watch/port_watch.py:_deliver_local` \| 304, 307-308,…" | pre-release | flows |  |
| 98 | "18 \| 47 \| `runner/extensions/service-watch/service_watch.py:_deliver_local` \| 332, 335-336,…" | pre-release | flows |  |
| 99 | "17 \| 26 \| `runner/cloud/send_job.py:cmd_verify` \| 315-318, 323-324,…" | pre-release | flows |  |
| 100 | "17 \| 26 \| `runner/extensions/latency-post/latency_post.py:_read_default_gateway` \| 90-106" | pre-release | flows |  |
| 101 | "17 \| 129 \| `runner/ops/extsources.py:_small_parts` \| 1482, 1484,…" | pre-release | flows |  |
| 102 | "17 \| 154 \| `runner/oracle/dri.py:evaluate_page_triggers` \| 302-304, 312,…" | pre-release | flows |  |
| 103 | "17 \| 60 \| `runner/runner.py:_remediation_confinement_followup` \| 3340, 3348,…" | pre-release | flows |  |
| 104 | "17 \| 38 \| `runner/runner.py:_v2_hand_off` \| 5769-5778, 5781-5785,…" | pre-release | flows |  |
| 105 | "17 \| 43 \| `runner/transport_extensions/dtls/__main__.py:main` \| 292, 294,…" | pre-release | flows |  |
| 106 | "17 \| 70 \| `runner/wire/transports.py:service_channel` \| 498, 506,…" | pre-release | flows |  |
| 107 | "16 \| 56 \| `runner/runner.py:_with_seen_file` \| 6645, 6657-6658,…" | pre-release | flows |  |
| 108 | "16 \| 95 \| `runner/runner.py:handle_board_mail` \| 4324-4325, 4331,…" | pre-release | flows |  |
| 109 | "16 \| 47 \| `runner/transport_extensions/file/__main__.py:FilePipe.scan_jobs` \| 96, 98-99,…" | pre-release | flows |  |
| 110 | "Covered \| Statements \| Missed \| Module" | pre-release | flows |  |
| 111 | "26% \| 173 \| 116 \| `runner/oracle/personal_docs.py`" | pre-release | flows |  |
| 112 | "41% \| 123 \| 68 \| `runner/transport_extensions/email/__main__.py`" | pre-release | flows |  |
| 113 | "45% \| 142 \| 76 \| `runner/transport_extensions/file/__main__.py`" | pre-release | flows |  |
| 114 | "63% \| 238 \| 77 \| `runner/ops/posture.py`" | pre-release | flows |  |
| 115 | "63% \| 353 \| 114 \| `runner/wire/protocol_v2.py`" | pre-release | flows |  |
| 116 | "64% \| 295 \| 90 \| `runner/cloud/send_job.py`" | pre-release | flows |  |
| 117 | "69% \| 229 \| 72 \| `runner/extensions/latency-post/latency_post.py`" | pre-release | flows |  |
| 118 | "69% \| 390 \| 103 \| `runner/oracle/learning.py`" | pre-release | flows |  |
| 119 | "73% \| 153 \| 38 \| `runner/cloud/send_dtls.py`" | pre-release | flows |  |
| 120 | "74% \| 237 \| 49 \| `runner/ops/setup.py`" | pre-release | flows |  |
| 121 | "76% \| 228 \| 48 \| `runner/transport_extensions/nats/__main__.py`" | pre-release | flows |  |
| 122 | "78% \| 540 \| 113 \| `runner/wire/transports.py`" | pre-release | flows |  |
| 123 | "78% \| 178 \| 37 \| `runner/transport_extensions/dtls/__main__.py`" | pre-release | flows |  |
| 124 | "80% \| 249 \| 53 \| `runner/extensions/service-watch/service_watch.py`" | pre-release | flows |  |
| 125 | "80% \| 6410 \| 1188 \| `runner/runner.py`" | pre-release | flows |  |
| 126 | "81% \| 805 \| 142 \| `runner/extensions/job-fuzz/job_fuzz.py`" | pre-release | flows |  |
| 127 | "81% \| 461 \| 80 \| `runner/wire/verify.py`" | pre-release | flows |  |
| 128 | "82% \| 204 \| 38 \| `runner/extensions/release-drop/release_drop.py`" | pre-release | flows |  |
| 129 | "82% \| 249 \| 45 \| `runner/extensions/resource-sentinel/resource_sentinel.py`" | pre-release | flows |  |
| 130 | "82% \| 241 \| 46 \| `runner/extensions/aide-feed/aide_feed.py`" | pre-release | flows |  |
| 131 | "82% \| 44 \| 6 \| `runner/wire/platformcard.py`" | pre-release | flows |  |
| 132 | "83% \| 54 \| 7 \| `runner/guard/defaulted.py`" | pre-release | flows |  |
| 133 | "84% \| 232 \| 35 \| `runner/wire/oauth.py`" | pre-release | flows |  |
| 134 | "85% \| 338 \| 45 \| `runner/extensions/sky-watcher/sky_watcher.py`" | pre-release | flows |  |
| 135 | "85% \| 394 \| 52 \| `runner/extensions/job-watcher/job_watcher.py`" | pre-release | flows |  |
| 136 | "85% \| 269 \| 39 \| `runner/extensions/wazuh-feed/wazuh_feed.py`" | pre-release | flows |  |
| 137 | "86% \| 293 \| 40 \| `runner/extensions/suricata-feed/suricata_feed.py`" | pre-release | flows |  |
| 138 | "87% \| 473 \| 54 \| `runner/extensions/softflowd-feed/softflowd_feed.py`" | pre-release | flows |  |
| 139 | "87% \| 341 \| 43 \| `runner/extensions/sysmon-feed/sysmon_feed.py`" | pre-release | flows |  |
| 140 | "87% \| 236 \| 27 \| `runner/extensions/cert-sentinel/cert_sentinel.py`" | pre-release | flows |  |
| 141 | "88% \| 194 \| 24 \| `runner/extensions/backup-freshness/backup_freshness.py`" | pre-release | flows |  |
| 142 | "88% \| 191 \| 21 \| `runner/wire/mailbox.py`" | pre-release | flows |  |
| 143 | "88% \| 412 \| 52 \| `runner/extensions/training-watch/training_watch.py`" | pre-release | flows |  |
| 144 | "89% \| 311 \| 29 \| `runner/oracle/senses.py`" | pre-release | flows |  |
| 145 | "89% \| 355 \| 39 \| `runner/extensions/zeek-feed/zeek_feed.py`" | pre-release | flows |  |
| 146 | "89% \| 100 \| 9 \| `runner/transport_extensions/channel.py`" | pre-release | flows |  |
| 147 | "89% \| 273 \| 29 \| `runner/extensions/failed-login-watch/failed_login_watch.py`" | pre-release | flows |  |
| 148 | "89% \| 1391 \| 131 \| `runner/ops/extsources.py`" | pre-release | flows |  |
| 149 | "90% \| 223 \| 22 \| `runner/extensions/port-watch/port_watch.py`" | pre-release | flows |  |
| 150 | "90% \| 166 \| 16 \| `runner/extensions/lab-results/lab_results.py`" | pre-release | flows |  |
| 151 | "91% \| 287 \| 26 \| `runner/extensions/log-sentinel/log_sentinel.py`" | pre-release | flows |  |
| 152 | "91% \| 292 \| 23 \| `runner/wire/board.py`" | pre-release | flows |  |
| 153 | "92% \| 157 \| 8 \| `runner/oracle/review.py`" | pre-release | flows |  |
| 154 | "92% \| 407 \| 37 \| `runner/oracle/dri.py`" | pre-release | flows |  |
| 155 | "92% \| 264 \| 18 \| `runner/ops/extensions.py`" | pre-release | flows |  |
| 156 | "92% \| 235 \| 17 \| `runner/extensions/usb-arrivals/usb_arrivals.py`" | pre-release | flows |  |
| 157 | "92% \| 232 \| 16 \| `runner/guard/security.py`" | pre-release | flows |  |
| 158 | "92% \| 276 \| 22 \| `runner/extensions/pi-health/pi_health.py`" | pre-release | flows |  |
| 159 | "93% \| 194 \| 16 \| `runner/oracle/resources.py`" | pre-release | flows |  |
| 160 | "93% \| 231 \| 16 \| `runner/ops/auditreport.py`" | pre-release | flows |  |
| 161 | "93% \| 50 \| 3 \| `runner/guard/confval.py`" | pre-release | flows |  |
| 162 | "93% \| 290 \| 20 \| `runner/extensions/osquery-feed/osquery_feed.py`" | pre-release | flows |  |
| 163 | "93% \| 431 \| 28 \| `runner/extensions/airwaves/airwaves.py`" | pre-release | flows |  |
| 164 | "94% \| 278 \| 17 \| `runner/extensions/falco-feed/falco_feed.py`" | pre-release | flows |  |
| 165 | "94% \| 214 \| 14 \| `runner/extensions/crash-watch/crash_watch.py`" | pre-release | flows |  |
| 166 | "94% \| 138 \| 6 \| `runner/guard/sandbox.py`" | pre-release | flows |  |
| 167 | "95% \| 245 \| 13 \| `runner/extensions/wire-arrivals/wire_arrivals.py`" | pre-release | flows |  |
| 168 | "95% \| 176 \| 8 \| `runner/oracle/detection.py`" | pre-release | flows |  |
| 169 | "95% \| 232 \| 13 \| `runner/extensions/tripwire/tripwire.py`" | pre-release | flows |  |
| 170 | "95% \| 309 \| 10 \| `runner/oracle/opinion.py`" | pre-release | flows |  |
| 171 | "95% \| 179 \| 7 \| `runner/wire/jobcrypto.py`" | pre-release | flows |  |
| 172 | "95% \| 34 \| 1 \| `runner/ops/winlog.py`" | pre-release | flows |  |
| 173 | "97% \| 1091 \| 17 \| `runner/wire/dtlsproto.py`" | pre-release | flows |  |
| 174 | "97% \| 1820 \| 38 \| `runner/ops/install.py`" | pre-release | flows |  |
| 175 | "99% \| 853 \| 3 \| `runner/oracle/remediation.py`" | pre-release | flows |  |
