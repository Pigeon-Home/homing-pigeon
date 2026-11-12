"""AV posture and command runner.

Extracted from runner.py.
"""
import os
import subprocess
import time


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore


# The grace a killed probe gets to hand its output back
# before _run_text walks away from its pipes. Bounded, like
# the probe timeout itself: a probe whose child leaves a
# pipe held open (a grandchild that inherited stdout) must
# not turn the walk-away into a second, unbounded wait --
# that shape hung the Windows test leg at the 20-minute
# wall (Q136 shard-5 follow-on, 2026-11-11: subprocess.run
# on Windows follows a timeout kill with a communicate()
# that carries no timeout, so the wait below is done by
# hand, with every wait bounded).
_KILL_GRACE_SECONDS = 2.0


def _abandon(proc, close_streams=True):
    """Kill a probe and walk away from it. Never raises.

    Closing the pipes is safe only while no reader thread
    exists -- that is, before any communicate() call. Once
    communicate() has started its readers, a reader sits
    inside a read on the very stream object a close would
    touch, and on Windows the close waits behind that read
    until the pipe reaches EOF: a grandchild holding the
    pipe would hold the caller after all (the collect path
    below, Q136 shard-7 follow-on, 2026-11-11). Past a
    communicate() the streams are therefore abandoned
    unclosed; they belong to the daemon reader threads and
    to the garbage collector.
    """
    try:
        proc.kill()
    except Exception:
        pass
    if not close_streams:
        return
    for stream in (getattr(proc, "stdout", None),
                   getattr(proc, "stderr", None),
                   getattr(proc, "stdin", None)):
        try:
            if stream is not None:
                stream.close()
        except Exception:
            pass


def _run_text(argv, timeout=5):
    """stdout of a short read-only command, or None. Never raises.

    The wait is on the process, not on its pipes. On Windows,
    communicate() joins a reader thread blocked in ReadFile; a
    grandchild that inherited the pipe keeps that read open for
    the child's whole life, so a timeout passed to communicate()
    did not return (Q136, build-windows 2026-11-11: the
    grandchild case took 30s against a 1s timeout). wait() uses
    the process handle and returns when the timeout says. A pipe
    still held after the process exits is then read under
    _KILL_GRACE_SECONDS and abandoned if it does not end.
    """
    try:
        flags = {}
        if _runner().sys.platform == "win32":
            cnw = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if cnw:
                flags["creationflags"] = cnw
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, **flags)
    except Exception:
        return None
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _abandon(proc)
        return None
    except Exception:
        _abandon(proc)
        return None
    try:
        out, _err = proc.communicate(timeout=_KILL_GRACE_SECONDS)
    except Exception:
        # The process is gone but a pipe it left open did
        # not reach EOF inside the grace -- a grandchild
        # holds it. communicate()'s reader threads are
        # inside reads on these streams now, so the pipes
        # are abandoned unclosed (see _abandon): closing
        # them here would wait for the grandchild's exit,
        # the very hold this function exists to never take.
        _abandon(proc, close_streams=False)
        return None
    if proc.returncode != 0 or not isinstance(out, str):
        return None
    return out


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


