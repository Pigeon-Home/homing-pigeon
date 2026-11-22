# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
# Automatic publishing to the stores: design

Opened on 2026-11-21 at the conductor's direction. His words:
the pipelines should publish to all these places when we do a
new release, instead of each storefront being pushed by hand,
one at a time, after the fact. This page is the design for
that. The per store preparation stands in
docs/steady/design/app-stores-design.md and, for the Snap
Store, in docs/steady/project/snap-store-readiness.md; this
page covers only the automation that ties the stores to the
release train.

## Where things stand, store by store

The release train itself is automatic end to end. A cut tags
the version, the tag build publishes the GitHub release with
its 13 assets, and PyPI, SourceForge, GitLab and the Docker
image follow from the same tag. The GitHub release is the
shelf every other route reads from, and it is the trigger
this design hangs the store legs on.

The Snap leg is half automatic already, by accident of how
the store works. The snapcraft.io build service watches the
repository, finds snap/snapcraft.yaml where the conductor
placed it on 2026-11-20, and Launchpad builds each new head
into fresh store revisions with no hands at all: the
3.17.32.13 head produced revisions 20 (amd64) and 21 (arm64)
on 2026-11-21 by this path alone. What is not automatic is
the step after the build: releasing those revisions to a
channel. That step sat on the store's Releases page, worked
by hand, and the store's classic confinement review holds
every revision until it clears: revisions stand at
ReviewQueued, the release controls stand disabled, and
release attempts close with no effect and no error. The
classic grant itself is a forum process, described in the
readiness page; it is a one time gate, not a per release one.

The Apple leg has no store listing at all, by the verdict in
the preparation notes: the Mac App Store's sandbox cannot
hold the runner, so the route is Developer ID signing,
notarization and stapling, distributed from our own shelf.
The conductor has directed that a store submission be
attempted anyway and Apple's own review be allowed to give
the answer. His enrollment stands active as an individual
with the agreements accepted (2026-11-21). The signing
requests stand generated on our side. The one step that
needs his hands is creating the Developer ID certificates in
his portal; only the account holder can create them.

The Microsoft leg waits on Microsoft. The Partner Center
account stands created in his name, the vetting submission
stands in with the publisher name pigeon-home.ai, and the
verification summary reads In Progress. The route is Route A
from the stores design page: the unpackaged installer
listing, which takes the product as it ships. Its two gaps
stand as that page records them: a single signed installer
executable, and a signing certificate in his name.

## The supposition, written before the build

Supposition: once each store's one time gate has cleared,
every later release can reach that store with no hands,
because each store offers a machine route for the repeat
steps and none of the repeat steps is a fresh review of the
publisher. The Snap release step is a store command once the
classic declaration stands. The Apple repeat steps are
signing and notarization, both machine run once the
certificates exist. The Microsoft repeat step is a new
submission carrying a new versioned installer address, which
Partner Center accepts through its submission route. What
would prove this wrong: a store that re-reviews the
publisher, rather than the package, on every release. The
first release through each gate is the test of it, and this
page will carry the conclusion against the numbers when the
first one lands.

## The design

One trigger: the published GitHub release. A store leg runs
after the release stands verified, reads the version from
the release, and does its store's steps. A leg that cannot
finish says so in the release record and tries again on the
standing 15 minute loop; it never holds the release itself
back, and it never reports the store as published until the
store's own page or API shows it.

### Snap leg

1. Build: already automatic. The build service builds each
   head from snap/snapcraft.yaml; a release cut is a head,
   so the revisions for the release version stand uploaded
   by the time the GitHub release is verified. No change.
2. Release: new. runner/tools/store_release.py plans the
   step from the store state: both architectures must stand
   uploaded at the release version, no revision at that
   version may stand in a review hold, and the plan is the
   two store commands that release the amd64 and arm64
   revisions to latest/stable and latest/edge. While the
   classic review holds, the plan is a refusal that names
   the hold, and the loop reports the block instead of
   fighting the page. The commands run under the store
   credentials the pipeline holds; the credential minting
   question stands as the build log records it, and until
   the pipeline holds a credential the planner's output is
   what the operator runs by hand, word for word.
3. The classic grant stays a one time, owner side process.
   No automation files the forum request or sits the
   vetting; once the declaration stands, step 2 is the whole
   per release work.

### Apple leg

1. Certificates: one time, his hands, in his portal, from
   the signing requests already generated. The private keys
   and the notarization credential then live as CI secrets.
2. Per release, in the macOS build legs that already exist:
   sign the executables with the Developer ID Application
   certificate under the hardened runtime, sign the package
   with the Developer ID Installer certificate, submit to
   notarization with notarytool, staple the ticket, and
   attach the package to the GitHub release beside the
   artifacts already there.
3. The store submission he directed is a separate one time
   attempt through App Store Connect, made once the package
   exists; its outcome is Apple's to give, and the notarized
   shelf route above does not depend on it.

### Microsoft leg

1. Vetting: one time, Microsoft's side, already in motion.
   Nothing automates another party's review of the
   publisher.
2. The installer gap closes in the build: the one directory
   freeze and the draft Inno Setup script already stand in
   the tree; the pipeline step builds the single installer
   executable per release and signs it once his certificate
   exists, so the versioned address on the GitHub release is
   the address the listing names.
3. Per release, the submission step hands Partner Center
   the new versioned installer address through its
   submission route and carries the listing forward
   unchanged. Certification of each submission is
   Microsoft's, measured in days, and the leg reports the
   store's own state rather than a hope.

## What cannot be automated, said plainly

- The first classic confinement approval at the Snap Store:
  a human review of the publisher and the case, by design.
- The first App Store review, if the submission is made: a
  human review, and the sandbox verdict may end the route.
- Microsoft's identity vetting of the publisher: in motion,
  theirs to finish.
- Any purchase: a signing certificate is bought in the
  conductor's name, by his hand, or not at all.

Everything else on this page is a machine step, and the
measure of the design is that a release cut at midnight
reaches every cleared store by morning with no hands.

## What landed with this page

- This page.
- runner/tools/store_release.py: the Snap release planner,
  pure and socket free, whose rules the tests pin.
- runner/tests/test_store_release.py: the pins: both
  architectures together, a refusal while the review holds,
  a refusal on a half built version, and no command when the
  version already stands released.
