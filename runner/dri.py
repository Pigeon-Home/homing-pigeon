#!/usr/bin/env python3
"""DRI playbook ("presence of mind"): outbound reach to the owner.

When fused signals cross adjustable thresholds, the Oracle pages the
owner. Advisory only: it pages, never remediates. The human decides.

Entry point: maybe_page(cfg, base_dir) — evaluates triggers, applies
per-trigger cooldown and digest batching, sends via the configured
channel, updates state. Safe to call every poll cycle; all state
persists in dri-state.json so restarts do not re-page.

Channels: telegram (implemented, Bot API over HTTPS). Signal and
WhatsApp are documented in docs/dri-playbook.md, not implemented.
No SMS, by owner decision.

This module imports senses (pure); the runner imports this module.
"""
import json
import os
import time
from datetime import datetime, timezone

try:
    from runner import senses as _senses
except ImportError:
    try:
        import senses as _senses
    except ImportError:
        _senses = None

STATE_FILE = "dri-state.json"
EVENTS_FILE = "security-events.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_ts(value):
    """ISO string or unix number -> float unix ts, or None."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        return None
    return dt.timestamp()


def parse_dri(cfg) -> dict:
    """Validate cfg["dri"]. Disabled by default. Raises RuntimeError."""
    raw = cfg.get("dri") or {}
    if not isinstance(raw, dict):
        raise RuntimeError("config error: dri must be an object")
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise RuntimeError("config error: dri.enabled must be a boolean")
    channel = raw.get("channel", "telegram")
    if channel not in ("telegram",):
        raise RuntimeError(
            "config error: dri.channel must be \"telegram\" "
            "(signal/whatsapp are spec-only)")
    triggers = raw.get("triggers") or {}
    if not isinstance(triggers, dict):
        raise RuntimeError("config error: dri.triggers must be an object")
    clean_triggers = {}
    sfs = triggers.get("sensor_fused_score")
    if sfs is not None:
        if not isinstance(sfs, dict):
            raise RuntimeError(
                "config error: dri.triggers.sensor_fused_score "
                "must be an object")
        clean_triggers["sensor_fused_score"] = {
            "threshold": float(sfs.get("threshold", 6.0)),
            "window_sec": float(sfs.get("window_sec", 600)),
        }
    for name in ("confinement_violation", "judge_block", "resource_pressure"):
        if triggers.get(name) is not None:
            clean_triggers[name] = bool(triggers[name])
    kp = triggers.get("key_probe")
    if kp is not None:
        if not isinstance(kp, dict):
            raise RuntimeError(
                "config error: dri.triggers.key_probe must be an object")
        clean_triggers["key_probe"] = {
            "threshold": int(kp.get("threshold", 5)),
            "window_sec": float(kp.get("window_sec", 3600)),
        }
    try:
        cooldown = float(raw.get("cooldown_sec", 3600))
        digest_window = float(raw.get("digest_window_sec", 300))
    except (TypeError, ValueError):
        raise RuntimeError("config error: dri cooldown/digest must be numbers")
    if cooldown < 0 or digest_window < 0:
        raise RuntimeError("config error: dri cooldown/digest must be >= 0")
    return {
        "enabled": enabled,
        "channel": channel,
        "telegram_bot_token": raw.get("telegram_bot_token") or "",
        "telegram_chat_id": raw.get("telegram_chat_id") or "",
        "triggers": clean_triggers,
        "cooldown_sec": cooldown,
        "digest_window_sec": digest_window,
    }


def _load_state(base_dir):
    try:
        with open(os.path.join(base_dir, STATE_FILE), "r",
                  encoding="utf-8") as f:
            st = json.load(f)
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(base_dir, state):
    try:
        tmp = os.path.join(base_dir, STATE_FILE + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, os.path.join(base_dir, STATE_FILE))
    except OSError:
        pass


def _recent_events(base_dir, since_ts):
    """security-events.jsonl entries newer than since_ts."""
    path = os.path.join(base_dir, EVENTS_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if not isinstance(ev, dict):
            continue
        ts = _to_ts(ev.get("at"))
        if ts is not None and ts >= since_ts:
            out.append(ev)
    return out


def _recent_retained(base_dir, since_ts):
    """Retained job results newer than since_ts: (job_id, payload)."""
    d = os.path.join(base_dir, "retained")
    try:
        names = os.listdir(d)
    except OSError:
        return []
    out = []
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, name), encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        ts = _to_ts(payload.get("saved_at"))
        if ts is not None and ts >= since_ts:
            out.append((payload.get("job_id") or name[:-5], payload))
    return out


def evaluate_page_triggers(dcfg, base_dir, since_ts, now=None):
    """Return [page events] for newly-tripped triggers.

    Each event: {"trigger", "at", "title", "detail", "signals"}.
    Pure evaluation: no sending, no state writes.
    """
    now = time.time() if now is None else now
    events = []
    trig = dcfg["triggers"]

    # Fused sensor score per sensor over the window.
    sfs = trig.get("sensor_fused_score")
    if sfs and _senses is not None:
        recs = _senses.load_alerts(base_dir, limit=5000)
        by_sensor = {}
        for rec in recs:
            ts = _to_ts(rec.get("observed_at") or rec.get("received_at"))
            if ts is None or now - ts > sfs["window_sec"]:
                continue
            by_sensor.setdefault(rec.get("sensor"), []).append(rec)
        for sensor, recs in by_sensor.items():
            total = 0.0
            for rec in recs:
                try:
                    total += _senses.alert_score(rec, rec.get("weight", 1.0))
                except (TypeError, ValueError):
                    continue
            if total >= sfs["threshold"]:
                def _one(rec):
                    try:
                        return _senses.alert_score(rec, rec.get("weight", 1.0))
                    except (TypeError, ValueError):
                        return 0.0
                top = sorted(recs, key=_one, reverse=True)[:3]
                events.append({
                    "trigger": "sensor_fused_score",
                    "at": _now_iso(),
                    "title": f"sensor fused score {total:.1f} "
                             f"on {sensor} (threshold {sfs['threshold']:.1f})",
                    "detail": f"{len(recs)} alerts in "
                              f"{sfs['window_sec']:.0f}s window",
                    "signals": [
                        f"{r.get('sensor')}/{r.get('severity')}: "
                        f"{r.get('title')}" for r in top],
                })

    # Boolean triggers from retained results and the event stream.
    if trig.get("confinement_violation") or trig.get("judge_block"):
        for job_id, payload in _recent_retained(base_dir, since_ts):
            if trig.get("confinement_violation") \
                    and payload.get("confined") is False:
                events.append({
                    "trigger": "confinement_violation",
                    "at": _now_iso(),
                    "title": f"confinement violation in job {job_id}",
                    "detail": "job wrote outside workspace_root",
                    "signals": [],
                })
            if trig.get("judge_block") and "judge blocked:" in str(
                    payload.get("stderr") or ""):
                events.append({
                    "trigger": "judge_block",
                    "at": _now_iso(),
                    "title": f"judge blocked job {job_id}",
                    "detail": str(payload.get("stderr") or "")[:200],
                    "signals": [],
                })

    kp = trig.get("key_probe")
    rp = trig.get("resource_pressure")
    if kp or rp:
        for ev in _recent_events(base_dir, since_ts):
            if rp and ev.get("type") == "resource_pressure":
                parts = []
                resources = ev.get("resources") if isinstance(ev.get("resources"), dict) else {}
                for k, v in resources.items():
                    try:
                        parts.append(f"{k}={float(v):.0%}")
                    except (TypeError, ValueError):
                        parts.append(f"{k}=?")
                try:
                    thr = float(ev.get("threshold", 0) or 0)
                except (TypeError, ValueError):
                    thr = 0.0
                events.append({
                    "trigger": "resource_pressure",
                    "at": ev.get("at") or _now_iso(),
                    "title": "resource pressure: " + ", ".join(parts),
                    "detail": f"over {thr:.0%} threshold",
                    "signals": [],
                })
        if kp:
            probes = [e for e in _recent_events(
                base_dir, now - kp["window_sec"])
                if e.get("type") == "auth_rejection"]
            if len(probes) >= kp["threshold"]:
                events.append({
                    "trigger": "key_probe",
                    "at": _now_iso(),
                    "title": f"{len(probes)} auth rejections in "
                             f"{kp['window_sec']:.0f}s",
                    "detail": "someone is knocking: bad signatures or "
                              "key-policy violations",
                    "signals": [],
                })
    return events


def format_page(events):
    """Render page events as one plain-text message."""
    lines = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        lines.append("homing-pigeon: " + str(ev.get("title") or ev.get("trigger") or "page"))
        if ev.get("detail"):
            lines.append(str(ev["detail"]))
        for sig in ev.get("signals") or []:
            lines.append(f"  - {sig}")
        lines.append("")
    lines.append("the Oracle took no action.")
    lines.append("ack by investigating; open the dashboard for the "
                 "full context.")
    return "\n".join(lines).strip()


def send_telegram(bot_token, chat_id, text):
    """POST one message via the Telegram Bot API. Returns True/False."""
    from urllib.request import Request, urlopen
    if not bot_token or not chat_id:
        return False
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = Request(f"https://api.telegram.org/bot{bot_token}/sendMessage",
                  data=payload,
                  headers={"Content-Type": "application/json"},
                  method="POST")
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception:
        return False


def _send(dcfg, text):
    if dcfg["channel"] == "telegram":
        return send_telegram(dcfg["telegram_bot_token"],
                             dcfg["telegram_chat_id"], text)
    return False


def _as_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def maybe_page(cfg, base_dir, now=None):
    """Evaluate triggers; page per cooldown/digest. Returns sent count."""
    now = time.time() if now is None else now
    try:
        dcfg = parse_dri(cfg)
    except RuntimeError:
        return 0
    if not dcfg["enabled"]:
        return 0
    state = _load_state(base_dir)
    since_ts = _as_float(state.get("last_check"), 0.0)
    if since_ts == 0:
        # First run: do not page for ancient history.
        state["last_check"] = now
        _save_state(base_dir, state)
        return 0
    # 1s overlap: event timestamps are whole seconds while the
    # cursor is a float; without it a same-second event is missed.
    # Re-scans are harmless: per-trigger cooldown suppresses dupes.
    events = evaluate_page_triggers(dcfg, base_dir, since_ts - 1.0, now)
    state["last_check"] = now

    # Per-trigger cooldown.
    last_page = state.get("last_page") or {}
    if not isinstance(last_page, dict):
        last_page = {}
    fresh = []
    for ev in events:
        if not isinstance(ev, dict) or not ev.get("trigger"):
            continue
        if now - _as_float(last_page.get(ev["trigger"]), 0.0) \
                >= dcfg["cooldown_sec"]:
            fresh.append(ev)
            last_page[ev["trigger"]] = now
    state["last_page"] = last_page

    # Digest batching.
    pending = state.get("pending_digest") or []
    if not isinstance(pending, list):
        pending = []
    pending.extend(fresh)
    digest_until = _as_float(state.get("digest_until"), 0.0)
    if fresh and digest_until == 0:
        digest_until = now + dcfg["digest_window_sec"]
    sent = 0
    if pending and (dcfg["digest_window_sec"] <= 0 or now >= digest_until):
        if _send(dcfg, format_page(pending)):
            sent = len(pending)
            pending = []
            digest_until = 0
    state["pending_digest"] = pending
    state["digest_until"] = digest_until
    _save_state(base_dir, state)
    return sent
