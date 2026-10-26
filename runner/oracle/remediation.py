#!/usr/bin/env python3
"""Remediation: acting on a job that goes bad mid-run.

The design of record is docs/design/remediation-design.md; this module
is its implementation, and every place the code departs from the
document is written there, in the open. The short form:

- The trigger is a *divergence*: observed behavior the job's
  intent envelope (the Oracle opinion's recorded expectations)
  did not declare. A job doing what its envelope said -- even
  something destructive the sender openly declared -- is not a
  remediation case.
- Authority is layered. A closed list of deterministic
  *tripwires* (this module's TRIPWIRE_KINDS) kills on sight in
  `deterministic` and `oracle` modes. In `oracle` mode the
  local model may additionally order a kill for a divergence
  that is not a tripwire; anything short of an affirmative
  order -- refusal, timeout, error, no inference configured --
  is an abstention and never kills. In `off` mode the system
  watches, records, and pages only: the DRI playbook's
  original doctrine, preserved as a setting.
- The acts escalate: kill the whole process tree, quarantine
  the job's outputs (moved, never deleted; the owner releases
  them with one recorded act), refer the suspect files to the
  box's antivirus for its own verdict, and page the owner
  through the DRI channel with the whole story.

This module is free of runner imports, like runner/oracle/opinion.py:
the runner wires the live probes (findings, the model call,
the senses store, the audit log) in as callables.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

try:
    from runner.guard import atomicio as _atomicio
except ImportError:
    from guard import atomicio as _atomicio  # type: ignore

MODES = ("off", "deterministic", "oracle")
DEFAULT_MODE = "deterministic"

# The closed tripwire list. A new entry here is a code change
# with a test, never a config accident or a model's suggestion.
TRIPWIRE_KINDS = frozenset((
    "confinement_escape",
    "process_storm",
    "credential_artifact",
))

# Divergence kinds that are evidence, not verdicts: they go to
# the authority layer (the Oracle in oracle mode, the record in
# every mode) and never kill by themselves.
DIVERGENCE_KINDS = frozenset((
    "confinement_strain",
    "undeclared_path_artifact",
    "tree_saturation",
    "tree_memory",
    "disk_fill",
    "sense_alert",
    "resource_event",
))

# Defaults for the config family. Every value is tunable; the
# names are the config keys.
DEFAULT_STORM_CEILING = 64
DEFAULT_SAMPLE_SEC = 1.0
DEFAULT_ORACLE_TIMEOUT_SEC = 20
DEFAULT_QUARANTINE_MAX_JOBS = 50
DEFAULT_QUARANTINE_MAX_BYTES = 512 * 1024 * 1024

# Saturation tells (named constants, per the design delta):
# CPU at or over SATURATION_CPU of one core for SATURATION_RUN
# consecutive samples; tree RSS at or over TREE_RSS_FRACTION of
# the box's memory for TREE_RSS_RUN samples; workdir growth of
# DISK_FILL_BYTES inside the run.
SATURATION_CPU = 0.95
SATURATION_RUN = 3
TREE_RSS_FRACTION = 0.5
TREE_RSS_RUN = 2
DISK_FILL_BYTES = 256 * 1024 * 1024

# The reason string runner._script_path_findings uses for its
# credential-store class. The tripwire keys on exactly it.
CREDENTIAL_REASON = "a credential store or key material"

ARTIFACT_READ_CAP = 256 * 1024
AV_MAX_FILES = 8
AV_TIMEOUT_SEC = 60

QUARANTINE_DIR = "quarantine"
QUARANTINE_ARCHIVE_DIR = "quarantine-archive"
SECURITY_EVENTS_FILE = "security-events.jsonl"
SECURITY_AUDIT_FILE = "security-audit.jsonl"

_JOB_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _safe_job_id(value):
    if not isinstance(value, str) or not _JOB_ID_RE.match(value):
        return None
    if value in (".", ".."):
        return None
    return value


# ------------------------------------------------------------ settings

def _clean_mode(value):
    return value if isinstance(value, str) and value in MODES \
        else DEFAULT_MODE


def mode_of(cfg):
    """The configured remediation mode; anything unrecognized
    is the default, deterministic -- never a silent `off`."""
    if not isinstance(cfg, dict):
        return DEFAULT_MODE
    return _clean_mode(cfg.get("remediation_mode"))


def _pos_int(value, default, minimum=1):
    if isinstance(value, bool):
        return default
    try:
        n = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return n if n >= minimum else default


def _pos_float(value, default, minimum=0.05):
    if isinstance(value, bool):
        return default
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if n != n or n in (float("inf"), float("-inf")) or n < minimum:
        return default
    return n


def settings(cfg):
    """The remediation settings family, defaults at the read site."""
    cfg = cfg if isinstance(cfg, dict) else {}
    return {
        "mode": _clean_mode(cfg.get("remediation_mode")),
        "storm_ceiling": _pos_int(
            cfg.get("remediation_storm_ceiling"), DEFAULT_STORM_CEILING),
        "sample_sec": _pos_float(
            cfg.get("remediation_sample_sec"), DEFAULT_SAMPLE_SEC),
        "oracle_timeout_sec": _pos_int(
            cfg.get("remediation_oracle_timeout_sec"),
            DEFAULT_ORACLE_TIMEOUT_SEC),
        "quarantine_max_jobs": _pos_int(
            cfg.get("remediation_quarantine_max_jobs"),
            DEFAULT_QUARANTINE_MAX_JOBS),
        "quarantine_max_bytes": _pos_int(
            cfg.get("remediation_quarantine_max_bytes"),
            DEFAULT_QUARANTINE_MAX_BYTES),
    }


def received_digest(job):
    """SHA-384 of the job as received, sig member excluded.

    The same definition as runner/oracle/opinion.py's: compact JSON,
    sorted keys, UTF-8, over the job object with `sig` removed,
    so the sender can recompute and diff.
    """
    payload = {}
    if isinstance(job, dict):
        payload = {k: v for k, v in job.items() if k != "sig"}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False)
    return hashlib.sha384(raw.encode("utf-8")).hexdigest()


# ------------------------------------------------------------ process trees
#
# A sample is {pid: (cpu_seconds, rss_bytes)}; rss may be None
# where the platform cannot read that process. Membership is
# the root plus every descendant in the parent map at sample
# time. A process that starts and exits between samples is
# invisible on every platform; that limit is in the design.

def tree_pids(root_pid, parents):
    """Root plus descendants, from a {pid: ppid} map. Pure."""
    children = {}
    for pid, ppid in parents.items():
        children.setdefault(ppid, []).append(pid)
    out = []
    seen = set()
    stack = [root_pid]
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
        stack.extend(children.get(pid, ()))
    return out


def _proc_parents():
    parents = {}
    try:
        names = os.listdir("/proc")
    except OSError:
        return parents
    for name in names:
        if not name.isdigit():
            continue
        try:
            with open(os.path.join("/proc", name, "stat"),
                      "r", encoding="utf-8", errors="replace") as fh:
                data = fh.read()
            # comm is parenthesized and may contain spaces or
            # parens; fields after the LAST ')' are stable.
            rest = data[data.rfind(")") + 2:].split()
            parents[int(name)] = int(rest[1])
        except (OSError, ValueError, IndexError):
            continue
    return parents


def _clk_tck():
    try:
        return float(os.sysconf("SC_CLK_TCK"))
    except (ValueError, OSError, AttributeError):
        return 100.0


def _page_size():
    try:
        return int(os.sysconf("SC_PAGE_SIZE"))
    except (ValueError, OSError, AttributeError):
        return 4096


def _proc_usage(pid, tck, page):
    try:
        with open(f"/proc/{pid}/stat", "r",
                  encoding="utf-8", errors="replace") as fh:
            data = fh.read()
        rest = data[data.rfind(")") + 2:].split()
        ticks = int(rest[11]) + int(rest[12])  # utime + stime
    except (OSError, ValueError, IndexError):
        return None
    rss = None
    try:
        with open(f"/proc/{pid}/statm", "r") as fh:
            parts = fh.read().split()
        rss = int(parts[1]) * page or None   # zero pages: no figure
    except (OSError, ValueError, IndexError):
        rss = None
    return (ticks / tck, rss)


def sample_tree_posix(root_pid):
    parents = _proc_parents()
    tck = _clk_tck()
    page = _page_size()
    sample = {}
    for pid in tree_pids(root_pid, parents):
        usage = _proc_usage(pid, tck, page)
        sample[pid] = usage if usage is not None else (0.0, None)
    if root_pid not in sample:
        sample[root_pid] = (0.0, None)
    return sample


def total_memory_bytes():
    """The box's RAM, or None where no stdlib route reads it."""
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/meminfo", "r") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            pass
    if os.name == "nt":
        try:
            return _win_total_memory()
        except Exception:
            return None
    try:
        return int(os.sysconf("SC_PHYS_PAGES")) * _page_size()
    except (ValueError, OSError, AttributeError):
        return None


# --- Windows, via ctypes. Toolhelp names a parent by pid, and
# Windows reuses pids, so a job can be handed the leftover
# children of whoever held that pid before. Those processes
# are older than the job. A process we cannot open at all is
# counted once and not walked: its children are the same
# ambiguity, and walking them is how a one-line job on a busy
# runner was charged with the whole tree (v3.11.36, 144
# processes, storm ceiling 64).

def _win_parents():
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snap = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snap == -1 or not snap:
        return {}
    parents = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            parents[int(entry.th32ProcessID)] = \
                int(entry.th32ParentProcessID)
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return parents


def _win_created_ticks(pid):
    """Process creation time in 100ns ticks, or None.

    None means the process could not be opened or its times
    could not be read. Callers must not treat that as "older"
    or "younger".
    """
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]

        def ticks100ns(self):
            return (self.hi << 32) | self.lo

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED
    if not handle:
        return None
    try:
        created, exited, kern, user = (FILETIME(), FILETIME(),
                                       FILETIME(), FILETIME())
        if not kernel32.GetProcessTimes(
                handle, ctypes.byref(created), ctypes.byref(exited),
                ctypes.byref(kern), ctypes.byref(user)):
            return None
        return created.ticks100ns()
    finally:
        kernel32.CloseHandle(handle)


def _win_usage(pid):
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]

        def ticks100ns(self):
            return (self.hi << 32) | self.lo

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    try:
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
    except OSError:
        psapi = kernel32  # GetProcessMemoryInfo lives in kernel32 too
    handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED
    if not handle:
        return None
    try:
        created, exited, kern, user = (FILETIME(), FILETIME(),
                                       FILETIME(), FILETIME())
        cpu = None
        if kernel32.GetProcessTimes(handle, ctypes.byref(created),
                                    ctypes.byref(exited),
                                    ctypes.byref(kern),
                                    ctypes.byref(user)):
            cpu = (kern.ticks100ns() + user.ticks100ns()) / 1e7
        rss = None
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters),
                                      counters.cb):
            rss = int(counters.WorkingSetSize)
        if cpu is None and rss is None:
            return None
        return (cpu or 0.0, rss)
    finally:
        kernel32.CloseHandle(handle)


def _win_total_memory():
    import ctypes
    from ctypes import wintypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
        return None
    return int(stat.ullTotalPhys)


def sample_tree_windows(root_pid):
    parents = _win_parents()
    children = {}
    for pid, ppid in parents.items():
        children.setdefault(ppid, []).append(pid)
    root_born = _win_created_ticks(root_pid)
    sample = {}
    seen = set()
    stack = [root_pid]
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        if pid != root_pid and root_born is not None:
            born = _win_created_ticks(pid)
            if born is None:
                sample[pid] = (0.0, None)
                continue
            if born < root_born:
                continue
        usage = _win_usage(pid)
        sample[pid] = usage if usage is not None else (0.0, None)
        stack.extend(children.get(pid, ()))
    if root_pid not in sample:
        sample[root_pid] = (0.0, None)
    return sample


# --- Darwin and the BSDs, via ps. No /proc with Linux's per-pid
# files there (FreeBSD's procfs, where mounted, has another shape),
# and the stdlib has no process-table call, so one `ps` per sample
# gives the table: pid, parent, resident set in KiB, and the
# accumulated CPU time, which ps prints as [[DD-]HH:]MM:SS[.ss].
# One fork per sample is the price; the storm this exists to catch
# makes the fork slower, not impossible (Q38, 2026-10-25).

_PS_ARGS = ("ps", "-axo", "pid=,ppid=,rss=,time=")


def _ps_available():
    return shutil.which("ps") is not None


def _cpu_seconds(text):
    """Seconds from ps's time column: '0:00.05', '1:02:03',
    '2-01:00:00'. None when the text is not that."""
    try:
        days = 0
        if "-" in text:
            d, text = text.split("-", 1)
            days = int(d)
        secs = 0.0
        for part in text.split(":"):
            secs = secs * 60 + float(part)
        return days * 86400 + secs
    except (ValueError, AttributeError, TypeError):
        return None


def _ps_table(run=None):
    """{pid: (ppid, rss_bytes|None, cpu_seconds)} from one ps call;
    empty when ps is absent or says nothing usable."""
    run = run or subprocess.run
    try:
        out = run(list(_PS_ARGS), stdout=subprocess.PIPE,
                  stderr=subprocess.DEVNULL, timeout=10,
                  universal_newlines=True).stdout
    except (OSError, subprocess.SubprocessError, ValueError,
            AttributeError):
        return {}
    table = {}
    for line in (out or "").splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        try:
            # A zero resident set is ps saying it has no figure yet (a
            # process between fork and exec, or on its way out), not a
            # measurement: it reads as unknown, like a dash.
            rss = int(parts[2]) * 1024 or None
        except ValueError:
            rss = None
        cpu = _cpu_seconds(parts[3])
        table[pid] = (ppid, rss, cpu if cpu is not None else 0.0)
    return table


def sample_tree_ps(root_pid, run=None):
    table = _ps_table(run)
    parents = {pid: row[0] for pid, row in table.items()}
    sample = {}
    for pid in tree_pids(root_pid, parents):
        row = table.get(pid)
        sample[pid] = (row[2], row[1]) if row else (0.0, None)
    if root_pid not in sample:
        sample[root_pid] = (0.0, None)
    return sample


def sample_tree(root_pid):
    """This platform's sampler. {pid: (cpu_seconds, rss|None)}.

    Windows reads the toolhelp snapshot, Linux reads /proc, and
    every other POSIX (Darwin, the BSDs) asks ps. A box with none of
    those sees the root alone, which is what the watch can honestly
    say about the tree there.
    """
    if os.name == "nt":
        return sample_tree_windows(root_pid)
    if sys.platform.startswith("linux") and os.path.isdir("/proc"):
        return sample_tree_posix(root_pid)
    if _ps_available():
        return sample_tree_ps(root_pid)
    return {root_pid: (0.0, None)}


# ------------------------------------------------------------ divergences

def divergence(kind, detail):
    return {"kind": kind, "detail": str(detail)[:300],
            "tripwire": kind in TRIPWIRE_KINDS}


def divergence_text(div):
    """The short string the result member and the records carry."""
    if not isinstance(div, dict):
        return ""
    kind = div.get("kind") or "divergence"
    detail = div.get("detail") or ""
    return (f"{kind}: {detail}" if detail else kind)[:300]


class TreeSignals:
    """Sustained-shape tells over a job's process tree samples.

    Point-in-time spikes are not divergences: saturation and
    memory pressure must hold across consecutive samples, the
    way resource-sentinel's signals hold across a window.
    Each kind fires at most once per job.
    """

    def __init__(self, total_mem=None):
        self._total_mem = total_mem
        self._prev = None          # (cpu_seconds_total, at)
        self._cpu_run = 0
        self._rss_run = 0
        self._first_dir_bytes = None
        self._fired = set()

    def feed(self, sample, at, workdir_bytes=None):
        """One sample in; the divergence dicts it newly proves."""
        out = []
        cpu_total = 0.0
        rss_total = 0
        rss_known = False
        for cpu, rss in sample.values():
            cpu_total += cpu or 0.0
            if rss is not None:
                rss_total += rss
                rss_known = True
        if self._prev is not None:
            prev_cpu, prev_at = self._prev
            dt = at - prev_at
            if dt > 0:
                rate = (cpu_total - prev_cpu) / dt
                if rate >= SATURATION_CPU:
                    self._cpu_run += 1
                else:
                    self._cpu_run = 0
                if self._cpu_run >= SATURATION_RUN \
                        and "tree_saturation" not in self._fired:
                    self._fired.add("tree_saturation")
                    out.append(divergence(
                        "tree_saturation",
                        f"job tree at {rate:.0%} of a core across "
                        f"{self._cpu_run} samples"))
        self._prev = (cpu_total, at)
        if rss_known and self._total_mem:
            share = rss_total / self._total_mem
            if share >= TREE_RSS_FRACTION:
                self._rss_run += 1
            else:
                self._rss_run = 0
            if self._rss_run >= TREE_RSS_RUN \
                    and "tree_memory" not in self._fired:
                self._fired.add("tree_memory")
                out.append(divergence(
                    "tree_memory",
                    f"job tree resident memory at {share:.0%} of "
                    f"the box's RAM across {self._rss_run} samples"))
        if workdir_bytes is not None:
            if self._first_dir_bytes is None:
                self._first_dir_bytes = workdir_bytes
            elif workdir_bytes - self._first_dir_bytes >= DISK_FILL_BYTES \
                    and "disk_fill" not in self._fired:
                self._fired.add("disk_fill")
                out.append(divergence(
                    "disk_fill",
                    f"workdir grew {workdir_bytes - self._first_dir_bytes} "
                    f"bytes inside the run"))
        return out


def _norm_path(path):
    if not isinstance(path, str):
        return ""
    return path.replace("\\", "/").rstrip("/")


def classify_findings(findings, declared_paths, declared_credential_paths):
    """Split live findings against the envelope's declarations.

    findings: (path, reason) pairs in the runner's
    _script_path_findings shape, produced by scanning what the
    job wrote. Returns (tripwire_divergence_or_None, [divergences]).

    A path the envelope itself declared is the job doing what
    it said: never a finding here, whatever its class. An
    undeclared credential-store reference in a produced
    artifact is the tripwire. Any other undeclared reference is
    a divergence for the authority layer.
    """
    declared = {_norm_path(p) for p in declared_paths or ()}
    declared_cred = {_norm_path(p) for p in declared_credential_paths or ()}
    tripwire = None
    divs = []
    seen = set()
    for path, reason in findings or ():
        norm = _norm_path(path)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        if norm in declared:
            continue
        if reason == CREDENTIAL_REASON and norm not in declared_cred:
            if tripwire is None:
                tripwire = divergence(
                    "credential_artifact",
                    f"produced artifact references {path} "
                    f"({reason}), which the job's envelope "
                    f"never declared")
            continue
        divs.append(divergence(
            "undeclared_path_artifact",
            f"produced artifact references {path} ({reason}), "
            f"which the job's envelope never declared"))
    return tripwire, divs


# ------------------------------------------------------------ window evidence
#
# Correlation rule (the design's first open item, closed here):
# the box's own clock is the only clock. An event belongs to a
# job's window when its timestamp falls inside [start, end] and
# it names the job -- by job id, by workdir path, or by a pid in
# the job's tree. Resource-pressure events inside the window
# are box-level evidence and need no naming.

def _parse_iso(text):
    """Epoch seconds for a ...Z timestamp, or None."""
    if not isinstance(text, str) or not text:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
        return dt.replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, OverflowError):
        return None


def _read_jsonl_window(path, since_ts, cap_bytes=512 * 1024):
    """Parsed objects from a JSONL file with ts >= since_ts.

    ts comes from the "at" or "ts" member. Reads only the tail:
    state files are capped by their writers, and a monitor must
    not turn a huge log into a per-sample cost. Never raises.
    """
    out = []
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > cap_bytes:
                fh.seek(size - cap_bytes)
                fh.readline()
            raw = fh.read()
    except OSError:
        return out
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        ts = _parse_iso(rec.get("at") or rec.get("ts"))
        if ts is not None and ts >= since_ts:
            out.append(rec)
    return out


def resource_events_in_window(base_dir, since_ts):
    """security-events entries of type resource_pressure in window."""
    path = os.path.join(base_dir, SECURITY_EVENTS_FILE)
    return [ev for ev in _read_jsonl_window(path, since_ts - 1.0)
            if ev.get("type") == "resource_pressure"]


def confinement_events_in_window(base_dir, job_id, since_ts):
    """Cage audit entries for this job inside the window.

    The cage's live report today is its startup audit entry (see
    the design delta): 'fallback' -- enforce was requested and
    the job is running uncaged -- is a strain divergence. A
    'denied' decision, for the day a cage reports one mid-run,
    is the escape tripwire.
    """
    path = os.path.join(base_dir, SECURITY_AUDIT_FILE)
    out = []
    for rec in _read_jsonl_window(path, since_ts - 5.0):
        if rec.get("feature") != "confinement":
            continue
        if str(rec.get("job_id") or "") != str(job_id):
            continue
        out.append(rec)
    return out


def alert_names_job(alert, job_id, work_dir, tree_pids_now):
    """True when a sense alert is about this job (see the rule)."""
    if not isinstance(alert, dict):
        return False
    haystack = " ".join(str(alert.get(k) or "") for k in
                        ("sensor", "signal", "title", "detail"))
    try:
        haystack += " " + json.dumps(alert.get("detail") or {})
    except (TypeError, ValueError):
        pass
    if job_id and str(job_id) in haystack:
        return True
    if work_dir and _norm_path(work_dir) and \
            _norm_path(work_dir) in _norm_path(haystack):
        return True
    for pid in tree_pids_now or ():
        if f"pid={pid}" in haystack or f"pid {pid}" in haystack:
            return True
    return False


# ------------------------------------------------------------ the Oracle's order

ORACLE_QUESTION = (
    "A running job has diverged from what its opinion envelope "
    "declared. You are the remediation authority for this box. "
    "Decide whether the job must be killed now. Answer with one "
    "line beginning KILL: followed by the reason, or one line "
    "beginning SPARE: followed by the reason. Anything else is "
    "recorded as an abstention and the job keeps running.")


def parse_oracle_order(answer):
    """True only on an affirmative order: a leading KILL line.

    A refusal, a hedge, an empty or missing reply -- all spare.
    The model orders a kill or the job runs; there is no third
    reading of its text.
    """
    if not isinstance(answer, str):
        return False
    for line in answer.splitlines():
        line = line.strip()
        if not line:
            continue
        return line.upper().startswith("KILL")
    return False


def ask_oracle_order(ask_fn, context_text):
    """One bounded judgment call. Returns (decision, reason).

    decision is "kill", "spare", or "abstain". A timeout, an
    error, or no callable at all is an abstention, recorded as
    such by the caller; an abstention never kills.
    """
    if ask_fn is None:
        return ("abstain", "no inference configured")
    try:
        answer = ask_fn(ORACLE_QUESTION, context_text)
    except Exception as e:
        return ("abstain", f"inference error: {e}"[:200])
    if not isinstance(answer, str) or not answer.strip():
        return ("abstain", "no answer from the model")
    if parse_oracle_order(answer):
        return ("kill", answer.strip()[:300])
    return ("spare", answer.strip()[:300])


# ------------------------------------------------------------ quarantine
#
# Quarantine moves, never deletes. A seized job lives at
# <base>/quarantine/<job_id>/ holding remediation.json (the
# marker) and work/ (the job's workdir, moved whole). Release
# moves work/ back out and leaves the marker with it. Bounds
# archive the oldest seizures to <base>/quarantine-archive/ --
# again a move.

def quarantine_root(base_dir):
    return os.path.join(base_dir, QUARANTINE_DIR)


def _dir_bytes(path):
    total = 0
    for dirpath, _dirs, names in os.walk(path):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                continue
    return total


def _work_file_list(work):
    out = []
    for dirpath, _dirs, names in os.walk(work):
        for name in names:
            path = os.path.join(dirpath, name)
            try:
                rel = os.path.relpath(path, work)
            except ValueError:
                rel = name
            out.append(rel.replace("\\", "/"))
    return sorted(out)


def quarantine_job(base_dir, job_id, work_dir, marker):
    """Move the job's workdir into quarantine. Returns the
    quarantine job dir, or None when there was nothing to move
    or the move failed. Never raises."""
    job_id = _safe_job_id(job_id)
    if not job_id or not isinstance(work_dir, str) \
            or not os.path.isdir(work_dir):
        return None
    root = quarantine_root(base_dir)
    try:
        os.makedirs(root, exist_ok=True)
        dest = os.path.join(root, job_id)
        n = 2
        while os.path.exists(dest):
            dest = os.path.join(root, f"{job_id}-{n}")
            n += 1
        os.makedirs(dest)
        shutil.move(work_dir, os.path.join(dest, "work"))
    except (OSError, shutil.Error):
        return None
    record = dict(marker) if isinstance(marker, dict) else {}
    record.setdefault("job_id", job_id)
    record["quarantined_at"] = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record["files"] = _work_file_list(os.path.join(dest, "work"))
    try:
        # Whole or not at all: a kill mid-write used to leave a
        # truncated marker beside a seized workdir (guard/atomicio).
        _atomicio.write_json(os.path.join(dest, "remediation.json"),
                             record, indent=1, fsync=True)
    except (OSError, TypeError, ValueError):
        pass
    return dest


def fix_marker_digest(base_dir, job_id, digest):
    """Correct a quarantine marker's received_digest in place.

    execute_job digests the job it ran; when an opinion repair
    changed that job, the ingest handler -- the one place that
    still holds the job as received -- rewrites the marker so
    the operator's copy names the same digest as the result.
    Never raises.
    """
    marker = load_marker(base_dir, job_id)
    if marker is None or marker.get("received_digest") == digest:
        return
    marker["received_digest"] = digest
    job_id = _safe_job_id(job_id)
    if not job_id:
        return
    path = os.path.join(quarantine_root(base_dir), job_id,
                        "remediation.json")
    try:
        # The operator's evidence record: replaced whole, fsynced.
        _atomicio.write_json(path, marker, indent=1, fsync=True)
    except (OSError, TypeError, ValueError):
        pass


def load_marker(base_dir, job_id):
    job_id = _safe_job_id(job_id)
    if not job_id:
        return None
    path = os.path.join(quarantine_root(base_dir), job_id,
                        "remediation.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def enforce_quarantine_bounds(base_dir, st):
    """Archive the oldest seizures past the count/byte ceilings.

    Archiving is a move to quarantine-archive/, never a delete.
    Returns the job ids archived. Never raises.
    """
    root = quarantine_root(base_dir)
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    entries = []
    for name in names:
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0.0
        entries.append((mtime, name, path))
    entries.sort()
    total = sum(_dir_bytes(p) for _m, _n, p in entries)
    archived = []
    archive_root = os.path.join(base_dir, QUARANTINE_ARCHIVE_DIR)
    while entries and (len(entries) > st["quarantine_max_jobs"]
                       or total > st["quarantine_max_bytes"]):
        _mtime, name, path = entries.pop(0)
        size = _dir_bytes(path)
        try:
            os.makedirs(archive_root, exist_ok=True)
            stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
            dest = os.path.join(archive_root, f"{name}-{stamp}")
            n = 2
            while os.path.exists(dest):
                dest = os.path.join(archive_root, f"{name}-{stamp}-{n}")
                n += 1
            shutil.move(path, dest)
            archived.append(name)
            total -= size
        except (OSError, shutil.Error):
            break
    return archived


def release_quarantine(base_dir, job_id):
    """The owner's release: restore a quarantined job's outputs.

    Moves quarantine/<job_id>/work back to work/<job_id> when
    that path is free, else to released/<job_id>-<stamp>. The
    marker rides with the files, plus released_at. Returns
    {"restored_to", "marker"} or None. Never raises.
    """
    job_id = _safe_job_id(job_id)
    if not job_id:
        return None
    src_dir = os.path.join(quarantine_root(base_dir), job_id)
    work = os.path.join(src_dir, "work")
    if not os.path.isdir(work):
        return None
    marker = load_marker(base_dir, job_id) or {"job_id": job_id}
    dest = os.path.join(base_dir, "work", job_id)
    try:
        if os.path.exists(dest):
            stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
            os.makedirs(os.path.join(base_dir, "released"),
                        exist_ok=True)
            dest = os.path.join(base_dir, "released",
                                f"{job_id}-{stamp}")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(work, dest)
    except (OSError, shutil.Error):
        return None
    marker = dict(marker)
    marker["released_at"] = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        _atomicio.write_json(os.path.join(dest, "remediation-marker.json"),
                             marker, indent=1, fsync=True)
    except (OSError, TypeError, ValueError):
        pass
    try:
        marker_src = os.path.join(src_dir, "remediation.json")
        if os.path.exists(marker_src):
            os.remove(marker_src)
        os.rmdir(src_dir)
    except OSError:
        pass
    return {"restored_to": dest, "marker": marker}


# ------------------------------------------------------------ antivirus referral
#
# The referral asks; it does not instruct. A consumer antivirus
# accepts a scan request on an exact path; its verdict --
# confirmed, clean, unavailable -- is recorded beside the
# Oracle's judgment, each attributed to its own witness.

def find_mpcmdrun(environ=None, which=None, exists=None,
                  listdir=None):
    """Locate MpCmdRun.exe across the Defender install layouts.

    Candidates, in order: PATH; the classic Windows Defender
    folder under %ProgramFiles%; the Platform/<version> folders
    under %ProgramData%/Microsoft/Windows Defender (newest
    version first). None when Defender is not on the box.
    """
    environ = os.environ if environ is None else environ
    which = shutil.which if which is None else which
    exists = os.path.exists if exists is None else exists
    listdir = os.listdir if listdir is None else listdir
    try:
        on_path = which("MpCmdRun.exe")
    except Exception:
        on_path = None
    if on_path:
        return on_path
    pf = environ.get("ProgramFiles") or ""
    if pf:
        cand = os.path.join(pf, "Windows Defender", "MpCmdRun.exe")
        if exists(cand):
            return cand
    pd = environ.get("ProgramData") or ""
    if pd:
        plat = os.path.join(pd, "Microsoft", "Windows Defender",
                            "Platform")
        try:
            versions = sorted(listdir(plat), reverse=True)
        except OSError:
            versions = []
        for ver in versions:
            cand = os.path.join(plat, ver, "MpCmdRun.exe")
            if exists(cand):
                return cand
    return None


def mpcmdrun_verdict(exit_code):
    """MpCmdRun scan exit code -> verdict.

    Per the vendor documentation: 0 is a completed scan with no
    threat found; 2 is a completed scan that found (and acted
    on) malware. Every other code is an error or a partial
    state this runner does not read as a verdict. Field
    verification on a real Windows box is still owed (see the
    design's narrowed open item). Pure.
    """
    if exit_code == 0:
        return "clean"
    if exit_code == 2:
        return "confirmed"
    return None


def clamdscan_verdict(exit_code):
    """clamdscan exit code -> verdict, per its manual:
    0 no virus, 1 virus found, 2 an error occurred. Pure."""
    if exit_code == 0:
        return "clean"
    if exit_code == 1:
        return "confirmed"
    return None


def av_referral(paths, run=None, which=None, os_name=None,
                mpcmdrun_path=None):
    """Ask the box's antivirus about the suspect files.

    Returns (verdict, detail): verdict is confirmed when any
    file confirms, else clean when any file scanned clean, else
    unavailable -- no AV, or every scan errored. Unavailable is
    a fact in the record, not an error. Never raises.
    """
    run = subprocess.run if run is None else run
    which = shutil.which if which is None else which
    os_name = os.name if os_name is None else os_name
    targets = [p for p in (paths or []) if isinstance(p, str) and p]
    targets = targets[:AV_MAX_FILES]
    if not targets:
        return ("unavailable", "no suspect files to refer")
    if os_name == "nt":
        exe = mpcmdrun_path or find_mpcmdrun(which=which)
        if not exe:
            return ("unavailable", "no Defender MpCmdRun on this box")
        tool, verdict_of = "defender", mpcmdrun_verdict

        def argv_for(path):
            return [exe, "-Scan", "-ScanType", "3", "-File", path]
    else:
        exe = which("clamdscan")
        if not exe:
            return ("unavailable", "no clamdscan on this box")
        tool, verdict_of = "clamdscan", clamdscan_verdict

        def argv_for(path):
            return [exe, "--no-summary", path]
    saw_clean = False
    notes = []
    for path in targets:
        try:
            proc = run(argv_for(path), stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=AV_TIMEOUT_SEC)
            code = proc.returncode
        except Exception as e:
            notes.append(f"{os.path.basename(path)}: scan failed ({e})")
            continue
        verdict = verdict_of(code)
        notes.append(f"{os.path.basename(path)}: exit {code}")
        if verdict == "confirmed":
            return ("confirmed", f"{tool}: " + "; ".join(notes))
        if verdict == "clean":
            saw_clean = True
    if saw_clean:
        return ("clean", f"{tool}: " + "; ".join(notes))
    return ("unavailable", f"{tool}: " + "; ".join(notes))


# ------------------------------------------------------------ the record

def result_member(mode, authority, div, act, av_verdict, digest):
    """The remediation member for the result (PROTOCOL 3.2).

    Exactly the design's shape; received_digest is the digest
    of the job as received (see received_digest).
    """
    return {
        "mode": mode,
        "authority": authority,
        "divergence": divergence_text(div),
        "act": act,
        "av_verdict": av_verdict,
        "received_digest": digest,
    }


# ------------------------------------------------------------ the monitor

class JobMonitor:
    """Watches one running job against its envelope.

    A daemon thread samples the job's process tree and its
    workdir on the settings cadence. Tripwires act at once
    (kill via the injected kill_fn) in deterministic and
    oracle modes. Lesser divergences go to the authority
    layer: in oracle mode, one bounded judgment call per kind
    via the injected ask_fn; in off mode, one page request.
    Nothing here raises: failures land in outcome["errors"].

    outcome keys:
      divergences -- every divergence observed, in order
      acted       -- {"authority", "divergence"} once an act was
                     ordered, else None
      oracle      -- [{divergence, decision, reason}] per call
      page        -- the first divergence in off mode, else None
      suspects    -- workdir-relative paths whose content tripped
                     the credential tripwire class
    """

    def __init__(self, st, job_id, root_pid, work_dir,
                 declared_paths=(), declared_credential_paths=(),
                 initial_files=(), kill_fn=None, ask_fn=None,
                 findings_fn=None, alerts_fn=None, sampler=None,
                 base_dir=None, envelope_note=""):
        self._st = st
        self.job_id = job_id
        self.root_pid = root_pid
        self.work_dir = work_dir
        self.base_dir = base_dir
        self._declared = set(declared_paths or ())
        self._declared_cred = set(declared_credential_paths or ())
        self._initial = set(initial_files or ())
        self._kill_fn = kill_fn
        self._ask_fn = ask_fn
        self._findings_fn = findings_fn
        self._alerts_fn = alerts_fn
        self._sampler = sampler or sample_tree
        self._envelope_note = envelope_note or ""
        self._signals = TreeSignals(total_mem=total_memory_bytes())
        self._sealed = False     # final scan: record, never act
        self._stop = threading.Event()
        self._thread = None
        self._started_wall = time.time()
        self._scanned = {}        # path -> (size, mtime_ns)
        self._seen_kinds = set()  # (kind, detail) already handled
        self._asked_kinds = set()
        self._cage_checked = False
        self._resource_checked = False
        self.outcome = {
            "divergences": [],
            "acted": None,
            "oracle": [],
            "page": None,
            "suspects": [],
            "errors": [],
        }

    # -- lifecycle -------------------------------------------------

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name=f"remediation-{self.job_id}",
            daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self):
        while not self._stop.is_set():
            try:
                self.sample_once()
            except Exception as e:
                self._error(e)
            if self.outcome["acted"] is not None:
                return
            self._stop.wait(self._st["sample_sec"])

    def _error(self, e):
        errors = self.outcome["errors"]
        if len(errors) < 8:
            errors.append(str(e)[:200])

    # -- one pass ----------------------------------------------------

    def sample_once(self):
        """One observation pass. Also callable directly by tests."""
        try:
            sample = self._sampler(self.root_pid)
        except Exception as e:
            self._error(e)
            sample = {self.root_pid: (0.0, None)}
        pids = sorted(sample.keys())
        if len(pids) > self._st["storm_ceiling"]:
            self._handle(divergence(
                "process_storm",
                f"job tree holds {len(pids)} processes, past "
                f"the ceiling of {self._st['storm_ceiling']}"))
            if self.outcome["acted"] is not None:
                return
        workdir_bytes = self._scan_workdir()
        for div in self._signals.feed(sample, time.monotonic(),
                                      workdir_bytes):
            self._handle(div)
        self._check_window_evidence(pids)

    def final_scan(self):
        """One last workdir pass after the job has exited.

        A short job can write a tripping artifact and finish
        inside one sample interval; the scan still sees it.
        New divergences are recorded; the caller decides the
        acts (there is nothing left to kill).
        """
        self._sealed = True
        self._scan_workdir()

    # -- pieces ------------------------------------------------------

    def _scan_workdir(self):
        """Scan produced files; returns the workdir's byte total."""
        total = 0
        seen_now = {}
        try:
            walker = os.walk(self.work_dir)
        except OSError:
            return 0
        for dirpath, _dirs, names in walker:
            for name in names:
                path = os.path.join(dirpath, name)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                total += st.st_size
                seen_now[path] = (st.st_size,
                                  getattr(st, "st_mtime_ns", 0))
        if self.outcome["acted"] is None:
            for path, meta in sorted(seen_now.items()):
                if path in self._initial:
                    continue
                if self._scanned.get(path) == meta:
                    continue
                self._scanned[path] = meta
                self._scan_file(path)
                if self.outcome["acted"] is not None:
                    break
        return total

    def _scan_file(self, path):
        if self._findings_fn is None:
            return
        try:
            if os.path.getsize(path) > ARTIFACT_READ_CAP:
                return
            with open(path, "rb") as fh:
                raw = fh.read(ARTIFACT_READ_CAP)
            text = raw.decode("utf-8")  # binary artifacts: no scan
        except (OSError, UnicodeDecodeError):
            return
        try:
            findings = self._findings_fn(text)
        except Exception as e:
            self._error(e)
            return
        tripwire, divs = classify_findings(
            findings, self._declared, self._declared_cred)
        if tripwire is not None:
            try:
                rel = os.path.relpath(path, self.work_dir)
            except ValueError:
                rel = os.path.basename(path)
            if rel not in self.outcome["suspects"]:
                self.outcome["suspects"].append(rel)
            self._handle(tripwire)
        for div in divs:
            self._handle(div)

    def _check_window_evidence(self, pids):
        if not self.base_dir:
            return
        if not self._cage_checked:
            self._cage_checked = True
            try:
                for rec in confinement_events_in_window(
                        self.base_dir, self.job_id, self._started_wall):
                    decision = rec.get("decision") or ""
                    if decision == "denied":
                        self._handle(divergence(
                            "confinement_escape",
                            "the cage reported a denial for this job"))
                    elif decision == "fallback":
                        self._handle(divergence(
                            "confinement_strain",
                            "confinement was requested but the job "
                            "is running uncaged "
                            f"({rec.get('reason') or 'fallback'})"))
            except Exception as e:
                self._error(e)
        if not self._resource_checked:
            self._resource_checked = True
            try:
                events = resource_events_in_window(
                    self.base_dir, self._started_wall)
            except Exception as e:
                self._error(e)
                events = []
            if events:
                self._handle(divergence(
                    "resource_event",
                    f"{len(events)} resource-pressure event(s) "
                    f"inside this job's window"))
        if self._alerts_fn is not None:
            try:
                since = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(self._started_wall - 1.0))
                alerts = self._alerts_fn(since) or []
            except Exception as e:
                self._error(e)
                alerts = []
            for alert in alerts:
                if alert_names_job(alert, self.job_id, self.work_dir,
                                   pids):
                    title = str(alert.get("title") or
                                alert.get("signal") or "alert")[:120]
                    self._handle(divergence(
                        "sense_alert",
                        f"a sense fired about this job: {title}"))
                    break

    # -- the authority layer ------------------------------------------

    def _handle(self, div):
        key = (div["kind"], div["detail"])
        if key in self._seen_kinds:
            return
        self._seen_kinds.add(key)
        self.outcome["divergences"].append(div)
        mode = self._st["mode"]
        if self._sealed:
            # The job has already exited: the divergence is
            # recorded (and paged, in off mode); acting on it is
            # the caller's call, with the acts that still apply.
            if mode == "off" and self.outcome["page"] is None:
                self.outcome["page"] = div
            return
        if mode == "off":
            if self.outcome["page"] is None:
                self.outcome["page"] = div
            return
        if self.outcome["acted"] is not None:
            return
        if div["tripwire"]:
            self.outcome["acted"] = {
                "authority": "tripwire", "divergence": div}
            self._kill()
            return
        if mode == "oracle" and div["kind"] not in self._asked_kinds:
            self._asked_kinds.add(div["kind"])
            context = (
                f"Job {self.job_id}. Divergence: "
                f"{divergence_text(div)}. Intent envelope: "
                f"{self._envelope_note or 'no declared paths'}. "
                f"Divergences so far: "
                + "; ".join(divergence_text(d)
                            for d in self.outcome["divergences"]))
            decision, reason = ask_oracle_order(self._ask_fn, context)
            self.outcome["oracle"].append({
                "divergence": divergence_text(div),
                "decision": decision, "reason": reason})
            if decision == "kill":
                self.outcome["acted"] = {
                    "authority": "oracle", "divergence": div}
                self._kill()

    def _kill(self):
        if self._kill_fn is None:
            return
        try:
            sample = self._sampler(self.root_pid)
            extra = [pid for pid in sample.keys()
                     if pid != self.root_pid]
        except Exception:
            extra = []
        try:
            self._kill_fn(extra)
        except Exception as e:
            self._error(e)
