#!/usr/bin/env python3
# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""What a push changed, for build.yml's scope job (de_dust2, P8).

A push that touches only the fuzz corpus and the campaign's ledgers
(the rigs' banks, several an hour) does not need two macOS legs, two
Windows legs, two ARM legs and the packaging to be believed: the
Linux `test` job replays the corpus and carries its crash probes, and
that is the whole of what such a push can break. This prints
`corpus_only=true` for such a push and `corpus_only=false` for every
other event: a code or doc change, a tag, a dispatch, a push whose
`before` is unknown (a new branch, a force push), or a diff git
cannot produce. The heavy jobs read the output and skip when it is
true; a release commit changes pyproject.toml and is never corpus
only, so the release gate still sees a full matrix on its sha.

Usage (in the workflow): BEFORE, AFTER and EVENT in the environment,
the output appended to $GITHUB_OUTPUT.
"""
import fnmatch
import os
import subprocess
import sys

CORPUS_ONLY = (
    "runner/tests/de_dust/*.jsonl",
    "runner/tests/de_dust/*.arcs.json",
    "runner/tests/de_dust/*.retired.json",
    "docs/infrastructure-documents/project/campaign-standing-orders.md",
    "docs/infrastructure-documents/seats/.com.chat",
    "docs/steady/seats/status.txt",
)
ZERO = "0" * 40

# A push that changes only documentation (build.yml's docs group reads
# the same rule from the push event's file list): anything under docs/, the
# manuals at the root, and the ledgers above. The desk lands these
# several times an hour, and each one was starting (and, under a
# cancelling concurrency group, cancelling) a full matrix whose
# every leg ignores them. Such a push runs the documentation guards
# alone (build.yml's `docs` job); a code path anywhere in the push
# runs the matrix.
DOCS_ONLY = CORPUS_ONLY + (
    "docs/*",
    "*.md",
)


def docs_only(paths):
    """True when every changed path is documentation or a ledger and
    at least one path changed. A root *.md and anything under docs/
    count; a path with a directory part outside docs/ does not."""
    paths = [p for p in paths if p]
    if not paths:
        return False
    for p in paths:
        if any(fnmatch.fnmatch(p, pat) for pat in CORPUS_ONLY):
            continue
        if p.startswith("docs/"):
            continue
        if "/" not in p and p.endswith(".md"):
            continue
        return False
    return True


def corpus_only(paths):
    """True when every changed path is a corpus or ledger file and at
    least one path changed."""
    paths = [p for p in paths if p]
    if not paths:
        return False
    return all(any(fnmatch.fnmatch(p, pat) for pat in CORPUS_ONLY)
               for p in paths)


def changed_paths(before, after, run=subprocess.run):
    """The paths `git diff --name-only before after` reports, or None
    when the range cannot be read."""
    if not before or not after or set(before) == {"0"}:
        return None
    try:
        proc = run(["git", "diff", "--name-only", before, after],
                   capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.split("\n")


def decide(event, before, after, run=subprocess.run, rule=None):
    """'true' or 'false' for the corpus_only output (``rule`` names
    another path rule, docs_only, for its own output)."""
    rule = corpus_only if rule is None else rule
    if event != "push" or not after or after.startswith("refs/tags/"):
        return "false"
    paths = changed_paths(before, after, run=run)
    if paths is None:
        return "false"
    return "true" if rule(paths) else "false"


def main(argv=None, environ=None, out=print):
    env = os.environ if environ is None else environ
    args = (env.get("EVENT", ""), env.get("BEFORE", ""),
            env.get("AFTER", ""))
    out(f"corpus_only={decide(*args)}")
    out(f"docs_only={decide(*args, rule=docs_only)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
