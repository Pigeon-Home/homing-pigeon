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

Recorded after the measurement runs. In the commit that carries
the supposition above, this section stands empty.

## The phase-2 plan

Recorded with the findings.
