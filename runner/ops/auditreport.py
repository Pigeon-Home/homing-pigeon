#!/usr/bin/env python3
"""--audit-report: summarize the security audit log.

Read-only. No mailbox access, no network, never writes to
config.json. Works with a config that has no mailbox credentials.

Output: a table (feature, mode, evaluated, would-deny, reasons),
per-key suggestions, suggested key_policies fragments (audit2allow),
and a "refused to suggest" section. Dangerous env names and URL file
sources are never suggested.
"""
import calendar
import json
import os
import re
import sys
import time

try:
    from runner.guard import security as _security
except ImportError:  # running from inside runner/ as __main__
    try:
        from guard import security as _security
    except ImportError:
        _security = None


def parse_since(value):
    """Parse '14d' or '48h' into seconds. Returns None when omitted."""
    if value is None:
        return 30 * 24 * 3600
    m = re.fullmatch(r"(\d+)([dh])", value.strip())
    if not m:
        raise ValueError(
            "bad --since value %r: use like 14d or 48h" % (value,))
    n = int(m.group(1))
    return n * (24 * 3600 if m.group(2) == "d" else 3600)


def _read_entries(base_dir):
    """Read security-audit.jsonl and its .1 rollover. Never raises."""
    entries = []
    if _security is None:
        return entries
    for name in (_security.AUDIT_FILE, _security.AUDIT_ROLLED_FILE):
        path = os.path.join(base_dir, name)
        if os.path.islink(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(e, dict):
                        entries.append(e)
        except OSError:
            continue
    return entries


def _entry_ts(entry):
    ts = entry.get("ts")
    if not isinstance(ts, str):
        return 0
    try:
        # The stored ts is UTC ("Z"); timegm reads it as UTC.
        # time.mktime read it as LOCAL time, which shifted every
        # entry by the host's UTC offset: on a host ahead of UTC
        # (e.g. Pacific/Kiritimati) fresh entries fell outside
        # the report window and the report came back empty, and
        # on a host behind UTC stale entries leaked in. CI runs
        # on UTC, where the two agree, so only a TZ-varied run
        # could see it.
        return calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, OverflowError):
        return 0


def _dangerous_names():
    if _security is not None:
        return _security.DANGEROUS_ENV_NAMES
    return frozenset()


def _looks_like_url(name):
    return isinstance(name, str) and (
        name.startswith("http://") or name.startswith("https://"))


def _is_dangerous(name):
    if _security is not None and hasattr(_security, "is_dangerous_env_name"):
        try:
            return bool(_security.is_dangerous_env_name(name))
        except Exception:
            pass
    names = _dangerous_names()
    return isinstance(name, str) and name.upper() in names


def _env_name_in_detail(detail):
    m = re.search(r"env '([^']+)'", detail or "")
    return m.group(1) if m else ""


def _file_name_in_detail(detail):
    m = re.search(r"file '([^']+)'", detail or "")
    return m.group(1) if m else ""


def build_fragments(per_key):
    """key_id -> (fragment dict, counts) for the audit2allow section.

    Only findings that would block a legitimate job (would_deny in
    audit mode, denied in enforce) contribute. Dangerous env names are
    never suggested — they belong in the refused section.
    Returns {kid: {"fragment": {...}, "env_counts": {...},
                   "file_counts": {...}, "arg_reasons": {...}}}.
    """
    out = {}
    for kid, es in sorted(per_key.items()):
        env_counts = {}
        file_counts = {}
        arg_reasons = {}
        for e in es:
            if e.get("decision") not in ("would_deny", "denied"):
                continue
            r = e.get("reason", "?")
            detail = e.get("detail") or ""
            if r == "env_not_allowed":
                name = _env_name_in_detail(detail)
                if name and not _is_dangerous(name):
                    env_counts[name] = env_counts.get(name, 0) + 1
            elif r == "file_not_allowed":
                name = _file_name_in_detail(detail)
                if name and not _looks_like_url(name):
                    file_counts[name] = file_counts.get(name, 0) + 1
            elif r in ("arg_pattern_mismatch", "args_too_many",
                       "arg_too_long"):
                arg_reasons[r] = arg_reasons.get(r, 0) + 1
        fragment = {}
        if env_counts:
            fragment["allowed_env"] = sorted(env_counts)
        if file_counts:
            fragment["allowed_files"] = sorted(file_counts)
        if fragment or arg_reasons:
            out[kid] = {"fragment": fragment,
                        "env_counts": env_counts,
                        "file_counts": file_counts,
                        "arg_reasons": arg_reasons}
    return out


def _read_counts(base_dir):
    path = os.path.join(base_dir, "security-audit-counts.json")
    if os.path.islink(path):
        return {}
    try:
        with open(os.path.join(base_dir, "security-audit-counts.json"),
                  encoding="utf-8") as fh:
            counts = json.load(fh)
        return counts if isinstance(counts, dict) else {}
    except (OSError, ValueError):
        return {}


def build_report(cfg, base_dir, since_secs, key=None, feature=None):
    """Return (table_rows, suggestions, refused, fragments).

    table_rows: [(feature, mode, evaluated, would_deny, reasons_str)]
    sorted by would_deny desc. suggestions: [str]. refused: [str].
    fragments: build_fragments() output for the audit2allow section.
    key/feature filter entries by key_id / feature when given.
    """
    now = time.time()
    entries = [e for e in _read_entries(base_dir)
               if now - _entry_ts(e) <= since_secs]
    if key is not None:
        want = "" if key == "(default)" else key
        entries = [e for e in entries if (e.get("key_id") or "") == want]
    if feature is not None:
        entries = [e for e in entries if e.get("feature") == feature]

    counts = _read_counts(base_dir)
    sec = cfg.get("security") if isinstance(cfg, dict) else None
    sec = sec if isinstance(sec, dict) else {}
    modes_cfg = sec.get("modes") if isinstance(sec.get("modes"), dict) else {}
    by_feature = {}
    for e in entries:
        f = e.get("feature", "?")
        info = by_feature.setdefault(
            f, {"would_deny": 0, "reasons": {}, "modes": set()})
        if e.get("decision") == "would_deny":
            info["would_deny"] += 1
        r = e.get("reason", "?")
        info["reasons"][r] = info["reasons"].get(r, 0) + 1
        m = e.get("mode") or modes_cfg.get(f) or "?"
        info["modes"].add(m)

    table_rows = []
    for f, info in sorted(by_feature.items(),
                          key=lambda kv: (-kv[1]["would_deny"], kv[0])):
        evaluated = 0
        feat_counts = counts.get(f)
        if isinstance(feat_counts, dict):
            evaluated = int(feat_counts.get("evaluated") or 0)
        mode = "/".join(sorted(info["modes"]))
        reasons = " ".join("%s(%d)" % (r, n) for r, n in sorted(
            info["reasons"].items(), key=lambda kv: -kv[1])) or "-"
        table_rows.append((f, mode, evaluated, info["would_deny"],
                           reasons))

    per_key = {}
    for e in entries:
        kid = e.get("key_id") or "(default)"
        per_key.setdefault(kid, []).append(e)

    suggestions = []
    refused = []

    # Suggestion 1: additional keys with no policy entry.
    extra = cfg.get("additional_secrets") or {}
    policies = cfg.get("key_policies") or {}
    if isinstance(extra, dict) and isinstance(policies, dict):
        for kid in extra:
            if kid and kid not in policies:
                suggestions.append(
                    'key "%s" holds an additional secret with no '
                    'key_policies entry: consider adding one '
                    "(see SECURITY.md)" % kid)

    # Suggestion 2: repeated audit findings per key.
    for kid, es in sorted(per_key.items()):
        reasons = {}
        for e in es:
            if e.get("decision") == "would_deny":
                r = e.get("reason", "?")
                reasons[r] = reasons.get(r, 0) + 1
        for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
            detail = (es[0].get("detail") or "")
            # Never suggest allowing a dangerous env name: refuse.
            if reason == "dangerous_env":
                name = ""
                for e in es:
                    if e.get("reason") == "dangerous_env" and e.get("detail"):
                        name = " (%s)" % e["detail"]
                        break
                refused.append(
                    'allowing the dangerous env name%s for key "%s" '
                    "(%d finding%s): dangerous names are never "
                    "suggested" % (name, kid, n, "s" if n != 1 else ""))
                continue
            # Never suggest permitting a URL file source.
            if reason in ("file_not_allowed", "pinned_script_with_files") \
                    and _looks_like_url(detail):
                refused.append(
                    'permitting URL file source for key "%s": URL file '
                    "sources are never suggested" % kid)
                continue
            suggestions.append(
                'key "%s": %d "%s" finding%s in audit mode; consider '
                "tightening the policy or switching the feature to "
                "enforce" % (kid, n, reason, "s" if n != 1 else ""))

    fragments = build_fragments(per_key)
    return table_rows, suggestions, refused, fragments


def format_report(table_rows, suggestions, refused, since_label,
                fragments=None):
    lines = []
    lines.append("Security audit report (%s)" % since_label)
    lines.append("=" * 60)
    if not table_rows:
        lines.append("no audit entries in this window")
    else:
        lines.append("%-14s %-10s %-9s %-10s %s"
                     % ("feature", "mode", "evaluated", "would-deny",
                        "reasons"))
        for feature, mode, evaluated, would_deny, reasons in table_rows:
            lines.append("%-14s %-10s %-9d %-10d %s"
                         % (feature, mode, evaluated, would_deny,
                            reasons))
    lines.append("")
    lines.append("Per-key suggestions")
    lines.append("-" * 60)
    if suggestions:
        for s in suggestions:
            lines.append("- " + s)
    else:
        lines.append("none")
    lines.append("")
    lines.append("Suggested key_policies fragments")
    lines.append("-" * 60)
    lines.append("(paste into config.json under \"key_policies\"; "
                 "nothing was written)")
    if fragments:
        for kid, info in fragments.items():
            lines.append('KEY: %s' % kid)
            frag = info["fragment"]
            if frag:
                lines.append("  %s" % json.dumps(frag, indent=4))
            # Counts per contributed name, so the owner sees frequency.
            bits = []
            for name, n in sorted(info["env_counts"].items()):
                bits.append('"%s" (%d)' % (name, n))
            for name, n in sorted(info["file_counts"].items()):
                bits.append('"%s" (%d)' % (name, n))
            if bits:
                lines.append("  observed: " + ", ".join(bits))
            for reason, n in sorted(info["arg_reasons"].items()):
                lines.append('  args: %d "%s" finding%s — craft '
                             "args_pattern/max_args manually"
                             % (n, reason, "s" if n != 1 else ""))
    else:
        lines.append("none")
    lines.append("")
    lines.append("Refused to suggest")
    lines.append("-" * 60)
    if refused:
        for s in refused:
            lines.append("- " + s)
    else:
        lines.append("none")
    return "\n".join(lines) + "\n"


def main(cfg, base_dir, since=None, key=None, feature=None):
    """Entry point for --audit-report. Returns an exit code."""
    try:
        since_secs = parse_since(since)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    # parse_since(None) is the 30-day default; label it honestly.
    label = "last %s" % since if since else "last 30d"
    if key:
        label += ", key %s" % key
    if feature:
        label += ", feature %s" % feature
    table_rows, suggestions, refused, fragments = build_report(
        cfg, base_dir, since_secs, key=key, feature=feature)
    # Key ids and finding counts. Secret values are not in the report.
    # codeql[py/clear-text-logging-sensitive-data]
    sys.stdout.write(format_report(table_rows, suggestions, refused,
                                   label, fragments))
    return 0
