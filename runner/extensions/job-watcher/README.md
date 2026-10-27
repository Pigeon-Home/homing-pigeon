# Job Watcher — an example Homing Pigeon extension

A sense that watches the jobs, not the machine. Job
Watcher reads the runner's retained job history — the
`retained/` folder under the runner's base dir, one JSON
file per finished job — and files what the history teaches
it: which jobs keep failing, which jobs pass and fail on
the same script so neither outcome can be trusted, which
jobs have quietly started taking far longer than they used
to, and when so many distinct jobs fail at once that the
box, not any job, is the story. It opens the retained
folder read-only; nothing in the runner knows it exists.

The watcher files four declared signals:

| Signal | Fires when |
|--------|------------|
| `job_failing_repeatedly` | The same job — same `kind` and script — failed at least `repeat_failures` times (default 3) inside `failure_window_sec` (default a day); the detail names the dominant exit code and the dominant first error line |
| `job_flaky` | The job's last `flaky_runs` runs (default 6) alternate success/failure at least `flaky_min_transitions` times (default 3), with both outcomes present — pattern `PFPF…` in the detail |
| `job_duration_anomaly` | A run's duration is a robust outlier against the job's **own** earlier durations (median/MAD, see below) — never filed for a job without enough history to have a baseline |
| `failure_cluster` | At least `cluster_min_jobs` distinct jobs (default 3) failed inside `cluster_window_sec` (default 15 minutes): look at the box, not the jobs |

Two honest limits of the source, stated once. Retention is
view-gated in the runner, so a job delivered at the full
view with no declared queries may leave no retained record
at all (or only an artifact-scan note, which carries no
`duration_sec` — such jobs count toward failures and
clusters but can never build a duration baseline). And
records are pruned by the runner's retention window; the
watcher's own state file is the long memory, folding every
record it sees into its per-job histories as it goes.

## How it improves

The watcher's calls are only as good as the history behind
them, and the history grows by itself. On day one it can
count failures and clusters. Duration calls wait: a job
needs `duration_min_baseline` earlier durations (default
5) before any anomaly can be filed against it, and the
scorer judges by median and MAD — spread the job itself
demonstrated — so a job that has always taken an hour is
never "anomalous" for taking an hour, while a job that
takes ten seconds and suddenly takes ten minutes is called
the first time it happens. The longer it runs, the more
jobs cross the baseline threshold and the tighter every
baseline gets. There is no training step and nothing to
tune per job; patience is the whole mechanism.

The judgement lives behind one seam: `score_duration(
history, value)` in the producer, today a standard-library
median/MAD judge. Owners who want a real streaming model
there can install [River](https://riverml.xyz) (the
open-source online machine-learning library, Apache-2.0)
and replace that one function with a scorer backed by its
streaming anomaly detectors — `HalfSpaceTrees` is the
natural fit — feeding it the same per-job duration history
and returning the same `(anomalous, stats)` shape. The
state file deliberately keeps each job's recent raw
durations, so a River-backed scorer can be warmed from
real history instead of starting cold. River is **not** a
dependency of this example and is not installed with it;
the shipped scorer is the stdlib one, and the seam is the
whole integration story.

Run one pass (the runner base dir is read from the
`runner_base_dir` tunable, or `--runner-dir`):

```bash
python3 job_watcher.py --runner-dir <runner base dir> \
    --local-dir <runner base dir> --key-id <its key id>
# HOMING_PIGEON_SENSOR_SECRET holds the job_watcher sense's key
```

Without `--local-dir` it prints one alert payload per line;
signing and delivery then follow the standard senses flow.
State lives in `.job-watcher-state.json` next to the
script; delete it and every baseline starts over.

Or try it anywhere by feeding it a readings file instead of
a retained store:

```bash
python3 job_watcher.py --readings readings.json
# one alert payload per line on stdout
```

A readings file is one JSON object of normalized records:

```json
{"now": 1792375113.0, "truncated": 0,
 "records": [{"job_id": "job-041", "key": "9f2ac41bd077e013",
              "kind": "exec", "label": "nightly backup.sh",
              "exit_code": 1, "timed_out": false,
              "duration_sec": 42.0, "saved_at": 1792375000.0,
              "error": "rsync: link_stat failed"}]}
```

### Other tunables

`duration_z` (default 3.5) is the robust z-score a run's duration must exceed against the job's own history before `job_duration_anomaly` files.

## Light mode

This sense reads small JSON files on a calm cadence, and
Light mode is mostly cadence: raise `poll_interval_sec`
to 900 or beyond — job history does not move fast, and a
quarter-hour's delay on a flakiness call costs nothing.
Lower `max_history_runs` (30 is plenty of baseline) and
`max_records_per_pass` to bound a single pass over a large
retained store. On Pi Light it pairs naturally with the
deterministic Oracle: the one signal that wakes it is
`failure_cluster` (high), and that alert already names how
many distinct jobs failed inside the window; the medium
signals (the repeat failures, the flapping, the long run and
its baseline) are filed for the next brief, never a wake.

The full extension walkthrough — manifest fields, the
versioning contract, sensor binding, and how to turn this
example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).
