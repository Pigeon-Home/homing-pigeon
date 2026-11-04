# Coverage gaps, 3.13.42 (Platinum cycle 6)

<!-- Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90 -->

Every function with two or more never-executed statements in the full
suite as measured on this rig at 61d4c77e (Linux, coverage.py run the
way `.github/workflows/coverage.yml` runs it: the `.pth` hook so child
processes count, `--rcfile=.github/coveragerc`, combine, json).
Classes are read from the AST by `runner/tools/coverage_targets.py`:
`logic` is the main flow, `guard` one early refusal, `except` a handler,
`platform` code for another OS, `shadowed` a def rebound later.
Project Platinum (standing orders, queue P) refreshes this table each
cycle. Cycle 6 closed nine statements gross, five net, and three
branch arcs against its baseline (99.6% / 130 missing at 40cc8733):
execute_job's staging trio, answer_queries' non-object arm,
resend_stashed's base arm, the QueuePipe pair, and store_answer's
pair. Two pins the full-suite map does not credit stay live rows for
cycle 7: execute_job's script-shape refusal (346) and
_record_payload's payload arm (1939) — targeted runs drive both, and
the map is the score. Four rarely-hit arms the cycle-5 map showed
covered read missing again (zeek-feed main's 682 and 688,
personal_docs _walk's 209, verify_body_keyed's 743) and are recorded
as map wobble, watched next cycle. Eight more single lines were
recorded dead by construction in cycle 6 and sit below this table's
threshold: sun_elevation_deg's `ha < -180` arm (the modulo above it
bounds the hour angle to [-180, 180) first), sample_tree_ps's
fallback entry (the pid walk always yields the root itself),
save_seen's merge (the mutator only ever receives a dict),
ensure_inference_ready's hostless arm (the loopback check requires a
hostname before it), _oracle_instruction_kind's empty-words arm
(every politeness prefix ends with a space and the lead is rebuilt
from split words, so a word always remains), _clean_rel_path's
no-parts arm (split always yields a segment and bad ones refuse
first), the email transport _subject_body's raw-payload fallback
(compat32 falls back to the raw bytes itself, and multipart is
walked above it), and ask_model's second arm (for the dicts the
model call returns, the two checks cannot both pass). The earlier
recorded set stands: `_scan_python`'s second except arm is a
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
string payloads its handler builds; send_job verify_body's shape
check (the extractor guarantees an object since Q61; the check is
Q48's belt), hosting cli.main's trailing return (argparse requires a
subcommand and the dispatch over them is exhaustive), job-fuzz
`_mut_blank_line`'s empty-lines guard (str.split never returns an
empty list), FlyMachines.ensure_app's trailing return (raise_for's
tail raises for every answer that reaches it), and load_retained's
commonpath arm (belt under the safe-id and islink guards above it).
The wire/ rows are the test legs seat's (40000e00), and the
platform rows are the other OS's.

statements 99.6% covered, 125 missing of 30283

| class | file:function | missing | branches | args |
|---|---|---:|---:|---|
| logic | `extensions/zeek-feed/zeek_feed.py:main` L564 | 2 (682,688) | 1 | argv |
| logic | `ops/startup.py:handle_board_mail` L104 | 2 (166,167) | 1 | cfg, imap, smtp, seq, raw, subject, board, secrets, opts, base_dir |
| logic | `wire/dtlsproto.py:x25519` L157 | 2 (186,187) | 1 | scalar, u_bytes |
| logic | `wire/transports.py:discover_transport_extensions` L245 | 2 (285,290) | 4 | cfg, base_dir, log, event_sink |
| guard | `wire/verify.py:verify_body_keyed` L693 | 2 (717,743) | 2 | body_text, secrets |
| except | `guard/extreview.py:_scan_python` L324 | 3 (332,337,339) | 1 | rel, text, observed, findings, signals_in_code |
| except | `extensions/pi-health/pi_health.py:_read_throttled` L181 | 2 (203,204) | 0 |  |
| except | `extensions/softflowd-feed/softflowd_feed.py:decode_datagram` L374 | 2 (401,402) | 0 | data, templates, now, stats |
| except | `extensions/training-watch/training_watch.py:decide` L465 | 2 (611,612) | 0 | readings, manifest, state |
| except | `ops/oracle_server.py:make_oracle_server` L25 | 2 (184,185) | 1 | cfg, host, port, base_dir |
| except | `ops/oracle_server.py:Handler.do_POST` L116 | 2 (184,185) | 0 |  |
| except | `oracle/dri.py:send_telegram` L468 | 2 (486,487) | 0 | bot_token, chat_id, text |
| except | `oracle/senses.py:load_alerts` L379 | 2 (426,427) | 0 | base_dir, sensor, severity_floor, since, until, limit |
| platform | `extensions/pi-health/pi_health.py:_mem_avail_pct_windows` L262 | 14 (270,271,273,274,286,287,288,290…) | 5 |  |
| platform | `oracle/remediation.py:sample_tree_windows` L458 | 2 (470,483) | 2 | root_pid |
