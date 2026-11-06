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
  but kernel confinement is not available on this platform, so
  `confinement` at enforce refuses to start and the operator must
  consciously choose a lower mode. The startup posture printout
  says which.
- **Experimental** — a CI leg or a documented target exists, but
  it is not part of the release guarantee.
- **Not supported** — no build, no tests, no claim.

## Platform support

| Platform | Level | Confinement (bwrap) | job_user | Oracle | Evidence |
|---|---|---|---|---|---|
| Linux x86-64 (glibc, Python 3.9+) | **Supported** | Enforce available: user/IPC/network/UTS namespaces probed at startup; a box that cannot enforce refuses to start | Enforce available (POSIX) | Full (interactive + mailbox) | Full suite in CI (10,304 tests, OK, at the last full run recorded before this file landed); switch proofs on the real kernel; platform-matrix and build legs green |
| Linux ARM64 | **Supported** | Same as x86-64 | Enforce available (POSIX) | Full | ARM64 build legs (ubuntu-22.04-arm) in CI; Pi Light targets this family |
| Linux, minimal userland | **Supported** | Same as x86-64 where bwrap is present | Enforce available (POSIX) | Full; Pi Light profile = deterministic Oracle, no local LLM | Dedicated minimal-userland workflow |
| Linux as root | **Supported** | Same as x86-64 | Enforce available | Full | Linux-root switch-proof legs in CI |
| Raspberry Pi (Pi Light) | **Supported** | Same as Linux ARM64 | Enforce available (POSIX) | Deterministic only (by design — no local model) | Pi Light build leg; the profile is a config choice, not a separate codebase |
| macOS (Intel and Apple silicon) | **Supported, reduced confinement** | Not available (bwrap is Linux-only; confinement at enforce refuses to start — fail-closed, never silent) | Enforce available (POSIX) | Full | macOS build legs (macos-15); full suite in 3 shards in CI (3,388 + 3,355 + 3,363 tests at the last full run recorded before this file landed). A Seatbelt (`sandbox-exec`) confinement backend is the known path to full parity; not built yet |
| Windows x86-64 | **Supported, reduced confinement** | Not available (same fail-closed refusal as macOS) | job_user at enforce refuses on win32 rather than silently doing nothing | Full | Windows build leg (windows-latest); Windows switch-proof legs in CI. An AppContainer + Job Objects backend is the known path to parity; not built, and not scheduled until a Windows deployment needs confinement rather than a lowered mode |
| Windows ARM64 | **Supported, reduced confinement** | As Windows x86-64 | As Windows x86-64 | Full | windows-11-arm build leg |
| Docker (GHCR image) | **Supported** | Inherits the host kernel's answer above | Inherits host | Full | docker workflow; image attested by digest; sums verifiable per docs/steady/verification.md |
| FreeBSD | **Experimental** | Not available | Not claimed | Not claimed | A freebsd CI workflow exists; no release guarantee |
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
testing runs. (Counts are as of the last full-suite records in
the repository; this file should be regenerated or test-pinned
when they move.)

| Test kind | What it proves | Where it runs |
|---|---|---|
| Unit + integration suite (~10,300 tests) | The core contract: protocol verification, policy, config refusal classes, transports, Oracle doors | Linux full run in CI; macOS in 3 shards; push runs a core leg set, nightly/manual runs the full corpus (runner/tools/platform_plan.py) |
| Switch proofs | The security-mode switches actually change behavior on a real kernel — enforce refuses, audit logs, off is off | switch-proofs workflow: Linux, Linux-root, macOS, macOS-root, Windows legs |
| Platform matrix | Builds and platform-specific behavior across OS/architecture legs, including scarce hosted runners on the full-corpus schedule | platform-matrix workflow |
| Coverage | 99.0% statements / 96.7% branches (1-Nov-2026 report), every shipped file above 90% | coverage workflow |
| Mutation testing | The suite is not made of tests that always pass: seeded mutations must be caught | mutation-seeded workflow |
| Fuzzing | Signed-object fuzzer (found the pre-auth quadratic DoS class by latency); a hybrid fuzzing pass (RFC 10024): 227,470 real-crypto rounds in 3,600 s, 0 findings, plus abstract-mode passes; the pass caught the F-1 missing-key_share refusal, now fixed and regression-pinned | Records under docs/infrastructure-documents/proofs/ |
| Property / stateful / race tests | Protocol state machines, replay and in-flight claim behavior, hostile-regex timing | Inside the main suite (Hypothesis) |
| Upgrade proof | A release upgrade preserves state and restarts cleanly (measured: plain restart ~8 s, full upgrade under 1 minute) | upgrade-proof workflow |
| Minimal userland | The runner works with a stripped userland (Pi Light class machines) | minimal-userland workflow |
| Soak | Long-running stability of the mail loop and workers | soak workflow |
| Release verification | Every release: SHA384SUMS over all assets, Sigstore build provenance, SBOM, PyPI OIDC trusted publishing, GHCR attestation | cut-release workflow; operator instructions in docs/steady/verification.md |
| Skip discipline | A skip is not a pass: every skip reason is registered (`runner/tests/test_skip_registry.py`) and the CI skip guard enumerates them | skip guard in CI |

Not yet true, stated plainly so this file stays honest:

- No independent third-party security audit has been performed.
- No second implementation of Protocol v3 exists.
- Confinement parity across platforms does not exist yet (see
  the platform table); only Linux confines at enforce today.

*Maintenance rule for this file: when a platform leg, a workflow,
or a support level changes, this file changes in the same commit —
and the follow-on work is to generate the platform table from the
workflow and platform-driver definitions so it cannot drift.*
