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

- AEAD: AES-256-GCM, NIST SP 800-38D, implemented in pure Python.
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

ALG = "aes-256-gcm/hkdf-sha384"
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
    # The AAD binds the envelope to its job and key. Both names must
    # be text: a caller that hands over a stash record's missing
    # job_id, or a number, gets the module's refusal, not an
    # AttributeError (the de_dust corpus's first finding).
    if not isinstance(job_id, str):
        raise JobCryptoError("job_id must be a string")
    if key_id is None:
        key_id = ""
    if not isinstance(key_id, str):
        raise JobCryptoError("key_id must be a string")
    try:
        return (job_id.encode("utf-8") + b"\x00"
                + key_id.encode("utf-8") + b"\x00"
                + ALG.encode("ascii"))
    except UnicodeEncodeError:
        raise JobCryptoError("job_id and key_id must be UTF-8 text") \
            from None


# ------------------------------------------------------------------
# AES-256 (FIPS 197) and GCM (NIST SP 800-38D)
# ------------------------------------------------------------------

_SBOX = bytes((
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
))

_RCON = (0x00,0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36)


def _xtime(a):
    return (((a << 1) ^ 0x1b) & 0xff) if (a & 0x80) else ((a << 1) & 0xff)


def _aes256_expand(key):
    """Key expansion for AES-256. Returns list of 15 16-byte round keys."""
    assert len(key) == 32
    # Nk=8, Nr=14, Nb=4 → 60 words
    w = [int.from_bytes(key[i:i+4], "big") for i in range(0, 32, 4)]
    for i in range(8, 60):
        temp = w[i-1]
        if i % 8 == 0:
            # RotWord + SubWord + Rcon
            temp = ((temp << 8) | (temp >> 24)) & 0xffffffff
            temp = ((_SBOX[(temp >> 24) & 0xff] << 24) |
                    (_SBOX[(temp >> 16) & 0xff] << 16) |
                    (_SBOX[(temp >> 8) & 0xff] << 8) |
                    _SBOX[temp & 0xff])
            temp ^= (_RCON[i // 8] << 24)
        elif i % 8 == 4:
            temp = ((_SBOX[(temp >> 24) & 0xff] << 24) |
                    (_SBOX[(temp >> 16) & 0xff] << 16) |
                    (_SBOX[(temp >> 8) & 0xff] << 8) |
                    _SBOX[temp & 0xff])
        w.append(w[i-8] ^ temp)
    return [b"".join(w[i+j].to_bytes(4, "big") for j in range(4))
            for i in range(0, 60, 4)]


def _aes_encrypt_block(block, round_keys):
    """Encrypt one 16-byte block with pre-expanded round keys."""
    # Flat 16-byte state, column-major indexing: state[r + 4*c]
    state = list(block)
    # AddRoundKey
    def add_round_key(st, rk):
        return [st[i] ^ rk[i] for i in range(16)]
    state = add_round_key(state, round_keys[0])
    for rnd in range(1, 14):
        # SubBytes
        state = [_SBOX[b] for b in state]
        # ShiftRows (row r shifted left by r)
        state = [
            state[0], state[5], state[10], state[15],
            state[4], state[9], state[14], state[3],
            state[8], state[13], state[2], state[7],
            state[12], state[1], state[6], state[11],
        ]
        # MixColumns
        def mix(col):
            a, b, c, d = col
            return [
                _xtime(a) ^ _xtime(b) ^ b ^ c ^ d,
                a ^ _xtime(b) ^ _xtime(c) ^ c ^ d,
                a ^ b ^ _xtime(c) ^ _xtime(d) ^ d,
                _xtime(a) ^ a ^ b ^ c ^ _xtime(d),
            ]
        cols = [mix(state[c*4:(c+1)*4]) for c in range(4)]
        state = [b & 0xff for col in cols for b in col]
        state = add_round_key(state, round_keys[rnd])
    # Final
    state = [_SBOX[b] for b in state]
    state = [
        state[0], state[5], state[10], state[15],
        state[4], state[9], state[14], state[3],
        state[8], state[13], state[2], state[7],
        state[12], state[1], state[6], state[11],
    ]
    state = add_round_key(state, round_keys[14])
    return bytes(state)


def _ghash(h, data):
    """GHASH with GCM bit ordering (NIST SP 800-38D)."""
    # Reflect H once
    def reflect128(n):
        r = 0
        for i in range(128):
            if n & (1 << i):
                r |= 1 << (127 - i)
        return r
    h_ref = reflect128(int.from_bytes(h, "big"))
    y = 0
    for i in range(0, len(data), 16):
        block = reflect128(int.from_bytes(data[i:i+16], "big"))
        y ^= block
        # Multiply y * h_ref in the reflected domain
        z = 0
        v = h_ref
        for bit in range(128):
            if y & (1 << bit):
                z ^= v
            if v & (1 << 127):
                v = ((v << 1) & ((1<<128)-1)) ^ 0x87
            else:
                v = (v << 1) & ((1<<128)-1)
        y = z
    return reflect128(y).to_bytes(16, "big")


def _inc32(block):
    n = int.from_bytes(block[12:], "big")
    return block[:12] + ((n + 1) & 0xffffffff).to_bytes(4, "big")


def aead_encrypt(key, nonce, plaintext, aad):
    if len(key) != _KEY_LEN or len(nonce) != _NONCE_LEN:
        raise JobCryptoError("aead key must be 32 octets and nonce 12")
    rk = _aes256_expand(key)
    h = _aes_encrypt_block(b"\x00"*16, rk)
    j0 = nonce + b"\x00\x00\x00\x01"
    # CTR
    counter = _inc32(j0)
    ct = bytearray()
    for off in range(0, len(plaintext), 16):
        ks = _aes_encrypt_block(counter, rk)
        chunk = plaintext[off:off+16]
        ct.extend(a ^ b for a, b in zip(chunk, ks))
        counter = _inc32(counter)
    ct = bytes(ct)
    def pad(d):
        r = len(d) % 16
        return d if r == 0 else d + b"\x00"*(16-r)
    g_in = (pad(aad) + pad(ct)
            + (len(aad)*8).to_bytes(8, "big")
            + (len(ct)*8).to_bytes(8, "big"))
    s = _ghash(h, g_in)
    tag = bytes(a ^ b for a, b in zip(s, _aes_encrypt_block(j0, rk)))
    return ct + tag


def aead_decrypt(key, nonce, ct_and_tag, aad):
    if len(key) != _KEY_LEN or len(nonce) != _NONCE_LEN:
        raise JobCryptoError("aead key must be 32 octets and nonce 12")
    if len(ct_and_tag) < _TAG_LEN:
        raise JobCryptoError("ciphertext shorter than its tag")
    ct, tag = ct_and_tag[:-16], ct_and_tag[-16:]
    rk = _aes256_expand(key)
    h = _aes_encrypt_block(b"\x00"*16, rk)
    j0 = nonce + b"\x00\x00\x00\x01"
    def pad(d):
        r = len(d) % 16
        return d if r == 0 else d + b"\x00"*(16-r)
    g_in = (pad(aad) + pad(ct)
            + (len(aad)*8).to_bytes(8, "big")
            + (len(ct)*8).to_bytes(8, "big"))
    s = _ghash(h, g_in)
    expect = bytes(a ^ b for a, b in zip(s, _aes_encrypt_block(j0, rk)))
    if not hmac.compare_digest(expect, tag):
        raise JobCryptoError("gcm tag mismatch")
    counter = _inc32(j0)
    pt = bytearray()
    for off in range(0, len(ct), 16):
        ks = _aes_encrypt_block(counter, rk)
        chunk = ct[off:off+16]
        pt.extend(a ^ b for a, b in zip(chunk, ks))
        counter = _inc32(counter)
    return bytes(pt)


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
