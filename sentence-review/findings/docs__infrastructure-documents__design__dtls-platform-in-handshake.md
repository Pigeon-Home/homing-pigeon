# Findings — docs/infrastructure-documents/design/dtls-platform-in-handshake.md

Source: docs/infrastructure-documents/design/dtls-platform-in-handshake.md, reviewed at main 737df18f.
Sentence units: 35. Flagged: 0. Categories: pre-release 35, post-release 0.

A design note for the platform disclosure riding inside the DTLS handshake: the need, the gap a post-handshake greeting leaves, the extension and its code point, the IKEv2 lift named as a lift, the tiers, solicitation, ordering, and what the encryption buys. 35 sentences of continuous design prose; each paragraph hands to the next — need, mechanism, rules, guarantee — and the closing sentence restates the opening need as met. Nothing is flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "A sender needs the runner's platform before the…" | pre-release | flows |  |
| 2 | "A separate greeting sent as the first application…" | pre-release | flows |  |
| 3 | "The initiator has finished the handshake, yet before…" | pre-release | flows |  |
| 4 | "On a store-and-forward carriage that wait becomes another…" | pre-release | flows |  |
| 5 | "The platform disclosure now rides in the handshake…" | pre-release | flows |  |
| 6 | "The server places a configuration-style extension, type `0xFFA0`,…" | pre-release | flows |  |
| 7 | "`0xFFA0` is an interim Private Use value (RFC…" | pre-release | flows |  |
| 8 | "It is not an IANA assignment, and it…" | pre-release | flows |  |
| 9 | "The extension value is the disclosure object: `disclosure`…" | pre-release | flows |  |
| 10 | "The old greeting members (`type`, `transport`, `v`) are…" | pre-release | flows |  |
| 11 | "The pattern is lifted from IKEv2's Configuration Payload…" | pre-release | flows |  |
| 12 | "IKEv2 carries configuration attributes inside its authenticated IKE_AUTH…" | pre-release | flows |  |
| 13 | "The encoding is not IKEv2's: the payload stays…" | pre-release | flows |  |
| 14 | "The extension is sent on every fresh handshake…" | pre-release | flows |  |
| 15 | "The existing `dtls_greeting` tiers keep their names and…" | pre-release | flows |  |
| 16 | "At `none`, the extension still rides, carrying the…" | pre-release | flows |  |
| 17 | "At `family`, `standard` and `full`, the `platform` member…" | pre-release | flows |  |
| 18 | "The extension is solicited, never unsolicited." | pre-release | flows |  |
| 19 | "The initiator includes the extension type, empty, in…" | pre-release | flows |  |
| 20 | "The responder sends the extension only to an…" | pre-release | flows |  |
| 21 | "A peer that does not offer still handshakes;…" | pre-release | flows |  |
| 22 | "EncryptedExtensions arrives before the server's Finished in the…" | pre-release | flows |  |
| 23 | "The client holds the extension's payload as pending…" | pre-release | flows |  |
| 24 | "A sender therefore never has to choose between…" | pre-release | flows |  |
| 25 | "For interoperability, a current client also accepts the…" | pre-release | flows |  |
| 26 | "EncryptedExtensions is encrypted under the handshake traffic keys." | pre-release | flows |  |
| 27 | "Those keys are derived from the pre-shared key…" | pre-release | flows |  |
| 28 | "The server builds the extension only after the…" | pre-release | flows |  |
| 29 | "The client does not surface the payload until…" | pre-release | flows |  |
| 30 | "Disclosure remains the responder's choice." | pre-release | flows |  |
| 31 | "The tier is local configuration; the initiator cannot…" | pre-release | flows |  |
| 32 | "The payload names platform shape only -- operating…" | pre-release | flows |  |
| 33 | "Jobs are ordinary application messages once the session…" | pre-release | flows |  |
| 34 | "There is no greeting application message and no…" | pre-release | flows |  |
| 35 | "The handshake carriage itself is the ordering guarantee:…" | pre-release | flows |  |
