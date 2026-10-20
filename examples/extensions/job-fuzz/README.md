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

One honest limit: the runner's retained records cap a
job's script at 500 characters, so variants fuzz the
retained text. The corpus is the record, not the wire.

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
