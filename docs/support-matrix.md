# Support matrix — platforms and testing in one file

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

One file that answers the two questions an operator asks before
deploying Homing Pigeon anywhere:

1. What is supported on my platform — and what does each security
   guarantee actually mean there?
2. What testing stands behind that claim?

Levels used below:

- **Supported** — built, tested in CI on that platform, and the
  full security posture (all `security.modes` features at their
  enforce defaults) is available.
- **Supported, reduced confinement** — built and tested, the
  runner runs with its full authentication and policy posture,
  but confinement on this platform is weaker than the Linux
  namespace sandbox: on macOS the backend applies a Seatbelt
  profile (system trees and the interpreter's prefix readable,
  the work directory the only writable tree, no network) with
  spawn resource limits — a profile over the host filesystem,
  not a namespace or a jail; on Windows the backend
  applies resource limits, a restricted token and a low
  integrity level, with no namespace isolation. The startup
  posture printout says which. (FreeBSD stood at this level
  until 2026-11-14, when its per-job jail was rebuilt to hold
  what the Linux sandbox holds; its row says what that is and
  what stands behind it.)
- **Experimental** — a CI leg or a documented target exists, but
  it is not part of the release guarantee.
- **Not supported** — no build, no tests, no claim.

## Platform support

| Platform | Level | Confinement | job_user | Oracle | Evidence |
|---|---|---|---|---|---|
| Linux x86-64 (glibc, Python 3.9+) | **Supported** | Enforce available: user/IPC/network/UTS namespaces probed at startup; a box that cannot enforce refuses to start | Enforce available (POSIX) | Full (interactive + mailbox) | Full suite in CI (12,677 tests at the full-suite collection taken on 2026-11-13, against 12,780 at the collection of 2026-11-11); switch proofs on the real kernel; platform-matrix and build legs green |
| Linux ARM64 | **Supported** | Same as x86-64 | Enforce available (POSIX) | Full | ARM64 build legs (ubuntu-22.04-arm) in CI; Pi Light targets this family |
| Linux, minimal userland | **Supported** | Same as x86-64 where bwrap is present | Enforce available (POSIX) | Full; Pi Light profile = deterministic Oracle, no local LLM | Dedicated minimal-userland workflow |
| Linux as root | **Supported** | Same as x86-64 | Enforce available | Full | Linux-root switch-proof legs in CI |
| Raspberry Pi (Pi Light) | **Supported** | Same as Linux ARM64 | Enforce available (POSIX) | Deterministic only (by design — no local model) | Pi Light build leg; the profile is a config choice, not a separate codebase |
| macOS (Intel and Apple silicon) | **Supported, reduced confinement** | Enforce available via the macOS backend (bwrap is Linux-only): a Seatbelt profile generated per job and applied by `sandbox-exec` — deny-by-default, the system trees and the job interpreter's own install prefix readable, the job's work directory the only writable tree, and no network at all (the profile names no network allow rule) — with a 512 MiB per-process memory ceiling applied at spawn as resource limits by a small launcher shim; the audit record names exactly "macos: seatbelt_profile + no_network + spawn_resource_limits". Startup probes the backend — the tool present, a generated profile that parses, and a confined trial spawn that reads a staged file and writes its work directory — and refuses when it cannot engage. It is a profile over the host filesystem, not a namespace and not a jail | Enforce available (POSIX); when confinement also engages, the named user is applied inside the launcher shim at spawn | Full | macOS build legs (macos-15 and macos-15-intel); full suite in CI in 3 parallel jobs packed by measured duration (12,677 tests at the full-suite collection taken on 2026-11-13). The confinement backend's live tests run in those CI legs (probe, confined spawn, escape write and read refused, network refused, spawn limits carried). The data-size refusal that once stood as the live word on the spawn limits is closed — five rounds of fixes closed it — and the one live point that then failed, the spawn-limits read-back (its address-space assertion compared the read-back against one platform's report of unlimited), is fixed. Live proof stands on the completed green `test-macos` jobs since: the build on the 3.16.25.8 release head of 2026-11-13 completed green, its `test-macos` jobs among them; there is no Mac in the project's own fleet, so no field proof on project hardware is claimed for this backend |
| Windows x86-64 | **Supported, reduced confinement** | Enforce available via the Windows backend: a Job Object memory ceiling (512 MiB per process), a restricted token (privileges stripped, Administrators group disabled) and a low integrity level, applied at creation — the audit record names exactly "windows: job_object + restricted_token + low_integrity". No filesystem namespace isolation: a confined job can still read any path its token can read. Startup probes the backend and refuses when it cannot engage | Enforce available via a Job Objects backend: a per-process memory ceiling assigned as each job starts, and a job that cannot be assigned is refused; the POSIX setuid demote itself does not exist here | Full | Windows build leg (windows-latest); Windows switch-proof legs in CI. Field-proven on the project's own Windows rig: the full 17-step rig battery passed at every security mode enforce on 2026-11-10 — the startup probe engaged, the escape write was blocked, a 700 MiB allocation was refused by the ceiling, tampered and wrong-audience jobs were rejected, and the production install stood untouched throughout (the escape read succeeded, as the confinement column states: the token's reads are not walled). The Job Objects backend carries job_user with the memory ceiling only; an AppContainer backend for confinement parity is not built yet |
| Windows ARM64 | **Supported, reduced confinement** | As Windows x86-64 | As Windows x86-64 | Full | windows-11-arm build leg |
| Docker (GHCR image) | **Supported** | Inherits the host kernel's answer above | Inherits host | Full | docker workflow; image attested by digest; sums verifiable per docs/steady/verification.md |
| FreeBSD | **Supported** | Enforce available via the FreeBSD backend: each job runs inside a jail made for it — a read-only root, the host's system directories mounted read-only below it, the job's work directory and a bounded `/tmp` (512 MiB) the only two trees that take a write, a process table of its own, no network at all (`ip4`/`ip6` disabled; a loopback of the job's own by a config switch), every mount `nosuid`, and root inside the jail holding no privilege (`allow.nosuser`) — with a 512 MiB per-process memory ceiling the job cannot raise and, on a host with RACCT enabled, rctl rules on the jail as a whole (256 processes, 2 GiB of address space across them). The audit record names the controls a job's jail carried, from the floor "freebsd: jail + no_network + spawn_resource_limits" up. The operator's read-only binds and work mount are the Linux sandbox's keys, and an interpreter outside the system trees gets its install prefix read-only, recorded, by the Linux sandbox's rule. A job's jail is removed, with every process in it, when the job ends or its runner dies. Startup probes the backend — a throwaway jail and a trial process that reads the boundary from inside — and refuses when it cannot engage. A fresh install asks the same probe before it writes its config: the mode stays at `enforce` where the probe passes, and is stated at `audit`, with the reason printed, where it does not (an ordinary user's install, most often). The backend needs root; there is no Capsicum; and the jail-wide ceilings are named only where RACCT is enabled (it is not on the fleet node). The design is docs/steady/design/freebsd-confinement-design.md | Enforce available (POSIX); when confinement also engages, the named user is applied at the jail door at spawn, and the `nosuid` mounts keep it from coming back as root | Not claimed | A freebsd CI workflow exists (weekly, on dispatch, and dispatched by the tag build when the tag's tree changed under runner/): on the v3.16.25.8 tag run of 2026-11-13 it produced the workflow's first artifact — the suite log, the switch-roster report, the sh-parser log and the verdict file, with every completed red named (2 reds, both in the remediation tests) and the switch roster inside the VM at 23 of 23 — but the suite itself is not green: it was killed at its 30-minute wall on that run, and no hosted run has completed green, so there is no release guarantee yet. A dedicated node running FreeBSD 14.5-RELEASE stands in the project's own fleet (stood up 2026-11-10) with the runner installed from the tree; against a battery copy of that tree the full 17-step rig battery passed at every security mode enforce on 2026-11-10 — startup probe engaged, escape write and escape read both contained by the jail root, the 512 MiB spawn limit refused a 700 MiB job, and the production install stood untouched throughout — and local end-to-end submission was proven on the node on 2026-11-11 through the file transport, driven by the project's own sender tool (submit, watched folder, verified decrypted result); the node's mailbox is not paired into its config yet, so it is not polling a mailbox. The confinement backend's own live proof is hosted and separate: the freebsd-confinement workflow (weekly and on dispatch) boots FreeBSD 14.5 and 15.0 guests with RACCT enabled and runs the backend's test module as root. Its first run, on 2026-11-14 against the first backend (run 43574966807), read the boundary from inside a job and found 7 of 9 boundary tests red on both releases — a job could lift its own memory ceiling, write the jail root, run a set-user-ID program as root, fill `/tmp` without bound, and every job left a mount behind; the backend described in this row was built against those tests, and its own first hosted run (run 43578228704, the same day) passed whole on 14.5-RELEASE and 15.0-RELEASE-p13 and left nothing on either guest: the nine boundary tests, the jail-wide rctl rules refusing a fork and an allocation, the private loopback reaching itself alone, the operator's binds and work mount, a runner killed outright losing its jail, and a job through the runner itself confined, recorded and collected. A third guest runs 14.5 as FreeBSD ships, RACCT off, the node's own state, and passed beside the other two on its first run (run 43578832525): there the record names no rctl control and the two rctl tests skip by design. The project's own node (14.5-RELEASE, RACCT off) ran the backend's live classes on 2026-11-14, independently of the build, in a test root with the production install untouched: 27 of 29 passed and the two that need RACCT skipped by name. The node's 17-step battery of 2026-11-10 was of the first backend; the full battery has not been run against this shape. The mode a fresh install states has its own live tests in the same workflow: on their first run (run 43585328369, 2026-11-14) the installer's seed left `enforce` as root on all three guests, a runner started on that config confined its first job, the same seed asked by an ordinary user stated `audit` and named root, and a config asking for a jail-wide ceiling was seeded at `enforce` on the two guests with RACCT and at `audit` on the one without; the node has not run them |
| Anything else (other BSDs, musl-only builds, Python < 3.9) | **Not supported** | — | — | — | No build, no tests |

Notes that belong with the table:

- Authentication and policy are platform-independent: HMAC is
  required in every mode on every platform, cleartext jobs are
  refused by default everywhere and reachable only by explicit
  CLI flags, and every `security.modes` feature defaults to
  enforce everywhere. What varies by platform is confinement and
  execution identity only — the two rows above.
- The security audit log is bounded: it rolls over to a single
  backup file when it reaches 20,000 lines by default (the
  `security.audit_max_lines` setting).
- The audit log is tamper-evident: every entry carries a
  sequence number and a SHA-256 hash chain over the previous
  entry's chain value, the chain carries across the rollover,
  and `--audit-verify` walks the chain and reports the first
  break. Entries written before chaining existed form an
  unchained legacy prefix and are reported as such.
- Protocol v3 (DTLS over email, hybrid X25519MLKEM768) is a
  config-gated profile, off by default on every platform. Its
  ML-KEM-768 and X25519 are pure Python and are **not
  constant-time** (stated in `runner/wire/mlkem.py`); treat v3 as
  a research/interoperability profile until a native crypto
  provider is configured.
- The runner prints its posture at startup on every platform.
  The printed posture, not this table, is the final word for a
  given box.

## Testing support

What stands behind the claims above, and where each kind of
testing runs. (Counts are as of the full-suite collection
taken on 2026-11-13; this file should be regenerated or
test-pinned when they move.)

| Test kind | What it proves | Where it runs |
|---|---|---|
| Unit + integration suite (12,677 tests at the collection of 2026-11-13) | The core contract: protocol verification, policy, config refusal classes, transports, Oracle doors | Linux full run in CI; macOS in 3 shards; push runs a core leg set, nightly/manual runs the full corpus (runner/tools/platform_plan.py) |
| Switch proofs | The security-mode switches actually change behavior on a real kernel — enforce refuses, audit logs, off is off | switch-proofs workflow: Linux, Linux-root, macOS, macOS-root, Windows legs |
| Platform matrix | Builds and platform-specific behavior across OS/architecture legs, including scarce hosted runners on the full-corpus schedule | platform-matrix workflow |
| Coverage | 99.0% statements / 96.7% branches (1-Nov-2026 report), every shipped file above 90% | coverage workflow |
| Mutation testing | The suite is not made of tests that always pass: seeded mutations must be caught. This proof is currently owed, not standing: the walk's last completed mutant-testing run is 2026-10-26, and its baseline has died before a mutant is tested since | mutation-seeded workflow (hourly and on dispatch) |
| Fuzzing | Signed-object fuzzer (found the pre-auth quadratic DoS class by latency); a hybrid fuzzing pass (RFC 10024): 227,470 real-crypto rounds in 3,600 s, 0 findings, plus abstract-mode passes; the pass caught the F-1 missing-key_share refusal, now fixed and regression-pinned | Records under docs/infrastructure-documents/proofs/ |
| Property / stateful / race tests | Protocol state machines, replay and in-flight claim behavior, hostile-regex timing | Inside the main suite (Hypothesis) |
| Upgrade proof | A release upgrade preserves state and restarts cleanly: the proof installs one tree, upgrades it with another, and checks every owner key and state file survives (a plain restart is measured at ~8 s on the project's own rig) | upgrade-proof workflow (nightly, on dispatch, and dispatched by the tag build) |
| Minimal userland | The runner works with a stripped userland (Pi Light class machines) | minimal-userland workflow |
| Soak | Long-running stability of the mail loop and workers | soak workflow |
| Release verification | Every release: SHA384SUMS over all assets, Sigstore build provenance, SBOM, PyPI OIDC trusted publishing, GHCR attestation | the release pipeline the cut-release workflow starts (the release and publish jobs in build.yml, the image attestation in docker.yml); operator instructions in docs/steady/verification.md |
| FreeBSD confinement proof | The jail backend's boundary on a real kernel, read from inside a job as root: which trees take a write, whether a job can lift its ceiling or keep a privilege, whether a set-user-ID bit is honoured, whether `/tmp` is bounded, what the jail-wide rctl rules refuse, what a private loopback reaches, what a finished job or a dead runner leaves on the host, and the mode a fresh install states there as root and as an ordinary user | freebsd-confinement workflow: FreeBSD 14.5 and 15.0 guests with RACCT enabled, and a 14.5 guest as FreeBSD ships, RACCT off (weekly and on dispatch) |
| Skip discipline | A skip is not a pass: every skip reason is registered (`runner/tests/test_skip_registry.py`) and the CI skip guard enumerates them | skip guard in CI |

Not yet true, stated plainly so this file stays honest:

- No green hosted FreeBSD suite run: the freebsd workflow's
  suite is killed at its 30-minute wall under emulation, and
  its first artifact (the v3.16.25.8 tag run of 2026-11-13)
  names the reds rather than clearing them; FreeBSD's support
  rests on the fleet node's field proof, not on hosted CI.
  The confinement backend's live proof is a workflow of its
  own (freebsd-confinement), green on hosted 14.5 and 15.0,
  and the node's battery was of the first backend: the
  backend the table describes has had its live classes run
  on the node, not the battery.
- No independent third-party security audit has been performed.
- No second implementation of Protocol v3 exists.
- Confinement parity across platforms does not exist yet (see
  the platform table): Linux confines with a namespace sandbox,
  and FreeBSD with a per-job jail that holds what the sandbox
  holds but cannot, as the sandbox can, confine without root;
  Windows confines with resource limits, a restricted token
  and a low integrity level, and no namespace isolation; macOS
  confines with a per-job Seatbelt profile and spawn resource
  limits, a profile over the host filesystem rather than a
  separate root.

*Maintenance rule for this file: when a platform leg, a workflow,
or a support level changes, this file changes in the same commit —
and the follow-on work is to generate the platform table from the
workflow and platform-driver definitions so it cannot drift.*
