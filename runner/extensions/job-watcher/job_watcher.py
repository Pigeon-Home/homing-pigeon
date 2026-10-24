#!/usr/bin/env python3
"""Job Watcher: a Homing Pigeon user extension (example sense).

Not a security sense. Job Watcher watches the runner's job
history and files what it learns as sensor alerts for the
Oracle: which jobs keep failing, which jobs cannot be
trusted because they pass and fail on the same script, which
jobs have started taking far longer than they used to, and
when so many different jobs fail at once that the box, not
any job, is the story. It gets better at these calls the
longer it runs, because every call is made against a
baseline the job itself accumulated.

What it reads: the runner's retained job store,
<base dir>/retained/<job_id>.json -- one JSON file per
finished job, holding (among other fields) kind, the script
(first 500 characters), exit_code, timed_out, duration_sec
and saved_at. The watcher opens that directory read-only;
nothing in the runner knows it exists. Two honest limits
of the source, stated once: retention is view-gated, so a
job delivered at the full view with no declared queries may
leave no record at all (or only an artifact-scan note,
which carries no duration_sec), and job ids are unique per
dispatch -- the repeatable identity of "the same job" is
its kind plus its script, which is what the baselines key
on. Records are also pruned by the runner's retention
window, so the watcher's own state file is the long
memory: each pass folds the records it has not seen into
its per-job run histories and keeps them there.

Each alert names one of the signals declared in
extension.json:

- job_failing_repeatedly  the same job failed at least
                    repeat_failures times (default 3)
                    inside failure_window_sec (default a
                    day); the detail names the dominant
                    exit code and error line
- job_flaky         the job's last flaky_runs runs
                    (default 6) alternate success/failure
                    at least flaky_min_transitions times
                    (default 3), with both outcomes present
- job_duration_anomaly a run far beyond the job's own
                    baseline spread, judged by the scorer
                    seam below; a job with fewer than
                    duration_min_baseline (default 5)
                    earlier durations has no baseline and
                    gets NO anomaly call -- that restraint
                    is deliberate
- failure_cluster   at least cluster_min_jobs (default 3)
                    DISTINCT jobs failed inside
                    cluster_window_sec (default 15
                    minutes): the box, not the job

The learning seam is one function: score_duration(history,
value) -> (anomalous, stats), today a robust median/MAD
judge from the standard library. The README documents the
upgrade path: River's streaming anomaly detectors can
replace the scorer behind the same seam for owners who
install River; the state file deliberately keeps each
job's recent raw durations so any future scorer can be
warmed from real history instead of starting cold.

The machinery is deliberately boring, in the Lab Results
example's shape. read_live() is the only function that
touches the machine; it returns one readings dict, and
decide() -- readings plus manifest plus last pass's state,
out come alerts and the new state -- is pure, so the whole
decision surface is testable against fixture records.
Current time arrives as readings["now"], never from a
clock inside decide(). A missing retained directory, an
unreadable or half-written record, an oversized file:
each is skipped quietly -- absence is a normal case, not
an error.

Run on the same machine as the runner, it delivers
locally: --local-dir <runner base dir> signs each payload
with this sense's key (read from the environment variable
named by --secret-env) and drops it into the runner's
local inbox, or pushes it to the runner's loopback
listener when --local-port is given. Same envelope, same
signature -- only the transport differs
(docs/extend/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line, and
signing and delivery follow the standard senses flow.

--readings FILE reads a readings dict from a JSON file
instead of the retained store: the way to try the sense
(and test it) against known history, on any box at all.
The retained directory it watches comes from the
runner_base_dir tunable (or --runner-dir, which wins).
"""
import argparse
import hashlib
import json
import os
import sys
import time

_MAX_RECORD_BYTES = 8 * 1024 * 1024
_SEEN_CAP = 2000


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


def _num(value):
    return "%g" % value


def _tunables(manifest):
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    return tunables if isinstance(tunables, dict) else {}


def _tunable(tunables, key, default):
    value = tunables.get(key)
    return float(value) if _is_number(value) else default


def _count_tunable(tunables, key, default):
    """A count of at least one, truncated; anything else is the default.

    Zero, a negative or a fraction below one is no count: it clamped a
    threshold to one or judged a whole history, so it reads as the
    documented default like every other unusable value.
    """
    value = tunables.get(key)
    if _is_number(value) and value >= 1:
        return int(value)
    return default


def _span_tunable(tunables, key, default):
    """A window of at least one second; anything else is the default."""
    value = tunables.get(key)
    if _is_number(value) and value >= 1:
        return float(value)
    return default


def _positive_tunable(tunables, key, default):
    """A strictly positive number; zero and below read as the default."""
    value = tunables.get(key)
    if _is_number(value) and value > 0:
        return float(value)
    return default


def job_key(kind, script):
    """The repeatable identity of "the same job".

    Job ids are unique per dispatch, so a baseline cannot
    key on them. What repeats is the work itself: the kind
    plus the script text the retained record kept.
    """
    digest = hashlib.sha256(
        f"{kind}\n{script}".encode("utf-8")).hexdigest()
    return digest[:16]


def job_label(kind, script):
    """A one-line human name for a job key's work."""
    for line in (script or "").splitlines():
        line = " ".join(line.split())
        if line:
            return line[:60]
    return kind or "job"


# --- the scorer seam: the one replaceable judgement -------------------

def _median(values):
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def score_duration(history, value, min_baseline=5, z_limit=3.5):
    """Judge one duration against a job's own earlier durations.

    Returns (anomalous, stats). The standard library's
    robust judge: the median is the baseline, the MAD
    (median absolute deviation) is the spread, and the
    value is anomalous when its robust z-score --
    0.6745 * (value - median) / MAD -- reaches z_limit
    while sitting above the median. With too little
    history there is no baseline and the answer is always
    (False, ...): no history, no anomaly call. A history
    with zero spread calls anything past twice the median
    (and at least 5 seconds beyond it) anomalous.

    This function is the learning seam (see the README):
    a streaming model such as River's HalfSpaceTrees can
    replace it behind this exact signature, consuming the
    same history and returning the same shape.
    """
    stats = {"baseline_runs": len(history), "median": None,
             "mad": None, "z": None}
    if value is None or len(history) < max(1, min_baseline):
        return False, stats
    med = _median(history)
    mad = _median([abs(v - med) for v in history])
    stats["median"] = round(med, 3)
    stats["mad"] = round(mad, 3)
    if value <= med:
        return False, stats
    if mad <= 0:
        return (value > 2.0 * med and (value - med) >= 5.0), stats
    z = 0.6745 * (value - med) / mad
    stats["z"] = round(z, 2)
    return z >= z_limit, stats


# --- the live reads: the only platform-touching code -----------------

def _record_observation(path, fallback_mtime):
    """One retained record -> one observation, or None.

    Tolerant by design: a file that is unreadable, not
    JSON, not an object, or missing a usable exit_code or
    timestamp is skipped, never an error. Only the fields
    the watcher judges are read out; the job's stdout is
    never touched.
    """
    try:
        if os.path.getsize(path) > _MAX_RECORD_BYTES:
            return None
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    exit_code = record.get("exit_code")
    if not _is_number(exit_code):
        return None
    saved_at = record.get("saved_at")
    if not _is_number(saved_at):
        saved_at = fallback_mtime
    if not _is_number(saved_at):
        return None
    job_id = record.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        job_id = os.path.basename(path)
        if job_id.endswith(".json"):
            job_id = job_id[:-5]
    kind = record.get("kind")
    if not isinstance(kind, str):
        kind = ""
    script = record.get("script")
    if not isinstance(script, str):
        script = ""
    duration = record.get("duration_sec")
    if not _is_number(duration):
        duration = None  # artifact-scan notes carry none
    stderr = record.get("stderr")
    error = ""
    if isinstance(stderr, str):
        for line in stderr.splitlines():
            line = line.strip()
            if line:
                error = line[:120]
                break
    return {
        "job_id": job_id,
        "key": job_key(kind, script),
        "kind": kind,
        "label": job_label(kind, script),
        "exit_code": int(exit_code),
        "timed_out": bool(record.get("timed_out")),
        "duration_sec": float(duration) if duration is not None
                        else None,
        "saved_at": float(saved_at),
        "error": error,
    }


def read_live(manifest):
    """One snapshot of the runner's retained job store.

    Returns {"now", "records", "truncated"}: the newest
    max_records_per_pass observations from <runner base
    dir>/retained, oldest first; records beyond the cap are
    counted in "truncated" (they are the oldest, and the
    next pass after the state advances sees the rest). A
    missing base dir or retained folder reads as empty.
    Never raises.
    """
    tunables = _tunables(manifest)
    base = tunables.get("runner_base_dir")
    if not isinstance(base, str):
        base = ""
    cap = int(_tunable(tunables, "max_records_per_pass", 500))
    if cap < 1:
        cap = 500
    records = []
    truncated = 0
    retained = os.path.join(base, "retained") if base else ""
    if retained and os.path.isdir(retained):
        try:
            names = sorted(os.listdir(retained))
        except OSError:
            names = []
        paths = []
        for name in names:
            if not name.endswith(".json"):
                continue
            path = os.path.join(retained, name)
            try:
                if os.path.isfile(path) and not os.path.islink(path):
                    paths.append((os.path.getmtime(path), path))
            except OSError:
                continue
        paths.sort()
        if len(paths) > cap:
            truncated = len(paths) - cap
            paths = paths[-cap:]
        for mtime, path in paths:
            obs = _record_observation(path, mtime)
            if obs is not None:
                records.append(obs)
        records.sort(key=lambda o: o["saved_at"])
    return {"now": time.time(), "records": records,
            "truncated": truncated}


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"seen": {}, "jobs": {}, "cluster_fired": ""}


def _clean_runs(runs, cap):
    if not isinstance(runs, list):
        return []
    clean = []
    for row in runs:
        if not isinstance(row, (list, tuple)) or len(row) != 4:
            continue
        ts, exit_code, duration, error = row
        if not _is_number(ts) or not _is_number(exit_code):
            continue
        clean.append([float(ts), int(exit_code),
                      float(duration) if _is_number(duration) else None,
                      error if isinstance(error, str) else ""])
    clean.sort(key=lambda r: r[0])
    return clean[-cap:] if cap > 0 else clean


def _clean_state(state, cap):
    if not isinstance(state, dict):
        return _fresh_state()
    seen = state.get("seen")
    if not isinstance(seen, dict):
        seen = {}
    seen = {k: float(v) for k, v in seen.items()
            if isinstance(k, str) and _is_number(v)}
    if len(seen) > _SEEN_CAP:
        keep = sorted(seen.items(), key=lambda kv: kv[1])[-_SEEN_CAP:]
        seen = dict(keep)
    jobs = {}
    raw_jobs = state.get("jobs")
    if isinstance(raw_jobs, dict):
        for key, entry in raw_jobs.items():
            if not isinstance(key, str) or not isinstance(entry, dict):
                continue
            fired = entry.get("fired")
            if not isinstance(fired, dict):
                fired = {}
            jobs[key] = {
                "kind": entry.get("kind")
                        if isinstance(entry.get("kind"), str) else "",
                "label": entry.get("label")
                         if isinstance(entry.get("label"), str) else "",
                "runs": _clean_runs(entry.get("runs"), cap),
                "fired": {k: v for k, v in fired.items()
                          if isinstance(k, str)
                          and isinstance(v, str)},
            }
    cluster_fired = state.get("cluster_fired")
    return {"seen": seen, "jobs": jobs,
            "cluster_fired": cluster_fired
                             if isinstance(cluster_fired, str) else ""}


def _mode(values):
    """The most common value, first-seen winning ties; "" if none."""
    counts = {}
    best = ""
    for value in values:
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
        if counts[value] > counts.get(best, 0):
            best = value
    return best


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time is
    readings["now"]. Records the watcher has not seen
    (by job id) fold into their job key's run history,
    oldest first; then each signal is judged against the
    histories as they now stand. State is {"seen":
    {job_id: saved_at}, "jobs": {key: {"kind", "label",
    "runs": [[ts, exit_code, duration_or_None, error],
    ...], "fired": {signal: fingerprint}}},
    "cluster_fired": fingerprint}.
    """
    tunables = _tunables(manifest)
    max_history = int(_tunable(tunables, "max_history_runs", 60))
    if max_history < 1:
        max_history = 60
    state = _clean_state(state, max_history)
    if not isinstance(readings, dict):
        readings = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "job_watcher"
    now = readings.get("now")
    now = float(now) if _is_number(now) else 0.0
    repeat_failures = _count_tunable(tunables, "repeat_failures", 3)
    failure_window = _tunable(tunables, "failure_window_sec", 86400.0)
    if failure_window <= 0:
        # A window of no time holds no failure, so the signal could
        # never file. It reads as the documented default, a day, like
        # the sibling watchers' window readers.
        failure_window = 86400.0
    flaky_runs = _count_tunable(tunables, "flaky_runs", 6)
    flaky_transitions = _count_tunable(
        tunables, "flaky_min_transitions", 3)
    min_baseline = _count_tunable(tunables, "duration_min_baseline", 5)
    z_limit = _positive_tunable(tunables, "duration_z", 3.5)
    cluster_min = _count_tunable(tunables, "cluster_min_jobs", 3)
    cluster_window = _span_tunable(tunables, "cluster_window_sec", 900.0)

    seen = dict(state["seen"])
    jobs = state["jobs"]
    fresh = []  # (key, observation) folded this pass
    records = readings.get("records")
    if not isinstance(records, list):
        records = []
    queue = []
    for obs in records:
        if not isinstance(obs, dict):
            continue
        job_id = obs.get("job_id")
        key = obs.get("key")
        saved_at = obs.get("saved_at")
        exit_code = obs.get("exit_code")
        if not isinstance(job_id, str) or not job_id \
                or not isinstance(key, str) or not key \
                or not _is_number(saved_at) \
                or not _is_number(exit_code):
            continue
        if job_id in seen:
            continue
        queue.append(obs)
    queue.sort(key=lambda o: o["saved_at"])
    for obs in queue:
        key = obs["key"]
        entry = jobs.get(key)
        if entry is None:
            entry = {"kind": "", "label": "", "runs": [], "fired": {}}
            jobs[key] = entry
        if isinstance(obs.get("kind"), str) and obs["kind"]:
            entry["kind"] = obs["kind"]
        if isinstance(obs.get("label"), str) and obs["label"]:
            entry["label"] = obs["label"]
        duration = obs.get("duration_sec")
        error = obs.get("error")
        entry["runs"].append([
            float(obs["saved_at"]), int(obs["exit_code"]),
            float(duration) if _is_number(duration) else None,
            error if isinstance(error, str) else ""])
        entry["runs"] = entry["runs"][-max_history:]
        seen[obs["job_id"]] = float(obs["saved_at"])
        fresh.append((key, obs))

    def _fire(entry, signal, fingerprint, alert):
        """Append `alert` unless this exact call already fired."""
        if entry["fired"].get(signal) == fingerprint:
            return None
        entry["fired"][signal] = fingerprint
        return alert

    alerts = []
    for key in sorted(jobs):
        entry = jobs[key]
        runs = entry["runs"]
        if not runs:
            continue
        label = entry["label"] or entry["kind"] or "job"
        base_detail = {"job": key, "kind": entry["kind"],
                       "label": label}

        # Repeated failure inside the failure window.
        recent_failures = [r for r in runs
                           if r[1] != 0
                           and r[0] >= now - failure_window]
        if len(recent_failures) >= max(1, repeat_failures):
            dominant_exit = _mode([str(r[1]) for r in recent_failures])
            dominant_error = _mode([r[3] for r in recent_failures])
            detail = dict(base_detail,
                          failures=len(recent_failures),
                          window_sec=int(failure_window),
                          dominant_exit_code=int(dominant_exit)
                          if dominant_exit else None,
                          dominant_error=dominant_error or None)
            fingerprint = (f"{len(recent_failures)}:"
                           f"{recent_failures[-1][0]}")
            alert = _fire(entry, "job_failing_repeatedly", fingerprint, {
                "sensor": sensor, "signal": "job_failing_repeatedly",
                "severity": "medium",
                "title": f"job keeps failing: {label} "
                         f"({len(recent_failures)} failures inside "
                         f"the window, dominant exit "
                         f"{detail['dominant_exit_code']})",
                "detail": detail})
            if alert:
                alerts.append(alert)

        # Flakiness across the recent runs.
        recent = runs[-flaky_runs:] if flaky_runs > 0 else runs
        if len(recent) >= 4:
            outcomes = [r[1] == 0 for r in recent]
            transitions = sum(1 for a, b in zip(outcomes, outcomes[1:])
                              if a != b)
            if transitions >= max(1, flaky_transitions) \
                    and any(outcomes) and not all(outcomes):
                pattern = "".join("P" if ok else "F" for ok in outcomes)
                detail = dict(base_detail, pattern=pattern,
                              runs=len(recent),
                              transitions=transitions)
                alert = _fire(entry, "job_flaky", pattern, {
                    "sensor": sensor, "signal": "job_flaky",
                    "severity": "info",
                    "title": f"job is flaky: {label} "
                             f"(recent outcomes {pattern})",
                    "detail": detail})
                if alert:
                    alerts.append(alert)

        # Duration anomaly for runs folded this pass, judged
        # against the runs that came before each of them.
        for fkey, obs in fresh:
            if fkey != key:
                continue
            duration = obs.get("duration_sec")
            if not _is_number(duration):
                continue
            history = [r[2] for r in runs
                       if r[0] < obs["saved_at"] and r[2] is not None]
            anomalous, stats = score_duration(
                history, float(duration),
                min_baseline=min_baseline, z_limit=z_limit)
            if not anomalous:
                continue
            detail = dict(base_detail,
                          duration_sec=round(float(duration), 3),
                          baseline_median_sec=stats["median"],
                          baseline_mad_sec=stats["mad"],
                          baseline_runs=stats["baseline_runs"],
                          z=stats["z"])
            alert = _fire(entry, "job_duration_anomaly",
                          str(obs["job_id"]), {
                              "sensor": sensor,
                              "signal": "job_duration_anomaly",
                              "severity": "medium",
                              "title": f"job ran far longer than "
                                       f"its baseline: {label} "
                                       f"({_num(round(float(duration), 1))}s "
                                       f"against a "
                                       f"{_num(stats['median'])}s "
                                       f"median)",
                              "detail": detail})
            if alert:
                alerts.append(alert)

    # Failure cluster: distinct jobs failing close together.
    cluster_keys = sorted({key for key, entry in jobs.items()
                           if any(r[1] != 0
                                  and r[0] >= now - cluster_window
                                  for r in entry["runs"])})
    cluster_fingerprint = ""
    if len(cluster_keys) >= max(1, cluster_min):
        cluster_fingerprint = ",".join(cluster_keys)
        if state["cluster_fired"] != cluster_fingerprint:
            detail = {"jobs": cluster_keys,
                      "distinct_jobs": len(cluster_keys),
                      "window_sec": int(cluster_window)}
            alerts.append({
                "sensor": sensor, "signal": "failure_cluster",
                "severity": "high",
                "title": f"{len(cluster_keys)} distinct jobs failed "
                         f"inside {int(cluster_window)}s -- look "
                         f"at the box, not the jobs",
                "detail": detail})
    new_state = {"seen": seen, "jobs": jobs,
                 "cluster_fired": cluster_fingerprint}
    return alerts, new_state


# --- delivery and the main loop, in the Lab Results shape -------------

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
        print(f"job-watcher: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"job-watcher: no signing secret in ${args.secret_env}; "
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
            print(f"job-watcher: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"job-watcher: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Job Watcher extension watcher: read the "
                    "runner's retained job history once and file "
                    "sensor alert payloads for what the history "
                    "has taught it.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".job-watcher-state.json"),
                    help="state file (default: .job-watcher-state.json "
                         "next to this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the retained store (trying "
                         "the sense against known history, on any box)")
    ap.add_argument("--runner-dir", default=None,
                    help="runner base dir whose retained/ folder to "
                         "watch (wins over the runner_base_dir "
                         "tunable)")
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
        print(f"job-watcher: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"job-watcher: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    else:
        if args.runner_dir:
            manifest = dict(manifest)
            tunables = dict(_tunables(manifest))
            tunables["runner_base_dir"] = args.runner_dir
            manifest["tunables"] = tunables
        readings = read_live(manifest)
    if isinstance(readings, dict) and readings.get("truncated"):
        print(f"job-watcher: {readings['truncated']} retained "
              f"record(s) beyond max_records_per_pass were not read "
              f"this pass; the oldest fold in on a later pass",
              file=sys.stderr)
    state = _fresh_state()
    try:
        with open(args.state, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        pass
    alerts, state = decide(readings, manifest, state)
    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten, so the
            # next pass reports these jobs again.
            print(f"job-watcher: {len(alerts) - delivered} of "
                  f"{len(alerts)} alert(s) not delivered; state not "
                  f"saved, will retry next pass", file=sys.stderr)
            return 2
    else:
        for alert in alerts:
            print(json.dumps(alert, sort_keys=True))
    try:
        with open(args.state, "w", encoding="utf-8") as fh:
            json.dump(state, fh, sort_keys=True)
    except OSError as e:
        print(f"job-watcher: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
