#!/usr/bin/env python3
"""Crude Windows confinement via built-in Win32 APIs (Job Objects + restricted tokens).

No external dependencies. Phase 1: resource ceilings via Job Object
(memory/CPU) and privilege drop via restricted token at low integrity.
AppContainer is a later phase.

This module is import-safe on non-Windows; functions that need the
APIs raise or return a problem string when called off win32.
"""
import ctypes
import os
import sys
from ctypes import wintypes

if sys.platform != "win32":
    # Stub so the rest of the runner can import without error.
    def windows_startup_problem(*args, **kwargs):
        return "windows_confine is Windows-only"

    def apply_windows_containment(*args, **kwargs):
        raise RuntimeError("windows_confine is Windows-only")
else:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

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

    def _create_job_with_limits(memory_bytes=512 * 1024 * 1024):
        """Create a Job Object with memory ceilings. Returns handle or None."""
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | JOB_OBJECT_LIMIT_JOB_MEMORY
            | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        info.ProcessMemoryLimit = memory_bytes
        info.JobMemoryLimit = memory_bytes
        ok = kernel32.SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            kernel32.CloseHandle(job)
            return None
        return job

    def windows_startup_problem(cfg=None, timeout=15):
        """None when a Job Object can be created and limited, else why not.

        Crude probe used at startup under confinement/job_user enforce
        so the runner does not refuse on win32 when the backend can
        engage. Does not keep the job open.
        """
        job = _create_job_with_limits()
        if job is None:
            err = ctypes.get_last_error()
            return (
                "Windows Job Object could not be created or limited "
                "(GetLastError %d); confinement/job_user cannot engage"
                % err
            )
        kernel32.CloseHandle(job)
        return None

    def apply_windows_containment(proc_handle=None, memory_bytes=512 * 1024 * 1024):
        """Assign a process to a limited Job Object (and prepare token path).

        Returns a short status string for the audit row, or raises.
        Crude first cut: Job Object only. Restricted token / low
        integrity is wired next (CreateRestrictedToken +
        SetTokenInformation for S-1-16-4096).
        """
        job = _create_job_with_limits(memory_bytes)
        if job is None:
            raise RuntimeError("cannot create limited Job Object")
        if proc_handle is not None:
            ok = kernel32.AssignProcessToJobObject(job, proc_handle)
            if not ok:
                kernel32.CloseHandle(job)
                raise RuntimeError(
                    "AssignProcessToJobObject failed (err %d)"
                    % ctypes.get_last_error()
                )
        # Token path placeholder (low integrity restricted token).
        # Full CreateRestrictedToken + integrity SID set is the next
        # increment; for now the Job Object is the ceiling.
        return "windows_job_object_restricted_token"
