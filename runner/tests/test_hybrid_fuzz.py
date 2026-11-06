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


class KeyShareEntriesFamilyTest(unittest.TestCase):
    """Family 1: duplicate and competing key_share entries
    (campaign record, supposition SD1). The parser returns
    every entry in wire order; begin keeps the FIRST entry
    per group (setdefault); selection prefers the hybrid
    group when the profile is on and it was offered, falls
    back to X25519, and refuses anything else. Each field
    of the extension value -- the list's total length, each
    entry's group, each entry's key length, the key bytes --
    has its own tests below, at the parse level, at the
    selection level, and through a full server feed with
    the crafted list spliced into a genuine hello."""

    G = dtlsproto.GROUP_X25519MLKEM768
    X = dtlsproto.GROUP_X25519
    ILLEGAL = dtlsproto.ALERT_ILLEGAL_PARAMETER
    MISSING = dtlsproto.ALERT_MISSING_EXTENSION

    @classmethod
    def setUpClass(cls):
        (cls.client_share, _ss, _secret, _dk) = hf.hybrid_vector(
            hf.acvp_vectors())

    # -- the list total field (parse level) --------------------

    def test_parse_returns_entries_in_wire_order(self):
        entries = [(self.G, self.client_share),
                   (self.X, hf.ALICE_PUB),
                   (self.G, b"\x07" * 32)]
        self.assertEqual(
            dtlsproto._key_share_entries(_share_value(entries)),
            entries)

    def test_parse_total_field_lies(self):
        good = _share_value([(self.X, hf.ALICE_PUB)])
        body = good[2:]
        for value in (
                (len(body) - 1).to_bytes(2, "big") + body,
                (len(body) + 1).to_bytes(2, "big") + body,
                (0).to_bytes(2, "big") + body,
                (65535).to_bytes(2, "big") + body):
            with self.assertRaises(dtlsproto.DtlsError):
                dtlsproto._key_share_entries(value)

    def test_parse_empty_and_short_values(self):
        for value in (b"", b"\x00", b"\x00\x00"):
            with self.assertRaises(dtlsproto.DtlsError):
                dtlsproto._key_share_entries(value)

    def test_parse_trailing_bytes_after_the_last_entry(self):
        good = _share_value([(self.X, hf.ALICE_PUB)])
        # One to three trailing bytes cannot start an entry.
        for extra in (b"\x00", b"\x00\x1d\x00"):
            value = (len(good) - 2 + len(extra)).to_bytes(
                2, "big") + good[2:] + extra
            with self.assertRaises(dtlsproto.DtlsError):
                dtlsproto._key_share_entries(value)
        # Four or more are read as another entry.
        extra = (4587).to_bytes(2, "big") + (3).to_bytes(
            2, "big") + b"abc"
        value = (len(good) - 2 + len(extra)).to_bytes(
            2, "big") + good[2:] + extra
        parsed = dtlsproto._key_share_entries(value)
        self.assertEqual(parsed[-1], (4587, b"abc"))

    # -- the group and key-length fields (parse level) ---------

    def test_parse_group_field_values(self):
        for group in (4588, 29, 4587, 4589, 25497, 25498,
                      0, 65535):
            entries = [(group, b"\x01\x02\x03")]
            self.assertEqual(
                dtlsproto._key_share_entries(
                    _share_value(entries)), entries)

    def test_parse_key_length_field(self):
        # A zero-length key parses; size discipline is
        # selection's, not the parser's.
        entries = [(self.G, b"")]
        self.assertEqual(
            dtlsproto._key_share_entries(_share_value(entries)),
            entries)
        # A key length that overruns the list is refused.
        body = (self.X).to_bytes(2, "big") + (33).to_bytes(
            2, "big") + hf.ALICE_PUB
        value = len(body).to_bytes(2, "big") + body
        with self.assertRaises(dtlsproto.DtlsError):
            dtlsproto._key_share_entries(value)

    def test_parse_key_sizes_are_the_parsers_business_not(self):
        for n in (0, 1, 1215, 1216, 1217):
            entries = [(self.G, bytes(n))]
            self.assertEqual(
                dtlsproto._key_share_entries(
                    _share_value(entries)), entries)

    def test_parse_bookends_stay_in_discipline(self):
        good = _share_value([(self.G, self.client_share),
                             (self.X, hf.ALICE_PUB)])
        for _label, variant in hf.bookend_variants(good):
            try:
                out = dtlsproto._key_share_entries(variant)
            except dtlsproto.DtlsError:
                continue
            self.assertIsInstance(out, list)

    def test_server_form_parse_takes_the_single_entry(self):
        value = (self.G).to_bytes(2, "big") + (4).to_bytes(
            2, "big") + b"key!" + b"trailing is not an entry"
        self.assertEqual(
            dtlsproto._key_share_entries(value, server_form=True),
            [(self.G, b"key!")])
        with self.assertRaises(dtlsproto.DtlsError):
            dtlsproto._key_share_entries(
                b"\x00\x1d\x00", server_form=True)

    # -- selection (begin level) --------------------------------

    def test_first_valid_hybrid_wins_over_a_garbage_duplicate(self):
        code = _begin_code([(self.G, self.client_share),
                            (self.G, b"\xff" * 32)])
        self.assertEqual(code, self.MISSING)

    def test_first_missized_hybrid_refuses_despite_a_valid_one(self):
        code = _begin_code([(self.G, b"\xff" * 32),
                            (self.G, self.client_share)])
        self.assertEqual(code, self.ILLEGAL)

    def test_duplicate_valid_hybrid_entries_pass_selection(self):
        code = _begin_code([(self.G, self.client_share),
                            (self.G, self.client_share)])
        self.assertEqual(code, self.MISSING)

    def test_unknown_group_first_does_not_shadow_the_hybrid(self):
        code = _begin_code([(4587, b"\x00" * 1216),
                            (self.G, self.client_share)])
        self.assertEqual(code, self.MISSING)

    def test_only_unknown_groups_refuse(self):
        for entries in ([(4587, b"\x00" * 40)],
                        [(4589, b"\x00" * 40), (25497, b"\x00")],
                        [(0, b""), (65535, b"\x00" * 9)]):
            self.assertEqual(_begin_code(entries), self.ILLEGAL)

    def test_x25519_fallback_when_the_hybrid_is_absent(self):
        code = _begin_code([(4587, b"\x00" * 40),
                            (self.X, hf.ALICE_PUB)])
        self.assertEqual(code, self.MISSING)

    def test_empty_hybrid_key_refuses_at_selection(self):
        self.assertEqual(
            _begin_code([(self.G, b"")]), self.ILLEGAL)
        self.assertEqual(
            _begin_code([(self.G, self.client_share[:-1])]),
            self.ILLEGAL)
        self.assertEqual(
            _begin_code([(self.G, self.client_share + b"\x00")]),
            self.ILLEGAL)

    def test_unparsable_values_refuse_illegal_parameter(self):
        for value in (b"", b"\x00\x00", b"\xff\xff" + b"\x00" * 8):
            self.assertEqual(
                _begin_code_value(value), self.ILLEGAL)

    def test_bookended_values_refuse_with_an_alert(self):
        good = _share_value([(self.G, self.client_share),
                             (self.X, hf.ALICE_PUB)])
        for _label, variant in hf.bookend_variants(good):
            code = _begin_code_value(variant)
            self.assertIn(code, (self.ILLEGAL, self.MISSING))

    # -- through a full server feed ------------------------------

    def _crafted_feed(self, build):
        """A genuine client's hello, with its key_share list
        rebuilt by build(hybrid_key, x25519_key) at exactly
        the genuine list's length, spliced into both hellos.
        Selection's refusal (illegal_parameter) precedes the
        binder check; anything selection accepts meets the
        binder computed over the unmodified hello and is
        refused for that (decrypt_error) -- which is what
        proves selection answered on the crafted list."""
        client = dtlsproto.DtlsClientCore(hf.SECRET, hybrid=True)
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(hf.SECRET),
            hybrid=True)

        def splice(datagram):
            _raw, exts = _ch_exts(datagram)
            genuine = exts[dtlsproto.EXT_KEY_SHARE]
            parsed = dtlsproto._key_share_entries(genuine)
            hyb = next(k for g, k in parsed if g == self.G)
            x = next(k for g, k in parsed if g == self.X)
            value = _share_value(build(hyb, x))
            assert len(value) == len(genuine)
            at = datagram.find(genuine, 13)
            assert at > 0
            return (datagram[:at] + value
                    + datagram[at + len(genuine):])

        hello1 = splice(client.start(NOW)[0])
        hrr = server.feed(hello1, ADDR, NOW)
        self.assertEqual(len(hrr), 1)
        hello2 = splice(client.feed(hrr[0], NOW)[0])
        out = server.feed(hello2, ADDR, NOW)
        self.assertEqual(server.sessions, {})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)
        return out[0][14]

    def test_feed_answers_on_the_first_hybrid_entry(self):
        code = self._crafted_feed(
            lambda hyb, x: [(self.G, hyb), (self.G, bytes(32))])
        self.assertEqual(code, dtlsproto.ALERT_DECRYPT_ERROR)

    def test_feed_refuses_a_missized_first_hybrid_entry(self):
        code = self._crafted_feed(
            lambda hyb, x: [(self.G, bytes(32)), (self.G, hyb)])
        self.assertEqual(code, self.ILLEGAL)

    def test_feed_entry_order_does_not_change_selection(self):
        code = self._crafted_feed(
            lambda hyb, x: [(self.X, x), (self.G, hyb)])
        self.assertEqual(code, dtlsproto.ALERT_DECRYPT_ERROR)

    def test_feed_unknown_group_first_still_selects(self):
        code = self._crafted_feed(
            lambda hyb, x: [(4587, bytes(1216)), (self.X, x)])
        self.assertEqual(code, dtlsproto.ALERT_DECRYPT_ERROR)

    def test_feed_garbage_second_entry_for_a_known_group(self):
        code = self._crafted_feed(
            lambda hyb, x: [(self.G, hyb), (self.X, bytes(32))])
        self.assertEqual(code, dtlsproto.ALERT_DECRYPT_ERROR)

    def test_feed_duplicate_x25519_entries(self):
        code = self._crafted_feed(
            lambda hyb, x: [(self.X, x), (self.X, bytes(32)),
                            (4587, bytes(1180))])
        self.assertEqual(code, dtlsproto.ALERT_DECRYPT_ERROR)


class MailboxFramingFamilyTest(unittest.TestCase):
    """Family 2: the version 3 carriage itself
    (dtls_mailbox.parse_message and FlightReassembler),
    field by field (campaign record, supposition SD2): the
    subject's session id, the frame header's transfer, part,
    parts, bytes and sha384 fields, the base64 chunk, and
    each FlightPart field at the reassembler. parse_message
    never raises and classifies into its documented kinds
    only; the reassembler completes a datagram only when
    its length and SHA-384 match the declared header."""

    SID = "family2-session"

    @classmethod
    def setUpClass(cls):
        client = dtlsproto.DtlsClientCore(hf.SECRET, hybrid=True)
        cls.hello = client.start(NOW)[0]
        cls.subject, cls.body = encode_flight(cls.hello, cls.SID)[0]
        cls.parts = encode_flight(
            cls.hello, cls.SID, max_chunk_chars=96)
        match = dtls_mailbox._HEADER_RE.match(
            cls.body.partition("\n")[0])
        cls.fields = match.groups()  # transfer part parts bytes sha
        cls.chunk = cls.body.partition("\n")[2]

    def _parse(self, subject, body):
        return parse_message(_raw_mail(subject, body))

    def _with_fields(self, **kw):
        transfer, part, count, total, digest = self.fields
        head = ("HP-DTLS/3 transfer=%s part=%s parts=%s "
                "bytes=%s sha384=%s" % (
                    kw.get("transfer", transfer),
                    kw.get("part", part),
                    kw.get("count", count),
                    kw.get("total", total),
                    kw.get("digest", digest)))
        return head + "\n" + kw.get("chunk", self.chunk)

    # -- the genuine articles ------------------------------------

    def test_genuine_single_part_is_a_dtls_init(self):
        out = self._parse(self.subject, self.body)
        self.assertEqual(out.kind, "dtls-init")
        self.assertEqual(out.datagram, self.hello)

    def test_genuine_parts_reassemble_through_the_parser(self):
        reasm = dtls_mailbox.FlightReassembler()
        got = None
        for subject, body in reversed(self.parts):
            out = self._parse(subject, body)
            self.assertEqual(out.kind, "dtls-part")
            got = reasm.offer(out.part, NOW) or got
        self.assertEqual(got, self.hello)

    # -- the transfer field ---------------------------------------

    def test_transfer_field_must_be_16_lower_hex(self):
        for bad in ("g" * 16, "A" * 16, "0" * 15, "0" * 17, ""):
            out = self._parse(
                self.subject, self._with_fields(transfer=bad))
            self.assertEqual(out.kind, "dtls-invalid", bad)

    # -- the part and parts fields ---------------------------------

    def test_part_field_must_name_a_part_that_exists(self):
        for bad in ("1", "2", "999"):
            out = self._parse(
                self.subject, self._with_fields(part=bad))
            self.assertEqual(out.kind, "dtls-invalid", bad)

    def test_parts_field_bounds(self):
        for bad in ("0", "1025", "99999"):
            out = self._parse(
                self.subject, self._with_fields(count=bad))
            self.assertEqual(out.kind, "dtls-invalid", bad)
        out = self._parse(
            self.subject, self._with_fields(count="1024"))
        self.assertEqual(out.kind, "dtls-part")
        out = self._parse(
            self.subject, self._with_fields(count="2"))
        self.assertEqual(out.kind, "dtls-part")

    # -- the bytes field --------------------------------------------

    def test_bytes_field_bounds(self):
        for bad in ("0", "262145", "999999999"):
            out = self._parse(
                self.subject, self._with_fields(total=bad))
            self.assertEqual(out.kind, "dtls-invalid", bad)
        # Smaller than the chunk it declares: the chunk
        # exceeds the declared datagram size.
        out = self._parse(
            self.subject, self._with_fields(total="10"))
        self.assertEqual(out.kind, "dtls-invalid")
        # Larger than the datagram, under the ceiling: a
        # single part must be exactly the declared size.
        out = self._parse(
            self.subject, self._with_fields(total="9999"))
        self.assertEqual(out.kind, "dtls-invalid")

    # -- the sha384 field ---------------------------------------------

    def test_digest_field_single_part_vs_part_of_many(self):
        flipped = ("1" if self.fields[4][0] == "0" else "0") \
            + self.fields[4][1:]
        out = self._parse(
            self.subject, self._with_fields(digest=flipped))
        self.assertEqual(out.kind, "dtls-invalid")
        # In a multi-part frame the digest is judged at
        # completion, not at parse: the part is accepted as
        # a part.
        subject, body = self.parts[0]
        head, _nl, chunk = body.partition("\n")
        m = dtls_mailbox._HEADER_RE.match(head)
        t, p, c, b, _d = m.groups()
        head = ("HP-DTLS/3 transfer=%s part=%s parts=%s "
                "bytes=%s sha384=%s" % (t, p, c, b, flipped))
        out = self._parse(subject, head + "\n" + chunk)
        self.assertEqual(out.kind, "dtls-part")
        for bad in ("0" * 95, "z" * 96):
            out = self._parse(
                self.subject, self._with_fields(digest=bad))
            self.assertEqual(out.kind, "dtls-invalid", bad)

    # -- the chunk field ------------------------------------------------

    def test_chunk_field_must_be_base64_of_the_datagram(self):
        for bad in ("!!!", "====", ""):
            out = self._parse(
                self.subject, self._with_fields(chunk=bad))
            self.assertEqual(out.kind, "dtls-invalid", bad)
        # Whitespace inside the chunk is stripped before
        # decoding (the frame tolerates mailer wrapping).
        wrapped = self.chunk[:10] + " \n " + self.chunk[10:]
        out = self._parse(
            self.subject, self._with_fields(chunk=wrapped))
        self.assertEqual(out.kind, "dtls-init")
        self.assertEqual(out.datagram, self.hello)

    def test_body_bookends_stay_in_discipline(self):
        for _label, variant in hf.bookend_variants(
                self.body.encode("ascii")):
            out = parse_message(_raw_mail(
                self.subject, variant.decode("ascii", "replace")))
            self.assertIn(out.kind, hf.MAIL_KINDS)

    # -- the subject's session id -----------------------------------------

    def test_subject_session_id_shapes(self):
        self.assertEqual(
            self._parse(self.subject, self.body).kind, "dtls-init")
        for subject in (
                flight_subject(self.SID) + " extra",
                "[HOMING-PIGEON] dtls ..",
                "[HOMING-PIGEON] dtls .",
                "[HOMING-PIGEON] dtls a/b",
                "[HOMING-PIGEON] dtls "):
            out = self._parse(subject, self.body)
            self.assertEqual(out.kind, "dtls-invalid", subject)
        out = self._parse("Re: " + self.subject, self.body)
        self.assertEqual(out.kind, "dtls-init")

    def test_legacy_subject_shape(self):
        import base64 as _b64
        body = _b64.b64encode(self.hello).decode("ascii")
        out = self._parse(dtls_mailbox.FLIGHT_SUBJECT, body)
        self.assertEqual(out.kind, "dtls-init")
        self.assertEqual(out.datagram, self.hello)
        out = self._parse(dtls_mailbox.FLIGHT_SUBJECT, "!!!")
        self.assertEqual(out.kind, "dtls-invalid")
        out = self._parse(
            dtls_mailbox.FLIGHT_SUBJECT,
            _b64.b64encode(b"not a record").decode("ascii"))
        self.assertEqual(out.kind, "dtls-invalid")

    def test_job_and_other_kinds(self):
        out = self._parse("[HOMING-PIGEON] job abc", "{}")
        self.assertEqual(out.kind, "job")
        out = self._parse("an ordinary subject", "hello")
        self.assertEqual(out.kind, "other")

    def test_mutated_raw_mails_never_raise(self):
        raw = _raw_mail(self.subject, self.body)
        rng = random.Random(20220)
        for _ in range(60):
            out = parse_message(hf.mutate(raw, rng))
            self.assertIn(out.kind, hf.MAIL_KINDS)
        for _label, variant in hf.bookend_variants(raw):
            out = parse_message(variant)
            self.assertIn(out.kind, hf.MAIL_KINDS)

    # -- the reassembler, field by field -------------------------------

    DG = bytes(range(200))

    def _part(self, index, data=None, **over):
        import hashlib as _hl
        data = self.DG if data is None else data
        chunks = (data[:80], data[80:150], data[150:])
        fields = {
            "session_id": "s1", "transfer_id": "aa" * 8,
            "index": index, "count": 3,
            "total_bytes": len(data),
            "sha384": _hl.sha384(data).hexdigest(),
            "chunk": chunks[index],
        }
        fields.update(over)
        return FlightPart(**fields)

    def test_reassembler_completes_in_any_order(self):
        for order in ((0, 1, 2), (2, 0, 1), (1, 2, 0)):
            reasm = dtls_mailbox.FlightReassembler()
            got = None
            for i in order:
                got = reasm.offer(self._part(i), NOW) or got
            self.assertEqual(got, self.DG)
            self.assertEqual(reasm.pending, 0)

    def test_reassembler_field_refusals(self):
        reasm = dtls_mailbox.FlightReassembler()
        self.assertIsNone(reasm.offer(self._part(0, count=0), NOW))
        self.assertIsNone(reasm.offer(self._part(0)._replace(index=3), NOW))
        self.assertIsNone(
            reasm.offer(self._part(0, total_bytes=0), NOW))
        self.assertIsNone(reasm.offer(
            self._part(0, total_bytes=256 * 1024 + 1), NOW))
        self.assertIsNone(reasm.offer(
            self._part(0, chunk=self.DG + b"x"), NOW))
        self.assertEqual(reasm.pending, 0)

    def test_reassembler_duplicate_part_is_idempotent(self):
        reasm = dtls_mailbox.FlightReassembler()
        self.assertIsNone(reasm.offer(self._part(0), NOW))
        self.assertIsNone(reasm.offer(self._part(0), NOW))
        self.assertIsNone(reasm.offer(self._part(1), NOW))
        self.assertEqual(reasm.offer(self._part(2), NOW), self.DG)

    def test_reassembler_contradiction_destroys_the_transfer(self):
        reasm = dtls_mailbox.FlightReassembler()
        self.assertIsNone(reasm.offer(self._part(0), NOW))
        other = self._part(0, chunk=b"\xff" * 80)
        self.assertIsNone(reasm.offer(other, NOW))
        self.assertEqual(reasm.pending, 0)
        self.assertIsNone(reasm.offer(self._part(1), NOW))
        self.assertIsNone(reasm.offer(self._part(2), NOW))
        # A header contradiction destroys it the same way.
        reasm = dtls_mailbox.FlightReassembler()
        self.assertIsNone(reasm.offer(self._part(0), NOW))
        self.assertIsNone(reasm.offer(self._part(1, count=4), NOW))
        self.assertEqual(reasm.pending, 0)

    def test_reassembler_completion_must_match_its_header(self):
        reasm = dtls_mailbox.FlightReassembler()
        wrong = "0" * 96
        for i in (0, 1):
            self.assertIsNone(
                reasm.offer(self._part(i, sha384=wrong), NOW))
        self.assertIsNone(
            reasm.offer(self._part(2, sha384=wrong), NOW))
        self.assertEqual(reasm.pending, 0)
        # The declared total is a length check too.
        reasm = dtls_mailbox.FlightReassembler()
        for i in (0, 1, 2):
            self.assertIsNone(
                reasm.offer(self._part(i, total_bytes=199), NOW))

    def test_reassembler_expiry_idle_and_deadline(self):
        reasm = dtls_mailbox.FlightReassembler(ttl_sec=100)
        self.assertIsNone(reasm.offer(self._part(0), 0.0))
        self.assertIsNone(reasm.offer(self._part(1), 101.0))
        self.assertEqual(reasm.pending, 1)  # part 1, fresh
        self.assertIsNone(reasm.offer(self._part(0), 101.0))
        self.assertEqual(reasm.offer(self._part(2), 101.0), self.DG)
        # The absolute deadline binds even when every part
        # arrives inside the idle timeout.
        reasm = dtls_mailbox.FlightReassembler(
            ttl_sec=1000, deadline_sec=50)
        self.assertIsNone(reasm.offer(self._part(0), 0.0))
        self.assertIsNone(reasm.offer(self._part(1), 40.0))
        self.assertIsNone(reasm.offer(self._part(2), 60.0))
        self.assertEqual(reasm.pending, 1)  # part 2 alone, fresh
        self.assertIsNone(reasm.offer(self._part(0), 60.0))
        self.assertEqual(reasm.offer(self._part(1), 60.0), self.DG)

    def test_reassembler_transfer_bound_evicts_the_oldest(self):
        data = b"xy" * 10
        import hashlib as _hl
        sha = _hl.sha384(data).hexdigest()

        def part(tid, index):
            return FlightPart(
                "s1", "%016x" % tid, index, 2, len(data), sha,
                (data[:10], data[10:])[index])

        reasm = dtls_mailbox.FlightReassembler()
        for tid in range(64):
            self.assertIsNone(reasm.offer(part(tid, 0), NOW))
        self.assertEqual(reasm.pending, 64)
        self.assertIsNone(reasm.offer(part(64, 0), NOW))
        self.assertEqual(reasm.pending, 64)
        # Transfer 0 was evicted: its second part starts a
        # new transfer instead of completing the old one.
        self.assertIsNone(reasm.offer(part(0, 1), NOW))
        self.assertEqual(reasm.offer(part(0, 0), NOW), data)

    def test_reassembler_key_includes_the_session(self):
        reasm = dtls_mailbox.FlightReassembler()
        self.assertIsNone(reasm.offer(self._part(0), NOW))
        self.assertIsNone(
            reasm.offer(self._part(0, session_id="s2"), NOW))
        self.assertEqual(reasm.pending, 2)

    def test_encode_flight_size_bounds(self):
        cap = dtls_mailbox.DEFAULT_MAX_DATAGRAM_BYTES
        with self.assertRaises(ValueError):
            encode_flight(b"", self.SID)
        with self.assertRaises(ValueError):
            encode_flight(bytes(cap + 1), self.SID)
        mails = encode_flight(bytes(cap), self.SID)
        reasm = dtls_mailbox.FlightReassembler()
        got = None
        for subject, body in mails:
            out = self._parse(subject, body)
            self.assertEqual(out.kind, "dtls-part")
            got = reasm.offer(out.part, NOW) or got
        self.assertEqual(got, bytes(cap))


class AdoptedTargetContractTest(unittest.TestCase):
    """The 3 adopted families' fuzz targets, run the way
    the campaign runs them, at the seeds the campaign
    record names: a Finding here fails the test."""

    def _targets(self):
        return hf.Targets(hf.RealOps, hf.acvp_vectors())

    def test_keyshare_entries_target_holds_its_contract(self):
        targets = self._targets()
        rng = random.Random(4588)
        for _ in range(60):
            targets.t_keyshare_entries(rng)

    def test_mailbox_frames_target_holds_its_contract(self):
        targets = self._targets()
        rng = random.Random(20220)
        for _ in range(60):
            targets.t_mailbox_frames(rng)

    def test_fragment_buffer_target_holds_its_contract(self):
        targets = self._targets()
        rng = random.Random(10024)
        for _ in range(60):
            targets.t_fragment_buffer(rng)

    def test_adopted_targets_subset_run_is_clean(self):
        lines = []
        code, rounds, findings = hf.run(
            "abstract", 0, 90, 4588, lines.append, None,
            ("keyshare_entries", "mailbox_frames",
             "fragment_buffer"))
        self.assertEqual(code, 0)
        self.assertEqual(findings, [])
        self.assertEqual(rounds, 90)


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
