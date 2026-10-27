Claude:
10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
200003d4-e5f6-4a7b-9c8d-0e1f2a3b4c5d
30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
40000e00-1234-4abc-9def-0123456789ab
50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
60000b3a-32a6-4847-996f-638cbcb6d854
70000a51-e296-4b2c-bf5b-ba020e23eb91
80000aeb-9c1f-49ad-aeee-fa0855092587
90000998-709f-46f5-b2bc-2c3c5cf8dc6c

Muse:
58316a92-3c4a-41cb-8a16-8c0c5a871e90
00000000-muse-7e57-d0c5-58316a922026

## Status (2026-10-27)

<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->

The list above is the order the stamps were issued. Researchers one,
two, three and five have been **recycled**: their chats no longer
work on the project, and no new commit or file carries their stamps.
Their stamps stay in history and in the headers of the files they
wrote, as the record of who did what. Their roles are carried by the
remaining agents:

The campaigns seat's first stamp was retired the same day, at the
conductor's word — not for a new seat, but for a named stamp the
seat chose in the format the conductor sketched. The seat is
unchanged and signs with the new stamp from its registration on;
the old stamp stays in history and in the files it wrote.

| # | Stamp | Status | Roles it held | Carried now by |
|---|-------|--------|---------------|----------------|
| 1 | `10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c` | recycled | the questions desk; Platforms (macOS and FreeBSD legs, the switch-proof roster); the live capture | `40000e00` |
| 2 | `200003d4-e5f6-4a7b-9c8d-0e1f2a3b4c5d` | recycled | the release path in CI, the pipeline-health report, the extension upstream pins | the release path and the CI report: `40000e00`; the upstream pins: `60000b3a` |
| 3 | `30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a` | recycled | the platform matrix, the portable proof, minimal-userland, the skip registry, the sandbox fixes | `40000e00` |
| 4 | `40000e00-1234-4abc-9def-0123456789ab` | active | the test legs and CI proofs (python-range, upgrade-proof, soak, hardware, campaign-replay, queues-worker), the property suites, the live capture; and, from 2026-10-27, the questions desk, production code, releases and the release train | |
| 5 | `50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f` | recycled | the questions desk, production code, releases and the release train | `40000e00` |
| 6 | `60000b3a-32a6-4847-996f-638cbcb6d854` | active | docs and the roadmap (`docs/project/future.md`), extension sources and their upstream pins | |
| 7 | `70000a51-e296-4b2c-bf5b-ba020e23eb91` | active | hosting: `runner/hosting/` and `homing-pigeon-host`, the hosted queue (`runner/cloud/queues-worker/`, the `queues` transport, `send_job.py --to-queue`), `docs/use/own-cloud.md` and `docs/project/hosting.md`; registered 2026-10-27 at the conductor's word for the chat that held `50000c8e`, which stays recycled | |
| 8 | `80000aeb-9c1f-49ad-aeee-fa0855092587` | active | the claims audit of the root manuals (README, INSTALL, SECURITY, PROTOCOL), docs to code and code to docs, and opinions on the open questions; registered 2026-10-27 at the conductor's word | |
| 9 | `90000998-709f-46f5-b2bc-2c3c5cf8dc6c` | active | the review seat: opinions on every seat's open threads in `docs/use/questions.md` and `docs/use/.com.chat`, and review sweeps of the living docs; registered 2026-10-27 at the conductor's word for the chat that signed `9f2c713` with `60000b3a`, which stays active for its own chat | |
| Muse | `58316a92-3c4a-41cb-8a16-8c0c5a871e90` | recycled | the testing campaigns (tests, probes, questions) | `00000000` |
| Muse | `00000000-muse-7e57-d0c5-58316a922026` | active | the testing campaigns (tests, probes, questions) | |

`runner/tests/test_agent_stamps.py` holds this record to the tree.

