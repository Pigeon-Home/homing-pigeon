# The default posture, measured

An outside review of this project (November 2026) made two claims
about the first-run posture: that the default story is muddled —
the config-file defaults are permissive while the security controls
claim to be on at enforce — and that some controls set to enforce
can still degrade at job time, running a job with less isolation
than the mode promises. This page records what the tree itself
says: what a first-time install actually does by default, layer by
layer, and exactly where an enforce control can step down at job
time. The behavior changes those findings support are listed at
the end as a plan; this page is the evidence, not the change.

Three different things are each called "the default" in the
project's own writing, and the review's muddle charge lives in
the gaps between them:

1. **The config-file defaults.** What a hand-written or seeded
   `config.json` does: the shipped seed is
   `runner/config.example.json`, and the code's own fallbacks for
   absent keys sit behind it.
2. **The installer profile.** A fresh install applies one built-in
   profile chosen by the platform, on top of the seed.
3. **The security-mode defaults.** The `security.modes` family
   (each feature `off`, `audit`, or `enforce`) and the rule that
   reads a feature the config does not set.

## Supposition

Written before the measurement below was run. The measurement is
expected to show:

- **S1.** The shipped seed states every security feature at
  `enforce`, and the feature names it states are exactly the
  feature list the code enforces — no drift between the seed and
  the code.
- **S2.** A config with no security block at all reads every
  feature as `enforce` under the code's default rule. The
  permissive side of a first run therefore comes from the
  non-mode keys (the judge and the result view), not from the
  security modes.
- **S3.** No built-in installer profile changes any security
  mode, with one exception (the hosted profile). A fresh-install
  profile changes only the judge, the result view, redaction
  patterns, protected paths, and, on the light installs, the
  Oracle's mode.
- **S4.** Nothing in the install path writes
  platform-appropriate security modes. A first start on a
  platform where an enforce mechanism cannot engage refuses on
  that gate until the owner edits the config by hand.
- **S5.** The job-time step-downs are exactly two chains —
  confinement and the job user — each one warns, writes a
  `fallback` audit entry, and runs the job weaker. Every enforce
  mechanism that cannot engage at startup refuses startup
  instead. Two softer degradations stand beside the chains: an
  enforce audience check with no runner id configured warns and
  is skipped, and the job user at enforce with no user named
  engages nothing and warns nowhere.
- **S6.** The reader-facing documents (the README posture table
  and the SECURITY.md confinement and job-user sections)
  already describe the startup refusals and the job-time
  fallbacks accurately. The one statement the measurement will
  find wrong is a code comment, not a reader document.
- **S7.** The seed names no job user, so the job-user control at
  its default `enforce` has nothing to demote jobs to on a fresh
  install: it reads enforce while engaging nothing.

## Method

The deterministic half of the measurement is
`runner/tests/test_default_posture.py`: it reads the shipped
seed, the code's effective-mode map, and every built-in profile
as the installer applies it, and pins the claims above that a
test can hold. The behavioral half — the startup refusals and
the job-time fallback chains — is already pinned by the existing
suites named in the findings, and is cited there rather than
re-measured.

## Findings

Measured 2026-11-09 against the tree at release commit
654de37cd8a0dfa152e07fe4a2093d9b1b015c1b. The
supposition held on every point but one nuance (S6). Verdicts,
with the evidence:

- **S1 — confirmed.** The seed's `security.modes` names exactly
  the code's feature list and states every one `enforce`
  (`runner/config.example.json` lines 85–96;
  `runner/guard/security.py` line 44, the feature list). Pinned
  by `test_default_posture.py`.
- **S2 — confirmed.** `sec_mode` (`runner/guard/security.py`
  line 350) reads a feature the config does not set as
  `enforce`; an absent, null, or empty security block — and an
  empty modes map — all read every feature `enforce`. The
  permissive side of a first run is the non-mode keys: the judge
  reads `off` when unset (`runner/ops/mail.py` line 343) and the
  result view reads `full` when unset
  (`runner/ops/policy.py` lines 33–34), both pinned against the
  seed and against the result-policy code itself. The review's
  muddle is real but located here: three layers, and only the
  mode layer is strict by default.
- **S3 — confirmed.** Of the built-in profiles
  (`runner/ops/install.py` line 1682), only `hosted` names
  security modes (confinement `enforce`, audience `audit`, line
  1733). Every other profile changes the judge (to `advisory`),
  the result view (to `attested`), redaction patterns, and
  protected paths; the light profiles add the deterministic
  Oracle mode. Applying each profile to the seed and reading the
  effective modes back is pinned in the test.
- **S4 — confirmed.** The installer seeds `config.json` by
  copying the example file verbatim (`runner/ops/install.py`
  line 486) and no install path writes platform-appropriate
  modes. The startup gates then decide first starts by platform
  (below).
- **S5 — confirmed.** The job-time step-downs are exactly two
  chains. Confinement: when the sandbox is unavailable at job
  time, or its command cannot be built, the job runs
  unsandboxed with a warning and a `fallback` audit entry
  (`runner/runner.py` lines 367–379). The job user: not root,
  an unresolvable user, or a workdir that cannot be chown'd
  each warn, audit `fallback`, and run the job as the current
  user (`runner/ops/remediation_ops.py` lines 203, 210, 238).
  At startup the same mechanisms refuse instead
  (`runner/ops/main.py` lines 113–137;
  `runner/guard/sandbox.py` line 88). The two softer
  degradations stand as supposed: audience at `enforce` with
  no runner id warns once and the check is skipped
  (`runner/ops/main.py` lines 138–143), and the job user at
  `enforce` with no user named engages nothing and writes no
  audit entry and no log line at job time
  (`runner/ops/remediation_ops.py` lines 180–186). The chains
  are reachable when conditions change after a good start —
  the sandbox binary leaving the path, a user removed — or
  when a per-job build step the startup trial cannot rehearse
  fails, such as an operator bind path. The existing suites
  pin both halves (startup: `test_decision1_startup.py`,
  `test_windows_platform_proofs.py`; job time:
  `test_confinement.py`, `test_security_parity.py`).
- **S6 — confirmed, with the exception where it was expected.**
  The README posture table (lines 229–262) and the SECURITY.md
  confinement and job-user sections (lines 533–590) describe
  the startup refusals and the job-time fallbacks accurately.
  The one wrong statement is a code comment:
  `runner/ops/main.py` said a missing security block leaves
  "every security feature stays off"; the mode reader reads
  `enforce`. The comment is corrected in the commit that
  carries these findings.
- **S7 — confirmed.** The seed's security block names no
  job-user sub-block at all, so the control at its default
  `enforce` demotes nothing on any fresh install until the
  owner configures a user. It reads enforce while engaging
  nothing, and nothing at startup says so.

What a first-time install does, by platform, all three layers
composed. In every row the seed is the example file, the modes
at first start read all-`enforce`, and the profile is the one
the installer's host decision picks (`runner/ops/install.py`
line 2031):

| Install route | Profile | First start |
|---|---|---|
| Linux, sandbox able to engage | password-only | Starts. Jobs run sandboxed; judge advisory, results attested. |
| Linux, sandbox missing or its namespaces blocked | password-only | Refuses to start, naming confinement, until the owner sets that mode to `audit` or `off`. |
| Raspberry Pi | pi-light | The same confinement gate; the Oracle runs deterministically, no model installed. |
| Windows (one-home installer) | password-only | Refuses on two gates — confinement is Linux-only and the job-user demote is POSIX-only — until the owner lowers both modes in `config.json`. |
| macOS | password-only | Refuses on the confinement gate until the owner lowers it. |
| FreeBSD | password-only | Refuses on the confinement gate (the sandbox is Linux-only). |
| No profile (`--no-profile`, or a platform the host decision does not know), or a hand-written config | none | The seed's own row: judge `off`, results `full`, modes `enforce` — the posture the README calls "just run it" — with the same startup gates above. |

One more measured detail: at the `attested` view a result
carries its output fields emptied, not omitted — the digest
and attestations ride, the body is blank. The review's
proposed default (attested disclosure) is therefore already
the fresh-install behavior through the profiles; the `full`
default survives only in the seed, in the code fallback behind
an absent key, and in a no-profile install.

## Conclusions

The review's two charges, as the tree answers them:

1. **The default story is three stories.** The security modes
   are strict by default everywhere; the installer profile is
   one notch tighter than the config-file defaults on the two
   keys it touches; and nothing states the platform gates for
   the owner at install time, so on three of the supported
   platforms the first start is a refusal the owner must edit
   their way out of, choosing weaker modes unguided.
2. **Enforce can step down at job time, in exactly two
   places.** Both are loud and audited, both exist because
   conditions can change after a good start — but a job that
   runs unsandboxed, or as the runner's own account, under a
   mode that reads `enforce` is a downgrade of the promise,
   however well recorded. Two quieter gaps stand beside them:
   an audience check skipped for want of a runner id, and a
   job-user mode that reads enforce while engaging nothing.

## The phase-2 plan

Behavior changes, in the order the evidence supports. None of
these are made by the commits that carry this page; each lands
with its own tests when it is taken up.

1. **Confinement at enforce fails the job, not open.** When
   the sandbox cannot engage or its command cannot be built
   at job time, an `enforce` job is refused with the fallback
   recorded, instead of running unsandboxed. `audit` and `off`
   are unchanged.
2. **The job user at enforce fails the job, not open.** The
   three job-time fallback reasons (not root, user
   unresolvable, workdir not chown-able) refuse the job under
   `enforce` instead of running it as the current user.
3. **A mode that cannot engage says so at startup.** The job
   user at `enforce` with no user named is named in the
   startup record and in the posture report as not engaged,
   so `enforce` never silently means nothing.
4. **Audience at enforce without a runner id joins the
   refusal class,** or the runner id is generated wherever a
   config is first written; the warn-and-skip path closes.
5. **The installer states the platform gates.** A first
   install on a platform where a mechanism cannot engage
   writes that mode into the seeded config at `off` or
   `audit`, stated in the file, instead of leaving the
   default to refuse the first start; the Windows guidance
   in `docs/steady/security/windows.md` names the two modes.
6. **One result-view default.** The seed and the code
   fallback move to `attested`, so the config-file defaults
   and a fresh install tell the same story, and the README
   posture table is updated to the single row that results.
