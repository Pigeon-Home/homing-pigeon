# Project blueMonday: the corpus

<!-- Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

One JSON-lines file per target, grown by
`runner/tools/bluemonday_corpus.py` and replayed by
`runner/tests/test_bluemonday_corpus.py` on every leg (Q62 in
`docs/use/questions.md`; section M of the standing orders).
`platform` reads every entry again under the simulated Windows
surface; a changed answer is a differential (Q71). The surface
does not swap in `ntpath`.

| file           | reader held to its contract                                   |
|----------------|---------------------------------------------------------------|
| `wire.jsonl`   | `runner/wire/verify.py`: `verify_body`, `verify_body_keyed`; on every trusted body, `runner/wire/mailbox.py`: `_valid_reply_to` and `send_mail` (provenance) |
| `cloud.jsonl`  | `runner/cloud/send_job.py`: `verify_body`; the same provenance check on every trusted body |
| `v2.jsonl`     | `runner/wire/protocol_v2.py`: `validate`                       |
| `crypto.jsonl` | `runner/wire/jobcrypto.py`: `decrypt_body`                     |
| `local.jsonl`  | `runner/runner.py`: `_ingest_local_envelope_inner`, with `runner/wire/transports.py`: `parse_envelope`. A refusal leaves the senses store untouched, and a known-good neighbor alert filed next into the same directory is stored (Q70) |
| `stash.jsonl`  | `runner/runner.py`: `_record_payload` (a stashed record's body and its three key slots, Q63) |
| `mail.jsonl`   | the mail path that chooses the text (Q65): `get_text_body`, `_bounce_of` and the subject's job id in the core; the email extension's `_subject_body` and `reply_target` with `mailbox._valid_reply_to`; the extension must read the same subject and body as the core |
| `dtls.jsonl`   | `runner/wire/dtlsproto.py` (Q66): `_split_records`, `_parse_handshake`, and, when a complete handshake message parses, `_parse_extensions`, the hello parsers, the key-share and PSK readers; `DtlsServerCore.feed` on the same datagram |
| `board.jsonl`  | `runner/wire/board.py` (Q67): `submit`, `offer`, `complete`, `approve`, `reoffer_expired` on one task dict; a refusal stores nothing, and a known-good neighbor submitted after it still runs |
| `board_ops.jsonl` | `runner/wire/board.py`, the sequence kind: a board file as a peer or a crash left it, then `submit`, `offer`, `complete`, `approve`, `reoffer_expired` in order on a throwaway path, the contract held after every step |
| `channels.jsonl` | `runner/wire/transports.py` (Q68): `fetch_channel_messages` over a throwaway directory. The entry is a pair of inbox files. A file that is not an envelope is an ack-only refusal and stores nothing; the known-good neighbor in the same directory is still a job |
| `manifest.jsonl` | `runner/ops/extensions.py` (Q69): `parse_manifest` on one extension.json object. `ValueError` is the refusal. A manifest it accepts is read back with the defaults filled, and the caller's objects are left alone |
| `inbox.jsonl`  | `runner/wire/transports.py`, the sequence kind: a whole inbox as a peer or a crash left it (files, links, directories, in their names) read by `fetch_channel_messages` and serviced by `service_channel` with the core's side in one of five shapes, a known-good envelope beside them |
| `local_inbox.jsonl` | `runner/runner.py`, the sequence kind: the local signal inbox as a peer or a crash left it, scanned once by `_scan_local_inbox`; each `.json` entry handled once and removed either way, the store holding exactly what the ingests filed, a known-good alert beside them |

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

A `board_ops` entry's data is `{"file", "ops"}`: the board file's
text (or `null` for no file) and the operations in order, each
`["submit", task]`, `["offer", worker_id, capabilities, key_id,
cfg]`, `["complete", task_id, result, require_review]`,
`["approve", task_id]` or `["reoffer", task_timeout]`. Accepted
means some operation took effect. Its mutators edit the file text
(the text set over the JSON), one operation's argument (the
payload set), or the sequence itself (an operation dropped,
repeated, swapped with its neighbour, or borrowed from another
entry). After every step each operation has answered its shape --
`(bool, str)`, a task copy or `None`, `(status, str)`, a count --
a task handed out is claimed under the id it carries and is a
copy, and the file reads back as the board in memory.

A `channels` entry's data is a pair, `{"poison", "other"}`, both
inbox texts (or a list of byte values for a non-UTF-8 poison),
so the JSON mutators apply. The check also plants a neighbor the
entry cannot change, a subdirectory, a symlink, a non-UTF-8
file, and one oversize envelope with the size cap lowered for
that probe only and put back. Accepted means the poison parsed
and came back as that subject and body. Refused means it was
ack-only and its reply stored nothing.

A `manifest` entry's data is one extension.json object, so the
JSON mutators apply. Accepted means `parse_manifest` returned
the cleaned manifest and the input's name, version, kind,
signals, tunables, entry, publisher, upstream and capabilities
read back, with defaults filled where the field was absent.
Refused means `ValueError` and a reason. A newer `api_version`
than this agent provides is accepted here; `api_refusal` is a
later check and is not this target.

An `inbox` entry's data is `{"files", "mode"}`: the whole inbox,
each entry `{"name", "text"}` (bytes that are not UTF-8 as
surrogates), `{"name", "link"}`, `{"name", "dir": true}` or
`{"name", "fill": n}` (n bytes of filler, which is how the size
cap is reached without storing it), and the shape of the core's
side in the service pass: `reply` (a result per parsed envelope,
the default), `raise`, `none`, `hold` (consume off) or `badreply`
(a reply whose write raises). The checker adds a known-good
envelope sorted last. Accepted means an envelope of the entry's
own parsed. Its mutators edit one file's text (the text set), a
name, the mode, or the inbox itself (a file dropped, repeated
under another name, borrowed from another entry, or turned into a
link, a directory or a filler). After the fetch every file and
link is one message in name order, a well-formed envelope as
`parse_envelope` reads it and anything else as the empty ack-only
refusal; after the service pass what stayed, what moved to done,
what landed in the outbox and what was re-queued follow from the
mode, the neighbor served either way, and a result file reads
back as the reply.

A `local_inbox` entry's data is `{"files"}` in the same shapes as
`inbox` (a text of `@alert` is a live alert signed at check time,
since a stored alert needs a fresh `issued_at`). The checker adds
a known-good alert sorted last and scans once. Accepted means an
alert of the entry's own was filed. After the scan every `.json`
entry was handled once and is gone -- a symlink or a file that is
not UTF-8 without an ingest call, a file that decodes with one
call carrying its text up to the size cap plus one byte --
anything not named `.json`, a directory among them, is left
alone, no ingest raised, and the store holds exactly the records
the ingests answered, in inbox order, the neighbor's among them.

Provenance, on every body `wire` or `cloud` trusts: where the
result would go is `_valid_reply_to` on the signed dict alone --
`None`, or a single plain address the dict carries under
`reply_to`, stripped, at most 254 characters, matching the one
pattern -- and `send_mail` (with a fake SMTP that keeps the
message) addresses it there or to the runner's own mailbox, with
the subject on one line by the header's own rule, never dropping
a result over its subject text. In `inbox` the reply carries the
target the core would pass, and the `.target.txt` sidecar beside
the result must carry exactly that.

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
nothing. The manifest reader refuses with `ValueError` and
nothing else; the channel reader and the service pass never
raise. A raise of any other type, or a `ValueError` escaping
`local`, `stash`, `mail`, `dtls`, `board`, `board_ops`,
`channels`, `inbox` or `local_inbox`, is a crash.
