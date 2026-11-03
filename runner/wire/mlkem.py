"""ML-KEM-768 (FIPS 203), pure Python, stdlib only.

The post-quantum half of the hybrid key exchange the version
3 profile adds to the DTLS engine (X25519MLKEM768, RFC
10024): runner.wire.dtlsproto holds this module's
encapsulation key in the client's hybrid share, encapsulates
to it on the responder side, and decapsulates on the client
side, concatenating the secrets in the order RFC 10024
section 4.3 specifies.

This is a straight implementation of FIPS 203 for the
ML-KEM-768 parameter set only (k = 3, eta1 = eta2 = 2,
du = 10, dv = 4): KeyGen, Encaps, and Decaps with their
internal forms exposed for the known-answer tests, which pin
this code byte-exact against the NIST ACVP vectors in
runner/tests/fixtures/mlkem768_acvp.json.

Honest limits, stated once here and in the proof record:
this implementation is NOT constant-time. Its loops,
comparisons, and rejection sampling all branch on secret
data, exactly as the pure-Python X25519 beside it in
dtlsproto does; it is written for correctness against the
standard and for a profile whose endpoints are this
project's own endpoints, not as a side-channel-hardened
KEM. The decapsulation failure path follows FIPS 203
Algorithm 19 (implicit rejection): a ciphertext that does
not re-encrypt to itself yields the rejection value derived
from z, never an error and never the real secret.

Stdlib only, Python 3.9+.
"""

import hashlib
import hmac as _hmac
import secrets

# FIPS 203 parameters for ML-KEM-768.
N = 256
Q = 3329
K = 3
ETA1 = 2
ETA2 = 2
DU = 10
DV = 4

EK_BYTES = 384 * K + 32            # 1184
DK_BYTES = 768 * K + 96            # 2400
CT_BYTES = 32 * (DU * K + DV)      # 1088
SS_BYTES = 32
SEED_BYTES = 32                    # d and z are 32 octets each


class MlkemError(ValueError):
    """A malformed input to the KEM: wrong length, or an
    encapsulation key that fails the FIPS 203 checks. Raised
    before any secret is produced; decapsulation of a merely
    wrong ciphertext is not an error (implicit rejection)."""


# ------------------------------------------------------------------
# Field and NTT helpers (FIPS 203 section 4.3)
# ------------------------------------------------------------------

def _bitrev7(i):
    return int("{:07b}".format(i)[::-1], 2)


# zetas[k] = 17 ** BitRev7(k) mod Q, k = 1..127 (the NTT
# twiddles); the inverse table holds each twiddle's modular
# inverse in the order the inverse transform consumes them.
_ZETAS = [0] + [pow(17, _bitrev7(i), Q) for i in range(1, 128)]
_ZETAS_INV = [0] + [pow(_ZETAS[i], Q - 2, Q) for i in range(1, 128)]
# gamma for the base-case multiplication of the i-th pair:
# 17 ** (2 * BitRev7(i) + 1) mod Q.
_GAMMAS = [pow(17, 2 * _bitrev7(i) + 1, Q) for i in range(128)]
_INTT_SCALE = pow(128, Q - 2, Q)   # 3303


def _ntt(f):
    """Algorithm 9: the number-theoretic transform."""
    out = list(f)
    k = 1
    length = 128
    while length >= 2:
        for start in range(0, 256, 2 * length):
            zeta = _ZETAS[k]
            k += 1
            for j in range(start, start + length):
                t = zeta * out[j + length] % Q
                out[j + length] = (out[j] - t) % Q
                out[j] = (out[j] + t) % Q
        length //= 2
    return out


def _intt(f):
    """Algorithm 10: the inverse transform. Each inverse
    butterfly pairs with the forward butterfly at the same
    (length, start), so it takes that twiddle's modular
    inverse -- the forward level for a given length starts
    at k = 128 // length and counts up per block. The 1/2 of
    each butterfly is folded into the closing multiply by
    128 ** -1."""
    out = list(f)
    length = 2
    while length <= 128:
        k = 128 // length
        for start in range(0, 256, 2 * length):
            zeta = _ZETAS_INV[k]
            k += 1
            for j in range(start, start + length):
                t = out[j]
                u = out[j + length]
                out[j] = (t + u) % Q
                out[j + length] = (t - u) * zeta % Q
        length *= 2
    return [x * _INTT_SCALE % Q for x in out]


def _ntt_mul(a, b):
    """Algorithm 12: multiplication in the NTT domain, as 128
    base-case products of degree-1 polynomials."""
    out = [0] * 256
    for i in range(128):
        a0, a1 = a[2 * i], a[2 * i + 1]
        b0, b1 = b[2 * i], b[2 * i + 1]
        gamma = _GAMMAS[i]
        out[2 * i] = (a0 * b0 + a1 * b1 * gamma) % Q
        out[2 * i + 1] = (a0 * b1 + a1 * b0) % Q
    return out


def _vec_ntt(v):
    return [_ntt(p) for p in v]


def _vec_add(a, b):
    return [[(x + y) % Q for x, y in zip(pa, pb)]
            for pa, pb in zip(a, b)]


def _mat_vec_mul(m, v):
    """NTT-domain matrix (k x k) times vector (k)."""
    out = []
    for i in range(K):
        acc = [0] * 256
        for j in range(K):
            prod = _ntt_mul(m[i][j], v[j])
            acc = [(x + y) % Q for x, y in zip(acc, prod)]
        out.append(acc)
    return out


def _vec_dot_ntt(a, b):
    acc = [0] * 256
    for i in range(K):
        prod = _ntt_mul(a[i], b[i])
        acc = [(x + y) % Q for x, y in zip(acc, prod)]
    return acc


# ------------------------------------------------------------------
# Byte encoding and sampling (FIPS 203 sections 4.1, 4.2)
# ------------------------------------------------------------------

def _byte_encode(d, f):
    bits = []
    for coeff in f:
        value = coeff % (Q if d == 12 else (1 << d))
        for i in range(d):
            bits.append((value >> i) & 1)
    out = bytearray(len(bits) // 8)
    for idx, bit in enumerate(bits):
        if bit:
            out[idx // 8] |= 1 << (idx % 8)
    return bytes(out)


def _byte_decode(d, data):
    if len(data) != 32 * d:
        raise MlkemError("byte decode input has the wrong length")
    coeffs = []
    for i in range(256):
        value = 0
        for j in range(d):
            idx = i * d + j
            bit = (data[idx // 8] >> (idx % 8)) & 1
            value |= bit << j
        coeffs.append(value % Q if d == 12 else value)
    return coeffs


def _sample_ntt(seed):
    """Algorithm 7: rejection sampling from a SHAKE128 stream.
    The stream is taken in growing prefixes; SHAKE output is a
    prefix stream, so a longer digest extends, never changes,
    the bytes already read."""
    size = 1536
    while True:
        stream = hashlib.shake_128(seed).digest(size)
        coeffs = []
        pos = 0
        while len(coeffs) < 256 and pos + 3 <= len(stream):
            d1 = stream[pos] + 256 * (stream[pos + 1] % 16)
            d2 = stream[pos + 1] // 16 + 16 * stream[pos + 2]
            pos += 3
            if d1 < Q:
                coeffs.append(d1)
            if d2 < Q and len(coeffs) < 256:
                coeffs.append(d2)
        if len(coeffs) == 256:
            return coeffs
        size *= 2


def _sample_cbd(eta, seed):
    """Algorithm 8: the centered binomial distribution, from
    a SHAKE256 stream of 64 * eta octets."""
    stream = hashlib.shake_256(seed).digest(64 * eta)
    as_int = int.from_bytes(stream, "little")
    coeffs = []
    for i in range(256):
        a = 0
        b = 0
        base = 2 * i * eta
        for j in range(eta):
            a += (as_int >> (base + j)) & 1
            b += (as_int >> (base + eta + j)) & 1
        coeffs.append((a - b) % Q)
    return coeffs


def _compress(d, f):
    top = 1 << d
    return [(((x << d) + Q // 2) // Q) % top for x in f]


def _decompress(d, f):
    return [(x * Q + (1 << (d - 1))) >> d for x in f]


def _matrix_a(rho):
    """A[i][j] = SampleNTT(rho || j || i), in the NTT domain."""
    return [[_sample_ntt(rho + bytes([j, i])) for j in range(K)]
            for i in range(K)]


def _cbd_vector(sigma, first_nonce, eta):
    return [_sample_cbd(eta, sigma + bytes([first_nonce + i]))
            for i in range(K)]


# ------------------------------------------------------------------
# K-PKE (FIPS 203 section 5)
# ------------------------------------------------------------------

def kpke_keygen(d):
    """Algorithm 13. d is 32 octets; returns (ek_pke, dk_pke)."""
    if len(d) != SEED_BYTES:
        raise MlkemError("K-PKE key generation seed is 32 octets")
    expanded = hashlib.sha3_512(d + bytes([K])).digest()
    rho, sigma = expanded[:32], expanded[32:]
    a = _matrix_a(rho)
    s = _cbd_vector(sigma, 0, ETA1)
    e = _cbd_vector(sigma, K, ETA1)
    s_hat = _vec_ntt(s)
    e_hat = _vec_ntt(e)
    t_hat = _vec_add(_mat_vec_mul(a, s_hat), e_hat)
    ek = b"".join(_byte_encode(12, p) for p in t_hat) + rho
    dk = b"".join(_byte_encode(12, p) for p in s_hat)
    return ek, dk


def kpke_encrypt(ek, m, r):
    """Algorithm 14. ek is 1184 octets, m and r 32 each;
    returns the 1088-octet ciphertext."""
    if len(ek) != EK_BYTES:
        raise MlkemError("K-PKE encryption key is 1184 octets")
    if len(m) != 32 or len(r) != 32:
        raise MlkemError("K-PKE message and randomness are 32 octets")
    t_hat = [_byte_decode(12, ek[i * 384:(i + 1) * 384])
             for i in range(K)]
    rho = ek[384 * K:]
    a = _matrix_a(rho)
    y = _cbd_vector(r, 0, ETA1)
    e1 = _cbd_vector(r, K, ETA2)
    e2 = _sample_cbd(ETA2, r + bytes([2 * K]))
    y_hat = _vec_ntt(y)
    a_t = [[a[j][i] for j in range(K)] for i in range(K)]
    u = _vec_add([_intt(p) for p in _mat_vec_mul(a_t, y_hat)], e1)
    mu = _decompress(1, _byte_decode(1, m))
    v_inner = _intt(_vec_dot_ntt(t_hat, y_hat))
    v = [(x + y + z) % Q for x, y, z in zip(v_inner, e2, mu)]
    c1 = b"".join(_byte_encode(DU, _compress(DU, p)) for p in u)
    c2 = _byte_encode(DV, _compress(DV, v))
    return c1 + c2


def kpke_decrypt(dk, c):
    """Algorithm 15. dk is the 1152-octet K-PKE decapsulation
    key; c is 1088 octets; returns the 32-octet message."""
    if len(dk) != 384 * K:
        raise MlkemError("K-PKE decapsulation key is 1152 octets")
    if len(c) != CT_BYTES:
        raise MlkemError("K-PKE ciphertext is 1088 octets")
    c1, c2 = c[:32 * DU * K], c[32 * DU * K:]
    u = [_decompress(DU, _byte_decode(
        DU, c1[i * 32 * DU:(i + 1) * 32 * DU])) for i in range(K)]
    v = _decompress(DV, _byte_decode(DV, c2))
    s_hat = [_byte_decode(12, dk[i * 384:(i + 1) * 384])
             for i in range(K)]
    w_inner = _intt(_vec_dot_ntt(s_hat, _vec_ntt(u)))
    w = [(x - y) % Q for x, y in zip(v, w_inner)]
    return _byte_encode(1, _compress(1, w))


# ------------------------------------------------------------------
# Key checks (FIPS 203 section 7)
# ------------------------------------------------------------------

def encapsulation_key_check(ek):
    """Section 7.2: the encapsulation key is 1184 octets and
    passes the modulus check -- every 12-bit field of the
    encoded t vector is a value in Z_q, which re-encoding
    proves byte-exact."""
    if len(ek) != EK_BYTES:
        return False
    head = ek[:384 * K]
    try:
        decoded = [_byte_decode(12, head[i * 384:(i + 1) * 384])
                   for i in range(K)]
    except MlkemError:
        return False
    return b"".join(_byte_encode(12, p) for p in decoded) == head


def decapsulation_key_check(dk):
    """Section 7.3: the decapsulation key is 2400 octets and
    its stored hash equals H(ek) for the ek it carries."""
    if len(dk) != DK_BYTES:
        return False
    ek = dk[384 * K:384 * K + EK_BYTES]
    stored = dk[384 * K + EK_BYTES:384 * K + EK_BYTES + 32]
    return _hmac.compare_digest(
        hashlib.sha3_256(ek).digest(), stored)


# ------------------------------------------------------------------
# ML-KEM (FIPS 203 section 6)
# ------------------------------------------------------------------

def keygen_internal(d, z):
    """Algorithm 16. (d, z) are 32 octets each; returns
    (ek, dk) of 1184 and 2400 octets."""
    if len(d) != SEED_BYTES or len(z) != SEED_BYTES:
        raise MlkemError("ML-KEM seeds d and z are 32 octets each")
    ek, dk_pke = kpke_keygen(d)
    dk = dk_pke + ek + hashlib.sha3_256(ek).digest() + z
    return ek, dk


def keygen(rng=None):
    """A fresh (ek, dk) from the given randomness source
    (a callable like secrets.token_bytes)."""
    rng = rng or secrets.token_bytes
    return keygen_internal(rng(32), rng(32))


def encaps_internal(ek, m):
    """Algorithm 17. m is 32 octets; returns (shared secret,
    ciphertext). The encapsulation key is checked first, as
    FIPS 203 section 7.2 requires of encapsulation."""
    if len(m) != 32:
        raise MlkemError("ML-KEM encapsulation randomness is 32 octets")
    if not encapsulation_key_check(ek):
        raise MlkemError("encapsulation key fails the FIPS 203 check")
    joined = hashlib.sha3_512(m + hashlib.sha3_256(ek).digest())
    secret, r = joined.digest()[:32], joined.digest()[32:]
    return secret, kpke_encrypt(ek, m, r)


def encaps(ek, rng=None):
    """Encapsulate to ek with fresh randomness; returns
    (shared secret, ciphertext)."""
    rng = rng or secrets.token_bytes
    return encaps_internal(ek, rng(32))


def decaps(dk, c):
    """Algorithm 19, with implicit rejection. A ciphertext of
    the wrong length, or a decapsulation key that fails its
    checks, is refused with MlkemError; a well-shaped but
    wrong ciphertext returns the rejection secret derived
    from z, indistinguishable in shape from a real one."""
    if len(c) != CT_BYTES:
        raise MlkemError("ML-KEM ciphertext is 1088 octets")
    if not decapsulation_key_check(dk):
        raise MlkemError("decapsulation key fails the FIPS 203 check")
    dk_pke = dk[:384 * K]
    ek = dk[384 * K:384 * K + EK_BYTES]
    h = dk[384 * K + EK_BYTES:384 * K + EK_BYTES + 32]
    z = dk[384 * K + EK_BYTES + 32:]
    m_prime = kpke_decrypt(dk_pke, c)
    joined = hashlib.sha3_512(m_prime + h).digest()
    secret_prime, r_prime = joined[:32], joined[32:]
    rejection = hashlib.shake_256(z + c).digest(32)
    c_prime = kpke_encrypt(ek, m_prime, r_prime)
    if _hmac.compare_digest(c, c_prime):
        return secret_prime
    return rejection
