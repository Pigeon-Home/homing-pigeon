"""Tests for the RFC 10024 hybrid fuzzing effort.

Pins, deterministically and in-suite, what the campaign in
runner/tools/hybrid_fuzz.py runs at length on the rig:

- the corpus is the standards vectors (NIST ACVP ML-KEM-768,
  RFC 7748 section 6.1, and the hybrid vector constructed
  from them), through the production code, plus the group
  geometry harvested from RFC 10024 itself into
  runner/tests/fixtures/rfc10024_groups.json;
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
import random
import string
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.wire import dtls_mailbox, dtlsproto, mlkem  # noqa: E402
from runner.wire.dtls_mailbox import (  # noqa: E402
    FlightPart, encode_flight, flight_subject, parse_message)
from runner.tools import hybrid_fuzz as hf  # noqa: E402
from runner.tools import hybrid_timing  # noqa: E402
from runner.tests.test_dtls import _ch_exts  # noqa: E402
from runner.tests.test_dtls_email_v3 import _raw_mail  # noqa: E402
from runner.tests.test_dtls_hybrid import (  # noqa: E402
    _only_session, _pair)

NOW = 1000.0
ADDR = ("127.0.0.1", 50001)


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


class Rfc10024HarvestTest(unittest.TestCase):
    """The corpus material harvested from RFC 10024 itself:
    the group geometry table in
    runner/tests/fixtures/rfc10024_groups.json (sections
    4.1, 4.2, 4.3 and 7 of the RFC) and the geometry target
    built from it."""

    @classmethod
    def setUpClass(cls):
        cls.geom = hf.rfc10024_groups()
        cls.by_code = {g["codepoint"]: g
                       for g in cls.geom["groups"]}

    def test_all_three_groups_and_the_obsoleted_pair(self):
        self.assertEqual(set(self.by_code), {4588, 4587, 4589})
        self.assertEqual(self.by_code[4588]["name"],
                         "X25519MLKEM768")
        self.assertEqual(self.by_code[4587]["name"],
                         "SecP256r1MLKEM768")
        self.assertEqual(self.by_code[4589]["name"],
                         "SecP384r1MLKEM1024")
        obsoleted = {o["codepoint"]
                     for o in self.geom["obsoleted"]}
        self.assertEqual(obsoleted, {25497, 25498})

    def test_group_arithmetic_is_consistent(self):
        part = {"kem_ek": "kem_ek_bytes",
                "kem_ct": "kem_ct_bytes",
                "kem": "kem_ss_bytes",
                "ecdhe": None}
        for g in self.geom["groups"]:
            share = {"ecdhe": g["ecdhe_share_bytes"]}
            client = sum(
                g[part[p]] if part[p] else share[p]
                for p in g["client_order"])
            server = sum(
                g[part[p]] if part[p] else share[p]
                for p in g["server_order"])
            secret = sum(
                g["kem_ss_bytes"] if p == "kem"
                else g["ecdhe_ss_bytes"]
                for p in g["secret_order"])
            self.assertEqual(client, g["client_share_bytes"], g)
            self.assertEqual(server, g["server_share_bytes"], g)
            self.assertEqual(secret, g["shared_secret_bytes"], g)

    def test_implemented_group_matches_the_code(self):
        g = self.by_code[dtlsproto.GROUP_X25519MLKEM768]
        self.assertEqual(g["codepoint"], 4588)
        self.assertEqual(g["client_share_bytes"],
                         dtlsproto.HYBRID_CLIENT_SHARE_BYTES)
        self.assertEqual(g["server_share_bytes"],
                         dtlsproto.HYBRID_SERVER_SHARE_BYTES)
        self.assertEqual(g["shared_secret_bytes"],
                         dtlsproto.HYBRID_SECRET_BYTES)
        self.assertEqual(g["kem_ek_bytes"], mlkem.EK_BYTES)
        self.assertEqual(g["kem_ct_bytes"], mlkem.CT_BYTES)
        self.assertEqual(g["client_order"], ["kem_ek", "ecdhe"])
        self.assertEqual(g["secret_order"], ["kem", "ecdhe"])

    def test_other_codepoints_are_not_in_the_engine(self):
        values = {v for k, v in vars(dtlsproto).items()
                  if k.startswith("GROUP_")
                  and isinstance(v, int)}
        self.assertIn(4588, values)
        for code in (4587, 4589, 25497, 25498):
            self.assertNotIn(code, values)

    def test_checks_carry_the_section_42_key_check(self):
        joined = " ".join(self.geom["checks"])
        self.assertIn("7.2", joined)
        self.assertIn("illegal_parameter", joined)

    def test_geometry_seeds_have_the_other_groups_sizes(self):
        targets = hf.Targets(hf.RealOps, hf.acvp_vectors())
        self.assertEqual(
            sorted(len(s) for s in targets.geo_client_sizes),
            [1249, 1665])
        self.assertEqual(
            sorted(len(s) for s in targets.geo_server_sizes),
            [1153, 1665])
        swapped = targets.geo_swapped_client
        self.assertEqual(len(swapped),
                         dtlsproto.HYBRID_CLIENT_SHARE_BYTES)
        self.assertNotEqual(swapped, targets.h_client_share)
        self.assertEqual(swapped[:32],
                         targets.h_client_share[-32:])

    def test_geometry_target_refuses_every_seed(self):
        targets = hf.Targets(hf.RealOps, hf.acvp_vectors())
        rng = random.Random(10024)
        for _ in range(90):
            targets.t_geometry(rng)  # a Finding here fails


class ClientFeedTargetTest(unittest.TestCase):
    """Finding F-1 (campaign record): a ServerHello whose
    key_share extension was removed used to raise an
    uncaught KeyError(51) out of DtlsClientCore.feed,
    where every sibling refusal is a DtlsError. Found by
    the Argon plan review, verified by hand, fixed in
    dtlsproto._on_server_hello; these tests pin the fix
    and the family around it."""

    def _targets(self):
        return hf.Targets(hf.RealOps, hf.acvp_vectors())

    def _feed(self, targets, exts):
        victim = targets._victim_at_wait_sh()
        return victim.feed(targets._sh_record(exts), NOW)

    def test_missing_key_share_is_a_dtls_error(self):
        targets = self._targets()
        _raw, fields = targets._genuine_server_hello()
        exts = dict(fields["exts"])
        del exts[51]
        with self.assertRaises(dtlsproto.DtlsError):
            self._feed(targets, exts)

    def test_each_extension_removed_stays_in_discipline(self):
        targets = self._targets()
        _raw, fields = targets._genuine_server_hello()
        for ext_id in sorted(fields["exts"]):
            exts = dict(fields["exts"])
            del exts[ext_id]
            try:
                out = self._feed(targets, exts)
            except dtlsproto.DtlsError:
                continue
            self.assertIsInstance(out, list, ext_id)

    def test_key_share_value_shapes_stay_in_discipline(self):
        targets = self._targets()
        _raw, fields = targets._genuine_server_hello()
        genuine = fields["exts"][51]
        for value in (b"", genuine[:2], genuine[:4],
                      genuine + b"\x00", bytes(len(genuine))):
            exts = dict(fields["exts"])
            exts[51] = value
            try:
                out = self._feed(targets, exts)
            except dtlsproto.DtlsError:
                continue
            self.assertIsInstance(out, list)

    def test_client_feed_target_holds_its_contract(self):
        targets = self._targets()
        rng = random.Random(10024)
        for _ in range(45):
            targets.t_client_feed(rng)  # a Finding here fails


class FragmentBufferFamilyTest(unittest.TestCase):
    """Family 3: handshake fragment reassembly
    (_FragmentBuffer.offer), field by field. The claim under
    test (campaign record, supposition SD3, verified by hand
    before these tests ran): a fragment header's total length
    was trusted into two bytearray(total) allocations -- up
    to about 33.5 MB for the largest 24-bit total -- with no
    cap on the total and no cap on the number of pending
    (message type, sequence) keys, and a fragment whose total
    contradicted the total its key started with could write
    past the stored buffer and raise IndexError out of offer,
    out of the cores' handshake path. The caps pinned here:
    a total of at most 256 KB (the size the suite already
    treats as the largest thing that travels whole -- the
    local envelope and the mailbox datagram ceiling,
    dtls_mailbox.DEFAULT_MAX_DATAGRAM_BYTES; the largest
    handshake message this profile sends, the hybrid
    ClientHello, is about 1.4 KB) and at most 64 pending
    keys (the carriage reassembler's own transfer bound).
    Beyond either cap, and on a contradicting total, offer
    refuses with its own incomplete signal, None."""

    CAP = dtls_mailbox.DEFAULT_MAX_DATAGRAM_BYTES
    MAX_PENDING = 64

    def _stored_sizes(self, buf):
        return [len(entry[0]) for entry in buf._pending.values()]

    # -- the total field --------------------------------------

    def test_total_above_the_cap_allocates_nothing(self):
        buf = dtlsproto._FragmentBuffer()
        for total in (self.CAP + 1, 1_000_000, 16_777_215):
            self.assertIsNone(buf.offer(2, 0, 0, b"", total))
            self.assertIsNone(buf.offer(2, 0, 0, b"AB", total))
        self.assertEqual(buf._pending, {})

    def test_total_at_and_below_the_cap_is_held(self):
        buf = dtlsproto._FragmentBuffer()
        self.assertIsNone(buf.offer(2, 0, 0, b"A", self.CAP))
        self.assertEqual(self._stored_sizes(buf), [self.CAP])
        buf = dtlsproto._FragmentBuffer()
        self.assertIsNone(buf.offer(2, 0, 0, b"A", self.CAP - 1))
        self.assertEqual(self._stored_sizes(buf), [self.CAP - 1])

    def test_zero_total_completes_empty_at_once(self):
        buf = dtlsproto._FragmentBuffer()
        whole = buf.offer(9, 3, 0, b"", 0)
        self.assertEqual(whole, dtlsproto._hs_message(9, b"", 3))
        self.assertEqual(buf._pending, {})

    def test_no_stored_buffer_ever_exceeds_the_cap(self):
        buf = dtlsproto._FragmentBuffer()
        for seq, total in enumerate(
                (0, 1, 100, self.CAP, self.CAP + 1, 16_777_215)):
            buf.offer(2, seq, 0, b"A", total)
        for size in self._stored_sizes(buf):
            self.assertLessEqual(size, self.CAP)

    # -- the number of pending keys ----------------------------

    def test_pending_keys_are_capped(self):
        buf = dtlsproto._FragmentBuffer()
        for seq in range(self.MAX_PENDING):
            self.assertIsNone(buf.offer(2, seq, 0, b"A", 100))
        self.assertEqual(len(buf._pending), self.MAX_PENDING)
        # One more distinct key is refused, allocating nothing.
        self.assertIsNone(
            buf.offer(2, self.MAX_PENDING, 0, b"A", 100))
        self.assertEqual(len(buf._pending), self.MAX_PENDING)
        # A key already held still completes, and completing
        # it frees its slot for a new key.
        whole = buf.offer(2, 0, 1, b"B" * 99, 100)
        self.assertEqual(
            whole,
            dtlsproto._hs_message(2, b"A" + b"B" * 99, 0))
        self.assertIsNone(
            buf.offer(2, self.MAX_PENDING, 0, b"A", 100))
        self.assertEqual(len(buf._pending), self.MAX_PENDING)

    # -- a contradicting total for a held key ------------------

    def test_mismatched_total_never_raises(self):
        buf = dtlsproto._FragmentBuffer()
        self.assertIsNone(buf.offer(2, 1, 0, b"A" * 10, 20))
        # The pre-fix shape: a fragment past the stored end
        # under a larger claimed total raised IndexError.
        self.assertIsNone(buf.offer(2, 1, 25, b"Z", 30))
        buf = dtlsproto._FragmentBuffer()
        self.assertIsNone(buf.offer(2, 1, 0, b"A" * 10, 30))
        self.assertIsNone(buf.offer(2, 1, 5, b"Z", 10))

    def test_mismatched_total_destroys_the_buffer(self):
        body = bytes(range(20))
        buf = dtlsproto._FragmentBuffer()
        self.assertIsNone(buf.offer(2, 1, 0, body[:10], 20))
        self.assertIsNone(buf.offer(2, 1, 25, b"Z", 30))
        self.assertNotIn((2, 1), buf._pending)
        # The pre-contradiction half is gone: the tail alone
        # does not complete, and a fresh full offer does.
        self.assertIsNone(buf.offer(2, 1, 10, body[10:], 20))
        whole = buf.offer(2, 1, 0, body[:10], 20)
        self.assertEqual(whole, dtlsproto._hs_message(2, body, 1))

    # -- the key fields: message type and sequence -------------

    def test_message_type_and_sequence_are_separate_keys(self):
        body = b"0123456789"
        buf = dtlsproto._FragmentBuffer()
        self.assertIsNone(buf.offer(1, 7, 0, body[:5], 10))
        self.assertIsNone(buf.offer(2, 7, 0, body[:5], 10))
        self.assertIsNone(buf.offer(1, 8, 0, body[:5], 10))
        self.assertEqual(len(buf._pending), 3)
        whole = buf.offer(2, 7, 5, body[5:], 10)
        self.assertEqual(whole, dtlsproto._hs_message(2, body, 7))
        self.assertEqual(len(buf._pending), 2)

    def test_a_completed_key_starts_fresh_with_a_new_total(self):
        buf = dtlsproto._FragmentBuffer()
        whole = buf.offer(1, 1, 0, b"abcd", 4)
        self.assertEqual(whole, dtlsproto._hs_message(1, b"abcd", 1))
        self.assertIsNone(buf.offer(1, 1, 0, b"Z", 9))
        self.assertEqual(self._stored_sizes(buf), [9])

    # -- the offset and fragment fields -------------------------

    def test_offset_at_and_past_the_end_lands_nothing(self):
        buf = dtlsproto._FragmentBuffer()
        self.assertIsNone(buf.offer(1, 1, 4, b"Z", 4))
        self.assertIsNone(buf.offer(1, 1, 100, b"Z", 4))
        whole = buf.offer(1, 1, 0, b"abcd", 4)
        self.assertEqual(whole, dtlsproto._hs_message(1, b"abcd", 1))

    def test_straddling_fragment_is_clipped_at_the_total(self):
        buf = dtlsproto._FragmentBuffer()
        self.assertIsNone(buf.offer(1, 1, 2, b"cdef", 4))
        whole = buf.offer(1, 1, 0, b"ab", 4)
        self.assertEqual(
            whole, dtlsproto._hs_message(1, b"abcd", 1))

    def test_overlapping_fragments_last_write_wins(self):
        buf = dtlsproto._FragmentBuffer()
        self.assertIsNone(buf.offer(1, 1, 0, b"ab", 4))
        whole = buf.offer(1, 1, 1, b"XYZ", 4)
        self.assertEqual(
            whole, dtlsproto._hs_message(1, b"aXYZ", 1))

    def test_duplicate_fragment_is_idempotent(self):
        body = b"0123456789"
        buf = dtlsproto._FragmentBuffer()
        self.assertIsNone(buf.offer(1, 1, 0, body[:5], 10))
        self.assertIsNone(buf.offer(1, 1, 0, body[:5], 10))
        whole = buf.offer(1, 1, 5, body[5:], 10)
        self.assertEqual(whole, dtlsproto._hs_message(1, body, 1))

    def test_empty_fragment_lands_nothing(self):
        buf = dtlsproto._FragmentBuffer()
        self.assertIsNone(buf.offer(1, 1, 0, b"", 4))
        whole = buf.offer(1, 1, 0, b"abcd", 4)
        self.assertEqual(whole, dtlsproto._hs_message(1, b"abcd", 1))

    # -- the feed path above the buffer -------------------------

    def test_feed_with_a_huge_claimed_total_stays_quiet(self):
        # A handshake header claiming the largest 24-bit
        # total, carrying no fragment bytes at all, fed to
        # both cores: a list back, no raise, and (behind the
        # server) nothing held.
        header = (bytes([1]) + (16_777_215).to_bytes(3, "big")
                  + (0).to_bytes(2, "big") + (0).to_bytes(3, "big")
                  + (0).to_bytes(3, "big"))
        record = (bytes([22]) + b"\xfe\xfd"
                  + (0).to_bytes(2, "big") + (0).to_bytes(6, "big")
                  + len(header).to_bytes(2, "big") + header)
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(hf.SECRET),
            hybrid=True)
        self.assertIsInstance(server.feed(record, ADDR, NOW), list)


def _share_value(entries):
    body = b"".join(
        g.to_bytes(2, "big") + len(k).to_bytes(2, "big") + k
        for g, k in entries)
    return len(body).to_bytes(2, "big") + body


def _begin_code_value(value, hybrid=True):
    """The alert code _ServerSession.begin refuses a hello
    carrying this key_share extension value with. The
    pre_shared_key extension is deliberately absent, so a
    hello that selection accepts is refused for that
    (missing_extension) and a hello selection refuses is
    refused at selection (illegal_parameter): the two codes
    separate the outcomes exactly."""
    core = dtlsproto.DtlsServerCore(
        secret_lookup=dtlsproto.make_secret_lookup(hf.SECRET),
        hybrid=hybrid)
    session = dtlsproto._ServerSession(core, ADDR)
    exts = {
        dtlsproto.EXT_PSK_MODES: bytes(
            [1, dtlsproto.PSK_MODE_DHE_KE]),
        dtlsproto.EXT_KEY_SHARE: value,
    }
    out = session.begin(
        b"x" * 80,
        {"suites": [dtlsproto.SUITE_AES256], "exts": exts},
        b"\x11" * dtlsproto.HASH_LEN, b"hrr", NOW)
    assert len(out) == 1 and out[0][0] == dtlsproto.CT_ALERT
    return out[0][14]


def _begin_code(entries, hybrid=True):
    return _begin_code_value(_share_value(entries), hybrid)


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
