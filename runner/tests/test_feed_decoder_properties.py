# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Property tests for the eight feed decoders.

Each feed sense reads text or datagrams that another program wrote,
and an attacker on the box or the wire can shape some of it. The
example tests pin what a good record means. These pin what any input
means: a decoder answers its documented shape and never raises, a
reader never wedges on a poison line, and whatever comes out can be
stored as strict JSON.

The checks are plain functions so the regression cases below run
without Hypothesis; the @given tests feed them generated input.
"""
import importlib.util
import json
import math
import os
import shutil
import struct
import tempfile
import unittest

try:
    from hypothesis import given, settings, strategies as st
except ImportError:  # pragma: no cover - hypothesis is a test-only dep
    given = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

JSON_FEEDS = ("suricata", "zeek", "osquery", "falco", "wazuh")
LINE_FEEDS = JSON_FEEDS + ("sysmon",)


def _load(name):
    path = os.path.join(ROOT, "runner", "extensions", "%s-feed" % name,
                        "%s_feed.py" % name)
    spec = importlib.util.spec_from_file_location(
        "%s_feed_properties" % name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FEEDS = {n: _load(n) for n in LINE_FEEDS + ("aide", "softflowd")}

# A line nested past the C stack. json.loads answers RecursionError,
# not ValueError, and before 3.12.69 that escaped five parsers: one
# such line in eve.json crashed the sense on every pass, because the
# reader never got past it.
DEEP = "[" * 200000
DEEP_IN_OBJECT = '{"event_type": "alert", "x": ' + "[" * 200000


def _strict_json(value):
    json.dumps(value, allow_nan=False)


# --- the checks -------------------------------------------------------

def check_line_parser(mod, line):
    """parse_event answers None or a dict that stores as strict JSON."""
    result = mod.parse_event(line)
    if result is None:
        return
    assert isinstance(result, dict), type(result)
    _strict_json(result)
    ts = result.get("ts")
    if ts is not None:
        assert isinstance(ts, (int, float)) and not isinstance(ts, bool)
        assert math.isfinite(ts), ts


def check_reader(mod, content):
    """A tail over arbitrary bytes never raises and never wedges."""
    tmp = tempfile.mkdtemp(prefix="hp-feedprop-")
    try:
        path = os.path.join(tmp, "feed.log")
        with open(path, "wb") as fh:
            fh.write(content)
        events, reader = mod.read_new_events([path], {})
        assert isinstance(events, list)
        for event in events:
            assert isinstance(event, dict)
            _strict_json(event)
        _strict_json(reader)
        stamps = [e["ts"] for e in events if "ts" in e]
        assert stamps == sorted(stamps)
        # A second pass from the saved state reads nothing new: the
        # first pass moved past every line, poison ones included.
        again, _ = mod.read_new_events([path], reader)
        assert again == [] or mod is FEEDS["sysmon"], again
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_aide(text):
    report = FEEDS["aide"].parse_report(text)
    assert set(report) == {"added", "removed", "changed", "differences"}
    assert isinstance(report["differences"], bool)
    for key in ("added", "removed", "changed"):
        assert all(isinstance(p, str) for p in report[key])
        # Every path the parser reports is text the report carried.
        assert all(p in text for p in report[key])


def check_datagram(data, templates=None):
    mod = FEEDS["softflowd"]
    stats = {}
    flows, learned = mod.decode_datagram(data, templates, now=1.0e9,
                                         stats=stats)
    assert isinstance(flows, list)
    assert isinstance(learned, dict)
    for flow in flows:
        assert isinstance(flow, dict)
        _strict_json(flow)
    return flows, learned


def _v5_datagram(count, records):
    mod = FEEDS["softflowd"]
    head = mod._V5_HEADER.pack(5, count, 1000, 1_700_000_000, 0, 1, 0, 0, 0)
    body = b""
    for r in range(records):
        body += mod._V5_RECORD.pack(
            0xC6336407, 0x0A000001 + r, 0, 1, 2, 10, 1500, 0, 900,
            40000 + r, 443, 0, 0x18, 6, 0, 0, 0, 24, 8, 0)
    return head + body


# --- regressions (no Hypothesis needed) -------------------------------

class PoisonLineTest(unittest.TestCase):
    def test_deep_nesting_answers_none(self):
        for name in JSON_FEEDS:
            for line in (DEEP, DEEP_IN_OBJECT):
                with self.subTest(feed=name, line=line[:30]):
                    self.assertIsNone(FEEDS[name].parse_event(line))

    def test_reader_moves_past_a_deep_line(self):
        for name in JSON_FEEDS:
            with self.subTest(feed=name):
                check_reader(FEEDS[name],
                             (DEEP_IN_OBJECT + "\n").encode() * 2)

    def test_sysmon_deep_xml_and_entity_expansion(self):
        deep = "<Event>" + "<a>" * 200000 + "</a>" * 200000 + "</Event>"
        ents = "".join('<!ENTITY %s "%s">' % (c, ("&%s;" % p) * 10)
                       for p, c in zip("abcdefgh", "bcdefghi"))
        laughs = ('<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa">'
                  + ents + ']><Event><System><EventID>1</EventID>'
                  '</System><EventData><Data Name="Image">&i;</Data>'
                  '</EventData></Event>')
        for text in (deep, laughs):
            check_line_parser(FEEDS["sysmon"], text)

    def test_invalid_utf8_and_nul_never_raise(self):
        junk = b"\xff\xfe\x00{\"ts\": 1}\n\xc3\x28\n\x00\x00\n"
        for name in LINE_FEEDS:
            with self.subTest(feed=name):
                check_reader(FEEDS[name], junk)

    def test_v5_truncation_only_drops_the_tail(self):
        full = _v5_datagram(3, 3)
        seen = []
        for cut in range(len(full) + 1):
            flows, _ = check_datagram(full[:cut])
            seen.append(len(flows))
        self.assertEqual(seen, sorted(seen))
        self.assertEqual(seen[-1], 3)

    def test_v5_count_larger_than_body(self):
        flows, _ = check_datagram(_v5_datagram(65535, 1))
        self.assertEqual(len(flows), 1)


# --- properties -------------------------------------------------------

if given is not None:
    _scalar = st.one_of(
        st.none(), st.booleans(), st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=40))
    _value = st.recursive(
        _scalar,
        lambda c: st.one_of(st.lists(c, max_size=4),
                            st.dictionaries(st.text(max_size=10), c,
                                            max_size=4)),
        max_leaves=16)
    # Field names the feeds actually read, so generated records reach
    # past the first type check instead of all dying at the door.
    _fields = st.sampled_from([
        "event_type", "timestamp", "alert", "anomaly", "signature",
        "signature_id", "severity", "category", "src_ip", "src_port",
        "dest_ip", "dest_port", "proto", "type", "event", "layer",
        "ts", "uid", "id.orig_h", "id.resp_h", "query", "qtype_name",
        "name", "action", "columns", "hostIdentifier", "unixTime",
        "rule", "priority", "output", "output_fields", "time",
        "agent", "id", "level", "description", "groups", "data",
        "decoder", "location", "full_log"])
    _record = st.dictionaries(_fields, _value, max_size=10)
    _event_type = st.sampled_from(["alert", "anomaly", "dns", "flow"])

    def _shaped(rec, kind):
        rec = dict(rec)
        rec["event_type"] = kind
        return rec

    _lines = st.one_of(
        st.text(max_size=200),
        _value.map(json.dumps),
        st.builds(_shaped, _record, _event_type).map(json.dumps),
        st.binary(max_size=200).map(
            lambda b: b.decode("utf-8", errors="replace")))

    _xml = st.lists(st.sampled_from([
        "<Event>", "</Event>", "<System>", "</System>",
        "<EventID>1</EventID>", "<EventID>", "<EventData>",
        "</EventData>", '<Data Name="Image">', '<Data Name="CommandLine">',
        "</Data>", "C:\\Temp\\a.exe", "-enc QQBBAA==", "&amp;", "&bogus;",
        "<![CDATA[", "]]>", "\x00", "\n"]), max_size=30).map("".join)

    _aide_lines = st.lists(st.one_of(
        st.sampled_from([
            "Added entries:", "Removed entries:", "Changed entries:",
            "---------------------------------------------------",
            "AIDE found differences between database and filesystem!!",
            "AIDE found NO differences between database and filesystem.",
            "The attributes of the (uncompressed) database(s):",
            "Detailed information about changes:", ""]),
        st.builds(lambda flag, p: "%s: %s" % (flag, p),
                  st.sampled_from(["f++++++++++++++++", "f-----------------",
                                   "f   ...    .C...", "d =.... mc.. .."]),
                  st.text(min_size=1, max_size=30)),
        st.text(max_size=60)), max_size=30).map("\n".join)

    _netflow = st.one_of(
        st.binary(max_size=300),
        st.builds(lambda v, rest: struct.pack("!H", v) + rest,
                  st.sampled_from([5, 9, 10]), st.binary(max_size=400)),
        st.builds(lambda n, r, cut: _v5_datagram(n, r)[:cut],
                  st.integers(0, 65535), st.integers(0, 4),
                  st.integers(0, 24 + 48 * 4)))

    _quick = settings(max_examples=150, deadline=None)

    class LineParserProperties(unittest.TestCase):
        @_quick
        @given(name=st.sampled_from(LINE_FEEDS), line=_lines)
        def test_parse_event_never_raises(self, name, line):
            check_line_parser(FEEDS[name], line)

        @_quick
        @given(line=_xml)
        def test_sysmon_xml_fragments(self, line):
            check_line_parser(FEEDS["sysmon"], line)

        @_quick
        @given(fields=st.lists(_fields, min_size=1, max_size=8),
               cells=st.lists(st.text(max_size=20), max_size=8))
        def test_zeek_tsv_rows(self, fields, cells):
            mod = FEEDS["zeek"]
            header = mod.parse_event("#fields\t" + "\t".join(fields))
            names = header["fields"] if header else fields
            row = "\t".join(c.replace("\t", " ").replace("\n", " ")
                            for c in cells)
            result = mod.parse_event(row, names)
            if result is not None:
                _strict_json(result)

    class ReaderProperties(unittest.TestCase):
        @settings(max_examples=40, deadline=None)
        @given(name=st.sampled_from(LINE_FEEDS),
               lines=st.lists(_lines, max_size=12),
               tail=st.binary(max_size=40))
        def test_tail_never_raises_or_wedges(self, name, lines, tail):
            content = "\n".join(lines).encode("utf-8", "surrogatepass")
            check_reader(FEEDS[name], content + b"\n" + tail)

    class AideProperties(unittest.TestCase):
        @_quick
        @given(text=_aide_lines)
        def test_report_shape(self, text):
            check_aide(text)

    class NetflowProperties(unittest.TestCase):
        @settings(max_examples=300, deadline=None)
        @given(data=_netflow)
        def test_decode_never_raises(self, data):
            check_datagram(data)

        @_quick
        @given(packets=st.lists(_netflow, max_size=6))
        def test_templates_carry_across_datagrams(self, packets):
            templates = None
            for data in packets:
                _, templates = check_datagram(data, templates)


if __name__ == "__main__":
    unittest.main()
