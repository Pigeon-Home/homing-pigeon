#!/usr/bin/env python3
"""The Oracle's self-learning loop: episodic, auditable, local.

The opinion machinery (runner/oracle/opinion.py) forms a call before a
job runs. This module closes the loop DRU asked for
(2026-10-19): when the job finishes, the call is compared with
what actually happened, the comparison is written to a local
ledger IMMEDIATELY, and the next job's opinion evaluation reads
the ledger fresh -- so a later job can be assessed, and where
the mode allows repaired, with the box's own history in view.

This is episodic learning, not model retraining: nothing here
touches a model's weights. What persists is a ledger of records
(oracle-learning.jsonl in the base dir):

- prediction: the frozen pre-execution call (job, digest, host,
  tier-1 findings, proposed repair, effective mode).
- reconciliation: the scored comparison (correct / incorrect /
  partial / no-prediction) plus the verified outcome facts.
- fact: a lesson derived by CODE from the execution record
  (an interpreter absent and the repair succeeding; a named
  tool missing and the job failing). Keyed by (host, feature),
  trusted, with a support count and last-seen time.
- candidate: a lesson the local MODEL distilled from an
  outcome, constrained to a validated schema. A candidate is
  a hypothesis: it is labeled uncorroborated wherever it
  surfaces, and it is promoted to corroborated only when
  later VERIFIED outcomes match what it expects
  (oracle_learning_promote_after, default 2, with no
  intervening contradiction). A contradiction retires it as
  negative evidence. Repetition of a claim is not
  corroboration; only a verified outcome counts.
- candidate_event: a corroboration / contradiction observation
  against a candidate.

Authority (the rule the design states and the tests pin): a
lesson never authorizes anything by itself. What a lesson may
do follows the opinion ladder -- off records and uses nothing;
diagnose records and explains; advise lets facts and labeled
candidates inform predictions; repair lets a corroborated
lesson SELECT among the existing mechanical repairs, and even
then only when the repair's preconditions are re-verified on
this job, on this host, now, and the repaired job is
re-judged as always. A candidate never drives a repair, and
no lesson lets the model invent a novel executable rewrite.

Poisoning discipline: raw job output is evidence, never
instruction. Facts are derived by code from verified probes
and outcomes, never from output text. Candidates pass a
schema check, and a claim phrased as an instruction ("ignore
previous instructions", "always approve", ...) is rejected
outright: a job cannot appoint itself the Oracle's teacher.

Host keying: every record carries the host fingerprint (the
hostname the results already name, hashed with the OS family),
so a lesson learned on one box never applies to another. A
fresh probe also supersedes a stale fact at use time: a
lesson that a tool was absent is not surfaced for a job where
the tool probes present today.

This module is free of runner imports, like opinion.py; the
runner owns file placement, model calls, and log lines. Every
write here is best-effort by contract with the caller: a
learning failure must never block or delay a job's result.
"""
import hashlib
import json
import os
import re
import threading

try:
    from runner.guard import atomicio as _atomicio
except ImportError:
    from guard import atomicio as _atomicio  # type: ignore
try:
    from runner.guard import confval as _confval
except ImportError:
    from guard import confval as _confval  # type: ignore
from datetime import datetime, timezone

LEDGER_FILE = "oracle-learning.jsonl"
LEDGER_MAX_LINES = 5000
LEDGER_KEEP_LINES = 4000
DEFAULT_PROMOTE_AFTER = 2
MAX_SURFACED = 4
_CLAIM_CAP = 240

_LOCK = threading.Lock()

_FEATURE_RE = re.compile(
    r"^(interpreter|tool|path|pathshape):[^\s:][^\n]{0,119}$")
_INSTRUCTION_RE = re.compile(
    r"(ignore (previous|prior|all) instructions|disregard .*"
    r"instructions|always approve|always trust|never verify|"
    r"skip verification|do not verify|you must|you should|"
    r"make sure to|from now on)",
    re.IGNORECASE)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _boolish(value, default):
    if value is None:
        return default
    if value is True or value == 1:
        return True
    if value is False or value == 0:
        return False
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "yes", "on", "1"):
            return True
        if text in ("false", "no", "off", "0"):
            return False
    return default


# ------------------------------------------------------------ settings

def learning_enabled(cfg):
    """oracle_learning: default on (whenever the opinion
    machinery is on); an explicit false turns the loop off."""
    if not isinstance(cfg, dict):
        return True
    return _boolish(cfg.get("oracle_learning"), True)


def learning_model_enabled(cfg):
    """oracle_learning_model: the model candidate channel's own
    opt-in, default off. (The runner additionally requires the
    opinion model tier to be enabled and inference configured,
    exactly as for tier-2 opinion notes.)"""
    if not isinstance(cfg, dict):
        return False
    return _boolish(cfg.get("oracle_learning_model"), False)


def promote_after(cfg):
    """oracle_learning_promote_after: verified corroborations a
    candidate needs before it carries weight. Default 2."""
    if not isinstance(cfg, dict):
        return DEFAULT_PROMOTE_AFTER
    # Not a count: a boolean (true once meant one corroboration),
    # infinity (once an OverflowError out of this reader), NaN, a
    # non-number, or anything under 1.
    return _confval.integer(cfg.get("oracle_learning_promote_after"),
                            DEFAULT_PROMOTE_AFTER, lo=1)


# ------------------------------------------------------------ host + features

def host_fingerprint(hostname, os_name):
    """Stable per-host key: the hostname the result record
    already carries, hashed with the OS family so the raw name
    is not what the ledger compares on."""
    raw = f"{hostname or ''}|{os_name or ''}"
    return hashlib.sha384(raw.encode("utf-8")).hexdigest()[:32]


def feature_keys(facts):
    """The negative features tier 1 can prove from live probes:
    an absent interpreter, a missing tool, a missing path, a
    foreign-shaped path. These are the keys facts and
    candidates are filed under."""
    keys = []
    if not isinstance(facts, dict):
        return keys
    interp = facts.get("interpreter") or []
    if not isinstance(interp, (list, tuple)):
        interp = []
    if interp and not facts.get("interpreter_present", True):
        keys.append("interpreter:" + str(interp[0]))
    tools = facts.get("tools") or {}
    if not isinstance(tools, dict):
        tools = {}
    for name, ok in tools.items():
        if not ok:
            keys.append("tool:" + str(name))
    paths = facts.get("paths") or {}
    if not isinstance(paths, dict):
        paths = {}
    for path, exists in paths.items():
        if exists is None:
            keys.append("pathshape:" + str(path))
        elif not exists:
            keys.append("path:" + str(path))
    return keys


def touched_keys(facts):
    """Every feature key this job touches, present or absent --
    the relevance universe for lesson lookup and for scoring a
    candidate against this job's verified outcome."""
    keys = set()
    if not isinstance(facts, dict):
        return keys
    interp = facts.get("interpreter") or []
    if isinstance(interp, (list, tuple)) and interp:
        keys.add("interpreter:" + str(interp[0]))
    tools = facts.get("tools") or {}
    if isinstance(tools, dict):
        for name in tools:
            keys.add("tool:" + str(name))
    paths = facts.get("paths") or {}
    if isinstance(paths, dict):
        for path in paths:
            keys.add("path:" + str(path))
            keys.add("pathshape:" + str(path))
    return keys


def feature_claim(feature):
    """The plain claim a feature key carries, for notes."""
    kind, _, value = str(feature).partition(":")
    if kind == "interpreter":
        return f"interpreter {value!r} is not present on this box"
    if kind == "tool":
        return f"tool {value!r} is not on PATH on this box"
    if kind == "path":
        return f"path {value!r} does not exist on this box"
    if kind == "pathshape":
        return (f"path {value!r} is shaped for a different "
                f"platform than this box")
    return str(feature)


# ------------------------------------------------------------ ledger io

def ledger_path(base_dir):
    if not isinstance(base_dir, str) or not base_dir:
        return None
    return os.path.join(base_dir, LEDGER_FILE)


def _append(base_dir, record):
    """Append one record. Returns True when written. Best
    effort is the caller's contract; this reports honestly."""
    path = ledger_path(base_dir)
    if path is None or not isinstance(record, dict):
        return False
    try:
        line = json.dumps(record, ensure_ascii=False,
                          allow_nan=False) + "\n"
    except (TypeError, ValueError):
        return False
    with _LOCK:
        try:
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            fd = os.open(path, flags, 0o600)
            try:
                os.write(fd, line.encode("utf-8"))
            finally:
                os.close(fd)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            _trim_locked(path)
        except OSError:
            return False
    return True


def _trim_locked(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return
    if len(lines) <= LEDGER_MAX_LINES:
        return
    try:
        _atomicio.write_text(path, "".join(lines[-LEDGER_KEEP_LINES:]))
    except OSError:
        pass


def read_records(base_dir):
    """Every parseable record in the ledger, oldest first.
    A torn final line is skipped, never fatal."""
    path = ledger_path(base_dir)
    if path is None:
        return []
    with _LOCK:
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return []
    out = []
    for line in lines[-LEDGER_MAX_LINES:]:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            out.append(record)
    return out


# ------------------------------------------------------------ folding

def load_state(base_dir, cfg=None):
    """Fold the ledger into current lesson state, read FRESH
    from disk on every call -- the freshness the loop promises
    the next job comes from there being no cached copy. With
    cfg, candidate promotion is applied to the folded state
    (promotion is derived from the event counts, never stored
    as its own claim)."""
    facts = {}
    candidates = {}
    for record in read_records(base_dir):
        rtype = record.get("type")
        host = record.get("host")
        if not isinstance(host, str):
            continue
        if rtype == "fact":
            feature = record.get("feature")
            if not isinstance(feature, str):
                continue
            entry = facts.setdefault((host, feature), {
                "feature": feature, "support": 0,
                "contradictions": 0, "last_seen": None,
                "last_job": None})
            if record.get("polarity") == "refute":
                entry["contradictions"] += 1
            else:
                entry["support"] += 1
            entry["last_seen"] = record.get("at")
            entry["last_job"] = record.get("job_id")
        elif rtype == "candidate":
            key = record.get("claim_key")
            if not isinstance(key, str):
                continue
            slot = (host, key)
            if slot in candidates:
                continue  # first birth wins; a rebirth resets nothing
            candidates[slot] = {
                "claim_key": key,
                "claim": record.get("claim"),
                "features": record.get("features") or [],
                "expects": record.get("expects"),
                "confidence": record.get("confidence"),
                "evidence_job": record.get("job_id"),
                "status": "candidate", "support": 0,
                "contradictions": 0, "last_seen": record.get("at")}
        elif rtype == "candidate_event":
            slot = (host, record.get("claim_key"))
            entry = candidates.get(slot)
            if entry is None or entry["status"] == "contradicted":
                continue
            if record.get("event") == "contradiction":
                entry["contradictions"] += 1
                entry["status"] = "contradicted"
            elif record.get("event") == "corroboration":
                entry["support"] += 1
            entry["last_seen"] = record.get("at")
    state = {"facts": facts, "candidates": candidates}
    if cfg is not None:
        _promote_check(state, cfg)
    return state


def _fact_status(entry):
    if entry["support"] >= 1 and entry["support"] > entry["contradictions"]:
        return "trusted"
    return "contested"


# ------------------------------------------------------------ prediction freeze

def prediction_record(job_id, digest, fingerprint, mode, verdict,
                      findings, features, repair, at=None):
    """The frozen pre-execution call, as one ledger record."""
    return {
        "type": "prediction",
        "at": at or _now(),
        "job_id": job_id,
        "received_digest": digest,
        "host": fingerprint,
        "mode": mode,
        "verdict": verdict,
        "findings": [{"kind": f.get("kind"), "detail": f.get("detail")}
                     for f in (findings or []) if isinstance(f, dict)],
        "features": list(features or []),
        "repair": repair,
    }


def freeze(base_dir, record):
    return _append(base_dir, record)


# ------------------------------------------------------------ reconciliation

def outcome_failed(outcome):
    if not isinstance(outcome, dict):
        return True
    if outcome.get("rejected") or outcome.get("timed_out"):
        return True
    code = outcome.get("exit_code")
    return not isinstance(code, int) or code != 0


def classify(frozen, outcome):
    """Score the frozen call against the verified outcome:
    correct / incorrect / partial / no-prediction."""
    if not isinstance(frozen, dict) or not frozen.get("verdict"):
        return "no-prediction"
    failed = outcome_failed(outcome)
    applied = bool(outcome.get("repair_applied"))
    if frozen["verdict"] == "likely_failure":
        if applied:
            return "partial" if failed else "correct"
        if outcome.get("repair_attempted") and outcome.get("rejected"):
            return "partial"
        return "correct" if failed else "incorrect"
    if frozen["verdict"] == "likely_success":
        return "incorrect" if failed else "correct"
    return "no-prediction"


def reconcile(base_dir, cfg, frozen, outcome, features,
              touched, job_id, fingerprint):
    """Write the reconciliation and everything it teaches.

    Appends the reconciliation record, one fact record per
    feature the job proved or refuted, and a candidate_event
    for every live candidate this job's verified outcome
    speaks to. Returns the reconciliation record, or None
    when the write failed (the caller logs and continues --
    learning never blocks a result).
    """
    scoring = classify(frozen, outcome)
    failed = outcome_failed(outcome)
    applied = bool(outcome.get("repair_applied"))
    repair_succeeded = None
    if outcome.get("repair_attempted") or applied:
        repair_succeeded = bool(applied and not failed)
    record = {
        "type": "reconciliation",
        "at": _now(),
        "job_id": job_id,
        "host": fingerprint,
        "classification": scoring,
        "predicted_verdict": (frozen or {}).get("verdict"),
        "outcome": {
            "exit_code": outcome.get("exit_code"),
            "timed_out": bool(outcome.get("timed_out")),
            "rejected": bool(outcome.get("rejected")),
            "repair_applied": applied,
            "repair_succeeded": repair_succeeded,
        },
        "lesson_selected": (frozen or {}).get("lesson_selected"),
    }
    if not _append(base_dir, record):
        return None
    # Verified facts: the features were live-probed; the
    # outcome says whether the problem claim held in practice.
    # A repaired run that succeeds confirms the interpreter
    # fact outright; a run that succeeds as sent refutes the
    # features it carried (the tool went unused, the path was
    # not needed); a failure supports them.
    for feature in features or []:
        if applied and not failed:
            polarity = "support"
        elif failed:
            polarity = "support"
        else:
            polarity = "refute"
        _append(base_dir, {
            "type": "fact", "at": record["at"], "host": fingerprint,
            "feature": feature, "polarity": polarity,
            "job_id": job_id})
    # Candidates: this job's VERIFIED outcome corroborates or
    # contradicts every live candidate whose features it touched.
    state = load_state(base_dir, cfg)
    for (host, _key), entry in sorted(state["candidates"].items()):
        if host != fingerprint or entry["status"] == "contradicted":
            continue
        overlap = [f for f in entry["features"] if f in (touched or set())]
        if not overlap:
            continue
        expects_failure = entry["expects"] == "failure"
        event = "corroboration" if expects_failure == failed \
            else "contradiction"
        _append(base_dir, {
            "type": "candidate_event", "at": record["at"],
            "host": fingerprint, "claim_key": entry["claim_key"],
            "event": event, "job_id": job_id})
    return record


def _promote_check(state, cfg):
    """Fold pass: mark candidates corroborated once support
    reaches the configured threshold with no contradiction."""
    need = promote_after(cfg)
    for entry in state["candidates"].values():
        if entry["status"] == "candidate" and entry["support"] >= need \
                and entry["contradictions"] == 0:
            entry["status"] = "corroborated"
    return state


# ------------------------------------------------------------ candidates

def claim_key(claim):
    raw = " ".join(str(claim).lower().split())
    return hashlib.sha384(raw.encode("utf-8")).hexdigest()[:16]


def validate_candidate(obj):
    """Validate a model-distilled candidate against the schema.

    Returns the normalized candidate dict, or None. The claim
    must be a bounded, single-line, declarative statement
    about the environment -- instruction-shaped text is
    rejected, because output is evidence, never instruction.
    """
    if not isinstance(obj, dict):
        return None
    if not set(obj) <= {"claim", "features", "expects", "confidence"}:
        return None
    claim = obj.get("claim")
    if not isinstance(claim, str):
        return None
    claim = " ".join(claim.split())
    if not claim or len(claim) > _CLAIM_CAP or "\n" in claim:
        return None
    if _INSTRUCTION_RE.search(claim) or "http" in claim.lower():
        return None
    features = obj.get("features")
    if not isinstance(features, list) or not features \
            or len(features) > 8:
        return None
    cleaned = []
    for feature in features:
        if not isinstance(feature, str) or not _FEATURE_RE.match(feature):
            return None
        if feature not in cleaned:
            cleaned.append(feature)
    expects = obj.get("expects")
    if expects not in ("failure", "success"):
        return None
    confidence = obj.get("confidence")
    if isinstance(confidence, bool) \
            or not isinstance(confidence, (int, float)) \
            or not 0 <= confidence <= 1:
        return None
    return {"claim": claim, "features": cleaned, "expects": expects,
            "confidence": float(confidence)}


def candidate_record(candidate, job_id, fingerprint, at=None):
    return {
        "type": "candidate",
        "at": at or _now(),
        "job_id": job_id,
        "host": fingerprint,
        "claim_key": claim_key(candidate["claim"]),
        "claim": candidate["claim"],
        "features": candidate["features"],
        "expects": candidate["expects"],
        "confidence": candidate["confidence"],
    }


def append_candidate(base_dir, record):
    return _append(base_dir, record)


# ------------------------------------------------------------ lesson lookup

def _fact_agrees(feature, claim_kind, facts):
    """Stale-fact supersession: when today's probe speaks about
    the feature, it wins over the ledger. Returns True only
    when the probe agrees (or does not speak)."""
    if not isinstance(facts, dict):
        return False
    interp = facts.get("interpreter") or []
    if not isinstance(interp, (list, tuple)):
        interp = []
    if claim_kind == "interpreter":
        if not interp or "interpreter:" + str(interp[0]) != feature:
            return False
        return not facts.get("interpreter_present", True)
    if claim_kind == "tool":
        name = feature.split(":", 1)[1]
        tools = facts.get("tools") or {}
        if not isinstance(tools, dict) or name not in tools:
            return False
        return not tools[name]
    if claim_kind == "path":
        path = feature.split(":", 1)[1]
        paths = facts.get("paths") or {}
        if not isinstance(paths, dict) or path not in paths:
            return False
        return paths[path] is False
    if claim_kind == "pathshape":
        path = feature.split(":", 1)[1]
        paths = facts.get("paths") or {}
        if not isinstance(paths, dict) or path not in paths:
            return False
        return paths[path] is None
    return False


def relevant_lessons(state, cfg, fingerprint, facts):
    """Lessons that speak to THIS job, on THIS host, filtered
    by today's probes and bounded. Promotion is applied here
    so callers always see the folded status."""
    state = _promote_check(state, cfg)
    touched = touched_keys(facts)
    facts_out = []
    for (host, feature), entry in sorted(state["facts"].items()):
        if host != fingerprint or feature not in touched:
            continue
        if _fact_status(entry) != "trusted":
            continue
        kind = feature.split(":", 1)[0]
        if not _fact_agrees(feature, kind, facts):
            continue
        facts_out.append({
            "feature": feature, "claim": feature_claim(feature),
            "support": entry["support"],
            "contradictions": entry["contradictions"],
            "last_seen": entry["last_seen"], "status": "trusted"})
    corroborated = []
    candidates = []
    for (host, _key), entry in sorted(state["candidates"].items()):
        if host != fingerprint or entry["status"] == "contradicted":
            continue
        if not any(f in touched for f in entry["features"]):
            continue
        item = {
            "claim_key": entry["claim_key"], "claim": entry["claim"],
            "features": entry["features"], "expects": entry["expects"],
            "support": entry["support"],
            "contradictions": entry["contradictions"],
            "status": entry["status"]}
        if entry["status"] == "corroborated":
            corroborated.append(item)
        else:
            candidates.append(item)
    return {"facts": facts_out[:MAX_SURFACED],
            "corroborated": corroborated[:MAX_SURFACED],
            "candidates": candidates[:MAX_SURFACED]}


def lesson_notes(relevant):
    """Bounded note sentences for an opinion member. Facts
    state their support; model lessons carry their status in
    the sentence -- a candidate is labeled uncorroborated
    wherever it surfaces."""
    notes = []
    for fact in (relevant or {}).get("facts", []):
        notes.append(
            f"Learned on this box (verified in "
            f"{fact['support']} prior job(s)): {fact['claim']}.")
    for item in (relevant or {}).get("corroborated", []):
        notes.append(
            f"Learned on this box (model lesson, corroborated "
            f"by {item['support']} verified outcome(s)): "
            f"{item['claim']}.")
    for item in (relevant or {}).get("candidates", []):
        notes.append(f"Uncorroborated lesson: {item['claim']}.")
    return notes[:MAX_SURFACED]


def lesson_selects(relevant, repair_features):
    """The corroborated lesson that selects among the existing
    mechanical repairs, or None. Only a corroborated lesson
    may select; a candidate never drives a repair, and the
    selection confers no authority -- the caller still
    re-verifies preconditions and re-judges."""
    wanted = set(repair_features or [])
    for item in (relevant or {}).get("corroborated", []):
        if wanted.intersection(item["features"]):
            return item
    return None
