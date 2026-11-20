# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
# App stores: design and preparation notes

Preparation notes for putting Homing Pigeon into the Microsoft
Store and the Ubuntu Snap Store, opened on 2026-11-20 at the
conductor's direction. The conductor's FUTURE.md names the stores as
future work. These notes cover the Microsoft Store in full and
give the short form of the Snap Store path, whose page of record
stands elsewhere in the tree. The Apple Store bullet in that
file is separate work and is not covered here.

Scope: this is preparation only. Account creation, identity
verification, name reservation, any purchase, and final submission
are the owner's hand on both stores, and each such step is marked
owner only where it appears below.

## What ships today

The build workflow (.github/workflows/build.yml) freezes the
runner with PyInstaller into one file executables, one pair per
platform: the runner itself and the install program. The Windows
legs (x86_64 and arm64) pack the pair with the example config
into a versioned zip; the Linux legs (x86_64 and arm64) pack the
same shape into a versioned tarball. Releases are cut from the
version in pyproject.toml and published on GitHub Releases, so
every release already has a stable, versioned download address
that never changes afterwards.

Two facts about the installed product decide the store fit:

- On Windows the install program registers a Scheduled Task named
  HomingPigeon that runs at startup as SYSTEM
  (runner/ops/install.py). The runner is a machine level service,
  not a per user app.
- On Linux the runner confines every job it runs with bubblewrap
  (runner/guard/sandbox.py), and jobs are the operator's own
  commands, run with whatever interpreters and binaries the host
  provides, in directories the operator chooses.

## The Snap Store

The Snap path has its own page of record,
docs/steady/project/snap-store-readiness.md, landed the same
day: what the store asks of any publisher, the confinement
reasoning from the code, the classic grant process and its
costs, the packaging path, the timelines, and the step split.
This page does not repeat it. The short form:

- The store asks for a free Ubuntu One account, a registered
  snap name, the snapcraft tool, and channelled uploads that pass
  automated checks, with human review for a classic snap until
  the store grants it a declaration. The name homing-pigeon fits
  the name rules (lowercase letters, numbers and hyphens, at
  least one letter, no hyphen at either end). Registration is
  free and permanent, and waits for the conductor's account.
  Owner only.
- Strict confinement cannot hold the runner. Jobs are arbitrary
  operator supplied commands run with host interpreters and host
  binaries; the runner confines each job with bubblewrap, which
  needs the namespace and mount operations a strict snap's own
  AppArmor and seccomp profiles deny; jobs work in operator
  chosen paths across the host; and the runner watches its job
  process trees on the host and kills the ones that break the
  bar. The store's classic review page names supported
  categories and criteria that describe this shape (an agent
  running arbitrary user directed code; running an arbitrary
  command; files on the host outside the snap's runtime), and
  the readiness page works the case in full.
- The grant is a process, not a setting: a forum request in the
  store-requests category with the technical reasons, review by
  the security team or an architect, vetting of the publisher,
  and a snap declaration on approval. It is per snap and can be
  revoked, and users install with
  snap install homing-pigeon --classic. Owner only: the request
  and the vetting belong to the publisher's account and identity.
- The draft package, packaging/snap/snapcraft.yaml, follows the
  readiness page's recommended shape: the python plugin on the
  core24 base, Python bundled into the snap, bubblewrap staged
  beside the runner, the five console scripts exposed as apps,
  the runner as a daemon (daemon: simple) that snapd manages
  instead of a systemd unit, and the version adopted from the
  Python package metadata. It sits in a packaging folder; the
  readiness page records the layout question (that folder, or
  the standard snap folder at the root) as the conductor's
  decision. Nothing is registered, built or uploaded yet.
- The first build spike ran on 2026-11-20 and its record stands
  in the readiness page. A staged build of the draft's exact
  layout passed 18 checks from the staged tree, including a
  bubblewrap trial job run by the runner's own command builder.
  A real snapcraft build could not run on that machine, because
  it cannot mount squashfs images and snapd therefore could not
  install snapcraft or the core24 base; the pack itself awaits a
  machine with that privilege. The spike found and fixed one
  defect in the draft: adopt-info had no part metadata to adopt,
  and the runner part now sets the version from the installed
  package metadata through craftctl in its override-build.

## The Microsoft Store

### What the store asks

- A Partner Center developer account. The current onboarding,
  entered from storedeveloper.microsoft.com, charges no
  registration fee for an individual or a company account.
  Identity verification uses a government issued ID and a selfie.
  An individual account cannot later be converted into a company
  account, so the choice is worth a pause. Owner only.
- A reserved product name. Reserving the name in Partner Center
  creates the package identity: the identity name, the publisher
  and the publisher display name. For a packaged submission those
  values must match the package manifest exactly, character for
  character. They are issued by the conductor's account, so the
  manifest cannot be finished before them. Owner only.
- A submission: packages, pricing and availability, properties
  (including a privacy policy address; the project already
  publishes one, docs/steady/project/privacy-policy.md, served at
  https://home.pigeon-home.ai/privacy), an age ratings
  questionnaire, and the store listing. The age ratings and the
  final submission are the conductor's hand.
- Review: Partner Center validates the package on upload, the
  Windows App Certification Kit can be run locally beforehand,
  and certification review follows. Review is measured in days.

### Route A: the unpackaged installer listing

Store policy 10.2.9 lets a non gaming product submit an HTTPS
download address for its installer instead of a package. The
requirements: the installer is a single .exe or .msi; it installs
silently (a UAC prompt is allowed); it is a standalone offline
installer, not a downloader; the address is versioned and the
binary at that address must not change after submission; and the
installer binary and every PE file in it must be digitally
signed with a certificate that chains to a certificate authority
in the Microsoft Trusted Root Program.

Fit: this route takes the product exactly as it ships today,
SYSTEM scheduled task and all, because the installer runs
outside the package container. GitHub Releases already provides
the versioned, unchanging addresses. Two gaps stand between here
and a submission:

1. The Windows release today is a zip of loose files, not an
   installer. A single self contained installer executable that
   lays down the same files and runs the same setup is new
   packaging work, of the ordinary kind.
2. Nothing in the Windows build is code signed today. A signing
   certificate from a trusted CA, or an Azure Artifact Signing
   subscription, is a purchase in the conductor's name. Owner only.

### Route B: MSIX

A packaged submission wraps the frozen executables in an MSIX
with an AppxManifest. Microsoft signs the package after
certification, so this route needs no certificate purchase. The
draft manifest prepared with these notes is
packaging/msix/Package.appxmanifest, with placeholder identity
values where Partner Center's will go.

Three costs keep this from being the first route:

1. The package model is per user and containerised. A packaged
   app cannot register a Task Scheduler task that runs as SYSTEM,
   so the install program's current shape does not carry over;
   the runner would run as the installing user, started by a
   startup task, and the setup flow would be reworked around the
   package's own data folders.
2. The package declares the restricted capability runFullTrust so
   its Win32 executables can run with the user's full rights.
   Restricted capabilities need a written justification at
   submission, and approval is part of certification.
3. Policy 10.2.2 forbids dynamic code that changes or extends the
   product beyond its described functionality. Executing jobs is
   this product's described functionality, so the listing and the
   capability justification must describe job execution plainly
   and early. That framing is honest and available; certification
   may still argue, and that risk is recorded here rather than
   wished away.

Verdict: prepare route A first, because it changes the product
least. Keep the MSIX draft warm for the day a per user install
is acceptable, or if the signing purchase is refused.

## What landed with these notes

- This page.
- packaging/snap/snapcraft.yaml: the draft Snap package
  definition, marked as a draft in its own header.
- packaging/msix/Package.appxmanifest: the draft MSIX manifest,
  with placeholder identity values.
- runner/tests/test_store_packaging.py: pins on the drafts, so a
  later edit cannot quietly flip the snap to strict confinement,
  drop the daemon entry, or replace the manifest placeholders
  with values that did not come from Partner Center.

## Owner only, both stores, in one list

- Snap Store account and developer namespace.
- Snap name registration for homing-pigeon.
- The classic confinement request and publisher vetting.
- Partner Center account and identity verification.
- The product name reservation, and the package identity values
  it issues.
- A code signing certificate or Azure Artifact Signing
  subscription, if route A is taken.
- Age ratings answers, listing approval, and the final submission
  on each store.

## Sources

Read on 2026-11-20:

- Microsoft Learn, "Steps to open a Microsoft Store developer
  account in Partner Center" and "Free developer registration
  for individual developers": the fee free onboarding, the
  identity check, and the account types.
- Microsoft Learn, "App package requirements for MSI/EXE app":
  the unpackaged route's signing, silence, offline and versioned
  address requirements.
- Microsoft Store Policies, sections 10.2.2, 10.2.4 and 10.2.9:
  dynamic code, service dependencies, and the installer address
  route.
- Snap documentation, "Reviewing classic confinement snaps": the
  process, the supported categories, the criteria, and the
  caveats.
- Snapcraft documentation and tutorials: snapcraft.yaml shape,
  name rules, registration, channels and publishing.
- In the tree: docs/steady/project/snap-store-readiness.md, the
  Snap path's page of record, whose recommended package shape
  the draft in packaging/snap/ follows.
