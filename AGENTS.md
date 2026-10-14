# Agents and the Gmail connector

## The split

There are two sides. They do not share credentials.

| Side | Who | How it talks to mail | What it must never do |
|------|-----|----------------------|------------------------|
| **Cloud SI** (this agent, Grok, or any assistant) | Holds a connected Gmail account | Gmail connector (`gmail_send_message`, `gmail_search`, `gmail_get_message`) | Ask the user for a mailbox login or password. Paste credentials into chat. Store an app password. |
| **Runner** (homing-pigeon on the host) | Dedicated throwaway mailbox | IMAP + SMTP with an app password in `config.json` on that machine | Be given the user's personal inbox. Accept mail from anyone but the configured sender. |

The connector is already authenticated. The SI uses it. The runner keeps using IMAP. That is the whole design.

## Why the SI does not need the mailbox password

- Sending a job is just sending an email. The connector can do that from the connected account.
- Reading a result is just reading an email. The connector can search and fetch it.
- The HMAC shared secret is a separate string the user pastes once into the runner's `config.json` and once to the SI. It is not the connector token, and it is not the user's Google password.
- Asking the user to paste `mailbox_user` / `mailbox_password` into chat is unnecessary and wrong for the SI side.

## What the runner still needs

The runner is a different process on a different machine. It polls with IMAP. It needs:

- a dedicated mailbox (never a personal inbox)
- an app password in `config.json` on that host
- `allowed_sender` set to the address the connector sends from (or left empty so it only accepts mail from the account it is logged into)

Those values live on the runner host. They do not travel through the SI chat.

## Rules for any agent working on this project

1. Use the Gmail connector for all cloud-side mail. Do not request or accept mailbox credentials in conversation.
2. The runner's IMAP/SMTP config is an install-time concern for the host, not a chat concern.
3. The shared secret for HMAC is the only secret the SI needs, and only so it can sign jobs. It is not a login.
4. If a live round-trip is required, send the signed job with the connector to the runner's dedicated address, then poll for the result with the connector. Do not log into the runner's mailbox.
5. If the connector is not connected, ask the user to connect Gmail. Do not fall back to asking for a password.

## Personal account is not the runner

The connector is attached to a personal Gmail account that holds legal and other private mail. Rules:

- **Allowed:** send a clearly marked test email to that same address, read it back, verify the signature, exercise the cloud pipeline.
- **Not allowed:** point the runner at that account, poll it with IMAP, or use it as the job mailbox for end-to-end execution tests.
- End-to-end execution tests need a dedicated throwaway mailbox. The personal connector account is only the easy path for the SI side.

## Current connector

The connected send-as address is the primary Gmail account on the connector. Jobs the SI sends come from that address. The runner, when it exists, must use a different dedicated mailbox and set `allowed_sender` to the connector address.
