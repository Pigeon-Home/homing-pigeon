# Job Fuzz — an example Homing Pigeon extension

A sense that fuzzes the jobs this box has already run. It
keeps a bounded corpus of the runner's retained job
records, mutates them with grammar-shaped mutations on
idle cycles only, and runs the variants through the
runner's own validation and confined execution — the
bucket — via the core's `--run-variant` door. What it
finds files as Oracle signals: a variant that hangs or
breaks the run (`variant_hard_failure`, high), a variant
whose outcome class diverges from the seed job's recorded
outcome (`variant_divergence`, medium), and the first
sighting of any (mutator, stage, outcome class)
combination (`coverage_novelty`, info).

The findings are context for future opinions, never a
gate on the job that seeded them. A campaign is always
some jobs behind the present; that lag is the design.

## Why this shape

OneFuzz, the platform fuzzer, is a platform as a service
as it stands. An extension does not need the service; it
needs the components, lifted to run locally: a mutation
engine, a corpus that distills, crash triage that
dedupes. Scale-out, corpus sync across machines, and the
notification plane stay behind. What remains is one small
stdlib-only process, run on the operator's own cadence
like every sense, that spends only idle cycles and yields
the moment a real job lands.

A variant is a mutation of a verified job, so its
signature no longer verifies by construction. Variants
are never admitted through the job path, never mailed,
never signed. The core's `--run-variant` mode is the one
door: it copies an allowlist of job keys (script,
interpreter, args, env, a timeout capped at 120s), drops
everything else — files, `script_url`, signatures,
delivery fields — and runs what remains through the same
validation and confined execution as a real exec job.
The sense never holds the shared secret.

## Wiring it up

The sense is off until configured, twice over: the
runner's config must enable the `job_fuzz` sensor (with
its own signing key, like every sense), and the manifest
tunables must say where the retained records live and
which command runs a variant:

- `runner_base_dir` — the runner's base dir; the corpus
  is read from its `retained/` folder. (`--runner-dir`
  wins over the tunable.)
- `runner_cmd` — the command handed one variant file,
  e.g. `python3 /path/to/runner/runner.py --config
  /path/to/config.json --run-variant {variant}`. Empty
  (the default) means no execution: the corpus is
  maintained and nothing files.

Corpus bounds are both operator-tunable: `corpus_max_jobs`
(default 200) and `corpus_max_age_days` (default 30).
Campaign bounds: `max_seeds_per_pass` (3),
`variants_per_seed` (4), `max_variants_per_pass` (8),
`variant_timeout_sec` (30). Idle bounds: `idle_after_sec`
(600) of job quiet plus, where the platform offers it, a
one-minute load average under `idle_load_max` (1.0).

Every variant the campaign runs is archived (default:
`.job-fuzz-variants/` next to the sense; `work_dir`
moves it), pruned to `max_archived_variants` (200). A
finding's detail names its archive file, and any finding
reproduces by handing that file to `--run-variant` again.

## How the campaign improves on itself

Four habits, each lifted from the fuzzing platforms and
kept deterministic:

- **The corpus learns.** A variant that reaches a
  coverage novelty is promoted into a distilled tier of
  the corpus (`distilled_max_jobs`, default 50, same age
  bound as seeds) and later campaigns mutate it as a seed
  in its own right. Campaigns compound instead of
  restarting from the same retained jobs.
- **Mutations recombine and speak the local dialect.**
  Alongside the single-seed mutators, `splice` grafts a
  segment of one seed's script into another, and
  `dictionary` injects tokens harvested from the corpus's
  own scripts — the commands, flags, and paths this box
  actually runs.
- **Two mutators are probes with a promise.**
  `blank_line` and `trailing_blank` preserve a script's
  meaning, so they carry an expected relation: same
  outcome class, same output digest. A broken promise
  files a divergence that names the broken relation.
- **Findings shrink, triage buckets, seeds earn their
  budget.** An interesting variant is minimized before it
  files — lines dropped while the outcome persists,
  bounded by `minimize_max_steps` (default 12) — so the
  archived repro is the smallest one the campaign could
  make. Hard failures file once per normalized reason
  bucket across all seeds (the same validation hole found
  ten ways is one signal with a count and examples), and
  seed selection spends the pass on the seeds with the
  best historical yield first.

One honest limit: the runner's retained records cap a
job's script at 500 characters, so variants fuzz the
retained text. The corpus is the record, not the wire.

### Other tunables

`filed_cooldown_sec` (default 604800, a week) is how long a finding that was already filed stays quiet before the same finding may file again; `max_alerts_per_pass` (default 20) caps the alerts one pass may file; `max_records_per_pass` (default 500) caps how many retained records one pass reads.

## Light mode

This sense exists to spend idle cycles, so Light mode is
mostly restraint: raise `poll_interval_sec` (900 is the
default; hours cost nothing — the corpus moves at the
speed of real jobs), lower `max_variants_per_pass` to 2
or 3, and keep `variant_timeout_sec` small. On a Pi the
campaign still runs entirely against the deterministic
machinery: mutation, the core's validation, the confined
execution, triage. No model is involved at any point, so
Pi Light loses nothing but speed.

```sh
# HOMING_PIGEON_SENSOR_SECRET holds the job_fuzz sense's key
# secret; --local-dir is the runner's base dir.
python3 job_fuzz.py --runner-dir /path/to/state \
    --runner-cmd "python3 /path/to/runner/runner.py \
      --config /path/to/config.json --run-variant {variant}" \
    --local-dir /path/to/state --key-id <the sense's key id>
```
