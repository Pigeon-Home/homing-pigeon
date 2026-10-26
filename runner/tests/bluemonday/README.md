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

The first line of each file is a header; every other line is one
entry: `id` (a hash of the kind and the data), `kind` (`text`, a
received body; `payload`, a JSON value the checker signs or hands
over), `data`, `from` (the seed's name or the parent's id),
`mutator`, and `arcs` (the line arcs the entry reached first). A
`<target>.crashes.jsonl` beside them, when one exists, holds
inputs that broke a contract and are waiting for a fix; the test
carries each as an `expectedFailure` probe until `promote` moves
it here.

The files are ASCII with Unix line ends and are written by the
tool only; grow the corpus with the tool, never by hand. Every
name in them is invented (`example.com`, `bm-*` ids, `/srv/example`).
