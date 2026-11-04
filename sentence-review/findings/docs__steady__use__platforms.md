# Findings — docs/steady/use/platforms.md

Source: docs/steady/use/platforms.md, reviewed at main cbb52068.
Sentence units: 36. Flagged: 2. Categories: pre-release 36, post-release 0.

A catalogue document: the proof rule first, then the legs table, then a run of paragraphs naming which boards each leg stands for, then what is not a leg and how a leg is added. The catalogue is the connection — each board paragraph answers for 1 row of the table — so the run flows. 2 units are flagged: the badge line (unit 4), on the same ground as the badge lines in the README findings, and the legs table's header row (unit 5), structure rather than a sentence. The table's data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Every leg below runs the same portable proof…" | pre-release | flows |  |
| 2 | "A leg fails unless every test ran and…" | pre-release | flows |  |
| 3 | "Nothing is stubbed but the mail." | pre-release | flows |  |
| 4 | "[![platform-matrix](https://github.com/Pigeon-Home/homing-pigeon/actions/workflows/platform-matrix.yml/badge.svg)](https://github.com/Pigeon-Home/homing-pigeon/actions/workflows/platform-matrix.yml)" | pre-release | flagged | Badge image line, not a sentence; it stands between the prose claim and the legs table |
| 5 | "Kind \| Legs" | pre-release | flagged | Table header row, structure rather than a sentence |
| 6 | "Native runners \| `native-ubuntu-x86_64`, `native-ubuntu-arm64`, `native-windows-arm64`, `native-macos-x86_64`, `native-windows-x86_64`,…" | pre-release | flows |  |
| 7 | "Distributions, x86_64 (containers) \| `alpine-3-x86_64`, `rocky-9-x86_64`, `python-3.9-floor-x86_64`, `debian-12-x86_64`,…" | pre-release | flows |  |
| 8 | "Distributions, arm64 (containers, native ARM runner) \| `debian-13-arm64`,…" | pre-release | flows |  |
| 9 | "Other architectures (QEMU) \| `debian-12-armv7-qemu`, `debian-12-i386-qemu`, `debian-12-ppc64le-qemu`, `debian-12-s390x-qemu`,…" | pre-release | flows |  |
| 10 | "Maker and robotics boards (QEMU, nightly) \| `debian-12-arm64-qemu`,…" | pre-release | flows |  |
| 11 | "BSD virtual machines (nightly) \| `vm-freebsd-14`, `vm-openbsd-7`, `vm-netbsd-10`" | pre-release | flows |  |
| 12 | "Administrator fat-fingers on a known-good base \| `fatfinger-no-bash`,…" | pre-release | flows |  |
| 13 | "A push runs the core legs whose runner…" | pre-release | flows |  |
| 14 | "macOS, Windows, and ARM hosted runners, and every…" | pre-release | flows |  |
| 15 | "Each of these is the userspace those boards…" | pre-release | flows |  |
| 16 | "Debian 12 armv7, already in the core tier:…" | pre-release | flows |  |
| 17 | "Ubuntu 22.04 and 24.04 armv7: PandaBoard, Odroid XU4,…" | pre-release | flows |  |
| 18 | "Debian 12 arm64: 64-bit Raspberry Pi OS, and…" | pre-release | flows |  |
| 19 | "Ubuntu 22.04 arm64: the Ubuntu under a Jetson,…" | pre-release | flows |  |
| 20 | "Alpine armv7: those 32-bit boards reflashed to musl." | pre-release | flows |  |
| 21 | "The x86 boards (Atomic Pi, LattePanda, Up Board,…" | pre-release | flows |  |
| 22 | "The RISC-V boards (VisionFive, Milk-V, Star64) are the…" | pre-release | flows |  |
| 23 | "Humble and Jazzy are the ROS images a…" | pre-release | flows |  |
| 24 | "A JetPack image is not pulled." | pre-release | flows |  |
| 25 | "It is several gigabytes and it needs NVIDIA's…" | pre-release | flows |  |
| 26 | "Fat-fingers are not crossed with every board." | pre-release | flows |  |
| 27 | "`runner/tests/test_build_config.py` pins this table to the matrix, so…" | pre-release | flows |  |
| 28 | "Not on the list: a box with no…" | pre-release | flows |  |
| 29 | "Also not a leg, and refused by the…" | pre-release | flows |  |
| 30 | "Those have no shell for a job to…" | pre-release | flows |  |
| 31 | "Android-class sets (Android TV, Google TV, Fire TV,…" | pre-release | flows |  |
| 32 | "A Linux board behind the screen is an…" | pre-release | flows |  |
| 33 | "To add a host or a fat-finger, add…" | pre-release | flows |  |
| 34 | "CI runs the mismatched-job check on Alpine (BusyBox…" | pre-release | flows |  |
| 35 | "A job naming `bash` whose script fits `sh`…" | pre-release | flows |  |
| 36 | "The arm64 leg is the Pi Light proof;…" | pre-release | flows |  |
