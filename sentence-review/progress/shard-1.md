# Sentence review — shard 1 progress

Shard 1 of 3: the documents standing at positions 1, 4, 7, 10, …
(every 3rd, starting at the 1st) of the not-started list in
sentence-review/INDEX.md as it stood at main cbb52068 — 61 documents
of the 183 not started. INDEX.md itself is not edited by the shards;
this file is the shard's record.

Extraction: prose sentences in reading order. Headings, fenced code
blocks and link targets are structure, not units. Each list item is
its own run; a table row is one run; a horizontal rule is one unit.
Where the source formatting splits a sentence (a bold lead-in on its
own line), the pieces are separate units, recorded as extracted and
flagged, as phase 1 did.

## Completed

| Document | Units | Flagged | Pre-release | Post-release |
|---|---|---|---|---|
| docs/ietf/draft-slutsky-homing-pigeon/status.md | 5 | 0 | 5 | 0 |
| docs/steady/networking.md | 37 | 3 | 37 | 0 |
| docs/steady/project/telephone-pole-words.md | 7 | 0 | 7 | 0 |
| docs/steady/emergency.md | 66 | 2 | 66 | 0 |
| docs/steady/secret-rotation.md | 55 | 1 | 52 | 3 |
| docs/steady/verification.md | 42 | 0 | 42 | 0 |
| docs/ietf/status.md | 108 | 2 | 101 | 7 |
| AGENTS.md | 216 | 4 | 215 | 1 |
| docs/infrastructure-documents/proofs/content-rung-50000.md | 31 | 0 | 31 | 0 |
| docs/infrastructure-documents/proofs/content-sh-macos.md | 35 | 0 | 35 | 0 |
| docs/infrastructure-documents/proofs/stage6-transports.md | 20 | 1 | 20 | 0 |
| docs/infrastructure-documents/proofs/stage6-keys.md | 31 | 1 | 31 | 0 |
| docs/infrastructure-documents/proofs/stage2.md | 42 | 1 | 42 | 0 |
| docs/infrastructure-documents/security/threat-model.md | 32 | 0 | 26 | 6 |
| docs/infrastructure-documents/project/duplication-audit.md | 131 | 0 | 131 | 0 |
| docs/infrastructure-documents/oracle/configuring-oracle.md | 244 | 1 | 239 | 5 |
| docs/infrastructure-documents/design/v3-sentence-review.md | 293 | 11 | 290 | 3 |
| docs/infrastructure-documents/design/v1-v2-sentence-review.md | 347 | 3 | 336 | 11 |
| docs/infrastructure-documents/proofs/content-series-review.md | 41 | 0 | 25 | 16 |
| docs/infrastructure-documents/proofs/stage8-50000.md | 32 | 1 | 32 | 0 |
| docs/infrastructure-documents/proofs/stage9.md | 43 | 0 | 42 | 1 |
| docs/infrastructure-documents/proofs/stage4-p3.md | 74 | 1 | 73 | 1 |
| docs/steady/design/extension-review-design.md | 38 | 1 | 37 | 1 |
| docs/steady/design/approval-gate-design.md | 52 | 0 | 7 | 45 |
| docs/infrastructure-documents/proofs/stage4-p6.md | 101 | 1 | 99 | 2 |
| docs/steady/oracle/dri-playbook.md | 62 | 0 | 61 | 1 |
| docs/infrastructure-documents/security/model-and-proof-testing.md | 110 | 0 | 110 | 0 |
| docs/steady/project/industry-map.md | 72 | 0 | 65 | 7 |
| docs/steady/proofs/verify-v31.md | 120 | 1 | 120 | 0 |
| docs/steady/reports/ci-failures.md | 70 | 1 | 58 | 12 |
| docs/steady/reports/germany-control-2026-10-27.md | 25 | 0 | 25 | 0 |
| docs/steady/reports/guard-wire-oracle-2026-10-27.md | 24 | 3 | 24 | 0 |
| docs/steady/reports/live-2026-10-25-readme.md | 35 | 0 | 35 | 0 |
| docs/steady/reports/mutation.md | 59 | 0 | 58 | 1 |
| docs/steady/reports/release-blocked-windows.md | 87 | 1 | 87 | 0 |
| docs/steady/reports/v3.14.46-release-retrospective.md | 40 | 1 | 39 | 1 |
| docs/steady/reports/distill-dry-run.md | 35 | 1 | 34 | 1 |
| docs/steady/reports/review-2026-10-27.md | 15 | 1 | 15 | 0 |
| docs/steady/reports/tools-2026-10-27.md | 27 | 3 | 27 | 0 |
| docs/steady/security/hardening-readme.md | 18 | 0 | 18 | 0 |
| docs/steady/reports/v3.12.65-coverage.md | 54 | 2 | 54 | 0 |
| docs/steady/reports/v3.13.27-coverage-gaps.md | 51 | 1 | 51 | 0 |
| docs/steady/reports/v3.13.38-coverage-gaps.md | 25 | 1 | 24 | 1 |
| docs/steady/reports/v3.15.1-coverage.md | 65 | 2 | 65 | 0 |
| docs/steady/reports/v3.12.20-coverage.md | 373 | 16 | 373 | 0 |
| docs/steady/use/use-runbook.md | 220 | 8 | 219 | 1 |
| docs/steady/project/de_dust2.md | 215 | 2 | 162 | 53 |
| docs/infrastructure-documents/proofs/goals.md | 247 | 0 | 243 | 4 |
| docs/infrastructure-documents/proofs/constraints.md | 285 | 1 | 285 | 0 |
| docs/steady/project/contributing.md | 279 | 2 | 278 | 1 |
| docs/ietf/draft-slutsky-homing-pigeon-v2/submitted/draft-slutsky-homing-pigeon-v2-01.md | 239 | 4 | 239 | 0 |
| docs/ietf/draft-slutsky-homing-pigeon-v3/source/draft-slutsky-homing-pigeon-v3-00.md | 446 | 35 | 445 | 1 |
| docs/infrastructure-documents/proofs/shotgun-queue.md | 400 | 0 | 347 | 53 |
| docs/steady/reports/v3.13.29-coverage.md | 75 | 7 | 75 | 0 |
| docs/steady/reports/v3.13.8-coverage-gaps.md | 57 | 1 | 57 | 0 |
| docs/steady/reports/v3.13.42-coverage.md | 78 | 7 | 78 | 0 |
| docs/steady/reports/v3.7.30-coverage.md | 84 | 2 | 84 | 0 |
| docs/steady/use/handoff-local-si.md | 59 | 1 | 59 | 0 |
| docs/steady/use/local-si-test.md | 78 | 0 | 78 | 0 |
| docs/steady/security/security-test-plan.md | 179 | 4 | 177 | 2 |

## Remaining in this shard (in shard order)

docs/steady/emergency.md;
docs/infrastructure-documents/design/v1-v2-sentence-review.md;
docs/infrastructure-documents/design/v3-sentence-review.md;
docs/infrastructure-documents/oracle/configuring-oracle.md;
docs/infrastructure-documents/project/duplication-audit.md;
docs/infrastructure-documents/proofs/constraints.md;
docs/infrastructure-documents/proofs/content-rung-50000.md;
docs/infrastructure-documents/proofs/content-series-review.md;
docs/infrastructure-documents/proofs/content-sh-macos.md;
docs/infrastructure-documents/proofs/goals.md;
docs/infrastructure-documents/proofs/shotgun-queue.md;
docs/infrastructure-documents/proofs/stage2.md;
docs/infrastructure-documents/proofs/stage4-p3.md;
docs/infrastructure-documents/proofs/stage4-p6.md;
docs/infrastructure-documents/proofs/stage6-keys.md;
docs/infrastructure-documents/proofs/stage6-transports.md;
docs/infrastructure-documents/proofs/stage8-50000.md;
docs/infrastructure-documents/proofs/stage9.md;
docs/infrastructure-documents/security/model-and-proof-testing.md;
docs/infrastructure-documents/security/threat-model.md;
docs/steady/design/approval-gate-design.md;
docs/steady/design/extension-review-design.md;
docs/steady/oracle/dri-playbook.md;
docs/steady/project/contributing.md;
docs/steady/project/de_dust2.md;
docs/steady/project/industry-map.md;
docs/steady/proofs/verify-v31.md;
docs/steady/reports/ci-failures.md;
docs/steady/reports/distill-dry-run.md;
docs/steady/reports/germany-control-2026-10-27.md;
docs/steady/reports/guard-wire-oracle-2026-10-27.md;
docs/steady/reports/live-2026-10-25-readme.md;
docs/steady/reports/mutation.md;
docs/steady/reports/release-blocked-windows.md;
docs/steady/reports/review-2026-10-27.md;
docs/steady/reports/tools-2026-10-27.md;
docs/steady/reports/v3.12.20-coverage.md;
docs/steady/reports/v3.12.65-coverage.md;
docs/steady/reports/v3.13.27-coverage-gaps.md;
docs/steady/reports/v3.13.29-coverage.md;
docs/steady/reports/v3.13.38-coverage-gaps.md;
docs/steady/reports/v3.13.42-coverage.md;
docs/steady/reports/v3.13.8-coverage-gaps.md;
docs/steady/reports/v3.14.46-release-retrospective.md;
docs/steady/reports/v3.15.1-coverage.md;
docs/steady/reports/v3.7.30-coverage.md;
docs/steady/security/hardening-readme.md;
docs/steady/security/security-test-plan.md;
docs/steady/use/handoff-local-si.md;
docs/steady/use/local-si-test.md;
docs/steady/use/use-runbook.md;
docs/ietf/draft-slutsky-homing-pigeon-v2/submitted/draft-slutsky-homing-pigeon-v2-01.md;
docs/ietf/draft-slutsky-homing-pigeon-v3/source/draft-slutsky-homing-pigeon-v3-00.md;
docs/ietf/draft-slutsky-homing-pigeon/submitted/draft-slutsky-homing-pigeon-01.md.

## Stopped at

60 documents done, 6,431 units. Only 1 document remains:
the v1 submitted draft -01 (705 units).
