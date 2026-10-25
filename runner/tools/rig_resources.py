#!/usr/bin/env python3
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
"""One line of resource facts for a test run, in a fixed shape.

    python runner/tools/rig_resources.py -- <command ...>
    python runner/tools/rig_resources.py --interval 60

The campaign rig is meant to be busy (standing orders: about 90% of
the box's CPU while a campaign runs) and to say what it used. This
wraps a command -- a suite run, a hunt, a shard set -- and prints
one `resources` line when it ends, built from the kernel's own
counters, so the line in the ledger is a measurement and not an
estimate:

    resources 2026-10-25T12:00:00Z: cores 8 | box cpu 88% | wall
    6m12s | cmd cpu 41m03s = 6.6 cores busy | peak rss 412 MB |
    mem used 61% | disk free 23.4 GB | exit 0 | on target

- box cpu: the whole machine's non-idle share over the command's
  wall time (/proc/stat before and after), which is what "peg the
  CPU" is measured against. Other tenants count; that is the point.
- cmd cpu / cores busy: the command's own user+system CPU time
  (children included, from the wait rusage) and that time divided
  by the wall time: how many cores the command actually kept busy.
- peak rss: the largest single process the command ran (the
  rusage high-water mark; children are reported as the biggest
  one, not the sum).
- mem used / disk free: at the end of the run, for the box and
  for the filesystem under the working directory.
- the verdict: `on target` when box cpu is within 20 points of
  --target (default 90), `under-driven` below that, `over` above
  it. Under-driven for an hour means the loop is waiting on
  something: more shards, or the next item while CI runs.

A second line, `resources-top`, names the five processes holding
the most resident memory, so a box at 97% memory says what is
eating it (a resident model server, say) without a login.

Without a command, --interval samples the box for that many
seconds and prints the same line with the cmd fields blank.
The wrapped command's exit code is this tool's exit code.
Stdlib only; the CPU and memory counters are Linux (/proc); on
other systems those fields read n/a and the rest is still printed.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time


def cpu_counters():
    """(busy, total) jiffies for the whole box, or None off Linux."""
    try:
        with open("/proc/stat", encoding="ascii") as fh:
            first = fh.readline().split()
    except OSError:
        return None
    if not first or first[0] != "cpu":
        return None
    nums = [int(x) for x in first[1:]]
    # user nice system idle iowait irq softirq steal [guest guestnice]
    idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
    total = sum(nums[:8])
    return total - idle, total


def busy_percent(before, after):
    if before is None or after is None:
        return None
    d_total = after[1] - before[1]
    if d_total <= 0:
        return None
    return 100.0 * (after[0] - before[0]) / d_total


def mem_used_percent():
    try:
        info = {}
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                key, _, rest = line.partition(":")
                info[key] = int(rest.split()[0])
        total = info["MemTotal"]
        avail = info.get("MemAvailable", info.get("MemFree", 0))
        return 100.0 * (total - avail) / total if total else None
    except (OSError, KeyError, ValueError, IndexError):
        return None


def top_memory(n=5):
    """The n processes holding the most resident memory, from /proc:
    [(rss_mb, name)], largest first; empty off Linux."""
    out = []
    try:
        pids = [d for d in os.listdir("/proc") if d.isdigit()]
    except OSError:
        return out
    for pid in pids:
        try:
            with open("/proc/%s/status" % pid, encoding="ascii",
                      errors="replace") as fh:
                name = ""
                rss = 0
                for line in fh:
                    if line.startswith("Name:"):
                        name = line.split(None, 1)[1].strip()
                    elif line.startswith("VmRSS:"):
                        rss = int(line.split()[1]) // 1024
                        break
            if rss:
                out.append((rss, name))
        except (OSError, ValueError, IndexError):
            continue
    out.sort(reverse=True)
    return out[:n]


def format_top(top):
    if not top:
        return "resources-top: n/a"
    return "resources-top: " + ", ".join(
        "%s %d MB" % (name, rss) for rss, name in top)


def disk_free_gb(path="."):
    try:
        return shutil.disk_usage(path).free / 1e9
    except OSError:
        return None


def hms(seconds):
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return "%dh%02dm%02ds" % (h, m, s)
    if m:
        return "%dm%02ds" % (m, s)
    return "%ds" % s


def verdict(box_cpu, target):
    if box_cpu is None:
        return "n/a"
    if box_cpu < target - 20:
        return "under-driven"
    if box_cpu > target + 8:
        return "over"
    return "on target"


def format_line(stamp, cores, box_cpu, wall, cmd_cpu, peak_rss_kb,
                mem_used, disk_free, exit_code, target):
    def pct(v):
        return "n/a" if v is None else "%.0f%%" % v

    cores_busy = ("n/a" if cmd_cpu is None or not wall
                  else "%.1f cores busy" % (cmd_cpu / wall))
    fields = [
        "cores %d" % cores,
        "box cpu " + pct(box_cpu),
        "wall " + hms(wall),
        ("cmd cpu %s = %s" % (hms(cmd_cpu), cores_busy)) if cmd_cpu is not None
        else "cmd -",
        ("peak rss %d MB" % (peak_rss_kb // 1024)) if peak_rss_kb else "peak rss n/a",
        "mem used " + pct(mem_used),
        ("disk free %.1f GB" % disk_free) if disk_free is not None else "disk free n/a",
        "exit %s" % ("-" if exit_code is None else exit_code),
        verdict(box_cpu, target),
    ]
    return "resources %s: %s" % (stamp, " | ".join(fields))


def _utc(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def run(command, target, out=sys.stdout):
    cores = os.cpu_count() or 1
    before = cpu_counters()
    started = time.time()
    cmd_cpu = None
    peak_rss_kb = None
    if command:
        proc = subprocess.Popen(command)
        if hasattr(os, "wait4"):
            _pid, status, ru = os.wait4(proc.pid, 0)
            exit_code = (os.waitstatus_to_exitcode(status)
                         if hasattr(os, "waitstatus_to_exitcode")
                         else (status >> 8))
            cmd_cpu = ru.ru_utime + ru.ru_stime
            peak_rss_kb = ru.ru_maxrss  # KiB on Linux
        else:
            exit_code = proc.wait()
    else:
        exit_code = None
    wall = time.time() - started
    after = cpu_counters()
    line = format_line(_utc(), cores, busy_percent(before, after), wall,
                       cmd_cpu, peak_rss_kb, mem_used_percent(),
                       disk_free_gb("."), exit_code, target)
    print(line, file=out, flush=True)
    print(format_top(top_memory()), file=out, flush=True)
    return 0 if exit_code is None else exit_code


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:
        i = argv.index("--")
        command = argv[i + 1:]
        argv = argv[:i]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--interval", type=float, default=60.0,
                    help="seconds to sample when no command is given")
    ap.add_argument("--target", type=float, default=90.0,
                    help="box cpu percent the rig aims for")
    a = ap.parse_args(argv)
    if not command:
        before = cpu_counters()
        time.sleep(max(0.0, a.interval))
        after = cpu_counters()
        print(format_line(_utc(), os.cpu_count() or 1,
                          busy_percent(before, after), a.interval, None,
                          None, mem_used_percent(), disk_free_gb("."),
                          None, a.target), flush=True)
        print(format_top(top_memory()), flush=True)
        return 0
    return run(command, a.target)


if __name__ == "__main__":
    sys.exit(main())
