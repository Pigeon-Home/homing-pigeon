# Findings — docs/steady/reports/queues-2026-10-27.md

Source: docs/steady/reports/queues-2026-10-27.md, reviewed at main cbb52068.
Sentence units: 26. Flagged: 1. Categories: pre-release 26, post-release 0.

A deployment record told in short factual statements: the setup, 2 probe requests and what each answer means, then the timed run of 1 ping. The staccato runs (units 9 to 11) are a configuration list, and the list is the connection, so they flow. The probe table's header row (unit 12) is structure and is flagged on that ground alone; its 2 data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "A one-tenant Cloudflare Worker and one Linux runner,…" | pre-release | flows |  |
| 2 | "Nothing below is a secret." | pre-release | flows |  |
| 3 | "The Worker's hostname, the runner token, the SI…" | pre-release | flows |  |
| 4 | "The Worker is the one-tenant shape: `TENANT`, `SI_TOKEN`,…" | pre-release | flows |  |
| 5 | "The Durable Object binding is `TENANT_QUEUE`." | pre-release | flows |  |
| 6 | "The runner was installed with the `hosted` profile…" | pre-release | flows |  |
| 7 | "Its queue URL is the Worker's `/t/homingpigeon02` base." | pre-release | flows |  |
| 8 | "The runner token is the blob's `transport_queues.token`, because…" | pre-release | flows |  |
| 9 | "Poll interval 20 seconds." | pre-release | flows |  |
| 10 | "The runner dials out." | pre-release | flows |  |
| 11 | "Nothing on it listens." | pre-release | flows |  |
| 12 | "Request \| Result" | pre-release | flagged | Table header row, structure rather than a sentence |
| 13 | "`GET /t/homingpigeon02/jobs` with no bearer \| `401 {"error":"runner…" | pre-release | flows |  |
| 14 | "`GET /t/not-a-tenant/jobs` with no bearer \| `404 {"error":"unknown…" | pre-release | flows |  |
| 15 | "The first line means the tenant is configured…" | pre-release | flows |  |
| 16 | "The second means any other slug is not…" | pre-release | flows |  |
| 17 | "At 21:03:36 UTC the SI posted one ping." | pre-release | flows |  |
| 18 | "The Worker accepted it with `202`." | pre-release | flows |  |
| 19 | "The id was `67afed13-2d34-4065-8f9e-8571b433d7c3`." | pre-release | flows |  |
| 20 | "The runner, which had been pulling since 21:00:56…" | pre-release | flows |  |
| 21 | "Startup beside that: `judge=advisory`, `ceiling=attested`, `workspace=/data/work`, `workers=1`." | pre-release | flows |  |
| 22 | "The SI then read `GET /results?max=3` with its…" | pre-release | flows |  |
| 23 | "The envelope is the encrypted form (`hp_enc`), and…" | pre-release | flows |  |
| 24 | "The body was not decrypted for this note." | pre-release | flows |  |
| 25 | "At 21:38 UTC the same runner was still…" | pre-release | flows |  |
| 26 | "No second job had been posted." | pre-release | flows |  |
