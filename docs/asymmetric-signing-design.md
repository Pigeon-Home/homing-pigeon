# Asymmetric signing — design (M9)

*Design only. Not implemented. This document records the shape of a
future migration from HMAC shared secrets to Ed25519 signatures, so
the work can be picked up without re-deriving the tradeoffs.*

## The problem with the current scheme

Today every signer shares one HMAC-SHA-384 secret with the runner
(PROTOCOL.md section 8). That has three costs:

1. **The secret travels.** It must be given to the cloud SI over some
   channel, and anyone who sees it can sign forever.
2. **Offline brute force.** Anyone holding one signed message can
   attack the HMAC key offline, which is why the secret needs 128+
   bits of real entropy and the runner refuses weak ones.
3. **No separation of sign and verify.** The runner must hold the same
   secret it verifies with; a read of `config.json` (or a secret file)
   is total compromise, not just verification-key disclosure.

None of this is fatal for the current trust model — the secret *is*
the root credential and is guarded like one — but it puts a ceiling
on how far the key hierarchy can go (per-sensor keys, per-key
policies, and the audience binding in M5 all still bottom out at
"whoever holds the secret signs").

## Proposed design

The SI holds an Ed25519 private key. The runner holds only public
keys, one per `key_id`. The wire format does not change shape: the
`signed body + hex sig` envelope stays, but `sig` becomes an Ed25519
signature over the same normalized body bytes, and `key_id` resolves
to a public key instead of a secret.

```
"signing": {
  "algorithm": "ed25519",
  "public_keys": {
    "": "<hex 32-byte public key>",
    "sensor-1": "<hex 32-byte public key>"
  }
}
```

Verification (`verify_body_keyed` and its callers) becomes
`verify_body` with a verifier per key: HMAC for legacy keys, Ed25519
for new ones. The `key_id` multiplexing, replay cache, audience
binding, and policy checks all sit above the signature algorithm and
do not change.

## Migration

1. Add the `signing` block alongside `additional_secrets`. A key_id
   present in both is a startup error.
2. The SI generates a keypair, sends the public key out of band once
   (the existing "show the secret once" ceremony in the setup wizard
   becomes "show the public key once" — notably, the public key is
   *not* sensitive, so the ceremony gets simpler, not harder).
3. Dual-verify during rotation: accept both for a window, then remove
   the HMAC secret. The audit log records which algorithm verified
   each message (`alg: hmac-sha384 | ed25519`).
4. The setup wizard (`--setup`) generates an Ed25519 keypair for new
   signers instead of a shared secret.

## Open questions

- **Dependency.** The stdlib has no Ed25519 (as of Python 3.12). Options:
  `cryptography` (C extension, heavy for the minimal-install story),
  `PyNaCl` (same), or a vendored pure-Python Ed25519 (~200 lines,
  slow but fine at job-submission rates). The pure-Python route fits
  the project's stdlib-only preference; it must be constant-time
  where it matters (it is, for verification, if written carefully —
  get this reviewed).
- **What HMAC still buys.** HMAC-SHA-384 is not broken; the migration
  is about key management, not algorithm strength. There is no rush.
- **Revocation.** A compromised SI private key needs revocation: remove
  the public key from config and restart. No CRL/OCSP — the config
  *is* the revocation list. Document that rotation means a restart.
- **Non-repudiation.** Ed25519 gives it; HMAC doesn't. Decide whether
  the audit log should start asserting "key X signed job Y" as a
  forensic claim (it shouldn't, until the migration is complete).

## Why not now

The HMAC scheme matches the current deployment reality: one owner,
one SI, one box. Asymmetric signing pays off when there are many
signers with different trust levels (the sensor keys in
`key_policies` are the first taste). Build it when the second
untrusted signer appears, not before.
