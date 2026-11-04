# Findings — docs/infrastructure-documents/proofs/content-sh-freebsd.md

Source: docs/infrastructure-documents/proofs/content-sh-freebsd.md, reviewed at main cbb52068.
Sentence units: 27. Flagged: 1. Categories: pre-release 27, post-release 0.

A run record: the setup, the results table, then 3 short paragraphs on what the result does and does not mean. The results table's rows are counted as units; its header row (unit 9) is structure standing in the sentence flow and is flagged for that reason alone. The prose itself is tightly chained — each paragraph answers the question the previous one raises.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The program was `/bin/sh` inside a FreeBSD 15.0-RELEASE-p13…" | pre-release | flows |  |
| 2 | "The guest is the one `freebsd.yml` already boots…" | pre-release | flows |  |
| 3 | "The run is https://github.com/Pigeon-Home/homing-pigeon/actions/runs/41387454749 ." | pre-release | flows |  |
| 4 | "`freebsd-version` printed `15.0-RELEASE-p13` at 2026-11-02 04:16:32Z." | pre-release | flows |  |
| 5 | "The phase was `HP_FREEBSD_SH=/bin/sh HP_FREEBSD_SYNTAX_ONLY=1`." | pre-release | flows |  |
| 6 | "That asks `sh -n` only." | pre-release | flows |  |
| 7 | "`handle_mail` was not called." | pre-release | flows |  |
| 8 | "Both tests passed, in 0.217 seconds, and the…" | pre-release | flows |  |
| 9 | "Rung \| What `/bin/sh -n` did" | pre-release | flagged | Table header row, structure rather than a sentence; it names the columns the following rows fill |
| 10 | "49 characters \| 3,269 scripts, each at most…" | pre-release | flows |  |
| 11 | "5,000 \| three different scripts, accepted" | pre-release | flows |  |
| 12 | "50,000 \| three different scripts, accepted" | pre-release | flows |  |
| 13 | "500,000 \| three different scripts, accepted" | pre-release | flows |  |
| 14 | "1,048,576 \| three different scripts, accepted" | pre-release | flows |  |
| 15 | "one byte over each of those \| accepted,…" | pre-release | flows |  |
| 16 | "`sh -n` does not know `max_script_bytes`." | pre-release | flows |  |
| 17 | "Accepting 1,048,577 is what a parser does." | pre-release | flows |  |
| 18 | "The refusal of that length, naming the cap,…" | pre-release | flows |  |
| 19 | "It was not asked again here." | pre-release | flows |  |
| 20 | "The job that contained this phase later failed." | pre-release | flows |  |
| 21 | "The suite reported 2 failures and 10 errors,…" | pre-release | flows |  |
| 22 | "Those are not this check." | pre-release | flows |  |
| 23 | "The parser phase had already printed `OK`, and…" | pre-release | flows |  |
| 24 | "A Linux machine still skips the test." | pre-release | flows |  |
| 25 | "dash was not used." | pre-release | flows |  |
| 26 | "bash was not used." | pre-release | flows |  |
| 27 | "The earlier attempts to build FreeBSD's `sh` on…" | pre-release | flows |  |
