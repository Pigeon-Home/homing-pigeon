#!/usr/bin/env python3
"""Crude Windows containment via built-in Win32 Job Objects.

No external dependencies. Phase 1 implements exactly one control: a
Job Object with a per-process memory ceiling, assigned to the job's
process after it starts. That is the whole of what this backend does.

What is NOT implemented, and must never be recorded as applied: a
restricted token, a low-integrity level, CPU or process-count
ceilings, and any filesystem or network isolation. The POSIX demote
(job_user's setuid drop) has no Windows equivalent here; this backend
serves the job_user seam only -- the confinement mode's sandbox
(bwrap namespaces) remains Linux-only, and confinement at enforce on
Windows still refuses at startup.

Handle lifetime: apply_windows_containment returns the job handle
with the status. The caller owns it and closes it with
close_job_handle once the job's process has exited. The limits live
exactly as long as the handle stays open (JOB_OBJECT_LIMIT_KILL_ON_
JOB_CLOSE means closing the last handle also ends anything still in
the job), so the handle must not be closed while the process runs,
and must not simply be dropped -- an unclosed handle is a leak in a
long-running runner.

This module is import-safe on non-Windows; functions that need the
APIs raise or return a problem string when called off win32.
"""
import ctypes
import sys
from ctypes import wintypes

# The one ceiling Phase 1 sets: 512 MiB of committed memory per job
# process. A named constant, not a config knob yet.
DEFAULT_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024

# The status string for the control actually applied. Audit records
# carry this and nothing stronger: it names the Job Object alone.
STATUS_JOB_OBJECT = "windows_job_object"

if sys.platform != "win32":
    # Stub so the rest of the runner can import without error. The
    # startup probe answers a problem string (never None), so an
    # enforce gate consulting this stub refuses, and apply raises:
    # off Windows this backend can never claim to have engaged.
    def windows_startup_problem(*args, **kwargs):
        return "windows_confine is Windows-only"

    def apply_windows_containment(*args, **kwargs):
        raise RuntimeError("windows_confine is Windows-only")

    def close_job_handle(handle):
        return None
else:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    # Typed bindings: HANDLE results must be declared, or ctypes
    # returns a 32-bit int and truncates the handle on 64-bit
    # Windows.
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID,
                                          wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE,
                                                  wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    # Constants
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    def _create_job_with_limits(memory_bytes):
        """(handle, None) with the memory ceiling set, or
        (None, problem). The last-error is read immediately after
        the failing call, before any CloseHandle can overwrite it.
        """
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None, "CreateJobObjectW failed: %d" % (
                ctypes.get_last_error(),)
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | JOB_OBJECT_LIMIT_JOB_MEMORY
            | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        info.ProcessMemoryLimit = int(memory_bytes)
        info.JobMemoryLimit = int(memory_bytes)
        if not kernel32.SetInformationJobObject(
            job, JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info)
        ):
            err = ctypes.get_last_error()
            kernel32.CloseHandle(job)
            return None, "SetInformationJobObject failed: %d" % err
        return job, None

    def windows_startup_problem(cfg=None, timeout=15):
        """None if a Job Object with the memory ceiling can be
        created on this host, else why not.

        This is a necessary condition, not a sufficient one: it
        proves creation and limit-setting work. Assigning a
        particular job process can still fail at job time (a
        process already inside a job that forbids breakaway is the
        known shape), and that failure refuses the job then -- the
        probe never stands in for the assignment.
        """
        job, problem = _create_job_with_limits(
            DEFAULT_PROCESS_MEMORY_BYTES)
        if problem is not None:
            return problem
        kernel32.CloseHandle(job)
        return None

    def apply_windows_containment(proc_handle,
                                  memory_bytes=DEFAULT_PROCESS_MEMORY_BYTES):
        """Assign the process behind `proc_handle` to a fresh Job
        Object carrying the memory ceiling.

        Returns (STATUS_JOB_OBJECT, job_handle) on success; the
        caller owns the job handle (see the module docstring).
        Raises RuntimeError whenever the control was not applied --
        there is no partial success to record.
        """
        if not proc_handle:
            raise RuntimeError(
                "no process handle to contain; nothing was applied")
        job, problem = _create_job_with_limits(memory_bytes)
        if problem is not None:
            raise RuntimeError(problem)
        if not kernel32.AssignProcessToJobObject(job, proc_handle):
            err = ctypes.get_last_error()
            kernel32.CloseHandle(job)
            raise RuntimeError(
                "AssignProcessToJobObject failed: %d" % err)
        return STATUS_JOB_OBJECT, job

    def close_job_handle(handle):
        """Close a job handle returned by apply_windows_containment.

        Called once the contained process has exited: closing the
        last handle ends the job (KILL_ON_JOB_CLOSE), which is a
        no-op for an exited process and a backstop for anything it
        left running inside the job.
        """
        if handle:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
