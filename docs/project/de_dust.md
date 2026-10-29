# Project de_dust: the test plan

<!-- Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

The conductor's campaign, 2026-10-26, to run indefinitely: a
coverage-guided seed corpus against every reader that stands
between bytes from outside and the agent's trust in them. This is
the plan from here on; the standing orders' section M is the loop
that runs it, `docs/use/questions.md` is where its questions and
findings go, and this file is revised as the campaign learns.
Nothing here names a person, a machine, a path or an address that
is real.

## 1. What the campaign is for

A reader is a function that takes bytes or text a peer delivered
and either turns them into trusted state (a job to run, an alert to
file, a result to accept) or refuses them. Every finding the
project's testing has produced from outside input came from a
reader: a refusal note that was not UTF-8 (Q60), a brace walk
that mis-segmented a signed body (Q61), an envelope reader that
raised the wrong exception (the corpus's first grow). The campaign
holds every such reader to its contract, continuously, with a
corpus that survives the process and grows only where it reaches
something new.

What it is not: a search for races, sandbox escapes or network
behaviour (those are the confinement and race suites), a model or
Oracle exercise, or job-fuzz the sense. In memory, no socket, no
secret that is real.

## 2. The instrument

`runner/tools/de_dust_corpus.py`, stdlib only.

- A **target** is a reader (or a small family of readers) with the
  files the tracer counts arcs in, a seed function, and a check
  function that holds one entry to the contract and answers
  `accepted`, `refused`, or a `Crash(kind, detail)`.
- An **entry** is one JSON line: `id` (a hash of kind and data),
  `kind` (`text`: a received body or raw message; `payload`: a JSON
  value the checker signs, seals or hands over), `data`, `from`
  (the seed's name or the parent's id), `mutator`, `arcs` (the
  line arcs the entry reached first). Bytes that are not UTF-8 ride
  as surrogate escapes, so a reader gets the exact bytes back.
- **Guidance** is line arcs under `sys.settrace` over the target's
  own files only. A child is kept when it reaches an arc no earlier
  entry reached. `sys.monitoring` was measured and is slower here;
  the signal is right for readers this size and the vocabulary is
  where the search goes, not the clock.
- **Mutation** is the job-fuzz vocabulary on text (truncate, drop,
  insert from a dictionary of protocol tokens, duplicate, splice,
  tamper the signature hex, plant a false marker, wrap in a quoted
  preamble or a mail trailer, CRLF, raw controls, case flips, number
  boundaries, brace noise, re-sign a parsed object after a JSON
  mutation) and on JSON values (replace a value at any path with a
  boundary value, delete a path, add or rename a key, mutate a
  string, mutate a number, nest deeper, splice another entry's keys,
  swap two values). Targets whose input is not text-shaped carry
  their own vocabulary: structural breaks for mail, flight breaks
  for DTLS.
- **Commands**: `seed` (adds the seeds a corpus lacks, never
  discarding what grows found; sealed seeds draw a counter nonce so
  their ids are stable), `grow` (`--jobs` at the core count,
  `--minutes` to cycle the targets with the seed moved on each
  cycle, least recently grown first unless `--order fixed`), `replay` (every entry against its contract, no tracer,
  what the test does), `promote` (after a fix, crashes that now
  refuse properly and reach something new move into the corpus),
  `stats` (sizes and the saturation mark), `platform` (every
  committed entry replayed on the host and again under the
  simulated Windows surface; a changed answer is a differential),
  and `dictionary` (rebuilds `grammar.json` from the drafts).
- **Records**: `runs.jsonl` gets one line per seed or grow (the
  head, the interpreter and platform, the seed, the rounds, what
  was tried and by which mutator, what was kept, what crashed, how
  long); `<target>.arcs.json` is the arc map the corpus reaches;
  `<target>.crashes.jsonl` holds inputs that broke a contract,
  shrunk, until a fix lands; `<target>.retired.json` names every
  crash record `promote` took off that file (promoted into the
  corpus or dropped as reaching nothing new), with the date, so a
  rig's stale copy is never banked back (a bank unions by id, and
  a retired record returned would be a probe that passes, which is
  a red build): `grow` drops such a copy from the rig's own file
  first, and `rig_bank` skips one unless it was found on a tree
  after the retirement (its `head` against the retirement's, by git
  ancestry; the `found` date where git cannot compare), the crash
  found again after the fix; a bank
  also replays the crash records it merges at main's head and
  promotes or retires the ones that pass there, so a grow on a stale
  tree never reddens main with a probe that passes.
  Everything is committed with the ledger
  line, a grow that kept nothing included: the data from the
  fuzzing is in the repository, not only its results.
- **Replay on every leg**: `runner/tests/test_de_dust_corpus.py`
  runs every entry against its contract on Linux, Windows and macOS,
  and carries every crash on file as an `expectedFailure` probe
  until the fix lands and `promote` moves it.

## 3. The surface

Every reader of outside bytes is a target or is listed here with
the reason it is not. The order is the order of exposure: what a
peer on the wire reaches first.

| # | target | readers | status |
|---|--------|---------|--------|
| 1 | `wire` | `runner/wire/verify.py`: `verify_body`, `verify_body_keyed` | in the corpus |
| 2 | `cloud` | `runner/cloud/send_job.py`: `verify_body` | in the corpus |
| 3 | `v2` | `runner/wire/protocol_v2.py`: `validate` | in the corpus |
| 4 | `crypto` | `runner/wire/jobcrypto.py`: `decrypt_body` | in the corpus |
| 5 | `local` | `runner/runner.py`: `_ingest_local_envelope_inner`; `runner/wire/transports.py`: `parse_envelope` | in the corpus |
| 6 | `stash` | `runner/runner.py`: `_record_payload` | in the corpus |
| 7 | `mail` | `runner/runner.py`: `get_text_body`, `_bounce_of`, the subject's job id; the email extension's `_subject_body`, `reply_target`; `runner/wire/mailbox.py`: `_valid_reply_to` | in the corpus |
| 8 | `dtls` | `runner/wire/dtlsproto.py`: `_split_records`, `_parse_handshake`, `_parse_extensions`, the hello and key-share readers, `DtlsServerCore.feed` | in the corpus (Q66) |
| 9 | `board` | `runner/wire/board.py`: `submit`, `offer`, `complete`, `approve`, `reoffer_expired` | in the corpus (Q67) |
| 9b | `board_ops` | `runner/wire/board.py` under the sequence contract: a board file and `submit`, `offer`, `complete`, `approve`, `reoffer_expired` in order over it | in the corpus |
| 10 | `channels` | `runner/wire/transports.py`: `fetch_channel_messages` over a throwaway directory; the entry is the pair | in the corpus (Q68) |
| 10b | `inbox` | `runner/wire/transports.py` under the sequence contract: a whole inbox of files, links and directories through `fetch_channel_messages` and `service_channel`, the core's side in nine shapes | in the corpus |
| 11 | `manifest` | `runner/ops/extensions.py`: `parse_manifest` | in the corpus (Q69) |
| 12 | `local_inbox` | `runner/runner.py` under the sequence contract: the local signal inbox scanned once by `_scan_local_inbox`, the store held to the ingests | in the corpus |
| 13 | `secret` | `runner/cloud/send_job.py` `require_signable_secret` and `runner/guard/security.py` `validate_shared_secret`: the sender's and the runner's strength rules on one candidate secret, held in step (a differential the code itself asks for) | in the corpus |
| 14 | `queries` | `runner/ops/policy.py` `apply_result_policy` and `runner/ops/queries.py` `answer_queries` (with `runner/ops/attest.py` and the pattern bound in `runner/guard/security.py`): a job's `result_policy` -- the view it asks for, its queries, its budget -- and the job's own output, under every ceiling the owner can set (Q84) | in the corpus |
| 15 | `names` | `runner/guard/filenames.py` `validate_file_name` and `runner/runner.py` `_safe_job_id`: one name a sender chose, before the six file-name rules (the same on every platform) and the job-id rule; an accepted file name is staged under a scratch work directory on the host (`_staged_dest`) | in the corpus |
| 16 | `query` | `runner/ops/queries.py` `handle_query_mail` through the mail rig: one query message (its subject id, the sealed object a sender chose, under a key) over the retained record of a job as the runner saved it or as a crash left it; the reply opened and held to the queries contract, the record held to spent and saved_at, a copy taken without a second reply; under the operator's flags a dry run spends nothing and sends nothing (Q87); the hourly window as the runner left it, held to section 11's accounting on every reply (Q88); the senses store as the runner left it, the senses op's filters held to the senses doc | in the corpus |
| 17 | `board_mail` | `runner/ops/startup.py` `handle_board_mail` through the mail rig: one board message (`task_submit`, `task_request`, `task_result`, `task_approve`; its subject id, the sealed object, the key) over a board file as the runner saved it or as a crash left it; the ack or offer opened and held to section 13's shapes, the reply routed by the signed body's `reply_to` or to the mailbox, the board file read back, a copy taken; under the operator's flags a dry run leaves the board still and sends nothing (Q87); the lease as the owner wrote it over a claim an hour old | in the corpus |
| 18 | `v2_mail` | `runner/ops/handlers.py` `handle_v2_mail` through the mail rig, the process set to answer: one version 2 message (determination, question or answer; its subject id, the sealed object, the key); the answer sent opened and validated against the question, the answer filed once, the copy dropped by the replay cache (on disk too) and a stale message refused unread (Q86); the answerer's model configured and down, or the deterministic Oracle; the two switches (a process that ignores, one that leaves a question unseen); the answer's text and id, the filed record and the late answers held to the draft by the checker's own rules | in the corpus |

Not targets, and why: the Oracle's reading of its model's replies
(`runner/ops/oracle_tools.py`), the config loader and the platform
card are an operator's or a model's output, not a peer's, and the
config loader already sits in the bounded never-raise campaign;
the sandbox command builder is fuzzed as argv construction and
never executed; sockets, races and namespaces are not in-memory
questions. A reader added to the product after this plan is a
target before its release ships: the desk adds it, in the release
that adds the reader.

## 4. The contracts

A contract is what a reader's own docstring promises, never its
implementation. Each target states its refusal type, so a grow
never files a refusal as a crash.

- **Refusal, not exception.** The verifiers (`wire`, `cloud`, `v2`)
  refuse with `ValueError` and nothing else; `crypto` with
  `JobCryptoError`; the surfaces that read for a caller (`local`,
  `stash`, `mail`) contain every raise and answer `None` or a
  string. Any other exception is a crash. `dtls` is the same
  rule on the handshake: the splitter, the handshake parser and
  `DtlsServerCore.feed` never raise, and the extension, hello,
  key-share and PSK readers refuse with `DtlsError` or
  `JobCryptoError`. `board` never raises either: `submit` refuses
  a task that is not a usable submission and stores nothing, and
  the next known-good task on that board still completes.
  `channels` never raises either: a file that is not an envelope
  is an ack-only refusal and stores nothing, and the known-good
  neighbor in the same directory is still a job. `manifest`
  refuses with `ValueError` and nothing else, and a manifest it
  accepts is read back with the defaults filled and the caller's
  objects left alone.
- **Round-trip.** What a signer signs, both verifiers read back;
  what `encrypt_body` seals, `decrypt_body` opens; the wrong secret
  is refused; an unknown key is refused before any MAC.
- **Differential.** Two readers of the same bytes agree: the
  agent's verifier and the front-end's, both ways, with the one
  difference by design (Q61's control-character arm) allowed only
  when a control character in the signed object explains it; the
  keyed reader and the plain one; the core's mail extraction and
  the email extension's.
- **Cross-platform.** The same entry accepts or refuses under the
  simulated Windows surface as it does on the host (Q71). The
  surface is the host identity and the APIs Windows lacks; it
  does not swap in `ntpath`, so this is not a path-separator
  proof. A changed answer is a differential.
- **Provenance** (`mail`, `wire`, `cloud`, `inbox` now). A reply
  target is the mailbox or a single plain address from inside the
  signed body, never anything a header said: the email extension's
  `reply_target` on the raw message, the core's `_valid_reply_to`
  and `send_mail` on every body the verifiers trust (the subject
  on one line by the header's own rule, the result never dropped
  over it), and the channel's `.target.txt` sidecar carrying
  exactly what the core passed.
- **Sequence.** The entry is the file as it was left plus the
  operations in order, and the contract holds after every step.
  `board_ops` is that for the board: every operation answers its
  shape, a task handed out is claimed under the id it carries and
  is a copy, and the file reads back as the board in memory.
  `channels` is the pair of inbox files, and the check plants a
  neighbor the entry cannot erase: a bad file stores nothing and
  the neighbor in the same directory is still a job. `inbox` is
  the whole inbox as it was left, through the fetch and then the
  service pass: every file and link is one message in name order,
  a poison file is the empty refusal and is consumed, and what
  stays, what is done, what lands in the outbox and what is
  re-queued follow from how the core answered. `local_inbox` is
  the local signal inbox scanned once: every `.json` entry is
  handled once and removed either way, a directory or a name
  that is not `.json` is left alone, and the store holds exactly
  what the ingests filed, the neighbor's alert among them.
  `local` is the same rule on the envelope reader (Q70): a
  refusal leaves the senses store untouched, and a known-good
  neighbor alert filed next into that directory is stored.
- **Reserved slots.** `sig` is the protocol's; a payload carrying
  its own is read back with the slot overwritten by the keyed
  reader and kept by the plain one, and neither is a disagreement.
- **Ceiling and view** (`queries`). The policy is read under every
  ceiling the owner can set -- the four views, the ceiling absent,
  the ceiling not a view -- and neither reader raises; the view
  handed back is the one asked for, capped at the ceiling, an
  unknown or absent request reading as full; the retain flag
  follows the view; under summary and attested nothing of the
  output comes back (the sender's own text echoed from the policy
  is not the output, and neither is an output entry's commitment,
  the name, size and digest that leave under every view by PROTOCOL
  section 6, Q106 and Q111, nor a word of the result's own
  vocabulary, what a result says when the job wrote nothing, Q112),
  and attested blanks the streams; under
  redacted no line handed back matches the owner's pattern; the
  answers are one per query in order, each query spending one,
  the budget's refusals after the budget, grep and tail refused as
  policy under the views that hand no lines back, their lines the
  output's own under full, ask and senses named unavailable; the
  result with its answers signs and verifies as a body. The output
  an entry carries is short (1,024 characters): the plain repeats
  a grep pattern may keep are bounded only by the text (Q84).
- **One rule set on every platform** (`names`). `validate_file_name`
  refuses with `BadFileName` naming one of its six rules and
  nothing else, or answers the normalized path, which a second pass
  accepts unchanged, which has no empty, dot, backslash or Windows
  device component, and which is not absolute under either path
  flavour (`posixpath` and `ntpath` are both asked, since the rules
  promise the same answer whatever runner holds the key); an
  accepted name stages under a scratch work directory on the host
  with its real path under the root and its relative path the name
  itself, or the staging check refuses it (a directory the host
  will not create is a refusal, not a crash). `_safe_job_id`
  refuses with `JobRejected` and nothing else, or answers the same
  string, one safe component under either flavour.
- **The query message** (`query`). The handler takes the message
  and never raises; the message is marked seen exactly once; at
  most one reply goes out, to the mailbox under the subject's id, a
  qresult naming that id that verifies and opens under the key,
  with a list of answers and either a known rejection or a budget
  that is not negative; a reply with answers follows the queries
  contract against the retained record (the lines handed back the
  record's own under the record's view, nothing of the output under
  summary or attested, the record's own patterns redacting); the
  record after an answered query is the same record with spent
  advanced by the queries and saved_at kept, and a rejected query
  leaves it as it was; a copy of the message is taken without a
  second reply.
- **The board message** (`board_mail`). The handler takes the
  message and never raises; the message is marked seen exactly
  once; at most one reply goes out, to a single plain address from
  inside the signed body or to the mailbox (provenance), sealed
  under its own subject's last word and opening under the key; the
  reply is section 13's ack (the subject's task id, ok and reason,
  or a known status and reason) or offer (a task whose id is the
  reply subject's, claimed on the board, or empty under the empty
  subject); the board file reads back as a dict of dict tasks
  after the message and as the board in memory; a copy of the
  message is taken without raising.
- **The version 2 message** (`v2_mail`). The handler takes the
  message and never raises; a message acted on or refused is
  marked seen exactly once, and its copy is marked once and acted
  on no further (the replay cache under `v2:<msg_id>`, a stale or
  future `issued_at` refused unread: Q86); at most one reply goes
  out, only to a question, to the mailbox, sealed under the
  answer's own msg_id and opening under the key as a valid answer
  naming the question's msg_id and job, carrying the question's
  local default; an answer message is filed once under its
  question id and a second answer to the same question does not
  replace it; a determination sends nothing and files nothing.

A contract added later replays over every entry already kept; an
old entry that fails a new contract is a crash file and a Q, never
a hand edit.

The sequence entries carry the recovery shapes too, not only
isolation: two different poisons before the good one (the first
refusal must leave nothing the second trips on), and a run of
refusals before the happy path on the same board. A crash entry
followed by a good one is the pair `promote` makes when a crash
is fixed: the fixed entry stays in the corpus and the good
neighbour beside it is the checker's own.

## 5. Seeds and vocabulary

Seeds are suite-style fixtures with invented names (`example.com`,
`bm-*` ids, `/srv/example`, keys that are hex digits typed by hand),
in the shapes the readers meet: every delivery wrapping the mail
path survives (preamble, trailer, quoted, CRLF, a control
character, an upper-cased signature, two objects, a brace inside
a string, a pretty-printed signed body), the key slots of an
envelope agreeing and disagreeing every way, the brace walk's
hardest shape (keys and values made of `{`, `}` and `"`), the
protocol messages at their caps, MIME in its shapes (plain,
multipart, nested, an attachment, a truncated base64 part,
encoded-word subjects, duplicate headers, bounces, bytes that are
not UTF-8), a sealed DTLS flight and its two-fragment pair, and
since Q94 the default key under its own name: the tool's
secrets map registers the fingerprint as `build_secrets` does, so
a body, an envelope, a stashed record, a query, a board message and
a version 2 message each have a seed naming the default key by
fingerprint (accepted) and one naming another key's fingerprint,
which no map registers (refused); the query target counts the
hourly window under the one name the runner counts the key under,
whichever name the message carries.

The vocabulary grows only where a target's readers would not meet
the existing one. The dictionary built from the IETF drafts' own
grammar (`docs/ietf/`) is in it now, two ways: the fixed lists
carry the drafts' member names, enumerations, subject markers and
boundaries by hand (Q72), and `runner/tests/de_dust/grammar.json`,
built by the tool's `dictionary` command, carries every literal,
every member name, every enumerated value and every boundary the
drafts state, as insertion tokens and as JSON values, drawn on by
every target's grow. The drafts' own examples are seeds beside it.
The dictionary also learns: the same command harvests the keys and
short values of every grown entry that reached a new arc into a
`learned` section with its provenance, so the vocabulary follows
the search as well as preceding it (Muse, 2026-10-26).

## 6. Roles

- **The campaign (Muse)** runs the grow at every moment, one
  process per core, with the seed moved on each cycle, and commits
  every run's records with its ledger line; adds seed fixtures the
  suite builds that the tool does not yet (into the tool's seed
  functions, invented names only); files every crash the tool
  writes as a Q to the desk with the entry id and the detail line;
  keeps the ledger line `de_dust <n>: <k> entries, <a> arcs,
  <m> crashes filed, <resources line>`.
- **The desk (Claude)** owns the tool, the targets, the contracts
  and the fixes: every crash is fixed in the reader, never in the
  test, and the fix lands with `promote`; every new reader in the
  product gets its target in the same release.
- **Grok** built the DTLS target (Q66), the board target (Q67),
  the channel target (Q68) and the manifest target (Q69), put
  the sequence contract on `local` (Q70), and the cross-platform
  replay (Q71), and the grammar dictionary (Q72), and reviews
  the plan when the conductor asks; its reads go under a Q and
  are applied by the desk or recorded with the reason. Grok does
  not grow, and fixes a crash only when the conductor names it
  (the conductor, 2026-10-26).
- **The conductor** decides what is not in this file: a new
  surface outside the readers, a second rig, the release of a
  finding's details.
- **The split, in one line (the conductor, 2026-10-26):** Muse
  grows and files crashes as questions; the desk fixes the reader
  and turns survivors into seeds; one writer on a file (the
  campaign writes the corpus files, the arc maps, `runs.jsonl`
  and `survivors.json`; the desk writes the tool, the seed
  functions and the readers); Muse's daily note is the top of
  `docs/use/.com.chat`.

## 7. Cadence and records

The grow is continuous and pegs the CPU (the conductor's order;
the resource line reads on target or over, and anything lower is a
serial step named in the ledger). The release train runs beside
it; the corpus and its records ride every release, and the replay
test is a release gate like any other. Every grow, kept or not,
is a line in `runs.jsonl`; every pass of the regression tool, when
the conductor lifts its suspension, is a line in
`docs/reports/regression/passes.jsonl`; the campaign's ledger is
the end of the standing orders; the campaign's questions are in
`questions.md`. Where each target Grok built landed is
`docs/project/de_dust-where.md`. A release's evidence
manifest beside its SBOM is
the conductor's call (offered 2026-10-26).

## 8. Saturation and what comes after it

A target whose full-depth grow keeps nothing and reaches no new
arc is saturated; `stats` says so from the run records. Saturation
is per mutator before it is per target (Muse, 2026-10-26): a
target reads unsaturated while one of its mutators is still
finding arcs, `stats` names the live and the saturated ones, and
the grow steers its rounds toward the live ones with a floor share
for the rest, so the pegged hour spends itself where the arcs
still are. Saturation
is a fact about the vocabulary and the seeds against that reader,
not a verdict on the reader, and the response is in this order:

1. A stronger contract on the same corpus (differential,
   round-trip, sequence, provenance): every entry replays under it.
2. New seeds in a shape the reader has not met.
3. New vocabulary the reader would meet (structural, grammar-built).
4. The next reader on the surface.
5. Only when every target is saturated under every contract and
   the grammar vocabulary: the mutation survivors (D4) as the
   instrument, on the readers, with the corpus as the test that
   must kill them. That instrument is
   `runner/tools/de_dust_survivors.py` (landed 2026-10-26): it
   mutates each reader on the lines the corpus reaches and replays
   the corpus against every mutant, outcomes and notes alike; the
   survivors in `runner/tests/de_dust/survivors.json` are the
   lines the corpus cannot yet tell from a wrong reader, and each
   one names the seed to write next. The first run: 1,877 mutants,
   171 survivors; the DTLS reader lost none of 513. Five seed
   batches later (2026-10-26): 101 of 1,950, the manifest reader
   losing all 241 and the DTLS reader all 516, and what remains is
   the kind no input tells apart (the corpus README names the
   kinds). Three readers were fixed on the way: the board's
   re-offer, load and approve, the mailbox's subject, and the
   board's non-finite priorities (Grok, Q78 and Q79), each found
   by a seed the survivors named, a grow that moved it, and a
   contract that caught the reader. The sixth batch (the desk,
   2026-10-26, at the conductor's word that survivors become
   seeds): thirty-six more lines read -- a signed text that is
   not JSON, a pretty body with lone-CR line ends, a sig whose
   last digit is not hex, the v2 message and question ids, three
   more shapes of the core's side of a channel (a bare reply, two
   replies, a rewrite under the core's hands) and the channel's
   rollback counted, the board's log read through its own seam
   and its ranking defaults, lease default and stale warning --
   65 of 1,970 on the desk's run over the merged seeds, one of
   them a hang the replay detects. The grow merges the seeds the
   corpus lacks before it starts, so the desk's seeds reach the
   campaign's next run with no step between; the campaign's
   survivors run after it carries the count. The instrument then
   learned to put a mutant where every reader holds the module --
   the tool's alias, a module's own import of it, the agent
   module's re-exports -- so the four targets that read through
   the agent module joined the kill set and a module read only
   through another's import (the pattern bound under `queries`)
   is told apart; with the `queries` and `names` targets that is
   2,357 mutants, 81 of them standing, every one named by kind in
   the corpus README. The seventh reading (the desk, 2026-10-27)
   went survivor by survivor through the report the campaign
   banked and sorted them: the ones a seed kills -- the query
   window's refusals, the record's stderr and attestation marks,
   the reply's version and job members, the board's lease default,
   the answerer's model branches, the result subject's fold, the
   literals and numbers JSON does not have and the nesting bound
   (Q88, Q89) -- have their seeds in the seed functions, and the
   rest are equivalent mutants, the kind no input can tell apart:
   in `jobcrypto`, the GHASH mask widened above bit 127 or
   narrowed at bit 0 (the shift leaves bit 0 clear and nothing
   reads above the field), the reflection and multiply loops run
   one bit past the field, the HKDF counter and length guard a
   32-octet key never reaches, the counter block read from one
   octet more or less (equal below 2^24 blocks), a slice one wider
   than the keystream it is zipped with, the length block written
   in seven octets (the same integer); in `security` and
   `send_job`, the entropy estimate's two refusals of one secret
   (an empty string or a one-letter alphabet is zero either way)
   and the period test's extra repeat; in `verify` and `send_job`,
   the signer's object check after `json.dumps` of a dict, and the
   depth-zero return of a walk that returns false either way; in
   `board`, a task key the loader rewrites whether or not it
   matches, and the file's indent; in `protocol_v2`, the return of
   a check whose callers keep their own value; in `handlers`, the
   replay-cache flag `save_seen` sets true on every key; in
   `transports`, the ack's true the service loop reassigns, a
   return no caller reads, the root path no reader of the paths
   dict asks for, and the done folder's name a directory check
   skips either way; in `startup`, the board kind the subject gate
   never admits; in `filenames`, the leaf split of the device-name
   check, which every caller on the surface hands a single
   component (the full-path form is the unit test's), and the
   split's limit past the first dot. A reading starts from this
   list; a survivor not on it is a seed to write.

The grow never idles: a saturated target still runs its share
while the desk brings the next step, since a grow that keeps
nothing is still the record that those rounds were run. What it
tried is kept too: with the archive on the rig's disk, every
child of every grow is on file outside the tree, and the run
record says where.

## 9. Phases

- **Phase 1 (done 2026-10-26):** the six verifier targets, the
  mail path, the differential both ways, the records in the tree,
  the continuous grow, the proof-of-work rules.
- **Phase 2 (readers in the corpus, 2026-10-26):** DTLS (Q66),
  the board (Q67, and `board_ops` under the sequence contract),
  the channel readers (Q68, and `inbox` under the sequence
  contract), the manifest reader (Q69).
- **Phase 3 (done 2026-10-26):** the sequence contract on
  `local` (`local_inbox` on the scanner, and Q70 on the envelope
  reader); provenance on `mail`, `wire`, `cloud` and `inbox`; the
  corpus replays the same under the simulated Windows surface
  (Q71): every committed entry agrees, and a reader that reads
  differently there is a differential of its own.
- **Phase 4 (done 2026-10-26):** the grammar dictionary from
  `docs/ietf/` is in the mutators two ways (the fixed lists,
  Q72; `grammar.json` with `t_grammar` and `p_grammar`), and the
  drafts' own examples are seeds on `wire`, `cloud` and `v2`.
  A grow of 20,000 rounds on every target (Q73) kept nothing
  and gained no arc on `wire`, `cloud`, `v2`, and `mail`. The
  same run kept one entry each on `dtls`, `board_ops`,
  `manifest`, and `local`, from those targets' own mutators.
  No crashes. The continuous grow carries the dictionary from
  here.
- **Phase 5 (in flight, 2026-10-26):** the posted capture's
  shape, not its bytes, is a seed (Q74): a subject line and a
  sealed envelope, rebuilt under the corpus secret with invented
  ids. Both verifiers accept it. `local` refuses the job, which
  is a sensor inbox. The capture's own ciphertexts stay where
  they were posted. The mutation survivors are not started.
- **Then:** every reader the product adds, in the release that adds
  it; the plan revised at each phase's close with what the corpus
  taught.

## 10. What perfection looks like

Every reader of outside bytes has a target. Every target has a
refusal type, a round-trip where one exists, and a differential
where two readers read the same bytes. Every grow is a line in the
tree with the head, the seed and what it found. Every crash is a
Q within the hour, a fix in the reader within the day, and a
promoted entry that replays on every leg forever. No skip, no
`continue-on-error`, no hand edit, nothing real. The resource line
reads on target. The ledger reads the campaign's whole history
without the conversation that produced it.

## 11. Hard rules

As Q62: no new CI leg, no `continue-on-error`, every skip
registered, nothing about any machine in the tree, the contract
asserted and never the implementation, existing entries never
edited or removed by hand, every commit stamped. As Q65: no live
socket until the new readers stop crashing on bytes, no model, no
job-fuzz folded in, a Platinum percentage is coverage and never a
reason to stop.
