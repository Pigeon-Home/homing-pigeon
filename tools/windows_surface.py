#!/usr/bin/env python3
"""The Windows API surface, simulated on a POSIX host.

The 3.8.9 release died exactly here: the local gate ran green on
Linux while build-windows failed on POSIX assumptions in the
tests (code reaching for os.sysconf, which a Windows interpreter
does not have). The fix that shipped (d2da8e6) stubbed the
missing attributes test by test. This module is that technique
generalized: one patch set that makes a POSIX interpreter present
the surface a Windows interpreter presents, so the suite -- or
any subset of it -- can be run against that surface HERE, before
CI has to find the discrepancy.

What the surface changes (apply_surface):

  identity    os.name -> "nt", sys.platform -> "win32",
              platform.system()/release()/version()/machine()
              -> Windows / 10 / 10.0.22621 / AMD64,
              os.sep -> "\\", os.altsep -> "/".
  absence     Attributes a Windows interpreter does not have are
              deleted for the duration: os.sysconf,
              os.getloadavg, os.fork, os.posix_spawn,
              os.register_at_fork, os.getuid/os.geteuid,
              os.getgid/os.getegid, os.uname, os.killpg,
              os.setsid, os.getsid, os.getpgid.
  windll      ctypes.windll and ctypes.WinDLL, absent on POSIX,
              are installed as neutral fakes: every function is
              callable, accepts anything, and returns 0 -- the
              "call failed / not an admin / snapshot refused"
              outcome, which guarded product code already treats
              as a normal result. Guarded Windows code therefore
              RUNS under the simulation instead of dying on the
              first ctypes attribute access.

One bootstrap discipline matters: several stdlib modules branch
on os.name/sys.platform AT IMPORT TIME (shutil imports the `nt`
builtin, subprocess imports _winapi, asyncio picks its Windows
event-loop policy). Applying the surface before those modules
are first imported makes the imports themselves fail on a POSIX
build -- an artifact, not a finding. The runner therefore
pre-imports the stdlib battery (tools/run_tests_windows_sim.py's
_PREIMPORT) before applying the surface; modules already in
sys.modules never re-run their import-time branches. In-suite
use (tests/test_windows_surface.py) gets this for free: by the
time a test applies the surface, everything it needs is already
imported.

What it deliberately does NOT change, and why:

  os.path     Rebinding os.path to ntpath would corrupt the
              harness itself (tempfile/pathlib in the test
              process would scatter backslash-named files across
              the POSIX filesystem). Path-SEPARATOR semantics are
              the one part of the Windows surface this tool does
              not simulate; product code branches on os.name /
              sys.platform, which ARE simulated, and the d2da8e6
              failure class was attribute absence + dispatch,
              which is fully covered.
  /proc       The directory still exists on the host. Product
              samplers reach /proc only behind a platform
              dispatch that the identity patches steer to the
              Windows route, exactly as on a real Windows box.
  os.linesep  Left at "\n": interpreter internals and fixture
              comparisons in the harness assume it. Product code
              that formats with os.linesep is rare and is caught
              by the platform-gated tests on the real CI job.

Everything is restored by the returned restore() callable, in
reverse order, including when apply raised partway. The module
is importable (the in-suite pins in tests/test_windows_surface.py
use it) and runnable: tools/run_tests_windows_sim.py drives a
whole suite run under the surface.

Stdlib only.
"""
import ctypes
import os
import platform
import sys

_IDENTITY = {
    "os.name": "nt",
    "sys.platform": "win32",
    "os.sep": "\\",
    "os.altsep": "/",
}

_PLATFORM_FUNCS = {
    "system": "Windows",
    "release": "10",
    "version": "10.0.22621",
    "machine": "AMD64",
    "processor": "AMD64 Family 25 Model 1",
    "platform": "Windows-10-10.0.22621-SP0",
}

_ABSENT = (
    "sysconf", "getloadavg", "fork", "posix_spawn",
    "register_at_fork", "getuid", "geteuid", "getgid", "getegid",
    "uname", "killpg", "setsid", "getsid", "getpgid",
)


class _FakeWinFunc:
    """One neutral Win32 function: callable, returns 0.

    ctypes call sites commonly assign .argtypes/.restype before
    calling; those are plain attributes here. Returning 0 is the
    failure/neutral value for the call sites the runner uses
    (IsUserAnAdmin -> not admin, GlobalMemoryStatusEx -> caller
    treats as unavailable, snapshot handles -> invalid).
    """

    def __init__(self, name):
        self._name = name
        self.argtypes = None
        self.restype = None

    def __call__(self, *args, **kwargs):
        return 0

    def __repr__(self):
        return f"<simulated Win32 function {self._name} -> 0>"


class _FakeDll:
    """Attribute access mints one stable _FakeWinFunc per name."""

    def __init__(self, name=""):
        self._dll_name = name

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        func = _FakeWinFunc(name)
        setattr(self, name, func)
        return func

    def __repr__(self):
        return f"<simulated DLL {self._dll_name or '?'}>"


class _FakeWinDllLoader:
    """ctypes.windll stand-in: attribute access mints DLLs."""

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        dll = _FakeDll(name)
        setattr(self, name, dll)
        return dll


def _fake_windll_factory(name=None, **_kwargs):
    return _FakeDll(name or "")


def surface_description():
    """The patch set as data, for reports and the pinning tests."""
    return {
        "identity": dict(_IDENTITY),
        "platform_functions": dict(_PLATFORM_FUNCS),
        "absent_os_attributes": list(_ABSENT),
        "windll": "ctypes.windll + ctypes.WinDLL installed as "
                  "neutral fakes (every function returns 0)",
        "not_simulated": [
            "os.path separator semantics (ntpath rebinding would "
            "corrupt the test harness's own filesystem use)",
            "/proc absence (platform dispatch, which IS "
            "simulated, is what steers product code away)",
            "os.linesep",
        ],
    }


def apply_surface():
    """Apply the Windows surface. Returns a restore() callable.

    Idempotent while applied: a second call returns a no-op
    restore and leaves the first call's restore in charge.
    """
    if getattr(apply_surface, "_active", False):
        return lambda: None
    undo = []

    def _set(obj, name, value):
        undo.append((obj, name, getattr(obj, name, _MISSING)))
        setattr(obj, name, value)

    def _del(obj, name):
        if hasattr(obj, name):
            undo.append((obj, name, getattr(obj, name)))
            delattr(obj, name)

    try:
        _set(os, "name", _IDENTITY["os.name"])
        _set(sys, "platform", _IDENTITY["sys.platform"])
        _set(os, "sep", _IDENTITY["os.sep"])
        _set(os, "altsep", _IDENTITY["os.altsep"])
        for func_name, result in _PLATFORM_FUNCS.items():
            _set(platform, func_name, (lambda r: lambda *a, **k: r)(result))
        for attr in _ABSENT:
            _del(os, attr)
        if not hasattr(ctypes, "windll"):
            _set(ctypes, "windll", _FakeWinDllLoader())
        if not hasattr(ctypes, "WinDLL"):
            _set(ctypes, "WinDLL", _fake_windll_factory)
    except Exception:
        _restore_all(undo)
        raise
    apply_surface._active = True

    def restore():
        if apply_surface._active:
            apply_surface._active = False
            _restore_all(undo)

    return restore


class _Missing:
    pass


_MISSING = _Missing()


def _restore_all(undo):
    for obj, name, saved in reversed(undo):
        if isinstance(saved, _Missing):
            try:
                delattr(obj, name)
            except AttributeError:
                pass
        else:
            setattr(obj, name, saved)


def windows_surface():
    """Context-manager form: `with windows_surface(): ...`"""
    import contextlib

    @contextlib.contextmanager
    def _cm():
        restore = apply_surface()
        try:
            yield
        finally:
            restore()

    return _cm()
