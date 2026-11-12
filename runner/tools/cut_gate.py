#!/usr/bin/env python3
"""The cut gate: which jobs of the build on a commit must be green
before the commit is cut, and whether they are.

    python3 runner/tools/cut_gate.py need --sha SHA --version V
    python3 runner/tools/cut_gate.py check --sha SHA --version V --run RUN_ID

One rule, read by the three places that gate a release: the cut
(cut-release.yml's gate step, before it tags), the tag build's
promotion check (release_train.py promote-check, before the release
job downloads the gate build's artifacts) and the train's own wait.

The gate is always the eight artifact legs. The two suites that
gated the release before the relief window of 2026-11-12 -- the
Linux suite (`test`) and the Windows suite (`test-windows`, both of
its parts) -- join the gate when the release carries runner code:
a file of the core (runner/ops/core.py's canonical list, the code a
user's machine executes) other than the version carrier changed
since the previous published release. A release of docs, tests, a
corpus or the tools outside the core keeps the short path, since
the suites it would wait for ran on the same core a published
release already waited for. The macOS suite stays advisory, as it
was before the window.

During the window the suites are advisory everywhere (every touched
workflow carries a RELIEF-48H marker with the expiry) and the gate
is the legs alone, whatever the release carries: `need` reads the
marker from build.yml and the clock.

A record that cannot be read is a refusal, never a pass: no
previous release, a compare the API will not give whole, a job
missing from the run.
"""
import argparse
import datetime
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API = "https://api.github.com/repos/Pigeon-Home/homing-pigeon"

LEGS = frozenset({"build-python", "build-linux", "build-linux-arm64",
                  "build-windows", "build-windows-arm64", "build-macos",
                  "build-macos-x86_64", "build-pi-light"})
SUITES = ("test", "test-windows")
# Never runner code for the gate's purpose, core list or not.
NOT_CODE = ("runner/tests/*", "runner/_version.py", "runner/__init__.py")
_MARKER = re.compile(r"RELIEF-48H expires (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z)")
_MATRIX = re.compile(r"^(.*?) \([^()]*\)$")


def _token():
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def api(path):
    """One GitHub API GET; a parsed body or None."""
    url = path if path.startswith("http") else API + path
    tok = _token()
    if tok:
        cmd = ["curl", "-sS", "-L", "-H", "Authorization: Bearer " + tok,
               "-H", "Accept: application/vnd.github+json", url]
    elif shutil.which("gh"):
        cmd = ["gh", "api", url.replace("https://api.github.com/", "")]
    else:
        return None
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return None


def relief_active(root=ROOT, now=None):
    """True while build.yml carries a RELIEF-48H marker whose instant
    has not passed."""
    path = os.path.join(root, ".github", "workflows", "build.yml")
    try:
        with open(path, encoding="utf-8") as fh:
            m = _MARKER.search(fh.read())
    except OSError:
        return False
    if not m:
        return False
    expiry = datetime.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%MZ").replace(
        tzinfo=datetime.timezone.utc)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return now < expiry


def core_files(root=ROOT):
    """The core list of the tree at `root` (runner/ops/core.py), or
    None when it cannot be read -- then every file under runner/
    counts as code."""
    path = os.path.join(root, "runner", "ops", "core.py")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    m = re.search(r"CORE_FILES\s*=\s*\(([^)]*)\)", text, re.S)
    if not m:
        return None
    return frozenset(re.findall(r'"([^"]+)"', m.group(1)))


def is_code(path, core=None):
    """True for a file of the core other than the carriers; with no
    core list, for any file under runner/ outside the tests."""
    if any(fnmatch.fnmatch(path, pat) for pat in NOT_CODE):
        return False
    if core is None:
        return path.startswith("runner/")
    return path in core


def carries_runner_code(paths, core=None):
    return any(is_code(p, core) for p in paths)


def previous_release(version, api=api):
    """The tag of the newest published release other than v<version>,
    or None."""
    rels = api("/releases?per_page=10")
    if not isinstance(rels, list):
        return None
    for r in rels:
        if r.get("draft") or not r.get("published_at"):
            continue
        if r.get("tag_name") == "v" + version:
            continue
        return r.get("tag_name")
    return None


def changed_since(prev_tag, sha, api=api):
    """The paths changed from prev_tag to sha, or None when the API
    will not give them whole (a compare lists at most 300 files)."""
    d = api("/compare/%s...%s" % (prev_tag, sha))
    if not isinstance(d, dict) or "files" not in d:
        return None
    files = d.get("files") or []
    if len(files) >= 300:
        return None
    return [f.get("filename", "") for f in files]


def need(sha, version, api=api, relief=None, root=ROOT):
    """(the set of job names the release waits for, the reason)."""
    if relief is None:
        relief = relief_active(root)
    if relief:
        return set(LEGS), "the relief window: the legs alone"
    prev = previous_release(version, api)
    if prev is None:
        return set(LEGS) | set(SUITES), "no previous release to compare against: the suites too"
    paths = changed_since(prev, sha, api)
    if paths is None:
        return set(LEGS) | set(SUITES), "the change set since %s cannot be read whole: the suites too" % prev
    core = core_files(root)
    code = sorted(p for p in paths if is_code(p, core))
    if code:
        return set(LEGS) | set(SUITES), "runner code since %s (%s%s): the suites too" % (
            prev, ", ".join(code[:4]), "" if len(code) <= 4 else " and %d more" % (len(code) - 4))
    return set(LEGS), "no runner code since %s: the legs alone" % prev


def match(name, jobs):
    """The job records a gate name stands for: the job of that name,
    or every leg of a matrix job named 'name (…)'."""
    if name in jobs:
        return [jobs[name]]
    found = []
    for jname, j in jobs.items():
        m = _MATRIX.match(jname)
        if m and m.group(1) == name:
            found.append(j)
    return found


def verdict(need_set, jobs):
    """(missing, bad, pending): names with no job in the run, jobs
    that completed other than success, jobs not yet completed."""
    missing, bad, pending = [], [], []
    for name in sorted(need_set):
        legs = match(name, jobs)
        if not legs:
            missing.append(name)
            continue
        for j in legs:
            label = j.get("name", name)
            if j.get("status") != "completed":
                pending.append(label)
            elif j.get("conclusion") != "success":
                bad.append("%s=completed/%s" % (label, j.get("conclusion")))
    return missing, bad, pending


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("need", "check"):
        p = sub.add_parser(name)
        p.add_argument("--sha", required=True)
        p.add_argument("--version", required=True, help="the version being cut, without the v")
        if name == "check":
            p.add_argument("--run", required=True, help="the build run whose jobs are read")
    args = ap.parse_args(argv)
    need_set, why = need(args.sha, args.version.lstrip("v"))
    if args.cmd == "need":
        print("%s (%s)" % (" ".join(sorted(need_set)), why))
        return 0
    d = api("/actions/runs/%s/jobs?per_page=100" % args.run)
    jobs = {j["name"]: j for j in (d or {}).get("jobs", [])} if isinstance(d, dict) else {}
    if not jobs:
        print("::error title=cut gate::run %s: its jobs cannot be read" % args.run)
        return 1
    missing, bad, pending = verdict(need_set, jobs)
    for name in missing:
        print("::error title=cut gate::no job in run %s for: %s" % (args.run, name))
    for item in bad:
        print("::error title=cut gate::%s" % item)
    if missing or bad:
        return 1
    if pending:
        print("cut gate: run %s: waiting on %s" % (args.run, ", ".join(pending)))
        return 2
    print("cut gate: run %s: %d job(s) green (%s)" % (args.run, len(need_set), why))
    return 0


if __name__ == "__main__":
    sys.exit(main())
