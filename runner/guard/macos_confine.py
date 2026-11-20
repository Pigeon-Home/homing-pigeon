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
  /opt, /etc, and the /private startup trees named in
  SYSTEM_READ_PATHS) and the job interpreter's own install
  prefix, allows reading the root directory's own listing
  (file-read-data on the literal "/" -- the names at the top
  of the disk and nothing below them; a process reads that
  listing as it starts and is aborted when it is refused,
  which is the second live verdict's primary supposition,
  R2-S1 in docs/steady/security/macos.md), allows file
  metadata (stat, readlink -- never contents) on any path,
  because a process resolves allowed paths with realpath(),
  which stats every component including ancestors no
  content rule names (the third live verdict's primary
  supposition, R3-S1 in docs/steady/security/macos.md),
  allows reading
  and writing only inside the job's work directory, and
  names no network allow rule at all -- with an
  explicit (deny network*) line beside the deny-by-default
  base, so a confined job has no network, loopback included.
  Of the session's services it names two, the user
  database's (SESSION_SERVICES), and lets a job look up
  those and whatever the operator names under
  security.confinement.macos.mach_services, and no other:
  the pasteboard is refused, so a job reads and writes no
  clipboard, and so are the window server, launch services,
  and the keychain's and the network configuration's
  daemons. No other Mach operation is allowed at all: a job
  registers no service name and is handed no task or host
  port.
  The memory ceiling is applied at spawn by a small launcher
  shim: sandbox-exec first runs the system shell (/bin/sh, in
  its privileged mode, which takes no function and no option
  list from the environment) on the shim text in this module.
  The shim sets the data-size resource limit with the shell's
  own ulimit and then execs the job's command. Darwin holds
  that limit against a process's whole address map, and a
  bare process's map is already large -- about 391.7 GiB on
  the hosted Apple silicon Mac and 32.5 GiB on the hosted
  Intel one, read on both on 2026-11-15
  (docs/steady/design/macos-confinement-design.md) -- so the
  kernel refuses a limit below that size from a started
  process. The shim therefore finds the floor first, the
  smallest value the kernel accepts from it, asking in
  subshells so that a refusal ends the subshell and never
  the shim: the request itself, then doublings up to the
  first value accepted, then halvings of the gap down to
  one mebibyte. The limit it applies is the floor plus the
  requested ceiling -- 512 MiB unless the operator names
  another under
  security.confinement.macos.process_memory_bytes -- so the
  ceiling is the distance a job process's map may grow past
  the size a bare process starts at; on a host with no floor
  above the request the limit is the request itself. An
  inherited hard limit is never raised: a value above it is
  clamped to it, and a host whose floor stands above it
  refuses the job by name. The soft and the hard limit are
  both set, so the ceiling is not the job's to raise --
  unless the job is root, which may raise a hard limit as
  root may anywhere: a runner that is root names a job user.
  Only
  the data-size limit is set, never the virtual-memory
  (address-space) limit: a 512 MiB RLIMIT_AS made every
  exec'd interpreter abort (SIGABRT, exit -6) before its
  first line of job code, which is the shape of the first
  live failure (build run 43089173541, recorded in
  docs/steady/security/macos.md, supposition S1). The job
  user, when the job_user seam hands one over, is applied
  by the spawn itself, between the fork and the exec of
  sandbox-exec, so the whole chain -- sandbox-exec, the
  shim, the job -- runs as that user (the POSIX preexec
  demote cannot ride a spawn that replaces process
  creation, so the demote happens at the spawn door -- the
  FreeBSD backend's jexec -u shape). Nothing in the chain is
  the runner's own interpreter, so a runner frozen into one
  file, which is what a release's macOS archives carry,
  engages exactly as a runner started from source does. The
  profile is in force before the shim's first line runs
  (sandbox-exec applies it to the process it starts), so
  there is no race in which the job runs unconfined; the
  process object owns nothing to tear down beyond the
  wrapped process itself, because the profile is passed to
  sandbox-exec as an argument, never written to a file.

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
  at spawn (ulimit in the launcher shim), not a Seatbelt
  rule. Seatbelt has no resource-limit operation, which is
  why the shim exists; the audit record names
  spawn_resource_limits and never a Seatbelt memory control.
  It is a ceiling on the size of a process's address map,
  not on the memory it touches, and it is each process's
  own: there is no ceiling on a job's processes taken
  together.
- It does not hide the host's processes from a job, or the
  machine's hardware properties, its serial number among
  them: the profile's default denial does not reach either
  (read on both hosted Macs).
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
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import threading

# The one ceiling this backend sets: 512 MiB per job process,
# applied as the data-size resource limit at spawn (never the
# virtual-memory limit -- see the module docstring for the
# startup abort a virtual-memory ceiling causes on macOS).
# The default, mirroring the Windows and FreeBSD backends'
# ceiling; security.confinement.macos.process_memory_bytes
# names another.
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
# base tools, the dynamic loader's world. The /private entries
# are the startup trees a process reads as it starts: the
# loader's own database (/private/var/db/dyld), the timezone
# tree /etc/localtime points into (/private/var/db/timezone),
# and the tool-selection links /bin/sh reads at every start
# (/private/var/select) -- beside /private/etc, the canonical
# twin of /etc. Working deny-by-default allowlists name all
# of them; the second live verdict's suppositions (R2-S2 in
# docs/steady/security/macos.md) record why they stand here.
# Nothing else of the host filesystem is readable under the
# profile.
SYSTEM_READ_PATHS = ("/System", "/usr", "/Library", "/bin",
                     "/sbin", "/opt", "/etc", "/private/etc",
                     "/private/var/db/dyld",
                     "/private/var/db/timezone",
                     "/private/var/select")

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


def _realpath_or_self(path):
    """os.path.realpath, answering the path itself when the
    resolution cannot be taken (a scripted host, an error)."""
    try:
        real = os.path.realpath(path)
    except (OSError, ValueError):
        return path
    return real if isinstance(real, str) and real else path


def _is_user_home_dir(path):
    """True when the directory `path` names is a user home,
    under any spelling of it (Q192) -- the mirror of the
    Linux sandbox's directory test: the spelled test on the
    path and on its realpath, a home-shaped tail
    (</...>/home/<name> or </...>/Users/<name>, the firmlink
    shape), and directory identity with the process user's
    own home."""
    if not isinstance(path, str) or not path:
        return False
    if _is_user_home(path):
        return True
    real = _realpath_or_self(path)
    # A resolution is trusted for identity only when it keeps
    # the directory's own name: an alias renames a parent
    # component (a firmlink, a linked /home), never the leaf.
    # A resolution that renames the leaf is a scripted host
    # answering for another path entirely, and judges nothing.
    real_ok = (real == path
               or os.path.basename(real) == os.path.basename(path))
    if real_ok and real != path and _is_user_home(real):
        return True
    for cand in ((path, real) if real_ok else (path,)):
        parts = cand.split("/")
        if (len(parts) >= 4 and parts[-2] in ("home", "Users")
                and bool(parts[-1])):
            return True
    own = os.path.expanduser("~")
    if (own.startswith("/") and real_ok and real == path
            and real == _realpath_or_self(own)):
        return True
    return False


def _install_prefix(path):
    """The directory a profile must let a job read so `path`
    can run: its grandparent when the parent is `bin`
    (…/x64/bin/python3 -> …/x64, bringing lib/ along), else its
    parent. Never shallower than two components, and never a
    user home directory: a bin grandparent that is a home
    directory falls back to the bin directory itself, so the
    whole home is never named. The mirror of the Linux
    sandbox's interpreter-prefix rule. A path carrying a NUL
    is no path at all and gets no prefix (Q190 family).
    """
    if not isinstance(path, str) or "\x00" in path:
        return None
    parent = os.path.dirname(path)
    if os.path.basename(parent) == "bin":
        grand = os.path.dirname(parent)
        if grand.count("/") >= 2 and grand != "/" \
                and not _is_user_home_dir(grand):
            return grand
    if parent.count("/") >= 2:
        if _is_user_home_dir(parent):
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
    if "\x00" in interpreter:
        # A path no filesystem can hold cannot be resolved,
        # and realpath would raise ValueError on it: refuse
        # in this function's own RuntimeError shape (Q190).
        raise RuntimeError(
            "cannot resolve interpreter %r for the profile"
            % interpreter)
    if "/" in interpreter:
        resolved = interpreter
    else:
        resolved = shutil.which(interpreter)
        if resolved is None:
            raise RuntimeError(
                "cannot resolve interpreter %r for the profile"
                % interpreter)
    candidates = [resolved, _realpath_or_self(resolved)]
    # The homes either candidate names, by directory (Q192),
    # as in sandbox.interpreter_binds.
    home_dirs = set()
    for cand in candidates:
        if not cand.startswith("/"):
            continue
        parent = os.path.dirname(cand)
        for anc in (parent, os.path.dirname(parent)):
            if _is_user_home_dir(anc):
                home_dirs.add(anc)
                anc_real = _realpath_or_self(anc)
                if os.path.basename(anc_real) == os.path.basename(anc):
                    home_dirs.add(anc_real)
    out = []
    seen = set()
    seen_dirs = set()
    for cand in candidates:
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
        prefix_dir = _realpath_or_self(prefix)
        if os.path.basename(prefix_dir) != os.path.basename(prefix):
            prefix_dir = prefix
        if _is_user_home_dir(prefix) or prefix_dir in home_dirs:
            continue
        if prefix_dir in seen_dirs:
            continue
        seen.add(prefix)
        seen_dirs.add(prefix_dir)
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


# The services of the session a job may look up, by the names
# launchd knows them by: the user database, which is how a
# process learns who a user is and which groups it is in
# (id, ls -l, and getpwuid in every language runtime). Read
# on the two hosted Macs on 2026-11-15 (the macos-confinement
# run 43761537586): with no service named, the programs a job
# is likely to be all ran, and the ones that ask who a user
# is got a number for a name or stopped; with the user
# database named, every one behaved as it does with every
# service open. The database also answers to an older third
# name, which no program asked for: two are named. Every
# other service is refused: the pasteboard, the window
# server, launch services, the keychain's and the network
# configuration's daemons among them.
SESSION_SERVICES = (
    "com.apple.system.opendirectoryd.libinfo",
    "com.apple.system.opendirectoryd.membership",
)
# The pasteboard's name. The probe's trial must be refused
# the clipboard, unless the operator has named this service.
PASTEBOARD_SERVICE = "com.apple.pasteboard.1"
PASTEBOARD_READER = "/usr/bin/pbpaste"
# How many services an operator may name.
MAX_MACH_SERVICES = 64
# A service name as launchd takes one: letters, digits, dots,
# underscores, hyphens and the at sign, starting with a
# letter or a digit. Nothing a profile's syntax could read
# as its own.
_SERVICE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@-]{0,254}\Z")


def validate_service_name(name):
    """Raise RuntimeError unless `name` is a plain service name."""
    if not isinstance(name, str) or not _SERVICE_NAME.match(name):
        raise RuntimeError(
            "a service name must be 1 to 255 letters, digits, "
            "dots, underscores, hyphens or at signs, starting "
            "with a letter or a digit (got %r)" % (name,))
    return name


def session_services(extra=()):
    """The services a profile lets a job look up: the
    backend's own, then the operator's, each once and each
    validated. Raises RuntimeError on a name that is not one,
    and on more than MAX_MACH_SERVICES of the operator's."""
    if isinstance(extra, (str, bytes)) \
            or not isinstance(extra, (list, tuple)):
        raise RuntimeError("the operator's services must be a list "
                           "of service names")
    if len(extra) > MAX_MACH_SERVICES:
        raise RuntimeError(
            "at most %d services may be named (got %d)"
            % (MAX_MACH_SERVICES, len(extra)))
    names = list(SESSION_SERVICES)
    for name in extra:
        validate_service_name(name)
        if name not in names:
            names.append(name)
    return tuple(names)


def build_profile(workdir, interpreter=None, read_paths=(),
                  mach_services=()):
    """The Seatbelt profile text for one job, deterministically.

    Fields, one by one:
    - workdir: the job's work directory -- the only tree the
      profile lets the job write, and the staged script's home.
    - interpreter: the job's interpreter (a bare name or a
      path); its install prefix joins the readable trees.
    - read_paths: extra trees the job may read (operator-named
      input trees), each validated the same way.
    - mach_services: services of the session a job may look
      up beyond the backend's own (operator-named), each a
      plain service name.

    The shape never varies: deny-by-default; the process,
    sysctl and IPC operations a job interpreter needs to
    start and run; a lookup of the session's services the
    profile names (SESSION_SERVICES, then the operator's) and
    of no other -- and no other Mach operation at all: no
    name registered, no task or host port asked for; reads
    (with execution mapping) for the system trees,
    the interpreter prefix and the extra read paths; the root
    directory's own listing (file-read-data on the literal
    "/", never a subpath grant -- a process reads that
    listing as it starts and is aborted when it is refused;
    supposition R2-S1 in docs/steady/security/macos.md);
    read + write inside the work directory; file metadata
    (file-read-metadata: existence, type, size, times and
    symlink targets, never contents) on any path -- a
    process resolves the paths it is allowed with
    realpath(), which stats every component in turn,
    including ancestors no content rule names (the root
    itself, a work directory's /private ancestors, an
    interpreter prefix's parents), and the framework
    interpreter on the CI host died at exactly that stat
    with its contents rules fully granted (supposition
    R3-S1 in docs/steady/security/macos.md); the /dev nodes a
    job's standard streams and entropy need; and the network
    denial stated. Paths under /var and /tmp are named with
    their /private canonical twins (see _with_canonical_twins),
    on the read line and the write line alike. No field can add
    a network allow rule, a write outside the work directory,
    or a read of a user home: the writer has no parameter
    that expresses them.
    """
    _validate_profile_path(workdir, "workdir")
    lookups = " ".join("(global-name %s)" % _sb_quote(name)
                       for name in session_services(mach_services))
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
        "(allow mach-lookup %s)" % lookups,
        "(allow ipc*)",
        "(allow signal (target self))",
        "(allow pseudo-tty)",
        "(allow file-read* file-map-executable %s)" % read_args,
        '(allow file-read-data (literal "/"))',
        "(allow file-read-metadata)",
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

# The shim's text. sandbox-exec starts the system shell on it
# (through -c, so no shim file exists to stage); it sets the
# data-size limit, soft and hard, and execs the job's command
# (arguments 2 onward; argument 1 is the requested ceiling in
# kibibytes, the unit ulimit -d speaks). A limit it cannot
# set ends the shim before the exec -- the job is refused,
# never run weaker. The one limit it sets is the data-size
# limit: an address-space limit at this ceiling is below the
# address space every macOS process maps at startup, and the
# exec'd interpreter aborts in the loader before job code
# (supposition S1 in docs/steady/security/macos.md).
#
# The value it asks for is computed against what the kernel
# accepts, by the rule data_limit_plan states: Darwin holds
# this limit against the process's whole address map and
# refuses a value below the map's current size (the
# current-usage floor, supposition R4-S1), so the shim finds
# the floor -- the request first, then doublings up to the
# first value accepted, then halvings of the gap down to
# DATA_FLOOR_STEP_KIB -- and applies the floor plus the
# request. Every try is made in a subshell: a refusal ends
# the subshell, and the shim keeps the limits it had. The
# cap on what it asks for is the inherited hard limit when
# that is finite, which is never raised (supposition R4-S2),
# and DATA_LIMIT_CAP_KIB when it is not. The soft limit is
# set first and the hard limit lowered onto it, so the job
# cannot raise either.
#
# The text is plain POSIX shell with nothing a shell could
# split or glob: every expansion is quoted or arithmetic.
# It names no command but the shell's own builtins, so
# nothing on the job's PATH runs before the job does.
SHELL_BIN = "/bin/sh"
# The shell's privileged mode. /bin/sh on macOS is bash
# unless the machine's owner selects dash or zsh; bash takes
# shell functions and an option list (SHELLOPTS) from its
# environment, and a job's environment is the submitter's,
# so without this flag a variable there could stand a
# function of its own under the name `ulimit`. In privileged
# mode bash takes neither; dash and zsh take neither in any
# mode, and accept the flag.
SHELL_PRIVILEGED = "-p"
# The name the shim's process carries as $0, and the mark its
# refusals begin with.
SHIM_NAME = "hp-shim"
KIB = 1024
# The largest value asked for when the inherited hard limit
# is unlimited: 2**62 bytes, the largest power of two below
# the platform's unlimited sentinel (2**63 - 1 on Darwin).
DATA_LIMIT_CAP_KIB = 2 ** 52
# How closely the floor is found: one mebibyte.
DATA_FLOOR_STEP_KIB = 1024

LIMIT_SHIM_TEXT = (
    'want=$1\n'
    'shift\n'
    'cap=%(cap)d\n'
    'hard=$(ulimit -H -d) || hard=\n'
    'case $hard in\n'
    '  unlimited) ;;\n'
    "  ''|*[!0-9]*)\n"
    '    echo "hp-shim: could not set the data-size limit: '
    'the hard limit could not be read" >&2\n'
    '    exit 1 ;;\n'
    '  *) cap=$hard ;;\n'
    'esac\n'
    'lim=$want\n'
    'if [ "$lim" -gt "$cap" ]; then lim=$cap; fi\n'
    'if ! (ulimit -S -d "$lim") 2>/dev/null; then\n'
    '  lo=$lim\n'
    '  while :; do\n'
    '    if [ "$lo" -ge "$cap" ]; then\n'
    '      echo "hp-shim: could not set the data-size limit: '
    'the kernel accepts no value up to $cap KiB" >&2\n'
    '      exit 1\n'
    '    fi\n'
    '    hi=$((lo * 2))\n'
    '    if [ "$hi" -gt "$cap" ]; then hi=$cap; fi\n'
    '    if (ulimit -S -d "$hi") 2>/dev/null; then break; fi\n'
    '    lo=$hi\n'
    '  done\n'
    '  while [ $((hi - lo)) -gt %(step)d ]; do\n'
    '    mid=$((lo + (hi - lo) / 2))\n'
    '    if (ulimit -S -d "$mid") 2>/dev/null; then hi=$mid; '
    'else lo=$mid; fi\n'
    '  done\n'
    '  lim=$((hi + want))\n'
    '  if [ "$lim" -gt "$cap" ]; then lim=$cap; fi\n'
    'fi\n'
    'if ! ulimit -S -d "$lim" || ! ulimit -H -d "$lim"; then\n'
    '  echo "hp-shim: could not set the data-size limit: '
    '$lim KiB was refused" >&2\n'
    '  exit 1\n'
    'fi\n'
    'exec "$@"\n'
) % {"cap": DATA_LIMIT_CAP_KIB, "step": DATA_FLOOR_STEP_KIB}


# The reports of an unlimited limit. Python's resource
# module does not mask platform differences: it reports
# a limit exactly as the platform's getrlimit reports
# it, so the one fact "unlimited" reaches Python under
# two values, one per platform family this backend
# ships for -- -1 on Linux, where the platform's
# unlimited sentinel reaches Python as -1, and
# 2 ** 63 - 1 (INT64_MAX) on Darwin, whose unlimited
# sentinel is that value (the shim's cap stands just
# below the same sentinel).
# A read-back assertion that names only one report
# fails on the other platform while the fact it pins
# stands: the spawn-limits live point hardcoded -1
# and failed on darwin with the sentinel in hand
# (supposition R6-S1 in docs/steady/security/macos.md).
UNLIMITED_LIMIT_REPORTS = (-1, 2 ** 63 - 1)


def reported_limit_is_unlimited(value):
    """Whether a reported limit value means unlimited.

    The deterministic substrate of the read-back
    classification: a limit value as Python's
    `resource` module reports it (from `getrlimit`,
    in this process or read back from a spawned job)
    means unlimited exactly when it is one of the
    named reports in UNLIMITED_LIMIT_REPORTS, and
    means a finite limit otherwise. The field, one
    by one:

    - value: the reported limit (an integer; a
      boolean is not a limit, and no report stands
      below -1).

    The classifier only classifies: it sets nothing,
    normalizes nothing, and no spawn path consults
    it, so confinement's fail-closed shape cannot
    move through it. Raises RuntimeError on a field
    that is not what it is named.
    """
    if isinstance(value, bool) \
            or not isinstance(value, int) or value < -1:
        raise RuntimeError(
            "a reported limit must be -1 or a "
            "non-negative integer")
    return value in UNLIMITED_LIMIT_REPORTS


def data_limit_plan(requested_kib, accepts, inherited_hard_kib=None):
    """(limit, floor) in KiB: the data-size limit the shim
    applies, and the floor it found under it.

    The deterministic substrate of the shim's computation (the
    shim text carries the same rule inline, because it runs as
    shell text with no module to import). Fields, one by one:

    - requested_kib: the ceiling the backend means to apply,
      in kibibytes (a positive integer; a boolean is not a
      ceiling).
    - accepts: the kernel's answer -- accepts(value) is True
      when a started process may set `value` KiB as its soft
      data-size limit. The shim asks in a subshell; a test
      scripts the answer.
    - inherited_hard_kib: the hard data-size limit the shim's
      process inherits, in kibibytes, or None when it is
      unlimited.

    The rule, stated whole. The cap is the inherited hard
    limit when it is finite -- no value above it is ever
    asked for, so the hard limit is never raised -- and
    DATA_LIMIT_CAP_KIB when it is not. The first value asked
    is the request, clamped to the cap; where the kernel
    accepts it, that is the limit and there is no floor
    (None). Where it does not, the value asked is doubled,
    clamped to the cap, until one is accepted; the gap
    between the last value refused and the first accepted is
    then halved until it is DATA_FLOOR_STEP_KIB or less, and
    its upper end is the floor: the smallest value the
    kernel accepts, to within that step. The limit is the
    floor plus the request, clamped to the cap. Raises
    RuntimeError when the kernel accepts no value up to the
    cap, and on a field that is not what it is named.
    """
    if isinstance(requested_kib, bool) \
            or not isinstance(requested_kib, int) or requested_kib <= 0:
        raise RuntimeError(
            "the requested data-size ceiling must be a "
            "positive integer")
    if inherited_hard_kib is not None and (
            isinstance(inherited_hard_kib, bool)
            or not isinstance(inherited_hard_kib, int)
            or inherited_hard_kib < 0):
        raise RuntimeError(
            "the inherited hard data limit must be None "
            "(unlimited) or a non-negative integer")
    cap = DATA_LIMIT_CAP_KIB if inherited_hard_kib is None \
        else inherited_hard_kib
    limit = min(requested_kib, cap)
    if accepts(limit):
        return limit, None
    low = limit
    while True:
        if low >= cap:
            raise RuntimeError(
                "the kernel accepts no data-size limit up to "
                "%d KiB" % cap)
        high = min(low * 2, cap)
        if accepts(high):
            break
        low = high
    while high - low > DATA_FLOOR_STEP_KIB:
        middle = low + (high - low) // 2
        if accepts(middle):
            high = middle
        else:
            low = middle
    return min(high + requested_kib, cap), high


def ceiling_kib(memory_bytes):
    """A ceiling in bytes as the kibibytes the shim is handed:
    rounded up, so the limit asked for is never below the
    ceiling named. Raises RuntimeError on a value that is not
    a ceiling (a boolean is not one)."""
    if isinstance(memory_bytes, bool) \
            or not isinstance(memory_bytes, int) \
            or memory_bytes <= 0:
        raise RuntimeError(
            "the spawn memory ceiling must be a positive integer")
    return (memory_bytes + KIB - 1) // KIB


def build_shim_argv(argv, memory_bytes=DEFAULT_PROCESS_MEMORY_BYTES):
    """The launcher shim's argv: [shell, -p, -c, text, name,
    ceiling in KiB, *argv].

    Each field is validated on its own: the command a
    non-empty list of strings, the ceiling a positive integer
    (a boolean is not a ceiling). The shell is the system's
    own and the text is this module's; neither is a field.
    """
    if not isinstance(argv, (list, tuple)) or not argv \
            or not all(isinstance(a, str) and a for a in argv):
        raise RuntimeError(
            "confined spawn needs a non-empty list of strings")
    return [SHELL_BIN, SHELL_PRIVILEGED, "-c", LIMIT_SHIM_TEXT,
            SHIM_NAME, str(ceiling_kib(memory_bytes)), *argv]


def job_user_drop(user, lookup=None, groups=None):
    """The spawn's own arguments that apply the job user, or
    none of them when no user is handed over.

    Returns the keyword arguments subprocess.Popen takes to
    change the child's user between its fork and its exec:
    `user` (the uid), `group` (the user's own group) and
    `extra_groups` (the groups the user database gives it, 16
    at most, which is what the platform's setgroups takes).
    The user is a plain name carrying nothing a process table
    cannot name; one that is not in the user database is a
    refusal, never a spawn as the runner's own user. `lookup`
    and `groups` are the tests' doors to the user database.
    """
    if user is None:
        return {}
    if not isinstance(user, str) or not user \
            or ":" in user \
            or any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in user):
        raise RuntimeError(
            "the job user for the spawn must be a plain user name")
    if lookup is None:
        import pwd
        lookup = pwd.getpwnam
    try:
        entry = lookup(user)
    except KeyError:
        raise RuntimeError(
            "the job user %s is not in this machine's user "
            "database" % user)
    if groups is None:
        groups = getattr(os, "getgrouplist", None)
    extra = _group_ids(groups, entry.pw_name, entry.pw_gid)
    if entry.pw_gid not in extra:
        extra.insert(0, entry.pw_gid)
    return {"user": entry.pw_uid, "group": entry.pw_gid,
            "extra_groups": extra[:16]}


def _group_ids(groups, name, gid):
    """The group ids the user database gives `name`, as the
    unsigned numbers a spawn takes; the user's own group alone
    when the list cannot be read.

    Darwin's getgrouplist speaks signed 32-bit ids where the
    rest of the platform speaks unsigned ones: the group of
    `nobody` is 4294967294 in the user database and -2 to that
    call, in both directions. An id too large for the call is
    handed over as its signed twin, and a negative id that
    comes back is read as its unsigned one. One id no spawn
    takes is left out: -1, which the platform reads as "no
    group" (the hosted Macs' list for `nobody` carries it).
    """
    if groups is None:
        return [gid]
    try:
        try:
            found = groups(name, gid)
        except OverflowError:
            found = groups(name, gid - 2 ** 32)
        found = [g + 2 ** 32 if g < 0 else g for g in found]
        return [g for g in found if 0 <= g < 2 ** 32 - 1]
    except (OSError, OverflowError, ValueError, TypeError):
        return [gid]


def _profile_realpath(path):
    """The canonical form of `path` for the profile.

    os.path.realpath on the host, which resolves every symlink
    and firmlink to the name Seatbelt matches. A host whose
    realpath rewrites a POSIX absolute path into another form
    (Windows turns "/work/job1" into "D:\\work\\job1") keeps
    the POSIX form, normalized, because the profile writer
    takes only leading-slash paths; no profile is enforced on
    such a host, and the field tests that build one there pass
    POSIX paths by design. A path carrying a NUL is refused
    outright: realpath would raise ValueError on it, where
    the profile writer's own shape is a RuntimeError refusal
    (Q190 family).
    """
    if isinstance(path, str) and "\x00" in path:
        raise RuntimeError(
            "a profile path must not contain a NUL: %r" % (path,))
    real = os.path.realpath(path)
    if isinstance(path, str) and path.startswith("/") \
            and not real.startswith("/"):
        return posixpath.normpath(path)
    return real


def build_sandbox_argv(argv, cwd=None, env=None,
                       memory_bytes=DEFAULT_PROCESS_MEMORY_BYTES,
                       read_paths=(), mach_services=()):
    """(the full sandbox-exec argv, the profile text) for a job.

    argv is the job's command in host paths; cwd is its work
    directory, the profile's one writable tree. The shape is
    fixed: sandbox-exec, -p, the generated profile, then the
    launcher shim carrying the job's command. `env` is accepted
    for symmetry with the other backends' builders and does
    not enter the argv -- the spawn passes it to the process,
    as the other backends' spawns do. The job user is not a
    field here either: the spawn applies it to the whole
    chain (job_user_drop).

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
    profile = build_profile(_profile_realpath(cwd),
                            interpreter=argv[0] if argv else None,
                            read_paths=read_paths,
                            mach_services=mach_services)
    shim = build_shim_argv(argv, memory_bytes=memory_bytes)
    return [SANDBOX_EXEC_BIN, "-p", profile, *shim], profile


# ----------------------------------------------------------------
# The settings (platform-neutral, pure)
# ----------------------------------------------------------------

# The backend's own settings, under security.confinement.macos.
MACOS_KEYS = ("process_memory_bytes", "mach_services")


def validate_macos_block(block):
    """Raise RuntimeError on a malformed security.confinement.
    macos block. A setting this backend does not know is an
    error: a ceiling the operator misspelled is a ceiling that
    is not there."""
    if not isinstance(block, dict):
        raise RuntimeError(
            "config error: security.confinement.macos must be "
            "an object")
    for key in block:
        if key not in MACOS_KEYS:
            raise RuntimeError(
                "config error: security.confinement.macos.%s is "
                "not a known setting (known: %s)"
                % (key, ", ".join(MACOS_KEYS)))
    if "process_memory_bytes" in block:
        value = block["process_memory_bytes"]
        if isinstance(value, bool) or not isinstance(value, int) \
                or value < 1:
            raise RuntimeError(
                "config error: security.confinement.macos."
                "process_memory_bytes must be a positive integer "
                "(got %r)" % (value,))
    if "mach_services" in block:
        try:
            session_services(block["mach_services"])
        except RuntimeError as e:
            raise RuntimeError(
                "config error: security.confinement.macos."
                "mach_services: %s" % e)
    return True


def confinement_settings(cfg):
    """The settings a job's launch is built from, read out of
    the config: the macos block of security.confinement, under
    this module's rules. Raises RuntimeError on a malformed
    block. The keys the Linux sandbox and the FreeBSD jail
    share (work_mount, extra_ro_binds, extra_flags) name
    mounts and bwrap arguments; there is no mount here, and
    this backend reads none of them."""
    sec = cfg.get("security") if isinstance(cfg, dict) else None
    conf = sec.get("confinement") if isinstance(sec, dict) else None
    conf = conf if isinstance(conf, dict) else {}
    block = conf.get("macos", {})
    validate_macos_block(block)
    extra = session_services(block.get("mach_services", ()))
    return {
        "process_memory_bytes": block.get(
            "process_memory_bytes", DEFAULT_PROCESS_MEMORY_BYTES),
        # The operator's own, in the order named, each once.
        "mach_services": extra[len(SESSION_SERVICES):],
    }


def _engaged_job_user(cfg):
    """The user a job is started as under this config, or
    None: security.job_user's user, when the job_user mode
    stands at enforce (its unset reading). The report's own
    reading of the shape -- it never raises."""
    sec = cfg.get("security") if isinstance(cfg, dict) else None
    if not isinstance(sec, dict):
        return None
    modes = sec.get("modes", {})
    if not isinstance(modes, dict) \
            or modes.get("job_user", "enforce") != "enforce":
        return None
    block = sec.get("job_user")
    user = block.get("user") if isinstance(block, dict) else None
    return user if isinstance(user, str) and user else None


def human_size(kib):
    """A size in kibibytes as a person reads it: whole
    mebibytes below a gibibyte, tenths of a gibibyte above."""
    if kib >= 1024 * 1024:
        return "%.1f GiB" % (kib / (1024.0 * 1024.0))
    return "%d MiB" % (kib // 1024)


def memory_line(memory_bytes, limit_kib=None, job_is_root=False):
    """The one sentence that says what the memory ceiling is
    on this host: the ceiling asked for, and, where the trial
    read the limit a job carries, the floor it stands on. A
    job that is root may raise a hard limit, as root may
    anywhere; the sentence says so where that is the job."""
    want = ceiling_kib(memory_bytes)
    held = ("the ceiling is not the job's to raise (ulimit in "
            "the launcher shim, soft and hard)")
    if job_is_root:
        held = ("it is set soft and hard (ulimit in the launcher "
                "shim), and a job that is root can raise it")
    if limit_kib is None:
        return ("a job process's address map may grow %s past "
                "the size a bare process starts at; %s"
                % (human_size(want), held))
    if limit_kib > want:
        return ("a job process's address map may grow %s past "
                "the %s a bare process starts at here; %s"
                % (human_size(want), human_size(limit_kib - want),
                   held))
    return ("a job process's address map is held to %s here; %s"
            % (human_size(want), held))


def services_line(mach_services=()):
    """The one sentence that says which of the session's
    services a job may look up, and where that leaves the
    clipboard: refused with the backend's own list; with an
    operator's, a matter of whether the pasteboard is on it
    -- the one service the probe's trial asks by name. A
    pasteboard that is named answers a job; what it hands
    one is its own matter (on the hosted Macs, nothing)."""
    extra = session_services(mach_services)[len(SESSION_SERVICES):]
    if not extra:
        return ("a job may ask the user database who a user is, "
                "and no other of the session's services: the "
                "clipboard is refused")
    return ("a job may ask the user database who a user is, and "
            "the services this config names: %s (security."
            "confinement.macos.mach_services); the pasteboard is "
            "%s" % (", ".join(extra),
                    "among them and answers a job"
                    if PASTEBOARD_SERVICE in extra
                    else "not among them"))


def _runner_is_root():
    geteuid = getattr(os, "geteuid", None)
    return geteuid is not None and geteuid() == 0


def posture_lines(cfg=None, probe=None, facts=None, root=None):
    """(level, text) lines for the posture report: what a job
    carries on this host under this config.

    Unlike the FreeBSD backend's report, this one asks the
    probe itself: the trial needs no privilege, builds
    nothing on the host but a temporary directory it removes,
    and its verdict is kept for the life of the process, so
    the report says what the startup gate would say. A WARN
    that the backend cannot engage is something the gate
    refuses on at enforce. One WARN is advice and refuses
    nothing: a runner that is root and names no job user
    starts its jobs as root, and root may raise the ceiling.
    `probe`, `facts` and `root` are the tests' doors: the
    probe to ask, what its trial read (the limit a job
    carries, in kibibytes), and whether the runner is root.
    """
    refuse = "; confinement in enforce mode would refuse to start"
    try:
        st = confinement_settings(cfg)
    except RuntimeError as e:
        return [("WARN", "macOS backend cannot engage: %s%s"
                 % (e, refuse))]
    ask = macos_confinement_problem if probe is None else probe
    try:
        problem = ask(cfg)
    except Exception as e:
        problem = str(e) or type(e).__name__
    if problem is not None:
        return [("WARN", "macOS backend cannot engage: %s%s"
                 % (problem, refuse))]
    if facts is None:
        facts = trial_facts(st["process_memory_bytes"],
                            st["mach_services"])
    if root is None:
        root = _runner_is_root()
    user = _engaged_job_user(cfg)
    job_is_root = bool(root) and user is None
    lines = [("OK", "macOS backend: %s" % STATUS_CONFINEMENT)]
    lines.append(("OK", memory_line(st["process_memory_bytes"],
                                    facts.get("limit_kib"),
                                    job_is_root)))
    lines.append(("OK", services_line(st["mach_services"])))
    if user is not None:
        lines.append((
            "OK", "a job is started as %s at the spawn door "
            "(security.job_user) and reads what that user can "
            "read" % user))
    elif job_is_root:
        lines.append((
            "WARN", "this runner is root and names no job user: "
            "a job is root under the profile, and root can raise "
            "its own ceiling (name a user under security.job_user)"))
    return lines


# ----------------------------------------------------------------
# The confinement trial (platform-neutral orchestration)
# ----------------------------------------------------------------

_TRIAL_MARKER = "hp-confinement-trial"
_TRIAL_OUTSIDE = "hp-confinement-outside"

# The trial program is staged inside the work directory, the
# shape of a real job, and run by the system shell: the
# confined process reads the staged data file it is handed
# and writes its output beside it, then tries the two things
# the profile is there to refuse -- a write and a read
# outside the work directory -- says what data-size limit it
# carries, and asks the pasteboard for the clipboard, which
# it reads nothing of and whose answer is the fact: the
# system's own reader succeeds only where the service can be
# looked up. Shell text, so the trial is the same whether the
# runner is a source tree's or a frozen binary.
_TRIAL_PROGRAM = (
    'data=$(/bin/cat "$1") || exit 1\n'
    'case $data in\n'
    '  *hp-confinement-trial*) ;;\n'
    '  *) echo "marker missing" >&2; exit 1 ;;\n'
    'esac\n'
    'echo TRIAL-READ-OK\n'
    'printf "%s\\n" "$data" > "$2/trial-out.txt" || exit 1\n'
    'echo TRIAL-WRITE-OK\n'
    '(: > "$3") 2>/dev/null && echo TRIAL-WROTE-OUTSIDE\n'
    'seen=$(/bin/cat "$4" 2>/dev/null)\n'
    'case $seen in\n'
    '  *hp-confinement-outside*) echo TRIAL-READ-OUTSIDE ;;\n'
    'esac\n'
    'echo "TRIAL-LIMIT $(ulimit -S -d) $(ulimit -H -d)"\n'
    'if [ -x ' + PASTEBOARD_READER + ' ] && ' + PASTEBOARD_READER
    + ' > /dev/null 2>&1; then\n'
    '  echo TRIAL-CLIPBOARD-OPEN\n'
    'fi\n'
)


def _trial_tail(text):
    """The last non-empty line of a trial process's output."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1][:200] if lines else "no output"


def _trial_limit(text):
    """(soft, hard) as the trial printed them, or None."""
    for line in text.splitlines():
        words = line.split()
        if len(words) == 3 and words[0] == "TRIAL-LIMIT":
            return words[1], words[2]
    return None


def confinement_trial_problem(spawn, timeout=60, facts=None,
                              clipboard_closed=True):
    """None when a confined process can work here, else why not.

    `spawn` is a confined-spawn callable with the backend's
    signature -- spawn(argv, cwd=..., env=...) returning a
    process object with communicate(timeout), kill(), close()
    and returncode. The trial stages a data file and a program
    inside a fresh work directory under the temp tree, and a
    second file beside that directory, outside it. It spawns
    the program confined with the work directory as its cwd,
    and names the stage that failed: the spawn itself, the
    staged read, the work-directory write, a write or a read
    outside the work directory that the profile let through,
    a job that carries no data-size ceiling of its own, or a
    job the pasteboard answered -- unless `clipboard_closed`
    is False, which is a config that names the pasteboard
    among its services.
    The temp tree is removed either way. A host whose confined
    processes cannot read what is staged for them, or are not
    confined, answers a problem here, at startup, instead of
    failing every job or running one unconfined. The
    orchestration is platform-neutral, so the suite exercises
    it through scripted spawn seams on any host; on a real
    macOS host the backend's macos_confinement_problem wires
    it to spawn_confined_process and caches the verdict.
    `facts`, when a dict is handed in, receives what a passing
    trial read: `limit_kib`, the data-size limit the confined
    process carried, and `clipboard_open`, whether the
    pasteboard answered it.
    """
    tmp = None
    try:
        tmp = tempfile.mkdtemp(prefix="hp-confinement-trial-")
        work = os.path.join(tmp, "work")
        os.makedirs(work)
        staged = os.path.join(work, "trial-staged.txt")
        with open(staged, "w", encoding="utf-8") as fh:
            fh.write(_TRIAL_MARKER + "\n")
        program = os.path.join(work, "trial_program.sh")
        with open(program, "w", encoding="utf-8") as fh:
            fh.write(_TRIAL_PROGRAM)
        outside_new = os.path.join(tmp, "outside-write.txt")
        outside_kept = os.path.join(tmp, "outside-kept.txt")
        with open(outside_kept, "w", encoding="utf-8") as fh:
            fh.write(_TRIAL_OUTSIDE + "\n")
        argv = [SHELL_BIN, program, staged, work,
                outside_new, outside_kept]
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
            if "TRIAL-WROTE-OUTSIDE" in out_text \
                    or os.path.exists(outside_new):
                return ("a confined process wrote a file outside "
                        "its work directory: the profile did not "
                        "hold")
            if "TRIAL-READ-OUTSIDE" in out_text:
                return ("a confined process read a file outside "
                        "its work directory: the profile did not "
                        "hold")
            limit = _trial_limit(out_text)
            if limit is None or not limit[0].isdigit() \
                    or limit[0] != limit[1]:
                return ("a confined process carried no data-size "
                        "ceiling of its own (soft %s, hard %s): "
                        "the launcher shim did not hold"
                        % (limit or ("unread", "unread")))
            clipboard_open = "TRIAL-CLIPBOARD-OPEN" in out_text
            if clipboard_open and clipboard_closed:
                return ("a confined process was answered by the "
                        "pasteboard, a service the profile does "
                        "not name: the profile did not hold")
            if proc.returncode not in (0, None):
                return ("the confined trial process exited %s "
                        "after reading and writing (%s)"
                        % (proc.returncode, _trial_tail(err_text)))
            if facts is not None:
                facts["limit_kib"] = int(limit[0])
                facts["clipboard_open"] = clipboard_open
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


# What each passing trial read, by the ceiling and the
# services it was run under: the limit a job carries on this
# host. The posture report words the memory ceiling from it.
_trial_lock = threading.Lock()
_trial_verdicts = {}


def trial_facts(memory_bytes=DEFAULT_PROCESS_MEMORY_BYTES,
                mach_services=()):
    """What the trial run under `memory_bytes` and the
    operator's `mach_services` read, or {} when none has
    passed in this process."""
    with _trial_lock:
        verdict = _trial_verdicts.get(
            (memory_bytes, tuple(mach_services)))
    return dict(verdict[1]) if verdict is not None \
        and verdict[0] is None else {}


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

        The tool itself, and the shell the shim runs on. The
        full trial is macos_confinement_problem's; this is
        the cheap half the spawn also checks, so a spawn on a
        host that lost either refuses instead of
        half-engaging.
        """
        for tool in (SANDBOX_EXEC_BIN, SHELL_BIN):
            if not (os.path.isfile(tool) and os.access(tool, os.X_OK)):
                return "%s is missing or not executable" % tool
        return None

    def macos_startup_problem(cfg=None, timeout=15):
        """None if sandbox-exec can start a trivially confined
        process on this host, else why not.

        This is a necessary condition, not a sufficient one: it
        proves the config's macos block reads, the tools are
        present and a generated profile parses and starts. A
        confined process that starts but cannot work is the
        trial's subject, in macos_confinement_problem; a
        particular job's spawn still makes its own profile,
        and its failure refuses that job then.
        """
        try:
            confinement_settings(cfg)
        except RuntimeError as e:
            return str(e)
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

    def macos_confinement_problem(cfg=None, timeout=15):
        """None when the confinement controls can engage here.

        Stronger than the startup probe: the tool must start a
        confined process, AND a trial process under the full
        controls (the generated profile, the launcher shim, the
        ceiling this config names) must read its staged file,
        write its work directory, be refused a write and a
        read outside it, carry a data-size ceiling of its own
        and be refused the clipboard, through
        confinement_trial_problem. The verdict is kept for
        the life of the process, one per ceiling and list of
        services -- the per-job gate consults this probe, and
        the trial's cost (one confined spawn) is paid once
        per runner start, not once per job.
        """
        problem = macos_startup_problem(cfg, timeout=timeout)
        if problem is not None:
            return problem
        st = confinement_settings(cfg)
        memory, services = st["process_memory_bytes"], \
            st["mach_services"]

        def _spawn(argv, cwd=None, env=None):
            return spawn_confined_process(
                argv, cwd=cwd, env=env, memory_bytes=memory,
                mach_services=services)

        key = (memory, services)
        with _trial_lock:
            if key not in _trial_verdicts:
                facts = {}
                _trial_verdicts[key] = (
                    confinement_trial_problem(
                        _spawn, facts=facts,
                        clipboard_closed=PASTEBOARD_SERVICE
                        not in services),
                    facts)
            return _trial_verdicts[key][0]

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
        .confinement_notes is what this job's launch carried
        beyond the status string, for the audit record's
        detail.
        """

        def __init__(self, argv, inner, notes=()):
            self.args = argv
            self.pid = inner.pid
            self._inner = inner
            self.returncode = None
            self.confinement_status = STATUS_CONFINEMENT
            self.confinement_notes = list(notes)
            self._closed = False

        def communicate(self, timeout=None):
            out, err = self._inner.communicate(timeout=timeout)
            self.returncode = self._inner.returncode
            return out, err

        def communicate_held(self, held, timeout=None):
            """communicate, by a reader with a bar on what it
            holds of each stream (runner/ops/helpers.py, Held).
            The wrapper lends the reader the wrapped process,
            which it reads as communicate() reads it: the same
            wait, and the same TimeoutExpired."""
            out, err = held(self._inner, timeout)
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
                               memory_bytes=None, cfg=None,
                               mach_services=None):
        """Create a job process under every confinement control.

        argv is the full command (interpreter, script, args) in
        host paths; cwd is the job's work directory, the
        profile's one writable tree. The per-job temp directory
        is made inside it and TMPDIR pointed at it. sandbox-exec
        applies the generated profile to the launcher shim,
        which sets the data-size ceiling -- `memory_bytes`, or
        the one `cfg` names, or the default -- before it execs
        the job's command; the profile names the services of
        the session the job may look up -- the backend's own,
        and `mach_services`, or the ones `cfg` names; `user`,
        when the job_user seam hands
        one over, is applied to the whole chain between the
        fork and the exec of sandbox-exec. A
        MacOSConfinedProcess is returned whose
        .confinement_status is STATUS_CONFINEMENT. Raises
        RuntimeError when any control could not be applied --
        there is no unconfined fallback to fall through to.
        """
        problem = _basic_problem()
        if problem is not None:
            raise RuntimeError(problem)
        if memory_bytes is None or mach_services is None:
            st = confinement_settings(cfg)
            if memory_bytes is None:
                memory_bytes = st["process_memory_bytes"]
            if mach_services is None:
                mach_services = st["mach_services"]
        if cwd is None:
            cwd = os.getcwd()
        sandbox_argv, _profile = build_sandbox_argv(
            argv, cwd=cwd, memory_bytes=memory_bytes,
            mach_services=mach_services)
        drop = job_user_drop(user)
        notes = ["memory ceiling %s above a bare process's address "
                 "map, soft and hard"
                 % human_size(ceiling_kib(memory_bytes))]
        named = session_services(
            mach_services)[len(SESSION_SERVICES):]
        if named:
            notes.append("services the config names: %s"
                         % ", ".join(named))
        if drop:
            notes.append("job user %s applied at the spawn door"
                         % user)
        env2 = dict(env) if env is not None else dict(os.environ)
        try:
            job_tmp = os.path.join(cwd, JOB_TMP_NAME)
            os.makedirs(job_tmp, exist_ok=True)
            env2["TMPDIR"] = job_tmp
            if drop:
                # The directory was just made by the runner; the
                # job that is to use it is the job user's.
                os.chown(job_tmp, drop["user"], drop["group"])
        except OSError:
            pass
        try:
            inner = subprocess.Popen(
                sandbox_argv, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=cwd, env=env2, start_new_session=True, **drop)
        except (OSError, ValueError,
                subprocess.SubprocessError) as e:
            raise RuntimeError(
                "the confined spawn could not be started: %s" % e)
        return MacOSConfinedProcess(list(argv), inner, notes)
