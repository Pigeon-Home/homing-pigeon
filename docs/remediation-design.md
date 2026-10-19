# Remediation: when a job goes bad mid-run

Status: design, recorded 2026-10-18. Not yet built. The detection
halves exist today — the senses, `resource-sentinel`, the
script-path findings, the wake gate. The opinion system
(`docs/oracle-opinion-design.md`, built) records what the Oracle
believed a job would do before it ran. What does not exist is the
act: stopping a job that is going bad *while it runs*, and doing
something about what it touched. This document is the shape of
that act, so the build is a transcription, not an invention.

## The trigger is a divergence, not a vibe

Every job that runs under an opinion carries an intent envelope:
the tier-1 expectations (interpreter, script shape, tools, paths)
and, when a model formed one, its note. Remediation watches the
running job against that envelope. A job doing what its envelope
said — even something destructive the sender openly declared —
is the owner's business, already judged at intake. A job doing
what its envelope did *not* say is the remediation case:

- it reaches for a credential store, home file, or `/etc` path
  the envelope never named (the `_script_path_findings` tells,
  evaluated against the live process, not just the script text);
- its resource shape turns adversary-shaped mid-run
  (`resource-sentinel`'s sustained saturation, fill velocity,
  process storm, keyed to the job's window);
- it escapes or strains its confinement (a cage event is a
  divergence by definition);
- a sense fires *about this job's process tree* while it runs.

Expectation-versus-outcome is a real field of study; here it is
also simply the only honest trigger available. The system does
not need to know what malice looks like in general. It needs to
know what *this job promised*, and notice the difference.

## Authority: reflexes below, judgment above

Two layers may pull the trigger, and the mode knob decides which
are armed (`remediation_mode`):

- **Deterministic tripwires** — a short, enumerated list of
  divergences that kill on sight: confinement escape, a
  credential-store read by a job whose envelope declared no such
  path, a fork storm past the hard ceiling. These are the
  owner's pre-authorized reflexes; no model is consulted, and
  the list is closed — a new tripwire is a code change with a
  test, never a config accident.
- **The Oracle's judgment** — when inference is configured, the
  Oracle may order a kill for a divergence that is real but not
  on the tripwire list. It sees the envelope, the observed
  behavior, and the box's context (its full charter), and its
  order is recorded *as its judgment*: the result and the audit
  log carry the divergence, the reasoning it gave, and the act
  taken, signed the way its other statements are signed. On a
  box without inference (Pi Light), this layer is simply absent
  and the reflexes still stand.

Default: `remediation_mode` follows the box — `oracle` where
inference is configured, `deterministic` where it is not,
`off` available to any owner who wants the pager back instead.
The DRI playbook's founding line ("it pages, never remediates;
the human decides") survives as the `off` posture and as the
escalation path: remediation *acts first and pages after* —
the page carries the whole story, not a request for permission
that arrives too late to matter.

## The acts, in escalating order

1. **Kill the tree.** The job's whole process tree, not just
   the interpreter — a divergence that survives its parent is
   not remediated.
2. **Quarantine the outputs.** The job's work directory and any
   artifact it produced are moved to a quarantine area, marked
   with the job id and the divergence, and held for the owner.
   Nothing is deleted by the system. The owner releases or
   destroys; a `remediation release` path makes the release one
   deliberate act, recorded like the seizure.
3. **Refer the file to the box's antivirus.** The Oracle's
   coolest power is not the kill — it is the referral. When a
   file is judged malicious, the system asks the platform
   antivirus for *its* verdict on that exact file: on Windows,
   a Defender custom scan of the path (`MpCmdRun -Scan
   -ScanType 3 -File`); where ClamAV is installed, `clamdscan`
   on the same path. Consumer antivirus accepts a scan request,
   not a declaration — the referral does not tell the AV what
   to conclude. But an AV that confirms takes ownership with
   machinery the runner should not imitate: OS-level
   quarantine, re-execution blocks, and a detection that
   outlives the job. On managed boxes the enterprise form of
   the same idea exists (Defender for Endpoint file indicators:
   block-and-remediate by hash), and the record shape below
   already carries what an indicator needs. The AV's verdict —
   confirmed, clean, or unavailable — is recorded beside the
   Oracle's judgment, attributed to each: two witnesses, neither
   borrowing the other's authority.
4. **Page the owner.** Through the DRI channel, with the
   intent envelope, the observed divergence, the act taken,
   and the AV verdict when one came back.

Every act lands in the job's result as a `remediation` member
(mode, divergence, act, av_verdict, received_digest of the job
as dispatched) and in the audit log, whether or not the sender
ever reads it. A remediation the owner cannot reconstruct from
the record did not happen, whatever the process table says.

## Restraints

- Remediation never expands to the box at large: the kill is
  the job's tree, the quarantine is the job's outputs, the
  referral is the job's files. A divergence is about a job.
- A killed job's result is a failure with the remediation
  member attached — the sender learns their job was stopped
  and why, in the signed result, like any other outcome.
- The tripwire list and the mode are owner configuration,
  changeable like any other knob; a sender cannot request,
  widen, or narrow remediation in a job. It is not latitude.
- False kills are the failure that makes owners turn systems
  off, so the bar is divergence from a *recorded* envelope —
  never a resemblance to somebody else's bad job.
