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
    if not isinstance(cfg, dict):
        raise RuntimeError("config error: config must be an object")
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
        try:
            clean_triggers["sensor_fused_score"] = {
                "threshold": float(sfs.get("threshold", 6.0)),
                "window_sec": float(sfs.get("window_sec", 600)),
            }
        except (TypeError, ValueError):
            raise RuntimeError(
                "config error: dri.triggers.sensor_fused_score "
                "threshold/window_sec must be numbers")
    for name in ("confinement_violation", "judge_block", "resource_pressure"):
        if triggers.get(name) is not None:
            clean_triggers[name] = bool(triggers[name])
    kp = triggers.get("key_probe")
    if kp is not None:
        if not isinstance(kp, dict):
            raise RuntimeError(
                "config error: dri.triggers.key_probe must be an object")
        try:
            clean_triggers["key_probe"] = {
                "threshold": int(kp.get("threshold", 5)),
                "window_sec": float(kp.get("window_sec", 3600)),
            }
        except (TypeError, ValueError):
            raise RuntimeError(
                "config error: dri.triggers.key_probe "
                "threshold/window_sec must be numbers")
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
    if not isinstance(base_dir, str) or not base_dir:
        return {}
    try:
        with open(os.path.join(base_dir, STATE_FILE), "r",
                  encoding="utf-8") as f:
            st = json.load(f)
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(base_dir, state):
    if not isinstance(base_dir, str) or not base_dir:
        return
    if not isinstance(state, dict):
        state = {}
    # Object keys and non-serializable values must not stop the page.
    clean = {}
    for k, v in state.items():
        if not isinstance(k, (str, int, float, bool)) or k is None:
            continue
        try:
            json.dumps(v)
            clean[k] = v
        except (TypeError, ValueError):
            clean[k] = str(v)
    try:
        tmp = os.path.join(base_dir, STATE_FILE + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(clean, f)
        os.replace(tmp, os.path.join(base_dir, STATE_FILE))
    except (OSError, TypeError, ValueError):
        pass
