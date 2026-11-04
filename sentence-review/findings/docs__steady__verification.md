# Findings — docs/steady/verification.md

Source: docs/steady/verification.md, reviewed at main cbb52068.
Sentence units: 42. Flagged: 0. Categories: pre-release 42, post-release 0.

Several units are lead-ins or parenthetical notes attached to the command blocks that follow them; the commands are structure, and the units are recorded in reading order around them.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Every Homing Pigeon release carries the machinery to…" | pre-release | flows |  |
| 2 | "This page walks the chain from a release…" | pre-release | flows |  |
| 3 | "Nothing here needs project credentials; the anchor of…" | pre-release | flows |  |
| 4 | "The chain, in one paragraph: the tag build…" | pre-release | flows |  |
| 5 | "PyPI publishing runs over OIDC trusted publishing (no…" | pre-release | flows |  |
| 6 | "The Docker image is attested by digest in…" | pre-release | flows |  |
| 7 | "The SourceForge and GitLab mirrors copy the GitHub…" | pre-release | flows |  |
| 8 | "Examples below use `vX.Y.Z` and `X.Y.Z` for the…" | pre-release | flows |  |
| 9 | "Download the archive and `SHA384SUMS` from the release…" | pre-release | flows |  |
| 10 | "(On macOS: `shasum -a 384 -c SHA384SUMS`.)" | pre-release | flows |  |
| 11 | "That proves the file matches what the release…" | pre-release | flows |  |
| 12 | "The sums file itself is covered by the…" | pre-release | flows |  |
| 13 | "The same command works for every file in…" | pre-release | flows |  |
| 14 | "A successful verify reports the workflow (`build.yml`), the…" | pre-release | flows |  |
| 15 | "`pip install pigeon-home-runner` fetches the wheel (or sdist)…" | pre-release | flows |  |
| 16 | "Two independent checks:" | pre-release | flows |  |
| 17 | "**Provenance.** Publishing uses OIDC trusted publishing: no PyPI…" | pre-release | flows |  |
| 18 | "PyPI shows it on the project's release page,…" | pre-release | flows |  |
| 19 | "The bundle's publisher block names kind `GitHub`, repository…" | pre-release | flows |  |
| 20 | "If it names anything else, the file did…" | pre-release | flows |  |
| 21 | "**Sums.** The wheel and sdist on PyPI are…" | pre-release | flows |  |
| 22 | "The image workflow builds for the tag and…" | pre-release | flows |  |
| 23 | "Get the digest for the tag, then verify…" | pre-release | flows |  |
| 24 | "Verify by digest, not by tag: a tag…" | pre-release | flows |  |
| 25 | "Both mirrors copy the published GitHub release assets…" | pre-release | flows |  |
| 26 | "The caution: a sums file is only as…" | pre-release | flows |  |
| 27 | "A `SHA384SUMS` downloaded from a mirror proves the…" | pre-release | flows |  |
| 28 | "So either verify one file (or the sums…" | pre-release | flows |  |
| 29 | "After that single anchored check, the sums verify…" | pre-release | flows |  |
| 30 | "Every install archive carries a stamp placed in…" | pre-release | flows |  |
| 31 | "(Windows: `tar -xzf ... -O` works the same…" | pre-release | flows |  |
| 32 | "It names the product, the version, the commit…" | pre-release | flows |  |
| 33 | "A file that arrives detached from any release…" | pre-release | flows |  |
| 34 | "Every install archive carries `project/`, and the same…" | pre-release | flows |  |
| 35 | "It is added to the archives before `SHA384SUMS`…" | pre-release | flows |  |
| 36 | "To check the history against the tag:" | pre-release | flows |  |
| 37 | "`SBOM.spdx.json` (SPDX 2.3) ships with every release and…" | pre-release | flows |  |
| 38 | "Because the runtime is stdlib-only, it is short:…" | pre-release | flows |  |
| 39 | "Read it with any SPDX tool, or as…" | pre-release | flows |  |
| 40 | "It proves a file is the file the…" | pre-release | flows |  |
| 41 | "It does not prove the build was benign…" | pre-release | flows |  |
| 42 | "The mirror check anchors on GitHub once, as…" | pre-release | flows |  |
