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
``python -m unittest discover -s tests -t .`` exactly -- the
parent discovers the same suite, counts it per module, and hands
each worker the module names it would have run itself.

Usage:
    python tools/run_tests_parallel.py [--jobs N]
                                       [--start-dir tests]
                                       [--top-level-dir .]
                                       [module ...]

With explicit modules, only those run (still sharded). Exit code
is 0 only if every shard passes; discovering zero tests is an
error (exit 2), never a silent green.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
import unittest


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


def run_shards(shards, top_level_dir):
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
    """
    kwargs = {}
    if sys.version_info >= (3, 10):
        kwargs["ignore_cleanup_errors"] = True
    tmp = tempfile.TemporaryDirectory(prefix="hp-test-shards-", **kwargs)
    procs = []
    failed = []
    try:
        for i, shard in enumerate(shards):
            out_path = os.path.join(tmp.name, "shard-%d.log" % i)
            fh = open(out_path, "wb")
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "unittest"] + shard,
                    cwd=top_level_dir, stdout=fh,
                    stderr=subprocess.STDOUT,
                    env=_child_env())
            except Exception:
                fh.close()
                raise
            procs.append((i, proc, fh, out_path))
            _emit("shard %d: %d module(s): %s"
                  % (i, len(shard), ", ".join(shard)))
        for i, proc, fh, out_path in procs:
            try:
                rc = proc.wait()
            except Exception:
                rc = None
            finally:
                fh.close()
            if rc != 0:
                failed.append(i)
            try:
                with open(out_path, encoding="utf-8",
                          errors="replace") as rf:
                    output = rf.read()
                if rc != 0:
                    _emit("=== shard %d FAILED (exit %s) ===\n%s"
                          % (i, rc, output))
                else:
                    tail = "\n".join(output.strip().splitlines()[-4:])
                    _emit("shard %d: OK\n%s" % (i, tail))
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
    parser.add_argument("--start-dir", default="tests")
    parser.add_argument("--top-level-dir", default=".")
    parser.add_argument("modules", nargs="*",
                        help="explicit modules to run instead of "
                             "discovering the whole suite")
    args = parser.parse_args(argv)

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
    rc = run_shards(shards, args.top_level_dir)
    _emit("sharded run finished in %.1fs (exit %d)"
          % (time.monotonic() - started, rc))
    return rc


if __name__ == "__main__":
    sys.exit(main())
