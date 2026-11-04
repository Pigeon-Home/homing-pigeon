# Start here — the steady shelf

Steady is the quiet shelf. A document lands here when it has not been touched for a while, and this folder exists for 1 thing: wandering. If you opened steady, you came to explore.

Everything on this shelf arrived between 2026-10-13 and 2026-11-01 — the project's first 3 weeks. Nothing here is deleted, and every file sits in exactly 1 place.

## The core of the project

9 files sit at the top of this folder, in no folder at all. They are the heart of the project: what the system is, how it is used, and how it keeps itself safe.

- overview.md — the project overview — what Homing Pigeon is and where the campaign stands. Untouched since 2026-10-30.
- networking.md — the networking picture — what talks to what, drawn as trust boundaries. Untouched since 2026-10-24.
- sending.md — sending a job — how any SI drives the runner through its mailbox. Untouched since 2026-11-01.
- extensions.md — user extensions — how the agent learns a new sense. Untouched since 2026-11-01.
- fuzzing.md — fuzzing the intake — the fuzzing method the project runs on. Untouched since 2026-10-30.
- present-but-invalid-config.md — the present-but-invalid decision — when a bad setting means refuse to start, and when it means fall back to the default. Untouched since 2026-10-30.
- secret-rotation.md — shared secret rotation — the 90 day rule for the secret every job is signed with. Untouched since 2026-10-30.
- verification.md — verifying a release — checking the bits you downloaded are the bits the build produced. Untouched since 2026-10-24.
- emergency.md — the emergency plan — the muster, the DRIs, the postmortem. Untouched since 2026-10-30.

## The drawers

The other 117 files are in 9 drawers, named the way the rest of the project's documents are named:

- design — 7 files. design documents and decision records — how pieces were shaped before they were built.
- security — 8 files. the hardening set — host hardening, the confinement profiles, and the security papers.
- use — 8 files. guides and runbooks — running the system and using it day to day.
- project — 11 files. the project's own papers — plans, maps, and campaign notes.
- oracle — 3 files. the Oracle's papers — its playbook, its reviews, its senses.
- seats — 3 files. papers from the seats era, which closed on 2026-10-31 — who sat where, and what was asked.
- proofs — 2 files. proof and verification records.
- specimens — 5 files. raw artifacts — logs and machine output, kept as found.
- reports — 70 files. the dated record — audits, coverage, reviews, rig reports, and release records; the biggest drawer.

## First stops: important, and untouched the longest

These are the files to look at first on a wander — the ones that carry the most weight and have gone the longest without a fresh look. Each one is very likely wrong somewhere by now.

1. docker.md (use) — untouched since 2026-10-18, 17 days. the Docker reference page; the release machinery has moved a long way since it was last checked against the image.
2. hardening_report.md (security) — untouched since 2026-10-18, 17 days. the hardening report; the lockdown flip has shipped since, and this still tells the older story.
3. use-runbook.md (use) — untouched since 2026-10-21, 14 days. the runner runbook, one of the first 2 files in the whole project; it predates the lockdown flip and the DTLS work.
4. transports-status.md (reports) — untouched since 2026-10-21, 14 days. the transports status page; a whole new transport story (DTLS over email) has landed since it froze.
5. networking.md (the top of steady) — untouched since 2026-10-24, 11 days. the trust-boundary picture; new transports have drawn new edges since it was last touched.
6. platforms.md (use) — untouched since 2026-10-24, 11 days. the proven platforms list; it has not been updated since the day it arrived, and platform claims go stale quietly.
7. verification.md (the top of steady) — untouched since 2026-10-24, 11 days. the release verification walk; the version scheme itself changed to 4 numbers after this was last touched.

## Every file, drawer by drawer, oldest untouched first

Inside each drawer below, files are listed oldest untouched first, with the date each one arrived in the project. The top of each list is where the stalest reading lives.

### design — 7 files

- approval-gate-design.md — untouched since 2026-10-21 · arrived 2026-10-15
- asymmetric-signing-design.md — untouched since 2026-10-21 · arrived 2026-10-15
- extension-review-design.md — untouched since 2026-10-25 · arrived 2026-10-25
- ci-runtime.md — untouched since 2026-10-26 · arrived 2026-10-22
- oracle-opinion-design.md — untouched since 2026-10-30 · arrived 2026-10-18
- remediation-design.md — untouched since 2026-10-30 · arrived 2026-10-18
- agent-stamp-design.md — untouched since 2026-11-01 · arrived 2026-10-22

### security — 8 files

- hardening_report.md — untouched since 2026-10-18 · arrived 2026-10-15
- security-test-plan.md — untouched since 2026-10-21 · arrived 2026-10-15
- hardening-readme.md — untouched since 2026-10-24 · arrived 2026-10-15
- homing-pigeon — untouched since 2026-10-24 · arrived 2026-10-15
- windows.md — untouched since 2026-10-24 · arrived 2026-10-15
- homing-pigeon.service — untouched since 2026-10-26 · arrived 2026-10-15
- homing_pigeon.te — untouched since 2026-10-26 · arrived 2026-10-15
- personal-documents-warning.md — untouched since 2026-10-26 · arrived 2026-10-21

### use — 8 files

- docker.md — untouched since 2026-10-18 · arrived 2026-10-14
- handoff-local-si.md — untouched since 2026-10-21 · arrived 2026-10-15
- idea321-runbook.md — untouched since 2026-10-21 · arrived 2026-10-20
- use-runbook.md — untouched since 2026-10-21 · arrived 2026-10-13
- platforms.md — untouched since 2026-10-24 · arrived 2026-10-24
- local-si-test.md — untouched since 2026-10-27 · arrived 2026-10-15
- live-examples.md — untouched since 2026-10-30 · arrived 2026-10-25
- own-cloud.md — untouched since 2026-10-30 · arrived 2026-10-25

### project — 11 files

- roadmap-spec.md — untouched since 2026-10-21 · arrived 2026-10-15
- contributing.md — untouched since 2026-10-24 · arrived 2026-10-13
- future-finished-2026-10-25.md — untouched since 2026-10-25 · arrived 2026-10-25
- industry-map.md — untouched since 2026-10-27 · arrived 2026-10-16
- telephone-pole-words.md — untouched since 2026-10-27 · arrived 2026-10-27
- de_dust-where.md — untouched since 2026-10-30 · arrived 2026-10-27
- de_dust.md — untouched since 2026-10-30 · arrived 2026-10-26
- de_dust2.md — untouched since 2026-10-30 · arrived 2026-10-29
- runner-line-reduction-runbook.md — untouched since 2026-10-30 · arrived 2026-10-25
- telephone-pole.md — untouched since 2026-10-30 · arrived 2026-10-28
- hosting.md — untouched since 2026-10-31 · arrived 2026-10-25

### oracle — 3 files

- senses.md — untouched since 2026-10-24 · arrived 2026-10-15
- dri-playbook.md — untouched since 2026-10-26 · arrived 2026-10-15
- job-review.md — untouched since 2026-10-26 · arrived 2026-10-15

### seats — 3 files

- questions.md — untouched since 2026-10-24 · arrived 2026-10-23
- bravo.md — untouched since 2026-10-31 · arrived 2026-10-31
- status.txt — untouched since 2026-10-31 · arrived 2026-10-27

### proofs — 2 files

- connector-roundtrip.md — untouched since 2026-10-18 · arrived 2026-10-14
- verify-v31.md — untouched since 2026-10-19 · arrived 2026-10-15

### specimens — 5 files

- oracle-learning.jsonl — untouched since 2026-10-25 · arrived 2026-10-25
- runner.log — untouched since 2026-10-25 · arrived 2026-10-25
- security-events.jsonl — untouched since 2026-10-25 · arrived 2026-10-25
- runs.jsonl — untouched since 2026-10-27 · arrived 2026-10-27
- passes.jsonl — untouched since 2026-10-30 · arrived 2026-10-26

### reports — 70 files

- v3.5.2-coverage.md — untouched since 2026-10-16 · arrived 2026-10-16
- mutation.md — untouched since 2026-10-18 · arrived 2026-10-18
- v3.7.22-coverage.md — untouched since 2026-10-18 · arrived 2026-10-17
- v3.11.1-coverage.md — untouched since 2026-10-19 · arrived 2026-10-19
- v3.7.30-coverage.md — untouched since 2026-10-19 · arrived 2026-10-18
- audit-2026-10-15.md — untouched since 2026-10-20 · arrived 2026-10-15
- known-failures.md — untouched since 2026-10-20 · arrived 2026-10-15
- transports-status.md — untouched since 2026-10-21 · arrived 2026-10-15
- ci-failures.md — untouched since 2026-10-22 · arrived 2026-10-22
- v3.12.20-coverage.md — untouched since 2026-10-22 · arrived 2026-10-22
- doc-default-divergences.md — untouched since 2026-10-23 · arrived 2026-10-23
- v3.12.61-coverage.md — untouched since 2026-10-24 · arrived 2026-10-24
- v3.12.65-coverage-gaps.md — untouched since 2026-10-24 · arrived 2026-10-24
- v3.12.65-coverage.md — untouched since 2026-10-24 · arrived 2026-10-24
- audit-report-since-7d.txt — untouched since 2026-10-25 · arrived 2026-10-25
- audit-report.txt — untouched since 2026-10-25 · arrived 2026-10-25
- ci-health.md — untouched since 2026-10-25 · arrived 2026-10-25
- job-campaign.txt — untouched since 2026-10-25 · arrived 2026-10-25
- job-connector-test.txt — untouched since 2026-10-25 · arrived 2026-10-25
- live-2026-10-25-readme.md — untouched since 2026-10-25 · arrived 2026-10-25
- mutation-survivors.txt — untouched since 2026-10-25 · arrived 2026-10-25
- posture.txt — untouched since 2026-10-25 · arrived 2026-10-25
- result-campaign.txt — untouched since 2026-10-25 · arrived 2026-10-25
- result-connector-test.txt — untouched since 2026-10-25 · arrived 2026-10-25
- rig-facts.txt — untouched since 2026-10-25 · arrived 2026-10-25
- transport-extensions-email-inbox-done.txt — untouched since 2026-10-25 · arrived 2026-10-25
- transport-extensions-email-outbox-done.txt — untouched since 2026-10-25 · arrived 2026-10-25
- v3.13.21-coverage.md — untouched since 2026-10-25 · arrived 2026-10-25
- v3.13.27-coverage.md — untouched since 2026-10-25 · arrived 2026-10-25
- v3.13.29-coverage.md — untouched since 2026-10-25 · arrived 2026-10-25
- v3.13.30-coverage.md — untouched since 2026-10-25 · arrived 2026-10-25
- v3.13.38-coverage.md — untouched since 2026-10-25 · arrived 2026-10-25
- v3.13.42-coverage.md — untouched since 2026-10-25 · arrived 2026-10-25
- v3.13.8-coverage-gaps.md — untouched since 2026-10-25 · arrived 2026-10-25
- v3.13.8-coverage.md — untouched since 2026-10-25 · arrived 2026-10-25
- v3.13.21-coverage-gaps.md — untouched since 2026-10-26 · arrived 2026-10-26
- v3.13.27-coverage-gaps.md — untouched since 2026-10-26 · arrived 2026-10-26
- v3.13.29-coverage-gaps.md — untouched since 2026-10-26 · arrived 2026-10-26
- v3.13.30-coverage-gaps.md — untouched since 2026-10-26 · arrived 2026-10-26
- v3.13.38-coverage-gaps.md — untouched since 2026-10-26 · arrived 2026-10-26
- v3.13.42-coverage-gaps.md — untouched since 2026-10-26 · arrived 2026-10-26
- 2026-10-27.md — untouched since 2026-10-27 · arrived 2026-10-27
- coverage-local.md — untouched since 2026-10-27 · arrived 2026-10-27
- first-ping-readme.md — untouched since 2026-10-27 · arrived 2026-10-27
- germany-control-2026-10-27.md — untouched since 2026-10-27 · arrived 2026-10-27
- guard-wire-oracle-2026-10-27.md — untouched since 2026-10-27 · arrived 2026-10-27
- hosting-2026-10-27.md — untouched since 2026-10-27 · arrived 2026-10-27
- local-regression-2026-10-27.md — untouched since 2026-10-27 · arrived 2026-10-27
- local-rig-2026-10-27-coverage-gaps.md — untouched since 2026-10-27 · arrived 2026-10-27
- project-review.md — untouched since 2026-10-27 · arrived 2026-10-26
- queues-2026-10-27.md — untouched since 2026-10-27 · arrived 2026-10-27
- report.md — untouched since 2026-10-27 · arrived 2026-10-27
- review-2026-10-27.md — untouched since 2026-10-27 · arrived 2026-10-27
- tools-2026-10-27.md — untouched since 2026-10-27 · arrived 2026-10-27
- v3.13.62-coverage-gaps.md — untouched since 2026-10-27 · arrived 2026-10-27
- v3.13.62-coverage.md — untouched since 2026-10-27 · arrived 2026-10-27
- germany-rig-2026-10-28.md — untouched since 2026-10-28 · arrived 2026-10-28
- germany-rig-driving-2026-10-27.md — untouched since 2026-10-28 · arrived 2026-10-27
- rig-2026-10-27.md — untouched since 2026-10-28 · arrived 2026-10-27
- san-francisco-rig-2026-10-28.md — untouched since 2026-10-28 · arrived 2026-10-28
- distill-dry-run.md — untouched since 2026-10-30 · arrived 2026-10-30
- ietf-drafts-suite-2026-10-30.txt — untouched since 2026-10-30 · arrived 2026-10-30
- ietf-status-suite-2026-10-30.txt — untouched since 2026-10-30 · arrived 2026-10-30
- release-blocked-windows.md — untouched since 2026-10-30 · arrived 2026-10-30
- release.md — untouched since 2026-10-30 · arrived 2026-10-30
- v3.14.43-release-retrospective.md — untouched since 2026-10-31 · arrived 2026-10-30
- v3.14.46-release-retrospective.md — untouched since 2026-10-31 · arrived 2026-10-31
- v3.14.47-release-retrospective.md — untouched since 2026-10-31 · arrived 2026-10-31
- v3.15.1-coverage-gaps.md — untouched since 2026-11-01 · arrived 2026-11-01
- v3.15.1-coverage.md — untouched since 2026-11-01 · arrived 2026-11-01

### the top of steady (core) — 9 files

- networking.md — untouched since 2026-10-24 · arrived 2026-10-16
- verification.md — untouched since 2026-10-24 · arrived 2026-10-18
- emergency.md — untouched since 2026-10-30 · arrived 2026-10-28
- fuzzing.md — untouched since 2026-10-30 · arrived 2026-10-20
- overview.md — untouched since 2026-10-30 · arrived 2026-10-29
- present-but-invalid-config.md — untouched since 2026-10-30 · arrived 2026-10-23
- secret-rotation.md — untouched since 2026-10-30 · arrived 2026-10-16
- extensions.md — untouched since 2026-11-01 · arrived 2026-10-18
- sending.md — untouched since 2026-11-01 · arrived 2026-10-24

Dates come from the project's own history on main: the day a file first arrived, and the last day its contents really changed. A move from place to place does not count as a change.
