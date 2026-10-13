# Homing Pigeon Protocol v1

Email-based control protocol between a cloud SI and a self-hosted
runner. Email carries only signed control metadata; large
payloads travel as cloud-hosted file URLs that the runner downloads.

## 1. Actors

- **Cloud SI:** composes signed job emails, uploads large inputs to
  file hosting, reads signed result emails.
- **Runner (Linux/macOS/FreeBSD/Windows):** polls a dedicated mailbox,
  verifies and executes jobs, emails back signed results. Implemented in
  Python 3.9+ using only the standard library.

## 2. Transport

- One dedicated mailbox (Gmail recommended). Both directions use it:
  The cloud SI sends jobs *to* it; the runner reads them and sends results back
  to the same address.
- Runner access: IMAP (read, port 993) + SMTP (send, port 587) with an
  app password. Gmail requires 2-Step Verification before an app
  password can be created.
- The runner reads the Gmail username + app password from `config.json`
  **in plaintext** — the user's explicit choice (dedicated throwaway
  account, fresh machine, nothing personal). They are never written to
  the log or into any email, but they ARE on disk: do not use this setup
  with an account you care about. The runner exits with an error if
  `mailbox_user` or `mailbox_password` is missing from config.
- Subject lines (exact prefixes):
  - Job: `[HOMING-PIGEON] job <job_id>`
  - Result: `[HOMING-PIGEON] result <job_id>`
  - `<job_id>` is a UUID (no spaces).

## 3. Message format

- Body is UTF-8 plain text containing a single JSON object.
- Every message ends with a `sig` field holding a hex HMAC-SHA-384
  signature (see section 4).

### 3.1 Job

```json
{
  "v": 1,
  "type": "job",
  "job_id": "3f9a1c2e-...-uuid",
  "issued_at": "2026-10-13T12:00:00Z",
  "kind": "exec",
  "script": "<inline script, optional>",
  "script_url": "<https url, optional>",
  "script_sha384": "<hex, optional>",
  "interpreter": ["<executable + args, optional>"],
  "files": [
    {"name": "input.csv", "url": "https://...", "sha384": "<hex, optional>"}
  ],
  "args": ["--flag", "value"],
  "env": {"MY_VAR": "value"},
  "timeout_sec": 300,
  "sig": "<hex hmac>"
}
```

- `kind`: `exec` or `ping`. A `ping` job carries no script; the runner
  answers with a `pong` result (health check).
- For `exec`, exactly one of `script` / `script_url` is required.
  `script_url` wins if both are present.
- `timeout_sec`: default 300, maximum 3600.
- `interpreter`: optional list whose first element is the executable and
  the rest are its arguments, e.g. `["pwsh", "-File"]` or `["bash"]`. The
  script is written to `<workdir>/script` and run as
  `<interpreter...> <workdir>/script <args...>`. If absent, the runner's
  `default_interpreter` config applies, else the platform default:
  PowerShell (`powershell -NoProfile -NonInteractive -ExecutionPolicy
  Bypass -File`) on Windows, `sh` elsewhere.
- Unknown fields must be ignored (forward compatibility).

### 3.2 Result

```json
{
  "v": 1,
  "type": "result",
  "job_id": "3f9a1c2e-...-uuid",
  "kind": "exec",
  "completed_at": "2026-10-13T12:01:23Z",
  "exit_code": 0,
  "timed_out": false,
  "stdout": "...",
  "stderr": "...",
  "stdout_truncated": false,
  "stderr_truncated": false,
  "duration_sec": 12.345,
  "runner": "DESKTOP-ABC123",
  "sig": "<hex hmac>"
}
```

- `timed_out: true` implies the process tree was killed; `exit_code` is -1.
- `exit_code` -2 means the job was rejected before execution (validation
  failure: unknown kind, SHA384 mismatch, unsafe file name...); details in
  `stderr`. Rejected jobs are marked seen and do not retry.
- `stdout`/`stderr` are truncated at a configurable byte limit
  (default 100_000); the `*_truncated` flags say so.

## 4. Signatures (no canonicalization needed)

Appending the signature last avoids cross-language JSON
canonicalization entirely:

1. Serialize the payload as a JSON object **without** `sig`
   (any key order, compact or pretty — sender's choice).
2. Normalize line endings to LF (`\r\n` → `\n`, `\r` → `\n`).
3. `sig = HEX(HMAC_SHA384(secret, normalized_payload))`.
4. Body = payload with the trailing `}` replaced by
   `,"sig":"<sig>"}`.

Verification:

1. Normalize line endings to LF.
2. Find the **last** occurrence of `,"sig":"`. Everything after it must
   match `^[0-9a-f]{96}"\}$`; otherwise reject.
3. `raw = <everything before the marker> + "}"`.
4. Recompute `HEX(HMAC_SHA384(secret, raw))` and compare with the
   presented signature using a constant-time comparison.

The shared secret is the Gmail app password string itself (user's explicit
choice). Both sides use its UTF-8 bytes directly as the HMAC-SHA-384 key.
The user gives the same string to the cloud side when they want jobs sent.
It never travels in email; only job signatures do.

## 5. Runner verification (all must pass, in order)

1. **Hard rule:** the `From` address must exactly match the account the
   runner is logged into (or the explicit `allowed_sender` override,
   which defaults to the login account). Anything else is rejected
   before signature verification. The runner never obeys a third party,
   signed or not.
2. Subject matches `[HOMING-PIGEON] job <job_id>`; body signature valid.
3. `v == 1` and `type == "job"`.
4. `issued_at` parses and is within `max_job_age_sec` (default 3600) of
   the runner's clock (replay / stale protection).
5. `job_id` not in the seen-set (replay protection).

Failures are logged, the mail is marked seen, and the job is **never**
executed. Delivery is at-least-once: a job whose result email fails to
send stays unseen and will be retried (re-executed) on the next cycle.

## 6. Execution semantics

- Working directory: `<base_dir>/work/<job_id>/`, created fresh per job.
- `files[]` are downloaded over HTTPS into the work dir. `name` must
  not escape the work dir (path traversal is rejected). `sha384` is
  verified when present.
- The script runs as `<interpreter...> script <args...>` (see section
  3.1) with stdout/stderr captured, `env` merged into the process
  environment, and the work dir as cwd.
- On timeout the whole process tree is killed (POSIX process group;
  `taskkill /T` on Windows).

## 7. Security model

- The runner host is a **full-trust execution environment**: anyone who
  can produce a valid signed job email owns the box.
- This deployment deliberately stores the Gmail app password in
  **plaintext** in config.json (user's explicit choice: dedicated
  throwaway account on a fresh machine with nothing personal). Anyone
  holding the password gets both Gmail access and the ability to sign
  jobs. Do not use this setup with an account you care about.
- Use a dedicated mailbox, never a personal inbox. Use an app password,
  never the account password.
- Recommended deployment: run the runner inside a Linux VM on the
  target host. VM snapshots give instant rollback, and the guest
  boundary contains everything a signed job can reach.
- IMAP/SMTP over TLS (993/587). File downloads over HTTPS only.
- Hardening roadmap (v2): encrypted credentials at rest, ack messages,
  per-job encryption, result file upload for large outputs,
  privacy-preserving result policies (specified in the v2 proposal below).

## 8. Cryptography — Suite B alignment (384-bit tier)

All primitives are in the NSA Suite B set at the 384-bit tier (now
transitioned to CNSA; the symmetric/hash primitives carry over unchanged):

- **Message authentication:** HMAC-SHA-384, keyed with the shared secret
  (Suite B integrity primitive, 384-bit tier).
- **Hashing:** SHA-384, used for file/script integrity checks (Suite B,
  384-bit tier).
- **Transport:** TLS 1.2+ enforced for IMAP, SMTP, and file downloads
  (Suite B requires TLS 1.2 with Suite B cipher suites).
- **Future payload encryption:** AES-256 (GCM where available) is the
  designated cipher if confidentiality beyond TLS is ever needed. No
  payload encryption in v1.

v1 does not encrypt payloads: confidentiality in transit comes from TLS;
authenticity and integrity come from HMAC-SHA-384.

---

# Protocol v2 (proposal): privacy-preserving results

**Paradigm: the runner as an oracle.** In v1 the SI receives full job
output (stdout/stderr) by email. v2 inverts this: the runner keeps the
output on its own (trusted) disk and answers only the questions the
result policy allows, with HMAC-signed attestations. The SI learns
predicates about the output — never the output itself unless the policy
permits it. This is the interactive-proof / functional-encryption shape
applied at the trust boundary, without any zero-knowledge proving
machinery: the runner is trusted (it's the user's own machine), so
egress filtering plus signed commitments gives the privacy property.

## 9. Result policies

The job gains an optional `result_policy` object:

```json
"result_policy": {
  "view": "summary",
  "redact_patterns": ["aws_key", "private_key", "bearer_token"],
  "query": true
}
```

- `view`: one of `full` (v1 behavior), `redacted`, `summary`, `attested`.
  Default: `full` (backward compatible).
- `redact_patterns`: named secret families to scrub in `redacted` view
  (runner ships a built-in set; config may extend it).
- `query`: whether the SI may send follow-up `query` messages against
  this job's retained output. Default `false`.

**The ceiling is set by the runner owner, not the SI.** `config.json`
gains `max_result_view` (default `full`). The effective view is the
*narrower* of the job's request and the runner's ceiling — a job can
never widen disclosure beyond what the machine's owner allows. This is
the load-bearing privacy property: the SI composes the job, but the
user's box decides what leaves it.

### 9.1 View definitions

- `full`: the v1 result message, unchanged.
- `redacted`: full result with every `redact_patterns` match replaced by
  `[REDACTED:<family>]`. The message lists which families were applied.
- `summary`: no raw output. Contains `exit_code`, `timed_out`,
  `duration_sec`, `stdout_bytes`, `stderr_bytes`, `result_class`
  (`success`/`failure`/`timeout`/`rejected`), and `output_digest`
  (SHA-384 of the complete untruncated stdout+stderr).
- `attested`: `summary` fields plus an `attestations` array — and nothing
  else. No output bytes cross the boundary at all.

### 9.2 Attestations

```json
"attestations": [
  {"predicate": "exit_zero", "value": true},
  {"predicate": "no_secrets", "value": true,
   "patterns_sha384": "<hex of the pattern set used>"},
  {"predicate": "output_digest", "value": "<hex sha384 of full output>"}
]
```

Built-in predicates (extensible by runner config):

- `exit_zero`: `exit_code == 0`.
- `no_secrets`: the retained output was scanned against the runner's
  secret patterns and none matched. `patterns_sha384` binds *which*
  pattern set ran, so the SI knows what "secrets" meant.
- `output_digest`: SHA-384 of the full output. This is a **commitment**:
  the SI can't see the output, but the runner is bound to it — if a
  wider view is ever granted later, the SI can verify the digest.

Each attestation is covered by the message HMAC (section 4), so a
predicate answer carries the same authenticity as v1 results.

## 10. The query loop

When `query: true`, the SI may interrogate retained output with signed
messages. Subject lines:

- Query: `[HOMING-PIGEON] query <query_id>`
- Query result: `[HOMING-PIGEON] qresult <query_id>`

```json
{
  "v": 2,
  "type": "query",
  "query_id": "9d8b7c6a-...-uuid",
  "job_id": "3f9a1c2e-...-uuid",
  "op": "grep",
  "pattern": "ERROR",
  "max_matches": 20,
  "sig": "<hex hmac>"
}
```

- `op`: `grep` (regex over retained stdout+stderr, returns matching
  lines up to `max_matches`), `tail` (`lines`: last N lines), or
  `attest` (`predicate`: evaluate a named predicate now).
- Every query passes the section-5 verification (From hard rule,
  signature, freshness, seen-set on `query_id`).
- **Policy binds the answers:** a query can never return more than the
  job's effective view allows. Under `attested`, `grep`/`tail` are
  rejected — only `attest` ops are answered. Under `redacted`, returned
  lines are scrubbed first.
- Outputs are retained per `output_retention_days` (runner config,
  default 7); queries against expired or unknown `job_id`s are rejected
  and marked seen.

## 11. v2 security properties

- **Non-escalation:** neither the job's `result_policy` nor any query
  can widen disclosure past the runner owner's `max_result_view`.
- **Commitment binding:** `output_digest` in every non-`full` view ties
  the hidden output to the signed claims about it.
- **Same transport trust as v1:** queries are HMAC-signed emails subject
  to the From hard rule; a third party can neither ask nor answer.
- **Data lifetime:** retained outputs age out per config; nothing about
  v2 weakens the v1 rule that the runner host itself is fully trusted —
  v2 protects data *from the SI*, not from the machine's owner.

*Status: proposal. v1 remains the implemented protocol; v2 message types
(`"v": 2`, `query`/`qresult`) are reserved.*
