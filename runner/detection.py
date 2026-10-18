#!/usr/bin/env python3
"""Low-overhead detection gaps: rules, plan budgets, baseline, ATT&CK tags.

Canary tripwires already exist in runner._canary_watch and are left
alone. This module fills the remaining SELinux-like-cost pieces:

- Tiny Sigma/YARA-style rules over job payloads and outputs
- Explicit multi-step plan budgets / step limits
- Tiny statistical baseline with a conservative anomaly flag
- ATT&CK technique tagging helper

All optional, advisory, evaluated only at decision points.
No external dependencies.
"""
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Tiny Sigma/YARA-style rules
# ---------------------------------------------------------------------------

DEFAULT_RULES = [
    {
        "id": "suspicious_interpreter",
        "title": "Unexpected interpreter",
        "technique": "T1059",
        "match": {"interpreter": ["python2", "perl", "ruby"]},
    },
    {
        "id": "encoded_command",
        "title": "Possible encoded command in script",
        "technique": "T1027",
        "match": {"script_contains": ["base64", "eval(", "exec("]},
    },
    {
        "id": "high_output",
        "title": "Unusually large output",
        "technique": "T1041",
        "match": {"stdout_len_gt": 100000},
    },
]


def evaluate_rules(job: Dict[str, Any],
                   result: Optional[Dict[str, Any]] = None,
                   rules: Optional[List[Dict]] = None) -> List[Dict[str, Any]]:
    """Return matching rules. Evaluated only when called. Cheap.

    Supports interpreter exact match, substring in script, and
    stdout length threshold.
    """
    if not isinstance(job, dict):
        return []
    rules = rules if rules is not None else DEFAULT_RULES
    hits = []
    script = job.get("script") or ""
    if not isinstance(script, str):
        script = ""
    interpreter = job.get("interpreter")
    stdout = ""
    if isinstance(result, dict):
        stdout = result.get("stdout") or ""
        if not isinstance(stdout, str):
            stdout = ""
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        match = rule.get("match") or {}
        if not isinstance(match, dict):
            continue
        hit = False
        interps = match.get("interpreter")
        if isinstance(interps, list) and interpreter in interps:
            hit = True
        substrs = match.get("script_contains")
        if isinstance(substrs, list):
            for s in substrs:
                if isinstance(s, str) and s in script:
                    hit = True
                    break
        limit = match.get("stdout_len_gt")
        if isinstance(limit, int) and len(stdout) > limit:
            hit = True
        if hit:
            hits.append({
                "rule_id": rule.get("id"),
                "title": rule.get("title"),
                "technique": rule.get("technique"),
            })
    return hits


# ---------------------------------------------------------------------------
# Explicit multi-step plan budgets
# ---------------------------------------------------------------------------

def check_plan_budget(plan: List[Dict], cfg: Dict[str, Any]) -> Tuple[bool, str]:
    """Return (allowed, reason). Cheap counter check.

    cfg may contain max_plan_steps (default 8) and
    max_plan_timeout_sec (default 600).
    """
    if not isinstance(plan, list):
        return False, "plan must be a list"
    max_steps = 8
    max_timeout = 600
    if isinstance(cfg, dict):
        try:
            max_steps = int(cfg.get("max_plan_steps", 8))
        except (TypeError, ValueError, OverflowError):
            max_steps = 8
        try:
            max_timeout = int(cfg.get("max_plan_timeout_sec", 600))
        except (TypeError, ValueError, OverflowError):
            max_timeout = 600
    if len(plan) > max_steps:
        return False, f"plan has {len(plan)} steps (max {max_steps})"
    total = 0
    for step in plan:
        if not isinstance(step, dict):
            continue
        try:
            total += int(step.get("timeout_sec") or 60)
        except (TypeError, ValueError, OverflowError):
            total += 60
    if total > max_timeout:
        return False, f"plan timeout {total}s exceeds {max_timeout}s"
    return True, ""


# ---------------------------------------------------------------------------
# Tiny statistical baseline
# ---------------------------------------------------------------------------

def update_baseline(base_dir: str, job: Dict[str, Any],
                    result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Update a tiny rolling baseline. Returns the current baseline.

    Stores only counts and a few size samples. The file is mode 0600.
    A symlink at that path is not read and not written through.
    """
    if not isinstance(base_dir, str) or not base_dir:
        return {}
    path = os.path.join(base_dir, "detection-baseline.json")
    baseline = {"kinds": {}, "output_sizes": [], "updated": 0}
    if os.path.isfile(path) and not os.path.islink(path):
        try:
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                baseline = loaded
        except (OSError, ValueError):
            baseline = {"kinds": {}, "output_sizes": [], "updated": 0}
    if not isinstance(baseline, dict):
        baseline = {"kinds": {}, "output_sizes": [], "updated": 0}
    kind = "unknown"
    if isinstance(job, dict):
        raw_kind = job.get("kind")
        if isinstance(raw_kind, str) and raw_kind and "\x00" not in raw_kind:
            kind = raw_kind
    kinds = baseline.get("kinds")
    if not isinstance(kinds, dict):
        kinds = {}
    baseline["kinds"] = kinds
    try:
        kinds[kind] = int(kinds.get(kind, 0)) + 1
    except (TypeError, ValueError):
        kinds[kind] = 1
    if isinstance(result, dict):
        stdout = result.get("stdout") or ""
        if isinstance(stdout, str):
            sizes = baseline.get("output_sizes")
            if not isinstance(sizes, list):
                sizes = []
            kept = []
            for item in sizes:
                try:
                    kept.append(int(item))
                except (TypeError, ValueError):
                    continue
            kept.append(len(stdout))
            baseline["output_sizes"] = kept[-50:]
    baseline["updated"] = int(time.time())
    tmp = path + ".tmp." + str(threading.get_ident())
    fd = None
    try:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        fd = os.open(tmp, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None
            json.dump(baseline, f, allow_nan=False)
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except (OSError, TypeError, ValueError):
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return baseline


def baseline_anomaly(baseline: Dict[str, Any], job: Dict[str, Any],
                     result: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Return a short reason if this looks extreme, else None.

    Conservative: output > 10x median of recent samples, or a brand-new
    kind when many jobs have already been seen.
    """
    if not isinstance(baseline, dict):
        return None
    sizes = baseline.get("output_sizes") or []
    if isinstance(result, dict) and isinstance(sizes, list) and len(sizes) >= 10:
        stdout = result.get("stdout") or ""
        if isinstance(stdout, str):
            try:
                median = sorted(sizes)[len(sizes) // 2]
                if median > 0 and len(stdout) > 10 * median:
                    return "output_size_anomaly"
            except Exception:
                pass
    kinds = baseline.get("kinds") or {}
    if isinstance(kinds, dict) and sum(kinds.values()) > 20:
        kind = (job or {}).get("kind") or "unknown"
        if kind not in kinds:
            return "new_job_kind"
    return None


# ---------------------------------------------------------------------------
# ATT&CK tagging
# ---------------------------------------------------------------------------

def tag_alert(alert: Dict[str, Any], technique: str) -> Dict[str, Any]:
    """Attach an ATT&CK technique ID to an alert dict. Pure function."""
    if not isinstance(alert, dict):
        alert = {}
    alert = dict(alert)
    alert["technique"] = technique
    return alert
