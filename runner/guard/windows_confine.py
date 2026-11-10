#!/usr/bin/env python3
"""Windows containment: Job Objects, and the confinement backend.

No external dependencies. Two seams use this module:

- job_user (Phase 1): a Job Object with a per-process memory
  ceiling, assigned to the job's process after it starts. The
  status string for that control alone is STATUS_JOB_OBJECT.

- confinement (Phase 2): the controls named by STATUS_CONFINEMENT
  -- "windows: job_object + restricted_token + low_integrity".
  A job process is created suspended with CreateProcessAsUserW
  under a restricted token derived from the runner's own token
  (CreateRestrictedToken with DISABLE_MAX_PRIVILEGE, which strips
  every privilege except SeChangeNotify, and the Administrators
  group disabled), with the token's mandatory integrity level set
  to Low, and is assigned to the Job Object (the same memory
  ceiling) before it is resumed. There is no race in which the
  job runs unconfined: the process does not execute a line until
  every control is in place.

What this is NOT, stated plainly wherever it is recorded: it is
not a sandbox in the Linux sense. There is no filesystem
namespace isolation: a confined job can still READ any path its
token can read. Low integrity stops the job writing to medium-
or higher-integrity objects outside its workspace (the workspace
directory is labelled Low before spawn so the job can write its
own outputs); it does not hide the filesystem. AppContainer
remains the future path to confinement parity on Windows.

Supposition for Q134, recorded before the field test that
settles it (an unelevated standard user on the Germany rig, a
throwaway account with its temp tree under its own profile --
the hosted CI runner's shape): the shipped spawn, engaged
there, reproduces the CI failure -- a confined PowerShell -File
job exits nonzero reporting the staged script does not exist,
while the same argv unconfined exits 0 -- even though the
creation probe above passes on that host. The isolation runs
spawn variants down the same creation path: the restricted
token at the caller's own integrity level, the caller's token
at Low, and the shipped token with the staged file itself
labelled Low. My lean, stated so the measurement can prove it
wrong: the denial is the restricted token's side of the pair,
not the label's -- integrity policy alone allows a Low process
to read up (only write-up is blocked by the default policy),
so a full token at Low should still read the staged file,
while the restricted token should fail at either integrity.
Whatever the isolation shows, the confinement probe becomes a
trial: it will spawn a confined process that reads a staged
file and writes its work directory, and name the failure, so a
host that cannot work confined refuses at startup instead of
failing every job. Conclusions from the field test are
recorded with the answer to Q134.

Handle lifetime: apply_windows_containment returns the job handle
with the status; the caller owns it and closes it with
close_job_handle once the job's process has exited. A confined
spawn's process object owns its handles; its release callable
(WindowsConfinedProcess.close) closes the Job Object handle --
closing the last handle ends the job (JOB_OBJECT_LIMIT_KILL_ON_
JOB_CLOSE) -- and the process and pipe handles.

Supposition, recorded before the field test on a real Windows
host (the Germany rig, Windows Server 2022): before this backend,
confinement at enforce on win32 refused at startup ("confinement
(bwrap) is Linux-only; this machine is win32"). After it, the
startup probe -- Job Object creation plus restricted-token
creation plus the integrity-level set, each on a throwaway
handle -- returns None on a host where those calls work, the
runner starts with every security mode at enforce, and a job's
audit record names STATUS_CONFINEMENT. Token creation for one's
own process needs no administrator rights; the probe, not an
assumption, is what the gate consults.

This module is import-safe on non-Windows; functions that need
the APIs raise or return a problem string when called off win32.
The stub/real branch below keys on the host's ctypes surface as
well as the platform string, so import stays safe under the
suite's simulated win32 (sys.platform patched on a POSIX host)
as well: a simulated platform cannot bind Windows APIs the host
does not have.
"""
import ctypes
import subprocess
import sys
import threading
from ctypes import wintypes

# The one ceiling Phase 1 sets: 512 MiB of committed memory per job
# process. A named constant, not a config knob yet.
DEFAULT_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024

# The status string for the Job Object control alone (job_user).
STATUS_JOB_OBJECT = "windows_job_object"

# The confinement controls, named exactly. Every audit and
# startup record for Windows confinement carries this string and
# nothing stronger: no record calls this a sandbox.
STATUS_CONFINEMENT = "windows: job_object + restricted_token + low_integrity"
CONFINEMENT_CONTROLS = ("job_object", "restricted_token", "low_integrity")

if sys.platform != "win32" or not hasattr(ctypes, "WinDLL"):
    # Stub so the rest of the runner can import without error. The
    # startup probes answer a problem string (never None), so an
    # enforce gate consulting this stub refuses, and apply/spawn
    # raise: off Windows this backend can never claim to have
    # engaged. IS_WINDOWS_BACKEND is how the gates tell this stub
    # from the real implementation below: only a real backend's
    # probe is ever consulted, so a simulated win32 answers the
    # refusal deterministically on any host.
    #
    # The branch follows the host's Windows API surface, not the
    # platform string alone: the suite simulates win32 by patching
    # sys.platform on POSIX hosts, and a first import under that
    # patch must still land here -- the host has no ctypes.WinDLL
    # to bind, and reaching for it raised AttributeError at import
    # (through main(), in the simulated-win32 startup tests). On
    # a real Windows host sys.platform is "win32" and ctypes
    # always carries WinDLL, so the real implementation below is
    # taken exactly as before.
    IS_WINDOWS_BACKEND = False

    def windows_startup_problem(*args, **kwargs):
        return "windows_confine is Windows-only"

    def windows_confinement_problem(*args, **kwargs):
        return "windows_confine is Windows-only"

    def apply_windows_containment(*args, **kwargs):
        raise RuntimeError("windows_confine is Windows-only")

    def spawn_confined_process(*args, **kwargs):
        raise RuntimeError("windows_confine is Windows-only")

    def close_job_handle(handle):
        return None
else:
    IS_WINDOWS_BACKEND = True

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

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
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.CreatePipe.restype = wintypes.BOOL
    kernel32.CreatePipe.argtypes = [ctypes.POINTER(wintypes.HANDLE),
                                    ctypes.POINTER(wintypes.HANDLE),
                                    wintypes.LPVOID, wintypes.DWORD]
    kernel32.SetHandleInformation.restype = wintypes.BOOL
    kernel32.SetHandleInformation.argtypes = [wintypes.HANDLE,
                                              wintypes.DWORD,
                                              wintypes.DWORD]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
        wintypes.HANDLE]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
                                  wintypes.DWORD,
                                  ctypes.POINTER(wintypes.DWORD),
                                  wintypes.LPVOID]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE,
                                             wintypes.DWORD]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE,
                                          ctypes.c_uint]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]

    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE)]
    advapi32.CreateRestrictedToken.restype = wintypes.BOOL
    advapi32.CreateRestrictedToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.LPVOID,
        ctypes.POINTER(wintypes.HANDLE)]
    advapi32.SetTokenInformation.restype = wintypes.BOOL
    advapi32.SetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
        wintypes.DWORD]
    advapi32.CreateProcessAsUserW.restype = wintypes.BOOL
    advapi32.CreateProcessAsUserW.argtypes = [
        wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPWSTR,
        wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL,
        wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
        wintypes.LPVOID, wintypes.LPVOID]
    advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL
    advapi32.ConvertStringSidToSidW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPVOID)]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype \
        = wintypes.BOOL
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD)]
    advapi32.GetSecurityDescriptorSacl.restype = wintypes.BOOL
    advapi32.GetSecurityDescriptorSacl.argtypes = [
        wintypes.LPVOID, ctypes.POINTER(wintypes.BOOL),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.BOOL)]
    advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi32.SetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
        wintypes.LPVOID, wintypes.LPVOID, wintypes.LPVOID,
        wintypes.LPVOID]

    # Constants
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9

    TOKEN_DUPLICATE = 0x0002
    TOKEN_ASSIGN_PRIMARY = 0x0001
    TOKEN_QUERY = 0x0008
    TOKEN_ADJUST_DEFAULT = 0x0080
    DISABLE_MAX_PRIVILEGE = 0x00000001
    TokenIntegrityLevel = 25
    SE_GROUP_INTEGRITY = 0x00000020
    ADMINISTRATORS_SID = "S-1-5-32-544"
    LOW_INTEGRITY_SID = "S-1-16-4096"

    CREATE_SUSPENDED = 0x00000004
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    STARTF_USESTDHANDLES = 0x00000100
    HANDLE_FLAG_INHERIT = 0x00000001
    WAIT_OBJECT_0 = 0x00000000
    WAIT_TIMEOUT = 0x00000102
    INFINITE = 0xFFFFFFFF
    STILL_ACTIVE = 259
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    SE_FILE_OBJECT = 1
    LABEL_SECURITY_INFORMATION = 0x00000010
    SDDL_REVISION_1 = 1
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

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

    class SID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Sid", wintypes.LPVOID),
                    ("Attributes", wintypes.DWORD)]

    class TOKEN_MANDATORY_LABEL(ctypes.Structure):
        _fields_ = [("Label", SID_AND_ATTRIBUTES)]

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD),
                    ("lpSecurityDescriptor", wintypes.LPVOID),
                    ("bInheritHandle", wintypes.BOOL)]

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [("hProcess", wintypes.HANDLE),
                    ("hThread", wintypes.HANDLE),
                    ("dwProcessId", wintypes.DWORD),
                    ("dwThreadId", wintypes.DWORD)]

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

    def _sid_from_string(text):
        """A PSID the caller frees with LocalFree, or (None, problem)."""
        sid = wintypes.LPVOID()
        if not advapi32.ConvertStringSidToSidW(text, ctypes.byref(sid)):
            return None, "ConvertStringSidToSidW(%s) failed: %d" % (
                text, ctypes.get_last_error())
        return sid, None

    def _create_restricted_low_token():
        """(token_handle, None) or (None, problem).

        The token is the runner's own, restricted: every privilege
        except SeChangeNotify stripped (DISABLE_MAX_PRIVILEGE), the
        Administrators group disabled (a job never inherits the
        runner's admin group), and the mandatory integrity level
        set to Low. The caller owns the handle.
        """
        src = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(
                kernel32.GetCurrentProcess(),
                TOKEN_DUPLICATE | TOKEN_ASSIGN_PRIMARY | TOKEN_QUERY
                | TOKEN_ADJUST_DEFAULT, ctypes.byref(src)):
            return None, "OpenProcessToken failed: %d" % (
                ctypes.get_last_error(),)
        try:
            admin_sid, problem = _sid_from_string(ADMINISTRATORS_SID)
            if problem is not None:
                return None, problem
            try:
                disable = SID_AND_ATTRIBUTES()
                disable.Sid = admin_sid
                disable.Attributes = 0
                token = wintypes.HANDLE()
                if not advapi32.CreateRestrictedToken(
                        src, DISABLE_MAX_PRIVILEGE, 1,
                        ctypes.byref(disable), 0, None, 0, None,
                        ctypes.byref(token)):
                    return None, "CreateRestrictedToken failed: %d" % (
                        ctypes.get_last_error(),)
            finally:
                kernel32.LocalFree(admin_sid)
            low_sid, problem = _sid_from_string(LOW_INTEGRITY_SID)
            if problem is not None:
                kernel32.CloseHandle(token)
                return None, problem
            try:
                label = TOKEN_MANDATORY_LABEL()
                label.Label.Sid = low_sid
                label.Label.Attributes = SE_GROUP_INTEGRITY
                if not advapi32.SetTokenInformation(
                        token, TokenIntegrityLevel, ctypes.byref(label),
                        ctypes.sizeof(label) + 64):
                    err = ctypes.get_last_error()
                    kernel32.CloseHandle(token)
                    return None, "SetTokenInformation(" \
                        "TokenIntegrityLevel) failed: %d" % err
            finally:
                kernel32.LocalFree(low_sid)
            return token, None
        finally:
            kernel32.CloseHandle(src)

    def _set_low_integrity_label(path):
        """Best effort: label a directory Low integrity so a
        low-integrity job can write inside its own workspace.
        Returns True when the label was set. Failure is not fatal
        to the spawn -- the job still runs confined; writes to
        that directory are then the integrity policy's answer,
        and the job's result records it -- but the caller may log
        it. Never raises.
        """
        try:
            sd = wintypes.LPVOID()
            if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                    "S:(ML;;NW;;;LW)", SDDL_REVISION_1,
                    ctypes.byref(sd), None):
                return False
            try:
                present = wintypes.BOOL()
                defaulted = wintypes.BOOL()
                sacl = wintypes.LPVOID()
                if not advapi32.GetSecurityDescriptorSacl(
                        sd, ctypes.byref(present), ctypes.byref(sacl),
                        ctypes.byref(defaulted)):
                    return False
                if not present or not sacl:
                    return False
                rc = advapi32.SetNamedSecurityInfoW(
                    ctypes.create_unicode_buffer(path), SE_FILE_OBJECT,
                    LABEL_SECURITY_INFORMATION, None, None, None, sacl)
                return rc == 0
            finally:
                kernel32.LocalFree(sd)
        except Exception:
            return False

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

    def windows_confinement_problem(cfg=None, timeout=15):
        """None when the confinement controls can engage here.

        Stronger than the job_user probe: a Job Object with the
        memory ceiling, AND a restricted token with the integrity
        level set to Low, must both be creatable. Each is made on
        a throwaway handle and closed here; the per-job spawn
        makes its own. Any failure is named, and the enforce gate
        refuses with it.
        """
        problem = windows_startup_problem(cfg, timeout=timeout)
        if problem is not None:
            return problem
        token, problem = _create_restricted_low_token()
        if problem is not None:
            return problem
        kernel32.CloseHandle(token)
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

    class WindowsConfinedProcess:
        """The Popen subset exec.py drives, for a confined spawn.

        .pid, ._handle, .returncode, .communicate(timeout),
        .kill(), .poll(). communicate raises
        subprocess.TimeoutExpired on timeout, exactly as Popen's
        does, and a second call after a timeout waits for the
        (killed) process and returns its output, as Popen's does.
        """

        def __init__(self, argv, handle, pid, job_handle,
                     out_read, err_read):
            self.args = argv
            self.pid = pid
            self._handle = handle
            self._job_handle = job_handle
            self._out_read = out_read
            self._err_read = err_read
            self.returncode = None
            self._result = None
            self._out = bytearray()
            self._err = bytearray()
            self._readers = []
            for target, sink in ((out_read, self._out),
                                 (err_read, self._err)):
                th = threading.Thread(target=self._pump,
                                      args=(target, sink), daemon=True)
                th.start()
                self._readers.append(th)

        def _pump(self, handle, sink):
            buf = ctypes.create_string_buffer(8192)
            while True:
                got = wintypes.DWORD(0)
                ok = kernel32.ReadFile(handle, buf, 8192,
                                       ctypes.byref(got), None)
                if not ok or got.value == 0:
                    return
                sink.extend(buf.raw[:got.value])

        def _wait(self, timeout_ms):
            return kernel32.WaitForSingleObject(self._handle, timeout_ms)

        def _finish(self):
            code = wintypes.DWORD(0)
            if kernel32.GetExitCodeProcess(self._handle,
                                           ctypes.byref(code)):
                self.returncode = code.value if code.value < 0x80000000 \
                    else code.value - 0x100000000
            for th in self._readers:
                th.join(timeout=5)
            self._result = (bytes(self._out), bytes(self._err))
            return self._result

        def communicate(self, timeout=None):
            if self._result is not None:
                return self._result
            if self.returncode is not None:
                return self._finish()
            if timeout is None:
                self._wait(INFINITE)
            else:
                rc = self._wait(int(timeout * 1000))
                if rc == WAIT_TIMEOUT:
                    raise subprocess.TimeoutExpired(self.args, timeout)
            return self._finish()

        def poll(self):
            if self.returncode is not None:
                return self.returncode
            if self._wait(0) == WAIT_TIMEOUT:
                return None
            self._finish()
            return self.returncode

        def kill(self):
            try:
                kernel32.TerminateProcess(self._handle, 1)
            except Exception:
                pass

        def close(self):
            """The release: close the Job Object (ends anything
            still in it), then the process and pipe handles."""
            close_job_handle(self._job_handle)
            self._job_handle = None
            for handle in (self._out_read, self._err_read, self._handle):
                if handle:
                    try:
                        kernel32.CloseHandle(handle)
                    except Exception:
                        pass
            self._out_read = self._err_read = None

    def spawn_confined_process(argv, cwd=None, env=None):
        """Create a job process under every confinement control.

        argv is the full command (interpreter, script, args). The
        process is created suspended under the restricted,
        low-integrity token, assigned to the Job Object, and only
        then resumed. Returns a WindowsConfinedProcess whose
        .confinement_status is STATUS_CONFINEMENT. Raises
        RuntimeError when any control could not be applied --
        there is no unconfined fallback to fall through to.
        """
        if not isinstance(argv, (list, tuple)) or not argv \
                or not all(isinstance(a, str) for a in argv):
            raise RuntimeError(
                "confined spawn needs a non-empty list of strings")
        job, problem = _create_job_with_limits(
            DEFAULT_PROCESS_MEMORY_BYTES)
        if problem is not None:
            raise RuntimeError(problem)
        token, problem = _create_restricted_low_token()
        if problem is not None:
            kernel32.CloseHandle(job)
            raise RuntimeError(problem)
        if cwd:
            _set_low_integrity_label(cwd)
        sa = SECURITY_ATTRIBUTES()
        sa.nLength = ctypes.sizeof(sa)
        sa.bInheritHandle = True
        out_read = wintypes.HANDLE()
        out_write = wintypes.HANDLE()
        err_read = wintypes.HANDLE()
        err_write = wintypes.HANDLE()
        stdin_handle = kernel32.CreateFileW(
            "NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
            ctypes.byref(sa), OPEN_EXISTING, 0, None)
        made = kernel32.CreatePipe(ctypes.byref(out_read),
                                   ctypes.byref(out_write),
                                   ctypes.byref(sa), 0) and \
            kernel32.CreatePipe(ctypes.byref(err_read),
                                ctypes.byref(err_write),
                                ctypes.byref(sa), 0)
        if not made or not stdin_handle \
                or stdin_handle == INVALID_HANDLE_VALUE:
            err = ctypes.get_last_error()
            for h in (out_read.value, out_write.value, err_read.value,
                      err_write.value, job, token):
                if h:
                    kernel32.CloseHandle(h)
            raise RuntimeError("confined spawn pipe setup failed: %d"
                               % err)
        kernel32.SetHandleInformation(out_read, HANDLE_FLAG_INHERIT, 0)
        kernel32.SetHandleInformation(err_read, HANDLE_FLAG_INHERIT, 0)
        si = STARTUPINFOW()
        si.cb = ctypes.sizeof(si)
        si.dwFlags = STARTF_USESTDHANDLES
        si.hStdInput = stdin_handle
        si.hStdOutput = out_write
        si.hStdError = err_write
        if env is None:
            env_block = None
            flags = CREATE_SUSPENDED
        else:
            env_text = "".join("%s=%s\0" % (k, v)
                               for k, v in env.items()) + "\0"
            env_block = ctypes.create_unicode_buffer(env_text)
            flags = CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT
        cmdline = ctypes.create_unicode_buffer(
            subprocess.list2cmdline(list(argv)))
        pi = PROCESS_INFORMATION()
        ok = advapi32.CreateProcessAsUserW(
            token, None, cmdline, None, None, True, flags,
            env_block, cwd, ctypes.byref(si), ctypes.byref(pi))
        err = ctypes.get_last_error()
        kernel32.CloseHandle(token)
        kernel32.CloseHandle(out_write)
        kernel32.CloseHandle(err_write)
        kernel32.CloseHandle(stdin_handle)
        if not ok:
            for h in (out_read.value, err_read.value, job):
                if h:
                    kernel32.CloseHandle(h)
            raise RuntimeError(
                "CreateProcessAsUserW failed: %d" % err)
        if not kernel32.AssignProcessToJobObject(job, pi.hProcess):
            err = ctypes.get_last_error()
            kernel32.TerminateProcess(pi.hProcess, 1)
            for h in (pi.hProcess, pi.hThread, out_read.value,
                      err_read.value, job):
                if h:
                    kernel32.CloseHandle(h)
            raise RuntimeError(
                "AssignProcessToJobObject failed: %d" % err)
        kernel32.ResumeThread(pi.hThread)
        kernel32.CloseHandle(pi.hThread)
        proc = WindowsConfinedProcess(
            list(argv), pi.hProcess, pi.dwProcessId, job,
            out_read, err_read)
        proc.confinement_status = STATUS_CONFINEMENT
        return proc
