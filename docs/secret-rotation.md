# Shared secret rotation

Rotate the shared secret every **90 days**.

Volume doesn't affect this: the secret never crosses the wire after setup,
only HMAC tags do, and tags don't leak the key at any message count.

## Other transports

The 90-day cadence is for email. A different transport — broader visibility,
weaker encryption, message logging, longer retention — warrants faster
rotation: every few weeks until you've measured the actual exposure.

## How to rotate (no downtime)

The runner verifies against a dict of secrets by `key_id`:

1. Add the new secret under `additional_secrets` (new `key_id`) — the old one
   keeps working.
2. Switch the signer to the new `key_id`.
3. Confirm jobs flow, then remove the old secret.

Never reuse a retired secret.
