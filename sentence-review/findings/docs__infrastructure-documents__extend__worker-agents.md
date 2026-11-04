# Findings — docs/infrastructure-documents/extend/worker-agents.md

Source: docs/infrastructure-documents/extend/worker-agents.md, reviewed at main 5c681047.
Sentence units: 48. Flagged: 0. Categories: pre-release 48, post-release 0.

A page on how an external agent framework meets the runner: what such a framework is, the 3 surfaces (worker on the task board, sender in its own right, the Oracle's model plug), the limits of each, and the credential separation. Continuous explanatory prose; each surface is introduced, walked through, and bounded before the next begins, and the closing paragraph restates the page's standing claim that no bridge ships with either project. Nothing is flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "An external agent framework is a self-hosted agent…" | pre-release | flows |  |
| 2 | "OpenClaw is the worked example throughout this page:…" | pre-release | flows |  |
| 3 | "Where a call is named, it is OpenClaw's…" | pre-release | flows |  |
| 4 | "Such a framework is neither extension kind." | pre-release | flows |  |
| 5 | "A sense files alerts and never runs work;…" | pre-release | flows |  |
| 6 | "A framework like this does work, so it…" | pre-release | flows |  |
| 7 | "Each way is stated with its limits; nothing…" | pre-release | flows |  |
| 8 | "The board (PROTOCOL.md section 13) is the meeting…" | pre-release | flows |  |
| 9 | "Its worker is any holder of the shared…" | pre-release | flows |  |
| 10 | "The loop is the one the protocol defines:" | pre-release | flows |  |
| 11 | "A task is opened with `task_submit` — by…" | pre-release | flows |  |
| 12 | "The worker pulls with a signed `task_request` naming…" | pre-release | flows |  |
| 13 | "A small bridge program hands the task's payload…" | pre-release | flows |  |
| 14 | "The framework's own surfaces carry that call: for…" | pre-release | flows |  |
| 15 | "The bridge files the turn's outcome as a…" | pre-release | flows |  |
| 16 | "The board answers `task_ack` — `done`, `pending_review` when…" | pre-release | flows |  |
| 17 | "A task opened with `require_review: true` waits in…" | pre-release | flows |  |
| 18 | "Results come back through the board and nowhere…" | pre-release | flows |  |
| 19 | "What the framework needs for this way is…" | pre-release | flows |  |
| 20 | "OpenClaw has both; it also starts work on…" | pre-release | flows |  |
| 21 | "The same bridge, holding the same authority, can…" | pre-release | flows |  |
| 22 | "From the runner's side the framework is an…" | pre-release | flows |  |
| 23 | "This is also how the framework asks the…" | pre-release | flows |  |
| 24 | "Two limits are plain." | pre-release | flows |  |
| 25 | "Nothing in this pattern wakes the Oracle: the…" | pre-release | flows |  |
| 26 | "And the protocol version 2 question exchange runs…" | pre-release | flows |  |
| 27 | "The Oracle's model is a configuration plug point,…" | pre-release | flows |  |
| 28 | "In `llm` mode the runner calls one endpoint:…" | pre-release | flows |  |
| 29 | "In `deterministic` mode — the Pi Light profile…" | pre-release | flows |  |
| 30 | "A framework that serves the same shape can…" | pre-release | flows |  |
| 31 | "OpenClaw's gateway does, when its OpenAI-compatible endpoint is…" | pre-release | flows |  |
| 32 | "Pointing the runner's `inference` endpoint at `http://127.0.0.1:18789/v1` with…" | pre-release | flows |  |
| 33 | "The runner's guards still apply to whatever comes…" | pre-release | flows |  |
| 34 | "The fit is partial, in three named places:" | pre-release | flows |  |
| 35 | "**Authentication.** The runner sends no credential with its…" | pre-release | flows |  |
| 36 | "The gateway's endpoint normally requires its bearer token,…" | pre-release | flows |  |
| 37 | "With token authentication on, the runner cannot call…" | pre-release | flows |  |
| 38 | "**What answers is an agent, not a model.**…" | pre-release | flows |  |
| 39 | "That is a heavier, less predictable answer than…" | pre-release | flows |  |
| 40 | "**One duty does not transfer.** The interactive `--oracle`…" | pre-release | flows |  |
| 41 | "An agent endpoint returns finished text, not tool…" | pre-release | flows |  |
| 42 | "And the rest of the Oracle — the…" | pre-release | flows |  |
| 43 | "The two programs' credentials stay separate." | pre-release | flows |  |
| 44 | "The framework's gateway and hooks tokens admit calls…" | pre-release | flows |  |
| 45 | "The bridge holds both, so the bridge is…" | pre-release | flows |  |
| 46 | "Board membership grants no runner privilege beyond claiming…" | pre-release | flows |  |
| 47 | "No bridge program ships with either project." | pre-release | flows |  |
| 48 | "This page describes compositions of interfaces both projects…" | pre-release | flows |  |
