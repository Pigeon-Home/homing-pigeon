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
  until 2026-11-14, when its per-job jail was rebuilt with a
  read-only root, no privilege inside and ceilings the job
  cannot raise; its row says what the jail holds, what it
  does not, and what stands behind it.)
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
| macOS (Intel and Apple silicon) | **Supported, reduced confinement** | Enforce available via the macOS backend (bwrap is Linux-only), with no root: a Seatbelt profile generated per job and applied by `sandbox-exec` — deny-by-default, the system trees and the job interpreter's own install prefix readable, the job's work directory the only writable tree, and no network at all (the profile names no network allow rule) — with a ceiling on each job process's address map set at spawn by a small launcher shim, the system shell: 512 MiB above the size a bare process starts at on that Mac unless `security.confinement.macos.process_memory_bytes` names another, set soft and hard, so it is not the job's to raise; the audit record names exactly "macos: seatbelt_profile + no_network + spawn_resource_limits". Nothing in the chain is the runner's own interpreter, so a release's frozen macOS binaries engage it as a runner started from source does. Startup probes the backend — the tools present, a generated profile that parses, and a confined trial that reads a staged file, writes its work directory, is refused a write and a read outside it and carries a ceiling of its own — and refuses when it cannot engage. A fresh install asks the same probe on the Mac it installs on: the mode stays at `enforce` where it passes, and is stated at `audit`, with the reason printed, where it does not. It is a profile over the host filesystem, not a namespace and not a jail: a job can list the host's processes and can reach the session's services — the clipboard was read from inside a job on both hosted Macs — and there is no ceiling on a job as a whole, on processor time or on cores | Enforce available (POSIX); when confinement also engages, the named user is applied by the spawn itself, to `sandbox-exec`, the launcher and the job alike | Full | macOS build legs (macos-15 and macos-15-intel); full suite in CI in 3 parallel jobs packed by measured duration (12,677 tests at the full-suite collection taken on 2026-11-13). The confinement backend's live tests run in those CI legs, and in a workflow of the backend's own (macos-confinement) on a hosted Apple silicon Mac and a hosted Intel Mac, as the ordinary user and as root, where the frozen release binaries are asked as well. That workflow's first run, on 2026-11-15, read the first backend there: its live points green on both Macs as both users, a bare process's address map at 391.7 GiB and 32.5 GiB, and the frozen runner refusing to start at `enforce`. The launcher that closes that refusal is judged by the same workflow; there is no Mac in the project's own fleet, so no field proof on project hardware is claimed for this backend |
| Windows x86-64 | **Supported, reduced confinement** | Enforce available via the Windows backend: a Job Object memory ceiling (512 MiB per process), a restricted token (privileges stripped, Administrators group disabled) and a low integrity level, applied at creation — the audit record names exactly "windows: job_object + restricted_token + low_integrity". No filesystem namespace isolation: a confined job can still read any path its token can read. Startup probes the backend and refuses when it cannot engage | Enforce available via a Job Objects backend: a per-process memory ceiling assigned as each job starts, and a job that cannot be assigned is refused; the POSIX setuid demote itself does not exist here | Full | Windows build leg (windows-latest); Windows switch-proof legs in CI. Field-proven on the project's own Windows rig: the full 17-step rig battery passed at every security mode enforce on 2026-11-10 — the startup probe engaged, the escape write was blocked, a 700 MiB allocation was refused by the ceiling, tampered and wrong-audience jobs were rejected, and the production install stood untouched throughout (the escape read succeeded, as the confinement column states: the token's reads are not walled). The Job Objects backend carries job_user with the memory ceiling only; an AppContainer backend for confinement parity is not built yet |
| Windows ARM64 | **Supported, reduced confinement** | As Windows x86-64 | As Windows x86-64 | Full | windows-11-arm build leg |
| Docker (GHCR image) | **Supported** | Inherits the host kernel's answer above | Inherits host | Full | docker workflow; image attested by digest; sums verifiable per docs/steady/verification.md |
| FreeBSD | **Supported** | Enforce available via the FreeBSD backend: each job runs inside a jail made for it — a read-only root, the host's system directories mounted read-only below it, the job's work directory and a bounded `/tmp` (512 MiB) the only two trees that take a write, a process table of its own, no network at all (`ip4`/`ip6` disabled; a loopback of the job's own by a config switch), every mount `nosuid`, and root inside the jail holding no privilege (`allow.nosuser`) — with a 512 MiB per-process memory ceiling the job cannot raise and, on a host with RACCT enabled, rctl rules on the jail as a whole (256 processes, 2 GiB of address space across them); a job that goes in as a job user is also held to 256 processes of that user across the host, by a limit set at the jail door that needs no RACCT. On a host with more than one core the jail is pinned to all but one of the cores the runner may run on, the lowest-numbered never a job's, by a cpuset the job cannot widen that needs no RACCT either. The audit record names the controls a job's jail carried, from the floor "freebsd: jail + no_network + spawn_resource_limits" up. The operator's read-only binds and work mount are the Linux sandbox's keys, and an interpreter outside the system trees gets its install prefix read-only, recorded, by the Linux sandbox's rule. A job's jail is removed, with every process in it, when the job ends or its runner dies. Startup probes the backend — a throwaway jail and a trial process that reads the boundary from inside — and refuses when it cannot engage. A fresh install asks the same probe before it writes its config: the mode stays at `enforce` where the probe passes, and is stated at `audit`, with the reason printed, where it does not (an ordinary user's install, most often). The backend needs root, and a job with no job user is still the owner of what root owns: it holds no privilege, but it reads a root-only file in a tree the jail shows it (`/usr/local/etc` among them) until `security.job_user` names a user. A fresh install whose probe passes makes an account for the jobs alone (`pigeon-jobs`: no password, no login shell, no home directory) and names it, after a trial job as that account has run inside a jail on that machine and been refused a root-only file; where the account cannot be had `nobody` stands in on the same trial; an install seeded before that names none; there is no Capsicum; and the jail-wide ceilings are named only where RACCT is enabled (it is not on the fleet node), so a job with no job user has no ceiling on its processes there; the limit on cores is a set of cores, not a share of time, shared by the jobs that run at once, and a host with one core holds none back. The design is docs/steady/design/freebsd-confinement-design.md | Enforce available (POSIX); when confinement also engages, the named user is applied at the jail door at spawn, the `nosuid` mounts keep it from coming back as root, and its processes are held to a ceiling that needs no RACCT | Not claimed | A freebsd CI workflow exists (weekly, on dispatch, and dispatched by the tag build when the tag's tree changed under runner/): on the v3.16.25.8 tag run of 2026-11-13 it produced the workflow's first artifact — the suite log, the switch-roster report, the sh-parser log and the verdict file, with every completed red named (2 reds, both in the remediation tests) and the switch roster inside the VM at 23 of 23 — and its suite was stopped at its 30-minute clock. The suite first ran whole and green there on the v3.16.26.6 tag (run 43612998944, 2026-11-14): as an ordinary user on 15.0-RELEASE-p13, 13,294 tests, 167 skipped by name and none red, in 1,683 seconds, the roster at 23 of 23 beside it. That clock stood inside the guest's own spread: of the fourteen runs from the first artifact to 2026-11-15, seven finished, in 1,360 to 1,683 seconds, and seven were stopped at 1,800, each in the last third of the suite; from 2026-11-15 the clock is 45 minutes. The first run under it (run 43663671470, 2026-11-15) was a slow one, and it finished: 13,331 tests, 174 skipped by name and none red, in 1,969 seconds, where the clock before it would have stopped the run at 1,800. The next run, on the tag that carried the change (run 43666816253, the same day), ran the same 13,331 tests green in 1,178 seconds. The workflow is a signal, not a gate: it runs after a release is out, and no release waits for it. A dedicated node running FreeBSD 14.5-RELEASE stands in the project's own fleet (stood up 2026-11-10) with the runner installed from the tree; against a battery copy of that tree the full 17-step rig battery passed at every security mode enforce on 2026-11-10 — startup probe engaged, escape write and escape read both contained by the jail root, the 512 MiB spawn limit refused a 700 MiB job, and the production install stood untouched throughout — and local end-to-end submission was proven on the node on 2026-11-11 through the file transport, driven by the project's own sender tool (submit, watched folder, verified decrypted result); the node's mailbox is not paired into its config yet, so it is not polling a mailbox. The confinement backend's own live proof is hosted and separate: the freebsd-confinement workflow (weekly and on dispatch) boots FreeBSD 14.5 and 15.0 guests with RACCT enabled and runs the backend's test module as root. Its first run, on 2026-11-14 against the first backend (run 43574966807), read the boundary from inside a job and found 7 of 9 boundary tests red on both releases — a job could lift its own memory ceiling, write the jail root, run a set-user-ID program as root, fill `/tmp` without bound, and every job left a mount behind; the backend described in this row was built against those tests, and its own first hosted run (run 43578228704, the same day) passed whole on 14.5-RELEASE and 15.0-RELEASE-p13 and left nothing on either guest: the nine boundary tests, the jail-wide rctl rules refusing a fork and an allocation, the private loopback reaching itself alone, the operator's binds and work mount, a runner killed outright losing its jail, and a job through the runner itself confined, recorded and collected. A third guest runs 14.5 as FreeBSD ships, RACCT off, the node's own state, and passed beside the other two on its first run (run 43578832525): there the record names no rctl control and the two rctl tests skip by design. The project's own node (14.5-RELEASE, RACCT off) ran the backend's live classes on 2026-11-14, independently of the build, in a test root with the production install untouched: 27 of 29 passed and the two that need RACCT skipped by name. The node's 17-step battery of 2026-11-10 was of the first backend; the full battery has not been run against this shape. The mode a fresh install states has its own live tests in the same workflow: on their first run (run 43585328369, 2026-11-14) the installer's seed left `enforce` as root on all three guests, a runner started on that config confined its first job, the same seed asked by an ordinary user stated `audit` and named root, and a config asking for a jail-wide ceiling was seeded at `enforce` on the two guests with RACCT and at `audit` on the one without. The job user the seed names ran there next (run 43592323669, 2026-11-14): as root the seed named `nobody` on all three guests, and a runner started on that config ran its first job as uid 65534, refused a root-only file in a tree it was shown. The account the installer makes ran there last (run 43597374538, 2026-11-14), on the guests alone because its tests add a user to their host: the installer made `pigeon-jobs` on all three and named it, a runner on that config ran its first job as that account, an account already there was used unchanged, and one the seed could not use was removed again. That a test run leaves the machine alone ran there after it (run 43607344777, 2026-11-14): the other modules' installer and wizard tests, started as root as the suite starts them, left no jobs account and nothing else, the same installer tests made the account once `HP_SEED_ASKS_MACHINE` was set on, and the posture report's tests read clean as an ordinary user. The job user's process ceiling ran there next (run 43656341793, 2026-11-15): under a ceiling of 24 a job that went in as a job user held 24 processes and was refused the next fork, with RACCT and without, could not raise the limit, and shared the one count with a second job of the account in another jail. The limit on a job's cores ran there next (run 43673558329, 2026-11-15, each guest with four cores): a job under the default read cores 1, 2 and 3 as its own, with RACCT and without, was refused all four as uid 0 inside the jail and as a job user, and eight processes spinning in a job pinned to one core used one core's worth of processor, 3.07 seconds in 3.07, where the same job with no core held back used a little over 12; a runner itself kept to two of a guest's cores kept its jobs to them (run 43675959619), where a job in a jail it left unpinned took all four; a host with one core has not been run, and the node has not run them |
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
| FreeBSD confinement proof | The jail backend's boundary on a real kernel, read from inside a job as root: which trees take a write, whether a job can lift its ceiling or keep a privilege, whether a set-user-ID bit is honoured, whether `/tmp` is bounded, what the jail-wide rctl rules refuse, whether a job user's process ceiling holds with RACCT and without, which cores a job runs on and whether it can widen them, what a private loopback reaches, what a finished job or a dead runner leaves on the host, and the mode a fresh install states there as root and as an ordinary user | freebsd-confinement workflow: FreeBSD 14.5 and 15.0 guests with RACCT enabled, and a 14.5 guest as FreeBSD ships, RACCT off (weekly and on dispatch) |
| macOS confinement proof | The Seatbelt backend's boundary on the two Macs the release freezes its macOS binaries on, read from inside a job as the ordinary user a macOS install runs as and again as root: the one tree that takes a write, the ceiling on a process's address map and whether the job can lift it, whether a set-user-ID program starts, a signal to a process outside, a job handed to launchd, a job user at the spawn door, and the mode a fresh install states there; then the release's frozen runner and frozen installer, asked whether a job runs confined through the one and whether the other leaves `enforce` in the config it writes | macos-confinement workflow: an Apple silicon leg (macos-15) and an Intel leg (macos-15-intel), weekly and on dispatch; a signal, not a gate |
| Skip discipline | A skip is not a pass: every skip reason is registered (`runner/tests/test_skip_registry.py`) and the CI skip guard enumerates them | skip guard in CI |

Not yet true, stated plainly so this file stays honest:

- No release waits for a FreeBSD run: the freebsd workflow's
  suite first ran whole and green on 2026-11-14 (the
  v3.16.26.6 tag), but it runs after a release is out, so a
  release can go out with that suite red or stopped at its
  clock. Of its fourteen runs from its first artifact
  (2026-11-13) to 2026-11-15, one was green, six finished red
  and seven were stopped at the 30-minute clock it then had.
  The confinement backend's live proof is a workflow of its
  own (freebsd-confinement), green on hosted 14.5 and 15.0,
  and no gate either; and the node's battery was of the first
  backend: the backend the table describes has had its live
  classes run on the node, not the battery.
- No independent third-party security audit has been performed.
- No second implementation of Protocol v3 exists.
- Confinement parity across platforms does not exist yet (see
  the platform table): Linux confines with a namespace sandbox,
  and FreeBSD with a per-job jail that cannot, as the sandbox
  can, confine without root — so a FreeBSD job with no job
  user still reads what root owns in the trees it is shown,
  where a Linux job reads what the runner's ordinary user can;
  Windows confines with resource limits, a restricted token
  and a low integrity level, and no namespace isolation; macOS
  confines with a per-job Seatbelt profile and a per-process
  memory ceiling, a profile over the host filesystem rather
  than a separate root, which leaves a job able to reach the
  session's services and holds no ceiling on a job as a
  whole.

*Maintenance rule for this file: when a platform leg, a workflow,
or a support level changes, this file changes in the same commit —
and the follow-on work is to generate the platform table from the
workflow and platform-driver definitions so it cannot drift.*
