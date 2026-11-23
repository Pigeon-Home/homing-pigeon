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

Filled in after the fix lands, in this same place.
