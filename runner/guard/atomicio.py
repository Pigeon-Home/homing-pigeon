"""One way to replace a state file: whole, or not at all.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

The runner's state files -- config, the replay cache, the DRI and
resource state, the detection baseline, the quarantine markers --
used to each carry their own copy of the same dozen lines: a
temp name, O_EXCL | O_NOFOLLOW, write, os.replace, chmod, unlink
on failure. Ten copies drift (two markers were being written
straight into the file, and a kill mid-write left a truncated
record). This module is the one copy.

The contract, for every writer here:

- The temp name is `<path>.tmp.<pid>.<thread>.<8 hex>`, created
  with O_WRONLY | O_CREAT | O_EXCL plus O_NOFOLLOW and O_BINARY
  where the platform has them, so a symlink planted at the temp
  name is not written through and two writers never share one.
- The bytes are written in full (and fsynced when asked), then
  os.replace moves the temp over `path`. A reader sees the old
  file or the new one, never a hole; a symlink at `path` is
  replaced, never followed.
- The mode is applied to the result best effort (0600 unless the
  caller says otherwise).
- On any failure the temp is unlinked and the exception is
  re-raised. Callers that swallow keep swallowing; nothing here
  decides that for them.

Stdlib only, no runner imports: the extension processes and the
cloud senders use it too.
"""
import json
import os
import time
import threading


def _temp_name(path):
    return "%s.tmp.%d.%d.%s" % (path, os.getpid(), threading.get_ident(),
                                os.urandom(4).hex())


def _open_new(path, mode):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    return os.open(path, flags, mode)


# On Windows a rename over a file another thread or process holds
# open is refused (PermissionError, winerror 5 or 32) until the handle
# closes; a reader of the replay cache in the poll loop was enough to
# make the writer's rename fail and the mark it carried disappear
# (Q124). The reader is gone in a moment, so the rename is tried
# again over a short window before the error stands. POSIX never
# takes this path: the first rename succeeds.
REPLACE_TRIES = 20
REPLACE_NAP = 0.01


def _replace(tmp, path):
    nap = REPLACE_NAP
    for attempt in range(REPLACE_TRIES):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == REPLACE_TRIES - 1:
                raise
            time.sleep(nap)
            nap = min(nap * 1.5, 0.1)


def write_bytes(path, data, mode=0o600, fsync=False):
    """Replace `path` with `data`, whole or not at all."""
    if not isinstance(path, str) or not path:
        raise ValueError("path must be a non-empty string")
    tmp = _temp_name(path)
    fd = _open_new(tmp, mode)
    failed = None
    try:
        view = memoryview(bytes(data))
        while len(view):
            view = view[os.write(fd, view):]
        if fsync:
            os.fsync(fd)
    except BaseException as e:   # the write's error is the one reported
        failed = e
    try:
        os.close(fd)
    except OSError as e:         # bytes may not be down: a failure too
        if failed is None:
            failed = e
    if failed is None:
        try:
            _replace(tmp, path)
        except BaseException as e:
            failed = e
    if failed is not None:
        try:
            os.unlink(tmp)       # a refused cleanup never masks the cause
        except OSError:
            pass
        raise failed
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def write_text(path, text, mode=0o600, encoding="utf-8", fsync=False):
    """Replace `path` with `text`, encoded (UTF-8 by default)."""
    return write_bytes(path, str(text).encode(encoding), mode=mode,
                       fsync=fsync)


def write_json(path, obj, mode=0o600, indent=None, fsync=False,
               sort_keys=False, allow_nan=True, newline=False):
    """Replace `path` with `obj` as JSON.

    The object is serialized before any file is touched, so an
    unserializable value raises with nothing on disk -- no temp,
    no half-written record. `newline` adds the trailing newline
    the human-edited files (config.json) carry.
    """
    text = json.dumps(obj, indent=indent, sort_keys=sort_keys,
                      allow_nan=allow_nan)
    if newline:
        text += "\n"
    return write_text(path, text, mode=mode, fsync=fsync)
