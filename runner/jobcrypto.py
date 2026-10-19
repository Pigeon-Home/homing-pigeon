"""Per-job encryption: confidentiality for the job object itself.

The HMAC signature authenticates a job; it does not hide it. Any
store-and-forward hop (above all the mailbox provider) can read a
signed job and its result. This module adds object encryption on
the same binding: the fully signed body is encrypted under a key
derived from the shared secret, wrapped in an envelope, and the
envelope is signed again with the same splice discipline as every
other body. A receiver verifies the envelope's signature BEFORE
attempting decryption, decrypts, and feeds the recovered signed
body through the ordinary verification path unchanged -- so an
encrypted job faces two signature checks and every check a
cleartext job faces.

Construction (standard library only; the runner takes no new
dependency):

- AEAD: ChaCha20-Poly1305, RFC 8439, implemented in pure Python.
- KDF: HKDF, RFC 5869, over HMAC-SHA-384. The master key is the
  selected shared secret's UTF-8 octets (the same key_id
  selection verification uses). The per-job key is
  HKDF(master, salt=nonce, info="homing-pigeon job-encryption v1",
  L=32).
- Nonce: 12 octets from secrets.token_bytes, fresh per message,
  carried in the envelope.
- AAD: job_id, key_id ("" for the default secret), and the
  algorithm string, UTF-8 encoded, joined by single NUL octets:
  job_id || 0x00 || key_id || 0x00 || alg. Binding the envelope
  to the job_id means an envelope replayed under a different
  subject does not decrypt.
- Tag comparison uses hmac.compare_digest. Every failure --
  malformed envelope, bad base64, unknown algorithm, tag
  mismatch -- raises JobCryptoError and no partial plaintext
  ever escapes.

There is NO forward secrecy, here or anywhere this construction
is described: the key derives from a static shared secret, so
compromise of the secret exposes every recorded encrypted job
and result, past and future. That is the stated price of
confidentiality on a store-and-forward binding with no session.

Stdlib only, Python 3.9+.
"""

import base64
import hashlib
import hmac
import secrets

ALG = "chacha20-poly1305/hkdf-sha384"
_KDF_INFO = b"homing-pigeon job-encryption v1"
_NONCE_LEN = 12
_TAG_LEN = 16
_KEY_LEN = 32


class JobCryptoError(ValueError):
    """Any envelope or AEAD failure. A ValueError so the mail
    path's existing rejection handling treats it as a bad body."""


# ------------------------------------------------------------------
# HKDF (RFC 5869) over a caller-chosen hash; SHA-384 in production.
# ------------------------------------------------------------------

def hkdf(ikm, salt, info, length, hashfn=hashlib.sha384):
    """RFC 5869 extract-and-expand. salt=None means HashLen zeros."""
    digest_size = hashfn().digest_size
    if length > 255 * digest_size:
        raise JobCryptoError("hkdf length too large")
    if salt is None:
        salt = b"\x00" * digest_size
    prk = hmac.new(salt, ikm, hashfn).digest()
    okm = b""
    block = b""
    counter = 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes([counter]),
                         hashfn).digest()
        okm += block
        counter += 1
    return okm[:length]


def _job_key(secret, nonce):
    if not isinstance(secret, str):
        raise JobCryptoError("secret must be a string")
    return hkdf(secret.encode("utf-8"), nonce, _KDF_INFO, _KEY_LEN)


def _aad(job_id, key_id):
    return (job_id.encode("utf-8") + b"\x00"
            + (key_id or "").encode("utf-8") + b"\x00"
            + ALG.encode("ascii"))


# ------------------------------------------------------------------
# ChaCha20 (RFC 8439 section 2.3/2.4)
# ------------------------------------------------------------------

def _rotl32(v, n):
    return ((v << n) & 0xFFFFFFFF) | (v >> (32 - n))


def _quarter_round(x, a, b, c, d):
    x[a] = (x[a] + x[b]) & 0xFFFFFFFF
    x[d] = _rotl32(x[d] ^ x[a], 16)
    x[c] = (x[c] + x[d]) & 0xFFFFFFFF
    x[b] = _rotl32(x[b] ^ x[c], 12)
    x[a] = (x[a] + x[b]) & 0xFFFFFFFF
    x[d] = _rotl32(x[d] ^ x[a], 8)
    x[c] = (x[c] + x[d]) & 0xFFFFFFFF
    x[b] = _rotl32(x[b] ^ x[c], 7)


def _chacha20_block(key, counter, nonce):
    const = [0x61707865, 0x3320646E, 0x79622D32, 0x6B206574]

    def words(data):
        return [int.from_bytes(data[i:i + 4], "little")
                for i in range(0, len(data), 4)]

    state = const + words(key) + [counter] + words(nonce)
    work = list(state)
    for _ in range(10):
        _quarter_round(work, 0, 4, 8, 12)
        _quarter_round(work, 1, 5, 9, 13)
        _quarter_round(work, 2, 6, 10, 14)
        _quarter_round(work, 3, 7, 11, 15)
        _quarter_round(work, 0, 5, 10, 15)
        _quarter_round(work, 1, 6, 11, 12)
        _quarter_round(work, 2, 7, 8, 13)
        _quarter_round(work, 3, 4, 9, 14)
    out = [(work[i] + state[i]) & 0xFFFFFFFF for i in range(16)]
    return b"".join(w.to_bytes(4, "little") for w in out)


def _chacha20_xor(key, nonce, counter, data):
    out = bytearray()
    ctr = counter
    for off in range(0, len(data), 64):
        block = _chacha20_block(key, ctr, nonce)
        chunk = data[off:off + 64]
        out.extend(b ^ k for b, k in zip(chunk, block))
        ctr += 1
    return bytes(out)


# ------------------------------------------------------------------
# Poly1305 (RFC 8439 section 2.5)
# ------------------------------------------------------------------

def _poly1305_mac(msg, key):
    r = int.from_bytes(key[:16], "little") & \
        0x0FFFFFFC0FFFFFFC0FFFFFFC0FFFFFFF
    s = int.from_bytes(key[16:], "little")
    p = (1 << 130) - 5
    acc = 0
    for off in range(0, len(msg), 16):
        chunk = msg[off:off + 16]
        n = int.from_bytes(chunk, "little") + (1 << (8 * len(chunk)))
        acc = ((acc + n) * r) % p
    tag = (acc + s) % (1 << 128)
    return tag.to_bytes(16, "little")


# ------------------------------------------------------------------
# AEAD (RFC 8439 section 2.8)
# ------------------------------------------------------------------

def _pad16(data):
    if len(data) % 16 == 0:
        return b""
    return b"\x00" * (16 - len(data) % 16)


def aead_encrypt(key, nonce, plaintext, aad):
    """Return ciphertext || tag (16-octet tag appended)."""
    poly_key = _chacha20_block(key, 0, nonce)[:32]
    ciphertext = _chacha20_xor(key, nonce, 1, plaintext)
    mac_data = (aad + _pad16(aad) + ciphertext + _pad16(ciphertext)
                + len(aad).to_bytes(8, "little")
                + len(ciphertext).to_bytes(8, "little"))
    return ciphertext + _poly1305_mac(mac_data, poly_key)


def aead_decrypt(key, nonce, ct_and_tag, aad):
    """Verify the tag (constant-time) and return the plaintext.

    Raises JobCryptoError on any failure; nothing partial escapes.
    """
    if len(ct_and_tag) < _TAG_LEN:
        raise JobCryptoError("ciphertext shorter than its tag")
    ciphertext, tag = ct_and_tag[:-_TAG_LEN], ct_and_tag[-_TAG_LEN:]
    poly_key = _chacha20_block(key, 0, nonce)[:32]
    mac_data = (aad + _pad16(aad) + ciphertext + _pad16(ciphertext)
                + len(aad).to_bytes(8, "little")
                + len(ciphertext).to_bytes(8, "little"))
    expect = _poly1305_mac(mac_data, poly_key)
    if not hmac.compare_digest(expect, tag):
        raise JobCryptoError("poly1305 tag mismatch")
    return _chacha20_xor(key, nonce, 1, ciphertext)


# ------------------------------------------------------------------
# The envelope
# ------------------------------------------------------------------

def is_envelope(payload):
    """True when a verified payload is an encryption envelope:
    exactly an hp_enc member, plus the optional key_id and the
    sig member verification adds -- nothing else."""
    if not isinstance(payload, dict):
        return False
    if not isinstance(payload.get("hp_enc"), dict):
        return False
    return set(payload) <= {"hp_enc", "key_id", "sig"}


def encrypt_body(signed_body, secret, job_id, key_id, sign):
    """Encrypt an already-signed body and sign the envelope.

    `sign` is the caller's sign_payload (dict, secret) -> str, so
    the envelope is serialized and spliced exactly as every other
    body on the wire. Returns the transmitted body text.
    """
    if not isinstance(signed_body, str):
        raise JobCryptoError("signed body must be a string")
    nonce = secrets.token_bytes(_NONCE_LEN)
    key = _job_key(secret, nonce)
    ct = aead_encrypt(key, nonce, signed_body.encode("utf-8"),
                      _aad(job_id, key_id))
    envelope = {
        "hp_enc": {
            "alg": ALG,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ct": base64.b64encode(ct).decode("ascii"),
        },
    }
    if key_id:
        envelope["key_id"] = key_id
    return sign(envelope, secret)


def _b64_field(enc, name):
    value = enc.get(name)
    if not isinstance(value, str):
        raise JobCryptoError(f"hp_enc.{name} missing or not a string")
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except Exception:
        raise JobCryptoError(f"hp_enc.{name} is not valid base64") \
            from None


def decrypt_body(payload, secret, job_id, key_id):
    """Decrypt a verified envelope payload back to the signed body
    it carries. The caller MUST have verified the envelope's
    signature first; this function assumes that gate has passed.
    Raises JobCryptoError on any defect."""
    if not is_envelope(payload):
        raise JobCryptoError("payload is not an encryption envelope")
    enc = payload["hp_enc"]
    if enc.get("alg") != ALG:
        raise JobCryptoError(f"unknown hp_enc alg {enc.get('alg')!r}")
    nonce = _b64_field(enc, "nonce")
    if len(nonce) != _NONCE_LEN:
        raise JobCryptoError("hp_enc.nonce must decode to 12 octets")
    ct = _b64_field(enc, "ct")
    if len(ct) < _TAG_LEN:
        raise JobCryptoError("hp_enc.ct shorter than its tag")
    key = _job_key(secret, nonce)
    plaintext = aead_decrypt(key, nonce, ct, _aad(job_id, key_id))
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError:
        raise JobCryptoError("decrypted body is not UTF-8") from None
