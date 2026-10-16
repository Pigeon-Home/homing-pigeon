# Shared secret rotation

Rotate the shared secret every **90 days**. The period is a calendar cap: the
secret lives on disk and gets pasted into chat to provision signers. It is not
a function of how many jobs you send.

HMAC-SHA-384 tags do not leak the key at any message count. One captured
message is already enough to test a guess, and a billion more do not make that
guess cheaper. Pigeon mail never carries the secret, only the tag.

## What the runner actually loads

A job with no `key_id` verifies against `shared_secret`. A job with a `key_id`
verifies against `additional_secrets`. Secrets are read at startup — editing
config.json takes effect on restart.

A new `key_id` does not inherit `key_policies`. If
`key_policies_default_deny` is false (the default), the new key is
unrestricted. If true, a new id with no policy is refused — copy the policy
entry onto the new id.

## Planned rotation

1. Generate a 256-bit secret:
   ```
   openssl rand -hex 32
   ```
   Put it in config.json under `additional_secrets` with a new id.
   `KEY_ID` must match `[A-Za-z0-9._-]{1,64}`. Leave `shared_secret` in place.
   (Note: `install.py --additional-secret KEY_ID` only stores the secret on
   fresh installs — on an existing Windows one-home install it is silently
   ignored, so edit the config directly.)
2. Restart the runner.
3. Tell the signer the new `key_id` and the new secret, in one prompt. From
   then on the signer sets `key_id` on every job.
4. Confirm a job signed with the new id runs. Mail already in the inbox still
   runs — it was signed with the old secret.
5. Remove the old secret only after every signer sends the new `key_id`. Do
   not delete `shared_secret` while any signer still omits `key_id`. Restart
   again.

Never reuse a retired secret. Never put two values on one `key_id`.

---
*Side note: NIST SP 800-57 caps symmetric authentication keys at under
2 years. Ninety days sits comfortably inside that.*
