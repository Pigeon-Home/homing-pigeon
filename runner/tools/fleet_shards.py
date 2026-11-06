#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Cross-rig suite sharding: manifest, shard worker, and merger.

The single-machine parallel runner (runner/tools/run_tests_parallel.py)
already discovers the suite census and splits it by measured test
count. This module carries that split across machines:

- ``manifest`` writes one JSON manifest for a pinned head: the full
  census it discovered (module names with their test counts) and,
  per rig, the module list that rig must run. The split is the same
  longest-processing-time greedy pass, weighted by each rig's speed
  so a faster rig is handed proportionally more test count.
- ``worker`` runs ONE module in-process with a recording test result
  and emits that module's JSON object. An import failure is an error
  entry in the object, never a silent crash; a module that raises
  SkipTest at import (a platform skip) is a skipped entry, not an
  error. The worker inserts the tree root into sys.path itself, so
  it runs under an embeddable Python whose ``._pth`` file pins
  sys.path (the shape plain ``-m unittest`` cannot survive on such
  an interpreter). Extra module directories travel as ``--path``
  arguments, never as PYTHONPATH: an embeddable Python in its
  isolated layout ignores that variable entirely.
- ``run-shard`` runs every module a manifest assigns to one rig,
  one worker subprocess per module, and writes the shard-result
  file: schema 1, the pinned head, the rig's name, platform and
  Python, the module objects, and their summed totals.
- ``merge`` reads a manifest and a directory of shard-result files
  and prints one verdict. It fails loudly, naming the modules, when
  any result names a different head, when the union of result
  modules is not the census exactly (missing, extra, or duplicated
  modules), when a result's totals do not match its own modules, or
  when any test failed or errored.

Usage:
    python runner/tools/fleet_shards.py manifest --head SHA
        --rig menlo=1 --rig germany=4 --out manifest.json
    python runner/tools/fleet_shards.py worker MODULE [--out FILE]
        [--path DIR ...]
    python runner/tools/fleet_shards.py run-shard --manifest M
        --rig NAME --jobs 4 --out result.json
    python runner/tools/fleet_shards.py merge --manifest M
        --results-dir DIR
"""

import argparse
import concurrent.futures
import datetime
import importlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import unittest

SCHEMA = 1

# The tree root is three levels up from this file
# (runner/tools/<this file>), and the worker must find it without
# any help from the interpreter's path setup: an embeddable
# Python's ``._pth`` pins sys.path to its own folder.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_parallel_runner():
    """The sibling census/LPT machinery, loaded by path.

    Loading by path works the same as a plain script, as a package
    module, and under an embeddable Python: no import root for the
    tools folder is assumed.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "run_tests_parallel.py")
    spec = importlib.util.spec_from_file_location(
        "run_tests_parallel", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def split_weighted(counts, rig_weights):
    """LPT split of {module: test_count} across weighted rigs.

    ``rig_weights`` is a list of (name, weight) pairs in the order
    the rigs were named. Returns a list of (name, weight, modules)
    triples in that same order, one per rig — a rig that is handed
    nothing still appears, with an empty module list. Every module
    appears in exactly one rig's list.

    Each module, considered in (-count, name) order, goes to the
    rig whose current load is smallest relative to its share of
    the total load (load / target, target proportional to weight).
    With equal weights this is exactly the unweighted greedy split
    in run_tests_parallel.shard_modules. A zero-weight rig is
    handed nothing; a run where every weight is zero is refused.
    """
    rigs = [(str(name), float(weight)) for name, weight in rig_weights]
    names = [name for name, _w in rigs]
    if len(set(names)) != len(names):
        raise ValueError("rig names must be unique: %r" % (names,))
    if any(weight < 0 for _n, weight in rigs):
        raise ValueError("rig weights must be >= 0")
    if counts and not rigs:
        raise ValueError("no rigs to split the census across")
    if counts and not any(weight > 0 for _n, weight in rigs):
        raise ValueError("at least one rig weight must be > 0")
    total_weight = sum(weight for _n, weight in rigs)
    total_load = sum(counts.values())
    targets = [(total_load * weight / total_weight if total_weight else 0.0)
               for _n, weight in rigs]
    loads = [0.0] * len(rigs)
    modules = [[] for _ in rigs]

    def underness(i):
        if targets[i] <= 0:
            return float("inf")
        return loads[i] / targets[i]

    for mod, count in sorted(counts.items(),
                             key=lambda kv: (-kv[1], kv[0])):
        idx = min(range(len(rigs)), key=lambda i: (underness(i), i))
        modules[idx].append(mod)
        loads[idx] += count
    return [(name, weight, mods)
            for (name, weight), mods in zip(rigs, modules)]


def build_manifest(head, counts, rig_weights, created_utc=None):
    """The manifest dict for a pinned head and a census.

    The census is carried whole (names sorted, with their test
    counts) so the merger can prove the shards together covered
    exactly it, and each rig's share is named beside it.
    """
    split = split_weighted(counts, rig_weights)
    return {
        "schema": SCHEMA,
        "head": head,
        "created_utc": created_utc or _utc_now(),
        "census": sorted(counts),
        "census_counts": {name: counts[name] for name in sorted(counts)},
        "total_tests": sum(counts.values()),
        "rigs": [{"rig": name, "weight": weight, "modules": mods}
                 for name, weight, mods in split],
    }


class RecordingResult(unittest.TestResult):
    """A TestResult that records failing and erroring test ids."""

    def __init__(self):
        super().__init__()
        self.failure_ids = []
        self.error_ids = []

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.failure_ids.append(test.id())

    def addError(self, test, err):
        super().addError(test, err)
        self.error_ids.append(test.id())


def run_module(module_name):
    """Run one module in-process; return its shard JSON object.

    An import failure becomes one error entry naming the module —
    the run counts 1 test run and 1 error, so the module can never
    vanish silently from a shard's totals.
    """
    started = time.monotonic()
    try:
        module = importlib.import_module(module_name)
    except unittest.SkipTest:
        # A module that skips itself at import (a platform gate)
        # is one skipped test, the shape discovery reports — not
        # an error.
        return {
            "module": module_name,
            "ran": 1,
            "failures": [],
            "errors": [],
            "skipped": 1,
            "seconds": round(time.monotonic() - started, 3),
        }
    except Exception:
        return {
            "module": module_name,
            "ran": 1,
            "failures": [],
            "errors": [module_name],
            "skipped": 0,
            "seconds": round(time.monotonic() - started, 3),
        }
    suite = unittest.TestLoader().loadTestsFromModule(module)
    result = RecordingResult()
    suite.run(result)
    return {
        "module": module_name,
        "ran": result.testsRun,
        "failures": result.failure_ids,
        "errors": result.error_ids,
        "skipped": len(result.skipped),
        "seconds": round(time.monotonic() - started, 3),
    }


def totals_of(module_objects):
    """The shard totals summed over module objects."""
    return {
        "modules": len(module_objects),
        "ran": sum(m["ran"] for m in module_objects),
        "failures": sum(len(m["failures"]) for m in module_objects),
        "errors": sum(len(m["errors"]) for m in module_objects),
        "skipped": sum(m["skipped"] for m in module_objects),
    }


def build_shard_result(head, rig, jobs, module_objects,
                       started_utc, wall_seconds):
    """A schema-1 shard-result dict over finished module objects."""
    ordered = sorted(module_objects, key=lambda m: m["module"])
    return {
        "schema": SCHEMA,
        "head": head,
        "rig": rig,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "jobs": jobs,
        "started_utc": started_utc,
        "wall_seconds": round(wall_seconds, 3),
        "modules": ordered,
        "totals": totals_of(ordered),
    }


def _worker_command(module_name, out_path, extra_paths=()):
    command = [sys.executable, os.path.abspath(__file__), "worker",
               module_name, "--out", out_path]
    for path in extra_paths:
        command += ["--path", path]
    return command


def _run_one_worker(module_name, work_dir, extra_paths=()):
    """One worker subprocess; a hard crash becomes an error entry.

    The worker itself turns import failures into error entries, so
    this fallback is only for a worker that died before it could
    write its object at all (killed, interpreter crash): the module
    still appears, as an error, and the census check stays honest.
    """
    out_path = os.path.join(
        work_dir, module_name.replace("/", "_").replace("\\", "_")
        + ".json")
    started = time.monotonic()
    try:
        subprocess.run(_worker_command(module_name, out_path,
                                       extra_paths),
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except Exception:
        pass
    try:
        with open(out_path, encoding="utf-8") as fh:
            obj = json.load(fh)
        if obj.get("module") != module_name:
            raise ValueError("worker named a different module")
        return obj
    except Exception:
        return {
            "module": module_name,
            "ran": 1,
            "failures": [],
            "errors": [module_name],
            "skipped": 0,
            "seconds": round(time.monotonic() - started, 3),
        }


def run_shard(manifest, rig_name, jobs, extra_paths=()):
    """Run one rig's manifest share; return the shard-result dict.

    ``extra_paths`` are directories the worker subprocesses insert
    into sys.path (forwarded as --path arguments, so they reach an
    embeddable Python that ignores PYTHONPATH).
    """
    shares = {entry["rig"]: entry["modules"]
              for entry in manifest["rigs"]}
    if rig_name not in shares:
        raise ValueError("rig %r is not in the manifest (rigs: %s)"
                         % (rig_name, ", ".join(sorted(shares))))
    modules = shares[rig_name]
    started_utc = _utc_now()
    started = time.monotonic()
    objects = []
    kwargs = {}
    if sys.version_info >= (3, 10):
        kwargs["ignore_cleanup_errors"] = True
    with tempfile.TemporaryDirectory(prefix="hp-fleet-shard-",
                                     **kwargs) as work_dir:
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, jobs)) as pool:
            objects = list(pool.map(
                lambda name: _run_one_worker(name, work_dir,
                                             extra_paths),
                modules))
    return build_shard_result(manifest["head"], rig_name, jobs, objects,
                              started_utc, time.monotonic() - started)


def merge_results(manifest, results):
    """Check shard results against a manifest; return (ok, lines).

    The checks, in order: every result is schema 1 and names the
    manifest head; every result's totals match the sum of its own
    modules; the union of result modules is the census exactly —
    missing, extra, and duplicated modules are each named. The
    summed totals and every failing/erroring test id are reported
    either way. ``ok`` is False when any check fails or any test
    failed or errored.
    """
    problems = []
    census = list(manifest.get("census") or [])
    census_set = set(census)
    seen = {}
    totals = {"modules": 0, "ran": 0, "failures": 0,
              "errors": 0, "skipped": 0}
    failing = []
    for result in results:
        rig = result.get("rig", "?")
        if result.get("schema") != SCHEMA:
            problems.append("rig %s: schema is %r, expected %d"
                            % (rig, result.get("schema"), SCHEMA))
        if result.get("head") != manifest.get("head"):
            problems.append("rig %s: head %r does not match the "
                            "manifest head %r"
                            % (rig, result.get("head"),
                               manifest.get("head")))
        objects = result.get("modules") or []
        summed = totals_of(objects)
        if result.get("totals") != summed:
            problems.append("rig %s: totals %r do not match its "
                            "modules' sum %r"
                            % (rig, result.get("totals"), summed))
        for key in totals:
            totals[key] += summed[key]
        for obj in objects:
            seen[obj["module"]] = seen.get(obj["module"], 0) + 1
            failing.extend(obj.get("failures") or [])
            failing.extend(obj.get("errors") or [])
    missing = sorted(census_set - set(seen))
    extra = sorted(set(seen) - census_set)
    duplicated = sorted(name for name, n in seen.items() if n > 1)
    if missing:
        problems.append("missing modules: %s" % ", ".join(missing))
    if extra:
        problems.append("extra modules: %s" % ", ".join(extra))
    if duplicated:
        problems.append("duplicated modules: %s"
                        % ", ".join(duplicated))
    lines = [
        "census: %d module(s); results: %d module(s) from %d rig(s)"
        % (len(census), totals["modules"], len(results)),
        "totals: ran=%d failures=%d errors=%d skipped=%d"
        % (totals["ran"], totals["failures"], totals["errors"],
           totals["skipped"]),
    ]
    if failing:
        lines.append("failing/erroring tests: %s" % ", ".join(failing))
    for problem in problems:
        lines.append("CHECK FAILED: %s" % problem)
    ok = not problems and totals["failures"] == 0 and totals["errors"] == 0
    lines.append("verdict: %s" % ("OK" if ok else "FAILED"))
    return ok, lines


def _write_json(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _parse_rig(text):
    name, sep, weight = text.partition("=")
    if not sep or not name:
        raise argparse.ArgumentTypeError(
            "rig must be NAME=WEIGHT, got %r" % (text,))
    try:
        return (name, float(weight))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "rig weight must be a number, got %r" % (text,))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_manifest = sub.add_parser(
        "manifest", help="write a shard manifest for a pinned head")
    p_manifest.add_argument("--head", required=True)
    p_manifest.add_argument("--rig", action="append", required=True,
                            type=_parse_rig, metavar="NAME=WEIGHT",
                            help="one per rig; repeat for each rig")
    p_manifest.add_argument("--out", required=True)
    p_manifest.add_argument("--start-dir", default="runner/tests")
    p_manifest.add_argument("--top-level-dir", default=".")

    p_worker = sub.add_parser(
        "worker", help="run one module in-process, emit its JSON object")
    p_worker.add_argument("module")
    p_worker.add_argument("--out", help="write the object here "
                                        "instead of stdout")
    p_worker.add_argument("--path", action="append", default=[],
                          metavar="DIR",
                          help="insert DIR into sys.path before "
                               "importing the module; repeatable")

    p_shard = sub.add_parser(
        "run-shard", help="run one rig's manifest share")
    p_shard.add_argument("--manifest", required=True)
    p_shard.add_argument("--rig", required=True)
    p_shard.add_argument("--jobs", type=int, default=1)
    p_shard.add_argument("--out", required=True)
    p_shard.add_argument("--path", action="append", default=[],
                         metavar="DIR",
                         help="forward DIR to every worker's "
                              "sys.path; repeatable")

    p_merge = sub.add_parser(
        "merge", help="merge shard results against a manifest")
    p_merge.add_argument("--manifest", required=True)
    p_merge.add_argument("--results-dir", required=True)

    args = parser.parse_args(argv)

    if args.command == "manifest":
        counts = _load_parallel_runner().module_test_counts(
            args.start_dir, args.top_level_dir)
        if not counts:
            print("error: no tests discovered under %s -- refusing "
                  "to write a vacuous manifest" % args.start_dir,
                  file=sys.stderr)
            return 2
        manifest = build_manifest(args.head, counts, args.rig)
        _write_json(manifest, args.out)
        print("manifest: %d module(s), %d test(s), %d rig(s) -> %s"
              % (len(manifest["census"]), manifest["total_tests"],
                 len(manifest["rigs"]), args.out))
        return 0

    if args.command == "worker":
        for path in reversed(args.path):
            if path not in sys.path:
                sys.path.insert(0, path)
        obj = run_module(args.module)
        if args.out:
            _write_json(obj, args.out)
        else:
            print(json.dumps(obj, indent=2, sort_keys=True))
        return 0

    if args.command == "run-shard":
        if args.jobs < 1:
            parser.error("--jobs must be >= 1")
        manifest = _read_json(args.manifest)
        try:
            result = run_shard(manifest, args.rig, args.jobs,
                               extra_paths=args.path)
        except ValueError as exc:
            print("error: %s" % (exc,), file=sys.stderr)
            return 2
        _write_json(result, args.out)
        print("shard %s: %d module(s), ran=%d failures=%d errors=%d "
              "in %.1fs -> %s"
              % (args.rig, result["totals"]["modules"],
                 result["totals"]["ran"], result["totals"]["failures"],
                 result["totals"]["errors"], result["wall_seconds"],
                 args.out))
        return 0

    if args.command == "merge":
        manifest = _read_json(args.manifest)
        results = []
        for name in sorted(os.listdir(args.results_dir)):
            if name.endswith(".json"):
                results.append(_read_json(
                    os.path.join(args.results_dir, name)))
        if not results:
            print("error: no shard-result JSON files in %s"
                  % args.results_dir, file=sys.stderr)
            return 2
        ok, lines = merge_results(manifest, results)
        for line in lines:
            print(line)
        return 0 if ok else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
