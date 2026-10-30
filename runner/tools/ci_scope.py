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
    "docs/project/campaign-standing-orders.md",
    "docs/seats/.com.chat",
    "docs/seats/status.txt",
)
ZERO = "0" * 40


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


def decide(event, before, after, run=subprocess.run):
    """'true' or 'false' for the corpus_only output."""
    if event != "push" or not after or after.startswith("refs/tags/"):
        return "false"
    paths = changed_paths(before, after, run=run)
    if paths is None:
        return "false"
    return "true" if corpus_only(paths) else "false"


def main(argv=None, environ=None, out=print):
    env = os.environ if environ is None else environ
    verdict = decide(env.get("EVENT", ""), env.get("BEFORE", ""),
                     env.get("AFTER", ""))
    out(f"corpus_only={verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
