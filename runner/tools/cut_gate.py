#!/usr/bin/env python3
"""The cut gate: which jobs of the build on a commit must be green
before the commit is cut, and whether they are.

    python3 runner/tools/cut_gate.py need --sha SHA --version V
    python3 runner/tools/cut_gate.py check --sha SHA --version V --run RUN_ID
    python3 runner/tools/cut_gate.py proofs-due --prev TAG --tag TAG

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

The suites join the gate in one more case, at the cut (the owner,
2026-11-12): main's suite is red -- the newest suite verdict among
the builds before the release commit's own is red, or a watched job
has failed on the release commit's own build. 3.16.24.22 carried no
core code and was cut over a suite that had read red ten minutes
earlier; the short path rests on the suites having read green on
what came before, and a red there takes the reason away. Such a
release waits for the suites on its own commit, which read green
only once the red is mended. The cut reads this (cut-release's gate
step and the train's wait); the promotion check does not, since by
then the cut has decided and the record it read has moved on.

During the window the suites are advisory everywhere (every touched
workflow carries a RELIEF-48H marker with the expiry) and the gate
is the legs alone, whatever the release carries: `need` reads the
marker from build.yml and the clock.

A record that cannot be read is a refusal, never a pass: no
previous release, a compare the API will not give whole, a job
missing from the run, a list of main's builds the API will not
give.

`proofs-due` answers the tag build's other question from the local
history: did anything under runner/ change between two tags other
than the release's own carrier lines? Every release commit moves
the version string in two files under runner/, the as-assembled
measure in runner/ops/core.py and the test line that pins it, so
"anything under runner/" was true of every tag, and the nine proof
workflows started on every release and were cancelled by the next
one (26 of the Python range proof's last 39 runs). A tag whose
only changes under runner/ are those lines starts no proofs; the
nightly covers them. Its last line is `true` or `false`, and the
workflow reads anything else as true.
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
# What says main's suite is red: a failed job among the suites the
# gate names, or the build's first-minute check beside them (the
# shrink guard and the core measure): no gate itself, and the first
# of them to read.
WATCHED = ("shape",) + SUITES
# Never runner code for the gate's purpose, core list or not: the
# tests, the version carrier, and runner/ops/core.py, whose
# as-assembled constants every release commit re-records (a file
# joining the list arrives as a code change of its own).
NOT_CODE = ("runner/tests/*", "runner/_version.py", "runner/__init__.py",
            "runner/ops/core.py")
# A carrier that is also code: its version line moves every release
# and counts for nothing; any other changed line counts.
CARRIER_LINE = {"runner/ops/install.py": re.compile(r"^[-+]\s*__version__\s*=")}
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


# The lines every release commit moves under runner/: the version
# string, the as-assembled measure, and the test line pinning it.
RELEASE_CARRIER_LINES = (
    re.compile(r'^[-+]\s*__version__\s*=\s*"[0-9.]+"\s*$'),
    re.compile(r"^[-+]\s*AS_ASSEMBLED_[A-Z_]+\s*=\s*\d+\s*$"),
    re.compile(r"^[-+]\s*self\.assertEqual\(\d+,\s*core\.AS_ASSEMBLED_[A-Z_]+\)\s*$"),
)


def runner_changes(diff_text):
    """The paths under runner/ that a `git diff -U0` text changes by
    a line other than a release carrier's. A file added, deleted,
    renamed or binary counts whole."""
    changed, path, counted = [], None, False
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            path, counted = line.split(" b/", 1)[-1], False
            continue
        if path is None or counted or not path.startswith("runner/"):
            continue
        whole = line.startswith(("new file mode", "deleted file mode", "rename from", "Binary files"))
        body = line[:1] in "+-" and not line.startswith(("+++", "---"))
        if whole or (body and not any(rx.match(line) for rx in RELEASE_CARRIER_LINES)):
            changed.append(path)
            counted = True
    return changed


def proofs_due(prev, tag, root=ROOT):
    """(due, the changed paths): whether the proofs start on `tag`.
    A diff that cannot be read is due."""
    proc = subprocess.run(["git", "-C", root, "diff", "-U0", prev, tag, "--", "runner/"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        return True, ["(the diff %s..%s could not be read)" % (prev, tag)]
    paths = runner_changes(proc.stdout)
    return bool(paths), paths


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


def is_code(path, core=None, patch=None):
    """True for a file of the core other than the carriers; with no
    core list, for any file under runner/ outside the tests. For a
    carrier that is also code (install.py), true only when a line
    other than its version line changed; with no patch to read,
    true."""
    if any(fnmatch.fnmatch(path, pat) for pat in NOT_CODE):
        return False
    if core is None:
        if not path.startswith("runner/"):
            return False
    elif path not in core:
        return False
    carrier = CARRIER_LINE.get(path)
    if carrier is not None and patch is not None:
        changed = [ln for ln in patch.splitlines()
                   if (ln.startswith("+") or ln.startswith("-"))
                   and not ln.startswith("+++") and not ln.startswith("---")]
        return any(not carrier.match(ln) for ln in changed)
    return True


def carries_runner_code(paths, core=None, patches=None):
    patches = patches or {}
    return any(is_code(p, core, patches.get(p)) for p in paths)


def previous_release(version, api=api):
    """The tag of the newest published release other than v<version>,
    or None. The listing's own order is by tag name as text (drafts
    first, then v3.16.24.9 before v3.16.24.11), so the newest is the
    latest published_at among the page, not the first row."""
    rels = api("/releases?per_page=30")
    if not isinstance(rels, list):
        return None
    published = [r for r in rels
                 if not r.get("draft") and r.get("published_at")
                 and r.get("tag_name") != "v" + version]
    if not published:
        return None
    newest = max(published, key=lambda r: str(r.get("published_at")))
    return newest.get("tag_name")


def changed_since(prev_tag, sha, api=api):
    """{path: patch-or-None} for the files changed from prev_tag to
    sha, or None when the API will not give them whole (a compare
    lists at most 300 files)."""
    d = api("/compare/%s...%s" % (prev_tag, sha))
    if not isinstance(d, dict) or "files" not in d:
        return None
    files = d.get("files") or []
    if len(files) >= 300:
        return None
    return {f.get("filename", ""): f.get("patch") for f in files}


def own_build(sha, api=api):
    """The run id of main's build on `sha` (its newest push or
    dispatch run, cancelled ones aside), or None."""
    d = api("/actions/workflows/build.yml/runs?head_sha=%s&per_page=20" % sha)
    runs = d.get("workflow_runs", []) if isinstance(d, dict) else []
    ids = [r["id"] for r in runs
           if isinstance(r, dict) and "id" in r
           and r.get("event") in ("push", "workflow_dispatch")
           and r.get("head_branch") == "main" and r.get("conclusion") != "cancelled"]
    return max(ids) if ids else None


def run_jobs(run_id, api=api):
    """{name: job} of a run, or None when the record cannot be read."""
    d = api("/actions/runs/%s/jobs?per_page=100" % run_id)
    if not isinstance(d, dict) or not isinstance(d.get("jobs"), list):
        return None
    return {j["name"]: j for j in d["jobs"] if isinstance(j, dict) and "name" in j}


def failed_watched(jobs):
    """The jobs among WATCHED that completed in failure, by name."""
    return sorted(j.get("name", n) for n in WATCHED for j in match(n, jobs)
                  if j.get("status") == "completed" and j.get("conclusion") == "failure")


def suite_verdict(api=api, before=None):
    """Main's newest suite verdict: (state, the commit, the run id,
    the failed jobs, the newer builds read past). state is 'red',
    'green', 'none' or 'unread'.

    Main's builds are read newest first (a push or a dispatch),
    down to the first that carries a verdict: a job among WATCHED
    that failed, or a Linux suite that read green with nothing
    failed beside it. A failed job is a verdict as soon as it has
    failed, while the rest still run. The verdict is the job's, not
    the run's: a run a later head cancelled still carries the
    verdict of a job that had finished, and a run whose suite was
    skipped (a change of docs alone) or cancelled says nothing
    about the tree and is read past. `before` is a build's run id:
    only builds older than it are read, so the reading at a release
    commit is of what came before it and does not move with what
    lands after. 'unread' is a list of builds, or a build's jobs,
    that the API would not give.
    """
    # a hundred builds back: a run of docs pushes (twenty web edits
    # in half an hour on 2026-11-13) stands between a release commit
    # and the last suite verdict more often than not
    d = api("/actions/workflows/build.yml/runs?branch=main&per_page=100")
    if not isinstance(d, dict) or not isinstance(d.get("workflow_runs"), list):
        return "unread", "", None, [], 0
    newer = 0
    for run in d["workflow_runs"]:
        if not isinstance(run, dict) or "id" not in run:
            continue
        if run.get("event") not in ("push", "workflow_dispatch"):
            continue
        if before is not None and run["id"] >= before:
            continue
        jobs = run_jobs(run["id"], api)
        if jobs is None:
            return "unread", str(run.get("head_sha", "")), run["id"], [], newer
        red = failed_watched(jobs)
        if red:
            return "red", str(run.get("head_sha", "")), run["id"], red, newer
        linux = jobs.get("test") or {}
        if linux.get("status") == "completed" and linux.get("conclusion") == "success":
            return "green", str(run.get("head_sha", "")), run["id"], [], newer
        newer += 1
    return "none", "", None, [], newer


def need(sha, version, api=api, relief=None, root=ROOT, red_main=True):
    """(the set of job names the release waits for, the reason).

    `red_main` is the cut's reading, on by default: a release that
    carries no runner code still waits for the suites when main's
    newest suite verdict before the release commit's own build is
    red. The promotion check passes False (see the module's head).
    """
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
    code = sorted(p for p in paths if is_code(p, core, paths.get(p)))
    if code:
        return set(LEGS) | set(SUITES), "runner code since %s (%s%s): the suites too" % (
            prev, ", ".join(code[:4]), "" if len(code) <= 4 else " and %d more" % (len(code) - 4))
    if red_main:
        both = set(LEGS) | set(SUITES)
        own = own_build(sha, api)
        if own is not None:
            # a job that has failed on the commit's own build stays
            # failed: this half of the reading only ever grows
            jobs = run_jobs(own, api)
            if jobs is None:
                return both, "no runner code since %s, but this commit's own build (run %s) cannot be read: the suites too" % (prev, own)
            red = failed_watched(jobs)
            if red:
                return both, ("no runner code since %s, but %s failed on this commit's own build (run %s): "
                              "the suites too" % (prev, ", ".join(red), own))
        state, vsha, run, red, _newer = suite_verdict(api, before=own)
        if state == "red":
            return both, ("no runner code since %s, but main's newest suite verdict before this commit is red "
                          "(%s on %s, run %s): the suites too" % (prev, ", ".join(red), vsha[:8], run))
        if state == "unread":
            return both, "no runner code since %s, but main's suite verdict cannot be read: the suites too" % prev
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
    p = sub.add_parser("proofs-due")
    p.add_argument("--prev", required=True, help="the previous release tag")
    p.add_argument("--tag", required=True, help="the tag the proofs would start on")
    args = ap.parse_args(argv)
    if args.cmd == "proofs-due":
        due, paths = proofs_due(args.prev, args.tag)
        print("%s..%s under runner/, release carriers aside: %s" % (
            args.prev, args.tag, ", ".join(paths[:6]) + (" and %d more" % (len(paths) - 6) if len(paths) > 6 else "") if paths else "nothing"))
        print("true" if due else "false")
        return 0
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
