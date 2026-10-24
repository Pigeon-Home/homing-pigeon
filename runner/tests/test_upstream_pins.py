"""The upstream files an extension carries, and the reading they back.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

Three things are pinned here, none of which needs the network:

1. The manifest `upstream` block parses under the extension API's
   rules (runner/ops/extensions.py), and the rules refuse the shapes
   that would let a path escape or a pin lie.
2. What sits under `<extension>/upstream/` matches the manifest and
   its PIN.json exactly, and everything together stays under the
   5 MiB budget. runner/tools/fetch_upstream.py --check is the same
   verdict from the command line; this is the one the suite runs.
3. The format each feed adapter parses is still the format its
   upstream source defines: the fields the adapter reads are named
   in the schema, the record layout, or the writer it carries. When
   an upstream rename breaks a sense, this is where it shows.

The fetch itself (git, network) is exercised by the build, not here.
"""
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runner", "tools"))

from runner.ops import extensions as E  # noqa: E402
import fetch_upstream as FU  # noqa: E402

EXT = os.path.join(ROOT, "runner", "extensions")
FEEDS_WITH_UPSTREAM = (
    "aide-feed", "falco-feed", "osquery-feed", "softflowd-feed",
    "suricata-feed", "sysmon-feed", "wazuh-feed", "zeek-feed",
)


def _manifest(name):
    with open(os.path.join(EXT, name, "extension.json"), encoding="utf-8") as f:
        return json.load(f)


def _upstream_file(name, rel):
    p = os.path.join(EXT, name, "upstream", *rel.split("/"))
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def _good_block(**kw):
    b = {"repo": "https://github.com/OISF/suricata", "ref": "main",
         "pin": "9451642a2885dde09c27826dabd4d514be984c00",
         "paths": ["etc/schema.json", "LICENSE"]}
    b.update(kw)
    return b


def _sense(**kw):
    m = {"name": "x", "version": "0.1.0", "api_version": 1, "kind": "sense",
         "signals": [{"name": "s", "description": "d"}]}
    m.update(kw)
    return m


class ManifestUpstreamBlock(unittest.TestCase):
    def test_absent_is_none(self):
        self.assertIsNone(E.parse_manifest(_sense())["upstream"])

    def test_good_block_round_trips(self):
        m = E.parse_manifest(_sense(upstream=_good_block()))
        self.assertEqual(m["upstream"], dict(_good_block(), license=""))
        m = E.parse_manifest(_sense(upstream=_good_block(license="GPL-2.0-only")))
        self.assertEqual(m["upstream"]["license"], "GPL-2.0-only")

    def test_shared_rules_with_the_tool(self):
        # The tool validates the same block the runner does; a
        # manifest the runner loads is one the tool fetches.
        self.assertEqual(FU.validate_upstream(_good_block()),
                         dict(_good_block(), license=""))

    def test_refuses_multiline_license(self):
        self._refused("license", license="GPL-2.0-only\nMIT")

    def _refused(self, msg, **kw):
        with self.assertRaises(ValueError) as cm:
            E.parse_manifest(_sense(upstream=_good_block(**kw)))
        self.assertIn(msg, str(cm.exception))
        with self.assertRaises(FU.UpstreamError):
            FU.validate_upstream(_good_block(**kw))

    def test_refuses_non_github_repo(self):
        self._refused("repo", repo="https://example.com/x/y")
        self._refused("repo", repo="git@github.com:OISF/suricata.git")

    def test_refuses_short_or_upper_pin(self):
        self._refused("pin", pin="9451642a")
        self._refused("pin", pin="9451642A2885DDE09C27826DABD4D514BE984C00")

    def test_refuses_ref_that_looks_like_an_option(self):
        self._refused("ref", ref="--upload-pack=evil")
        self._refused("ref", ref="")

    def test_refuses_escaping_paths(self):
        self._refused("paths", paths=["../etc/passwd"])
        self._refused("paths", paths=["/etc/passwd"])
        self._refused("paths", paths=["a/./b"])
        self._refused("paths", paths=["-rf"])
        self._refused("paths", paths=["a\\b"])

    def test_refuses_duplicate_and_empty_paths(self):
        self._refused("twice", paths=["LICENSE", "LICENSE"])
        self._refused("paths", paths=[])

    def test_refuses_unknown_and_missing_members(self):
        with self.assertRaises(ValueError) as cm:
            E.parse_manifest(_sense(upstream=_good_block(mirror="x")))
        self.assertIn("mirror", str(cm.exception))
        b = _good_block()
        del b["pin"]
        with self.assertRaises(ValueError) as cm:
            E.parse_manifest(_sense(upstream=b))
        self.assertIn("pin", str(cm.exception))

    def test_unknown_manifest_field_is_still_refused(self):
        # Adding `upstream` did not loosen the by-name refusal.
        with self.assertRaises(ValueError) as cm:
            E.parse_manifest(_sense(upstrem=_good_block()))
        self.assertIn("upstrem", str(cm.exception))


class ShippedUpstreamState(unittest.TestCase):
    def test_every_feed_names_an_upstream(self):
        for name in FEEDS_WITH_UPSTREAM:
            with self.subTest(name):
                self.assertIn("upstream", _manifest(name))

    def test_tree_matches_manifests_and_pins(self):
        # The same verdict as `fetch_upstream.py --check`, from the
        # library, so a stale or tampered upstream/ fails the suite.
        for name, ext_dir, _m, data in FU.iter_manifests(EXT):
            with self.subTest(name):
                block = data.get("upstream")
                updir = os.path.join(ext_dir, "upstream")
                if block is None:
                    self.assertFalse(os.path.isdir(updir),
                                     f"{name}: upstream/ without a manifest block")
                    continue
                block = FU.validate_upstream(block)
                ok, reasons = FU.current_state(ext_dir, block)
                self.assertTrue(ok, f"{name}: {'; '.join(reasons)}")

    def test_pin_json_is_self_consistent(self):
        for name in FEEDS_WITH_UPSTREAM:
            with self.subTest(name):
                pin = FU.read_pin(os.path.join(EXT, name))
                self.assertEqual(pin["pin"], _manifest(name)["upstream"]["pin"])
                self.assertEqual(sum(v["bytes"] for v in pin["files"].values()),
                                 pin["bytes"])
                self.assertRegex(pin["fetched_at"],
                                 r"\A\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")

    def test_every_upstream_carries_its_license(self):
        for name in FEEDS_WITH_UPSTREAM:
            with self.subTest(name):
                block = _manifest(name)["upstream"]
                self.assertTrue(
                    any(p.split("/")[-1] in ("LICENSE", "COPYING")
                        for p in block["paths"]),
                    f"{name}: upstream paths carry no LICENSE or COPYING")
                self.assertTrue(block.get("license"),
                                f"{name}: upstream names no SPDX license")

    def test_the_manifest_block_is_the_one_declaration(self):
        # The retired upstream.json and provenance/ bundles never come
        # back beside a manifest that declares its upstream, and the
        # extension's sources.json names that repository by
        # "upstream": true, not by spelling it a second time.
        for name in FEEDS_WITH_UPSTREAM:
            with self.subTest(name):
                d = os.path.join(EXT, name)
                self.assertFalse(os.path.exists(os.path.join(d, "upstream.json")))
                self.assertFalse(os.path.exists(os.path.join(d, "provenance")))
                repo = _manifest(name)["upstream"]["repo"].lower()
                sp = os.path.join(d, "sources.json")
                if not os.path.exists(sp):
                    continue
                with open(sp, encoding="utf-8") as f:
                    entries = json.load(f)["sources"]
                dup = [e for e in entries if repo.endswith(
                    "/" + str(e.get("github", "")).lower())]
                self.assertFalse(dup, f"{name}: sources.json repeats the "
                                      f"manifest's repository")
                self.assertTrue(any(e.get("upstream") is True for e in entries),
                                f"{name}: no sources.json entry inherits the "
                                f"manifest's upstream")

    def test_total_under_budget(self):
        total, per = FU.budget_report(EXT)
        self.assertLessEqual(
            total, FU.UPSTREAM_BUDGET_BYTES,
            f"upstream/ totals {total} bytes; largest: "
            + ", ".join(f"{k}={v}" for k, v in
                        sorted(per.items(), key=lambda kv: -kv[1])[:3]))
        self.assertEqual(FU.UPSTREAM_BUDGET_BYTES, 5 * 1024 * 1024)


class FormatDrift(unittest.TestCase):
    """The adapter's reading, checked against the source it carries."""

    def test_suricata_eve_schema_names_what_the_adapter_reads(self):
        schema = json.loads(_upstream_file("suricata-feed", "etc/schema.json"))
        props = schema["properties"]
        for top in ("timestamp", "event_type", "src_ip", "src_port",
                    "dest_ip", "dest_port", "proto", "alert", "anomaly"):
            self.assertIn(top, props, f"eve.json schema lost {top}")
        alert = props["alert"]["properties"]
        for k in ("signature", "signature_id", "severity", "category"):
            self.assertIn(k, alert, f"eve.json alert lost {k}")
        anomaly = props["anomaly"]["properties"]
        for k in ("event", "type", "layer"):
            self.assertIn(k, anomaly, f"eve.json anomaly lost {k}")

    def test_zeek_conn_and_dns_records_name_what_the_adapter_reads(self):
        conn = _upstream_file("zeek-feed", "scripts/base/protocols/conn/main.zeek")
        for field in ("ts", "uid", "id", "proto", "service"):
            self.assertRegex(conn, rf"(?m)^\s*{field}:\s+\S+.*&log",
                             f"Conn::Info lost {field}")
        self.assertIn("conn_id", conn)  # id.orig_h / id.resp_h / id.resp_p
        dns = _upstream_file("zeek-feed", "scripts/base/protocols/dns/main.zeek")
        for field in ("query", "qtype_name"):
            self.assertRegex(dns, rf"(?m)^\s*{field}:\s+\S+.*&log",
                             f"DNS::Info lost {field}")

    def test_osquery_tables_keep_the_adapters_columns(self):
        want = {
            "specs/processes.table": ("pid", "name", "path"),
            "specs/users.table": ("uid", "username"),
            "specs/listening_ports.table": ("pid", "port", "protocol", "address"),
        }
        for rel, cols in want.items():
            spec = _upstream_file("osquery-feed", rel)
            for c in cols:
                self.assertRegex(spec, rf'Column\("{c}"', f"{rel} lost column {c}")

    def test_falco_rules_still_use_the_priorities_the_adapter_maps(self):
        # The rules file spells priorities in capitals (CRITICAL); the
        # alert Falco writes spells them capitalized (Critical). The
        # adapter maps the written form, so compare case-blind.
        rules = _upstream_file("falco-feed", "rules/falco_rules.yaml")
        seen = {p.lower() for p in
                re.findall(r"(?m)^\s*priority:\s*([A-Za-z]+)", rules)}
        self.assertTrue(seen, "no priority: lines in falco_rules.yaml")
        from importlib import util
        spec = util.spec_from_file_location(
            "falco_feed", os.path.join(EXT, "falco-feed", "falco_feed.py"))
        mod = util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        known = {p.lower() for p in mod._PRIORITY_SIGNALS} \
            | {p.lower() for p in mod._PARSED_ONLY}
        # Falco writes a rule's INFO as "Informational"; the adapter
        # parses that spelling and files nothing for it, by design.
        aliases = {"info": "informational"}
        unknown = {aliases.get(p, p) for p in seen} - known
        self.assertFalse(unknown, f"falco rules use priorities the adapter "
                                  f"does not know: {sorted(unknown)}")

    def test_wazuh_to_json_writes_the_keys_the_adapter_reads(self):
        src = _upstream_file("wazuh-feed", "src/analysisd/format/to_json.c")
        for key in ("rule", "agent", "id", "level", "description",
                    "full_log", "decoder"):
            self.assertIn(f'"{key}"', src, f"to_json.c no longer writes {key}")
        # The top-level timestamp and location are added by helpers the
        # writer calls, not by string literals in this file.
        self.assertIn("W_JSON_AddTimestamp", src, "to_json.c dropped the timestamp")
        # `location` appears in the adapter's docstring only; it reads
        # none of it, so its absence from this writer is not drift.

    def test_aide_plain_report_keeps_its_headings(self):
        src = _upstream_file("aide-feed", "src/report_plain.c")
        for heading in ("Added entries", "Removed entries", "Changed entries"):
            self.assertIn(heading, src, f"AIDE plain report lost {heading!r}")

    def test_sysmon_process_create_keeps_its_fields(self):
        xml = _upstream_file("sysmon-feed", "manifest.xml")
        m = re.search(r'<event [^>]*value="1"[^>]*>(.*?)</event>', xml, re.S)
        self.assertIsNotNone(m, "Sysmon manifest lost event 1 (ProcessCreate)")
        body = m.group(1)
        for f in ("UtcTime", "ProcessGuid", "ProcessId", "Image", "CommandLine",
                  "CurrentDirectory", "User", "ParentProcessId", "ParentImage",
                  "ParentCommandLine", "Hashes"):
            self.assertIn(f'name="{f}"', body, f"ProcessCreate lost {f}")

    def test_softflowd_still_emits_the_records_the_collector_decodes(self):
        v5 = _upstream_file("softflowd-feed", "compat/netflow5.c")
        v9 = _upstream_file("softflowd-feed", "compat/netflow9.c")
        # v5: the fixed header and flow record the collector unpacks whole.
        self.assertIn("struct NETFLOW5_HEADER", v5, "netflow5.c lost the v5 header")
        self.assertIn("struct NETFLOW5_FLOW", v5, "netflow5.c lost the v5 record")
        # v9: templates still carry the start/end uptime fields the
        # collector turns into durations (FIRST/LAST_SWITCHED on the wire).
        self.assertIn("flowStartSysUpTime", v9, "netflow9.c dropped flow start time")
        self.assertIn("flowEndSysUpTime", v9, "netflow9.c dropped flow end time")
        self.assertIn("NETFLOW9_SOFTFLOWD_TEMPLATE", v9, "netflow9.c lost its template")


if __name__ == "__main__":
    unittest.main()
