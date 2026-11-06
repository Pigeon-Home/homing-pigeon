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

(to be filled in from the probes, after this section was
committed)

## Conclusions and the landed fix

(to be filled in once the fix and its tests land)
