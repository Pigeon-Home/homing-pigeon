# Findings — docs/steady/project/de_dust.md

Source: docs/steady/project/de_dust.md, reviewed at main fc813e21.
Sentence units: 156. Flagged: 2. Categories: pre-release 156, post-release 0.

The de_dust campaign plan: what a reader is, the corpus tool's vocabulary (target, entry, guidance, mutation, commands, records, replay), the target table in exposure order, and the contract each target is held to. The definitions chain — each term is used by the ones after it — and the contract list at the end states, target family by target family, what counts as a refusal and what counts as a crash. The non-sentences are the stamp comment (unit 1) and the target table's header row (unit 25); the table's data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "The conductor's campaign, 2026-10-26, to run indefinitely: a…" | pre-release | flows |  |
| 3 | "This is the plan from here on; the…" | pre-release | flows |  |
| 4 | "Nothing here names a person, a machine, a…" | pre-release | flows |  |
| 5 | "A reader is a function that takes bytes…" | pre-release | flows |  |
| 6 | "Every finding the project's testing has produced from…" | pre-release | flows |  |
| 7 | "The campaign holds every such reader to its…" | pre-release | flows |  |
| 8 | "What it is not: a search for races,…" | pre-release | flows |  |
| 9 | "In memory, no socket, no secret that is…" | pre-release | flows |  |
| 10 | "`runner/tools/de_dust_corpus.py`, stdlib only." | pre-release | flows |  |
| 11 | "A **target** is a reader (or a small…" | pre-release | flows |  |
| 12 | "An **entry** is one JSON line: `id` (a…" | pre-release | flows |  |
| 13 | "Bytes that are not UTF-8 ride as surrogate…" | pre-release | flows |  |
| 14 | "**Guidance** is line arcs under `sys.settrace` over the…" | pre-release | flows |  |
| 15 | "A child is kept when it reaches an…" | pre-release | flows |  |
| 16 | "`sys.monitoring` was measured and is slower here; the…" | pre-release | flows |  |
| 17 | "**Mutation** is the job-fuzz vocabulary on text (truncate,…" | pre-release | flows |  |
| 18 | "Targets whose input is not text-shaped carry their…" | pre-release | flows |  |
| 19 | "**Commands**: `seed` (adds the seeds a corpus lacks,…" | pre-release | flows |  |
| 20 | "**Records**: `runs.jsonl` gets one line per seed or…" | pre-release | flows |  |
| 21 | "Everything is committed with the ledger line, a…" | pre-release | flows |  |
| 22 | "**Replay on every leg**: `runner/tests/test_de_dust_corpus.py` runs every entry…" | pre-release | flows |  |
| 23 | "Every reader of outside bytes is a target…" | pre-release | flows |  |
| 24 | "The order is the order of exposure: what…" | pre-release | flows |  |
| 25 | "# \| target \| readers \| status" | pre-release | flagged | Table header row, structure rather than a sentence |
| 26 | "1 \| `wire` \| `runner/wire/verify.py`: `verify_body`, `verify_body_keyed` \|…" | pre-release | flows |  |
| 27 | "2 \| `cloud` \| `runner/cloud/send_job.py`: `verify_body` \| in…" | pre-release | flows |  |
| 28 | "3 \| `v2` \| `runner/wire/protocol_v2.py`: `validate` \| in…" | pre-release | flows |  |
| 29 | "4 \| `crypto` \| `runner/wire/jobcrypto.py`: `decrypt_body` \| in…" | pre-release | flows |  |
| 30 | "5 \| `local` \| `runner/runner.py`: `_ingest_local_envelope_inner`; `runner/wire/transports.py`: `parse_envelope`…" | pre-release | flows |  |
| 31 | "6 \| `stash` \| `runner/runner.py`: `_record_payload` \| in…" | pre-release | flows |  |
| 32 | "7 \| `mail` \| `runner/runner.py`: `get_text_body`, `_bounce_of`, the…" | pre-release | flows |  |
| 33 | "8 \| `dtls` \| `runner/wire/dtlsproto.py`: `_split_records`, `_parse_handshake`, `_parse_extensions`,…" | pre-release | flows |  |
| 34 | "9 \| `board` \| `runner/wire/board.py`: `submit`, `offer`, `complete`,…" | pre-release | flows |  |
| 35 | "9b \| `board_ops` \| `runner/wire/board.py` under the sequence…" | pre-release | flows |  |
| 36 | "10 \| `channels` \| `runner/wire/transports.py`: `fetch_channel_messages` over a…" | pre-release | flows |  |
| 37 | "10b \| `inbox` \| `runner/wire/transports.py` under the sequence…" | pre-release | flows |  |
| 38 | "11 \| `manifest` \| `runner/ops/extensions.py`: `parse_manifest` \| in…" | pre-release | flows |  |
| 39 | "12 \| `local_inbox` \| `runner/runner.py` under the sequence…" | pre-release | flows |  |
| 40 | "13 \| `secret` \| `runner/cloud/send_job.py` `require_signable_secret` and `runner/guard/security.py`…" | pre-release | flows |  |
| 41 | "14 \| `queries` \| `runner/ops/policy.py` `apply_result_policy` and `runner/ops/queries.py`…" | pre-release | flows |  |
| 42 | "15 \| `names` \| `runner/guard/filenames.py` `validate_file_name` and `runner/runner.py`…" | pre-release | flows |  |
| 43 | "16 \| `query` \| `runner/ops/queries.py` `handle_query_mail` through the…" | pre-release | flows |  |
| 44 | "17 \| `board_mail` \| `runner/ops/startup.py` `handle_board_mail` through the…" | pre-release | flows |  |
| 45 | "18 \| `v2_mail` \| `runner/ops/handlers.py` `handle_v2_mail` through the…" | pre-release | flows |  |
| 46 | "19 \| `stage`, `collect` \| `runner/ops/exec.py`: the staging…" | pre-release | flows |  |
| 47 | "20 \| `keydir` \| `runner/wire/verify.py` `load_key_directory`, `validate_key_directory`, `key_directory_verdict`…" | pre-release | flows |  |
| 48 | "21 \| `address` \| `runner/wire/mailbox.py` `_valid_reply_to` and `send_mail`:…" | pre-release | flows |  |
| 49 | "22 \| `dtls_session` \| `runner/wire/dtlsproto.py`, stateful: a script…" | pre-release | flows |  |
| 50 | "23 \| `race_board` \| `runner/wire/board.py` under threads: lanes…" | pre-release | flows |  |
| 51 | "24 \| `race_stash` \| `runner/runner.py` under threads: lanes…" | pre-release | flows |  |
| 52 | "25 \| `race_state` \| `runner/runner.py` under threads: lanes…" | pre-release | flows |  |
| 53 | "26 \| `dtls_hostile` \| `runner/wire/dtlsproto.py`, stateful: the client…" | pre-release | flows |  |
| 54 | "27 \| `edge_subject` \| `runner/wire/transports.py` vs the hosted…" | pre-release | flows |  |
| 55 | "The `dtls` target's core holds three resumption tickets…" | pre-release | flows |  |
| 56 | "Not targets, and why: the Oracle's reading of…" | pre-release | flows |  |
| 57 | "A reader added to the product after this…" | pre-release | flows |  |
| 58 | "A contract is what a reader's own docstring…" | pre-release | flows |  |
| 59 | "Each target states its refusal type, so a…" | pre-release | flows |  |
| 60 | "**Refusal, not exception.** The verifiers (`wire`, `cloud`, `v2`)…" | pre-release | flows |  |
| 61 | "Any other exception is a crash." | pre-release | flows |  |
| 62 | "`dtls` is the same rule on the handshake:…" | pre-release | flows |  |
| 63 | "`board` never raises either: `submit` refuses a task…" | pre-release | flows |  |
| 64 | "`channels` never raises either: a file that is…" | pre-release | flows |  |
| 65 | "`manifest` refuses with `ValueError` and nothing else, and…" | pre-release | flows |  |
| 66 | "**Round-trip.** What a signer signs, both verifiers read…" | pre-release | flows |  |
| 67 | "**Differential.** Two readers of the same bytes agree:…" | pre-release | flows |  |
| 68 | "**Cross-platform.** The same entry accepts or refuses under…" | pre-release | flows |  |
| 69 | "The surface is the host identity and the…" | pre-release | flows |  |
| 70 | "A changed answer is a differential." | pre-release | flows |  |
| 71 | "**Provenance** (`mail`, `wire`, `cloud`, `inbox` now)." | pre-release | flows |  |
| 72 | "A reply target is the mailbox or a…" | pre-release | flows |  |
| 73 | "**Sequence.** The entry is the file as it…" | pre-release | flows |  |
| 74 | "`board_ops` is that for the board: every operation…" | pre-release | flows |  |
| 75 | "`channels` is the pair of inbox files, and…" | pre-release | flows |  |
| 76 | "`inbox` is the whole inbox as it was…" | pre-release | flows |  |
| 77 | "`local_inbox` is the local signal inbox scanned once:…" | pre-release | flows |  |
| 78 | "`local` is the same rule on the envelope…" | pre-release | flows |  |
| 79 | "**Reserved slots.** `sig` is the protocol's; a payload…" | pre-release | flows |  |
| 80 | "**Ceiling and view** (`queries`)." | pre-release | flows |  |
| 81 | "The policy is read under every ceiling the…" | pre-release | flows |  |
| 82 | "The output an entry carries is short (1,024…" | pre-release | flows |  |
| 83 | "**One rule set on every platform** (`names`)." | pre-release | flows |  |
| 84 | "`validate_file_name` refuses with `BadFileName` naming one of its…" | pre-release | flows |  |
| 85 | "`_safe_job_id` refuses with `JobRejected` and nothing else, or…" | pre-release | flows |  |
| 86 | "**The query message** (`query`)." | pre-release | flows |  |
| 87 | "The handler takes the message and never raises;…" | pre-release | flows |  |
| 88 | "**The board message** (`board_mail`)." | pre-release | flows |  |
| 89 | "The handler takes the message and never raises;…" | pre-release | flows |  |
| 90 | "**The version 2 message** (`v2_mail`)." | pre-release | flows |  |
| 91 | "The handler takes the message and never raises;…" | pre-release | flows |  |
| 92 | "A contract added later replays over every entry…" | pre-release | flows |  |
| 93 | "The sequence entries carry the recovery shapes too,…" | pre-release | flows |  |
| 94 | "A crash entry followed by a good one…" | pre-release | flows |  |
| 95 | "Seeds are suite-style fixtures with invented names (`example.com`,…" | pre-release | flows |  |
| 96 | "The vocabulary grows only where a target's readers…" | pre-release | flows |  |
| 97 | "The dictionary built from the IETF drafts' own…" | pre-release | flows |  |
| 98 | "The drafts' own examples are seeds beside it." | pre-release | flows |  |
| 99 | "The dictionary also learns: the same command harvests…" | pre-release | flows |  |
| 100 | "**The campaign (Muse)** runs the grow at every…" | pre-release | flows |  |
| 101 | "**The desk (Claude)** owns the tool, the targets,…" | pre-release | flows |  |
| 102 | "**Grok** built the DTLS target (Q66), the board…" | pre-release | flows |  |
| 103 | "Grok does not grow, and fixes a crash…" | pre-release | flows |  |
| 104 | "**The conductor** decides what is not in this…" | pre-release | flows |  |
| 105 | "**The split, in one line (the conductor, 2026-10-26):**…" | pre-release | flows |  |
| 106 | "The grow is continuous and pegs the CPU…" | pre-release | flows |  |
| 107 | "Since de_dust2 (`docs/project/de_dust2.md`) a cycling grow gives each…" | pre-release | flows |  |
| 108 | "The release train runs beside it; the corpus…" | pre-release | flows |  |
| 109 | "Every grow, kept or not, is a line…" | pre-release | flows |  |
| 110 | "Where each target Grok built landed is `docs/project/de_dust-where.md`." | pre-release | flows |  |
| 111 | "A release's evidence manifest beside its SBOM is…" | pre-release | flows |  |
| 112 | "The fleet's own signature of saturation, read on…" | pre-release | flows |  |
| 113 | "What paid the same day: time slices tilted…" | pre-release | flows |  |
| 114 | "`stats --yield` prints the table." | pre-release | flows |  |
| 115 | "A target whose full-depth grow keeps nothing and…" | pre-release | flows |  |
| 116 | "Saturation is per mutator before it is per…" | pre-release | flows |  |
| 117 | "Saturation is a fact about the vocabulary and…" | pre-release | flows |  |
| 118 | "A stronger contract on the same corpus (differential,…" | pre-release | flows |  |
| 119 | "New seeds in a shape the reader has…" | pre-release | flows |  |
| 120 | "New vocabulary the reader would meet (structural, grammar-built)." | pre-release | flows |  |
| 121 | "The next reader on the surface." | pre-release | flows |  |
| 122 | "Only when every target is saturated under every…" | pre-release | flows |  |
| 123 | "That instrument is `runner/tools/de_dust_survivors.py` (landed 2026-10-26): it mutates…" | pre-release | flows |  |
| 124 | "The first run: 1,877 mutants, 171 survivors; the…" | pre-release | flows |  |
| 125 | "Five seed batches later (2026-10-26): 101 of 1,950,…" | pre-release | flows |  |
| 126 | "Three readers were fixed on the way: the…" | pre-release | flows |  |
| 127 | "The sixth batch (the desk, 2026-10-26, at the…" | pre-release | flows |  |
| 128 | "The grow merges the seeds the corpus lacks…" | pre-release | flows |  |
| 129 | "The instrument then learned to put a mutant…" | pre-release | flows |  |
| 130 | "The seventh reading (the desk, 2026-10-27) went survivor…" | pre-release | flows |  |
| 131 | "A reading starts from this list; a survivor…" | pre-release | flows |  |
| 132 | "The grow never idles: a saturated target still…" | pre-release | flows |  |
| 133 | "What it tried is kept too: with the…" | pre-release | flows |  |
| 134 | "**Phase 1 (done 2026-10-26):** the six verifier targets,…" | pre-release | flows |  |
| 135 | "**Phase 2 (readers in the corpus, 2026-10-26):** DTLS…" | pre-release | flows |  |
| 136 | "**Phase 3 (done 2026-10-26):** the sequence contract on…" | pre-release | flows |  |
| 137 | "**Phase 4 (done 2026-10-26):** the grammar dictionary from…" | pre-release | flows |  |
| 138 | "A grow of 20,000 rounds on every target…" | pre-release | flows |  |
| 139 | "The same run kept one entry each on…" | pre-release | flows |  |
| 140 | "No crashes." | pre-release | flows |  |
| 141 | "The continuous grow carries the dictionary from here." | pre-release | flows |  |
| 142 | "**Phase 5 (in flight, 2026-10-26):** the posted capture's…" | pre-release | flows |  |
| 143 | "Both verifiers accept it." | pre-release | flows |  |
| 144 | "`local` refuses the job, which is a sensor…" | pre-release | flows |  |
| 145 | "The capture's own ciphertexts stay where they were…" | pre-release | flows |  |
| 146 | "The mutation survivors are not started." | pre-release | flows |  |
| 147 | "**Then:** every reader the product adds, in the…" | pre-release | flows |  |
| 148 | "Every reader of outside bytes has a target." | pre-release | flows |  |
| 149 | "Every target has a refusal type, a round-trip…" | pre-release | flows |  |
| 150 | "Every grow is a line in the tree…" | pre-release | flows |  |
| 151 | "Every crash is a Q within the hour,…" | pre-release | flows |  |
| 152 | "No skip, no `continue-on-error`, no hand edit, nothing…" | pre-release | flows |  |
| 153 | "The resource line reads on target." | pre-release | flows |  |
| 154 | "The ledger reads the campaign's whole history without…" | pre-release | flows |  |
| 155 | "As Q62: no new CI leg, no `continue-on-error`,…" | pre-release | flows |  |
| 156 | "As Q65: no live socket until the new…" | pre-release | flows |  |
