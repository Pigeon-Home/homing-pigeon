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
                                       [--duration-table PATH]
                                       [--in-flight N]
                                       [--part K/N]
                                       [--full-log PATH]
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
- ``--part K/N`` runs every Nth shard from the Kth of the packed
  list (shards K-1, K-1+N, ...), keeping the global shard numbers,
  so N runners each take a part of one packing and together run
  every shard exactly once. The Windows leg runs as two parts on
  two runners since 2026-11-12: its 28 shards all start at once on
  a four-core box and the suite ends when the box's CPU work is
  done, so one runner's 66 CPU-minutes stood 20 per cent under the
  20-minute wall; two runners halve the work each box carries for
  the same runner-minutes. A part with no shard is an error (exit
  2), never a silent green.
"""

import argparse
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest

_FAILED_TEST_RE = re.compile(r"^(FAIL|ERROR): (\S+) \(([\w.]+)\)", re.M)
_DURATIONS_HEADER = "Slowest test durations"
_RAN_LINE = re.compile(r"^Ran \d+ tests? in ")
# The workflow-command parser treats these as part of the command.
_ANNOTATION_UNSAFE = str.maketrans({"\r": " ", "\n": " ", "%": "%25",
                                    ":": "%3A", ",": "%2C"})
TAIL_LINES = 40      # of a shard that died with no test named
TAIL_CHARS = 3500    # Actions keeps about 4 KB of an annotation


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


def load_split_list(path, key="modules"):
    """The modules a split file names under ``key``.

    The file is JSON with two lists. "modules": modules sharded by
    class -- a module whose tests cost more than a shard can carry
    (the Q165 briefing guard, 273 tests and fourteen CPU-minutes in
    one file, 2026-11-12: the macOS and Windows shards that drew it
    hit their 20-minute walls) rides as its classes, each a name
    unittest takes as it takes a module's. "own_job": modules the
    per-push legs leave out and a leg of their own runs under a
    longer wall (--heavy-only) -- a single test of the same module
    outran a 30-minute wall on Linux and a 20-minute one on Windows
    and macOS, each in its own shard, once the classes were spread.
    A file that cannot be read raises.
    """
    import json
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    modules = data.get(key, []) if isinstance(data, dict) else None
    if not isinstance(modules, list) or not all(
            isinstance(m, str) and m for m in modules):
        raise ValueError("%s: %r must be a list of module names" % (path, key))
    return set(modules)


def module_test_counts(start_dir, top_level_dir, split=()):
    """Discover the suite and return {item_name: test_count}.

    An item is a module, or -- for a module named in ``split`` --
    one of its test classes as "module.Class", which unittest runs
    by that name exactly as it runs a module. Import failures
    during discovery surface as _FailedTest entries whose id is
    "unittest.loader._FailedTest.<module>"; the module name is
    recovered from that id and counted under its own module so a
    worker reproduces the failure loudly instead of the parent
    quietly dropping the module from every shard.
    """
    split = set(split or ())
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
                    if mod in split:
                        mod = "%s.%s" % (mod, type(item).__qualname__)
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


def load_duration_tool():
    """Load runner/tools/windows_durations.py, the packing's
    home, from beside this file. The suite tools are run as
    scripts, not imported as a package, so the sibling is
    loaded by path (the same shape refresh_figures uses for
    the ops modules)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "windows_durations.py")
    spec = importlib.util.spec_from_file_location(
        "hp_windows_durations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def class_weights(counts, durations):
    """Weights for the class items of split modules: a class item
    "module.Class" the table does not name takes its share of the
    module's measured duration, by test count. Items the table
    names, and whole modules, are left to the table (and the
    packer's median default for the unnamed)."""
    totals = {}
    for name, count in counts.items():
        mod, _, cls = name.rpartition(".")
        if cls and mod in durations and name not in durations and cls[:1].isupper():
            totals[mod] = totals.get(mod, 0) + count
    weights = {}
    for name, count in counts.items():
        mod, _, cls = name.rpartition(".")
        if mod in totals and name not in durations:
            weights[name] = float(durations[mod]) * count / totals[mod]
    return weights


def duration_shards(counts, table_path, budget_seconds=None):
    """Shard item names by measured duration from a table.

    Returns (shards, loads, budget). A module the table does
    not name is weighted at the table's median by the
    packer, so a new file is packed, never dropped; a class
    item of a split module takes its share of the module's
    duration (class_weights). A table that cannot be read or
    trusted raises -- the caller turns that into a loud exit,
    never a silent count split.
    """
    tool = load_duration_tool()
    table = tool.load_table_file(table_path)
    budget = table["budget_seconds"] if budget_seconds is None \
        else budget_seconds
    durations = dict(table["durations"])
    durations.update(class_weights(counts, durations))
    shards = tool.pack_modules(sorted(counts), durations, budget)
    loads = tool.shard_loads(shards, durations)
    return shards, loads, budget


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
    except (Exception, KeyboardInterrupt):
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
        # 3.11+ prints "test_bad (mod.T.test_bad)"; 3.9 and 3.10
        # print "test_bad (mod.T)". Same id either way.
        if not test_id.endswith("." + m.group(2)):
            test_id += "." + m.group(2)
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


_REASON_RE = re.compile(
    r"^(?:[\w.]*(?:Error|Exception|Failure|Interrupt|Exit)|"
    r"AssertionError|subTest)\b.*\S", re.M)


def failure_reasons(output):
    """test id -> the exception line its traceback ends on.

    The block of a FAIL:/ERROR: header runs to the next header or
    the next ``====`` rule. Its last exception-shaped line is the
    reason (``AssertionError: 0 != -2``), which is what a reader of
    the run page needs when the log itself cannot be opened.
    (Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab)
    """
    reasons = {}
    heads = list(_FAILED_TEST_RE.finditer(output))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(output)
        block = output[m.end():end]
        rule = block.find("\n=====")
        if rule >= 0:
            block = block[:rule]
        test_id = m.group(3)
        if not test_id.endswith("." + m.group(2)):
            test_id += "." + m.group(2)
        found = _REASON_RE.findall(block)
        if found and test_id not in reasons:
            reasons[test_id] = found[-1].strip()[:400]
    return reasons


def annotations_for(output, shard):
    """``::error`` workflow commands naming each failed test in a shard.

    One line per failed test, title first so the run page shows
    the test id, the message saying which shard carries the dump.
    Actions keeps the first ten error annotations of a step; the
    full list is still in the log above them.

    A shard that dies on WinError 10038 (Windows select on a
    closed socket, a known flake under CI load) gets one named
    line first, so the run page says what it is.
    """
    lines = []
    if "WinError 10038" in output:
        lines.append(
            "::error title=shard %d::Windows socket flake "
            "(WinError 10038: select on a closed socket); "
            "the dump is in the log" % shard)
    reasons = failure_reasons(output)
    named = failed_tests(output)
    for test_id in named:
        title = test_id.translate(_ANNOTATION_UNSAFE)
        message = "unittest failed in shard %d; its output is above" % shard
        if test_id in reasons:
            message += " -- " + reasons[test_id]
        message = message.translate(_ANNOTATION_UNSAFE)
        lines.append("::error title=%s::%s" % (title, message))
    if not named:
        # The shard ended without unittest naming a test: the
        # interpreter died, the loader raised, or the run was cut.
        # The log host is often out of reach of the reader (the
        # Windows legs of 30-OCT: four shards gone in two minutes,
        # nothing on the run page), so the tail of the output goes
        # on the run page, newlines as %0A, which the page unfolds.
        tail = output.rstrip().splitlines()[-TAIL_LINES:]
        text = "%0A".join(ln.translate(_ANNOTATION_UNSAFE)
                          for ln in tail)[-TAIL_CHARS:]
        lines.append("::error title=shard %d ended without a named "
                     "failure::its last lines%%3A %%0A%s" % (shard, text))
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
    lines = text.splitlines()
    # A shard's stderr can carry lines after unittest's verdict (a
    # ResourceWarning at interpreter exit), which would push "Ran N
    # tests" out of a fixed tail and drop the shard from every count
    # read from the log. The summary is found by its own line.
    ran = [i for i, ln in enumerate(lines) if _RAN_LINE.match(ln)]
    if ran:
        start = max(0, ran[-1] - 1)
        end = len(lines)
        for j in range(ran[-1] + 1, len(lines)):
            if lines[j].startswith(("OK", "FAILED")):
                end = j + 1
                break
        return "\n".join(lines[start:end])
    return "\n".join(lines[-4:])


_SHARD_RAN_RE = re.compile(r"^Ran (\d+) tests? in ([0-9.]+)s", re.M)
_SHARD_VERDICT_RE = re.compile(r"^(OK|FAILED)\b(?: \((.*)\))?\s*$", re.M)


def combined_summary(outputs, elapsed, interrupted=()):
    """The suite's one verdict over every shard's output, in
    unittest's own two-line shape, for a log that tools read the
    way they read a single ``python -m unittest -v`` run
    (runner/tools/skip_guard.py and make_snapshot.py take the
    last "Ran N tests" line and the verdict after it).

    ``outputs`` maps shard index to its captured text; a shard with
    no "Ran" line (killed at the wall, or never started) counts as
    one error, named in the detail, so the verdict is never an OK
    that a lost shard could hide behind.
    """
    ran = 0
    counts = {"failures": 0, "errors": 0, "skipped": 0,
              "expected failures": 0, "unexpected successes": 0}
    lost = []
    for i in sorted(outputs):
        text = outputs[i]
        m = None
        for m in _SHARD_RAN_RE.finditer(text):
            pass
        if m is None:
            lost.append(i)
            continue
        ran += int(m.group(1))
        v = None
        for v in _SHARD_VERDICT_RE.finditer(text[m.end():]):
            pass
        if v is None:
            lost.append(i)
            continue
        for part in (v.group(2) or "").split(","):
            part = part.strip()
            if "=" not in part:
                continue
            key, _eq, num = part.partition("=")
            key = key.strip()
            if key in counts and num.strip().isdigit():
                counts[key] += int(num)
    for i in interrupted:
        if i not in lost:
            lost.append(i)
    if lost:
        counts["errors"] += len(lost)
    detail = ["%s=%d" % (k, n) for k, n in counts.items() if n]
    if lost:
        detail.append("shards without a verdict=%s"
                      % "/".join(str(i) for i in lost))
    ok = not (counts["failures"] or counts["errors"]
              or counts["unexpected successes"] or lost)
    verdict = "OK" if ok else "FAILED"
    if detail:
        verdict += " (" + ", ".join(detail) + ")"
    return "Ran %d tests in %.3fs\n\n%s\n" % (ran, elapsed, verdict)


def parse_part(spec):
    """'K/N' -> (K, N) with 1 <= K <= N; ValueError otherwise."""
    try:
        k, n = (int(x) for x in str(spec).split("/", 1))
    except ValueError:
        raise ValueError("--part wants K/N, two integers")
    if n < 1 or k < 1 or k > n:
        raise ValueError("--part wants 1 <= K <= N, not %s" % spec)
    return k, n


def part_of(shards, k, n):
    """The Kth of N parts of a shard list: the shards at positions
    K-1, K-1+N, ..., with those global positions, so the parts
    together are the list exactly once."""
    numbers = list(range(k - 1, len(shards), n))
    return [shards[i] for i in numbers], numbers


def run_shards(shards, top_level_dir, durations=None, annotate=None,
               wall_clock=0, in_flight=0, full_log=None, numbers=None):
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
    ``in_flight`` bounds how many shards run at once: 0 starts them
    all together, N keeps at most N running and starts the next
    the moment one finishes, in shard order. A shard's wall clock
    and hard stop count from its own start, not the parent's.
    ``full_log`` names a file that receives every shard's complete
    output, in the order the shards finish, followed by one
    combined "Ran N tests" line and verdict (combined_summary), so
    the file reads like a single ``python -m unittest -v`` log to
    the tools that read one; the shards run with -v for it.
    ``numbers`` names each shard's number in the report (default:
    its position); a part of a packing keeps its global numbers.
    """
    if annotate is None:
        annotate = under_actions()
    extra = durations_args(durations)
    if full_log:
        extra = ["-v"] + extra
    if durations and not extra:
        _emit("durations: unittest --durations needs Python 3.12+; "
              "this is %d.%d, running without it"
              % (sys.version_info[0], sys.version_info[1]))
    kwargs = {}
    if sys.version_info >= (3, 10):
        kwargs["ignore_cleanup_errors"] = True
    tmp = tempfile.TemporaryDirectory(prefix="hp-test-shards-", **kwargs)
    grace = wall_clock * 60.0 + _HARD_STOP_GRACE_SEC if wall_clock else None
    limit = len(shards) if not in_flight or in_flight < 1 else in_flight
    started = time.monotonic()
    running = []      # (i, proc, fh, out_path, started_at)
    failed = []
    pending = list(zip(numbers if numbers is not None else range(len(shards)), shards))
    outputs = {}
    interrupted_shards = []
    log_fh = open(full_log, "w", encoding="utf-8") if full_log else None

    def launch(i, shard):
        out_path = os.path.join(tmp.name, "shard-%d.log" % i)
        fh = open(out_path, "wb")
        popen_kw = {}
        if os.name == "nt":
            # A console control event is delivered to every process
            # in the group. A shard that raises one was interrupting
            # this wait (KeyboardInterrupt, two minutes in, no log).
            # Its own group keeps the event there. taskkill /T still
            # reaches it.
            popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        elif wall_clock:
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
        running.append((i, proc, fh, out_path, time.monotonic()))
        _emit("shard %d: %d module(s): %s"
              % (i, len(shard), ", ".join(shard)))

    def report(i, fh, out_path, rc, elapsed, timed_out, interrupted):
        fh.close()
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
        if interrupted:
            _emit_quietly(
                "=== shard %d INTERRUPTED: the parent was signalled "
                "while waiting; the shard was stopped and its log "
                "follows ===" % i)
        try:
            with open(out_path, encoding="utf-8",
                      errors="replace") as rf:
                output = rf.read()
            outputs[i] = output
            if interrupted:
                interrupted_shards.append(i)
            if log_fh is not None:
                try:
                    log_fh.write("=== shard %d (exit %s, %.1fs) ===\n%s\n"
                                 % (i, rc, elapsed, output))
                    log_fh.flush()
                except Exception:
                    pass
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

    try:
        try:
            while pending or running:
                while pending and len(running) < limit:
                    i, shard = pending.pop(0)
                    launch(i, shard)
                # Wait on the shard that started first; the others
                # keep running meanwhile and are collected in turn.
                i, proc, fh, out_path, started_at = running[0]
                timed_out = False
                try:
                    if grace is None:
                        rc = proc.wait()
                    else:
                        try:
                            rc = proc.wait(timeout=max(
                                0.0, started_at + grace - time.monotonic()))
                        except subprocess.TimeoutExpired:
                            timed_out = True
                            _kill_tree(proc)
                            rc = "timeout"
                except Exception:
                    rc = None
                running.pop(0)
                report(i, fh, out_path, rc, time.monotonic() - started_at,
                       timed_out, False)
        except KeyboardInterrupt:
            # BaseException, so the Exception handler above never
            # saw it, and the shard logs died with the parent. Every
            # running shard is stopped and reported; a shard not yet
            # started is simply not run, and counted failed.
            for i, proc, fh, out_path, started_at in running:
                _kill_tree(proc)
                report(i, fh, out_path, "interrupted",
                       time.monotonic() - started_at, False, True)
            running = []
            for i, _shard in pending:
                failed.append(i)
                _emit_quietly("shard %d: not started; the parent was "
                              "signalled first" % i)
            pending = []
    finally:
        if log_fh is not None:
            try:
                summary = combined_summary(
                    outputs, time.monotonic() - started,
                    interrupted=interrupted_shards
                    + [i for i, _s in pending])
                log_fh.write("\n=== combined ===\n" + summary)
                _emit("combined: " + summary.strip().splitlines()[-1])
            except Exception:
                _emit_quietly("the combined summary could not be written")
            try:
                log_fh.close()
            except Exception:
                pass
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
    parser.add_argument("--duration-table", metavar="PATH",
                        help="pack the shards by measured duration "
                             "from this table (see "
                             "runner/tools/windows_durations.py) "
                             "instead of by test count; --jobs "
                             "does not apply in that mode")
    parser.add_argument("--budget-seconds", type=float, default=None,
                        metavar="SECONDS",
                        help="shard budget for --duration-table "
                             "(default: the table's own budget)")
    parser.add_argument("--full-log", default=None, metavar="PATH",
                        help="write every shard's complete output "
                             "(the shards run with -v) and one combined "
                             "verdict to PATH, a log that reads like a "
                             "single python -m unittest -v run")
    parser.add_argument("--in-flight", type=int, default=0, metavar="N",
                        help="run at most N shards at once and start "
                             "the next as one finishes (default 0: "
                             "every shard at once)")
    parser.add_argument("--part", default=None, metavar="K/N",
                        help="run the Kth of N parts of the packed "
                             "shard list (every Nth shard from the "
                             "Kth), keeping the shard numbers; N "
                             "runners with K=1..N run every shard once")
    parser.add_argument("--split", default=None, metavar="PATH",
                        help="a JSON file naming modules to shard by "
                             "class, and modules a leg of their own runs "
                             "(see runner/tools/split_modules.json)")
    parser.add_argument("--heavy-only", action="store_true",
                        help="run only the split file's own_job modules "
                             "(the per-push legs leave them out)")
    parser.add_argument("modules", nargs="*",
                        help="explicit modules to run instead of "
                             "discovering the whole suite")
    args = parser.parse_args(argv)
    if args.durations < 0:
        parser.error("--durations must be >= 0")
    if args.wall_clock < 0:
        parser.error("--wall-clock must be >= 0")
    if args.budget_seconds is not None and args.budget_seconds <= 0:
        parser.error("--budget-seconds must be > 0")
    if args.in_flight < 0:
        parser.error("--in-flight must be >= 0")
    part = None
    if args.part:
        try:
            part = parse_part(args.part)
        except ValueError as exc:
            parser.error(str(exc))

    split, own_job = set(), set()
    if args.split:
        try:
            split = load_split_list(args.split)
            own_job = load_split_list(args.split, key="own_job")
        except (OSError, ValueError) as exc:
            print("error: cannot read the split list %s: %s"
                  % (args.split, exc), file=sys.stderr)
            return 2
    if args.heavy_only and not own_job:
        parser.error("--heavy-only needs a --split file with an own_job list")
    if args.modules:
        counts = {mod: 1 for mod in args.modules}
    else:
        counts = module_test_counts(args.start_dir, args.top_level_dir,
                                    split=split | own_job)
        # The own_job modules ride in their own leg: left out here,
        # the only items under --heavy-only. A class item belongs to
        # the module its name starts with.
        def _owned(item):
            return any(item == m or item.startswith(m + ".") for m in own_job)
        counts = {k: v for k, v in counts.items() if _owned(k) == bool(args.heavy_only)}
    if not counts:
        print("error: no tests discovered under %s -- refusing to "
              "report a vacuous green" % args.start_dir, file=sys.stderr)
        return 2
    total = sum(counts.values())
    if args.duration_table:
        try:
            shards, loads, budget = duration_shards(
                counts, args.duration_table, args.budget_seconds)
        except (OSError, ValueError) as exc:
            print("error: cannot pack from the durations table "
                  "%s: %s" % (args.duration_table, exc),
                  file=sys.stderr)
            return 2
        _emit("running %d test(s) from %d module(s) in %d shard(s)"
              % (total, len(counts), len(shards)))
        _emit("duration-balanced from %s: budget %.0fs per shard; "
              "packed loads %s"
              % (args.duration_table, budget,
                 ", ".join("%.0fs" % load for load in loads)))
    else:
        shards = shard_modules(counts, args.jobs)
        _emit("running %d test(s) from %d module(s) in %d shard(s)"
              % (total, len(counts), len(shards)))
    numbers = None
    if part:
        packed = len(shards)
        shards, numbers = part_of(shards, *part)
        if not shards:
            print("error: part %d of %d has no shard (%d packed) -- "
                  "refusing to report a vacuous green"
                  % (part[0], part[1], packed), file=sys.stderr)
            return 2
        tests = sum(counts.get(item, 0) for shard in shards for item in shard)
        _emit("part %d of %d: shard(s) %s -- %d of the %d shard(s), "
              "%d of the %d test(s)"
              % (part[0], part[1], ", ".join(str(n) for n in numbers),
                 len(shards), packed, tests, total))
    started = time.monotonic()
    if args.in_flight and args.in_flight < len(shards):
        _emit("in flight: at most %d of the %d shard(s) at once"
              % (args.in_flight, len(shards)))
    rc = run_shards(shards, args.top_level_dir, durations=args.durations,
                    wall_clock=args.wall_clock, in_flight=args.in_flight,
                    full_log=args.full_log, numbers=numbers)
    _emit("sharded run finished in %.1fs (exit %d)"
          % (time.monotonic() - started, rc))
    return rc


if __name__ == "__main__":
    sys.exit(main())
