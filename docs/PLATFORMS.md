# Proven platforms

Every leg below runs the same portable proof
(`runner/tests/test_platform_proof.py`) on every push or nightly: a signed job
runs under the platform default and under that box's Python, a job
with a bad signature produces no result at all, a job naming an absent
interpreter is repaired to the platform default and the result says so,
non-ASCII output survives the box's locale, and the result carries the
members every consumer relies on. A leg fails unless every test ran and
passed; a skipped proof is not a proof. Nothing is stubbed but the mail.
[![platform-matrix](https://github.com/Pigeon-Home/homing-pigeon/actions/workflows/platform-matrix.yml/badge.svg)](https://github.com/Pigeon-Home/homing-pigeon/actions/workflows/platform-matrix.yml)

| Kind | Legs |
|------|------|
| Native runners | `native-ubuntu-x86_64`, `native-ubuntu-arm64`, `native-windows-arm64`, `native-macos-x86_64`, `native-windows-x86_64`, `native-macos-arm64` |
| Distributions, x86_64 (containers) | `alpine-3-x86_64`, `rocky-9-x86_64`, `python-3.9-floor-x86_64`, `debian-12-x86_64`, `ubuntu-22.04-x86_64`, `ubuntu-24.04-x86_64`, `fedora-latest-x86_64`, `almalinux-8-x86_64`, `ubi9-minimal-x86_64`, `ubi9-minimal-fips-x86_64`, `opensuse-leap-15-x86_64`, `archlinux-x86_64`, `amazonlinux-2023-x86_64`, `python-3.14-x86_64` |
| Distributions, arm64 (containers, native ARM runner) | `debian-13-arm64`, `alpine-3-arm64`, `ubuntu-24.04-arm64`, `fedora-latest-arm64`, `rocky-9-arm64` |
| Other architectures (QEMU) | `debian-12-armv7-qemu`, `debian-12-i386-qemu`, `debian-12-ppc64le-qemu`, `debian-12-s390x-qemu`, `debian-13-riscv64-qemu` |
| Maker and robotics boards (QEMU, nightly) | `debian-12-arm64-qemu`, `ubuntu-22.04-arm64-qemu`, `ubuntu-22.04-armv7-qemu`, `ubuntu-24.04-armv7-qemu`, `alpine-3-armv7-qemu`, `ros-humble-arm64-qemu`, `ros-jazzy-arm64-qemu` |
| BSD virtual machines (nightly) | `vm-freebsd-14`, `vm-openbsd-7`, `vm-netbsd-10` |
| Administrator fat-fingers on a known-good base | `fatfinger-no-bash`, `fatfinger-noexec-tmp`, `fatfinger-no-home`, `fatfinger-path-minimal`, `fatfinger-c-locale`, `fatfinger-umask-077`, `fatfinger-closed-stdin`, `fatfinger-readonly-root` |

A push runs the core legs whose runner is ubuntu-latest. macOS,
Windows, and ARM hosted runners, and every full leg, run nightly
and on dispatch. Each of these is the userspace those boards
ship, not a boot of the board, and two boards on the same
userspace share a leg instead of paying for the proof twice.
Debian 12 armv7, already in the core tier: 32-bit Raspberry
Pi OS, BeagleBone, the old CHIP, the Tinker Board, and
Armbian's Debian image on the H3 boards (Orange Pi PC,
NanoPi Neo). Ubuntu 22.04 and 24.04 armv7: PandaBoard,
Odroid XU4, Cubieboard, Banana Pi M1. Debian 12 arm64:
64-bit Raspberry Pi OS, and Armbian Debian on the 64-bit
competitors (Orange Pi 5, ROCK 5, Banana Pi M5, NanoPi,
Khadas, Pine64, Libre Computer). Ubuntu 22.04 arm64: the
Ubuntu under a Jetson, Odroid N2, C4 and M1, and Armbian's
Ubuntu image. Alpine armv7: those 32-bit boards reflashed
to musl. The x86 boards (Atomic Pi, LattePanda, Up Board,
Odroid H3) are the Debian and Ubuntu x86_64 legs. The
RISC-V boards (VisionFive, Milk-V, Star64) are the riscv64
leg. Humble and Jazzy are the ROS images a robot on any of
those puts under its own packages. A JetPack image is not
pulled. It is several gigabytes and it needs NVIDIA's
runtime. Fat-fingers are not crossed with every board.
`runner/tests/test_build_config.py` pins this table to the matrix, so a leg
cannot be claimed here without running there. Not on the list: a box
with no Python at all (BusyBox-only, bare firmware) -- the runner is
stdlib Python, so that is the floor, not a gap. Also not a leg, and
refused by the installer rather than simulated: a television
(Tizen, webOS, Roku, Apple TV), and a USB accelerator with no
Linux host under it. Those have no shell for a job to run in.
Android-class sets (Android TV, Google TV, Fire TV, Shield) with a
sideloaded shell are permitted with a stated warning -- no
service, no model, no sandbox -- because the shell is what
decides. A Linux board behind the screen is an ordinary leg;
`--profile display-board` is that install with no model. To add a host or a
fat-finger, add one matrix line and one table entry.
