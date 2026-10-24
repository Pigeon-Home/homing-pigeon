#!/usr/bin/env python3
"""Run the unittest suite in parallel module shards.

The full suite takes over five minutes single-threaded on the
Windows CI runner, while every other step of that job combined
takes about a minute -- the serial suite run IS the Windows build
time. The suite's modules are independent (each builds its own
temp state), so sharding the module list across worker processes
cuts the wall time roughly by the worker count without changing
what is tested: every worker runs plain ``python -m unittest``
over its shard, and this parent fails if any worker fails.

Sharding is by measured test count per module (longest-processing-
time greedy), so a few very large scenario/property modules do not
pile onto one worker while the others idle. Discovery matches
``python -m unittest discover -s runner/tests -t .`` exactly -- the
parent discovers the same suite, counts it per module, and hands
each worker the module names it would have run itself.

Usage:
    python runner/tools/run_tests_parallel.py [--jobs N]
                                       [--start-dir runner/tests]
                                       [--top-level-dir .]
                                       [--durations N]
                                       [--wall-clock MINUTES]
                                       [module ...]

With explicit modules, only those run (still sharded). Exit code
is 0 only if every shard passes; discovering zero tests is an
error (exit 2), never a silent green.

Two things the report carries so a red or slow Windows job can be
read from the run page, not only from a downloaded log
(Agent-Stamp 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c, 2026-10-22):

- ``--durations N`` hands unittest's own ``--durations`` to every
  shard (Python 3.12+; older interpreters run without it and say
  so), and a passing shard's report keeps that block instead of
  only the last four lines. Each shard also reports its wall time,
  so the long pole among the shards is one line.
- Under GitHub Actions, every ``FAIL:`` / ``ERROR:`` line in a
  failed shard's output becomes a ``::error`` annotation naming
  the test, so the run page lists the failing tests. Outside
  Actions nothing is annotated. Annotation never changes the
  verdict and, like all reporting here, cannot crash the run.
- ``--wall-clock MINUTES`` runs every shard under
  runner/tools/suite_wall_clock.py, so a shard still running at the
  deadline stops and names the test it was in (stack in its dump,
  ``::error`` on the run page), instead of the job sitting until
  its own limit with nothing in the log. That is what happened on
  2026-10-23: one test looped forever and both CI suites sat past
  80 minutes. The parent keeps a hard stop 90 seconds past the
  deadline for a shard whose clock could not fire; that shard is
  reported as timed out with whatever it had printed.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest

_FAILED_TEST_RE = re.compile(r"^(FAIL|ERROR): (\S+) \(([\w.]+)\)", re.M)
_DURATIONS_HEADER = "Slowest test durations"
# The workflow-command parser treats these as part of the command.
_ANNOTATION_UNSAFE = str.maketrans({"\r": " ", "\n": " ", "%": "%25",
                                    ":": "%3A", ",": "%2C"})


def _emit(text):
    """Write one block of parent output to stdout.

    Shard output is utf-8 text and may carry characters the
    parent's stdout cannot encode -- a Windows CI console is
    cp1252, and a shard dump of test names and failure text is
    exactly where an exotic character lands. The v3.7.36-era
    Windows run of 9d8cdac died here: printing a failed shard's
    output raised UnicodeEncodeError, the reporter destroyed the
    failure report it existed to print, and the shards after it
    were never reported at all. Writing the block to the raw
    buffer as utf-8 with replacement keeps a shard's output from
    ever crashing the reporter. Streams without a buffer
    (StringIO under tests) take the plain text path; if even that
    raises, run_shards isolates the failure per shard.
    """
    if not text.endswith("\n"):
        text += "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode("utf-8", "replace"))
        buffer.flush()
    else:
        sys.stdout.write(text)
        sys.stdout.flush()


def _emit_quietly(text):
    """_emit for last-resort notes: reporting must never crash the run."""
    try:
        _emit(text)
    except Exception:
        pass


def _harden_streams():
    """Best-effort: make stdout/stderr replace unencodable characters.

    Guarded for streams that cannot be reconfigured (StringIO and
    other stand-ins have no reconfigure). _emit's buffer path is
    the primary defense and does not depend on this succeeding.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (OSError, ValueError):
            pass


def _discard_tmpdir(tmp):
    """Clean up the shard-log directory; failure here is litter only.

    Every shard handle is closed before this runs, so cleanup has
    nothing held open. A platform that still refuses (an indexer
    or scanner holding a log, say) must not turn finished
    reporting into a crash -- the 9d8cdac Windows run ended in
    PermissionError [WinError 32] from exactly this cleanup after
    the reporter's exception left a handle open. On 3.10+ the
    directory is also created with ignore_cleanup_errors=True;
    this wrapper is the equivalent tolerance on 3.9.
    """
    try:
        tmp.cleanup()
    except Exception:
        pass


def module_test_counts(start_dir, top_level_dir):
    """Discover the suite and return {module_name: test_count}.

    Import failures during discovery surface as _FailedTest entries
    whose id is "unittest.loader._FailedTest.<module>"; the module
    name is recovered from that id and counted under its own
    module so a worker reproduces the failure loudly instead of
    the parent quietly dropping the module from every shard.
    """
    loader = unittest.TestLoader()
    # Discover imports every module it finds into this process.
    # A later discover of another tree that reuses a module name
    # (the tests do this with test_alpha) raises ImportError
    # unless those imports are dropped. The v3.7.35 tag's clean
    # run hit that after stats left the import cached.
    before = set(sys.modules)
    try:
        suite = loader.discover(start_dir, top_level_dir=top_level_dir)
        counts = {}
        failed_prefix = "unittest.loader._FailedTest."

        def walk(node):
            for item in node:
                if isinstance(item, unittest.TestSuite):
                    walk(item)
                elif isinstance(item, unittest.loader._FailedTest):
                    mod = item.id()
                    if mod.startswith(failed_prefix):
                        mod = mod[len(failed_prefix):]
                    counts[mod] = counts.get(mod, 0) + 1
                else:
                    mod = type(item).__module__
                    counts[mod] = counts.get(mod, 0) + 1

        walk(suite)
        return counts
    finally:
        for name in list(sys.modules):
            if name not in before:
                sys.modules.pop(name, None)


def shard_modules(counts, jobs):
    """Greedy longest-processing-time sharding.

    Returns a list of shards (each a list of module names) such
    that every module appears in exactly one shard and the summed
    test counts are as balanced as the greedy pass can make them.
    Deterministic: equal loads break ties by shard index, modules
    are considered in (-count, name) order.
    """
    if jobs < 1:
        raise ValueError("jobs must be >= 1")
    shards = [[] for _ in range(min(jobs, len(counts)) or 1)]
    loads = [0] * len(shards)
    for mod, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        idx = min(range(len(shards)), key=lambda i: loads[i])
        shards[idx].append(mod)
        loads[idx] += count
    return [s for s in shards if s]


def _child_env():
    """UTF-8 stdio for shard children, without UTF-8 mode.

    The parent decodes each shard log as UTF-8. A Windows child
    whose stdout is the ANSI code page cannot print a character
    outside that page, so the shard fails on the print itself, and
    a failure dump that does get out arrives as backslash escapes
    instead of the text the reporter is supposed to carry.
    PYTHONIOENCODING changes the stdio encoding only. It does not
    enable UTF-8 mode, so open() keeps the locale encoding the
    suite already runs under.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


_WALL_CLOCK_TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "suite_wall_clock.py")
_HARD_STOP_GRACE_SEC = 90.0


def shard_command(extra, shard, wall_clock=0):
    """The unittest command for one shard.

    Plain ``python -m unittest`` by default; under a wall clock the
    same arguments go through runner/tools/suite_wall_clock.py, which runs
    unittest in-process and names the running test at the deadline.
    """
    if wall_clock and wall_clock > 0:
        return ([sys.executable, _WALL_CLOCK_TOOL,
                 "--minutes", "%g" % wall_clock, "--"] + extra + shard)
    return [sys.executable, "-m", "unittest"] + extra + shard


def _kill_tree(proc):
    """Stop a shard and what it started; never raises."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           capture_output=True, timeout=30)
        else:
            try:
                os.killpg(proc.pid, 9)
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()
        proc.wait(timeout=30)
    except Exception:
        pass


def durations_args(durations, version_info=None):
    """The unittest arguments that ask for the slowest-test block.

    unittest grew ``--durations`` in Python 3.12. An older
    interpreter gets no flag (it would refuse the run), and the
    caller says so once. None or 0 asks for nothing.
    """
    if not durations:
        return []
    if (version_info or sys.version_info) < (3, 12):
        return []
    return ["--durations", str(durations)]


def failed_tests(output):
    """The test ids named by FAIL:/ERROR: lines, in order, once each."""
    seen = []
    for m in _FAILED_TEST_RE.finditer(output):
        test_id = m.group(3)
        if test_id not in seen:
            seen.append(test_id)
    return seen


def under_actions(environ=None):
    """True when GitHub Actions is reading the output.

    ``environ`` None means the process environment; an empty
    mapping means an environment with nothing in it, and must not
    fall through to the real one (it did, on the first CI run of
    this code, where GITHUB_ACTIONS is of course set).
    """
    env = os.environ if environ is None else environ
    return env.get("GITHUB_ACTIONS") == "true"


def annotations_for(output, shard):
    """``::error`` workflow commands naming each failed test in a shard.

    One line per failed test, title first so the run page shows
    the test id, the message saying which shard carries the dump.
    Actions keeps the first ten error annotations of a step; the
    full list is still in the log above them.
    """
    lines = []
    for test_id in failed_tests(output):
        title = test_id.translate(_ANNOTATION_UNSAFE)
        message = ("unittest failed in shard %d; its output is above"
                   % shard).translate(_ANNOTATION_UNSAFE)
        lines.append("::error title=%s::%s" % (title, message))
    return lines


def passing_tail(output, durations):
    """What a passing shard reports: the summary, or the durations block.

    Without durations the last four lines (the separator, "Ran N
    tests", a blank, and OK) are the whole story. With durations
    the block unittest prints before "Ran" is the story, so the
    report starts at its header and runs to the end.
    """
    text = output.strip()
    if durations:
        where = text.find(_DURATIONS_HEADER)
        if where >= 0:
            return text[where:]
    return "\n".join(text.splitlines()[-4:])


def run_shards(shards, top_level_dir, durations=None, annotate=None,
               wall_clock=0):
    """Run each shard as a unittest subprocess; return exit code.

    Output is captured per shard and printed when the shard
    finishes (full output for failures, the unittest summary tail
    for passes), so the CI log stays readable without interleaving
    four workers' dots into soup.

    Reporting is fault-isolated per shard. A shard is counted
    failed the moment its exit code is known, before anything is
    printed, and a failure to print one shard's output never skips
    the shards after it or changes the verdict. Every file handle
    is closed in a finally, whatever printing does, and the temp
    directory's cleanup tolerates refusal instead of crashing.

    ``durations`` asks each shard for its slowest tests (see
    durations_args). ``annotate`` None means "when under Actions";
    True or False forces it. Annotations are emitted after a
    failed shard's dump and never affect the exit code.
    ``wall_clock`` (minutes, 0 for none) runs each shard under
    runner/tools/suite_wall_clock.py and hard-stops a shard that outlives
    the deadline by more than a grace period; a timed-out shard is
    a failed shard.
    """
    if annotate is None:
        annotate = under_actions()
    extra = durations_args(durations)
    if durations and not extra:
        _emit("durations: unittest --durations needs Python 3.12+; "
              "this is %d.%d, running without it"
              % (sys.version_info[0], sys.version_info[1]))
    kwargs = {}
    if sys.version_info >= (3, 10):
        kwargs["ignore_cleanup_errors"] = True
    tmp = tempfile.TemporaryDirectory(prefix="hp-test-shards-", **kwargs)
    procs = []
    failed = []
    started = time.monotonic()
    try:
        for i, shard in enumerate(shards):
            out_path = os.path.join(tmp.name, "shard-%d.log" % i)
            fh = open(out_path, "wb")
            popen_kw = {}
            if wall_clock and os.name != "nt":
                # Its own process group, so the hard stop can take
                # the shard and anything it spawned together.
                popen_kw["start_new_session"] = True
            try:
                proc = subprocess.Popen(
                    shard_command(extra, shard, wall_clock),
                    cwd=top_level_dir, stdout=fh,
                    stderr=subprocess.STDOUT,
                    env=_child_env(), **popen_kw)
            except Exception:
                fh.close()
                raise
            procs.append((i, proc, fh, out_path))
            _emit("shard %d: %d module(s): %s"
                  % (i, len(shard), ", ".join(shard)))
        hard_stop = (started + wall_clock * 60.0 + _HARD_STOP_GRACE_SEC
                     if wall_clock else None)
        for i, proc, fh, out_path in procs:
            timed_out = False
            try:
                if hard_stop is None:
                    rc = proc.wait()
                else:
                    try:
                        rc = proc.wait(
                            timeout=max(0.0, hard_stop - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        _kill_tree(proc)
                        rc = "timeout"
            except Exception:
                rc = None
            finally:
                fh.close()
            elapsed = time.monotonic() - started
            if rc != 0:
                failed.append(i)
            if timed_out:
                _emit_quietly(
                    "=== shard %d TIMED OUT: still running %.0fs past "
                    "its %g-minute wall clock; stopped by the parent ==="
                    % (i, _HARD_STOP_GRACE_SEC, wall_clock))
                if annotate:
                    _emit_quietly(
                        "::error title=shard %d::still running %g minutes "
                        "past its wall clock and stopped by the parent; "
                        "its partial output is in the log"
                        % (i, _HARD_STOP_GRACE_SEC / 60.0))
            try:
                with open(out_path, encoding="utf-8",
                          errors="replace") as rf:
                    output = rf.read()
                if rc != 0:
                    _emit("=== shard %d FAILED (exit %s) ===\n(%.1fs)\n%s"
                          % (i, rc, elapsed, output))
                    if annotate:
                        for line in annotations_for(output, i):
                            _emit_quietly(line)
                else:
                    _emit("shard %d: OK in %.1fs\n%s"
                          % (i, elapsed,
                             passing_tail(output, bool(extra))))
            except Exception:
                _emit_quietly(
                    "shard %d: its captured output could not be printed"
                    % i)
    finally:
        _discard_tmpdir(tmp)
    if failed:
        _emit("FAILED shard(s): %s" % ", ".join(str(i) for i in failed))
        return 1
    return 0


def main(argv=None):
    _harden_streams()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int,
                        default=os.cpu_count() or 1,
                        help="worker processes (default: CPU count)")
    parser.add_argument("--start-dir", default="runner/tests")
    parser.add_argument("--top-level-dir", default=".")
    parser.add_argument("--durations", type=int, default=0, metavar="N",
                        help="each shard lists its N slowest tests "
                             "(unittest --durations; Python 3.12+)")
    parser.add_argument("--wall-clock", type=float, default=0.0,
                        metavar="MINUTES",
                        help="stop a shard still running after this many "
                             "minutes and name the test it was in "
                             "(0: no clock)")
    parser.add_argument("modules", nargs="*",
                        help="explicit modules to run instead of "
                             "discovering the whole suite")
    args = parser.parse_args(argv)
    if args.durations < 0:
        parser.error("--durations must be >= 0")
    if args.wall_clock < 0:
        parser.error("--wall-clock must be >= 0")

    if args.modules:
        counts = {mod: 1 for mod in args.modules}
    else:
        counts = module_test_counts(args.start_dir, args.top_level_dir)
    if not counts:
        print("error: no tests discovered under %s -- refusing to "
              "report a vacuous green" % args.start_dir, file=sys.stderr)
        return 2
    shards = shard_modules(counts, args.jobs)
    total = sum(counts.values())
    _emit("running %d test(s) from %d module(s) in %d shard(s)"
          % (total, len(counts), len(shards)))
    started = time.monotonic()
    rc = run_shards(shards, args.top_level_dir, durations=args.durations,
                    wall_clock=args.wall_clock)
    _emit("sharded run finished in %.1fs (exit %d)"
          % (time.monotonic() - started, rc))
    return rc


if __name__ == "__main__":
    sys.exit(main())
