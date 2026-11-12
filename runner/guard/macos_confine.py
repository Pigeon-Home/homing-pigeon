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
import posixpath
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


def _profile_realpath(path):
    """The canonical form of `path` for the profile.

    os.path.realpath on the host, which resolves every symlink
    and firmlink, except when the host rewrites a leading-slash
    POSIX path into a drive-letter form (Windows). The macOS
    profile writer requires a leading /; the field tests are
    platform-neutral and pass POSIX absolute paths, so keep the
    original form in that case. On a real macOS host the rewrite
    never happens, and the realpath is the form Seatbelt matches.
    """
    real = os.path.realpath(path)
    if isinstance(path, str) and path.startswith("/") and not real.startswith("/"):
        return path
    return real
