"""In-memory fuzzing for the RFC 10024 hybrid key agreement.

Fuzzes the X25519MLKEM768 hybrid path (runner/wire/mlkem.py
and the hybrid share handling in runner/wire/dtlsproto.py)
in memory: no sockets, no mail. The corpus is seeded from
the public standards throughout — the NIST ACVP ML-KEM-768
vectors in runner/tests/fixtures/mlkem768_acvp.json, the
RFC 7748 section 5.2 and 6.1 X25519 vectors, a hybrid
vector constructed from those two sources, and the group
geometry harvested from RFC 10024 itself into
runner/tests/fixtures/rfc10024_groups.json (all three
groups' code points, share sizes, concatenation orders and
shared-secret sizes, plus the obsoleted pre-standard code
points; the RFC publishes no vectors of its own) — and
every
mutation family includes the bookend rule: each ASCII
symbol, plus NUL, tab, CR and LF, at the front and the back
of the input, symbol-only strings, and symbol runs at the
front, the back and the middle.

Targets and their contracts:

- ML-KEM decapsulation: a 1088-octet ciphertext against a
  genuine key never raises and returns 32 octets (implicit
  rejection); any other failure is MlkemError only.
- ML-KEM encapsulation: MlkemError only; success returns a
  32-octet secret and a 1088-octet ciphertext.
- The FIPS 203 section 7.2 and 7.3 key checks: a boolean,
  never a raise, on any input.
- ML-KEM key generation from mutated seeds: MlkemError
  only; a produced pair passes both key checks.
- The client's hybrid shared secret (a mutated server
  share): DtlsError only, or a 64-octet secret.
- The responder's hybrid answer (a mutated client share):
  DtlsError only, or a well-shaped share and secret.
- The server's datagram entry with a mutated ClientHello:
  feed() never raises at all.
- The client's datagram entry with a crafted ServerHello
  (structural variants — an extension removed, a foreign
  group named — plus byte mutations): a list back, or
  DtlsError only, never a foreign exception.
- The RFC 10024 geometry: this group's shares rebuilt at
  the other groups' fixed sizes, and its parts in the
  RFC 9954 order, must be refused.

Modes. --mode real runs the targets against the production
cryptography. --mode abstract swaps the ML-KEM operations
behind the seam in this file (class AbstractOps) for fast,
deterministic, size-faithful stand-ins, and patches them
into the DTLS engine's view of the mlkem module, so the
share parsing, the length discipline and the combiner keep
running for real while the expensive KEM internals stand
down. The stand-ins preserve the contracts above: same byte
sizes, MlkemError discipline, an encapsulation a matching
decapsulation opens, and a wrong ciphertext yielding a
different secret rather than an error (the implicit
rejection shape). What abstract mode does NOT exercise is
the real KEM's internals — that is what real mode is for,
and the run shape fixed for this effort is 1 hour of real
mode first, then the abstracted continuation.

Verdicts. One line per 250 rounds and a final verdict line
go to stdout and to --log when given. A contract break is a
finding: the offending input is recorded (hex, capped) in
the findings file beside the log, and the exit code is 3.
Exit 4 is a resource abort (MemAvailable under the floor).

Stdlib only. Run from the repository root:

    python3 runner/tools/hybrid_fuzz.py --mode real \
        --duration 3600 --seed 10024 --log /path/run.log
"""

import argparse
import hashlib
import json
import os
import random
import string
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.wire import dtlsproto, mlkem  # noqa: E402

SECRET = "hybrid-fuzz"
ADDR = ("127.0.0.1", 50001)
NOW = 1000.0
MEM_FLOOR_MB = 128

SYMBOLS = (string.punctuation.encode("ascii")
           + b"\x00\x09\x0a\x0d")


class Finding(Exception):
    """A fuzz contract break: carries the target name and
    the offending input for the record."""


# ------------------------------------------------------------------
# Corpus: the standards vectors
# ------------------------------------------------------------------

def _h(text):
    return bytes.fromhex(text)


def acvp_vectors():
    path = os.path.join(
        REPO, "runner", "tests", "fixtures",
        "mlkem768_acvp.json")
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {}
    for group in ("keygen", "encap", "decap",
                  "encap_key_check", "decap_key_check"):
        out[group] = [
            {k: (_h(v) if k not in ("tcId", "reason",
                                    "testPassed") else v)
             for k, v in row.items()}
            for row in raw[group]]
    return out


def rfc10024_groups():
    """The group geometry harvested from RFC 10024 itself
    (sections 4.1, 4.2, 4.3 and 7): every group's code
    point, component sizes, concatenation orders and
    shared-secret size, and the obsoleted pre-standard code
    points. The RFC publishes no test vectors; this table is
    what it fixes, and the geometry target fuzzes the
    implemented group against the other groups' shapes."""
    path = os.path.join(
        REPO, "runner", "tests", "fixtures",
        "rfc10024_groups.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# RFC 7748 section 6.1 (Alice and Bob), transcribed in
# runner/tests/test_dtls.py from the RFC text.
ALICE_PRIV = _h("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992a"
                "b177fba51db92c2a")
ALICE_PUB = _h("8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4"
               "eba4a98eaa9b4e6a")
BOB_PRIV = _h("5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1"
              "c2f8b27ff88e0eb")
BOB_PUB = _h("de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dad"
             "fc7e146f882b4f")
X25519_SHARED = _h("4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d"
                   "19e3376f09b3c1e161742")


def hybrid_vector(acvp):
    """The standards-derived hybrid vector: the first ACVP
    key-generation entry (whose ek and dk are pinned
    byte-exact by the standard), encapsulated to with the
    first ACVP encapsulation entry's message — the
    encapsulation function itself is pinned byte-exact by
    the ACVP encapsulation entries in the unit tests — plus
    RFC 7748's Alice (client) and Bob (server). Returns
    (client_share, server_share, secret, dk) in the
    RFC 10024 section 4 shapes."""
    kg = acvp["keygen"][0]
    m = acvp["encap"][0]["m"]
    k, c = mlkem.encaps_internal(kg["ek"], m)
    client_share = kg["ek"] + ALICE_PUB
    server_share = c + BOB_PUB
    secret = k + X25519_SHARED
    return client_share, server_share, secret, kg["dk"]


# ------------------------------------------------------------------
# The abstraction seam
# ------------------------------------------------------------------

class RealOps:
    """The production ML-KEM operations."""
    name = "real"
    keygen_internal = staticmethod(mlkem.keygen_internal)
    encaps_internal = staticmethod(mlkem.encaps_internal)
    decaps = staticmethod(mlkem.decaps)
    ek_check = staticmethod(mlkem.encapsulation_key_check)
    dk_check = staticmethod(mlkem.decapsulation_key_check)


class AbstractOps:
    """Fast deterministic stand-ins for the ML-KEM
    operations, behind the same contracts and byte sizes.
    The decapsulation key keeps the production layout
    (1152-octet private part, the encapsulation key, its
    SHA3-256, then z), so the production section 7.3 check
    passes on abstract keys unchanged."""
    name = "abstract"

    @staticmethod
    def keygen_internal(d, z):
        if len(d) != mlkem.SEED_BYTES or len(z) != mlkem.SEED_BYTES:
            raise mlkem.MlkemError(
                "ML-KEM seeds d and z are 32 octets each")
        ek = hashlib.shake_256(b"hp-abstract-ek\x00" + d).digest(
            mlkem.EK_BYTES)
        dk_pke = hashlib.shake_256(
            b"hp-abstract-dkpke\x00" + d + z).digest(384 * mlkem.K)
        dk = dk_pke + ek + hashlib.sha3_256(ek).digest() + z
        return ek, dk

    @staticmethod
    def ek_check(ek):
        # The modulus check is part of what is abstracted;
        # the shape discipline is what the seam keeps.
        return len(ek) == mlkem.EK_BYTES

    dk_check = staticmethod(mlkem.decapsulation_key_check)

    @staticmethod
    def encaps_internal(ek, m):
        if len(m) != 32:
            raise mlkem.MlkemError(
                "ML-KEM encapsulation randomness is 32 octets")
        if not AbstractOps.ek_check(ek):
            raise mlkem.MlkemError(
                "encapsulation key fails the FIPS 203 check")
        secret = hashlib.sha3_512(
            m + hashlib.sha3_256(ek).digest()).digest()[:32]
        mask = hashlib.shake_256(
            b"hp-abstract-mask\x00" + ek).digest(32)
        head = bytes(a ^ b for a, b in zip(m, mask))
        pad = hashlib.shake_256(
            b"hp-abstract-pad\x00" + ek + m).digest(
                mlkem.CT_BYTES - 32)
        return secret, head + pad

    @staticmethod
    def decaps(dk, c):
        if len(c) != mlkem.CT_BYTES:
            raise mlkem.MlkemError("ML-KEM ciphertext is 1088 octets")
        if not AbstractOps.dk_check(dk):
            raise mlkem.MlkemError(
                "decapsulation key fails the FIPS 203 check")
        ek = dk[384 * mlkem.K:384 * mlkem.K + mlkem.EK_BYTES]
        mask = hashlib.shake_256(
            b"hp-abstract-mask\x00" + ek).digest(32)
        m = bytes(a ^ b for a, b in zip(c[:32], mask))
        return hashlib.sha3_512(
            m + hashlib.sha3_256(ek).digest()).digest()[:32]


_OPS_ATTRS = ("keygen", "keygen_internal", "encaps_internal",
              "decaps", "encapsulation_key_check")


class apply_ops:
    """Patch an ops set into the DTLS engine's view of the
    mlkem module (and restore it on exit). The engine calls
    mlkem.keygen, mlkem.encaps_internal and mlkem.decaps,
    and checks keys through mlkem.encapsulation_key_check;
    those are the seams' patch points."""

    def __init__(self, ops):
        self.ops = ops
        self.saved = {}

    def __enter__(self):
        for attr in _OPS_ATTRS:
            self.saved[attr] = getattr(mlkem, attr)
        ops = self.ops
        if ops.name == "abstract":
            mlkem.keygen_internal = ops.keygen_internal
            mlkem.encaps_internal = ops.encaps_internal
            mlkem.decaps = ops.decaps
            mlkem.encapsulation_key_check = ops.ek_check

            def keygen(rng=None):
                rng = rng or __import__("secrets").token_bytes
                return ops.keygen_internal(rng(32), rng(32))
            mlkem.keygen = keygen
        return self.ops

    def __exit__(self, *exc):
        for attr, value in self.saved.items():
            setattr(mlkem, attr, value)
        return False


# ------------------------------------------------------------------
# Mutation: the bookend rule and the combinatorics
# ------------------------------------------------------------------

def bookend_variants(data):
    """Yield (label, bytes): every bookend shape the rule
    names, applied to data — each symbol alone at the front
    and at the back, symbol-only strings, and symbol runs at
    the front, the back and the middle."""
    for sym in SYMBOLS:
        s = bytes([sym])
        yield "pre-" + repr(s), s + data
        yield "post-" + repr(s), data + s
    for sym in SYMBOLS:
        s = bytes([sym])
        for n in (1, 8, 32, 256):
            yield "only-" + repr(s) + "-" + str(n), s * n
    for sym in (b"-", b";", b"'", b'"', b"\x00", b"\n"):
        yield "run-pre-" + repr(sym), b"A" * 10 + sym + data
        yield "run-post-" + repr(sym), data + sym + b"A" * 10
        mid = len(data) // 2
        yield "run-mid-" + repr(sym), data[:mid] + sym * 10 + data[mid:]


def mutate(data, rng):
    """One mutated copy of data, from the campaign's
    families: bit flips, byte sets, truncation, extension,
    swapped halves, and bookend wraps."""
    if not data:
        return bytes(rng.randrange(0, 64))
    op = rng.randrange(8)
    buf = bytearray(data)
    if op == 0:  # bit flip
        i = rng.randrange(len(buf))
        buf[i] ^= 1 << rng.randrange(8)
    elif op == 1:  # byte set
        i = rng.randrange(len(buf))
        buf[i] = rng.choice((0x00, 0xFF, rng.choice(SYMBOLS),
                             rng.randrange(256)))
    elif op == 2:  # truncate
        buf = buf[:rng.randrange(len(buf) + 1)]
    elif op == 3:  # extend
        extra = bytes(rng.choice(SYMBOLS) if rng.random() < 0.5
                      else rng.randrange(256)
                      for _ in range(rng.randrange(1, 65)))
        buf = buf + bytearray(extra)
    elif op == 4:  # swap halves
        mid = len(buf) // 2
        buf = buf[mid:] + buf[:mid]
    elif op == 5:  # bookend wrap
        sym = bytes([rng.choice(SYMBOLS)])
        buf = bytearray(sym + bytes(buf) + sym)
    elif op == 6:  # symbol-only stretch inside
        i = rng.randrange(len(buf))
        sym = bytes([rng.choice(SYMBOLS)])
        buf[i:i] = sym * rng.randrange(1, 33)
    else:  # several bit flips
        for _ in range(rng.randrange(2, 9)):
            i = rng.randrange(len(buf))
            buf[i] ^= 1 << rng.randrange(8)
    return bytes(buf)


# ------------------------------------------------------------------
# Targets
# ------------------------------------------------------------------

def _resize(data, size):
    if len(data) >= size:
        return data[:size]
    return data + bytes(size - len(data))


class Targets:
    def __init__(self, ops, acvp):
        self.ops = ops
        self.acvp = acvp
        (self.h_client_share, self.h_server_share,
         self.h_secret, self.h_dk) = hybrid_vector(acvp)
        self._client = None
        self._session = None
        self._hello = None
        self._sh_raw = None
        self._sh_fields = None
        # The RFC 10024 geometry seeds: this group's genuine
        # shares rebuilt at the OTHER groups' fixed sizes,
        # and this group's genuine parts laid out in the
        # RFC 9954 order (ECDHE first) instead of the
        # RFC 10024 order. Every one of them must be refused.
        geom = rfc10024_groups()
        self.geo_client_sizes = []
        self.geo_server_sizes = []
        for g in geom["groups"]:
            if g["codepoint"] == \
                    dtlsproto.GROUP_X25519MLKEM768:
                continue
            self.geo_client_sizes.append(_resize(
                self.h_client_share, g["client_share_bytes"]))
            self.geo_server_sizes.append(_resize(
                self.h_server_share, g["server_share_bytes"]))
        ek = self.h_client_share[:mlkem.EK_BYTES]
        self.geo_swapped_client = (
            self.h_client_share[mlkem.EK_BYTES:] + ek)

    # -- ML-KEM primitives ------------------------------------

    def t_decaps(self, rng):
        ops = self.ops
        row = rng.choice(self.acvp["decap"])
        dk, ct = row["dk"], mutate(row["c"], rng)
        if len(ct) == mlkem.CT_BYTES:
            try:
                out = ops.decaps(dk, ct)
            except Exception as exc:  # noqa: BLE001
                raise Finding(
                    "decaps raised on a 1088-octet ciphertext: "
                    + repr(exc)) from exc
            if len(out) != 32:
                raise Finding("decaps returned %d octets" % len(out))
        else:
            try:
                ops.decaps(dk, ct)
            except mlkem.MlkemError:
                return
            except Exception as exc:  # noqa: BLE001
                raise Finding(
                    "decaps raised a foreign exception: "
                    + repr(exc)) from exc
            raise Finding(
                "decaps accepted a %d-octet ciphertext" % len(ct))

    def t_encaps(self, rng):
        ops = self.ops
        row = rng.choice(self.acvp["encap"])
        ek = mutate(row["ek"], rng)
        try:
            secret, ct = ops.encaps_internal(ek, row["m"])
        except mlkem.MlkemError:
            return
        except Exception as exc:  # noqa: BLE001
            raise Finding(
                "encaps raised a foreign exception: "
                + repr(exc)) from exc
        if len(secret) != 32 or len(ct) != mlkem.CT_BYTES:
            raise Finding("encaps returned wrong sizes")

    def t_key_checks(self, rng):
        ops = self.ops
        ek_row = rng.choice(self.acvp["encap_key_check"])
        dk_row = rng.choice(self.acvp["decap_key_check"])
        for check, value in (
                (ops.ek_check, mutate(ek_row["ek"], rng)),
                (ops.dk_check, mutate(dk_row["dk"], rng))):
            try:
                out = check(value)
            except Exception as exc:  # noqa: BLE001
                raise Finding(
                    "a key check raised: " + repr(exc)) from exc
            if not isinstance(out, bool):
                raise Finding("a key check returned a non-bool")

    def t_keygen(self, rng):
        ops = self.ops
        row = rng.choice(self.acvp["keygen"])
        d, z = mutate(row["d"], rng), mutate(row["z"], rng)
        try:
            ek, dk = ops.keygen_internal(d, z)
        except mlkem.MlkemError:
            if len(d) == 32 and len(z) == 32:
                raise Finding(
                    "keygen refused well-shaped seeds")
            return
        except Exception as exc:  # noqa: BLE001
            raise Finding(
                "keygen raised a foreign exception: "
                + repr(exc)) from exc
        if len(ek) != mlkem.EK_BYTES or len(dk) != mlkem.DK_BYTES:
            raise Finding("keygen returned wrong sizes")
        if not ops.ek_check(ek) or not ops.dk_check(dk):
            raise Finding("a generated pair fails its own checks")

    # -- DTLS hybrid share paths ------------------------------

    def _primed_client(self):
        if self._client is None:
            client = dtlsproto.DtlsClientCore(SECRET, hybrid=True)
            client.start(NOW)
            assert client._mlkem_dk is not None
            self._client = client
        return self._client

    def _genuine_server_share(self):
        client = self._primed_client()
        ek = client._mlkem_dk[384 * mlkem.K:
                              384 * mlkem.K + mlkem.EK_BYTES]
        m = bytes(range(32))
        secret, ct = self.ops.encaps_internal(ek, m)
        share = ct + dtlsproto.x25519_public(BOB_PRIV)
        client_x = dtlsproto.x25519_public(client._eph_hyb)
        server_secret = secret + dtlsproto._ecdh(BOB_PRIV, client_x)
        return share, server_secret

    def t_client_shared(self, rng):
        client = self._primed_client()
        share, server_secret = self._genuine_server_share()
        got = client._hybrid_shared(share)
        if got != server_secret:
            raise Finding("positive control: hybrid secrets differ")
        mutated = mutate(share, rng)
        try:
            out = client._hybrid_shared(mutated)
        except dtlsproto.DtlsError:
            return
        except Exception as exc:  # noqa: BLE001
            raise Finding(
                "client hybrid shared raised a foreign "
                "exception: " + repr(exc)) from exc
        if len(out) != dtlsproto.HYBRID_SECRET_BYTES:
            raise Finding("client hybrid secret is %d octets"
                          % len(out))

    def _pumped_session(self):
        if self._session is None:
            server = dtlsproto.DtlsServerCore(
                secret_lookup=dtlsproto.make_secret_lookup(SECRET),
                hybrid=True)
            client = dtlsproto.DtlsClientCore(SECRET, hybrid=True)
            out = client.start(NOW)
            for _ in range(60):
                if not out:
                    break
                nxt = []
                for dg in out:
                    nxt += server.feed(dg, ADDR, NOW)
                out = []
                for dg in nxt:
                    out += client.feed(dg, NOW)
            assert client.state == "established", client.state
            sessions = list(server.sessions.values())
            assert len(sessions) == 1
            self._session = sessions[0]
        return self._session

    def t_server_answer(self, rng):
        session = self._pumped_session()
        mutated = mutate(self.h_client_share, rng)
        try:
            share, secret = session._hybrid_answer(mutated)
        except dtlsproto.DtlsError:
            return
        except Exception as exc:  # noqa: BLE001
            raise Finding(
                "server hybrid answer raised a foreign "
                "exception: " + repr(exc)) from exc
        want = 4 + dtlsproto.HYBRID_SERVER_SHARE_BYTES
        if len(share) != want or len(secret) != \
                dtlsproto.HYBRID_SECRET_BYTES:
            raise Finding("server hybrid answer returned "
                          "wrong sizes")

    def t_geometry(self, rng):
        """The RFC 10024 geometry contract: RFC 10024 fixes
        exactly one size per component per group, so a share
        carrying another group's size, or this group's parts
        in the other concatenation order, must be refused
        with DtlsError — never accepted, never a foreign
        exception."""
        kind = rng.randrange(3)
        if kind == 0:
            session = self._pumped_session()
            share = rng.choice(self.geo_client_sizes)
            try:
                session._hybrid_answer(share)
            except dtlsproto.DtlsError:
                return
            except Exception as exc:  # noqa: BLE001
                raise Finding(
                    "geometry: foreign exception on a "
                    "%d-octet client share: %s"
                    % (len(share), repr(exc))) from exc
            raise Finding(
                "geometry: server accepted a %d-octet client "
                "share (another group's size)" % len(share))
        if kind == 1:
            client = self._primed_client()
            share = rng.choice(self.geo_server_sizes)
            try:
                client._hybrid_shared(share)
            except dtlsproto.DtlsError:
                return
            except Exception as exc:  # noqa: BLE001
                raise Finding(
                    "geometry: foreign exception on a "
                    "%d-octet server share: %s"
                    % (len(share), repr(exc))) from exc
            raise Finding(
                "geometry: client accepted a %d-octet server "
                "share (another group's size)" % len(share))
        session = self._pumped_session()
        try:
            share, secret = session._hybrid_answer(
                self.geo_swapped_client)
        except dtlsproto.DtlsError:
            return
        except Exception as exc:  # noqa: BLE001
            raise Finding(
                "geometry: foreign exception on the "
                "order-swapped client share: " + repr(exc)
                ) from exc
        if self.ops.name == "abstract":
            # What refuses the swapped share in real mode is
            # the FIPS 203 section 7.2 content check, which
            # the seam abstracts to the length only (see the
            # campaign record): behind the seam the swapped
            # share is held to the framing contract instead —
            # DtlsError above, or a well-shaped answer here.
            want = 4 + dtlsproto.HYBRID_SERVER_SHARE_BYTES
            if len(share) != want or len(secret) != \
                    dtlsproto.HYBRID_SECRET_BYTES:
                raise Finding(
                    "geometry: abstract answer to the swapped "
                    "share returned wrong sizes")
            return
        raise Finding(
            "geometry: server accepted the client share with "
            "its parts in the RFC 9954 order")

    def _genuine_server_hello(self):
        if self._sh_raw is None:
            client = dtlsproto.DtlsClientCore(SECRET, hybrid=True)
            server = dtlsproto.DtlsServerCore(
                secret_lookup=dtlsproto.make_secret_lookup(SECRET),
                hybrid=True)
            out = client.start(NOW)
            found = None
            for _ in range(60):
                if not out:
                    break
                nxt = []
                for dg in out:
                    nxt += server.feed(dg, ADDR, NOW)
                for dg in nxt:
                    payload = dg[13:]
                    while len(payload) >= 12:
                        mlen = int.from_bytes(
                            payload[1:4], "big")
                        msg = payload[:12 + mlen]
                        if msg[0] == 2 and \
                                dtlsproto._parse_server_hello(
                                    msg[12:])["random"] != \
                                dtlsproto.HRR_RANDOM:
                            found = msg
                        payload = payload[12 + mlen:]
                out = []
                for dg in nxt:
                    out += client.feed(dg, NOW)
            assert found is not None
            self._sh_raw = found
            self._sh_fields = dtlsproto._parse_server_hello(
                found[12:])
        return self._sh_raw, self._sh_fields

    def _sh_record(self, exts):
        _raw, fields = self._genuine_server_hello()
        blob = b"".join(
            t.to_bytes(2, "big") + len(v).to_bytes(2, "big") + v
            for t, v in sorted(exts.items()))
        body = (self._sh_raw[12:14] + fields["random"] + b"\x00"
                + fields["suite"].to_bytes(2, "big") + b"\x00"
                + len(blob).to_bytes(2, "big") + blob)
        msg = (bytes([2]) + len(body).to_bytes(3, "big")
               + self._sh_raw[4:12] + body)
        return (bytes([22]) + b"\xfe\xfd"
                + (0).to_bytes(2, "big") + (0).to_bytes(6, "big")
                + len(msg).to_bytes(2, "big") + msg)

    def _victim_at_wait_sh(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            hybrid=True)
        victim = dtlsproto.DtlsClientCore(SECRET, hybrid=True)
        out = victim.start(NOW)
        for _ in range(6):
            nxt = []
            for dg in out:
                nxt += server.feed(dg, ADDR, NOW)
            out = []
            for dg in nxt:
                out += victim.feed(dg, NOW)
            if victim.state == "wait-sh":
                return victim
        raise Finding("harness: victim never reached wait-sh")

    def t_client_feed(self, rng):
        """A crafted ServerHello against a waiting client:
        the mirror of server_feed. Structural variants (an
        extension removed, a foreign group named) plus byte
        mutations of the genuine article. The contract is
        feed()'s own discipline elsewhere: a list back, or
        DtlsError — never a foreign exception. (This target's
        missing-key_share variant is finding F-1's shape;
        see the campaign record.)"""
        _raw, fields = self._genuine_server_hello()
        kind = rng.randrange(5)
        if kind == 4:
            msg = mutate(self._sh_raw, rng)
            record = (bytes([22]) + b"\xfe\xfd"
                      + (0).to_bytes(2, "big")
                      + (0).to_bytes(6, "big")
                      + len(msg).to_bytes(2, "big") + msg)
        else:
            exts = dict(fields["exts"])
            if kind == 0:
                exts.pop(51, None)          # no key_share
            elif kind == 1:
                exts.pop(41, None)          # no pre_shared_key
            elif kind == 2:
                exts.pop(43, None)          # no supported_versions
            else:                           # a foreign group
                code = rng.choice((4587, 4589, 25497, 25498))
                exts[51] = code.to_bytes(2, "big") + exts[51][2:]
            record = self._sh_record(exts)
        victim = self._victim_at_wait_sh()
        try:
            out = victim.feed(record, NOW)
        except dtlsproto.DtlsError:
            return
        except Exception as exc:  # noqa: BLE001
            raise Finding(
                "client feed raised a foreign exception: "
                + repr(exc)) from exc
        if not isinstance(out, list):
            raise Finding("client feed returned a non-list")

    def t_server_feed(self, rng):
        if self._hello is None:
            client = dtlsproto.DtlsClientCore(SECRET, hybrid=True)
            self._hello = client.start(NOW)[0]
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            hybrid=True)
        dg = mutate(self._hello, rng)
        try:
            out = server.feed(dg, ADDR, NOW)
        except Exception as exc:  # noqa: BLE001
            raise Finding(
                "server feed raised: " + repr(exc)) from exc
        if not isinstance(out, list):
            raise Finding("server feed returned a non-list")

    def run(self, name, rng):
        getattr(self, "t_" + name)(rng)


TARGET_NAMES = ("decaps", "encaps", "key_checks", "keygen",
                "client_shared", "server_answer", "server_feed",
                "geometry", "client_feed")


# ------------------------------------------------------------------
# The run
# ------------------------------------------------------------------

def _mem_avail_mb():
    try:
        with open("/proc/meminfo", "r", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


def run(mode, duration_s, rounds_cap, seed, emit,
        findings_path=None):
    ops = RealOps if mode == "real" else AbstractOps
    acvp = acvp_vectors()
    rng = random.Random(seed)
    findings = []

    def record_finding(target, exc):
        findings.append((target, repr(exc)))
        emit("hybrid-fuzz FINDING target=%s %s" % (target, exc))
        if findings_path:
            with open(findings_path, "a", encoding="utf-8") as fh:
                fh.write("target=%s error=%r\n" % (target, exc))

    with apply_ops(ops):
        targets = Targets(ops, acvp)
        # Positive controls before any mutation: a full
        # round trip through the ops in use, or the run is
        # measuring a broken harness. In real mode the ACVP
        # vector must also verify byte-exact.
        ek, dk = ops.keygen_internal(bytes(range(32)),
                                     bytes(range(32, 64)))
        secret, ct = ops.encaps_internal(ek, bytes(range(64, 96)))
        if ops.decaps(dk, ct) != secret or \
                not ops.ek_check(ek) or not ops.dk_check(dk):
            raise Finding("control: ops round trip disagrees")
        if ops.name == "real":
            _cs, s_share, v_secret, v_dk = hybrid_vector(acvp)
            if ops.decaps(v_dk, s_share[:mlkem.CT_BYTES]) != \
                    v_secret[:32]:
                raise Finding(
                    "control: hybrid vector decapsulation "
                    "disagrees")
        if dtlsproto._ecdh(ALICE_PRIV, BOB_PUB) != X25519_SHARED:
            raise Finding("control: RFC 7748 handshake disagrees")
        # The harvested RFC 10024 geometry must match the
        # code's own constants for the implemented group, or
        # the corpus is measuring the wrong shapes.
        own = next(
            g for g in rfc10024_groups()["groups"]
            if g["codepoint"] ==
            dtlsproto.GROUP_X25519MLKEM768)
        if own["client_share_bytes"] != \
                dtlsproto.HYBRID_CLIENT_SHARE_BYTES or \
                own["server_share_bytes"] != \
                dtlsproto.HYBRID_SERVER_SHARE_BYTES or \
                own["shared_secret_bytes"] != \
                dtlsproto.HYBRID_SECRET_BYTES or \
                own["kem_ek_bytes"] != mlkem.EK_BYTES or \
                own["kem_ct_bytes"] != mlkem.CT_BYTES:
            raise Finding(
                "control: RFC 10024 geometry disagrees with "
                "the code's constants")
        emit("hybrid-fuzz start mode=%s seed=%d targets=%s"
             % (mode, seed, ",".join(TARGET_NAMES)))
        started = time.time()
        rounds = 0
        while True:
            if rounds_cap and rounds >= rounds_cap:
                break
            if duration_s and time.time() - started >= duration_s:
                break
            name = rng.choice(TARGET_NAMES)
            try:
                targets.run(name, rng)
            except Finding as exc:
                record_finding(name, exc)
                if len(findings) >= 10:
                    break
            rounds += 1
            if rounds % 250 == 0:
                mem = _mem_avail_mb()
                emit("hybrid-fuzz round=%d findings=%d "
                     "elapsed_s=%d mem_avail_mb=%s"
                     % (rounds, len(findings),
                        int(time.time() - started), mem))
                if mem is not None and mem < MEM_FLOOR_MB:
                    emit("hybrid-fuzz verdict: ABORT memory "
                         "floor rounds=%d" % rounds)
                    return 4, rounds, findings
        emit("hybrid-fuzz verdict: rounds=%d findings=%d "
             "mode=%s seed=%d elapsed_s=%d"
             % (rounds, len(findings), mode, seed,
                int(time.time() - started)))
    return (3 if findings else 0), rounds, findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("real", "abstract"),
                        default="real")
    parser.add_argument("--duration", type=float, default=300.0,
                        help="seconds to run (0 = no time cap)")
    parser.add_argument("--rounds", type=int, default=0,
                        help="round cap (0 = no cap)")
    parser.add_argument("--seed", type=int, default=10024)
    parser.add_argument("--log", default=None,
                        help="append verdict lines to this file")
    args = parser.parse_args(argv)

    log_fh = open(args.log, "a", encoding="utf-8") \
        if args.log else None

    def emit(line):
        print(line, flush=True)
        if log_fh:
            log_fh.write(line + "\n")
            log_fh.flush()

    findings_path = (args.log + ".findings") if args.log else None
    try:
        code, _rounds, _findings = run(
            args.mode, args.duration, args.rounds, args.seed,
            emit, findings_path)
    finally:
        if log_fh:
            log_fh.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
