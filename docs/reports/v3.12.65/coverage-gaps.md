# Coverage gaps: the code no test has run

<!-- Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c -->

This report belongs to package 3.12.65. It answers the owner's
question of 2026-10-24: the project is two weeks old, the campaign
rig has tested it hard for two days, so where was it never tested?
History shows where bugs were fixed. This shows where no test has
ever executed a line, which is where the next bugs are and where the
next campaign should aim.

## How it was measured

The full suite (5,695 tests) was run on Linux under coverage.py
7.6.1 with branch coverage on, and with every child process
measured too (the runner, the transport extensions and the sense
extensions do their real work in subprocesses). Only shipped code
counts: `runner/` without `runner/tests/` and `runner/tools/`. The
function table is produced by `runner/tools/coverage_gaps.py`, which
attributes each never-executed line to the function that owns it
(nested functions counted separately), so every row is a single
target a test can be written against.

From now on `.github/workflows/coverage.yml` produces the same
report on every push to main, on Linux and on Windows, uploads it as
`coverage-Linux` and `coverage-Windows`, and annotates the run page
with the totals and the ten largest gaps. It is a signal, not a
gate: it never blocks a build or a release.

**Limit of this snapshot.** It is the Linux map. Code that runs only
on Windows (registry reads, `icacls` checks, the Windows service,
PowerShell job paths, `taskkill`) shows here as never executed even
where the Windows CI shards do run it. The first `coverage-Windows`
artifact is the other half; until it is read, treat a Windows-only
row below as unknown, not as untested.

## Where it matters, ranked by what a user loses if it is wrong

The table further down is ordered by how many lines never ran. This
list is ordered by harm. Each item is filed as a question for the
campaign in `docs/use/questions.md` (Q11 to Q17), with what a test
has to make run and what it has to assert.

1. **The email transport extension: 41% covered** (Q11). Email is the
   default transport, the one nearly every install uses, and
   `pass_once` (20 of 33 lines) and `flush_results` (22 lines), the
   code that picks jobs up and sends results back, have never run in
   a test. The campaign drove everything through the file inbox
   because its VM cannot reach a mailbox. A broken result send here
   means a job runs and nobody hears the answer; a broken pickup
   means jobs are ignored.
2. **Running a job as another user, `_job_user_preexec`: 38 of 63 lines
   never ran** (Q12). This is the privilege drop behind
   `security.modes.job_user`, the one feature that would make the job
   a different principal from the runner (the plan's open decision
   2). The untested lines are the group, supplementary-group and uid
   changes and their error handling: if they are wrong, the job keeps
   the runner's own identity, which is exactly what the feature
   exists to prevent.
3. **Stopping a job that is going bad, `_finish_remediation`: 42 of 95
   lines never ran** (Q13). The kill, the cleanup and the report of a
   remediated job. The decision to remediate is tested; acting on it
   is not.
4. **Every sense extension's alert delivery, `_deliver_local`: about 27
   lines in each of 13 extensions** (Q14). The campaign hunted each
   extension's decision logic through fifteen shapes, but never the
   step that hands the finished alert to the runner (signing it,
   writing it to the local inbox or socket). If that step breaks,
   the extension decides correctly and the runner never hears.
5. **The Oracle agent's tool calls and loop** (Q15):
   `_run_oracle_tool` (41 of 134 lines) and `ask_model_agent` (29 of
   196). This is where a model's output is untrusted input, the same
   class as job JSON; the untested lines are the error and refusal
   branches, which are the ones that matter when the model misbehaves.
6. **The personal-documents warning, `oracle/personal_docs.py`: 26%
   covered** (Q16). The check that warns before a box with personal
   files in reach is used for jobs. `_walk`, `_sensitive` and
   `_xdg_dirs` barely run. A bug here is a privacy failure that
   looks like silence.
7. **Protocol v2 waiting for an answer, and the cloud sender** (Q17):
   `protocol_v2.await_answer` (28 of 71) and `send_job.py cmd_new`
   (40 of 66), the command a cloud SI uses to build a job. The answer
   window and the job builder are both on the path every v2 job and
   every hand-sent job takes.

Not ranked, worth knowing: `oracle_cli` (75 of 109, the loopback chat
UI), `run_variant` and `_disk_owns.mutate` (the diagnostic and
mutation tooling inside the runner), `main` (33 of 672, mostly flag
combinations), and `verify.build_key_policies` (35 of 133, the
refusal branches of key policies, already in the refuse class and
partly hunted by the table hunt).

## What the campaign should do with this

The shape that worked for the documented-default hunt works here:
the map is the registry. For each row the campaign writes a test
that makes the lines run through the public seam (a job, a config,
a transport envelope, an extension's main), asserts what the docs
promise those lines do, and files anything that disagrees as a
finding. A test that cannot reach the lines without mocking the
world is itself a finding: the seam is missing.

## The Linux map, 2026-10-24
Statements 29005, never executed 4398; branches 12937, never taken 2472; 83.6% covered overall (shipped code only: runner/ without tests/ and tools/).

## Functions with the most never-executed lines

Lines counted are the function's own, nested functions excluded. Each row is a hunt target: a test that makes these lines run, and asserts what the docs say they do.

| Missed | Of | Function | Never-executed lines |
|---:|---:|---|---|
| 75 | 109 | `runner/runner.py:oracle_cli` | 10265-10271, 10273-10282, 10284-10286, 10288, 10290, 10292-10294, 10296-10313, 10316-10319, 10321-10322, 10331-10341, 10343, 10345-10346, 10348, 10351-10354, 10356, 10359-10364 |
| 42 | 95 | `runner/runner.py:_finish_remediation` | 3249-3250, 3258-3259, 3264-3266, 3269, 3272, 3278-3279, 3282-3286, 3290, 3292-3295, 3298, 3301-3311, 3313-3317, 3319-3320, 3324, 3326 |
| 41 | 134 | `runner/runner.py:_run_oracle_tool` | 1675, 1693-1694, 1701-1702, 1705, 1715, 1720-1721, 1730-1731, 1734, 1742, 1749, 1758, 1766-1767, 1769-1781, 1785-1795 |
| 41 | 96 | `runner/runner.py:run_variant` | 7607-7612, 7614-7615, 7617-7619, 7621-7622, 7625-7627, 7630-7639, 7641-7643, 7648-7650, 7654, 7666-7669, 7671-7674 |
| 40 | 66 | `runner/cloud/send_job.py:cmd_new` | 233, 235, 237, 239-268, 279-285 |
| 38 | 63 | `runner/runner.py:_job_user_preexec` | 447-449, 451-452, 454-459, 461-462, 464-470, 474-487, 489-491, 501 |
| 35 | 133 | `runner/wire/verify.py:build_key_policies` | 274, 281, 327-328, 330, 333, 335-336, 338, 341, 347, 349-350, 352, 355, 359-360, 363, 365-366, 368, 371, 373-375, 378-381, 387-391, 394 |
| 33 | 672 | `runner/runner.py:main` | 10691, 10695, 10764, 10784, 10790-10791, 10793-10795, 10797-10798, 10801-10803, 10807, 10814, 10816, 10836-10838, 10841-10844, 10847-10850, 10874, 10939-10940, 10983-10984 |
| 31 | 48 | `runner/runner.py:_disk_owns.mutate` | 6755-6757, 6759-6783, 6786-6788 |
| 30 | 41 | `runner/extensions/service-watch/service_watch.py:read_live` | 95-106, 108-115, 117-124, 126-127 |
| 29 | 196 | `runner/runner.py:ask_model_agent` | 2112, 2114, 2117-2121, 2123, 2187-2190, 2194, 2203, 2213-2214, 2216-2217, 2219, 2227, 2235, 2247-2248, 2260, 2262, 2264-2265, 2286-2287 |
| 28 | 49 | `runner/extensions/job-fuzz/job_fuzz.py:_deliver_local` | 1365-1366, 1368-1373, 1376-1380, 1383-1386, 1390-1392, 1394, 1396, 1398-1399, 1401-1403, 1405 |
| 28 | 71 | `runner/wire/protocol_v2.py:await_answer` | 483, 487-488, 491, 496-497, 530-548, 556-558 |
| 27 | 48 | `runner/extensions/aide-feed/aide_feed.py:_deliver_local` | 310-311, 313-318, 321-324, 327-330, 334-336, 338, 340, 342-343, 345-347, 349 |
| 27 | 47 | `runner/extensions/job-watcher/job_watcher.py:_deliver_local` | 635-636, 638-643, 646-649, 651-654, 658-660, 662, 664, 666-667, 669-671, 673 |
| 27 | 47 | `runner/extensions/latency-post/latency_post.py:_deliver_local` | 303-304, 306-311, 314-317, 319-322, 326-328, 330, 332, 334-335, 337-339, 341 |
| 27 | 47 | `runner/extensions/release-drop/release_drop.py:_deliver_local` | 267-268, 270-275, 278-281, 283-286, 290-292, 294, 296, 298-299, 301-303, 305 |
| 27 | 48 | `runner/extensions/resource-sentinel/resource_sentinel.py:_deliver_local` | 394-395, 397-402, 405-408, 411-414, 418-420, 422, 424, 426-427, 429-431, 433 |
| 27 | 47 | `runner/extensions/sky-watcher/sky_watcher.py:_deliver_local` | 534-535, 537-542, 545-548, 550-553, 557-559, 561, 563, 565-566, 568-570, 572 |
| 27 | 48 | `runner/extensions/softflowd-feed/softflowd_feed.py:_deliver_local` | 727-728, 730-735, 738-741, 744-747, 751-753, 755, 757, 759-760, 762-764, 766 |
| 27 | 48 | `runner/extensions/suricata-feed/suricata_feed.py:_deliver_local` | 423-424, 426-431, 434-437, 440-443, 447-449, 451, 453, 455-456, 458-460, 462 |
| 27 | 48 | `runner/extensions/sysmon-feed/sysmon_feed.py:_deliver_local` | 478-479, 481-486, 489-492, 495-498, 502-504, 506, 508, 510-511, 513-515, 517 |
| 27 | 48 | `runner/extensions/training-watch/training_watch.py:_deliver_local` | 703-704, 706-711, 714-717, 720-723, 727-729, 731, 733, 735-736, 738-740, 742 |
| 27 | 48 | `runner/extensions/wazuh-feed/wazuh_feed.py:_deliver_local` | 391-392, 394-399, 402-405, 408-411, 415-417, 419, 421, 423-424, 426-428, 430 |
| 27 | 54 | `runner/extensions/zeek-feed/zeek_feed.py:_deliver_local` | 516-523, 528-531, 536-539, 547-550, 552-554, 558-561 |
| 27 | 53 | `runner/oracle/personal_docs.py:personal_documents_present` | 237, 242-243, 247, 250-261, 264-265, 267, 270-277 |
| 27 | 37 | `runner/transport_extensions/file/__main__.py:FilePipe.scan_results` | 146-147, 149-156, 158-167, 174-176, 178-181 |
| 26 | 249 | `runner/runner.py:execute_job` | 3395, 3434, 3451, 3466-3467, 3469, 3486, 3494-3496, 3498, 3503, 3507, 3531-3532, 3581-3582, 3595-3596, 3611, 3614-3615, 3627-3629, 3638 |
| 24 | 25 | `runner/oracle/personal_docs.py:_walk` | 200-223 |
| 24 | 27 | `runner/runner.py:_pid_alive` | 6604-6615, 6617-6628 |
| 23 | 109 | `runner/extensions/job-fuzz/job_fuzz.py:main` | 1460-1461, 1463, 1466, 1468, 1470-1473, 1477, 1484-1485, 1487, 1492, 1495-1498, 1501, 1505, 1512-1513, 1515 |
| 22 | 28 | `runner/transport_extensions/email/__main__.py:EmailPipe.flush_results` | 167-173, 175-177, 180-181, 183-188, 190-193 |
| 21 | 25 | `runner/oracle/personal_docs.py:_sensitive` | 124-126, 129-133, 135-147 |
| 20 | 68 | `runner/ops/posture.py:_windows_file_restricted` | 210, 218, 222-233, 235-240 |
| 20 | 27 | `runner/oracle/learning.py:_trim_locked` | 271-272, 275-285, 287-293 |
| 20 | 38 | `runner/runner.py:_reg_query` | 8082, 8088-8096, 8098-8104, 8106-8108 |
| 20 | 226 | `runner/runner.py:answer_queries` | 2331, 2360, 2391, 2403, 2421, 2427, 2431-2432, 2444-2447, 2452, 2470-2472, 2476, 2495, 2498, 2518 |
| 20 | 33 | `runner/transport_extensions/email/__main__.py:EmailPipe.pass_once` | 98-105, 108, 113, 115-118, 122, 124, 126-129 |
| 19 | 35 | `runner/extensions/latency-post/latency_post.py:_probe` | 119-126, 128, 130-131, 133-134, 137-142 |
| 19 | 32 | `runner/oracle/learning.py:_fact_agrees` | 600, 603, 605-607, 612, 614-626 |
| 19 | 29 | `runner/oracle/personal_docs.py:_xdg_dirs` | 176-178, 181-196 |
| 19 | 68 | `runner/runner.py:_v2_ingest` | 5802, 5806, 5816-5817, 5820, 5840-5841, 5845-5847, 5850-5853, 5856-5860 |
| 19 | 28 | `runner/wire/protocol_v2.py:_other_answers` | 431-432, 437, 440-455 |
| 18 | 47 | `runner/extensions/backup-freshness/backup_freshness.py:_deliver_local` | 263, 266-267, 270, 276-278, 282-284, 286, 288, 290-291, 293-295, 297 |
| 18 | 47 | `runner/extensions/cert-sentinel/cert_sentinel.py:_deliver_local` | 375, 378-379, 382, 388-390, 394-396, 398, 400, 402-403, 405-407, 409 |
| 18 | 48 | `runner/extensions/failed-login-watch/failed_login_watch.py:_deliver_local` | 356, 359-360, 363, 370-372, 376-378, 380, 382, 384-385, 387-389, 391 |
| 18 | 48 | `runner/extensions/log-sentinel/log_sentinel.py:_deliver_local` | 371, 374-375, 378, 385-387, 391-393, 395, 397, 399-400, 402-404, 406 |
| 18 | 47 | `runner/extensions/port-watch/port_watch.py:_deliver_local` | 304, 307-308, 311, 317-319, 323-325, 327, 329, 331-332, 334-336, 338 |
| 18 | 47 | `runner/extensions/service-watch/service_watch.py:_deliver_local` | 332, 335-336, 339, 345-347, 351-353, 355, 357, 359-360, 362-364, 366 |
| 17 | 26 | `runner/cloud/send_job.py:cmd_verify` | 315-318, 323-324, 327-328, 331-339 |
| 17 | 26 | `runner/extensions/latency-post/latency_post.py:_read_default_gateway` | 90-106 |
| 17 | 129 | `runner/ops/extsources.py:_small_parts` | 1482, 1484, 1498-1499, 1512-1514, 1517, 1570-1572, 1574-1576, 1584-1586 |
| 17 | 154 | `runner/oracle/dri.py:evaluate_page_triggers` | 302-304, 312, 375-380, 383-389 |
| 17 | 60 | `runner/runner.py:_remediation_confinement_followup` | 3340, 3348, 3350, 3352, 3361-3373 |
| 17 | 38 | `runner/runner.py:_v2_hand_off` | 5769-5778, 5781-5785, 5787-5788 |
| 17 | 43 | `runner/transport_extensions/dtls/__main__.py:main` | 292, 294, 304, 312-314, 318-323, 325-329 |
| 17 | 70 | `runner/wire/transports.py:service_channel` | 498, 506, 509, 512-514, 517-520, 526-527, 529, 531-534 |
| 16 | 56 | `runner/runner.py:_with_seen_file` | 6645, 6657-6658, 6666-6669, 6673, 6676-6677, 6682-6683, 6687-6688, 6691-6692 |
| 16 | 95 | `runner/runner.py:handle_board_mail` | 4324-4325, 4331, 4341-4342, 4348, 4385-4388, 4390-4392, 4394-4396 |
| 16 | 47 | `runner/transport_extensions/file/__main__.py:FilePipe.scan_jobs` | 96, 98-99, 102-104, 106, 108, 112-114, 126-127, 131-132, 134 |

## Modules, least covered first

| Covered | Statements | Missed | Module |
|---:|---:|---:|---|
| 26% | 173 | 116 | `runner/oracle/personal_docs.py` |
| 41% | 123 | 68 | `runner/transport_extensions/email/__main__.py` |
| 45% | 142 | 76 | `runner/transport_extensions/file/__main__.py` |
| 63% | 238 | 77 | `runner/ops/posture.py` |
| 63% | 353 | 114 | `runner/wire/protocol_v2.py` |
| 64% | 295 | 90 | `runner/cloud/send_job.py` |
| 69% | 229 | 72 | `runner/extensions/latency-post/latency_post.py` |
| 69% | 390 | 103 | `runner/oracle/learning.py` |
| 73% | 153 | 38 | `runner/cloud/send_dtls.py` |
| 74% | 237 | 49 | `runner/ops/setup.py` |
| 76% | 228 | 48 | `runner/transport_extensions/nats/__main__.py` |
| 78% | 540 | 113 | `runner/wire/transports.py` |
| 78% | 178 | 37 | `runner/transport_extensions/dtls/__main__.py` |
| 80% | 249 | 53 | `runner/extensions/service-watch/service_watch.py` |
| 80% | 6410 | 1188 | `runner/runner.py` |
| 81% | 805 | 142 | `runner/extensions/job-fuzz/job_fuzz.py` |
| 81% | 461 | 80 | `runner/wire/verify.py` |
| 82% | 204 | 38 | `runner/extensions/release-drop/release_drop.py` |
| 82% | 249 | 45 | `runner/extensions/resource-sentinel/resource_sentinel.py` |
| 82% | 241 | 46 | `runner/extensions/aide-feed/aide_feed.py` |
| 82% | 44 | 6 | `runner/wire/platformcard.py` |
| 83% | 54 | 7 | `runner/guard/defaulted.py` |
| 84% | 232 | 35 | `runner/wire/oauth.py` |
| 85% | 338 | 45 | `runner/extensions/sky-watcher/sky_watcher.py` |
| 85% | 394 | 52 | `runner/extensions/job-watcher/job_watcher.py` |
| 85% | 269 | 39 | `runner/extensions/wazuh-feed/wazuh_feed.py` |
| 86% | 293 | 40 | `runner/extensions/suricata-feed/suricata_feed.py` |
| 87% | 473 | 54 | `runner/extensions/softflowd-feed/softflowd_feed.py` |
| 87% | 341 | 43 | `runner/extensions/sysmon-feed/sysmon_feed.py` |
| 87% | 236 | 27 | `runner/extensions/cert-sentinel/cert_sentinel.py` |
| 88% | 194 | 24 | `runner/extensions/backup-freshness/backup_freshness.py` |
| 88% | 191 | 21 | `runner/wire/mailbox.py` |
| 88% | 412 | 52 | `runner/extensions/training-watch/training_watch.py` |
| 89% | 311 | 29 | `runner/oracle/senses.py` |
| 89% | 355 | 39 | `runner/extensions/zeek-feed/zeek_feed.py` |
| 89% | 100 | 9 | `runner/transport_extensions/channel.py` |
| 89% | 273 | 29 | `runner/extensions/failed-login-watch/failed_login_watch.py` |
| 89% | 1391 | 131 | `runner/ops/extsources.py` |
| 90% | 223 | 22 | `runner/extensions/port-watch/port_watch.py` |
| 90% | 166 | 16 | `runner/extensions/lab-results/lab_results.py` |
| 91% | 287 | 26 | `runner/extensions/log-sentinel/log_sentinel.py` |
| 91% | 292 | 23 | `runner/wire/board.py` |
| 92% | 157 | 8 | `runner/oracle/review.py` |
| 92% | 407 | 37 | `runner/oracle/dri.py` |
| 92% | 264 | 18 | `runner/ops/extensions.py` |
| 92% | 235 | 17 | `runner/extensions/usb-arrivals/usb_arrivals.py` |
| 92% | 232 | 16 | `runner/guard/security.py` |
| 92% | 276 | 22 | `runner/extensions/pi-health/pi_health.py` |
| 93% | 194 | 16 | `runner/oracle/resources.py` |
| 93% | 231 | 16 | `runner/ops/auditreport.py` |
| 93% | 50 | 3 | `runner/guard/confval.py` |
| 93% | 290 | 20 | `runner/extensions/osquery-feed/osquery_feed.py` |
| 93% | 431 | 28 | `runner/extensions/airwaves/airwaves.py` |
| 94% | 278 | 17 | `runner/extensions/falco-feed/falco_feed.py` |
| 94% | 214 | 14 | `runner/extensions/crash-watch/crash_watch.py` |
| 94% | 138 | 6 | `runner/guard/sandbox.py` |
| 95% | 245 | 13 | `runner/extensions/wire-arrivals/wire_arrivals.py` |
| 95% | 176 | 8 | `runner/oracle/detection.py` |
| 95% | 232 | 13 | `runner/extensions/tripwire/tripwire.py` |
| 95% | 309 | 10 | `runner/oracle/opinion.py` |
| 95% | 179 | 7 | `runner/wire/jobcrypto.py` |
| 95% | 34 | 1 | `runner/ops/winlog.py` |
| 97% | 1091 | 17 | `runner/wire/dtlsproto.py` |
| 97% | 1820 | 38 | `runner/ops/install.py` |
| 99% | 853 | 3 | `runner/oracle/remediation.py` |
