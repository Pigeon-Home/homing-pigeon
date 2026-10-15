#!/usr/bin/env python3
"""Oracle senses: inbound signal extensions (host IDS, network monitor).

A sense is a named signal source that files signed alerts with the
Oracle. Each sense is adjustable from day one: an enable flag, a
weight (how much the Oracle weighs its alerts), and a free-form
profile of tunables. The runner enforces a small set of known profile
knobs; unknown keys are accepted and carried through so future
heuristics can be tuned without a code change.

Alerts arrive as signed jobs of kind "sensor_alert" from a key bound
to the sense (see key_policies: allowed_kinds ["sensor_alert"]). They
are validated, gated by the sense profile, stored, and never
executed. The "senses" query op reads them back, ranked by
weight x severity.

This module is deliberately free of runner imports: the crypto and
mail flow stay in runner.py, which calls in here.
"""
import json
import os
import threading
import time
from datetime import datetime, timezone

SEVERITY_SCORES = {
    "critical": 4.0,
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
    "info": 0.5,
}

SENSES_FILE = "senses.jsonl"
MAX_STORED = 5000


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        return None
    return dt


def parse_sensors(cfg) -> dict:
    """Validate cfg["sensors"]. Returns {name: cleaned config}.

    Raises RuntimeError on config error, mirroring build_key_policies.
    Unknown profile keys are kept: the profile is the operator's
    tuning surface for heuristics that do not exist yet.
    """
    raw = cfg.get("sensors") or {}
    if not isinstance(raw, dict):
        raise RuntimeError("config error: sensors must be an object")
    out = {}
    for name, scfg in raw.items():
        where = f"config error: sensors[{name!r}]"
        if not isinstance(name, str) or not name:
            raise RuntimeError("config error: sensor names must be strings")
        if not isinstance(scfg, dict):
            raise RuntimeError(where + " must be an object")
        enabled = scfg.get("enabled", False)
        if not isinstance(enabled, bool):
            raise RuntimeError(where + ".enabled must be a boolean")
        key_id = scfg.get("key_id") or ""
        if not isinstance(key_id, str) or not key_id:
            raise RuntimeError(where + ".key_id must be a non-empty string")
        try:
            weight = float(scfg.get("weight", 1.0))
        except (TypeError, ValueError):
            raise RuntimeError(where + ".weight must be a number")
        if weight < 0:
            raise RuntimeError(where + ".weight must be >= 0")
        profile = scfg.get("profile") or {}
        if not isinstance(profile, dict):
            raise RuntimeError(where + ".profile must be an object")
        clean_profile = dict(profile)
        floor = clean_profile.get("severity_floor", "info")
        if floor not in SEVERITY_SCORES:
            raise RuntimeError(
                where + f".profile.severity_floor must be one of "
                f"{sorted(SEVERITY_SCORES)}")
        for knob in ("cooldown_sec", "max_per_hour"):
            if knob in clean_profile:
                try:
                    v = float(clean_profile[knob])
                except (TypeError, ValueError):
                    raise RuntimeError(where + f".profile.{knob} must be a number")
                if v < 0:
                    raise RuntimeError(where + f".profile.{knob} must be >= 0")
                clean_profile[knob] = v
        out[name] = {
            "enabled": enabled,
            "key_id": key_id,
            "weight": weight,
            "profile": clean_profile,
        }
    # Two senses may not share a key: the key binds the daemon's identity.
    seen_keys = {}
    for name, scfg in out.items():
        kid = scfg["key_id"]
        if kid in seen_keys:
            raise RuntimeError(
                f"config error: key_id {kid!r} is bound to both "
                f"sensors[{seen_keys[kid]!r}] and sensors[{name!r}]")
        seen_keys[kid] = name
    return out


def sensor_for_key(sensors: dict, key_id: str):
    """Return the sensor name bound to key_id, or None."""
    for name, scfg in sensors.items():
        if scfg["key_id"] == key_id:
            return name
    return None


def validate_sensor_alert(job: dict):
    """Shape-check a kind=sensor_alert job. Returns None or a reason."""
    sensor = job.get("sensor")
    if not isinstance(sensor, str) or not sensor:
        return "sensor must be a non-empty string"
    severity = job.get("severity") or "info"
    if severity not in SEVERITY_SCORES:
        return f"severity must be one of {sorted(SEVERITY_SCORES)}"
    title = job.get("title")
    if not isinstance(title, str) or not title.strip():
        return "title must be a non-empty string"
    if "detail" in job and not isinstance(job["detail"], dict):
        return "detail must be an object"
    if "observed_at" in job and job["observed_at"] is not None \
            and _parse_ts(job["observed_at"]) is None:
        return "observed_at must be a UTC ISO timestamp"
    if "job_id_hint" in job and job["job_id_hint"] is not None \
            and not isinstance(job["job_id_hint"], str):
        return "job_id_hint must be a string"
    return None


def gate_alert(sensor_cfg: dict, alert: dict, recent: list, now: float = None):
    """Apply the sense profile's ingest gates.

    Returns None if the alert is kept, else a drop reason. `recent`
    is the sense's recent stored alerts (newest last), used for the
    cooldown and hourly cap.
    """
    now = time.time() if now is None else now
    profile = sensor_cfg.get("profile") or {}
    floor = profile.get("severity_floor", "info")
    if floor not in SEVERITY_SCORES:
        floor = "info"
    sev = alert.get("severity", "info")
    if sev not in SEVERITY_SCORES:
        sev = "info"
    if SEVERITY_SCORES[sev] < SEVERITY_SCORES[floor]:
        return f"below severity_floor {floor}"
    try:
        cooldown = float(profile.get("cooldown_sec") or 0)
    except (TypeError, ValueError):
        cooldown = 0
    if cooldown > 0:
        for prev in reversed(recent):
            pts = _parse_ts(prev.get("received_at"))
            if pts is None:
                continue
            if now - pts.timestamp() > cooldown:
                break
            if prev.get("title") == alert.get("title"):
                return f"cooldown: same title within {cooldown:g}s"
    cap = float(profile.get("max_per_hour") or 0)
    if cap > 0:
        n = 0
        for prev in reversed(recent):
            pts = _parse_ts(prev.get("received_at"))
            if pts is None:
                continue
            if now - pts.timestamp() > 3600:
                break
            n += 1
        if n >= cap:
            return f"over max_per_hour {cap:g}"
    return None


def _path(base_dir: str) -> str:
    return os.path.join(base_dir, SENSES_FILE)


_STORE_LOCK = threading.Lock()


def store_alert(base_dir: str, record: dict) -> None:
    """Append one alert record; keep the file capped at MAX_STORED lines.

    Concurrent senses must not tear a line or drop each other's alerts.
    """
    path = _path(base_dir)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _STORE_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return
        if len(lines) > MAX_STORED:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines[-MAX_STORED:])


def load_alerts(base_dir: str, sensor=None, severity_floor=None,
                since=None, until=None, limit=50):
    """Read stored alerts, oldest first, with optional filters."""
    path = _path(base_dir)
    with _STORE_LOCK:
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return []
    since_dt = _parse_ts(since) if since else None
    until_dt = _parse_ts(until) if until else None
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        if sensor and rec.get("sensor") != sensor:
            continue
        if severity_floor and SEVERITY_SCORES.get(rec.get("severity"), 0) < \
                SEVERITY_SCORES.get(severity_floor, 0):
            continue
        ts = _parse_ts(rec.get("observed_at") or rec.get("received_at"))
        if since_dt and (ts is None or ts < since_dt):
            continue
        if until_dt and (ts is None or ts > until_dt):
            continue
        out.append(rec)
    if limit is not None:
        out = out[-int(limit):]
    return out


def alert_score(alert: dict, weight: float) -> float:
    """How much the Oracle weighs this alert: source weight x severity."""
    try:
        weight_n = float(weight)
    except (TypeError, ValueError):
        weight_n = 1.0
    severity = alert.get("severity") if isinstance(alert, dict) else None
    score = SEVERITY_SCORES.get(severity, 0.5) if isinstance(severity, str) else 0.5
    return weight_n * score
