#!/usr/bin/env python3
# agent-ident: 200003d4-e5f6-4a7b-9c8d-0e1f2a3b4c5d
"""Pin, vendor, and verify the upstream projects a sense extension reads.

The sense extensions do not import their upstreams -- they tail the
log output of tools like Zeek, Suricata, Falco. The dependency is a
format contract plus a question every audit eventually asks: *which
version of that tool was this extension built against, and can I
prove it offline?* Shipping the full upstream source would answer it
and cost hundreds of MB per tool. This instead ships a small,
pinned, hash-verified provenance bundle alongside each extension and
leaves the bytes reproducibly re-fetchable from the pinned commit.

It is the extension-tree sibling of tools/stamp_provenance.py: that
stamps "which build am I?" into an archive; this stamps "which
upstream, at which commit?" into an extension.

Layout, per extension that declares upstreams
----------------------------------------------
    examples/extensions/<ext>/
        extension.json          the runtime manifest (untouched)
        upstream.json           pins + vendor spec (committed; see below)
        upstream/<name>/        generated, committed
            UPSTREAM-PROVENANCE.json
            <vendored files>

upstream.json
-------------
    {
      "schema": 1,
      "upstreams": [
        {
          "name": "zeek",
          "repo": "https://github.com/zeek/zeek",
          "track": "branch:master",     refresh re-resolves this
          "commit": "<40 hex>",         the pin; refresh writes it
          "license": "BSD-3-Clause",    SPDX, informational
          "paths": ["COPYING"]          files to vendor at `commit`
        }
      ]
    }

Subcommands
-----------
    refresh   resolve each `track` to its current commit and update
              `commit` in upstream.json when it changed. Idempotent:
              a tree already on latest reports "up to date" and
              writes nothing. This is the deliberate "pull latest"
              step -- run it, commit the pin bump, and every build
              after is reproducible against that pin.
    vendor    materialize upstream/<name>/ for every pin: fetch the
              declared paths at `commit`, write them, and write
              UPSTREAM-PROVENANCE.json. Enforces --max-bytes.
    check     vendor into a scratch dir and compare against what is
              committed; fail on any drift or on cap overflow. This
              is the CI guard -- it catches a pin bumped without a
              re-vendor, a hand-edited bundle, or a size blowout.

Fetching uses git with a blobless, sparse, shallow checkout, so only
the blobs for the declared paths cross the wire -- not the upstream
tree. Stdlib + the git binary only, like the rest of the project.

Usage:
    python tools/vendor_upstreams.py refresh [--root .] [--ext NAME]
    python tools/vendor_upstreams.py vendor  [--root .] [--max-bytes 5242880]
    python tools/vendor_upstreams.py check   [--root .] [--max-bytes 5242880]
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
import datetime

DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB, the whole vendored footprint
VENDOR_DIRNAME = "upstream"
MANIFEST = "upstream.json"
PROVENANCE = "UPSTREAM-PROVENANCE.json"
_HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")
_NAME_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_EXT_ROOT = os.path.join("examples", "extensions")


# --------------------------------------------------------------------------
# manifest handling
# --------------------------------------------------------------------------
def _fail(msg):
    raise SystemExit("vendor_upstreams: " + msg)


def _load_manifest(path):
    """Read and validate one upstream.json. Returns its upstream list."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        _fail(path + ": manifest must be a JSON object")
    if data.get("schema") != 1:
        _fail(path + ": schema must be 1")
    ups = data.get("upstreams")
    if not isinstance(ups, list) or not ups:
        _fail(path + ": upstreams must be a non-empty list")
    seen = set()
    for i, u in enumerate(ups):
        where = "%s: upstreams[%d]" % (path, i)
        if not isinstance(u, dict):
            _fail(where + " must be an object")
        name = u.get("name")
        if not isinstance(name, str) or not _NAME_RE.match(name):
            _fail(where + ".name must be a plain identifier")
        if name in seen:
            _fail(where + ": duplicate upstream name %r" % name)
        seen.add(name)
        repo = u.get("repo", "")
        if not isinstance(repo, str) or not repo.startswith("https://"):
            _fail(where + ".repo must be an https URL")
        track = u.get("track", "")
        if not isinstance(track, str) \
                or not re.match(r"\A(branch|tag):\S+\Z", track):
            _fail(where + ".track must be 'branch:NAME' or 'tag:NAME'")
        commit = u.get("commit", "")
        if commit and not _HEX40.match(commit):
            _fail(where + ".commit must be a 40-hex sha or empty")
        paths = u.get("paths")
        if not isinstance(paths, list) or not paths \
                or not all(isinstance(p, str) and p and ".." not in p
                           and not p.startswith("/") for p in paths):
            _fail(where + ".paths must be a list of repo-relative files")
    return data


def _iter_manifests(root, only_ext=None):
    """Yield (ext_name, manifest_path, data) for each upstream.json."""
    base = os.path.join(root, _EXT_ROOT)
    if not os.path.isdir(base):
        return
    for ext in sorted(os.listdir(base)):
        if only_ext and ext != only_ext:
            continue
        mpath = os.path.join(base, ext, MANIFEST)
        if os.path.isfile(mpath):
            yield ext, mpath, _load_manifest(mpath)


# --------------------------------------------------------------------------
# git plumbing (blobless, sparse, shallow -- only declared blobs transfer)
# --------------------------------------------------------------------------
def _git(args, cwd=None, check=True):
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1", GIT_TERMINAL_PROMPT="0")
    res = subprocess.run(["git"] + args, cwd=cwd, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True)
    if check and res.returncode != 0:
        _fail("git %s failed: %s" % (" ".join(args), res.stderr.strip()))
    return res


def resolve_commit(repo, track):
    """Resolve a track ('branch:master'/'tag:v1') to a commit sha.

    Annotated tags are peeled to the commit they name.
    """
    kind, name = track.split(":", 1)
    ref = "refs/heads/" + name if kind == "branch" else "refs/tags/" + name
    out = _git(["ls-remote", repo, ref, ref + "^{}"]).stdout
    peeled = None
    plain = None
    for line in out.splitlines():
        sha, got = line.split("\t", 1)
        if got.endswith("^{}"):
            peeled = sha
        else:
            plain = sha
    sha = peeled or plain
    if not sha or not _HEX40.match(sha):
        _fail("could not resolve %s %s" % (repo, track))
    return sha


def fetch_paths(repo, commit, paths, dest):
    """Check out exactly `paths` at `commit` into a fresh dest dir."""
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    _git(["init", "-q"], cwd=dest)
    _git(["remote", "add", "origin", repo], cwd=dest)
    _git(["config", "extensions.partialClone", "origin"], cwd=dest)
    _git(["sparse-checkout", "init", "--no-cone"], cwd=dest)
    _git(["sparse-checkout", "set", "--no-cone"] + list(paths), cwd=dest)
    _git(["fetch", "-q", "--depth", "1", "--filter=blob:none",
          "origin", commit], cwd=dest)
    _git(["checkout", "-q", commit], cwd=dest)


# --------------------------------------------------------------------------
# hashing / provenance
# --------------------------------------------------------------------------
def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _provenance(upstream, files, now):
    tree = hashlib.sha256()
    for rel, digest, _n in files:
        tree.update(("%s %s\n" % (digest, rel)).encode("utf-8"))
    return {
        "upstream": upstream["name"],
        "repo": upstream["repo"],
        "track": upstream["track"],
        "commit": upstream["commit"],
        "license": upstream.get("license", "unknown"),
        "fetched_at": now,
        "files": [{"path": rel, "sha256": d, "bytes": n}
                  for rel, d, n in files],
        "tree_sha256": tree.hexdigest(),
        "stamp": "tools/vendor_upstreams.py",
    }


def vendor_one(upstream, out_dir, now):
    """Fetch + write one upstream's bundle into out_dir/<name>/.

    Returns (provenance_dict, total_bytes).
    """
    if not upstream.get("commit"):
        _fail("%s has no commit pin; run 'refresh' first"
              % upstream["name"])
    name = upstream["name"]
    target = os.path.join(out_dir, name)
    with tempfile.TemporaryDirectory(prefix="vendor-") as scratch:
        fetch_paths(upstream["repo"], upstream["commit"],
                    upstream["paths"], scratch)
        if os.path.exists(target):
            shutil.rmtree(target)
        os.makedirs(target)
        files = []
        for rel in sorted(upstream["paths"]):
            src = os.path.join(scratch, rel)
            if not os.path.isfile(src):
                _fail("%s: path %r absent at %s"
                      % (name, rel, upstream["commit"][:12]))
            dst = os.path.join(target, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            files.append((rel, _sha256_file(dst), os.path.getsize(dst)))
    prov = _provenance(upstream, files, now)
    with open(os.path.join(target, PROVENANCE), "w", encoding="utf-8") as fh:
        json.dump(prov, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return prov, _dir_bytes(target)


def _dir_bytes(path):
    total = 0
    for root, _d, names in os.walk(path):
        for n in names:
            total += os.path.getsize(os.path.join(root, n))
    return total


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------
def cmd_refresh(args):
    """Re-resolve every pin. A single unresolvable upstream is
    reported and the rest still refresh; the command exits non-zero
    if any failed, so a typo in one track never silently strands the
    others on a stale pin."""
    changed = 0
    failed = []
    for ext, mpath, data in _iter_manifests(args.root, args.ext):
        dirty = False
        for u in data["upstreams"]:
            try:
                new = resolve_commit(u["repo"], u["track"])
            except SystemExit as exc:
                failed.append("%s/%s: %s" % (ext, u["name"], exc))
                print("%s/%s: FAILED to resolve" % (ext, u["name"]))
                continue
            if new != u.get("commit"):
                print("%s/%s: %s -> %s"
                      % (ext, u["name"], (u.get("commit") or "unpinned")[:12],
                         new[:12]))
                u["commit"] = new
                dirty = True
                changed += 1
            else:
                print("%s/%s: up to date (%s)"
                      % (ext, u["name"], new[:12]))
        if dirty:
            with open(mpath, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
    print("refresh: %d pin(s) updated" % changed)
    if failed:
        for f in failed:
            print("  unresolved: " + f)
        _fail("%d upstream(s) did not resolve" % len(failed))
    return 0


def _vendor_all(root, out_root_for):
    """Vendor every manifest; out_root_for(ext_dir) picks the dest.

    Returns (total_bytes, count).
    """
    now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    total = 0
    count = 0
    for ext, mpath, data in _iter_manifests(root):
        ext_dir = os.path.dirname(mpath)
        out_dir = out_root_for(ext_dir)
        for u in data["upstreams"]:
            _prov, nbytes = vendor_one(u, out_dir, now)
            total += nbytes
            count += 1
            print("vendored %s/%s (%d bytes)" % (ext, u["name"], nbytes))
    return total, count


def cmd_vendor(args):
    total, count = _vendor_all(
        args.root,
        lambda ext_dir: os.path.join(ext_dir, VENDOR_DIRNAME))
    print("vendor: %d upstream(s), %d bytes total (cap %d)"
          % (count, total, args.max_bytes))
    if total > args.max_bytes:
        _fail("vendored footprint %d exceeds cap %d"
              % (total, args.max_bytes))
    return 0


def cmd_verify(args):
    """Offline guard: validate the committed bundles without touching
    the network. For every upstream it recomputes each vendored
    file's hash and the tree hash and compares them to what
    UPSTREAM-PROVENANCE.json records, confirms the provenance commit
    matches the manifest pin, and enforces the size cap. This is the
    per-build gate -- it catches a hand-edited bundle, a pin bumped
    without a re-vendor, or a size blowout, and it never depends on
    an upstream being reachable. Use 'check' (online) to also confirm
    the bytes still match the pinned commit upstream."""
    problems = []
    total = 0
    count = 0
    for ext, _mpath, data in _iter_manifests(args.root):
        ext_dir = os.path.join(args.root, _EXT_ROOT, ext)
        for u in data["upstreams"]:
            count += 1
            bundle = os.path.join(ext_dir, VENDOR_DIRNAME, u["name"])
            ppath = os.path.join(bundle, PROVENANCE)
            if not os.path.isfile(ppath):
                problems.append("%s/%s: no vendored bundle (run 'vendor')"
                                % (ext, u["name"]))
                continue
            with open(ppath, encoding="utf-8") as fh:
                prov = json.load(fh)
            if prov.get("commit") != u.get("commit"):
                problems.append("%s/%s: provenance commit %s != manifest pin "
                                "%s (re-vendor after refresh)"
                                % (ext, u["name"],
                                   (prov.get("commit") or "?")[:12],
                                   (u.get("commit") or "?")[:12]))
            tree = hashlib.sha256()
            for entry in prov.get("files", []):
                fp = os.path.join(bundle, entry["path"])
                if not os.path.isfile(fp):
                    problems.append("%s/%s: %s listed but absent"
                                    % (ext, u["name"], entry["path"]))
                    continue
                digest = _sha256_file(fp)
                if digest != entry["sha256"]:
                    problems.append("%s/%s: %s hash mismatch"
                                    % (ext, u["name"], entry["path"]))
                tree.update(("%s %s\n" % (digest, entry["path"]))
                            .encode("utf-8"))
            if tree.hexdigest() != prov.get("tree_sha256"):
                problems.append("%s/%s: tree_sha256 mismatch"
                                % (ext, u["name"]))
            total += _dir_bytes(bundle)
    if total > args.max_bytes:
        problems.append("vendored footprint %d exceeds cap %d"
                        % (total, args.max_bytes))
    if problems:
        for p in problems:
            print("FAIL: " + p)
        _fail("%d problem(s) in committed bundles" % len(problems))
    print("verify: %d upstream(s) consistent, %d bytes total (cap %d)"
          % (count, total, args.max_bytes))
    return 0


def cmd_check(args):
    """Regenerate into scratch and diff against the committed tree."""
    with tempfile.TemporaryDirectory(prefix="vendor-check-") as scratch:
        mapping = {}

        def out_for(ext_dir):
            d = os.path.join(scratch, os.path.basename(ext_dir))
            mapping[ext_dir] = d
            return d

        total, count = _vendor_all(args.root, out_for)
        if total > args.max_bytes:
            _fail("vendored footprint %d exceeds cap %d"
                  % (total, args.max_bytes))
        drift = []
        for ext_dir, fresh in mapping.items():
            committed = os.path.join(ext_dir, VENDOR_DIRNAME)
            drift += _diff_trees(committed, fresh)
    if drift:
        for d in drift:
            print("DRIFT: " + d)
        _fail("%d vendored file(s) differ from committed; "
              "run 'vendor' and commit" % len(drift))
    print("check: %d upstream(s) match, %d bytes total (cap %d)"
          % (count, total, args.max_bytes))
    return 0


def _compare_digest(path):
    """Digest used for drift detection.

    For a provenance file the capture timestamp is volatile by
    design, so it is dropped before hashing: the pin (commit), the
    per-file hashes and tree_sha256 are still compared exactly, so a
    changed upstream or a hand-edited bundle is still caught -- only
    the clock is forgiven.
    """
    if os.path.basename(path) == PROVENANCE:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data.pop("fetched_at", None)
        norm = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()
    return _sha256_file(path)


def _diff_trees(committed, fresh):
    """Return human diffs between two vendored trees (ignores mtime
    and the provenance capture timestamp)."""
    out = []
    cset = _rel_set(committed)
    fset = _rel_set(fresh)
    for rel in sorted(fset - cset):
        out.append("missing from commit: " + rel)
    for rel in sorted(cset - fset):
        out.append("committed but not produced: " + rel)
    for rel in sorted(cset & fset):
        cf = os.path.join(committed, rel)
        ff = os.path.join(fresh, rel)
        if _compare_digest(cf) != _compare_digest(ff):
            out.append("content differs: " + rel)
    return out


def _rel_set(root):
    s = set()
    if not os.path.isdir(root):
        return s
    for base, _d, names in os.walk(root):
        for n in names:
            s.add(os.path.relpath(os.path.join(base, n), root))
    return s


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", default=".",
                   help="repository root (default: .)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("refresh", help="re-resolve pins to latest")
    pr.add_argument("--ext", help="limit to one extension dir name")
    pr.set_defaults(func=cmd_refresh)

    pv = sub.add_parser("vendor", help="materialize committed bundles")
    pv.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    pv.set_defaults(func=cmd_vendor)

    pf = sub.add_parser("verify",
                        help="offline guard: committed hashes + size cap")
    pf.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    pf.set_defaults(func=cmd_verify)

    pc = sub.add_parser("check",
                        help="online guard: re-fetch pins + drift + cap")
    pc.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    pc.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
