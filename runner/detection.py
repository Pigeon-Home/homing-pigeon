#!/usr/bin/env python3
"""Low-overhead detection helpers for the Homing Pigeon runner.

Inspired by the open detection backbone (Sigma/YARA-style rules,
ATT&CK tagging, canary tripwires, hard budgets, and a tiny
statistical baseline). All pieces are optional, advisory by default,
and designed for SELinux-like cost: evaluated only at decision
points, near-zero idle overhead.

No external dependencies. Safe to import even if the rest of the
runner is partially broken.
"""
import hashlib
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Canary tripwires
# ---------------------------------------------------------------------------

def plant_canary(base_dir: str, name: str, content: str = "CANARY") -> str:
    """Write a canary file. Returns the path. Low cost: one write."""
    if not isinstance(base_dir, str) or not base_dir:
        return ""
    d = os.path.join(base_dir, "canaries")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def check_canaries(base_dir: str) -> List[Dict[str, Any]]:
    """Return a list of tripped canaries (missing or content changed).

    Expected state is stored next to the canaries as .expected.json.
    Near-zero cost when nothing has changed.
    """
    if not isinstance(base_dir, str) or not base_dir:
        return []
    d = os.path.join(base_dir, "canaries")
    if not os.path.isdir(d):
        return []
    expected_path = os.path.join(d, ".expected.json")
    expected = {}
    if os.path.exists(expected_path):
        try:
            with open(expected_path, encoding="utf-8") as f:
                expected = json.load(f)
        except Exception:
            expected = {}
    tripped = []
    for name in os.listdir(d):
        if name.startswith("."):
            continue
        path = os.path.join(d, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            digest = hashlib.sha256(content.encode()).hexdigest()
        except OSError:
            continue
        prior = expected.get(name)
        if prior and prior != digest:
            tripped.append({
                "canary": name,
                "path": path,
                "reason": "content_changed",
                "technique": "T1070.004",  # File Deletion / Indicator Removal
            })
        expected[name] = digest
    try:
        with open(expected_path, "w", encoding="utf-8") as f:
            json.dump(expected, f)
    except OSError:
        pass
    return tripped


# ---------------------------------------------------------------------------
# Simple Sigma/YARA-style rules (payload / output matching)
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


def evaluate_rules(job: Dict[str, Any], result: Optional[Dict[str, Any]] = None,
                   rules: Optional[List[Dict]] = None) -> List[Dict[str, Any]]:
    """Return list of matching rules. Evaluated only when called.

    Supports a tiny subset: interpreter exact match, substring in
    script, and stdout length threshold. Designed to be cheap.
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
# Hard budgets / step limits (for multi-step plans)
# ---------------------------------------------------------------------------

def check_plan_budget(plan: List[Dict], cfg: Dict[str, Any]) -> Tuple[bool, str]:
    """Return (allowed, reason). Cheap counter check.

    cfg may contain:
      max_plan_steps (default 8)
      max_plan_timeout_sec (default 600)
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
# Tiny statistical baseline (job kinds, output sizes)
# ---------------------------------------------------------------------------

def update_baseline(base_dir: str, job: Dict[str, Any],
                    result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Update a tiny rolling baseline. Returns the current baseline.

    Stores only counts and a few size samples. File is small.
    """
    if not isinstance(base_dir, str) or not base_dir:
        return {}
    path = os.path.join(base_dir, "detection-baseline.json")
    baseline = {"kinds": {}, "output_sizes": [], "updated": 0}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                baseline = json.load(f)
        except Exception:
            baseline = {"kinds": {}, "output_sizes": [], "updated": 0}
    if not isinstance(baseline, dict):
        baseline = {"kinds": {}, "output_sizes": [], "updated": 0}
    kind = (job or {}).get("kind") or "unknown"
    kinds = baseline.setdefault("kinds", {})
    if not isinstance(kinds, dict):
        kinds = {}
        baseline["kinds"] = kinds
    kinds[kind] = kinds.get(kind, 0) + 1
    if isinstance(result, dict):
        stdout = result.get("stdout") or ""
        if isinstance(stdout, str):
            sizes = baseline.setdefault("output_sizes", [])
            if not isinstance(sizes, list):
                sizes = []
                baseline["output_sizes"] = sizes
            sizes.append(len(stdout))
            if len(sizes) > 50:
                baseline["output_sizes"] = sizes[-50:]
    baseline["updated"] = int(time.time())
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(baseline, f)
    except OSError:
        pass
    return baseline


def baseline_anomaly(baseline: Dict[str, Any], job: Dict[str, Any],
                     result: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Return a short reason string if this looks extreme, else None.

    Very conservative: only flags output > 10x the median of recent
    samples, or a brand-new kind when many jobs have already been seen.
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
# ATT&CK tagging helper
# ---------------------------------------------------------------------------

def tag_alert(alert: Dict[str, Any], technique: str) -> Dict[str, Any]:
    """Attach an ATT&CK technique ID to an alert dict. Pure function."""
    if not isinstance(alert, dict):
        alert = {}
    alert = dict(alert)
    alert["technique"] = technique
    return alert
