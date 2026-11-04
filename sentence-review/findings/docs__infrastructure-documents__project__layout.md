# Findings — docs/infrastructure-documents/project/layout.md

Source: docs/infrastructure-documents/project/layout.md, reviewed at main cbb52068.
Sentence units: 43. Flagged: 2. Categories: pre-release 43, post-release 0.

A path-by-path map of the tree, 1 entry per file or folder, each entry a path and a short gloss. The list itself is the connection; 2 units do not hold even as entries.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "`PROTOCOL.md` — the full wire protocol (message formats,…" | pre-release | flows |  |
| 2 | "`docs/FUTURE.md` — work that is not built." | pre-release | flows |  |
| 3 | "The only list." | pre-release | flagged | Fragment ("The only list."); its referent is not recoverable from the entry it follows, and it hands nothing to the next entry |
| 4 | "`docs/extend/transports.md` — the job transports as shipped: email…" | pre-release | flows |  |
| 5 | "Everything past those in that file is design…" | pre-release | flows |  |
| 6 | "`docs/security/safeguards.md` — how to run this without getting…" | pre-release | flows |  |
| 7 | "`docs/` — the long shelf: the threat model…" | pre-release | flows |  |
| 8 | "Beneath it, grouped by reader: `docs/use/` (running it),…" | pre-release | flows |  |
| 9 | "`runner/runner.py` — the agent." | pre-release | flows |  |
| 10 | "Polls, verifies, executes, replies." | pre-release | flows |  |
| 11 | "No dependencies beyond the Python 3.9+ standard library." | pre-release | flows |  |
| 12 | "Its modules live in four role folders beside…" | pre-release | flows |  |
| 13 | "Two of them are bound back onto it:…" | pre-release | flows |  |
| 14 | "`runner/wire/platformcard.py` is the card a pong and the…" | pre-release | flows |  |
| 15 | "`runner/wire/transports.py` — the transport-extension contract (v1), discovery, and…" | pre-release | flows |  |
| 16 | "`runner/guard/extreview.py` — the extension review: before a sense…" | pre-release | flows |  |
| 17 | "`runner/guard/atomicio.py` — the one way a state file…" | pre-release | flows |  |
| 18 | "Every state writer in the core goes through…" | pre-release | flows |  |
| 19 | "`runner/guard/filenames.py` — the `files[].name` rules (PROTOCOL.md section 6),…" | pre-release | flows |  |
| 20 | "`runner/ops/extsources.py` — extension sources: the first time an…" | pre-release | flows |  |
| 21 | "`runner/oracle/opinion.py` — the Oracle's opinion: the pre-run checks,…" | pre-release | flows |  |
| 22 | "`runner/oracle/learning.py` — the self-learning ledger: frozen calls, scored…" | pre-release | flows |  |
| 23 | "`runner/oracle/remediation.py` — the running-job monitor: tripwires, quarantine, antivirus…" | pre-release | flows |  |
| 24 | "`runner/ops/install.py` — installs it as a boot-start service:…" | pre-release | flows |  |
| 25 | "`runner/config.example.json` — copy to `config.json` and fill in." | pre-release | flows |  |
| 26 | "`runner/hosting/` — the hosting control plane (`homing-pigeon-host`): one…" | pre-release | flows |  |
| 27 | "Tested against recorded exchanges in `runner/tests/hosting_fixtures/`; never a…" | pre-release | flows |  |
| 28 | "Plan: `docs/project/hosting.md`." | pre-release | flagged | A bare file pointer ("Plan: …") after the hosting entry; a fragment with no hand-off, as in the FUTURE findings |
| 29 | "`runner/cloud/queues-worker/` — the hosted queue's Worker and Durable…" | pre-release | flows |  |
| 30 | "`runner/cloud/send_job.py` — cloud-side helper: builds signed job messages,…" | pre-release | flows |  |
| 31 | "`runner/tests/` — the suite: the real runner driven…" | pre-release | flows |  |
| 32 | "Beside it, outside discovery: `runner/tests/airgap/` (the air-gapped batches)…" | pre-release | flows |  |
| 33 | "The campaigns' recorded cycles sat beside it as…" | pre-release | flows |  |
| 34 | "`runner/__init__.py` and `runner/_version.py` — the package and the…" | pre-release | flows |  |
| 35 | "`docs/use/runbook.md` — step-by-step instructions (written for a 5-year-old):…" | pre-release | flows |  |
| 36 | "`runner/tools/make_snapshot.py` — packs the whole project into every…" | pre-release | flows |  |
| 37 | "An installed runner keeps it in its state…" | pre-release | flows |  |
| 38 | "`runner/tools/pin_extension_sources.py` — the release job's pins: every declared…" | pre-release | flows |  |
| 39 | "`runner/extensions/` — the shipped extensions: 28 folders, from…" | pre-release | flows |  |
| 40 | "`docs/security/hardening/` — opt-in OS hardening: a systemd unit,…" | pre-release | flows |  |
| 41 | "`.github/` — CI: the workflows, the container images…" | pre-release | flows |  |
| 42 | "The build and CI scripts are in `runner/tools/`." | pre-release | flows |  |
| 43 | "The root otherwise: `README.md`, `INSTALL.md`, `SECURITY.md`, `FAQ.md`, `AGENTS.md`…" | pre-release | flows |  |
