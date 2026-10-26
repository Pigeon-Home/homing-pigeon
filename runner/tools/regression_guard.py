#!/usr/bin/env python3
# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""The pre-push guard for test commits: what a red leg would have said.

    python runner/tools/regression_guard.py            # changed vs origin/main
    python runner/tools/regression_guard.py test_x.py  # these modules
    python runner/tools/regression_guard.py --since HEAD~3 --repeat 5 --shuffles 3

Every red the campaign's pushes have put on a car had a local
tell: a test that passes alone and fails after another module's
patch leaks; a timing assertion that holds on one run in three; a
POSIX assumption the Windows leg refuses; a skip no registry
knows. This tool runs those checks on the test modules a commit
touches, before the push, and prints one verdict per module per
check so the triage is already done when the car runs:

  native     the module as the test job runs it; expected failures
             allowed, an unexpected success is red
  repeat     the same run N more times; any run that differs from
             the first is a flake (a timing race, an order-free
             assumption on the clock or the machine)
  shuffled   runner/tools/run_tests_shuffled.py on the module with
             several seeds; a failure that appears is a cross-test
             pollution the alphabetical order hid
  windows    runner/tools/run_tests_windows_sim.py on the module,
             compared with the same run on the --since tree in a
             temporary worktree: a count that moved is a finding or
             a test bug, a count that did not is a known artifact
             of the surface (the surface's own docstring lists them)
  leaks      the module in-process with a snapshot of the global
             state around every test: os attributes (name, sep,
             O_BINARY, umask), the environment, the working
             directory, sys.path, the active mock patches, the
             signal handlers, stdout/stderr, the default socket
             timeout; a difference after a test is a leak that
             will land on whichever module runs next, on whichever
             leg orders them differently
  gates      the registry tests every leg runs: the skip registry,
             the version-rot scan, the layout scan

The exit status is 1 when any check is red; the summary says which.
Stdlib only. Nothing here changes a test: a red here is a reason to
fix the test or file the finding, never to soften the check.
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
TESTS = os.path.join("runner", "tests")
TESTS_GIT = "runner/tests"   # git pathspecs take forward slashes everywhere
GATES = ("runner.tests.test_skip_registry",
         "runner.tests.test_doc_version_rot",
         "runner.tests.test_layout")
_RAN = re.compile(r"^Ran (\d+) tests? in", re.M)
_VERDICT = re.compile(r"^(OK|FAILED)(?: \((.*)\))?\s*$", re.M)
_COUNT = re.compile(r"(failures|errors|skipped|expected failures|"
                    r"unexpected successes)=(\d+)")
_HARD_LEAKS = ("os", "environ", "cwd", "umask", "sys.path", "patches",
               "signals", "streams", "socket_timeout")


# ------------------------------------------------------------------
# unittest output
# ------------------------------------------------------------------

def parse_summary(text):
    """{'ran', 'ok', 'failures', 'errors', 'skipped',
    'expected_failures', 'unexpected_successes'} from a unittest
    report, or None when there is no summary line (a crash before
    the run, an import error)."""
    ran = _RAN.findall(text)
    verdict = _VERDICT.findall(text)
    if not ran or not verdict:
        return None
    word, detail = verdict[-1]
    out = {"ran": int(ran[-1]), "ok": word == "OK", "failures": 0,
           "errors": 0, "skipped": 0, "expected_failures": 0,
           "unexpected_successes": 0}
    for key, n in _COUNT.findall(detail or ""):
        out[key.replace(" ", "_")] = int(n)
    return out


def red_count(summary):
    """The number of things a leg would call red."""
    if summary is None:
        return 1
    return (summary["failures"] + summary["errors"]
            + summary["unexpected_successes"])


def run_python(args, cwd=ROOT, timeout=1800):
    """(returncode, combined output) of one python subprocess."""
    env = dict(os.environ)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    try:
        proc = subprocess.run([sys.executable] + list(args), cwd=cwd,
                              env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out = (e.output or b"").decode("utf-8", "replace")
        return 124, out + f"\n[timed out after {timeout}s]\n"
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


# ------------------------------------------------------------------
# which modules
# ------------------------------------------------------------------

def module_name(path):
    """runner.tests.test_x for runner/tests/test_x.py (or a bare name)."""
    base = os.path.basename(path)
    if base.endswith(".py"):
        base = base[:-3]
    return "runner.tests." + base


def changed_modules(since, cwd=ROOT):
    """Test modules changed or added against `since`, from git."""
    names = set()
    for args in (["git", "diff", "--name-only", since + "...HEAD", "--",
                  TESTS_GIT],
                 ["git", "diff", "--name-only", "--", TESTS_GIT],
                 ["git", "ls-files", "--others", "--exclude-standard",
                  TESTS_GIT]):
        try:
            out = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in out.stdout.decode("utf-8", "replace").splitlines():
            line = line.strip().replace("\\", "/")
            base = os.path.basename(line)
            if (line.startswith(TESTS_GIT + "/")
                    and base.startswith("test_") and base.endswith(".py")
                    and "/" not in line[len(TESTS_GIT) + 1:]):
                names.add(base)
    return sorted(names)


def existed_at(since, module_file, cwd=ROOT):
    try:
        proc = subprocess.run(["git", "cat-file", "-e",
                               f"{since}:{TESTS_GIT}/{module_file}"],
                              cwd=cwd, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


# ------------------------------------------------------------------
# the checks
# ------------------------------------------------------------------

class Verdict:
    def __init__(self, check, ok, note):
        self.check = check
        self.ok = ok
        self.note = note


def check_native(module_file):
    rc, out = run_python(["-m", "unittest", module_name(module_file)])
    summary = parse_summary(out)
    if summary is None:
        return Verdict("native", False, "no unittest summary (import error?)"
                       + _tail(out)), None
    note = (f"{summary['ran']} tests, {summary['failures']} failures, "
            f"{summary['errors']} errors, {summary['skipped']} skipped, "
            f"{summary['expected_failures']} expected failures, "
            f"{summary['unexpected_successes']} unexpected successes")
    return Verdict("native", red_count(summary) == 0 and rc == 0,
                   note + ("" if rc == 0 else _tail(out))), summary


def check_repeat(module_file, first, times):
    if first is None:
        return Verdict("repeat", False, "skipped: the native run had no summary")
    differing = []
    for n in range(times):
        _rc, out = run_python(["-m", "unittest", module_name(module_file)])
        summary = parse_summary(out)
        if summary != first:
            differing.append((n + 1, summary, out))
    if not differing:
        return Verdict("repeat", True, f"{times} more runs, all the same")
    n, summary, out = differing[0]
    return Verdict("repeat", False,
                   f"{len(differing)} of {times} runs differ from the first "
                   f"(run {n}: {summary}); a flake" + _tail(out))


def check_shuffled(module_file, seeds):
    bad = []
    for seed in seeds:
        rc, out = run_python(["runner/tools/run_tests_shuffled.py",
                              "--seed", str(seed), "--pattern", module_file])
        summary = parse_summary(out)
        if red_count(summary) or rc != 0:
            bad.append((seed, summary, out))
    if not bad:
        return Verdict("shuffled", True,
                       f"seeds {', '.join(map(str, seeds))}: all green")
    seed, summary, out = bad[0]
    return Verdict("shuffled", False,
                   f"seed {seed} is red ({summary}); reproduce with "
                   f"run_tests_shuffled.py --seed {seed} --pattern "
                   f"{module_file}" + _tail(out))


def sim_counts(module_file, cwd):
    rc, out = run_python(["runner/tools/run_tests_windows_sim.py",
                          "--pattern", module_file], cwd=cwd)
    return parse_summary(out), rc, out


def check_windows(module_file, since, baseline):
    now, rc, out = sim_counts(module_file, ROOT)
    if now is None:
        return Verdict("windows", False,
                       "the simulated surface run had no summary" + _tail(out))
    here = red_count(now)
    if here == 0:
        return Verdict("windows", True, f"{now['ran']} tests green under "
                       "the simulated surface")
    if not baseline:
        return Verdict("windows", False,
                       f"{here} red under the simulated surface and no "
                       "baseline to compare (a new module): triage each as "
                       "finding, test bug or surface artifact" + _tail(out))
    with Worktree(since) as tree:
        if tree is None or not os.path.exists(
                os.path.join(tree, TESTS, module_file)):
            return Verdict("windows", False,
                           f"{here} red under the simulated surface; the "
                           f"{since} tree could not be checked out for a "
                           "baseline" + _tail(out))
        before, _rc, _out = sim_counts(module_file, tree)
    was = red_count(before)
    if here <= was:
        return Verdict("windows", True,
                       f"{here} red under the simulated surface, "
                       f"{was} on {since}: known artifacts of the surface")
    return Verdict("windows", False,
                   f"{here} red under the simulated surface against {was} "
                   f"on {since}: the count moved" + _tail(out))


class Worktree:
    """A temporary checkout of a commit, for the baseline runs."""

    def __init__(self, ref):
        self.ref = ref
        self.path = None

    def __enter__(self):
        self.path = tempfile.mkdtemp(prefix="hp-guard-base-")
        try:
            proc = subprocess.run(
                ["git", "worktree", "add", "--detach", self.path, self.ref],
                cwd=ROOT, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return self.path if proc.returncode == 0 else None

    def __exit__(self, *exc):
        try:
            subprocess.run(["git", "worktree", "remove", "--force", self.path],
                           cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            pass
        shutil.rmtree(self.path, ignore_errors=True)
        return False


def check_leaks(module_file):
    rc, out = run_python([os.path.join("runner", "tools",
                                       "regression_guard.py"),
                          "--leaks", os.path.join(TESTS, module_file)])
    leaks = []
    for line in out.splitlines():
        if line.startswith("LEAK "):
            try:
                leaks.append(json.loads(line[5:]))
            except ValueError:
                leaks.append({"test": "?", "what": "unparsed", "detail": line})
    if rc not in (0, 1):
        return Verdict("leaks", False, "the leak run crashed" + _tail(out))
    hard = [l for l in leaks if l.get("what") in _HARD_LEAKS]
    soft = [l for l in leaks if l.get("what") not in _HARD_LEAKS]
    if not leaks:
        return Verdict("leaks", True, "no global state left behind")
    lines = [f"{l['test']}: {l['what']}: {l['detail']}" for l in hard + soft]
    return Verdict("leaks", not hard,
                   f"{len(hard)} hard, {len(soft)} soft:\n      "
                   + "\n      ".join(lines[:12]))


def check_gates():
    rc, out = run_python(["-m", "unittest"] + list(GATES))
    summary = parse_summary(out)
    if summary is None or red_count(summary) or rc != 0:
        return Verdict("gates", False, "a registry gate is red" + _tail(out))
    return Verdict("gates", True, f"{summary['ran']} registry tests green")


def _tail(out, lines=25):
    kept = [l for l in out.splitlines() if l.strip()][-lines:]
    return "\n      | " + "\n      | ".join(kept) if kept else ""


# ------------------------------------------------------------------
# the in-process leak run (--leaks)
# ------------------------------------------------------------------

def _snapshot():
    import signal
    import socket
    import threading
    from unittest import mock
    snap = {
        "os": {k: getattr(os, k, "<absent>")
               for k in ("name", "sep", "linesep", "O_BINARY")},
        "environ": dict(os.environ),
        "cwd": _safe(os.getcwd),
        "umask": _umask(),
        "sys.path": list(sys.path),
        "patches": len(getattr(mock._patch, "_active_patches", [])),
        "signals": {name: _safe(lambda n=name: signal.getsignal(
            getattr(signal, n))) for name in
            ("SIGINT", "SIGTERM", "SIGHUP", "SIGALRM", "SIGCHLD")
            if hasattr(signal, name)},
        "streams": (id(sys.stdout), id(sys.stderr), id(sys.stdin)),
        "socket_timeout": socket.getdefaulttimeout(),
        "threads": sorted(t.name for t in threading.enumerate()
                          if t is not threading.main_thread()),
        "modules": len(sys.modules),
        "tempdir": _tempdir_entries(),
    }
    return snap


def _safe(fn):
    try:
        return fn()
    except Exception as e:  # a snapshot never aborts the run
        return f"<error {type(e).__name__}>"


def _umask():
    try:
        old = os.umask(0)
        os.umask(old)
        return old
    except (OSError, AttributeError):
        return "<n/a>"


def _tempdir_entries():
    try:
        return sorted(os.listdir(tempfile.gettempdir()))
    except OSError:
        return []


def _diff(before, after):
    """[(what, detail)] for the parts of two snapshots that differ."""
    out = []
    for key in ("os", "signals"):
        for k in before[key]:
            if before[key][k] != after[key].get(k):
                out.append((key, f"{k}: {before[key][k]!r} -> "
                                 f"{after[key].get(k)!r}"))
    env_b, env_a = before["environ"], after["environ"]
    added = sorted(set(env_a) - set(env_b))
    removed = sorted(set(env_b) - set(env_a))
    changed = sorted(k for k in env_b if k in env_a and env_b[k] != env_a[k])
    if added or removed or changed:
        out.append(("environ", f"added {added}, removed {removed}, "
                               f"changed {changed}"))
    for key in ("cwd", "umask", "patches", "streams", "socket_timeout"):
        if before[key] != after[key]:
            out.append((key, f"{before[key]!r} -> {after[key]!r}"))
    if before["sys.path"] != after["sys.path"]:
        out.append(("sys.path", f"{len(before['sys.path'])} -> "
                                f"{len(after['sys.path'])} entries"))
    if before["threads"] != after["threads"]:
        new = sorted(set(after["threads"]) - set(before["threads"]))
        out.append(("threads", f"left running: {new}"))
    new_tmp = sorted(set(after["tempdir"]) - set(before["tempdir"]))
    if new_tmp:
        out.append(("tempdir", f"left behind: {new_tmp[:6]}"
                               + (" ..." if len(new_tmp) > 6 else "")))
    return out


class LeakResult(unittest.TextTestResult):
    """The TextTestResult with a snapshot around every test; each
    difference is printed as one LEAK line of JSON for the parent."""

    def startTest(self, test):
        self._before = _snapshot()
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        after = _snapshot()
        for what, detail in _diff(self._before, after):
            # On its own line: the dots of the progress report share
            # the stream.
            sys.stdout.write("\nLEAK " + json.dumps(
                {"test": test.id(), "what": what, "detail": detail}) + "\n")
            sys.stdout.flush()


def leak_run(path):
    """Run one test module in-process under the leak detector."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    # A private temp root for this run: the shared one is busy with
    # other shards' files on a CI box, and a tempdir left behind must
    # be this module's own to be named.
    private = tempfile.mkdtemp(prefix="hp-guard-tmp-")
    for var in ("TMPDIR", "TEMP", "TMP"):
        os.environ[var] = private
    tempfile.tempdir = private
    name = module_name(path)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    runner = unittest.TextTestRunner(verbosity=1, resultclass=LeakResult,
                                     stream=sys.stdout)
    # Threads a test starts may finish a moment after it returns;
    # the snapshot after each test is taken as stopTest runs, so a
    # thread still winding down shows as soft. Hard leaks are the
    # synchronous ones.
    result = runner.run(suite)
    shutil.rmtree(private, ignore_errors=True)
    return 0 if result.wasSuccessful() else 1


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------

def guard(modules, since, repeat, shuffles, no_sim, no_leaks, out=print):
    """Run every check on every module; return the exit status."""
    red = False
    t0 = time.time()
    for module_file in modules:
        out(f"== {module_file}")
        verdicts = []
        native, first = check_native(module_file)
        verdicts.append(native)
        if repeat:
            verdicts.append(check_repeat(module_file, first, repeat))
        if shuffles:
            verdicts.append(check_shuffled(
                module_file, [20261026 + n for n in range(shuffles)]))
        if not no_sim:
            verdicts.append(check_windows(
                module_file, since, existed_at(since, module_file)))
        if not no_leaks:
            verdicts.append(check_leaks(module_file))
        for v in verdicts:
            out(f"  {'green' if v.ok else 'RED  '} {v.check:9s} {v.note}")
            red = red or not v.ok
    gates = check_gates()
    out("== gates")
    out(f"  {'green' if gates.ok else 'RED  '} {gates.check:9s} {gates.note}")
    red = red or not gates.ok
    out(f"regression guard: {'RED' if red else 'green'} "
        f"({len(modules)} module(s), {time.time() - t0:.0f}s)")
    return 1 if red else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("modules", nargs="*",
                    help="test module files (default: changed vs --since)")
    ap.add_argument("--since", default="origin/main",
                    help="the tree to diff against and to baseline the "
                         "simulated Windows run on (default origin/main)")
    ap.add_argument("--repeat", type=int, default=3,
                    help="extra native runs for flake detection (default 3)")
    ap.add_argument("--shuffles", type=int, default=2,
                    help="shuffled-order runs (default 2; 0 disables)")
    ap.add_argument("--no-sim", action="store_true",
                    help="skip the simulated Windows surface")
    ap.add_argument("--no-leaks", action="store_true",
                    help="skip the leak run")
    ap.add_argument("--leaks", metavar="PATH",
                    help=argparse.SUPPRESS)  # the in-process leak run
    args = ap.parse_args(argv)
    if args.leaks:
        return leak_run(args.leaks)
    modules = [os.path.basename(m) for m in args.modules] \
        or changed_modules(args.since)
    if not modules:
        print(f"regression guard: no test modules changed against "
              f"{args.since}; name the modules to check")
        return 0
    return guard(modules, args.since, args.repeat, args.shuffles,
                 args.no_sim, args.no_leaks)


if __name__ == "__main__":
    sys.exit(main())
