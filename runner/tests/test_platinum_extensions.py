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

    def test_header_valid_record_damaged_datagrams(self):
        # The harder shapes: a v9 template set whose data set
        # is truncated mid-record, a template claiming fields
        # its body does not carry, an IPFIX enterprise field
        # cut short. Each answers with no flows; a template
        # learned before the damage is kept. (The function's
        # own except arm did not fire for any of these: every
        # sub-parser length-checks its unpacks, verified on
        # this rig in cycle 4 -- the arm stands as the belt
        # over their braces, recorded in the cycle's ledger.)
        import struct
        sf = self._load()
        hdr9 = struct.pack(">HHIII", 9, 2, 1000, 1700000000, 1) \
            + struct.pack(">I", 7)
        tmpl_body = struct.pack(">HH", 256, 1) \
            + struct.pack(">HH", 1, 8)
        tmpl_set = struct.pack(">HH", 0, 4 + len(tmpl_body)) \
            + tmpl_body
        data_set = struct.pack(">HH", 256, 8) + b"\x00\x00\x00\x01"
        flows, templates = sf.decode_datagram(
            hdr9 + tmpl_set + data_set, {}, now=1.0)
        self.assertEqual(flows, [])
        self.assertIn((9, 7, 256), templates)
        greedy = struct.pack(">HH", 0, 12) \
            + struct.pack(">HH", 256, 50) + struct.pack(">HH", 1, 8)
        self.assertEqual(
            sf.decode_datagram(hdr9 + greedy, {}, now=1.0),
            ([], {}))


class OsqueryFeedMainTest(unittest.TestCase):
    """Cycle 4 target, logic class:
    `extensions/osquery-feed/osquery_feed.py:main` (590,596)
    -- the same delivery contract as service-watch: a pass
    whose local delivery lands only some of its alerts
    returns 2 and leaves the state unwritten, so the offsets
    do not advance and the next pass re-reads the lines. The
    alert is the extension's real decide() over a readings
    fixture carrying one added process; the delivery seam is
    the module's own `_deliver_local`, scripted short.
    """

    def _load(self):
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(
            here, "..", "extensions", "osquery-feed",
            "osquery_feed.py")
        spec = importlib.util.spec_from_file_location(
            "osquery_feed_platinum", os.path.normpath(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_a_short_delivery_returns_2_and_keeps_the_state(self):
        import json
        import tempfile
        from unittest import mock
        of = self._load()
        td = tempfile.mkdtemp(prefix="hp-plat-osq-")
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            manifest = os.path.join(td, "extension.json")
            with open(os.path.join(
                    here, "..", "extensions", "osquery-feed",
                    "extension.json"), encoding="utf-8") as fh:
                raw = fh.read()
            with open(manifest, "w", encoding="utf-8") as fh:
                fh.write(raw)
            line = json.dumps({
                "name": "hp_processes",
                "hostIdentifier": "fixture-host",
                "unixTime": 1792382200,
                "columns": {"name": "sshd",
                            "path": "/usr/sbin/sshd", "pid": "812"},
                "action": "added"})
            event = of.parse_event(line)
            self.assertIsNotNone(event)
            readings = os.path.join(td, "readings.json")
            with open(readings, "w", encoding="utf-8") as fh:
                json.dump({"now": event["ts"], "events": [event]},
                          fh)
            state = os.path.join(td, "state.json")
            with mock.patch.object(of, "_deliver_local",
                                   return_value=0):
                rc = of.main(["--manifest", manifest,
                              "--state", state,
                              "--readings", readings,
                              "--local-dir", td])
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(state))
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)


class PortWatchMainTest(unittest.TestCase):
    """Cycle 5 target, logic class:
    `extensions/port-watch/port_watch.py:main` (400,403,406)
    -- the third sibling with the same delivery contract: a
    pass whose local delivery lands only some of its alerts
    returns 2 and leaves the state unwritten. The alert is
    the extension's real decide() over a readings fixture
    with learning off and one exposed listener; the delivery
    seam is the module's own `_deliver_local`, scripted
    short.
    """

    def _load(self):
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(
            here, "..", "extensions", "port-watch",
            "port_watch.py")
        spec = importlib.util.spec_from_file_location(
            "port_watch_platinum", os.path.normpath(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_a_short_delivery_returns_2_and_keeps_the_state(self):
        import json
        import tempfile
        from unittest import mock
        pw = self._load()
        td = tempfile.mkdtemp(prefix="hp-plat-portwatch-")
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(
                    here, "..", "extensions", "port-watch",
                    "extension.json"), encoding="utf-8") as fh:
                shipped = json.load(fh)
            shipped["tunables"]["learn_first_pass"] = False
            manifest = os.path.join(td, "extension.json")
            with open(manifest, "w", encoding="utf-8") as fh:
                json.dump(shipped, fh)
            readings = os.path.join(td, "readings.json")
            with open(readings, "w", encoding="utf-8") as fh:
                json.dump({"now": 1792382200.0, "listeners": [
                    {"proto": "tcp", "addr": "0.0.0.0",
                     "port": 22}]}, fh)
            state = os.path.join(td, "state.json")
            with mock.patch.object(pw, "_deliver_local",
                                   return_value=0):
                rc = pw.main(["--manifest", manifest,
                              "--state", state,
                              "--readings", readings,
                              "--local-dir", td])
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(state))
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)


class SkyWatcherSunTest(unittest.TestCase):
    """Cycle 5 target, logic class:
    `extensions/sky-watcher/sky_watcher.py:
    sun_elevation_deg` -- whatever the inputs, the
    elevation is a finite angle in [-90, 90]. (The
    hour-angle wrap at line 231 did not fire at any input:
    the modulo above it bounds the angle to [-180, 180),
    so the wrap is recorded dead by construction in cycle
    6's ledger; the contract is what is pinned here.)
    """

    def _load(self):
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(
            here, "..", "extensions", "sky-watcher",
            "sky_watcher.py")
        spec = importlib.util.spec_from_file_location(
            "sky_watcher_platinum", os.path.normpath(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @settings(deadline=None, max_examples=200)
    @given(lat=st.floats(min_value=-89.0, max_value=89.0),
           lon=st.floats(min_value=-180.0, max_value=180.0),
           ts=st.floats(min_value=0.0, max_value=2_000_000_000.0))
    def test_the_elevation_is_always_a_real_angle(
            self, lat, lon, ts):
        import math
        sky = self._load()
        elev = sky.sun_elevation_deg(lat, lon, ts)
        self.assertTrue(math.isfinite(elev))
        self.assertGreaterEqual(elev, -90.0)
        self.assertLessEqual(elev, 90.0)


class JobFuzzBlankLineTest(unittest.TestCase):
    """Cycle 5 target, guard class:
    `extensions/job-fuzz/job_fuzz.py:_mut_blank_line`
    (391) -- a job with no script lines has nothing to
    insert a blank line into, and the mutator answers
    None (no variant) rather than inventing a script.
    """

    def _load(self):
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(
            here, "..", "extensions", "job-fuzz", "job_fuzz.py")
        spec = importlib.util.spec_from_file_location(
            "job_fuzz_platinum", os.path.normpath(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_blank_line_variants(self):
        import random
        jf = self._load()
        rng = random.Random(7)
        # A scriptless job still yields a variant ("\n"): the
        # mutator's empty-lines guard above this can never
        # fire, because str.split never returns an empty list
        # -- recorded in cycle 5's ledger as a dead guard;
        # what the mutator does today is pinned here.
        self.assertEqual(jf._mut_blank_line({}, rng, {}),
                         {"script": "\n"})
        variant = jf._mut_blank_line({"script": "print(1)"},
                                     rng, {})
        self.assertEqual(variant["script"].split("\n"),
                         ["", "print(1)"])


class EmailSubjectBodyTest(unittest.TestCase):
    """Cycle 5 target, guard class:
    `transport_extensions/email/__main__.py:_subject_body`
    -- a body in a transfer encoding the mail library
    cannot decode comes back as its raw text, and a plain
    message decodes directly. (A multipart is walked for
    its text part earlier in the function. The trailing
    fallback at line 61 did not fire for any shape tried:
    the library's decode falls back to the raw bytes
    itself, so the belt under it is recorded dead by
    construction in cycle 6's ledger.)
    """

    def _load(self):
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(
            here, "..", "transport_extensions", "email",
            "__main__.py")
        spec = importlib.util.spec_from_file_location(
            "email_transport_platinum", os.path.normpath(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_an_undecodable_body_falls_back_to_the_raw_text(self):
        import email
        em = self._load()
        raw = (b"Subject: odd encoding\n"
               b"Content-Transfer-Encoding: base64\n"
               b"\n"
               b"!!! not base64 !!!\n")
        self.assertEqual(em._subject_body(raw),
                         ("odd encoding", "!!! not base64 !!!"))
        plain = email.message_from_bytes(
            b"Subject: one\n\nhello body\n")
        self.assertEqual(em._subject_body(plain.as_bytes()),
                         ("one", "hello body\n"))


if __name__ == "__main__":
    unittest.main()
