# Training Watch — an example Homing Pigeon extension

A sense for machine-learning training runs. A training job
runs for hours on expensive hardware and fails in a small
number of well-known ways: the process dies on an exception
nobody is watching, the log goes quiet while the run is
supposedly alive, the loss stops improving long before the
schedule ends, the GPU cooks or runs out of memory
headroom. Training Watch polls the three places those
failures are visible — the run's log tail, the run's
checkpoint directory, and the GPU itself — and files what
it finds as Oracle signals.

The watcher files five declared signals:

| Signal | Fires when | Severity |
|--------|------------|----------|
| `checkpoint_arrived` | A new checkpoint file in the run directory has **stopped changing** (rule below) | info |
| `training_stalled` | The log grew before and then went quiet for `stall_after_sec` while the run should be alive, **or** the last `loss_points` parsed losses are flat or worsening — one signal; the detail names which evidence fired | medium |
| `run_crashed` | A crash marker in the newly read log lines: a Python `Traceback`, `CUDA out of memory`, an NCCL error, a `RuntimeError` | high |
| `gpu_overheating` | GPU temperature reaches `gpu_temp_high_c` (default 85) | high |
| `gpu_memory_pressure` | GPU memory reaches `gpu_mem_high_pct` of the card's total (default 95) | medium |

The two high signals cross the local wake gate: a crashed
run or a cooking GPU wakes the Oracle, which files its
brief from the alert itself.

## The rules that keep it quiet

**Checkpoints file when they settle, never while they
grow.** A checkpoint is identified by name + size +
mtime. The first pass that sees a file only records it;
the alert files on the first later pass that finds size
and mtime unchanged, so a half-written multi-GB
checkpoint never files. The price is one poll of delay on
a finished checkpoint — deliberate. A filed checkpoint
that later changes (overwritten in place) goes back to
unfiled and must settle again. The scan is shallow: the
run directory and its immediate subdirectories, basenames
matched against `checkpoint_globs`.

**A stall needs a run that started.** The quiet-log
variant never fires on a log that never produced a line,
and never on the first pass that sees lines — the log
must have been seen growing on an earlier pass and then
go quiet for the full `stall_after_sec`. If you configure
a status command (`--status-cmd` or the `status_cmd`
tunable; exit 0 means the run is alive) and it reports
the run is over, quiet is expected and neither stall
variant fires: a finished run is not a stalled one.

**The loss variant only believes losses it can read.**
Losses come from a deliberately conservative regex over
the log lines — `loss: 0.431`, `loss=0.431`,
`train_loss: 1.2e-3` shapes and nothing cleverer. The
last `loss_points` (default 5) parsed losses file the
variant when no point in the window improves on the
window's first value by more than `loss_flat_tol`
(default 0.01); it is edge-triggered, so a run that stays
flat files once, and the variant re-arms only when a loss
improves past the tolerance. The detail always carries
`source: "parsed_from_log"`. A log format the regex
cannot read simply never produces this variant — the
quiet-log variant and the crash markers still work.

**A crash dump files once.** Crash episodes key on the
marker plus a line window (the cumulative log line number
divided by `crash_window_lines`, default 100), so a
repeated traceback dump spanning consecutive lines files
one alert; the same marker turning up windows later is a
new episode and files again. The detail carries the
marker, the matched line, and the log's last line.

**The GPU source is capability-based.** Temperature and
memory come from one `nvidia-smi` query per pass. No GPU
or no `nvidia-smi` — a CPU-only box, a laptop — and the
source reports nothing, which never yields a signal and
is never an error; the log and checkpoint halves of the
sense work unchanged.

Footprint: this is a standard-library text parser plus a
directory listing, run as a poll — there is no resident
process, no daemon, and no model anywhere in it. A pass
costs one bounded log read (`tail_bytes`), one shallow
directory scan, and at most one short `nvidia-smi` call;
between passes it costs exactly nothing. It is sized to
sit next to a local inference model on the same box
without measurable contention — the whole sense is
cheaper than one inference call, by construction.

Run one pass (point it at a run):

```bash
python3 training_watch.py --log runs/exp1/train.log \
    --run-dir runs/exp1 \
    --local-dir <runner base dir> --key-id <its key id>
# HOMING_PIGEON_SENSOR_SECRET holds the training_watch sense's key
```

Add `--status-cmd "kill -0 12345"` (or a run script's
pidfile check) if you want finished runs exempted from
the stall call. Without `--local-dir` it prints one alert
payload per line; signing and delivery then follow the
standard senses flow. State lives in
`.training-watch-state.json` next to the script; delete
it and every baseline — settled checkpoints, parsed
losses, log offsets — starts over.

Or try it anywhere by feeding it a samples file instead
of a live run:

```bash
python3 training_watch.py --samples samples.json
# one alert payload per line on stdout
```

A samples file is one JSON object of readings:

```json
{"now": 1792375113.0,
 "gpu": {"temp_c": 71.0, "mem_used_mb": 23000.0,
         "mem_total_mb": 24576.0, "util_pct": 98.0},
 "run_alive": true,
 "log_lines": [{"ts": 1792375000.0,
                "line": "step 400 loss: 0.431"}],
 "checkpoints": [{"name": "checkpoint-400",
                  "size": 1048576, "mtime": 1792374900.0}]}
```

(`gpu` may be `null` and `run_alive` `null` when a source
has nothing to say; log lines carry their own timestamps
in samples, while a live read stamps new lines with the
log file's mtime.)

### Other tunables

`run_dir` (default empty) is the directory whose checkpoints are scanned and `log_path` (default empty) the training log that is tailed — with both empty the watcher has nothing to watch and files nothing; `loss_history` (default 200) is how many parsed loss points the state file keeps for the trend rules; `max_checkpoints` (default 200) bounds how many checkpoint identities are remembered.

## Light mode

Light mode is cadence and surface. Raise
`poll_interval_sec` to 900 or beyond — training runs move
on a scale of hours, and a quarter-hour's delay on a
stall call costs nothing. Lower `tail_bytes` (16384 still
catches every crash marker in practice). Set
`gpu_temp_high_c` aside entirely by pointing the sense at
a box with no `nvidia-smi` in its PATH — or accept the
one short query per pass, which is the cheapest read this
sense makes. With the GPU source silent the parser half
still watches the log and the checkpoints at full
strength; nothing about the sense needs a GPU to be
useful. On Pi Light it pairs naturally with the
deterministic Oracle: the alert already names the marker,
the silent seconds, and the loss window it judged.

The full extension walkthrough — manifest fields, the
versioning contract, sensor binding, and how to turn this
example into your own package — is in
[docs/extensions.md](../../../docs/extensions.md).
