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
| `mail.jsonl`   | the mail path that chooses the text (Q65): `get_text_body`, `_bounce_of` and the subject's job id in the core; the email extension's `_subject_body` and `reply_target` with `mailbox._valid_reply_to`; the extension must read the same subject and body as the core |
| `dtls.jsonl`   | `runner/wire/dtlsproto.py` (Q66): `_split_records`, `_parse_handshake`, and, when a complete handshake message parses, `_parse_extensions`, the hello parsers, the key-share and PSK readers; `DtlsServerCore.feed` on the same datagram |
| `board.jsonl`  | `runner/wire/board.py` (Q67): `submit`, `offer`, `complete`, `approve`, `reoffer_expired` on one task dict; a refusal stores nothing, and a known-good neighbor submitted after it still runs |

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

A `mail` entry's data is the raw RFC 822 message as text; bytes
that are not UTF-8 ride as surrogate escapes (`\udcXX` in the
file), so the readers get the exact bytes back. Its mutators are
structural (a header dropped, duplicated, folded or inserted, a
boundary broken, a part truncated, the blank line moved) rather
than the JSON set.

A `dtls` entry's data is one datagram as text, with the same
surrogate escapes as mail, so a record byte that is not UTF-8 is
the byte the readers see. Its mutators are the record's own (a
length field flipped, a mid-record truncate, two overlapping
fragments, a wrapped sequence number, a unified-header bit
flipped, a record duplicated or dropped, two datagrams spliced,
one random byte), not the text set. Accepted means a complete
handshake message parsed; a fragment, an empty datagram and a
record whose length overruns the datagram are refusals.

A `board` entry's data is one task dict, a JSON value, so the
JSON mutators apply. Accepted means `submit` stored it: it is
offered to a worker holding its capabilities, a zero-lease
reopens the claim, `complete` finishes it (a `bm_review` payload
goes through `pending_review` and `approve`), and a second
complete is a duplicate. Refused means nothing was stored. Either
way a known-good neighbor task submitted next still completes.
The board file is a private temp directory and does not outlive
the check.

The refusal types, so a grow never files one as a crash (Q63):
for the verifiers (`wire`, `cloud`, `v2`) the refusal is
`ValueError`, raised, not returned -- an unknown `key_id` from
`verify_body_keyed` included; for `crypto` it is `JobCryptoError`;
the surfaces that read for a caller (`local`, `stash`) contain
those raises themselves and answer `None`; the mail readers never
raise at all; the DTLS splitter, handshake parser and `feed`
never raise, and the extension and hello readers refuse with
`DtlsError` or `JobCryptoError`. The board methods never raise:
a bad task is a `(False, reason)` from `submit` and stores
nothing. A raise of any other type, or a `ValueError` escaping
`local`, `stash`, `mail`, `dtls` or `board`, is a crash.
