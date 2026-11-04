# Findings — docs/steady/design/extension-review-design.md

Source: docs/steady/design/extension-review-design.md, reviewed at main cbb52068.
Sentence units: 38. Flagged: 1. Categories: pre-release 37, post-release 1.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "*Built. `runner/guard/extreview.py`; the owner's guide is docs/extend/extensions.md, "The…" | pre-release | flows |  |
| 2 | "This note records why it has the shape…" | pre-release | flows |  |
| 3 | "Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f" | pre-release | flagged | Agent stamp line; metadata, not a sentence |
| 4 | "An extension is a folder of code the…" | pre-release | flows |  |
| 5 | "The runner trusted the manifest and never looked…" | pre-release | flows |  |
| 6 | "Nothing signed the code." | pre-release | flows |  |
| 7 | "A folder could declare three signals and open…" | pre-release | flows |  |
| 8 | "Signing extension code is the eventual answer and…" | pre-release | flows |  |
| 9 | "What could ship now is the thing a…" | pre-release | flows |  |
| 10 | "**The manifest states, the review checks.** A new…" | pre-release | flows |  |
| 11 | "The review reads every code file and holds…" | pre-release | flows |  |
| 12 | "The vocabulary is small on purpose: four words…" | pre-release | flows |  |
| 13 | "**Deterministic, stdlib, no model.** The Oracle's model-side reading…" | pre-release | flows |  |
| 14 | "The gate before load cannot wait for a…" | pre-release | flows |  |
| 15 | "So the review is a parser and a…" | pre-release | flows |  |
| 16 | "**Findings carry weight, and only the heavy ones…" | pre-release | flows |  |
| 17 | "**Enforce by default.** `extension_review` is `enforce` unless the…" | pre-release | flows |  |
| 18 | "The alternatives were weighed: `advisory` by default would…" | pre-release | flows |  |
| 19 | "The cost of `enforce` is that an owner's…" | pre-release | flows |  |
| 20 | "The refusal line names the file and the…" | pre-release | flows |  |
| 21 | "The shipped extensions all declare what they use;…" | pre-release | flows |  |
| 22 | "**Refuse like the loader.** A refused extension is…" | pre-release | flows |  |
| 23 | "A refused drop-in transport is not silently replaced…" | pre-release | flows |  |
| 24 | "The refusal and the "no loadable transport extension"…" | pre-release | flows |  |
| 25 | "**Shadowing stays legal and gets loud.** The documented…" | pre-release | flows |  |
| 26 | "It is now a `warn` finding and a…" | pre-release | flows |  |
| 27 | "**Read once per change.** `_extension_registry` runs on every…" | pre-release | flows |  |
| 28 | "The review caches per folder on a fingerprint…" | pre-release | flows |  |
| 29 | "**One report, two kinds.** Both loaders write their…" | pre-release | flows |  |
| 30 | "It does not read what a program does…" | pre-release | flows |  |
| 31 | "A transport that declares `network` may connect anywhere;…" | pre-release | flows |  |
| 32 | "Egress policy is the sandbox's business." | pre-release | flows |  |
| 33 | "It does not prove provenance." | pre-release | flows |  |
| 34 | "A folder written by an attacker who can…" | pre-release | flows |  |
| 35 | "That is the signature's job, and the identity…" | pre-release | flows |  |
| 36 | "It does not scan non-code files for capabilities…" | pre-release | flows |  |
| 37 | "The capability vocabulary is extensible without an API…" | pre-release | flows |  |
| 38 | "If a signature scheme lands, the review stays…" | post-release | flows |  |
