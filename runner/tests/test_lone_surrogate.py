# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""A JSON escape of a lone surrogate (\\ud800) is valid JSON syntax
and not UTF-8 text. A signed body carrying one passed both
verifiers, and the result that echoed its text (the job's kind on
every result, rejections included) could not be signed, so the
sender never heard back (Q85, found by blueMonday's queries
target). Both verifiers refuse it at the door now, the keyed one
too, and the runner's signer names it before its encode would."""

import hashlib
import hmac
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.cloud import send_job as SJ  # noqa: E402
from runner.guard import textutil as TU  # noqa: E402
from runner.wire import verify as V  # noqa: E402

SECRET = "5e0f3c2a9b8d7e6f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7081"


def _signed(text):
    """A body signed exactly as a sender signs: the HMAC over the
    object's text, the sig tail in place of its closing brace."""
    sig = hmac.new(SECRET.encode("utf-8"), text.encode("utf-8"),
                   hashlib.sha384).hexdigest()
    return text[:-1] + ',"sig":"' + sig + '"}'


ESCAPED = _signed('{"v":1,"type":"job","job_id":"bm-s-0001","kind":"\\ud800"}')
NESTED = _signed('{"v":1,"type":"job","job_id":"bm-s-0002","kind":"exec",'
                 '"detail":{"a":["x","\\udfff"]}}')
IN_KEY = _signed('{"v":1,"type":"job","job_id":"bm-s-0003","kind":"exec",'
                 '"\\ud83d":1}')
PAIRED = _signed('{"v":1,"type":"job","job_id":"bm-s-0004","kind":"exec",'
                 '"note":"\\ud83d\\udc26 caf\\u00e9"}')


class HasLoneSurrogateTest(unittest.TestCase):
    def test_walks_strings_keys_lists_and_nests(self):
        self.assertTrue(TU._lone_surrogate("\ud800"))
        self.assertTrue(TU._lone_surrogate({"a": {"b": ["\udfff"]}}))
        self.assertTrue(TU._lone_surrogate({"\ud800": 1}))
        self.assertTrue(TU._lone_surrogate(("x", ("\ud800",))))
        self.assertFalse(TU._lone_surrogate({"a": "café \U0001f426",
                                                "b": [1, None, True, 2.5]}))
        self.assertFalse(TU._lone_surrogate(7))
        self.assertFalse(TU._lone_surrogate(b"\xed\xa0\x80"))

    def test_a_cycle_ends_at_the_depth_cap(self):
        cycle = {"a": []}
        cycle["a"].append(cycle)
        self.assertFalse(TU._lone_surrogate(cycle))
        cycle["a"].append("\ud800")
        self.assertTrue(TU._lone_surrogate(cycle))


class VerifiersRefuseTest(unittest.TestCase):
    def test_both_verifiers_refuse_the_escape_wherever_it_sits(self):
        for body in (ESCAPED, NESTED, IN_KEY):
            for name, verify in (("verify_body", V.verify_body),
                                 ("send_job.verify_body", SJ.verify_body)):
                with self.assertRaisesRegex(ValueError, "unpaired UTF-16 surrogate",
                                            msg=f"{name}: {body[:60]}"):
                    verify(body, SECRET)
            with self.assertRaisesRegex(ValueError, "unpaired UTF-16 surrogate"):
                V.verify_body_keyed(body, {"": SECRET})

    def test_a_surrogate_pair_and_non_ascii_text_still_verify(self):
        for verify in (V.verify_body, SJ.verify_body):
            job = verify(PAIRED, SECRET)
            self.assertEqual(job["note"], "\U0001f426 café")
        payload, key_id = V.verify_body_keyed(PAIRED, {"": SECRET})
        self.assertEqual((payload["note"], key_id), ("\U0001f426 café", ""))

    def test_the_refusal_is_the_signed_body_not_the_preamble(self):
        # A lone surrogate in text around the object is not the
        # object's: the body still verifies (the preamble is ignored).
        good = V.sign_payload({"v": 1, "type": "job", "job_id": "bm-s-0005",
                               "kind": "exec"}, SECRET)
        job = V.verify_body("note: \ud800\n\n" + good, SECRET)
        self.assertEqual(job["job_id"], "bm-s-0005")


class SignersRefuseTest(unittest.TestCase):
    def test_the_runner_signer_names_it_and_the_other_raises_in_step(self):
        payload = {"v": 1, "type": "result", "job_id": "bm-s-0006",
                   "kind": "\ud800"}
        with self.assertRaisesRegex(ValueError, "unpaired UTF-16 surrogate"):
            V.sign_payload(payload, SECRET)
        with self.assertRaises(ValueError):      # UnicodeEncodeError is one
            SJ.sign_payload(payload, SECRET)

    def test_what_both_sign_both_verify(self):
        payload = {"v": 1, "type": "job", "job_id": "bm-s-0007",
                   "kind": "exec", "note": "\U0001f426 é"}
        for sign in (V.sign_payload, SJ.sign_payload):
            body = sign(payload, SECRET)
            self.assertEqual(V.verify_body(body, SECRET)["note"],
                             payload["note"])
            self.assertEqual(SJ.verify_body(body, SECRET)["note"],
                             payload["note"])


if __name__ == "__main__":
    unittest.main()
