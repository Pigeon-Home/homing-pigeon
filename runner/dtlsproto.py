"""A bounded DTLS 1.3 profile: the DTLS direct binding of
protocol version 1.

This module implements exactly the profile the IETF draft's
DTLS binding section specifies -- no more. Both endpoints of
every session in the project run this code (the dtls transport
extension on the runner side, runner/cloud/send_dtls.py on the SI
side), and the profile is deliberately narrow:

- DTLS 1.3 (RFC 9147) records and handshake, ONE ciphersuite:
  TLS_AES_256_GCM_SHA384. The AEAD is
  runner.jobcrypto's AES-256-GCM, reused as-is;
  DTLS differs from the per-job envelope in its key schedule,
  which needs raw HKDF-Expand against derived secrets (the
  envelope module's hkdf() is extract+expand for its own
  construction), so the small expand/label helpers live here,
  next to the schedule they serve.
- Authentication is PSK-only: the shared secret is the
  external pre-shared key. Identities: "homing-pigeon" names
  the default secret, "homing-pigeon:<key_id>" names an
  additional secret; resumption tickets are opaque.
- Key exchange is psk_dhe_ke ONLY (DRU's hard rule): an
  ephemeral X25519 share rides every handshake, full or
  resumed. psk_ke is never offered and never accepted, so a
  recorded session stays sealed even if the secret later
  leaks -- perfect forward secrecy is enforced, not offered.
- HelloRetryRequest with a stateless cookie on EVERY first
  contact: address validation before the server sends
  anything larger than the retry itself (anti-amplification:
  the server is stateless until the cookie comes back).
- Connection IDs (RFC 9146) in both directions, so a NAT
  rebinding (a new source port) does not kill the session.
- Epochs follow RFC 9147: 0 plaintext (the first flight, in
  legacy DTLSPlaintext record form so a peer can find the
  version), 1 never used (no 0-RTT, no early data, ever),
  2 handshake traffic, 3 application traffic (4+ after a
  KeyUpdate, which this profile answers but never starts).
- The record AEAD nonce is the traffic IV XORed with the
  96-bit big-endian value (epoch << 48) | sequence -- the
  DTLS combined sequence construction, because sequence
  numbers restart per epoch and the epoch is a nonce input.
- Application framing: one uint32 length prefix per message
  over the record stream. The first application message on
  every session is the runner's greeting (see the dtls
  transport extension); jobs are never accepted before it.

The cores are transport-agnostic: feed() takes datagrams and
returns datagrams; the extension and the client own sockets.
Time is an argument, never read from a wall clock inside, so
tests drive retransmission timers deterministically.

Stdlib only, Python 3.9+.
"""

import hashlib
import hmac
import json
import secrets

try:  # package context (runner.dtlsproto)
    from runner import jobcrypto
except Exception:  # pragma: no cover - sibling context
    try:
        from . import jobcrypto  # type: ignore
    except Exception:
        import jobcrypto  # type: ignore

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

DTLS_1_3 = 0xFEFC            # supported_versions value for DTLS 1.3
LEGACY_VERSION = 0xFEFD      # the version field every record carries
SUITE_AES256 = 0x1302      # TLS_AES_256_GCM_SHA384
GROUP_X25519 = 0x001D
HASH = hashlib.sha384
HASH_LEN = 48

CT_ALERT = 21
CT_HANDSHAKE = 22
CT_APPDATA = 23
CT_ACK = 26

HS_CLIENT_HELLO = 1
HS_SERVER_HELLO = 2
HS_NEW_SESSION_TICKET = 4
HS_ENCRYPTED_EXTENSIONS = 8
HS_FINISHED = 20
HS_KEY_UPDATE = 24
HS_MESSAGE_HASH = 254

EXT_SUPPORTED_VERSIONS = 43
EXT_SUPPORTED_GROUPS = 10
EXT_KEY_SHARE = 51
EXT_PRE_SHARED_KEY = 41
EXT_PSK_MODES = 45
EXT_COOKIE = 47
EXT_CONNECTION_ID = 54

PSK_MODE_KE = 0              # prohibited by the profile -- never
PSK_MODE_DHE_KE = 1          # the only mode this profile speaks

ALERT_FATAL = 2
ALERT_BAD_RECORD_MAC = 20
ALERT_HANDSHAKE_FAILURE = 40
ALERT_ILLEGAL_PARAMETER = 47
ALERT_DECRYPT_ERROR = 51
ALERT_PROTOCOL_VERSION = 70
ALERT_MISSING_EXTENSION = 109

HRR_RANDOM = bytes.fromhex(
    "CF21AD74E59A611BBE1D8C021E65B891"
    "C2A211167ABB8C5E079E09E2C8A8339C")

DEFAULT_IDENTITY = "homing-pigeon"
IDENTITY_PREFIX = "homing-pigeon:"

# Application messages are length-prefixed over the record
# stream; a single record carries at most this much plaintext
# (a conservative under-MTU chunk; a large job is many
# records, which loopback and ordinary paths both absorb).
RECORD_PLAINTEXT_MAX = 1200
APP_MESSAGE_MAX = 4 * 1024 * 1024 + 65536

RETRANSMIT_FIRST = 1.0       # seconds; doubles per retry
RETRANSMIT_MAX = 16.0
RETRANSMIT_GIVE_UP = 60.0    # total seconds before the flight dies

TICKET_LIFETIME = 3600       # seconds a resumption ticket lives

_P = 2 ** 255 - 19


class DtlsError(Exception):
    """A session-level protocol failure. The session is dead;
    the process hosting the core is not."""


# ------------------------------------------------------------------
# X25519 (RFC 7748), pure Python
# ------------------------------------------------------------------

def _decode_u(data):
    b = bytearray(data)
    b[31] &= 0x7F                       # X25519 masks the top bit
    return int.from_bytes(b, "little")


def _decode_scalar(data):
    b = bytearray(data)
    b[0] &= 248
    b[31] &= 127
    b[31] |= 64
    return int.from_bytes(b, "little")


def x25519(scalar, u_bytes):
    """The RFC 7748 X25519 function: 32 octets in, 32 out."""
    if len(scalar) != 32 or len(u_bytes) != 32:
        raise DtlsError("x25519 inputs are 32 octets")
    k = _decode_scalar(scalar)
    x1 = _decode_u(u_bytes)
    x2, z2, x3, z3, swap = 1, 0, x1, 1, 0
    a24 = 121665
    for t in range(254, -1, -1):
        bit = (k >> t) & 1
        swap ^= bit
        if swap:
            x2, x3 = x3, x2
            z2, z3 = z3, z2
        swap = bit
        a = (x2 + z2) % _P
        aa = a * a % _P
        b = (x2 - z2) % _P
        bb = b * b % _P
        e = (aa - bb) % _P
        c = (x3 + z3) % _P
        d = (x3 - z3) % _P
        da = d * a % _P
        cb = c * b % _P
        x3 = (da + cb) ** 2 % _P
        z3 = x1 * (da - cb) ** 2 % _P
        x2 = aa * bb % _P
        z2 = e * (aa + a24 * e) % _P
    if swap:
        x2, x3 = x3, x2
        z2, z3 = z3, z2
    out = x2 * pow(z2, _P - 2, _P) % _P
    return out.to_bytes(32, "little")


def x25519_public(private):
    """The public key for a 32-octet private scalar."""
    return x25519(private, (9).to_bytes(32, "little"))


def _ecdh(private, peer_public):
    shared = x25519(private, peer_public)
    if shared == b"\x00" * 32:
        # RFC 7748 section 6.1: an all-zero result means the
        # peer sent a small-order point; abort.
        raise DtlsError("x25519 produced an all-zero secret")
    return shared


# ------------------------------------------------------------------
# HKDF (RFC 5869) and the TLS 1.3 label schedule (RFC 8446 7.1)
# (DTLS differs from the job envelope here: the schedule needs
# raw Expand against derived secrets, not extract+expand from
# an IKM -- hence these helpers rather than jobcrypto.hkdf.)
# ------------------------------------------------------------------

def _hkdf_extract(salt, ikm):
    if salt is None:
        salt = b"\x00" * HASH_LEN
    return hmac.new(salt, ikm, HASH).digest()


def _hkdf_expand(prk, info, length):
    out = b""
    block = b""
    counter = 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([counter]),
                         HASH).digest()
        out += block
        counter += 1
    return out[:length]


def _expand_label(secret, label, context, length):
    full = b"tls13 " + label
    info = (length.to_bytes(2, "big") + bytes([len(full)]) + full
            + bytes([len(context)]) + context)
    return _hkdf_expand(secret, info, length)


def _derive_secret(secret, label, transcript_hash):
    """Derive-Secret with the transcript hash already taken."""
    return _expand_label(secret, label, transcript_hash, HASH_LEN)


def _traffic_keys(traffic_secret):
    key = _expand_label(traffic_secret, b"key", b"", 32)
    iv = _expand_label(traffic_secret, b"iv", b"", 12)
    return key, iv


def _finished_verify(traffic_secret, transcript_hash):
    key = _expand_label(traffic_secret, b"finished", b"", HASH_LEN)
    return hmac.new(key, transcript_hash, HASH).digest()


def _binder(psk_bytes, label, transcript_hash):
    """The PSK binder for a partial-transcript hash (RFC 8446
    4.2.11.2): label is "ext binder" for an external PSK,
    "res binder" for a resumption PSK."""
    early = _hkdf_extract(b"\x00" * HASH_LEN, psk_bytes)
    binder_key = _derive_secret(early, label, HASH(b"").digest())
    fin_key = _expand_label(binder_key, b"finished", b"", HASH_LEN)
    return hmac.new(fin_key, transcript_hash, HASH).digest()


# ------------------------------------------------------------------
# Wire helpers
# ------------------------------------------------------------------

def _u24(n):
    return n.to_bytes(3, "big")


def _hs_message(msg_type, body, msg_seq):
    header = (bytes([msg_type]) + _u24(len(body))
              + msg_seq.to_bytes(2, "big") + _u24(0)
              + _u24(len(body)))
    return header + body


def _extensions_bytes(pairs):
    body = b"".join(t.to_bytes(2, "big") + len(d).to_bytes(2, "big")
                    + d for t, d in pairs)
    return len(body).to_bytes(2, "big") + body


def _parse_extensions(data, offset):
    """(dict type -> value, next offset). Raises DtlsError."""
    if offset + 2 > len(data):
        raise DtlsError("truncated extensions length")
    total = int.from_bytes(data[offset:offset + 2], "big")
    offset += 2
    end = offset + total
    if end > len(data):
        raise DtlsError("extensions overrun the message")
    out = {}
    while offset < end:
        if offset + 4 > end:
            raise DtlsError("truncated extension header")
        etype = int.from_bytes(data[offset:offset + 2], "big")
        elen = int.from_bytes(data[offset + 2:offset + 4], "big")
        offset += 4
        if offset + elen > end:
            raise DtlsError("extension overruns the block")
        if etype in out:
            raise DtlsError("duplicate extension")
        out[etype] = data[offset:offset + elen]
        offset += elen
    return out, end


class Transcript:
    """The handshake transcript: whole handshake messages (DTLS
    headers included), each logical message exactly once. After
    a HelloRetryRequest the first ClientHello is replaced by
    the RFC 8446 message_hash synthetic, per that section."""

    def __init__(self):
        self._parts = []

    def add(self, hs_bytes):
        self._parts.append(bytes(hs_bytes))

    def hash(self, extra=b""):
        h = HASH()
        for part in self._parts:
            h.update(part)
        if extra:
            h.update(extra)
        return h.digest()

    def apply_hrr(self, ch1_hs_bytes, hrr_hs_bytes):
        ch1_hash = HASH(ch1_hs_bytes).digest()
        synthetic = _hs_message(HS_MESSAGE_HASH, ch1_hash, 0)
        self._parts = [synthetic, bytes(hrr_hs_bytes)]

    def apply_hrr_hash(self, ch1_hash, hrr_hs_bytes):
        synthetic = _hs_message(HS_MESSAGE_HASH, ch1_hash, 0)
        self._parts = [synthetic, bytes(hrr_hs_bytes)]


# ------------------------------------------------------------------
# Records
# ------------------------------------------------------------------

def _plaintext_record(content_type, epoch, seq, body):
    return (bytes([content_type]) + LEGACY_VERSION.to_bytes(2, "big")
            + epoch.to_bytes(2, "big") + seq.to_bytes(6, "big")
            + len(body).to_bytes(2, "big") + body)


def _is_plaintext_record(data):
    return (len(data) >= 13 and data[0] in (20, 21, 22, 23)
            and data[1:3] == LEGACY_VERSION.to_bytes(2, "big"))


def _split_records(data):
    """Split a datagram into raw records. One record per
    datagram is the profile; several are tolerated, and a
    trailing undecodable remainder is dropped, never fatal."""
    out = []
    off = 0
    while off < len(data):
        if _is_plaintext_record(data[off:]):
            length = int.from_bytes(data[off + 11:off + 13], "big")
            if off + 13 + length > len(data):
                break
            out.append(data[off:off + 13 + length])
            off += 13 + length
            continue
        first = data[off]
        if first & 0xE0 != 0x20:
            break
        pos = off + 1
        if first & 0x04:                       # C: connection id
            if pos >= len(data):
                break
            pos += 1 + data[pos]
        if pos > len(data):
            break
        pos += 2 if first & 0x10 else 1        # S: sequence size
        if first & 0x08:                       # L: length field
            if pos + 2 > len(data):
                break
            length = int.from_bytes(data[pos:pos + 2], "big")
            pos += 2
            if pos + length > len(data):
                break
            out.append(data[off:pos + length])
            off = pos + length
        else:
            out.append(data[off:])
            break
    return out


def _record_cid(record):
    """The destination CID a unified record carries, or None."""
    if not record or record[0] & 0xE0 != 0x20 or not record[0] & 0x04:
        return None
    if len(record) < 2:
        return None
    n = record[1]
    return record[2:2 + n]


class _RecordSealer:
    """Per-direction, per-epoch AEAD record state."""

    def __init__(self, traffic_secret):
        self.key, self.iv = _traffic_keys(traffic_secret)
        self.seq = 0
        self._next_expected = 0

    def _nonce(self, epoch, seq):
        combined = ((epoch << 48) | seq).to_bytes(12, "big")
        return bytes(a ^ b for a, b in zip(self.iv, combined))

    def seal(self, epoch, content_type, plaintext, cid):
        seq = self.seq
        self.seq += 1
        first = 0x20 | 0x10 | 0x08 | (epoch & 0x3)
        if cid is not None:
            first |= 0x04
        header = bytes([first])
        if cid is not None:
            header += bytes([len(cid)]) + cid
        header += (seq & 0xFFFF).to_bytes(2, "big")
        header += (len(plaintext) + 1 + 16).to_bytes(2, "big")
        inner = plaintext + bytes([content_type])
        return header + jobcrypto.aead_encrypt(
            self.key, self._nonce(epoch, seq), inner, header)

    def open(self, epoch, record):
        """(content_type, content, seq); raises on any defect.

        The inner plaintext is content || type || zeros*
        (RFC 8446 5.2): strip the zero padding from the end,
        the last remaining octet is the content type, and the
        content keeps any trailing zeros of its own.
        """
        if not record:
            raise DtlsError("record too short")
        first = record[0]
        pos = 1
        if first & 0x04:
            if pos >= len(record):
                raise DtlsError("record too short")
            pos += 1 + record[pos]
        if first & 0x10:
            if pos + 2 > len(record):
                raise DtlsError("record too short")
            seq_low = int.from_bytes(record[pos:pos + 2], "big")
            pos += 2
        else:
            if pos >= len(record):
                raise DtlsError("record too short")
            seq_low = record[pos]
            pos += 1
        if first & 0x08:
            if pos + 2 > len(record):
                raise DtlsError("record too short")
            length = int.from_bytes(record[pos:pos + 2], "big")
            pos += 2
        else:
            length = len(record) - pos
        body = record[pos:pos + length]
        if len(body) < 17 or pos + length > len(record):
            raise DtlsError("record too short")
        # Sequence reconstruction: within one epoch, sequence
        # numbers grow monotonically; the wire carries the low
        # 16 bits and the window's high bits are inferred.
        seq = (self._next_expected & ~0xFFFF) | seq_low
        if seq + 0x8000 < self._next_expected:
            seq += 0x10000
        elif seq > self._next_expected + 0x8000 and seq >= 0x10000:
            seq -= 0x10000
        plain = jobcrypto.aead_decrypt(
            self.key, self._nonce(epoch, seq), body, record[:pos])
        stripped = plain.rstrip(b"\x00")
        if not stripped:
            raise DtlsError("empty inner plaintext")
        content_type = stripped[-1]
        self._next_expected = max(self._next_expected, seq + 1)
        return content_type, stripped[:-1], seq


# ------------------------------------------------------------------
# Handshake message parsing
# ------------------------------------------------------------------

def _parse_handshake(data):
    """Parse one handshake message at the head of `data`.

    Returns (msg_type, msg_seq, body, raw) for a whole message,
    ("fragment", ...) for a fragment, or None when too little
    data is present to tell.
    """
    if len(data) < 12:
        return None
    msg_type = data[0]
    length = int.from_bytes(data[1:4], "big")
    msg_seq = int.from_bytes(data[4:6], "big")
    frag_off = int.from_bytes(data[6:9], "big")
    frag_len = int.from_bytes(data[9:12], "big")
    if frag_off != 0 or frag_len != length:
        return ("fragment", msg_type, msg_seq, frag_off,
                data[12:12 + frag_len], length)
    if len(data) < 12 + length:
        return None
    return (msg_type, msg_seq, data[12:12 + length],
            data[:12 + length])


class _FragmentBuffer:
    """Reassembles fragmented handshake messages (this profile
    never sends fragments; a peer's are tolerated)."""

    def __init__(self):
        self._pending = {}

    def offer(self, msg_type, msg_seq, frag_off, frag, total):
        key = (msg_type, msg_seq)
        buf, have = self._pending.get(
            key, (bytearray(total), bytearray(total)))
        for i, byte in enumerate(frag):
            pos = frag_off + i
            if pos < total:
                buf[pos] = byte
                have[pos] = 1
        self._pending[key] = (buf, have)
        if all(have):
            del self._pending[key]
            return _hs_message(msg_type, bytes(buf), msg_seq)
        return None


def _reader(body):
    pos = [0]

    def take(n):
        if pos[0] + n > len(body):
            raise DtlsError("truncated message")
        chunk = body[pos[0]:pos[0] + n]
        pos[0] += n
        return chunk

    return take, pos


def _parse_client_hello(body):
    take, pos = _reader(body)
    take(2)                                   # legacy_version
    random = take(32)
    take(take(1)[0])                          # legacy_session_id
    take(take(1)[0])                          # legacy_cookie
    suites_len = int.from_bytes(take(2), "big")
    suites = take(suites_len)
    take(take(1)[0])                          # compression methods
    exts, _ = _parse_extensions(body, pos[0])
    suite_list = [int.from_bytes(suites[i:i + 2], "big")
                  for i in range(0, len(suites) - 1, 2)]
    return {"random": random, "suites": suite_list, "exts": exts}


def _parse_server_hello(body):
    take, pos = _reader(body)
    take(2)
    random = take(32)
    take(take(1)[0])
    suite = int.from_bytes(take(2), "big")
    take(1)                                   # compression
    exts, _ = _parse_extensions(body, pos[0])
    return {"random": random, "suite": suite, "exts": exts}


def _key_share_entry(data, server_form=False):
    """The (group, public) of a key_share extension value."""
    if server_form:
        if len(data) < 4:
            raise DtlsError("truncated key_share")
        group = int.from_bytes(data[0:2], "big")
        klen = int.from_bytes(data[2:4], "big")
        if 4 + klen > len(data):
            raise DtlsError("truncated key_share key")
        return group, data[4:4 + klen]
    if len(data) < 2:
        raise DtlsError("truncated key_share list")
    total = int.from_bytes(data[0:2], "big")
    inner = data[2:2 + total]
    if len(inner) < 4 or len(inner) < total:
        raise DtlsError("truncated key_share entry")
    group = int.from_bytes(inner[0:2], "big")
    klen = int.from_bytes(inner[2:4], "big")
    if 4 + klen > len(inner):
        raise DtlsError("truncated key_share key")
    return group, inner[4:4 + klen]


def _parse_psk_extension(data):
    """(identities [bytes], binders [bytes]) of a
    pre_shared_key extension value."""
    if len(data) < 2:
        raise DtlsError("truncated psk extension")
    id_len = int.from_bytes(data[0:2], "big")
    pos = 2
    end = pos + id_len
    if end > len(data):
        raise DtlsError("psk identities overrun")
    identities = []
    while pos < end:
        if pos + 2 > end:
            raise DtlsError("truncated identity")
        n = int.from_bytes(data[pos:pos + 2], "big")
        pos += 2
        if pos + n + 4 > end:
            raise DtlsError("truncated identity body")
        identities.append(data[pos:pos + n])
        pos += n + 4                          # obfuscated ticket age
    if pos >= len(data):
        raise DtlsError("psk binders missing")
    binders_len = data[pos]
    pos += 1
    binders = []
    b_end = pos + binders_len
    if b_end > len(data):
        raise DtlsError("psk binders overrun")
    while pos < b_end:
        n = data[pos]
        pos += 1
        if pos + n > b_end:
            raise DtlsError("psk binder overruns")
        binders.append(data[pos:pos + n])
        pos += n
    return identities, binders


# ------------------------------------------------------------------
# Session identity -> secret
# ------------------------------------------------------------------

def identity_for(key_id):
    if key_id:
        return (IDENTITY_PREFIX + key_id).encode("utf-8")
    return DEFAULT_IDENTITY.encode("utf-8")


def make_secret_lookup(default_secret, additional=None):
    """identity bytes -> secret string or None, over the
    runner's shared_secret plus its additional_secrets."""
    table = {}
    if default_secret:
        table[DEFAULT_IDENTITY.encode("utf-8")] = default_secret
    for key_id, secret in (additional or {}).items():
        if secret:
            table[identity_for(key_id)] = secret
    return table.get


# ------------------------------------------------------------------
# Endpoint plumbing shared by both roles
# ------------------------------------------------------------------

class _Endpoint:
    def __init__(self, log=None, rng=None):
        self.log = log or (lambda msg, level="INFO": None)
        self.rng = rng or secrets.token_bytes
        self.dead = False
        self.state = "new"
        self.record_log = []       # ("out"/"in", epoch, ctype)
        self.transcript = Transcript()
        self._fragments = _FragmentBuffer()
        self.receivers = {}        # epoch -> _RecordSealer
        self.senders = {}          # epoch -> _RecordSealer
        self._flight = None        # [(epoch, ctype, content)]
        self._flight_next = 0.0
        self._flight_first = 0.0
        self._acks_wanted = []     # (epoch, seq) to acknowledge
        self._app_buf = bytearray()
        self.app_messages = []     # whole messages, in order
        self._next_hs_seq = 0
        self._plain_seq = 0
        self._peer_cid = None
        # Set by _install_app_keys; ratcheted by KeyUpdate.
        self._send_ap_secret = None
        self._recv_ap_secret = None

    # -- sending ---------------------------------------------------

    def _alloc_seq(self):
        seq = self._next_hs_seq
        self._next_hs_seq += 1
        return seq

    def _emit(self, epoch, content_type, content):
        if epoch == 0:
            seq = self._plain_seq
            self._plain_seq += 1
            self.record_log.append(("out", 0, content_type))
            return _plaintext_record(content_type, 0, seq, content)
        record = self.senders[epoch].seal(
            epoch, content_type, content, self._peer_cid)
        self.record_log.append(("out", epoch, content_type))
        return record

    def _set_flight(self, items, now):
        self._flight = list(items)
        self._flight_first = now
        self._flight_next = now + RETRANSMIT_FIRST
        return [self._emit(e, t, c) for e, t, c in items]

    def _clear_flight(self):
        self._flight = None

    def tick(self, now):
        """Datagrams owed by retransmission timers and pending
        ACKs. Callers pass a monotonic clock."""
        out = []
        if self._flight is not None and not self.dead:
            if now - self._flight_first > RETRANSMIT_GIVE_UP:
                self.dead = True
                self.state = "dead"
                self.log("dtls: handshake flight unanswered for "
                         f"{RETRANSMIT_GIVE_UP:.0f}s; session "
                         "abandoned", "WARN")
                self._flight = None
            elif now >= self._flight_next:
                out.extend(self._emit(e, t, c)
                           for e, t, c in self._flight)
                gap = min(RETRANSMIT_MAX,
                          (self._flight_next - self._flight_first)
                          or RETRANSMIT_FIRST)
                self._flight_next = now + min(
                    RETRANSMIT_MAX, max(RETRANSMIT_FIRST, gap * 2))
        if self._acks_wanted and self.senders and not self.dead:
            out.extend(self._send_ack())
        return out

    def _send_ack(self):
        epoch = max(self.senders)
        body = b""
        for (ep, seq) in self._acks_wanted:
            body += (ep.to_bytes(2, "big") + seq.to_bytes(6, "big"))
        self._acks_wanted = []
        record = (len(body).to_bytes(2, "big") + body)
        return [self._emit(epoch, CT_ACK, record)]

    def _note_ack(self, content):
        # Any well-formed ACK for our flight ends retransmission.
        if len(content) >= 2:
            self._clear_flight()

    # -- application data ----------------------------------------------

    def _app_send(self, data):
        framed = len(data).to_bytes(4, "big") + data
        epoch = max(e for e in self.senders if e >= 3)
        out = []
        while framed:
            chunk = framed[:RECORD_PLAINTEXT_MAX]
            framed = framed[len(chunk):]
            out.append(self._emit(epoch, CT_APPDATA, chunk))
        return out

    def _app_receive(self, content):
        self._app_buf.extend(content)
        while len(self._app_buf) >= 4:
            n = int.from_bytes(self._app_buf[0:4], "big")
            if n > APP_MESSAGE_MAX:
                raise DtlsError("application message too large")
            if len(self._app_buf) < 4 + n:
                break
            msg = bytes(self._app_buf[4:4 + n])
            del self._app_buf[:4 + n]
            self.app_messages.append(msg)
            self._on_app_message(msg)

    def _on_app_message(self, msg):
        raise NotImplementedError

    # -- key update (RFC 9147 5.6): answered, never initiated ----------

    def _handle_key_update(self, received_epoch, body):
        if not body or body[0] not in (0, 1):
            self.log("dtls: malformed KeyUpdate; dropped", "WARN")
            return []
        update_requested = body[0] == 1
        self._recv_ap_secret = _expand_label(
            self._recv_ap_secret, b"traffic upd", b"", HASH_LEN)
        self.receivers[received_epoch + 1] = _RecordSealer(
            self._recv_ap_secret)
        if not update_requested:
            return []
        self._send_ap_secret = _expand_label(
            self._send_ap_secret, b"traffic upd", b"", HASH_LEN)
        send_epoch = max(self.senders) + 1
        self.senders[send_epoch] = _RecordSealer(self._send_ap_secret)
        reply = _hs_message(HS_KEY_UPDATE, b"\x00",
                            self._alloc_seq())
        return [self._emit(send_epoch, CT_HANDSHAKE, reply)]

    # -- flights' shared key install ------------------------------------

    def _install_app_keys(self, master_secret, th_through_sfin):
        c_ap = _derive_secret(master_secret, b"c ap traffic",
                              th_through_sfin)
        s_ap = _derive_secret(master_secret, b"s ap traffic",
                              th_through_sfin)
        if isinstance(self, DtlsClientCore):
            self.senders[3] = _RecordSealer(c_ap)
            self.receivers[3] = _RecordSealer(s_ap)
            self._send_ap_secret, self._recv_ap_secret = c_ap, s_ap
        else:
            self.senders[3] = _RecordSealer(s_ap)
            self.receivers[3] = _RecordSealer(c_ap)
            self._send_ap_secret, self._recv_ap_secret = s_ap, c_ap


# ------------------------------------------------------------------
# Client
# ------------------------------------------------------------------

class DtlsClientCore(_Endpoint):
    """The initiator side. feed() takes datagrams from the
    server and returns datagrams to send; events and state are
    read off the object. Application messages land in
    app_messages; the first is also parsed into .greeting."""

    def __init__(self, secret, key_id=None, log=None, rng=None,
                 ticket=None):
        """`ticket` is a (ticket_bytes, resumption_psk) pair
        from a previous session's .ticket property, if any."""
        super().__init__(log=log, rng=rng)
        self._psk = secret.encode("utf-8") if secret else b""
        self._key_id = key_id
        self._identity = identity_for(key_id)
        self._binder_label = b"ext binder"
        if ticket is not None:
            self._identity, self._psk = ticket
            self._binder_label = b"res binder"
        self.state = "idle"
        self._eph = None
        self._cookie = None
        self._ch1 = None
        self._hs = None
        self._c_hs = None
        self._s_hs = None
        self._res_master = None
        self.finished_received = False
        self.finished_sent = False
        self._ee_seen = False
        self.greeting = None
        self._ticket_out = None

    # -- handshake construction -------------------------------------

    def _client_hello(self, msg_seq):
        self._eph = self.rng(32)
        eph_pub = x25519_public(self._eph)
        share = (GROUP_X25519.to_bytes(2, "big")
                 + (32).to_bytes(2, "big") + eph_pub)
        shares = len(share).to_bytes(2, "big") + share
        exts = [
            (EXT_SUPPORTED_VERSIONS,
             b"\x02" + DTLS_1_3.to_bytes(2, "big")),
            (EXT_SUPPORTED_GROUPS,
             b"\x00\x02" + GROUP_X25519.to_bytes(2, "big")),
            (EXT_KEY_SHARE, shares),
            (EXT_PSK_MODES, bytes([1, PSK_MODE_DHE_KE])),
            (EXT_CONNECTION_ID, b"\x04" + self._our_cid()),
        ]
        if self._cookie is not None:
            exts.append((EXT_COOKIE, len(self._cookie).to_bytes(
                2, "big") + self._cookie))
        body = (LEGACY_VERSION.to_bytes(2, "big") + self.rng(32)
                + b"\x00"                    # session_id: empty
                + b"\x00"                    # cookie: empty
                + (2).to_bytes(2, "big")
                + SUITE_AES256.to_bytes(2, "big")
                + b"\x01\x00"                # compression: [null]
                )
        partial_exts = exts  # psk extension is appended last
        id_entry = (len(self._identity).to_bytes(2, "big")
                    + self._identity + (0).to_bytes(4, "big"))
        # The binder is one HASH_LEN value: the binders vector
        # is 1 length octet + the value, the value's own length
        # octet, then HASH_LEN placeholder octets the binder
        # computation replaces.
        psk_ext = (len(id_entry).to_bytes(2, "big") + id_entry
                   + bytes([1 + HASH_LEN]) + bytes([HASH_LEN])
                   + b"\x00" * HASH_LEN)
        body_full = body + _extensions_bytes(
            partial_exts + [(EXT_PRE_SHARED_KEY, psk_ext)])
        message = _hs_message(HS_CLIENT_HELLO, body_full, msg_seq)
        partial = message[:-HASH_LEN]        # minus binder value
        binder = _binder(self._psk, self._binder_label,
                         self.transcript.hash(extra=partial))
        return message[:-HASH_LEN] + binder

    def _our_cid(self):
        if not hasattr(self, "_cid"):
            self._cid = self.rng(4)
        return self._cid

    def start(self, now):
        """The first ClientHello datagram (a list of one)."""
        self.transcript = Transcript()
        self._next_hs_seq = 0
        hello = self._client_hello(self._alloc_seq())
        self._ch1 = hello
        self.transcript.add(hello)
        self.state = "wait-hrr-or-sh"
        return self._set_flight([(0, CT_HANDSHAKE, hello)], now)

    def _start_after_hrr(self, now):
        self._clear_flight()
        hello = self._client_hello(self._alloc_seq())
        self.transcript.add(hello)
        self.state = "wait-sh"
        return self._set_flight([(0, CT_HANDSHAKE, hello)], now)

    # -- receiving --------------------------------------------------------

    def feed(self, datagram, now):
        out = []
        for record in _split_records(datagram):
            out.extend(self._feed_record(record, now))
        return out

    def _feed_record(self, record, now):
        if _is_plaintext_record(record):
            length = int.from_bytes(record[11:13], "big")
            content = record[13:13 + length]
            if record[0] == CT_ALERT:
                self.dead = True
                self.state = "dead"
                self.log("dtls: fatal alert from the server",
                         "WARN")
                return []
            if record[0] != CT_HANDSHAKE:
                self.log("dtls: plaintext record that is not a "
                         "handshake or an alert; dropped", "WARN")
                return []
            return self._on_handshake_bytes(content, now, 0)
        low2 = record[0] & 0x3
        for epoch in sorted(self.receivers):
            if epoch & 0x3 != low2:
                continue
            try:
                ctype, content, seq = self.receivers[epoch].open(
                    epoch, record)
            except Exception:
                continue
            self.record_log.append(("in", epoch, ctype))
            return self._on_protected(epoch, ctype, content, seq,
                                      now)
        self.log("dtls: record did not decrypt under any "
                 "known epoch key; dropped", "WARN")
        return []

    def _on_protected(self, epoch, ctype, content, seq, now):
        out = []
        if ctype == CT_ACK:
            self._note_ack(content)
            return out
        if ctype == CT_ALERT:
            if content and content[0] == ALERT_FATAL:
                self.dead = True
                self.state = "dead"
                self.log("dtls: fatal alert from the server; "
                         "session dead", "WARN")
            return out
        if ctype == CT_APPDATA:
            if not self.finished_sent:
                raise DtlsError(
                    "application data before our Finished was "
                    "sent -- the greeting cannot precede "
                    "authentication")
            self._app_receive(content)
            return out
        if ctype == CT_HANDSHAKE:
            self._acks_wanted.append((epoch, seq))
            out.extend(self._on_handshake_bytes(content, now,
                                                epoch))
            if self.state == "established" and self._acks_wanted:
                out.extend(self._send_ack())
            return out
        return out

    def _on_handshake_bytes(self, data, now, epoch):
        parsed = _parse_handshake(data)
        if parsed is None:
            self.log("dtls: handshake record carries no "
                     "complete message; dropped", "WARN")
            return []
        if parsed[0] == "fragment":
            whole = self._fragments.offer(
                parsed[1], parsed[2], parsed[3], parsed[4],
                parsed[5])
            if whole is None:
                return []
            parsed = _parse_handshake(whole)
            if parsed is None:
                return []
        msg_type, msg_seq, body, raw = parsed
        if msg_type == HS_SERVER_HELLO:
            return self._on_server_hello(body, raw, now)
        if msg_type == HS_FINISHED:
            return self._on_server_finished(body, raw, now)
        if msg_type == HS_NEW_SESSION_TICKET:
            self._on_ticket(body, now)
            return []
        if msg_type == HS_ENCRYPTED_EXTENSIONS:
            # No extensions this profile acts on, but the
            # message is part of the transcript -- once.
            if not self._ee_seen:
                self._ee_seen = True
                self.transcript.add(raw)
            return []
        if msg_type == HS_KEY_UPDATE:
            return self._handle_key_update(epoch, body)
        self.log(f"dtls: unexpected handshake message type "
                 f"{msg_type}; dropped", "WARN")
        return []

    def _on_server_hello(self, body, raw, now):
        fields = _parse_server_hello(body)
        exts = fields["exts"]
        if fields["random"] == HRR_RANDOM:
            if self.state != "wait-hrr-or-sh":
                return []
            ver = int.from_bytes(
                exts.get(EXT_SUPPORTED_VERSIONS, b""), "big")
            if ver != DTLS_1_3 or EXT_COOKIE not in exts:
                raise DtlsError("bad HelloRetryRequest")
            cookie_ext = exts[EXT_COOKIE]
            self._cookie = cookie_ext[2:2 + int.from_bytes(
                cookie_ext[0:2], "big")]
            self.transcript.apply_hrr(self._ch1, raw)
            return self._start_after_hrr(now)
        if self.state not in ("wait-hrr-or-sh", "wait-sh"):
            # A retransmitted ServerHello for a handshake that
            # has already moved on: not an error, not news.
            return []
        if fields["suite"] != SUITE_AES256:
            raise DtlsError("server picked a foreign ciphersuite")
        if int.from_bytes(exts.get(EXT_SUPPORTED_VERSIONS, b""),
                          "big") != DTLS_1_3:
            raise DtlsError("server did not pick DTLS 1.3")
        if EXT_PRE_SHARED_KEY not in exts or int.from_bytes(
                exts[EXT_PRE_SHARED_KEY], "big") != 0:
            raise DtlsError("server did not accept our PSK")
        group, peer_pub = _key_share_entry(
            exts[EXT_KEY_SHARE], server_form=True)
        if group != GROUP_X25519:
            raise DtlsError("server picked a foreign group")
        if EXT_CONNECTION_ID in exts:
            cid_ext = exts[EXT_CONNECTION_ID]
            if cid_ext:
                self._peer_cid = cid_ext[1:1 + cid_ext[0]]
        self._clear_flight()
        self.transcript.add(raw)
        shared = _ecdh(self._eph, peer_pub)
        early = _hkdf_extract(b"\x00" * HASH_LEN, self._psk)
        self._hs = _hkdf_extract(
            _derive_secret(early, b"derived", HASH(b"").digest()),
            shared)
        th = self.transcript.hash()
        self._c_hs = _derive_secret(self._hs, b"c hs traffic", th)
        self._s_hs = _derive_secret(self._hs, b"s hs traffic", th)
        self.senders[2] = _RecordSealer(self._c_hs)
        self.receivers[2] = _RecordSealer(self._s_hs)
        self.state = "handshake-keys"
        return []

    def _on_server_finished(self, body, raw, now):
        if self.state != "handshake-keys":
            return []      # a retransmitted Finished; we moved on
        expect = _finished_verify(self._s_hs,
                                  self.transcript.hash())
        if not hmac.compare_digest(expect, body):
            self.dead = True
            self.state = "dead"
            raise DtlsError("server Finished does not verify")
        self.finished_received = True
        self.transcript.add(raw)
        ms = _hkdf_extract(
            _derive_secret(self._hs, b"derived",
                           HASH(b"").digest()),
            b"\x00" * HASH_LEN)
        th = self.transcript.hash()       # Hash(CH..SFin)
        self._install_app_keys(ms, th)
        cfin_verify = _finished_verify(self._c_hs,
                                       self.transcript.hash())
        cfin = _hs_message(HS_FINISHED, cfin_verify,
                           self._alloc_seq())
        self.transcript.add(cfin)
        self._res_master = _derive_secret(
            ms, b"res master", self.transcript.hash())
        self.finished_sent = True
        self.state = "established"
        out = self._set_flight([(2, CT_HANDSHAKE, cfin)], now)
        if self._acks_wanted:
            out.extend(self._send_ack())
        return out

    def _on_ticket(self, body, now):
        try:
            take, pos = _reader(body)
            take(4)                                   # lifetime
            take(4)                                   # age_add
            nonce_len = take(1)[0]
            nonce = take(nonce_len)
            ticket_len = int.from_bytes(take(2), "big")
            ticket = take(ticket_len)
        except DtlsError:
            self.log("dtls: malformed NewSessionTicket; "
                     "dropped", "WARN")
            return
        psk = _expand_label(self._res_master, b"resumption",
                            nonce, HASH_LEN)
        self._ticket_out = (ticket, psk)

    @property
    def ticket(self):
        """(ticket_bytes, resumption_psk) once a NewSessionTicket
        has been processed; feed it to a future client."""
        return self._ticket_out

    def _on_app_message(self, msg):
        if self.greeting is None:
            try:
                self.greeting = json.loads(msg.decode("utf-8"))
            except Exception:
                self.greeting = {}

    # -- sending application data ------------------------------------

    def send_app(self, data):
        if not self.finished_sent:
            raise DtlsError("no session yet")
        return self._app_send(data)


# ------------------------------------------------------------------
# Server
# ------------------------------------------------------------------

def _addr_bytes(addr):
    if isinstance(addr, tuple) and len(addr) == 2:
        host, port = addr
        return str(host).encode("utf-8") + int(port).to_bytes(2, "big")
    return str(addr).encode("utf-8")


def _hello_retry_request(cookie, msg_seq=0):
    """The (deterministic) HelloRetryRequest for a cookie.
    Deterministic so the server can rebuild the identical
    bytes for the transcript when the cookie comes back."""
    body = (LEGACY_VERSION.to_bytes(2, "big") + HRR_RANDOM
            + b"\x00"                       # session_id: empty
            + SUITE_AES256.to_bytes(2, "big") + b"\x00"
            + _extensions_bytes([
                (EXT_SUPPORTED_VERSIONS,
                 DTLS_1_3.to_bytes(2, "big")),
                (EXT_COOKIE,
                 len(cookie).to_bytes(2, "big") + cookie),
            ]))
    return _hs_message(HS_SERVER_HELLO, body, msg_seq)


def _sendable_alert(session, code):
    """A fatal alert under the newest keys we hold, else
    plaintext -- for when a session dies mid-handshake."""
    if session.senders:
        epoch = max(session.senders)
        return session._emit(epoch, CT_ALERT,
                             bytes([ALERT_FATAL, code]))
    return _plaintext_record(CT_ALERT, 0, 0,
                             bytes([ALERT_FATAL, code]))


class _ServerSession(_Endpoint):
    """One negotiated (or negotiating) DTLS association."""

    def __init__(self, core, addr):
        super().__init__(log=core.log, rng=core.rng)
        self.core = core
        self.peer_addr = addr
        self.identity = None
        self.resumed = False
        self.established = False
        self.greeting_sent = False
        self._our_cid = None
        self._hs = None
        self._c_hs = None
        self._s_hs = None

    @property
    def session_id(self):
        return self._our_cid

    # -- establishment ------------------------------------------------

    def begin(self, raw_ch, fields, ch1_hash, hrr_raw, now):
        """Validate a cookie-bearing ClientHello and answer
        with the server flight; returns datagrams (a lone
        plaintext alert when the hello is refused)."""
        self.transcript.apply_hrr_hash(ch1_hash, hrr_raw)
        exts = fields["exts"]

        def refuse(code, note=None):
            self.dead = True
            self.state = "dead"
            if note:
                self.core.log(note, "WARN")
            return [_plaintext_record(
                CT_ALERT, 0, 0, bytes([ALERT_FATAL, code]))]

        if SUITE_AES256 not in fields["suites"]:
            return refuse(ALERT_HANDSHAKE_FAILURE)
        modes = exts.get(EXT_PSK_MODES)
        if modes is None:
            return refuse(ALERT_MISSING_EXTENSION)
        offered = list(modes[1:1 + modes[0]]) if modes else []
        if PSK_MODE_DHE_KE not in offered:
            # psk_ke alone (or nothing) is refused outright:
            # this profile never trades forward secrecy away.
            return refuse(ALERT_ILLEGAL_PARAMETER,
                          "dtls: peer offered no psk_dhe_ke mode; "
                          "refused")
        if EXT_KEY_SHARE not in exts:
            return refuse(ALERT_ILLEGAL_PARAMETER)
        try:
            group, peer_pub = _key_share_entry(exts[EXT_KEY_SHARE])
        except DtlsError:
            return refuse(ALERT_ILLEGAL_PARAMETER)
        if group != GROUP_X25519:
            return refuse(ALERT_ILLEGAL_PARAMETER)
        if EXT_PRE_SHARED_KEY not in exts:
            return refuse(ALERT_MISSING_EXTENSION)
        try:
            identities, binders = _parse_psk_extension(
                exts[EXT_PRE_SHARED_KEY])
        except DtlsError:
            return refuse(ALERT_ILLEGAL_PARAMETER)
        if not identities or not binders:
            return refuse(ALERT_ILLEGAL_PARAMETER)
        identity = identities[0]
        self.identity = identity
        psk = None
        label = b"ext binder"
        ticket = self.core.tickets.get(identity)
        if ticket is not None:
            stored_psk, expiry = ticket
            if now <= expiry:
                psk = stored_psk
                label = b"res binder"
                self.resumed = True
                del self.core.tickets[identity]   # one-shot
        if psk is None:
            secret = self.core.secret_for(identity)
            if secret is None:
                return refuse(ALERT_HANDSHAKE_FAILURE,
                              "dtls: unknown PSK identity; "
                              "handshake refused")
            psk = secret.encode("utf-8")
        binder = binders[0]
        if len(raw_ch) <= len(binder):
            return refuse(ALERT_DECRYPT_ERROR)
        partial = raw_ch[:-len(binder)]
        expect = _binder(psk, label,
                         self.transcript.hash(extra=partial))
        if not hmac.compare_digest(expect, binder):
            return refuse(ALERT_DECRYPT_ERROR,
                          "dtls: PSK binder mismatch; handshake "
                          "refused")
        self.transcript.add(raw_ch)
        if EXT_CONNECTION_ID in exts:
            cid_ext = exts[EXT_CONNECTION_ID]
            if cid_ext:
                self._peer_cid = cid_ext[1:1 + cid_ext[0]]
        self._our_cid = self.core.rng(4)
        self.core.sessions[self._our_cid] = self
        self.core.by_addr[self.peer_addr] = self
        # The retry held message_seq 0; ours start at 1.
        self._next_hs_seq = 1
        eph = self.core.rng(32)
        eph_pub = x25519_public(eph)
        share = (GROUP_X25519.to_bytes(2, "big")
                 + (32).to_bytes(2, "big") + eph_pub)
        sh_exts = [
            (EXT_SUPPORTED_VERSIONS, DTLS_1_3.to_bytes(2, "big")),
            (EXT_KEY_SHARE, share),
            (EXT_PRE_SHARED_KEY, (0).to_bytes(2, "big")),
            (EXT_CONNECTION_ID,
             bytes([len(self._our_cid)]) + self._our_cid),
        ]
        sh_body = (LEGACY_VERSION.to_bytes(2, "big")
                   + self.core.rng(32)
                   + b"\x00" + SUITE_AES256.to_bytes(2, "big")
                   + b"\x00" + _extensions_bytes(sh_exts))
        sh_raw = _hs_message(HS_SERVER_HELLO, sh_body,
                             self._alloc_seq())
        self.transcript.add(sh_raw)
        shared = _ecdh(eph, peer_pub)
        early = _hkdf_extract(b"\x00" * HASH_LEN, psk)
        hs = _hkdf_extract(
            _derive_secret(early, b"derived", HASH(b"").digest()),
            shared)
        self._hs = hs
        th = self.transcript.hash()
        self._c_hs = _derive_secret(hs, b"c hs traffic", th)
        self._s_hs = _derive_secret(hs, b"s hs traffic", th)
        self.receivers[2] = _RecordSealer(self._c_hs)
        self.senders[2] = _RecordSealer(self._s_hs)
        ee_raw = _hs_message(HS_ENCRYPTED_EXTENSIONS, b"\x00\x00",
                             self._alloc_seq())
        self.transcript.add(ee_raw)
        sfin_verify = _finished_verify(self._s_hs,
                                       self.transcript.hash())
        sfin_raw = _hs_message(HS_FINISHED, sfin_verify,
                               self._alloc_seq())
        self.transcript.add(sfin_raw)
        self.state = "wait-finished"
        return self._set_flight(
            [(0, CT_HANDSHAKE, sh_raw),
             (2, CT_HANDSHAKE, ee_raw),
             (2, CT_HANDSHAKE, sfin_raw)], now)

    # -- established traffic -------------------------------------------

    def feed_authenticated(self, record, now):
        """A record carrying our CID. Returns (datagrams, ok);
        ok says the record authenticated, so the caller may
        trust its source address (NAT rebinding)."""
        try:
            epoch, ctype, content, seq = self._open_record(record)
        except DtlsError:
            self.log("dtls: record carrying a live session's "
                     "CID did not decrypt; dropped", "WARN")
            return [], False
        out = self._on_protected(epoch, ctype, content, seq, now)
        return out, True

    def _open_record(self, record):
        low2 = record[0] & 0x3
        for cand in sorted(self.receivers):
            if cand & 0x3 != low2:
                continue
            try:
                ctype, content, seq = self.receivers[cand].open(
                    cand, record)
            except Exception:
                continue
            self.record_log.append(("in", cand, ctype))
            return cand, ctype, content, seq
        raise DtlsError("undecryptable record")

    def _on_protected(self, epoch, ctype, content, seq, now):
        out = []
        if ctype == CT_ACK:
            self._note_ack(content)
            return out
        if ctype == CT_ALERT:
            if content and content[0] == ALERT_FATAL:
                self.dead = True
                self.state = "dead"
                self.log("dtls: fatal alert from the client; "
                         "session dead", "WARN")
            return out
        if ctype == CT_APPDATA:
            if not self.established:
                self.core.log(
                    "dtls: application data before the session "
                    "was established; dropped", "WARN")
                return out
            self._app_receive(content)
            return out
        if ctype == CT_HANDSHAKE:
            self._acks_wanted.append((epoch, seq))
            out.extend(self._on_handshake_bytes(content, now,
                                                epoch))
            if self.established and self._acks_wanted:
                out.extend(self._send_ack())
            return out
        return out

    def _on_handshake_bytes(self, data, now, epoch):
        parsed = _parse_handshake(data)
        if parsed is None:
            self.log("dtls: handshake record carries no "
                     "complete message; dropped", "WARN")
            return []
        if parsed[0] == "fragment":
            whole = self._fragments.offer(
                parsed[1], parsed[2], parsed[3], parsed[4],
                parsed[5])
            if whole is None:
                return []
            parsed = _parse_handshake(whole)
            if parsed is None:
                return []
        msg_type, msg_seq, body, raw = parsed
        if msg_type == HS_FINISHED:
            if self.established:
                return []  # retransmitted Finished; session is up
            return self._on_client_finished(body, raw, now)
        if msg_type == HS_KEY_UPDATE:
            return self._handle_key_update(epoch, body)
        self.log(f"dtls: unexpected handshake message type "
                 f"{msg_type}; dropped", "WARN")
        return []

    def _on_client_finished(self, body, raw, now):
        expect = _finished_verify(self._c_hs,
                                  self.transcript.hash())
        if not hmac.compare_digest(expect, body):
            self.dead = True
            self.state = "dead"
            self.core.log("dtls: client Finished does not "
                          "verify", "WARN")
            return [_sendable_alert(self, ALERT_DECRYPT_ERROR)]
        # Application secrets bind Hash(CH..ServerFinished) --
        # taken BEFORE the client Finished joins the transcript.
        th_app = self.transcript.hash()
        ms = _hkdf_extract(
            _derive_secret(self._hs, b"derived",
                           HASH(b"").digest()),
            b"\x00" * HASH_LEN)
        self._install_app_keys(ms, th_app)
        self.transcript.add(raw)          # CFin joins here
        res_master = _derive_secret(
            ms, b"res master", self.transcript.hash())
        self._clear_flight()
        self.established = True
        self.state = "established"
        self.core.events.append(
            ("established", self._our_cid,
             {"identity": self.identity, "resumed": self.resumed,
              "addr": self.peer_addr}))
        out = []
        # The greeting is the session's first application
        # message -- before the ticket, before any job.
        greeting = self.core.greeting_for(self)
        if greeting is not None:
            out.extend(self._app_send(greeting))
            self.greeting_sent = True
        # A fresh resumption ticket: a fresh PSK, and resumption
        # still demands fresh DHE next time.
        nonce = self.core.rng(16)
        ticket = self.core.rng(24)
        psk = _expand_label(res_master, b"resumption", nonce,
                            HASH_LEN)
        self.core.tickets[ticket] = (psk, now + TICKET_LIFETIME)
        nst_body = ((TICKET_LIFETIME).to_bytes(4, "big")
                    + self.core.rng(4)
                    + bytes([len(nonce)]) + nonce
                    + len(ticket).to_bytes(2, "big") + ticket
                    + b"\x00\x00")
        nst = _hs_message(HS_NEW_SESSION_TICKET, nst_body,
                          self._alloc_seq())
        out.append(self._emit(3, CT_HANDSHAKE, nst))
        if self._acks_wanted:
            out.extend(self._send_ack())
        return out

    def _on_app_message(self, msg):
        self.core.events.append(("app", self._our_cid, msg))

    def app_send(self, data):
        return self._app_send(data)


class DtlsServerCore:
    """The responder side: many sessions, one socket's worth of
    datagrams. Stateless until a cookie validates -- the first
    ClientHello costs the server one small HelloRetryRequest
    and no memory that matters."""

    def __init__(self, secret_lookup=None, greeting_for=None,
                 log=None, rng=None, secrets_map=None):
        self.log = log or (lambda msg, level="INFO": None)
        if secrets_map is not None:
            secret_lookup = secrets_map.get
        self._secret_lookup = secret_lookup or (lambda ident: None)
        self.greeting_for = greeting_for or (lambda session: None)
        self.rng = rng or secrets.token_bytes
        self.cookie_secret = self.rng(32)
        self.sessions = {}         # our CID -> _ServerSession
        self.by_addr = {}          # peer addr -> _ServerSession
        self.tickets = {}          # ticket bytes -> (psk, expiry)
        self.events = []
        self.dropped_records = 0

    def secret_for(self, identity):
        return self._secret_lookup(identity)

    # -- cookies ---------------------------------------------------

    def _issue_cookie(self, ch1_hash, addr):
        mac = hmac.new(self.cookie_secret,
                       _addr_bytes(addr) + ch1_hash,
                       HASH).digest()[:16]
        return ch1_hash + mac

    def _check_cookie(self, cookie, addr):
        if len(cookie) != HASH_LEN + 16:
            return None
        ch1_hash, mac = cookie[:HASH_LEN], cookie[HASH_LEN:]
        expect = hmac.new(self.cookie_secret,
                          _addr_bytes(addr) + ch1_hash,
                          HASH).digest()[:16]
        if not hmac.compare_digest(expect, mac):
            return None
        return ch1_hash

    # -- datagram entry ----------------------------------------------

    def feed(self, datagram, addr, now):
        out = []
        for record in _split_records(datagram):
            out.extend(self._feed_record(record, addr, now))
        return out

    def _feed_record(self, record, addr, now):
        cid = _record_cid(record)
        if cid is not None and cid in self.sessions:
            session = self.sessions[cid]
            out, ok = session.feed_authenticated(record, now)
            if ok and session.peer_addr != addr:
                self.log(f"dtls: session rebound from "
                         f"{session.peer_addr} to {addr} (CID)")
                self.by_addr.pop(session.peer_addr, None)
                session.peer_addr = addr
                self.by_addr[addr] = session
            return out
        if _is_plaintext_record(record):
            if record[0] != CT_HANDSHAKE:
                self.log("dtls: plaintext record that is not a "
                         "handshake; dropped", "WARN")
                return []
            length = int.from_bytes(record[11:13], "big")
            return self._on_hello_bytes(record[13:13 + length],
                                        addr, now)
        if cid is None:
            session = self.by_addr.get(addr)
            if session is not None:
                out, _ok = session.feed_authenticated(record, now)
                return out
        self.dropped_records += 1
        return []

    def _on_hello_bytes(self, data, addr, now):
        parsed = _parse_handshake(data)
        if parsed is None or parsed[0] == "fragment":
            # No service for fragmented first flights: the
            # profile's ClientHello is one message by design.
            self.log("dtls: unparseable or fragmented first "
                     "handshake flight; dropped", "WARN")
            return []
        msg_type, msg_seq, body, raw = parsed
        if msg_type != HS_CLIENT_HELLO:
            self.log(f"dtls: first handshake message is type "
                     f"{msg_type}, not a ClientHello; dropped",
                     "WARN")
            return []
        try:
            fields = _parse_client_hello(body)
        except DtlsError:
            self.log("dtls: malformed ClientHello; dropped",
                     "WARN")
            return []
        cookie_ext = fields["exts"].get(EXT_COOKIE)
        if cookie_ext is None:
            cookie = self._issue_cookie(HASH(raw).digest(), addr)
            hrr = _hello_retry_request(cookie)
            return [_plaintext_record(CT_HANDSHAKE, 0, 0, hrr)]
        if len(cookie_ext) < 2:
            self.log("dtls: malformed cookie extension; "
                     "dropped", "WARN")
            return []
        cookie = cookie_ext[2:2 + int.from_bytes(cookie_ext[0:2],
                                                 "big")]
        ch1_hash = self._check_cookie(cookie, addr)
        if ch1_hash is None:
            self.log("dtls: bad cookie; handshake ignored",
                     "WARN")
            return []
        existing = self.by_addr.get(addr)
        if existing is not None and \
                existing.state == "wait-finished":
            # A retransmitted cookie-bearing hello: answer with
            # the flight again; re-derive nothing.
            return [existing._emit(e, t, c)
                    for e, t, c in (existing._flight or [])]
        hrr = _hello_retry_request(cookie)
        session = _ServerSession(self, addr)
        try:
            return session.begin(raw, fields, ch1_hash, hrr, now)
        except DtlsError as e:
            # A half-registered session must not linger.
            session.dead = True
            if session._our_cid is not None:
                self.sessions.pop(session._our_cid, None)
            if self.by_addr.get(addr) is session:
                self.by_addr.pop(addr, None)
            self.log(f"dtls: handshake failed: {e}", "WARN")
            return []

    # -- driving sessions ---------------------------------------------

    def tick(self, now):
        """[(addr, datagram)] for every session's timers, plus
        housekeeping: dead sessions and expired tickets go."""
        out = []
        for cid, session in list(self.sessions.items()):
            for dg in session.tick(now):
                out.append((session.peer_addr, dg))
            if session.dead:
                self.sessions.pop(cid, None)
                if self.by_addr.get(session.peer_addr) is session:
                    self.by_addr.pop(session.peer_addr, None)
        for addr, session in list(self.by_addr.items()):
            if session.dead:
                self.by_addr.pop(addr, None)
        for ticket, (_psk, expiry) in list(self.tickets.items()):
            if now > expiry:
                del self.tickets[ticket]
        return out

    def send_app(self, session_id, data):
        """[(addr, datagram)] carrying one application message
        to the session's peer."""
        session = self.sessions.get(session_id)
        if session is None or not session.established:
            return []
        return [(session.peer_addr, dg)
                for dg in session.app_send(data)]
