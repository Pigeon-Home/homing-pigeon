#!/usr/bin/env python3
"""Per-job encryption (runner/jobcrypto.py): RFC vectors first.

The construction is only worth anything if the primitives are the
standard ones, so this file pins ChaCha20, Poly1305, the AEAD
composition, and HKDF against published test data before it tests
a single envelope. Envelope tests then pin the wire discipline:
sign the envelope as transmitted, verify before decrypting, and
let no malformed shape reach a plaintext.
"""

import hashlib
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "cloud"))

from runner import jobcrypto  # noqa: E402
from runner.jobcrypto import JobCryptoError  # noqa: E402
from runner.runner import sign_payload, verify_body_keyed  # noqa: E402

SECRET = ("kX9f" "2vQz" "7Lp4" "Wd8s" "Rb3N" "j6Hc" "5Ty1" "Mx0G" "aVqP")
OTHER_SECRET = ("Zp8w" "Qx3K" "v7Nm" "2Bs9" "Df4G" "h6Jk" "1Lc5" "Rt0V" "yUnB")
SUNSCREEN = (b"Ladies and Gentlemen of the class of '99: If I could "
             b"offer you only one tip for the future, sunscreen "
             b"would be it.")


def _sign(payload, secret):
    return sign_payload(payload, secret)


class ChaChaBlockVectorTest(unittest.TestCase):
    def test_rfc8439_section_2_3_2_block(self):
        # The block function test vector: key 00..1f, nonce
        # 000000090000004a00000000, counter 1.
        block = jobcrypto._chacha20_block(
            bytes(range(32)), 1,
            bytes.fromhex("000000090000004a00000000"))
        self.assertEqual(
            block.hex(),
            "10f1e7e4d13b5915500fdd1fa32071c4"
            "c7d1f4c733c068030422aa9ac3d46c4e"
            "d2826446079faa0914c2d705d98b02a2"
            "b5129cd1de164eb9cbd083e8a2503c4e")

    def test_rfc8439_appendix_a1_zero_block(self):
        block = jobcrypto._chacha20_block(bytes(32), 0, bytes(12))
        self.assertEqual(
            block.hex(),
            "76b8e0ada0f13d90405d6ae55386bd28"
            "bdd219b8a08ded1aa836efcc8b770dc7"
            "da41597c5157488d7724e03fb8d84a37"
            "6a43b8f41518a11cc387b669b2ee6586")


class Poly1305VectorTest(unittest.TestCase):
    def test_rfc8439_section_2_5_2(self):
        key = bytes.fromhex(
            "85d6be7857556d337f4452fe42d506a8"
            "0103808afb0db2fd4abff6af4149f51b")
        tag = jobcrypto._poly1305_mac(
            b"Cryptographic Forum Research Group", key)
        self.assertEqual(tag.hex(), "a8061dc1305136c6c22b8baf0c0127a9")


class AeadVectorTest(unittest.TestCase):
    KEY = bytes.fromhex(
        "808182838485868788898a8b8c8d8e8f"
        "909192939495969798999a9b9c9d9e9f")
    NONCE = bytes.fromhex("070000004041424344454647")
    AAD = bytes.fromhex("50515253c0c1c2c3c4c5c6c7")

    def test_rfc8439_section_2_8_2(self):
        out = jobcrypto.aead_encrypt(self.KEY, self.NONCE,
                                     SUNSCREEN, self.AAD)
        ct, tag = out[:-16], out[-16:]
        self.assertEqual(len(ct), len(SUNSCREEN))
        self.assertTrue(ct.hex().startswith(
            "d31a8d34648e60db7b86afbc53ef7ec2"
            "a4aded51296e08fea9e2b5a736ee62d6"))
        # The Poly1305 tag covers the AAD and every ciphertext
        # octet, so the published tag pins the whole ciphertext,
        # not just the prefix above.
        self.assertEqual(tag.hex(), "1ae10b594f09e26a7e902ecbd0600691")
        self.assertEqual(
            jobcrypto.aead_decrypt(self.KEY, self.NONCE, out,
                                   self.AAD),
            SUNSCREEN)

    def test_tag_tamper_rejected(self):
        out = bytearray(jobcrypto.aead_encrypt(
            self.KEY, self.NONCE, SUNSCREEN, self.AAD))
        out[-1] ^= 0x01
        with self.assertRaises(JobCryptoError):
            jobcrypto.aead_decrypt(self.KEY, self.NONCE,
                                   bytes(out), self.AAD)

    def test_ciphertext_tamper_rejected(self):
        out = bytearray(jobcrypto.aead_encrypt(
            self.KEY, self.NONCE, SUNSCREEN, self.AAD))
        out[0] ^= 0x01
        with self.assertRaises(JobCryptoError):
            jobcrypto.aead_decrypt(self.KEY, self.NONCE,
                                   bytes(out), self.AAD)

    def test_wrong_aad_rejected(self):
        out = jobcrypto.aead_encrypt(self.KEY, self.NONCE,
                                     SUNSCREEN, self.AAD)
        with self.assertRaises(JobCryptoError):
            jobcrypto.aead_decrypt(self.KEY, self.NONCE, out,
                                   b"different aad")

    def test_short_input_rejected(self):
        with self.assertRaises(JobCryptoError):
            jobcrypto.aead_decrypt(self.KEY, self.NONCE,
                                   b"\x00" * 8, self.AAD)


class HkdfVectorTest(unittest.TestCase):
    def test_rfc5869_test_case_1_sha256(self):
        # RFC 5869 publishes SHA-256/SHA-1 cases; this one pins
        # the extract-and-expand structure both hashes share.
        okm = jobcrypto.hkdf(b"\x0b" * 22, bytes(range(13)),
                             bytes(range(0xF0, 0xFA)), 42,
                             hashfn=hashlib.sha256)
        self.assertEqual(
            okm.hex(),
            "3cb25f25faacd57a90434f64d0362f2a"
            "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
            "34007208d5b887185865")

    def test_hkdf_sha384_pin(self):
        # RFC 5869 has no SHA-384 case. This value was generated
        # by this implementation AFTER the SHA-256 case above
        # validated the shared code path; it pins the production
        # hash choice against drift, and is labeled a pin, not a
        # published vector.
        okm = jobcrypto.hkdf(b"\x0b" * 22, bytes(range(13)),
                             bytes(range(0xF0, 0xFA)), 42)
        self.assertEqual(
            okm.hex(),
            "9b5097a86038b805309076a44b3a9f38"
            "063e25b516dcbf369f394cfab43685f7"
            "48b6457763e4f0204fc5")


SIGNED_JOB = None  # built in setUpModule from a real payload


def _signed_job(job_id="job-1", secret=SECRET, **kw):
    payload = {"v": 1, "type": "job", "job_id": job_id,
               "issued_at": "2026-10-19T00:00:00Z", "kind": "ping"}
    payload.update(kw)
    return sign_payload(payload, secret)


class EnvelopeTest(unittest.TestCase):
    def test_roundtrip_through_real_verification(self):
        body = _signed_job()
        wire = jobcrypto.encrypt_body(body, SECRET, "job-1", "",
                                      _sign)
        payload, key_id = verify_body_keyed(wire, {"": SECRET})
        self.assertEqual(key_id, "")
        self.assertTrue(jobcrypto.is_envelope(payload))
        self.assertEqual(set(payload["hp_enc"]),
                         {"alg", "nonce", "ct"})
        back = jobcrypto.decrypt_body(payload, SECRET, "job-1", "")
        self.assertEqual(back, body)
        job, key_id2 = verify_body_keyed(back, {"": SECRET})
        self.assertEqual(job["job_id"], "job-1")
        self.assertEqual(key_id2, "")

    def test_envelope_shape_is_exact(self):
        wire = jobcrypto.encrypt_body(_signed_job(), SECRET,
                                      "job-1", "", _sign)
        env = json.loads(wire[:wire.rfind(',"sig":"')] + "}")
        self.assertEqual(env["hp_enc"]["alg"],
                         "chacha20-poly1305/hkdf-sha384")
        import base64
        self.assertEqual(len(base64.b64decode(env["hp_enc"]["nonce"])),
                         12)

    def test_nonce_uniqueness(self):
        body = _signed_job()
        nonces = set()
        for _ in range(64):
            wire = jobcrypto.encrypt_body(body, SECRET, "job-1", "",
                                          _sign)
            env = json.loads(wire[:wire.rfind(',"sig":"')] + "}")
            nonces.add(env["hp_enc"]["nonce"])
        self.assertEqual(len(nonces), 64)

    def test_wrong_secret_rejected(self):
        wire = jobcrypto.encrypt_body(_signed_job(), SECRET,
                                      "job-1", "", _sign)
        payload, _ = verify_body_keyed(wire, {"": SECRET})
        with self.assertRaises(JobCryptoError):
            jobcrypto.decrypt_body(payload, OTHER_SECRET,
                                   "job-1", "")

    def test_wrong_job_id_rejected(self):
        # The AAD binds the envelope to its job_id: replaying the
        # same envelope under another id must not decrypt.
        wire = jobcrypto.encrypt_body(_signed_job(), SECRET,
                                      "job-1", "", _sign)
        payload, _ = verify_body_keyed(wire, {"": SECRET})
        with self.assertRaises(JobCryptoError):
            jobcrypto.decrypt_body(payload, SECRET, "job-2", "")

    def test_key_id_selects_its_secret(self):
        secrets = {"": SECRET, "alt": OTHER_SECRET}
        body = _signed_job(secret=OTHER_SECRET, key_id="alt")
        wire = jobcrypto.encrypt_body(body, OTHER_SECRET, "job-1",
                                      "alt", _sign)
        payload, key_id = verify_body_keyed(wire, secrets)
        self.assertEqual(key_id, "alt")
        back = jobcrypto.decrypt_body(payload, OTHER_SECRET,
                                      "job-1", "alt")
        self.assertEqual(back, body)
        with self.assertRaises(JobCryptoError):
            jobcrypto.decrypt_body(payload, SECRET, "job-1", "alt")

    MALFORMED = [
        ("missing hp_enc", {}),
        ("hp_enc not an object", {"hp_enc": "x"}),
        ("extra member", {"hp_enc": {"alg": jobcrypto.ALG,
                                     "nonce": "AAAA", "ct": "AAAA"},
                          "surprise": 1}),
        ("unknown alg", {"hp_enc": {"alg": "aes-gcm",
                                    "nonce": "AAAAAAAAAAAAAAA=",
                                    "ct": "AAAAAAAAAAAAAAAAAAAAAA=="}}),
        ("nonce missing", {"hp_enc": {"alg": jobcrypto.ALG,
                                      "ct": "AAAAAAAAAAAAAAAAAAAAAA=="}}),
        ("nonce bad base64", {"hp_enc": {"alg": jobcrypto.ALG,
                                         "nonce": "!!!",
                                         "ct": "AAAAAAAAAAAAAAAAAAAAAA=="}}),
        ("nonce wrong length", {"hp_enc": {"alg": jobcrypto.ALG,
                                           "nonce": "AAAAAAAAAAA=",
                                           "ct": "AAAAAAAAAAAAAAAAAAAAAA=="}}),
        ("ct missing", {"hp_enc": {"alg": jobcrypto.ALG,
                                   "nonce": "AAAAAAAAAAAAAAA="}}),
        ("ct bad base64", {"hp_enc": {"alg": jobcrypto.ALG,
                                      "nonce": "AAAAAAAAAAAAAAA=",
                                      "ct": "@@@"}}),
        ("ct shorter than tag", {"hp_enc": {"alg": jobcrypto.ALG,
                                            "nonce": "AAAAAAAAAAAAAAA=",
                                            "ct": "AAAAAAAAAAA="}}),
    ]

    def test_malformed_envelopes_rejected_cleanly(self):
        for name, payload in self.MALFORMED:
            with self.subTest(shape=name):
                with self.assertRaises(JobCryptoError):
                    jobcrypto.decrypt_body(payload, SECRET,
                                           "job-1", "")

    def test_tampered_ciphertext_fails_at_signature_step(self):
        # Flip one ciphertext character in the transmitted body:
        # the outer HMAC no longer matches, so verification (the
        # step BEFORE decryption) is what rejects it.
        wire = jobcrypto.encrypt_body(_signed_job(), SECRET,
                                      "job-1", "", _sign)
        env = json.loads(wire[:wire.rfind(',"sig":"')] + "}")
        ct = env["hp_enc"]["ct"]
        env["hp_enc"]["ct"] = ("A" if ct[0] != "A" else "B") + ct[1:]
        tampered = json.dumps(env, separators=(",", ":")) \
            + wire[wire.rfind(',"sig":"'):]
        with self.assertRaises(ValueError) as cm:
            verify_body_keyed(tampered, {"": SECRET})
        self.assertNotIsInstance(cm.exception, JobCryptoError)


if __name__ == "__main__":
    unittest.main()
