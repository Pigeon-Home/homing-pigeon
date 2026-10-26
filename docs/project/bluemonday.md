# Project blueMonday: the test plan

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

`runner/tools/bluemonday_corpus.py`, stdlib only.

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
  cycle), `replay` (every entry against its contract, no tracer,
  what the test does), `promote` (after a fix, crashes that now
  refuse properly and reach something new move into the corpus),
  `stats` (sizes and the saturation mark).
- **Records**: `runs.jsonl` gets one line per seed or grow (the
  head, the interpreter and platform, the seed, the rounds, what
  was tried and by which mutator, what was kept, what crashed, how
  long); `<target>.arcs.json` is the arc map the corpus reaches;
  `<target>.crashes.jsonl` holds inputs that broke a contract,
  shrunk, until a fix lands. Everything is committed with the ledger
  line, a grow that kept nothing included: the data from the
  fuzzing is in the repository, not only its results.
- **Replay on every leg**: `runner/tests/test_bluemonday_corpus.py`
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
| 10 | `channels` | `runner/wire/transports.py`: `fetch_channel_messages` over a throwaway directory, with the sequence kind | the desk |
| 11 | `manifest` | `runner/ops/extensions.py`: `parse_manifest` | the desk |

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
- **Round-trip.** What a signer signs, both verifiers read back;
  what `encrypt_body` seals, `decrypt_body` opens; the wrong secret
  is refused; an unknown key is refused before any MAC.
- **Differential.** Two readers of the same bytes agree: the
  agent's verifier and the front-end's, both ways, with the one
  difference by design (Q61's control-character arm) allowed only
  when a control character in the signed object explains it; the
  keyed reader and the plain one; the core's mail extraction and
  the email extension's.
- **Provenance.** A reply target is the mailbox or a single plain
  address from inside the signed body, never anything a header
  said.
- **Sequence** (`board_ops` now; `channels` and `local` to come):
  the entry is the file as it was left plus the operations in
  order, and the contract holds after every step -- for the
  board, every operation answers its shape, a task handed out is
  claimed under the id it carries and is a copy, and the file
  reads back as the board in memory; for the readers, a bad
  message stores nothing and the next good one in the same poll
  or directory still does.
- **Reserved slots.** `sig` is the protocol's; a payload carrying
  its own is read back with the slot overwritten by the keyed
  reader and kept by the plain one, and neither is a disagreement.

A contract added later replays over every entry already kept; an
old entry that fails a new contract is a crash file and a Q, never
a hand edit.

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
not UTF-8), a sealed DTLS flight and its two-fragment pair.

The vocabulary grows only where a target's readers would not meet
the existing one. The next vocabulary with leverage is a
dictionary built from the IETF draft's own grammar (`docs/ietf/`):
every literal, every member name, every enumerated value, every
boundary the draft states, as insertion tokens and as JSON values.
That is phase 4 below.

## 6. Roles

- **The campaign (Muse)** runs the grow at every moment, one
  process per core, with the seed moved on each cycle, and commits
  every run's records with its ledger line; adds seed fixtures the
  suite builds that the tool does not yet (into the tool's seed
  functions, invented names only); files every crash the tool
  writes as a Q to the desk with the entry id and the detail line;
  keeps the ledger line `blueMonday <n>: <k> entries, <a> arcs,
  <m> crashes filed, <resources line>`.
- **The desk (Claude)** owns the tool, the targets, the contracts
  and the fixes: every crash is fixed in the reader, never in the
  test, and the fix lands with `promote`; every new reader in the
  product gets its target in the same release.
- **Grok** built the DTLS target (Q66) and the board target
  (Q67) and reviews the plan when the conductor asks; its reads
  go under a Q and are applied by the desk or recorded with the
  reason.
- **The conductor** decides what is not in this file: a new
  surface outside the readers, a second rig, the release of a
  finding's details.

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
`questions.md`. A release's evidence manifest beside its SBOM is
the conductor's call (offered 2026-10-26).

## 8. Saturation and what comes after it

A target whose full-depth grow keeps nothing and reaches no new
arc is saturated; `stats` says so from the run records. Saturation
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
   must kill them.

The grow never idles: a saturated target still runs its share
while the desk brings the next step, since a grow that keeps
nothing is still the record that those rounds were run.

## 9. Phases

- **Phase 1 (done 2026-10-26):** the six verifier targets, the
  mail path, the differential both ways, the records in the tree,
  the continuous grow, the proof-of-work rules.
- **Phase 2 (in flight):** DTLS (Grok), the board (Grok's on one
  task, the desk's on the sequence), the channel readers with the
  sequence contract, the manifest reader.
- **Phase 3:** the sequence contract on `local`; the provenance
  contract on every reader that names a destination; cross-platform
  replay findings (a reader that reads differently on Windows is a
  differential of its own).
- **Phase 4:** the grammar dictionary from the IETF draft; seeds
  from the draft's own examples; a grow of every target under it.
- **Phase 5:** live captures, scrubbed to invented names, as seeds
  (the conductor decides what is captured); the mutation survivors
  on the readers.
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
