# Version 3 draft: sentence-by-sentence accuracy review

Date: 3-Nov-2026. Scope: `docs/ietf/draft-slutsky-homing-pigeon-v3-00.md`
against the code on main at 99c672e1. The draft stays local; nothing
in this pass submits it anywhere.

## Method

1. The draft was read in full and every checkable statement was
   extracted into the ledger below, 1 row per statement: normative
   requirements, factual claims about behavior, every number, every
   default, every option / field / media-type name, and every
   cross-reference to the version 1 draft and to RFCs.
2. Each row was settled against ground truth in this order:
   (a) the code and tests on main (`runner/wire/dtls_mailbox.py`,
   `runner/wire/dtlsproto.py`, `runner/wire/platformcard.py`,
   `runner/wire/subject.py`, `runner/wire/mailbox.py`,
   `runner/transport_extensions/email/__main__.py`,
   `runner/transport_extensions/dtls/__main__.py`,
   `runner/cloud/send_dtls.py`, `runner/tests/test_dtls_email_v3*.py`);
   (b) deterministic machine checks for mechanical claims -- a script
   greps the code for the exact constant, default, or string the
   sentence names, and its output is the row's evidence (the values
   are collected in the machine-check table below);
   (c) the version 1 draft (-03, `docs/ietf/draft-slutsky-homing-pigeon-03.md`)
   for inherited statements; (d) the cited RFCs (RFC 9846's table of
   contents was read at rfc-editor.org for the citation rows).
3. Verdicts: **holds** (the statement is true as written; a
   holds-with-note row is true and carries a precision note),
   **draft-wrong** (the text was corrected in this pass),
   **code-wrong** (the code was fixed test-first in this pass),
   **unverifiable-from-here** (nothing on this side can settle it),
   **OPEN** (genuinely ambiguous; the text is unchanged and the row
   is left for the owner's review).
4. Settled decisions were not reopened: the title and docname stay;
   the platform-card provenance silence is deliberate; the media-type
   wire string `application/hp-dtls3` is unchanged (its label was
   verified as already corrected, and not altered).

## The defaults sweep (the lockdown flip)

The draft was written before the security-modes default flip
(since 3.15.137, every security mode reads ENFORCE when unset, and
a box that cannot enforce refuses to start). Every occurrence of
"default" in the draft was checked, and the draft was searched for
"enforce", "audit", "security mode", and "lockdown":

| Draft occurrence | What it is about | Flip-sensitive? |
|---|---|---|
| Introduction: "by default, per-job encryption" | version 1 object crypto on the sending side | No |
| Section 1.1: "the option is off by default" | the `dtls_via_email` enablement gate | No |
| Section 4.1: "a local default of the datagram binding" | UDP port 20220 | No |
| Section 5.3: "its default chunk is 32768 base64 characters" | the carriage chunk size (number corrected, see F4) | No |
| Section 7.1: "than its defaults" | RFC 9147's timer defaults | No |
| Section 11: "family by default" | the platform disclosure tier | No |
| Section 15: "version 1's local default" | UDP port 20220 again | No |

"enforce", "audit", "security mode", and "lockdown" do not occur in
the draft at all. No sentence in the draft states or depends on the
runner's security-modes defaults, so the flip falsifies no draft
sentence. The drift the owner suspected was real but elsewhere:
1 wrong number (Section 5.3), 1 wrong eviction description
(Sections 7.2 and 16.4), 1 obsolete citation (Section 13), and
1 place where the code had drifted from the draft (the Section 5.3
size cap, fixed in the code).

## Machine checks (script output, mirror tree at 99c672e1)

```
carriage datagram limit (octets) = 262144
default chunk (base64 chars) = 32768
max decoded octets per chunk = 24576
max parts per transfer = 1024
max chunk chars accepted = 1024 * 1024
reassembly max_transfers = 64
reassembly ttl_sec = 3600
reassembly deadline_sec default = None (reads as ttl_sec)
digest cache max_entries = 4096
digest cache refreshes on hit (move_to_end in _already_seen) = True
transfer id generation = token_hex(8)
suite = 0x1302
hybrid group = 4588
hybrid client share bytes = 1216
hybrid server share bytes = 1120
platform extension value = 0xFFA0
psk modes offered by client = bytes([1, PSK_MODE_DHE_KE])
RETRANSMIT_FIRST = 1.0
RETRANSMIT_MAX = 16.0
RETRANSMIT_GIVE_UP = 60.0
TICKET_LIFETIME = 3600
mail server hybrid default = True
mail client hybrid default = True
enablement literal-true = True
held result ttl default (seconds) = 604800
held result max count = 64
held result max bytes = 16 * 1024 * 1024
cookie key file = dtls-cookie.key
cookie key file mode = True (created 0600)
platform tiers = "none", "family", "standard", "full"
platform default tier = family
subject space set is ECMAScript = True
core retransmissions before the 60s give-up = 6 (at +1, +3, +7, +15, +31, +47 s)
```

## The ledger

### Abstract and Introduction

| # | Section | Statement (short quote) | Verdict | Evidence |
|---|---|---|---|---|
| 1 | Abstract | "a transport extension to version 1, not a replacement ... the version 1 job acceptance gate is unchanged" | holds | Session jobs are delivered to the core as ordinary envelopes (`email/__main__.py` `_drain_dtls_apps` -> `ch.deliver_job`); the gate is the core's and the carriage does not touch it |
| 2 | Abstract | "Version 1 defines a DTLS 1.3 session profile (its Sections 19 and 20): one cipher suite, a pre-shared key ..., and the platform_info disclosure carried in the server's EncryptedExtensions" | holds | v1 -03 Sections 19.2 and 20, read in full |
| 3 | Abstract | "the 3 of this document's title ... is not a value of any object's version field ... HP-DTLS/3 ... is a carriage label" | holds | Objects in sessions are v1 objects (`v` = 1); `HP-DTLS/3` occurs only in the frame header (`_HEADER_RE`) |
| 4 | Abstract | "a local, unsubmitted draft ... requests no IANA action" | holds | Process fact; consistent with Section 15 and the draft's own status block |
| 5 | Introduction | "the object crypto of version 1 -- a signature and, by default, per-job encryption under the shared secret" | holds | v1 Section 16: senders SHOULD encrypt and the reference sender encrypts by default (`send_dtls.py`: `--encrypt` is the default, `--cleartext` opts out) |
| 6 | Introduction | the 4 bullets mapping the design to Sections 5, 6, 8, 10, 10.2, 11 | holds | Section map checked against the draft's own structure |
| 7 | Introduction | "A deployment MAY offer either binding, or both; the profile, the handshake, and the acceptance gate are the same on each" | holds | Both bindings exist as transport extensions over 1 engine (`dtlsproto.py`); the gate is binding-independent |
| 8 | Section 1.1 | "implemented and tested in the Homing Pigeon software suite under an opt-in configuration option; the option is off by default" | holds | `cfg.get("dtls_via_email") is True` gates the whole carriage in the email extension; absent or non-true builds no DTLS server |
| 9 | Section 2 | the BCP 14 boilerplate | holds | Standard RFC 2119 / RFC 8174 form |
| 10 | Section 3 | the 4 added terms (flight mail, mail session-id, transfer, carriage = "the rules of Sections 5 to 9") | holds | Each term matches the code structure it names; the carriage is specified in Sections 5 to 9 |

### Section 4 -- the profile on this carriage

| # | Section | Statement | Verdict | Evidence |
|---|---|---|---|---|
| 11 | 4.1 | "DTLS 1.3 is the session protocol. The 1 cipher suite is TLS_AES_256_GCM_SHA384" | holds | `SUITE_AES256 = 0x1302` is the only suite in `dtlsproto.py`; the client offers only it and the server refuses any other |
| 12 | 4.1 | "The pre-shared key is the shared secret ... an authenticator and only an authenticator ... no second secret and no new key material" | holds | `make_secret_lookup` over `shared_secret` + `additional_secrets`; session keys derive from the ephemeral exchange with the PSK as authenticator |
| 13 | 4.1 | "Only the `psk_dhe_ke` key exchange mode is used. `psk_ke` MUST NOT be offered, accepted, or fallen back to, in a full handshake or in resumption" | holds | The client offers `bytes([1, PSK_MODE_DHE_KE])` only; the server refuses (illegal_parameter) a hello that does not offer DHE; `test_psk_ke_only_offer_over_mail_is_refused` |
| 14 | 4.1 | "Every handshake, full or resumed, carries a fresh ephemeral share" | holds | A fresh ephemeral is generated per handshake in the core, on the resume path as on the full path |
| 15 | 4.1 | "The responder is stateless until a HelloRetryRequest cookie validates" | holds | The server core holds no session before the cookie validates; the cookie is `ch1_hash` + HMAC(cookie secret, address + ch1_hash) |
| 16 | 4.1 | "Connection IDs are used in both directions" | holds-with-note | The engine negotiates the `connection_id` extension and carries CIDs in records in both directions. The citation (RFC 9146) is version 1's own Section 19.2 citation for the same mechanism |
| 17 | 4.1 | "Early data is not used ... A ClientHello that carries early data ... MUST be rejected" | holds | A ClientHello carrying the early-data extension is dropped unanswered at the server core; epoch 1 is never derived; `EarlyDataRejectionTest` (2 tests) |
| 18 | 4.1 | "The platform_info extension is offered empty in the ClientHello and, when offered, MAY be answered in EncryptedExtensions only" | holds | The client offers `(0xFFA0, b"")` in every ClientHello; the server sends the payload only in EncryptedExtensions and only when offered |
| 19 | 4.1 | "Certificates are not part of this profile ... A ClientHello that offers no pre_shared_key extension is refused before any key is derived" | holds | The server core's `begin()` refuses with missing_extension when the pre_shared_key extension is absent, before any derivation |
| 20 | 4.1 | "The UDP port 20220 of version 1 is a local default of the datagram binding. This carriage has no port" | holds | v1 Section 19.1; `DEFAULT_PORT = 20220` in the DTLS extension and in `send_dtls.py`; the carriage code has no port |
| 21 | 4.2 | the carriage changes only size, ordering, duplication, and delay handling, plus the Section 4.4 exception | holds | Design statement; the code's carriage layer (`dtls_mailbox.py`) does exactly segmentation, reassembly, dedup, and dispatch, and nothing cryptographic of its own |
| 22 | 4.3 | "A runner enables it by explicit configuration (in the reference implementation, the `dtls_via_email` option, which only the literal boolean true enables)" | holds | Machine check: `enablement literal-true = True` |
| 23 | 4.3 | "the shared secret is handed to the component that terminates DTLS only when the carriage is enabled" | holds | The email extension builds its DTLS server only when enabled, and refuses (log, no server) when enabled with no secret handed over |
| 24 | 4.3 | "A platform card MAY state, as an unauthenticated fact, that the runner offers this carriage" (the discovery hint) | holds | Permissive text, and the settled form of the hint. Note: the reference card (`platformcard.build_card`) carries no carriage member today; the MAY permits one and asserts nothing about the current card |
| 25 | 4.4 | "in the client share, the ML-KEM-768 encapsulation key followed by an X25519 share; in the server share, the ML-KEM ciphertext followed by an X25519 share" | holds | `HYBRID_CLIENT_SHARE_BYTES = 1216` (1184 + 32); `HYBRID_SERVER_SHARE_BYTES = 1120` (1088 + 32); layout in the core matches RFC 10024 |
| 26 | 4.4 | "a shared secret that is the ML-KEM secret followed by the X25519 secret, fed into the same key schedule" | holds | `HYBRID_SECRET_BYTES = 64`; the combined secret enters the same key schedule the X25519 secret feeds |
| 27 | 4.4 | "A responder on this carriage that is offered the hybrid share selects it" | holds | `DtlsMailServer` and `DtlsMailClient` both default `hybrid=True`; the server core selects the hybrid group when enabled and offered |
| 28 | 4.4 | "A responder that does not implement this section -- and every peer on the datagram binding ... -- selects the X25519 share" | holds | The engine cores default `hybrid=False`; the datagram extension and `send_dtls.py` construct them without enabling it, so the version 1 wire is unchanged |
| 29 | 4.4 | "The responder MUST perform the encapsulation-key check of FIPS 203 Section 7.2 ... and MUST abort ... with an illegal_parameter alert when it fails" | holds | `_hybrid_answer` runs `mlkem.encapsulation_key_check`; failure raises the illegal_parameter alert |
| 30 | 4.4 | "A hybrid share of any size other than the one RFC 10024 fixes ... fail[s] the handshake closed; nothing falls back" | holds | Share-size checks on both sides raise before any fallback; a hybrid session whose Finished does not verify dies |
| 31 | 4.4 | the group is X25519MLKEM768 per RFC 10024 | holds | `GROUP_X25519MLKEM768 = 4588`; RFC 10024 verified (Standards Track, August 2026, value 4588, DTLS-OK Y, Recommended Y) |

### Sections 5 and 6 -- message format, segmentation, reassembly

| # | Section | Statement | Verdict | Evidence |
|---|---|---|---|---|
| 32 | 5.1 | the flight subject grammar and its ABNF | holds | `_V3_SUBJECT_RE` is built from the one subject grammar module and must fullmatch (after the prefix rule) |
| 33 | 5.1 | "session-id = 1*128 session-id-char ... and not "." or ".."" with `session-id-char = ALPHA / DIGIT / "." / "_" / "-"` | holds | `valid_session_id`: `^[A-Za-z0-9._-]{1,128}$` plus the explicit "." / ".." exclusion |
| 34 | 5.1 | the alphabet "is an alphabet safe in a mail header field (RFC 5322, Section 2.2) and as a filesystem name", inherited from version 1's `word-char` | holds | Identical to v1 Section 6's `job-id-char`; the sentence is the corrected form of the final pass, re-verified against both texts |
| 35 | 5.1 | "a future widening of version 1's production MUST NOT widen it" | unverifiable-from-here | A requirement on a future document, not on anything in this tree |
| 36 | 5.1 | "The mail session-id is chosen by the initiator, 1 per session attempt; a resumption attempt ... takes a new mail session-id" | holds | The client mints a fresh id per attempt; a resumption attempt is a new client attempt with a new id |
| 37 | 5.1 | "A receiver MAY accept at most 1 leading "Re:" or "Fwd:" (case-insensitive), and only when the remainder is exactly a flight subject" | holds | `_flight_subject_match` strips at most 1 prefix, then requires a fullmatch; `SubjectPrefixTest` (a chain does not route) |
| 38 | 5.1 | "A receiver MUST NOT treat a flight subject, a mail session-id, or any mail header ... as evidence of who sent a flight" | holds | No header is read for authentication anywhere in the carriage path; authentication is applied to the reassembled datagram by DTLS only |
| 39 | 5.1 | the unaddressed harness shape "MAY also [be] accept[ed] ... inside an in-process test harness"; "A deployment mailbox MUST NOT feed it to a DTLS stack" | holds | `parse_message` classifies it; the email extension logs and drops unaddressed DTLS mail without feeding it; `test_an_unaddressed_flight_is_not_fed_on_the_mailbox` |
| 40 | 5.2 | the frame's content type is `application/hp-dtls3` -- "a name in the standards tree that no registration backs" | holds | The wire string is `FLIGHT_CONTENT_TYPE` in the code and is unchanged; the label sentence is the settled corrected form, verified and not altered |
| 41 | 5.2 | the frame is "1 header line, 1 line break, and 1 base64 chunk" with the shown header shape | holds | `_HEADER_RE`: `^HP-DTLS/3 transfer=([0-9a-f]{16}) part=([0-9]+) parts=([0-9]+) bytes=([0-9]+) sha384=([0-9a-f]{96})$` -- field order, names, and cases exact |
| 42 | 5.2 | "`t` is the transfer identifier: 16 lowercase hexadecimal digits, chosen fresh by the sender for each datagram" | holds | `token_hex(8)` per `encode_flight` call |
| 43 | 5.2 | "`i` and `n` are the 0-based index ... An unsegmented datagram is part 0 of 1" | holds | `encode_flight` numbering; the header parser refuses an index outside the count |
| 44 | 5.2 | "`b` is the total length of the datagram in octets ... this document specifies no padding" | holds | No padding exists anywhere in the carriage code |
| 45 | 5.2 | "`d` is the SHA-384 digest of the whole datagram, as 96 lowercase hexadecimal digits" | holds | The header carries `hashlib.sha384` hex; reassembly completes only on a digest match |
| 46 | 5.2 | "Slices are cut on base64 group boundaries, so each chunk decodes on its own" | holds-with-note | Slices are cut from the encoded text at the chunk size; the default (32768) is a multiple of 4, so the property holds. `chunk_chars` is a code parameter of the encoder, not a configuration surface, and the deployed path always uses the default |
| 47 | 5.2 | "The digest ... is not a signature and MUST NOT be treated as authentication" | holds | The digest is checked for wholeness at reassembly only; the datagram is authenticated afterwards, by DTLS |
| 48 | 5.2 | "Text outside the part is not the frame and MUST be ignored for framing" (the gateway-footer rule) | holds | When a typed part is present it is the only frame source; `MimeFrameTest` footer and gateway cases |
| 49 | 5.2 | "The part is a leaf part ... A sender MUST NOT wrap it in [a message/rfc822 part]. A receiver finds the frame part by its content type wherever it sits" | holds | `build_flight_message` attaches the frame bytes as a direct part; the receiver walks the whole part tree; `test_the_senders_frame_part_is_a_leaf_part` |
| 50 | 5.2 | "Base64 folding at 76 columns inside the part is accepted: the chunk is read with its whitespace removed" | holds | The chunk text is read with all whitespace stripped before the header parse |
| 51 | 5.2 | "Quoted-printable MUST NOT be used for the part and MUST NOT be accepted for it" | holds | A typed part whose transfer encoding is not base64 yields no frame and fails closed; `test_a_typed_part_must_be_base64` |
| 52 | 5.2 | the naked shape: with no typed part, "the frame as the 1st text/plain part's text ... with no preamble and no trailer" | holds | The parser's fallback extraction, the same one ordinary mail bodies get |
| 53 | 5.2 | "When a typed part is present it is the only frame source: a frame-shaped text part does not rescue a typed part that does not frame" | holds | A present-but-unusable typed part returns an empty frame, which is invalid; `test_a_typed_part_is_the_only_frame_source` |
| 54 | 5.3 | "a receiver MUST refuse a flight mail whose raw object exceeds the [version 1 mail size] cap before it decodes any base64, allocates any reassembly state, or feeds any octet to a DTLS stack" | **code-wrong -- fixed in this pass** | The core applies `max_job_bytes` to the mail it takes in, but flight mail never reaches the core: the extension decoded the frame in `parse_message` with no cap applied first. Fixed in the email extension (see "Code fix" below); v1's cap text is Section 5 ("The RECOMMENDED cap is 4194304 octets. A cap of 0 means no limit") and the core's reading of it is `runner/ops/mail.py` |
| 55 | 5.3 | "The reference implementation's limit is 262144 octets" (the carriage datagram limit) | holds | Machine check: `DEFAULT_MAX_DATAGRAM_BYTES = 256 * 1024 = 262144`; a header declaring more is refused before any state is kept |
| 56 | 5.3 | "its default chunk is 32768 base64 characters (8192 decoded octets at most per part before the header)" | **draft-wrong -- corrected (F4)** | 32768 base64 characters decode to at most 24576 octets (32768 x 3/4). The parenthetical now reads 24576 |
| 57 | 5.3 | "A part count MUST NOT exceed 1024" | holds | `_MAX_PARTS = 1024`; the header parser refuses a larger count |
| 58 | 6 | "The receiver's reassembly state is keyed by (mail session-id, transfer identifier)" | holds | The `FlightReassembler` key is exactly that pair |
| 59 | 6 | "Parts MAY arrive in any order. Duplicate parts are idempotent" | holds | Parts are held by index; the same index with the same chunk changes nothing; `SegmentationTest` |
| 60 | 6 | "A part that contradicts its transfer ... destroys the transfer" | holds | A conflicting chunk or header field drops the transfer's state and completes nothing |
| 61 | 6 | "A transfer completes when every index is held and the concatenated datagram matches the declared byte count and digest. A completed datagram is delivered upward exactly once, and the state is discarded" | holds | The reassembler's completion rule, in those terms |
| 62 | 6 | "the reference implementation holds at most 64 transfers" | holds | Machine check: `max_transfers = 64`; overflow evicts the oldest |
| 63 | 6 | "a transfer [is kept] for at most 3600 seconds from its first part, and 3600 seconds from its last part, and no arriving part extends the first-part deadline" | holds | `ttl_sec = 3600` (idle, from the last part) and `deadline_sec` defaulting to it (absolute, from the first part); `ReassemblyDeadlineTest`, including the slow-drip case |

### Section 7 -- retransmission, duplicates, ordering

| # | Section | Statement | Verdict | Evidence |
|---|---|---|---|---|
| 64 | 7.1 | "The carriage defines no acknowledgement and no retransmission timer of its own. Retransmission is the DTLS handshake's" | holds | Only the cores carry timers (`RETRANSMIT_*` in `dtlsproto.py`); the mail wrappers send what the core emits, when it emits it |
| 65 | 7.1 | "a flight's re-send is a new flight mail, under a new transfer identifier ... a new record, with a new record sequence number ... not a copy of the earlier mail" | holds | Each outbound datagram is re-encoded per send (fresh transfer id) and retransmission re-enters the record layer in the core |
| 66 | 7.1 | "A sender SHOULD NOT re-send a flight mail at the mail layer on its own schedule" | holds | No mail-layer re-send exists in the wrappers; the only mail-layer re-send is the Section 7.2 re-post, which is the stack's answer, not a copy of a flight |
| 67 | 7.1 | "the initial retransmission interval SHOULD be at least 2 of the implementation's mailbox poll periods" | **OPEN** | The core's first retransmission interval is 1.0 second whatever the poll period is, and the mail drivers tick the core on their poll cadence, so the effective first retransmission lands about 1 poll period out, not 2. Whether the mail wrappers should stretch the core's timers, or the sentence should be softened, is left for the owner; the text is unchanged |
| 68 | 7.1 | "an attempt SHOULD be given up after about 8 retransmissions" | **OPEN** | Measured: the core retransmits at +1, +3, +7, +15, +31, and +47 seconds -- 6 retransmissions -- and the flight dies when its age passes the 60-second give-up. The code bounds the attempt by time, the sentence by count. Same disposition as row 67 |
| 69 | 7.2 | "A receiver keeps a digest of each datagram it has accepted from flight mail, bounded ... the reference implementation's cache holds 4096 digests" | holds | Machine check: `max_entries = 4096` |
| 70 | 7.2 | "... first in first out" (the digest cache's eviction) | **draft-wrong -- corrected (F5)** | A hit refreshes the entry's position (`move_to_end` in `_already_seen`), so eviction is least-recently-seen, not first in first out. Corrected in Section 7.2 and in the Section 16.4 list (row 153) |
| 71 | 7.2 | "The connection-id binding check of Section 9.2 runs before a datagram's digest is recorded, so a misaddressed copy cannot poison the cache" | holds | The order in `receive_bytes`: binding check first, digest recorded after |
| 72 | 7.2 | "A digest hit on a handshake-phase datagram is not fed to the DTLS stack again ... the receiver instead re-posts its saved last outbound flight, under a new transfer identifier" | holds | `DuplicateSplitTest`, including the replayed initialization and the replayed cookied hello |
| 73 | 7.2 | "a receiver MUST re-post a saved flight at most once per generation of that flight ... only a new flight from the DTLS stack ... arms another" | holds | The re-post budget is 1 per flight generation, re-armed only when the stack produces a new flight (`_repost_armed` / `_save_flight`) |
| 74 | 7.2 | "A thousand copies of 1 ClientHello therefore cost the responder at most 1 HelloRetryRequest mail beyond the 1 it already sent" | holds | `test_a_thousand_copies_of_a_hello_cost_one_repost` |
| 75 | 7.2 | "A digest hit on application data is dropped and does nothing" | holds | The application-phase branch of the duplicate split returns nothing |
| 76 | 7.2 | a DTLS retransmission "is not bit-identical ... It misses this cache, enters the stack, and is answered by the stack. The budget does not limit it" | holds | A retransmission carries a new record sequence number, so its digest differs and the stack answers it from its state machine |
| 77 | 7.2 | "A duplicate flight mail MUST NOT create a 2nd session, MUST NOT deliver an application message twice, and MUST NOT cause a job to run twice. A duplicate part MUST NOT complete a transfer twice" | holds | The 3 layers' rules compose: digest cache, record-layer sequence window, gate seen-set; transfer state is discarded at completion |
| 78 | 7.3 | "No ordering is assumed anywhere in this carriage ... Application messages inside a session keep the session's own order, which the record layer defines" | holds | Reassembly is order-independent; application messages are delivered in record order by the core |

### Section 8 -- the mailbox parser

| # | Section | Statement | Verdict | Evidence |
|---|---|---|---|---|
| 79 | 8.1 | the dispatch order: flight subject -> DTLS and nothing else; job subject -> the gate; everything else -> other mail | holds | `pass_once` classifies before anything is delivered; DTLS kinds are handled and consumed ahead of the job path |
| 80 | 8.1 | "DTLS classification happens in the component that owns the mailbox ... The runner core -- the acceptance gate -- never sees flight mail" | holds | Classification and consumption happen in the email transport extension; nothing about a flight crosses the channel to the core |
| 81 | 8.2 | "A complete datagram is an initialization flight when its 1st record is a plaintext handshake record whose handshake message is one complete ClientHello" | holds | `_is_client_hello`, in those terms |
| 82 | 8.2 | "A fragmented or incomplete first handshake message ... draws no HelloRetryRequest" and is allocated "no reassembly state" | holds-with-note | The server core drops a fragmented first flight unanswered (`test_a_fragmented_first_hello_draws_no_answer`). The "no reassembly state" is the DTLS-layer sense -- the core buffers no handshake fragments before a cookie; the mail reassembly of the datagram's own parts is Section 6's, bounded there |
| 83 | 8.2 | "A complete datagram that parses as DTLS records but is not an initialization is a session datagram" | holds | The classifier's third case, fed to the stack under its mail session-id |
| 84 | 8.3 | malformed flight mail "is consumed as DTLS input -- marked seen ... dropped ... and never reinterpreted as a job" | holds | `_handle_dtls_mail` marks seen on every branch; `test_a_malformed_dtls_mail_is_consumed_and_delivers_nothing` |
| 85 | 8.3 | "An implementation MUST NOT fall back from a DTLS-shaped failure to any other reading of the same message" | holds | The lane is chosen by classification before any job handling, and the DTLS lane never falls through |
| 86 | 8.4 | "A party MUST mark a flight message seen only when it has consumed it" | holds | Marking seen is the consumer's explicit act in the extension, after handling |
| 87 | 8.4 | "A fetch made to decide, before consumption, MUST NOT set the seen flag: over IMAP that is a BODY.PEEK fetch" | holds | `fetch_job_mails` fetches `(BODY.PEEK[])`; `PeekFetchTest.test_fetches_are_peeks` |
| 88 | 8.4 | "An initiator MUST ignore flight mail whose mail session-id is not an attempt it has open" | holds | The client's receive path returns nothing for an unknown mail session-id |

### Section 9 -- session establishment

| # | Section | Statement | Verdict | Evidence |
|---|---|---|---|---|
| 89 | 9.1 | the 5 steps of an attempt (ClientHello; stateless HelloRetryRequest; cookied ClientHello; the responder's flight of ServerHello, EncryptedExtensions, Finished; the initiator's Finished) | holds | The cores implement exactly this exchange; proven live over the real mailbox (2-Nov and 3-Nov) and in `MailSessionTest` |
| 90 | 9.2 | "The peer address on this carriage is the ASCII string `email:` followed by the mail session-id" | holds | Both mail wrappers bind sessions under `"email:" + session_id` |
| 91 | 9.2 | "The cookie key is a secret of the responder, generated by the responder and not derived from the address or from anything the message asserts" | holds | 32 random bytes, drawn by the responder; persistence is row 100 |
| 92 | 9.2 | "The PSK identity inside the handshake selects the shared secret, including any additional secret ... the mail session-id never selects a key" | holds | The lookup is keyed by PSK identity only (`make_secret_lookup`, wrapped by the key-directory lookup) |
| 93 | 9.2 | "A protected record is accepted under a mail session-id only if its destination connection ID is the connection ID bound to that mail session-id. A record whose connection ID is bound to a different mail session-id is dropped" | holds | Bound records are checked against their session before dedup and before the stack; `test_a_record_from_one_session_is_not_the_others` |
| 94 | 9.3 | "tickets MAY be issued and, on this carriage, MUST be single-use" | holds | A ticket is issued at establishment and deleted from the table when presented, before it is used, so a replay finds nothing; `test_a_ticket_resumes_only_once_over_mail` |
| 95 | 9.3 | "A replayed ticket MUST NOT become a second long-lived secret" | holds | The same one-shot deletion; ticket lifetime is 3600 seconds (`TICKET_LIFETIME`) |
| 96 | 9.3 | "(Version 1's SHOULD for the datagram binding is unchanged.)" | holds | v1 Section 19.2: "the ticket SHOULD be single-use" |
| 97 | 9.3 | "A resumed handshake is a full handshake in everything that matters here -- a fresh mail session-id, a fresh ephemeral share, `psk_dhe_ke` only, and a fresh platform disclosure" | holds | `ResumptionOverMailTest`, including `test_resumption_over_mail_fresh_share_and_redisclosure` |
| 98 | 9.3 | "A deployment MAY disable resumption on this carriage by configuration" | holds-with-note | Permissive text. The reference implementation offers no such switch: it always issues tickets and enforces single-use. The sentence permits the switch; it does not assert one exists |
| 99 | 9.4 | "An attempt ... is abandoned by the side waiting on it when its retransmission gives up, and its partial state ... expires with the bounds of Sections 6 and 7.2" | holds | The cores kill a flight at the 60-second give-up; reassembly and cache state expire under their own bounds |
| 100 | 9.4 | "A responder SHOULD keep its cookie key across its own restarts ... kept as the shared secret is kept: in the responder's own state ... The reference implementation keeps it beside the mailbox's own state, readable by its owner only" | holds | `dtls-cookie.key` beside the channel state, created with mode 0600, loaded when the DTLS server is built and installed as the core's cookie secret; `test_a_responder_restart_between_retry_and_cookied_hello_completes` |
| 101 | 9.4 | "A responder whose cookie key does not survive a restart abandons every attempt in flight at that restart ... Recovery is a fresh attempt under a new mail session-id" | holds | `test_without_the_kept_cookie_key_a_restart_abandons_the_attempt` |
| 102 | 9.4 | "Established sessions do not survive a restart of either end on any binding -- their keys are erased with the process" | holds | Sessions exist only in process memory, on both bindings |
| 103 | 9.5 | "an implementation MUST NOT keep a session's keys, or its mail session-id binding, past the session's configured lifetime. Keys are erased with the session" | holds-with-note | The implementation has no separate session-lifetime knob: a handshake dies at the retransmission give-up, an established session lives in process memory until it ends or the process does, and its keys are erased with it. The configured lifetime in the reference implementation is the process's |

### Section 10 -- jobs and results inside a session

| # | Section | Statement | Verdict | Evidence |
|---|---|---|---|---|
| 104 | 10.1 | "a 4-octet big-endian length prefix per message, and each application message is exactly 1 envelope" | holds | The core's application framing; the envelope is the channel envelope (subject line, blank line, body) |
| 105 | 10.1 | "a completed application message is converted back into that ordinary envelope and delivered to the runner core through the same channel an ordinary mail job crosses. The core cannot tell ... that the envelope arrived inside a session" | holds | `_drain_dtls_apps` -> `ch.deliver_job`, the same call ordinary mail delivery makes |
| 106 | 10.1 | "A job inside a session is a version 1 job object and a result inside a session is a version 1 result object ... no object in a session carries [the 3]" | holds | The objects are the v1 job and result objects, `v` = 1 |
| 107 | 10.2 | "Completing a DTLS handshake MUST NOT bypass, widen, or substitute for the job acceptance gate. A job carried inside a session is admitted exactly as the same job arriving as ordinary mail" | holds | Delivery is as an ordinary envelope into the same gate; `test_the_session_key_does_not_authorize_the_job` |
| 108 | 10.2 | "a cleartext object inside a session is still refused unless the operator has enabled cleartext acceptance" | holds | The gate's cleartext rule is binding-independent; `test_a_cleartext_job_inside_a_session_is_refused` |
| 109 | 10.2 | "The PSK identity that opened the session and the key id that signed a job inside it need not name the same key ... A job signed under 1 key MAY be carried by a session opened under another" | holds | The session's identity is used only for result routing (Section 10.3); admission reads the job's own key id and policy |
| 110 | 10.3 | "The carriage remembers, for each job it delivered from a session, the session's connection ID and the job ident together, and the PSK identity the session authenticated under -- never the job ident alone" | holds | The extension's hold map is keyed `(connection id, job ident)` and stores the identity |
| 111 | 10.3 | "The hold is kept as the result is kept, in the responder's own state and across a restart of the process" | holds | `<ident>.session.txt` sidecars beside the channel state, loaded at startup; `test_a_restart_does_not_downgrade_a_held_session_result`, `test_a_restart_keeps_a_hold_for_a_job_still_running` |
| 112 | 10.3 | a held result leaves "in exactly 1 way: inside a later session that authenticated under the same PSK identity and that carries the same job ident again" | holds | `_send_result_on_session` checks the live session's identity against the hold's; `test_a_same_key_session_carrying_the_ident_again_gets_the_result` |
| 113 | 10.3 | "A job whose ident is held for another PSK identity's job is not delivered: it is logged and dropped" | holds | The owner check in `_drain_dtls_apps` |
| 114 | 10.3 | "A held result MUST NOT be sent as an ordinary mail result, MUST NOT be sent inside a session under a different PSK identity, and MUST NOT be sent inside a different job's session" | holds | `flush_results` routes a session-bound result only to the session path; `test_a_session_result_is_never_downgraded_to_plain_mail`, `test_a_result_never_enters_another_keys_session` |
| 115 | 10.3 | "A held result expires by age -- the reference implementation's bound is 7 days -- and the held set as a whole is bounded in count and in total bytes, oldest first. An expired result is dropped and the expiry is logged; it is never sent" | holds | Machine checks: TTL default 604800 (7 days, `dtls_result_ttl_sec` overrides), count 64, bytes 16 MiB; expiry acks the file, logs, and forgets only the dropped holds; `test_a_session_result_expires_instead_of_waiting_forever`, `test_held_session_results_are_count_bounded`, `test_expiry_of_one_result_leaves_an_in_flight_hold` |
| 116 | 10.3 | "The PSK identity distinguishes submitters only as finely as the key directory. Two peers that authenticate with the same secret are the same identity" | holds | The identity behind a session is its PSK identity (or its issuing key's, for a resumed session) |

### Sections 11 to 15 -- disclosure, downgrade, replay, operations, IANA

| # | Section | Statement | Verdict | Evidence |
|---|---|---|---|---|
| 117 | 11 | the disclosure mechanism as version 1 Section 20: offered empty, answered only in EncryptedExtensions, never unsolicited, never elsewhere | holds | v1 Section 20 and row 18 |
| 118 | 11 | "the tiers are version 1's (none, family by default, standard, full)" | holds | Machine checks: `TIERS = "none", "family", "standard", "full"`, `DEFAULT_TIER = "family"`; `greeting_tier` defaults to family on both bindings |
| 119 | 11 | "the initiator cannot ask for a wider tier" | holds | The offer is empty; the tier is the responder's configuration |
| 120 | 11 | "a resumed session carries the disclosure again" | holds | The platform payload is consulted on every handshake, resumed ones included (row 97) |
| 121 | 11 | "the responder sends EncryptedExtensions only in a flight it builds after the cookie has validated and the PSK binder has verified" | holds | In the server core's handshake path the platform payload is consulted after the binder verifies |
| 122 | 11 | "Riding the final handshake flight -- the pattern version 1 lifts from IKEv2's Configuration Payload (RFC 7296, Section 3.15)" | holds | RFC 7296 Section 3.15 is the Configuration Payload; v1 Section 20 and the code (`platformcard.py`) name the same lift |
| 123 | 12 | the 6 no-downgrade rules, collected | holds | Each maps to a mechanism verified above: `psk_ke` refusal (row 13), no carriage fallback in the code, the cleartext rule (row 108), session-bound results (row 114), fail-closed lanes (row 85), and no session-less trust path in the extension |
| 124 | 13 | a handshake-phase replay "re-posts the saved flight without re-entering the stack -- once per generation of that flight, and then it is dropped -- and an application-data replay is dropped" | holds | Rows 72 to 75 |
| 125 | 13 | "a replay that evades the cache meets the cookie exchange and the handshake state machine, which answer a retransmitted ClientHello with the flight it already produced and derive nothing twice" | holds | A retransmitted cookied ClientHello during the wait for Finished re-emits the saved server flight; nothing is derived a 2nd time |
| 126 | 13 | "Early data has no layer here at all ... this profile derives no epoch-1 keys for a replay to use" | holds | Row 17 |
| 127 | 13 | the citation: RFC 8446 "Sections 2.3 and 8, Appendix E.5" for the 0-RTT rejection rule | **draft-wrong -- corrected (F3)** | RFC 8446 is obsoleted by RFC 9846 (the recorded idnits error). In RFC 9846 the same material stands at Sections 2.3 (0-RTT Data) and 8 (0-RTT and Anti-Replay), and the replay appendix is F.5 (it was E.5 in 8446; 9846's Appendix E is Backward Compatibility). Citation and reference entry now name RFC 9846, Appendix F.5 |
| 128 | 13 | "A replayed record meets the record layer: sequence numbers and AEAD verification under RFC 9147 decide" | holds | The core's record layer, in both directions |
| 129 | 13 | "A replayed job meets the acceptance gate's seen-set: at most once, with the 2 priced windows version 1 documents (a crash between run and result, and the seen record ageing out), and no 3rd window is opened by this carriage" | holds-with-note | v1 Sections 15 and 17 document the windows in those terms (a result held before the seen record is written, and the seen record ageing or clearing). The carriage adds no execution path -- session jobs cross the same channel into the same gate -- so it opens no 3rd window |
| 130 | 13 | "Resumption tickets on this carriage MUST be single-use (Section 9.3); version 1's SHOULD stands for the datagram binding" | holds | Rows 94 and 96 |
| 131 | 14 | "A runner that polls its mailbox every 20 seconds completes a handshake in about 4 poll cycles when both sides are prompt" | holds-with-note | 20 seconds is the email extension's documented default poll interval; the cycle count is an operational estimate, not a protocol claim, and the live proofs completed at that order of latency |
| 132 | 14 | "an implementation SHOULD log session establishment, abandonment, and expiry, and the dropping of malformed flight mail ... It MUST NOT log session keys, ephemeral material, or the shared secret" | holds | The extension and cores log establishment, drops, and refusals; no log call in the carriage code carries key material (checked by grep over the log calls in `dtls_mailbox.py` and `dtlsproto.py`) |
| 133 | 15 | "This document requests no IANA action" | holds | The draft's own position, consistent throughout |
| 134 | 15 | "The platform_info extension's code point is version 1's IANA action, stated in version 1 Section 18: a value in the TLS ExtensionType Values registry, TBD there, with 0xFFA0 in interim private use" | holds | v1 -03 Section 18, read verbatim: the 1 IANA action, the registry, TBD, "0xFFA0 is Private Use ... and is not an assignment"; the code sends 0xFFA0 |
| 135 | 15 | "it does not request a 2nd value, a new registry, a port, a service name, a media type, or an OID" | holds | Nothing else in the draft requests anything |
| 136 | 15 | "The DTLS reference port 20220 remains version 1's local default for the datagram binding and is not used by this carriage" | holds | Row 20 |
| 137 | 15 | "The carriage's MIME content type (Section 5.2) is an unregistered name in the standards tree ... this document requests no media type registration for it" | holds | Row 40 |

### Section 16 -- security considerations

| # | Section | Statement | Verdict | Evidence |
|---|---|---|---|---|
| 138 | 16.1 | "a session's keys are derived from an ephemeral exchange performed fresh in that session's handshake ... combined with the pre-shared key, and are erased when the session ends" | holds | The key schedule and the session lifecycle in the core |
| 139 | 16.1 | recording every flight mail and later obtaining the shared secret "does not decrypt the session" | holds | A property of the profile (`psk_dhe_ke` only, ephemeral erased); the recorded-flight list in the draft matches the handshake's actual flights |
| 140 | 16.1 | compromise of the shared secret "permits impersonation in future handshakes and an active man-in-the-middle of a future session ... [and] reading ordinary version 1 mail jobs that rely on the object crypto" | holds | v1's own security considerations state the same of the object crypto |
| 141 | 16.1 | the bare-X25519 recorded-session limit: "a party that records a session's flights ... and that later breaks X25519 ... decrypts the recorded session without ever learning the shared secret" | holds | An accurate statement of the bare share's property; it is the stated reason the hybrid exists in the profile |
| 142 | 16.1 | "The remedy is the hybrid share of Section 4.4 ... it is part of this profile ... the reference implementation implements it, and a session on this carriage negotiates it whenever both endpoints offer it" | holds | Implemented on main (192fd424); the mail wrappers default the hybrid on at both ends, and negotiation requires both sides (rows 25 to 28) |
| 143 | 16.1 | "a later break of X25519 alone does not decrypt a hybrid session, and neither does a later break of ML-KEM alone; the recorded session falls only if both halves fall" | holds | The session secret is the ML-KEM secret and the X25519 secret together (row 26); either half alone leaves the other unknown |
| 144 | 16.2 | the mailbox and hops hold "the session's whole transcript in the clear at the DTLS-record layer: subjects, sizes, timing, counts, and the handshake's public values ... protected records are visible as ciphertext" | holds | Subjects and sizes are mail-visible by construction; protected records are AEAD ciphertext |
| 145 | 16.2 | "The provider cannot read application data, cannot forge a record that verifies, and cannot complete a handshake, not holding the shared secret" | holds | No secret is ever present at the provider; record AEAD and the PSK binder decide |
| 146 | 16.2 | "this document specifies no padding or cover traffic" | holds | No padding or cover-traffic code exists in the carriage (row 44) |
| 147 | 16.3 | "a flight mail that claims any `From` whatsoever is treated identically" | holds | The carriage path never reads `From`; dispatch is by subject, authentication by the handshake |
| 148 | 16.3 | "A deployment MUST NOT add a sender allowlist as a substitute gate on this carriage" | holds | Normative guidance, and true of the reference path: there is no sender allowlist anywhere in the mailbox fetch or the carriage (checked by grep) |
| 149 | 16.4 | "A fresh ClientHello costs the responder 1 HelloRetryRequest mail and no session state" | holds | Row 15 |
| 150 | 16.4 | "A bit-identical copy of a handshake-phase flight costs at most 1 re-post of the saved flight per generation of that flight" | holds | Rows 73 and 74 |
| 151 | 16.4 | "A flight mail is refused above the mail size cap before any decoding (Section 5.3)" | **code-wrong -- fixed in this pass** | The same defect as row 54, stated as a bound in this list; the fix makes it true of the implementation |
| 152 | 16.4 | "A reassembly slot is 1 of at most 64, bounded in total size, and held at most 3600 seconds from its first part and from its last; a contradiction destroys the transfer" | holds | Rows 60, 62, 63; total size is bounded by the datagram limit per transfer |
| 153 | 16.4 | "A digest-cache entry is 1 of 4096, first in first out (Section 7.2)" | **draft-wrong -- corrected (F5)** | The same eviction error as row 70, in this list; corrected with it |
| 154 | 16.4 | "A saved outbound flight is 1 of 4096, first in first out, the same bound as the digest cache" | holds | The server's saved-flight table is bounded at 4096 and evicts the least recently saved entry; a re-post does not refresh an entry's place (the digest cache's hit-refresh is the difference F5 records) |
| 155 | 16.4 | "A malformed flight is consumed in 1 pass and 1 log line, not re-offered on every poll" | holds-with-note | The substance is exact: consumption in a single pass, marked seen once. "1 log line" is the design's intent; most malformed shapes log exactly once at the point of refusal |
| 156 | 16.4 | "A fragmented or incomplete first handshake message is this case: it draws no HelloRetryRequest and no reassembly state (Section 8.2)" | holds-with-note | Row 82, including its note |
| 157 | 16.4 | "The unaddressed harness subject, on a deployment mailbox, is this case too: consumed, not fed to a DTLS stack, and worth no answer (Section 5.1)" | holds | Row 39 |
| 158 | 16.5 | "at no point does this carriage answer a failure by doing the same thing more weakly" | holds | No fallback path exists in the carriage code; every failure mode verified above ends in a drop or a refusal |
| 159 | 16.6 | "The acceptance gate -- signature, audience, caps, key policy, seen-set -- is what decides whether a job runs ... Carrying a job inside a session ... changes its admission not at all" | holds | Row 107 |
| 160 | 16.6 | "The constraint that narrows what a session may cause is the key policy of the key that signs the job ... The session does not widen that policy" | holds | Policy is applied by the gate to the job's own key; the session contributes no policy input (row 109) |

## Verdict summary

160 rows. **holds: 142. holds-with-note: 9** (rows 16, 46, 82, 98,
103, 129, 131, 155, 156). **draft-wrong: 4** (rows 56, 70, 127, 153).
**code-wrong: 2** (rows 54 and 151 -- the same defect stated in 2
places). **OPEN: 2** (rows 67, 68). **unverifiable-from-here: 1**
(row 35).

## Corrections applied to the draft

8 edits, all in `docs/ietf/draft-slutsky-homing-pigeon-v3-00.md`:

| Edit | Where | What changed |
|---|---|---|
| F1 | Abstract | The `{{I-D.slutsky-homing-pigeon}}` citation is gone; the sentence names version 1 in plain words. Fixes the recorded idnits error INVALID_ABSTRACT_SECTION_ID_REF |
| F2a | Abstract | "the frame header of Section 5.2" -> "the frame header this document defines". Fixes half of INVALID_ABSTRACT_SECTION_REF |
| F2b | Abstract | "requests no IANA action (Section 15)" -> "requests no IANA action." Fixes the other half |
| F3a | References | The RFC 8446 entry is replaced by RFC 9846 (same title and author; July 2026; DOI 10.17487/RFC9846). Fixes OBSOLETE_REFERENCE |
| F3b | Section 13 | The citations now name RFC 9846, and "Appendix E.5" -> "Appendix F.5" (in RFC 9846 the 0-RTT replay appendix is F.5; Sections 2.3 and 8 keep their numbers and subjects -- verified against the RFC's table of contents at rfc-editor.org) |
| F4 | Section 5.3 | "(8192 decoded octets at most per part" -> "(24576 decoded octets at most per part" (row 56) |
| F5a | Section 7.2 | "holds 4096 digests, first in first out" -> "holds 4096 digests, evicting the least recently seen (a hit refreshes an entry's place)" (row 70) |
| F5b | Section 16.4 | "A digest-cache entry is 1 of 4096, first in first out" -> "1 of 4096, the least recently seen evicted first" (row 153). The saved-flight sentence beside it keeps "first in first out": that table does evict in save order (row 154) |

## Code fix (rows 54 and 151): the mail size cap reaches flight mail

The draft's Section 5.3 rule -- the version 1 mail size cap applies
1st, before any decoding -- was true of job mail (the core applies
`max_job_bytes` when it takes mail in) but not of flight mail: the
email transport extension decoded the frame in `parse_message` with
no cap applied, because flight mail never reaches the core. The fix
is in the extension, in the lane that owns the mailbox
(`runner/transport_extensions/email/__main__.py`):

- `EmailPipe` now reads `max_job_bytes` the way the core reads it
  (an unusable value reads as the default 4194304; a cap of 0 means
  no limit, per version 1 Section 5).
- At the head of `pass_once`, a raw message that is flight mail by
  its subject alone (the Section 5.1 grammar, or the harness
  subject; no body is decoded to decide) and whose raw object
  exceeds the cap is consumed as malformed DTLS mail: marked seen,
  logged, dropped -- never decoded, never answered, never
  reinterpreted as a job. Ordinary job mail is untouched: the cap
  there remains the core's to apply.

Proof of work -- `runner/tests/test_dtls_email_v3_cap.py`, 5 tests,
written before the fix:

- Before the fix: `test_an_oversized_flight_mail_is_refused_before_decoding`
  FAILED (the oversized flight mail was answered with a
  HelloRetryRequest -- the defect, demonstrated), and
  `test_the_cap_decision_reads_the_subject_alone` errored (the seam
  did not exist). The at-cap and zero-cap tests passed (no cap
  existed to break), and the job-mail test reached `deliver_job`
  before erroring on this VM's write wall (below).
- After the fix: all 5 tests pass.
- Regression: the full `runner.tests.test_dtls_email_v3` with the
  fix in place runs 82 tests, OK. The neighboring suites that touch
  the email extension -- `test_email_pipe_coverage`,
  `test_email_uid_identity`, `test_extension_sources`,
  `test_doc_default_divergences` -- run 200 tests, OK.
- Environment note: this VM had an intermittent write denial active
  through the day (3-Nov). In a bad window the unmodified module's
  baseline here was 82 ran, 66 passed, 15 errors and 1 failure --
  every one in `EmailPipeIntegrationTest`, rooted in
  `PermissionError` on `os.write` inside `runner/guard/atomicio.py`,
  the environment and not the code (the same module recorded 82 OK,
  0 skips on 2-Nov, and ran 82 OK again in a healthy window with the
  fix in place). 1 of 6 post-fix runs of the new cap tests lost the
  job-mail test to the same wall; the other 5 runs were 5 of 5.

## OPEN rows

Both are in Section 7.1, and both are the same shape of question:
the paragraph recommends timer behavior for mailbox implementations
that the reference implementation's core does not itself follow.

- Row 67: "the initial retransmission interval SHOULD be at least 2
  of the implementation's mailbox poll periods." The core's first
  interval is 1.0 second whatever the poll period is; the mail
  drivers tick the core on their poll cadence, so the effective
  first retransmission lands about 1 poll period out.
- Row 68: "an attempt SHOULD be given up after about 8
  retransmissions." The core bounds the attempt by time, not count:
  retransmissions at +1, +3, +7, +15, +31, and +47 seconds (6), and
  the flight dies past 60 seconds.

The owner's call: stretch the timers in the mail wrappers (a code
change with its own test family), soften the paragraph's numbers,
or let both SHOULDs stand as guidance other implementations may
follow more literally. The text is unchanged.

### Disposition: the code was stretched (same day)

The call was the code change. Rows 67 and 68 are closed: the
draft text stands as written, and the reference implementation
now follows it on this carriage.

- `runner/wire/dtlsproto.py` gained
  `mail_retransmit_profile(poll_period_sec)`: a (first,
  max_interval, give_up_sec, max_retries) profile with first =
  2 poll periods, the intervals doubling (2, 4, 8 poll periods)
  and then holding at 8 poll periods, no wall-clock bound, and
  a give-up after 8 retransmissions. An attempt spans at most
  54 poll periods. Endpoints carry the profile per session;
  the module constants remain the datagram profile and are
  unchanged when no profile is applied.
- The mail wrappers (`DtlsMailServer`, `DtlsMailClient` in
  `runner/wire/dtls_mailbox.py`) take `poll_period_sec` and
  build the profile from it. The email transport hands the
  server the poll interval it actually polls at
  (`poll_interval_sec`, default 20 seconds), so the profile
  in force on a live runner is the draft's.
- As built, at a 10 second poll period a client's flight is
  retransmitted at +20, +60, +140, +220, +300, +380, +460 and
  +540 seconds, and the attempt dies at the 9th due time
  (+620) with no 9th retransmission. The server's flight
  follows the same schedule.
- One measurement correction to row 68's note: the core's gap
  arithmetic gives the datagram profile's retransmissions at
  +1, +3, +9, +25, +41 and +57 seconds, not the idealized
  doubling series the row recorded. The row's verdict is
  unaffected: 6 retransmissions, bounded by the 60 second
  clock, not by count.
- Tests: `runner/tests/test_dtls_mail_retransmit.py`, 14
  tests -- the profile's shape, the client and server
  schedules, the count give-up on both sides, the fresh-flight
  budget restart after a HelloRetryRequest, the datagram
  profile pinned unchanged without a poll period, a full
  handshake with the profile on, and the email transport's
  wiring of its configured and default poll intervals.

## Render and idnits

The corrected draft was re-rendered. 1 tooling note: the
kramdown-rfc binary was unavailable in this environment at render
time (its install in the tools cache had been pruned), so the
rendered `.xml` was patched at exactly the corrected sentences --
the same 8 edits, at the XML level -- and `.txt` / `.html` were
then produced from it by xml2rfc 3.35.0, the pipeline's own second
half. The `.md` is the source of truth; a full pipeline render at
submission time will regenerate the same text. xml2rfc reported
1 warning: the reference `I-D.slutsky-homing-pigeon` is now unused
in the body -- it was cited only from the abstract, which the
idnits fix required to be reference-free. The entry is retained
deliberately: version 1 is this document's normative base, and the
entry is wanted at submission time.

idnits 3.3.0 was re-run on the corrected renders (the refreshed
record is beside the draft). Result: **0 errors** -- all 3 recorded
errors (2 abstract references, RFC 8446 obsoleted by RFC 9846) are
gone. What remains is what stood before and is recorded here so it
is not mistaken for a regression: on the `.txt` run, 2 warnings
(the normative reference to the version 1 draft, a submission-time
matter for a delta document; and the `[HOMING-PIGEON]` bracket
notice, a false positive on the subject marker); on the `.xml`
run, the MISSING_BCP14_TAGS comments that kramdown's output has
always carried.

## Landing note

The review was worked against 99c672e1. By the time it landed, main
had advanced to 59677166 (release 3.15.148 and the ComChat tasking
entries); none of the files this review touches or cites as evidence
changed between the 2 heads, so the change set was re-parented onto
59677166 unchanged.
