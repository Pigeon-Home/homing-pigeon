# Privacy design: declared configuration, in the security-modes family

This document states how privacy is handled in this suite: what
exists, how it is configured, and what is recorded as still to
build. It is written the way the audit handling is written --
the activity is done and documented, in the open, for readers
who look. Two companions stand beside it:
`privacy-fremont-research.md`, an inventory of privacy work in
the Fremont Derby project that this design draws on, and
`privacy-models.md`, a survey of the privacy models an operator
could adopt.

**The operator of this project takes no position among the
models in `privacy-models.md`.** They are documented as open
options. What this design commits to is narrower and mechanical:
privacy behaviour in this suite is *declared configuration*, in
the family of the config security modes, so that an operator's
chosen mentality is expressed by configuration, not by a code
fork. Section 3 shows, for each surveyed model, the
configuration shape that expresses it.

## 1. What exists today

- **The personal-documents warning** (`runner/oracle/personal_docs.py`,
  `personal-documents-warning.md`). At startup and at install, a
  shallow scan of file and folder *names* in the home papers
  folders (Documents, Desktop, Downloads, OneDrive paper
  folders, XDG-relocated folders) prints a fixed banner when a
  name matches legal, tax or medical vocabulary. It never opens
  a file, never keeps a name, never sends anything.
- **The config security modes** (`runner/guard/security.py`).
  Six guard features -- `policy_env`, `policy_files`,
  `policy_args`, `audience`, `confinement`, `job_user` -- each
  set to `off`, `audit` or `enforce` under `security.modes` in
  the config, each defaulting to `enforce`, with audit records
  written to a tamper-evident log. An unknown feature name in
  the config is refused at startup. This family is the pattern
  privacy behaviour follows.
- **The postures** (README, `runner/ops/posture.py`). The named
  owner postures -- *just run it*, *eyes open*, *lockdown* --
  bundle mode settings. Under *just run it* the config defaults
  stand and privacy is not a concern of the run; under the other
  postures it is treated as a major concern. That split is a
  property of the postures, and the privacy features below are
  engaged or quiet exactly as the posture's configuration says.
- **The disclosure postures** (`runner/tools/posture.py`): what
  may be said about a piece of work is itself declared in code
  and carried in logs -- the same declared-configuration shape,
  applied to disclosure rather than to data handling.

## 2. The design rule

Privacy behaviour is declared in the same place and the same
shape as the guard features: a named feature under
`security.modes`, one of `off` / `audit` / `enforce`, defaulting
to `enforce`, refused when misspelled, visible in the posture
report. A new privacy behaviour arrives as a new feature in
that family, with its mode semantics stated in its own
document -- never as an environment variable, a command-line
flag of its own, or a code path only one mentality can use.

Mode semantics for an operator-invoked behaviour (the shelter
is the first) follow the family's logic one step removed:
`off` refuses, `audit` shows what would happen and does nothing,
`enforce` permits the operator's explicit action to take effect.
Nothing in this family acts at startup on the operator's files.

## 3. The surveyed models, as configuration

`privacy-models.md` documents 11 models. The table states, for
each, how an operator holding that mentality expresses it with
this suite's configuration. Where a row needs machinery that
does not exist yet, the row says so and section 6 records it as
queued work; the table does not pretend otherwise.

| Model (survey section) | Expressed as |
|---|---|
| Privacy by Design / by-default (1) | The family defaults themselves: every feature defaults to `enforce`; the shipped example config states every mode explicitly. |
| Data minimisation (2) | The personal-documents scan is name-only and keeps nothing; results are size-bounded by config (`max_result_view`); the shelter reduces what a run can meet to what the job needs. |
| Contextual integrity (3) | Per-posture configuration: the same machine runs *just run it* for one context and *lockdown* for another; flows are judged per context by the operator's declared modes, not by a global rule in code. |
| LINDDUN / OPSEC, threat-model-first (4) | `audit` mode across the family: the audit log records what each guard saw and did, in a tamper-evident chain, so the operator's threat model is checked against records rather than intentions. |
| Local-first / data sovereignty (5) | The suite is self-hosted end to end; jobs arrive from a source in the cloud the operator controls; the shelter and the warning both act locally and send nothing. |
| Compartment models (6) | The shelter is the compartment mechanism for personal documents: a marker-verified folder the warning scan treats as out of scope. Disclosure compartments are the disclosure postures. |
| Consent-and-control / privacy as a dial (7) | The modes *are* the dial: per-feature `off` / `audit` / `enforce`, reversible at any time by editing the config; the shelter is the survey's sheltering pattern (its section 7) implemented. |
| Radical transparency (8) | Also a configuration: an operator holding this mentality sets the privacy features `off` and the posture to *just run it*; the suite expresses that choice in the same shape, and the posture report shows it. |
| Dignity/autonomy; IETF positions (9) | No configuration of its own: the design follows RFC 6973's minimisation vocabulary and RFC 7258's stance in the mechanisms themselves (name-only scanning; nothing kept; nothing sent). |
| Obfuscation (10) | Not expressed. The suite does not add noise to an operator's data; recorded here so the absence is a stated fact, not an oversight. |
| Privacy as a collective good (11) | Expressed at the project level rather than per machine: the defaults a new operator inherits are the strict ones, so one operator's choice does not lower the next operator's starting point. |

## 4. The Fremont mechanisms, mapped

Each mechanism or principle from `privacy-fremont-research.md`,
with its disposition here and the reason.

| Fremont item | Disposition | Reason |
|---|---|---|
| Personal-documents sheltering (survey section 7's pattern; Fremont's scrub-on-copy and synthetic-data work are its neighbours) | **Implemented** (section 5) | The settled example for this project: a machine that holds personal documents gets an operator-run shelter, gated by a security mode. |
| Privacy behaviour as declared, default-off configuration (consent tables: absent row = false) | **Adopted as the design rule** (section 2) | This suite's equivalent of "absent = false" is "unset = enforce, misspelled = refused": the declaration is the config, and silence resolves to the strict reading. |
| Mask by default, reveal as a separate explicit action | **Adopted as a rule for new surfaces** | Any future surface that can show a sensitive value ships masked, with reveal a distinct, gated action. The shelter's plan/apply split is this rule in operator-tool form. |
| Split existence from value (`has_phone`; audits record the boolean) | **Adopted; already the house shape** | The warning banner is fixed text that cannot reveal which name matched; audit records name features and outcomes, not file names. The shelter's manifest is the one deliberate exception: it holds paths, lives only inside the shelter folder on the operator's disk, and is never logged or sent. |
| Privacy-safe telemetry (counters only, key denylist, value cap) | **Queued** (section 6) | The suite has no general telemetry surface today; the contract is recorded so the first one is built to it. |
| QA-evidence privacy contract (pseudonymous IDs, redaction, 90-day raw retention) | **Documented; partially standing** | Crash and result records here already carry code names rather than target identities (the disclosure postures). A retention value for raw evidence is an operator decision, recorded as queued. |
| Boundary test: prove a sensitive value appears only in allowlisted files | **Adopted as a testing rule** | The shelter family includes it in miniature: manifest paths are validated to stay inside home and the shelter, and the marker tests prove a lookalike folder does not gain the shelter's exemption. A tree-wide value-confinement test is queued. |
| Fail-closed preflight for copies (gamma refresh) | **Already the house shape** | Decision 1 refuses startup when a wrong config value changes reach, execution or protection; the shelter validates its manifest fail-closed before moving anything. |
| Session isolation (one user's state never surfaces in another's session) | **Documented only** | This suite has no multi-user interactive surface; jobs and results are bound to their job and key by the protocol. The principle is recorded for any future surface. |
| Browser-deny data plane (RLS `using(false)`, service-role RPCs) | **Documented only** | There is no browser data plane here. The structural equivalent -- jobs cannot reach the host except through the runner's checked paths -- already holds. |
| Consent-gated messaging channels; retire a surface rather than consent-manage it | **Documented only** | No social surface exists here. Both halves are recorded: default-off per-channel consent as the shape for any future contact surface, and retirement as a legitimate disposition. |
| Archive instead of delete; soft removal with an audit record | **Already the house shape** | Runs and results are append-recorded; deletion of records with history is not a runner operation. |
| Environment/lane isolation, synthetic identities for test lanes | **Already the house shape** | Test lanes here run synthetic fixtures; the fleet's lanes are separate machines with separate configs. |
| Non-leaky errors, request guards, storage hygiene, OAuth hygiene | **Already the house shape** | The runner's error, envelope and size handling follows the same rules; recorded in the research document for comparison. |

## 5. What was implemented

Three suppositions were written before the implementation, and
the implementation was measured against them:

- **S1.** A marker-verified shelter folder can be taken out of
  the warning scan's scope without weakening the scan: a folder
  with the shelter's name but no marker, or the wrong marker,
  still trips the warning. -- **Held**: tests cover the name-only
  and wrong-marker folders (both still trip) and the real marker
  (out of scope).
- **S2.** A new feature can join the security-modes family
  without changing any existing feature's behaviour: the
  existing families (security config, posture, parity, startup
  gate) stay green unchanged. -- **Held**: those families pass
  unmodified; the one recorded change is the core line measure,
  re-measured and re-recorded in the established way because two
  core files grew.
- **S3.** Sheltering by the warning check's own name scan makes
  the warning quiet afterwards, end to end: plan, apply, and the
  check no longer trips. -- **Held**: covered by an integration
  test that trips the check, shelters, and re-checks.

The implementation:

- `runner/guard/security.py`: the feature `personal_docs_shelter`
  joins the modes family (section 2's semantics); the shipped
  example config states it.
- `runner/oracle/personal_docs.py`: the shelter marker --
  constants and `is_shelter_dir`, a bounded marker read that
  fails to False on any doubt -- and the scan's skip of a
  verified shelter folder.
- `runner/oracle/personal_docs_shelter.py`: the operator tool.
  Plan (default), `--apply`, `--restore`; the mode gate read
  from the runner config; moves that never delete and never
  overwrite (numbered suffixes); a manifest inside the shelter
  folder, validated fail-closed before anything moves (paths
  confined to home and to the shelter, exact key set, no
  duplicates); restore that never overwrites an occupied
  original place. Run as
  `python -m runner.oracle.personal_docs_shelter`; the operator
  document is `personal-documents-shelter.md`.
- The shelter module is not in the canonical core list: the core
  is the code the runner executes, and the shelter runs only
  when the operator invokes it.

## 6. Queued work

Recorded, not claimed:

1. **Startup-offered sheltering.** Under the *eyes open* and
   *lockdown* postures, startup could offer the shelter plan
   beside the warning banner (an offer, printed, never an
   automatic move). Needs a posture-level hook and its own
   tests.
2. **A privacy-safe telemetry helper**, built to the Fremont
   contract (counters only; dimension keys matching
   phone/token/password/email/message/body/authorization dropped;
   string values over 64 characters dropped), for the first
   surface that needs counters -- with a production caller this
   time, or not at all.
3. **A raw-evidence retention setting**: an operator-declared
   number of days for raw crash/result evidence, enforced by a
   sweep, in the modes family.
4. **A tree-wide value-confinement test**: the boundary-test
   technique generalised -- a test that proves named sensitive
   values appear only in allowlisted files.
5. **An erasure path for operator-held records**: Fremont has
   none and neither does this suite; a deliberate, audited
   forget operation for a machine's own run records is design
   work, not a small lift.

## 7. Proof

Implemented and measured on 2026-11-08:

- New tests: `runner/tests/test_personal_docs_shelter.py` --
  plan shape (watched folders, depth, skip rules, symlinks,
  bookend and unicode names), apply/restore (marker, manifest,
  collisions, occupied restore, vanished sources, a corrupt
  manifest refusing), the marker's effect on the warning check,
  the manifest fuzz family (17 malformed shapes, each failing
  closed and moving nothing), and the mode gate through the
  tool's entry point (off refuses, audit plans only, enforce
  applies, no-config takes the family default).
- Existing families re-run green: the personal-documents tests,
  the security-config tests, the posture and parity families,
  the startup gate, the core measure (re-recorded, section 5),
  the document guards and the reader-pages test over the three
  new documents in this drawer.
