#!/usr/bin/env python3
"""The release cycle as one command: prepare, build, cut, publish, verify.

    python3 runner/tools/release_train.py status
    python3 runner/tools/release_train.py prepare --note "Fix: ..." [--note ...]
    python3 runner/tools/release_train.py cut [--sha SHA]
    python3 runner/tools/release_train.py run --note "..." [--note ...]

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
    """build.yml runs on `sha`, newest first, cancelled ones dropped."""
    d = api("/actions/workflows/build.yml/runs?head_sha=%s&per_page=20" % sha) or {}
    runs = [r for r in d.get("workflow_runs", []) if r.get("conclusion") != "cancelled"]
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
        return watch_tag_build(carriers()["pyproject.toml"], args.limit)
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
            remedy = ("; the workflow's token could not place the tag (the tree's "
                      ".github/workflows changed since the last tag): add the "
                      "RELEASE_TOKEN secret (Q30), or push the tag by hand: "
                      "git tag -a v%s %s -m 'Version %s' && git push origin v%s"
                      % (version, sha[:12], version, version))
        raise RuntimeError("cut-release %s concluded %s at step %r: %s%s"
                           % (cut["id"], cut["conclusion"], step, cut["html_url"], remedy))
    _say("tagged v%s" % version)
    return watch_tag_build(version, args.limit)


def watch_tag_build(version, limit):
    """Wait for the tag build of v<version>; report its publish jobs
    and the mirrors' own words from their logs."""
    def tag_probe():
        runs = (api("/actions/workflows/build.yml/runs?branch=v%s&per_page=5" % version) or {}).get("workflow_runs", [])
        if runs and runs[0]["status"] == "completed":
            return runs[0]
        return None
    tag_build = _wait("the tag build", tag_probe, 60, limit)
    jobs = run_jobs(tag_build["id"])
    report = ["tag build %s: %s" % (tag_build["id"], tag_build["conclusion"])]
    for name in ("release", "pypi-publish", "sourceforge", "gitlab"):
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
    return 0 if tag_build["conclusion"] == "success" else 1


def cmd_run(args):
    sha = cmd_prepare(args)
    return cmd_cut(args, sha=sha)


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
    p = sub.add_parser("cut")
    p.add_argument("--sha", default=None)
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--watch", action="store_true",
                   help="the tag is already placed: skip the gate and the "
                        "dispatch, wait for the tag build and read the mirrors")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "status":
            return cmd_status(args)
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
