# Layout

- `PROTOCOL.md` — the full wire protocol (message formats, signatures,
  verification rules, security model).
- `docs/FUTURE.md` — work that is not built. The only list.
- `docs/infrastructure-documents/extend/transports.md` — the job transports as shipped: email (default),
  file, core NATS, the hosted queue, and the DTLS session binding
  (off unless enabled — it is the one transport that listens). Everything
  past those in that file is design notes, not code.
- `docs/infrastructure-documents/security/safeguards.md` — how to run this without getting burned: the
  non-negotiables, containment, the Oracle as a safeguard, and what
  to do when something goes wrong.
- `docs/` — the long shelf, on two shelves. The steady shelf
  (`docs/steady/`) holds the reader's guides: `docs/steady/use/`
  (running it), `docs/steady/oracle/` (the Oracle),
  `docs/steady/security/` (the platform confinement pages, the
  default posture, the hardening templates), `docs/steady/project/`
  (contributing, hosting, the roadmap, the de_dust campaign
  strategies), `docs/steady/design/` (design records: opinions
  and self-learning, remediation, the approval gate, asymmetric
  signing), `docs/steady/seats/` (the seats' drawers),
  `docs/steady/proofs/` and `docs/steady/reports/` (dated coverage
  and mutation reports), `docs/steady/specimens/` (recorded
  results the tests read), and the steady top-level pages —
  start-here, sending, networking, the extensions walkthrough
  (`docs/steady/extensions.md`), feature tiers, fuzzing
  (`docs/steady/fuzzing.md`), verification, secret rotation, the
  emergency plan and the present-but-invalid-config record. The
  infrastructure shelf (`docs/infrastructure-documents/`) holds
  the project's own records: `use/`, `extend/` (transports,
  worker agents), `oracle/` (configuring the Oracle), `security/`
  (the threat model, security gaps, safeguards, the OWASP
  reference, the model-and-proof-testing summary), `design/`,
  `project/` (this page, testing, the campaigns, the statistics
  record), `proofs/` (the formal proof work), `reports/` and
  `seats/`. Beside the shelves: `docs/ietf/` (the
  Internet-Drafts), `docs/archive/` (historical notes, kept
  for the record; not current guidance), and
  `docs/infrastructure-documents/changelog.md`; contributing
  stands at `docs/steady/project/contributing.md`.
- `runner/runner.py` — the agent. Polls, verifies, executes,
  replies. No dependencies beyond the Python 3.9+ standard library.
  Its modules live in four role folders beside it: `runner/oracle/`
  (the Oracle: opinion, learning, review, remediation, detection,
  senses, resources, dri, personal_docs), `runner/wire/` (transports,
  mailbox, DTLS, protocol v2, job crypto, OAuth, verification, the
  board, the platform card), `runner/guard/` (security controls,
  the sandbox, typed config readers, text helpers) and `runner/ops/`
  (install, setup, extensions and their sources, the harness, the
  local test, posture, the audit report, the Windows event log, and
  the parts of the agent's own loop split out of `runner.py`: the
  CLI, polling, mail handling, execution, queries, startup, the
  Oracle's page and tools, and `main`; `runner.py` loads each through
  `_load_mod` and re-exports its names, so `python3 runner.py` and
  the frozen binaries reach them the same way).
  Two of them are bound back onto it:
  `runner/wire/verify.py` (signing, verification, secrets, key policies,
  audience — PROTOCOL.md sections 4, 5, 14) and `runner/wire/board.py`
  (the task board, section 13). `runner/wire/platformcard.py` is the
  card a pong and the DTLS handshake payload carry; `runner/guard/textutil.py` the
  text helpers they share.
- `runner/wire/transports.py` — the transport-extension contract
  (v1), discovery, and supervision: the core is transport-blind,
  and email, the watched folder, core NATS, and the DTLS
  listener all run as supervised extension programs under
  `runner/transport_extensions/`, enabled by the `transports`
  config key.
- `runner/guard/extreview.py` — the extension review: before a sense
  or transport folder is loaded, its code is read against its
  manifest (`capabilities`, `entry` inside the folder, compiling
  `.py`, no symlinks or bidi control characters, nothing naming the
  runner's state); `enforce` refuses a contradiction like a bad
  manifest (`docs/steady/extensions.md`, "The review").
- `runner/guard/atomicio.py` — the one way a state file is replaced:
  a temp name opened `O_EXCL | O_NOFOLLOW`, the bytes written (and
  fsynced where the record is evidence, as the quarantine markers
  are), `os.replace`, mode 0600. Every state writer in the core goes
  through it; `runner/tests/test_atomicio.py` kills a writer
  mid-write and scans the tree for a second copy.
- `runner/guard/filenames.py` — the `files[].name` rules (PROTOCOL.md
  section 6), numbered so a rejection names the one broken; the
  runner's gate and `runner/cloud/send_job.py` both call it.
- `runner/ops/extsources.py` — extension sources: the first time an
  extension runs, its own code and the upstream sources and specs
  its `sources.json` declares reach the Oracle — fetched in the
  background, held to the build's SHA-384 pins, never executed,
  and under the disclosure rule (`docs/steady/extensions.md`, "Sources").
- `runner/oracle/opinion.py` — the Oracle's opinion: the pre-run checks,
  the prediction, and the one mechanical repair.
- `runner/oracle/learning.py` — the self-learning ledger: frozen calls,
  scored outcomes, and the lessons the next opinion reads.
- `runner/oracle/remediation.py` — the running-job monitor: tripwires,
  quarantine, antivirus referral, the page.
- `runner/ops/install.py` — installs it as a boot-start service: systemd
  (Linux), launchd (macOS), cron @reboot (FreeBSD), Scheduled Task
  (Windows).
- `runner/config.example.json` — copy to `config.json` and fill in.
- `runner/hosting/` — the hosting control plane (`homing-pigeon-host`):
  one HTTP door (`httpdoor.py`), the provider interface (`base.py`),
  adapters for Fly Machines, Hetzner Cloud, DigitalOcean and GitHub
  Actions, the bootstrap a fresh machine runs, the inventory with its
  one-tenant-per-machine rule, and prepaid billing with the Stripe
  webhook. Tested against recorded exchanges in
  `runner/tests/hosting_fixtures/`; never a live call. Plan:
  `docs/steady/project/hosting.md`.
- `runner/cloud/queues-worker/` — the hosted queue's Worker and Durable
  Object (`docs/infrastructure-documents/extend/transports.md`, "Queues"); its tests run under
  node.
- `runner/cloud/send_job.py` — cloud-side helper: builds signed job messages,
  verifies result messages. (Your SI uses this logic when dispatching jobs.)
  `runner/cloud/send_dtls.py` is the same for the DTLS binding.
- `runner/tests/` — the suite: the real runner driven against fake
  IMAP/SMTP servers and a fake NATS broker. Beside it, outside
  discovery: `runner/tests/airgap/` (the air-gapped batches) and
  `runner/tests/de_dust/` (the fuzz corpus and its arc maps). The
  campaigns' recorded cycles sat beside it as `runner/tests/archive/`
  until their removal on 2026-11-01; the record lives at the
  `campaign-1-record` tag and the shapes in
  `runner/tests/test_campaign_core.py`.
- `runner/__init__.py` and `runner/_version.py` — the package and the
  one version constant every entry point reports.
- `docs/steady/use/use-runbook.md` — step-by-step instructions (written for a 5-year-old):
  cloning, pushing, cutting a release, installing, sending a job.
- `runner/tools/make_snapshot.py` — packs the whole project into every
  release: each install archive carries `project/` (every tracked
  file, the full git history as a bundle, and the build's CI facts
  and test results, indexed by `project/PROJECT-SNAPSHOT.md`), and
  the same snapshot ships alone as
  `homing-pigeon-project-<version>.tar.gz`. An installed runner
  keeps it in its state dir, so the Oracle can read the source, the
  tests, and the CI that built it without a network.
- `runner/tools/pin_extension_sources.py` — the release job's pins: every
  declared extension source resolved to a commit and hashed,
  shipped in the snapshot as `project/EXTENSION-SOURCES.lock.json`
  (the sources themselves never ship; the boxes fetch them).
- `runner/extensions/` — the shipped extensions: 28 folders, from the
  lab-results sense to the IDS feeds; 25 of them are the pinned
  catalog in `docs/steady/extensions.md`.
- The hardening files in `docs/steady/security/` — opt-in OS hardening:
  a systemd unit (`homing-pigeon.service`), an AppArmor profile
  (`homing-pigeon`), an SELinux module (`homing_pigeon.te`), and
  Windows notes (`windows.md`).
- `.github/` — CI: the workflows, the container images in
  `.github/docker/`, and the CI pins in `.github/requirements-ci.txt`.
  The build and CI scripts are in `runner/tools/`.
- The root otherwise: `README.md`, `INSTALL.md`, `SECURITY.md`,
  `AGENTS.md` (the agents' rules and the layout map), `LICENSE`,
  `pyproject.toml` (the package, the wheel's exclusions, the mutmut
  scope) and `assets/` (images). At the top of `docs/` sit
  `docs/FAQ.md`, `docs/FUTURE.md`, `docs/ENTERPRISE.md` (a
  placeholder, kept as is), `docs/support-matrix.md` and
  `docs/checklist.txt` (the conductor's own file), one level back
  from the root.
