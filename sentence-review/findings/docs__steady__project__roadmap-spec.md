# Findings — docs/steady/project/roadmap-spec.md

Source: docs/steady/project/roadmap-spec.md, reviewed at main dc5bd698.
Sentence units: 86. Flagged: 0. Categories: pre-release 1, post-release 85.

A spec-only roadmap (2026-10-15, its own status line): proposed senses, job kinds, and Oracle features that were not built for the first release — post-release except the status frame. The prose is connected throughout; nothing is flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "**Archived 2026-10-22.** A spec-only roadmap from 2026-10-15; nothing…" | post-release | flows |  |
| 2 | "Unbuilt work is listed in [docs/FUTURE.md](../FUTURE.md)." | post-release | flows |  |
| 3 | "Status: **spec only** (2026-10-15)." | pre-release | flows | The document's own status line, true when read — pre-release |
| 4 | "Nothing here is scheduled or approved for build." | post-release | flows |  |
| 5 | "Drawn from a Claude brainstorm; edited to fit…" | post-release | flows |  |
| 6 | "Design constraints that apply to everything below: minimal-install…" | post-release | flows |  |
| 7 | "Claude's one-weekend pick, if any of this gets…" | post-release | flows |  |
| 8 | "Together they make it feel alive and make…" | post-release | flows |  |
| 9 | "All of these arrive as `sensor_alert` jobs through…" | post-release | flows |  |
| 10 | "Sensors are dumb; the Oracle fuses." | post-release | flows |  |
| 11 | "A job kind that returns a screenshot, a…" | post-release | flows |  |
| 12 | "Uses: debug a GUI the SI can't see,…" | post-release | flows |  |
| 13 | "Design notes:" | post-release | flows |  |
| 14 | "Snapshot jobs run under the same key-policy scoping…" | post-release | flows |  |
| 15 | "Media never leaves the box except inside a…" | post-release | flows |  |
| 16 | "The Oracle's `ask` path can request a snapshot…" | post-release | flows |  |
| 17 | "UPS/battery state, SMART disk health, Pi temperature, GPU…" | post-release | flows |  |
| 18 | "Each is a tiny script on a timer." | post-release | flows |  |
| 19 | "To make writing one trivial, ship a `homing-pigeon-sense`…" | post-release | flows |  |
| 20 | "A sense becomes a five-line shell script plus…" | post-release | flows |  |
| 21 | "GPIO, serial, servo drivers the SI can drive…" | post-release | flows |  |
| 22 | "The SI can never swing a servo through…" | post-release | flows |  |
| 23 | "Actuator jobs are the one job family where…" | post-release | flows |  |
| 24 | "A transport is a poll/send adapter behind one…" | post-release | flows |  |
| 25 | "Jobs carry a transport id so replies route…" | post-release | flows |  |
| 26 | "The mailbox stays the default; these are options." | post-release | flows |  |
| 27 | "**Telegram long-poll inbound.** Phone-to-runner with no mailbox." | post-release | flows |  |
| 28 | "The DRI paging already speaks Telegram, so half…" | post-release | flows |  |
| 29 | "**ntfy.sh.** A hosted push topic as a transport;…" | post-release | flows |  |
| 30 | "**Matrix room.** For people who already live in…" | post-release | flows |  |
| 31 | "**GitHub as a transport.** A labeled issue or…" | post-release | flows |  |
| 32 | "Odd, but it gives you issues, threads, and…" | post-release | flows |  |
| 33 | "Telegram inline buttons on a risky-looking job: the…" | post-release | flows |  |
| 34 | "Heuristics for "risky-looking" stay adjustable from day one…" | post-release | flows |  |
| 35 | "This is the safety companion to §1.3 and…" | post-release | flows |  |
| 36 | ""Hey pigeon, run the tests." Local Whisper turns…" | post-release | flows |  |
| 37 | "Voice never signs directly — it drafts, you…" | post-release | flows |  |
| 38 | "When a job fails, the Oracle proposes a…" | post-release | flows |  |
| 39 | "The advisory reviewer (`runner/review.py`, `docs/job-review.md`) then gets better…" | post-release | flows |  |
| 40 | "A local-model summary, once a day: what ran,…" | post-release | flows |  |
| 41 | "Cheap, private, no cloud involved." | post-release | flows |  |
| 42 | "The runner already snapshots files outside the workspace…" | post-release | flows |  |
| 43 | "Show "what this job changed on my disk"…" | post-release | flows |  |
| 44 | "Turns "what did it just do?" from a…" | post-release | flows |  |
| 45 | "**Recipes.** Named, hash-pinned scripts the owner stores locally." | post-release | flows |  |
| 46 | "The SI says "run recipe `backup-photos` with these…" | post-release | flows |  |
| 47 | "Kills a whole class of prompt-injection-via-job-body." | post-release | flows |  |
| 48 | "A community recipe gallery would be an easy…" | post-release | flows |  |
| 49 | "**Schedules and watches.** "Run this nightly at 2am."…" | post-release | flows |  |
| 50 | "**Live progress.** A `tail` query op so the…" | post-release | flows |  |
| 51 | "**Undo.** Snapshot before a job (btrfs, ZFS, or…" | post-release | flows |  |
| 52 | "Pairs naturally with §4.3: the diff shows what…" | post-release | flows |  |
| 53 | "**Arena mode.** Send the same task to different…" | post-release | flows |  |
| 54 | "`key_id` scoping and the board code already do…" | post-release | flows |  |
| 55 | "**The Loft.** A fleet view with capability tags…" | post-release | flows |  |
| 56 | "The board assigns tasks to the right bird;…" | post-release | flows |  |
| 57 | "**Integrations.** Home Assistant add-on, Homebrew tap, winget package,…" | post-release | flows |  |
| 58 | "The general model is a mediocre security analyst:…" | post-release | flows |  |
| 59 | "So incidents get a specialist." | post-release | flows |  |
| 60 | "The shape:" | post-release | flows |  |
| 61 | "A **security sub-model** — a smaller model trained…" | post-release | flows |  |
| 62 | "The Oracle (the main Llama) then decides what…" | post-release | flows |  |
| 63 | "The sub-model never pages, never remediates, never touches…" | post-release | flows |  |
| 64 | "It is an advisor with one output: a…" | post-release | flows |  |
| 65 | "The Oracle keeps the decision, which keeps the…" | post-release | flows |  |
| 66 | "Why a separate model instead of a better…" | post-release | flows |  |
| 67 | "Classification is what these models are *trained* for." | post-release | flows |  |
| 68 | "A general chat model grades its own homework;…" | post-release | flows |  |
| 69 | "It is cheap to run beside the main…" | post-release | flows |  |
| 70 | "The verdict is structured (`safe`/`unsafe` + category), not…" | post-release | flows |  |
| 71 | "What exists today (verified 2026-10-16, all Ollama-pullable, all…" | post-release | flows |  |
| 72 | "**Llama Guard 3** (`llama-guard3:1b`, ~1.6 GB; `:8b`, ~4.9…" | post-release | flows |  |
| 73 | "Safety classification against the MLCommons hazard taxonomy; the…" | post-release | flows |  |
| 74 | "**Granite Guardian** (`granite3-guardian:2b/8b`, Apache-2.0)." | post-release | flows |  |
| 75 | "Harm/jailbreak/violence classification with a yes/no output." | post-release | flows |  |
| 76 | "Both are content-safety models, not IDS models —…" | post-release | flows |  |
| 77 | "That is exactly the triage job here: "is…" | post-release | flows |  |
| 78 | "Config (same adjustable-everything posture as the senses):" | post-release | flows |  |
| 79 | "`enabled` (bool, default false): nothing changes until the…" | post-release | flows |  |
| 80 | "`model` / `endpoint`: which local model judges." | post-release | flows |  |
| 81 | "Any OpenAI-compatible chat endpoint on loopback; the loopback-only…" | post-release | flows |  |
| 82 | "`route`: which incidents get triaged." | post-release | flows |  |
| 83 | "`all`, or `severity_floor_<level>` to skip info/low noise." | post-release | flows |  |
| 84 | "When the sub-model is unreachable or times out,…" | post-release | flows |  |
| 85 | "Open questions, deliberately unresolved: whether the verdict should…" | post-release | flows |  |
| 86 | "Both are config-shaped, not code-shaped, so they can…" | post-release | flows |  |
