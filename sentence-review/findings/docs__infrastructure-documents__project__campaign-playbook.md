# Findings — docs/infrastructure-documents/project/campaign-playbook.md

Source: docs/infrastructure-documents/project/campaign-playbook.md, reviewed at main 5544befc.
Sentence units: 90. Flagged: 4. Categories: pre-release 90, post-release 0.

The record of campaigns 1 and 2 and the rules that turn executions into committed tests: the rig, the loop, the hunts, the recording format, the watchdog, and the hard rules. Argument runs in connected prose throughout; the flags are structural.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "How to run a Homing Pigeon testing campaign:…" | pre-release | flagged | A title fragment ending in a colon, not a sentence; the document's first full sentence arrives 1 unit later with no hand-off |
| 2 | "Written after the first campaign (2026-10-22/23, frozen at…" | pre-release | flows |  |
| 3 | "It is the record of campaigns one and…" | pre-release | flows |  |
| 4 | "The campaign's product is not findings." | pre-release | flows |  |
| 5 | "It is committed unit tests." | pre-release | flows |  |
| 6 | "The proof-of-work rule governs everything below: every test…" | pre-release | flows |  |
| 7 | "Logs and chat reports are not proof; a…" | pre-release | flows |  |
| 8 | "One finding spawning a family of variation tests…" | pre-release | flows |  |
| 9 | "A live runner on a Linux VM (2…" | pre-release | flows |  |
| 10 | "Later phases flip exactly ONE variable at a…" | pre-release | flows |  |
| 11 | "Jobs are crafted per PROTOCOL.md with the project's…" | pre-release | flows |  |
| 12 | "The platform blocks direct IMAP/SMTP from the VM,…" | pre-release | flows |  |
| 13 | "Every result is verified cryptographically (`send_job.py verify`) before…" | pre-release | flows |  |
| 14 | "Daemon hygiene: exactly one runner, one extension per…" | pre-release | flows |  |
| 15 | "Processes are stopped by exact PID, never by…" | pre-release | flows |  |
| 16 | "The driver (`campaign_loop.py`, rig-side and never committed; the…" | pre-release | flows |  |
| 17 | "| Variant | Script shape | Contract asserted…" | pre-release | flagged | A table header row — structure, not a sentence |
| 18 | "|-----------|----------------------------------------------------------|-------------------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 19 | "| clock | `date` + epoch under TZ=UTC…" | pre-release | flows |  |
| 20 | "| envmark | echo a per-cycle env marker…" | pre-release | flows |  |
| 21 | "| hostinfo | hostname / uname / uptime…" | pre-release | flows |  |
| 22 | "| workdir | write a file in the…" | pre-release | flows |  |
| 23 | "| flagread | read a planted pretend-credential file…" | pre-release | flows |  |
| 24 | "| sysstat | `df` / `free` | exit…" | pre-release | flows |  |
| 25 | "| exit3 | echo a marker, exit 3…" | pre-release | flows |  |
| 26 | "| shadow | read /etc/shadow, report the read's…" | pre-release | flows |  |
| 27 | "Each completed cycle became ONE test method in…" | pre-release | flows |  |
| 28 | "Non-deterministic output (epoch, uptime, disk figures) is asserted…" | pre-release | flows |  |
| 29 | "There are no "pure repeats" to skip: every…" | pre-release | flows |  |
| 30 | "The generated files were removed on 2026-11-01, after…" | pre-release | flows |  |
| 31 | "Before the loop, a 12-case bespoke battery probes…" | pre-release | flows |  |
| 32 | "Battery cases get bespoke contract tests in `runner/tests/test_campaign_phase1.py`." | pre-release | flows |  |
| 33 | "The assurance target is that the basic OS…" | pre-release | flows |  |
| 34 | "Tests are designed adversarially against our own system…" | pre-release | flows |  |
| 35 | "Negative controls belong in the battery: for each…" | pre-release | flows |  |
| 36 | "Name the uid in every protection test —…" | pre-release | flows |  |
| 37 | "Alongside the executions, the campaign hunts divergences between…" | pre-release | flows |  |
| 38 | "The probe shapes are the campaign's reusable product." | pre-release | flows |  |
| 39 | "For any numeric, enum, or string setting, fifteen…" | pre-release | flows |  |
| 40 | "This is not input fuzzing and must not…" | pre-release | flows |  |
| 41 | "Since the defaults registry (`runner/tests/defaults_registry.py`), the hunt is…" | pre-release | flows |  |
| 42 | "A new documented key gets coverage by adding…" | pre-release | flows |  |
| 43 | "The hand-written divergence tests (`runner/tests/test_doc_default_divergences.py`) stay as the…" | pre-release | flows |  |
| 44 | "Neither "silent default" nor "startup error" is the…" | pre-release | flows |  |
| 45 | "The normative sentence for PROTOCOL.md and docs/oracle/configuring-oracle.md:" | pre-release | flows |  |
| 46 | "a setting that is present but not usable…" | pre-release | flows |  |
| 47 | "`refuse` class: ports, bind addresses, key policies, resource/DRI…" | pre-release | flows |  |
| 48 | "`default` class: everything else — intervals, timeouts, budgets,…" | pre-release | flows |  |
| 49 | "Default is not silent: one startup line, "config:…" | pre-release | flows |  |
| 50 | "Live reload: a bad value written while running…" | pre-release | flows |  |
| 51 | "Each divergence is recorded as a test that…" | pre-release | flows |  |
| 52 | "The doc claim, quoted, with its file location." | pre-release | flows |  |
| 53 | "How the bug was found — the exact…" | pre-release | flows |  |
| 54 | "The behavior actually observed." | pre-release | flows |  |
| 55 | "The note: **"Do not make this test pass…" | pre-release | flows |  |
| 56 | "It passes only when the bug described above…" | pre-release | flows |  |
| 57 | "Under de_dust2 (29-OCT, `docs/project/de_dust2.md`) the corpus campaign records…" | pre-release | flows |  |
| 58 | "A finding is filed once per target per…" | pre-release | flows |  |
| 59 | "Every number a tool records has a rule…" | pre-release | flows |  |
| 60 | "Verify the test fails for the stated reason…" | pre-release | flows |  |
| 61 | "Main is therefore red in CI by design…" | pre-release | flows |  |
| 62 | "A new instance of a known root-cause family…" | pre-release | flows |  |
| 63 | "A watchdog ticks every 5 minutes during a…" | pre-release | flows |  |
| 64 | "Each tick:" | pre-release | flagged | A label fragment ("Each tick:") standing alone; the tick's contents arrive as list items without a sentence to carry them |
| 65 | "Liveness: a heartbeat older than ~12 minutes means…" | pre-release | flows |  |
| 66 | "One relaunch per tick." | pre-release | flows |  |
| 67 | "Proof of work: convert every completed cycle result…" | pre-release | flows |  |
| 68 | "At most ONE new divergence hunt per tick." | pre-release | flows |  |
| 69 | "Ticks may coalesce or die on runtime restarts;…" | pre-release | flows |  |
| 70 | "The next successful tick batches whatever accumulated." | pre-release | flows |  |
| 71 | "Live email is not a test and never…" | pre-release | flows |  |
| 72 | "Email parity is a ONE-SHOT RIG STEP PER…" | pre-release | flows |  |
| 73 | "Once per release, run the parity exchange once…" | pre-release | flows |  |
| 74 | "Capture the real messages it produces." | pre-release | flows |  |
| 75 | "Commit those messages as FIXTURES." | pre-release | flows |  |
| 76 | "The deterministic tests cover parsing and envelope handling…" | pre-release | flows |  |
| 77 | "No email in any loop, no standing trickle,…" | pre-release | flows |  |
| 78 | "The binding constraint on sends is the mail…" | pre-release | flows |  |
| 79 | "The campaign does NOT fix bugs and does…" | pre-release | flows |  |
| 80 | "Findings are recorded as tests only." | pre-release | flows |  |
| 81 | "Bug fixing belongs to the bug-crush phase, on…" | pre-release | flows |  |
| 82 | "No input fuzzing." | pre-release | flows |  |
| 83 | "The fuzzer's mentality — systematic, coverage-driven test-point design…" | pre-release | flows |  |
| 84 | "Docs describe shipped state only." | pre-release | flows |  |
| 85 | "When a policy decision changes a documented behavior,…" | pre-release | flows |  |
| 86 | "Testing pauses and resumes only on the owner's…" | pre-release | flows |  |
| 87 | "A pause is not a stop: on pause,…" | pre-release | flows |  |
| 88 | "A run is complete when every completed cycle…" | pre-release | flows |  |
| 89 | "The sequence after the first run: snapshot the…" | pre-release | flows |  |
| 90 | "That protection-versus-protection pass starts with the kernel-level protections,…" | pre-release | flows |  |
