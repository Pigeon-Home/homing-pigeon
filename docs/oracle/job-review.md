# Oracle job review (advisory)

The Oracle is always on. So it might as
well read the job before running it.

## What it is

`review_job()` inspects each verified job after the signature and
key-policy checks and before execution. It returns notes about
likely failures: things that will probably make the job fail or
behave unexpectedly. The notes are attached to the result as
`result["review"]`, so the failure-handling path sees what the
Oracle predicted alongside what actually happened.

The review is **advisory, never a gate**. The job runs regardless,
because the Oracle can be wrong. Policy ("should this run") stays
with the judge; review is correctness ("will this work").

## The two tiers

Two tiers, split by whether the check needs the script text:

- **Metadata tier** needs no content access: job shape, declared
  files, timeouts, interpreter form, shebang vs platform. It works
  even when job bodies are encrypted.
- **Content tier** reads the script text: known-failure patterns
  and static checks (dangling file references, operator-defined
  regexes). Under per-job encryption it needs the decrypt
  credential the runner already holds — no new man-in-the-middle.
  The Oracle reads what the runner legitimately decrypted.

## Authenticated opinion, not a new signature

The notes ride in the already-HMAC-signed result message, bound to
the `job_id`. The Oracle is an authenticated party with an opinion;
it does not need its own key for this. A dedicated Oracle signing
key is listed in docs/project/future.md, for when the opinion may need to travel
outside the result envelope (e.g., to the DRI playbook channel).

## Built-in checks

| id | tier | severity | what it catches |
|----|------|----------|-----------------|
| no_script_source | metadata | warn | neither `script` nor `script_url` |
| script_url_no_integrity | metadata | info | `script_url` without `script_sha384` |
| file_no_integrity | metadata | info | file without `sha384` |
| absolute_file_name | metadata | warn | absolute path (will be rejected) |
| interpreter_not_list | metadata | warn | interpreter not a list (will be rejected) |
| shebang_platform_mismatch | metadata | warn | `#!/bin/bash` on Windows, etc. |
| timeout_clamped | metadata | info | `timeout_sec` > 3600 (will be clamped) |
| dangling_file_ref | content | warn | script names a file not in `files[]` |

Operator patterns go in `review_patterns_extra` (see
`docs/archive/known-failures.md` for the format and the filing process).

## The learning loop

Every diagnosed recurring failure gets filed in
`docs/archive/known-failures.md` with its pattern. Filing alone
changes no matching: the reviewer matches new jobs only against
patterns supplied via `review_patterns_extra` in config — an
operator copies a filed pattern there to arm it. The Oracle gets smarter the way
an on-call engineer does: by writing down what broke.
