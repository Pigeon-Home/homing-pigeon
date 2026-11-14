# Readiness for the official release: the standing checklist

Dated 2026-11-09. This page is the living checklist an official
release of this project is checked against. It assembles what
the tree already establishes — the release gate's design, the
measured default posture, the ship pipeline's own guards, the
statistics record, and the spillage doctrine — into one list
that can be worked top to bottom at the gate. It decides
nothing new: where a check rests on another document, that
document is named, and the check is only as strong as the
evidence it points at.

The checklist is worked per candidate, the way the release
gate's own checklist is (release-gate.md). A line is checked
only from a record — a build result, a ship record, a test
run, a page read — never from memory of an earlier release.
Lines that cannot be checked yet are gaps, and the standing
gaps known today are listed at the foot of this page so the
list itself stays honest.

## 1. The candidate and the gate

From the release gate's design (release-gate.md), which stands
at Gate 5 of the desk:

- A candidate record (runner/tools/release_gate.py) exists
  for the exact full version and release commit being cut,
  and the record's ten items are worked in order.
- Every review class the candidate's range touches — protocol,
  execution, key handling, confinement, job-user behavior,
  extension loading, disclosure controls — carries a reviewed
  line in the record, and the classes the range did not touch
  are printed as not touched.
- Dark landings in the range are named in the record, each
  either activated deliberately for this release or shipped
  dark on purpose.
- The sign-off block is filled and validates under
  `release_gate.py check-signoff`: full four-component
  version, full commit SHA, candidate form agreeing with the
  verdict form, one reviewed line per touched class, no
  reviewed line for an untouched class.
- The record states the state of main honestly: the tip
  green, or the protected-candidate form with the red tip and
  its red guard families named.

## 2. Secure by default

From the measured default posture
(docs/steady/security/default-posture.md), whose phase-2 plan
names the behavior changes the measurement supports. An
official release carries those changes landed, each with its
own tests:

- Confinement at enforce fails the job, not open: a job whose
  sandbox cannot engage or whose command cannot be built is
  refused under enforce instead of running unsandboxed.
- The job user at enforce fails the job, not open: the three
  job-time fallback reasons refuse the job under enforce
  instead of running it as the current user.
- A mode that cannot engage says so at startup: a job user at
  enforce with no user named is named in the startup record
  and the posture report as not engaged.
- Audience at enforce without a runner id no longer warns and
  skips: it joins the refusal class, or the runner id is
  generated wherever a config is first written.
- The installer states the platform gates: a first install on
  a platform where a mechanism cannot engage writes that mode
  into the seeded config at off or audit, stated in the file.
- One result-view default: the seed and the code fallback both
  read attested, and the README posture table tells the single
  story that results.
- `runner/tests/test_default_posture.py` is green on the
  candidate, pinning the seed, the effective-mode map, and
  the installer profiles to the claims above.

## 3. The documentation reads as an official release

- No page in the tree presents the suite as provisional, in
  beta, or as a work in progress; status language everywhere
  matches what the release is.
- The version line the release ships on is settled, and the
  version carriers agree: `pyproject.toml`,
  `runner/_version.py`, and `runner/ops/install.py` carry the
  same full version (the cut-release workflow refuses the tag
  when they do not).
- The release's changelog section covers every content commit
  in the candidate's range (the gate's checklist item 6).
- The IETF pages state the drafts' standing as it is: the
  posted revisions stand as the current text. The living v1
  and v2 draft texts remain byte-identical to the posted
  texts — the mirror rule is not touched by any readiness
  pass; wording changes for the drafts travel the established
  review route, never into the mirrored texts.
- The reader's pages stay quiet: no process trail in the
  manuals or the guides, held by
  `runner/tests/test_reader_docs_quiet.py`.

## 4. The figures

- A fresh dormant-code audit stands in the record
  (dormant-code-audit.md), measured on a named commit with
  the standing method, and statistics.md is corrected from
  it: the facts block's latent percentages and audit date
  are the fresh audit's.
- `runner/tools/refresh_figures.py --check` is green and
  `runner/tests/test_doc_figure_slots.py` passes: every
  generated slot in AGENTS.md, PROTOCOL.md, and
  docs/steady/fuzzing.md equals the facts.
- The milestone line in statistics.md states measured
  figures only, each with its measured basis beside it.
- The version's token component is recounted fresh —
  uncached — on the tree being shipped, and the statistics
  write stands as the last content commit before the
  release commit (the frozen order of the release
  procedure).

## 5. The channels

Every outlet presents the release as a full release, with no
beta, alpha, or pre-release marker standing against it:

- GitHub: the release is published (draft=false), not
  flagged as a pre-release, and stands as the latest
  release, with the full asset set.
- PyPI (the package is pigeon-home-runner): the project
  page's development-status classifier reads
  Production/Stable, and the release's wheel and sdist are
  the current files.
- Docker: ghcr.io/pigeon-home/homing-pigeon carries the
  version tag and the latest tag for this release.
- SourceForge: the project's development status reads
  Production/Stable (set 2026-11-09, from Beta), and the
  default download is the current release's file.
- GitLab: the mirror release carries the full asset set,
  matching the GitHub release.

## 6. The spillage and privacy sweep

From SECURITY.md's spillage doctrine and the accidental-commit
protections, worked over the candidate's range before the
cut:

- The range diff is read against the private shelf's list:
  no credential or secret value, no security-testing
  material (what is being examined, engagement or case
  records, unfixed findings in any detail, crash data), and
  no client information stands in any file the range adds
  or changes.
- No agent permission or configuration state stands in the
  tree the release ships: the approval files, saved-command
  records, and deployment config state the accidental-commit
  work guards against are absent or held out, and the
  agent-state guard's tests are green.
- The commit messages and the release notes of the range
  carry no private-shelf material either; the sweep reads
  messages, not only files.
- Name discipline holds: commit subjects name no person,
  and no real name registry stands in the tree (nameguard's
  registry in the tree is the example only).

## 7. The ship pipeline

From the release procedure (docs/steady/use/use-runbook.md,
Job 4) and the cut-release workflow's guards, in their order:

- The tag does not already exist.
- The version carriers agree (section 3 above; the workflow
  checks them again).
- The build job on the exact commit has concluded success —
  the nine guard jobs green — before any tag lands.
- The main build on the release commit is green, and the
  tag build is green on every leg.
- The publish jobs succeed: release, pypi-publish,
  sourceforge, gitlab, and the Docker image publish.
- The release stands published with its full asset set
  (13 assets at the current line's shape), including
  SHA384SUMS, the SBOM, the build-provenance attestation,
  and the project snapshot.
- The stamp check matches three times: the wheel, the
  sdist, and the platform tarball re-downloaded and matched
  against the release's sums.

## 8. After the cut

- Every outlet is checked by name — GitHub Release, PyPI,
  Docker, SourceForge, GitLab — before the release is
  reported, and the release is reported once.
- The candidate's signed record stands committed on main
  (in the gate's enforcing phase, before the tag; until
  then, with the release).

## Standing gaps, as of 2026-11-13

The honest state of the lines above, so the checklist is
never read as claiming more than stands:

- **The phase-2 changes have landed whole.** Section 2's
  six behavior changes stand as a plan in the posture
  record; items 1 and 2 — confinement and the job user at
  enforce failing the job instead of stepping down —
  landed on 2026-11-09 with their tests. Items 3, 4 and 5
  landed beside them: the unengaged mode named at startup
  and in the posture report, the audience check refusing
  startup without a runner id, and the installer stating
  the platform gates in the seeded config (2026-11-10).
  Item 6 has landed beside them (2026-11-13): the single
  result-view default — the seed and the code fallback
  read `attested`, so a hand-written or no-profile config
  tells the same story as a fresh install.
- **The release gate is advisory, not enforcing.** The
  candidate-record tooling and the validator stand landed;
  the trains do not yet refuse a tag for want of a signed
  record. The gate becomes a block at the conductor's word,
  as its design states; until then section 1 is a practice
  the record shows, not a refusal the pipeline makes.
- **The dormant-code figures are fresh as of this pass.**
  The milestone line's non-latent percentage rested on the
  2026-11-03 audit until the fresh audit landed beside this
  page (dormant-code-audit.md, measured 2026-11-09):
  96.83% non-latent, from 3.17% near-duplicate and 0.03%
  exact. Section 4's first line is checked from that record
  onward; the gap reopens only as that audit ages.
- **Channel polish is verified outlet by outlet, not
  assumed.** Section 5's lines are each read from the
  outlet itself at the cut; the SourceForge status line was
  corrected on 2026-11-09 and the package metadata line
  with it, and the remaining outlets answer at their own
  checks.
