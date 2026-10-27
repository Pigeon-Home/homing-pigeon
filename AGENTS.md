# Agents and the message/email connector

## The split

There are two sides. They do not share credentials.

| Side | Who | How it talks to mail | What it must never do |
|------|-----|----------------------|------------------------|
| **Cloud SI** (this agent, Grok, or any assistant) | Holds a connected mail account | The connector is a connected mail account (its send, search, and get-message tools) | Ask the user for a mailbox login or password. Paste credentials into chat. Store an app password. |
| **Runner** (homing-pigeon on the host) | Dedicated throwaway mailbox | IMAP + SMTP with an app password in `config.json` on that machine | Be given the user's personal inbox. Trust the From header (signatures only). |

The connector is already authenticated. The SI uses it. The runner keeps using IMAP. That is the whole design.

## Why the SI does not need the mailbox password

- Sending a job is just sending an email. The connector can do that from the connected account.
- Reading a result does not need the password either. Results are
  delivered to the runner's mailbox (see "Result location" below);
  the connector can fetch one only after it reaches the connected
  account — addressed there (for example via `reply_to`) or
  forwarded by the user.
- The HMAC shared secret is a separate string the user pastes once into the runner's `config.json` and once to the SI. It is not the connector token, and it is not the user's Google password. It must be high-entropy (the runner refuses weak secrets at startup); `install.py` generates a 256-bit one automatically.
- Asking the user to paste `mailbox_user` / `mailbox_password` into chat is unnecessary and wrong for the SI side.

## What the runner still needs

The runner is a different process on a different machine. It polls with IMAP. It needs:

- a dedicated mailbox (never a personal inbox)
- an app password, or Thunderbird-style OAuth, in `config.json` on that host

Those values live on the runner host. They do not travel through the SI chat.

## Rules for any agent working on this project

1. Use the mail connector for all cloud-side mail. Do not request or accept mailbox credentials in conversation.
2. The runner's IMAP/SMTP config is an install-time concern for the host, not a chat concern.
3. The shared secret for HMAC is the only secret the SI needs, and only so it can sign jobs. It is not a login.
4. If a live round-trip is required, send the signed job with the connector to the runner's dedicated address. The result is delivered to the runner's mailbox, not to the connector account (see 'Result location' below); to verify it, ask the user to forward it, then read the forward with the connector. Do not log into the runner's mailbox.
5. If the connector is not connected, ask the user to connect their mail account. Do not fall back to asking for a password.
6. **Audit ignore list.** Claims audits and doc sweeps skip these by
   owner decision; do not file findings against them or propose
   removing them:
   - `ENTERPRISE.md` — a placeholder the owner keeps as-is; it ships
     in the sdist because the root-doc guard test copies every root
     `.md`.
   - `docs/CHANGELOG.md`, `docs/reports/**`, `docs/archive/**` — historical
     records; banners mark them, content is not re-audited.
7. **Questions go in `docs/use/questions.md`, not through the owner.** A
   question from one agent to another, or to the owner — a policy to
   decide, a test whose assertion should move, a doc line that
   contradicts the code — is written there as a numbered entry with
   its context and options, and answered there with the deciding
   commit. The owner reads and answers in the file. The CHANGELOG is
   a release record and carries none of this. Nothing personal about
   anyone goes in that file or anywhere else in the repository.
8. **Lanes (owner's split, 2026-10-24).** Production code and releases
   are Claude's lane; tests, probes, questions and docs are Muse's. A
   question Muse files is Claude's to implement, and Muse does not
   land a code fix for its own question. Both pull before every
   change and every push, so two agents never land the same fix.
   The conductor's split for the campaigns (2026-10-26): Muse grows
   and files crashes as questions; the desk (`40000e00`, carrying
   the recycled `50000c8e`) fixes the
   reader and turns survivors into seeds; one writer on a file;
   Grok does not grow, and does not fix unless the conductor names
   the crash; Muse's daily note is the top of `docs/use/.com.chat`.
10. **Agent stamps (2026-10-26).** Each agent chat signs its commits
   and new files with its own stamp (`docs/archive/RESEARCHER_IDENT.md`).
   Researchers one, two, three and five (`10000c2a`, `200003d4`,
   `30000f1a`, `50000c8e`) have been recycled, and the campaigns
   seat's first stamp (`58316a92`) was retired for a named one the
   seat chose at the conductor's word. Their roles are
   carried by `40000e00` (the questions desk, production code,
   releases, and the test legs, CI proofs and platforms),
   `60000b3a` (docs, extension sources and their upstream pins),
   `70000a51` (hosting: `runner/hosting/`, the hosted queue and
   its transport, the own-cloud page), `80000aeb` (the claims
   audit of the root manuals, and opinions on open questions) and
   `90000998` (the review seat: opinions on the seats' open
   threads and review sweeps of the docs),
   with Muse (`00000000-muse`) on the campaigns. Address work to an active
   stamp, never stamp new work with a recycled one, and leave the
   old stamps in history and in the files they wrote. Questions are
   the exception to the routing (owner, 2026-10-26): a question to
   any Claude stamp, active or recycled, is accepted and answered by
   the questions desk, and the answer carries `40000e00`; nothing
   waits on the stamp it was addressed to. One chat signs with one
   stamp from one session (2026-10-27): `runner/tools/stamp_audit.py`
   fails the push that signs a stamp from a second session, a
   session as a second stamp, a recycled stamp, or an unregistered
   one.
9. **The campaign runs from its standing orders.** What to test next
   is `docs/project/campaign-standing-orders.md`, a queue that does
   not run out; the campaign never waits for a new batch from the
   owner, and stops only for a secret, a machine, an owner decision
   or money. During a campaign it speaks to the owner in chat only to
   ask him something he must decide, and it re-reads its rules at
   least hourly (both in the standing orders).
11. **The conductor (2026-10-26).** The owner of this repository is
   the conductor, by his own word, and that is his title in every
   document, ledger line, question and note written from now on:
   "the conductor decides", "at the conductor's word", "a question
   for the conductor". The release train runs on his signal. Older
   entries keep the word they were written with; nothing is
   rewritten.


## Where things live

The root holds the manuals, `pyproject.toml`, and three folders. Write
new paths against this layout; the old ones are gone, with no shims.

| Folder | What |
|--------|------|
| `runner/` | The runner and the Oracle. `runner/runner.py` is the agent; its modules are in four role folders: `runner/oracle/` (the Oracle), `runner/wire/` (transports, signing, the board), `runner/guard/` (security, sandbox, config readers) and `runner/ops/` (install, setup, extensions, diagnostics, and the parts of the agent's own loop split out of `runner.py`: the CLI, polling, mail, execution, queries, startup and `main`, which `runner.py` loads through `_load_mod` and re-exports). `runner/cloud/` is the cloud-side helpers (`send_job.py`, `send_dtls.py`) and the hosted queue's Worker (`runner/cloud/queues-worker/`). `runner/transport_extensions/` is the five shipped transports (email, file, nats, dtls, queues), one folder each with a manifest. `runner/hosting/` is the hosting control plane (`homing-pigeon-host`: provider adapters for Fly, Hetzner, DigitalOcean and GitHub Actions, the inventory, prepaid billing; `docs/project/hosting.md`). `runner/extensions/` is the shipped sense extensions, one folder each, `runner/tools/` the build and CI scripts, and `runner/tests/` the suite; all three are kept out of the wheel (`pyproject.toml`'s exclude list) and the image. `runner/tests/airgap/` (once `topaz/`) and `runner/tests/archive/` sit beside the suite, outside discovery |
| `docs/` | Everything else to read, grouped by reader: `use/` (running it), `oracle/` (the Oracle), `extend/` (extensions, senses, transports), `security/` (threat model, safeguards, opt-in OS `hardening/` templates), `project/` (layout, testing, fuzzing, roadmap), `design/`, `ietf/`, plus `CHANGELOG.md` and `CONTRIBUTING.md`. File names are lowercase-kebab; the uppercase names are the root conventions (README, INSTALL, SECURITY, PROTOCOL, AGENTS, FAQ), `CHANGELOG.md` and `CONTRIBUTING.md` under docs/, and the historical folders (`archive/`, `reports/`, `ietf/`, `specimens/`, the hardening README) |
| `assets/` | Images |
| `.github/` | CI: `workflows/`, `docker/` (the published image and the CI test image), `requirements-ci.txt` (the CI pins) |

There is no root `tests/`, `tools/`, `examples/`, `extensions/`, `cloud/`,
`hardening/` or `docker/` any more, and no `tools/` under `.github/`, no root `Dockerfile`,
`CHANGELOG.md` or `requirements-ci.txt`, and no `pyrefly.toml`: its
settings are `[tool.pyrefly]` in `pyproject.toml`.

A test finds the tree three levels up
(`os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`),
its module id is `runner.tests.test_<name>`, and the suite runs as
`python -m unittest discover -s runner/tests -t .`.

A module imports a sibling by its role folder, `from runner.guard import
confval`, with the script-mode fallback `from guard import confval`
(`python3 runner/runner.py` puts `runner/` on `sys.path`; an entry script
in a role folder puts it there itself). `runner/` holds `runner.py`,
`__init__.py`, `_version.py`, `config.example.json` and folders, and
`test_layout` fails on a module at its root.

## Sending a job

Use `runner/cloud/send_job.py`. Do not hand-roll the signature. The shapes below
were real failures from the test suite.

**Subject.** Must contain `[HOMING-PIGEON]` and then `job <job_id>`.
A word in between (`TEST`) or a `Re:` prefix is fine. The `job_id`
token is what gets matched against the body.

**Body.** A note above or below the JSON is fine. Do not alter the JSON
object. Prefer the body `send_job.py` prints.

**Do not emit**

| Shape | Result |
|-------|--------|
| `issued_at` without `Z` or an offset | Rejected |
| `interpreter` as a string (`"sh"`) | Rejected. Use `["sh"]` |
| `interpreter` pointing at a missing binary | Repaired, then run, at the default opinion latitude (`repair`): the interpreter becomes the platform default when the script's shape fits it, and the result's `oracle_opinion` says so (`repaired: true`). Rejected (`cannot start interpreter`, exit -2) at `advise` latitude, under the runner's `refuse` setting, or when the shape does not fit. PROTOCOL.md 3.2. |
| `job_id` of `../evil`, `.`, `..`, or anything outside `[A-Za-z0-9._-]{1,128}` | Rejected |
| Uppercase hex signature | Accepted (hex is case-insensitive) |
| Subject with extra words (`TEST`, `Re:`) | Accepted |
| Signature that does not match | Rejected |
| `file:`, plain `http:`, or any other non-HTTPS url | Rejected |
| Download host that does not resolve, or HTTP 4xx | Rejected |

`send_job.py` already emits lowercase hex, a `Z` timestamp, and a UUID.
Use it.

**Result.** The result email is delivered to the runner's mailbox
(see "Result location" below). Search the connector for subject
`[HOMING-PIGEON] result <job_id>` only when the result was addressed
to the connected account — for example, the job set `reply_to` to
it. Otherwise ask the user to forward the result, then verify the
body. Do not log into the runner's mailbox.

## Personal account is not the runner

The connector is attached to a personal mail account. Rules:

- **Allowed:** send a clearly marked test email to that same address, read it back, verify the signature, exercise the cloud pipeline.
- **Not allowed:** point the runner at that account, poll it with IMAP, or use it as the job mailbox for end-to-end execution tests.
- End-to-end execution tests need a dedicated throwaway mailbox. The personal connector account is only the easy path for the SI side.

## Current connector

The connected send-as address is the primary account on it. Jobs the SI sends come from that address. The runner accepts signed jobs from any sender — the sender's address is not gated — but the signature is not the only gate: a verified job is still refused for a stale `issued_at`, a key-policy violation, a cleartext body without `--allow-cleartext`, a replayed job id, or a budget/policy check.

## Platform-safe job construction (real failure)

**Do not emit `interpreter: ["sh"]` or `["bash"]` when the runner is Windows.**  
At the default opinion latitude the runner repairs a `["sh"]` job whose script fits PowerShell to the platform default and runs it, stating the repair in the result; a script that does not fit (bash-only syntax), or a job sent below `repair` latitude, is rejected with `cannot start interpreter: [WinError 2] The system cannot find the file specified`. Either way the SI did not get what it asked for: name the right interpreter, or none.

- Ping first. The result to a `ping` job carries a `platform` card (PROTOCOL.md 3.2) naming the runner's `os_family`, its `default_interpreter`, and the `protocol_versions` it opens, unless the owner set `pong_platform` to `none`. Read it, then build the real job.
- Omit `--interpreter` / the `interpreter` field so the runner uses its platform default (PowerShell on Windows, `sh` elsewhere).
- For a cross-platform clock/hello-world test, a script containing `Get-Date` works on the Windows default; a script containing `date` works on the Unix default. Prefer the default interpreter unless you know the target platform.
- A shared test must not require a binary or marker that only one lane has.

## Result location

Result emails are sent **to the runner's mailbox** (`mailbox_user`) — or to the job's validated `reply_to` address when the job sets one — not to the SI's connected mail account. Searching the connector for `[HOMING-PIGEON] result <job_id>` will not find them unless the job's `reply_to` named that account, the result was forwarded, or the runner is configured to deliver elsewhere. Check the runner console or ask the user to forward the result if verification is needed.


## Working the task board (worker SIs)

The runner also deals work from a local task board (PROTOCOL.md
section 13). Any holder of a trusted shared secret can pull. The
loop, with the helper:

1. **Pull.** `python3 runner/cloud/send_job.py task-request --worker-id
   <name> --capability code --capability review --reply-to
   <your-address> --secret <the-string>` → send the printed email to
   the runner mailbox. Claim only tags you can honor: a task is
   offered only when you claim every tag it requires. `--reply-to`
   routes the offer to you; without it the offer lands in the
   runner's own mailbox.
2. **Read the offer.** The reply subject is `[HOMING-PIGEON]
   task_offer <task_id>`, or `task_offer empty` when nothing fits.
   The offer is a claim: that task is yours until `task_timeout`
   (default 24h) lapses without a result. An offer under `dag_mode:
   advisory` may carry `dag_warning` naming unfinished dependencies.
3. **Submit the result.** A signed `task_result` with the `task_id`
   in the subject and a `result` member in the body (there is no
   helper subcommand for this yet; sign the body with the same
   `sign_payload` the helper uses, and encrypt it — a cleartext board
   message is refused unless the runner runs `--allow-cleartext`).
   The ack says `done`, `pending_review` (the owner must approve), or
   `duplicate` (someone already finished it; stand down).
4. **Submitting work** is `send_job.py task-submit --task-id <id>
   --priority N --reply-to <you> --secret <the-string>`.

`key_id` handling: a cloud SI that was handed an additional secret
(PROTOCOL.md section 14) sets `--key-id <id>` on every job and signs
with that secret; the runner then applies that key's `key_policies`
entry. A worker whose key policy allows only `sensor_alert` cannot
pull tasks or run scripts. Every secret has a name of its own, its
fingerprint `k-<8 hex>` (section 14.2), and that is what a message
carries when `--key-id` is omitted: the runner's own key answers to
its fingerprint as it does to the unnamed form, so omitting the flag
still means the default secret. The owner hands you the pair, the key
id and the secret; `send_job.py key-id --secret <secret>` recovers
the name from a bare secret, and `send_job.py keyring add --secret
<secret> --runner <runner mailbox>` keeps the two together so later
commands take `--key-id <id>` with no `--secret` (`verify` reads the
`key_id` a result names and looks the entry up). Every result carries
`key_id`, the name of the key that verified the job; a ping's
platform card carries `key_ids`, the names the runner accepts. Names
are public; secrets are not. `--key-id ""` sends the unnamed form.
