# Findings — docs/infrastructure-documents/security/security-gaps.md

Source: docs/infrastructure-documents/security/security-gaps.md, reviewed at main aa570da1.
Sentence units: 65. Flagged: 4. Categories: pre-release 65, post-release 0.

The honest accounting of the default installation: the job is the runner, protections compose in 1 order (split the identities, ACL the secrets, cage the workspace), what is not a filesystem question, and the expected-technologies list with a status for each. The numbered steps are split by their own formatting — the numeral stands as its own unit (units 10, 15, 23) and the heading sentence completes in the unit after — and the platform table's header row (unit 17) is structure; the table's data rows are counted as units and flow as records. Everything else chains: each step's uselessness without the previous one is the argument.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This is the honest accounting." | pre-release | flows |  |
| 2 | "The project's threat model (`docs/security/threat-model.md`) says: the shared…" | pre-release | flows |  |
| 3 | "This document says what the *default* installation actually…" | pre-release | flows |  |
| 4 | "With default settings, **the job is the runner**:…" | pre-release | flows |  |
| 5 | "Every file permission on the box is theater…" | pre-release | flows |  |
| 6 | "The restrictions are deliberately near zero out of…" | pre-release | flows |  |
| 7 | "Everything below follows from that." | pre-release | flows |  |
| 8 | "Protections compose in one order." | pre-release | flows |  |
| 9 | "Each step is useless without the ones before…" | pre-release | flows |  |
| 10 | "**1." | pre-release | flagged | A bare step numeral standing as its own unit; the step's heading sentence completes in the next unit |
| 11 | "Split the identities.** The job must run as…" | pre-release | flows |  |
| 12 | "That's `security.modes.job_user` (`enforce`) on POSIX — the runner…" | pre-release | flows |  |
| 13 | "On Windows that's `install.exe --run-as` with a limited…" | pre-release | flows |  |
| 14 | "Until this is done, steps 2 and 3…" | pre-release | flows |  |
| 15 | "**2." | pre-release | flagged | A bare step numeral standing as its own unit; the step's heading sentence completes in the next unit |
| 16 | "ACL the secrets away from the job.** Once…" | pre-release | flows |  |
| 17 | "Platform \| What exists \| The gap" | pre-release | flagged | Table header row, structure rather than a sentence |
| 18 | "Linux \| `job_user` (setuid), `install.py` writes owner-only `0600`…" | pre-release | flows |  |
| 19 | "macOS \| launchd agent as the installing user…" | pre-release | flows |  |
| 20 | "FreeBSD \| cron `@reboot` as the user \|…" | pre-release | flows |  |
| 21 | "Windows \| Scheduled Task (SYSTEM by default, or…" | pre-release | flows |  |
| 22 | "`--posture` already warns about the Windows ACL; it…" | pre-release | flows |  |
| 23 | "**3." | pre-release | flagged | A bare step numeral standing as its own unit; the step's heading sentence completes in the next unit |
| 24 | "Cage the workspace.** `workspace_root` and `protected_paths` are a…" | pre-release | flows |  |
| 25 | "An ACL — or bwrap where it exists…" | pre-release | flows |  |
| 26 | "On Linux, bwrap (`security.modes.confinement`) is the better tool…" | pre-release | flows |  |
| 27 | "ACLs matter where confinement is set to `off`,…" | pre-release | flows |  |
| 28 | "The Pi profile already lists `/etc/shadow` as a…" | pre-release | flows |  |
| 29 | "Set the workdir ACL at the same moment…" | pre-release | flows |  |
| 30 | "**The HMAC check.** An ACL doesn't decide who…" | pre-release | flows |  |
| 31 | "Signatures do." | pre-release | flows |  |
| 32 | "**`key_policies.allowed_files`.** That's a string check before a file…" | pre-release | flows |  |
| 33 | "The kernel never sees it." | pre-release | flows |  |
| 34 | "Keep it — and don't pretend it's a…" | pre-release | flows |  |
| 35 | "**`reply_to`, the Oracle, or the wire format.** No…" | pre-release | flows |  |
| 36 | "Result routing is not a filesystem question." | pre-release | flows |  |
| 37 | "Basic technologies a project like this is expected…" | pre-release | flows |  |
| 38 | "Items marked absent are listed in docs/FUTURE.md." | pre-release | flows |  |
| 39 | "**Runner code integrity.** Nothing verifies `runner.py` hasn't been…" | pre-release | flows |  |
| 40 | "A same-user job can patch the runner and…" | pre-release | flows |  |
| 41 | "No hash check at startup, no read-only install…" | pre-release | flows |  |
| 42 | "Status: absent." | pre-release | flows |  |
| 43 | "**Network egress control.** The canonical agent attack is…" | pre-release | flows |  |
| 44 | "Only bwrap in enforce mode (Linux, the default)…" | pre-release | flows |  |
| 45 | "Status: mechanism exists, on by default where bwrap…" | pre-release | flows |  |
| 46 | "**Audit log integrity.** Neither log is append-only in…" | pre-release | flows |  |
| 47 | "The watched principal can edit or truncate either." | pre-release | flows |  |
| 48 | "No append-only flag (`chattr +a`), no hash chain,…" | pre-release | flows |  |
| 49 | "Status: absent." | pre-release | flows |  |
| 50 | "**Supply chain.** Releases ship `SHA384SUMS`, but nothing in…" | pre-release | flows |  |
| 51 | "PyPI trusted publishing is the one solid link." | pre-release | flows |  |
| 52 | "Status: partial." | pre-release | flows |  |
| 53 | "**Secret revocation.** "The shared secret is root" is…" | pre-release | flows |  |
| 54 | "Status: documented." | pre-release | flows |  |
| 55 | "**Windows default privilege.** The out-of-box Scheduled Task runs…" | pre-release | flows |  |
| 56 | "`--run-as` exists, but the default is the highest-privilege…" | pre-release | flows |  |
| 57 | "Status: documented in `docs/security/hardening/windows.md`, default unchanged by owner…" | pre-release | flows |  |
| 58 | "**`reply_to` (v3.7.0).** The runner now emails results to…" | pre-release | flows |  |
| 59 | "The signed-body-only rule keeps it sound, but it…" | pre-release | flows |  |
| 60 | "Status: shipped, documented in `PROTOCOL.md`." | pre-release | flows |  |
| 61 | "The near-zero default posture is the owner's call,…" | pre-release | flows |  |
| 62 | "Most of the hardening controls are opt-in for…" | pre-release | flows |  |
| 63 | "The exceptions: M1 is two always-on defect fixes…" | pre-release | flows |  |
| 64 | "What *was* an oversight is that the docs…" | pre-release | flows |  |
| 65 | "That's what this file is." | pre-release | flows |  |
