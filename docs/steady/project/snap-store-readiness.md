# Snap Store readiness: the Ubuntu store path for the runner

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

This page records the preparation for offering the runner through the
Ubuntu Snap Store, one of the three store fronts the owner names in
[FUTURE.md](../../FUTURE.md). It sits beside [hosting.md](hosting.md),
which covers machines the tenant pays for; this page covers a store
listing for machines the user already owns. Status: preparation only.
No store account exists yet, nothing has been submitted, and no money
has been spent. The decisions this page asks of the owner are collected
at the end.

## The short answer

1. The runner needs classic confinement. Strict confinement cannot run
   it, for structural reasons set out below; this is the finding the
   whole submission turns on.
2. Canonical's own review guidance names a supported category that
   matches this runner closely: an AI agent or assistant that runs
   arbitrary code at the user's direction and needs to reach files and
   programs that are not known at build time. The request can be
   written from the runner's real requirements.
3. Everything else is ordinary packaging work. One snapcraft.yaml, the
   python plugin on the core24 base, Python bundled into the snap
   because a classic snap may not use the base snap's interpreter,
   bubblewrap staged beside the runner, and the runner run as a daemon
   that snapd manages instead of a systemd unit the installer writes
   itself.

## What the store asks of any publisher

- An Ubuntu One account, created at the snapcraft.io account page.
  The command line tool signs in with `snapcraft login`.
- A registered snap name. Names are unique across the whole store and
  are held by whoever registers first. A name may use lowercase
  letters, digits and hyphens, must contain at least one letter, and
  may not begin or end with a hyphen. Registration is
  `snapcraft register homing-pigeon` once signed in, and the name in
  snapcraft.yaml must match the registered name exactly.
- The snapcraft tool itself, installed as a classic snap with
  `sudo snap install snapcraft --classic`. Builds run in a clean
  container or virtual machine that snapcraft manages (LXD on Linux,
  Multipass as the other provider), so the build machine needs one of
  those working.
- Uploads go through channels of rising confidence: edge, beta,
  candidate, stable, on the default track named latest. Automated
  checks run on every upload. A snap that asks for classic confinement
  is flagged for human review until the store grants classic to that
  snap; after the grant, later uploads pass without the human step.
- No fee for the account or for publishing appears anywhere in the
  store documentation cited at the end of this page.

## The confinement question

### What the runner must be able to do

The list comes from the code, not from preference.

- Run the command a signed job names. The command and the programs it
  uses are chosen by the job and cannot be known when the package is
  built; running other people's programs is the product.
- Confine each job with bubblewrap. The Linux backend in
  [runner/guard/sandbox.py](../../../runner/guard/sandbox.py) builds a
  bwrap invocation with user, IPC, network and UTS namespaces, /usr
  mounted read only, a fresh /proc and /dev, a tmpfs at /tmp, and the
  job folder as the only writable mount.
- Read and write the host's real filesystem wherever a job points,
  including paths outside the user's home folder.
- Start at boot and keep running. Today the installer in
  [runner/ops/install.py](../../../runner/ops/install.py) writes a
  systemd unit and drives systemctl to enable it.
- Reach the network, for mail and for the hosted transports described
  in [cs_canoe.md](../design/cs_canoe.md).

### Why strict confinement cannot carry that

A strict snap runs inside a mount namespace that snapd builds from
the base snap, under an AppArmor profile and seccomp filtering that
snapd generates. Its root filesystem is the base snap's, not the
host's, so the host's programs are not present to run. Access to the
outside world comes only through interfaces, which grant named slices:
this folder, that socket, the network. No interface grants the two
things this runner is made of:

- creating mounts and namespaces of its own, which bubblewrap needs
  before it can confine anything, and
- running arbitrary programs from the host, which the job model needs
  on every single job.

The failure is not theoretical. The Loupe image viewer's snap could
not move past version 46 because glycin, the library that loads its
images, sandboxes its loaders with bubblewrap, and inside the strict
snap bubblewrap met AppArmor denials under the snap's own profile. A
maintainer's summary in that bug report: a strict confined snap does
not have read access to most of the things the tool is trying to hide,
and does not have the ability to create all those mounts. A tool whose
whole job is creating mounts fares no better.

Super privileged interfaces exist for a few named daemons (the docker
snap's docker-support is the well known one) and each needs its own
store approval before a snap carrying it may be distributed. None of
them covers a general job runner, and asking Canonical for a new one
is a snapd feature request, not a submission step. That path is set
aside.

Canonical's security model guidance names three needs that in
practice only classic confinement resolves: access to arbitrary
filesystem paths outside the home folder and /media; running other
programs that cannot be determined at build time; and privileged
tasks not yet covered by interfaces. The runner presents all three at
once. Devmode, the third confinement level, is a debugging aid only:
a devmode snap cannot be released to the stable channel and does not
appear in search results, so it plays no part in a store listing.

### Why classic confinement fits, and what it costs

Classic confinement runs the snap against the host's own filesystem
and permissions, much as a traditional package runs. The user
installs it with `snap install homing-pigeon --classic`; the flag is
the user's own acknowledgment that the snap runs unconfined.

The grant is a process, not a setting:

1. The publisher files a request in the forum's store-requests
   category, giving the technical reasons.
2. The security team or an architect reviews the technical case while
   the advocacy and reviewers teams vet the publisher.
3. On approval a store reviewer issues a snap declaration for the
   snap, and uploads stop triggering human review.

The published list of supported categories includes the AI agent
category quoted in the short answer above, and the published criteria
add two more shapes that fit: running an arbitrary command,
especially one the user can configure, and access to files on the
host outside the snap's runtime, with /usr named as the example. The
same page warns that difficulty making strict confinement work is not
by itself a reason, so the request must stand on the requirements
themselves. Here it can: the requirements are the product.

Costs and caveats, stated plainly:

- Classic snaps cannot be installed on Ubuntu Core devices. The
  runner's audience is ordinary Ubuntu desktops and servers, so this
  costs little.
- A classic snap runs in the host mount namespace rather than the
  base snap's filesystem. Snapcraft patches paths in built binaries
  to look under $SNAP, so a classic snap needs testing on more than
  one distribution before it can be called reliable.
- The grant belongs to the snap and the store may revoke it. The
  request text should be written as if it will be read again later.
- Ubuntu 24.04 hosts restrict unprivileged user namespaces through
  AppArmor by default. That host setting already shapes bubblewrap
  for every install form today, and the runner already detects it
  (the same sandbox.py linked above reads the sysctl). Classic
  confinement adds no second profile over the runner, so the snap
  behaves like the current install on this point. Strict confinement
  is the form that adds the blocking profile.

## The packaging path

### The build file

Snapcraft looks for snap/snapcraft.yaml in the tree. The standard
layout puts a snap folder at the root, the same shape as the existing
runner and docs folders; the alternative is a packaging folder kept
elsewhere with its source pointed at the tree. That choice is the
owner's (see the decisions at the end). The shape of the file:

```yaml
name: homing-pigeon
base: core24
adopt-info: runner
summary: A self hosted, email driven agent runner
description: |
  Homing Pigeon runs signed jobs on your own machine. Tell your
  cloud SI to send the job by email; the runner verifies it,
  runs it confined, and mails the result back.
confinement: classic
grade: stable
platforms:
  amd64:
  arm64:

apps:
  homing-pigeon:
    command: bin/homing-pigeon
    daemon: simple
  homing-pigeon-install:
    command: bin/homing-pigeon-install
  homing-pigeon-send-job:
    command: bin/homing-pigeon-send-job
  homing-pigeon-auth:
    command: bin/homing-pigeon-auth
  homing-pigeon-host:
    command: bin/homing-pigeon-host

parts:
  runner:
    plugin: python
    source: .
    python-packages:
      - certifi
    stage-packages:
      - python3-venv
      - bubblewrap
```

Notes on the choices inside it:

- core24 is the current long term support base (Ubuntu 24.04) and
  carries Python 3.12. The project declares Python 3.9 or newer in
  [pyproject.toml](../../../pyproject.toml), so the base interpreter
  is comfortably inside the supported range.
- A classic snap cannot use the base snap's interpreter, so Python
  must be bundled. The python plugin documentation gives the recipe:
  staging python3-venv forces the interpreter into the snap.
- The package declares no runtime dependencies, so there is no
  requirements file to chase. The one exception is certifi, named in
  python-packages above: the runner's TLS helper in runner/wire uses
  certifi's bundle when it can import it, which is the same reason
  the frozen build collects certifi today. Inside the snap the bundle
  must travel with the runner or verified TLS has nothing to stand
  on.
- Staging the bubblewrap package puts bwrap inside the snap. The
  runner finds bwrap by name on its PATH, and a snap app's PATH
  covers the snap's own staged bin folders, so the snap does not
  depend on the host having bubblewrap installed.
- adopt-info takes the snap's version from the Python part's package
  metadata, so the snap never carries a second copy of the version
  number to drift.
- The five apps are the five console scripts pyproject.toml already
  declares. The runner itself is declared with `daemon: simple`,
  which makes snapd run it as a service that starts at boot and is
  managed with the snap start, stop and restart commands.
- amd64 and arm64 are both declared. An arm64 build on an amd64
  machine can be produced with `snapcraft remote-build`, which runs
  the build on Launchpad's farm; that needs a Launchpad account and
  uploads the source to it, which costs this project nothing because
  the tree is already public.

### What changes around the runner

- The job path does not change. Signing, transports, confinement and
  the oracle all stay as they are; the snap wraps the same entry
  points the wheel and the frozen build already ship.
- The service step moves. Inside a snap, snapd owns the daemon, so
  the installer's systemd work must not run; teaching the installer
  to notice a snap install and skip that step is a small, separate
  code change that belongs to the build spike, not to this page.
- One design point the spike must settle: where configuration lives.
  A system daemon's data sits under /var/snap/homing-pigeon (the
  SNAP_DATA and SNAP_COMMON folders), while the setup wizard is an
  interactive flow a user runs in a terminal, today writing the
  user's own config. Which of the two owns the config under a snap,
  and how the wizard hands over to the daemon, is the one real design
  question in the packaging.
- The alternative worth one spike day: stage the frozen binary the
  project already builds per platform, using the dump plugin,
  instead of building the Python part. That reuses the exact artifact
  the rig batteries already test, at the price of a second packaging
  logic to keep in step. The Python path above is the recommended
  first attempt; the frozen path is the fallback if it fights back.

## The steps, split by who takes them

### Muse can do alone

1. Write snap/snapcraft.yaml and produce a first local build with
   snapcraft and LXD on a Linux build machine.
2. Install the built snap locally with the dangerous and classic
   flags (the form for a local file that has not been through the
   store) and run the runner's own checks against the snapped
   commands, including a trial job under bubblewrap confinement.
3. Draft the classic confinement request from the store's template,
   written from the requirements listed on this page.
4. Prepare the store listing text from the README and an icon from
   the assets folder.
5. Keep this page current as each step lands.

### The owner must do

1. Create the Ubuntu One account at the snapcraft.io account page.
   This is the first manual step and the only one that cannot be
   delegated at all: the account is the publisher's identity, and
   everything else hangs off it.
2. Register the name homing-pigeon from that account. Names go to
   whoever registers first, so this one step is worth taking early,
   before the build is finished. Whether the name is still free is
   known only at the moment of trying; a web search on 2026-11-20
   found no snap carrying it, which is encouraging and proves
   nothing.
3. Post the classic confinement request under his own account and
   answer the reviewers' questions. The vetting is of the publisher,
   so some answers can only be his.
4. Approve the final listing text and press the button on the first
   stable release.

### Expected timelines, with their evidence marked

- Account and name: minutes, in one sitting. This follows the
  documented flow.
- A first locally built and locally tested snap: days of work, not
  weeks. Estimate. The packaging is one file and the runner brings no
  runtime dependencies with it; the unknown is the config question
  above, not the tooling.
- The classic confinement review: Canonical publishes no timeline for
  it. The process has several human stages, so plan for weeks rather
  than days, and start it as soon as the name is registered, in
  parallel with the build rather than after it. Estimate, unverified;
  the stages themselves are documented at the source below.
- After the grant: uploads return to automated checks and later
  releases move at the project's own pace. Documented.

## Decisions for the owner

1. The snap folder question above: standard layout at the root, or a
   packaging folder elsewhere.
2. Both architectures from the first listing, or amd64 first with
   arm64 following once remote build is set up.
3. The listing's support links: the GitHub page, and the privacy page
   at [privacy-policy.md](privacy-policy.md), are the natural pair.

## Sources

Store and snapcraft documentation, read on 2026-11-20:

- Snap confinement: https://snapcraft.io/docs/explanation/security/snap-confinement/
- Reviewing classic confinement snaps (the process, the supported
  categories and the criteria quoted above):
  https://snapcraft.io/docs/reference/administration/reviewing-classic-confinement-snaps/
- Choosing a security model (the three needs that point at classic):
  https://forum.snapcraft.io/t/choosing-a-security-model/6847
- The python plugin (bundling Python for classic snaps):
  https://snapcraft.io/docs/python-plugin
- Services and daemons (the daemon key and service management):
  https://ubuntu.com/docs/snapcraft/latest/explanation/services-daemons/
- Remote build (multi architecture builds on Launchpad):
  https://forum.snapcraft.io/t/remote-build/14400
- The docker interface page (super privileged interfaces and the
  store approval they need): https://snapcraft.io/docs/docker-interface
- The Loupe bubblewrap bug report (strict confinement versus
  bubblewrap, in the wild):
  https://www.mail-archive.com/touch-packages@lists.launchpad.net/msg378867.html
- The account, name registration and upload flow, as walked through
  in two independent guides:
  https://docs.flutter.dev/deployment/linux and
  https://discourse.ubuntu.com/t/part-3-distribute-ros-applications-with-the-snap-store/40762

Anything on this page marked as an estimate is Muse's judgment from
those sources, not a Canonical commitment. The name's availability is
unverified until the registration attempt itself answers it.
