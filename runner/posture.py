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
import shutil
import stat
import sys

try:
    from runner import security as _security
except ImportError:  # running from inside runner/ as __main__
    try:
        import security as _security
    except ImportError:
        _security = None


# Features the posture check recommends even for a default install.
# Advisory only: WARN, never FAIL.
RECOMMENDED_FEATURES = ("audience", "policy_env", "policy_files",
                        "policy_args")


def _check_privileges(results):
    """Plan M4: report whether the runner runs as root/SYSTEM.

    Informational: this runner is designed to run privileged and drop
    privileges per job (job_user), so root itself is not a warning.
    """
    if os.name == "nt":
        user = os.environ.get("USERNAME", "?")
        results.append(("OK", "privileges", "running as %s" % user))
        return
    try:
        euid = os.geteuid()
    except AttributeError:
        results.append(("OK", "privileges", "uid check unavailable"))
        return
    if euid == 0:
        results.append(("OK", "privileges", "running as root (uid 0)"))
    else:
        try:
            import pwd
            name = pwd.getpwuid(euid).pw_name
        except (ImportError, KeyError):
            name = str(euid)
        results.append(("OK", "privileges",
                        "running as %s (uid %d)" % (name, euid)))


def _check_workspace_root(cfg, results):
    ws = cfg.get("workspace_root") if isinstance(cfg, dict) else None
    if ws:
        results.append(("OK", "workspace",
                        "workspace_root set: %s" % ws))
    else:
        results.append(("WARN", "workspace",
                        "workspace_root unset "
                        "(confinement attestations off)"))


def _check_key_policies(cfg, results):
    """Plan M4: additional keys with no policy entry."""
    if not isinstance(cfg, dict):
        return
    extra = cfg.get("additional_secrets")
    policies = cfg.get("key_policies")
    if not isinstance(extra, dict):
        return
    if not isinstance(policies, dict):
        policies = {}
    default_deny = cfg.get("key_policies_default_deny") is True
    for kid in sorted(extra):
        if not kid or kid in policies:
            continue
        if default_deny:
            results.append(("OK", "key policies",
                            'key "%s" has no policy entry '
                            "(key_policies_default_deny covers it)" % kid))
        else:
            results.append(("WARN", "key policies",
                            'key "%s" has no policy entry and '
                            "key_policies_default_deny is off" % kid))


def _check_recommended_features(cfg, results):
    sec = cfg.get("security")
    sec = sec if isinstance(sec, dict) else {}
    modes = sec.get("modes") if isinstance(sec.get("modes"), dict) else {}
    for feat in RECOMMENDED_FEATURES:
        mode = modes.get(feat, "off")
        if not isinstance(mode, str) or mode.lower() == "off":
            results.append(("WARN", "security modes",
                            "%s is off (recommended: audit or enforce)"
                            % feat))


def _check_confinement_backend(results):
    if sys.platform.startswith("linux"):
        if shutil.which("bwrap"):
            results.append(("OK", "confinement",
                            "bwrap backend installed"))
        else:
            results.append(("WARN", "confinement",
                            "bwrap not installed (confinement in enforce "
                            "mode would run unsandboxed)"))
    else:
        results.append(("OK", "confinement",
                        "bwrap is Linux-only; not applicable on %s"
                        % sys.platform))


def _check_service_unit(results):
    """Plan M4/M7: service unit hardening directives, where we can tell."""
    if os.name == "nt":
        results.append(("OK", "service",
                        "Windows service hardening check not implemented"))
        return
    candidates = [
        "/etc/systemd/system/homing-pigeon.service",
        os.path.expanduser(
            "~/.config/systemd/user/homing-pigeon.service"),
    ]
    found = next((p for p in candidates if os.path.exists(p)), None)
    if not found:
        results.append(("OK", "service",
                        "no homing-pigeon systemd unit found"))
        return
    if os.path.islink(found):
        results.append(("WARN", "service",
                        "unit %s is a symlink" % found))
        return
    try:
        with open(found, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        results.append(("WARN", "service",
                        "cannot read %s" % found))
        return
    directives = ["NoNewPrivileges", "ProtectSystem", "ProtectHome",
                  "PrivateTmp"]
    present = [d for d in directives if d in text]
    if len(present) >= 2:
        results.append(("OK", "service",
                        "unit has hardening directives (%s)"
                        % ", ".join(present)))
    else:
        results.append(("WARN", "service",
                        "unit %s lacks hardening directives" % found))


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

    _check_privileges(results)
    _check_workspace_root(cfg, results)
    _check_key_policies(cfg, results)
    _check_recommended_features(cfg, results)
    _check_confinement_backend(results)
    _check_service_unit(results)

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

    sec = cfg.get("security")
    sec = sec if isinstance(sec, dict) else {}
    modes = sec.get("modes") if isinstance(sec.get("modes"), dict) else {}
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
