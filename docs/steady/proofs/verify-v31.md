# Verification runbook: v3.1 non-GUI protocol

> Historical record. Written against `main` @ `1c03c72` during v3.1
> verification, before the v3.1.0 tag. Do not run this runbook.
> The `oracle_enabled` flag it tells you to test was removed. The
> Oracle is unconditional. A check that fails because that flag is
> gone is not a regression.

Status under test: `main` @ `1c03c72` (parent `09768ab`, based on `e3cebb9`).

This runbook checks the work that closed the non-GUI gaps. It does not add features. It does not start the loopback dashboard.

The piece under test is the runner an owner already has: a local model the owner runs themselves, plus query follow-ups, extra secrets, the board, and the judgment denylist. The suite never calls a live model and never executes a denylisted command.

## 0. Ground rules

- Python standard library only. Do not add a dependency to make a test pass.
- New runner code stays in `runner/runner.py`. This runbook should not need any.
- `oracle_enabled=false` must still return the v1 result. If a check shows otherwise, stop and revert the offending change.
- Never write or run a test that executes a denylisted command. Judgment checks use `kind=ping` with a `script` field, or call `judge_job` directly. Ping does not run `script`.
- Do not call a real model. Openers in the tests are fakes.
- Use "SI" not "AI" if you edit docs. Light punctuation. No em dashes.
- Do not tag a release and do not merge to a release branch. Owner sign-off is still required for that.
- Do not expand `ORACLE_DASHBOARD.md`. v4 is out of scope.

## 1. What "done" means

Pass only if every item below is true on the commit you are checking.

1. `ask` is answered when endpoint and model are set and the host is loopback.
2. A non-loopback endpoint leaves `inference_config` as `None`, and `ask` returns `inference_unconfigured`.
3. A model reply that hits a secret pattern becomes `{"rejected": "sanitization"}` before any qresult is mailed. The secret text is not in the message.
4. An `ask` spends 1 from the budget when it is answered and when it is rejected.
5. A signed query against a known retained job returns a signed qresult for grep, tail, and attest, and persists `spent`.
6. An unknown job, an expired retained file, a bad signature, a stale `issued_at`, a rate limit, and an attested view each fail closed in the way section 4 describes.
7. `runner/install.py --additional-secret KEY_ID` writes a 256-bit value under `additional_secrets` and does not print it.
8. One `poll_once` cycle can submit, request, offer, and a second request gets an empty offer. `oracle_enabled=false` rejects board mail.
9. `judge=enforce` blocks the denylist before `execute_job`. `judge=advisory` attaches a verdict and still runs a ping. `judge=off` does not attach a verdict. None of these execute the denylist text.
10. README roadmap calls v3.1 implemented. `docs/configuring-oracle.md` says the endpoint must be loopback or the op stays off.

## 2. Automated gate

From the repo root:

```
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_v31_verify tests.test_followups tests.test_board -v
```

Both commands must exit 0. The second command is the v3.1 slice. The first is the regression gate, including the v1 path with the oracle off.

`tests/test_v31_verify.py` is the extra coverage for branches the first landing did not lock. If that file fails, the feature is not verified, even if the older tests pass.

## 3. Map from the implementation runbook to tests

| Claim | Where it is locked |
|---|---|
| Loopback gate, fail closed | `InferenceGateTest.test_fail_closed_matrix` |
| Endpoint normalized, 127.0.0.2 accepted, redirect refused | `InferenceGateTest.test_normalizes_safe_endpoint`, `test_redirect_is_refused` |
| Constrained prompt, truncation, secret past the cap dropped | `InferenceGateTest.test_success_truncates_and_posts_constrained_prompt`, `test_secret_past_the_cap_is_dropped` |
| Bearer token and empty pattern map still sanitize | `InferenceGateTest.test_bearer_and_builtin_fallback_reject` |
| Transport failure is `inference_error`, not a mailed reply | `InferenceGateTest.test_non_loopback_and_transport_errors` |
| `ask` wired through the real `ask_model`, budget spent on reject | `AnswerQueryBranchTest.test_ask_uses_real_ask_model_and_spends_on_reject` and `InferenceTest.test_ask_spends_budget_when_rejected` |
| grep / tail / bad pattern / unknown op / mid-list budget | `AnswerQueryBranchTest` |
| attested and summary views do not return raw lines | `AnswerQueryBranchTest.test_grep_tail_policy_redaction_and_budget` |
| redacted view scrubs before the answer is returned | same |
| retained path traversal, corrupt JSON, expiry | `RetainedEdgeTest` |
| job then follow-up in one poll, ping script not executed | `QueryMailVerifyTest.test_job_then_followup_and_script_is_not_run` |
| expired, rate limit, attested follow-up | `QueryMailVerifyTest.test_expired_rate_limit_and_attested_view` |
| bad signature, stale time, bad type, traversal id, duplicate query | `QueryMailVerifyTest.test_rejects_without_leaking_and_duplicate_is_silent` |
| sanitization before the qresult is mailed | `QueryMailVerifyTest.test_ask_sanitization_runs_before_the_email` |
| extra secret stored, not printed, bad id refused | `InstallVerifyTest` and `AdditionalSecretTest` |
| denylist, enforce, advisory | `JudgmentDenylistTest` |
| judge off leaves the ping result alone | `JudgeOffPathTest` |
| board submit, exclusive offer, duplicate, bad signature, result before claim | `BoardVerifyTest` and `BoardE2ETest` |
| oracle off rejects query and board, v1 stdout unchanged | `QueryFollowupTest.test_oracle_disabled_leaves_v1_result`, `test_oracle_disabled_rejects_query`, `BoardE2ETest.test_oracle_disabled_rejects_board` |

## 4. Expected fail-closed results

Confirm these if you are reading a failure rather than trusting the test name.

- Unknown `job_id`, unsafe `job_id`: qresult `rejected=unknown_job`, message marked seen.
- Retained file present but `saved_at` older than `output_retention_days`: `rejected=expired`. `spent` does not change.
- `max_queries_per_hour` exceeded: `rejected=rate_limit`. The bucket is the signing `key_id`, and the empty id (the default secret) shares one bucket across query ids. This happens before the budget is spent. A check that keyed the bucket on `query_id` whenever `key_id` was `""` did not cap the common install. That path is covered by `QueryMailVerifyTest.test_expired_rate_limit_and_attested_view`.
- `timeout_sec` of 0, or a missing timeout, means unset and becomes 180. A negative or non-numeric timeout is refused. The same rule applies to `max_answer_chars` (0 means the default 2000, a negative value is refused).
- `output_retention_days` of 0, or a missing value, means the default 7, so an old retained file is `rejected=expired`. A negative value disables expiry. *(Audit note, 2026-10-18: this was the behavior when this document was written. The code has since changed — since 3.7.37 an explicit 0 means no expiry; a missing value still means the default 7.)*
- Bad signature: IMAP message marked seen, no qresult, seen-set key not written.
- `issued_at` outside the window: no qresult, seen-set key written.
- `type` other than `query`: `rejected=unsupported`.
- Duplicate `query_id` in the seen set: no second qresult, budget not spent again.
- View `attested` or `summary`: grep and tail return `rejected=policy` and still spend 1. Raw lines are not in the mail.
- `oracle_enabled=false` on a query: `rejected=unsupported`. A ping job in the same config returns stdout `pong` and does not write `retained/`.
- `oracle_enabled=false` on board mail: no reply, no `board.json`.
- Second `task_request` while the only open task is claimed by someone else: `task_offer` with `empty=true`.
- `task_result` for an id that was never submitted: `status=not_found`, no board file created.
- `--additional-secret` with a key id outside `[A-Za-z0-9._-]{1,64}`: exit 2, config bytes unchanged, value never printed.
- Non-loopback, missing model, negative `max_answer_chars`, negative `timeout_sec`, or a non-http(s) scheme: `inference_config` is `None`. Zero for those two fields means unset, not refused.

## 5. Checks that are not unit tests

Run these from the repo root after the suite is green.

```
git diff e3cebb9..HEAD -- ORACLE_DASHBOARD.md
git grep -n "v3.1" README.md docs/configuring-oracle.md
```

- The dashboard diff must be empty.
- README must say the ask op is implemented, and that the endpoint must be loopback or the op stays off.
- `docs/configuring-oracle.md` must say the same about loopback. Do not rewrite the rest of that file.

Do not start Ollama. Do not point `inference.endpoint` at a host other than loopback and expect a live answer. A manual probe, if the owner wants one later, is a loopback server plus one signed `ask` query. That probe is not part of this runbook and must not be required for a pass.

## 6. Stop conditions

- A test would execute a denylisted command. Delete it. Do not "just run it once".
- `oracle_enabled=false` changes the v1 result. Revert.
- A change adds `http.server`, a GUI, or dashboard work. Revert. That is v4.
- The suite only passes when a real model is reachable. The fake opener is the contract.
- Someone asks for a release tag. Stop. Owner sign-off is not part of this verification.

## 7. Recording a pass

A pass is: both unittest commands exit 0, the dashboard diff is empty, and the two doc lines match section 5. Record the commit you ran against. Do not force-push `main` to rewrite the landing commits.
