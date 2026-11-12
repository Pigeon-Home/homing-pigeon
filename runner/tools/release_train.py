#!/usr/bin/env python3
"""The release cycle as one command: prepare, build, cut, publish, verify.

    python3 runner/tools/release_train.py status
    python3 runner/tools/release_train.py prepare --note "Fix: ..." [--note ...]
    python3 runner/tools/release_train.py cut [--sha SHA]
    python3 runner/tools/release_train.py run --note "..." [--note ...]
    python3 runner/tools/release_train.py clock [--version V] [--since ISO-TIME]
    python3 runner/tools/release_train.py promote-check --run RUN_ID --sha SHA

`status` reads the tree and the hosted record: the three version
carriers and whether they agree, whether the tag for that version
exists, the newest build on HEAD and the state of the jobs the cut
gates on, and the local guards a release commit must pass (the
version-rot guard, the core measure, the figure slots, the shrink
guard).

`prepare` moves the version one step on its rightmost component in
the three carriers, writes the changelog entry from the notes given,
re-records the core measure and the figures over the tree, runs the
local guards, and commits and pushes a release-prefixed commit (the
prefix keeps the build in its own concurrency group, so another
push cannot cancel it).

`cut` waits for the build on the commit, checks the jobs cut-release
gates on, dispatches cut-release with the full sha, waits for the
tag and for the tag build's publish jobs, then reads the mirrors'
own responses out of those jobs' logs (PyPI's "View at", the
SourceForge file listing and git push, the GitLab uploads and
release, the image tags) and prints the verdict. `run` is prepare
then cut.

`promote-check` is the tag build's own step: cut-release dispatches
the tag build with the gate build's run id (build.yml's promote_from
input), the tag build packages nothing, and before its release job
downloads that run's artifacts it reads the run back -- a build.yml
run on exactly the tag's commit, not cancelled, every gate job green
-- and refuses the release by name otherwise.

`clock` reads one cycle's timeline out of the hosted record -- the
release commit, the build's start, the gate going green, every
cut-release dispatch with its verdict and failed step, the tag, the
tag build and its publish jobs, the release's publish time -- each
with the minutes since the step before and since the start, so
"how long did that take, and where" is one command after a cycle
instead of a hand count over the Actions pages.

Why this exists: the 3.16.20.10 cycle of 2026-11-11 took three hours
of a person's attention for seven build cycles, each step a poll
and a judgment a tool can make. The GitHub API is reached through
`gh api` when gh is signed in, else curl with GH_TOKEN or
GITHUB_TOKEN; both are what the seats already carry.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = "Pigeon-Home/homing-pigeon"
API = "https://api.github.com/repos/" + REPO
CARRIERS = (
    ("pyproject.toml", re.compile(r'^(version = ")(\d+\.\d+\.\d+\.\d+)(")$', re.M)),
    ("runner/_version.py", re.compile(r'^(__version__ = ")(\d+\.\d+\.\d+\.\d+)(")$', re.M)),
    ("runner/ops/install.py", re.compile(r'^(__version__ = ")(\d+\.\d+\.\d+\.\d+)(")$', re.M)),
)
CHANGELOG = "docs/infrastructure-documents/changelog.md"
LOCAL_GUARDS = ("runner.tests.test_version", "runner.tests.test_install_edges",
                "runner.tests.test_core", "runner.tests.test_doc_version_rot",
                "runner.tests.test_release_drop", "runner.tests.test_doc_figure_slots",
                "runner.tests.test_reader_docs_quiet")
SUITE_RUNNERS = ("runner/tools/run_tests_parallel.py",
                 "runner/tools/run_tests_shuffled.py",
                 "runner/tools/run_tests_windows_sim.py")


# ----------------------------------------------------------------
# the hosted record
# ----------------------------------------------------------------

def _token():
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def api(path, method="GET", body=None, raw=False):
    """One GitHub API call; a dict (or bytes when raw) or None."""
    url = path if path.startswith("http") else API + path
    tok = _token()
    if tok:
        cmd = ["curl", "-sS", "-L", "-X", method, "-H", "Authorization: Bearer " + tok,
               "-H", "Accept: application/vnd.github+json"]
        if body is not None:
            cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
        cmd.append(url)
    elif shutil.which("gh"):
        cmd = ["gh", "api", "-X", method, url.replace("https://api.github.com/", "")]
        if body is not None:
            cmd += ["--input", "-"]
    else:
        raise RuntimeError("no GH_TOKEN/GITHUB_TOKEN and no gh on PATH")
    proc = subprocess.run(cmd, capture_output=True,
                          input=(json.dumps(body).encode() if body is not None and cmd[0] == "gh" else None))
    if proc.returncode != 0:
        return None
    if raw:
        return proc.stdout
    if not proc.stdout.strip():
        return {}
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return None


def failed_step(run_id):
    """The name of the first failed step of a run's first job, or ''."""
    for j in run_jobs(run_id).values():
        for st in j.get("steps", []):
            if st.get("conclusion") == "failure":
                return st.get("name", "")
    return ""


def gate_jobs():
    """The job names cut-release.yml gates on, read from the file."""
    with open(os.path.join(ROOT, ".github", "workflows", "cut-release.yml"),
              encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"need = \{([^}]+)\}", text)
    if not m:
        return set()
    return set(re.findall(r'"([a-z0-9_-]+)"', m.group(1)))


def build_runs(sha):
    """build.yml runs of main on `sha`, newest first: cancelled ones
    dropped, and pull_request runs never counted -- a PR run's
    head_sha is the PR's head but its tree is the head merged into
    the base, so its verdict and its artifacts are another tree's.
    A tag build on the same sha is not the gate's build either."""
    d = api("/actions/workflows/build.yml/runs?head_sha=%s&per_page=20" % sha) or {}
    runs = [r for r in d.get("workflow_runs", [])
            if r.get("conclusion") != "cancelled"
            and r.get("event") in ("push", "workflow_dispatch")
            and r.get("head_branch") == "main"]
    return sorted(runs, key=lambda r: r["id"], reverse=True)


def run_jobs(run_id):
    d = api("/actions/runs/%s/jobs?per_page=100" % run_id) or {}
    return {j["name"]: j for j in d.get("jobs", [])}


def gate_verdict(sha):
    """(state, detail): state is 'green', 'red', 'running' or 'none'."""
    runs = build_runs(sha)
    if not runs:
        return "none", "no build run on this commit (cancelled runs are not verdicts)"
    run = runs[0]
    jobs = run_jobs(run["id"])
    need = gate_jobs()
    missing = sorted(need - set(jobs))
    bad = [n for n in need if n in jobs and jobs[n]["status"] == "completed"
           and jobs[n]["conclusion"] != "success"]
    pending = [n for n in need if n in jobs and jobs[n]["status"] != "completed"]
    if bad:
        return "red", "run %s: %s" % (run["id"], ", ".join("%s=%s" % (n, jobs[n]["conclusion"]) for n in bad))
    if missing or pending:
        return "running", "run %s: waiting on %s" % (run["id"], ", ".join(sorted(set(missing) | set(pending))))
    return "green", "run %s: %d gate jobs green" % (run["id"], len(need))


# ----------------------------------------------------------------
# the tree
# ----------------------------------------------------------------

def _git(*args, check=True):
    proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), proc.stderr.strip()))
    return proc.stdout.strip()


def carriers(root=ROOT):
    """{path: version} for the three carriers."""
    out = {}
    for rel, rx in CARRIERS:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            m = rx.search(fh.read())
        out[rel] = m.group(2) if m else None
    return out


def bump(version):
    """The next version: the rightmost component plus one."""
    parts = version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def write_carriers(version, root=ROOT):
    for rel, rx in CARRIERS:
        path = os.path.join(root, rel)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new, n = rx.subn(lambda m: m.group(1) + version + m.group(3), text, count=1)
        if n != 1:
            raise RuntimeError("%s: no version line to carry" % rel)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new)


def changelog_entry(version, notes, today):
    lines = ["## %s - %s" % (version, today), ""]
    lines += ["- " + n.strip() for n in notes if n.strip()]
    return "\n".join(lines) + "\n\n"


def write_changelog(version, notes, today, root=ROOT):
    path = os.path.join(root, CHANGELOG)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if "## %s " % version in text:
        raise RuntimeError("the changelog already carries %s" % version)
    m = re.search(r"^## \d+\.\d+\.\d+\.\d+ - ", text, re.M)
    if not m:
        raise RuntimeError("the changelog has no release heading to insert before")
    text = text[:m.start()] + changelog_entry(version, notes, today) + text[m.start():]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def record_core_measure(root=ROOT):
    """Re-record runner/ops/core.py's as-assembled constants, the
    test pins, and the fuzzing page's part list from a fresh
    measure; returns the parts measured."""
    sys.path.insert(0, root)
    import importlib
    core = importlib.import_module("runner.ops.core")
    importlib.reload(core)
    files = tuple(sorted(set(core.CORE_FILES) | set(SUITE_RUNNERS)))
    total = nonblank = 0
    parts = {}
    for name in files:
        with open(os.path.join(root, name), "rb") as fh:
            lines = fh.read().decode("utf-8", "replace").splitlines()
        total += len(lines)
        nonblank += sum(1 for ln in lines if ln.strip())
        top = name.split("/")
        part = "/".join(top[:2]) if len(top) > 2 else name
        parts[part] = parts.get(part, 0) + len(lines)
    zip_bytes = len(core.core_zip_bytes(root, files=files))
    runners = 0
    for name in SUITE_RUNNERS:
        with open(os.path.join(root, name), "rb") as fh:
            runners += len(fh.read().decode("utf-8", "replace").splitlines())
    fmt = lambda n: "{:,}".format(n)

    def rewrite(rel, pairs):
        path = os.path.join(root, rel)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for old, new in pairs:
            if old not in text:
                raise RuntimeError("%s: cannot find %r to re-record" % (rel, old))
            text = text.replace(old, new, 1)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    core_pairs = [
        ("AS_ASSEMBLED_ZIP_BYTES = %d" % core.AS_ASSEMBLED_ZIP_BYTES, "AS_ASSEMBLED_ZIP_BYTES = %d" % zip_bytes),
        ("AS_ASSEMBLED_LINES = %d" % core.AS_ASSEMBLED_LINES, "AS_ASSEMBLED_LINES = %d" % total),
        ("AS_ASSEMBLED_NONBLANK_LINES = %d" % core.AS_ASSEMBLED_NONBLANK_LINES, "AS_ASSEMBLED_NONBLANK_LINES = %d" % nonblank),
    ]
    with open(os.path.join(root, "runner/ops/core.py"), encoding="utf-8") as fh:
        core_text = fh.read()
    m = re.search(r"the as-assembled set runs to ([\d,]+) lines,\n([\d,]+) of them non-blank", core_text)
    if m:
        core_pairs.append((m.group(0), "the as-assembled set runs to %s lines,\n%s of them non-blank" % (fmt(total), fmt(nonblank))))
    for part, old_n in core.AS_ASSEMBLED_PART_LINES.items():
        if parts.get(part, old_n) != old_n:
            core_pairs.append(('    "%s": %d,' % (part, old_n), '    "%s": %d,' % (part, parts[part])))
    rewrite("runner/ops/core.py", core_pairs)
    test_pairs = [
        ("self.assertEqual(%d, core.AS_ASSEMBLED_ZIP_BYTES)" % core.AS_ASSEMBLED_ZIP_BYTES, "self.assertEqual(%d, core.AS_ASSEMBLED_ZIP_BYTES)" % zip_bytes),
        ("self.assertEqual(%d, core.AS_ASSEMBLED_LINES)" % core.AS_ASSEMBLED_LINES, "self.assertEqual(%d, core.AS_ASSEMBLED_LINES)" % total),
        ("self.assertEqual(%d, core.AS_ASSEMBLED_NONBLANK_LINES)" % core.AS_ASSEMBLED_NONBLANK_LINES, "self.assertEqual(%d, core.AS_ASSEMBLED_NONBLANK_LINES)" % nonblank),
        ('self.assertEqual(%d, core.AS_ASSEMBLED_PART_LINES["runner/runner.py"])' % core.AS_ASSEMBLED_PART_LINES["runner/runner.py"],
         'self.assertEqual(%d, core.AS_ASSEMBLED_PART_LINES["runner/runner.py"])' % parts["runner/runner.py"]),
    ]
    with open(os.path.join(root, "runner/tests/test_core.py"), encoding="utf-8") as fh:
        test_text = fh.read()
    m = re.search(r"# The 3 excluded suite runners: (\d+) lines\.\n(\s+)self\.assertEqual\(recorded - (\d+), parts\[part\]\)", test_text)
    if m and int(m.group(1)) != runners:
        test_pairs.append((m.group(0), "# The 3 excluded suite runners: %d lines.\n%sself.assertEqual(recorded - %d, parts[part])" % (runners, m.group(2), runners)))
    rewrite("runner/tests/test_core.py", test_pairs)
    fz = os.path.join(root, "docs/steady/fuzzing.md")
    with open(fz, encoding="utf-8") as fh:
        text = fh.read()
    start = text.find("The runner proper is ")
    end_marker = "- runner/_version.py: 10\n"
    end = text.find(end_marker, start)
    if start >= 0 and end >= 0:
        end += len(end_marker)
        order = ["runner/ops", "runner/tools", "runner/wire", "runner/runner.py", "runner/oracle",
                 "runner/transport_extensions", "runner/guard", "runner/cloud", "runner/hosting",
                 "runner/__init__.py", "runner/_version.py"]
        block = ("The runner proper is %s lines; the core around it is\n%s. The set as assembled, part by part (re-measured\n%s):\n\n"
                 % (fmt(parts["runner/runner.py"]), fmt(total - parts["runner/runner.py"]),
                    datetime.date.today().isoformat()))
        block += "".join("- %s: %s%s\n" % (k, fmt(parts[k]), " lines" if k == "runner/ops" else "") for k in order if k in parts)
        text = text[:start] + block + text[end:]
    m = re.search(r"for ([\d,]+) of the lines, leaving ([\d,]+) in the canonical list\.", text)
    if m:
        text = text.replace(m.group(0), "for %s of the lines, leaving %s in the canonical list." % (fmt(runners), fmt(parts["runner/tools"] - runners)), 1)
    with open(fz, "w", encoding="utf-8") as fh:
        fh.write(text)
    return parts


def local_guards(root=ROOT):
    """Run the guards a release commit must pass; the failing output or ''."""
    proc = subprocess.run([sys.executable, "-m", "unittest", *LOCAL_GUARDS], cwd=root,
                          capture_output=True, text=True)
    if proc.returncode == 0:
        return ""
    return proc.stdout + proc.stderr


# ----------------------------------------------------------------
# mirror evidence
# ----------------------------------------------------------------

_MIRROR_PATTERNS = {
    "pypi-publish": [r"https://pypi\.org/project/[^\s]+", r"Uploading [^\s]+\.(?:whl|tar\.gz)"],
    "sourceforge": [r'"name": "([^"]+)", "path": "/v[^"]+"', r"default \w+ -> \S+", r"source mirrored to SourceForge git",
                    r"\* \[new tag\]\s+\S+ -> \S+"],
    "gitlab": [r"^uploaded \S+", r"gitlab release \S+ created"],
}


def mirror_evidence(name, log_text):
    """The lines of a publish job's log that are the mirror's own word."""
    found = []
    clean = re.sub(r"^\S+Z ", "", log_text, flags=re.M)
    for pat in _MIRROR_PATTERNS.get(name, []):
        for m in re.finditer(pat, clean, re.M):
            line = m.group(0)
            if line not in found:
                found.append(line)
    return found


def image_tags(log_text):
    return sorted(set(re.findall(r"ghcr\.io/pigeon-home/homing-pigeon:[A-Za-z0-9._-]+", log_text)))


# ----------------------------------------------------------------
# the commands
# ----------------------------------------------------------------

def _say(text):
    print(text, flush=True)


def _wait(label, probe, interval, limit_minutes):
    """Poll `probe` until it returns a value; None keeps waiting."""
    deadline = time.monotonic() + limit_minutes * 60
    while True:
        out = probe()
        if out is not None:
            return out
        if time.monotonic() > deadline:
            raise RuntimeError("%s: still waiting after %d minutes" % (label, limit_minutes))
        time.sleep(interval)


def cmd_status(args):
    cs = carriers()
    agree = len(set(cs.values())) == 1 and None not in cs.values()
    version = cs["pyproject.toml"]
    _say("version carriers: %s (%s)" % (", ".join("%s=%s" % kv for kv in cs.items()), "agree" if agree else "DISAGREE"))
    tag = api("/git/ref/tags/v%s" % version)
    _say("tag v%s: %s" % (version, "exists" if tag and tag.get("object") else "not yet"))
    sha = _git("rev-parse", "HEAD")
    state, detail = gate_verdict(sha)
    _say("build on HEAD %s: %s (%s)" % (sha[:8], state, detail))
    rel = api("/releases/latest") or {}
    _say("latest release: %s published %s with %d assets" % (rel.get("tag_name"), rel.get("published_at"), len(rel.get("assets", []))))
    out = local_guards()
    _say("local guards: %s" % ("green" if not out else "RED\n" + out[-1500:]))
    sg = subprocess.run([sys.executable, os.path.join(ROOT, "runner/tools/shrink_guard.py"), "--commit", "HEAD"],
                        capture_output=True, text=True, cwd=ROOT)
    _say(sg.stdout.strip())
    return 0 if agree and not out else 1


def cmd_prepare(args):
    if _git("status", "--porcelain"):
        raise RuntimeError("the tree has uncommitted changes; commit or stash them first")
    _git("fetch", "origin", "main")
    behind = _git("rev-list", "--count", "HEAD..origin/main")
    if behind != "0":
        _git("rebase", "origin/main")
    cs = carriers()
    if len(set(cs.values())) != 1:
        raise RuntimeError("the carriers disagree: %s" % cs)
    version = bump(cs["pyproject.toml"])
    tag = api("/git/ref/tags/v%s" % version)
    while tag and tag.get("object"):
        version = bump(version)
        tag = api("/git/ref/tags/v%s" % version)
    today = datetime.date.today().isoformat()
    _say("preparing %s" % version)
    write_carriers(version)
    write_changelog(version, args.note, today)
    record_core_measure()
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "runner/tools/refresh_figures.py"), "--write"],
                          cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("refresh_figures --write failed:\n" + proc.stdout + proc.stderr)
    out = local_guards()
    if out:
        raise RuntimeError("the local guards are red; the tree is left as prepared for a look:\n" + out[-3000:])
    subject = args.subject or (args.note[0] if args.note else "the cut")
    message = "release: %s — %s\n\n%s\n" % (version, subject, "\n".join("- " + n for n in args.note))
    if args.trailer:
        message += "\n" + "\n".join(args.trailer) + "\n"
    _git("add", "-A")
    _git("commit", "-q", "-m", message)
    _git("push", "origin", "HEAD:main")
    sha = _git("rev-parse", "HEAD")
    _say("pushed release commit %s for %s" % (sha[:8], version))
    return sha


def cmd_cut(args, sha=None):
    sha = sha or args.sha or _git("rev-parse", "HEAD")
    sha = _git("rev-parse", sha)
    if getattr(args, "watch", False):
        return watch_tag_build(getattr(args, "version", None) or carriers()["pyproject.toml"], args.limit)
    _say("waiting for the build on %s" % sha[:8])

    def probe():
        state, detail = gate_verdict(sha)
        if state == "green":
            return detail
        if state == "red":
            raise RuntimeError("the build is red: " + detail)
        return None
    _say(_wait("the build", probe, 45, args.limit))
    version = carriers()["pyproject.toml"]
    if api("/git/ref/tags/v%s" % version) and api("/git/ref/tags/v%s" % version).get("object"):
        raise RuntimeError("tag v%s already exists; prepare a new version" % version)
    before = {r["id"] for r in (api("/actions/workflows/cut-release.yml/runs?per_page=10") or {}).get("workflow_runs", [])}
    res = api("/actions/workflows/cut-release.yml/dispatches", "POST", {"ref": "main", "inputs": {"sha": sha}})
    if res is None:
        raise RuntimeError("cut-release dispatch failed")
    _say("cut-release dispatched on %s" % sha[:8])

    def cut_probe():
        runs = (api("/actions/workflows/cut-release.yml/runs?per_page=10") or {}).get("workflow_runs", [])
        new = [r for r in runs if r["id"] not in before]
        if new and new[0]["status"] == "completed":
            return new[0]
        return None
    cut = _wait("the cut", cut_probe, 20, 15)
    if cut["conclusion"] != "success":
        step = failed_step(cut["id"])
        remedy = ""
        if step == "tag":
            # Two cuts on 2026-11-12 read the rule: the workflow's
            # token placed v3.16.21.2 through the REST path while the
            # tree's workflows differed from the last tag's, and was
            # refused v3.16.21.1 when main's head had moved past the
            # commit with a newer workflow file. The tag goes in while
            # the commit is main's head; a workflow change landed
            # after it is what the refusal names.
            head = (api("/commits/main") or {}).get("sha", "")
            remedy = ("; the workflow's token could not place the tag"
                      + (" (main's head %s has moved past the commit; the token "
                         "tags the head's tree, so cut the head or prepare again)"
                         % head[:8] if head and head != sha else "")
                      + ": add the RELEASE_TOKEN secret (Q30), or push the tag by "
                      "hand: git tag -a v%s %s -m 'Version %s' && git push origin v%s"
                      % (version, sha[:12], version, version))
        raise RuntimeError("cut-release %s concluded %s at step %r: %s%s"
                           % (cut["id"], cut["conclusion"], step, cut["html_url"], remedy))
    _say("tagged v%s" % version)
    return watch_tag_build(version, args.limit)


def watch_tag_build(version, limit):
    """Wait for the tag build of v<version>; report its publish jobs
    and the mirrors' own words from their logs."""
    publish = ("release", "pypi-publish", "sourceforge", "gitlab")

    def tag_probe():
        # The verdict is the publish jobs', not the whole run's: an
        # advisory suite that walls holds the run 20 minutes past
        # the mirrors (the 3.16.21.2 tag build, 2026-11-12).
        runs = (api("/actions/workflows/build.yml/runs?branch=v%s&per_page=5" % version) or {}).get("workflow_runs", [])
        if not runs:
            return None
        if runs[0]["status"] == "completed":
            return runs[0], run_jobs(runs[0]["id"])
        jobs = run_jobs(runs[0]["id"])
        if all(jobs.get(n, {}).get("status") == "completed" for n in publish):
            return runs[0], jobs
        return None
    tag_build, jobs = _wait("the tag build", tag_probe, 60, limit)
    state = tag_build["conclusion"] or "%s (publish jobs done)" % tag_build["status"]
    report = ["tag build %s: %s" % (tag_build["id"], state)]
    for name in publish:
        j = jobs.get(name)
        report.append("  %-14s %s" % (name, j["conclusion"] if j else "absent"))
        if j and j["conclusion"] == "success" and name != "release":
            log = api("/actions/jobs/%s/logs" % j["id"], raw=True) or b""
            for line in mirror_evidence(name, log.decode("utf-8", "replace"))[:14]:
                report.append("      " + line[:160])
    rel = api("/releases/tags/v%s" % version) or {}
    names = [a["name"] for a in rel.get("assets", [])]
    report.append("  release: %d assets%s" % (len(names), "" if any("windows-x86_64" in n for n in names) else " (NO windows-x86_64 archive)"))
    for run in (api("/actions/workflows/docker.yml/runs?branch=v%s&per_page=3" % version) or {}).get("workflow_runs", []):
        for j in run_jobs(run["id"]).values():
            log = api("/actions/jobs/%s/logs" % j["id"], raw=True) or b""
            tags = image_tags(log.decode("utf-8", "replace"))
            if tags:
                report.append("  image: %s (%s)" % (", ".join(tags), run["conclusion"]))
    _say("\n".join(report))
    return 0 if all((jobs.get(n) or {}).get("conclusion") == "success" for n in publish) else 1


def cmd_run(args):
    sha = cmd_prepare(args)
    try:
        return cmd_cut(args, sha=sha)
    except RuntimeError as exc:
        # The one refusal a second try answers: a push landed between
        # the release commit and the cut, and the workflow's token
        # tags main's head only (3.16.21.4, 2026-11-12). The version
        # moves one more step at the head, with the same notes and
        # the record of the cut that did not publish, and the cycle
        # runs again; any other refusal is reported as it stands.
        if "has moved past the commit" not in str(exc) or getattr(args, "no_retry", False):
            raise
        stale = carriers()["pyproject.toml"]
        _say("release train: %s" % exc)
        _say("main moved past %s before the cut; preparing the next version at the head and cutting again" % stale)
        args.note = list(args.note) + [
            "Re-cut of %s, which never published: main moved past its commit "
            "before the cut, and the workflow token tags the head only" % stale]
        sha = cmd_prepare(args)
        return cmd_cut(args, sha=sha)


# ----------------------------------------------------------------
# the promotion check (the tag build's own reading of the gate build)
# ----------------------------------------------------------------

# The artifacts a gate build carries, one per archive leg plus the
# wheel and sdist: what a promoted release is made of. Each archive
# artifact is named with the version; the python one is not.
PROMOTED_ARTIFACTS = ("homing-pigeon-linux-x86_64-", "homing-pigeon-linux-arm64-",
                      "homing-pigeon-macos-arm64-", "homing-pigeon-macos-x86_64-",
                      "homing-pigeon-windows-x86_64-", "homing-pigeon-windows-arm64-",
                      "homing-pigeon-pi-light-arm64-", "homing-pigeon-python")


def promote_problem(run_id, sha, run=None, jobs=None, artifacts=None):
    """Why the build run `run_id` may not be promoted to the tag on
    `sha`, or None when it may.

    The run must be a build.yml run of main (a push or a dispatch:
    a pull_request run's head_sha is the PR's head but its tree is
    the head merged into the base, so its artifacts are another
    tree's) on exactly that commit; every job cut-release gates on
    (gate_jobs()) must have completed success in it -- the run as a
    whole may still be going, or have been cancelled after the legs
    completed, since the advisory suites outlast the legs; and the
    eight artifacts a release is made of must be there, none
    expired. `run`, `jobs` and `artifacts` are the records, fetched
    when not given; a record that cannot be read is a refusal,
    never a pass.
    """
    if not re.fullmatch(r"[0-9]+", str(run_id)):
        return "promote_from %r is not a run id" % (run_id,)
    if run is None:
        run = api("/actions/runs/%s" % run_id)
    if not run or "head_sha" not in run:
        return "run %s cannot be read" % run_id
    if run.get("head_sha") != sha:
        return "run %s is on %s, not %s" % (run_id, str(run.get("head_sha"))[:12], sha[:12])
    path = str(run.get("path") or "")
    if not path.endswith("/build.yml"):
        return "run %s is %s, not build.yml" % (run_id, path or run.get("name"))
    if run.get("event") not in ("push", "workflow_dispatch"):
        return "run %s is a %s run, whose tree is not the commit it names" % (run_id, run.get("event"))
    if run.get("head_branch") != "main":
        return "run %s is a build of %s, not of main" % (run_id, run.get("head_branch"))
    if jobs is None:
        jobs = run_jobs(run_id)
    need = gate_jobs()
    if not need:
        return "cut-release.yml names no gate jobs"
    missing = sorted(need - set(jobs))
    if missing:
        return "run %s has no job for: %s" % (run_id, ", ".join(missing))
    bad = sorted(n for n in need
                 if jobs[n].get("status") != "completed" or jobs[n].get("conclusion") != "success")
    if bad:
        return "run %s: %s" % (run_id, ", ".join(
            "%s=%s/%s" % (n, jobs[n].get("status"), jobs[n].get("conclusion")) for n in bad))
    if artifacts is None:
        artifacts = (api("/actions/runs/%s/artifacts?per_page=100" % run_id) or {}).get("artifacts")
    if artifacts is None:
        return "run %s: its artifacts cannot be read" % run_id
    names = [a.get("name", "") for a in artifacts if not a.get("expired")]
    absent = [p for p in PROMOTED_ARTIFACTS
              if not any(n == p or (p.endswith("-") and n.startswith(p)) for n in names)]
    if absent:
        return "run %s has no artifact for: %s" % (run_id, ", ".join(absent))
    return None


def cmd_promote_check(args):
    problem = promote_problem(args.run, args.sha)
    if problem:
        _say("::error title=promotion::%s" % problem)
        return 1
    _say("run %s is a build of %s with every gate job green; promoting its artifacts"
         % (args.run, args.sha[:12]))
    return 0


# ----------------------------------------------------------------
# the clock
# ----------------------------------------------------------------

def _ts(text):
    """A GitHub timestamp as an aware datetime, or None."""
    if not text:
        return None
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def cycle_clock(version, since=None):
    """The timeline of one release cycle, read from the hosted record.

    A list of (label, datetime-or-None) in the order the steps
    happen: the release commit, its build's start, the gate green
    (the last gate job done), each cut-release dispatch on the
    commit with its verdict, the tag, the tag build's start, the
    release job, each publish job, and the release's publish time.
    `since` (an ISO time) is the moment the cycle was asked for and
    heads the list when given. Rows the record does not have carry
    None, so a cycle still in flight reads as far as it has gone.
    """
    rows = []
    if since:
        rows.append(("asked for", _ts(since)))
    ref = api("/git/ref/tags/v%s" % version) or {}
    obj = ref.get("object") or {}
    tag_time = None
    sha = obj.get("sha")
    if obj.get("type") == "tag" and sha:
        tag = api("/git/tags/%s" % sha) or {}
        tag_time = _ts((tag.get("tagger") or {}).get("date"))
        sha = (tag.get("object") or {}).get("sha")
    if not sha:
        # No tag yet: the newest build whose head commit carries the
        # release prefix for this version.
        d = api("/actions/workflows/build.yml/runs?branch=main&per_page=50") or {}
        for r in d.get("workflow_runs", []):
            if (r.get("display_title") or "").startswith("release: %s" % version):
                sha = r["head_sha"]
                break
    if not sha:
        return rows + [("release commit", None)]
    commit = api("/commits/%s" % sha) or {}
    commit_time = _ts(((commit.get("commit") or {}).get("committer") or {}).get("date"))
    rows.append(("release commit %s" % sha[:8], commit_time))
    # The tag build shares the sha; the gate's build is main's.
    runs = [r for r in build_runs(sha) if r.get("head_branch") == "main"] or build_runs(sha)
    if runs:
        run = runs[0]
        rows.append(("build %s started" % run["id"], _ts(run.get("run_started_at") or run.get("created_at"))))
        jobs = run_jobs(run["id"])
        need = gate_jobs()
        done = [_ts(jobs[n].get("completed_at")) for n in need if n in jobs and jobs[n].get("completed_at")]
        if len(done) == len(need) and need:
            rows.append(("gate green (%d jobs)" % len(need), max(done)))
        else:
            rows.append(("gate green", None))
        if run.get("status") == "completed":
            rows.append(("build %s whole: %s" % (run["id"], run.get("conclusion")), _ts(run.get("updated_at"))))
    else:
        rows.append(("build started", None))
    # A dispatch names the sha in its inputs, which the runs API does
    # not show; the cycle's dispatches are the ones between the
    # release commit and the tag (or now, while the tag is owed).
    d = api("/actions/workflows/cut-release.yml/runs?per_page=30") or {}
    cuts = []
    for r in d.get("workflow_runs", []):
        when = _ts(r.get("created_at"))
        if when is None or (commit_time and when < commit_time):
            continue
        if tag_time and when > tag_time + datetime.timedelta(minutes=1):
            continue
        cuts.append(r)
    for r in sorted(cuts, key=lambda r: r["id"]):
        verdict = r.get("conclusion") or r.get("status")
        step = failed_step(r["id"]) if verdict == "failure" else ""
        rows.append(("cut-release %s: %s%s" % (r["id"], verdict, " at '%s'" % step if step else ""),
                     _ts(r.get("created_at"))))
    rows.append(("tag v%s%s" % (version, "" if tag_time or not obj else " (lightweight)"), tag_time))
    d = api("/actions/workflows/build.yml/runs?branch=v%s&per_page=5" % version) or {}
    tag_runs = d.get("workflow_runs", [])
    if tag_runs:
        tr = tag_runs[0]
        rows.append(("tag build %s started" % tr["id"], _ts(tr.get("run_started_at") or tr.get("created_at"))))
        jobs = run_jobs(tr["id"])
        for name in ("release", "pypi-publish", "sourceforge", "gitlab"):
            j = jobs.get(name) or {}
            state = j.get("conclusion") or j.get("status") or (
                "pending" if tr.get("status") != "completed" else "absent")
            rows.append(("%s: %s" % (name, state), _ts(j.get("completed_at"))))
    else:
        rows.append(("tag build started", None))
    rel = api("/releases/tags/v%s" % version) or {}
    rows.append(("release published (%d assets)" % len(rel.get("assets", [])), _ts(rel.get("published_at"))))
    return rows


def clock_report(rows):
    """The timeline as text: each row's time, the minutes since the
    row before it, and the minutes since the first row."""
    out = []
    timed = sorted((r for r in rows if r[1] is not None), key=lambda r: r[1])
    first = None
    prev = None
    for label, when in timed:
        if first is None:
            first = when
        since_first = (when - first).total_seconds() / 60
        step = "" if prev is None else "%+.1f" % ((when - prev).total_seconds() / 60)
        out.append("%-52s %s  %6s  %6.1f min" % (label, when.strftime("%H:%M:%SZ"), step, since_first))
        prev = when
    for label, when in rows:
        if when is None:
            out.append("%-52s --" % label)
    return "\n".join(out)


def cmd_clock(args):
    version = args.version or carriers()["pyproject.toml"]
    rows = cycle_clock(version, args.since)
    _say("the %s cycle, from the hosted record:" % version)
    _say(clock_report(rows))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    for name in ("prepare", "run"):
        p = sub.add_parser(name)
        p.add_argument("--note", action="append", default=[], help="a changelog line (repeatable)")
        p.add_argument("--subject", default=None, help="the release commit's subject after the version")
        p.add_argument("--trailer", action="append", default=[], help="a commit trailer line (repeatable)")
        p.add_argument("--limit", type=int, default=60, help="minutes to wait for a build")
        p.add_argument("--no-retry", action="store_true",
                       help="run: do not prepare the next version and cut again when "
                            "main moved past the release commit before the cut")
    p = sub.add_parser("cut")
    p.add_argument("--sha", default=None)
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--watch", action="store_true",
                   help="the tag is already placed: skip the gate and the "
                        "dispatch, wait for the tag build and read the mirrors")
    p.add_argument("--version", default=None,
                   help="with --watch: the version to watch (default: the carriers', "
                        "which a prepared next release has already moved past)")
    p = sub.add_parser("promote-check",
                       help="the tag build's reading of the gate build it promotes")
    p.add_argument("--run", required=True, help="the build run id to promote")
    p.add_argument("--sha", required=True, help="the tag's commit (full sha)")
    p = sub.add_parser("clock", help="one cycle's timeline from the hosted record")
    p.add_argument("--version", default=None, help="the version (default: the carriers')")
    p.add_argument("--since", default=None, help="when the cycle was asked for (ISO time), as the first row")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "status":
            return cmd_status(args)
        if args.cmd == "clock":
            return cmd_clock(args)
        if args.cmd == "promote-check":
            return cmd_promote_check(args)
        if args.cmd == "prepare":
            if not args.note:
                ap.error("prepare needs at least one --note")
            cmd_prepare(args)
            return 0
        if args.cmd == "cut":
            return cmd_cut(args)
        if args.cmd == "run":
            if not args.note:
                ap.error("run needs at least one --note")
            return cmd_run(args)
    except RuntimeError as exc:
        print("release train: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
