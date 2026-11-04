# Findings — docs/steady/reports/project-review.md

Source: docs/steady/reports/project-review.md, reviewed at main 8696f0cc.
Sentence units: 78. Flagged: 4. Categories: pre-release 78, post-release 0.

A whole-project review report: the 118 findings by class, the fixes, and the headline corrections by area. 1 markup unit, the class table's structure, and 1 fragment lead-in are the breaks. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->" | pre-release | flagged | An HTML agent-stamp comment standing as the first unit — markup where the document's first sentence should be |
| 2 | "**Status:** a dated record, at the conductor's word…" | pre-release | flows |  |
| 3 | "Every finding below was either fixed in the…" | pre-release | flows |  |
| 4 | "Later edits on main move things; read the…" | pre-release | flows |  |
| 5 | "**Baseline:** main at `2642bb02` (version 3.13.60, 2026-10-26). **Scope:**…" | pre-release | flows |  |
| 6 | "Not re-audited, by standing rule (AGENTS.md rule 6):…" | pre-release | flows |  |
| 7 | "About 1,300 claims were checked; about 1,180 held…" | pre-release | flows |  |
| 8 | "The 118 that did not, by class:" | pre-release | flows |  |
| 9 | "| Class | Count | Meaning |" | pre-release | flagged | A table header row — structure, not a sentence |
| 10 | "|---|---:|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 11 | "| WRONG | 15 | the code does…" | pre-release | flows |  |
| 12 | "| STALE | 28 | was true, the…" | pre-release | flows |  |
| 13 | "| BROKEN COMMAND | 6 | a documented…" | pre-release | flows |  |
| 14 | "| DEAD LINK | 14 | a pointer…" | pre-release | flows |  |
| 15 | "| MISLEADING | 24 | true as written,…" | pre-release | flows |  |
| 16 | "| NIT | 31 | a count, a…" | pre-release | flows |  |
| 17 | "Every link, path and GitHub URL in the…" | pre-release | flows |  |
| 18 | "The coordination files are in order: three questions…" | pre-release | flows |  |
| 19 | "Four of the findings were not documentation." | pre-release | flows |  |
| 20 | "**An allowlisted key could run arbitrary remote code.**…" | pre-release | flows |  |
| 21 | "PROTOCOL.md section 14 already said `script_url` is not…" | pre-release | flows |  |
| 22 | "Fixed in `ea3168e7`." | pre-release | flows |  |
| 23 | "**`send_dtls.py` sent cleartext by default.** `--encrypt` (store_false) and…" | pre-release | flows |  |
| 24 | "The default is pinned to encrypt; a test…" | pre-release | flows |  |
| 25 | "Fixed in `ea3168e7`." | pre-release | flows |  |
| 26 | "**The wheel shipped the build tools and the…" | pre-release | flows |  |
| 27 | "Excluded now, the transports kept." | pre-release | flows |  |
| 28 | "Fixed in `ea3168e7`." | pre-release | flows |  |
| 29 | "**Main was red, and the release train stopped…" | pre-release | flows |  |
| 30 | "Rewritten through the tool's own writer; the 3.13.60…" | pre-release | flows |  |
| 31 | "Fixed in `850a2d99`." | pre-release | flows |  |
| 32 | "Two more in CI, found by the readers…" | pre-release | flows |  |
| 33 | "The headline corrections, by area." | pre-release | flagged | A fragment lead-in ("The headline corrections, by area.") standing as its own paragraph; the corrections it announces arrive under separate lead-ins with no hand-off |
| 34 | "The commits carry the full list; each batch's…" | pre-release | flows |  |
| 35 | "**Security and design** (`79a78b47`)." | pre-release | flows |  |
| 36 | "`safeguards.md` and the README said a missing `bwrap`…" | pre-release | flows |  |
| 37 | "The SELinux template commented with `!` and named…" | pre-release | flows |  |
| 38 | "The hardened systemd unit set `RestrictNamespaces=true`, which stops…" | pre-release | flows |  |
| 39 | "`ci-runtime.md` described a mutation job on tags, a…" | pre-release | flows |  |
| 40 | "The stamp design note said nothing enforced it;…" | pre-release | flows |  |
| 41 | "Four pointers into `future.md` named entries that were…" | pre-release | flows |  |
| 42 | "**Extensions** (`79a78b47`)." | pre-release | flows |  |
| 43 | "`docs/extend/transports.md` ended mid-sentence: a commit had cut 184…" | pre-release | flows |  |
| 44 | "Restored, with the two things it never had…" | pre-release | flows |  |
| 45 | "The Queues section described two named queues that…" | pre-release | flows |  |
| 46 | "Fifteen READMEs presented `poll_interval_sec` as a knob "the…" | pre-release | flows |  |
| 47 | "The catalog counted a sense twice; osquery was…" | pre-release | flows |  |
| 48 | "**Root manuals, docs/use, docs/oracle** (`65d4a405`)." | pre-release | flows |  |
| 49 | "The README's `--cleartext` was the sender's flag described…" | pre-release | flows |  |
| 50 | "**Project docs and CI** (`e347e100`)." | pre-release | flows |  |
| 51 | "`testing.md` said every platform is proven on a…" | pre-release | flows |  |
| 52 | "The campaign playbook's hard rules were superseded by…" | pre-release | flows |  |
| 53 | "Four workflows were outside the CI guard's registry,…" | pre-release | flows |  |
| 54 | "**PROTOCOL.md and the drafts** (`e7d96f23`)." | pre-release | flows |  |
| 55 | "The audience claim the reference signs is `aud`,…" | pre-release | flows |  |
| 56 | "`kind` has a third value." | pre-release | flows |  |
| 57 | "The `attested` view was said to carry the…" | pre-release | flows |  |
| 58 | "The draft still described a failed send as…" | pre-release | flows |  |
| 59 | "The DTLS greeting's family tier carries three members,…" | pre-release | flows |  |
| 60 | "The v2 draft's replay rule is kept as…" | pre-release | flows |  |
| 61 | "Each with who holds it." | pre-release | flows |  |
| 62 | "**Q86, the desk:** version 2 messages keep no…" | pre-release | flows |  |
| 63 | "The draft's requirement stands; the fix is small." | pre-release | flows |  |
| 64 | "**Q54, Q57, Grok:** the extraction rule and the…" | pre-release | flows |  |
| 65 | "**The FreeBSD leg, 40000e00:** nine runs, nine failures…" | pre-release | flows |  |
| 66 | "The row in `testing.md` says so until it…" | pre-release | flows |  |
| 67 | "**Coverage cadence, decided (the conductor, 2026-10-27):** `coverage.yml` runs…" | pre-release | flows |  |
| 68 | "`python-range.yml` stays on push: a failure there is…" | pre-release | flows |  |
| 69 | "**The hardened systemd unit, decided (the conductor, 2026-10-27):**…" | pre-release | flows |  |
| 70 | "The strict value is one line to restore…" | pre-release | flows |  |
| 71 | "**The AppArmor profile, documented, not fixed:** it runs…" | pre-release | flows |  |
| 72 | "Extending it needs a box to `aa-logprof` on." | pre-release | flows |  |
| 73 | "**`hardware.yml`:** dispatch-only and never dispatched; nothing is known…" | pre-release | flows |  |
| 74 | "**Suite:** 3,456 tests on the reviewed tree (local…" | pre-release | flows |  |
| 75 | "314 test modules; 0 TODO/FIXME in `runner/` outside…" | pre-release | flows |  |
| 76 | "**Workflows:** 118 `uses:` lines, all pinned by 40-hex…" | pre-release | flows |  |
| 77 | "**CI on main:** green on every leg at…" | pre-release | flows |  |
| 78 | "The same pass, on any later tree: hold…" | pre-release | flows |  |
