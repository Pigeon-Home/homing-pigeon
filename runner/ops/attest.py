"""Attestation and hot-config helpers.

Extracted from runner.py.
"""
import json
import os


def build_attestations(queries, ctx):
    atts = []
    if not isinstance(queries, list):
        return atts
    if not isinstance(ctx, dict):
        ctx = {}
    for q in queries:
        if not isinstance(q, dict):
            continue
        if q.get("op") != "attest":
            continue
        pred = q.get("predicate")
        # A predicate whose equality raises is unknown.
        def _is(name):
            try:
                return pred == name
            except Exception:
                return False
        if _is("exit_zero"):
            try:
                ok = ctx.get("exit_code") == 0
            except Exception:
                ok = False
            atts.append({"predicate": "exit_zero", "ok": ok})
        elif _is("no_secrets"):
            pats = ctx.get("patterns")
            if not isinstance(pats, dict):
                pats = {}
            # Non-string keys (poison from an extension) cannot be sorted
            # with strings. A key whose text form raises must not stop
            # the attestation.
            safe_items = []
            for k, v in pats.items():
                if not isinstance(v, str):
                    continue
                try:
                    key = k if isinstance(k, str) else str(k)
                except Exception:
                    key = "pattern"
                safe_items.append((key, v))
            text = ctx.get("text", "") if isinstance(ctx, dict) else ""
            atts.append({"predicate": pred,
                         "ok": not secret_scan(text, pats),
                         "patterns_sha384": hashlib.sha384(json.dumps(sorted(safe_items)).encode()).hexdigest()})
        elif _is("output_digest"):
            atts.append({"predicate": pred, "digest": ctx.get("digest")})
        elif _is("confined_to_workspace"):
            c = ctx.get("confined")
            if c is None:
                atts.append({"predicate": "confined_to_workspace", "ok": False,
                             "reason": "unconfigured"})
            else:
                try:
                    confined_ok = bool(c)
                except Exception:
                    confined_ok = False
                    c = None
                if c is None:
                    atts.append({"predicate": "confined_to_workspace", "ok": False,
                                 "reason": "unconfigured"})
                elif confined_ok:
                    atts.append({"predicate": "confined_to_workspace", "ok": True,
                                 "reason": None})
                else:
                    atts.append({"predicate": "confined_to_workspace", "ok": False,
                                 "reason": "violation_detected"})
        else:
            atts.append({"predicate": pred, "ok": False, "reason": "unknown"})
    return atts


def reload_hot_config(cfg: dict, path: str, state: dict,
                      pinned=None) -> list:
    """Apply hot keys from path if its mtime changed.

    state holds {"mtime": float}. pinned keys (set by CLI flags) are
    left alone. On a bad file, state is not advanced, so the next cycle
    retries the same mtime. Returns the keys that actually changed.
    """
    from runner import runner as R
    if not isinstance(cfg, dict) or not isinstance(path, str) or not path:
        return []
    if not isinstance(state, dict):
        state = {}
    pinned = set(pinned or ())
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return []
    if mtime == state.get("mtime"):
        return []
    # A bad file must not stop the cycle. Leave mtime alone so the
    # next poll retries the same file.
    try:
        fresh = load_config(path)
    except Exception:
        return []
    changed = []
    for key in HOT_KEYS:
        if key in pinned or key not in fresh:
            continue
        val = R._valid_hot(key, fresh[key])
        if val is None:
            val = HOT_DEFAULTS[key]
            log(f"config reload: invalid {key}={fresh[key]!r} reads as "
                f"the default {val}", "WARN")
        if val != cfg.get(key):
            cfg[key] = val
            changed.append(key)
    # The rest of the default class: a bad live value reads as the
    # documented default and is named, like the hot keys above.
    if R._defaulted is not None:
        for key in R._defaulted.defaulted_keys(fresh):
            if key in HOT_KEYS or key in pinned:
                continue
            val = R._defaulted.default_for(key)
            log(f"config reload: invalid {key}={fresh[key]!r} reads as "
                f"the default {val}", "WARN")
            if val != cfg.get(key):
                cfg[key] = val
                changed.append(key)
    for key in LIVE_KEYS:
        if key in pinned or key not in fresh:
            continue
        val = fresh[key]
        if key == "owner_instructions" and not isinstance(val, str):
            log(f"config reload: ignoring invalid {key}", "WARN")
            continue
        if key == "inference" and not isinstance(val, dict):
            log(f"config reload: ignoring invalid {key}", "WARN")
            continue
        if key == "oracle_mode" and not isinstance(val, str):
            log(f"config reload: ignoring invalid {key}", "WARN")
            continue
        if key == "verbose" and not isinstance(val, (bool, str)):
            log(f"config reload: ignoring invalid {key}", "WARN")
            continue
        if val != cfg.get(key):
            cfg[key] = val
            changed.append(key)
    state["mtime"] = mtime
    return changed


