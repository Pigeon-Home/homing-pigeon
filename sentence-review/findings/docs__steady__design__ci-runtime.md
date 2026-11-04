# Findings — docs/steady/design/ci-runtime.md

Source: docs/steady/design/ci-runtime.md, reviewed at main b2a9d030.
Sentence units: 97. Flagged: 3. Categories: pre-release 97, post-release 0.

A record of what the CI legs cost and prove: the workflow table with measured times, the legs that hurt and why, and the stand-in table for the emulated legs. The prose around the tables argues from the measurements, and each table answers the paragraph that introduces it. The non-sentences are the 3 table header rows (units 7, 41, 72); every data row is counted as a unit and flows as a record.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Written 2026-10-22, from the runs of that morning." | pre-release | flows |  |
| 2 | "The growth was intentional: more hosts, a real…" | pre-release | flows |  |
| 3 | "This note is what of that is earning…" | pre-release | flows |  |
| 4 | "The numbers below are wall-clock of the job,…" | pre-release | flows |  |
| 5 | "Queue time was the larger number, and it…" | pre-release | flows |  |
| 6 | "Every push to main started four workflows." | pre-release | flows |  |
| 7 | "Workflow \| What it proved \| Measured" | pre-release | flagged | Table header row, structure rather than a sentence |
| 8 | "build.yml `test` \| The whole suite, on Ubuntu,…" | pre-release | flows |  |
| 9 | "build.yml binaries \| PyInstaller for Windows, Windows arm64,…" | pre-release | flows |  |
| 10 | "platform-matrix \| A small portable proof, core tier,…" | pre-release | flows |  |
| 11 | "minimal-userland \| Repair when bash is absent, x86_64…" | pre-release | flows |  |
| 12 | "Docker publish runs on a tag, not on…" | pre-release | flows |  |
| 13 | "The mutation job runs only on a manual…" | pre-release | flows |  |
| 14 | "The seeded mutation run is hourly, at :17." | pre-release | flows |  |
| 15 | "CodeQL is weekly." | pre-release | flows |  |
| 16 | "None of those belong on the push path,…" | pre-release | flows |  |
| 17 | "`build-windows` was the long pole of the build,…" | pre-release | flows |  |
| 18 | "It waited for the Ubuntu suite to finish…" | pre-release | flows |  |
| 19 | "The release then waited for the binaries." | pre-release | flows |  |
| 20 | "The Windows job runs the whole suite, and…" | pre-release | flows |  |
| 21 | "That is a real duplicate, and it should…" | pre-release | flows |  |
| 22 | "The failure it exists for is not theoretical." | pre-release | flows |  |
| 23 | "On 2026-10-22 `os.kill(pid, 0)` raised WinError 87 inside…" | pre-release | flows |  |
| 24 | "Ubuntu cannot see that." | pre-release | flows |  |
| 25 | "A Windows-only module list would have to be…" | pre-release | flows |  |
| 26 | "Five minutes of a Windows runner, on the…" | pre-release | flows |  |
| 27 | "What was not worth it was running that…" | pre-release | flows |  |
| 28 | "The compile does not need the Ubuntu result." | pre-release | flows |  |
| 29 | "The release does." | pre-release | flows |  |
| 30 | "The binary jobs now start with the suite,…" | pre-release | flows |  |
| 31 | "A red suite still cannot publish." | pre-release | flows |  |
| 32 | "A tag's wall clock is the slower of…" | pre-release | flows |  |
| 33 | "The portable proof (`runner/tests/test_platform_proof.py`) is the other duplicate,…" | pre-release | flows |  |
| 34 | "It is not the suite." | pre-release | flows |  |
| 35 | "Copying the suite onto 41 legs would be…" | pre-release | flows |  |
| 36 | "Adding a leg should mean adding that proof,…" | pre-release | flows |  |
| 37 | "minimal-userland is a third small proof, on a…" | pre-release | flows |  |
| 38 | "It is twenty seconds and it stays on…" | pre-release | flows |  |
| 39 | "The Pi Light archive points at it." | pre-release | flows |  |
| 40 | "The core tier had eleven legs, and four…" | pre-release | flows |  |
| 41 | "Leg \| Runner \| Why it hurt" | pre-release | flagged | Table header row, structure rather than a sentence |
| 42 | "native-macos-x86_64 \| `macos-13` \| Retired December 2025. The…" | pre-release | flows |  |
| 43 | "native-windows-arm64 \| `windows-11-arm` \| Same pool as `build-windows-arm64`,…" | pre-release | flows |  |
| 44 | "native-ubuntu-arm64 \| `ubuntu-24.04-arm` \| Same pool as the…" | pre-release | flows |  |
| 45 | "debian-13-arm64 \| `ubuntu-24.04-arm` \| Same pool again" | pre-release | flows |  |
| 46 | "By the afternoon of 2026-10-22 the platform-matrix workflow…" | pre-release | flows |  |
| 47 | "Each new push added another, and none of…" | pre-release | flows |  |
| 48 | "That is not coverage." | pre-release | flows |  |
| 49 | "The leg was not running." | pre-release | flows |  |
| 50 | "Those legs stay in the corpus." | pre-release | flows |  |
| 51 | "The label is `macos-15-intel` now, which is the…" | pre-release | flows |  |
| 52 | "They run on the nightly schedule (09:17 UTC)…" | pre-release | flows |  |
| 53 | "A push runs the core legs whose runner…" | pre-release | flows |  |
| 54 | "A leg is scarce when its runner starts…" | pre-release | flows |  |
| 55 | "`"pool": "scarce"` or `"pool": "plentiful"` on the leg…" | pre-release | flows |  |
| 56 | "The nightly is the frequent full pass." | pre-release | flows |  |
| 57 | "It is one copy, not one copy per…" | pre-release | flows |  |
| 58 | "A new push cancels the previous push's matrix;…" | pre-release | flows |  |
| 59 | "It does not cancel the nightly, and nothing…" | pre-release | flows |  |
| 60 | "It does not drop the Windows suite, on…" | pre-release | flows |  |
| 61 | "It does not merge minimal-userland into the matrix." | pre-release | flows |  |
| 62 | "The matrix proof assumes a normal userland." | pre-release | flows |  |
| 63 | "The point of that workflow is that bash…" | pre-release | flows |  |
| 64 | "It does not run mutation on a push." | pre-release | flows |  |
| 65 | "Seventeen minutes, and it is a signal." | pre-release | flows |  |
| 66 | "A manual dispatch runs it, and the hourly…" | pre-release | flows |  |
| 67 | "It does not try to shard the Ubuntu…" | pre-release | flows |  |
| 68 | "Four minutes is not the queue." | pre-release | flows |  |
| 69 | "Splitting it would make the annotation and the…" | pre-release | flows |  |
| 70 | "Added as full legs on `ubuntu-latest`, under QEMU,…" | pre-release | flows |  |
| 71 | "They run beside the existing nightly, not after…" | pre-release | flows |  |
| 72 | "Leg \| What it stands in for" | pre-release | flagged | Table header row, structure rather than a sentence |
| 73 | "`debian-12-armv7-qemu` (already core) \| 32-bit Raspberry Pi OS,…" | pre-release | flows |  |
| 74 | "`debian-12-arm64-qemu` \| 64-bit Raspberry Pi OS, Armbian Debian" | pre-release | flows |  |
| 75 | "`ubuntu-22.04-arm64-qemu` \| The Ubuntu under a Jetson, and…" | pre-release | flows |  |
| 76 | "`alpine-3-armv7-qemu` \| The same 32-bit boards on musl…" | pre-release | flows |  |
| 77 | "`ros-humble-arm64-qemu` \| ROS 2 Humble, the fleet image…" | pre-release | flows |  |
| 78 | "`ros-jazzy-arm64-qemu` \| ROS 2 Jazzy (`ros:jazzy-ros-base`, Ubuntu 24.04…" | pre-release | flows |  |
| 79 | "Not a leg, on purpose." | pre-release | flows |  |
| 80 | "A second container of an image the nightly…" | pre-release | flows |  |
| 81 | "A NVIDIA JetPack image, which is several gigabytes…" | pre-release | flows |  |
| 82 | "The eight fat-fingers crossed with each board." | pre-release | flows |  |
| 83 | "The proof is the same either way, and…" | pre-release | flows |  |
| 84 | "Put it in `.github/platform-legs.json`." | pre-release | flows |  |
| 85 | "A new distribution on `ubuntu-latest` with `"tier": "core"`…" | pre-release | flows |  |
| 86 | "Keep that set small." | pre-release | flows |  |
| 87 | "One qemu architecture is enough on the push…" | pre-release | flows |  |
| 88 | "The rest are `"tier": "full"` and run nightly." | pre-release | flows |  |
| 89 | "A new Mac, Windows, or ARM hosted runner…" | pre-release | flows |  |
| 90 | "It runs nightly." | pre-release | flows |  |
| 91 | "Do not put it on the push path…" | pre-release | flows |  |
| 92 | "The binary job for that OS already runs…" | pre-release | flows |  |
| 93 | "The proof it runs is `runner/tools/platform_proof.sh` or `runner/tests/test_platform_proof.py`." | pre-release | flows |  |
| 94 | "A skipped proof is a failure (`--no-skips --require-ok`)." | pre-release | flows |  |
| 95 | "Do not add the whole suite to the…" | pre-release | flows |  |
| 96 | "The leg's name has to appear in the…" | pre-release | flows |  |
| 97 | "`runner/tests/test_build_config.py` pins that, the tier size, and the…" | pre-release | flows |  |
