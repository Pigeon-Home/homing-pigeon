# Asymmetric signing — design

*Not built. See docs/project/future.md. This document records the shape of a
migration from HMAC shared secrets to Ed25519 signatures, so
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
`signed body + sig` envelope stays, but `sig` becomes an Ed25519
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

- **Dependency.** Options:
  `cryptography` (C extension, heavy for the minimal-install story),
  `PyNaCl` (same), or a vendored pure-Python Ed25519 (~200 lines,
  slow but fine at job-submission rates). The pure-Python route fits
  the project's stdlib-only preference; it must be constant-time
  where it matters (it is, for verification, if written carefully —
  get this reviewed). A fourth option the plan asks us to evaluate is
  `ssh-keygen -Y` (below) — it may obsolete this whole question.
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

## Appendix: evaluating `ssh-keygen -Y` (plan M9)

The plan asks for an explicit evaluation of OpenSSH's `ssh-keygen -Y
sign` / `-Y verify` as the Ed25519 mechanism, because it is the only
option with no new Python dependency.

**How it would work.** The SI signs the normalized body bytes with
`ssh-keygen -Y sign -f <private-key> -n homing-pigeon`, producing an
armored signature placed in the `sig` field (or a companion field —
the armor is multi-line, so it needs a JSON-safe encoding). The
runner verifies with `ssh-keygen -Y verify -f allowed_signers -n
homing-pigeon -s <sig>`, where `allowed_signers` maps each `key_id`
to a public key line:

```
default@example.com namespaces="homing-pigeon" ssh-ed25519 AAAA...
```

The `-n` namespace binds the signature to this application, so a
signature minted for another purpose (git commits, SSH auth) cannot
be replayed as a job.

**In its favor.**
- Zero Python dependencies: no C extensions, no vendored crypto to
  own and get reviewed. OpenSSH ships on every target platform,
  including recent Windows.
- The crypto is maintained by someone else (OpenBSD) and is
  battle-tested.
- Key generation and management UX already exists
  (`ssh-keygen -t ed25519`); operators already know it.
- Verification-only on the runner, signing-only on the SI — the
  timing-side-channel concern that haunts pure-Python Ed25519
  applies to signing, which happens off-box.

**Against it.**
- Shelling out per message: a subprocess spawn on every poll hit.
  At job-submission rates (a handful of messages per poll, polls
  minutes apart) this is negligible, but it is a new failure mode
  (missing binary, PATH issues, Windows quoting).
- The armored signature is bulky (~0.5 KB base64-armored) versus
  64 bytes raw; fine for email, but the envelope grows.
- `allowed_signers` is a second key store beside `config.json`,
  with its own file-permission story (it must not be writable by
  the SI's key_id — it lives on the runner).
- Namespace discipline is load-bearing: if the namespace string is
  ever reused across applications, cross-protocol replay becomes
  possible. It must be a constant, not configurable.

**Recommendation.** The plan's lean is correct: `ssh-keygen -Y` is
the best first mechanism, behind a `signature_scheme` config key
(`hmac` today, `ssh-keygen` when implemented). It keeps the
stdlib-only story intact, outsources the crypto, and the costs
(subprocess per verify, bulky armor) are irrelevant at this
system's message rates. The vendored pure-Python verifier remains
the fallback if OpenSSH is ever unavailable on a target. Either
way, the `alg` field in the signed body would record which scheme
signed each message, so the audit log stays unambiguous during
rotation. (No `alg` field exists today; it arrives with the
scheme.)
