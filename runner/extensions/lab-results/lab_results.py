#!/usr/bin/env python3
"""Lab Results: a Homing Pigeon user extension (example sense).

Watches a folder where experiment runs drop result files -- one
JSON file per run, shaped like:

    {"run": "exp-041", "status": "finished",
     "metrics": {"accuracy": 0.93, "loss": 0.21}}

-- and turns landed runs into sensor alerts for the Oracle. Each
alert names one of the signals declared in extension.json:

- experiment_finished      a run reached a finished state
- metric_threshold_crossed the headline metric crossed the
                           threshold declared in the tunables
- result_anomaly           the headline metric sits far outside
                           the folder's earlier results

The watcher is deliberately boring machinery: it diffs the folder
against a small state file, prints one alert payload per line, and
exits. Signing and mailing the payloads is the standard senses
flow (docs/senses.md); this script is the part a researcher
rewrites, so it stays small enough to read in one sitting.

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload with
this sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extensions.md, "Local delivery").

Result files are diffed by content. A file still being written, or
one whose run has not finished, files nothing and is retried on
the next pass. Editing a finished result re-reports it: the
content changed, so as far as the lab is concerned it is a new
result.
"""
import argparse
import json
import os
import sys


def _num(value):
    return "%g" % value


def _is_number(value):
    """A finite int or float, never a bool.

    Infinity and NaN are floats, and an integer too large for a float
    is an int, but none of them is a usable tunable: inf once made a
    threshold that never trips (or always trips), and int(inf) is an
    OverflowError. Each reads as "not a number" so the documented
    default applies.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        f = float(value)
    except (OverflowError, ValueError):
        return False
    return f == f and f not in (float("inf"), float("-inf"))


def _fresh_state():
    return {"reported": {}, "history": []}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    reported = state.get("reported")
    if not isinstance(reported, dict):
        reported = {}
    history = state.get("history")
    if not isinstance(history, list):
        history = []
    return {
        "reported": {k: v for k, v in reported.items()
                     if isinstance(k, str) and isinstance(v, str)},
        "history": [float(v) for v in history if _is_number(v)],
    }


def scan(watch_dir, manifest, state):
    """One pass over the results folder. Returns (alerts, new_state).

    Pure apart from reading the folder: no printing, no clock, so
    tests drive it directly. `manifest` is the parsed extension.json
    (its tunables steer the pass); `state` is the dict this function
    returned last time.
    """
    state = _clean_state(state)
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "lab_results"
    metric = tunables.get("metric")
    if not isinstance(metric, str) or not metric:
        metric = "accuracy"
    threshold = tunables.get("threshold")
    if not _is_number(threshold):
        threshold = None
    band = tunables.get("anomaly_band")
    band = float(band) if _is_number(band) and band > 0 else 0.25
    min_history = tunables.get("anomaly_min_history")
    min_history = int(min_history) if _is_number(min_history) \
        and min_history >= 1 else 3
    alerts = []
    try:
        names = sorted(os.listdir(watch_dir))
    except OSError:
        return alerts, state
    for fname in names:
        if not fname.endswith(".json"):
            continue
        path = os.path.join(watch_dir, fname)
        try:
            with open(path, encoding="utf-8") as fh:
                rec = json.load(fh)
        except (OSError, UnicodeDecodeError, ValueError):
            continue  # half-written result file; retry next pass
        if not isinstance(rec, dict):
            continue
        fingerprint = json.dumps(rec, sort_keys=True, default=str)
        if state["reported"].get(fname) == fingerprint:
            continue
        if rec.get("status") != "finished":
            continue  # not landed yet; a later pass picks it up
        run = rec.get("run")
        if not isinstance(run, str) or not run:
            run = fname[:-len(".json")]
        metrics = rec.get("metrics")
        if not isinstance(metrics, dict):
            metrics = {}
        value = metrics.get(metric)
        numeric = _is_number(value)
        detail = {"run": run, "metric": metric,
                  "value": value if numeric else None}
        alerts.append({
            "sensor": sensor, "signal": "experiment_finished",
            "severity": "info",
            "title": f"experiment {run} finished",
            "detail": dict(detail),
        })
        if numeric and threshold is not None and value >= threshold:
            alerts.append({
                "sensor": sensor, "signal": "metric_threshold_crossed",
                "severity": "medium",
                "title": f"experiment {run}: {metric} {_num(value)} "
                       f"crossed threshold {_num(threshold)}",
                "detail": dict(detail, threshold=threshold),
            })
        history = state["history"]
        if numeric and len(history) >= min_history:
            mean = sum(history) / len(history)
            if mean != 0 and abs(value - mean) > band * abs(mean):
                alerts.append({
                    "sensor": sensor, "signal": "result_anomaly",
                    "severity": "high",
                    "title": f"experiment {run}: {metric} {_num(value)} "
                           f"is far from this folder's earlier mean "
                           f"{_num(mean)}",
                    "detail": dict(detail, history_mean=mean,
                                   history_count=len(history)),
                })
        state["reported"][fname] = fingerprint
        if numeric:
            history.append(float(value))
    return alerts, state


def _deliver_local(alerts, args):
    """Sign and deliver each alert to a runner on this machine.

    Returns how many alerts were delivered, or None when local
    delivery is not set up (the reason is printed). Uses the
    runner's own producer helpers, so the envelope and signature
    are the contract's, not a re-implementation.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(
        os.path.join(here, "..", "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        from runner.ops import extensions as hp_extensions
    except ImportError as e:
        print(f"lab-results: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"lab-results: no signing secret in ${args.secret_env}; "
              f"set it to this sense's key secret", file=sys.stderr)
        return None
    delivered = 0
    for alert in alerts:
        payload = hp_extensions.build_sensor_alert(
            alert["sensor"], alert["severity"], alert["title"],
            key_id=args.key_id, signal=alert.get("signal"),
            detail=alert.get("detail"))
        try:
            if args.local_port:
                hp_extensions.send_local_signal(
                    payload, secret, port=args.local_port)
                where = f"127.0.0.1:{args.local_port}"
            else:
                where = hp_extensions.drop_local_signal(
                    args.local_dir, payload, secret)
        except (OSError, ValueError) as e:
            print(f"lab-results: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"lab-results: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Lab Results extension watcher: print sensor "
                    "alert payloads for runs that landed since the "
                    "last pass.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--watch-dir", default=None,
                    help="results folder (default: the manifest's "
                         "watch_dir tunable, else ./results)")
    ap.add_argument("--state", default=None,
                    help="state file (default: .lab-results-state.json "
                         "in the results folder)")
    ap.add_argument("--local-dir", default=None,
                    help="runner base dir: deliver alerts locally "
                         "(signed, into its local inbox) instead of "
                         "printing payloads")
    ap.add_argument("--local-port", type=int, default=None,
                    help="with --local-dir: push to the runner's "
                         "loopback listener on this port instead of "
                         "dropping files")
    ap.add_argument("--key-id", default="",
                    help="key id this sense signs as (its "
                         "sensors.<name>.key_id in the runner config)")
    ap.add_argument("--secret-env", default="HOMING_PIGEON_SENSOR_SECRET",
                    help="environment variable holding the signing "
                         "secret (default: HOMING_PIGEON_SENSOR_SECRET)")
    args = ap.parse_args(argv)
    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"lab-results: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    watch_dir = args.watch_dir or tunables.get("watch_dir") or "results"
    state_path = args.state or os.path.join(
        watch_dir, ".lab-results-state.json")
    state = _fresh_state()
    try:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        pass
    if not os.path.isdir(watch_dir):
        print(f"lab-results: no results folder at {watch_dir} yet; "
              f"nothing filed", file=sys.stderr)
        return 0
    alerts, state = scan(watch_dir, manifest, state)
    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten, so the
            # next pass reports these runs again.
            print(f"lab-results: {len(alerts) - delivered} of "
                  f"{len(alerts)} alert(s) not delivered; state not "
                  f"saved, will retry next pass", file=sys.stderr)
            return 2
    else:
        for alert in alerts:
            print(json.dumps(alert, sort_keys=True))
    try:
        with open(state_path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, sort_keys=True)
    except OSError as e:
        print(f"lab-results: cannot write state {state_path}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
