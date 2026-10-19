#!/usr/bin/env python3
"""Run the test suite in a shuffled order.

    python tools/run_tests_shuffled.py [--seed N] [--pattern 'test_*.py']

unittest's discovery order is deterministic (alphabetical by
module, then by class, then by method), and a suite that only
ever runs in that order can hide cross-test pollution: a module
that leaks a global, a file, an env var, or a patch and relies
on an alphabetically-later module never noticing. This runner
flattens the discovered suite and shuffles the individual test
cases with a seeded Random, so a pollution failure reproduces
from the seed alone.

setUpClass/tearDownClass still run per class (unittest groups
by class when the suite is rebuilt), so what shuffles is the
order classes and standalone cases execute in -- the realistic
shape of the parallel shard runner in CI, which also reorders
whole classes across processes.
"""
import argparse
import random
import unittest


def _flatten(suite):
    out = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            out.extend(_flatten(item))
        else:
            out.append(item)
    return out


def shuffled_suite(suite, seed):
    cases = _flatten(suite)
    random.Random(seed).shuffle(cases)
    # Rebuild grouped by class so class fixtures run once per
    # class, in the shuffled class order.
    grouped = {}
    order = []
    for case in cases:
        cls = type(case)
        if cls not in grouped:
            grouped[cls] = []
            order.append(cls)
        grouped[cls].append(case)
    rebuilt = unittest.TestSuite()
    for cls in order:
        rebuilt.addTests(grouped[cls])
    return rebuilt


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the suite with shuffled test order.")
    parser.add_argument("--seed", type=int, default=20261019)
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--start-dir", default="tests")
    parser.add_argument("--top-level", default=".")
    args = parser.parse_args(argv)

    loader = unittest.TestLoader()
    suite = loader.discover(args.start_dir, pattern=args.pattern,
                            top_level_dir=args.top_level)
    if suite.countTestCases() == 0:
        print("shuffle: discovery came up empty")
        return 1
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(shuffled_suite(suite, args.seed))
    print(f"shuffle(seed={args.seed}): {result.testsRun} tests, "
          f"{len(result.failures)} failures, {len(result.errors)} errors, "
          f"{len(result.skipped)} skipped")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
