# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
"""Choose which platform legs run for this event.

A push or a pull request runs the core legs that sit on a
plentiful runner (ubuntu-latest, including the qemu containers
that run there). macOS, Windows, and ARM hosted runners are
scarce. Asking for one on every push stacked a queue that never
drained, and the Intel macOS leg was still named macos-13, which
GitHub retired in December 2025, so that copy never started.

The nightly schedule and a manual dispatch run the whole corpus,
scarce runners included. That is the frequent full pass. A push
stays the pass that can actually start.

A leg may set "pool" to "scarce" or "plentiful" to override the
rule the runner name implies.
"""
import json
import os

FULL_EVENTS = ("schedule", "workflow_dispatch")


def runner_is_scarce(runner):
    """Hosted runners GitHub does not hand out like ubuntu-latest."""
    runner = runner or ""
    if runner.startswith(("macos-", "windows-")):
        return True
    if runner.endswith("-arm"):
        return True
    return False


def is_scarce(entry):
    pool = entry.get("pool")
    if pool == "plentiful":
        return False
    if pool == "scarce":
        return True
    return runner_is_scarce(entry.get("runner"))


def choose(legs, event_name):
    """{job: [leg, ...]} for this event. Full corpus, or cheap core."""
    full = event_name in FULL_EVENTS
    picked = {}
    for job, entries in legs.items():
        if full:
            picked[job] = list(entries)
        else:
            picked[job] = [
                e for e in entries
                if e.get("tier") == "core" and not is_scarce(e)
            ]
    return picked


def main():
    legs = json.load(open(".github/platform-legs.json"))
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    picked = choose(legs, event)
    out = []
    for job, entries in picked.items():
        out.append("%s=%s" % (job, json.dumps({"include": entries})))
        out.append("%s_count=%d" % (job, len(entries)))
    with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
        fh.write("\n".join(out) + "\n")
    print("tier:", "full" if event in FULL_EVENTS else "push-core",
          {j: len(v) for j, v in picked.items()})


if __name__ == "__main__":
    main()
