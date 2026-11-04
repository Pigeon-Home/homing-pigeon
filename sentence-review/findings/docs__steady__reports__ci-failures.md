# Findings — docs/steady/reports/ci-failures.md

Source: docs/steady/reports/ci-failures.md, reviewed at main cbb52068.
Sentence units: 70. Flagged: 1. Categories: pre-release 58, post-release 12.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This report belongs to package 3.12.56." | pre-release | flows |  |
| 2 | "It answers one question the owner asked on…" | pre-release | flows |  |
| 3 | "The method is the one the owner named:…" | pre-release | flows |  |
| 4 | "The corpus is every workflow run GitHub still…" | pre-release | flows |  |
| 5 | "Numbers below are from that record." | pre-release | flows |  |
| 6 | "Job logs could not be read from where…" | pre-release | flows |  |
| 7 | "**No timer fired.** The pipeline had exactly one…" | pre-release | flows |  |
| 8 | "Nothing else carries a timer; the helper scripts…" | pre-release | flows |  |
| 9 | "Zero jobs ended with the conclusion `timed_out`." | pre-release | flows |  |
| 10 | "Whatever has been red was not cut short…" | pre-release | flows |  |
| 11 | "**The red is the test suite, and it…" | pre-release | flows |  |
| 12 | "The jobs that failed: `build-windows` 259 times, `test`…" | pre-release | flows |  |
| 13 | "On main, 241 runs were red on Windows…" | pre-release | flows |  |
| 14 | "The Windows failures are therefore not the same…" | pre-release | flows |  |
| 15 | "Red came in streaks: 27 one-run reds fixed…" | pre-release | flows |  |
| 16 | "By day, main's red fraction was 27%, 66%,…" | pre-release | flows |  |
| 17 | "**The 13-hour stalls were a retired runner label,…" | pre-release | flows |  |
| 18 | "46 such jobs in `build`, 59 in `platform-matrix`;…" | pre-release | flows |  |
| 19 | "Since the move the job runs in 1-3…" | pre-release | flows |  |
| 20 | "The stall was the pipeline's only "it never…" | pre-release | flows |  |
| 21 | "**The long pole of a release is mutation,…" | pre-release | flows |  |
| 22 | "The 20 tags cut between 21:53Z and 22:08Z…" | pre-release | flows |  |
| 23 | "The release job itself averages 0.5 minutes." | pre-release | flows |  |
| 24 | "In runner minutes over the window, by GitHub's…" | pre-release | flows |  |
| 25 | "Most of the macOS share is 845 one-minute…" | pre-release | flows |  |
| 26 | "**The annotations meant to name the failing test…" | pre-release | flows |  |
| 27 | "A `-v` log of a 4,500-test suite carries…" | pre-release | flows |  |
| 28 | "Result: 126 of 137 red Linux suite runs…" | pre-release | flows |  |
| 29 | "The Windows shard runner annotated nothing at all;…" | pre-release | flows |  |
| 30 | "**Smaller shapes, for completeness.** Eleven runs on 2026-10-16…" | pre-release | flows |  |
| 31 | "Three `typecheck` failures, one `sourceforge`, one `build-python`." | pre-release | flows |  |
| 32 | "Queue waits are not a factor anywhere but…" | pre-release | flows |  |
| 33 | "Measurement first, by the owner's instruction: no timer…" | pre-release | flows |  |
| 34 | "The mutation job's `timeout-minutes: 40` is removed." | pre-release | flows |  |
| 35 | "It was the only one. `tests/test_build_config.py` now pins…" | pre-release | flows |  |
| 36 | "The platform ceiling of 360 minutes per job…" | pre-release | flows |  |
| 37 | "The Linux suite runs with `--durations 25`; the…" | pre-release | flows |  |
| 38 | "Each Windows shard also reports its wall time." | pre-release | flows |  |
| 39 | "Under Actions, the Windows shard runner turns every…" | pre-release | flows |  |
| 40 | "`skip_guard.py --annotate` spends its ten annotations on `FAIL:`…" | pre-release | flows |  |
| 41 | "Nothing was removed from the pipeline." | pre-release | flows |  |
| 42 | "Every job, step and proof runs as before." | pre-release | flows |  |
| 43 | "The record above is the seed corpus." | pre-release | flows |  |
| 44 | "These are the mutations of "a push to…" | pre-release | flows |  |
| 45 | "Mutation of a run ; Seen ; Catches…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 46 | "A test passes on Linux and fails on…" | pre-release | flows |  |
| 47 | "A test fails on Linux only ; 125…" | pre-release | flows |  |
| 48 | "A runner label GitHub has retired ; 105…" | pre-release | flows |  |
| 49 | "Twenty tags in fifteen minutes ; 20 runs…" | pre-release | flows |  |
| 50 | "A startup regression in the frozen binary ;…" | pre-release | flows |  |
| 51 | "A `::error` cap spent on fixture noise ;…" | pre-release | flows |  |
| 52 | "A push that cancels the run before it…" | pre-release | flows |  |
| 53 | "Not seen once in 1,000 runs: a job…" | pre-release | flows |  |
| 54 | "The things that are slow are deterministic and…" | pre-release | flows |  |
| 55 | "For scale, the first `--durations` run of the…" | pre-release | flows |  |
| 56 | "Nothing else takes more than 4.3 s." | pre-release | flows |  |
| 57 | "If the suite ever needs to be faster,…" | pre-release | flows |  |
| 58 | "Proposals, not changes; each is one commit when…" | post-release | flows |  |
| 59 | "**Move mutation off the tag path.** It is…" | post-release | flows |  |
| 60 | "Running mutation nightly on main (or on `workflow_dispatch`)…" | post-release | flows |  |
| 61 | "**Stop building macOS arm64 and Windows arm64 on…" | post-release | flows |  |
| 62 | "Gating them on tags saves 23% of billing-weighted…" | post-release | flows |  |
| 63 | "The x86_64 Linux build and the Pi Light…" | post-release | flows |  |
| 64 | "**Give scarce runners a short timer, deliberately.** Finding…" | post-release | flows |  |
| 65 | "A `timeout-minutes: 30` on the macOS x86_64 and…" | post-release | flows |  |
| 66 | "**Make the Windows population visible before deciding anything…" | post-release | flows |  |
| 67 | "Until then no Windows change is worth making." | post-release | flows |  |
| 68 | "**Leave `test`, `typecheck`, `build-linux`, `build-pi-light`, `build-python`, `minimal-userland`, `docker`…" | post-release | flows |  |
| 69 | "Put `timeout-minutes: 40` back on the mutation job…" | post-release | flows |  |
| 70 | "Everything else in this release stays useful after…" | pre-release | flows |  |
