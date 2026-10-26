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
import os
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


class RefuseResultTest(unittest.TestCase):
    """Cycle 3 target, except class:
    `transport_extensions/channel.py:refuse_result` (2) -- a
    result that cannot be set aside (its failed/ folder
    cannot be created) is a logged warning, never an
    exception: the channel's contract is "never raises".
    """

    def test_an_unwritable_channel_is_a_warning_not_a_raise(self):
        import tempfile
        td = tempfile.mkdtemp(prefix="hp-plat-chan-")
        try:
            failed = os.path.join(td, "outbox", "failed")
            os.makedirs(os.path.dirname(failed))
            with open(failed, "w", encoding="utf-8") as fh:
                fh.write("a file where failed/ belongs")
            self.assertIsNone(
                ch.refuse_result(td, "x.result.txt", "refused"))
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)


class ServiceWatchMainTest(unittest.TestCase):
    """Cycle 3 target, logic class:
    `extensions/service-watch/service_watch.py:main` (2) -- a
    pass whose local delivery lands only some of its alerts
    returns 2 and leaves the state file unwritten, so the next
    pass reports the changes again. The delivery seam is the
    module's own `_deliver_local`, scripted short; the alert
    itself is the extension's real decide() over a learned
    state and a process table with sshd gone.
    """

    def _load(self):
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(
            here, "..", "extensions", "service-watch",
            "service_watch.py")
        spec = importlib.util.spec_from_file_location(
            "service_watch_platinum", os.path.normpath(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_a_short_delivery_returns_2_and_keeps_the_state(self):
        import json
        import tempfile
        from unittest import mock
        sw = self._load()
        td = tempfile.mkdtemp(prefix="hp-plat-svcwatch-")
        try:
            manifest = os.path.join(td, "extension.json")
            here = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(
                    here, "..", "extensions", "service-watch",
                    "extension.json"), encoding="utf-8") as fh:
                shipped = json.load(fh)
            shipped["tunables"]["services"] = [
                {"name": "sshd", "match": "exact"}]
            with open(manifest, "w", encoding="utf-8") as fh:
                json.dump(shipped, fh)
            state = os.path.join(td, "state.json")
            up = os.path.join(td, "up.json")
            down = os.path.join(td, "down.json")
            proc = {"name": "sshd", "pid": 100,
                    "cmdline": "/usr/sbin/sshd"}
            with open(up, "w", encoding="utf-8") as fh:
                json.dump({"now": 1700000000.0,
                           "processes": [proc]}, fh)
            with open(down, "w", encoding="utf-8") as fh:
                json.dump({"now": 1700000030.0, "processes": []}, fh)
            rc = sw.main(["--manifest", manifest, "--state", state,
                          "--readings", up])
            self.assertEqual(rc, 0)
            with open(state, encoding="utf-8") as fh:
                learned = fh.read()
            with mock.patch.object(sw, "_deliver_local",
                                   return_value=0):
                rc = sw.main(["--manifest", manifest,
                              "--state", state, "--readings", down,
                              "--local-dir", td])
            self.assertEqual(rc, 2)
            with open(state, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), learned)
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)


class DecodeDatagramTest(unittest.TestCase):
    """Cycle 3 target, except class:
    `extensions/softflowd-feed/softflowd_feed.py:
    decode_datagram` (2) -- a datagram whose header
    announces NetFlow v5 or IPFIX but whose body is too
    damaged to parse answers with no flows and the templates
    it was handed: the pure function's "never raises".
    """

    def _load(self):
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(
            here, "..", "extensions", "softflowd-feed",
            "softflowd_feed.py")
        spec = importlib.util.spec_from_file_location(
            "softflowd_platinum", os.path.normpath(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @settings(deadline=None)
    @given(version=st.sampled_from([5, 9, 10]),
           tail=st.binary(min_size=0, max_size=18))
    def test_truncated_datagrams_answer_empty(self, version, tail):
        sf = self._load()
        data = version.to_bytes(2, "big") + tail
        flows, templates = sf.decode_datagram(data, {}, now=1.0)
        self.assertEqual(flows, [])
        self.assertEqual(templates, {})


if __name__ == "__main__":
    unittest.main()
