#!/usr/bin/env python3
"""--audit-report: summarize the security audit log.

Read-only. No mailbox access, no network, never writes to
config.json. Works with a config that has no mailbox credentials.

Output: a table of audit decisions in the window, per-key
suggestions, and a "refused to suggest" section. Dangerous env
names and URL file sources are never suggested.
"""
import json
import os
import re
import sys
import time

try:
    from runner import security as _security
except ImportError:  # running from inside runner/ as __main__
    try:
        import security as _security
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
        return time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, OverflowError):
        return 0


def _dangerous_names():
    if _security is not None:
        return _security.DANGEROUS_ENV_NAMES
    return frozenset()


def _looks_like_url(name):
    return isinstance(name, str) and (
        name.startswith("http://") or name.startswith("https://"))


def build_report(cfg, base_dir, since_secs):
    """Return (table_rows, suggestions, refused).

    table_rows: [(feature, decision, reason, count)] sorted by count.
    suggestions: [str]. refused: [str].
    """
    now = time.time()
    entries = [e for e in _read_entries(base_dir)
               if now - _entry_ts(e) <= since_secs]

    counts = {}
    per_key = {}
    for e in entries:
        key = (e.get("feature", "?"), e.get("decision", "?"),
               e.get("reason", "?"))
        counts[key] = counts.get(key, 0) + 1
        kid = e.get("key_id") or "(default)"
        per_key.setdefault(kid, []).append(e)

    table_rows = sorted(
        ((f, d, r, c) for (f, d, r), c in counts.items()),
        key=lambda row: (-row[3], row[0], row[1], row[2]))

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

    return table_rows, suggestions, refused


def format_report(table_rows, suggestions, refused, since_label):
    lines = []
    lines.append("Security audit report (%s)" % since_label)
    lines.append("=" * 60)
    if not table_rows:
        lines.append("no audit entries in this window")
    else:
        lines.append("%-16s %-10s %-24s %s"
                     % ("feature", "decision", "reason", "count"))
        for feature, decision, reason, count in table_rows:
            lines.append("%-16s %-10s %-24s %d"
                         % (feature, decision, reason, count))
    lines.append("")
    lines.append("Per-key suggestions")
    lines.append("-" * 60)
    if suggestions:
        for s in suggestions:
            lines.append("- " + s)
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


def main(cfg, base_dir, since=None):
    """Entry point for --audit-report. Returns an exit code."""
    try:
        since_secs = parse_since(since)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    # parse_since(None) is the 30-day default; label it honestly.
    label = "last %s" % since if since else "last 30d"
    table_rows, suggestions, refused = build_report(cfg, base_dir,
                                                    since_secs)
    sys.stdout.write(format_report(table_rows, suggestions, refused,
                                   label))
    return 0
