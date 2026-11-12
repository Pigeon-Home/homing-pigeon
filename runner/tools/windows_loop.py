#!/usr/bin/env python3
"""Fast loop for the tests that have been failing the Windows leg.

The Windows CI job shards the whole suite
(``runner/tools/run_tests_parallel.py``) and sits near the
20-minute wall. The reds on that leg have been a few modules
that do not need a Windows host: confinement path form, the
probe bounds, the Windows surface, and the slow-model hang
guards. On the 3.16.20.9 build those guards were 5 and 8
seconds and the loaded pool answered in 6.3 and 8.3; they are
30-second hang guards now. This runs that set in a venv, once
or until a pass fails, in well under a minute.

    python3 runner/tools/windows_loop.py
    python3 runner/tools/windows_loop.py --repeat 5

The venv is ``.venv-windows-loop`` at the repo root (gitignored).
A later pass reuses it. The suite is the stdlib, so the venv
gets no packages installed.
"""

import argparse
import os
import subprocess
import sys
import time

# The modules whose failures have shown up on the Windows leg,
# plus the surface tests that simulate that host. Explicit, so
# a pass cannot silently grow into the full suite.
MODULES = (
    "runner.tests.test_macos_confine",
    "runner.tests.test_windows_confine",
    "runner.tests.test_windows_cli_sim",
    "runner.tests.test_windows_durations",
    "runner.tests.test_windows_extensions_negative",
    "runner.tests.test_windows_platform_proofs",
    "runner.tests.test_windows_portability",
    "runner.tests.test_windows_run_as",
    "runner.tests.test_windows_surface",
    "runner.tests.test_low_profile",
    "runner.tests.test_shrink_guard",
    "runner.tests.test_oracle_send.SlowModelTest",
    "runner.tests.test_oracle_send_contract.OracleSendServerTest"
    ".test_slow_model_still_returns_a_body",
)

VENV_DIR = ".venv-windows-loop"


def repo_root():
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.dirname(os.path.dirname(here))


def venv_python(venv):
    for rel in ("bin/python", "Scripts/python.exe"):
        path = os.path.join(venv, rel)
        if os.path.isfile(path):
            return path
    return None


def ensure_venv(root, venv):
    """The venv's interpreter, creating the venv if it is missing."""
    python = venv_python(venv)
    if python:
        return python
    proc = subprocess.run(
        [sys.executable, "-m", "venv", venv], cwd=root)
    if proc.returncode != 0:
        return None
    return venv_python(venv)


def run_once(python, root):
    started = time.monotonic()
    proc = subprocess.run(
        [python, "-m", "unittest", *MODULES, "-q"], cwd=root)
    elapsed = time.monotonic() - started
    return proc.returncode, elapsed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repeat", type=int, default=1,
        help="how many green passes to require (default 1)")
    parser.add_argument(
        "--venv", default=None,
        help="venv directory (default: <repo>/%s)" % VENV_DIR)
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    root = repo_root()
    venv = args.venv or os.path.join(root, VENV_DIR)
    python = ensure_venv(root, venv)
    if not python:
        print("windows loop: could not make a venv at %s" % venv,
              file=sys.stderr)
        return 2
    print("windows loop: %d module(s), %d pass(es), %s"
          % (len(MODULES), args.repeat, python), flush=True)
    for n in range(1, args.repeat + 1):
        code, elapsed = run_once(python, root)
        if code != 0:
            print("windows loop: pass %d FAILED in %.1fs (exit %d)"
                  % (n, elapsed, code), flush=True)
            return code
        print("windows loop: pass %d ok in %.1fs" % (n, elapsed), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
