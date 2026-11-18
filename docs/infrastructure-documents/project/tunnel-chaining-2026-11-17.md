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

Owed. The build and its measures land after this supposition
stands on the branch, and the conclusions against each
numbered point are recorded here in the same place.
