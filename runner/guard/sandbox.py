#!/usr/bin/env python3
"""Linux confinement via bubblewrap (bwrap). Hardening M6.

Builds the bwrap command array; the runner decides when to use it
(see runner.py). The flag set below is the one proven on the build
machine (Ubuntu, usr-merged, overlayfs):

- /usr is read-only inside; the sandbox cannot see home; no network;
  the job workdir is the only writable mount. An interpreter that
  lives outside /usr gets its own install prefix bound read-only
  (interpreter_binds below), and the bind is reported to the caller.
- --unshare-pid is deliberately ABSENT: on this VM it breaks the
  /proc mount (AppArmor/seccomp); without it --proc mounts fine.

Divergences and the machine's real paths are recorded in
docs/archive/HARDENING_REPORT.md.
"""
import os
import shutil
import sys

BWRAP_BIN = "bwrap"
WORK_MOUNT = "/work"

# Proven working set. Order matters: mounts before --chdir.
DEFAULT_FLAGS = [
    "--unshare-user", "--uid", "0", "--gid", "0",
    "--unshare-ipc", "--unshare-net", "--unshare-uts",
    "--die-with-parent",
    "--ro-bind", "/usr", "/usr",
    # usr-merge: the ELF interpreter lives under /lib64.
    "--symlink", "usr/lib", "/lib",
    "--symlink", "usr/lib64", "/lib64",
    "--symlink", "usr/bin", "/bin",
    "--proc", "/proc",
    "--dev", "/dev",
    "--tmpfs", "/tmp",
    "--clearenv",
]


def sandbox_available():
    """True when bwrap can be used on this machine."""
    if os.name == "nt" or not sys.platform.startswith("linux"):
        return False
    return shutil.which(BWRAP_BIN) is not None


_USERNS_SYSCTL = "/proc/sys/kernel/apparmor_restrict_unprivileged_userns"


def _userns_restricted():
    try:
        with open(_USERNS_SYSCTL, encoding="ascii") as fh:
            return fh.read().strip() == "1"
    except OSError:
        return False


def startup_problem(timeout=15):
    """None when bwrap can confine a job here, else why not.

    Run once at startup under confinement: enforce (Decision 1's
    refuse class: a security mode whose mechanism cannot engage
    changes what the box protects, docs/seats/questions.md Q9). It
    checks the platform, finds bwrap on PATH, and starts it once
    with the same namespace flags a job gets, running `true`. The
    first env-axes pair showed why a trial run and not a PATH
    lookup: with apparmor_restrict_unprivileged_userns=1, Ubuntu
    24.04's default, bwrap is installed and every start fails.
    """
    if os.name == "nt" or not sys.platform.startswith("linux"):
        return ("confinement (bwrap) is Linux-only; this machine is "
                "%s" % sys.platform)
    path = shutil.which(BWRAP_BIN)
    if path is None:
        return "bwrap is not installed (not found on PATH)"
    import subprocess
    try:
        proc = subprocess.run(
            [path, *DEFAULT_FLAGS, "/usr/bin/true"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return "bwrap could not be started: %s" % e
    if proc.returncode == 0:
        return None
    detail = (proc.stderr or b"").decode("utf-8", "replace").strip()
    reason = "bwrap cannot start a sandbox (exit %d%s)" % (
        proc.returncode, ": " + detail[:200] if detail else "")
    if _userns_restricted():
        reason += ("; kernel.apparmor_restrict_unprivileged_userns is 1, "
                   "which blocks the user namespace bwrap needs (set it "
                   "to 0, or give bwrap an AppArmor profile)")
    return reason


def _confinement_cfg(cfg):
    sec = cfg.get("security")
    sec = sec if isinstance(sec, dict) else {}
    block = sec.get("confinement")
    return block if isinstance(block, dict) else {}


def _absolute_mount(value, label):
    """An absolute mount path. No null, no newline, no .. segment."""
    parts = value.split("/") if isinstance(value, str) else []
    if (not isinstance(value, str) or not value.startswith("/")
            or any(ch in value for ch in "\x00\r\n")
            or ".." in parts):
        raise RuntimeError(
            "config error: security.confinement.%s "
            "must be an absolute path with no .. segment" % label)


def _flag_list(flags):
    if not isinstance(flags, list) or not all(
            isinstance(f, str) and f and ".." not in f
            and not any(ch in f for ch in "\x00\r\n/")
            for f in flags):
        raise RuntimeError(
            "config error: security.confinement.extra_flags "
            "must be a list of strings")


def _bind_pairs(pairs):
    if not isinstance(pairs, list):
        raise RuntimeError(
            "config error: security.confinement.extra_ro_binds "
            "must be a list of [src, dst] string pairs")
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            raise RuntimeError(
                "config error: security.confinement.extra_ro_binds "
                "must be a list of [src, dst] string pairs")
        _absolute_mount(pair[0], "extra_ro_binds")
        _absolute_mount(pair[1], "extra_ro_binds")


def _validate_confinement_block(block):
    """Raise RuntimeError on a malformed confinement block."""
    if not isinstance(block, dict):
        raise RuntimeError(
            "config error: security.confinement must be an object")
    extra_flags = block.get("extra_flags", [])
    _flag_list(extra_flags)
    extra_binds = block.get("extra_ro_binds", [])
    _bind_pairs(extra_binds)
    work_mount = block.get("work_mount", WORK_MOUNT)
    _absolute_mount(work_mount, "work_mount")
    return True


# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
# The sandbox shows the job /usr and nothing else, so an interpreter
# that lives elsewhere (pyenv, a venv, /opt, GitHub's hosted
# toolcache) resolves fine on the host and then fails inside the
# wall with "execvp ...: No such file or directory". CI found this
# the first day bwrap was installed on the runner. The fix below
# binds the interpreter's own install prefix read-only -- the
# smallest tree that lets it run -- and reports what it bound, so
# the audit record states the widening rather than hiding it.
_ALWAYS_VISIBLE = ("/usr",)


def _under(path, roots):
    for root in roots:
        root = root.rstrip("/") or "/"
        if path == root or path.startswith(root + "/"):
            return True
    return False


def _install_prefix(path):
    """The directory to bind so `path` can run: its grandparent when
    the parent is `bin` (…/x64/bin/python3 -> …/x64, bringing lib/
    along), else its parent. Never shallower than two components, so
    /snap/bin/python3 binds /snap/bin, not all of /snap."""
    parent = os.path.dirname(path)
    if os.path.basename(parent) == "bin":
        grand = os.path.dirname(parent)
        if grand.count("/") >= 2 and grand != "/":
            return grand
    return parent


def interpreter_binds(resolved, extra_ro_binds=()):
    """Read-only binds needed for `resolved` to execute in the sandbox.

    Returns a list of (src, dst) pairs, possibly empty. Both the path
    as resolved and its realpath are considered: a venv's python3 is
    a symlink whose own prefix (pyvenv.cfg, site-packages) is needed
    as well as the base interpreter's. Paths already under /usr or an
    operator extra_ro_bind need nothing.
    """
    visible = list(_ALWAYS_VISIBLE) + [
        dst for _src, dst in extra_ro_binds if isinstance(dst, str)]
    out = []
    seen = set()
    for cand in (resolved, os.path.realpath(resolved)):
        if not isinstance(cand, str) or not cand.startswith("/"):
            continue
        if _under(cand, visible):
            continue
        prefix = _install_prefix(cand)
        if prefix in seen or _under(prefix, visible):
            continue
        seen.add(prefix)
        out.append((prefix, prefix))
    return out


def build_bwrap_command(cfg, interpreter, script_name, workdir, args, env,
                        notes=None):
    """Return the bwrap argv to run a job.

    interpreter: list like ["bash", "-c"] (host paths or bare names).
    script_name: basename of the script inside the workdir.
    workdir: host path of the job workdir (bound read-write).
    args: job args. env: dict of scrubbed env vars for --setenv.
    notes: optional list; a one-line description of each read-only
    bind added for the interpreter's own install prefix is appended,
    so the caller can put it in the audit record.
    Raises RuntimeError when the interpreter cannot be resolved.
    """
    if not interpreter or not all(isinstance(x, str) for x in interpreter):
        raise RuntimeError("interpreter must be a non-empty list of strings")
    if (not isinstance(script_name, str) or not script_name
            or script_name in (".", "..")
            or "/" in script_name or "\\" in script_name
            or "\x00" in script_name):
        raise RuntimeError("script name must be a single path segment")
    if not isinstance(workdir, str) or not workdir or "\x00" in workdir:
        raise RuntimeError("workdir must be a path string")
    if not isinstance(args, (list, tuple)) or not all(
            isinstance(a, str) for a in args):
        raise RuntimeError("args must be a list of strings")
    if not isinstance(env, dict):
        raise RuntimeError("env must be a dict")
    conf = _confinement_cfg(cfg if isinstance(cfg, dict) else {})
    work_mount = conf.get("work_mount", WORK_MOUNT)
    _absolute_mount(work_mount, "work_mount")
    flags = conf.get("extra_flags", [])
    _flag_list(flags)
    binds = conf.get("extra_ro_binds", [])
    _bind_pairs(binds)
    resolved = shutil.which(interpreter[0])
    if not resolved:
        raise RuntimeError(
            "cannot resolve interpreter %r for sandbox" % interpreter[0])

    argv = [BWRAP_BIN]
    argv.extend(DEFAULT_FLAGS)
    for flag in flags:
        argv.append(flag)
    for src, dst in binds:
        argv.extend(["--ro-bind", src, dst])
    for src, dst in interpreter_binds(resolved, binds):
        argv.extend(["--ro-bind", src, dst])
        if isinstance(notes, list):
            notes.append("interpreter prefix %s bound read-only" % src)
    # Minimal PATH plus the job's scrubbed env.
    argv.extend(["--setenv", "PATH", "/usr/bin:/bin"])
    for k, v in env.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        if not k or "=" in k or "\x00" in k or "\x00" in v:
            continue
        argv.extend(["--setenv", k, v])
    argv.extend(["--bind", workdir, work_mount,
                 "--chdir", work_mount])
    argv.append(resolved)
    argv.extend(interpreter[1:])
    argv.append("%s/%s" % (work_mount, script_name))
    argv.extend(args)
    return argv
