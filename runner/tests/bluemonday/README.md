# Project blueMonday: the corpus

<!-- Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

One JSON-lines file per target, grown by
`runner/tools/bluemonday_corpus.py` and replayed by
`runner/tests/test_bluemonday_corpus.py` on every leg (Q62 in
`docs/use/questions.md`; section M of the standing orders).

| file           | reader held to its contract                                   |
|----------------|---------------------------------------------------------------|
| `wire.jsonl`   | `runner/wire/verify.py`: `verify_body`, `verify_body_keyed`    |
| `cloud.jsonl`  | `runner/cloud/send_job.py`: `verify_body`                      |
| `v2.jsonl`     | `runner/wire/protocol_v2.py`: `validate`                       |
| `crypto.jsonl` | `runner/wire/jobcrypto.py`: `decrypt_body`                     |
| `local.jsonl`  | `runner/runner.py`: `_ingest_local_envelope_inner`, with `runner/wire/transports.py`: `parse_envelope` |
| `stash.jsonl`  | `runner/runner.py`: `_record_payload` (a stashed record's body and its three key slots, Q63) |

The first line of each file is a header; every other line is one
entry: `id` (a hash of the kind and the data), `kind` (`text`, a
received body; `payload`, a JSON value the checker signs or hands
over), `data`, `from` (the seed's name or the parent's id),
`mutator`, and `arcs` (the line arcs the entry reached first). A
`<target>.crashes.jsonl` beside them, when one exists, holds
inputs that broke a contract and are waiting for a fix; the test
carries each as an `expectedFailure` probe until `promote` moves
it here.

The work is in the tree beside the corpus. `runs.jsonl` has one
line per `seed` or `grow`: the head it ran against, the rng seed,
the rounds, how many children were tried and by which mutator,
which entries were kept, what crashed, how long it took; a run is
replayable from its seed and the corpus before it.
`<target>.arcs.json` is the arc map the corpus reached after the
last run (file, from line, to line), data rather than an assertion
since line numbers move with every edit of the reader. Both are
committed with the corpus files they describe.

The files are ASCII with Unix line ends and are written by the
tool only; grow the corpus with the tool, never by hand. Every
name in them is invented (`example.com`, `bm-*` ids, `/srv/example`).

The refusal types, so a grow never files one as a crash (Q63):
for the verifiers (`wire`, `cloud`, `v2`) the refusal is
`ValueError`, raised, not returned -- an unknown `key_id` from
`verify_body_keyed` included; for `crypto` it is `JobCryptoError`;
the surfaces that read for a caller (`local`, `stash`) contain
those raises themselves and answer `None`. A raise of any other
type, or a `ValueError` escaping `local` or `stash`, is a crash.
