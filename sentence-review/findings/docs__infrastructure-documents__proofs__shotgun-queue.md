# Findings — docs/infrastructure-documents/proofs/shotgun-queue.md

Source: docs/infrastructure-documents/proofs/shotgun-queue.md, reviewed at main cbb52068.
Sentence units: 400. Flagged: 0. Categories: pre-release 347, post-release 53.

Each queue item is a block of field lines (Found, Fixed, Area, Existing tests, Target, Status, and its proof of work); the lines of an item are recorded in order. In the queued items at the end, the Target and Status lines are categorized post-release; their Found, Fixed, and Area lines record the bug and its fix.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Built 1-Nov-2026 from the git record on main…" | pre-release | flows |  |
| 2 | "Window: since 27-Oct-2026 00:00 PDT." | pre-release | flows |  |
| 3 | "Newest first." | pre-release | flows |  |
| 4 | "Rule (the shotgun standard): each bug gets a…" | pre-release | flows |  |
| 5 | "Status: queued / in progress / done." | pre-release | flows |  |
| 6 | "This file is the durable queue in the…" | pre-release | flows |  |
| 7 | "It was rebuilt and landed on main 2-Nov-2026;…" | pre-release | flows |  |
| 8 | "Excluded, not bugs: 31,394 corpus records retired 29–31…" | pre-release | flows |  |
| 9 | "Bank and release commits are transport, not findings." | pre-release | flows |  |
| 10 | "Applied to every item on this queue, item…" | pre-release | flows |  |
| 11 | "PER-FIELD UNIT TESTS." | pre-release | flows |  |
| 12 | "Wherever an item touches a fielded surface —…" | pre-release | flows |  |
| 13 | "One test per field, not one test per…" | pre-release | flows |  |
| 14 | "The enumeration counts toward the item's 50-test cap." | pre-release | flows |  |
| 15 | "PER-TEST FUZZ JOB." | pre-release | flows |  |
| 16 | "For each of those unit tests, a fuzz…" | pre-release | flows |  |
| 17 | "The fuzzing is executed, not just the static…" | pre-release | flows |  |
| 18 | "Where a full rig fuzz job is out…" | pre-release | flows |  |
| 19 | "WRITTEN PROOF IN THE REPO." | pre-release | flows |  |
| 20 | "The commit and the queue entry carry the…" | pre-release | flows |  |
| 21 | "The write-up documents the rigor of the work…" | pre-release | flows |  |
| 22 | "Fuzzing here is ordinary programming through combinatorics —…" | pre-release | flows |  |
| 23 | "BOOKENDS AND RUN LENGTHS (added 1-Nov-2026)." | pre-release | flows |  |
| 24 | "Every fuzz routine and every generated family wraps…" | pre-release | flows |  |
| 25 | "Repetition counts are part of the sweep: runs…" | pre-release | flows |  |
| 26 | "Found: 1-Nov-2026, Germany rig grow (race_state crash 9b26d146d86a0e08)" | pre-release | flows |  |
| 27 | "Fixed: 4d4bf568 (31-Oct-2026) — load_retained checks the directory…" | pre-release | flows |  |
| 28 | "Area: runner/runner.py load_retained / retained store" | pre-release | flows |  |
| 29 | "Existing tests: runner/tests/test_retained_store.py" | pre-release | flows |  |
| 30 | "Target: up to 50 new tests" | pre-release | flows |  |
| 31 | "Status: done — 50 new tests (LoadRetainedCaseShotgunTest in…" | pre-release | flows |  |
| 32 | "Landed on main 2-Nov-2026 (db8f7254, c2235b1d); the file…" | pre-release | flows |  |
| 33 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 34 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target race_state --rounds 400…" | pre-release | flows |  |
| 35 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 36 | "The grow's bookkeeping writes were not banked (banking…" | pre-release | flows |  |
| 37 | "The same write-up is carried in the test…" | pre-release | flows |  |
| 38 | "Found: 31-Oct-2026, Windows CI leg of 3.15.2" | pre-release | flows |  |
| 39 | "Fixed: 4d4bf568 (same commit, second half) — audit_entry_is_audit_only" | pre-release | flows |  |
| 40 | "Area: runner/tests/test_security_parity.py" | pre-release | flows |  |
| 41 | "Target: up to 50 new tests" | pre-release | flows |  |
| 42 | "Status: done — 50 new tests (AuditEntryShotgunTest in…" | pre-release | flows |  |
| 43 | "Landed on main 2-Nov-2026 (36460659, 8a36684a); the file…" | pre-release | flows |  |
| 44 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 45 | "Bookends: every string shape also gets bookended variants…" | pre-release | flows |  |
| 46 | "Run lengths: ten ordinary characters then the odd…" | pre-release | flows |  |
| 47 | "Fuzz executed: no de_dust target drives this test-harness…" | pre-release | flows |  |
| 48 | "The grows' bookkeeping writes were not banked (banking…" | pre-release | flows |  |
| 49 | "The same write-up is carried in the test…" | pre-release | flows |  |
| 50 | "Fixed: f97119aa (31-Oct-2026)" | pre-release | flows |  |
| 51 | "Area: result delivery / target file naming" | pre-release | flows |  |
| 52 | "Existing tests: the result-lifecycle tests (test_transport_queues.py, test_transport_shells.py)" | pre-release | flows |  |
| 53 | "Target: up to 50 new tests" | pre-release | flows |  |
| 54 | "Status: done — 50 new tests (SecondResultTargetShotgunTest in…" | pre-release | flows |  |
| 55 | "Landed on main 2-Nov-2026 (39438977); the file runs…" | pre-release | flows |  |
| 56 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 57 | "Bookends and run lengths per the method section,…" | pre-release | flows |  |
| 58 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target stash --rounds 400…" | pre-release | flows |  |
| 59 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 60 | "The grow's bookkeeping writes were not banked (banking…" | pre-release | flows |  |
| 61 | "The same write-up is carried in the test…" | pre-release | flows |  |
| 62 | "Fixed: e4c21957 (31-Oct-2026)" | pre-release | flows |  |
| 63 | "Existing tests: test_transport_shells.py (35 in file)" | pre-release | flows |  |
| 64 | "Target: up to 50 new tests" | pre-release | flows |  |
| 65 | "Status: done — 50 new tests (FilePipeHeldResultShotgunTest in…" | pre-release | flows |  |
| 66 | "Landed on main 2-Nov-2026 (13075bc1); the file runs…" | pre-release | flows |  |
| 67 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 68 | "Bookends: every printable ASCII symbol at the front…" | pre-release | flows |  |
| 69 | "Run lengths: stems and suffix digit runs of…" | pre-release | flows |  |
| 70 | "Injection-shaped names are ordinary names." | pre-release | flows |  |
| 71 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target channels --rounds 400…" | pre-release | flows |  |
| 72 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 73 | "The grow's bookkeeping writes were reverted, not banked…" | pre-release | flows |  |
| 74 | "The same write-up is carried in the test…" | pre-release | flows |  |
| 75 | "Fixed: 2715bedc (31-Oct-2026)" | pre-release | flows |  |
| 76 | "Existing tests: test_platinum_runner.py" | pre-release | flows |  |
| 77 | "Target: up to 50 new tests" | pre-release | flows |  |
| 78 | "Status: done — 50 new tests (RefusedNoRecordShotgunTest in…" | pre-release | flows |  |
| 79 | "Landed on main 2-Nov-2026 (85b00a6b); the file runs…" | pre-release | flows |  |
| 80 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 81 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target race_stash --rounds 400…" | pre-release | flows |  |
| 82 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 83 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 84 | "Fixed: 4203d661 (31-Oct-2026)" | pre-release | flows |  |
| 85 | "Existing tests: test_transport_queues.py (39 in file)" | pre-release | flows |  |
| 86 | "Target: up to 50 new tests" | pre-release | flows |  |
| 87 | "Status: done — 50 new tests (UnreadableResultShotgunTest in…" | pre-release | flows |  |
| 88 | "Landed on main 2-Nov-2026 (8ba79990; authored in a…" | pre-release | flows |  |
| 89 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 90 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target stash --rounds 400…" | pre-release | flows |  |
| 91 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 92 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 93 | "Fixed: ab721ef9 (31-Oct-2026)" | pre-release | flows |  |
| 94 | "Existing tests: test_transport_queues.py" | pre-release | flows |  |
| 95 | "Target: up to 50 new tests" | pre-release | flows |  |
| 96 | "Status: done — 50 new tests (SymlinkResultShotgunTest in…" | pre-release | flows |  |
| 97 | "Landed on main 2-Nov-2026 (7159cf8e); the file runs…" | pre-release | flows |  |
| 98 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 99 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target race_stash --rounds 400…" | pre-release | flows |  |
| 100 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 101 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 102 | "Fixed: 6ed7281e (31-Oct-2026)" | pre-release | flows |  |
| 103 | "Existing tests: test_email_pipe_coverage.py" | pre-release | flows |  |
| 104 | "Target: up to 50 new tests" | pre-release | flows |  |
| 105 | "Status: done — 50 new tests (UnbuildableResultShotgunTest in…" | pre-release | flows |  |
| 106 | "Landed on main 2-Nov-2026 (77edd0ec); the file runs…" | pre-release | flows |  |
| 107 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 108 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target mail --rounds 400…" | pre-release | flows |  |
| 109 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 110 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 111 | "Fixed: 81ef9ee5 (31-Oct-2026)" | pre-release | flows |  |
| 112 | "Existing tests: test_dtls.py" | pre-release | flows |  |
| 113 | "Target: up to 50 new tests" | pre-release | flows |  |
| 114 | "Status: done — 50 new tests (DtlsResultStaysShotgunTest in…" | pre-release | flows |  |
| 115 | "Landed on main 2-Nov-2026 (a11ce8d5); the file runs…" | pre-release | flows |  |
| 116 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 117 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target dtls --rounds 400…" | pre-release | flows |  |
| 118 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 119 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 120 | "Fixed: a3cec2fc (31-Oct-2026)" | pre-release | flows |  |
| 121 | "Existing tests: test_transports.py" | pre-release | flows |  |
| 122 | "Target: up to 50 new tests" | pre-release | flows |  |
| 123 | "Status: done — 50 new tests (NatsPublishAckShotgunTest in…" | pre-release | flows |  |
| 124 | "Landed on main 2-Nov-2026 (157e5d0c); the file runs…" | pre-release | flows |  |
| 125 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 126 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target channels --rounds 400…" | pre-release | flows |  |
| 127 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 128 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 129 | "Fixed: bfb3a790 (31-Oct-2026)" | pre-release | flows |  |
| 130 | "Existing tests: test_transport_queues.py" | pre-release | flows |  |
| 131 | "Target: up to 50 new tests" | pre-release | flows |  |
| 132 | "Status: done — 50 new tests (StaleResultDoesNotAckShotgunTest in…" | pre-release | flows |  |
| 133 | "Landed on main 2-Nov-2026 (c2dbd567; authored in a…" | pre-release | flows |  |
| 134 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 135 | "Fuzz executed: the queue's named target for this…" | pre-release | flows |  |
| 136 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 137 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 138 | "Follow-up finding (2-Nov-2026, from this item's family work;…" | pre-release | flows |  |
| 139 | "When a noted stale file leaves the outbox…" | pre-release | flows |  |
| 140 | "Verified first-hand against main (480e0667) with a probe…" | pre-release | flows |  |
| 141 | "Two bounds on the blast radius, also verified:…" | pre-release | flows |  |
| 142 | "The fix shape, for a later pass: discard…" | pre-release | flows |  |
| 143 | "No production code was changed by this queue…" | pre-release | flows |  |
| 144 | "Fixed: 9d8493c3 (31-Oct-2026)" | pre-release | flows |  |
| 145 | "Existing tests: test_platinum_runner.py" | pre-release | flows |  |
| 146 | "Target: up to 50 new tests" | pre-release | flows |  |
| 147 | "Status: done — 50 new tests (UnreadableRefusalNameShotgunTest in…" | pre-release | flows |  |
| 148 | "Deliberately distinct from item 5's family in the…" | pre-release | flows |  |
| 149 | "Landed on main 2-Nov-2026 (c4b82b47); the file runs…" | pre-release | flows |  |
| 150 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 151 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target stash --rounds 400…" | pre-release | flows |  |
| 152 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 153 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 154 | "Fixed: bfb230cf (31-Oct-2026)" | pre-release | flows |  |
| 155 | "Existing tests: test_delivery_edges.py" | pre-release | flows |  |
| 156 | "Target: up to 50 new tests" | pre-release | flows |  |
| 157 | "Status: done — 50 new tests (WindowsPinsNoRecordShotgunTest in…" | pre-release | flows |  |
| 158 | "Landed on main 2-Nov-2026 (feac1460); the file runs…" | pre-release | flows |  |
| 159 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 160 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target channels --rounds 400…" | pre-release | flows |  |
| 161 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 162 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 163 | "Fixed: ee1fe83f (31-Oct-2026)" | pre-release | flows |  |
| 164 | "Existing tests: test_dtls.py, test_email_pipe_coverage.py, test_transport_shells.py (added by the…" | pre-release | flows |  |
| 165 | "Target: up to 50 new tests" | pre-release | flows |  |
| 166 | "Status: done — 50 new tests (SuffixedResultStillThatJobShotgunTest in…" | pre-release | flows |  |
| 167 | "Landed on main 2-Nov-2026 (8edf607d); the file runs…" | pre-release | flows |  |
| 168 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 169 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target dtls --rounds 400…" | pre-release | flows |  |
| 170 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 171 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 172 | "Fixed: 929fce3f (31-Oct-2026)" | pre-release | flows |  |
| 173 | "Existing tests: queues-worker worker.test.mjs, test_queue_weather.py" | pre-release | flows |  |
| 174 | "Target: up to 50 new tests" | pre-release | flows |  |
| 175 | "Status: done — 50 new tests (the shotgun15…" | pre-release | flows |  |
| 176 | "Landed on main 2-Nov-2026 (591a1b3d); the file runs…" | pre-release | flows |  |
| 177 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 178 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target channels --rounds 400…" | pre-release | flows |  |
| 179 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 180 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 181 | "Fixed: 694dc82a (31-Oct-2026)" | pre-release | flows |  |
| 182 | "Existing tests: queues-worker fatfinger.test.mjs, test_transport_queues.py" | pre-release | flows |  |
| 183 | "Target: up to 50 new tests" | pre-release | flows |  |
| 184 | "Status: done — 50 new tests (the shotgun16…" | pre-release | flows |  |
| 185 | "Landed on main 2-Nov-2026 (3d7082d2); the file runs…" | pre-release | flows |  |
| 186 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 187 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target channels --rounds 400…" | pre-release | flows |  |
| 188 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 189 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 190 | "Fixed: accf7b95 (31-Oct-2026)" | pre-release | flows |  |
| 191 | "Existing tests: test_transport_queues.py, test_transport_shells.py" | pre-release | flows |  |
| 192 | "Target: up to 50 new tests" | pre-release | flows |  |
| 193 | "Status: done — 50 new tests (UnreadableContentResultShotgunTest in…" | pre-release | flows |  |
| 194 | "Landed on main 2-Nov-2026 (2467787f); the file runs…" | pre-release | flows |  |
| 195 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 196 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target stash --rounds 400…" | pre-release | flows |  |
| 197 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 198 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 199 | "Fixed: 4931ec16 (31-Oct-2026)" | pre-release | flows |  |
| 200 | "Existing tests: test_result_size.py, test_transport_queues.py" | pre-release | flows |  |
| 201 | "Target: up to 50 new tests" | pre-release | flows |  |
| 202 | "Status: done — 50 new tests (RefusedCollisionSetAsideShotgunTest in…" | pre-release | flows |  |
| 203 | "Landed on main 2-Nov-2026 (29ead251); the file runs…" | pre-release | flows |  |
| 204 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 205 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target race_stash --rounds 400…" | pre-release | flows |  |
| 206 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 207 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 208 | "Fixed: dc4b7a70 (31-Oct-2026)" | pre-release | flows |  |
| 209 | "Existing tests: test_transport_queues.py" | pre-release | flows |  |
| 210 | "Target: up to 50 new tests" | pre-release | flows |  |
| 211 | "Status: done — 50 new tests (LoopbackRedirectShotgunTest in…" | pre-release | flows |  |
| 212 | "Landed on main 2-Nov-2026 (e6f610cb); the file runs…" | pre-release | flows |  |
| 213 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 214 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target wire --rounds 400…" | pre-release | flows |  |
| 215 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 216 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 217 | "Fixed: fe4ec56c (31-Oct-2026)" | pre-release | flows |  |
| 218 | "Existing tests: test_queue_pipe_edges.py, test_transport_queues.py" | pre-release | flows |  |
| 219 | "Target: up to 50 new tests" | pre-release | flows |  |
| 220 | "Status: done — 50 new tests (RefusedAckShotgunTest in…" | pre-release | flows |  |
| 221 | "Landed on main 2-Nov-2026 (spliced beside items 21,…" | pre-release | flows |  |
| 222 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 223 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target channels --rounds 400…" | pre-release | flows |  |
| 224 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 225 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 226 | "Fixed: 2f6502f2 (31-Oct-2026)" | pre-release | flows |  |
| 227 | "Existing tests: test_transport_queues.py" | pre-release | flows |  |
| 228 | "Target: up to 50 new tests" | pre-release | flows |  |
| 229 | "Status: done — 50 new tests (LongIdCollisionShotgunTest in…" | pre-release | flows |  |
| 230 | "Landed on main 2-Nov-2026 (334a43cb); the file runs…" | pre-release | flows |  |
| 231 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 232 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target names --rounds 400…" | pre-release | flows |  |
| 233 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 234 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 235 | "Fixed: 4922aa37 (31-Oct-2026)" | pre-release | flows |  |
| 236 | "Existing tests: test_transport_queues.py" | pre-release | flows |  |
| 237 | "Target: up to 50 new tests" | pre-release | flows |  |
| 238 | "Status: done — 50 new tests (OversizedResultShotgunTest in…" | pre-release | flows |  |
| 239 | "Distinct from item 18's set-aside naming pins." | pre-release | flows |  |
| 240 | "Landed on main 2-Nov-2026 (spliced beside items 20,…" | pre-release | flows |  |
| 241 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 242 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target stash --rounds 400…" | pre-release | flows |  |
| 243 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 244 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 245 | "Fixed: 9be8c1a6 (31-Oct-2026)" | pre-release | flows |  |
| 246 | "Existing tests: test_transport_queues.py, test_transport_shells.py" | pre-release | flows |  |
| 247 | "Target: up to 50 new tests" | pre-release | flows |  |
| 248 | "Status: done — 50 new tests (QueueNeverTakesResultShotgunTest in…" | pre-release | flows |  |
| 249 | "One behavior pinned as current, noted in the…" | pre-release | flows |  |
| 250 | "Landed on main 2-Nov-2026 (spliced beside items 20,…" | pre-release | flows |  |
| 251 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 252 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target race_stash --rounds 400…" | pre-release | flows |  |
| 253 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 254 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 255 | "Fixed: 2c0f4d5d (31-Oct-2026)" | pre-release | flows |  |
| 256 | "Existing tests: queues-worker fuzz.test.mjs, test_transport_queues.py" | pre-release | flows |  |
| 257 | "Target: up to 50 new tests" | pre-release | flows |  |
| 258 | "Status: done — 50 new tests (DifferentResultStoredShotgunTest in…" | pre-release | flows |  |
| 259 | "Landed on main 2-Nov-2026 (spliced beside items 20,…" | pre-release | flows |  |
| 260 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 261 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target channels --rounds 400…" | pre-release | flows |  |
| 262 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 263 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 264 | "Fixed: 9565d89f (31-Oct-2026)" | pre-release | flows |  |
| 265 | "Existing tests: queues-worker fuzz.test.mjs" | pre-release | flows |  |
| 266 | "Target: up to 50 new tests" | pre-release | flows |  |
| 267 | "Status: done — 50 new tests (the shotgun25…" | pre-release | flows |  |
| 268 | "Landed on main 2-Nov-2026 (6911c265); the file runs…" | pre-release | flows |  |
| 269 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 270 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target wire --rounds 400…" | pre-release | flows |  |
| 271 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 272 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 273 | "Fixed: 90ca98f3 (31-Oct-2026)" | pre-release | flows |  |
| 274 | "Existing tests: queues-worker fuzz.test.mjs" | pre-release | flows |  |
| 275 | "Target: up to 50 new tests" | pre-release | flows |  |
| 276 | "Status: done — 50 new tests (the shotgun26…" | pre-release | flows |  |
| 277 | "Landed on main 2-Nov-2026 (spliced after item 25's…" | pre-release | flows |  |
| 278 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 279 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target collect --rounds 400…" | pre-release | flows |  |
| 280 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 281 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 282 | "Fixed: cf591bb4 (31-Oct-2026)" | pre-release | flows |  |
| 283 | "Existing tests: test_transport_queues.py" | pre-release | flows |  |
| 284 | "Target: up to 50 new tests" | pre-release | flows |  |
| 285 | "Status: done — 50 new tests (SecondResultFileReplacementShotgunTest in…" | pre-release | flows |  |
| 286 | "Deliberately distinct from items 3, 11 and 23…" | pre-release | flows |  |
| 287 | "Landed on main 2-Nov-2026 (spliced beside items 20…" | pre-release | flows |  |
| 288 | "Proof of work (per the method section): per-field…" | pre-release | flows |  |
| 289 | "Fuzz executed: runner/tools/de_dust_corpus.py grow --target stash --rounds 400…" | pre-release | flows |  |
| 290 | "Result: 400 rounds, 0 crashes, 0 slow, arcs…" | pre-release | flows |  |
| 291 | "The grow's bookkeeping writes were reverted and are…" | pre-release | flows |  |
| 292 | "Fixed: 29001ad3, 66329844, 4635a1db (31-Oct-2026)" | pre-release | flows |  |
| 293 | "Existing tests: queues-worker tests" | pre-release | flows |  |
| 294 | "Target: up to 50 new tests" | pre-release | flows |  |
| 295 | "Status: queued" | post-release | flows |  |
| 296 | "Fixed: b2795848 (31-Oct-2026)" | pre-release | flows |  |
| 297 | "Existing tests: queues-worker fatfinger/fuzz tests, test_hosting_queue_edges.py" | pre-release | flows |  |
| 298 | "Target: up to 50 new tests" | post-release | flows |  |
| 299 | "Status: queued" | post-release | flows |  |
| 300 | "Fixed: 8c5ae5cf (31-Oct-2026)" | pre-release | flows |  |
| 301 | "Existing tests: queues-worker fatfinger.test.mjs" | pre-release | flows |  |
| 302 | "Target: up to 50 new tests" | post-release | flows |  |
| 303 | "Status: queued" | post-release | flows |  |
| 304 | "Fixed: fbc3d845 (31-Oct-2026)" | pre-release | flows |  |
| 305 | "Existing tests: queues-worker fatfinger.test.mjs" | pre-release | flows |  |
| 306 | "Target: up to 50 new tests" | post-release | flows |  |
| 307 | "Status: queued" | post-release | flows |  |
| 308 | "Fixed: 344c7df9 (31-Oct-2026)" | pre-release | flows |  |
| 309 | "Existing tests: test_transport_queues.py" | pre-release | flows |  |
| 310 | "Target: up to 50 new tests" | post-release | flows |  |
| 311 | "Status: queued" | post-release | flows |  |
| 312 | "Fixed: 4cca4cc6 (31-Oct-2026)" | pre-release | flows |  |
| 313 | "Existing tests: queues-worker fatfinger.test.mjs, test_transport_queues.py" | pre-release | flows |  |
| 314 | "Target: up to 50 new tests" | post-release | flows |  |
| 315 | "Status: queued" | post-release | flows |  |
| 316 | "Fixed: ab002020 (31-Oct-2026)" | pre-release | flows |  |
| 317 | "Existing tests: queues-worker fuzz.test.mjs" | pre-release | flows |  |
| 318 | "Target: up to 50 new tests" | post-release | flows |  |
| 319 | "Status: queued" | post-release | flows |  |
| 320 | "Fixed: 53e3f33a (31-Oct-2026)" | pre-release | flows |  |
| 321 | "Existing tests: queues-worker fuzz.test.mjs" | pre-release | flows |  |
| 322 | "Target: up to 50 new tests" | post-release | flows |  |
| 323 | "Status: queued" | post-release | flows |  |
| 324 | "Fixed: 9716fb5d (31-Oct-2026)" | pre-release | flows |  |
| 325 | "Existing tests: queues-worker fuzz.test.mjs" | pre-release | flows |  |
| 326 | "Target: up to 50 new tests" | post-release | flows |  |
| 327 | "Status: queued" | post-release | flows |  |
| 328 | "Fixed: 355ab824 (31-Oct-2026)" | pre-release | flows |  |
| 329 | "Existing tests: queues-worker fuzz.test.mjs" | pre-release | flows |  |
| 330 | "Target: up to 50 new tests" | post-release | flows |  |
| 331 | "Status: queued" | post-release | flows |  |
| 332 | "Fixed: 3f3c16b9 (31-Oct-2026)" | pre-release | flows |  |
| 333 | "Existing tests: queues-worker fuzz.test.mjs" | pre-release | flows |  |
| 334 | "Target: up to 50 new tests" | post-release | flows |  |
| 335 | "Status: queued" | post-release | flows |  |
| 336 | "Fixed: 965e4d82, 3dfbd878 (31-Oct-2026)" | pre-release | flows |  |
| 337 | "Existing tests: queues-worker fuzz.test.mjs, worker.test.mjs" | pre-release | flows |  |
| 338 | "Target: up to 50 new tests" | post-release | flows |  |
| 339 | "Status: queued" | post-release | flows |  |
| 340 | "Fixed: 220d6324, a71acd3d (31-Oct-2026)" | pre-release | flows |  |
| 341 | "Existing tests: queues-worker fuzz.test.mjs" | pre-release | flows |  |
| 342 | "Target: up to 50 new tests" | post-release | flows |  |
| 343 | "Status: queued" | post-release | flows |  |
| 344 | "Fixed: bc4cb3d8 (31-Oct-2026)" | pre-release | flows |  |
| 345 | "Existing tests: de_dust board_mail corpus; board tests" | pre-release | flows |  |
| 346 | "Target: up to 50 new tests" | post-release | flows |  |
| 347 | "Status: queued" | post-release | flows |  |
| 348 | "Found: 31-Oct-2026, live on the Germany rig (file…" | pre-release | flows |  |
| 349 | "Fixed: 8174b51f (31-Oct-2026) — the gate routes through…" | pre-release | flows |  |
| 350 | "Existing tests: test_windows_platform_proofs.py MailboxGate tests (9 of the…" | pre-release | flows |  |
| 351 | "Target: up to 50 new tests" | post-release | flows |  |
| 352 | "Status: queued" | post-release | flows |  |
| 353 | "Found: 31-Oct-2026, live on the Germany rig" | pre-release | flows |  |
| 354 | "Fixed: 8174b51f — enforce refuses at startup on…" | pre-release | flows |  |
| 355 | "Existing tests: test_windows_platform_proofs.py JobUser tests (10 of the…" | pre-release | flows |  |
| 356 | "Target: up to 50 new tests" | post-release | flows |  |
| 357 | "Status: queued" | post-release | flows |  |
| 358 | "Fixed: d27e7e63 (30-Oct-2026)" | pre-release | flows |  |
| 359 | "Area: DTLS session handling in the corpus reader" | pre-release | flows |  |
| 360 | "Target: up to 50 new tests" | post-release | flows |  |
| 361 | "Status: queued" | post-release | flows |  |
| 362 | "Fixed: 5b068aff (30-Oct-2026)" | pre-release | flows |  |
| 363 | "Existing tests: test_de_dust2.py" | pre-release | flows |  |
| 364 | "Target: up to 50 new tests" | post-release | flows |  |
| 365 | "Status: queued" | post-release | flows |  |
| 366 | "Found: f19bc40e (29-Oct-2026); fixed: 30119441 (29-Oct-2026)" | pre-release | flows |  |
| 367 | "Area: runner/cloud/send_job.py keydir handling" | pre-release | flows |  |
| 368 | "Target: up to 50 new tests" | post-release | flows |  |
| 369 | "Status: queued" | post-release | flows |  |
| 370 | "Found: f19bc40e (29-Oct-2026); fixed: a1bbaeaf (29-Oct-2026), records retired…" | pre-release | flows |  |
| 371 | "Target: up to 50 new tests" | post-release | flows |  |
| 372 | "Status: queued" | post-release | flows |  |
| 373 | "Fixed: 4c93d140 (29-Oct-2026)" | pre-release | flows |  |
| 374 | "Area: cloud result addressing / provenance" | pre-release | flows |  |
| 375 | "Target: up to 50 new tests" | post-release | flows |  |
| 376 | "Status: queued" | post-release | flows |  |
| 377 | "Fixed: 1fa6d626 (27-Oct-2026)" | pre-release | flows |  |
| 378 | "Area: runner/cloud/send_job.py, runner/ops/exec.py" | pre-release | flows |  |
| 379 | "Target: up to 50 new tests" | post-release | flows |  |
| 380 | "Status: queued" | post-release | flows |  |
| 381 | "Fixed: c4df30c7 (27-Oct-2026)" | pre-release | flows |  |
| 382 | "Existing tests: test_queue_weather.py" | pre-release | flows |  |
| 383 | "Target: up to 50 new tests" | post-release | flows |  |
| 384 | "Status: queued" | post-release | flows |  |
| 385 | "Fixed: eff6a7ae, 369eafd9, 862669f2 (27-Oct-2026)" | pre-release | flows |  |
| 386 | "Area: runner/ops/poll.py, mail.py, handlers.py, startup.py" | pre-release | flows |  |
| 387 | "Target: up to 50 new tests" | post-release | flows |  |
| 388 | "Status: queued" | post-release | flows |  |
| 389 | "Fixed: f02356a2, 8d9e9102 (27-Oct-2026)" | pre-release | flows |  |
| 390 | "Area: runner/ops/queries.py and the doors" | pre-release | flows |  |
| 391 | "Target: up to 50 new tests" | post-release | flows |  |
| 392 | "Status: queued" | post-release | flows |  |
| 393 | "Filed: 27-Oct-2026 morning; closed inside the Oct 27…" | pre-release | flows |  |
| 394 | "Verify the exact fix commits on pickup before…" | pre-release | flows |  |
| 395 | "Target: up to 50 new tests" | post-release | flows |  |
| 396 | "Status: queued (verify first)" | post-release | flows |  |
| 397 | "Fixed: 33547a42 (27-Oct-2026) — harness defect found by…" | pre-release | flows |  |
| 398 | "Existing tests: test_de_dust_corpus.py" | pre-release | flows |  |
| 399 | "Target: up to 50 new tests" | post-release | flows |  |
| 400 | "Status: queued" | post-release | flows |  |
