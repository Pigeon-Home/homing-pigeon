#!/usr/bin/env python3
"""Windows Event Log writer (stdlib-only, via ctypes).

Telemetry must never break the runner: every failure path here is
swallowed. On non-Windows this module is a no-op.
"""
import os

SOURCE = "HomingPigeon"

# Set once per process after the first successful report; avoids
# re-registering the event source on every call.
_reported_ok = False


def _ensure_source():
    """Register the event source under the Application log.

    Requires admin (the service runs as SYSTEM; install runs elevated).
    Without registration ReportEvent still writes, but Event Viewer shows
    a generic description. Best effort; never raises.
    """
    import winreg
    key_path = ("SYSTEM\\CurrentControlSet\\Services\\EventLog\\Application\\"
                + SOURCE)
    with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
        # EventMessageFile points at a stock system DLL so the viewer can
        # render; our text travels as insertion strings regardless.
        winreg.SetValueEx(key, "EventMessageFile", 0, winreg.REG_EXPAND_SZ,
                          r"%SystemRoot%\System32\EventCreate.exe")
        winreg.SetValueEx(key, "TypesSupported", 0, winreg.REG_DWORD, 7)


def report_event(message: str, level: str = "ERROR") -> None:
    """Write one event to the Windows Application log.

    No-op on non-Windows. Never raises.
    """
    global _reported_ok
    if os.name != "nt":
        return
    try:
        import ctypes

        if not _reported_ok:
            try:
                _ensure_source()
            except Exception:
                pass  # unregistered source still writes; move on

        advapi32 = ctypes.windll.advapi32  # pyrefly: ignore[missing-attribute]  # win32-only; this module is a no-op elsewhere
        EVENTLOG_ERROR_TYPE = 0x0001
        EVENTLOG_WARNING_TYPE = 0x0002
        EVENTLOG_INFORMATION_TYPE = 0x0004
        wtype = {"ERROR": EVENTLOG_ERROR_TYPE,
                 "WARN": EVENTLOG_WARNING_TYPE,
                 "INFO": EVENTLOG_INFORMATION_TYPE}.get(level, EVENTLOG_ERROR_TYPE)

        h = advapi32.RegisterEventSourceW(None, SOURCE)
        if not h:
            return
        try:
            msg_arr = (ctypes.c_wchar_p * 1)(message)
            advapi32.ReportEventW(h, wtype, 0, 1, None, 1, 0, msg_arr, None)
        finally:
            advapi32.DeregisterEventSource(h)
        _reported_ok = True
    except Exception:
        pass  # telemetry never breaks the runner
