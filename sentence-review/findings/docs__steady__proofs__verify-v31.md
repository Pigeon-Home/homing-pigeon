# Findings — docs/steady/proofs/verify-v31.md

Source: docs/steady/proofs/verify-v31.md, reviewed at main cbb52068.
Sentence units: 120. Flagged: 1. Categories: pre-release 120, post-release 0.

Units 1-5 are the blockquote historical banner, recorded as extracted; the document is a historical runbook and says so.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "> Historical record." | pre-release | flows |  |
| 2 | "Written against `main` @ `1c03c72` during v3.1 >…" | pre-release | flows |  |
| 3 | "Do not run this runbook. > The `oracle_enabled`…" | pre-release | flows |  |
| 4 | "The > Oracle is unconditional." | pre-release | flows |  |
| 5 | "A check that fails because that flag is…" | pre-release | flows |  |
| 6 | "Status under test: `main` @ `1c03c72` (parent `09768ab`,…" | pre-release | flows |  |
| 7 | "This runbook checks the work that closed the…" | pre-release | flows |  |
| 8 | "It does not add features." | pre-release | flows |  |
| 9 | "It does not start the loopback dashboard." | pre-release | flows |  |
| 10 | "The piece under test is the runner an…" | pre-release | flows |  |
| 11 | "The suite never calls a live model and…" | pre-release | flows |  |
| 12 | "Python standard library only." | pre-release | flows |  |
| 13 | "Do not add a dependency to make a…" | pre-release | flows |  |
| 14 | "New runner code stays in `runner/runner.py`." | pre-release | flows |  |
| 15 | "This runbook should not need any." | pre-release | flows |  |
| 16 | "`oracle_enabled=false` must still return the v1 result." | pre-release | flows |  |
| 17 | "If a check shows otherwise, stop and revert…" | pre-release | flows |  |
| 18 | "Never write or run a test that executes…" | pre-release | flows |  |
| 19 | "Judgment checks use `kind=ping` with a `script` field,…" | pre-release | flows |  |
| 20 | "Ping does not run `script`." | pre-release | flows |  |
| 21 | "Do not call a real model." | pre-release | flows |  |
| 22 | "Openers in the tests are fakes." | pre-release | flows |  |
| 23 | "Use "SI" not "AI" if you edit docs." | pre-release | flows |  |
| 24 | "Light punctuation." | pre-release | flows |  |
| 25 | "No em dashes." | pre-release | flows |  |
| 26 | "Do not tag a release and do not…" | pre-release | flows |  |
| 27 | "Owner sign-off is still required for that." | pre-release | flows |  |
| 28 | "Do not expand `ORACLE_DASHBOARD.md`. v4 is out of…" | pre-release | flows |  |
| 29 | "Pass only if every item below is true…" | pre-release | flows |  |
| 30 | "`ask` is answered when endpoint and model are…" | pre-release | flows |  |
| 31 | "A non-loopback endpoint leaves `inference_config` as `None`, and…" | pre-release | flows |  |
| 32 | "A model reply that hits a secret pattern…" | pre-release | flows |  |
| 33 | "The secret text is not in the message." | pre-release | flows |  |
| 34 | "An `ask` spends 1 from the budget when…" | pre-release | flows |  |
| 35 | "A signed query against a known retained job…" | pre-release | flows |  |
| 36 | "An unknown job, an expired retained file, a…" | pre-release | flows |  |
| 37 | "`runner/install.py --additional-secret KEY_ID` writes a 256-bit value under…" | pre-release | flows |  |
| 38 | "One `poll_once` cycle can submit, request, offer, and…" | pre-release | flows |  |
| 39 | "`judge=enforce` blocks the denylist before `execute_job`. `judge=advisory` attaches…" | pre-release | flows |  |
| 40 | "None of these execute the denylist text." | pre-release | flows |  |
| 41 | "README roadmap calls v3.1 implemented. `docs/configuring-oracle.md` says the…" | pre-release | flows |  |
| 42 | "From the repo root:" | pre-release | flows |  |
| 43 | "Both commands must exit 0." | pre-release | flows |  |
| 44 | "The second command is the v3.1 slice." | pre-release | flows |  |
| 45 | "The first is the regression gate, including the…" | pre-release | flows |  |
| 46 | "`tests/test_v31_verify.py` is the extra coverage for branches the…" | pre-release | flows |  |
| 47 | "If that file fails, the feature is not…" | pre-release | flows |  |
| 48 | "Claim ; Where it is locked" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 49 | "Loopback gate, fail closed ; `InferenceGateTest.test_fail_closed_matrix`" | pre-release | flows |  |
| 50 | "Endpoint normalized, 127.0.0.2 accepted, redirect refused ; `InferenceGateTest.test_normalizes_safe_endpoint`,…" | pre-release | flows |  |
| 51 | "Constrained prompt, truncation, secret past the cap dropped…" | pre-release | flows |  |
| 52 | "Bearer token and empty pattern map still sanitize…" | pre-release | flows |  |
| 53 | "Transport failure is `inference_error`, not a mailed reply…" | pre-release | flows |  |
| 54 | "`ask` wired through the real `ask_model`, budget spent…" | pre-release | flows |  |
| 55 | "grep / tail / bad pattern / unknown…" | pre-release | flows |  |
| 56 | "attested and summary views do not return raw…" | pre-release | flows |  |
| 57 | "redacted view scrubs before the answer is returned…" | pre-release | flows |  |
| 58 | "retained path traversal, corrupt JSON, expiry ; `RetainedEdgeTest`" | pre-release | flows |  |
| 59 | "job then follow-up in one poll, ping script…" | pre-release | flows |  |
| 60 | "expired, rate limit, attested follow-up ; `QueryMailVerifyTest.test_expired_rate_limit_and_attested_view`" | pre-release | flows |  |
| 61 | "bad signature, stale time, bad type, traversal id,…" | pre-release | flows |  |
| 62 | "sanitization before the qresult is mailed ; `QueryMailVerifyTest.test_ask_sanitization_runs_before_the_email`" | pre-release | flows |  |
| 63 | "extra secret stored, not printed, bad id refused…" | pre-release | flows |  |
| 64 | "denylist, enforce, advisory ; `JudgmentDenylistTest`" | pre-release | flows |  |
| 65 | "judge off leaves the ping result alone ;…" | pre-release | flows |  |
| 66 | "board submit, exclusive offer, duplicate, bad signature, result…" | pre-release | flows |  |
| 67 | "oracle off rejects query and board, v1 stdout…" | pre-release | flows |  |
| 68 | "Confirm these if you are reading a failure…" | pre-release | flows |  |
| 69 | "Unknown `job_id`, unsafe `job_id`: qresult `rejected=unknown_job`, message marked…" | pre-release | flows |  |
| 70 | "Retained file present but `saved_at` older than `output_retention_days`:…" | pre-release | flows |  |
| 71 | "`max_queries_per_hour` exceeded: `rejected=rate_limit`." | pre-release | flows |  |
| 72 | "The bucket is the signing `key_id`, and the…" | pre-release | flows |  |
| 73 | "This happens before the budget is spent." | pre-release | flows |  |
| 74 | "A check that keyed the bucket on `query_id`…" | pre-release | flows |  |
| 75 | "That path is covered by `QueryMailVerifyTest.test_expired_rate_limit_and_attested_view`." | pre-release | flows |  |
| 76 | "`timeout_sec` of 0, or a missing timeout, means…" | pre-release | flows |  |
| 77 | "A negative or non-numeric timeout is refused." | pre-release | flows |  |
| 78 | "The same rule applies to `max_answer_chars` (0 means…" | pre-release | flows |  |
| 79 | "`output_retention_days` of 0, or a missing value, means…" | pre-release | flows |  |
| 80 | "A negative value disables expiry. *(Audit note, 2026-10-18:…" | pre-release | flows |  |
| 81 | "The code has since changed — since 3.7.37…" | pre-release | flows |  |
| 82 | "Bad signature: IMAP message marked seen, no qresult,…" | pre-release | flows |  |
| 83 | "`issued_at` outside the window: no qresult, seen-set key…" | pre-release | flows |  |
| 84 | "`type` other than `query`: `rejected=unsupported`." | pre-release | flows |  |
| 85 | "Duplicate `query_id` in the seen set: no second…" | pre-release | flows |  |
| 86 | "View `attested` or `summary`: grep and tail return…" | pre-release | flows |  |
| 87 | "Raw lines are not in the mail." | pre-release | flows |  |
| 88 | "`oracle_enabled=false` on a query: `rejected=unsupported`." | pre-release | flows |  |
| 89 | "A ping job in the same config returns…" | pre-release | flows |  |
| 90 | "`oracle_enabled=false` on board mail: no reply, no `board.json`." | pre-release | flows |  |
| 91 | "Second `task_request` while the only open task is…" | pre-release | flows |  |
| 92 | "`task_result` for an id that was never submitted:…" | pre-release | flows |  |
| 93 | "`--additional-secret` with a key id outside `[A-Za-z0-9._-]{1,64}`: exit…" | pre-release | flows |  |
| 94 | "Non-loopback, missing model, negative `max_answer_chars`, negative `timeout_sec`, or…" | pre-release | flows |  |
| 95 | "Zero for those two fields means unset, not…" | pre-release | flows |  |
| 96 | "Run these from the repo root after the…" | pre-release | flows |  |
| 97 | "The dashboard diff must be empty." | pre-release | flows |  |
| 98 | "README must say the ask op is implemented,…" | pre-release | flows |  |
| 99 | "`docs/configuring-oracle.md` must say the same about loopback." | pre-release | flows |  |
| 100 | "Do not rewrite the rest of that file." | pre-release | flows |  |
| 101 | "Do not start Ollama." | pre-release | flows |  |
| 102 | "Do not point `inference.endpoint` at a host other…" | pre-release | flows |  |
| 103 | "A manual probe, if the owner wants one…" | pre-release | flows |  |
| 104 | "That probe is not part of this runbook…" | pre-release | flows |  |
| 105 | "A test would execute a denylisted command." | pre-release | flows |  |
| 106 | "Delete it." | pre-release | flows |  |
| 107 | "Do not "just run it once"." | pre-release | flows |  |
| 108 | "`oracle_enabled=false` changes the v1 result." | pre-release | flows |  |
| 109 | "Revert." | pre-release | flows |  |
| 110 | "A change adds `http.server`, a GUI, or dashboard…" | pre-release | flows |  |
| 111 | "Revert." | pre-release | flows |  |
| 112 | "That is v4." | pre-release | flows |  |
| 113 | "The suite only passes when a real model…" | pre-release | flows |  |
| 114 | "The fake opener is the contract." | pre-release | flows |  |
| 115 | "Someone asks for a release tag." | pre-release | flows |  |
| 116 | "Stop." | pre-release | flows |  |
| 117 | "Owner sign-off is not part of this verification." | pre-release | flows |  |
| 118 | "A pass is: both unittest commands exit 0,…" | pre-release | flows |  |
| 119 | "Record the commit you ran against." | pre-release | flows |  |
| 120 | "Do not force-push `main` to rewrite the landing…" | pre-release | flows |  |
