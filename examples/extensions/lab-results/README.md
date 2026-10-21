# Lab Results — an example Homing Pigeon extension

A sense for people who run experiments. Point it at the folder
where your training or evaluation runs drop their result files,
and the Oracle learns what the lab produced: which runs finished,
which ones crossed the metric you care about, and which ones look
wrong against the folder's own history.

Each result file is one JSON object:

```json
{"run": "exp-041", "status": "finished",
 "metrics": {"accuracy": 0.93, "loss": 0.21}}
```

The watcher files three declared signals:

| Signal | Fires when |
|--------|------------|
| `experiment_finished` | A run reaches `"status": "finished"` |
| `metric_threshold_crossed` | A finished run's headline metric reaches the `threshold` tunable |
| `result_anomaly` | A finished run's headline metric sits outside `anomaly_band` of the folder's earlier mean |

Run one pass:

```bash
python3 lab_results.py --watch-dir path/to/results
# one alert payload per line on stdout; state in
# path/to/results/.lab-results-state.json
```

Alert payloads are unsigned sense alerts; signing and delivery
follow the standard senses flow.

## Light mode

For a Pi Light install this sense is already cheap: a pass is
one listing of `watch_dir` plus reading the result files in
it — no network, no subprocess, no model. The one cost that
can grow is the folder itself: every pass re-reads every
`.json` file in it to diff the contents against the state
file, so keep the folder pruned — move results out once the
lab is done with them. Experiments land on human timescales,
so run the pass on a slow timer; a result noticed minutes
late is noticed in plenty of time.

The full extension walkthrough — manifest fields, the
versioning contract, sensor binding, and how to turn this
example into your own package — is in
[docs/extensions.md](../../../docs/extensions.md).
