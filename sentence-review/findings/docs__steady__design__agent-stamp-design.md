# Findings — docs/steady/design/agent-stamp-design.md

Source: docs/steady/design/agent-stamp-design.md, reviewed at main 3b99fe45.
Sentence units: 49. Flagged: 3. Categories: pre-release 41, post-release 8.

A design record for agent stamps: what a stamp is, where it appears, the spellings seen, 2 proposals, the runtime surfaces not yet built, the questions still open, and the enforcement that has since landed. The design half and the record half chain cleanly — the enforcement section answers the design section point by point. The proposals and the unbuilt surfaces (units 23, 24, 28 to 30, and the proposed answers 33, 34, 36) are the document's post-release statements. 3 units are flagged: the stamp comment at the head, the surfaces table's header row, and unit 8, the first half of a sentence split at its own quoted question.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "Status: the record is enforced by `runner/tests/test_agent_stamps.py` (every…" | pre-release | flows |  |
| 3 | "The rest is the design as captured." | pre-release | flows |  |
| 4 | "Several agent chats work on this repo." | pre-release | flows |  |
| 5 | "Each one has its own stamp, a UUID-shaped…" | pre-release | flows |  |
| 6 | "The stamp works like a software watermark." | pre-release | flows |  |
| 7 | "It is not a credential and grants nothing." | pre-release | flows |  |
| 8 | "Its only job is to make "which agent…" | pre-release | flagged | First half of a sentence split at its quoted question mark; the sentence completes in unit 9 |
| 9 | "answerable with `grep`." | pre-release | flows |  |
| 10 | "A stamp only helps tracing if a person…" | pre-release | flows |  |
| 11 | "So it is always visible text: no zero-width…" | pre-release | flows |  |
| 12 | "Surface \| Form" | pre-release | flagged | Table header row, structure rather than a sentence |
| 13 | "Commit message \| trailer `Agent-Stamp: <uuid>`, next to…" | pre-release | flows |  |
| 14 | "PR description \| footer line `Agent-Stamp: <uuid>`" | pre-release | flows |  |
| 15 | "New source file \| first-line comment `# Agent-Stamp:…" | pre-release | flows |  |
| 16 | "New Markdown file \| `<!-- Agent-Stamp: <uuid> -->`…" | pre-release | flows |  |
| 17 | "Chat deliverables \| short sign-off with the full…" | pre-release | flows |  |
| 18 | "To find everything one agent touched:" | pre-release | flows |  |
| 19 | "The canonical spelling is `Agent-Stamp`." | pre-release | flows |  |
| 20 | "Variants seen so far:" | pre-release | flows |  |
| 21 | "`# agent-ident: ...` in two files since retired…" | pre-release | flows |  |
| 22 | "an `Agent-Chat-Stamp:` trailer and file header, the spelling…" | pre-release | flows |  |
| 23 | "Proposal: rewrite the two file headers to `Agent-Stamp`." | post-release | flows |  |
| 24 | "Leave history alone, and have the search tooling…" | post-release | flows |  |
| 25 | "Static stamps record which agent *edited* something." | pre-release | flows |  |
| 26 | "They say nothing about which agent *drove the…" | pre-release | flows |  |
| 27 | "Possible runtime surfaces:" | pre-release | flows |  |
| 28 | "**Protocol header**: an optional `X-Agent-Stamp` field on requests…" | post-release | flows |  |
| 29 | "**Structured log field**: `agent_stamp` on every job record,…" | post-release | flows |  |
| 30 | "**Snapshot manifest**: release snapshots list the stamps present…" | post-release | flows |  |
| 31 | "Questions to settle before any of this goes…" | pre-release | flows |  |
| 32 | "Is the stamp ever trusted for anything?" | pre-release | flows |  |
| 33 | "Proposed answer: no, it is advisory only." | post-release | flows |  |
| 34 | "A spoofed stamp misattributes work but must never…" | post-release | flows |  |
| 35 | "Should the runner reject malformed stamps or just…" | pre-release | flows |  |
| 36 | "Proposed answer: log as given, cap the length,…" | post-release | flows |  |
| 37 | "`runner/tests/test_agent_stamps.py` (2026-10-26) lists every stamp written after a…" | pre-release | flows |  |
| 38 | "It runs with the suite, so a stamp…" | pre-release | flows |  |
| 39 | "It does not flag spellings: both `Agent-Stamp` and…" | pre-release | flows |  |
| 40 | "The tree check sees stamps in files; it…" | pre-release | flows |  |
| 41 | "`runner/tools/stamp_audit.py` reads the commit trailers instead (`Agent-Stamp` or…" | pre-release | flows |  |
| 42 | "History before that moment is reported, never failed." | pre-release | flows |  |
| 43 | "The suite runs the check on whatever history…" | pre-release | flows |  |
| 44 | "The `stamp-audit` workflow used to run it over…" | pre-release | flows |  |
| 45 | "It is off as of 2026-11-01: dispatch only,…" | pre-release | flows |  |
| 46 | "The baseline is `docs/reports/stamp-audit/2026-10-27.md`." | pre-release | flows |  |
| 47 | "A stamp outlives its chat." | pre-release | flows |  |
| 48 | "When a chat stops working on the project…" | pre-release | flows |  |
| 49 | "Researchers one to three (`10000c2a`, `200003d4`, `30000f1a`) were…" | pre-release | flows |  |
