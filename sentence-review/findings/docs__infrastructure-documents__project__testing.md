# Findings — docs/infrastructure-documents/project/testing.md

Source: docs/infrastructure-documents/project/testing.md, reviewed at main a9a35b81.
Sentence units: 66. Flagged: 5. Categories: pre-release 66, post-release 0.

The testing page: the audit flags, the fake-server suite, the end-to-end steps, the platform proof table and its roster, the proof families, the stdlib coverage tools, and how to run the proofs locally. Every table is introduced by the prose it answers to and the prose chains section to section. The non-sentences are the stamp comment (unit 35) and the 4 table header rows (units 2, 26, 38, 51); every data row is counted as a unit and flows as a record.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "**Watch before you trust.** The runner is fully…" | pre-release | flows |  |
| 2 | "Flag \| What it does" | pre-release | flagged | Table header row, structure rather than a sentence |
| 3 | "`--dry-run` \| Verify and describe; execute nothing, send…" | pre-release | flows |  |
| 4 | "`--workers COUNT` \| Concurrent job executions (default 1)" | pre-release | flows |  |
| 5 | "`-v`, `--verbose` \| Decision lines: every poll, ingest,…" | pre-release | flows |  |
| 6 | "`--pdb` \| Drop into pdb on unhandled exceptions" | pre-release | flows |  |
| 7 | "`--no-send` \| Execute, but log results instead of…" | pre-release | flows |  |
| 8 | "`--once` \| Single poll cycle, then exit" | pre-release | flows |  |
| 9 | "`--inspect {board,budget,job,outbox,redact,review,sources}` \| Read local Oracle state and…" | pre-release | flows |  |
| 10 | "`--audit-report [--since 14d \| 48h] [--feature NAME] [--key…" | pre-release | flows |  |
| 11 | "`--posture` \| Report the runner's security posture (exit…" | pre-release | flows |  |
| 12 | "`--run-variant FILE` \| Run one locally supplied fuzz…" | pre-release | flows |  |
| 13 | "`--oracle` \| Open a loopback chat with the…" | pre-release | flows |  |
| 14 | "`--poll-interval SECONDS`, `--timeout SECONDS`, `--judge MODE`, `--dag-mode MODE`,…" | pre-release | flows |  |
| 15 | "`install.py` accepts the common run flags — `--poll-interval`,…" | pre-release | flows |  |
| 16 | "The suite drives the real runner code against…" | pre-release | flows |  |
| 17 | "End-to-end without your SI:" | pre-release | flows |  |
| 18 | "`python3 runner/cloud/send_job.py new --kind ping --secret <the-string>` →…" | pre-release | flows |  |
| 19 | "From any email account, send it to the…" | pre-release | flows |  |
| 20 | "On the target machine: `python3 runner/runner.py --config config.json…" | pre-release | flows |  |
| 21 | "A result message should arrive in the mailbox…" | pre-release | flows |  |
| 22 | "It arrives as an encrypted envelope; decrypt it…" | pre-release | flows |  |
| 23 | "The runner ships for Linux (x86_64, ARM64, the…" | pre-release | flows |  |
| 24 | "Every platform that ships is tested on a…" | pre-release | flows |  |
| 25 | "The FreeBSD leg is the one without a…" | pre-release | flows |  |
| 26 | "Platform \| Suite \| Switch proofs (the roster)…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 27 | "Linux (ubuntu-latest) \| `test` job, in-process under the…" | pre-release | flows |  |
| 28 | "Windows (windows-latest) \| `build-windows` job, sharded over 4…" | pre-release | flows |  |
| 29 | "macOS (macos-15) \| `test-macos` job, sharded over 3…" | pre-release | flows |  |
| 30 | "FreeBSD 15 (a VM inside a Linux runner)…" | pre-release | flows |  |
| 31 | "The roster (`runner/tests/switch_roster.py`) says, per control, what a…" | pre-release | flows |  |
| 32 | "A leg judges only the entries it can;…" | pre-release | flows |  |
| 33 | "What the platforms cannot prove is what the…" | pre-release | flows |  |
| 34 | "The real cages elsewhere are named in `docs/security/security-gaps.md`…" | pre-release | flows |  |
| 35 | "<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands mid-document where a second part of the page begins |
| 36 | "The suite proves a commit on one Python…" | pre-release | flows |  |
| 37 | "These prove what it cannot:" | pre-release | flows |  |
| 38 | "Proof \| What it proves \| When" | pre-release | flagged | Table header row, structure rather than a sentence |
| 39 | "`python-range` \| the whole suite on the 3.9…" | pre-release | flows |  |
| 40 | "`upgrade-proof` \| the last release installs, the owner's…" | pre-release | flows |  |
| 41 | "`soak` \| two hours of the real poll…" | pre-release | flows |  |
| 42 | "`hardware` \| the suite, the platform proof, the…" | pre-release | flows |  |
| 43 | "`coverage` \| the map of code no test…" | pre-release | flows |  |
| 44 | "`stamp-audit` \| every commit's agent stamp against `docs/archive/RESEARCHER_IDENT.md`…" | pre-release | flows |  |
| 45 | "`test_parser_properties` \| every parser that reads input the…" | pre-release | flows |  |
| 46 | "`test_live_capture` \| the runner's readers take three days…" | pre-release | flows |  |
| 47 | "The live capture is the suite's one corpus…" | pre-release | flows |  |
| 48 | "A change that would not read those files…" | pre-release | flows |  |
| 49 | "A box with no package index can still…" | pre-release | flows |  |
| 50 | "Two tools do it with the standard library's…" | pre-release | flows |  |
| 51 | "Tool \| For \| Child processes" | pre-release | flagged | Table header row, structure rather than a sentence |
| 52 | "`runner/tools/linecov.py --out cov.json --source <path> -- <test names>`…" | pre-release | flows |  |
| 53 | "`runner/tools/stdlib_coverage.py --subprocess --jobs N --out cov.json` \| the…" | pre-release | flows |  |
| 54 | "`runner/tools/coverage_one.py [--jobs N]` \| both of the above,…" | pre-release | flows |  |
| 55 | "`docs/reports/coverage/` and `docs/reports/local-rig-2026-10-27/` keep the reports they have…" | pre-release | flows |  |
| 56 | "On the same tree both read at or…" | pre-release | flows |  |
| 57 | "`linecov.py` leaves out of a count what no…" | pre-release | flows |  |
| 58 | "Its keys use `/` on every box." | pre-release | flows |  |
| 59 | "A whole-suite pass takes about twelve minutes on…" | pre-release | flows |  |
| 60 | "Running the same proofs locally:" | pre-release | flows |  |
| 61 | "A box with no PyPI runs all of…" | pre-release | flows |  |
| 62 | "hypothesis is a test-only dependency: without it a…" | pre-release | flows |  |
| 63 | "A module that is nothing but property tests…" | pre-release | flows |  |
| 64 | "Neither stands in under CI (`GITHUB_ACTIONS` or `CI`…" | pre-release | flows |  |
| 65 | "Adding a platform leg: copy the nearest job…" | pre-release | flows |  |
| 66 | "A test that only works on one kernel…" | pre-release | flows |  |
