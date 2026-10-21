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


## Sending a job

Use `cloud/send_job.py`. Do not hand-roll the signature. The shapes below
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
| `interpreter` pointing at a missing binary | Rejected |
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
The job is rejected with `cannot start interpreter: [WinError 2] The system cannot find the file specified`.

- Omit `--interpreter` / the `interpreter` field so the runner uses its platform default (PowerShell on Windows, `sh` elsewhere).
- For a cross-platform clock/hello-world test, a script containing `Get-Date` works on the Windows default; a script containing `date` works on the Unix default. Prefer the default interpreter unless you know the target platform.
- A shared test must not require a binary or marker that only one lane has.

## Result location

Result emails are sent **to the runner's mailbox** (`mailbox_user`) — or to the job's validated `reply_to` address when the job sets one — not to the SI's connected mail account. Searching the connector for `[HOMING-PIGEON] result <job_id>` will not find them unless the job's `reply_to` named that account, the result was forwarded, or the runner is configured to deliver elsewhere. Check the runner console or ask the user to forward the result if verification is needed.


## Working the task board (worker SIs)

The runner also deals work from a local task board (PROTOCOL.md
section 13). Any holder of a trusted shared secret can pull. The
loop, with the helper:

1. **Pull.** `python3 cloud/send_job.py task-request --worker-id
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
pull tasks or run scripts. Omit `--key-id` to use the default secret.
