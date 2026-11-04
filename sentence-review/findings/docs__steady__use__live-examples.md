# Findings — docs/steady/use/live-examples.md

Source: docs/steady/use/live-examples.md, reviewed at main a190a50a.
Sentence units: 81. Flagged: 18. Categories: pre-release 81, post-release 0.

A page built from a real 3-day capture: the setup, the generated facts block, what the numbers say, then a run of captured excerpts (the flagread job at 3 views, a failing job, the Oracle ledger, resource pressure, the refusals, the posture report), each introduced by a short prose caption. The argument chains — nothing lost, the round trip is waiting, the box ran hot, predictions are a base rate — and the excerpt captions, several of them verbless, are the page's standing introduction pattern and flow as captions. The non-sentences are the stamp comment, the thesis fragment (unit 2), the facts table's header row (unit 15), and the 15 HTML boundary/source comments that mark the excerpts and the generated block; the table's data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "What a real runner wrote, and what three…" | pre-release | flagged | Fragment with no verb; it states the page's thesis, which the next 2 sentences then set up |
| 3 | "Everything below is either a verbatim line from…" | pre-release | flows |  |
| 4 | "Each excerpt names its file, and `runner/tests/test_live_capture.py` fails…" | pre-release | flows |  |
| 5 | "The test box is a two-core Linux VM,…" | pre-release | flows |  |
| 6 | "It ran as root with confinement off, every…" | pre-release | flows |  |
| 7 | "Mail carried jobs at first; after the mail-off…" | pre-release | flows |  |
| 8 | "The test sent the same eight scripts in…" | pre-release | flows |  |
| 9 | "That is a test bench, deliberately wide open,…" | pre-release | flows |  |
| 10 | "A real install starts with the `password-only` profile…" | pre-release | flows |  |
| 11 | "<!-- live-facts:begin --> <!-- Written by runner/tools/live_capture.py --write-doc;…" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 12 | "-->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 13 | "**19,227 jobs**, completed 2026-10-23T05:10:48Z to 2026-10-24T23:18:35Z." | pre-release | flows |  |
| 14 | "Every one came back: 19,227 results, 19,227 verified,…" | pre-release | flows |  |
| 15 | "Job \| Runs \| Exit codes" | pre-release | flagged | Table header row, structure rather than a sentence |
| 16 | "`clock` \| 2,404 \| exit 0 x 2,404" | pre-release | flows |  |
| 17 | "`envmark` \| 2,404 \| exit 0 x 2,404" | pre-release | flows |  |
| 18 | "`exit3` \| 2,403 \| exit 3 x 2,403" | pre-release | flows |  |
| 19 | "`flagread` \| 2,404 \| exit 0 x 2,404" | pre-release | flows |  |
| 20 | "`hostinfo` \| 2,404 \| exit 0 x 2,404" | pre-release | flows |  |
| 21 | "`shadow` \| 2,403 \| exit 0 x 2,403" | pre-release | flows |  |
| 22 | "`sysstat` \| 2,402 \| exit 0 x 2,402" | pre-release | flows |  |
| 23 | "`workdir` \| 2,403 \| exit 0 x 2,403" | pre-release | flows |  |
| 24 | "**Time on the box** (the script itself): median…" | pre-release | flows |  |
| 25 | "**Round trip** (signed job handed over to verified…" | pre-release | flows |  |
| 26 | "The 249 results that went back by mail,…" | pre-release | flows |  |
| 27 | "**Resource pressure**: 171 events (40 cpu, 131 mem),…" | pre-release | flows |  |
| 28 | "**Refused at the door**: 2 bad_signature, 1 cleartext_not_supported." | pre-release | flows |  |
| 29 | "**Oracle predictions** (deterministic mode): 2,247, all `likely_success` x…" | pre-release | flows |  |
| 30 | "Of 2,248 reconciled, 1,967 were right (87.5%); that…" | pre-release | flows |  |
| 31 | "The ledger keeps its newest lines, so it…" | pre-release | flows |  |
| 32 | "**runner.log**: 33,525 lines kept (11,735 INFO, 1,936 DEBUG,…" | pre-release | flows |  |
| 33 | "<!-- live-facts:end -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 34 | "What the numbers say:" | pre-release | flows |  |
| 35 | "**Nothing was lost.** Every job produced a result…" | pre-release | flows |  |
| 36 | "Three messages were refused before anything ran (two…" | pre-release | flows |  |
| 37 | "**The round trip is the waiting, not the…" | pre-release | flows |  |
| 38 | "By mail the same jobs took about three…" | pre-release | flows |  |
| 39 | "**The box ran hot and kept going.** The…" | pre-release | flows |  |
| 40 | "Each event is a security event the DRI…" | pre-release | flows |  |
| 41 | "**Deterministic predictions are a base rate.** With no…" | pre-release | flows |  |
| 42 | "Use the prediction as a record, not as…" | pre-release | flows |  |
| 43 | "**`full` means full.** At `max_result_view: full` the result…" | pre-release | flows |  |
| 44 | "The `flagread` job prints a planted fake credential…" | pre-release | flows |  |
| 45 | "That is the reason the default ceiling is…" | pre-release | flows |  |
| 46 | "The configuration the test ran under, from the…" | pre-release | flows |  |
| 47 | "<!-- source: runner.log -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 48 | "The last `flagread` of the run, as the…" | pre-release | flows |  |
| 49 | "The log truncates stdout and redacts what it…" | pre-release | flows |  |
| 50 | "<!-- source: runner.log -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 51 | "<!-- source: runner.log -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 52 | "The same job as the SI received it,…" | pre-release | flows |  |
| 53 | "<!-- source: campaign-results.jsonl.gz -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 54 | "And on the wire, where nobody without the…" | pre-release | flows |  |
| 55 | "<!-- source: envelopes/result-campaign.txt -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 56 | "A failing job finishes the same way; `exit3`…" | pre-release | flows |  |
| 57 | "<!-- source: runner.log -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 58 | "A prediction and the reconciliation that graded one,…" | pre-release | flows |  |
| 59 | "This one is the `exit3` job above:" | pre-release | flows |  |
| 60 | "<!-- source: oracle-learning.jsonl -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 61 | "Every reconciliation above ends `"lesson_selected": null`, and the…" | pre-release | flows |  |
| 62 | "That is the learning design working as written,…" | pre-release | flows |  |
| 63 | "A verified fact is derived from a cause…" | pre-release | flows |  |
| 64 | "The `exit3` script runs `exit 3` with every…" | pre-release | flows |  |
| 65 | "The other kind of lesson, a model candidate…" | pre-release | flows |  |
| 66 | "A Pi Light Oracle is right about the…" | pre-release | flows |  |
| 67 | "Resource pressure, as the log says it and…" | pre-release | flows |  |
| 68 | "<!-- source: runner.log -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 69 | "<!-- source: security-events.jsonl -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 70 | "The three messages refused at the door, all…" | pre-release | flows |  |
| 71 | "<!-- source: security-events.jsonl -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 72 | "Mail broke before the mail-off; the runner kept…" | pre-release | flows |  |
| 73 | "<!-- source: runner.log -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 74 | "`runner.py --posture` from the tree at capture time…" | pre-release | flows |  |
| 75 | "Every warning here is the box's open setup,…" | pre-release | flows |  |
| 76 | "<!-- source: posture.txt -->" | pre-release | flagged | An HTML source/boundary comment, not a sentence; it marks where a captured excerpt or a generated block sits |
| 77 | "The matching `--audit-report` is empty: with every mode…" | pre-release | flows |  |
| 78 | "`python3 runner/tools/live_capture.py` prints every number above as JSON;…" | pre-release | flows |  |
| 79 | "The job records are one JSON object per…" | pre-release | flows |  |
| 80 | "The suite replays parts of the capture through…" | pre-release | flows |  |
| 81 | "A change that would not read a real…" | pre-release | flows |  |
