# Temp reaping: the per-job workspace leak — suppositions, measurements, fix record

The Germany rig repair of 2026-11-06 (recorded in the campaign
record outside this tree) measured the damage first-hand:
`C:\Windows\Temp` held 134.8 GB across 1,144,525 files on a box
whose every Python process runs as SYSTEM (so TEMP is the
system temp). The contents named three creators: loose Python
`tmp*` tempfile artifacts, `_MEI*` PyInstaller extraction dirs,
and per-job runner workspaces (`hp-jf-*`, `hp-joff-*`,
`hp-adv-*`, each holding work/state/sent subtrees). Accumulation
ran at roughly 27 GB/day at full tilt until the disk hit 99.1%
used and wedged the box's services. The rig was repaired by hand
and a daily age-based cleanup task was installed there as a
guard. This record is the product fix: the runner and its job
layer reap what they create, so no deployment needs the guard.

## Leak sites, found first-hand in the code (2026-11-06)

1. `runner/ops/exec.py`, `execute_job`: the per-job workspace
   `base_dir/work/<job_id>` is created at the top of the
   function and removed on exactly two paths — the two
   workspace-integrity sweep violations. Every other exit
   leaves it: the success return (staged files, the script,
   collected outputs, change staging all stay), the `ping`
   early return, every `JobRejected` raised after creation
   (unknown kind, file-shape errors, staging failures, SHA384
   mismatches, a bad interpreter, a missing script, args/env
   validation, an interpreter that cannot start), and the
   `RuntimeError` download-failure paths. The only mitigation
   is at the start of a later attempt with the SAME job_id,
   which removes the previous attempt's directory; distinct
   job_ids accumulate forever, and a refused job is never
   retried, so its workspace is permanent.
2. Nothing reaps `base_dir/work/` orphans: there is no
   `shutil.rmtree` anywhere in `runner/runner.py`, and
   `runner/ops/main.py` only creates `work/` at startup. A
   workspace left by a crash, a kill mid-job, or an older
   version stays until the disk objects.
3. Test harnesses whose temp bases are the exact prefixes the
   rig weighed (the suite runs as a service on the campaign
   rigs, so its temp use is service temp use):
   `runner/tests/test_job_fuzz.py` — `ReadLiveTest` (hp-jf-),
   `ReadLiveCampaignLegsTest` (hp-jf-legs-) and `MainTest`
   (hp-jf-main-) create their base with `tempfile.mkdtemp` in
   `setUp` and never remove it (the file's fourth such class,
   `ScanRetainedEdgesTest`, does remove its own);
   `runner/tests/test_v31_verify.py` — `JudgeOffPathTest`
   (hp-joff-) creates a local temp base and never removes it;
   `runner/tests/test_protocol_and_edges.py` —
   `AdversarialTests` (hp-adv-) the same.
4. `runner/tests/test_canary_watch.py` (19 sites) and
   `runner/tests/test_graceful_failure.py` (87 sites) create
   default-prefix `tempfile.mkdtemp()` directories in test
   methods and never remove them — the suite's contribution
   to the loose `tmp*` population. A scan of the suite finds
   the same omission in further files; they are counted in
   the conclusions below and left as a named follow-on,
   because this change fixes the sites the rig evidence
   names plus the two uniform-pattern files above.
5. `runner/tools/first_ping.py`: the bench loop creates one
   `hp-first-ping-` temp base per measured run and never
   removes it (the loop's `finally` only restores the log
   function).

Examined and NOT leaks, with the evidence:

- `runner/hosting/inventory.py` and `runner/hosting/billing.py`:
  `mkstemp` in the target folder, `os.replace` on success,
  `os.unlink` on any exception. Clean.
- `runner/ops/sensors.py`: the `hp-yara-` rules file is
  removed in a `finally`. Clean.
- `runner/tools/rig_bank.py`: both temp trees are removed in
  a `finally`, with a comment naming this exact failure
  ("fills the rig's disk a timer tick at a time"). Clean —
  and the precedent idiom for this fix.
- `runner/tools/fetch_upstream.py`, `runner/tools/soak.py`
  (its `main`), `runner/tools/upgrade_proof.py`,
  `runner/tools/regression_guard.py`,
  `runner/tools/regression_pass.py`: temp trees removed on
  the way out. Clean.
- `runner/ops/install.py`: downloads land at fixed names in
  the temp dir (one file per package, overwritten next run)
  and the backup dir defaults there because backups are meant
  to persist. Bounded and named, not a per-job leak.
- `runner/cloud/send_job.py` and `runner/cloud/send_dtls.py`:
  no temp creation at all.
- `_MEI*` PyInstaller dirs: created by the bootloader, not by
  runner code, and removed by it on a clean exit; a killed
  process leaves one. They are NOT swept by this fix: the
  pattern is the packager's, not the runner's, and a live
  sibling instance's extraction dir is indistinguishable from
  an orphan by name — an age-based sweep at startup could
  remove the extraction of an instance that has been running
  longer than the age bound. The rig-side daily task remains
  the guard for these.
- A job script's own temp use (a job that creates temp files
  and leaves them) is the job's, not the runner's; the runner
  reaps the workspace it owns, and a job's temp files inside
  its workspace go with it.

## Suppositions, written before any measurement (2026-11-06)

The code reading above is the investigation; the behavioral
claims below are stated before any probe is run. The probes
are small scripts driving `execute_job` and the poll loop
against a scratch base, counting what is left under `work/`
and in the temp dir. The probes are the arbiter.

- S1. One successful exec job leaves exactly 1 directory
  under `base_dir/work/` after `execute_job` returns.
- S2. A job refused after its workspace is created (a SHA384
  mismatch on an inline file) and a `ping` each leave exactly
  1 directory as well — no exit path but the two integrity
  sweeps reaps.
- S3. Two jobs with distinct job_ids leave 2 directories:
  accumulation is per job, unbounded, and nothing in a
  runner restart removes them.
- S4. Running one test from each harness named in site 3
  leaves 1 new temp directory per test under the process
  temp dir, matching its prefix.
- S5. After the fix, the same probes show 0 directories left
  by finished jobs on every path (success, refusal, failure,
  ping); a planted orphan in `work/` older than the retention
  age is reaped by the startup sweep while a fresh directory,
  a foreign-named directory, a plain file and a symlink of
  any age are all left untouched; and a value of 0 for the
  retention setting turns the sweep off entirely.

## The fix shape (decided before implementation)

- `execute_job` reaps its workspace on every path out, via a
  `finally` around everything after creation. Remediation is
  unaffected by construction: quarantine MOVES the workspace
  out before the result returns, so the reap of a seized job
  finds nothing at the path and is a no-op, and the seized
  copy stays under the quarantine root under its own bounds.
  The delivery layer's kept refused result
  (`work/<job_id>/result.json`, written after execution when
  a delivery is refused) recreates the folder holding just
  that file; the startup sweep ages it out like any orphan.
- A bounded orphan sweep runs once at runner startup, after
  `work/` is created. Domain: the direct children of
  `base_dir/work/` only. A child is reaped only when it is a
  real directory (never a symlink or reparse point), its name
  matches the runner's own safe job_id shape
  (`runner/runner.py`'s `_SAFE_JOB_ID`, 1–128 chars of
  `[A-Za-z0-9._-]`, not `.` or `..`), and its mtime is older
  than the retention age. At most 512 directories are reaped
  per sweep. A reap failure is logged and never stops
  startup.
- The retention age is the config key `work_retention_sec`:
  default 604800 (7 days — a job runs at most 3600 seconds,
  so a week-old workspace is certainly orphaned, and a kept
  refused result gets a week of operator visibility). 0
  disables the sweep. A present-but-unusable value reads as
  the default and is named in a startup warning line, per
  the present-but-invalid-config rule (this setting changes
  neither who can reach the box, nor what it executes, nor
  what it protects, so it reads as its default rather than
  refusing to start). The key and its default are stated in
  `runner/config.example.json` beside the other retention
  keys. No CLI flag: startup flags are reserved for
  acceptance posture (the cleartext switch is the example);
  retention is ordinary configuration.
- The harnesses named in sites 3–5 gain the cleanup they
  were missing (`tearDown`/`addCleanup` removal of the temp
  base they created; the first_ping bench removes each run's
  base in a `finally`).

## Measurements

Probes run 2026-11-06 against the tree at `d799a6c9`, before any
fix, with the workspace disk as TMPDIR:

- S1 CONFIRMED. One successful exec job
  (`print('hi')`, interpreter the local Python) returned
  exit 0 and left exactly 1 directory under
  `base_dir/work/`: `probe-ok-1`, holding `script.py`.
- S2 CONFIRMED. A `ping` left its (empty) directory, and a
  job refused for a SHA384 mismatch on an inline file left
  its directory holding the staged `a.txt`. After the three
  jobs the work root held `probe-ok-1`, `probe-ping`,
  `probe-refused`.
- S3 CONFIRMED. A second successful job with a distinct
  job_id brought the count to 4 — one directory per job,
  unbounded.
- S4 CONFIRMED. One test each from `ReadLiveTest`,
  `JudgeOffPathTest` and `AdversarialTests`, run with
  TMPDIR pointed at an empty scratch dir, left exactly the
  three directories the rig weighed: `hp-jf-*`, `hp-joff-*`,
  `hp-adv-*` (one per test, all tests green).
- Wider suite scan (grep over `runner/tests`: a file counts
  when it calls `mkdtemp` and contains no `rmtree`,
  `addCleanup` or `TemporaryDirectory` token): 49 files leak
  their temp bases outright, including `test_graceful_failure`
  (87 sites), `test_notable_access` (38),
  `test_negative_oracle_and_extensions` (17) and
  `test_oracle_intake_fuzz` (12). The count is a lower
  bound — files that contain a cleanup token somewhere may
  still leak in the classes that do not use it, as the
  `hp-jf-` file itself shows. The rig's temp fill was the
  whole suite running as a service, so the whole-suite
  pattern is the honest cause; the product fix in this
  record stops the runner's own accumulation and the named
  harnesses, and the remaining 49 files are a named
  follow-on in the conclusions, not silently fixed by this
  change.

## Conclusions and the landed fix

Landed 2026-11-06 on top of the supposition commit. S5
CONFIRMED in full: the same probes that left 3–4 directories
before the fix leave 0 after it on the success, ping and
refusal paths, and the planted sweep set behaves exactly as
S5 states (the 30-day orphan reaped; the fresh directory,
the foreign-named directory, the plain file and the symlink
all kept; a retention of 0 reaps nothing). The harness
re-probe also shows 0: the three tests of S4, re-run with
TMPDIR at an empty scratch dir, leave nothing behind.

What landed:

- `runner/ops/exec.py`: `execute_job` is a thin head —
  validation that needs no workspace, workspace creation,
  and the stashed result's root — wrapping
  `_execute_job_body` in a `try/finally` that reaps the
  workspace on EVERY path out (success, ping, refusal,
  failure, timeout). A reap that leaves the directory behind
  logs a WARN; the startup sweep retries it later.
  `reap_work_dir` never follows symlinks and never raises.
  `reap_work_orphans` is the bounded startup sweep of the
  fix shape above (direct children of `work/` only, the
  safe job_id name shape, real directories only, mtime
  older than the retention age, at most 512 per sweep,
  never raises). Both helpers are re-exported on the
  `runner/runner.py` facade.
- `runner/ops/main.py`: the sweep runs once at startup,
  after the log file is set, and logs one INFO line when it
  reaped anything.
- The config key `work_retention_sec` (default 604800, 0
  disables) is registered in `runner/guard/defaulted.py`'s
  NUMERIC table, so an unusable value reads as the default
  and is named by the existing defaulted-keys startup
  summary line — the mechanism the fix shape promised, not
  a bespoke warning. It is mirrored in
  `runner/tests/defaults_registry.py` (the registry's row
  count pin moved 132 to 133 and its core count 81 to 82
  for the new row; the `max_output_bytes` row's reader
  moved to `_execute_job_body` with the split), stated in
  `runner/config.example.json`, and documented in
  `docs/infrastructure-documents/oracle/configuring-oracle.md`.
  No CLI flag, as decided.
- Harness cleanups: `tearDown` in `test_job_fuzz.py`'s
  `ReadLiveTest`, `ReadLiveCampaignLegsTest` and `MainTest`;
  `addCleanup` in `test_v31_verify.py`'s `JudgeOffPathTest`,
  in `test_protocol_and_edges.py`'s `AdversarialTests`, at
  all 19 `mkdtemp` sites in `test_canary_watch.py` and all
  87 in `test_graceful_failure.py`, and for the `hp-r3-`
  bases in `test_enforce_races.py`'s `SeenSetRaceTest`;
  the `first_ping.py` bench loop removes each run's base in
  a `finally`.

Tests: `runner/tests/test_temp_reap.py`, 21 tests —
`ExecuteJobReapTest` (success, outputs collected before
the reap, ping, SHA384 refusal, unknown-kind refusal,
failed download, timeout, quarantine surviving the reap,
`reap_work_dir` semantics) and `WorkOrphanSweepTest` (old
orphan reaped; fresh, foreign-named, plain-file and symlink
children kept; retention 0 disables and is not read as a
defaulted value; an unusable value and a boolean read as
the default; a custom retention age; the 512 bound, with
520 planted and exactly 8 left; a missing work root is
quiet; the count is only what the sweep itself reaped).
Test-first evidence: against the unfixed tree the file
runs 21 tests with 7 failures and 14 errors; against the
fixed tree, 21 pass. The symlink case reuses the already
registered skip reason "cannot create a symlink here"; no
new skip reason was registered by this change.

Assertion moves, recorded as Q127 in
`docs/steady/seats/questions.md`: 3 tests asserted the
workspace survives the job, and 3 more used it as their
observation channel — `test_protocol_and_edges`' no-send
test, `test_campaign_core`'s workdir shape,
`test_enforce_races`' seen-set races, `test_remediation`'s
benign and off-mode tests, and `test_run_variant`'s bucket
test. Each keeps its named intent and now observes through
a channel that survives by design (the result, declared
outputs collected before the reap, the sent results, the
quarantine root, the variant's audit entry). No other
assertion moved.

Verification runs (TMPDIR on the workspace disk; the box
was under fleet load throughout, and timing-sensitive
suites flap on it): test_temp_reap 21 OK (repeatedly);
test_temp_reap + test_canary_watch + test_graceful_failure
233 OK; test_job_fuzz + test_protocol_and_edges 214 with
the single no-send assertion above, green after its move;
test_confinement, test_enforce_races, test_campaign_core,
test_flag321_indirect, test_concurrency_poison,
test_atomicio, test_delivery_edges, test_extension_poison,
test_file_names, test_campaign_phase1 — 338 tests, the only
failures the campaign-core and race assertions above, green
after their moves; the runner/guard cluster (test_runner,
test_change_kind, test_run_variant, test_platinum_runner,
test_audience, test_job_files, test_doc_default_divergences,
test_defaults_table_hunt, test_skip_registry,
test_doc_version_rot, test_reader_docs_quiet, the 4
remediation files, test_security_config, test_enforce_races)
— 1,349 tests, failures only in the families named here:
the registry pins and reader (fixed above), the remediation
and variant assertions (moved above), and the
`TestGrepMaxMatches*` families of
test_doc_default_divergences. Those grep families fail
identically on the pristine base tree in this environment
(the query worker subprocess returns no matches; 16
failures there against 20 on the fixed tree in the same 3
classes, the count varying run to run) — pre-existing and
unrelated to this change, which touches no query code.
test_first_ping 12 OK.

Follow-on, named and not done by this change: the wider
suite scan counted 49 test files whose temp bases leak
outright (the pattern, not the runner, is the remaining
cause — the suite runs as a service on the rigs, so its
temp use is service temp use). The files this change fixed
are the ones the rig evidence names plus the two
uniform-pattern files; the other 49 are a queue item of
their own, one `addCleanup` pattern repeated, and the
`_MEI*` dirs stay with the rig-side daily guard for the
reasons stated above.
