#!/usr/bin/env python3
# Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854
"""Pin every declared extension source: the lock a release ships.

For each extension folder with a sources.json -- by default every
shipped one, examples/extensions/* and runner/transport_extensions/* --
resolve each GitHub entry's "latest" to a commit, download every
declared file and archive, and record the SHA-384 of each in one lock:

    {"lock_version": 1, "generated_at": ..., "generator": ...,
     "homing_pigeon": "<version>",
     "extensions": {"<kind>/<name>": {"declaration_sha384": ...,
                                      "entries": {...}}}}

The release job writes it into the project snapshot as
project/EXTENSION-SOURCES.lock.json. On an extension's first run a box
fetches exactly what the lock names and refuses bytes whose digest
differs (runner/extsources.py). An extension author pins one extension
the same way and ships the result beside its declaration as
sources.lock.json:

    python tools/pin_extension_sources.py --out my-ext/sources.lock.json my-ext

A problem -- a 404, an unreachable host, GitHub's rate limit -- is
recorded in the lock and printed, never fatal: a box resolves what the
build could not pin. --strict exits 1 when anything could not be
pinned. GITHUB_TOKEN, when set, is sent to api.github.com and nowhere
else.
"""

import argparse
import datetime
import json
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402
from runner import extsources as X  # noqa: E402

SHIPPED_PARENTS = ("examples/extensions", "runner/transport_extensions")


def shipped_dirs(repo=REPO):
    """Every shipped extension folder that declares sources."""
    out = []
    for parent in SHIPPED_PARENTS:
        root = os.path.join(repo, *parent.split("/"))
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for name in names:
            folder = os.path.join(root, name)
            if os.path.isfile(os.path.join(folder, X.SOURCES_FILE)):
                out.append(folder)
    return out


def _version(repo):
    try:
        with open(os.path.join(repo, "pyproject.toml"), encoding="utf-8") as fh:
            in_project = False
            for line in fh:
                line = line.strip()
                if line.startswith("["):
                    in_project = line == "[project]"
                elif in_project and line.startswith("version"):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "unknown"


def pin_dirs(dirs, fetcher, hash_archives=True, now=None, repo=REPO,
             out=print):
    """Build the lock for these extension folders. Returns (lock, problems)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    lock = {"lock_version": X.LOCK_VERSION,
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": "tools/pin_extension_sources.py",
            "homing_pigeon": _version(repo),
            "extensions": {}}
    problems = 0
    with tempfile.TemporaryDirectory() as tmp:
        for folder in dirs:
            try:
                with open(os.path.join(folder, E.MANIFEST_FILE),
                          encoding="utf-8") as fh:
                    manifest = E.parse_manifest(json.load(fh))
            except (OSError, ValueError) as e:
                out("%s: no usable %s: %s" % (folder, E.MANIFEST_FILE, e))
                problems += 1
                continue
            decl, problem = X.load_declaration(folder)
            if problem:
                out("%s: %s" % (folder, problem))
                problems += 1
                continue
            if decl is None:
                continue
            key = "%s/%s" % (manifest["kind"], manifest["name"])
            block = X.pin_declaration(fetcher, decl, tmp,
                                      hash_archives=hash_archives)
            lock["extensions"][key] = block
            for eid, rec in sorted(block["entries"].items()):
                res = rec.get("resolved") or {}
                got = len(rec.get("files") or {})
                arch = rec.get("archive") or {}
                line = "%s: %s:" % (key, eid)
                if res.get("commit"):
                    line += " %s @ %s" % (res.get("tag") or res.get("branch")
                                          or res.get("ref"),
                                          res["commit"][:12])
                line += " %d file(s)" % got
                if arch.get("sha384"):
                    line += ", archive %.1f MB" % (arch.get("bytes", 0)
                                                   / (1 << 20))
                elif arch.get("url"):
                    line += ", archive not hashed"
                for p in rec.get("problems") or []:
                    line += "\n    problem: %s" % p
                    problems += 1
                    if os.environ.get("GITHUB_ACTIONS") == "true":
                        # A workflow annotation: the pin that could not
                        # be made shows on the run, not only in its log.
                        out("::warning title=extension sources::%s: %s: %s"
                            % (key, eid, p))
                out(line)
    return lock, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dirs", nargs="*", metavar="EXTENSION_DIR",
                    help="extension folders to pin (default: every "
                         "shipped one that declares sources)")
    ap.add_argument("--out", required=True, help="the lock file to write")
    ap.add_argument("--no-archives", action="store_true",
                    help="resolve and hash the files, record the archive "
                         "URLs without downloading them (a box then "
                         "trusts each archive on first use)")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when anything could not be pinned")
    args = ap.parse_args(argv)
    dirs = [os.path.abspath(d) for d in args.dirs] or shipped_dirs()
    fetcher = X.Fetcher(token=os.environ.get("GITHUB_TOKEN") or None,
                        timeout=120)
    lock, problems = pin_dirs(dirs, fetcher,
                              hash_archives=not args.no_archives)
    parent = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(parent, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(lock, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("pinned %d extension(s) into %s; %d problem(s); %d request(s)"
          % (len(lock["extensions"]), args.out, problems, fetcher.requests))
    return 1 if (args.strict and problems) else 0


if __name__ == "__main__":
    sys.exit(main())
