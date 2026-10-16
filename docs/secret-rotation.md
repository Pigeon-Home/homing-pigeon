# Shared secret rotation

Rotate the shared secret every **90 days**. This is time-based, not
volume-based — deliberately so.

## Why time, not exchanges

After setup, the secret never crosses the wire — only HMAC-SHA384 tags do,
and a tag leaks nothing about the key. Ten jobs a day and ten thousand are
cryptographically identical, so counting exchanges is the wrong axis. Rotation
is a time question: how long should a single key be the one that matters.

NIST SP 800-57 caps symmetric authentication keys at under 2 years (a ceiling,
not a target), shortening with exposure. Ninety days sits comfortably inside
that.

## Other transports

The 90-day guidance is for email. A different transport changes the exposure:
broader visibility (shared topics), weaker encryption, message logging or
indefinite retention. If any of those apply, rotate every few weeks until
you've measured the actual exposure.

## How to rotate (no downtime)

The runner verifies against a dict of secrets by `key_id`, so:

1. Add the new secret under `additional_secrets` (new `key_id`) — the old one
   keeps working.
2. Switch the signer to the new `key_id`.
3. Confirm jobs flow, then remove the old secret.

Never reuse a retired secret.
