#!/usr/bin/env python3
"""FreeBSD containment: jails, and the confinement backend.

No external dependencies; stdlib only, driving the base system's
own tools (/usr/sbin/jail, /usr/sbin/jexec, /sbin/mount,
/usr/bin/limits). One seam uses this module:

- confinement: the controls named by STATUS_CONFINEMENT --
  "freebsd: jail + no_network + spawn_resource_limits". A job
  process is executed inside a freshly created jail(8) whose
  root is a per-job skeleton: the host's /usr, /usr/local,
  /bin, /lib,
  /libexec and /sbin are mounted read-only (nullfs), the job's
  work directory is the only writable mount (at /work), /tmp is
  a fresh tmpfs, and /dev is the jail devfs (ruleset 4: the few
  nodes a job needs, nothing else). The jail is created with
  ip4=disable and ip6=disable, so the job has no network at
  all -- not even loopback. The memory ceiling is applied at
  spawn: the job's command runs under limits(1) with the
  virtual-memory and data-size limits both set to
  DEFAULT_PROCESS_MEMORY_BYTES (512 MiB). The jail exists
  before the job's first process runs (jexec starts the job
  inside it), so there is no race in which the job runs
  unconfined; the process object owns the teardown, and its
  release (FreeBSDConfinedProcess.close) removes the jail,
  unmounts the skeleton and deletes it.

What this is NOT, stated plainly wherever it is recorded:

- The memory ceiling is a per-process resource limit applied
  at spawn (setrlimit via limits(1)), not an rctl(8) rule.
  RACCT/RCTL is present on the fleet node but disabled
  (kern.racct.enable=0, a boot tunable), so rctl cannot deny
  anything there; the audit record names spawn_resource_limits
  and never rctl. On a host with RACCT enabled a future pass
  can name the stronger control -- it will change the status
  string when it does, not before.
- Capsicum is not used. Capsicum capability mode is entered
  in-process by the confined program itself; this launcher
  starts arbitrary job interpreters that know nothing of it,
  so it does not fit the launcher shape. The jail is the
  filesystem and network boundary instead.
- The job runs as root inside its jail (uid 0 in the jail's
  own id space) unless the job_user seam hands the spawn a
  user, which jexec then applies at the jail door (jexec -u,
  resolved in the host's user database).
  The jail root cannot see the host filesystem outside the
  mounts above, cannot mount, cannot use raw sockets or
  System V IPC (the jail defaults deny all three), and its
  root is not host root: a process that escapes the job still
  has to escape the jail, which is the kernel's boundary, not
  this module's claim to have written one.

Supposition, recorded before the field test on the fleet
FreeBSD node (FreeBSD 14.5-RELEASE): before this backend,
confinement at enforce on FreeBSD refused at startup
("confinement (bwrap) is Linux-only; this machine is
freebsd14"). After it, the startup probe -- a throwaway
skeleton, its nullfs mounts, a throwaway jail created and
removed, and a `true` run inside it under the spawn limits --
returns None on a host where those calls work (root, jail(8),
mount_nullfs), the runner starts with confinement at enforce,
a job's audit record names STATUS_CONFINEMENT, an escape write
to a host path outside the work mount does not land (the path
does not exist inside the jail root), an escape read of a host
file does not return its contents (same reason -- stronger
than the Windows backend, which has no namespace isolation),
and a job that tries to commit 700 MiB is refused by the
512 MiB spawn limit. The probe, not an assumption, is what
the gate consults. Conclusions from the field test are
recorded in docs/steady/security/freebsd.md.

This module is import-safe on non-FreeBSD; functions that need
the platform raise or return a problem string when called off
FreeBSD.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

# The one ceiling this backend sets: 512 MiB per job process,
# applied as both the virtual-memory and the data-size resource
# limit at spawn. A named constant, mirroring the Windows
# backend's ceiling; not a config knob yet.
DEFAULT_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024

# The confinement controls, named exactly. Every audit and
# startup record for FreeBSD confinement carries this string
# and nothing stronger.
STATUS_CONFINEMENT = "freebsd: jail + no_network + spawn_resource_limits"
CONFINEMENT_CONTROLS = ("jail", "no_network", "spawn_resource_limits")

# Where the job's work directory is mounted inside the jail.
WORK_MOUNT = "/work"

JAIL_BIN = "/usr/sbin/jail"
JEXEC_BIN = "/usr/sbin/jexec"
LIMITS_BIN = "/usr/bin/limits"
MOUNT_BIN = "/sbin/mount"
UMOUNT_BIN = "/sbin/umount"

# Host trees mounted read-only inside the jail root. Together
# they are the whole userland a job can execute: the
# interpreter, its libraries and the base tools. Nothing else
# of the host filesystem exists inside the jail.
#: Host paths mounted read-only (nullfs) into the jail root, in
#: mount order, parents before children: a child tree that
#: lives on its parent's filesystem (a plain directory under
#: it, like /usr/local under /usr on a stock FreeBSD) is
#: already exposed by the parent's mount and is not mounted
#: again -- nullfs refuses that cycle. /usr/local is listed
#: because it is where the pkg-installed interpreters live;
#: on a host where it is its own filesystem it mounts for real.
RO_MOUNTS = ("/usr", "/usr/local", "/bin", "/lib", "/libexec",
             "/sbin")

# The PATH a jailed job sees when the caller's env names none.
JAIL_PATH = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if not sys.platform.startswith("freebsd"):
    # Stub so the rest of the runner can import without error.
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

    def _run(argv, timeout=30):
        """Run a base-system tool; return (rc, stdout, stderr)."""
        proc = subprocess.run(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout)
        return (proc.returncode,
                proc.stdout.decode("utf-8", "replace"),
                proc.stderr.decode("utf-8", "replace"))

    def _jail_name(tag):
        """A jail name: alphanumerics only, unique per call."""
        return "hp%s%s" % (tag, uuid.uuid4().hex[:12])

    def _basic_problem():
        """Why the backend cannot engage at all here, or None.

        Root (jail creation, nullfs mounts), and the base tools
        themselves. The full trial is freebsd_confinement_
        problem's; this is the cheap half the spawn also checks,
        so a spawn on a host that lost root refuses instead of
        half-engaging.
        """
        if os.geteuid() != 0:
            return ("creating a jail needs root; the runner is "
                    "not running as root")
        for path in (JAIL_BIN, JEXEC_BIN, LIMITS_BIN, MOUNT_BIN,
                     UMOUNT_BIN):
            if not (os.path.isfile(path) and os.access(path, os.X_OK)):
                return "%s is missing or not executable" % path
        for tree in RO_MOUNTS:
            if not os.path.isdir(tree):
                return "host tree %s is missing" % tree
        return None

    def _make_skeleton():
        """A fresh jail root: empty mount points, a minimal /etc.

        The /etc carries copies of the host's passwd and group
        files so the jail's own name service sees the host's
        accounts; the spawn's user is resolved on the host
        side (jexec -u), not in here.
        """
        root = tempfile.mkdtemp(prefix="hp-jail-")
        # mkdtemp makes the root 0700; a job demoted to the
        # job user must be able to traverse its own jail root
        # to reach the mounts (a root-run jexec masks this --
        # the field test's demoted spawn could not exec at
        # 0700). The skeleton holds only mount points and the
        # /etc copies below, nothing that needs the tighter
        # mode.
        os.chmod(root, 0o755)
        for name in ("usr", "bin", "lib", "libexec", "sbin",
                     "etc", "tmp", "dev", "work"):
            os.mkdir(os.path.join(root, name))
        for name in ("passwd", "group"):
            try:
                shutil.copyfile("/etc/" + name,
                                os.path.join(root, "etc", name))
            except OSError:
                pass
        # The dynamic loader's hints live in /var/run on
        # FreeBSD; without them, binaries linked against
        # /usr/local libraries (the pkg-installed python3 is
        # the standing case) fail inside the jail with
        # "Shared object ... not found" while /bin tools,
        # which link only against /lib, run fine -- the field
        # test's file-write job found exactly that. The
        # skeleton carries a copy of the hints, nothing else
        # of /var.
        os.makedirs(os.path.join(root, "var", "run"))
        try:
            shutil.copyfile("/var/run/ld-elf.so.hints",
                            os.path.join(root, "var", "run",
                                         "ld-elf.so.hints"))
        except OSError:
            pass
        os.chmod(os.path.join(root, "tmp"), 0o1777)
        return root

    def _mounts_for(root, workdir):
        """(argv, undo) pairs, in the order to apply them."""
        mounts = []
        for tree in RO_MOUNTS:
            mounts.append([MOUNT_BIN, "-t", "nullfs", "-o", "ro",
                           tree, os.path.join(root, tree[1:])])
        mounts.append([MOUNT_BIN, "-t", "tmpfs", "tmpfs",
                       os.path.join(root, "tmp")])
        if workdir:
            mounts.append([MOUNT_BIN, "-t", "nullfs", workdir,
                           os.path.join(root, "work")])
        else:
            mounts.append([MOUNT_BIN, "-t", "tmpfs", "tmpfs",
                           os.path.join(root, "work")])
        return mounts

    def _apply_mounts(mounts, timeout):
        """Apply the mount argvs in order; (applied, problem).

        A nullfs entry is skipped when an entry already applied
        mounts an ancestor of its source AND the source lives on
        the same host filesystem as that ancestor (same device):
        the ancestor's mount already exposes the source at
        exactly that path, and mounting it again is a cycle
        nullfs refuses ("Resource deadlock avoided"). This is
        /usr/local on a stock FreeBSD: a plain directory under
        /usr, not a filesystem of its own. Where the child IS
        its own filesystem (a different device), it is mounted
        for real. Only mounts actually applied are returned,
        for teardown.
        """
        applied = []
        mounted = []  # (source, st_dev) actually mounted
        for argv in mounts:
            if argv[1:3] == ["-t", "nullfs"]:
                src = argv[-2]
                try:
                    dev = os.stat(src).st_dev
                except OSError:
                    dev = None
                if dev is not None and any(
                        dev == adev and (
                            src == asrc
                            or src.startswith(asrc + "/"))
                        for asrc, adev in mounted):
                    continue
            rc, _out, err = _run(argv, timeout=timeout)
            if rc != 0:
                return applied, "mount %s failed (exit %d): %s" % (
                    argv[-1], rc, err.strip()[:200])
            applied.append(argv)
            if argv[1:3] == ["-t", "nullfs"]:
                try:
                    mounted.append(
                        (argv[-2], os.stat(argv[-2]).st_dev))
                except OSError:
                    pass
        return applied, None

    def _teardown(name, root, mounts):
        """Remove the jail, unmount the skeleton, delete it.

        Best effort and idempotent: every step ignores failure,
        because teardown runs from release paths that must not
        raise over a job that already finished.
        """
        if name:
            try:
                _run([JAIL_BIN, "-r", name], timeout=15)
            except Exception:
                pass
        for argv in reversed(mounts or []):
            try:
                _run([UMOUNT_BIN, argv[-1]], timeout=15)
            except Exception:
                pass
        if root:
            shutil.rmtree(root, ignore_errors=True)

    def _create_jail(name, root):
        """Create the persistent jail; None or the problem."""
        argv = [JAIL_BIN, "-c",
                "name=" + name,
                "path=" + root,
                "host.hostname=hp-job",
                "ip4=disable",
                "ip6=disable",
                "mount.devfs",
                "devfs_ruleset=4",
                "enforce_statfs=1",
                "persist=true"]
        rc, _out, err = _run(argv, timeout=30)
        if rc != 0:
            return "jail -c failed (exit %d): %s" % (
                rc, err.strip()[:200])
        return None

    def freebsd_startup_problem(cfg=None, timeout=15):
        """None when the confinement controls can engage here.

        The trial: root and the base tools, a throwaway skeleton
        with its nullfs mounts, a throwaway jail created on it,
        a `true` run inside the jail under the spawn limits,
        then everything removed. Any failure is named, and the
        enforce gate refuses with it. This proves creation,
        mounting and the in-jail spawn work; a particular job's
        spawn still makes its own jail, and its failure refuses
        that job then -- the probe never stands in for it.
        """
        problem = _basic_problem()
        if problem is not None:
            return problem
        name = _jail_name("probe")
        root = None
        mounts = []
        try:
            root = _make_skeleton()
            mounts, problem = _apply_mounts(
                _mounts_for(root, None), timeout)
            if problem is not None:
                return problem
            problem = _create_jail(name, root)
            if problem is not None:
                return problem
            rc, _out, err = _run(
                [JEXEC_BIN, name, LIMITS_BIN, "-v",
                 str(DEFAULT_PROCESS_MEMORY_BYTES), "-d",
                 str(DEFAULT_PROCESS_MEMORY_BYTES), "/usr/bin/true"],
                timeout=timeout)
            if rc != 0:
                return "in-jail trial run failed (exit %d): %s" % (
                    rc, err.strip()[:200])
            return None
        except (OSError, subprocess.SubprocessError) as e:
            return "confinement trial failed: %s" % e
        finally:
            _teardown(name, root, mounts)

    # The confinement probe is the only probe this backend has:
    # unlike the Windows backend's two controls there is no
    # lesser subset to gate separately.
    freebsd_confinement_problem = freebsd_startup_problem

    def build_jail_argv(argv, cwd=None):
        """Translate a host argv into the argv that runs in-jail.

        The interpreter is resolved on the host; a resolved path
        under one of the read-only mounted trees keeps its path
        (the mounts mirror the host layout), a path under the
        job's work directory (cwd) becomes its /work path, and
        anything else cannot be engaged honestly -- the file
        would not exist inside the jail -- so it raises. Every
        later argument under cwd is translated the same way;
        other arguments (including absolute host paths outside
        the mounts, which are the job's own business and simply
        do not resolve inside the jail) pass unchanged.
        """
        if not isinstance(argv, (list, tuple)) or not argv \
                or not all(isinstance(a, str) for a in argv):
            raise RuntimeError(
                "confined spawn needs a non-empty list of strings")
        out = []
        for i, arg in enumerate(argv):
            if i == 0 and "/" not in arg:
                resolved = shutil.which(arg)
                if resolved is None:
                    raise RuntimeError(
                        "cannot resolve interpreter %r for the "
                        "jail" % arg)
                arg = resolved
            if cwd and (arg == cwd or arg.startswith(cwd + os.sep)):
                out.append(WORK_MOUNT + arg[len(cwd):])
                continue
            if i == 0:
                if not any(arg == t or arg.startswith(t + "/")
                           for t in RO_MOUNTS):
                    raise RuntimeError(
                        "interpreter %r does not live under a "
                        "mounted tree (%s); it would not exist "
                        "inside the jail" % (arg, ", ".join(RO_MOUNTS)))
            out.append(arg)
        return out

    class FreeBSDConfinedProcess:
        """The Popen subset exec.py drives, for a confined spawn.

        .pid, .returncode, .communicate(timeout), .kill(),
        .poll(). The wrapped process is the jexec process, which
        IS the job's first process inside the jail (jexec
        attaches and execs), started in its own session so a
        tree kill by process group reaches it. communicate
        raises subprocess.TimeoutExpired on timeout, exactly as
        Popen's does (the wrapped Popen raises it). .close() is
        the release: it tears the jail down once the process
        has exited.
        """

        def __init__(self, argv, inner, name, root, mounts):
            self.args = argv
            self.pid = inner.pid
            self._inner = inner
            self._name = name
            self._root = root
            self._mounts = mounts
            self.returncode = None
            self.confinement_status = STATUS_CONFINEMENT
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
            still inside it), unmount the skeleton, delete it."""
            if self._closed:
                return
            self._closed = True
            _teardown(self._name, self._root, self._mounts)
            self._name = None

    def spawn_confined_process(argv, cwd=None, env=None, user=None,
                               memory_bytes=DEFAULT_PROCESS_MEMORY_BYTES):
        """Create a job process under every confinement control.

        argv is the full command (interpreter, script, args) in
        host paths; cwd is the job's work directory, mounted at
        /work inside the jail. The jail is created first, the job
        is started inside it under the spawn resource limits via
        jexec (as `user` when the job_user seam hands one over),
        and a FreeBSDConfinedProcess is returned whose
        .confinement_status is STATUS_CONFINEMENT. Raises
        RuntimeError when any control could not be applied --
        there is no unconfined fallback to fall through to.
        """
        problem = _basic_problem()
        if problem is not None:
            raise RuntimeError(problem)
        inner_argv = build_jail_argv(argv, cwd=cwd)
        name = _jail_name("job")
        root = None
        mounts = []
        try:
            root = _make_skeleton()
            mounts, problem = _apply_mounts(
                _mounts_for(root, cwd), 30)
            if problem is not None:
                raise RuntimeError(problem)
            problem = _create_jail(name, root)
            if problem is not None:
                raise RuntimeError(problem)
            cmd = [JEXEC_BIN]
            if cwd:
                # The host spawn's cwd is the job's run
                # directory; inside the jail that directory is
                # /work, and relative-path jobs must land there.
                cmd += ["-d", "/work"]
            if user:
                # -u resolves the user in the HOST's user
                # database (the account the job_user seam
                # named); -U would resolve in the jail's,
                # which a skeleton /etc cannot serve.
                cmd += ["-u", user]
            cmd += [name, LIMITS_BIN, "-v", str(int(memory_bytes)),
                    "-d", str(int(memory_bytes))]
            cmd += inner_argv
            env2 = dict(env) if env is not None else dict(os.environ)
            if not env2.get("PATH"):
                env2["PATH"] = JAIL_PATH
            inner = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env2, start_new_session=True)
        except Exception:
            _teardown(name, root, mounts)
            raise
        return FreeBSDConfinedProcess(
            list(argv), inner, name, root, mounts)
