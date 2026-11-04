# Findings — docs/infrastructure-documents/proofs/dtls-over-email-v3.md

Source: docs/infrastructure-documents/proofs/dtls-over-email-v3.md, reviewed at main 0bfaff40.
Sentence units: 162. Flagged: 1. Categories: pre-release 162, post-release 0.

The version 3 build record: what was built, the test families, the live mailbox run, what stayed unproven, the release determinations, 2 peer reviews with their verdicts, corrections to the record, recorded live runs, and the hybrid group. A chronological record whose sections hand the story along; review items are list entries and flow as such. 1 label stands alone.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Local branch `homing-pigeon-v3` (created as `together`, renamed 2-Nov-2026),…" | pre-release | flows |  |
| 2 | "The branch was pushed to GitHub for review,…" | pre-release | flows |  |
| 3 | "Nothing is submitted; the version 3 draft is…" | pre-release | flows |  |
| 4 | "Read the continuation and the review pass sections…" | pre-release | flows |  |
| 5 | "`docs/design/v3-dtls-over-email-plan.md` -- the plan: 6 goals, design decisions…" | pre-release | flows |  |
| 6 | "Its addendum records the resolution of the seed…" | pre-release | flows |  |
| 7 | "`docs/ietf/draft-slutsky-homing-pigeon-v3-00.md` -- the version 3 specification, 930 lines:…" | pre-release | flows |  |
| 8 | "`runner/wire/dtls_mailbox.py` -- grown from the 110-line local harness…" | pre-release | flows |  |
| 9 | "`DtlsMailServer` and `DtlsMailClient` wrap the unchanged engine in…" | pre-release | flows |  |
| 10 | "`runner/transport_extensions/email/__main__.py` -- with the `dtls_via_email` option on (literal…" | pre-release | flows |  |
| 11 | "There is no downgrade to an ordinary mail…" | pre-release | flows |  |
| 12 | "`runner/wire/transports.py` -- the email extension is handed the…" | pre-release | flows |  |
| 13 | "The security integration is structural: the core's acceptance…" | pre-release | flows |  |
| 14 | "`runner/tests/test_dtls_email_v3.py`, 26 tests, written before the carriage existed…" | pre-release | flows |  |
| 15 | "Parser routing: a ClientHello mail is `dtls-init`; a…" | pre-release | flows |  |
| 16 | "Segmentation: parts reassemble exactly out of order with…" | pre-release | flows |  |
| 17 | "Carriage round trips over mail tuples only: a…" | pre-release | flows |  |
| 18 | "The production path: over `EmailPipe` with a fake…" | pre-release | flows |  |
| 19 | "The negative family: a wrong-secret handshake never establishes…" | pre-release | flows |  |
| 20 | "The fuzz family, on the bookend doctrine: the…" | pre-release | flows |  |
| 21 | "Over 300 wrapped cases in the subject/body test…" | pre-release | flows |  |
| 22 | "The parser never raised, every answer was a…" | pre-release | flows |  |
| 23 | "`runner.tests.test_dtls_email_v3`: 26 tests, OK." | pre-release | flows |  |
| 24 | "Final combined run over every touched suite --…" | pre-release | flows |  |
| 25 | "The skip is pre-existing and registered; this build…" | pre-release | flows |  |
| 26 | "Commits at that point, on `together`: 714ab9e5 (plan),…" | pre-release | flows |  |
| 27 | "Commit 4cc16fe0, tests only -- no carriage code…" | pre-release | flows |  |
| 28 | "Resumption over mail (5 tests): a resumed handshake…" | pre-release | flows |  |
| 29 | "Resumption is also exercised end to end through…" | pre-release | flows |  |
| 30 | "Loss and provider shapes (12 tests): a lost…" | pre-release | flows |  |
| 31 | "Through the pipe, a footer-rewritten DTLS mail is…" | pre-release | flows |  |
| 32 | "1 finding the tests forced: an early version…" | pre-release | flows |  |
| 33 | "That is wrong: a retransmitted hello is not…" | pre-release | flows |  |
| 34 | "The case recovers, and the test pins the…" | pre-release | flows |  |
| 35 | "Results, as read from the runs: `runner.tests.test_dtls_email_v3`: 45…" | pre-release | flows |  |
| 36 | "Combined touched suites (the same 7 modules as…" | pre-release | flows |  |
| 37 | "No new skip reasons; the skip registry was…" | pre-release | flows |  |
| 38 | "A separate throwaway runner instance was stood up…" | pre-release | flows |  |
| 39 | "A client driver on this VM ran 1…" | pre-release | flows |  |
| 40 | "The handshake completed over real mail: ClientHello, HelloRetryRequest,…" | pre-release | flows |  |
| 41 | "The platform disclosure arrived in the handshake: the…" | pre-release | flows |  |
| 42 | "1 real signed and encrypted ping job (`v3-live-job-4`)…" | pre-release | flows |  |
| 43 | "The runner's log shows it delivered from a…" | pre-release | flows |  |
| 44 | "The throwaway instance was stopped afterwards." | pre-release | flows |  |
| 45 | "The standing runner was never touched." | pre-release | flows |  |
| 46 | "3 earlier attempts failed, and what stopped them…" | pre-release | flows |  |
| 47 | "Attempts 1 and 2 drove the client with…" | pre-release | flows |  |
| 48 | "Stale flight mail from earlier sessions in the…" | pre-release | flows |  |
| 49 | "The server failed closed in every case; nothing…" | pre-release | flows |  |
| 50 | "Attempt 3 filtered by mail session-id but fetched…" | pre-release | flows |  |
| 51 | "An RFC822 fetch sets the \Seen flag, so…" | pre-release | flows |  |
| 52 | "The working discipline, used by the successful run:…" | pre-release | flows |  |
| 53 | "Finding: on a shared mailbox, fetch semantics are…" | pre-release | flows |  |
| 54 | "A consumer that fetches DTLS mail with side…" | pre-release | flows |  |
| 55 | "Both failure modes fail closed; neither reaches the…" | pre-release | flows |  |
| 56 | "Resumption over a live mailbox: resumption is proven…" | pre-release | flows |  |
| 57 | "Provider rewriting beyond the tested shapes: the live…" | pre-release | flows |  |
| 58 | "The footer and subject-suffix cases remain synthetic, as…" | pre-release | flows |  |
| 59 | "Live scale: the live run carried 1 session…" | pre-release | flows |  |
| 60 | "Many sessions, many jobs, and multi-job sessions over…" | pre-release | flows |  |
| 61 | "The unaddressed legacy harness shape remains a local…" | pre-release | flows |  |
| 62 | "The 3.15.125 tag build failed on 2 assertions." | pre-release | flows |  |
| 63 | "Both were checked first-hand; the determinations are recorded…" | pre-release | flows |  |
| 64 | "Provider name in live docs." | pre-release | flagged | A heading-style label ("Provider name in live docs.") standing as its own paragraph; the determination it names arrives in the next unit with no hand-off |
| 65 | "The plan and this record named the mail…" | pre-release | flows |  |
| 66 | "Live docs name no provider; both files now…" | pre-release | flows |  |
| 67 | "The record is unchanged in substance: 1 live…" | pre-release | flows |  |
| 68 | "C20's transports pin (`test_c20_channel_envelopes_face_the _core_gate`)." | pre-release | flows |  |
| 69 | "The pin asserted that the first `_dtls_secret_material` hand-over…" | pre-release | flows |  |
| 70 | "The carriage added a second hand-over site inside…" | pre-release | flows |  |
| 71 | "Determination: a structural pin, not an ordering regression." | pre-release | flows |  |
| 72 | "The email site is guarded by `if cfg.get("dtls_via_email")…" | pre-release | flows |  |
| 73 | "No session envelope reaches the core gate by…" | pre-release | flows |  |
| 74 | "The pin now counts the hand-over sites (exactly…" | pre-release | flows |  |
| 75 | "2 peer reviews of this build were posted…" | pre-release | flows |  |
| 76 | "Every item was verified first-hand against the merged…" | pre-release | flows |  |
| 77 | "The forum entry of this date carries the…" | pre-release | flows |  |
| 78 | "Short review (5:38pm):" | pre-release | flows |  |
| 79 | "Section 9.2 / plan D6 overclaim: HELD." | pre-release | flows |  |
| 80 | "`_addr_for` builds `"email:" + (session_id or "legacy")`; no…" | pre-release | flows |  |
| 81 | "Section 9.2 and D6 rewritten to the code…" | pre-release | flows |  |
| 82 | "Duplicate split: HELD." | pre-release | flows |  |
| 83 | "The digest cache dropped every repeat in both…" | pre-release | flows |  |
| 84 | "Implemented: a handshake-phase digest hit re-posts the saved…" | pre-release | flows |  |
| 85 | "The connection-ID binding check already ran before the…" | pre-release | flows |  |
| 86 | "Absolute reassembly deadline: HELD." | pre-release | flows |  |
| 87 | "`offer` refreshed the idle stamp on every part." | pre-release | flows |  |
| 88 | "`created` + deadline added; a drip test pins…" | pre-release | flows |  |
| 89 | "Pending-result expiry: HELD, and the keying was weaker…" | pre-release | flows |  |
| 90 | "Keyed by (connection ID, job ident); expiry by…" | pre-release | flows |  |
| 91 | "MIME frame: JUDGMENT CALL, taken as the review…" | pre-release | flows |  |
| 92 | "Justification: fail-closed was a reaction to a broken…" | pre-release | flows |  |
| 93 | "The full-handshake-over-MIME test carries a signed job end…" | pre-release | flows |  |
| 94 | "Section 16.1 harvest limit and hybrid slot: HELD." | pre-release | flows |  |
| 95 | "The limit is stated; RFC 7748 is cited;…" | pre-release | flows |  |
| 96 | "Proof staleness: PARTLY SUPERSEDED at the review's read…" | pre-release | flows |  |
| 97 | "The suggested rebase was not followed: the build…" | pre-release | flows |  |
| 98 | "Full review (6:10pm), in its order:" | pre-release | flows |  |
| 99 | "Version 1 objects text: ACCEPTED (abstract, Section 10.1)." | pre-release | flows |  |
| 100 | "Title/docname rename: NOT LANDED -- the owner's call,…" | pre-release | flows |  |
| 101 | "The review's worry about `v: 3` does not…" | pre-release | flows |  |
| 102 | "Section 9.2 replacement: ACCEPTED; verified clause by clause…" | pre-release | flows |  |
| 103 | "MIME part: ACCEPTED (see the judgment call above)." | pre-release | flows |  |
| 104 | "Retransmission/duplicates: ACCEPTED." | pre-release | flows |  |
| 105 | ""Carrying the same datagram" deleted (RFC 9147 Section…" | pre-release | flows |  |
| 106 | "Section 16.1, the slogan, "2 ways", the firewall…" | pre-release | flows |  |
| 107 | "Minors: session-id ABNF ACCEPTED (the code already enforced…" | pre-release | flows |  |
| 108 | "Bounds: ACCEPTED (reassembly deadline, result expiry, digest cache…" | pre-release | flows |  |
| 109 | "References and rendering: ACCEPTED." | pre-release | flows |  |
| 110 | "RFC 5234, RFC 4648, RFC 7748, RFC 5322,…" | pre-release | flows |  |
| 111 | "`dtls_over_email` corrected to `dtls_via_email` (3 strings)." | pre-release | flows |  |
| 112 | "Rendered with kramdown-rfc 1.7.43 and xml2rfc 3.35.0: `.xml`,…" | pre-release | flows |  |
| 113 | "Discovery hint: PREPARED, NOT LANDED (forum entry carries…" | pre-release | flows |  |
| 114 | "Tests: `runner/tests/test_dtls_email_v3.py` grew from 45 to 62 tests;…" | pre-release | flows |  |
| 115 | "The release-gate batch (this record's constraints module, the…" | pre-release | flows |  |
| 116 | "Still unproven, unchanged from the continuation: resumption over…" | pre-release | flows |  |
| 117 | "A final adversarial review of the draft (protocol…" | pre-release | flows |  |
| 118 | "The forum entry of this date carries the…" | pre-release | flows |  |
| 119 | "Corrections to the record above:" | pre-release | flows |  |
| 120 | "The discovery hint is LANDED, not prepared: the…" | pre-release | flows |  |
| 121 | "The review-pass section's "PREPARED, NOT LANDED" line is…" | pre-release | flows |  |
| 122 | "Test counts: the module stood at 62 at…" | pre-release | flows |  |
| 123 | "Behavior changes in this pass:" | pre-release | flows |  |
| 124 | "The production sender's frame part is a leaf…" | pre-release | flows |  |
| 125 | "`build_flight_message` attached the frame as a whole message…" | pre-release | flows |  |
| 126 | "The receiver is unchanged and reads the wrapped…" | pre-release | flows |  |
| 127 | "Tests pin the leaf shape and a full…" | pre-release | flows |  |
| 128 | "A fragmented first ClientHello is refused by the…" | pre-release | flows |  |
| 129 | "The outcome is unchanged; the refusal now sits…" | pre-release | flows |  |
| 130 | "A test pins the parse kind and the…" | pre-release | flows |  |
| 131 | "The session-hold sidecar writes through the tree's one…" | pre-release | flows |  |
| 132 | "Verified, not changed:" | pre-release | flows |  |
| 133 | "The held-result fixes of 3.15.130 (a `<ident>.session.txt` sidecar…" | pre-release | flows |  |
| 134 | "The re-post budget and the cookie key kept…" | pre-release | flows |  |
| 135 | "Combination cells landed as tests: a gateway-shaped flight…" | pre-release | flows |  |
| 136 | "Still unproven, updated: resumption over a live mailbox,…" | pre-release | flows |  |
| 137 | "Resumption across a responder restart is not possible…" | pre-release | flows |  |
| 138 | "The exact flight mail of the 2 live…" | pre-release | flows |  |
| 139 | "The tests in `runner/tests/test_dtls_email_v3_live.py` replay the recorded mail…" | pre-release | flows |  |
| 140 | "The live runs are replayable offline from the…" | pre-release | flows |  |
| 141 | "The slot Section 16.1 named is now filled." | pre-release | flows |  |
| 142 | "X25519MLKEM768 (RFC 10024, group 4588) is implemented in…" | pre-release | flows |  |
| 143 | "What was built:" | pre-release | flows |  |
| 144 | "`runner/wire/mlkem.py`: ML-KEM-768 (FIPS 203) in pure Python, stdlib…" | pre-release | flows |  |
| 145 | "The engine (`runner/wire/dtlsproto.py`): group 4588 as a profile…" | pre-release | flows |  |
| 146 | "The carriage (`runner/wire/dtls_mailbox.py`) turns it on: DtlsMailClient offers…" | pre-release | flows |  |
| 147 | "The datagram binding's cores keep the default, so…" | pre-release | flows |  |
| 148 | "The layout is RFC 10024 sections 4.1 to…" | pre-release | flows |  |
| 149 | "The correctness gate, run before any integration: the…" | pre-release | flows |  |
| 150 | "Key generation from the recorded (d, z) seeds,…" | pre-release | flows |  |
| 151 | "One defect was found and fixed on the…" | pre-release | flows |  |
| 152 | "Negotiation and failure shapes are pinned in `runner.tests.test_dtls_hybrid`…" | pre-release | flows |  |
| 153 | "The carriage handshake is also driven segmented at…" | pre-release | flows |  |
| 154 | "Full DTLS-related runs on the finished tree, unfiltered:…" | pre-release | flows |  |
| 155 | "The version 3 carriage suite passes with the…" | pre-release | flows |  |
| 156 | "The draft re-renders with 0 warnings from xml2rfc;…" | pre-release | flows |  |
| 157 | "Honest limits:" | pre-release | flows |  |
| 158 | "The pure-Python ML-KEM is not constant-time -- its…" | pre-release | flows |  |
| 159 | "It is a correctness-first implementation for this profile's…" | pre-release | flows |  |
| 160 | "Cost, measured on this machine (means of short…" | pre-release | flows |  |
| 161 | "On this carriage, whose flights already take seconds…" | pre-release | flows |  |
| 162 | "Judgment calls, stated: the hybrid is offered by…" | pre-release | flows |  |
