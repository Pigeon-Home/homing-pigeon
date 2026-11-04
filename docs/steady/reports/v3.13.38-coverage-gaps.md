# Coverage gaps, 3.13.38 (Platinum cycle 5)

<!-- Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90 -->

Every function with two or more never-executed statements in the full
suite as measured on this rig at 40cc8733 (Linux, coverage.py run the
way `.github/workflows/coverage.yml` runs it: the `.pth` hook so child
processes count, `--rcfile=.github/coveragerc`, combine, json).
Classes are read from the AST by `runner/tools/coverage_targets.py`:
`logic` is the main flow, `guard` one early refusal, `except` a handler,
`platform` code for another OS, `shadowed` a def rebound later.
Project Platinum (standing orders, queue P) refreshes this table each
cycle. Cycle 5 closed 40 statements and 39 branch arcs against its
baseline (99.4% / 170 missing at 2006bdc2). The one live row is
execute_job's script-shape refusal and its staging trio, cycle 6's
first targets. Every other row is recorded dead, defensive, platform,
or the test legs seat's: `_scan_python`'s second except arm is a
Python 3.9-3.11 arm (Q42); `handle_board_mail`'s unknown-kind else
cannot fire (its subject regex admits only the four kinds the
branches above it handle); `send_telegram`'s re-dump return cannot
fire (the coercion above it leaves only strings); `load_alerts`'
severity except is guarded by the isinstance check above it;
`_read_throttled`'s int arm cannot fire (its regex admits only hex
digits); training-watch's float arm cannot fire (its loss grammar
admits only float-shaped strings); `decode_datagram`'s except arm
did not fire for any malformed datagram in cycle 4's battery (every
sub-parser length-checks its unpacks) and stands as the belt over
their braces; the oracle server's dumps fallback cannot fire for the
string payloads its handler builds. Five more single lines were
recorded dead by construction in cycle 5 and sit below this table's
threshold: send_job verify_body's shape check (the extractor
guarantees an object since Q61; the check is Q48's belt),
hosting cli.main's trailing return (argparse requires a subcommand
and the dispatch over them is exhaustive), job-fuzz
`_mut_blank_line`'s empty-lines guard (str.split never returns an
empty list), FlyMachines.ensure_app's trailing return (raise_for's
tail raises for every answer that reaches it), and load_retained's
commonpath arm (belt under the safe-id and islink guards above it).
The wire/ rows are the test legs seat's (40000e00), and the
platform rows are the other OS's.

statements 99.6% covered, 130 missing of 30283

| class | file:function | missing | branches | args |
|---|---|---:|---:|---|
| logic | `ops/exec.py:execute_job` L225 | 4 (346,491,492,493) | 2 | cfg, job, base_dir |
| logic | `ops/startup.py:handle_board_mail` L104 | 2 (166,167) | 1 | cfg, imap, smtp, seq, raw, subject, board, secrets, opts, base_dir |
| logic | `wire/dtlsproto.py:x25519` L157 | 2 (186,187) | 1 | scalar, u_bytes |
| logic | `wire/transports.py:discover_transport_extensions` L245 | 2 (285,290) | 4 | cfg, base_dir, log, event_sink |
| except | `guard/extreview.py:_scan_python` L324 | 3 (332,337,339) | 1 | rel, text, observed, findings, signals_in_code |
| except | `extensions/pi-health/pi_health.py:_read_throttled` L181 | 2 (203,204) | 0 |  |
| except | `extensions/softflowd-feed/softflowd_feed.py:decode_datagram` L374 | 2 (401,402) | 0 | data, templates, now, stats |
| except | `extensions/training-watch/training_watch.py:decide` L465 | 2 (611,612) | 0 | readings, manifest, state |
| except | `ops/oracle_server.py:make_oracle_server` L25 | 2 (184,185) | 1 | cfg, host, port, base_dir |
| except | `ops/oracle_server.py:Handler.do_POST` L116 | 2 (184,185) | 0 |  |
| except | `oracle/dri.py:send_telegram` L468 | 2 (486,487) | 0 | bot_token, chat_id, text |
| except | `oracle/senses.py:load_alerts` L379 | 2 (426,427) | 0 | base_dir, sensor, severity_floor, since, until, limit |
| except | `wire/protocol_v2.py:store_answer` L395 | 2 (424,425) | 0 | base_dir, obj |
| platform | `extensions/pi-health/pi_health.py:_mem_avail_pct_windows` L262 | 14 (270,271,273,274,286,287,288,290…) | 5 |  |
| platform | `oracle/remediation.py:sample_tree_windows` L458 | 2 (470,483) | 2 | root_pid |
