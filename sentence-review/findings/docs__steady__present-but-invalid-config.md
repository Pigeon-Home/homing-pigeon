# Findings — docs/steady/present-but-invalid-config.md

Source: docs/steady/present-but-invalid-config.md, reviewed at main 7c9d289d.
Sentence units: 46. Flagged: 1. Categories: pre-release 46, post-release 0.

The present-but-invalid decision record: the documented defaults, the gap the docs were silent on, the 2 policies already living in the code with what each costs, the split rule, and the decision restating it. The argument is linear and each policy's cost paragraph answers the policy paragraph before it; the decision list at units 36 to 43 restates the rule in force, its short lines ('Default, not silent.', 'Live reload.') reading as the list's own beats. The stamp comment (unit 1) is the only non-sentence.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "Status: decision record, written 2026-10-24 from the documented-default…" | pre-release | flows |  |
| 3 | "The decision at the end was made 2026-10-23;…" | pre-release | flows |  |
| 4 | "The rule below is applied in code; "Applied…" | pre-release | flows |  |
| 5 | "Every numeric and enum setting in `config.json` has…" | pre-release | flows |  |
| 6 | "The docs are clear about what happens when…" | pre-release | flows |  |
| 7 | "They are silent about a key that is…" | pre-release | flows |  |
| 8 | "The hunt handed every reader those values and…" | pre-release | flows |  |
| 9 | "**Policy A, read as the default.** The reader…" | pre-release | flows |  |
| 10 | "`runner/guard/confval.py` is this policy written once (`number`, `integer`,…" | pre-release | flows |  |
| 11 | "A boolean is never a number there, a…" | pre-release | flows |  |
| 12 | "**Policy B, refuse to start.** The reader raises…" | pre-release | flows |  |
| 13 | "Four readers do this and did before the…" | pre-release | flows |  |
| 14 | "The hunt kept them that way: `confval.is_number` is…" | pre-release | flows |  |
| 15 | "Nothing in the docs says which keys get…" | pre-release | flows |  |
| 16 | "The split is the history of who wrote…" | pre-release | flows |  |
| 17 | "A reads the docs literally and keeps a…" | pre-release | flows |  |
| 18 | "Its failure is quiet by construction." | pre-release | flows |  |
| 19 | "`transport_dtls.port: "2O220"` listens on 20220 and says so…" | pre-release | flows |  |
| 20 | "The warning is the whole safety net, and…" | pre-release | flows |  |
| 21 | "B catches the typo while the operator is…" | pre-release | flows |  |
| 22 | "Its failure is loud and total: a transport…" | pre-release | flows |  |
| 23 | "B also contradicts the docs for every key…" | pre-release | flows |  |
| 24 | "The job-supplied values are not part of this…" | pre-release | flows |  |
| 25 | "A query's `max_matches`, `lines` or `max_chars` comes from…" | pre-release | flows |  |
| 26 | "Split by what a wrong value changes, and…" | pre-release | flows |  |
| 27 | "**Refuse (B)** when the wrong value changes who…" | pre-release | flows |  |
| 28 | "These are the readers that already refuse, plus…" | pre-release | flows |  |
| 29 | "**Default and say so (A)** for everything else:…" | pre-release | flows |  |
| 30 | "The warning becomes visible: one line at startup,…" | pre-release | flows |  |
| 31 | "The rule for a new key, one sentence…" | pre-release | flows |  |
| 32 | "Under this rule the current code is right…" | pre-release | flows |  |
| 33 | "Decision (owner): Adopted as relayed 2026-10-23." | pre-release | flows |  |
| 34 | "Neither side is the rule." | pre-release | flows |  |
| 35 | "The rule is what a wrong value changes." | pre-release | flows |  |
| 36 | "Refuse to start when a wrong value changes…" | pre-release | flows |  |
| 37 | "That is the four readers that already refuse,…" | pre-release | flows |  |
| 38 | "Read as the documented default for everything else:…" | pre-release | flows |  |
| 39 | "Default, not silent." | pre-release | flows |  |
| 40 | "The fallback gets one startup line, "config: N…" | pre-release | flows |  |
| 41 | "Live reload." | pre-release | flows |  |
| 42 | "A bad value written while running reads as…" | pre-release | flows |  |
| 43 | "The refuse class cannot refuse mid-run: a bad…" | pre-release | flows |  |
| 44 | "Date: 2026-10-23" | pre-release | flows |  |
| 45 | "Applied in: the readers and the docs moved…" | pre-release | flows |  |
| 46 | "The warning has shipped: one startup line naming…" | pre-release | flows |  |
