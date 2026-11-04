# Findings — docs/ietf/draft-slutsky-homing-pigeon/submitted/draft-slutsky-homing-pigeon-00.md

Source: docs/ietf/draft-slutsky-homing-pigeon/submitted/draft-slutsky-homing-pigeon-00.md, reviewed at main 47232c1a.
Sentence units: 713. Flagged: 5. Categories: pre-release 713, post-release 0.

A frozen submitted Internet-Draft, the version 1 base specification at its -00 revision: the full protocol in RFC order — transport, message forms, the acceptance gate, the transports, security modes, the Oracle, IANA. At 713 units it is the shard's largest single specification; the prose is definitional, each section's rules stated in the order the protocol performs them, and the field tables sit inside the prose that introduces them. The non-sentences are the 5 table header rows (units 87, 300, 355, 400, 419); every data row is counted as a unit and flows as a record.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "title: "Homing Pigeon Message Protocol, Version 1" abbrev:…" | pre-release | flows |  |
| 2 | "ins: "A." | pre-release | flows |  |
| 3 | "Slutsky" name: "Andrew Slutsky" email: "slutsky5544@gmail.com"" | pre-release | flows |  |
| 4 | "normative: RFC2104: title: "HMAC: Keyed-Hashing for Message Authentication"…" | pre-release | flows |  |
| 5 | "name: "H." | pre-release | flows |  |
| 6 | "Krawczyk"" | pre-release | flows |  |
| 7 | "name: "M." | pre-release | flows |  |
| 8 | "Bellare"" | pre-release | flows |  |
| 9 | "name: "R." | pre-release | flows |  |
| 10 | "Canetti" date: 1997-02 seriesinfo: RFC: 2104 DOI: 10.17487/RFC2104…" | pre-release | flows |  |
| 11 | "name: "D." | pre-release | flows |  |
| 12 | "Crocker, Ed." | pre-release | flows |  |
| 13 | "name: "P." | pre-release | flows |  |
| 14 | "Overell" date: 2008-01 seriesinfo: RFC: 5234 STD: 68…" | pre-release | flows |  |
| 15 | "name: "H." | pre-release | flows |  |
| 16 | "Krawczyk"" | pre-release | flows |  |
| 17 | "name: "P." | pre-release | flows |  |
| 18 | "Eronen" date: 2010-05 seriesinfo: RFC: 5869 DOI: 10.17487/RFC5869…" | pre-release | flows |  |
| 19 | "name: "A." | pre-release | flows |  |
| 20 | "Langley"" | pre-release | flows |  |
| 21 | "name: "M." | pre-release | flows |  |
| 22 | "Hamburg"" | pre-release | flows |  |
| 23 | "name: "S." | pre-release | flows |  |
| 24 | "Turner" date: 2016-01 seriesinfo: RFC: 7748 DOI: 10.17487/RFC7748…" | pre-release | flows |  |
| 25 | "name: "T." | pre-release | flows |  |
| 26 | "Bray, Ed." | pre-release | flows |  |
| 27 | "date: 2017-12 seriesinfo: RFC: 8259 STD: 90 DOI:…" | pre-release | flows |  |
| 28 | "name: "K." | pre-release | flows |  |
| 29 | "Moore"" | pre-release | flows |  |
| 30 | "name: "C." | pre-release | flows |  |
| 31 | "Newman" date: 2018-01 seriesinfo: RFC: 8314 DOI: 10.17487/RFC8314…" | pre-release | flows |  |
| 32 | "name: "E." | pre-release | flows |  |
| 33 | "Rescorla" date: 2018-08 seriesinfo: RFC: 8446 DOI: 10.17487/RFC8446…" | pre-release | flows |  |
| 34 | "name: "K." | pre-release | flows |  |
| 35 | "Moriarty"" | pre-release | flows |  |
| 36 | "name: "S." | pre-release | flows |  |
| 37 | "Farrell" date: 2021-03 seriesinfo: RFC: 8996 BCP: 195…" | pre-release | flows |  |
| 38 | "name: "E." | pre-release | flows |  |
| 39 | "Rescorla, Ed." | pre-release | flows |  |
| 40 | "name: "H." | pre-release | flows |  |
| 41 | "Tschofenig, Ed." | pre-release | flows |  |
| 42 | "name: "T." | pre-release | flows |  |
| 43 | "Fossati"" | pre-release | flows |  |
| 44 | "name: "A." | pre-release | flows |  |
| 45 | "Kraus" date: 2022-03 seriesinfo: RFC: 9146 DOI: 10.17487/RFC9146…" | pre-release | flows |  |
| 46 | "name: "E." | pre-release | flows |  |
| 47 | "Rescorla"" | pre-release | flows |  |
| 48 | "name: "H." | pre-release | flows |  |
| 49 | "Tschofenig"" | pre-release | flows |  |
| 50 | "name: "N." | pre-release | flows |  |
| 51 | "Modadugu" date: 2022-04 seriesinfo: RFC: 9147 DOI: 10.17487/RFC9147…" | pre-release | flows |  |
| 52 | "name: "Y." | pre-release | flows |  |
| 53 | "Sheffer"" | pre-release | flows |  |
| 54 | "name: "P." | pre-release | flows |  |
| 55 | "Saint-Andre"" | pre-release | flows |  |
| 56 | "name: "T." | pre-release | flows |  |
| 57 | "Fossati" date: 2022-11 seriesinfo: RFC: 9325 BCP: 195…" | pre-release | flows |  |
| 58 | "org: National Institute of Standards and Technology date:…" | pre-release | flows |  |
| 59 | "name: M." | pre-release | flows |  |
| 60 | "Dworkin date: 2007-11 seriesinfo: NIST SP: 800-38D DOI:…" | pre-release | flows |  |
| 61 | "informative: RFC9562: title: "Universally Unique IDentifiers (UUIDs)" author:" | pre-release | flows |  |
| 62 | "name: "K." | pre-release | flows |  |
| 63 | "Davis"" | pre-release | flows |  |
| 64 | "name: "B." | pre-release | flows |  |
| 65 | "Peabody"" | pre-release | flows |  |
| 66 | "name: "P." | pre-release | flows |  |
| 67 | "Leach" date: 2024-05 seriesinfo: RFC: 9562 DOI: 10.17487/RFC9562…" | pre-release | flows |  |
| 68 | "name: "Andrew Slutsky" ins: "A." | pre-release | flows |  |
| 69 | "Slutsky" date: 2026-10 seriesinfo: Internet-Draft: draft-slutsky-homing-pigeon-v2-00" | pre-release | flows |  |
| 70 | "--- abstract" | pre-release | flows |  |
| 71 | "This document specifies the Homing Pigeon message protocol,…" | pre-release | flows |  |
| 72 | "On the email binding, a submitter sends one…" | pre-release | flows |  |
| 73 | "The signature is the only authorization." | pre-release | flows |  |
| 74 | "The job object is protected end to end…" | pre-release | flows |  |
| 75 | "The store-and-forward bindings open no inbound listener on…" | pre-release | flows |  |
| 76 | "The DTLS binding changes the binding and not…" | pre-release | flows |  |
| 77 | "It is a binding of version 1, not…" | pre-release | flows |  |
| 78 | "The shared secret is the session's external pre-shared…" | pre-release | flows |  |
| 79 | "The binding opens an inbound listener on the…" | pre-release | flows |  |
| 80 | "It is an addition, never a replacement: the…" | pre-release | flows |  |
| 81 | "--- middle" | pre-release | flows |  |
| 82 | "Some hosts cannot accept inbound connections." | pre-release | flows |  |
| 83 | "The protocol needs a store-and-forward queue so neither…" | pre-release | flows |  |
| 84 | "The first binding this document specifies is a…" | pre-release | flows |  |
| 85 | "The exchange is two messages:" | pre-release | flows |  |
| 86 | "~~~ Submitter Mailbox Runner" | pre-release | flows |  |
| 87 | "job message (signed JSON) \|" | pre-release | flagged | Table header row, structure rather than a sentence |
| 88 | "---------------------------> \|" | pre-release | flows |  |
| 89 | "\| poll" | pre-release | flows |  |
| 90 | "\| <---------------------------" | pre-release | flows |  |
| 91 | "\| result message" | pre-release | flows |  |
| 92 | "\| (signed JSON)" | pre-release | flows |  |
| 93 | "\| <---------------------------" | pre-release | flows |  |
| 94 | "result (same mailbox, or \|" | pre-release | flows |  |
| 95 | "signed reply_to) \|" | pre-release | flows |  |
| 96 | "<--------------------------- \|" | pre-release | flows |  |
| 97 | "~~~" | pre-release | flows |  |
| 98 | "The deployment this protocol is written for is…" | pre-release | flows |  |
| 99 | "The person holds the mailbox and the secret;…" | pre-release | flows |  |
| 100 | "Email is the path that already exists between…" | pre-release | flows |  |
| 101 | "The runner is deliberately plain: it executes what…" | pre-release | flows |  |
| 102 | "Version negotiation is not a handshake." | pre-release | flows |  |
| 103 | "The message carries `v`." | pre-release | flows |  |
| 104 | "This document defines `v` = 1 only." | pre-release | flows |  |
| 105 | "A receiver that does not implement version 1…" | pre-release | flows |  |
| 106 | "The protocol is specified in the open so…" | pre-release | flows |  |
| 107 | "Any implementation of this document can submit jobs:…" | pre-release | flows |  |
| 108 | "Two things are out of scope for this…" | pre-release | flows |  |
| 109 | "The sender asks the owner which address to…" | pre-release | flows |  |
| 110 | "Neither is discovered from the mail." | pre-release | flows |  |
| 111 | "Once the sender knows the address, the secret,…" | pre-release | flows |  |
| 112 | "This document specifies one version of the protocol:…" | pre-release | flows |  |
| 113 | "Its bindings are the email binding (Section 5),…" | pre-release | flows |  |
| 114 | "It consolidates this document's earlier text, which specified…" | pre-release | flows |  |
| 115 | "The companion draft that now carries the name…" | pre-release | flows |  |
| 116 | "A binding does not version the messages." | pre-release | flows |  |
| 117 | "The job and result objects are the same…" | pre-release | flows |  |
| 118 | "A receiver that does not offer a binding…" | pre-release | flows |  |
| 119 | "The reference implementation speaks version 1, and it…" | pre-release | flows |  |
| 120 | "A receiver following this document rejects any message…" | pre-release | flows |  |
| 121 | "The sender also requires the shared secret to…" | pre-release | flows |  |
| 122 | "That floor is not a protocol version; it…" | pre-release | flows |  |
| 123 | "Nothing else in the exchange changes shape." | pre-release | flows |  |
| 124 | "Later work also layers behavior this document scopes…" | pre-release | flows |  |
| 125 | "Those behaviors ride in extra members (Section 8);…" | pre-release | flows |  |
| 126 | "One consequence a submitter needs: a receiver layered…" | pre-release | flows |  |
| 127 | "{::boilerplate bcp14-tagged}" | pre-release | flows |  |
| 128 | "Job: a signed request that the runner execute…" | pre-release | flows |  |
| 129 | "Result: a signed report of what the runner…" | pre-release | flows |  |
| 130 | "Shared secret: an octet string known to the…" | pre-release | flows |  |
| 131 | "It is the HMAC key." | pre-release | flows |  |
| 132 | "It is not sent on the wire." | pre-release | flows |  |
| 133 | "Default secret: the shared secret selected when `key_id`…" | pre-release | flows |  |
| 134 | "Key identifier: the string in `key_id`." | pre-release | flows |  |
| 135 | "It is a label, not a secret." | pre-release | flows |  |
| 136 | "Seen-set: the runner's record of `job_id` values already…" | pre-release | flows |  |
| 137 | "It is local state." | pre-release | flows |  |
| 138 | "It is not a message." | pre-release | flows |  |
| 139 | "Freshness window: how far `issued_at` may be from…" | pre-release | flows |  |
| 140 | "Preamble: text in the message body before the…" | pre-release | flows |  |
| 141 | "It is not signed." | pre-release | flows |  |
| 142 | "LOCAL: a parameter or a check this document…" | pre-release | flows |  |
| 143 | "It is not negotiated." | pre-release | flows |  |
| 144 | "Session: one DTLS association between a submitter (the…" | pre-release | flows |  |
| 145 | "Defined in Section 19." | pre-release | flows |  |
| 146 | "Greeting: the first application message of a session,…" | pre-release | flows |  |
| 147 | "PSK identity: the `pre_shared_key` identity under which a…" | pre-release | flows |  |
| 148 | "The default secret's identity is `homing-pigeon`; an additional…" | pre-release | flows |  |
| 149 | "Ticket: the opaque resumption identity a runner issues…" | pre-release | flows |  |
| 150 | "This document specifies subjects, the signed object, the…" | pre-release | flows |  |
| 151 | "This document does not specify disclosure policy, queries,…" | pre-release | flows |  |
| 152 | "A job MAY carry extra members for those…" | pre-release | flows |  |
| 153 | "Receivers that do not implement them MUST ignore…" | pre-release | flows |  |
| 154 | "Section 1 describes how those uses relate to…" | pre-release | flows |  |
| 155 | "This section specifies the email binding." | pre-release | flows |  |
| 156 | "The protocol itself needs only the store-and-forward queue…" | pre-release | flows |  |
| 157 | "Further bindings are specified in Sections 5.1 and…" | pre-release | flows |  |
| 158 | "A direct session binding, in which the same…" | pre-release | flows |  |
| 159 | "The binding layer is abstract." | pre-release | flows |  |
| 160 | "A binding is an interchangeable carrier of the…" | pre-release | flows |  |
| 161 | "An implementation MAY substitute one binding for another,…" | pre-release | flows |  |
| 162 | "Conformance is per binding." | pre-release | flows |  |
| 163 | "This document specifies one version of the protocol,…" | pre-release | flows |  |
| 164 | "Pairing is established out of band (Section 1)…" | pre-release | flows |  |
| 165 | "The email binding of this section is the…" | pre-release | flows |  |
| 166 | "Two security properties are REQUIRED of the protocol…" | pre-release | flows |  |
| 167 | "The first is authentication of the object: the…" | pre-release | flows |  |
| 168 | "That requirement attaches to the object, never to…" | pre-release | flows |  |
| 169 | "No authentication a binding performs, however strong, satisfies…" | pre-release | flows |  |
| 170 | "The second is confidentiality of the object, in…" | pre-release | flows |  |
| 171 | "That requirement attaches to the property, not to…" | pre-release | flows |  |
| 172 | "A binding whose carriage provides confidentiality end to…" | pre-release | flows |  |
| 173 | "Where a binding's carriage terminates at an intermediary,…" | pre-release | flows |  |
| 174 | "Each binding specified in this document states which…" | pre-release | flows |  |
| 175 | "The runner reads the mailbox with IMAP and…" | pre-release | flows |  |
| 176 | "Mail authentication is out of band." | pre-release | flows |  |
| 177 | "The signature check does not change with the…" | pre-release | flows |  |
| 178 | "IMAP and SMTP MUST be used over TLS." | pre-release | flows |  |
| 179 | "An implementation MUST NOT carry this protocol over…" | pre-release | flows |  |
| 180 | "The TLS version MUST be 1.2 or higher;…" | pre-release | flows |  |
| 181 | "The recommendations of {{RFC9325}} apply." | pre-release | flows |  |
| 182 | "Cleartext mail access is obsolete {{RFC8314}}: implicit TLS…" | pre-release | flows |  |
| 183 | "TLS protects a hop." | pre-release | flows |  |
| 184 | "It does not hide the message from the…" | pre-release | flows |  |
| 185 | "The TLS requirements of this section therefore do…" | pre-release | flows |  |
| 186 | "On this binding the confidentiality property is carried…" | pre-release | flows |  |
| 187 | "An implementation MAY additionally support PGP/MIME protection of…" | pre-release | flows |  |
| 188 | "Such support is not required, and it is…" | pre-release | flows |  |
| 189 | "The body is UTF-8 text in a `text/plain`…" | pre-release | flows |  |
| 190 | "This document does not register a media type." | pre-release | flows |  |
| 191 | "If the message is multipart, the receiver uses…" | pre-release | flows |  |
| 192 | "The message MUST be rejected before the MAC…" | pre-release | flows |  |
| 193 | "The RECOMMENDED cap is 4194304 octets." | pre-release | flows |  |
| 194 | "A cap of 0 means no limit." | pre-release | flows |  |
| 195 | "This cap is LOCAL." | pre-release | flows |  |
| 196 | "The file binding carries the same envelope as…" | pre-release | flows |  |
| 197 | "It exists for deployments where the submitter and…" | pre-release | flows |  |
| 198 | "The envelope mapping is byte-for-byte the email form:…" | pre-release | flows |  |
| 199 | "A job is a regular file in the…" | pre-release | flows |  |
| 200 | "The file SHOULD be named `<ident>.job.txt`, where `<ident>`…" | pre-release | flows |  |
| 201 | "A result is a file named `<ident>.result.txt` in…" | pre-release | flows |  |
| 202 | "A receiver polls the directories on its ordinary…" | pre-release | flows |  |
| 203 | "Acknowledgement is consumption." | pre-release | flows |  |
| 204 | "Whichever side has taken a file moves it…" | pre-release | flows |  |
| 205 | "A redelivery of the same job rewrites the…" | pre-release | flows |  |
| 206 | "Two gates stand in series on this binding." | pre-release | flows |  |
| 207 | "The first is the inbox directory's operating-system access…" | pre-release | flows |  |
| 208 | "The second is the signature, which remains the…" | pre-release | flows |  |
| 209 | "A deployment MUST treat the directory's access control…" | pre-release | flows |  |
| 210 | "The binding's limits are the filesystem's." | pre-release | flows |  |
| 211 | "Both parties need access to the same directories,…" | pre-release | flows |  |
| 212 | "There is no store-and-forward beyond the disk, no…" | pre-release | flows |  |
| 213 | "Of the two security properties of Section 5,…" | pre-release | flows |  |
| 214 | "The MAC carries the authentication property, as on…" | pre-release | flows |  |
| 215 | "Whether Section 16 is applied on this binding…" | pre-release | flows |  |
| 216 | "The NATS binding carries the same envelope over…" | pre-release | flows |  |
| 217 | "It exists for deployments where submitter and runner…" | pre-release | flows |  |
| 218 | "The envelope mapping is the email form carried…" | pre-release | flows |  |
| 219 | "Jobs are published on a jobs subject (a…" | pre-release | flows |  |
| 220 | "Results are published on a per-job subject formed…" | pre-release | flows |  |
| 221 | "Core NATS is at-most-once: the broker acknowledges nothing…" | pre-release | flows |  |
| 222 | "A job published while no runner is subscribed…" | pre-release | flows |  |
| 223 | "The protocol's own machinery is the recovery: the…" | pre-release | flows |  |
| 224 | "A deployment that needs broker-side retention needs a…" | pre-release | flows |  |
| 225 | "Two gates stand in series." | pre-release | flows |  |
| 226 | "The first is the broker's own authentication: broker…" | pre-release | flows |  |
| 227 | "A deployment MAY relax this by an explicit…" | pre-release | flows |  |
| 228 | "The second gate is the signature, unchanged." | pre-release | flows |  |
| 229 | "A required-auth NATS deployment is, for this reason,…" | pre-release | flows |  |
| 230 | "The binding's limits are the broker's: payload sizes…" | pre-release | flows |  |
| 231 | "Of the two security properties of Section 5,…" | pre-release | flows |  |
| 232 | "TLS on a broker connection, where a deployment…" | pre-release | flows |  |
| 233 | "The MAC therefore carries the authentication property on…" | pre-release | flows |  |
| 234 | "Subjects are part of the email binding (Section…" | pre-release | flows |  |
| 235 | "Subjects are matched case-insensitively." | pre-release | flows |  |
| 236 | "A preamble such as `Re:` MAY appear before…" | pre-release | flows |  |
| 237 | "The marker need not be the first character…" | pre-release | flows |  |
| 238 | "A job subject matches this pattern, in the…" | pre-release | flows |  |
| 239 | "~~~ [HOMING-PIGEON] (SP word)* SP job SP job-id…" | pre-release | flows |  |
| 240 | "`word` is one or more visible characters." | pre-release | flows |  |
| 241 | "`job-id` is one or more visible characters with…" | pre-release | flows |  |
| 242 | "The words between the marker and `job` are…" | pre-release | flows |  |
| 243 | "`TEST` is a legal decoration." | pre-release | flows |  |
| 244 | "A result subject matches:" | pre-release | flows |  |
| 245 | "~~~ [HOMING-PIGEON] SP result SP job-id ~~~" | pre-release | flows |  |
| 246 | "ABNF {{RFC5234}} for the identifier only:" | pre-release | flows |  |
| 247 | "~~~ job-id = 1*128 job-id-char job-id-char = ALPHA…" | pre-release | flows |  |
| 248 | "/ "_" / "-" ~~~" | pre-release | flows |  |
| 249 | "The `job_id` in the subject MUST equal the…" | pre-release | flows |  |
| 250 | "A mismatch MUST be rejected (Section 14)." | pre-release | flows |  |
| 251 | "`job-id` MUST NOT be `.` or `..`." | pre-release | flows |  |
| 252 | "A UUID {{RFC9562}} is RECOMMENDED as the `job_id`." | pre-release | flows |  |
| 253 | "A message whose subject is not a job…" | pre-release | flows |  |
| 254 | "The receiver MUST NOT execute it." | pre-release | flows |  |
| 255 | "The receiver MAY mark it seen so that…" | pre-release | flows |  |
| 256 | "Result messages use the result pattern above and…" | pre-release | flows |  |
| 257 | "They are not jobs." | pre-release | flows |  |
| 258 | "The signed object is one JSON object {{RFC8259}}." | pre-release | flows |  |
| 259 | "The receiver ignores preamble and trailer." | pre-release | flows |  |
| 260 | "Verification uses the object that ends in the…" | pre-release | flows |  |
| 261 | "Line endings are normalized before both signing and…" | pre-release | flows |  |
| 262 | "Trailing whitespace after that normalization is not part…" | pre-release | flows |  |
| 263 | "The sender builds the object without `sig`, serializes…" | pre-release | flows |  |
| 264 | "~~~ ,"sig":"<96 hex digits>"} ~~~" | pre-release | flows |  |
| 265 | "JSON member order before `sig` is the sender's…" | pre-release | flows |  |
| 266 | "`sig` MUST be last." | pre-release | flows |  |
| 267 | "Senders SHOULD serialize with no insignificant whitespace." | pre-release | flows |  |
| 268 | "Receivers MUST accept insignificant whitespace inside the object,…" | pre-release | flows |  |
| 269 | "The receiver finds the signature as follows:" | pre-release | flows |  |
| 270 | "Normalize line endings and remove trailing whitespace." | pre-release | flows |  |
| 271 | "Let `marker` be the last occurrence of the…" | pre-release | flows |  |
| 272 | "If `marker` is absent, the message is malformed." | pre-release | flows |  |
| 273 | "The 96 characters after `marker` MUST be hexadecimal." | pre-release | flows |  |
| 274 | "The two characters after those MUST be `"`…" | pre-release | flows |  |
| 275 | "The signed octets are the bytes from the…" | pre-release | flows |  |
| 276 | "That `{` is the start of the object…" | pre-release | flows |  |
| 277 | "If no such `{` exists, the message is…" | pre-release | flows |  |
| 278 | "A sender MUST NOT place the character sequence…" | pre-release | flows |  |
| 279 | "The receiver uses the last occurrence." | pre-release | flows |  |
| 280 | "The MAC is HMAC-SHA-384 {{RFC2104}} using SHA-384 {{FIPS180-4}}." | pre-release | flows |  |
| 281 | "The HMAC key is the UTF-8 octets of…" | pre-release | flows |  |
| 282 | "Implementations MUST NOT hash, stretch, or otherwise derive…" | pre-release | flows |  |
| 283 | "The secret is a string of characters." | pre-release | flows |  |
| 284 | "Two sides that disagree on the characters disagree…" | pre-release | flows |  |
| 285 | "`sig` is the 48-octet HMAC value encoded as…" | pre-release | flows |  |
| 286 | "Senders MUST use lowercase digits." | pre-release | flows |  |
| 287 | "Receivers MUST compare in constant time after mapping…" | pre-release | flows |  |
| 288 | "Receivers MUST reject a malformed tail." | pre-release | flows |  |
| 289 | "Receivers MUST reject a MAC mismatch." | pre-release | flows |  |
| 290 | "A mismatch produces no result message (Section 14)." | pre-release | flows |  |
| 291 | "The compare covers all 96 digits." | pre-release | flows |  |
| 292 | "It MUST NOT stop at the first differing…" | pre-release | flows |  |
| 293 | "A local reject log MAY record that the…" | pre-release | flows |  |
| 294 | "It SHOULD NOT record the expected digest." | pre-release | flows |  |
| 295 | "A receiver MUST ignore object members it does…" | pre-release | flows |  |
| 296 | "`v` other than 1 MUST be rejected" | pre-release | flows |  |
| 297 | "`type` other than `job`, on a message the…" | pre-release | flows |  |
| 298 | "`kind` other than `exec` or `ping` MUST NOT…" | pre-release | flows |  |
| 299 | "Ignoring a member means the member is still…" | pre-release | flows |  |
| 300 | "Member \| JSON type \| Presence \| Rule" | pre-release | flagged | Table header row, structure rather than a sentence |
| 301 | "`v` \| number \| REQUIRED \| Integer 1.…" | pre-release | flows |  |
| 302 | "`type` \| string \| REQUIRED \| `job` or…" | pre-release | flows |  |
| 303 | "`job_id` \| string \| REQUIRED \| Section 6." | pre-release | flows |  |
| 304 | "`key_id` \| string \| OPTIONAL \| Selects the…" | pre-release | flows |  |
| 305 | "`aud` \| string \| OPTIONAL \| Audience claim.…" | pre-release | flows |  |
| 306 | "`sig` \| string \| REQUIRED \| Section 7.…" | pre-release | flows |  |
| 307 | "`key_id` is covered by the MAC." | pre-release | flows |  |
| 308 | "Key identifiers MAY appear in logs." | pre-release | flows |  |
| 309 | "An unknown `key_id` MUST be rejected before the…" | pre-release | flows |  |
| 310 | "The receiver MUST NOT try another secret." | pre-release | flows |  |
| 311 | "If a receiver enforces `runner_id`, the expected value…" | pre-release | flows |  |
| 312 | "The signed value is what the submitter claimed." | pre-release | flows |  |
| 313 | "It is not the source of the expected…" | pre-release | flows |  |
| 314 | "The receiver holds a map from `key_id` to…" | pre-release | flows |  |
| 315 | "The empty identifier names the default secret." | pre-release | flows |  |
| 316 | "Selection, before the MAC:" | pre-release | flows |  |
| 317 | "If `key_id` is absent, select the default secret." | pre-release | flows |  |
| 318 | "If `key_id` is present and is a string…" | pre-release | flows |  |
| 319 | "Otherwise reject." | pre-release | flows |  |
| 320 | "Do not compute a MAC." | pre-release | flows |  |
| 321 | "How keys are stored is LOCAL." | pre-release | flows |  |
| 322 | "Two values MUST NOT be assigned to one…" | pre-release | flows |  |
| 323 | "The default identifier has one slot." | pre-release | flows |  |
| 324 | "A secret MAY be named by its fingerprint." | pre-release | flows |  |
| 325 | "The reference software does so." | pre-release | flows |  |
| 326 | "The fingerprint is `k-` followed by the first…" | pre-release | flows |  |
| 327 | "~~~ key_id = "k-" \|\| hex(SHA-384("homing-pigeon key id…" | pre-release | flows |  |
| 328 | "The reference receiver puts that identifier in the…" | pre-release | flows |  |
| 329 | "An operator-chosen name, when one was configured, is…" | pre-release | flows |  |
| 330 | "One `key_id` still names one secret." | pre-release | flows |  |
| 331 | "One secret MAY have several identifiers." | pre-release | flows |  |
| 332 | "Two secrets MUST NOT share one." | pre-release | flows |  |
| 333 | "The reference sender includes `key_id` on every message…" | pre-release | flows |  |
| 334 | "The value is the fingerprint, unless the sender…" | pre-release | flows |  |
| 335 | "The empty identifier is how a sender asks…" | pre-release | flows |  |
| 336 | "A receiver that has not registered the fingerprint…" | pre-release | flows |  |
| 337 | "An absent `key_id` still selects the default secret." | pre-release | flows |  |
| 338 | "A fingerprint that is not in the map…" | pre-release | flows |  |
| 339 | "So is a near-miss: a different length, a…" | pre-release | flows |  |
| 340 | "The receiver MUST NOT select the default secret…" | pre-release | flows |  |
| 341 | "The name is a label." | pre-release | flows |  |
| 342 | "It is 32 bits of a one-way function…" | pre-release | flows |  |
| 343 | "It is not invertible." | pre-release | flows |  |
| 344 | "As an oracle for a guessed secret it…" | pre-release | flows |  |
| 345 | "The label keeps this hash apart from that…" | pre-release | flows |  |
| 346 | "Publishing the name discloses nothing a signed message…" | pre-release | flows |  |
| 347 | "The DTLS PSK identity (Section 3) is a…" | pre-release | flows |  |
| 348 | "`homing-pigeon` names the default secret." | pre-release | flows |  |
| 349 | "`homing-pigeon:` followed by a configured `key_id` names an…" | pre-release | flows |  |
| 350 | "The fingerprint is not a PSK identity unless…" | pre-release | flows |  |
| 351 | "`type` is `job`." | pre-release | flows |  |
| 352 | "~~~ json { "v": 1, "type": "job", "job_id":…" | pre-release | flows |  |
| 353 | "The `sig` line above is abbreviated." | pre-release | flows |  |
| 354 | "On the wire it is 96 hex digits." | pre-release | flows |  |
| 355 | "Member \| JSON type \| Presence \| Rule" | pre-release | flagged | Table header row, structure rather than a sentence |
| 356 | "`issued_at` \| string \| REQUIRED \| Section 11.1." | pre-release | flows |  |
| 357 | "`kind` \| string \| REQUIRED \| `exec` or…" | pre-release | flows |  |
| 358 | "`reply_to` \| string \| OPTIONAL \| Section 11.2." | pre-release | flows |  |
| 359 | "`script` \| string \| see 11.3 \| Inline…" | pre-release | flows |  |
| 360 | "`script_url` \| string \| see 11.3 \| `https`…" | pre-release | flows |  |
| 361 | "`script_sha384` \| string \| OPTIONAL \| 96 lowercase…" | pre-release | flows |  |
| 362 | "`interpreter` \| array of strings \| OPTIONAL \|…" | pre-release | flows |  |
| 363 | "`args` \| array of strings \| OPTIONAL \|…" | pre-release | flows |  |
| 364 | "`env` \| object \| OPTIONAL \| String values…" | pre-release | flows |  |
| 365 | "`files` \| array \| OPTIONAL \| Section 11.4." | pre-release | flows |  |
| 366 | "`timeout_sec` \| number \| OPTIONAL \| Positive integer.…" | pre-release | flows |  |
| 367 | "`issued_at` is an ISO 8601 timestamp." | pre-release | flows |  |
| 368 | "It MUST carry a timezone designator, `Z` or…" | pre-release | flows |  |
| 369 | "A value without a timezone MUST be rejected." | pre-release | flows |  |
| 370 | "A value that does not parse MUST be…" | pre-release | flows |  |
| 371 | "Senders SHOULD use UTC in the form `YYYY-MM-DDTHH:MM:SSZ`." | pre-release | flows |  |
| 372 | "Let `age` be the runner's clock minus `issued_at`,…" | pre-release | flows |  |
| 373 | "The receiver MUST reject the job if `age`…" | pre-release | flows |  |
| 374 | "The RECOMMENDED past window is 3600 seconds." | pre-release | flows |  |
| 375 | "That window is LOCAL." | pre-release | flows |  |
| 376 | "The receiver MUST reject the job if `issued_at`…" | pre-release | flows |  |
| 377 | "The RECOMMENDED future allowance is 300 seconds." | pre-release | flows |  |
| 378 | "`reply_to` is a single address, at most 254…" | pre-release | flows |  |
| 379 | "The domain contains a dot." | pre-release | flows |  |
| 380 | "If the member is absent, or present but…" | pre-release | flows |  |
| 381 | "The job is not rejected for an invalid…" | pre-release | flows |  |
| 382 | "The receiver MUST take the result address only…" | pre-release | flows |  |
| 383 | "The email `From` header and the email `Reply-To`…" | pre-release | flows |  |
| 384 | "`kind` `ping` carries no script." | pre-release | flows |  |
| 385 | "The runner MUST NOT start a script." | pre-release | flows |  |
| 386 | "The result has `kind` `ping`." | pre-release | flows |  |
| 387 | "`kind` `exec` requires at least one of `script`…" | pre-release | flows |  |
| 388 | "If neither is present, the receiver MUST reject…" | pre-release | flows |  |
| 389 | "If both are present, the receiver MUST use…" | pre-release | flows |  |
| 390 | "If `script_sha384` is present, the receiver MUST hash…" | pre-release | flows |  |
| 391 | "The digest is 96 lowercase hex digits." | pre-release | flows |  |
| 392 | "If `interpreter` is absent, the runner uses a…" | pre-release | flows |  |
| 393 | "The script is written to a new file…" | pre-release | flows |  |
| 394 | "~~~ <interpreter...> <script-file> <args...> ~~~" | pre-release | flows |  |
| 395 | "The working directory is that job directory." | pre-release | flows |  |
| 396 | "On timeout the receiver MUST kill the process…" | pre-release | flows |  |
| 397 | "A `timeout_sec` above the receiver's maximum MUST be…" | pre-release | flows |  |
| 398 | "The RECOMMENDED maximum is 3600." | pre-release | flows |  |
| 399 | "Each element is an object:" | pre-release | flows |  |
| 400 | "Member \| JSON type \| Presence \| Rule" | pre-release | flagged | Table header row, structure rather than a sentence |
| 401 | "`name` \| string \| REQUIRED \| File name…" | pre-release | flows |  |
| 402 | "`url` \| string \| REQUIRED \| `https` URL." | pre-release | flows |  |
| 403 | "`sha384` \| string \| OPTIONAL \| 96 lowercase…" | pre-release | flows |  |
| 404 | "`name` MUST NOT be absolute, MUST NOT contain…" | pre-release | flows |  |
| 405 | "A violation MUST be rejected before the file…" | pre-release | flows |  |
| 406 | "Downloads MUST use HTTPS." | pre-release | flows |  |
| 407 | "If `sha384` is present, a digest mismatch MUST…" | pre-release | flows |  |
| 408 | "Unknown `kind` MUST NOT be executed." | pre-release | flows |  |
| 409 | "A job the receiver rejects after the MAC…" | pre-release | flows |  |
| 410 | "That job MUST be marked seen and MUST…" | pre-release | flows |  |
| 411 | "A job rejected before the MAC verifies produces…" | pre-release | flows |  |
| 412 | "See Section 14." | pre-release | flows |  |
| 413 | "The result is signed with the same secret…" | pre-release | flows |  |
| 414 | "`key_id` on the result, when present, MUST name…" | pre-release | flows |  |
| 415 | "The reference sender includes it (Section 10.1): the…" | pre-release | flows |  |
| 416 | "`type` is `result`." | pre-release | flows |  |
| 417 | "The subject is the result pattern in Section…" | pre-release | flows |  |
| 418 | "~~~ json { "v": 1, "type": "result", "job_id":…" | pre-release | flows |  |
| 419 | "Member \| JSON type \| Presence \| Rule" | pre-release | flagged | Table header row, structure rather than a sentence |
| 420 | "`completed_at` \| string \| REQUIRED \| Same form…" | pre-release | flows |  |
| 421 | "`kind` \| string \| REQUIRED \| The job's…" | pre-release | flows |  |
| 422 | "`exit_code` \| number \| REQUIRED \| Section 13.1." | pre-release | flows |  |
| 423 | "`timed_out` \| boolean \| REQUIRED \| True if…" | pre-release | flows |  |
| 424 | "`stdout` \| string \| REQUIRED \| Captured standard…" | pre-release | flows |  |
| 425 | "`stderr` \| string \| REQUIRED \| Captured standard…" | pre-release | flows |  |
| 426 | "`stdout_truncated` \| boolean \| REQUIRED \| True if…" | pre-release | flows |  |
| 427 | "`stderr_truncated` \| boolean \| REQUIRED \| True if…" | pre-release | flows |  |
| 428 | "`duration_sec` \| number \| REQUIRED \| Seconds, as…" | pre-release | flows |  |
| 429 | "`runner` \| string \| REQUIRED \| Host label.…" | pre-release | flows |  |
| 430 | "Value \| Meaning" | pre-release | flows |  |
| 431 | "0 \| The process exited 0, or `ping`…" | pre-release | flows |  |
| 432 | "-1 \| `timed_out` is true. The process tree…" | pre-release | flows |  |
| 433 | "-2 \| Rejected before execution. Reason in `stderr`.…" | pre-release | flows |  |
| 434 | "other \| The process exit status." | pre-release | flows |  |
| 435 | "If `timed_out` is true, `exit_code` MUST be -1." | pre-release | flows |  |
| 436 | "Each stream MAY be cut at a LOCAL…" | pre-release | flows |  |
| 437 | "The RECOMMENDED limit is 100000 characters." | pre-release | flows |  |
| 438 | "When a stream is cut, its `*_truncated` member…" | pre-release | flows |  |
| 439 | "When it is not cut, that member MUST…" | pre-release | flows |  |
| 440 | "A result specified here includes the output the…" | pre-release | flows |  |
| 441 | "Omitting output for a local privacy policy is…" | pre-release | flows |  |
| 442 | "A submitter MUST NOT assume output will be…" | pre-release | flows |  |
| 443 | "Where a disclosure policy is layered on the…" | pre-release | flows |  |
| 444 | "The receiver maintains a seen-set." | pre-release | flows |  |
| 445 | "The key SHOULD be `job_id` prefixed by the…" | pre-release | flows |  |
| 446 | "For each unseen message:" | pre-release | flows |  |
| 447 | "If the subject is not a job subject,…" | pre-release | flows |  |
| 448 | "This is not an error." | pre-release | flows |  |
| 449 | "Stop." | pre-release | flows |  |
| 450 | "If the seen-set already contains this `job_id`, do…" | pre-release | flows |  |
| 451 | "Stop." | pre-release | flows |  |
| 452 | "If the raw message exceeds the size cap…" | pre-release | flows |  |
| 453 | "Mark seen." | pre-release | flows |  |
| 454 | "Stop." | pre-release | flows |  |
| 455 | "Select the key (Section 10)." | pre-release | flows |  |
| 456 | "On failure, reject with no result." | pre-release | flows |  |
| 457 | "Mark seen." | pre-release | flows |  |
| 458 | "Stop." | pre-release | flows |  |
| 459 | "Verify the MAC (Section 7)." | pre-release | flows |  |
| 460 | "On failure, reject with no result." | pre-release | flows |  |
| 461 | "Mark seen." | pre-release | flows |  |
| 462 | "Stop." | pre-release | flows |  |
| 463 | "The `From` header is not an input to…" | pre-release | flows |  |
| 464 | "Parse the signed octets as one JSON object." | pre-release | flows |  |
| 465 | "If it is not an object, reject with…" | pre-release | flows |  |
| 466 | "Mark seen." | pre-release | flows |  |
| 467 | "Stop." | pre-release | flows |  |
| 468 | "If `v` is not 1 or `type` is…" | pre-release | flows |  |
| 469 | "Mark seen." | pre-release | flows |  |
| 470 | "Stop." | pre-release | flows |  |
| 471 | "If the subject `job_id` and the member `job_id`…" | pre-release | flows |  |
| 472 | "Mark seen." | pre-release | flows |  |
| 473 | "Stop." | pre-release | flows |  |
| 474 | "(A `job_id` that is illegal under Section 6…" | pre-release | flows |  |
| 475 | "Check `issued_at` (Section 11.1)." | pre-release | flows |  |
| 476 | "On failure, reject with no result." | pre-release | flows |  |
| 477 | "Mark seen." | pre-release | flows |  |
| 478 | "Stop." | pre-release | flows |  |
| 479 | "LOCAL checks (audience, per-key policy) MAY reject here." | pre-release | flows |  |
| 480 | "A reject at this step MUST NOT execute…" | pre-release | flows |  |
| 481 | "Whether a result is sent is LOCAL." | pre-release | flows |  |
| 482 | "The reference receiver sends no result for an…" | pre-release | flows |  |
| 483 | "If `kind` is `ping`, go to step 13." | pre-release | flows |  |
| 484 | "If `kind` is `exec`, resolve the script and…" | pre-release | flows |  |
| 485 | "On failure, send a result with `exit_code` -2,…" | pre-release | flows |  |
| 486 | "If `kind` is anything else, send a result…" | pre-release | flows |  |
| 487 | "Execute." | pre-release | flows |  |
| 488 | "Honor `timeout_sec`." | pre-release | flows |  |
| 489 | "Build the result (Section 13) and sign it…" | pre-release | flows |  |
| 490 | "Stash the signed result in a LOCAL outbox,…" | pre-release | flows |  |
| 491 | "Send the result to `reply_to` if that member…" | pre-release | flows |  |
| 492 | "If the send fails, the stashed result is…" | pre-release | flows |  |
| 493 | "The job is never executed again (Section 15)." | pre-release | flows |  |
| 494 | "If the object verified at step 5 is…" | pre-release | flows |  |
| 495 | "The envelope's verification never substitutes for the body's…" | pre-release | flows |  |
| 496 | "The email `From` address MAY be logged after…" | pre-release | flows |  |
| 497 | "It MUST NOT authorize the job." | pre-release | flows |  |
| 498 | "It MUST NOT choose the result address." | pre-release | flows |  |
| 499 | "Execution is at most once; delivery of the…" | pre-release | flows |  |
| 500 | "A receiver MUST record `job_id` in the seen-set…" | pre-release | flows |  |
| 501 | "A send that fails is retried from the…" | pre-release | flows |  |
| 502 | "Submitters MUST still treat `exec` as repeatable: a…" | pre-release | flows |  |
| 503 | "Two senses of "seen" are kept apart." | pre-release | flows |  |
| 504 | "Marking a message seen (Section 14, steps 3…" | pre-release | flows |  |
| 505 | "Recording a `job_id` in the seen-set is the…" | pre-release | flows |  |
| 506 | "A reject that produces no result (steps 3…" | pre-release | flows |  |
| 507 | "A redelivered copy of such a message is…" | pre-release | flows |  |
| 508 | "This is deliberate: a message that never verified…" | pre-release | flows |  |
| 509 | "This section defines per-job encryption: encrypting the job…" | pre-release | flows |  |
| 510 | "It is a required part of version 1." | pre-release | flows |  |
| 511 | "Implementations MUST support receiving and decrypting objects encrypted…" | pre-release | flows |  |
| 512 | "Senders SHOULD encrypt; the reference software encrypts by…" | pre-release | flows |  |
| 513 | "A receiver MUST NOT execute a job object…" | pre-release | flows |  |
| 514 | "In the reference software the enable is a…" | pre-release | flows |  |
| 515 | "The MAC of Section 7 is verified before…" | pre-release | flows |  |
| 516 | "This section is the protocol's confidentiality mechanism at…" | pre-release | flows |  |
| 517 | "Receiver support is REQUIRED on every binding, because…" | pre-release | flows |  |
| 518 | "Sender application is OPTIONAL on a binding that…" | pre-release | flows |  |
| 519 | "On a binding that does not provide the…" | pre-release | flows |  |
| 520 | "The plaintext is the complete signed job body…" | pre-release | flows |  |
| 521 | "The cipher is AES-256-GCM {{SP800-38D}}:" | pre-release | flows |  |
| 522 | "Key: HKDF {{RFC5869}} with HMAC-SHA-384." | pre-release | flows |  |
| 523 | "The input keying material is the UTF-8 octets…" | pre-release | flows |  |
| 524 | "The salt is the nonce." | pre-release | flows |  |
| 525 | "The info string is "homing-pigeon job-encryption v1"." | pre-release | flows |  |
| 526 | "The output is 32 octets." | pre-release | flows |  |
| 527 | "Nonce: 12 octets, freshly random for each message." | pre-release | flows |  |
| 528 | "Additional authenticated data: the `job_id`, the `key_id` (empty…" | pre-release | flows |  |
| 529 | "The transmitted body is a JSON envelope object,…" | pre-release | flows |  |
| 530 | "~~~ json {"hp_enc": {"alg": "aes-256-gcm/hkdf-sha384", "nonce": "<base64>", "ct":…" | pre-release | flows |  |
| 531 | "`ct` is the ciphertext with the 16-octet GCM…" | pre-release | flows |  |
| 532 | "When the selected secret is not the default,…" | pre-release | flows |  |
| 533 | "`hp_enc` is a reserved member name: a body…" | pre-release | flows |  |
| 534 | "An envelope is processed inside Section 14's steps,…" | pre-release | flows |  |
| 535 | "The envelope's `key_id` selects the secret (Section 10),…" | pre-release | flows |  |
| 536 | "The envelope's MAC is verified — step 5…" | pre-release | flows |  |
| 537 | "On failure, reject as step 5 specifies." | pre-release | flows |  |
| 538 | "A receiver MUST NOT attempt decryption before the…" | pre-release | flows |  |
| 539 | "Decrypt." | pre-release | flows |  |
| 540 | "Any failure — an unknown `alg`, a malformed…" | pre-release | flows |  |
| 541 | "No partial plaintext is processed." | pre-release | flows |  |
| 542 | "The recovered body re-enters Section 14 at step…" | pre-release | flows |  |
| 543 | "Support of this section is REQUIRED (Section 16)." | pre-release | flows |  |
| 544 | "A receiver that does not implement it is…" | pre-release | flows |  |
| 545 | "The result for an encrypted job SHOULD be…" | pre-release | flows |  |
| 546 | "A receiver's local policy MAY override in either…" | pre-release | flows |  |
| 547 | "Per-job encryption provides confidentiality against observers of the…" | pre-release | flows |  |
| 548 | "It provides NO forward secrecy, and the two…" | pre-release | flows |  |
| 549 | "Encryption also raises the value of a captured…" | pre-release | flows |  |
| 550 | "A valid MAC is permission to run as…" | pre-release | flows |  |
| 551 | "Anyone who holds the secret can operate the…" | pre-release | flows |  |
| 552 | "This protocol does not define a sandbox." | pre-release | flows |  |
| 553 | "LOCAL confinement MUST NOT be assumed by the…" | pre-release | flows |  |
| 554 | "HMAC authenticates; it does not encrypt." | pre-release | flows |  |
| 555 | "The protocol's confidentiality is Section 16, and nothing…" | pre-release | flows |  |
| 556 | "Where cleartext is in use under an operator's…" | pre-release | flows |  |
| 557 | "With per-job encryption in use, the job and…" | pre-release | flows |  |
| 558 | "The reference software encrypts by default." | pre-release | flows |  |
| 559 | "A receiver that has not explicitly enabled cleartext…" | pre-release | flows |  |
| 560 | "Per-job encryption provides NO forward secrecy." | pre-release | flows |  |
| 561 | "Its key derives from the static shared secret,…" | pre-release | flows |  |
| 562 | "A confidentiality claim for this protocol MUST be…" | pre-release | flows |  |
| 563 | "One captured message is enough to test candidate…" | pre-release | flows |  |
| 564 | "More messages do not reduce that search." | pre-release | flows |  |
| 565 | "HMAC-SHA-384 does not yield the key from the…" | pre-release | flows |  |
| 566 | "The secret SHOULD be 32 octets from a…" | pre-release | flows |  |
| 567 | "Sixty-four hexadecimal characters are the usual form." | pre-release | flows |  |
| 568 | "A long human sentence is not a substitute." | pre-release | flows |  |
| 569 | "The secret SHOULD NOT be the mailbox password." | pre-release | flows |  |
| 570 | "The floor is normative for this protocol: the…" | pre-release | flows |  |
| 571 | "The requirement answers the offline-guessing attack above, and…" | pre-release | flows |  |
| 572 | "`From`, `Reply-To`, `Sender`, and `To` MUST NOT satisfy…" | pre-release | flows |  |
| 573 | "An invalid MAC MUST NOT cause any result…" | pre-release | flows |  |
| 574 | "Failing closed before the MAC stops a message…" | pre-release | flows |  |
| 575 | "A near-miss fingerprint is this case (Section 10.1):…" | pre-release | flows |  |
| 576 | "The past window rejects stale `issued_at`." | pre-release | flows |  |
| 577 | "The seen-set rejects a repeated `job_id`." | pre-release | flows |  |
| 578 | "A receiver with a wrong clock will accept…" | pre-release | flows |  |
| 579 | "A receiver whose seen-set is cleared will accept…" | pre-release | flows |  |
| 580 | "Jobs MUST be safe to repeat for that…" | pre-release | flows |  |
| 581 | "The transport credentials and the HMAC secret, which…" | pre-release | flows |  |
| 582 | "The splitter uses the last `,"sig":"`." | pre-release | flows |  |
| 583 | "A string value that contains that sequence will…" | pre-release | flows |  |
| 584 | "Senders MUST keep that sequence out of values." | pre-release | flows |  |
| 585 | "Version 1 results carry `stdout` and `stderr` up…" | pre-release | flows |  |
| 586 | "A receiver that wants to withhold output is…" | pre-release | flows |  |
| 587 | "That policy is not signaled by `v`." | pre-release | flows |  |
| 588 | "How that layering relates to this document is…" | pre-release | flows |  |
| 589 | "An attacker who can drop the result mail…" | pre-release | flows |  |
| 590 | "This protocol does not add a separate ack." | pre-release | flows |  |
| 591 | "This document has no IANA actions." | pre-release | flows |  |
| 592 | "No new port, service name, media type, TLS…" | pre-release | flows |  |
| 593 | "HMAC-SHA-384 is already named by {{RFC2104}} and {{FIPS180-4}}." | pre-release | flows |  |
| 594 | "The algorithm OID `hmacWithSHA384` (`1.2.840.113549.2.10`) already exists." | pre-release | flows |  |
| 595 | "This protocol identifies the algorithm by name, not…" | pre-release | flows |  |
| 596 | "The reference port for the DTLS binding (Section…" | pre-release | flows |  |
| 597 | "This section and the three that follow it…" | pre-release | flows |  |
| 598 | "The messages do not change on this binding;…" | pre-release | flows |  |
| 599 | "The store-and-forward bindings need no path between submitter…" | pre-release | flows |  |
| 600 | "That is the right default, and it is…" | pre-release | flows |  |
| 601 | "Where a direct path does exist -- the…" | pre-release | flows |  |
| 602 | "The cost is real, and it falls on…" | pre-release | flows |  |
| 603 | "The store-and-forward bindings ask the submitter only to…" | pre-release | flows |  |
| 604 | "This binding asks the submitter to terminate DTLS…" | pre-release | flows |  |
| 605 | "Many submitter environments cannot open a UDP socket…" | pre-release | flows |  |
| 606 | "That is why this binding is optional, why…" | pre-release | flows |  |
| 607 | "Section 21 states the conformance burden plainly." | pre-release | flows |  |
| 608 | "Two consequences of a direct binding deserve emphasis…" | pre-release | flows |  |
| 609 | "First, the runner listens: enabling this binding opens…" | pre-release | flows |  |
| 610 | "The binding is therefore off unless an owner…" | pre-release | flows |  |
| 611 | "Second, channel security is not delivery." | pre-release | flows |  |
| 612 | "A session protects what crosses it while it…" | pre-release | flows |  |
| 613 | "Delivery, retry, and deduplication remain the protocol's own…" | pre-release | flows |  |
| 614 | "The submitter initiates." | pre-release | flows |  |
| 615 | "The runner listens on a UDP port (LOCAL;…" | pre-release | flows |  |
| 616 | "One session carries any number of job and…" | pre-release | flows |  |
| 617 | "Roles do not reverse: the runner never initiates…" | pre-release | flows |  |
| 618 | "This binding is a bounded profile of DTLS…" | pre-release | flows |  |
| 619 | "An implementation of this binding implements exactly this…" | pre-release | flows |  |
| 620 | "Transport: DTLS 1.3 {{RFC9147}} over UDP." | pre-release | flows |  |
| 621 | "DTLS 1.2 MUST NOT be negotiated." | pre-release | flows |  |
| 622 | "Ciphersuite: TLS_AES_256_GCM_SHA384 {{RFC8446}} only." | pre-release | flows |  |
| 623 | "No other suite is offered or accepted." | pre-release | flows |  |
| 624 | "Authentication: pre-shared key only." | pre-release | flows |  |
| 625 | "The external PSK is the shared secret, under…" | pre-release | flows |  |
| 626 | "Certificates are not part of this profile, in…" | pre-release | flows |  |
| 627 | "The shared secret MUST meet the minimum-entropy floor…" | pre-release | flows |  |
| 628 | "Key exchange: `psk_dhe_ke` only." | pre-release | flows |  |
| 629 | "The `psk_key_exchange_modes` extension MUST offer mode 1 and…" | pre-release | flows |  |
| 630 | "An ephemeral X25519 {{RFC7748}} key share MUST ride…" | pre-release | flows |  |
| 631 | "Section 22.1 gives the reason: this is the…" | pre-release | flows |  |
| 632 | "Address validation: the responder MUST perform the HelloRetryRequest…" | pre-release | flows |  |
| 633 | "The cookie is stateless and is bound to…" | pre-release | flows |  |
| 634 | "Connection ID: both sides MUST negotiate the `connection_id`…" | pre-release | flows |  |
| 635 | "Retransmission: handshake flights are retransmitted on the timers…" | pre-release | flows |  |
| 636 | "Duplicate or retransmitted handshake messages are consumed exactly…" | pre-release | flows |  |
| 637 | "Early data: none." | pre-release | flows |  |
| 638 | "0-RTT MUST NOT be offered, sent, or accepted;…" | pre-release | flows |  |
| 639 | "Resumption: a responder MAY issue a NewSessionTicket." | pre-release | flows |  |
| 640 | "A resumed session MUST use a fresh ephemeral…" | pre-release | flows |  |
| 641 | "KeyUpdate: an implementation MUST NOT initiate KeyUpdate." | pre-release | flows |  |
| 642 | "An implementation that receives a KeyUpdate with `update_requested`…" | pre-release | flows |  |
| 643 | "Malformed input: a malformed or undecryptable datagram is…" | pre-release | flows |  |
| 644 | "It MUST NOT be fatal to the listener…" | pre-release | flows |  |
| 645 | "Inside a session, application data is a stream…" | pre-release | flows |  |
| 646 | "Each message is one protocol envelope in the…" | pre-release | flows |  |
| 647 | "A job message is answered, in due course,…" | pre-release | flows |  |
| 648 | "Acknowledgement and deduplication are the protocol's own, unchanged:…" | pre-release | flows |  |
| 649 | "A result produced after its session has died…" | pre-release | flows |  |
| 650 | "This binding provides the confidentiality property of Section…" | pre-release | flows |  |
| 651 | "Application of the per-job encryption of Section 16…" | pre-release | flows |  |
| 652 | "A sender may send a cleartext signed job…" | pre-release | flows |  |
| 653 | "The receiver rule of Section 16 is unchanged…" | pre-release | flows |  |
| 654 | "Receiver support of Section 16 remains REQUIRED, on…" | pre-release | flows |  |
| 655 | "Neither layer's presence relaxes the other's checks where…" | pre-release | flows |  |
| 656 | "The session's authentication of its peer does not…" | pre-release | flows |  |
| 657 | "When a session's handshake completes -- the responder…" | pre-release | flows |  |
| 658 | "Three properties are normative." | pre-release | flows |  |
| 659 | "The greeting is post-authentication, never before." | pre-release | flows |  |
| 660 | "A responder MUST NOT send it before the…" | pre-release | flows |  |
| 661 | "The greeting precedes work." | pre-release | flows |  |
| 662 | "A runner MUST NOT accept a job on…" | pre-release | flows |  |
| 663 | "The greeting is the responder's choice." | pre-release | flows |  |
| 664 | "Its disclosure tier is the runner's LOCAL configuration." | pre-release | flows |  |
| 665 | "The initiator cannot request, negotiate, or widen it;…" | pre-release | flows |  |
| 666 | "The greeting is a JSON object {{RFC8259}} in…" | pre-release | flows |  |
| 667 | "~~~ {"disclosure": "family", "platform": {"os_family": "linux", "default_interpreter": ["sh"],…" | pre-release | flows |  |
| 668 | "The members `type` (always `greeting`), `transport` (always `dtls`),…" | pre-release | flows |  |
| 669 | "The `platform` member is present unless the tier…" | pre-release | flows |  |
| 670 | "`none`: no `platform` member." | pre-release | flows |  |
| 671 | "The greeting still goes out; it says the…" | pre-release | flows |  |
| 672 | "`family`: `os_family` (one of `windows`, `macos`, `linux`, `other`),…" | pre-release | flows |  |
| 673 | "This is the reference default." | pre-release | flows |  |
| 674 | "`standard`: `family` plus `os_release` (the operating system's release…" | pre-release | flows |  |
| 675 | "`full`: `standard` plus `path_tools`, an object naming a…" | pre-release | flows |  |
| 676 | "The platform values above are strings on the…" | pre-release | flows |  |
| 677 | "The disclosure is proportioned the way the protocol…" | pre-release | flows |  |
| 678 | "The information itself is of the kind any…" | pre-release | flows |  |
| 679 | "A resumed session is a new session for…" | pre-release | flows |  |
| 680 | "This section is candid because the Introduction's promise…" | pre-release | flows |  |
| 681 | "A conforming submitter for this binding implements DTLS…" | pre-release | flows |  |
| 682 | "It needs a UDP path to the runner,…" | pre-release | flows |  |
| 683 | "None of this is required of a submitter…" | pre-release | flows |  |
| 684 | "The conformance of the messages and their checks…" | pre-release | flows |  |
| 685 | "The bindings coexist: the same runner, the same…" | pre-release | flows |  |
| 686 | "The profile's load-bearing rule is that `psk_ke` is…" | pre-release | flows |  |
| 687 | "In `psk_ke`, session keys derive from the pre-shared…" | pre-release | flows |  |
| 688 | "Because this protocol's shared secret is long-lived and…" | pre-release | flows |  |
| 689 | "In `psk_dhe_ke`, every session -- full or resumed…" | pre-release | flows |  |
| 690 | "An implementation MUST NOT offer, accept, or fall…" | pre-release | flows |  |
| 691 | "One limit is stated plainly: forward secrecy here…" | pre-release | flows |  |
| 692 | "The ephemeral exchange is X25519, so a recorded…" | pre-release | flows |  |
| 693 | "A hybrid post-quantum key exchange is the known…" | pre-release | flows |  |
| 694 | "The shared secret does two jobs on this…" | pre-release | flows |  |
| 695 | "These are independent constructions (the TLS key schedule's…" | pre-release | flows |  |
| 696 | "The composition does not weaken the analysis of…" | pre-release | flows |  |
| 697 | "The offline-guessing analysis of Section 17.3 applies to…" | pre-release | flows |  |
| 698 | "The greeting is a deliberate, bounded disclosure to…" | pre-release | flows |  |
| 699 | "Its bounds are its defenses: it is never…" | pre-release | flows |  |
| 700 | "An owner who considers even the OS family…" | pre-release | flows |  |
| 701 | "What the greeting must never become is a…" | pre-release | flows |  |
| 702 | "A UDP listener is a reflection surface." | pre-release | flows |  |
| 703 | "The cookie exchange is the mitigation this profile…" | pre-release | flows |  |
| 704 | "The listener's other exposure is computational: handshakes cost…" | pre-release | flows |  |
| 705 | "The stateless cookie keeps pre-authentication cost to one…" | pre-release | flows |  |
| 706 | "Enabling this binding changes the host's posture from…" | pre-release | flows |  |
| 707 | "DTLS authenticates and encrypts records; it does not…" | pre-release | flows |  |
| 708 | "This profile deliberately keeps the protocol's at-least-once semantics…" | pre-release | flows |  |
| 709 | "An implementation MUST NOT treat session establishment as…" | pre-release | flows |  |
| 710 | "The confidentiality claim is end to end between…" | pre-release | flows |  |
| 711 | "A middlebox that terminates DTLS -- an inspecting…" | pre-release | flows |  |
| 712 | "Deployments that route this binding through such a…" | pre-release | flows |  |
| 713 | "--- back" | pre-release | flows |  |
