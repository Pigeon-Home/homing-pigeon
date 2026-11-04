# Findings — docs/steady/reports/audit-2026-10-15.md

Source: docs/steady/reports/audit-2026-10-15.md, reviewed at main 3b99fe45.
Sentence units: 100. Flagged: 0. Categories: pre-release 100, post-release 0.

A dated claim-by-claim audit from 2026-10-15, bannered at the top with what later edits already corrected. Its body is a run of findings in a fixed shape — the claim, the code evidence, the fix — and the findings chain by that shape; a verified-true list and a priority summary close it. The quoted claims that open several findings (units 32, 38) read as interruptions until the verdict lands 1 or 2 units later, which is the audit's method rather than a break. Nothing is flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Snapshot from 2026-10-15." | pre-release | flows |  |
| 2 | "Do not treat the fix list below as…" | pre-release | flows |  |
| 3 | "Later edits on `main` corrected the README status,…" | pre-release | flows |  |
| 4 | "Cloudflare Queues is not in the runner." | pre-release | flows |  |
| 5 | "`runner/transports.py` exists in the current tree — it…" | pre-release | flows |  |
| 6 | "Read the current file before acting on a…" | pre-release | flows |  |
| 7 | "**Status:** internal audit, kept as a dated record." | pre-release | flows |  |
| 8 | "The findings were actioned in two passes (the…" | pre-release | flows |  |
| 9 | "Formerly `hidden_audit/audit-report.md`, renamed so the location says what…" | pre-release | flows |  |
| 10 | "**Baseline:** committed `main` at `39124d9` (v3.2.0 tag)." | pre-release | flows |  |
| 11 | "Read-only audit; no docs or code were edited." | pre-release | flows |  |
| 12 | "**Date:** 2026-10-15." | pre-release | flows |  |
| 13 | "**Scope:** all 18 markdown docs (root + `docs/`),…" | pre-release | flows |  |
| 14 | "**Lines 8–14:** table claims `nats`, `mqtt`, `redis`, `durable_objects`…" | pre-release | flows |  |
| 15 | "**Code:** commit `711c590` ("keep only email and Cloudflare…" | pre-release | flows |  |
| 16 | "At v3.2.0 `runner/transports.py` contains only `EmailTransport` and `CloudflareQueuesTransport`…" | pre-release | flows |  |
| 17 | "**Also lines 17–18:** "The others are wired so…" | pre-release | flows |  |
| 18 | "**Fix (doc edit):** rewrite the table to email…" | pre-release | flows |  |
| 19 | "**Lines 9–10:** "The local socket and the other…" | pre-release | flows |  |
| 20 | "**"Transports the mock SI can use" section:** "Local…" | pre-release | flows |  |
| 21 | "The only `socket` use in `runner/local_test.py` (lines 53–54)…" | pre-release | flows |  |
| 22 | "The entire "High-throughput local transport" section (length-prefixed framing,…" | pre-release | flows |  |
| 23 | "**`TRANSPORTS.md:248`:** "`(--local-test --browser)` speaks a length-prefixed protocol over…" | pre-release | flows |  |
| 24 | "**Fix (doc edit):** delete the local-socket sections; the…" | pre-release | flows |  |
| 25 | "**Docs:** `docs/local-si-test.md` (lines 29, 35, 55), `docs/handoff-local-si.md` (lines…" | pre-release | flows |  |
| 26 | "**Code:** `runner/runner.py`'s `ArgumentParser` (lines 2675+) defines no `--local-test`…" | pre-release | flows |  |
| 27 | "Running it prints usage and exits (verified: `error:…" | pre-release | flows |  |
| 28 | "The `getattr(args, "local_test", False)` branch at line 2751…" | pre-release | flows |  |
| 29 | "**Fix:** this is a **code bug**, not just…" | pre-release | flows |  |
| 30 | "Adding the flags is the smaller, intent-matching fix." | pre-release | flows |  |
| 31 | "Note: `docs/security-test-plan.md` lab setup (step 4) depends on…" | pre-release | flows |  |
| 32 | ""The Oracle also grows two optional capabilities (spec'd,…" | pre-release | flows |  |
| 33 | "Both shipped:" | pre-release | flows |  |
| 34 | "Local inference: `ask_model` (`runner.py:630`), `inference_config` (`runner.py:564`), the `ask`…" | pre-release | flows |  |
| 35 | "Execution confinement: `confined_to_workspace` attestation (`runner.py:407`), `snapshot_outside` with the…" | pre-release | flows |  |
| 36 | "(The "walk stops at 50000 files" sentence in…" | pre-release | flows |  |
| 37 | "**Fix (doc edit):** rewrite as shipped features with…" | pre-release | flows |  |
| 38 | ""The Oracle can restrict jobs to a single…" | pre-release | flows |  |
| 39 | "Implemented (see B1)." | pre-release | flows |  |
| 40 | "The "(v2, spec'd)" label is doubly stale —…" | pre-release | flows |  |
| 41 | "**Fix (doc edit):** change to implemented, point at…" | pre-release | flows |  |
| 42 | "The trailing Status paragraph says "v1.4.4… The v3…" | pre-release | flows |  |
| 43 | "This directly contradicts the Roadmap two screens up…" | pre-release | flows |  |
| 44 | "**Fix (doc edit):** the Status section is a…" | pre-release | flows |  |
| 45 | "Missing: `workspace_root`, `inference` (dict), `max_queries_per_hour`, `owner_instructions`, `redact_patterns_extra` (+…" | pre-release | flows |  |
| 46 | "All are real (`runner.py` lines 564–590, 808, 785,…" | pre-release | flows |  |
| 47 | "**Fix (doc edit):** add the missing keys (commented…" | pre-release | flows |  |
| 48 | "Verified: all 31 keys currently in the example…" | pre-release | flows |  |
| 49 | "`inference.endpoint` / `inference.model` are mentioned in prose in…" | pre-release | flows |  |
| 50 | "No doc lists the full sub-key set or…" | pre-release | flows |  |
| 51 | "**Fix (doc edit):** document the four sub-keys in…" | pre-release | flows |  |
| 52 | "`--inspect {board,budget,job,redact}` exists in argparse (`runner.py`) and is…" | pre-release | flows |  |
| 53 | "**Fix (doc edit):** add a row to the…" | pre-release | flows |  |
| 54 | "`docs/verify-v31.md` is properly bannered historical ("those checks no…" | pre-release | flows |  |
| 55 | "No action needed." | pre-release | flows |  |
| 56 | "`RUNBOOK.md` troubleshooting: "check … that the email was…" | pre-release | flows |  |
| 57 | "`README.md` (v1.4.0 note), `SECURITY.md` ("the sender address is…" | pre-release | flows |  |
| 58 | "A validly-signed job from a personal account works…" | pre-release | flows |  |
| 59 | "**Fix (doc edit):** reword to "check the signature/secret"…" | pre-release | flows |  |
| 60 | "Related: `SAFEGUARDS.md` §1 "Whoever can send mail *as*…" | pre-release | flows |  |
| 61 | "`README.md` Roadmap "Later: Cloudflare Queues as Transport #2"…" | pre-release | flows |  |
| 62 | "`docs/transports-status.md:17`: "Cloudflare is ready for a live try." | pre-release | flows |  |
| 63 | "Code at v3.2.0: a complete `CloudflareQueuesTransport` (send/poll/ack) exists…" | pre-release | flows |  |
| 64 | "These are reconcilable ("adapter written and tested, runner…" | pre-release | flows |  |
| 65 | "A reader gets "later" / "ready for a…" | pre-release | flows |  |
| 66 | "**Fix (doc edit):** one status line, ideally in…" | pre-release | flows |  |
| 67 | "The whole doc is aspirational bench prose (NATS/MQTT/Redis/Postgres/DO…" | pre-release | flows |  |
| 68 | "After the `711c590` cut it reads as a…" | pre-release | flows |  |
| 69 | "The comparison table (line 202) doesn't distinguish "design…" | pre-release | flows |  |
| 70 | "**Fix (doc edit):** add a status banner at…" | pre-release | flows |  |
| 71 | "**E1.** `docs/configuring-oracle.md:14` ("`inference` — endpoint and model for…" | pre-release | flows |  |
| 72 | "Relabel to v3.0." | pre-release | flows |  |
| 73 | "**E2.** `docs/connector-roundtrip.md`: "Captured from a live Gmail round-trip…" | pre-release | flows |  |
| 74 | "One of the two dates is wrong." | pre-release | flows |  |
| 75 | "**E3.** `RUNBOOK.md` Job 4: release-tag example says `v1.0.0`…" | pre-release | flows |  |
| 76 | "Cosmetic; bump to a 3.x example." | pre-release | flows |  |
| 77 | "These were checked claim-by-claim against code and hold:" | pre-release | flows |  |
| 78 | "**`PROTOCOL.md`**: message types and dispatch — `job`/`result` (§3),…" | pre-release | flows |  |
| 79 | "All four attest predicates documented (§9.2) match `build_attestations`." | pre-release | flows |  |
| 80 | "Crypto claims (HMAC-SHA-384, §8) match code." | pre-release | flows |  |
| 81 | "§15 rollout reads as a record of what…" | pre-release | flows |  |
| 82 | "The implementation note that the judge's **semantic** path…" | pre-release | flows |  |
| 83 | "**`docs/oracle-flag.md`**: accurate on the removed `--no-oracle` / `oracle_enabled`…" | pre-release | flows |  |
| 84 | "**`docs/verify-v31.md`**: correctly bannered historical." | pre-release | flows |  |
| 85 | "**`docs/configuring-oracle.md`**: every listed key verified in code (`max_result_view`,…" | pre-release | flows |  |
| 86 | "**`INSTALL.md`**: hot-reload key list matches `HOT_KEYS` (`poll_interval_sec`, `workers`,…" | pre-release | flows |  |
| 87 | "Ollama/model defaults correct (`llama3.2:3b`, Pi `llama3.2:1b`)." | pre-release | flows |  |
| 88 | "**`DOCKER.md`**: `PIGEON_*` env table matches `docker/entrypoint.sh` exactly, including…" | pre-release | flows |  |
| 89 | "**`README.md`**: `--oracle` flag-table row accurate; Setup model defaults…" | pre-release | flows |  |
| 90 | "**`SECURITY.md`, `CONTRIBUTING.md`, `AGENTS.md`**: no implementation claims found to…" | pre-release | flows |  |
| 91 | "**`ORACLE_DASHBOARD.md`**: clearly labeled "v4 Spec (draft) … Not…" | pre-release | flows |  |
| 92 | "**`docs/security-test-plan.md`**: marked "draft for execution"; no false implementation…" | pre-release | flows |  |
| 93 | "**`docs/handoff-local-si.md`**: accurate except the transport table (A1) and…" | pre-release | flows |  |
| 94 | "**A3** (`--local-test`/`--browser` not in argparse) — user-facing breakage;…" | pre-release | flows |  |
| 95 | "**A1/A2** (cut transports still documented) — actively misleading…" | pre-release | flows |  |
| 96 | "Note the working tree already deletes `transports.py`, which…" | pre-release | flows |  |
| 97 | "**B1/B2/B3** (shipped features labeled "not yet") — the…" | pre-release | flows |  |
| 98 | "**D1** (sender-address troubleshooting) — will misdirect real debugging." | pre-release | flows |  |
| 99 | "**C1/C2** (example config + inference sub-keys) — discoverability…" | pre-release | flows |  |
| 100 | "**D2/D3/E1/E2/E3** — polish." | pre-release | flows |  |
