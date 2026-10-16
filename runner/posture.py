#!/usr/bin/env python3
"""--posture: report the runner's security posture and exit.

Read-only. No mailbox access. Works with a config that has no
mailbox credentials.

Exit codes:
  0 - every check passed
  1 - at least one WARN, no FAIL
  2 - at least one FAIL, or the config file / base dir could not be read

Sections: config file, secrets, audit log, base dir, security modes.
"""
import os
import stat
import sys

try:
    from runner import security as _security
except ImportError:  # running from inside runner/ as __main__
    try:
        import security as _security
    except ImportError:
        _security = None


def _looks_like_placeholder(value):
    """Lazy import of the shared placeholder check; never copied."""
    try:
        from runner.install import _looks_like_placeholder as f
    except ImportError:
        try:
            from install import _looks_like_placeholder as f
        except ImportError:
            return False
    try:
        return bool(f(value))
    except Exception:
        return False


def _windows_file_restricted(path):
    """Best-effort Windows ACL check.

    Returns True if no broad-read ACE (Everyone/Users/Guests) was
    found, False if one was, None when it could not be determined.
    Any failure degrades to None (reported as WARN, never FAIL).
    """
    try:
        import ctypes
        from ctypes import wintypes
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        SE_FILE_OBJECT = 1
        DACL_SECURITY_INFORMATION = 0x00000004
        p_dacl = wintypes.LPVOID()
        p_sd = wintypes.LPVOID()
        rc = advapi32.GetNamedSecurityInfoW(
            path, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
            None, None, ctypes.byref(p_dacl), None,
            ctypes.byref(p_sd))
        if rc != 0 or not p_dacl:
            return None
        try:
            class _AclSizeInfo(ctypes.Structure):
                _fields_ = [("AceCount", wintypes.DWORD),
                            ("AclBytesInUse", wintypes.DWORD),
                            ("AclBytesFree", wintypes.DWORD)]

            info = _AclSizeInfo()
            # 2 == AclSizeInformation
            if not advapi32.GetAclInformation(
                    p_dacl, ctypes.byref(info),
                    ctypes.sizeof(info), 2):
                return None
            # Well-known SIDs: World (Everyone), Builtin Users/Guests.
            well_known = []
            for sid_type in (1, 27, 28):
                buf = ctypes.create_string_buffer(68)
                size = wintypes.DWORD(68)
                if advapi32.CreateWellKnownSid(sid_type, None, buf,
                                               ctypes.byref(size)):
                    well_known.append(bytes(buf[:size.value]))
            # GENERIC_READ | FILE_GENERIC_READ
            READ_MASK = 0x80000000 | 0x00120089
            for i in range(info.AceCount):
                p_ace = wintypes.LPVOID()
                if not advapi32.GetAce(p_dacl, i, ctypes.byref(p_ace)):
                    continue
                ace = p_ace.value
                if not ace:
                    continue
                ace_type = ctypes.c_ubyte.from_address(ace).value
                if ace_type != 0:  # 0 == ACCESS_ALLOWED_ACE_TYPE
                    continue
                mask = wintypes.DWORD.from_address(ace + 4).value
                if not (mask & READ_MASK):
                    continue
                # ACCESS_ALLOWED_ACE: header(4) + mask(4) + SidStart.
                sid_addr = ace + 8
                for wk in well_known:
                    cand = (ctypes.c_ubyte * len(wk)).from_address(sid_addr)
                    if advapi32.EqualSid(cand, wk):
                        return False
            return True
        finally:
            kernel32.LocalFree(p_sd)
    except Exception:
        return None


def _check_file_perms(path, results):
    """Append (level, section, message) for a secret-bearing file."""
    name = os.path.basename(path) or path
    if os.name == "nt":
        restricted = _windows_file_restricted(path)
        if restricted is True:
            results.append(("OK", "files",
                            "%s: no broad-read ACE found" % name))
        elif restricted is False:
            results.append(("WARN", "files",
                            "%s: readable by Everyone/Users/Guests "
                            "(Windows ACL)" % name))
        else:
            results.append(("WARN", "files",
                            "%s: could not evaluate Windows ACLs" % name))
        return
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError as e:
        results.append(("FAIL", "files", "%s: cannot stat: %s" % (name, e)))
        return
    if mode == 0o600:
        results.append(("OK", "files", "%s: permissions 0600" % name))
    else:
        results.append(("WARN", "files",
                        "%s: permissions %04o (expected 0600)" % (name, mode)))


def _check_secret(label, value, results):
    if _looks_like_placeholder(value):
        results.append(("FAIL", "secrets",
                        "%s looks like a placeholder value" % label))
        return
    if _security is None:
        results.append(("WARN", "secrets",
                        "%s: cannot evaluate (security module "
                        "unavailable)" % label))
        return
    try:
        _security.validate_shared_secret(value)
    except RuntimeError as e:
        # validate_shared_secret raises RuntimeError("config error: ...")
        msg = str(e).split("config error: ", 1)[-1].split(". ", 1)[0]
        results.append(("FAIL", "secrets", "%s too weak: %s" % (label, msg)))
    else:
        results.append(("OK", "secrets", "%s: strong" % label))


def build_posture(cfg, cfg_path, base_dir):
    """Return a list of (level, section, message).

    level is OK, WARN or FAIL. Never raises for a bad config; an
    unreadable config path yields a single FAIL.
    """
    results = []
    try:
        with open(cfg_path, "rb"):
            pass
    except OSError as e:
        return [("FAIL", "config",
                 "cannot read config file %s: %s" % (cfg_path, e))]
    results.append(("OK", "config", "config file readable"))
    _check_file_perms(cfg_path, results)

    if not isinstance(cfg, dict):
        return results + [("FAIL", "config", "config is not an object")]

    _check_secret("shared_secret", cfg.get("shared_secret"), results)
    extra = cfg.get("additional_secrets")
    if isinstance(extra, dict):
        for kid, sec in extra.items():
            _check_secret("additional_secrets[%r]" % (kid,), sec, results)

    if _security is not None:
        audit_path = os.path.join(base_dir, _security.AUDIT_FILE)
        if os.path.exists(audit_path):
            _check_file_perms(audit_path, results)
        else:
            results.append(("OK", "audit log",
                            "no audit entries yet (nothing to protect)"))

    if os.path.isdir(base_dir):
        results.append(("OK", "base dir", "exists: %s" % base_dir))
        if not os.access(base_dir, os.W_OK):
            results.append(("WARN", "base dir", "not writable"))
    else:
        results.append(("FAIL", "base dir",
                        "does not exist: %s" % base_dir))

    modes = (cfg.get("security") or {}).get("modes") or {}
    on = sorted(k for k, v in modes.items()
                if isinstance(v, str) and v.lower() != "off")
    if on:
        results.append(("OK", "security modes",
                        "active: %s" % ", ".join(
                            "%s=%s" % (k, modes[k]) for k in on)))
    else:
        results.append(("OK", "security modes",
                        "all features off (default)"))

    policies = cfg.get("key_policies")
    if isinstance(policies, dict) and policies:
        results.append(("OK", "key policies",
                        "%d key(s) have policy entries"
                        % len(policies)))
    else:
        results.append(("OK", "key policies",
                        "no policy entries (keys unrestricted)"))
    return results


def format_posture(results):
    lines = ["Security posture", "=" * 60]
    for level, section, message in results:
        lines.append("[%-4s] %-14s %s" % (level, section, message))
    return "\n".join(lines) + "\n"


def exit_code_for(results):
    if any(level == "FAIL" for level, _, _ in results):
        return 2
    if any(level == "WARN" for level, _, _ in results):
        return 1
    return 0


def main(cfg, cfg_path, base_dir):
    """Entry point for --posture. Returns an exit code."""
    results = build_posture(cfg, cfg_path, base_dir)
    sys.stdout.write(format_posture(results))
    return exit_code_for(results)
