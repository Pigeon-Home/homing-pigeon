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

### 12. An unreadable refusal is still the job in its name
- Fixed: 9d8493c3 (31-Oct-2026)
- Existing tests: test_platinum_runner.py
- Target: up to 50 new tests
- Status: queued

### 13. Windows pins: a refusal with no record is not filed
- Fixed: bfb230cf (31-Oct-2026)
- Existing tests: test_delivery_edges.py
- Target: up to 50 new tests
- Status: queued

### 14. A suffixed result file is still that job
- Fixed: ee1fe83f (31-Oct-2026)
- Existing tests: test_dtls.py, test_email_pipe_coverage.py,
  test_transport_shells.py (added by the fix)
- Target: up to 50 new tests
- Status: queued

### 15. A second job under a live id is not a successful send (queue Worker)
- Fixed: 929fce3f (31-Oct-2026)
- Existing tests: queues-worker worker.test.mjs, test_queue_weather.py
- Target: up to 50 new tests
- Status: queued

### 16. A receipt that is not this pull's is 409, not 404
- Fixed: 694dc82a (31-Oct-2026)
- Existing tests: queues-worker fatfinger.test.mjs, test_transport_queues.py
- Target: up to 50 new tests
- Status: queued

### 17. A result that cannot be read does not finish the job
- Fixed: accf7b95 (31-Oct-2026)
- Existing tests: test_transport_queues.py, test_transport_shells.py
- Target: up to 50 new tests
- Status: queued

### 18. A refused collision result is set aside under the job id
- Fixed: 4931ec16 (31-Oct-2026)
- Existing tests: test_result_size.py, test_transport_queues.py
- Target: up to 50 new tests
- Status: queued

### 19. A URL that only starts with the loopback text is not loopback; a redirect takes the token with it
- Fixed: dc4b7a70 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: queued

### 20. An ack the queue refuses forgets the result, and the job stays leased
- Fixed: fe4ec56c (31-Oct-2026)
- Existing tests: test_queue_pipe_edges.py, test_transport_queues.py
- Target: up to 50 new tests
- Status: queued

### 21. Two job ids differing only after 120 characters collide into one file; neither result posted
- Fixed: 2f6502f2 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: queued

### 22. An oversized result does not finish the job
- Fixed: 4922aa37 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: queued

### 23. A result the queue will never take is set aside
- Fixed: 9be8c1a6 (31-Oct-2026)
- Existing tests: test_transport_queues.py, test_transport_shells.py
- Target: up to 50 new tests
- Status: queued

### 24. A different result for a stored id does not finish the job
- Fixed: 2c0f4d5d (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs, test_transport_queues.py
- Target: up to 50 new tests
- Status: queued

### 25. A result whose body names a different id is refused (queue Worker)
- Fixed: 9565d89f (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: queued

### 26. Result bytes had no daily cap of their own (queue Worker)
- Fixed: 90ca98f3 (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: queued

### 27. A second result file replaced the first and still acked the job
- Fixed: cf591bb4 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: queued

### 28. Results and dead-letter pages did not say when they stopped; reads stopped at 8 MB of subjects
- Fixed: 29001ad3, 66329844, 4635a1db (31-Oct-2026)
- Existing tests: queues-worker tests
- Target: up to 50 new tests
- Status: queued

### 29. An ack did not name the hand it was given; a later pull kept its job
- Fixed: b2795848 (31-Oct-2026)
- Existing tests: queues-worker fatfinger/fuzz tests, test_hosting_queue_edges.py
- Target: up to 50 new tests
- Status: queued

### 30. A negative LEASE_MS read as an already-expired job instead of the five-minute default
- Fixed: 8c5ae5cf (31-Oct-2026)
- Existing tests: queues-worker fatfinger.test.mjs
- Target: up to 50 new tests
- Status: queued

### 31. A quota that is not an object was not a 400
- Fixed: fbc3d845 (31-Oct-2026)
- Existing tests: queues-worker fatfinger.test.mjs
- Target: up to 50 new tests
- Status: queued

### 32. A finished id the queue offered again was leased into the dead list
- Fixed: 344c7df9 (31-Oct-2026)
- Existing tests: test_transport_queues.py
- Target: up to 50 new tests
- Status: queued

### 33. A renew did not name its attempt; a bad quota was not a 400
- Fixed: 4cca4cc6 (31-Oct-2026)
- Existing tests: queues-worker fatfinger.test.mjs, test_transport_queues.py
- Target: up to 50 new tests
- Status: queued

### 34. max=0 leased one job, not the default page
- Fixed: ab002020 (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: queued

### 35. The job id check did not read the signed payload the way the runner does
- Fixed: 53e3f33a (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: queued

### 36. The daily cap counted JavaScript characters, not UTF-8 bytes
- Fixed: 9716fb5d (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: queued

### 37. The storage budget counted zero instead of the lease timestamp
- Fixed: 355ab824 (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: queued

### 38. A second result for an id replaced the first envelope
- Fixed: 3f3c16b9 (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: queued

### 39. A read filled the object instead of stopping at 8 MB of envelopes; a pull loaded every envelope
- Fixed: 965e4d82, 3dfbd878 (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs, worker.test.mjs
- Target: up to 50 new tests
- Status: queued

### 40. The queue stored an envelope the Durable Object cannot store; an id the route cannot name; a subject that is not the signed job_id
- Fixed: 220d6324, a71acd3d (31-Oct-2026)
- Existing tests: queues-worker fuzz.test.mjs
- Target: up to 50 new tests
- Status: queued

### 41. A board subject went unhandled, and one stash could be sent twice
- Fixed: bc4cb3d8 (31-Oct-2026)
- Existing tests: de_dust board_mail corpus; board tests
- Target: up to 50 new tests
- Status: queued

### 42. Mailbox setup gate demanded mailbox auth from a runner with no email transport, hanging it at an unseen prompt
- Found: 31-Oct-2026, live on the Germany rig (file transport only)
- Fixed: 8174b51f (31-Oct-2026) — the gate routes through
  setup.mailbox_gate_reason
- Existing tests: test_windows_platform_proofs.py MailboxGate tests
  (9 of the file's 20)
- Target: up to 50 new tests
- Status: queued

### 43. job_user=enforce on Windows was a silent no-op; jobs ran as SYSTEM
- Found: 31-Oct-2026, live on the Germany rig
- Fixed: 8174b51f — enforce refuses at startup on win32; audit writes
  an unsupported_platform record
- Existing tests: test_windows_platform_proofs.py JobUser tests
  (10 of the file's 20)
- Target: up to 50 new tests
- Status: queued

### 44. A client restart did not drop the old client's flight (dtls_session)
- Fixed: d27e7e63 (30-Oct-2026)
- Area: DTLS session handling in the corpus reader
- Target: up to 50 new tests
- Status: queued

### 45. Q122: the parallel grow did not drain its children; two crash families (race_state, v2_mail) were the grow's own
- Fixed: 5b068aff (30-Oct-2026)
- Existing tests: test_de_dust2.py
- Target: up to 50 new tests
- Status: queued

### 46. Q115: a keydir contract crash in the sender
- Found: f19bc40e (29-Oct-2026); fixed: 30119441 (29-Oct-2026)
- Area: runner/cloud/send_job.py keydir handling
- Target: up to 50 new tests
- Status: queued

### 47. Q116–Q118: slow families on cloud, wire and local — operations pathologically slow, a latency defect class
- Found: f19bc40e (29-Oct-2026); fixed: a1bbaeaf
  (29-Oct-2026), records retired as fast
- Target: up to 50 new tests
- Status: queued

### 48. Q113: provenance crash on the cloud target — a result addressed to '<>'
- Fixed: 4c93d140 (29-Oct-2026)
- Area: cloud result addressing / provenance
- Target: up to 50 new tests
- Status: queued

### 49. Q101: inline files and outputs — canonical base64; the sender wrote outputs outside its folder
- Fixed: 1fa6d626 (27-Oct-2026)
- Area: runner/cloud/send_job.py, runner/ops/exec.py
- Target: up to 50 new tests
- Status: queued

### 50. Q105: the queue client broke on a dropped connection and a cut-short read
- Fixed: c4df30c7 (27-Oct-2026)
- Existing tests: test_queue_weather.py
- Target: up to 50 new tests
- Status: queued

### 51. Q102: the replay cache kept an entry by its place, not its age; callers saw times instead of keys
- Fixed: eff6a7ae, 369eafd9, 862669f2 (27-Oct-2026)
- Area: runner/ops/poll.py, mail.py, handlers.py, startup.py
- Target: up to 50 new tests
- Status: queued

### 52. Q103: the query door — an ownerless record was not the owner's; the owner's policy did not reach every door; policy ran before freshness
- Fixed: f02356a2, 8d9e9102 (27-Oct-2026)
- Area: runner/ops/queries.py and the doors
- Target: up to 50 new tests
- Status: queued

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
- Status: queued
