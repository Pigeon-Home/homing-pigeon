#!/usr/bin/env python3
"""Run the test suite under the simulated Windows surface.

    python .github/tools/run_tests_windows_sim.py [--pattern 'test_*.py']
                                          [--start-dir tests]
                                          [--top-level .]
                                          [--describe]

Exit status is the suite's: 0 when every test passes under the
surface, 1 otherwise. Failures are printed with the standard
unittest report; triage each as product bug, test bug (the
d2da8e6 class: the test assumed a POSIX attribute the product
never promised), or simulation artifact (see
.github/tools/windows_surface.py's "not simulated" list) -- in that
order of suspicion.

Reading the results -- the boundary of what the surface can
prove. The surface fakes the HOST IDENTITY (os.name,
sys.platform, platform.*) and the API ABSENCES faithfully, in
this process only. It follows that:

- Failures in parsing, config, dispatch, and validation logic
  are FINDINGS: that code sees exactly what it would see on
  Windows, and CI's Windows job is the only other place they
  would surface.
- Failures in tests that EXECUTE through the faked identity --
  running a job with the platform-default interpreter, spawning
  a supervised child process (children are real processes and
  do not inherit the surface), binding or timing against the
  real OS -- are artifacts of the mismatch between the faked
  identity and the real substrate. The first full-suite run's
  clusters were of this kind: jobs dispatched to a "Windows"
  default interpreter that does not exist on the host
  (exit_code -2), and the Oracle opinion drives whose verdict
  expectations are staged for the host they were written on.
  Those paths are what the real build-windows job verifies;
  the sim cannot, and its failures there are not evidence
  against them.

TMPDIR is pointed at a fresh scratch directory before the
surface is applied: tempfile's candidate list consults TMPDIR
on every platform, so the harness keeps a working temp root
even with os.name claiming "nt".
"""
import argparse
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from windows_surface import apply_surface, surface_description  # noqa: E402

# Stdlib modules that branch on os.name/sys.platform at import
# time. They must be in sys.modules before the surface goes on,
# or their import-time branches reach for Windows-only builtins
# (nt, _winapi) that a POSIX build does not have. See
# .github/tools/windows_surface.py's module docstring.
_PREIMPORT = (
    "asyncio", "asyncio.events", "ctypes", "email", "email.policy",
    "imaplib", "json", "logging", "multiprocessing", "pathlib",
    "shutil", "smtplib", "socket", "ssl", "subprocess", "tarfile",
    "tempfile", "threading", "urllib.request", "uuid", "zipfile",
)


def _preimport_stdlib():
    import importlib
    for name in _PREIMPORT:
        try:
            importlib.import_module(name)
        except Exception:
            pass  # a missing optional module must not stop the run


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the suite under the simulated Windows surface.")
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--start-dir", default="tests")
    parser.add_argument("--top-level", default=".")
    parser.add_argument("--describe", action="store_true",
                        help="print the surface and exit")
    args = parser.parse_args(argv)

    if args.describe:
        import json
        print(json.dumps(surface_description(), indent=2))
        return 0

    scratch = tempfile.mkdtemp(prefix="hp-winsim-")
    os.environ["TMPDIR"] = scratch
    os.environ.setdefault("TEMP", scratch)
    os.environ.setdefault("TMP", scratch)

    _preimport_stdlib()
    restore = apply_surface()
    try:
        loader = unittest.TestLoader()
        suite = loader.discover(args.start_dir, pattern=args.pattern,
                                top_level_dir=args.top_level)
        if suite.countTestCases() == 0:
            print("windows-sim: discovery came up empty", file=sys.stderr)
            return 1
        runner = unittest.TextTestRunner(verbosity=1)
        result = runner.run(suite)
    finally:
        restore()
    print(f"windows-sim: {result.testsRun} tests, "
          f"{len(result.failures)} failures, {len(result.errors)} errors, "
          f"{len(result.skipped)} skipped")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
