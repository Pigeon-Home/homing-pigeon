"""ML-KEM-768 known-answer tests (FIPS 203).

The vectors are the NIST ACVP ML-KEM-768 vectors, recorded
in fixtures/mlkem768_acvp.json: the ACVP-Server repository's
gen-val/json-files ML-KEM-keyGen-FIPS203 and
ML-KEM-encapDecap-FIPS203 internalProjection.json files
(ML-KEM-768 test groups), retrieved 2026-11-03 from
https://github.com/usnistgov/ACVP-Server. Key generation is
pinned from the recorded (d, z) seeds, encapsulation from
the recorded message m against the recorded key, and
decapsulation against the recorded ciphertexts -- including
the ACVP decapsulation validation group's modified
ciphertext, whose expected secret is the implicit-rejection
value. The key-check groups pin the FIPS 203 section 7.2
and 7.3 checks both ways.

Proof of work for the hybrid key exchange build: this suite
is the correctness gate runner/wire/mlkem.py had to pass
before the engine was allowed to use it.
"""

import json
import os
import unittest

from runner.wire import mlkem

FIXTURE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures", "mlkem768_acvp.json")


def _vectors():
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _h(text):
    return bytes.fromhex(text)


class KeyGenKatTest(unittest.TestCase):
    def test_keygen_from_recorded_seeds(self):
        for vec in _vectors()["keygen"]:
            with self.subTest(tcId=vec["tcId"]):
                ek, dk = mlkem.keygen_internal(
                    _h(vec["d"]), _h(vec["z"]))
                self.assertEqual(ek, _h(vec["ek"]))
                self.assertEqual(dk, _h(vec["dk"]))


class EncapsKatTest(unittest.TestCase):
    def test_encaps_from_recorded_message(self):
        for vec in _vectors()["encap"]:
            with self.subTest(tcId=vec["tcId"]):
                secret, c = mlkem.encaps_internal(
                    _h(vec["ek"]), _h(vec["m"]))
                self.assertEqual(secret, _h(vec["k"]))
                self.assertEqual(c, _h(vec["c"]))

class DecapsKatTest(unittest.TestCase):
    def test_decaps_validation_group(self):
        for vec in _vectors()["decap"]:
            with self.subTest(tcId=vec["tcId"],
                              reason=vec["reason"]):
                secret = mlkem.decaps(_h(vec["dk"]), _h(vec["c"]))
                self.assertEqual(secret, _h(vec["k"]))


class KeyCheckKatTest(unittest.TestCase):
    def test_encapsulation_key_check_group(self):
        for vec in _vectors()["encap_key_check"]:
            with self.subTest(tcId=vec["tcId"],
                              reason=vec["reason"]):
                self.assertEqual(
                    mlkem.encapsulation_key_check(_h(vec["ek"])),
                    vec["testPassed"])

    def test_decapsulation_key_check_group(self):
        for vec in _vectors()["decap_key_check"]:
            with self.subTest(tcId=vec["tcId"],
                              reason=vec["reason"]):
                self.assertEqual(
                    mlkem.decapsulation_key_check(_h(vec["dk"])),
                    vec["testPassed"])


class RoundTripTest(unittest.TestCase):
    def test_keygen_encaps_decaps_round_trip(self):
        ek, dk = mlkem.keygen(rng=lambda n: b"\x07" * n)
        self.assertEqual(len(ek), mlkem.EK_BYTES)
        self.assertEqual(len(dk), mlkem.DK_BYTES)
        secret, c = mlkem.encaps(ek, rng=lambda n: b"\x09" * n)
        self.assertEqual(len(c), mlkem.CT_BYTES)
        self.assertEqual(mlkem.decaps(dk, c), secret)


class FailureShapeTest(unittest.TestCase):
    def setUp(self):
        self.ek, self.dk = mlkem.keygen(
            rng=lambda n: b"\x11" * n)
        self.secret, self.c = mlkem.encaps(
            self.ek, rng=lambda n: b"\x13" * n)

    def test_tampered_ciphertext_implicitly_rejects(self):
        # Flip one bit in the ciphertext's first half and one
        # in its second: both return a 32-octet secret that is
        # not the real one, and neither raises.
        for pos in (0, 500, mlkem.CT_BYTES - 1):
            bad = bytearray(self.c)
            bad[pos] ^= 0x01
            got = mlkem.decaps(self.dk, bytes(bad))
            self.assertEqual(len(got), 32)
            self.assertNotEqual(got, self.secret)

    def test_tampered_ciphertext_rejection_is_deterministic(self):
        bad = bytearray(self.c)
        bad[10] ^= 0xFF
        self.assertEqual(mlkem.decaps(self.dk, bytes(bad)),
                         mlkem.decaps(self.dk, bytes(bad)))

    def test_wrong_length_inputs_refused(self):
        with self.assertRaises(mlkem.MlkemError):
            mlkem.decaps(self.dk, self.c[:-1])
        with self.assertRaises(mlkem.MlkemError):
            mlkem.decaps(self.dk[:-1], self.c)
        with self.assertRaises(mlkem.MlkemError):
            mlkem.encaps_internal(self.ek[:-1], b"\x00" * 32)
        with self.assertRaises(mlkem.MlkemError):
            mlkem.encaps_internal(self.ek, b"\x00" * 31)
        with self.assertRaises(mlkem.MlkemError):
            mlkem.keygen_internal(b"\x00" * 31, b"\x00" * 32)
        with self.assertRaises(mlkem.MlkemError):
            mlkem.keygen_internal(b"\x00" * 32, b"\x00" * 33)

    def test_key_with_failed_check_refused(self):
        # An ek whose t vector holds a value outside Z_q
        # (every 12-bit field 0xFFF) fails the modulus check,
        # and encapsulation to it is refused, not attempted.
        bad_ek = b"\xff" * (384 * mlkem.K) + self.ek[384 * mlkem.K:]
        self.assertFalse(mlkem.encapsulation_key_check(bad_ek))
        with self.assertRaises(mlkem.MlkemError):
            mlkem.encaps_internal(bad_ek, b"\x00" * 32)
        # A dk whose stored hash does not match its ek is
        # refused at decapsulation.
        bad_dk = bytearray(self.dk)
        bad_dk[-33] ^= 0x01          # inside the stored hash
        self.assertFalse(
            mlkem.decapsulation_key_check(bytes(bad_dk)))
        with self.assertRaises(mlkem.MlkemError):
            mlkem.decaps(bytes(bad_dk), self.c)


if __name__ == "__main__":
    unittest.main()
