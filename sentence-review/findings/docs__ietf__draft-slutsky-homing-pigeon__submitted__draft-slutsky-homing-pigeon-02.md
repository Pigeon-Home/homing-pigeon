# Findings — docs/ietf/draft-slutsky-homing-pigeon/submitted/draft-slutsky-homing-pigeon-02.md

Source: docs/ietf/draft-slutsky-homing-pigeon/submitted/draft-slutsky-homing-pigeon-02.md, reviewed at main fe5be690.
Sentence units: 763. Flagged: 98. Categories: pre-release 763, post-release 0.

The frozen submitted v1 -02 text in kramdown form: a long YAML front matter (units 2–85, title, author, and the reference entries), section markers, then the full normative prose with 5 tables. The front matter and markers are metadata and structure standing where sentences should be; the body prose connects, with field lists, ABNF, and figures flowing by the format's design. All pre-release, a frozen record.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "---" | pre-release | flagged | A document fence line ("---") standing as its own unit — structure, not a sentence |
| 2 | "title: "Homing Pigeon Message Protocol, Version 1" abbrev:…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 3 | "ins: "A." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 4 | "Slutsky" name: "Andrew Slutsky" organization: "Independent" email: "slutsky5544@gmail.com"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 5 | "normative: RFC2104: title: "HMAC: Keyed-Hashing for Message Authentication"…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 6 | "name: "H." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 7 | "Krawczyk"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 8 | "name: "M." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 9 | "Bellare"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 10 | "name: "R." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 11 | "Canetti" date: 1997-02 seriesinfo: RFC: 2104 DOI: 10.17487/RFC2104…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 12 | "name: "D." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 13 | "Crocker, Ed."" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 14 | "name: "P." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 15 | "Overell" date: 2008-01 seriesinfo: RFC: 5234 STD: 68…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 16 | "name: "H." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 17 | "Krawczyk"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 18 | "name: "P." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 19 | "Eronen" date: 2010-05 seriesinfo: RFC: 5869 DOI: 10.17487/RFC5869…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 20 | "name: "A." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 21 | "Langley"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 22 | "name: "M." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 23 | "Hamburg"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 24 | "name: "S." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 25 | "Turner" date: 2016-01 seriesinfo: RFC: 7748 DOI: 10.17487/RFC7748…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 26 | "name: "T." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 27 | "Bray, Ed." date: 2017-12 seriesinfo: RFC: 8259 STD:…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 28 | "name: "K." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 29 | "Moore"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 30 | "name: "C." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 31 | "Newman" date: 2018-01 seriesinfo: RFC: 8314 DOI: 10.17487/RFC8314…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 32 | "name: "E." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 33 | "Rescorla" date: 2018-08 seriesinfo: RFC: 8446 DOI: 10.17487/RFC8446…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 34 | "name: "K." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 35 | "Moriarty"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 36 | "name: "S." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 37 | "Farrell" date: 2021-03 seriesinfo: RFC: 8996 BCP: 195…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 38 | "name: "E." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 39 | "Rescorla, Ed."" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 40 | "name: "H." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 41 | "Tschofenig, Ed."" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 42 | "name: "T." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 43 | "Fossati"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 44 | "name: "A." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 45 | "Kraus" date: 2022-03 seriesinfo: RFC: 9146 DOI: 10.17487/RFC9146…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 46 | "name: "E." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 47 | "Rescorla"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 48 | "name: "H." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 49 | "Tschofenig"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 50 | "name: "N." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 51 | "Modadugu" date: 2022-04 seriesinfo: RFC: 9147 DOI: 10.17487/RFC9147…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 52 | "name: "Y." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 53 | "Sheffer"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 54 | "name: "P." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 55 | "Saint-Andre"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 56 | "name: "T." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 57 | "Fossati" date: 2022-11 seriesinfo: RFC: 9325 BCP: 195…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 58 | "org: National Institute of Standards and Technology date:…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 59 | "name: M." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 60 | "Dworkin date: 2007-11 seriesinfo: NIST SP: 800-38D DOI:…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 61 | "informative: RFC9562: title: "Universally Unique IDentifiers (UUIDs)" author:" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 62 | "name: "K." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 63 | "Davis"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 64 | "name: "B." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 65 | "Peabody"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 66 | "name: "P." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 67 | "Leach" date: 2024-05 seriesinfo: RFC: 9562 DOI: 10.17487/RFC9562…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 68 | "name: "M." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 69 | "Dürst"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 70 | "name: "M." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 71 | "Suignard" date: 2005-01 seriesinfo: RFC: 3987 DOI: 10.17487/RFC3987…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 72 | "name: "P." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 73 | "Resnick, Ed." date: 2008-10 seriesinfo: RFC: 5322 DOI:…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 74 | "name: "C." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 75 | "Kaufman"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 76 | "name: "P." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 77 | "Hoffman"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 78 | "name: "Y." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 79 | "Nir"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 80 | "name: "P." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 81 | "Eronen"" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 82 | "name: "T." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 83 | "Kivinen" date: 2014-09 seriesinfo: RFC: 7296 STD: 79…" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 84 | "name: "Andrew Slutsky" ins: "A." | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 85 | "Slutsky" date: 2026-10 seriesinfo: Internet-Draft: draft-slutsky-homing-pigeon-v2-00" | pre-release | flagged | A YAML front-matter shard (title, author, or reference metadata) — metadata, not a sentence |
| 86 | "--- abstract" | pre-release | flagged | A section marker ("--- abstract") standing as its own unit — structure, not a sentence |
| 87 | "This document specifies the Homing Pigeon message protocol,…" | pre-release | flows |  |
| 88 | "On the email binding, a submitter sends one…" | pre-release | flows |  |
| 89 | "The signature is the only authorization." | pre-release | flows |  |
| 90 | "The job object is protected end to end…" | pre-release | flows |  |
| 91 | "The store-and-forward bindings open no inbound listener on…" | pre-release | flows |  |
| 92 | "The DTLS binding changes the binding and not…" | pre-release | flows |  |
| 93 | "It is a binding of version 1, not…" | pre-release | flows |  |
| 94 | "The shared secret is the session's external pre-shared…" | pre-release | flows |  |
| 95 | "The binding opens an inbound listener on the…" | pre-release | flows |  |
| 96 | "It is an addition, never a replacement: the…" | pre-release | flows |  |
| 97 | "--- middle" | pre-release | flagged | A section marker ("--- middle") standing as its own unit — structure, not a sentence |
| 98 | "Some hosts cannot accept inbound connections." | pre-release | flows |  |
| 99 | "The protocol needs a store-and-forward queue so neither…" | pre-release | flows |  |
| 100 | "The first binding this document specifies is a…" | pre-release | flows |  |
| 101 | "The exchange is two messages:" | pre-release | flows |  |
| 102 | "~~~ Submitter Mailbox Runner" | pre-release | flows |  |
| 103 | "| | |" | pre-release | flows |  |
| 104 | "| job message (signed JSON) | |" | pre-release | flows |  |
| 105 | "|--------------------------->| |" | pre-release | flows |  |
| 106 | "| | poll |" | pre-release | flows |  |
| 107 | "| |<---------------------------|" | pre-release | flows |  |
| 108 | "| | result message |" | pre-release | flows |  |
| 109 | "| | (signed JSON) |" | pre-release | flows |  |
| 110 | "| |<---------------------------|" | pre-release | flows |  |
| 111 | "| result (same mailbox, or | |" | pre-release | flows |  |
| 112 | "| signed reply_to) | |" | pre-release | flows |  |
| 113 | "|<---------------------------| | ~~~" | pre-release | flows |  |
| 114 | "The deployment this protocol is written for is…" | pre-release | flows |  |
| 115 | "The person holds the mailbox and the secret;…" | pre-release | flows |  |
| 116 | "Email is the path that already exists between…" | pre-release | flows |  |
| 117 | "The runner is deliberately plain: it executes what…" | pre-release | flows |  |
| 118 | "Version negotiation is not a handshake." | pre-release | flows |  |
| 119 | "The message carries `v`." | pre-release | flows |  |
| 120 | "This document defines `v` = 1 only." | pre-release | flows |  |
| 121 | "A receiver that does not implement version 1…" | pre-release | flows |  |
| 122 | "The protocol is specified in the open so…" | pre-release | flows |  |
| 123 | "Any implementation of this document can submit jobs:…" | pre-release | flows |  |
| 124 | "Two things are out of scope for this…" | pre-release | flows |  |
| 125 | "The sender asks the owner which address to…" | pre-release | flows |  |
| 126 | "Neither is discovered from the mail." | pre-release | flows |  |
| 127 | "Once the sender knows the address, the secret,…" | pre-release | flows |  |
| 128 | "This document specifies one version of the protocol:…" | pre-release | flows |  |
| 129 | "Its bindings are the email binding (Section 5),…" | pre-release | flows |  |
| 130 | "It consolidates this document's earlier text, which specified…" | pre-release | flows |  |
| 131 | "The companion draft that now carries the name…" | pre-release | flows |  |
| 132 | "A binding does not version the messages." | pre-release | flows |  |
| 133 | "The job and result objects are the same…" | pre-release | flows |  |
| 134 | "A receiver that does not offer a binding…" | pre-release | flows |  |
| 135 | "The reference implementation speaks version 1, and it…" | pre-release | flows |  |
| 136 | "A receiver following this document rejects any message…" | pre-release | flows |  |
| 137 | "The sender also requires the shared secret to…" | pre-release | flows |  |
| 138 | "That floor is not a protocol version; it…" | pre-release | flows |  |
| 139 | "Nothing else in the exchange changes shape." | pre-release | flows |  |
| 140 | "Later work also layers behavior this document scopes…" | pre-release | flows |  |
| 141 | "Those behaviors ride in extra members (Section 8);…" | pre-release | flows |  |
| 142 | "One consequence a submitter needs: a receiver layered…" | pre-release | flows |  |
| 143 | "{::boilerplate bcp14-tagged}" | pre-release | flows |  |
| 144 | "Job: a signed request that the runner execute…" | pre-release | flows |  |
| 145 | "Result: a signed report of what the runner…" | pre-release | flows |  |
| 146 | "Shared secret: an octet string known to the…" | pre-release | flows |  |
| 147 | "It is the HMAC key." | pre-release | flows |  |
| 148 | "It is not sent on the wire." | pre-release | flows |  |
| 149 | "Default secret: the shared secret selected when `key_id`…" | pre-release | flows |  |
| 150 | "Key identifier: the string in `key_id`." | pre-release | flows |  |
| 151 | "It is a label, not a secret." | pre-release | flows |  |
| 152 | "Seen-set: the runner's record of `job_id` values already…" | pre-release | flows |  |
| 153 | "It is local state." | pre-release | flows |  |
| 154 | "It is not a message." | pre-release | flows |  |
| 155 | "Freshness window: how far `issued_at` may be from…" | pre-release | flows |  |
| 156 | "Preamble: text in the message body before the…" | pre-release | flows |  |
| 157 | "It is not signed." | pre-release | flows |  |
| 158 | "LOCAL: a parameter or a check this document…" | pre-release | flows |  |
| 159 | "It is not negotiated." | pre-release | flows |  |
| 160 | "Session: one DTLS association between a submitter (the…" | pre-release | flows |  |
| 161 | "Defined in Section 19." | pre-release | flows |  |
| 162 | "Platform disclosure: the runner's summary of its platform,…" | pre-release | flows |  |
| 163 | "PSK identity: the `pre_shared_key` identity under which a…" | pre-release | flows |  |
| 164 | "The default secret's identity is `homing-pigeon`; an additional…" | pre-release | flows |  |
| 165 | "Ticket: the opaque resumption identity a runner issues…" | pre-release | flows |  |
| 166 | "This document specifies subjects, the signed object, the…" | pre-release | flows |  |
| 167 | "This document does not specify disclosure policy, queries,…" | pre-release | flows |  |
| 168 | "A job MAY carry extra members for those…" | pre-release | flows |  |
| 169 | "Receivers that do not implement them MUST ignore…" | pre-release | flows |  |
| 170 | "Section 1 describes how those uses relate to…" | pre-release | flows |  |
| 171 | "This section specifies the email binding." | pre-release | flows |  |
| 172 | "The protocol itself needs only the store-and-forward queue…" | pre-release | flows |  |
| 173 | "Further bindings are specified in Sections 5.1 and…" | pre-release | flows |  |
| 174 | "A direct session binding, in which the same…" | pre-release | flows |  |
| 175 | "The binding layer is abstract." | pre-release | flows |  |
| 176 | "A binding is an interchangeable carrier of the…" | pre-release | flows |  |
| 177 | "An implementation MAY substitute one binding for another,…" | pre-release | flows |  |
| 178 | "Conformance is per binding." | pre-release | flows |  |
| 179 | "This document specifies one version of the protocol,…" | pre-release | flows |  |
| 180 | "Pairing is established out of band (Section 1)…" | pre-release | flows |  |
| 181 | "The email binding of this section is the…" | pre-release | flows |  |
| 182 | "Two security properties are REQUIRED of the protocol…" | pre-release | flows |  |
| 183 | "The first is authentication of the object: the…" | pre-release | flows |  |
| 184 | "That requirement attaches to the object, never to…" | pre-release | flows |  |
| 185 | "No authentication a binding performs, however strong, satisfies…" | pre-release | flows |  |
| 186 | "The second is confidentiality of the object, in…" | pre-release | flows |  |
| 187 | "That requirement attaches to the property, not to…" | pre-release | flows |  |
| 188 | "A binding whose carriage provides confidentiality end to…" | pre-release | flows |  |
| 189 | "Where a binding's carriage terminates at an intermediary,…" | pre-release | flows |  |
| 190 | "Each binding specified in this document states which…" | pre-release | flows |  |
| 191 | "The runner reads the mailbox with IMAP and…" | pre-release | flows |  |
| 192 | "Mail authentication is out of band." | pre-release | flows |  |
| 193 | "The signature check does not change with the…" | pre-release | flows |  |
| 194 | "IMAP and SMTP MUST be used over TLS." | pre-release | flows |  |
| 195 | "An implementation MUST NOT carry this protocol over…" | pre-release | flows |  |
| 196 | "The TLS version MUST be 1.2 or higher;…" | pre-release | flows |  |
| 197 | "The recommendations of {{RFC9325}} apply." | pre-release | flows |  |
| 198 | "Cleartext mail access is obsolete {{RFC8314}}: implicit TLS…" | pre-release | flows |  |
| 199 | "TLS protects a hop." | pre-release | flows |  |
| 200 | "It does not hide the message from the…" | pre-release | flows |  |
| 201 | "The TLS requirements of this section therefore do…" | pre-release | flows |  |
| 202 | "On this binding the confidentiality property is carried…" | pre-release | flows |  |
| 203 | "An implementation MAY additionally support PGP/MIME protection of…" | pre-release | flows |  |
| 204 | "Such support is not required, and it is…" | pre-release | flows |  |
| 205 | "The body is UTF-8 text in a `text/plain`…" | pre-release | flows |  |
| 206 | "This document does not register a media type." | pre-release | flows |  |
| 207 | "If the message is multipart, the receiver uses…" | pre-release | flows |  |
| 208 | "The message MUST be rejected before the MAC…" | pre-release | flows |  |
| 209 | "The RECOMMENDED cap is 4194304 octets." | pre-release | flows |  |
| 210 | "A cap of 0 means no limit." | pre-release | flows |  |
| 211 | "This cap is LOCAL." | pre-release | flows |  |
| 212 | "The file binding carries the same envelope as…" | pre-release | flows |  |
| 213 | "It exists for deployments where the submitter and…" | pre-release | flows |  |
| 214 | "The envelope mapping is byte-for-byte the email form:…" | pre-release | flows |  |
| 215 | "A job is a regular file in the…" | pre-release | flows |  |
| 216 | "The file SHOULD be named `<ident>.job.txt`, where `<ident>`…" | pre-release | flows |  |
| 217 | "A result is a file named `<ident>.result.txt` in…" | pre-release | flows |  |
| 218 | "A receiver polls the directories on its ordinary…" | pre-release | flows |  |
| 219 | "Acknowledgement is consumption." | pre-release | flows |  |
| 220 | "Whichever side has taken a file moves it…" | pre-release | flows |  |
| 221 | "A redelivery of the same job rewrites the…" | pre-release | flows |  |
| 222 | "Two gates stand in series on this binding." | pre-release | flows |  |
| 223 | "The first is the inbox directory's operating-system access…" | pre-release | flows |  |
| 224 | "The second is the signature, which remains the…" | pre-release | flows |  |
| 225 | "A deployment MUST treat the directory's access control…" | pre-release | flows |  |
| 226 | "The binding's limits are the filesystem's." | pre-release | flows |  |
| 227 | "Both parties need access to the same directories,…" | pre-release | flows |  |
| 228 | "There is no store-and-forward beyond the disk, no…" | pre-release | flows |  |
| 229 | "Of the two security properties of Section 5,…" | pre-release | flows |  |
| 230 | "The MAC carries the authentication property, as on…" | pre-release | flows |  |
| 231 | "Whether Section 16 is applied on this binding…" | pre-release | flows |  |
| 232 | "The NATS binding carries the same envelope over…" | pre-release | flows |  |
| 233 | "It exists for deployments where submitter and runner…" | pre-release | flows |  |
| 234 | "The envelope mapping is the email form carried…" | pre-release | flows |  |
| 235 | "Jobs are published on a jobs subject (a…" | pre-release | flows |  |
| 236 | "Results are published on a per-job subject formed…" | pre-release | flows |  |
| 237 | "Core NATS is at-most-once: the broker acknowledges nothing…" | pre-release | flows |  |
| 238 | "A job published while no runner is subscribed…" | pre-release | flows |  |
| 239 | "The protocol's own machinery is the recovery: the…" | pre-release | flows |  |
| 240 | "A deployment that needs broker-side retention needs a…" | pre-release | flows |  |
| 241 | "Two gates stand in series." | pre-release | flows |  |
| 242 | "The first is the broker's own authentication: broker…" | pre-release | flows |  |
| 243 | "A deployment MAY relax this by an explicit…" | pre-release | flows |  |
| 244 | "The second gate is the signature, unchanged." | pre-release | flows |  |
| 245 | "A required-auth NATS deployment is, for this reason,…" | pre-release | flows |  |
| 246 | "The binding's limits are the broker's: payload sizes…" | pre-release | flows |  |
| 247 | "Of the two security properties of Section 5,…" | pre-release | flows |  |
| 248 | "TLS on a broker connection, where a deployment…" | pre-release | flows |  |
| 249 | "The MAC therefore carries the authentication property on…" | pre-release | flows |  |
| 250 | "Subjects are part of the email binding (Section…" | pre-release | flows |  |
| 251 | "Subjects are matched case-insensitively." | pre-release | flows |  |
| 252 | "A preamble such as `Re:` MAY appear before…" | pre-release | flows |  |
| 253 | "The marker need not be the first character…" | pre-release | flows |  |
| 254 | "A job or result subject matches this grammar,…" | pre-release | flows |  |
| 255 | "The grammar is ABNF {{RFC5234}} written over Unicode…" | pre-release | flows |  |
| 256 | "A gap is one or more characters of…" | pre-release | flows |  |
| 257 | "The set is the ECMAScript WhiteSpace and LineTerminator…" | pre-release | flows |  |
| 258 | "~~~ job-subject = marker *( gap word )…" | pre-release | flows |  |
| 259 | "`word-char` excludes the gap set by the prose…" | pre-release | flows |  |
| 260 | "A control character other than those listed in…" | pre-release | flows |  |
| 261 | "The words between the marker and `job` are…" | pre-release | flows |  |
| 262 | "`TEST` is a legal decoration." | pre-release | flows |  |
| 263 | "The `job_id` in the subject MUST equal the…" | pre-release | flows |  |
| 264 | "A mismatch MUST be rejected (Section 14)." | pre-release | flows |  |
| 265 | "`job-id` MUST NOT be `.` or `..`." | pre-release | flows |  |
| 266 | "A UUID {{RFC9562}} is RECOMMENDED as the `job_id`." | pre-release | flows |  |
| 267 | "A message whose subject is not a job…" | pre-release | flows |  |
| 268 | "The receiver MUST NOT execute it." | pre-release | flows |  |
| 269 | "The receiver MAY mark it seen so that…" | pre-release | flows |  |
| 270 | "Result messages use the result pattern above and…" | pre-release | flows |  |
| 271 | "They are not jobs." | pre-release | flows |  |
| 272 | "The signed object is one JSON object {{RFC8259}}." | pre-release | flows |  |
| 273 | "The receiver ignores preamble and trailer." | pre-release | flows |  |
| 274 | "Verification uses the object that ends in the…" | pre-release | flows |  |
| 275 | "Line endings are normalized before both signing and…" | pre-release | flows |  |
| 276 | "Trailing whitespace after that normalization is not part…" | pre-release | flows |  |
| 277 | "The sender builds the object without `sig`, serializes…" | pre-release | flows |  |
| 278 | "~~~ ,"sig":"<96 hex digits>"} ~~~" | pre-release | flows |  |
| 279 | "JSON member order before `sig` is the sender's…" | pre-release | flows |  |
| 280 | "`sig` MUST be last." | pre-release | flows |  |
| 281 | "Senders SHOULD serialize with no insignificant whitespace." | pre-release | flows |  |
| 282 | "Receivers MUST accept insignificant whitespace inside the object,…" | pre-release | flows |  |
| 283 | "The receiver finds the signature as follows:" | pre-release | flows |  |
| 284 | "Normalize line endings and remove trailing whitespace." | pre-release | flows |  |
| 285 | "Let `marker` be the last occurrence of the…" | pre-release | flows |  |
| 286 | "If `marker` is absent, the message is malformed." | pre-release | flows |  |
| 287 | "The 96 characters after `marker` MUST be hexadecimal." | pre-release | flows |  |
| 288 | "The two characters after those MUST be `"`…" | pre-release | flows |  |
| 289 | "The signed octets are the bytes from the…" | pre-release | flows |  |
| 290 | "That `{` is the start of the object…" | pre-release | flows |  |
| 291 | "If no such `{` exists, the message is…" | pre-release | flows |  |
| 292 | "A sender MUST NOT place the character sequence…" | pre-release | flows |  |
| 293 | "The receiver uses the last occurrence." | pre-release | flows |  |
| 294 | "The MAC is HMAC-SHA-384 {{RFC2104}} using SHA-384 {{FIPS180-4}}." | pre-release | flows |  |
| 295 | "The HMAC key is the UTF-8 octets of…" | pre-release | flows |  |
| 296 | "Implementations MUST NOT hash, stretch, or otherwise derive…" | pre-release | flows |  |
| 297 | "The secret is a string of characters." | pre-release | flows |  |
| 298 | "Two sides that disagree on the characters disagree…" | pre-release | flows |  |
| 299 | "`sig` is the 48-octet HMAC value encoded as…" | pre-release | flows |  |
| 300 | "Senders MUST use lowercase digits." | pre-release | flows |  |
| 301 | "Receivers MUST compare in constant time after mapping…" | pre-release | flows |  |
| 302 | "Receivers MUST reject a malformed tail." | pre-release | flows |  |
| 303 | "Receivers MUST reject a MAC mismatch." | pre-release | flows |  |
| 304 | "A mismatch produces no result message (Section 14)." | pre-release | flows |  |
| 305 | "The compare covers all 96 digits." | pre-release | flows |  |
| 306 | "It MUST NOT stop at the first differing…" | pre-release | flows |  |
| 307 | "A local reject log MAY record that the…" | pre-release | flows |  |
| 308 | "It SHOULD NOT record the expected digest." | pre-release | flows |  |
| 309 | "A receiver MUST ignore object members it does…" | pre-release | flows |  |
| 310 | "`v` other than 1 MUST be rejected" | pre-release | flows |  |
| 311 | "`type` other than `job`, on a message the…" | pre-release | flows |  |
| 312 | "`kind` other than `exec` or `ping` MUST NOT…" | pre-release | flows |  |
| 313 | "Ignoring a member means the member is still…" | pre-release | flows |  |
| 314 | "| Member | JSON type | Presence |…" | pre-release | flagged | A table header row — structure, not a sentence |
| 315 | "|---|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 316 | "| `v` | number | REQUIRED | Integer…" | pre-release | flows |  |
| 317 | "No other value is defined. |" | pre-release | flows |  |
| 318 | "| `type` | string | REQUIRED | `job`…" | pre-release | flows |  |
| 319 | "| `job_id` | string | REQUIRED | Section…" | pre-release | flows |  |
| 320 | "| `key_id` | string | OPTIONAL | Selects…" | pre-release | flows |  |
| 321 | "Absent selects the default secret. |" | pre-release | flows |  |
| 322 | "| `aud` | string | OPTIONAL | Audience…" | pre-release | flows |  |
| 323 | "Enforcement is LOCAL." | pre-release | flows |  |
| 324 | "`runner_id` is accepted as its older spelling; when…" | pre-release | flows |  |
| 325 | "| `sig` | string | REQUIRED | Section…" | pre-release | flows |  |
| 326 | "Not part of the signed octets. |" | pre-release | flows |  |
| 327 | "`key_id` is covered by the MAC." | pre-release | flows |  |
| 328 | "Key identifiers MAY appear in logs." | pre-release | flows |  |
| 329 | "An unknown `key_id` MUST be rejected before the…" | pre-release | flows |  |
| 330 | "The receiver MUST NOT try another secret." | pre-release | flows |  |
| 331 | "If a receiver enforces `runner_id`, the expected value…" | pre-release | flows |  |
| 332 | "The signed value is what the submitter claimed." | pre-release | flows |  |
| 333 | "It is not the source of the expected…" | pre-release | flows |  |
| 334 | "The receiver holds a map from `key_id` to…" | pre-release | flows |  |
| 335 | "The empty identifier names the default secret." | pre-release | flows |  |
| 336 | "Selection, before the MAC:" | pre-release | flows |  |
| 337 | "If `key_id` is absent, select the default secret." | pre-release | flows |  |
| 338 | "If `key_id` is present and is a string…" | pre-release | flows |  |
| 339 | "Otherwise reject." | pre-release | flows |  |
| 340 | "Do not compute a MAC." | pre-release | flows |  |
| 341 | "How keys are stored is LOCAL." | pre-release | flows |  |
| 342 | "Two values MUST NOT be assigned to one…" | pre-release | flows |  |
| 343 | "The default identifier has one slot." | pre-release | flows |  |
| 344 | "A secret MAY be named by its fingerprint." | pre-release | flows |  |
| 345 | "The reference software does so." | pre-release | flows |  |
| 346 | "The fingerprint is `k-` followed by the first…" | pre-release | flows |  |
| 347 | "~~~ key_id = "k-" || hex(SHA-384("homing-pigeon key id…" | pre-release | flows |  |
| 348 | "The reference receiver puts that identifier in the…" | pre-release | flows |  |
| 349 | "An operator-chosen name, when one was configured, is…" | pre-release | flows |  |
| 350 | "One `key_id` still names one secret." | pre-release | flows |  |
| 351 | "One secret MAY have several identifiers." | pre-release | flows |  |
| 352 | "Two secrets MUST NOT share one." | pre-release | flows |  |
| 353 | "The reference sender includes `key_id` on every message…" | pre-release | flows |  |
| 354 | "The value is the fingerprint, unless the sender…" | pre-release | flows |  |
| 355 | "The empty identifier is how a sender asks…" | pre-release | flows |  |
| 356 | "A receiver that has not registered the fingerprint…" | pre-release | flows |  |
| 357 | "An absent `key_id` still selects the default secret." | pre-release | flows |  |
| 358 | "A fingerprint that is not in the map…" | pre-release | flows |  |
| 359 | "So is a near-miss: a different length, a…" | pre-release | flows |  |
| 360 | "The receiver MUST NOT select the default secret…" | pre-release | flows |  |
| 361 | "The name is a label." | pre-release | flows |  |
| 362 | "It is 32 bits of a one-way function…" | pre-release | flows |  |
| 363 | "It is not invertible." | pre-release | flows |  |
| 364 | "As an oracle for a guessed secret it…" | pre-release | flows |  |
| 365 | "The label keeps this hash apart from that…" | pre-release | flows |  |
| 366 | "Publishing the name discloses nothing a signed message…" | pre-release | flows |  |
| 367 | "The DTLS PSK identity (Section 3) is a…" | pre-release | flows |  |
| 368 | "`homing-pigeon` names the default secret." | pre-release | flows |  |
| 369 | "`homing-pigeon:` followed by a configured `key_id` names an…" | pre-release | flows |  |
| 370 | "The fingerprint is not a PSK identity unless…" | pre-release | flows |  |
| 371 | "`type` is `job`." | pre-release | flows |  |
| 372 | "~~~ json { "v": 1, "type": "job", "job_id":…" | pre-release | flows |  |
| 373 | "The `sig` line above is abbreviated." | pre-release | flows |  |
| 374 | "On the wire it is 96 hex digits." | pre-release | flows |  |
| 375 | "| Member | JSON type | Presence |…" | pre-release | flagged | A table header row — structure, not a sentence |
| 376 | "|---|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 377 | "| `issued_at` | string | REQUIRED | Section…" | pre-release | flows |  |
| 378 | "| `kind` | string | REQUIRED | `exec`…" | pre-release | flows |  |
| 379 | "| `reply_to` | string | OPTIONAL | Section…" | pre-release | flows |  |
| 380 | "| `script` | string | see 11.3 |…" | pre-release | flows |  |
| 381 | "`exec` only. |" | pre-release | flows |  |
| 382 | "| `script_url` | string | see 11.3 |…" | pre-release | flows |  |
| 383 | "`exec` only. |" | pre-release | flows |  |
| 384 | "| `script_sha384` | string | OPTIONAL | 96…" | pre-release | flows |  |
| 385 | "| `interpreter` | array of strings | OPTIONAL…" | pre-release | flows |  |
| 386 | "| `args` | array of strings | OPTIONAL…" | pre-release | flows |  |
| 387 | "| `env` | object | OPTIONAL | String…" | pre-release | flows |  |
| 388 | "| `files` | array | OPTIONAL | Section…" | pre-release | flows |  |
| 389 | "| `timeout_sec` | number | OPTIONAL | Positive…" | pre-release | flows |  |
| 390 | "RECOMMENDED default 300." | pre-release | flows |  |
| 391 | "RECOMMENDED maximum 3600. |" | pre-release | flows |  |
| 392 | "`issued_at` is an ISO 8601 timestamp." | pre-release | flows |  |
| 393 | "It MUST carry a timezone designator, `Z` or…" | pre-release | flows |  |
| 394 | "A value without a timezone MUST be rejected." | pre-release | flows |  |
| 395 | "A value that does not parse MUST be…" | pre-release | flows |  |
| 396 | "Senders SHOULD use UTC in the form `YYYY-MM-DDTHH:MM:SSZ`." | pre-release | flows |  |
| 397 | "Let `age` be the runner's clock minus `issued_at`,…" | pre-release | flows |  |
| 398 | "The receiver MUST reject the job if `age`…" | pre-release | flows |  |
| 399 | "The RECOMMENDED past window is 3600 seconds." | pre-release | flows |  |
| 400 | "That window is LOCAL." | pre-release | flows |  |
| 401 | "The receiver MUST reject the job if `issued_at`…" | pre-release | flows |  |
| 402 | "The RECOMMENDED future allowance is 300 seconds." | pre-release | flows |  |
| 403 | "`reply_to` is a single address, at most 254…" | pre-release | flows |  |
| 404 | "The domain contains a dot." | pre-release | flows |  |
| 405 | "If the member is absent, or present but…" | pre-release | flows |  |
| 406 | "The job is not rejected for an invalid…" | pre-release | flows |  |
| 407 | "The receiver MUST take the result address only…" | pre-release | flows |  |
| 408 | "The email `From` header and the email `Reply-To`…" | pre-release | flows |  |
| 409 | "`kind` `ping` carries no script." | pre-release | flows |  |
| 410 | "The runner MUST NOT start a script." | pre-release | flows |  |
| 411 | "The result has `kind` `ping`." | pre-release | flows |  |
| 412 | "`kind` `exec` requires at least one of `script`…" | pre-release | flows |  |
| 413 | "If neither is present, the receiver MUST reject…" | pre-release | flows |  |
| 414 | "If both are present, the receiver MUST use…" | pre-release | flows |  |
| 415 | "If `script_sha384` is present, the receiver MUST hash…" | pre-release | flows |  |
| 416 | "The digest is 96 lowercase hex digits." | pre-release | flows |  |
| 417 | "If `interpreter` is absent, the runner uses a…" | pre-release | flows |  |
| 418 | "The script is written to a new file…" | pre-release | flows |  |
| 419 | "~~~ <interpreter...> <script-file> <args...> ~~~" | pre-release | flows |  |
| 420 | "The working directory is that job directory." | pre-release | flows |  |
| 421 | "On timeout the receiver MUST kill the process…" | pre-release | flows |  |
| 422 | "A `timeout_sec` above the receiver's maximum MUST be…" | pre-release | flows |  |
| 423 | "The RECOMMENDED maximum is 3600." | pre-release | flows |  |
| 424 | "Each element is an object:" | pre-release | flows |  |
| 425 | "| Member | JSON type | Presence |…" | pre-release | flagged | A table header row — structure, not a sentence |
| 426 | "|---|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 427 | "| `name` | string | REQUIRED | File…" | pre-release | flows |  |
| 428 | "| `url` | string | REQUIRED | `https`…" | pre-release | flows |  |
| 429 | "| `sha384` | string | OPTIONAL | 96…" | pre-release | flows |  |
| 430 | "`name` MUST NOT be absolute, MUST NOT contain…" | pre-release | flows |  |
| 431 | "A violation MUST be rejected before the file…" | pre-release | flows |  |
| 432 | "Downloads MUST use HTTPS." | pre-release | flows |  |
| 433 | "If `sha384` is present, a digest mismatch MUST…" | pre-release | flows |  |
| 434 | "Unknown `kind` MUST NOT be executed." | pre-release | flows |  |
| 435 | "A job the receiver rejects after the MAC…" | pre-release | flows |  |
| 436 | "That job MUST be marked seen and MUST…" | pre-release | flows |  |
| 437 | "A job rejected before the MAC verifies produces…" | pre-release | flows |  |
| 438 | "See Section 14." | pre-release | flows |  |
| 439 | "The result is signed with the same secret…" | pre-release | flows |  |
| 440 | "`key_id` on the result, when present, MUST name…" | pre-release | flows |  |
| 441 | "The reference sender includes it (Section 10.1): the…" | pre-release | flows |  |
| 442 | "`type` is `result`." | pre-release | flows |  |
| 443 | "The subject is the result pattern in Section…" | pre-release | flows |  |
| 444 | "~~~ json { "v": 1, "type": "result", "job_id":…" | pre-release | flows |  |
| 445 | "| Member | JSON type | Presence |…" | pre-release | flagged | A table header row — structure, not a sentence |
| 446 | "|---|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 447 | "| `completed_at` | string | REQUIRED | Same…" | pre-release | flows |  |
| 448 | "| `kind` | string | REQUIRED | The…" | pre-release | flows |  |
| 449 | "| `exit_code` | number | REQUIRED | Section…" | pre-release | flows |  |
| 450 | "| `timed_out` | boolean | REQUIRED | True…" | pre-release | flows |  |
| 451 | "| `stdout` | string | REQUIRED | Captured…" | pre-release | flows |  |
| 452 | "May be empty. |" | pre-release | flows |  |
| 453 | "| `stderr` | string | REQUIRED | Captured…" | pre-release | flows |  |
| 454 | "May be empty. |" | pre-release | flows |  |
| 455 | "| `stdout_truncated` | boolean | REQUIRED | True…" | pre-release | flows |  |
| 456 | "| `stderr_truncated` | boolean | REQUIRED | True…" | pre-release | flows |  |
| 457 | "| `duration_sec` | number | REQUIRED | Seconds,…" | pre-release | flows |  |
| 458 | "| `runner` | string | REQUIRED | Host…" | pre-release | flows |  |
| 459 | "Authenticated only by the result MAC. |" | pre-release | flows |  |
| 460 | "| Value | Meaning |" | pre-release | flagged | A table header row — structure, not a sentence |
| 461 | "|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 462 | "| 0 | The process exited 0, or…" | pre-release | flows |  |
| 463 | "| -1 | `timed_out` is true." | pre-release | flows |  |
| 464 | "The process tree was killed. |" | pre-release | flows |  |
| 465 | "| -2 | Rejected before execution." | pre-release | flows |  |
| 466 | "Reason in `stderr`." | pre-release | flows |  |
| 467 | "Not retried. |" | pre-release | flows |  |
| 468 | "| other | The process exit status. |" | pre-release | flows |  |
| 469 | "If `timed_out` is true, `exit_code` MUST be -1." | pre-release | flows |  |
| 470 | "Each stream MAY be cut at a LOCAL…" | pre-release | flows |  |
| 471 | "The RECOMMENDED limit is 100000 characters." | pre-release | flows |  |
| 472 | "When a stream is cut, its `*_truncated` member…" | pre-release | flows |  |
| 473 | "When it is not cut, that member MUST…" | pre-release | flows |  |
| 474 | "A result specified here includes the output the…" | pre-release | flows |  |
| 475 | "Omitting output for a local privacy policy is…" | pre-release | flows |  |
| 476 | "A submitter MUST NOT assume output will be…" | pre-release | flows |  |
| 477 | "Where a disclosure policy is layered on the…" | pre-release | flows |  |
| 478 | "The receiver maintains a seen-set." | pre-release | flows |  |
| 479 | "The key SHOULD be `job_id` prefixed by the…" | pre-release | flows |  |
| 480 | "For each unseen message:" | pre-release | flows |  |
| 481 | "If the subject is not a job subject,…" | pre-release | flows |  |
| 482 | "This is not an error." | pre-release | flows |  |
| 483 | "Stop." | pre-release | flows |  |
| 484 | "If the seen-set already contains this `job_id`, do…" | pre-release | flows |  |
| 485 | "Stop." | pre-release | flows |  |
| 486 | "If the raw message exceeds the size cap…" | pre-release | flows |  |
| 487 | "Mark seen." | pre-release | flows |  |
| 488 | "Stop." | pre-release | flows |  |
| 489 | "Select the key (Section 10)." | pre-release | flows |  |
| 490 | "On failure, reject with no result." | pre-release | flows |  |
| 491 | "Mark seen." | pre-release | flows |  |
| 492 | "Stop." | pre-release | flows |  |
| 493 | "Verify the MAC (Section 7)." | pre-release | flows |  |
| 494 | "On failure, reject with no result." | pre-release | flows |  |
| 495 | "Mark seen." | pre-release | flows |  |
| 496 | "Stop." | pre-release | flows |  |
| 497 | "The `From` header is not an input to…" | pre-release | flows |  |
| 498 | "Parse the signed octets as one JSON object." | pre-release | flows |  |
| 499 | "If it is not an object, reject with…" | pre-release | flows |  |
| 500 | "Mark seen." | pre-release | flows |  |
| 501 | "Stop." | pre-release | flows |  |
| 502 | "If `v` is not 1 or `type` is…" | pre-release | flows |  |
| 503 | "Mark seen." | pre-release | flows |  |
| 504 | "Stop." | pre-release | flows |  |
| 505 | "If the subject `job_id` and the member `job_id`…" | pre-release | flows |  |
| 506 | "Mark seen." | pre-release | flows |  |
| 507 | "Stop. (A `job_id` that is illegal under Section…" | pre-release | flows |  |
| 508 | "Check `issued_at` (Section 11.1)." | pre-release | flows |  |
| 509 | "On failure, reject with no result." | pre-release | flows |  |
| 510 | "Mark seen." | pre-release | flows |  |
| 511 | "Stop." | pre-release | flows |  |
| 512 | "LOCAL checks (audience, per-key policy) MAY reject here." | pre-release | flows |  |
| 513 | "A reject at this step MUST NOT execute…" | pre-release | flows |  |
| 514 | "Whether a result is sent is LOCAL." | pre-release | flows |  |
| 515 | "The reference receiver sends no result for an…" | pre-release | flows |  |
| 516 | "If `kind` is `ping`, go to step 13." | pre-release | flows |  |
| 517 | "If `kind` is `exec`, resolve the script and…" | pre-release | flows |  |
| 518 | "On failure, send a result with `exit_code` -2,…" | pre-release | flows |  |
| 519 | "If `kind` is anything else, send a result…" | pre-release | flows |  |
| 520 | "Execute." | pre-release | flows |  |
| 521 | "Honor `timeout_sec`." | pre-release | flows |  |
| 522 | "Build the result (Section 13) and sign it…" | pre-release | flows |  |
| 523 | "Stash the signed result in a LOCAL outbox,…" | pre-release | flows |  |
| 524 | "Send the result to `reply_to` if that member…" | pre-release | flows |  |
| 525 | "If the send fails, the stashed result is…" | pre-release | flows |  |
| 526 | "The job is never executed again (Section 15)." | pre-release | flows |  |
| 527 | "If the object verified at step 5 is…" | pre-release | flows |  |
| 528 | "The envelope's verification never substitutes for the body's…" | pre-release | flows |  |
| 529 | "The email `From` address MAY be logged after…" | pre-release | flows |  |
| 530 | "It MUST NOT authorize the job." | pre-release | flows |  |
| 531 | "It MUST NOT choose the result address." | pre-release | flows |  |
| 532 | "Execution is at most once; delivery of the…" | pre-release | flows |  |
| 533 | "A receiver MUST record `job_id` in the seen-set…" | pre-release | flows |  |
| 534 | "A send that fails is retried from the…" | pre-release | flows |  |
| 535 | "Submitters MUST still treat `exec` as repeatable: a…" | pre-release | flows |  |
| 536 | "Two senses of "seen" are kept apart." | pre-release | flows |  |
| 537 | "Marking a message seen (Section 14, steps 3…" | pre-release | flows |  |
| 538 | "Recording a `job_id` in the seen-set is the…" | pre-release | flows |  |
| 539 | "A reject that produces no result (steps 3…" | pre-release | flows |  |
| 540 | "A redelivered copy of such a message is…" | pre-release | flows |  |
| 541 | "This is deliberate: a message that never verified…" | pre-release | flows |  |
| 542 | "This section defines per-job encryption: encrypting the job…" | pre-release | flows |  |
| 543 | "It is a required part of version 1." | pre-release | flows |  |
| 544 | "Implementations MUST support receiving and decrypting objects encrypted…" | pre-release | flows |  |
| 545 | "Senders SHOULD encrypt; the reference software encrypts by…" | pre-release | flows |  |
| 546 | "A receiver MUST NOT execute a job object…" | pre-release | flows |  |
| 547 | "In the reference software the enable is a…" | pre-release | flows |  |
| 548 | "The MAC of Section 7 is verified before…" | pre-release | flows |  |
| 549 | "This section is the protocol's confidentiality mechanism at…" | pre-release | flows |  |
| 550 | "Receiver support is REQUIRED on every binding, because…" | pre-release | flows |  |
| 551 | "Sender application is OPTIONAL on a binding that…" | pre-release | flows |  |
| 552 | "On a binding that does not provide the…" | pre-release | flows |  |
| 553 | "The plaintext is the complete signed job body…" | pre-release | flows |  |
| 554 | "The cipher is AES-256-GCM {{SP800-38D}}:" | pre-release | flows |  |
| 555 | "Key: HKDF {{RFC5869}} with HMAC-SHA-384." | pre-release | flows |  |
| 556 | "The input keying material is the UTF-8 octets…" | pre-release | flows |  |
| 557 | "The salt is the nonce." | pre-release | flows |  |
| 558 | "The info string is "homing-pigeon job-encryption v1"." | pre-release | flows |  |
| 559 | "The output is 32 octets." | pre-release | flows |  |
| 560 | "Nonce: 12 octets, freshly random for each message." | pre-release | flows |  |
| 561 | "Additional authenticated data: the `job_id`, the `key_id` (empty…" | pre-release | flows |  |
| 562 | "The transmitted body is a JSON envelope object,…" | pre-release | flows |  |
| 563 | "~~~ json {"hp_enc": {"alg": "aes-256-gcm/hkdf-sha384", "nonce": "<base64>", "ct":…" | pre-release | flows |  |
| 564 | "`ct` is the ciphertext with the 16-octet GCM…" | pre-release | flows |  |
| 565 | "When the selected secret is not the default,…" | pre-release | flows |  |
| 566 | "`hp_enc` is a reserved member name: a body…" | pre-release | flows |  |
| 567 | "An envelope is processed inside Section 14's steps,…" | pre-release | flows |  |
| 568 | "The envelope's `key_id` selects the secret (Section 10),…" | pre-release | flows |  |
| 569 | "The envelope's MAC is verified - step 5…" | pre-release | flows |  |
| 570 | "On failure, reject as step 5 specifies." | pre-release | flows |  |
| 571 | "A receiver MUST NOT attempt decryption before the…" | pre-release | flows |  |
| 572 | "Decrypt." | pre-release | flows |  |
| 573 | "Any failure - an unknown `alg`, a malformed…" | pre-release | flows |  |
| 574 | "No partial plaintext is processed." | pre-release | flows |  |
| 575 | "The recovered body re-enters Section 14 at step…" | pre-release | flows |  |
| 576 | "Support of this section is REQUIRED (Section 16)." | pre-release | flows |  |
| 577 | "A receiver that does not implement it is…" | pre-release | flows |  |
| 578 | "The result for an encrypted job SHOULD be…" | pre-release | flows |  |
| 579 | "A receiver's local policy MAY override in either…" | pre-release | flows |  |
| 580 | "Per-job encryption provides confidentiality against observers of the…" | pre-release | flows |  |
| 581 | "It provides NO forward secrecy, and the two…" | pre-release | flows |  |
| 582 | "Encryption also raises the value of a captured…" | pre-release | flows |  |
| 583 | "A valid MAC is permission to run as…" | pre-release | flows |  |
| 584 | "Anyone who holds the secret can operate the…" | pre-release | flows |  |
| 585 | "This protocol does not define a sandbox." | pre-release | flows |  |
| 586 | "LOCAL confinement MUST NOT be assumed by the…" | pre-release | flows |  |
| 587 | "HMAC authenticates; it does not encrypt." | pre-release | flows |  |
| 588 | "The protocol's confidentiality is Section 16, and nothing…" | pre-release | flows |  |
| 589 | "Where cleartext is in use under an operator's…" | pre-release | flows |  |
| 590 | "With per-job encryption in use, the job and…" | pre-release | flows |  |
| 591 | "The reference software encrypts by default." | pre-release | flows |  |
| 592 | "A receiver that has not explicitly enabled cleartext…" | pre-release | flows |  |
| 593 | "Per-job encryption provides NO forward secrecy." | pre-release | flows |  |
| 594 | "Its key derives from the static shared secret,…" | pre-release | flows |  |
| 595 | "A confidentiality claim for this protocol MUST be…" | pre-release | flows |  |
| 596 | "One captured message is enough to test candidate…" | pre-release | flows |  |
| 597 | "More messages do not reduce that search." | pre-release | flows |  |
| 598 | "HMAC-SHA-384 does not yield the key from the…" | pre-release | flows |  |
| 599 | "The secret SHOULD be 32 octets from a…" | pre-release | flows |  |
| 600 | "Sixty-four hexadecimal characters are the usual form." | pre-release | flows |  |
| 601 | "A long human sentence is not a substitute." | pre-release | flows |  |
| 602 | "The secret SHOULD NOT be the mailbox password." | pre-release | flows |  |
| 603 | "The floor is normative for this protocol: the…" | pre-release | flows |  |
| 604 | "The requirement answers the offline-guessing attack above, and…" | pre-release | flows |  |
| 605 | "`From`, `Reply-To`, `Sender`, and `To` MUST NOT satisfy…" | pre-release | flows |  |
| 606 | "An invalid MAC MUST NOT cause any result…" | pre-release | flows |  |
| 607 | "Failing closed before the MAC stops a message…" | pre-release | flows |  |
| 608 | "A near-miss fingerprint is this case (Section 10.1):…" | pre-release | flows |  |
| 609 | "The past window rejects stale `issued_at`." | pre-release | flows |  |
| 610 | "The seen-set rejects a repeated `job_id`." | pre-release | flows |  |
| 611 | "A receiver with a wrong clock will accept…" | pre-release | flows |  |
| 612 | "A receiver whose seen-set is cleared will accept…" | pre-release | flows |  |
| 613 | "Jobs MUST be safe to repeat for that…" | pre-release | flows |  |
| 614 | "The transport credentials and the HMAC secret, which…" | pre-release | flows |  |
| 615 | "The splitter uses the last `,"sig":"`." | pre-release | flows |  |
| 616 | "A string value that contains that sequence will…" | pre-release | flows |  |
| 617 | "Senders MUST keep that sequence out of values." | pre-release | flows |  |
| 618 | "Version 1 results carry `stdout` and `stderr` up…" | pre-release | flows |  |
| 619 | "A receiver that wants to withhold output is…" | pre-release | flows |  |
| 620 | "That policy is not signaled by `v`." | pre-release | flows |  |
| 621 | "How that layering relates to this document is…" | pre-release | flows |  |
| 622 | "An attacker who can drop the result mail…" | pre-release | flows |  |
| 623 | "This protocol does not add a separate ack." | pre-release | flows |  |
| 624 | "This document has one IANA action." | pre-release | flows |  |
| 625 | "Section 20 defines one TLS extension, `platform_info`, carried…" | pre-release | flows |  |
| 626 | "A code point for it in the TLS…" | pre-release | flows |  |
| 627 | "No new port, service name, media type, or…" | pre-release | flows |  |
| 628 | "HMAC-SHA-384 is already named by {{RFC2104}} and {{FIPS180-4}}." | pre-release | flows |  |
| 629 | "The algorithm OID `hmacWithSHA384` (`1.2.840.113549.2.10`) already exists." | pre-release | flows |  |
| 630 | "This protocol identifies the algorithm by name, not…" | pre-release | flows |  |
| 631 | "The reference port for the DTLS binding (Section…" | pre-release | flows |  |
| 632 | "This section and the three that follow it…" | pre-release | flows |  |
| 633 | "The messages do not change on this binding;…" | pre-release | flows |  |
| 634 | "The store-and-forward bindings need no path between submitter…" | pre-release | flows |  |
| 635 | "That is the right default, and it is…" | pre-release | flows |  |
| 636 | "Where a direct path does exist -- the…" | pre-release | flows |  |
| 637 | "The cost is real, and it falls on…" | pre-release | flows |  |
| 638 | "The store-and-forward bindings ask the submitter only to…" | pre-release | flows |  |
| 639 | "This binding asks the submitter to terminate DTLS…" | pre-release | flows |  |
| 640 | "Many submitter environments cannot open a UDP socket…" | pre-release | flows |  |
| 641 | "That is why this binding is optional, why…" | pre-release | flows |  |
| 642 | "Section 21 states the conformance burden plainly." | pre-release | flows |  |
| 643 | "Two consequences of a direct binding deserve emphasis…" | pre-release | flows |  |
| 644 | "First, the runner listens: enabling this binding opens…" | pre-release | flows |  |
| 645 | "The binding is therefore off unless an owner…" | pre-release | flows |  |
| 646 | "Second, channel security is not delivery." | pre-release | flows |  |
| 647 | "A session protects what crosses it while it…" | pre-release | flows |  |
| 648 | "Delivery, retry, and deduplication remain the protocol's own…" | pre-release | flows |  |
| 649 | "The submitter initiates." | pre-release | flows |  |
| 650 | "The runner listens on a UDP port (LOCAL;…" | pre-release | flows |  |
| 651 | "One session carries any number of job and…" | pre-release | flows |  |
| 652 | "Roles do not reverse: the runner never initiates…" | pre-release | flows |  |
| 653 | "This binding is a bounded profile of DTLS…" | pre-release | flows |  |
| 654 | "An implementation of this binding implements exactly this…" | pre-release | flows |  |
| 655 | "Transport: DTLS 1.3 {{RFC9147}} over UDP." | pre-release | flows |  |
| 656 | "DTLS 1.2 MUST NOT be negotiated." | pre-release | flows |  |
| 657 | "Ciphersuite: TLS_AES_256_GCM_SHA384 {{RFC8446}} only." | pre-release | flows |  |
| 658 | "No other suite is offered or accepted." | pre-release | flows |  |
| 659 | "Authentication: pre-shared key only." | pre-release | flows |  |
| 660 | "The external PSK is the shared secret, under…" | pre-release | flows |  |
| 661 | "Certificates are not part of this profile, in…" | pre-release | flows |  |
| 662 | "The shared secret MUST meet the minimum-entropy floor…" | pre-release | flows |  |
| 663 | "Key exchange: `psk_dhe_ke` only." | pre-release | flows |  |
| 664 | "The `psk_key_exchange_modes` extension MUST offer mode 1 and…" | pre-release | flows |  |
| 665 | "An ephemeral X25519 {{RFC7748}} key share MUST ride…" | pre-release | flows |  |
| 666 | "Section 22.1 gives the reason: this is the…" | pre-release | flows |  |
| 667 | "Address validation: the responder MUST perform the HelloRetryRequest…" | pre-release | flows |  |
| 668 | "The cookie is stateless and is bound to…" | pre-release | flows |  |
| 669 | "Connection ID: both sides MUST negotiate the `connection_id`…" | pre-release | flows |  |
| 670 | "Retransmission: handshake flights are retransmitted on the timers…" | pre-release | flows |  |
| 671 | "Duplicate or retransmitted handshake messages are consumed exactly…" | pre-release | flows |  |
| 672 | "Early data: none." | pre-release | flows |  |
| 673 | "0-RTT MUST NOT be offered, sent, or accepted;…" | pre-release | flows |  |
| 674 | "Resumption: a responder MAY issue a NewSessionTicket." | pre-release | flows |  |
| 675 | "A resumed session MUST use a fresh ephemeral…" | pre-release | flows |  |
| 676 | "KeyUpdate: an implementation MUST NOT initiate KeyUpdate." | pre-release | flows |  |
| 677 | "An implementation that receives a KeyUpdate with `update_requested`…" | pre-release | flows |  |
| 678 | "Malformed input: a malformed or undecryptable datagram is…" | pre-release | flows |  |
| 679 | "It MUST NOT be fatal to the listener…" | pre-release | flows |  |
| 680 | "Inside a session, application data is a stream…" | pre-release | flows |  |
| 681 | "Each message is one protocol envelope in the…" | pre-release | flows |  |
| 682 | "A job message is answered, in due course,…" | pre-release | flows |  |
| 683 | "Acknowledgement and deduplication are the protocol's own, unchanged:…" | pre-release | flows |  |
| 684 | "A result produced after its session has died…" | pre-release | flows |  |
| 685 | "This binding provides the confidentiality property of Section…" | pre-release | flows |  |
| 686 | "Application of the per-job encryption of Section 16…" | pre-release | flows |  |
| 687 | "A sender may send a cleartext signed job…" | pre-release | flows |  |
| 688 | "The receiver rule of Section 16 is unchanged…" | pre-release | flows |  |
| 689 | "Receiver support of Section 16 remains REQUIRED, on…" | pre-release | flows |  |
| 690 | "Neither layer's presence relaxes the other's checks where…" | pre-release | flows |  |
| 691 | "The session's authentication of its peer does not…" | pre-release | flows |  |
| 692 | "The platform is what the initiator needs before…" | pre-release | flows |  |
| 693 | "The session gives the handshake itself a place…" | pre-release | flows |  |
| 694 | "The pattern is the Configuration Payload of IKEv2…" | pre-release | flows |  |
| 695 | "The carriage is one TLS extension, `platform_info` (extension…" | pre-release | flows |  |
| 696 | "An initiator that implements this section includes the…" | pre-release | flows |  |
| 697 | "The offer says only that the initiator can…" | pre-release | flows |  |
| 698 | "A responder MAY answer the offer by including…" | pre-release | flows |  |
| 699 | "A responder MUST NOT send the extension to…" | pre-release | flows |  |
| 700 | "EncryptedExtensions is encrypted under the handshake traffic keys,…" | pre-release | flows |  |
| 701 | "A stranger at the listener learns nothing from…" | pre-release | flows |  |
| 702 | "The disclosure is the responder's choice." | pre-release | flows |  |
| 703 | "Its tier is the runner's LOCAL configuration." | pre-release | flows |  |
| 704 | "The bare offer above is not a request,…" | pre-release | flows |  |
| 705 | "The extension value is a JSON object {{RFC8259}}…" | pre-release | flows |  |
| 706 | "~~~ {"disclosure": "family", "platform": {"os_family": "linux", "default_interpreter": ["sh"],…" | pre-release | flows |  |
| 707 | "The member `disclosure` (the tier in force) is…" | pre-release | flows |  |
| 708 | "The `platform` member is present unless the tier…" | pre-release | flows |  |
| 709 | "`none`: no `platform` member." | pre-release | flows |  |
| 710 | "The responder declines to describe the host." | pre-release | flows |  |
| 711 | "A responder at this tier MAY omit the…" | pre-release | flows |  |
| 712 | "`family`: `os_family` (one of `windows`, `macos`, `linux`, `other`),…" | pre-release | flows |  |
| 713 | "This is the reference default." | pre-release | flows |  |
| 714 | "`standard`: `family` plus `os_release` (the operating system's release…" | pre-release | flows |  |
| 715 | "`full`: `standard` plus `path_tools`, an object naming a…" | pre-release | flows |  |
| 716 | "The platform values above are strings on the…" | pre-release | flows |  |
| 717 | "The disclosure precedes work, in the only form…" | pre-release | flows |  |
| 718 | "A responder that implements this section does not…" | pre-release | flows |  |
| 719 | "The disclosure is proportioned the way the protocol…" | pre-release | flows |  |
| 720 | "The information itself is of the kind any…" | pre-release | flows |  |
| 721 | "The reference implementation includes the platform disclosure in…" | pre-release | flows |  |
| 722 | "A resumed session is a new session for…" | pre-release | flows |  |
| 723 | "This section is candid because the Introduction's promise…" | pre-release | flows |  |
| 724 | "A conforming submitter for this binding implements DTLS…" | pre-release | flows |  |
| 725 | "It needs a UDP path to the runner,…" | pre-release | flows |  |
| 726 | "None of this is required of a submitter…" | pre-release | flows |  |
| 727 | "The conformance of the messages and their checks…" | pre-release | flows |  |
| 728 | "The bindings coexist: the same runner, the same…" | pre-release | flows |  |
| 729 | "The profile's load-bearing rule is that `psk_ke` is…" | pre-release | flows |  |
| 730 | "In `psk_ke`, session keys derive from the pre-shared…" | pre-release | flows |  |
| 731 | "Because this protocol's shared secret is long-lived and…" | pre-release | flows |  |
| 732 | "In `psk_dhe_ke`, every session -- full or resumed…" | pre-release | flows |  |
| 733 | "An implementation MUST NOT offer, accept, or fall…" | pre-release | flows |  |
| 734 | "One limit is stated plainly: forward secrecy here…" | pre-release | flows |  |
| 735 | "The ephemeral exchange is X25519, so a recorded…" | pre-release | flows |  |
| 736 | "A hybrid post-quantum key exchange is the known…" | pre-release | flows |  |
| 737 | "The shared secret does two jobs on this…" | pre-release | flows |  |
| 738 | "These are independent constructions (the TLS key schedule's…" | pre-release | flows |  |
| 739 | "The composition does not weaken the analysis of…" | pre-release | flows |  |
| 740 | "The offline-guessing analysis of Section 17.3 applies to…" | pre-release | flows |  |
| 741 | "The disclosure of Section 20 is a deliberate,…" | pre-release | flows |  |
| 742 | "The responder sends the disclosure inside its handshake…" | pre-release | flows |  |
| 743 | "The alternative placement - the same information as…" | pre-release | flows |  |
| 744 | "What protects the disclosure at the earlier moment…" | pre-release | flows |  |
| 745 | "EncryptedExtensions is encrypted under the handshake traffic keys…" | pre-release | flows |  |
| 746 | "A peer without the secret harvests nothing from…" | pre-release | flows |  |
| 747 | "The audience of the disclosure is therefore the…" | pre-release | flows |  |
| 748 | "What moved is only the moment, one flight…" | pre-release | flows |  |
| 749 | "An owner who weighs even that sets the…" | pre-release | flows |  |
| 750 | "Its other bounds are its defenses: it contains…" | pre-release | flows |  |
| 751 | "What the disclosure must never become is a…" | pre-release | flows |  |
| 752 | "A UDP listener is a reflection surface." | pre-release | flows |  |
| 753 | "The cookie exchange is the mitigation this profile…" | pre-release | flows |  |
| 754 | "The listener's other exposure is computational: handshakes cost…" | pre-release | flows |  |
| 755 | "The stateless cookie keeps pre-authentication cost to one…" | pre-release | flows |  |
| 756 | "Enabling this binding changes the host's posture from…" | pre-release | flows |  |
| 757 | "DTLS authenticates and encrypts records; it does not…" | pre-release | flows |  |
| 758 | "This profile deliberately keeps the protocol's at-least-once semantics…" | pre-release | flows |  |
| 759 | "An implementation MUST NOT treat session establishment as…" | pre-release | flows |  |
| 760 | "The confidentiality claim is end to end between…" | pre-release | flows |  |
| 761 | "A middlebox that terminates DTLS -- an inspecting…" | pre-release | flows |  |
| 762 | "Deployments that route this binding through such a…" | pre-release | flows |  |
| 763 | "--- back" | pre-release | flagged | A section marker ("--- back") standing as its own unit — structure, not a sentence |
