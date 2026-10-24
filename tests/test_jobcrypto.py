#!/usr/bin/env python3
"""Per-job encryption (runner/jobcrypto.py): RFC vectors first.

The construction is only worth anything if the primitives are the
standard ones, so this file pins AES-256, GCM, the AEAD
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
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

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


class AesBlockVectorTest(unittest.TestCase):
    def test_fips197_aes256_block(self):
        # FIPS 197 C.3: AES-256 encrypt
        key = bytes.fromhex(
            "000102030405060708090a0b0c0d0e0f"
            "101112131415161718191a1b1c1d1e1f")
        pt = bytes.fromhex("00112233445566778899aabbccddeeff")
        rk = jobcrypto._aes256_expand(key)
        ct = jobcrypto._aes_encrypt_block(pt, rk)
        self.assertEqual(ct.hex(), "8ea2b7ca516745bfeafc49904b496089")


class AeadVectorTest(unittest.TestCase):
    # NIST SP 800-38D style vector (AES-256-GCM, 12-byte nonce)
    KEY = bytes.fromhex(
        "000102030405060708090a0b0c0d0e0f"
        "101112131415161718191a1b1c1d1e1f")
    NONCE = bytes(12)
    PT = bytes.fromhex("000102030405060708090a0b0c0d0e0f")

    def test_aes256_gcm_known_vector(self):
        out = jobcrypto.aead_encrypt(self.KEY, self.NONCE, self.PT, b"")
        ct, tag = out[:-16], out[-16:]
        self.assertEqual(ct.hex(), "0ebdb7ddb12985ba00a1a33e14219f96")
        self.assertEqual(tag.hex(), "2a62b8712eb3268f46c04c1e4bd0ed40")
        self.assertEqual(
            jobcrypto.aead_decrypt(self.KEY, self.NONCE, out, b""),
            self.PT)

    def test_roundtrip_with_aad(self):
        aad = b"job-id\x00key-id\x00aes-256-gcm/hkdf-sha384"
        out = jobcrypto.aead_encrypt(self.KEY, self.NONCE, self.PT, aad)
        self.assertEqual(
            jobcrypto.aead_decrypt(self.KEY, self.NONCE, out, aad),
            self.PT)

    def test_tag_tamper_rejected(self):
        out = bytearray(jobcrypto.aead_encrypt(
            self.KEY, self.NONCE, self.PT, b"aad"))
        out[-1] ^= 0x01
        with self.assertRaises(JobCryptoError):
            jobcrypto.aead_decrypt(self.KEY, self.NONCE,
                                   bytes(out), b"aad")

    def test_ciphertext_tamper_rejected(self):
        out = bytearray(jobcrypto.aead_encrypt(
            self.KEY, self.NONCE, self.PT, b"aad"))
        out[0] ^= 0x01
        with self.assertRaises(JobCryptoError):
            jobcrypto.aead_decrypt(self.KEY, self.NONCE,
                                   bytes(out), b"aad")

    def test_wrong_aad_rejected(self):
        out = jobcrypto.aead_encrypt(self.KEY, self.NONCE,
                                     self.PT, b"aad")
        with self.assertRaises(JobCryptoError):
            jobcrypto.aead_decrypt(self.KEY, self.NONCE, out,
                                   b"different aad")

    def test_short_input_rejected(self):
        with self.assertRaises(JobCryptoError):
            jobcrypto.aead_decrypt(self.KEY, self.NONCE,
                                   b"\x00" * 8, b"aad")


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
                         "aes-256-gcm/hkdf-sha384")
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
