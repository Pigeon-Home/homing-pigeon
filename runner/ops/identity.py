# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Build identity: the banner every entry point opens with.

One implementation, used by every CLI and every log in the
system. The banner names, in full:

- the version (runner/_version.py, the same constant --version
  has always reported),
- the build stamp: the full source commit the tree was built
  from (runner/_build.py, written by runner/tools/build_stamp.py
  at packaging time; "unknown" in a plain checkout),
- the build checksum: a single SHA-384 over the runner tree's
  manifest, written beside the stamp at packaging time, from
  which the exact tree that ran can be derived,
- the entire platform architecture: OS, OS release, machine
  architecture, and the full platform string,
- the compile/build info: the Python version, implementation
  and compiler, and whether the process is a frozen binary or
  running from source.

--version on every CLI prints this block (see VersionAction:
argparse's own version action collapses the newlines, so the
block is printed by a custom action, verbatim). Every log opens
with it at CRITICAL level -- printed to the terminal always,
never rate-limited, never suppressed by quiet settings. And
announce() implements the first-use rule: the first time a code
module is used in a process, it emits its provenance once;
later calls for the same module emit nothing.

The module lives in runner/ops/ with the runner's other
startup machinery, and is registered in the canonical core
list (runner/ops/core.py) like the entry points it serves.
"""
import argparse
import platform
import sys

try:
    from runner._version import __version__
except ImportError:  # running from inside runner/ as __main__
    from _version import __version__  # type: ignore

import importlib

_build_module = None
for _name in ("runner._build", "_build"):
    try:
        _build_module = importlib.import_module(_name)
        break
    except ImportError:
        continue


def build_stamp():
    """The full source commit this tree was built from, or
    "unknown" in a plain checkout."""
    value = getattr(_build_module, "__build__", "unknown")
    return value if isinstance(value, str) and value else "unknown"


def build_checksum():
    """The SHA-384 over the tree manifest, written beside the
    stamp at packaging time, or "unknown" in a plain checkout."""
    value = getattr(_build_module, "__checksum__", "unknown")
    return value if isinstance(value, str) and value else "unknown"


def identity_text(prog="homing-pigeon", version=None, build=None,
                  checksum=None):
    """The full build identity block, one fact per line.

    `prog` heads the first line, beside the version. The
    overrides exist for entry points that carry their own
    loaded values (the runner's dynamic loads, the installer's
    own version constant); defaults read this module's.
    """
    lines = [
        "%s %s" % (prog, __version__ if version is None else version),
        "build stamp: %s" % (
            build_stamp() if build is None else build),
        "build checksum (sha384): %s" % (
            build_checksum() if checksum is None else checksum),
        "platform: %s %s %s (%s)" % (
            platform.system(), platform.release(),
            platform.machine(), platform.platform()),
        "python: %s %s [%s] %s" % (
            platform.python_version(),
            platform.python_implementation(),
            platform.python_compiler(),
            "frozen" if getattr(sys, "frozen", False) else "source"),
    ]
    return "\n".join(lines)


class VersionAction(argparse.Action):
    """--version: print the full build identity, then exit 0.

    argparse's built-in version action runs the string through
    the help formatter, which collapses the block's newlines;
    this action prints the block verbatim instead.
    """

    def __init__(self, option_strings, dest=argparse.SUPPRESS,
                 default=argparse.SUPPRESS,
                 help="print the full build identity and exit"):
        super().__init__(option_strings=option_strings, dest=dest,
                         nargs=0, default=default, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        print(identity_text(parser.prog))
        parser.exit(0)


_ANNOUNCED = set()


def _print_critical(text):
    try:
        print("[CRITICAL] " + text, flush=True)
    except Exception:
        pass


def announce(module_name, emit=None, version=None, build=None,
             checksum=None):
    """Emit the build identity once for `module_name`.

    The first call for a module in this process emits the block
    through `emit` (one call, the whole block) and returns True;
    every later call for the same module emits nothing and
    returns False. The default emit prints the block to the
    terminal at CRITICAL. A caller with a log passes its own
    emit -- the runner passes one that writes through log() at
    CRITICAL, so the block opens the log file too.
    """
    if module_name in _ANNOUNCED:
        return False
    _ANNOUNCED.add(module_name)
    if emit is None:
        emit = _print_critical
    emit(identity_text(version=version, build=build,
                       checksum=checksum))
    return True


def _reset_announced():
    """Forget every announced module. For tests."""
    _ANNOUNCED.clear()
