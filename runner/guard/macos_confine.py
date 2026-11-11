#!/usr/bin/env python3
"""macOS containment: Seatbelt profiles, and the confinement backend.

No external dependencies; stdlib only, driving the base system's
own tool (/usr/bin/sandbox-exec). One seam uses this module:

- confinement: the controls named by STATUS_CONFINEMENT --
  "macos: seatbelt_profile + no_network + spawn_resource_limits".
  A job process is executed under a Seatbelt profile generated
  for that job and applied by sandbox-exec(1): the profile
  starts from deny-by-default, allows executing and reading
  the system trees (/System, /usr, /Library, /bin, /sbin,
  /opt, /etc) and the job interpreter's own install prefix,
  allows reading and writing only inside the job's work
  directory, and names no network allow rule at all -- with an
  explicit (deny network*) line beside the deny-by-default
  base, so a confined job has no network, loopback included.
  The memory ceiling is applied at spawn by a small launcher
  shim: sandbox-exec first runs the runner's own interpreter
  on the shim text in this module, which sets the data-size
  resource limit to DEFAULT_PROCESS_MEMORY_BYTES (512 MiB)
  with setrlimit, drops to the job user when the job_user
  seam hands one over (the POSIX preexec demote cannot ride
  a spawn that replaces process creation, so the demote
  happens in the shim, at the spawn door -- the FreeBSD
  backend's jexec -u shape), and then execs the job's
  command. Only the data-size limit is set, never the
  virtual-memory (address-space) limit: on macOS the
  address space a process maps at startup -- the dynamic
  loader, the dyld shared cache, the system libraries --
  already exceeds 512 MiB, so a 512 MiB RLIMIT_AS made
  every exec'd interpreter abort (SIGABRT, exit -6) before
  its first line of job code, which is the shape of the
  first live failure (build run 43089173541, recorded in
  docs/steady/security/macos.md, supposition S1). The
  data-size limit is the ceiling macOS enforces on a
  process's data mappings, and it is the one this backend
  has applied since that fix. The profile is in force before
  the shim's first line runs (sandbox-exec applies it to the
  process it starts), so there is no race in which the job
  runs unconfined; the process object owns nothing to tear
  down beyond the wrapped process itself, because the profile
  is passed to sandbox-exec as an argument, never written to
  a file.

What this is NOT, stated plainly wherever it is recorded:

- App Sandbox is not used. App Sandbox is an entitlement a
  bundled application opts itself into; this launcher starts
  arbitrary job interpreters that carry no entitlement, so it
  does not fit the launcher shape. Seatbelt through
  sandbox-exec is the mechanism that fits a launcher.
- The profile is not a filesystem namespace and not a jail.
  It is a mandatory-access profile over the host filesystem:
  paths the profile does not name cannot be read -- stronger
  than the Windows backend, whose confined jobs can read any
  path their token can read -- and it is not the FreeBSD
  jail's separate root: the job sees the host's path layout,
  and the profile, not a mount table, is what refuses it.
- The memory ceiling is a per-process resource limit applied
  at spawn (setrlimit in the launcher shim), not a Seatbelt
  rule. Seatbelt has no resource-limit operation, which is
  why the shim exists; the audit record names
  spawn_resource_limits and never a Seatbelt memory control.
- sandbox-exec is a tool Apple has marked deprecated while
  still shipping it and still building App Sandbox on the
  same profile language. The startup probe, not an
  assumption, is what the gate consults: a macOS release
  that removes the tool, or a host where a confined trial
  process cannot work, refuses at startup -- fail-closed,
  never a weaker run.

Supposition, recorded before the build (2026-11-11; the full
record stands in docs/steady/security/macos.md): before this
backend, confinement at enforce on macOS refused at startup
("confinement (bwrap) is Linux-only; this machine is darwin").
After it, the startup probe -- sandbox-exec present, a
generated profile that parses, and a trial spawn under the
full controls that reads a staged file inside its work
directory and writes its output there -- returns None on a
host where those work, the runner starts with confinement at
enforce, a job's audit record names STATUS_CONFINEMENT, an
escape write outside the work directory does not land, an
escape read of a host file outside the allowed trees does
not return its contents, a job process carries the 512 MiB
spawn limits (its own getrlimit reads them back), and a
network attempt is refused by the profile. There is no Mac
in the project's fleet, so the CI macos-15 and macos-15-intel
legs are the field test for this platform; conclusions from
that proof are recorded in docs/steady/security/macos.md, in
the place the supposition stands.

This module is import-safe on non-macOS; functions that need
the platform raise or return a problem string when called
off darwin. The pure builders (the profile writer, the shim
argv builder, the sandbox argv builder) and the trial
orchestration are platform-neutral -- they stand above the
platform branch, like the Windows backend's trial -- so the
suite exercises them on any host; only the probe and the
spawn consult the platform.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import threading

# The one ceiling this backend sets: 512 MiB per job process,
# applied as the data-size resource limit at spawn (never the
# virtual-memory limit -- see the module docstring for the
# startup abort a virtual-memory ceiling causes on macOS).
# A named constant, mirroring the Windows and FreeBSD
# backends' ceiling; not a config knob yet.
DEFAULT_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024

# The confinement controls, named exactly. Every audit and
# startup record for macOS confinement carries this string
# and nothing stronger.
STATUS_CONFINEMENT = "macos: seatbelt_profile + no_network + spawn_resource_limits"
CONFINEMENT_CONTROLS = ("seatbelt_profile", "no_network",
                        "spawn_resource_limits")

SANDBOX_EXEC_BIN = "/usr/bin/sandbox-exec"

# System trees a confined job may read and execute: the whole
# userland a job can run -- the interpreter's libraries, the
# base tools, the dynamic loader's world. Nothing else of the
# host filesystem is readable under the profile.
SYSTEM_READ_PATHS = ("/System", "/usr", "/Library", "/bin",
                     "/sbin", "/opt", "/etc", "/private/etc")

# The name of the per-job temporary directory the spawn makes
# inside the work directory and points TMPDIR at: inside the
# one writable tree, so a job that uses its temp directory is
# exercising the work mount it already has, not a host /tmp
# the profile does not name.
JOB_TMP_NAME = ".hp-tmp"


# ----------------------------------------------------------------
# The profile writer (platform-neutral, pure)
# ----------------------------------------------------------------

def _validate_profile_path(value, label):
    """An absolute path a profile may name, or RuntimeError.

    A profile is text another program parses: a path carrying
    a control character (a NUL, a tab, a carriage return, a
    newline, any of them) cannot be carried by that text
    honestly -- several of them are line or token boundaries
    to one parser or another -- and a relative path would
    name a different tree than the caller means. Both are
    refused here, at the writer, never escaped into a profile
    that would silently mean something else.
    """
    if not isinstance(value, str) or not value:
        raise RuntimeError("%s must be a non-empty path string" % label)
    if not value.startswith("/"):
        raise RuntimeError("%s must be an absolute path: %r"
                           % (label, value))
    if any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in value):
        raise RuntimeError(
            "%s must not contain a control character" % label)
    return value


def _sb_quote(value):
    """`value` as a Seatbelt string literal.

    The profile language reads backslash escapes inside a
    double-quoted string, so the backslash and the quote are
    the two characters that must be escaped for a path to
    arrive as itself; every other character -- parentheses,
    semicolons, comment marks -- is inert inside a string
    literal. Control characters never reach here (the path
    validator refuses them).
    """
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _is_user_home(path):
    """True when `path` is a user home directory (the process
    user's own, any /home/<name> or /Users/<name>, or /root)."""
    if not isinstance(path, str) or not path:
        return False
    own = os.path.expanduser("~")
    if own.startswith("/") and path == own:
        return True
    if path == "/root":
        return True
    parts = path.split("/")
    return (len(parts) == 3 and parts[0] == ""
            and parts[1] in ("home", "Users") and bool(parts[2]))


def _install_prefix(path):
    """The directory a profile must let a job read so `path`
    can run: its grandparent when the parent is `bin`
    (…/x64/bin/python3 -> …/x64, bringing lib/ along), else its
    parent. Never shallower than two components, and never a
    user home directory: a bin grandparent that is a home
    directory falls back to the bin directory itself, so the
    whole home is never named. The mirror of the Linux
    sandbox's interpreter-prefix rule.
    """
    parent = os.path.dirname(path)
    if os.path.basename(parent) == "bin":
        grand = os.path.dirname(parent)
        if grand.count("/") >= 2 and grand != "/" \
                and not _is_user_home(grand):
            return grand
    if parent.count("/") >= 2:
        if _is_user_home(parent):
            return None
        return parent
    return None


def interpreter_read_paths(interpreter):
    """The read paths a job needs for `interpreter` to execute.

    The interpreter resolved on the host, and its realpath:
    a hosted toolcache python, a framework python, a venv
    interpreter (a symlink whose own prefix carries its
    configuration). Each contributes its install prefix;
    prefixes already inside the system trees need nothing.
    Raises RuntimeError when the interpreter cannot be
    resolved -- a confined spawn for an interpreter that does
    not exist is a refusal, not a profile that omits it.
    """
    if not isinstance(interpreter, str) or not interpreter:
        raise RuntimeError("interpreter must be a non-empty string")
    if "/" in interpreter:
        resolved = interpreter
    else:
        resolved = shutil.which(interpreter)
        if resolved is None:
            raise RuntimeError(
                "cannot resolve interpreter %r for the profile"
                % interpreter)
    out = []
    seen = set()
    for cand in (resolved, os.path.realpath(resolved)):
        if not cand.startswith("/"):
            continue
        if any(cand == t or cand.startswith(t + "/")
               for t in SYSTEM_READ_PATHS):
            continue
        prefix = _install_prefix(cand)
        if prefix is None or prefix in seen:
            continue
        if any(prefix == t or prefix.startswith(t + "/")
               for t in SYSTEM_READ_PATHS):
            continue
        seen.add(prefix)
        out.append(prefix)
    return out


def _with_canonical_twins(paths):
    """`paths` with each path's /private canonical twin added.

    On macOS /var and /tmp are firmlinks (in the filesystem,
    symlinks) to /private/var and /private/tmp, and Seatbelt
    path filters match the canonical path of the file a
    process touches: a rule naming only "/var/folders/..."
    never matches the staged file it means, which lives at
    "/private/var/folders/...". That is why SYSTEM_READ_PATHS
    already names /private/etc beside /etc; a job's work
    directory lives under the temp tree, so it needs the
    same twin or its staged read and its work write are
    refused (docs/steady/security/macos.md, supposition
    S2). The twin is added for /var and /tmp paths only,
    deduplicated, in first-seen order, so the writer stays
    deterministic and a path already named in canonical
    form gains nothing.
    """
    out = []
    for path in paths:
        if path not in out:
            out.append(path)
        for alias in ("/var", "/tmp"):
            if path == alias or path.startswith(alias + "/"):
                twin = "/private" + path
                if twin not in out:
                    out.append(twin)
                break
    return out


def build_profile(workdir, interpreter=None, read_paths=()):
    """The Seatbelt profile text for one job, deterministically.

    Fields, one by one:
    - workdir: the job's work directory -- the only tree the
      profile lets the job write, and the staged script's home.
    - interpreter: the job's interpreter (a bare name or a
      path); its install prefix joins the readable trees.
    - read_paths: extra trees the job may read (operator-named
      input trees), each validated the same way.

    The shape never varies: deny-by-default; process, sysctl,
    mach and IPC services a job interpreter needs to start and
    run; reads (with execution mapping) for the system trees,
    the interpreter prefix and the extra read paths; read +
    write inside the work directory; the /dev nodes a job's
    standard streams and entropy need; and the network denial
    stated. Paths under /var and /tmp are named with their
    /private canonical twins (see _with_canonical_twins), on
    the read line and the write line alike. No field can add
    a network allow rule, a write outside the work directory,
    or a read of a user home: the writer has no parameter
    that expresses them.
    """
    _validate_profile_path(workdir, "workdir")
    reads = list(SYSTEM_READ_PATHS)
    if interpreter is not None:
        reads.extend(interpreter_read_paths(interpreter))
    for path in read_paths:
        _validate_profile_path(path, "read_paths entry")
        if path not in reads:
            reads.append(path)
    if workdir not in reads:
        reads.append(workdir)
    reads = _with_canonical_twins(reads)
    read_args = " ".join("(subpath %s)" % _sb_quote(p) for p in reads)
    write_args = " ".join(
        "(subpath %s)" % _sb_quote(p)
        for p in _with_canonical_twins([workdir]))
    lines = [
        "(version 1)",
        "(deny default)",
        "(allow process*)",
        "(allow sysctl-read)",
        "(allow mach*)",
        "(allow ipc*)",
        "(allow signal (target self))",
        "(allow pseudo-tty)",
        "(allow file-read* file-map-executable %s)" % read_args,
        "(allow file-write* %s)" % write_args,
        '(allow file-read* file-write* (literal "/dev/null")'
        ' (literal "/dev/zero") (literal "/dev/random")'
        ' (literal "/dev/urandom") (subpath "/dev/fd"))',
        "(deny network*)",
    ]
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------
# The launcher shim (platform-neutral, pure)
# ----------------------------------------------------------------

# The shim's text. sandbox-exec starts the runner's own
# interpreter on it (through -c, so no shim file exists to
# stage); it sets the spawn resource limit, drops to the job
# user when one is named (argument 2, "-" when none), and
# execs the job's command (arguments 3 onward). A limit it
# cannot set, or a user it cannot drop to, ends the shim
# before the exec -- the job is refused, never run weaker.
# The one limit it sets is RLIMIT_DATA: a RLIMIT_AS at this
# ceiling is below the address space every macOS process
# maps at startup, and the exec'd interpreter aborts in
# the loader before job code (supposition S1 in
# docs/steady/security/macos.md).
LIMIT_SHIM_SOURCE = (
    "import os, sys\n"
    "limit = int(sys.argv[1])\n"
    "user = sys.argv[2]\n"
    "argv = sys.argv[3:]\n"
    "import resource\n"
    "for _name in ('RLIMIT_DATA',):\n"
    "    _r = getattr(resource, _name, None)\n"
    "    if _r is not None:\n"
    "        resource.setrlimit(_r, (limit, limit))\n"
    "if user != '-':\n"
    "    import pwd\n"
    "    _pw = pwd.getpwnam(user)\n"
    "    os.setgid(_pw.pw_gid)\n"
    "    try:\n"
    "        os.initgroups(_pw.pw_name, _pw.pw_gid)\n"
    "    except OSError:\n"
    "        os.setgroups([_pw.pw_gid])\n"
    "    os.setuid(_pw.pw_uid)\n"
    "os.execvp(argv[0], argv)\n"
)


def build_shim_argv(argv, memory_bytes=DEFAULT_PROCESS_MEMORY_BYTES,
                    user=None):
    """The launcher shim's argv: [interpreter, -c, source,
    memory, user-or-"-", *argv].

    Each field is validated on its own: the command a
    non-empty list of strings, the ceiling a positive integer
    (a boolean is not a ceiling), the user None or a non-empty
    string carrying nothing a process table cannot name.
    """
    if not isinstance(argv, (list, tuple)) or not argv \
            or not all(isinstance(a, str) and a for a in argv):
        raise RuntimeError(
            "confined spawn needs a non-empty list of strings")
    if isinstance(memory_bytes, bool) \
            or not isinstance(memory_bytes, int) \
            or memory_bytes <= 0:
        raise RuntimeError(
            "the spawn memory ceiling must be a positive integer")
    if user is not None:
        if not isinstance(user, str) or not user \
                or ":" in user \
                or any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in user):
            raise RuntimeError(
                "the job user for the shim must be a plain user name")
    return [sys.executable, "-c", LIMIT_SHIM_SOURCE,
            str(int(memory_bytes)), user if user else "-",
            *argv]


def build_sandbox_argv(argv, cwd=None, env=None,
                       memory_bytes=DEFAULT_PROCESS_MEMORY_BYTES,
                       user=None, read_paths=()):
    """(the full sandbox-exec argv, the profile text) for a job.

    argv is the job's command in host paths; cwd is its work
    directory, the profile's one writable tree. The shape is
    fixed: sandbox-exec, -p, the generated profile, then the
    launcher shim carrying the job's command. `env` is accepted
    for symmetry with the other backends' builders and does
    not enter the argv -- the spawn passes it to the process,
    as the other backends' spawns do.

    The profile names the work directory's real path, not
    the path as handed over: Seatbelt matches the canonical
    path, and a work directory reached through a symlink or
    a firmlink (the /var temp tree is the standing case) is
    a different string from the file's canonical name, so a
    profile built from the handed-over string would refuse
    the staged read it exists to allow. The /var and /tmp
    twins in build_profile cover the firmlink case for a
    profile built directly from a temp path; the realpath
    here covers every other alias a caller hands over.
    """
    if cwd is None:
        cwd = os.getcwd()
    profile = build_profile(os.path.realpath(cwd),
                            interpreter=argv[0] if argv else None,
                            read_paths=read_paths)
    shim = build_shim_argv(argv, memory_bytes=memory_bytes, user=user)
    return [SANDBOX_EXEC_BIN, "-p", profile, *shim], profile


# ----------------------------------------------------------------
# The confinement trial (platform-neutral orchestration)
# ----------------------------------------------------------------

_TRIAL_MARKER = "hp-confinement-trial"

# The trial program is staged inside the work directory, the
# shape of a real job: the confined process reads the staged
# data file it is handed and writes its output beside it.
_TRIAL_PROGRAM = (
    "import os, sys\n"
    "data = open(sys.argv[1], encoding='utf-8').read()\n"
    "assert 'hp-confinement-trial' in data, 'marker missing'\n"
    "print('TRIAL-READ-OK', flush=True)\n"
    "out = os.path.join(sys.argv[2], 'trial-out.txt')\n"
    "with open(out, 'w', encoding='utf-8') as fh:\n"
    "    fh.write(data)\n"
    "print('TRIAL-WRITE-OK', flush=True)\n"
)


def _trial_tail(text):
    """The last non-empty line of a trial process's output."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1][:200] if lines else "no output"


def confinement_trial_problem(spawn, timeout=60):
    """None when a confined process can work here, else why not.

    `spawn` is a confined-spawn callable with the backend's
    signature -- spawn(argv, cwd=..., env=...) returning a
    process object with communicate(timeout), kill(), close()
    and returncode. The trial stages a data file and a program
    inside a fresh work directory under the temp tree, spawns
    the program confined with that directory as its cwd, and
    names the stage that failed: the spawn itself, the staged
    read, or the work-directory write. The temp tree is
    removed either way. A host whose confined processes cannot
    read what is staged for them answers a problem here, at
    startup, instead of failing every job. The orchestration
    is platform-neutral, so the suite exercises it through
    scripted spawn seams on any host; on a real macOS host the
    backend's macos_confinement_problem wires it to
    spawn_confined_process and caches the verdict.
    """
    tmp = None
    try:
        tmp = tempfile.mkdtemp(prefix="hp-confinement-trial-")
        work = os.path.join(tmp, "work")
        os.makedirs(work)
        staged = os.path.join(work, "trial-staged.txt")
        with open(staged, "w", encoding="utf-8") as fh:
            fh.write(_TRIAL_MARKER + "\n")
        program = os.path.join(work, "trial_program.py")
        with open(program, "w", encoding="utf-8") as fh:
            fh.write(_TRIAL_PROGRAM)
        argv = [sys.executable, program, staged, work]
        try:
            proc = spawn(argv, cwd=work, env=dict(os.environ))
        except Exception as e:
            return "confined trial spawn failed: %s" % (e,)
        try:
            try:
                out, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                return ("confined trial timed out after %ss; a "
                        "confined process could not finish "
                        "reading its staged file and writing its "
                        "work directory" % (timeout,))
            out_text = out.decode("utf-8", "replace") \
                if isinstance(out, (bytes, bytearray)) else str(out or "")
            err_text = err.decode("utf-8", "replace") \
                if isinstance(err, (bytes, bytearray)) else str(err or "")
            if "TRIAL-READ-OK" not in out_text:
                return ("a confined process could not read its "
                        "staged file (exit %s: %s)"
                        % (proc.returncode,
                           _trial_tail(err_text or out_text)))
            if "TRIAL-WRITE-OK" not in out_text or not os.path.exists(
                    os.path.join(work, "trial-out.txt")):
                return ("a confined process read its staged file "
                        "but could not write its work directory "
                        "(exit %s: %s)"
                        % (proc.returncode,
                           _trial_tail(err_text or out_text)))
            if proc.returncode not in (0, None):
                return ("the confined trial process exited %s "
                        "after reading and writing (%s)"
                        % (proc.returncode, _trial_tail(err_text)))
            return None
        finally:
            try:
                proc.close()
            except Exception:
                pass
    except Exception as e:
        return "confined trial could not be staged: %s" % (e,)
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------
# The platform branch
# ----------------------------------------------------------------

if sys.platform != "darwin":
    # Stub so the rest of the runner can import without error.
    # The startup probe answers a problem string (never None),
    # so an enforce gate consulting this stub refuses, and the
    # spawn raises: off macOS this backend can never claim to
    # have engaged. IS_MACOS_BACKEND is how the gates tell this
    # stub from the real implementation below: only a real
    # backend's probe is ever consulted, so a simulated darwin
    # answers the refusal deterministically on any host.
    IS_MACOS_BACKEND = False

    def macos_startup_problem(*args, **kwargs):
        return "macos_confine is macOS-only"

    def macos_confinement_problem(*args, **kwargs):
        return "macos_confine is macOS-only"

    def spawn_confined_process(*args, **kwargs):
        raise RuntimeError("macos_confine is macOS-only")
else:
    IS_MACOS_BACKEND = True

    def _basic_problem():
        """Why the backend cannot engage at all here, or None.

        The tool itself, and the interpreter the shim runs on.
        The full trial is macos_confinement_problem's; this is
        the cheap half the spawn also checks, so a spawn on a
        host that lost the tool refuses instead of
        half-engaging.
        """
        if not (os.path.isfile(SANDBOX_EXEC_BIN)
                and os.access(SANDBOX_EXEC_BIN, os.X_OK)):
            return "%s is missing or not executable" % SANDBOX_EXEC_BIN
        return None

    def macos_startup_problem(cfg=None, timeout=15):
        """None if sandbox-exec can start a trivially confined
        process on this host, else why not.

        This is a necessary condition, not a sufficient one: it
        proves the tool is present and a generated profile
        parses and starts. A confined process that starts but
        cannot work is the trial's subject, in
        macos_confinement_problem; a particular job's spawn
        still makes its own profile, and its failure refuses
        that job then.
        """
        problem = _basic_problem()
        if problem is not None:
            return problem
        try:
            proc = subprocess.run(
                [SANDBOX_EXEC_BIN, "-p",
                 "(version 1)\n(allow default)\n", "/usr/bin/true"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as e:
            return "sandbox-exec could not be started: %s" % e
        if proc.returncode != 0:
            detail = (proc.stderr or b"").decode(
                "utf-8", "replace").strip()
            return "sandbox-exec cannot start a confined process " \
                "(exit %d%s)" % (
                    proc.returncode, ": " + detail[:200] if detail else "")
        return None

    _trial_lock = threading.Lock()
    _trial_verdict = []

    def macos_confinement_problem(cfg=None, timeout=15):
        """None when the confinement controls can engage here.

        Stronger than the startup probe: the tool must start a
        confined process, AND a trial process under the full
        controls (the generated profile, the launcher shim, the
        spawn limits) must read its staged file and write its
        work directory, through confinement_trial_problem. The
        verdict is cached for the life of the process -- the
        per-job gate consults this probe, and the trial's cost
        (one confined spawn) is paid once per runner start, not
        once per job.
        """
        problem = macos_startup_problem(cfg, timeout=timeout)
        if problem is not None:
            return problem
        with _trial_lock:
            if not _trial_verdict:
                _trial_verdict.append(
                    confinement_trial_problem(spawn_confined_process))
            return _trial_verdict[0]

    class MacOSConfinedProcess:
        """The Popen subset exec.py drives, for a confined spawn.

        .pid, .returncode, .communicate(timeout), .kill(),
        .poll(). The wrapped process is the sandbox-exec
        process, which IS the confined job process (sandbox-exec
        execs the shim, which execs the job). communicate raises
        subprocess.TimeoutExpired on timeout, exactly as Popen's
        does (the wrapped Popen raises it). .close() is the
        release: the profile rode in as an argument, so there
        is nothing on disk to remove; close only drops the
        wrapper's reference once the process has exited.
        """

        def __init__(self, argv, inner):
            self.args = argv
            self.pid = inner.pid
            self._inner = inner
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
            self._closed = True

    def spawn_confined_process(argv, cwd=None, env=None, user=None,
                               memory_bytes=DEFAULT_PROCESS_MEMORY_BYTES):
        """Create a job process under every confinement control.

        argv is the full command (interpreter, script, args) in
        host paths; cwd is the job's work directory, the
        profile's one writable tree. The per-job temp directory
        is made inside it and TMPDIR pointed at it. sandbox-exec
        applies the generated profile to the launcher shim,
        which sets the spawn resource limits (and drops to
        `user` when the job_user seam hands one over) before it
        execs the job's command, and a MacOSConfinedProcess is
        returned whose .confinement_status is
        STATUS_CONFINEMENT. Raises RuntimeError when any control
        could not be applied -- there is no unconfined fallback
        to fall through to.
        """
        problem = _basic_problem()
        if problem is not None:
            raise RuntimeError(problem)
        if cwd is None:
            cwd = os.getcwd()
        sandbox_argv, _profile = build_sandbox_argv(
            argv, cwd=cwd, memory_bytes=memory_bytes, user=user)
        env2 = dict(env) if env is not None else dict(os.environ)
        try:
            job_tmp = os.path.join(cwd, JOB_TMP_NAME)
            os.makedirs(job_tmp, exist_ok=True)
            env2["TMPDIR"] = job_tmp
        except OSError:
            pass
        inner = subprocess.Popen(
            sandbox_argv, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=cwd, env=env2, start_new_session=True)
        return MacOSConfinedProcess(list(argv), inner)
