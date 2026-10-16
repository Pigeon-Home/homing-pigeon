# Security gaps: what the defaults don't cover

This is the honest accounting. The project's threat model
(`docs/threat-model.md`) says: the shared secret is root, and every
job should be treated as potentially destructive. This document says
what the *default* installation actually protects against — and what
it doesn't — plus the order in which to turn things on if the answer
bothers you.

## The one sentence

With default settings, **the job is the runner**: jobs execute as the
same OS user that owns `config.json`, the code, the state, and the
audit log. Every file permission on the box is theater against the
job itself, because the job can read and rewrite all of it. The
restrictions are deliberately near zero out of the box (the owner's
explicit posture choice). Everything below follows from that.

## The order

Protections compose in one order. Each step is useless without the
ones before it.

**1. Split the identities.** The job must run as a different
principal from the runner. That's `security.modes.job_user`
(`enforce`) on POSIX — the runner keeps its user, the job drops to
`job_user`. On Windows that's `install.exe --run-as` with a limited
account instead of the default SYSTEM. Until this is done, steps 2
and 3 do nothing: an ACL that hides `config.json` from the job also
hides it from the runner when they're the same user.

**2. ACL the secrets away from the job.** Once the principals are
split: `config.json`, the secret file, the OAuth token, `seen.json`,
`board.json`, `security-audit.jsonl`, and `retained/` should be
readable by the runner principal and not by the job principal.

| Platform | What exists | The gap |
|---|---|---|
| Linux | `job_user` (setuid), `install.py` writes owner-only `0600` | Default is still the same user. POSIX ACLs (`setfacl`) on the base dir should hide the secret from the job user when bwrap is off |
| macOS | launchd agent as the installing user | `chmod +a` ACLs exist but nothing applies them; the real cage would be `sandbox-exec`, not an ACL |
| FreeBSD | cron `@reboot` as the user | `setfacl` on ZFS/UFS unapplied; a jail is the real boundary |
| Windows | Scheduled Task (SYSTEM by default, or `--run-as`); `hardening/windows.md` documents the account as the sandbox | `install.py` only chmods, which sets no real DACL on Windows — the `icacls /inheritance:r` recipe is advice in a doc, not code that runs at install. Low integrity or a restricted token is the stronger cousin |

`--posture` already warns about the Windows ACL; it should warn
about a missing POSIX ACL too.

**3. Cage the workspace.** `workspace_root` and `protected_paths`
are a snapshot today: the Oracle *notices* a write outside the
workspace after the fact. An ACL — or bwrap where it exists — makes
the write *fail*. On Linux, bwrap (`security.modes.confinement`) is
the better tool and should stay the confinement backend. ACLs matter
for the default (confinement off) and for macOS, FreeBSD, and
Windows, where bwrap doesn't exist. The Pi profile already lists
`/etc/shadow` as a protected path; that path should be *denied* to
the job user, not only watched.

Set the workdir ACL at the same moment the runner chowns the workdir
for `job_user` (in `_job_user_preexec`), never from anything in the
signed job: **a job field that names an ACL is the same hole as a
job field that turns the judge off.**

### What should not grow an ACL

- **The HMAC check.** An ACL doesn't decide who may send a job.
  Signatures do.
- **`key_policies.allowed_files`.** That's a string check before a
  file is staged. The kernel never sees it. Keep it — and don't
  pretend it's a DACL.
- **`reply_to`, the Oracle, or the wire format.** No new message
  field. Result routing is not a filesystem question.

## The rest of the inventory

Basic technologies a project like this is expected to have, and
where each one stands:

- **Runner code integrity.** Nothing verifies `runner.py` hasn't
  been modified on disk. A same-user job can patch the runner and own
  every future run. No hash check at startup, no read-only install
  dir. Status: absent.
- **Network egress control.** The canonical agent attack is
  exfiltration — the job `curl`s secrets straight out, bypassing
  every redaction rule (those only cover what comes *back* in the
  result email). Only bwrap in enforce mode (Linux, off by default)
  blocks it. Status: mechanism exists, default-off.
- **Audit log integrity.** `security-events.jsonl` is append-only by
  convention. The watched principal can edit or truncate it. No
  append-only flag (`chattr +a`), no hash chain, no remote copy.
  Status: absent.
- **Supply chain.** Releases ship `SHA384SUMS`, but nothing in the
  install path verifies them; the installer itself runs `curl | sh`
  for Ollama. PyPI trusted publishing is the one solid link.
  Status: partial.
- **Secret revocation.** "The shared secret is root" is documented,
  but there is no written fire drill: rotate the shared secret first
  (setup wizard or `--shared-secret`), then the mailbox credential,
  then assume every job signed with the old secret is suspect and
  re-verify the seen-set. Status: undocumented until this paragraph.
- **Windows default privilege.** The out-of-box Scheduled Task runs
  as SYSTEM. `--run-as` exists, but the default is the
  highest-privilege account on the box and it's quiet about it.
  Status: documented in `hardening/windows.md`, default unchanged by
  owner choice.
- **`reply_to` (v3.7.0).** The runner now emails results to a
  SI-named address. The signed-body-only rule keeps it sound, but it
  is new outbound-mail surface. Status: shipped, documented in
  `PROTOCOL.md`.

## Deliberately not done

The near-zero default posture is the owner's call, not an accident:
this is a personal runner, and availability beats strictness for one
user's box. The hardening controls (M0–M11) are all opt-in for that
reason. What *was* an oversight is that the docs never said, in one
place: here's what the defaults don't protect you from, and here's
the order to turn things on. That's what this file is.
