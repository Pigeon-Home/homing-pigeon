#!/usr/bin/env python3
"""Pin and fetch the upstream files an extension depends on.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

A feed sense parses what another project writes: Suricata's
eve.json, Zeek's conn.log, osquery's results log. The adapter is
only as right as its reading of that format, and the format lives
in the other project's tree. This tool carries the few files that
define it alongside the extension, pinned to one upstream commit,
so the reading can be checked against the thing it reads -- and so
a box with the extension installed also holds the source of the
format it is parsing, with its license.

Full upstream source does not fit: Suricata alone is tens of
megabytes compressed. The budget for everything under
`extensions/*/upstream/` together is UPSTREAM_BUDGET_BYTES
(5 MiB), and `--check` fails when it is spent.

The manifest names what to carry:

    "upstream": {
      "repo": "https://github.com/OISF/suricata",
      "ref": "master",
      "pin": "<40-hex commit>",
      "paths": ["etc/schema.json", "LICENSE"],
      "license": "GPL-2.0-only"
    }

`license` is the upstream's SPDX expression, informational, written
here once; the extension's sources.json inherits it for an entry
that says `"upstream": true`.

`pin` is the commit the files were taken from. `ref` is the branch
or tag the nightly bump resolves to find a newer pin. The files land
under `<extension>/upstream/<path>` with `upstream/PIN.json` beside
them recording the pin, the fetch time, and a SHA-384 per file.

Modes:

    fetch_upstream.py            fetch what is missing or stale
    fetch_upstream.py --check    verify pins, digests, and the budget;
                                 fetch nothing; exit 1 on any gap
    fetch_upstream.py --bump     resolve each ref to its current commit,
                                 rewrite the manifest pin, and fetch

The fetch is plain git -- a blobless, depth-1 fetch of the pinned
commit followed by a sparse checkout of the listed paths -- so it
needs no token and only the blobs it carries home. Stdlib only.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

# This file lives in .github/tools/: the tree is two levels up.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
EXTENSIONS_DIR = os.path.join(ROOT, "extensions")
MANIFEST_FILE = "extension.json"
UPSTREAM_DIR = "upstream"
PIN_FILE = "PIN.json"
UPSTREAM_BUDGET_BYTES = 5 * 1024 * 1024

_SHA_RE = re.compile(r"\A[0-9a-f]{40}\Z")
_REPO_RE = re.compile(r"\Ahttps://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class UpstreamError(Exception):
    pass


def _sha384(path):
    h = hashlib.sha384()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(args, cwd=None, timeout=600):
    proc = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                          text=True, timeout=timeout)
    if proc.returncode != 0:
        raise UpstreamError(
            f"git {' '.join(args)} failed ({proc.returncode}): "
            f"{proc.stderr.strip()[:500]}")
    return proc.stdout


def validate_upstream(block, where="upstream"):
    """The manifest-side rules; runner/extensions.py applies the same."""
    if not isinstance(block, dict):
        raise UpstreamError(f"{where}: must be an object")
    extra = sorted(set(block) - {"repo", "ref", "pin", "paths", "license"})
    if extra:
        raise UpstreamError(f"{where}: unknown field(s) {', '.join(extra)}")
    license_ = block.get("license", "")
    if not isinstance(license_, str) or len(license_) > 100 \
            or "\n" in license_ or "\r" in license_:
        raise UpstreamError(f"{where}.license must be one line (an SPDX "
                            f"expression) of at most 100 characters")
    for field in ("repo", "ref", "pin", "paths"):
        if field not in block:
            raise UpstreamError(f"{where}: missing {field}")
    repo, ref, pin, paths = (block["repo"], block["ref"], block["pin"],
                             block["paths"])
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
        raise UpstreamError(f"{where}.repo must be https://github.com/<owner>/<name>")
    if not isinstance(ref, str) or not ref or len(ref) > 128 \
            or any(c.isspace() for c in ref) or ref.startswith("-"):
        raise UpstreamError(f"{where}.ref must be a branch or tag name")
    if not isinstance(pin, str) or not _SHA_RE.match(pin):
        raise UpstreamError(f"{where}.pin must be a 40-hex commit id")
    if not isinstance(paths, list) or not paths or len(paths) > 32:
        raise UpstreamError(f"{where}.paths must list 1 to 32 repository paths")
    seen = set()
    for p in paths:
        if not isinstance(p, str) or not p or len(p) > 240 \
                or p.startswith("/") or p.startswith("-") \
                or "\\" in p or "\x00" in p \
                or any(part in ("", ".", "..") for part in p.split("/")):
            raise UpstreamError(f"{where}.paths: {p!r} is not a plain relative path")
        if p in seen:
            raise UpstreamError(f"{where}.paths: {p!r} listed twice")
        seen.add(p)
    return {"repo": repo, "ref": ref, "pin": pin, "paths": list(paths),
            "license": license_}


def iter_manifests(ext_root=EXTENSIONS_DIR):
    for name in sorted(os.listdir(ext_root)):
        d = os.path.join(ext_root, name)
        mpath = os.path.join(d, MANIFEST_FILE)
        if not os.path.isfile(mpath):
            continue
        with open(mpath, encoding="utf-8") as f:
            data = json.load(f)
        yield name, d, mpath, data


def read_pin(ext_dir):
    p = os.path.join(ext_dir, UPSTREAM_DIR, PIN_FILE)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def current_state(ext_dir, block):
    """What is on disk versus what the manifest asks for.

    Returns (ok, reasons). ok is True only when PIN.json names the
    manifest's pin, every listed path is present with the digest
    PIN.json recorded, and nothing else sits under upstream/.
    """
    reasons = []
    pin = read_pin(ext_dir)
    updir = os.path.join(ext_dir, UPSTREAM_DIR)
    if pin is None:
        return False, ["no upstream/PIN.json"]
    if pin.get("repo") != block["repo"]:
        reasons.append("PIN.json repo differs from manifest")
    if pin.get("pin") != block["pin"]:
        reasons.append(f"PIN.json pin {str(pin.get('pin'))[:12]} != "
                       f"manifest pin {block['pin'][:12]}")
    files = pin.get("files") or {}
    if sorted(files) != sorted(block["paths"]):
        reasons.append("PIN.json file list differs from manifest paths")
    for rel in block["paths"]:
        fpath = os.path.join(updir, *rel.split("/"))
        if not os.path.isfile(fpath):
            reasons.append(f"missing {rel}")
            continue
        want = (files.get(rel) or {}).get("sha384")
        if want and _sha384(fpath) != want:
            reasons.append(f"digest mismatch {rel}")
    present = set()
    for dp, _dn, fns in os.walk(updir):
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), updir).replace(os.sep, "/")
            if rel != PIN_FILE:
                present.add(rel)
    stray = sorted(present - set(block["paths"]))
    if stray:
        reasons.append(f"unlisted file(s) under upstream/: {', '.join(stray)}")
    return not reasons, reasons


def resolve_ref(repo, ref):
    out = _git(["ls-remote", repo, f"refs/heads/{ref}", f"refs/tags/{ref}",
                f"refs/tags/{ref}^{{}}"], timeout=120)
    found = {}
    for line in out.splitlines():
        sha, _, name = line.partition("\t")
        found[name.strip()] = sha.strip()
    # A peeled annotated tag wins over the tag object; then the branch.
    for key in (f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}", f"refs/heads/{ref}"):
        if key in found:
            return found[key]
    raise UpstreamError(f"{repo}: ref {ref!r} not found")


def fetch(ext_dir, block, log=print):
    updir = os.path.join(ext_dir, UPSTREAM_DIR)
    tmp = tempfile.mkdtemp(prefix="hp-upstream-")
    try:
        _git(["init", "-q", tmp])
        _git(["-C", tmp, "remote", "add", "origin", block["repo"]])
        _git(["-C", tmp, "config", "extensions.partialClone", "origin"])
        _git(["-C", tmp, "fetch", "-q", "--depth", "1", "--filter=blob:none",
              "origin", block["pin"]])
        _git(["-C", tmp, "sparse-checkout", "init", "--no-cone"])
        _git(["-C", tmp, "sparse-checkout", "set", "--no-cone"] + block["paths"])
        _git(["-C", tmp, "checkout", "-q", "FETCH_HEAD"])
        staged = {}
        for rel in block["paths"]:
            src = os.path.join(tmp, *rel.split("/"))
            if not os.path.isfile(src):
                raise UpstreamError(
                    f"{block['repo']}@{block['pin'][:12]}: {rel} is not a file")
            staged[rel] = src
        # Replace upstream/ wholesale so nothing stale survives.
        if os.path.isdir(updir):
            shutil.rmtree(updir)
        os.makedirs(updir)
        files = {}
        total = 0
        for rel, src in staged.items():
            dst = os.path.join(updir, *rel.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            size = os.path.getsize(dst)
            total += size
            files[rel] = {"sha384": _sha384(dst), "bytes": size}
        pin = {
            "repo": block["repo"],
            "ref": block["ref"],
            "pin": block["pin"],
            "license": block.get("license", ""),
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bytes": total,
            "files": files,
        }
        with open(os.path.join(updir, PIN_FILE), "w", encoding="utf-8") as f:
            json.dump(pin, f, indent=2, sort_keys=True)
            f.write("\n")
        log(f"  fetched {len(files)} file(s), {total} bytes, "
            f"from {block['repo']}@{block['pin'][:12]}")
        return pin
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def budget_report(ext_root=EXTENSIONS_DIR):
    """Bytes under every upstream/ together, PIN.json included."""
    total = 0
    per = {}
    for name in sorted(os.listdir(ext_root)):
        updir = os.path.join(ext_root, name, UPSTREAM_DIR)
        if not os.path.isdir(updir):
            continue
        n = 0
        for dp, _dn, fns in os.walk(updir):
            for fn in fns:
                n += os.path.getsize(os.path.join(dp, fn))
        per[name] = n
        total += n
    return total, per


def write_manifest_pin(mpath, data, new_pin):
    data["upstream"]["pin"] = new_pin
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="verify only; fetch nothing; exit 1 on any gap")
    ap.add_argument("--bump", action="store_true",
                    help="resolve each ref to its current commit, rewrite "
                         "the manifest pin, and fetch")
    ap.add_argument("--only", action="append", default=[],
                    help="limit to this extension folder (repeatable)")
    ap.add_argument("--extensions-dir", default=EXTENSIONS_DIR)
    args = ap.parse_args(argv)
    if args.check and args.bump:
        ap.error("--check and --bump are exclusive")

    problems = []
    touched = 0
    for name, ext_dir, mpath, data in iter_manifests(args.extensions_dir):
        if args.only and name not in args.only:
            continue
        block = data.get("upstream")
        updir = os.path.join(ext_dir, UPSTREAM_DIR)
        if block is None:
            if os.path.isdir(updir):
                problems.append(f"{name}: upstream/ exists but the manifest "
                                f"names no upstream")
            continue
        try:
            block = validate_upstream(block, f"{name}/{MANIFEST_FILE}: upstream")
        except UpstreamError as e:
            problems.append(str(e))
            continue
        if args.bump:
            try:
                new = resolve_ref(block["repo"], block["ref"])
            except UpstreamError as e:
                problems.append(f"{name}: {e}")
                continue
            if new != block["pin"]:
                print(f"{name}: {block['ref']} moved {block['pin'][:12]} -> {new[:12]}")
                write_manifest_pin(mpath, data, new)
                block["pin"] = new
        ok, reasons = current_state(ext_dir, block)
        if ok:
            print(f"{name}: up to date at {block['pin'][:12]}")
            continue
        if args.check:
            problems.append(f"{name}: " + "; ".join(reasons))
            continue
        print(f"{name}: fetching ({'; '.join(reasons)})")
        try:
            fetch(ext_dir, block)
            touched += 1
        except UpstreamError as e:
            problems.append(f"{name}: {e}")

    total, per = budget_report(args.extensions_dir)
    print(f"upstream total: {total} bytes of {UPSTREAM_BUDGET_BYTES} "
          f"({100 * total // UPSTREAM_BUDGET_BYTES}%)")
    if total > UPSTREAM_BUDGET_BYTES:
        worst = sorted(per.items(), key=lambda kv: -kv[1])[:3]
        problems.append(
            f"upstream budget exceeded: {total} > {UPSTREAM_BUDGET_BYTES} bytes; "
            f"largest: " + ", ".join(f"{k}={v}" for k, v in worst))
    for p in problems:
        print(f"PROBLEM: {p}", file=sys.stderr)
    if problems:
        return 1
    if touched:
        print(f"{touched} extension(s) fetched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
