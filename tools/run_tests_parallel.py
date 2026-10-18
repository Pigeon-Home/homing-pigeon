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


def run_shards(shards, top_level_dir):
    """Run each shard as a unittest subprocess; return exit code.

    Output is captured per shard and printed when the shard
    finishes (full output for failures, the unittest summary tail
    for passes), so the CI log stays readable without interleaving
    four workers' dots into soup.
    """
    procs = []
    with tempfile.TemporaryDirectory(prefix="hp-test-shards-") as tmp:
        for i, shard in enumerate(shards):
            out_path = os.path.join(tmp, "shard-%d.log" % i)
            fh = open(out_path, "wb")
            proc = subprocess.Popen(
                [sys.executable, "-m", "unittest"] + shard,
                cwd=top_level_dir, stdout=fh, stderr=subprocess.STDOUT)
            procs.append((i, shard, proc, fh, out_path))
            print("shard %d: %d module(s): %s"
                  % (i, len(shard), ", ".join(shard)), flush=True)
        failed = []
        for i, shard, proc, fh, out_path in procs:
            rc = proc.wait()
            fh.close()
            with open(out_path, encoding="utf-8", errors="replace") as rf:
                output = rf.read()
            if rc != 0:
                failed.append(i)
                print("=== shard %d FAILED (exit %d) ===\n%s"
                      % (i, rc, output), flush=True)
            else:
                tail = "\n".join(output.strip().splitlines()[-4:])
                print("shard %d: OK\n%s" % (i, tail), flush=True)
    if failed:
        print("FAILED shard(s): %s" % ", ".join(str(i) for i in failed))
        return 1
    return 0


def main(argv=None):
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
    print("running %d test(s) from %d module(s) in %d shard(s)"
          % (total, len(counts), len(shards)), flush=True)
    started = time.monotonic()
    rc = run_shards(shards, args.top_level_dir)
    print("sharded run finished in %.1fs (exit %d)"
          % (time.monotonic() - started, rc))
    return rc


if __name__ == "__main__":
    sys.exit(main())
