# Findings — docs/infrastructure-documents/design/v3-dtls-over-email-plan.md

Source: docs/infrastructure-documents/design/v3-dtls-over-email-plan.md, reviewed at main 737df18f.
Sentence units: 168. Flagged: 0. Categories: pre-release 168, post-release 0.

The local build plan for DTLS over email, with its addendum: the seed sentence and the SS question it raised, the version 1 profile it builds on, the specification and code work it directs, the rules the build must preserve, the open questions and the defaults taken, and the done-conditions with their evidence. The plan reads in build order and the addendum closes each open question against the plan section that raised it; the done list at the end answers the condition list directly above it. 168 units, all sentences or list statements in 1 register. Nothing is flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "*Local build plan." | pre-release | flows |  |
| 2 | "The specification produced under this plan is a…" | pre-release | flows |  |
| 3 | "Nothing in this plan authorizes submission to the…" | pre-release | flows |  |
| 4 | "The seed is the owner-written entry in `docs/FUTURE.md`:" | pre-release | flows |  |
| 5 | "**ietf homing pigeon perfect forward secrecy v3** defines…" | pre-release | flows |  |
| 6 | "That sentence ends at `SS`." | pre-release | flows |  |
| 7 | "The question it raised is answered: `SS` is…" | pre-release | flows |  |
| 8 | "No part of the design had to guess…" | pre-release | flows |  |
| 9 | "Version 1 already defines a direct DTLS 1.3…" | pre-release | flows |  |
| 10 | "Its profile is narrow and remains the cryptographic…" | pre-release | flows |  |
| 11 | "DTLS 1.3 only." | pre-release | flows |  |
| 12 | "1 cipher suite: `TLS_AES_256_GCM_SHA384`." | pre-release | flows |  |
| 13 | "The shared secret is the external pre-shared key." | pre-release | flows |  |
| 14 | "`psk_dhe_ke` only; `psk_ke` is prohibited." | pre-release | flows |  |
| 15 | "An ephemeral X25519 key share rides every full…" | pre-release | flows |  |
| 16 | "The `platform_info` extension is offered empty in ClientHello…" | pre-release | flows |  |
| 17 | "Jobs inside a DTLS session still face the…" | pre-release | flows |  |
| 18 | "The missing piece is carriage." | pre-release | flows |  |
| 19 | "The version 1 DTLS binding needs a live…" | pre-release | flows |  |
| 20 | "Version 3 carries the same DTLS records over…" | pre-release | flows |  |
| 21 | "Produce `docs/ietf/draft-slutsky-homing-pigeon-v3-00.md`, modeled on the version 2 companion…" | pre-release | flows |  |
| 22 | "The document will define:" | pre-release | flows |  |
| 23 | "The email wire format for DTLS flights and…" | pre-release | flows |  |
| 24 | "A session identifier and per-message sequence sufficient to…" | pre-release | flows |  |
| 25 | "Segmentation of a DTLS datagram across email messages…" | pre-release | flows |  |
| 26 | "Retransmission behavior for a carrier that can delay,…" | pre-release | flows |  |
| 27 | "Recognition of the DTLS initialization flight by the…" | pre-release | flows |  |
| 28 | "Session establishment using the unmodified version 1 DTLS…" | pre-release | flows |  |
| 29 | "Carriage of ordinary version 1 job and result…" | pre-release | flows |  |
| 30 | "Platform disclosure in EncryptedExtensions on this carrier." | pre-release | flows |  |
| 31 | "Binding to the version 1 acceptance gate: HMAC…" | pre-release | flows |  |
| 32 | "No-downgrade rules: no fallback from an email DTLS…" | pre-release | flows |  |
| 33 | "Replay handling at the mail, handshake, record, and…" | pre-release | flows |  |
| 34 | "IANA considerations stating that this local draft requests…" | pre-release | flows |  |
| 35 | "Security considerations that state the forward-secrecy property and…" | pre-release | flows |  |
| 36 | "Expand the owner-written 1-line entry in `docs/FUTURE.md` into…" | pre-release | flows |  |
| 37 | "It will keep the owner's bold title words…" | pre-release | flows |  |
| 38 | "Grow `runner/wire/dtls_mailbox.py` from a local proof harness into…" | pre-release | flows |  |
| 39 | "The production mail flow is:" | pre-release | flows |  |
| 40 | "`runner/transport_extensions/email/__main__.py` owns the mailbox." | pre-release | flows |  |
| 41 | "It fetches unseen messages through `runner/wire/mailbox.py`." | pre-release | flows |  |
| 42 | "Ordinary jobs cross the transport channel as envelopes." | pre-release | flows |  |
| 43 | "The runner core processes a channel envelope through…" | pre-release | flows |  |
| 44 | "Results return through the channel and the email…" | pre-release | flows |  |
| 45 | "Version 3 inserts DTLS recognition into step 2…" | pre-release | flows |  |
| 46 | "A message whose subject matches the DTLS grammar…" | pre-release | flows |  |
| 47 | "A valid DTLS initialization or continuation flight goes…" | pre-release | flows |  |
| 48 | "Outgoing DTLS datagrams are posted back through SMTP…" | pre-release | flows |  |
| 49 | "Application data from an established session is unwrapped…" | pre-release | flows |  |
| 50 | "A result for a job known to have…" | pre-release | flows |  |
| 51 | "It is not sent as an ordinary email…" | pre-release | flows |  |
| 52 | "The client side will use the same carriage…" | pre-release | flows |  |
| 53 | "The DTLS session is a second gate, never…" | pre-release | flows |  |
| 54 | "The build will preserve these rules:" | pre-release | flows |  |
| 55 | "A completed handshake authenticates possession of the shared…" | pre-release | flows |  |
| 56 | "A job application message must contain the ordinary…" | pre-release | flows |  |
| 57 | "It reaches the existing core path and must…" | pre-release | flows |  |
| 58 | "A cleartext signed object inside a session remains…" | pre-release | flows |  |
| 59 | "Session establishment does not turn it into an…" | pre-release | flows |  |
| 60 | "Session keys derive from a fresh ephemeral X25519…" | pre-release | flows |  |
| 61 | "Long-term secret compromise must not decrypt a completed…" | pre-release | flows |  |
| 62 | "A DTLS-shaped message that is malformed, unauthenticated, replayed,…" | pre-release | flows |  |
| 63 | "Exact duplicate mail flights are suppressed by the…" | pre-release | flows |  |
| 64 | "Duplicate handshake messages are left to the DTLS…" | pre-release | flows |  |
| 65 | "Duplicate application records do not create a second…" | pre-release | flows |  |
| 66 | "Session state is bounded and expires." | pre-release | flows |  |
| 67 | "Store-and-forward delay does not create unbounded reassembly or…" | pre-release | flows |  |
| 68 | "Tests come before claims and, wherever behavior changes,…" | pre-release | flows |  |
| 69 | "The test family will cover:" | pre-release | flows |  |
| 70 | "Parser routing: DTLS initialization, DTLS continuation, ordinary job,…" | pre-release | flows |  |
| 71 | "Mailbox round trips over a fake mailbox shaped…" | pre-release | flows |  |
| 72 | "Result carriage back inside the same session." | pre-release | flows |  |
| 73 | "Negative cases: forged initialization, wrong-secret handshake, tampered flight,…" | pre-release | flows |  |
| 74 | "Segmentation and reassembly under loss, duplication, and reordering." | pre-release | flows |  |
| 75 | "A fuzz family for the new mail parser…" | pre-release | flows |  |
| 76 | "Inputs are wrapped at the front and back…" | pre-release | flows |  |
| 77 | "Registration of any new skip reason in `runner/tests/test_skip_registry.py`…" | pre-release | flows |  |
| 78 | "The default for this build is to add…" | pre-release | flows |  |
| 79 | "Add a proof note under `docs/proofs/` naming the…" | pre-release | flows |  |
| 80 | "`runner/wire/dtlsproto.py` already implements the required profile, including the…" | pre-release | flows |  |
| 81 | "Version 3 changes the carriage, not the session…" | pre-release | flows |  |
| 82 | "This avoids a second DTLS implementation and keeps…" | pre-release | flows |  |
| 83 | "Mail subjects and headers route work; they never…" | pre-release | flows |  |
| 84 | "The DTLS subject line will carry the kind,…" | pre-release | flows |  |
| 85 | "The datagram still has to parse and authenticate…" | pre-release | flows |  |
| 86 | "A spoofed subject can waste bounded parser work,…" | pre-release | flows |  |
| 87 | "The email extension is the only production process…" | pre-release | flows |  |
| 88 | "Version 3 therefore belongs beside that poll, not…" | pre-release | flows |  |
| 89 | "The DTLS-via-email server core runs in the email…" | pre-release | flows |  |
| 90 | "Established-session application data is converted back into the…" | pre-release | flows |  |
| 91 | "The core's `handle_mail` path remains the single place…" | pre-release | flows |  |
| 92 | "No DTLS module will parse job authority or…" | pre-release | flows |  |
| 93 | "The carriage will be controlled by a transport-email…" | pre-release | flows |  |
| 94 | "A present but unusable value follows the project's…" | pre-release | flows |  |
| 95 | "Enabling it hands the email extension the DTLS…" | pre-release | flows |  |
| 96 | "The DTLS core keys its stateless cookie and…" | pre-release | flows |  |
| 97 | "Email has no UDP address." | pre-release | flows |  |
| 98 | "The address the carriage uses is the string…" | pre-release | flows |  |
| 99 | "There is no configured peer identity in it,…" | pre-release | flows |  |
| 100 | "Mail headers remain untrusted routing data throughout." | pre-release | flows |  |
| 101 | "(This decision's first text claimed a configured mailbox…" | pre-release | flows |  |
| 102 | "The specification's Section 9.2 says the same." | pre-release | flows |  |
| 103 | "A DTLS datagram remains the unit the engine…" | pre-release | flows |  |
| 104 | "If it exceeds the configured mail-body limit, the…" | pre-release | flows |  |
| 105 | "Reassembly is bounded by count, total size, and…" | pre-release | flows |  |
| 106 | "Duplicate parts are idempotent." | pre-release | flows |  |
| 107 | "A mailbox poll or a sender retry can…" | pre-release | flows |  |
| 108 | "The carriage records a digest of each accepted…" | pre-release | flows |  |
| 109 | "The rule is split by phase (the review…" | pre-release | flows |  |
| 110 | "This is a carriage dedup rule, separate from…" | pre-release | flows |  |
| 111 | "It stops a replayed protected record from being…" | pre-release | flows |  |
| 112 | "The email extension will remember, for each job…" | pre-release | flows |  |
| 113 | "When the matching result appears in the channel…" | pre-release | flows |  |
| 114 | "If the session is gone, the result remains…" | pre-release | flows |  |
| 115 | "The pending hold is bounded (the review of…" | pre-release | flows |  |
| 116 | "An expired result is dropped and the expiry…" | pre-release | flows |  |
| 117 | "The suite supports 2 ways of reaching a…" | pre-release | flows |  |
| 118 | "The direct way is just DTLS, with no…" | pre-release | flows |  |
| 119 | "The way this plan builds is DTLS via…" | pre-release | flows |  |
| 120 | "The carriage's prose name is "DTLS via email"…" | pre-release | flows |  |
| 121 | "The seed line quoted at the top of…" | pre-release | flows |  |
| 122 | "This plan." | pre-release | flows |  |
| 123 | "Version 3 specification and the completed `future.md` entry." | pre-release | flows |  |
| 124 | "Parser and wire-format tests." | pre-release | flows |  |
| 125 | "Carriage state machine: classification, segmentation, reassembly, duplicate suppression,…" | pre-release | flows |  |
| 126 | "Email-extension integration and client-side send path." | pre-release | flows |  |
| 127 | "Core-gate round-trip tests using a real signed job." | pre-release | flows |  |
| 128 | "Negative, downgrade, replay, and cross-session tests." | pre-release | flows |  |
| 129 | "Parser fuzz family." | pre-release | flows |  |
| 130 | "Full touched-suite runs and the proof note." | pre-release | flows |  |
| 131 | "Each step landed as its own commit on…" | pre-release | flows |  |
| 132 | "The branch was pushed for review, then merged…" | pre-release | flows |  |
| 133 | "Nothing has been submitted to the IETF." | pre-release | flows |  |
| 134 | "(This paragraph's first text said the work sat…" | pre-release | flows |  |
| 135 | "It now says what happened." | pre-release | flows |  |
| 136 | "**What does `SS` mean in the seed line?**…" | pre-release | flows |  |
| 137 | "See the addendum." | pre-release | flows |  |
| 138 | "**Should resumption be allowed over email?** The default…" | pre-release | flows |  |
| 139 | "Disabling it is a configuration option if operational…" | pre-release | flows |  |
| 140 | "**What mail-size ceiling should a deployment use?** The…" | pre-release | flows |  |
| 141 | "The exact operational default can be revisited after…" | pre-release | flows |  |
| 142 | "Open question 1 is answered: `SS` is the…" | pre-release | flows |  |
| 143 | "It is the DTLS handshake's key in the…" | pre-release | flows |  |
| 144 | "One sentence belongs next to the expansion, because…" | pre-release | flows |  |
| 145 | "It authenticates the handshake; it does not encrypt…" | pre-release | flows |  |
| 146 | "Open questions 2 and 3 stand as defaults…" | pre-release | flows |  |
| 147 | "As built, the wire format of D7 is…" | pre-release | flows |  |
| 148 | "2 peer reviews (the forum entries of 2-Nov-2026,…" | pre-release | flows |  |
| 149 | "The wire format moved: the frame of D7…" | pre-release | flows |  |
| 150 | "D8's split and D9's bound and keying are…" | pre-release | flows |  |
| 151 | "Reassembly gained an absolute deadline from the first…" | pre-release | flows |  |
| 152 | "The engine now rejects a ClientHello that carries…" | pre-release | flows |  |
| 153 | "Mail fetches are BODY.PEEK fetches, so a decision…" | pre-release | flows |  |
| 154 | "The specification carries the same changes; the proof…" | pre-release | flows |  |
| 155 | "The build is done when all of the…" | pre-release | flows |  |
| 156 | "The plan, specification, and completed future entry are…" | pre-release | flows |  |
| 157 | "An email can open a DTLS session, further…" | pre-release | flows |  |
| 158 | "The result returns inside the session." | pre-release | flows |  |
| 159 | "The negative and fuzz families above pass." | pre-release | flows |  |
| 160 | "The proof note records only results read from…" | pre-release | flows |  |
| 161 | "Each condition above is established, with its evidence…" | pre-release | flows |  |
| 162 | "Present: this plan, `docs/ietf/draft-slutsky-homing-pigeon-v3-00.md` (local, unsubmitted), and the…" | pre-release | flows |  |
| 163 | "Session and job through the production path: the…" | pre-release | flows |  |
| 164 | "Result inside the session: verified in both the…" | pre-release | flows |  |
| 165 | "Negative and fuzz families: 45 tests in `runner/tests/test_dtls_email_v3.py`,…" | pre-release | flows |  |
| 166 | "Resumption under the fresh-share rule and the loss…" | pre-release | flows |  |
| 167 | "The proof note records only results read from…" | pre-release | flows |  |
| 168 | "What remains unproven is listed in the proof…" | pre-release | flows |  |
