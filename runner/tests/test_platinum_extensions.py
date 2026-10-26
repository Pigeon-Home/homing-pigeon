"""Project Platinum, cycle 3: the transport extensions' mains
and helpers, driven through their own seams.

Target from the cycle-2 refreshed table
(`docs/reports/v3.13.27/coverage-gaps.md`):

  logic  transport_extensions/email/__main__.py:_permanent (2)
         -- a delivery failure is permanent when every
         recipient was refused with a 5xx, or the response
         exception itself carries a 5xx; a single 4xx anywhere
         makes it retryable.

Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90
"""
import smtplib
import unittest

from hypothesis import given, settings, strategies as st

from runner.transport_extensions import channel as ch
from runner.transport_extensions.email import __main__ as email_ext


class PermanentProperties(unittest.TestCase):
    @settings(deadline=None)
    @given(codes=st.lists(
        st.integers(min_value=200, max_value=699),
        min_size=1, max_size=4))
    def test_recipients_refused_is_permanent_only_when_all_5xx(
            self, codes):
        exc = smtplib.SMTPRecipientsRefused(
            {f"user{i}@example.test": (code, b"refused")
             for i, code in enumerate(codes)})
        self.assertEqual(email_ext._permanent(exc),
                         all(500 <= c <= 599 for c in codes))

    @settings(deadline=None)
    @given(code=st.integers(min_value=200, max_value=699))
    def test_a_response_exception_is_its_code(self, code):
        exc = smtplib.SMTPResponseException(code, b"answer")
        self.assertEqual(email_ext._permanent(exc),
                         500 <= code <= 599)

    def test_the_channels_own_permanent_error_counts(self):
        self.assertTrue(
            email_ext._permanent(ch.PermanentDeliveryError("gone")))

    def test_anything_else_is_retryable(self):
        self.assertFalse(email_ext._permanent(OSError("down")))
        self.assertFalse(email_ext._permanent(
            smtplib.SMTPRecipientsRefused({})))


if __name__ == "__main__":
    unittest.main()
