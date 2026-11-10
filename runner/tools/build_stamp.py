#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Write the build stamp into a runner tree about to be packaged.

Usage:
    python runner/tools/build_stamp.py --tree <dir> --commit <hex>

<dir> is a tree containing runner/ (a checkout, an extracted
preview build, or a rig test deployment). The stamp lands in
<dir>/runner/_build.py as __build__; the startup log prints it
beside the version ("homing-pigeon 3.15.20.19 (build c0ba079d)
starting ..."), so a log names the exact code that ran. Release
tooling, preview-build zippers, and test deployments all stamp
through here, so the file's shape has one writer.
"""
import argparse
import os
import re
import sys

_STAMP_RE = re.compile(r"^[0-9a-f]{7,64}$")

_TEMPLATE = '''"""Build identity for this runner tree.

Written by the build tooling (runner/tools/build_stamp.py) when a
tree is packaged -- a release build, a preview build, or a rig
test deployment -- with the source commit the tree was built
from. A plain source checkout carries "unknown", and the startup
log then prints the version alone, with no build parenthetical.
The runner never shells out to git at runtime to discover this:
what is stamped here is what was built, and a log reader can tell
at a glance which code is executing.
"""

__build__ = "%s"
'''


def write_build_stamp(tree, commit):
    """Stamp <tree>/runner/_build.py with `commit`. Returns the path."""
    if not isinstance(commit, str) or not _STAMP_RE.match(commit):
        raise ValueError("commit must be 7-64 lowercase hex characters")
    runner_dir = os.path.join(tree, "runner")
    if not os.path.isdir(runner_dir):
        raise ValueError("no runner/ directory under %r" % (tree,))
    path = os.path.join(runner_dir, "_build.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_TEMPLATE % commit)
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
