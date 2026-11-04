# Findings — docs/infrastructure-documents/design/v3-sentence-review.md

Source: docs/infrastructure-documents/design/v3-sentence-review.md, reviewed at main cbb52068.
Sentence units: 293. Flagged: 11. Categories: pre-release 290, post-release 3.

The ledger's rows are entries; a row whose quoted statement or evidence runs past 1 sentence is split into consecutive units that belong to the same row. The document's framing, counts, fix narrative, and open-row sections are prose and read in order.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Date: 3-Nov-2026." | pre-release | flows |  |
| 2 | "Scope: `docs/ietf/draft-slutsky-homing-pigeon-v3-00.md` against the code on main at…" | pre-release | flows |  |
| 3 | "The draft stays local; nothing in this pass…" | pre-release | flows |  |
| 4 | "The draft was read in full and every…" | pre-release | flows |  |
| 5 | "Each row was settled against ground truth in…" | pre-release | flows |  |
| 6 | "Verdicts: **holds** (the statement is true as written;…" | pre-release | flows |  |
| 7 | "Settled decisions were not reopened: the title and…" | pre-release | flows |  |
| 8 | "The draft was written before the security-modes default…" | pre-release | flows |  |
| 9 | "Every occurrence of "default" in the draft was…" | pre-release | flows |  |
| 10 | "Draft occurrence ; What it is about ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 11 | "Introduction: "by default, per-job encryption" ; version 1…" | pre-release | flows |  |
| 12 | "Section 1.1: "the option is off by default"…" | pre-release | flows |  |
| 13 | "Section 4.1: "a local default of the datagram…" | pre-release | flows |  |
| 14 | "Section 5.3: "its default chunk is 32768 base64…" | pre-release | flows |  |
| 15 | "Section 7.1: "than its defaults" ; RFC 9147's…" | pre-release | flows |  |
| 16 | "Section 11: "family by default" ; the platform…" | pre-release | flows |  |
| 17 | "Section 15: "version 1's local default" ; UDP…" | pre-release | flows |  |
| 18 | ""enforce", "audit", "security mode", and "lockdown" do not…" | pre-release | flows |  |
| 19 | "No sentence in the draft states or depends…" | pre-release | flows |  |
| 20 | "The drift the owner suspected was real but…" | pre-release | flows |  |
| 21 | "# ; Section ; Statement (short quote) ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 22 | "1 ; Abstract ; "a transport extension to…" | pre-release | flows |  |
| 23 | "2 ; Abstract ; "Version 1 defines a…" | pre-release | flows |  |
| 24 | "3 ; Abstract ; "the 3 of this…" | pre-release | flows |  |
| 25 | "HP-DTLS/3 ... is a carriage label" ; holds…" | pre-release | flows |  |
| 26 | "4 ; Abstract ; "a local, unsubmitted draft…" | pre-release | flows |  |
| 27 | "5 ; Introduction ; "the object crypto of…" | pre-release | flows |  |
| 28 | "6 ; Introduction ; the 4 bullets mapping…" | pre-release | flows |  |
| 29 | "7 ; Introduction ; "A deployment MAY offer…" | pre-release | flows |  |
| 30 | "8 ; Section 1.1 ; "implemented and tested…" | pre-release | flows |  |
| 31 | "9 ; Section 2 ; the BCP 14…" | pre-release | flows |  |
| 32 | "10 ; Section 3 ; the 4 added…" | pre-release | flows |  |
| 33 | "# ; Section ; Statement ; Verdict ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 34 | "11 ; 4.1 ; "DTLS 1.3 is the…" | pre-release | flows |  |
| 35 | "The 1 cipher suite is TLS_AES_256_GCM_SHA384" ; holds…" | pre-release | flows |  |
| 36 | "12 ; 4.1 ; "The pre-shared key is…" | pre-release | flows |  |
| 37 | "13 ; 4.1 ; "Only the `psk_dhe_ke` key…" | pre-release | flows |  |
| 38 | "14 ; 4.1 ; "Every handshake, full or…" | pre-release | flows |  |
| 39 | "15 ; 4.1 ; "The responder is stateless…" | pre-release | flows |  |
| 40 | "16 ; 4.1 ; "Connection IDs are used…" | pre-release | flows |  |
| 41 | "The citation (RFC 9146) is version 1's own…" | pre-release | flows |  |
| 42 | "17 ; 4.1 ; "Early data is not…" | pre-release | flows |  |
| 43 | "A ClientHello that carries early data ..." | pre-release | flows |  |
| 44 | "MUST be rejected" ; holds ; A ClientHello…" | pre-release | flows |  |
| 45 | "18 ; 4.1 ; "The platform_info extension is…" | pre-release | flows |  |
| 46 | "19 ; 4.1 ; "Certificates are not part…" | pre-release | flows |  |
| 47 | "A ClientHello that offers no pre_shared_key extension is…" | pre-release | flows |  |
| 48 | "20 ; 4.1 ; "The UDP port 20220…" | pre-release | flows |  |
| 49 | "This carriage has no port" ; holds ;…" | pre-release | flows |  |
| 50 | "21 ; 4.2 ; the carriage changes only…" | pre-release | flows |  |
| 51 | "22 ; 4.3 ; "A runner enables it…" | pre-release | flows |  |
| 52 | "23 ; 4.3 ; "the shared secret is…" | pre-release | flows |  |
| 53 | "24 ; 4.3 ; "A platform card MAY…" | pre-release | flows |  |
| 54 | "Note: the reference card (`platformcard.build_card`) carries no carriage…" | pre-release | flows |  |
| 55 | "25 ; 4.4 ; "in the client share,…" | pre-release | flows |  |
| 56 | "26 ; 4.4 ; "a shared secret that…" | pre-release | flows |  |
| 57 | "27 ; 4.4 ; "A responder on this…" | pre-release | flows |  |
| 58 | "28 ; 4.4 ; "A responder that does…" | pre-release | flows |  |
| 59 | "29 ; 4.4 ; "The responder MUST perform…" | pre-release | flows |  |
| 60 | "30 ; 4.4 ; "A hybrid share of…" | pre-release | flows |  |
| 61 | "31 ; 4.4 ; the group is X25519MLKEM768…" | pre-release | flows |  |
| 62 | "# ; Section ; Statement ; Verdict ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 63 | "32 ; 5.1 ; the flight subject grammar…" | pre-release | flows |  |
| 64 | "33 ; 5.1 ; "session-id = 1*128 session-id-char…" | pre-release | flows |  |
| 65 | "34 ; 5.1 ; the alphabet "is an…" | pre-release | flows |  |
| 66 | "35 ; 5.1 ; "a future widening of…" | post-release | flows |  |
| 67 | "36 ; 5.1 ; "The mail session-id is…" | pre-release | flows |  |
| 68 | "37 ; 5.1 ; "A receiver MAY accept…" | pre-release | flows |  |
| 69 | "38 ; 5.1 ; "A receiver MUST NOT…" | pre-release | flows |  |
| 70 | "39 ; 5.1 ; the unaddressed harness shape…" | pre-release | flows |  |
| 71 | "40 ; 5.2 ; the frame's content type…" | pre-release | flows |  |
| 72 | "41 ; 5.2 ; the frame is "1…" | pre-release | flows |  |
| 73 | "42 ; 5.2 ; "`t` is the transfer…" | pre-release | flows |  |
| 74 | "43 ; 5.2 ; "`i` and `n` are…" | pre-release | flows |  |
| 75 | "An unsegmented datagram is part 0 of 1"…" | pre-release | flows |  |
| 76 | "44 ; 5.2 ; "`b` is the total…" | pre-release | flows |  |
| 77 | "45 ; 5.2 ; "`d` is the SHA-384…" | pre-release | flows |  |
| 78 | "46 ; 5.2 ; "Slices are cut on…" | pre-release | flows |  |
| 79 | "47 ; 5.2 ; "The digest ... is…" | pre-release | flows |  |
| 80 | "48 ; 5.2 ; "Text outside the part…" | pre-release | flows |  |
| 81 | "49 ; 5.2 ; "The part is a…" | pre-release | flows |  |
| 82 | "A sender MUST NOT wrap it in [a…" | pre-release | flows |  |
| 83 | "A receiver finds the frame part by its…" | pre-release | flows |  |
| 84 | "50 ; 5.2 ; "Base64 folding at 76…" | pre-release | flows |  |
| 85 | "51 ; 5.2 ; "Quoted-printable MUST NOT be…" | pre-release | flows |  |
| 86 | "52 ; 5.2 ; the naked shape: with…" | pre-release | flows |  |
| 87 | "53 ; 5.2 ; "When a typed part…" | pre-release | flows |  |
| 88 | "54 ; 5.3 ; "a receiver MUST refuse…" | pre-release | flows |  |
| 89 | "Fixed in the email extension (see "Code fix"…" | pre-release | flows |  |
| 90 | "A cap of 0 means no limit") and…" | pre-release | flows |  |
| 91 | "55 ; 5.3 ; "The reference implementation's limit…" | pre-release | flows |  |
| 92 | "56 ; 5.3 ; "its default chunk is…" | pre-release | flows |  |
| 93 | "The parenthetical now reads 24576" | pre-release | flows |  |
| 94 | "57 ; 5.3 ; "A part count MUST…" | pre-release | flows |  |
| 95 | "58 ; 6 ; "The receiver's reassembly state…" | pre-release | flows |  |
| 96 | "59 ; 6 ; "Parts MAY arrive in…" | pre-release | flows |  |
| 97 | "Duplicate parts are idempotent" ; holds ; Parts…" | pre-release | flows |  |
| 98 | "60 ; 6 ; "A part that contradicts…" | pre-release | flows |  |
| 99 | "61 ; 6 ; "A transfer completes when…" | pre-release | flows |  |
| 100 | "A completed datagram is delivered upward exactly once,…" | pre-release | flows |  |
| 101 | "62 ; 6 ; "the reference implementation holds…" | pre-release | flows |  |
| 102 | "63 ; 6 ; "a transfer [is kept]…" | pre-release | flows |  |
| 103 | "# ; Section ; Statement ; Verdict ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 104 | "64 ; 7.1 ; "The carriage defines no…" | pre-release | flows |  |
| 105 | "Retransmission is the DTLS handshake's" ; holds ;…" | pre-release | flows |  |
| 106 | "65 ; 7.1 ; "a flight's re-send is…" | pre-release | flows |  |
| 107 | "66 ; 7.1 ; "A sender SHOULD NOT…" | pre-release | flows |  |
| 108 | "67 ; 7.1 ; "the initial retransmission interval…" | pre-release | flows |  |
| 109 | "Whether the mail wrappers should stretch the core's…" | pre-release | flows |  |
| 110 | "68 ; 7.1 ; "an attempt SHOULD be…" | pre-release | flows |  |
| 111 | "The code bounds the attempt by time, the…" | pre-release | flows |  |
| 112 | "Same disposition as row 67" | pre-release | flows |  |
| 113 | "69 ; 7.2 ; "A receiver keeps a…" | pre-release | flows |  |
| 114 | "70 ; 7.2 ; "... first in first…" | pre-release | flows |  |
| 115 | "Corrected in Section 7.2 and in the Section…" | pre-release | flows |  |
| 116 | "71 ; 7.2 ; "The connection-id binding check…" | pre-release | flows |  |
| 117 | "72 ; 7.2 ; "A digest hit on…" | pre-release | flows |  |
| 118 | "73 ; 7.2 ; "a receiver MUST re-post…" | pre-release | flows |  |
| 119 | "74 ; 7.2 ; "A thousand copies of…" | pre-release | flows |  |
| 120 | "75 ; 7.2 ; "A digest hit on…" | pre-release | flows |  |
| 121 | "76 ; 7.2 ; a DTLS retransmission "is…" | pre-release | flows |  |
| 122 | "It misses this cache, enters the stack, and…" | pre-release | flows |  |
| 123 | "The budget does not limit it" ; holds…" | pre-release | flows |  |
| 124 | "77 ; 7.2 ; "A duplicate flight mail…" | pre-release | flows |  |
| 125 | "A duplicate part MUST NOT complete a transfer…" | pre-release | flows |  |
| 126 | "78 ; 7.3 ; "No ordering is assumed…" | pre-release | flows |  |
| 127 | "Application messages inside a session keep the session's…" | pre-release | flows |  |
| 128 | "# ; Section ; Statement ; Verdict ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 129 | "79 ; 8.1 ; the dispatch order: flight…" | pre-release | flows |  |
| 130 | "80 ; 8.1 ; "DTLS classification happens in…" | pre-release | flows |  |
| 131 | "The runner core -- the acceptance gate --…" | pre-release | flows |  |
| 132 | "81 ; 8.2 ; "A complete datagram is…" | pre-release | flows |  |
| 133 | "82 ; 8.2 ; "A fragmented or incomplete…" | pre-release | flows |  |
| 134 | "The "no reassembly state" is the DTLS-layer sense…" | pre-release | flows |  |
| 135 | "83 ; 8.2 ; "A complete datagram that…" | pre-release | flows |  |
| 136 | "84 ; 8.3 ; malformed flight mail "is…" | pre-release | flows |  |
| 137 | "85 ; 8.3 ; "An implementation MUST NOT…" | pre-release | flows |  |
| 138 | "86 ; 8.4 ; "A party MUST mark…" | pre-release | flows |  |
| 139 | "87 ; 8.4 ; "A fetch made to…" | pre-release | flows |  |
| 140 | "88 ; 8.4 ; "An initiator MUST ignore…" | pre-release | flows |  |
| 141 | "# ; Section ; Statement ; Verdict ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 142 | "89 ; 9.1 ; the 5 steps of…" | pre-release | flows |  |
| 143 | "90 ; 9.2 ; "The peer address on…" | pre-release | flows |  |
| 144 | "91 ; 9.2 ; "The cookie key is…" | pre-release | flows |  |
| 145 | "92 ; 9.2 ; "The PSK identity inside…" | pre-release | flows |  |
| 146 | "93 ; 9.2 ; "A protected record is…" | pre-release | flows |  |
| 147 | "A record whose connection ID is bound to…" | pre-release | flows |  |
| 148 | "94 ; 9.3 ; "tickets MAY be issued…" | pre-release | flows |  |
| 149 | "95 ; 9.3 ; "A replayed ticket MUST…" | pre-release | flows |  |
| 150 | "96 ; 9.3 ; "(Version 1's SHOULD for…" | pre-release | flows |  |
| 151 | "97 ; 9.3 ; "A resumed handshake is…" | pre-release | flows |  |
| 152 | "98 ; 9.3 ; "A deployment MAY disable…" | pre-release | flows |  |
| 153 | "The reference implementation offers no such switch: it…" | pre-release | flows |  |
| 154 | "The sentence permits the switch; it does not…" | pre-release | flows |  |
| 155 | "99 ; 9.4 ; "An attempt ... is…" | pre-release | flows |  |
| 156 | "100 ; 9.4 ; "A responder SHOULD keep…" | pre-release | flows |  |
| 157 | "The reference implementation keeps it beside the mailbox's…" | pre-release | flows |  |
| 158 | "101 ; 9.4 ; "A responder whose cookie…" | pre-release | flows |  |
| 159 | "Recovery is a fresh attempt under a new…" | pre-release | flows |  |
| 160 | "102 ; 9.4 ; "Established sessions do not…" | pre-release | flows |  |
| 161 | "103 ; 9.5 ; "an implementation MUST NOT…" | pre-release | flows |  |
| 162 | "Keys are erased with the session" ; holds-with-note…" | pre-release | flows |  |
| 163 | "The configured lifetime in the reference implementation is…" | pre-release | flows |  |
| 164 | "# ; Section ; Statement ; Verdict ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 165 | "104 ; 10.1 ; "a 4-octet big-endian length…" | pre-release | flows |  |
| 166 | "105 ; 10.1 ; "a completed application message…" | pre-release | flows |  |
| 167 | "The core cannot tell ... that the envelope…" | pre-release | flows |  |
| 168 | "106 ; 10.1 ; "A job inside a…" | pre-release | flows |  |
| 169 | "107 ; 10.2 ; "Completing a DTLS handshake…" | pre-release | flows |  |
| 170 | "A job carried inside a session is admitted…" | pre-release | flows |  |
| 171 | "108 ; 10.2 ; "a cleartext object inside…" | pre-release | flows |  |
| 172 | "109 ; 10.2 ; "The PSK identity that…" | pre-release | flows |  |
| 173 | "A job signed under 1 key MAY be…" | pre-release | flows |  |
| 174 | "110 ; 10.3 ; "The carriage remembers, for…" | pre-release | flows |  |
| 175 | "111 ; 10.3 ; "The hold is kept…" | pre-release | flows |  |
| 176 | "112 ; 10.3 ; a held result leaves…" | pre-release | flows |  |
| 177 | "113 ; 10.3 ; "A job whose ident…" | pre-release | flows |  |
| 178 | "114 ; 10.3 ; "A held result MUST…" | pre-release | flows |  |
| 179 | "115 ; 10.3 ; "A held result expires…" | pre-release | flows |  |
| 180 | "An expired result is dropped and the expiry…" | pre-release | flows |  |
| 181 | "116 ; 10.3 ; "The PSK identity distinguishes…" | pre-release | flows |  |
| 182 | "Two peers that authenticate with the same secret…" | pre-release | flows |  |
| 183 | "# ; Section ; Statement ; Verdict ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 184 | "117 ; 11 ; the disclosure mechanism as…" | pre-release | flows |  |
| 185 | "118 ; 11 ; "the tiers are version…" | pre-release | flows |  |
| 186 | "119 ; 11 ; "the initiator cannot ask…" | pre-release | flows |  |
| 187 | "120 ; 11 ; "a resumed session carries…" | pre-release | flows |  |
| 188 | "121 ; 11 ; "the responder sends EncryptedExtensions…" | pre-release | flows |  |
| 189 | "122 ; 11 ; "Riding the final handshake…" | pre-release | flows |  |
| 190 | "123 ; 12 ; the 6 no-downgrade rules,…" | pre-release | flows |  |
| 191 | "124 ; 13 ; a handshake-phase replay "re-posts…" | pre-release | flows |  |
| 192 | "125 ; 13 ; "a replay that evades…" | pre-release | flows |  |
| 193 | "126 ; 13 ; "Early data has no…" | pre-release | flows |  |
| 194 | "127 ; 13 ; the citation: RFC 8446…" | pre-release | flows |  |
| 195 | "In RFC 9846 the same material stands at…" | pre-release | flows |  |
| 196 | "Citation and reference entry now name RFC 9846,…" | pre-release | flows |  |
| 197 | "128 ; 13 ; "A replayed record meets…" | pre-release | flows |  |
| 198 | "129 ; 13 ; "A replayed job meets…" | pre-release | flows |  |
| 199 | "The carriage adds no execution path -- session…" | pre-release | flows |  |
| 200 | "130 ; 13 ; "Resumption tickets on this…" | pre-release | flows |  |
| 201 | "131 ; 14 ; "A runner that polls…" | pre-release | flows |  |
| 202 | "132 ; 14 ; "an implementation SHOULD log…" | pre-release | flows |  |
| 203 | "It MUST NOT log session keys, ephemeral material,…" | pre-release | flows |  |
| 204 | "133 ; 15 ; "This document requests no…" | pre-release | flows |  |
| 205 | "134 ; 15 ; "The platform_info extension's code…" | pre-release | flows |  |
| 206 | "135 ; 15 ; "it does not request…" | pre-release | flows |  |
| 207 | "136 ; 15 ; "The DTLS reference port…" | pre-release | flows |  |
| 208 | "137 ; 15 ; "The carriage's MIME content…" | pre-release | flows |  |
| 209 | "# ; Section ; Statement ; Verdict ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 210 | "138 ; 16.1 ; "a session's keys are…" | pre-release | flows |  |
| 211 | "139 ; 16.1 ; recording every flight mail…" | pre-release | flows |  |
| 212 | "140 ; 16.1 ; compromise of the shared…" | pre-release | flows |  |
| 213 | "141 ; 16.1 ; the bare-X25519 recorded-session limit:…" | pre-release | flows |  |
| 214 | "142 ; 16.1 ; "The remedy is the…" | pre-release | flows |  |
| 215 | "143 ; 16.1 ; "a later break of…" | pre-release | flows |  |
| 216 | "144 ; 16.2 ; the mailbox and hops…" | pre-release | flows |  |
| 217 | "145 ; 16.2 ; "The provider cannot read…" | pre-release | flows |  |
| 218 | "146 ; 16.2 ; "this document specifies no…" | pre-release | flows |  |
| 219 | "147 ; 16.3 ; "a flight mail that…" | pre-release | flows |  |
| 220 | "148 ; 16.3 ; "A deployment MUST NOT…" | pre-release | flows |  |
| 221 | "149 ; 16.4 ; "A fresh ClientHello costs…" | pre-release | flows |  |
| 222 | "150 ; 16.4 ; "A bit-identical copy of…" | pre-release | flows |  |
| 223 | "151 ; 16.4 ; "A flight mail is…" | pre-release | flows |  |
| 224 | "152 ; 16.4 ; "A reassembly slot is…" | pre-release | flows |  |
| 225 | "153 ; 16.4 ; "A digest-cache entry is…" | pre-release | flows |  |
| 226 | "154 ; 16.4 ; "A saved outbound flight…" | pre-release | flows |  |
| 227 | "155 ; 16.4 ; "A malformed flight is…" | pre-release | flows |  |
| 228 | ""1 log line" is the design's intent; most…" | pre-release | flows |  |
| 229 | "156 ; 16.4 ; "A fragmented or incomplete…" | pre-release | flows |  |
| 230 | "157 ; 16.4 ; "The unaddressed harness subject,…" | pre-release | flows |  |
| 231 | "158 ; 16.5 ; "at no point does…" | pre-release | flows |  |
| 232 | "159 ; 16.6 ; "The acceptance gate --…" | pre-release | flows |  |
| 233 | "Carrying a job inside a session ... changes…" | pre-release | flows |  |
| 234 | "160 ; 16.6 ; "The constraint that narrows…" | pre-release | flows |  |
| 235 | "The session does not widen that policy" ;…" | pre-release | flows |  |
| 236 | "160 rows. **holds: 142. holds-with-note: 9** (rows 16,…" | pre-release | flows |  |
| 237 | "8 edits, all in `docs/ietf/draft-slutsky-homing-pigeon-v3-00.md`:" | pre-release | flows |  |
| 238 | "Edit ; Where ; What changed" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 239 | "F1 ; Abstract ; The `{{I-D.slutsky-homing-pigeon}}` citation is…" | pre-release | flows |  |
| 240 | "Fixes the recorded idnits error INVALID_ABSTRACT_SECTION_ID_REF" | pre-release | flows |  |
| 241 | "F2a ; Abstract ; "the frame header of…" | pre-release | flows |  |
| 242 | "Fixes half of INVALID_ABSTRACT_SECTION_REF" | pre-release | flows |  |
| 243 | "F2b ; Abstract ; "requests no IANA action…" | pre-release | flows |  |
| 244 | "Fixes the other half" | pre-release | flows |  |
| 245 | "F3a ; References ; The RFC 8446 entry…" | pre-release | flows |  |
| 246 | "Fixes OBSOLETE_REFERENCE" | pre-release | flows |  |
| 247 | "F3b ; Section 13 ; The citations now…" | pre-release | flows |  |
| 248 | "F4 ; Section 5.3 ; "(8192 decoded octets…" | pre-release | flows |  |
| 249 | "F5a ; Section 7.2 ; "holds 4096 digests,…" | pre-release | flows |  |
| 250 | "F5b ; Section 16.4 ; "A digest-cache entry…" | pre-release | flows |  |
| 251 | "The saved-flight sentence beside it keeps "first in…" | pre-release | flows |  |
| 252 | "The draft's Section 5.3 rule -- the version…" | pre-release | flows |  |
| 253 | "The fix is in the extension, in the…" | pre-release | flows |  |
| 254 | "`EmailPipe` now reads `max_job_bytes` the way the core…" | pre-release | flows |  |
| 255 | "At the head of `pass_once`, a raw message…" | pre-release | flows |  |
| 256 | "Ordinary job mail is untouched: the cap there…" | pre-release | flows |  |
| 257 | "Proof of work -- `runner/tests/test_dtls_email_v3_cap.py`, 5 tests, written…" | pre-release | flows |  |
| 258 | "Before the fix: `test_an_oversized_flight_mail_is_refused_before_decoding` FAILED (the oversized flight…" | pre-release | flows |  |
| 259 | "The at-cap and zero-cap tests passed (no cap…" | pre-release | flows |  |
| 260 | "After the fix: all 5 tests pass." | pre-release | flows |  |
| 261 | "Regression: the full `runner.tests.test_dtls_email_v3` with the fix in…" | pre-release | flows |  |
| 262 | "The neighboring suites that touch the email extension…" | pre-release | flows |  |
| 263 | "Environment note: this VM had an intermittent write…" | pre-release | flows |  |
| 264 | "In a bad window the unmodified module's baseline…" | pre-release | flows |  |
| 265 | "1 of 6 post-fix runs of the new…" | pre-release | flows |  |
| 266 | "Both are in Section 7.1, and both are…" | pre-release | flows |  |
| 267 | "Row 67: "the initial retransmission interval SHOULD be…" | pre-release | flows |  |
| 268 | "The core's first interval is 1.0 second whatever…" | pre-release | flows |  |
| 269 | "Row 68: "an attempt SHOULD be given up…" | pre-release | flows |  |
| 270 | "The core bounds the attempt by time, not…" | pre-release | flows |  |
| 271 | "The owner's call: stretch the timers in the…" | pre-release | flows |  |
| 272 | "The text is unchanged." | pre-release | flows |  |
| 273 | "The call was the code change." | pre-release | flows |  |
| 274 | "Rows 67 and 68 are closed: the draft…" | pre-release | flows |  |
| 275 | "`runner/wire/dtlsproto.py` gained `mail_retransmit_profile(poll_period_sec)`: a (first, max_interval, give_up_sec, max_retries)…" | pre-release | flows |  |
| 276 | "An attempt spans at most 54 poll periods." | pre-release | flows |  |
| 277 | "Endpoints carry the profile per session; the module…" | pre-release | flows |  |
| 278 | "The mail wrappers (`DtlsMailServer`, `DtlsMailClient` in `runner/wire/dtls_mailbox.py`) take…" | pre-release | flows |  |
| 279 | "The email transport hands the server the poll…" | pre-release | flows |  |
| 280 | "As built, at a 10 second poll period…" | pre-release | flows |  |
| 281 | "The server's flight follows the same schedule." | pre-release | flows |  |
| 282 | "One measurement correction to row 68's note: the…" | pre-release | flows |  |
| 283 | "The row's verdict is unaffected: 6 retransmissions, bounded…" | pre-release | flows |  |
| 284 | "Tests: `runner/tests/test_dtls_mail_retransmit.py`, 14 tests -- the profile's shape,…" | pre-release | flows |  |
| 285 | "The corrected draft was re-rendered." | pre-release | flows |  |
| 286 | "1 tooling note: the kramdown-rfc binary was unavailable…" | pre-release | flows |  |
| 287 | "The `.md` is the source of truth; a…" | post-release | flows |  |
| 288 | "The entry is retained deliberately: version 1 is…" | post-release | flows |  |
| 289 | "idnits 3.3.0 was re-run on the corrected renders…" | pre-release | flows |  |
| 290 | "Result: **0 errors** -- all 3 recorded errors…" | pre-release | flows |  |
| 291 | "What remains is what stood before and is…" | pre-release | flows |  |
| 292 | "The review was worked against 99c672e1." | pre-release | flows |  |
| 293 | "By the time it landed, main had advanced…" | pre-release | flows |  |
