#!/usr/bin/env python3
# Agent-Stamp: 200003d4-e5f6-4a7b-9c8d-0e1f2a3b4c5d
"""Read the build pipeline's own run history and write a CI-health report.

docs/reports/v3.12.56/ci-failures.md read six days of runs by hand and
answered one question once. The answer rotted the moment the next run
landed. This does the same reading from the GitHub Actions API and
writes it as a dated, regenerable report, so "how is the pipeline
doing" is a command, not an archaeology dig:

    python runner/tools/ci_run_report.py            # writes the report
    python runner/tools/ci_run_report.py --stdout   # print, don't write

It answers, from the record and never from a hunch:
  * how often the pipeline is red, overall and per job;
  * the platform split -- a job red on Windows but not Linux is a
    separate population from one red on both (ci-failures finding 2);
  * the slow jobs: p50 / p90 / max wall time per job, and the long pole;
  * runs that never finished -- timed_out, or cancelled by concurrency;
  * billing-weighted minutes per job (Linux x1, Windows x2, macOS x10),
    so the expensive legs are named;
  * flaky-vs-real: jobs red on exactly one platform.

Run-level stats come from the runs list (cheap, a wide window).
Per-job stats come from the jobs of the most recent runs (one API call
each, so it is sampled; the report says the sample size). Stdlib plus
the `gh` CLI, which every CI runner and dev box here already has.
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone

WORKFLOW = "build.yml"
# GitHub's hosted-runner billing multipliers; the macOS/Windows legs
# cost more per wall-minute, so "slow" and "expensive" are not the same
# question. https://docs.github.com/actions billing.
BILLING = {"windows": 2.0, "macos": 10.0, "linux": 1.0}
REPO_ENV = "HP_CI_REPORT_REPO"  # override; else derived from `gh`


def _gh(args):
    """Run a gh command, return parsed JSON stdout (or None on failure)."""
    res = subprocess.run(["gh"] + args, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        return None
    out = res.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def _repo():
    env = os.environ.get(REPO_ENV)
    if env:
        return env
    info = _gh(["repo", "view", "--json", "nameWithOwner"])
    if info and info.get("nameWithOwner"):
        return info["nameWithOwner"]
    # gh repo view leans on an API gh may route oddly; fall back to the
    # origin remote, which is the repo either way.
    res = subprocess.run(["git", "remote", "get-url", "origin"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True)
    url = res.stdout.strip()
    # Only a GitHub remote names the repo: any other URL split on a
    # host it does not contain would come back whole, scheme included.
    if "github.com" in url:
        tail = url.split("github.com", 1)[-1].lstrip(":/")
        if tail.endswith(".git"):
            tail = tail[:-4]
        if "/" in tail:
            return tail
    raise SystemExit("ci_run_report: cannot determine owner/repo; "
                     "set %s=owner/repo" % REPO_ENV)


def _iso(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _minutes(a, b):
    return (_iso(b) - _iso(a)).total_seconds() / 60.0


def _platform_of(job_name):
    n = job_name.lower()
    if "windows" in n:
        return "windows"
    if "macos" in n or "darwin" in n:
        return "macos"
    return "linux"


# --------------------------------------------------------------------------
# data pull
# --------------------------------------------------------------------------
def fetch_runs(repo, limit):
    """Fetch recent build-workflow runs via the REST API.

    `gh run list --limit >100` paginates through a numeric-ID
    repository path the session proxy refuses, so page the REST
    endpoint under the owner/repo path instead (per_page max 100) and
    normalize its snake_case fields to the names the report uses.
    """
    rows = []
    page = 1
    while len(rows) < limit:
        want = min(100, limit - len(rows))
        data = _gh(["api", "repos/%s/actions/workflows/%s/runs"
                    "?per_page=%d&page=%d" % (repo, WORKFLOW, want, page)])
        batch = (data or {}).get("workflow_runs") if data else None
        if not batch:
            break
        for r in batch:
            rows.append({
                "databaseId": r["id"],
                "headSha": r.get("head_sha", ""),
                "headBranch": r.get("head_branch", ""),
                "event": r.get("event", ""),
                "status": r.get("status", ""),
                "conclusion": r.get("conclusion"),
                "createdAt": r.get("created_at", ""),
                "updatedAt": r.get("updated_at", ""),
            })
        if len(batch) < want:
            break
        page += 1
    return rows


def fetch_jobs(repo, run_id):
    data = _gh(["run", "view", str(run_id), "--repo", repo, "--json", "jobs"])
    return (data or {}).get("jobs", []) if data else []


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def run_level(runs):
    done = [r for r in runs if r["status"] == "completed"]
    # A cancelled run was superseded by a newer push; it is not a
    # pass/fail verdict on the commit, so it is out of the red-rate
    # denominator and counted on its own.
    pushes = [r for r in done if r["event"] == "push"
              and r.get("headBranch") == "main"
              and r["conclusion"] != "cancelled"]
    cancelled_pushes = sum(1 for r in done if r["event"] == "push"
                           and r.get("headBranch") == "main"
                           and r["conclusion"] == "cancelled")
    by_day = defaultdict(lambda: [0, 0])  # day -> [red, total]
    for r in pushes:
        day = r["createdAt"][:10]
        by_day[day][1] += 1
        if r["conclusion"] not in ("success", "skipped"):
            by_day[day][0] += 1
    concl = defaultdict(int)
    for r in done:
        concl[r["conclusion"] or "none"] += 1
    return done, pushes, by_day, concl, cancelled_pushes


def job_level(repo, runs, sample):
    """Per-job stats over the most recent `sample` completed runs."""
    recent = [r for r in runs if r["status"] == "completed"][:sample]
    durations = defaultdict(list)       # job -> [minutes]
    reds = defaultdict(int)             # job -> red count
    totals = defaultdict(int)          # job -> seen count
    # which commits had this job red / green, for the platform split
    red_on = defaultdict(set)          # platform -> set(sha) red
    seen_commits = 0
    for r in recent:
        jobs = fetch_jobs(repo, r["databaseId"])
        if jobs:
            seen_commits += 1
        for j in jobs:
            name = j["name"]
            concl = j.get("conclusion")
            if concl in (None, "skipped"):
                continue
            totals[name] += 1
            if j.get("startedAt") and j.get("completedAt") \
                    and concl == "success":
                durations[name].append(
                    _minutes(j["startedAt"], j["completedAt"]))
            if concl == "failure":
                reds[name] += 1
                red_on[_platform_of(name)].add(r["headSha"])
    return recent, durations, reds, totals, red_on, seen_commits


def _pct(lst, p):
    if not lst:
        return 0.0
    lst = sorted(lst)
    k = max(0, min(len(lst) - 1, int(round((p / 100.0) * (len(lst) - 1)))))
    return lst[k]


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
def _version(root):
    try:
        import tomllib
        with open(os.path.join(root, "pyproject.toml"), "rb") as fh:
            return tomllib.load(fh)["project"]["version"]
    except Exception:
        return "unknown"


def build_report(repo, runs, done, pushes, by_day, concl, cancelled_pushes,
                 durations, reds, totals, red_on, sample_runs, version):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    window = ""
    if done:
        lo = min(_iso(r["createdAt"]) for r in done)
        hi = max(_iso(r["createdAt"]) for r in done)
        window = "%s to %s" % (lo.strftime("%Y-%m-%d %H:%MZ"),
                               hi.strftime("%Y-%m-%d %H:%MZ"))
    out = []
    w = out.append
    w("# CI health: the build pipeline, read from its own runs\n")
    w("<!-- Agent-Stamp: 200003d4-e5f6-4a7b-9c8d-0e1f2a3b4c5d -->\n")
    w("Generated by `runner/tools/ci_run_report.py` at %s for package "
      "%s. Re-run it to refresh; this file is a snapshot of a live "
      "query, not a hand-written record. It reads the `%s` workflow's "
      "run history from the GitHub Actions API and reports what the "
      "record shows, the way docs/reports/v3.12.56/ci-failures.md did "
      "once by hand.\n" % (now, version, WORKFLOW))
    w("Window: %d completed runs, %s. Per-job figures are sampled from "
      "the %d most recent runs.\n" % (len(done), window or "n/a",
                                      sample_runs))

    # --- red rate ---
    w("## How often it is red\n")
    red_pushes = sum(d[0] for d in by_day.values())
    tot_pushes = sum(d[1] for d in by_day.values())
    rate = (100.0 * red_pushes / tot_pushes) if tot_pushes else 0.0
    w("Of %d completed (non-cancelled) pushes to main in the window, %d "
      "ended red (%.0f%%). A further %d main pushes were cancelled by a "
      "newer push before finishing -- concurrency doing its job, not a "
      "verdict, so they are out of this denominator.\n"
      % (tot_pushes, red_pushes, rate, cancelled_pushes))
    if by_day:
        w("By day (red / total pushes to main):\n")
        for day in sorted(by_day):
            red, tot = by_day[day]
            w("- %s: %d / %d" % (day, red, tot))
        w("")
    w("Run conclusions over all %d completed runs: %s.\n"
      % (len(done), ", ".join("%s %d" % (k, v)
                              for k, v in sorted(concl.items(),
                                                 key=lambda x: -x[1]))))

    # --- per-job red, platform split ---
    w("## What is red, and where\n")
    w("| job | runs | red | red rate |")
    w("|---|---:|---:|---:|")
    for name in sorted(totals, key=lambda n: (-reds[n], n)):
        t, rd = totals[name], reds[name]
        w("| %s | %d | %d | %.0f%% |"
          % (name, t, rd, (100.0 * rd / t) if t else 0.0))
    w("")
    both = red_on["windows"] & red_on["linux"]
    win_only = red_on["windows"] - red_on["linux"]
    lin_only = red_on["linux"] - red_on["windows"]
    w("Platform split (distinct commits with a red job, sampled): "
      "Windows-only %d, Linux-only %d, both %d, macOS %d. A job red on "
      "one platform and not the other is a separate population -- a "
      "portability or flakiness problem on that platform, not the same "
      "breakage seen twice (ci-failures finding 2).\n"
      % (len(win_only), len(lin_only), len(both), len(red_on["macos"])))

    # --- slow ---
    w("## What is slow\n")
    w("Per-job wall time over successful runs in the sample.\n")
    w("| job | p50 | p90 | max | n |")
    w("|---|---:|---:|---:|---:|")
    polename, poleval = None, 0.0
    for name in sorted(durations, key=lambda n: -_pct(durations[n], 90)):
        d = durations[name]
        p90 = _pct(d, 90)
        if p90 > poleval:
            polename, poleval = name, p90
        w("| %s | %.1f | %.1f | %.1f | %d |"
          % (name, _pct(d, 50), p90, max(d) if d else 0.0, len(d)))
    w("")
    if polename:
        w("Long pole: **%s** at p90 %.1f min. The jobs run in parallel, "
          "so the pipeline's wall time is the slowest leg plus the "
          "publish, not the sum.\n" % (polename, poleval))

    # --- billing ---
    w("## Where the minutes go\n")
    weighted = defaultdict(float)
    for name, d in durations.items():
        mult = BILLING[_platform_of(name)]
        weighted[name] += sum(d) * mult
    grand = sum(weighted.values()) or 1.0
    w("Billing-weighted minutes (Linux x1, Windows x2, macOS x10), "
      "successful runs in the sample:\n")
    w("| job | weighted min | share |")
    w("|---|---:|---:|")
    for name in sorted(weighted, key=lambda n: -weighted[n]):
        w("| %s | %.0f | %.0f%% |"
          % (name, weighted[name], 100.0 * weighted[name] / grand))
    w("")

    # --- never finished ---
    timed = [r for r in done if r["conclusion"] == "timed_out"]
    w("## What never finished\n")
    w("%d run(s) concluded `timed_out` in the window. A job that sits "
      "for hours without a runner shows as a long wall time on a job "
      "whose runner label the platform retired (ci-failures finding 3); "
      "watch the slow table above for a build-* job far above its "
      "peers.\n" % len(timed))

    w("## How to read this against the baseline\n")
    w("The first read of this pipeline is docs/reports/v3.12.56/"
      "ci-failures.md: six days, by hand, with the fixes it drove "
      "(mutation off the release path, the scarce-runner timers, the "
      "shard annotations). This report is the same questions asked of "
      "the current record; a finding that has come back is a "
      "regression, a finding that is gone stays gone only as long as "
      "this stays green.\n")
    return "\n".join(out) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--runs", type=int, default=300,
                   help="run-list window for run-level stats (default 300)")
    p.add_argument("--job-detail", type=int, default=80,
                   help="most-recent runs to pull per-job (default 80)")
    p.add_argument("--stdout", action="store_true",
                   help="print the report instead of writing it")
    p.add_argument("--out", help="explicit output path")
    args = p.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    repo = _repo()
    runs = fetch_runs(repo, args.runs)
    if not runs:
        raise SystemExit("ci_run_report: no runs returned for %s %s "
                         "(is gh authenticated?)" % (repo, WORKFLOW))
    done, pushes, by_day, concl, cancelled_pushes = run_level(runs)
    (recent, durations, reds, totals, red_on,
     seen) = job_level(repo, runs, args.job_detail)
    version = _version(root)
    report = build_report(repo, runs, done, pushes, by_day, concl,
                          cancelled_pushes, durations, reds, totals,
                          red_on, seen, version)

    if args.stdout:
        sys.stdout.write(report)
        return 0
    out = args.out or os.path.join(root, "docs", "reports",
                                   "v" + version, "ci-health.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(report)
    print("wrote %s (%d runs, %d sampled for jobs)"
          % (out, len(done), seen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
