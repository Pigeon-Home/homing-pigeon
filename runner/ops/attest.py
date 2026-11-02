"""Attestation and hot-config helpers.

Extracted from runner.py.
"""
import hashlib
import json
import os


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore


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
                         "ok": not _runner().secret_scan(text, pats),
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
    R = _runner()
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
        fresh = _runner().load_config(path)
    except Exception:
        return []
    _name_bad_refuse(fresh)
    changed = []
    for key in _runner().HOT_KEYS:
        if key in pinned or key not in fresh:
            continue
        val = R._valid_hot(key, fresh[key])
        if val is None:
            val = _runner().HOT_DEFAULTS[key]
            _runner().log(f"config reload: invalid {key}={fresh[key]!r} reads as "
                f"the default {val}", "WARN")
        if val != cfg.get(key):
            cfg[key] = val
            changed.append(key)
    # The rest of the default class: a bad live value reads as the
    # documented default and is named, like the hot keys above.
    if R._defaulted is not None:
        for key in R._defaulted.defaulted_keys(fresh):
            if key in _runner().HOT_KEYS or key in pinned:
                continue
            val = R._defaulted.default_for(key)
            _runner().log(f"config reload: invalid {key}={fresh[key]!r} reads as "
                f"the default {val}", "WARN")
            if val != cfg.get(key):
                cfg[key] = val
                changed.append(key)
    for key in _runner().LIVE_KEYS:
        if key in pinned or key not in fresh:
            continue
        val = fresh[key]
        if key == "owner_instructions" and not isinstance(val, str):
            _runner().log(f"config reload: ignoring invalid {key}", "WARN")
            continue
        if key == "inference" and not isinstance(val, dict):
            _runner().log(f"config reload: ignoring invalid {key}", "WARN")
            continue
        if key == "oracle_mode" and not isinstance(val, str):
            _runner().log(f"config reload: ignoring invalid {key}", "WARN")
            continue
        if key == "verbose" and not isinstance(val, (bool, str)):
            _runner().log(f"config reload: ignoring invalid {key}", "WARN")
            continue
        if val != cfg.get(key):
            cfg[key] = val
            changed.append(key)
    state["mtime"] = mtime
    return changed


def _name_bad_refuse(fresh):
    """A bad refuse-class value written live is named and not applied.

    Ports and key policies take effect at the next start. Until
    this read them, a bad value sat in the file and the log
    never said so.
    """
    if not isinstance(fresh, dict):
        return
    R = _runner()
    for key in ("imap_port", "smtp_port"):
        if key not in fresh:
            continue
        try:
            R._port({key: fresh[key]}, key, 1)
        except Exception as exc:
            R.log("config reload: refuse-class %s=%r is not applied (%s)"
                  % (key, fresh[key], exc), "ERROR")
    # The size caps are refuse-class too (stage 4 P6 finding
    # F1, the disposition's extension of this read): the same
    # validator the startup gauntlet uses names a bad one.
    try:
        cap_err = R._validate_size_caps(fresh)
    except Exception:
        cap_err = None
    if cap_err:
        R.log("config reload: refuse-class value is not applied (%s)"
              % cap_err, "ERROR")
    if "key_policies" not in fresh:
        return
    try:
        R.build_key_policies({"key_policies": fresh["key_policies"]})
    except Exception as exc:
        R.log("config reload: refuse-class key_policies is not applied (%s)"
              % exc, "ERROR")


