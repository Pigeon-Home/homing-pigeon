#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Write the build stamp into a runner tree about to be packaged.

Usage:
    python runner/tools/build_stamp.py --tree <dir> --commit <hex>

<dir> is a tree containing runner/ (a checkout, an extracted
preview build, or a rig test deployment). The stamp lands in
<dir>/runner/_build.py as __build__; beside it lands __checksum__,
a single SHA-384 over the tree manifest -- one line per covered
file, "<path> <sha384 of its bytes>", sorted by path -- so the
exact tree that ran can be derived from that one checksum. The
manifest covers every file under runner/ except the stamp
carrier itself (runner/_build.py, whose content is the stamp)
and Python bytecode (__pycache__ directories and .pyc/.pyo
files). The identity banner (runner/ops/identity.py) prints both
values at the head of every log and in --version, so a log
names the exact code that ran. Release tooling, preview-build
zippers, and test deployments all stamp through here, so the
file's shape has one writer.
"""
import argparse
import hashlib
import os
import re
import sys

_STAMP_RE = re.compile(r"^[0-9a-f]{7,64}$")

_TEMPLATE = '''"""Build identity for this runner tree.

Written by the build tooling (runner/tools/build_stamp.py) when a
tree is packaged -- a release build, a preview build, or a rig
test deployment -- with the source commit the tree was built
from (__build__) and a single SHA-384 checksum over the runner
tree's manifest (__checksum__), from which the exact tree that
ran can be derived. A plain source checkout carries "unknown"
for both, and the identity banner (runner/ops/identity.py) prints
the version, platform and Python in full beside those unknowns.
The runner never shells out to git at runtime to discover this:
what is stamped here is what was built, and a log reader can tell
at a glance which code is executing.
"""

__build__ = "%s"
__checksum__ = "%s"
'''


def tree_checksum(tree):
    """SHA-384 over the manifest of <tree>/runner/.

    One line per covered file -- "<path> <sha384 hex>" with the
    path relative to <tree> and sorted -- hashed as UTF-8. The
    stamp carrier (runner/_build.py) and Python bytecode are
    not covered, so restamping a tree never moves its checksum;
    changing any covered file does.
    """
    runner_dir = os.path.join(tree, "runner")
    lines = []
    for root, dirs, files in os.walk(runner_dir):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            if name.endswith((".pyc", ".pyo")):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, tree).replace(os.sep, "/")
            if rel == "runner/_build.py":
                continue
            digest = hashlib.sha384()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    digest.update(chunk)
            lines.append("%s %s\n" % (rel, digest.hexdigest()))
    lines.sort()
    return hashlib.sha384("".join(lines).encode("utf-8")).hexdigest()


def write_build_stamp(tree, commit):
    """Stamp <tree>/runner/_build.py with `commit` and the tree
    checksum. Returns the path."""
    if not isinstance(commit, str) or not _STAMP_RE.match(commit):
        raise ValueError("commit must be 7-64 lowercase hex characters")
    runner_dir = os.path.join(tree, "runner")
    if not os.path.isdir(runner_dir):
        raise ValueError("no runner/ directory under %r" % (tree,))
    checksum = tree_checksum(tree)
    path = os.path.join(runner_dir, "_build.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_TEMPLATE % (commit, checksum))
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tree", required=True)
    ap.add_argument("--commit", required=True)
    args = ap.parse_args(argv)
    try:
        path = write_build_stamp(args.tree, args.commit)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
