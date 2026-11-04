# Findings — docs/steady/proofs/connector-roundtrip.md

Source: docs/steady/proofs/connector-roundtrip.md, reviewed at main cbb52068.
Sentence units: 32. Flagged: 3. Categories: pre-release 32, post-release 0.

A capture record from a live round trip: the happy path first, then the negative cases from the same session, then how to replay. The prose is plain and well chained. The 2 table header rows (units 7 and 23) are structure and are flagged on that ground alone; the data rows are counted as units and flow as records. Unit 17 is the bare label that introduces the notes list.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Captured from a live Gmail round-trip on 2026-10-13." | pre-release | flows |  |
| 2 | "These messages exercise the cloud side: sign, send,…" | pre-release | flows |  |
| 3 | "No IMAP login, no job execution on a…" | pre-release | flows |  |
| 4 | "The captures are replayed by `tests/test_connector_captures.py` to validate…" | pre-release | flows |  |
| 5 | "All messages are from the test address to…" | pre-release | flows |  |
| 6 | "Safe to delete." | pre-release | flows |  |
| 7 | "Field \| Value" | pre-release | flagged | Table header row, structure rather than a sentence |
| 8 | "Message \| `1a1380ce30ccfbfb`" | pre-release | flows |  |
| 9 | "Subject \| `[HOMING-PIGEON] TEST job c142d598-261a-4000-8a41-b8cb7d28bf38`" | pre-release | flows |  |
| 10 | "Kind \| `ping`" | pre-release | flows |  |
| 11 | "Secret used \| `test-shared-secret` (not a mailbox password)" | pre-release | flows |  |
| 12 | "Outcome \| `verify_body` on the JSON line returned…" | pre-release | flows |  |
| 13 | "The body as returned by `gmail_get_message` (`body_text`):" | pre-release | flows |  |
| 14 | "This capture is a protocol 1 message, which…" | pre-release | flows |  |
| 15 | "The signature is over those bytes." | pre-release | flows |  |
| 16 | "Do not edit the line." | pre-release | flows |  |
| 17 | "Notes:" | pre-release | flagged | A bare label, not a sentence; it names the notes that follow without leading into them |
| 18 | "The JSON line verifies." | pre-release | flows |  |
| 19 | "As of the body-extraction change, the full `body_text`…" | pre-release | flows |  |
| 20 | "The subject contains `TEST` between the prefix and…" | pre-release | flows |  |
| 21 | "These were sent the same way." | pre-release | flows |  |
| 22 | "Outcomes are from running the returned body through…" | pre-release | flows |  |
| 23 | "Subject \| Message \| What it probed \|…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 24 | "`NEG-sigin` \| `1a1380e84018aa6a` \| `,"sig":"` inside the script…" | pre-release | flows |  |
| 25 | "`NEG-upper` \| `1a1380e8aa70b40a` \| Uppercase hex signature \|…" | pre-release | flows |  |
| 26 | "`NEG-path` \| `1a1380e91cf58eef` \| `job_id` `../evil` \| Signature…" | pre-release | flows |  |
| 27 | "`NEG-naive` \| `1a1380e97ac687a9` \| `issued_at` with no timezone…" | pre-release | flows |  |
| 28 | "`NEG-strint` \| `1a1380e9d9d74822` \| `interpreter` as a string…" | pre-release | flows |  |
| 29 | "`NEG-tamper` \| `1a1380ea1d8c28d9` \| Flipped signature bytes \|…" | pre-release | flows |  |
| 30 | "`NEG-long` \| `1a1380e3be3907b0` \| Long-line wrap \| Placeholder…" | pre-release | flows |  |
| 31 | "Paste the JSON line from the happy-path body." | pre-release | flows |  |
| 32 | "Unit tests that replay the captured bodies live…" | pre-release | flows |  |
