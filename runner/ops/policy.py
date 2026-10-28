"""Result policy and sensor alert helpers.

Extracted from runner.py.
"""
import hashlib
import json
import os
import re
import socket
from datetime import datetime, timezone


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore


def apply_result_policy(cfg, job, exec_result, patterns, confined):
    """Return (result_dict, retain_bool). Job can never widen past owner ceiling."""
    R = _runner()
    if not isinstance(cfg, dict):
        cfg = {}
    if not isinstance(job, dict):
        job = {}
    if not isinstance(exec_result, dict):
        exec_result = {}
    if not isinstance(patterns, dict):
        patterns = {}
    policy = job.get("result_policy")
    if not isinstance(policy, dict):
        policy = {}
    requested = policy.get("view") or "full"
    ceiling = cfg.get("max_result_view") or "full"
    # A non-string view is bad data. .get on a dict key raises TypeError
    # and the job retried forever. An unrecognised string is the
    # documented default (PROTOCOL.md section 9: "Default: full"), not
    # a name that survives verbatim into the attested branch with the
    # output blanked -- the owner's ceiling below is what bounds a job,
    # so the default widens nothing the job could not ask for by name.
    if not isinstance(requested, str) or requested not in R.VIEW_ORDER:
        requested = "full"
    if not isinstance(ceiling, str):
        ceiling = "full"
    effective = requested if R.VIEW_ORDER.get(requested, 3) <= R.VIEW_ORDER.get(ceiling, 3) else ceiling
    stdout = exec_result.get("stdout")
    stderr = exec_result.get("stderr")
    full_out = R._as_text(stdout) + R._as_text(stderr)
    # Result digest, not a password hash. SHA-384 is the protocol.
    # codeql[py/weak-sensitive-data-hashing]
    digest = hashlib.sha384(full_out.encode("utf-8")).hexdigest()
    base = {
        "v": R.PROTOCOL_VERSION, "type": "result", "job_id": job.get("job_id"),
        "kind": job.get("kind"), "exit_code": exec_result.get("exit_code"),
        "timed_out": exec_result.get("timed_out", False),
        "duration_sec": exec_result.get("duration_sec"),
        "view": effective, "output_digest": digest,
    }
    if isinstance(exec_result.get("key_id"), str):
        # The key that verified the job, by name (Q94), rides every
        # view: a name, never a value.
        base["key_id"] = exec_result["key_id"]
    # Spec-required members (PROTOCOL result table): the exec
    # result carries both, and this rebuild must not drop them.
    # A caller that hands in a bare exec result gets them minted
    # here rather than emitting a result that lacks them.
    completed_at = exec_result.get("completed_at")
    if not (isinstance(completed_at, str) and completed_at):
        completed_at = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    base["completed_at"] = completed_at
    runner_name = exec_result.get("runner")
    if not (isinstance(runner_name, str) and runner_name):
        runner_name = socket.gethostname()
    base["runner"] = runner_name
    retain = effective != "full"
    if effective == "full":
        base.update({
            "stdout": exec_result.get("stdout"),
            "stderr": exec_result.get("stderr"),
            "stdout_truncated": exec_result.get("stdout_truncated", False),
            "stderr_truncated": exec_result.get("stderr_truncated", False),
        })
        if isinstance(exec_result.get("outputs"), list):
            base["outputs"] = exec_result["outputs"]
    elif effective == "redacted":
        out = full_out
        families = []
        for name, pat in patterns.items():
            if not isinstance(pat, str):
                continue
            try:
                if re.search(pat, out):
                    label = R._as_text(name) or "pattern"
                    out = re.sub(pat, "[REDACTED:" + label + "]", out)
                    families.append(label)
            except re.error:
                continue
        base.update({"stdout": out, "stderr": "", "redacted_families": families})
        _output_digests(base, exec_result)
    elif effective == "summary":
        try:
            ok_exit = exec_result.get("exit_code") == 0
        except Exception:
            ok_exit = False
        base.update({
            # The members say bytes, so they count UTF-8 octets, not
            # characters (Q98 item 19).
            "stdout_bytes": len(R._as_text(exec_result.get("stdout")).encode("utf-8", "replace")),
            "stderr_bytes": len(R._as_text(exec_result.get("stderr")).encode("utf-8", "replace")),
            "result_class": "ok" if ok_exit else "fail",
        })
        _output_digests(base, exec_result)
    else:  # attested
        base["attestations"] = R.build_attestations(
            (policy.get("queries") or []),
            {"exit_code": exec_result.get("exit_code"), "digest": digest, "confined": confined, "patterns": patterns,
             "text": full_out},
        )
        base["stdout"] = ""
        base["stderr"] = ""
    return base, retain


# What of an output entry leaves below the full view (PROTOCOL.md
# section 6): the name, the size and the SHA-384 of a file read, or
# the name and the reason (and the size, for too_large) of one not
# read. Nothing else: an entry is projected onto these, never
# filtered, so a member the collector never writes cannot carry the
# job's output past the view (Q106).
_OUTPUT_COMMITMENT = ("name", "size", "sha384", "omitted")
_OUTPUT_REASONS = ("missing", "too_large", "outside the workdir",
                   "not a regular file", "unreadable", "changed while read")


def _is_hex_digest(value):
    return isinstance(value, str) and len(value) == 96 \
        and all(c in "0123456789abcdef" for c in value.lower())


def output_commitment(entry):
    """The members of one output entry that leave below the full
    view, each only in its own shape: `name` text, `size` a count,
    `sha384` a hex digest, `omitted` one of the collector's reasons.
    A member in any other shape is not the collector's and stays."""
    out = {}
    name = entry.get("name")
    if isinstance(name, str):
        # A name the collector wrote passed the file-name rules as the
        # job named it; one that would not is not a name (Q106).
        try:
            if _runner().validate_file_name(name) == name:
                out["name"] = name
        except Exception:
            pass
    size = entry.get("size")
    if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
        out["size"] = size
    if _is_hex_digest(entry.get("sha384")):
        out["sha384"] = entry["sha384"].lower()
    if entry.get("omitted") in _OUTPUT_REASONS:
        out["omitted"] = entry["omitted"]
    return out


def _output_digests(base, exec_result):
    """Below the full view a file's bytes stay home: its name, size
    and SHA-384 leave, a commitment the SI can check later, never
    the content (no redaction pattern can scrub arbitrary bytes)."""
    outs = exec_result.get("outputs")
    if not isinstance(outs, list):
        return
    base["outputs"] = [output_commitment(o) for o in outs if isinstance(o, dict)]


def _sensor_alert_core(cfg, job, key_id, base_dir, dry=False, extra=None,
                       names=None):
    """Validate and file one sensor_alert job. The one ingest core.

    Every delivery path -- a mailed job (via _ingest_sensor_alert)
    and the local front-ends (via _ingest_local_envelope) -- files
    alerts through here, so the chain is identical by construction:
    senses shape checks, the sensor must exist and be enabled, the
    signing key must be the key bound to that sensor, the extension
    declared-signal gate, then the sense profile's own gates at
    store time.

    Returns (status, why, record):
      "stored"   -- filed; record is the stored alert dict.
      "dropped"  -- the sense profile dropped it; why says so.
      "rejected" -- refused; why says why. Nothing stored.
      "config"   -- the sensors config itself is broken (why is the
                    config error); the mail path logs this at ERROR.
      "dry"      -- dry run: validated, nothing stored.
    `extra` fields are merged into the stored record before filing
    (the local path marks its records source="local"). Never
    raises: bad sensor or extension data answers, it does not abort.
    """
    R = _runner()
    if R._senses is None:
        return ("rejected", "rejected: senses module unavailable", None)
    try:
        sensors = R._senses.parse_sensors(cfg)
    except RuntimeError as e:
        return ("config", str(e), None)
    bad = R._senses.validate_sensor_alert(job)
    if bad:
        return ("rejected", f"rejected: {bad}", None)
    name = job["sensor"]
    scfg = sensors.get(name)
    if not isinstance(scfg, dict):
        return ("rejected", f"rejected: unknown sensor {name!r}", None)
    if not scfg.get("enabled"):
        return ("rejected", f"rejected: sensor {name!r} is not enabled",
                None)
    # The binding names a key; the key answers under any of its
    # names (Q94), the sender's first.
    bound = None
    for candidate in (names if isinstance(names, (tuple, list)) and names
                      else (key_id,)):
        bound = R._senses.sensor_for_key(sensors, candidate)
        if bound is not None:
            break
    if bound != name:
        return ("rejected",
                f"rejected: key {key_id!r} is not bound to sensor {name!r}",
                None)
    # An extension-backed sense files DECLARED signals only. The
    # manifest is the contract: the Oracle receives the declaration
    # as context, so a signal nobody declared is refused here and
    # logged (via the caller), never stored and never passed through.
    manifest = R._extension_registry(cfg, base_dir).get(name)
    signal = job.get("signal")
    signal_description = None
    if manifest is not None:
        if not isinstance(signal, str) or not signal:
            return ("rejected",
                    f"rejected: sensor {name!r} is backed by extension "
                    f"{manifest.get('name')!r} v{manifest.get('version')}; "
                    f"alerts must name a declared signal", None)
        signal_description = R._extensions.signal_description(manifest, signal)
        if signal_description is None:
            declared = ", ".join(
                sorted(manifest.get("signal_descriptions") or {}))
            return ("rejected",
                    f"rejected: undeclared signal {signal!r} for extension "
                    f"{name!r} (declared: {declared})", None)
    if dry:
        return ("dry", "", None)
    alert = {
        "sensor": name,
        "severity": job.get("severity") or "info",
        "title": job["title"],
        "detail": job.get("detail") or {},
        "observed_at": job.get("observed_at"),
        "job_id_hint": job.get("job_id_hint"),
    }
    record = dict(alert)
    record.update({
        "received_at": R._senses._now_iso(),
        "key_id": key_id,
        "weight": scfg.get("weight", 1.0) if isinstance(scfg, dict) else 1.0,
    })
    if isinstance(signal, str) and signal:
        record["signal"] = signal
    if manifest is not None:
        # The extension's own version rides with the alert, so the
        # record shows which build of the extension filed it.
        record["extension"] = manifest.get("name")
        record["extension_version"] = manifest.get("version")
    if signal_description is not None:
        record["signal_description"] = signal_description
    if isinstance(extra, dict):
        record.update(extra)
    drop = R._senses.file_sensor_alert(base_dir, scfg, record)
    if drop:
        return ("dropped",
                f"dropped by profile: {drop} "
                f"({name}/{alert['severity']}: {alert['title']})", None)
    return ("stored",
            f"stored ({name}/{alert['severity']}: {alert['title']})",
            record)


