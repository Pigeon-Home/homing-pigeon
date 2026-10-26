# Layout

- `PROTOCOL.md` — the full wire protocol (message formats, signatures,
  verification rules, security model).
- `docs/project/future.md` — work that is not built. The only list.
- `docs/extend/transports.md` — the job transports as shipped: email (default),
  file, core NATS, the hosted queue, and the DTLS session binding
  (off unless enabled — it is the one transport that listens). Everything
  past those in that file is design notes, not code.
- `docs/security/safeguards.md` — how to run this without getting burned: the
  non-negotiables, containment, the Oracle as a safeguard, and what
  to do when something goes wrong.
- `docs/` — the long shelf: the threat model and security gaps,
  configuring the Oracle, the extensions walkthrough, fuzzing
  (`docs/project/fuzzing.md`), and the four manuals above. Beneath it:
  `docs/design/` (design records: opinions and self-learning,
  remediation, the approval gate, asymmetric signing),
  `docs/ietf/` (the Internet-Drafts), `docs/reports/` (dated
  coverage and mutation reports), and `docs/archive/`
  (historical notes, kept for the record; not current guidance).
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
  card a pong and the DTLS greeting carry; `runner/guard/textutil.py` the
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
  manifest (`docs/extend/extensions.md`, "The review").
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
  and under the disclosure rule (`docs/extend/extensions.md`, "Sources").
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
  `docs/project/hosting.md`.
- `runner/cloud/queues-worker/` — the hosted queue's Worker and Durable
  Object (`docs/extend/transports.md`, "Queues"); its tests run under
  node.
- `runner/cloud/send_job.py` — cloud-side helper: builds signed job messages,
  verifies result messages. (Your SI uses this logic when dispatching jobs.)
- `runner/tests/` — the suite: the real runner driven against fake
  IMAP/SMTP servers and a fake NATS broker.
- `docs/use/runbook.md` — step-by-step instructions (written for a 5-year-old):
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
  catalog in `docs/extend/extensions.md`.
- `docs/security/hardening/` — opt-in OS hardening: a systemd unit, an
  AppArmor profile, an SELinux module, and Windows notes.
- `.github/` — CI: the workflows, the container images in
  `.github/docker/`, and the CI pins in `.github/requirements-ci.txt`.
  The build and CI scripts are in `runner/tools/`.
