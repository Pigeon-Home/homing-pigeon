# Changelog

One section per release, newest first. Entries are compact by
design: the headline changes, the fixes that mattered, and the
facts a reader may need to cite. Git history carries the rest.

## 3.13.54 - 2026-10-26

- **blueMonday's live mutators, again (Q76).** Another steered
  grow of 20,000 rounds. `board_ops` kept one (`board_file`).
  `local` kept one (`t_case`). `dtls` and `manifest` kept
  nothing. No crashes. Still live: `t_case`, `d_random_byte`,
  `board_file`, `p_text`.
- **blueMonday's survivors: the instrument for after saturation.**
  `runner/tools/bluemonday_survivors.py` mutates every reader the
  corpus holds directly -- a comparison flipped, an `and` for an
  `or`, a `not` dropped, a constant moved by one, a literal
  emptied, a return made `None`, a raise made `pass`, a plus made
  minus -- on the lines the arc maps say the corpus reaches, and
  replays the corpus of every target that reads through that
  module against each mutant, under an alarm. A mutant the replay
  cannot tell from the reader has survived, and its line is the
  next seed to write; the checkers now note what they see beyond
  accepted or refused (the key chosen, a digest of what the reader
  returned, each board operation's answer, the refusal's reason),
  so a mutant that accepts the same entries but reads them
  differently is killed too. `survivors.json` holds the last run
  and `runs.jsonl` the line of every run. First run: 1,877
  mutants over nine readers, 171 survivors, the DTLS reader losing
  none of 513. Twenty `v2` seeds came out of it at once: the
  deadline floor and each cap at itself and one past it, the
  version in every wrong type, a sent clean pass, a non-UTC
  `issued_at`.
- **The survivors' first seeds, and a thirteenth target.** The
  verifier's survivors named their seeds and got them: the marker
  at the very start of a body, the tail one short and one long, a
  tail closed by the wrong character, a 95-digit signature and one
  with a non-hex digit, an empty object signed, a one-member
  object signed, a brace-balanced candidate that is not JSON, an
  object closed twice, a tab and a control character inside a
  string; `reply_to` at exactly 254 and 255 characters; and the
  provenance arm notes the message it sends (from, to, subject,
  content). The signer's secret-strength rule was reached but
  never exercised, so `secret` is a target of its own: one
  candidate secret before the sender's `require_signable_secret`
  and the runner's `validate_shared_secret`, the two held in step
  as `send_job.py`'s own comment asks -- both refuse naming the
  same fault or both accept, and the two entropy estimates are one
  number -- with seeds at the 128-bit floor, one just under it
  (30 characters over 19 symbols), the repeating units, the
  placeholders, and the alphabets of one and two. Second survivors
  run: 1,928 mutants over ten readers, 147 survivors (171 before);
  the mailbox reader keeps one, the verifier fourteen.
- **The survivors' second seeds.** The board's second offer in a
  sequence is another worker's, since the first would only be
  handed its outstanding claim again, so enforce now withholds and
  advisory hands out with the warning in the corpus; a task
  withheld, its requirement done, then offered; every priority
  shape (absent, zero, a fraction, NaN, the infinities, a boolean,
  2^63). The channel inbox checker notes the channel's own log
  lines and the result files' text, and the core's side has a
  sixth shape, the reply as a pair without a target. Third
  survivors run: 131 of 1,928; the board keeps 19, the channel
  readers 20.
- **blueMonday's live mutators, one grow (Q75).** A steered grow
  of 20,000 rounds on the four mutators `stats` still called
  live. `dtls` kept two (`d_random_byte`, arcs 290 to 295).
  `local` kept one (`t_case`). `board_ops` and `manifest` kept
  nothing. No crashes. `t_sig_tamper`, `t_case`, `d_random_byte`,
  `board_arg` and `p_replace` are still live.
- **blueMonday's live shape, rebuilt (Q74).** The posted capture
  sends a subject line and a sealed envelope. That shape is now
  a seed on `wire`, `cloud`, and `local`, rebuilt under the
  corpus secret with invented ids and a fixed nonce. Not the
  capture's own ciphertexts or job ids. Both verifiers accept
  the job and the result. `local` refuses the job. A short grow
  filed no crash and kept nothing past the seeds.
- **Where the blueMonday targets are.**
  `docs/project/bluemonday-where.md` names the commit for Q65
  through Q74. The capture's own bytes are not among them.
- **blueMonday steers, archives and learns (Muse's four, from the
  grow seat).** Saturation is per mutator: `stats` names each
  target's live and saturated mutators from the last grows'
  records, and a grow reads the same records and chooses mutators
  by their keep rate, a saturated one keeping a floor share of the
  best one's (`--no-steer` for the uniform grow; the record says
  `steered`). `--archive <dir>` (`HP_BLUEMONDAY_ARCHIVE`) writes
  every child a grow tries, kept or not, to one gzip JSON-lines
  file per grow on a disk outside the tree -- the rig's, which has
  the room -- and the run record carries the file's name, size,
  SHA-384 and count. The dictionary learns: `dictionary` also
  harvests the keys and short values of every grown entry that
  reached a new arc into a `learned` section with its provenance,
  and the grammar mutators draw on both. The sequence seeds carry
  the recovery shapes: two different poisons before the good one on
  `inbox` and `local_inbox`, a run of refusals before the happy
  path on `board_ops`.
- **Every guard subprocess reads from nothing.** The pre-push
  guard's test runs, the simulated surface and the in-process leak
  run take `stdin` from the null device: a test that reaches the
  terminal (the install wizard behind an unpatched module copy)
  fails in the open instead of waiting on an inherited stdin that
  never delivers.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.53 - 2026-10-26

- **blueMonday's grammar dictionary (phase 4).** `python
  runner/tools/bluemonday_corpus.py dictionary` builds
  `runner/tests/bluemonday/grammar.json` from the drafts in
  `docs/ietf/`: every backticked token without a space (member
  names, literals, enumerated values, patterns), every number the
  text states with its neighbours on both sides, and every JSON
  example with `sig` removed. Two mutators use it on every
  target: a word of the drafts dropped into a text or in place of
  a quoted string, and a draft member set on an object, a number
  moved to a boundary, or a key respelled as a draft member. The
  drafts' examples seed `wire`, `cloud` and `v2`. The desk rebuilds
  the dictionary when the drafts change.
- **blueMonday's channel inbox, under the sequence contract.**
  `inbox` holds an extension's whole inbox as a peer or a crash
  may have left it -- files, symlinks and directories, in the
  names they were given, with a known-good envelope beside them
  -- read by `fetch_channel_messages` and then serviced by
  `service_channel` with the core's side in one of five shapes
  (a reply per envelope, a callback that raises, no replies,
  consume off, a reply whose write raises). Every file and link
  comes back as one message in name order, a well-formed envelope
  as `parse_envelope` reads it and anything else as the empty
  ack-only refusal; after the service pass what stayed, what moved
  to done, what landed in the outbox and what was re-queued follow
  from the shape, the neighbor served either way. Twenty-one
  entries over 191 arcs; the mutators edit a file's text, a name,
  the shape, or the inbox itself. Saturated on the file surface
  at the first grows: the paths left are the ones only a failing
  disk reaches.
- **blueMonday's local inbox, under the sequence contract.**
  `local_inbox` holds the local signal inbox as a peer or a crash
  may have left it -- `.json` envelopes, other files, symlinks,
  directories, fillers, with a known-good alert beside them --
  scanned once by `_scan_local_inbox`. Every `.json` entry is
  handled once and removed either way, a symlink or a file that
  is not UTF-8 without an ingest call, anything not named `.json`
  left alone, no ingest raises, and the senses store holds
  exactly the records the ingests answered, in inbox order, the
  neighbor's among them whatever came before. One finding, fixed
  and pinned: a directory whose name ends in `.json` was counted
  as handled, logged as failed and left in place on every scan,
  once a second for as long as the runner ran; it is left alone
  like any non-`.json` entry. Twenty-one entries over 376 arcs.
- **blueMonday's provenance contract on the verifiers.** Every
  body `wire` or `cloud` trusts is now held to where its result
  would go: `_valid_reply_to` on the signed dict alone answers
  `None` or a single plain address the dict carries under
  `reply_to`, and `send_mail` addresses the result there or to the
  runner's own mailbox with the subject on one line. Ten seeds in
  the reply_to shapes (padded, a display name, two addresses, a
  header line folded in, no TLD, over the length cap, non-ASCII,
  not text, the mailbox itself); `mailbox.py` joins the two arc
  maps. In `inbox` the reply carries the target the core would
  pass and the `.target.txt` sidecar must carry exactly that. One
  finding, fixed and pinned: a result subject with a form feed, a
  vertical tab, a 0x1c-0x1e separator, U+0085, U+2028 or U+2029
  in it raised from the header and the result was dropped unsent;
  the subject is one line by the header's own rule, which is
  Python's `splitlines` set, not CR and LF alone.
- **blueMonday's sequence contract on local (Q70).** Every
  `local` entry, the ones already kept included, is now followed
  by a known-good neighbor alert in the same directory. A
  refusal leaves the senses store untouched. The neighbor is
  stored either way. This is the envelope reader, beside
  `local_inbox` on the scanner. The existing 52 entries still
  meet it. One grow of 20,000 rounds filed no crash and kept
  one: 53 entries, 120 arcs.
- **blueMonday's cross-platform replay (Q71).** Every committed
  entry is read again under the simulated Windows surface (the
  host identity and the APIs Windows lacks; not `ntpath`). The
  answer must be the same accepted or refused. A changed answer
  is a differential. The first replay agreed on all fourteen
  targets. `platform` runs it; the suite replays it on the
  Linux leg.
- **blueMonday's grammar dictionary (Q72).** The mutators now
  insert the IETF drafts' own member names, enumerated values,
  and boundaries (`docs/ietf/`): `reply_to`, `runner_id`,
  `timeout_sec`, `script_sha384`, `stdout`, `exit_code`, `exec`,
  `ping`, `result`, a 128-character job id, 96 hex digits, a
  500-character `why`, deadline 30 and 31, and the subject
  markers `[HOMING-PIGEON] TEST job` and `[HOMING-PIGEON] result`.
  The drafts' own examples are seeds, with invented ids: six on
  `wire` and `cloud`, six on `v2`. One grow of 800 rounds on
  every target filed no crash and kept nothing past those seeds.
  The verifier accepts a 129-character job id and `.` and `..`;
  the draft's identifier rule is the runner's safe-id check, not
  this verifier's refusal, so those seeds are recorded as
  accepted and the verifier was not changed.
- **blueMonday under the grammar, 20,000 rounds (Q73).** Every
  target was grown again with the dictionary in the pool. `wire`,
  `cloud`, `v2`, and `mail` kept nothing and gained no arc.
  `dtls`, `board_ops`, `manifest`, and `local` each kept one,
  from their own mutators (`d_random_byte`, `board_arg`,
  `p_replace`, `t_sig_tamper`), not from a draft token. No
  crashes. The mail dictionary also inserts the draft's
  decoration word `TEST`.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.52 - 2026-10-26

- **blueMonday's eighth target: DTLS (Q66).** `dtls` holds one
  datagram against `runner/wire/dtlsproto.py`: `_split_records`
  and `_parse_handshake` never raise, a complete handshake
  message is handed to the extension, hello, key-share and PSK
  readers (which refuse with `DtlsError` or `JobCryptoError` and
  nothing else), and `DtlsServerCore.feed` returns datagrams and
  never raises. Seeds are a sealed flight built from the module's
  constructors under invented keys (ClientHello with a key share
  and a PSK, ServerHello, a sealed Finished), the two-fragment
  pair, an empty datagram, and a plaintext record whose length
  claims more than the datagram holds. The mutators are the
  record's own, not the text set. A grow of 20,000 rounds found
  no crash: 19 entries, 289 arcs.
- **blueMonday's ninth target: the task board (Q67).** `board`
  holds one task dict against `runner/wire/board.py`: `submit`,
  `offer`, `complete`, `approve` and `reoffer_expired` never
  raise. A task that is not a usable submission is refused and
  stores nothing; a task that is accepted is offered, a stale
  claim reopens on a zero lease, and a second complete is a
  duplicate. A `bm_review` payload finishes through
  `pending_review`. After every entry a known-good neighbor
  still completes, and a second board file walks the allowlist
  miss, the compartment miss, enforce withholding an unmet
  requirement, and advisory handing it out with the warning.
  Twenty-four seeds. Two grows of 20,000 rounds filed no crash
  and kept nothing past the seeds: 24 entries, 249 arcs.
- **blueMonday's board, under the sequence contract.** `board_ops`
  holds a board file as a peer or a crash may have left it, then a
  sequence of peer operations on it -- `submit`, `offer`,
  `complete`, `approve`, `reoffer_expired` -- on a throwaway path,
  held after every step: each answers its shape, a task handed out
  is claimed under the id it carries and is a copy, and the file
  reads back as the board in memory. Its mutators edit the file,
  an argument, or the sequence. Three findings, each fixed and
  pinned: the re-offer of an outstanding claim handed out the
  board's own record where a fresh hand-out gives a copy; a record
  whose `task_id` disagreed with its key was handed out under a
  name no result could complete, so `load` makes the record carry
  its key; `approve` of a non-string id answered a string where
  every other path answers `(ok, reason)`, the shape its ack
  carries.
- **blueMonday's tenth target: the channel inbox (Q68).**
  `channels` holds a pair of inbox files against
  `runner/wire/transports.py`: `fetch_channel_messages` never
  raises. A file that is not an envelope is an ack-only refusal
  and stores nothing; a file that is an envelope comes back as
  that subject and body, and its reply stays inside the outbox.
  A known-good neighbor in the same directory is still a job
  either way. The check also plants a subdirectory, a symlink,
  a non-UTF-8 file, and one oversize envelope with the size cap
  lowered for that probe only and put back. Eleven seeds. One
  grow of 20,000 rounds filed no crash and kept nothing past
  the seeds: 11 entries, 142 arcs.
- **blueMonday's eleventh target: the extension manifest (Q69).**
  `manifest` holds one extension.json object against
  `runner/ops/extensions.py`: `parse_manifest` returns the
  cleaned manifest or raises `ValueError` and nothing else. A
  manifest it accepts is read back with the defaults filled,
  and the caller's tunables, entry and upstream paths are
  copies. A newer `api_version` than this agent provides is
  still accepted here; `api_refusal` is the later check.
  Thirty-nine seeds. One grow of 20,000 rounds filed no crash
  and kept 24: 63 entries, 237 arcs.
- **A repeated object is written twice.** `_json_safe` (the signer's
  and the board's JSON walk) treated an object that merely appears
  twice -- under two keys, or twice in a list -- as a cycle and
  wrote the second occurrence as `null`; a true cycle is still
  `null`, a repeat is now written twice, which is how JSON reads it
  back.
- **A grown child is checked as the corpus will carry it.** The
  tool reads every payload child back through JSON before the
  check, so a crash on file always reproduces from the file.
- **The guard sees a staged test change.** `regression_guard.py`
  lists the test modules changed against the baseline from the
  commits since it, the working tree against `HEAD` (staged and
  unstaged alike) and the untracked files; a change already
  staged for the commit no longer slips past the pre-push run.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.51 - 2026-10-26

- **The differential, both ways (Q65).** Every `wire` and `cloud`
  text entry now holds the agent's verifier and the front-end's to
  agreeing on one body: both trust it and read the same dict, or
  both refuse, with the one difference by design (Q61) allowed
  only when a control character in the signed object explains it.
  Seeds for the brace walk's hardest shape (keys and values made of
  `{`, `}` and `"`, nested and at the top) and a body signed in its
  pretty-printed form. `stats` reads the run records and marks a
  target saturated when its last grow kept nothing and reached no
  new arc.
- **blueMonday's seventh target: the mail path (Q65).** `mail`
  holds the readers that choose the text a verifier will see, on
  one raw RFC 822 message: the core's subject, bounce check and
  `get_text_body`, the email extension's `_subject_body` and
  `reply_target` with `mailbox._valid_reply_to`. Contract: none
  raises, the extension reads the same subject and body as the
  core, and the reply target is the mailbox or a plain address from
  inside the body's JSON, never anything a header said. Twenty
  seeds in the structural shapes (plain, multipart, nested, an
  attachment, a base64 body, a truncated base64 part, encoded-word
  subjects, duplicate headers, a reply-to inside the body and one
  only in a header, bounces, bytes that are not UTF-8) and
  structural mutators (a header dropped, duplicated, folded or
  inserted, a boundary broken, a part truncated, the blank line
  moved). A first grow of 40,000 rounds found no crash.
- **The blueMonday plan.** `docs/project/bluemonday.md`: the
  campaign the conductor runs indefinitely, written down whole --
  what it is for, the instrument, the surface with every reader of
  outside bytes and its status, the contracts (refusal, round-trip,
  differential, provenance, sequence), the seeds and vocabulary,
  the roles, the cadence and records, saturation and what comes
  after it, the phases, what perfection looks like, the hard rules.
  Section M of the standing orders points at it.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.50 - 2026-10-26

- **The guard's leak run has a private temp root.** A tempdir left
  behind is named only when it is the module's own: the in-process
  leak run points `tempfile` and `TMPDIR` at a fresh directory for
  its duration, so other shards' files on a busy CI box no longer
  read as leaks.
- **A zero resident set reads as unknown.** The tree samplers (the
  `ps` reader on Darwin and the BSDs, the `/proc` reader on Linux)
  report `None` for a process whose resident set is zero, which is
  the platform saying it has no figure yet, a process between fork
  and exec or on its way out, not a measurement; the tree's memory
  signals skip it as they skip every unknown.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.49 - 2026-10-26

- **Records carry the interpreter and the platform.** Every
  blueMonday run line and every regression pass line says which
  Python and which platform produced it.
- **blueMonday is the only effort.** The conductor's order in the
  standing orders: no hourly regression pass, no Platinum cycle, no
  other queue item until he lifts it; a grow runs at every moment,
  one process per core, with nothing beside it, and the resource
  line is expected on target or over.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.48 - 2026-10-26

- **Parallel by default.** `bluemonday_corpus.py grow` and
  `regression_pass.py` take `--jobs` as the box's core count unless
  told otherwise, as the parallel test runner always has, so a plain
  command keeps every core busy.
- **Q64: the pass refuses a dirty tree in its own shape, and the
  guard's soft leaks are pinned.** Under `--pull` the regression
  pass reads `git status` first and a dirty tree is a `NOT RUN`
  ledger line with its record in `passes.jsonl`, never a traceback;
  a failing pull is recorded the same way. The guard's leak run is
  held to naming a tempdir and a thread left behind, as soft, with
  the test that left them.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.47 - 2026-10-26

- **The grow is always on.** Section M of the standing orders: a
  blueMonday grow runs on the rig at every moment, measures and
  passes included, with `--jobs <cores>` and `--minutes` to the
  next rules refresh, under `nice -n 10` so a measure or a pass
  keeps priority while the grow takes every idle cycle.
- **blueMonday 2 (Muse).** Two nested-signature seeds (a `sig`
  member inside a nested object, with and without an outer key)
  merged into the `wire` and `cloud` seeds; the grow's keeps and
  run records committed, 157 entries, 651 arcs, no crash.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.46 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.45 published; the tree is 36ffa6fc's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.45 - 2026-10-26

- **Grows one per core, and for as long as told.**
  `bluemonday_corpus.py grow --jobs J` (`HP_BLUEMONDAY_JOBS`) grows
  the targets J at a time in their own processes, the next starting
  the moment any one finishes; `--minutes M` cycles the targets,
  each cycle with its seed moved on, until the time is up: the
  continuous grow between a measure and a pass. The standing orders'
  throughput section names it, the parallel runner under coverage
  for the measure step, and `--jobs` on the regression pass, so the
  rig's resource line reads on target instead of under-driven.
- **The conductor.** AGENTS.md rule 11: the owner of the repository
  is the conductor, by his own word, in every document, ledger line,
  question and note from now on; older text keeps its wording.
- **The work is data in the tree.** The corpus tool appends one
  line per seed or grow to `runner/tests/bluemonday/runs.jsonl`
  (head, seed, rounds, what was tried and by which mutator, what
  was kept, what crashed, how long) and rewrites
  `<target>.arcs.json`, the arc map the corpus reaches; the
  regression pass appends one line per pass to
  `docs/reports/regression/passes.jsonl` (head, tests, wall time,
  failing ids, the flake split, the culprits, the ledger line). The
  standing orders commit both with the ledger lines, grows that
  kept nothing and green passes included: the conductor's order
  that the data from the testing goes into the repository, not only
  its results.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.44 - 2026-10-26

- **blueMonday's sixth target, and the key slots that disagree
  (Q63).** `stash` holds `_record_payload` to a dict or None over
  records whose three key slots (the body's own key_id, the
  envelope's, the record's) agree and disagree every way; `crypto`
  and `local` got the same family at the AAD and at the ingest.
  Sealed seeds draw a counter nonce so their ids are stable, and
  `seed` adds to an existing corpus only what it lacks. The README
  states the refusal types so a grow never files one as a crash.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.43 - 2026-10-26

- **The pre-push regression guard.** `runner/tools/regression_guard.py`
  runs, on the test modules a commit touches, what a red leg would
  have said: the module natively, again for flakes, in shuffled
  orders, under the simulated Windows surface against the same
  module on origin/main, in-process with a global-state snapshot
  around every test that names a leaked patch, environment
  variable, working directory, signal handler or `os` attribute
  with the test that left it, and then the registry gates. Section
  P of the standing orders names it as the campaign's pre-push
  command. Its tests are `runner/tests/test_regression_guard.py`.
- **The questions desk answers for every Claude stamp.** AGENTS.md
  rule 10: a question to any Claude stamp, active or recycled, is
  accepted and answered by the desk, and the answer carries
  `50000c8e` (the owner's routing).
- **The rig's regression pass.** `runner/tools/regression_pass.py`
  runs the whole suite on the head of main, re-runs any red alone
  to split flake from deterministic, bisects each deterministic red
  between the last green head the rig recorded and the current head
  (the failing tests alone, in a temporary worktree per step; a
  test that did not exist before is named as red since the commit
  that added it), and prints the ledger line and a paragraph ready
  for `questions.md`. State stays outside the tree. The standing
  orders run it hourly beside the campaign; its tests include a
  bisect on a throwaway repository.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.42 - 2026-10-26

- **Project blueMonday: the fuzz corpus against the verifiers.** The
  owner's name for Q62's campaign, built at his request in this
  lane: `runner/tools/bluemonday_corpus.py` grows a coverage-guided
  corpus (an entry is kept when it reaches a line arc no earlier
  entry did, measured with `sys.settrace` over the target's own
  files) against five readers -- `verify_body` and
  `verify_body_keyed`, the cloud front-end's `verify_body`,
  `protocol_v2.validate`, `jobcrypto.decrypt_body`, and the
  local-signal ingest with `parse_envelope` -- from suite-style seeds
  mutated the job-fuzz ways. `runner/tests/bluemonday/<target>.jsonl`
  is the corpus and `runner/tests/test_bluemonday_corpus.py` replays
  it on every leg, carrying any crash on file as an
  `expectedFailure` probe; its ASCII check tolerates a Windows
  checkout's CRLF, which the first car caught. Section M of the
  standing orders is the campaign's loop.
- **`jobcrypto` refuses a non-text job or key name.** The corpus's
  first finding: `decrypt_body` and `encrypt_body` built the AAD
  from `job_id` and `key_id` unchecked, so a number, a list or a
  missing name raised `AttributeError` where the module promises
  `JobCryptoError`; `_aad` refuses it now. Every caller on the wire
  passes text, so no envelope could reach it from outside.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.41 - 2026-10-26

- **Q62: Platinum's next phase.** The owner's brief to Muse, in
  `docs/use/questions.md`: when a cycle's ledger line closes no new
  statements, the campaign turns to a coverage-guided seed corpus
  against the verifiers -- `runner/wire/verify.py` first, then the
  cloud front-end's verifier, the v2 message parsers, and the
  jobcrypto and local-signal envelope readers -- with the corpus kept
  under `runner/tests/` as replayable fixtures and every crash filed
  as a probe with a Q.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.40 - 2026-10-26

- **Project Platinum, cycle 5's ledger and cycle 6.** The cycle-5
  ledger line (statements 99.6%, branches 97.5%, no crashes filed)
  with the refreshed coverage table and gap list under
  `docs/reports/v3.13.38/`; cycle 6's tests over `execute_job`'s
  poison script (a non-string script is the JobRejected poison its
  comment promises) and a remediation finish that throws, which
  leaves the job's own result standing; the queues pipe's seen-id
  step and a posted result's final newline; `answer_queries`
  stepping over a non-object declared signal; and three fixtures
  reaching the arms their cycle-5 versions walked past (Muse).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.39 - 2026-10-26

- **Two remediation tests accept the act that landed.** The
  3.13.38 tag build's macOS leg caught the 0.1 s sampler killing a
  job whose script exits in milliseconds, where Linux lets it finish
  and quarantines; the runner records whichever act landed, and
  `test_remediation`'s two quick-script tests now assert that the
  recorded act matches the process's fate (a clean exit for a
  quarantine, a signal for a kill) instead of naming one branch.
  Runner unchanged; the note is in `docs/use/misc.md`.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.38 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.37 published; the tree is 3.13.34's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.37 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.36 published; the tree is 3.13.34's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.36 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.35 published; the tree is 3.13.34's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.35 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.34 published; the tree is 3.13.34's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.34 - 2026-10-26

- **Project Platinum, cycle 5.** The last two-line row (port-watch's
  short delivery) and the one-line frontier top-down: the sun's
  hour-angle wrap, the O_BINARY arms under a simulated flag, the
  audit, stripe and ledger guards, the loader coercions, the tail
  window, the registry tags, the provider record refusals, the
  pump's deadline, the extraction fallback and the small seams of
  ops and oracle (Muse).
- **The O_BINARY simulation leaves a real flag alone.** Cycle 5's
  Windows leg went red when a test zeroed the platform's own flag
  and the writer fell into text mode (CRLF); `test_platinum_oracle`
  now plants the stand-in only where the platform has no flag, the
  runner unchanged. Muse carried the same helper into the guard and
  oauth tests and gave the `ps` probe its registered POSIX skip;
  the note is in `docs/use/misc.md`.
- **Five older tests no longer zero or delete the real O_BINARY.**
  The leg stayed red after that: `test_harness_gaps`,
  `test_install_edges` and `test_setup_gaps` ended their flag arm
  with `del os.O_BINARY`, and `test_oracle_learning` and
  `test_runner_last_edges` left it at 0, so on Windows every writer
  later in the same test process ran in text mode (CRLF) until a
  test finally asserted exact bytes. Each site now patches the flag
  to its own value and restores it; a replay with a real-valued
  flag shows it surviving all five modules.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.33 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.32 published; the tree is 3.13.32's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.32 - 2026-10-26

- **The nightly pin refresh.** The softflowd and Suricata feed senses
  re-pinned to their upstreams' current tips by
  `.github/workflows/upstream-pins.yml`, the drift tests green
  against them (sibling `60000b3a`).
- **Project Platinum, cycle 4's ledger.** Statements 99.4%, branches
  97.2%, no crashes filed; the refreshed coverage table and gap list
  under `docs/reports/v3.13.30/` and a cycle-4 note in the campaign
  standing orders (Muse).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.31 - 2026-10-26

- **Project Platinum, cycle 3's ledger and cycle 4's first batch.**
  The cycle-3 ledger line (statements 99.4%) and the refreshed
  coverage table under `docs/reports/v3.13.29/`; property tests
  over the to-file envelope, the no-folder carry and `inspect`'s
  success print (Muse).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.30 - 2026-10-26

- **Project Platinum, cycle 3 continued.** Property tests over the
  hosting control plane, the Oracle's paging arms, the softflowd
  sense and the unstashable rejection (Muse).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.29 - 2026-10-26

- **The cloud sender's verifier takes the signed object the
  runner's signer wrote, whatever braces its strings hold.**
  `send_job.verify_body` found the object's opening `{` by the
  brace walk alone, so a payload that nests an object keyed `"{"`
  and later carries an escaped quote walked balanced from the brace
  inside the key, the extracted span started mid-payload and a body
  `verify.sign_payload` produced failed as a signature mismatch.
  The opener search now parses each candidate, as the runner's
  verifier has since Q32: the two signers are one signer in two
  homes (Q61, Project Platinum cycle 2; the probe runs without its
  decorator, and `test_two_signers_agree` no longer errors on that
  payload).
- **Project Platinum, cycle 2's ledger and most of cycle 3.** The
  cycle-2 ledger line and the refreshed coverage table under
  `docs/reports/v3.13.27/`, Q61 filed, the guard module's long-line
  probes; cycle 3's logic batch (`cmd_new`'s queue refusal,
  `apply`'s fallback, the live fallback, `inspect`'s missing
  review), the stash, channel and filename failure arms, the
  transport rollback closure and service-watch's short delivery
  (Muse).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.28 - 2026-10-26

**The next car, with nothing new aboard.** Opened on the release
cadence as 3.13.27 published; the tree is 3.13.27's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.27 - 2026-10-26

- **A provision record that is not fetched says why.**
  `test_extension_sources` asserted a record's status alone, so a
  Windows leg that saw `partial` lost the reasons; `_Base.assertFetched`
  fails on one line with the record's detail, its per-file problems,
  the transient count and the pass's last warnings (the fake opener
  is deterministic, so a partial record there can only be a refused
  local write).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.26 - 2026-10-26

**The next car, with nothing new aboard.** Opened on the release
cadence as 3.13.25 published; the tree is 3.13.22's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.25 - 2026-10-26

**The next car, with nothing new aboard.** Opened on the release
cadence as 3.13.24 published; the tree is 3.13.22's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.24 - 2026-10-26

**The next car, with nothing new aboard.** Opened on the release
cadence as 3.13.23 published; the tree is 3.13.22's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.23 - 2026-10-26

**The next car, with nothing new aboard.** Opened on the release
cadence as 3.13.22 published; the tree is 3.13.22's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.22 - 2026-10-26

- **The version 2 deadline test picks the question up by its
  final name.** The test's sender read every file in the outbox
  and could take the writer's temp file, which already read
  "question " before its rename; that pickup removed nothing,
  the real question stayed, and the runner waited out its whole
  deadline then rode the local default alone (one build-windows
  leg in five). The sender now takes `*.result.txt` only, a
  planted temp file proves it, and a failed leg reports the
  watcher's timeline. The runner was never wrong.
- **A refusal note that is not UTF-8 no longer ends the delivery
  sweep.** `_sweep_channel_refusals` read each extension's
  `<stem>.refused.txt` and its result file guarded against
  `OSError` only, so bytes that are not UTF-8 raised
  `UnicodeDecodeError` out of the poll pass on every cycle. The
  pair now reads as unparsed with reason "refused", the note is
  filed to `outbox/done/`, and the sweep goes on (Q60, Project
  Platinum cycle 1; the probe runs without its decorator).
- **Project Platinum, cycles 1 and 2.** Property tests over the
  delivery and stash family, the DTLS sender's happy path walked
  end to end, and the ops, queues, guard, workspace and
  queue-post arms (`runner/tests/test_platinum_*.py`); the
  cycle-1 ledger line and the refreshed coverage table under
  `docs/reports/v3.13.21/`; Q59 answered, Q60 filed and fixed
  (Muse).
- **Three test lines made portable.** Cycle 2's skip reason is
  registered; the DTLS ticket's `0o600` mode is asserted on POSIX
  and its existence everywhere (Windows keeps no mode bits); the
  workspace-sweep test hands the sweep a real path, as production
  does, since a macOS temp directory sits behind `/var ->
  /private/var`.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.21 - 2026-10-26

**The next car, with nothing new aboard.** Opened on the release
cadence as 3.13.20 published; the tree is 3.13.20's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.20 - 2026-10-26

- **`FAQ.md` is at the root.** The FAQ, the owner's own page, moves
  from `docs/use/faq.md` to `FAQ.md` beside the other manuals, in
  caps like them; its text is untouched, one relative link now
  resolves from the root, every pointer follows, and the retired path
  is on the layout guard's list.
- **Platinum's second pass over wire/.** `protocol_v2.validate` from
  three valid seed messages with fields dropped, swapped and grown;
  `verify.verify_body_keyed` from bodies `sign_payload` wrote, with
  mail line wraps, preambles, a signature digit changed, every
  `key_id` shape, wrong secrets, nesting past the decoder's limit and
  wrong argument types (the payload or a ValueError, nothing else);
  `DtlsServerCore._feed_record`'s drop path, a sealed record for no
  session dropped and counted, never answered. The lines left dark
  are named with their reasons (`runner/tests/test_platinum_wire.py`,
  queue P, sibling chat).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.19 - 2026-10-26

- **Platinum's first module, the DTLS record layer.**
  `runner/tests/test_platinum_wire.py` drives `_RecordSealer.open`,
  `_split_records` and `_parse_extensions` from a real corpus (records
  sealed by `_RecordSealer.seal`, with and without a connection id,
  several epochs, plaintext records, extension blocks) mutated the
  ordinary ways, truncation, a flipped bit, a boundary octet, the
  length field rewritten, a byte dropped or doubled, the record
  repeated, junk appended, and asserts the contract: the splitter
  never raises and cuts the datagram contiguously from the start, an
  unmutated run splits back into its records (queue P, sibling chat).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.18 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.17 published; the tree is 3.13.17's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.17 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.16 published; the tree is 3.13.16's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.16 - 2026-10-26

- **No first names in the tree.** A first name dropped from test
  comments and the playbook (`runner/tests/`, sibling chat).
- **Researchers one to three are recycled.** Stamps `10000c2a`,
  `200003d4` and `30000f1a` carry no new work; the questions desk,
  production code and releases are `50000c8e`'s, the test legs, CI
  proofs and platforms `40000e00`'s, the extension upstream pins
  `60000b3a`'s with the sources they pin. The status table is in
  `docs/archive/RESEARCHER_IDENT.md`, the rule is AGENTS.md rule 10,
  and `runner/tests/test_agent_stamps.py` holds the record to the tree.
  <!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->
- **The nightly upstream-pins bump signs as its owner.**
  `.github/workflows/upstream-pins.yml` stamps its commits `60000b3a`
  (sibling chat). This tag was cut from that commit, not from the
  rev: a tag cannot carry a workflow tree that differs from main's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.15 - 2026-10-26

- **`docs/project/future.md`, edited by the owner.** A run of the
  owner's own edits on main, with a sibling chat reshaping after each:
  sections A to D with items numbered consecutively, then the
  letters and numbers dropped so the bullets carry it.
- **The v2 deadline test's shape gives every margin a full second.**
  A six-second deadline, the sender's pickup at two seconds and its
  answer five seconds after that: past the deadline measured from the
  send, a second inside it measured from the pickup, four seconds
  before the runner would give up waiting for the pickup. The answer
  file is written whole, by rename. One Windows leg in a few lost the
  old 0.8/2.4/3 shape to the give-up, the answer filed and never
  read (`runner/tests/test_protocol_v2_messages.py`).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.14 - 2026-10-26

- **`docs/project/future.md` holds only what might be built.** Lettered
  sections and numbered items, each a sentence or two with its status
  re-read against the code and no cross-references; a table of
  contents in place of the preamble; the cut and hardware-research
  sections gone, and the items already decided against (Signal and
  WhatsApp paging, line-rate detection with an ML pipeline and MCP, a
  self-improving SI, the concentrate) removed; the security
  mechanisms that posture cannot close are listed (sibling chat).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.13 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.12 published; the tree is 3.13.12's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.12 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.11 published; the tree is 3.13.11's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.11 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.10 published; the tree is 3.13.10's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.10 - 2026-10-26

- **Project Platinum opens.** Coverage-guided fuzzing on the idle rig
  (queue P in the campaign's standing orders, Q59): `coverage` runs
  under `.github/workflows/coverage.yml` with the child-process hook,
  `runner/tools/coverage_targets.py` ranks the gaps from the AST
  (`logic`, `guard`, `except`, `platform`, `shadowed`), and
  `HP_PLATINUM_EXAMPLES` in `runner/tests/conftest.py` sets how many
  examples a property test without its own `max_examples` runs. The
  hosting entry point, the real HTTP client and the hosting edges
  gained their tests (sibling chat).
- **The queue Worker lives in `runner/cloud/queues-worker/`.** Out of
  the root, with its own tests run in CI
  (`.github/workflows/queues-worker.yml`); the mutation-seeded
  workflow runs hourly, one walk at a time (sibling chats).
- **The hosting-edges vanished-temp leg runs on Windows.** Its fake
  writer closes the ledger's temp handle before it unlinks the file,
  which Windows refuses while open
  (`runner/tests/test_hosting_edges.py`).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.9 - 2026-10-26

- **One `_runner()` for the ops modules.** `runner/ops/live.py` holds
  the one copy that 21 modules used to carry each; `runner.ops.live`
  is on the seven frozen-build lines (sibling chat).
- **Fewer lines in the runner, same behavior.** 27 load-or-raise
  guards are one `_required_load_mod`; `_firewall_watch` and
  `_av_watch` are one `_posture_watch` with five arguments;
  `_read_json_dict` serves the seven read-a-dict-or-nothing sites
  and the two flagged-record loops share one generator; the dead
  `_transports_arg` (shadowed by `cli.py`'s) is gone, with a guard
  against rebound defs in `runner/tests/test_extracted_no_runner_writes.py`
  (sibling chat).
- **A job carrying an unpaired surrogate is refused once.** JSON lets
  a signed body escape a lone UTF-16 surrogate (`\ud800`), and a
  JavaScript SI that slices through an emoji emits one. The runner
  parsed it, then failed to size, stage or answer it, and retried the
  job on every poll. It is now refused at intake and marked seen.
- **A damaged upstream archive is a `SourceError`.** A truncated gzip,
  a bad zip or a corrupt xz stream escaped `extract_archive` as the
  decompressor's own error; the sources pass now gets the failure it
  handles. A tag whose number is past Python's 4,300-digit limit is
  no version instead of a crash.
- **Every untrusted-input parser has a property test.**
  `runner/tests/test_parser_properties.py` holds 23 parsers to their
  contracts on generated input, and its `PROPERTY_ROSTER` is the
  audit record: a parser, its promise and its proof, guarded so an
  entry cannot lose its test. (Agent-Stamp 40000e00)
- **Two flaky legs read and fixed.** The v2 deadline test's sender
  retries its pickup for two seconds and the assertion names why it
  stopped (`runner/tests/test_protocol_v2_messages.py`); the three
  failed-write legs of `test_remediation_gaps` patch the atomic
  writer, where the marker writes live now.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.8 - 2026-10-26

- **The next car, with nothing new aboard.** Opened on the release
  cadence as 3.13.7 published; the tree is 3.13.7's.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.7 - 2026-10-26

- **The tree-kill fixture brings its child up before it writes the
  loot.** `test-macos` kept failing on
  `test_tree_kill_takes_the_child_too` because the tripwire kill
  could land before the second interpreter existed; the script now
  spawns the child, waits for its pid file (written whole, by
  rename), then writes the loot, so the test measures the kill and
  not the race (`runner/tests/test_remediation_e2e.py`).
- **Claims audit, two passes.** Undocumented knobs and flags named
  in the docs, an overclaimed platform list trimmed, the ops layout
  and the line-reduction runbook's repaired rules current, the hosted
  queue counted as the fifth shipped transport everywhere
  (`docs/`, by a sibling chat).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.6 - 2026-10-26

- **The isolation sweep names its vector on every check**, one line
  per assertion, so a red `build-windows` leg reads from the run page
  when the log host is out of reach. A record's writer temp
  (`<record>.tmp.<pid>.<thread>.<hex>`, as `runner/guard/atomicio.py`
  names it) and the canaries the local watch plants are the runner's
  own, never counted as a job's escape; a name carrying the job's own
  file name still counts first, whatever its shape
  (`runner/tests/test_workspace_isolation.py`, `OutsideCheckTest`).
- **A failed test's annotation carries its exception line.** The
  parallel runner's `::error` for each FAIL/ERROR block now ends with
  the block's last exception-shaped line (`AssertionError: 0 != -2`),
  so the run page says why, not only which
  (`runner/tools/run_tests_parallel.py`, `failure_reasons`).
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.5 - 2026-10-25

- **Hosting ships as a feature.** `docs/use/own-cloud.md` is the user's
  page: one command, their own account, their own bill. The container
  image starts from a one-blob config (`HP_CONFIG_BLOB`) with the hosted
  profile and carries bubblewrap; the Fly adapter names the image by
  its git tag. The ephemeral workflow is a template for a user's own
  repository with GitHub's terms called out; billing stays dormant.
- **Workspace isolation's vector sweep** counts a new name outside the
  state tree only when it carries one of the job's own file names or is
  plainly not a runner record, so the runner's lazily written records
  no longer trip it under load.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.4 - 2026-10-25

- **Hosting, Phases 0 to 4, built against recorded exchanges.** The
  `hosted` install profile and the one-blob config
  (`homing-pigeon-install --config-json`); `--once --drain N
  --drain-seconds T` for an ephemeral runner's bounded life; the
  `runner/hosting/` control plane (`homing-pigeon-host up / status /
  redeploy / rotate / destroy / dispatch`) with adapters for Fly
  Machines, Hetzner Cloud, DigitalOcean and GitHub Actions, the machine
  bootstrap, the one-tenant-per-machine inventory, prepaid billing and
  the Stripe webhook; the hosted queue (a Cloudflare Worker and one
  Durable Object per tenant with the token gate, the HMAC gate and a
  per-tenant quota, tested under node), the runner's `queues`
  transport and `send_job.py --to-queue`. Every provider call in the
  suite is a recorded exchange; no account exists yet.
  `docs/project/hosting.md`.
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.13.3 - 2026-10-25

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

The four review items, plus workspace isolation (the runbook of
2026-10-25; one commit per item, each with its tests, each green in
CI before the next).

- **One atomic writer for state files.** `runner/guard/atomicio.py`
  replaces a state file whole or not at all (a temp name opened
  `O_EXCL | O_NOFOLLOW`, written, `os.replace`d, mode 0600; the temp
  unlinked and the cause re-raised on any failure). The ten
  hand-rolled copies of that block (the replay cache, retained
  results, the sent record, config and the OAuth token, the board,
  the DRI, resource and detection state, the security counts, the
  review report, the learning ledger trim, the channel envelopes)
  are calls now, and the two quarantine markers remediation wrote
  straight into the file -- a kill mid-write left a truncated
  record -- go through it fsynced. `runner/tests/test_atomicio.py`:
  a writer killed at random fifty times leaves the destination
  absent or complete, a planted symlink is replaced and never
  followed, and a scan of the core fails on the eleventh copy.
- **`files[].name`, refused the same way on every platform.**
  `runner/guard/filenames.py` is one numbered rule set (no NUL, 255
  bytes a component and 1024 in all; no backslash; not absolute --
  no leading `/`, drive letter or UNC prefix; no `.`, `..` or empty
  component; `[A-Za-z0-9._-]` components that do not start with `-`;
  no Windows device name, with or without an extension, whatever
  the runner's OS), checked in the job-shape loop before any download
  so a bad name is poison and costs no fetch, and the rejection names
  the rule. `os.path.join("/w", "C:\\x")` used to stage a file named
  `C:\x` on Linux, and `CON` was refused only on Windows. A nested
  name has its directories made inside the work dir, after the walk
  confirms no component is a symlink; the real-path gate still runs
  after. `runner/cloud/send_job.py` applies the same module at composition
  time. `runner/tests/test_file_names.py`: the vector table with its
  rule numbers, the end-to-end rejection (poison, never retried, no
  download), the sender by path. PROTOCOL.md section 6.
- **Workspace isolation, pinned.** The work directory's real path is
  resolved once per job (a work directory that is itself a symlink
  is refused) and every check answers for it; the tree is walked
  after staging and again right before the process starts -- no
  symlink or junction, nothing but regular files and directories,
  nothing resolving outside -- and a violation is a `workspace
  integrity` rejection with the work directory removed; the script
  must be a regular file under the root; a download lands in a temp
  name beside its destination (`O_EXCL | O_NOFOLLOW`), capped while
  streaming, and is renamed into place whole; the Linux sandbox
  binds the real path. `runner/tests/test_workspace_isolation.py`:
  every rejected name end to end with nothing written outside the
  work tree, a symlink planted between staging and start caught by
  the pre-exec sweep, a symlinked work directory refused, the endless
  download stopped at the cap with its temp removed, the junction leg
  on Windows, and a property over random file lists (nothing new
  outside the work tree after any job); `test_confinement`'s
  EnforceTest refuses a planted link before the sandbox is entered.
  PROTOCOL.md section 9.4, "The work directory".
- **Execution at most once, delivery at least once.** The moment a
  result (or a rejection) is built and signed it is written to
  `<base_dir>/outbox/` and the job committed as seen, on disk, before
  the first send; a send that fails leaves the record waiting and
  later polls resend the same bytes (`result_resend_backoff_sec`,
  default 60, between attempts), giving up into `outbox/failed/`
  with an audit entry after `result_stash_retention_sec` (default
  86400) -- the script is never run twice. A delivered record moves
  to `sent/`, where a redelivered copy is answered from it. The one
  window left is the stash write itself, pinned by test. A channel
  result goes back out the channel it came through; the startup line
  says how many results are waiting or given up, and `--inspect
  outbox` lists them. `runner/tests/test_result_stash.py` (replacing
  `test_sent_results.py`): the failed send that does not re-execute,
  the byte-identical resend, the backoff, the retention with its
  audit row, the crash window, the rejection through the same path,
  the channel record, and a hypothesis property over random
  send-ok / send-fail / poll / clock sequences (never two executions,
  never a lost result). PROTOCOL.md sections 5 and 6; the two keys in
  `docs/oracle/configuring-oracle.md`.
- **The result's size, permanent refusals, bounces.** A body is held
  under `max_result_bytes` (default 5 MiB) before it is signed: the
  streams are cut to head and tail with a marker, the flags set and
  `result_truncated` added, three passes at most, so the signature
  covers what is sent. A 5xx refusal (552 and the rest, every
  recipient refused, a transport's `PermanentDeliveryError`) is
  permanent: a signed stub with the streams dropped and a
  `delivery_note` goes out once and the original is kept under
  `work/<job_id>/result.json`; a stub refused too is given up with
  the audit row; a 4xx, a socket or a TLS error resends the original.
  The email extension sets a refused result aside under its channel's
  `outbox/failed/` instead of wedging the queue, and the core's next
  pass answers it with the stub down the same channel. A delivery
  status notification in the inbox is said once with the id it
  refers to, marked seen, never parsed as a job; one message whose
  parts raise fails alone. `runner/tests/test_result_size.py` (the
  fit, the classification, 552 then the stub once, a refused stub
  given up, 421 resending the original, the channel refusal, and a
  hypothesis property that the body never exceeds the cap) and
  `runner/tests/test_bounces.py` (Gmail-, Exchange- and Postfix-shaped
  DSNs, the subject parser, the poison message). PROTOCOL.md 3.2;
  `max_result_bytes` in `docs/oracle/configuring-oracle.md`.

## 3.13.1 - 2026-10-25

<!-- Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a -->

Cloudflare Queues Worker boundary with optional REJECT_INVALID_HMAC
gate. When the wrangler var is set, the Worker rejects any inbound
message that fails HMAC-SHA-384 before writing to D1 or doing further
compute. Default off. Full Queues + D1 wiring remains design notes.

- **Worker boundary HMAC reject (optional).** The Cloudflare Queues
  Worker rejects any inbound message that fails HMAC-SHA-384
  verification at the edge when `REJECT_INVALID_HMAC` is set.
  Invalid jobs are never written to D1 and no further compute runs.
  Default is off so existing flows are unchanged until the operator
  turns it on. See `cloudflare/queues-worker/`.

## 3.13.0 - 2026-10-25

<!-- Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a -->

Grok constraint-solve line reduction and human refactor. runner.py
cut from 11,205 lines to ~5,400; platform modules extracted
(ops/mail, ops/exec, ops/av, ops/windows, ops/startup, and the
rest). No behavior change — the same suite, the same gates, the
same protocol. The typecheck gate is green again after the
extraction repairs (dead globals dropped, _runner() typed, the
script-context loads restored).
## 3.12.77 - 2026-10-25

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

Fix forward over 3.12.75 and 3.12.76, which were tagged but never
reached PyPI, SourceForge or GitLab: an empty release was created on
each tag before the pipeline's own, and the release job was refused
(Q56). Carries the typecheck gate green again (three dead
`global _LOG_FILE` lines from the extractions removed, Q55) and the
guard that every `global` in runner/ops/ names a module binding.

## 3.12.75 - 2026-10-25

Cut from 1a808829. The Darwin suite is green on this release (the
wrong-case shape, Q51), the extracted modules' `_runner()` is typed
for the type gate, and the two regression guards from the line
reduction ride with it; otherwise the 3.12.74 code.

## 3.12.74 - 2026-10-25

Runner line reduction: runner.py from 11,205 to 5,362 lines.
Extracted to runner/ops/: cli, oracle_page, oracle_tools, oracle_server,
oracle_ops, context, policy, attest, paths, watch, sensors, handlers,
startup, poll, misc, remediation_ops, queries, exec, mail, main,
windows, firewall, av. Platform-specific code broken out. No behavior
change in the release as cut: the extractions as first landed broke
the installed runner (`python3 runner.py` could not import its own
modules), every job result (a NameError), version 2 ingest, live
config reload, the seen-file writes (two self-recursive helpers) and
the log file name, and all of it was repaired before this cut --
every extracted module loads through `_load_mod`, reaches the runner
through `_runner()`, carries its own imports and is re-exported;
`runner/tests/test_script_context.py` and
`runner/tests/test_extracted_no_runner_writes.py` guard the shape,
`runner/tools/repair_script_imports.py` produces it. docs/use/questions.md
Q52, Q53, Q54.

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.12.72 - 2026-10-25

Cut from 342709f7, minutes after 3.12.71: the version carriers and
the changelog section above, plus Q50's record. The campaign's
test-fixture fixes (Q50, Q51) landed after this cut and ride in the
next release.

## 3.12.71 - 2026-10-25

Cut from b1436f85 (3.12.69 and 3.12.70 were version bumps whose
tags, where they exist, carry this same section's work in part).

<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->
<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

- **Remediation watches the whole tree on macOS and the BSDs.** The
  tree sampler had a Linux reader (`/proc`) and a Windows one
  (Toolhelp) and saw the root alone everywhere else, so a process
  storm on Darwin was invisible to the watch. Darwin and the BSDs
  now sample through one `ps` call per pass (pid, parent, resident
  set, accumulated CPU time); the storm kill proves it on the macOS
  leg. docs/use/questions.md Q38.
- **The macOS install completes without a GUI session.** `launchctl
  bootstrap gui/<uid>` needs a logged-in session and refused over
  SSH, in CI and on a headless Mac, aborting the install after the
  files were written. The agent file is in place either way and
  loads at the next login: an upgrade over a loaded agent is now
  restarted with `kickstart -k`, anything else is a warning with the
  command to run from a logged-in session. Q39.
- **A source install starts.** The installer's file list predated
  the role folders, so `python3 runner/ops/install.py` copied
  `runner.py` without `guard/`, `oracle/` or most of `wire/`, and the
  runner it left refused to import. It now copies the runtime the way
  the wheel ships it. Upgrading over a broken install repairs it.
- **One poison line no longer stops a feed sense.** A line nested
  past the C stack made `json.loads` raise `RecursionError`, which
  five feeds (Suricata, Zeek, osquery, Falco, Wazuh) did not catch;
  the reader never moved past it, so the sense crashed on every pass.
  It is now a malformed line like any other.
- **The 3.9 floor reads timestamps like 3.12 does.** Before 3.11,
  `fromisoformat` takes only 3- or 6-digit fractions and no `+0000`
  offset. A job's `issued_at` in those forms was fresh on 3.12 and
  unparseable on 3.9, and Falco, Suricata and Wazuh dropped events
  with short fractions. Both now normalize first.
- **New proofs.** `python-range` runs the whole suite on 3.9 and
  3.14 on every push. `upgrade-proof` installs the last release,
  seeds owner edits and state, upgrades to the commit and checks
  nothing was lost. `soak` runs the poll loop for two hours nightly
  and fails on growth. `hardware` runs the suite, the platform proof,
  the upgrade proof and a soak on a self-hosted board. Property tests
  cover all eight feed decoders.
- **The extension review: code held to the manifest before load.**
  Nothing signs an extension's code, so the agent now reads each
  sense and transport folder against its manifest before anything
  acts on it (`runner/guard/extreview.py`): a new manifest field
  `capabilities` (`network`, `listen`, `subprocess`, `native`) has to
  cover what the code does; a transport `entry` has to stay inside
  its folder; every `.py` has to compile; symlinks, bidi and
  zero-width control characters, and references to the runner's own
  state are findings. `extension_review` is `enforce` by default -- a
  folder with a high finding is refused like a bad manifest, with a
  security event, and the agent runs without it -- or `advisory`
  (load and log) or `off`. A drop-in that shadows a shipped transport
  is loaded and said out loud; one the review refuses is absent, not
  replaced. Verdicts land in `<base_dir>/extension-review.json`;
  `--inspect review` reads the folders now. The shipped extensions
  declare what they use and pass clean. docs/extend/extensions.md,
  "The review"; docs/design/extension-review-design.md.
- **A job runs at most once per `job_id`.** The result, as it goes on
  the wire, is recorded under `<base_dir>/sent/` before the send; a
  redelivered job (the send failed, the process died before the
  seen-set commit, a duplicate copy) is answered from the record and
  not executed again. The record is bound to the job's received
  digest, so a different job under a reused id runs on its own, and
  it ages out with `output_retention_days`. Delivery stays
  at-least-once; the seen-set still commits only after a successful
  send. PROTOCOL.md sections 5 and 6.
- **`cut-release` tags through the REST API.** GITHUB_TOKEN may not
  push a tag whose tree carries a workflow file it did not write,
  which is what stopped 3.12.66 and 3.12.67 the day `coverage.yml`
  was added. The tag object and its ref are now created through the
  API, with `git push` as the fallback, using `RELEASE_TOKEN` when
  the owner sets one (docs/use/questions.md Q30). The early refusal
  that compared the commit's workflows to main's was a misdiagnosis
  and is gone.
- **The suite and the switch proofs run on macOS and FreeBSD.** The
  release has shipped macOS binaries since the start, smoked but
  never tested; now `test-macos` runs the suite on macos-14 on every
  push, and switch-proofs gains `macos` and `macos-root` legs (a
  real second user, so the privilege drop is proven on a second
  kernel). FreeBSD 14 runs the suite and the roster weekly in a VM.
  Where the suite runs and what each platform proves:
  `docs/project/testing.md`.

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.12.68 - 2026-10-25

- **A quoted preamble no longer rejects a valid signed job.** A
  connector note with an odd number of `"` before the body inverted
  the signed-object search's string tracking, and a job whose body
  carried a `{` inside a string was rejected as a signature mismatch
  (Q32, found by the preamble property under Hypothesis). The search
  now takes the newest `{` whose text up to the marker parses as a
  JSON object, which a brace inside a string never does; the HMAC
  still decides.
- **The suite lints itself for Windows.** `runner/tests/test_windows_portability.py`
  names, on Linux and on the campaign rig before a push, the fixture
  shapes that pass on POSIX and fail on Windows (a patch of an os
  attribute Windows lacks without `create=True`, an `os.stat` call
  counter standing in for a path probe, a fake `os.close` that never
  releases the descriptor, `chmod 000` as an unreadable file). Four
  cuts of 3.12.67 were lost to those shapes in one hour.
- The campaign's standing orders gain the release window, the
  expected-failure rule for probes, and the no-model rule; the roster
  gains `ORACLE.alphabet`, `ORACLE.tools.alphabet`, R5, R6 and the
  Oracle-versus-cage entry.

## 3.12.67 - 2026-10-25

- **Two audit writers no longer lose an entry on Windows.** The first
  full switch-proofs run found it (Q25): `O_APPEND` is one atomic
  write on POSIX, but the Windows C runtime seeks then writes, so two
  job threads denied in the same moment overwrote each other's audit
  entry. One re-entrant lock per process now serializes the bound
  check, the append and the counts bump; it also closes the
  count-then-roll and counts-file races that existed on every
  platform. Entry format, file names and roll-by-rename are unchanged.
- **A refused channel ack rolls back.** `IncomingMessage.ack()` now
  returns what the channel's ack returns, so `service_channel` sees
  the refusal (the envelope changed after the read, the move failed)
  and runs the rollback that drops the seen-set entry; the retry is
  no longer refused as a duplicate of itself (Q25).
- **A withheld root that cannot be resolved still withholds on
  Windows.** `is_withheld` compares both sides as given, made
  absolute the same way, instead of a drive-qualified real path
  against a bare one.
- airwaves: a signal line too long for `int()` degrades that reading
  to None instead of ending the sense's cycle, in all three parsers
  (Q28).
- (3.12.66 was built but not tagged: its Windows build caught the
  audit race above; everything below shipped in this release.)
- **The mutation signal, un-blinded.** A collection failure in the
  mutants tree (two archived probe files with one basename) ended
  mutmut's coverage pass before a test ran; mutmut ignores that
  pass's exit code, so only import-time lines counted as covered and
  three mutants were generated where 443 had been, all green (Q22).
  mutmut's pytest runs now ignore the two folders beside the suite,
  as `unittest discover` does, and `runner/tools/mutation_floor.py`
  fails a mutation job whose run generated fewer than 100 mutants or
  reached fewer than 6 functions, with the tally in the log.
- **Switch proofs, continuous.** `runner/tests/switch_roster.py` lists
  every security control, what SECURITY.md promises when it is on,
  and the tests that prove it; `.github/workflows/switch-proofs.yml`
  runs the roster on every push on three legs (Linux with bwrap, root
  with a second user, Windows) and names each control proven,
  unproven, or failed. A proof that disappears fails the run (Q24).
- **The campaign rig reports what it used.** `runner/tools/rig_resources.py`
  wraps a run and prints one measured `resources` line (box CPU share,
  cores kept busy, peak memory, disk, exit code, verdict against the
  90% target) for the campaign ledger.
- **Release builds cannot be dropped from the queue.** A `release:`
  commit gets its own build concurrency group, so a push every minute
  from the campaign no longer supersedes the one build cut-release
  must read.
- Three sense extensions (aide-feed, usb-arrivals, wire-arrivals) drop
  an `_is_number` helper nothing called (Q23).
- **The coverage map, kept current.** `.github/workflows/coverage.yml`
  runs the full suite under coverage.py on Linux and Windows on every
  push to main, child processes included, and
  `runner/tools/coverage_gaps.py` turns the result into the list of
  never-executed code by function. It is uploaded per platform and
  its ten largest gaps are annotated on the run page; a signal, never
  a gate. The first map, with the gaps ranked by what a user loses if
  that code is wrong, is `docs/reports/v3.12.65/coverage-gaps.md`, and
  each ranked gap is a question for the campaign
  (`docs/use/questions.md`, Q11 to Q17). `coverage` joins the CI pin
  file.

## 3.12.65 - 2026-10-24

- **Default, not silent.** Decision 1's warning now exists. A setting that
  is present but unusable and reads as its documented default is named:
  one startup line ("config: N settings read as their default: ..."),
  the same list as `config_defaulted` in the `full`-tier platform card,
  and a log line on live reload for every default-class key, not just
  the five hot ones. The key table lives in `runner/guard/defaulted.py`
  and a test keeps it in step with the defaults registry.

## 3.12.64 - 2026-10-24

- **Twenty more hunt conversions land as regression tests** (aide, suricata,
  falco, zeek, wazuh, sysmon, osquery, softflowd, and the watch senses).
  aide-feed no longer swallows a second new report on first sight: both
  paths new at once now read on consecutive passes.

## 3.12.63 - 2026-10-24

- **More hunt conversions.** Muse's tripwire, resource-sentinel, job-fuzz and
  job-watcher hunts land as regression tests; the type gate covers the
  role folders' script-mode imports; training-watch and log-sentinel
  read a corrupt saved inode as a restart.

## 3.12.62 - 2026-10-24

- **Docs regrouped, README and FAQ sharpened.** `docs/` is grouped by reader
  with lowercase names; the FAQ leads with use cases and the hard
  security questions; the README gains an FAQ teaser and a "Where it
  goes next" section. pi-health and lab-results now read unusable
  values (huge digit strings, non-string folders, odd mounts) as the
  documented default instead of crashing.
- **`docs/` is grouped by reader and named in lowercase-kebab.** Guides
  moved into `use/`, `oracle/`, `extend/`, `security/` (with
  `hardening/`) and `project/`; `RUNBOOK.md` is `use/runbook.md`, and so
  on. Uppercase file names stay only for the root conventions. The
  layout guard flags the old paths.
- **`runner/` holds `runner.py` and folders.** The 35 modules that sat
  beside it are in four role folders: `runner/oracle/` (opinion,
  learning, review, remediation, detection, senses, resources, dri,
  personal_docs), `runner/wire/` (transports, mailbox, dtlsproto,
  protocol_v2, jobcrypto, oauth, verify, board, platformcard),
  `runner/guard/` (security, sandbox, confval, textutil) and
  `runner/ops/` (install, setup, extensions, extsources, harness,
  local_test, posture, auditreport, winlog). Imports are
  `runner.<folder>.<module>`; a script run by path falls back to
  `<folder>.<module>` with `runner/` on `sys.path`. The installer
  copies `runner.py`, `wire/oauth.py` and `ops/winlog.py` with their
  folders, and the console scripts are `runner.ops.install:main` and
  `runner.wire.oauth:main`. No shims; `test_layout` fails on a module
  at the top of `runner/` or a path to its old place.

- **`extensions/` is `runner/extensions/`.** The root holds the manuals,
  `pyproject.toml`, and three folders (`runner/`, `docs/`, `assets/`)
  beside `.github/`. Like the suite and the CI scripts it is kept out
  of the wheel, the image, the SBOM, the pyrefly gate and mutmut. An
  agent's own `extensions/` folder under its base dir is unchanged.

- **More unusable values read as their documented default.**
  `max_job_age_sec` at mail and local ingest (zero, negative, a boolean
  or a huge integer was used as written), a list or dict
  `severity_floor` in `load_alerts` (it dropped every alert), the
  job-watcher repeat, flaky, baseline, z and cluster tunables (zero,
  negative and sub-one values clamped or disabled them), the job-fuzz
  corpus age and filed cooldown (zero disabled the bound), and an
  infinite cert-sentinel TLS port (it crashed the pass instead of
  yielding no record). Decision 1 has the rule.

## 3.12.61 - 2026-10-24

- **The build and CI scripts are `runner/tools/`.** They left
  `.github/tools/`, kept out of the wheel, the image, the SBOM,
  the pyrefly gate and mutmut, the same way the suite is. Workflows,
  tests and docs follow. No shim. The climb to the tree is unchanged.

## 3.12.60 - 2026-10-24

- **A workspace given through a symlink no longer counts its own files as outside.**
  `snapshot_outside` pruned by `abspath`, which does not resolve the link, so a
  job that changed only a file inside that workspace was attested
  `confined_to_workspace` false.

- **The root holds the manuals, `pyproject.toml`, and four folders**
  (`runner/`, `extensions/`, `docs/`, `assets/`) beside `.github/`
  and `.gitignore`. Moved, with no shims:
  - `tests/` is `runner/tests/`, kept out of the wheel and the
    published image. A test finds the tree three levels up, its
    module id is `runner.tests.test_<name>`, and the suite runs as
    `python -m unittest discover -s runner/tests -t .`. Grok's
    airgap work area (`topaz/`, then `tools/airgap/`) is
    `runner/tests/airgap/`, beside `runner/tests/archive/`, both
    outside discovery.
  - `examples/extensions/` is `extensions/`, and there is no
    `examples/`.
  - `cloud/` is `runner/cloud/`: the console script is
    `runner.cloud.send_job:main`, and the wheel ships one package,
    `runner`.
  - `hardening/`, `CONTRIBUTING.md` and `CHANGELOG.md` are under
    `docs/`, with a short Contributing blurb in the README.
  - The build and CI scripts (`tools/`), the Dockerfiles and
    `docker/`, and `requirements-ci.txt` are under `.github/`, with
    `.dockerignore` beside each Dockerfile as
    `Dockerfile.dockerignore`.
  - `pyrefly.toml` is `[tool.pyrefly]` in `pyproject.toml`, and
    `.gitattributes` lives in `extensions/`, its patterns relative to
    it.

  Every workflow, test, tool, doc, the snapshot index, the SBOM
  source list, mutmut's settings and Dependabot follow.
  `runner/tests/test_layout.py` fails on a retired root entry or a
  path into a retired folder anywhere in the living tree.
  `pyproject.toml`, `.gitignore` and `.github/` stay at the root
  because pip, git and GitHub read them there. AGENTS.md has the
  layout.
- **A bad live value reads as its documented default.** A hot key
  written live with an unusable value (zero, a negative, a string,
  null, Infinity, NaN, a list) kept the last good value. It now
  reads as the documented default (`poll_interval_sec` 20,
  `workers` 1, `default_timeout_sec` 300, `max_output_bytes`
  100000, `max_job_age_sec` 3600) and is named in the log, as
  Decision 1 has it: no hidden last-good state.
- **A dots-only `files[]` path component on Windows.** The new
  staging hunt expected `.../x.txt` to land in a `...` directory;
  Win32 strips trailing dots from a component, so on Windows it lands
  in the workdir itself. Inside either way; the test now says so.
- **A senses query's zero limit returns no alerts.** The store reader
  sliced `out[-0:]`, the whole list, so `"limit": 0` (or 0.5) read as
  no cap. The job-watcher's `failure_window_sec` of zero or below now
  reads as its documented day instead of a window no failure fits.
- **Addressing values refuse instead of defaulting (Decision 1).**
  `docs/design/present-but-invalid-config.md` is decided: a setting
  present but not usable reads as its documented default, unless it
  is a port, a bind address, a key policy, a paging threshold, a
  security mode or a secret, which refuse to start and name the key.
  The two readers that read as the default moved: `transport_dtls.port`
  and `transport_dtls.bind` (a port that is not a whole number 0 to
  65535, or a bind that is not an address string, is a config error
  and the DTLS extension exits 2 naming it; port 0 and an empty bind
  keep their meanings) and the NATS URL's port (`url_port`; a port
  present but not 1 to 65535 is a config error at startup, where
  before it fell to 4222 or killed the reconnect loop). The sentence
  is in PROTOCOL.md section 5 and `docs/configuring-oracle.md`; the
  four campaign classes that asserted the default for those keys
  changed with the docs. The defaults registry's rows point at the
  moved readers and their doc lines, and its coverage guard reads
  paths the same on Windows.
- **`docs/QUESTIONS.md`.** Questions between the agents and the
  owner go there as numbered, dated entries with their answer and
  the applying commit, instead of through the owner by hand
  (AGENTS.md rule 7). Four entries open the file.

## 3.12.59 - 2026-10-24

- **The suites run under a wall clock that names the test.**
  `tools/suite_wall_clock.py` is `python -m unittest` with a
  deadline: a run still going at 20 minutes stops, prints the
  running test and the main thread's stack, annotates the test on
  the run page, and exits 124. The Linux suite step runs through it
  and `tools/run_tests_parallel.py --wall-clock 20` puts every
  Windows shard under it (the parent keeps a hard stop 90 seconds
  past the deadline for a shard whose clock cannot fire). Not a
  job timer: the workflow's only two timers stay on the two scarce
  runners. The 2026-10-23 stall, one test looping forever and both
  suites sitting past 80 minutes with nothing in the log, is the
  reason.
- **The campaign report.** `docs/reports/v3.12.58/doc-default-divergences.md`
  indexes the 72 divergence classes (shape, doc source, reader,
  tests, fix commit), generated from the test docstrings, with the
  three shapes, the six bugs and what the release cost that the
  hunt did not predict.

## 3.12.58 - 2026-10-23

Report: `docs/reports/v3.12.58/doc-default-divergences.md` (the 72
classes indexed, added after the tag).

- **The code now delivers every default the docs promise.** The VM
  campaign's documented-default divergences
  (`tests/test_doc_default_divergences.py`, 184 tests, red by design
  since they landed) all pass, with no test edited. Three shapes
  covered most of them: a JSON boolean read as a number (`true` was
  1, so `poll_interval_sec: true` polled every second and
  `max_output_bytes: true` cut results to one byte), a huge integer
  or `inf`/`NaN` escaping as a raw `OverflowError`, and a key present
  as `null`, a non-numeric string, zero or a negative number used as
  is (`task_timeout: null` wedged claimed tasks forever,
  `default_timeout_sec: null` rejected every timeout-less job). Six
  were their own bugs: a stored alert with no severity dropped on
  read-back, the inference timeout falling back to 60 not 180,
  `ask_model` never sending `keep_alive`, a bad NATS port killing the
  extension from inside `urlparse().port`, an unknown result view
  echoed verbatim instead of reading as `full`, and a null or unknown
  `dtls_greeting` refusing to start instead of reading as `family`.
- **`runner/confval.py`** is the one typed reader behind the fix: a
  boolean is never a number, a number must be finite, bounds decide
  what is usable, and the documented default is what anything else
  gets. `senses.py`, the transport channel and all 28 example
  extensions carry the same rule locally so they stay import-free.
- **Three tests moved with the behavior.** The DTLS extension starts on
  the default tier for a bad `dtls_greeting` and says so, instead of
  exiting 2; the campaign modules' four skip reasons are registered.
  The frozen builds carry `runner.confval` as a hidden import. The
  third was the one that stalled CI: a test in
  `tests/test_oracle_intake_fuzz.py` called the DTLS extension's
  `main()` in-process with a list for the tier and expected exit 2;
  with `main()` now going on to listen, that call bound udp 20220 and
  looped forever, and both CI suites sat past 80 minutes with no
  output. It now checks that `main()` reaches its loop on the default
  tier, with the listener stood in for. The module runs only where
  hypothesis is installed, which is why the local suite never saw it.
- **Typecheck green again.** `runner/platformcard.py` (from the
  unreleased queue below) declared `build_card` as returning a dict
  and returned `None` at tier `none`; the annotation now says so, and
  the card is typed as a plain dict so the `full` tier's `path_tools`
  map assigns. Annotations only, no behavior change.

<!-- Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c -->

Also in this release, from the unreleased queue:

- **`cut-release` workflow.** `gh workflow run cut-release.yml` tags
  the version in `pyproject.toml` on a green commit and dispatches
  the release pipeline on the tag. Refuses an existing tag, drifting
  version carriers, or a commit whose build jobs are not all green.
  docs/RUNBOOK.md Job 4. No change to what the runner does.
- **Extension sources: "auto" by default, and nothing unpinned by
  default.** `extension_sources` now defaults to `"auto"`: the
  background fetch runs only where a local model runs the Oracle,
  so a deterministic box (Pi Light) makes no request, which is what
  the README said of it. An entry no lock pins waits as `unpinned`,
  listed in the index with the reason, until the owner sets the new
  `unpinned` switch for that extension or for all; the build's pins
  and an extension's own lock need no consent. docs/SAFEGUARDS.md
  states the egress.
- **One upstream declaration.** The manifest's `upstream` block
  (now with an SPDX `license`) is the one place an extension names
  its upstream. `runner/extsources.py` hands the files it pins to
  the Oracle as the entry `pinned`, vouched for by the digests
  `upstream/PIN.json` recorded, and a `sources.json` entry says
  `"upstream": true` to fetch more from that repository without
  naming it again. `upstream.json`, the `provenance/` bundles,
  `tools/vendor_upstreams.py`, and their tests are retired; the
  build's offline verify step went with them (`fetch_upstream.py
  --check` was already the gate).
- **The pong carries a platform card.** A `ping` job's result now
  carries `platform` at the owner's `pong_platform` tier (default
  `family`: `os_family`, `default_interpreter`, `protocol_versions`;
  `standard` and `full` add more; `none` sends the bare pong). A
  sender learns what box it is talking to, and whether it opens
  version 2, before the first real job. The DTLS greeting now
  carries the same card (`runner/platformcard.py`), so the two
  bindings describe the box the same way; its `family` tier gained
  `default_interpreter` and `protocol_versions`. PROTOCOL.md 3.2.
- **Mirrors cannot publish out of order.** Two releases cut minutes
  apart run side by side; the SourceForge default-download marker
  is now set only by the newest tag on the repository, so an older
  pipeline finishing last leaves it alone. GitLab and the version
  folders were already order-independent. `cut-release` notes on
  its run page when a tag carries the same code as the last one.
- **runner.py is a thousand lines shorter.** Signing, verification,
  secrets, key policies, and the audience check moved to
  `runner/verify.py`; the task board to `runner/board.py`; the text
  helpers they share to `runner/textutil.py`. Every name is bound
  back onto `runner.runner`, so callers and tests resolve what they
  always did. The pattern -- stdlib only, no import of runner.py,
  the runner's logger found live -- is the one the next pieces
  follow. No change to what the runner does.
- **Three doc statements brought in line with the code**: the
  redacted view's shape, a spent query budget's answers, and
  `--inspect sources`.

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.12.56 - 2026-10-22

- **Every pipeline timer is off, to measure.** The mutation job's
  `timeout-minutes: 40` -- the pipeline's only explicit job timer --
  is removed by the owner's decision, so a run shows how long it
  really takes instead of where a guard cut it. The platform's
  360-minute ceiling still applies. `tests/test_build_config.py`
  pins the experiment (no timer on mutation, none in any workflow)
  and says how to end it.

- **The red and the slow are now named on the run page.** The Linux
  suite runs with `--durations 25` and the Windows shards with
  `--durations 15`, so unittest lists the slowest tests after each
  run. `tools/run_tests_parallel.py` reports each shard's wall time
  and, under GitHub Actions, turns every `FAIL:`/`ERROR:` line of a
  failed shard into an annotation naming the test. `tools/skip_guard.py
  --annotate` spends its ten annotations on test ids first and
  annotates nothing when the verdict is OK; fixture noise used to
  take the slots before the real failure.

- **Six days of CI, read as a corpus.** `docs/reports/v3.12.56/
  ci-failures.md`: 1,000 build runs and their jobs and steps. No
  timer ever fired. The red was the suite -- Windows twice as often
  as Linux, almost never both; the 13-hour stalls were the retired
  `macos-13` label, since moved; mutation is a release's entire long
  pole and gates nothing. The report lists the failure modes seen
  and what to cut.

- **The first red run proved the annotations and found two holes.**
  Main at f0a69dd went red on both suites, and the Windows run page
  named the test for the first time: `under_actions({})` fell
  through to the real environment, where Actions sets the variable.
  Fixed, with the two holes the same run showed: `skip_guard` now
  reads the verdict unittest prints last (a fixture's bare `OK`
  earlier in the log blinded it, and would have fooled
  `--require-ok` the same way), and the shard runner's own tests
  run with `GITHUB_ACTIONS` unset so a fake red shard never
  annotates a real run. The suite is run under the CI environment
  variable before a release from now on.

<!-- Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c -->

## 3.12.54 - 2026-10-22

- **Three source pins that 404'd.** The first lock missed
  softflowd's netflow files (they live on `master`, not the
  v1.1.1 tag), Sysmon's `LICENSE.txt`, and the NATS client
  protocol page. Those paths are corrected.
- A design note for agent stamps is in
  `docs/design/agent-stamp-design.md`. It is a note, not a
  behavior change.

## 3.12.53 - 2026-10-22

- **The extension doc no longer names the release it ships in.**
  `docs/extensions.md` said "at least 3.12.52" while 3.12.52 was
  the version being tagged. The evergreen-doc test forbids that,
  and it is the only failure in the 3.12.52 Windows job. The
  sentence now points at the changelog instead of a number.

## 3.12.52 - 2026-10-22

- **OAuth consent waits for its own callback.** The redirect
  listener ignores a favicon, a stale tab, and any callback
  whose state is not this consent's. A matching code or error
  is what ends the sign-in. The previous tests still expected
  a bare path to finish it as "unknown", which is what turned
  the last main run red on the suite and on Windows.

- **Feed senses carry the format they parse.** Each of the eight
  feed senses (Suricata, Zeek, osquery, Falco, Wazuh, AIDE, Sysmon,
  softflowd) now names an `upstream` in its manifest -- repository,
  ref, pinned commit, and the few files that define the log or
  record it reads -- and `tools/fetch_upstream.py` carries those
  files into `<extension>/upstream/` beside the adapter, licenses
  included. The fetch is a blobless sparse git checkout; the whole
  set is budgeted at 5 MiB (1.2 MiB used) and the build fails past
  it or when a file is stale or hand-edited. New drift tests assert
  the fields each adapter reads are still defined in the source it
  carries. A nightly `upstream-pins` workflow moves the pins, reruns
  those tests, and commits only when they pass. `docs/extensions.md`,
  "Upstream: carrying the format you parse". No change to what the
  runner does; the manifest field is validated and never fetched by
  the agent.

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

- **Every extension brings its own code for the Oracle.** The first
  time the agent loads a sense or starts a transport, it gives the
  Oracle the extension's installed code and fetches, in the
  background, what its optional `sources.json` declares: its
  published source, the upstream project it wraps, the specs it
  speaks. On every box by default, a Pi Light with no model
  included (`extension_sources`). The release job pins every
  declared upstream (`project/EXTENSION-SOURCES.lock.json`) and a
  box refuses bytes that differ. A written disclosure rule decides
  what the Oracle sees: provide by default, withhold when the owner
  (or the author) says so. `--inspect sources`, `--fetch-sources`.
  `docs/extensions.md`, "Sources".
- **pip installs get their transports.** The wheel now carries each
  shipped transport's `extension.json`; the 3.12.50 wheel had none,
  so a pip install discovered no transport at all.
- **Provenance bundles.** Each feed's `upstream.json` keeps its
  upstream's license and pinned commit under
  `<extension>/provenance/<name>/`, verified offline in the build
  (`tools/vendor_upstreams.py`). The folder is `provenance/`, not
  `upstream/`, so the format files' nightly fetch cannot delete it.

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

## 3.12.51 - 2026-10-22

- **Windows Oracle asks no longer get dropped.** The chat
  server listened with a backlog of 5. Eight asks at once
  filled it, Windows aborted the rest (WinError 10053), and
  the send-button test saw 2 answers out of 8. That is the
  failure that turned the 3.12.25 Windows job red. The
  backlog is 32, and a refused localhost socket is retried.
- The other red runs in this stretch were already fixed:
  the unregistered "posix spawn arm" skip (3.12.25), the
  tar exec bit Windows never writes (3.12.27 and 3.12.28),
  and the `file://C:\...` clone URL (3.12.30). The twenty
  tags from 3.12.31 through 3.12.50 were the same code as
  3.12.30 and their tag runs passed.

## 3.12.50 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.49 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.48 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.47 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.46 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.45 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.44 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.43 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.42 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.41 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.40 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.39 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.38 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.37 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.36 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.35 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.34 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.33 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.32 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.31 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.30 - 2026-10-22

- **Windows snapshot test.** The shallow-clone check built
  `file://C:\...`, which is not a file URL. It now uses
  `pathlib.Path.as_uri()`, so git gets `file:///C:/...`.
  The module also stays importable when the Windows
  simulator breaks `shutil.which`.
- No change to what the runner does. Mirrors are still on
  3.12.26 until a Windows job passes and the release job
  publishes.

## 3.12.29 - 2026-10-22

- **The Windows job can finish a release again.** The new
  snapshot test required a Unix exec bit. On Windows, `chmod`
  plus `tar.add` never writes that bit, so the suite failed,
  the release job was skipped, and 3.12.27 never reached
  GitLab or SourceForge. The test now writes the bit into the
  tar header, which is what inject is supposed to keep.
- Mirrors are otherwise current through 3.12.26: GitLab
  releases, SourceForge files (Linux, macOS, and Windows
  defaults), and both git mirrors at that tag.

## 3.12.28 - 2026-10-22

- Same code as 3.12.27. No change to what the runner does.

## 3.12.27 - 2026-10-22

- **Every release ships the whole project.** Each install
  archive now carries `project/`: every tracked file at the tag,
  the full git history as `project/.history/homing-pigeon.bundle`,
  and `CI-SNAPSHOT.json` — every workflow with its triggers and
  jobs, the platform each build ran on, and the test results of
  the run that built the release. `PROJECT-SNAPSHOT.md` indexes
  it with links pinned to the commit. The same snapshot ships
  alone as `homing-pigeon-project-<version>.tar.gz`. The release
  job builds it once, after the test job, and adds it to the
  finished archives before `SHA384SUMS`, so the sums and the
  attestation cover it (`tools/make_snapshot.py`).
- **The Oracle can read it.** The installer copies `project/`
  into the state dir (an upgrade replaces it whole), and the
  Oracle's context names it, so the local model can read the
  source, the tests, and the CI that built this release with no
  network. This is the groundwork for the Oracle recommending CI
  changes and unit tests from the environments it fails in.
- **Links.** PROTOCOL.md's Agent Guide, README, INSTALL, RUNBOOK
  and `docs/verification.md` point at the source, the tests, the
  CI workflows, and the snapshot. RUNBOOK no longer states a file
  count for the release.

## 3.12.26 - 2026-10-22

- **CI.** A push runs the plentiful proofs only. macOS,
  Windows, and ARM hosted runners, and the board legs, run
  nightly. Binary jobs start beside the suite. The release
  still waits for the suite and for every artifact. The
  reasoning is `docs/design/ci-runtime.md`. No change to
  what the runner does.

## 3.12.25 - 2026-10-22

- **More boards, same push.** The nightly platform proof now
  covers the userspace a Pi competitor ships: 64-bit Pi OS
  and Armbian, Ubuntu under a Jetson and on Odroid N2, the
  32-bit Ubuntu a PandaBoard and an Odroid XU4 shipped,
  Alpine on those 32-bit boards, and ROS 2 Humble and Jazzy.
  A push does not run them. 32-bit Pi OS, BeagleBone, CHIP,
  and the Tinker Board were already the Debian armv7 leg.
- **The suite is green again.** The relay spawn test skipped
  on Windows with a reason the skip registry had not been
  told about, so the Ubuntu job went red. The reason is
  registered. The Windows arm of that launch is its own test.
- No change to what the runner does.

## 3.12.24 - 2026-10-22

- **Docs reorganized to the common layout.** The root keeps
  README, INSTALL, CHANGELOG, CONTRIBUTING, SECURITY, AGENTS,
  PROTOCOL, and ENTERPRISE. TRANSPORTS, SAFEGUARDS, RUNBOOK,
  and FUTURE moved to `docs/`; design records to
  `docs/design/`; four retired notes and RESEARCHER_IDENT to
  `docs/archive/`. PROTOCOL.md and the IETF drafts did not
  move, so their published URLs still work. Links to the
  four moved root files now need the `docs/` prefix.
- **FAQ: "What can I actually use this for?"** Use cases from a barn Pi to camera traps,
  each tied to the feature and doc that makes it work.
- No change to what the runner does.

## 3.12.23 - 2026-10-22

- **CI.** A red suite is the suite's own exit code again:
  `tee` can no longer hide it. A failure is also a check
  annotation, so the test name and the exception are
  readable without the log. No change to what the runner
  does.

## 3.12.22 - 2026-10-22

- **The release can finish.** GitHub retired the `macos-13`
  runner in December 2025. The Intel macOS build was still
  asking for it, so the release job sat in that queue and
  never published. It now asks for `macos-15-intel`. No
  change to what the runner does.

## 3.12.21 - 2026-10-22

- **Windows build.** The job-claim tests called `os.kill(pid, 0)`
  to find a pid that is not running. On Windows that is
  WinError 87, not "no such process", and it failed
  `build-windows`. The tests ask the process table there, the
  same way the runner does.
- **No runner change.** Coverage on this tree is 96.8%
  statements. The doc tree was reorganized. What the runner
  does is the same as 3.12.20.

## 3.12.20 - 2026-10-21

- **A computer with no Python.** The common one is a Windows
  PC, which does not ship Python. Download the Windows zip
  and run `homing-pigeon.exe`. Do not install Python. The
  binary carries its own interpreter, and so do the Linux
  and macOS binaries. The release proves it: Windows starts
  the exe with Python off `PATH`, and the Linux binary
  starts in a Debian image that has no `python3`. A
  television OS still cannot run this. The board behind the
  screen, if you control it, is the Linux archive, and that
  board does not need Python either.

## 3.12.19 - 2026-10-21

- **Release.** Same code as 3.12.18.

## 3.12.18 - 2026-10-21

- **Release.** Same code as 3.12.17.

## 3.12.17 - 2026-10-21

- **FAQ: the duty of care sits with the SI.** A new entry in
  `docs/FAQs.md` says why the runner does not protect a beginner
  from installing on the wrong computer: the runner is the dumb
  end of the wire, the vendors claim their models act
  responsibly, and the project takes them at their word.

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.12.16 - 2026-10-21

- **Release.** Same code as 3.12.15.

## 3.12.15 - 2026-10-21

- **Release.** Same code as 3.12.14.

## 3.12.14 - 2026-10-21

- **Release.** Same code as 3.12.13.

## 3.12.13 - 2026-10-21

- **A skipped test has to say why.** Every skip reason in the
  suite is registered with the reason it is legitimate and
  where the test does run. An unused registration fails, and
  a skip hidden behind `if True` is refused. The workflows
  no longer hardcode a test count, and `continue-on-error`
  stays only on the release mutation job, where it is
  documented.

## 3.12.12 - 2026-10-21

- **A television is not a runner.** Tizen, webOS, Roku, and
  Apple TV are refused before any file is copied. So is any
  environment that cannot execute a shell, including an
  Android set whose app cannot exec. Android with a shell
  (a sideloaded terminal) is warned and then installed as
  `display-board`: no model, no service, jobs run as that
  app's user. A USB accelerator is not the computer.
  `--profile display-board` is the no-model install for a
  dedicated Linux board behind a screen.
- **Three more frozen binaries.** Linux ARM64 (no Pi Light
  marker), Windows ARM64, and Intel macOS. Each is built on
  the matching runner. The SourceForge defaults stay Windows
  x64, Linux x64, and Apple Silicon.
- **Enforce mode can see the interpreter.** The sandbox
  binds that interpreter's install prefix read-only, so a
  pyenv, a venv, or a toolcache Python is not missing inside
  the wall. The bind is written into the audit record.
- **Python 3.9 imports again.** Annotations in the installer,
  the mailbox, and setup are lazy, matching the declared
  floor.

## 3.12.11 - 2026-10-21

- **Bash-only scripts are not repaired onto `sh`.** An array,
  a here-string, `declare`, process substitution, or a
  substring expansion means the job stays as sent. A plain
  `#!/bin/bash` script with none of those is still repaired.
  `send_job.py verify` prints one line naming the digest of
  what was received and the first line of what ran.
- **Extension output is in the runner log.** Transport
  extensions relay each line into the same log `--logs`
  tails.
- **The release is proved before it is published.** Repair
  is run on Alpine with no bash, on x86_64 and arm64. A
  skipped proof fails the build. POSIX archives and the
  Docker image are smoked before publish.

## 3.12.10 - 2026-10-21

- **Release.** Same code as 3.12.9. The 3.13.0 tag was
  removed and is not part of this line.

## 3.12.9 - 2026-10-21

- **Code scanning is clear.** Three queries still fired after
  3.12.8, all false positives: clear-text logging of a line
  that does not contain a secret, the fixed Oracle
  classifier pattern, and the DTLS listen address. The
  default suite does not honor a comment on the line, so
  those three are excluded in the CodeQL config. The other
  queries stay on.

## 3.12.8 - 2026-10-21

- **Code scanning.** The open CodeQL alerts were false
  positives: test fixtures, sample sensors that name an empty
  env var and do not print the secret, the result SHA-384
  digest, the job script written so it can run, and operator
  reports that show key ids rather than secret values. Ignore
  rules cover those. The checks stay on for the runner.

## 3.12.7 - 2026-10-21

- **3.12.6 did not publish.** The Windows test job failed the
  live-claim check. That test wrote pid 1 into the claim file.
  Pid 1 is alive on Linux and usually nobody on Windows, so
  Windows treated the claim as dead and took it. The test now
  holds a real second process. The claim rule is unchanged.

## 3.12.6 - 2026-10-21

- **Skip the personal-documents check.**
  `--ignore-personal-documents` on the runner skips the scan
  for that process. The same flag on the installer skips the
  warning and writes it into the service command. The banner
  does not mention the flag. `--help` does.

## 3.12.5 - 2026-10-21

- **Personal-documents warning.** On startup, and before an
  install copies files, the program looks at file and folder
  names in the home Documents, Desktop, and Downloads. A legal,
  tax, or medical name prints a fixed banner: do not install
  here unless you are a proficient system administrator. No
  file is opened, and the name that matched is not recorded.
  Decisions: docs/personal-documents-warning.md.

## 3.12.4 - 2026-10-21

- **3.12.3 did not publish.** Its test job failed: the seen-file
  temp name did not match the Linux pin, and the Windows lock
  import ran on Linux when a test pretended to be Windows.
  Binaries for that tag were not built. This tag is the same
  race fixes, with those two corrected.

## 3.12.3 - 2026-10-21

- **Two runners, one state directory.** A job is claimed on
  disk as well as in memory. `seen.json` is merged, not
  replaced. A crash drops the claim. A live claim leaves the
  mail unseen so the next poll can take it.
- **Channel ack checks the bytes.** A job file rewritten after
  the read stays in the inbox. A same-length rewrite used to
  match the timestamp and get moved to done unread.
- **Version 2 answer slot.** Job ids that differ only past 120
  characters no longer share one question. A second valid
  answer is kept as late context. The first still wins.
- **Board offer returns a copy**, so a later complete cannot
  change the reply being sent.
- **Learning ledger trim replaces the file** instead of
  truncating it under a reader.

## 3.12.2 - 2026-10-21

- **Channel reliability.** A job whose failure is retryable stays
  unseen on the channel instead of being consumed, and a result
  that does not land rolls the seen-set back and leaves the
  envelope. IMAP SEARCH/FETCH are serialized with STORE. The
  security-events trim replaces the file instead of truncating
  it under another writer.
- **Board subcommands encrypt by default**, like `new`.
- **Protocol version 2 questions.** A question stays unseen
  until its answerer reads it, and the answer deadline starts
  at send.
- **Docs bent to shipped behavior.** The 2026-10-20 claims
  audit's 18 spec items are closed, and a 2026-10-21 round bent
  10 more docs, closed the three PROTOCOL.md items PC-01..03,
  and documented 30 previously undocumented knobs.

## 3.12.1 - 2026-10-21

- **Frozen builds include the version 2 module.** The one-file
  executables load `runner.protocol_v2` dynamically, so PyInstaller
  needs it named. The 3.12.0 tag failed that check in CI before
  anything was published. No protocol change.

## 3.12.0 - 2026-10-21

- **Protocol version 2, as messages beside a version 1 job.**
  A runner with `protocol_v2` sends a determination when the
  Oracle does not expect a clean pass, and a deterministic
  Oracle also sends the question it would have asked a local
  model. Any holder of a trusted secret may answer.
  `answer_only` is the laptop that answers and does not
  execute. One answer decides; a late one is context. The
  segments ride the version 1 result and do not change what
  runs. Off unless the operator turns it on. Jobs stay
  version 1.

## 3.11.63 - 2026-10-20

- **Version rev.** No functional change from 3.11.62.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.62 - 2026-10-20

- **Version rev.** No functional change from 3.11.61.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.61 - 2026-10-20

- **Version rev.** No functional change from 3.11.60.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.60 - 2026-10-20

- **Version rev.** No functional change from 3.11.59.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.59 - 2026-10-20

- **Version rev.** No functional change from 3.11.58.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.58 - 2026-10-20

- **Version rev.** No functional change from 3.11.57.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.57 - 2026-10-20

- **Version rev.** No functional change from 3.11.56.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.56 - 2026-10-20

- **Version rev.** No functional change from 3.11.55.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.55 - 2026-10-20

- **Version rev.** No functional change from 3.11.54.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.54 - 2026-10-20

- **Version rev.** No functional change from 3.11.53.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.53 - 2026-10-20

- **Version rev.** No functional change from 3.11.52.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.52 - 2026-10-20

- **Version rev.** No functional change from 3.11.51.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.51 - 2026-10-20

- **Arg-pattern timing test allows a slow Windows runner.**
  The v3.11.50 tag did not publish. `test_long_arg_is_fast`
  measured the whole job, and a loaded runner took 10.5s
  against a 5s ceiling. The main push of the same commit
  passed. The ceiling is 30s. The pattern is still linear.

## 3.11.50 - 2026-10-20

- **Version rev.** No functional change from 3.11.49.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.49 - 2026-10-20

- **Version rev.** No functional change from 3.11.48.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.48 - 2026-10-20

- **Version rev.** No functional change from 3.11.47.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.47 - 2026-10-20

- **Version rev.** No functional change from 3.11.46.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.46 - 2026-10-20

- **Version rev.** No functional change from 3.11.45.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.45 - 2026-10-20

- **Version rev.** No functional change from 3.11.44.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.44 - 2026-10-20

- **Version rev.** No functional change from 3.11.43.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.43 - 2026-10-20

- **Version rev.** No functional change from 3.11.42.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.42 - 2026-10-20

- **Version rev.** No functional change from 3.11.41.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.41 - 2026-10-20

- **Version rev.** No functional change from 3.11.40.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.40 - 2026-10-20

- **Version rev.** No functional change from 3.11.39.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.39 - 2026-10-20

- **Version rev.** No functional change from 3.11.38.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.38 - 2026-10-20

- **Oracle ask tests wait longer on a loaded Windows runner.**
  The v3.11.37 tag published, but its main push failed
  `test_random_questions_all_carry_the_line`: a loopback
  POST to the test server timed out at 5 seconds. The
  client waits 20 now.

## 3.11.37 - 2026-10-20

- **Windows process tree ignores a reused pid.** Toolhelp
  still names the previous owner's children. On the
  v3.11.36 tag a one-line job was charged with 144
  processes, the storm fired, and the env-gate test saw
  that audit line. The main push of the same commit did
  not. A process older than the job is not part of the
  tree. A process that cannot be opened is counted once
  and not walked. That tag did not publish.
- **`--inference-only` honors an in-place oracle_mode flip.**
  A Pi Light box that sets `oracle_mode` to `llm` in
  config.json and re-runs the flag now installs the model
  instead of skipping.
- **Result policy keeps the spec-required members.**

## 3.11.36 - 2026-10-20

- **Version rev.** No functional change from 3.11.35.
  That tag and its main push both finished green,
  Windows and SourceForge included. This tag is the
  next look.

## 3.11.35 - 2026-10-20

- **Version rev.** No functional change from 3.11.34.
  That tag and its main push both finished green,
  Windows and SourceForge included. This tag is the
  next look.

## 3.11.34 - 2026-10-20

- **SourceForge waits for a new file to be indexed.** The
  v3.11.33 upload landed, then the default-download PUT
  got a 404 and the job exited before the git mirror.
  That call now retries for about a minute.

## 3.11.33 - 2026-10-20

- **Version rev.** No functional change from 3.11.32.
  The FUTURE.md note about a USB neural-link peripheral
  landed after that tag, and its main push finished
  green, Windows included. This tag is the next look.

## 3.11.32 - 2026-10-20

- **Version rev.** No functional change from 3.11.31.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.31 - 2026-10-20

- **Version rev.** No functional change from 3.11.30.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.30 - 2026-10-20

- **Version rev.** No functional change from 3.11.29.
  The FUTURE.md edit landed after that tag, and its main
  push finished green, Windows included. This tag is the
  next look.

## 3.11.29 - 2026-10-20

- **Version rev.** No functional change from 3.11.28.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.28 - 2026-10-20

- **Version rev.** No functional change from 3.11.27.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.27 - 2026-10-20

- **Version rev.** No functional change from 3.11.26.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.26 - 2026-10-20

- **Version rev.** No functional change from 3.11.25.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.25 - 2026-10-20

- **Version rev.** No functional change from 3.11.24.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.24 - 2026-10-20

- **RESEARCHER_IDENT.md rides with the mutant tree.** The
  new root doc made the live-docs guard fail stats
  collection: mutmut only copies what also_copy names, and
  the main push of that file died in the test job before
  any build ran. It is on the copy list now.

## 3.11.23 - 2026-10-20

- **Version rev.** No functional change from 3.11.22.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.22 - 2026-10-20

- **Version rev.** No functional change from 3.11.21.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.21 - 2026-10-20

- **Version rev.** No functional change from 3.11.20.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.20 - 2026-10-20

- **Version rev.** No functional change from 3.11.19.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.19 - 2026-10-20

- **Version rev.** No functional change from 3.11.18.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.18 - 2026-10-20

- **Windows monitor test stamps inside the resource window.**
  The evidence was written before the monitor started, and
  the resource window only looks one second back. On the
  v3.11.17 main push that write took longer, so
  `resource_event` was missing while confinement (five
  seconds of slack) still matched. The tag of the same
  commit was fast enough to publish. The test now stamps
  from the monitor's own start.

## 3.11.17 - 2026-10-20

- **Version rev.** No functional change from 3.11.16.
  That tag published, Windows included. The only red run
  still on the board is v3.11.14, which v3.11.15 already
  fixed. This tag is the next look.

## 3.11.16 - 2026-10-20

- **Version rev.** No functional change from 3.11.15.
  The main run after that cut, including the v2 editor
  note, finished green, Windows included. This tag is the
  next look at the pipeline.

## 3.11.15 - 2026-10-20

- **Windows canary test stops tripping on its own rewrite.**
  The CRLF regression test replaced every `\n`, including the
  one inside an existing `\r\n`, so a file that was already
  CRLF became CR-CR-LF and the watcher correctly called that
  a content change. The v3.11.14 tag run failed build-windows
  on that and did not publish. The test now writes the other
  line ending of the same text.

## 3.11.14 - 2026-10-20

- **Mutation cannot pin a tag run for hours.** The job has
  no functional product change. It now dies at 40 minutes
  instead of the platform default of 6 hours. The v3.11.11
  run measured about 25 minutes; stacked tag runs were
  sitting in_progress long after the mirrors had published.
  Mutation stays a signal: it still cannot fail the publish.

## 3.11.13 - 2026-10-20

- **Version rev.** No functional change from 3.11.12.
  Last cut asked for on top of the one already on the mirrors.

## 3.11.12 - 2026-10-20

- **Version rev.** No functional change from 3.11.11.
  v3.11.11 is already on the mirrors; this cut is the
  rev that was asked for on top of it.

## 3.11.11 - 2026-10-20

- **Windows build can finish.** The guided-fuzz campaign
  compared coverage across two runs in one process. On the
  Windows runner those sets disagreed by four lines inside
  `runner.runner.log`, the minute-rollover branch, which is
  wall-clock gated. The tracer no longer records that
  function, so a campaign's coverage is the parsers again.
  v3.11.10's Windows job failed on this and never published.

## 3.11.10 - 2026-10-20

- **job-fuzz: a sense that fuzzes the jobs this box
  already ran.** A new example sense plus a core one-shot
  door (`--run-variant FILE`): the sense keeps a bounded
  corpus of the runner's retained jobs, mutates them on
  idle cycles only, and runs each variant through the
  runner's own validation and confined execution; findings
  file as Oracle signals (hard failures, divergence from
  the seed's recorded outcome, coverage novelties) and are
  context for future opinions, never a gate on the seed
  job. Variants are mutations of verified jobs, so they
  are never admitted through the job path; the door copies
  an allowlist of job keys and drops everything else. The
  corpus learns: novelty-reaching variants are promoted
  into a distilled tier, splice and dictionary mutators
  widen the neighborhood, relation probes carry an
  expected class and digest, interesting variants are
  minimized before they file, hard failures triage into
  reason buckets, and seeds earn their budget by yield.
- **Windows fixes.** job-fuzz splits its runner command
  per platform (POSIX shlex ate the backslashes out of
  Windows paths, so no campaign could run there), and the
  Pi Light end-to-end test drains the wake gate's brief
  thread before its temp tree comes down. 3.11.9 was
  tagged but never published: its release build failed on
  that cleanup race (WinError 145). This release
  supersedes it.

## 3.11.9 - 2026-10-20

- **Mutation stats can finish.** mutmut's stats pass sets
  `MUTANT_UNDER_TEST=stats` and rewrites the mutated module
  with trampolines that need mutmut's own process. The DTLS
  sidecar inherited that variable, hit
  `validate_shared_secret` on startup, and died with exit 1,
  so `pytest -x` aborted the stats run ("failed to collect
  stats"). Transport children now drop the variable and run
  the original module. A raw docstring in `review.py` also
  drops the invalid-escape SyntaxWarning Python 3.12 printed
  during that job.

## 3.11.8 - 2026-10-20

- **Version rev.** No functional changes from 3.11.7; the
  tree is identical apart from the version constants and
  this entry.

## 3.11.7 - 2026-10-19

- **Strictness batch.** The protocol version field is now
  checked as an integer in the strict sense: JSON `true`
  and `1.0` are refused, as draft Section 9 states. Key
  selection follows draft Section 10: a present `key_id`
  must name a configured secret or the job is refused
  before its MAC is checked; the empty identifier names
  the default secret. Downloads accept `https://` URLs
  only, and a redirect to any other scheme is refused.
  The DTLS transport extension enforces the shared-secret
  entropy floor at its own endpoint and refuses to start
  below it, as the sender already did. Malformed DTLS
  records are logged at WARN instead of dropped silently.
- **Documentation corrections from the claims audit.**
  CONTRIBUTING's chat-privacy account now rests on
  redact-before-write, which is what the code does; two
  parked items -- the `av` detections sense and the
  Windows WFP cage -- are described as not built, which
  they are; and a set of smaller audit fixes lands across
  thirteen documents.
- **Seeded mutation testing.** A scheduled, non-gating
  twin of the release mutation job reruns the security
  module's mutants under a fresh recorded seed each week,
  so order-dependent survivors have nowhere permanent to
  hide. The release job itself is unchanged and stays
  deterministic.

## 3.11.6 - 2026-10-19

- **The cleartext posture, completed.** 3.11.5 refused an
  unencrypted job on the shipped CLI path; the refusal now
  applies at the one acceptance point every channel
  funnels through, so the form decides, not the channel:
  mail, file, NATS, and DTLS deliveries are refused alike,
  with key-policy reject semantics (message marked seen,
  an `auth_rejection` event recorded, the job_id not
  recorded in the seen set). `--allow-cleartext` remains
  the only enable and there is still no configuration
  key; `install.py` can now bake the flag into the
  installed service command like the other run flags, the
  startup log announces it when on, and the diagnose
  harness sends its round-trip job encrypted so it works
  without the flag. The spec text states the posture in
  full: draft Sections 16, 17, and 19.4, PROTOCOL.md
  Section 8, and the configuring doc. The test suite's
  fixtures now send encrypted jobs end to end, which is
  what surfaced the next fix.
- **`reply_to` routing fixed on the email transport
  extension.** The extension read the result's destination
  out of the raw job body, so for encrypted jobs — the
  default form — results fell back to the mailbox instead
  of the job's `reply_to`. The core now states its routing
  decision in a `<ident>.target.txt` sidecar beside the
  channel result (additive at transport contract v1;
  extensions that ignore it behave as before), and the
  extension honors it after re-checking the address
  against the same rule the direct path applies. Found by
  the fixture migration above: cleartext fixtures had
  been masking it.
- **New FAQ entry:** why the one shared secret safely
  keys both the HMAC signature and the job encryption —
  the AES key is an HKDF output, neither construction
  feeds the other, and the stated cost of reuse is that
  a compromised secret opens both.

## 3.11.5 - 2026-10-19

- **Cleartext is a flag, not a mode.** The runner refuses an
  HMAC-signed job that is not encrypted unless it was started
  with `--allow-cleartext`. `send_job.py --cleartext` and
  `send_dtls.py --cleartext` still send that body, and the
  shared secret is still required. There is no config key
  for this. Encrypted jobs are unchanged. Protocol version
  stays 1.

## 3.11.4 - 2026-10-19

- **PROTOCOL.md names the AEAD primitive.** The crypto
  section still claimed "exactly two cryptographic
  primitives" and "the protocol does not encrypt
  payloads" — text from before per-job encryption
  shipped. It now names the third primitive (AES-256-GCM,
  keyed per job by HKDF-SHA-384, the signed `hp_enc`
  envelope, verify-before-decrypt, receiver MUST accept)
  and states the shipped posture: confidentiality is a
  property of the signed object, the reference senders
  encrypt by default, and cleartext is an explicit
  sender choice, never a silent fallback. Documentation
  only; no behavior change.
- **Docs match the draft.** PROTOCOL no longer treats email
  as the whole protocol, no longer calls `job_id` a UUID,
  and no longer says a cleartext job's confidentiality is
  the mail TLS hop. The FAQ, the configuring doc, the
  example config, and the `mail_tls_required: false`
  warning say the same thing: that switch relaxes hop
  verification, and the confidentiality property is the
  envelope. `STYLE.md` is gone; the mutation copy list
  no longer names it. FUTURE.md marks BUILT entries as
  a decision record, not work.

## 3.11.3 - 2026-10-19

- **falco-feed files `Error`-priority rules.** The sense
  named all eight of Falco's priorities but mapped only
  seven; an `Error` alert fell into the malformed bucket
  and was ignored. `Error` now files as `falco_critical`
  (high) — the error-and-above tier — and a test accounts
  for all eight names.
- **Inline `script_sha384` is verified.** `execute_job`
  checked the digest only for `script_url` downloads; an
  inline script carrying `script_sha384` ran unverified.
  The digest of the script's UTF-8 bytes is now checked
  before staging, as PROTOCOL §3.2's −2 class always
  claimed.
- **Documentation consistency pass.** PROTOCOL.md's
  internal contradictions are resolved (the freeze was
  lifted for these deltas): §5 verification is stated
  per message type and names the job-shape checks behind
  the −2 class; the redacted view carries
  `output_digest`; task IDs state their own rule; "seen"
  distinguishes the mail flag from the seen-set; budget
  accounting is per key ID throughout; the confinement
  predicate excludes the runner's own tree. The same
  internal-consistency pass ran over every live document
  — README, INSTALL, RUNBOOK, TRANSPORTS, the security
  docs, `docs/`, the IETF draft (envelope steps now
  select the key before verifying the MAC; the
  SP 800-38D reference cites the right document),
  hardening, and the extension READMEs.

## 3.11.2 - 2026-10-19

- **Coverage report.** Statement coverage on the 3.11.1 tree
  is 94.2% (14436 of 15326), 93.1% with branches, from 3979
  tests. The report is `docs/reports/v3.11.1/coverage.md`.
  No runner behavior changes in this release.

## 3.11.1 - 2026-10-19

- **DTLS key schedule uses the suite's hash.** Suite
  0x1302 fixes SHA-384; the AES change had left the
  handshake hash on SHA-256, with the PSK binder splice
  and the stateless cookie sized for a 32-octet digest.
  Transcript, HKDF schedule, Finished, binder, and cookie
  now ride SHA-384 end to end, pinned by tests including
  the in-test RFC 8446 recomputation.
- **No mandatory binding.** The draft no longer requires
  the email binding: conformance is per binding, an
  implementation offers at least one binding, and email
  is the default by guidance, not by mandate.

## 3.11.0 - 2026-10-19

- **AES-256-GCM.** Per-job encryption is AES-256-GCM (NIST SP
  800-38D). The envelope algorithm id is
  `aes-256-gcm/hkdf-sha384`. The DTLS ciphersuite on the wire
  is TLS_AES_256_GCM_SHA384 (`0x1302`). ChaCha20-Poly1305 is
  gone: a job or result encrypted by 3.10.1 or earlier does
  not decrypt.

## 3.10.1 - 2026-10-19

- **One protocol, version 1.** This release supersedes the
  3.10.0 tree, which was tagged before the no-v2 restructure
  landed. There is no protocol version 2: the DTLS session
  support is a binding of version 1, specified in the same
  IETF draft, and the DTLS greeting's `v` field carries the
  protocol version (1). Per-job AEAD encryption is a
  required capability of version 1 — implementations MUST
  support it, the reference sender encrypts by default, and
  cleartext is sent only by a sender's explicit choice.
- **Conformance is per binding.** The draft now states the
  security requirements as properties: object authentication
  (the signature/MAC) is REQUIRED on every binding and never
  moves to the transport; confidentiality is REQUIRED as a
  property on every binding and may be satisfied by the
  binding itself. On the DTLS binding the session provides
  it, so per-job encryption is OPTIONAL for the sender there
  (receiver support stays REQUIRED everywhere); on email and
  NATS the per-job encryption carries it; on the file binding
  it is local policy. A runner MUST offer the email binding.
- **Pipeline hardening.** The transport and encryption parser
  surfaces were fuzz-campaigned; the Windows surface is now
  simulated locally (path separators, SSL stores) so platform
  failures surface before CI; test-isolation fixes keep the
  suite green under shuffled order and unprivileged runs;
  `jobcrypto` validates key and nonce sizes in its own
  vocabulary; the audit report reads UTC stamps as UTC. The
  ruff gate is green on the whole tree.
- The Windows-surface simulator overlays `windll` even when the
  host already has one — an elevated runner's `IsUserAnAdmin`
  returns 1 — and restores the host objects afterwards.

## 3.10.0 - 2026-10-19

- **Transports are extensions.** The runner core is
  transport-blind: email, the watched folder, and NATS each run
  as a standalone extension program under one contract
  (TRANSPORT_API_VERSION = 1), supervised by the runner over
  per-extension file channels. Email remains the default; a
  3.9.0 config works unchanged; the shared secret is never
  handed to a carrying pipe. Anyone can drop in a transport —
  a valid manifest loads, registered or not.
- **DTLS session binding.** A new `dtls`
  transport extension terminates DTLS 1.3 sessions directly:
  the shared secret as external PSK, `psk_dhe_ke` only
  (forward secrecy is a hard requirement, resumption
  included; `psk_ke` is never offered or accepted),
  connection IDs so NAT rebinding survives, a stateless cookie
  exchange before any large flight. Off until the owner
  enables it — the product's first network-facing inbound
  listener (the loopback local-signal socket and the Oracle
  page predate it). The
  session's first message is the greeting: platform
  information tiered by the responder's own configuration
  (`none` / `family` / `standard` / `full`, default family),
  sent only after authentication. Client: `cloud/send_dtls.py`.
- **Per-job encryption, on by default.** `send_job.py` wraps
  the signed body in an AEAD envelope (AES-256-GCM,
  HKDF-SHA-384 key from the job's selected secret; stdlib-only
  `runner/jobcrypto.py`). The runner verifies the signature
  before decrypting; results mirror the job's form;
  `job_encryption` overrides explicitly; `--cleartext` is the
  deliberate interop escape. Cleartext jobs are still accepted
  and logged as such. No forward secrecy, stated wherever the
  feature is described: a compromised secret exposes every
  recorded encrypted job.
- **Mail TLS, required and forward-secret.** `mail_tls_required`
  (default true): IMAP over implicit TLS, STARTTLS required
  with the peer certificate verified, TLS 1.2 floor — and in
  the required posture TLS 1.2 sessions are pinned to ECDHE
  suites, so the hops are forward-secret as 1.3 is by
  construction. The opt-out relaxes verification only; no
  setting enables cleartext mail.
- **One draft, one version.** The IETF documents
  consolidated into `draft-homing-pigeon-00` (the one
  canonical file): one protocol version, with the email,
  file, NATS, and DTLS bindings in one numbering and one
  reference list — the DTLS work is a binding of version 1,
  not a second version. The short-lived pointer files are
  removed; the -00 file is the document itself. The draft's
  mail binding now requires TLS (MUST, RFC 8314/8996/9325),
  and per-job encryption is a requirement of the protocol,
  not an optional extension.
- FAQs gained the email-binding census and two refusals with
  reasons: no PGP/S/MIME (a cloud SI has a connector, not a
  mail client), and no public-key cryptography in the core
  protocol (no strangers to introduce; symmetric end to end,
  which is also the quantum-resistant posture).
- Windows Oracle chat answers a refused `/ask` (bad token,
  bad origin, oversized body) with that status. The body is
  read first, so the socket is not aborted before the browser
  can see it.

## 3.9.0 - 2026-10-19

- **The Oracle learns from its own calls.** Each opinion is
  frozen before the job runs and scored against the outcome
  in a local learning ledger, written before the result goes
  out. Two lesson channels: verified execution facts, and
  model-formed candidates born uncorroborated, promoted only
  by later corroboration, retired permanently by one
  contradiction. Each job reads the ledger fresh, host- and
  feature-filtered. A lesson authorizes nothing by itself —
  repair still needs the latitude, the mismatch re-verified
  on this job, and the result re-judged. Keys:
  `oracle_learning` (on), `oracle_learning_model` (off),
  `oracle_learning_promote_after` (2).
- README rebuilt as a landing page; the Windows test fixes
  that 3.8.9 needed landed here (POSIX assumptions in the
  coverage pins).

## 3.8.9 - 2026-10-19

Tagged but never published: the Windows build failed
(coverage-pin tests assumed POSIX) and 3.9.0 superseded it
the same night. Content: in-core file and NATS transports
beside email, and the two-gate rule — a credentialed
transport's required authentication counts as a second gate
beside the HMAC signature. Both were re-homed as transport
extensions in 3.10.0.

## 3.8.8 - 2026-10-19

- Fix: opinion predictions attach only under the effective
  latitude, not the job's raw request (claims audit B46).
- SourceForge and GitLab publish as jobs inside the tag build
  instead of separate workflows.
- Claims audit round 2 closed: 196 claims re-inventoried and
  resolved against the tree; satire kept by the maintainer's
  vote.

## 3.8.7 - 2026-10-18

- The Oracle's opinion defaults to `repair`: one certain
  environment mismatch is fixed before the run, re-judged, and
  recorded with the received digest. Owner ceiling `diagnose`
  restores the old behavior exactly.

## 3.8.6 - 2026-10-18

- Fix: `requirements-ci.txt` joins the mutation copy list;
  the 3.8.5 mutation job died in stats collection without it.

## 3.8.5 - 2026-10-18

- **IDS collectors:** eight adapters (Falco, Suricata, Zeek,
  osquery, Sysmon, AIDE, softflowd, Wazuh); osquery is the
  measured install default (~27 MB idle; Zeek ~230 MB, opt-in
  only). Capability-probed: installed is not sensing.
- **Remediation:** jobs that diverge from their opinion
  envelope can be stopped mid-run — deterministic tripwires
  (process storm, credential artifact, confinement escape)
  kill on sight; `remediation_mode: oracle` adds judgment for
  unlisted divergences, abstention recorded, never converted
  to a kill. Quarantine never deletes; AV referral records
  the scanner's own verdict. Default `deterministic`.
- Training Watch joins the extension catalog (24 senses).
- Release pipeline lifts from the OneFuzz audit: SHA-pinned
  actions, default-deny workflow tokens with exact per-job
  grants, BUILD-PROVENANCE.json in every archive, an SPDX SBOM
  among the nine release assets, pinned CI tooling,
  docs/verification.md.
- Fix: `--oracle-opinion` startup exit (string flag in the
  numeric overrides set).

## 3.8.4 - 2026-10-18

- Docs only: the remediation design written in full; STYLE.md
  trimmed; TRANSPORTS.md status note; the front page stops
  selling the lockdown posture as the shipped default.

## 3.8.3 - 2026-10-18

- Two senses: Resource Sentinel (rolling-window rates, not
  samples) and Job Watcher (per-job baselines from `retained/`).
  Catalog: fifteen.

## 3.8.2 - 2026-10-18

- **The Oracle's opinion is built:** a job may request a
  latitude (`off`/`diagnose`/`advise`/`repair`), capped by
  `oracle_opinion_mode`; tier-1 checks are deterministic; a
  repair is never silent and carries `received_digest`.
- **Pi Light:** `oracle_mode: deterministic` — the full
  runner and protocol with no local model — plus the ARM64
  Pi Light archive whose `default_profile` marker selects it.
- `dag_mode: advisory` (PROTOCOL 13.1); thirteen worked senses
  ship as examples; one-process CLI overrides for the runtime
  knobs; counted `-v` verbosity; the invocation line logged
  shell-quoted; designed `--help` on all three front doors.

## 3.8.1 - 2026-10-18

- Docs: the Oracle's-opinion design recorded (FUTURE.md +
  docs/oracle-opinion-design.md). Design only; built in 3.8.2.

## 3.8.0 - 2026-10-18

- **Claims audit:** 106 doc claims inventoried and decided one
  by one; corrections landed across the live docs (external
  facts re-verified, including the Mandiant acquisition and
  the Cloudflare Queues tier figures). PROTOCOL §8 names the
  two primitives actually used and states the protocol does
  not encrypt payloads; §10.1 names qwen3:1.7b the tested
  reference model. ORACLE_DASHBOARD.md removed.

## 3.7.41 - 2026-10-18

- Test fix: the local-signal fixture joins its brief thread
  before temp-dir cleanup (Windows WinError 145).

## 3.7.40 - 2026-10-18

- **Local signals:** same-box senses and extensions deliver
  signed alerts without mail — a watched `local-inbox/` folder
  (~1 s scan) or a loopback socket (port 39271) — through the
  mail path's one ingest core and gates. A high-severity local
  alert can wake the Oracle through a deterministic,
  cooldown-limited gate; the brief is recorded, never acted on
  by the gate itself.

## 3.7.39 - 2026-10-18

- Docs: the README prompt points at the published protocol
  URL (pigeon-home.com/PROTOCOLv1).

## 3.7.38 - 2026-10-18

- **User extensions:** a folder + `extension.json` manifest
  (declared signals, own semver, API version); strict manifest
  validation, undeclared signals refused at ingest, broken
  extensions refused and logged without touching the agent.
- The notable-access line in a retained summary names its own
  job id, so small models stop transplanting it onto neighbors.

## 3.7.37 - 2026-10-18

- Fix: `output_retention_days: 0` means keep-forever on every
  path (the expiry check's `or 7` disagreed with the prune).
- Coverage-guided fuzzing over the parser surfaces joins the
  suite (150 rounds, corpus grows only on new coverage).
- CI: the Windows shard reporter can no longer be crashed by
  its own output (UTF-8 end to end).

## 3.7.36 - 2026-10-18

- Security: the Oracle's log-tail context feed is scrubbed of
  quoted model replies and flagged jobs' logged output —
  runner.log itself keeps everything.
- CI: mutation's repeated in-process suite counts fixed
  (module-cache collision).

## 3.7.35 - 2026-10-18

- Security: a flagged (suspicious-access) job's raw output is
  withheld from the Oracle's context — summary, script, and a
  digest marker instead; the withheld text still feeds the
  reply gate as scan-only. CI: `tools/` joins the mutation
  copy list.

## 3.7.34 - 2026-10-18

- Default model is `qwen3:1.7b`, winner of the full eval
  battery (clean catches, no invention, history and detail).
  `--faster` pulls qwen2.5:3b.
- CI: the Windows suite runs sharded across four workers.

## 3.7.33 - 2026-10-18

- CI: a failed mutation job no longer fails the tag build
  (signal kept; mirrors key off the run conclusion).

## 3.7.32 - 2026-10-18

- Oracle chat: owner instructions dispatch — an action
  request whose first reply is prose-only is re-asked once
  with a directive to call the tool or name the blocker.

## 3.7.31 - 2026-10-18

- The interactive Oracle's charter restored: the owner's
  debugging partner with full hands (the mailbox prompt keeps
  its disclosure boundary; both sides pinned by tests).
- Fix: a job id ending in a newline is rejected (`$` matched
  before it).
- Coverage/mutation reports for 3.7.30 archived (91.8%
  statements; runner/security.py mutation 458/537 killed).

## 3.7.30 - 2026-10-18

- CI: the root manuals join the mutation copy tree (the tag
  job died on a missing INSTALL.md).

## 3.7.29 - 2026-10-18

- The Oracle chat works again in the browser: a raw newline
  inside a JS string had made the page's whole script a
  SyntaxError (Send did nothing); a `node --check` regression
  test now parses the served script. The chat box starts
  empty, loopback Sends without an Origin header reach the
  model, and the no_secrets attestation scans job output
  again (a merge had dropped its binding).

## 3.7.28 - 2026-10-18

- CI: mutation runs on version tags only.

## 3.7.27 - 2026-10-17

- `--faster` pulls qwen2.5:3b (the 1.5B model's Flag321
  verdicts didn't hold across paraphrases).

## 3.7.26 - 2026-10-17

- Protocol: messages use `"v": 1` again (see 3.7.20).

## 3.7.25 - 2026-10-17

- `--oracle-cli`: the terminal Oracle chat on the same ask
  pipeline as the web window.
- Detection: job summaries carry a deterministic "notable:"
  line when a script referenced a credential store or a path
  outside its workspace; artifact scan gains built-in YARA
  rules (hp_cred_dump, hp_reverse_shell) with ATT&CK tags.
- Flag321 field scenario pinned as unit tests (retention and
  context contracts).

## 3.7.24 - 2026-10-17

- Frozen builds ship the whole runner again: the importlib
  loader hid sibling modules from PyInstaller, so one-file
  builds silently omitted them. Every dynamic module is now a
  hidden import on all platforms, guarded by a test; Linux and
  macOS smoke the binaries' `--version`.
- Hardening: state files opened no-follow throughout; path
  containment for retained jobs, sandbox scripts, and the
  Oracle's file tools. Suite: 1,954 tests.
- Dependabot bumps folded in; Docker base python:3.14-slim.

## 3.7.23 - 2026-10-17

- Oracle chat: structured-data dumps and tool-call-shaped
  replies are withheld and re-asked once for plain prose.

## 3.7.22 - 2026-10-17

- Both mirrors carry the full release (archives, wheel,
  sdist, SHA384SUMS); first unattended GitLab publish.

## 3.7.21 - 2026-10-17

- Releases publish to SourceForge (best-effort; GitHub and
  PyPI never wait on it).

## 3.7.20 - 2026-10-17

- Protocol v2 on the wire: messages carry `"v": 2`; v1 is
  rejected unless the operator opts in per process with
  `--allow-protocol-v1`; the 128-bit secret floor is enforced
  on the sender too. PROTOCOL.md and the draft continue to
  specify v1, the specification of record. (3.7.26 returned
  messages to `"v": 1`.)

## 3.7.19 - 2026-10-17

- Debuggable logging: runner.log bounds become config
  (defaults 32 MB × 4), full job stdout/stderr land in the
  log, and an opt-in `oracle.log` keeps full-fidelity
  inference records (~2 GB worst case). Secrets never enter
  either log.

## 3.7.18 - 2026-10-17

- `--diagnose`: a black-box gauntlet against the real
  configured system (config audit, mailbox auth, model
  reachability, a signed round-trip job, an Oracle-context
  audit, acceptance probes, senses snapshot) writing a
  verdict report; the exit code counts failed sections.

## 3.7.17 - 2026-10-16

- The Oracle chat gets a real interface: bubbles, clock
  stamps on every message, elapsed time on the Working
  bubble. Summary questions are answered from the job index
  without tool rounds.

## 3.7.16 - 2026-10-16

- Version-only release moving the checkpoint line.

## 3.7.15 - 2026-10-16

- `--faster` for installer and runner: the 1B model for one
  process or an install, config untouched on a normal upgrade.

## 3.7.14 - 2026-10-16

- The chat cannot stall in silence: a Working indicator with
  elapsed seconds, warm model (keep_alive + background
  warm-up), a per-question wall-clock budget, empty stdin for
  tool commands. Summaries come from a computed job index at
  the head of the context, not the log tail.

## 3.7.13 - 2026-10-16

- Low-profile senses ride the existing watches: ATT&CK labels
  on audit lines, host-log tails, a one-line firewall posture
  diffed against its baseline, post-job artifact scans when a
  scanner is already installed, canary and AV-posture filings.
- runner/detection.py: per-job Sigma/YARA-style evaluation
  with ATT&CK ids and a rolling baseline; advisory only.

## 3.7.12 - 2026-10-16

- Oracle system watch on by default: Windows Event Log tail,
  registry persistence watch (diffed), canary tripwires with
  tokens that never silently re-baseline. (Supersedes the
  unpublished 3.7.11, whose Windows build failed.)

## 3.7.10 - 2026-10-16

- The local chat prompt is separated from the cloud ask
  rules: the operator is at this computer; open the files.
  The mailed ask path keeps its disclosure rules.

## 3.7.9 - 2026-10-16

- Property-based tests (Hypothesis) over the protocol core —
  and a real bug they caught: the signed-body extractor could
  pick a `{` inside a string literal as the object opener and
  reject a valid body. Infinity config values hardened.

## 3.7.8 - 2026-10-16

- Oracle agent: content-embedded tool calls replay as plain
  chat (Ollama rejected fabricated call history); inference
  failures log the endpoint's response body.

## 3.7.7 - 2026-10-16

- PROTOCOL.md ships inside the release binaries; the Oracle's
  prompt points the local model at it on demand.

## 3.7.6 - 2026-10-16

- The Oracle chat page opens with a role statement and a
  pre-filled summary prompt; content-embedded tool calls from
  small local models are detected and executed (known tool
  names only); the system prompt teaches the model the
  project's vocabulary and this box's real state paths.
