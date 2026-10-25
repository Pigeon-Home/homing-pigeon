"""AV posture and command runner.

Extracted from runner.py.
"""
import os
import subprocess
import sys
import time


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


def _run_text(argv, timeout=5):
    """stdout of a short read-only command, or None. Never raises."""
    try:
        flags = {}
        if _runner().sys.platform == "win32":
            cnw = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if cnw:
                flags["creationflags"] = cnw
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, **flags)
    except Exception:
        return None
    if proc.returncode != 0 or not isinstance(proc.stdout, str):
        return None
    return proc.stdout


def _av_posture():
    """One line: is the host antivirus effective. None if unreadable.

    Not a malware scan. Linux stats the ClamAV daily signature file.
    Windows asks whether the Defender service is running. macOS has
    no stable read for XProtect, so it returns None. Never raises.
    """
    try:
        if _runner().sys.platform == "win32":
            return _runner()._parse_defender_query(_runner()._run_text(["sc", "query", "WinDefend"]))
        if _runner().sys.platform == "darwin":
            return None
        return _runner()._clam_sig_line()
    except Exception:
        return None


def _parse_defender_query(text):
    """'av: windows defender=running' from sc query, or None."""
    if not isinstance(text, str) or "STATE" not in text:
        return None
    for raw in text.splitlines():
        line = raw.strip()
        if not line.upper().startswith("STATE"):
            continue
        state = line.split()[-1].upper() if line.split() else ""
        if state == "RUNNING":
            return "av: windows defender=running"
        if state in ("STOPPED", "STOP_PENDING", "PAUSED"):
            return "av: windows defender=" + state.lower() + " [T1562.001]"
    return None


def _clam_sig_line(now=None):
    """Signature age only. Does not run freshclam or scan a file."""
    newest = None
    for path in _runner()._CLAM_SIG_PATHS:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if newest is None or mtime > newest:
            newest = mtime
    if newest is None:
        return None
    try:
        now = time.time() if now is None else float(now)
    except (TypeError, ValueError):
        now = time.time()
    age = now - newest
    if age > _runner()._AV_STALE_SEC:
        days = int(age // 86400)
        return "av: clamav signatures stale (%dd) [T1562.001]" % days
    return "av: clamav signatures current"


