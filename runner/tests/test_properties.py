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
    BUILTIN_REDACT_PATTERNS,
    JobRejected,
    _issued_at_ok,
    _normalize,
    _safe_job_id,
    redact_text,
    secret_fragment_hit,
    secret_scan,
    sign_payload,
    verify_body,
    verify_body_keyed,
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


class PreambleBraceInStringTest(unittest.TestCase):
    # Q32: a lopsided quote in the preamble inverts _object_start's
    # forward string tracking, and its fallback tries an in-string
    # `{` before the real opener, so a valid signed job whose body
    # carries a `{` inside a string is rejected as a signature
    # mismatch -- against draft Section 7 ("The receiver ignores
    # preamble and trailer"; the opener is "not a `{` inside a
    # string"). The failing shapes sat under expectedFailure until
    # the fix landed (_object_start takes the newest `{` whose text
    # up to the marker parses as a JSON object; a brace inside a
    # string never does); the fix removed the decorators.
    SECRET = "preamble-probe-secret"

    def _roundtrip(self, payload, preamble):
        body = sign_payload(payload, self.SECRET)
        text = preamble + "\n" + body + "\n-- trailer --"
        self.assertEqual(verify_body(text, self.SECRET), payload)

    # Q32 failing shapes
    def test_hypothesis_counterexample_one_quote(self):
        self._roundtrip({'{': None, '"': []}, '"')

    # Q32 failing shapes
    def test_hypothesis_counterexample_three_quotes(self):
        self._roundtrip({'{': None, '"': []}, '"""')

    # Q32 failing shapes
    def test_hypothesis_counterexample_text_quote(self):
        self._roundtrip({'{': None, '"': []}, 'say "hi')

    # Q32 failing shapes
    def test_regression_payload_behind_one_quote(self):
        self._roundtrip({"{": '"', "script": "if ($x) { $y }"}, '"')

    def test_counterexample_without_preamble(self):
        body = sign_payload({'{': None, '"': []}, self.SECRET)
        self.assertEqual(
            verify_body(body + "\n-- trailer --", self.SECRET),
            {'{': None, '"': []})

    def test_simple_payload_behind_one_quote(self):
        self._roundtrip({"a": 1}, '"')

    def test_simple_payload_behind_balanced_quotes(self):
        self._roundtrip({"a": 1}, '""')

    def test_brace_key_payload_behind_one_quote(self):
        self._roundtrip({'{': 1}, '"')

    def test_brace_in_value_behind_one_quote(self):
        self._roundtrip({"script": "echo { hi }"}, '"')


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

    @given(payload=payloads, secret=secrets)
    def test_sign_deterministic(self, payload, secret):
        self.assertEqual(sign_payload(payload, secret),
                         sign_payload(payload, secret))


class KeyedVerificationProperties(unittest.TestCase):
    @given(payload=payloads, kid=st.text(min_size=1, max_size=16),
           secret=secrets, default_secret=secrets)
    def test_keyed_roundtrip_selects_key(self, payload, kid, secret,
                                         default_secret):
        assume(kid != "")
        p = dict(payload)
        p["key_id"] = kid
        body = sign_payload(p, secret)
        out, out_kid = verify_body_keyed(
            body, {"": default_secret, kid: secret})
        self.assertEqual(out_kid, kid)
        self.assertEqual({k: v for k, v in out.items() if k != "sig"}, p)

    @given(payload=payloads, secret=secrets)
    def test_default_key_when_absent(self, payload, secret):
        p = dict(payload)
        p.pop("key_id", None)
        body = sign_payload(p, secret)
        out, out_kid = verify_body_keyed(body, {"": secret, "other": "x"})
        self.assertEqual(out_kid, "")

    @given(payload=payloads, secret=secrets)
    def test_unknown_key_id_fails_closed(self, payload, secret):
        p = dict(payload)
        p["key_id"] = "nope"
        body = sign_payload(p, secret)
        with self.assertRaisesRegex(ValueError, "unknown key_id"):
            verify_body_keyed(body, {"": secret})

    @given(payload=payloads, kid=st.text(min_size=1, max_size=16),
           secret=secrets, wrong=secrets)
    def test_wrong_keyed_secret_rejected(self, payload, kid, secret, wrong):
        assume(kid != "" and secret != wrong)
        p = dict(payload)
        p["key_id"] = kid
        body = sign_payload(p, secret)
        with self.assertRaises(ValueError):
            verify_body_keyed(body, {"": "d", kid: wrong})


class RedactionProperties(unittest.TestCase):
    @given(secret=st.text(
        alphabet=st.characters(blacklist_categories=("Z", "C")),
        min_size=8, max_size=32))
    def test_redact_removes_literal_secret(self, secret):
        out, families = redact_text("leaked: " + secret,
                                    {"tok": re.escape(secret)})
        self.assertNotIn(secret, out)
        self.assertIn("[REDACTED:tok]", out)
        self.assertIn("tok", families)

    @given(text=st.one_of(st.text(max_size=100), st.integers(), st.none(),
                           st.lists(st.text(max_size=20), max_size=3)),
           patterns=st.one_of(
               st.none(),
               st.dictionaries(st.text(max_size=10),
                               st.one_of(st.text(max_size=30),
                                         st.integers(), st.none()),
                               max_size=3)))
    def test_redact_never_crashes(self, text, patterns):
        out, families = redact_text(text, patterns)
        self.assertIsInstance(out, str)
        self.assertIsInstance(families, list)

    @given(text=st.text(max_size=120))
    def test_redact_clean_text_untouched(self, text):
        assume(not secret_scan(text, BUILTIN_REDACT_PATTERNS))
        out, families = redact_text(text, BUILTIN_REDACT_PATTERNS)
        self.assertEqual(out, text)
        self.assertEqual(families, [])


class FragmentProperties(unittest.TestCase):
    @given(secret=st.from_regex(r"AKIA[0-9A-Z]{16}", fullmatch=True),
           at=st.integers(min_value=0, max_value=8))
    def test_fragment_hit_on_slice(self, secret, at):
        sl = secret[at:at + 8]
        self.assertTrue(secret_fragment_hit(
            "here is " + sl + " ok", "key=" + secret,
            BUILTIN_REDACT_PATTERNS))

    @given(secret=st.from_regex(r"AKIA[0-9A-Z]{16}", fullmatch=True))
    def test_fragment_hit_case_insensitive(self, secret):
        self.assertTrue(secret_fragment_hit(
            "key " + secret[:8].lower(), "key=" + secret,
            BUILTIN_REDACT_PATTERNS))

    @given(reply=st.text(max_size=60), source=st.text(max_size=60))
    def test_fragment_no_match_no_hit(self, reply, source):
        assume(not secret_scan(source, BUILTIN_REDACT_PATTERNS))
        self.assertFalse(secret_fragment_hit(reply, source,
                                             BUILTIN_REDACT_PATTERNS))


class NormalizeProperties(unittest.TestCase):
    @given(s=st.text(max_size=100))
    def test_normalize_idempotent(self, s):
        self.assertEqual(_normalize(_normalize(s)), _normalize(s))

    @given(s=st.text(max_size=100))
    def test_normalize_no_cr(self, s):
        self.assertNotIn("\r", _normalize(s))


if __name__ == "__main__":
    unittest.main()
