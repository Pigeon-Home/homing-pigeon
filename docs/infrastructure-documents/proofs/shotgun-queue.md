# Shotgun test queue — fuzz-found bugs, last 5 days

Built 1-Nov-2026 from the git record on main and
runner/tests/de_dust/. Window: since 27-Oct-2026 00:00 PDT. Newest
first. Rule (the shotgun standard): each bug gets a creative family
of UP TO 50 new tests on this pass — never a single regression test,
never more than 50 per bug. Status: queued / in progress / done.

This file is the durable queue in the tree. It was rebuilt and
landed on main 2-Nov-2026; items 1 and 2 were completed 1-Nov-2026
and their test families landed on main with it (see the entries).

Excluded, not bugs: 31,394 corpus records retired 29–31 Oct alone
(31,172 redundant echoes of already-fixed families, 208 slow records
reclassified as fast, 14 promoted), plus the Oct 27–28 echo
retirements (123 + 44 slow echoes) — repeats and reclassifications,
no new defect. Bank and release commits are transport, not findings.

## Method (refinement, 1-Nov-2026)

Applied to every item on this queue, item 1 included:

1. PER-FIELD UNIT TESTS. Wherever an item touches a fielded surface —
   config fields above all — every field is enumerated and each field
   gets its own unit test. One test per field, not one test per bug.
   The enumeration counts toward the item's 50-test cap.
2. PER-TEST FUZZ JOB. For each of those unit tests, a fuzz job is
   actually run against the surface through the corpus machinery
   (de_dust targets / grow tooling). The fuzzing is executed, not
   just the static test written. Where a full rig fuzz job is out of
   reach, the closest real equivalent the repo tooling supports
   locally is run, and the record says exactly what ran.
3. WRITTEN PROOF IN THE REPO. The commit and the queue entry carry
   the proof of work: the unit tests are named, the fuzz execution is
   stated, and the procedure and protocol are described (corpus,
   targets, how the runs were driven, run counts). The write-up
   documents the rigor of the work in plain language. Fuzzing here
   is ordinary programming through combinatorics — systematically
   trying combinations a hand-written list would never reach — not
   exotic security magic, and the write-ups treat it that way.
4. BOOKENDS AND RUN LENGTHS (added 1-Nov-2026). Every fuzz routine
   and every generated family wraps its inputs with special
   characters at the front AND the back — every symbol on the ASCII
   table, plus NUL, tab, CR and LF, and symbol-only strings.
   Repetition counts are part of the sweep: runs of the odd
   character, and runs of ordinary characters with the odd one at
   the front, the back and the middle.

## The queue

### 1. Retained load answered a case-variant id with another job's record
- Found: 1-Nov-2026, Germany rig grow (race_state crash 9b26d146d86a0e08)
- Fixed: 4d4bf568 (31-Oct-2026) — load_retained checks the
  directory entry's exact name before reading
- Area: runner/runner.py load_retained / retained store
- Existing tests: runner/tests/test_retained_store.py
- Target: up to 50 new tests
- Status: done — 50 new tests (LoadRetainedCaseShotgunTest in
  test_retained_store.py): every case transform of five id shapes on
  the real filesystem and the simulated case-insensitive surface, the
  listing seam lying/failing/empty, extension tricks, boundary
  lengths (128/129), non-ASCII lookalikes, hostile and
  injection-shaped payloads, repetition, order and concurrency.
  Landed on main 2-Nov-2026 (db8f7254, c2235b1d); the file runs
  green (93 tests in the file; 150 across this item's and item 2's
  files together, 0 skipped), no live bug exposed, no production
  code changed.
- Proof of work (per the method section): per-field enumeration — the
  one config field governing this store, output_retention_days, has
  its own tests in RetainedExpiredTest (the _retention_days table,
  zero/negative/string readings, prune agreement); the family adds
  test_no_other_config_key_moves_the_retention_window. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target race_state --rounds
  400 --seed 20261101, run locally against the banked race_state
  corpus (94 entries; the mark/save/load_seen/load two-thread mix
  that produced the original crash). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 186, slowest try 66 ms — the case-alias
  crash did not recur. The grow's bookkeeping writes were not banked
  (banking is the rigs' hourly job). The same write-up is carried in
  the test file's class docstring in the repo.

### 2. Parity test demanded confinement records only; job_user's Windows audit record read as a break
- Found: 31-Oct-2026, Windows CI leg of 3.15.2
- Fixed: 4d4bf568 (same commit, second half) — audit_entry_is_audit_only
- Area: runner/tests/test_security_parity.py
- Target: up to 50 new tests
- Status: done — 50 new tests (AuditEntryShotgunTest in
  test_security_parity.py): the would_ prefix's exact edges, the one
  exact unsupported_platform string, case and Cyrillic-lookalike
  spellings of both fields, wrong types in either field, non-dict
  entries, the real record shape write_audit_entry emits, and
  injection-shaped text in the free fields; restructured inside the
  same cap to 18 hand-written seams, 18 generated per-feature tests,
  10 bookend sweeps and 4 run-length sweeps. Landed on main
  2-Nov-2026 (36460659, 8a36684a); the file runs 57/57 green,
  0 skipped, skip-registry gate green; no new skip reasons needed,
  no live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration —
  the acceptance rule reads exactly two fields, feature and
  decision; the feature field is enumerated against the whole
  FEATURES set (each of the six features in
  runner.guard.security.FEATURES × would_* acceptance,
  unsupported_platform verdict, denial bundle), and the record's
  remaining real fields (ts, reason, key_id, job_id, detail, mode)
  are pinned as inert by the full-record tests. Bookends: every
  string shape also gets bookended variants — all 32 printable
  ASCII symbols (string.punctuation) at the front and at the back,
  as singles, matched pairs, mismatched pairs and symbol-only
  strings, plus NUL, tab, CR and LF at both ends of both fields.
  Run lengths: ten ordinary characters then the odd one, ten of
  the odd one itself, runs at the front, the back and the middle.
  Fuzz executed: no de_dust target drives this test-harness rule,
  so the corpus machinery ran against the nearest target, secret —
  the target exercising runner/guard/security.py, the module that
  owns the mode set and writes the audit log —
  runner/tools/de_dust_corpus.py grow --target secret --rounds 400
  against the banked secret corpus (26 entries), twice: seed
  20261102 (0 crashes, 0 slow, slowest try 58 ms) and, for the
  bookend/run-length pass, seed 20261103 (0 crashes, 0 slow,
  slowest try 3 ms; the machinery's wrap and duplicate operators
  tried 32 and 29 times). The grows' bookkeeping writes were not
  banked (banking is the rigs' hourly job). The same write-up is
  carried in the test file's class docstring in the repo.

### 3. A second result for one job shares that job's target file
- Fixed: f97119aa (31-Oct-2026)
- Area: result delivery / target file naming
- Existing tests: the result-lifecycle tests (test_transport_queues.py,
  test_transport_shells.py)
- Target: up to 50 new tests
- Status: done — 50 new tests (SecondResultTargetShotgunTest in
  test_de_dust_corpus.py — the fix's own commit touched only
  runner/tools/de_dust_corpus.py, so the family lives with the
  checker's tests and pins the writer through the transports
  module): colliding stems in every channel mode, cleaned and
  case-variant names, poison files sharing a stem, the checker
  refusing both an extra and a missing sidecar, and the writer's
  suffix sequence and shared sidecar. Landed on main 2-Nov-2026
  (39438977); the file runs green (133 tests in the file,
  0 skipped), no live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration —
  the writer's surface is fielded (base_dir, name, job_subject,
  subject, body, ident_hint, target) and each field has its own
  test, ident_hint and target a second each for their type and
  emptiness edges; the checker's spec fields are enumerated by
  the hand-written file shapes and the generated per-mode tests.
  Bookends and run lengths per the method section, on every
  text surface (the ident hint, the result subject's id, the
  target, the body, the inbox file name). Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target stash --rounds
  400 --seed 20261104, run locally against the banked stash
  corpus (31 entries), and re-run at landing with the same
  result. Result: 400 rounds, 0 crashes, 0 slow, arcs unchanged
  at 20, slowest try about 50 ms — the shared-target miscount
  did not recur. The grow's bookkeeping writes were not banked
  (banking is the rigs' hourly job). The same write-up is
  carried in the test file's class docstring in the repo.

### 4. Result stays while it is still set aside (file transport)
- Fixed: e4c21957 (31-Oct-2026)
- Existing tests: test_transport_shells.py (35 in file)
- Target: up to 50 new tests
- Status: done — 50 new tests (FilePipeHeldResultShotgunTest in
  test_transport_shells.py): the file pipe no longer finishes a
  watched job whose result still sits in the channel's
  outbox/failed/ — held by the channel ident, held by the signed
  job id, one set-aside name holding two jobs, the refused
  sidecar alone not holding, a missing, empty or not-a-folder
  failed/, a directory entry named like a result, the set-aside
  file's content never read, release when the file goes away,
  and a real result still delivering while held. Landed on main
  2-Nov-2026 (13075bc1); the file runs green (85 tests in the
  file, 0 skipped), no live bug exposed, no production code
  changed.
- Proof of work (per the method section): per-field enumeration
  — the one parsed field is the set-aside file's name, read
  through ch.result_file_id, and its shapes are enumerated one
  by one (plain, collision-suffixed, zero and zero-padded
  suffixes, suffix shapes that do not parse, empty stems, case,
  trailing characters including the trailing newline the name
  pattern's end anchor admits, dotted and dashed stems, unicode
  stems, symbol-only stems, none and empty). Bookends: every
  printable ASCII symbol at the front and the back of the name,
  at the parser and, bar the path separator, at the pipe; the
  non-printing bookends (NUL, tab, CR, LF) at the parser. Run
  lengths: stems and suffix digit runs of 1, 5 and 10.
  Injection-shaped names are ordinary names. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261108, run locally against the banked
  channels corpus (11 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 142, slowest try 15 ms — the
  set-aside shape did not recur. The grow's bookkeeping writes
  were reverted, not banked (banking is the rigs' hourly job).
  The same write-up is carried in the test file's class
  docstring in the repo.

### 5. Refused result with no record stays until one can answer it
- Fixed: 2715bedc (31-Oct-2026)
- Existing tests: test_platinum_runner.py
- Target: up to 50 new tests
- Status: done — 50 new tests (RefusedNoRecordShotgunTest in
  test_platinum_runner.py): the stash walk's refusal shapes —
  the record-side and channel-side halves of the set-aside pair
  in every combination, a refused result with no record staying
  until a record can answer it, drained and undrained states,
  and the record read failing in every way a read can fail.
  Landed on main 2-Nov-2026 (85b00a6b); the file runs green
  (96 tests in the file, 0 skipped), no live bug exposed, no
  production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target race_stash
  --rounds 400 --seed 20261105, run locally against the banked
  race_stash corpus (63 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 193, slowest try 58 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 6. A result the listing cannot read does not finish the job
- Fixed: 4203d661 (31-Oct-2026)
- Existing tests: test_transport_queues.py (39 in file)
- Target: up to 50 new tests
- Status: done — 50 new tests (UnreadableResultShotgunTest in
  test_transport_queues.py): a result whose read fails is set
  aside with its refusal and never finishes the job — the
  read-error shapes (every OSError variant), the set-aside
  pair, the refusal reason's one-line shape, and the listing
  retried. Landed on main 2-Nov-2026 (8ba79990; authored in a
  parallel worktree and spliced beside item 7's family after a
  tail conflict); the file runs green (189 tests in the file
  with items 7 and 11 landed, 0 skipped), no live bug exposed,
  no production code changed.
- Proof of work (per the method section): per-field enumeration
  (channel, file-name stem, collision suffix, refusal-reason
  text and shape, content subject, content body bytes, pending
  key) and the bookend / run-length sweeps are carried in the
  class docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target stash --rounds
  400 --seed 20261109, run locally against the banked stash
  corpus (31 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 20, slowest try 63 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 7. A symlink result is not followed, and does not finish the job
- Fixed: ab721ef9 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (SymlinkResultShotgunTest in
  test_transport_queues.py): a result that is a symlink is
  refused unread and set aside with its refusal — links to a
  file, a directory, missing targets, chains and loops,
  absolute and relative targets, a forged envelope behind a
  link, links inside failed/, and traversal-shaped ids landing
  inside failed/. Landed on main 2-Nov-2026 (7159cf8e); the
  file runs green (189 tests in the file with items 6 and 11
  landed, 0 skipped — the family's only possible skip is the
  already-registered "cannot create a symlink here", which did
  not trigger), no live bug exposed, no production code
  changed.
- Proof of work (per the method section): per-field enumeration
  (channel, file name, collision counters including past 9,
  non-result names, dotted/dashed stems, the result_file_id
  name table, cross-channel isolation) and the bookend /
  run-length sweeps are carried in the class docstring in the
  repo. Fuzz executed: runner/tools/de_dust_corpus.py grow
  --target race_stash --rounds 400 --seed 20261110, run locally
  against the banked race_stash corpus (64 entries). Result:
  400 rounds, 0 crashes, 0 slow, arcs unchanged at 193,
  slowest try 47 ms. The grow's bookkeeping writes were
  reverted and are not banked (banking is the rigs' hourly job).

### 8. A result that cannot be built into mail is not treated as sent
- Fixed: 6ed7281e (31-Oct-2026)
- Existing tests: test_email_pipe_coverage.py
- Target: up to 50 new tests
- Status: done — 50 new tests (UnbuildableResultShotgunTest in
  test_email_pipe_coverage.py): a result the mail builder
  cannot build is set aside beside its refusal, and the job is
  not treated as sent — build-failure shapes across the
  result's own fields, the set-aside pair written and missing,
  and the posting retried. Landed on main 2-Nov-2026
  (77edd0ec); the file runs green (66 tests in the file,
  0 skipped), no live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target mail --rounds
  400 --seed 20261106, run locally against the banked mail
  corpus (26 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 101, slowest try 31 ms — the unbuildable-
  result failure did not recur. The grow's bookkeeping writes
  were reverted and are not banked (banking is the rigs' hourly
  job).

### 9. A DTLS result stays until a session can take it
- Fixed: 81ef9ee5 (31-Oct-2026)
- Existing tests: test_dtls.py
- Target: up to 50 new tests
- Status: done — 50 new tests (DtlsResultStaysShotgunTest in
  test_dtls.py): a result completed before any session can
  take it stays on the pending shelf until a session acks it —
  the shelf's keying, expiry and ack shapes, hostile job ids
  and subjects, and the session arriving early, late and
  never. Landed on main 2-Nov-2026 (a11ce8d5); the file runs
  green (136 tests in the file, 1 skip — the pre-existing
  environmental skip for unconnected UDP in this environment,
  not from this family), no live bug exposed, no production
  code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target dtls --rounds
  400 --seed 20261107, run locally against the banked dtls
  corpus (55 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 728, slowest try 62 ms — the lost-result
  shape did not recur. The grow's bookkeeping writes were
  reverted and are not banked (banking is the rigs' hourly job).

### 10. A NATS result is not done until the broker answers the publish
- Fixed: a3cec2fc (31-Oct-2026)
- Existing tests: test_transports.py
- Target: up to 50 new tests
- Status: done — 50 new tests (NatsPublishAckShotgunTest in
  test_transports.py): the publish is not done until the
  broker's answer comes back — PONG, -ERR, +OK, PING, MSG,
  unknown lines, silence, a closed socket, a send failure and
  a passed deadline at the flush, and the ack ordering and
  retry shapes through the pipe, all against the file's
  scripted socket fake. Landed on main 2-Nov-2026 (157e5d0c);
  the file runs green (163 tests in the file, 0 skipped), no
  live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  (result file name, result subject and its job id, result
  body, subject prefix, client timeout against the flush
  deadline) and the bookend / run-length sweeps are carried in
  the class docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261111, run locally against the banked
  channels corpus (11 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 142, slowest try 61 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 11. A result from the finished life does not ack the next one
- Fixed: bfb3a790 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (StaleResultDoesNotAckShotgunTest
  in test_transport_queues.py): a stored result envelope from
  a job's finished life does not ack a later lease of the same
  id — the stored-envelope match by ident, by suffixed name
  and by body id, stale and fresh envelopes side by side, and
  the next life's own result posting normally. Landed on main
  2-Nov-2026 (c2dbd567; authored in a parallel worktree and
  spliced beside items 6 and 7 after tail conflicts); the file
  runs green (189 tests in the file, 0 skipped), no live bug
  exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed: the queue's named
  target for this item, runs, is a records file and not a grow
  target in this tree, so the corpus machinery ran against the
  nearest target, channels — the channel inbox/result surface
  the queues pipe is built on — with the same rounds and seed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261112 against the banked channels
  corpus (11 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 142, slowest try 37 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).
- Follow-up finding (2-Nov-2026, from this item's family work;
  the 2 tests that expose it were held back from the family
  and are not on main): QueuePipe._stale entries are discarded
  only on the successful stale-post path. When a noted stale
  file leaves the outbox through a set-aside — a permanent
  refusal inside push_results, or the listing's own set-asides
  — the entry lingers, and a later result of the same name is
  posted and moved to done as if it were the stale file,
  without the result-path ack. Verified first-hand against
  main (480e0667) with a probe driving the fake Worker: after
  a 413 refusal set the stale file aside, _stale still held
  the name; the fresh result then posted with no ack and the
  job stayed leased and pending. Two bounds on the blast
  radius, also verified: the pass's reconcile phase acks a
  pending job whose core consumption is marked in inbox/done,
  which rescues the plain-removal drive; and the set-aside
  file keeps its own id in the pass's unposted set until the
  runner's stub cycle answers it. The fix shape, for a later
  pass: discard the _stale entry whenever its file leaves the
  outbox by any path. No production code was changed by this
  queue item.

### 12. An unreadable refusal is still the job in its name
- Fixed: 9d8493c3 (31-Oct-2026)
- Existing tests: test_platinum_runner.py
- Target: up to 50 new tests
- Status: done — 50 new tests (UnreadableRefusalNameShotgunTest
  in test_platinum_runner.py): when the set-aside result's body
  names no job, the refusal is answered under the job id in the
  result file's own stem — the fallback's shapes (no blank
  line, non-UTF-8 bodies, empty and whitespace bodies, BOM,
  the reason cut at 500 for the record and 300 for the stub),
  the precedence of a parsed name over the stem, and the stem
  field itself. Deliberately distinct from item 5's family in
  the same file, which pins the no-record stay in the same
  branch; this family pins the answering side. Landed on main
  2-Nov-2026 (c4b82b47); the file runs green (146 tests in the
  file, 0 skipped), no live bug exposed, no production code
  changed.
- Proof of work (per the method section): per-field enumeration
  (the subject field's shapes, the record's fields, the stem
  field including the 128/129 boundary) and the bookend /
  run-length sweeps are carried in the class docstring in the
  repo. Fuzz executed: runner/tools/de_dust_corpus.py grow
  --target stash --rounds 400 --seed 20261113, run locally
  against the banked stash corpus (31 entries). Result:
  400 rounds, 0 crashes, 0 slow, arcs unchanged at 20,
  slowest try 60 ms. The grow's bookkeeping writes were
  reverted and are not banked (banking is the rigs' hourly
  job).

### 13. Windows pins: a refusal with no record is not filed
- Fixed: bfb230cf (31-Oct-2026)
- Existing tests: test_delivery_edges.py
- Target: up to 50 new tests
- Status: done — 50 new tests (WindowsPinsNoRecordShotgunTest
  in test_delivery_edges.py): on the Windows-shaped pins, a
  refusal note with no result file beside it is filed and
  counted, while a pair carrying a result file and no record
  stays in failed/ byte-for-byte and is never moved — the
  counting and mixed-pair shapes, and the config fields
  (runner_id, shared_secret, mailbox_user) that decide whether
  a record can answer. Landed on main 2-Nov-2026 (feac1460);
  the file runs green (82 tests in the file, 0 skipped), no
  live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261114, run locally against the banked
  channels corpus (11 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 142, slowest try 38 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 14. A suffixed result file is still that job
- Fixed: ee1fe83f (31-Oct-2026)
- Existing tests: test_dtls.py, test_email_pipe_coverage.py,
  test_transport_shells.py (added by the fix)
- Target: up to 50 new tests
- Status: done — 50 new tests (SuffixedResultStillThatJobShotgunTest
  in test_dtls.py — the pipe that acked without sending; the
  family pins the live-session correlation, distinct from item
  4's held-set parser pins and item 9's waiting-for-a-session
  pins): a collision-suffixed result file still delivers to
  that job's session — every counter shape (0, 1, 2, 3, 9, 10,
  11, 99, 100, 999, zero-padded), the suffix shapes that do
  not parse, siblings in one pump in sorted order, and prefix
  idents. Landed on main 2-Nov-2026 (8edf607d); the file runs
  green (186 tests in the file, 1 skip — the pre-existing
  environmental UDP skip), no live bug exposed, no production
  code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target dtls --rounds
  400 --seed 20261115, run locally against the banked dtls
  corpus (55 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 728, slowest try 57 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 15. A second job under a live id is not a successful send (queue Worker)
- Fixed: 929fce3f (31-Oct-2026)
- Existing tests: queues-worker worker.test.mjs, test_queue_weather.py
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun15 suite in
  runner/cloud/queues-worker/test/worker.test.mjs, the file
  where the fix's own Worker tests live): a second envelope
  under an id that is already live is stored as a duplicate,
  never as a successful send — the envelope's fields one by
  one (v, type, job_id, kind, script, sig, extra fields, the
  subject), duplicate runs, and the lifecycle edges (an ack
  frees the id, a dead id answers 409 not a duplicate, a
  duplicate does not disturb a live lease, a posted result
  does not free the id). Landed on main 2-Nov-2026 (591a1b3d);
  the file runs green under node --test (64 tests, 64 pass,
  0 skipped — the Python skip registry does not apply to this
  file), no live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261116, run locally against the banked
  channels corpus (11 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 142, slowest try 54 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 16. A receipt that is not this pull's is 409, not 404
- Fixed: 694dc82a (31-Oct-2026)
- Existing tests: queues-worker fatfinger.test.mjs, test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun16 suite in
  runner/cloud/queues-worker/test/fatfinger.test.mjs, the file
  where the fix's own Worker tests live): an ack or renew
  carrying a receipt that is not this pull's answers 409, and
  one naming no live job answers 404 — the receipt's fields
  one by one (hand, attempt, the job id, the verb), their
  numeric spellings, a missing job with plausible and
  malformed receipts, a lease expiring on the exact
  millisecond, and every 409 leaving the stored record
  unchanged. Landed on main 2-Nov-2026 (3d7082d2); the file
  runs green under node --test (83 tests, 83 pass, 0 skipped
  — the Python skip registry does not apply to this file), no
  live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261117, run locally against the banked
  channels corpus (11 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 142, slowest try 54 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 17. A result that cannot be read does not finish the job
- Fixed: accf7b95 (31-Oct-2026)
- Existing tests: test_transport_queues.py, test_transport_shells.py
- Target: up to 50 new tests
- Status: done — 50 new tests (UnreadableContentResultShotgunTest
  in test_transport_shells.py — the channel level, deliberately
  the content leg beside item 6's OSError leg and item 7's
  symlink leg, whose pins it does not duplicate): a result
  whose content cannot be read as an envelope — every
  no-blank-line shape and every not-UTF-8 shape — is set aside
  with its refusal and does not finish the job, while the
  shapes that do parse are returned. Landed on main
  2-Nov-2026 (2467787f); the file runs green (135 tests in the
  file, 0 skipped), no live bug exposed, no production code
  changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target stash --rounds
  400 --seed 20261118, run locally against the banked stash
  corpus (31 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 20, slowest try 47 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 18. A refused collision result is set aside under the job id
- Fixed: 4931ec16 (31-Oct-2026)
- Existing tests: test_result_size.py, test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (RefusedCollisionSetAsideShotgunTest
  in test_result_size.py, the file where the fix's own sweep
  test lives): a refused result under a collision name is set
  aside under the plain job id, so the stub sweep can answer
  it — the set-aside naming for every counter shape (past 9,
  zero-padded), the refusal reason and body carried
  byte-for-byte, the original kept under work/<job_id>/, and
  primary and collision refusals answered in one pass. Landed
  on main 2-Nov-2026 (29ead251); the file runs green (66 tests
  in the file, 0 skipped), no live bug exposed, no production
  code changed.
- Proof of work (per the method section): per-field enumeration
  (channel, id stem, collision suffix, extension, refusal
  reason, result body) and the bookend / run-length sweeps are
  carried in the class docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target race_stash
  --rounds 400 --seed 20261119, run locally against the banked
  race_stash corpus (64 entries). Result: 400 rounds,
  0 crashes, 0 slow, arcs unchanged at 193, slowest try 7 ms.
  The grow's bookkeeping writes were reverted and are not
  banked (banking is the rigs' hourly job).

### 19. A URL that only starts with the loopback text is not loopback; a redirect takes the token with it
- Fixed: dc4b7a70 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (LoopbackRedirectShotgunTest in
  test_transport_queues.py): the queue base URL is loopback
  only when the host really is — disguised hosts (spellings,
  ranges, trailing dots, userinfo tricks) are refused — and a
  redirect is never followed with the token: every redirect
  code and Location shape against in-process loopback servers
  that record the requests and their Authorization headers,
  the second hop never reached, and the three doors (the
  queue client, the queues main, send_job's queue call) each
  gated. Landed on main 2-Nov-2026 (e6f610cb); the file runs
  green (239 tests in the file, 0 skipped), no live bug
  exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  (scheme, host, port, path/query/fragment, userinfo) and the
  bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target wire --rounds
  400 --seed 20261120, run locally against the banked wire
  corpus (117 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 184, slowest try 312 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 20. An ack the queue refuses forgets the result, and the job stays leased
- Fixed: fe4ec56c (31-Oct-2026)
- Existing tests: test_queue_pipe_edges.py, test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (RefusedAckShotgunTest in
  test_transport_queues.py, the file where the fix's own
  regression test lives): an ack the queue refuses — 500, 409,
  a connection error, a falsy answer — leaves the posted
  result in place and the job leased, on both arms of the
  pipe (the result arm and the reconcile arm), with the ack
  call's own status and receipt fields pinned, and the retry
  storing the same bytes once. Landed on main 2-Nov-2026
  (spliced beside items 21, 22 and 23 after tail conflicts);
  the file runs green (439 tests in the file with all queue
  families landed, 0 skipped), no live bug exposed, no
  production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261121, run locally against the banked
  channels corpus (11 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 142, slowest try 30 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 21. Two job ids differing only after 120 characters collide into one file; neither result posted
- Fixed: 2f6502f2 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (LongIdCollisionShotgunTest in
  test_transport_queues.py): the delivery name keeps 128
  characters, so two ids differing only past that point are
  two jobs with two files — the length boundaries
  (119/120/121/127 kept exactly, 129 and 1000 cut at 128),
  ids differing at every position around the cut, prefixes
  shared to every depth, 10 ids sharing the first 127, and
  the pair carried through the whole pipe to 2 acks. Landed
  on main 2-Nov-2026 (334a43cb); the file runs green
  (439 tests in the file with all queue families landed,
  0 skipped), no live bug exposed, no production code
  changed.
- Proof of work (per the method section): per-field enumeration
  (channel, ident, subject, body, the returned path) and the
  bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target names --rounds
  400 --seed 20261122, run locally against the banked names
  corpus (84 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 89, slowest try 3 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 22. An oversized result does not finish the job
- Fixed: 4922aa37 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (OversizedResultShotgunTest in
  test_transport_queues.py): an over-cap result is set aside
  by the listing before the pass can post it, and the pipe
  holds the job's lease through its failed/ scan — sizes at,
  1 under and 1 over a lowered cap and the real 4 MiB cap,
  the trailing newline as the crossing byte, UTF-8 bytes
  against characters, and the failed/ scan's membership
  shapes. Distinct from item 18's set-aside naming pins.
  Landed on main 2-Nov-2026 (spliced beside items 20, 21 and
  23 after tail conflicts); the file runs green (439 tests in
  the file with all queue families landed, 0 skipped), no
  live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target stash --rounds
  400 --seed 20261123, run locally against the banked stash
  corpus (31 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 20, slowest try 12 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 23. A result the queue will never take is set aside
- Fixed: 9be8c1a6 (31-Oct-2026)
- Existing tests: test_transport_queues.py, test_transport_shells.py
- Target: up to 50 new tests
- Status: done — 50 new tests (QueueNeverTakesResultShotgunTest
  in test_transport_queues.py): a result the queue answers
  with a permanent refusal (400, 403, 413) is set aside with
  its refusal and the job stays leased, while every retryable
  answer (401, 404, 409, 429, 500, 503) leaves the file for
  the next pass — the status seams at the client, the pipe
  integrations against the fake Worker, and the oversize
  listing leg. One behavior pinned as current, noted in the
  class docstring: the listing's size leg reads size before
  name, so an oversize non-result file or sidecar in the
  outbox is also set aside under its own name. Landed on main
  2-Nov-2026 (spliced beside items 20, 21 and 22 after tail
  conflicts); the file runs green (439 tests in the file with
  all queue families landed, 0 skipped), no live bug exposed,
  no production code changed.
- Proof of work (per the method section): per-field enumeration
  (status, payload, file name, subject id, body, the refusal
  reason's shape) and the bookend / run-length sweeps are
  carried in the class docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target race_stash
  --rounds 400 --seed 20261124, run locally against the banked
  race_stash corpus (64 entries). Result: 400 rounds,
  0 crashes, 0 slow, arcs unchanged at 193, slowest try 27 ms.
  The grow's bookkeeping writes were reverted and are not
  banked (banking is the rigs' hourly job).

### 24. A different result for a stored id does not finish the job
- Fixed: 2c0f4d5d (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs, test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (DifferentResultStoredShotgunTest
  in test_transport_queues.py, the file where the fix's own
  tests live): a second result for an id whose stored envelope
  hashes differently does not finish the job — the stored-hash
  answer in every shape (matching, mismatching, uppercased,
  padded, truncated, extended, empty, missing, wrong-typed,
  the old Worker's no-hash answer), malformed payloads, the
  envelope's own fields, and the permanent/retryable status
  split. Landed on main 2-Nov-2026 (spliced beside items 20,
  21, 22 and 23 after tail conflicts); the file runs green
  (539 tests in the file with item 27 landed, 0 skipped), no
  live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261125, run locally against the banked
  channels corpus (11 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 142, slowest try 7 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 25. A result whose body names a different id is refused (queue Worker)
- Fixed: 9565d89f (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun25 suite in
  runner/cloud/queues-worker/test/fuzz.test.mjs, the file
  where the fix's own tests live): a result whose signed body
  names a different id than its subject is refused — which
  field governs each kind (job_id for result, query_id for
  qresult, the other kind's field ignored), null and
  wrong-typed claims, the signed payload governing past
  unsigned decoys on both sides, duplicate keys reading their
  last value, and a refusal billing no bytes and leaving the
  first envelope in place. Landed on main 2-Nov-2026
  (6911c265); the file runs green under node --test (128 tests
  with item 26's suite landed, 128 pass, 0 skipped — the
  Python skip registry does not apply to this file), no live
  bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target wire --rounds
  400 --seed 20261126, run locally against the banked wire
  corpus (117 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 184, slowest try 660 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 26. Result bytes had no daily cap of their own (queue Worker)
- Fixed: 90ca98f3 (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun26 suite in
  runner/cloud/queues-worker/test/fuzz.test.mjs, the file
  where the fix's own tests live): result bytes bill against
  their own daily cap — counts at, 1 under and 1 over the
  cap, cumulative fills, what counts (UTF-8 bytes not
  characters, the whole envelope, the subject line, the
  trailing newline), the 429's error/bytes/retry fields, the
  UTC day boundary at the exact millisecond, the quota
  object's field shapes, no refund on ack, and tenant
  isolation. Landed on main 2-Nov-2026 (spliced after item
  25's suite in the same file after a tail conflict); the
  file runs green under node --test (128 tests, 128 pass,
  0 skipped), no live bug exposed, no production code
  changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target collect
  --rounds 400 --seed 20261127, run locally against the banked
  collect corpus (20 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 65, slowest try 31 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 27. A second result file replaced the first and still acked the job
- Fixed: cf591bb4 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (SecondResultFileReplacementShotgunTest
  in test_transport_queues.py): the writer's first name posts
  first — a collision-named result sorting before the plain
  name no longer replaces the stored envelope or steals the
  ack: the ordering seams (plain beating counters 2, 3, 10;
  collisions alone sorting alphabetically), identical bytes
  following the winner into done with no second ack, the
  subject-mismatch and ident-fallback seams, and the
  result-name parser field by field. Deliberately distinct
  from items 3, 11 and 23 in the same area. Landed on main
  2-Nov-2026 (spliced beside items 20 to 24 after tail
  conflicts); the file runs green (539 tests in the file,
  0 skipped), no live bug exposed, no production code
  changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target stash --rounds
  400 --seed 20261128, run locally against the banked stash
  corpus (31 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 20, slowest try 18 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 28. Results and dead-letter pages did not say when they stopped; reads stopped at 8 MB of subjects
- Fixed: 29001ad3, 66329844, 4635a1db (31-Oct-2026)
- Existing tests: queues-worker tests
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun28 suite in
  runner/cloud/queues-worker/test/fuzz.test.mjs): results and
  dead-letter pages say when they stopped, and subject reads
  stop at 8 MB — the pager shapes and per-field pins are
  carried in the suite's header comment in the repo. Landed on
  main 5-Nov-2026 (spliced from the item's worktree onto the
  current main); the file runs green under node --test
  (178 tests in the file with items 25 and 26 landed,
  178 pass, 0 skipped — the Python skip registry does not
  apply to these files), no live bug
  exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target collect
  --rounds 400 --seed 20261129, run locally against the banked
  collect corpus (20 entries), and re-run at landing with the
  same result. Result: 400 rounds, 0 crashes, 0 slow, arcs
  unchanged at 65, slowest try 75 ms — the silent-stop shape
  did not recur. The grow's bookkeeping writes were reverted
  and are not banked (banking is the rigs' hourly job).

### 29. An ack did not name the hand it was given; a later pull kept its job
- Fixed: b2795848 (31-Oct-2026)
- Existing tests: queues-worker fatfinger/fuzz tests, test_hosting_queue_edges.py
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun29 suites in
  runner/cloud/queues-worker/test/fatfinger.test.mjs and
  runner/tests/test_hosting_queue_edges.py): an ack names the
  hand and attempt it was given, and a later pull keeps its
  job — the per-field pins are carried in the suites' header
  comments in the repo. Landed on main 5-Nov-2026 (spliced
  from the item's worktree onto the current main, beside items
  30 and 31 after tail conflicts); the files run green
  (233 tests in the file with items 30 and 31 landed under
  node --test, 233 pass, 0 skipped; test_hosting_queue_edges.py
  runs 71 tests, 0 skipped, skip-registry gate green), no live
  bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suites' header comments in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261130, run locally against the banked
  channels corpus (11 entries), and re-run at landing with the
  same result. Result: 400 rounds, 0 crashes, 0 slow, arcs
  unchanged at 142, slowest try 163 ms — the stale-hand shape
  did not recur. The grow's bookkeeping writes were reverted
  and are not banked (banking is the rigs' hourly job).

### 30. A negative LEASE_MS read as an already-expired job instead of the five-minute default
- Fixed: 8c5ae5cf (31-Oct-2026)
- Existing tests: queues-worker fatfinger.test.mjs
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun30 suite in
  runner/cloud/queues-worker/test/fatfinger.test.mjs): a
  negative LEASE_MS reads as the five-minute default, never as
  an already-expired job — the value shapes are carried in the
  suite's header comment in the repo. Landed on main
  5-Nov-2026 (spliced from the item's worktree onto the current
  main, beside items 29 and 31 after tail conflicts); the file
  runs green under node --test (233 tests in the file with items 28, 29 and
  31 landed, 233 pass, 0 skipped), no live bug exposed, no
  production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target wire --rounds
  400 --seed 20261131, run locally against the banked wire
  corpus (117 entries), and re-run at landing with the same
  result. Result: 400 rounds, 0 crashes, 0 slow, arcs
  unchanged at 184 — the already-expired-lease shape did not
  recur. The grow's bookkeeping writes were reverted and are
  not banked (banking is the rigs' hourly job).

### 31. A quota that is not an object was not a 400
- Fixed: fbc3d845 (31-Oct-2026)
- Existing tests: queues-worker fatfinger.test.mjs
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun31 suite in
  runner/cloud/queues-worker/test/fatfinger.test.mjs): a quota
  that is not an object is a 400 and stores nothing — the
  shape shapes are carried in the suite's header comment in
  the repo. Landed on main 5-Nov-2026 (spliced from the item's
  worktree onto the current main, beside items 29 and 30 after
  tail conflicts); the file runs green under node --test
  (233 tests in the file with items 28, 29 and 30 landed,
  233 pass, 0 skipped), no live
  bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target stage
  --rounds 400 --seed 20261132, run locally against the banked
  stage corpus (35 entries), and re-run at landing with the
  same result. Result: 400 rounds, 0 crashes, 0 slow, arcs
  unchanged at 93, slowest try 74 ms — the not-an-object quota
  shape did not recur. The grow's bookkeeping writes were
  reverted and are not banked (banking is the rigs' hourly
  job).

### 32. A finished id the queue offered again was leased into the dead list
- Fixed: 344c7df9 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (FinishedIdReofferShotgunTest in
  test_transport_queues.py): a finished id the queue offers
  again is delivered as a new life, its old done marker
  cleared before anything can ack, and only its own answer
  acks it — the per-field pins are carried in the class's
  header comment in the repo. The file's new class runs
  green under the Python suite (50 tests, 0 skipped), no
  live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  class's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261133, run locally against the banked
  channels corpus (11 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 142, slowest try 793 ms — the
  leased-into-the-dead-list shape did not recur. The grow's
  bookkeeping writes were reverted and are not banked
  (banking is the rigs' hourly job).

### 33. A renew did not name its attempt; a bad quota was not a 400
- Fixed: 4cca4cc6 (31-Oct-2026)
- Existing tests: queues-worker fatfinger.test.mjs, test_transport_queues.py
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun33 suite in
  runner/cloud/queues-worker/test/fatfinger.test.mjs): a
  renew names the attempt it was given, and a quota field
  that is not a number is a 400 that stores nothing — the
  per-field pins are carried in the suite's header comment
  in the repo. The file runs green under node --test
  (50 tests in the suite, 50 pass, 0 skipped), no live bug
  exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target wire
  --rounds 400 --seed 20261134, run locally against the banked
  wire corpus (117 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 180, slowest try 4716 ms — the
  unnamed-renew and bad-quota shapes did not recur. The
  grow's bookkeeping writes were reverted and are not banked
  (banking is the rigs' hourly job).

### 34. max=0 leased one job, not the default page
- Fixed: ab002020 (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun34 suite in
  runner/cloud/queues-worker/test/fuzz.test.mjs): max=0
  leases one job, not the default page, on the pull, the
  results read and the dead-letter read alike — the
  per-field pins are carried in the suite's header comment
  in the repo. The file runs green under node --test
  (50 tests in the suite, 50 pass, 0 skipped), no live bug
  exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target collect
  --rounds 400 --seed 20261135, run locally against the banked
  collect corpus (20 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 65, slowest try 389 ms — the
  max=0 shape did not recur. The grow's bookkeeping writes
  were reverted and are not banked (banking is the rigs'
  hourly job).

### 35. The job id check did not read the signed payload the way the runner does
- Fixed: 53e3f33a (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun35 suite in
  runner/cloud/queues-worker/test/fuzz.test.mjs): the signed
  payload is the text that is read — NaN, Infinity and
  -Infinity riding in payload fields the runner's way, the
  tokens as the job_id value and as string contents, unsigned
  decoy objects before and after the signed object, duplicate
  keys last-wins, absent / nested / non-string claims, key
  spellings (jobId, JOB_ID, job-id, trailing space, a Cyrillic
  lookalike, and the \u-escaped spelling the parser decodes),
  the sig member's own shapes (wrong secret, absent, not last,
  fake inner member, forged inside a string, uppercase hex,
  a raw control byte past the gate), the gate-off whole-body
  fallback, bookended and run-length claimed ids, and the
  storage life around a refusal. Deliberately distinct from
  item 25's suite, which pins the result route's claim check:
  this family pins the job route's signed-payload reading
  itself, where an absent job_id is itself a mismatch. The
  suite runs green under node --test (50 tests, 50 pass,
  0 skipped), no live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target wire --rounds
  400 --seed 20261136, run locally against the banked wire
  corpus (117 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 180, slowest try 3614 ms — the
  signed-payload misreading did not recur. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 36. The daily cap counted JavaScript characters, not UTF-8 bytes
- Fixed: 9716fb5d (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun36 suite in
  runner/cloud/queues-worker/test/fuzz.test.mjs): the job
  daily cap, the stored record's size and the job route's
  2 MB storage edge all count UTF-8 bytes — 2-byte accents,
  3-byte signs and CJK, 4-byte emoji, combining marks, a ZWJ
  sequence and a lone surrogate read as U+FFFD; caps at the
  byte count, 1 under it, and between the character count and
  the byte count where the old reading accepted; the whole
  envelope billed as written (subject, payload, sig member,
  trailing newline, JSON escape text); bytes_per_day missing /
  null / numeric string / non-number / zero / negative /
  fractional; the hour counter counting jobs, never bytes;
  and the day boundary in bytes. Deliberately distinct from
  item 26's suite, which pins the result counter's own cap:
  this family pins the job counter, the job record's size
  field and the job storage edge. The suite runs green under
  node --test (50 tests, 50 pass, 0 skipped), no live bug
  exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target cloud --rounds
  400 --seed 20261137, run locally against the banked cloud
  corpus (113 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 184, slowest try 3175 ms — the
  character-count billing did not recur. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 37. The storage budget counted zero instead of the lease timestamp
- Fixed: 355ab824 (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun37 suite in
  runner/cloud/queues-worker/test/fuzz.test.mjs): the storage
  budget measured directly and at the submit route — the
  budget's exact 12-byte distance from the zero-lease reading,
  its floor at the full-width stamp and the extra digit past
  it, per-field widths (id, envelope, the size field's own
  digits, attempts, leased_until, enqueued_at, requeued_at,
  dead_at, hand), jobs at the exact ceiling and 1 past it, a
  body the zero-lease measure would have stored refused as a
  413, and the real records on the whole road (enqueued,
  leased, dead, requeued, dead again) each inside the budget
  quoted at submit. The suite runs green under node --test
  (50 tests, 50 pass, 0 skipped), no live bug exposed, no
  production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target cloud --rounds
  400 --seed 20261138, run locally against the banked cloud
  corpus (113 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 184, slowest try 2173 ms — the zero-lease
  budget did not recur. The grow's bookkeeping writes were
  reverted and are not banked (banking is the rigs' hourly
  job).

### 38. A second result for an id replaced the first envelope
- Fixed: 3f3c16b9 (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun38 suite in
  runner/cloud/queues-worker/test/fuzz.test.mjs): a repeat
  post for a stored result id answers 200 with the sha256 of
  the envelope that stayed and replaces nothing — different
  bytes, identical bytes, the other kind (result and qresult
  share one key), repeats 10 deep, alternating bodies,
  repeats across the day boundary, and the gates that answer
  before the duplicate handling (bad token, a claim for
  another id, oversized, malformed) each leaving the first
  envelope untouched; an ack makes the next post a fresh
  first again. Deliberately distinct from the Python
  writer-ordering family: this family pins the hosted
  queue's stored record and its routes' answers. The suite
  runs green under node --test (50 tests, 50 pass,
  0 skipped), no live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target collect
  --rounds 400 --seed 20261139, run locally against the banked
  collect corpus (20 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 65, slowest try 156 ms — the
  envelope replacement did not recur. The grow's bookkeeping
  writes were reverted and are not banked (banking is the
  rigs' hourly job).

### 39. A read filled the object instead of stopping at 8 MB of envelopes; a pull loaded every envelope
- Fixed: 965e4d82, 3dfbd878 (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs, worker.test.mjs
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun39 suite in
  runner/cloud/queues-worker/test/fuzz.test.mjs): a pull pages
  the queue inside storage and every envelope read stops at
  8 MB — deliberately distinct from shotgun28, which pins the
  results/dead-letter `more` flag, `after` cursor and subject
  budget; this family pins the pull (no `more`, no cursor,
  continuation by lease and ack, a whole-envelope UTF-8 budget
  on jobs), results continuation by ack, and dead-letter
  paging only. The per-field pins are carried in the suite's
  header comment in the repo. The suite runs green under
  node --test (50 tests, 50 pass, 0 skipped — the Python skip
  registry does not apply to these files), no live bug
  exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261140, run locally against the banked
  channels corpus (11 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 142, slowest try 813 ms — the
  load-every-envelope shape did not recur. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 40. The queue stored an envelope the Durable Object cannot store; an id the route cannot name; a subject that is not the signed job_id
- Fixed: 220d6324, a71acd3d (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: done — 50 new tests (the shotgun40 suite in
  runner/cloud/queues-worker/test/fuzz.test.mjs): three legs,
  each enumerated per-field — an envelope the Durable Object
  cannot store (the gate at exactly the 2,000,000-byte stored
  limit and 1 byte past it, for jobs in every form they take
  and for results), an id the route cannot name (safeJobId
  per character class, length and type, at the gate and on
  the ack route), and a subject that is not the signed job_id
  (the signed payload governs, duplicate keys read last, an
  absent or non-string claim is a mismatch). The pins are
  carried in the suite's header comment in the repo. The
  suite runs green under node --test (50 tests, 50 pass,
  0 skipped — the Python skip registry does not apply to
  these files), no live bug exposed, no production code
  changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target edge_subject
  --rounds 400 --seed 20261141, run locally against the banked
  edge_subject corpus (20 entries). Result: 400 rounds,
  0 crashes, 0 slow, arcs unchanged at 0, slowest try 714 ms
  — the unnamable-id shape did not recur. The grow's
  bookkeeping writes were reverted and are not banked
  (banking is the rigs' hourly job).

### 41. A board subject went unhandled, and one stash could be sent twice
- Fixed: bc4cb3d8 (31-Oct-2026)
- Existing tests: de_dust board_mail corpus; board tests
- Target: up to 50 new tests
- Status: done — 50 new tests (BoardSubjectAndStashShotgunTest
  in runner/tests/test_de_dust2.py, beside the fix's own
  combined contract test for both legs in that file): the
  board subject is handled under the shared grammar (the
  separator controls are word characters, the byte order mark
  is a gap), a board key that is not a task id is not loaded
  or offered, and one stash is sent once across direct
  delivers, the resend pass and their races. The per-field
  pins are carried in the class docstring in the repo. The
  class runs green (50 tests, 0 skipped; the family adds no
  skip reasons, so nothing new needed registering), no live
  bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target board_mail
  --rounds 400 --seed 20261142, run locally against the banked
  board_mail corpus (100 entries). Result: 400 rounds,
  0 crashes, 0 slow, arcs unchanged at 617, slowest try
  13703 ms — the unhandled-subject and double-send shapes did
  not recur. The grow's bookkeeping writes were reverted and
  are not banked (banking is the rigs' hourly job).

### 42. Mailbox setup gate demanded mailbox auth from a runner with no email transport, hanging it at an unseen prompt
- Found: 31-Oct-2026, live on the Germany rig (file transport only)
- Fixed: 8174b51f (31-Oct-2026) — the gate routes through
  setup.mailbox_gate_reason
- Existing tests: test_windows_platform_proofs.py MailboxGate tests
  (9 of the file's 20)
- Target: up to 50 new tests
- Status: done — 50 new tests (MailboxGateShotgunTest in
  test_windows_platform_proofs.py): the gate in every transport
  container and spelling, the example placeholders in both
  mailbox fields, the auth field's exact oauth reading, inert
  neighbour fields, and the gate through main() in its string
  and mixed transport spellings; the file runs green (70 tests
  in the file, 0 skipped), no live bug exposed, no production
  code changed.
- Proof of work (per the method section): per-field enumeration
  — the gate reads exactly the config object, mailbox_user,
  mailbox_password, auth, oauth_client_id, oauth_refresh_token
  and the transports argument, and each field gets its own
  generated test (7 per-field tests, beside 27 hand-written
  seams, 12 bookend sweeps and 4 run-length sweeps carried in
  the class docstring in the repo). Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target mail --rounds
  400 --seed 20261143, run locally against the banked mail
  corpus (26 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 131, slowest try 500 ms — the gate
  demanding auth from an email-less runner did not recur. The
  grow's bookkeeping writes were reverted and are not banked
  (banking is the rigs' hourly job).

### 43. job_user=enforce on Windows was a silent no-op; jobs ran as SYSTEM
- Found: 31-Oct-2026, live on the Germany rig
- Fixed: 8174b51f — enforce refuses at startup on win32; audit writes
  an unsupported_platform record
- Existing tests: test_windows_platform_proofs.py JobUser tests
  (10 of the file's 20)
- Target: up to 50 new tests
- Status: done — 50 new tests (JobUserEnforceShotgunTest in
  test_windows_platform_proofs.py): the mode/platform/startup
  refusal surface itself — the exact refusal string, the
  sec_mode defaults that make an unset mode an enforce, the
  Windows preexec record's exact call shape and its real audit
  log line, and the POSIX would_run_as contrast — pinned
  through the code's own seams (the platform parameter,
  os.name, a mocked security module), never by running a job
  as another user, and distinct from item 2's family, which
  pins how the parity check reads the record; the file runs
  green (120 tests in the file with item 42's family landed,
  0 skipped), no live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  — the surface reads exactly security, security.modes,
  security.modes.job_user, security.job_user,
  security.job_user.user, the platform argument, job_id and
  base_dir, and each field gets its own generated test (8
  per-field tests, beside 26 hand-written seams, 12 bookend
  sweeps and 4 run-length sweeps carried in the class
  docstring in the repo; a bookended key name is pinned as an
  unknown key, so the enforce default takes over). Fuzz
  executed: runner/tools/de_dust_corpus.py grow --target
  secret --rounds 400 --seed 20261144, run locally against
  the banked secret corpus (26 entries) — the target that
  exercises runner/guard/security.py, the module that owns
  the mode set. Result: 400 rounds, 0 crashes, 0 slow, arcs
  unchanged at 78, slowest try 89 ms — the silent Windows
  no-op did not recur. The grow's bookkeeping writes were
  reverted and are not banked (banking is the rigs' hourly
  job).

### 44. A client restart did not drop the old client's flight (dtls_session)
- Fixed: d27e7e63 (30-Oct-2026)
- Area: DTLS session handling in the corpus reader
- Target: up to 50 new tests
- Status: done — 50 new tests (ClientRestartFlightShotgunTest
  in test_de_dust_corpus.py): restarts at every point of the
  handshake dropping the old flight in both directions, the
  old server session marked replaced and its established
  events skipped (with the unreplaced "established before
  Finished" shape pinned as the control crash), the other
  client's flight untouched, and the restarts that are not
  restarts at all — an invalid key, ticket or index returns
  before anything is dropped; the class runs green (50 tests,
  0 skipped), no live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  — the restart is one step, and every field it reads (op, c,
  key, ticket, and the script and step containers) gets its
  own generated test (6 per-field tests, beside 28
  hand-written seams, 12 bookend sweeps and 4 run-length
  sweeps carried in the class docstring in the repo). Fuzz
  executed: runner/tools/de_dust_corpus.py grow --target
  dtls_session --rounds 400 --seed 20261145, run locally
  against the banked dtls_session corpus (39 entries).
  Result: 400 rounds, 0 crashes, 0 slow, arcs unchanged at
  1235, slowest try 4981 ms — the stale-flight shape did not
  recur. The grow's bookkeeping writes were reverted and are
  not banked (banking is the rigs' hourly job).

### 45. Q122: the parallel grow did not drain its children; two crash families (race_state, v2_mail) were the grow's own
- Fixed: 5b068aff (30-Oct-2026)
- Existing tests: test_de_dust2.py
- Target: up to 50 new tests
- Status: done — 50 new tests (the ParallelGrowOwnShotgunTest
  suite in runner/tests/test_de_dust2.py): the parallel grow
  drains its children through the spawn seam (no real long
  grows; fakes only), and the grow's own race_state NUL-key and
  v2_mail token-grammar families stay attributed to the grow —
  the per-field pins are carried in the suite's header comment
  in the repo. The file runs green (the suite's 50 tests pass,
  0 skipped, skip-registry gate unaffected), no live bug
  exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target race_state
  --rounds 400 --seed 20261146, run locally against the banked
  race_state corpus (109 entries) — race_state chosen over
  v2_mail because its 72 records were the larger of the grow's
  two own families. Result: 400 rounds, 0 crashes, 0 slow,
  arcs 183 -> 186, slowest try 480 ms — neither the stall nor
  the lost-update attribution recurred. The grow's bookkeeping
  writes were reverted and are not banked (banking is the rigs'
  hourly job).

### 46. Q115: a keydir contract crash in the sender
- Found: f19bc40e (29-Oct-2026); fixed: 30119441 (29-Oct-2026)
- Area: runner/cloud/send_job.py keydir handling
- Target: up to 50 new tests
- Status: done — 50 new tests (the KeydirContractShotgunTest
  suite in runner/tests/test_q114_key_directory_doors.py, the
  file where the fix's own tests live): one key, one entry —
  a key with entries under two of its names is refused under
  either name with one sorted reason, at the door and at
  startup — the per-field pins are carried in the suite's
  header comment in the repo. The suite runs green (50 tests
  pass, 0 skipped, skip-registry gate unaffected), no live bug
  exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target keydir
  --rounds 400 --seed 20261147, run locally against the banked
  keydir corpus (38 entries) — keydir chosen as the nearest
  target: it is the sender's key-directory surface the crash
  came from. Result: 400 rounds, 0 crashes, 0 slow, arcs
  unchanged at 242, slowest try 157 ms — the two-names contract
  crash did not recur. The grow's bookkeeping writes were
  reverted and are not banked (banking is the rigs' hourly job).

### 47. Q116–Q118: slow families on cloud, wire and local — operations pathologically slow, a latency defect class
- Found: f19bc40e (29-Oct-2026); fixed: a1bbaeaf
  (29-Oct-2026), records retired as fast
- Target: up to 50 new tests
- Status: done — 50 new tests (the SlowLatencyShotgunTest suite
  in runner/tests/test_de_dust_corpus.py): the slow
  classification and retirement machinery pinned per target
  (cloud, wire and local each enumerated with the same seven
  generated tests) and the one-pass brace walk pinned by
  agreement with the brute-force walk in both its copies —
  the per-field pins are carried in the suite's header comment
  in the repo. Timing pins use the machinery's own thresholds
  and a scripted clock, never wall-clock sleeps. The suite
  runs green (50 tests pass, 0 skipped, skip-registry gate
  unaffected), no live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target wire --rounds
  400 --seed 20261148, run locally against the banked wire
  corpus (117 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 180, slowest try 4,100 ms — no slow record
  was filed, so the latency class did not recur. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 48. Q113: provenance crash on the cloud target — a result addressed to '<>'
- Fixed: 4c93d140 (29-Oct-2026)
- Area: cloud result addressing / provenance
- Target: up to 50 new tests
- Status: done — 50 new tests (the ReplyToProvenanceShotgunTest
  suite in runner/tests/test_blackbox_findings.py, the file
  where the fix's own tests live): a mutated reply_to whose
  domain starts with a dot, or carries consecutive dots, is
  refused and the result falls back to the runner's mailbox,
  never addressed to '<>' — the per-field pins (the job, the
  local part, the '@', every domain label, the top-level
  domain, and the angle shapes themselves) are carried in the
  suite's header comment in the repo. The suite runs green
  (50 tests pass, 0 skipped, skip-registry gate unaffected),
  no live bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  and the bookend / run-length sweeps are carried in the
  suite's header comment in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target cloud
  --rounds 400 --seed 20261149, run locally against the banked
  cloud corpus (113 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 184, slowest try 2,532 ms — no
  result was addressed to '<>' again. The grow's bookkeeping
  writes were reverted and are not banked (banking is the rigs'
  hourly job).

### 49. Q101: inline files and outputs — canonical base64; the sender wrote outputs outside its folder
- Fixed: 1fa6d626 (27-Oct-2026)
- Area: runner/cloud/send_job.py, runner/ops/exec.py
- Target: up to 50 new tests
- Status: done — 50 new tests (InlineOutputsShotgunTest in
  test_q101_files_edges.py, the file where the fix's own tests
  live): the canonical and non-canonical base64 tables, strict
  padding and alphabet refusals, traversal and device output
  names, symlink plants at every depth, digest shapes, and the
  duplicate-name leg. The file runs green (57 tests in the
  file, 0 skipped), no live bug exposed, no production code
  changed.
- Proof of work (per the method section): per-field enumeration
  (name, content_b64 and sha384 each pinned separately, the
  size field pinned as inert, the max_output_file_bytes reading
  table), the bookend sweeps (every printable ASCII symbol and
  NUL, tab, CR and LF at both ends of a canonical string,
  symbol-only strings) and the run-length sweeps are carried in
  the class docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target cloud --rounds
  400 --seed 20261150, run locally against the banked cloud
  corpus (113 entries). Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 184, slowest try 1515 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 50. Q105: the queue client broke on a dropped connection and a cut-short read
- Fixed: c4df30c7 (27-Oct-2026)
- Existing tests: test_queue_weather.py
- Target: up to 50 new tests
- Status: done — 50 new tests (QueueWeatherShotgunTest in
  test_queue_weather.py, the file where the fix's own tests
  live): every transient exception shape and non-transient
  lookalike, failures at the call and at the read, the backoff
  sequence, and each door the sender serves (post, results,
  dead-letter, ack, new). The file runs green (68 tests in the
  file, 0 skipped), no live bug exposed, no production code
  changed.
- Proof of work (per the method section): per-field enumeration
  (the request resent byte-for-byte, the status and body, the
  exception and its URLError reason, the backoff table, each
  command's exit line) and the failure run lengths (success on
  the first, second and third try, and no fourth) are carried
  in the class docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target channels
  --rounds 400 --seed 20261151, run locally against the banked
  channels corpus (11 entries). Result: 400 rounds, 0 crashes,
  0 slow, arcs unchanged at 142, slowest try 953 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 51. Q102: the replay cache kept an entry by its place, not its age; callers saw times instead of keys
- Fixed: eff6a7ae, 369eafd9, 862669f2 (27-Oct-2026)
- Area: runner/ops/poll.py, mail.py, handlers.py, startup.py
- Target: up to 50 new tests
- Status: done — 50 new tests (ReplayCacheAgeShotgunTest in
  test_q102_seen_age.py, the file where the first fix's own
  tests live): floods at and past the old 2000 count, ages at,
  inside and past the keep horizon, the stamp-plausibility
  bound, flag-shaped values, bookended keys, and every
  caller-visible shape (keys to callers, times on disk). The
  file runs green (61 tests in the file, 0 skipped), no live
  bug exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  (max_job_age_sec read value by value against seen_keep_sec;
  the key and recorded-at fields; the save call's keep_sec) and
  the bookend / run-length sweeps are carried in the class
  docstring in the repo. Fuzz executed:
  runner/tools/de_dust_corpus.py grow --target mail --rounds
  400 --seed 20261152, run locally against the banked mail
  corpus (26 entries) — mail is the nearest de_dust target to
  the replay surface. Result: 400 rounds, 0 crashes, 0 slow,
  arcs unchanged at 131, slowest try 1364 ms. The grow's
  bookkeeping writes were reverted and are not banked (banking
  is the rigs' hourly job).

### 52. Q103: the query door — an ownerless record was not the owner's; the owner's policy did not reach every door; policy ran before freshness
- Fixed: f02356a2, 8d9e9102 (27-Oct-2026)
- Area: runner/ops/queries.py and the doors
- Target: up to 50 new tests
- Status: done — 50 new tests (QueryDoorShotgunTest in
  test_q103_query_door.py, the file where the first fix's own
  tests live; the second fix's seen-key leg is pinned there at
  the same door): owner shapes in the record (missing, empty
  and every non-text type), policy entries under every name
  of a key at every door, freshness shapes of every kind, and
  the seen-key leg end to end. The two Q103 files run green
  (71 tests across both files, 0 skipped), no live bug
  exposed, no production code changed.
- Proof of work (per the method section): per-field enumeration
  (the record's key field, the key_policies entry's name and
  allowed_kinds, the deny flag, the query's v, issued_at,
  key_id and query_id fields, and every door in the generated
  check_door_policy tests) and the repeated-ask run lengths
  are carried in the class docstring in the repo. Fuzz
  executed: runner/tools/de_dust_corpus.py grow --target
  query --rounds 400 --seed 20261153, run locally against the
  banked query corpus (167 entries). Result: 400 rounds,
  0 crashes, 0 slow, arcs unchanged at 903, slowest try
  9214 ms. The grow's bookkeeping writes were reverted and are
  not banked (banking is the rigs' hourly job).

### 53. Q90–Q93: query-target crash families filed from grows 12–15
- Filed: 27-Oct-2026 morning; closed inside the Oct 27 query-door and
  replay work (items 51–52). Verify the exact fix commits on pickup
  before writing tests.
- Target: up to 50 new tests
- Status: queued (verify first)

### 54. Q95: the grow walker died with RecursionError in _paths; depth was mis-measured
- Fixed: 33547a42 (27-Oct-2026) — harness defect found by
  the campaign's own grows 16–17
- Existing tests: test_de_dust_corpus.py
- Target: up to 50 new tests
- Status: done — 50 new tests (GrowWalkerDepthShotgunTest in
  test_de_dust_corpus.py, the file where the fix's own tests
  live): depths at, just past and far past MAX_DEPTH and the
  interpreter's recursion limit, mixed and wide shapes, symbol
  keys, graft lineages that compound across generations, and
  mutators raising every exception type, counted in the run
  record and never a worker death. The family runs green
  (50 tests, 0 skipped), no live bug exposed, no production
  code changed.
- Proof of work (per the method section): per-field enumeration
  (the value's type at each level, its breadth and depth, the
  parent's and the graft's depth against MAX_DEPTH, and the
  Session's mutator_errors, tried and stopped record fields)
  and the nesting run lengths (1, 2, 3, 5, 10, 24, 25, 100,
  500, 1000 and 5000) are carried in the class docstring in
  the repo. Fuzz executed: runner/tools/de_dust_corpus.py
  grow --target collect --rounds 400 --seed 20261155, run
  locally against the banked collect corpus (20 entries) —
  collect is the walker's nearest target. Result: 400 rounds,
  0 crashes, 0 slow, arcs unchanged at 65, slowest try 187 ms.
  The grow's bookkeeping writes were reverted and are not
  banked (banking is the rigs' hourly job).
