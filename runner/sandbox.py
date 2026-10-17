#!/usr/bin/env python3
"""Linux confinement via bubblewrap (bwrap). Hardening M6.

Builds the bwrap command array; the runner decides when to use it
(see runner.py). The flag set below is the one proven on the build
machine (Ubuntu, usr-merged, overlayfs):

- /usr is read-only inside; the sandbox cannot see home; no network;
  the job workdir is the only writable mount.
- --unshare-pid is deliberately ABSENT: on this VM it breaks the
  /proc mount (AppArmor/seccomp); without it --proc mounts fine.

Divergences and the machine's real paths are recorded in
HARDENING_REPORT.md.
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


def _confinement_cfg(cfg):
    block = (cfg.get("security") or {}).get("confinement")
    return block if isinstance(block, dict) else {}


def _validate_confinement_block(block):
    """Raise RuntimeError on a malformed confinement block."""
    if not isinstance(block, dict):
        raise RuntimeError(
            "config error: security.confinement must be an object")
    extra_flags = block.get("extra_flags", [])
    if not isinstance(extra_flags, list) or \
            not all(isinstance(f, str) for f in extra_flags):
        raise RuntimeError(
            "config error: security.confinement.extra_flags "
            "must be a list of strings")
    extra_binds = block.get("extra_ro_binds", [])
    if not isinstance(extra_binds, list) or any(
            not isinstance(p, list) or len(p) != 2 or
            not all(isinstance(x, str) for x in p)
            for p in extra_binds):
        raise RuntimeError(
            "config error: security.confinement.extra_ro_binds "
            "must be a list of [src, dst] string pairs")
    work_mount = block.get("work_mount", WORK_MOUNT)
    if not isinstance(work_mount, str) or not work_mount.startswith("/"):
        raise RuntimeError(
            "config error: security.confinement.work_mount "
            "must be an absolute path string")
    return True


def build_bwrap_command(cfg, interpreter, script_name, workdir, args, env):
    """Return the bwrap argv to run a job.

    interpreter: list like ["bash", "-c"] (host paths or bare names).
    script_name: basename of the script inside the workdir.
    workdir: host path of the job workdir (bound read-write).
    args: job args. env: dict of scrubbed env vars for --setenv.
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
    resolved = shutil.which(interpreter[0])
    if not resolved:
        raise RuntimeError(
            "cannot resolve interpreter %r for sandbox" % interpreter[0])
    conf = _confinement_cfg(cfg)
    work_mount = conf.get("work_mount", WORK_MOUNT)

    argv = [BWRAP_BIN]
    argv.extend(DEFAULT_FLAGS)
    for f in conf.get("extra_flags", []):
        argv.append(f)
    for src, dst in conf.get("extra_ro_binds", []):
        argv.extend(["--ro-bind", src, dst])
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
