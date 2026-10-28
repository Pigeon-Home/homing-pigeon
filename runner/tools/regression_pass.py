#!/usr/bin/env python3
# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""One regression pass on the rig: the suite, the culprit, the ledger line.

    python runner/tools/regression_pass.py [--pull] [--jobs N] [--repeat 3]
                                           [--state-dir DIR] [--no-bisect]

The campaign's hourly regression pass used to end at "red" and a
guess. This pass ends at a verdict: the whole suite runs in parallel
shards on the current head; a red is re-run alone --repeat times and
classified (a failure that passes once is a flake, a failure that
never passes is deterministic); each deterministic failure is then
bisected between the last green head this rig recorded and the
current head, the failing tests alone, in a temporary worktree per
step, so the first bad commit is named -- or, when the test did not
exist before the commit that added it, that commit is named as the
one the test has been red since. The result is one ledger line for
the standing orders and, on red, a paragraph ready to paste under a
Q in docs/use/questions.md with the reproduce command.

The rig's own state lives outside the tree, under --state-dir
(default ~/.cache/homing-pigeon/regression/): the last green head
and a JSON record per pass. The proof of the work lives in the
tree: every pass appends one line to --record (default
docs/reports/regression/passes.jsonl) -- the head, the test count,
the wall time, the failing ids, the flake split, the culprits and
the ledger line -- which the campaign commits with the ledger
line. A pass that cannot run (a dirty tree under --pull, a pull
that fails, a suite that does not start) says so in the same
shape, a NOT RUN ledger line and a record, never a traceback.
Exit 0 green, 1 deterministic red, 3 flakes only, 2 not run.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
REPO = ROOT   # the repository the pass runs in (tests point it elsewhere)
STAMP = "50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f"
RECORD = os.path.join("docs", "reports", "regression", "passes.jsonl")
_RAN = re.compile(r"^Ran (\d+) tests? in", re.M)
_RED = re.compile(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)", re.M)
_MISSING = re.compile(r"No module named '([A-Za-z_][\w.]*)'")
_LOADER = "unittest.loader._FailedTest."


# ------------------------------------------------------------------
# git and subprocess helpers
# ------------------------------------------------------------------

def git(*args, cwd=None, check=True):
    proc = subprocess.run(["git"] + list(args), cwd=cwd or REPO,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=600)
    if check and proc.returncode != 0:
        raise RuntimeError("git %s: %s" % (
            " ".join(args), proc.stderr.decode("utf-8", "replace").strip()))
    return proc.stdout.decode("utf-8", "replace").strip()


def run_python(args, cwd=None, timeout=7200):
    env = dict(os.environ)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    try:
        proc = subprocess.run([sys.executable] + list(args), cwd=cwd or REPO,
                              env=env,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out = (e.output or b"").decode("utf-8", "replace")
        return 124, out + f"\n[timed out after {timeout}s]\n"
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


# ------------------------------------------------------------------
# reading a suite run
# ------------------------------------------------------------------

def failing_ids(output):
    """The unittest ids that failed or errored in a run's output, in
    order of first appearance; a module that failed to import is
    reported as its runner.tests module name."""
    seen = []
    for _kind, name, dotted in _RED.findall(output):
        if dotted.startswith(_LOADER):
            ident = "runner.tests." + name
        else:
            ident = dotted
        if ident not in seen:
            seen.append(ident)
    return seen


def missing_dependency(output):
    """The third-party module a run could not import, or None. A test
    that cannot start because this box lacks a package the CI pins
    (`hypothesis`, say) is not a regression of the code: the pass
    names it as not run here instead of red. A missing `runner`
    module is the code's own and stays red."""
    for name in _MISSING.findall(output or ""):
        top = name.split(".")[0]
        if top != "runner":
            return top
    return None


def tests_ran(output):
    return sum(int(n) for n in _RAN.findall(output))


# ------------------------------------------------------------------
# the pass
# ------------------------------------------------------------------

def default_state_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache")
    return os.path.join(base, "homing-pigeon", "regression")


class State:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.join(path, "runs"), exist_ok=True)
        self.file = os.path.join(path, "last_green.json")

    def last_green(self):
        try:
            with open(self.file, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def record_green(self, sha, tests):
        data = {"sha": sha, "tests": tests,
                "when": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")}
        tmp = self.file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, self.file)

    def record_run(self, record):
        name = "%s-%s.json" % (record["sha"][:8],
                               time.strftime("%Y%m%dT%H%M%S", time.gmtime()))
        path = os.path.join(self.path, "runs", name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=1, sort_keys=True)
        return path


def append_record(path, record):
    """One line per pass in the tree, a stamped header on the first."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        if new:
            fh.write(json.dumps({"regression": 1, "file": "passes",
                                 "Agent-Stamp": STAMP},
                                ensure_ascii=True) + "\n")
        fh.write(json.dumps(record, ensure_ascii=True, sort_keys=True)
                 + "\n")


def run_suite(jobs, timeout):
    args = ["runner/tools/run_tests_parallel.py"]
    if jobs:
        args += ["--jobs", str(jobs)]
    return run_python(args, timeout=timeout)


def rerun(ids, times, cwd=None, outputs=None):
    """{id: [passed?, ...]} for `times` lone runs of the failing tests
    (a module that failed to import is run as the module). When
    `outputs` is a dict, each test's last lone output lands in it."""
    results = {i: [] for i in ids}
    for _ in range(times):
        for ident in ids:
            rc, out = run_python(["-m", "unittest", ident], cwd=cwd,
                                 timeout=1800)
            results[ident].append(rc == 0 and not failing_ids(out))
            if outputs is not None:
                outputs[ident] = out
    return results


def classify(results):
    flaky = sorted(i for i, runs in results.items() if any(runs))
    deterministic = sorted(i for i, runs in results.items()
                           if runs and not any(runs))
    return deterministic, flaky


class Worktree:
    def __init__(self, sha):
        self.sha = sha
        self.path = tempfile.mkdtemp(prefix="hp-regress-")

    def __enter__(self):
        git("worktree", "add", "--detach", self.path, self.sha)
        return self.path

    def __exit__(self, *exc):
        try:
            git("worktree", "remove", "--force", self.path, check=False)
        finally:
            shutil.rmtree(self.path, ignore_errors=True)
        return False


def _module_file(ident):
    parts = ident.split(".")
    if len(parts) >= 3 and parts[0] == "runner" and parts[1] == "tests":
        return os.path.join("runner", "tests", parts[2] + ".py")
    return None


def is_red_at(sha, ids):
    """True when the failing tests fail at `sha`. A test whose module
    does not exist there is not red there: the bisect then lands on
    the commit that added it, which is what the ledger should say."""
    with Worktree(sha) as tree:
        present = [i for i in ids
                   if _module_file(i) is None
                   or os.path.exists(os.path.join(tree, _module_file(i)))]
        if not present:
            return False
        rc, out = run_python(["-m", "unittest"] + present, cwd=tree,
                             timeout=1800)
        return rc != 0 or bool(failing_ids(out))


def is_ancestor(good, sha):
    proc = subprocess.run(["git", "merge-base", "--is-ancestor", good, sha],
                          cwd=REPO, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=600)
    return proc.returncode == 0


def bisect(good, bad, ids, log=None):
    """The first commit on the first-parent line from good (exclusive)
    to bad (inclusive) at which the tests are red, assuming they are
    red at bad and green at good. Returns (sha, subject, steps)."""
    commits = git("rev-list", "--first-parent", "--reverse",
                  f"{good}..{bad}").split()
    if not commits:
        return None, "", 0
    lo, hi, steps = 0, len(commits) - 1, 0
    while lo < hi:
        mid = (lo + hi) // 2
        steps += 1
        red = is_red_at(commits[mid], ids)
        if log:
            log(f"  bisect step {steps}: {commits[mid][:8]} is "
                f"{'red' if red else 'green'}")
        if red:
            hi = mid
        else:
            lo = mid + 1
    sha = commits[lo]
    return sha, git("log", "-1", "--format=%s", sha), steps


def _unavailable_part(unavailable):
    mods = sorted(set(unavailable.values()))
    return (f"{len(unavailable)} not run here (missing "
            f"{', '.join(mods)}): {', '.join(sorted(unavailable))}")


def ledger_line(sha, tests, seconds, deterministic, flaky, culprits,
                unavailable=None):
    mins, secs = divmod(int(seconds), 60)
    if not deterministic and not flaky:
        line = (f"regression {sha[:8]}: {tests} tests green in "
                f"{mins}m{secs:02d}s")
        if unavailable:
            line += "; " + _unavailable_part(unavailable)
        return line
    parts = []
    if deterministic:
        named = ", ".join(
            f"{i} (since {culprits[i][0][:8]})" if culprits.get(i)
            and culprits[i][0] else i for i in deterministic)
        parts.append(f"{len(deterministic)} deterministic: {named}")
    if flaky:
        parts.append(f"{len(flaky)} flaky: {', '.join(flaky)}")
    if unavailable:
        parts.append(_unavailable_part(unavailable))
    return (f"regression {sha[:8]}: RED, {tests} tests in "
            f"{mins}m{secs:02d}s; " + "; ".join(parts))


def q_paragraph(sha, deterministic, flaky, culprits, repeat):
    lines = []
    for ident in deterministic:
        culprit = culprits.get(ident)
        since = (f"; red since {culprit[0][:8]} ({culprit[1]})"
                 if culprit and culprit[0] else "")
        lines.append(f"- `{ident}` fails on {sha[:8]} in {repeat} of "
                     f"{repeat} lone runs{since}. Reproduce: "
                     f"`python -m unittest {ident}`.")
    for ident in flaky:
        lines.append(f"- `{ident}` failed in the full run and passed in at "
                     f"least one of {repeat} lone runs on {sha[:8]}: a flake; "
                     f"`python runner/tools/regression_guard.py "
                     f"{_module_file(ident) or ident} --repeat 10` is the "
                     "next step.")
    return "\n".join(lines)


def environment():
    """The interpreter and platform that produced a record."""
    import platform
    return {"python": platform.python_version(),
            "platform": f"{platform.system()}-{platform.machine()}"}


def dirty_files():
    """The paths git would refuse to pull over: modified, staged or
    untracked, as `git status --porcelain` lists them."""
    out = git("status", "--porcelain", "--untracked-files=normal")
    return [line[3:] for line in out.splitlines() if line.strip()]


def refuse(args, state, sha, why, out):
    """A pass that cannot run says so in the ledger's own shape and
    in the tree's record, never as a traceback."""
    line = f"regression {sha[:8]}: NOT RUN, {why}"
    record = {"sha": sha, "tests": 0, "seconds": 0.0, "exit": 2,
              "failing": [], "deterministic": [], "flaky": [],
              "culprits": {}, "refused": why, "ledger": line,
              **environment(),
              "when": datetime.now(timezone.utc).strftime(
                  "%Y-%m-%dT%H:%M:%SZ")}
    state.record_run(record)
    if args.record:
        append_record(os.path.join(REPO, args.record), record)
    out(line)
    return 2


def regression_pass(args, out=print):
    state = State(args.state_dir or default_state_dir())
    try:
        sha = git("rev-parse", "HEAD")
    except RuntimeError as e:
        out(f"regression: NOT RUN, not a repository here: {e}")
        return 2
    if args.pull:
        dirty = dirty_files()
        if dirty:
            shown = ", ".join(dirty[:6]) + (" ..." if len(dirty) > 6 else "")
            return refuse(args, state, sha,
                          f"the tree is dirty and --pull would refuse it "
                          f"({len(dirty)} path(s): {shown}); commit or "
                          "stash, then run again", out)
        try:
            git("pull", "--ff-only", "-q", "origin", "main")
        except RuntimeError as e:
            return refuse(args, state, sha, f"the pull failed: {e}", out)
        sha = git("rev-parse", "HEAD")
    out(f"regression pass on {sha[:8]}")
    t0 = time.time()
    rc, output = run_suite(args.jobs, args.timeout)
    seconds = time.time() - t0
    tests = tests_ran(output)
    ids = failing_ids(output)
    if tests == 0 and rc != 0:
        out("the suite did not run:")
        out(output[-3000:])
        return 2
    record = {"sha": sha, "tests": tests, "seconds": round(seconds, 1),
              "exit": rc, "failing": ids, "deterministic": [],
              "flaky": [], "culprits": {}, **environment()}
    if rc == 0 and not ids:
        state.record_green(sha, tests)
        line = ledger_line(sha, tests, seconds, [], [], {})
        record["ledger"] = line
        record["when"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        state.record_run(record)
        if args.record:
            append_record(os.path.join(REPO, args.record), record)
        out(line)
        return 0
    if rc != 0 and not ids:
        # A shard died without a unittest report (a timeout, a
        # crash): nothing to re-run, and the parent's output says.
        out("the run failed without a named test:")
        out(output[-3000:])
        return 2
    out(f"{len(ids)} red: re-running each alone {args.repeat} time(s)")
    outputs = {}
    results = rerun(ids, args.repeat, outputs=outputs)
    deterministic, flaky = classify(results)
    unavailable = {}
    for ident in list(deterministic):
        mod = missing_dependency(outputs.get(ident, ""))
        if mod:
            unavailable[ident] = mod
            deterministic.remove(ident)
    record["unavailable"] = unavailable
    if not deterministic and not flaky:
        # Every red was a package this box lacks: green for the code.
        state.record_green(sha, tests)
        line = ledger_line(sha, tests, seconds, [], [], {}, unavailable)
        record["ledger"] = line
        record["when"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        state.record_run(record)
        if args.record:
            append_record(os.path.join(REPO, args.record), record)
        out(line)
        return 0
    culprits = {}
    last = state.last_green()
    if deterministic and not args.no_bisect and last:
        good = last["sha"]
        try:
            if is_ancestor(good, sha):
                out(f"bisecting {good[:8]}..{sha[:8]} on "
                    f"{len(deterministic)} test(s)")
                culprit = bisect(good, sha, deterministic, log=out)
                for ident in deterministic:
                    culprits[ident] = culprit
            else:
                out(f"last green {good[:8]} is not an ancestor of "
                    f"{sha[:8]}; no bisect")
        except RuntimeError as e:
            out(f"bisect could not run: {e}")
    elif deterministic and not last:
        out("no last green head recorded on this rig; no bisect")
    record.update({"deterministic": deterministic, "flaky": flaky,
                   "culprits": {k: list(v) for k, v in culprits.items()}})
    line = ledger_line(sha, tests, seconds, deterministic, flaky, culprits,
                       unavailable)
    record["ledger"] = line
    record["when"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    path = state.record_run(record)
    if args.record:
        append_record(os.path.join(REPO, args.record), record)
    out(line)
    out("for questions.md:")
    out(q_paragraph(sha, deterministic, flaky, culprits, args.repeat))
    out(f"record: {path}")
    return 1 if deterministic else 3


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pull", action="store_true",
                    help="git pull --ff-only origin main first")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1,
                    help="shards for run_tests_parallel.py (default: this "
                         "box's core count)")
    ap.add_argument("--repeat", type=int, default=3,
                    help="lone re-runs of each red test (default 3)")
    ap.add_argument("--state-dir", default=None,
                    help="where the last green head and the records live")
    ap.add_argument("--no-bisect", action="store_true",
                    help="classify only; do not bisect")
    ap.add_argument("--timeout", type=int, default=7200,
                    help="seconds for the full suite (default 7200)")
    ap.add_argument("--record", default=RECORD,
                    help="the in-tree pass log, relative to the "
                         "repository (default %s)" % RECORD.replace(
                             os.sep, "/"))
    ap.add_argument("--no-record", dest="record", action="store_const",
                    const="", help="append nothing to the tree")
    args = ap.parse_args(argv)
    return regression_pass(args)


if __name__ == "__main__":
    sys.exit(main())
