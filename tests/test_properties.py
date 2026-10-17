"""Property-based tests (Hypothesis) for the protocol's pure core.

Each test asserts a property over generated inputs instead of one
example per behavior, so edge cases -- empty strings, boundary
lengths, tampered bytes, odd decorations -- get exercised
automatically. These are the scenarios the example-based suite kept
missing.
"""
import re
import unittest
from datetime import datetime, timedelta, timezone

from hypothesis import assume, given, strategies as st

from runner.runner import (
    JobRejected,
    _issued_at_ok,
    _safe_job_id,
    sign_payload,
    verify_body,
)

SUBJECT_RE = re.compile(r"\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)", re.I)

json_scalar = st.one_of(
    st.text(max_size=24),
    st.integers(),
    st.booleans(),
    st.none(),
)
json_value = st.recursive(
    json_scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(st.text(max_size=12), children, max_size=4),
    ),
    max_leaves=12,
)
payloads = st.dictionaries(st.text(min_size=1, max_size=16),
                           json_value, max_size=6)
secrets = st.text(min_size=1, max_size=64)
job_ids = st.from_regex(r"[A-Za-z0-9._-]{1,32}", fullmatch=True)
word = st.text(alphabet=st.characters(blacklist_categories=("Z", "C")),
               min_size=1, max_size=8)


class SignatureProperties(unittest.TestCase):
    @given(payload=payloads, secret=secrets)
    def test_sign_verify_roundtrip(self, payload, secret):
        self.assertEqual(verify_body(sign_payload(payload, secret), secret),
                         payload)

    @given(payload=payloads, secret=secrets, secret2=secrets)
    def test_wrong_secret_rejected(self, payload, secret, secret2):
        assume(secret != secret2)
        body = sign_payload(payload, secret)
        with self.assertRaises(ValueError):
            verify_body(body, secret2)

    @given(payload=payloads, secret=secrets,
           index=st.integers(min_value=0, max_value=128))
    def test_tampered_byte_rejected(self, payload, secret, index):
        body = sign_payload(payload, secret)
        marker = body.rfind(',"sig":"')
        assume(marker > 0)
        i = index % marker
        tampered = (body[:i] + ("X" if body[i] != "X" else "Y")
                    + body[i + 1:])
        with self.assertRaises(ValueError):
            verify_body(tampered, secret)

    @given(payload=payloads, secret=secrets,
           preamble=st.text(max_size=40))
    def test_preamble_and_trailer_ignored(self, payload, secret, preamble):
        assume(',"sig":"' not in preamble)
        body = sign_payload(payload, secret)
        self.assertEqual(
            verify_body(preamble + "\n" + body + "\n-- trailer --", secret),
            payload)

    def test_brace_inside_string_is_not_the_object_start(self):
        # Regression: _object_start once chose a `{` inside a string
        # literal as the object opener, so verify_body rejected a
        # legitimately signed body. Found by the roundtrip property.
        payload = {"{": '"', "script": "if ($x) { $y }"}
        body = sign_payload(payload, "s3cret")
        self.assertEqual(verify_body(body, "s3cret"), payload)


class SubjectProperties(unittest.TestCase):
    @given(deco=st.lists(word, max_size=3), job_id=job_ids,
           marker=st.sampled_from(["[HOMING-PIGEON]", "[homing-pigeon]",
                                   "[Homing-Pigeon]"]))
    def test_decorated_subject_extracts_job_id(self, deco, job_id, marker):
        subject = (marker + "".join(" " + w for w in deco)
                   + " job " + job_id)
        m = SUBJECT_RE.search(subject)
        self.assertIsNotNone(m, subject)
        self.assertEqual(m.group(1), job_id)

    @given(job_id=job_ids)
    def test_re_prefix_still_matches(self, job_id):
        m = SUBJECT_RE.search("Re: [HOMING-PIGEON] job " + job_id)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), job_id)


class JobIdProperties(unittest.TestCase):
    @given(job_id=st.from_regex(r"[A-Za-z0-9._-]{1,128}", fullmatch=True))
    def test_charset_accepted(self, job_id):
        assume(job_id not in (".", ".."))
        self.assertEqual(_safe_job_id(job_id), job_id)

    @given(s=st.text())
    def test_outside_charset_rejected(self, s):
        assume(not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", s)
               or s in (".", ".."))
        with self.assertRaises(JobRejected):
            _safe_job_id(s)


class FreshnessProperties(unittest.TestCase):
    # age = now - issued: the past gets a 3600s window, the future 300s.
    @given(delta_s=st.integers(min_value=-3590, max_value=290))
    def test_inside_window_accepted(self, delta_s):
        ts = (datetime.now(timezone.utc)
              + timedelta(seconds=delta_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ok, _ = _issued_at_ok(ts, {})
        self.assertTrue(ok, ts)

    @given(delta_s=st.one_of(st.integers(min_value=-7200, max_value=-3610),
                             st.integers(min_value=310, max_value=1200)))
    def test_outside_window_rejected(self, delta_s):
        ts = (datetime.now(timezone.utc)
              + timedelta(seconds=delta_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ok, _ = _issued_at_ok(ts, {})
        self.assertFalse(ok, ts)

    @given(delta_s=st.integers(min_value=-600, max_value=-61))
    def test_custom_window_honored(self, delta_s):
        ts = (datetime.now(timezone.utc)
              + timedelta(seconds=delta_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ok, _ = _issued_at_ok(ts, {"max_job_age_sec": 60})
        self.assertFalse(ok, ts)

    def test_malformed_rejected(self):
        for bad in ["not-a-date", "2026-10-16 12:00:00", "", None, 12345,
                    "2026-13-99T99:99:99Z"]:
            ok, _ = _issued_at_ok(bad, {})
            self.assertFalse(ok, bad)


if __name__ == "__main__":
    unittest.main()
