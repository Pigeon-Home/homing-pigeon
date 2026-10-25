"""Softflowd Feed: the example sense that collects NetFlow.

Pins the Softflowd Feed example
(runner/extensions/softflowd-feed/): the manifest through
the real extension loader, the pure decode_datagram() subset
-- NetFlow v5 complete, v9 template-driven, IPFIX with its
enterprise-bit rule -- built byte by byte with struct, the
pure collect_flows() against a fake socket, and the pure
decide() discipline: a new external peer files once, and a
flow's volume and duration signals fire at their thresholds
and only once per flow.

No live sockets anywhere: decode is pure and collect_flows
is driven with a fake socket object.
"""
import importlib.util
import io
import ipaddress
import json
import os
import shutil
import socket
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(
    REPO, "runner", "extensions", "softflowd-feed")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "softflowd_feed_example",
        os.path.join(EXAMPLE_DIR, "softflowd_feed.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SF = _load_example_module()

SECS = 1_700_000_000


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _ip(text):
    return int(ipaddress.IPv4Address(text))


# --- datagram builders (struct, byte by byte) -------------------------

def _v5_datagram(src="10.0.0.5", dst="8.8.8.8", sport=51111,
                 dport=443, proto=6, packets=10, octets=5000,
                 first_ms=90_000, last_ms=99_500, uptime=100_000):
    header = struct.pack("!HHIIIIBBH", 5, 1, uptime, SECS,
                         0, 0, 0, 0, 0)
    record = struct.pack(
        "!IIIHHIIIIHHBBBBHHBBH",
        _ip(src), _ip(dst), 0, 0, 0, packets, octets,
        first_ms, last_ms, sport, dport, 0, 0, proto, 0,
        0, 0, 0, 0, 0)
    assert len(record) == 48
    return header + record


_V9_FIELDS = [(8, 4), (12, 4), (7, 2), (11, 2), (4, 1),
              (2, 4), (1, 4), (22, 4), (21, 4)]


def _v9_template_datagram(fields=_V9_FIELDS, template_id=256,
                          uptime=200_000):
    body = struct.pack("!HH", template_id, len(fields))
    for ftype, flen in fields:
        body += struct.pack("!HH", ftype, flen)
    flowset = struct.pack("!HH", 0, 4 + len(body)) + body
    header = struct.pack("!HHIIII", 9, 1, uptime, SECS, 0, 7)
    return header + flowset


def _v9_data_datagram(record, template_id=256, uptime=200_000):
    flowset = struct.pack("!HH", template_id, 4 + len(record)) + record
    header = struct.pack("!HHIIII", 9, 1, uptime, SECS, 0, 7)
    return header + flowset


def _v9_record(src="10.0.0.5", dst="8.8.8.8", sport=51111,
               dport=443, proto=6, packets=10, octets=5000,
               first_sw=110_000, last_sw=200_000):
    return struct.pack("!IIHHBIIII", _ip(src), _ip(dst), sport,
                       dport, proto, packets, octets, first_sw,
                       last_sw)


_IPFIX_FIELDS = [(8, 4), (12, 4), (7, 2), (11, 2), (4, 1),
                 (2, 4), (1, 4)]


def _ipfix_pair(fields=_IPFIX_FIELDS, template_id=256,
                enterprise=False):
    body = struct.pack("!HH", template_id, len(fields))
    width = 0
    for ftype, flen in fields:
        if enterprise:
            body += struct.pack("!HHI", ftype | 0x8000, flen, 12345)
        else:
            body += struct.pack("!HH", ftype, flen)
        width += flen
    template_set = struct.pack("!HH", 2, 4 + len(body)) + body
    if enterprise:
        record = b"\x08\x08\x08\x08" + b"\x00" * (width - 4)
    else:
        record = struct.pack("!IIHHBII", _ip("10.0.0.5"),
                             _ip("8.8.8.8"), 51111, 443, 6, 10, 5000)
    data_set = struct.pack("!HH", template_id, 4 + len(record)) + record
    total = 16 + len(template_set) + len(data_set)
    header = struct.pack("!HHIII", 10, total, SECS, 0, 7)
    return header + template_set + data_set


def _flow(dst="8.8.8.8", src="192.168.1.20", sport=51111,
          dport=443, proto=6, packets=10, nbytes=1000,
          first=1000.0, last=1010.0):
    return {"version": 9, "src": src, "dst": dst,
            "src_port": sport, "dst_port": dport, "proto": proto,
            "packets": packets, "bytes": nbytes,
            "first": first, "last": last}


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "softflowd_feed")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            [s["name"] for s in clean["signals"]],
            ["flow_new_external_peer", "flow_high_volume",
             "flow_long_lived"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        self.assertEqual(clean["tunables"]["listen_addr"],
                         "127.0.0.1:2055")
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR,
                            os.path.join(d, "softflowd-feed"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("softflowd_feed", registry)


class DecodeV5Test(unittest.TestCase):
    def test_v5_round_trip_fields_and_timestamps(self):
        flows, _templates = SF.decode_datagram(_v5_datagram())
        self.assertEqual(len(flows), 1)
        flow = flows[0]
        self.assertEqual(flow["version"], 5)
        self.assertEqual(flow["src"], "10.0.0.5")
        self.assertEqual(flow["dst"], "8.8.8.8")
        self.assertEqual(flow["src_port"], 51111)
        self.assertEqual(flow["dst_port"], 443)
        self.assertEqual(flow["proto"], 6)
        self.assertEqual(flow["packets"], 10)
        self.assertEqual(flow["bytes"], 5000)
        # First/Last are sysUpTime stamps: converted with the
        # header's unix_secs and sysUpTime (100_000 ms).
        self.assertEqual(flow["first"], SECS - 10.0)
        self.assertEqual(flow["last"], SECS - 0.5)


class DecodeV9Test(unittest.TestCase):
    def test_template_and_data_in_one_datagram(self):
        # Build one datagram carrying both flowsets.
        template = _v9_template_datagram()
        header, template_flowset = template[:20], template[20:]
        record = _v9_record()
        data_flowset = struct.pack("!HH", 256, 4 + len(record)) + record
        packet = header + template_flowset + data_flowset
        flows, _templates = SF.decode_datagram(packet)
        self.assertEqual(len(flows), 1)
        flow = flows[0]
        self.assertEqual(flow["version"], 9)
        self.assertEqual(flow["dst"], "8.8.8.8")
        self.assertEqual(flow["bytes"], 5000)
        # sysUpTime anchor 200_000 ms: first 110_000, last 200_000.
        self.assertEqual(flow["first"], SECS - 90.0)
        self.assertEqual(flow["last"], float(SECS))

    def test_template_and_data_split_across_two_datagrams(self):
        flows, templates = SF.decode_datagram(_v9_template_datagram())
        self.assertEqual(flows, [])
        flows, _templates = SF.decode_datagram(
            _v9_data_datagram(_v9_record()), templates)
        self.assertEqual(len(flows), 1)
        self.assertEqual(flows[0]["src"], "10.0.0.5")

    def test_data_before_its_template_decodes_to_nothing(self):
        flows, _t = SF.decode_datagram(
            _v9_data_datagram(_v9_record()), {})
        self.assertEqual(flows, [])

    def test_unknown_field_record_is_skipped_and_counted(self):
        fields = [(8, 4), (999, 4)]
        _flows, templates = SF.decode_datagram(
            _v9_template_datagram(fields=fields))
        record = struct.pack("!II", _ip("10.0.0.5"), 1234)
        stats = {}
        flows, _t = SF.decode_datagram(
            _v9_data_datagram(record), templates, stats=stats)
        self.assertEqual(flows, [])
        self.assertEqual(stats["skipped_records"], 1)

    def test_truncated_datagrams_are_quiet(self):
        for data in (b"", b"\x00\x05\x00", _v5_datagram()[:30],
                     _v9_template_datagram()[:10], b"\xff\xffjunk"):
            flows, _t = SF.decode_datagram(data)
            self.assertEqual(flows, [], data[:8])


class DecodeIpfixTest(unittest.TestCase):
    def test_ipfix_round_trip_uses_the_collect_time(self):
        flows, _t = SF.decode_datagram(
            _ipfix_pair(), now=SECS + 500.0)
        self.assertEqual(len(flows), 1)
        flow = flows[0]
        self.assertEqual(flow["version"], 10)
        self.assertEqual(flow["dst"], "8.8.8.8")
        self.assertEqual(flow["bytes"], 5000)
        # IPFIX carries no sysUpTime anchor: no fabricated
        # duration, both stamps are the collect time.
        self.assertEqual(flow["first"], SECS + 500.0)
        self.assertEqual(flow["last"], SECS + 500.0)

    def test_ipfix_enterprise_field_is_skipped_and_counted(self):
        stats = {}
        flows, _t = SF.decode_datagram(
            _ipfix_pair(enterprise=True), stats=stats)
        self.assertEqual(flows, [])
        self.assertEqual(stats["skipped_records"], 1)


class _FakeSocket:
    def __init__(self, datagrams):
        self._datagrams = list(datagrams)
        self.bound = None

    def bind(self, addr):
        self.bound = addr

    def settimeout(self, _value):
        pass

    def recvfrom(self, _size):
        if self._datagrams:
            return self._datagrams.pop(0), ("127.0.0.1", 9999)
        raise socket.timeout("the window expired")

    def close(self):
        pass


class DecodeDamageLegsTest(unittest.TestCase):
    """Queue A refill: _parse_v9_templates'
    truncated-fields leg (coverage run
    40189711740: lines 275-276), with the truncated
    v5 shape pinned beside it. A datagram too
    damaged to decode answers with no flows; a
    template whose field list is cut short is not
    recorded at all. (decode_datagram's own
    except at 401-402 sits behind the decoders'
    length guards and cannot be reached through
    the datagram seam; the ledger records that
    disposition.)
    """

    def test_a_truncated_v5_record_decodes_to_nothing(self):
        flows, _t = SF.decode_datagram(
            _v5_datagram()[:30], {}, now=1000.0)
        self.assertEqual(flows, [])

    def test_a_template_cut_short_in_its_fields(self):
        body = struct.pack("!HH", 256, 3)
        body += struct.pack("!HH", 8, 4)
        flowset = struct.pack("!HH", 0, 4 + len(body)) + body
        header = struct.pack("!HHIIII", 9, 1, 200_000, SECS, 0, 7)
        flows, templates = SF.decode_datagram(
            header + flowset, {}, now=1000.0)
        self.assertEqual(flows, [])
        self.assertEqual(templates, {})


class CollectFlowsClockTest(unittest.TestCase):
    """Queue A refill: collect_flows' window-expiry
    and close-failure legs (coverage run
    40189711740: lines 476, 492-493). The pass ends
    when the window closes -- checked at the top of
    the loop, so a datagram that arrives just inside
    the window is the last one read -- and a socket
    that refuses to close is still just a quiet,
    empty pass.
    """

    def test_the_window_closing_ends_the_pass(self):
        import time as _time
        import types as _types
        from unittest import mock as _mock
        ticks = iter([100.0, 100.0, 200.0])
        fake_time = _types.SimpleNamespace(
            time=_time.time, monotonic=lambda: next(ticks))
        manifest = {"tunables": {"listen_addr": "127.0.0.1:0",
                                 "collect_window_sec": 5,
                                 "max_datagrams": 10}}
        with _mock.patch.object(SF, "time", fake_time), \
                _mock.patch.object(SF.socket, "socket",
                                   return_value=_FakeSocket([b""])):
            readings = SF.collect_flows(manifest, {})
        self.assertEqual(readings["flows"], [])

    def test_a_socket_that_will_not_close_is_quiet(self):
        from unittest import mock as _mock

        class BadClose(_FakeSocket):
            def __init__(self):
                super().__init__([])

            def close(self):
                raise OSError("stuck")

        with _mock.patch.object(SF.socket, "socket",
                                return_value=BadClose()):
            readings = SF.collect_flows(
                {"tunables": {"listen_addr": "127.0.0.1:0",
                              "collect_window_sec": 0.05}}, {})
        self.assertEqual(readings["flows"], [])
        self.assertEqual(readings["skipped_records"], 0)


class DecoderEdgesTest(unittest.TestCase):
    """Queue A refill: the softflowd decoder's fallback and
    truncation legs (_flow_from_values and
    _parse_ipfix_templates; coverage run 40189711740:
    5 lines each). The contracts, from the functions' own
    docstrings: an address falls back to the IPv6 field
    when no IPv4 field is present; a flow carrying only
    its LAST switched stamp anchors both ends on it
    rather than inventing a duration; a template record
    truncated mid-field -- or mid enterprise number --
    is not recorded at all; a variable-length field
    records its template tainted, so its data records
    are skipped and counted, never misdecoded.
    """

    def test_ipv6_addresses_when_no_ipv4_field(self):
        values = {
            27: ipaddress.IPv6Address("2001:db8::1").packed,
            28: ipaddress.IPv6Address("2001:db8::2").packed,
            7: (51111).to_bytes(2, "big"),
            11: (443).to_bytes(2, "big"),
            4: b"\x06",
        }
        flow = SF._flow_from_values(10, values, 1234.5)
        self.assertEqual(flow["src"], "2001:db8::1")
        self.assertEqual(flow["dst"], "2001:db8::2")
        self.assertEqual(flow["src_port"], 51111)
        self.assertEqual(flow["first"], 1234.5)
        self.assertEqual(flow["last"], 1234.5)

    def test_only_a_last_stamp_anchors_both_ends(self):
        values = {8: _ip("10.0.0.5").to_bytes(4, "big"),
                  12: _ip("8.8.8.8").to_bytes(4, "big"),
                  21: (200_000).to_bytes(4, "big")}
        flow = SF._flow_from_values(9, values, 999.0,
                                    uptime_ms=250_000,
                                    unix_secs=SECS)
        self.assertEqual(flow["last"], SECS - 50.0)
        self.assertEqual(flow["first"], SECS - 50.0)

    def test_a_template_truncated_mid_field_is_not_recorded(self):
        body = struct.pack("!HH", 256, 2) \
            + struct.pack("!HH", 8, 4) + b"\x00\x02"
        templates = {}
        SF._parse_ipfix_templates(body, (10, 7), templates)
        self.assertEqual(templates, {})

    def test_a_truncated_enterprise_number_is_not_recorded(self):
        body = struct.pack("!HH", 256, 1) \
            + struct.pack("!HH", 8 | 0x8000, 4) + b"\x00\x00"
        templates = {}
        SF._parse_ipfix_templates(body, (10, 7), templates)
        self.assertEqual(templates, {})

    def test_a_variable_length_field_taints_the_template(self):
        body = struct.pack("!HH", 256, 1) \
            + struct.pack("!HH", 8, 0xFFFF)
        templates = {}
        SF._parse_ipfix_templates(body, (10, 7), templates)
        rec = templates[(10, 7, 256)]
        self.assertEqual(rec["fields"], [(8, 0xFFFF)])
        self.assertTrue(rec["tainted"])
        clean = {}
        SF._parse_ipfix_templates(
            struct.pack("!HH", 256, 1) + struct.pack("!HH", 8, 4),
            (10, 7), clean)
        self.assertFalse(clean[(10, 7, 256)]["tainted"])


class CollectFlowsTest(unittest.TestCase):
    def test_collect_flows_decodes_what_the_socket_yields(self):
        fake = _FakeSocket([_v5_datagram()])
        manifest = _manifest()
        with mock.patch("socket.socket", return_value=fake):
            readings = SF.collect_flows(manifest, {})
        self.assertEqual(fake.bound, ("127.0.0.1", 2055))
        self.assertEqual(len(readings["flows"]), 1)
        self.assertEqual(readings["flows"][0]["dst"], "8.8.8.8")
        self.assertEqual(readings["skipped_records"], 0)
        self.assertIsInstance(readings["now"], float)

    def test_collect_flows_counts_skipped_records(self):
        _f, templates_packet = None, _v9_template_datagram(
            fields=[(8, 4), (999, 4)])
        record = struct.pack("!II", _ip("10.0.0.5"), 1234)
        fake = _FakeSocket([templates_packet,
                            _v9_data_datagram(record)])
        with mock.patch("socket.socket", return_value=fake):
            readings = SF.collect_flows(_manifest(), {})
        self.assertEqual(readings["flows"], [])
        self.assertEqual(readings["skipped_records"], 1)


class DecideTest(unittest.TestCase):
    def decide(self, readings, state=None, manifest=None):
        return SF.decide(readings, manifest or _manifest(),
                         state if state is not None else {})

    def test_new_external_peer_files_info_once(self):
        readings = {"now": 2000.0, "flows": [_flow()]}
        alerts, state = self.decide(readings)
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "softflowd_feed")
        self.assertEqual(alert["signal"], "flow_new_external_peer")
        self.assertEqual(alert["severity"], "info")
        self.assertEqual(alert["detail"]["dst"], "8.8.8.8")
        self.assertIn("8.8.8.8", state["peers"])
        alerts, _state = self.decide(readings, state=state)
        self.assertEqual(alerts, [])

    def test_non_external_destinations_are_quiet(self):
        for dst in ("10.0.0.5", "192.168.1.1", "172.16.0.9",
                    "127.0.0.1", "169.254.1.1", "224.0.0.1",
                    "::1", "fe80::1"):
            alerts, _state = self.decide(
                {"now": 2000.0, "flows": [_flow(dst=dst)]})
            self.assertEqual(alerts, [], dst)

    def test_allowlisted_peer_is_quiet(self):
        manifest = _manifest()
        manifest["tunables"]["allowlist"] = ["8.8.8.0/24"]
        alerts, _state = self.decide(
            {"now": 2000.0, "flows": [_flow()]}, manifest=manifest)
        self.assertEqual(alerts, [])

    def test_high_volume_fires_at_the_threshold_only(self):
        big = _flow(nbytes=50_000_000, dst="10.0.0.5")
        alerts, _state = self.decide({"now": 2000.0, "flows": [big]})
        self.assertEqual([a["signal"] for a in alerts],
                         ["flow_high_volume"])
        self.assertEqual(alerts[0]["severity"], "medium")
        self.assertEqual(alerts[0]["detail"]["bytes"], 50_000_000)
        small = _flow(nbytes=49_999_999, dst="10.0.0.5")
        alerts, _state = self.decide({"now": 2000.0, "flows": [small]})
        self.assertEqual(alerts, [])

    def test_long_lived_fires_at_the_threshold_only(self):
        long_flow = _flow(dst="10.0.0.5", first=0.0, last=3600.0)
        alerts, _state = self.decide(
            {"now": 4000.0, "flows": [long_flow]})
        self.assertEqual([a["signal"] for a in alerts],
                         ["flow_long_lived"])
        self.assertEqual(alerts[0]["severity"], "info")
        self.assertEqual(alerts[0]["detail"]["duration_sec"], 3600.0)
        short = _flow(dst="10.0.0.5", first=0.0, last=3599.0)
        alerts, _state = self.decide({"now": 4000.0, "flows": [short]})
        self.assertEqual(alerts, [])

    def test_same_readings_twice_files_nothing_second_time(self):
        flow = _flow(nbytes=60_000_000, first=0.0, last=7200.0)
        readings = {"now": 8000.0, "flows": [flow]}
        alerts, state = self.decide(readings)
        self.assertEqual([a["signal"] for a in alerts],
                         ["flow_new_external_peer", "flow_high_volume",
                          "flow_long_lived"])
        alerts, _state = self.decide(readings, state=state)
        self.assertEqual(alerts, [])

    def test_below_every_threshold_is_quiet(self):
        alerts, _state = self.decide(
            {"now": 2000.0, "flows": [_flow(dst="10.0.0.5")]})
        self.assertEqual(alerts, [])

    def test_peer_memory_is_bounded(self):
        manifest = _manifest()
        manifest["tunables"]["max_known_peers"] = 2
        flows = [_flow(dst=f"8.8.8.{n}", sport=40000 + n)
                 for n in (1, 2, 3)]
        alerts, state = self.decide({"now": 2000.0, "flows": flows},
                                    manifest=manifest)
        self.assertEqual(len(alerts), 3)
        self.assertEqual(state["peers"], ["8.8.8.2", "8.8.8.3"])

    def test_unusable_flows_are_ignored(self):
        readings = {"now": 2000.0, "flows": [
            None, {}, {"src": "x"},
            _flow(dst="not-an-ip", nbytes=-1)]}
        alerts, _state = self.decide(readings)
        self.assertEqual(alerts, [])


class MainTest(unittest.TestCase):
    def test_readings_fixture_files_the_peer(self):
        with tempfile.TemporaryDirectory() as d:
            readings_path = os.path.join(d, "readings.json")
            state_path = os.path.join(d, "state.json")
            with open(readings_path, "w", encoding="utf-8") as fh:
                json.dump({"now": 2000.0, "flows": [_flow()]}, fh)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = SF.main(["--readings", readings_path,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual([p["signal"] for p in printed],
                             ["flow_new_external_peer"])


class SoftflowdMainDeliveryTest(unittest.TestCase):
    """Queue A refill: softflowd-feed main's live branch
    and local-delivery legs (coverage run 40187685363:
    7 lines on both platforms). Same contract as every
    sense main: the live collection runs when no
    readings file is given (collect_flows itself is
    covered by CollectFlowsTest; here it is stubbed so
    the branch main takes is what is under test);
    delivery not set up is exit 2; a short delivery is
    exit 2 with the state unwritten, so the next pass
    reports these flows again.
    """

    ENV = "HP_SOFT_SECRET"

    def _drive(self, d, extra, readings=None):
        state = os.path.join(d, "state.json")
        argv = ["--state", state, "--secret-env", self.ENV]
        if readings is not None:
            path = os.path.join(d, "readings.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(readings, fh)
            argv += ["--readings", path]
        err = io.StringIO()
        with redirect_stderr(err):
            rc = SF.main(argv + extra)
        return rc, state, err.getvalue()

    def _alert_readings(self):
        return {"now": 2000.0, "flows": [_flow()]}

    def test_the_live_branch_runs_without_a_readings_file(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    SF, "collect_flows",
                    return_value=self._alert_readings()):
                rc, state, _err = self._drive(d, [])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(state))

    def test_local_delivery_success_writes_state(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ[self.ENV] = "ab" * 32
            try:
                rc, state, _err = self._drive(
                    d, ["--local-dir", d],
                    readings=self._alert_readings())
            finally:
                os.environ.pop(self.ENV, None)
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(state))
            inbox = os.path.join(d, "local-inbox")
            self.assertEqual(len(os.listdir(inbox)), 1)

    def test_local_delivery_not_set_up_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ.pop(self.ENV, None)
            rc, state, _err = self._drive(
                d, ["--local-dir", d],
                readings=self._alert_readings())
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(state))

    def test_short_delivery_is_exit_2_and_saves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            blocker = os.path.join(d, "blocker")
            with open(blocker, "w", encoding="utf-8") as fh:
                fh.write("not a directory")
            os.environ[self.ENV] = "ab" * 32
            try:
                rc, state, err = self._drive(
                    d, ["--local-dir", blocker],
                    readings=self._alert_readings())
            finally:
                os.environ.pop(self.ENV, None)
            self.assertEqual(rc, 2)
            self.assertIn("state not saved", err)
            self.assertFalse(os.path.exists(state))


class DecodeEmptyLegsTest(unittest.TestCase):
    """Queue A refill: the decoders' empty
    answers (coverage run 40189711740:
    _decode_records line 216, _decode_templated
    line 336). A template whose fields total
    zero bytes decodes no records, and an
    IPFIX datagram shorter than its own header
    decodes no flows -- both are empty answers,
    not errors.
    """

    def test_a_zero_length_template_decodes_nothing(self):
        self.assertEqual(
            SF._decode_records(b"\x00" * 8, [], 5, 0.0,
                               None, 0, {}),
            [])

    def test_a_short_ipfix_datagram_decodes_nothing(self):
        self.assertEqual(
            SF._decode_templated(b"\x00\x0a\x00\x04", 10,
                                 {}, 0.0, {}),
            [])


if __name__ == "__main__":
    unittest.main()
