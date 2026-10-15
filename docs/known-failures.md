# Known failures

The Oracle's pre-execution reviewer matches incoming jobs against
these patterns. Each entry is a failure that actually happened,
diagnosed once, filed here so it happens less. When you diagnose a
new recurring failure, add it: symptom, cause, fix, and the pattern
the reviewer should match.

Format for reviewer patterns (`review_patterns_extra` in config):

```json
{"id": "kf-00X", "pattern": "<regex over the script text>",
 "note": "<what the Oracle tells the failure handler>",
 "severity": "info"}
```

Severity is `info` or `warn`. Patterns are advisory: the job still
runs.

---

## KF-001 — PowerShell bare script (fixed in runner v1.3.1)

- **Symptom:** every PowerShell job failed immediately on Windows.
- **Cause:** `powershell -File` refuses a script file without a `.ps1`
  extension; the runner staged it as a bare `script`.
- **Fix:** the runner now names the staged script for the
  interpreter (`script.ps1` for PowerShell). See `script_filename()`.
- **Reviewer:** built in — no live pattern needed. Kept here as the
  format example and a reminder that staging bugs are forever.

## KF-002 — timeout silently clamped

- **Symptom:** long jobs died at exactly 3600s with no explanation.
- **Cause:** the runner clamps `timeout_sec` to a maximum of 3600.
  A job asking for 7200 gets 3600 without being told.
- **Fix:** ask for what you need up to 3600, or split the job.
- **Reviewer:** built in (`timeout_clamped`, info).

## KF-003 — unverified downloads

- **Symptom:** a job fetched a `script_url` or file that had changed
  upstream; the failure looked like a code bug.
- **Cause:** no `sha384` on the download, so there was no integrity
  check to catch the change.
- **Fix:** pin `script_sha384` / file `sha384` on anything you
  download more than once.
- **Reviewer:** built in (`script_url_no_integrity`,
  `file_no_integrity`, info).

## KF-004 — dangling file references

- **Symptom:** `FileNotFoundError` a few seconds into the run.
- **Cause:** the script opened a file that was never listed in
  `files[]`, so it was never staged into the work dir.
- **Fix:** list every input file in `files[]`.
- **Reviewer:** built in (`dangling_file_ref`, warn) — matches
  quoted filename-like literals against the staged names.

## KF-005 — absolute file names rejected

- **Symptom:** job rejected before running: "unsafe file name".
- **Cause:** `files[]` entries must be relative; absolute paths can
  never stage inside the work dir.
- **Fix:** use relative names.
- **Reviewer:** built in (`absolute_file_name`, warn).

---

## Adding a pattern

1. Diagnose the failure and confirm it recurs.
2. Add a section above (next KF number), with symptom, cause, fix.
3. If it is script-text-shaped, add a `review_patterns_extra` entry
   to your config with the same id. If it is job-shape-shaped,
   propose it as a built-in check.
