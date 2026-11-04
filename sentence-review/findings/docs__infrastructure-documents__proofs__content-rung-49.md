# Findings — docs/infrastructure-documents/proofs/content-rung-49.md

Source: docs/infrastructure-documents/proofs/content-rung-49.md, reviewed at main c0f3e44f.
Sentence units: 51. Flagged: 2. Categories: pre-release 51, post-release 0.

A proof record in the house style: how the set was generated, what the checkers did, what the gate did, what it does not say, and a first-hand verification. Short declarative sentences, each handing to the next; the only breaks are the 2 1-word shell labels standing as their own paragraphs.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The earlier series listed twenty-two scripts here." | pre-release | flows |  |
| 2 | "This replaces that sample with a generated set." | pre-release | flows |  |
| 3 | "It does not reuse a stage number." | pre-release | flows |  |
| 4 | "The old record, `stage7.md`, stays as history." | pre-release | flows |  |
| 5 | "Bash." | pre-release | flagged | A 1-word label standing as its own paragraph; the shell's generation paragraph arrives after it with no sentence to carry it |
| 6 | "Twenty-two atoms: simple commands, quoting, a parameter expansion,…" | pre-release | flows |  |
| 7 | "Every atom is kept." | pre-release | flows |  |
| 8 | "Every pair of atoms joined by `&&`, `||`,…" | pre-release | flows |  |
| 9 | "Every triple of the atoms that are themselves…" | pre-release | flows |  |
| 10 | "That is 3,682 scripts." | pre-release | flows |  |
| 11 | "The longest is 46 characters." | pre-release | flows |  |
| 12 | "PowerShell." | pre-release | flagged | A 1-word label standing as its own paragraph; the shell's generation paragraph arrives after it with no sentence to carry it |
| 13 | "Ten atoms in its own syntax, the same…" | pre-release | flows |  |
| 14 | "That produced 521 candidates." | pre-release | flows |  |
| 15 | "The real parser rejected 10 of them." | pre-release | flows |  |
| 16 | "Those 10 were not given to the gate." | pre-release | flows |  |
| 17 | "511 survived, each at most 49 characters." | pre-release | flows |  |
| 18 | "PowerShell's constructs are longer than bash's, so 49…" | pre-release | flows |  |
| 19 | "The record says so." | pre-release | flows |  |
| 20 | "511 is the set the bound can hold,…" | pre-release | flows |  |
| 21 | "`bash -n` was run once on the 3,682…" | pre-release | flows |  |
| 22 | "Exit code 0." | pre-release | flows |  |
| 23 | "A syntax error in any script would have…" | pre-release | flows |  |
| 24 | "No checker crashed." | pre-release | flows |  |
| 25 | "PowerShell 7.5.4 parsed the 521 candidates in one…" | pre-release | flows |  |
| 26 | "The binary was a stock 7.5.4 linux-x64 build." | pre-release | flows |  |
| 27 | "The test looks for `pwsh` on `PATH` and…" | pre-release | flows |  |
| 28 | "Where neither exists, the PowerShell cases skip and…" | pre-release | flows |  |
| 29 | "On the machine that produced this record, they…" | pre-release | flows |  |
| 30 | "`handle_mail` admitted all 3,682 bash scripts and all…" | pre-release | flows |  |
| 31 | "The decision did not depend on which constructs…" | pre-release | flows |  |
| 32 | "The cap check is a sample, and it…" | pre-release | flows |  |
| 33 | "Twenty bash scripts longer than one byte were…" | pre-release | flows |  |
| 34 | "The one-byte script `:` was admitted at that…" | pre-release | flows |  |
| 35 | "The admission of the whole set is not…" | pre-release | flows |  |
| 36 | "The cap check is." | pre-release | flows |  |
| 37 | "The harness is `runner/tests/test_proof_content_rung49.py`." | pre-release | flows |  |
| 38 | "The scripts were syntax-checked, not executed." | pre-release | flows |  |
| 39 | "The five tests passed in about 50 seconds." | pre-release | flows |  |
| 40 | "This is not every string of 49 characters." | pre-release | flows |  |
| 41 | "It is the combinations of this atom list,…" | pre-release | flows |  |
| 42 | "Deeper nesting is not in the set." | pre-release | flows |  |
| 43 | "The rungs above 49 are not claimed here." | pre-release | flows |  |
| 44 | "This record was re-checked first-hand after it landed,…" | pre-release | flows |  |
| 45 | "**The generation was recomputed independently**, outside the test…" | pre-release | flows |  |
| 46 | "Both numbers match the record." | pre-release | flows |  |
| 47 | "**The tests were re-run.** The harness's 5 tests…" | pre-release | flows |  |
| 48 | "The PowerShell parser dropped exactly 10 candidates and…" | pre-release | flows |  |
| 49 | "`bash -n` accepted the whole bash set as…" | pre-release | flows |  |
| 50 | "**The code was re-read.** The gate's only length…" | pre-release | flows |  |
| 51 | "No step branches on a script's text." | pre-release | flows |  |
