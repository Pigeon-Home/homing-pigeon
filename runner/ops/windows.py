"""Windows-specific helpers.

Extracted from runner.py. Only loaded on Windows, or when
Windows-specific functions are called.
"""
import subprocess
import sys


from typing import Any


def _runner() -> Any:
    """The live runner module, looked up at call time.

    `runner.runner` when the suite or a package import loaded it,
    `__main__` when runner.py was started as a script (an install,
    the one-file binaries), where `runner` is the file itself and
    `from runner import runner` raises "'runner' is not a package".
    """
    for name in ("runner.runner", "__main__"):
        m = sys.modules.get(name)
        if m is not None and callable(getattr(m, "_load_mod", None)):
            return m
    from runner import runner as R  # a host that imported us first
    return R


def _wevtutil_query(logname, xpath, count, timeout=15):
    """Run wevtutil and return stdout text.

    wevtutil ships with Windows. Returns None on any failure (so the
    caller can say "unreadable" instead of "clean"); "" means the query
    ran but matched nothing. Never raises: telemetry must not break
    the runner.
    """
    try:
        flags = {}
        if _runner().sys.platform == "win32":
            cnw = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if cnw:
                flags["creationflags"] = cnw
        proc = subprocess.run(
            ["wevtutil", "qe", logname, "/q:" + xpath,
             "/c:%d" % count, "/rd:true", "/f:xml"],
            capture_output=True, text=True, timeout=timeout, **flags)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout
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
        flags = {}
        if _runner().sys.platform == "win32":
            cnw = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if cnw:
                flags["creationflags"] = cnw
        proc = subprocess.run(
            ["reg", "query", key], capture_output=True, text=True,
            timeout=15, **flags)
    except Exception:
        return None
    if proc.returncode != 0 or not isinstance(proc.stdout, str):
        return None
    values = {}
    subkeys = []
    for raw in proc.stdout.splitlines():
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


