Claude:
10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
200003d4-e5f6-4a7b-9c8d-0e1f2a3b4c5d
30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
40000e00-1234-4abc-9def-0123456789ab
50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
60000b3a-32a6-4847-996f-638cbcb6d854

Muse:
58316a92-3c4a-41cb-8a16-8c0c5a871e90

## Status (2026-10-26)

<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->

The list above is the order the stamps were issued. Researchers one,
two and three have been **recycled**: their chats no longer work on
the project, and no new commit or file carries their stamps. Their
stamps stay in history and in the headers of the files they wrote,
as the record of who did what. Their roles are carried by the
remaining agents:

| # | Stamp | Status | Roles it held | Carried now by |
|---|-------|--------|---------------|----------------|
| 1 | `10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c` | recycled | the questions desk; Platforms (macOS and FreeBSD legs, the switch-proof roster); the live capture | the desk: `50000c8e`; Platforms and the capture: `40000e00` |
| 2 | `200003d4-e5f6-4a7b-9c8d-0e1f2a3b4c5d` | recycled | the release path in CI, the pipeline-health report, the extension upstream pins | the release path and the pins: `50000c8e`; the CI report: `40000e00` |
| 3 | `30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a` | recycled | the platform matrix, the portable proof, minimal-userland, the skip registry, the sandbox fixes | the matrix, proofs and registry: `40000e00`; the sandbox: `50000c8e` |
| 4 | `40000e00-1234-4abc-9def-0123456789ab` | active | the test legs and CI proofs (python-range, upgrade-proof, soak, hardware, campaign-replay, queues-worker), the property suites, the live capture | |
| 5 | `50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f` | active | the questions desk, production code, releases and the release train | |
| 6 | `60000b3a-32a6-4847-996f-638cbcb6d854` | active | docs and the roadmap (`docs/project/future.md`), extension sources | |
| Muse | `58316a92-3c4a-41cb-8a16-8c0c5a871e90` | active | the testing campaigns (tests, probes, questions) | |

`runner/tests/test_agent_stamps.py` holds this record to the tree.

