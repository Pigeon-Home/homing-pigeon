#!/usr/bin/env python3
# Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854
"""Package the whole project as a snapshot that ships with every release.

Every install carries the project that built it, so the Oracle on the
box can read the source, the tests, the docs, the CI workflows, and
the results of the CI run without a network. A snapshot directory:

    project/                     every tracked file at the commit
                                 (git archive: exactly the tree, no
                                 untracked files, no .git)
    project/.history/homing-pigeon.bundle
                                 the full git history as one file
                                 (`git clone homing-pigeon.bundle`);
                                 omitted, and said so, on a shallow
                                 checkout
    project/CI-SNAPSHOT.json     machine-readable: version, commit,
                                 run, every workflow with its
                                 triggers and jobs (runs-on, needs),
                                 and the test summary when a
                                 `unittest -v` log is supplied
    project/PROJECT-SNAPSHOT.md  the index: what is where, as local
                                 paths and as GitHub links pinned to
                                 the commit
    project/EXTENSION-SOURCES.lock.json
                                 with --sources-lock: every declared
                                 extension source pinned by this
                                 build (.github/tools/pin_extension_sources.py)

Stdlib only, like the rest of the project. No YAML parser: workflow
facts are read with line rules that match how build.yml is written.

Usage:
    python .github/tools/make_snapshot.py --out snapshot [--test-log test-output.log]
                                  [--sources-lock EXTENSION-SOURCES.lock.json]
    python .github/tools/make_snapshot.py --inject snapshot/project ARCHIVE...

--inject adds the snapshot to finished install archives as
<archive's top dir>/project/, so the release job builds the snapshot
once (after the test job, with its log) and every archive carries it.
The binaries inside an archive are copied byte for byte.
"""

import argparse
import datetime
import io
import json
import os
import re
import subprocess
import sys
import tarfile

REPO_URL = "https://github.com/Pigeon-Home/homing-pigeon"
BUNDLE = os.path.join(".history", "homing-pigeon.bundle")

_SKIP_RE = re.compile(
    r"^(?P<test>\S+) \((?P<where>[^)]+)\)"
    r".*?\.\.\. skipped ['\"](?P<reason>.*?)['\"]\s*$")
_RAN_RE = re.compile(r"^Ran (\d+) tests? in ([0-9.]+)s")
_RESULT_RE = re.compile(r"^(OK|FAILED)\b(?: \((.*)\))?")


def _git(repo, *args, binary=False):
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True,
                         check=True)
    return out.stdout if binary else out.stdout.decode("utf-8").strip()


def _version(repo):
    with open(os.path.join(repo, "pyproject.toml"), encoding="utf-8") as fh:
        in_project = False
        for line in fh:
            line = line.strip()
            if line.startswith("["):
                in_project = line == "[project]"
            elif in_project and line.startswith("version"):
                return line.split("=", 1)[1].strip().strip('"')
    return "unknown"


def export_tree(repo, dest):
    """Every tracked file at HEAD, via git archive. Returns the count."""
    data = _git(repo, "archive", "--format=tar", "HEAD", binary=True)
    os.makedirs(dest, exist_ok=True)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        members = []
        for m in tar.getmembers():
            # git archive emits only regular files, dirs and symlinks
            # from the tracked tree; refuse anything that would land
            # outside dest anyway.
            norm = os.path.normpath(m.name)
            if norm.startswith("..") or os.path.isabs(norm):
                continue
            members.append(m)
            if m.isfile():
                count += 1
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, members=members, filter="data")
        else:  # Python < 3.12: the members were vetted above
            tar.extractall(dest, members=members)
    return count


def export_history(repo, dest):
    """Full history as a git bundle. Returns (path or None, note)."""
    shallow = _git(repo, "rev-parse", "--is-shallow-repository")
    if shallow == "true":
        return None, ("omitted: the checkout is shallow, so the full "
                      "history was not available to bundle")
    path = os.path.join(dest, BUNDLE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _git(repo, "bundle", "create", path, "--all")
    _git(repo, "bundle", "verify", path)
    return path, "full history, every branch and tag the checkout holds"


def _scalar(line):
    return line.split(":", 1)[1].strip().strip('"').strip("'")


def workflow_facts(path):
    """Name, triggers, and jobs (runs-on, needs, if) of one workflow."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    facts = {"file": None, "name": None, "on": [], "jobs": {}}
    section = None
    job = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        text = raw.strip()
        if indent == 0:
            section = text.split(":", 1)[0]
            job = None
            if section == "name":
                facts["name"] = _scalar(text)
            elif section in ("on", "true") and ":" in text \
                    and text.split(":", 1)[1].strip():
                facts["on"] = [t.strip() for t in re.split(
                    r"[\[\],]", text.split(":", 1)[1]) if t.strip()]
            continue
        if section in ("on", "true") and indent == 2 and text.endswith(":"):
            facts["on"].append(text[:-1])
        elif section == "jobs" and indent == 2 and text.endswith(":"):
            job = text[:-1]
            facts["jobs"][job] = {}
        elif section == "jobs" and job and indent == 4:
            key = text.split(":", 1)[0]
            if key in ("runs-on", "needs", "if", "name",
                       "continue-on-error", "timeout-minutes"):
                facts["jobs"][job][key] = _scalar(text)
    return facts


def test_summary(log_path):
    """Totals and skips from a `python -m unittest -v` log."""
    summary = {"ran": None, "seconds": None, "result": None,
               "detail": None, "skips": []}
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = _SKIP_RE.match(line)
            if m:
                where = m.group("where")
                # 3.11+ prints the full id in the parentheses;
                # older interpreters print only module.Class.
                if not where.endswith("." + m.group("test")):
                    where = "%s.%s" % (where, m.group("test"))
                summary["skips"].append({"test": where,
                                         "reason": m.group("reason")})
                continue
            m = _RAN_RE.match(line)
            if m:
                summary["ran"] = int(m.group(1))
                summary["seconds"] = float(m.group(2))
                continue
            m = _RESULT_RE.match(line)
            if m and summary["ran"] is not None:
                summary["result"] = m.group(1)
                summary["detail"] = m.group(2)
    return summary


def ci_snapshot(repo, project, test_log=None, env=None, now=None):
    env = os.environ if env is None else env
    now = now or datetime.datetime.now(datetime.timezone.utc)
    wf_dir = os.path.join(project, ".github", "workflows")
    workflows = []
    if os.path.isdir(wf_dir):
        for name in sorted(os.listdir(wf_dir)):
            if name.endswith((".yml", ".yaml")):
                facts = workflow_facts(os.path.join(wf_dir, name))
                facts["file"] = ".github/workflows/" + name
                workflows.append(facts)
    snap = {
        "version": _version(repo),
        "commit": _git(repo, "rev-parse", "HEAD"),
        "ref": env.get("GITHUB_REF") or "unknown",
        "run": "%s/%s" % (env.get("GITHUB_RUN_ID") or "unknown",
                          env.get("GITHUB_RUN_ATTEMPT") or "unknown"),
        "run_url": ("%s/actions/runs/%s" % (REPO_URL, env["GITHUB_RUN_ID"])
                    if env.get("GITHUB_RUN_ID") else None),
        "snapshot_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": "%d.%d.%d" % sys.version_info[:3],
        "workflows": workflows,
        "tests": test_summary(test_log) if test_log else None,
        "requirements_ci": ".github/requirements-ci.txt",
        "coverage_reports": sorted(
            "docs/reports/%s" % d for d in os.listdir(
                os.path.join(project, "docs", "reports"))
        ) if os.path.isdir(os.path.join(project, "docs", "reports")) else [],
    }
    return snap


_INDEX = [
    ("The protocol (draft spec)", "PROTOCOL.md"),
    ("The IETF draft, version 1", "docs/ietf/draft-homing-pigeon-00.md"),
    ("The IETF draft, version 2", "docs/ietf/draft-homing-pigeon-v2-00.md"),
    ("Project overview", "README.md"),
    ("Rules for agents working on the project", "AGENTS.md"),
    ("Install", "INSTALL.md"),
    ("Changelog", "docs/CHANGELOG.md"),
    ("The runner and the Oracle (source)", "runner/"),
    ("The cloud-side helpers (source)", "runner/cloud/"),
    ("The test suite", "runner/tests/"),
    ("CI workflows", ".github/workflows/"),
    ("The release pipeline", ".github/workflows/build.yml"),
    ("The platform matrix", ".github/workflows/platform-matrix.yml"),
    ("CI tool pins", ".github/requirements-ci.txt"),
    ("CI and build tools", ".github/tools/"),
    ("Coverage and mutation reports", "docs/reports/"),
    ("Everything not built yet", "docs/FUTURE.md"),
    ("The shipped extensions", "extensions/"),
    ("OS hardening templates", "docs/hardening/"),
    ("Container images", ".github/docker/"),
]


SOURCES_LOCK = "EXTENSION-SOURCES.lock.json"


def sources_lock_facts(path):
    """Counts for the CI facts: extensions, entries, problems."""
    with open(path, encoding="utf-8") as fh:
        lock = json.load(fh)
    exts = lock.get("extensions") if isinstance(lock, dict) else None
    if not isinstance(exts, dict):
        raise SystemExit("%s is not an extension sources lock" % path)
    entries = [e for b in exts.values() if isinstance(b, dict)
               for e in (b.get("entries") or {}).values()]
    return {"file": SOURCES_LOCK, "extensions": len(exts),
            "entries": len(entries),
            "problems": sum(len(e.get("problems") or [])
                            for e in entries if isinstance(e, dict)),
            "generated_at": lock.get("generated_at")}


def index_markdown(snap, history_note, bundle_present, file_count):
    sha = snap["commit"]
    ver = snap["version"]
    what = ("every tracked file, the full history, and the CI"
            if bundle_present else "every tracked file and the CI")
    out = ["# Homing Pigeon %s — project snapshot" % ver, "",
           "This directory is the whole project as it stood at commit",
           "`%s`: %s" % (sha, what),
           "facts of the build that produced this release. The Oracle",
           "on this box reads it with no network.", "",
           "Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854", "",
           "## Where to find things", "",
           "| What | Here | Upstream at this commit |",
           "|---|---|---|"]
    for label, path in _INDEX:
        kind = "tree" if path.endswith("/") else "blob"
        url = "%s/%s/%s/%s" % (REPO_URL, kind, sha, path.rstrip("/"))
        out.append("| %s | `%s` | %s |" % (label, path, url))
    out += ["| CI facts for this build | `CI-SNAPSHOT.json` | %s |"
            % (snap["run_url"] or "n/a (built outside CI)")]
    if snap.get("extension_sources_lock"):
        out.append("| Extension sources pinned by this build | `%s` | — |"
                   % SOURCES_LOCK)
    out += ["| The release | — | %s/releases/tag/v%s |" % (REPO_URL, ver),
            ""]
    out += ["## History", ""]
    if bundle_present:
        out += ["`%s` holds %s." % (BUNDLE, history_note),
                "Restore it with `git clone %s homing-pigeon`." % BUNDLE, ""]
    else:
        out += ["History bundle %s." % history_note, ""]
    tests = snap.get("tests")
    out += ["## CI run", "",
            "- Workflows: %d (%s)" % (
                len(snap["workflows"]),
                ", ".join(w["file"] for w in snap["workflows"])),
            "- Build jobs: %s" % ", ".join(
                "%s on %s" % (j, f.get("runs-on", "?"))
                for w in snap["workflows"]
                if w["file"].endswith("build.yml")
                for j, f in w["jobs"].items() if "runs-on" in f)]
    if tests:
        out.append("- Test suite: %s tests, %s%s, %d skipped" % (
            tests["ran"], tests["result"],
            " (%s)" % tests["detail"] if tests["detail"] else "",
            len(tests["skips"])))
    out += ["- Files in this snapshot: %d" % file_count, ""]
    return "\n".join(out) + "\n"


def make_snapshot(repo, out_dir, test_log=None, env=None, now=None,
                  sources_lock=None):
    project = os.path.join(out_dir, "project")
    if os.path.exists(project) and os.listdir(project):
        raise SystemExit("%s exists and is not empty" % project)
    count = export_tree(repo, project)
    bundle, note = export_history(repo, project)
    snap = ci_snapshot(repo, project, test_log, env=env, now=now)
    snap["history"] = {"bundle": BUNDLE if bundle else None, "note": note}
    snap["files"] = count
    snap["extension_sources_lock"] = None
    if sources_lock:
        snap["extension_sources_lock"] = sources_lock_facts(sources_lock)
        with open(sources_lock, "rb") as src, \
                open(os.path.join(project, SOURCES_LOCK), "wb") as dst:
            dst.write(src.read())
    with open(os.path.join(project, "CI-SNAPSHOT.json"), "w",
              encoding="utf-8") as fh:
        json.dump(snap, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(os.path.join(project, "PROJECT-SNAPSHOT.md"), "w",
              encoding="utf-8") as fh:
        fh.write(index_markdown(snap, note, bundle is not None, count))
    return project, snap


def _top_dir(names):
    tops = {n.split("/", 1)[0] for n in names if n.strip("/")}
    if len(tops) != 1:
        raise SystemExit("archive has no single top directory: %s"
                         % sorted(tops)[:5])
    return tops.pop()


def _project_files(project):
    for dirpath, dirnames, filenames in os.walk(project):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, project).replace(os.sep, "/")
            yield full, rel


def inject(project, archive):
    """Add project/ under the archive's top directory. Returns count."""
    import zipfile
    count = 0
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            top = _top_dir(zf.namelist())
            if any(n.startswith(top + "/project/") for n in zf.namelist()):
                raise SystemExit("%s already carries project/" % archive)
        with zipfile.ZipFile(archive, "a", zipfile.ZIP_DEFLATED) as zf:
            for full, rel in _project_files(project):
                zf.write(full, "%s/project/%s" % (top, rel))
                count += 1
        return count
    if not archive.endswith((".tar.gz", ".tgz")):
        raise SystemExit("not an install archive: %s" % archive)
    tmp = archive + ".tmp"
    with tarfile.open(archive, "r:gz") as src:
        members = src.getmembers()
        top = _top_dir(m.name for m in members)
        if any(m.name.startswith(top + "/project/") for m in members):
            raise SystemExit("%s already carries project/" % archive)
        with tarfile.open(tmp, "w:gz") as dst:
            for m in members:
                dst.addfile(m, src.extractfile(m) if m.isfile() else None)
            for full, rel in _project_files(project):
                info = dst.gettarinfo(full, "%s/project/%s" % (top, rel))
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with open(full, "rb") as fh:
                    dst.addfile(info, fh)
                count += 1
    os.replace(tmp, archive)
    return count


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", help="directory to create project/ in")
    ap.add_argument("--inject", metavar="PROJECT_DIR",
                    help="add this project/ to each ARCHIVE instead")
    ap.add_argument("archives", nargs="*", metavar="ARCHIVE")
    ap.add_argument("--repo", default=".", help="the git checkout")
    ap.add_argument("--test-log", default=None,
                    help="a `python -m unittest -v` log to summarize")
    ap.add_argument("--sources-lock", default=None,
                    help="an extension sources lock to ship as "
                         "project/" + SOURCES_LOCK)
    args = ap.parse_args(argv)
    if args.inject:
        if not args.archives:
            ap.error("--inject needs at least one ARCHIVE")
        for archive in args.archives:
            n = inject(args.inject, archive)
            print("injected %d files into %s" % (n, archive))
        return 0
    if not args.out:
        ap.error("--out is required")
    project, snap = make_snapshot(args.repo, args.out, args.test_log,
                                  sources_lock=args.sources_lock)
    print("snapshot %s: %s @ %s, %d files, history %s"
          % (project, snap["version"], snap["commit"][:12], snap["files"],
             "bundled" if snap["history"]["bundle"] else "omitted"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
