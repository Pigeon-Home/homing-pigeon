#!/usr/bin/env python3
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
"""Refuse a mutation run whose signal collapsed.

    python runner/tools/mutation_floor.py [--mutants-dir mutants]
        [--min-mutants 100] [--min-functions 6] [--annotate]

mutmut exits 0 whenever its machinery ran, however little it
measured. On 2026-10-25 a run over runner/guard/security.py produced
three mutants where the same configuration had produced 443 (Q22):
pytest's collection failed on two archived files with one basename,
`-x` ended mutmut's coverage pass before a single test ran, mutmut
ignored that pass's exit code, and `mutate_only_covered_lines` then
kept only the import-time lines. Every survivor was triaged, the run
was green, and the signal was blind.

This reads what mutmut wrote -- `mutmut-stats.json` (which tests
reached which function) and every `*.meta` file (each mutant's
result) -- and fails when the run is below the floor: fewer mutants
than --min-mutants, or fewer functions with tests than
--min-functions. It also prints the tally (killed, survived, no
tests, timeout, suspicious, skipped) so the log reads the result
without the TUI. Stdlib only.
"""

import argparse
import glob
import json
import os
import sys

# mutmut 3's exit-code meanings (mutmut/stats.py: status_by_exit_code).
_STATUS = {1: "killed", 3: "killed", 0: "survived", 5: "no tests",
           33: "no tests", 34: "skipped", 35: "suspicious", 36: "timeout",
           37: "caught by type check", 2: "interrupted", None: "not checked",
           -24: "timeout", 24: "timeout", 152: "timeout", 255: "timeout",
           -11: "segfault", -9: "segfault"}


def read_run(mutants_dir):
    stats_path = os.path.join(mutants_dir, "mutmut-stats.json")
    functions_with_tests = 0
    tests_total = 0
    try:
        with open(stats_path, encoding="utf-8") as fh:
            stats = json.load(fh)
        by_function = stats.get("tests_by_mangled_function_name", {})
        functions_with_tests = sum(1 for v in by_function.values() if v)
        tests_total = len(stats.get("duration_by_test", {}))
    except (OSError, ValueError):
        stats = None
    tally = {}
    mutants = 0
    files = sorted(glob.glob(os.path.join(mutants_dir, "**", "*.meta"),
                             recursive=True))
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            continue
        for code in meta.get("exit_code_by_key", {}).values():
            mutants += 1
            status = _STATUS.get(code, "suspicious")
            tally[status] = tally.get(status, 0) + 1
    return {"stats_found": stats is not None,
            "functions_with_tests": functions_with_tests,
            "tests_total": tests_total, "meta_files": len(files),
            "mutants": mutants, "tally": tally}


def judge(run, min_mutants, min_functions):
    """The list of floor breaches, empty when the run is sound."""
    problems = []
    if not run["stats_found"]:
        problems.append("no mutmut-stats.json: the stats phase did not run")
    if run["mutants"] < min_mutants:
        problems.append("%d mutants generated, floor is %d" % (
            run["mutants"], min_mutants))
    if run["functions_with_tests"] < min_functions:
        problems.append("%d functions reached by tests, floor is %d" % (
            run["functions_with_tests"], min_functions))
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mutants-dir", default="mutants")
    ap.add_argument("--min-mutants", type=int, default=100)
    ap.add_argument("--min-functions", type=int, default=6)
    ap.add_argument("--annotate", action="store_true")
    a = ap.parse_args(argv)
    run = read_run(a.mutants_dir)
    tally = ", ".join("%s %d" % (k, v) for k, v in sorted(run["tally"].items()))
    summary = ("mutation run: %d mutants in %d files (%s); %d functions "
               "reached by %d tests" % (
                   run["mutants"], run["meta_files"], tally or "none",
                   run["functions_with_tests"], run["tests_total"]))
    print(summary)
    problems = judge(run, a.min_mutants, a.min_functions)
    if a.annotate:
        print("::notice title=mutation::" + summary)
    if not problems:
        return 0
    why = ("; ".join(problems) + ". The signal collapsed, not the code: "
           "most often pytest's collection or an early test failed inside "
           "the mutants tree under -x, and mutmut's coverage pass ignores "
           "that exit code. Reproduce with `cd mutants && python -m pytest "
           "-x -q runner/tests/` and fix what stops it (Q22).")
    print("MUTATION FLOOR: " + why)
    if a.annotate:
        print("::error title=mutation signal collapsed::" + why[:900])
    return 1


if __name__ == "__main__":
    sys.exit(main())
