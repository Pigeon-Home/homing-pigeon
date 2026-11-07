#!/usr/bin/env python3
"""The code side of the Internet-Draft alignment that is not DTLS.

Each test names the draft rule it pins, so a later edit to either
side shows up here:

- Version 1 Section 16.2 step 4: the envelope's key_id and the
  body's key_id match when they name the same secret (Section
  10's sense, where one secret carries several names), not only
  when they are the same string. The runner compared strings;
  send_job's verifier did not; the two disagreed on a legal pair.
- Version 1 Section 11.1: issued_at is an RFC 3339 date-time.
  The parser took whatever its Python's fromisoformat took, which
  widens with every Python release, so a job could be fresh on
  one box and unparseable on the next.
- Version 2 Section 10: the question's platform context is the
  platform disclosure at the owner's tier, the same knob the ping
  card and the DTLS handshake use. It used to name the OS, the
  machine, the Python version and the Pi model with no tier at
  all, while version 1 promised that tier `none` names nothing.
"""
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner import runner  # noqa: E402
from runner.guard import security, textutil  # noqa: E402
from runner.wire import jobcrypto, protocol_v2  # noqa: E402

SECRET = "0e1f2a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7"
LAB = "7c1e9a4d2b8f6053e1a7c9d3b5f2e8a4061c3d5e7f9a2b4c6d8e0f1a3b5c7d9e"


def _job(job_id, key_id=None):
    job = {"v": 1, "type": "job", "job_id": job_id, "kind": "ping",
           "issued_at": datetime.now(timezone.utc).strftime(
               "%Y-%m-%dT%H:%M:%SZ")}
    if key_id is not None:
        job["key_id"] = key_id
    return job


class EnvelopeKeyIdMatchTest(unittest.TestCase):
    def setUp(self):
        self.secrets = runner.build_secrets(
            {"shared_secret": SECRET, "additional_secrets": {"lab": LAB}})
        self.lab_fp = security.key_fingerprint(LAB)
        self.default_fp = security.key_fingerprint(SECRET)

    def _admit(self, inner_secret, inner_key_id, outer_secret, outer_key_id):
        job_id = "j-" + (outer_key_id or "default").replace("k-", "")
        inner = runner.sign_payload(_job(job_id, inner_key_id), inner_secret)
        body = jobcrypto.encrypt_body(inner, outer_secret, job_id,
                                      outer_key_id or "",
                                      sign=runner.sign_payload)
        return runner._admit_object(body, self.secrets, job_id)

    def test_the_fingerprint_outside_and_the_name_inside_are_one_key(self):
        obj, key_id, secret, encrypted = self._admit(
            LAB, "lab", LAB, self.lab_fp)
        self.assertTrue(encrypted)
        self.assertEqual(secret, LAB)
        self.assertEqual(obj["key_id"], "lab")

    def test_the_name_outside_and_the_fingerprint_inside_are_one_key(self):
        obj, key_id, secret, _enc = self._admit(
            LAB, self.lab_fp, LAB, "lab")
        self.assertEqual(secret, LAB)
        self.assertEqual(obj["key_id"], self.lab_fp)

    def test_the_default_keys_fingerprint_and_no_name_are_one_key(self):
        obj, key_id, secret, _enc = self._admit(
            SECRET, None, SECRET, self.default_fp)
        self.assertEqual(secret, SECRET)
        self.assertNotIn("key_id", obj)

    def test_two_different_keys_do_not_match(self):
        with self.assertRaisesRegex(ValueError, "does not match its body"):
            self._admit(SECRET, None, LAB, "lab")

    def test_the_mail_path_reads_the_pair_the_same_way(self):
        job_id = "j-mail"
        inner = runner.sign_payload(_job(job_id, "lab"), LAB)
        body = jobcrypto.encrypt_body(inner, LAB, job_id, self.lab_fp,
                                      sign=runner.sign_payload)
        import email
        msg = email.message_from_string(
            "Subject: [HOMING-PIGEON] job " + job_id + "\n\n" + body)
        job, key_id, secret, was_encrypted = runner._verify_and_decrypt(
            msg, self.secrets, job_id)
        self.assertTrue(was_encrypted)
        self.assertEqual(secret, LAB)
        self.assertEqual(job["key_id"], "lab")


class Rfc3339TimestampTest(unittest.TestCase):
    def test_the_rfc_3339_forms_parse(self):
        for text in ("2026-10-13T12:00:00Z", "2026-10-13t12:00:00z",
                     "2026-10-13T12:00:00.5Z",
                     "2026-10-13T12:00:00.123456789+05:30",
                     "2026-10-13T12:00:00-08:00"):
            with self.subTest(text=text):
                when = textutil._fromiso(text)
                self.assertEqual(when.year, 2026)
                self.assertIsNotNone(when.tzinfo)

    def test_other_iso_8601_forms_are_refused_on_every_python(self):
        for text in ("20261013T120000Z", "2026-10-13 12:00:00Z",
                     "2026-10-13T12:00:00+0000", "2026-W42-2T12:00:00Z",
                     "2026-286T12:00:00Z", "2026-10-13T12:00Z",
                     "2026-10-13", "yesterday", ""):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "RFC 3339"):
                    textutil._fromiso(text)

    def test_a_date_time_with_no_offset_keeps_its_own_refusal(self):
        # The shape passes, so the runner can still say "missing
        # timezone" rather than "unparseable" for this case.
        when = textutil._fromiso("2026-10-13T12:00:00")
        self.assertIsNone(when.tzinfo)
        ok, why = runner._issued_at_ok("2026-10-13T12:00:00", {})
        self.assertFalse(ok)
        self.assertIn("missing timezone", why)
        ok, why = runner._issued_at_ok("20261013T120000Z", {})
        self.assertFalse(ok)
        self.assertIn("unparseable", why)

    def test_a_fresh_rfc_3339_stamp_is_fresh(self):
        stamp = (datetime.now(timezone.utc) - timedelta(seconds=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        ok, why = runner._issued_at_ok(stamp, {})
        self.assertTrue(ok, why)


class QuestionContextTierTest(unittest.TestCase):
    def _question(self, cfg):
        return protocol_v2.question_for(
            cfg, {"job_id": "j-tier", "kind": "exec", "script": "echo hi"})

    def test_the_default_tier_is_family(self):
        q = self._question({"protocol_v2": True})
        ctx = q["context"]
        self.assertEqual(len(ctx), 1)
        self.assertEqual(ctx[0]["kind"], "platform")
        card = json.loads(ctx[0]["text"])
        self.assertEqual(set(card),
                         {"os_family", "default_interpreter",
                          "protocol_versions"})
        self.assertEqual(card["protocol_versions"], [1, 2])

    def test_tier_none_discloses_nothing(self):
        q = self._question({"protocol_v2": True, "pong_platform": "none"})
        self.assertNotIn("context", q)
        self.assertEqual(protocol_v2.platform_facts(
            {"pong_platform": "none"}), "")

    def test_the_standard_tier_adds_the_release_and_the_runtime(self):
        q = self._question({"protocol_v2": True,
                            "pong_platform": "standard"})
        card = json.loads(q["context"][0]["text"])
        self.assertIn("os_release", card)
        self.assertIn("python_version", card)
        self.assertNotIn("path_tools", card)

    def test_an_unreadable_tier_discloses_nothing(self):
        self.assertEqual(protocol_v2.platform_facts(
            {"pong_platform": "everything"}), "")

    def test_the_segment_is_data_and_within_the_cap(self):
        q = self._question({"protocol_v2": True, "pong_platform": "full"})
        text = q["context"][0]["text"]
        self.assertLessEqual(len(text), 500)
        self.assertNotIn("secret", text.lower())
        protocol_v2.validate(q)


if __name__ == "__main__":
    unittest.main()
