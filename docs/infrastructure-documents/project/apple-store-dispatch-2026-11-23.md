# Apple store dispatch: supposition, 2026-11-23

Written before the fix, at the owner's direction to act on the
outside review of the store legs forwarded on 2026-11-23.

## The gap

The macos-store workflow starts on a published release event.
The release job in build.yml publishes through
softprops/action-gh-release under the default GITHUB_TOKEN.
GitHub does not start a new workflow run for an event raised by
that token, workflow_dispatch being the stated exception, and
cut-release.yml already relies on that exception for the same
reason. So a release this pipeline publishes raises no
macos-store run at all. The one upload that stands, on
2026-11-22, followed a dispatch by hand.

A second gap rides with it. When the planner refuses for want
of signing material, the plan step writes a summary, sets
PLAN_OK to false and exits 0. The run stands green although
nothing was uploaded, and a green run reads as an upload to
anyone scanning the run list.

## Suppositions

S1. A job inside build.yml that needs the release job, gated
on the release job's success on a version tag, and that runs
gh workflow run for macos-store.yml with the release's version
as its input, will start exactly one store run per published
release, because workflow_dispatch from GITHUB_TOKEN is the
one trigger GitHub allows that token.

S2. The dispatch belongs in build.yml beside the proofs job,
not in cut-release.yml, because build.yml is where the release
actually publishes: every path that publishes (a promoted tag
build, a full tag build) passes through its release job,
while a cut is only one of the ways a tag comes to stand.

S3. Making the plan step fail on a planner refusal (exit code
3 from runner/tools/apple_store.py), with an error annotation
naming the refusal and a summary headed NOT uploaded, ends
the green run that looks like an upload: the run stands red
whenever the material is short, and green only when the plan
ran and its commands were carried out.

S4. Tests reading the two workflow files as text can pin all
of this: the dispatch job's needs, gate, permissions and
command, and the plan step's failure on a refusal.

## Conclusions

S1 and S2 stand as built. build.yml gained a
macos-store-dispatch job beside the proofs job: it needs
only the release job, runs on a version tag when that job
succeeded, holds actions: write and nothing wider, and runs
gh workflow run for macos-store.yml on main with the tag's
version as the input. The store workflow keeps its release
event trigger for releases a person or an honoured token
publishes, and its hand dispatch for a chosen version.

S3 stands as built. The plan step in macos-store.yml now
answers a planner refusal with an error annotation naming
the refusal, a summary headed NOT uploaded, and exit 1.
PLAN_OK still gates the keychain and command steps, which
only a successful plan reaches.

S4 stands. runner/tests/test_apple_store.py gained two
tests, written before the fix and red against the old
workflows (7 run, 2 failed, both new). After the fix the
apple store modules pass whole (67 tests) and the build
configuration suite passes whole (82 tests). Both workflow
files parse as YAML.

One limit, stated plainly: the dispatch itself can only be
exercised live by the next published release. What stands
proven here is the wiring, pinned by tests in the shape the
proofs dispatch already runs in production.
