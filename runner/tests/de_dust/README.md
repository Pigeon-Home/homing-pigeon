# Project de_dust: the corpus

<!-- Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

One JSON-lines file per target, grown by
`runner/tools/de_dust_corpus.py` and replayed by
`runner/tests/test_de_dust_corpus.py` on every leg (Q62 in
`docs/use/questions.md`; section M of the standing orders).
`platform` reads every entry again under the simulated Windows
surface; a changed answer is a differential (Q71). The surface
does not swap in `ntpath`. The mutators also insert the IETF
drafts' own member names and boundaries, and the drafts'
examples are seeds (Q72). The posted capture's shape, a subject
and a sealed envelope rebuilt under the corpus secret, is a seed
too (Q74). The capture's own bytes are not.

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
| `inbox.jsonl`  | `runner/wire/transports.py`, the sequence kind: a whole inbox as a peer or a crash left it (files, links, directories, in their names) read by `fetch_channel_messages` and serviced by `service_channel` with the core's side in one of nine shapes, a known-good envelope beside them |
| `local_inbox.jsonl` | `runner/runner.py`, the sequence kind: the local signal inbox as a peer or a crash left it, scanned once by `_scan_local_inbox`; each `.json` entry handled once and removed either way, the store holding exactly what the ingests filed, a known-good alert beside them |
| `secret.jsonl` | `runner/cloud/send_job.py` and `runner/guard/security.py`: one candidate shared secret before the sender's `require_signable_secret` and the runner's `validate_shared_secret`, the two held in step (both refuse naming the same fault, or both accept; one entropy estimate) |
| `queries.jsonl` | `runner/ops/policy.py` and `runner/ops/queries.py` (with `runner/ops/attest.py` and the pattern bound): a job's `result_policy` and its own output, read by `apply_result_policy` and `answer_queries` under every ceiling the owner can set; the view capped at the ceiling, nothing of the output under summary or attested, no canary under redacted, one answer per query with the budget's and the policy's refusals where section 10 puts them, the result signed and verified (Q84, Q85) |
| `names.jsonl` | `runner/guard/filenames.py` and `runner/runner.py`: one name a sender chose before `validate_file_name` (the six file-name rules, the same on every platform, the normalized path stable under a second pass and not absolute under either path flavour, then staged under a scratch work directory) and `_safe_job_id` (the job-id rule) |
| `query.jsonl` | `runner/ops/queries.py`, the sequence kind through the mail rig: one query message (its subject id, the sealed object, the key) over the retained record of a job, through `handle_query_mail` twice; the reply opened and held to the queries contract against the record, the record held to spent and saved_at, the copy taken without a second reply; a dry run spends nothing and sends nothing (Q87); the hourly window as the runner left it, every reply held to section 11's accounting (Q88); the senses store as the runner left it, the senses op's filters held to the senses doc |
| `board_mail.jsonl` | `runner/ops/startup.py`, the sequence kind through the mail rig: one board message (its kind and subject id, the sealed object, the key) over a board file, through `handle_board_mail` twice; the ack or offer opened and held to section 13's shapes, routed by the body's `reply_to` or to the mailbox, the board file read back, the copy taken; a dry run leaves the board still and sends nothing (Q87); the lease as the owner wrote it |
| `v2_mail.jsonl` | `runner/ops/handlers.py`, the sequence kind through the mail rig, the process set to answer: one version 2 message (its kind and subject id, the sealed object, the key) through `handle_v2_mail` twice; the answer sent opened and validated against the question, the answer filed once and not replaced by a second, the copy dropped by the replay cache (on disk too), a stale message refused unread (Q86); the answerer's model configured and down, or the deterministic Oracle; the two switches; the answer's text and id, the filed record and the late answers (kept beside the first, the same text once, eight at most) held to the draft by the checker's own rules |

The first line of each file is a header; every other line is one
entry: `id` (a hash of the kind and the data), `kind` (`text`, a
received body; `payload`, a JSON value the checker signs or hands
over), `data`, `from` (the seed's name or the parent's id),
`mutator`, and `arcs` (the line arcs the entry reached first). A
`<target>.crashes.jsonl` beside them, when one exists, holds
inputs that broke a contract and are waiting for a fix; the test
carries each as an `expectedFailure` probe until `promote` moves
it here. `<target>.slow.jsonl`, when one exists, holds inputs a
grow ran over fifty times the corpus median and over half a second
(confirmed twice; de_dust2, Q116); a time is the box's, so the test
replays them for correctness only and never as a probe, and
`promote` retires one that runs under half the floor on a quiet box
as `fast` in `<target>.retired.json`, beside the crashes it retired
as `promoted` or `redundant`. A record on either file whose `head`
predates the fix that retired its family is an echo the bank keeps
out (Q108).

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

`grammar.json` is the dictionary the drafts in `docs/ietf/`
dictate, built by `python runner/tools/de_dust_corpus.py
dictionary`: every backticked token without a space, every number
the text states with its neighbours on both sides, every JSON
example with `sig` removed -- and, under `learned`, the tokens the
search itself found: the keys and short string values of every
grown entry that reached a new arc, each with the target and entry
it came from, capped. The `t_grammar` and `p_grammar` mutators draw
on both, and the examples seed `wire`, `cloud` and `v2`. It is
rebuilt by the desk when the drafts change or the corpus has grown;
the test holds it to its shape, not to the drafts' current text.

`survivors.json` is the last run of
`runner/tools/de_dust_survivors.py`, the instrument for after
saturation (the plan's section 8, step 5): every reader the corpus
holds directly is mutated one small change at a time, on the lines
the arc maps say the corpus reaches, and the corpus of every target
that reads through that module is replayed against the mutant. A
mutant whose replay answers the same for every entry -- the same
accepted, refused or crash, and the same notes (the key a reader
chose, a digest of what it returned, each operation's answer, the
refusal's reason) -- has survived, and its line is what the next
seeds are for. Each run adds a line of kind `survivors` to
`runs.jsonl`. A mutant is put where every reader will meet it: the
tool's own alias, every module that imported the reader under its
own name, and the agent module's re-exports of its functions, each
put back after the replay; so the targets that read through the
agent module (`local`, `stash`, `mail`, `local_inbox`) are in the
kill set, and a module one target reads only through another's
import (the pattern bound under `queries`) is told apart too. The
report's `through_agent` is the set a run left out, empty now.

The survivors are turned into seeds by the desk, one line at a
time (the seed functions name them: `pretty_cr`, `sig_last_not_hex`,
`signed_not_json`, the `msg_id_*` and `question_id_*` shapes, the
`core_bare`, `core_two` and `core_touch` inbox shapes, the
`rank_*` and `lease_default_edge` board sequences), and the board
sequence now records what the board logs through its own seam, so
a line that only logs is a line the corpus reads. What remains
after that round and the two targets that followed (the desk's own
run over the seeded corpora, every target in the kill set: 81 of
2,357, one of them a hang the replay detects as a timeout) is,
reader by reader, the kind of mutant no input tells apart: in the
cipher, the masking slack of GHASH and the key schedule (a mask
one bit wider, a length field one byte shorter whose integer is
the same, a range end past the words used, a counter byte the
short messages never reach) and the HKDF counter that one block
never reaches; in the verifiers, the opener search's loop bounds
(two more starts that are never a brace), the tail cap one short
where the next check refuses anyway, a shape check on a body the
signer built, the serializer's flags over bodies the safe form
already cleaned, a `False` returned as `None`, and the secret
rules' arithmetic (`log2(1)` is zero either way, one more repeat
of a unit that already covers the string); in the board and the
channel readers, a return nothing reads, the key names of a paths
table the readers here never index, the directory name the inbox
cannot hold as a file, a flag the next line overwrites, and the
file's indentation; in the result policy and its queries, a budget
the caller already clamped, a digest the caller already computed
from the same text, the one attestation read from either end of
its list, and a senses answer the absent base directory decides
alone; in the file-name rules, the leaf of a component that has no
separator. A line in that file is still a claim to
check when a reader changes: a survivor that was equivalent can
stop being so, and the run after the change says which. The
committed report is the campaign's last run; the campaign's next
run over the merged seeds carries the new count.

A grow is steered: it reads the last grows' records for the target
and chooses mutators by their keep rate, a saturated one keeping a
floor share of the best one's (saturation is per mutator, and
`stats` names each target's live and saturated mutators). With
`--archive <dir>` (or `HP_DE_DUST_ARCHIVE`) every child a grow
tries, kept or not, is written to one gzip JSON-lines file per grow
in that directory, outside the tree; the run record's `archive`
member carries the file's name, size, SHA-384 and count.

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
`channels`, `inbox` or `local_inbox`, is a crash. The secret rules
refuse with `ValueError` (the sender's) and `RuntimeError` (the
runner's), and a disagreement between the two is a crash.
