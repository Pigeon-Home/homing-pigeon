"""Tests for the RFC 10024 hybrid fuzzing effort.

Pins, deterministically and in-suite, what the campaign in
runner/tools/hybrid_fuzz.py runs at length on the rig:

- the corpus is the standards vectors (NIST ACVP ML-KEM-768,
  RFC 7748 section 6.1, and the hybrid vector constructed
  from them), through the production code;
- the bookend corpus carries every ASCII symbol plus NUL,
  tab, CR and LF, front and back;
- each field of each hybrid share has its own mutation
  tests (client share: encapsulation key, X25519 half;
  server share: ciphertext, X25519 half), plus the size
  discipline around both shares;
- the abstraction seam (AbstractOps) honours the same
  contracts as the production operations, and a hybrid
  handshake completes behind it with both sides agreeing;
- a bounded in-process fuzz run in each mode finds nothing.

The campaign record, with the suppositions these tests were
written against and the measured timings, is
docs/infrastructure-documents/proofs/hybrid-fuzz-10024.md.
"""

import os
import string
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.wire import dtlsproto, mlkem  # noqa: E402
from runner.tools import hybrid_fuzz as hf  # noqa: E402
from runner.tools import hybrid_timing  # noqa: E402
from runner.tests.test_dtls_hybrid import (  # noqa: E402
    _only_session, _pair)

NOW = 1000.0


def _primed_client():
    client = dtlsproto.DtlsClientCore(hf.SECRET, hybrid=True)
    client.start(NOW)
    return client


def _client_ek(client):
    dk = client._mlkem_dk
    return dk[384 * mlkem.K:384 * mlkem.K + mlkem.EK_BYTES]


class BookendCorpusTest(unittest.TestCase):
    def test_symbol_set_is_every_ascii_symbol_plus_controls(self):
        for ch in string.punctuation.encode("ascii"):
            self.assertIn(ch, hf.SYMBOLS)
        for ch in (0x00, 0x09, 0x0A, 0x0D):
            self.assertIn(ch, hf.SYMBOLS)

    def test_variants_bookend_front_and_back(self):
        data = b"AB"
        variants = dict(hf.bookend_variants(data))
        for sym in hf.SYMBOLS:
            s = bytes([sym])
            self.assertIn(s + data, variants.values())
            self.assertIn(data + s, variants.values())

    def test_symbol_only_strings_and_runs(self):
        values = list(dict(hf.bookend_variants(b"AB")).values())
        self.assertIn(b"-" * 256, values)
        self.assertIn(b"\x00" * 8, values)
        self.assertTrue(any(v.startswith(b"A" * 10 + b";")
                            for v in values))
        self.assertTrue(any(v.endswith(b";" + b"A" * 10)
                            for v in values))


class StandardsVectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.acvp = hf.acvp_vectors()

    def test_acvp_through_real_ops(self):
        ops = hf.RealOps
        for row in self.acvp["keygen"]:
            ek, dk = ops.keygen_internal(row["d"], row["z"])
            self.assertEqual((ek, dk), (row["ek"], row["dk"]))
        for row in self.acvp["encap"]:
            secret, ct = ops.encaps_internal(row["ek"], row["m"])
            self.assertEqual((secret, ct), (row["k"], row["c"]))
        for row in self.acvp["decap"]:
            # Includes the ACVP modified-ciphertext case,
            # whose expected secret is the rejection value.
            self.assertEqual(ops.decaps(row["dk"], row["c"]),
                             row["k"])

    def test_rfc7748_corpus_keys(self):
        self.assertEqual(dtlsproto.x25519_public(hf.ALICE_PRIV),
                         hf.ALICE_PUB)
        self.assertEqual(dtlsproto.x25519_public(hf.BOB_PRIV),
                         hf.BOB_PUB)
        self.assertEqual(dtlsproto._ecdh(hf.ALICE_PRIV, hf.BOB_PUB),
                         hf.X25519_SHARED)

    def test_hybrid_vector_through_the_engine_paths(self):
        client_share, server_share, secret, dk = hf.hybrid_vector(
            self.acvp)
        self.assertEqual(len(client_share),
                         dtlsproto.HYBRID_CLIENT_SHARE_BYTES)
        self.assertEqual(len(server_share),
                         dtlsproto.HYBRID_SERVER_SHARE_BYTES)
        # The vector assembles byte-exact at the primitive
        # level: decapsulating the vector's ciphertext under
        # the vector's key and concatenating the RFC 7748
        # secret reproduces the hybrid secret.
        mlkem_secret = mlkem.decaps(
            dk, server_share[:mlkem.CT_BYTES])
        client_secret = mlkem_secret + dtlsproto._ecdh(
            hf.ALICE_PRIV, hf.BOB_PUB)
        self.assertEqual(client_secret, secret)
        # Through the responder's engine path the same client
        # share is answered with a fresh encapsulation, and
        # the client's half of the path rebuilds the identical
        # secret from the answer.
        _client, server = _pair(True, True)
        session = _only_session(server)
        share, server_secret = session._hybrid_answer(client_share)
        self.assertEqual(
            len(share), 4 + dtlsproto.HYBRID_SERVER_SHARE_BYTES)
        ct2 = share[4:4 + mlkem.CT_BYTES]
        x2 = share[4 + mlkem.CT_BYTES:]
        rebuilt = mlkem.decaps(dk, ct2) + dtlsproto._ecdh(
            hf.ALICE_PRIV, x2)
        self.assertEqual(rebuilt, server_secret)


class PerFieldMutationTest(unittest.TestCase):
    """One test family per share field, per the per-field
    rule: a field's mutations are exercised against the path
    that consumes that field."""

    @classmethod
    def setUpClass(cls):
        cls.acvp = hf.acvp_vectors()
        (cls.client_share, cls.server_share, cls.secret,
         cls.dk) = hf.hybrid_vector(cls.acvp)
        _c, server = _pair(True, True)
        cls.session = _only_session(server)

    # -- client share, encapsulation-key field ---------------

    def test_ek_field_garbage_of_exact_size_is_refused(self):
        bad = b"\xff" * mlkem.EK_BYTES + hf.ALICE_PUB
        with self.assertRaises(dtlsproto.DtlsError):
            self.session._hybrid_answer(bad)

    def test_ek_field_bookended_is_refused(self):
        for _label, variant in hf.bookend_variants(
                self.client_share):
            if len(variant) == len(self.client_share):
                continue  # wraps change the size; sizes are below
            with self.assertRaises(dtlsproto.DtlsError):
                self.session._hybrid_answer(variant)

    # -- client share, X25519 field ---------------------------

    def test_client_x_field_zero_is_refused(self):
        share = self.client_share[:mlkem.EK_BYTES] + b"\x00" * 32
        with self.assertRaises(dtlsproto.DtlsError):
            self.session._hybrid_answer(share)

    def test_client_share_sizes_around_the_line(self):
        for n in (0, 1, 100, mlkem.EK_BYTES - 1,
                  mlkem.EK_BYTES, mlkem.EK_BYTES + 31,
                  dtlsproto.HYBRID_CLIENT_SHARE_BYTES - 1,
                  dtlsproto.HYBRID_CLIENT_SHARE_BYTES + 1,
                  2 * dtlsproto.HYBRID_CLIENT_SHARE_BYTES):
            data = (self.client_share * 3)[:n]
            with self.assertRaises(dtlsproto.DtlsError,
                                   msg="size %d" % n):
                self.session._hybrid_answer(data)

    # -- server share, ciphertext field -----------------------

    def test_ct_field_flip_yields_a_different_secret(self):
        client = _primed_client()
        ek = _client_ek(client)
        secret, ct = mlkem.encaps_internal(ek, bytes(range(32)))
        server_x = dtlsproto.x25519_public(hf.BOB_PRIV)
        good_share = ct + server_x
        client_x = dtlsproto.x25519_public(client._eph_hyb)
        want = secret + dtlsproto._ecdh(hf.BOB_PRIV, client_x)
        self.assertEqual(client._hybrid_shared(good_share), want)
        flipped = bytes([ct[0] ^ 1]) + ct[1:] + server_x
        got = client._hybrid_shared(flipped)
        self.assertEqual(len(got), dtlsproto.HYBRID_SECRET_BYTES)
        self.assertNotEqual(got, want)

    # -- server share, X25519 field ---------------------------

    def test_server_x_field_zero_is_refused(self):
        client = _primed_client()
        ek = _client_ek(client)
        _secret, ct = mlkem.encaps_internal(ek, bytes(range(32)))
        with self.assertRaises(dtlsproto.DtlsError):
            client._hybrid_shared(ct + b"\x00" * 32)

    def test_server_share_sizes_around_the_line(self):
        client = _primed_client()
        ek = _client_ek(client)
        _secret, ct = mlkem.encaps_internal(ek, bytes(range(32)))
        share = ct + dtlsproto.x25519_public(hf.BOB_PRIV)
        for n in (0, 1, mlkem.CT_BYTES - 1, mlkem.CT_BYTES,
                  dtlsproto.HYBRID_SERVER_SHARE_BYTES - 1,
                  dtlsproto.HYBRID_SERVER_SHARE_BYTES + 1,
                  2 * dtlsproto.HYBRID_SERVER_SHARE_BYTES):
            data = (share * 3)[:n]
            with self.assertRaises(dtlsproto.DtlsError,
                                   msg="size %d" % n):
                client._hybrid_shared(data)


class AbstractOpsContractTest(unittest.TestCase):
    def test_round_trip_and_sizes(self):
        ops = hf.AbstractOps
        ek, dk = ops.keygen_internal(bytes(range(32)),
                                     bytes(range(32, 64)))
        self.assertEqual(len(ek), mlkem.EK_BYTES)
        self.assertEqual(len(dk), mlkem.DK_BYTES)
        secret, ct = ops.encaps_internal(ek, bytes(range(64, 96)))
        self.assertEqual(len(ct), mlkem.CT_BYTES)
        self.assertEqual(ops.decaps(dk, ct), secret)

    def test_abstract_dk_passes_the_production_check(self):
        _ek, dk = hf.AbstractOps.keygen_internal(
            bytes(range(32)), bytes(range(32, 64)))
        self.assertTrue(mlkem.decapsulation_key_check(dk))

    def test_wrong_ct_is_a_different_secret_not_an_error(self):
        ops = hf.AbstractOps
        ek, dk = ops.keygen_internal(bytes(range(32)),
                                     bytes(range(32, 64)))
        secret, ct = ops.encaps_internal(ek, bytes(range(64, 96)))
        bad = bytes([ct[0] ^ 1]) + ct[1:]
        self.assertNotEqual(ops.decaps(dk, bad), secret)

    def test_length_discipline_matches(self):
        ops = hf.AbstractOps
        ek, dk = ops.keygen_internal(bytes(range(32)),
                                     bytes(range(32, 64)))
        with self.assertRaises(mlkem.MlkemError):
            ops.keygen_internal(b"short", bytes(32))
        with self.assertRaises(mlkem.MlkemError):
            ops.encaps_internal(ek, b"short")
        with self.assertRaises(mlkem.MlkemError):
            ops.encaps_internal(b"short", bytes(32))
        with self.assertRaises(mlkem.MlkemError):
            ops.decaps(dk, b"short")
        with self.assertRaises(mlkem.MlkemError):
            ops.decaps(b"short", bytes(mlkem.CT_BYTES))


class SeamHandshakeTest(unittest.TestCase):
    def test_handshake_completes_behind_the_seam(self):
        with hf.apply_ops(hf.AbstractOps):
            client, _server = _pair(True, True)
        self.assertEqual(client.state, "established")
        self.assertEqual(client.negotiated_group,
                         dtlsproto.GROUP_X25519MLKEM768)

    def test_module_is_restored_after_the_seam(self):
        before = mlkem.encaps_internal
        with hf.apply_ops(hf.AbstractOps):
            self.assertIsNot(mlkem.encaps_internal, before)
        self.assertIs(mlkem.encaps_internal, before)


class FuzzSmokeTest(unittest.TestCase):
    def test_bounded_real_run_is_clean(self):
        lines = []
        code, rounds, findings = hf.run(
            "real", 0, 40, 10024, lines.append)
        self.assertEqual(code, 0)
        self.assertEqual(findings, [])
        self.assertEqual(rounds, 40)
        self.assertTrue(any("verdict" in ln for ln in lines))

    def test_bounded_abstract_run_is_clean(self):
        lines = []
        code, rounds, findings = hf.run(
            "abstract", 0, 120, 7748, lines.append)
        self.assertEqual(code, 0)
        self.assertEqual(findings, [])
        self.assertEqual(rounds, 120)


class TimingTableTest(unittest.TestCase):
    def test_benchmark_reports_every_operation(self):
        rows = hybrid_timing.benchmark(budget_s=0.2)
        names = [r["op"] for r in rows]
        self.assertEqual(len(rows), 11)
        for needle in ("keygen", "encaps", "decaps",
                       "encapsulation_key_check", "x25519",
                       "composed", "handshake"):
            self.assertTrue(any(needle in n for n in names),
                            needle)
        for r in rows:
            self.assertGreater(r["median_ms"], 0)


if __name__ == "__main__":
    unittest.main()
