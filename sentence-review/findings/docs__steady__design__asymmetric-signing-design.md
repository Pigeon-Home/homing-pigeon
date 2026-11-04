# Findings — docs/steady/design/asymmetric-signing-design.md

Source: docs/steady/design/asymmetric-signing-design.md, reviewed at main 16957c7d.
Sentence units: 54. Flagged: 4. Categories: pre-release 10, post-release 44.

A design record for a migration that is explicitly not built: the costs of the current HMAC scheme (pre-release), then the proposed Ed25519 design, migration steps, open questions, the ssh-keygen evaluation, and the recommendation (post-release). The status header and the 2 appendix lead-ins are the breaks.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "*Not built." | post-release | flagged | A 2-word status label ("*Not built.") standing as its own unit; the document it heads arrives after it |
| 2 | "See docs/future.md." | post-release | flagged | A bare pointer ("See docs/future.md.") standing as its own unit under the status label |
| 3 | "This document records the shape of a migration…" | pre-release | flows |  |
| 4 | "Today every signer shares one HMAC-SHA-384 secret with…" | pre-release | flows |  |
| 5 | "That has three costs:" | pre-release | flows |  |
| 6 | "**The secret travels.** It must be given to…" | pre-release | flows |  |
| 7 | "**Offline brute force.** Anyone holding one signed message…" | pre-release | flows |  |
| 8 | "**No separation of sign and verify.** The runner…" | pre-release | flows |  |
| 9 | "None of this is fatal for the current…" | pre-release | flows |  |
| 10 | "The SI holds an Ed25519 private key." | post-release | flows |  |
| 11 | "The runner holds only public keys, one per…" | post-release | flows |  |
| 12 | "The wire format does not change shape: the…" | post-release | flows |  |
| 13 | "Verification (`verify_body_keyed` and its callers) becomes `verify_body` with…" | post-release | flows |  |
| 14 | "The `key_id` multiplexing, replay cache, audience binding, and…" | post-release | flows |  |
| 15 | "Add the `signing` block alongside `additional_secrets`." | post-release | flows |  |
| 16 | "A key_id present in both is a startup…" | post-release | flows |  |
| 17 | "The SI generates a keypair, sends the public…" | post-release | flows |  |
| 18 | "Dual-verify during rotation: accept both for a window,…" | post-release | flows |  |
| 19 | "The audit log records which algorithm verified each…" | post-release | flows |  |
| 20 | "The setup wizard (`--setup`) generates an Ed25519 keypair…" | post-release | flows |  |
| 21 | "**Dependency.** Options: `cryptography` (C extension, heavy for the…" | post-release | flows |  |
| 22 | "The pure-Python route fits the project's stdlib-only preference;…" | post-release | flows |  |
| 23 | "A fourth option the plan asks us to…" | post-release | flows |  |
| 24 | "**What HMAC still buys.** HMAC-SHA-384 is not broken;…" | pre-release | flows |  |
| 25 | "There is no rush." | pre-release | flows |  |
| 26 | "**Revocation.** A compromised SI private key needs revocation:…" | post-release | flows |  |
| 27 | "No CRL/OCSP — the config *is* the revocation…" | post-release | flows |  |
| 28 | "Document that rotation means a restart." | post-release | flows |  |
| 29 | "**Non-repudiation.** Ed25519 gives it; HMAC doesn't." | post-release | flows |  |
| 30 | "Decide whether the audit log should start asserting…" | post-release | flows |  |
| 31 | "The HMAC scheme matches the current deployment reality:…" | pre-release | flows |  |
| 32 | "Asymmetric signing pays off when there are many…" | post-release | flows |  |
| 33 | "Build it when the second untrusted signer appears,…" | post-release | flows |  |
| 34 | "The plan asks for an explicit evaluation of…" | post-release | flows |  |
| 35 | "**How it would work.** The SI signs the…" | post-release | flows |  |
| 36 | "The runner verifies with `ssh-keygen -Y verify -f…" | post-release | flows |  |
| 37 | "The `-n` namespace binds the signature to this…" | post-release | flows |  |
| 38 | "**In its favor.**" | post-release | flagged | A free-standing bold label ("**In its favor.**"); the argument list it names arrives in the following units |
| 39 | "Zero Python dependencies: no C extensions, no vendored…" | post-release | flows |  |
| 40 | "OpenSSH ships on every target platform, including recent…" | post-release | flows |  |
| 41 | "The crypto is maintained by someone else (OpenBSD)…" | post-release | flows |  |
| 42 | "Key generation and management UX already exists (`ssh-keygen…" | post-release | flows |  |
| 43 | "Verification-only on the runner, signing-only on the SI…" | post-release | flows |  |
| 44 | "**Against it.**" | post-release | flagged | A free-standing bold label ("**Against it.**"); the argument list it names arrives in the following units |
| 45 | "Shelling out per message: a subprocess spawn on…" | post-release | flows |  |
| 46 | "At job-submission rates (a handful of messages per…" | post-release | flows |  |
| 47 | "The armored signature is bulky (~0.5 KB base64-armored)…" | post-release | flows |  |
| 48 | "`allowed_signers` is a second key store beside `config.json`,…" | post-release | flows |  |
| 49 | "Namespace discipline is load-bearing: if the namespace string…" | post-release | flows |  |
| 50 | "It must be a constant, not configurable." | post-release | flows |  |
| 51 | "**Recommendation.** The plan's lean is correct: `ssh-keygen -Y`…" | post-release | flows |  |
| 52 | "It keeps the stdlib-only story intact, outsources the…" | post-release | flows |  |
| 53 | "The vendored pure-Python verifier remains the fallback if…" | post-release | flows |  |
| 54 | "Either way, the `alg` field in the signed…" | post-release | flows |  |
