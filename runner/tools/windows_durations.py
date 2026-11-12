#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Windows test durations: the measured table behind the split.

The build workflow's Windows leg used to shard the suite by
test COUNT (runner/tools/run_tests_parallel.py's LPT split).
Counts are a poor proxy on Windows, where a handful of files
carry most of the wall time: on 2026-11-10 the count split's
shard 2 was still running when the 20-minute hang guard
killed it (exit 124), on the attempt and on the rerun, while
its sibling shards finished in 6 to 12 minutes -- and that
one red leg held the release. The desk's answer (Q136 in
docs/steady/seats/questions.md) is the split this tool
implements: test FILES packed largest-first by their
measured Windows durations into shards budgeted at 12
minutes (720 seconds) against the standing 20-minute wall.
The wall is never raised; the budget is what moves.

The table (windows_durations.json, beside this tool) is a
checked-in fact like the figure slots: the workflow packs
from it, this tool refreshes it, and
runner/tests/test_windows_durations.py guards that the
checked-in table is canonical, names only real test files,
and packs within its budget. A file with no entry is not
forgotten: the packer weights it at the MEDIAN of the
table's values, computed at pack time, so a new file enters
conservatively (most files are small; the median says so)
and the packing stays total -- every discovered file lands
in exactly one shard.

How a duration is estimated from a build log, honestly: a
log carries, per shard, the shard's wall time and unittest's
own top-15 slowest-test list. A file's listed tests are
measured exactly. The shard's remaining wall (wall minus
the listed sum) is spread over the shard's files in
proportion to their unlisted test counts (or, when every
test in the shard is listed, over all its files by count)
-- an estimate, not a measurement, and it also absorbs
per-shard startup.
A shard the hang guard killed contributes its files at the
killed wall as a FLOOR: their true durations are larger,
by an amount no log records. When several logs are given,
a file keeps its LARGEST estimate across them. The seed
table was built this way from the two build-windows
attempts of the 2026-11-10 head build (both attempts of
the run whose shard 2 hit the wall), the only Windows logs
at hand when the split landed; it is refreshed the same
way from newer logs as they accumulate:

    python runner/tools/windows_durations.py --write \
        --from-logs test-windows.log

The drift rule rides with the table: if any shard exceeds
15 minutes on 2 consecutive main builds, refresh the table
from those builds' logs and land the refresh. --pack shows
the packing the workflow will run, per-shard totals
included, without running anything.
"""
import argparse
import json
import os
import re
import statistics
import sys

TABLE_NAME = "windows_durations.json"

# The Q136 numbers: shards are budgeted at 12 minutes
# against the standing 20-minute wall. The wall lives in
# the workflow (--wall-clock 20) and is never raised; the
# check below pins the pair so the two cannot drift apart
# silently.
BUDGET_SECONDS = 720.0
WALL_MINUTES = 20

# The bucket unittest discovery reports for modules that
# failed to import. It is not a file and never enters the
# table; at pack time it is just another unmeasured name
# and takes the median like any other.
LOADER_BUCKET = "unittest.loader"


def default_table_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        TABLE_NAME)


def repo_root():
    return os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))


def validate_table(table):
    """Check a parsed table's shape; return it normalized.

    Raises ValueError on anything the packer could not
    trust: a missing or non-positive budget, a duration
    that is not a finite non-negative number, a module name
    that is not a dotted string.
    """
    if not isinstance(table, dict):
        raise ValueError("the durations table is not an object")
    budget = table.get("budget_seconds")
    if not isinstance(budget, (int, float)) or isinstance(budget, bool) \
            or budget <= 0:
        raise ValueError("the durations table has no usable "
                         "budget_seconds")
    durations = table.get("durations")
    if not isinstance(durations, dict):
        raise ValueError("the durations table has no durations object")
    clean = {}
    for name, value in durations.items():
        if not isinstance(name, str) or not name:
            raise ValueError("a durations key is not a module name")
        if not isinstance(value, (int, float)) \
                or isinstance(value, bool) or value < 0 \
                or value != value or value in (float("inf"),
                                               float("-inf")):
            raise ValueError("duration for %s is not a finite "
                             "non-negative number" % name)
        clean[name] = float(value)
    return {"budget_seconds": float(budget), "durations": clean,
            "raw": table}


def load_table_file(path):
    with open(path, encoding="utf-8") as handle:
        return validate_table(json.load(handle))


def table_to_text(table):
    """The canonical text of a table dict: sorted keys, one
    entry per line, a trailing newline. The guard compares
    the checked-in file against this form, so a hand edit
    that reorders or reformats is caught like a stale one.
    """
    return json.dumps(table, indent=1, sort_keys=True) + "\n"


def default_duration(durations):
    """The weight of a file with no measurement: the median
    of the table's values, or 1.0 for an empty table."""
    if not durations:
        return 1.0
    return float(statistics.median(durations.values()))


def pack_modules(modules, durations, budget_seconds, default=None):
    """Pack module names into duration-balanced shards.

    Largest-first: modules are taken in (-weight, name)
    order and each joins the least-loaded shard (ties to
    the lowest index). The shard count is set by the total
    against the budget -- ceil(total / budget) -- so the
    load spreads evenly instead of filling one shard to
    the cap while the next stands empty. A module that
    fits in no open shard opens a new one rather than
    pushing a shard over budget, and a module heavier
    than the whole budget rides alone in an over-budget
    shard -- there is nowhere legal to put it, and
    dropping it would break totality. The result depends
    only on the weights and the budget, never on input
    order.
    """
    if budget_seconds <= 0:
        raise ValueError("the shard budget must be positive")
    for name, value in durations.items():
        if value < 0:
            raise ValueError("duration for %s is negative" % name)
    if default is None:
        default = default_duration(durations)
    weights = {name: float(durations.get(name, default))
               for name in modules}
    if not weights:
        return []
    total = sum(weights.values())
    count = min(len(weights),
                max(1, int(-(-total // budget_seconds))))
    shards = [[] for _ in range(count)]
    loads = [0.0] * count
    for name in sorted(weights, key=lambda n: (-weights[n], n)):
        weight = weights[name]
        if weight > budget_seconds:
            shards.append([name])
            loads.append(weight)
            continue
        best = None
        for index, load in enumerate(loads):
            if load + weight <= budget_seconds and (
                    best is None or load < loads[best]):
                best = index
        if best is None:
            shards.append([name])
            loads.append(weight)
        else:
            shards[best].append(name)
            loads[best] += weight
    # An over-budget file riding alone can leave a pre-opened
    # shard empty; an empty shard is not a shard (at runtime
    # it would run unittest with no modules named).
    return [shard for shard in shards if shard]


def shard_loads(shards, durations, default=None):
    if default is None:
        default = default_duration(durations)
    return [sum(float(durations.get(name, default)) for name in shard)
            for shard in shards]


# --- the log estimator -------------------------------------
#
# The lines the estimator reads are the parallel runner's
# own, inside the workflow log's step for it: the shard
# membership lines, the per-shard verdict lines, and
# unittest's slowest-tests block each passing shard prints.
# Workflow log lines carry the job, the step and a timestamp
# in tab-separated fields; a line from any other step is not
# this runner's evidence and is skipped. A bare shard log
# (no workflow fields) is accepted as-is.

_STEP_MARK = "run_tests_parallel"
_TIMESTAMP = re.compile(r"^\S+Z\s+")
_RUN_START = re.compile(r"^running (\d+) test\(s\) from (\d+) module\(s\)")
_SHARD_LIST = re.compile(r"^shard (\d+): (\d+) module\(s\): (.*)$")
_SHARD_OK = re.compile(r"^shard (\d+): OK in ([0-9.]+)s")
_SHARD_FAILED = re.compile(r"^=== shard (\d+) FAILED \(exit (-?\d+)\)")
_RUN_DONE = re.compile(r"^sharded run finished in ([0-9.]+)s")
_DURATION = re.compile(r"^([0-9.]+)s\s+\S+ \(([\w.]+)\)$")
_RAN = re.compile(r"^Ran (\d+) tests? in ([0-9.]+)s")


def _body(line):
    """The runner's own text from one log line, or None when
    the line belongs to another step of the workflow log. A job
    log fetched through the API carries no step fields, only the
    timestamp each line starts with; it is read as a bare shard
    log with the timestamp dropped (the refresh of 2026-11-12
    estimated nothing from three such logs before this)."""
    if "\t" in line:
        fields = line.split("\t", 2)
        if len(fields) == 3:
            if _STEP_MARK not in fields[1]:
                return None
            return _TIMESTAMP.sub("", fields[2]).strip()
    return _TIMESTAMP.sub("", line).strip()


def parse_log_text(text):
    """Parse one workflow log into its sharded runs.

    A run is {"total": seconds or None, "shards": {index:
    {"mods": [...], "listed": {module: seconds},
    "listed_n": {module: count}, "ran": seconds or None,
    "ok": seconds or None, "failed": bool}}}. Lines that
    match nothing are ignored: a log is evidence with noise
    in it, and the estimator's job is the signal.
    """
    runs = []
    run = None
    shard = None
    for raw in text.splitlines():
        body = _body(raw)
        if body is None:
            continue
        match = _RUN_START.match(body)
        if match:
            run = {"total": None, "shards": {}}
            runs.append(run)
            shard = None
            continue
        if run is None:
            continue
        match = _SHARD_LIST.match(body)
        if match:
            entry = run["shards"].setdefault(int(match.group(1)), {})
            entry["mods"] = [name.strip()
                              for name in match.group(3).split(",")]
            continue
        match = _SHARD_OK.match(body)
        if match:
            shard = int(match.group(1))
            run["shards"].setdefault(shard, {})["ok"] = \
                float(match.group(2))
            continue
        match = _SHARD_FAILED.match(body)
        if match:
            shard = int(match.group(1))
            run["shards"].setdefault(shard, {})["failed"] = True
            continue
        match = _RUN_DONE.match(body)
        if match:
            run["total"] = float(match.group(1))
            continue
        match = _DURATION.match(body)
        if match and shard is not None:
            module = match.group(2).rsplit(".", 2)[0]
            entry = run["shards"].setdefault(shard, {})
            listed = entry.setdefault("listed", {})
            listed[module] = listed.get(module, 0.0) \
                + float(match.group(1))
            listed_n = entry.setdefault("listed_n", {})
            listed_n[module] = listed_n.get(module, 0) + 1
            continue
        match = _RAN.match(body)
        if match and shard is not None:
            run["shards"].setdefault(shard, {})["ran"] = \
                float(match.group(2))
    return runs


def estimate_run(run, counts):
    """One run's per-file estimates, by the docstring's
    model: listed tests exact, the shard's remaining wall
    spread over its files by unlisted test count, a killed
    shard's files floored at the run's total wall."""
    fallback = float(statistics.median(counts.values())) if counts \
        else 1.0
    estimates = {}
    for entry in run["shards"].values():
        mods = entry.get("mods", [])
        if not mods:
            continue
        listed = entry.get("listed", {})
        listed_n = entry.get("listed_n", {})
        wall = entry.get("ran") or entry.get("ok")
        if wall is None and entry.get("failed"):
            wall = run.get("total")
        residual = max(0.0, (wall or 0.0) - sum(listed.values()))
        spread = {}
        for name in mods:
            unlisted = counts.get(name, fallback) \
                - listed_n.get(name, 0)
            spread[name] = max(0.0, float(unlisted))
        if not any(spread.values()):
            # Every test in the shard was listed; the
            # residual (startup, unlisted overhead) still
            # belongs to the shard's files, by count.
            spread = {name: float(counts.get(name, fallback))
                      for name in mods}
        denom = sum(spread.values())
        for name in mods:
            share = residual * spread[name] / denom if denom else 0.0
            estimates[name] = listed.get(name, 0.0) + share
    return estimates


def estimate_from_logs(texts, counts):
    """Per-file durations from several logs: each file
    keeps its largest estimate across every run parsed."""
    combined = {}
    for text in texts:
        for run in parse_log_text(text):
            for name, value in estimate_run(run, counts).items():
                if name == LOADER_BUCKET:
                    continue
                combined[name] = max(combined.get(name, 0.0), value)
    return {name: round(value, 1) for name, value in combined.items()}


def discover_counts(root):
    """Test counts per module, from the parallel runner's
    own discovery, so the estimator spreads residuals by
    exactly the counts the splitter itself sees."""
    sys.path.insert(0, os.path.join(root, "runner", "tools"))
    try:
        import run_tests_parallel
    finally:
        sys.path.pop(0)
    return run_tests_parallel.module_test_counts(
        os.path.join(root, "runner", "tests"), root)


def seed_header():
    return {
        "about": "Measured Windows durations per test file "
                 "(seconds), the table the build workflow's "
                 "Windows leg packs its shards from. See "
                 "runner/tools/windows_durations.py for how a "
                 "duration is estimated and refreshed, and "
                 "Q136 in docs/steady/seats/questions.md for "
                 "the decision. A file with no entry runs at "
                 "the median of these values.",
        "budget_seconds": BUDGET_SECONDS,
        "wall_minutes": WALL_MINUTES,
        "repack_rule": "If any shard exceeds 15 minutes on "
                       "2 consecutive main builds, refresh "
                       "this table from those builds' logs.",
    }


def _split_modules(root):
    """The modules runner/tools/split_modules.json names, or none."""
    path = os.path.join(root, "runner", "tools", "split_modules.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return set()
    modules = data.get("modules") if isinstance(data, dict) else None
    return set(m for m in (modules or []) if isinstance(m, str))


def _module_classes(root, module):
    """The test-class names of a module under runner/tests, read
    from its source without importing it (a class line at the left
    margin whose name ends in Test or starts with Test)."""
    parts = module.split(".")
    path = os.path.join(root, *parts) + ".py"
    classes = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                m = re.match(r"^class (\w+)\s*\(", line)
                if m and (m.group(1).endswith("Test") or m.group(1).startswith("Test")
                          or m.group(1).endswith("Tests")):
                    classes.append(m.group(1))
    except OSError:
        pass
    return classes


def check_table(root, path):
    """The guard's problems list for the checked-in table:
    canonical form, the Q136 numbers, every key a real test
    file, every packed shard within budget."""
    problems = []
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        table = validate_table(json.loads(text))
    except (OSError, ValueError) as exc:
        return ["the durations table does not load: %s" % exc]
    if table_to_text(json.loads(text)) != text:
        problems.append("the durations table is not in canonical "
                        "form; rewrite it with "
                        "windows_durations.py --write")
    raw = json.loads(text)
    if raw.get("budget_seconds") != BUDGET_SECONDS:
        problems.append("budget_seconds is %r, not the Q136 "
                        "budget %r" % (raw.get("budget_seconds"),
                                       BUDGET_SECONDS))
    if raw.get("wall_minutes") != WALL_MINUTES:
        problems.append("wall_minutes is %r, not the standing "
                        "wall %r" % (raw.get("wall_minutes"),
                                     WALL_MINUTES))
    durations = table["durations"]
    tests_dir = os.path.join(root, "runner", "tests")
    for name in durations:
        parts = name.split(".")
        if len(parts) != 3 or parts[:2] != ["runner", "tests"]:
            problems.append("%s is not a runner.tests module" % name)
            continue
        if not os.path.isfile(os.path.join(tests_dir,
                                           parts[2] + ".py")):
            problems.append("%s names no file in runner/tests" % name)
    # A module the split list names (runner/tools/split_modules.json)
    # rides as its classes at run time, each at its share of the
    # module's duration, so the module's own weight may exceed the
    # budget without any shard doing so; the check packs the list
    # the way the leg runs it -- a split module stands for a share
    # of itself per listed class, never for one item.
    split = _split_modules(root)
    items = {}
    for name in durations:
        if name in split:
            classes = _module_classes(root, name)
            share = float(durations[name]) / max(1, len(classes))
            for cls in classes:
                items["%s.%s" % (name, cls)] = share
        else:
            items[name] = durations[name]
    shards = pack_modules(sorted(items), items, table["budget_seconds"])
    for index, load in enumerate(shard_loads(shards, items)):
        if load > table["budget_seconds"]:
            problems.append("shard %d packs %.1fs over the %.0fs "
                            "budget" % (index, load,
                                        table["budget_seconds"]))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Pack, check or refresh the Windows test "
                    "durations table.")
    parser.add_argument("--table", default=default_table_path(),
                        help="the table file (default: %(default)s)")
    parser.add_argument("--check", action="store_true",
                        help="verify the checked-in table and exit")
    parser.add_argument("--write", action="store_true",
                        help="refresh the table from --from-logs "
                             "and write it")
    parser.add_argument("--from-logs", nargs="*", default=[],
                        metavar="LOG",
                        help="workflow logs to estimate durations "
                             "from (with --write)")
    parser.add_argument("--pack", action="store_true",
                        help="print the packing the workflow "
                             "would run from the table")
    args = parser.parse_args(argv)
    root = repo_root()

    if args.check:
        problems = check_table(root, args.table)
        for problem in problems:
            print("windows-durations: %s" % problem, file=sys.stderr)
        if problems:
            return 1
        print("windows-durations: the table is canonical and "
              "packs within budget")
        return 0

    if args.write:
        if not args.from_logs:
            print("windows-durations: --write needs --from-logs",
                  file=sys.stderr)
            return 2
        texts = []
        for log_path in args.from_logs:
            with open(log_path, encoding="utf-8",
                      errors="replace") as handle:
                texts.append(handle.read())
        fresh = estimate_from_logs(texts, discover_counts(root))
        if not fresh:
            print("windows-durations: no durations estimated "
                  "from the given logs", file=sys.stderr)
            return 2
        durations = dict(fresh)
        if os.path.exists(args.table):
            try:
                prior = load_table_file(args.table)["durations"]
            except (OSError, ValueError):
                prior = {}
            for name, value in prior.items():
                durations.setdefault(name, value)
        table = seed_header()
        table["durations"] = durations
        with open(args.table, "w", encoding="utf-8") as handle:
            handle.write(table_to_text(table))
        print("windows-durations: wrote %d durations to %s"
              % (len(durations), args.table))
        return 0

    if args.pack:
        table = load_table_file(args.table)
        counts = discover_counts(root)
        shards = pack_modules(sorted(counts), table["durations"],
                              table["budget_seconds"])
        loads = shard_loads(shards, table["durations"])
        measured = set(table["durations"])
        for index, shard in enumerate(shards):
            missing = [name for name in shard if name not in measured]
            print("shard %d: %d module(s), %.0fs packed%s"
                  % (index, len(shard), loads[index],
                     ", %d at the median default" % len(missing)
                     if missing else ""))
        print("%d shard(s), budget %.0fs, wall %d minutes"
              % (len(shards), table["budget_seconds"], WALL_MINUTES))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
