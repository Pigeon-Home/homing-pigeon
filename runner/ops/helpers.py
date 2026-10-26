"""Small helpers extracted from runner.py.
"""
import os
import json


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore


def snapshot_outside(workspace_root, exclude=None):
    """Best-effort snapshot of paths outside the workspace. Returns path -> (size, mtime)."""
    if not isinstance(exclude, list):
        exclude = []
    exclude = [e for e in exclude if isinstance(e, str) and e]
    snap = {}
    if not workspace_root or not isinstance(workspace_root, str) \
            or not os.path.isdir(workspace_root):
        return snap
    parent = os.path.dirname(os.path.abspath(workspace_root))
    try:
        ws_real = os.path.realpath(workspace_root)
    except OSError:
        ws_real = os.path.abspath(workspace_root)
    # "/" as a workspace makes the parent the filesystem root. Walking
    # it stalls the poll. Refuse.
    if parent in ("/", "") or os.path.abspath(parent) == os.path.abspath(workspace_root):
        _runner().log("confinement snapshot refused: workspace parent is the filesystem root", "WARN")
        return snap
    count = 0
    try:
        walker = os.walk(parent)
    except OSError as e:
        _runner().log(f"confinement snapshot failed: {e}", "WARN")
        return snap
    try:
        for root, dirs, files in walker:
            # prune workspace and excluded dirs
            abs_root = os.path.abspath(root)
            try:
                root_real = os.path.realpath(root)
            except OSError:
                root_real = abs_root
            if root_real == ws_real or any(abs_root.startswith(os.path.abspath(e)) for e in exclude if e):
                dirs[:] = []
                continue
            for name in files:
                if count >= 50000:
                    _runner().log("confinement snapshot hit 50000 files; result is partial",
                        "WARN")
                    return snap
                path = os.path.join(root, name)
                try:
                    st = os.stat(path)
                    snap[path] = (st.st_size, st.st_mtime)
                    count += 1
                except Exception:
                    pass
    except OSError as e:
        _runner().log(f"confinement snapshot failed: {e}", "WARN")
    return snap


def append_bounded_log(path, text, max_bytes=2_097_152, backups=1):
    """Append one record. Roll once the file would pass max_bytes.

    Keeps up to `backups` rotated files (path.1 .. path.N, oldest
    dropped); backups=1 is the historic behavior: one backup, then
    the old backup is replaced. A chatty process cannot fill the
    disk. Failures are swallowed: logging must not kill the runner.
    """
    if not path or not isinstance(text, str) or not text:
        return
    if isinstance(max_bytes, bool):
        max_bytes = 2_097_152
    else:
        try:
            max_bytes = int(max_bytes)
        except (TypeError, ValueError, OverflowError):
            max_bytes = 2_097_152
    if max_bytes < 1:
        max_bytes = 2_097_152
    if isinstance(backups, bool):
        backups = 1
    else:
        try:
            backups = int(backups)
        except (TypeError, ValueError, OverflowError):
            backups = 1
    if backups < 1:
        backups = 1
    if backups > 100:
        backups = 100
    data = text if text.endswith("\n") else text + "\n"
    raw = data.encode("utf-8")
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
    folder = os.path.dirname(path)
    try:
        if folder:
            os.makedirs(folder, exist_ok=True)
        with _runner()._LOG_WRITE_LOCK:
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            if size and size + len(raw) > max_bytes:
                try:
                    if backups > 1:
                        oldest = f"{path}.{backups}"
                        if os.path.exists(oldest):
                            os.remove(oldest)
                        for n in range(backups - 1, 0, -1):
                            src = f"{path}.{n}"
                            if os.path.exists(src):
                                os.replace(src, f"{path}.{n + 1}")
                    os.replace(path, path + ".1")
                except OSError:
                    pass
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
            fd = _runner()._safe_open(path, flags, 0o600)
            try:
                os.write(fd, raw)
            finally:
                os.close(fd)
    except Exception:
        pass


