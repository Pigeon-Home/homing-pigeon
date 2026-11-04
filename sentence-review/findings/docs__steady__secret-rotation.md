# Findings — docs/steady/secret-rotation.md

Source: docs/steady/secret-rotation.md, reviewed at main cbb52068.
Sentence units: 55. Flagged: 1. Categories: pre-release 52, post-release 3.

Unit 16 is a prose run the source keeps as 1 paragraph; its sentences are recorded once, as extracted. Unit 53 is a horizontal rule, recorded as extracted and flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Rotate the shared secret every **90 days**." | pre-release | flows |  |
| 2 | "The period is a calendar cap: the secret…" | pre-release | flows |  |
| 3 | "It is not a function of how many…" | pre-release | flows |  |
| 4 | "HMAC-SHA-384 tags do not leak the key at…" | pre-release | flows |  |
| 5 | "One captured message is already enough to test…" | pre-release | flows |  |
| 6 | "Pigeon mail never carries the secret, only the…" | pre-release | flows |  |
| 7 | "A job with no `key_id` verifies against `shared_secret`,…" | pre-release | flows |  |
| 8 | "A job with any other `key_id` verifies against…" | pre-release | flows |  |
| 9 | "Secrets are read at startup — editing config.json…" | pre-release | flows |  |
| 10 | "A new secret is a new name: its…" | pre-release | flows |  |
| 11 | "The name is public (SECURITY.md, "Key names are…" | pre-release | flows |  |
| 12 | "A new `key_id` does not inherit `key_policies`." | pre-release | flows |  |
| 13 | "If `key_policies_default_deny` is false (the default), the new…" | pre-release | flows |  |
| 14 | "If true, a new id with no policy…" | pre-release | flows |  |
| 15 | "A secret the installer generates is named, and…" | pre-release | flows |  |
| 16 | "The first secret's name is its fingerprint, `k-`…" | pre-release | flows |  |
| 17 | "A sender sends the key's name on every…" | pre-release | flows |  |
| 18 | "The empty key id stays a legacy alias…" | post-release | flows |  |
| 19 | "A later release may refuse an unnamed body." | post-release | flows |  |
| 20 | "That is a separate question." | post-release | flows |  |
| 21 | "A planned rotation names the new key." | pre-release | flows |  |
| 22 | "The old one stays until every sender has…" | pre-release | flows |  |
| 23 | "A leak is not a planned rotation: `docs/security/safeguards.md`…" | pre-release | flows |  |
| 24 | "`install.py --check` prints the key ids a runner…" | pre-release | flows |  |
| 25 | "Generate a 256-bit secret:" | pre-release | flows |  |
| 26 | "Put it in config.json under `additional_secrets` with a…" | pre-release | flows |  |
| 27 | "The runner imposes no pattern or length limit…" | pre-release | flows |  |
| 28 | "Leave `shared_secret` in place." | pre-release | flows |  |
| 29 | "(Note: `install.py --additional-secret KEY_ID` only stores the secret…" | pre-release | flows |  |
| 30 | "Restart the runner." | pre-release | flows |  |
| 31 | "Tell the signer the new `key_id` and the…" | pre-release | flows |  |
| 32 | "From then on the signer sets `key_id` on…" | pre-release | flows |  |
| 33 | "Confirm a job signed with the new id…" | pre-release | flows |  |
| 34 | "Mail already in the inbox still runs —…" | pre-release | flows |  |
| 35 | "Remove the old secret only after every signer…" | pre-release | flows |  |
| 36 | "Do not delete `shared_secret` while any signer still…" | pre-release | flows |  |
| 37 | "Restart again." | pre-release | flows |  |
| 38 | "A DTLS resumption ticket records the key that…" | pre-release | flows |  |
| 39 | "Never reuse a retired secret." | pre-release | flows |  |
| 40 | "Never put two values on one `key_id`." | pre-release | flows |  |
| 41 | "With a directory configured (`key_directory` inline, or `key_directory_file`…" | pre-release | flows |  |
| 42 | "The runner refuses any key whose entry does…" | pre-release | flows |  |
| 43 | "The steps with a directory:" | pre-release | flows |  |
| 44 | "Add the new secret under its id as…" | pre-release | flows |  |
| 45 | "Restart for the secret (it is read at…" | pre-release | flows |  |
| 46 | "Hand the new id and secret to the…" | pre-release | flows |  |
| 47 | "Mark the old key `{"state": "superseded", "not_after": }`." | pre-release | flows |  |
| 48 | "It keeps verifying until that moment and is…" | pre-release | flows |  |
| 49 | "After the window, remove the old secret from…" | pre-release | flows |  |
| 50 | "Restart for the secret's removal." | pre-release | flows |  |
| 51 | "A leaked key is marked `{"state": "compromised"}` first…" | pre-release | flows |  |
| 52 | "An entry may also carry the key's `fingerprint`…" | pre-release | flows |  |
| 53 | "(horizontal rule)" | pre-release | flagged | Horizontal rule; structure, not a sentence; the side note follows |
| 54 | "*Side note: NIST SP 800-57 recommends an originator-usage…" | pre-release | flows |  |
| 55 | "Ninety days sits comfortably inside that.*" | pre-release | flows |  |
