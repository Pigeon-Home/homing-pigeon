"""Job file names: one rule set, refused the same way on every platform.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

A `files[].name` names a path under the job's work directory. The
staging check (`_staged_dest` in runner.py) resolves the real path
and refuses anything that lands outside, which catches `..`, an
absolute POSIX path and, on Windows, a drive letter. It did not catch
everything the same way everywhere: `os.path.join("/w", "C:\\x")` is
`/w/C:\\x` on Linux, inside the work dir, so a job written for a
Windows runner staged a file literally named `C:\\x` on a Linux
runner; and the Windows device names (CON, NUL, COM1) were refused
only when the runner itself was Windows. A job is one object sent to
whatever runner holds the key, so the refusal cannot depend on which
OS happens to run it.

The rules, numbered so a rejection result tells the author what to
fix (the number is in the message):

1. A non-empty string, no NUL byte, at most 255 bytes per component
   and 1024 bytes in all (UTF-8).
2. No backslash. `/` is the protocol's only separator; the runner
   converts to the host's separator itself.
3. Not absolute: no leading `/`, no `[A-Za-z]:` first component (a
   drive letter, relative or not), no `//server/share` UNC prefix.
   `os.path.isabs` and `os.path.splitdrive` are consulted too, but
   alone they answer differently per platform.
4. No component is `.` or `..`, and none is empty (so no `a//b`, no
   trailing `/`).
5. Every component matches `[A-Za-z0-9._-]+`, does not start with
   `-` (a name must not read as a flag to an interpreter), and is not
   dots only.
6. No component is a Windows reserved device name (`CON`, `PRN`,
   `AUX`, `NUL`, `COM1`-`COM9`, `LPT1`-`LPT9`, with or without an
   extension), on every platform.

The staging check still runs after these: the rules are the first
gate, the real-path check is the one that catches a symlink planted
in the work tree. Stdlib only, no runner imports: the sender
(runner/cloud/send_job.py) applies the same rules at composition
time, so an author is told before a rejection result would.
"""
import os
import re

MAX_COMPONENT_BYTES = 255
MAX_NAME_BYTES = 1024

_COMPONENT = re.compile(r"\A[A-Za-z0-9._-]+\Z")
_DRIVE = re.compile(r"\A[A-Za-z]:")

_WIN_DEVICES = (
    {"CON", "PRN", "AUX", "NUL"}
    | {"COM%d" % i for i in range(1, 10)}
    | {"LPT%d" % i for i in range(1, 10)}
)

RULES = {
    1: "a non-empty string, no NUL, at most 255 bytes per component "
       "and 1024 bytes in all",
    2: "no backslash ('/' is the only separator)",
    3: "not absolute (no leading '/', drive letter, or UNC prefix)",
    4: "no '.', '..' or empty component",
    5: "components of [A-Za-z0-9._-], not starting with '-', not "
       "dots only",
    6: "no Windows device name (CON, NUL, COM1, ...) on any platform",
}


def _shown(name):
    """The name as a rejection shows it: repr, cut at 60 characters."""
    if not isinstance(name, str):
        return type(name).__name__
    text = repr(name)
    return text if len(text) <= 60 else text[:57] + "..."


class BadFileName(ValueError):
    """A files[].name that breaks one rule; `rule` says which."""

    def __init__(self, rule, why, name=None):
        self.rule = rule
        self.why = why
        shown = "" if name is None else " " + _shown(name)
        super().__init__("unsafe file name%s (rule %d): %s"
                         % (shown, rule, why))


def windows_reserved_name(name) -> bool:
    """True for CON, NUL, COM1, a trailing dot, and the same with an
    extension. Windows opens these as devices, or rewrites the
    trailing dot, no matter which directory they are joined onto."""
    if not isinstance(name, str):
        return False
    leaf = name.replace("/", "\\").rsplit("\\", 1)[-1]
    if not leaf or leaf.endswith(".") or leaf.endswith(" ") or ":" in leaf:
        return True
    return leaf.split(".", 1)[0].upper() in _WIN_DEVICES


def validate_file_name(name) -> str:
    """The normalized relative path (components joined by '/'), or
    BadFileName naming the rule it broke."""
    if not isinstance(name, str) or not name:
        raise BadFileName(1, "a non-empty string is required", name)
    if "\x00" in name:
        raise BadFileName(1, "a NUL byte", name)
    try:
        raw = name.encode("utf-8")
    except UnicodeEncodeError:
        raise BadFileName(1, "not valid text", name)
    if len(raw) > MAX_NAME_BYTES:
        raise BadFileName(1, "longer than %d bytes" % MAX_NAME_BYTES, name)
    if "\\" in name:
        raise BadFileName(2, "a backslash; '/' is the only separator", name)
    if name.startswith("/") or os.path.isabs(name) \
            or os.path.splitdrive(name)[0]:
        raise BadFileName(3, "an absolute path", name)
    parts = name.split("/")
    if _DRIVE.match(parts[0]):
        raise BadFileName(3, "a drive letter", name)
    for part in parts:
        if part == "":
            raise BadFileName(4, "an empty component (a doubled or "
                                 "trailing '/')", name)
        if part in (".", ".."):
            raise BadFileName(4, "'.' or '..' as a component", name)
        if len(part.encode("utf-8")) > MAX_COMPONENT_BYTES:
            raise BadFileName(1, "a component longer than %d bytes"
                              % MAX_COMPONENT_BYTES, name)
        if not _COMPONENT.match(part):
            raise BadFileName(5, "a component outside [A-Za-z0-9._-]: "
                                 "%r" % part, name)
        if part.startswith("-"):
            raise BadFileName(5, "a component that starts with '-': %r"
                              % part, name)
        if part.strip(".") == "":
            raise BadFileName(5, "a component of dots only", name)
        if windows_reserved_name(part):
            raise BadFileName(6, "a Windows device name: %s" % part, name)
    return "/".join(parts)
