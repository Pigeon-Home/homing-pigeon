# CI runtime

Written 2026-10-22, from the runs of that morning. The growth
was intentional: more hosts, a real sandbox proof, a portable
proof, mutation, a minimal userland. This note is what of that
is earning its minutes, what was queued and never starting, and
the shape that lets the corpus grow without every push paying
for every runner.

The numbers below are wall-clock of the job, not of the queue
in front of it. Queue time was the larger number, and it is
the one the shape change is aimed at.

## What a push was doing

Every push to main started four workflows.

| Workflow | What it proved | Measured |
|---|---|---|
| build.yml `test` | The whole suite, on Ubuntu, with bubblewrap | 4.3 min (run 39827660180) |
| build.yml binaries | PyInstaller for Windows, Windows arm64, Linux, Linux arm64, macOS, macOS Intel, Pi Light, plus the wheel | 0.2 to 5.6 min, after the suite |
| platform-matrix | A small portable proof, core tier, 11 legs | Did not finish. Queued. |
| minimal-userland | Repair when bash is absent, x86_64 and arm64 | About 20 seconds |

Docker publish and the release mutation job run on a tag, not
on a push. The seeded mutation run is weekly. CodeQL is weekly.
None of those belong on the push path, and they are not moved.

`build-windows` was the long pole of the build, 5.6 minutes,
and about five of those are the suite again. It waited for the
Ubuntu suite to finish first, so the line was four minutes plus
six. The release then waited for the binaries.

## The duplicate that is worth keeping

The Windows job runs the whole suite, and Ubuntu already ran
it. That is a real duplicate, and it should stay.

The failure it exists for is not theoretical. On 2026-10-22
`os.kill(pid, 0)` raised WinError 87 inside two tests that
pass on Linux. Ubuntu cannot see that. A Windows-only module
list would have to be maintained by hand, and the first miss
is the next WinError. Five minutes of a Windows runner, on
the release, is the cheap version of that miss.

What was not worth it was running that suite, then waiting to
start the compile. The compile does not need the Ubuntu
result. The release does. The binary jobs now start with the
suite, and the release waits for the suite and for every
artifact, including the wheel. A red suite still cannot
publish. A tag's wall clock is the slower of the two, not
the sum.

The portable proof (`runner/tests/test_platform_proof.py`) is the
other duplicate, and it is the right size: one signed job,
one bad signature, one repaired interpreter. It is not the
suite. Copying the suite onto 41 legs would be the explosion.
Adding a leg should mean adding that proof, not a new full run.

minimal-userland is a third small proof, on a box with no
bash. It is twenty seconds and it stays on every push. The
Pi Light archive points at it.

## The duplicate that was the queue

The core tier had eleven legs, and four of them asked for a
hosted runner the binary build was already holding:

| Leg | Runner | Why it hurt |
|---|---|---|
| native-macos-x86_64 | `macos-13` | Retired December 2025. The job never starts. The workflow never finishes. |
| native-windows-arm64 | `windows-11-arm` | Same pool as `build-windows-arm64`, once per push |
| native-ubuntu-arm64 | `ubuntu-24.04-arm` | Same pool as the arm64 Linux builds |
| debian-13-arm64 | `ubuntu-24.04-arm` | Same pool again |

By the afternoon of 2026-10-22 the platform-matrix workflow
had a line of queued runs going back to 07:19 UTC. Each new
push added another, and none of them could pass the retired
runner. That is not coverage. The leg was not running.

Those legs stay in the corpus. The label is `macos-15-intel`
now, which is the hosted Intel runner that replaced
`macos-13`. They run on the nightly schedule (09:17 UTC) and
on a manual dispatch. A push runs the core legs whose runner
is plentiful: `ubuntu-latest`, including the one qemu leg
(32-bit ARM) that is already in the core tier.

A leg is scarce when its runner starts with `macos-` or
`windows-`, or ends with `-arm`. `"pool": "scarce"` or
`"pool": "plentiful"` on the leg overrides that, so a future
leg does not need a new rule and a new label.

The nightly is the frequent full pass. It is one copy, not
one copy per commit. A new push cancels the previous push's
matrix and the previous push's build. It does not cancel the
nightly, and nothing cancels a tag.

## What this does not do

- It does not drop the Windows suite, on a push or on a tag.
- It does not merge minimal-userland into the matrix. The
  matrix proof assumes a normal userland. The point of that
  workflow is that bash is gone.
- It does not run mutation on a push. Seventeen minutes, and
  it is a signal. The tag already runs it, and Monday's
  seeded run walks a different seed.
- It does not try to shard the Ubuntu suite across jobs.
  Four minutes is not the queue. Splitting it would make
  the annotation and the skip guard apply to a fragment.

## Maker boards and robots

Added as full legs on `ubuntu-latest`, under QEMU, so a push
does not grow and the nightly's wall clock grows only if one
of them is slower than the qemu legs already there. They run
beside the existing nightly, not after it.

| Leg | What it stands in for |
|---|---|
| `debian-12-armv7-qemu` (already core) | 32-bit Raspberry Pi OS, BeagleBone, the old C.H.I.P. Debian |
| `debian-12-arm64-qemu` | 64-bit Raspberry Pi OS, Armbian Debian |
| `ubuntu-22.04-arm64-qemu` | The Ubuntu under a Jetson, and Ubuntu images for Orange Pi and ROCK Pi |
| `alpine-3-armv7-qemu` | The same 32-bit boards on musl instead of glibc |
| `ros-humble-arm64-qemu` | ROS 2 Humble, the fleet image (`ros:humble-ros-base`, Ubuntu 22.04 arm64) |
| `ros-jazzy-arm64-qemu` | ROS 2 Jazzy (`ros:jazzy-ros-base`, Ubuntu 24.04 arm64) |

Not a leg, on purpose. A second container of an image the
nightly already runs (Ubuntu 24.04 arm64 has a native arm
runner). A NVIDIA JetPack image, which is several gigabytes
and wants the NVIDIA runtime. The eight fat-fingers crossed
with each board. The proof is the same either way, and the
minutes are not.

## Adding a leg later

Put it in `.github/platform-legs.json`.

- A new distribution on `ubuntu-latest` with `"tier": "core"`
  runs on every push. Keep that set small. One qemu
  architecture is enough on the push path. The rest are
  `"tier": "full"` and run nightly.
- A new Mac, Windows, or ARM hosted runner is scarce by its
  name. It runs nightly. Do not put it on the push path to
  make the README look busier. The binary job for that OS
  already runs on the push.
- The proof it runs is `.github/tools/platform_proof.sh` or
  `runner/tests/test_platform_proof.py`. A skipped proof is a
  failure (`--no-skips --require-ok`). Do not add the whole
  suite to the leg.
- The leg's name has to appear in the README's Proven
  platforms table. `runner/tests/test_build_config.py` pins that,
  the tier size, and the push filter.
