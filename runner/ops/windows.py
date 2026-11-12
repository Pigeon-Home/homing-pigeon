"""Windows-specific helpers.

Extracted from runner.py. Only loaded on Windows, or when
Windows-specific functions are called.

Both probes below read through the bounded _run_text seam
(runner/ops/av.py), never subprocess.run: on Windows,
run() answers a timeout by killing the child and then
calling communicate() with no timeout to collect output,
and that collect joins the pipe reader threads without a
bound, so a pipe held open past the kill hangs the caller
for as long as it stays open (Q136 shard-7 follow-on,
2026-11-11; the kill dump of build run 43121516173 sits
inside _reg_query's run() exactly this way). _run_text
waits on the process handle and abandons a held pipe
inside its grace, on every path.
"""


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore


def _wevtutil_query(logname, xpath, count, timeout=15):
    """Run wevtutil and return stdout text.

    wevtutil ships with Windows. Returns None on any failure (so the
    caller can say "unreadable" instead of "clean"); "" means the query
    ran but matched nothing. Never raises: telemetry must not break
    the runner.
    """
    try:
        out = _runner()._run_text(
            ["wevtutil", "qe", logname, "/q:" + xpath,
             "/c:%d" % count, "/rd:true", "/f:xml"],
            timeout=timeout)
    except Exception:
        return None
    return out if isinstance(out, str) else None


def _reg_attack(key):
    """ATT&CK id for a watched registry location, or ""."""
    low = key.lower().replace("/", "\\")
    if "winlogon" in low:
        return "T1547.004"
    if low.endswith("\\run") or low.endswith("\\runonce"):
        return "T1547.001"
    return ""


def _reg_query(key):
    """(values, subkeys) for a registry key, or None on failure.

    values is {name: data}, subkeys is [name]. Uses reg.exe, which ships
    with Windows. Never raises.
    """
    try:
        out = _runner()._run_text(["reg", "query", key], timeout=15)
    except Exception:
        return None
    if not isinstance(out, str):
        return None
    values = {}
    subkeys = []
    for raw in out.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if not raw[:1].isspace():
            # A subkey path (reg.exe prints them flush-left).
            subkeys.append(line.strip())
            continue
        parts = line.strip().split(None, 2)
        if len(parts) >= 3:
            values[parts[0]] = parts[2][:160]
        elif len(parts) == 2:
            values[parts[0]] = ""
    # The first flush-left line is the queried key itself, not a subkey.
    if subkeys and subkeys[0].lower() == key.lower():
        subkeys = subkeys[1:]
    return values, subkeys
