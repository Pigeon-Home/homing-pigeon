# Remediation: when a job goes bad mid-run

Status: design, recorded 2026-10-18, expanded the same evening
at the owner's direction to incorporate the full discussion.
Not yet built. This document is the design of record: when the
build happens, it is a transcription of this text, and any
place the code must depart from it is a delta written here
first, in the open.

## Why this exists

The project can already refuse a job before it runs (the
judge), predict how it will go (the Oracle's opinion,
`docs/oracle-opinion-design.md`), and report what it did
afterwards (the retained record, the audit log). What it
cannot do is act *while* a job runs. If the agent determines
that something from a job is going bad — not failed, not
finished, *going* bad — nothing stops it and nothing cleans
up after it. The DRI playbook pages the owner, and its
founding line is explicit: it pages, never remediates; the
human decides. That was the right doctrine when the system
could only watch. The owner has since directed otherwise:
the system should be able to stop a job that is going bad
and remediate — as an option, implemented as a core feature.
This document gets that design right before it is code.

Three different "fix" stories live in this project and are
not interchangeable:

- **The judge** gates *entry*: a job that should never run
  does not run.
- **Opinion repair** fixes the *job*: a job that would run
  wrong in this environment is corrected before it runs, and
  re-judged as corrected.
- **Remediation** stops a *running* job whose observed
  behavior diverges from what it was expected to do, and
  deals with what it touched.

## The trigger is a divergence, not a vibe

Every job that runs under an opinion carries an intent
envelope: the deterministic tier-1 expectations (interpreter,
script shape, named tools, referenced paths) and, when a
model formed one, its labeled note. That envelope is the
record of *what the inference system believed was going to
happen*. Remediation watches the running job against it.
A job doing what its envelope said — even something
destructive the sender openly declared — is the owner's
business, already judged at intake. A job doing what its
envelope did not say is the remediation case. Expectation
versus outcome is a genuine field of research; here it is
also simply the only honest trigger available. The system
never has to know what malice looks like in general. It has
to know what *this job promised*, and notice the difference.

Concretely, the divergences the design recognizes today:

- **Undeclared reach.** The running job touches a credential
  store, a home file, an `/etc` path, or an outside-workspace
  path its envelope never named — the `_script_path_findings`
  tells, evaluated against the live job and the artifacts it
  produces, not only against the script text at intake.
- **Adversary-shaped resources.** The job's window fills with
  the signals `resource-sentinel` exists to file: sustained
  CPU saturation, disk-fill velocity, process storm,
  collapsing memory — keyed to this job's process tree and
  time window, not the box in general.
- **Confinement events.** A job straining or escaping its
  cage is a divergence by definition; the cage's report is
  the evidence.
- **A sense fires about this job.** Any sense — built-in or
  an owner's extension — files an alert that names this
  job's process tree, its work directory, or its window.
  Detection may come from anywhere (see Placement).

A divergence is evidence, not yet a verdict. What happens
next depends on which authority is armed.

## Authority: reflexes below, judgment above

The owner was asked to choose between deterministic rules
and the Oracle's judgment, and declined to choose: both are
great options, and the build should select the best *given
that the system has inference*. The selection this design
records:

- **Deterministic tripwires** — a short, enumerated list of
  divergences that kill on sight: a confinement escape; a
  credential-store read by a job whose envelope declared no
  such path; a process storm past the hard ceiling. These
  are the owner's pre-authorized reflexes. No model is
  consulted, the list is closed, and a new tripwire enters
  it only as a code change with a test — never as a config
  accident or a model's suggestion.
- **The Oracle's judgment** — where inference is configured,
  the Oracle may order a kill for a divergence that is real
  but not on the tripwire list. It judges with its full
  charter context: the envelope, the observed behavior, the
  box's state, the job's history as `job-watcher` knows it.
  Its order is recorded *as its judgment* — the divergence,
  the reasoning it gave, and the act taken ride the result
  and the audit log, attributed to the Oracle the way its
  opinions are. On a box without inference (Pi Light), this
  layer is absent by construction and the reflexes stand
  alone: the deterministic Oracle has no judgment to lend,
  and this design does not pretend otherwise.

The option surface is one key, `remediation_mode`
(`off | deterministic | oracle`), with a matching
`--remediation-mode` flag for one process. **Default:
`deterministic`** — the reflexes are armed out of the box;
the Oracle's layer is armed by the owner's deliberate act
of choosing `oracle`, because a model ordering a kill is
the one power in this design an owner should switch on
knowingly. `off` restores the original doctrine in full:
the system watches, records, and pages; the human decides.

## The acts, in escalating order

1. **Kill the tree.** The job's whole process tree, not
   merely the interpreter that was dispatched. A divergence
   that survives its parent is not remediated. The result
   records the job as failed-by-remediation, distinctly from
   an ordinary failure and from a timeout kill.
2. **Quarantine the outputs.** The job's work directory and
   every artifact it produced move to a quarantine area,
   marked with the job id, the divergence, and the authority
   that acted. Nothing is deleted by the system, ever. The
   owner's release path (`--remediation-release <job_id>`,
   plus the matching Oracle door) is one deliberate act,
   recorded like the seizure. Quarantine is also where a
   merely-failed job's outputs are *not*: failure alone is
   not a divergence and quarantines nothing.
3. **Refer the file to the box's antivirus.** A conventional
   antivirus, left to itself, tries to kill the process —
   it is a remediation actor with exactly one move and no
   knowledge of the job system. The Oracle knows things the
   AV does not: which job, whose envelope, what divergence.
   So when a file is judged malicious, the system refers
   that process and its associated file to the antivirus
   *as a suspect*, and asks for the AV's own verdict on that
   exact path: on Windows, a Defender custom scan
   (`MpCmdRun -Scan -ScanType 3 -File <path>`); where ClamAV
   is installed, `clamdscan` on the same path. A consumer
   antivirus accepts a scan request, not a declaration —
   the referral asks; it does not instruct. But an AV that
   confirms takes ownership with machinery this runner
   should not imitate: OS-level quarantine, re-execution
   blocks, a detection that outlives the job's account of
   itself. The enterprise form of the same idea (Defender
   for Endpoint file indicators — block and remediate by
   hash) is recorded as the managed-box variant; the record
   shape below already carries what an indicator needs. The
   AV's verdict — `confirmed`, `clean`, or `unavailable` —
   is recorded beside the Oracle's judgment, attributed to
   each: two witnesses, neither borrowing the other's
   authority, and an owner's box with no AV loses nothing
   but the second witness (`unavailable` is a fact in the
   record, not an error).
4. **Page the owner.** Through the DRI channel, carrying
   the whole story: the intent envelope, the observed
   divergence, the authority that acted, the acts taken,
   and the AV verdict when one has come back. Remediation
   acts first and pages after — the page is a report, not a
   request for permission that would arrive too late to
   matter. In `off` mode the same page is all that happens,
   which is the playbook's original shape preserved as a
   setting rather than as a limit.

## The record

Every act lands twice. In the job's result, as a
`remediation` member (additive, OPTIONAL, in the §3.2
result): `{mode, authority: tripwire | oracle, divergence,
act: killed | quarantined | referred, av_verdict,
received_digest}` — the sender learns their job was stopped
and why, in the signed result, like any other outcome. And
in the audit log, as the operator's copy, with the quarantine
path and the referral detail. A remediation the owner cannot
reconstruct from the record did not happen, whatever the
process table said at the time. The quarantine area is
bounded like the other state (a count and a size ceiling in
config, oldest released-to-archive first — archiving moves,
never deletes).

## Placement: core feature, extension-fed

The owner asked whether remediation is an extension or a
core feature; it might not have to be an extension, and
maybe an extension is the right place. The design's answer
is both, split at the only seam that matters — **who can
act**:

- **The acts are core.** Only the runner holds the process
  tree, the confinement, the work directory, and the result
  channel. An extension *cannot* kill a job, and must not:
  extensions are untrusted producers whose entire contract
  is filing signed alerts; the agent never imports their
  code, and that invariant is load-bearing for the whole
  senses design. A kill switch reachable from extension
  code would be a privilege escalation with a manifest.
- **The detection is extension-shaped.** A sense that
  notices a divergence files it like any other alert;
  `resource-sentinel`, the senses, and any owner-planted
  extension are all legitimate witnesses, fused by the same
  correlation the wake gate already performs. An owner who
  writes a sense that watches *their* workload's idea of
  "going bad" has, without knowing it, written a remediation
  detector. That is the ecosystem working as designed.

## Restraints

- **Scope is the job.** The kill is the job's tree, the
  quarantine is the job's outputs, the referral is the
  job's files. Remediation never widens to the box, the
  sender's other jobs, or the sender's key — a key-level
  consequence belongs to the key policy the owner sets,
  not to a mid-run judgment.
- **No sender surface.** A job cannot request, widen,
  narrow, or appeal remediation. It is not latitude; it is
  not in the envelope's gift. The `oracle_opinion` member a
  sender sets has no remediation meaning.
- **False kills are the existential failure.** A system
  that kills good jobs gets switched off, and an `off`
  remediation system detects nothing. Hence the trigger
  discipline: divergence from a *recorded* envelope, never
  a resemblance to somebody else's bad job; the tripwire
  list closed and tiny; the Oracle's layer opt-in; and
  every act reversible by the owner (release the
  quarantine, read the record, judge the judge).
- **The model is never the only witness for a tripwire.**
  Tripwires are deterministic by construction; the Oracle's
  layer exists precisely for the cases that are not, and
  its orders are labeled as judgment wherever they land.

## Open items the build must close in code

- The observation loop: how the running job's tree is
  sampled (cadence against `poll_interval_sec`, per-job
  cost on a loaded box) and how sense alerts are correlated
  to a job's window without a shared clock assumption
  beyond the box's own.
- The Defender path: locating `MpCmdRun.exe` across
  Defender install layouts, and its exit-code/verdict
  mapping, verified on a real Windows box — the VM that
  writes this design cannot sign that page.
- Whether the Oracle's judgment call is synchronous (ask
  at divergence time, bounded by a short timeout, act on
  timeout as `deterministic` would) — the design's
  inclination, recorded here so the build argues with it
  explicitly if it argues at all.
