"""AV posture and command runner.

Extracted from runner.py.
"""
import os
import subprocess
import threading
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
    """Kill a probe, reap it inside the grace, and walk away. Never raises.

    Closing the pipes is safe only while no reader thread
    exists. _run_text starts a reader on each pipe the moment
    the child exists, so it never closes them: a reader sits
    inside a read on the very stream object a close would
    touch, and on Windows the close waits behind that read
    until the pipe reaches EOF -- a grandchild holding the
    pipe would hold the caller after all (Q136 shard-7
    follow-on, 2026-11-11). Abandoned streams belong to the
    daemon reader threads and to the garbage collector. The
    reap after the kill is bounded too; it is what keeps a
    killed probe from lingering as an unwaited child.
    """
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=_KILL_GRACE_SECONDS)
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


def _drain(stream, sink):
    """Read `stream` to EOF into `sink`; a reader thread's whole job."""
    try:
        sink.append(stream.read())
    except Exception:
        pass


def _run_text(argv, timeout=5):
    """stdout of a short read-only command, or None. Never raises.

    The pipes are drained by two daemon reader threads from
    the moment the child exists, and the wait is on the
    process handle with the caller's timeout. Both halves
    are load-bearing. Reading first: a probe whose output
    outgrows the pipe buffer (reg query on the Services key,
    wevtutil's XML) blocks on its write until someone reads,
    so a wait that read nothing timed out on every such probe
    and the Windows suite leg spent 15 seconds a probe, nine
    probes a poll, until 20 of its 28 shards hit the wall
    (build-windows, 2026-11-11). Waiting on the handle: on
    Windows, communicate() joins a reader blocked in ReadFile,
    and a grandchild that inherited the pipe keeps that read
    open for its whole life, so a timeout passed to
    communicate() did not return (Q136, the grandchild case
    took 30s against a 1s timeout). After the process exits
    the readers get _KILL_GRACE_SECONDS to reach EOF; a pipe
    still held past that is a grandchild's, and the probe is
    abandoned, its output not an answer.
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
    out_chunks, err_chunks = [], []
    readers = []
    try:
        for stream, sink in ((proc.stdout, out_chunks),
                             (proc.stderr, err_chunks)):
            if stream is None:
                continue
            thread = threading.Thread(target=_drain, args=(stream, sink),
                                      daemon=True)
            thread.start()
            readers.append(thread)
    except Exception:
        _abandon(proc, close_streams=False)
        return None
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _abandon(proc, close_streams=False)
        return None
    except Exception:
        _abandon(proc, close_streams=False)
        return None
    deadline = time.monotonic() + _KILL_GRACE_SECONDS
    for thread in readers:
        thread.join(max(0.0, deadline - time.monotonic()))
        if thread.is_alive():
            # The process is gone but a pipe it left open did
            # not reach EOF inside the grace -- a grandchild
            # holds it, and the reader sits inside that read.
            _abandon(proc, close_streams=False)
            return None
    if proc.returncode != 0 or not out_chunks:
        return None
    out = out_chunks[0]
    return out if isinstance(out, str) else None


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


