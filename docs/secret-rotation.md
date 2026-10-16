# Shared secret rotation

Rotate the shared secret every **90 days**.

Volume doesn't affect this: the secret never crosses the wire after setup,
only HMAC tags do, and tags don't leak the key at any message count. Email
gets the 90-day cadence not because it's low-volume, but because of its
exposure properties: TLS in transit, a single mailbox, no shared topics, no
third-party message logging.

## How to rotate (no downtime)

The runner verifies against a dict of secrets by `key_id`:

1. Add the new secret under `additional_secrets` (new `key_id`) — the old one
   keeps working.
2. Switch the signer to the new `key_id`.
3. Confirm jobs flow, then remove the old secret.

Never reuse a retired secret.

---
*Side note: NIST SP 800-57 caps symmetric authentication keys at under
2 years. Ninety days sits comfortably inside that.*
