# Security Policy

Homing Pigeon is, by design, a remote code execution tool: anyone
holding the shared secret gets full control of the machine the runner
runs on. That makes its security posture load-bearing, not decorative.
This document explains how to report problems and what to expect.

## Reporting a vulnerability

**Do not open a public issue for security problems.** Public issues
get scraped, and a disclosed-but-unfixed hole in a tool like this
puts every deployment at risk.

Instead, use GitHub's **private vulnerability reporting**:

1. Go to the repo's **Security** tab.
2. Click **Report a vulnerability**.
3. Describe the issue: what you found, how to reproduce it, and what
   you think the impact is.

If private reporting isn't available to you, open a minimal public
issue that says you've found a security problem and ask for a contact —
no details.

### What happens next

- You'll get an acknowledgment as soon as the report is seen.
- The issue will be assessed for impact and reproducibility.
- A fix will be developed privately, then released with a clear
  description of what was wrong and which versions are affected.
- You'll be credited in the release notes unless you'd rather stay
  anonymous.

## Scope

In scope: the runner (`runner/runner.py`), the installer
(`runner/ops/install.py`), the cloud helper (`runner/cloud/send_job.py`), the
protocol itself (PROTOCOL.md), and the build/release pipeline
(`.github/workflows/`).

Out of scope: the security of the mailbox provider itself, the secrecy of a
shared secret the user chose to share, and deployments that ignore
the documented threat model (e.g., running the agent on a machine
with irreplaceable data and no VM snapshot).

## A note on the threat model

This project is explicit that the runner is a **full-trust execution
environment**. Reports along the lines of "anyone with the secret can
run arbitrary code" describe the intended design, not a vulnerability.
A vulnerability is something that breaks the documented guarantees:
signature forgery, a job executing without a valid
signature, sandbox/workdir escape, or secret leakage through logs,
emails, or error messages. Sender spoofing is not in scope: the sender
address is not validated, so there is nothing to spoof — the signature
is the only thing the runner trusts.

**What the signature proves, and what it does not.** The HMAC signature
answers two questions: was this job sent by someone holding the shared
secret, and has it been tampered with in transit? It does not answer a
third question: is this job safe to execute? A compromised SI, a
prompt-injected SI, or a careless human with the secret can sign a
perfectly valid, perfectly destructive job, and the runner will run it.
Authentication is not authorization to be safe. That is why the
deployment model matters more than the cryptography: throwaway account,
disposable machine, secret kept like a password. The crypto keeps
strangers out. Only your own judgment keeps bad jobs out.

## Spillage: when private material is published

### What spillage is

"Spillage" is the security industry's term for a specific failure:
information ending up somewhere it is not authorized to be. CNSSI
4009 defines spillage as a security incident that results in the
transfer of information onto an information system not authorized
to store or process it. That definition was written for classified
information. This project handles no classified information, and
nothing in this section concerns any government's material — the
shape of the failure is the same at any sensitivity: material under
a handling rule appears outside the boundary the rule sets. NIST
SP 800-53 gives the failure its own control, IR-9 (Information
Spillage Response), because it recurs everywhere, and because an
improvised response to it is reliably worse than a prepared one.

For this software, the boundary is concrete. The work around the
suite keeps two shelves:

- **The public shelf** — this repository (code, documentation,
  commit messages, issues, pull requests, release notes) and
  everything published from it: packages, images, mirrors.
- **The private shelf** — what the public shelf must never carry.
  Credentials and secret values. The material of security-testing
  work done with the suite: what is being examined, engagement and
  case records, unfixed findings in any detail, crash data and
  crash artifacts. And, for an operator who runs the suite for
  clients — a penetration-testing firm is the standing example —
  the clients' information: their systems, their findings, their
  names.

One category stands on the private shelf by name, because it is
the one most often carried across by accident: **agent
permission and configuration files** — an agent's approval
memory, the saved record of commands its operator approved and
need not be asked again (sometimes preserved word for word, with
a credential inside the command), and a deployment's config and
state files. Research published in November 2026 counted over a
thousand public copies of one coding agent's approval file
holding real secrets, most of them committed without their
owners noticing. If such a file crosses, the response below
applies unchanged, and rotation comes first: a credential inside
an approved command is compromised the moment the commit is
pushed, and deleting the file does not reach the copies in
history and forks. The design record for the category is
`docs/steady/security/privacy-design.md`, section 8.

**Spillage is private-shelf material reaching the public shelf:**
committed to this repository in any form — a file, a page, a
commit message, a test fixture, a screenshot, a log excerpt, a
release asset — or published onward from it. The crossing does not
require anyone to intend it. An operator assembling a public change
out of private notes can carry a sentence, a file name, or an
artifact across the boundary without noticing; an agent doing the
same can do it faster and at larger scale. Intent is not part of
the definition. Presence is.

### Why the response matters more than the spill

A spill is an accident. What happens next is a choice, and the
choice is what this section governs.

The instinct on finding private material in a public place is to
delete it quietly and move on. That instinct is the one outcome
this project forbids, for reasons that are practical before they
are ethical:

- **Deletion is not unpublication.** A public repository is
  cloned, forked, mirrored, cached, and indexed. GitHub's guide to
  removing sensitive data from a repository is blunt about it:
  once a commit has been pushed, the data it contains should be
  considered compromised, because copies may survive in clones and
  forks, in cached views reachable by commit hash, and in
  pull-request references — none of which a history rewrite
  reaches. Quiet deletion removes the one copy the deleter
  controls, leaves every other copy live, and manufactures the
  false impression that the exposure has ended.
- **Exposure runs on a clock, and silence wastes it.** A spilled
  credential is dangerous until it is rotated, and rotation can
  begin the minute the spill is declared — or never begin, because
  nobody was told. The same holds for a client whose information
  crossed, and for a vendor whose unfixed finding crossed: each of
  them can act on early notice, and none of them can act on
  silence.
- **Concealment converts an accident into a cover-up.** A spill
  that surfaces later — found by a reader, a client, a program —
  with no record behind it reads as a decision to hide it, and it
  will be judged as one, whatever the intention was. The same
  spill, declared at once and recorded plainly, reads as what it
  is: an error, handled. The record is the difference, and the
  record costs nothing but the willingness to write it.

So the standing rule, which outranks every other step in this
section: **a spill is declared, contained, and recorded — never
concealed.** Removing the material is the first step of the
response. It is never the whole response.

### Preparation: what stands before any spill

Incident response is mostly decided before the incident; NIST
SP 800-61 puts preparation first for exactly that reason. Whoever
operates a deployment of this suite — the person, firm, or system
that runs it and works in its repository — keeps four things in
place:

1. **The shelf rule is written down**, as it is here and, for this
   project's own research work, on the cs_office page
   (`docs/infrastructure-documents/project/cs_office.md`), so that
   "private" names specific categories rather than a feeling. A new
   kind of material gets its shelf decision when it appears, not
   when it leaks.
2. **The alert path is written down**: who is told, by what
   channels, in what order. For this repository the path is: the
   operator on watch alerts the repository's owner immediately,
   directly and by email — out-of-band from the repository itself,
   because an alert posted only where the spill sits can be missed,
   and IR-9 specifies alerting by a method of communication not
   associated with the spill. A firm adopting this section writes
   its own path here; theirs normally runs to the engagement lead
   and, where client material is involved, to the client contact.
3. **Containment is pre-authorized.** The containment steps below
   are pre-authorized in full, executed on detection without
   waiting for anyone's approval. In the first hour of a spill, the owner's
   role is to be told, not to be asked: minutes matter more than
   permission, and a response that waits for a meeting is a
   response that starts after the copies have spread.
4. **The guards run.** Secret scanning and push protection are
   enabled on the repository, and the working rule for every change
   is the shelf rule applied with doubt resolved in one direction:
   a doubtful item stays private. Doubt is settled on the private
   shelf — by the accountable human, if it needs one — never by
   publishing and seeing what happens.

   One of those guards is this project's own. A code name that
   lives only in conversation cannot be scanned for, so protected
   terms — code names among them — are declared in code instead:
   the name guard at `runner/tools/nameguard.py` scans candidate
   public text against a registry of declared terms, under
   matching rules stated in the tool itself (normalization against
   lookalike letters and zero-width characters, word and substring
   rules, case rules). The registry is private-shelf material and
   never enters this repository; the format ships with obviously
   fake example entries (`runner/tools/nameguard-registry.example.json`)
   so any operator can adopt the mechanism, and declare their own
   terms, without anything real crossing the boundary.

### The response

The lifecycle is NIST SP 800-61's — detection and analysis,
containment, eradication and recovery, post-incident activity —
applied to a spill:

**1. Declare.** Whoever detects a spill declares it, on the alert
path, at once — including, especially, whoever caused it.
Self-reporting is the design assumption: a response culture that
punishes the declaration gets silence instead, and silence is the
failure this section exists to prevent. The declaration names the
class of material that crossed (never the material itself), where
it sits (the commit, the file, the issue, the release), and when
it was published. Detection and declaration are a single step:
there is no "clean it up first and mention it after."

**2. Contain.** The material comes off the public shelf
immediately, following GitHub's published procedure for removing
sensitive data from a repository:

- Rewrite the history to purge the material — `git-filter-repo` in
  its sensitive-data-removal mode, or the BFG Repo-Cleaner — and
  force-push the rewritten history.
- Ask GitHub Support, through the support portal, to remove cached
  views and pull-request references and to run garbage collection,
  so the unreachable objects are expunged from GitHub's storage
  rather than merely unlinked.
- Sweep the rest of the publication surface: releases and their
  assets, published packages, container images, and the mirrors the
  project ships to. Anything that carried the material is withdrawn
  or rebuilt from the cleaned history.
- Coordinate the copies that cannot be reached from here. Anyone
  holding a clone of the old history re-clones or rebases — never
  merges — because one merge from a tainted clone reintroduces
  everything the rewrite removed. Forks are their owners' to clean;
  the owners are asked to remove the material or delete the fork.

**3. Assume exposure.** From the moment of publication, the
material is treated as copied — permanently, by parties unknown.
Containment limits further exposure; it does not undo the exposure
that already happened, and the rest of the response is sized by
this assumption rather than by the hope that nobody looked. It is
the same posture this file takes toward a leaked shared secret:
the question is never "did anyone see it," it is "what must change
now that anyone could have."

**4. Eradicate, by the class of what crossed.** Containment
removes the copy; eradication removes the risk the copy created,
and the work differs by class:

- *A credential or secret value* is revoked or rotated at once —
  before the history work, or alongside it, never after it.
  GitHub's guidance is explicit that a revoked secret can no
  longer be used, which may close the exposure on its own. A
  spilled shared secret of this suite is handled as a compromised
  key: marked `compromised` in the key directory, which refuses it
  at every door at once, and rotated under
  `docs/steady/secret-rotation.md`.
- *Security-testing material* — what was being examined, an
  unfixed finding, crash data — is handled as disclosed. Where it
  belongs to an engagement, a bounty program, or a vendor's
  product, the affected client, program, or vendor is notified
  through its formal channel, by the human accountable for the
  work, ahead of any public statement: they hear it from the
  project first. Any plan that depended on the material's secrecy —
  above all, a fix still in progress — is re-planned on the
  assumption that the secrecy is gone.
- *A client's or another person's information* is notified to the
  client or person it belongs to, promptly and plainly: what
  class of material crossed, when, and what has been done. Their
  own duties — to their customers, their regulators — may run from
  the same clock, which is one more reason the declaration never
  waits.

**5. Record the incident, publicly.** The response closes with a
written incident note in this repository: that a spill occurred;
when the material was published and when the spill was declared;
the class of material it carried; and what was done — containment,
rotation, notification — in general terms. The note never
reproduces the spilled material, quotes it, or describes it beyond
its class. It is published once the notifications in step 4 have
been made, and it stays: later readers, clients, and programs are
entitled to find the incident, and to find it handled in the open.
Skipping the note is the concealment this section forbids, however
thorough the cleanup was.

**6. Post-incident: close the mechanism, not just the incident.**
The follow-up review answers one question: by what mechanism did
private material reach a public commit — a file assembled from
private notes, a fixture copied across, a code name resolved in
the wrong place, a screenshot taken on the wrong machine — and
what change makes that mechanism fail loudly next time? The change
lands as engineering, not as intention: a scanning rule, a
pre-push check, a test that fails when the boundary is crossed, a
sharper line in the shelf definition. The review is blameless and
factual, and its conclusions are appended to the incident note. A
spill whose mechanism stays open is an incident scheduled to
repeat.

### A worked example

Hypothetical, and deliberately ordinary, because most spills are.
An operator is writing a public summary of a fuzzing pass and, to
illustrate a sentence, pastes in a minimized crash input taken
from a live engagement. The commit lands. A reader of the
repository now holds a reproducer for an unfixed finding in a
client's product, and enough context to guess whose product it is.

Under this section: the operator notices on a re-read an hour
later — or a reader reports it — and declares it on the alert path
at once, naming the class (crash data, an unfixed finding, client
engagement) and the commit. Containment runs without waiting: the
history is rewritten, the rewritten history is force-pushed,
GitHub Support is asked to clear the cached views, and the release
assets of the affected version are checked and rebuilt. The
client is notified the same day, through the engagement's formal
channel, by the human accountable for the engagement — before the
public incident note, so the client hears it from the firm first.
The note then goes into the repository in general terms: a spill
of crash data occurred, it was public for a stated number of
hours, it has been purged, and it was formally reported to the
affected client. The follow-up finds the mechanism — the public
summary was drafted in the same place as the private case notes —
and closes it: summaries are drafted from public-shelf material
only, and a check now fails any commit that adds a file matching
the case-artifact shapes. The spill was an hour's carelessness.
The response is the part that was rehearsed.

### Adopting this section

This section is this repository's own policy, and it is written to
be adopted. This suite will be operated by people and systems
other than the ones who wrote it — licensed to other testers, run
inside other firms, picked up by whatever system an operator works
with next — and a spill response that lives in one operator's
memory is not a response at all. Adopting it takes three decisions,
recorded where the deployment's own documentation lives: the
categories on the private shelf, the alert path, and the human
accountable for notifications. The steps, the order, and the rule
against concealment do not change. Only the names do.

### Open questions: safeguards are yours to extend

Everything above is this project's floor: the safeguards this
deployment runs, stated so another operator can adopt them as
they stand. It is not a ceiling. The operators of this suite —
testers, firms, and the systems that work for them — are
encouraged, in the strongest terms this page has, to treat the
shelf boundary as a research problem of their own: to implement
safeguards this page does not describe, to test the ones it does,
and to publish the general techniques they find, so the next
operator inherits them. The material a safeguard protects stays
private. The safeguard itself belongs in the open, where it can
be checked.

The questions below are open on purpose. They are the ones this
project has not finished answering for itself, posed so that an
operator — or a system working for one — meets them as work, not
as decoration:

- Can you enumerate your private shelf, exactly? A boundary that
  cannot be listed cannot be scanned for, and a scanner is the
  only guard that reads every commit.
- Which of your code names are declared in code, where a machine
  can enforce them, and which live only in conversation between
  you and your system? The second kind protects nothing, however
  careful the conversation is.
- If a change were assembled from your private notes tonight —
  by a tired person, or by a system working quickly — which of
  your safeguards would stop private material at the boundary:
  a rule, a scan, a test? Or would only care stop it? Care is
  not a control.
- Does your publication surface end at the repository? Packages,
  images, mirrors, release assets, hosted pages: a cleanup plan
  that reaches only the repository reaches only part of a spill.
- What is your shelf's answer for material that is not yours —
  a client's systems, a client's findings, a client's name —
  and on what clock do they hear about a crossing? Their duties
  may start before yours end.
- And the standing one: when your response is written down,
  could a different operator — or a different system — run it
  cold, at 3 in the morning, without asking you anything? If
  not, the response is a memory, not a plan.

An operator who answers these in writing, and builds what the
answers call for, has done more for their material than any
policy they could adopt unchanged — including this one.

References: CNSSI 4009 (the definition of spillage); NIST
SP 800-53 Rev. 5, control IR-9, Information Spillage Response;
NIST SP 800-61, the incident handling lifecycle; GitHub Docs,
"Removing sensitive data from a repository"
(https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

## Dual-use: yes, this looks like email-C2

Saying it plainly: a program that polls an inbox and executes signed
messages is the same *shape* as email-based command-and-control malware.
The difference is not the mechanism — it is consent, control, and
auditability:

- **Consent:** you install it on your own machine, on purpose, to run
  your own jobs. It does nothing you did not ask it to do.
- **Control:** the shared secret is yours, the mailbox is yours, and
  revoking the mailbox credential stops mail delivery — without
  mailbox access the runner can't receive jobs by email. It is not
  the only channel, though: a same-box producer can still deliver
  signed `sensor_alert` envelopes through the local inbox or the
  loopback signal socket, so a leaked signing secret does have a
  delivery channel on the box itself — which is why rotating the
  secret matters more than the mailbox. To rotate a compromised
  secret, generate a new one and update `shared_secret` in config.json
  on the runner (and hand the new string to your SI).
- **Auditability:** the runner is inspectable by design. `--dry-run`
  verifies signatures and prints exactly what a job *would* do without
  executing anything; `--verbose` logs every accept/reject decision;
  `--pdb` drops into the Python debugger on errors. Malware hides.
  This tool is built to be watched.

It belongs to the same family as GitHub self-hosted runners, VS Code
Remote tunnels, and Tailscale: legitimate remote-administration tools
whose power is the point. If your antivirus flags the prebuilt
binaries, that is a known PyInstaller false-positive pattern — verify
the `SHA384SUMS` file attached to the release, or build from source
(`pip install` the wheel, or run `runner/runner.py` directly).

---

## Security controls and key management

Homing Pigeon ships with optional security controls, on by default.
With no `security` block in `config.json`, every control runs at
`enforce`. A control a config sets runs at the mode it is set to;
the default fills in only what a config leaves unset. Every control
has three modes:

- `enforce` — for the `policy_*` features and `audience`,
  violations are rejected through the existing reject path. For
  `confinement` and `job_user`, enforce changes how the job runs, as
  described under each below. This is the default.
- `audit` — the job proceeds exactly as with `off`, but a line is
  written to `security-audit.jsonl` describing what `enforce` mode
  would have decided.
- `off` — the control does nothing.

```json
"security": {
  "modes": {
    "policy_env": "enforce",
    "policy_files": "enforce",
    "policy_args": "enforce",
    "audience": "enforce",
    "confinement": "enforce",
    "job_user": "enforce"
  },
  "audit_max_lines": 20000
}
```

**Changing a mode requires a restart.** Poll interval, workers,
timeouts, output limits, max job age, the result stash's retention
and resend backoff, and the live keys (`owner_instructions`,
`inference`, `oracle_mode`, `verbose`, `extension_sources`) reload
when `config.json` changes. The `security` block does not.

**A malformed security block stops startup** with an error naming the
key (and, for a mode value and `audit_max_lines`, the bad value). It never silently falls back to `off`.

The audit log lives at `security-audit.jsonl` in the runner base
directory, created `0600` on POSIX, bounded by `audit_max_lines`
(default 20000) with rollover to one `.1` file. A small counter file,
`security-audit-counts.json`, tracks decisions per feature. Audit
entries carry identifiers only — never secret values, script text,
or file contents.

Each audit entry also carries a `seq` number and a `chain` value —
the SHA-256 of the previous entry's chain value and the entry's
canonical JSON — forming a tamper-evident hash chain that carries
across the rollover; the counts file records the chain head, so
tail truncation is detected too. `--audit-verify` walks the chain
and reports the first break (exit 1), or states honestly what it
could not cover: entries written before chaining existed form an
unchained legacy prefix and are reported as such.

### What a wide-open box looks like

A test box ran as root with confinement and every security
mode off, at `max_result_view: full`
([live-examples.md](docs/steady/use/live-examples.md)). Three things from
its 19,227 jobs are worth knowing before loosening a real box:

- At view `full` the SI receives what the script printed. The run's
  `flagread` job printed a planted fake credential file;
  `runner.log` redacted the key, the result carried it verbatim.
  The installer's profiles set the ceiling to `attested` for that
  reason; the bare config default is `full`.
- A job running as root read `/etc/shadow` and returned it. Only
  confinement and `job_user` stop that; a signature does not.
- `--posture` warns when `audience` or a `policy_*` mode is off and
  when bwrap is missing. It does not flag running as root,
  confinement or `job_user` off, or `max_result_view: full`; those
  are on the operator to read in the config. `--audit-report` shows
  no entry from the six security features while they are off, since
  no decision was made to record; remediation (on by default in
  deterministic mode) still writes its own entries there.

### Features

| Feature | Milestone | What it does |
|---|---|---|
| `policy_env` | M2 | Constrains env vars for keys with a policy entry |
| `policy_files` | M2 | Constrains staged files for keys with a policy entry |
| `policy_args` | M2 | Constrains job args for keys with a policy entry |
| `audience` | M5 | Binds signed jobs to this runner's id |
| `confinement` | M6 | Runs jobs inside the platform's confinement backend: a bwrap sandbox on Linux, a Job Object with a restricted token at low integrity on Windows, a jail with no network on FreeBSD |
| `job_user` | M8 | Runs jobs as a different user (a POSIX setuid demote; on Windows, a Job Object memory ceiling instead) |

### Confinement

With `security.modes.confinement: enforce` on Linux and `bwrap`
installed, each `exec` job runs inside a bubblewrap sandbox: `/usr`
read-only, no network, no access to home, and the job workdir
writable (mounted at `/work`), plus a writable tmpfs at `/tmp`,
`/proc` and `/dev`. When the job's interpreter lives outside `/usr`
(pyenv, a venv, `/opt`), its install folder is bound read-only too,
and that is logged and recorded in the audit entry. `PATH` inside is
`/usr/bin:/bin`.
The job's scrubbed env arrives via
`--setenv`. At startup under `enforce` the runner starts bwrap once
with the built-in namespace flags, and again with the configured
`extra_flags` added in the position a job's argv gives them; when
either start cannot (bwrap missing, a kernel that blocks
the user namespace, such as
`kernel.apparmor_restrict_unprivileged_userns=1` on Ubuntu 24.04,
or a configured flag bwrap rejects)
the runner refuses to start and names the cause — a security mode
whose mechanism cannot engage is a config error, not a silent
downgrade (`docs/steady/present-but-invalid-config.md`). Extra
binds are not part of the trial: they name operator paths and are
applied per job. If bwrap
leaves `PATH` after a successful start, or the sandbox command
cannot be built, the fallback is recorded and the job is refused:
the runner warns, audits a `fallback` decision, and does not run
the job at all -- under `enforce` a job never runs unsandboxed.
If bwrap is still present
but fails to start, the job fails. Each sandboxed job is audited as
`sandboxed`. `audit` mode runs normally and records a `would_sandbox`
decision (reason `would_run_sandboxed`), with or without bwrap.

Optional tuning under `security.confinement` (all optional):

```json
"confinement": {
  "extra_flags": ["--unshare-pid"],
  "extra_ro_binds": [["/opt/data", "/data"]],
  "work_mount": "/work"
}
```

On Windows and FreeBSD the same mode engages the platform
backend instead, and the startup gate probes that backend the
same way. On Windows: a Job Object (512 MiB per process), a
restricted token and a low integrity level, audited as
`windows: job_object + restricted_token + low_integrity` —
no filesystem namespace isolation, so a confined job can
still read any path its token can read. On FreeBSD: a
per-job jail with the host's system directories mounted
read-only, the work directory the only writable mount, a
fresh `/tmp`, no network at all, and a 512 MiB per-process
ceiling applied at spawn, audited as
`freebsd: jail + no_network + spawn_resource_limits`. A
platform with no backend (macOS today) refuses to start at
`enforce`. The platform pages are
`docs/steady/security/windows.md` and
`docs/steady/security/freebsd.md`; the guarantee each
platform carries stands in `docs/support-matrix.md`.

### Running jobs as another user

With `security.modes.job_user: enforce` and
`security.job_user: {"user": "pigeon-jobs"}`, each `exec` job runs as
that POSIX user (via setuid after fork). The job's workdir is chown'd
to the user, and the parent chain up to the base dir gets traverse-only
(`+x`) permission so the job can reach its workdir without listing the
runner's state. The demote needs the runner itself to run as root,
and the configured user to be resolvable: under `enforce`, startup
refuses when either fails, rather than starting and running jobs
as the runner's own account. A user that exists at startup and is
removed later, or a workdir that cannot be chown'd, is met at job
time instead: the runner warns loudly, audits a `fallback`
decision, and refuses that job -- under `enforce` a job never
runs as the current user in place of the demote. Each job run as
the configured user is audited as `run_as`. `audit` mode runs
normally and records a `would_run_as` decision (reason
`would_run_as_user`).
The user must exist, or startup fails.

## Secrets, keys, and emergency stop

### Secret files

Secrets don't have to live in `config.json`. `shared_secret_file`
and `additional_secrets_files` (`{"key_id": "/path/to/file"}`) read
each secret from a file at startup (whitespace-stripped). A secret
given both inline and via file is a startup error, as is a missing or
empty file. File secrets pass the same entropy gate.

### Multiple secrets and message verification

`additional_secrets` maps key IDs to further shared secrets
(PROTOCOL.md section 14). Threat notes:

- **A key ID is a label, not a secret.** It travels in the clear
  inside the signed body and may appear in logs. Possession of the
  secret it names is the credential; guessing the label buys nothing.
- **Every secret is root unless its policy says otherwise.** Keys
  without a `key_policies` entry are unrestricted by default. Give
  every delegated key an entry (`allowed_kinds`, `allowed_recipes`,
  `max_timeout_sec`, `allowed_script_sha384`, ...), or set
  `key_policies_default_deny`
  so a new key with no entry is refused.
- **Unknown key IDs are rejected before any MAC is computed**, and
  the runner never falls back to the default secret for them. An
  attacker cannot make a message verify under a key it did not name.
- **Finding the signed object costs one pass over the body.** Before
  29-OCT the search for the `{` that opens the signed object walked
  the brace walk once per brace, quadratic in a nest, so an
  unauthenticated sender could post a `max_job_bytes` body of braces
  and hold the mail loop for a day before any MAC ran; fuzzing
  found it as a latency outlier. The search is one
  backward pass now, in the runner and in the sender's verifier
  alike, with the same answers; a 4 MB nest extracts in under a
  second.
- **Rotation is per key**: add the new ID, hand it out, retire the
  old one (`docs/steady/secret-rotation.md`). An inline secret is read at
  startup and rotating it takes a restart; a secret given by file is
  read again on every poll cycle.
- **The key directory names the state of every key** (PROTOCOL.md
  section 14.4; `key_directory` or `key_directory_file`): `in_use`
  verifies, `superseded` verifies until its `not_after`, every other
  state is refused, `compromised` at once, and a key with no entry is
  refused. The verdict comes before the key's policy at the job's
  door, the query, board, version 2 and cancel doors and the DTLS
  handshake, and is read on every check, so marking a leaked key
  `compromised` stops it everywhere without a restart. The hosted
  queue's Worker reads its tenant record, not this file.
- **The dispatcher's trust model** (section 13): a result from a
  worker is bound to that worker's key by the signature, and the
  attestation binds the worker to its claimed output. Neither says
  the output is correct; review (`require_review`, the human gate)
  is the correctness anchor.

### The panic word

The worst case in this file is the shared secret in the wrong hands.
Revoking the mailbox and rotating the key both need a laptop and
time. The panic word is the stop that needs neither: the installer
prints six words once, and a message to the runner's mailbox with the
subject `[HOMING-PIGEON] panic <the six words>` stops the box. It is
checked before any signature work and needs no secret, so it works
from a phone, and holding the secret does not let anyone answer it or
undo it: only `install.py --rearm`, run on the box, releases a stopped
runner (PROTOCOL.md section 14.3).

What it does not do, stated plainly: if jobs run as the runner's own
user, a holder of the secret can send a job that deletes the word's
file or patches the check before the owner ever sends the word. The
word is real protection only where jobs cannot write to the runner's
state or code, which today means `security.job_user` in `enforce`
(above) on a POSIX box, or `security.confinement` in `enforce` on
Linux or FreeBSD, whose backends give a job no write to them.
`install.py --check` prints which case a
box is in. Keep the word off the machine it protects.

### Key names are public

Every secret has a name, its fingerprint `k-<8 hex>` (PROTOCOL.md
section 14.2), and the names travel in the open: a result names the
key that verified its job, the pong's platform card lists the names a
runner accepts (unless `pong_platform` is `none`), the installer prints the name beside the secret, and
the reference sender writes the name into every message unless
`--key-id ""` is given. The
questions a reviewer asks about that, and the answers:

- **Is the name a secret?** No. It is a label, like a user name; the
  secret is the credential. A name tells an attacker which key to
  try -- which the empty key id of the default key told them before
  there were names.
- **Does the fingerprint leak the secret?** No. It is eight hex
  digits (32 bits) of SHA-384 over a fixed label and a 256-bit random
  secret: one-way, and too short to constrain the secret (224 bits
  stay free). As an oracle for a guessed secret it adds nothing a
  signed message does not give already, since every HMAC is a full
  oracle for a guess, and the secret's entropy is what defeats both.
- **Can the name be confused with a signature or a key?** No. The
  label (`homing-pigeon key id v1\n`) separates this hash from the
  HMAC over a body and from the HKDF that derives a job key; nothing
  the secret keys starts from the same input.
- **Can a name change what a key may do?** No. The runner reads a
  key by its value: the default key's empty key id, its fingerprint
  and any name `install --key-id` stored the same secret under are
  one key to every rule -- its policy entry, `key_policies_default_
  deny`, the hourly query window, `v2_answerers`, a sense's `key_id`
  binding. Naming the owner's key by fingerprint grants nothing and
  escapes nothing, and a `key_policies` entry under two names of one
  key is refused at startup.
- **What does a runner publish about its keys?** Names, never values:
  `key_ids` in the pong card, `key_id` in a result, the key ids in
  the doctor's line. The card with `key_ids` leaves only in a ping's
  result, which answers a verified job, so an unauthenticated sender
  sees none of it. The DTLS binding's greeting carries a card without
  key names, and only after the PSK handshake has authenticated the
  peer.
- **Where does the sender keep the pair?** `send_job.py keyring`
  (`~/.homing-pigeon/keyring.json`, mode 0600 in a 0700 directory,
  or `HP_KEYRING`), written whole or not at all; `list` prints names
  and runners, never a secret.

See the hardening report (`docs/steady/security/hardening_report.md`) for per-milestone
status, and the threat model (`docs/infrastructure-documents/security/threat-model.md`) for the
overall posture: the Oracle reviews while the operating system
contains.
