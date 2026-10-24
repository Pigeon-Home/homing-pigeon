#!/usr/bin/env python3
"""Training Watch: a Homing Pigeon user extension (example sense).

A sense for machine-learning training runs. Training jobs
run for hours on expensive hardware and fail in a small
number of well-known ways: the process dies on an exception
nobody is watching, the log goes quiet while the run is
supposedly alive, the loss stops improving long before the
schedule ends, the GPU cooks or runs out of memory headroom.
This watcher polls the three places those failures are
visible -- the run's log tail, the run's checkpoint
directory, and the GPU itself -- and files what it finds as
sensor alerts for the Oracle. It is a text parser and a
directory listing: no resident process, no model, nothing
learned, so it sits next to a local inference model without
contending with it.

Each alert names one of the signals declared in
extension.json:

- checkpoint_arrived (info)  a new checkpoint file
                    appeared in the run directory and has
                    STOPPED changing (the stabilization
                    rule, below)
- training_stalled (medium) one signal, two kinds of
                    evidence, named in the detail: the log
                    grew before and has produced nothing
                    new for stall_after_sec while the run
                    should be alive ("no_log_growth"), or
                    the last loss_points parsed losses are
                    flat or worsening within loss_flat_tol
                    ("loss_flat", always labeled
                    parsed-from-log)
- run_crashed (high) a crash marker -- a Python Traceback,
                    "CUDA out of memory", an NCCL error, a
                    RuntimeError -- in the newly read log
                    lines; once per marker episode (the
                    dedupe rule, below)
- gpu_overheating (high) GPU temperature at or over
                    gpu_temp_high_c (default 85C, the same
                    threshold discipline as Pi Health's
                    board limit)
- gpu_memory_pressure (medium) GPU memory at or over
                    gpu_mem_high_pct (default 95%) of the
                    card's total

The stabilization rule for checkpoints: a checkpoint is
identified by name + size + mtime. The first pass that sees
a file only records it; the alert files on the first later
pass that finds size and mtime unchanged -- a checkpoint
is announced when it has stopped being written, never
while it is still growing, so a half-written multi-GB
checkpoint never files. A filed checkpoint whose size or
mtime later changes (overwritten in place) goes back to
unfiled and must stabilize again.

The crash dedupe rule: episodes key on the marker plus a
line window -- the cumulative log line number divided by
crash_window_lines (default 100). A repeated traceback dump
spans consecutive lines inside one window and files once;
the same marker turning up windows later is a new episode
and files again.

The stall discipline: "no_log_growth" never fires on a log
that never started, and never on the first pass that sees
lines -- the log must have been seen growing on an earlier
pass and then go quiet for the full stall_after_sec. When
a status command is configured (--status-cmd or the
status_cmd tunable; exit 0 means the run is alive) and it
reports the run is over, quiet is expected and neither
stall variant fires. The loss variant needs at least
loss_points extractable losses; a log whose format the
loss regex cannot read simply never produces that variant
-- the no-growth variant and the crash markers still work.

The loss regex is deliberately conservative: it reads
"loss: 0.431", "loss=0.431", "train_loss: 1.2e-3" shapes
and nothing cleverer. Parsed losses are kept (last
loss_history, default 200) in the state file; they feed
the loss_flat variant ONLY, and the alert detail always
carries source: "parsed_from_log".

Sources, all optional and capability-based -- a source
that yields nothing has no vote and is never an error:

- GPU: `nvidia-smi --query-gpu=temperature.gpu,
  memory.used,memory.total,utilization.gpu
  --format=csv,noheader,nounits`, parsed in
  _read_gpu(). No GPU or no nvidia-smi: None.
- log: the log_path file, tailed incrementally (the
  _reader offsets ride in the state file, owned by
  main(), exactly as Log Sentinel's do). New lines are
  stamped with the log file's mtime: the watcher knows
  when the file last changed, not each line's birthday.
- checkpoints: a shallow scan of run_dir (the directory
  itself and its immediate subdirectories), basenames
  matched against the checkpoint_globs tunable.
- liveness: the configured status command's exit code;
  unconfigured or failing to run: None (no opinion).

The machinery is deliberately boring, in the family
shape. read_live() is the only function that touches the
machine (plus the reader helper it drives); decide() --
readings plus manifest plus last pass's state, out come
alerts and the new state -- is pure, so the whole
decision surface is testable off-hardware. Current time
arrives as readings["now"], never from a clock inside
decide().

Run on the same machine as the runner, it delivers
locally: --local-dir <runner base dir> signs each payload
with this sense's key (read from the environment variable
named by --secret-env) and drops it into the runner's
local inbox, or pushes it to the runner's loopback
listener when --local-port is given. Same envelope, same
signature -- only the transport differs
(docs/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line, and
signing and delivery follow the standard senses flow.

--samples FILE reads a readings dict from a JSON file
instead of the machine: the way to try the sense (and
test it) against known runs, on any box at all. A
samples file carries "now", "gpu" (an object with
temp_c / mem_used_mb / mem_total_mb / util_pct, or null),
"run_alive" (true/false/null), "log_lines" (a list of
{"ts", "line"} objects), and "checkpoints" (a list of
{"name", "size", "mtime"} objects).
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time

# The conservative loss shapes: "loss: 0.431", "loss=0.431",
# "train_loss: 1.2e-3". Nothing cleverer is attempted; a log
# in any other shape simply never yields the loss variant.
_LOSS_RE = re.compile(
    r"\b(?:train_)?loss\s*[:=]\s*"
    r"([0-9]+(?:\.[0-9]*)?(?:[eE][-+]?[0-9]+)?)",
    re.IGNORECASE)

# Crash markers: (label, predicate on one log line). The
# labels ride the alert detail, so they name the failure the
# way the log named it.
_CRASH_MARKERS = (
    ("Traceback", lambda line: "Traceback" in line),
    ("CUDA out of memory",
     lambda line: "CUDA out of memory" in line),
    ("NCCL error",
     lambda line: "NCCL" in line and "error" in line.lower()),
    ("RuntimeError", lambda line: "RuntimeError" in line),
)

_MAX_CRASH_EPISODES = 64
_DEFAULT_GLOBS = "checkpoint-*,*.pt,*.safetensors"


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


def _str_tunable(tunables, key, default=""):
    value = tunables.get(key)
    return value if isinstance(value, str) else default


# --- the live reads: the only platform-touching code -----------------

def _read_gpu():
    """One GPU sample from nvidia-smi, or None.

    The first GPU only (training runs of the shape this
    sense watches live on one card). No nvidia-smi, a
    timeout, or an unparsable line all read as None: this
    source has no vote on such a machine.
    """
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=temperature.gpu,memory.used,"
                  "memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    for line in (out.stdout or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            continue
        try:
            temp_c, used, total, util = (float(p) for p in parts)
        except ValueError:
            continue
        return {"temp_c": temp_c, "mem_used_mb": used,
                "mem_total_mb": total, "util_pct": util}
    return None


def _read_new_log_lines(path, reader_state, tail_bytes):
    """Read what is new in the training log, tail -f style.

    Returns (lines, newest_ts, new_reader_state): the new
    lines as text, the log file's mtime (the stamp every new
    line carries), and the advanced reader state. The rules
    are Log Sentinel's: the first sight of a file starts
    tail_bytes from the end; a new inode or a shrunken file
    restarts at the beginning of the tail; a missing file
    keeps its recorded offset and yields nothing. Never
    raises.
    """
    if not _is_number(tail_bytes) or tail_bytes <= 0:
        tail_bytes = 65536
    tail_bytes = int(tail_bytes)
    if not isinstance(reader_state, dict):
        reader_state = {}
    prev = reader_state.get(path)
    if not isinstance(prev, dict):
        prev = None
    try:
        info = os.stat(path)
    except OSError:
        return [], None, ({path: dict(prev)} if prev is not None
                          else {})
    inode, size = int(info.st_ino), int(info.st_size)
    mtime = float(info.st_mtime)
    offset = prev.get("offset") if prev else None
    if prev is None or not _is_number(offset):
        start = max(0, size - tail_bytes)
    elif int(prev.get("inode") or -1) != inode or size < offset:
        start = 0  # rotated (new inode) or truncated: restart
    else:
        start = int(offset)
    end = min(size, start + tail_bytes)
    entry = {"inode": inode, "offset": start}
    lines = []
    if end > start:
        try:
            with open(path, "rb") as fh:
                fh.seek(start)
                raw = fh.read(end - start)
        except OSError:
            return [], None, ({path: dict(prev)}
                              if prev is not None else {})
        lines = raw.decode("utf-8", errors="replace").splitlines()
        entry["offset"] = start + len(raw)
    else:
        entry["offset"] = end
    return lines, mtime, {path: entry}


def _scan_checkpoints(run_dir, globs):
    """Shallow-scan the run dir for checkpoint files.

    The directory itself and its immediate subdirectories;
    basenames matched against the glob list; symlinks not
    followed. Identity is the path relative to run_dir, so
    two runs' same-named checkpoints never collide.
    Returns a list of {"name", "size", "mtime"}.
    """
    found = []
    if not run_dir or not os.path.isdir(run_dir):
        return found
    dirs = [run_dir]
    try:
        for name in sorted(os.listdir(run_dir)):
            path = os.path.join(run_dir, name)
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    dirs.append(path)
            except OSError:
                continue
    except OSError:
        return found
    for folder in dirs:
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for name in names:
            if not any(fnmatch.fnmatchcase(name, glob)
                       for glob in globs):
                continue
            path = os.path.join(folder, name)
            try:
                if not os.path.isfile(path) or os.path.islink(path):
                    continue
                info = os.stat(path)
            except OSError:
                continue
            found.append({
                "name": os.path.relpath(path, run_dir),
                "size": int(info.st_size),
                "mtime": float(info.st_mtime)})
    return found


def _run_alive(status_cmd):
    """Exit-code liveness from the owner's status command.

    0 means the run is alive, nonzero means it is over, and
    an unconfigured command -- or one that cannot run at
    all -- has no opinion (None).
    """
    if not status_cmd:
        return None
    try:
        out = subprocess.run(status_cmd, shell=True,
                             capture_output=True, text=True,
                             timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.returncode == 0


def read_live(manifest, reader_state=None):
    """One live snapshot of the training run, as a readings dict.

    Returns {"now", "gpu", "log_lines", "run_alive",
    "checkpoints", "_reader"}: lines stamped with the log
    file's mtime, the advanced reader state riding under
    "_reader" for main() to store. A machine with none of
    the sources yields empty readings, never an exception.
    """
    tunables = _tunables(manifest)
    log_path = _str_tunable(tunables, "log_path")
    run_dir = _str_tunable(tunables, "run_dir")
    globs_text = _str_tunable(tunables, "checkpoint_globs",
                              _DEFAULT_GLOBS)
    globs = [g.strip() for g in globs_text.split(",") if g.strip()]
    lines, newest_ts, new_reader = [], None, {}
    if log_path:
        raw_lines, newest_ts, new_reader = _read_new_log_lines(
            log_path, reader_state,
            _tunable(tunables, "tail_bytes", 65536.0))
        lines = [{"ts": newest_ts, "line": line}
                 for line in raw_lines]
    return {
        "now": time.time(),
        "gpu": _read_gpu(),
        "log_lines": lines,
        "run_alive": _run_alive(_str_tunable(tunables,
                                             "status_cmd")),
        "checkpoints": _scan_checkpoints(run_dir, globs),
        "_reader": new_reader,
    }


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"checkpoints": {}, "gpu_active": {}, "log_seen": False,
            "log_newest_ts": None, "losses": [], "loss_flat": False,
            "stall_time_fired": "", "crash_fired": [],
            "lines_total": 0}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    checkpoints = {}
    raw = state.get("checkpoints")
    if isinstance(raw, dict):
        for name, entry in raw.items():
            if not isinstance(name, str) or not isinstance(entry, dict):
                continue
            size = entry.get("size")
            mtime = entry.get("mtime")
            if not _is_number(size) or not _is_number(mtime):
                continue
            checkpoints[name] = {
                "size": int(size), "mtime": float(mtime),
                "filed": bool(entry.get("filed"))}
    gpu_active = state.get("gpu_active")
    if not isinstance(gpu_active, dict):
        gpu_active = {}
    gpu_active = {k: v for k, v in gpu_active.items()
                  if isinstance(k, str) and isinstance(v, str)}
    losses = state.get("losses")
    if not isinstance(losses, list):
        losses = []
    losses = [float(v) for v in losses if _is_number(v)][-1000:]
    newest = state.get("log_newest_ts")
    crash_fired = state.get("crash_fired")
    if not isinstance(crash_fired, list):
        crash_fired = []
    crash_fired = [k for k in crash_fired
                   if isinstance(k, str)][-_MAX_CRASH_EPISODES:]
    lines_total = state.get("lines_total")
    fired = state.get("stall_time_fired")
    return {
        "checkpoints": checkpoints,
        "gpu_active": gpu_active,
        "log_seen": bool(state.get("log_seen")),
        "log_newest_ts": float(newest) if _is_number(newest) else None,
        "losses": losses,
        "loss_flat": bool(state.get("loss_flat")),
        "stall_time_fired": fired if isinstance(fired, str) else "",
        "crash_fired": crash_fired,
        "lines_total": int(lines_total) if _is_number(lines_total)
                       else 0,
    }


def _line_parts(entry, now):
    """One log_lines entry -> (ts, text); tolerant of shape drift."""
    if isinstance(entry, dict):
        text = entry.get("line")
        ts = entry.get("ts")
        return (float(ts) if _is_number(ts) else now,
                text if isinstance(text, str) else "")
    if isinstance(entry, str):
        return now, entry
    return now, ""


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time is
    readings["now"]. See the module docstring for the
    stabilization, dedupe, and stall rules this implements.
    """
    tunables = _tunables(manifest)
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "training_watch"
    now = readings.get("now")
    now = float(now) if _is_number(now) else 0.0
    stall_after = _tunable(tunables, "stall_after_sec", 1800.0)
    loss_points = int(_tunable(tunables, "loss_points", 5))
    if loss_points < 2:
        loss_points = 5
    loss_tol = _tunable(tunables, "loss_flat_tol", 0.01)
    loss_history = int(_tunable(tunables, "loss_history", 200))
    if loss_history < loss_points:
        loss_history = loss_points
    crash_window = int(_tunable(tunables, "crash_window_lines", 100))
    if crash_window < 1:
        crash_window = 100
    temp_high = _tunable(tunables, "gpu_temp_high_c", 85.0)
    mem_high = _tunable(tunables, "gpu_mem_high_pct", 95.0)
    max_checkpoints = int(_tunable(tunables, "max_checkpoints", 200))
    if max_checkpoints < 1:
        max_checkpoints = 200

    alerts = []
    alive = readings.get("run_alive")
    if not isinstance(alive, bool):
        alive = None

    # -- checkpoints: record on sight, file when stable ----
    observed = {}
    raw_ckpts = readings.get("checkpoints")
    if isinstance(raw_ckpts, list):
        for entry in raw_ckpts:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            size = entry.get("size")
            mtime = entry.get("mtime")
            if not isinstance(name, str) or not name \
                    or not _is_number(size) or not _is_number(mtime):
                continue
            observed[name] = {"size": int(size),
                              "mtime": float(mtime)}
    checkpoints = {}
    for name in sorted(observed):
        obs = observed[name]
        prev = state["checkpoints"].get(name)
        if prev is None:
            # First sight: record only. A checkpoint files
            # when it has stopped changing, and one pass is
            # not yet evidence of that.
            checkpoints[name] = dict(obs, filed=False)
            continue
        if prev["size"] != obs["size"] or prev["mtime"] != obs["mtime"]:
            checkpoints[name] = dict(obs, filed=False)
            continue
        if not prev["filed"]:
            detail = {"name": name, "size_bytes": obs["size"],
                      "mtime": obs["mtime"]}
            alerts.append({
                "sensor": sensor, "signal": "checkpoint_arrived",
                "severity": "info",
                "title": f"checkpoint settled: {name} "
                         f"({obs['size']} bytes)",
                "detail": detail})
            checkpoints[name] = dict(obs, filed=True)
        else:
            checkpoints[name] = dict(obs, filed=True)
    if len(checkpoints) > max_checkpoints:
        keep = sorted(checkpoints.items(),
                      key=lambda kv: kv[1]["mtime"])[-max_checkpoints:]
        checkpoints = dict(keep)

    # -- GPU: threshold conditions, pi-health discipline ----
    gpu_firing = {}
    gpu = readings.get("gpu")
    if isinstance(gpu, dict):
        temp = gpu.get("temp_c")
        if _is_number(temp) and temp >= temp_high:
            detail = {"temp_c": temp, "threshold_c": temp_high}
            gpu_firing["gpu_overheating"] = (
                json.dumps(detail, sort_keys=True),
                {"sensor": sensor, "signal": "gpu_overheating",
                 "severity": "high",
                 "title": f"GPU temperature {_num(temp)}C reached "
                          f"the {_num(temp_high)}C limit",
                 "detail": detail})
        used = gpu.get("mem_used_mb")
        total = gpu.get("mem_total_mb")
        if _is_number(used) and _is_number(total) and total > 0:
            pct = round(100.0 * used / total, 1)
            if pct >= mem_high:
                detail = {"mem_used_mb": used,
                          "mem_total_mb": total,
                          "mem_used_pct": pct,
                          "threshold_pct": mem_high}
                gpu_firing["gpu_memory_pressure"] = (
                    json.dumps(detail, sort_keys=True),
                    {"sensor": sensor,
                     "signal": "gpu_memory_pressure",
                     "severity": "medium",
                     "title": f"GPU memory {_num(pct)}% used "
                              f"(limit {_num(mem_high)}%)",
                     "detail": detail})
    gpu_active = {}
    for key in sorted(gpu_firing):
        fingerprint, alert = gpu_firing[key]
        gpu_active[key] = fingerprint
        if state["gpu_active"].get(key) != fingerprint:
            alerts.append(alert)

    # -- the log: losses, crash markers, growth -------------
    raw_lines = readings.get("log_lines")
    if not isinstance(raw_lines, list):
        raw_lines = []
    lines = [_line_parts(entry, now) for entry in raw_lines]
    prev_newest = state["log_newest_ts"]
    newest = prev_newest
    for ts, _text in lines:
        if newest is None or ts > newest:
            newest = ts
    log_seen = state["log_seen"] or bool(lines)

    losses = list(state["losses"])
    for _ts, text in lines:
        m = _LOSS_RE.search(text)
        if m:
            try:
                losses.append(float(m.group(1)))
            except ValueError:
                pass
    losses = losses[-loss_history:]

    crash_fired = list(state["crash_fired"])
    if lines:
        last_line = lines[-1][1][:200]
        for i, (_ts, text) in enumerate(lines):
            line_no = state["lines_total"] + i + 1
            window = line_no // crash_window
            for label, matches in _CRASH_MARKERS:
                if not matches(text):
                    continue
                episode = f"{label}:{window}"
                if episode in crash_fired:
                    continue
                crash_fired.append(episode)
                detail = {"marker": label, "line": text[:200],
                          "last_line": last_line,
                          "evidence": "log_marker"}
                alerts.append({
                    "sensor": sensor, "signal": "run_crashed",
                    "severity": "high",
                    "title": f"training run crashed: {label} "
                             f"in the log tail",
                    "detail": detail})
    crash_fired = crash_fired[-_MAX_CRASH_EPISODES:]
    lines_total = state["lines_total"] + len(lines)

    # -- stalls: one signal, two kinds of evidence ---------
    loss_flat = state["loss_flat"]
    if alive is not False:
        # Quiet-log evidence. The log must have been seen on
        # an earlier pass (prev_newest set) and brought no
        # new lines this pass; a log that never started, and
        # the first pass that sees one, can never fire this.
        if prev_newest is not None and not lines \
                and now - prev_newest >= stall_after:
            episode = repr(prev_newest)
            if state["stall_time_fired"] != episode:
                detail = {"evidence": "no_log_growth",
                          "silent_sec": int(now - prev_newest),
                          "stall_after_sec": int(stall_after),
                          "last_line_ts": prev_newest}
                alerts.append({
                    "sensor": sensor, "signal": "training_stalled",
                    "severity": "medium",
                    "title": f"training log silent for "
                             f"{int(now - prev_newest)}s "
                             f"(stall limit {int(stall_after)}s)",
                    "detail": detail})
                state["stall_time_fired"] = episode
        # Flat-loss evidence, edge-triggered: fires when the
        # last loss_points losses stop improving, stays
        # quiet while they stay flat, re-arms when a loss
        # improves past the tolerance.
        if len(losses) >= loss_points:
            window_losses = losses[-loss_points:]
            flat_now = min(window_losses) >= window_losses[0] - loss_tol
            if flat_now and not loss_flat:
                detail = {"evidence": "loss_flat",
                          "source": "parsed_from_log",
                          "losses": window_losses,
                          "points": loss_points,
                          "tolerance": loss_tol}
                alerts.append({
                    "sensor": sensor, "signal": "training_stalled",
                    "severity": "medium",
                    "title": f"training loss flat or worsening "
                             f"over the last {loss_points} "
                             f"points ({_num(window_losses[0])} "
                             f"to {_num(window_losses[-1])})",
                    "detail": detail})
            loss_flat = flat_now

    new_state = {
        "checkpoints": checkpoints,
        "gpu_active": gpu_active,
        "log_seen": log_seen,
        "log_newest_ts": newest,
        "losses": losses,
        "loss_flat": loss_flat,
        "stall_time_fired": state["stall_time_fired"],
        "crash_fired": crash_fired,
        "lines_total": lines_total,
    }
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
        print(f"training-watch: local delivery needs the "
              f"homing-pigeon repo importable ({e}); run me from "
              f"a clone", file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"training-watch: no signing secret in "
              f"${args.secret_env}; set it to this sense's key "
              f"secret", file=sys.stderr)
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
            print(f"training-watch: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"training-watch: filed {alert.get('signal')} "
              f"via {where}", file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Training Watch extension watcher: watch a "
                    "training run's log, checkpoints, and GPU "
                    "once and file sensor alert payloads for "
                    "what needs attention.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".training-watch-state.json"),
                    help="state file (default: "
                         ".training-watch-state.json next to "
                         "this script)")
    ap.add_argument("--samples", default=None,
                    help="read a readings dict from this JSON "
                         "file instead of the machine (trying "
                         "the sense against a known run, on any "
                         "box)")
    ap.add_argument("--log", default=None,
                    help="training log file to tail (wins over "
                         "the log_path tunable)")
    ap.add_argument("--run-dir", default=None,
                    help="run directory to scan for checkpoints "
                         "(wins over the run_dir tunable)")
    ap.add_argument("--status-cmd", default=None,
                    help="command whose exit code says whether "
                         "the run is alive (0 = alive; wins "
                         "over the status_cmd tunable)")
    ap.add_argument("--local-dir", default=None,
                    help="runner base dir: deliver alerts locally "
                         "(signed, into its local inbox) instead "
                         "of printing payloads")
    ap.add_argument("--local-port", type=int, default=None,
                    help="with --local-dir: push to the runner's "
                         "loopback listener on this port instead "
                         "of dropping files")
    ap.add_argument("--key-id", default="",
                    help="key id this sense signs as (its "
                         "sensors.<name>.key_id in the runner "
                         "config)")
    ap.add_argument("--secret-env", default="HOMING_PIGEON_SENSOR_SECRET",
                    help="environment variable holding the "
                         "signing secret (default: "
                         "HOMING_PIGEON_SENSOR_SECRET)")
    args = ap.parse_args(argv)
    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"training-watch: cannot read manifest "
              f"{args.manifest}: {e}", file=sys.stderr)
        return 2
    overrides = {}
    if args.log:
        overrides["log_path"] = args.log
    if args.run_dir:
        overrides["run_dir"] = args.run_dir
    if args.status_cmd:
        overrides["status_cmd"] = args.status_cmd
    if overrides:
        manifest = dict(manifest)
        tunables = dict(_tunables(manifest))
        tunables.update(overrides)
        manifest["tunables"] = tunables
    state = _fresh_state()
    try:
        with open(args.state, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        pass
    if args.samples:
        try:
            with open(args.samples, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"training-watch: cannot read samples "
                  f"{args.samples}: {e}", file=sys.stderr)
            return 2
        reader = state.get("_reader") if isinstance(state, dict) \
            else None
    else:
        reader = state.get("_reader") if isinstance(state, dict) \
            else None
        readings = read_live(manifest, reader)
        reader = readings.pop("_reader", None)
    alerts, state = decide(readings, manifest, state)
    if isinstance(reader, dict):
        state["_reader"] = reader
    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten, so
            # the next pass reports these conditions again.
            print(f"training-watch: {len(alerts) - delivered} of "
                  f"{len(alerts)} alert(s) not delivered; state "
                  f"not saved, will retry next pass",
                  file=sys.stderr)
            return 2
    else:
        for alert in alerts:
            print(json.dumps(alert, sort_keys=True))
    try:
        with open(args.state, "w", encoding="utf-8") as fh:
            json.dump(state, fh, sort_keys=True)
    except OSError as e:
        print(f"training-watch: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
