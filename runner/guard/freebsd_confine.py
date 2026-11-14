#!/usr/bin/env python3
"""FreeBSD containment: jails, and the confinement backend.

No external dependencies; stdlib only, driving the base system's
own tools (/usr/sbin/jail, /usr/sbin/jexec, /usr/sbin/jls,
/sbin/mount, /sbin/umount, /usr/bin/limits, /usr/bin/rctl,
/sbin/sysctl, /sbin/ifconfig, /bin/sh). One seam uses this
module:

- confinement: a job process is executed inside a freshly
  created jail(8), and every audit and startup record names
  exactly the controls that jail carried, in the order of
  CONTROL_ORDER, as "freebsd: " and the names joined by " + ".
  The floor every confined job has is STATUS_CONFINEMENT --
  "freebsd: jail + no_network + spawn_resource_limits" -- and
  a record that says more names a control that was applied to
  that job and proven by the startup trial on that host.

The controls, and what each one is:

- jail. The jail's root is a read-only view (nullfs) of a
  per-job skeleton that holds mount points and three small
  files, nothing else. Mounted below it: the host's /usr,
  /usr/local, /bin, /lib, /libexec and /sbin, read-only; the
  operator's extra read-only binds (security.confinement.
  extra_ro_binds); the install prefix of an interpreter that
  lives outside those trees, read-only, noted in the audit
  record; a tmpfs at /tmp, bounded (512 MiB unless the config
  says otherwise); /dev as devfs under ruleset 4; and the job's
  work directory at the work mount (/work unless the config
  says otherwise). Every mount is nosuid. The result is that
  exactly two trees take a write from inside -- the work mount
  and /tmp -- whoever the job runs as, and a set-user-ID bit on
  any file the job can reach buys nothing. A jail has its own
  process table: the host's processes do not exist inside it,
  and removing the jail ends every process the job left.
- no_network. The jail is created with ip4=disable and
  ip6=disable: no network at all, loopback included. This is
  the default.
- private_loopback. In place of no_network when the config
  sets security.confinement.freebsd.loopback: the jail gets a
  network stack of its own (vnet) whose only interface is its
  own lo0, brought up at 127.0.0.1. The job can talk to itself
  and to nothing else; the host's loopback is another stack.
- no_superuser. When no job user is handed to the spawn the
  job is uid 0 inside its jail, and the jail is created with
  allow.nosuser: that uid holds no privilege there. It cannot
  raise a resource limit, change a file's owner, or do anything
  else the super-user's privilege grants. When the job_user
  seam hands the spawn a user, jexec applies it at the jail
  door (jexec -u, resolved in the host's user database), the
  job is that user from its first instruction, and this control
  is not named: the job_user record is.
- rctl_resource_limits. On a host with RACCT enabled
  (kern.racct.enable=1, a boot tunable) the jail as a whole is
  held by rctl(8) rules the kernel enforces: a ceiling on the
  number of processes in the jail and a ceiling on the address
  space of all of them together (256 processes and 2 GiB unless
  the config says otherwise). On a host without RACCT the rules
  cannot deny anything, so they are not written and the control
  is not named.
- spawn_resource_limits. The job's command runs under limits(1)
  with the virtual-memory and data-size limits both set to the
  per-process ceiling (512 MiB unless the config says
  otherwise). Under no_superuser, and under a job user, the job
  cannot raise them.

The jail exists before the job's first process runs (jexec
starts the job inside it), so there is no race in which the job
runs unconfined. The process object owns the teardown, and its
release (FreeBSDConfinedProcess.close) removes the jail, its
rctl rules, every mount and the skeleton. Two things stand
behind the release:

- A reaper. Each job's jail has a small watcher holding the
  read end of a pipe whose write end only the runner holds. If
  the runner dies, by any cause, the pipe closes and the watcher
  removes the jail, which ends every process of the job.
- A sweep. The first probe of a runner process removes what a
  dead runner left: jails, rctl rules, mounts and skeletons
  whose names carry the process id of a runner that is gone.

The skeleton is never removed through a mount. The release
unmounts, reads the mount table to see that nothing is mounted
below the skeleton any more, and removes the tree without
leaving its filesystem; a skeleton with a mount still under it
is left for the sweep.

What this is NOT, stated plainly wherever it is recorded:

- Not Capsicum. Capability mode is entered in-process by the
  confined program itself; this launcher starts arbitrary job
  interpreters that know nothing of it, so it does not fit the
  launcher shape.
- Not an unprivileged sandbox. Creating a jail and mounting
  into it need root: the runner must run as root for this
  backend to engage, and the probe refuses otherwise.
- The per-process ceiling is a resource limit applied at spawn.
  It is the job's own to keep only because the job holds no
  privilege to raise it; it is not a kernel rule. The kernel
  rules are the rctl ones, on a host that has RACCT enabled.
- Memory a job holds outside a process's address space -- a
  POSIX shared-memory object it never maps -- is bounded by
  neither ceiling. The /tmp bound closes the largest such door.
- The job's work directory is on the host's disk and is not
  bounded here.

The startup probe proves the controls on the host before any
job runs: a throwaway skeleton, its mounts, a throwaway jail
with the same parameters a job's would have, and a trial
process inside it that writes its work mount, tries to write
the jail root, tries an act that needs privilege, and reports
what devices it can see. A trial that lands a write outside the
two trees, keeps a privilege, or sees the host's devices is a
refusal by name. The verdict of a passing trial is kept for the
life of the process, for the settings it was run with; a
particular job's spawn still makes its own jail, and its
failure refuses that job then.

This module is import-safe on non-FreeBSD: the public probe and
spawn refuse there, and everything below the public names is
written against a host object (the commands and the few facts
about the machine) that the suite replaces, so the logic is
exercised on every platform and the kernel only where it is
real.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid

try:
    from runner.guard import sandbox as _sandbox
except ImportError:  # script mode: runner/ is on sys.path
    from guard import sandbox as _sandbox  # type: ignore

# The per-process ceiling: applied as both the virtual-memory and
# the data-size resource limit at spawn.
DEFAULT_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024
# The bound on the job's /tmp, which is memory.
DEFAULT_TMP_BYTES = 512 * 1024 * 1024
# The jail-wide ceilings, held by rctl on a host with RACCT.
DEFAULT_JOB_MEMORY_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_JOB_PROCESSES = 256

# The floor: the controls every confined job has, named exactly.
STATUS_CONFINEMENT = "freebsd: jail + no_network + spawn_resource_limits"
CONFINEMENT_CONTROLS = ("jail", "no_network", "spawn_resource_limits")
# Every control this backend can name, in the order a record
# names them.
CONTROL_ORDER = ("jail", "no_network", "private_loopback",
                 "no_superuser", "rctl_resource_limits",
                 "spawn_resource_limits")

# Where the job's work directory is mounted inside the jail
# unless security.confinement.work_mount says otherwise.
WORK_MOUNT = "/work"

JAIL_BIN = "/usr/sbin/jail"
JEXEC_BIN = "/usr/sbin/jexec"
JLS_BIN = "/usr/sbin/jls"
LIMITS_BIN = "/usr/bin/limits"
MOUNT_BIN = "/sbin/mount"
UMOUNT_BIN = "/sbin/umount"
RCTL_BIN = "/usr/bin/rctl"
SYSCTL_BIN = "/sbin/sysctl"
IFCONFIG_BIN = "/sbin/ifconfig"
SH_BIN = "/bin/sh"

#: Host paths mounted read-only (nullfs) into the jail root, in
#: mount order, parents before children: a child tree that
#: lives on its parent's filesystem (a plain directory under
#: it, like /usr/local under /usr on a stock FreeBSD) is
#: already exposed by the parent's mount and is not mounted
#: again -- nullfs refuses that cycle. /usr/local is listed
#: because it is where the pkg-installed interpreters live;
#: on a host where it is its own filesystem it mounts for real.
#: Together they are the whole userland a job can execute.
RO_MOUNTS = ("/usr", "/usr/local", "/bin", "/lib", "/libexec",
             "/sbin")

# The PATH a jailed job sees when the caller's env names none.
JAIL_PATH = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# A skeleton is a directory named for the runner process that
# made it, under the temporary folder; a jail is named the same
# way. The names are how the sweep tells a dead runner's
# leavings from a live runner's jobs.
SKELETON_PREFIX = "hp-jail-"
_JAIL_NAME = re.compile(r"^hp(job|probe)(\d+)x[0-9a-f]+$")
_SKELETON_NAME = re.compile(r"^hp-jail-(\d+)-")

# The names the skeleton itself uses at the jail root. A work
# mount or a bind may not land on them.
_RESERVED_TOP = ("usr", "bin", "lib", "libexec", "sbin", "etc",
                 "tmp", "dev", "var")

# The settings security.confinement.freebsd may carry.
FREEBSD_KEYS = ("loopback", "process_memory_bytes", "tmp_bytes",
                "job_memory_bytes", "job_processes")
_FREEBSD_NUMBERS = FREEBSD_KEYS[1:]

# The reaper: one line of sh on the read end of a pipe. The word
# "done" is the release saying it will remove the jail itself;
# anything else -- the pipe closing because the runner is gone
# -- removes the jail, which ends every process inside it.
def reaper_script(jail_bin=JAIL_BIN):
    return ('read word; [ "$word" = done ] && exit 0; '
            'exec %s -r "$1"' % jail_bin)


REAPER_SCRIPT = reaper_script()

# The trial a probe runs inside its throwaway jail, from the
# work mount. Each line it prints is a fact about the boundary.
TRIAL_SCRIPT = (
    "echo trial > hp-trial && /bin/cat hp-trial && /bin/rm hp-trial "
    "&& echo WORK-OK; "
    "( : > /hp-trial ) 2> /dev/null && echo ROOT-WRITABLE; "
    "( : > /tmp/hp-trial ) 2> /dev/null && echo TMP-OK; "
    "/usr/sbin/chown 65534 . 2> /dev/null && echo PRIVILEGED; "
    "[ -c /dev/null ] && echo NULL-OK; "
    "[ -e /dev/mem ] && echo DEVICES-EXPOSED; "
    "echo END")


def confinement_status(controls):
    """The record's string for a set of controls: "freebsd: "
    and the names in CONTROL_ORDER. A name this backend does
    not know is an error, never a string."""
    unknown = sorted(set(controls) - set(CONTROL_ORDER))
    if unknown:
        raise RuntimeError(
            "unknown confinement control(s): %s" % ", ".join(unknown))
    return "freebsd: " + " + ".join(
        name for name in CONTROL_ORDER if name in controls)


def validate_freebsd_block(block):
    """Raise RuntimeError on a malformed security.confinement.
    freebsd block. A setting this backend does not know is an
    error: a ceiling the operator misspelled is a ceiling that
    is not there."""
    if not isinstance(block, dict):
        raise RuntimeError(
            "config error: security.confinement.freebsd must be "
            "an object")
    for key in block:
        if key not in FREEBSD_KEYS:
            raise RuntimeError(
                "config error: security.confinement.freebsd.%s is "
                "not a known setting (known: %s)"
                % (key, ", ".join(FREEBSD_KEYS)))
    if "loopback" in block and not isinstance(block["loopback"], bool):
        raise RuntimeError(
            "config error: security.confinement.freebsd.loopback "
            "must be true or false")
    for key in _FREEBSD_NUMBERS:
        if key not in block:
            continue
        value = block[key]
        if isinstance(value, bool) or not isinstance(value, int) \
                or value < 1:
            raise RuntimeError(
                "config error: security.confinement.freebsd.%s must "
                "be a positive integer (got %r)" % (key, value))
    return True


def _inside(path, roots):
    """True when `path` is one of `roots` or lies below one."""
    return _sandbox._under(path, roots)


def confinement_settings(cfg):
    """The settings a jail is built from, read out of the config.

    The shared keys of security.confinement (work_mount,
    extra_ro_binds, extra_flags) are read under the sandbox
    module's own rules, and the freebsd block under this
    module's. Raises RuntimeError on a malformed block, on a
    work mount or a bind that would land on the skeleton's own
    names, and on extra_flags: those are bwrap arguments, this
    backend can apply none of them, and a flag an operator
    wrote for a reason is not dropped in silence.
    """
    conf = _sandbox._confinement_cfg(cfg if isinstance(cfg, dict) else {})
    work_mount = conf.get("work_mount", WORK_MOUNT)
    _sandbox._absolute_mount(work_mount, "work_mount")
    binds = conf.get("extra_ro_binds", [])
    _sandbox._bind_pairs(binds)
    flags = conf.get("extra_flags", [])
    _sandbox._flag_list(flags)
    if flags:
        raise RuntimeError(
            "security.confinement.extra_flags (%s) are bwrap "
            "arguments; the FreeBSD jail takes none of them. Remove "
            "them; the jail's own settings are under "
            "security.confinement.freebsd" % ", ".join(flags))
    block = conf.get("freebsd", {})
    validate_freebsd_block(block)
    work_mount = work_mount.rstrip("/")
    top = work_mount.split("/")[1] if work_mount.count("/") else ""
    if not work_mount or top in _RESERVED_TOP:
        raise RuntimeError(
            "config error: security.confinement.work_mount %r "
            "cannot be used on FreeBSD: it must be a directory of "
            "its own at the jail root, not the root itself and not "
            "under %s" % (conf.get("work_mount", WORK_MOUNT),
                          ", ".join("/" + n for n in _RESERVED_TOP)))
    pairs = []
    for src, dst in binds:
        dst = dst.rstrip("/")
        if not dst or dst.split("/")[1] in ("tmp", "dev") \
                or _inside(dst, (work_mount,)) \
                or _inside(work_mount, (dst,)):
            raise RuntimeError(
                "config error: security.confinement.extra_ro_binds "
                "destination %r cannot be used on FreeBSD: it must "
                "not be the jail root, /tmp, /dev or the work mount"
                % (dst or "/",))
        pairs.append((src, dst))
    return {
        "work_mount": work_mount,
        "extra_ro_binds": pairs,
        "loopback": bool(block.get("loopback", False)),
        "process_memory_bytes": block.get(
            "process_memory_bytes", DEFAULT_PROCESS_MEMORY_BYTES),
        "tmp_bytes": block.get("tmp_bytes", DEFAULT_TMP_BYTES),
        # None means the operator named none: the default applies
        # where RACCT can hold it and nothing is written where it
        # cannot. A number means the operator asked for the rule.
        "job_memory_bytes": block.get("job_memory_bytes"),
        "job_processes": block.get("job_processes"),
    }


def _settings_key(st):
    return json.dumps(st, sort_keys=True)


def jail_name(tag, pid):
    """A jail name: alphanumerics only, carrying the process id
    of the runner that made it, unique per call."""
    return "hp%s%dx%s" % (tag, pid, uuid.uuid4().hex[:10])


def jail_parameters(name, root, loopback=False, superuser=True):
    """The jail(8) command that creates one job's jail.

    No mount.devfs: this backend mounts /dev itself, so it can
    unmount it itself -- jail(8) does not unmount the devfs of
    a jail it was not given a configuration file for.
    """
    argv = [JAIL_BIN, "-c", "name=" + name, "path=" + root,
            "host.hostname=hp-job"]
    if loopback:
        argv.append("vnet=new")
    else:
        argv += ["ip4=disable", "ip6=disable"]
    argv += ["devfs_ruleset=4", "enforce_statfs=1"]
    if not superuser:
        argv.append("allow.nosuser")
    argv.append("persist=true")
    return argv


def rctl_rules(name, st):
    """The rules that hold one job's jail as a whole."""
    procs = st["job_processes"]
    memory = st["job_memory_bytes"]
    return [
        "jail:%s:maxproc:deny=%d" % (
            name, DEFAULT_JOB_PROCESSES if procs is None else procs),
        "jail:%s:vmemoryuse:deny=%d" % (
            name, DEFAULT_JOB_MEMORY_BYTES if memory is None else memory),
    ]


def mount_plan(skel, root, workdir, st, prefixes=()):
    """The mounts of one jail, in the order to apply them.

    Each entry is {"kind", "point", "argv"} and, for a mount
    that mirrors a host tree at its own path, "mirror": the
    host path. The first entry is the root itself: the skeleton
    seen read-only, which is what makes every path that is not
    a writable mount refuse a write. With no work directory (a
    probe's trial) the work mount is a small tmpfs.
    """
    def nullfs(kind, src, dst, options, mirror=None):
        entry = {"kind": kind, "point": dst,
                 "argv": [MOUNT_BIN, "-t", "nullfs", "-o", options,
                          src, dst]}
        if mirror is not None:
            entry["mirror"] = mirror
        return entry

    plan = [nullfs("root", skel, root, "ro,nosuid")]
    for tree in RO_MOUNTS:
        plan.append(nullfs("ro", tree, root + tree, "ro,nosuid",
                           mirror=tree))
    for src, dst in st["extra_ro_binds"]:
        plan.append(nullfs("bind", src, root + dst, "ro,nosuid"))
    for prefix in prefixes:
        plan.append(nullfs("prefix", prefix, root + prefix,
                           "ro,nosuid", mirror=prefix))
    plan.append({
        "kind": "tmp", "point": root + "/tmp",
        "argv": [MOUNT_BIN, "-t", "tmpfs", "-o",
                 "nosuid,size=%d,mode=1777" % st["tmp_bytes"],
                 "tmpfs", root + "/tmp"]})
    plan.append({
        "kind": "dev", "point": root + "/dev",
        "argv": [MOUNT_BIN, "-t", "devfs", "-o", "ruleset=4",
                 "devfs", root + "/dev"]})
    work_point = root + st["work_mount"]
    if workdir:
        plan.append(nullfs("work", workdir, work_point, "nosuid"))
    else:
        plan.append({
            "kind": "work", "point": work_point,
            "argv": [MOUNT_BIN, "-t", "tmpfs", "-o",
                     "nosuid,size=1048576,mode=1777",
                     "tmpfs", work_point]})
    return plan


def translate_argv(argv, cwd, st, which=shutil.which, notes=None):
    """Translate a host argv into the argv that runs in-jail.

    Returns (argv, prefixes). The interpreter is resolved on the
    host; a resolved path under one of the read-only mounted
    trees or an operator bind keeps its path (the mounts mirror
    the host layout), a path under the job's work directory
    (cwd) becomes its work-mount path, and an interpreter that
    lives anywhere else gets its own install prefix mounted
    read-only at the same path -- the rule the Linux sandbox
    applies (sandbox.interpreter_binds), with the same floor:
    never a user's home, never a tree shallower than two
    components. Each such mount is returned in `prefixes` and
    described in `notes`, so the audit record states the
    widening. An interpreter no mount can show cannot be
    engaged honestly -- the file would not exist inside the
    jail -- so it raises. Every later argument under cwd is
    translated the same way; other arguments (absolute host
    paths outside the mounts, which are the job's own business
    and do not resolve inside the jail) pass unchanged.
    """
    if not isinstance(argv, (list, tuple)) or not argv \
            or not all(isinstance(a, str) for a in argv):
        raise RuntimeError(
            "confined spawn needs a non-empty list of strings")
    visible = list(RO_MOUNTS) + [dst for _src, dst in st["extra_ro_binds"]]
    prefixes = []
    out = []
    for i, arg in enumerate(argv):
        if i == 0 and "/" not in arg:
            resolved = which(arg)
            if resolved is None:
                raise RuntimeError(
                    "cannot resolve interpreter %r for the "
                    "jail" % arg)
            arg = resolved
        if cwd and (arg == cwd or arg.startswith(cwd + "/")):
            out.append(st["work_mount"] + arg[len(cwd):])
            continue
        if i == 0:
            # Asked of every interpreter, visible or not: one
            # that is a symbolic link from a mounted tree to a
            # tree outside them needs its target's prefix too.
            for src, _dst in _sandbox.interpreter_binds(
                    arg, st["extra_ro_binds"],
                    always_visible=RO_MOUNTS):
                if _inside(src, ("/tmp", "/dev", st["work_mount"])):
                    # The jail puts a tree of its own at that
                    # path; the host's is not what a job would
                    # find there.
                    raise RuntimeError(
                        "interpreter %r lives under a path the jail "
                        "replaces with a tree of its own (/tmp, /dev "
                        "or the work mount); it would not exist "
                        "inside the jail" % arg)
                prefixes.append(src)
                if isinstance(notes, list):
                    notes.append(
                        "interpreter prefix %s mounted read-only" % src)
            if not _inside(arg, visible + prefixes):
                raise RuntimeError(
                    "interpreter %r does not live under a mounted "
                    "tree (%s) and its install prefix cannot be "
                    "mounted; it would not exist inside the jail"
                    % (arg, ", ".join(visible)))
        out.append(arg)
    return out, prefixes


class _Host:
    """The machine, as this backend touches it: the commands it
    runs and the few facts it reads. The suite passes its own."""

    def euid(self):
        return os.geteuid()

    def pid(self):
        return os.getpid()

    def run(self, argv, timeout=30):
        """Run a base-system tool; return (rc, stdout, stderr)."""
        proc = subprocess.run(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout)
        return (proc.returncode,
                proc.stdout.decode("utf-8", "replace"),
                proc.stderr.decode("utf-8", "replace"))

    def popen(self, argv, **kwargs):
        return subprocess.Popen(argv, **kwargs)

    def executable(self, path):
        return os.path.isfile(path) and os.access(path, os.X_OK)

    def is_dir(self, path):
        return os.path.isdir(path)

    def device(self, path):
        try:
            return os.stat(path).st_dev
        except OSError:
            return None

    def which(self, name):
        return shutil.which(name)

    def pid_alive(self, pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except OSError:
            return True
        return True

    def sleep(self, seconds):
        time.sleep(seconds)

    def temp_folder(self):
        return tempfile.gettempdir()


_HOST = _Host()


def _quiet(host, argv, timeout=30):
    """Run a command whose failure is an answer, not an error."""
    try:
        return host.run(argv, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return (-1, "", str(e))


def _racct_enabled(host):
    rc, out, _err = _quiet(host, [SYSCTL_BIN, "-n", "kern.racct.enable"])
    return rc == 0 and out.strip() == "1"


def _vimage_present(host):
    rc, out, _err = _quiet(host, [SYSCTL_BIN, "-n",
                                  "kern.features.vimage"])
    return rc == 0 and out.strip() == "1"


def _basic_problem(host, st=None):
    """Why the backend cannot engage at all here, or None.

    Root (jail creation, the mounts), and the base tools
    themselves. The full trial is the probe's; this is the cheap
    half the spawn also checks, so a spawn on a host that lost
    root refuses instead of half-engaging.
    """
    if host.euid() != 0:
        return ("creating a jail needs root; the runner is "
                "not running as root")
    tools = [JAIL_BIN, JEXEC_BIN, JLS_BIN, LIMITS_BIN, MOUNT_BIN,
             UMOUNT_BIN, SYSCTL_BIN, SH_BIN]
    if st is not None and st["loopback"]:
        tools.append(IFCONFIG_BIN)
    for path in tools:
        if not host.executable(path):
            return "%s is missing or not executable" % path
    for tree in RO_MOUNTS:
        if not host.is_dir(tree):
            return "host tree %s is missing" % tree
    return None


def controls_for(host, st, user=None):
    """(controls, rctl) for a job on this host: the names the
    record will carry and whether the rctl rules are written.

    Raises RuntimeError when the config asks for a control this
    host cannot hold. A default adapts to the host -- the rctl
    ceilings are written where RACCT is enabled and not named
    where it is not -- but a setting the operator wrote must
    engage or refuse.
    """
    controls = ["jail"]
    if st["loopback"]:
        if not _vimage_present(host):
            raise RuntimeError(
                "security.confinement.freebsd.loopback needs a "
                "kernel with VIMAGE (kern.features.vimage is not "
                "1 on this host)")
        controls.append("private_loopback")
    else:
        controls.append("no_network")
    if user is None:
        controls.append("no_superuser")
    racct = _racct_enabled(host)
    if racct:
        if not host.executable(RCTL_BIN):
            raise RuntimeError(
                "RACCT is enabled but %s is missing or not "
                "executable" % RCTL_BIN)
        controls.append("rctl_resource_limits")
    elif st["job_memory_bytes"] is not None \
            or st["job_processes"] is not None:
        raise RuntimeError(
            "security.confinement.freebsd names a jail-wide ceiling "
            "(job_memory_bytes or job_processes), which is an rctl "
            "rule, and RACCT is not enabled on this host "
            "(kern.racct.enable is not 1): set kern.racct.enable=1 "
            "in /boot/loader.conf and reboot, or remove the setting")
    controls.append("spawn_resource_limits")
    return controls, racct


def _make_skeleton(host, st, points=()):
    """A fresh skeleton; returns (base, skel, root).

    base is private to the runner (0700) and holds two
    directories: skel, the tree the jail will see read-only as
    its root, and root, the empty directory that view is
    mounted on. skel holds mount points, copies of the host's
    passwd and group files (the spawn's user is resolved on the
    host side, jexec -u, not in here), and the dynamic loader's
    hints -- they live in /var/run on FreeBSD, and without them
    a binary linked against /usr/local libraries (the
    pkg-installed python3 is the standing case) does not load
    inside the jail. Nothing is ever mounted inside skel
    itself: every mount hangs below root.
    """
    # The real path: the mount table names mount points by
    # their real paths, and the release reads it by this one.
    base = os.path.realpath(tempfile.mkdtemp(
        prefix="%s%d-" % (SKELETON_PREFIX, host.pid()),
        dir=host.temp_folder()))
    skel = base + "/skel"
    root = base + "/root"
    try:
        os.mkdir(skel)
        os.mkdir(root)
        # A job demoted to the job user must be able to
        # traverse its own jail root to reach the mounts.
        os.chmod(skel, 0o755)
        os.chmod(root, 0o755)
        for name in ("usr", "bin", "lib", "libexec", "sbin", "etc",
                     "tmp", "dev"):
            os.mkdir(os.path.join(skel, name))
        os.makedirs(os.path.join(skel, "var", "run"))
        wanted = [st["work_mount"]] + [p for p in points
                                       if not _inside(p, RO_MOUNTS)]
        for point in wanted:
            os.makedirs(skel + point, exist_ok=True)
        for name in ("passwd", "group"):
            try:
                shutil.copyfile("/etc/" + name,
                                os.path.join(skel, "etc", name))
            except OSError:
                pass
        try:
            shutil.copyfile("/var/run/ld-elf.so.hints",
                            os.path.join(skel, "var", "run",
                                         "ld-elf.so.hints"))
        except OSError:
            pass
        os.chmod(os.path.join(skel, "tmp"), 0o1777)
    except OSError:
        # Nothing is mounted yet: the tree is plain files.
        shutil.rmtree(base, ignore_errors=True)
        raise
    return base, skel, root


def _apply_mounts(host, plan, timeout=30):
    """Apply the plan in order; (applied, problem).

    A mirror entry is skipped when an entry already applied
    mirrors an ancestor of its source AND the source lives on
    the same host filesystem as that ancestor (same device):
    the ancestor's mount already exposes the source at exactly
    that path, and mounting it again is a cycle nullfs refuses
    ("Resource deadlock avoided"). This is /usr/local on a
    stock FreeBSD: a plain directory under /usr, not a
    filesystem of its own. Where the child IS its own
    filesystem (a different device), it is mounted for real.
    Only mounts actually applied are returned, for teardown.
    """
    applied = []
    mirrored = []  # (host path, device) actually mounted
    for entry in plan:
        src = entry.get("mirror")
        if src is not None:
            dev = host.device(src)
            if dev is not None and any(
                    dev == adev and _inside(src, (asrc,))
                    for asrc, adev in mirrored):
                continue
        try:
            rc, _out, err = host.run(entry["argv"], timeout=timeout)
        except (OSError, subprocess.SubprocessError) as e:
            return applied, "mount %s failed: %s" % (entry["point"], e)
        if rc != 0:
            return applied, "mount %s failed (exit %d): %s" % (
                entry["point"], rc, err.strip()[:200])
        applied.append(entry)
        if src is not None:
            mirrored.append((src, host.device(src)))
    return applied, None


def _mounted_below(host, base):
    """The mount points at or below `base`, deepest first, read
    from the mount table; None when the table cannot be read."""
    rc, out, _err = _quiet(host, [MOUNT_BIN, "-p"])
    if rc != 0:
        return None
    found = []
    for line in out.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        point = fields[1]
        if point == base or point.startswith(base + "/"):
            found.append(point)
    return sorted(set(found), key=lambda p: (-len(p), p))


def _unmount(host, point):
    """Unmount one point; True when it is no longer mounted.

    A jail that was just removed may still be letting go of its
    last process, so a busy mount is tried again before it is
    forced. Forcing is safe here: the jail is gone, and nothing
    else was ever given the mount.
    """
    for _attempt in range(8):
        rc, _out, err = _quiet(host, [UMOUNT_BIN, point])
        if rc == 0:
            return True
        low = err.lower()
        if "not a file system root" in low \
                or "not currently mounted" in low \
                or "no such file or directory" in low:
            return True
        host.sleep(0.25)
    rc, _out, _err = _quiet(host, [UMOUNT_BIN, "-f", point])
    return rc == 0


def _remove_one_fs(path, dev):
    """Remove `path` and what is below it, never leaving the
    filesystem `dev`. True when the whole tree is gone."""
    try:
        st = os.lstat(path)
    except OSError:
        return True
    if st.st_dev != dev:
        # Another filesystem: a mount. Not ours to empty.
        return False
    if stat.S_ISDIR(st.st_mode):
        try:
            names = os.listdir(path)
        except OSError:
            return False
        ok = True
        for name in names:
            ok = _remove_one_fs(os.path.join(path, name), dev) and ok
        if not ok:
            return False
        try:
            os.rmdir(path)
        except OSError:
            return False
        return True
    try:
        os.unlink(path)
    except OSError:
        return False
    return True


def _remove_skeleton(host, base):
    """Unmount whatever is below `base` and remove the tree.

    The tree is removed only when the mount table shows nothing
    mounted at or below it, and the removal itself stops at any
    entry on another filesystem. A skeleton that cannot be
    removed whole stays where it is, for the sweep to finish.
    Returns True when the skeleton is gone.
    """
    below = _mounted_below(host, base)
    if below is None:
        return False
    for point in below:
        _unmount(host, point)
    if _mounted_below(host, base) != []:
        return False
    try:
        dev = os.lstat(base).st_dev
    except OSError:
        return True
    return _remove_one_fs(base, dev)


def _jail_exists(host, name):
    rc, _out, _err = _quiet(host, [JLS_BIN, "-j", name, "jid"])
    return rc == 0


def _remove_jail(host, name, rules=False):
    """Remove a jail's rctl rules and the jail, which ends every
    process inside it, and wait for it to be gone. The rules go
    first, while the jail's name still stands to find them by:
    a rule outlives the jail it was written for."""
    if rules:
        _quiet(host, [RCTL_BIN, "-r", "jail:" + name])
    _quiet(host, [JAIL_BIN, "-r", name])
    for _attempt in range(20):
        if not _jail_exists(host, name):
            break
        host.sleep(0.1)


def _teardown(host, name, base, applied, rules=False):
    """Remove the jail, unmount the skeleton, delete it.

    Best effort and idempotent: every step ignores failure,
    because teardown runs from release paths that must not
    raise over a job that already finished. True when nothing
    of the job is left on the host.
    """
    if name:
        _remove_jail(host, name, rules)
    for entry in reversed(applied or []):
        _unmount(host, entry["point"])
    if base:
        return _remove_skeleton(host, base)
    return True


def _create_jail(host, name, root, loopback, superuser):
    """Create the persistent jail; None or the problem."""
    try:
        rc, _out, err = host.run(
            jail_parameters(name, root, loopback, superuser))
    except (OSError, subprocess.SubprocessError) as e:
        return "jail -c failed: %s" % e
    if rc != 0:
        return "jail -c failed (exit %d): %s" % (
            rc, err.strip()[:200])
    return None


def _engage_loopback(host, name, keep_superuser):
    """Bring the jail's own lo0 up, then take the super-user's
    privilege away unless a job user still needs the door.

    The address is configured from inside the jail, which needs
    the privilege, so the jail is created with it and loses it
    here -- before any job process exists."""
    rc, _out, err = _quiet(
        host, [JEXEC_BIN, name, IFCONFIG_BIN, "lo0", "inet",
               "127.0.0.1/8", "up"])
    if rc != 0:
        return "the jail's loopback could not be brought up " \
            "(exit %d): %s" % (rc, err.strip()[:200])
    if keep_superuser:
        return None
    rc, _out, err = _quiet(
        host, [JAIL_BIN, "-m", "name=" + name, "allow.nosuser"])
    if rc != 0:
        return "jail -m allow.nosuser failed (exit %d): %s" % (
            rc, err.strip()[:200])
    return None


def _apply_rctl(host, name, st):
    """Write the jail-wide rules; None or the problem."""
    for rule in rctl_rules(name, st):
        rc, _out, err = _quiet(host, [RCTL_BIN, "-a", rule])
        if rc != 0:
            return "rctl -a %s failed (exit %d): %s" % (
                rule, rc, err.strip()[:200])
    return None


def _build_jail(host, st, name, workdir, user, rctl, prefixes=()):
    """Skeleton, mounts, jail, loopback and rules for one jail.

    Returns (base, root, applied). On any failure everything
    made so far is torn down and RuntimeError carries the
    problem: there is no half-built jail to run a job in.
    """
    base = None
    applied = []
    made = False
    try:
        base, skel, root = _make_skeleton(
            host, st,
            [dst for _src, dst in st["extra_ro_binds"]] + list(prefixes))
        applied, problem = _apply_mounts(
            host, mount_plan(skel, root, workdir, st, prefixes))
        if problem is None:
            made = True
            problem = _create_jail(
                host, name, root, st["loopback"],
                superuser=(user is not None or st["loopback"]))
        if problem is None and st["loopback"]:
            problem = _engage_loopback(
                host, name, keep_superuser=user is not None)
        if problem is None and rctl:
            problem = _apply_rctl(host, name, st)
        if problem is not None:
            raise RuntimeError(problem)
    except Exception:
        _teardown(host, name if made else None, base, applied, rctl)
        raise
    return base, root, applied


def _limits(memory_bytes):
    return [LIMITS_BIN, "-v", str(int(memory_bytes)),
            "-d", str(int(memory_bytes))]


def _trial(host, st, timeout=15):
    """Build a throwaway jail as a job's would be built and run
    the trial inside it; None or the problem, by name."""
    try:
        controls, rctl = controls_for(host, st, user=None)
    except RuntimeError as e:
        return str(e)
    name = jail_name("probe", host.pid())
    base = None
    applied = []
    try:
        base, _root, applied = _build_jail(
            host, st, name, None, None, rctl)
    except RuntimeError as e:
        return str(e)
    except (OSError, subprocess.SubprocessError) as e:
        return "confinement trial failed: %s" % e
    try:
        rc, out, err = host.run(
            [JEXEC_BIN, "-d", st["work_mount"], name]
            + _limits(st["process_memory_bytes"])
            + [SH_BIN, "-c", TRIAL_SCRIPT], timeout=timeout)
        words = out.split()
        if rc != 0 or "END" not in words:
            return "in-jail trial run failed (exit %d): %s" % (
                rc, err.strip()[:200])
        if "WORK-OK" not in words or "TMP-OK" not in words:
            return ("the trial could not write its work mount and "
                    "its /tmp: %s" % err.strip()[:200])
        if "ROOT-WRITABLE" in words:
            return ("the trial wrote the jail root: the read-only "
                    "root did not engage")
        if "PRIVILEGED" in words:
            return ("root inside the trial jail kept its privilege: "
                    "allow.nosuser did not engage")
        if "NULL-OK" not in words or "DEVICES-EXPOSED" in words:
            return ("the trial jail's /dev is not the jail ruleset's: "
                    "devfs ruleset 4 (devfsrules_jail) is not loaded "
                    "on this host (see devfs_load_rulesets in "
                    "rc.conf)")
        if st["loopback"]:
            lrc, lout, _lerr = _quiet(
                host, [JEXEC_BIN, name, IFCONFIG_BIN, "lo0"])
            if lrc != 0 or "127.0.0.1" not in lout:
                return ("the trial jail's loopback does not carry "
                        "127.0.0.1")
        if rctl:
            rrc, rout, rerr = _quiet(host, [RCTL_BIN, "jail:" + name])
            held = [ln for ln in rout.splitlines() if ":deny=" in ln]
            if rrc != 0 or len(held) < len(rctl_rules(name, st)):
                return "the trial jail's rctl rules did not take: " \
                    "%s" % (rerr.strip()[:200] or rout.strip()[:200])
        return None
    except (OSError, subprocess.SubprocessError) as e:
        return "confinement trial failed: %s" % e
    finally:
        _teardown(host, name, base, applied, rctl)


def sweep_stale(host=None):
    """Remove what a dead runner left on this host.

    A jail and a skeleton carry the process id of the runner
    that made them. One whose runner is gone is removed: the
    jail first (which ends its processes), then its rctl rules,
    then every mount below its skeleton and the skeleton
    itself. A skeleton from before the names carried a process
    id is removed when no jail stands on it. A live runner's
    jobs -- this process's own included -- are never touched.
    Returns a line for each thing removed.
    """
    host = host or _HOST
    removed = []
    own = host.pid()

    def dead(pid):
        return pid != own and not host.pid_alive(pid)

    rc, out, _err = _quiet(host, [JLS_BIN, "name"])
    names = out.split() if rc == 0 else []
    racct = _racct_enabled(host) and host.executable(RCTL_BIN)
    for name in names:
        m = _JAIL_NAME.match(name)
        if m and dead(int(m.group(2))):
            _remove_jail(host, name, rules=racct)
            removed.append("jail %s" % name)
    if racct:
        rc, out, _err = _quiet(host, [RCTL_BIN])
        seen = set()
        for line in (out.splitlines() if rc == 0 else []):
            parts = line.split(":")
            if len(parts) > 2 and parts[0] == "jail":
                seen.add(parts[1])
        for name in sorted(seen):
            m = _JAIL_NAME.match(name)
            if m and dead(int(m.group(2))) \
                    and not _jail_exists(host, name):
                _quiet(host, [RCTL_BIN, "-r", "jail:" + name])
                removed.append("rctl rules of %s" % name)
    rc, out, _err = _quiet(host, [JLS_BIN, "path"])
    paths = out.split() if rc == 0 else None
    folder = host.temp_folder()
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        entries = []
    for entry in entries:
        if not entry.startswith(SKELETON_PREFIX):
            continue
        base = os.path.join(folder, entry)
        m = _SKELETON_NAME.match(entry)
        if m:
            if not dead(int(m.group(1))):
                continue
        elif "-" in entry[len(SKELETON_PREFIX):]:
            continue
        if paths is None or any(_inside(p, (base,)) for p in paths):
            # A jail still stands on it, or the jails cannot be
            # read: leave it.
            continue
        if _remove_skeleton(host, base):
            removed.append("skeleton %s" % base)
    return removed


def posture_lines(cfg=None, host=None):
    """(level, text) lines for the posture report: what a job's
    jail would carry on this host, read without building one.

    The report is advisory and read-only, so this is the cheap
    half -- the config, root, the tools, the host's facts --
    and never the trial. A WARN is something the startup gate
    would refuse on at enforce.
    """
    host = host or _HOST
    refuse = "; confinement in enforce mode would refuse to start"
    try:
        st = confinement_settings(cfg)
        problem = _basic_problem(host, st)
        if problem is not None:
            raise RuntimeError(problem)
        controls, rctl = controls_for(host, st)
    except RuntimeError as e:
        return [("WARN", "FreeBSD jail backend cannot engage: %s%s"
                 % (e, refuse))]
    lines = [("OK", "FreeBSD jail backend: %s"
              % confinement_status(controls))]
    if not rctl:
        lines.append((
            "OK", "RACCT is not enabled on this host, so the "
            "jail-wide rctl ceilings are not written "
            "(kern.racct.enable=1 in /boot/loader.conf and a "
            "reboot engage them)"))
    return lines


_trial_lock = threading.Lock()
_trial_passed = set()
_swept = []


def _startup_problem(cfg=None, timeout=15, host=None, cached=False):
    host = host or _HOST
    try:
        st = confinement_settings(cfg)
    except RuntimeError as e:
        return str(e)
    problem = _basic_problem(host, st)
    if problem is not None:
        return problem
    key = _settings_key(st)
    with _trial_lock:
        if cached and key in _trial_passed:
            return None
        if not _swept:
            _swept.append(True)
            try:
                sweep_stale(host)
            except Exception:
                pass
        problem = _trial(host, st, timeout)
        if problem is None:
            _trial_passed.add(key)
        return problem


def _start_reaper(host, name):
    """Start the watcher for one jail; returns (process, fd).

    The watcher sits on the read end of a pipe. The write end
    stays in the runner and nowhere else (it is not inherited
    by any process the runner starts), so it closes when the
    runner is gone, whatever ended it.
    """
    read_end, write_end = os.pipe()
    try:
        proc = host.popen(
            [SH_BIN, "-c", REAPER_SCRIPT, "hp-reaper", name],
            stdin=read_end, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, cwd="/",
            start_new_session=True)
    except Exception:
        os.close(read_end)
        os.close(write_end)
        raise
    os.close(read_end)
    return proc, write_end


def _stop_reaper(reaper):
    """Tell the watcher the release has the jail, and reap it."""
    if reaper is None:
        return
    proc, write_end = reaper
    try:
        os.write(write_end, b"done\n")
    except OSError:
        pass
    try:
        os.close(write_end)
    except OSError:
        pass
    try:
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


class FreeBSDConfinedProcess:
    """The Popen subset exec.py drives, for a confined spawn.

    .pid, .returncode, .communicate(timeout), .kill(), .poll().
    The wrapped process is the jexec process, which IS the
    job's first process inside the jail (jexec attaches and
    execs), started in its own session so a tree kill by
    process group reaches it. communicate raises
    subprocess.TimeoutExpired on timeout, exactly as Popen's
    does (the wrapped Popen raises it). .close() is the
    release: it tears the jail down once the process has
    exited. .confinement_status names exactly the controls
    this job's jail carried, and .confinement_notes any
    read-only mount added for the job's interpreter.
    """

    def __init__(self, argv, inner, host, name, base, applied,
                 rules, reaper, status, notes):
        self.args = argv
        self.pid = inner.pid
        self._inner = inner
        self._host = host
        self._name = name
        self._base = base
        self._applied = applied
        self._rules = rules
        self._reaper = reaper
        self.returncode = None
        self.confinement_status = status
        self.confinement_notes = list(notes)
        self._closed = False

    def communicate(self, timeout=None):
        out, err = self._inner.communicate(timeout=timeout)
        self.returncode = self._inner.returncode
        return out, err

    def poll(self):
        rc = self._inner.poll()
        if rc is not None:
            self.returncode = rc
        return self.returncode

    def kill(self):
        try:
            self._inner.kill()
        except Exception:
            pass

    def close(self):
        """The release: remove the jail (which ends anything
        still inside it) and its rules, unmount the skeleton,
        delete it."""
        if self._closed:
            return
        self._closed = True
        _stop_reaper(self._reaper)
        self._reaper = None
        _teardown(self._host, self._name, self._base, self._applied,
                  self._rules)
        self._name = None


def _spawn(argv, cwd=None, env=None, user=None, memory_bytes=None,
           cfg=None, host=None):
    host = host or _HOST
    st = confinement_settings(cfg)
    if memory_bytes is None:
        memory_bytes = st["process_memory_bytes"]
    problem = _basic_problem(host, st)
    if problem is not None:
        raise RuntimeError(problem)
    controls, rctl = controls_for(host, st, user)
    notes = []
    inner_argv, prefixes = translate_argv(
        argv, cwd, st, which=host.which, notes=notes)
    name = jail_name("job", host.pid())
    base, _root, applied = _build_jail(
        host, st, name, cwd, user, rctl, prefixes)
    reaper = None
    try:
        reaper = _start_reaper(host, name)
        cmd = [JEXEC_BIN]
        if cwd:
            # The host spawn's cwd is the job's run directory;
            # inside the jail that directory is the work mount,
            # and relative-path jobs must land there.
            cmd += ["-d", st["work_mount"]]
        if user:
            # -u resolves the user in the HOST's user database
            # (the account the job_user seam named); -U would
            # resolve in the jail's, which a skeleton /etc
            # cannot serve.
            cmd += ["-u", user]
        cmd += [name] + _limits(memory_bytes) + inner_argv
        env2 = dict(env) if env is not None else dict(os.environ)
        if not env2.get("PATH"):
            env2["PATH"] = JAIL_PATH
        inner = host.popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env2, start_new_session=True)
    except Exception:
        _stop_reaper(reaper)
        _teardown(host, name, base, applied, rctl)
        raise
    return FreeBSDConfinedProcess(
        list(argv), inner, host, name, base, applied, rctl, reaper,
        confinement_status(controls), notes)


if not sys.platform.startswith("freebsd"):
    # Stubs so the rest of the runner can import without error.
    # The startup probe answers a problem string (never None),
    # so an enforce gate consulting this stub refuses, and the
    # spawn raises: off FreeBSD this backend can never claim to
    # have engaged. IS_FREEBSD_BACKEND is how the gates tell
    # this stub from the real implementation below: only a real
    # backend's probe is ever consulted, so a simulated FreeBSD
    # answers the refusal deterministically on any host.
    IS_FREEBSD_BACKEND = False

    def freebsd_startup_problem(*args, **kwargs):
        return "freebsd_confine is FreeBSD-only"

    def freebsd_confinement_problem(*args, **kwargs):
        return "freebsd_confine is FreeBSD-only"

    def spawn_confined_process(*args, **kwargs):
        raise RuntimeError("freebsd_confine is FreeBSD-only")

    def build_jail_argv(*args, **kwargs):
        raise RuntimeError("freebsd_confine is FreeBSD-only")
else:
    IS_FREEBSD_BACKEND = True

    def freebsd_startup_problem(cfg=None, timeout=15):
        """None when the confinement controls can engage here.

        The trial, run now: root and the base tools, a
        throwaway skeleton with its mounts, a throwaway jail
        with a job's parameters, and a trial process inside it
        under the spawn limits, then everything removed. Any
        failure is named, and the enforce gate refuses with it.
        """
        return _startup_problem(cfg, timeout=timeout)

    def freebsd_confinement_problem(cfg=None, timeout=15):
        """None when the confinement controls can engage here.

        The gate's probe: the cheap checks every time, and the
        trial once per runner process for each set of settings
        it is asked about -- a passing verdict is kept, so the
        per-job gate does not build a throwaway jail beside
        every job's own.
        """
        return _startup_problem(cfg, timeout=timeout, cached=True)

    def build_jail_argv(argv, cwd=None, cfg=None):
        """The argv a job's command becomes inside its jail
        (translate_argv, under the config's settings)."""
        return translate_argv(argv, cwd, confinement_settings(cfg))[0]

    def spawn_confined_process(argv, cwd=None, env=None, user=None,
                               memory_bytes=None, cfg=None):
        """Create a job process under every confinement control.

        argv is the full command (interpreter, script, args) in
        host paths; cwd is the job's work directory, mounted at
        the work mount inside the jail. The jail is created
        first, the job is started inside it under the spawn
        resource limits via jexec (as `user` when the job_user
        seam hands one over), and a FreeBSDConfinedProcess is
        returned whose .confinement_status names the controls
        applied. Raises RuntimeError when any control could not
        be applied -- there is no unconfined fallback to fall
        through to.
        """
        return _spawn(argv, cwd=cwd, env=env, user=user,
                      memory_bytes=memory_bytes, cfg=cfg)
