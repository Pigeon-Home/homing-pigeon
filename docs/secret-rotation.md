# Shared secret rotation

## Recommendation

Rotate the shared secret every **90 days**.

## Why 90 days is fine for email

After setup, the secret itself never traverses the wire again — only
HMAC-SHA384 tags do. A tag leaks nothing about the key no matter how many
emails you send: ten jobs a day and ten thousand jobs a day are equally safe
from a cryptographic standpoint. Transit is protected by TLS, and the mailbox
is the only party that ever sees the signed bodies.

So for email, volume is not the risk. The residual risk is **endpoint
compromise**: someone getting the secret out of the runner's config, a backup,
or the owner's records. Rotation doesn't prevent that — it bounds it. A
90-day rotation means a quietly stolen secret is useful for at most 90 days.

## Why other transports may need faster rotation

The 90-day guidance is for email. A different transport changes the exposure,
so re-evaluate:

- **Visibility:** a shared queue topic or pub/sub channel may be readable by
  more parties than a single mailbox.
- **Transport encryption:** not every transport is TLS-everywhere; some log
  message bodies or headers where the secret (or material around it) could land.
- **Retention:** a transport that archives messages indefinitely extends the
  lifetime of anything that leaks into them.

If the transport is weaker than email on any of these, rotate faster — every few
weeks is a sane starting point — until you've measured the actual exposure.

## How to rotate (no downtime)

The runner verifies against a dict of secrets, selected by the job's `key_id`
(`verify_body_keyed`). That makes rotation graceful:

1. Generate the new secret.
2. Add it under `additional_secrets` in the runner config (a new `key_id`).
   The old secret keeps working — nothing breaks mid-rotation.
3. Switch the signer (`send_job.py` / the cloud SI) to the new `key_id`.
4. Confirm jobs flow, then remove the old secret from the config.

Never reuse a retired secret, and never put the new secret in the same place
the old one lived if you suspect the old one was compromised — rotate the
storage too, not just the value.

## What rotation doesn't fix

Rotation bounds the blast radius of a stolen secret; it does not prevent the
theft. If the runner's config file itself is compromised, the attacker gets
the new secret the moment you install it. Endpoint hygiene (locked-down user,
0600 config, the ACL story in `docs/security-gaps.md`) is what keeps the
secret secret. Rotation is the second line, not the first.
