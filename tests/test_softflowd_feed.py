"""Softflowd Feed: the example sense that collects NetFlow.

Pins the Softflowd Feed example
(extensions/softflowd-feed/): the manifest through
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
from contextlib import redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(
    REPO, "extensions", "softflowd-feed")


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


if __name__ == "__main__":
    unittest.main()
