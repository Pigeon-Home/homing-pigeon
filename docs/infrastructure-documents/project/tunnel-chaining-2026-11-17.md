# Tunnel chaining: the working record, 2026-11-17

The ask: FUTURE.md item 2, tunnel chaining over air gaps. This
pass covers step A (define a chain hop), step B (build the
relay on file transport first), and the test core of step E
(prove a 2 hop chain in tests, with tampered and replayed
envelopes refused). Steps C, F and G stand for later passes.
The work rides the branch `future/tunnel-chaining` for the
conductor's review; nothing here is on main.

The definition stands in the design drawer:
`docs/steady/design/tunnel-chaining-design.md`. This record
holds the supposition, the method, and the conclusions.

## Supposition (recorded before the build)

1. The existing envelope machinery suffices. A chain hop needs
   no new cryptography: the `hp_enc` envelope, the signed body
   discipline, and the key map carry it, and the chain adds
   only a body type, a subject kind, and a relay handler.
2. The early dispatch pattern admits one more handler without
   changing the job path. Cancel, query, board, and version 2
   mail are each tried before the job path and return having
   handled their own kind; a chain handler of the same shape
   leaves every existing suite green.
3. A 2 hop chain traverses on file transport alone. The
   relay's forwarded file, carried by hand in the test from
   the relay's watched outbox to the final runner's watched
   inbox, is accepted by the final runner as an ordinary job
   and runs.
4. Tamper and replay both refuse with no forward and no
   execution, and each refusal leaves the standing records: a
   log line, and for the failures of authentication an
   `auth_rejection` entry in the security events.
5. The relay cannot read the carried job. With only the first
   hop's secret in the relay's key map, opening the carried
   envelope under that secret fails, and the relay's own
   processing never attempts it.

## Method

The sender side lives in `runner/wire/chain.py`: the chain
body's shape, its sealing, and its opening, all over the
standing wire machinery. The relay side is a mail handler,
`runner/ops/chain.py`, tried in early dispatch beside the
query and board handlers, following the query handler's
conventions for admission, the replay cache, refusal, and
marking. The door policy learns the door name `chain`, so a
key's `allowed_kinds` speaks of it the way it speaks of
`query` and `board`. The proof is
`runner/tests/test_chain_relay.py`: wire level round trips and
refusals, then the full 2 hop traversal over two file
transport fixtures, the tamper refusal, and the replay
refusal.

## Conclusions

The build landed on this branch in two commits after the
definition: the relay itself, then the core record's
re-measure the relay's growth required. Against the
supposition, point by point:

1. Held. The envelope machinery sufficed, and the chain
   added exactly the predicted pieces and no more: one body
   type (`runner/wire/chain.py`: the chain body's shape, its
   sealing, its opening), one subject kind
   (`[HOMING-PIGEON] chain <chain_id>`), one relay handler
   (`runner/ops/chain.py`), and one door name (`chain`, in
   the door policy beside `query` and `board`). No new
   cryptography anywhere: sealing and opening ride the
   standing `sign_payload`, `encrypt_body`, `decrypt_body`,
   and `verify_body_keyed`.
2. Held, with one honest rider. The handler is tried in
   early dispatch after the board handler and before the
   version 2 mail handler, in the same shape as the query
   handler, and the job path is untouched. The suites the
   pass ran stand green: the chain suite itself, 15 tests;
   a neighbour batch of 164 across the chain suite, the
   skip registry, the door policy edges, the query door,
   the local rig gaps, the reader docs, the board, and the
   mutation oracle; the core and release train suites (109)
   green after the rider below. The rider: growing
   `runner/runner.py` by 5 lines moved the recorded
   as-assembled core figures, and a new test module rotted
   the mutmut recorded selection; both are re-recorded in
   this same pass, by the standing tools
   (`record_core_measure`; the mutation oracle's
   regeneration), so the branch stands green whole rather
   than green except for the records.
3. Held. `test_two_hop_traversal` runs the whole chain on
   file transport alone: the chain envelope dropped in the
   relay's watched inbox, the relay's forwarded file
   carried by hand to the final runner's watched inbox,
   the final runner running the job as an ordinary job, and
   the result opening under the final hop's secret with the
   ping's `pong` and exit code 0. The relay ran nothing
   itself. One precision against the design's wording: the
   relay forwards the carried subject and body exactly as
   the chain body held them; the file the next runner reads
   back carries the one trailing newline the mail envelope
   framing itself adds, the tolerance every envelope in
   this suite travels with, and the test pins the body
   equal up to that newline.
4. Held. The tampered chain envelope (one flipped
   ciphertext character) is refused: nothing in the outbox,
   an `auth_rejection` in the relay's security events, and
   the file taken so it cannot wedge the channel. The
   replayed envelope, arriving again under a new file name
   as a replay on carried media does, is answered by the
   replay cache: logged, taken, and not forwarded again
   (the outbox still holds exactly the first forward). A
   chain under a key the relay does not hold refuses the
   same way, and a stale chain is refused on freshness.
5. Held. The final hop's envelope opens under neither
   secret the relay holds (its own default nor the first
   hop's): `decrypt_body` raises under both, pinned at the
   wire level. The relay's handler never attempts it: the
   carried envelope moves as the chain body's text, opened
   by no one until the next runner.

What stands for later passes, unchanged from the plan:
step C (version 3 DTLS hops for linked segments), step F
(the retro rig field test under the Pi Light profile), and
step G (PROTOCOL and the support matrix, and shipping on
the train). One more, found by this pass: the relay's two
modules (`runner/wire/chain.py`, `runner/ops/chain.py`)
are not on the core's canonical list yet; their admission
is a separate recording, noted in `runner/ops/core.py`'s
chronicle where this pass's re-measure stands.
