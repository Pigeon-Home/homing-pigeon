#!/usr/bin/env python3
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
"""Run unittest under a wall clock that names the test it killed.

    python runner/tools/suite_wall_clock.py --minutes 20 -- discover -s runner/tests -t . -v

Everything after ``--`` is handed to ``unittest.main`` unchanged, so
this is ``python -m unittest ...`` with one addition: when the run is
still going at the deadline, the process stops and says which test
was running, with the main thread's stack, instead of sitting there
until the job's own limit.

Why it exists (2026-10-23): one test called a transport extension's
``main()`` in-process, a behavior change made that call listen
forever, and both CI suites sat past 80 minutes with nothing in the
log. The job had no clock, the log was readable only in the browser,
and the one line that named the test was the unfinished one at the
end of it. This clock is not a job timer (the workflow's only two
timers stay on the two scarce runners, by the owner's call): a job
timer kills the job and says nothing, this says the test.

On the deadline:

- the test running on the main thread is named (``TestCase.id()``,
  found on the stack), and under GitHub Actions it becomes an
  ``::error`` annotation so the run page carries it;
- the main thread's stack is printed, most recent call first, then
  the other threads' stacks;
- the process exits 124 (the convention ``timeout(1)`` uses).

A faulthandler dump thirty seconds after that is the backstop for
the case where Python threads cannot run at all; it exits 1.

Outside the deadline the exit status is unittest's own.
"""

import argparse
import faulthandler
import os
import sys
import threading
import time
import traceback
import unittest

_TIMEOUT_EXIT = 124
_ANNOTATION_UNSAFE = str.maketrans({"\r": " ", "\n": " ", "%": "%25",
                                    ":": "%3A", ",": "%2C"})


def under_actions(environ=None):
    env = os.environ if environ is None else environ
    return env.get("GITHUB_ACTIONS") == "true"


def running_test(frames):
    """The id of the TestCase whose test method is on ``frames``.

    ``frames`` is a list of (frame, filename, lineno, function)
    innermost first, the shape ``traceback.extract_stack`` does not
    give but ``_stack_of`` below does. The test is the innermost
    frame whose ``self`` is a TestCase executing its own test
    method; None when no test is on the stack (discovery, setup of
    the runner, a stuck module import).
    """
    for frame in frames:
        this = frame.f_locals.get("self")
        if not isinstance(this, unittest.TestCase):
            continue
        method = getattr(this, "_testMethodName", None)
        if method and frame.f_code.co_name == method:
            try:
                return this.id()
            except Exception:  # noqa: BLE001 - reporting must not raise
                return "%s.%s" % (type(this).__name__, method)
    return None


def _stack_of(frame):
    frames = []
    while frame is not None:
        frames.append(frame)
        frame = frame.f_back
    return frames


def report(minutes, main_ident, current_frames, out):
    """Write the deadline report; return the stuck test's id or None."""
    main_frame = current_frames.get(main_ident)
    frames = _stack_of(main_frame) if main_frame is not None else []
    test_id = running_test(frames)
    out.write("\n=== suite wall clock: %g minutes elapsed, the run is "
              "killed ===\n" % minutes)
    out.write("running test: %s\n" % (test_id or "(none on the main "
                                      "thread; see the stack)"))
    if main_frame is not None:
        out.write("main thread, most recent call first:\n")
        for line in reversed(traceback.format_stack(main_frame)):
            out.write(line)
    others = [(ident, f) for ident, f in current_frames.items()
              if ident not in (main_ident, threading.get_ident())]
    out.write("other threads: %d\n" % len(others))
    for ident, frame in others:
        out.write("--- thread %s, most recent call first:\n" % ident)
        for line in reversed(traceback.format_stack(frame)[-12:]):
            out.write(line)
    out.flush()
    return test_id


def annotation(test_id, minutes):
    title = (test_id or "suite wall clock").translate(_ANNOTATION_UNSAFE)
    message = ("still running after %g minutes; the suite was killed "
               "here, the stack is in the log" % minutes
               ).translate(_ANNOTATION_UNSAFE)
    return "::error title=%s::%s" % (title, message)


def _arm(minutes, main_ident, annotate):
    seconds = minutes * 60.0
    # Backstop: if no Python thread can run, this C-level watchdog
    # still dumps every thread and exits (status 1).
    faulthandler.dump_traceback_later(seconds + 30.0, repeat=False,
                                      exit=True)

    def watchdog():
        time.sleep(seconds)
        try:
            frames = sys._current_frames()  # noqa: SLF001 - the point
            test_id = report(minutes, main_ident, frames, sys.stderr)
            if annotate:
                sys.stdout.write(annotation(test_id, minutes) + "\n")
                sys.stdout.flush()
        finally:
            os._exit(_TIMEOUT_EXIT)

    t = threading.Thread(target=watchdog, name="suite-wall-clock",
                         daemon=True)
    t.start()
    return t


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        usage="%(prog)s --minutes M -- <unittest arguments>")
    ap.add_argument("--minutes", type=float, required=True,
                    help="kill the run after this many minutes")
    ap.add_argument("rest", nargs=argparse.REMAINDER,
                    help="arguments for unittest, after --")
    a = ap.parse_args(argv)
    rest = a.rest[1:] if a.rest and a.rest[0] == "--" else a.rest
    if a.minutes <= 0:
        ap.error("--minutes must be positive")
    if not rest:
        ap.error("give the unittest arguments after --")
    # ``python -m unittest`` resolves module names from the current
    # directory; a script run by path has its own folder there
    # instead. Same import root as the command this stands in for.
    cwd = os.getcwd()
    if sys.path[:1] != [cwd]:
        sys.path.insert(0, cwd)
    _arm(a.minutes, threading.main_thread().ident, under_actions())
    # unittest.main exits with the run's status (SystemExit) and
    # never returns; module=None is the ``python -m unittest`` shape.
    unittest.main(module=None, argv=["python -m unittest"] + rest)


if __name__ == "__main__":
    main()
