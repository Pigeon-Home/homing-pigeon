# Shared secret rotation

Rotate the shared secret every **90 days**. The period is a calendar cap: the
secret lives on disk and gets pasted into chat to provision signers. It is not
a function of how many jobs you send.

HMAC-SHA-384 tags do not leak the key at any message count. One captured
message is already enough to test a guess, and a billion more do not make that
guess cheaper. Pigeon mail never carries the secret, only the tag.

## What the runner actually loads

A job with no `key_id` verifies against `shared_secret`, and so does a job
whose `key_id` is that secret's fingerprint (`k-<8 hex>`, PROTOCOL.md
section 14.2: the name every secret carries, which the reference sender
uses by default since Q94). A job with any other `key_id` verifies
against `additional_secrets`. Secrets are read at startup — editing
config.json takes effect on restart.

A new secret is a new name: its fingerprint changes with it, and the
pong's platform card (`key_ids`) lists the names the running config
accepts, so a signer can see a rotation land before it switches. The
name is public (SECURITY.md, "Key names are public"); only the secret
is handed over in private.

A new `key_id` does not inherit `key_policies`. If
`key_policies_default_deny` is false (the default), the new key is
unrestricted. If true, a new id with no policy is refused — copy the policy
entry onto the new id.

## Naming the first secret

The conductor decided on 2026-10-27 (Q94) that a secret the
installer generates is named, and it is:

- The first secret's name is its fingerprint, `k-<8 hex>`
  (PROTOCOL.md section 14.2), which the installer prints beside the
  secret and `send_job.py key-id` recovers from a bare secret;
  `install --key-id <name>` stores a chosen name beside it under
  `additional_secrets` with the same value. `shared_secret` holds
  the secret as before, so a sender that still omits `key_id` keeps
  verifying.
- A sender sends the key's name on every body by default.
  `--key-id ""` is how it asks for the unnamed slot.
- The empty key id stays a legacy alias of that first key
  through the next line of releases. A later release may refuse
  an unnamed body. That is a separate question.
- A planned rotation names the new key. The old one stays until
  every sender has moved. A leak is not a planned rotation:
  `docs/security/safeguards.md` §7 replaces the secret now.

`install.py --check` prints the key ids a runner holds and never
the values: the runner's key by its fingerprint, then any
additional ids.

## Planned rotation

1. Generate a 256-bit secret:
   ```
   openssl rand -hex 32
   ```
   Put it in config.json under `additional_secrets` with a new id.
   The runner imposes no pattern or length limit on these ids — it
   requires only a non-empty string (the `[A-Za-z0-9._-]{1,64}`
   pattern is enforced only by `install.py --additional-secret`).
   Leave `shared_secret` in place.
   (Note: `install.py --additional-secret KEY_ID` only stores the secret on
   fresh installs — on an existing Windows one-home install it is silently
   ignored, so edit the config directly.)
2. Restart the runner.
3. Tell the signer the new `key_id` and the new secret, in one prompt. From
   then on the signer sets `key_id` on every job (`send_job.py keyring add
   --secret <new> --key-id <new id> --runner <mailbox>` keeps the pair on the
   signer's side; `send_job.py key-id --secret <new>` prints the fingerprint
   if the new id is to be the secret's own name).
4. Confirm a job signed with the new id runs. Mail already in the inbox still
   runs — it was signed with the old secret.
5. Remove the old secret only after every signer sends the new `key_id`. Do
   not delete `shared_secret` while any signer still omits `key_id` or names
   it by its fingerprint. Restart again. A DTLS resumption ticket records
   the key that authenticated the session it was issued on, so a sender
   holding a ticket from the old secret is refused on its next resume and
   handshakes afresh under the new one (`send_dtls.py` does that itself and
   drops the ticket).

Never reuse a retired secret. Never put two values on one `key_id`.

---
*Side note: NIST SP 800-57 recommends an originator-usage period of
under 2 years for symmetric authentication keys. Ninety days sits
comfortably inside that.*
