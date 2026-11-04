# Findings — docs/ietf/draft-slutsky-homing-pigeon-v3/source/draft-slutsky-homing-pigeon-v3-00.md

Source: docs/ietf/draft-slutsky-homing-pigeon-v3/source/draft-slutsky-homing-pigeon-v3-00.md, reviewed at main cbb52068.
Sentence units: 446. Flagged: 36. Categories: pre-release 445, post-release 1.

This document is an Internet-Draft in kramdown source form. The front matter (units 2-74) is one YAML metadata block of title and reference records; the figures and examples in tilde-fenced blocks (the flight subject, the ABNF, the frame header line) are each a single figure recorded in order, and the definition-list entries at units 111-116 lead with their term and complete in the same unit or the next.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "(horizontal rule)" | pre-release | flagged | Horizontal rule standing alone; structure, not a sentence |
| 2 | "title: "Homing Pigeon Message Protocol, Version 3: DTLS…" | pre-release | flows |  |
| 3 | "ins: "A." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 4 | "Slutsky" name: "Andrew Slutsky" organization: "Independent" email: "slutsky5544@gmail.com"" | pre-release | flows |  |
| 5 | "normative: I-D.slutsky-homing-pigeon: title: "Homing Pigeon Message Protocol, Version…" | pre-release | flows |  |
| 6 | "name: "Andrew Slutsky" ins: "A." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 7 | "Slutsky" date: 2026-11 seriesinfo: Internet-Draft: draft-slutsky-homing-pigeon-03 RFC2119: title:…" | pre-release | flows |  |
| 8 | "name: "S." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 9 | "Bradner" date: 1997-03 seriesinfo: RFC: 2119 DOI: 10.17487/RFC2119…" | pre-release | flows |  |
| 10 | "name: "B." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 11 | "Leiba" date: 2017-05 seriesinfo: RFC: 8174 DOI: 10.17487/RFC8174…" | pre-release | flows |  |
| 12 | "name: "E." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 13 | "Rescorla" date: 2026-07 seriesinfo: RFC: 9846 DOI: 10.17487/RFC9846…" | pre-release | flows |  |
| 14 | "name: "D." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 15 | "Crocker"" | pre-release | flows |  |
| 16 | "name: "P." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 17 | "Overell" date: 2008-01 seriesinfo: RFC: 5234 DOI: 10.17487/RFC5234…" | pre-release | flows |  |
| 18 | "name: "S." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 19 | "Josefsson" date: 2006-10 seriesinfo: RFC: 4648 DOI: 10.17487/RFC4648…" | pre-release | flows |  |
| 20 | "name: "A." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 21 | "Langley"" | pre-release | flows |  |
| 22 | "name: "M." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 23 | "Hamburg"" | pre-release | flows |  |
| 24 | "name: "S." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 25 | "Turner" date: 2016-01 seriesinfo: RFC: 7748 DOI: 10.17487/RFC7748…" | pre-release | flows |  |
| 26 | "name: "E." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 27 | "Rescorla"" | pre-release | flows |  |
| 28 | "name: "H." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 29 | "Tschofenig"" | pre-release | flows |  |
| 30 | "name: "T." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 31 | "Fossati"" | pre-release | flows |  |
| 32 | "name: "A." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 33 | "Kraus" date: 2022-03 seriesinfo: RFC: 9146 DOI: 10.17487/RFC9146…" | pre-release | flows |  |
| 34 | "name: "E." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 35 | "Rescorla"" | pre-release | flows |  |
| 36 | "name: "H." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 37 | "Tschofenig"" | pre-release | flows |  |
| 38 | "name: "N." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 39 | "Modadugu" date: 2022-04 seriesinfo: RFC: 9147 DOI: 10.17487/RFC9147…" | pre-release | flows |  |
| 40 | "informative: RFC5322: title: "Internet Message Format" author:" | pre-release | flows |  |
| 41 | "name: "P." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 42 | "Resnick" date: 2008-10 seriesinfo: RFC: 5322 DOI: 10.17487/RFC5322…" | pre-release | flows |  |
| 43 | "name: "B." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 44 | "Ramsdell"" | pre-release | flows |  |
| 45 | "name: "S." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 46 | "Turner" date: 2019-04 seriesinfo: RFC: 8551 DOI: 10.17487/RFC8551…" | pre-release | flows |  |
| 47 | "name: "A." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 48 | "Melnikov"" | pre-release | flows |  |
| 49 | "name: "B." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 50 | "Leiba" date: 2021-08 seriesinfo: RFC: 9051 DOI: 10.17487/RFC9051…" | pre-release | flows |  |
| 51 | "name: "K." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 52 | "Kwiatkowski"" | pre-release | flows |  |
| 53 | "name: "P." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 54 | "Kampanakis"" | pre-release | flows |  |
| 55 | "name: "B." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 56 | "Westerbaan"" | pre-release | flows |  |
| 57 | "name: "D." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 58 | "Stebila" date: 2026-08 seriesinfo: RFC: 10024 DOI: 10.17487/RFC10024…" | pre-release | flows |  |
| 59 | "name: "C." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 60 | "Kaufman"" | pre-release | flows |  |
| 61 | "name: "P." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 62 | "Hoffman"" | pre-release | flows |  |
| 63 | "name: "Y." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 64 | "Nir"" | pre-release | flows |  |
| 65 | "name: "P." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 66 | "Eronen"" | pre-release | flows |  |
| 67 | "name: "T." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 68 | "Kivinen" date: 2014-10 seriesinfo: RFC: 7296 DOI: 10.17487/RFC7296…" | pre-release | flows |  |
| 69 | "name: "Y." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 70 | "Sheffer"" | pre-release | flows |  |
| 71 | "name: "P." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 72 | "Saint-Andre"" | pre-release | flows |  |
| 73 | "name: "T." | pre-release | flagged | Fragment of an author name record in the YAML front matter, split mid-name by the source formatting; the record completes in the next unit |
| 74 | "Fossati" date: 2022-11 seriesinfo: RFC: 9325 DOI: 10.17487/RFC9325…" | pre-release | flows |  |
| 75 | "--- abstract" | pre-release | flows |  |
| 76 | "This document specifies version 3 of the Homing…" | pre-release | flows |  |
| 77 | "Version 3 is a transport extension to version…" | pre-release | flows |  |
| 78 | "Version 1 defines a DTLS 1.3 session profile…" | pre-release | flows |  |
| 79 | "Version 1 binds that profile to a live…" | pre-release | flows |  |
| 80 | "This document binds the same profile to the…" | pre-release | flows |  |
| 81 | "The objects carried inside the session remain version…" | pre-release | flows |  |
| 82 | "The 3 of this document's title numbers this…" | pre-release | flows |  |
| 83 | "HP-DTLS/3, the frame header this document defines, is…" | pre-release | flows |  |
| 84 | "This document is a local, unsubmitted draft." | pre-release | flows |  |
| 85 | "It has not been posted to the Internet-Drafts…" | pre-release | flows |  |
| 86 | "--- middle" | pre-release | flows |  |
| 87 | "Version 1's email binding is store-and-forward: a job…" | pre-release | flows |  |
| 88 | "Version 1's DTLS binding is the opposite shape:…" | pre-release | flows |  |
| 89 | "Each binding gives up what the other has." | pre-release | flows |  |
| 90 | "The email binding carries a job anywhere mail…" | pre-release | flows |  |
| 91 | "The DTLS binding provides forward secrecy, because its…" | pre-release | flows |  |
| 92 | "Version 3 carries the version 1 DTLS profile,…" | pre-release | flows |  |
| 93 | "What it removes is the confidentiality side of…" | pre-release | flows |  |
| 94 | "What it does not remove is the rest…" | pre-release | flows |  |
| 95 | "A DTLS handshake flight is carried as 1…" | pre-release | flows |  |
| 96 | "The receiver's mailbox parser recognizes a DTLS initialization…" | pre-release | flows |  |
| 97 | "Once the session is established, jobs and results…" | pre-release | flows |  |
| 98 | "The platform disclosure rides the handshake on this…" | pre-release | flows |  |
| 99 | "Nothing else in version 1 changes." | pre-release | flows |  |
| 100 | "The deltas in this document are stated as…" | pre-release | flows |  |
| 101 | "The same profile therefore runs on 2 bindings,…" | pre-release | flows |  |
| 102 | "On the version 1 datagram binding it is…" | pre-release | flows |  |
| 103 | "On this document's binding it is DTLS via…" | pre-release | flows |  |
| 104 | "A deployment MAY offer either binding, or both;…" | pre-release | flows |  |
| 105 | "This is a local working draft, revision -00,…" | pre-release | flows |  |
| 106 | "It is not an Internet-Draft of record: it…" | pre-release | flows |  |
| 107 | "The carriage this document specifies is implemented and…" | pre-release | flows |  |
| 108 | "The key words "MUST", "MUST NOT", "REQUIRED", "SHALL",…" | pre-release | flows |  |
| 109 | "The terms of version 1 apply: the runner,…" | pre-release | flows |  |
| 110 | "This document adds:" | pre-release | flows |  |
| 111 | "flight mail: : 1 email message carrying all…" | pre-release | flows |  |
| 112 | "mail session-id: : the identifier in a flight…" | pre-release | flows |  |
| 113 | "It is a routing label chosen by the…" | pre-release | flows |  |
| 114 | "It is not a credential, not a DTLS…" | pre-release | flows |  |
| 115 | "transfer: : the set of flight mails that…" | pre-release | flows |  |
| 116 | "carriage: : the rules of Sections 5 to…" | pre-release | flows |  |
| 117 | "The session profile of version 1 Sections 19…" | pre-release | flows |  |
| 118 | "In particular:" | pre-release | flows |  |
| 119 | "DTLS 1.3 {{RFC9147}} is the session protocol." | pre-release | flows |  |
| 120 | "The 1 cipher suite is TLS_AES_256_GCM_SHA384." | pre-release | flows |  |
| 121 | "The pre-shared key is the shared secret of…" | pre-release | flows |  |
| 122 | "The shared secret is an authenticator and only…" | pre-release | flows |  |
| 123 | "There is no second secret and no new…" | pre-release | flows |  |
| 124 | "Only the `psk_dhe_ke` key exchange mode is used.…" | pre-release | flows |  |
| 125 | "Every handshake, full or resumed, carries a fresh…" | pre-release | flows |  |
| 126 | "This is the rule the perfect forward secrecy…" | pre-release | flows |  |
| 127 | "The responder is stateless until a HelloRetryRequest cookie…" | pre-release | flows |  |
| 128 | "Connection IDs {{RFC9146}} are used in both directions." | pre-release | flows |  |
| 129 | "Early data is not used; there is no…" | pre-release | flows |  |
| 130 | "A ClientHello that carries early data is a…" | pre-release | flows |  |
| 131 | "The platform_info extension is offered empty in the…" | pre-release | flows |  |
| 132 | "Certificates are not part of this profile, in…" | pre-release | flows |  |
| 133 | "Nothing in this document adds a certificate path…" | pre-release | flows |  |
| 134 | "A ClientHello that offers no pre_shared_key extension is…" | pre-release | flows |  |
| 135 | "The UDP port 20220 of version 1 is…" | pre-release | flows |  |
| 136 | "This carriage has no port: its addresses are…" | pre-release | flows |  |
| 137 | "The carriage changes the unit of transport." | pre-release | flows |  |
| 138 | "DTLS is written for datagrams that arrive whole,…" | pre-release | flows |  |
| 139 | "Mail arrives whole per message, in no guaranteed…" | pre-release | flows |  |
| 140 | "Sections 5 to 9 exist to bridge exactly…" | pre-release | flows |  |
| 141 | "The carriage does not change the cryptography, the…" | pre-release | flows |  |
| 142 | "An implementation MUST NOT use this carriage as…" | pre-release | flows |  |
| 143 | "This carriage is opt-in." | pre-release | flows |  |
| 144 | "A runner enables it by explicit configuration (in…" | pre-release | flows |  |
| 145 | "A runner that has not enabled it treats…" | pre-release | flows |  |
| 146 | "A submitter discovers the carriage the way it…" | pre-release | flows |  |
| 147 | "There is no negotiation message, and a failed…" | pre-release | flows |  |
| 148 | "A platform card MAY state, as an unauthenticated…" | pre-release | flows |  |
| 149 | "The fact is trusted for nothing except whether…" | pre-release | flows |  |
| 150 | "It grants nothing." | pre-release | flows |  |
| 151 | "Admission remains the handshake's and the acceptance gate's…" | pre-release | flows |  |
| 152 | "The one delta this document states against the…" | pre-release | flows |  |
| 153 | "On this carriage, a client offers, beside the…" | pre-release | flows |  |
| 154 | "A responder on this carriage that is offered…" | pre-release | flows |  |
| 155 | "A responder that does not implement this section…" | pre-release | flows |  |
| 156 | "The hybrid rides under the same `psk_dhe_ke` rule:…" | pre-release | flows |  |
| 157 | "The home of the group is this carriage's…" | pre-release | flows |  |
| 158 | "The responder MUST perform the encapsulation-key check of…" | pre-release | flows |  |
| 159 | "A hybrid share of any size other than…" | pre-release | flows |  |
| 160 | "What the hybrid buys is stated in Section…" | pre-release | flows |  |
| 161 | "It changes nothing else in this document: not…" | pre-release | flows |  |
| 162 | "Flight mail is recognized by its subject, under…" | pre-release | flows |  |
| 163 | "The flight subject is:" | pre-release | flows |  |
| 164 | "~~~ [HOMING-PIGEON] dtls ~~~" | pre-release | flows |  |
| 165 | "In ABNF {{RFC5234}}, with the separator set as…" | pre-release | flows |  |
| 166 | "~~~ flight-subject = "[HOMING-PIGEON]" 1*gap "dtls" 1*gap session-id…" | pre-release | flows |  |
| 167 | "The session-id alphabet is stated here in full…" | pre-release | flows |  |
| 168 | "The mail session-id is chosen by the initiator,…" | pre-release | flows |  |
| 169 | "The responder answers flight mail for an attempt…" | pre-release | flows |  |
| 170 | "A mail user agent that replies to flight…" | pre-release | flows |  |
| 171 | "A receiver MAY accept at most 1 leading…" | pre-release | flows |  |
| 172 | "A chain of prefixes, or any other text…" | pre-release | flows |  |
| 173 | "The prefixes are mail user agent convention, not…" | pre-release | flows |  |
| 174 | "The acceptance rule here is this carriage's own,…" | pre-release | flows |  |
| 175 | "Subjects route; they never authenticate." | pre-release | flows |  |
| 176 | "A receiver MUST NOT treat a flight subject,…" | pre-release | flows |  |
| 177 | "Authentication is the DTLS handshake's, applied to the…" | pre-release | flows |  |
| 178 | "An implementation MAY also accept the unaddressed harness…" | pre-release | flows |  |
| 179 | "That shape carries no mail session-id, cannot be…" | pre-release | flows |  |
| 180 | "A deployment mailbox MUST NOT feed it to…" | pre-release | flows |  |
| 181 | "On that mailbox it is malformed flight mail…" | pre-release | flows |  |
| 182 | "The frame of a flight mail is carried…" | pre-release | flows |  |
| 183 | "The part's content, under Content-Transfer-Encoding base64, is 1…" | pre-release | flows |  |
| 184 | "~~~ HP-DTLS/3 transfer= part= parts= bytes= sha384= ~~~" | pre-release | flows |  |
| 185 | "where:" | pre-release | flows |  |
| 186 | "`t` is the transfer identifier: 16 lowercase hexadecimal…" | pre-release | flows |  |
| 187 | "`i` and `n` are the 0-based index of…" | pre-release | flows |  |
| 188 | "An unsegmented datagram is part 0 of 1." | pre-release | flows |  |
| 189 | "`b` is the total length of the datagram…" | pre-release | flows |  |
| 190 | "The field publishes the datagram's exact length, which…" | pre-release | flows |  |
| 191 | "`d` is the SHA-384 digest of the whole…" | pre-release | flows |  |
| 192 | "the chunk is a slice of the base64…" | pre-release | flows |  |
| 193 | "Slices are cut on base64 group boundaries, so…" | pre-release | flows |  |
| 194 | "The digest binds the parts of a transfer…" | pre-release | flows |  |
| 195 | "It is not a signature and MUST NOT…" | pre-release | flows |  |
| 196 | "The frame rides as its own part, and…" | pre-release | flows |  |
| 197 | "This is the dedicated-part practice {{RFC8551}} records for…" | pre-release | flows |  |
| 198 | "Text outside the part is not the frame…" | pre-release | flows |  |
| 199 | "The part is a leaf part: a direct…" | pre-release | flows |  |
| 200 | "A sender MUST NOT wrap it in one." | pre-release | flows |  |
| 201 | "A receiver finds the frame part by its…" | pre-release | flows |  |
| 202 | "The header line is the part's 1st line." | pre-release | flows |  |
| 203 | "Base64 folding at 76 columns inside the part…" | pre-release | flows |  |
| 204 | "Quoted-printable MUST NOT be used for the part…" | pre-release | flows |  |
| 205 | "A message with no `application/hp-dtls3` part is read…" | pre-release | flows |  |
| 206 | "When a typed part is present it is…" | pre-release | flows |  |
| 207 | "The naked shape is read for senders that…" | pre-release | flows |  |
| 208 | "It is not a 2nd copy of the…" | pre-release | flows |  |
| 209 | "A sender that uses the typed part places…" | pre-release | flows |  |
| 210 | "A receiver cannot tell that a typed part…" | pre-release | flows |  |
| 211 | "It applies the rule it can check: no…" | pre-release | flows |  |
| 212 | "The flight is repaired, if at all, by…" | pre-release | flows |  |
| 213 | "An intermediary that drops the typed part from…" | pre-release | flows |  |
| 214 | "A flight mail is subject to the version…" | pre-release | flows |  |
| 215 | "Within the carriage, a datagram MUST NOT exceed…" | pre-release | flows |  |
| 216 | "The reference implementation's limit is 262144 octets, and…" | pre-release | flows |  |
| 217 | "Both are local limits, configurable within the bounds…" | pre-release | flows |  |
| 218 | "A part count MUST NOT exceed 1024." | pre-release | flows |  |
| 219 | "A sender segments a datagram when its base64…" | pre-release | flows |  |
| 220 | "Every part of 1 transfer carries the same…" | pre-release | flows |  |
| 221 | "A sender MUST NOT place parts of 2…" | pre-release | flows |  |
| 222 | "The receiver's reassembly state is keyed by (mail…" | pre-release | flows |  |
| 223 | "Its rules are:" | pre-release | flows |  |
| 224 | "Parts MAY arrive in any order." | pre-release | flows |  |
| 225 | "Duplicate parts are idempotent: the same index with…" | pre-release | flows |  |
| 226 | "A part that contradicts its transfer -- a…" | pre-release | flows |  |
| 227 | "The receiver drops the state and completes nothing…" | pre-release | flows |  |
| 228 | "The sender may start the transfer again under…" | pre-release | flows |  |
| 229 | "A transfer completes when every index is held…" | pre-release | flows |  |
| 230 | "A completed datagram is delivered upward exactly once,…" | pre-release | flows |  |
| 231 | "Incomplete state is bounded in count, in total…" | pre-release | flows |  |
| 232 | "The reference implementation holds at most 64 transfers." | pre-release | flows |  |
| 233 | "A transfer's age runs from its FIRST part…" | pre-release | flows |  |
| 234 | "Expired parts complete nothing: a part that arrives…" | pre-release | flows |  |
| 235 | "Reassembly is deliberately unauthenticated and therefore deliberately cheap…" | pre-release | flows |  |
| 236 | "The carriage defines no acknowledgement and no retransmission…" | pre-release | flows |  |
| 237 | "Retransmission is the DTLS handshake's, as version 1's…" | pre-release | flows |  |
| 238 | "On this carriage a flight's re-send is a…" | pre-release | flows |  |
| 239 | "The re-sent flight is the DTLS stack's own…" | pre-release | flows |  |
| 240 | "A sender SHOULD NOT re-send a flight mail…" | pre-release | flows |  |
| 241 | "Timers that are reasonable on a live path…" | pre-release | flows |  |
| 242 | "An implementation on this carriage SHOULD stretch its…" | pre-release | flows |  |
| 243 | "Stretching a timer changes no message and no…" | pre-release | flows |  |
| 244 | "Mail is delivered at least once by some…" | pre-release | flows |  |
| 245 | "The carriage keeps the 3 layers' duplicate handling…" | pre-release | flows |  |
| 246 | "Mail layer: the carriage suppresses exact duplicates, split…" | pre-release | flows |  |
| 247 | "A receiver keeps a digest of each datagram…" | pre-release | flows |  |
| 248 | "The cache is an optimization against a poller…" | pre-release | flows |  |
| 249 | "The connection-id binding check of Section 9.2 runs…" | pre-release | flows |  |
| 250 | "A digest hit on a handshake-phase datagram is…" | pre-release | flows |  |
| 251 | "A digest hit spends the 1 re-post the…" | pre-release | flows |  |
| 252 | "A thousand copies of 1 ClientHello therefore cost…" | pre-release | flows |  |
| 253 | "A replayed mail is therefore not a new…" | pre-release | flows |  |
| 254 | "A retransmission under {{RFC9147}} Section 5.2 is not…" | pre-release | flows |  |
| 255 | "It is a new record, with a new…" | pre-release | flows |  |
| 256 | "It misses this cache, enters the stack, and…" | pre-release | flows |  |
| 257 | "The budget does not limit it, and if…" | pre-release | flows |  |
| 258 | "DTLS layer: records are protected and sequenced by…" | pre-release | flows |  |
| 259 | "Job layer: a job inside a session faces…" | pre-release | flows |  |
| 260 | "A duplicate flight mail MUST NOT create a…" | pre-release | flows |  |
| 261 | "A duplicate part MUST NOT complete a transfer…" | pre-release | flows |  |
| 262 | "No ordering is assumed anywhere in this carriage." | pre-release | flows |  |
| 263 | "Flight mails of 1 attempt can arrive in…" | pre-release | flows |  |
| 264 | "Application messages inside a session keep the session's…" | pre-release | flows |  |
| 265 | "On a runner that has enabled this carriage,…" | pre-release | flows |  |
| 266 | "The classification is by subject grammar and body…" | pre-release | flows |  |
| 267 | "A message whose subject matches the flight subject…" | pre-release | flows |  |
| 268 | "It goes to the carriage, and to nothing…" | pre-release | flows |  |
| 269 | "The unaddressed harness subject is not this case…" | pre-release | flows |  |
| 270 | "A message whose subject is a version 1…" | pre-release | flows |  |
| 271 | "Everything else is other mail, handled as before." | pre-release | flows |  |
| 272 | "DTLS classification happens in the component that owns…" | pre-release | flows |  |
| 273 | "A complete datagram is an initialization flight when…" | pre-release | flows |  |
| 274 | "A fragmented or incomplete first handshake message is…" | pre-release | flows |  |
| 275 | "It is malformed flight mail: consumed, dropped, not…" | pre-release | flows |  |
| 276 | "The profile's ClientHello is one message, and this…" | pre-release | flows |  |
| 277 | "A complete datagram that parses as DTLS records…" | pre-release | flows |  |
| 278 | "The recognition is of the DTLS bytes, not…" | pre-release | flows |  |
| 279 | "An initialization flight is answered as version 1's…" | pre-release | flows |  |
| 280 | "A first flight that is not a complete…" | pre-release | flows |  |
| 281 | "A message with a DTLS subject whose body…" | pre-release | flows |  |
| 282 | "It is:" | pre-release | flows |  |
| 283 | "consumed as DTLS input -- marked seen, so…" | pre-release | flows |  |
| 284 | "dropped -- it produces no session, no application…" | pre-release | flows |  |
| 285 | "never reinterpreted as a job or as any…" | pre-release | flows |  |
| 286 | "An implementation MUST NOT fall back from a…" | pre-release | flows |  |
| 287 | "The lane a message enters by its subject…" | pre-release | flows |  |
| 288 | "Flight mail is consumed by the component that…" | pre-release | flows |  |
| 289 | "A party MUST mark a flight message seen…" | pre-release | flows |  |
| 290 | "An initiator MUST ignore flight mail whose mail…" | pre-release | flows |  |
| 291 | "An attempt proceeds exactly as the datagram binding's…" | pre-release | flows |  |
| 292 | "The initiator sends its ClientHello as flight mail…" | pre-release | flows |  |
| 293 | "The responder, stateless, answers with a HelloRetryRequest flight…" | pre-release | flows |  |
| 294 | "The initiator answers with its cookied ClientHello." | pre-release | flows |  |
| 295 | "The responder validates the cookie and the PSK…" | pre-release | flows |  |
| 296 | "The initiator verifies the flight, holds the disclosure…" | pre-release | flows |  |
| 297 | "The session is established at both ends when…" | pre-release | flows |  |
| 298 | "No step of this exchange is a job,…" | pre-release | flows |  |
| 299 | "The responder's DTLS core needs a peer address…" | pre-release | flows |  |
| 300 | "On the datagram binding that is the datagram's…" | pre-release | flows |  |
| 301 | "On this carriage there is no source address…" | pre-release | flows |  |
| 302 | "The peer address on this carriage is the…" | pre-release | flows |  |
| 303 | "That string is an untrusted routing label: it…" | pre-release | flows |  |
| 304 | "The cookie key is a secret of the…" | pre-release | flows |  |
| 305 | "The key's lifetime is the matter of Section…" | pre-release | flows |  |
| 306 | "When a session establishes, the carriage binds the…" | pre-release | flows |  |
| 307 | "From then on:" | pre-release | flows |  |
| 308 | "A protected record is accepted under a mail…" | pre-release | flows |  |
| 309 | "A record whose connection ID is bound to…" | pre-release | flows |  |
| 310 | "A record therefore cannot be moved from 1…" | pre-release | flows |  |
| 311 | "Resumption over this carriage follows the profile: tickets…" | pre-release | flows |  |
| 312 | "A ticket is stored mail like any other…" | pre-release | flows |  |
| 313 | "(Version 1's SHOULD for the datagram binding is…" | pre-release | flows |  |
| 314 | "A resumed handshake is a full handshake in…" | pre-release | flows |  |
| 315 | "A deployment MAY disable resumption on this carriage…" | pre-release | flows |  |
| 316 | "An attempt that cannot complete -- a flight…" | pre-release | flows |  |
| 317 | "The cookie key of Section 9.2 has a…" | pre-release | flows |  |
| 318 | "On the datagram binding a HelloRetryRequest is answered…" | pre-release | flows |  |
| 319 | "On this carriage it is answered on a…" | pre-release | flows |  |
| 320 | "A responder SHOULD keep its cookie key across…" | pre-release | flows |  |
| 321 | "A responder whose cookie key does not survive…" | pre-release | flows |  |
| 322 | "Recovery is a fresh attempt under a new…" | pre-release | flows |  |
| 323 | "Established sessions do not survive a restart of…" | pre-release | flows |  |
| 324 | "A session ends by alert, by the profile's…" | pre-release | flows |  |
| 325 | "Keys are erased with the session (Section 16.1).…" | pre-release | flows |  |
| 326 | "Application data on the session is framed as…" | pre-release | flows |  |
| 327 | "A job travels as the envelope of its…" | pre-release | flows |  |
| 328 | "A result travels as the envelope of its…" | pre-release | flows |  |
| 329 | "On the runner, a completed application message is…" | pre-release | flows |  |
| 330 | "The core cannot tell, and does not need…" | pre-release | flows |  |
| 331 | "The objects are version 1 objects." | pre-release | flows |  |
| 332 | "A job inside a session is a version…" | pre-release | flows |  |
| 333 | "Completing a DTLS handshake MUST NOT bypass, widen,…" | pre-release | flows |  |
| 334 | "A job carried inside a session is admitted…" | pre-release | flows |  |
| 335 | "The session authenticates the channel; the signature authenticates…" | pre-release | flows |  |
| 336 | "Neither stands in for the other, and the…" | pre-release | flows |  |
| 337 | "The 2 keys are checked independently." | pre-release | flows |  |
| 338 | "The PSK identity that opened the session and…" | pre-release | flows |  |
| 339 | "A job signed under 1 key MAY be…" | pre-release | flows |  |
| 340 | "An implementation MUST NOT admit, widen, or narrow…" | pre-release | flows |  |
| 341 | "(The session's key does decide 1 thing, which…" | pre-release | flows |  |
| 342 | "A result for a job that arrived inside…" | pre-release | flows |  |
| 343 | "The carriage remembers, for each job it delivered…" | pre-release | flows |  |
| 344 | "The hold is kept as the result is…" | pre-release | flows |  |
| 345 | "A hold that died with the process would…" | pre-release | flows |  |
| 346 | "If that session no longer exists when the…" | pre-release | flows |  |
| 347 | "The acceptance gate refuses the repeated job as…" | pre-release | flows |  |
| 348 | "A job whose ident is held for another…" | pre-release | flows |  |
| 349 | "A held result MUST NOT be sent as…" | pre-release | flows |  |
| 350 | "Section 12 states the general rule this follows…" | pre-release | flows |  |
| 351 | "The PSK identity distinguishes submitters only as finely…" | pre-release | flows |  |
| 352 | "Two peers that authenticate with the same secret…" | pre-release | flows |  |
| 353 | "Distinct submitters are distinct keys, which version 1's…" | pre-release | flows |  |
| 354 | "This carriage does not invent a finer name…" | pre-release | flows |  |
| 355 | "The hold is bounded, as the hold of…" | pre-release | flows |  |
| 356 | "A held result expires by age -- the…" | pre-release | flows |  |
| 357 | "An expired result is dropped and the expiry…" | pre-release | flows |  |
| 358 | "Dropping is not downgrade: downgrade would be sending…" | pre-release | flows |  |
| 359 | "The platform disclosure is the version 1 Section…" | pre-release | flows |  |
| 360 | "The carriage is why the mechanism matters most…" | pre-release | flows |  |
| 361 | "On a live path, a post-handshake greeting costs…" | pre-release | flows |  |
| 362 | "Over a mailbox, it costs a poll cycle…" | pre-release | flows |  |
| 363 | "Riding the final handshake flight -- the pattern…" | pre-release | flows |  |
| 364 | "Even a rudimentary exchange counts: a responder that…" | pre-release | flows |  |
| 365 | "The precondition that makes the early disclosure acceptable…" | pre-release | flows |  |
| 366 | "A peer that does not hold the shared…" | pre-release | flows |  |
| 367 | "The accepted cost of version 1 Section 20…" | pre-release | flows |  |
| 368 | "Version 1's security considerations argue the point; this…" | pre-release | flows |  |
| 369 | "The following are stated in 1 place because…" | pre-release | flows |  |
| 370 | "`psk_ke` MUST NOT be offered, accepted, or fallen…" | pre-release | flows |  |
| 371 | "A session's keys are never a fallback for…" | pre-release | flows |  |
| 372 | "A cleartext object inside a session is refused…" | pre-release | flows |  |
| 373 | "A result bound to a session is never…" | pre-release | flows |  |
| 374 | "Flight mail that fails is never reinterpreted as…" | pre-release | flows |  |
| 375 | "The mail hop's own TLS (Section 16.2) is…" | pre-release | flows |  |
| 376 | "Replay is handled at 3 layers, each in…" | pre-release | flows |  |
| 377 | "A replayed flight mail meets the mail layer's…" | pre-release | flows |  |
| 378 | "A replayed initialization therefore cannot create a duplicate…" | pre-release | flows |  |
| 379 | "Early data has no layer here at all:…" | pre-release | flows |  |
| 380 | "A job that runs a program is not…" | pre-release | flows |  |
| 381 | "A replayed record meets the record layer: sequence…" | pre-release | flows |  |
| 382 | "A replayed application message that somehow reached the…" | pre-release | flows |  |
| 383 | "A replayed job meets the acceptance gate's seen-set:…" | pre-release | flows |  |
| 384 | "Resumption tickets on this carriage MUST be single-use…" | pre-release | flows |  |
| 385 | "A replayed ticket can at most restart a…" | pre-release | flows |  |
| 386 | "The carriage shares the mailbox with the ordinary…" | pre-release | flows |  |
| 387 | "Flight mail and job mail are distinguished by…" | pre-release | flows |  |
| 388 | "Poll rhythm is the operational dial that matters." | pre-release | flows |  |
| 389 | "A runner that polls its mailbox every 20…" | pre-release | flows |  |
| 390 | "Nothing in the protocol changes -- only the…" | pre-release | flows |  |
| 391 | "Operators pairing this carriage with a slow poll…" | pre-release | flows |  |
| 392 | "Sessions are state, and state on a store-and-forward…" | pre-release | flows |  |
| 393 | "It MUST NOT log session keys, ephemeral material,…" | pre-release | flows |  |
| 394 | "This document requests no IANA action." | pre-release | flows |  |
| 395 | "The platform_info extension's code point is version 1's…" | pre-release | flows |  |
| 396 | "This document reuses that extension exactly as version…" | pre-release | flows |  |
| 397 | "The DTLS reference port 20220 remains version 1's…" | pre-release | flows |  |
| 398 | "The carriage's MIME content type (Section 5.2) is…" | pre-release | flows |  |
| 399 | "A future standards-track revision is where such a…" | post-release | flows |  |
| 400 | "As a local, unsubmitted draft, this document could…" | pre-release | flows |  |
| 401 | "The property this version exists for: a session's…" | pre-release | flows |  |
| 402 | "The shared secret authenticates; it does not encrypt…" | pre-release | flows |  |
| 403 | "It follows that recording every flight mail of…" | pre-release | flows |  |
| 404 | "The recorded flights are a ClientHello, a HelloRetryRequest,…" | pre-release | flows |  |
| 405 | "Without the ephemeral private keys, which never leave…" | pre-release | flows |  |
| 406 | "The limits of the property are the usual…" | pre-release | flows |  |
| 407 | "Forward secrecy is a property of recorded sessions…" | pre-release | flows |  |
| 408 | "One further limit belongs to this carriage in…" | pre-release | flows |  |
| 409 | "Where the ephemeral exchange is the bare X25519…" | pre-release | flows |  |
| 410 | "Forward secrecy there is secrecy against later compromise…" | pre-release | flows |  |
| 411 | "The remedy is the hybrid share of Section…" | pre-release | flows |  |
| 412 | "In a hybrid session the ephemeral secret is…" | pre-release | flows |  |
| 413 | "The `psk_dhe_ke` rule is unchanged -- the PSK…" | pre-release | flows |  |
| 414 | "On this carriage the mailbox provider, and any…" | pre-release | flows |  |
| 415 | "The provider cannot read application data, cannot forge…" | pre-release | flows |  |
| 416 | "It can delay, drop, duplicate, and reorder mail;…" | pre-release | flows |  |
| 417 | "Deployments that care about the metadata itself should…" | pre-release | flows |  |
| 418 | "Every routing decision in this carriage is made…" | pre-release | flows |  |
| 419 | "The synthetic peer address of Section 9.2 exists…" | pre-release | flows |  |
| 420 | "A deployment MUST NOT add a sender allowlist…" | pre-release | flows |  |
| 421 | "Everything a receiver does before a binder verifies…" | pre-release | flows |  |
| 422 | "A fresh ClientHello costs the responder 1 HelloRetryRequest…" | pre-release | flows |  |
| 423 | "A bit-identical copy of a handshake-phase flight costs…" | pre-release | flows |  |
| 424 | "A flight mail is refused above the mail…" | pre-release | flows |  |
| 425 | "A reassembly slot is 1 of at most…" | pre-release | flows |  |
| 426 | "A digest-cache entry is 1 of 4096, the…" | pre-release | flows |  |
| 427 | "A saved outbound flight is 1 of 4096,…" | pre-release | flows |  |
| 428 | "Evicting one drops only the spare re-post for…" | pre-release | flows |  |
| 429 | "A retransmission is a new record and is…" | pre-release | flows |  |
| 430 | "A malformed flight is consumed in 1 pass…" | pre-release | flows |  |
| 431 | "The unaddressed harness subject, on a deployment mailbox,…" | pre-release | flows |  |
| 432 | "An action an unauthenticated sender can cause that…" | pre-release | flows |  |
| 433 | "The platform disclosure's cost -- disclosure before the…" | pre-release | flows |  |
| 434 | "Section 12 collects the no-downgrade rules." | pre-release | flows |  |
| 435 | "The general statement behind them: at no point…" | pre-release | flows |  |
| 436 | "A failed handshake is a failed handshake; a…" | pre-release | flows |  |
| 437 | "An implementation that adds a fallback -- plain…" | pre-release | flows |  |
| 438 | "It is worth restating the architecture once, because…" | pre-release | flows |  |
| 439 | "The acceptance gate -- signature, audience, caps, key…" | pre-release | flows |  |
| 440 | "Carrying a job inside a session changes the…" | pre-release | flows |  |
| 441 | "Any future extension of this carriage that proposes…" | pre-release | flows |  |
| 442 | "The constraint that narrows what a session may…" | pre-release | flows |  |
| 443 | "A deployment that wants one key to run…" | pre-release | flows |  |
| 444 | "The session does not widen that policy, and…" | pre-release | flows |  |
| 445 | "A holder of a different key, or of…" | pre-release | flows |  |
| 446 | "The gate reads the job's own key and…" | pre-release | flows |  |
