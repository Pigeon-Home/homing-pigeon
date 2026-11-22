"""Plan the Snap Store release step for one Homing Pigeon release.

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

The release train already builds the snap with no hands: the
snapcraft.io build service watches the repository, finds
snap/snapcraft.yaml, and Launchpad builds every new head into
fresh revisions in the store. What was missing is the step
after the build: releasing the newest revisions to a channel.
That step was done by hand on the store's Releases page, and
the page fight is what this tool replaces.

The tool is a planner, not a publisher. Given the store state
for the snap (the shape the store API and the Releases page
both carry: one entry per revision, with its architecture, its
version, its review status and the channels it already sits
in), it works out the release for one version:

- both architectures (amd64 and arm64) must stand uploaded at
  that version before anything is released; a half built
  release is refused, never released one leg at a time;
- while any revision at that version still stands in review
  (ReviewQueued and its kin), the plan is a refusal that names
  the hold, because the store disables the release controls
  until the review clears; the caller reports the hold and
  tries again on the next cycle instead of fighting the page;
- once the review has cleared, the plan is the two store
  commands that release the amd64 and arm64 revisions to the
  target channels, in architecture order.

Nothing here opens a socket or runs a command. The pipeline
step that carries the plan out runs the printed commands with
the store credentials it already holds (see
docs/steady/design/auto-publish-design.md). Keeping the
decision pure is what lets the tests below pin it.
"""

import argparse
import json
import sys

ARCHES = ("amd64", "arm64")
DEFAULT_CHANNELS = ("latest/stable", "latest/edge")

# Review states in which the store will not release a revision.
# The store disables the release controls and closes release
# attempts with no effect while a revision stands in one of
# these; 3.17.32.11's revisions stood at ReviewQueued.
HELD_STATES = frozenset({
    "ReviewQueued",
    "ReviewInProgress",
    "ReviewPending",
    "ManualReviewPending",
})


def plan_release(revisions, version, channels=DEFAULT_CHANNELS):
    """Return the release plan for one version.

    revisions: an iterable of mappings with the keys revision
    (int), architecture (str), version (str), status (str) and
    channels (an iterable of channel names, possibly empty).

    The plan is a mapping: {"ok": bool, "reason": str,
    "commands": [str, ...]}. ok is False with an empty command
    list whenever the release must not be attempted yet.
    """
    channels = tuple(channels)
    at_version = [r for r in revisions if r.get("version") == version]
    if not at_version:
        return {
            "ok": False,
            "reason": "no revision stands uploaded at version %s" % version,
            "commands": [],
        }
    by_arch = {}
    for rev in at_version:
        arch = rev.get("architecture")
        if arch in ARCHES:
            current = by_arch.get(arch)
            if current is None or rev["revision"] > current["revision"]:
                by_arch[arch] = rev
    missing = [a for a in ARCHES if a not in by_arch]
    if missing:
        return {
            "ok": False,
            "reason": "version %s is missing an uploaded revision for %s"
                      % (version, ", ".join(missing)),
            "commands": [],
        }
    held = [a for a in ARCHES if by_arch[a].get("status") in HELD_STATES]
    if held:
        return {
            "ok": False,
            "reason": "the store review still holds the %s revision (%s); "
                      "the release controls stay disabled until it clears"
                      % (", ".join(held),
                         ", ".join(sorted({by_arch[a]["status"]
                                           for a in held}))),
            "commands": [],
        }
    commands = []
    for arch in ARCHES:
        rev = by_arch[arch]
        already = set(rev.get("channels") or ())
        todo = [c for c in channels if c not in already]
        if todo:
            commands.append(
                "snapcraft release homing-pigeon %d %s"
                % (rev["revision"], ",".join(todo)))
    if not commands:
        return {
            "ok": True,
            "reason": "version %s already stands released to %s"
                      % (version, ", ".join(channels)),
            "commands": [],
        }
    return {
        "ok": True,
        "reason": "release version %s to %s"
                  % (version, ", ".join(channels)),
        "commands": commands,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Plan the Snap Store release for one version.")
    parser.add_argument("--state", required=True,
                        help="path to a JSON file holding the store state: "
                             "a list of revision entries")
    parser.add_argument("--version", required=True,
                        help="the version to release, e.g. 3.17.32.13")
    parser.add_argument("--channels", default=",".join(DEFAULT_CHANNELS),
                        help="comma separated channels to release to")
    args = parser.parse_args(argv)
    with open(args.state, encoding="utf-8") as fh:
        revisions = json.load(fh)
    plan = plan_release(revisions, args.version,
                        channels=tuple(args.channels.split(",")))
    print(plan["reason"])
    for command in plan["commands"]:
        print(command)
    return 0 if plan["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
