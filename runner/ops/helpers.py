"""Small helpers extracted from runner.py.
"""
import os
import json
import selectors
import subprocess
import threading
import time


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


# ---------------------------------------------------------------- the held output
#
# What the runner holds of a job's 2 streams while the job runs
# (finding F17). communicate() holds every byte a job writes
# until the job ends, and the output cap cut the text only
# after that: a job that wrote without end was held without
# end, in the runner's own memory. The reader below reads each
# stream to its end as communicate() does, holds the first part
# of it up to a bar, and counts the rest and lets it go.

# The standard library's Popen, taken at the first import. A
# test may put a stand-in at subprocess.Popen; a stand-in is
# read by its own communicate(), as before.
POPEN = subprocess.Popen

# The most 1 read takes.
HELD_CHUNK = 65536

# What the log's copy of a stream leaves out at its end when the
# bar cut the stream, in characters. The bar can cut a secret in
# 2, and the half that is held does not match the pattern that
# would redact the whole.
HELD_TAIL = 65536

# How the 2 streams are read. The standard library's
# communicate() reads them in the calling thread where the
# system can wait on a pipe, and by a thread for each stream on
# Windows, where it cannot. The reader below does as it does.
HELD_BY_THREADS = os.name == "nt"


def held_bound(max_out, log_bytes=0):
    """The bar: how many bytes of each stream of a job the runner
    holds at most.

    A result carries the first `max_out` characters of a stream.
    A character is at most 4 bytes, so those characters lie
    within the first 4 x max_out bytes whatever the bytes are.
    The 4 bytes more are a margin: whether a stream goes on past
    what is held is settled by the reader's own count. Where the
    runner keeps a log, `log_bytes` is the most its record
    carries of a stream, and the bar is that, and the tail the
    record leaves out, where that is the larger. A value that
    is not a number counts as 0.
    """
    try:
        chars = max(0, int(max_out))
    except (TypeError, ValueError, OverflowError):
        chars = 0
    try:
        log_bytes = max(0, int(log_bytes))
    except (TypeError, ValueError, OverflowError):
        log_bytes = 0
    bound = 4 * chars + 4
    if log_bytes:
        bound = max(bound, log_bytes + 4 * HELD_TAIL)
    return bound


class Held:
    """A job's 2 streams, read to their end with a bar on what
    is held.

    `held(proc, timeout)` is `proc.communicate(timeout=timeout)`
    for a Popen: it returns when both streams are at their end
    and the process has ended, it raises
    subprocess.TimeoutExpired as communicate() does, and a later
    call goes on where the first stopped. Of each stream the
    first `keep` bytes are held and the rest are counted.
    Reading never stops at the bar, so a job never waits on a
    pipe the runner has left.

    The streams are read in the calling thread, and no thread is
    started for them, where the system can wait on a pipe. On
    Windows each is read by a thread of its own. Both are what
    communicate() does.

    `seen` is how many bytes each stream carried, `kept` how
    many of them were handed back, and `cut(name)` whether the
    stream carried more than was handed back.

    A process that is not the standard library's Popen (a
    stand-in) is read by its own communicate(), unbounded, as
    before.
    """

    STREAMS = ("stdout", "stderr")

    def __init__(self, keep, by_threads=None):
        try:
            self.keep = max(0, int(keep))
        except (TypeError, ValueError, OverflowError):
            self.keep = 0
        self.seen = {"stdout": 0, "stderr": 0}
        self.kept = {"stdout": 0, "stderr": 0}
        self._held = {"stdout": bytearray(), "stderr": bytearray()}
        self._by_threads = (HELD_BY_THREADS if by_threads is None
                            else bool(by_threads))
        self._open = None
        self._threads = None
        self._let_go = False

    def _take(self, name, chunk, seen):
        seen[name] += len(chunk)
        held = self._held[name]
        room = self.keep - len(held)
        if room > 0:
            held += chunk[:room]

    def _streams_of(self, proc):
        """The pipes of `proc` that are there to read."""
        found = []
        for name in self.STREAMS:
            pipe = getattr(proc, name, None)
            if pipe is not None and not pipe.closed:
                found.append((name, pipe))
        return found

    def _end(self, name):
        pipe = self._open.pop(name, None)
        try:
            if pipe is not None:
                pipe.close()
        except Exception:
            pass

    def _read_here(self, proc, left, timeout):
        """Both streams, in the calling thread, until both are at
        their end or the time is up."""
        if self._open is None:
            self._open = dict(self._streams_of(proc))
        if not self._open:
            return
        kind = getattr(selectors, "PollSelector", None) \
            or selectors.SelectSelector
        with kind() as waiting:
            for name, pipe in list(self._open.items()):
                try:
                    waiting.register(pipe, selectors.EVENT_READ, name)
                except (KeyError, ValueError, OSError):
                    # Closed under the reader: the stream's end.
                    self._end(name)
            while self._open:
                for key, _events in waiting.select(left()):
                    name, pipe = key.data, key.fileobj
                    try:
                        chunk = (getattr(pipe, "read1", None)
                                 or pipe.read)(HELD_CHUNK)
                    except (OSError, ValueError):
                        chunk = b""
                    if chunk:
                        self._take(name, chunk, self.seen)
                    else:
                        try:
                            waiting.unregister(pipe)
                        except (KeyError, ValueError, OSError):
                            pass
                        self._end(name)
                if self._open and left() == 0:
                    raise subprocess.TimeoutExpired(proc.args, timeout)

    def _drain(self, name, pipe, seen):
        read = getattr(pipe, "read1", None) or pipe.read
        try:
            while True:
                chunk = read(HELD_CHUNK)
                if not chunk or self._let_go:
                    break
                self._take(name, chunk, seen)
        except (OSError, ValueError):
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    def _read_by_threads(self, proc, left, timeout):
        """Each stream by a thread of its own, until both are at
        their end or the time is up."""
        if self._threads is None:
            self._threads = []
            for name, pipe in self._streams_of(proc):
                thread = threading.Thread(
                    target=self._drain, args=(name, pipe, self.seen),
                    name="job-" + name, daemon=True)
                thread.start()
                self._threads.append(thread)
        for thread in self._threads:
            thread.join(left())
            if thread.is_alive():
                raise subprocess.TimeoutExpired(proc.args, timeout)

    def __call__(self, proc, timeout=None):
        if not isinstance(proc, POPEN):
            out, err = proc.communicate(timeout=timeout)
            for name, data in zip(self.STREAMS, (out, err)):
                self.took(name, data)
            return out, err
        end = None if timeout is None else time.monotonic() + timeout

        def left():
            return None if end is None else max(0.0, end - time.monotonic())

        if self._by_threads:
            self._read_by_threads(proc, left, timeout)
        else:
            self._read_here(proc, left, timeout)
        proc.wait(timeout=left())
        # Handed back once, and no second copy stays behind.
        out = bytes(self._held["stdout"])
        self._held["stdout"] = bytearray()
        err = bytes(self._held["stderr"])
        self._held["stderr"] = bytearray()
        self.kept["stdout"], self.kept["stderr"] = len(out), len(err)
        return out, err

    def took(self, name, data, seen=None):
        """Note what another reader handed back for a stream, and
        how many bytes that stream carried where the reader
        counted them."""
        size = len(data) if isinstance(data, (bytes, bytearray)) else 0
        self.kept[name] = size
        self.seen[name] = size if seen is None else max(size, int(seen))

    def cut(self, name):
        """Whether the stream carried more than was handed back."""
        return self.seen[name] > self.kept[name]

    def let_go(self):
        """The caller has given the job up. The pipes read in the
        calling thread are closed here; a thread that reads one
        stops at its next read and closes it. Nothing of the
        streams is counted as read, then or after."""
        self._let_go = True
        for name in list(self._open or ()):
            self._end(name)
        self.seen = {"stdout": 0, "stderr": 0}
        self.kept = {"stdout": 0, "stderr": 0}
