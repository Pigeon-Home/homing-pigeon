#!/usr/bin/env python3
"""Name any tracked file a commit cut down to a fraction of itself.

Two files on main were rewritten to a fraction of their lines on
2026-11-11 -- runner/ops/install.py to 309 of 3,824, then
runner/guard/macos_confine.py to 219 of 798 -- by edits that
wrote a file's head and dropped the rest. The suite found both,
one leg and one import error at a time; this guard names the
file and the commit directly, in the build's first minute.

    python3 runner/tools/shrink_guard.py                 # HEAD against its parent
    python3 runner/tools/shrink_guard.py --commit REV    # REV against its parent
    python3 runner/tools/shrink_guard.py --working-tree  # the index and work tree against HEAD

A finding is a tracked text file that lost at least SHRINK_LINES
lines and at least SHRINK_FRACTION of what it had, deletion of
the whole file included. A commit that means to cut a file that
far says so with a trailer line in its message:

    Shrink-OK: runner/ops/old_module.py

(one per line; a path or a glob), or the caller passes --allow.
Binary files, new files, and a first commit with no parent are
never findings. Exit 0 with nothing to report, 1 with findings,
2 when git cannot answer. Under GitHub Actions each finding is
also an ::error annotation on the file.
"""

import argparse
import fnmatch
import os
import re
import subprocess
import sys

SHRINK_LINES = 100
SHRINK_FRACTION = 0.25
_TRAILER_RE = re.compile(r"^\s*shrink-ok:\s*(\S.*?)\s*$", re.I | re.M)


def _git(root, *args):
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args),
                                           proc.stderr.strip()))
    return proc.stdout


def _line_count(root, rev, path):
    """Lines of `path` at `rev` (the working tree when rev is None)."""
    if rev is None:
        full = os.path.join(root, path)
        if not os.path.isfile(full):
            return 0
        with open(full, "rb") as fh:
            data = fh.read()
    else:
        proc = subprocess.run(["git", "show", "%s:%s" % (rev, path)],
                              cwd=root, capture_output=True)
        if proc.returncode != 0:
            return 0
        data = proc.stdout
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def allowed_from_message(message):
    """The Shrink-OK paths and globs a commit message carries."""
    return [m.strip() for m in _TRAILER_RE.findall(message or "")]


def _is_allowed(path, allowed):
    return any(path == pat or fnmatch.fnmatchcase(path, pat)
               for pat in allowed)


def findings(root, old_rev, new_rev, allowed=(), lines=SHRINK_LINES,
             fraction=SHRINK_FRACTION):
    """(path, old_lines, new_lines) for every file cut past the bound.

    `new_rev` None compares the index and the working tree against
    `old_rev`. Binary files (numstat prints "-") and files that
    only grew are skipped.
    """
    if new_rev is None:
        numstat = _git(root, "diff", "--numstat", old_rev)
    else:
        numstat = _git(root, "diff", "--numstat", old_rev, new_rev)
    out = []
    for line in numstat.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        if added == "-" or deleted == "-":
            continue
        if int(deleted) == 0:
            continue
        # a rename shows as "old => new" in braces or plain
        if " => " in path:
            path = re.sub(r"\{([^{}]*) => ([^{}]*)\}", r"\2", path)
            if " => " in path:
                path = path.split(" => ", 1)[1]
        old = _line_count(root, old_rev, path)
        new = _line_count(root, new_rev, path)
        if old == 0 or new >= old:
            continue
        lost = old - new
        if lost >= lines and lost >= fraction * old and \
                not _is_allowed(path, allowed):
            out.append((path, old, new))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=None,
                        help="the checkout (default: the one this tool is in)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--commit", default=None, metavar="REV",
                      help="compare REV to its first parent (default HEAD)")
    mode.add_argument("--working-tree", action="store_true",
                      help="compare the index and work tree to HEAD")
    parser.add_argument("--allow", action="append", default=[],
                        metavar="PATH", help="a path or glob that may shrink")
    parser.add_argument("--lines", type=int, default=SHRINK_LINES)
    parser.add_argument("--fraction", type=float, default=SHRINK_FRACTION)
    args = parser.parse_args(argv)
    root = args.root or os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    try:
        if args.working_tree:
            old_rev, new_rev, label = "HEAD", None, "the working tree"
            allowed = list(args.allow)
        else:
            rev = args.commit or "HEAD"
            new_rev = _git(root, "rev-parse", "--verify", rev + "^{commit}").strip()
            parents = _git(root, "rev-list", "--parents", "-n", "1",
                           new_rev).split()[1:]
            if not parents:
                print("shrink guard: %s has no parent; nothing to compare"
                      % new_rev[:12])
                return 0
            old_rev = parents[0]
            label = "commit " + new_rev[:12]
            message = _git(root, "log", "-1", "--format=%B", new_rev)
            allowed = list(args.allow) + allowed_from_message(message)
        found = findings(root, old_rev, new_rev, allowed,
                         lines=args.lines, fraction=args.fraction)
    except RuntimeError as exc:
        print("shrink guard: %s" % exc, file=sys.stderr)
        return 2
    if not found:
        print("shrink guard: no tracked file lost %d+ lines and %d%%+ of "
              "itself in %s" % (args.lines, round(args.fraction * 100), label))
        return 0
    under_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    for path, old, new in found:
        text = ("%s: %d lines to %d in %s (%d%% gone); a cut this deep "
                "is said in the commit message as 'Shrink-OK: %s' when "
                "it is meant" % (path, old, new, label,
                                 round(100.0 * (old - new) / old), path))
        print("shrink guard: " + text)
        if under_actions:
            print("::error file=%s,title=file cut down::%s" % (path, text))
    return 1


if __name__ == "__main__":
    sys.exit(main())
